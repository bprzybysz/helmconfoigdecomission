# Makefile for PostgreSQL Decommission Tool

.PHONY: help install test test-unit test-integration test-e2e clean lint format typecheck check dev-setup ci clean-venv container-build container-shell container-clean container-debug-persistence generate-requirements

# Variables
PYTHON_VERSION := 3.11
VENV_DIR := .venv
PYTHON := $(VENV_DIR)/bin/python
PIP := $(VENV_DIR)/bin/pip
PYTEST := $(VENV_DIR)/bin/pytest
MYPY := $(VENV_DIR)/bin/mypy
BLACK := $(VENV_DIR)/bin/black
RUFF := $(VENV_DIR)/bin/ruff
PIP_COMPILE := $(VENV_DIR)/bin/pip-compile

# Container settings
IMAGE_NAME ?= decommission-tool
IMAGE_TAG ?= latest
CONTAINER_RUNTIME := $(shell command -v podman 2>/dev/null || command -v docker 2>/dev_null)
COMPOSE_FILE := tests/docker-compose.yml
COMPOSE_CMD := $(CONTAINER_RUNTIME)-compose -f $(COMPOSE_FILE)

# Help target
help:
	@echo "PostgreSQL Decommission Tool"
	@echo "Available commands:"
	@echo "  install       - Install development dependencies"
	@echo "  dev-setup     - Set up the full development environment"
	@echo "  test          - Run all tests (unit, integration, e2e)"
	@echo "  test-unit     - Run unit tests"
	@echo "  test-integration - Run integration tests"
	@echo "  test-e2e      - Run end-to-end tests using docker-compose"
	@echo "  lint          - Run code linter (ruff)"
	@echo "  format        - Format code (black)"
	@echo "  typecheck     - Run type checking (mypy)"
	@echo "  check         - Run all checks (lint, typecheck, test)"
	@echo "  ci            - Run CI checks (lint, typecheck, test, build)"
	@echo "  clean         - Clean up generated files and cache"
	@echo "  clean-venv    - Remove virtual environment"
	@echo "  container-build - Build the Docker container image"
	@echo "  container-shell - Open a shell inside the running container"
	@echo "  container-clean - Clean up Docker containers and volumes"
	@echo "  container-debug-persistence - Inspect the persistence volume in the container"
	@echo "  generate-requirements - Generate requirements.txt and requirements-dev.txt"

# Virtual environment setup
$(VENV_DIR)/bin/activate: pyproject.toml
	@echo "Setting up virtual environment..."
	@python$(PYTHON_VERSION) -m venv $(VENV_DIR)
	@$(PIP) install --upgrade pip setuptools wheel pip-tools
	@echo "Virtual environment ready."

# Install dependencies
install: $(VENV_DIR)/bin/activate
	@echo "📦 Installing dependencies..."
	@if [ -f requirements.txt ]; then \
		$(PIP) install -r requirements.txt; \
	else \
		$(PIP) install .; \
	fi
	@if [ -f requirements-dev.txt ]; then \
		$(PIP) install -r requirements-dev.txt; \
	else \
		$(PIP) install -e '.[dev]'; \
	fi
	@echo "✅ Dependencies installed"

# Generate requirements files
generate-requirements: $(VENV_DIR)/bin/activate
	@echo "Generating requirements.txt and requirements-dev.txt..."
	@$(PIP_COMPILE) --output-file requirements.txt pyproject.toml
	@$(PIP_COMPILE) --extra dev --output-file requirements-dev.txt pyproject.toml
	@echo "✅ Requirements files generated."

# Set up development environment
dev-setup: clean-venv install
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

# Run end-to-end tests using docker-compose
test-e2e: container-build
	@echo "🧪 Running end-to-end tests..."
	@$(PYTHON) tests/e2e_test.py

# Lint code
lint: $(VENV_DIR)/bin/activate
	@echo "🔍 Running linter (ruff)..."
	@$(RUFF) check .

# Format code
format: $(VENV_DIR)/bin/activate
	@echo "🎨 Formatting code..."
	@$(BLACK) .
	@$(RUFF) format .

# Type check code
typecheck: $(VENV_DIR)/bin/activate
	@echo "🔍 Running type checker (mypy)..."
	@$(MYPY) . --ignore-missing-imports

# Run all checks
check: lint typecheck test

# CI/CD pipeline simulation
ci:
	@set -e; \
	echo "🎯 Starting CI pipeline..."; \
	make install; \
	make lint; \
	make test; \
	echo "✅ CI pipeline completed successfully"

# Clean up generated files
clean: container-clean
	@echo "🧹 Cleaning up..."
	@rm -rf .pytest_cache .mypy_cache
	@find . -type d -name "__pycache__" -exec rm -r {} + > /dev/null 2>&1 || true
	@rm -f decommission_findings.json requirements.txt requirements-dev.txt

# Clean virtual environment
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
