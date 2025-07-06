import pytest

def pytest_addoption(parser):
    """Add a command line option to pytest to keep test branches."""
    parser.addoption(
        "--dont-delete", action="store_true", default=False, help="Don't delete test branch after test run"
    )
