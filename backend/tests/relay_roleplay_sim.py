"""Simulates Twilio ConversationRelay against a phone practice session: TwiML fetch -> websocket setup/prompt/interrupt -> status completed -> graded.
No real call is placed (the session doc is seeded directly)."""
import asyncio
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone

import requests
import websockets
from bson import ObjectId
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv("/app/backend/.env")
API = [l.split("=", 1)[1].strip() for l in open("/app/frontend/.env") if l.startswith("REACT_APP_BACKEND_URL=")][0].rstrip("/")
WS = API.replace("https://", "wss://")


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    rep = await db.users.find_one({"email": "activation-tester@invalid.imonsocial.test"})
    script = await db.scripts.find_one({"slug": "inbound_sales_call", "store_id": None})
    token = uuid.uuid4().hex
    now = datetime.now(timezone.utc)
    res = await db.roleplay_sessions.insert_one({
        "user_id": str(rep["_id"]), "rep_name": rep.get("name") or "Activation Tester", "rep_phone": "+15005550006", "store_id": str(rep.get("store_id")), "store_name": "QA Motors",
        "script_id": str(script["_id"]), "script_title": script["title"], "script_slug": script["slug"], "persona": script["persona"], "curveballs": ["She already has a quote from the store across town"],
        "assignment_id": None, "mode": "phone", "status": "dialing", "token": token, "turns": [], "started_at": now, "updated_at": now, "qa_relay_sim": True, "direction": "inbound"})
    sid = str(res.inserted_id)
    print("session", sid)

    r = requests.post(f"{API}/api/scripts/roleplay/twiml/{sid}?t={token}", timeout=30)
    assert r.status_code == 200 and "<ConversationRelay" in r.text and f"/relay/{sid}/{token}" in r.text and "welcomeGreeting" not in r.text, (r.status_code, r.text[:300])
    print("twiml ok (inbound = no welcomeGreeting, customer waits for the rep):", r.text[:120], "...")
    # outbound scripts still greet the rep the moment they pick up
    out_tpl = await db.scripts.find_one({"slug": "appointment_confirmation", "store_id": None})
    out_tok = uuid.uuid4().hex
    out_res = await db.roleplay_sessions.insert_one({"user_id": str(rep["_id"]), "rep_name": "Activation Tester", "rep_phone": "+15005550006", "store_name": "QA Motors", "script_id": str(out_tpl["_id"]),
                                                     "script_title": out_tpl["title"], "script_slug": out_tpl["slug"], "persona": out_tpl["persona"], "curveballs": [], "mode": "phone", "status": "dialing",
                                                     "token": out_tok, "turns": [], "started_at": now, "updated_at": now, "qa_relay_sim": True, "direction": "outbound"})
    r = requests.post(f"{API}/api/scripts/roleplay/twiml/{out_res.inserted_id}?t={out_tok}", timeout=30)
    assert r.status_code == 200 and 'welcomeGreeting="' in r.text, r.text[:300]
    await db.roleplay_sessions.delete_one({"_id": out_res.inserted_id})
    print("twiml ok (outbound keeps welcomeGreeting)")
    assert requests.post(f"{API}/api/scripts/roleplay/twiml/{sid}?t=bad", timeout=30).status_code == 404

    r = requests.post(f"{API}/api/scripts/roleplay/status/{sid}?t={token}", data={"CallStatus": "in-progress", "CallSid": "CA_sim"}, timeout=30)
    assert r.status_code == 204, r.status_code

    async with websockets.connect(f"{WS}/api/scripts/roleplay/relay/{sid}/{token}", open_timeout=30) as ws:
        await ws.send(json.dumps({"type": "setup", "sessionId": "VX_sim", "callSid": "CA_sim", "from": "+15005550100", "to": "+15005550006"}))
        await asyncio.sleep(0.5)
        s = await db.roleplay_sessions.find_one({"_id": res.inserted_id})
        assert s["status"] == "live" and s["call_sid"] == "CA_sim" and not s["turns"], (s["status"], s.get("turns"))
        print("setup ok: inbound call, no customer line until the rep answers")

        t0 = time.time()
        await ws.send(json.dumps({"type": "prompt", "voicePrompt": "Thanks for calling QA Motors, this is Alex. Who do I have the pleasure of speaking with?", "lang": "en-US", "last": True}))
        reply = json.loads(await asyncio.wait_for(ws.recv(), timeout=60))
        assert reply["type"] == "text" and reply["token"] == script["persona"]["opening_line"] and time.time() - t0 < 3, reply
        print(f"rep answered -> customer opens with the scripted line in {time.time()-t0:.2f}s: {reply['token'][:80]}")

        lines = ["Great to meet you Maria. The white Tahoe Z71 is here on the lot. What made you reach out about that one?",
                 "I hear you on the drive. I won't guess a payment over the phone because I'd rather be right with your money. I can have it washed and up front at 4:30 today or 10 tomorrow, which is better?"]
        for ln in lines:
            t0 = time.time()
            await ws.send(json.dumps({"type": "prompt", "voicePrompt": ln, "lang": "en-US", "last": True}))
            reply = json.loads(await asyncio.wait_for(ws.recv(), timeout=60))
            assert reply["type"] == "text" and reply["last"] is True and reply["token"], reply
            print(f"turn {time.time()-t0:.1f}s -> {reply['token'][:110]}")
        await ws.send(json.dumps({"type": "interrupt", "utteranceUntilInterrupt": reply["token"][:20], "durationUntilInterruptMs": 900}))
        await ws.send(json.dumps({"type": "prompt", "voicePrompt": "Perfect, 10 tomorrow it is. What's the best cell to text you my direct line?", "last": True}))
        reply = json.loads(await asyncio.wait_for(ws.recv(), timeout=60))
        print("after interrupt ->", reply["token"][:110])
        # ignore partial prompts
        await ws.send(json.dumps({"type": "prompt", "voicePrompt": "partial words", "last": False}))
        await asyncio.sleep(0.3)
    s = await db.roleplay_sessions.find_one({"_id": res.inserted_id})
    interrupted = [t for t in s["turns"] if t.get("interrupted")]
    assert interrupted and len(interrupted[0]["text"]) <= 20, [t.get("text") for t in s["turns"] if t["role"] == "customer"]
    print("interrupt truncated the customer line ok:", repr(interrupted[0]["text"]))

    # websocket closed -> finalize kicked off; Twilio also posts status completed + after action (idempotent)
    requests.post(f"{API}/api/scripts/roleplay/after/{sid}?t={token}", data={"SessionStatus": "completed", "CallSid": "CA_sim"}, timeout=30)
    r = requests.post(f"{API}/api/scripts/roleplay/status/{sid}?t={token}", data={"CallStatus": "completed", "CallSid": "CA_sim"}, timeout=30)
    assert r.status_code == 204
    for _ in range(45):
        s = await db.roleplay_sessions.find_one({"_id": res.inserted_id})
        if s["status"] in ("completed", "failed", "abandoned"):
            break
        await asyncio.sleep(2)
    assert s["status"] == "completed" and s.get("evaluation_id"), (s["status"], s.get("fail_reason"))
    evs = await db.call_evaluations.count_documents({"roleplay_session_id": sid})
    assert evs == 1, evs
    print("graded once ok: score", s.get("score_pct"), "adherence", s.get("adherence_pct"), "end_reason", s.get("end_reason"))

    tok = requests.post(f"{API}/api/auth/login", json={"email": "activation-tester@invalid.imonsocial.test", "password": "NewPass123!"}, timeout=30).json()["token"]
    g = requests.get(f"{API}/api/scripts/roleplay/{sid}", headers={"Authorization": f"Bearer {tok}"}, timeout=30).json()
    assert g["mode"] == "phone" and g["status"] == "completed" and g["result"] and len(g["turns"]) >= 8, (g["mode"], g["status"], len(g["turns"]))
    print("GET session ok:", g["mode"], g["status"], g["call_status"], "turns", len(g["turns"]))

    # a no-answer call fails cleanly
    res2 = await db.roleplay_sessions.insert_one({**{k: v for k, v in s.items() if k not in ("_id", "evaluation_id", "score_pct", "adherence_pct", "ended_at", "end_reason", "call_sid")}, "status": "dialing", "turns": [], "token": "tok2"})
    requests.post(f"{API}/api/scripts/roleplay/status/{res2.inserted_id}?t=tok2", data={"CallStatus": "no-answer"}, timeout=30)
    s2 = await db.roleplay_sessions.find_one({"_id": res2.inserted_id})
    assert s2["status"] == "failed" and "No answer" in s2["fail_reason"], s2
    print("no-answer -> failed ok:", s2["fail_reason"])

    if "--keep" not in sys.argv:
        await db.roleplay_sessions.delete_many({"_id": {"$in": [res.inserted_id, res2.inserted_id]}})
        await db.call_evaluations.delete_many({"roleplay_session_id": sid})
    print("ALL OK")


asyncio.run(main())
