import os
import re
import sys
import json
import yaml
import subprocess
from pathlib import Path
from typing import List, Dict, Tuple, Optional

class PostgreSQLDecommissionTool:
    def __init__(self, repo_path: str, db_name: str, remove: bool = False, max_findings: int = 100):
        self.repo_path = Path(repo_path)
        self.db_name = db_name
        self.remove = remove
        self.max_findings = max_findings
        self.findings = {}
        self.original_branch = None
        self.test_branch = None
        self.constraints = {
            'yaml_extensions': ['.yaml', '.yml'],
            'config_extensions': ['.conf', '.env', '.properties', '.toml'],
            'source_extensions': ['.go', '.py', '.ts', '.js', '.java', '.rb', '.php'],
            'max_file_size': 10 * 1024 * 1024,  # 10MB limit
            'exclude_dirs': ['.git', 'node_modules', '__pycache__', '.pytest_cache', 'vendor', 'target', 'build', 'dist']
        }

    def _run_git_command(self, cmd: List[str]) -> subprocess.CompletedProcess:
        """Run git command and return result"""
        return subprocess.run(cmd, cwd=self.repo_path, capture_output=True, text=True)

    def get_current_branch(self) -> str:
        """Get the current git branch name."""
        result = self._run_git_command(['git', 'rev-parse', '--abbrev-ref', 'HEAD'])
        if result.returncode == 0:
            return result.stdout.strip()
        return ""

    def create_test_branch(self, branch_name: Optional[str] = None) -> bool:
        """Create and checkout test branch for safe modifications"""
        try:
            self.original_branch = self.get_current_branch()
            if not self.original_branch:
                print("Not a git repository or no branch checked out.", file=sys.stderr)
                return False

            if not branch_name:
                branch_name = f"chore/{self.db_name}-decommission"
            self.test_branch = branch_name

            result = self._run_git_command(['git', 'show-ref', '--verify', f'refs/heads/{self.test_branch}'])
            if result.returncode == 0:
                checkout_result = self._run_git_command(['git', 'checkout', self.test_branch])
            else:
                checkout_result = self._run_git_command(['git', 'checkout', '-b', self.test_branch])

            if checkout_result.returncode != 0:
                print(f"Failed to checkout branch '{self.test_branch}': {checkout_result.stderr}", file=sys.stderr)
                return False

            print(f"Switched to new branch '{self.test_branch}'")
            return True

        except Exception as e:
            print(f"Error creating test branch: {e}", file=sys.stderr)
            return False

    def commit_changes(self, message: Optional[str] = None) -> bool:
        """Commit changes to the test branch."""
        if not self.test_branch:
            print("Not on a test branch. Cannot commit.", file=sys.stderr)
            return False
        
        if not message:
            message = f"chore: remove PostgreSQL database '{self.db_name}' references"
        
        add_result = self._run_git_command(['git', 'add', '.'])
        if add_result.returncode != 0:
            print(f"Failed to stage changes: {add_result.stderr}", file=sys.stderr)
            return False
        
        commit_result = self._run_git_command(['git', 'commit', '-m', message])
        if commit_result.returncode != 0:
            if "nothing to commit" in commit_result.stdout or "nothing to commit" in commit_result.stderr:
                print("No changes to commit.")
                return True
            print(f"Failed to commit changes: {commit_result.stderr}", file=sys.stderr)
            return False
        
        print(f"Committed changes with message: '{message}'")
        return True

    def switch_back_to_original(self) -> bool:
        """Switch back to original branch"""
        return self.revert_changes()

    def delete_test_branch(self) -> bool:
        """Delete the test branch"""
        if not self.test_branch:
            return True
        
        # Switch to original branch first
        if not self.switch_back_to_original():
            return False
        
        delete_result = self._run_git_command(['git', 'branch', '-D', self.test_branch])
        if delete_result.returncode != 0:
            print(f"Failed to delete test branch '{self.test_branch}': {delete_result.stderr}", file=sys.stderr)
            return False
        
        print(f"✅ Deleted test branch: {self.test_branch}")
        return True

    def revert_changes(self) -> bool:
        """Revert changes and go back to the original branch."""
        if not self.original_branch:
            print("No original branch recorded. Cannot revert.", file=sys.stderr)
            return False

        checkout_result = self._run_git_command(['git', 'checkout', self.original_branch])
        if checkout_result.returncode != 0:
            print(f"Failed to checkout original branch '{self.original_branch}': {checkout_result.stderr}", file=sys.stderr)
            return False

        if self.test_branch:
            delete_branch_result = self._run_git_command(['git', 'branch', '-D', self.test_branch])
            if delete_branch_result.returncode != 0:
                print(f"Failed to delete test branch '{self.test_branch}': {delete_branch_result.stderr}", file=sys.stderr)
        
        return True

    def get_git_status(self) -> Dict[str, List[str]]:
        """Get git status."""
        status_result = self._run_git_command(['git', 'status', '--porcelain'])
        if status_result.returncode != 0:
            return {'error': ['Could not get git status.']}
        
        status = {'modified': [], 'deleted': [], 'added': [], 'untracked': []}
        for line in status_result.stdout.strip().splitlines():
            if line.startswith(' M '):
                status['modified'].append(line[3:])
            elif line.startswith(' D '):
                status['deleted'].append(line[3:])
            elif line.startswith('A  '):
                status['added'].append(line[3:])
            elif line.startswith('?? '):
                status['untracked'].append(line[3:])
        return status

    def _is_excluded(self, path: Path) -> bool:
        """Check if a file or directory should be excluded from scan."""
        return any(part in self.constraints['exclude_dirs'] for part in path.parts)

    def scan_repository(self) -> Dict:
        """Scan the repository to find all references to the database."""
        self.findings = {
            'helm_dependencies': [],
            'pvc_references': [],
            'config_map_references': [],
            'source_code_references': [],
            'total_scanned': 0,
            'total_found': 0
        }
        found_files = set()

        for file_path in self.repo_path.rglob('*'):
            if file_path.is_file() and not self._is_excluded(file_path):
                self.findings['total_scanned'] += 1
                try:
                    content = file_path.read_text(encoding='utf-8')
                    added_to_findings = False

                    if file_path.name == 'Chart.yaml':
                        try:
                            chart_content = yaml.safe_load(content)
                            for dep in chart_content.get('dependencies', []):
                                if dep.get('name') == 'postgresql':
                                    self.findings['helm_dependencies'].append({'file': str(file_path), 'dependency': dep})
                                    added_to_findings = True
                        except yaml.YAMLError:
                            pass # Ignore if not a valid YAML
                    
                    if 'pvc' in file_path.name.lower() and file_path.suffix in self.constraints['yaml_extensions']:
                        if 'postgres' in content.lower():
                            self.findings['pvc_references'].append({'file': str(file_path)})
                            added_to_findings = True
                    
                    if file_path.suffix in self.constraints['yaml_extensions'] and not added_to_findings: # Avoid double counting if already added as Chart or PVC
                        if self.db_name in content or 'postgresql' in content.lower():
                            self.findings['config_map_references'].append({'file': str(file_path)})
                            added_to_findings = True
                    
                    if file_path.suffix in self.constraints['source_extensions'] and not added_to_findings: # Avoid double counting
                        if self.db_name in content or 'postgresql' in content.lower():
                            self.findings['source_code_references'].append({'file': str(file_path)})
                            added_to_findings = True
                    
                    if added_to_findings:
                        found_files.add(str(file_path))
                except (UnicodeDecodeError, OSError) as e:
                    print(f"Could not read file {file_path}: {e}", file=sys.stderr)

        self.findings['total_found'] = len(found_files)
        return self.findings

    def remove_references(self):
        """Remove found references from files."""
        if not self.remove:
            return

        # Remove Helm dependencies
        for finding in self.findings.get('helm_dependencies', []):
            file_path = Path(finding['file'])
            try:
                with file_path.open('r') as f:
                    chart = yaml.safe_load(f)
                if 'dependencies' in chart:
                    chart['dependencies'] = [dep for dep in chart['dependencies'] if dep.get('name') != 'postgresql']
                    with file_path.open('w') as f:
                        yaml.dump(chart, f)
                    self._run_git_command(['git', 'add', str(file_path)])
            except Exception as e:
                print(f"Error processing {file_path}: {e}", file=sys.stderr)

        # Remove PVC files
        for finding in self.findings.get('pvc_references', []):
            file_path = Path(finding['file'])
            try:
                os.remove(file_path)
                self._run_git_command(['git', 'rm', str(file_path)])
            except OSError as e:
                print(f"Error deleting {file_path}: {e}", file=sys.stderr)

        # Remove from other YAMLs and source code
        all_files_to_clean = set(f['file'] for f in self.findings.get('config_map_references', [])) | set(f['file'] for f in self.findings.get('source_code_references', []))
        for file_path_str in all_files_to_clean:
            file_path = Path(file_path_str)
            try:
                if file_path.suffix in ['.yaml', '.yml']:
                    with file_path.open('r') as f:
                        data = yaml.safe_load(f)
                    
                    def remove_from_dict(obj, db_name):
                        if isinstance(obj, dict):
                            keys_to_delete = []
                            for k, v in list(obj.items()): # Iterate over a copy since we're modifying
                                if isinstance(v, (dict, list)):
                                    remove_from_dict(v, db_name)
                                elif isinstance(v, str):
                                    if db_name in v or 'postgresql' in v.lower():
                                        # Replace the specific database name or 'postgresql' string
                                        obj[k] = v.replace(db_name, '').replace('postgresql', '')
                                if db_name in str(k) or 'postgresql' in str(k).lower():
                                    keys_to_delete.append(k)
                            for k in keys_to_delete:
                                del obj[k]
                        elif isinstance(obj, list):
                            items_to_remove_indices = []
                            for i, item in enumerate(obj):
                                if isinstance(item, (dict, list)):
                                    remove_from_dict(item, db_name)
                                elif isinstance(item, str):
                                    if db_name in item or 'postgresql' in item.lower():
                                        # Replace the specific database name or 'postgresql' string
                                        obj[i] = item.replace(db_name, '').replace('postgresql', '')
                            # Remove empty strings or items that become irrelevant after replacement
                            obj[:] = [item for item in obj if item not in ('', None)]
                    
                    remove_from_dict(data, self.db_name)
                    
                    with file_path.open('w') as f:
                        yaml.dump(data, f)
                    self._run_git_command(['git', 'add', str(file_path)])
                else:
                    lines = file_path.read_text(encoding='utf-8').splitlines()
                    new_lines = [line for line in lines if self.db_name not in line and 'postgresql' not in line.lower()]
                    if len(lines) != len(new_lines):
                        file_path.write_text('\n'.join(new_lines) + '\n', encoding='utf-8')
                        self._run_git_command(['git', 'add', str(file_path)])
            except Exception as e:
                print(f"Error processing {file_path}: {e}", file=sys.stderr)

    def show_diff(self, max_lines: int = 30) -> str:
        """Show git diff."""
        diff_result = self._run_git_command(['git', 'diff'])
        if diff_result.returncode != 0:
            return "Could not get diff."
        
        diff_lines = diff_result.stdout.splitlines()
        if max_lines > 0 and len(diff_lines) > max_lines:
            return '\n'.join(diff_lines[:max_lines]) + f"\n... (diff truncated to {max_lines} lines)"
        return '\n'.join(diff_lines)

    def commit_changes(self, message: Optional[str] = None) -> bool:
        """Commit changes."""
        if not message:
            message = f"feat: Decommission {self.db_name}"
        
        commit_result = self._run_git_command(['git', 'commit', '-m', message])
        if commit_result.returncode != 0:
            print(f"Failed to commit changes: {commit_result.stderr}", file=sys.stderr)
            return False
        
        return True

    def run(self):
        """Run the decommissioning tool."""
        self.scan_repository()
        if self.remove:
            self.remove_references()

def generate_summary_and_plan(findings: Dict, db_name: str, remove: bool) -> Tuple[str, str]:
    summary_lines = [
        f"Decommissioning Plan for PostgreSQL Database: {db_name}",
        "" # Placeholder for detailed summary
    ]

    plan_lines = ["Decommissioning Plan:"]
    
    # Detailed summary of findings
    helm_deps_count = len(findings.get('helm_dependencies', []))
    pvc_refs_count = len(findings.get('pvc_references', []))
    config_map_refs_count = len(findings.get('config_map_references', []))
    source_code_refs_count = len(findings.get('source_code_references', []))

    summary_details = []
    if helm_deps_count > 0:
        summary_details.append(f"- Helm Dependencies: {helm_deps_count} found")
    if pvc_refs_count > 0:
        summary_details.append(f"- PVC References: {pvc_refs_count} found")
    if config_map_refs_count > 0:
        summary_details.append(f"- ConfigMap References: {config_map_refs_count} found")
    if source_code_refs_count > 0:
        summary_details.append(f"- Source Code References: {source_code_refs_count} found")

    if summary_details:
        summary_lines.append("\n".join(summary_details))
    else:
        summary_lines.append("No PostgreSQL references found.")

    # Decommissioning plan based on findings
    step = 1
    if helm_deps_count > 0:
        plan_lines.append(f"{step}. Remove Helm Dependency (Chart.yaml)")
        step += 1
    if pvc_refs_count > 0:
        plan_lines.append(f"{step}. Delete Persistent Volume Claims (PVCs)")
        step += 1
    if config_map_refs_count > 0:
        plan_lines.append(f"{step}. Remove Configuration Entries (values.yaml, ConfigMaps)")
        step += 1
    if source_code_refs_count > 0:
        plan_lines.append(f"{step}. Remove Database References from Source Code")
        step += 1

    plan_lines.append(f"{step}. Manual Review")

    return "\n".join(summary_lines), "\n".join(plan_lines)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python decommission_tool.py <repo_path> <db_name> [--remove]", file=sys.stderr)
        sys.exit(1)
    
    repo_path = sys.argv[1]
    db_name = sys.argv[2]
    remove = "--remove" in sys.argv

    tool = PostgreSQLDecommissionTool(repo_path, db_name, remove)
    
    try:
        if remove:
            if not tool.create_test_branch():
                print("Failed to create test branch. Aborting.", file=sys.stderr)
                sys.exit(1)
            print(f"🌿 Switched to new branch: {tool.test_branch}")

        tool.run()

        if not remove:
            summary, plan = generate_summary_and_plan(tool.findings, tool.db_name, tool.remove)
            print("\n📝 Summary of Findings:")
            print(summary)
            print("\n📝 Decommissioning Plan:")
            print(plan)
        else:
            # Show git status after changes
            status_after = tool.get_git_status()
            print("\n📋 Files after modification:")
            for status_type, files in status_after.items():
                if files and status_type != 'error':
                    print(f"  {status_type}: {files}")
            
            # Show diff
            if status_after.get('modified') or status_after.get('deleted'):
                print("\n📝 Changes made:")
                print(tool.show_diff(max_lines=30))
            
            # Commit changes
            print("\n💾 Committing changes...")
            commit_message = f"feat: Decommission {db_name}"
            if tool.commit_changes(commit_message):
                print("✅ Changes committed successfully")
            else:
                print("❌ Failed to commit changes")
            
            print("\n✅ Database references removal process finished!")
            print(f"🌿 Changes are in branch: {tool.test_branch}")
            print("💡 Use 'git checkout <original-branch>' to return to original state")
            print("💡 Or run with revert flag to automatically clean up")

    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)
