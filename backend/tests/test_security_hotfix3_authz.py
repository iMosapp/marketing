"""Security hotfix part 3: /api default deny + {user_id} ownership with organization boundaries + the account routes under /auth.

Live preview API. For every affected route: anonymous -> 401, another rep -> 403, a manager from another organization -> 403,
the user themselves (and their own scoped manager / super admin) -> allowed. Legit app flows and public pages keep working."""
import os

import pytest
import requests
from bson import ObjectId

from tests._http import API, call
from tests.live_auth import ORG_B, REP, STORE_A, STORE_B, Session, anon, ensure_qa_user

BASE = API
QA_ORG_A = "org_001"  # STORE_A's organization


@pytest.fixture(scope="module")
def victim(mongo):
    """A rep in STORE_A (manager A's store): the account the attackers try to touch."""
    email, pw = ensure_qa_user(mongo, "qa-hotfix3-victim@invalid.imonsocial.test", "user", QA_ORG_A, STORE_A, "QA Hotfix Victim")
    s = Session(email, pw)
    mongo.users.update_one({"_id": ObjectId(s.user_id)}, {"$set": {"phone": "+15550000001", "persona": {"bio": "original bio"}, "review_links": {"google": "https://g.page/original"}}})
    return s


@pytest.fixture(scope="module")
def other_rep(mongo):
    email, pw = ensure_qa_user(mongo, "qa-hotfix3-rep@invalid.imonsocial.test", "user", ORG_B, STORE_B, "QA Hotfix Other Rep")
    return Session(email, pw)


@pytest.fixture(scope="module")
def foreign_manager(org_admin):
    """org_admin of ORG_B: a manager, but not of the victim's organization."""
    return org_admin


@pytest.fixture(scope="module")
def own_manager(store_manager):
    """store_manager on STORE_A: the victim's own manager."""
    return store_manager


def _codes(victim, other_rep, foreign_manager, method, path, body=None):
    a = anon(method, path, body)[0]
    r = getattr(other_rep, method.lower())(path, body)[0] if method != "GET" else other_rep.get(path)[0]
    f = getattr(foreign_manager, method.lower())(path, body)[0] if method != "GET" else foreign_manager.get(path)[0]
    return a, r, f


# ── identity middleware: default deny + X-User-ID binding ──────────────────────────────────────────────────────────────────

def test_auth_routes_no_longer_skip_the_identity_gate(victim):
    uid = victim.user_id
    for method, path in (("PATCH", f"/api/auth/users/{uid}"), ("PUT", f"/api/auth/user/{uid}"), ("POST", f"/api/auth/persona/{uid}"),
                         ("GET", f"/api/auth/persona/{uid}/ai-prompt"), ("POST", f"/api/auth/persona/{uid}/sample-message"),
                         ("GET", f"/api/auth/users/{uid}/review-links"), ("PUT", f"/api/auth/users/{uid}/review-links"),
                         ("POST", "/api/auth/change-password"), ("POST", "/api/auth/complete-onboarding"), ("GET", f"/api/auth/user/{uid}")):
        st, body = anon(method, path, {"name": "x"} if method != "GET" else None)
        assert st == 401, (method, path, st, body)
        # a spoofed X-User-ID without a token is worthless
        st2, _ = call(method, path, {"name": "x"} if method != "GET" else None, {"X-User-ID": uid})
        assert st2 == 401, (method, path, st2)


def test_spoofed_x_user_id_with_a_real_token_is_refused(victim, other_rep):
    st, body = call("GET", f"/api/auth/user/{victim.user_id}", headers={"Authorization": "Bearer " + other_rep.token, "X-User-ID": victim.user_id})
    assert st == 401, (st, body)


def test_test_login_is_gone():
    st, body = anon("POST", "/api/auth/test-login", {"email": "forest@imosapp.com", "password": "guess"})
    assert st == 410, (st, body)
    assert "diagnostics" not in str(body)


# ── PATCH /auth/users/{id}, PUT /auth/user/{id}: email / phone takeover ──────────────────────────────────────────────────────

def test_patch_user_email_and_phone(victim, other_rep, foreign_manager, own_manager, super_admin, mongo):
    uid = victim.user_id
    evil = {"email": "attacker-hotfix3@invalid.imonsocial.test", "phone": "+15559999999"}
    assert _codes(victim, other_rep, foreign_manager, "PATCH", f"/api/auth/users/{uid}", evil) == (401, 403, 403)
    assert _codes(victim, other_rep, foreign_manager, "PUT", f"/api/auth/user/{uid}", {"phone": "+15559999999"}) == (401, 403, 403)
    doc = mongo.users.find_one({"_id": ObjectId(uid)}, {"email": 1, "phone": 1})
    assert doc["email"] == victim.email and doc["phone"] == "+15550000001", "nothing changed"
    st, body = victim.patch(f"/api/auth/users/{uid}", {"phone": "+15550000002", "title": "Sales"})
    assert st == 200 and body["phone"] == "+15550000002" and "password" not in body, (st, body)
    st, _ = own_manager.put(f"/api/auth/user/{uid}", {"timezone": "America/Denver"})
    assert st == 200
    st, _ = super_admin.patch(f"/api/auth/users/{uid}", {"title": "Senior Sales"})
    assert st == 200


def test_persona_and_review_links(victim, other_rep, foreign_manager, own_manager, mongo):
    uid = victim.user_id
    persona = {"bio": "hijacked bio that is long enough", "tone": "rude"}
    assert _codes(victim, other_rep, foreign_manager, "POST", f"/api/auth/persona/{uid}", persona) == (401, 403, 403)
    assert _codes(victim, other_rep, foreign_manager, "GET", f"/api/auth/persona/{uid}/ai-prompt") == (401, 403, 403)
    assert _codes(victim, other_rep, foreign_manager, "POST", f"/api/auth/persona/{uid}/sample-message", {"scenario": "hi"}) == (401, 403, 403)
    assert _codes(victim, other_rep, foreign_manager, "GET", f"/api/auth/users/{uid}/review-links") == (401, 403, 403)
    assert _codes(victim, other_rep, foreign_manager, "PUT", f"/api/auth/users/{uid}/review-links", {"review_links": {"google": "https://evil"}}) == (401, 403, 403)
    doc = mongo.users.find_one({"_id": ObjectId(uid)}, {"persona": 1, "review_links": 1})
    assert doc["persona"]["bio"] == "original bio" and doc["review_links"]["google"] == "https://g.page/original"
    st, body = victim.put(f"/api/auth/users/{uid}/review-links", {"review_links": {"google": "https://g.page/mine"}, "custom_link_name": "Mine"})
    assert st == 200, body
    st, body = victim.get(f"/api/auth/users/{uid}/review-links")
    assert st == 200 and body["review_links"]["google"] == "https://g.page/mine"
    st, body = own_manager.get(f"/api/auth/persona/{uid}/ai-prompt")
    assert st == 200 and "prompt" in body
    st, body = victim.post(f"/api/auth/persona/{uid}", {"bio": "my own bio, written by me and long enough"})
    assert st == 200, body


def test_change_password_and_onboarding_bind_to_the_caller(victim, other_rep):
    st, body = other_rep.post("/api/auth/change-password", {"user_id": victim.user_id, "current_password": "x", "new_password": "Hijack123!"})
    assert st == 403, (st, body)
    st, body = other_rep.post("/api/auth/complete-onboarding", {"user_id": victim.user_id, "name": "Hijacked"})
    assert st == 403, (st, body)
    st, body = victim.post("/api/auth/change-password", {"current_password": "definitely-wrong", "new_password": "Whatever123!"})
    assert st == 401, (st, body)  # own account, wrong current password: refused by the password check, not by authz


# ── messages: sending as someone else, touching someone else's conversation ─────────────────────────────────────────────────

def test_messages_send_as_another_user(victim, other_rep, foreign_manager):
    uid = victim.user_id
    body = {"conversation_id": str(ObjectId()), "content": "pwned"}
    assert _codes(victim, other_rep, foreign_manager, "POST", f"/api/messages/send/{uid}", body) == (401, 403, 403)
    assert _codes(victim, other_rep, foreign_manager, "POST", f"/api/messages/send/{uid}/{ObjectId()}", {"content": "pwned"}) == (401, 403, 403)
    assert _codes(victim, other_rep, foreign_manager, "POST", f"/api/messages/merge-duplicates/{uid}") == (401, 403, 403)
    st, body = other_rep.post("/api/messages/schedule-delayed", {"user_id": uid, "to": "+15551234567", "body": "pwned"})
    assert st == 403, (st, body)
    st, body = other_rep.post("/api/messages/twilio-send", {"user_id": uid, "to": "+15551234567", "body": "pwned"})
    assert st == 403, (st, body)
    st, body = victim.post(f"/api/messages/send/{uid}/{ObjectId()}", {"content": "hello"})
    assert st in (404, 400, 422), (st, body)  # own path: past authorization, conversation simply does not exist


def test_conversation_routes_check_ownership(victim, other_rep, own_manager, foreign_manager, mongo):
    conv = {"user_id": victim.user_id, "contact_phone": "+15550001111", "contact_name": "QA Contact", "status": "active", "unread": True,
            "created_at": __import__("datetime").datetime.utcnow()}
    cid = str(mongo.conversations.insert_one(conv).inserted_id)
    try:
        for method, path in (("PUT", f"/api/messages/conversation/{cid}/archive"), ("PUT", f"/api/messages/conversation/{cid}/read"),
                             ("PUT", f"/api/messages/conversation/{cid}/unread"), ("GET", f"/api/messages/conversation/{cid}/info"),
                             ("POST", f"/api/messages/ai-suggest/{cid}"), ("DELETE", f"/api/messages/conversation/{cid}")):
            a, r, f = _codes(victim, other_rep, foreign_manager, method, path, {} if method in ("PUT", "POST") else None)
            assert (a, r, f) == (401, 403, 403), (method, path, a, r, f)
        st, body = other_rep.post("/api/messages/bulk/archive", {"conversation_ids": [cid]})
        assert st == 200 and body["modified_count"] == 0, (st, body)
        st, body = other_rep.post("/api/messages/bulk/delete", {"conversation_ids": [cid]})
        assert st == 200 and body["deleted_count"] == 0, (st, body)
        assert mongo.conversations.find_one({"_id": ObjectId(cid)})["status"] == "active"
        st, _ = victim.put(f"/api/messages/conversation/{cid}/read")
        assert st == 200
        st, _ = own_manager.put(f"/api/messages/conversation/{cid}/archive")
        assert st == 200
        st, body = victim.post("/api/messages/bulk/restore", {"conversation_ids": [cid]})
        assert st == 200 and body["modified_count"] == 1, body
    finally:
        mongo.conversations.delete_one({"_id": ObjectId(cid)})


# ── profile ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────

def test_profile_writes_need_the_owner_reads_stay_public(victim, other_rep, foreign_manager):
    uid = victim.user_id
    assert _codes(victim, other_rep, foreign_manager, "PUT", f"/api/profile/{uid}", {"bio": "hijacked"}) == (401, 403, 403)
    assert _codes(victim, other_rep, foreign_manager, "POST", f"/api/profile/{uid}/generate-bio", {}) == (401, 403, 403)
    assert anon("GET", f"/api/profile/{uid}")[0] == 200, "public presence page"
    assert anon("GET", f"/api/profile/{uid}/vcard.vcf")[0] in (200, 404)
    st, body = victim.put(f"/api/profile/{uid}", {"bio": "my bio"})
    assert st == 200, body


# ── public surface stays open, everything else is closed ───────────────────────────────────────────────────────────────────

def test_public_flows_still_answer_without_a_session(victim):
    checks = [("GET", "/api/health", 200), ("GET", "/api/legal/terms", 200), ("GET", f"/api/card/{victim.user_id}", 200),
              ("GET", f"/api/p/{victim.user_id}", 200), ("GET", "/api/subscriptions/plans", 200), ("GET", "/api/auth/ref/nope", 200),
              ("POST", "/api/auth/login", 401), ("POST", "/api/auth/refresh", 401), ("GET", "/api/auth/me", 401),
              ("POST", "/api/auth/forgot-password/request", 400), ("POST", "/api/demo-requests", 200), ("POST", "/api/app-installs/first-open", 400),
              ("POST", "/api/cron/pilot-reminders", 401), ("GET", "/api/v1/contacts", 401), ("POST", "/api/webhooks/twilio/sms", 403),  # public route, but unsigned Twilio callbacks are refused (hotfix 4)
              ("POST", "/api/messages/webhook/inbound", 403), ("POST", "/api/leads/adf", 400), ("GET", "/api/public/platform-stats", 200)]
    for method, path, want in checks:
        st, body = anon(method, path, {} if method == "POST" else None)
        assert st == want, (method, path, st, str(body)[:120])


def test_private_reads_are_closed_to_strangers():
    for path in ("/api/directory/members", "/api/demo-requests", "/api/partners/agreements", "/api/invoices/user/" + "0" * 24,
                 "/api/jessie/history/" + "0" * 24, "/api/lifecycle/dashboard", "/api/errors/recent", "/api/permission-templates/",
                 "/api/webhooks/unassigned-contacts", "/api/p/referrals/" + "0" * 24, "/api/p/reviews/pending/" + "0" * 24,
                 "/api/account-health/overview", "/api/nda/agreements", "/api/calendar/appointments/" + "0" * 24):
        st, _ = anon("GET", path)
        assert st == 401, (path, st)


def test_user_id_routes_enforce_organization_boundaries(victim, other_rep, foreign_manager, own_manager, super_admin):
    uid = victim.user_id
    for path in (f"/api/jessie/history/{uid}", f"/api/calendar/status/{uid}", f"/api/review-templates/{uid}", f"/api/auth/user/{uid}"):
        assert _codes(victim, other_rep, foreign_manager, "GET", path) == (401, 403, 403), path
        assert victim.get(path)[0] == 200, path
        assert own_manager.get(path)[0] == 200, path
        assert super_admin.get(path)[0] == 200, path


def test_query_user_id_is_bound_like_the_path_parameter(victim, other_rep, foreign_manager, own_manager, super_admin):
    """49 routes read `?user_id=` (notifications, broadcast, team chat, lead claims...): it is an identity claim and is bound too."""
    uid = victim.user_id
    for method, path in (("GET", f"/api/notifications/?user_id={uid}"), ("GET", f"/api/notifications/unread-count?user_id={uid}"),
                         ("POST", f"/api/notifications/mark-all-read?user_id={uid}"), ("GET", f"/api/chat/leads?user_id={uid}"),
                         ("GET", f"/api/team-chat/channels?user_id={uid}"), ("GET", f"/api/broadcast?user_id={uid}"),
                         ("POST", f"/api/notifications/{ObjectId()}/action?action=dismissed&user_id={uid}")):
        a, r, f = _codes(victim, other_rep, foreign_manager, method, path, {} if method == "POST" else None)
        assert (a, r, f) == (401, 403, 403), (method, path, a, r, f)
    assert victim.get(f"/api/notifications/unread-count?user_id={uid}")[0] == 200
    assert own_manager.get(f"/api/notifications/unread-count?user_id={uid}")[0] == 200
    assert super_admin.get(f"/api/notifications/unread-count?user_id={uid}")[0] == 200
    st, body = other_rep.get(f"/api/notifications/unread-count?user_id={other_rep.user_id}")
    assert st == 200, (st, body)


def test_inbox_and_lead_notification_calls_work_with_a_session(own_manager, victim):
    """The app used to call these with a bare fetch(); they now go through the token-injecting client."""
    st, body = own_manager.get(f"/api/chat/leads?user_id={own_manager.user_id}")
    assert st == 200 and "conversations" in body, (st, body)
    st, body = own_manager.get(f"/api/admin/team/shared-inboxes?user_id={own_manager.user_id}")
    assert st == 200, (st, body)
    st, body = victim.post(f"/api/notifications/{ObjectId()}/action?action=dismissed&user_id={victim.user_id}")
    assert st == 404, (st, body)  # past the gate, notification does not exist


def test_congrats_card_page_needs_no_session(victim, mongo):
    """Customer-facing card: slug + link page come with the card (the page no longer calls /auth/user), referral link stays public."""
    import datetime as _dt
    card_id = f"qa-hotfix3-{ObjectId()}"
    mongo.congrats_cards.insert_one({"card_id": card_id, "salesman_id": victim.user_id, "customer_name": "QA Customer", "customer_phone": "+15550001111",
                                     "headline": "Thank You!", "message": "Hi {customer_name}", "card_type": "congrats", "show_salesman": True,
                                     "salesman_name": "QA Hotfix Victim", "created_at": _dt.datetime.utcnow(), "views": 0})
    try:
        st, body = anon("GET", f"/api/congrats/card/{card_id}?preview=rep")
        assert st == 200, (st, body)
        assert "linkpage_username" in body and ("store" not in body or body["store"] is None or "slug" in body["store"]), body
        st, body = anon("POST", f"/api/congrats/referral-link/{victim.user_id}?card_id={card_id}")
        assert st == 200 and body.get("short_url"), (st, body)
        assert anon("POST", f"/api/congrats/card/{card_id}/track", {"action": "share"})[0] == 200
        assert anon("GET", f"/api/auth/user/{victim.user_id}")[0] == 401, "the user profile itself stays private"
        assert anon("GET", f"/api/linkpage/user/{victim.user_id}")[0] == 401
    finally:
        mongo.congrats_cards.delete_one({"card_id": card_id})
        mongo.short_urls.delete_many({"reference_id": victim.user_id, "link_type": "referral"})


# ── webhooks that used to run in "demo mode" without a secret ─────────────────────────────────────────────────────────────

def test_external_webhooks_fail_closed_without_a_secret(victim, mongo):
    """POST /api/webhooks/user-created used to accept anonymous calls and set ANY role on ANY account (verified: user -> super_admin)."""
    email = "qa-webhook-probe@example.com"
    mongo.users.delete_many({"email": email})
    mongo.users.insert_one({"email": email, "name": "QA Webhook Probe", "role": "user", "status": "active", "is_active": True, "password": "x",
                            "organization_id": ORG_B})
    try:
        st, body = anon("POST", "/api/webhooks/user-created", {"external_id": "probe", "email": email, "name": "QA Webhook Probe", "role": "super_admin"})
        assert st == 401, (st, body)
        assert mongo.users.find_one({"email": email})["role"] == "user"
        st, _ = call("POST", "/api/webhooks/user-created", {"external_id": "probe", "email": email, "name": "x", "role": "super_admin"},
                     {"X-Webhook-Secret": "not-a-real-secret"})
        assert st == 401
        assert anon("POST", "/api/webhooks/user-deleted", {"email": email})[0] == 401
        assert mongo.users.find_one({"email": email})["is_active"] is True
        assert anon("POST", "/api/webhooks/contact-created", {"external_id": "c1", "name": "x"})[0] == 401
        assert anon("POST", "/api/webhooks/event", {"type": "probe"})[0] == 401
        assert anon("POST", "/api/webhooks/inventory/add", {"external_id": "v1", "name": "car"})[0] == 401
        assert anon("GET", "/api/webhooks/inventory")[0] == 401
        assert anon("GET", "/api/webhooks/config")[0] == 200, "documentation stays public"
    finally:
        mongo.users.delete_many({"email": email})


def test_external_webhook_is_bound_to_its_organization(victim, mongo):
    """With a real secret: no admin roles, no store outside the org, no edits to another organization's users."""
    secret = f"qa-hotfix3-{ObjectId()}"
    mongo.organizations.update_one({"_id": ObjectId(ORG_B)}, {"$set": {"webhook_secret": secret}})
    new_email = f"qa-webhook-new-{str(ObjectId())[-6:]}@example.com"
    hdr = {"X-Webhook-Secret": secret}
    try:
        st, body = call("POST", "/api/webhooks/user-created", {"external_id": "ext-1", "email": new_email, "name": "QA Ext Rep", "role": "super_admin",
                                                               "organization_id": QA_ORG_A, "store_id": STORE_A}, hdr)
        assert st == 400, (st, body)  # STORE_A is not in ORG_B
        st, body = call("POST", "/api/webhooks/user-created", {"external_id": "ext-1", "email": new_email, "name": "QA Ext Rep", "role": "super_admin",
                                                               "organization_id": QA_ORG_A}, hdr)
        assert st == 200, (st, body)
        doc = mongo.users.find_one({"email": new_email})
        assert doc["role"] == "user" and doc["organization_id"] == ORG_B, doc
        outsider = mongo.users.find_one({"email": REP[0]}, {"role": 1, "is_active": 1})  # a real account outside ORG_B (.test addresses fail EmailStr)
        st, body = call("POST", "/api/webhooks/user-created", {"external_id": "ext-2", "email": REP[0], "name": "Hijack", "role": "store_manager"}, hdr)
        assert st == 403, (st, body)
        assert mongo.users.find_one({"email": REP[0]})["role"] == outsider["role"]
        st, body = call("POST", "/api/webhooks/user-deleted", {"email": REP[0]}, hdr)
        assert st == 200 and body["status"] == "not_found", (st, body)
        assert mongo.users.find_one({"email": REP[0]}).get("is_active") == outsider.get("is_active")
        st, body = call("POST", "/api/webhooks/user-deleted", {"email": new_email}, hdr)
        assert st == 200 and body["status"] == "deleted", (st, body)
    finally:
        mongo.organizations.update_one({"_id": ObjectId(ORG_B)}, {"$unset": {"webhook_secret": ""}})
        mongo.users.delete_many({"email": new_email})


def test_short_links_are_minted_only_for_a_session(victim, other_rep, super_admin, mongo):
    body = {"original_url": "https://example.com/qa-hotfix3", "link_type": "qa_test"}
    assert anon("POST", "/api/s/create", body)[0] == 401
    assert anon("POST", "/api/s/wrap", {"url": "https://example.com/x", "user_id": victim.user_id})[0] == 401
    st, resp = other_rep.post("/api/s/create", {**body, "user_id": victim.user_id})
    assert st == 403, (st, resp)
    st, resp = victim.post("/api/s/create", body)
    assert st == 200 and resp.get("short_code"), (st, resp)
    try:
        assert anon("GET", f"/api/s/{resp['short_code']}")[0] == 200, "redirect page stays public"
        assert anon("GET", f"/api/s/stats/{resp['short_code']}")[0] == 401
        assert super_admin.get(f"/api/s/stats/{resp['short_code']}")[0] == 200
        assert mongo.short_urls.find_one({"short_code": resp["short_code"]})["user_id"] == victim.user_id
    finally:
        mongo.short_urls.delete_many({"short_code": resp["short_code"]})
    st, _ = other_rep.get("/api/webhooks/unassigned-contacts")
    assert st == 403


def test_anonymous_write_surface_is_exactly_the_public_allowlist():
    """Every POST/PUT/PATCH/DELETE route that answers a stranger with anything but 401/403 must be listed public in route_guard."""
    import re
    from fastapi.routing import APIRoute
    from server import app
    from services.route_guard import is_public
    leaks = []
    for r in app.routes:
        if not isinstance(r, APIRoute) or not r.path.startswith("/api/"):
            continue
        for m in sorted(r.methods - {"HEAD", "OPTIONS", "GET"}):
            if is_public(m, re.sub(r"\{[^}]+\}", "0" * 24, r.path)) or is_public(m, re.sub(r"\{[^}]+\}", "probe", r.path)):
                continue
            path = re.sub(r"\{[^}]+\}", "0" * 24, r.path)
            try:
                st = requests.request(m, BASE + path, json={}, timeout=20).status_code
            except Exception:
                continue
            if st not in (401, 403):
                leaks.append((m, r.path, st))
    assert not leaks, leaks
