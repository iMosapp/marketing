# Live-API auth fixtures (super_admin / store_manager / org_admin / rep / mongo) for preview tests
import os

import pytest
from dotenv import load_dotenv

pytest_plugins = ["tests.live_auth"]


def pytest_configure(config):
    """Preview only: every test run refuses a non-local MongoDB or a production API URL before any module is imported."""
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
    from tests.safe_cleanup import UnsafeCleanup, require_preview_db
    try:
        require_preview_db()
    except UnsafeCleanup as e:
        pytest.exit(str(e), returncode=3)


@pytest.fixture(scope="module", autouse=True)
def _fresh_motor_client():
    """Many modules own their own asyncio loop; routers.database caches one Motor client per process, so a client created on an
    earlier module's loop would raise "Future attached to a different loop". Give every module a fresh lazy client."""
    from routers import database
    database._client, database._db = None, None
    yield
    database._client, database._db = None, None
