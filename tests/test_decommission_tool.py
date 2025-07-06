import pytest
from pathlib import Path
from decommission_tool import PostgreSQLDecommissionTool

@pytest.fixture
def temp_repo(tmp_path: Path) -> Path:
    """Create a temporary repository structure for testing."""
    repo_dir = tmp_path / "test-repo"
    charts_dir = repo_dir / "charts"
    templates_dir = charts_dir / "templates"
    
    templates_dir.mkdir(parents=True)

    # 1. Helm Chart with a postgres dependency
    (charts_dir / "Chart.yaml").write_text("""
apiVersion: v2
name: my-app
dependencies:
  - name: postgresql
    version: "12.1.6"
    repository: "https://charts.bitnami.com/bitnami"
""")

    # 2. values.yaml with a DB name reference
    (charts_dir / "values.yaml").write_text("""
replicaCount: 1
database:
  name: my_test_db
  user: admin
""")

    # 3. A PVC manifest
    (templates_dir / "pvc.yaml").write_text("""
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: postgres-data-pvc
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 1Gi
""")
    # 4. A source file with a DSN
    (repo_dir / "main.go").write_text('const dsn = "postgres://user:pass@host/my_test_db"')

    return repo_dir

def test_scan_finds_helm_dependency(temp_repo: Path):
    """Verify that a Helm dependency is correctly identified."""
    tool = PostgreSQLDecommissionTool(str(temp_repo), "postgresql")
    findings = tool.scan_repository()
    assert len(findings['helm_dependencies']) == 1
    helm_finding = findings['helm_dependencies'][0]
    assert helm_finding['severity'] == 'high'
    assert 'Chart.yaml' in helm_finding['file']

def test_scan_finds_config_reference(temp_repo: Path):
    """Verify that a database name in values.yaml is found."""
    tool = PostgreSQLDecommissionTool(str(temp_repo), "my_test_db")
    findings = tool.scan_repository()
    assert len(findings['config_references']) >= 1
    config_finding = findings['config_references'][0]
    assert config_finding['severity'] == 'medium'
    assert 'values.yaml' in config_finding['file']

def test_scan_finds_pvc_reference(temp_repo: Path):
    """Verify that a PVC with 'postgres' in the name is found."""
    tool = PostgreSQLDecommissionTool(str(temp_repo), "any_db")
    findings = tool.scan_repository()
    assert len(findings['pvc_references']) == 1
    pvc_finding = findings['pvc_references'][0]
    assert pvc_finding['severity'] == 'critical'
    assert 'pvc.yaml' in pvc_finding['file']
    
def test_scan_finds_source_code_reference(temp_repo: Path):
    """Verify that a DSN in a source code file is found."""
    tool = PostgreSQLDecommissionTool(str(temp_repo), "my_test_db")
    findings = tool.scan_repository()
    assert len(findings['source_code_references']) == 1
    dsn_finding = findings['source_code_references'][0]
    assert dsn_finding['severity'] == 'high'
    assert 'main.go' in dsn_finding['file']

def test_exit_code_on_critical_findings(temp_repo: Path, capsys):
    """Verify the tool suggests a non-zero exit for critical findings."""
    # This test doesn't check sys.exit() directly but checks the output message.
    # In a real CI, the exit code itself would be asserted.
    tool = PostgreSQLDecommissionTool(str(temp_repo), "any_db")
    findings = tool.scan_repository()
    # Mocking main() is complex, so we call the summary function directly.
    from decommission_tool import generate_summary_and_plan
    summary = generate_summary_and_plan(findings, str(temp_repo))
    
    captured = capsys.readouterr()
    # Check if the summary was printed, which happens before the final exit message
    assert "CRITICAL: 1" in captured.out
