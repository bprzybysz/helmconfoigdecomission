# Makefile for PostgreSQL Decommission Tool
# UV-managed Python environment

.PHONY: help install test scan clean lint format check e2e dev-setup ci clean-venv test-e2e-inspect

# Variables
TARGET_REPO_URL := https://github.com/cloudnative-pg/cloudnative-pg.git
TARGET_REPO_DIR := ./cloudnative-pg
DB_NAME ?= postgres
VENV_DIR := .venv
PYTHON := $(VENV_DIR)/bin/python

# Container settings
IMAGE_NAME ?= helm-decommission-tool
IMAGE_TAG ?= latest
# Detect container runtime (podman or docker)
CONTAINER_RUNTIME := $(shell command -v podman 2>/dev/null || command -v docker 2>/dev/null)
COMPOSE_CMD := $(if $(findstring podman,$(CONTAINER_RUNTIME)),podman-compose,docker-compose)

# Default target
help:
	@echo "PostgreSQL Decommission Tool - UV Managed"
	@echo "Available commands:"
	@echo "  install          - Install dependencies with UV"
	@echo "  dev-setup        - Set up the full development environment"
	@echo "  test             - Run all unit and integration tests"
	@echo "  test-e2e-branch  - Run e2e test with branch creation and automatic cleanup"
	@echo "  test-e2e-inspect - Run e2e test and leave branch for inspection"
	@echo "  scan-db          - Scan target repo. Usage: make scan-db DB_NAME=mydb [ARGS=--remove]"
	@echo "  lint             - Run linting and type checking"
	@echo "  format           - Format code"
	@echo "  ci               - Run a full CI check (lint, test, e2e)"
	@echo "  clean            - Clean up generated files, cache, and cloned repo"
	@echo ""
	@echo "Container Commands:"
	@echo "  container-build  - Build the container image"
	@echo "  container-test   - Run tests inside the container"
	@echo "  container-shell  - Get a shell inside the running container"
	@echo "  container-clean  - Clean up containers and volumes"
	@echo "  container-debug-persistence - Inspect persistence volume in the container"

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

# Run all tests
test:
	@echo "🧪 Running all tests..."
	@$(PYTHON) -m pytest tests/ -v --tb=short

# Run E2E test with branch management and cleanup
test-e2e-branch:
	@echo "🧪 Running E2E test with branch creation and cleanup..."
	@$(PYTHON) -m pytest tests/test_decommission_tool.py::test_e2e_branch_lifecycle -v

# Run e2e tests and leave the branch for inspection
test-e2e-inspect:
	@echo "🧪 Running E2E test and leaving branch for inspection..."
	@$(PYTHON) -m pytest tests/test_decommission_tool.py::test_e2e_branch_lifecycle -v -s --dont-delete

# Scan repository with a custom database name
scan-db: setup-target
	@echo "🔍 Scanning $(TARGET_REPO_DIR) for database: $(DB_NAME) with args: $(ARGS)"
	@$(PYTHON) decommission_tool.py $(TARGET_REPO_DIR) $(DB_NAME) $(ARGS)

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

# Clean up generated files
clean: container-clean
	@echo "🧹 Cleaning up..."
	@rm -rf .pytest_cache .mypy_cache
	@find . -type d -name "__pycache__" -exec rm -r {} + > /dev/null 2>&1 || true
	@rm -f decommission_findings.json
	@rm -rf $(TARGET_REPO_DIR)

# Run e2e tests
e2e: test-e2e-branch

# CI/CD pipeline simulation[5]
ci:
	@set -e; \
	echo "🎯 Starting CI pipeline..."; \
	make install; \
	make lint; \
	make test; \
	make e2e; \
	make container-build; \
	make container-test; \
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

container-test:
	@echo "🧪 Running tests inside the container..."
	@$(COMPOSE_CMD) run --rm app ./run_tests.sh

container-shell:
	@echo "🐚 Opening a shell in the container..."
	@$(COMPOSE_CMD) run --rm app /bin/bash

container-clean:
	@echo "🧹 Cleaning up containers and volumes..."
	@$(COMPOSE_CMD) down -v --remove-orphans

container-debug-persistence:
	@echo "🔍 Inspecting persistence volume..."
	@$(COMPOSE_CMD) run --rm app sh -c "echo '--- Root directory ---' && ls -la / && echo '--- Persistence directory ---' && ls -la /persistence"
