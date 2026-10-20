import os
import pytest


@pytest.fixture(autouse=True)
def set_test_env():
    """Sets a mock test API key for offline test suites if not already present."""
    old_key = os.environ.get("OMNIROUTE_API_KEY")
    os.environ["OMNIROUTE_API_KEY"] = old_key or "mock-test-omniroute-key-offline"
    yield
    if old_key is None:
        os.environ.pop("OMNIROUTE_API_KEY", None)
    else:
        os.environ["OMNIROUTE_API_KEY"] = old_key
