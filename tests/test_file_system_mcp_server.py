import pytest
from pathlib import Path
import os
import sys
import shutil
import subprocess

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from file_system_mcp_server import FileSystemMCPServer
from git_utils import GitRepository, GitBranchContext

class TestClient:
    """A test client to simulate the client pattern for the MCP server."""
    __test__ = False
    def __init__(self, server: FileSystemMCPServer):
        self.server = server

    def process_files(self, files: list[str], scan_and_delete: bool = False):
        return self.server.process_files(files, scan_and_delete=scan_and_delete)

@pytest.fixture
def temp_dir(tmp_path: Path) -> Path:
    """Create a temporary directory with some files for testing."""
    d = tmp_path / "test_dir"
    d.mkdir()
    (d / "file1.txt").write_text("hello")
    (d / "file2.log").write_text("world")
    (d / "sub").mkdir()
    (d / "sub" / "file3.txt").write_text("sub hello")
    (d / ".git").mkdir() # excluded dir
    (d / ".git" / "config").write_text("git config")
    return d

@pytest.fixture
def mcp_server() -> FileSystemMCPServer:
    """Returns an instance of the FileSystemMCPServer."""
    return FileSystemMCPServer()

def test_scan_all_files(mcp_server: FileSystemMCPServer, temp_dir: Path):
    """Test scanning all files without any filters."""
    results = list(mcp_server.scan_and_process_files(str(temp_dir)))
    # Results are batched, so we need to flatten the list
    all_files = [item for batch in results for item in batch]
    assert len(all_files) == 3
    paths = {f['path'] for f in all_files}
    assert str(temp_dir / "file1.txt") in paths
    assert str(temp_dir / "file2.log") in paths
    assert str(temp_dir / "sub" / "file3.txt") in paths

def test_scan_with_filetype_filter(mcp_server: FileSystemMCPServer, temp_dir: Path):
    """Test scanning with a filetype filter."""
    results = list(mcp_server.scan_and_process_files(str(temp_dir), filetypes_filter=['.log']))
    all_files = [item for batch in results for item in batch]
    assert len(all_files) == 1
    assert all_files[0]['path'] == str(temp_dir / "file2.log")

def test_batching(mcp_server: FileSystemMCPServer, temp_dir: Path):
    """Test that the results are batched correctly."""
    # There are 3 non-excluded files. With batch_size=1, we expect 3 batches.
    results = list(mcp_server.scan_and_process_files(str(temp_dir), batch_size=1))
    assert len(results) == 3
    assert len(results[0]) == 1
    assert len(results[1]) == 1
    assert len(results[2]) == 1

def test_scan_and_delete(mcp_server: FileSystemMCPServer, temp_dir: Path):
    """Test the scan_and_delete functionality."""
    assert (temp_dir / "file1.txt").exists()
    results = list(mcp_server.scan_and_process_files(str(temp_dir), scan_and_delete=True))
    all_files = [item for batch in results for item in batch]
    assert len(all_files) == 3
    assert not (temp_dir / "file1.txt").exists()
    assert not (temp_dir / "file2.log").exists()
    assert not (temp_dir / "sub" / "file3.txt").exists()
    deleted_files = [f for f in all_files if f['deleted']]
    assert len(deleted_files) == 3

def test_persistent_storage_protection(mcp_server: FileSystemMCPServer, tmp_path: Path, monkeypatch):
    """Test that files in persistent storage are protected from deletion."""
    # Create a directory that will be treated as persistent storage
    persistent_dir = tmp_path / "mnt" / "persistent"
    persistent_dir.mkdir(parents=True, exist_ok=True)
    
    # Create a test file in the persistent storage
    test_file = persistent_dir / "protected_file.txt"
    test_file.write_text("This is a protected file")
    
    # Create a regular file for comparison
    regular_file = tmp_path / "regular_file.txt"
    regular_file.write_text("This is a regular file")
    
    # Monkeypatch the is_persistent_storage method to recognize our test directory
    original_is_persistent = mcp_server.is_persistent_storage
    
    def mock_is_persistent_storage(path):
        if str(path).startswith(str(persistent_dir)):
            return True
        return original_is_persistent(path)
    
    monkeypatch.setattr(mcp_server, 'is_persistent_storage', mock_is_persistent_storage)
    
    # Try to delete both files without force_delete
    files_to_delete = [str(test_file), str(regular_file)]
    results = list(mcp_server.process_files(files_to_delete, scan_and_delete=True))
    all_files = [item for batch in results for item in batch]
    
    # Verify the persistent file was not deleted
    assert test_file.exists(), "Persistent storage file was deleted without force_delete"
    assert not regular_file.exists(), "Regular file was not deleted"
    
    # Check the results
    protected_result = next(f for f in all_files if f['path'] == str(test_file))
    assert not protected_result['deleted'], "Protected file was marked as deleted"
    assert 'error' in protected_result, "No error message for protected file"
    assert 'persistent storage' in protected_result['error'], "Incorrect error message"
    
    # Now try with force_delete=True
    results = list(mcp_server.process_files([str(test_file)], scan_and_delete=True, force_delete=True))
    all_files = [item for batch in results for item in batch]
    
    # Verify the persistent file was deleted with force_delete
    assert not test_file.exists(), "Persistent storage file was not deleted with force_delete"
    deleted_file = all_files[0]
    assert deleted_file['deleted'], "File was not marked as deleted with force_delete"
    assert 'error' not in deleted_file, "Error present when deletion should have succeeded"
    
    # Clean up
    try:
        if test_file.exists():
            test_file.unlink()
        if regular_file.exists():
            regular_file.unlink()
        if persistent_dir.exists():
            persistent_dir.rmdir()
    except Exception as e:
        print(f"Cleanup warning: {e}")

def test_is_persistent_storage(mcp_server: FileSystemMCPServer):
    """Test the path classification logic."""
    assert mcp_server.is_persistent_storage("/mnt/data/some/path")
    assert mcp_server.is_persistent_storage("/persistence/storage")
    assert not mcp_server.is_persistent_storage("/home/user/local/path")

@pytest.fixture
def git_repo(tmp_path: Path, request) -> Path:
    """Initialize a git repository in the temp_repo and handle cleanup."""
    repo_dir = tmp_path / "test-repo"
    repo_dir.mkdir()
    (repo_dir / "file1.txt").write_text("hello")
    (repo_dir / "file2.log").write_text("world")

    subprocess.run(["git", "init"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_dir, check=True)
    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_dir, check=True, capture_output=True)
    
    yield repo_dir
    
    if request.config.getoption("--dont-delete"):
        print(f"\nTest repository and branch left for inspection at: {repo_dir}")

def test_process_files(mcp_server: FileSystemMCPServer, temp_dir: Path):
    """Test processing an explicit list of files."""
    files_to_process = [
        str(temp_dir / "file1.txt"),
        str(temp_dir / "sub" / "file3.txt")
    ]
    results = list(mcp_server.process_files(files_to_process))
    all_files = [item for batch in results for item in batch]
    assert len(all_files) == 2
    paths = {f['path'] for f in all_files}
    assert str(temp_dir / "file1.txt") in paths
    assert str(temp_dir / "sub" / "file3.txt") in paths

def test_e2e_mcp_server_with_git(mcp_server: FileSystemMCPServer, git_repo: Path):
    """End-to-end test for file processing within a git branch."""
    client = TestClient(mcp_server)
    branch_name = "test-mcp-e2e"
    commit_message = "feat: test file deletion"
    
    # Create a GitRepository instance
    git_repo_obj = GitRepository(str(git_repo))
    
    # Pass the GitRepository instance instead of the path
    with GitBranchContext(git_repo_obj, branch_name, True) as git_util:
        files_to_delete = [
            str(git_repo / "file1.txt"),
            str(git_repo / "file2.log")
        ]
        assert (git_repo / "file1.txt").exists()
        assert (git_repo / "file2.log").exists()

        results = list(client.process_files(files_to_delete, scan_and_delete=True))
        all_files = [item for batch in results for item in batch]
        
        assert len(all_files) == 2
        assert not (git_repo / "file1.txt").exists()
        assert not (git_repo / "file2.log").exists()
        
        deleted_files = [f for f in all_files if f['deleted']]
        assert len(deleted_files) == 2
        
        # Stage and commit the changes
        git_repo_obj._run_git_command(["add", "."])
        git_repo_obj._run_git_command(["commit", "-m", commit_message])

    # After the context manager, we are on the original branch.
    # The test branch should exist with the commit.
    git_util = GitRepository(str(git_repo))
    assert git_util.checkout_branch(branch_name)  # Checks out the branch

    log_result = subprocess.run(["git", "log", "-1", "--pretty=%B"], cwd=git_repo, check=True, capture_output=True, text=True)
    assert commit_message in log_result.stdout
