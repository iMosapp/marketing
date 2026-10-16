"""Iteration 399 (testing agent): Photo Intelligence controls (scopes, test orgs, Pause All), usage report shape, live signed-webhook
scope behaviour, Pause All on rep uploads, and photo suggestion accept/reject over HTTP. Restores 'no settings doc' at the end."""
import base64
import io
import os
import time
from datetime import datetime, timezone

import pytest
from bson import ObjectId

from tests._http import call
from tests.live_auth import STORE_A, Session, ensure_qa_user
from tests.test_mms_stage1 import FAKE_TWILIO_MEDIA, _signed_inbound, _wait

KEY = "jessi_mms_vision"
QA_ORG = "org_001"
REP_NUMBER = "+15005550077"
FOREST_ORG = "69a907033b77512d1d8d8a08"


@pytest.fixture(scope="module", autouse=True)
def restore(mongo):
    before = mongo.settings.find_one({"key": KEY})
    t0 = datetime.now(timezone.utc)
    yield
    if before:
        mongo.settings.replace_one({"key": KEY}, before)
    else:
        mongo.settings.delete_one({"key": KEY})
    mongo.vision_settings_events.delete_many({"at": {"$gte": t0}})


@pytest.fixture(scope="module")
def mms_rep(mongo):
    email, pw = ensure_qa_user(mongo, "qa-mms-rep@invalid.imonsocial.test", "user", QA_ORG, STORE_A, "QA Mms Rep")
    mongo.users.update_one({"email": email}, {"$set": {"twilio_number": REP_NUMBER, "ai_master_paused": False}, "$unset": {"default_campaign_id": ""}})
    yield mongo.users.find_one({"email": email}), pw
    mongo.users.update_one({"email": email}, {"$unset": {"twilio_number": ""}})


@pytest.fixture
def thread(mongo, mms_rep):
    made = []

    def make(name="QA PI399"):
        rep_id = str(mms_rep[0]["_id"])
        phone = f"+1500555{int(time.time() * 1000) % 10000:04d}"
        cid = mongo.contacts.insert_one({"user_id": rep_id, "phone": phone, "name": name, "first_name": "QA", "last_name": "PI",
                                         "status": "active", "created_at": datetime.utcnow()}).inserted_id
        conv = mongo.conversations.insert_one({"user_id": rep_id, "rep_phone": REP_NUMBER, "contact_id": str(cid), "contact_phone": phone, "contact_name": name,
                                               "status": "active", "ai_mode": "draft_only", "ai_enabled": True, "needs_assistance": False,
                                               "created_at": datetime.utcnow(), "last_message_at": datetime.utcnow()}).inserted_id
        made.append((cid, conv))
        return rep_id, str(cid), str(conv), phone
    yield make
    for cid, conv in made:
        mongo.ai_reply_queue.update_many({"conversation_id": str(conv), "status": "pending"}, {"$set": {"status": "cancelled"}})
        for coll in ("messages", "notifications", "ai_reply_queue"):
            mongo[coll].delete_many({"conversation_id": str(conv)})
        for coll in ("vision_usage", "contact_events", "contact_files"):
            mongo[coll].delete_many({"contact_id": str(cid)})
        mongo.conversations.delete_one({"_id": conv})
        mongo.contacts.delete_one({"_id": cid})


def _put(sa, **kw):
    st, b = sa.put("/api/jessi-vision/settings", kw)
    assert st == 200, (st, b)
    return b


# ── auth gates ──
def test_role_gates(super_admin, store_manager, org_admin, rep):
    for m, p in (("GET", "/api/jessi-vision/settings"), ("PUT", "/api/jessi-vision/settings"), ("GET", "/api/jessi-vision/usage"),
                 ("POST", "/api/jessi-vision/test-orgs/mine"), ("DELETE", f"/api/jessi-vision/test-orgs/{QA_ORG}")):
        assert call(m, p, {"paused": False} if m == "PUT" else None)[0] == 401, (m, p)
        for who in (store_manager, org_admin, rep):
            st, _ = getattr(who, m.lower())(p, {"paused": False}) if m == "PUT" else getattr(who, m.lower())(p)
            assert st == 403, (m, p, st)


def test_unset_defaults(super_admin, mongo):
    mongo.settings.delete_one({"key": KEY})
    st, b = super_admin.get("/api/jessi-vision/settings")
    assert st == 200
    assert (b["replies"], b["intelligence"], b["paused"]) == ("off", "off", False)
    assert b["scopes"] == ["off", "test_orgs", "all"] and b["test_orgs"] == [] and b["model"]
    assert b["my_org"]["id"] == FOREST_ORG and b["my_org"]["is_test"] is False and b["my_org"]["replies_on"] is False
    assert "updated_at" in b and "updated_by" in b


def test_put_validation_and_events(super_admin, mongo):
    assert super_admin.put("/api/jessi-vision/settings", {"replies": "everyone"})[0] == 422
    assert super_admin.put("/api/jessi-vision/settings", {"intelligence": "ON"})[0] == 422
    assert super_admin.put("/api/jessi-vision/settings", {})[0] == 422
    n0 = mongo.vision_settings_events.count_documents({})
    b = _put(super_admin, replies="test_orgs")
    assert b["replies"] == "test_orgs" and b["intelligence"] == "off" and b["updated_by"] == "forest@imosapp.com"
    ev = mongo.vision_settings_events.find_one(sort=[("at", -1)])
    assert mongo.vision_settings_events.count_documents({}) == n0 + 1
    assert ev["before"]["replies"] == "off" and ev["after"]["replies"] == "test_orgs" and ev["by"] == "forest@imosapp.com"
    assert super_admin.get("/api/jessi-vision/settings")[1]["replies"] == "test_orgs"


def test_test_orgs_and_scope_reflection(super_admin, mongo):
    _put(super_admin, replies="test_orgs", intelligence="test_orgs", paused=False)
    st, b = super_admin.post("/api/jessi-vision/test-orgs/mine")
    assert st == 200 and b["my_org"]["is_test"] is True and any(o["id"] == FOREST_ORG and o["name"] != FOREST_ORG for o in b["test_orgs"])
    assert b["my_org"]["replies_on"] is True and b["my_org"]["intelligence_on"] is True
    b = super_admin.post("/api/jessi-vision/test-orgs/mine")[1]   # idempotent
    assert [o["id"] for o in b["test_orgs"]].count(FOREST_ORG) == 1
    b = _put(super_admin, paused=True)
    assert b["paused"] is True and b["my_org"]["replies_on"] is False and b["my_org"]["intelligence_on"] is False
    b = _put(super_admin, paused=False, intelligence="off")
    assert b["my_org"]["replies_on"] is True and b["my_org"]["intelligence_on"] is False
    st, b = super_admin.delete(f"/api/jessi-vision/test-orgs/{FOREST_ORG}")
    assert st == 200 and b["my_org"]["is_test"] is False and b["my_org"]["replies_on"] is False
    b = _put(super_admin, replies="all")
    assert b["my_org"]["replies_on"] is True and b["my_org"]["is_test"] is False


# ── usage report ──
def test_usage_shape_and_clamp(super_admin):
    for q, n in (("0", 1), ("7", 7), ("9999", 365), ("-5", 1)):
        st, b = super_admin.get(f"/api/jessi-vision/usage?days={q}")
        assert st == 200 and b["days"] == n and len(b["daily"]) == n, (q, st, b if st != 200 else b["days"])
    assert super_admin.get("/api/jessi-vision/usage?days=abc")[0] == 422
    b = super_admin.get("/api/jessi-vision/usage?days=30")[1]
    assert b["cost_basis"] == "estimate" and "Estimated" in b["cost_method"]
    for k in ("totals", "daily", "monthly", "organizations", "stores", "reps", "by_source", "by_model", "monitoring"):
        assert k in b, k
    assert set(b["monitoring"]) >= {"unattributed_rows", "duplicate_processing"}
    for k in ("received", "analyzed", "reused", "successful", "failed", "est_cost_usd", "active_reps", "avg_cost_per_analyzed", "cost_per_active_rep"):
        assert k in b["totals"], k
    assert b["daily"][-1]["day"] == datetime.now(timezone.utc).strftime("%Y-%m-%d")


def test_usage_attribution_with_rows(super_admin, mongo, mms_rep):
    rep_id = str(mms_rep[0]["_id"])
    now = datetime.now(timezone.utc)
    tag = f"TEST_pi399_{int(time.time())}"
    base = {"organization_id": QA_ORG, "store_id": STORE_A, "user_id": rep_id, "contact_id": tag, "file_id": "", "model": "openai/gpt-5.4",
            "day": now.strftime("%Y-%m-%d"), "month": now.strftime("%Y-%m"), "created_at": now, "cost_basis": "estimate"}
    rows = [{**base, "message_id": tag, "i": 0, "source": "mms", "analyzed": True, "ok": True, "cached": False, "reason": "", "est_cost_usd": 0.01, "ms": 1000},
            {**base, "message_id": tag, "i": 0, "source": "mms", "analyzed": True, "ok": True, "cached": False, "reason": "", "est_cost_usd": 0.01, "ms": 1000},
            {**base, "message_id": tag + "b", "i": 0, "source": "mms", "analyzed": False, "ok": True, "cached": True, "reason": "", "est_cost_usd": 0},
            {**base, "message_id": tag + "c", "i": 0, "source": "mms", "analyzed": False, "ok": False, "cached": False, "reason": "fetch_failed", "est_cost_usd": 0},
            {**base, "organization_id": "", "store_id": "", "message_id": None, "i": None, "source": "upload", "analyzed": True, "ok": False, "cached": False,
             "reason": "unreadable", "est_cost_usd": 0.002}]
    b0 = super_admin.get("/api/jessi-vision/usage?days=1")[1]
    mongo.vision_usage.insert_many(rows)
    try:
        b = super_admin.get("/api/jessi-vision/usage?days=1")[1]
        d = lambda k: b["totals"][k] - b0["totals"][k]
        assert (d("received"), d("analyzed"), d("reused"), d("fetch_failed"), d("failed")) == (4, 3, 1, 1, 1)
        assert round(d("est_cost_usd"), 4) == 0.022
        assert b["monitoring"]["unattributed_rows"] - b0["monitoring"]["unattributed_rows"] == 1
        assert b["monitoring"]["duplicate_processing"] - b0["monitoring"]["duplicate_processing"] == 1
        org = next(o for o in b["organizations"] if o["organization_id"] == QA_ORG)
        assert org["name"] == "QA org_001"
        r = next(x for x in b["reps"] if x["user_id"] == rep_id)
        assert r["name"] and r["name"] != "Unknown rep" and r["org_name"] == "QA org_001"
        assert any(s["store_id"] == STORE_A and s["name"] != "No location" for s in b["stores"])
        assert {s["source"] for s in b["by_source"]} >= {"mms", "upload"}
        # cost logs never carry image content
        for row in mongo.vision_usage.find({}).limit(200):
            assert not ({"summary", "text", "visible", "fields"} & set(row)), row.keys()
    finally:
        mongo.vision_usage.delete_many({"contact_id": tag})
        mongo.vision_usage.delete_many({"user_id": rep_id, "source": "upload", "organization_id": "", "created_at": now})


# ── live signed webhook per scope ──
def _photo(mongo, phone, sid):
    form = {"MessageSid": sid, "AccountSid": os.environ.get("TWILIO_ACCOUNT_SID", ""), "From": phone, "To": REP_NUMBER,
            "Body": "", "NumMedia": "1", "MediaUrl0": FAKE_TWILIO_MEDIA, "MediaContentType0": "image/jpeg"}
    return form


def _run(mongo, conv, form, twice=False):
    assert _signed_inbound(form) in (200, 204)
    if twice:
        assert _signed_inbound(form) in (200, 204)
    q = _wait(lambda: mongo.ai_reply_queue.find_one({"conversation_id": conv}, sort=[("created_at", -1)]), seconds=90)
    assert q, "no draft queued"
    mongo.ai_reply_queue.update_many({"conversation_id": conv, "status": "pending"}, {"$set": {"status": "cancelled", "cancel_reason": "qa_test"}})
    time.sleep(3)
    note = mongo.notifications.find_one({"conversation_id": conv, "type": "you_are_needed", "title": {"$regex": "photo"}}, sort=[("created_at", -1)])
    return q, note


@pytest.mark.parametrize("cfg,stage2", [
    ({"replies": "test_orgs", "test_org_ids": [QA_ORG]}, True),
    ({"replies": "test_orgs", "test_org_ids": [FOREST_ORG]}, False),
    ({"replies": "all", "test_org_ids": []}, True),
    ({"replies": "off", "test_org_ids": [QA_ORG]}, False),
    ({"replies": "all", "test_org_ids": [], "paused": True}, False),
])
def test_webhook_scope(mongo, thread, cfg, stage2):
    mongo.settings.replace_one({"key": KEY}, {"key": KEY, "intelligence": "off", "paused": False, **cfg}, upsert=True)
    rep_id, cid, conv, phone = thread()
    q, note = _run(mongo, conv, _photo(mongo, phone, f"MMqa399{int(time.time() * 1000)}"))
    print("\n", cfg, "->", q.get("photo_status"), "|", (note or {}).get("title"), "/", (note or {}).get("message"), "| draft:", q.get("body"))
    if stage2:
        assert q["photo_status"] == "failed" and note and "couldn't open" in note["message"]
    else:
        assert q.get("photo_status") is None and note and "Jessi can't see it" in note["title"]
    rows = list(mongo.vision_usage.find({"contact_id": cid}))
    assert len(rows) == 1 and rows[0]["reason"] == "fetch_failed" and rows[0]["est_cost_usd"] == 0 and rows[0]["organization_id"] == QA_ORG


def test_webhook_duplicate_delivery_once(mongo, thread):
    mongo.settings.replace_one({"key": KEY}, {"key": KEY, "replies": "test_orgs", "intelligence": "off", "paused": False, "test_org_ids": [QA_ORG]}, upsert=True)
    rep_id, cid, conv, phone = thread()
    q, note = _run(mongo, conv, _photo(mongo, phone, f"MMqa399d{int(time.time() * 1000)}"), twice=True)
    time.sleep(4)
    assert mongo.messages.count_documents({"conversation_id": conv, "sender": "contact"}) == 1
    assert mongo.ai_reply_queue.count_documents({"conversation_id": conv}) == 1
    assert mongo.vision_usage.count_documents({"contact_id": cid}) == 1
    assert mongo.notifications.count_documents({"conversation_id": conv, "title": {"$regex": "photo"}}) == 1


def test_plain_text_still_drafts(mongo, thread):
    mongo.settings.replace_one({"key": KEY}, {"key": KEY, "replies": "all", "intelligence": "all", "paused": False, "test_org_ids": []}, upsert=True)
    rep_id, cid, conv, phone = thread()
    form = {"MessageSid": f"SMqa399{int(time.time() * 1000)}", "AccountSid": os.environ.get("TWILIO_ACCOUNT_SID", ""), "From": phone, "To": REP_NUMBER,
            "Body": "Do you have any blue SUVs in stock?", "NumMedia": "0"}
    assert _signed_inbound(form) in (200, 204)
    q = _wait(lambda: mongo.ai_reply_queue.find_one({"conversation_id": conv}), seconds=60)
    assert q and q.get("body") and q.get("photo_status") is None
    assert mongo.vision_usage.count_documents({"contact_id": cid}) == 0


# ── Pause All on rep uploads ──
def test_pause_blocks_rep_upload_reads(mongo, thread, mms_rep):
    from PIL import Image
    mongo.settings.replace_one({"key": KEY}, {"key": KEY, "replies": "all", "intelligence": "all", "paused": True, "test_org_ids": []}, upsert=True)
    rep_id, cid, conv, _ = thread()
    s = Session(mms_rep[0]["email"], mms_rep[1])
    buf = io.BytesIO()
    Image.new("RGB", (64, 48), (200, 30, 30)).save(buf, "PNG")
    st, b = s.post(f"/api/contact-files/{rep_id}/chunk", {"upload_id": f"qa399{int(time.time())}", "index": 0, "total": 1,
                                                         "data": base64.b64encode(buf.getvalue()).decode(), "name": "qa.png", "content_type": "image/png", "contact_id": cid})
    assert st == 200, (st, b)
    doc = mongo.contact_files.find_one({"contact_id": cid})
    assert doc["status"] == "unread" and doc.get("unread_reason") == "paused"
    assert mongo.vision_usage.count_documents({"contact_id": cid, "analyzed": True}) == 0


# ── photo suggestions over HTTP ──
def test_add_suggestion_appends_never_replaces(mongo, thread, mms_rep):
    rep_id, cid, conv, _ = thread()
    s = Session(mms_rep[0]["email"], mms_rep[1])
    sugs = [{"id": "a1", "field": "interests", "label": "Interest (from a photo)", "old": "", "new": "Fishing (seen in a photo)", "mode": "add", "basis": "visible", "source": "a photo"},
            {"id": "a2", "field": "personal_notes", "label": "Note (from a photo)", "old": "", "new": "Has a dog (seen in a photo)", "mode": "add", "basis": "visible", "source": "a photo"},
            {"id": "a3", "field": "interests", "label": "Interest (from a photo)", "old": "", "new": "Golf (Jessi's guess)", "mode": "add", "basis": "inferred", "source": "a photo"}]
    mongo.contacts.update_one({"_id": ObjectId(cid)}, {"$set": {"personal_details": {"interests": ["Boating"], "personal_notes": "Likes coffee"}, "detail_suggestions": sugs}})
    assert s.post(f"/api/contact-intel/{rep_id}/{cid}/suggestions/a1", {"action": "accept"})[0] == 200
    assert s.post(f"/api/contact-intel/{rep_id}/{cid}/suggestions/a2", {"action": "accept"})[0] == 200
    st, b = s.post(f"/api/contact-intel/{rep_id}/{cid}/suggestions/a3", {"action": "reject"})
    assert st == 200 and b["suggestions"] == []
    c = mongo.contacts.find_one({"_id": ObjectId(cid)})
    assert c["personal_details"]["interests"] == ["Boating", "Fishing (seen in a photo)"]
    assert c["personal_details"]["personal_notes"] == "Likes coffee; Has a dog (seen in a photo)"
    assert any(r["new"].startswith("Golf") for r in c["detail_suggestions_rejected"])
    assert s.post(f"/api/contact-intel/{rep_id}/{cid}/suggestions/zzz", {"action": "accept"})[0] == 404
    assert s.post(f"/api/contact-intel/{rep_id}/{cid}/suggestions/a1", {"action": "maybe"})[0] in (400, 422)


def test_suggestion_decision_requires_auth_and_ownership(mongo, thread, rep):
    rep_id, cid, conv, _ = thread()
    mongo.contacts.update_one({"_id": ObjectId(cid)}, {"$set": {"detail_suggestions": [{"id": "x1", "field": "interests", "new": "X", "mode": "add", "source": "a photo"}]}})
    st_anon = call("POST", f"/api/contact-intel/{rep_id}/{cid}/suggestions/x1", {"action": "reject"})[0]
    st_other = rep.post(f"/api/contact-intel/{rep_id}/{cid}/suggestions/x1", {"action": "reject"})[0]
    left = mongo.contacts.find_one({"_id": ObjectId(cid)}).get("detail_suggestions") or []
    print(f"\nanon={st_anon} other-rep={st_other} remaining={len(left)}")
    assert st_anon == 401
    assert st_other in (403, 404) and len(left) == 1, "another user could decide a suggestion on a contact they do not own"
