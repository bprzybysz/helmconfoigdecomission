# Makefile for PostgreSQL Decommission Tool
# UV-managed Python environment

.PHONY: help install test scan clean lint format check e2e dev-setup ci clean-venv

# Variables
TARGET_REPO_URL := https://github.com/cloudnative-pg/cloudnative-pg.git
TARGET_REPO_DIR := ./cloudnative-pg
DB_NAME ?= postgres
VENV_DIR := .venv
PYTHON := $(VENV_DIR)/bin/python

# Default target
help:
	@echo "PostgreSQL Decommission Tool - UV Managed"
	@echo "Available commands:"
	@echo "  install      - Install dependencies with UV"
	@echo "  dev-setup    - Set up the full development environment"
	@echo "  test         - Run unit tests"
	@echo "  e2e          - Run e2e tests against cloudnative-pg"
	@echo "  test-e2e-branch - Run e2e test with branch creation and removal"
	@echo "  scan-db      - Scan target repo. Usage: make scan-db DB_NAME=mydb [ARGS=--remove]"
	@echo "  lint         - Run linting and type checking"
	@echo "  format       - Format code"
	@echo "  ci           - Run a full CI check (lint, test, e2e)"
	@echo "  clean        - Clean up generated files and cloned repo"

# Install dependencies using uv[2]
install:
	@echo "📦 Installing dependencies with UV..."
	@if [ ! -d "$(VENV_DIR)" ]; then \
		uv venv $(VENV_DIR); \
	fi
	@source $(VENV_DIR)/bin/activate && \
	uv pip install --upgrade pip && \
	uv pip install pytest pytest-mock pyyaml ruff black mypy
	@echo "✅ Dependencies installed"

# Clone target repository if it doesn't exist
setup-target:
	@if [ ! -d "$(TARGET_REPO_DIR)" ]; then \
		echo "📥 Cloning $(TARGET_REPO_URL)..."; \
		git clone --depth 1 $(TARGET_REPO_URL) $(TARGET_REPO_DIR); \
	else \
		echo "✅ Target repository '$(TARGET_REPO_DIR)' already exists"; \
	fi

# Development setup
dev-setup: install setup-target
	@echo "🚀 Development environment ready"
	@echo "Run 'make e2e' to test against the target repo"

# Run unit tests
test:
	@echo "🧪 Running unit tests..."
	@$(PYTHON) -m pytest tests/ -v --tb=short

# Run e2e tests
e2e: setup-target
	@echo "🔄 Running e2e scan against $(TARGET_REPO_DIR)..."
	@$(PYTHON) test_e2e_branch.py
	@echo "✅ E2E scan completed. Results are in decommission_findings.json"

# Scan repository with a custom database name
scan-db: setup-target
	@echo "🔍 Scanning $(TARGET_REPO_DIR) for database: $(DB_NAME) with args: $(ARGS)"
	@$(PYTHON) decommission_tool.py $(TARGET_REPO_DIR) $(DB_NAME) $(ARGS)

# Run E2E test with branch management
test-e2e-branch:
	@echo "🧪 Running E2E test with branch creation..."
	@$(PYTHON) test_e2e_branch.py

# Lint and type check code
lint:
	@echo "🔍 Running linter (ruff)..."
	@$(VENV_DIR)/bin/uv run ruff check .
	@echo "🔍 Running type checker (mypy)..."
	@$(VENV_DIR)/bin/uv run mypy . --ignore-missing-imports

# Format code
format:
	@echo "🎨 Formatting code..."
	@$(VENV_DIR)/bin/uv run black .
	@$(VENV_DIR)/bin/uv run ruff format .

# CI/CD pipeline simulation[5]
ci:
	@set -e; \
	echo "🎯 Starting CI pipeline..."; \
	make install; \
	make lint; \
	make test; \
	make e2e; \
	echo "✅ CI pipeline completed successfully"

# Clean up generated files and artifacts[4]
clean-venv:
	@echo "🧹 Cleaning virtual environment..."
	@rm -rf $(VENV_DIR)
	@echo "✅ Virtual environment cleaned"

clean: clean-venv
	@echo "🧹 Cleaning up..."
	@rm -f decommission_findings.json
	@rm -rf __pycache__/ .pytest_cache/ .mypy_cache/
	@rm -rf $(TARGET_REPO_DIR)
	@echo "✅ Cleanup completed"
