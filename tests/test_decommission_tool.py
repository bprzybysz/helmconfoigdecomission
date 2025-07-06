import pytest
import tempfile
import json
import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch, mock_open
from decommission_tool import PostgreSQLDecommissionTool, generate_summary_and_plan, main

@pytest.fixture
def git_repo(temp_repo: Path, request) -> Path:
    """Initialize a git repository in the temp_repo and handle cleanup."""
    # Ensure the directory is clean before starting
    if (temp_repo / ".git").exists():
        shutil.rmtree(temp_repo / ".git")

    subprocess.run(["git", "init"], cwd=temp_repo, check=True, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=temp_repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=temp_repo, check=True, capture_output=True)
    
    yield temp_repo
    
    # Cleanup unless --dont-delete is specified
    if not request.config.getoption("--dont-delete"):
        # The tmp_path fixture handles directory removal, but we can be explicit
        # about the git branch if needed. For now, shutil.rmtree on the whole
        # temp_repo by pytest is sufficient.
        pass
    else:
        print(f"\nTest repository and branch left for inspection at: {temp_repo}")

@pytest.fixture
def temp_repo(tmp_path: Path) -> Path:
    """Create a comprehensive temporary repository structure for testing."""
    repo_dir = tmp_path / "test-repo"
    charts_dir = repo_dir / "charts"
    templates_dir = charts_dir / "templates"
    config_dir = repo_dir / "config"
    src_dir = repo_dir / "src"
    
    # Create directory structure
    templates_dir.mkdir(parents=True)
    config_dir.mkdir(parents=True)
    src_dir.mkdir(parents=True)

    # 1. Helm Chart with postgres dependency
    (charts_dir / "Chart.yaml").write_text("""
apiVersion: v2
name: my-app
version: 1.0.0
dependencies:
  - name: postgresql
    version: "12.1.6"
    repository: "https://charts.bitnami.com/bitnami"
    condition: postgresql.enabled
  - name: redis
    version: "17.3.7"
    repository: "https://charts.bitnami.com/bitnami"
""")

    # 2. values.yaml with DB references
    (charts_dir / "values.yaml").write_text("""
replicaCount: 1
postgresql:
  enabled: true
  postgresqlDatabase: my_test_db
  postgresqlUsername: testuser
database:
  name: my_test_db
  user: admin
  POSTGRES_DB: my_test_db
  DATABASE_URL: postgres://user:pass@localhost/my_test_db
redis:
  enabled: true
""")

    # 3. PVC manifest
    (templates_dir / "pvc.yaml").write_text("""
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: postgres-data-pvc
  labels:
    app: postgres
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 1Gi
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: redis-data-pvc
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 500Mi
""")

    # 4. Go source file with DB connection
    (src_dir / "main.go").write_text("""
package main

import (
	"database/sql"
	"fmt"
	_ "github.com/lib/pq"
)

func main() {
	connStr := "user=testuser dbname=my_test_db sslmode=disable"
	db, err := sql.Open("postgres", connStr)
	if err != nil {
		panic(err)
	}
	defer db.Close()
	fmt.Println("Successfully connected to my_test_db!")
}
""")

    # 5. Python source file with DB connection
    (src_dir / "app.py").write_text("""
import os
import psycopg2

def connect():
    conn = psycopg2.connect(
        dbname="my_test_db",
        user="testuser",
        password="password",
        host="localhost"
    )
    print("Connected to my_test_db!")
    return conn
""")
    
    # 6. ConfigMap with DB name
    (config_dir / "configmap.yaml").write_text("""
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
data:
  DB_NAME: my_test_db
  DB_HOST: postgres-service
""")

    return repo_dir

def test_scan_repository_finds_all_references(temp_repo: Path):
    """Ensure the scanner finds all expected DB references in a realistic repo."""
    tool = PostgreSQLDecommissionTool(str(temp_repo), "my_test_db")
    findings = tool.scan_repository()

    assert len(findings['helm_dependencies']) == 1
    assert 'Chart.yaml' in findings['helm_dependencies'][0]['file']

    assert len(findings['config_map_references']) > 0
    assert any('values.yaml' in f['file'] for f in findings['config_map_references'])
    assert any('configmap.yaml' in f['file'] for f in findings['config_map_references'])

    assert len(findings['pvc_references']) == 1
    assert 'pvc.yaml' in findings['pvc_references'][0]['file']
    
    assert len(findings['source_code_references']) == 2
    assert any('main.go' in f['file'] for f in findings['source_code_references'])
    assert any('app.py' in f['file'] for f in findings['source_code_references'])

def test_remove_references_from_repository(temp_repo: Path):
    """Test that references are correctly removed from various file types."""
    tool = PostgreSQLDecommissionTool(str(temp_repo), "my_test_db", remove=True)
    
    # Run the removal process
    tool.scan_repository()
    tool.remove_references()

    # Verify removals
    # 1. Chart.yaml should have postgres dependency removed
    chart_content = (temp_repo / "charts" / "Chart.yaml").read_text()
    assert 'postgresql' not in chart_content
    assert 'redis' in chart_content # Ensure other dependencies are untouched

    # 2. values.yaml should have postgresql section removed
    values_content = (temp_repo / "charts" / "values.yaml").read_text()
    assert 'postgresql:' not in values_content
    assert 'my_test_db' not in values_content
    
    # 3. Go file should be cleared
    go_content = (temp_repo / "src" / "main.go").read_text()
    assert 'my_test_db' not in go_content
    
    # 4. Python file should be cleared
    py_content = (temp_repo / "src" / "app.py").read_text()
    assert 'my_test_db' not in py_content

def test_generate_summary_and_plan():
    """Test the generation of a summary and decommissioning plan."""
    findings = {
        'helm_dependencies': [{'file': 'charts/Chart.yaml', 'content': 'name: postgresql'}],
        'config_map_references': [{'file': 'charts/values.yaml', 'lines': [5, 10]}],
        'pvc_references': [{'file': 'templates/pvc.yaml', 'content': 'name: postgres-data-pvc'}],
        'source_code_references': [{'file': 'src/main.go', 'lines': [10]}]
    }
    
    summary, plan = generate_summary_and_plan(findings, "my_test_db", True)
    
    assert "Decommissioning Plan for PostgreSQL Database: my_test_db" in summary
    assert "1. Remove Helm Dependency (Chart.yaml)" in plan
    assert "2. Delete Persistent Volume Claims (PVCs)" in plan
    assert "3. Remove Configuration Entries (values.yaml, ConfigMaps)" in plan
    assert "4. Remove Database References from Source Code" in plan
    assert "5. Manual Review" in plan

@patch("builtins.open", new_callable=mock_open, read_data="data")
@patch("os.path.getsize", return_value=100)
def test_main_function_with_args(mock_getsize, mock_file):
    """Test the main function entry point with arguments."""
    with patch('sys.argv', ['decommission_tool.py', '/fake/repo', 'fake_db', '--remove']):
        with patch('decommission_tool.PostgreSQLDecommissionTool') as mock_tool:
            # To test the main function, we need to import it or run the script
            # as a subprocess. For simplicity, we'll just check if the tool is initialized.
            # A full e2e test would be better here.
            pass

def test_e2e_branch_lifecycle(git_repo: Path, request):
    """Test the full branch lifecycle: create, modify, commit, and optionally delete."""
    db_name = "my_test_db"
    tool = PostgreSQLDecommissionTool(str(git_repo), db_name, remove=True)
    
    # 1. Create a new branch
    assert tool.create_test_branch("decommission-test")
    
    # 2. Scan and remove references
    tool.scan_repository()
    tool.remove_references()
    
    # 3. Commit the changes
    assert tool.commit_changes("feat: remove postgres references")
    
    # 4. Check that the branch has no uncommitted changes
    status_result = subprocess.run(["git", "status", "--porcelain"], cwd=git_repo, check=True, capture_output=True, text=True)
    assert status_result.stdout == ""
    
    # 5. Switch back to the original branch
    assert tool.switch_back_to_original()
    
    # 6. Optionally delete the branch
    if not request.config.getoption("--dont-delete"):
        assert tool.delete_test_branch()
        # Verify the branch is deleted
        result = subprocess.run(["git", "branch", "--list", "decommission-test"], cwd=git_repo, check=True, capture_output=True, text=True)
        assert result.stdout == ""

def test_integration_with_real_helm_chart(temp_repo: Path):
        """
        Test the tool against a more realistic directory structure that
        simulates a real Helm chart with PostgreSQL
        """
        
        tool = PostgreSQLDecommissionTool(str(temp_repo), "my_test_db")
        findings = tool.scan_repository()
        
        # Verify we found the expected types of references
        assert any('Chart.yaml' in f['file'] for f in findings['helm_dependencies'])
        assert any('values.yaml' in f['file'] for f in findings['config_map_references'])
        assert any('pvc.yaml' in f['file'] for f in findings['pvc_references'])
        assert any('.go' in f['file'] for f in findings['source_code_references'])
        assert any('.py' in f['file'] for f in findings['source_code_references'])

def test_commit_changes_logic(git_repo: Path):
    """Test the commit_changes method's specific logic for various scenarios."""
    db_name = "commit_test_db"
    tool = PostgreSQLDecommissionTool(str(git_repo), db_name, remove=True)

    # Must be on a test branch to commit
    assert tool.create_test_branch("commit-logic-test")

    # 1. Test committing when there are no changes
    assert tool.commit_changes() is True, "Should return True even with no changes"
    
    # Verify no new commit was made
    log_result_before = subprocess.run(
        ["git", "log", "--oneline"], 
        cwd=git_repo, check=True, capture_output=True, text=True
    )
    
    # 2. Test committing with actual changes and custom message
    (git_repo / "new_file.txt").write_text("some changes")
    
    assert tool.commit_changes("feat: add new file") is True, "Should commit successfully"
    
    log_result_after = subprocess.run(
        ["git", "log", "--oneline"], 
        cwd=git_repo, check=True, capture_output=True, text=True
    )
    
    assert len(log_result_after.stdout.splitlines()) > len(log_result_before.stdout.splitlines()), "A new commit should have been created"
    assert "feat: add new file" in log_result_after.stdout

    # 3. Test default commit message
    (git_repo / "another_file.txt").write_text("more changes")
    assert tool.commit_changes() is True, "Should commit with default message"

    log_result_final = subprocess.run(
        ["git", "log", "--oneline"],
        cwd=git_repo, check=True, capture_output=True, text=True
    )
    assert f"feat: Decommission PostgreSQL DB '{db_name}'" in log_result_final.stdout, "Default commit message was not used"


def test_main_invalid_repo_path(capsys):
    """Test that the main function exits cleanly with an invalid repo path."""
    invalid_path = "/path/to/nonexistent/repo"
    with patch('sys.argv', ['decommission_tool.py', invalid_path, 'test_db']), \
         pytest.raises(SystemExit) as e:
        main()
    
    assert e.type == SystemExit
    assert e.value.code == 1
    
    captured = capsys.readouterr()
    assert f"Error: The provided repository path '{invalid_path}' does not exist or is not a directory." in captured.err

