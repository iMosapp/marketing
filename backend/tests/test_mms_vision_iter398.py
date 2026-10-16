# Iteration 398 (testing agent): MMS Stage 2 photo understanding - kill switch API, usage log, webhook paths (switch ON/OFF),
# paused-for-human photo alert, plain-text inbound regression (queue_ai_reply message_id kwarg), private guard, ai-suggest photo content.
# Every conversation is draft_only, every queued draft is cancelled and removed, the switch document is restored at the end.
import os
import re
import time
from datetime import datetime, timedelta

import pytest
from bson import ObjectId

from tests.live_auth import STORE_A, ensure_qa_user, anon, Session
from tests import qa_creds
from tests.test_mms_stage1 import _signed_inbound, _wait

QA_ORG_A = "org_001"
REP_NUMBER = "+15005550077"
KEY = "jessi_mms_vision"


def _media_url(tag: str) -> str:
    h = (tag.encode().hex() * 32)[:32]
    return f"https://api.twilio.com/2010-04-01/Accounts/AC{'c' * 32}/Messages/MM{h}/Media/ME{h}"


@pytest.fixture(scope="module", autouse=True)
def restore_switch(mongo):
    before = mongo.settings.find_one({"key": KEY})
    yield
    if before:
        mongo.settings.replace_one({"key": KEY}, before, upsert=True)
    else:
        mongo.settings.delete_one({"key": KEY})


def _set(mongo, on):
    if on is None:
        mongo.settings.delete_one({"key": KEY})
    else:
        # Photo Replies on (test org rollout for the QA org) or off; Photo Intelligence stays off here
        mongo.settings.replace_one({"key": KEY}, {"key": KEY, "replies": "test_orgs" if on else "off", "intelligence": "off", "paused": False,
                                                  "test_org_ids": [QA_ORG_A]}, upsert=True)


@pytest.fixture(scope="module")
def mms_rep(mongo):
    email, _ = ensure_qa_user(mongo, "qa-mms-rep@invalid.imonsocial.test", "user", QA_ORG_A, STORE_A, "QA Mms Rep")
    mongo.users.update_one({"email": email}, {"$set": {"twilio_number": REP_NUMBER, "ai_master_paused": False}, "$unset": {"default_campaign_id": ""}})
    rep = mongo.users.find_one({"email": email})
    yield rep
    mongo.users.update_one({"_id": rep["_id"]}, {"$unset": {"twilio_number": ""}})


@pytest.fixture
def thread(mongo, mms_rep):
    made = []

    def make(name="TEST Photo", **conv_extra):
        rep_id = str(mms_rep["_id"])
        time.sleep(0.01)
        phone = f"+1500555{int(time.time() * 1000) % 10000:04d}"
        mongo.contacts.delete_many({"user_id": rep_id, "phone": phone})
        mongo.conversations.delete_many({"rep_phone": REP_NUMBER, "contact_phone": phone})
        cid = mongo.contacts.insert_one({"user_id": rep_id, "phone": phone, "name": name, "first_name": name.split()[0], "last_name": name.split()[-1],
                                         "status": "active", "created_at": datetime.utcnow()}).inserted_id
        conv = mongo.conversations.insert_one({"user_id": rep_id, "rep_phone": REP_NUMBER, "contact_id": str(cid), "contact_phone": phone, "contact_name": name,
                                               "status": "active", "ai_mode": "draft_only", "ai_enabled": True, "needs_assistance": False,
                                               "created_at": datetime.utcnow(), "last_message_at": datetime.utcnow(), **conv_extra}).inserted_id
        made.append((cid, conv))
        return rep_id, str(cid), str(conv), phone
    yield make
    for cid, conv in made:
        mongo.ai_reply_queue.update_many({"conversation_id": str(conv), "status": "pending"}, {"$set": {"status": "cancelled", "cancel_reason": "qa_test"}})
        for coll in ("messages", "notifications", "ai_reply_queue"):
            mongo[coll].delete_many({"conversation_id": str(conv)})
        mongo.vision_usage.delete_many({"contact_id": str(cid)})
        mongo.contact_files.delete_many({"contact_id": str(cid)})
        mongo.conversations.delete_one({"_id": conv})
        mongo.contacts.delete_one({"_id": cid})


def _form(phone, body="", media=None, sid_tag=""):
    f = {"MessageSid": f"MMqa398{int(time.time() * 1000)}{sid_tag}", "AccountSid": os.environ.get("TWILIO_ACCOUNT_SID", ""), "From": phone, "To": REP_NUMBER,
         "Body": body, "NumMedia": str(len(media or []))}
    for i, u in enumerate(media or []):
        f[f"MediaUrl{i}"], f[f"MediaContentType{i}"] = u, "image/jpeg"
    return f


def _photo_notes(mongo, conv):
    return mongo.notifications.count_documents({"conversation_id": conv, "type": "you_are_needed", "title": {"$regex": "sent .*photo"}})


# ── Kill switch + usage API ──────────────────────────────────────────────────────────────────────────────────────────


def test_settings_unset_is_off_and_role_gates(super_admin, store_manager, org_admin, rep, mongo):
    _set(mongo, None)
    code, d = super_admin.get("/api/jessi-vision/settings")
    assert code == 200 and (d["replies"], d["intelligence"], d["paused"], d["test_orgs"]) == ("off", "off", False, []) and d["model"] == "openai/gpt-5.4"
    assert anon("GET", "/api/jessi-vision/settings")[0] == 401
    assert anon("PUT", "/api/jessi-vision/settings", {"replies": "all"})[0] == 401
    assert anon("POST", "/api/jessi-vision/test-orgs/mine", {})[0] == 401
    assert anon("GET", "/api/jessi-vision/usage")[0] == 401
    for s in (rep, store_manager, org_admin):
        assert s.get("/api/jessi-vision/settings")[0] == 403, s.email
        assert s.put("/api/jessi-vision/settings", {"replies": "all"})[0] == 403, s.email
        assert s.post("/api/jessi-vision/test-orgs/mine", {})[0] == 403, s.email
        assert s.delete("/api/jessi-vision/test-orgs/org_001")[0] == 403, s.email
        assert s.get("/api/jessi-vision/usage?days=7")[0] == 403, s.email
    assert mongo.settings.find_one({"key": KEY}) is None, "a non-super-admin PUT created the switch"


def test_settings_put_persists_and_validates(super_admin, mongo):
    code, d = super_admin.put("/api/jessi-vision/settings", {"replies": "all", "intelligence": "test_orgs"})
    assert code == 200 and d["replies"] == "all" and d["intelligence"] == "test_orgs" and d["updated_by"] and d["updated_at"]
    assert mongo.settings.find_one({"key": KEY})["replies"] == "all"
    assert super_admin.get("/api/jessi-vision/settings")[1]["intelligence"] == "test_orgs"
    assert super_admin.put("/api/jessi-vision/settings", {})[0] == 422
    assert super_admin.put("/api/jessi-vision/settings", {"replies": "maybe"})[0] == 422
    assert super_admin.put("/api/jessi-vision/settings", {"paused": "maybe"})[0] == 422
    code, d = super_admin.put("/api/jessi-vision/settings", {"replies": "off", "intelligence": "off"})
    assert code == 200 and d["replies"] == "off" and mongo.settings.find_one({"key": KEY})["intelligence"] == "off"


def test_usage_aggregates_per_org(super_admin, mongo):
    org = "TEST_org_398"
    now = datetime.utcnow()
    day = lambda d: d.strftime("%Y-%m-%d")
    rows = [{"organization_id": org, "source": "mms", "analyzed": True, "ok": True, "cached": False, "est_cost_usd": 0.0021, "created_at": now, "day": day(now), "contact_id": "TEST_398", "user_id": "u1"},
            {"organization_id": org, "source": "mms", "analyzed": False, "ok": True, "cached": True, "est_cost_usd": 0.0, "created_at": now, "day": day(now), "contact_id": "TEST_398", "user_id": "u1"},
            {"organization_id": org, "source": "mms", "analyzed": True, "ok": False, "cached": False, "est_cost_usd": 0.0, "created_at": now, "day": day(now), "contact_id": "TEST_398", "user_id": "u2"},
            {"organization_id": org, "source": "mms", "analyzed": True, "ok": True, "cached": False, "est_cost_usd": 5.0, "created_at": now - timedelta(days=20), "day": day(now - timedelta(days=20)), "contact_id": "TEST_398", "user_id": "u1"}]
    mongo.vision_usage.insert_many(rows)
    try:
        code, u = super_admin.get("/api/jessi-vision/usage?days=7")
        assert code == 200 and u["days"] == 7
        mine = [o for o in u["organizations"] if o["organization_id"] == org]
        assert len(mine) == 1, u
        o = mine[0]
        assert (o["received"], o["analyzed"], o["reused"], o["successful"], o["failed"], o["active_reps"]) == (3, 2, 1, 1, 1, 2), o
        assert abs(o["est_cost_usd"] - 0.0021) < 1e-6 and abs(o["cost_per_active_rep"] - 0.00105) < 1e-4, o
        u30 = super_admin.get("/api/jessi-vision/usage?days=30")[1]
        o30 = [x for x in u30["organizations"] if x["organization_id"] == org][0]
        assert o30["received"] == 4 and abs(o30["est_cost_usd"] - 5.0021) < 1e-6
        assert u30["totals"]["est_cost_usd"] >= 5.0 and len(u30["daily"]) == 30
        for bad in ("0", "-5", "100000"):
            assert super_admin.get(f"/api/jessi-vision/usage?days={bad}")[0] == 200
        assert super_admin.get("/api/jessi-vision/usage?days=abc")[0] == 422
    finally:
        mongo.vision_usage.delete_many({"contact_id": "TEST_398"})


# ── Regression: queue_ai_reply(message_id=...) ─────────────────────────────────────────────────────────────────────


def test_plain_text_inbound_still_queues_a_draft(mongo, thread):
    _set(mongo, True)
    rep_id, cid, conv, phone = thread("TEST Plain")
    assert _signed_inbound(_form(phone, "Hi, what time are you open on Saturday?")) in (200, 204)
    q = _wait(lambda: mongo.ai_reply_queue.find_one({"conversation_id": conv}), seconds=60)
    assert q, "no draft queued for a plain-text inbound (queue_ai_reply message_id regression)"
    assert q.get("attachments", 0) == 0 and q.get("photo_status") is None and q["requires_approval"] is True and q["body"]
    assert _photo_notes(mongo, conv) == 0


def test_plain_text_inbound_switch_off_queues_a_draft(mongo, thread):
    _set(mongo, False)
    rep_id, cid, conv, phone = thread("TEST PlainOff")
    assert _signed_inbound(_form(phone, "Do you have any trucks under 30k?")) in (200, 204)
    q = _wait(lambda: mongo.ai_reply_queue.find_one({"conversation_id": conv}), seconds=60)
    assert q and q["body"], "no draft queued for a plain-text inbound with switch off"


# ── Webhook, switch ON ─────────────────────────────────────────────────────────────────────────────────────────────


def test_webhook_on_fetch_failed_and_every_photo_flags_rep(mongo, thread):
    _set(mongo, True)
    rep_id, cid, conv, phone = thread("TEST WebOn")
    assert _signed_inbound(_form(phone, "", [_media_url("on1")])) in (200, 204)
    q = _wait(lambda: mongo.ai_reply_queue.find_one({"conversation_id": conv}), seconds=90)
    assert q, "no draft"
    msg = mongo.messages.find_one({"conversation_id": conv, "sender": "contact", "has_media": True})
    print("\nON draft:", q["body"], "| read:", msg.get("media_read"))
    assert "/api/webhooks/twilio/media-proxy?url=" in msg["media_urls"][0]
    assert msg["media_read"] and msg["media_read"][0]["reason"] == "fetch_failed" and msg["media_read"][0]["ok"] is False
    assert "media_read_pending" not in msg
    assert q["photo_status"] == "failed" and q["requires_approval"] is True
    body = q["body"].lower()
    assert any(w in body for w in ("again", "resend", "re-send", "come through", "send it")), q["body"]
    assert not any(w in body for w in ("looks like", "the photo shows", "i see ", "i'll send")), q["body"]
    n = mongo.notifications.find_one({"conversation_id": conv, "type": "you_are_needed", "title": {"$regex": "sent a photo"}})
    assert n and n["title"] == "TEST WebOn sent a photo" and "couldn't open" in n["message"] and n.get("photo_status") == "failed", n
    assert mongo.conversations.find_one({"_id": ObjectId(conv)})["needs_assistance"] is True
    # second photo-only text within 30 min: the rep is flagged AGAIN (no suppression with switch on)
    assert _signed_inbound(_form(phone, "", [_media_url("on2"), _media_url("on3")], "b")) in (200, 204)
    assert _wait(lambda: _photo_notes(mongo, conv) >= 2, seconds=90), "second photo did not notify the rep with switch on"
    n2 = mongo.notifications.find_one({"conversation_id": conv, "title": {"$regex": "sent 2 photos"}})
    assert n2, "second notification title should say 2 photos"
    time.sleep(3)
    print("drafts after 2nd photo:", [d["body"] for d in mongo.ai_reply_queue.find({"conversation_id": conv})])


def test_webhook_on_paused_for_human_no_draft_but_alert(mongo, thread):
    _set(mongo, True)
    rep_id, cid, conv, phone = thread("TEST Paused", ai_paused_for_human=True, needs_assistance=True)
    assert _signed_inbound(_form(phone, "", [_media_url("pz")])) in (200, 204)
    assert _wait(lambda: _photo_notes(mongo, conv) >= 1, seconds=90), "paused conversation got no 'sent a photo' alert"
    time.sleep(3)
    assert mongo.ai_reply_queue.count_documents({"conversation_id": conv}) == 0, "paused conversation got a draft"


# ── Webhook, switch OFF (Stage 1 unchanged) ──────────────────────────────────────────────────────────────────────────


def test_webhook_off_stage1_unchanged(mongo, thread):
    _set(mongo, False)
    rep_id, cid, conv, phone = thread("TEST WebOff")
    assert _signed_inbound(_form(phone, "", [_media_url("off1")])) in (200, 204)
    q = _wait(lambda: mongo.ai_reply_queue.find_one({"conversation_id": conv}), seconds=90)
    assert q, "no draft"
    print("\nOFF draft:", q["body"])
    assert q.get("photo_status") is None
    n = mongo.notifications.find_one({"conversation_id": conv, "type": "you_are_needed", "title": {"$regex": "sent a photo"}})
    assert n and "Jessi can't see it" in n["title"], n
    body = q["body"].lower()
    for claim in ("looks like", "the photo shows", "i can see", "didn't come through"):
        assert claim not in body, (claim, q["body"])
    drafts, notes = mongo.ai_reply_queue.count_documents({"conversation_id": conv}), _photo_notes(mongo, conv)
    assert _signed_inbound(_form(phone, "", [_media_url("off2")], "b")) in (200, 204)
    time.sleep(10)
    assert mongo.ai_reply_queue.count_documents({"conversation_id": conv}) == drafts, "second draft within 30 min"
    assert _photo_notes(mongo, conv) == notes, "second notification within 30 min (switch off)"


# ── Private document guard ───────────────────────────────────────────────────────────────────────────────────────


def test_guard_private_and_sensitive_items():
    from services.mms_vision import guard_private, PRIVATE_SAFE_REPLY, reply_block
    p = {"status": "private"}
    for bad in ("Got it, DL 98-765-4321", "Thanks, your DOB 1988 is noted", "Policy 12345 received", "Card ending 4 4 1 2 thanks"):
        assert guard_private(bad, p) == PRIVATE_SAFE_REPLY, bad
    assert guard_private("Thanks for sending that, the team will take it from here.", p).startswith("Thanks for sending")
    assert guard_private("Your VIN 1HGCM82633A004352", {"status": "seen"}).startswith("Your VIN")
    assert guard_private("Call 5551234", None) == "Call 5551234"
    b = reply_block([{"ok": True, "type": "insurance_card", "sensitive": True, "summary": "", "visible": "", "text": "", "fields": {}}], "")
    assert b["status"] == "private" and "insurance card" in b["block"] and "Never repeat" in b["block"]


def test_stored_sensitive_items_carry_no_content(mongo):
    """Any media_read stored so far with sensitive=True must have empty summary/visible/text/fields."""
    leaks = []
    for m in mongo.messages.find({"media_read.sensitive": True}, {"media_read": 1}).limit(200):
        for i in m["media_read"]:
            if i.get("sensitive") and (i.get("summary") or i.get("visible") or i.get("text") or i.get("fields") or i.get("title")):
                leaks.append(str(m["_id"]))
    assert not leaks, leaks


# ── Ask Jessi (manual suggestion) ────────────────────────────────────────────────────────────────────────────────────


def _suggest_thread(mongo, mms_rep, thread, read):
    rep_id, cid, conv, phone = thread("TEST Suggest")
    t0 = datetime.utcnow() - timedelta(minutes=5)
    mongo.messages.insert_many([
        {"conversation_id": conv, "contact_id": cid, "user_id": rep_id, "sender": "user", "direction": "outbound", "status": "sent",
         "content": "Hey, happy to help with your trade. Anything I should know about it?", "timestamp": t0},
        {"conversation_id": conv, "contact_id": cid, "user_id": rep_id, "sender": "contact", "direction": "inbound", "content": "what about this?",
         "media_urls": [_media_url("sg")], "media_types": ["image/jpeg"], "num_media": 1, "has_media": True, "media_read": read,
         "timestamp": t0 + timedelta(minutes=1)}])
    s = Session(mms_rep["email"], qa_creds.password_for(mms_rep["email"]))
    return s.post(f"/api/messages/ai-suggest/{conv}", {})


SEEN = [{"i": 0, "ok": True, "type": "trade_in", "sensitive": False, "summary": "Blue pickup truck with a large crack across the windshield",
         "visible": "Blue pickup truck, cracked windshield", "text": "", "fields": {}, "confidence": 0.9}]


def test_ai_suggest_uses_photo_when_on(mongo, mms_rep, thread):
    _set(mongo, True)
    code, d = _suggest_thread(mongo, mms_rep, thread, SEEN)
    assert code == 200 and d.get("suggestion"), (code, d)
    print("\nsuggest ON:", d["suggestion"])
    s = d["suggestion"].lower()
    assert any(w in s for w in ("windshield", "crack", "glass")), d["suggestion"]
    assert not any(w in s for w in ("can't see", "cannot see", "can't open", "the image shows")), d["suggestion"]


def test_ai_suggest_stage1_when_off(mongo, mms_rep, thread):
    _set(mongo, False)
    code, d = _suggest_thread(mongo, mms_rep, thread, SEEN)
    assert code == 200 and d.get("suggestion"), (code, d)
    print("\nsuggest OFF:", d["suggestion"])
    s = d["suggestion"].lower()
    assert not any(w in s for w in ("windshield", "crack", "blue")), d["suggestion"]


def test_ai_suggest_private_never_leaks(mongo, mms_rep, thread):
    _set(mongo, True)
    code, d = _suggest_thread(mongo, mms_rep, thread, [{"i": 0, "ok": True, "type": "id_document", "sensitive": True, "summary": "", "visible": "",
                                                         "text": "", "fields": {}, "confidence": 0.9}])
    assert code == 200 and d.get("suggestion"), (code, d)
    print("\nsuggest PRIVATE:", d["suggestion"])
    assert not re.search(r"\d{4,}", d["suggestion"]) and "thank" in d["suggestion"].lower(), d["suggestion"]
