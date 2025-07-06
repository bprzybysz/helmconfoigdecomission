Based on your updated codebase in the attachments, here are comprehensive unit tests for your `decommission_tool.py`:

## **Enhanced Unit Tests for Updated Codebase**

### **tests/test_decommission_tool.py**

```python
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

    # 4. Template with PostgreSQL resources
    (templates_dir / "postgres-deployment.yaml").write_text("""
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: postgres-primary
spec:
  serviceName: postgres
  replicas: 1
  template:
    spec:
      containers:
      - name: postgres
        image: postgres:13
        env:
        - name: POSTGRES_DB
          value: my_test_db
""")

    # 5. Config files
    (config_dir / "database.conf").write_text("""
# Database configuration
POSTGRES_DB=my_test_db
POSTGRES_USER=testuser
PGPASSWORD=secret123
""")

    (config_dir / "app.env").write_text("""
DATABASE_URL=postgres://user:pass@postgres:5432/my_test_db
REDIS_URL=redis://redis:6379
""")

    # 6. Source code files with DSN
    (src_dir / "main.go").write_text('''
package main

const dsn = "postgres://user:pass@host/my_test_db"
const redisDSN = "redis://localhost:6379"
''')

    (src_dir / "config.py").write_text('''
DATABASE_URL = "postgresql://user:pass@localhost:5432/my_test_db"
REDIS_URL = "redis://localhost:6379"
''')

    # 7. Large file (should be excluded)
    large_content = "x" * (11 * 1024 * 1024)  # 11MB
    (repo_dir / "large_file.yaml").write_text(large_content)

    # 8. Files in excluded directories
    excluded_dir = repo_dir / "node_modules"
    excluded_dir.mkdir()
    (excluded_dir / "package.yaml").write_text("postgres: test")

    return repo_dir

class TestPostgreSQLDecommissionTool:
    """Test suite for PostgreSQLDecommissionTool"""

    def test_initialization(self, temp_repo):
        """Test tool initialization with valid parameters"""
        tool = PostgreSQLDecommissionTool(str(temp_repo), "my_test_db")
        assert tool.repo_path == Path(temp_repo)
        assert tool.db_name == "my_test_db"
        assert tool.max_findings == 100
        assert 'yaml_extensions' in tool.constraints

    def test_initialization_invalid_path(self):
        """Test tool initialization with invalid repository path"""
        with pytest.raises(FileNotFoundError):
            tool = PostgreSQLDecommissionTool("/nonexistent/path", "test_db")
            tool.scan_repository()

    def test_scan_helm_dependencies(self, temp_repo):
        """Test scanning for Helm dependencies"""
        tool = PostgreSQLDecommissionTool(str(temp_repo), "postgresql")
        findings = tool.scan_repository()
        
        helm_deps = findings['helm_dependencies']
        assert len(helm_deps) == 1
        assert helm_deps[0]['severity'] == 'high'
        assert 'Chart.yaml' in helm_deps[0]['file']
        assert helm_deps[0]['content']['name'] == 'postgresql'

    def test_scan_config_references(self, temp_repo):
        """Test scanning for configuration references"""
        tool = PostgreSQLDecommissionTool(str(temp_repo), "my_test_db")
        findings = tool.scan_repository()
        
        config_refs = findings['config_references']
        assert len(config_refs) >= 3  # Should find multiple references
        
        # Check that we found references in different file types
        file_types = {ref['file'].split('.')[-1] for ref in config_refs}
        assert 'yaml' in file_types  # values.yaml
        assert 'conf' in file_types  # database.conf
        assert 'env' in file_types   # app.env

    def test_scan_pvc_references(self, temp_repo):
        """Test scanning for PVC references"""
        tool = PostgreSQLDecommissionTool(str(temp_repo), "any_db")
        findings = tool.scan_repository()
        
        pvc_refs = findings['pvc_references']
        assert len(pvc_refs) == 1  # Only postgres PVC should match
        assert pvc_refs[0]['severity'] == 'critical'
        assert 'postgres-data-pvc' in pvc_refs[0]['content']

    def test_scan_template_resources(self, temp_repo):
        """Test scanning for template resources"""
        tool = PostgreSQLDecommissionTool(str(temp_repo), "my_test_db")
        findings = tool.scan_repository()
        
        template_refs = findings['template_resources']
        assert len(template_refs) >= 1
        
        # Should find the postgres deployment
        postgres_template = next((t for t in template_refs if 'postgres-deployment' in t['file']), None)
        assert postgres_template is not None
        assert postgres_template['severity'] == 'high'

    def test_scan_source_code_references(self, temp_repo):
        """Test scanning for source code DSN references"""
        tool = PostgreSQLDecommissionTool(str(temp_repo), "my_test_db")
        findings = tool.scan_repository()
        
        source_refs = findings['source_code_references']
        assert len(source_refs) >= 2  # Should find references in .go and .py files
        
        # Check file types
        file_extensions = {ref['file'].split('.')[-1] for ref in source_refs}
        assert 'go' in file_extensions
        assert 'py' in file_extensions

    def test_file_constraints_size_limit(self, temp_repo):
        """Test that large files are excluded"""
        tool = PostgreSQLDecommissionTool(str(temp_repo), "test_db")
        findings = tool.scan_repository()
        
        # Large file should not appear in any findings
        all_files = []
        for category in findings.values():
            all_files.extend([f['file'] for f in category])
        
        assert not any('large_file.yaml' in f for f in all_files)

    def test_file_constraints_excluded_directories(self, temp_repo):
        """Test that excluded directories are ignored"""
        tool = PostgreSQLDecommissionTool(str(temp_repo), "postgres")
        findings = tool.scan_repository()
        
        # Files in node_modules should not appear
        all_files = []
        for category in findings.values():
            all_files.extend([f['file'] for f in category])
        
        assert not any('node_modules' in f for f in all_files)

    def test_max_findings_constraint(self, temp_repo):
        """Test that max findings constraint is applied"""
        tool = PostgreSQLDecommissionTool(str(temp_repo), "my_test_db", max_findings=2)
        findings = tool.scan_repository()
        
        # Each category should have at most 2 findings
        for category, refs in findings.items():
            assert len(refs) <= 2

    def test_severity_assignment(self, temp_repo):
        """Test that severity levels are correctly assigned"""
        tool = PostgreSQLDecommissionTool(str(temp_repo), "my_test_db")
        findings = tool.scan_repository()
        
        # Check severity levels
        assert all(f['severity'] == 'critical' for f in findings['pvc_references'])
        assert all(f['severity'] == 'high' for f in findings['helm_dependencies'])
        assert all(f['severity'] == 'high' for f in findings['template_resources'])
        assert all(f['severity'] == 'high' for f in findings['source_code_references'])
        assert all(f['severity'] == 'medium' for f in findings['config_references'])

    def test_relative_file_paths(self, temp_repo):
        """Test that file paths are relative to repository root"""
        tool = PostgreSQLDecommissionTool(str(temp_repo), "my_test_db")
        findings = tool.scan_repository()
        
        all_files = []
        for category in findings.values():
            all_files.extend([f['file'] for f in category])
        
        # All paths should be relative (not start with /)
        assert all(not f.startswith('/') for f in all_files)
        # All paths should be relative to repo root
        assert all(not f.startswith(str(temp_repo)) for f in all_files)

    def test_yaml_error_handling(self, temp_repo):
        """Test handling of invalid YAML files"""
        # Create invalid YAML file
        invalid_yaml = temp_repo / "invalid.yaml"
        invalid_yaml.write_text("invalid: yaml: content: [")
        
        tool = PostgreSQLDecommissionTool(str(temp_repo), "test_db")
        # Should not raise exception, should handle gracefully
        findings = tool.scan_repository()
        assert isinstance(findings, dict)

    def test_empty_yaml_handling(self, temp_repo):
        """Test handling of empty YAML files"""
        empty_yaml = temp_repo / "empty.yaml"
        empty_yaml.write_text("")
        
        tool = PostgreSQLDecommissionTool(str(temp_repo), "test_db")
        findings = tool.scan_repository()
        assert isinstance(findings, dict)

    def test_multiple_yaml_documents(self, temp_repo):
        """Test handling of YAML files with multiple documents"""
        multi_doc = temp_repo / "multi-doc.yaml"
        multi_doc.write_text("""
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: postgres-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: postgres-service
""")
        
        tool = PostgreSQLDecommissionTool(str(temp_repo), "postgres")
        findings = tool.scan_repository()
        
        # Should find the PVC in the multi-document file
        pvc_files = [f['file'] for f in findings['pvc_references']]
        assert any('multi-doc.yaml' in f for f in pvc_files)

class TestGenerateSummaryAndPlan:
    """Test suite for generate_summary_and_plan function"""

    def test_summary_generation(self, temp_repo, capsys):
        """Test summary generation with various findings"""
        tool = PostgreSQLDecommissionTool(str(temp_repo), "my_test_db")
        findings = tool.scan_repository()
        
        summary = generate_summary_and_plan(findings, str(temp_repo))
        
        # Check summary structure
        assert 'total_references' in summary
        assert 'severity_breakdown' in summary
        assert 'files_affected' in summary
        
        # Check that totals make sense
        assert summary['total_references'] > 0
        assert summary['files_affected'] > 0
        
        # Check output was printed
        captured = capsys.readouterr()
        assert "PostgreSQL Decommissioning Plan" in captured.out
        assert "Total References Found" in captured.out

    def test_severity_breakdown(self, temp_repo):
        """Test severity breakdown calculation"""
        tool = PostgreSQLDecommissionTool(str(temp_repo), "my_test_db")
        findings = tool.scan_repository()
        
        summary = generate_summary_and_plan(findings, str(temp_repo))
        severity_breakdown = summary['severity_breakdown']
        
        # Should have critical findings (PVCs)
        assert severity_breakdown['critical'] > 0
        # Should have high findings (Helm deps, templates, source code)
        assert severity_breakdown['high'] > 0
        # Should have medium findings (config refs)
        assert severity_breakdown['medium'] > 0

    def test_empty_findings(self, temp_repo, capsys):
        """Test summary generation with no findings"""
        # Use a database name that won't be found
        tool = PostgreSQLDecommissionTool(str(temp_repo), "nonexistent_db")
        findings = tool.scan_repository()
        
        summary = generate_summary_and_plan(findings, str(temp_repo))
        
        assert summary['total_references'] == 0
        assert summary['files_affected'] == 0
        assert all(count == 0 for count in summary['severity_breakdown'].values())

class TestMainFunction:
    """Test suite for main function"""

    @patch('sys.argv', ['decommission_tool.py', '/test/repo', 'test_db'])
    @patch('decommission_tool.PostgreSQLDecommissionTool')
    def test_main_function_success(self, mock_tool_class):
        """Test main function with valid arguments"""
        from decommission_tool import main
        
        # Mock the tool instance
        mock_tool = mock_tool_class.return_value
        mock_tool.scan_repository.return_value = {
            'helm_dependencies': [],
            'config_references': [],
            'template_resources': [],
            'pvc_references': [],
            'source_code_references': []
        }
        
        # Mock file writing
        with patch('builtins.open', mock_open()):
            with patch('json.dump'):
                with pytest.raises(SystemExit) as exc_info:
                    main()
                
                # Should exit with 0 (no critical findings)
                assert exc_info.value.code == 0

    @patch('sys.argv', ['decommission_tool.py', '/test/repo', 'test_db'])
    @patch('decommission_tool.PostgreSQLDecommissionTool')
    def test_main_function_critical_findings(self, mock_tool_class):
        """Test main function with critical findings"""
        from decommission_tool import main
        
        # Mock the tool instance with critical findings
        mock_tool = mock_tool_class.return_value
        mock_tool.scan_repository.return_value = {
            'helm_dependencies': [],
            'config_references': [],
            'template_resources': [],
            'pvc_references': [{'severity': 'critical'}],
            'source_code_references': []
        }
        
        with patch('builtins.open', mock_open()):
            with patch('json.dump'):
                with patch('decommission_tool.generate_summary_and_plan') as mock_summary:
                    mock_summary.return_value = {
                        'total_references': 1,
                        'severity_breakdown': {'critical': 1, 'high': 0, 'medium': 0, 'low': 0},
                        'files_affected': 1
                    }
                    
                    with pytest.raises(SystemExit) as exc_info:
                        main()
                    
                    # Should exit with 2 (critical findings)
                    assert exc_info.value.code == 2

    @patch('sys.argv', ['decommission_tool.py'])
    def test_main_function_insufficient_args(self):
        """Test main function with insufficient arguments"""
        from decommission_tool import main
        
        with pytest.raises(SystemExit) as exc_info:
            main()
        
        # Should exit with 1 (error)
        assert exc_info.value.code == 1

class TestEdgeCases:
    """Test edge cases and error conditions"""

    def test_binary_file_handling(self, temp_repo):
        """Test that binary files are handled gracefully"""
        # Create a binary file
        binary_file = temp_repo / "binary.png"
        binary_file.write_bytes(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR')
        
        tool = PostgreSQLDecommissionTool(str(temp_repo), "test_db")
        # Should not crash on binary files
        findings = tool.scan_repository()
        assert isinstance(findings, dict)

    def test_unicode_content(self, temp_repo):
        """Test handling of files with unicode content"""
        unicode_file = temp_repo / "unicode.yaml"
        unicode_file.write_text("name: test_db_ñáéíóú", encoding='utf-8')
        
        tool = PostgreSQLDecommissionTool(str(temp_repo), "test_db")
        findings = tool.scan_repository()
        assert isinstance(findings, dict)

    def test_symlink_handling(self, temp_repo):
        """Test handling of symbolic links"""
        if hasattr(temp_repo, 'symlink_to'):  # Python 3.10+
            target = temp_repo / "target.yaml"
            target.write_text("postgres: test")
            
            symlink = temp_repo / "link.yaml"
            try:
                symlink.symlink_to(target)
                
                tool = PostgreSQLDecommissionTool(str(temp_repo), "postgres")
                findings = tool.scan_repository()
                assert isinstance(findings, dict)
            except OSError:
                # Skip if symlinks not supported
                pass

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

### **Additional Test Configuration Files**

#### **tests/conftest.py**

```python
import pytest
import tempfile
from pathlib import Path

@pytest.fixture(scope="session")
def test_data_dir():
    """Provide a directory for test data files"""
    return Path(__file__).parent / "test_data"

@pytest.fixture
def mock_repo_minimal(tmp_path):
    """Create a minimal repository for quick tests"""
    repo_dir = tmp_path / "minimal-repo"
    repo_dir.mkdir()
    
    # Just a simple Chart.yaml
    (repo_dir / "Chart.yaml").write_text("""
apiVersion: v2
name: test-app
dependencies:
  - name: postgresql
    version: "12.1.6"
""")
    
    return repo_dir
```

#### **tests/test_integration.py**

```python
import pytest
import json
from pathlib import Path
from decommission_tool import PostgreSQLDecommissionTool

class TestIntegration:
    """Integration tests for the complete workflow"""

    def test_full_workflow(self, temp_repo):
        """Test the complete scanning workflow"""
        tool = PostgreSQLDecommissionTool(str(temp_repo), "my_test_db")
        
        # Step 1: Scan repository
        findings = tool.scan_repository()
        
        # Step 2: Verify all categories have findings
        assert len(findings['helm_dependencies']) > 0
        assert len(findings['config_references']) > 0
        assert len(findings['template_resources']) > 0
        assert len(findings['pvc_references']) > 0
        assert len(findings['source_code_references']) > 0
        
        # Step 3: Verify JSON serialization works
        json_str = json.dumps(findings)
        parsed_findings = json.loads(json_str)
        assert parsed_findings == findings

    def test_real_world_scenario(self, temp_repo):
        """Test with a realistic PostgreSQL deployment scenario"""
        # This test uses the comprehensive temp_repo fixture
        # which simulates a real Helm chart with PostgreSQL
        
        tool = PostgreSQLDecommissionTool(str(temp_repo), "my_test_db")
        findings = tool.scan_repository()
        
        # Verify we found the expected types of references
        assert any('Chart.yaml' in f['file'] for f in findings['helm_dependencies'])
        assert any('values.yaml' in f['file'] for f in findings['config_references'])
        assert any('pvc.yaml' in f['file'] for f in findings['pvc_references'])
        assert any('.go' in f['file'] for f in findings['source_code_references'])
        assert any('.py' in f['file'] for f in findings['source_code_references'])
```

## **Running the Tests**

Add these commands to your `Makefile`:

```makefile
# Run all tests with coverage
test-coverage:
	@echo "🧪 Running tests with coverage..."
	@$(PYTHON) -m pytest tests/ -v --cov=decommission_tool --cov-report=html --cov-report=term

# Run specific test categories
test-unit:
	@echo "🧪 Running unit tests..."
	@$(PYTHON) -m pytest tests/test_decommission_tool.py -v

test-integration:
	@echo "🧪 Running integration tests..."
	@$(PYTHON) -m pytest tests/test_integration.py -v

# Run tests with detailed output
test-verbose:
	@echo "🧪 Running tests with verbose output..."
	@$(PYTHON) -m pytest tests/ -v -s --tb=long
```

These comprehensive unit tests cover:

- **All scanning methods** for different file types
- **Constraint validation** (file size, excluded directories)
- **Error handling** for invalid YAML, binary files, unicode content
- **Edge cases** like empty files, symlinks, multi-document YAML
- **Integration scenarios** with realistic repository structures
- **Main function testing** with different exit conditions
- **Summary generation** and output formatting

The tests ensure your decommissioning tool is robust and handles real-world scenarios effectively.

Citations:
[1] [repomix-output.xml](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/8768170/d1af88b4-8f13-49c1-b2d1-cb1e9d369be9/repomix-output.xml)