"""Regression tests for the June 2026 security audit fixes:
identity binding (X-User-ID must match the Bearer token), /api/admin/* auth gate,
role/scope checks on formerly open admin routes, ?user_id= binding, SSRF guard, widget abuse caps."""
import asyncio
import os
import sys

import pytest
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/124 Safari/537.36"}
STORE = "69a0b7095fddcede09591668"


def _login(email, pw):
    r = requests.post(f"{BASE}/api/auth/login", json={"email": email, "password": pw}, headers=UA, timeout=20)
    r.raise_for_status()
    d = r.json()
    return d["token"], d["user"]["_id"]


@pytest.fixture(scope="module")
def who():
    sa = _login("forest@imosapp.com", "Admin123!")
    mg = _login("qa-manager@invalid.imonsocial.test", "Manager123!")
    us = _login("mjeast1985@gmail.com", "NavyBean1!")
    return {"sa": sa, "mg": mg, "us": us}


def _h(tok=None, uid=None):
    h = dict(UA)
    if tok:
        h["Authorization"] = f"Bearer {tok}"
    if uid:
        h["X-User-ID"] = uid
    return h


def _get(path, **kw):
    return requests.get(f"{BASE}{path}", timeout=25, **kw)


# ---------------- identity binding

def test_header_alone_is_rejected(who):
    assert _get("/api/admin/search?q=fo", headers=_h(uid=who["sa"][1])).status_code == 401


def test_header_must_match_token(who):
    r = _get("/api/admin/search?q=fo", headers=_h(who["us"][0], who["sa"][1]))
    assert r.status_code == 401


def test_token_only_is_enough_for_admin(who):
    assert _get("/api/admin/search?q=fo", headers=_h(who["sa"][0])).status_code == 200


def test_impersonation_token_binds_to_impersonated_user(who):
    sa_tok, sa_id = who["sa"]
    us_id = who["us"][1]
    r = requests.post(f"{BASE}/api/admin/users/{us_id}/impersonate", json={}, headers=_h(sa_tok, sa_id), timeout=25)
    assert r.status_code == 200, r.text
    tok = r.json()["token"]
    assert _get(f"/api/users/{us_id}", headers=_h(tok, us_id)).status_code == 200
    assert _get("/api/admin/search?q=fo", headers=_h(tok, sa_id)).status_code == 401


# ---------------- /api/admin gate + formerly open routes

@pytest.mark.parametrize("method,path", [
    ("PUT", f"/api/admin/stores/{STORE}"),
    ("GET", f"/api/admin/stores/{STORE}/review-links"),
    ("GET", "/api/admin/billing/mrr"),
    ("GET", "/api/admin/partners"),
    ("GET", "/api/admin/pending-users"),
    ("GET", "/api/admin/stats"),
    ("POST", "/api/admin/deduplicate-campaigns"),
    ("POST", "/api/admin/seed/backfill-all"),
    ("GET", f"/api/admin/hierarchy/store/{STORE}"),
])
def test_admin_routes_need_a_login(method, path):
    r = requests.request(method, f"{BASE}{path}", json={"name": "x"}, headers=UA, timeout=25)
    assert r.status_code == 401, (path, r.status_code, r.text[:100])


@pytest.mark.parametrize("method,path", [
    ("GET", "/api/admin/billing/mrr"),
    ("GET", "/api/admin/partners"),
    ("GET", "/api/admin/pending-users"),
    ("GET", "/api/admin/stats"),
    ("PUT", f"/api/admin/stores/{STORE}"),
    ("PUT", f"/api/admin/stores/{STORE}/review-links"),
    ("GET", f"/api/admin/stores/{STORE}/campaign-settings"),
    ("POST", "/api/admin/deduplicate-campaigns"),
    ("GET", f"/api/admin/hierarchy/store/{STORE}"),
])
def test_plain_rep_is_forbidden(who, method, path):
    tok, uid = who["us"]
    r = requests.request(method, f"{BASE}{path}", json={"name": "x"}, headers=_h(tok, uid), timeout=25)
    assert r.status_code == 403, (path, r.status_code, r.text[:100])


def test_manager_cannot_see_platform_billing(who):
    tok, uid = who["mg"]
    assert _get("/api/admin/billing/mrr", headers=_h(tok, uid)).status_code == 403


@pytest.mark.parametrize("path", [
    f"/api/admin/stores/{STORE}",
    f"/api/admin/stores/{STORE}/review-links",
    f"/api/admin/stores/{STORE}/campaign-settings",
    f"/api/admin/hierarchy/store/{STORE}",
    "/api/admin/stats",
])
def test_manager_keeps_store_access(who, path):
    tok, uid = who["mg"]
    assert _get(path, headers=_h(tok, uid)).status_code == 200, path


def test_query_user_id_must_be_the_caller(who):
    us_tok, us_id = who["us"]
    sa_id = who["sa"][1]
    assert _get(f"/api/admin/team/shared-inboxes?user_id={sa_id}", headers=_h(us_tok, us_id)).status_code == 403
    mg_tok, mg_id = who["mg"]
    assert _get(f"/api/admin/team/shared-inboxes?user_id={mg_id}", headers=_h(mg_tok, mg_id)).status_code == 200


def test_rep_can_read_own_store_review_links(who):
    tok, uid = who["us"]
    assert _get(f"/api/admin/users/{uid}/store-review-links", headers=_h(tok, uid)).status_code == 200


def test_public_admin_allowlist_still_open():
    assert _get("/api/admin/partners/by-slug/does-not-exist", headers=UA).status_code == 404


# ---------------- SSRF guard

def test_ssrf_guard_blocks_private_targets():
    from services.safe_fetch import assert_public_url, UnsafeURL

    async def run():
        for u in ["http://169.254.169.254/latest/meta-data/", "http://localhost:8001/api/health", "http://10.0.0.5/",
                  "http://[::1]/", "http://metadata.google.internal/", "http://backend.default.svc/"]:
            with pytest.raises(UnsafeURL):
                await assert_public_url(u)
        await assert_public_url("https://www.imonsocial.com/")

    asyncio.run(run())


# ---------------- widget abuse caps + origin check

def test_widget_domain_check_uses_origin():
    from services import widgets as W
    w = {"domains": ["imonsocial.com"]}
    assert W.domain_ok(w, "https://www.imonsocial.com/x")
    assert not W.domain_ok(w, "https://www.imonsocial.com/x", "https://evil.example.com")
    assert not W.domain_ok(w, "https://evil.example.com/x", "https://www.imonsocial.com")
    assert W.domain_ok({"domains": []}, "https://anything.example.com/")


def test_widget_daily_phone_cap():
    from services import widgets as W
    W._hits.pop("lead_phone_day:+15005550099", None)
    results = [W.allow("+15005550099", "lead_phone_day", W.DAILY_PER_PHONE, 86400) for _ in range(W.DAILY_PER_PHONE + 2)]
    assert results[:W.DAILY_PER_PHONE] == [True] * W.DAILY_PER_PHONE and results[-2:] == [False, False]
