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
    branch_name = "test-mcp-e2e"
    commit_message = "feat: test file deletion"

    with GitBranchContext(str(git_repo), branch_name, commit_message) as git_util:
        files_to_delete = [
            str(git_repo / "file1.txt"),
            str(git_repo / "file2.log")
        ]
        assert (git_repo / "file1.txt").exists()
        assert (git_repo / "file2.log").exists()

        results = list(mcp_server.process_files(files_to_delete, scan_and_delete=True))
        all_files = [item for batch in results for item in batch]
        
        assert len(all_files) == 2
        assert not (git_repo / "file1.txt").exists()
        assert not (git_repo / "file2.log").exists()
        
        deleted_files = [f for f in all_files if f['deleted']]
        assert len(deleted_files) == 2

    # After the context manager, we are on the original branch.
    # The test branch should exist with the commit.
    git_util = GitRepository(str(git_repo))
    assert git_util.create_test_branch(branch_name)  # Checks out the branch

    log_result = subprocess.run(["git", "log", "-1", "--pretty=%B"], cwd=git_repo, check=True, capture_output=True, text=True)
    assert commit_message in log_result.stdout
