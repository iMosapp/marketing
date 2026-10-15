"""Jessi Mini voice quality: the name policy is in mini's prompt only, GPT-Live's prompt is unchanged, close diagnostics carry no content."""
import os
from datetime import datetime, timezone

import pytest
from bson import ObjectId
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
from routers.database import get_db  # noqa: E402
from services import live_voice as lv  # noqa: E402

USER = {"name": "Forest Ward", "role": "super_admin", "organization_name": "I'm On Social"}
CFG = lv.clean_config({"energy": 4, "pacing": 5, "playful": 4, "brevity": 5})
CTX = "Right now it is Thursday October 15, 2026, 9:05 AM for the rep. Their app is open on the Home screen."


def test_mini_prompt_drops_use_their_name_and_adds_the_name_policy():
    mini = lv.mini_instructions(lv.assistant_instructions(CFG, USER), CTX)
    assert "Use their first name now and then" not in mini
    assert lv.MINI_NAME_RULES in mini and "Never start a reply with it" in mini and "'Absolutely, [name]'" in mini
    assert "keep every customer name and number" in mini and "keep every name and number" not in mini
    assert mini.count("Forest") == 1 and "You are talking with Forest" in mini  # the name is known, said once in the prompt
    assert lv.personality(CFG) in mini and lv.CORE_RULES in mini  # personality, humor and tone untouched
    assert mini.endswith(CTX)


def test_shopper_mode_gets_no_rep_name_rules():
    assert lv.MINI_NAME_RULES not in lv.mini_instructions("You are a shopper named Dana.", CTX, names=False)


def test_gpt_live_prompt_is_unchanged():
    live = lv.assistant_instructions(CFG, USER)
    assert "You are talking with Forest, super_admin at I'm On Social. Use their first name now and then, not every sentence." in live
    assert lv.MINI_NAME_RULES not in live and "NAMES:" not in live


def test_greeting_keeps_the_name_once():
    assert lv.greeting_text(lv.clean_config({"greeting": "Hey {first}, Who are we talking about today?"}), USER) == "Hey Forest, Who are we talking about today?"


def test_close_diag_keeps_only_whitelisted_typed_fields():
    d = lv.close_diag({"initiated_by": "provider", "unexpected": 1, "pc_state": "connected", "ice_state": "connected", "dc_state": "closed", "last_event": "response.done",
                       "last_event_age_ms": "1200", "quiet_s": 3.7, "backgrounds": 2, "app_build": "1.0.4 (88)" + "x" * 100,
                       "transcript": "Sarah bought a Tahoe", "text": "secret", "audio": "base64...", "last_audio_age_ms": "nope"})
    assert d == {"initiated_by": "provider", "unexpected": True, "pc_state": "connected", "ice_state": "connected", "dc_state": "closed", "last_event": "response.done",
                 "last_event_age_ms": 1200, "quiet_s": 3, "backgrounds": 2, "app_build": ("1.0.4 (88)" + "x" * 100)[:60]}


@pytest.mark.asyncio
async def test_closed_event_stores_diagnostics_and_reason():
    db = get_db()
    live_id = "test" + str(ObjectId())[-8:]
    await db[lv.COLL].insert_one({"live_id": live_id, "user_id": "qa-none", "mode": "assistant", "engine": "mini", "model": lv.MINI_MODEL, "status": "closing-test",
                                  "config": dict(lv.DEFAULTS), "started_at": datetime.now(timezone.utc), "seconds": 0, "cost_usd": 0.0, "transcript": [], "delegations": []})
    try:
        live = await lv.get_live(db, live_id)
        await lv.record_events(db, live, [{"type": "closed", "reason": "away", "seconds": 154, "tokens": {"audio_out": 900},
                                           "diag": {"initiated_by": "app", "unexpected": False, "pc_state": "connected", "quiet_s": 150, "note": "dropped"}}])
        doc = await lv.get_live(db, live_id)
        assert doc["close_reason"] == "away" and doc["seconds"] == 154
        assert doc["close_diag"] == {"initiated_by": "app", "unexpected": False, "pc_state": "connected", "quiet_s": 150}
        assert lv.serialize(doc)["close_diag"]["initiated_by"] == "app"
    finally:
        await db[lv.COLL].delete_one({"live_id": live_id})
