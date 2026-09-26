"""Website Widget (Phase 1: Text us + Call me now).

API cases hit the running backend (REACT_APP_BACKEND_URL); the ring-group case runs in-process with WIDGET_RING_DRY_RUN
so no phone rings. Everything it creates uses 500-555 numbers and is cleaned up.

    cd /app/backend && set -a && . ./.env && . ../frontend/.env && set +a && python -m pytest tests/test_website_widget.py -q
"""
import asyncio
import base64
import json
import os
import time

import pytest
import requests
from bson import ObjectId

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
STORE = "69a0b7095fddcede09591668"
REP = "activation-tester@invalid.imonsocial.test"
RUN = str(int(time.time()))[-6:]
TEXT_PHONE = f"+1500555{RUN[-4:].rjust(4, '1')}"
CALL_PHONE = f"+1500556{RUN[-4:].rjust(4, '2')}"


def _login(email, pw):
    r = requests.post(f"{BASE}/api/auth/login", json={"email": email, "password": pw}, timeout=30)
    r.raise_for_status()
    tok = r.json().get("token") or r.json().get("access_token")
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def mgr():
    return _login("qa-manager@invalid.imonsocial.test", "Manager123!")


@pytest.fixture(scope="module")
def rep():
    return _login(REP, "NewPass123!")


@pytest.fixture(scope="module")
def widget(mgr):
    r = requests.post(f"{BASE}/api/widgets", json={"store_id": STORE}, headers=mgr, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["widget"]


LOOP = asyncio.new_event_loop()


def run(coro):
    return LOOP.run_until_complete(coro)


def _db():
    from routers.database import get_db
    return get_db()


# ---------------------------------------------------------------- pure config rules
def test_normalize_config_guards():
    from services import widgets as W
    cfg = W.normalize_config({"appearance": {"bubble_color": "zzz", "icon": "nope", "radius": 999, "label": "x" * 50}, "routing": {"ring_seconds": 5, "assignment_method": "bad", "call_user_ids": ["a"] * 40}, "hours": {"mode": "weird"}})
    assert cfg["appearance"]["bubble_color"] == "#2196F3" and cfg["appearance"]["icon"] == "text" and cfg["appearance"]["radius"] == 32 and len(cfg["appearance"]["label"]) == 30
    assert cfg["routing"]["ring_seconds"] == 15 and cfg["routing"]["assignment_method"] == "round_robin" and len(cfg["routing"]["call_user_ids"]) == 25
    assert cfg["hours"]["mode"] == "store"
    assert W.contrast_text("#FFFFFF") == "#111111" and W.contrast_text("#1D4ED8") == "#FFFFFF"
    assert W.domain_ok({"domains": ["qa-dealer.test"]}, "https://www.qa-dealer.test/x") and W.domain_ok({"domains": ["qa-dealer.test"]}, "https://shop.qa-dealer.test/")
    assert not W.domain_ok({"domains": ["qa-dealer.test"]}, "https://evil.test/") and W.domain_ok({"domains": []}, "https://anything.test/")
    assert W.clean_phone("(500) 555-0141") == "+15005550141" and W.clean_phone("123") == ""


# ---------------------------------------------------------------- manager API
def test_one_widget_per_store_and_scope(mgr, rep, widget):
    again = requests.post(f"{BASE}/api/widgets", json={"store_id": STORE}, headers=mgr, timeout=30).json()
    assert again["existing"] is True and again["widget"]["id"] == widget["id"]
    lst = requests.get(f"{BASE}/api/widgets", headers=mgr, timeout=30).json()
    assert any(w["id"] == widget["id"] for w in lst["widgets"]) and lst["can_manage"] is True
    assert next(s for s in lst["stores"] if s["id"] == STORE)["has_widget"] is True
    assert widget["snippet"].startswith("<script src=") and f"/api/w/{widget['key']}.js" in widget["snippet"]
    # a rep can look but not touch
    assert requests.get(f"{BASE}/api/widgets/{widget['id']}", headers=rep, timeout=30).status_code == 200
    assert requests.put(f"{BASE}/api/widgets/{widget['id']}", json={"name": "x"}, headers=rep, timeout=30).status_code == 403
    assert requests.post(f"{BASE}/api/widgets", json={"store_id": STORE}, headers=rep, timeout=30).status_code == 403
    assert requests.get(f"{BASE}/api/widgets", timeout=30).status_code == 401
    assert requests.post(f"{BASE}/api/widgets", json={"store_id": str(ObjectId())}, headers=mgr, timeout=30).status_code == 403


def test_update_reflects_in_script_and_demo(mgr, widget):
    body = {"appearance": {"bubble_color": "#dc2626", "label": "Text Our Team", "position": "left"}, "doors": {"call": {"label": "Ring me"}}, "domains": ["https://www.QA-Dealer.test/inventory", "other.test"], "name": "QA Widget"}
    r = requests.put(f"{BASE}/api/widgets/{widget['id']}", json=body, headers=mgr, timeout=30)
    assert r.status_code == 200, r.text
    w = r.json()["widget"]
    assert w["appearance"]["bubble_color"] == "#DC2626" and w["appearance"]["text_color"] == "#FFFFFF" and w["appearance"]["position"] == "left"
    assert w["doors"]["call"]["label"] == "Ring me" and w["doors"]["text"]["on"] is True and w["domains"] == ["qa-dealer.test", "other.test"] and w["name"] == "QA Widget"
    js = requests.get(f"{BASE}/api/w/{widget['key']}.js", timeout=30)
    assert js.status_code == 200 and js.headers["content-type"].startswith("application/javascript") and '"bubble_color":"#DC2626"' in js.text and "Text Our Team" in js.text
    demo = requests.get(f"{BASE}/api/w/{widget['key']}/demo", timeout=30)
    assert demo.status_code == 200 and "IMOS_WIDGET_PREVIEW = true" in demo.text and '"preview":true' in demo.text
    # unsaved preview override rides in ?c=
    c = base64.urlsafe_b64encode(json.dumps({"appearance": {"bubble_color": "#16A34A"}}).encode()).decode().rstrip("=")
    over = requests.get(f"{BASE}/api/w/{widget['key']}/demo", params={"c": c}, timeout=30)
    assert '"bubble_color":"#16A34A"' in over.text and "#DC2626" not in over.text
    # the lead source behind the widget follows the routing
    detail = requests.get(f"{BASE}/api/widgets/{widget['id']}", headers=mgr, timeout=30).json()
    assert detail["widget"]["lead_source_id"] and isinstance(detail["reps"], list) and "store_hours" in detail and detail["demo_url"].endswith(f"/api/w/{widget['key']}/demo")
    assert requests.get(f"{BASE}/api/w/nope1234.js", timeout=30).status_code == 404


# ---------------------------------------------------------------- public: Text us
def test_text_us_creates_a_lead_through_the_pipeline(mgr, widget):
    key = widget["key"]
    # wrong site -> blocked (domains were set above)
    r = requests.post(f"{BASE}/api/w/{key}/text", json={"name": "Eve", "phone": TEXT_PHONE, "page": "https://evil.test/"}, timeout=30)
    assert r.status_code == 403
    r = requests.post(f"{BASE}/api/w/{key}/text", json={"name": "Wendy", "phone": "123", "page": "https://www.qa-dealer.test/"}, timeout=30)
    assert r.status_code == 400
    ok = requests.post(f"{BASE}/api/w/{key}/text", json={"name": f"Wendy Widget{RUN}", "phone": TEXT_PHONE, "message": "Still have the crew cab?", "page": "https://www.qa-dealer.test/inventory/9", "title": "Crew Cab", "visitor": f"v{RUN}"}, timeout=60)
    assert ok.status_code == 200, ok.text
    j = ok.json()
    assert j["ok"] is True and j["lead_id"] and "message" in j
    # honeypot: pretend success, create nothing
    hp = requests.post(f"{BASE}/api/w/{key}/text", json={"name": "Bot", "phone": "5005550199", "website": "http://spam", "page": "https://www.qa-dealer.test/"}, timeout=30).json()
    assert hp["ok"] is True and "lead_id" not in hp
    # same phone twice more right away -> the third is throttled (2 per 2 minutes per phone)
    requests.post(f"{BASE}/api/w/{key}/text", json={"name": "Wendy", "phone": TEXT_PHONE, "page": "https://www.qa-dealer.test/"}, timeout=60)
    again = requests.post(f"{BASE}/api/w/{key}/text", json={"name": "Wendy", "phone": TEXT_PHONE, "page": "https://www.qa-dealer.test/"}, timeout=30)
    assert again.status_code == 400 and "wait" in again.json()["detail"].lower()
    assert requests.post(f"{BASE}/api/w/{key}/event", json={"kind": "open", "page": "https://www.qa-dealer.test/", "visitor": f"v{RUN}"}, timeout=30).json()["ok"] is True
    detail = requests.get(f"{BASE}/api/widgets/{widget['id']}", headers=mgr, timeout=30).json()
    assert detail["stats"]["text_leads"] >= 1 and detail["stats"]["opens"] >= 1 and detail["widget"]["installed"] is True and detail["widget"]["last_seen_host"] == "qa-dealer.test"

    async def check():
        db = _db()
        lead = await db.inbound_leads.find_one({"_id": ObjectId(j["lead_id"])})
        assert lead and lead["phone"] == TEXT_PHONE and lead["source_name"].startswith("Website Widget") and "Still have the crew cab?" in lead["comments"]
        src = await db.lead_sources.find_one({"_id": ObjectId(detail["widget"]["lead_source_id"])})
        assert src["kind"] == "website_widget" and src["widget_id"] == widget["id"]
        contact = await db.contacts.find_one({"_id": ObjectId(lead["contact_id"])})
        assert contact and contact.get("first_name") == "Wendy"
    run(check())


# ---------------------------------------------------------------- Call me now: ring group, first to press 1 wins (dry run)
def test_call_me_now_ring_group_first_press_wins(mgr, widget):
    assert os.environ.get("WIDGET_RING_DRY_RUN", "").lower() == "true", "set WIDGET_RING_DRY_RUN=true so no phone rings"
    from services import widgets as W, widget_calls as WC

    async def flow():
        db = _db()
        rep = await db.users.find_one({"email": REP})
        w = await db[W.COLL].find_one({"_id": ObjectId(widget["id"])})
        await db[W.COLL].update_one({"_id": w["_id"]}, {"$set": {"hours.mode": "always", "routing.call_user_ids": [str(rep["_id"])], "routing.ring_seconds": 20}})
        w = await db[W.COLL].find_one({"_id": w["_id"]})
        reps = await WC.available_reps(db, w)
        assert [str(u["_id"]) for u in reps] == [str(rep["_id"])]
        res = await WC.request_call(db, w, {"name": f"Carl Caller{RUN}", "phone": CALL_PHONE, "page": "https://www.qa-dealer.test/specials", "visitor": f"c{RUN}"}, "9.9.9.9")
        assert res["status"] == "ringing" and res["request_id"], res
        req = await db[WC.COLL].find_one({"_id": ObjectId(res["request_id"])})
        assert req["status"] == "ringing" and len(req["legs"]) == 1 and req["legs"][0]["status"] == "ringing" and req["legs"][0]["call_sid"].startswith("CAdry") and req["legs"][0]["to"] == "+15005550006"
        assert req["contact_id"] and req["lead_id"] and req["conversation_id"]
        tok = req["legs"][0]["token"]
        gather = await WC.ring_twiml(db, res["request_id"], tok)
        assert "<Gather" in gather and f"Carl Caller{RUN}" in gather and "qa-dealer.test" in gather and f"/api/w/ring-answer/{res['request_id']}/{tok}" in gather
        assert "<Hangup/>" in await WC.ring_twiml(db, res["request_id"], "badtoken")
        # rep presses 2 -> released; presses 1 -> wins and the visitor is dialed
        assert "releasing" in (await WC.answer_twiml(db, res["request_id"], tok, "2")).lower()
        bridge = await WC.answer_twiml(db, res["request_id"], tok, "1")
        assert "<Dial" in bridge and f"<Number statusCallback=\"{W.app_url()}/api/w/ring-customer/{res['request_id']}\"" in bridge and CALL_PHONE in bridge
        req = await db[WC.COLL].find_one({"_id": req["_id"]})
        assert req["status"] == "connecting" and req["winner_user_id"] == str(rep["_id"]) and req["pending_call_id"]
        pc = await db.pending_calls.find_one({"widget_request_id": str(req["_id"])})
        assert pc and pc["customer_phone"] == CALL_PHONE and pc["rep_user_id"] == str(rep["_id"]) and pc["source"] == "website_widget"
        # a second press 1 (another leg / replay) cannot steal it
        assert "already" in (await WC.answer_twiml(db, res["request_id"], tok, "1")).lower()
        assert "already took" in await WC.ring_twiml(db, res["request_id"], tok)
        # the visitor picks up
        await WC.customer_status(db, res["request_id"], "in-progress")
        req = await db[WC.COLL].find_one({"_id": req["_id"]})
        assert req["status"] == "connected" and isinstance(req["seconds_to_connect"], int)
        st = await WC.visitor_status(db, widget["key"], res["request_id"])
        assert st["status"] == "connected" and st["rep_first"]
        assert (await WC.visitor_status(db, "wrongkey", res["request_id"]))["status"] == "unknown"
        return res["request_id"]

    req_id = run(flow())
    # the visitor-facing poll + the manager's recent list
    poll = requests.get(f"{BASE}/api/w/{widget['key']}/call/{req_id}", timeout=30).json()
    assert poll["status"] == "connected"
    detail = requests.get(f"{BASE}/api/widgets/{widget['id']}", headers=mgr, timeout=30).json()
    row = next(c for c in detail["recent_calls"] if c["id"] == req_id)
    assert row["status"] == "connected" and row["phone_last4"] == CALL_PHONE[-4:] and row["host"] == "qa-dealer.test" and detail["stats"]["calls_connected"] >= 1
    # Twilio webhook shapes over HTTP
    twiml = requests.post(f"{BASE}/api/w/ring/{req_id}/badtoken", timeout=30)
    assert twiml.status_code == 200 and twiml.headers["content-type"].startswith("application/xml") and "<Hangup/>" in twiml.text
    assert requests.post(f"{BASE}/api/w/ring-status/{req_id}/badtoken", data={"CallStatus": "completed"}, timeout=30).text == "OK"


def test_nobody_available_texts_and_makes_a_callback_task(widget):
    from services import widgets as W, widget_calls as WC

    async def flow():
        db = _db()
        w = await db[W.COLL].find_one({"_id": ObjectId(widget["id"])})
        await db[W.COLL].update_one({"_id": w["_id"]}, {"$set": {"hours.mode": "always", "routing.call_user_ids": []}})
        w = await db[W.COLL].find_one({"_id": w["_id"]})
        phone = CALL_PHONE[:-1] + "9"
        res = await WC.request_call(db, w, {"name": f"Nora Nobody{RUN}", "phone": phone, "page": "https://www.qa-dealer.test/"}, "9.9.9.8")
        assert res["status"] == "missed" and res["message"]
        req = await db[WC.COLL].find_one({"_id": ObjectId(res["request_id"])})
        assert req["status"] == "missed" and req["missed_reason"] == "nobody_available"
        return phone

    run(flow())


# ---------------------------------------------------------------- key rotation + cleanup
def test_rotate_key_kills_the_old_script(mgr, widget):
    old = widget["key"]
    r = requests.post(f"{BASE}/api/widgets/{widget['id']}/rotate-key", headers=mgr, timeout=30)
    assert r.status_code == 200
    new = r.json()["widget"]["key"]
    assert new != old and requests.get(f"{BASE}/api/w/{old}.js", timeout=30).status_code == 404 and requests.get(f"{BASE}/api/w/{new}.js", timeout=30).status_code == 200
    widget["key"] = new


@pytest.fixture(scope="module", autouse=True)
def _cleanup():
    yield

    async def wipe():
        from services import widgets as W, widget_calls as WC
        db = _db()
        w = await db[W.COLL].find_one({"store_id": STORE, "is_active": {"$ne": False}})
        if w:
            await db[W.COLL].update_one({"_id": w["_id"]}, {"$set": {"hours.mode": "store", "domains": [], "name": w.get("store_name") or "Website Widget",
                                                                     "appearance.bubble_color": "#007AFF", "appearance.text_color": "#FFFFFF", "appearance.label": "Text Us", "appearance.position": "right", "doors.call.label": "Call me now"}})
        phones = [TEXT_PHONE, CALL_PHONE, CALL_PHONE[:-1] + "9"]
        contacts = await db.contacts.find({"phone": {"$in": phones}}, {"_id": 1}).to_list(20)
        cids = [str(c["_id"]) for c in contacts]
        await db.contacts.delete_many({"phone": {"$in": phones}})
        await db.conversations.delete_many({"$or": [{"contact_phone": {"$in": phones}}, {"contact_id": {"$in": cids}}]})
        await db.inbound_leads.delete_many({"phone": {"$in": phones}})
        await db.tasks.delete_many({"contact_id": {"$in": cids}})
        await db.campaign_pending_sends.delete_many({"contact_id": {"$in": cids}})
        await db.contact_events.delete_many({"contact_id": {"$in": cids}})
        await db.messages.delete_many({"contact_id": {"$in": cids}})
        await db[WC.COLL].delete_many({"phone": {"$in": phones}})
        await db.pending_calls.delete_many({"customer_phone": {"$in": phones}})
        await db.widget_events.delete_many({"visitor": {"$in": [f"v{RUN}", f"c{RUN}"]}})

    run(wipe())
