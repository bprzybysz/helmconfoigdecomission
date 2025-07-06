from pathlib import Path
from .container_manager import AsyncContainerManager, AsyncE2ETestSuite
import pytest

# Path to the docker-compose.yml file
COMPOSE_FILE = Path(__file__).parent.parent / "docker-compose.yml"

# Replace the container_env fixture
@pytest.fixture(scope="session")
async def container_env():
    """Session-scoped container environment."""
    async with AsyncContainerManager(COMPOSE_FILE) as container:
        yield container

@pytest.fixture(scope="function")
async def fresh_container():
    """Function-scoped fresh container for each test."""
    async with AsyncContainerManager(COMPOSE_FILE) as container:
        yield container

# Update all test methods to be async
class TestContainerE2E:
    @pytest.mark.asyncio
    async def test_container_basic_health(self, container_env):
        """Test basic container health and Python environment."""
        result = await container_env.execute(["python", "--version"])
        assert "Python 3.1" in result
        
        result = await container_env.execute([
            "python", "-c", "import decommission_tool; print('Import successful')"
        ])
        assert "Import successful" in result
