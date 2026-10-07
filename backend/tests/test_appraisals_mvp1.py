"""Trade Appraisal MVP1: draft flow, VIN photo (barcode) + odometer photo (Jessi) imports with provenance, NHTSA decode, manual vehicle,
REAPPRAISE on the same vehicle, tenant/store isolation, permission gate. Needs the running preview backend + EMERGENT_LLM_KEY for the odometer read."""
import base64
import io
import os
import sys
import time
import uuid

import pytest
from bson import ObjectId
from pymongo import MongoClient

sys.path.insert(0, "/app/backend")
sys.path.insert(0, "/app/backend/tests")
from _http import call, login, auth  # noqa: E402
from utils import vin as vinlib  # noqa: E402

REP = ("activation-tester@invalid.imonsocial.test", "NewPass123!")
MANAGER = ("qa-manager@invalid.imonsocial.test", "Manager123!")
OTHER_ORG_ADMIN = ("qa-orgadmin@invalid.imonsocial.test", "OrgAdmin123!")
NO_PERM_REP = ("mjeast1985@gmail.com", "NavyBean1!")
SARAH = "6aa413008f0d53e3f2261853"
VIN = "1HGCM82633A004352"  # 2003 Honda Accord, valid check digit


def _env(k):
    for line in open("/app/backend/.env"):
        if line.startswith(k + "="):
            return line.split("=", 1)[1].strip().strip('"')


@pytest.fixture(scope="module")
def db():
    return MongoClient(_env("MONGO_URL"))[_env("DB_NAME")]


@pytest.fixture(scope="module")
def rep(db):
    tok, uid = login(*REP)
    db.users.update_one({"_id": ObjectId(uid)}, {"$set": {"feature_permissions.my_tools._enabled": True, "feature_permissions.my_tools.trade_appraisal": True}})
    tok, uid = login(*REP)  # token payload refreshed with the permission
    return auth(tok, uid), uid


def _barcode_png(text: str) -> bytes:
    import zxingcpp
    from PIL import Image
    img = Image.fromarray(zxingcpp.write_barcode(zxingcpp.BarcodeFormat.Code39, text, width=900, height=220))
    canvas = Image.new("RGB", (1000, 400), "white")
    canvas.paste(img.convert("RGB"), (50, 60))
    from PIL import ImageDraw, ImageFont
    d = ImageDraw.Draw(canvas)
    try:
        f = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 34)
    except Exception:
        f = ImageFont.load_default()
    d.text((60, 300), f"VIN {text}", fill="black", font=f)
    b = io.BytesIO()
    canvas.save(b, "PNG")
    return b.getvalue()


def _odometer_png(miles: int) -> bytes:
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGB", (900, 420), (12, 14, 20))
    d = ImageDraw.Draw(img)
    try:
        big = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", 96)
        small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 30)
    except Exception:
        big = small = ImageFont.load_default()
    d.rounded_rectangle((60, 90, 840, 330), radius=24, outline=(90, 95, 110), width=4)
    d.text((110, 150), f"{miles:,}", fill=(240, 240, 240), font=big)
    d.text((660, 180), "mi", fill=(200, 200, 200), font=small)
    d.text((110, 280), "ODO", fill=(140, 140, 150), font=small)
    d.text((560, 60), "TRIP A  123.4", fill=(120, 120, 130), font=small)
    b = io.BytesIO()
    img.save(b, "PNG")
    return b.getvalue()


def _upload(hdrs, appraisal_id, data: bytes, role: str, source: str, name: str):
    b64 = base64.b64encode(data).decode()
    pieces = [b64[i:i + 500_000] for i in range(0, len(b64), 500_000)]
    uid = uuid.uuid4().hex
    out = None
    for i, piece in enumerate(pieces):
        st, out = call("POST", f"/api/appraisals/{appraisal_id}/media/chunk",
                       {"upload_id": uid, "index": i, "total": len(pieces), "data": piece, "name": name, "content_type": "image/png", "role": role, "source": source}, hdrs)
        assert st == 200, (st, out)
    return out["media"]


# ---------------- VIN utils ----------------
def test_vin_validation_and_ocr_fixes():
    assert vinlib.validate(VIN)["valid"] and vinlib.validate(VIN)["checksum"] == "ok"
    bad = vinlib.validate(VIN[:-1] + "1")
    assert not bad["valid"] and "Check digit" in bad["errors"][0]
    assert vinlib.normalize("1hgcm8263-3a0O4352") == VIN  # lowercase, dash, letter O -> 0
    assert vinlib.validate("1HGCM82633A00435")["errors"][0].startswith("A VIN has 17")
    assert vinlib.candidates(f"door label text VIN: {VIN} tire 35 psi")[0] == VIN


# ---------------- flow ----------------
def test_mvp1_flow_vin_photo_odometer_reappraise(rep, db):
    hdrs, uid = rep
    st, meta = call("GET", "/api/appraisals/meta", headers=hdrs)
    assert st == 200 and meta["modes"]["customer_sent"] and any(i["kind"] == "plate" and not i["available"] for i in meta["identity"])

    st, r = call("POST", "/api/appraisals", {"contact_id": SARAH, "mode": "customer_sent"}, hdrs)
    assert st == 200, r
    a = r["appraisal"]
    aid = a["id"]
    assert a["status"] == "draft" and a["mode"] == "customer_sent" and a["step"] == "mode" and a["contact_name"].startswith("Sarah")

    st, r = call("POST", f"/api/appraisals/{aid}/mode", {"mode": "customer_sent"}, hdrs)
    assert st == 200 and r["appraisal"]["step"] == "identity"

    # typed VIN: validation errors come back as data, not a 400
    st, r = call("POST", "/api/appraisals/vin/decode", {"vin": VIN[:-1] + "1"}, hdrs)
    assert st == 200 and not r["validation"]["valid"] and r["vehicle"] is None

    # customer-sent VIN photo (Code 39 label) -> barcode read, provenance preserved
    m = _upload(hdrs, aid, _barcode_png(VIN), "vin_photo", "customer_supplied", "vin.png")
    assert m["reading"]["vin"] == VIN and m["reading"]["method"] == "barcode" and m["reading"]["confidence"] == "high"
    assert m["source"] == "customer_supplied" and m["source_label"] == "Customer supplied" and m["uploaded_by"] == uid and m["thumb_url"]

    # confirm -> NHTSA decode -> vehicles doc
    st, r = call("POST", f"/api/appraisals/{aid}/vehicle", {"vin": m["reading"]["vin"], "method": "vin_photo"}, hdrs)
    assert st == 200, r
    veh = r["appraisal"]["vehicle_record"]
    assert veh["vin"] == VIN and veh["make"] == "Honda" and veh["model"] == "Accord" and veh["year"] == 2003 and veh["decoded_by"] == "nhtsa_vpic"
    assert r["appraisal"]["step"] == "mileage" and r["appraisal"]["identity_method"] == "vin_photo"
    vehicle_id = r["appraisal"]["vehicle_id"]

    # rep-captured odometer photo -> Jessi reads it, rep confirms
    if os.environ.get("EMERGENT_LLM_KEY") or _env("EMERGENT_LLM_KEY"):
        m2 = _upload(hdrs, aid, _odometer_png(47821), "odometer_photo", "captured_by_rep", "odo.png")
        assert m2["source"] == "captured_by_rep" and m2["role_label"] == "Odometer photo"
        assert m2["reading"]["mileage"] == 47821, m2["reading"]
        detected = m2["reading"]["mileage"]
    else:
        detected = None
    st, r = call("POST", f"/api/appraisals/{aid}/mileage", {"confirmed": 47821, "detected": detected, "source": "photo" if detected else "manual"}, hdrs)
    assert st == 200 and r["appraisal"]["mileage_confirmed"] == 47821 and r["appraisal"]["step"] == "inspection"

    st, r = call("POST", f"/api/appraisals/{aid}/expectation", {"asked": True, "value": 32000}, hdrs)
    assert st == 200 and r["appraisal"]["customer_expected_value"] == 32000 and r["appraisal"]["step"] == "review"

    st, d = call("GET", f"/api/appraisals/{aid}", headers=hdrs)
    assert st == 200 and d["vehicle_record"]["current_mileage"] == 47821
    assert any(h["id"] == aid for h in d["history"]), "the vehicle's history must include this appraisal (earlier runs may have left others)"
    sources = {x["source"] for x in d["media"]}
    assert "customer_supplied" in sources
    assert {x["action"] for x in d["activity"]} >= {"appraisal_started", "mode_set", "media_added", "vehicle_identified", "mileage_confirmed", "expectation_recorded"}

    # REAPPRAISE: same vehicle, new appraisal, VIN + vehicle carried, starts at mileage
    st, r = call("POST", "/api/appraisals", {"contact_id": SARAH, "vehicle_id": vehicle_id}, hdrs)
    assert st == 200, r
    re_ = r["appraisal"]
    assert re_["is_reappraisal"] and re_["vehicle_id"] == vehicle_id and re_["vin"] == VIN and re_["step"] == "mileage" and re_["previous_appraisal_id"] == aid
    st, v = call("GET", f"/api/appraisals/vehicles/{SARAH}", headers=hdrs)
    assert st == 200
    hondas = [x for x in v["vehicles"] if x["vin"] == VIN]
    assert len(hondas) == 1 and hondas[0]["appraisal_count"] >= 2 and len(hondas[0]["appraisals"]) >= 2

    # manual vehicle without a VIN never collides with the Honda
    st, r = call("POST", "/api/appraisals", {"contact_id": SARAH, "mode": "vehicle_here"}, hdrs)
    man_id = r["appraisal"]["id"]
    st, r = call("POST", f"/api/appraisals/{man_id}/vehicle", {"manual": {"year": 2019, "make": "Ford", "model": "F-150", "trim": "Lariat"}, "method": "manual_vehicle"}, hdrs)
    assert st == 200 and r["appraisal"]["vehicle_record"]["decoded_by"] == "manual" and r["appraisal"]["vehicle_record"]["vin"] is None
    assert r["appraisal"]["vehicle_id"] != vehicle_id

    # search by VIN, customer, vehicle
    for q in (VIN[-6:], "Sarah", "Accord"):
        st, lst = call("GET", f"/api/appraisals?q={q}", headers=hdrs)
        assert st == 200 and any(x["id"] == aid for x in lst["appraisals"]), q
    assert lst["counts"]["drafts"] >= 3

    # ---- isolation ----
    mh = auth(*login(*MANAGER))
    st, lst = call("GET", "/api/appraisals", headers=mh)
    assert st == 200 and any(x["id"] == aid for x in lst["appraisals"]), "store manager must see their rep's appraisal"
    st, _ = call("GET", f"/api/appraisals/{aid}", headers=mh)
    assert st == 200

    oh = auth(*login(*OTHER_ORG_ADMIN))
    st, lst = call("GET", "/api/appraisals", headers=oh)
    assert st == 200 and not any(x["id"] == aid for x in lst["appraisals"]), "another org must not list it"
    st, _ = call("GET", f"/api/appraisals/{aid}", headers=oh)
    assert st == 404
    st, _ = call("POST", f"/api/appraisals/{aid}/mileage", {"confirmed": 1}, oh)
    assert st == 404
    st, _ = call("GET", f"/api/appraisals/vehicles/{SARAH}", headers=oh)
    assert st == 404, "another org cannot read the contact's vehicles"

    nh = auth(*login(*NO_PERM_REP))
    st, body = call("GET", "/api/appraisals", headers=nh)
    assert st == 403 and "not switched on" in str(body)

    # cleanup drafts (soft delete); the Honda stays on Sarah as demo data
    for x in (aid, re_["id"], man_id):
        st, _ = call("DELETE", f"/api/appraisals/{x}", headers=hdrs)
        assert st == 200
    st, lst = call("GET", "/api/appraisals", headers=hdrs)
    assert not any(x["id"] in (aid, re_["id"], man_id) for x in lst["appraisals"])
