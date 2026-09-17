"""Lead Shops end to end, in-process, with fakes for everything that touches the outside world (Resend send, Twilio number
buying / recording / SMS replies, LLM grading + coaching). Covers: create (ADF delivered, persona reachable), the store
calling back (AI persona over ConversationRelay), texting back, an auto-reply email + a human email, closing + scoring,
number release with cooldown, late calls after close, and the admin API.
Run: cd /app/backend && set -a && . ./.env && set +a && python -m pytest tests/test_lead_shops.py -q"""
import asyncio
import os
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace

import pytest
import requests
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

from services import lead_shops as ls
from services import scripts as scr
from services import text_shops as tx
from services import email_shops as ems
from services import mystery_shops as ms

BASE_URL = [l.split("=", 1)[1].strip() for l in open("/app/frontend/.env") if l.startswith("REACT_APP_BACKEND_URL=")][0].rstrip("/")
API = BASE_URL + "/api"
SHOPPER = "+15005550301"
STORE_CELL = "+15005550999"


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
    r = requests.post(f"{API}/auth/login", json={"email": "forest@imosapp.com", "password": "Admin123!"}, timeout=30)
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json().get('token') or r.json().get('access_token')}"}


@pytest.fixture()
def fakes(monkeypatch):
    sent = []

    async def fake_acquire(db, client, me):
        row = {"phone_number": SHOPPER, "twilio_sid": "PN_fake", "status": "in_use", "purpose": ls.POOL_PURPOSE, "lead_shop_id": None, "cooldown_until": None, "monthly_cost_usd": 1.15, "purchased_at": ls._now(), "assigned_at": ls._now()}
        res = await db[ls.POOL].insert_one(row)
        row["_id"] = res.inserted_id
        return row

    import resend
    monkeypatch.setattr(resend.Emails, "send", lambda payload: sent.append(payload) or {"id": f"em_{len(sent)}"})
    monkeypatch.setattr(ls, "acquire_number", fake_acquire)

    async def no_record(*a, **k):
        return None
    monkeypatch.setattr(ls, "_record_call", no_record)
    monkeypatch.setattr(tx, "schedule_reply", lambda sid: None)
    monkeypatch.setattr(ems, "schedule_reply", lambda sid: None)

    async def fake_grade(db, session):
        now = ls._now()
        ev = {"call_sid": f"RP_{session['_id']}", "roleplay_session_id": str(session["_id"]), "is_mystery_shop": True, "shop_client_id": session.get("client_id"), "score_pct": 80, "summary": "Solid, answered the question.",
              "wins": ["Named the store"], "coaching": ["Offer two times"], "channel": "text" if session.get("mode") == "text" else "email" if session.get("mode") == "email" else "call", "graded_by": "ai", "results": [], "created_at": now}
        await db.call_evaluations.update_one({"call_sid": ev["call_sid"]}, {"$set": ev}, upsert=True)
        ev_id = str((await db.call_evaluations.find_one({"call_sid": ev["call_sid"]}, {"_id": 1}))["_id"])
        await db.roleplay_sessions.update_one({"_id": session["_id"]}, {"$set": {"status": "completed", "ended_at": now, "evaluation_id": ev_id, "score_pct": 80}})
        await ms.after_graded(db, str(session["_id"]))
        return {"evaluation_id": ev_id, "score_pct": 80}
    monkeypatch.setattr(scr, "grade_session", fake_grade)

    async def fake_coach(*a, **k):
        return {"summary": "Fast call, slow email.", "wins": ["Called in 2 minutes"], "coaching": ["Email within 15 minutes"]}
    monkeypatch.setattr(ls, "_coach", fake_coach)
    return sent


async def _client_doc(db):
    me = await db.users.find_one({"email": "forest@imosapp.com"})
    await db.shop_clients.delete_many({"name": "QA Lead Shop Motors"})
    res = await db.shop_clients.insert_one({"name": "QA Lead Shop Motors", "industry": "automotive", "brand": "Jeep", "city": "Sandy", "state": "UT", "timezone": "America/Denver", "locale": "en-US", "active": True, "record_calls": True,
                                            "contact_phone": "+18015550100", "lead_email": "crm-intake@qa-leadshop.test", "lead_process": {"first_call_min": 5, "first_text_min": 5, "first_email_min": 15, "channels": ["call", "text", "email"], "day1_calls": 2, "follow_up_days": 1},
                                            "vehicles": ["2022 Jeep Grand Cherokee"], "created_at": ls._now(), "created_by": str(me["_id"])})
    return me, await db.shop_clients.find_one({"_id": res.inserted_id})


async def _cleanup(db, client):
    cid = str(client["_id"])
    async for s in db[ls.COLL].find({"client_id": cid}):
        await db.roleplay_sessions.delete_many({"lead_shop_id": str(s["_id"])})
        await db.call_evaluations.delete_many({"roleplay_session_id": {"$in": [str(x["_id"]) async for x in db.roleplay_sessions.find({"lead_shop_id": str(s["_id"])}, {"_id": 1})]}})
    await db[ls.COLL].delete_many({"client_id": cid})
    await db[ls.POOL].delete_many({"phone_number": SHOPPER})
    await db.shop_clients.delete_one({"_id": client["_id"]})
    await db.notifications.delete_many({"type": "lead_shop_graded"})


def test_process_and_adf():
    p = ls.clean_process({"first_call_min": "3", "channels": ["email", "bogus"], "day1_calls": 99, "must": ["A", ""]})
    assert p["first_call_min"] == 3 and p["channels"] == ["email"] and p["day1_calls"] == 14 and p["must"] == ["A"]
    shop = {"_id": ObjectId(), "created_at": datetime(2026, 6, 1, 15, 0, tzinfo=timezone.utc), "source_name": "Website",
            "persona": {"first": "Sam", "last": "Rivera", "email": "sam.rivera.42@imosapp.com", "phone": SHOPPER, "vehicle": "the 2022 Jeep Grand Cherokee", "goals": "Is it still available & out-the-door price?"}}
    xml = ls.adf_xml(shop, {"name": "QA Motors", "city": "Sandy", "state": "UT", "industry": "automotive"})
    assert "<?adf version=\"1.0\"?>" in xml and "<year>2022</year>" in xml and "<make>Jeep</make>" in xml and "<model>Grand Cherokee</model>" in xml
    assert "sam.rivera.42@imosapp.com" in xml and SHOPPER in xml and "&amp;" in xml and "<vendorname>QA Motors</vendorname>" in xml
    assert ls._speed_pts(3, 5) == 100 and ls._speed_pts(None, 5) == 0 and ls._speed_pts(30, 5) == 15 and 15 < ls._speed_pts(10, 5) < 100


def test_lead_shop_lifecycle(fakes):
    async def go():
        db = _db()
        me, client = await _client_doc(db)
        try:
            shop = await ls.create(db, client, me, {"method": "adf", "window_hours": 24, "department": "sales", "offering": "the 2022 Jeep Grand Cherokee"})
            assert shop["status"] == "live" and shop["persona"]["phone"] == SHOPPER and shop["persona"]["email"].endswith("@" + ls.inbound_domain())
            assert shop["events"][0]["kind"] == "delivered" and shop["delivery"]["email_id"] == "em_1"
            assert fakes[0]["to"] == ["crm-intake@qa-leadshop.test"] and fakes[0]["reply_to"] == shop["persona"]["email"] and "<adf>" in fakes[0]["text"] and fakes[0]["attachments"][0]["filename"] == "lead.xml"
            assert "online inquiry" in shop["persona"]["summary"]
            pool = await db[ls.POOL].find_one({"phone_number": SHOPPER})
            assert pool["lead_shop_id"] == str(shop["_id"])

            # 1) the store calls the shopper 2 minutes later: AI answers in persona
            twiml = await ls.inbound_call(db, SHOPPER, STORE_CELL, "CA_lead_1")
            assert "<ConversationRelay" in twiml and "welcomeGreeting=" in twiml
            call = await db.roleplay_sessions.find_one({"lead_shop_id": str(shop["_id"]), "mode": "phone"})
            assert call["direction"] == "outbound" and call["status"] == "live" and call["rep_phone"] == STORE_CELL and call["notify_sms"] is False and call["manual"] is True
            sysprompt = scr._customer_system({"title": "t", "purpose": "p"}, call["persona"], "QA Lead Shop Motors", "Joe", [], live=True, direction="outbound", mystery=True, industry="automotive", department="sales", covert=True)
            assert "Nobody at the business knows this is a shop" in sysprompt and "practice call" not in sysprompt
            await db.roleplay_sessions.update_one({"_id": call["_id"]}, {"$push": {"turns": {"$each": [{"role": "customer", "text": "Hello?", "at": ls._now()}, {"role": "rep", "text": "Hi Sam, Joe from QA Motors about the Grand Cherokee", "at": ls._now()}]}}})
            await scr.finalize_session(db, str(call["_id"]), "call_completed")
            await asyncio.sleep(0.2)
            shop = await db[ls.COLL].find_one({"_id": shop["_id"]})
            kinds = [e["kind"] for e in shop["events"]]
            assert "call_answered" in kinds and "graded" in kinds and shop["status"] == "live", "grading a call must not close a live shop"

            # 2) the store texts: a text thread opens on the lead shop and the rep turn is stored
            assert await ls.inbound_text(db, SHOPPER, STORE_CELL, "Hi Sam, Joe here from QA Motors. Still interested in the Grand Cherokee?", "SM1")
            t = await db.roleplay_sessions.find_one({"lead_shop_id": str(shop["_id"]), "mode": "text"})
            assert t and t["turns"][0]["role"] == "rep" and t["from_number"] == SHOPPER and t["rep_phone"] == STORE_CELL
            assert await ls.inbound_text(db, SHOPPER, STORE_CELL, "We have it in silver too", "SM2")
            t = await db.roleplay_sessions.find_one({"_id": t["_id"]})
            assert len(t["turns"]) == 2

            # 3) CRM auto-reply first (counts as an email touch, shopper does not answer a robot), then a human email
            shop = await db[ls.COLL].find_one({"_id": shop["_id"]})
            assert await ls.inbound_email(db, shop, "noreply@crm.test", "Thank you for your inquiry", "We have received your request and will be in touch.", "e1")
            e = await db.roleplay_sessions.find_one({"lead_shop_id": str(shop["_id"]), "mode": "email"})
            assert e and e["turns"] == [] and e["lead_from"].endswith(f"<{shop['persona']['email']}>")
            shop = await db[ls.COLL].find_one({"_id": shop["_id"]})
            await db[ls.COLL].update_one({"_id": shop["_id"]}, {"$set": {"started_at": ls._now() - timedelta(minutes=2)}})   # move the clock past AUTO_REPLY_S so the next email is not "quick"
            shop = await db[ls.COLL].find_one({"_id": shop["_id"]})
            assert await ls.inbound_email(db, shop, "joe@qamotors.test", "Re: your inquiry", "Hi Sam, Joe here. It is available, want to come see it Saturday at 10?", "e2")
            e = await db.roleplay_sessions.find_one({"_id": e["_id"]})
            assert len(e["turns"]) == 1 and e["turns"][0]["role"] == "rep" and e["rep_email"] == "joe@qamotors.test"
            shop = await db[ls.COLL].find_one({"_id": shop["_id"]})
            kinds = [x["kind"] for x in shop["events"]]
            assert kinds.count("auto_reply") == 1 and kinds.count("email_received") == 1 and kinds.count("text_received") == 2
            assert (await ls.lead_shop_for_email(db, [{"email": shop["persona"]["email"].upper()}]))["_id"] == shop["_id"]
            view = await ls.serialize(db, shop, with_sessions=True)
            assert view["counts"] == {"call": 1, "text": 2, "email": 2} and len(view["conversations"]) == 3 and view["events"][0]["since"] in ("+1m", "+2m")  # clock was moved back 2 min above

            # 4) close: text + email threads grade (fake), the shop scores itself, number goes back to the pool with a cooldown
            await ls.close(db, shop, "closed_by_admin")
            await asyncio.sleep(0.3)
            shop = await db[ls.COLL].find_one({"_id": shop["_id"]})
            assert shop["status"] == "completed", shop.get("status")
            sc = shop["score"]
            assert sc["per_channel"]["call"]["first_minutes"] is not None and sc["per_channel"]["call"]["speed_pts"] == 100
            assert sc["per_channel"]["email"]["human_count"] == 1 and sc["per_channel"]["email"]["count"] == 2
            assert sc["quality"] == 80 and sc["parts"]["coverage"] == 100 and sc["day1_calls"] == 1 and sc["parts"]["effort"] == 50
            assert 0 < sc["overall"] <= 100 and sc["summary"] == "Fast call, slow email." and len(sc["timeline"]) >= 5
            pool = await db[ls.POOL].find_one({"phone_number": SHOPPER})
            assert pool["status"] == "available" and pool["lead_shop_id"] is None and pool["last_lead_shop_id"] == str(shop["_id"]) and pool["cooldown_until"] > datetime.utcnow() + timedelta(days=10)
            assert await db.notifications.find_one({"type": "lead_shop_graded", "user_id": str(me["_id"])})

            # 5) a late call to the cooling number: voicemail, logged on the closed shop, no new session
            twiml = await ls.inbound_call(db, SHOPPER, STORE_CELL, "CA_late")
            assert "<Record" in twiml and "<ConversationRelay" not in twiml
            shop = await db[ls.COLL].find_one({"_id": shop["_id"]})
            assert shop["events"][-1]["kind"] == "late_call"
            assert await db.roleplay_sessions.count_documents({"lead_shop_id": str(shop["_id"])}) == 3
            assert await ls.inbound_text(db, SHOPPER, STORE_CELL, "late text", "SM9") is True
            assert (await ls.number_owner(db, "+15005550000")) == (None, None)

            # 6) manual method: identity card, clock starts on 'delivered'
            fakes.clear()
            await db[ls.POOL].update_one({"phone_number": SHOPPER}, {"$set": {"cooldown_until": None}})
            manual = await ls.create(db, client, me, {"method": "manual", "window_hours": 72})
            assert manual["status"] == "pending_delivery" and manual["started_at"] is None and not fakes
            card = ls.identity_card(manual)
            assert card["phone"] and card["email"] and card["name"]
            assert "<Record" in await ls.inbound_call(db, manual["persona"]["phone"], STORE_CELL, "CA_early"), "nothing rings the persona before the lead is delivered"
            await ls.mark_delivered(db, manual)
            manual = await db[ls.COLL].find_one({"_id": manual["_id"]})
            assert manual["status"] == "live" and manual["expires_at"] > datetime.utcnow() + timedelta(hours=71)
            await db[ls.COLL].update_one({"_id": manual["_id"]}, {"$set": {"expires_at": ls._now() - timedelta(minutes=1)}})
            await ls.sweep(db)
            await asyncio.sleep(0.2)
            manual = await db[ls.COLL].find_one({"_id": manual["_id"]})
            assert manual["status"] == "completed" and manual["score"]["overall"] == 0 and manual["score"]["no_contact"] is True
        finally:
            await _cleanup(db, client)
    _run(go())


def test_lead_shop_api(admin, fakes):
    """Against the real server, so the fakes above do not apply there: seed a free pool number FIRST or the server buys a real Twilio number."""
    async def mk():
        db = _db()
        await db[ls.POOL].delete_many({"phone_number": SHOPPER})
        await db[ls.POOL].insert_one({"phone_number": SHOPPER, "twilio_sid": "PN_fake_api", "status": "available", "assigned_user_id": None, "purpose": ls.POOL_PURPOSE, "lead_shop_id": None, "cooldown_until": None, "monthly_cost_usd": 1.15, "purchased_at": ls._now(), "purchased_by": None})
        return await _client_doc(db)
    me, client = _run(mk())
    cid = str(client["_id"])
    try:
        s = requests.get(f"{API}/lead-shops/setup/{cid}", headers=admin, timeout=30).json()
        assert s["lead_email"] == "crm-intake@qa-leadshop.test" and s["lead_process"]["first_call_min"] == 5 and s["email_ready"] and "pool" in s
        assert any(n["phone"] == SHOPPER and n["status"] == "available" for n in s["pool"]["numbers"]), "seeded pool number must be free before creating a shop"
        bad = requests.put(f"{API}/lead-shops/setup/{cid}", headers=admin, json={"lead_email": "not-an-email"}, timeout=30)
        assert bad.status_code == 400
        ok = requests.put(f"{API}/lead-shops/setup/{cid}", headers=admin, json={"lead_process": {"first_call_min": 2, "channels": ["call", "text"]}}, timeout=30).json()
        assert ok["lead_process"]["first_call_min"] == 2 and ok["lead_process"]["channels"] == ["call", "text"]
        created = requests.post(f"{API}/lead-shops", headers=admin, json={"client_id": cid, "method": "manual", "window_hours": 24, "offering": "2021 Ram 1500"}, timeout=60)
        assert created.status_code == 200, created.text
        shop = created.json()
        assert shop["status"] == "pending_delivery" and shop["persona"]["phone"] == SHOPPER and shop["process"]["channels"] == ["call", "text"] and shop["window_label"] == "24 hours"
        detail = requests.get(f"{API}/lead-shops/{shop['id']}", headers=admin, timeout=30).json()
        assert detail["identity_card"]["name"] == shop["persona"]["name"] and detail["adf_preview"] is None
        lst = requests.get(f"{API}/lead-shops", headers=admin, params={"client_id": cid}, timeout=30).json()
        assert any(x["id"] == shop["id"] for x in lst["shops"])
        d = requests.post(f"{API}/lead-shops/{shop['id']}/delivered", headers=admin, timeout=30).json()
        assert d["status"] == "live" and d["events"][0]["kind"] == "delivered"
        assert requests.post(f"{API}/lead-shops/{shop['id']}/delivered", headers=admin, timeout=30).status_code == 409
        assert requests.delete(f"{API}/lead-shops/{shop['id']}", headers=admin, timeout=30).status_code == 409
        closed = requests.post(f"{API}/lead-shops/{shop['id']}/close", headers=admin, timeout=60).json()
        assert closed["status"] in ("completed", "closing")
        assert requests.delete(f"{API}/lead-shops/{shop['id']}", headers=admin, timeout=30).json()["deleted"] is True
        nums = requests.get(f"{API}/lead-shops/numbers", headers=admin, timeout=30).json()
        assert "cap" in nums
    finally:
        async def cl():
            await _cleanup(_db(), client)
        _run(cl())
