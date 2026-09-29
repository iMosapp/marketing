"""Scenario add-ons (guide_note) ride along with the texted guide, and the challenge preview call picks the admin's cell."""
import os
import uuid
import pytest
from datetime import timedelta

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from routers.database import get_db  # noqa: E402
from routers import mystery_shops as r  # noqa: E402
from services import mystery_shops as ms  # noqa: E402
from services.kubota_pack import KUBOTA_SCENARIOS  # noqa: E402

pytestmark = pytest.mark.asyncio
KEY = f"test_note_{uuid.uuid4().hex[:8]}"


def test_scenarios_carry_a_guide_note_and_drafts_keep_it():
    assert all(c.get("guide_note") for c in KUBOTA_SCENARIOS)
    d = ms.normalize_draft({"title": "Parts caller: x", "body": "Answer well.", "guide_note": "A contractor is calling with a crew waiting \u2014 verify the hose.", "persona": {"name": "A B", "opening_line": "Hi"}}, "eq_parts")
    assert d["guide_note"] == "A contractor is calling with a crew waiting, verify the hose." or "\u2014" not in d["guide_note"]


def test_preview_phone_prefers_the_saved_shop_phone():
    assert r._preview_phone({"phone": "8015551212"}) == "8015551212"
    assert r._preview_phone({"shop_preview_phone": "+18015550000", "phone": "8015551212"}) == "+18015550000"
    assert r._preview_phone({}) == ""


async def test_pending_view_gets_the_challenge_note():
    db = get_db()
    await ms.ensure_challenges(db)
    sc = await db.scripts.find_one({"slug": "kubota_parts_06", "pool": "mystery_shop"})
    assert sc and sc.get("guide_note")
    tok = uuid.uuid4().hex
    await db.roleplay_sessions.insert_one({"kind": "mystery_shop", "seed_key": KEY, "client_id": "x", "target_id": "x", "rep_name": "Sam Test", "department": "eq_parts", "status": "scheduled", "ready_only": True,
                                           "token": tok, "script_id": str(sc["_id"]), "scheduled_for": ms._now() + timedelta(minutes=2)})
    try:
        out = await r.guide_pending(tok)
        assert out["state"] == "waiting" and out["first_name"] == "Sam"
        assert out["guide_note"] == sc["guide_note"] and out["challenge_title"] == sc["title"]
        assert "guide_note" not in await r.guide_pending("nope")
    finally:
        await db.roleplay_sessions.delete_many({"seed_key": KEY})
