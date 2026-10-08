"""Voice into findings + trade-link pings + walkaround snapshots (Oct 8 2026).
- a voice note's words become PENDING findings (origin voice) that weigh nothing until confirmed; deleting the clip drops the unconfirmed ones
- the rep's inbox thread gets a system chip + a notification when the customer opens the link, when a burst of photos lands, when they submit
- a walkaround video's snapshots are pulled at upload time, listed on the appraisal, reused by the inspection run, re-pullable on demand
Fake transcription / fake extractor in-process; the snapshot case goes through the preview API like the MVP2 suite.
Run: cd /app/backend && set -a && . ./.env && set +a && python -m pytest tests/test_voice_findings_pings_snapshots.py -q"""
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
from services.appraisals import core, inspection, intake, voice, voice_findings  # noqa: E402

pytestmark = pytest.mark.asyncio
REP = ("activation-tester@invalid.imonsocial.test", "NewPass123!")
SARAH = "6aa413008f0d53e3f2261853"
FIX = "/app/backend/tests/fixtures/appraisal/"
TRANSCRIPT = "The AC blows warm when it idles, there is a dent in the passenger rear door and I think the brakes might be squealing a little. Runs great otherwise."
RAWS = [
    {"category": "mechanical", "subtype": "ac_heat", "location": "climate_control", "location_label": "Climate Control", "severity": "moderate", "confidence": "high", "quote": "The AC blows warm when it idles", "explanation": "AC not cooling at idle."},
    {"category": "body", "subtype": "dent", "location": "passenger_rear_door", "location_label": "Passenger Rear Door", "severity": "minor", "confidence": "high", "quote": "a dent in the passenger rear door", "explanation": "Dent on the door."},
    {"category": "mechanical", "subtype": "brakes", "location": "brakes", "location_label": "Brakes", "severity": "minor", "confidence": "low", "quote": "the brakes might be squealing a little", "explanation": "Possible brake noise."},
    {"category": "mechanical", "subtype": "transmission", "location": "transmission", "location_label": "Transmission", "severity": "major", "confidence": "high", "quote": "the transmission slips badly", "explanation": "not said"},
    {"category": "paint", "subtype": "x", "quote": "Runs great otherwise"},
]


async def _rep(db):
    return await db.users.find_one({"email": REP[0]})


async def _draft(db, me):
    contact = await db.contacts.find_one({"_id": ObjectId(SARAH)})
    return await core.create(db, me, contact, mode="vehicle_here")


async def _wipe(db, appr):
    aid = str(appr["_id"])
    await db[core.A].delete_one({"_id": appr["_id"]})
    for c in (inspection.FD, inspection.FR, inspection.INS, core.M, core.ACT):
        await db[c].delete_many({"appraisal_id": aid})
    await db.messages.delete_many({"appraisal_id": aid})
    await db.notifications.delete_many({"link": f"/appraisal/{aid}"})


# ---------- voice into findings ----------
async def test_voice_note_becomes_pending_findings_that_wait_for_the_rep(monkeypatch):
    db = get_db()
    me = await _rep(db)
    appr = await _draft(db, me)
    try:
        async def fake_transcribe(audio, filename):
            return TRANSCRIPT

        async def fake_extract(transcript, label):
            assert transcript == TRANSCRIPT
            return RAWS
        monkeypatch.setattr(voice, "transcribe", fake_transcribe)
        monkeypatch.setattr(voice_findings, "EXTRACTOR", fake_extract)
        monkeypatch.setattr(voice, "put_object", lambda *a, **k: None)
        vn = await voice.add_voice_note(db, appr, me, by="rep", data=b"\x00" * 2000, content_type="audio/mp4", duration=9.0)
        assert vn["transcribed"] and vn["findings_count"] == 3 and len(vn["findings"]) == 3, "the unsaid transmission line and the bad category are dropped"
        subs = sorted(f["subtype"] for f in vn["findings"])
        assert subs == ["ac_heat", "brakes", "dent"]
        ac = next(f for f in vn["findings"] if f["subtype"] == "ac_heat")
        assert ac["origin"] == "voice" and ac["decision"] == "pending" and ac["quote"] == "The AC blows warm when it idles" and ac["spoken_by"] == "rep" and ac["voice_note_id"] == vn["id"]
        assert ac["category_label"] == "Mechanical" and ac["subtype_label"] == "AC / Heat" and ac["evidence"] == []
        brakes = next(f for f in vn["findings"] if f["subtype"] == "brakes")
        assert brakes["possible"] is True, "hedged words read as a possible issue"
        fresh = await db[core.A].find_one({"_id": appr["_id"]})
        assert fresh["voice_notes"][0]["findings_count"] == 3 and "AC blows warm" in fresh["notes"]
        ins = await inspection.get_or_create(db, fresh)
        findings = await inspection.findings_for(db, ins)
        assert len(findings) == 3 and all(d["origin"] == "voice" for d in findings)
        assert inspection.grade(findings, final=True)["overall"] == "very_good", "nothing heard counts until a human confirms it"
        rd = await inspection.read(db, fresh)
        assert rd["report"] is not None and len(rd["report"]["pending"]) == 2 and len(rd["report"]["possible"]) == 1 and rd["coverage"] is None
        assert "mechanical" in rd["categories"] and "ac_heat" in rd["subtypes"]["mechanical"]
        ac_doc = next(d for d in findings if d["subtype"] == "ac_heat")
        await inspection.decide(db, ins, fresh, me, str(ac_doc["_id"]), "confirmed")
        findings = await inspection.findings_for(db, ins)
        g = inspection.grade(findings, final=True)
        assert g["categories"]["mechanical"] == "good" and g["overall"] == "good", "a confirmed moderate mechanical issue now weighs 2 points"
        ins2 = await db[inspection.INS].find_one({"_id": ins["_id"]})
        assert ins2["final_overall"] == "good"
        # Deleting the clip drops the two unconfirmed suggestions; the confirmed AC finding stays as the rep's decision.
        await voice.delete_voice_note(db, fresh, me, vn["id"])
        left = await inspection.findings_for(db, ins)
        assert [d["subtype"] for d in left] == ["ac_heat"] and left[0]["decision"] == "confirmed"
        after = await db[core.A].find_one({"_id": appr["_id"]})
        assert not after.get("voice_notes") and "AC blows warm" not in (after.get("notes") or "")
        acts = [a["action"] for a in await core.activity(db, appr)]
        assert "voice_findings_suggested" in acts and "voice_note_removed" in acts
    finally:
        await _wipe(db, appr)


async def test_quiet_or_positive_notes_make_no_findings(monkeypatch):
    db = get_db()
    me = await _rep(db)
    appr = await _draft(db, me)
    try:
        calls = []

        async def fake_extract(transcript, label):
            calls.append(transcript)
            return []
        monkeypatch.setattr(voice_findings, "EXTRACTOR", fake_extract)
        monkeypatch.setattr(voice, "put_object", lambda *a, **k: None)
        monkeypatch.setattr(voice, "transcribe", lambda *a, **k: asyncio.sleep(0, result="Runs great, super clean inside, two keys."))
        vn = await voice.add_voice_note(db, appr, me, by="rep", data=b"\x00" * 2000, content_type="audio/mp4", duration=4.0)
        assert vn["findings_count"] == 0 and vn["findings"] == [] and calls == ["Runs great, super clean inside, two keys."]
        monkeypatch.setattr(voice, "transcribe", lambda *a, **k: asyncio.sleep(0, result="Um."))
        vn2 = await voice.add_voice_note(db, appr, await db[core.A].find_one({"_id": appr["_id"]}), by="rep", data=b"\x00" * 2000, content_type="audio/mp4", duration=4.0)
        assert vn2["findings_count"] == 0 and len(calls) == 1, "too few words: the extractor is not even asked"
        assert await db[inspection.FD].count_documents({"appraisal_id": str(appr["_id"])}) == 0
    finally:
        await _wipe(db, appr)


# ---------- trade-link pings ----------
async def test_link_opened_photos_and_submit_land_in_the_thread(monkeypatch):
    db = get_db()
    me = await _rep(db)
    appr = await _draft(db, me)
    aid = str(appr["_id"])
    pushed = []

    async def fake_push(user_id, title, body, url="/", icon="flame", **k):
        pushed.append((user_id, title, body, url))
    import routers.push_notifications as pn
    monkeypatch.setattr(pn, "send_push_to_user", fake_push)
    monkeypatch.setattr(intake, "PHOTO_QUIET_S", 1)
    monkeypatch.setattr(core, "put_object", lambda *a, **k: None)
    monkeypatch.setattr(core, "_kick_snapshots", lambda *a, **k: None)
    t0 = core._now()
    conv = None
    try:
        await intake.create_link(db, appr, me, channel="copy")
        appr = await db[core.A].find_one({"_id": appr["_id"]})
        ctx = await intake.context(db, appr, mark_opened=True)
        assert ctx["state"] == "open"
        await asyncio.sleep(1.0)
        appr = await db[core.A].find_one({"_id": appr["_id"]})
        assert appr["intake"]["opened_at"]
        msgs = await db.messages.find({"appraisal_id": aid}).sort("timestamp", 1).to_list(20)
        assert len(msgs) == 1 and msgs[0]["sender"] == "system" and msgs[0]["kind"] == "trade_link_opened" and "opened the trade link" in msgs[0]["content"]
        conv = await db.conversations.find_one({"_id": ObjectId(msgs[0]["conversation_id"])})
        assert conv and conv["user_id"] == str(me["_id"]) and conv["contact_id"] == SARAH and conv["last_message_sender"] == "system"
        notes = await db.notifications.find({"user_id": str(me["_id"]), "link": f"/appraisal/{aid}"}).to_list(10)
        assert len(notes) == 1 and "opened your trade link" in notes[0]["title"] and notes[0]["type"] == "appraisal_intake"
        assert len(pushed) == 1 and pushed[0][0] == str(me["_id"]) and pushed[0][3] == f"/appraisal/{aid}"
        # A second open says nothing new.
        await intake.context(db, appr, mark_opened=True)
        await asyncio.sleep(0.5)
        assert await db.messages.count_documents({"appraisal_id": aid}) == 1
        # Three photos in a burst -> one chip, one notification, after the customer goes quiet.
        jpg = open(FIX + "front_driver.jpg", "rb").read()
        for i in range(3):
            appr = await db[core.A].find_one({"_id": appr["_id"]})
            await intake.add_photo(db, appr, role="exterior", data=jpg, content_type="image/jpeg", name=f"p{i}.jpg")
        appr = await db[core.A].find_one({"_id": appr["_id"]})
        assert appr["intake"]["photo_count"] == 3 and appr["intake"]["photo_burst"] == 3
        for _ in range(30):
            await asyncio.sleep(0.25)
            if await db.messages.count_documents({"appraisal_id": aid, "kind": "trade_link_photos"}):
                break
        photo_msgs = await db.messages.find({"appraisal_id": aid, "kind": "trade_link_photos"}).to_list(5)
        assert len(photo_msgs) == 1 and "sent 3 photos through the trade link" in photo_msgs[0]["content"]
        appr = await db[core.A].find_one({"_id": appr["_id"]})
        assert appr["intake"]["photo_burst"] == 0 and appr["intake"]["photo_count"] == 3
        assert len(pushed) == 2 and "sent 3 photos" in pushed[1][1]
        # Submit: one more chip with the summary; the existing rep notification still fires.
        r = await intake.submit(db, appr, {"mileage": 48900, "zip": "84070", "condition": {"overall": "good"}, "notes": "clean"})
        assert r["ok"]
        sub = await db.messages.find_one({"appraisal_id": aid, "kind": "trade_link_submitted"})
        assert sub and "submitted the trade link" in sub["content"] and "48,900 mi" in sub["content"] and "3 photos" in sub["content"]
        assert len(pushed) == 3 and pushed[2][1] == "Customer sent trade info"
        assert await db.messages.count_documents({"appraisal_id": aid}) == 3
    finally:
        await _wipe(db, appr)
        if conv and conv.get("created_at") and conv["created_at"].replace(tzinfo=t0.tzinfo) >= t0:
            await db.conversations.delete_one({"_id": conv["_id"]})


# ---------- walkaround snapshots ----------
def _upload(hdr, aid, path, role, source, name):
    data = base64.b64encode(open(path, "rb").read()).decode()
    piece, total, uid = 500_000, max(1, -(-len(data) // 500_000)), uuid.uuid4().hex[:12]
    last = None
    for i in range(total):
        st, last = call("POST", f"/api/appraisals/{aid}/media/chunk", {"upload_id": uid, "index": i, "total": total, "data": data[i * piece:(i + 1) * piece], "name": name, "content_type": "video/mp4", "role": role, "source": source}, hdr)
        assert st == 200, (st, last)
    return last["media"]


def _wait_ready(hdr, aid, mid, timeout=90):
    end = time.time() + timeout
    while time.time() < end:
        st, body = call("GET", f"/api/appraisals/{aid}/inspection", None, hdr)
        assert st == 200
        m = next(x for x in body["media"] if x["id"] == mid)
        if m["frames_status"] in ("ready", "failed"):
            return body, m
        time.sleep(2)
    raise AssertionError("snapshots never finished")


async def test_video_upload_pulls_snapshots_before_analyze_and_the_run_reuses_them(monkeypatch):
    hdr = auth(*login(*REP))
    db = get_db()
    st, b = call("POST", "/api/appraisals", {"contact_id": SARAH, "mode": "vehicle_here"}, hdr)
    assert st == 200, b
    aid = b["appraisal"]["id"]
    try:
        m = _upload(hdr, aid, FIX + "walkaround.mp4", "walkaround_video", "captured_by_rep", "walkaround.mp4")
        assert m["kind"] == "video" and m["frames_status"] == "extracting" and m["frame_count"] is None
        body, mv = _wait_ready(hdr, aid, m["id"])
        assert mv["frames_status"] == "ready" and 6 <= mv["frame_count"] <= 18 and body["status"] == "idle", "snapshots exist before anyone taps Analyze"
        snaps = body["snapshots"]
        assert len(snaps) == mv["frame_count"] and all(s["kind"] == "image" and s["snapshot"] and s["url"] and s["thumb_url"] and s["timestamp_label"] and s["media_id"] == m["id"] for s in snaps)
        assert snaps[0]["role"] == "walkaround_frame" and snaps[0]["source"] == "captured_by_rep" and snaps[0]["role_label"].startswith("Walk-around")
        assert [s["timestamp_s"] for s in snaps] == sorted(s["timestamp_s"] for s in snaps)
        st, detail = call("GET", f"/api/appraisals/{aid}", None, hdr)
        assert st == 200 and len(detail["snapshots"]) == len(snaps)
        acts = [a["action"] for a in detail["activity"]]
        assert "snapshots_extracted" in acts
        # The run reuses them: same frames, no duplicates, video marked processed.
        from test_appraisals_mvp2 import fake_jessi, ALL_AREAS, std_findings
        monkeypatch.setattr(inspection, "ANALYZER", fake_jessi(ALL_AREAS, std_findings))
        appr = await db[core.A].find_one({"_id": ObjectId(aid)})
        ins = await inspection.start_run(db, appr, await _rep(db), background=False)
        assert ins["status"] == "ready", ins.get("last_error")
        frames = await inspection.frames_for(db, ins)
        assert len(frames) == len(snaps) and {str(f["_id"]) for f in frames} == {s["id"] for s in snaps}
        assert m["id"] in ins["processed_media_ids"]
        # Re-pull on demand: old frames retire, new ones take their place, count stays sane.
        st, r = call("POST", f"/api/appraisals/{aid}/media/{m['id']}/snapshots", None, hdr)
        assert st == 200 and r["media"]["frames_status"] == "extracting"
        body2, mv2 = _wait_ready(hdr, aid, m["id"])
        assert mv2["frames_status"] == "ready" and 6 <= len(body2["snapshots"]) <= 18
        assert not ({s["id"] for s in body2["snapshots"]} & {s["id"] for s in snaps}), "retired frames are gone from the list"
        assert await db[inspection.FR].count_documents({"media_id": m["id"], "deleted": {"$ne": True}}) == len(body2["snapshots"])
        st, _ = call("POST", f"/api/appraisals/{aid}/media/{ObjectId()}/snapshots", None, hdr)
        assert st == 404
    finally:
        call("DELETE", f"/api/appraisals/{aid}", None, hdr)
