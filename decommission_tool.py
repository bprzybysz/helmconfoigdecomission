

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
