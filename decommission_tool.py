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

    def commit_changes(self, message: str) -> bool:
        """Commit changes to the test branch."""
        if not self.test_branch:
            print("Not on a test branch. Cannot commit.", file=sys.stderr)
            return False

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
        
        print(f"Reverted changes and returned to branch '{self.original_branch}'")
        self.test_branch = None
        return True

    def _is_valid_path(self, path: Path) -> bool:
        """Check if a path should be included in the scan."""
        if any(part in self.constraints['exclude_dirs'] for part in path.parts):
            return False
        try:
            if path.stat().st_size > self.constraints['max_file_size']:
                return False
        except FileNotFoundError:
            return False
        return True

    def _scan_source_code(self, file_path: Path) -> List[Dict]:
        """Scan source code for database name."""
        found = []
        try:
            content = file_path.read_text(encoding='utf-8')
            pattern = re.compile(re.escape(self.db_name), re.IGNORECASE)
            if pattern.search(content):
                lines = content.splitlines()
                matched_lines = [i + 1 for i, line in enumerate(lines) if pattern.search(line)]
                if matched_lines:
                    found.append({
                        'file': str(file_path.relative_to(self.repo_path)),
                        'lines': matched_lines
                    })
        except (UnicodeDecodeError, IOError):
            pass
        return found

    def _scan_config_file(self, file_path: Path) -> List[Dict]:
        """Scan config files for database name."""
        found = []
        try:
            content = file_path.read_text(encoding='utf-8')
            if self.db_name in content:
                lines = content.splitlines()
                matched_lines = [i + 1 for i, line in enumerate(lines) if self.db_name in line]
                if matched_lines:
                    found.append({
                        'file': str(file_path.relative_to(self.repo_path)),
                        'lines': matched_lines
                    })
        except (UnicodeDecodeError, IOError):
            pass
        return found

    def _scan_helm_chart(self, file_path: Path) -> List[Dict]:
        """Scan Chart.yaml for PostgreSQL dependency."""
        if file_path.name != 'Chart.yaml':
            return []
        
        found = []
        try:
            with file_path.open('r', encoding='utf-8') as f:
                chart = yaml.safe_load(f)
                if 'dependencies' in chart and chart['dependencies']:
                    for dep in chart['dependencies']:
                        if 'postgresql' in dep.get('name', ''):
                            found.append({
                                'file': str(file_path.relative_to(self.repo_path)),
                                'content': f"name: {dep['name']}, version: {dep.get('version', 'N/A')}"
                            })
        except (yaml.YAMLError, IOError):
            pass
        return found

    def _scan_pvc(self, file_path: Path) -> List[Dict]:
        """Scan YAML files for PVCs related to postgres."""
        found = []
        try:
            content = file_path.read_text(encoding='utf-8')
            if 'PersistentVolumeClaim' in content and ('postgres' in content or 'pg' in content):
                found.append({
                    'file': str(file_path.relative_to(self.repo_path)),
                    'content': 'Potential PostgreSQL PVC found'
                })
        except (UnicodeDecodeError, IOError):
            pass
        return found

    def scan_repository(self) -> Dict[str, List]:
        """Scan for all PostgreSQL references with constraints"""
        if not self.repo_path.is_dir():
            raise FileNotFoundError(f"Repository path does not exist or is not a directory: {self.repo_path}")

        all_files = [p for p in self.repo_path.rglob('*') if p.is_file() and self._is_valid_path(p)]
        
        findings = {
            'helm_dependencies': [],
            'config_references': [],
            'pvc_references': [],
            'source_code_references': []
        }

        for file_path in all_files:
            if sum(len(v) for v in findings.values()) >= self.max_findings:
                break

            file_suffix = file_path.suffix
            
            if file_suffix in self.constraints['source_extensions']:
                findings['source_code_references'].extend(self._scan_source_code(file_path))

            if file_suffix in self.constraints['yaml_extensions']:
                findings['helm_dependencies'].extend(self._scan_helm_chart(file_path))
                findings['pvc_references'].extend(self._scan_pvc(file_path))
                findings['config_references'].extend(self._scan_config_file(file_path))

            if file_suffix in self.constraints['config_extensions']:
                findings['config_references'].extend(self._scan_config_file(file_path))
        
        unique_configs = {item['file']: item for item in findings['config_references']}
        findings['config_references'] = list(unique_configs.values())

        self.findings = findings
        return findings

    def remove_references(self):
        """Remove found references from files."""
        if not self.remove:
            print("Removal flag not set. Skipping modification.")
            return

        for item in self.findings.get('helm_dependencies', []):
            file_path = self.repo_path / item['file']
            try:
                with file_path.open('r+', encoding='utf-8') as f:
                    chart = yaml.safe_load(f)
                    if 'dependencies' in chart:
                        chart['dependencies'] = [dep for dep in chart['dependencies'] if 'postgresql' not in dep.get('name', '')]
                        f.seek(0)
                        yaml.dump(chart, f)
                        f.truncate()
            except (IOError, yaml.YAMLError) as e:
                print(f"Error updating {file_path}: {e}")

        for item in self.findings.get('config_references', []) + self.findings.get('source_code_references', []):
            file_path = self.repo_path / item['file']
            try:
                content = file_path.read_text(encoding='utf-8')
                
                if file_path.name == 'values.yaml':
                    content = re.sub(r'^\s*postgresql:.*?(?=\n\S|\Z)', '', content, flags=re.DOTALL | re.MULTILINE)

                lines = content.splitlines()
                new_lines = [line for line in lines if self.db_name not in line]
                file_path.write_text('\n'.join(new_lines), encoding='utf-8')
            except IOError as e:
                print(f"Error updating {file_path}: {e}")

def generate_summary_and_plan(findings: Dict[str, List], db_name: str, remove: bool = False) -> Tuple[str, str]:
    """Generate a summary and decommissioning plan based on findings."""
    summary_lines = [f"Decommissioning Plan for PostgreSQL Database: {db_name}"]
    plan_lines = []
    
    summary_lines.append("\n--- Summary of Findings ---")
    summary_lines.append(f"- Helm Dependencies: {len(findings.get('helm_dependencies', []))} found")
    summary_lines.append(f"- Configuration References: {len(findings.get('config_references', []))} found")
    summary_lines.append(f"- PVC References: {len(findings.get('pvc_references', []))} found")
    summary_lines.append(f"- Source Code References: {len(findings.get('source_code_references', []))} found")
    
    plan_lines.append("\n--- Decommissioning Plan ---")
    step = 1
    
    if findings.get('helm_dependencies'):
        plan_lines.append(f"{step}. Remove Helm Dependency")
        step += 1
        
    if findings.get('config_references'):
        plan_lines.append(f"{step}. Remove Configuration Entries")
        step += 1
        
    if findings.get('pvc_references'):
        plan_lines.append(f"{step}. Delete Persistent Volume Claims (PVCs)")
        step += 1
        
    if findings.get('source_code_references'):
        plan_lines.append(f"{step}. Remove Database References from Source Code")
        step += 1
        
    plan_lines.append(f"{step}. Manual Review")
    
    return "\n".join(summary_lines), "\n".join(plan_lines)

def main():
    if len(sys.argv) < 3:
        print("Usage: python decommission_tool.py <repo_path> <db_name> [--remove]", file=sys.stderr)
        sys.exit(1)
        
    repo_path = sys.argv[1]
    db_name = sys.argv[2]
    should_remove = '--remove' in sys.argv
    output_file = Path("decommission_findings.json")

    tool = PostgreSQLDecommissionTool(repo_path, db_name, remove=should_remove)

    try:
        if should_remove:
            if not tool.create_test_branch():
                sys.exit(1)

        findings = tool.scan_repository()
        
        summary, plan = generate_summary_and_plan(findings, db_name, should_remove)
        
        print(summary)
        print(plan)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({'summary': summary, 'plan': plan, 'findings': findings}, f, indent=2)
        
        print(f"\n📄 Detailed findings exported to: {output_file}")

        if should_remove:
            print("\n🚀 Starting file modification process...")
            tool.remove_references()
            print("\n✅ Database references removal process finished!")
            
            commit_message = f"feat: Decommission {db_name}"
            if tool.commit_changes(commit_message):
                print(f"Changes committed to branch '{tool.test_branch}'. Please review and create a pull request.")
            else:
                print("Failed to commit changes. Reverting...", file=sys.stderr)
                tool.revert_changes()

        else:
            print("\n💡 Run with --remove flag to actually modify files")

        if findings.get('helm_dependencies') or findings.get('pvc_references'):
             print("\n❌ Critical findings detected. Exiting with error code.", file=sys.stderr)
             sys.exit(2)

    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        if tool.test_branch:
            print("Reverting changes due to error...", file=sys.stderr)
            tool.revert_changes()
        sys.exit(1)

if __name__ == "__main__":
    main()
