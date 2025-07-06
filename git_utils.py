import subprocess
from pathlib import Path
from typing import List, Dict, Optional, Callable, Any
import logging
from functools import wraps
import inspect

class GitRepository:
    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)
        if not (self.repo_path / '.git').is_dir():
            raise ValueError(f"'{repo_path}' is not a valid git repository.")
        self.original_branch: Optional[str] = None
        self.test_branch: Optional[str] = None

    def _run_command(self, cmd: List[str]) -> subprocess.CompletedProcess:
        return subprocess.run(cmd, cwd=self.repo_path, capture_output=True, text=True, check=False)

    def get_current_branch(self) -> str:
        result = self._run_command(['git', 'rev-parse', '--abbrev-ref', 'HEAD'])
        return result.stdout.strip() if result.returncode == 0 else ""

    def create_test_branch(self, branch_name: str) -> bool:
        self.original_branch = self.get_current_branch()
        if not self.original_branch:
            logging.error("Not a git repository or no branch checked out.")
            return False
        
        self.test_branch = branch_name
        result = self._run_command(['git', 'checkout', '-b', self.test_branch])
        if result.returncode != 0:
            # If branch already exists, just check it out
            if f"A branch named '{self.test_branch}' already exists" in result.stderr:
                logging.warning(f"Branch '{self.test_branch}' already exists. Checking it out.")
                result = self._run_command(['git', 'checkout', self.test_branch])
        
        if result.returncode != 0:
            logging.error(f"Failed to create or checkout branch '{self.test_branch}': {result.stderr}")
            return False
        
        logging.info(f"Switched to new branch: {self.test_branch}")
        return True

    def commit_changes(self, message: str) -> bool:
        self._run_command(['git', 'add', '.'])
        status_result = self._run_command(['git', 'status', '--porcelain'])
        if not status_result.stdout.strip():
            logging.info("No changes to commit.")
            return True
            
        result = self._run_command(['git', 'commit', '-m', message])
        if result.returncode == 0:
            logging.info(f"Committed changes with message: '{message}'")
            return True
        else:
            logging.error(f"Failed to commit changes: {result.stderr}")
            return False

    def revert_to_original_branch(self) -> bool:
        if self.original_branch:
            result = self._run_command(['git', 'checkout', self.original_branch])
            if result.returncode == 0:
                logging.info(f"Reverted to original branch: {self.original_branch}")
                return True
            else:
                logging.error(f"Failed to revert to original branch '{self.original_branch}': {result.stderr}")
                return False
        return False

    def delete_test_branch(self) -> bool:
        if not self.test_branch or not self.original_branch:
            return False
        self._run_command(['git', 'checkout', self.original_branch])
        result = self._run_command(['git', 'branch', '-D', self.test_branch])
        if result.returncode == 0:
            logging.info(f"Deleted test branch: {self.test_branch}")
            return True
        else:
            logging.error(f"Failed to delete test branch '{self.test_branch}': {result.stderr}")
            return False

    def show_diff(self, max_lines: int = 30) -> str:
        """Show git diff of unstaged changes."""
        diff_result = self._run_command(['git', 'diff'])
        if diff_result.returncode != 0:
            return "Could not get diff."
        
        diff_lines = diff_result.stdout.splitlines()
        if max_lines > 0 and len(diff_lines) > max_lines:
            return '\n'.join(diff_lines[:max_lines]) + f"\n... (diff truncated to {max_lines} lines)"
        return '\n'.join(diff_lines)

    def checkout_branch(self, branch_name: str) -> bool:
        result = self._run_command(['git', 'checkout', branch_name])
        if result.returncode == 0:
            logging.info(f"Switched to branch: {branch_name}")
            return True
        else:
            logging.error(f"Failed to checkout branch '{branch_name}': {result.stderr}")
            return False

class GitBranchContext:
    """Context manager for running code within a git branch."""
    def __init__(self, repo_path: str, branch_name: str, commit_message: str = "Test commit"):
        self.git_repo = GitRepository(repo_path)
        self.branch_name = branch_name
        self.commit_message = commit_message

    def __enter__(self):
        if not self.git_repo.create_test_branch(self.branch_name):
            raise RuntimeError(f"Failed to create test branch '{self.branch_name}'")
        return self.git_repo

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            if not self.git_repo.commit_changes(self.commit_message):
                logging.warning(f"Failed to commit changes for branch '{self.branch_name}'")
        
        self.git_repo.revert_to_original_branch()
        # The test branch is intentionally not deleted to allow for inspection.
        # The test fixture should handle the cleanup of the repo directory.
