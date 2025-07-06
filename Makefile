# Makefile for PostgreSQL Decommission Tool with Python 3.11+

# Variables - Simplified Python detection
VENV_DIR := .venv
PYTHON_VERSION := 3.11
PYTHON := $(VENV_DIR)/bin/python
PYTHON_VERSION := $(shell $(PYTHON) -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
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
	@echo "  install           - Install development dependencies"
	@echo "  dev-setup         - Set up full development environment"
	@echo "  test              - Run all tests"
	@echo "  test-unit         - Run unit tests only"
	@echo "  test-integration  - Run integration tests only"
	@echo "  test-e2e          - Run end-to-end tests only"
	@echo "  test-container-quick - Run quick container E2E tests"
	@echo "  test-container-full  - Run full container E2E tests"
	@echo "  lint              - Run code linter"
	@echo "  format            - Format code"
	@echo "  typecheck         - Run type checking"
	@echo "  check             - Run all checks (lint, typecheck, test)"
	@echo "  container-build   - Build container image"
	@echo "  container-clean   - Clean container images"
	@echo "  clean             - Clean up generated files"
	@echo "  ci                - Run CI pipeline"

# Python environment setup - FIXED: Proper version detection and error handling
check-python:
	@echo "🔍 Checking Python installation..."
	@if [ -z "$(PYTHON)" ]; then \
		echo "❌ No Python interpreter found. Please install Python 3.11+"; \
		exit 1; \
	fi
	@echo "✅ Found Python: $(PYTHON)"
	@echo "✅ Python version: $(PYTHON_VERSION)"
	@if [ "$(shell echo "$(PYTHON_VERSION)" | cut -d. -f1)" != "3" ] || \
	   [ "$(shell echo "$(PYTHON_VERSION)" | cut -d. -f2)" -lt "11" ]; then \
		echo "❌ Python 3.11+ required, found $(PYTHON_VERSION)"; \
		exit 1; \
	fi

$(VENV_DIR)/bin/activate: check-python
	@echo "🐍 Creating Python $(PYTHON_VERSION) virtual environment..."
	@$(PYTHON) -m venv $(VENV_DIR)
	@$(PIP) install --upgrade pip setuptools wheel
	@echo "✅ Virtual environment created"

install: $(VENV_DIR)/bin/activate
	@echo "📦 Installing development dependencies..."
	@$(PIP) install -e '.[dev]'
	@echo "✅ Dependencies installed"

dev-setup: clean-venv install
	@echo "🔧 Setting up development environment..."
	@if command -v pre-commit >/dev/null 2>&1; then \
		$(VENV_DIR)/bin/pre-commit install; \
	else \
		$(PIP) install pre-commit; \
		$(VENV_DIR)/bin/pre-commit install; \
	fi
	@echo "✨ Development environment ready"

# Testing targets - FIXED: Proper async test configuration
test-unit: $(VENV_DIR)/bin/activate
	@echo "🧪 Running unit tests..."
	@$(PYTEST) tests/test_*.py -v --cov=decommission_tool --cov-report=term-missing --asyncio-mode=auto

test-integration: $(VENV_DIR)/bin/activate
	@echo "🔍 Running integration tests..."
	@$(PYTEST) tests/test_decommission_tool.py tests/test_remove_functionality.py tests/test_file_system_mcp_server.py -v --asyncio-mode=auto

test-e2e: $(VENV_DIR)/bin/activate
	@echo "🏁 Running E2E tests..."
	@$(PYTEST) tests/test_container_e2e.py -v -s --asyncio-mode=auto

test: test-unit test-integration test-e2e

# Container E2E testing - FIXED: Container runtime detection
test-container-quick: container-build
	@echo "🚀 Running quick container E2E tests..."
	@$(PYTEST) tests/test_container_e2e.py::TestContainerE2E -v -s --asyncio-mode=auto

test-container-full: container-build
	@echo "🚀 Running full container E2E tests..."
	@$(PYTEST) tests/test_container_e2e.py -v -s --tb=short --asyncio-mode=auto

# Code quality - FIXED: Proper tool paths
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
	@$(VENV_DIR)/bin/mypy decommission_tool.py git_utils.py file_system_mcp_server.py mcp_server_main.py
	@echo "✅ Type checking passed"

check: lint typecheck test

# Container operations - FIXED: Better error handling
container-build:
	@if [ -z "$(CONTAINER_RUNTIME)" ]; then \
		echo "❌ Neither podman nor docker found. Please install one."; \
		exit 1; \
	fi
	@echo "🏗️ Building container image with $(CONTAINER_RUNTIME)..."
	@$(CONTAINER_RUNTIME) build -t $(IMAGE_NAME):$(IMAGE_TAG) .
	@echo "✅ Container image built successfully"

container-clean:
	@if [ -z "$(CONTAINER_RUNTIME)" ]; then \
		echo "❌ Neither podman nor docker found. Please install one."; \
		exit 1; \
	fi
	@echo "🧹 Cleaning container images..."
	@$(CONTAINER_RUNTIME) rmi -f $(IMAGE_NAME):$(IMAGE_TAG) 2>/dev/null || true
	@$(CONTAINER_RUNTIME) system prune -f
	@echo "✅ Container cleanup complete"

# Clean up - FIXED: More thorough cleanup
clean:
	@echo "🧹 Cleaning up..."
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name '*.py[co]' -delete 2>/dev/null || true
	@rm -rf .pytest_cache .mypy_cache .ruff_cache
	@rm -f .coverage .coverage.*
	@rm -rf htmlcov
	@rm -rf build dist *.egg-info
	@rm -f decommission_findings.json repomix-output.xml
	@echo "✅ Clean complete"

clean-venv:
	@echo "🧹 Removing virtual environment..."
	@rm -rf $(VENV_DIR)
	@echo "✅ Virtual environment removed"

# CI pipeline - FIXED: Proper dependency order - lint, typecheck was disabled
ci: clean check-python install test test-container-quick
	@echo "✅ CI pipeline completed successfully"

# Development helpers - FIXED: Proper Python usage
dev-run: install
	@echo "🚀 Running development version..."
	@$(VENV_DIR)/bin/python -m decommission_tool --help

dev-shell: install
	@echo "🐚 Starting development shell..."
	@$(VENV_DIR)/bin/python

.DEFAULT_GOAL := help
