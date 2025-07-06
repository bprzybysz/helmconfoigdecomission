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
        Scans a single file for references to the database name.
        Returns a list of (line_number, line_content) where the database name was found.
        """
        found_lines = []
        try:
            content = file_path.read_text(encoding='utf-8')

            # Scan for db_name in all files, including YAMLs (for values.yaml,
            # etc.) and source files
            for i, line in enumerate(content.splitlines()):
                if re.search(r'\b' + re.escape(self.db_name) + r'\b', line):
                    found_lines.append((i + 1, line.strip()))
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

        if file_path.suffix in self.constraints['yaml_extensions']:
            try:
                with file_path.open('r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)

                modified = False
                if file_path.name == "Chart.yaml" and 'dependencies' in data:
                    logging.debug(f"Processing Chart.yaml: {relative_path}")
                    initial_len = len(data['dependencies'])
                    logging.debug(
                        f"Initial dependencies: {
                            data['dependencies']}")
                    data['dependencies'] = [
                    else:
                        removed_count += 1

                if removed_count > 0:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.writelines(new_lines)
                    logging.info(f"Removed references from {file_path.name}")
        except Exception as e:
            logging.error(f"Error processing file {file_path}: {e}")

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
                    with open(chart_yaml_path, 'w', encoding='utf-8') as f:
                        yaml.dump(chart_data, f, sort_keys=False)
                    logging.info(f"Removed PostgreSQL dependency from {chart_yaml_path.name}")
        except Exception as e:
            logging.error(f"Error removing Helm dependency from {chart_yaml_path}: {e}")

    def _remove_postgresql_config_from_values(self, values_yaml_path: Path):
        """
        Removes the PostgreSQL configuration block from values.yaml.
        """
        try:
            with open(values_yaml_path, 'r', encoding='utf-8') as f:
                values_data = yaml.safe_load(f)

            if values_data and 'postgresql' in values_data:
                del values_data['postgresql']
                with open(values_yaml_path, 'w', encoding='utf-8') as f:
                    yaml.dump(values_data, f, sort_keys=False)
                logging.info(f"Removed PostgreSQL configuration from {values_yaml_path.name}")
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

    # Create a Git branch context
    repo = GitRepository(args.repo_path)
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

        if not args.dry_run:
            print(
                f"\nChanges have been committed to branch '{branch_name}'. Please review and create a pull request.")
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
