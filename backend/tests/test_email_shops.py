"""Email mystery shops: the shopper emails the person, replies arrive via the Resend inbound webhook addressed to shop+<session>@,
reply speed is scored by the clock (30 min first, 2 h pace), quality by the grader, no reply for a day = 0%.
In-process with faked Resend + LLM. Run: cd /app/backend && set -a && . ./.env && set +a && python -m pytest tests/test_email_shops.py -q"""
import asyncio
import os
from datetime import datetime, timedelta, timezone

import pytest
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

from services import email_shops as ems
from services import mystery_shops as ms
from services import scorecards as sc
from services import scripts as scr
from routers import resend_webhooks as rw

CLIENT_ID = "6aa6d7dfb4c41decb2734ec4"  # QA Jeep 979a (preview)
PHONE = "+15005550096"
EMAIL = "qa.emailshop@invalid.imonsocial.test"


def _db():
    return AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


def _run(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


class Fakes:
    def __init__(self, monkeypatch, replies):
        self.sent, self.replies = [], list(replies)
        monkeypatch.setenv("INBOUND_EMAIL_DOMAIN", "reply.qa.imonsocial.test")
        monkeypatch.setenv("RESEND_API_KEY", os.environ.get("RESEND_API_KEY") or "re_fake")

        async def send(db, s, subject, body):
            self.sent.append({"to": s.get("rep_email"), "from": ems.from_address(s), "reply_to": ems.shop_address(str(s["_id"])), "subject": subject, "body": body})
            return {"success": True, "id": f"em_fake_{len(self.sent)}"}

        async def llm_json(system, user, timeout=75):
            self.last_system, self.last_user = system, user
            return self.replies.pop(0) if self.replies else {"say": "ok", "ended": False, "mood": "neutral"}

        async def grade(card, transcript, rep_name, contact_name, direction, duration_s, industry=None, language=None, channel="call"):
            self.graded = {"card": card, "transcript": transcript, "channel": channel}
            return {"results": [{"criterion_id": c["id"], "text": c["text"], "critical": bool(c.get("critical")), "weight": int(c.get("weight") or 1), "passed": True, "ai_passed": True, "evidence": "q", "confidence": 0.9, "override": None} for c in card["criteria"]],
                    "summary": "Fake summary.", "wins": ["w"], "coaching": ["c"], "customer_sentiment": "positive", "call_type": "conversation"}

        async def adherence(script, transcript, rep_first):
            return {"score_pct": None, "hits": [], "misses": [], "coaching": [], "summary": ""}

        async def send_sms(to_phone, message, media_urls=None, from_phone=None):
            self.sms = {"to": to_phone, "text": message}
            return {"success": True, "sid": "SM_fake", "status": "queued"}

        from services import twilio_service as tws
        monkeypatch.setattr(ems, "_send", send)
        monkeypatch.setattr(scr, "_llm_json", llm_json)
        monkeypatch.setattr(sc, "grade_with_ai", grade)
        monkeypatch.setattr(scr, "_grade_adherence", adherence)
        monkeypatch.setattr(ems, "schedule_reply", lambda sid: None)
        monkeypatch.setattr(tws, "send_sms", send_sms)


async def _target(db):
    t = await db.shop_targets.find_one({"client_id": CLIENT_ID, "phone": PHONE})
    if not t:
        now = datetime.now(timezone.utc)
        res = await db.shop_targets.insert_one({"client_id": CLIENT_ID, "name": "QA Emailer", "phone": PHONE, "email": EMAIL, "department": "sales", "title": "", "notes": "email shop test", "active": True, "challenge_history": [], "created_at": now, "updated_at": now})
        t = await db.shop_targets.find_one({"_id": res.inserted_id})
    return t


async def _cleanup(db):
    ids = [s["_id"] async for s in db.roleplay_sessions.find({"kind": "mystery_shop", "rep_phone": PHONE}, {"_id": 1})]
    await db.call_evaluations.delete_many({"roleplay_session_id": {"$in": [str(i) for i in ids]}})
    await db.roleplay_sessions.delete_many({"_id": {"$in": ids}})
    await db.shop_targets.delete_many({"client_id": CLIENT_ID, "phone": PHONE})
    await db.inbound_email_unmatched.delete_many({"from": EMAIL})


def _inbound(sid, body, subject="Re: Question about the Wrangler", email_id="rx1", to=None):
    return {"from": f"Sam Seller <{EMAIL}>", "to": to or [ems.shop_address(sid)], "subject": subject, "text": body}


def test_email_shop_thread_and_grading(monkeypatch):
    f = Fakes(monkeypatch, [
        {"subject": "Question about the 2023 Wrangler", "say": "Hi,\n\nI saw the 2023 Wrangler on your site. Is it still available and what's the out the door price?\n\nThanks,\nMaria", "ended": False},
        {"say": "Great, thanks Sam. Could I come see it Thursday around 5?\n\nMaria", "ended": False, "mood": "warm"},
        {"say": "Perfect, see you Thursday at 5.\n\nMaria", "ended": True, "mood": "warm"},
    ])

    async def go():
        db = _db()
        client = await db.shop_clients.find_one({"_id": ObjectId(CLIENT_ID)})
        assert client, "QA Jeep client missing in preview"
        await _cleanup(db)
        t = await _target(db)
        assert ems.configured() is None
        call = await ms.create_shop_call(db, client, t, datetime.now(timezone.utc), created_by="test", manual=True, mode="email")
        assert call["mode"] == "email" and call["direction"] == "inbound" and call["rep_email"] == EMAIL and ms.serialize_call(call)["channel"] == "email"
        assert await ms.dial_now(db, call)
        s = await db.roleplay_sessions.find_one({"_id": call["_id"]})
        sid = str(s["_id"])
        assert s["status"] == "live" and s["subject"] == "Question about the 2023 Wrangler" and s["reply_to"] == f"shop+{sid}@reply.qa.imonsocial.test"
        assert len(s["turns"]) == 1 and s["turns"][0]["role"] == "customer" and "Wrangler" in s["turns"][0]["text"] and s["turns"][0]["email_id"] == "em_fake_1"
        assert f.sent[-1]["to"] == EMAIL and f.sent[-1]["reply_to"] == s["reply_to"] and f.sent[-1]["subject"] == s["subject"]
        sender_domain = os.environ.get("SENDER_EMAIL", "notifications@send.imonsocial.com").split("@")[-1]
        assert f.sent[-1]["from"].endswith(f"@{sender_domain}>") and f.sent[-1]["from"].split(" <")[0] == s["persona"]["name"] and "notifications" not in f.sent[-1]["from"]
        assert "emailing" in f.last_system and "EMAIL thread" in f.last_system
        # inbound routing: shop+<id>@ is picked out of the To list; a random address is not
        assert ems.session_id_from([{"email": s["reply_to"]}]) == sid and ems.session_id_from(["reply+abc@x.test"]) is None
        assert not await ems.handle_inbound(db, str(ObjectId()), EMAIL, "hi", "hi")
        # the rep answers 12 minutes later through the Resend webhook ingest: delay measured from the shopper's email
        await db.roleplay_sessions.update_one({"_id": s["_id"]}, {"$set": {"turns.0.at": datetime.now(timezone.utc) - timedelta(minutes=12)}})
        r = await rw.ingest_received_email(db, _inbound(sid, "Hi Maria,\n\nYes it is still here! Out the door is 48,900. When would you like to come see it?\n\nSam\n\nOn Tue, Maria wrote:\n> I saw the 2023 Wrangler"), "rx1")
        assert r["status"] == "shop" and r["session_id"] == sid
        s = await db.roleplay_sessions.find_one({"_id": s["_id"]})
        assert s["turns"][-1]["role"] == "rep" and 700 <= s["turns"][-1]["delay_s"] <= 760 and s["turns"][-1]["from"] == EMAIL and s["turns"][-1]["email_id"] == "rx1"
        assert "On Tue" not in s["turns"][-1]["text"] and "48,900" in s["turns"][-1]["text"], "quoted history must be stripped"
        # same email delivered twice (webhook retry) is ignored
        assert (await rw.ingest_received_email(db, _inbound(sid, "dup"), "rx1"))["status"] == "duplicate" or len((await db.roleplay_sessions.find_one({"_id": s["_id"]}))["turns"]) == 2
        # the shopper replies once, as Re:
        assert await ems.reply_if_due(db, sid)
        assert not await ems.reply_if_due(db, sid)
        s = await db.roleplay_sessions.find_one({"_id": s["_id"]})
        assert s["turns"][-1]["role"] == "customer" and "Thursday" in s["turns"][-1]["text"] and f.sent[-1]["subject"] == "Re: Question about the 2023 Wrangler" and s.get("text_lock") is None
        assert "[replied after 12 min]" in f.last_user and "SUBJECT: Question about the 2023 Wrangler" in f.last_user
        st = ems.stats(s)
        assert st["replies"] == 1 and st["first_reply_s"] == s["turns"][1]["delay_s"] and st["waiting_since"]
        # rep confirms, shopper signs off with ended=true -> graded, scorecard text mentions the email thread
        await db.roleplay_sessions.update_one({"_id": s["_id"]}, {"$set": {"notify_sms": True}})
        r = await rw.ingest_received_email(db, _inbound(sid, "Thursday at 5 is perfect, ask for Sam.", email_id="rx2"), "rx2")
        assert r["status"] == "shop"
        assert await ems.reply_if_due(db, sid)
        s = await db.roleplay_sessions.find_one({"_id": s["_id"]})
        assert s["status"] == "completed" and s["end_reason"] == "customer_ended" and s["score_pct"] == 100
        ev = await db.call_evaluations.find_one({"_id": ObjectId(s["evaluation_id"])})
        assert ev["channel"] == "email" and ev["text_stats"]["replies"] == 2 and f.graded["channel"] == "email" and f.graded["card"]["name"].endswith("(email)")
        assert "QA: [replied after 12 min]" in f.graded["transcript"] and f.graded["transcript"].startswith("SUBJECT: Question about the 2023 Wrangler")
        by_id = {r["criterion_id"]: r for r in ev["results"]}
        assert by_id["email_first"]["passed"] is True and by_id["email_first"]["evidence"] == "First reply after 12 min" and by_id["email_pace"]["passed"] is True
        assert f.sms["to"] == PHONE and "that email thread just now was a practice shop" in f.sms["text"]
        out = ms.serialize_call(s)
        assert out["channel"] == "email" and out["subject"] == s["subject"] and out["text"]["first_reply_s"] == s["turns"][1]["delay_s"] and out["rep_email"] == EMAIL
        pub = ms.public_score(s, ev, client)
        assert pub["channel"] == "email" and pub["subject"] == s["subject"] and len(pub["transcript_turns"]) == 5
        # a reply to a finished shop is swallowed, never lands as a customer thread
        r = await rw.ingest_received_email(db, _inbound(sid, "one more thing", email_id="rx3"), "rx3")
        assert r["status"] == "shop"
        assert await db.inbound_email_unmatched.count_documents({"from": EMAIL}) == 0
        # a second live email shop for the same address waits instead of starting
        await db.roleplay_sessions.update_one({"_id": s["_id"]}, {"$set": {"status": "live"}})
        call2 = await ms.create_shop_call(db, client, t, datetime.now(timezone.utc), created_by="test", manual=True, mode="email")
        assert await ms.dial_now(db, call2)
        s2 = await db.roleplay_sessions.find_one({"_id": call2["_id"]})
        assert s2["status"] == "scheduled" and s2["scheduled_for"] > datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=5)
        await _cleanup(db)

    _run(go())


def test_no_reply_scores_zero_slow_reply_fails_speed_and_sweep(monkeypatch):
    f = Fakes(monkeypatch, [
        {"subject": "Grand Cherokee L availability", "say": "Hi, do you have the Grand Cherokee L in stock?\n\nMaria", "ended": False},
        {"subject": "Wrangler", "say": "Is the Wrangler still there?\n\nMaria", "ended": False},
        {"say": "Thanks!\n\nMaria", "ended": True, "mood": "neutral"},
    ])

    async def go():
        db = _db()
        client = await db.shop_clients.find_one({"_id": ObjectId(CLIENT_ID)})
        await _cleanup(db)
        t = await _target(db)
        call = await ms.create_shop_call(db, client, t, datetime.now(timezone.utc), created_by="test", manual=True, mode="email")
        assert await ems.start_email_shop(db, call)
        await db.roleplay_sessions.update_one({"_id": call["_id"]}, {"$set": {"notify_sms": True}})
        # a day and a bit of silence -> the sweep closes it as no reply, graded 0 with every criterion missed
        await db.roleplay_sessions.update_one({"_id": call["_id"]}, {"$set": {"turns.0.at": datetime.now(timezone.utc) - timedelta(hours=25), "started_at": datetime.now(timezone.utc) - timedelta(hours=25)}})
        assert await ems.sweep(db) >= 1
        s = await db.roleplay_sessions.find_one({"_id": call["_id"]})
        assert s["status"] == "completed" and s["outcome"] == "no_reply" and s["score_pct"] == 0 and s["end_reason"] == "no_reply" and s["fail_reason"] == "No reply to the email in 24 hours"
        ev = await db.call_evaluations.find_one({"_id": ObjectId(s["evaluation_id"])})
        assert ev["channel"] == "email" and ev["graded_by"] == "system" and all(r["passed"] is False for r in ev["results"]) and "email_first" in ev["critical_misses"]
        assert "never replied" in ev["summary"] and "gave up after 25 hours" in ev["summary"] and ev["coaching"][0].startswith("Answer every email lead within 30 minutes")
        assert f.sms["to"] == PHONE and "You scored 0%" in f.sms["text"]
        # slow reply: 3 hours -> first-reply and pace criteria both fail by the clock even though the grader passed everything
        call = await ms.create_shop_call(db, client, t, datetime.now(timezone.utc), created_by="test", manual=True, mode="email")
        assert await ems.start_email_shop(db, call)
        sid = str(call["_id"])
        await db.roleplay_sessions.update_one({"_id": call["_id"]}, {"$set": {"turns.0.at": datetime.now(timezone.utc) - timedelta(hours=3)}})
        assert await ems.handle_inbound(db, sid, EMAIL, "Re: Wrangler", "Yes we have it, come by anytime.", "rx9")
        # lost delayed reply: the rep's email is older than the stale window -> the sweep answers it (shopper signs off)
        await db.roleplay_sessions.update_one({"_id": call["_id"]}, {"$set": {"turns.1.at": datetime.now(timezone.utc) - timedelta(minutes=25)}})
        assert await ems.sweep(db) >= 1
        s = await db.roleplay_sessions.find_one({"_id": call["_id"]})
        assert s["status"] == "completed" and s["end_reason"] == "customer_ended"
        ev = await db.call_evaluations.find_one({"_id": ObjectId(s["evaluation_id"])})
        by_id = {r["criterion_id"]: r for r in ev["results"]}
        assert by_id["email_first"]["passed"] is False and by_id["email_first"]["evidence"] == "First reply after 3 h 0 min" and by_id["email_pace"]["passed"] is False
        assert ev["score_pct"] < 100 and "email_first" in ev["critical_misses"]
        # the report counts email shops
        rep = await ms.build_report(db, client)
        assert rep["summary"]["email_shops"] >= 2 and rep["summary"]["email_no_reply"] >= 1 and any(c["channel"] == "email" for c in rep["calls"])
        await _cleanup(db)

    _run(go())


def test_not_configured_and_no_email_fail_cleanly(monkeypatch):
    async def go():
        db = _db()
        client = await db.shop_clients.find_one({"_id": ObjectId(CLIENT_ID)})
        t = await _target(db)
        monkeypatch.delenv("INBOUND_EMAIL_DOMAIN", raising=False)
        assert "INBOUND_EMAIL_DOMAIN" in (ems.configured() or "")
        call = await ms.create_shop_call(db, client, t, datetime.now(timezone.utc), created_by="test", manual=True, mode="email")
        assert not await ems.start_email_shop(db, call)
        s = await db.roleplay_sessions.find_one({"_id": call["_id"]})
        assert s["status"] == "failed" and s["outcome"] == "not_configured" and "INBOUND_EMAIL_DOMAIN" in s["fail_reason"]
        monkeypatch.setenv("INBOUND_EMAIL_DOMAIN", "reply.qa.imonsocial.test")
        call = await ms.create_shop_call(db, client, {**t, "email": ""}, datetime.now(timezone.utc), created_by="test", manual=True, mode="email")
        assert call["rep_email"] is None and not await ems.start_email_shop(db, call)
        s = await db.roleplay_sessions.find_one({"_id": call["_id"]})
        assert s["fail_reason"] == "This person has no email address"
        # the same person can be on a call, a text and an email shop at once: mode queries do not collide
        assert ms.mode_q("email") == {"mode": "email"} and ms.mode_q("text") == {"mode": "text"} and ms.mode_q("phone") == {"mode": {"$nin": ["text", "email"]}} and ms.mode_of("bogus") == "phone"
        await _cleanup(db)

    _run(go())


def test_plan_month_schedules_email_shops_only_for_people_with_email():
    async def go():
        db = _db()
        now = datetime.now(timezone.utc)
        res = await db.shop_clients.insert_one({"name": "QA Email Plan", "industry": "automotive", "locale": "en-US", "timezone": "America/Denver", "plan": {"per_month": {"sales": 0}, "email_per_month": {"sales": 2}, "price_monthly": 100},
                                                "hours": {"start": "00:00", "end": "23:59", "days": [0, 1, 2, 3, 4, 5, 6]}, "vehicles": [], "active": True, "record_calls": True, "created_at": now, "updated_at": now})
        cid = str(res.inserted_id)
        await db.shop_targets.insert_one({"client_id": cid, "name": "QA No Email", "phone": "+15005550095", "department": "sales", "active": True, "challenge_history": [], "created_at": now, "updated_at": now})
        await db.shop_targets.insert_one({"client_id": cid, "name": "QA With Email", "phone": "+15005550094", "email": "with.email@invalid.imonsocial.test", "department": "sales", "active": True, "challenge_history": [], "created_at": now, "updated_at": now})
        client = await db.shop_clients.find_one({"_id": res.inserted_id})
        try:
            made = await ms.plan_month(db, client, created_by="test")
            assert made.get("email", {}).get("sales") == 2 and made["sales"] == 0
            rows = await db.roleplay_sessions.find({"client_id": cid}).to_list(10)
            assert len(rows) == 2 and all(r["mode"] == "email" and r["rep_email"] == "with.email@invalid.imonsocial.test" and r["rep_name"] == "QA With Email" for r in rows)
            assert ms.plan_email_per_month(client) == {"sales": 2} and ms.serialize_client(client)["plan"]["email_per_month"] == {"sales": 2}
            assert (await ms.plan_month(db, client, created_by="test")).get("email") is None, "already full"
        finally:
            await db.roleplay_sessions.delete_many({"client_id": cid})
            await db.shop_targets.delete_many({"client_id": cid})
            await db.shop_clients.delete_one({"_id": res.inserted_id})

    _run(go())
