import asyncio
import uvloop
import pytest

@pytest.fixture(scope="session")
def event_loop():
    """Force uvloop to be used for all async tests."""
    policy = uvloop.EventLoopPolicy()
    asyncio.set_event_loop_policy(policy)
    loop = policy.new_event_loop()
    yield loop
    loop.close()
def pytest_addoption(parser):
    """Add a command line option to pytest to keep test branches."""
    parser.addoption(
        "--dont-delete", action="store_true", default=False, help="Don't delete test branch after test run"
    )
