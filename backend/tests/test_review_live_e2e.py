"""Live-API e2e check for the Jan 2026 review:
seeded appraisal shape, snapshots retry, TTS voice note end-to-end, trade-link pings (open+photos+submit).
Run: cd /app/backend && set -a && . ./.env && set +a && python -m pytest tests/test_review_live_e2e.py -q
"""
import asyncio
import base64
import io
import os
import sys
import time
import uuid

import pytest
import requests
from bson import ObjectId
from dotenv import load_dotenv

sys.path.insert(0, "/app/backend")
sys.path.insert(0, "/app/backend/tests")
load_dotenv("/app/backend/.env")
from _http import API, call, login, auth  # noqa: E402

REP = ("activation-tester@invalid.imonsocial.test", "NewPass123!")
MANAGER = ("qa-manager@invalid.imonsocial.test", "Manager123!")
ORGADMIN = ("qa-orgadmin@invalid.imonsocial.test", "OrgAdmin123!")
SARAH = "6aa413008f0d53e3f2261853"
SEEDED = "6ac80f67a2136477f78ca87d"
FIX = "/app/backend/tests/fixtures/appraisal/"


@pytest.fixture(scope="module")
def rep():
    return auth(*login(*REP))


@pytest.fixture(scope="module")
def manager():
    return auth(*login(*MANAGER))


@pytest.fixture(scope="module")
def orgadmin():
    return auth(*login(*ORGADMIN))


# ---------- seeded shape ----------
def test_seeded_appraisal_has_snapshots_and_voice_findings(rep):
    st, b = call("GET", f"/api/appraisals/{SEEDED}", None, rep)
    assert st == 200, b
    snaps = b["snapshots"]
    assert len(snaps) == 10, f"expected 10 snapshots got {len(snaps)}"
    video_id = None
    for m in b["media"]:
        if m.get("kind") == "video":
            video_id = m["id"]
            assert m["frames_status"] == "ready" and m["frame_count"] == 10
    assert video_id, "walkaround video missing"
    for s in snaps:
        assert s["kind"] == "image" and s["snapshot"] is True
        assert s["role"] == "walkaround_frame"
        assert s["url"].startswith("/api/images/") and s["thumb_url"].startswith("/api/images/")
        assert s["timestamp_label"] and s["media_id"] == video_id
    assert b["voice_notes"] and b["voice_notes"][0]["findings_count"] == 3


def test_seeded_inspection_shape(rep):
    st, b = call("GET", f"/api/appraisals/{SEEDED}/inspection", None, rep)
    assert st == 200, b
    assert len(b["snapshots"]) == 10
    findings = b["findings"]
    assert len(findings) == 3
    for f in findings:
        assert f["origin"] == "voice"
        assert f.get("spoken_by") == "rep"
        assert f.get("quote")
        assert f.get("voice_note_id")
        assert f["decision"] == "pending"
    assert "mechanical" in b["categories"]
    assert "ac_heat" in b["subtypes"].get("mechanical", [])
    assert b["report"] is not None
    assert b.get("coverage") is None
    assert b["status"] == "idle"


# ---------- snapshots retry (seeded video) ----------
def test_snapshots_retry_route(rep, manager):
    st, b = call("GET", f"/api/appraisals/{SEEDED}", None, rep)
    video = next(m for m in b["media"] if m.get("kind") == "video")
    mid = video["id"]
    before_ids = {s["id"] for s in b["snapshots"]}

    st, r = call("POST", f"/api/appraisals/{SEEDED}/media/{mid}/snapshots", None, rep)
    assert st == 200, r
    assert r["media"]["frames_status"] == "extracting"

    # poll inspection for ready
    end = time.time() + 90
    final = None
    while time.time() < end:
        st, body = call("GET", f"/api/appraisals/{SEEDED}/inspection", None, rep)
        assert st == 200
        m = next(x for x in body["media"] if x["id"] == mid)
        if m["frames_status"] in ("ready", "failed"):
            final = (body, m)
            break
        time.sleep(2)
    assert final, "snapshots never finished re-extracting"
    body, m = final
    assert m["frames_status"] == "ready"
    assert 6 <= len(body["snapshots"]) <= 18
    after_ids = {s["id"] for s in body["snapshots"]}
    assert not (before_ids & after_ids), "retried frames should have new ids"

    # bogus id -> 404
    st, _ = call("POST", f"/api/appraisals/{SEEDED}/media/{ObjectId()}/snapshots", None, rep)
    assert st == 404

    # other-org admin -> 404/403 (orgadmin fixture)
    # (use a fresh client because orgadmin fixture isn't passed into this test; grab inline)
    oa = auth(*login(*ORGADMIN))
    st, _ = call("POST", f"/api/appraisals/{SEEDED}/media/{mid}/snapshots", None, oa)
    assert st in (403, 404), f"other-org should not access, got {st}"


# ---------- TTS -> voice findings end-to-end ----------
def _speech(text: str) -> bytes:
    from emergentintegrations.llm.openai import OpenAITextToSpeech

    async def go():
        return await OpenAITextToSpeech(api_key=os.environ["EMERGENT_LLM_KEY"]).generate_speech(
            text=text, model="tts-1", voice="alloy", speed=1.0, response_format="mp3"
        )
    return asyncio.run(go())


def _chunks(aid: str, audio: bytes, headers: dict, piece: int = 60_000, duration: float = 8.0):
    b64 = base64.b64encode(audio).decode()
    total = max(1, (len(b64) + piece - 1) // piece)
    uid = f"qa{uuid.uuid4().hex[:8]}"
    last = None
    for i in range(total):
        st, last = call(
            "POST", f"/api/appraisals/{aid}/voice-note/chunk",
            {"upload_id": uid, "index": i, "total": total, "data": b64[i * piece:(i + 1) * piece],
             "content_type": "audio/mpeg", "duration": duration},
            headers,
        )
        assert st == 200, (st, last)
    return last


def test_voice_note_real_speech_creates_findings_and_delete_drops_them(rep):
    st, b = call("POST", "/api/appraisals", {"contact_id": SARAH, "mode": "vehicle_here"}, rep)
    assert st == 200, b
    aid = b["appraisal"]["id"]
    try:
        text = ("The check engine light is on and the rear bumper has a big dent. "
                "The AC works great.")
        audio = _speech(text)
        out = _chunks(aid, audio, rep, duration=9.0)
        vn = out["voice_note"]
        assert vn["transcribed"]
        assert vn["findings_count"] >= 1, vn
        transcript = vn["transcript"].lower()
        for f in vn["findings"]:
            # quote should be a substring of what was heard
            q = (f.get("quote") or "").lower()
            assert q and q in transcript, (q, transcript)
            assert f["decision"] == "pending"
            assert f["origin"] == "voice"

        # inspection shows them too
        st, insp = call("GET", f"/api/appraisals/{aid}/inspection", None, rep)
        assert st == 200
        assert len(insp["findings"]) == vn["findings_count"]
        assert all(x["origin"] == "voice" for x in insp["findings"])

        # delete the voice note -> findings gone
        st, _ = call("DELETE", f"/api/appraisals/{aid}/voice-note/{vn['id']}", None, rep)
        assert st == 200
        st, insp2 = call("GET", f"/api/appraisals/{aid}/inspection", None, rep)
        assert st == 200
        assert insp2["findings"] == []
    finally:
        call("DELETE", f"/api/appraisals/{aid}", None, rep)


# ---------- trade link pings end-to-end ----------
def _preview_host():
    return API  # same preview host


def test_trade_link_open_photos_submit_chips(rep):
    st, b = call("POST", "/api/appraisals", {"contact_id": SARAH, "mode": "vehicle_here"}, rep)
    assert st == 200, b
    aid = b["appraisal"]["id"]
    try:
        st, link = call("POST", f"/api/appraisals/{aid}/intake-link", {"channel": "copy"}, rep)
        assert st == 200, link
        url = link["intake"]["url"]
        assert "/api/public/trade/" in url
        token = url.rstrip("/").split("/")[-1]
        base = _preview_host()

        # open link (GET HTML)
        r = requests.get(f"{base}/api/public/trade/{token}",
                         headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        assert r.status_code == 200, r.text[:200]

        # poll notifications collection directly (notifications_center has 30s cache)
        from routers.database import get_db  # noqa
        db = get_db()
        rep_uid = rep["X-User-ID"]

        async def _wait_notif(kinds_or_links):
            end = time.time() + 15
            while time.time() < end:
                doc = await db.notifications.find_one({"user_id": rep_uid, "link": f"/appraisal/{aid}", "type": "appraisal_intake"})
                if doc:
                    return doc
                await asyncio.sleep(1)
            return None

        opened_notif = asyncio.get_event_loop().run_until_complete(_wait_notif(None)) \
            if False else asyncio.new_event_loop().run_until_complete(_wait_notif(None))
        assert opened_notif, "rep notification for link opened not found"
        assert "opened your trade link" in opened_notif["title"].lower()

        # find thread -> last message system / trade_link_opened
        st, convs = call("GET", f"/api/messages/conversations/{rep_uid}", None, rep)
        assert st == 200, convs
        if isinstance(convs, list):
            clist = convs
        else:
            clist = convs.get("conversations") or convs.get("items") or []
        conv = next((c for c in clist if c.get("contact_id") == SARAH and str(c.get("user_id") or "") == rep_uid), None)
        if not conv:
            conv = next((c for c in clist if c.get("contact_id") == SARAH), None)
        assert conv, "sarah conversation not found"
        conv_id = conv.get("_id") or conv.get("id")
        st, thread = call("GET", f"/api/messages/thread/{conv_id}", None, rep)
        if st == 403:
            pytest.skip("shared-inbox thread (403); routing covered by unit test")
        assert st == 200, thread
        if isinstance(thread, dict):
            msgs = thread.get("messages", [])
        else:
            msgs = thread
        last = msgs[-1]
        assert last["sender"] == "system"
        # NOTE: thread serializer does not expose `kind` field. We verify via content.
        assert "opened the trade link" in last["content"]
        baseline_ids = {m["_id"] for m in msgs}

        # upload 2 photos via public page
        for i in range(2):
            with open(FIX + "front_driver.jpg", "rb") as fh:
                files = {"file": (f"p{i}.jpg", fh, "image/jpeg")}
                rr = requests.post(f"{base}/api/public/trade/{token}/photo",
                                   data={"role": "exterior"}, files=files,
                                   headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
                assert rr.status_code == 200, rr.text[:200]

        # wait up to ~95s for burst announce (PHOTO_QUIET_S=40 in prod + buffer)
        end = time.time() + 95
        photos_msg = None
        while time.time() < end:
            st, thread = call("GET", f"/api/messages/thread/{conv_id}", None, rep)
            assert st == 200
            msgs = thread.get("messages", []) if isinstance(thread, dict) else thread
            for m in reversed(msgs):
                if m["_id"] in baseline_ids:
                    continue
                if m.get("sender") == "system" and "photos through the trade link" in (m.get("content") or ""):
                    photos_msg = m
                    break
            if photos_msg:
                break
            time.sleep(3)
        assert photos_msg, "trade_link_photos chip did not land"
        assert "2 photos" in photos_msg["content"] and "trade link" in photos_msg["content"]
        baseline_ids.add(photos_msg["_id"])

        # submit
        rr = requests.post(f"{base}/api/public/trade/{token}/submit",
                           json={"mileage": 48900, "zip": "84070",
                                 "condition": {"overall": "good"}, "notes": "clean"},
                           headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        assert rr.status_code == 200, rr.text[:200]

        # thread has submitted chip
        end = time.time() + 15
        submitted = None
        while time.time() < end:
            st, thread = call("GET", f"/api/messages/thread/{conv_id}", None, rep)
            msgs = thread.get("messages", []) if isinstance(thread, dict) else thread
            for m in reversed(msgs):
                if m["_id"] in baseline_ids:
                    continue
                if m.get("sender") == "system" and "submitted the trade link" in (m.get("content") or ""):
                    submitted = m
                    break
            if submitted:
                break
            time.sleep(1)
        assert submitted, "trade_link_submitted chip did not land"
        content = submitted["content"]
        assert "submitted the trade link" in content
        assert "48,900 mi" in content, f"mileage not propagated: {content}"
        assert "2 photos" in content, f"photo count not reported: {content}"
    finally:
        call("DELETE", f"/api/appraisals/{aid}", None, rep)
