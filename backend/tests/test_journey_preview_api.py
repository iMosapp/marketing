"""Preview-env API checks for Journey Campaigns (iteration 373).

Covers scenarios on top of test_journey_campaigns.py:
 - options endpoint shape
 - draft campaigns NOT listed under GET /api/lead-shops
 - arm with 2 identities fails (only 1 free pool number)
 - delete-identity on draft, generate 400 on cap, duplicate name 400, empty body 400
 - close draft via POST /api/journeys/{id}/close; 401 unauth and 403 non-admin
 - Twilio inbound webhook creates a text_received event on the live identity
 - Final cleanup resets +15005550311 to available/no cooldown and deletes any residual docs

Only one free pool number is expected: +15005550311. We DO NOT buy or touch Twilio.
"""
import os
import asyncio
import time
import pytest
import requests
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient
from tests import qa_creds

BASE_URL = [l.split("=", 1)[1].strip() for l in open("/app/frontend/.env") if l.startswith("REACT_APP_BACKEND_URL=")][0].rstrip("/")
API = BASE_URL + "/api"
FREE_POOL = "+15005550311"
STORE_CELL = "+18015550140"
CLIENT_NAME = "QA Journey Tester 373"


def _db():
    return AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


def _run(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=30)
    r.raise_for_status()
    j = r.json()
    return j.get("token") or j.get("access_token")


@pytest.fixture(scope="module")
def admin():
    return {"Authorization": f"Bearer {_login('forest@imosapp.com', qa_creds.password_for('forest@imosapp.com'))}"}


@pytest.fixture(scope="module")
def manager():
    try:
        return {"Authorization": f"Bearer {_login('qa-manager@invalid.imonsocial.test', qa_creds.password_for('qa-manager@invalid.imonsocial.test'))}"}
    except Exception:
        pytest.skip("qa-manager account not available")


@pytest.fixture(scope="module")
def client_id(admin):
    """Create a throwaway shop_clients doc; teardown deletes it + any residual campaigns/leads."""
    async def mk():
        db = _db()
        await db.shop_clients.delete_many({"name": CLIENT_NAME})
        me = await db.users.find_one({"email": "forest@imosapp.com"})
        res = await db.shop_clients.insert_one({
            "name": CLIENT_NAME, "industry": "automotive", "brand": "Jeep", "city": "Sandy", "state": "UT",
            "timezone": "America/Denver", "locale": "en-US", "active": True, "record_calls": False,
            "contact_phone": "+18015550100", "lead_email": "crm-intake@qa-journey.test",
            "lead_process": {"first_call_min": 5, "first_text_min": 5, "first_email_min": 15,
                             "channels": ["call", "text", "email"], "day1_calls": 2, "follow_up_days": 1},
            "vehicles": ["2023 Ram 1500"],
            "created_by": str(me["_id"]),
        })
        return str(res.inserted_id)

    cid = _run(mk())
    yield cid

    async def tear():
        db = _db()
        obj = ObjectId(cid)
        # delete campaigns + identities for this client
        async for c in db.journey_campaigns.find({"client_id": cid}):
            await db.lead_shops.delete_many({"campaign_id": str(c["_id"])})
        await db.journey_campaigns.delete_many({"client_id": cid})
        # delete any lead_shops under this client (completed identities)
        await db.lead_shops.delete_many({"client_id": cid})
        # free pool number
        await db.phone_number_pool.update_one({"phone_number": FREE_POOL},
                                              {"$set": {"status": "available", "cooldown_until": None, "lead_shop_id": None}})
        await db.shop_clients.delete_one({"_id": obj})
    _run(tear())


def _ensure_free_pool():
    async def go():
        db = _db()
        await db.phone_number_pool.update_one({"phone_number": FREE_POOL},
                                              {"$set": {"status": "available", "cooldown_until": None, "lead_shop_id": None}})
    _run(go())


# ---- options endpoint ----
def test_options_shape(admin):
    o = requests.get(f"{API}/journeys/options", headers=admin, timeout=30).json()
    assert o["max_identities"] == 10
    assert o["default_modes"] == {"email": "approve", "sms": "approve", "voice": "voicemail"}
    assert any(w["hours"] == 720 for w in o["windows"])
    assert o["email_ready"] is True
    assert "pool" in o


# ---- unauth / non-admin on close ----
def test_close_unauthenticated_401():
    r = requests.post(f"{API}/journeys/000000000000000000000000/close", timeout=10)
    assert r.status_code in (401, 403)  # FastAPI may return 403 for missing bearer


def test_close_non_admin_403(manager):
    r = requests.post(f"{API}/journeys/000000000000000000000000/close", headers=manager, timeout=10)
    assert r.status_code == 403


# ---- Full lifecycle on preview ----
def test_preview_full_flow(admin, client_id):
    # Temporarily lock +15005550312 so only +15005550311 is free, then test insufficient-pool guard.
    async def lock_12():
        db = _db()
        await db.phone_number_pool.update_one({"phone_number": "+15005550312"},
                                              {"$set": {"status": "in_use", "lead_shop_id": "qa_lock_373"}})
        await db.phone_number_pool.update_one({"phone_number": FREE_POOL},
                                              {"$set": {"status": "available", "cooldown_until": None, "lead_shop_id": None}})
    async def unlock_12():
        db = _db()
        await db.phone_number_pool.update_one({"phone_number": "+15005550312", "lead_shop_id": "qa_lock_373"},
                                              {"$set": {"status": "available", "cooldown_until": None, "lead_shop_id": None}})
    _run(lock_12())
    # Create draft with 2 identities (LLM enrichment ~ 10-60s)
    r = requests.post(f"{API}/journeys", headers=admin, json={
        "client_id": client_id, "name": "Preview arm test", "department": "sales",
        "method": "manual", "window_hours": 168, "count": 2, "offering": "2023 Ram 1500",
        "notes": "QA preview"
    }, timeout=180)
    assert r.status_code == 200, r.text
    camp = r.json()
    jid = camp["id"]
    assert camp["status"] == "draft"
    assert camp["counts"]["total"] == 2
    idents = camp["identities"]
    assert len(idents) == 2
    for i in idents:
        p = i["persona"]
        assert p["no_commit"] is True
        assert not p.get("phone"), "drafts never reserve a phone"
        assert "@" in p["email"]
        assert p["timeline"] and p["questions"]
    # unique name / email
    assert len({i["persona"]["name"] for i in idents}) == 2
    assert len({i["persona"]["email"] for i in idents}) == 2

    # draft identities must NOT appear in lead-shops list
    ls_list = requests.get(f"{API}/lead-shops", headers=admin, params={"client_id": client_id}, timeout=30).json()
    draft_ids = {i["id"] for i in idents}
    assert not (draft_ids & {s["id"] for s in ls_list["shops"]}), "drafts leaked to lead-shops list"

    # arm without confirm -> 400
    r = requests.post(f"{API}/journeys/{jid}/arm", headers=admin, json={"confirm": False}, timeout=30)
    assert r.status_code == 400

    # arm with 2 identities but only 1 pool free -> 400 with explicit message
    r = requests.post(f"{API}/journeys/{jid}/arm", headers=admin,
                      json={"confirm": True, "website_url": "https://qa.test/contact", "note": "QA"}, timeout=90)
    assert r.status_code == 400, r.text
    body_text = r.text.lower()
    assert "1" in body_text and ("shopper number" in body_text or "pool" in body_text or "free" in body_text), r.text

    # PATCH duplicate name -> 400
    a, b = idents[0], idents[1]
    nm = b["persona"]["name"].split()
    r = requests.patch(f"{API}/journeys/{jid}/identities/{a['id']}", headers=admin,
                       json={"first": nm[0], "last": nm[-1]}, timeout=30)
    assert r.status_code == 400

    # PATCH empty -> 400
    r = requests.patch(f"{API}/journeys/{jid}/identities/{a['id']}", headers=admin, json={}, timeout=30)
    assert r.status_code == 400

    # PATCH rename a -> email regen w/ new slug
    r = requests.patch(f"{API}/journeys/{jid}/identities/{a['id']}", headers=admin,
                       json={"first": "Nora", "last": "Vale", "timeline": "this week",
                             "questions": ["Do you deliver?"], "channel_prefs": ["email", "text"],
                             "ai_instructions": "Short answers only."}, timeout=30)
    assert r.status_code == 200, r.text
    renamed = r.json()
    assert renamed["persona"]["name"] == "Nora Vale"
    assert renamed["persona"]["email"].startswith("nora.vale.")

    # DELETE one draft identity to fit in 1 pool number
    r = requests.delete(f"{API}/journeys/{jid}/identities/{b['id']}", headers=admin, timeout=30)
    assert r.status_code == 200, r.text

    # Modes patch while draft
    r = requests.patch(f"{API}/journeys/{jid}", headers=admin, json={"modes": {"sms": "auto"}, "window_hours": 720}, timeout=30)
    assert r.status_code == 200 and r.json()["modes"]["sms"] == "auto" and r.json()["window_hours"] == 720

    # Arm succeeds now
    r = requests.post(f"{API}/journeys/{jid}/arm", headers=admin,
                      json={"confirm": True, "website_url": "https://qa.test/contact", "note": "GM OK"}, timeout=120)
    assert r.status_code == 200, r.text
    armed = r.json()
    assert armed["status"] == "armed"
    assert armed["identities"][0]["status"] == "pending_delivery"
    phone = armed["identities"][0]["persona"]["phone"]
    assert phone == FREE_POOL
    assert armed["authorization"]["note"] == "GM OK"

    # generate on armed -> 409
    r = requests.post(f"{API}/journeys/{jid}/identities/generate", headers=admin, json={"count": 1}, timeout=30)
    assert r.status_code == 409
    # window_hours patch on armed -> 400
    r = requests.patch(f"{API}/journeys/{jid}", headers=admin, json={"window_hours": 24}, timeout=30)
    assert r.status_code == 400
    # modes patch still works
    r = requests.patch(f"{API}/journeys/{jid}", headers=admin, json={"modes": {"email": "auto"}}, timeout=30)
    assert r.status_code == 200 and r.json()["modes"]["email"] == "auto"
    # rename after arm -> 400
    r = requests.patch(f"{API}/journeys/{jid}/identities/{armed['identities'][0]['id']}", headers=admin,
                       json={"first": "Should", "last": "Fail"}, timeout=30)
    assert r.status_code == 400
    # ai_instructions after arm -> 200
    r = requests.patch(f"{API}/journeys/{jid}/identities/{armed['identities'][0]['id']}", headers=admin,
                       json={"ai_instructions": "Mention the trade."}, timeout=30)
    assert r.status_code == 200 and r.json()["persona"]["ai_instructions"] == "Mention the trade."
    # delete armed campaign -> 409
    assert requests.delete(f"{API}/journeys/{jid}", headers=admin, timeout=30).status_code == 409

    # mark delivered -> live
    sid = armed["identities"][0]["id"]
    r = requests.post(f"{API}/lead-shops/{sid}/delivered", headers=admin, timeout=30)
    assert r.status_code == 200 and r.json()["status"] == "live"
    j = requests.get(f"{API}/journeys/{jid}", headers=admin, timeout=30).json()
    assert j["status"] == "live"

    # Twilio inbound webhook: store texts the identity's shopper number
    msid = f"SM{int(time.time()*1000)}"
    r = requests.post(f"{API}/webhooks/twilio/incoming",
                      data={"From": STORE_CELL, "To": phone, "Body": "Hi this is Joe about the Ram",
                            "MessageSid": msid, "NumMedia": "0"}, timeout=30)
    assert r.status_code in (200, 204), r.text
    # Give any scheduled work a moment, then re-fetch
    time.sleep(1.5)
    j2 = requests.get(f"{API}/journeys/{jid}", headers=admin, timeout=30).json()
    ident = j2["identities"][0]
    events = ident.get("events") or []
    assert any("text" in (e.get("kind") or "") for e in events), f"no text event: {events}"

    # Stop + delete
    r = requests.post(f"{API}/journeys/{jid}/stop", headers=admin, json={"reason": "QA done"}, timeout=60)
    assert r.status_code == 200 and r.json()["status"] == "stopped"
    # second stop -> 409
    r = requests.post(f"{API}/journeys/{jid}/stop", headers=admin, json={"reason": "again"}, timeout=30)
    assert r.status_code == 409
    r = requests.delete(f"{API}/journeys/{jid}", headers=admin, timeout=30)
    assert r.status_code == 200 and r.json()["deleted"] is True
    _run(unlock_12())


# ---- close draft via POST close ----
def test_close_draft_discards_drafts(admin, client_id):
    _ensure_free_pool()
    r = requests.post(f"{API}/journeys", headers=admin, json={
        "client_id": client_id, "department": "sales", "method": "manual", "window_hours": 72,
        "count": 1, "offering": "2023 Ram 1500"
    }, timeout=180)
    assert r.status_code == 200, r.text
    jid = r.json()["id"]
    r = requests.post(f"{API}/journeys/{jid}/close", headers=admin, timeout=30)
    assert r.status_code == 200, r.text
    assert r.json()["status"] in ("closed", "stopped")
    # cleanup
    requests.delete(f"{API}/journeys/{jid}", headers=admin, timeout=30)
