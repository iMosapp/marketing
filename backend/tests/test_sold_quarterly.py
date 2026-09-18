"""Sold - Quarterly Check-In: the evergreen plan, the history-driven writer, and the two send guardrails (STOP, waiting on a reply).
The writer probe at the end calls the real LLM."""
import os
import pytest
from bson import ObjectId
from datetime import datetime, timezone, timedelta

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from routers.database import get_db  # noqa: E402
from routers import ai_campaigns as aic  # noqa: E402
from routers.campaigns import PREBUILT_TEMPLATES  # noqa: E402
import scheduler  # noqa: E402

pytestmark = pytest.mark.asyncio
TAG = "QA Quarterly"


def _tpl():
    return next(t for t in PREBUILT_TEMPLATES if t["id"] == "sold_quarterly")


async def test_template_shape():
    t = _tpl()
    assert t["trigger_tag"] == "sold" and t["ai_enabled"] is True and t["repeat_every_months"] == 3
    assert [s["delay_months"] for s in t["sequences"]] == [3, 6, 9, 12] and all(s["ai_generated"] and s["step_context"] for s in t["sequences"])
    assert "Never reuse an angle" in t["repeat_step"]["step_context"]


async def _seed(db, uid):
    now = datetime.now(timezone.utc)
    c = {"_id": ObjectId(), "user_id": uid, "first_name": "Marcus", "last_name": "QA-Hill", "phone": "+15005550601", "status": "active", "tags": [TAG, "sold"],
         "vehicle": "2024 Chevy Tahoe", "purchase_history": [{"title": "2024 Chevy Tahoe", "category": "vehicle", "date": (now - timedelta(days=200)).strftime("%Y-%m-%d"), "notes": "traded the F-150, tows a camper", "source": "wizard"}],
         "sold_count": 1, "date_sold": (now - timedelta(days=200)).strftime("%Y-%m-%d"), "created_at": now, "updated_at": now}
    await db.contacts.insert_one(c)
    conv = {"_id": ObjectId(), "user_id": uid, "contact_id": str(c["_id"]), "channel": "sms", "last_message_at": now - timedelta(days=150), "created_at": now, "updated_at": now}
    await db.conversations.insert_one(conv)
    msgs = [("user", "Congrats on the Tahoe Marcus! Send me a pic when you hook the camper up.", 199), ("contact", "Will do! Heading to Moab next month with it.", 198),
            ("user", "Moab in a Tahoe with the camper, perfect. Let me know how it pulls.", 198), ("contact", "Pulled great, barely felt it on the grade.", 160)]
    await db.messages.insert_many([{"_id": ObjectId(), "conversation_id": str(conv["_id"]), "contact_id": str(c["_id"]), "user_id": uid, "sender": s, "direction": "outbound" if s == "user" else "inbound",
                                    "content": t, "timestamp": now - timedelta(days=d), "channel": "sms"} for s, t, d in msgs])
    enr = {"_id": ObjectId(), "user_id": uid, "campaign_id": str(ObjectId()), "campaign_name": "Sold - Quarterly Check-In", "contact_id": str(c["_id"]), "status": "active",
           "messages_sent": [{"step": 1, "content": "Hey Marcus, three months with the Tahoe already. How did Moab treat you two?", "sent_at": now - timedelta(days=110)}]}
    await db.campaign_enrollments.insert_one(enr)
    return c, conv, enr


async def _wipe(db, c, conv, enr):
    await db.contacts.delete_one({"_id": c["_id"]})
    await db.conversations.delete_one({"_id": conv["_id"]})
    await db.messages.delete_many({"conversation_id": str(conv["_id"])})
    await db.campaign_enrollments.delete_one({"_id": enr["_id"]})
    await db.campaign_pending_sends.delete_many({"contact_id": str(c["_id"])})


async def test_history_block_and_writer():
    db = get_db()
    forest = await db.users.find_one({"email": "forest@imosapp.com"})
    uid = str(forest["_id"])
    c, conv, enr = await _seed(db, uid)
    try:
        text = await aic.campaign_history(uid, str(c["_id"]))
        assert "TODAY:" in text and "WHAT THEY BOUGHT FROM ME" in text and "2024 Chevy Tahoe" in text and "6 months ago" in text and "tows a camper" in text
        assert "OUR ACTUAL TEXTS" in text and "Moab" in text and "Me:" in text and "Marcus:" in text
        assert "CHECK-INS I ALREADY SENT" in text and "three months with the Tahoe" in text
        # real writer: personal, from the history, not the template, no canned filler
        out = await aic.generate_campaign_message(uid, str(c["_id"]), {"step_context": _tpl()["sequences"][1]["step_context"], "channel": "sms", "campaign_name": "Sold - Quarterly Check-In",
                                                                       "template_hint": "Hey {first_name}, half a year in. Anything I can help with on the {vehicle}?"})
        msg = out["message"]
        print("\nWRITER:", msg)
        assert out["success"] and 20 < len(msg) < 400
        low = msg.lower()
        assert "half a year in. anything i can help with" not in low, "must not parrot the template"
        assert "just checking in" not in low and "hope this finds you" not in low
        assert any(k in low for k in ("tahoe", "camper", "moab", "marcus", "tow", "trip", "service")), "should lean on something specific"
    finally:
        await _wipe(db, c, conv, enr)


async def test_repeat_touch_scheduling():
    db = get_db()
    now = datetime.utcnow()
    send_doc = {"user_id": "u1", "campaign_id": str(ObjectId()), "campaign_name": "Sold - Quarterly Check-In", "contact_id": str(ObjectId()), "contact_name": "QA Repeat", "contact_phone": "+15005550602",
                "enrollment_id": str(ObjectId()), "delivery_mode": "auto", "ai_enabled": True, "step": 4, "send_at": now - timedelta(hours=1)}
    camp = {"name": "Sold - Quarterly Check-In", "active": True, "repeat_every_months": 3, "repeat_step": _tpl()["repeat_step"], "sequences": _tpl()["sequences"]}
    try:
        doc = await scheduler._schedule_repeat_touch(db, send_doc, camp, now)
        assert doc and doc["step"] == 5 and doc["repeat"] is True and doc["status"] == "pending" and doc["channel"] == "sms"
        assert doc["step_context"] == _tpl()["repeat_step"]["step_context"] and doc["message_template"].startswith("Hey {first_name}, thought of you")
        assert abs((doc["send_at"] - (send_doc["send_at"] + timedelta(days=90))).total_seconds()) < 5
        assert await db.campaign_pending_sends.count_documents({"enrollment_id": send_doc["enrollment_id"], "status": "pending"}) == 1
        assert await scheduler._schedule_repeat_touch(db, send_doc, {**camp, "active": False}, now) is None, "switched-off plan stops"
        assert await scheduler._schedule_repeat_touch(db, send_doc, {**camp, "repeat_every_months": 0}, now) is None
    finally:
        await db.campaign_pending_sends.delete_many({"enrollment_id": send_doc["enrollment_id"]})


async def test_send_guardrails():
    """Opted-out contact -> skipped; customer waiting on a reply -> held two days (max 3 holds). Runs the real queue worker with manual-delivery sends."""
    db = get_db()
    forest = await db.users.find_one({"email": "forest@imosapp.com"})
    uid = str(forest["_id"])
    now = datetime.now(timezone.utc)
    stop = {"_id": ObjectId(), "user_id": uid, "first_name": "Stop", "last_name": "QA-Guard", "phone": "+15005550611", "status": "active", "tags": [TAG], "sms_opt_out": True, "created_at": now, "updated_at": now}
    waiting = {"_id": ObjectId(), "user_id": uid, "first_name": "Waiting", "last_name": "QA-Guard", "phone": "+15005550612", "status": "active", "tags": [TAG], "created_at": now, "updated_at": now}
    await db.contacts.insert_many([stop, waiting])
    conv = {"_id": ObjectId(), "user_id": uid, "contact_id": str(waiting["_id"]), "channel": "sms", "last_message_at": now - timedelta(hours=5), "created_at": now, "updated_at": now}
    await db.conversations.insert_one(conv)
    await db.messages.insert_one({"_id": ObjectId(), "conversation_id": str(conv["_id"]), "contact_id": str(waiting["_id"]), "user_id": uid, "sender": "contact", "direction": "inbound",
                                  "content": "Hey is the service department open Saturday?", "timestamp": now - timedelta(hours=5), "channel": "sms"})
    due = datetime.utcnow() - timedelta(minutes=5)
    base = {"user_id": uid, "campaign_id": str(ObjectId()), "campaign_name": "QA Guard", "enrollment_id": "", "step": 1, "message_template": "Hey {first_name}, checking in.", "media_urls": [],
            "channel": "sms", "delivery_mode": "manual", "ai_enabled": False, "send_at": due, "status": "pending", "created_at": due}
    s1 = {**base, "_id": ObjectId(), "contact_id": str(stop["_id"]), "contact_name": "Stop QA-Guard", "contact_phone": stop["phone"]}
    s2 = {**base, "_id": ObjectId(), "contact_id": str(waiting["_id"]), "contact_name": "Waiting QA-Guard", "contact_phone": waiting["phone"]}
    await db.campaign_pending_sends.insert_many([s1, s2])
    try:
        await scheduler.process_pending_campaign_steps()
        r1 = await db.campaign_pending_sends.find_one({"_id": s1["_id"]})
        assert r1["status"] == "skipped" and r1["skip_reason"] == "opted_out", r1
        r2 = await db.campaign_pending_sends.find_one({"_id": s2["_id"]})
        assert r2["status"] == "pending" and r2["held_reason"] == "customer_waiting_on_reply" and r2["held_count"] == 1, r2
        assert r2["send_at"] > datetime.utcnow() + timedelta(days=1, hours=23)
        # after three holds the touch goes through (here: becomes the rep's manual task)
        await db.campaign_pending_sends.update_one({"_id": s2["_id"]}, {"$set": {"send_at": due, "held_count": 3}})
        await scheduler.process_pending_campaign_steps()
        r2 = await db.campaign_pending_sends.find_one({"_id": s2["_id"]})
        assert r2["status"] != "pending" and r2["held_count"] == 3, r2
    finally:
        await db.campaign_pending_sends.delete_many({"_id": {"$in": [s1["_id"], s2["_id"]]}})
        await db.contacts.delete_many({"_id": {"$in": [stop["_id"], waiting["_id"]]}})
        await db.conversations.delete_one({"_id": conv["_id"]})
        await db.messages.delete_many({"conversation_id": str(conv["_id"])})
        await db.tasks.delete_many({"contact_id": {"$in": [str(stop["_id"]), str(waiting["_id"])]}})
        await db.notifications.delete_many({"contact_id": {"$in": [str(stop["_id"]), str(waiting["_id"])]}})
