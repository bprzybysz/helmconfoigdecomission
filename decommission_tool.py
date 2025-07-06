import logging
import sys
import re
from pathlib import Path
import argparse
import subprocess
from typing import List, Tuple, Dict, Any
import yaml

from git_utils import GitRepository, GitBranchContext

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

class PostgreSQLDecommissionTool:
    """
    A tool to find and remove references to a PostgreSQL database in a repository.
    This class is responsible for the core logic of scanning files and removing references.
    Git operations are handled separately.
    """

    def __init__(self, repo_path: str, db_name: str, remove: bool = False, dry_run: bool = False):
        self.repo_path = Path(repo_path)
        self.db_name = db_name
        self.remove = remove
        self.dry_run = dry_run
        self.findings: Dict = {}
        self.constraints = {
            'yaml_extensions': ['.yaml', '.yml'],
            'source_extensions': ['.go', '.py', '.ts', '.js', '.java', '.rb', '.php'],
            'documentation_extensions': ['.md'],
            'exclude_dirs': ['.git', 'node_modules', '__pycache__', '.pytest_cache', 'vendor', 'target', 'build', 'dist']
        }

    def _is_excluded(self, path: Path) -> bool:
        """Check if a file or directory should be excluded from scan."""
        return any(part in self.constraints['exclude_dirs'] for part in path.parts)

    def scan_file(self, file_path: Path) -> List[Tuple[int, str]]:
        """
        Scans a single file for references to the database name.
        Returns a list of (line_number, line_content) where the database name was found.
        """
        found_lines = []
        try:
            content = file_path.read_text(encoding='utf-8')

            if file_path.name == "Chart.yaml":
                try:
                    chart_data = yaml.safe_load(content)
                    if 'dependencies' in chart_data:
                        for dep in chart_data['dependencies']:
                            if dep.get('name') == 'postgresql':
                                found_lines.append((0, "Helm PostgreSQL dependency")) # Dummy line number, actual removal is YAML-aware
                                break
                except yaml.YAMLError:
                    logging.warning(f"Could not parse Chart.yaml: {file_path}")
            elif file_path.name == "pvc.yaml":
                if "postgresql" in content:
                    found_lines.append((0, "PostgreSQL PVC")) # Dummy line number, actual removal is file deletion

            # Scan for db_name in all files, including YAMLs (for values.yaml, etc.) and source files
            for i, line in enumerate(content.splitlines()):
                if re.search(r'\b' + re.escape(self.db_name) + r'\b', line):
                    found_lines.append((i + 1, line.strip()))
            if found_lines:
                logging.debug(f"Found references in {file_path.name}: {found_lines}")
        except Exception as e:
            logging.warning(f"Could not read file {file_path}: {e}")
        return found_lines

    def scan_repository(self) -> None:
        """
        Scans the entire repository for references to the database name.
        Populates self.findings with file paths and their matching lines.
        """
        logging.info(f"Scanning repository {self.repo_path} for references to '{self.db_name}'...")
        for file_path in self.repo_path.rglob('*'):
            if file_path.is_file() and not self._is_excluded(file_path):
                if (file_path.suffix in self.constraints['yaml_extensions'] or 
                    file_path.suffix in self.constraints['source_extensions'] or
                    file_path.suffix in self.constraints['documentation_extensions']):
                    found_lines = self.scan_file(file_path)
                    if found_lines:
                        self.findings[str(file_path.relative_to(self.repo_path))] = found_lines
        logging.info("Scan complete.")

    def _remove_from_file(self, file_path: Path) -> None:
        """
        Removes references to the database name from a single file.
        This is a destructive operation and should only be called if self.remove is True.
        """
        relative_path = file_path.relative_to(self.repo_path)

        if file_path.name == "pvc.yaml" and ("postgresql" in file_path.read_text() or self.db_name in file_path.read_text()):
            if not self.dry_run:
                file_path.unlink()
                logging.info(f"Deleted {relative_path} as it contained references to {self.db_name}")
            else:
                logging.info(f"Dry run: Would delete {relative_path} as it contains references to {self.db_name}")
            return

        if file_path.suffix in self.constraints['yaml_extensions']:
            try:
                with file_path.open('r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                
                modified = False
                if file_path.name == "Chart.yaml" and 'dependencies' in data:
                    logging.debug(f"Processing Chart.yaml: {relative_path}")
                    initial_len = len(data['dependencies'])
                    logging.debug(f"Initial dependencies: {data['dependencies']}")
                    data['dependencies'] = [dep for dep in data['dependencies'] if dep.get('name') != 'postgresql']
                    logging.debug(f"Dependencies after filtering: {data['dependencies']}")
                    if len(data['dependencies']) < initial_len:
                        modified = True
                        logging.debug("Chart.yaml modified flag set to True.")

                if file_path.name == "values.yaml":
                    if 'postgresql' in data and self.db_name in str(data['postgresql']):
                        del data['postgresql']
                        modified = True
                    if 'database' in data and data['database'].get('name') == self.db_name:
                        del data['database']
                        modified = True

                if modified:
                    logging.debug(f"File {relative_path} was modified. Dry run: {self.dry_run}")
                    if not self.dry_run:
                        with file_path.open('w', encoding='utf-8') as f:
                            yaml.dump(data, f, sort_keys=False)
                        logging.info(f"Removed references from {relative_path} (YAML)")
                    else:
                        logging.info(f"Dry run: Would remove references from {relative_path} (YAML)")
                elif self.db_name in file_path.read_text(encoding='utf-8'): # Fallback for YAML files if not handled by specific logic
                    original_content = file_path.read_text(encoding='utf-8')
                    new_content = re.sub(r'\b' + re.escape(self.db_name) + r'\b', '', original_content)
                    if original_content != new_content:
                        if not self.dry_run:
                            file_path.write_text(new_content, encoding='utf-8')
                            logging.info(f"Removed references from {relative_path}")
                        else:
                            logging.info(f"Dry run: Would remove references from {relative_path}")

            except yaml.YAMLError as e:
                logging.warning(f"Could not parse YAML file {relative_path}: {e}. Attempting regex replacement.")
                original_content = file_path.read_text(encoding='utf-8')
                new_content = re.sub(r'\b' + re.escape(self.db_name) + r'\b', '', original_content)
                if original_content != new_content:
                    if not self.dry_run:
                        file_path.write_text(new_content, encoding='utf-8')
                        logging.info(f"Removed references from {relative_path}")
                    else:
                        logging.info(f"Dry run: Would remove references from {relative_path}")
            except Exception as e:
                logging.warning(f"Error processing {relative_path}: {e}. Attempting regex replacement.")
                original_content = file_path.read_text(encoding='utf-8')
                new_content = re.sub(r'\b' + re.escape(self.db_name) + r'\b', '', original_content)
                if original_content != new_content:
                    if not self.dry_run:
                        file_path.write_text(new_content, encoding='utf-8')
                        logging.info(f"Removed references from {relative_path}")
                    else:
                        logging.info(f"Dry run: Would remove references from {relative_path}")
        else:
            original_content = file_path.read_text(encoding='utf-8')
            new_content = re.sub(r'\b' + re.escape(self.db_name) + r'\b', '', original_content)
            if original_content != new_content:
                if not self.dry_run:
                    file_path.write_text(new_content, encoding='utf-8')
                    logging.info(f"Removed references from {relative_path}")
                else:
                    logging.info(f"Dry run: Would remove references from {relative_path}")

    def remove_references(self) -> None:
        """
        Removes all found references from the files if self.remove is True.
        """
        if not self.remove:
            logging.info("Remove flag is not set. Skipping reference removal.")
            return

        if not self.findings:
            logging.info("No references found to remove.")
            return

        logging.info(f"Removing references to '{self.db_name}' from files...")
        for file_path_str in self.findings:
            full_path = self.repo_path / file_path_str
            if full_path.exists() and full_path.is_file():
                self._remove_from_file(full_path)
        logging.info("Reference removal complete.")

    def generate_report(self) -> Dict:
        """
        Generates a report of findings.
        """
        report = {
            "database_name": self.db_name,
            "repository_path": str(self.repo_path),
            "dry_run": self.dry_run,
            "remove_mode": self.remove,
            "findings": self.findings
        }
        return report

    def run(self) -> Dict:
        """
        Executes the tool's main logic: scan and optionally remove.
        """
        self.scan_repository()
        self.remove_references()
        return self.generate_report()

class HelmDecommissionTool(PostgreSQLDecommissionTool):
    """
    Extends PostgreSQLDecommissionTool to specifically handle Helm chart decommissioning.
    This includes identifying Helm releases and generating Helm-specific commands.
    """
    def __init__(self, repo_path: str, db_name: str, release_name: str, remove: bool = False, dry_run: bool = False):
        super().__init__(repo_path, db_name, remove, dry_run)
        self.release_name = release_name
        self.helm_findings: Dict = {}

    def scan_helm_charts(self) -> None:
        """
        Scans Helm chart files (values.yaml, templates/*.yaml) for database references.
        """
        logging.info(f"Scanning Helm charts for release '{self.release_name}' and DB '{self.db_name}'...")
        helm_chart_paths = []
        for path in self.repo_path.rglob('Chart.yaml'):
            chart_dir = path.parent
            if not self._is_excluded(chart_dir):
                helm_chart_paths.append(chart_dir)

        for chart_dir in helm_chart_paths:
            chart_name = chart_dir.name # Assuming chart directory name is the chart name
            values_file = chart_dir / 'values.yaml'
            templates_dir = chart_dir / 'templates'

            chart_findings = {}

            if values_file.exists():
                found_lines = self.scan_file(values_file)
                if found_lines:
                    chart_findings[str(values_file.relative_to(self.repo_path))] = found_lines

            if templates_dir.exists():
                for template_file in templates_dir.rglob('*.yaml'):
                    if template_file.is_file() and not self._is_excluded(template_file):
                        found_lines = self.scan_file(template_file)
                        if found_lines:
                            chart_findings[str(template_file.relative_to(self.repo_path))] = found_lines
            
            if chart_findings:
                self.helm_findings[chart_name] = chart_findings
        logging.info("Helm chart scan complete.")

    def generate_helm_commands(self) -> List[str]:
        """
        Generates Helm CLI commands for decommissioning based on findings.
        """
        commands = []
        if self.helm_findings:
            logging.info("Generating Helm decommissioning commands...")
            for chart_name in self.helm_findings:
                # Assuming the release name is directly tied to the chart or can be inferred
                # For simplicity, using the provided release_name, but in a real scenario,
                # you might need to parse Chart.yaml or other files for actual release names.
                commands.append(f"helm uninstall {self.release_name} --namespace {chart_name}")
                commands.append(f"helm delete {self.release_name} --purge") # --purge is deprecated in Helm 3, use uninstall
        return commands

    def run(self) -> Dict:
        """
        Executes the Helm tool's main logic: scan repository, scan helm charts, and optionally remove.
        """
        super().run() # Run the base class scanning and removal
        self.scan_helm_charts()
        
        report = self.generate_report() # Get the base report
        report["helm_release_name"] = self.release_name
        report["helm_chart_findings"] = self.helm_findings
        report["helm_decommission_commands"] = self.generate_helm_commands()
        return report

def main():
    # Configure logging to output to stdout
    logging.basicConfig(
        level=logging.INFO,
        format='%(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    parser = argparse.ArgumentParser(description="Decommission a PostgreSQL database from a repository.")
    parser.add_argument('repo_path', help="Path to the Git repository.")
    parser.add_argument('db_name', help="Name of the database to decommission.")
    parser.add_argument('--release-name', help="Helm release name to decommission (if applicable).")
    parser.add_argument('--remove', action='store_true', help="Remove references from files (DANGEROUS without --dry-run).")
    parser.add_argument('--dry-run', action='store_true', help="Perform a dry run without making actual changes.")
    parser.add_argument('--verbose', action='store_true', help="Enable verbose logging.")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.remove and not args.dry_run:
        logging.warning("\nWARNING: Running in --remove mode without --dry-run. This will make permanent changes.\n")
        confirm = input("Type 'yes' to proceed with permanent changes: ")
        if confirm.lower() != 'yes':
            logging.info("Operation cancelled by user.")
            sys.exit(0)

    repo_path_obj = Path(args.repo_path)
    if not repo_path_obj.exists() or not repo_path_obj.is_dir():
        logging.error(f"Error: The provided repository path '{args.repo_path}' does not exist or is not a directory.")
        sys.exit(1)

    if args.release_name:
        tool = HelmDecommissionTool(args.repo_path, args.db_name, args.release_name, args.remove, args.dry_run)
    else:
        tool = PostgreSQLDecommissionTool(args.repo_path, args.db_name, args.remove, args.dry_run)

    # Remove debug prints
    report = tool.run()

    logging.info("\n--- Decommissioning Report ---")
    logging.info(f"Database Name: {report['database_name']}")
    logging.info(f"Repository Path: {report['repository_path']}")
    logging.info(f"Dry Run: {report['dry_run']}")
    logging.info(f"Remove Mode: {report['remove_mode']}")
    
    # Add message when no changes are made in non-remove mode
    if not args.remove and not args.dry_run:
        logging.info("\nNo changes were made to files. Use --remove to make changes.")

    if report['findings']:
        logging.info("\nFound references:")
        for file, lines in report['findings'].items():
            logging.info(f"  File: {file}")
            for line_num, line_content in lines:
                logging.info(f"    Line {line_num}: {line_content}")
    else:
        logging.info("\nNo database references found in code/config files.")

    if 'helm_chart_findings' in report and report['helm_chart_findings']:
        logging.info("\nFound Helm chart references:")
        for chart, files in report['helm_chart_findings'].items():
            logging.info(f"  Chart: {chart}")
            for file, lines in files.items():
                logging.info(f"    File: {file}")
                for line_num, line_content in lines:
                    logging.info(f"      Line {line_num}: {line_content}")
    elif 'helm_chart_findings' in report:
        logging.info("\nNo Helm chart references found.")

    if 'helm_decommission_commands' in report and report['helm_decommission_commands']:
        logging.info("\nSuggested Helm Decommissioning Commands:")
        for cmd in report['helm_decommission_commands']:
            logging.info(f"  - {cmd}")

    if not args.dry_run and args.remove and (report['findings'] or ('helm_chart_findings' in report and report['helm_chart_findings'])):
        logging.info("\nReferences have been removed from files (if --remove was specified and not --dry-run).")
    elif args.dry_run:
        logging.info("\nThis was a dry run. No changes were made to files.")
    else:
        logging.info("\nNo changes were made to files.")

    logging.info("--- Report End ---")

def generate_summary_and_plan(repo_path: str, db_name: str) -> Dict[str, Any]:
    """
    Generate a summary of changes and a plan for removing database references.
    
    Args:
        repo_path: Path to the repository to scan
        db_name: Name of the database to decommission
        
    Returns:
        A dictionary containing the summary and plan
    """
    tool = PostgreSQLDecommissionTool(repo_path, db_name, remove=False, dry_run=True)
    tool.scan_repository()
    
    # Count the number of files with references
    file_count = len(tool.findings)
    total_refs = sum(len(lines) for lines in tool.findings.values())
    
    # Generate the summary
    summary = {
        'database_name': db_name,
        'repository_path': str(repo_path),
        'files_affected': file_count,
        'total_references': total_refs,
        'files': []
    }
    
    # Add details for each file
    for file_path, refs in tool.findings.items():
        summary['files'].append({
            'file_path': str(file_path),
            'reference_count': len(refs),
            'references': [
                {'line_number': line, 'content': content}
                for line, content in refs
            ]
        })
    
    # Generate the plan
    plan = {
        'steps': [
            {
                'action': 'remove_postgresql_dependency',
                'description': 'Remove PostgreSQL dependency from Chart.yaml',
                'impact': 'Removes the PostgreSQL chart dependency',
                'files_affected': ['charts/Chart.yaml']
            },
            {
                'action': 'remove_postgresql_config',
                'description': 'Remove PostgreSQL configuration from values.yaml',
                'impact': 'Removes PostgreSQL configuration values',
                'files_affected': ['charts/values.yaml']
            },
            {
                'action': 'remove_pvc',
                'description': 'Remove PostgreSQL PVC template',
                'impact': 'Deletes the PVC template file',
                'files_affected': ['charts/templates/pvc.yaml']
            },
            {
                'action': 'update_source_code',
                'description': 'Update source code to remove database references',
                'impact': 'Modifies source files to remove direct database references',
                'files_affected': [str(f) for f in tool.findings.keys() 
                                if str(f).endswith(tuple(tool.constraints['source_extensions']))]
            }
        ],
        'rollback_instructions': (
            'To rollback these changes, you will need to restore from git history.\n'
            '1. Check git status to see modified files\n'
            '2. For any modified files, you can restore them using:\n'
            '   git checkout -- <file>\n\n'
            '3. For deleted files, you can restore them using:\n'
            '   git checkout HEAD -- <file>\n\n'
            '4. If you have committed the changes, you can revert the commit:\n'
            '   git revert <commit-hash>'
        )
    }
    
    return {
        'summary': summary,
        'plan': plan,
        'recommendations': [
            'Review the changes in a test environment before applying to production.',
            'Ensure you have a backup of your repository before proceeding with removal.',
            'Test the application thoroughly after removing the database references.'
        ]
    }


if __name__ == "__main__":
    main()
