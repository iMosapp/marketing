"""The Kubota pack ships ten specific scenarios per department on top of the master role-play, and the lazy seed puts them in the pool."""
import os
import pytest
from collections import Counter
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from routers.database import get_db  # noqa: E402
from services import mystery_shops as ms  # noqa: E402
from services.kubota_pack import KUBOTA_CHALLENGES, KUBOTA_SCENARIOS  # noqa: E402

pytestmark = pytest.mark.asyncio
DEPTS = ("eq_sales", "eq_service", "eq_parts", "eq_rental")


def test_pack_shape():
    assert Counter(c["department"] for c in KUBOTA_SCENARIOS) == {d: 10 for d in DEPTS}
    slugs = [c["slug"] for c in KUBOTA_CHALLENGES]
    assert len(slugs) == len(set(slugs)) == 44
    for c in KUBOTA_SCENARIOS:
        p = c["persona"]
        assert c["title"].startswith("Kubota ") and c["body"].startswith("[This call]") and c["direction"] == "inbound"
        assert p["name"] and p["voice"] in ms.VOICES and p["opening_line"] and len(p["objections"]) >= 3 and len(c["curveballs"]) == 3
        assert len(c["success_points"]) >= 10 and "\u2014" not in str(c)


async def test_seed_lands_in_every_department_pool():
    db = get_db()
    await ms.ensure_challenges(db)
    for d in DEPTS:
        n = await db.scripts.count_documents({"pool": "mystery_shop", "shop_client_id": None, "industry": "equipment", "department": d, "slug": {"$regex": "^kubota_"}, "active": {"$ne": False}})
        assert n >= 11, (d, n)
    assert await ms.ensure_challenges(db) == 0  # idempotent
