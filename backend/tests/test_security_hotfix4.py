"""Security hotfix 4: tenant isolation on contact ids, role hierarchy on account edits, provider webhook authentication,
public card save without enrollment, smoke-script preflight. Live preview API; each finding is probed as anonymous, as a rep
from another dealership, as a manager from another organization and as the authorized caller."""
import os
import sys
import time
import urllib.parse
import urllib.request

import pytest
import requests
from bson import ObjectId

from tests._http import API, call
from tests.live_auth import ORG_B, STORE_A, STORE_B, Session, anon, ensure_qa_user, unsigned_twilio_codes

QA_ORG_A = "org_001"
ZERO = "0" * 24


# ── accounts ──────────────────────────────────────────────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def victim(mongo):
    email, pw = ensure_qa_user(mongo, "qa-hotfix3-victim@invalid.imonsocial.test", "user", QA_ORG_A, STORE_A, "QA Hotfix Victim")
    return Session(email, pw)


@pytest.fixture(scope="module")
def other_rep(mongo):
    email, pw = ensure_qa_user(mongo, "qa-hotfix3-rep@invalid.imonsocial.test", "user", ORG_B, STORE_B, "QA Hotfix Other Rep")
    return Session(email, pw)


@pytest.fixture(scope="module")
def org_a_admin(mongo):
    """An org_admin who sits in STORE_A: inside the store manager's scope, but above the store manager's rank."""
    email, pw = ensure_qa_user(mongo, "qa-hotfix4-orgadmin@invalid.imonsocial.test", "org_admin", QA_ORG_A, STORE_A, "QA Hotfix4 Org Admin")
    s = Session(email, pw)
    mongo.users.update_one({"_id": ObjectId(s.user_id)}, {"$set": {"phone": "+15550004000", "email_recovery": "orig"}})
    return s


@pytest.fixture(scope="module")
def own_manager(store_manager):
    return store_manager


@pytest.fixture(scope="module")
def foreign_manager(org_admin):
    return org_admin


def _contact(mongo, owner_id, first, phone=None):
    doc = {"user_id": owner_id, "first_name": first, "last_name": "Hotfix4", "name": f"{first} Hotfix4", "status": "active", "source": "qa-hotfix4"}
    if phone:
        doc["phone"] = phone
    return str(mongo.contacts.insert_one(doc).inserted_id)


@pytest.fixture(scope="module")
def contacts(mongo, victim, other_rep):
    """victim's own contact (no phone: nothing can be sent) and a contact that belongs to the other dealership."""
    mine = _contact(mongo, victim.user_id, "Mine")
    theirs = _contact(mongo, other_rep.user_id, "Theirs")
    yield {"mine": mine, "theirs": theirs}
    ids = [mine, theirs]
    mongo.conversations.delete_many({"contact_id": {"$in": ids}})
    mongo.messages.delete_many({"conversation_id": {"$in": [str(c["_id"]) for c in mongo.conversations.find({"contact_id": {"$in": ids}}, {"_id": 1})]}})
    mongo.voice_upload_chunks.delete_many({"user_id": {"$in": [victim.user_id, other_rep.user_id]}})
    mongo.voice_notes.delete_many({"contact_id": {"$in": ids}})
    mongo.card_events.delete_many({"contact_id": {"$in": ids}})
    mongo.campaign_enrollments.delete_many({"contact_id": {"$in": ids}})
    mongo.contacts.delete_many({"_id": {"$in": [ObjectId(i) for i in ids]}})


# ── 1. cross-dealership contact ids in messaging ──────────────────────────────────────────────────────────────────────────


def test_cross_dealership_contact_cannot_open_a_conversation(victim, other_rep, foreign_manager, own_manager, super_admin, contacts, mongo):
    path = f"/api/messages/conversations/{victim.user_id}"
    assert anon("POST", path, {"contact_id": contacts["theirs"]})[0] == 401
    assert other_rep.post(path, {"contact_id": contacts["theirs"]})[0] == 403          # not even as themselves on victim's route
    assert foreign_manager.post(path, {"contact_id": contacts["theirs"]})[0] == 403
    st, body = victim.post(path, {"contact_id": contacts["theirs"]})
    assert st == 404, (st, body)
    assert mongo.conversations.count_documents({"contact_id": contacts["theirs"]}) == 0, "no conversation may exist on the foreign contact"
    # the other rep's own route with their own contact keeps working
    st, body = other_rep.post(f"/api/messages/conversations/{other_rep.user_id}", {"contact_id": contacts["theirs"]})
    assert st == 200 and body.get("user_id") == other_rep.user_id, (st, body)
    # authorized: the rep, their own manager, super admin
    for who in (victim, own_manager, super_admin):
        st, body = who.post(path, {"contact_id": contacts["mine"]})
        assert st == 200 and body.get("contact_id") == contacts["mine"], (who.email, st, body)
    assert mongo.conversations.count_documents({"contact_id": contacts["mine"], "user_id": victim.user_id}) == 1


def test_cross_dealership_contact_cannot_be_texted(victim, other_rep, contacts, mongo):
    path = f"/api/messages/send/{victim.user_id}"
    before = mongo.messages.count_documents({"user_id": victim.user_id})
    st, body = victim.post(path, {"contact_id": contacts["theirs"], "content": "hello from the wrong dealership"})
    assert st == 404, (st, body)
    assert mongo.conversations.count_documents({"contact_id": contacts["theirs"], "user_id": victim.user_id}) == 0
    assert mongo.messages.count_documents({"user_id": victim.user_id}) == before
    # twilio-send with a foreign contact id is refused before anything is sent
    st, body = victim.post("/api/messages/twilio-send", {"user_id": victim.user_id, "to": "+15005550006", "body": "x", "contact_id": contacts["theirs"]})
    assert st == 404, (st, body)
    # MMS fallback that treats the path id as a contact id
    r = requests.post(f"{API}/api/messages/send-mms/{victim.user_id}/{contacts['theirs']}", headers={k: v for k, v in victim.headers.items()},
                      data={"content": "x"}, files={"media": ("x.jpg", b"\xff\xd8\xff\xd9", "image/jpeg")}, timeout=40)
    assert r.status_code == 404, (r.status_code, r.text[:200])
    assert mongo.conversations.count_documents({"contact_id": contacts["theirs"], "user_id": victim.user_id}) == 0
    # authorized: own contact (no phone -> the message is logged as failed, nothing leaves)
    st, body = victim.post(path, {"contact_id": contacts["mine"], "content": "hello mine"})
    assert st == 200, (st, body)
    assert mongo.messages.count_documents({"user_id": victim.user_id}) == before + 1


def test_voice_note_upload_needs_the_reps_own_contact(victim, other_rep, contacts, mongo):
    chunk = {"upload_id": "qa-hotfix4", "index": 0, "total": 2, "data": "AAAA", "content_type": "audio/mp4", "duration": 12, "kind": "memo"}
    assert anon("POST", f"/api/voice-notes/{victim.user_id}/{contacts['theirs']}/chunk", chunk)[0] == 401
    assert other_rep.post(f"/api/voice-notes/{victim.user_id}/{contacts['theirs']}/chunk", chunk)[0] == 403
    st, body = victim.post(f"/api/voice-notes/{victim.user_id}/{contacts['theirs']}/chunk", chunk)
    assert st == 404, (st, body)
    assert mongo.voice_upload_chunks.count_documents({"user_id": victim.user_id, "upload_id": "qa-hotfix4"}) == 0
    assert victim.post(f"/api/voice-notes/{victim.user_id}/{contacts['theirs']}/capture-reminder", {})[0] == 404
    st, body = victim.post(f"/api/voice-notes/{victim.user_id}/{contacts['mine']}/chunk", chunk)
    assert st == 200 and body.get("received") == 1, (st, body)
    mongo.voice_upload_chunks.delete_many({"user_id": victim.user_id, "upload_id": "qa-hotfix4"})


# ── 2. role hierarchy ─────────────────────────────────────────────────────────────────────────────────────────────────────


def test_store_manager_cannot_modify_an_org_admin(own_manager, org_a_admin, super_admin, victim, mongo):
    target = org_a_admin.user_id
    # the manager really is scoped to this account: reads work
    st, body = own_manager.get(f"/api/auth/user/{target}")
    assert st == 200, (st, body)
    for method, path, payload in [
        ("PATCH", f"/api/auth/users/{target}", {"phone": "+15550009999"}),
        ("PATCH", f"/api/auth/users/{target}", {"email": "stolen@invalid.imonsocial.test"}),
        ("PUT", f"/api/auth/user/{target}", {"phone": "+15550009999"}),
        ("POST", f"/api/auth/persona/{target}", {"bio": "hijacked"}),
        ("PUT", f"/api/auth/users/{target}/review-links", {"review_links": {"google": "https://evil"}}),
        ("PUT", f"/api/admin/users/{target}", {"phone": "+15550009999"}),
        ("PUT", f"/api/admin/users/{target}/status", {"status": "inactive"}),
    ]:
        st, body = getattr(own_manager, method.lower())(path, payload)
        assert st == 403, (method, path, st, body)
    doc = mongo.users.find_one({"_id": ObjectId(target)}, {"phone": 1, "email": 1, "persona": 1, "status": 1, "is_active": 1})
    assert doc["phone"] == "+15550004000" and doc["email"] == "qa-hotfix4-orgadmin@invalid.imonsocial.test" and doc.get("status") == "active", doc
    # higher rank editing lower rank inside the organization still works
    st, body = org_a_admin.patch(f"/api/auth/users/{victim.user_id}", {"title": "QA title"})
    assert st == 200, (st, body)
    st, body = super_admin.patch(f"/api/auth/users/{target}", {"phone": "+15550004000"})
    assert st == 200, (st, body)


def test_roles_can_only_be_granted_below_your_own(own_manager, org_a_admin, victim, mongo):
    for role in ("org_admin", "store_manager", "super_admin"):
        st, body = own_manager.put(f"/api/admin/users/{victim.user_id}", {"role": role})
        assert st == 403, (role, st, body)
    st, body = own_manager.put(f"/api/admin/users/{own_manager.user_id}", {"role": "org_admin"})
    assert st == 403, (st, body)
    assert mongo.users.find_one({"_id": ObjectId(victim.user_id)}, {"role": 1})["role"] == "user"
    assert mongo.users.find_one({"_id": ObjectId(own_manager.user_id)}, {"role": 1})["role"] == "store_manager"
    for role in ("org_admin", "super_admin"):
        assert org_a_admin.put(f"/api/admin/users/{victim.user_id}", {"role": role})[0] == 403, role
    st, body = org_a_admin.put(f"/api/admin/users/{victim.user_id}", {"role": "store_manager"})
    assert st == 200, (st, body)
    mongo.users.update_one({"_id": ObjectId(victim.user_id)}, {"$set": {"role": "user"}})


# ── 3. provider webhooks ──────────────────────────────────────────────────────────────────────────────────────────────────

TWILIO_CALLBACKS = [
    "/api/webhooks/twilio/incoming", "/api/webhooks/twilio/sms", "/api/webhooks/twilio/status", "/api/webhooks/twilio/voice",
    "/api/webhooks/twilio/voice-fallback", "/api/webhooks/twilio/recording-complete", "/api/webhooks/twilio/call-status",
    "/api/webhooks/twilio/voicemail-recording", "/api/webhooks/twilio/voicemail-transcription", "/api/webhooks/twilio/call-whisper",
    "/api/webhooks/twilio/call-whisper/accept", "/api/webhooks/twilio/call-bridge", "/api/webhooks/twilio/call-bridge-connect",
    "/api/webhooks/twilio/call-bridge-result", "/api/webhooks/twilio/trusthub-status", "/api/messages/webhook/inbound",
    "/api/webhooks/dialer/rep/status", "/api/webhooks/dialer/lead/status",
]


def _form_post(path, form, headers=None):
    data = urllib.parse.urlencode(form).encode()
    req = urllib.request.Request(API + path, method="POST", data=data, headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": "TwilioProxy/1.1", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.status, r.read().decode()[:200]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:200]


def test_twilio_callbacks_reject_unsigned_and_forged_requests():
    form = {"MessageSid": "SMqahotfix4", "MessageStatus": "delivered", "AccountSid": os.environ.get("TWILIO_ACCOUNT_SID", ""), "From": "+15005550006", "To": "+15005550006", "Body": "forged"}
    for path in TWILIO_CALLBACKS:
        st, body = _form_post(path, form)
        assert st in unsigned_twilio_codes(), (path, st, body)
        st, body = _form_post(path, form, {"X-Twilio-Signature": "bm90LXRoZS1yZWFsLXNpZ25hdHVyZQ=="})
        assert st in unsigned_twilio_codes(), (path, st, body)


def test_a_properly_signed_twilio_callback_is_processed():
    """Signed the way Twilio does it for the production URL shape (APP_URL + path), which is the first candidate the server tries."""
    from twilio.request_validator import RequestValidator
    token, sid = os.environ.get("TWILIO_AUTH_TOKEN", ""), os.environ.get("TWILIO_ACCOUNT_SID", "")
    assert token and sid, "preview backend .env must be loaded"
    base = (os.environ.get("PUBLIC_FACING_URL") or os.environ.get("APP_URL") or "").rstrip("/")
    form = {"MessageSid": "SMqahotfix4signed", "MessageStatus": "delivered", "AccountSid": sid, "From": "+15005550006", "To": "+15005550006"}
    path = "/api/webhooks/twilio/status"
    good = RequestValidator(token).compute_signature(base + path, form)
    st, body = _form_post(path, form, {"X-Twilio-Signature": good})
    assert st == 200, (st, body)
    # the host-based shape (X-Forwarded-Host / Host) is accepted too
    host = urllib.parse.urlsplit(API).netloc
    good2 = RequestValidator(token).compute_signature(f"https://{host}{path}", form)
    st, body = _form_post(path, form, {"X-Twilio-Signature": good2})
    assert st == 200, (st, body)
    # same signature on a different body is a forgery
    st, body = _form_post(path, {**form, "MessageStatus": "failed"}, {"X-Twilio-Signature": good})
    assert st in unsigned_twilio_codes(), (st, body)


def test_app_call_routes_under_the_twilio_prefix_need_a_session(victim, other_rep, foreign_manager):
    assert anon("POST", "/api/webhooks/twilio/call", {"rep_user_id": victim.user_id, "customer_phone": "+15005550006"})[0] == 401
    assert anon("POST", "/api/webhooks/twilio/call-cancel", {"call_sid": "CAqa"})[0] == 401
    assert anon("GET", "/api/webhooks/twilio/call-progress/CAqa")[0] == 401
    for who in (other_rep, foreign_manager):
        st, body = who.post("/api/webhooks/twilio/call", {"rep_user_id": victim.user_id, "customer_phone": "+15005550006"})
        assert st == 403, (who.email, st, body)
    assert victim.post("/api/webhooks/twilio/call-cancel", {"call_sid": "CAqa-does-not-exist"})[0] == 404
    assert victim.get("/api/webhooks/twilio/call-progress/CAqa-does-not-exist")[0] == 404
    # the rep themselves gets past the gate (an empty phone fails later, never 401/403)
    st, body = victim.post("/api/webhooks/twilio/call", {"rep_user_id": victim.user_id, "customer_phone": ""})
    assert st not in (401, 403), (st, body)


def test_media_proxy_only_fetches_twilio_hosts(victim):
    """Hotfix 4B tightened this further (media token + exact resource allowlist); see test_security_hotfix4b.py."""
    tok = victim.get("/api/calls/recording-token")[1]["token"]
    for url in ("https://example.com/x.jpg", "http://api.twilio.com/x", "https://api.twilio.com.evil.net/x", "https://169.254.169.254/latest/meta-data"):
        assert call("GET", "/api/webhooks/twilio/media-proxy?url=" + urllib.parse.quote(url, safe=""))[0] == 401, url   # no token: nothing is even parsed
        st, body = call("GET", "/api/webhooks/twilio/media-proxy?url=" + urllib.parse.quote(url, safe="") + "&t=" + tok)
        assert st == 400, (url, st, body)
    good = "https://api.twilio.com/2010-04-01/Accounts/AC" + "a" * 32 + "/Recordings/RE" + "b" * 32 + ".mp3"
    st, _ = call("GET", "/api/webhooks/twilio/media-proxy?url=" + urllib.parse.quote(good, safe="") + "&t=" + tok)
    assert st not in (400, 401)


def test_resend_inbound_fails_closed(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from routers import resend_webhooks as rw
    st, body = anon("POST", "/api/webhooks/resend/inbound", {"type": "email.received", "data": {"email_id": "x"}})
    assert st in (401, 503), (st, body)  # 401 = secret configured, unsigned; 503 = secret missing (preview): never processed
    monkeypatch.setenv("RESEND_WEBHOOK_SECRET", "")
    assert rw._verify_svix({"svix-id": "m", "svix-timestamp": str(int(time.time())), "svix-signature": "v1,abc"}, b"{}") is False
    app = FastAPI()
    app.include_router(rw.router)
    client = TestClient(app)
    r = client.post("/webhooks/resend/inbound", json={"type": "email.received", "data": {"email_id": "x"}})
    assert r.status_code == 503, (r.status_code, r.text)


# ── 4. public card save ───────────────────────────────────────────────────────────────────────────────────────────────────


def test_card_save_never_enrolls_anyone(victim, contacts, mongo):
    campaign_id = str(mongo.campaigns.insert_one({"user_id": victim.user_id, "name": "QA Hotfix4 Campaign", "status": "active", "steps": []}).inserted_id)
    try:
        st, body = anon("POST", f"/api/card/save/{victim.user_id}", {"contact_id": contacts["theirs"], "campaign_id": campaign_id})
        assert st == 404, (st, body)
        st, body = anon("POST", f"/api/card/save/{ZERO}", {"contact_id": contacts["mine"], "campaign_id": campaign_id})
        assert st == 404, (st, body)
        st, body = anon("POST", f"/api/card/save/{victim.user_id}", {"contact_id": contacts["mine"], "campaign_id": campaign_id})
        assert st == 200 and body.get("enrolled") is False, (st, body)
        assert mongo.campaign_enrollments.count_documents({"contact_id": {"$in": [contacts["mine"], contacts["theirs"]]}}) == 0
        assert mongo.card_events.count_documents({"type": "card_save", "contact_id": contacts["mine"]}) == 1
    finally:
        mongo.campaigns.delete_one({"_id": ObjectId(campaign_id)})


# ── 5. production smoke script preflight ─────────────────────────────────────────────────────────────────────────────────


def test_smoke_script_stops_before_any_probe_when_the_build_differs(monkeypatch):
    sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
    import prod_smoke_hotfix3 as smoke
    assert smoke.preflight("v2", fetch=lambda m, p: (200, '{"build": "v2"}')) == (True, "v2")
    assert smoke.preflight("v2", fetch=lambda m, p: (200, '{"build": "v1"}')) == (False, "v1")
    assert smoke.preflight("v2", fetch=lambda m, p: (200, '{}')) == (False, "")
    assert smoke.preflight("v2", fetch=lambda m, p: (503, 'down'))[0] is False
    assert smoke.preflight("", fetch=lambda m, p: (200, '{"build": ""}'))[0] is False
    sent = []
    monkeypatch.setattr(smoke, "call", lambda m, p, b=None, h=None: sent.append((m, p)) or (200, '{"build": "older"}'))
    with pytest.raises(SystemExit) as ex:
        smoke.main()
    assert ex.value.code == 2
    assert sent == [("GET", "/api/health")], sent
    for method, path, body, headers, want in smoke.CHECKS:
        assert body in (None, {}) or path.startswith(f"/api/card/save/{ZERO}"), (method, path, body)
