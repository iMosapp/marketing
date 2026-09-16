"""In-process tests for prompt gateway, ai_reply routing, sample preview, and interview trim.

Uses backend python modules directly with an active DB. LLM calls (2-8s each).
"""
import asyncio
import os
import sys
from datetime import datetime, timezone
import pytest
import requests

sys.path.insert(0, "/app/backend")

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

MONGO = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
FOREST_ID = "69a0b7095fddcede09591667"
QAMGR_EMAIL = "qa-manager@invalid.imonsocial.test"


def _read_frontend_env():
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip().strip('"').rstrip("/")
    return ""

BASE_URL = _read_frontend_env()

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


def _db():
    client = AsyncIOMotorClient(MONGO)
    return client[DB_NAME]

import pytest_asyncio

@pytest_asyncio.fixture(loop_scope="session")
async def db():
    client = AsyncIOMotorClient(MONGO)
    return client[DB_NAME]


@pytest.fixture(scope="module")
def forest_tok():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": "forest@imosapp.com", "password": "Admin123!"}, timeout=15).json()
    return r.get("access_token") or r.get("token")


# ------------------------------------------------------ Interview trim
class TestInterviewTrim:
    def test_module_constants(self):
        from services import interview
        assert interview.MAX_MINUTES == 6
        assert interview.WRAP_AFTER_MINUTES == 4
        assert len(interview.BASE_TOPICS) == 9
        for banned in ("custom_phrases", "greeting_style", "signature"):
            assert banned not in interview.PERSONA_STR
            assert banned not in interview.PERSONA_LIST
            assert banned not in interview.PERSONA_ENUM

    def test_topics_automotive(self):
        from services.interview import topics
        t = topics("automotive")
        assert len(t) == 10
        assert t[5][0] == "vehicles"

    def test_topics_real_estate(self):
        from services.interview import topics
        t = topics("real_estate")
        keys = [k for k, _ in t]
        assert "interests" in keys

    def test_greeting_five_minutes(self):
        from services.interview import greeting
        g = greeting("Alex")
        assert "about five minutes" in g

    def test_serialize_labels(self):
        from services.interview import serialize
        s_auto = {"_id": ObjectId(), "status": "completed", "industry": "automotive", "turns": []}
        r_auto = serialize(s_auto)
        assert r_auto["topics_total"] == 10
        assert r_auto["labels"]["vehicles"] == "What you drive"
        s_re = {"_id": ObjectId(), "status": "completed", "industry": "real_estate", "turns": []}
        r_re = serialize(s_re)
        assert r_re["labels"]["interests"] == "Your neighborhood"


# ------------------------------------------------------ Prompt gateway
class TestPromptGateway:
    @pytest.mark.asyncio
    async def test_forest_new_prompt(self, db):
        # ensure forest has 'I am off Sundays' mine fact
        u = await db.users.find_one({"_id": ObjectId(FOREST_ID)}, {"va_facts": 1, "industry": 1})
        mine = u.get("va_facts") or []
        assert any("I am off Sundays" in (f.get("text") or "") for f in mine), "prereq: forest must have 'I am off Sundays' fact"
        from routers.ai_campaigns import build_clone_system_prompt
        prompt = await build_clone_system_prompt(FOREST_ID)
        assert prompt.startswith("You ARE Forest.")
        assert "FACTS (the ONLY source of specifics" in prompt
        assert "Automotive dealership" in prompt
        assert "I am off Sundays" in prompt

    @pytest.mark.asyncio
    async def test_qamgr_old_prompt_in_lab(self, db):
        u = await db.users.find_one({"email": QAMGR_EMAIL}, {"_id": 1})
        assert u
        from routers.ai_campaigns import build_clone_system_prompt
        prompt = await build_clone_system_prompt(str(u["_id"]))
        assert "Your Only Job" in prompt, f"expected OLD template; got: {prompt[:200]}"

    @pytest.mark.asyncio
    async def test_qamgr_new_prompt_when_live(self, db, forest_tok):
        # flip to live
        r = requests.put(f"{BASE_URL}/api/lab/features/industry_va",
                         headers={"Authorization": f"Bearer {forest_tok}"},
                         json={"status": "live"}, timeout=15)
        assert r.status_code == 200, r.text
        try:
            # need a store fact present
            store_fact_text = "We take walk-ins weekdays until 6 pm"
            s = await db.stores.find_one({"_id": ObjectId("69a0b7095fddcede09591668")}, {"va_facts": 1})
            has_it = any(store_fact_text in (f.get("text") or "") for f in (s.get("va_facts") or []))
            assert has_it, "prereq store fact missing"
            u = await db.users.find_one({"email": QAMGR_EMAIL}, {"_id": 1})
            from routers.ai_campaigns import build_clone_system_prompt
            prompt = await build_clone_system_prompt(str(u["_id"]))
            assert "FACTS (the ONLY source of specifics" in prompt
            assert store_fact_text in prompt
        finally:
            r = requests.put(f"{BASE_URL}/api/lab/features/industry_va",
                             headers={"Authorization": f"Bearer {forest_tok}"},
                             json={"status": "lab"}, timeout=15)
            assert r.status_code == 200


# ------------------------------------------------------ Sample preview
class TestSamplePreview:
    def test_price_ask_no_dollars(self, forest_tok):
        r = requests.post(f"{BASE_URL}/api/auth/persona/{FOREST_ID}/sample-message",
                          headers={"Authorization": f"Bearer {forest_tok}"},
                          json={"scenario": "What is the best price you can do on the white Tahoe? And what would the payment be?"},
                          timeout=45)
        assert r.status_code == 200, r.text
        msg = (r.json().get("message") or r.json().get("reply") or r.json().get("text") or "").lower()
        assert "$" not in msg, msg
        assert not any(w in msg for w in ("check", "get back", "let me")) == False, msg
        assert "—" not in msg

    def test_sunday_fact(self, forest_tok):
        r = requests.post(f"{BASE_URL}/api/auth/persona/{FOREST_ID}/sample-message",
                          headers={"Authorization": f"Bearer {forest_tok}"},
                          json={"scenario": "Are you around this Sunday?"},
                          timeout=45)
        assert r.status_code == 200
        msg = (r.json().get("message") or r.json().get("reply") or r.json().get("text") or "").lower()
        assert "sunday" in msg or "monday" in msg or "off" in msg
        assert "—" not in msg


# ------------------------------------------------------ Inbound routing (ai_reply)
class TestInboundRouting:
    @pytest.mark.asyncio
    async def _setup_convo(self, db):
        contact = {"name": "QA Router Test", "phone": "+15005551234", "assigned_user_id": FOREST_ID, "qa_test": True, "created_at": datetime.now(timezone.utc)}
        cid = (await db.contacts.insert_one(contact)).inserted_id
        conv = {"contact_id": str(cid), "assigned_user_id": FOREST_ID, "qa_test": True, "created_at": datetime.now(timezone.utc), "messages": []}
        conv_id = (await db.conversations.insert_one(conv)).inserted_id
        return str(cid), str(conv_id)

    async def _cleanup(self, db, cid, conv_id):
        await db.contacts.delete_one({"_id": ObjectId(cid)})
        await db.conversations.delete_one({"_id": ObjectId(conv_id)})
        await db.ai_reply_queue.delete_many({"conversation_id": conv_id})
        await db.notifications.delete_many({"link": {"$regex": conv_id}})

    @pytest.mark.asyncio
    async def test_case_a_fact_match(self, db):
        # add temp mine fact for forest
        text = "We take walk-ins weekdays until 6 pm"
        from services import va_prompt as _vp
        fact = _vp._fact(text, {"_id": ObjectId(FOREST_ID), "name": "Forest"}, "mine")
        await db.users.update_one({"_id": ObjectId(FOREST_ID)}, {"$push": {"va_facts": fact}})
        cid, conv_id = await self._setup_convo(db)
        try:
            from routers.ai_reply import queue_ai_reply, AI_MODE_AUTO_REPLY
            await queue_ai_reply(contact_id=cid, conversation_id=conv_id, enrollment_id="", campaign_id="",
                                 assigned_user_id=FOREST_ID,
                                 incoming_message="Do you guys take walk-ins or do I need an appointment?",
                                 ai_assist_mode=AI_MODE_AUTO_REPLY)
            await asyncio.sleep(1.0)
            docs = await db.ai_reply_queue.find({"conversation_id": conv_id}).to_list(5)
            assert docs, "no queue doc created"
            d = docs[-1]
            assert not d.get("hot_topic_escalation"), d
            assert "let me check on that and get back" not in (d.get("body") or "").lower()
            conv = await db.conversations.find_one({"_id": ObjectId(conv_id)})
            assert not conv.get("ai_paused_for_human"), conv
        finally:
            await db.users.update_one({"_id": ObjectId(FOREST_ID)}, {"$pull": {"va_facts": {"id": fact["id"]}}})
            await self._cleanup(db, cid, conv_id)

    @pytest.mark.asyncio
    async def test_case_b_hot_topic(self, db):
        cid, conv_id = await self._setup_convo(db)
        try:
            from routers.ai_reply import queue_ai_reply, AI_MODE_AUTO_REPLY
            await queue_ai_reply(contact_id=cid, conversation_id=conv_id, enrollment_id="", campaign_id="",
                                 assigned_user_id=FOREST_ID,
                                 incoming_message="What is the out the door price on the Tahoe?",
                                 ai_assist_mode=AI_MODE_AUTO_REPLY)
            await asyncio.sleep(0.5)
            docs = await db.ai_reply_queue.find({"conversation_id": conv_id}).to_list(5)
            assert docs
            d = docs[-1]
            assert d.get("hot_topic_escalation") is True, d
            assert "let me check on that and get back" in (d.get("body") or "").lower()
            conv = await db.conversations.find_one({"_id": ObjectId(conv_id)})
            assert conv.get("ai_paused_for_human") is True
        finally:
            await self._cleanup(db, cid, conv_id)

    @pytest.mark.asyncio
    async def test_case_c_real_estate_hold(self, db, forest_tok):
        # switch forest to real_estate
        r = requests.put(f"{BASE_URL}/api/va/industry", headers={"Authorization": f"Bearer {forest_tok}"},
                         json={"industry": "real_estate"}, timeout=15)
        assert r.status_code == 200
        cid, conv_id = await self._setup_convo(db)
        try:
            from routers.ai_reply import queue_ai_reply, AI_MODE_AUTO_REPLY
            await queue_ai_reply(contact_id=cid, conversation_id=conv_id, enrollment_id="", campaign_id="",
                                 assigned_user_id=FOREST_ID,
                                 incoming_message="Is the house on Maple still under contract?",
                                 ai_assist_mode=AI_MODE_AUTO_REPLY)
            await asyncio.sleep(0.5)
            d = (await db.ai_reply_queue.find({"conversation_id": conv_id}).to_list(5))[-1]
            assert d.get("hot_topic_escalation") is True, d

            # base hold word 'in stock' -> also hold
            cid2, conv2 = await self._setup_convo(db)
            try:
                await queue_ai_reply(contact_id=cid2, conversation_id=conv2, enrollment_id="", campaign_id="",
                                     assigned_user_id=FOREST_ID,
                                     incoming_message="Do you have it in stock?",
                                     ai_assist_mode=AI_MODE_AUTO_REPLY)
                await asyncio.sleep(0.5)
                d2 = (await db.ai_reply_queue.find({"conversation_id": conv2}).to_list(5))[-1]
                assert d2.get("hot_topic_escalation") is True, d2
            finally:
                await self._cleanup(db, cid2, conv2)
        finally:
            await self._cleanup(db, cid, conv_id)
            r = requests.put(f"{BASE_URL}/api/va/industry", headers={"Authorization": f"Bearer {forest_tok}"},
                             json={"industry": "automotive"}, timeout=15)
            assert r.status_code == 200
