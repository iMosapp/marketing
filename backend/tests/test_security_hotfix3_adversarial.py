"""Independent adversarial verification of Security Hotfix 3 (P0).
Author: T1 testing agent, Jan 2026. Preview-only. Each attack is phrased from scratch
and never reuses the main suite's helpers beyond login + mongo. Cleans up every
doc it inserts (conversations / short_urls / congrats_cards / webhook secrets).
"""
import uuid

import pytest
from bson import ObjectId

from tests import qa_creds
from tests._http import call, login
from tests.live_auth import (
    ORG_ADMIN,
    STORE_MANAGER,
    SUPER_ADMIN,
)

VICTIM = ("qa-hotfix3-victim@invalid.imonsocial.test", qa_creds.password_for("qa-hotfix3-victim@invalid.imonsocial.test"))
REP_B = ("qa-hotfix3-rep@invalid.imonsocial.test", qa_creds.password_for("qa-hotfix3-rep@invalid.imonsocial.test"))
PROFILE_TESTER = ("qa-profile-tester@invalid.imonsocial.test", qa_creds.password_for("qa-profile-tester@invalid.imonsocial.test"))
PLAIN_REP = ("mjeast1985@gmail.com", "NavyBean1!")


def H(tok):
    return {"Authorization": "Bearer " + tok}


@pytest.fixture(scope="module")
def tokens():
    sa_tok, sa_id = login(*SUPER_ADMIN)
    mgr_tok, mgr_id = login(*STORE_MANAGER)
    orga_tok, orga_id = login(*ORG_ADMIN)
    v_tok, v_id = login(*VICTIM)
    b_tok, b_id = login(*REP_B)
    pt_tok, pt_id = login(*PROFILE_TESTER)
    plain_tok, plain_id = login(*PLAIN_REP)
    return {
        "sa": (sa_tok, sa_id), "mgr": (mgr_tok, mgr_id), "orga": (orga_tok, orga_id),
        "victim": (v_tok, v_id), "rep_b": (b_tok, b_id),
        "pt": (pt_tok, pt_id), "plain": (plain_tok, plain_id),
    }


# -------- 1. anonymous default-deny on non-public /api routes --------
ANON_PROBES = [
    ("GET", "/api/auth/user/{VID}"),
    ("PATCH", "/api/auth/users/{VID}"),
    ("POST", "/api/auth/persona/{VID}"),
    ("PUT", "/api/auth/users/{VID}/review-links"),
    ("POST", "/api/auth/change-password"),
    ("POST", "/api/auth/complete-onboarding"),
    ("POST", "/api/messages/send/{VID}"),
    ("PUT", "/api/profile/{VID}"),
    ("GET", "/api/notifications/?user_id={VID}"),
    ("GET", "/api/directory/members"),
    ("GET", "/api/s/stats/XYZ123"),
    ("POST", "/api/s/create"),
]


def test_anonymous_default_deny(tokens):
    vid = tokens["victim"][1]
    fails = []
    for method, path in ANON_PROBES:
        p = path.replace("{VID}", vid)
        st, _b = call(method, p, body={} if method != "GET" else None)
        if st != 401:
            fails.append((method, p, st))
    assert not fails, f"routes answered a stranger with != 401: {fails}"


def test_bare_x_user_id_header_without_bearer_rejected(tokens):
    vid = tokens["victim"][1]
    st, _ = call("GET", f"/api/auth/user/{vid}", headers={"X-User-ID": vid})
    assert st == 401
    st, _ = call("GET", "/api/auth/me", headers={"X-User-ID": vid})
    assert st == 401


# -------- 2. token/header mismatch (spoofing) --------
def test_x_user_id_spoof_rejected(tokens):
    b_tok, _b_id = tokens["rep_b"]
    vid = tokens["victim"][1]
    st, _ = call("GET", f"/api/auth/user/{vid}", headers={"Authorization": "Bearer " + b_tok, "X-User-ID": vid})
    assert st == 401


# -------- 3. cross-org 403 on path {user_id} routes + DB stays untouched --------
def test_cross_org_patch_users_denied_and_db_untouched(tokens, mongo):
    _, vid = tokens["victim"]
    b_tok, _ = tokens["rep_b"]
    orga_tok, _ = tokens["orga"]
    before = mongo.users.find_one({"_id": ObjectId(vid)}, {"email": 1, "phone": 1})
    attempts = [
        ("rep_b", b_tok),
        ("foreign_org_admin", orga_tok),
    ]
    for label, tok in attempts:
        st, _ = call("PATCH", f"/api/auth/users/{vid}", body={"email": "pwn@attacker.test", "phone": "+15005559999"}, headers=H(tok))
        assert st == 403, f"{label} PATCH returned {st}"
    after = mongo.users.find_one({"_id": ObjectId(vid)}, {"email": 1, "phone": 1})
    assert before == after, "DB mutated by foreign PATCH"


def test_victim_can_patch_self_and_super_admin_too(tokens, mongo):
    v_tok, vid = tokens["victim"]
    sa_tok, _ = tokens["sa"]
    mgr_tok, _ = tokens["mgr"]
    # self PATCH no-op
    st, _ = call("PATCH", f"/api/auth/users/{vid}", body={"title": "QA Hotfix3 Victim"}, headers=H(v_tok))
    assert st == 200
    # super admin
    st, _ = call("PATCH", f"/api/auth/users/{vid}", body={"title": "QA Hotfix3 Victim"}, headers=H(sa_tok))
    assert st == 200
    # own store manager (STORE_A)
    st, _ = call("PATCH", f"/api/auth/users/{vid}", body={"title": "QA Hotfix3 Victim"}, headers=H(mgr_tok))
    assert st == 200


def test_persona_review_links_cross_org_403(tokens):
    _, vid = tokens["victim"]
    b_tok, _ = tokens["rep_b"]
    orga_tok, _ = tokens["orga"]
    for tok in (b_tok, orga_tok):
        st, _ = call("POST", f"/api/auth/persona/{vid}", body={"tone": "pwn"}, headers=H(tok))
        assert st == 403
        st, _ = call("GET", f"/api/auth/persona/{vid}/ai-prompt", headers=H(tok))
        assert st == 403
        st, _ = call("GET", f"/api/auth/users/{vid}/review-links", headers=H(tok))
        assert st == 403
        st, _ = call("PUT", f"/api/auth/users/{vid}/review-links", body={"links": []}, headers=H(tok))
        assert st == 403


def test_profile_cross_org_403(tokens):
    _, vid = tokens["victim"]
    b_tok, _ = tokens["rep_b"]
    orga_tok, _ = tokens["orga"]
    for tok in (b_tok, orga_tok):
        st, _ = call("PUT", f"/api/profile/{vid}", body={"bio": "pwn"}, headers=H(tok))
        assert st == 403
        st, _ = call("POST", f"/api/profile/{vid}/generate-bio", body={}, headers=H(tok))
        assert st == 403


def test_messages_send_cross_user_403(tokens):
    _, vid = tokens["victim"]
    b_tok, _ = tokens["rep_b"]
    # send using a fake conversation id so NOTHING would be sent even if auth was broken
    fake_cid = "ffffffffffffffffffffffff"
    st, _ = call("POST", f"/api/messages/send/{vid}", body={"conversation_id": fake_cid, "content": "pwn"}, headers=H(b_tok))
    assert st == 403
    st, _ = call("POST", f"/api/messages/send/{vid}/{fake_cid}", body={"content": "pwn"}, headers=H(b_tok))
    assert st == 403


# -------- 4. body-bound identity --------
def test_body_user_id_binding(tokens):
    _, vid = tokens["victim"]
    b_tok, _ = tokens["rep_b"]
    st, _ = call("POST", "/api/auth/change-password", body={"user_id": vid, "current_password": "x", "new_password": "y"}, headers=H(b_tok))
    assert st == 403
    st, _ = call("POST", "/api/auth/complete-onboarding", body={"user_id": vid}, headers=H(b_tok))
    assert st == 403


# -------- 5. query-string identity binding --------
QS_PROBES = [
    "/api/notifications/?user_id={VID}",
    "/api/notifications/unread-count?user_id={VID}",
    "/api/chat/leads?user_id={VID}",
    "/api/team-chat/channels?user_id={VID}",
    "/api/broadcast?user_id={VID}",
]


def test_query_user_id_cross_user_403(tokens):
    _, vid = tokens["victim"]
    b_tok, _ = tokens["rep_b"]
    for path in QS_PROBES:
        st, _ = call("GET", path.replace("{VID}", vid), headers=H(b_tok))
        assert st == 403, f"{path} returned {st} for cross-user rep"
    # mark-all-read is POST
    st, _ = call("POST", f"/api/notifications/mark-all-read?user_id={vid}", body={}, headers=H(b_tok))
    assert st == 403


def test_query_user_id_own_200(tokens):
    v_tok, vid = tokens["victim"]
    sa_tok, _ = tokens["sa"]
    mgr_tok, _ = tokens["mgr"]
    for tok, label in [(v_tok, "self"), (sa_tok, "super admin"), (mgr_tok, "own store manager")]:
        st, _ = call("GET", f"/api/notifications/unread-count?user_id={vid}", headers=H(tok))
        assert st == 200, f"{label} got {st}"


# -------- 6. conversation ownership --------
@pytest.fixture
def throwaway_conv(mongo, tokens):
    _, vid = tokens["victim"]
    oid = ObjectId()
    cid = str(oid)
    mongo.conversations.insert_one({
        "_id": oid, "user_id": vid, "customer_phone": "+15005550101",
        "customer_name": "QA Throwaway", "last_message_at": None,
        "status": "active", "unread_count": 0,
    })
    yield cid
    mongo.conversations.delete_one({"_id": oid})


def test_conversation_ownership_rules(tokens, throwaway_conv, mongo):
    cid = throwaway_conv
    b_tok, _ = tokens["rep_b"]
    orga_tok, _ = tokens["orga"]
    v_tok, _ = tokens["victim"]
    mgr_tok, _ = tokens["mgr"]
    # anonymous 401
    assert call("GET", f"/api/messages/conversation/{cid}/info")[0] == 401
    # rep_b: /info may be 403 or 404 (404 hides existence); writes return 403 or 404 (both deny)
    assert call("GET", f"/api/messages/conversation/{cid}/info", headers=H(b_tok))[0] in (403, 404)
    assert call("PUT", f"/api/messages/conversation/{cid}/archive", body={}, headers=H(b_tok))[0] in (403, 404)
    assert call("POST", f"/api/messages/ai-suggest/{cid}", body={}, headers=H(b_tok))[0] in (403, 404)
    assert call("DELETE", f"/api/messages/conversation/{cid}", headers=H(b_tok))[0] in (403, 404)
    # foreign org_admin 403/404
    assert call("GET", f"/api/messages/conversation/{cid}/info", headers=H(orga_tok))[0] in (403, 404)
    # owner 200
    assert call("GET", f"/api/messages/conversation/{cid}/info", headers=H(v_tok))[0] == 200
    # owner's manager 200
    assert call("GET", f"/api/messages/conversation/{cid}/info", headers=H(mgr_tok))[0] == 200
    # bulk by rep_b: 200 but 0 affected and doc intact
    st, body = call("POST", "/api/messages/bulk/archive", body={"conversation_ids": [cid]}, headers=H(b_tok))
    assert st == 200
    assert body.get("modified_count", 0) == 0, body
    doc = mongo.conversations.find_one({"_id": ObjectId(cid)})
    assert doc and doc.get("status") == "active"


# -------- 7. test-login gone --------
def test_auth_test_login_is_410():
    st, body = call("POST", "/api/auth/test-login", body={"email": "x@y", "password": "z"})
    assert st == 410
    low = (body if isinstance(body, str) else str(body)).lower()
    for leak in ("stacktrace", "traceback", "mongo", "bcrypt", "secret"):
        assert leak not in low


# -------- 8. public surface stays open --------
def test_public_surface_open():
    for p in [
        "/api/health",
        "/api/legal/terms",
        "/api/subscriptions/plans",
        "/api/auth/ref/nope",
        "/api/public/platform-stats",
        "/api/webhooks/config",
    ]:
        st, _ = call("GET", p)
        assert st == 200, (p, st)
    # bad login is 401 but not "Authentication required"
    st, body = call("POST", "/api/auth/login", body={"email": "nobody@nope.test", "password": "nope"})
    assert st == 401
    low = (body if isinstance(body, str) else str(body)).lower()
    assert "authentication required" not in low
    # refresh / me without session -> 401
    for p in ["/api/auth/refresh", "/api/auth/me"]:
        st, _ = call("GET", p) if p.endswith("me") else call("POST", p, body={})
        assert st == 401
    # demo-requests open
    st, _ = call("POST", "/api/demo-requests", body={"email": "qa@example.com", "name": "QA", "company": "QA", "notes": "qa"})
    assert st in (200, 201, 400, 422)


# -------- 9. webhooks fail closed without secret --------
def test_webhooks_fail_closed_without_secret():
    probes = [
        ("POST", "/api/webhooks/user-created", {"external_id": "qa", "email": "qa@example.com", "name": "QA", "role": "super_admin"}),
        ("POST", "/api/webhooks/user-deleted", {"email": "qa@example.com"}),
        ("POST", "/api/webhooks/contact-created", {"external_id": "qa", "email": "qa@example.com", "name": "QA", "phone": "+15005550100"}),
        ("POST", "/api/webhooks/event", {"event_type": "qa", "payload": {}}),
        ("POST", "/api/webhooks/inventory/add", {"external_id": "qa", "name": "QA", "vin": "QA12345", "year": 2024, "make": "QA", "model": "QA", "price": 1}),
        ("GET", "/api/webhooks/inventory", None),
    ]
    for method, path, body in probes:
        st, _ = call(method, path, body=body)
        assert st == 401, f"{method} {path} no secret -> {st}"
        # wrong secret
        st, _ = call(method, path, body=body, headers={"X-Webhook-Secret": "wrong", "X-API-Key": "wrong"})
        assert st == 401, f"{method} {path} wrong secret -> {st}"
    # inventory endpoints config open
    st, _ = call("GET", "/api/webhooks/inventory/config/endpoints")
    assert st == 200


def test_webhook_cannot_elevate_existing_user_role(mongo):
    """No-secret user-created cannot promote mjeast to super_admin."""
    before = mongo.users.find_one({"email": PLAIN_REP[0]}, {"role": 1})
    call("POST", "/api/webhooks/user-created", body={"external_id": "pwn", "email": PLAIN_REP[0], "name": "pwn", "role": "super_admin"})
    after = mongo.users.find_one({"email": PLAIN_REP[0]}, {"role": 1})
    assert before == after
    assert after["role"] != "super_admin"


# -------- 10. short links need a session --------
def test_short_links_require_session(tokens, mongo):
    v_tok, vid = tokens["victim"]
    b_tok, _ = tokens["rep_b"]
    sa_tok, _ = tokens["sa"]
    # anon
    assert call("POST", "/api/s/create", body={"original_url": "https://example.com", "link_type": "other"})[0] == 401
    assert call("POST", "/api/s/wrap", body={"url": "https://example.com"})[0] == 401
    # rep_b trying to attribute to victim -> 403
    st, _ = call("POST", "/api/s/create", body={"original_url": "https://example.com", "link_type": "other", "user_id": vid}, headers=H(b_tok))
    assert st == 403
    # victim creates own
    st, body = call("POST", "/api/s/create", body={"original_url": "https://example.com/qa", "link_type": "other"}, headers=H(v_tok))
    assert st == 200
    code = body.get("short_code") or (body.get("short_url", "").rstrip("/").split("/")[-1] if body.get("short_url") else None)
    assert code
    # stats anon 401
    assert call("GET", f"/api/s/stats/{code}")[0] == 401
    # stats super admin 200
    st, _ = call("GET", f"/api/s/stats/{code}", headers=H(sa_tok))
    assert st == 200
    # DB attribution
    doc = mongo.short_urls.find_one({"short_code": code})
    assert doc and doc.get("user_id") == vid
    mongo.short_urls.delete_one({"short_code": code})


# -------- 11. unassigned-contacts role gating --------
def test_unassigned_contacts_role_gate(tokens):
    v_tok, _ = tokens["victim"]
    mgr_tok, _ = tokens["mgr"]
    sa_tok, _ = tokens["sa"]
    assert call("GET", "/api/webhooks/unassigned-contacts", headers=H(v_tok))[0] == 403
    assert call("GET", "/api/webhooks/unassigned-contacts", headers=H(mgr_tok))[0] == 200
    assert call("GET", "/api/webhooks/unassigned-contacts", headers=H(sa_tok))[0] == 200


# -------- 12. profile social_links regression --------
def test_profile_social_links_patch(tokens):
    pt_tok, pt_id = tokens["pt"]
    st, _ = call("PUT", f"/api/profile/{pt_id}", body={"social_links": {"instagram": "qa_probe"}}, headers=H(pt_tok))
    assert st == 200, "social_links PUT regressed to 503"
    st, body = call("GET", f"/api/profile/{pt_id}", headers=H(pt_tok))
    assert st == 200
    user = (body or {}).get("user") or {}
    sl = user.get("social_links") or {}
    assert sl.get("instagram") == "qa_probe", sl
    call("PUT", f"/api/profile/{pt_id}", body={"social_links": {"instagram": ""}}, headers=H(pt_tok))


# -------- 13. regression happy-paths --------
def test_regression_happy_paths(tokens):
    for key in ("sa", "mgr", "orga", "victim", "rep_b", "pt", "plain"):
        tok, uid = tokens[key]
        st, body = call("GET", "/api/auth/me", headers=H(tok))
        assert st == 200, (key, st)
        who = (body or {}).get("user") or body
        assert who.get("_id") == uid, (key, who.get("_id"))
    v_tok, vid = tokens["victim"]
    st, _ = call("GET", f"/api/contacts/{vid}", headers=H(v_tok))
    assert st == 200
    st, _ = call("GET", f"/api/notifications/unread-count?user_id={vid}", headers=H(v_tok))
    assert st == 200
    mgr_tok, mgr_id = tokens["mgr"]
    st, body = call("GET", f"/api/chat/leads?user_id={mgr_id}", headers=H(mgr_tok))
    assert st == 200
    assert "conversations" in (body or {})
    st, _ = call("GET", f"/api/admin/team/shared-inboxes?user_id={mgr_id}", headers=H(mgr_tok))
    assert st == 200
    st, _ = call("GET", "/api/inboxes", headers=H(mgr_tok))
    assert st == 200


# -------- 14. congrats public GET returns the two keys --------
def test_congrats_card_public_exposes_linkpage_and_store_slug(mongo, tokens):
    from datetime import datetime, timezone
    _, vid = tokens["victim"]
    card_id = f"qa-hotfix3-card-{uuid.uuid4().hex[:8]}"
    mongo.congrats_cards.insert_one({
        "card_id": card_id, "salesman_id": vid, "customer_name": "QA",
        "customer_phone": "+15005550123", "headline": "QA", "message": "QA",
        "card_type": "congrats", "show_salesman": True, "salesman_name": "QA",
        "created_at": datetime.now(timezone.utc), "views": 0,
    })
    try:
        st, body = call("GET", f"/api/congrats/card/{card_id}")
        assert st == 200
        assert "linkpage_username" in (body or {}), body
        if body.get("store"):
            assert "slug" in body["store"]
        st, body = call("POST", f"/api/congrats/referral-link/{vid}?card_id={card_id}", body={})
        assert st == 200
        assert body.get("short_url")
        # cleanup short_url if created
        from urllib.parse import urlparse
        code = urlparse(body["short_url"]).path.rstrip("/").split("/")[-1]
        if code:
            mongo.short_urls.delete_one({"short_code": code})
        st, _ = call("POST", f"/api/congrats/card/{card_id}/track", body={"action": "share"})
        assert st == 200
    finally:
        mongo.congrats_cards.delete_one({"card_id": card_id})
