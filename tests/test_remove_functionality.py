import pytest
import tempfile
import yaml
from pathlib import Path
from decommission_tool import PostgreSQLDecommissionTool, generate_summary_and_plan

@pytest.fixture
def temp_repo_with_postgres(tmp_path: Path) -> Path:
    """Create a repository with PostgreSQL references for removal testing."""
    repo_dir = tmp_path / "test-repo"
    charts_dir = repo_dir / "charts"
    templates_dir = charts_dir / "templates"
    src_dir = repo_dir / "src"
    
    # Create directory structure
    templates_dir.mkdir(parents=True)
    src_dir.mkdir(parents=True)

    # Chart.yaml with PostgreSQL dependency
    (charts_dir / "Chart.yaml").write_text("""
apiVersion: v2
name: my-app
dependencies:
  - name: postgresql
    version: "12.1.6"
    repository: "https://charts.bitnami.com/bitnami"
  - name: redis
    version: "17.3.7"
    repository: "https://charts.bitnami.com/bitnami"
""")

    # values.yaml with PostgreSQL config
    (charts_dir / "values.yaml").write_text("""
replicaCount: 1
postgresql:
  enabled: true
  postgresqlDatabase: my_test_db
  postgresqlUsername: testuser
redis:
  enabled: true
database:
  name: my_test_db
  host: postgres-service
""")

    # Source code with DB references
    (src_dir / "main.go").write_text("""
package main

const dbName = "my_test_db"
const redisHost = "redis-service"

func main() {
    // Connect to my_test_db
    db := connectDB("my_test_db")
}
""")

    (src_dir / "config.py").write_text("""
DATABASE_NAME = "my_test_db"
REDIS_URL = "redis://localhost:6379"

def get_db_connection():
    return connect_to_db("my_test_db")
""")

    # PVC file
    (templates_dir / "pvc.yaml").write_text("""
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: postgresql-pvc
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 1Gi
""")

    return repo_dir

def test_remove_postgres_references(temp_repo_with_postgres):
    """Test that PostgreSQL references are correctly removed from all files."""
    tool = PostgreSQLDecommissionTool(str(temp_repo_with_postgres), "my_test_db", remove=True)
    tool.run()

    # Verify Chart.yaml is updated
    chart_path = temp_repo_with_postgres / "charts" / "Chart.yaml"
    with chart_path.open() as f:
        chart_data = yaml.safe_load(f)
    assert not any(dep["name"] == "postgresql" for dep in chart_data["dependencies"])
    assert any(dep["name"] == "redis" for dep in chart_data["dependencies"])

    # Verify values.yaml is updated
    values_path = temp_repo_with_postgres / "charts" / "values.yaml"
    with values_path.open() as f:
        values_data = yaml.safe_load(f)
    assert "postgresql" not in values_data
    assert "redis" in values_data

    # Verify source code is updated
    main_go_path = temp_repo_with_postgres / "src" / "main.go"
    main_go_content = main_go_path.read_text()
    assert 'const dbName = "my_test_db"' not in main_go_content
    assert 'connectDB("my_test_db")' not in main_go_content

    config_py_path = temp_repo_with_postgres / "src" / "config.py"
    config_py_content = config_py_path.read_text()
    assert 'DATABASE_NAME = "my_test_db"' not in config_py_content
    assert 'connect_to_db("my_test_db")' not in config_py_content

    # Verify PVC is deleted
    pvc_path = temp_repo_with_postgres / "charts" / "templates" / "pvc.yaml"
    assert not pvc_path.exists()
