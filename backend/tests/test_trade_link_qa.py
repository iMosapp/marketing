"""QA for Customer Trade Link + follow-up tags (iteration 367).

Login-based. Cleans up all appraisals it creates and clears trade-* tags on Sarah.
Mock market provider in preview; suggested ACV ~ $17,800 for Sarah vehicles.
"""
import io
import os
import sys
import time

import pytest
import requests
from dotenv import load_dotenv

sys.path.insert(0, "/app/backend")
sys.path.insert(0, "/app/backend/tests")
load_dotenv("/app/backend/.env")
from _http import API, call, login, auth  # noqa: E402

REP = ("activation-tester@invalid.imonsocial.test", "NewPass123!")
MGR = ("qa-manager@invalid.imonsocial.test", "Manager123!")
OTHER_ORG = ("qa-orgadmin@invalid.imonsocial.test", "OrgAdmin123!")
SARAH = "6aa413008f0d53e3f2261853"
REP_UID = "6a978d68b8673c29063aa8b9"
STORE_ID = "69a0b7095fddcede09591668"
VIN = "2T3DWRFV3LW077677"
TRADE_TAGS = ("trade-appraised", "trade-accepted", "trade-wants-more", "trade-thinking",
              "trade-not-trading", "trade-gap-none", "trade-gap-under-1k", "trade-gap-1k-3k", "trade-gap-3k-plus")


@pytest.fixture(scope="module")
def rep():
    return auth(*login(*REP))


@pytest.fixture(scope="module")
def mgr():
    return auth(*login(*MGR))


@pytest.fixture(scope="module")
def stranger():
    return auth(*login(*OTHER_ORG))


def _jpeg() -> bytes:
    from PIL import Image
    im = Image.new("RGB", (640, 480), (90, 90, 90))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=80)
    return buf.getvalue()


def _del(aid, hdr):
    try:
        call("DELETE", f"/api/appraisals/{aid}", None, hdr)
    except Exception:
        pass


# ============ 1) intake-link mint / dedupe / cross-org 404 ============
def test_intake_link_mint_and_cross_org(rep, stranger):
    st, b = call("POST", "/api/appraisals", {"contact_id": SARAH, "mode": "vehicle_here"}, rep)
    assert st == 200, b
    aid = b["appraisal"]["id"]
    try:
        st, b = call("POST", f"/api/appraisals/{aid}/intake-link", {"channel": "copy"}, rep)
        assert st == 200, b
        it = b["intake"]
        assert "/api/public/trade/" in it["url"]
        assert it["short_url"]
        assert it["expires_at"]
        assert b["appraisal"]["mode"] == "customer_sent"
        assert "intake_token" not in b["appraisal"], "intake_token leaked in appraisal payload"
        # idempotent re-mint
        st2, b2 = call("POST", f"/api/appraisals/{aid}/intake-link", {"channel": "copy"}, rep)
        assert st2 == 200 and b2["intake"]["url"] == it["url"]
        # cross-org 404
        st3, _ = call("POST", f"/api/appraisals/{aid}/intake-link", {"channel": "copy"}, stranger)
        assert st3 == 404
    finally:
        _del(aid, rep)


# ============ 2) public page submit (end-to-end) ============
@pytest.fixture(scope="module")
def submitted(rep):
    """Create an appraisal, mint link, customer submits with VIN+mileage+photo. Yields appraisal id + token."""
    st, b = call("POST", "/api/appraisals", {"contact_id": SARAH, "mode": "vehicle_here"}, rep)
    assert st == 200
    aid = b["appraisal"]["id"]
    st, b = call("POST", f"/api/appraisals/{aid}/intake-link", {"channel": "copy"}, rep)
    assert st == 200
    token = b["intake"]["url"].rsplit("/", 1)[1]
    # upload a VIN sticker photo
    r = requests.post(f"{API}/api/public/trade/{token}/photo",
                      data={"role": "vin_sticker"},
                      files={"file": ("vin.jpg", _jpeg(), "image/jpeg")})
    assert r.status_code == 200, r.text
    # customer submits
    body = {"vin": VIN, "mileage": "61200", "zip": "84070",
            "condition": {"overall": "good", "accidents": "no", "warning_lights": "no", "tires": "ok", "smoke": "no", "keys": "2"},
            "notes": "Timing belt recent", "wants": "32000"}
    r = requests.post(f"{API}/api/public/trade/{token}/submit", json=body)
    assert r.status_code == 200, r.text
    yield {"aid": aid, "token": token}
    _del(aid, auth(*login(*REP)))


def test_public_page_html_and_context(submitted):
    token = submitted["token"]
    r = requests.get(f"{API}/api/public/trade/{token}")
    assert r.status_code == 200
    # After submit it should show thank-you
    assert "Sent to" in r.text or "sent" in r.text.lower()
    assert "Bearer" not in r.text
    ctx = requests.get(f"{API}/api/public/trade/{token}/context").json()
    assert ctx["state"] == "open"
    assert ctx.get("submitted") is True
    photos = ctx.get("photos")
    pc = ctx.get("photo_count", 0)
    if isinstance(photos, list):
        assert len(photos) >= 1 or pc >= 1
    else:
        assert pc >= 1 or (isinstance(photos, int) and photos >= 1)
    for forbidden in ("suggested_acv", "approved_value", "user_id", "contact_id"):
        assert forbidden not in ctx, f"leaked {forbidden}"
    # bogus token
    assert requests.get(f"{API}/api/public/trade/this-token-xx-404").status_code == 404


def test_appraisal_reflects_customer_submission(submitted, rep):
    aid = submitted["aid"]
    st, a = call("GET", f"/api/appraisals/{aid}", None, rep)
    assert st == 200
    assert a["vin"] == VIN
    assert a.get("vehicle", {}).get("make") == "Toyota"
    assert a["step"] == "mileage"
    assert a["mileage_confirmed"] is None
    ci = a["customer_intake"]
    assert ci["mileage"] == 61200
    assert ci["zip"] == "84070"
    assert ci["notes"]
    assert ci["wants"] == 32000
    actions = {x["action"] for x in a.get("activity") or []}
    assert "intake_link_created" in actions
    assert "customer_intake" in actions


# ============ 3) rep stepper flow: confirm mileage then revoke ============
def test_odometer_confirm_customer_reported(submitted, rep):
    aid = submitted["aid"]
    st, b = call("POST", f"/api/appraisals/{aid}/mileage",
                 {"confirmed": 61200, "source": "customer_reported"}, rep)
    assert st == 200, b
    st, a = call("GET", f"/api/appraisals/{aid}", None, rep)
    assert a.get("mileage_confirmed") == 61200


def test_revoke_returns_410_on_public(submitted, rep):
    token = submitted["token"]
    st, b = call("DELETE", f"/api/appraisals/{submitted['aid']}/intake-link", None, rep)
    assert st == 200, b
    assert b["intake"].get("revoked_at")
    r = requests.get(f"{API}/api/public/trade/{token}")
    assert r.status_code == 410


# ============ 4) campaign-options tags ============
def test_campaign_options_contains_trade_tags(mgr):
    st, b = call("GET", "/api/appraisals/campaign-options", None, mgr)
    assert st == 200, b
    keys = set((b.get("tags") or {}).keys()) if isinstance(b.get("tags"), dict) else set(b.get("tags") or [])
    for t in TRADE_TAGS:
        assert t in keys, f"missing {t} in campaign-options.tags: {keys}"


# ============ 5) tags end-to-end (approve -> present -> outcome wants_more) ============
def _strip_trade_tags(hdr):
    st, c = call("GET", f"/api/contacts/{REP_UID}/{SARAH}", None, hdr)
    if st != 200:
        return
    tags = [t for t in (c.get("tags") or []) if not str(t).startswith("trade-")]
    call("PATCH", f"/api/contacts/{REP_UID}/{SARAH}/tags", {"tags": tags}, hdr)


def test_full_outcome_wants_more_tags(rep, mgr):
    _strip_trade_tags(rep)
    # New appraisal + link + submit (expected 32000, suggested mock ~ -> gap-3k-plus)
    st, b = call("POST", "/api/appraisals", {"contact_id": SARAH, "mode": "vehicle_here"}, rep)
    aid = b["appraisal"]["id"]
    try:
        st, b = call("POST", f"/api/appraisals/{aid}/intake-link", {"channel": "copy"}, rep)
        token = b["intake"]["url"].rsplit("/", 1)[1]
        requests.post(f"{API}/api/public/trade/{token}/photo",
                      data={"role": "vin_sticker"},
                      files={"file": ("vin.jpg", _jpeg(), "image/jpeg")})
        r = requests.post(f"{API}/api/public/trade/{token}/submit", json={
            "vin": VIN, "mileage": "61200", "zip": "84070",
            "condition": {"overall": "good", "accidents": "no", "warning_lights": "no", "tires": "ok", "smoke": "no", "keys": "2"},
            "notes": "n", "wants": "32000"})
        assert r.status_code == 200
        # Confirm mileage
        st, b = call("POST", f"/api/appraisals/{aid}/mileage",
                     {"confirmed": 61200, "source": "customer_reported"}, rep)
        assert st == 200, b
        # Market refresh (mock)
        time.sleep(1)
        st, b = call("POST", f"/api/appraisals/{aid}/market/refresh", {"zip": "84070"}, rep)
        if st == 429:
            time.sleep(12)
            st, b = call("POST", f"/api/appraisals/{aid}/market/refresh", {"zip": "84070"}, rep)
        assert st == 200, b
        # record expectation
        st, b = call("POST", f"/api/appraisals/{aid}/expectation", {"asked": True, "value": 32000}, rep)
        assert st == 200, b
        # submit for review
        st, b = call("POST", f"/api/appraisals/{aid}/submit", {}, rep)
        assert st == 200, b
        # approve (manager) -> /decide {action:'approve'}
        st, b = call("POST", f"/api/appraisals/{aid}/decide", {"action": "approve"}, mgr)
        assert st == 200, b
        # present (rep)
        st, b = call("POST", f"/api/appraisals/{aid}/present", {}, rep)
        assert st == 200, b
        # outcome wants_more
        st, b = call("POST", f"/api/appraisals/{aid}/outcome", {"outcome": "wants_more", "expected_value": 32000}, rep)
        assert st == 200, b
        # Check contact tags
        st, c = call("GET", f"/api/contacts/{REP_UID}/{SARAH}", None, rep)
        assert st == 200, c
        tags = set(c.get("tags") or [])
        assert "trade-appraised" in tags, tags
        assert "trade-wants-more" in tags, tags
        gap_bucket = {"trade-gap-none", "trade-gap-under-1k", "trade-gap-1k-3k", "trade-gap-3k-plus"} & tags
        assert len(gap_bucket) == 1, f"expected exactly one gap bucket, got {gap_bucket}"
        assert "trade-gap-3k-plus" in tags, f"expected 3k-plus with wants=32k vs suggested~17.8k: {tags}"
        assert "trade-thinking" not in tags
        assert "trade-accepted" not in tags
        # activity has follow_up_tagged
        st, a = call("GET", f"/api/appraisals/{aid}", None, rep)
        actions = {x["action"] for x in a.get("activity") or []}
        assert "follow_up_tagged" in actions, actions
    finally:
        _del(aid, rep)


def test_second_appraisal_replaces_outcome_tag_to_thinking(rep, mgr):
    # (leftover tags from the previous test: trade-appraised + trade-wants-more + gap bucket)
    st, b = call("POST", "/api/appraisals", {"contact_id": SARAH, "mode": "vehicle_here"}, rep)
    aid = b["appraisal"]["id"]
    try:
        st, b = call("POST", f"/api/appraisals/{aid}/intake-link", {"channel": "copy"}, rep)
        token = b["intake"]["url"].rsplit("/", 1)[1]
        requests.post(f"{API}/api/public/trade/{token}/photo",
                      data={"role": "vin_sticker"},
                      files={"file": ("vin.jpg", _jpeg(), "image/jpeg")})
        requests.post(f"{API}/api/public/trade/{token}/submit", json={
            "vin": VIN, "mileage": "61200", "zip": "84070",
            "condition": {"overall": "good", "accidents": "no", "warning_lights": "no", "tires": "ok", "smoke": "no", "keys": "2"}})
        call("POST", f"/api/appraisals/{aid}/mileage",
             {"confirmed": 61200, "source": "customer_reported"}, rep)
        time.sleep(12)
        call("POST", f"/api/appraisals/{aid}/market/refresh", {"zip": "84070"}, rep)
        call("POST", f"/api/appraisals/{aid}/expectation", {"asked": False}, rep)
        call("POST", f"/api/appraisals/{aid}/submit", {}, rep)
        call("POST", f"/api/appraisals/{aid}/decide", {"action": "approve"}, mgr)
        call("POST", f"/api/appraisals/{aid}/present", {}, rep)
        st, b = call("POST", f"/api/appraisals/{aid}/outcome", {"outcome": "thinking"}, rep)
        assert st == 200, b
        st, c = call("GET", f"/api/contacts/{REP_UID}/{SARAH}", None, rep)
        tags = set(c.get("tags") or [])
        assert "trade-thinking" in tags, tags
        assert "trade-wants-more" not in tags, "previous outcome tag should be replaced"
        assert "trade-appraised" in tags
    finally:
        _del(aid, rep)


# ============ 6) rules follow_up.gap_tags toggle persists ============
def test_rules_gap_tags_toggle_persists(mgr):
    # read current effective
    st, r0 = call("GET", "/api/appraisals/rules", None, mgr)
    assert st == 200
    before = (r0.get("effective", {}).get("rules", {}).get("follow_up", {}) or {}).get("gap_tags")
    # Flip and save at store scope
    new_val = not bool(before)
    body = {"scope": "store", "store_id": STORE_ID,
            "rules": {"follow_up": {"tag_on_outcome": True, "gap_tags": new_val}}}
    st, b = call("PUT", "/api/appraisals/rules", body, mgr)
    assert st == 200, b
    # verify persist via PUT response (store-scoped)
    saved = (b.get("effective", {}).get("rules", {}).get("follow_up", {}) or {}).get("gap_tags")
    assert saved == new_val, f"saved={saved} new_val={new_val} full={b.get('effective',{}).get('rules',{}).get('follow_up')}"
    # cleanup
    st, _ = call("DELETE", f"/api/appraisals/rules/store/{STORE_ID}", None, mgr)
    assert st in (200, 204)


# ============ 7) cleanup trade-* tags on Sarah ============
def test_cleanup_trade_tags_on_sarah(rep):
    st, c = call("GET", f"/api/contacts/{REP_UID}/{SARAH}", None, rep)
    assert st == 200
    tags = [t for t in (c.get("tags") or []) if not t.startswith("trade-")]
    st, b = call("PATCH", f"/api/contacts/{REP_UID}/{SARAH}/tags", {"tags": tags}, rep)
    assert st == 200, b
