# PostgreSQL Decommissioning Scanner

A Python-based tool to scan a repository for references to a PostgreSQL database that needs to be decommissioned. It identifies dependencies in Helm charts, configuration values, Kubernetes resource templates, and source code.

This tool is designed to be run in a CI/CD pipeline to ensure all references are removed before deployment.

## Prerequisites

- Python 3.8+
- `uv` (for package management)

## Quickstart

1.  **Setup Development Environment**:
    This will install dependencies using `uv` and clone the target test repository (`cloudnative-pg`).
    ```
    make dev-setup
    ```

2.  **Run an End-to-End Scan**:
    This will scan the cloned `./cloudnative-pg` repository for references to a database named `postgres`.
    ```
    make e2e
    ```

3.  **Run a Custom Scan**:
    Scan the target repository for a specific database name.
    ```
    make scan-db DB_NAME=my_app_db
    ```
    The results, including a summary and detailed findings, will be printed to the console and saved to `decommission_findings.json`.

## Makefile Commands

- `make install`: Install all Python dependencies.
- `make dev-setup`: Prepare the full development environment.
- `make lint`: Run `ruff` and `mypy` to check code quality.
- `make format`: Format code with `black` and `ruff`.
- `make test`: Run unit tests located in the `tests/` directory.
- `make e2e`: Run a full E2E scan on the `./cloudnative-pg` repository.
- `make scan-db DB_NAME=<name>`: Run a scan for a custom database name.
- `make ci`: Simulate a CI pipeline run (lint, test, e2e).
- `make clean`: Remove generated files, virtual environments, and the cloned test repository.
