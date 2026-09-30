"""Voice Preview: a pinned GPT-Live voice per challenge + the five-second sample endpoint (fake GPT-Live, no network)."""
import asyncio
import audioop
import base64
import io
import os
import sys
import wave

import pytest
from bson import ObjectId

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services import kubota_pack as kp  # noqa: E402
from services import live_shops as ls  # noqa: E402
from services import live_voice as lv  # noqa: E402
from services import voice_samples as vs  # noqa: E402
from tests._http import auth, call, login  # noqa: E402
from tests.test_live_shops import FakeUpstream, _session  # noqa: E402


def test_ulaw_decode_matches_audioop_and_wav_is_valid():
    raw = bytes(range(256)) * 20
    assert vs.ulaw_to_pcm16(raw) == audioop.ulaw2lin(raw, 2)
    with wave.open(io.BytesIO(vs.wav_bytes(vs.ulaw_to_pcm16(raw))), "rb") as w:
        assert (w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()) == (1, 2, 8000, len(raw))


def test_sample_line_fills_placeholders_and_trims():
    line = vs.sample_line({"opening_line": "Hi, I'm calling about {offering} I saw on {store}'s site."}, "equipment", "eq_sales")
    assert "{" not in line and "tractor" in line and "dealership" in line
    long = vs.sample_line({"opening_line": "Hey there, this is Bill calling from across town. " + "word " * 40}, "automotive", "sales")
    assert long == "Hey there, this is Bill calling from across town."  # cut at the sentence end that fits, when that sentence is worth saying
    short = vs.sample_line({"opening_line": "So " + "word " * 40}, "automotive", "sales")
    assert len(short.split()) == vs.MAX_WORDS and short.endswith(".")
    assert vs.sample_line({}, "automotive", "sales") == vs.FALLBACK_LINE
    assert vs.sample_line({"opening_lines": ["First option here", "Second"]}, "equipment", "eq_parts") == "First option here"


def test_voice_for_honours_a_pinned_voice_that_fits_the_locale():
    s = _session(persona={"name": "Bill Harmon", "gender": "male", "live_voice": "cinder", "opening_line": "Hi"})
    assert ls.voice_for(s) == "cinder"
    s["persona"]["live_voice"] = "nope"
    assert ls.voice_for(s) in ls.MASCULINE
    uk = _session(locale="en-GB", persona={"name": "Bill Harmon", "gender": "male", "live_voice": "cinder", "opening_line": "Hi"})
    assert ls.voice_for(uk) in ls.UK_VOICES["male"]  # a US pin does not follow a UK client
    uk["persona"]["live_voice"] = "stone"
    assert ls.voice_for(uk) == "stone"


def test_roll_persona_drops_a_pin_that_no_longer_fits_the_rolled_name():
    p = kp.roll_persona({"names": ["Denise Carter"], "voices": ["female"], "live_voice": "cinder", "opening_line": "Hi"})
    assert p["gender"] == "female" and "live_voice" not in p
    p = kp.roll_persona({"name": "Bill Harmon", "live_voice": "cinder", "opening_line": "Hi"})
    assert p["live_voice"] == "cinder"
    assert lv.voice_gender("gleam") == "female" and lv.voice_gender("meridian") == "male" and lv.voice_gender("x") is None


class _DB:
    """Just enough of motor for get_or_make: one collection with find_one / insert_one."""

    def __init__(self):
        self.rows = []

    def __getitem__(self, name):
        return self

    async def find_one(self, q, proj=None):
        return next((r for r in self.rows if r["key"] == q["key"]), None)

    async def insert_one(self, doc):
        self.rows.append(doc)


def test_get_or_make_records_five_seconds_then_serves_from_cache():
    db = _DB()
    ups = []

    async def connect():
        up = FakeUpstream()
        ups.append(up)

        async def feed():
            await asyncio.sleep(0.05)
            await up.q.put({"type": "session.started", "session": {"id": "live_fake_vs"}})
            await asyncio.sleep(0.05)
            await up.q.put({"type": "session.output_transcript.delta", "delta": "Hi, I'm calling about the Wrangler."})
            for _ in range(12):  # 12 x 8000 bytes = 12 s of pcmu, the sample keeps the first 5.5 s
                await up.q.put({"type": "session.output_audio.delta", "delta": base64.b64encode(bytes([0xFF, 0x7F] * 4000)).decode()})
        asyncio.get_event_loop().create_task(feed())
        return up

    persona = {"name": "Casey Morgan", "gender": "female", "opening_line": "Hi, I'm calling about the Wrangler.", "summary": "Busy nurse"}
    out = asyncio.get_event_loop().run_until_complete(vs.get_or_make(db, "gleam", persona, "automotive", "sales", connect=connect))
    assert out["voice"] == "gleam" and out["cached"] is False and out["seconds"] == 5.5 and out["url"].endswith(f"/api/public/voice-sample/{out['id']}.wav")
    assert out["transcript"].startswith("Hi, I'm calling")
    up = ups[0]
    start = next(e for e in up.sent if e["type"] == "session.start")
    assert start["session"]["audio"] == {"format": {"type": "audio/pcmu", "rate": 8000}, "output": {"voice": "gleam"}}
    assert "Casey Morgan, a woman" in start["session"]["instructions"] and '"Hi, I\'m calling about the Wrangler."' in start["session"]["instructions"]
    assert [e["type"] for e in up.sent][1:] == ["session.instructions.append", "session.commentary.append", "session.close"] and up.closed
    with wave.open(io.BytesIO(bytes(db.rows[0]["wav"])), "rb") as w:
        assert w.getframerate() == 8000 and round(w.getnframes() / 8000, 1) == 5.5
    again = asyncio.get_event_loop().run_until_complete(vs.get_or_make(db, "gleam", persona, "automotive", "sales", connect=connect))
    assert again["cached"] is True and again["id"] == out["id"] and len(ups) == 1

    async def broken():
        up = FakeUpstream()
        await up.q.put({"type": "error", "error": {"message": "voice unavailable"}})
        return up
    with pytest.raises(vs.VoiceSampleError, match="voice unavailable"):
        asyncio.get_event_loop().run_until_complete(vs.get_or_make(db, "cinder", persona, "automotive", "sales", connect=broken))


def test_api_voices_and_sample_guard():
    tok, uid = login("forest@imosapp.com", "Admin123!")
    st, b = call("GET", "/api/shop-clients/voices", headers=auth(tok, uid))
    assert st == 200 and [v["id"] for v in b["female"]] == list(ls.FEMININE) and [v["id"] for v in b["male"]] == list(ls.MASCULINE)
    assert all(v["tone"] == "masculine" for v in b["male"]) and "configured" in b
    st, b = call("POST", "/api/shop-clients/voices/sample", {"voice": "nope", "persona": {}}, headers=auth(tok, uid))
    assert st == 400
    if not (os.environ.get("OPENAI_API_KEY") or "").strip():
        st, b = call("POST", "/api/shop-clients/voices/sample", {"voice": "cinder", "persona": {"name": "Bill", "opening_line": "Hi"}}, headers=auth(tok, uid))
        assert st == 503 and "OPENAI_API_KEY" in b
    st, _ = call("GET", f"/api/public/voice-sample/{ObjectId()}.wav")
    assert st == 404


def test_script_voice_resolves_pin_or_pool_and_a_concrete_master_persona():
    sid = ObjectId("000000000000000000000010")  # last two hex digits 10 -> 16 % pool size
    voice, p, pinned = vs.script_voice({"_id": sid, "persona": {"name": "Bill Harmon", "live_voice": "cinder", "opening_line": "Hi"}})
    assert (voice, pinned, p["gender"]) == ("cinder", True, "male")
    voice, p, pinned = vs.script_voice({"_id": sid, "persona": {"name": "Bill Harmon", "live_voice": "gleam", "opening_line": "Hi"}})
    assert voice in ls.MASCULINE and pinned is False and p["live_voice"] is None  # a woman's voice pinned on Bill is ignored
    master = {"_id": sid, "persona": {"names": ["Denise Holloway", "Randy Coker"], "voices": ["male", "female"], "opening_lines": ["First line here", "Second"], "summary": "x"}}
    voice, p, pinned = vs.script_voice(master)
    assert p["name"] == "Denise Holloway" and p["opening_line"] == "First line here" and p["gender"] == "female" and "names" not in p and "voices" not in p
    assert voice in ls.FEMININE and pinned is False
    assert vs.script_voice(master) == vs.script_voice(master)  # the card always sounds the same
    voice, _, _ = vs.script_voice({"_id": sid, "persona": {"name": "Bill Harmon", "opening_line": "Hi"}}, "en-GB")
    assert voice in ls.UK_VOICES["male"]


def test_api_challenge_voice_sample_guards():
    tok, uid = login("forest@imosapp.com", "Admin123!")
    st, b = call("POST", f"/api/shop-clients/challenges/{ObjectId()}/voice-sample", {}, headers=auth(tok, uid))
    assert st == 404
    st, lib = call("GET", "/api/shop-clients/challenges?industry=equipment", headers=auth(tok, uid))
    rows = (lib or {}).get("challenges") if st == 200 else None
    assert st == 200 and rows, lib
    if not (os.environ.get("OPENAI_API_KEY") or "").strip():
        st, b = call("POST", f"/api/shop-clients/challenges/{rows[0]['id']}/voice-sample", {}, headers=auth(tok, uid))
        assert st == 503 and "OPENAI_API_KEY" in b
    st, b = call("POST", f"/api/shop-clients/challenges/{rows[0]['id']}/voice-sample", {})
    assert st == 401


def test_api_challenge_keeps_a_matching_pin_and_drops_a_mismatch():
    tok, uid = login("forest@imosapp.com", "Admin123!")
    body = {"title": "QA voice pin", "department": "sales", "body": "Answer and book.", "persona": {"name": "Bill Harmon", "gender": "male", "voice": "older", "live_voice": "cinder", "opening_line": "Hi, is the Wrangler still there?"}}
    st, c = call("POST", "/api/shop-clients/challenges", body, headers=auth(tok, uid))
    assert st == 200, c
    try:
        assert c["persona"]["live_voice"] == "cinder" and c["persona"]["live_voice_label"] == "Cinder"
        body["persona"]["live_voice"] = "gleam"  # a woman's voice on Bill: dropped, the pool decides
        st, c2 = call("PUT", f"/api/shop-clients/challenges/{c['id']}", body, headers=auth(tok, uid))
        assert st == 200 and c2["persona"]["live_voice"] is None and c2["persona"]["live_voice_label"] is None
    finally:
        call("DELETE", f"/api/shop-clients/challenges/{c['id']}", headers=auth(tok, uid))
