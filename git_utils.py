import subprocess
import logging
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

class GitRepository:
    """
    A utility class to perform common Git operations.
    """

    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)
        if not self.repo_path.is_dir() or not (self.repo_path / ".git").is_dir():
            raise ValueError(f"The provided path '{repo_path}' is not a valid Git repository.")

    def _run_git_command(self, command: List[str]) -> Optional[str]:
        """
        Runs a git command and returns its stdout, or None if it fails.
        """
        try:
            result = subprocess.run(
                ["git"] + command,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            logging.error(f"Git command failed: {' '.join(command)}\nStdout: {e.stdout}\nStderr: {e.stderr}")
            return None
        except FileNotFoundError:
            logging.error("Git command not found. Please ensure Git is installed and in your PATH.")
            return None

    def get_current_branch(self) -> Optional[str]:
        """
        Returns the name of the current Git branch.
        """
        return self._run_git_command(["rev-parse", "--abbrev-ref", "HEAD"])

    def create_test_branch(self, branch_name: str) -> bool:
        """
        Creates a new branch and switches to it.
        """
        current_branch = self.get_current_branch()
        if not current_branch:
            return False
        
        # Delete branch if it already exists
        self._run_git_command(["branch", "-D", branch_name])
        
        if self._run_git_command(["checkout", "-b", branch_name]) is not None:
            logging.info(f"Switched to new branch '{branch_name}'.")
            return True
        return False

    def commit_changes(self, message: str) -> bool:
        """
        Stages all changes and commits them with the given message.
        Returns True if successful, False otherwise.
        """
        if self._run_git_command(["add", "."]) is None:
            return False
        
        # Check if there are any changes to commit
        status_output = self._run_git_command(["status", "--porcelain"])
        if not status_output:
            logging.info("No changes to commit.")
            return True  # No changes, so technically successful

        if self._run_git_command(["commit", "-m", message]) is None:
            return False
        logging.info(f"Changes committed with message: '{message}'")
        return True

    def revert_to_original_branch(self) -> bool:
        """
        Returns to the original branch that was checked out when the tool started.
        """
        if hasattr(self, 'original_branch'):
            return self.checkout_branch(self.original_branch)
        return False

    def delete_branch(self, branch_name: str, force: bool = False) -> bool:
        """
        Deletes a local Git branch.
        """
        command = ["branch", "-D", branch_name] if force else ["branch", "-d", branch_name]
        if self._run_git_command(command) is not None:
            logging.info(f"Deleted branch '{branch_name}'.")
            return True
        return False

    def show_diff(self, max_lines: int = 30) -> str:
        """
        Shows the current changes in the working directory.
        """
        diff = self._run_git_command(["diff"])
        if diff:
            lines = diff.split('\n')
            if max_lines and len(lines) > max_lines:
                return '\n'.join(lines[:max_lines]) + f"\n... (showing first {max_lines} of {len(lines)} lines)"
            return diff
        return "No changes to show."

    def checkout_branch(self, branch_name: str) -> bool:
        """
        Checks out the specified branch.
        """
        if not hasattr(self, 'original_branch'):
            self.original_branch = self.get_current_branch()
            
        if self._run_git_command(["checkout", branch_name]) is not None:
            logging.info(f"Checked out branch '{branch_name}'.")
            return True
        return False

    def get_commit_history(self, limit: int = 5) -> List[Dict[str, str]]:
        """
        Returns the commit history as a list of dictionaries.
        """
        format = "%H|%an|%ad|%s"
        log = self._run_git_command(["log", f"-n {limit}", f"--pretty=format:{format}", "--date=short"])
        if not log:
            return []
            
        commits = []
        for line in log.split('\n'):
            if '|' in line:
                commit_hash, author, date, subject = line.split('|', 3)
                commits.append({
                    'hash': commit_hash,
                    'author': author,
                    'date': date,
                    'subject': subject
                })
        return commits

    def get_remote_url(self, remote_name: str = "origin") -> Optional[str]:
        """
        Gets the URL of a remote repository.
        """
        return self._run_git_command(["remote", "get-url", remote_name])

    def push_changes(self, branch_name: Optional[str] = None, force: bool = False) -> bool:
        """
        Pushes changes to the remote repository.
        """
        if not branch_name:
            branch_name = self.get_current_branch()
            if not branch_name:
                return False
                
        command = ["push", "origin", branch_name]
        if force:
            command.insert(1, "--force")
            
        if self._run_git_command(command) is not None:
            logging.info(f"Pushed changes to '{branch_name}'.")
            return True
        return False

    def get_status(self) -> Dict[str, List[str]]:
        """
        Returns the status of the working directory.
        """
        status = {
            'staged': [],
            'unstaged': [],
            'untracked': []
        }
        
        output = self._run_git_command(["status", "--porcelain"])
        if not output:
            return status
            
        for line in output.split('\n'):
            if not line.strip():
                continue
                
            status_code = line[:2].strip()
            filename = line[3:].strip()
            
            if status_code.startswith('?'):
                status['untracked'].append(filename)
            elif status_code.startswith(' '):
                status['staged'].append(filename)
            else:
                status['unstaged'].append(filename)
                
        return status

    def reset_changes(self, hard: bool = False) -> bool:
        """
        Resets all changes in the working directory.
        """
        command = ["reset", "--hard"] if hard else ["reset", "--soft", "HEAD"]
        if self._run_git_command(command) is not None:
            logging.info("Reset changes in working directory.")
            return True
        return False

    def get_file_history(self, file_path: str) -> List[Dict[str, str]]:
        """
        Returns the commit history for a specific file.
        """
        format = "%H|%an|%ad|%s"
        log = self._run_git_command(["log", f"--pretty=format:{format}", "--date=short", "--follow", "--", file_path])
        if not log:
            return []
            
        history = []
        for line in log.split('\n'):
            if '|' in line:
                commit_hash, author, date, subject = line.split('|', 3)
                history.append({
                    'hash': commit_hash,
                    'author': author,
                    'date': date,
                    'subject': subject
                })
        return history

    def get_file_content_at_commit(self, file_path: str, commit_hash: str = "HEAD") -> Optional[str]:
        """
        Gets the content of a file at a specific commit.
        """
        return self._run_git_command(["show", f"{commit_hash}:{file_path}"])

    def get_commit_files(self, commit_hash: str = "HEAD") -> List[str]:
        """
        Gets the list of files changed in a commit.
        """
        files = self._run_git_command(["show", "--name-only", "--pretty=format:", commit_hash])
        return [f for f in files.split('\n') if f.strip()] if files else []

    def get_commit_diff(self, commit_hash: str = "HEAD") -> Optional[str]:
        """
        Gets the diff for a specific commit.
        """
        return self._run_git_command(["show", commit_hash])

    def get_branches(self) -> Dict[str, List[str]]:
        """
        Gets lists of local and remote branches.
        """
        local = self._run_git_command(["branch", "--format=%(refname:short)"])
        remote = self._run_git_command(["branch", "-r", "--format=%(refname:short)"])
        
        return {
            'local': local.split('\n') if local else [],
            'remote': [b for b in (remote.split('\n') if remote else []) if '->' not in b]
        }

    def get_tags(self) -> List[str]:
        """
        Gets the list of tags.
        """
        tags = self._run_git_command(["tag", "-l"])
        return [t for t in tags.split('\n') if t.strip()] if tags else []

    def create_tag(self, tag_name: str, message: str = "", commit_hash: str = "HEAD") -> bool:
        """
        Creates an annotated tag.
        """
        command = ["tag", "-a", tag_name, "-m", message] if message else ["tag", tag_name]
        command.append(commit_hash)
        
        if self._run_git_command(command) is not None:
            logging.info(f"Created tag '{tag_name}' at {commit_hash}.")
            return True
        return False

    def delete_tag(self, tag_name: str) -> bool:
        """
        Deletes a tag.
        """
        if self._run_git_command(["tag", "-d", tag_name]) is not None:
            logging.info(f"Deleted tag '{tag_name}'.")
            return True
        return False

    def get_config(self, key: str) -> Optional[str]:
        """
        Gets a Git configuration value.
        """
        return self._run_git_command(["config", key])

    def set_config(self, key: str, value: str, global_config: bool = False) -> bool:
        """
        Sets a Git configuration value.
        """
        command = ["config", "--global" if global_config else "--local", key, value]
        return self._run_git_command(command) is not None

    def get_commit_stats(self) -> Dict[str, int]:
        """
        Gets commit statistics (additions, deletions, files changed).
        """
        stats = {"insertions": 0, "deletions": 0, "files_changed": 0}
        output = self._run_git_command(["diff", "--shortstat"])
        
        if output:
            import re
            insertions = re.search(r'(\d+) insertion', output)
            deletions = re.search(r'(\d+) deletion', output)
            files = re.search(r'(\d+) file', output)
            
            if insertions:
                stats["insertions"] = int(insertions.group(1))
            if deletions:
                stats["deletions"] = int(deletions.group(1))
            if files:
                stats["files_changed"] = int(files.group(1))
                
        return stats

    def get_file_diff(self, file_path: str) -> Optional[str]:
        """
        Gets the diff for a specific file.
        """
        return self._run_git_command(["diff", file_path])

    def get_stash_list(self) -> List[Dict[str, str]]:
        """
        Gets the list of stashes.
        """
        format = "%gd|%an|%ar|%s"
        stashes = self._run_git_command(["stash", "list", f"--pretty=format:{format}"])
        if not stashes:
            return []
            
        result = []
        for stash in stashes.split('\n'):
            if '|' in stash:
                ref, author, date, message = stash.split('|', 3)
                result.append({
                    'ref': ref,
                    'author': author,
                    'date': date,
                    'message': message
                })
        return result

    def stash_changes(self, message: str = "") -> bool:
        """
        Stashes changes in the working directory.
        """
        command = ["stash", "save", message] if message else ["stash"]
        return self._run_git_command(command) is not None

    def apply_stash(self, stash_ref: str = "stash@{0}") -> bool:
        """
        Applies a stash.
        """
        return self._run_git_command(["stash", "apply", stash_ref]) is not None

    def drop_stash(self, stash_ref: str = "stash@{0}") -> bool:
        """
        Drops a stash.
        """
        return self._run_git_command(["stash", "drop", stash_ref]) is not None

    def get_merge_conflicts(self) -> List[str]:
        """
        Gets a list of files with merge conflicts.
        """
        output = self._run_git_command(["diff", "--name-only", "--diff-filter=U"])
        return [f for f in output.split('\n') if f.strip()] if output else []

    def abort_merge(self) -> bool:
        """
        Aborts a merge in progress.
        """
        return self._run_git_command(["merge", "--abort"]) is not None

    def cherry_pick(self, commit_hash: str) -> bool:
        """
        Applies the changes introduced by some existing commits.
        """
        return self._run_git_command(["cherry-pick", commit_hash]) is not None

    def rebase(self, upstream: str, branch: Optional[str] = None) -> bool:
        """
        Rebase the current branch onto upstream.
        """
        command = ["rebase", upstream]
        if branch:
            command.append(branch)
        return self._run_git_command(command) is not None

    def get_remote_branches(self) -> List[str]:
        """
        Gets the list of remote branches.
        """
        branches = self._run_git_command(["branch", "-r"])
        if not branches:
            return []
            
        return [b.strip() for b in branches.split('\n') if b.strip() and '->' not in b]

    def fetch_all(self) -> bool:
        """
        Fetches all remotes.
        """
        return self._run_git_command(["fetch", "--all"]) is not None

    def pull_changes(self, remote: str = "origin", branch: Optional[str] = None) -> bool:
        """
        Pulls changes from a remote repository.
        """
        command = ["pull", remote]
        if branch:
            command.append(branch)
        return self._run_git_command(command) is not None

    def get_commit_author(self, commit_hash: str = "HEAD") -> Optional[Dict[str, str]]:
        """
        Gets the author information for a commit.
        """
        format = "%an|%ae|%ad|%ar"
        output = self._run_git_command(["log", "-1", f"--pretty=format:{format}", commit_hash])
        if not output or '|' not in output:
            return None
            
        name, email, date, relative_date = output.split('|', 3)
        return {
            'name': name,
            'email': email,
            'date': date,
            'relative_date': relative_date
        }

    def get_file_blame(self, file_path: str) -> List[Dict[str, str]]:
        """
        Gets the blame information for a file.
        """
        format = "%H|%an|%ad|%s"
        blame = self._run_git_command(["blame", "-p", "--date=short", f"--pretty=format:{format}", file_path])
        if not blame:
            return []
            
        result = []
        for line in blame.split('\n'):
            if '|' in line:
                commit_hash, author, date, subject = line.split('|', 3)
                result.append({
                    'commit': commit_hash,
                    'author': author,
                    'date': date,
                    'subject': subject
                })
        return result

    def get_submodules(self) -> List[Dict[str, str]]:
        """
        Gets the list of submodules.
        """
        output = self._run_git_command(["submodule", "status"])
        if not output:
            return []
            
        submodules = []
        for line in output.split('\n'):
            if not line.strip():
                continue
                
            parts = line.split()
            if len(parts) >= 2:
                submodules.append({
                    'commit': parts[0].lstrip('-+ ')[:7],
                    'path': parts[1],
                    'branch': parts[2] if len(parts) > 2 else None
                })
        return submodules

    def init_submodules(self) -> bool:
        """
        Initializes and updates submodules.
        """
        return self._run_git_command(["submodule", "update", "--init", "--recursive"]) is not None

    def get_commit_message(self, commit_hash: str = "HEAD") -> Optional[str]:
        """
        Gets the commit message for a specific commit.
        """
        return self._run_git_command(["log", "-1", "--pretty=%B", commit_hash])

    def get_commit_files_stats(self, commit_hash: str = "HEAD") -> Dict[str, Dict[str, int]]:
        """
        Gets the file statistics for a specific commit.
        """
        stats = {}
        output = self._run_git_command(["show", "--stat", "--pretty=", commit_hash])
        if not output:
            return stats
            
        import re
        for line in output.split('\n'):
            match = re.match(r'^\s*(.*?)\s*\|\s*(\d+) ([+-]*)$', line)
            if match:
                filename = match.group(1).strip()
                changes = len(match.group(2))
                stats[filename] = {
                    'insertions': changes,
                    'deletions': 0
                }
        return stats

    def get_commit_diff_stats(self, commit_hash: str = "HEAD") -> Dict[str, int]:
        """
        Gets the diff statistics for a specific commit.
        """
        stats = {"files_changed": 0, "insertions": 0, "deletions": 0}
        output = self._run_git_command(["show", "--stat", "--pretty=", commit_hash])
        
        if output:
            import re
            files_changed = re.search(r'(\d+) file', output)
            insertions = re.search(r'(\d+) insertion', output)
            deletions = re.search(r'(\d+) deletion', output)
            
            if files_changed:
                stats["files_changed"] = int(files_changed.group(1))
            if insertions:
                stats["insertions"] = int(insertions.group(1))
            if deletions:
                stats["deletions"] = int(deletions.group(1))
                
        return stats


class GitBranchContext:
    """
    A context manager for working with Git branches.
    
    This class provides a convenient way to temporarily switch to a different branch
    and automatically switch back when the context is exited, even if an error occurs.
    """
    
    def __init__(self, repo: GitRepository, branch_name: str, create_if_missing: bool = False):
        """
        Initialize the context manager.
        
        Args:
            repo: A GitRepository instance
            branch_name: The name of the branch to switch to
            create_if_missing: If True, create the branch if it doesn't exist
        """
        self.repo = repo
        self.branch_name = branch_name
        self.create_if_missing = create_if_missing
        self.original_branch = None
        
    def __enter__(self):
        """Switch to the specified branch when entering the context."""
        self.original_branch = self.repo.get_current_branch()
        
        # Check if the branch exists
        branches = self.repo.get_branches()
        branch_exists = self.branch_name in branches['local']
        
        if not branch_exists and self.create_if_missing:
            # Create and switch to the new branch
            if not self.repo.create_test_branch(self.branch_name):
                raise RuntimeError(f"Failed to create branch: {self.branch_name}")
        elif not branch_exists:
            raise ValueError(f"Branch '{self.branch_name}' does not exist and create_if_missing is False")
        else:
            # Switch to the existing branch
            if not self.repo.checkout_branch(self.branch_name):
                raise RuntimeError(f"Failed to switch to branch: {self.branch_name}")
                
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Switch back to the original branch when exiting the context."""
        if self.original_branch:
            success = self.repo.checkout_branch(self.original_branch)
            if not success:
                logging.warning(f"Failed to switch back to original branch: {self.original_branch}")
        
        # Don't suppress exceptions
        return False
