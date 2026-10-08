"""Finding -> recon (itemized recon line) + photo markups (Oct 8 2026). Against the preview backend like the MVP4 suite.
Run: cd /app/backend && set -a && . ./.env && set +a && python -m pytest tests/test_markups_and_recon.py -q"""
import base64
import os
import sys
import time
import uuid

import pytest
from bson import ObjectId
from dotenv import load_dotenv
from pymongo import MongoClient

sys.path.insert(0, "/app/backend")
sys.path.insert(0, "/app/backend/tests")
load_dotenv("/app/backend/.env")
from _http import call, login, auth  # noqa: E402
from services.appraisals import engine  # noqa: E402
from services.appraisals.rules import DEFAULT_RULES  # noqa: E402
from test_appraisal_engine import MARKET, VEHICLE, GOOD, BOOKS  # noqa: E402

REP = ("activation-tester@invalid.imonsocial.test", "NewPass123!")
MANAGER = ("qa-manager@invalid.imonsocial.test", "Manager123!")
SARAH = "6aa413008f0d53e3f2261853"
FIX = "/app/backend/tests/fixtures/appraisal/"
CREATED = []


def _db():
    return MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


@pytest.fixture(scope="module")
def rep():
    return auth(*login(*REP))


@pytest.fixture(scope="module")
def manager():
    return auth(*login(*MANAGER))


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    yield
    db = _db()
    for aid in CREATED:
        db.vehicle_appraisals.update_one({"_id": ObjectId(aid)}, {"$set": {"deleted": True}})
        db.appraisal_markups.delete_many({"appraisal_id": aid})


# ---------- engine: itemized recon ----------
BASE = dict(vehicle=VEHICLE, mileage=61200, condition=GOOD, market=MARKET, book_values=BOOKS, customer_expected_value=None, rules=DEFAULT_RULES, now_year=2026, allow_development_basis=True)


def _line(out, key):
    return next((l for l in out["breakdown"] if l["key"] == key), None)


def test_engine_itemized_recon_replaces_allowance_when_everything_is_priced():
    flat = engine.calculate(**BASE)
    allowance = _line(flat, "recon")["amount"]
    assert allowance < 0 and "recon_allowance" not in {l["key"] for l in flat["breakdown"]}
    items = [{"finding_id": "a", "label": "Rear Bumper · Dent", "amount": 450, "by_name": "Kira"}, {"finding_id": "b", "label": "Climate Control · AC / Heat", "amount": 900, "by_name": "Kira"}]
    full = engine.calculate(**BASE, recon_items=items, recon_unpriced=0)
    rl = _line(full, "recon")
    assert rl["amount"] == -1350 and rl["label"] == "Recon (itemized · 2 items)" and rl["source"] == "MANUAL" and rl["reason"] == "Priced by Kira" and rl["items"] == items
    assert _line(full, "recon_allowance") is None, "every confirmed finding is priced: the flat allowance is gone"
    assert full["suggested_acv"] == flat["suggested_acv"] + (-allowance) - 1350
    assert not any("no recon price" in r for r in full["review_reasons"])


def test_engine_partial_pricing_keeps_allowance_and_flags_the_rest():
    items = [{"finding_id": "a", "label": "Rear Bumper · Dent", "amount": 450, "by_name": "Kira"}]
    part = engine.calculate(**BASE, recon_items=items, recon_unpriced=2)
    rl, al = _line(part, "recon"), _line(part, "recon_allowance")
    assert rl["amount"] == -450 and al is not None and al["amount"] < 0 and "covers 2 unpriced" in al["label"]
    assert any("2 confirmed findings have no recon price yet" in r for r in part["review_reasons"]) and part["manager_review_required"] is True
    flat = engine.calculate(**BASE, recon_items=[], recon_unpriced=3)
    assert _line(flat, "recon")["key"] == "recon" and _line(flat, "recon_allowance") is None and "items" not in _line(flat, "recon")
    assert any("3 confirmed findings are not priced" in w for w in flat["warnings"]) and not any("no recon price" in r for r in flat["review_reasons"])
    assert _line(engine.calculate(**BASE, recon_items=[{"finding_id": "x", "label": "x", "amount": None}], recon_unpriced=0), "recon")["amount"] == _line(flat, "recon")["amount"], "a None amount is not an item"


# ---------- API: desk prices findings on a submitted appraisal ----------
def _ready_appraisal(rep):
    st, b = call("POST", "/api/appraisals", {"contact_id": SARAH, "mode": "vehicle_here"}, rep)
    assert st == 200, b
    aid = b["appraisal"]["id"]
    CREATED.append(aid)
    assert call("POST", f"/api/appraisals/{aid}/vehicle", {"manual": {"year": 2019, "make": "Ford", "model": "F-150", "trim": "XLT"}, "method": "manual_vehicle"}, rep)[0] == 200
    assert call("POST", f"/api/appraisals/{aid}/mileage", {"confirmed": 61200, "source": "manual"}, rep)[0] == 200
    for _ in range(4):
        st, b = call("POST", f"/api/appraisals/{aid}/market/refresh", {"zip": "84070", "radius": 100}, rep)
        if st == 200:
            break
        assert st == 429, (st, b)
        time.sleep(16)
    assert st == 200
    return aid


def _upload(rep, aid, name, role, content_type):
    data = base64.b64encode(open(FIX + name, "rb").read()).decode()
    piece, total, uid = 500_000, max(1, -(-len(data) // 500_000)), uuid.uuid4().hex[:12]
    last = None
    for i in range(total):
        st, last = call("POST", f"/api/appraisals/{aid}/media/chunk", {"upload_id": uid, "index": i, "total": total, "data": data[i * piece:(i + 1) * piece], "name": name, "content_type": content_type, "role": role, "source": "captured_by_rep"}, rep)
        assert st == 200, (st, last)
    return last["media"]


def _photo(rep, aid, name="front_driver.jpg", role="exterior"):
    return _upload(rep, aid, name, role, "image/jpeg")


def _finding(rep, aid, **kw):
    st, b = call("POST", f"/api/appraisals/{aid}/inspection/findings", {"category": "body", "subtype": "dent", "location": "rear_bumper", "severity": "moderate", **kw}, rep)
    assert st == 200, b
    return b["finding"]


def test_desk_prices_findings_and_the_number_refreezes(rep, manager):
    aid = _ready_appraisal(rep)
    f1 = _finding(rep, aid)
    f2 = _finding(rep, aid, category="mechanical", subtype="ac_heat", location="climate_control", severity="major")
    assert f1["decision"] == "confirmed" and f1["recon_cost"] is None
    st, pv = call("GET", f"/api/appraisals/{aid}/calculate", None, rep)
    assert st == 200 and _line(pv["output"], "recon") is not None and any("2 confirmed findings are not priced" in w for w in pv["output"]["warnings"])
    # not before it is confirmed / not by a rep / not out of range
    assert call("POST", f"/api/appraisals/{aid}/inspection/findings/{f1['id']}/recon", {"amount": 450}, rep)[0] == 403
    assert call("POST", f"/api/appraisals/{aid}/inspection/findings/{f1['id']}/recon", {"amount": 99999}, manager)[0] == 400
    assert call("POST", f"/api/appraisals/{aid}/inspection/findings/{ObjectId()}/recon", {"amount": 450}, manager)[0] == 404
    # Draft: pricing works, no calculation is frozen, the live preview already itemizes.
    st, r = call("POST", f"/api/appraisals/{aid}/inspection/findings/{f1['id']}/recon", {"amount": 450}, manager)
    assert st == 200 and r["finding"]["recon_cost"] == 450 and r["finding"]["recon_by_name"] and r["calculation"] is None
    assert r["recon"] == {"items": [{**r["recon"]["items"][0], "amount": 450, "label": "Rear Bumper · Dent"}], "unpriced": 1, "confirmed": 2}
    assert _line(r["preview"], "recon")["amount"] == -450 and _line(r["preview"], "recon_allowance") is not None
    # Submit freezes v1 with the partial itemization.
    st, s = call("POST", f"/api/appraisals/{aid}/submit", None, rep)
    assert st == 200, s
    v1 = s["workflow"]["suggested_acv"]
    st, d = call("GET", f"/api/appraisals/desk/{aid}", None, manager)
    assert st == 200 and d["calculation"]["version"] == 1 and d["recon"]["unpriced"] == 1
    assert any("1 confirmed finding has no recon price yet" in x for x in d["calculation"]["output"]["review_reasons"])
    conf = d["inspection"]["report"]["confirmed"]
    assert next(f for f in conf if f["id"] == f1["id"])["recon_cost"] == 450 and next(f for f in conf if f["id"] == f2["id"])["recon_cost"] is None
    # Price the second one on the desk: new calc v2, itemized only, number moves by the difference between allowance and the items.
    st, r = call("POST", f"/api/appraisals/{aid}/inspection/findings/{f2['id']}/recon", {"amount": 900}, manager)
    assert st == 200 and r["calculation"]["version"] == 2 and r["calculation"]["trigger"] == "recon_itemized" and r["preview"] is None
    out = r["calculation"]["output"]
    rl = _line(out, "recon")
    assert rl["amount"] == -1350 and len(rl["items"]) == 2 and _line(out, "recon_allowance") is None and not any("no recon price" in x for x in out["review_reasons"])
    allowance = -_line(d["calculation"]["output"], "recon_allowance")["amount"]
    assert r["suggested_acv"] == out["suggested_acv"] == v1 + allowance - 900, "the allowance leaves, the AC price enters"
    st, d2 = call("GET", f"/api/appraisals/desk/{aid}", None, manager)
    assert d2["calculation"]["version"] == 2 and d2["suggested_acv"] == r["suggested_acv"] and d2["recon"] == {"items": d2["recon"]["items"], "unpriced": 0, "confirmed": 2}
    assert any(a["action"] == "number_refreshed" for a in d2["activity"]) and any(a["action"] == "finding_priced" for a in d2["activity"])
    st, mine = call("GET", f"/api/appraisals/{aid}", None, rep)
    assert mine["suggested_acv"] == r["suggested_acv"] and mine["calculation"]["version"] == 2, "the rep sees the re-frozen number"
    # Clear one price: back to partial (v3), allowance returns.
    st, r = call("POST", f"/api/appraisals/{aid}/inspection/findings/{f2['id']}/recon", {"amount": None}, manager)
    assert st == 200 and r["finding"]["recon_cost"] is None and r["calculation"]["version"] == 3 and _line(r["calculation"]["output"], "recon_allowance") is not None
    # Approve, then pricing no longer moves the signed number.
    st, dd = call("POST", f"/api/appraisals/{aid}/decide", {"action": "approve"}, manager)
    assert st == 200 and dd["status"] == "approved"
    st, r = call("POST", f"/api/appraisals/{aid}/inspection/findings/{f2['id']}/recon", {"amount": 700}, manager)
    assert st == 200 and r["calculation"] is None and r["finding"]["recon_cost"] == 700
    st, d3 = call("GET", f"/api/appraisals/desk/{aid}", None, manager)
    assert d3["calculation"]["version"] == 3 and d3["approved_value"] is not None


# ---------- API: markups ----------
STROKES = [[{"x": 0.30, "y": 0.40}, {"x": 0.35, "y": 0.35}, {"x": 0.42, "y": 0.38}, {"x": 0.40, "y": 0.46}, {"x": 0.31, "y": 0.45}], [{"x": 0.5, "y": 0.5}, {"x": 0.6, "y": 0.6}]]


def test_manager_marks_up_a_photo_and_the_rep_sees_it(rep, manager):
    st, b = call("POST", "/api/appraisals", {"contact_id": SARAH, "mode": "vehicle_here"}, rep)
    assert st == 200
    aid = b["appraisal"]["id"]
    CREATED.append(aid)
    photo = _photo(rep, aid)
    rep_uid = login(*REP)[1]
    db = _db()
    before = db.notifications.count_documents({"user_id": rep_uid, "type": "appraisal_markup"})
    assert call("POST", f"/api/appraisals/{aid}/markups", {"target_id": photo["id"], "strokes": [], "note": "x"}, manager)[0] == 400
    assert call("POST", f"/api/appraisals/{aid}/markups", {"target_id": str(ObjectId()), "strokes": STROKES}, manager)[0] == 404
    assert call("POST", f"/api/appraisals/{aid}/markups", {"target_id": photo["id"], "strokes": [[{"x": "nope"}]]}, manager)[0] == 400
    st, r = call("POST", f"/api/appraisals/{aid}/markups", {"target_id": photo["id"], "strokes": [[{"x": 1.7, "y": -0.2}, {"x": 0.5, "y": 0.5}]] + STROKES, "note": "This dent is deeper than it looks", "color": "#FF3B30"}, manager)
    assert st == 200, r
    k = r["markup"]
    assert k["target_kind"] == "media" and k["note"] == "This dent is deeper than it looks" and k["by_name"] and k["color"] == "#FF3B30"
    assert k["strokes"][0][0] == {"x": 1.0, "y": 0.0}, "points are clamped into the photo"
    assert len(k["strokes"]) == 3 and k["strokes"][1] == STROKES[0]
    m = next(x for x in r["media"] if x["id"] == photo["id"])
    assert len(m["markups"]) == 1 and m["markups"][0]["id"] == k["id"]
    assert db.notifications.count_documents({"user_id": rep_uid, "type": "appraisal_markup"}) == before + 1
    n = db.notifications.find_one({"user_id": rep_uid, "type": "appraisal_markup"}, sort=[("created_at", -1)])
    assert "marked up a photo" in n["title"] and n["message"].startswith("This dent") and n["link"] == f"/appraisal/{aid}"
    st, d = call("GET", f"/api/appraisals/{aid}", None, rep)
    assert st == 200 and len(next(x for x in d["media"] if x["id"] == photo["id"])["markups"]) == 1
    assert any(a["action"] == "photo_marked_up" and "deeper" in (a.get("detail") or "") for a in d["activity"])
    st, insp = call("GET", f"/api/appraisals/{aid}/inspection", None, rep)
    assert st == 200 and len(next(x for x in insp["media"] if x["id"] == photo["id"])["markups"]) == 1
    # The rep's own markup does not notify the rep; a second markup stacks.
    st, r2 = call("POST", f"/api/appraisals/{aid}/markups", {"target_id": photo["id"], "strokes": STROKES[1:], "note": "Got it"}, rep)
    assert st == 200 and len(next(x for x in r2["media"] if x["id"] == photo["id"])["markups"]) == 2
    assert db.notifications.count_documents({"user_id": rep_uid, "type": "appraisal_markup"}) == before + 1
    # Only the author (or a manager) removes one.
    assert call("DELETE", f"/api/appraisals/{aid}/markups/{k['id']}", None, rep)[0] == 403
    assert call("DELETE", f"/api/appraisals/{aid}/markups/{ObjectId()}", None, manager)[0] == 404
    st, r3 = call("DELETE", f"/api/appraisals/{aid}/markups/{k['id']}", None, manager)
    assert st == 200 and [x["note"] for x in next(x for x in r3["media"] if x["id"] == photo["id"])["markups"]] == ["Got it"]
    # No drawing on the video itself.
    vid = _upload(rep, aid, "walkaround.mp4", "walkaround_video", "video/mp4")["id"]
    assert call("POST", f"/api/appraisals/{aid}/markups", {"target_id": vid, "strokes": STROKES}, manager)[0] == 400
    # ... but a snapshot pulled from it takes ink and carries it in snapshots[].
    for _ in range(40):
        time.sleep(2)
        st, insp = call("GET", f"/api/appraisals/{aid}/inspection", None, rep)
        if next(x for x in insp["media"] if x["id"] == vid)["frames_status"] != "extracting":
            break
    snap = insp["snapshots"][0]
    st, r4 = call("POST", f"/api/appraisals/{aid}/markups", {"target_id": snap["id"], "strokes": STROKES, "note": "Curb rash here"}, manager)
    assert st == 200 and r4["markup"]["target_kind"] == "snapshot"
    assert len(next(s for s in r4["snapshots"] if s["id"] == snap["id"])["markups"]) == 1
    st, dd = call("GET", f"/api/appraisals/desk/{aid}", None, manager)
    assert st == 200 and len(next(s for s in dd["snapshots"] if s["id"] == snap["id"])["markups"]) == 1
