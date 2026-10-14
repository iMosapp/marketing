"""Journey campaigns (Phase 2): campaign + virtual identities on top of Lead Shops, in-process with fakes for the outside
world (LLM enrichment, Twilio numbers, Resend, grading), plus the admin API against the running server.
Run: cd /app/backend && set -a && . ./.env && set +a && python -m pytest tests/test_journey_campaigns.py -q"""
import asyncio
import os
from datetime import timedelta

import pytest
import requests
from motor.motor_asyncio import AsyncIOMotorClient

from services import lead_shops as ls
from services import scripts as scr
from services import text_shops as tx
from services import email_shops as ems
from services.journey import campaigns as jc
from services.journey import identities as ids
from tests import qa_creds

BASE_URL = [l.split("=", 1)[1].strip() for l in open("/app/frontend/.env") if l.startswith("REACT_APP_BACKEND_URL=")][0].rstrip("/")
API = BASE_URL + "/api"
NUMBERS = ["+15005550321", "+15005550322", "+15005550323", "+15005550324"]
STORE_CELL = "+15005550998"


def _db():
    return AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


def _run(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.run_until_complete(asyncio.sleep(0.05))
        loop.close()


@pytest.fixture(scope="module")
def admin():
    r = requests.post(f"{API}/auth/login", json={"email": "forest@imosapp.com", "password": qa_creds.password_for("forest@imosapp.com")}, timeout=30)
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json().get('token') or r.json().get('access_token')}"}


@pytest.fixture()
def fakes(monkeypatch):
    sent = []

    async def fake_acquire(db, client, me):
        row = await db[ls.POOL].find_one_and_update({"phone_number": {"$in": NUMBERS}, "status": "available"}, {"$set": {"status": "in_use", "assigned_at": ls._now()}})
        assert row, "test pool exhausted"
        return row

    async def fake_enrich(client, campaign, bases):
        return [{"timeline": "this month", "personality": f"persona {i}: direct", "channel_prefs": ["text", "email"], "questions": ["Is it still available?", "Out the door price?"], "objections": ["Saw it cheaper elsewhere"], "ai_instructions": "Has a trade but only mentions it if asked."} for i in range(len(bases))]

    import resend
    monkeypatch.setattr(resend.Emails, "send", lambda payload: sent.append(payload) or {"id": f"em_{len(sent)}"})
    monkeypatch.setattr(ls, "acquire_number", fake_acquire)
    monkeypatch.setattr(ids, "_enrich", fake_enrich)
    monkeypatch.setattr(tx, "schedule_reply", lambda sid: None)
    monkeypatch.setattr(ems, "schedule_reply", lambda sid: None)

    async def fake_coach(*a, **k):
        return {"summary": "Quick text, no call.", "wins": [], "coaching": ["Call within 5 minutes"]}
    monkeypatch.setattr(ls, "_coach", fake_coach)
    return sent


async def _client_doc(db, name="QA Journey Motors", pool=3):
    me = await db.users.find_one({"email": "forest@imosapp.com"})
    await db.shop_clients.delete_many({"name": name})
    await db[ls.POOL].delete_many({"phone_number": {"$in": NUMBERS}})
    for n in NUMBERS[:pool]:
        await db[ls.POOL].insert_one({"phone_number": n, "twilio_sid": "PN_fake", "status": "available", "assigned_user_id": None, "purpose": ls.POOL_PURPOSE, "lead_shop_id": None, "cooldown_until": None, "monthly_cost_usd": 1.15, "purchased_at": ls._now(), "purchased_by": None})
    res = await db.shop_clients.insert_one({"name": name, "industry": "automotive", "brand": "Jeep", "city": "Sandy", "state": "UT", "timezone": "America/Denver", "locale": "en-US", "active": True, "record_calls": False,
                                            "contact_phone": "+18015550100", "lead_email": "crm-intake@qa-journey.test", "lead_process": {"first_call_min": 5, "first_text_min": 5, "first_email_min": 15, "channels": ["call", "text", "email"], "day1_calls": 2, "follow_up_days": 1},
                                            "vehicles": ["2022 Jeep Grand Cherokee", "2023 Ram 1500"], "created_at": ls._now(), "created_by": str(me["_id"])})
    return me, await db.shop_clients.find_one({"_id": res.inserted_id})


async def _cleanup(db, client):
    cid = str(client["_id"])
    ours = []
    async for s in db[ls.COLL].find({"client_id": cid}):
        ours.append(str(s["_id"]))
        await db.roleplay_sessions.delete_many({"lead_shop_id": str(s["_id"])})
    # a real preview pool number the server handed out goes back to free with no cooldown
    await db[ls.POOL].update_many({"$or": [{"last_lead_shop_id": {"$in": ours}}, {"lead_shop_id": {"$in": ours}}]}, {"$set": {"status": "available", "cooldown_until": None, "lead_shop_id": None}})
    await db[ls.COLL].delete_many({"client_id": cid})
    await db[jc.COLL].delete_many({"client_id": cid})
    await db[ls.POOL].delete_many({"phone_number": {"$in": NUMBERS}})
    await db.shop_clients.delete_one({"_id": client["_id"]})


def test_clean_fields_and_prompt_rules():
    f = ids.clean_fields({"timeline": "next week — maybe", "channel_prefs": ["sms", "bogus", "call", "text"], "questions": "Is it available?\nPrice?\n\n", "objections": ["a", "b", "c", "d"], "interest": " 2021 Ram 1500 ", "zzz": 1})
    assert f["timeline"] == "next week, maybe" and f["channel_prefs"] == ["text", "call"] and f["questions"] == ["Is it available?", "Price?"] and len(f["objections"]) == 3 and f["offering"] == "2021 Ram 1500" and "zzz" not in f
    rules = ids.prompt_rules({"timeline": "this month", "personality": "direct", "questions": ["Price?"], "channel_prefs": ["email"], "ai_instructions": "Works nights.", "no_commit": True})
    assert "YOUR TIMELINE: you plan to decide this month" in rules and "rather be reached by email" in rules and "HARD RULE" in rules and "Works nights." in rules
    assert ids.prompt_rules({"name": "plain"}) == ""
    sysprompt = scr._customer_system({"title": "t", "purpose": "p"}, {"name": "Avery Marsh", "summary": "s", "goals": "g", "no_commit": True, "questions": ["Still available?"]}, "QA Motors", "Joe", [], covert=True, channel="text")
    assert "never confirm a firm appointment" in sysprompt and "Still available?" in sysprompt
    assert jc.clean_modes({"email": "auto", "sms": "nope", "voice": "live"}) == {"email": "auto", "sms": "approve", "voice": "live"}
    assert jc._window(720) == 720 and jc._window(99) == 72


def test_campaign_lifecycle(fakes):
    async def go():
        db = _db()
        me, client = await _client_doc(db)
        try:
            camp = await jc.create(db, client, me, {"name": "Weekend BDC test", "department": "sales", "method": "manual", "window_hours": 720, "count": 3, "modes": {"email": "auto"}, "offering": "the 2022 Jeep Grand Cherokee"})
            assert camp["status"] == "draft" and camp["modes"] == {"email": "auto", "sms": "approve", "voice": "voicemail"} and camp["window_hours"] == 720 and camp["authorization"] is None
            rows = await jc.identities_of(db, camp)
            assert len(rows) == 3 and all(r["status"] == "draft" and r["campaign_id"] == str(camp["_id"]) and not r["persona"].get("phone") for r in rows)
            assert len({r["persona"]["name"] for r in rows}) == 3 and len({r["persona"]["email"] for r in rows}) == 3, "names and emails are unique inside a campaign"
            assert all(r["persona"]["no_commit"] is True and r["persona"]["timeline"] == "this month" and r["persona"]["questions"] and r["persona"]["objections"] == ["Saw it cheaper elsewhere"] for r in rows)
            assert all(r["window_hours"] == 720 and r["method"] == "manual" for r in rows)
            assert await db[ls.POOL].count_documents({"phone_number": {"$in": NUMBERS}, "status": "in_use"}) == 0, "drafts never reserve a number"

            # edit one identity: name + email follow, AI fields change; duplicate names are refused
            first = rows[0]
            upd = await ids.update(db, first, {"first": "Zed", "last": "Quartz", "timeline": "this week", "questions": ["Do you deliver?"], "channel_prefs": ["call"], "ai_instructions": "Short answers."})
            assert upd["persona"]["name"] == "Zed Quartz" and upd["persona"]["email"].startswith("zed.quartz.") and upd["persona"]["timeline"] == "this week" and upd["persona"]["questions"] == ["Do you deliver?"]
            with pytest.raises(ValueError):
                await ids.update(db, rows[1], {"first": "Zed", "last": "Quartz"})
            with pytest.raises(ValueError):
                await ids.update(db, rows[1], {})
            # remove one, add one more, cap at the limit
            await ids.remove(db, rows[2])
            await ids.generate(db, camp, client, me, 1)
            assert await db[ls.COLL].count_documents({"campaign_id": str(camp["_id"])}) == 3
            await db[jc.COLL].update_one({"_id": camp["_id"]}, {"$set": {"submission_limit": 3}})
            camp = await db[jc.COLL].find_one({"_id": camp["_id"]})
            with pytest.raises(ValueError):
                await ids.generate(db, camp, client, me, 1)
            view = await jc.serialize(db, camp, with_identities=True)
            assert view["counts"] == {"draft": 3, "pending_delivery": 0, "live": 0, "closing": 0, "completed": 0, "total": 3, "open": 0} and view["identities"][0]["persona"]["no_commit"] is True and view["window_label"] == "30 days"

            # arming needs the authorization confirm; then every draft gets a number and waits for the web form
            with pytest.raises(ValueError):
                await jc.arm(db, camp, client, me, {"confirm": False})
            camp = await jc.arm(db, camp, client, me, {"confirm": True, "website_url": "https://qa-journey.test/contact", "note": "GM approved"})
            assert camp["status"] == "armed" and camp["authorization"]["by"] == str(me["_id"]) and camp["authorization"]["website_url"].endswith("/contact") and not camp.get("arm_errors")
            rows = await jc.identities_of(db, camp)
            assert all(r["status"] == "pending_delivery" and r["persona"]["phone"] in NUMBERS for r in rows) and len({r["persona"]["phone"] for r in rows}) == 3
            shop, row = await ls.number_owner(db, rows[0]["persona"]["phone"])
            assert shop and shop["_id"] == rows[0]["_id"] and row["lead_shop_id"] == str(rows[0]["_id"])
            with pytest.raises(ValueError):
                await ids.update(db, rows[0], {"first": "Nope"})
            upd = await ids.update(db, rows[0], {"ai_instructions": "Mention the trade."})
            assert upd["persona"]["ai_instructions"] == "Mention the trade."

            # the admin submits the first web form: that identity goes live and so does the campaign
            await ls.mark_delivered(db, rows[0])
            camp = await db[jc.COLL].find_one({"_id": camp["_id"]})
            assert camp["status"] == "live"
            live = await db[ls.COLL].find_one({"_id": rows[0]["_id"]})
            assert live["status"] == "live" and ls._utc(live["expires_at"]) > ls._now() + timedelta(hours=719)
            # the store texts the live identity: the shopper's prompt carries its journey rules
            assert await ls.inbound_text(db, live["persona"]["phone"], STORE_CELL, "Hi, Joe from QA Journey Motors about the Grand Cherokee", "SMJ1")
            t = await db.roleplay_sessions.find_one({"lead_shop_id": str(live["_id"]), "mode": "text"})
            prompt = scr._customer_system({"title": "t", "purpose": "p"}, t["persona"], "QA Journey Motors", "Joe", [], covert=True, channel="text")
            assert "HARD RULE" in prompt and "Do you deliver?" in prompt and "Mention the trade." in prompt
            # the Lead Shops list never shows drafts, but shows armed identities
            listed = requests.get(f"{API}/lead-shops", headers=_admin_headers(), params={"client_id": str(client["_id"])}, timeout=30).json()["shops"]
            assert {s["status"] for s in listed} <= {"pending_delivery", "live"} and len(listed) == 3

            # emergency stop: everything open closes, numbers go back with a cooldown, campaign stopped
            camp = await jc.stop(db, camp, me, "GM called it off")
            await asyncio.sleep(0.3)
            assert camp["status"] == "stopped" and camp["emergency_stop"]["reason"] == "GM called it off"
            rows = await jc.identities_of(db, camp)
            assert all(r["status"] in ("closing", "completed") and r.get("close_reason") == "emergency_stop" for r in rows)
            assert await db[ls.POOL].count_documents({"phone_number": {"$in": NUMBERS}, "status": "available", "cooldown_until": {"$ne": None}}) == 3
            with pytest.raises(ValueError):
                await jc.stop(db, camp, me)
            # sweep closes nothing here (stopped is terminal); a fresh campaign whose identities all complete closes itself
            assert await jc.sweep(db) == 0
            await db[jc.COLL].update_one({"_id": camp["_id"]}, {"$set": {"status": "live"}})
            await db[ls.COLL].update_many({"campaign_id": str(camp["_id"])}, {"$set": {"status": "completed"}})
            assert await jc.sweep(db) == 1
            camp = await db[jc.COLL].find_one({"_id": camp["_id"]})
            assert camp["status"] == "closed"
            await jc.remove(db, camp)
            assert await db[jc.COLL].count_documents({"_id": camp["_id"]}) == 0
            assert await db[ls.COLL].count_documents({"client_id": str(client["_id"]), "campaign_id": {"$exists": False}}) == 3, "finished identities survive the campaign"
        finally:
            await _cleanup(db, client)
    _run(go())


def _admin_headers():
    r = requests.post(f"{API}/auth/login", json={"email": "forest@imosapp.com", "password": qa_creds.password_for("forest@imosapp.com")}, timeout=30)
    return {"Authorization": f"Bearer {r.json().get('token') or r.json().get('access_token')}"}


def test_adf_campaign_delivers_on_arm(fakes):
    async def go():
        db = _db()
        me, client = await _client_doc(db, "QA Journey ADF Motors")
        try:
            camp = await jc.create(db, client, me, {"department": "sales", "method": "adf", "window_hours": 72, "count": 2, "source_name": "Cars.com"})
            assert camp["name"].startswith("Sales journey")
            camp = await jc.arm(db, camp, client, me, {"confirm": True})
            assert camp["status"] == "live" and len(fakes) == 2 and all(p["to"] == ["crm-intake@qa-journey.test"] for p in fakes) and all("<adf>" in p["text"] for p in fakes)
            rows = await jc.identities_of(db, camp)
            assert all(r["status"] == "live" and r["events"][0]["kind"] == "delivered" and r["source_name"] == "Cars.com" for r in rows)
            camp = await jc.close(db, camp)
            await asyncio.sleep(0.3)
            assert camp["status"] == "closed" and all(r["status"] in ("closing", "completed") for r in await jc.identities_of(db, camp))
        finally:
            await _cleanup(db, client)
    _run(go())


def test_journeys_api(admin):
    """Against the real server (real LLM enrichment, ~10-30 s). A free pool number is seeded first so arming never buys a Twilio number."""
    async def mk():
        db = _db()
        return await _client_doc(db, "QA Journey API Motors", pool=1)
    me, client = _run(mk())
    cid = str(client["_id"])
    try:
        o = requests.get(f"{API}/journeys/options", headers=admin, timeout=30).json()
        assert o["max_identities"] == 10 and o["default_modes"]["email"] == "approve" and any(w["hours"] == 720 for w in o["windows"]) and o["email_ready"]
        created = requests.post(f"{API}/journeys", headers=admin, json={"client_id": cid, "name": "API journey", "department": "sales", "method": "manual", "window_hours": 168, "count": 1, "offering": "2023 Ram 1500", "notes": "Has a trade, works nights"}, timeout=120)
        assert created.status_code == 200, created.text
        camp = created.json()
        assert camp["status"] == "draft" and camp["counts"]["total"] == 1 and camp["identities"][0]["status"] == "draft" and camp["identities"][0]["persona"]["no_commit"] is True
        ident = camp["identities"][0]
        assert ident["persona"]["timeline"] and ident["persona"]["personality"] and ident["persona"]["questions"], "the LLM (or the fallback) fills the identity"
        assert requests.get(f"{API}/journeys", headers=admin, params={"client_id": cid}, timeout=30).json()["campaigns"][0]["id"] == camp["id"]
        p = requests.patch(f"{API}/journeys/{camp['id']}", headers=admin, json={"modes": {"sms": "auto"}, "window_hours": 720}, timeout=30).json()
        assert p["modes"]["sms"] == "auto" and p["window_hours"] == 720 and p["identities"][0]["window_hours"] == 720
        e = requests.patch(f"{API}/journeys/{camp['id']}/identities/{ident['id']}", headers=admin, json={"first": "Nora", "last": "Vale", "timeline": "this week", "questions": ["Do you deliver?", "Is the price firm?"], "channel_prefs": ["email", "text"]}, timeout=30).json()
        assert e["persona"]["name"] == "Nora Vale" and e["persona"]["email"].startswith("nora.vale.") and e["persona"]["questions"] == ["Do you deliver?", "Is the price firm?"] and e["persona"]["channel_prefs"] == ["email", "text"]
        assert requests.post(f"{API}/journeys/{camp['id']}/arm", headers=admin, json={"confirm": False}, timeout=30).status_code == 400
        armed = requests.post(f"{API}/journeys/{camp['id']}/arm", headers=admin, json={"confirm": True, "note": "QA"}, timeout=60)
        assert armed.status_code == 200, armed.text
        a = armed.json()
        assert a["status"] == "armed" and a["identities"][0]["status"] == "pending_delivery" and a["identities"][0]["persona"]["phone"] and a["authorization"]["note"] == "QA"
        assert requests.post(f"{API}/journeys/{camp['id']}/identities/generate", headers=admin, json={"count": 1}, timeout=30).status_code == 409
        assert requests.patch(f"{API}/journeys/{camp['id']}", headers=admin, json={"window_hours": 24}, timeout=30).status_code == 400
        assert requests.delete(f"{API}/journeys/{camp['id']}", headers=admin, timeout=30).status_code == 409
        d = requests.post(f"{API}/lead-shops/{ident['id']}/delivered", headers=admin, timeout=30).json()
        assert d["status"] == "live"
        assert requests.get(f"{API}/journeys/{camp['id']}", headers=admin, timeout=30).json()["status"] == "live"
        s = requests.post(f"{API}/journeys/{camp['id']}/stop", headers=admin, json={"reason": "QA done"}, timeout=60).json()
        assert s["status"] == "stopped" and s["emergency_stop"]["reason"] == "QA done"
        assert requests.delete(f"{API}/journeys/{camp['id']}", headers=admin, timeout=30).json()["deleted"] is True
    finally:
        async def cl():
            await _cleanup(_db(), client)
        _run(cl())
