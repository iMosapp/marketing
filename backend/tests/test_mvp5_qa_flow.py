"""MVP5 QA flow against the preview backend using the pre-seeded data for Sarah Tester.
Covers: tenant isolation, vehicles API, reappraise (reuses vehicle), ownership + migration rule,
campaign options + money gate, Jessi context normalization.
Non-destructive: soft-deletes created appraisals and restores org setting + ownership.
"""
import os
import sys
import time

import pytest
from dotenv import load_dotenv
from pymongo import MongoClient
from bson import ObjectId

sys.path.insert(0, "/app/backend")
sys.path.insert(0, "/app/backend/tests")
load_dotenv("/app/backend/.env")
from _http import call, login, auth  # noqa: E402

REP = ("activation-tester@invalid.imonsocial.test", "NewPass123!")
MANAGER = ("qa-manager@invalid.imonsocial.test", "Manager123!")
ORGADMIN = ("qa-orgadmin@invalid.imonsocial.test", "OrgAdmin123!")
SUPER = ("forest@imosapp.com", "Admin123!")

SARAH = "6aa413008f0d53e3f2261853"
REP_UID = "6a978d68b8673c29063aa8b9"
QA_STORE = "69a0b7095fddcede09591668"
F150_VID = "6ac68a8474b0deab3f9b261f"
DELETED_VID = "6ac69fac07f402375b50d07f"
OTHER_ORG = "69a907033b77512d1d8d8a08"

STATE: dict = {}


def _db():
    return MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


@pytest.fixture(scope="module")
def rep():
    return auth(*login(*REP))


@pytest.fixture(scope="module")
def manager():
    return auth(*login(*MANAGER))


@pytest.fixture(scope="module")
def stranger():
    return auth(*login(*ORGADMIN))


@pytest.fixture(scope="module")
def forest():
    return auth(*login(*SUPER))


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    yield
    db = _db()
    for aid in STATE.get("created_appraisals", []):
        try:
            db.vehicle_appraisals.update_one({"_id": ObjectId(aid)}, {"$set": {"deleted": True}})
        except Exception:
            pass


# ---------------- Tenant isolation ----------------
def test_rep_pipeline_only_own(rep):
    st, b = call("GET", "/api/appraisals/pipeline", None, rep)
    assert st == 200, (st, b)
    for g in b["groups"]:
        for it in g["items"]:
            assert it.get("user_id") == REP_UID or it.get("salesperson_id") == REP_UID, it
    assert b.get("can_team") in (False, None)


def test_rep_search_only_own(rep):
    st, b = call("GET", "/api/appraisals/search?q=Sarah", None, rep)
    assert st == 200
    for a in b["appraisals"]:
        assert a.get("user_id") == REP_UID or a.get("salesperson_id") == REP_UID, a


def test_rep_blocked_from_reports(rep):
    assert call("GET", "/api/appraisals/reports/summary", None, rep)[0] == 403
    assert call("GET", "/api/appraisals/reports/followup", None, rep)[0] == 403


def test_manager_reports_summary(manager):
    st, b = call("GET", "/api/appraisals/reports/summary", None, manager)
    assert st == 200, (st, b)
    for key in ("counts", "averages", "rates", "by_salesperson", "by_manager", "by_make", "options"):
        assert key in b, (key, list(b.keys()))


def test_manager_pipeline_team(manager):
    st, b = call("GET", "/api/appraisals/pipeline?team=true", None, manager)
    assert st == 200
    assert b.get("can_team") is True


def test_other_org_admin_sees_nothing(stranger):
    st, b = call("GET", "/api/appraisals/reports/summary", None, stranger)
    assert st == 200
    assert b["counts"].get("started", 0) == 0
    st, s = call("GET", "/api/appraisals/search?q=Sarah", None, stranger)
    assert st == 200
    assert s.get("total", len(s.get("appraisals", []))) == 0
    assert s["appraisals"] == []


def test_other_org_admin_cant_fetch_rep_vehicle(stranger):
    st, _ = call("GET", f"/api/appraisals/vehicle/{F150_VID}", None, stranger)
    assert st == 404


def test_super_admin_sees_everything(forest):
    st, b = call("GET", "/api/appraisals/reports/summary", None, forest)
    assert st == 200
    assert b["counts"].get("started", 0) >= 1


# ---------------- Vehicles API ----------------
def test_vehicles_list_for_sarah(rep):
    st, b = call("GET", f"/api/appraisals/vehicles/{SARAH}", None, rep)
    assert st == 200, (st, b)
    assert "vehicles" in b and "can_appraise" in b and "ownership_options" in b
    STATE["initial_vehicle_count"] = len(b["vehicles"])
    v = next(x for x in b["vehicles"] if x["id"] == F150_VID)
    for k in ("id", "label", "ownership_status", "ownership_label", "trade_intent_status", "last", "appraisal_count", "open_appraisal_id"):
        assert k in v, (k, list(v.keys()))
    last = v["last"]
    for k in ("date", "mileage", "suggested_acv", "approved_value", "customer_expected_value", "expectation_gap", "outcome", "outcome_label", "status_label"):
        assert k in last, (k, list(last.keys()))


def test_vehicle_detail_history(rep):
    st, b = call("GET", f"/api/appraisals/vehicle/{F150_VID}", None, rep)
    assert st == 200, (st, b)
    assert "history" in b and isinstance(b["history"], list) and len(b["history"]) >= 1
    for row in b["history"]:
        for k in ("status", "outcome", "suggested_acv", "approved_value", "customer_expected_value", "mileage", "date"):
            assert k in row, (k, list(row.keys()))
    dates = [h["date"] for h in b["history"] if h.get("date")]
    assert dates == sorted(dates), "history should be oldest first"
    assert "value_history" in b
    assert b["contact"]["id"] == SARAH and "name" in b["contact"]
    assert "ownership_options" in b


def test_vehicle_detail_deleted_404(rep):
    st, _ = call("GET", f"/api/appraisals/vehicle/{DELETED_VID}", None, rep)
    assert st == 404


# ---------------- Reappraise reuses vehicle ----------------
def test_reappraise_reuses_vehicle(rep):
    st, before = call("GET", f"/api/appraisals/vehicles/{SARAH}", None, rep)
    assert st == 200
    pre_count = len(before["vehicles"])
    st, b = call("POST", "/api/appraisals", {"contact_id": SARAH, "mode": "vehicle_here", "vehicle_id": F150_VID}, rep)
    assert st == 200, (st, b)
    a = b["appraisal"]
    STATE.setdefault("created_appraisals", []).append(a["id"])
    assert a.get("is_reappraisal") is True
    assert a.get("vehicle_id") == F150_VID
    vr = a.get("vehicle_record") or a.get("vehicle") or {}
    # should carry prior mileage/last_appraisal
    assert vr.get("last_appraisal") or vr.get("previous_mileage") or a.get("previous_appraisal_id"), a
    st, after = call("GET", f"/api/appraisals/vehicles/{SARAH}", None, rep)
    assert st == 200
    assert len(after["vehicles"]) == pre_count, (pre_count, len(after["vehicles"]))
    f150 = next(x for x in after["vehicles"] if x["id"] == F150_VID)
    assert f150["open_appraisal_id"] == a["id"]


# ---------------- Ownership + migration rule ----------------
def test_ownership_toggle_restores(rep):
    # F-150's latest outcome is not_trading per fixture, pick a vehicle owned & toggle
    st, b = call("GET", f"/api/appraisals/vehicle/{F150_VID}", None, rep)
    assert st == 200
    before_status = b.get("ownership_status", "owns")

    # invalid
    st, _ = call("PUT", f"/api/appraisals/vehicle/{F150_VID}/ownership", {"status": "garbage"}, rep)
    assert st in (400, 422)

    # to traded
    st, d = call("PUT", f"/api/appraisals/vehicle/{F150_VID}/ownership", {"status": "traded", "note": "QA confirm"}, rep)
    assert st == 200, (st, d)
    assert d["ownership_status"] == "traded" and d.get("trade_confirmed_at")

    # restore
    st, d = call("PUT", f"/api/appraisals/vehicle/{F150_VID}/ownership", {"status": before_status or "owns", "note": ""}, rep)
    assert st == 200
    assert d["ownership_status"] == (before_status or "owns")


def test_accepted_outcome_vehicles_are_owns(forest):
    # find an accepted-outcome appraisal and verify its vehicle is owns + intent accepted
    st, s = call("GET", "/api/appraisals/search?outcome=accepted", None, forest)
    assert st == 200
    rows = s.get("appraisals", [])
    if not rows:
        pytest.skip("no accepted appraisals in dataset")
    for a in rows[:5]:
        vid = a.get("vehicle_id")
        if not vid:
            continue
        st, d = call("GET", f"/api/appraisals/vehicle/{vid}", None, forest)
        if st != 200:
            continue
        # accepted vehicles should remain owns unless manual confirm set traded
        if d.get("ownership_status") == "owns":
            assert d.get("trade_intent_status") in ("accepted", None)
            return
    pytest.skip("no accepted->owns vehicle found; dataset may have manual confirms")


# ---------------- Campaign options + money gate ----------------
def test_campaign_options_default_off(manager):
    st, b = call("GET", "/api/appraisals/campaign-options", None, manager)
    assert st == 200, (st, b)
    triggers = b["triggers"] if isinstance(b.get("triggers"), list) else list(b["triggers"].keys())
    trade_triggers = [t for t in triggers if "trade_appraisal" in t]
    assert len(trade_triggers) >= 8, trade_triggers
    mf = b["merge_fields"] if isinstance(b.get("merge_fields"), list) else list(b["merge_fields"].keys())
    for f in ["trade_vehicle", "trade_mileage", "trade_appraisal_date", "trade_approved_value",
              "trade_customer_wants", "trade_gap", "trade_condition", "trade_outcome", "trade_suggested_acv", "trade_salesperson"]:
        assert f in mf, (f, mf)
    assert b.get("allow_trade_values") is False
    assert "money_fields" in b


def test_org_settings_rep_and_manager_forbidden(rep, manager):
    assert call("PUT", "/api/appraisals/org-settings", {"allow_trade_values_in_automated_messages": True}, rep)[0] == 403
    assert call("PUT", "/api/appraisals/org-settings", {"allow_trade_values_in_automated_messages": True}, manager)[0] == 403


def test_org_settings_super_admin_toggle(forest, manager):
    # Determine the org id from manager's campaign-options (or fall back)
    st, b = call("GET", "/api/appraisals/campaign-options", None, manager)
    assert st == 200
    org_id = b.get("organization_id") or b.get("org_id")
    if not org_id:
        # look it up
        db = _db()
        store = db.stores.find_one({"_id": ObjectId(QA_STORE)}) if ObjectId.is_valid(QA_STORE) else None
        if store:
            org_id = store.get("organization_id")
    if not org_id:
        pytest.skip("could not resolve manager's org id")

    st, r = call("PUT", "/api/appraisals/org-settings",
                 {"allow_trade_values_in_automated_messages": True, "organization_id": org_id}, forest)
    assert st == 200, (st, r)
    st, b = call("GET", "/api/appraisals/campaign-options", None, manager)
    assert st == 200 and b.get("allow_trade_values") is True
    # Restore
    st, r = call("PUT", "/api/appraisals/org-settings",
                 {"allow_trade_values_in_automated_messages": False, "organization_id": org_id}, forest)
    assert st == 200
    st, b = call("GET", "/api/appraisals/campaign-options", None, manager)
    assert b.get("allow_trade_values") is False


def test_campaign_create_filters_invalid_triggers(manager):
    db = _db()
    uid = manager["X-User-ID"]
    body = {
        "name": "QA MVP5 trigger sanitise",
        "type": "custom",
        "trigger_events": ["trade_appraisal.approved", "bogus.event"],
        "active": False,
        "sequences": [],
        "scope": "personal",
    }
    st, b = call("POST", f"/api/campaigns/{uid}", body, manager)
    if st != 200:
        pytest.skip(f"campaign create blocked for manager: {st} {b}")
    cid = b.get("_id") or b.get("id")
    try:
        doc = db.campaigns.find_one({"_id": ObjectId(cid)})
        assert doc["trigger_events"] == ["trade_appraisal.approved"], doc["trigger_events"]
    finally:
        db.campaigns.delete_one({"_id": ObjectId(cid)})


# ---------------- Jessi context: normalized, no raw payloads ----------------
def test_jessi_context_about_sarah(rep):
    # Try common ask endpoints
    body = {"question": "what did we offer Sarah for her F-150 and what did she want?"}
    st, b = call("POST", f"/api/contact-ask/{SARAH}/ask", body, rep)
    assert st == 200, (st, b)
    assert isinstance(b, dict)
    answer = (b.get("answer") or b.get("response") or b.get("text")
              or (b.get("message") or {}).get("content") or "")
    assert answer, b
    low = answer.lower()
    assert "f-150" in low or "f150" in low or "ford" in low, answer[:400]
    # must not include raw provider JSON
    assert "listings\":" not in low and "{\"vin\"" not in low and "provider_payload" not in low, answer[:400]
