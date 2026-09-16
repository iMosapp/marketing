"""Text (SMS) mystery shops: the shopper texts the person from the shop number, replies are matched by the (shop number, cell) pair,
reply speed is scored by the clock, quality by the grader, no reply = 0%. In-process tests fake Twilio + the LLM; the API test runs the
real flow through the server against a 500-555 test number (Twilio queues, never delivers).
Run: cd /app/backend && set -a && . ./.env && set +a && python -m pytest tests/test_text_shops.py -q"""
import asyncio
import os
import time
from datetime import datetime, timedelta, timezone

import pytest
import requests
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

from services import mystery_shops as ms
from services import scorecards as sc
from services import scripts as scr
from services import text_shops as tx
from services import twilio_service as tws

BASE_URL = [l.split("=", 1)[1].strip() for l in open("/app/frontend/.env") if l.startswith("REACT_APP_BACKEND_URL=")][0].rstrip("/")
API = BASE_URL + "/api"
CLIENT_ID = "6aa6d7dfb4c41decb2734ec4"  # QA Jeep 979a (preview)
PHONE = "+15005550099"


def _db():
    return AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


def _run(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro() if callable(coro) else coro)


@pytest.fixture(scope="module")
def admin():
    r = requests.post(f"{API}/auth/login", json={"email": "forest@imosapp.com", "password": "Admin123!"}, timeout=30)
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json().get('token') or r.json().get('access_token')}"}


class Fakes:
    def __init__(self, monkeypatch, replies):
        self.sent, self.replies = [], list(replies)

        async def send_sms(to_phone, message, media_urls=None, from_phone=None):
            self.sent.append({"to": to_phone, "from": from_phone, "text": message})
            return {"success": True, "sid": f"SM_fake_{len(self.sent)}", "status": "queued"}

        async def llm_json(system, user, timeout=75):
            self.last_system, self.last_user = system, user
            return self.replies.pop(0) if self.replies else {"say": "ok", "ended": False, "mood": "neutral"}

        async def grade(card, transcript, rep_name, contact_name, direction, duration_s, industry=None, language=None, channel="call"):
            self.graded = {"card": card, "transcript": transcript, "channel": channel}
            return {"results": [{"criterion_id": c["id"], "text": c["text"], "critical": bool(c.get("critical")), "weight": int(c.get("weight") or 1), "passed": True, "ai_passed": True, "evidence": "q", "confidence": 0.9, "override": None} for c in card["criteria"]],
                    "summary": "Fake summary.", "wins": ["w"], "coaching": ["c"], "customer_sentiment": "positive", "call_type": "conversation"}

        async def adherence(script, transcript, rep_first):
            return {"score_pct": None, "hits": [], "misses": [], "coaching": [], "summary": ""}

        monkeypatch.setattr(tws, "send_sms", send_sms)
        monkeypatch.setattr(scr, "_llm_json", llm_json)
        monkeypatch.setattr(sc, "grade_with_ai", grade)
        monkeypatch.setattr(scr, "_grade_adherence", adherence)
        monkeypatch.setattr(tx, "schedule_reply", lambda sid: None)


async def _target(db, name="QA Texter"):
    t = await db.shop_targets.find_one({"client_id": CLIENT_ID, "phone": PHONE})
    if not t:
        now = datetime.now(timezone.utc)
        res = await db.shop_targets.insert_one({"client_id": CLIENT_ID, "name": name, "phone": PHONE, "department": "sales", "title": "", "notes": "text shop test", "active": True, "challenge_history": [], "created_at": now, "updated_at": now})
        t = await db.shop_targets.find_one({"_id": res.inserted_id})
    return t


async def _cleanup(db):
    ids = [s["_id"] async for s in db.roleplay_sessions.find({"kind": "mystery_shop", "rep_phone": PHONE}, {"_id": 1})]
    await db.call_evaluations.delete_many({"roleplay_session_id": {"$in": [str(i) for i in ids]}})
    await db.roleplay_sessions.delete_many({"_id": {"$in": ids}})
    await db.shop_targets.delete_many({"client_id": CLIENT_ID, "phone": PHONE})


def test_text_shop_thread_and_grading(monkeypatch):
    f = Fakes(monkeypatch, [{"say": "Hey, is the 2023 Wrangler still there?", "ended": False}, {"say": "Cool, can I come by at 4?", "ended": False, "mood": "warm"}, {"say": "Perfect, see you at 4!", "ended": True, "mood": "warm"}])

    async def go():
        db = _db()
        client = await db.shop_clients.find_one({"_id": ObjectId(CLIENT_ID)})
        assert client, "QA Jeep client missing in preview"
        t = await _target(db)
        call = await ms.create_shop_call(db, client, t, datetime.now(timezone.utc), created_by="test", manual=True, mode="text")
        assert call["mode"] == "text" and call["direction"] == "inbound" and ms.serialize_call(call)["channel"] == "text"
        assert await ms.dial_now(db, call)
        s = await db.roleplay_sessions.find_one({"_id": call["_id"]})
        frm = await ms.from_number(db, client)
        assert s["status"] == "live" and s["from_number"] == frm and len(s["turns"]) == 1 and s["turns"][0]["role"] == "customer" and "Wrangler" in s["turns"][0]["text"]
        assert f.sent[-1] == {"to": PHONE, "from": frm, "text": "Hey, is the 2023 Wrangler still there?"} and "texting (SMS)" in f.last_system
        # a text from someone else, or to another number, is not ours
        assert not await tx.handle_inbound(db, frm, "+15005550098", "hi")
        assert not await tx.handle_inbound(db, "+15005550000", PHONE, "hi")
        # the rep answers 3 minutes later: delay measured from the shopper's text
        await db.roleplay_sessions.update_one({"_id": s["_id"]}, {"$set": {"turns.0.at": datetime.now(timezone.utc) - timedelta(seconds=185)}})
        assert await tx.handle_inbound(db, frm, PHONE, "Yes it is! This is Sam at QA Jeep, when can you come see it?", "SM1")
        s = await db.roleplay_sessions.find_one({"_id": s["_id"]})
        assert s["turns"][-1]["role"] == "rep" and 180 <= s["turns"][-1]["delay_s"] <= 200
        # a second rep text before the shopper answers carries no delay (not an answer to anything)
        assert await tx.handle_inbound(db, frm, PHONE, "We are open till 8", "SM2")
        s = await db.roleplay_sessions.find_one({"_id": s["_id"]})
        assert "delay_s" not in s["turns"][-1]
        # the shopper replies once for both texts, from the shop number
        assert await tx.reply_if_due(db, str(s["_id"]))
        assert not await tx.reply_if_due(db, str(s["_id"]))  # nothing new to answer
        s = await db.roleplay_sessions.find_one({"_id": s["_id"]})
        assert s["turns"][-1] == {**s["turns"][-1], "role": "customer", "text": "Cool, can I come by at 4?", "mood": "warm"} and f.sent[-1]["from"] == frm and s["status"] == "live" and s.get("text_lock") is None
        assert "[replied after 3 min]" in f.last_user and "This is exchange 2" in f.last_user
        st = tx.stats(s)
        assert st["replies"] == 2 and st["first_reply_s"] == s["turns"][1]["delay_s"] and st["waiting_since"]
        # rep closes it, shopper says goodbye with ended=true -> graded (scorecard text on for this shop)
        await db.roleplay_sessions.update_one({"_id": s["_id"]}, {"$set": {"notify_sms": True}})
        assert await tx.handle_inbound(db, frm, PHONE, "4 works, ask for Sam", "SM3")
        assert await tx.reply_if_due(db, str(s["_id"]))
        s = await db.roleplay_sessions.find_one({"_id": s["_id"]})
        assert s["status"] == "completed" and s["end_reason"] == "customer_ended" and s["score_pct"] is not None
        ev = await db.call_evaluations.find_one({"_id": ObjectId(s["evaluation_id"])})
        assert ev["channel"] == "text" and ev["text_stats"]["replies"] == 3 and f.graded["channel"] == "text" and f.graded["card"]["name"].endswith("(text)")
        assert "QA: [replied after 3 min]" in f.graded["transcript"] and "QA: [replied within a minute] 4 works" in f.graded["transcript"]
        by_id = {r["criterion_id"]: r for r in ev["results"]}
        assert by_id["text_first"]["passed"] is True and by_id["text_first"]["evidence"] == "First reply after 3 min" and by_id["text_pace"]["passed"] is True
        assert ev["score_pct"] == 100 and ev["critical_misses"] == []
        # scorecard text went to the rep from the shop number with the text wording
        assert f.sent[-1]["to"] == PHONE and f.sent[-1]["from"] == frm and "those texts just now were a practice shop" in f.sent[-1]["text"] and "the thread:" in f.sent[-1]["text"]
        out = ms.serialize_call(s)
        assert out["channel"] == "text" and out["text"]["first_reply_s"] == s["turns"][1]["delay_s"]
        pub = ms.public_score(s, ev, client)
        assert pub["channel"] == "text" and len(pub["transcript_turns"]) == 6 and pub["transcript_turns"][1]["delay_s"] == s["turns"][1]["delay_s"]
        # a second live text shop for the same pair waits instead of starting (replies could not be told apart)
        await db.roleplay_sessions.update_one({"_id": s["_id"]}, {"$set": {"status": "live"}})
        call2 = await ms.create_shop_call(db, client, t, datetime.now(timezone.utc), created_by="test", manual=True, mode="text")
        assert await ms.dial_now(db, call2)
        s2 = await db.roleplay_sessions.find_one({"_id": call2["_id"]})
        assert s2["status"] == "scheduled" and s2["scheduled_for"] > datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=2)
        await db.roleplay_sessions.update_one({"_id": s["_id"]}, {"$set": {"status": "completed"}})
        await _cleanup(db)

    _run(go())


def test_no_reply_scores_zero_and_sweep_answers_stale(monkeypatch):
    f = Fakes(monkeypatch, [{"say": "Hi, do you have the Grand Cherokee L in stock?", "ended": False}, {"say": "Hello?? Is the Grand Cherokee L there?", "ended": False}, {"say": "great thanks", "ended": False}])

    async def go():
        db = _db()
        client = await db.shop_clients.find_one({"_id": ObjectId(CLIENT_ID)})
        t = await _target(db)
        call = await ms.create_shop_call(db, client, t, datetime.now(timezone.utc), created_by="test", manual=True, mode="text")
        assert await tx.start_text_shop(db, call)
        await db.roleplay_sessions.update_one({"_id": call["_id"]}, {"$set": {"notify_sms": True}})
        # five hours of silence -> the sweep closes it as no reply, graded 0 with every criterion missed
        await db.roleplay_sessions.update_one({"_id": call["_id"]}, {"$set": {"turns.0.at": datetime.now(timezone.utc) - timedelta(hours=5), "started_at": datetime.now(timezone.utc) - timedelta(hours=5)}})
        assert await tx.sweep(db) >= 1
        s = await db.roleplay_sessions.find_one({"_id": call["_id"]})
        assert s["status"] == "completed" and s["outcome"] == "no_reply" and s["score_pct"] == 0 and s["end_reason"] == "no_reply" and s["fail_reason"] == "No reply to the text in 4 hours"
        ev = await db.call_evaluations.find_one({"_id": ObjectId(s["evaluation_id"])})
        assert ev["channel"] == "text" and ev["graded_by"] == "system" and all(r["passed"] is False for r in ev["results"]) and "text_first" in ev["critical_misses"]
        assert "never replied" in ev["summary"] and "gave up after 5 hours" in ev["summary"] and ev["coaching"][0].startswith("Answer every text lead within 5 minutes")
        assert f.sent[-1]["to"] == PHONE and "You scored 0%" in f.sent[-1]["text"]
        # a lost delayed reply: last turn is the rep's, older than the stale window -> the sweep answers it
        call = await ms.create_shop_call(db, client, t, datetime.now(timezone.utc), created_by="test", manual=True, mode="text")
        assert await tx.start_text_shop(db, call)
        frm = await ms.from_number(db, client)
        assert await tx.handle_inbound(db, frm, PHONE, "Yes we have two", "SM9")
        await db.roleplay_sessions.update_one({"_id": call["_id"]}, {"$set": {"turns.1.at": datetime.now(timezone.utc) - timedelta(seconds=200)}})
        n_before = len(f.sent)
        assert await tx.sweep(db) >= 1
        s = await db.roleplay_sessions.find_one({"_id": call["_id"]})
        assert s["turns"][-1]["role"] == "customer" and s["turns"][-1]["text"] == "great thanks" and len(f.sent) == n_before + 1
        # an admin can end a live thread: graded on what happened
        await tx.finish(db, str(call["_id"]), "ended_by_admin")
        s = await db.roleplay_sessions.find_one({"_id": call["_id"]})
        assert s["status"] == "completed" and s["end_reason"] == "ended_by_admin"
        # the report sees text shops
        rep = await ms.build_report(db, client)
        assert rep["summary"]["text_shops"] >= 2 and rep["summary"]["text_no_reply"] >= 1 and any(c["channel"] == "text" for c in rep["calls"])
        await _cleanup(db)

    _run(go())


def test_plan_month_schedules_text_shops(monkeypatch):
    async def go():
        db = _db()
        now = datetime.now(timezone.utc)
        res = await db.shop_clients.insert_one({"name": "QA Text Plan", "industry": "automotive", "locale": "en-US", "timezone": "America/Denver", "plan": {"per_month": {"sales": 0}, "text_per_month": {"sales": 2}, "price_monthly": 100},
                                                "hours": {"start": "00:00", "end": "23:59", "days": [0, 1, 2, 3, 4, 5, 6]}, "vehicles": [], "active": True, "record_calls": True, "created_at": now, "updated_at": now})
        cid = str(res.inserted_id)
        await db.shop_targets.insert_one({"client_id": cid, "name": "QA Plan Person", "phone": "+15005550097", "department": "sales", "active": True, "challenge_history": [], "created_at": now, "updated_at": now})
        client = await db.shop_clients.find_one({"_id": res.inserted_id})
        assert ms.plan_text_per_month(client) == {"sales": 2} and ms.serialize_client(client)["plan"]["text_per_month"] == {"sales": 2}
        made = await ms.plan_month(db, client)
        assert made["sales"] == 0 and made["text"]["sales"] == 2
        rows = await db.roleplay_sessions.find({"kind": "mystery_shop", "client_id": cid}).to_list(10)
        assert len(rows) == 2 and all(r["mode"] == "text" and r["status"] == "scheduled" for r in rows)
        assert (await ms.plan_month(db, client)) == {"sales": 0} or made  # idempotent: quota already met
        assert await db.roleplay_sessions.count_documents({"kind": "mystery_shop", "client_id": cid}) == 2
        rep = await ms.build_report(db, client)
        assert rep["by_department"]["sales"]["planned"] == 2 and rep["by_department"]["sales"]["planned_texts"] == 2 and rep["summary"]["planned"] == 2
        assert " Plus 2 sales text shops a month" in ms.proposal_text({"terms": {"per_month": {"sales": 4}, "text_per_month": {"sales": 2}, "price_monthly": 100, "term_months": 3}, "client_name": "X"}, "en-US")[0][1]
        assert "sms-shops per maand" in ms.proposal_text({"terms": {"per_month": {"sales": 4}, "text_per_month": {"sales": 2}, "price_monthly": 100, "term_months": 3}, "client_name": "X"}, "nl-NL")[0][1]
        await db.roleplay_sessions.delete_many({"client_id": cid})
        await db.shop_targets.delete_many({"client_id": cid})
        await db.shop_clients.delete_one({"_id": res.inserted_id})

    _run(go())


def test_api_text_shop_end_to_end(admin):
    """Real server path: Shop now by text -> Twilio webhook reply -> the shopper answers (LLM) -> End & grade (LLM). ~2 min."""
    t = _run(lambda: _target(_db(), "QA Texter API"))
    try:
        r = requests.post(f"{API}/shop-clients/{CLIENT_ID}/calls/shop-now", headers=admin, json={"target_id": str(t["_id"]), "channel": "text"}, timeout=90)
        assert r.status_code == 200, r.text
        call = r.json()
        assert call["channel"] == "text" and call["status"] == "live" and call["text"]["customer_texts"] == 1 and call["text"]["waiting_since"]
        # same person again by text = 409
        assert requests.post(f"{API}/shop-clients/{CLIENT_ID}/calls/shop-now", headers=admin, json={"target_id": str(t["_id"]), "channel": "text"}, timeout=30).status_code == 409
        d = requests.get(f"{API}/shop-clients/calls/{call['id']}", headers=admin, timeout=30).json()
        frm = _run(lambda: _db().roleplay_sessions.find_one({"_id": ObjectId(call["id"])}))["from_number"]
        opening = d["transcript_turns"][0]["text"]
        assert d["transcript_turns"][0]["role"] == "customer" and 5 < len(opening) <= 320
        # the rep replies through the real webhook
        w = requests.post(f"{API}/webhooks/twilio/incoming", data={"From": PHONE, "To": frm, "Body": "Yes we do! This is Sam at QA Jeep. Want to come see it today at 4 or tomorrow at 10?", "MessageSid": f"SMtest{int(time.time())}", "NumMedia": "0"}, timeout=30)
        assert w.status_code == 200
        d = requests.get(f"{API}/shop-clients/calls/{call['id']}", headers=admin, timeout=30).json()
        assert d["transcript_turns"][-1]["role"] == "rep" and d["transcript_turns"][-1]["delay_s"] is not None and d["text"]["replies"] == 1
        # the shopper thinks for 20-75s, then answers from the shop number
        for _ in range(30):
            time.sleep(5)
            d = requests.get(f"{API}/shop-clients/calls/{call['id']}", headers=admin, timeout=30).json()
            if d["transcript_turns"][-1]["role"] == "customer" and len(d["transcript_turns"]) >= 3:
                break
        assert d["transcript_turns"][-1]["role"] == "customer" and len(d["transcript_turns"]) >= 3, d["transcript_turns"]
        assert d["status"] in ("live", "ending", "grading", "completed")
        # end it: graded on the thread
        if d["status"] in ("live", "ending"):
            e = requests.post(f"{API}/shop-clients/calls/{call['id']}/end", headers=admin, timeout=120)
            assert e.status_code == 200, e.text
        for _ in range(24):
            d = requests.get(f"{API}/shop-clients/calls/{call['id']}", headers=admin, timeout=30).json()
            if d["status"] == "completed":
                break
            time.sleep(5)
        assert d["status"] == "completed" and d["evaluation"] and d["channel"] == "text", d
        ids = {r["criterion_id"] for r in d["evaluation"]["results"]}
        assert {"text_first", "text_pace"} <= ids and d["evaluation"]["scorecard_name"].endswith("(text)")
        first = next(r for r in d["evaluation"]["results"] if r["criterion_id"] == "text_first")
        assert first["passed"] is True and first["evidence"].startswith("First reply after")
        assert requests.post(f"{API}/shop-clients/calls/{call['id']}/end", headers=admin, timeout=30).status_code == 409
        # public scorecard page data carries the thread
        pub = requests.get(f"{API}/public/shop-score/{d['score_url'].rsplit('/', 1)[1]}", timeout=30).json()
        assert pub["channel"] == "text" and len(pub["transcript_turns"]) >= 3 and pub["text"]["first_reply_s"] is not None
    finally:
        _run(lambda: _cleanup(_db()))
