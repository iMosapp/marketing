"""Voice notes on an appraisal: rep clip (chunked) and customer clip (trade link page) are typed by Whisper and appended to the notes; removal takes
the words back out. Speech comes from OpenAI TTS so the transcript is real. Runs against the preview backend with the shared QA accounts."""
import asyncio
import base64
import os
import sys

import pytest
import requests
from dotenv import load_dotenv

sys.path.insert(0, "/app/backend")
sys.path.insert(0, "/app/backend/tests")
load_dotenv("/app/backend/.env")
from _http import API, call, login, auth  # noqa: E402

REP = ("activation-tester@invalid.imonsocial.test", "NewPass123!")
MANAGER = ("qa-manager@invalid.imonsocial.test", "Manager123!")
SARAH = "6aa413008f0d53e3f2261853"
REP_LINE = "The rear bumper has a dent and the front tires are worn. New brakes last month."
CUSTOMER_LINE = "The check engine light has been on for two weeks and the sunroof leaks when it rains."


def _speech(text: str) -> bytes:
    from emergentintegrations.llm.openai import OpenAITextToSpeech

    async def go():
        return await OpenAITextToSpeech(api_key=os.environ["EMERGENT_LLM_KEY"]).generate_speech(text=text, model="tts-1", voice="alloy", speed=1.0, response_format="mp3")
    return asyncio.run(go())


@pytest.fixture(scope="module")
def rep():
    return auth(*login(*REP))


@pytest.fixture(scope="module")
def manager():
    return auth(*login(*MANAGER))


@pytest.fixture(scope="module")
def appraisal(rep):
    st, b = call("POST", "/api/appraisals", {"contact_id": SARAH, "mode": "vehicle_here"}, rep)
    assert st == 200, b
    yield b["appraisal"]
    call("DELETE", f"/api/appraisals/{b['appraisal']['id']}", None, rep)


def _chunks(aid: str, audio: bytes, headers: dict, piece: int = 60_000, duration: float = 6.0):
    import uuid
    b64 = base64.b64encode(audio).decode()
    total = max(1, (len(b64) + piece - 1) // piece)
    uid = f"qa{uuid.uuid4().hex[:8]}"
    last = None
    for i in range(total):
        st, last = call("POST", f"/api/appraisals/{aid}/voice-note/chunk", {"upload_id": uid, "index": i, "total": total, "data": b64[i * piece:(i + 1) * piece], "content_type": "audio/mpeg", "duration": duration}, headers)
        assert st == 200, (st, last)
        if i < total - 1:
            assert last["received"] == i + 1 and "voice_note" not in last
    return last


def test_rep_voice_note_is_typed_into_the_notes(rep, appraisal):
    aid = appraisal["id"]
    assert appraisal["voice_notes"] == [] and not appraisal.get("notes")
    out = _chunks(aid, _speech(REP_LINE), rep)
    vn = out["voice_note"]
    assert vn["by"] == "rep" and vn["by_label"] == "Rep voice note" and vn["duration"] == 6.0 and vn["audio_url"].startswith("/api/images/appraisals/")
    assert vn["transcribed"] and "bumper" in vn["transcript"].lower() and "tires" in vn["transcript"].lower(), vn
    a = out["appraisal"]
    assert len(a["voice_notes"]) == 1 and a["voice_notes"][0]["id"] == vn["id"]
    assert a["notes"].startswith("[Rep voice note · ") and vn["transcript"] in a["notes"]
    # the clip plays back from storage
    r = requests.get(f"{API}{vn['audio_url']}", headers={"User-Agent": "Mozilla/5.0"})
    assert r.status_code == 200 and len(r.content) > 1000
    # second note appends under the first
    out2 = _chunks(aid, _speech("Two keys, no smoke smell."), rep, duration=3.0)
    assert len(out2["appraisal"]["voice_notes"]) == 2
    assert out2["appraisal"]["notes"].count("[Rep voice note") == 2 and out2["appraisal"]["notes"].index(vn["transcript"]) < out2["appraisal"]["notes"].index(out2["voice_note"]["transcript"])
    # audit trail has it
    st, full = call("GET", f"/api/appraisals/{aid}", None, rep)
    assert st == 200 and len(full["voice_notes"]) == 2 and full["notes"] == out2["appraisal"]["notes"]


def test_customer_voice_note_from_the_trade_link(rep, appraisal):
    aid = appraisal["id"]
    st, b = call("POST", f"/api/appraisals/{aid}/intake-link", {"channel": "copy"}, rep)
    assert st == 200, b
    token = b["intake"]["url"].rsplit("/", 1)[1]
    page = requests.get(f"{API}/api/public/trade/{token}", headers={"User-Agent": "Mozilla/5.0"})
    assert page.status_code == 200 and 'id="rec"' in page.text and "/voice" in page.text or "API+\"/voice\"" in page.text
    ctx = requests.get(f"{API}/api/public/trade/{token}/context", headers={"User-Agent": "Mozilla/5.0"}).json()
    assert ctx["voice_notes"] == [] and ctx["max_voice_notes"] == 5
    r = requests.post(f"{API}/api/public/trade/{token}/voice", data={"duration": "7"}, files={"file": ("note.mp3", _speech(CUSTOMER_LINE), "audio/mpeg")}, headers={"User-Agent": "Mozilla/5.0"})
    assert r.status_code == 200, r.text
    j = r.json()
    assert set(j) == {"id", "transcript", "duration", "transcribed"} and "engine" in j["transcript"].lower() and j["duration"] == 7.0
    ctx = requests.get(f"{API}/api/public/trade/{token}/context", headers={"User-Agent": "Mozilla/5.0"}).json()
    assert [v["id"] for v in ctx["voice_notes"]] == [j["id"]]
    assert not any(k in ctx for k in ("suggested_acv", "approved_value", "user_id", "contact_id", "audio_url")), "public side carries no values, ids or storage paths"
    st, a = call("GET", f"/api/appraisals/{aid}", None, rep)
    assert st == 200
    mine = [v for v in a["voice_notes"] if v["by"] == "customer"]
    assert len(mine) == 1 and mine[0]["by_name"].startswith("Sarah") and mine[0]["by_label"] == "Customer voice note"
    assert "[Customer voice note · " in a["notes"] and j["transcript"] in a["notes"]
    # empty upload is refused, revoked link is closed
    r = requests.post(f"{API}/api/public/trade/{token}/voice", data={"duration": "1"}, files={"file": ("note.webm", b"", "audio/webm")}, headers={"User-Agent": "Mozilla/5.0"})
    assert r.status_code == 400
    assert call("DELETE", f"/api/appraisals/{aid}/intake-link", None, rep)[0] == 200
    r = requests.post(f"{API}/api/public/trade/{token}/voice", data={"duration": "3"}, files={"file": ("note.mp3", b"abc" * 100, "audio/mpeg")}, headers={"User-Agent": "Mozilla/5.0"})
    assert r.status_code == 400 and "no longer active" in r.text


def test_desk_sees_clips_and_delete_takes_the_words_back(rep, manager, appraisal):
    aid = appraisal["id"]
    st, a = call("GET", f"/api/appraisals/{aid}", None, rep)
    assert st == 200 and len(a["voice_notes"]) == 3
    victim = a["voice_notes"][1]
    st, d = call("DELETE", f"/api/appraisals/{aid}/voice-note/{victim['id']}", None, rep)
    assert st == 200, d
    after = d["appraisal"]
    assert [v["id"] for v in after["voice_notes"]] == [a["voice_notes"][0]["id"], a["voice_notes"][2]["id"]]
    assert victim["transcript"] not in after["notes"] and a["voice_notes"][0]["transcript"] in after["notes"] and a["voice_notes"][2]["transcript"] in after["notes"]
    assert "\n\n\n" not in after["notes"]
    assert call("DELETE", f"/api/appraisals/{aid}/voice-note/{victim['id']}", None, rep)[0] == 404
    # a manager who can see the store reads the same clips on the desk payload (desk detail needs a submitted appraisal, so check the shared serializer)
    st, m = call("GET", f"/api/appraisals/{aid}", None, manager)
    assert st == 200 and len(m["voice_notes"]) == 2 and m["voice_notes"][0]["audio_url"]


def test_bad_chunks_and_bad_notes_are_refused(rep, appraisal):
    aid = appraisal["id"]
    st, b = call("POST", f"/api/appraisals/{aid}/voice-note/chunk", {"upload_id": "x", "index": 3, "total": 2, "data": "AAAA", "content_type": "audio/mp4", "duration": 2}, rep)
    assert st == 400
    st, b = call("POST", f"/api/appraisals/{aid}/voice-note/chunk", {"upload_id": "toolong", "index": 0, "total": 1, "data": "AAAA", "content_type": "audio/mp4", "duration": 999}, rep)
    assert st == 400 and "5 minutes" in str(b)
    st, b = call("POST", f"/api/appraisals/{aid}/voice-note/chunk", {"upload_id": "nothing", "index": 0, "total": 1, "data": "", "content_type": "audio/mp4", "duration": 4}, rep)
    assert st == 400 and "Empty" in str(b)
    st, b = call("GET", f"/api/appraisals/{aid}", None, rep)
    assert st == 200 and len(b["voice_notes"]) == 2
