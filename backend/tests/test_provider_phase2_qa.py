"""Preview QA for Market Data Provider Phase 2 (iteration ~366).

Covers:
- GET /api/appraisals/providers (manager vs rep)
- POST /api/appraisals/providers/compare (super_admin, manager, rep, missing zip)
- GET /api/appraisals/providers/comparisons (super_admin, other-org admin, rep)
- Rules round-trip for `market` section (valid update, invalid payloads, restore)
- Appraisal-level compare gating (/{id}/market and /{id}/market/compare)

No live provider keys are expected in preview, so compare endpoints must return 503
rather than 500 or fake numbers. Credentials/key substrings must not leak.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))
from _http import call, login, auth  # noqa: E402


REP = ("activation-tester@invalid.imonsocial.test", "NewPass123!")
MANAGER = ("qa-manager@invalid.imonsocial.test", "Manager123!")
ORGADMIN = ("qa-orgadmin@invalid.imonsocial.test", "OrgAdmin123!")
SUPER = ("forest@imosapp.com", "Admin123!")

STORE_ID = "69a0b7095fddcede09591668"
SARAH_CONTACT_ID = "6aa413008f0d53e3f2261853"
BANNED_SUBSTRINGS = ("api_key", "MARKETCHECK_API_KEY", "VINAUDIT_API_KEY")


@pytest.fixture(scope="module")
def rep():
    return auth(*login(*REP))


@pytest.fixture(scope="module")
def manager():
    return auth(*login(*MANAGER))


@pytest.fixture(scope="module")
def orgadmin():
    return auth(*login(*ORGADMIN))


@pytest.fixture(scope="module")
def forest():
    return auth(*login(*SUPER))


# ------- GET /api/appraisals/providers -------

def test_providers_summary_as_manager(manager):
    st, b = call("GET", "/api/appraisals/providers", None, manager)
    assert st == 200, (st, b)
    raw = json.dumps(b)
    for needle in BANNED_SUBSTRINGS:
        assert needle not in raw, f"leaked substring {needle!r}"
    names = {p["name"]: p for p in b["market"]}
    assert {"marketcheck", "vinaudit", "mock"} <= set(names)
    assert names["marketcheck"]["live"] is True
    assert names["vinaudit"]["live"] is True
    assert names["vinaudit"].get("comps_kind") == "sales records"
    assert sum(1 for p in b["market"] if p.get("active")) == 1
    assert names["mock"]["active"] is True
    usage_all = b.get("usage_all") or []
    assert len(usage_all) == 2
    for row in usage_all:
        for k in ("calls", "cap", "comparisons", "failures"):
            assert k in row, (row, k)
    assert b["market_rules"]["primary"] == "marketcheck"
    assert b.get("dev_market_allowed") is True


def test_providers_summary_rep_forbidden(rep):
    st, _ = call("GET", "/api/appraisals/providers", None, rep)
    assert st == 403


# ------- POST /api/appraisals/providers/compare -------

def test_compare_adhoc_super_admin_503(forest):
    st, b = call(
        "POST", "/api/appraisals/providers/compare",
        {"vin": "2T3DWRFV3LW077677", "mileage": 76189, "zip": "80215"}, forest,
    )
    assert st == 503, (st, b)
    assert "live" in str(b).lower() or "key" in str(b).lower()
    assert all(n not in str(b) for n in BANNED_SUBSTRINGS)


def test_compare_adhoc_manager_forbidden(manager):
    st, _ = call(
        "POST", "/api/appraisals/providers/compare",
        {"vin": "2T3DWRFV3LW077677", "mileage": 76189, "zip": "80215"}, manager,
    )
    assert st == 403


def test_compare_adhoc_rep_forbidden(rep):
    st, _ = call(
        "POST", "/api/appraisals/providers/compare",
        {"vin": "2T3DWRFV3LW077677", "mileage": 76189, "zip": "80215"}, rep,
    )
    assert st == 403


def test_compare_adhoc_missing_zip(forest):
    st, b = call(
        "POST", "/api/appraisals/providers/compare",
        {"vin": "2T3DWRFV3LW077677", "mileage": 76189}, forest,
    )
    assert st in (400, 503), (st, b)
    assert st != 500


# ------- GET /api/appraisals/providers/comparisons -------

def test_comparisons_list_super_admin(forest):
    st, b = call("GET", "/api/appraisals/providers/comparisons", None, forest)
    assert st == 200, (st, b)
    assert isinstance(b, dict) and "comparisons" in b
    assert isinstance(b["comparisons"], list)


def test_comparisons_list_other_org_admin(orgadmin):
    st, b = call("GET", "/api/appraisals/providers/comparisons", None, orgadmin)
    assert st == 200
    assert b.get("comparisons") == [] or isinstance(b.get("comparisons"), list)


def test_comparisons_list_rep_forbidden(rep):
    st, _ = call("GET", "/api/appraisals/providers/comparisons", None, rep)
    assert st == 403


# ------- Rules market section round-trip -------

def test_rules_market_options(manager):
    st, b = call("GET", "/api/appraisals/rules", None, manager)
    assert st == 200
    opts = b.get("options", {})
    mp = opts.get("market_providers", {})
    assert isinstance(mp, dict)
    assert "marketcheck" in mp and "vinaudit" in mp
    for v in ("marketcheck", "vinaudit"):
        for k in ("label", "hint", "configured"):
            assert k in mp[v], (v, k)
        assert mp[v]["configured"] is False
    eff = b["effective"]["rules"]
    assert "market" in eff
    for k in ("primary", "fallback", "comparison"):
        assert k in eff["market"]


def test_rules_market_invalid_primary(manager):
    st, b = call("GET", "/api/appraisals/rules", None, manager)
    assert st == 200
    base = b["effective"]["rules"]
    body = {"scope": "store", "store_id": STORE_ID, "rules": {**base, "market": {"primary": "kbb", "fallback": "none", "comparison": False}}}
    st, _ = call("PUT", "/api/appraisals/rules", body, manager)
    assert st == 400


def test_rules_market_invalid_fallback_equals_primary(manager):
    body = {"scope": "store", "store_id": STORE_ID, "rules": {"market": {"primary": "marketcheck", "fallback": "marketcheck", "comparison": False}}}
    st, _ = call("PUT", "/api/appraisals/rules", body, manager)
    assert st == 400


def test_rules_market_invalid_fallback_mock(manager):
    body = {"scope": "store", "store_id": STORE_ID, "rules": {"market": {"primary": "marketcheck", "fallback": "mock", "comparison": False}}}
    st, _ = call("PUT", "/api/appraisals/rules", body, manager)
    assert st == 400


def test_rules_market_valid_update_and_restore(manager):
    st, b = call("GET", "/api/appraisals/rules", None, manager)
    assert st == 200
    base = b["effective"]["rules"]
    body = {"scope": "store", "store_id": STORE_ID, "rules": {**base, "market": {"primary": "marketcheck", "fallback": "vinaudit", "comparison": True}}}
    st, b2 = call("PUT", "/api/appraisals/rules", body, manager)
    assert st == 200, (st, b2)
    m = b2["effective"]["rules"]["market"]
    assert m["primary"] == "marketcheck"
    assert m["fallback"] == "vinaudit"
    assert m["comparison"] is True
    # restore
    st, _ = call("DELETE", f"/api/appraisals/rules/store/{STORE_ID}", None, manager)
    assert st in (200, 204)
    st, b3 = call("GET", "/api/appraisals/rules", None, manager)
    m3 = b3["effective"]["rules"]["market"]
    assert m3["fallback"] == "none"
    assert m3["comparison"] is False


# ------- Appraisal-level compare gating -------

@pytest.fixture()
def rep_draft(rep):
    """Create a draft appraisal for the rep. Yields appraisal_id. Deletes on teardown."""
    st, b = call("POST", "/api/appraisals", {"contact_id": SARAH_CONTACT_ID, "mode": "vehicle_here"}, rep)
    assert st in (200, 201), (st, b)
    appr = b.get("appraisal") if isinstance(b, dict) else None
    aid = (appr or {}).get("_id") or (appr or {}).get("id") or (b.get("_id") if isinstance(b, dict) else None)
    assert aid, b
    st, _ = call("POST", f"/api/appraisals/{aid}/vehicle",
                 {"manual": {"year": 2019, "make": "Ford", "model": "F-150", "trim": "XLT"},
                  "method": "manual_vehicle"}, rep)
    assert st in (200, 201)
    st, _ = call("POST", f"/api/appraisals/{aid}/mileage",
                 {"confirmed": 61200, "source": "manual"}, rep)
    assert st in (200, 201)
    yield aid
    call("DELETE", f"/api/appraisals/{aid}", None, rep)


def test_appraisal_market_defaults_rep(rep, rep_draft):
    st, b = call("GET", f"/api/appraisals/{rep_draft}/market", None, rep)
    assert st == 200, (st, b)
    assert b.get("comparison", {}).get("allowed") is False
    assert b.get("comparison", {}).get("latest") in (None, {})
    prov = b.get("provider", {})
    assert prov.get("fallback") in (None, "none")
    assert prov.get("name") == "mock"


def test_appraisal_compare_rep_forbidden(rep, rep_draft):
    st, _ = call("POST", f"/api/appraisals/{rep_draft}/market/compare", {}, rep)
    assert st == 403


def test_appraisal_compare_forest_rule_off(forest, rep_draft):
    st, b = call("POST", f"/api/appraisals/{rep_draft}/market/compare", {}, forest)
    assert st == 403, (st, b)
    assert "switched off" in str(b).lower() or "off" in str(b).lower() or "disabled" in str(b).lower()


def test_appraisal_compare_other_org_admin_not_found(orgadmin, rep_draft):
    st, _ = call("POST", f"/api/appraisals/{rep_draft}/market/compare", {}, orgadmin)
    assert st == 404


def test_appraisal_compare_forest_rule_on_503(manager, forest, rep_draft):
    """With comparison rule ON, super admin should hit 503 (no live keys), not 403."""
    # Enable the store override
    st, b = call("GET", "/api/appraisals/rules", None, manager)
    base = b["effective"]["rules"]
    put = {"scope": "store", "store_id": STORE_ID, "rules": {**base, "market": {"primary": "marketcheck", "fallback": "none", "comparison": True}}}
    st, _ = call("PUT", "/api/appraisals/rules", put, manager)
    assert st == 200
    try:
        st, b2 = call("POST", f"/api/appraisals/{rep_draft}/market/compare", {}, forest)
        assert st == 503, (st, b2)
    finally:
        call("DELETE", f"/api/appraisals/rules/store/{STORE_ID}", None, manager)


def test_appraisal_market_refresh_mock(rep, rep_draft):
    st, b = call("POST", f"/api/appraisals/{rep_draft}/market/refresh",
                 {"zip": "84070", "radius": 100}, rep)
    assert st == 200, (st, b)
    snap = b.get("snapshot") or b
    assert snap.get("live") is False
    assert "DEVELOPMENT DATA" in (snap.get("badge") or "")
    assert snap.get("purpose") == "appraisal"
    assert snap.get("fallback_from") in (None, "")
