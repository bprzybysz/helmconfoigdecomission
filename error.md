## Current Error: `[tool.poetry] section not found in /app/pyproject.toml`

**Problem Description:**
The `podman-compose up --build -d` command, executed within the `running_mcp_server` fixture in `tests/test_container_e2e.py`, is failing during the Docker image build process with the error `[tool.poetry] section not found in /app/pyproject.toml`.

This error occurs because the `Dockerfile` attempts to use `poetry install` (specifically the line `poetry install --only main --no-interaction --no-ansi`), but the `pyproject.toml` file in this project is configured for `setuptools` (as indicated by `build-backend = "setuptools.build_meta"` and the absence of a `[tool.poetry]` section), not Poetry.

**Symptoms:**
- `test_container_e2e.py` tests fail during the `running_mcp_server` fixture setup.
- The specific error message from `podman-compose` build output is `[tool.poetry] section not found in /app/pyproject.toml`.
- The container image fails to build, preventing any further tests from running.

**Relevant Code Snippets:**

**`tests/test_container_e2e.py` (Fixture setup where the error occurs):**
```python
@pytest.fixture(scope="session")
def running_mcp_server(tmp_path_factory):
    """
    Builds and starts the MCP server container, waits for it to be healthy,
    and yields the container name. Tears down the container after tests.
    """
    # Ensure the container is not already running from a previous failed run
    if is_container_running(CONTAINER_NAME):
        subprocess.run(["podman-compose", "-f", str(COMPOSE_FILE), "down", "-v"], check=True)

    # Build and start the container in detached mode
    print("Building and starting container...")
    subprocess.run(["podman-compose", "-f", str(COMPOSE_FILE), "up", "--build", "-d"], check=True)

    # ... health check and teardown code ...
```

**`docker-compose.yml` (Service definition and healthcheck - *Note: The healthcheck is currently irrelevant as the build fails before it's reached*):**
```yaml
version: '3.8'
services:
  mcp-server:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "5001:5000"
    volumes:
      - ./tests/test_repo:/app/test_repo:ro
    environment:
      - MCP_LOG_LEVEL=DEBUG
      - MCP_HOST_REPO_PATH=/app/test_repo
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/health"]
      interval: 2s
      timeout: 5s
      retries: 15
```

**`Dockerfile` (The problematic section):**
```dockerfile
# ... (previous steps)

# Install Poetry
RUN pip install "poetry==$POETRY_VERSION"

# Set work directory
WORKDIR /app

# Copy only the files needed for dependency installation
COPY pyproject.toml poetry.lock* ./

# Install dependencies
RUN --mount=type=cache,target=/root/.cache/pypoetry \
    poetry config virtualenvs.in-project true && \
    poetry install --only main --no-interaction --no-ansi

# ... (rest of the Dockerfile)
```

**`pyproject.toml` (Showing `setuptools` configuration and lack of `[tool.poetry]`):**
```toml
[build-system]
requires = ["setuptools>=42.0"]
build-backend = "setuptools.build_meta"

[project]
name = "decommission-tool"
version = "0.1.0"
description = "Tool to decommission PostgreSQL databases from a Helm-based infrastructure"
readme = "README.md"
# ... (rest of the pyproject.toml)
```

**Error Log Snippet (from `pytest -v --log-cli-level=DEBUG tests/test_container_e2e.py`):**
```
<truncated output>
[1/2] STEP 7/7: RUN --mount=type=cache,target=/root/.cache/pypoetry     poetry config virtualenvs.in-project true &&     poetry install --only main --no-interaction --no-ansi

[tool.poetry] section not found in /app/pyproject.toml
------------------------------- Captured stderr setup -------------------------------
Error: building at STEP "RUN --mount=type=cache,target=/root/.cache/pypoetry poetry config virtualenvs.in-project true &&     poetry install --only main --no-interaction --no-ansi": while running runtime: exit status 1

ERROR:podman_compose:Build command failed
___________ ERROR at setup of test_decommission_tool_remove_in_container ____________

<truncated output>
E               subprocess.CalledProcessError: Command '['podman-compose', '-f', '/Users/blaisem4/src/helmconfoigdecomission/docker-compose.yml', 'up', '--build', '-d']' returned non-zero exit status 1.
```

**Analysis:**
The root cause of the current failure is the `Dockerfile` attempting to use Poetry for dependency installation, while the project's `pyproject.toml` is configured for `setuptools`. This mismatch leads to the `[tool.poetry] section not found` error during the image build process.

**Next Steps (Debugging Strategy):**
1.  **Correct Dockerfile for Setuptools:** Modify the `Dockerfile` to use `pip install .` or `python -m pip install .` for dependency installation, aligning with the `setuptools` build backend defined in `pyproject.toml`. This will replace the Poetry-specific commands.
2.  **Re-evaluate Healthcheck:** After the container builds successfully, the `healthcheck` in `docker-compose.yml` will become relevant again. Given that `decommission_tool.py` is a CLI tool, the current healthcheck expecting a web server on port 5000 is still fundamentally incorrect. This will need to be addressed (either by removing it, or adapting it to check for the CLI tool's readiness in a different way, if applicable).
3.  **Clean Podman Environment:** Ensure any lingering Podman containers or images are removed before attempting a new build to avoid caching issues and conflicts.