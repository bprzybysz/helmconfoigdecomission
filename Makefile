# Makefile for PostgreSQL Decommission Tool
# UV-managed Python environment

.PHONY: help install test test-unit test-integration test-e2e clean lint format typecheck check dev-setup ci clean-venv

# Variables
PYTHON_VERSION := 3.11
VENV_DIR := .venv
PYTHON := $(VENV_DIR)/bin/python
PIP := $(VENV_DIR)/bin/pip
PYTEST := $(VENV_DIR)/bin/pytest
MYPY := $(VENV_DIR)/bin/mypy
BLACK := $(VENV_DIR)/bin/black
RUFF := $(VENV_DIR)/bin/ruff

# Container settings
IMAGE_NAME ?= decommission-tool
IMAGE_TAG ?= latest
CONTAINER_RUNTIME := $(shell command -v podman 2>/dev/null || command -v docker 2>/dev/null)

# Help target
help:
	@echo "PostgreSQL Decommission Tool"
	@echo "Available commands:"
	@echo "  install       - Install development dependencies"
	@echo "  dev-setup     - Set up the full development environment"
	@echo "  test          - Run all tests (unit, integration, e2e)"
	@echo "  test-unit     - Run unit tests"
	@echo "  test-integration - Run integration tests"
	@echo "  test-e2e      - Run end-to-end tests"
	@echo "  lint          - Run code linter (ruff)"
	@echo "  format        - Format code (black)"
	@echo "  typecheck     - Run type checking (mypy)"
	@echo "  check         - Run all checks (lint, typecheck, test)"
	@echo "  ci            - Run CI checks (lint, typecheck, test, build)"
	@echo "  clean         - Clean up generated files and cache"
	@echo "  clean-venv    - Remove virtual environment"

# Install dependencies
install: $(VENV_DIR)/bin/activate
	@echo "📦 Installing dependencies..."
	@$(PIP) install -e '.[dev]'
	@echo "✅ Dependencies installed"

# Set up development environment
dev-setup: clean-venv install pre-commit
	@echo "✨ Development environment ready"

# Run all tests
test: test-unit test-integration test-e2e

# Run unit tests
test-unit: $(VENV_DIR)/bin/activate
	@echo "🚀 Running unit tests..."
	@$(PYTEST) tests/unit -v --cov=decommission_tool --cov-report=term-missing

# Run integration tests
test-integration: $(VENV_DIR)/bin/activate
	@echo "🔍 Running integration tests..."
	@$(PYTEST) tests/integration -v

# Run end-to-end tests
test-e2e: $(VENV_DIR)/bin/activate
	@echo "🏁 Running end-to-end tests..."
	@$(PYTEST) tests/e2e -v

# Run linter
lint: $(VENV_DIR)/bin/activate
	@echo "🔍 Running linter..."
	@$(RUFF) check .
	@echo "✅ Linting passed"

# Format code
format: $(VENV_DIR)/bin/activate
	@echo "🎨 Formatting code..."
	@$(BLACK) .
	@echo "✅ Formatting complete"

# Run type checking
typecheck: $(VENV_DIR)/bin/activate
	@echo "🔍 Running type checking..."
	@$(MYPY) decommission_tool tests
	@echo "✅ Type checking passed"

# Run all checks
check: lint typecheck test

# Run CI checks
ci: clean install lint typecheck test

# Clean up generated files and cache
clean:
	@echo "🧹 Cleaning up..."
	@rm -rf `find . -name __pycache__`
	@rm -f `find . -type f -name '*.py[co]'`
	@rm -f `find . -type f -name '*~'`
	@rm -f `find . -type f -name '.*~'`
	@rm -rf .cache
	@rm -rf .pytest_cache
	@rm -rf htmlcov
	@rm -f .coverage
	@rm -f .coverage.*
	@echo "✅ Clean complete"

# Remove virtual environment
clean-venv:
	@echo "🧹 Removing virtual environment..."
	@rm -rf $(VENV_DIR)

# Create virtual environment
$(VENV_DIR)/bin/activate:
	@echo "🐍 Creating Python $(PYTHON_VERSION) virtual environment..."
	@python$(PYTHON_VERSION) -m venv $(VENV_DIR)
	@$(PIP) install --upgrade pip setuptools wheel

# Install pre-commit hooks
pre-commit: $(VENV_DIR)/bin/activate
	@echo "🔧 Installing pre-commit hooks..."
	@$(PIP) install pre-commit
	@$(VENV_DIR)/bin/pre-commit install

# Build container image
container-build:
	@echo "🐳 Building container image..."
	@$(CONTAINER_RUNTIME) build -t $(IMAGE_NAME):$(IMAGE_TAG) .

# Run container with shell
container-shell: container-build
	@echo "🚀 Starting container with shell..."
	@$(CONTAINER_RUNTIME) run -it --rm \
		-v $(PWD):/app \
		-w /app \
		$(IMAGE_NAME):$(IMAGE_TAG) \
		/bin/bash

# Clean container images
container-clean:
	@echo "🧹 Cleaning container images..."
	-@$(CONTAINER_RUNTIME) rmi $(IMAGE_NAME):$(IMAGE_TAG) 2>/dev/null || true

# Run in development mode
dev: install
	@echo "🚀 Starting in development mode..."
	@$(PYTHON) -m decommission_tool --help

# Show help by default
.DEFAULT_GOAL := help

# Set up the full development environment
dev-setup: install
	@echo "✅ Development setup complete."

# Run all tests
test:
	@echo "🧪 Running unit and integration tests..."
	@uv run pytest tests/

# Scan target repo
scan-db:
	@echo "🔎 Scanning $(TARGET_REPO_DIR) for database: $(DB_NAME) with args: $(ARGS)"
	@$(PYTHON) decommission_tool.py $(TARGET_REPO_DIR) $(DB_NAME) $(ARGS)

# Lint and type check code
lint:
	@echo "🔍 Running linter (ruff)..."
	@uv run ruff check .
	@echo "🔍 Running type checker (mypy)..."
	@uv run mypy . --ignore-missing-imports

# Format code
format:
	@echo "🎨 Formatting code..."
	@$(VENV_DIR)/bin/uv run black .
	@$(VENV_DIR)/bin/uv run ruff format .

# Clean up generated files
clean: container-clean
	@echo "🧹 Cleaning up..."
	@rm -rf .pytest_cache .mypy_cache
	@find . -type d -name "__pycache__" -exec rm -r {} + > /dev/null 2>&1 || true
	@rm -f decommission_findings.json
	@rm -rf $(TARGET_REPO_DIR)

# Primary E2E test target
test-container-e2e:
	@echo "🧪 Running containerized E2E tests..."
	@$(PYTHON) -m pytest tests/test_container_e2e.py -v -s

# CI/CD pipeline simulation[5]
ci:
	@set -e; \
	echo "🎯 Starting CI pipeline..."; \
	make install; \
	make lint; \
	make test; \
	make test-container-e2e; \
	echo "✅ CI pipeline completed successfully"

# Clean up generated files and artifacts[4]
clean-venv:
	@echo "🧹 Cleaning virtual environment..."
	@rm -rf $(VENV_DIR)
	@echo "✅ Virtual environment cleaned"

# --- Container Commands ---

container-build:
	@if [ -z "$(CONTAINER_RUNTIME)" ]; then \
		echo "❌ Neither podman nor docker found. Please install one."; \
		exit 1; \
	fi
	@echo "🏗️ Building container image with $(CONTAINER_RUNTIME)..."
	@$(CONTAINER_RUNTIME) build -t $(IMAGE_NAME):$(IMAGE_TAG) .

container-shell:
	@echo "🐚 Opening a shell in the container..."
	@$(COMPOSE_CMD) run --rm app /bin/bash

container-clean:
	@echo "🧹 Cleaning up containers and volumes..."
	@$(COMPOSE_CMD) down -v --remove-orphans

container-debug-persistence:
	@echo "🔍 Inspecting persistence volume..."
	@$(COMPOSE_CMD) run --rm app sh -c "echo '--- Root directory ---' && ls -la / && echo '--- Persistence directory ---' && ls -la /persistence"
