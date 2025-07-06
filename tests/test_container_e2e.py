# tests/test_container_e2e.py
import os
import subprocess
import time
from pathlib import Path
import pytest
import yaml

# Define constants for compose file and container name
COMPOSE_FILE = Path(__file__).parent.parent / "docker-compose.yml"
CONTAINER_NAME = "helmconfoigdecomission_mcp-server_1"
IMAGE_NAME = "helm-config-decommission-tool"

def is_container_running(container_name):
    """Check if a container with the given name is running."""
    result = subprocess.run(["podman", "ps", "--filter", f"name={container_name}"], capture_output=True, text=True)
    return container_name in result.stdout

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

    # Health check loop
    max_wait = 60  # seconds
    start_time = time.time()
    is_healthy = False
    print("Waiting for container to be healthy...")
    while time.time() - start_time < max_wait:
        result = subprocess.run(
            ["podman", "inspect", "--format", "{{.State.Health.Status}}", CONTAINER_NAME],
            capture_output=True, text=True,
        )
        if result.stdout.strip() == "healthy":
            is_healthy = True
            print("✅ Container is healthy!")
            break
        time.sleep(2)

    if not is_healthy:
        # Capture logs for debugging before failing
        logs = subprocess.run(["podman", "logs", CONTAINER_NAME], capture_output=True, text=True).stdout
        pytest.fail(f"Container did not become healthy within {max_wait} seconds.\nLogs:\n{logs}")

    yield CONTAINER_NAME

    # Teardown: stop and remove the container
    print("\nTearing down container...")
    subprocess.run(["podman-compose", "-f", str(COMPOSE_FILE), "down", "-v"], check=True)


def test_container_can_access_mounted_repo(running_mcp_server):
    """
    Verify that the container can access the files mounted in the volume.
    This is a basic check to ensure the volume mount is working correctly.
    """
    # The path inside the container where the repo is mounted
    container_repo_path = "/app/test_repo"
    
    # Command to list files in the mounted directory inside the container
    cmd = ["podman", "exec", running_mcp_server, "ls", "-l", container_repo_path]
    
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    
    # Check for a file that is known to be in the test repo
    assert "service.yaml" in result.stdout
    print("✅ Container can access the mounted repository.")


def test_decommission_tool_remove_in_container(running_mcp_server):
    """
    Full E2E test:
    1. Runs the decommission tool inside the container against the mounted repo.
    2. Verifies that the tool creates a new branch with the expected changes.
    """
    db_name = "example-db"
    branch_name = f"chore/decommission-{db_name}"
    host_repo_path = Path(__file__).parent / "test_repo"

    # Ensure the host repo is on the main branch and clean before the test
    subprocess.run(["git", "-C", str(host_repo_path), "checkout", "main"], check=True)
    subprocess.run(["git", "-C", str(host_repo_path), "reset", "--hard", "origin/main"], check=True)
    # Clean up any branches from previous runs
    existing_branches = subprocess.run(["git", "-C", str(host_repo_path), "branch"], capture_output=True, text=True).stdout
    if branch_name in existing_branches:
        subprocess.run(["git", "-C", str(host_repo_path), "branch", "-D", branch_name], check=True)

    # Run the decommission tool inside the container
    # Note: The path to the repo is the container-internal path
    cmd = [
        "podman", "exec", running_mcp_server,
        "python", "/app/decommission_tool.py", ".", db_name, "--remove", f"--branch-name={branch_name}"
    ]
    remove_result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    
    assert f"Changes are in branch: {branch_name}" in remove_result.stdout
    print("✅ Decommission tool --remove ran successfully inside the container.")
    
    # Verify on the host that the new branch was created with changes
    diff_check = subprocess.run(
        ["git", "-C", str(host_repo_path), "diff", "--quiet", "main", branch_name],
        capture_output=True
    )
    assert diff_check.returncode != 0, "No diff found between main and the new branch. Removal likely failed."
    print(f"✅ Verified changes were made in branch '{branch_name}' on the host.")
