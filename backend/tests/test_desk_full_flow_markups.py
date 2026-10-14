"""Full-desk flow E2E: fresh submitted appraisal, price findings on the desk, re-freeze, approve, markups.
Oct 8, 2026 iteration 372. Preview backend."""
import os
import sys
import time

import pytest
from bson import ObjectId
from dotenv import load_dotenv
from pymongo import MongoClient
from tests import qa_creds

sys.path.insert(0, "/app/backend")
sys.path.insert(0, "/app/backend/tests")
load_dotenv("/app/backend/.env")
from _http import call, login, auth  # noqa: E402

REP = ("activation-tester@invalid.imonsocial.test", qa_creds.password_for("activation-tester@invalid.imonsocial.test"))
MANAGER = ("qa-manager@invalid.imonsocial.test", qa_creds.password_for("qa-manager@invalid.imonsocial.test"))
SARAH = "6aa413008f0d53e3f2261853"


def _db():
    return MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


@pytest.fixture(scope="module")
def rep():
    return auth(*login(*REP))


@pytest.fixture(scope="module")
def manager():
    return auth(*login(*MANAGER))


def _line(bd, key):
    return next((l for l in bd["breakdown"] if l["key"] == key), None)


def test_full_desk_flow_with_itemized_recon_refreeze(rep, manager):
    created = []
    try:
        # Create fresh appraisal, vehicle, mileage, market
        st, b = call("POST", "/api/appraisals", {"contact_id": SARAH, "mode": "vehicle_here"}, rep)
        assert st == 200
        aid = b["appraisal"]["id"]
        created.append(aid)
        assert call("POST", f"/api/appraisals/{aid}/vehicle",
                    {"manual": {"year": 2019, "make": "Ford", "model": "F-150", "trim": "XLT"},
                     "method": "manual_vehicle"}, rep)[0] == 200
        assert call("POST", f"/api/appraisals/{aid}/mileage", {"confirmed": 61200, "source": "manual"}, rep)[0] == 200
        for _ in range(4):
            st, _ = call("POST", f"/api/appraisals/{aid}/market/refresh",
                         {"zip": "84070", "radius": 100}, rep)
            if st == 200:
                break
            time.sleep(16)
        assert st == 200

        # Two human findings - confirmed on creation
        st, b = call("POST", f"/api/appraisals/{aid}/inspection/findings",
                     {"category": "body", "subtype": "dent", "location": "rear_bumper",
                      "location_label": "Rear Bumper", "severity": "moderate"}, rep)
        assert st == 200
        f1 = b["finding"]
        assert f1["decision"] == "confirmed"
        st, b = call("POST", f"/api/appraisals/{aid}/inspection/findings",
                     {"category": "wheels_tires", "subtype": "curb_rash",
                      "location": "front_left_wheel", "location_label": "Front Left Wheel",
                      "severity": "minor"}, rep)
        assert st == 200
        f2 = b["finding"]

        # Submit
        st, s = call("POST", f"/api/appraisals/{aid}/submit", None, rep)
        assert st == 200, s

        # Desk: v1, flat allowance, 2 unpriced
        st, d = call("GET", f"/api/appraisals/desk/{aid}", None, manager)
        assert st == 200
        assert d["calculation"]["version"] == 1
        assert d["recon"]["unpriced"] == 2 and d["recon"]["confirmed"] == 2
        out = d["calculation"]["output"]
        assert _line(out, "recon") is not None
        # When partial pricing/0 priced: flat allowance applies under key 'recon' alone
        assert _line(out, "recon_allowance") is None  # 0 items priced -> flat under 'recon'

        # Price f1 $450 -> re-freeze v2
        st, r = call("POST", f"/api/appraisals/{aid}/inspection/findings/{f1['id']}/recon",
                     {"amount": 450}, manager)
        assert st == 200
        assert r["calculation"]["version"] == 2
        assert r["calculation"]["trigger"] == "recon_itemized"
        out2 = r["calculation"]["output"]
        recon = _line(out2, "recon")
        assert recon["amount"] == -450
        assert "1 item" in recon["label"]
        allowance = _line(out2, "recon_allowance")
        assert allowance is not None and "covers 1 unpriced" in allowance["label"]
        assert any("1 confirmed finding has no recon price yet" in rr for rr in out2["review_reasons"])

        # Price f2 $150 -> v3, allowance gone, 2 items
        st, r = call("POST", f"/api/appraisals/{aid}/inspection/findings/{f2['id']}/recon",
                     {"amount": 150}, manager)
        assert st == 200
        assert r["calculation"]["version"] == 3
        out3 = r["calculation"]["output"]
        recon = _line(out3, "recon")
        assert recon["amount"] == -600 and "2 items" in recon["label"]
        assert _line(out3, "recon_allowance") is None
        assert len(recon["items"]) == 2

        # Verify via GET desk
        st, d3 = call("GET", f"/api/appraisals/desk/{aid}", None, manager)
        assert d3["calculation"]["version"] == 3
        assert d3["suggested_acv"] == out3["suggested_acv"]

        # Approve
        st, dd = call("POST", f"/api/appraisals/{aid}/decide", {"action": "approve"}, manager)
        assert st == 200 and dd["status"] == "approved"

        # Pricing after approve returns calculation: None
        st, r = call("POST", f"/api/appraisals/{aid}/inspection/findings/{f1['id']}/recon",
                     {"amount": 500}, manager)
        assert st == 200 and r["calculation"] is None

    finally:
        db = _db()
        for aid in created:
            db.vehicle_appraisals.update_one({"_id": ObjectId(aid)}, {"$set": {"deleted": True}})
            db.appraisal_markups.delete_many({"appraisal_id": aid})
