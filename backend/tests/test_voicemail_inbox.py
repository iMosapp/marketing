"""Voicemail inbox: unanswered call -> missed row -> recording upgrades it -> transcript -> scope/heard/delete.

Hits the running API (REACT_APP_BACKEND_URL). Fake recording URLs: Whisper fails gracefully, Twilio's transcription fills the text.
"""
import os
import time

import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
FOREST_LINE = "+14352203414"
RUN = str(int(time.time()))


@pytest.fixture(scope="module")
def admin_headers():
    r = requests.post(f"{BASE}/api/auth/login", json={"email": "forest@imosapp.com", "password": "Admin123!"}, timeout=30)
    r.raise_for_status()
    tok = r.json().get("token") or r.json().get("access_token")
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def rep_headers():
    r = requests.post(f"{BASE}/api/auth/login", json={"email": "activation-tester@invalid.imonsocial.test", "password": "NewPass123!"}, timeout=30)
    if r.status_code != 200:
        pytest.skip("rep test account unavailable")
    tok = r.json().get("token") or r.json().get("access_token")
    return {"Authorization": f"Bearer {tok}"}


def _fallback(call_sid, frm, status="no-answer"):
    r = requests.post(f"{BASE}/api/webhooks/twilio/voice-fallback", data={"DialCallStatus": status, "To": FOREST_LINE, "From": frm, "CallSid": call_sid}, timeout=30)
    assert r.status_code == 200
    return r.text


def _inbox(headers, **params):
    r = requests.get(f"{BASE}/api/voicemails", headers=headers, params=params, timeout=30)
    assert r.status_code == 200
    return r.json()


def _row(headers, call_sid_marker):
    return next((i for i in _inbox(headers)["items"] if i["from_phone"].endswith(call_sid_marker)), None)


def test_unanswered_call_lands_as_missed_then_becomes_voicemail(admin_headers):
    sid = f"CAvm_{RUN}_a"
    twiml = _fallback(sid, "+15005550101")
    assert "<Record" in twiml and "voicemail-recording?" in twiml and "from=%2B15005550101" in twiml and "transcribeCallback" in twiml

    row = _row(admin_headers, "0101")
    assert row and row["kind"] == "missed" and row["heard"] is False and row["line_label"] == "Your line" and row["play_url"] is None

    r = requests.post(f"{BASE}/api/webhooks/twilio/voicemail-recording", params={"from": "+15005550101", "to": FOREST_LINE},
                      data={"RecordingUrl": f"https://api.twilio.com/2010-04-01/Accounts/ACx/Recordings/RE{RUN}a", "RecordingSid": f"RE{RUN}a",
                            "RecordingDuration": "37", "RecordingStatus": "completed", "CallSid": sid}, timeout=30)
    assert r.status_code == 200
    time.sleep(1.5)
    row = _row(admin_headers, "0101")
    assert row["kind"] == "voicemail" and row["duration"] == 37 and row["duration_display"] == "0:37"
    assert row["play_url"] and "media-proxy" in row["play_url"] and row["play_url"].endswith(".mp3")

    # Twilio's transcription arrives (Whisper could not fetch the fake file)
    r = requests.post(f"{BASE}/api/webhooks/twilio/voicemail-transcription",
                      data={"TranscriptionText": "Hi Forest, it's Sam about the truck.", "TranscriptionStatus": "completed", "CallSid": sid,
                            "From": "+15005550101", "To": FOREST_LINE, "RecordingUrl": f"https://api.twilio.com/2010-04-01/Accounts/ACx/Recordings/RE{RUN}a"}, timeout=30)
    assert r.status_code == 200
    row = _row(admin_headers, "0101")
    assert row["transcript"] == "Hi Forest, it's Sam about the truck." and row["transcript_status"] == "done"


def test_tiny_recording_stays_a_missed_call(admin_headers):
    sid = f"CAvm_{RUN}_b"
    _fallback(sid, "+15005550102", status="busy")
    r = requests.post(f"{BASE}/api/webhooks/twilio/voicemail-recording", params={"from": "+15005550102", "to": FOREST_LINE},
                      data={"RecordingUrl": "https://api.twilio.com/x/RE1", "RecordingSid": "RE1", "RecordingDuration": "1", "RecordingStatus": "completed", "CallSid": sid}, timeout=30)
    assert r.status_code == 200
    row = _row(admin_headers, "0102")
    assert row["kind"] == "missed" and row["play_url"] is None


def test_webhooks_are_idempotent(admin_headers):
    sid = f"CAvm_{RUN}_c"
    _fallback(sid, "+15005550103")
    _fallback(sid, "+15005550103")
    for _ in range(2):
        requests.post(f"{BASE}/api/webhooks/twilio/voicemail-recording", params={"from": "+15005550103", "to": FOREST_LINE},
                      data={"RecordingUrl": "https://api.twilio.com/x/RE2", "RecordingSid": "RE2", "RecordingDuration": "12", "RecordingStatus": "completed", "CallSid": sid}, timeout=30)
    rows = [i for i in _inbox(admin_headers)["items"] if i["from_phone"].endswith("0103")]
    assert len(rows) == 1 and rows[0]["kind"] == "voicemail"


def test_lines_and_unheard_counts(admin_headers):
    data = _inbox(admin_headers)
    line = next(l for l in data["lines"] if l["phone"] == FOREST_LINE)
    assert line["label"] == "Your line" and line["unheard"] >= 3 and data["unheard"] >= line["unheard"]
    filtered = _inbox(admin_headers, line=FOREST_LINE)
    assert filtered["items"] and all(i["to_phone"] == FOREST_LINE for i in filtered["items"])
    r = requests.get(f"{BASE}/api/voicemails/unheard-count", headers=admin_headers, timeout=30)
    assert r.status_code == 200 and r.json()["unheard"] == data["unheard"]


def test_heard_and_delete(admin_headers):
    row = _row(admin_headers, "0101")
    before = _inbox(admin_headers)["unheard"]
    r = requests.post(f"{BASE}/api/voicemails/{row['id']}/heard", headers=admin_headers, timeout=30)
    assert r.status_code == 200 and r.json()["unheard"] == before - 1
    assert _row(admin_headers, "0101")["heard"] is True
    # heard twice is a no-op
    r = requests.post(f"{BASE}/api/voicemails/{row['id']}/heard", headers=admin_headers, timeout=30)
    assert r.json()["unheard"] == before - 1

    for marker in ("0101", "0102", "0103"):
        rr = _row(admin_headers, marker)
        r = requests.delete(f"{BASE}/api/voicemails/{rr['id']}", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        assert _row(admin_headers, marker) is None
    r = requests.delete(f"{BASE}/api/voicemails/{row['id']}", headers=admin_headers, timeout=30)
    assert r.status_code == 404


def test_rep_sees_only_their_own_line(rep_headers):
    data = _inbox(rep_headers)
    assert all(i["line_is_mine"] for i in data["items"])
    assert not any(i["to_phone"] == FOREST_LINE for i in data["items"])


def test_requires_auth():
    assert requests.get(f"{BASE}/api/voicemails", timeout=30).status_code in (401, 403)


def _make_m4a(path):
    import subprocess
    from imageio_ffmpeg import get_ffmpeg_exe
    subprocess.run([get_ffmpeg_exe(), "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=4", "-c:a", "aac", path], check=True, capture_output=True)


def test_greeting_record_play_remove(admin_headers, tmp_path):
    """Rep records a greeting in the app -> stored as mp3 -> Twilio <Play>s it -> remove -> default <Say>."""
    m4a = tmp_path / "greet.m4a"
    _make_m4a(str(m4a))
    with open(m4a, "rb") as f:
        r = requests.post(f"{BASE}/api/voicemails/greeting", headers=admin_headers, files={"file": ("greet.m4a", f, "audio/m4a")}, timeout=120)
    assert r.status_code == 200, r.text
    g = r.json()
    assert g["has_greeting"] and 3 <= g["duration"] <= 5 and ".mp3" in g["url"]
    assert requests.get(f"{BASE}/api/voicemails/greeting", headers=admin_headers, timeout=30).json()["has_greeting"] is True

    sid = f"CAvm_{RUN}_g"
    twiml = _fallback(sid, "+15005550104")
    assert "<Play>" in twiml and "/api/webhooks/twilio/greeting/" in twiml and "Sorry, Forest is unavailable" not in twiml

    # the URL carries the production host (PUBLIC_FACING_URL); fetch the same path from the API under test
    from urllib.parse import urlparse
    mp3 = requests.get(f"{BASE}{urlparse(g['url']).path}", timeout=30)
    assert mp3.status_code == 200 and mp3.headers["content-type"].startswith("audio/mpeg") and len(mp3.content) > 5000

    r = requests.delete(f"{BASE}/api/voicemails/greeting", headers=admin_headers, timeout=30)
    assert r.status_code == 200 and r.json()["has_greeting"] is False
    twiml = _fallback(f"CAvm_{RUN}_g2", "+15005550104")
    assert "<Play>" not in twiml and "Sorry, Forest is unavailable right now" in twiml
    for marker in ("0104",):
        rr = _row(admin_headers, marker)
        while rr:
            requests.delete(f"{BASE}/api/voicemails/{rr['id']}", headers=admin_headers, timeout=30)
            rr = _row(admin_headers, marker)


def test_greeting_rejects_empty_upload(admin_headers):
    r = requests.post(f"{BASE}/api/voicemails/greeting", headers=admin_headers, files={"file": ("x.m4a", b"abc", "audio/m4a")}, timeout=30)
    assert r.status_code == 400
