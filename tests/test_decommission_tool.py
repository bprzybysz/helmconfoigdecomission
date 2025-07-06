import pytest
import tempfile
import json
import shutil
import subprocess
import logging
import sys
from pathlib import Path
from unittest.mock import patch, mock_open

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from decommission_tool import PostgreSQLDecommissionTool, HelmDecommissionTool, main
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
      storage: 1Gi
""")
    (charts_dir / "values.yaml").write_text("""
replicaCount: 1
image:
  repository: nginx
  tag: stable
service:
  type: ClusterIP
  port: 80
postgres:
  enabled: true
  databaseName: my-test-db
  username: admin
""")
    (config_dir / "database.yml").write_text("""
development:
  adapter: postgresql
  encoding: unicode
  database: my-test-db
  pool: 5
  username: admin
  password: password
""")
    (src_dir / "main.go").write_text("""
package main

import (
	"fmt"
)

func main() {
	fmt.Println("Connecting to database: my-test-db")
}
""")
    (repo_dir / "README.md").write_text("""
# My Test Repo

This repository contains references to `my-test-db`.
""")
    return repo_dir

@pytest.fixture
def repo_with_references(git_repo: Path) -> Path:
    """Fixture that provides a git repository with pre-defined references to 'my-test-db'."""
    return git_repo

class TestPostgreSQLDecommissionTool:
    def test_scan_file(self, temp_repo):
        tool = PostgreSQLDecommissionTool(str(temp_repo), "my-test-db")
        file_path = temp_repo / "config" / "database.yml"
        findings = tool.scan_file(file_path)
        
        # Verify we found at least one match
        assert len(findings) > 0
        
        # Verify the first match is on line 5 and contains the database name
        assert findings[0][0] == 5  # Line number
        assert "database: my-test-db" in findings[0][1]
        
        # Verify all findings contain the database name
        for line_num, line_content in findings:
            assert "my-test-db" in line_content.lower()

    def test_scan_repository(self, repo_with_references):
        tool = PostgreSQLDecommissionTool(str(repo_with_references), "my-test-db")
        tool.scan_repository()
        assert len(tool.findings) == 5 # database.yml, main.go, values.yaml, README.md, Chart.yaml
        assert "config/database.yml" in tool.findings
        assert "src/main.go" in tool.findings
        assert "charts/values.yaml" in tool.findings
        assert "charts/Chart.yaml" in tool.findings
        assert "README.md" in tool.findings

    def test_remove_references_dry_run(self, repo_with_references):
        tool = PostgreSQLDecommissionTool(str(repo_with_references), "my-test-db", remove=True, dry_run=True)
        tool.run()
        # Verify files still contain references in dry run
        assert "my-test-db" in (repo_with_references / "config" / "database.yml").read_text()

    def test_remove_references_actual(self, repo_with_references):
        tool = PostgreSQLDecommissionTool(str(repo_with_references), "my-test-db", remove=True, dry_run=False)
        tool.run()
        # Verify files no longer contain references
        assert "my-test-db" not in (repo_with_references / "config" / "database.yml").read_text()
        assert "my-test-db" not in (repo_with_references / "src" / "main.go").read_text()
        assert "my-test-db" not in (repo_with_references / "charts" / "values.yaml").read_text()
        assert "my-test-db" not in (repo_with_references / "README.md").read_text()

    def test_generate_report(self, repo_with_references):
        tool = PostgreSQLDecommissionTool(str(repo_with_references), "my-test-db")
        tool.scan_repository()
        report = tool.generate_report()
        assert report["database_name"] == "my-test-db"
        assert report["dry_run"] == False
        assert report["remove_mode"] == False
        assert "config/database.yml" in report["findings"]

class TestHelmDecommissionTool:
    def test_scan_helm_charts(self, repo_with_references):
        tool = HelmDecommissionTool(str(repo_with_references), "my-test-db", "my-release")
        tool.scan_helm_charts()
        assert "my-app" in tool.helm_findings
        assert "charts/values.yaml" in tool.helm_findings["my-app"]

    def test_generate_helm_commands(self, repo_with_references):
        tool = HelmDecommissionTool(str(repo_with_references), "my-test-db", "my-release")
        tool.scan_helm_charts()
        commands = tool.generate_helm_commands()
        assert len(commands) == 2
        assert "helm uninstall my-release" in commands
        assert "helm delete my-release --purge" in commands

    def test_helm_tool_run(self, repo_with_references):
        tool = HelmDecommissionTool(str(repo_with_references), "my-test-db", "my-release", remove=True, dry_run=False)
        report = tool.run()
        assert report["database_name"] == "my-test-db"
        assert report["helm_release_name"] == "my-release"
        assert "my-app" in report["helm_chart_findings"]
        assert "helm uninstall my-release" in report["helm_decommission_commands"]
        # Verify files no longer contain references after Helm tool run
        assert "my-test-db" not in (repo_with_references / "config" / "database.yml").read_text()
        assert "my-test-db" not in (repo_with_references / "src" / "main.go").read_text()
        assert "my-test-db" not in (repo_with_references / "charts" / "values.yaml").read_text()
        assert "my-test-db" not in (repo_with_references / "README.md").read_text()

class TestMainFunction:
    def test_main_no_remove_no_dry_run(self, repo_with_references):
        """Test that running the tool without --remove or --dry-run doesn't modify files."""
        db_name = "my-test-db"
        git_repo = str(repo_with_references)
        
        # Get the original content of a file we know contains the database name
        db_file = Path(git_repo) / "config" / "database.yml"
        original_content = db_file.read_text()
        
        # Run the main function
        with patch('sys.argv', ['decommission_tool.py', git_repo, db_name]):
            main()
        
        # Verify the file wasn't modified
        assert db_file.read_text() == original_content, \
            "File was modified when it shouldn't have been"
            
        # Verify the database name is still in the file
        assert db_name in db_file.read_text(), \
            f"Database name '{db_name}' was removed from the file"

    def test_main_remove_with_dry_run(self, repo_with_references, capsys):
        db_name = "my-test-db"
        git_repo = str(repo_with_references)
        
        # Verify the file wasn't modified (as it's a dry run)
        db_file = Path(git_repo) / "config" / "database.yml"
        original_content = db_file.read_text()
        
        with patch('sys.argv', ['decommission_tool.py', git_repo, db_name, '--dry-run', '--remove']):
            main()
        
        assert db_file.read_text() == original_content, \
            "File was modified during a dry run when it shouldn't have been"
        assert "my-test-db" in (Path(git_repo) / "config" / "database.yml").read_text()

    def test_main_remove_actual_confirmed(self, repo_with_references, capsys):
        db_name = "my-test-db"
        git_repo = str(repo_with_references)
        
        # Clear any existing log handlers to prevent interference
        logging.getLogger().handlers = []

        # Get the original content of a file we know contains the database name
        db_file = Path(git_repo) / "config" / "database.yml"
        original_content = db_file.read_text()

        with patch('sys.argv', ['decommission_tool.py', git_repo, db_name, '--remove']):
            with patch('builtins.input', return_value='yes'):
                main()
        captured = capsys.readouterr()
        
        # Assert that the database name is no longer in the file
        assert db_name not in db_file.read_text(), \
            f"Database name '{db_name}' was not removed from the file"

        # Assert that the expected message is in the output
        assert "References have been removed from files" in captured.out, \
            f"Expected message not found in stdout: {captured.out}"

    def test_main_remove_actual_cancelled(self, repo_with_references, capsys):
        db_name = "my-test-db"
        git_repo = str(repo_with_references)

        # Clear any existing log handlers to prevent interference
        logging.getLogger().handlers = []

        # Get the original content of a file
        db_file = Path(git_repo) / "config" / "database.yml"
        original_content = db_file.read_text()

        with patch('sys.argv', ['decommission_tool.py', git_repo, db_name, '--remove']):
            with patch('builtins.input', return_value='no'):
                with pytest.raises(SystemExit) as excinfo:
                    main()

        # Assert that the program exited with code 0 (success/cancellation)
        assert excinfo.value.code == 0

        captured = capsys.readouterr()

        # Assert that the file content remains unchanged
        assert db_file.read_text() == original_content, \
            "File was modified despite user cancellation"

        # Assert that the cancellation message is in the output
        assert "Operation cancelled by user." in captured.out, \
            f"Expected cancellation message not found in stdout: {captured.out}"

    def test_main_helm_decommission(self, repo_with_references, capsys):
        db_name = "my-test-db"
        release_name = "my-release"
        git_repo = str(repo_with_references)

        # Clear any existing log handlers to prevent interference
        logging.getLogger().handlers = []

        with patch('sys.argv', ['decommission_tool.py', git_repo, db_name, '--release-name', release_name, '--remove', '--dry-run']):
            main()
        captured = capsys.readouterr()
        assert "Suggested Helm Decommissioning Commands:" in captured.out
        assert "helm uninstall my-release --namespace charts" in captured.out
        assert "helm delete my-release --purge" in captured.out
        assert "This was a dry run. No changes were made to files." in captured.out
        assert "my-test-db" in (Path(git_repo) / "config" / "database.yml").read_text()

    def test_main_invalid_repo_path(self, caplog):
        invalid_path = "/path/to/nonexistent/repo"
        
        with patch('sys.argv', ['decommission_tool.py', invalid_path, 'test_db']):
            # main() calls sys.exit(1) on invalid path, so we catch SystemExit
            with pytest.raises(SystemExit) as pytest_wrapped_e:
                main()
            assert pytest_wrapped_e.type == SystemExit
            assert pytest_wrapped_e.value.code == 1
        
        # Assert that the error message is in the captured logs
        assert f"Error: The provided repository path '{invalid_path}' does not exist or is not a directory." in caplog.text

    def test_dry_run_does_not_modify_files(self, repo_with_references, capsys):
        db_name = "my-test-db"
        git_repo = str(repo_with_references)
        original_content = (Path(git_repo) / "charts/values.yaml").read_text()

        with patch('sys.argv', ['decommission_tool.py', git_repo, db_name, '--remove', '--dry-run']):
            main()
        
        # Verify the file content is unchanged
        assert (Path(git_repo) / "charts/values.yaml").read_text() == original_content

        # Verify no new branch was created
        result = subprocess.run(["git", "branch"], cwd=git_repo, capture_output=True, text=True)
        assert f"chore/{db_name}-decommission" not in result.stdout
