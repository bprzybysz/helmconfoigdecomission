import pytest
import subprocess
from pathlib import Path
from tests.container_manager import ContainerManager

# Define the path to your docker-compose.yml file
DOCKER_COMPOSE_FILE = Path(__file__).parent / "docker-compose.yml"

@pytest.fixture(scope="module")
def container_environment():
    """
    Fixture to set up and tear down the Docker container environment
    for E2E tests.
    """
    with ContainerManager(DOCKER_COMPOSE_FILE) as manager:
        yield manager

def test_decommission_tool_help(container_environment):
    """
    Test that the decommission_tool can be run with --help inside the container.
    """
    container_name = container_environment.container_name
    
    command = [
        "docker", "exec", container_name,
        "python", "-m", "decommission_tool", "--help"
    ]
    
    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True
        )
        print(result.stdout)
        assert "usage: decommission_tool" in result.stdout
        assert "show this help message and exit" in result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Command failed with error: {e.stderr}")
        pytest.fail(f"E2E test failed: {e.stderr}")

# Add more E2E tests here as needed
