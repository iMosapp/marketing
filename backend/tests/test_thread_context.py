"""Thread context: the AI writers must tell a web chat about the widget, a trade-in appraisal and the customer's own texts
apart instead of blending them into one "Customer:" blob.
Run: cd /app/backend && set -a && . ./.env && set +a && python -m pytest tests/test_thread_context.py -q"""
import asyncio
import os
from datetime import datetime, timezone, timedelta

import pytest
import requests
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

from services import thread_context as tc
from tests import qa_creds

BASE_URL = [l.split("=", 1)[1].strip() for l in open("/app/frontend/.env") if l.startswith("REACT_APP_BACKEND_URL=")][0].rstrip("/")
API = BASE_URL + "/api"
T0 = datetime(2026, 10, 7, 15, 2, tzinfo=timezone.utc)


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


def _scenario(conv_id="c1", appraisal_id="a1"):
    """Forest chats on the website about adding the widget, a day later gets a trade link, opens it, photos arrive, then asks what his truck is worth."""
    t = lambda h, m=0: T0 + timedelta(hours=h, minutes=m)
    return [
        {"conversation_id": conv_id, "sender": "contact", "direction": "inbound", "channel": "webchat", "type": "webchat_transcript", "timestamp": t(0),
         "content": "Web chat on imonsocial.com (asked for a person):\n\nVisitor: how do I get this chat added to my site?\nJessi: Great question! You paste one line of code into your website. Want me to have someone walk you through it?\nVisitor: yes please"},
        {"conversation_id": conv_id, "sender": "ai", "direction": "outbound", "channel": "sms", "timestamp": t(0, 3), "content": "Hey Forest, this is Jessi with i'M On Social. I saw you asked about adding the chat to your site, happy to help. What platform is your website on?"},
        {"conversation_id": conv_id, "sender": "user", "direction": "outbound", "channel": "sms", "kind": "trade_link", "appraisal_id": appraisal_id, "timestamp": t(23),
         "content": "Hi Forest, here's the link to snap a few photos of your truck so I can get you a number: https://x.test/t/abc"},
        {"conversation_id": conv_id, "sender": "system", "direction": "system", "channel": "system", "type": "event", "kind": "trade_link_opened", "appraisal_id": appraisal_id, "timestamp": t(23, 4), "content": "Forest opened the trade link"},
        {"conversation_id": conv_id, "sender": "system", "direction": "system", "channel": "system", "type": "event", "kind": "trade_link_photos", "appraisal_id": appraisal_id, "timestamp": t(23, 21), "content": "4 photos arrived from Forest"},
        {"conversation_id": conv_id, "sender": "contact", "direction": "inbound", "channel": "sms", "timestamp": t(23, 30), "content": "ok sent them. what do you think it's worth?"},
    ]


def test_labels_events_and_webchat_instead_of_calling_everything_customer():
    view = tc.build(_scenario(), "Forest Morris", vehicles={"a1": "2019 Ford F-150 Lariat"}, now=T0 + timedelta(hours=23, minutes=35))
    text = view.dialogue()
    assert "Customer:" not in text and "Forest: Forest opened" not in text, text
    assert "[event 2:06 PM] Forest opened the trade link" in text and "[event 2:23 PM] 4 photos arrived from Forest" in text
    assert "[web chat on imonsocial.com, with the site assistant, before this text thread]" in text
    assert "Forest (on the site): how do I get this chat added to my site?" in text and "Site assistant: Great question!" in text
    assert "Me: Hey Forest, this is Jessi" in text, "Jessi's own reply is mine, not the customer's"
    assert "Forest: ok sent them. what do you think it's worth?" in text
    assert "=== Oct 8 · trade-in appraisal of their 2019 Ford F-150 Lariat (CURRENT TOPIC) ===" in text, "a new topic opens under its own dated header"
    gap = tc.build([{"conversation_id": "g", "sender": "contact", "timestamp": T0, "content": "is the blue truck still in stock?"},
                    {"conversation_id": "g", "sender": "contact", "timestamp": T0 + timedelta(days=2), "content": "hello? still in stock?"}], "Forest", now=T0 + timedelta(days=2, minutes=1))
    assert "--- 2 days later, Oct 9 ---" in gap.dialogue() and len(gap.episodes) == 1, "silence inside one topic shows as a divider, not a new topic"


def test_episodes_current_topic_and_earlier_topics():
    view = tc.build(_scenario(), "Forest Morris", inquiry={"kind": "software_demo", "topic": "a demo of i'M On Social", "source_name": "Website chat"},
                    vehicles={"a1": "2019 Ford F-150 Lariat"}, now=T0 + timedelta(hours=23, minutes=35))
    assert [e.kind for e in view.episodes] == ["software", "trade_in"]
    assert view.current.kind == "trade_in" and "2019 Ford F-150 Lariat" in view.current.label() and view.current.trigger == "I sent them the trade link"
    assert view.earlier()[0].kind == "software" and 'asked "how do I get this chat added to my site?"' in view.earlier()[0].label()
    block = view.topic_block()
    assert block.startswith("WHAT THE CUSTOMER IS TALKING ABOUT RIGHT NOW: trade-in appraisal of their 2019 Ford F-150 Lariat (since 35 minutes ago")
    assert "EARLIER, SEPARATE TOPICS" in block and "web chat on imonsocial.com" in block and "do not pitch other vehicles" in block
    assert not view.switched
    assert view.inquiry_for_prompt({"kind": "software_demo"}) is None, "the software-demo lead block must not fire while they talk trade-in"
    assert "(CURRENT TOPIC)" in view.dialogue() and "(earlier, separate topic)" in view.dialogue()
    s = view.summary()
    assert s["kind"] == "trade_in" and len(s["episodes"]) == 2 and s["episodes"][1]["current"]


def test_customer_switching_subject_in_their_own_words():
    msgs = _scenario() + [{"conversation_id": "c1", "sender": "contact", "direction": "inbound", "channel": "sms", "timestamp": T0 + timedelta(hours=24),
                           "content": "also, I still need to know how to install the widget on my website"}]
    view = tc.build(msgs, "Forest", vehicles={"a1": "2019 Ford F-150"}, now=T0 + timedelta(hours=24, minutes=1))
    assert view.current.kind == "software" and view.switched and len(view.episodes) == 3
    assert "The customer just changed the subject" in view.topic_block() and "never mention vehicles" in view.topic_block()
    # the rep overrides: this reply is about the trade-in after all
    view.force("trade_in")
    assert view.current.kind == "trade_in" and view.forced and "chosen by the rep" in view.topic_block() and not view.switched
    assert 'their last words on it: "ok sent them. what do you think it\'s worth?"' in view.topic_block()
    view.force("software")
    assert 'their last words on it: "also, I still need to know how to install the widget on my website"' in view.topic_block(), "force picks the latest episode of that kind"
    only_chat = tc.build(_scenario(), "Forest", vehicles={"a1": "2019 Ford F-150"}, now=T0 + timedelta(hours=24)).force("software")
    assert 'their last words on it: "how do I get this chat added to my site? / yes please"' in only_chat.topic_block(), "a web chat episode remembers what the visitor asked"
    # a plain thread with no triggers and vague texts stays one general episode
    plain = tc.build([{"conversation_id": "c2", "sender": "contact", "timestamp": T0, "content": "hey"}, {"conversation_id": "c2", "sender": "user", "timestamp": T0 + timedelta(minutes=1), "content": "hi Forest, what can I do for you?"},
                      {"conversation_id": "c2", "sender": "contact", "timestamp": T0 + timedelta(minutes=2), "content": "do you still have the blue truck in stock?"}], "Forest", now=T0 + timedelta(minutes=3))
    assert len(plain.episodes) == 1 and plain.current.kind == "vehicle" and not plain.switched
    assert tc.classify("what's my trade worth") == "trade_in" and tc.classify("how do I embed the widget") == "software" and tc.classify("thanks!") is None
    assert tc.build([], "X").topic_block() == "" and tc.build([], "X").dialogue() == ""


def test_lead_marker_and_unsent_drafts():
    msgs = [{"conversation_id": "c3", "sender": "system", "type": "event", "is_lead_marker": True, "timestamp": T0, "content": "New Website lead from this customer · 2022 Jeep Grand Cherokee"},
            {"conversation_id": "c3", "sender": "ai_draft", "status": "pending", "timestamp": T0 + timedelta(minutes=1), "content": "DRAFT NOT SENT"},
            {"conversation_id": "c3", "sender": "ai_draft", "status": "sent", "timestamp": T0 + timedelta(minutes=2), "content": "Hi, thanks for asking about the Grand Cherokee"},
            {"conversation_id": "c3", "sender": "user", "channel": "voice", "type": "call_log", "timestamp": T0 + timedelta(minutes=9), "content": "Outbound call placed to +1801"}]
    view = tc.build(msgs, "Dana", now=T0 + timedelta(minutes=10))
    text = view.dialogue()
    assert view.current.kind == "vehicle" and "2022 Jeep Grand Cherokee" in view.current.label() and view.current.trigger == "a new lead from this customer"
    assert "DRAFT NOT SENT" not in text and "Me: Hi, thanks for asking" in text and "[call 3:11 PM] Outbound call placed" in text


def test_live_suggest_and_brief_use_the_thread_reader():
    """Against the running server: Ask Jessi returns the topic, honours an override, and the draft about the trade-in does not drag the widget in."""
    r = requests.post(f"{API}/auth/login", json={"email": "forest@imosapp.com", "password": qa_creds.password_for("forest@imosapp.com")}, timeout=30)
    r.raise_for_status()
    token = r.json().get("token") or r.json().get("access_token")
    headers = {"Authorization": f"Bearer {token}"}

    async def mk():
        db = _db()
        me = await db.users.find_one({"email": "forest@imosapp.com"})
        contact = {"first_name": "Forest", "last_name": "QAThread", "phone": "+15005550777", "user_id": str(me["_id"]), "created_at": datetime.now(timezone.utc)}
        cid = str((await db.contacts.insert_one(contact)).inserted_id)
        appr_id = (await db.vehicle_appraisals.insert_one({"user_id": str(me["_id"]), "contact_id": cid, "vehicle": {"year": 2019, "make": "Ford", "model": "F-150", "trim": "Lariat"}, "created_at": datetime.now(timezone.utc), "qa_thread_context": True})).inserted_id
        conv = {"user_id": str(me["_id"]), "contact_id": cid, "contact_name": "Forest QAThread", "contact_phone": "+15005550777", "status": "active", "ai_mode": "assisted", "created_at": T0, "last_message_at": datetime.now(timezone.utc)}
        conv_id = str((await db.conversations.insert_one(conv)).inserted_id)
        rows = _scenario(conv_id, str(appr_id))
        for m in rows:
            m["contact_id"] = cid
        await db.messages.insert_many(rows)
        return str(me["_id"]), cid, conv_id, str(appr_id)

    uid, cid, conv_id, appr_id = _run(mk())
    try:
        async def check_brief():
            from services.relationship_intel import build_relationship_brief
            brief = await build_relationship_brief(uid, cid, conversation_id=conv_id)
            ctx = brief["ai_context"]
            assert "RECENT MESSAGES" not in ctx, "the generator supplies the dialogue; the brief must not add a second, unlabelled copy"
            assert "ACTIVITY TIMELINE" not in ctx
            loose = await build_relationship_brief(uid, cid)
            return loose["ai_context"]
        loose_ctx = _run(check_brief())
        assert "RECENT MESSAGES (may span several threads and channels" in loose_ctx and "Salesperson: Hey Forest, this is Jessi" in loose_ctx and "Forest QAThread: Forest opened" not in loose_ctx

        async def check_load():
            view = await tc.load(_db(), conv_id)
            return view
        view = _run(check_load())
        assert view.current.kind == "trade_in" and "2019 Ford F-150 Lariat" in view.current.label(), "load() resolves the vehicle from the appraisal"

        r1 = requests.post(f"{API}/messages/ai-suggest/{conv_id}", headers=headers, json={}, timeout=60)
        assert r1.status_code == 200, r1.text
        d1 = r1.json()
        assert d1["topic"]["kind"] == "trade_in" and d1["topic"]["episodes"][0]["kind"] == "software" and d1["suggestion"], d1
        low = d1["suggestion"].lower()
        assert "widget" not in low and "website" not in low and "your site" not in low, f"the trade-in draft dragged the web chat in: {d1['suggestion']}"
        r2 = requests.post(f"{API}/messages/ai-suggest/{conv_id}", headers=headers, json={"topic_kind": "software"}, timeout=60)
        d2 = r2.json()
        assert d2["topic"]["kind"] == "software" and d2["topic"]["forced"] is True and d2["suggestion"], d2
        low2 = d2["suggestion"].lower()
        assert any(w in low2 for w in ("site", "website", "chat", "widget", "code", "platform", "install", "wordpress", "page")), f"forced software draft ignored the topic: {d2['suggestion']}"
        assert "truck" not in low2 and "f-150" not in low2 and "trade" not in low2, d2["suggestion"]
    finally:
        async def cl():
            db = _db()
            await db.messages.delete_many({"conversation_id": conv_id})
            await db.conversations.delete_one({"_id": ObjectId(conv_id)})
            await db.contacts.delete_one({"_id": ObjectId(cid)})
            await db.vehicle_appraisals.delete_one({"_id": ObjectId(appr_id)})
        _run(cl())
