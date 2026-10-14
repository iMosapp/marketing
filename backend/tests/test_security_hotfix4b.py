"""Security hotfix 4B: self-promotion / cross-org movement on hierarchy routes, Twilio media-proxy allowlist + media tokens,
WebSocket call-host under signature enforcement, same-rank recovery edits, Stripe/ADF/shared-inbox/lead-call webhook auth,
calendar OAuth state, inventory tenant scoping, public AI throttling, recording access by call sid.
Live preview API; every finding probed as anonymous, cross-user, cross-organization and authorized."""
import asyncio
import os
import secrets
import time
import urllib.parse
import urllib.request

import pytest
from bson import ObjectId

from tests._http import API, UA, call
from tests.live_auth import ORG_B, STORE_A, STORE_B, Session, anon, ensure_qa_user

QA_ORG_A = "org_001"
ZERO = "0" * 24


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
    email, pw = ensure_qa_user(mongo, "qa-hotfix4-orgadmin@invalid.imonsocial.test", "org_admin", QA_ORG_A, STORE_A, "QA Hotfix4 Org Admin")
    return Session(email, pw)


@pytest.fixture(scope="module")
def manager2(mongo):
    """A second store manager of STORE_A: same rank as `store_manager`."""
    email, pw = ensure_qa_user(mongo, "qa-hotfix4b-manager2@invalid.imonsocial.test", "store_manager", QA_ORG_A, STORE_A, "QA Hotfix4b Manager Two")
    s = Session(email, pw)
    mongo.users.update_one({"_id": ObjectId(s.user_id)}, {"$set": {"phone": "+15550004200"}})
    return s


def _user(mongo, sid):
    return mongo.users.find_one({"_id": ObjectId(sid)}, {"role": 1, "organization_id": 1, "store_id": 1, "store_ids": 1, "phone": 1, "email": 1, "name": 1})


# ── CRITICAL 1: hierarchy routes ─────────────────────────────────────────────────────────────────────────────────────────


def test_a_rep_cannot_promote_or_move_themselves(victim, mongo):
    before = _user(mongo, victim.user_id)
    me = victim.user_id
    attempts = [
        ("PUT", f"/api/admin/hierarchy/users/{me}/assign-org", {"organization_id": ORG_B, "role": "super_admin"}),
        ("PUT", f"/api/admin/hierarchy/users/{me}/assign-org", {"organization_id": QA_ORG_A, "role": "org_admin"}),
        ("PUT", f"/api/admin/hierarchy/users/{me}/assign-store", {"store_id": STORE_B}),
        ("PUT", f"/api/admin/hierarchy/users/{me}/change-organization", {"organization_id": ORG_B}),
        ("PUT", f"/api/admin/hierarchy/users/{me}/role", {"role": "super_admin"}),
        ("PUT", f"/api/admin/hierarchy/users/{me}/role", {"role": "store_manager"}),
        ("PUT", f"/api/admin/hierarchy/users/{me}/remove-store", {"store_id": STORE_A}),
        ("PUT", f"/api/admin/users/{me}", {"role": "super_admin"}),
        ("PUT", f"/api/admin/users/{me}", {"organization_id": ORG_B}),
    ]
    for method, path, body in attempts:
        st, resp = victim.put(path, body)
        assert st == 403, (path, body, st, resp)
        assert anon(method, path, body)[0] == 401, path
    assert _user(mongo, me) == before, "nothing about the rep may have changed"


def test_managers_stay_inside_their_rank_and_scope(store_manager, org_admin, org_a_admin, victim, super_admin, mongo):
    v = victim.user_id
    before = _user(mongo, v)
    # store manager: can't grant managers/admins, can't place people into stores or orgs they don't manage, can't touch an org admin
    for path, body in [
        (f"/api/admin/hierarchy/users/{v}/assign-org", {"organization_id": QA_ORG_A, "role": "store_manager"}),
        (f"/api/admin/hierarchy/users/{v}/assign-org", {"organization_id": ORG_B, "role": "user"}),
        (f"/api/admin/hierarchy/users/{v}/assign-store", {"store_id": STORE_B}),
        (f"/api/admin/hierarchy/users/{v}/change-organization", {"organization_id": ORG_B}),
        (f"/api/admin/hierarchy/users/{v}/role", {"role": "store_manager"}),
        (f"/api/admin/hierarchy/users/{v}/role", {"role": "org_admin"}),
        (f"/api/admin/hierarchy/users/{org_a_admin.user_id}/assign-store", {"store_id": STORE_A}),
        (f"/api/admin/hierarchy/users/{org_a_admin.user_id}/role", {"role": "user"}),
        (f"/api/admin/hierarchy/users/{store_manager.user_id}/role", {"role": "org_admin"}),
    ]:
        st, resp = store_manager.put(path, body)
        assert st == 403, (path, body, st, resp)
    # org admin of ANOTHER organization: no reach into store A at all
    for path, body in [
        (f"/api/admin/hierarchy/users/{v}/assign-org", {"organization_id": ORG_B, "role": "user"}),
        (f"/api/admin/hierarchy/users/{v}/change-organization", {"organization_id": ORG_B}),
        (f"/api/admin/hierarchy/users/{v}/assign-store", {"store_id": STORE_B}),
        (f"/api/admin/hierarchy/users/{v}/role", {"role": "store_manager"}),
    ]:
        st, resp = org_admin.put(path, body)
        assert st == 403, (path, body, st, resp)
    # the org's own admin: can't move the rep into an org they don't administer, can't mint org admins, can't move themselves
    assert org_a_admin.put(f"/api/admin/hierarchy/users/{v}/change-organization", {"organization_id": ORG_B})[0] == 403
    assert org_a_admin.put(f"/api/admin/hierarchy/users/{v}/assign-org", {"organization_id": QA_ORG_A, "role": "org_admin"})[0] == 403
    assert org_a_admin.put(f"/api/admin/hierarchy/users/{org_a_admin.user_id}/role", {"role": "super_admin"})[0] == 403
    assert _user(mongo, v) == before
    # authorized: own org admin grants store manager inside the org, store manager (re)assigns the rep to their own store
    st, resp = org_a_admin.put(f"/api/admin/hierarchy/users/{v}/role", {"role": "store_manager"})
    assert st == 200, (st, resp)
    assert _user(mongo, v)["role"] == "store_manager"
    st, resp = super_admin.put(f"/api/admin/hierarchy/users/{v}/role", {"role": "user"})
    assert st == 200, (st, resp)
    st, resp = store_manager.put(f"/api/admin/hierarchy/users/{v}/assign-store", {"store_id": STORE_A})
    assert st == 200 and STORE_A in resp.get("store_ids", []), (st, resp)
    mongo.users.update_one({"_id": ObjectId(v)}, {"$set": {k: before[k] for k in ("role", "store_id", "store_ids", "organization_id") if k in before}})


def test_partner_portal_routes_need_authorization(victim, super_admin):
    assert anon("POST", "/api/partners/portal/assign-org", {"agreement_id": ZERO, "org_id": ORG_B})[0] == 401
    assert victim.post("/api/partners/portal/assign-org", {"agreement_id": ZERO, "org_id": ORG_B})[0] == 403
    assert victim.get(f"/api/partners/portal/orgs/{ORG_B}/users")[0] == 403
    assert victim.get(f"/api/partners/portal/orgs/{ORG_B}/stores")[0] == 403
    st, body = super_admin.get(f"/api/partners/portal/orgs/{ORG_B}/users")
    assert st == 200 and all("password" not in u for u in body), (st, str(body)[:200])


# ── CRITICAL 2: media proxy ──────────────────────────────────────────────────────────────────────────────────────────────

GOOD_MEDIA = "https://api.twilio.com/2010-04-01/Accounts/AC" + "a" * 32 + "/Messages/MM" + "b" * 32 + "/Media/ME" + "c" * 32
GOOD_REC = "https://api.twilio.com/2010-04-01/Accounts/AC" + "a" * 32 + "/Recordings/RE" + "d" * 32 + ".mp3"
BAD_URLS = [
    "https://example.com/x.jpg", "http://api.twilio.com/2010-04-01/Accounts/ACaa/Recordings/REdd.mp3", "https://api.twilio.com.evil.net/x",
    "https://evil.net/api.twilio.com/2010-04-01/Accounts/x", "https://api.twilio.com@evil.net/2010-04-01/Accounts/x", "https://user:pw@api.twilio.com/2010-04-01/Accounts/x",
    "https://api.twilio.com:8443/2010-04-01/Accounts/AC" + "a" * 32 + "/Recordings/RE" + "d" * 32, "https://169.254.169.254/latest/meta-data",
    "https://api.twilio.com/2010-04-01/Accounts.json", "https://api.twilio.com/2010-04-01/Accounts/AC" + "a" * 32 + "/Keys.json",
    "https://api.twilio.com/2010-04-01/Accounts/AC" + "a" * 32 + "/Messages.json", "https://api.twilio.com/2010-04-01/Accounts/AC" + "a" * 32 + "/Calls/CA" + "e" * 32 + ".json",
    GOOD_MEDIA + "/../../Keys.json", GOOD_MEDIA.replace("/Media/", "/%4dedia/"), GOOD_MEDIA + "?x=1", GOOD_MEDIA + "#frag", GOOD_MEDIA + "\\\\evil",
    "https://media.twiliocdn.com/AC" + "a" * 32 + "/x", "ftp://api.twilio.com/2010-04-01/Accounts/x", "", "https://api.twilio.com//2010-04-01/Accounts/x",
    "https://api.twilio.com/2010-04-01/Accounts/AC" + "a" * 32 + "/Recordings/RE" + "d" * 32 + ".txt", "https://API.TWILIO.COM/2010-04-01/Accounts/AC" + "a" * 32 + "/Recordings/RE" + "z" * 32,
]


def test_media_url_allowlist_unit():
    from routers.twilio_webhooks import allowed_media_url, allowed_redirect
    assert allowed_media_url(GOOD_MEDIA) == GOOD_MEDIA
    assert allowed_media_url(GOOD_REC) == GOOD_REC
    assert allowed_media_url(GOOD_REC[:-4]) == GOOD_REC[:-4]
    assert allowed_media_url(GOOD_MEDIA.replace("https://api.twilio.com", "HTTPS://API.twilio.com")) == GOOD_MEDIA
    for bad in BAD_URLS:
        assert allowed_media_url(bad) is None, bad
    assert allowed_redirect("https://media.twiliocdn.com/AC" + "a" * 32 + "/x?Signature=abc")
    for bad in ("http://media.twiliocdn.com/x", "https://media.twiliocdn.com.evil.net/x", "https://evil.net/x", "https://media.twiliocdn.com:8443/x", "https://u@media.twiliocdn.com/x", "", "https://api.twilio.com/x"):
        assert not allowed_redirect(bad), bad


def test_media_proxy_requires_a_media_token_and_an_allowlisted_url(victim, other_rep):
    enc = lambda u: urllib.parse.quote(u, safe="")  # noqa: E731
    assert call("GET", "/api/webhooks/twilio/media-proxy?url=" + enc(GOOD_MEDIA))[0] == 401
    assert call("GET", "/api/webhooks/twilio/media-proxy?url=" + enc(GOOD_MEDIA) + "&t=forged")[0] == 401
    st, body = victim.get("/api/calls/recording-token")
    assert st == 200 and body.get("token"), (st, body)
    tok = body["token"]
    for bad in BAD_URLS:
        st, resp = call("GET", "/api/webhooks/twilio/media-proxy?url=" + enc(bad) + "&t=" + tok)
        assert st == 400, (bad, st, resp)
    # allowlisted path with a valid token gets past both gates (Twilio itself says this fake media does not exist)
    st, resp = call("GET", "/api/webhooks/twilio/media-proxy?url=" + enc(GOOD_MEDIA) + "&t=" + tok)
    assert st in (404, 502), (st, resp)
    # an expired token is dead
    from services import media_tokens
    assert media_tokens.verify(media_tokens.mint(victim.user_id, ttl=-5)) is None
    assert media_tokens.verify(media_tokens.mint(victim.user_id)) == victim.user_id
    assert media_tokens.verify(media_tokens.mint(victim.user_id)[:-3] + "AAA") is None
    assert anon("GET", "/api/calls/recording-token")[0] == 401


# ── HIGH 3: call-host websocket ──────────────────────────────────────────────────────────────────────────────────────────


def _ws_probe(url: str):
    import websockets

    async def run():
        try:
            async with websockets.connect(url, open_timeout=20, close_timeout=5) as ws:
                try:
                    await asyncio.wait_for(ws.recv(), timeout=3)
                except asyncio.TimeoutError:
                    pass
                except websockets.exceptions.ConnectionClosed as e:
                    return ("closed-after-accept", e.rcvd.code if e.rcvd else None)
                return ("open", None)
        except websockets.exceptions.InvalidStatus as e:
            return ("rejected", e.response.status_code)
        except websockets.exceptions.ConnectionClosed as e:
            return ("closed", e.rcvd.code if e.rcvd else None)
    return asyncio.run(run())


def test_call_host_websocket_rejects_bad_tokens_and_accepts_the_real_one(victim, mongo):
    ws_base = API.replace("https://", "wss://").replace("http://", "ws://")
    # bad pid / bad token: closed with policy violation, never a 500 crash
    assert _ws_probe(f"{ws_base}/api/webhooks/twilio/call-host/{ZERO}/nope") in (("closed", 1008), ("closed-after-accept", 1008), ("rejected", 403))
    token = secrets.token_hex(12)
    pid = mongo.pending_calls.insert_one({"rep_user_id": victim.user_id, "customer_phone": "+15005550006", "contact_id": None, "token": token,
                                          "status": "pending", "created_at": time.time(), "qa": "hotfix4b"}).inserted_id
    try:
        assert _ws_probe(f"{ws_base}/api/webhooks/twilio/call-host/{pid}/wrong-token") in (("closed", 1008), ("closed-after-accept", 1008), ("rejected", 403))
        kind, code = _ws_probe(f"{ws_base}/api/webhooks/twilio/call-host/{pid}/{token}")
        assert kind in ("open", "closed-after-accept") and code != 1008, (kind, code)   # real-world <Stream> URL shape connects
    finally:
        mongo.pending_calls.delete_one({"_id": pid})


# ── same-rank recovery edits ─────────────────────────────────────────────────────────────────────────────────────────────


def test_same_rank_cannot_change_recovery_details(store_manager, manager2, org_a_admin, mongo):
    t = manager2.user_id
    for path, body in [
        (f"/api/auth/users/{t}", {"phone": "+15550009999"}), (f"/api/auth/users/{t}", {"email": "stolen@invalid.imonsocial.test"}),
        (f"/api/auth/user/{t}", {"phone": "+15550009999"}), (f"/api/admin/users/{t}", {"phone": "+15550009999"}), (f"/api/admin/users/{t}", {"email": "stolen@invalid.imonsocial.test"}),
    ]:
        st, resp = (store_manager.patch if path.startswith("/api/auth/users/") else store_manager.put)(path, body)
        assert st == 403, (path, body, st, resp)
    doc = _user(mongo, t)
    assert doc["phone"] == "+15550004200" and doc["email"] == "qa-hotfix4b-manager2@invalid.imonsocial.test"
    # non-recovery fields between peers in the same store still work; a higher rank may change recovery details
    st, resp = store_manager.patch(f"/api/auth/users/{t}", {"title": "QA peer title"})
    assert st == 200, (st, resp)
    st, resp = org_a_admin.patch(f"/api/auth/users/{t}", {"phone": "+15550004200"})
    assert st == 200, (st, resp)
    st, resp = manager2.patch(f"/api/auth/users/{t}", {"phone": "+15550004200"})
    assert st == 200, (st, resp)


# ── provider webhooks ────────────────────────────────────────────────────────────────────────────────────────────────────


def _form_post(path, form, headers=None):
    data = urllib.parse.urlencode(form).encode()
    req = urllib.request.Request(API + path, method="POST", data=data, headers={"Content-Type": "application/x-www-form-urlencoded", **UA, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.status, r.read().decode()[:200]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:200]


def test_lead_call_webhooks_require_a_twilio_signature():
    form = {"CallSid": "CAqa", "AccountSid": os.environ.get("TWILIO_ACCOUNT_SID", ""), "Digits": "1", "CallStatus": "completed"}
    for path in ("/api/webhooks/twilio/lead-call/answer?job=x", "/api/webhooks/twilio/lead-call/claim?job=x", "/api/webhooks/twilio/lead-call/status?job=x"):
        st, body = _form_post(path, form)
        assert st == 403, (path, st, body)
        st, body = _form_post(path, form, {"X-Twilio-Signature": "bm90LXRoZS1yZWFsLXNpZ25hdHVyZQ=="})
        assert st == 403, (path, st, body)


def test_stripe_mystery_shop_webhook_fails_closed(monkeypatch):
    st, body = anon("POST", "/api/stripe/webhook", {"type": "invoice.paid", "data": {"object": {"id": "in_qa"}}})
    assert st in (400, 503), (st, body)   # 400 = secret configured, unsigned; 503 = secret missing
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from routers import mystery_shops as msr
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "")
    app = FastAPI()
    app.include_router(msr.stripe_router)
    r = TestClient(app).post("/stripe/webhook", json={"type": "invoice.paid", "data": {"object": {"id": "in_qa"}}})
    assert r.status_code == 503, (r.status_code, r.text)


def test_adf_lead_intake_requires_the_sources_api_key(mongo):
    src = mongo.lead_sources.insert_one({"name": "QA Hotfix4b Portal", "is_active": True, "api_key": "qa-hotfix4b-key", "assignment_method": "jump_ball", "store_id": STORE_A, "qa": "hotfix4b"}).inserted_id
    try:
        xml = "<?xml version='1.0'?><adf><prospect><customer><contact><name part='full'>QA Forged</name><phone>+15005559977</phone></contact></customer></prospect></adf>"
        for headers in ({}, {"X-API-Key": "wrong"}):
            req = urllib.request.Request(f"{API}/api/leads/adf?source_id={src}", method="POST", data=xml.encode(), headers={"Content-Type": "application/xml", **UA, **headers})
            try:
                with urllib.request.urlopen(req, timeout=40) as r:
                    st, body = r.status, r.read().decode()[:200]
            except urllib.error.HTTPError as e:
                st, body = e.code, e.read().decode()[:200]
            assert st == 401, (headers, st, body)
        assert mongo.contacts.count_documents({"phone": {"$regex": "5005559977$"}, "created_at": {"$exists": True}}) == mongo.contacts.count_documents({"phone": {"$regex": "5005559977$"}, "created_at": {"$exists": True}, "source_name": {"$ne": "QA Hotfix4b Portal"}}), "no lead may have been created for the forged post"
    finally:
        mongo.lead_sources.delete_one({"_id": src})


def test_shared_inbox_webhook_needs_the_inbox_key(store_manager, victim, mongo):
    inbox = mongo.shared_inboxes.insert_one({"name": "QA Hotfix4b Inbox", "is_active": True, "organization_id": QA_ORG_A, "store_id": STORE_A, "assigned_user_ids": [], "created_by": store_manager.user_id, "qa": "hotfix4b"}).inserted_id
    lead = {"first_name": "QA", "last_name": "Webhook", "phone": "+15005550098", "message": "forged"}
    try:
        st, body = anon("POST", f"/api/admin/team/shared-inboxes/{inbox}/webhook", lead)
        assert st == 401, (st, body)
        assert anon("POST", f"/api/admin/team/shared-inboxes/{inbox}/webhook?key=guess", lead)[0] == 401
        assert mongo.contacts.count_documents({"phone": {"$regex": "5005550098$"}}) == 0
        # a plain rep can't read the key; the store's manager can, and the URL it hands out works
        assert victim.get(f"/api/admin/team/shared-inboxes/{inbox}/webhook-info?user_id={victim.user_id}")[0] == 403
        st, info = store_manager.get(f"/api/admin/team/shared-inboxes/{inbox}/webhook-info?user_id={store_manager.user_id}")
        assert st == 200 and "key=" in info["webhook_url"], (st, info)
        key = urllib.parse.parse_qs(urllib.parse.urlsplit(info["webhook_url"]).query)["key"][0]
        st, body = anon("POST", f"/api/admin/team/shared-inboxes/{inbox}/webhook?key={key}", lead)
        assert st == 200, (st, body)
    finally:
        mongo.shared_inboxes.delete_one({"_id": inbox})
        for c in mongo.contacts.find({"phone": {"$regex": "5005550098$"}}, {"_id": 1}):
            mongo.conversations.delete_many({"contact_id": str(c["_id"])})
            mongo.notifications.delete_many({"contact_id": str(c["_id"])})
        mongo.contacts.delete_many({"phone": {"$regex": "5005550098$"}})


# ── calendar OAuth state ─────────────────────────────────────────────────────────────────────────────────────────────────


def test_calendar_oauth_state_is_signed_and_session_bound(victim, other_rep):
    from routers import calendar as cal
    assert anon("GET", f"/api/calendar/oauth/login/{victim.user_id}")[0] == 401
    assert other_rep.get(f"/api/calendar/oauth/login/{victim.user_id}")[0] == 403
    st, body = victim.get(f"/api/calendar/oauth/login/{victim.user_id}")
    assert st in (200, 503), (st, body)   # 503 = Google client not configured in preview
    if st == 200:
        state = urllib.parse.parse_qs(urllib.parse.urlsplit(body["authorization_url"]).query)["state"][0]
        assert cal._user_from_state(state) == victim.user_id
    assert cal._user_from_state(cal._oauth_state(victim.user_id)) == victim.user_id
    assert cal._user_from_state(victim.user_id) is None
    assert cal._user_from_state(cal._oauth_state(victim.user_id)[:-4] + "AAAA") is None
    assert anon("GET", f"/api/calendar/oauth/callback?code=x&state={victim.user_id}")[0] == 400
    assert anon("GET", "/api/calendar/oauth/callback?code=x&state=garbage")[0] == 400


# ── inventory webhook tenant isolation ───────────────────────────────────────────────────────────────────────────────────


def test_inventory_keys_cannot_reach_another_organizations_items(mongo):
    key_a, key_b = "qa-hotfix4b-inv-a-" + secrets.token_hex(4), "qa-hotfix4b-inv-b-" + secrets.token_hex(4)
    org_a = mongo.organizations.insert_one({"name": "QA Inv Org A", "api_key": key_a, "qa": "hotfix4b"}).inserted_id
    org_b = mongo.organizations.insert_one({"name": "QA Inv Org B", "api_key": key_b, "qa": "hotfix4b"}).inserted_id
    ext = "QA-VIN-" + secrets.token_hex(4)
    try:
        st, body = call("POST", "/api/webhooks/inventory/add", {"external_id": ext, "name": "2024 QA Car", "category": "vehicle", "price": 1, "organization_id": str(org_b)}, {"X-API-Key": key_a})
        assert st == 200 and body["status"] == "created", (st, body)
        doc = mongo.inventory.find_one({"external_id": ext})
        assert doc["organization_id"] == str(org_a), "tenant comes from the key, not the body"
        assert call("POST", "/api/webhooks/inventory/update", {"external_id": ext, "price": 999}, {"X-API-Key": key_b})[0] == 404
        st, body = call("POST", "/api/webhooks/inventory/delete", {"external_id": ext}, {"X-API-Key": key_b})
        assert st == 200 and body["status"] == "not_found", (st, body)
        assert call("GET", f"/api/webhooks/inventory/{ext}", None, {"X-API-Key": key_b})[0] == 404
        st, body = call("GET", "/api/webhooks/inventory?include_hidden=true", None, {"X-API-Key": key_b})
        assert st == 200 and all(i["external_id"] != ext for i in body["items"]), (st, body.get("total"))
        st, body = call("POST", "/api/webhooks/inventory/bulk", {"operations": [{"action": "delete", "external_id": ext}]}, {"X-API-Key": key_b})
        assert st == 200 and body["details"][0]["result"] == "not_found", (st, body)
        assert mongo.inventory.find_one({"external_id": ext})["price"] == 1
        assert call("POST", "/api/webhooks/inventory/update", {"external_id": ext, "price": 2}, {"X-API-Key": key_a})[0] == 200
        assert call("GET", f"/api/webhooks/inventory/{ext}", None, {"X-API-Key": key_a})[1]["price"] == 2
    finally:
        mongo.inventory.delete_many({"external_id": ext})
        mongo.organizations.delete_many({"qa": "hotfix4b"})


# ── public AI cost exposure ──────────────────────────────────────────────────────────────────────────────────────────────


def test_public_chat_widget_is_throttled_per_ip():
    from services import ratelimit
    assert all(ratelimit.allow("unit", 3, 60, now=100 + i) for i in range(3)) and not ratelimit.allow("unit", 3, 60, now=103) and ratelimit.allow("unit", 3, 60, now=161)
    statuses = [anon("POST", "/api/chat/start", {"page": "qa-hotfix4b"})[0] for _ in range(12)]
    assert 429 in statuses and set(statuses) <= {200, 429}, statuses   # 10/min per IP; earlier runs in the same minute only make it trip sooner


# ── call recordings by sid ───────────────────────────────────────────────────────────────────────────────────────────────


def test_call_recordings_need_a_listener_who_may_hear_them(victim, other_rep, store_manager, super_admin, mongo):
    sid = "CAqa" + secrets.token_hex(15)
    mongo.call_logs.insert_one({"call_sid": sid, "user_id": victim.user_id, "recording_url": "https://api.twilio.com/2010-04-01/Accounts/AC" + "a" * 32 + "/Recordings/RE" + "f" * 32, "recording_sid": "RE" + "f" * 32, "qa": "hotfix4b"})
    try:
        assert anon("GET", f"/api/calls/recording/{sid}")[0] == 401
        assert call("GET", f"/api/calls/recording/{sid}?t=forged")[0] == 401
        tok = lambda s: s.get("/api/calls/recording-token")[1]["token"]  # noqa: E731
        assert call("GET", f"/api/calls/recording/{sid}?t={tok(other_rep)}")[0] == 404     # another dealership: hidden
        assert other_rep.get(f"/api/calls/recording/{sid}")[0] == 404
        for who in (victim, store_manager, super_admin):                                     # allowed listeners reach the fetch (fake recording -> 502)
            st, body = call("GET", f"/api/calls/recording/{sid}?t={tok(who)}")
            assert st == 502, (who.email, st, body)
    finally:
        mongo.call_logs.delete_one({"call_sid": sid})
