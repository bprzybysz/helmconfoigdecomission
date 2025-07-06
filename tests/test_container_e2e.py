"""
Clean E2E tests using the new container manager.
"""
import pytest
from pathlib import Path
from .container_manager import AsyncContainerManager, AsyncE2ETestSuite

# Test configuration
COMPOSE_FILE = Path(__file__).parent.parent / "docker-compose.yml"
TEST_DB_NAME = "example-db"
TEST_BRANCH_NAME = f"chore/decommission-{TEST_DB_NAME}"

@pytest.fixture(scope="session")
async def container_env():
    """Session-scoped container environment."""
    async with AsyncContainerManager(COMPOSE_FILE) as container:
        yield container

@pytest.fixture(scope="function")
async def fresh_container():
    """Function-scoped fresh container for each test."""
    async with AsyncContainerManager(COMPOSE_FILE) as container:
        yield container

class TestContainerE2E:
    """Clean E2E tests for containerized decommission tool."""
    
    def test_container_basic_health(self, container_env):
        """Test basic container health and Python environment."""
        # Test Python version
        result = container_env.execute(["python", "--version"])
        assert "Python 3.1" in result.stdout  # Python 3.11+
        
        # Test our module import
        result = container_env.execute([
            "python", "-c", "import decommission_tool; print('Import successful')"
        ])
        assert "Import successful" in result.stdout
    
    def test_container_file_access(self, container_env):
        """Test that container can access mounted test repository."""
        # List mounted test repo
        result = container_env.execute(["ls", "-la", "/app/test_repo"])
        assert "service.yaml" in result.stdout
        
        # Test Python can read the files
        result = container_env.execute([
            "python", "-c", 
            "from pathlib import Path; print(list(Path('/app/test_repo').glob('*.yaml')))"
        ])
        assert "service.yaml" in result.stdout
    
    def test_decommission_tool_help(self, container_env):
        """Test decommission tool help command."""
        result = container_env.execute([
            "python", "-m", "decommission_tool", "--help"
        ])
        assert "PostgreSQL database" in result.stdout
        assert "--remove" in result.stdout
        assert "--dry-run" in result.stdout
    
    def test_decommission_tool_scan_only(self, container_env):
        """Test scanning for database references without removal."""
        result = container_env.execute([
            "python", "-m", "decommission_tool",
            "/app/test_repo", TEST_DB_NAME
        ])
        
        # Should complete successfully
        assert result.returncode == 0
        # Should show scan results in output
        assert "Scanning repository" in result.stdout or "Found references" in result.stdout
    
    def test_decommission_tool_dry_run(self, container_env):
        """Test dry run removal mode."""
        result = container_env.execute([
            "python", "-m", "decommission_tool",
            "/app/test_repo", TEST_DB_NAME, "--remove", "--dry-run"
        ])
        
        assert result.returncode == 0
        assert "dry run" in result.stdout.lower() or "no changes were made" in result.stdout.lower()
    
    def test_file_operations_in_container(self, fresh_container):
        """Test file operations within container."""
        # Create a test file
        fresh_container.execute([
            "sh", "-c", "echo 'test content' > /tmp/test_file.txt"
        ])
        
        # Verify file exists and has content
        result = fresh_container.execute(["cat", "/tmp/test_file.txt"])
        assert "test content" in result.stdout
        
        # Clean up
        fresh_container.execute(["rm", "/tmp/test_file.txt"])
    
    def test_git_operations_in_container(self, fresh_container):
        """Test git operations within container."""
        # Test git is available
        result = fresh_container.execute(["git", "--version"])
        assert "git version" in result.stdout
        
        # Test git operations in test repo
        result = fresh_container.execute([
            "git", "-C", "/app/test_repo", "status"
        ])
        # Should not fail (even if not a git repo, should give meaningful error)
        assert result.returncode == 0 or "not a git repository" in result.stderr

class TestE2EScenarios:
    """Complex E2E scenarios using the test suite."""
    
    def test_full_decommission_workflow(self):
        """Test complete decommission workflow as separate scenarios."""
        suite = AsyncE2ETestSuite(COMPOSE_FILE)
        
        # Scenario 1: Initial scan
        def scan_scenario(container):
            result = container.execute([
                "python", "-m", "decommission_tool",
                "/app/test_repo", TEST_DB_NAME
            ])
            assert result.returncode == 0
        
        # Scenario 2: Dry run removal
        def dry_run_scenario(container):
            result = container.execute([
                "python", "-m", "decommission_tool",
                "/app/test_repo", TEST_DB_NAME, "--remove", "--dry-run"
            ])
            assert result.returncode == 0
            assert "dry run" in result.stdout.lower() or "no changes" in result.stdout.lower()
        
        # Run scenarios
        suite.run_test_scenario("initial_scan", scan_scenario)
        suite.run_test_scenario("dry_run_removal", dry_run_scenario)
        
        # Check results
        summary = suite.get_summary()
        assert summary["failed"] == 0, f"Test scenarios failed: {summary}"
        assert summary["success_rate"] == 1.0

@pytest.mark.slow
def test_container_performance():
    """Test container startup and execution performance."""
    import time
    
    start_time = time.time()
    
    with ContainerManager(COMPOSE_FILE) as container:
        setup_time = time.time() - start_time
        
        # Test command execution time
        cmd_start = time.time()
        container.execute(["python", "--version"])
        cmd_time = time.time() - cmd_start
        
        assert setup_time < 30, f"Container setup took too long: {setup_time}s"
        assert cmd_time < 5, f"Command execution took too long: {cmd_time}s"

def test_container_error_handling():
    """Test container error handling and cleanup."""
    with pytest.raises(RuntimeError):
        with ContainerManager(COMPOSE_FILE) as container:
            # This should fail and trigger cleanup
            container.execute(["python", "-c", "raise Exception('Test error')"])

if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])
