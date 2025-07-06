import os
import re
import sys
import json
import yaml
from pathlib import Path
from typing import List, Dict

class PostgreSQLDecommissionTool:
    def __init__(self, repo_path: str, db_name: str, max_findings: int = 100):
        self.repo_path = Path(repo_path)
        self.db_name = db_name
        self.max_findings = max_findings
        self.constraints = {
            'yaml_extensions': ['.yaml', '.yml', '.tpl'],
            'config_extensions': ['.conf', '.env'],
            'source_extensions': ['.go', '.py', '.ts', '.js'],
            'max_file_size': 10 * 1024 * 1024,  # 10MB limit
            'exclude_dirs': ['.git', 'node_modules', '__pycache__', '.pytest_cache', 'vendor']
        }

    def scan_repository(self) -> Dict[str, List]:
        """Scan for all PostgreSQL references with constraints"""
        if not self.repo_path.is_dir():
            raise FileNotFoundError(f"Repository path does not exist or is not a directory: {self.repo_path}")

        all_files = [p for p in self.repo_path.rglob('*') if p.is_file() and self._is_valid_path(p)]
        
        findings = {
            'helm_dependencies': [],
            'config_references': [],
            'template_resources': [],
            'pvc_references': [],
            'source_code_references': []
        }

        for file_path in all_files:
            # Scan for config references if it's a values.yaml or a recognized config extension
            if file_path.name == 'values.yaml' or file_path.suffix in self.constraints['config_extensions']:
                findings['config_references'].extend(self._scan_config_file(file_path))
            
            # Scan for Helm, PVC, and template resources if it's a YAML file
            if file_path.suffix in self.constraints['yaml_extensions']:
                findings['helm_dependencies'].extend(self._scan_helm_chart(file_path))
                findings['pvc_references'].extend(self._scan_pvc(file_path))
                findings['template_resources'].extend(self._scan_template(file_path))
            
            # Scan for source code references
            if file_path.suffix in self.constraints['source_extensions']:
                findings['source_code_references'].extend(self._scan_source_code(file_path))
        
        # Apply max findings constraint to each category
        for key in findings:
            findings[key] = findings[key][:self.max_findings]
        
        return findings

    def _is_valid_path(self, file_path: Path) -> bool:
        """Check if a file path is valid against constraints."""
        if file_path.stat().st_size > self.constraints['max_file_size']:
            return False
        if any(excluded in file_path.parts for excluded in self.constraints['exclude_dirs']):
            return False
        return True

    def _scan_helm_chart(self, file_path: Path) -> List[Dict]:
        """Scan a single Chart.yaml or requirements.yaml file."""
        findings = []
        if file_path.name not in ['Chart.yaml', 'requirements.yaml']:
            return findings
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = yaml.safe_load(f)
            if not content or 'dependencies' not in content:
                return findings

            for dep in content['dependencies']:
                name = dep.get('name', '').lower()
                if 'postgres' in name or self.db_name in name:
                    findings.append({'file': str(file_path.relative_to(self.repo_path)), 'type': 'helm_dependency', 'content': dep, 'severity': 'high'})
        except (yaml.YAMLError, IOError) as e:
            print(f"Warning: Could not process {file_path}: {e}", file=sys.stderr)
        return findings

    def _scan_config_file(self, file_path: Path) -> List[Dict]:
        """Scan config files like values.yaml, .env, .conf."""
        findings = []
        patterns = [rf'\b{self.db_name}\b', r'POSTGRES_DB', r'POSTGRES_USER', r'PGPASSWORD', r'DATABASE_URL']
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for i, line in enumerate(f, 1):
                    if any(re.search(p, line, re.IGNORECASE) for p in patterns):
                        findings.append({'file': str(file_path.relative_to(self.repo_path)), 'line': i, 'type': 'config_reference', 'content': line.strip()[:200], 'severity': 'medium'})
        except IOError as e:
            print(f"Warning: Could not read {file_path}: {e}", file=sys.stderr)
        return findings
    
    def _scan_template(self, file_path: Path) -> List[Dict]:
        """Scan a generic Kubernetes YAML/template file for resource references."""
        findings = []
        patterns = [r'image:.*postgres', r'kind:\s*(StatefulSet|Deployment)', rf'\b{self.db_name}\b']
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            if any(re.search(p, content, re.IGNORECASE) for p in patterns):
                findings.append({'file': str(file_path.relative_to(self.repo_path)), 'type': 'template_resource', 'content': 'Potential PostgreSQL resource definition', 'severity': 'high'})
        except IOError as e:
            print(f"Warning: Could not read {file_path}: {e}", file=sys.stderr)
        return findings

    def _scan_pvc(self, file_path: Path) -> List[Dict]:
        """Scan a YAML file specifically for PersistentVolumeClaims related to PostgreSQL."""
        findings = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                docs = yaml.safe_load_all(f)
            for doc in docs:
                # Ensure doc is a dictionary before proceeding
                if not isinstance(doc, dict) or doc.get('kind') != 'PersistentVolumeClaim':
                    continue
                    
                name = doc.get('metadata', {}).get('name', '').lower()
                labels = doc.get('metadata', {}).get('labels', {})
                # Simple check if 'postgres' or db_name is in the PVC name or a common label
                if 'postgres' in name or self.db_name in name or 'postgres' in str(labels):
                    findings.append({'file': str(file_path.relative_to(self.repo_path)), 'type': 'pvc_reference', 'content': f"PVC found: {name}", 'severity': 'critical'})
        except (yaml.YAMLError, IOError) as e:
            print(f"Warning: Could not process {file_path} for PVCs: {e}", file=sys.stderr)
        return findings

    def _scan_source_code(self, file_path: Path) -> List[Dict]:
        """Scan source code files for hardcoded DSNs."""
        findings = []
        # Pattern for postgres://user:pass@host:port/dbname
        dsn_pattern = r'postgres(ql)?:\/\/[^\s"]+'
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for i, line in enumerate(f, 1):
                    if re.search(dsn_pattern, line, re.IGNORECASE):
                        findings.append({'file': str(file_path.relative_to(self.repo_path)), 'line': i, 'type': 'source_code_reference', 'content': line.strip()[:200], 'severity': 'high'})
        except IOError as e:
            print(f"Warning: Could not read {file_path}: {e}", file=sys.stderr)
        return findings

def generate_summary_and_plan(findings: Dict[str, List], repo_path: str) -> Dict:
    """Generate a summary and print a removal plan."""
    total_refs = sum(len(refs) for refs in findings.values())
    severity_counts = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0}
    files_affected = set()

    for category, find_list in findings.items():
        for finding in find_list:
            severity = finding.get('severity', 'low')
            severity_counts[severity] += 1
            files_affected.add(finding['file'])
    
    summary = {
        'total_references': total_refs,
        'severity_breakdown': severity_counts,
        'files_affected': len(files_affected)
    }

    print("--- PostgreSQL Decommissioning Plan ---")
    print(f"Target Repository: {repo_path}")
    print(f"Total References Found: {summary['total_references']}")
    print(f"Unique Files Affected: {summary['files_affected']}")
    print("\n**Severity Breakdown:**")
    for severity, count in summary['severity_breakdown'].items():
        if count > 0:
            print(f"- {severity.upper()}: {count}")

    if findings['pvc_references']:
        print("\n**Step 1: Handle Persistent Volumes (CRITICAL)**")
        print("- ⚠️  BACKUP DATA BEFORE PROCEEDING. Review PVC retention policies.")
        for item in findings['pvc_references'][:5]:
            print(f"- Review PVC in: {item['file']} ({item['content']})")

    if findings['helm_dependencies'] or findings['template_resources'] or findings['source_code_references']:
        print("\n**Step 2: Remove High-Severity References (HIGH)**")
        for item in findings['helm_dependencies'][:5]:
            print(f"- Remove Helm dependency from: {item['file']}")
        for item in findings['template_resources'][:5]:
            print(f"- Review template resource in: {item['file']}")
        for item in findings['source_code_references'][:5]:
            print(f"- Remove hardcoded DSN from: {item['file']}:{item['line']}")

    if findings['config_references']:
        print("\n**Step 3: Clean Configuration (MEDIUM)**")
        for item in findings['config_references'][:5]:
            print(f"- Update config in: {item['file']}:{item['line']}")
    
    print("--- End of Plan ---")
    return summary

def main():
    if len(sys.argv) < 3:
        print("Usage: python decommission_tool.py <repo_path> <db_name>", file=sys.stderr)
        sys.exit(1)
        
    repo_path = sys.argv[1]
    db_name = sys.argv[2]
    output_file = Path("decommission_findings.json")

    try:
        tool = PostgreSQLDecommissionTool(repo_path, db_name)
        findings = tool.scan_repository()
        summary = generate_summary_and_plan(findings, repo_path)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({'summary': summary, 'findings': findings}, f, indent=2)
        
        print(f"\n📄 Detailed findings exported to: {output_file}")

        # Exit with non-zero status if critical issues are found for CI
        if summary['severity_breakdown']['critical'] > 0:
            print("\n❌ Critical findings detected. Exiting with error code.", file=sys.stderr)
            sys.exit(2)

    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
