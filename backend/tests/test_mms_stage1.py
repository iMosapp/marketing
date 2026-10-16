"""Stage 1 MMS repair: the media proxy follows Twilio's real MMS redirect host, Jessi is told about attachments she cannot
see (no guessing, one clarification, human flagged), and the preview/alert text for a photo-only inbound is never empty.
Live preview API + a read-only look at the shared Twilio account for a real inbound MMS media URL."""
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

import pytest

from tests._http import call
from tests.live_auth import API, STORE_A, ensure_qa_user

QA_ORG_A = "org_001"
REP_NUMBER = "+15005550077"      # Twilio test range: never a real line
CUSTOMER_NUMBER = "+15005550088"
FAKE_TWILIO_MEDIA = "https://api.twilio.com/2010-04-01/Accounts/AC" + "c" * 32 + "/Messages/MM" + "d" * 32 + "/Media/ME" + "e" * 32


# ── A. media proxy redirect allowlist ───────────────────────────────────────────────────────────────────────────────────


def test_redirect_allowlist_has_exactly_twilios_two_cdn_hosts():
    from routers.twilio_webhooks import allowed_redirect, _TWILIO_CDN_HOSTS
    assert set(_TWILIO_CDN_HOSTS) == {"media.twiliocdn.com", "mms.twiliocdn.com"}
    assert allowed_redirect("https://mms.twiliocdn.com/AC" + "a" * 32 + "/abc?Expires=1&Signature=x")
    assert allowed_redirect("https://media.twiliocdn.com/AC" + "a" * 32 + "/abc")
    for bad in ("http://mms.twiliocdn.com/x", "https://mms.twiliocdn.com.evil.net/x", "https://evil.net/mms.twiliocdn.com",
                "https://mms.twiliocdn.com:8443/x", "https://u@mms.twiliocdn.com/x", "https://xmms.twiliocdn.com/x",
                "https://api.twilio.com/2010-04-01/Accounts/x", "https://s3.amazonaws.com/mms.twiliocdn.com/x", ""):
        assert not allowed_redirect(bad), bad


def _real_inbound_mms_media_url():
    """A real inbound MMS media URL from the shared Twilio account (read-only), or None when the account has none recently."""
    sid, tok = os.environ.get("TWILIO_ACCOUNT_SID", ""), os.environ.get("TWILIO_AUTH_TOKEN", "")
    if not sid or not tok:
        return None
    from twilio.rest import Client
    c = Client(sid, tok)
    since = datetime.now(timezone.utc) - timedelta(days=14)
    for m in c.messages.list(date_sent_after=since, limit=300):
        if m.direction == "inbound" and int(m.num_media or 0) > 0:
            media = c.messages(m.sid).media.list(limit=1)
            if media:
                return "https://api.twilio.com" + media[0].uri.replace(".json", "")
    return None


def test_live_proxy_serves_a_real_inbound_mms_image(rep):
    url = _real_inbound_mms_media_url()
    if not url:
        pytest.skip("no inbound MMS in the Twilio account in the last 14 days")
    enc = urllib.parse.quote(url, safe="")
    assert call("GET", f"/api/webhooks/twilio/media-proxy?url={enc}")[0] == 401                       # no token
    tok = rep.get("/api/calls/recording-token")[1]["token"]
    req = urllib.request.Request(f"{API}/api/webhooks/twilio/media-proxy?url={enc}&t={tok}", headers={"User-Agent": "Mozilla/5.0 QA"})
    with urllib.request.urlopen(req, timeout=40) as r:
        assert r.status == 200
        assert r.headers.get("Content-Type", "").startswith("image/"), r.headers.get("Content-Type")
        assert len(r.read()) > 500



# ── B. attachment-aware Jessi ───────────────────────────────────────────────────────────────────────────────────────────


def test_attachment_prompt_helpers():
    from routers.ai_reply import attachment_notice, attachment_preview
    assert attachment_notice(0, "hi") == ""
    one = attachment_notice(1, "")
    assert "CANNOT open or see" in one and "attachment IS the message" in one and "Never say that YOU will send" in one
    two = attachment_notice(2, "here you go")
    assert "2 photos or files" in two and "attachment IS the message" not in two
    assert attachment_preview(1, "") == "[sent a photo]" and attachment_preview(3, "") == "[sent 3 photos]"
    assert attachment_preview(1, "  look ") == "look" and attachment_preview(0, "") == ""


@pytest.fixture(scope="module")
def mms_rep(mongo):
    email, pw = ensure_qa_user(mongo, "qa-mms-rep@invalid.imonsocial.test", "user", QA_ORG_A, STORE_A, "QA Mms Rep")
    mongo.users.update_one({"email": email}, {"$set": {"twilio_number": REP_NUMBER, "ai_master_paused": False}, "$unset": {"default_campaign_id": ""}})
    rep = mongo.users.find_one({"email": email})
    yield rep
    mongo.users.update_one({"_id": rep["_id"]}, {"$unset": {"twilio_number": ""}})


def _signed_inbound(form: dict):
    """POST /api/webhooks/twilio/incoming signed exactly like Twilio does (works in enforce and log modes)."""
    from twilio.request_validator import RequestValidator
    path = "/api/webhooks/twilio/incoming"
    base = os.environ.get("PUBLIC_FACING_URL") or os.environ.get("APP_URL") or "https://app.imonsocial.com"
    sig = RequestValidator(os.environ["TWILIO_AUTH_TOKEN"]).compute_signature(base.rstrip("/") + path, form)
    data = urllib.parse.urlencode(form).encode()
    req = urllib.request.Request(API + path, method="POST", data=data,
                                 headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": "TwilioProxy/1.1", "X-Twilio-Signature": sig})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


def _wait(pred, seconds=40):
    for _ in range(seconds * 2):
        v = pred()
        if v:
            return v
        time.sleep(0.5)
    return None


def test_photo_only_inbound_flags_a_human_and_jessi_never_claims_to_see_it(mongo, mms_rep):
    rep_id = str(mms_rep["_id"])
    mongo.contacts.delete_many({"user_id": rep_id, "phone": CUSTOMER_NUMBER})
    mongo.conversations.delete_many({"rep_phone": REP_NUMBER, "contact_phone": CUSTOMER_NUMBER})
    cid = mongo.contacts.insert_one({"user_id": rep_id, "phone": CUSTOMER_NUMBER, "name": "QA Mms Customer", "first_name": "QA", "last_name": "Mms",
                                     "status": "active", "created_at": datetime.utcnow()}).inserted_id
    conv_id = mongo.conversations.insert_one({"user_id": rep_id, "rep_phone": REP_NUMBER, "contact_id": str(cid), "contact_phone": CUSTOMER_NUMBER,
                                              "contact_name": "QA Mms Customer", "status": "active", "ai_mode": "auto_reply", "ai_enabled": True,
                                              "needs_assistance": False, "created_at": datetime.utcnow(), "last_message_at": datetime.utcnow()}).inserted_id
    conv = str(conv_id)
    # a little legitimate history: Jessi asked for an email address last turn
    mongo.messages.insert_one({"conversation_id": conv, "content": "What's the best email for you? I'll send the embed code over.", "sender": "ai",
                               "direction": "outbound", "status": "sent", "timestamp": datetime.utcnow() - timedelta(minutes=5)})
    try:
        form = {"MessageSid": f"MMqa{int(time.time())}", "AccountSid": os.environ.get("TWILIO_ACCOUNT_SID", ""), "From": CUSTOMER_NUMBER, "To": REP_NUMBER,
                "Body": "", "NumMedia": "1", "MediaUrl0": FAKE_TWILIO_MEDIA, "MediaContentType0": "image/jpeg"}
        assert _signed_inbound(form) in (200, 204)
        # stored for the human: proxied URL, flagged as media
        msg = _wait(lambda: mongo.messages.find_one({"conversation_id": conv, "sender": "contact", "has_media": True}))
        assert msg and msg["media_urls"][0].startswith("https://") and "/api/webhooks/twilio/media-proxy?url=" in msg["media_urls"][0]
        # Jessi's draft: knows it is a photo, does not claim to see it; the rep is flagged
        q = _wait(lambda: mongo.ai_reply_queue.find_one({"conversation_id": conv}, sort=[("created_at", -1)]), seconds=60)
        assert q, "no AI reply queued for the photo-only inbound"
        mongo.ai_reply_queue.update_many({"conversation_id": conv, "status": "pending"}, {"$set": {"status": "cancelled", "cancel_reason": "qa_test"}})
        assert q["attachments"] == 1 and q["incoming_message_preview"] == "[sent a photo]"
        print("\nJessi draft (photo only, after asking for an email):", q["body"])
        body = (q["body"] or "").lower()
        assert body, "empty draft"
        for claim in ("i see ", "i can see", "looks like a", "in the photo i", "the photo shows", "nice car", "i've sent", "just sent you", "sent it over", "i'll send", "i’ll send", "i will send"):
            assert claim not in body, (claim, q["body"])
        c = mongo.conversations.find_one({"_id": conv_id})
        assert c["needs_assistance"] is True and c.get("attachment_prompted_at")
        n = mongo.notifications.find_one({"conversation_id": conv, "type": "you_are_needed", "title": {"$regex": "sent a photo"}})
        assert n, "rep was not told a photo arrived"
        # second photo-only message within 30 min: no second clarification, human still flagged
        before = mongo.ai_reply_queue.count_documents({"conversation_id": conv})
        notes_before = mongo.notifications.count_documents({"conversation_id": conv, "title": {"$regex": "sent a photo"}})
        form2 = {**form, "MessageSid": f"MMqa{int(time.time())}b", "NumMedia": "2", "MediaUrl1": FAKE_TWILIO_MEDIA.replace("e" * 32, "f" * 32), "MediaContentType1": "image/jpeg"}
        assert _signed_inbound(form2) in (200, 204)
        time.sleep(8)
        assert mongo.ai_reply_queue.count_documents({"conversation_id": conv}) == before, "Jessi nagged a second time"
        assert mongo.notifications.count_documents({"conversation_id": conv, "title": {"$regex": "sent a photo"}}) == notes_before
        assert mongo.conversations.find_one({"_id": conv_id})["needs_assistance"] is True
    finally:
        mongo.ai_reply_queue.update_many({"conversation_id": conv, "status": "pending"}, {"$set": {"status": "cancelled", "cancel_reason": "qa_test"}})
        mongo.messages.delete_many({"conversation_id": conv})
        mongo.notifications.delete_many({"conversation_id": conv})
        mongo.ai_reply_queue.delete_many({"conversation_id": conv})
        mongo.conversations.delete_one({"_id": conv_id})
        mongo.contacts.delete_one({"_id": cid})
        mongo.vision_usage.delete_many({"contact_id": str(cid)})
        mongo.contact_files.delete_many({"contact_id": str(cid)}) if "contact_files" in mongo.list_collection_names() else None


def test_text_plus_photo_still_gets_a_normal_reply_with_the_notice(mongo, mms_rep):
    rep_id = str(mms_rep["_id"])
    cust = "+15005550089"
    mongo.contacts.delete_many({"user_id": rep_id, "phone": cust})
    mongo.conversations.delete_many({"rep_phone": REP_NUMBER, "contact_phone": cust})
    cid = mongo.contacts.insert_one({"user_id": rep_id, "phone": cust, "name": "QA Mms Two", "first_name": "QA", "last_name": "Two", "status": "active", "created_at": datetime.utcnow()}).inserted_id
    conv_id = mongo.conversations.insert_one({"user_id": rep_id, "rep_phone": REP_NUMBER, "contact_id": str(cid), "contact_phone": cust, "contact_name": "QA Mms Two",
                                              "status": "active", "ai_mode": "auto_reply", "ai_enabled": True, "needs_assistance": False,
                                              "created_at": datetime.utcnow(), "last_message_at": datetime.utcnow()}).inserted_id
    conv = str(conv_id)
    try:
        form = {"MessageSid": f"MMqa{int(time.time())}c", "AccountSid": os.environ.get("TWILIO_ACCOUNT_SID", ""), "From": cust, "To": REP_NUMBER,
                "Body": "Here is my truck, what do you think it's worth?", "NumMedia": "1", "MediaUrl0": FAKE_TWILIO_MEDIA, "MediaContentType0": "image/jpeg"}
        assert _signed_inbound(form) in (200, 204)
        q = _wait(lambda: mongo.ai_reply_queue.find_one({"conversation_id": conv}, sort=[("created_at", -1)]), seconds=60)
        assert q, "no AI reply queued"
        mongo.ai_reply_queue.update_many({"conversation_id": conv, "status": "pending"}, {"$set": {"status": "cancelled", "cancel_reason": "qa_test"}})
        assert q["attachments"] == 1 and q["incoming_message_preview"].startswith("Here is my truck")
        print("\nJessi draft (truck photo + text):", q["body"])
        body = (q["body"] or "").lower()
        for claim in ("i see ", "i can see", "looks like a", "the photo shows", "nice truck", "great looking", "clean truck", "good condition"):
            assert claim not in body, (claim, q["body"])
        assert mongo.conversations.find_one({"_id": conv_id})["needs_assistance"] is True
    finally:
        mongo.ai_reply_queue.update_many({"conversation_id": conv, "status": "pending"}, {"$set": {"status": "cancelled", "cancel_reason": "qa_test"}})
        mongo.messages.delete_many({"conversation_id": conv})
        mongo.notifications.delete_many({"conversation_id": conv})
        mongo.ai_reply_queue.delete_many({"conversation_id": conv})
        mongo.conversations.delete_one({"_id": conv_id})
        mongo.contacts.delete_one({"_id": cid})
        mongo.vision_usage.delete_many({"contact_id": str(cid)})


# ── D. the thread reader and Ask Jessi (manual suggestion) are told the same thing ──────────────────────────────────────


def test_thread_reader_marks_photos_the_model_cannot_see():
    from services import thread_context as tc
    ts = datetime(2026, 10, 14, 12, 0)
    photo_only = {"sender": "contact", "content": "", "media_urls": ["https://x/1"], "timestamp": ts}
    with_text = {"sender": "contact", "content": "here is my truck", "media_urls": ["https://x/1"], "timestamp": ts}
    plain = {"sender": "contact", "content": "hi there", "timestamp": ts}
    assert tc._line(photo_only, "Sam", ts) == "Sam: [sent a photo you cannot see]"
    assert tc._line(with_text, "Sam", ts) == "Sam: [sent a photo you cannot see] here is my truck"
    assert tc._line(plain, "Sam", ts) == "Sam: hi there"
    assert tc._line({"sender": "user", "content": "", "media_urls": ["https://x/2"], "timestamp": ts}, "Sam", ts) == "Me: [sent a photo]"


def test_ask_jessi_suggestion_on_a_photo_only_text_never_claims_to_see_it(mongo, mms_rep):
    from tests.live_auth import Session
    from tests import qa_creds
    rep_id = str(mms_rep["_id"])
    cust = "+15005550091"
    cid = mongo.contacts.insert_one({"user_id": rep_id, "phone": cust, "name": "QA Mms Suggest", "first_name": "QA", "last_name": "Suggest", "status": "active", "created_at": datetime.utcnow()}).inserted_id
    conv_id = mongo.conversations.insert_one({"user_id": rep_id, "rep_phone": REP_NUMBER, "contact_id": str(cid), "contact_phone": cust, "contact_name": "QA Mms Suggest",
                                              "status": "active", "ai_mode": "assisted", "ai_enabled": True, "created_at": datetime.utcnow(), "last_message_at": datetime.utcnow()}).inserted_id
    conv = str(conv_id)
    t0 = datetime.utcnow() - timedelta(minutes=5)
    mongo.messages.insert_many([
        {"conversation_id": conv, "contact_id": str(cid), "user_id": rep_id, "sender": "user", "direction": "outbound", "content": "Hey QA, happy to help with the website embed. What's the best email to reach you at?", "timestamp": t0, "status": "sent"},
        {"conversation_id": conv, "contact_id": str(cid), "user_id": rep_id, "sender": "contact", "direction": "inbound", "content": "", "media_urls": [FAKE_TWILIO_MEDIA], "media_types": ["image/jpeg"], "num_media": 1, "has_media": True, "timestamp": t0 + timedelta(minutes=1)},
    ])
    try:
        s = Session(mms_rep["email"], qa_creds.password_for(mms_rep["email"]))
        code, data = s.post(f"/api/messages/ai-suggest/{conv}", {})
        assert code == 200 and data.get("suggestion"), (code, data)
        print("\nAsk Jessi draft (photo only):", data["suggestion"])
        body = data["suggestion"].lower()
        for claim in ("i see ", "i can see", "looks like", "the photo shows", "in the photo", "in the picture", "got it, i'll", "i'll send"):
            assert claim not in body, (claim, data["suggestion"])
        assert any(w in body for w in ("email", "type", "can't open", "cannot open", "can't see", "cannot see", "can't view", "what did you send", "attachment", "photo", "image")), data["suggestion"]
    finally:
        mongo.messages.delete_many({"conversation_id": conv})
        mongo.conversations.delete_one({"_id": conv_id})
        mongo.contacts.delete_one({"_id": cid})
        mongo.vision_usage.delete_many({"contact_id": str(cid)})
