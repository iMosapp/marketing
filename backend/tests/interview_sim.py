"""Simulates Twilio ConversationRelay against an onboarding interview: TwiML fetch -> websocket setup/prompt turns with realistic
rep answers -> status completed -> persona built and applied to the user. No real call (session doc seeded directly).
Run: cd /app/backend && python tests/interview_sim.py"""
import asyncio
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone

import requests
import websockets
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv("/app/backend/.env")
API = [l.split("=", 1)[1].strip() for l in open("/app/frontend/.env") if l.startswith("REACT_APP_BACKEND_URL=")][0].rstrip("/")
WS = API.replace("https://", "wss://")

ANSWERS = [
    "Everybody just calls me Alex. I'm a sales consultant here at QA Motors, mostly trucks and SUVs.",
    "Been doing this about twelve years now. Started washing cars on the lot in college and never left, honestly.",
    "I grew up in Ogden, still live about ten minutes from where I was raised. My wife Jen and I have two boys, eight and eleven, and a very loud husky named Blue.",
    "Weekends we're usually camping up in the Uintas or at a little league game. I fly fish when I can sneak away.",
    "I drive a 2023 F-150 Tremor. Dream truck would be a Raptor R, but don't tell Jen.",
    "Trucks for sure, and first time buyers. I like walking somebody through their first deal so they don't get taken advantage of.",
    "There was a single mom, Maria, who came in scared to death of getting ripped off. We found her a Highlander she could actually afford and she still sends me a Christmas card every year.",
    "My motto is pretty simple. Do what you said you'd do, when you said you'd do it.",
    "I text pretty casual, like I talk. Short, no big paragraphs. Maybe a thumbs up emoji now and then but that's about it.",
    "I joke around a fair amount. Not corny, just keep it light. People are stressed enough buying a car.",
    "I say 'no worries' a lot, and 'let's make it easy'. Probably too much.",
    "I never say 'what's it gonna take to get you in a car today'. Hate that. And I never bad mouth another store.",
    "Fun fact, I was a college wrestler and I still coach the middle school team on Tuesdays.",
    "Pick me because I'll still answer your text two years after you buy. Most guys disappear after the sale.",
    "I usually open with 'Hey, it's Alex at QA Motors' and I sign off with just 'Alex' or 'talk soon'.",
    "Nope, I think that covers it. Thanks Jessi.",
]


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    rep = await db.users.find_one({"email": "activation-tester@invalid.imonsocial.test"})
    assert rep, "seed the activation tester first"
    before = {"persona": rep.get("persona"), "title": rep.get("title"), "onboarding_complete": rep.get("onboarding_complete"), "persona_interviewed_at": rep.get("persona_interviewed_at")}
    token = uuid.uuid4().hex
    now = datetime.now(timezone.utc)
    res = await db.interview_sessions.insert_one({
        "user_id": str(rep["_id"]), "rep_name": "Alex Tester", "rep_phone": "+15005550006", "from_number": "+15005550100", "store_id": str(rep.get("store_id")), "store_name": "QA Motors",
        "role_title": "", "locale": "en-US", "status": "dialing", "token": token, "turns": [], "covered": [], "created_at": now, "updated_at": now, "qa_sim": True})
    sid = str(res.inserted_id)
    print("session", sid)
    try:
        r = requests.post(f"{API}/api/interview/call/twiml/{sid}?t={token}", timeout=30)
        assert r.status_code == 200 and "<ConversationRelay" in r.text and f"/api/interview/relay/{sid}/{token}" in r.text and 'welcomeGreeting="Hey Alex' in r.text, (r.status_code, r.text[:300])
        assert 'voice="en-US-Journey-F"' in r.text and "/api/interview/call/after/" in r.text
        print("twiml ok:", r.text[:140], "...")
        assert requests.post(f"{API}/api/interview/call/twiml/{sid}?t=bad", timeout=30).status_code == 404
        assert requests.post(f"{API}/api/interview/call/status/{sid}?t={token}", data={"CallStatus": "ringing", "CallSid": "CA_sim"}, timeout=30).status_code == 204
        s = await db.interview_sessions.find_one({"_id": res.inserted_id})
        assert s["status"] == "dialing" and s["call_status"] == "ringing"

        covered_total = 0
        async with websockets.connect(f"{WS}/api/interview/relay/{sid}/{token}", open_timeout=30) as ws:
            await ws.send(json.dumps({"type": "setup", "sessionId": "VX_sim", "callSid": "CA_sim", "from": "+15005550100", "to": "+15005550006"}))
            await asyncio.sleep(0.6)
            s = await db.interview_sessions.find_one({"_id": res.inserted_id})
            assert s["status"] == "live" and s["turns"] and s["turns"][0]["role"] == "jessi", (s["status"], s.get("turns"))
            print("setup ok: live, greeting logged as Jessi's first turn")
            # partial prompts are ignored
            await ws.send(json.dumps({"type": "prompt", "voicePrompt": "Everybody just", "last": False}))
            ended = False
            for i, ans in enumerate(ANSWERS):
                t0 = time.time()
                await ws.send(json.dumps({"type": "prompt", "voicePrompt": ans, "lang": "en-US", "last": True}))
                reply = json.loads(await asyncio.wait_for(ws.recv(), timeout=90))
                assert reply["type"] == "text" and reply["last"] is True and reply["token"], reply
                assert "\u2014" not in reply["token"] and len(reply["token"].split()) <= 70, reply["token"]
                s = await db.interview_sessions.find_one({"_id": res.inserted_id})
                covered_total = len(s.get("covered") or [])
                print(f"turn {i+1} {time.time()-t0:.1f}s covered={covered_total} -> {reply['token'][:120]}")
                if i == 2:
                    await ws.send(json.dumps({"type": "interrupt", "utteranceUntilInterrupt": reply["token"][:15], "durationUntilInterruptMs": 800}))
                    await asyncio.sleep(0.3)
                    s = await db.interview_sessions.find_one({"_id": res.inserted_id})
                    assert s["turns"][-1].get("interrupted") is True and s["turns"][-1]["text"] == reply["token"][:15], s["turns"][-1]
                    print("interrupt ok: Jessi's last line trimmed to what was heard")
                if s["status"] == "ending":
                    end = json.loads(await asyncio.wait_for(ws.recv(), timeout=30))
                    assert end["type"] == "end", end
                    ended = True
                    print(f"Jessi wrapped up after {i+1} answers (end message received)")
                    break
            assert covered_total >= 8, f"only {covered_total} topics marked covered"
            if not ended:
                print("NOTE: Jessi did not end on her own within the scripted answers; hanging up from Twilio's side")
        # Twilio reports the call finished
        assert requests.post(f"{API}/api/interview/call/status/{sid}?t={token}", data={"CallStatus": "completed", "CallSid": "CA_sim"}, timeout=30).status_code == 204
        for _ in range(60):
            await asyncio.sleep(2)
            s = await db.interview_sessions.find_one({"_id": res.inserted_id})
            if s["status"] in ("completed", "failed", "abandoned"):
                break
        assert s["status"] == "completed", (s["status"], s.get("fail_reason"))
        ex = s["extracted"]
        print("built in", (s["built_at"] - s["ended_at"]).total_seconds(), "s; applied:", s["applied_fields"])
        print("bio:", ex["bio"])
        print("highlights:", s["highlights"])
        assert len(ex["bio"]) >= 40 and "\u2014" not in ex["bio"]
        assert "ogden" in (ex["hometown"] or "").lower(), ex["hometown"]
        assert any("f-150" in h.lower() or "f150" in h.lower() or "tremor" in h.lower() for h in [ex["vehicles"]]), ex["vehicles"]
        assert ex["tone"] in ("casual", "friendly") and ex["humor_level"] in ("some", "light", "lots"), (ex["tone"], ex["humor_level"])
        assert ex["hobbies"] and ex["specialties"] and ex["never_say"], (ex["hobbies"], ex["specialties"], ex["never_say"])
        assert ex["professional_identity"], ex
        u = await db.users.find_one({"_id": rep["_id"]})
        assert u["persona"]["bio"] == ex["bio"] and u["persona"]["hometown"] == ex["hometown"] and u.get("persona_interviewed_at"), "persona not applied"
        if not before["title"]:
            assert u.get("title") == ex["professional_identity"], u.get("title")
        # the auth'd status endpoint shows it
        login = requests.post(f"{API}/api/auth/login", json={"email": "activation-tester@invalid.imonsocial.test", "password": "NewPass123!"}, timeout=30).json()
        h = {"Authorization": f"Bearer {login['token']}"}
        st = requests.get(f"{API}/api/interview/status", headers=h, timeout=30).json()
        assert st["session"]["id"] == sid and st["session"]["status"] == "completed" and st["persona_filled"] >= 8 and st["voice"]["status"] in ("none", "not_configured"), st
        assert st["session"]["labels"]["bio"] == "Your story" and len(st["session"]["turns"]) == len(s["turns"])
        one = requests.get(f"{API}/api/interview/sessions/{sid}", headers=h, timeout=30).json()
        assert one["id"] == sid and one["extracted"]["bio"] == ex["bio"]
        assert requests.get(f"{API}/api/interview/sessions/{sid}", timeout=30).status_code == 401
        # rebuild path works too
        rb = requests.post(f"{API}/api/interview/sessions/{sid}/rebuild", headers=h, timeout=180)
        assert rb.status_code == 200 and rb.json()["status"] == "completed" and rb.json()["extracted"]["bio"], rb.text[:200]
        print("status/session/rebuild endpoints ok; persona_filled =", st["persona_filled"])
        # --- Test Lab dry run: same transcript, nothing applied until /apply
        marker = f"marker-{uuid.uuid4().hex[:6]}"
        await db.users.update_one({"_id": rep["_id"]}, {"$set": {"persona.hometown": marker}})
        dry_tok = uuid.uuid4().hex
        dry = await db.interview_sessions.insert_one({**{k: v for k, v in s.items() if k not in ("_id", "extracted", "highlights", "applied_fields", "applied", "built_at", "status", "token", "ended_at", "end_reason")},
                                                      "status": "live", "token": dry_tok, "dry_run": True, "qa_sim": True, "created_at": datetime.now(timezone.utc)})
        assert requests.post(f"{API}/api/interview/call/status/{dry.inserted_id}?t={dry_tok}", data={"CallStatus": "completed", "CallSid": "CA_sim2"}, timeout=30).status_code == 204
        for _ in range(60):
            await asyncio.sleep(2)
            d = await db.interview_sessions.find_one({"_id": dry.inserted_id})
            if d["status"] in ("completed", "failed", "abandoned"):
                break
        assert d["status"] == "completed" and d["applied_fields"] == [] and d.get("applied") is False and d["extracted"]["bio"], (d["status"], d.get("applied_fields"))
        u = await db.users.find_one({"_id": rep["_id"]}, {"persona.hometown": 1})
        assert u["persona"]["hometown"] == marker, "dry run must not touch the profile"
        ser = requests.get(f"{API}/api/interview/sessions/{dry.inserted_id}", headers=h, timeout=30).json()
        assert ser["dry_run"] is True and ser["applied"] is False
        ap = requests.post(f"{API}/api/interview/sessions/{dry.inserted_id}/apply", headers=h, timeout=60)
        assert ap.status_code == 200 and ap.json()["applied"] is True and "hometown" in ap.json()["applied_fields"], ap.text[:200]
        u = await db.users.find_one({"_id": rep["_id"]}, {"persona.hometown": 1})
        assert u["persona"]["hometown"] == d["extracted"]["hometown"] != marker
        print("dry run ok: nothing applied until /apply, then persona updated")
        # --- Test Lab flags
        adm = requests.post(f"{API}/api/auth/login", json={"email": "forest@imosapp.com", "password": "Admin123!"}, timeout=30).json()
        ah = {"Authorization": f"Bearer {adm['token']}"}
        feats = requests.get(f"{API}/api/lab/features", headers=ah, timeout=30).json()["features"]
        vi = next(f for f in feats if f["key"] == "voice_interview")
        was = vi["status"]
        assert requests.get(f"{API}/api/lab/features", headers=h, timeout=30).status_code == 403
        assert requests.put(f"{API}/api/lab/features/voice_interview", json={"status": "bogus"}, headers=ah, timeout=30).status_code == 400
        assert requests.put(f"{API}/api/lab/features/nope", json={"status": "live"}, headers=ah, timeout=30).status_code == 404
        r = requests.put(f"{API}/api/lab/features/voice_interview", json={"status": "live"}, headers=ah, timeout=30)
        assert r.status_code == 200 and r.json()["status"] == "live" and r.json()["changed_by"]
        assert requests.get(f"{API}/api/interview/status", headers=h, timeout=30).json()["available"] is True
        requests.put(f"{API}/api/lab/features/voice_interview", json={"status": "lab"}, headers=ah, timeout=30)
        assert requests.get(f"{API}/api/interview/status", headers=h, timeout=30).json()["available"] is False
        assert requests.post(f"{API}/api/interview/start", json={"dry_run": True}, headers=h, timeout=30).status_code == 403, "dry runs are super-admin only"
        assert requests.post(f"{API}/api/interview/start", json={}, headers=h, timeout=30).status_code == 403, "not released -> reps cannot start"
        requests.put(f"{API}/api/lab/features/voice_interview", json={"status": was}, headers=ah, timeout=30)
        print("lab flags ok (restored to", was + ")")
        print("ALL OK")
    finally:
        if "--keep" in sys.argv:
            print("--keep: leaving the completed session + persona in place for UI checks")
            return
        await db.users.update_one({"_id": rep["_id"]}, {"$set": {k: v for k, v in before.items() if v is not None}, "$unset": {k: "" for k, v in before.items() if v is None}})
        await db.interview_sessions.delete_many({"user_id": str(rep["_id"]), "qa_sim": True})
        print("restored tester persona, removed sim session")


asyncio.run(main())
