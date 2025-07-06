import pytest
import tempfile
import json
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch, mock_open

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from decommission_tool import PostgreSQLDecommissionTool, generate_summary_and_plan, main
from git_utils import GitRepository

@pytest.fixture
def git_repo(temp_repo: Path, request) -> Path:
    """Initialize a git repository in the temp_repo and handle cleanup."""
    if (temp_repo / ".git").exists():
        shutil.rmtree(temp_repo / ".git")

    subprocess.run(["git", "init"], cwd=temp_repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=temp_repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=temp_repo, check=True)
    subprocess.run(["git", "add", "."], cwd=temp_repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=temp_repo, check=True, capture_output=True)
    
    yield temp_repo
    
    if request.config.getoption("--dont-delete"):
        print(f"\nTest repository and branch left for inspection at: {temp_repo}")

@pytest.fixture
def temp_repo(tmp_path: Path) -> Path:
    """Create a comprehensive temporary repository structure for testing."""
    repo_dir = tmp_path / "test-repo"
    charts_dir = repo_dir / "charts"
    templates_dir = charts_dir / "templates"
    config_dir = repo_dir / "config"
    src_dir = repo_dir / "src"
    
    templates_dir.mkdir(parents=True)
    config_dir.mkdir(parents=True)
    src_dir.mkdir(parents=True)

    (charts_dir / "Chart.yaml").write_text("""
apiVersion: v2
name: my-app
version: 1.0.0
dependencies:
  - name: postgresql
    version: "12.1.6"
    repository: "https://charts.bitnami.com/bitnami"
""")
    (templates_dir / "my-pvc.yaml").write_text("""
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: my-postgres-pvc
spec:
  accessModes: ["ReadWriteOnce"]
  resources:
    requests:
      storage: 8Gi
""")
    (config_dir / "my-config.yaml").write_text("""
apiVersion: v1
kind: ConfigMap
metadata:
  name: my-app-config
data:
  DATABASE_URL: "postgres://user:pass@my-test-db:5432/mydb"
""")
    (src_dir / "main.py").write_text("""
import os
def get_db_url():
    return os.environ.get("DATABASE_URL", "postgres://default:default@my-test-db:5432/default")
print(get_db_url())
""")
    (repo_dir / "README.md").write_text("This is a test repo.")
    
    return repo_dir

def test_tool_initialization(temp_repo: Path):
    tool = PostgreSQLDecommissionTool(str(temp_repo), "test_db")
    assert tool.repo_path == temp_repo
    assert tool.db_name == "test_db"
    assert tool.remove is False

def test_is_excluded(temp_repo: Path):
    tool = PostgreSQLDecommissionTool(str(temp_repo), "test_db")
    assert tool._is_excluded(temp_repo / ".git" / "config") is True
    assert tool._is_excluded(temp_repo / "node_modules" / "some-lib") is True
    assert tool._is_excluded(temp_repo / "src" / "main.py") is False

def test_scan_repository(git_repo: Path):
    db_name = "my-test-db"
    tool = PostgreSQLDecommissionTool(str(git_repo), db_name)
    findings = tool.scan_repository()
    assert findings['total_scanned'] > 0
    assert findings['total_found'] > 0
    assert len(findings['helm_dependencies']) == 1
    assert len(findings['pvc_references']) == 1
    assert len(findings['config_map_references']) == 1
    assert len(findings['source_code_references']) == 1

def test_remove_references(git_repo: Path):
    db_name = "my-test-db"
    tool = PostgreSQLDecommissionTool(str(git_repo), db_name, remove=True)
    tool.scan_repository()
    tool.remove_references()
    chart_content = (git_repo / "charts" / "Chart.yaml").read_text()
    assert "postgresql" not in chart_content
    assert not (git_repo / "templates" / "my-pvc.yaml").exists()
    config_content = (git_repo / "config" / "my-config.yaml").read_text()
    assert db_name not in config_content
    source_content = (git_repo / "src" / "main.py").read_text()
    assert db_name not in source_content

def test_generate_summary_and_plan():
    findings = {
        'helm_dependencies': [{'file': 'charts/Chart.yaml'}],
        'pvc_references': [{'file': 'templates/pvc.yaml'}],
        'config_map_references': [],
        'source_code_references': [{'file': 'src/main.py'}],
    }
    summary, plan = generate_summary_and_plan(findings, "test_db", False)
    assert "Helm Dependencies: 1 found" in summary
    assert "PVC References: 1 found" in summary
    assert "Source Code References: 1 found" in summary
    assert "1. Remove Helm Dependency" in plan

def test_e2e_branch_lifecycle(git_repo: Path, request):
    db_name = "my_test_db"
    git_util = GitRepository(str(git_repo))
    tool = PostgreSQLDecommissionTool(str(git_repo), db_name, remove=True)

    assert git_util.create_test_branch("decommission-test")
    tool.run()
    diff = git_util.show_diff()
    assert "postgresql" in diff
    assert git_util.commit_changes("feat: remove db references")
    original_branch = git_util.original_branch
    assert git_util.revert_to_original_branch()
    assert git_util.get_current_branch() == original_branch
    if not request.config.getoption("--dont-delete"):
        assert git_util.delete_test_branch()
        result = subprocess.run(["git", "branch", "--list", git_util.test_branch], cwd=git_repo, capture_output=True, text=True)
        assert git_util.test_branch not in result.stdout

def test_commit_changes_logic(git_repo: Path):
    git_util = GitRepository(str(git_repo))
    assert git_util.create_test_branch("commit-logic-test")
    assert git_util.commit_changes("no changes commit") is True
    log_result_before = subprocess.run(["git", "log", "--oneline"], cwd=git_repo, check=True, capture_output=True, text=True)
    (git_repo / "new_file.txt").write_text("some changes")
    assert git_util.commit_changes("feat: add new file") is True
    log_result_after = subprocess.run(["git", "log", "--oneline"], cwd=git_repo, check=True, capture_output=True, text=True)
    assert len(log_result_after.stdout.splitlines()) > len(log_result_before.stdout.splitlines())
    assert "feat: add new file" in log_result_after.stdout

def test_main_invalid_repo_path(capsys):
    invalid_path = "/path/to/nonexistent/repo"
    with patch('sys.argv', ['decommission_tool.py', invalid_path, 'test_db']), pytest.raises(SystemExit) as e:
        main()
    assert e.type == SystemExit
    assert e.value.code == 1
    captured = capsys.readouterr()
    assert f"Error: The provided repository path '{invalid_path}' does not exist or is not a directory." in captured.err
