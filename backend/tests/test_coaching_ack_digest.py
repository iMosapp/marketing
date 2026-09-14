"""Rep 'Got it' on coaching + Monday coaching digest for managers.
Seeds two weeks of graded calls for Activation Tester on the QA store, exercises the ack API as rep and manager,
the team/rep unread counts, the digest builder (one thing to coach next), due logic, and a REAL send to Resend's sink."""
import asyncio
import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
import requests
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

from services import coaching_digest as cd
from services import scorecards as sc

BASE_URL = [l.split("=", 1)[1].strip() for l in open("/app/frontend/.env") if l.startswith("REACT_APP_BACKEND_URL=")][0].rstrip("/")
API = BASE_URL + "/api"
STORE_ID = "69a0b7095fddcede09591668"
DENVER = ZoneInfo("America/Denver")


def _db():
    return AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


def _login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=30)
    r.raise_for_status()
    d = r.json()
    return {"Authorization": f"Bearer {d.get('token') or d.get('access_token')}"}, d["user"]


@pytest.fixture(scope="module")
def rep():
    return _login("activation-tester@invalid.imonsocial.test", "NewPass123!")


@pytest.fixture(scope="module")
def mgr():
    return _login("qa-manager@invalid.imonsocial.test", "Manager123!")


@pytest.fixture(scope="module")
def seeded(rep):
    """Two graded calls last week (one with a critical miss) + one the week before, for the rep on the QA store."""
    uid = rep[1].get("id") or rep[1].get("_id")

    async def run():
        db = _db()
        await db.users.update_one({"_id": ObjectId(uid)}, {"$set": {"store_id": STORE_ID}})
        card = await db.scorecards.find_one({"store_id": STORE_ID, "active": {"$ne": False}}) or {}
        crit = next((c for c in card.get("criteria") or [] if c.get("critical")), None) or {"id": "qa_crit", "text": "Asked for an appointment", "hint": "Sell the visit.", "critical": True}
        other = next((c for c in card.get("criteria") or [] if not c.get("critical")), None) or {"id": "qa_other", "text": "Got the name", "hint": "", "critical": False}
        start, end, key, label = cd.last_week(DENVER)
        mid = start + timedelta(days=2, hours=17)
        base = {"user_id": uid, "rep_name": "Activation Tester", "store_id": STORE_ID, "scorecard_id": str(card.get("_id") or ObjectId()), "scorecard_name": card.get("name") or "QA Card",
                "department": "Sales", "duration_s": 120, "direction": "outbound", "wins": ["Warm open"], "customer_sentiment": "neutral", "call_type": "conversation", "graded_by": "ai", "qa_ack": True}
        res = await db.call_evaluations.insert_many([
            {**base, "call_sid": f"CA_qaack_{ObjectId()}", "contact_name": "Ack One", "call_at": mid, "created_at": mid, "score_pct": 55, "critical_misses": [crit["id"]],
             "results": [{"criterion_id": crit["id"], "text": crit["text"], "critical": True, "weight": 2, "passed": False}, {"criterion_id": other["id"], "text": other["text"], "critical": False, "weight": 1, "passed": True}],
             "coaching": ["Ask for the visit before the call ends."]},
            {**base, "call_sid": f"CA_qaack_{ObjectId()}", "contact_name": "Ack Two", "call_at": mid + timedelta(hours=3), "created_at": mid, "score_pct": 85, "critical_misses": [],
             "results": [{"criterion_id": crit["id"], "text": crit["text"], "critical": True, "weight": 2, "passed": True}, {"criterion_id": other["id"], "text": other["text"], "critical": False, "weight": 1, "passed": False}],
             "coaching": ["Use their name twice."]},
            {**base, "call_sid": f"CA_qaack_{ObjectId()}", "contact_name": "Ack Old", "call_at": start - timedelta(days=3), "created_at": start, "score_pct": 60, "critical_misses": [],
             "results": [{"criterion_id": crit["id"], "text": crit["text"], "critical": True, "weight": 2, "passed": True}], "coaching": ["Recap next steps."], "acknowledged_at": start - timedelta(days=2), "acknowledged_by": uid},
        ])
        return {"ids": [str(i) for i in res.inserted_ids], "uid": uid, "crit": crit, "week_label": label}
    async def clean():
        await _db().call_evaluations.delete_many({"qa_ack": True})
    asyncio.run(clean())
    ctx = asyncio.run(run())
    yield ctx
    asyncio.run(clean())


# ---------------------------------------------------------------- Got it
def test_rep_sees_unread_then_acks(rep, seeded):
    H = rep[0]
    d = requests.get(f"{API}/scorecards/evaluations/mine?days=30", headers=H, timeout=30).json()
    assert d["stats"]["unread_coaching"] >= 2 and d["stats"]["acknowledged"] >= 1
    ev_id = seeded["ids"][0]
    r = requests.post(f"{API}/scorecards/evaluations/{ev_id}/ack", headers=H, timeout=30)
    assert r.status_code == 200, r.text
    assert r.json()["acknowledged_at"] and r.json()["acknowledged_by"] == seeded["uid"]
    stamp = r.json()["acknowledged_at"][:19]
    # idempotent
    r2 = requests.post(f"{API}/scorecards/evaluations/{ev_id}/ack", headers=H, timeout=30)
    assert r2.status_code == 200 and r2.json()["acknowledged_at"][:19] == stamp
    d2 = requests.get(f"{API}/scorecards/evaluations/mine?days=30", headers=H, timeout=30).json()
    assert d2["stats"]["unread_coaching"] == d["stats"]["unread_coaching"] - 1
    assert next(e for e in d2["evaluations"] if e["id"] == ev_id)["acknowledged_at"][:19] == stamp


def test_manager_cannot_ack_for_the_rep_but_sees_the_stamp(mgr, seeded):
    H = mgr[0]
    r = requests.post(f"{API}/scorecards/evaluations/{seeded['ids'][1]}/ack", headers=H, timeout=30)
    assert r.status_code == 403, r.text
    team = requests.get(f"{API}/scorecards/team?days=30", headers=H, timeout=30).json()
    row = next(x for x in team["reps"] if x["user_id"] == seeded["uid"])
    assert row["unread_coaching"] >= 1 and row["acknowledged"] >= 1 and team["unread_coaching"] >= 1
    alert = next(a for a in team["alerts"] if a["id"] == seeded["ids"][0])
    assert alert["acknowledged_at"]
    detail = requests.get(f"{API}/scorecards/evaluations/{seeded['ids'][0]}", headers=H, timeout=30).json()
    assert detail["evaluation"]["acknowledged_at"] and detail["can_manage"]
    repview = requests.get(f"{API}/scorecards/rep/{seeded['uid']}?days=30", headers=H, timeout=30).json()
    assert repview["stats"]["unread_coaching"] >= 1


# ---------------------------------------------------------------- digest logic
def test_week_and_due_logic():
    now = datetime(2026, 9, 14, 15, 0, tzinfo=timezone.utc)  # Monday 9am Denver
    start, end, key, label = cd.last_week(DENVER, now)
    assert key == "2026-W37" and label == "Sep 7 to Sep 13" and (end - start).days == 7
    store = {"timezone": "America/Denver"}
    assert cd.due_now(store, now)
    assert not cd.due_now(store, datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc))          # 6am: too early
    assert cd.due_now(store, datetime(2026, 9, 15, 15, 0, tzinfo=timezone.utc))              # Tuesday catch-up
    assert not cd.due_now(store, datetime(2026, 9, 16, 15, 0, tzinfo=timezone.utc))          # Wednesday: no
    assert not cd.due_now({**store, "coaching_digest": {"last_sent_week": "2026-W37"}}, now)  # already sent
    assert not cd.due_now({**store, "coaching_digest": {"enabled": False}}, now)
    assert cd.next_monday(DENVER, now) == "2026-09-21"


def test_one_thing_prefers_critical_then_lowest():
    evals = [{"results": [{"criterion_id": "a", "text": "Got the name", "critical": False, "passed": False}, {"criterion_id": "b", "text": "Asked for the appointment", "critical": True, "passed": False}, {"criterion_id": "c", "text": "Recap", "critical": False, "passed": True}], "scorecard_id": "card1"},
             {"results": [{"criterion_id": "a", "text": "Got the name", "critical": False, "passed": False}, {"criterion_id": "b", "text": "Asked for the appointment", "critical": True, "passed": True}], "scorecard_id": "card1"}]
    ot = cd.one_thing(evals, {"card1": {"criteria": [{"id": "b", "hint": "Two times, then confirm."}]}})
    assert ot["text"] == "Asked for the appointment" and ot["critical"] and ot["pass_rate"] == 50 and ot["hint"] == "Two times, then confirm."
    assert cd.one_thing([{"results": [{"criterion_id": "c", "text": "Recap", "critical": False, "passed": True}]}], {}) is None


def test_build_digest_and_html(seeded):
    async def run():
        db = _db()
        store = await db.stores.find_one({"_id": ObjectId(STORE_ID)})
        d = await cd.build_digest(db, store)
        row = next(r for r in d["reps"] if r["user_id"] == seeded["uid"])
        # the QA store also carries the scorecard demo seed for this rep, so counts are lower bounds
        assert row["count"] >= 2 and row["avg_score"] is not None and row["prev_avg"] is not None and row["delta"] is not None and row["critical_misses"] >= 1
        assert row["unread_coaching"] >= 1 and row["one_thing"] and row["one_thing"]["critical"] and row["one_thing"]["pass_rate"] < 100
        assert d["team"]["calls"] >= 2 and d["label"] == seeded["week_label"]
        line = cd.digest_line(d)
        assert "graded" in line and "team average" in line and "critical miss" in line
        html = cd.digest_html(d, "QA", line, "https://x/scorecards/team", "")
        assert "Activation Tester" in html and "COACH ACTIVATION ON THIS" in html and row["one_thing"]["text"] in html and "vs the week before" in html and "coaching unread" in html
        people = await cd.recipients(db, STORE_ID)
        assert any(u["email"] == "qa-manager@invalid.imonsocial.test" for u in people)
        # real send to Resend's delivered sink
        res = await cd.send_digest(db, store, [{"_id": ObjectId(), "name": "Sink Manager", "email": "delivered@resend.dev"}], reason="test")
        assert res["ok"] and res["sent"] == 1 and res["calls"] >= 2, res
        log = await db.coaching_digest_sends.find_one({"to": "delivered@resend.dev", "week": d["week"]}, sort=[("at", -1)])
        assert log and log["ok"]
        fresh = await db.stores.find_one({"_id": ObjectId(STORE_ID)}, {"coaching_digest": 1})
        assert fresh["coaching_digest"]["last_sent_week"] == d["week"]
        # scheduler: already stamped for the week -> nothing sent
        assert not cd.due_now(fresh, datetime.now(timezone.utc).replace(hour=16))
    asyncio.run(run())


def test_digest_api_settings_toggle_and_send_guard(mgr, rep):
    H = mgr[0]
    d = requests.get(f"{API}/scorecards/digest", headers=H, timeout=30).json()
    assert d["enabled"] is True and d["store"]["id"] == STORE_ID and d["recipients"] >= 1 and d["email"] == "qa-manager@invalid.imonsocial.test"
    off = requests.put(f"{API}/scorecards/digest", headers=H, json={"enabled": False}, timeout=30).json()
    assert off["enabled"] is False and off["next_send"] is None and off["recipients"] == d["recipients"] - 1
    on = requests.put(f"{API}/scorecards/digest", headers=H, json={"enabled": True}, timeout=30).json()
    assert on["enabled"] is True and on["next_send"] and on["recipients"] == d["recipients"]
    # reps never see the manager settings
    assert requests.get(f"{API}/scorecards/digest", headers=rep[0], timeout=30).status_code == 403
    # a super admin with no store cannot send
    fh, _ = _login("forest@imosapp.com", "Admin123!")
    r = requests.post(f"{API}/scorecards/digest/send", headers=fh, timeout=30)
    assert r.status_code == 400 and "store" in r.json()["detail"].lower()
