# Makefile for PostgreSQL Decommission Tool with Python 3.11+

# Variables
PYTHON_VERSION := 3.11
VENV_DIR := .venv
PYTHON := $(VENV_DIR)/bin/python
PIP := $(VENV_DIR)/bin/pip
PYTEST := $(VENV_DIR)/bin/pytest

# Container settings
IMAGE_NAME ?= decommission-tool
IMAGE_TAG ?= latest
CONTAINER_RUNTIME := $(shell command -v podman 2>/dev/null || command -v docker 2>/dev/null)

.PHONY: help install dev-setup test test-unit test-integration test-e2e \
        lint format typecheck check clean clean-venv container-build \
        container-clean test-container-quick test-container-full ci

help:
	@echo "PostgreSQL Decommission Tool (Python 3.11+)"
	@echo "Available commands:"
	@echo "  install              - Install development dependencies"
	@echo "  dev-setup           - Set up full development environment"
	@echo "  test                - Run all tests"
	@echo "  test-unit           - Run unit tests only"
	@echo "  test-integration    - Run integration tests only"
	@echo "  test-e2e            - Run end-to-end tests only"
	@echo "  test-container-quick - Run quick container E2E tests"
	@echo "  test-container-full  - Run full container E2E tests"
	@echo "  lint                - Run code linter"
	@echo "  format              - Format code"
	@echo "  typecheck           - Run type checking"
	@echo "  check               - Run all checks (lint, typecheck, test)"
	@echo "  container-build     - Build container image"
	@echo "  container-clean     - Clean container images"
	@echo "  clean               - Clean up generated files"
	@echo "  ci                  - Run CI pipeline"

# Python environment setup
$(VENV_DIR)/bin/activate:
	@echo "🐍 Creating Python $(PYTHON_VERSION) virtual environment..."
	@python$(PYTHON_VERSION) -m venv $(VENV_DIR)
	@$(PIP) install --upgrade pip setuptools wheel

install: $(VENV_DIR)/bin/activate
	@echo "📦 Installing development dependencies..."
	@$(PIP) install -e '.[dev]'
	@echo "✅ Dependencies installed"

dev-setup: clean-venv install
	@echo "🔧 Setting up development environment..."
	@$(PIP) install pre-commit
	@$(VENV_DIR)/bin/pre-commit install
	@echo "✨ Development environment ready"

# Testing targets
test-unit: $(VENV_DIR)/bin/activate
	@echo "🧪 Running unit tests..."
	@$(PYTEST) tests/test_*.py -v --cov=decommission_tool --cov-report=term-missing

test-integration: $(VENV_DIR)/bin/activate
	@echo "🔍 Running integration tests..."
	@$(PYTEST) tests/test_*integration*.py tests/test_*_mcp_*.py -v

test-e2e: $(VENV_DIR)/bin/activate
	@echo "🏁 Running E2E tests..."
	@$(PYTEST) tests/test_container_e2e.py -v -s

test: test-unit test-integration

# Container E2E testing
test-container-quick: container-build
	@echo "🚀 Running quick container E2E tests..."
	@$(PYTEST) tests/test_container_e2e.py::TestContainerE2E -v -s

test-container-full: container-build
	@echo "🚀 Running full container E2E tests..."
	@$(PYTEST) tests/test_container_e2e.py -v -s --tb=short

# Code quality
lint: $(VENV_DIR)/bin/activate
	@echo "🔍 Running linter..."
	@$(VENV_DIR)/bin/ruff check .
	@echo "✅ Linting passed"

format: $(VENV_DIR)/bin/activate
	@echo "🎨 Formatting code..."
	@$(VENV_DIR)/bin/black .
	@$(VENV_DIR)/bin/ruff format .
	@echo "✅ Formatting complete"

typecheck: $(VENV_DIR)/bin/activate
	@echo "🔍 Running type checking..."
	@$(VENV_DIR)/bin/mypy decommission_tool.py git_utils.py file_system_mcp_server.py
	@echo "✅ Type checking passed"

check: lint typecheck test

# Container operations
container-build:
	@if [ -z "$(CONTAINER_RUNTIME)" ]; then \
		echo "❌ Neither podman nor docker found. Please install one."; \
		exit 1; \
	fi
	@echo "🏗️ Building container image with $(CONTAINER_RUNTIME)..."
	@$(CONTAINER_RUNTIME) build -t $(IMAGE_NAME):$(IMAGE_TAG) .

container-clean:
	@echo "🧹 Cleaning container images..."
	@$(CONTAINER_RUNTIME) rmi -f $(IMAGE_NAME):$(IMAGE_TAG) 2>/dev/null || true
	@$(CONTAINER_RUNTIME) system prune -f

# Clean up
clean:
	@echo "🧹 Cleaning up..."
	@rm -rf `find . -name __pycache__`
	@rm -f `find . -type f -name '*.py[co]'`
	@rm -rf .pytest_cache .mypy_cache .ruff_cache
	@rm -f .coverage .coverage.*
	@rm -rf htmlcov
	@rm -rf build dist *.egg-info
	@echo "✅ Clean complete"

clean-venv:
	@echo "🧹 Removing virtual environment..."
	@rm -rf $(VENV_DIR)

# CI pipeline
ci: clean install lint typecheck test test-container-quick
	@echo "✅ CI pipeline completed successfully"

# Development helpers
dev-run: install
	@echo "🚀 Running development version..."
	@$(PYTHON) -m decommission_tool --help

dev-shell: install
	@echo "🐚 Starting development shell..."
	@$(PYTHON)

# Version check
check-python:
	@python3 --version | grep -E "Python 3\.(1[1-9]|[2-9][0-9])" || \
		(echo "❌ Python 3.11+ required" && exit 1)
	@echo "✅ Python version check passed"

.DEFAULT_GOAL := help
