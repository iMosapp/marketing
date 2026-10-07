"""Trade Appraisal MVP4 - dealership rules, suggested ACV, manager approval workflow, present + outcome. Runs against the preview backend.
Rep = activation-tester (store QA), manager = qa-manager (store_manager on the same store), stranger = org admin of another org."""
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
OTHER_ORG_ADMIN = ("qa-orgadmin@invalid.imonsocial.test", "OrgAdmin123!")
SARAH = "6aa413008f0d53e3f2261853"
QA_STORE = "69a0b7095fddcede09591668"
CREATED = []


def _db():
    return MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


def _new_appraisal(hdr, miles=61200, market=True):
    st, b = call("POST", "/api/appraisals", {"contact_id": SARAH, "mode": "vehicle_here"}, hdr)
    assert st == 200, (st, b)
    aid = b["appraisal"]["id"]
    CREATED.append(aid)
    st, _ = call("POST", f"/api/appraisals/{aid}/vehicle", {"manual": {"year": 2019, "make": "Ford", "model": "F-150", "trim": "XLT"}, "method": "manual_vehicle"}, hdr)
    assert st == 200
    st, _ = call("POST", f"/api/appraisals/{aid}/mileage", {"confirmed": miles, "source": "manual"}, hdr)
    assert st == 200
    if market:
        for _ in range(4):
            st, b = call("POST", f"/api/appraisals/{aid}/market/refresh", {"zip": "84070", "radius": 100}, hdr)
            if st == 200:
                break
            assert st == 429, (st, b)
            time.sleep(16)
        assert st == 200, "market refresh kept hitting the rate limit"
    return aid


@pytest.fixture(scope="module")
def rep():
    return auth(*login(*REP))


@pytest.fixture(scope="module")
def manager():
    return auth(*login(*MANAGER))


@pytest.fixture(scope="module")
def stranger():
    return auth(*login(*OTHER_ORG_ADMIN))


@pytest.fixture(scope="module", autouse=True)
def cleanup(manager):
    yield
    call("DELETE", f"/api/appraisals/rules/store/{QA_STORE}", None, manager)
    db = _db()
    for aid in CREATED:
        db.vehicle_appraisals.update_one({"_id": ObjectId(aid)}, {"$set": {"deleted": True}})


# ---------- permissions + meta ----------
def test_meta_abilities(rep, manager):
    st, b = call("GET", "/api/appraisals/meta", None, rep)
    assert st == 200 and b["abilities"] == {"manager": False, "edit_rules": False}
    assert "resubmitted" in b["statuses"] and "wants_more" in b["outcomes"]
    st, b = call("GET", "/api/appraisals/meta", None, manager)
    assert st == 200 and b["abilities"] == {"manager": True, "edit_rules": True}


def test_rules_gates_and_versioning(rep, manager):
    assert call("GET", "/api/appraisals/rules", None, rep)[0] == 403
    assert call("GET", "/api/appraisals/desk", None, rep)[0] == 403
    call("DELETE", f"/api/appraisals/rules/store/{QA_STORE}", None, manager)
    st, b = call("GET", "/api/appraisals/rules", None, manager)
    assert st == 200 and b["effective"]["source"] in ("default", "org") and QA_STORE in {s["id"] for s in b["stores"]}
    assert b["org_editable"] is False and b["can_edit"] is True and "provider_retail" in b["options"]["basis"]
    # store manager cannot write the org default
    assert call("PUT", "/api/appraisals/rules", {"scope": "org", "rules": b["effective"]["rules"]}, manager)[0] == 403
    # bad rules -> 400
    st, _ = call("PUT", "/api/appraisals/rules", {"scope": "store", "store_id": QA_STORE, "rules": {"basis": {"order": ["bogus"]}}}, manager)
    assert st == 400
    rules = b["options"]["defaults"] | {"target_gross": {"enabled": True, "method": "fixed", "amount": 2500}, "mileage": {"enabled": True}}
    st, b = call("PUT", "/api/appraisals/rules", {"scope": "store", "store_id": QA_STORE, "rules": rules}, manager)
    assert st == 200, b
    assert b["store"]["version"] == 1 and b["effective"]["source"] == "store" and b["effective"]["rules"]["target_gross"]["amount"] == 2500
    assert any("Mileage adjustment is ON" in w for w in b["warnings"])
    st, b = call("PUT", "/api/appraisals/rules", {"scope": "store", "store_id": QA_STORE, "rules": rules | {"mileage": {"enabled": False}}}, manager)
    assert st == 200 and b["store"]["version"] == 2 and b["store"]["history_count"] == 1 and b["warnings"] == []
    # outside reach
    assert call("PUT", "/api/appraisals/rules", {"scope": "store", "store_id": "69a907033b77512d1d8d8a09", "rules": rules}, manager)[0] == 403


# ---------- the happy path: calculate -> submit -> needs info -> resubmit -> change -> present -> outcome ----------
def test_full_workflow(rep, manager, stranger):
    aid = _new_appraisal(rep)
    st, pv = call("GET", f"/api/appraisals/{aid}/calculate", None, rep)
    assert st == 200 and pv["preview"] is True and pv["rules_source"] == "store" and pv["rules_version"] == 2
    out = pv["output"]
    assert out["suggested_acv"] is not None and out["basis"]["source"] == "MARKET DATA"
    keys = [l["key"] for l in out["breakdown"]]
    assert keys[:2] == ["basis", "target_gross"] and next(l for l in out["breakdown"] if l["key"] == "target_gross")["amount"] == -2500
    assert pv["abilities"]["submit"] is True and pv["abilities"]["decide"] is False
    retail = pv["market"]["estimated_retail"]
    st, _ = call("POST", f"/api/appraisals/{aid}/expectation", {"asked": True, "value": retail + 5000}, rep)
    assert st == 200
    # present / outcome / decide before submit are refused by the status machine
    assert call("POST", f"/api/appraisals/{aid}/present", None, rep)[0] == 409
    assert call("POST", f"/api/appraisals/{aid}/outcome", {"outcome": "accepted"}, rep)[0] == 409
    assert call("POST", f"/api/appraisals/{aid}/decide", {"action": "approve"}, manager)[0] == 409

    st, b = call("POST", f"/api/appraisals/{aid}/submit", None, rep)
    assert st == 200, b
    assert b["appraisal"]["status"] == "submitted" and b["workflow"]["calculation_version"] == 1 and b["workflow"]["rules_version"] == 2
    assert b["workflow"]["suggested_acv"] == out["suggested_acv"] and b["notified"] >= 1
    assert b["appraisal"]["approved_value"] is None
    suggested = b["workflow"]["suggested_acv"]
    # frozen: inputs locked, rep cannot decide, stranger cannot see
    assert call("POST", f"/api/appraisals/{aid}/mileage", {"confirmed": 70000}, rep)[0] == 409
    assert call("POST", f"/api/appraisals/{aid}/book-values", {"source": "mmr", "value_type": "wholesale", "value": 20000}, rep)[0] == 409
    assert call("POST", f"/api/appraisals/{aid}/decide", {"action": "approve"}, rep)[0] == 403
    assert call("GET", f"/api/appraisals/desk/{aid}", None, stranger)[0] == 404
    assert call("GET", f"/api/appraisals/{aid}", None, stranger)[0] == 404
    # rule change after submit does not touch the frozen calculation
    st, rb = call("GET", "/api/appraisals/rules", {"store_id": QA_STORE}, manager) if False else call("GET", f"/api/appraisals/rules?store_id={QA_STORE}", None, manager)
    rules = rb["effective"]["rules"] | {"target_gross": {"enabled": True, "method": "fixed", "amount": 4000}}
    assert call("PUT", "/api/appraisals/rules", {"scope": "store", "store_id": QA_STORE, "rules": rules}, manager)[0] == 200
    st, d = call("GET", f"/api/appraisals/{aid}", None, rep)
    assert st == 200 and d["calculation"]["output"]["suggested_acv"] == suggested and d["calculation"]["rules_version"] == 2
    assert d["abilities"]["locked"] is True and d["abilities"]["edit"] is False and d["status"] == "submitted"
    assert d["workflow"]["approved_value"] is None and d["suggested_acv"] == suggested

    # desk
    st, q = call("GET", "/api/appraisals/desk?group=waiting", None, manager)
    assert st == 200 and aid in {r["id"] for r in q["appraisals"]} and q["counts"]["waiting"] >= 1
    row = next(r for r in q["appraisals"] if r["id"] == aid)
    assert row["waiting_s"] is not None and row["expectation_gap"] == (retail + 5000 - suggested) and row["market_retail"] == retail
    st, dd = call("GET", f"/api/appraisals/desk/{aid}", None, manager)
    assert st == 200 and dd["abilities"]["decide"] is True and dd["calculation"]["version"] == 1 and dd["market"]["snapshot"] is not None
    assert dd["customer_expected_value"] == retail + 5000 and dd["suggested_acv"] == suggested and dd["approved_value"] is None
    assert len(dd["market"]["comparables"]) > 0

    # request info -> rep edits -> resubmits
    assert call("POST", f"/api/appraisals/{aid}/decide", {"action": "request_info", "reason": "x"}, manager)[0] == 400
    st, dd = call("POST", f"/api/appraisals/{aid}/decide", {"action": "request_info", "reason": "Need photos of the tailgate dent"}, manager)
    assert st == 200 and dd["status"] == "needs_info" and dd["needs_info_request"]["reason"].startswith("Need photos")
    st, d = call("GET", f"/api/appraisals/{aid}", None, rep)
    assert d["abilities"]["edit"] is True and d["abilities"]["resubmit"] is True and d["workflow"]["needs_info_request"]["by_name"]
    assert call("POST", f"/api/appraisals/{aid}/mileage", {"confirmed": 61500}, rep)[0] == 200
    st, b = call("POST", f"/api/appraisals/{aid}/submit", None, rep)
    assert st == 200 and b["appraisal"]["status"] == "resubmitted" and b["workflow"]["calculation_version"] == 2 and b["workflow"]["rules_version"] == 3
    # rules v3 (target gross 4000) now applies to the fresh calculation
    assert b["workflow"]["suggested_acv"] == suggested - 1500
    suggested2 = b["workflow"]["suggested_acv"]
    st, q = call("GET", "/api/appraisals/desk?group=waiting", None, manager)
    assert aid in {r["id"] for r in q["appraisals"]}

    # change value
    assert call("POST", f"/api/appraisals/{aid}/decide", {"action": "change", "reason": "Strong unit"}, manager)[0] == 400
    st, dd = call("POST", f"/api/appraisals/{aid}/decide", {"action": "change", "value": suggested2 + 700, "reason": "Strong unit, we need trucks"}, manager)
    assert st == 200, dd
    assert dd["status"] == "changed" and dd["approved_value"] == suggested2 + 700 and dd["suggested_acv"] == suggested2
    assert dd["manager_adjustment"]["delta"] == 700 and dd["approved_by_name"]
    assert len(dd["decisions"]) == 2 and dd["decisions"][-1]["action"] == "change" and dd["decisions"][-1]["system_suggested_acv"] == suggested2
    assert dd["abilities"]["decide"] is False and dd["abilities"]["present"] is True
    assert call("POST", f"/api/appraisals/{aid}/decide", {"action": "approve"}, manager)[0] == 409
    # three numbers stay distinct
    assert dd["market_retail"] == retail and dd["suggested_acv"] == suggested2 and dd["approved_value"] == suggested2 + 700

    # present + outcome
    assert call("POST", f"/api/appraisals/{aid}/outcome", {"outcome": "accepted"}, rep)[0] == 409
    st, b = call("POST", f"/api/appraisals/{aid}/present", None, rep)
    assert st == 200 and b["appraisal"]["status"] == "presented" and b["abilities"]["outcome"] is True
    assert call("POST", f"/api/appraisals/{aid}/outcome", {"outcome": "nonsense"}, rep)[0] == 400
    st, b = call("POST", f"/api/appraisals/{aid}/outcome", {"outcome": "wants_more", "expected_value": suggested2 + 3000, "note": "Will think about it over the weekend"}, rep)
    assert st == 200, b
    assert b["appraisal"]["status"] == "closed" and b["appraisal"]["outcome"] == "wants_more" and b["appraisal"]["outcome_label"] == "Wants more"
    assert b["workflow"]["expectation_gap_final"] == 2300 and b["appraisal"]["customer_expected_value"] == suggested2 + 3000
    st, d = call("GET", f"/api/appraisals/{aid}", None, rep)
    assert d["workflow"]["status_history"][-1]["to"] == "closed" and [h["to"] for h in d["workflow"]["status_history"]][-5:] == ["needs_info", "resubmitted", "changed", "presented", "closed"]

    # relationship intelligence + events
    db = _db()
    c = db.contacts.find_one({"_id": ObjectId(SARAH)}, {"trade_appraisal": 1})
    ta = c.get("trade_appraisal") or {}
    assert ta.get("appraisal_id") == aid and ta.get("approved_value") == suggested2 + 700 and ta.get("outcome") == "wants_more" and ta.get("suggested_acv") == suggested2
    evs = [e["event"] for e in db.appraisal_events.find({"appraisal_id": aid}).sort("created_at", 1)]
    assert evs == ["trade_appraisal.submitted", "trade_appraisal.needs_info", "trade_appraisal.resubmitted", "trade_appraisal.approved", "trade_appraisal.presented",
                   "trade_appraisal.wants_more", "trade_appraisal.closed"]
    ev = db.appraisal_events.find_one({"appraisal_id": aid, "event": "trade_appraisal.approved"})
    assert ev["context"]["trade_approved_value"] == f"${suggested2 + 700:,}" and ev["numbers"]["suggested_acv"] == suggested2
    n = db.notifications.find_one({"type": "appraisal_submitted", "link": f"/appraisal/desk/{aid}"})
    assert n is not None
    assert db.notifications.find_one({"type": "appraisal_changed", "link": f"/appraisal/{aid}"}) is not None
    calcs = list(db.appraisal_calculations.find({"appraisal_id": aid}).sort("version", 1))
    assert [c["version"] for c in calcs] == [1, 2] and calcs[0]["inputs"]["rules_snapshot"]["target_gross"]["amount"] == 2500 and calcs[1]["inputs"]["rules_snapshot"]["target_gross"]["amount"] == 4000


def test_decline_then_outcome_and_approve_as_is(rep, manager):
    aid = _new_appraisal(rep, market=False)
    # no market, no book -> no basis -> manager review required, still submittable
    st, pv = call("GET", f"/api/appraisals/{aid}/calculate", None, rep)
    assert st == 200 and pv["output"]["suggested_acv"] is None and pv["output"]["manager_review_required"] is True
    st, b = call("POST", f"/api/appraisals/{aid}/submit", None, rep)
    assert st == 200 and b["appraisal"]["status"] == "submitted" and b["workflow"]["manager_review_required"] is True
    # approve "as is" with no suggested value is refused; decline needs a reason
    assert call("POST", f"/api/appraisals/{aid}/decide", {"action": "approve"}, manager)[0] == 400
    assert call("POST", f"/api/appraisals/{aid}/decide", {"action": "decline"}, manager)[0] == 400
    st, dd = call("POST", f"/api/appraisals/{aid}/decide", {"action": "decline", "reason": "Branded title, we do not buy these"}, manager)
    assert st == 200 and dd["status"] == "declined" and dd["declined_reason"].startswith("Branded") and dd["abilities"]["outcome"] is True
    assert call("POST", f"/api/appraisals/{aid}/present", None, rep)[0] == 409
    st, b = call("POST", f"/api/appraisals/{aid}/outcome", {"outcome": "not_trading"}, rep)
    assert st == 200 and b["appraisal"]["status"] == "closed" and b["appraisal"]["outcome"] == "not_trading"
    st, q = call("GET", "/api/appraisals/desk?group=decided", None, manager)
    assert st == 200 and aid in {r["id"] for r in q["appraisals"]}

    # approve exactly the suggested number
    aid2 = _new_appraisal(rep)
    st, b = call("POST", f"/api/appraisals/{aid2}/submit", None, rep)
    assert st == 200
    sug = b["workflow"]["suggested_acv"]
    st, dd = call("POST", f"/api/appraisals/{aid2}/decide", {"action": "approve"}, manager)
    assert st == 200 and dd["status"] == "approved" and dd["approved_value"] == sug and dd["manager_adjustment"] is None
    assert dd["decisions"][-1]["delta"] == 0
    st, lst = call("GET", "/api/appraisals?group=approved", None, rep)
    assert st == 200 and aid2 in {r["id"] for r in lst["appraisals"]} and "desk" not in lst
    st, lst = call("GET", "/api/appraisals", None, manager)
    assert st == 200 and "desk" in lst and "waiting" in lst["desk"]


def test_submit_requires_vehicle_and_mileage(rep):
    st, b = call("POST", "/api/appraisals", {"contact_id": SARAH, "mode": "vehicle_here"}, rep)
    aid = b["appraisal"]["id"]
    st, b = call("POST", f"/api/appraisals/{aid}/submit", None, rep)
    assert st == 400 and "vehicle" in b.lower()
    call("DELETE", f"/api/appraisals/{aid}", None, rep)
