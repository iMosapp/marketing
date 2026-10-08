"""Trade Appraisal MVP2 - AI Vehicle Inspection. Media (recorded / imported / customer-sent video and photos) goes through ONE pipeline:
frames -> Jessi -> coverage -> findings with evidence -> human review -> condition report. Jessi is replaced by a deterministic fake here;
`test_real_jessi_on_photos` runs the real model when EMERGENT_LLM_KEY is present. Needs the running preview backend (uploads go through the API)."""
import asyncio
import base64
import os
import sys
import time
import uuid

import pytest
from bson import ObjectId
from dotenv import load_dotenv

sys.path.insert(0, "/app/backend")
sys.path.insert(0, "/app/backend/tests")
load_dotenv("/app/backend/.env")
from _http import call, login, auth  # noqa: E402
from routers.database import get_db  # noqa: E402
from services.appraisals import inspection, frames as fx  # noqa: E402

pytestmark = pytest.mark.asyncio

REP = ("activation-tester@invalid.imonsocial.test", "NewPass123!")
MANAGER = ("qa-manager@invalid.imonsocial.test", "Manager123!")
OTHER_ORG_ADMIN = ("qa-orgadmin@invalid.imonsocial.test", "OrgAdmin123!")
SARAH = "6aa413008f0d53e3f2261853"
FIX = "/app/backend/tests/fixtures/appraisal/"
PHOTOS = ["front_driver.jpg", "passenger_rear_dent.jpg", "wheel_curb_rash.jpg", "rear_bumper_scratches.jpg", "windshield_chip.jpg", "interior_seats.jpg"]


# ---------- helpers ----------
def _upload(hdr, aid, path, role, source, name=None, content_type=None):
    data = base64.b64encode(open(path, "rb").read()).decode()
    piece, total, uid = 500_000, max(1, -(-len(data) // 500_000)), uuid.uuid4().hex[:12]
    ct = content_type or ("video/mp4" if path.endswith(".mp4") else "image/jpeg")
    last = None
    for i in range(total):
        st, last = call("POST", f"/api/appraisals/{aid}/media/chunk", {"upload_id": uid, "index": i, "total": total, "data": data[i * piece:(i + 1) * piece],
                                                                       "name": name or os.path.basename(path), "content_type": ct, "role": role, "source": source}, hdr)
        assert st == 200, (st, last)
    return last["media"]


def _new_appraisal(hdr, mode="vehicle_here"):
    st, b = call("POST", "/api/appraisals", {"contact_id": SARAH, "mode": mode}, hdr)
    assert st == 200, (st, b)
    aid = b["appraisal"]["id"]
    st, _ = call("POST", f"/api/appraisals/{aid}/vehicle", {"manual": {"year": 2015, "make": "Honda", "model": "Accord", "trim": "EX"}, "method": "manual_vehicle"}, hdr)
    assert st == 200
    st, _ = call("POST", f"/api/appraisals/{aid}/mileage", {"confirmed": 61200, "source": "manual"}, hdr)
    assert st == 200
    return aid


def fake_jessi(areas_cycle, findings_per_batch):
    """areas_cycle: list of area lists handed out per image in order; findings_per_batch(batch_no, n_images) -> raw findings list."""
    state = {"batch": 0, "img": 0}

    async def _fake(label, items):
        out_frames = []
        for it in items:
            out_frames.append({"i": it["i"], "areas": areas_cycle[state["img"] % len(areas_cycle)], "usable": True})
            state["img"] += 1
        state["batch"] += 1
        return {"frames": out_frames, "findings": findings_per_batch(state["batch"], len(items)), "impression": f"fake impression {state['batch']}"}
    return _fake


ALL_AREAS = [["driver_front"], ["driver_side", "wheels"], ["driver_rear"], ["rear"], ["passenger_rear"], ["passenger_side", "wheels"], ["passenger_front"], ["front"],
             ["windshield"], ["interior", "seats"], ["dashboard"], ["wheels"]]
EXTERIOR_ONLY = [["driver_front"], ["driver_side"], ["rear"], ["passenger_side"], ["front"], ["wheels"]]


def std_findings(batch, n):
    if batch != 1:
        return []
    return [{"images": [1, 2], "category": "body", "subtype": "dent", "location": "passenger_rear_door", "location_label": "Passenger Rear Door", "severity": "minor", "confidence": "medium",
             "explanation": "Shallow dent below the handle."},
            {"images": [2], "category": "wheels_tires", "subtype": "curb_rash", "location": "driver_front_wheel", "location_label": "Driver Front Wheel", "severity": "moderate", "confidence": "high",
             "explanation": "Scrapes along the rim lip."},
            {"images": [3], "category": "glass", "subtype": "windshield_chip", "location": "windshield", "location_label": "Windshield", "severity": "minor", "confidence": "low",
             "explanation": "Small mark that may be a chip or a water spot."}]


@pytest.fixture(scope="module")
def rep():
    tok, uid = login(*REP)
    return auth(tok, uid)


@pytest.fixture(scope="module")
def other_org():
    tok, uid = login(*OTHER_ORG_ADMIN)
    return auth(tok, uid)


@pytest.fixture(scope="module")
def manager():
    tok, uid = login(*MANAGER)
    return auth(tok, uid)


async def _me(db):
    return await db.users.find_one({"email": REP[0]})


async def _run(db, aid, fake, monkeypatch):
    monkeypatch.setattr(inspection, "ANALYZER", fake)
    appr = await db.vehicle_appraisals.find_one({"_id": ObjectId(aid)})
    ins = await inspection.start_run(db, appr, await _me(db), background=False)
    assert ins["status"] == "ready", ins.get("last_error")
    return ins


def _cleanup(hdr, aid):
    call("DELETE", f"/api/appraisals/{aid}", None, hdr)


# ---------- frame extraction (pure) ----------
async def test_frame_extraction_dedupe_and_quality():
    r = fx.extract(open(FIX + "walkaround.mp4", "rb").read(), "mp4")
    assert r["duration"] == pytest.approx(18.0, abs=0.5)
    assert r["candidates"] >= 30 and r["duplicates_removed"] > 0 and 6 <= len(r["frames"]) <= fx.MAX_KEEP
    ts = [f["t"] for f in r["frames"]]
    assert ts == sorted(ts) and all(f["label"].count(":") == 1 for f in r["frames"])
    assert r["quality"] == "ok"
    bad = fx.extract(open(FIX + "blurry_walkaround.mp4", "rb").read(), "mp4")
    assert bad["quality"] == "poor" and bad["sharp"] == 0 and len(bad["frames"]) >= 1


async def test_grade_rules_match_the_spec_example():
    mk = lambda cat, sub, sev, conf, dec="pending", origin="ai": {"category": cat, "subtype": sub, "severity": sev, "confidence": conf, "decision": dec, "origin": origin}  # noqa: E731
    findings = [mk("wheels_tires", "curb_rash", "moderate", "high", "confirmed"), mk("body", "dent", "minor", "high", "confirmed"), mk("body", "scratch", "moderate", "high", "confirmed"),
                mk("glass", "windshield_chip", "minor", "low")]
    g = inspection.grade(findings, final=True)
    assert g["overall"] == "good"
    assert g["categories"] == {"body": "good", "interior": "very_good", "wheels_tires": "fair", "glass": "very_good", "mechanical": "very_good"}
    assert "Low-confidence findings" in g["reason"]
    assert inspection.grade([mk("body", "rust", "major", "high")], final=False)["overall"] == "fair"
    assert inspection.grade([mk("glass", "windshield_crack", "major", "high")], final=False)["categories"]["glass"] == "poor"
    assert inspection.grade([], final=True)["overall"] == "very_good"


# ---------- the pipeline over real uploads ----------
async def test_recorded_walkaround_video(rep, monkeypatch):
    db = get_db()
    aid = _new_appraisal(rep)
    try:
        m = _upload(rep, aid, FIX + "walkaround.mp4", "walkaround_video", "captured_by_rep", name="walkaround.mp4")
        assert m["kind"] == "video" and m["source"] == "captured_by_rep" and m["thumb_url"] and m["duration"] == pytest.approx(18, abs=0.5)
        ins = await _run(db, aid, fake_jessi(ALL_AREAS, std_findings), monkeypatch)
        frames = await inspection.frames_for(db, ins)
        assert 6 <= len(frames) <= fx.MAX_KEEP
        assert all(f["media_source"] == "captured_by_rep" and f["media_id"] == m["id"] and f["timestamp_label"] for f in frames)
        st, body = call("GET", f"/api/appraisals/{aid}/inspection", None, rep)
        assert st == 200 and body["status"] == "ready"
        video = next(x for x in body["media"] if x["id"] == m["id"])
        assert video["frame_count"] == len(frames) and video["extraction"]["duplicates_removed"] > 0 and video["video_quality"] == "ok"
        assert body["coverage"]["groups"]["exterior"]["status"] in ("complete", "partial")
        st, detail = call("GET", f"/api/appraisals/{aid}", None, rep)
        assert detail["status"] == "ready" and detail["inspection"]["status"] == "ready" and detail["step"] == "inspection"
    finally:
        _cleanup(rep, aid)


async def test_imported_walkaround_video_uses_the_same_pipeline(rep, monkeypatch):
    db = get_db()
    aid = _new_appraisal(rep)
    try:
        m = _upload(rep, aid, FIX + "walkaround.mp4", "walkaround_video", "uploaded_by_rep", name="IMG_2231.mp4")
        ins = await _run(db, aid, fake_jessi(ALL_AREAS, std_findings), monkeypatch)
        frames = await inspection.frames_for(db, ins)
        assert frames and all(f["media_source"] == "uploaded_by_rep" and f["media_name"] == "IMG_2231.mp4" for f in frames)
        findings = await inspection.findings_for(db, ins)
        assert len(findings) == 3 and all(e["media_source"] == "uploaded_by_rep" for d in findings for e in d["evidence"])
    finally:
        _cleanup(rep, aid)


async def test_customer_supplied_video_provenance_survives_to_evidence(rep, monkeypatch):
    db = get_db()
    aid = _new_appraisal(rep, mode="customer_sent")
    try:
        m = _upload(rep, aid, FIX + "walkaround.mp4", "walkaround_video", "customer_supplied", name="customer_walkaround.mov", content_type="video/quicktime")
        ins = await _run(db, aid, fake_jessi(ALL_AREAS, std_findings), monkeypatch)
        st, body = call("GET", f"/api/appraisals/{aid}/inspection", None, rep)
        dent = next(f for f in body["findings"] if f["subtype"] == "dent")
        assert dent["sources"] == ["customer_supplied"]
        ev = dent["evidence"][0]
        assert ev["media_id"] == m["id"] and ev["media_name"] == "customer_walkaround.mov" and ev["media_source"] == "customer_supplied"
        assert ev["timestamp_label"] and ev["thumb_url"] and ev["url"]
        assert body["report"]["pending"][0]["sources"] == ["customer_supplied"]
    finally:
        _cleanup(rep, aid)


async def test_imported_photos_become_frames_without_copies(rep, monkeypatch):
    db = get_db()
    aid = _new_appraisal(rep)
    try:
        ms = [_upload(rep, aid, FIX + p, "exterior" if "interior" not in p else "interior", "uploaded_by_rep") for p in PHOTOS[:3]]
        ins = await _run(db, aid, fake_jessi(ALL_AREAS, std_findings), monkeypatch)
        frames = await inspection.frames_for(db, ins)
        assert len(frames) == 3 and all(f["media_kind"] == "image" and f["timestamp_s"] is None for f in frames)
        paths = {f["path"] for f in frames}
        for m in ms:
            doc = await db.appraisal_media.find_one({"_id": ObjectId(m["id"])})
            assert doc["path"] in paths and doc["frame_count"] == 1
    finally:
        _cleanup(rep, aid)


async def test_mixed_customer_video_and_rep_photos_in_one_inspection(rep, monkeypatch):
    db = get_db()
    aid = _new_appraisal(rep, mode="customer_sent")
    try:
        _upload(rep, aid, FIX + "walkaround.mp4", "walkaround_video", "customer_supplied", name="from_customer.mp4")
        _upload(rep, aid, FIX + "wheel_curb_rash.jpg", "exterior", "captured_by_rep", name="tire.jpg")
        _upload(rep, aid, FIX + "interior_seats.jpg", "interior", "captured_by_rep", name="seats.jpg")

        def both(batch, n):
            return [{"images": [1, n], "category": "body", "subtype": "scratch", "location": "rear_bumper", "severity": "moderate", "confidence": "high", "explanation": "x"}] if batch == 1 else []
        ins = await _run(db, aid, fake_jessi(ALL_AREAS, both), monkeypatch)
        frames = await inspection.frames_for(db, ins)
        assert {f["media_source"] for f in frames} == {"customer_supplied", "captured_by_rep"}
        st, body = call("GET", f"/api/appraisals/{aid}/inspection", None, rep)
        assert len(body["findings"]) == 1 and len(body["media"]) == 3
    finally:
        _cleanup(rep, aid)


async def test_poor_quality_video_is_flagged(rep, monkeypatch):
    db = get_db()
    aid = _new_appraisal(rep)
    try:
        _upload(rep, aid, FIX + "blurry_walkaround.mp4", "walkaround_video", "captured_by_rep", name="shaky.mp4")
        await _run(db, aid, fake_jessi(EXTERIOR_ONLY, lambda b, n: []), monkeypatch)
        st, body = call("GET", f"/api/appraisals/{aid}/inspection", None, rep)
        assert body["media"][0]["video_quality"] == "poor" and body["report"]["poor_quality_media"] == ["shaky.mp4"]
    finally:
        _cleanup(rep, aid)


async def test_partial_coverage_is_named_but_not_blocking(rep, monkeypatch):
    db = get_db()
    aid = _new_appraisal(rep)
    try:
        _upload(rep, aid, FIX + "walkaround.mp4", "walkaround_video", "captured_by_rep")
        await _run(db, aid, fake_jessi(EXTERIOR_ONLY, lambda b, n: []), monkeypatch)
        st, body = call("GET", f"/api/appraisals/{aid}/inspection", None, rep)
        cov = body["coverage"]
        assert cov["groups"]["interior"]["status"] == "missing" and set(cov["groups"]["interior"]["missing"]) == {"Interior", "Dashboard", "Seats"}
        assert cov["groups"]["glass"]["status"] == "missing" and cov["groups"]["exterior"]["status"] in ("partial", "complete")
        assert "Seats" in cov["missing"] and cov["sufficient"] is True
        assert body["report"]["final_overall"] == "very_good"
        st, _ = call("PATCH", f"/api/appraisals/{aid}", {"step": "expectation"}, rep)
        assert st == 200
    finally:
        _cleanup(rep, aid)


async def test_findings_review_confirm_dismiss_edit_add_override(rep, manager, monkeypatch):
    db = get_db()
    aid = _new_appraisal(rep)
    try:
        _upload(rep, aid, FIX + "walkaround.mp4", "walkaround_video", "captured_by_rep")
        await _run(db, aid, fake_jessi(ALL_AREAS, std_findings), monkeypatch)
        st, body = call("GET", f"/api/appraisals/{aid}/inspection", None, rep)
        by = {f["subtype"]: f for f in body["findings"]}
        dent, rash, chip = by["dent"], by["curb_rash"], by["windshield_chip"]
        # AI detected vs possible
        assert dent["decision"] == "pending" and dent["possible"] is False and chip["possible"] is True and chip["confidence"] == "low"
        rep_ = body["report"]
        assert len(rep_["pending"]) == 2 and len(rep_["possible"]) == 1 and rep_["ai_overall"] == "good" and rep_["categories"]["wheels_tires"]["final"] == "fair"
        # confirm
        st, r = call("POST", f"/api/appraisals/{aid}/inspection/findings/{rash['id']}/decision", {"decision": "confirmed"}, rep)
        assert st == 200 and r["finding"]["decision"] == "confirmed" and r["finding"]["decision_by_name"]
        # dismiss -> drops out of the grade
        st, r = call("POST", f"/api/appraisals/{aid}/inspection/findings/{dent['id']}/decision", {"decision": "dismissed"}, rep)
        assert st == 200 and r["finding"]["decision"] == "dismissed"
        st, body = call("GET", f"/api/appraisals/{aid}/inspection", None, rep)
        assert body["report"]["dismissed_count"] == 1 and body["report"]["categories"]["body"]["final"] == "very_good" and body["report"]["categories"]["body"]["ai"] == "good"
        # edit keeps the AI original
        st, r = call("PATCH", f"/api/appraisals/{aid}/inspection/findings/{rash['id']}", {"severity": "major", "location_label": "Driver Front Wheel (inner lip)"}, rep)
        assert st == 200 and r["finding"]["severity"] == "major" and r["finding"]["edited"] is True and r["finding"]["ai_original"]["severity"] == "moderate"
        doc = await db.appraisal_findings.find_one({"_id": ObjectId(rash["id"])})
        assert doc["edit_history"][0]["before"]["severity"] == "moderate" and doc["edited_by_name"]
        # add a human issue with evidence
        st, r = call("POST", f"/api/appraisals/{aid}/inspection/findings", {"category": "interior", "subtype": "stain", "location_label": "Rear Seat", "severity": "minor",
                                                                             "explanation": "Coffee stain", "frame_ids": [body["frames"][0]["id"]]}, rep)
        assert st == 200 and r["finding"]["origin"] == "human" and r["finding"]["decision"] == "confirmed" and len(r["finding"]["evidence"]) == 1
        st, r = call("POST", f"/api/appraisals/{aid}/inspection/findings", {"category": "interior", "severity": "minor"}, rep)
        assert st == 400
        st, body = call("GET", f"/api/appraisals/{aid}/inspection", None, rep)
        assert body["report"]["categories"]["wheels_tires"]["final"] == "poor" and body["report"]["final_overall"] == "fair"
        # manager override + audit
        st, r = call("POST", f"/api/appraisals/{aid}/inspection/override", {"overall": "good", "reason": "Wheel is being refinished before retail"}, manager)
        assert st == 200 and r["report"]["final_overall"] == "good" and r["report"]["overridden"] and r["report"]["override"]["by_name"] and r["report"]["computed_overall"] == "fair"
        st, r = call("POST", f"/api/appraisals/{aid}/inspection/override", {"overall": "good", "reason": ""}, manager)
        assert st == 400
        st, r = call("POST", f"/api/appraisals/{aid}/inspection/override", {"overall": None}, manager)
        assert st == 200 and r["report"]["overridden"] is False and r["report"]["final_overall"] == "fair"
        st, detail = call("GET", f"/api/appraisals/{aid}", None, rep)
        acts = [a["action"] for a in detail["activity"]]
        for a in ("inspection_started", "inspection_completed", "finding_confirmed", "finding_dismissed", "finding_edited", "finding_added", "condition_overridden", "condition_override_cleared"):
            assert a in acts, a
    finally:
        _cleanup(rep, aid)


async def test_retry_after_failure_does_not_duplicate_findings(rep, monkeypatch):
    db = get_db()
    aid = _new_appraisal(rep)
    try:
        _upload(rep, aid, FIX + "walkaround.mp4", "walkaround_video", "captured_by_rep")

        async def boom(label, items):
            raise RuntimeError("vision timeout")
        monkeypatch.setattr(inspection, "ANALYZER", boom)
        appr = await db.vehicle_appraisals.find_one({"_id": ObjectId(aid)})
        ins = await inspection.start_run(db, appr, await _me(db), background=False)
        assert ins["status"] == "failed" and "vision timeout" in ins["last_error"]
        appr = await db.vehicle_appraisals.find_one({"_id": ObjectId(aid)})
        assert appr["status"] == "draft"
        n_frames = len(await inspection.frames_for(db, ins))
        assert n_frames > 0
        # retry: frames reused, findings created once
        ins = await _run(db, aid, fake_jessi(ALL_AREAS, std_findings), monkeypatch)
        assert len(await inspection.frames_for(db, ins)) == n_frames and ins["run_count"] == 2
        f1 = await inspection.findings_for(db, ins)
        assert len(f1) == 3
        rash = next(d for d in f1 if d["subtype"] == "curb_rash")
        await inspection.decide(db, ins, appr, await _me(db), str(rash["_id"]), "confirmed")
        # run again (same issues, Jessi now says the rash is minor) -> still 3, the human decision stands
        ins = await _run(db, aid, fake_jessi(ALL_AREAS, lambda b, n: [dict(x, severity="minor") for x in std_findings(b, n)]), monkeypatch)
        f2 = await inspection.findings_for(db, ins)
        assert len(f2) == 3 and ins["run_count"] == 3
        rash2 = next(d for d in f2 if d["subtype"] == "curb_rash")
        assert rash2["decision"] == "confirmed" and rash2["severity"] == "moderate"
        dent2 = next(d for d in f2 if d["subtype"] == "dent")
        assert len(dent2["evidence"]) == len({e["frame_id"] for e in dent2["evidence"]})
    finally:
        _cleanup(rep, aid)


async def test_cross_store_access_blocked(rep, other_org, monkeypatch):
    db = get_db()
    aid = _new_appraisal(rep)
    try:
        m = _upload(rep, aid, FIX + "front_driver.jpg", "exterior", "captured_by_rep")
        await _run(db, aid, fake_jessi(ALL_AREAS, std_findings), monkeypatch)
        st, body = call("GET", f"/api/appraisals/{aid}/inspection", None, rep)
        fid = body["findings"][0]["id"]
        for method, path, payload in (("GET", f"/api/appraisals/{aid}/media", None), ("DELETE", f"/api/appraisals/{aid}/media/{m['id']}", None),
                                      ("GET", f"/api/appraisals/{aid}/inspection", None), ("POST", f"/api/appraisals/{aid}/inspection/run", None),
                                      ("POST", f"/api/appraisals/{aid}/inspection/findings/{fid}/decision", {"decision": "confirmed"}),
                                      ("PATCH", f"/api/appraisals/{aid}/inspection/findings/{fid}", {"severity": "major"}),
                                      ("POST", f"/api/appraisals/{aid}/inspection/findings", {"category": "body", "location_label": "Hood"}),
                                      ("POST", f"/api/appraisals/{aid}/inspection/override", {"overall": "poor", "reason": "nope"})):
            st, _ = call(method, path, payload, other_org)
            assert st in (403, 404), (method, path, st)
        doc = await db.appraisal_findings.find_one({"_id": ObjectId(fid)})
        assert doc["decision"] == "pending" and doc["severity"] != "major"
    finally:
        _cleanup(rep, aid)


async def test_media_delete_removes_frames_and_retention_off_destroys_original(rep, monkeypatch):
    db = get_db()
    aid = _new_appraisal(rep)
    try:
        v = _upload(rep, aid, FIX + "walkaround.mp4", "walkaround_video", "captured_by_rep")
        p = _upload(rep, aid, FIX + "front_driver.jpg", "exterior", "captured_by_rep")

        async def org_off(db_, ins_):
            return (False, 365)
        monkeypatch.setattr(inspection, "_org_retains", org_off)
        ins = await _run(db, aid, fake_jessi(ALL_AREAS, std_findings), monkeypatch)
        vdoc = await db.appraisal_media.find_one({"_id": ObjectId(v["id"])})
        assert vdoc["original_available"] is False and vdoc["original_destroyed_reason"] == "org_retention_off"
        frames = [f for f in await inspection.frames_for(db, ins) if f["media_id"] == v["id"]]
        assert frames and all(not f.get("deleted") for f in frames)
        st, body = call("GET", f"/api/appraisals/{aid}/inspection", None, rep)
        vid = next(x for x in body["media"] if x["id"] == v["id"])
        assert vid["url"] is None and vid["original_available"] is False and vid["thumb_url"]
        assert all(f["thumb_url"] for f in body["frames"])
        # delete the photo -> its frame goes
        st, r = call("DELETE", f"/api/appraisals/{aid}/media/{p['id']}", None, rep)
        assert st == 200 and all(x["id"] != p["id"] for x in r["media"])
        assert not [f for f in await inspection.frames_for(db, ins) if f["media_id"] == p["id"]]
    finally:
        _cleanup(rep, aid)


async def test_org_policy_resolves_through_the_store():
    db = get_db()
    me = await db.users.find_one({"email": REP[0]})
    retain, days = await inspection._org_retains(db, {"organization_id": None, "store_id": str(me["store_id"])})
    assert retain is True and days == 365


@pytest.mark.skipif(not os.environ.get("EMERGENT_LLM_KEY"), reason="needs the vision model")
async def test_real_jessi_on_photos(rep):
    """End to end through the API with the real model: six photos of a silver Accord with a dent, curb rash and a windshield chip."""
    aid = _new_appraisal(rep)
    try:
        for p in PHOTOS:
            _upload(rep, aid, FIX + p, "interior" if "interior" in p or "windshield" in p else "exterior", "uploaded_by_rep")
        st, r = call("POST", f"/api/appraisals/{aid}/inspection/run", None, rep)
        assert st == 200 and r["status"] in ("queued", "processing")
        st, r = call("POST", f"/api/appraisals/{aid}/inspection/run", None, rep)
        assert st == 409
        for _ in range(60):
            time.sleep(3)
            st, body = call("GET", f"/api/appraisals/{aid}/inspection", None, rep)
            if body["status"] in ("ready", "failed"):
                break
        assert body["status"] == "ready", body.get("last_error")
        assert len(body["frames"]) == 6 and all(f["areas"] for f in body["frames"])
        assert body["findings"], "Jessi should see at least the dent / curb rash / chip"
        assert all(f["evidence"] and f["explanation"] and f["confidence"] in ("high", "medium", "low") for f in body["findings"])
        cats = {f["category"] for f in body["findings"]}
        assert cats & {"body", "wheels_tires", "glass"}
        assert body["report"]["ai_overall"] in ("very_good", "good", "fair", "poor") and body["report"]["reason"]
        assert body["coverage"]["groups"]["wheels"]["status"] != "missing"
    finally:
        _cleanup(rep, aid)
