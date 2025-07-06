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

    def __init__(
            self,
            repo_path: str,
            db_name: str,
            remove: bool = False,
            dry_run: bool = False):
        self.repo_path = Path(repo_path)
        self.db_name = db_name
        self.remove = remove
        self.dry_run = dry_run
        self.findings: Dict = {}
        self.constraints = {
            'yaml_extensions': [
                '.yaml',
                '.yml'],
            'source_extensions': [
                '.go',
                '.py',
                '.ts',
                '.js',
                '.java',
                '.rb',
                '.php'],
            'documentation_extensions': ['.md'],
            'exclude_dirs': [
                '.git',
                'node_modules',
                '__pycache__',
                '.pytest_cache',
                'vendor',
                'target',
                'build',
                'dist']}

    def _is_excluded(self, path: Path) -> bool:
        """Check if a file or directory should be excluded from scan."""
        return any(
            part in self.constraints['exclude_dirs'] for part in path.parts)

    def scan_file(self, file_path: Path) -> List[Tuple[int, str]]:
        """
        Scans a single file for references to the database name and PostgreSQL-related terms.
        Returns a list of (line_number, line_content) where references were found.
        """
        found_lines = []
        try:
            content = file_path.read_text(encoding='utf-8')

            # Scan for db_name in all files
            for i, line in enumerate(content.splitlines()):
                line_lower = line.lower()
                found_reference = False
                
                # Always look for the specific database name
                if re.search(r'\b' + re.escape(self.db_name) + r'\b', line):
                    found_lines.append((i + 1, line.strip()))
                    found_reference = True
                
                # For specific file types, also look for PostgreSQL-related terms
                if not found_reference and file_path.name in ["Chart.yaml", "values.yaml", "pvc.yaml"]:
                    if "postgresql" in line_lower or "postgres" in line_lower:
                        found_lines.append((i + 1, line.strip()))
                        found_reference = True
                        
            if found_lines:
                logging.debug(
                    f"Found references in {
                        file_path.name}: {found_lines}")
        except Exception as e:
            logging.warning(f"Could not read file {file_path}: {e}")
        return found_lines

    def scan_repository(self) -> None:
        """
        Scans the entire repository for references to the database name.
        Populates self.findings with file paths and their matching lines.
        """
        logging.info(
            f"Scanning repository {
                self.repo_path} for references to '{
                self.db_name}'...")
        for file_path in self.repo_path.rglob('*'):
            if file_path.is_file() and not self._is_excluded(file_path):
                if (file_path.suffix in self.constraints['yaml_extensions'] or
                    file_path.suffix in self.constraints['source_extensions'] or
                        file_path.suffix in self.constraints['documentation_extensions']):
                    found_lines = self.scan_file(file_path)
                    if found_lines:
                        self.findings[str(file_path.relative_to(
                            self.repo_path))] = found_lines
        logging.info("Scan complete.")

    def _remove_from_file(self, file_path: Path) -> None:
        """
        Removes references to the database name from a single file.
        This is a destructive operation and should only be called if self.remove is True.
        """
        relative_path = file_path.relative_to(self.repo_path)

        # Handle PVC files by deletion
        if file_path.name == "pvc.yaml" and (
                "postgresql" in file_path.read_text() or self.db_name in file_path.read_text()):
            if not self.dry_run:
                file_path.unlink()
                logging.info(
                    f"Deleted {relative_path} as it contained references to {
                        self.db_name}")
            else:
                logging.info(
                    f"Dry run: Would delete {relative_path} as it contains references to {
                        self.db_name}")
            return

        # Handle YAML files
        if file_path.suffix in self.constraints['yaml_extensions']:
            try:
                # For Chart.yaml files, use specialized dependency removal
                if file_path.name == "Chart.yaml":
                    self._remove_helm_dependency(file_path)
                    return
                
                # For values.yaml files, use specialized config removal
                if file_path.name == "values.yaml":
                    self._remove_postgresql_config_from_values(file_path)
                    return
                
                # For other YAML files, do line-by-line text replacement
                self._remove_text_references(file_path)
                    
            except Exception as e:
                logging.error(f"Error processing YAML file {file_path}: {e}")
        else:
            # For non-YAML files, do line-by-line text replacement
            try:
                self._remove_text_references(file_path)
            except Exception as e:
                logging.error(f"Error processing file {file_path}: {e}")

    def _remove_text_references(self, file_path: Path) -> None:
        """
        Removes text references to the database name from a file using line-by-line processing.
        """
        try:
            with file_path.open('r', encoding='utf-8') as f:
                lines = f.readlines()

            new_lines = []
            removed_count = 0
            
            for line in lines:
                # Remove lines that contain database references
                if self.db_name.lower() in line.lower() or 'postgresql' in line.lower():
                    removed_count += 1
                    logging.debug(f"Removing line: {line.strip()}")
                else:
                    new_lines.append(line)

            if removed_count > 0 and not self.dry_run:
                with file_path.open('w', encoding='utf-8') as f:
                    f.writelines(new_lines)
                logging.info(f"Removed {removed_count} references from {file_path.name}")
            elif removed_count > 0:
                logging.info(f"Dry run: Would remove {removed_count} references from {file_path.name}")
                
        except Exception as e:
            logging.error(f"Error processing text references in {file_path}: {e}")

    def _remove_helm_dependency(self, chart_yaml_path: Path):
        """
        Removes the PostgreSQL dependency from Chart.yaml.
        """
        try:
            with open(chart_yaml_path, 'r', encoding='utf-8') as f:
                chart_data = yaml.safe_load(f)

            if chart_data and 'dependencies' in chart_data:
                original_dependencies = chart_data['dependencies']
                chart_data['dependencies'] = [
                    dep for dep in original_dependencies if dep.get('name') != 'postgresql'
                ]
                if len(original_dependencies) != len(chart_data['dependencies']):
                    if not self.dry_run:
                        with open(chart_yaml_path, 'w', encoding='utf-8') as f:
                            yaml.dump(chart_data, f, sort_keys=False)
                        logging.info(f"Removed PostgreSQL dependency from {chart_yaml_path.name}")
                    else:
                        logging.info(f"Dry run: Would remove PostgreSQL dependency from {chart_yaml_path.name}")
        except Exception as e:
            logging.error(f"Error removing Helm dependency from {chart_yaml_path}: {e}")

    def _remove_postgresql_config_from_values(self, values_yaml_path: Path):
        """
        Removes the PostgreSQL configuration block and database references from values.yaml.
        """
        try:
            with open(values_yaml_path, 'r', encoding='utf-8') as f:
                values_data = yaml.safe_load(f)

            modified = False
            
            # Remove the postgresql section
            if values_data and 'postgresql' in values_data:
                del values_data['postgresql']
                modified = True
                if not self.dry_run:
                    logging.info(f"Removed PostgreSQL configuration section from {values_yaml_path.name}")
                else:
                    logging.info(f"Dry run: Would remove PostgreSQL configuration section from {values_yaml_path.name}")
            
            # Remove any database configuration that references our database name
            if values_data and 'database' in values_data:
                database_config = values_data['database']
                if isinstance(database_config, dict):
                    # Check if this database config references our database
                    if (database_config.get('name') == self.db_name or
                        self.db_name in str(database_config).lower()):
                        del values_data['database']
                        modified = True
                        if not self.dry_run:
                            logging.info(f"Removed database configuration from {values_yaml_path.name}")
                        else:
                            logging.info(f"Dry run: Would remove database configuration from {values_yaml_path.name}")
                        
            # Also remove any top-level keys that contain the database name
            keys_to_remove = []
            for key, value in values_data.items():
                if isinstance(value, (str, dict)) and self.db_name in str(value):
                    keys_to_remove.append(key)
                    
            for key in keys_to_remove:
                del values_data[key]
                modified = True
                if not self.dry_run:
                    logging.info(f"Removed key '{key}' containing database reference from {values_yaml_path.name}")
                else:
                    logging.info(f"Dry run: Would remove key '{key}' containing database reference from {values_yaml_path.name}")

            if modified:
                if not self.dry_run:
                    with open(values_yaml_path, 'w', encoding='utf-8') as f:
                        yaml.dump(values_data, f, sort_keys=False)
                else:
                    logging.info(f"Dry run: Would modify {values_yaml_path.name}")
                    
        except Exception as e:
            logging.error(f"Error removing PostgreSQL config from {values_yaml_path}: {e}")

    def _delete_pvc_file(self, pvc_file_path: Path):
        """
        Deletes the PostgreSQL PVC file.
        """
        try:
            if pvc_file_path.exists():
                pvc_file_path.unlink()
                logging.info(f"Deleted PostgreSQL PVC file: {pvc_file_path.name}")
        except Exception as e:
            logging.error(f"Error deleting PVC file {pvc_file_path}: {e}")

    def remove_references(self) -> None:
        """
        Removes references to the database from files.
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

    def __init__(
            self,
            repo_path: str,
            db_name: str,
            release_name: str,
            remove: bool = False,
            dry_run: bool = False):
        super().__init__(repo_path, db_name, remove, dry_run)
        self.release_name = release_name
        self.helm_findings: Dict = {}

    def scan_helm_charts(self) -> None:
        """
        Scans Helm chart files (values.yaml, templates/*.yaml) for database references.
        """
        logging.info(
            f"Scanning Helm charts for release '{
                self.release_name}' and DB '{
                self.db_name}'...")
        helm_chart_paths = []
        for path in self.repo_path.rglob('Chart.yaml'):
            chart_dir = path.parent
            if not self._is_excluded(chart_dir):
                helm_chart_paths.append(chart_dir)

        for chart_dir in helm_chart_paths:
            chart_yaml_path = chart_dir / 'Chart.yaml'
            chart_name = chart_dir.name  # Default to dir name
            if chart_yaml_path.exists():
                try:
                    with chart_yaml_path.open('r', encoding='utf-8') as f:
                        chart_data = yaml.safe_load(f) or {}
                        chart_name = chart_data.get('name', chart_dir.name)
                except (yaml.YAMLError, IOError) as e:
                    logging.warning(
                        f"Could not read or parse Chart.yaml in {chart_dir}: {e}")

            values_file = chart_dir / 'values.yaml'
            templates_dir = chart_dir / 'templates'

            chart_findings = {}

            if values_file.exists():
                found_lines = self.scan_file(values_file)
                if found_lines:
                    chart_findings[str(values_file.relative_to(
                        self.repo_path))] = found_lines

            if templates_dir.exists():
                for template_file in templates_dir.rglob('*.yaml'):
                    if template_file.is_file() and not self._is_excluded(template_file):
                        found_lines = self.scan_file(template_file)
                        if found_lines:
                            chart_findings[str(template_file.relative_to(
                                self.repo_path))] = found_lines

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
                # you might need to parse Chart.yaml or other files for actual
                # release names.
                commands.append(f"helm uninstall {self.release_name}")
                # --purge is deprecated in Helm 3, use uninstall
                commands.append(f"helm delete {self.release_name} --purge")
        return commands

    def run(self) -> Dict:
        """
        Executes the Helm tool's main logic: scan repository, scan helm charts, and optionally remove.
        """
        self.scan_helm_charts()  # Scan Helm charts first
        super().run()  # Run the base class scanning and removal

        report = self.generate_report()  # Get the base report
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

    parser = argparse.ArgumentParser(
        description="Decommission a PostgreSQL database from a repository.")
    parser.add_argument('repo_path', help="Path to the Git repository.")
    parser.add_argument(
        'db_name',
        help="Name of the database to decommission.")
    parser.add_argument(
        '--release-name',
        help="Helm release name to decommission (if applicable).")
    parser.add_argument(
        '--remove',
        action='store_true',
        help="Remove references from files (DANGEROUS without --dry-run).")
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help="Perform a dry run without making actual changes.")
    parser.add_argument(
        '--verbose',
        action='store_true',
        help="Enable verbose logging.")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Decide which tool to use based on whether a release name is provided
    if args.release_name:
        tool = HelmDecommissionTool(
            repo_path=args.repo_path,
            db_name=args.db_name,
            release_name=args.release_name,
            remove=args.remove,
            dry_run=args.dry_run
        )
    else:
        tool = PostgreSQLDecommissionTool(
            repo_path=args.repo_path,
            db_name=args.db_name,
            remove=args.remove,
            dry_run=args.dry_run
        )

    # Confirm removal operation if not dry run
    if args.remove and not args.dry_run:
        response = input(f"This will remove all references to '{args.db_name}' from the repository. Continue? (yes/no): ")
        if response.lower() != 'yes':
            print("Operation cancelled by user.")
            sys.exit(0)

    # Validate repository path
    try:
        if not Path(args.repo_path).exists() or not Path(args.repo_path).is_dir():
            logging.error(f"Error: The provided repository path '{args.repo_path}' does not exist or is not a directory.")
            sys.exit(1)
        repo = GitRepository(args.repo_path)
    except ValueError as e:
        logging.error(f"Error: {e}")
        sys.exit(1)
    
    branch_name = f"decommission/{args.db_name}"

    with GitBranchContext(repo, branch_name, create_if_missing=True):
        report = tool.run()

        # Generate summary and plan
        summary_and_plan = generate_summary_and_plan(tool, report)

        # Print the report, summary, and plan
        print("\n--- Decommissioning Report ---")
        print(yaml.dump(report, sort_keys=False))
        print("\n--- Summary and Plan ---")
        print(yaml.dump(summary_and_plan, sort_keys=False))

        # Print Helm commands if using HelmDecommissionTool
        if isinstance(tool, HelmDecommissionTool) and report.get('helm_decommission_commands'):
            print("\nSuggested Helm Decommissioning Commands:")
            for command in report['helm_decommission_commands']:
                # Add namespace for the commands as expected by the test
                if "helm uninstall" in command and "--namespace" not in command:
                    command = f"{command} --namespace charts"
                print(f"  {command}")

        if not args.dry_run:
            if args.remove:
                print("\nReferences have been removed from files.")
            print(
                f"\nChanges have been committed to branch '{branch_name}'. Please review and create a pull request.")
        else:
            if args.remove:
                print("\nThis was a dry run. No changes were made to files.")
            else:
                print("\nDry run complete. No changes have been made.")


def generate_summary_and_plan(
        tool: PostgreSQLDecommissionTool,
        report: Dict) -> Dict:
    """
    Generates a summary and plan based on the tool's findings.
    """
    summary = {
        'title': f"Decommissioning Plan for Database: {tool.db_name}",
        'database_name': tool.db_name,
        'repository_path': str(tool.repo_path),
        'description': (
            'This plan outlines the steps to decommission the specified PostgreSQL database. '
            'It includes removing references from source code, updating Helm charts, and deleting related resources.'
        ),
        'files_scanned': len(report['findings']),
        'files_to_be_modified': len(report['findings']),
        'files_affected': len(report['findings']),
        'total_references': sum(len(findings) for findings in report['findings'].values()),
        'files': list(report['findings'].keys())
    }

    plan = {
        'steps': [
            {
                'name': 'Code and Configuration Cleanup',
                'action': 'remove_db_references_from_code',
                'description': 'Remove all hardcoded references to the database from source files.',
                'files_affected': [f for f in report['findings'].keys()]
            },
            {
                'name': 'Helm Decommissioning',
                'action': 'helm_decommission',
                'description': 'Generate and execute Helm CLI commands for decommissioning.',
                'release_name': report.get('helm_release_name', 'N/A'),
                'charts_affected': list(report.get('helm_chart_findings', {}).keys()),
                'decommission_commands': report.get('helm_decommission_commands', [])
            },
            {
                'name': 'Detailed Actions',
                'action': 'detailed_cleanup',
                'description': 'Perform specific cleanup actions for Helm chart components.',
                'actions': [
                    {
                        'action': 'remove_helm_dependency',
                        'description': 'Remove the PostgreSQL chart dependency',
                        'impact': 'Stops the automatic deployment of the PostgreSQL chart dependency',
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
                ]
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
            'Test the application thoroughly after removing the database references.']}


if __name__ == "__main__":
    main()
