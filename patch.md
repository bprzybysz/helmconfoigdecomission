import os
import re
import yaml
from pathlib import Path
from typing import List, Dict, Set

class PostgreSQLDecommissionTool:
    def __init__(self, repo_path: str, db_name: str):
        self.repo_path = Path(repo_path)
        self.db_name = db_name
        self.findings = []
        
    def scan_repository(self) -> Dict[str, List]:
        """Scan for PostgreSQL references using proven patterns"""
        patterns = {
            'helm_dependencies': self._scan_helm_dependencies(),
            'config_references': self._scan_config_files(),
            'template_resources': self._scan_template_files(),
            'persistent_volumes': self._scan_pvc_references()
        }
        return patterns
    
    def _scan_helm_dependencies(self) -> List[Dict]:
        """Scan Chart.yaml and requirements.yaml for PostgreSQL dependencies"""
        findings = []
        chart_files = list(self.repo_path.glob("**/Chart.yaml")) + \
                     list(self.repo_path.glob("**/requirements.yaml"))
        
        for file_path in chart_files:
            try:
                with open(file_path, 'r') as f:
                    content = yaml.safe_load(f)
                    
                # Check dependencies section
                if 'dependencies' in content:
                    for dep in content['dependencies']:
                        if ('postgresql' in dep.get('name', '').lower() or 
                            'postgres' in dep.get('name', '').lower() or
                            self.db_name in dep.get('name', '')):
                            findings.append({
                                'file': str(file_path),
                                'type': 'helm_dependency',
                                'content': dep
                            })
            except Exception as e:
                print(f"Error reading {file_path}: {e}")
        
        return findings
    
    def _scan_config_files(self) -> List[Dict]:
        """Scan values.yaml and config files for PostgreSQL configuration"""
        findings = []
        config_files = list(self.repo_path.glob("**/values.yaml")) + \
                      list(self.repo_path.glob("**/config/*.yaml"))
        
        search_patterns = [
            rf'\bpostgresql\b',
            rf'\bpostgres\b',
            rf'\b{self.db_name}\b',
            r'POSTGRES_',
            r'DATABASE_URL'
        ]
        
        for file_path in config_files:
            try:
                with open(file_path, 'r') as f:
                    content = f.read()
                    
                for i, line in enumerate(content.split('\n'), 1):
                    for pattern in search_patterns:
                        if re.search(pattern, line, re.IGNORECASE):
                            findings.append({
                                'file': str(file_path),
                                'line': i,
                                'type': 'config_reference',
                                'content': line.strip()
                            })
            except Exception as e:
                print(f"Error reading {file_path}: {e}")
        
        return findings
    
    def _scan_template_files(self) -> List[Dict]:
        """Scan Helm templates for PostgreSQL resources"""
        findings = []
        template_files = list(self.repo_path.glob("**/templates/*.yaml"))
        
        resource_patterns = [
            r'kind:\s*(StatefulSet|Deployment|Service)',
            r'postgresql',
            r'postgres',
            rf'{self.db_name}'
        ]
        
        for file_path in template_files:
            try:
                with open(file_path, 'r') as f:
                    content = f.read()
                    
                # Check if file contains PostgreSQL resources
                has_postgres_ref = any(re.search(pattern, content, re.IGNORECASE) 
                                     for pattern in resource_patterns[1:])
                
                if has_postgres_ref:
                    findings.append({
                        'file': str(file_path),
                        'type': 'template_resource',
                        'content': 'PostgreSQL resource template'
                    })
            except Exception as e:
                print(f"Error reading {file_path}: {e}")
        
        return findings
    
    def _scan_pvc_references(self) -> List[Dict]:
        """Scan for PersistentVolumeClaim references"""
        findings = []
        all_yaml_files = list(self.repo_path.glob("**/*.yaml"))
        
        for file_path in all_yaml_files:
            try:
                with open(file_path, 'r') as f:
                    content = f.read()
                    
                # Look for PVC patterns
                pvc_patterns = [
                    r'kind:\s*PersistentVolumeClaim',
                    rf'postgres.*{self.db_name}',
                    r'volumeClaimTemplates'
                ]
                
                for pattern in pvc_patterns:
                    if re.search(pattern, content, re.IGNORECASE):
                        findings.append({
                            'file': str(file_path),
                            'type': 'pvc_reference',
                            'content': 'PVC reference found'
                        })
                        break
            except Exception as e:
                print(f"Error reading {file_path}: {e}")
        
        return findings

def generate_removal_plan(findings: Dict[str, List]) -> None:
    """Generate step-by-step removal plan based on proven patterns"""
    print("## PostgreSQL Decommissioning Plan")
    print("### Based on proven patterns from Eclipse Che and Crunchy Data")
    
    # Step 1: Dependencies
    if findings['helm_dependencies']:
        print("\n**Step 1: Remove Helm Dependencies**")
        for item in findings['helm_dependencies']:
            print(f"- Remove from {item['file']}: {item['content']['name']}")
    
    # Step 2: Resources (following Crunchy Data pattern)
    if findings['template_resources']:
        print("\n**Step 2: Remove Template Resources**")
        print("- Delete PostgreSQL StatefulSets, Deployments, Services")
        for item in findings['template_resources']:
            print(f"- Clean up {item['file']}")
    
    # Step 3: PVCs (with retention policy consideration)
    if findings['persistent_volumes']:
        print("\n**Step 3: Handle Persistent Volumes**")
        print("- Review PVC retention policy")
        print("- Backup data if needed")
        for item in findings['persistent_volumes']:
            print(f"- Handle PVC in {item['file']}")
    
    # Step 4: Configuration cleanup
    if findings['config_references']:
        print("\n**Step 4: Clean Configuration**")
        print("- Remove PostgreSQL configuration blocks")
        for item in findings['config_references']:
            print(f"- Update {item['file']}:{item.get('line', 'N/A')}")

# Usage
def main(repo_path: str, db_name: str):
    tool = PostgreSQLDecommissionTool(repo_path, db_name)
    findings = tool.scan_repository()
    generate_removal_plan(findings)
    
    # Summary
    total_refs = sum(len(refs) for refs in findings.values())
    print(f"\n**Total References Found: {total_refs}**")

# Example usage
# main('<repoPath>', 'decommissioned_db')
