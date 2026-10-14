"""End-to-end customer journey for Living Relationship Intelligence Phase 2 (2A timeline, 2B Reply In Your Voice, 2C nudges).

Tom bought a 2022 Jeep Wrangler two years ago -> the rep's voice memo says he bought a camper and wants to tow -> today a website
inquiry on a 2025 F-150 -> Tom texts "what can the F-150 tow?". The engine must: lead with the F-150, treat the Jeep as a trade
question only, show why, and nudge the rep exactly once. Live LLM (EMERGENT_LLM_KEY) through the running backend; cleans up after itself.

Run: cd /app/backend && set -a && . ./.env && . ../frontend/.env && set +a && python -m pytest tests/test_intel_phase2_journey.py -q
"""
import asyncio
import os
import sys
from datetime import datetime, timezone

import pytest
import pytest_asyncio
import requests
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient
from tests import qa_creds

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from intel_journey_seed import REP_ID, STORE_ID, TAG, draft as _draft, seed as _seed, wipe as _wipe  # noqa: E402

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8001").rstrip("/")
MONGO, DB_NAME = os.environ["MONGO_URL"], os.environ["DB_NAME"]
REP_EMAIL, REP_PASS = "activation-tester@invalid.imonsocial.test", qa_creds.password_for("activation-tester@invalid.imonsocial.test")
S: dict = {}                                 # state shared across the ordered steps


def _em(text: str) -> bool:
    return "\u2014" in (text or "") or "\u2013" in (text or "")


@pytest_asyncio.fixture(scope="session")
async def db():
    return AsyncIOMotorClient(MONGO)[DB_NAME]


@pytest.fixture(scope="module")
def rep_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": REP_EMAIL, "password": REP_PASS}, timeout=20)
    assert r.status_code == 200, r.text[:200]
    return r.json().get("token") or r.json().get("access_token")


@pytest.mark.asyncio
async def test_00_two_years_of_history_become_facts(db):
    """Jeep bought two years ago (sale record), camper voice memo 18 months ago, F-150 inquiry 2 days ago, towing text today: dated, sourced facts."""
    from services.intelligence import config, state
    assert config.ingest_enabled(), "INTEL_FACTS_INGEST must be on in preview"
    out = await _seed(db)
    S.update(cid=out["cid"], conv=out["conv"], f150_fact=out["f150_fact"], jeep_fact=out["jeep_fact"])
    assert out["purchases"]["created"] == 2 and out["memo"]["created"] == 2 and out["lead"]["action"] == "created", out
    assert out["text"].get("refreshed", 0) >= 1, out["text"]
    owned = await db.contact_facts.find_one({"_id": ObjectId(S["jeep_fact"])})
    assert owned["confirmations"] >= 1 and "Jeep" in owned["statement"] and owned["source"]["kind"] == "sale", owned
    contact = await db.contacts.find_one({"_id": ObjectId(S["cid"])})
    st = await state.build(db, contact, await config.settings(db, STORE_ID))
    assert st["driving"] and "F-150" in st["driving"]["label"] and st["driving"]["phase"] == "active", st["driving"]
    assert any(f["key"] == "vehicle.owned" and "Jeep" in f["label"] for f in st["current_state"])


@pytest.mark.asyncio
async def test_02_timeline_tells_the_story(db, rep_token):
    """2A: Recommended = the F-150, the Jeep is current (confirmed), the purchase is a marker, the camper is a known preference."""
    r = requests.get(f"{BASE_URL}/api/intel/contacts/{S['cid']}/timeline", headers={"Authorization": f"Bearer {rep_token}"}, timeout=30)
    assert r.status_code == 200, r.text[:300]
    tl = r.json()
    assert tl["enabled"] is True
    assert tl["recommended"]["mode"] == "active_intent" and "F-150" in tl["recommended"]["topic"], tl["recommended"]
    assert any("Jeep" in m for m in tl["recommended"]["mention_history"]), tl["recommended"]["mention_history"]
    assert any("F-150" in a["label"] for a in tl["active"]), tl["active"]
    drives = tl["current"]["drives"]
    assert any("Jeep" in d["label"] and d["confirmed"] for d in drives), drives
    assert any(m["kind"] == "purchase" and "Jeep" in m["title"] for m in tl["markers"]), tl["markers"]
    assert any("camper" in (p["label"] or "").lower() for p in tl["current"]["preferences"]), tl["current"]["preferences"]
    assert not _em(str(tl))


@pytest.mark.asyncio
async def test_03_reply_context_block(db, rep_token):
    """2B: the block Jessi reads leads with the F-150, keeps the Jeep as a trade question, and never invents."""
    r = requests.get(f"{BASE_URL}/api/intel/contacts/{S['cid']}/reply-context", headers={"Authorization": f"Bearer {rep_token}"}, timeout=30)
    assert r.status_code == 200, r.text[:300]
    rc = r.json()
    assert rc["enabled"] is True
    text = rc["text"]
    right_now = text.split("\n")[1]
    assert right_now.startswith("RIGHT NOW (lead with this)") and "F-150" in right_now, right_now
    assert "owns 2022 Jeep Wrangler" in text and "confirmed" in text, text
    assert "WORTH ASKING" in text and "Jeep" in text.split("WORTH ASKING")[1], text
    assert "camper" in text.lower()
    assert "DO NOT:" in text and "invent details" in text
    ids = {e["fact_id"] for e in rc["rationale"]["evidence"]}
    assert S["f150_fact"] in ids and S["jeep_fact"] in ids, rc["rationale"]
    assert rc["rationale"]["summary"].startswith("Based on:") and "F-150" in rc["rationale"]["summary"]
    assert not _em(text)
    S["rationale"] = rc["rationale"]


@pytest.mark.asyncio
async def test_04_jessi_suggests_in_the_reps_voice(rep_token):
    """2B: the 'Jessi suggests' draft answers the towing question about the F-150 first; the Jeep only as a trade / replace question; rationale attached."""
    r = requests.post(f"{BASE_URL}/api/messages/ai-suggest/{S['conv']}", headers={"Authorization": f"Bearer {rep_token}"}, json={}, timeout=60)
    assert r.status_code == 200, r.text[:300]
    j = r.json()
    text = (j.get("suggestion") or "")
    assert text, j
    low = text.lower()
    assert "f-150" in low or "f150" in low or "tow" in low, text
    if "jeep" in low or "wrangler" in low:
        assert any(w in low for w in ("trade", "replace", "replacing", "keep", "additional", "swap", "second")), text
    assert not _em(text), text
    assert j.get("intel_rationale") and S["f150_fact"] in {e["fact_id"] for e in j["intel_rationale"]["evidence"]}, j.get("intel_rationale")
    S["suggestion"] = text


@pytest.mark.asyncio
async def test_05_inbound_draft_carries_why_this_reply(db, rep_token):
    """2B: the inbound auto-draft (draft_only, nothing sent) lands in ai_reply_queue with intel_rationale and shows up in GET /ai-reply/pending."""
    doc = await _draft(db, S["cid"], S["conv"])
    assert doc, "no draft queued"
    assert doc["requires_approval"] is True and doc["status"] == "pending"
    assert not _em(doc["body"]), doc["body"]
    assert doc.get("intel_rationale") and S["f150_fact"] in {e["fact_id"] for e in doc["intel_rationale"]["evidence"]}, doc.get("intel_rationale")
    low = doc["body"].lower()
    if "jeep" in low or "wrangler" in low:
        assert any(w in low for w in ("trade", "replace", "replacing", "keep", "additional", "swap", "second")), doc["body"]
    await asyncio.sleep(0.5)
    r = requests.get(f"{BASE_URL}/api/ai-reply/pending/{REP_ID}", headers={"Authorization": f"Bearer {rep_token}"}, timeout=30)
    assert r.status_code == 200, r.text[:300]
    mine = [p for p in r.json()["pending"] if p["conversation_id"] == S["conv"]]
    assert mine and mine[0].get("intel_rationale", {}).get("summary", "").startswith("Based on:"), mine
    S["queue_id"] = doc["id"]


@pytest.mark.asyncio
async def test_06_nudge_once_and_only_once(db, rep_token):
    """2C: 'Ask Tom if the Jeep is a trade' (verified) is created exactly once; a pending Jessi draft blocks it; re-running writes nothing; dormant task never coexists."""
    from services.intelligence import nudges
    assert nudges.enabled(), "INTEL_NUDGES must be on in preview"
    contact = await db.contacts.find_one({"_id": ObjectId(S["cid"])})
    cands = await nudges.candidates(db, contact)
    trade = [c for c in cands if c["kind"] == "possible_trade"]
    assert trade and trade[0]["basis"] == "verified" and "Jeep" in trade[0]["title"], cands
    assert {e["fact_id"] for e in trade[0]["evidence"]} == {S["f150_fact"], S["jeep_fact"]}
    # the Jessi draft is still pending -> the trade question waits; the 2-year Jeep anniversary (today) is a milestone and goes through anyway
    r0 = await nudges.write(db, contact, cands)
    assert [c["kind"] for c in r0["created"]] == ["milestone"] and any(s["reason"] == "draft_pending" for s in r0["skipped"]), r0
    ms = await db.tasks.find_one({"contact_id": S["cid"], "intel_kind": "milestone"})
    assert ms and "2-year anniversary" in ms["title"] and "Jeep" in ms["title"] and ms["basis"] == "verified", ms
    await db.ai_reply_queue.update_one({"_id": ObjectId(S["queue_id"])}, {"$set": {"status": "rejected"}})
    now = datetime.now(timezone.utc)
    await db.tasks.insert_one({"user_id": REP_ID, "contact_id": S["cid"], "contact_name": "Tom Journey", "type": "follow_up", "source": "system", "title": "Reconnect with Tom Journey",
                               "status": "pending", "completed": False, "due_date": now, "created_at": now, "idempotency_key": f"dormant_{REP_ID}_{S['cid']}"})
    r1 = await nudges.write(db, contact, cands)
    assert len(r1["created"]) == 1 and r1["created"][0]["kind"] == "possible_trade" and r1["created"][0]["dormant_dismissed"] == 1, r1
    r2 = await nudges.write(db, contact, await nudges.candidates(db, contact))
    assert not r2["created"] and all(s["reason"] in ("exists", "open_same_kind") for s in r2["skipped"]), r2
    run = await nudges.run(db, user_id=REP_ID, contact_id=S["cid"])
    assert run["enabled"] and run["contacts"] == 1 and run["created"] == 0, run
    open_tasks = await db.tasks.find({"contact_id": S["cid"], "status": "pending"}).to_list(10)
    assert len(open_tasks) == 2 and all(t["source"] == "intelligence" and t["basis"] == "verified" for t in open_tasks), open_tasks
    trade_task = next(t for t in open_tasks if t["intel_kind"] == "possible_trade")
    assert trade_task["idempotency_key"] == f"intel_possible_trade_{S['cid']}_{S['f150_fact']}"
    assert not _em(trade_task["suggested_message"])
    dormant = await db.tasks.find_one({"idempotency_key": f"dormant_{REP_ID}_{S['cid']}"})
    assert dormant["status"] == "dismissed" and dormant["dismissed_reason"] == "intelligence_nudge"
    # surfaces: contact tasks + suggested actions
    hdr = {"Authorization": f"Bearer {rep_token}"}
    t = requests.get(f"{BASE_URL}/api/tasks/{REP_ID}/contact/{S['cid']}", headers=hdr, timeout=30).json()
    assert any(x.get("source") == "intelligence" and "Jeep" in x["title"] for x in t["tasks"]), t
    a = requests.get(f"{BASE_URL}/api/contacts/{REP_ID}/{S['cid']}/suggested-actions", headers=hdr, timeout=30).json()
    intel = [x for x in a["actions"] if x["type"] == "intel_possible_trade"]
    assert intel and intel[0]["basis"] == "verified" and "Verified fact" in intel[0]["description"], a
    p = requests.get(f"{BASE_URL}/api/intel/nudges/preview", params={"contact_id": S["cid"]}, headers=hdr, timeout=30).json()
    assert p["enabled"] and any(c["kind"] == "possible_trade" for c in p["candidates"]) and not p["would_create"], p


@pytest.mark.asyncio
async def test_07_bought_elsewhere_switches_everything_off(db, rep_token):
    """The customer closes the loop himself: the F-150 interest becomes history (lost), the reply block says no pitch, no new nudges."""
    from services.intelligence import ingest, nudges, reply_context
    contact = await db.contacts.find_one({"_id": ObjectId(S["cid"])})
    now = datetime.now(timezone.utc)
    mid = (await db.messages.insert_one({"conversation_id": S["conv"], "contact_id": S["cid"], "sender": "contact", "direction": "inbound", "channel": "sms",
                                          "content": "Appreciate it but we ended up buying a Ram from another dealer this weekend.", "timestamp": now, "status": "received"})).inserted_id
    out = await ingest.from_inbound_message(db, contact, S["conv"], "Appreciate it but we ended up buying a Ram from another dealer this weekend.", {"score": 1}, at=now, message_id=str(mid))
    assert out.get("purchased_elsewhere") == "created" and out.get("closed"), out
    rc = await reply_context.build(db, contact)
    assert "bought somewhere else" in rc["text"] and "No pitch" in rc["text"], rc["text"]
    assert rc["rationale"]["mode"] == "lost"
    assert "F-150" not in rc["text"].split("\n")[1]
    cands = await nudges.candidates(db, contact)
    assert not [c for c in cands if c["kind"] in ("possible_trade", "interest_aging")], cands
    tl = requests.get(f"{BASE_URL}/api/intel/contacts/{S['cid']}/timeline", headers={"Authorization": f"Bearer {rep_token}"}, timeout=30).json()
    assert tl["recommended"]["mode"] == "lost" and any(m["kind"] == "lost" for m in tl["markers"]), tl["recommended"]


@pytest.mark.asyncio
async def test_99_cleanup(db):
    await _wipe(db)
    assert await db.contacts.count_documents({"tags": TAG}) == 0
    assert await db.contact_facts.count_documents({"contact_id": S.get("cid", "x")}) == 0
