# PostgreSQL Decommissioning Tool

A production-ready Python tool for identifying and removing PostgreSQL database references in Helm charts, Kubernetes resources, and application code. This tool helps ensure clean database decommissioning by scanning repositories and managing the removal of database references.

## Features

- Scans repositories for PostgreSQL database references
- Supports Helm charts, Kubernetes resources, and application code
- Dry-run mode for safe preview of changes
- Comprehensive reporting of found references
- Git integration for safe branch-based changes
- Containerized deployment option

## Prerequisites

- Python 3.11+
- Git 2.25+
- Docker 20.10+ (for containerized execution)

## Installation

### Local Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/decommission-tool.git
   cd decommission-tool
   ```

2. Set up the development environment:
   ```bash
   make dev-setup
   ```

### Container Installation

```bash
docker build -t decommission-tool .
```

## Usage

### Basic Usage

```bash
# Scan a repository for database references
python -m decommission_tool scan /path/to/repo --db-name my_database

# Scan with removal of references (dry-run by default)
python -m decommission_tool scan /path/to/repo --db-name my_database --remove

# Actually remove references (requires confirmation)
python -m decommission_tool scan /path/to/repo --db-name my_database --remove --no-dry-run
```

### Container Usage

```bash
# Scan using the container
docker run --rm -v /path/to/repo:/repo decommission-tool scan /repo --db-name my_database
```

### Command Line Options

```
usage: decommission_tool.py scan [-h] [--db-name DB_NAME] [--remove] [--dry-run/--no-dry-run] [--output OUTPUT] [--verbose] repo_path

Scan a repository for PostgreSQL database references.

positional arguments:
  repo_path            Path to the repository to scan

options:
  -h, --help           show this help message and exit
  --db-name DB_NAME    Name of the database to search for
  --remove             Remove found references (dry-run by default)
  --dry-run/--no-dry-run
                       Show what would be changed without making changes (default: --dry-run)
  --output OUTPUT      Output file for scan results (default: decommission_report.json)
  --verbose            Enable verbose output
```

## Development

### Setting Up Development Environment

```bash
make dev-setup  # Sets up pre-commit hooks and installs dev dependencies
```

### Running Tests

```bash
make test          # Run all tests
make test-unit     # Run unit tests
make test-e2e      # Run end-to-end tests
make test-coverage # Run tests with coverage report
```

### Code Quality

```bash
make format    # Format code with Black and isort
make lint      # Run linters
make typecheck # Run type checking with mypy
make check     # Run all checks (lint, typecheck, test)
```

## CI/CD Integration

The tool includes a `Makefile` target for CI integration:

```yaml
# Example GitHub Actions workflow
name: Decommission Check

on: [push, pull_request]

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          make install
      - name: Run decommission scan
        run: |
          python -m decommission_tool scan . --db-name my_database --output decommission_report.json
      - name: Upload report
        uses: actions/upload-artifact@v3
        with:
          name: decommission-report
          path: decommission_report.json
```

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

Contributions are welcome! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details.
