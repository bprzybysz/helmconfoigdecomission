# 📊 Python Code Quality Best Practices & Rules

## 🎯 Tool Roles and Principles

### Black (Auto-formatting)
- Automates code formatting for PEP 8 compliance.
- Reduces style debates and speeds up code reviews.
- Produces uniform, deterministic diffs.

### Ruff (Linting)
- High-performance, extensible linter.
- Covers PEP 8, naming conventions, import conventions, and other static checks.
- Can autofix many issues.

### Mypy (Static Type Checking)
- Brings static type checking to Python using type hints.
- Enables early bug detection and improves code safety.

## 🔧 Configuration Recommendations

### Centralize Configuration in `pyproject.toml`
```toml
# pyproject.toml
[tool.black]
line-length = 100
target-version = ['py311']
skip-string-normalization = true

[tool.ruff]
line-length = 100
select = ["E", "F", "I"]  # Example: errors, flakes, imports
ignore = ["E501"]         # Example: ignore line-length if Black is responsible for formatting

[tool.mypy]
python_version = 3.11
warn_unused_configs = true
disallow_untyped_defs = true
```
- **Adjust settings:** Modify line length, target Python version, and enable/disable specific rules based on team workflow and codebase evolution.

## ⚙️ Integration with CI/CD and Developer Workflow

### Pre-commit Hooks
- Use `pre-commit` to automate Black, Ruff, and Mypy checks before every commit.
- Prevents non-compliant code from entering the codebase.

### CI/CD Pipelines
- Run all three tools as part of your build pipeline (e.g., GitHub Actions, GitLab CI) to enforce standards on all pushes and pull requests.
```yaml
# Example GitHub Actions steps
- name: Run Black
  run: black --check .
- name: Run Ruff
  run: ruff check .
- name: Run Mypy
  run: mypy .
```

### IDE Integration
- Enable extensions for Black and Ruff in your preferred IDE (VSCode, PyCharm) for real-time feedback and auto-formatting.

## 📈 Gradual Adoption Strategies (Existing Codebases)

- **Start Small:** Run tools on a limited scope (new code, touched files, specific submodules).
- **Incremental Opt-in (Mypy):** Gradually increase strictness (e.g., start with `warn_return_any`, then `disallow_untyped_defs`).
- **Selective Enforcement:** Use `per-file-ignores` (Ruff) or exclude problematic files until refactoring is feasible.
- **Progress Tracking:** Monitor codebase compliance over time with reports or CI warnings.

## ⚡ Performance Optimization

- **Ruff:** Designed for speed; leverage its autofix capabilities to minimize manual correction.
- **Black:** Can be targeted to changed files only for large projects.
- **Mypy:** Use `--incremental` flag or run only on changed files for faster checks.

## ⚠️ Handling Edge Cases

- **Ruff & Black Overlap:** Disable stylistic lint rules in Ruff that Black already covers (e.g., line-length) to reduce conflicts.
- **Project-Specific Exceptions:** Use `# noqa` (Ruff) or `# type: ignore` (Mypy) comments for false positives or unavoidable rule violations.
- **Third-Party Code:** Exclude vendored or auto-generated code directories using `exclude` settings.

## 🤝 Team Practices

- **Educate the team:** Ensure everyone understands the purpose of each tool and how to fix common issues.
- **Require passing checks:** Enforce all checks in CI for code merges.
- **Regularly revisit configurations:** Update tool versions to benefit from improvements.

## 📋 Code Quality Checklist

- [ ] `pyproject.toml` configured for Black, Ruff, and Mypy.
- [ ] Pre-commit hooks installed and configured.
- [ ] CI/CD pipeline runs all code quality checks.
- [ ] All new code passes linting, formatting, and type checks.
- [ ] Existing codebase gradually brought into compliance.
- [ ] No hardcoded secrets.
- [ ] Appropriate use of `# noqa` or `# type: ignore` comments for justified exceptions.
- [ ] All team members are aware of and follow code quality guidelines. 