# Live-API auth fixtures (super_admin / store_manager / org_admin / rep / mongo) for preview tests
import pytest

pytest_plugins = ["tests.live_auth"]


@pytest.fixture(scope="module", autouse=True)
def _fresh_motor_client():
    """Many modules own their own asyncio loop; routers.database caches one Motor client per process, so a client created on an
    earlier module's loop would raise "Future attached to a different loop". Give every module a fresh lazy client."""
    from routers import database
    database._client, database._db = None, None
    yield
    database._client, database._db = None, None
