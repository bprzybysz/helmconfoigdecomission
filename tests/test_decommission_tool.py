import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch, mock_open
from decommission_tool import PostgreSQLDecommissionTool, generate_summary_and_plan

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

    assert len(findings['config_references']) > 0
    assert any('values.yaml' in f['file'] for f in findings['config_references'])
    assert any('configmap.yaml' in f['file'] for f in findings['config_references'])

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
        'config_references': [{'file': 'charts/values.yaml', 'lines': [5, 10]}],
        'pvc_references': [{'file': 'templates/pvc.yaml', 'content': 'name: postgres-data-pvc'}],
        'source_code_references': [{'file': 'src/main.go', 'lines': [10]}]
    }
    
    summary, plan = generate_summary_and_plan(findings, "my_test_db", True)
    
    assert "Decommissioning Plan for PostgreSQL Database: my_test_db" in summary
    assert "1. Remove Helm Dependency" in plan
    assert "2. Remove Configuration Entries" in plan
    assert "3. Delete Persistent Volume Claims (PVCs)" in plan
    assert "4. Remove Database References from Source Code" in plan
    assert "5. Manual Review" in plan

@patch("builtins.open", new_callable=mock_open, read_data="data")
@patch("os.path.getsize", return_value=100)
def test_main_function_with_args(mock_getsize, mock_file):
    """Test the main function entry point with arguments."""
    with patch('sys.argv', ['decommission_tool.py', '/fake/repo', 'fake_db', '--remove']):
        with patch('decommission_tool.PostgreSQLDecommissionTool') as mock_tool:
            # To test the main function, we need to import it or run the script
            # This is a placeholder for how you might structure this test
            pass

def test_integration_with_real_helm_chart(temp_repo: Path):
        """
        Test the tool against a more realistic directory structure that
        simulates a real Helm chart with PostgreSQL
        """
        
        tool = PostgreSQLDecommissionTool(str(temp_repo), "my_test_db")
        findings = tool.scan_repository()
        
        # Verify we found the expected types of references
        assert any('Chart.yaml' in f['file'] for f in findings['helm_dependencies'])
        assert any('values.yaml' in f['file'] for f in findings['config_references'])
        assert any('pvc.yaml' in f['file'] for f in findings['pvc_references'])
        assert any('.go' in f['file'] for f in findings['source_code_references'])
        assert any('.py' in f['file'] for f in findings['source_code_references'])
