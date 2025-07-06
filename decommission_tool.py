import os
import re
import sys
import argparse
import yaml
import subprocess
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Any
import logging

# Import the new GitRepository class
from git_utils import GitRepository

class PostgreSQLDecommissionTool:
    """
    A tool to find and remove references to a PostgreSQL database in a repository.
    This class is responsible for the core logic of scanning files and removing references.
    Git operations are handled separately.
    """
    def __init__(self, repo_path: str, db_name: str, remove: bool = False):
        self.repo_path = Path(repo_path)
        self.db_name = db_name
        self.remove = remove
        self.findings: Dict = {}
        self.constraints = {
            'yaml_extensions': ['.yaml', '.yml'],
            'source_extensions': ['.go', '.py', '.ts', '.js', '.java', '.rb', '.php'],
            'exclude_dirs': ['.git', 'node_modules', '__pycache__', '.pytest_cache', 'vendor', 'target', 'build', 'dist']
        }

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
                    
                    if file_path.suffix in self.constraints['yaml_extensions'] and not added_to_findings:
                        if self.db_name in content or 'postgresql' in content.lower():
                            self.findings['config_map_references'].append({'file': str(file_path)})
                            added_to_findings = True
                    
                    if file_path.suffix in self.constraints['source_extensions'] and not added_to_findings:
                        if self.db_name in content or 'postgresql' in content.lower():
                            self.findings['source_code_references'].append({'file': str(file_path)})
                            added_to_findings = True
                    
                    if added_to_findings:
                        found_files.add(str(file_path))
                except (UnicodeDecodeError, OSError) as e:
                    print(f"Could not read file {file_path}: {e}", file=sys.stderr)

        self.findings['total_found'] = len(found_files)
        return self.findings

    def _remove_from_yaml_structure(self, data: Any) -> Any:
        """Recursively removes db_name from string values in YAML structures."""
        if isinstance(data, dict):
            new_data = {}
            for k, v in data.items():
                if k == self.db_name or k == 'postgresql':
                    continue # Skip this key
                new_data[k] = self._remove_from_yaml_structure(v)
            return new_data
        elif isinstance(data, list):
            new_list = []
            for elem in data:
                if isinstance(elem, str) and (elem == self.db_name or elem == 'postgresql'):
                    continue # Skip this element
                new_list.append(self._remove_from_yaml_structure(elem))
            return new_list
        elif isinstance(data, str):
            # Use regex to replace the db_name, ensuring it's a whole word or part of a URL/connection string
            # This regex tries to match the db_name as a whole word or within common connection string patterns
            # It's a balance between being too aggressive and missing cases.
            pattern = re.compile(r'\b' + re.escape(self.db_name) + r'\b|' + re.escape(self.db_name) + r'(?=[/:@])')
            return pattern.sub('', data)
        return data

    def remove_references(self):
        """Remove found references from files."""
        if not self.remove:
            return

        for finding in self.findings.get('helm_dependencies', []):
            file_path = Path(finding['file'])
            logging.debug(f"Processing Helm dependencies in {file_path}")
            try:
                with file_path.open('r') as f:
                    chart = yaml.safe_load(f)
                if 'dependencies' in chart:
                    chart['dependencies'] = [dep for dep in chart['dependencies'] if dep.get('name') != 'postgresql']
                    with file_path.open('w') as f:
                        yaml.dump(chart, f, default_flow_style=False)
                    logging.debug(f"Successfully removed 'postgresql' dependency from {file_path}")
            except yaml.YAMLError as e:
                logging.error(f"Error processing YAML file {file_path}: {e}")
            except Exception as e:
                logging.error(f"An unexpected error occurred while processing {file_path}: {e}")

        for finding in self.findings.get('pvc_references', []):
            file_path = Path(finding['file'])
            try:
                os.remove(file_path)
            except OSError as e:
                print(f"Error deleting {file_path}: {e}", file=sys.stderr)

        all_files_to_clean = set(f['file'] for f in self.findings.get('config_map_references', [])) | set(f['file'] for f in self.findings.get('source_code_references', []))
        for file_path_str in all_files_to_clean:
            file_path = Path(file_path_str)
            logging.debug(f"Cleaning references in {file_path}")
            try:
                if file_path.suffix in self.constraints['yaml_extensions']:
                    with file_path.open('r') as f:
                        data = yaml.safe_load(f)
                    
                    data = self._remove_from_yaml_structure(data)
                    
                    with file_path.open('w') as f:
                        yaml.dump(data, f, default_flow_style=False)
                else:
                    lines = file_path.read_text(encoding='utf-8').splitlines()
                    new_lines = [line for line in lines if self.db_name not in line and 'postgresql' not in line.lower()]
                    if len(lines) != len(new_lines):
                        file_path.write_text('\n'.join(new_lines) + '\n', encoding='utf-8')
                        logging.debug(f"Successfully cleaned references from {file_path}")
            except yaml.YAMLError as e:
                logging.error(f"Error processing YAML file {file_path}: {e}")
            except Exception as e:
                logging.error(f"An unexpected error occurred while processing {file_path}: {e}")

    def run(self):
        """Run the decommissioning tool."""
        self.scan_repository()
        if self.remove:
            self.remove_references()

def generate_summary_and_plan(findings: Dict, db_name: str, remove: bool) -> Tuple[str, str]:
    summary_lines = [
        f"Decommissioning Plan for PostgreSQL Database: {db_name}",
        ""
    ]

    plan_lines = ["Decommissioning Plan:"]
    
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

    if not summary_details:
        summary_lines.append("No PostgreSQL references found.")
    else:
        summary_lines.append("\n".join(summary_details))

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

def main():
    """Main function to parse arguments and run the tool."""
    parser = argparse.ArgumentParser(
        description="A tool to scan a repository for PostgreSQL database references and optionally remove them.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("repo_path", help="The absolute path to the repository to scan.")
    parser.add_argument("db_name", help="The name of the PostgreSQL database to search for.")
    parser.add_argument("--remove", action="store_true", help="If set, creates a new git branch and removes all found references.")
    parser.add_argument("--branch-name", help="Specify a custom name for the new branch created with --remove.")

    args = parser.parse_args()

    repo_path = Path(args.repo_path)
    if not repo_path.is_dir():
        print(f"Error: The provided repository path '{args.repo_path}' does not exist or is not a directory.", file=sys.stderr)
        sys.exit(1)

    git_repo = None
    if args.remove:
        try:
            git_repo = GitRepository(str(repo_path))
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    tool = PostgreSQLDecommissionTool(str(repo_path), args.db_name, args.remove)
    
    original_branch = None
    if git_repo:
        original_branch = git_repo.get_current_branch()
        test_branch_name = args.branch_name if args.branch_name else f"chore/{args.db_name}-decommission"
    
    try:
        if args.remove and git_repo:
            if not git_repo.create_test_branch(test_branch_name):
                print("Failed to create test branch. Aborting.", file=sys.stderr)
                sys.exit(1)

        tool.run()

        if not args.remove:
            summary, plan = generate_summary_and_plan(tool.findings, tool.db_name, tool.remove)
            print("\n📝 Summary of Findings:")
            print(summary)
            print("\n📝 Decommissioning Plan:")
            print(plan)
        else:
            if git_repo:
                print("\n💾 Committing changes...")
                commit_message = f"feat: Decommission PostgreSQL DB '{tool.db_name}'"
                if git_repo.commit_changes(commit_message):
                    print("✅ Changes committed successfully")
                else:
                    print("❌ Failed to commit changes")

                print("\n✅ Database references removal process finished!")
                print(f"🌿 Changes are in branch: {git_repo.test_branch}")
                if original_branch:
                    print(f"💡 To revert, run: git checkout {original_branch} && git branch -D {git_repo.test_branch}")
    
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        if args.remove and git_repo and original_branch:
            git_repo.revert_to_original_branch()
            print(f"🔄 Reverted to original branch: {original_branch}")
        sys.exit(1)

if __name__ == "__main__":
    main()
