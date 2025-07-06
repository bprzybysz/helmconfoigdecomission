# Error Report & Troubleshooting (generated 2025-07-06)

## Error Context
Below are the key failures from the latest pytest run (``pytest tests/test_decommission_tool.py tests/test_file_system_mcp_server.py tests/test_remove_functionality.py -v``):

| Test | Exception / Assertion |
|------|-----------------------|
| `TestHelmDecommissionTool.test_helm_tool_run` | `AssertionError: assert 'my-app' in {}` – `HelmDecommissionTool.helm_findings` returned an empty dict, expected key `'my-app'`. |
| `TestMainFunction.test_main_no_remove_no_dry_run` | `ValueError: Branch 'decommission/my-test-db' does not exist and create_if_missing is False` |
| `TestMainFunction.test_main_remove_actual_confirmed` | Same `ValueError` as above |
| `TestMainFunction.test_main_remove_actual_cancelled` | Same `ValueError` as above |
| `TestMainFunction.test_main_helm_decommission` | `AssertionError` – expected decommission suggestions string in output, but git branch deletion failed (same underlying branch error). |
| `TestMainFunction.test_main_invalid_repo_path` | `ValueError: The provided path '/path/to/nonexistent/repo' is not a valid Git repository.` |
| `test_remove_postgres_references` | Final assertion failed – Postgres references were **not** removed as expected (`assert not True`). |
| `test_generate_summary_and_plan` | `KeyError: 'steps'` – the plan dict contains key `stages`, test expects top-level key `steps`. |

Additional log excerpt:
```
INFO Scanning Helm charts for release 'my-release' and DB 'my-test-db'...
INFO Helm chart scan complete.
ERROR Git command failed: branch -D decommission/my-test-db
Stdout: 
Stderr: error: branch 'decommission/my-test-db' not found.
```

### Relevant Code Snippets
1. **HelmDecommissionTool.scan_helm_charts** (lines 298-346):
```python
for chart_dir in helm_chart_paths:
    chart_yaml_path = chart_dir / 'Chart.yaml'
    chart_name = chart_dir.name  # Default to dir name
    if chart_yaml_path.exists():
        with chart_yaml_path.open('r') as f:
            chart_data = yaml.safe_load(f)
            if 'name' in chart_data:
                chart_name = chart_data['name']
    ...
    if chart_findings:
        self.helm_findings[chart_name] = chart_findings
```

2. **generate_summary_and_plan** (excerpt):
```python
summary = {
    'database_name': tool.db_name,
    ...
}
plan = {
    'stages': [
        { 'name': 'Code and Configuration Cleanup', 'steps': [...] }
    ],
    ...
}
```

3. **GitRepository._run_git_command** (excerpt):
```python
result = subprocess.run(["git"] + command, cwd=self.repo_path, check=True, ...)
```
The branch deletion error surfaces here when the branch does not exist.

---

## Perplexity Troubleshooting Suggestions

The following remediation advice was generated via Perplexity (@resources:perplexity-ask):

> **1. Fix missing `'my-app'` in `helm_findings`**  
> Parse `Chart.yaml` and use its `name` field as the key:
> ```python
> with chart_yaml_path.open() as f:
>     chart_yaml = yaml.safe_load(f)
> chart_name = chart_yaml.get('name', chart_dir.name)
> ```
>
> **2. KeyError `'steps'`**  
> Align structure: either expose `plan['steps']` top-level, or update tests. Easiest: change code to:
> ```python
> plan = {
>     'steps': [...],
>     ...
> }
> ```
>
> **3. Branch missing ValueErrors**  
> In tests, create the branch beforehand or in code allow `create_if_missing=True`.
>
> **4. Postgres reference removal test**  
> Ensure test asserts for absence of references after removal OR debug removal logic.

These targeted changes should clear the remaining eight failures.
