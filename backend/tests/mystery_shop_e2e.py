"""Mystery Shop Clients end-to-end (preview): client + people -> challenge rotation -> a simulated shop call over the relay websocket -> grading
-> store report JSON + PDF (public link) -> proposal -> public sign -> Stripe invoice (sandbox). Run: cd /app/backend && python tests/mystery_shop_e2e.py"""
import asyncio
import json
import os
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone

import requests
import websockets
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
API = os.environ.get("TEST_API_URL") or "http://localhost:8001"
WS = API.replace("https://", "wss://").replace("http://", "ws://")
WIPE = "--wipe" in sys.argv


def login(email, pw):
    r = requests.post(f"{API}/api/auth/login", json={"email": email, "password": pw}, timeout=30)
    r.raise_for_status()
    return r.json().get("token") or r.json().get("access_token")


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    if WIPE:
        cids = [str(c["_id"]) async for c in db.shop_clients.find({"name": {"$regex": "^QA Jeep"}}, {"_id": 1})]
        await db.roleplay_sessions.delete_many({"kind": "mystery_shop", "client_id": {"$in": cids}})
        await db.call_evaluations.delete_many({"shop_client_id": {"$in": cids}})
        await db.shop_targets.delete_many({"client_id": {"$in": cids}})
        await db.shop_proposals.delete_many({"client_id": {"$in": cids}})
        await db.shop_clients.delete_many({"name": {"$regex": "^QA Jeep"}})
        print("wiped", len(cids), "QA clients")
        return
    admin = login("forest@imosapp.com", "Admin123!")
    rep = login("activation-tester@invalid.imonsocial.test", "NewPass123!")
    H = {"Authorization": f"Bearer {admin}"}
    assert requests.get(f"{API}/api/shop-clients", headers={"Authorization": f"Bearer {rep}"}, timeout=30).status_code == 403
    print("rep 403 ok")

    c = requests.post(f"{API}/api/shop-clients", headers=H, json={"name": f"QA Jeep {uuid.uuid4().hex[:4]}", "brand": "Jeep, Ram", "city": "Sandy", "state": "UT", "contact_name": "Pat Manager", "contact_email": "pat@example.invalid",
                                                                 "plan": {"sales_per_month": 4, "service_per_month": 2, "price_monthly": 400}, "hours": {"start": "00:00", "end": "23:59", "days": [0, 1, 2, 3, 4, 5, 6]},
                                                                 "vehicles": ["2023 Jeep Grand Cherokee L Limited", "2022 Ram 1500 Big Horn"]}, timeout=30)
    assert c.status_code == 200, c.text
    client = c.json(); cid = client["id"]
    print("client ok", cid, "report token", client["report_token"][:6])
    assert requests.post(f"{API}/api/shop-clients/{cid}/people", headers=H, json={"name": "Sam Seller", "phone": "5005550006", "department": "sales"}, timeout=30).status_code == 200
    assert requests.post(f"{API}/api/shop-clients/{cid}/people", headers=H, json={"name": "Sam Seller", "phone": "5005550006", "department": "sales"}, timeout=30).status_code == 409
    assert requests.post(f"{API}/api/shop-clients/{cid}/people", headers=H, json={"name": "Bad", "phone": "123", "department": "sales"}, timeout=30).status_code == 400
    p2 = requests.post(f"{API}/api/shop-clients/{cid}/people", headers=H, json={"name": "Val Advisor", "phone": "5005550007", "department": "service", "title": "Service advisor"}, timeout=30).json()
    detail = requests.get(f"{API}/api/shop-clients/{cid}", headers=H, timeout=30).json()
    assert len(detail["people"]) == 2 and detail["report_url"].endswith(client["report_token"])
    sam = next(p for p in detail["people"] if p["name"] == "Sam Seller")
    print("people ok")

    ch = requests.get(f"{API}/api/shop-clients/{cid}/challenges", headers=H, timeout=30).json()["challenges"]
    sales_pool = [x for x in ch if x["department"] == "sales"]
    assert len(sales_pool) >= 5 and all(x["direction"] == "inbound" for x in ch), len(ch)
    custom = requests.post(f"{API}/api/shop-clients/{cid}/challenges", headers=H, json={"title": "Shopper: Wrangler lift kit question", "department": "sales", "body": "Answer the accessory question, then sell the visit.",
                                                                                     "success_points": ["Answers the accessory question", "Offers two times"], "persona": {"name": "Jo Rivera", "voice": "young", "summary": "Wants a lifted Wrangler", "opening_line": "Hey, do you guys do lift kits on the Wranglers you sell?"}}, timeout=30)
    assert custom.status_code == 200 and custom.json()["client_specific"], custom.text
    lib = requests.get(f"{API}/api/scripts", headers=H, timeout=30).json()["scripts"]
    assert not any(s["title"].startswith("Shopper:") for s in lib), "challenge pool leaked into the practice library"
    print("challenges ok:", len(ch), "global +1 custom; library clean")

    # rotation: 6 sales challenges in the pool -> 6 picks are all different, the 7th repeats the oldest
    from services import mystery_shops as ms
    cdoc = await db.shop_clients.find_one({"_id": __import__("bson").ObjectId(cid)})
    tdoc = await db.shop_targets.find_one({"_id": __import__("bson").ObjectId(sam["id"])})
    picked = []
    pool_n = len(sales_pool) + 1  # + the custom one
    for _ in range(pool_n + 1):
        tdoc = await db.shop_targets.find_one({"_id": tdoc["_id"]})
        s = await ms.pick_challenge(db, cdoc, tdoc)
        picked.append(str(s["_id"]))
        await db.shop_targets.update_one({"_id": tdoc["_id"]}, {"$push": {"challenge_history": str(s["_id"])}})
    assert len(set(picked[:-1])) == pool_n and picked[-1] == picked[0], picked
    await db.shop_targets.update_one({"_id": tdoc["_id"]}, {"$set": {"challenge_history": []}})
    print("rotation ok: no repeats until the pool is exhausted")

    # persona fill uses the client's vehicles
    filled = ms.fill_persona(sales_pool[0]["persona"], cdoc, "sales")
    assert "{vehicle}" not in json.dumps(filled) and ("Jeep" in json.dumps(filled) or "Ram" in json.dumps(filled)), filled
    print("persona fill ok:", filled["opening_line"][:90])

    # plan the month: 4 sales + 2 service scheduled, spread, people rotate
    made = requests.post(f"{API}/api/shop-clients/{cid}/plan-month", headers=H, json={}, timeout=60).json()["created"]
    calls = requests.get(f"{API}/api/shop-clients/{cid}/calls", headers=H, timeout=30).json()["calls"]
    assert made == {"sales": 4, "service": 2} and len(calls) == 6 and all(x["status"] == "scheduled" for x in calls), (made, len(calls))
    again = requests.post(f"{API}/api/shop-clients/{cid}/plan-month", headers=H, json={}, timeout=60).json()["created"]
    assert again == {"sales": 0, "service": 0}, again
    print("planner ok: 6 scheduled, idempotent")

    # a scheduled call can be cancelled (and frees the challenge for that person)
    victim = calls[0]
    assert requests.delete(f"{API}/api/shop-clients/calls/{victim['id']}", headers=H, timeout=30).status_code == 200

    # simulate a shop call: create + drive the Twilio side by hand (relay connects the moment the line is answered)
    call = await ms.create_shop_call(db, cdoc, tdoc, datetime.now(timezone.utc), manual=True, script=await db.scripts.find_one({"slug": "shop_sales_availability"}))
    sid, token = str(call["_id"]), call["token"]
    await db.roleplay_sessions.update_one({"_id": call["_id"]}, {"$set": {"status": "dialing", "started_at": datetime.now(timezone.utc), "attempts": 1, "call_sid": "CA_shop_sim"}})
    # answering-machine detection is OFF for shop calls: it kept cutting off real people mid-greeting, so even a machine label must still connect
    r = requests.post(f"{API}/api/scripts/roleplay/twiml/{sid}?t={token}", data={"AnsweredBy": "machine_end_beep", "CallSid": "CA_shop_sim"}, timeout=30)
    assert r.status_code == 200 and "ConversationRelay" in r.text and "<Hangup/>" not in r.text, r.text[:300]
    s = await db.roleplay_sessions.find_one({"_id": call["_id"]})
    assert s["status"] == "dialing" and not s.get("outcome"), (s["status"], s.get("outcome"))
    print("machine label no longer hangs up the call ok")
    await db.roleplay_sessions.update_one({"_id": call["_id"]}, {"$set": {"status": "dialing", "started_at": datetime.now(timezone.utc), "attempts": 2, "call_sid": "CA_shop_sim2"}})
    r = requests.post(f"{API}/api/scripts/roleplay/twiml/{sid}?t={token}", data={"AnsweredBy": "human", "CallSid": "CA_shop_sim2"}, timeout=30)
    assert r.status_code == 200 and "ConversationRelay" in r.text and 'welcomeGreeting="Hi, is this Sam?"' in r.text, r.text[:300]
    print("human -> relay twiml with 'Hi, is this Sam?' ok")
    async with websockets.connect(f"{WS}/api/scripts/roleplay/relay/{sid}/{token}", open_timeout=30) as ws:
        await ws.send(json.dumps({"type": "setup", "sessionId": "VX_shop", "callSid": "CA_shop_sim2"}))
        await asyncio.sleep(0.4)
        s = await db.roleplay_sessions.find_one({"_id": call["_id"]})
        assert s["status"] == "live" and s["turns"][0]["text"] == "Hi, is this Sam?", s.get("turns")
        t0 = time.time()
        await ws.send(json.dumps({"type": "prompt", "voicePrompt": "Yeah, this is Sam.", "last": True}))
        reply = json.loads(await asyncio.wait_for(ws.recv(), timeout=60))
        assert reply["type"] == "text" and reply["token"] == s["persona"]["opening_line"] and time.time() - t0 < 3, reply
        print("rep answered -> scripted opening in", f"{time.time()-t0:.2f}s:", reply["token"][:80])
        for line in ["Yes it is, it just came in. Who am I speaking with?", "Great to meet you Dana. Are you going to have anything to trade in?",
                     "I'd love to have it up front for you. I have 4:30 today or 10 tomorrow, which works better? And what's the best cell for you in case we get cut off?"]:
            await ws.send(json.dumps({"type": "prompt", "voicePrompt": line, "last": True}))
            reply = json.loads(await asyncio.wait_for(ws.recv(), timeout=60))
            print("  shopper ->", reply["token"][:100])
        await ws.send(json.dumps({"type": "prompt", "voicePrompt": "Are you a real person or is this a recording?", "last": True}))
        reply = json.loads(await asyncio.wait_for(ws.recv(), timeout=60))
        low = reply["token"].lower()
        assert "ai" not in low.split() and "artificial" not in low and "mystery" not in low, reply
        print("  stays in character ->", reply["token"][:100])
    r = requests.post(f"{API}/api/scripts/roleplay/status/{sid}?t={token}", data={"CallStatus": "completed", "CallSid": "CA_shop_sim2"}, timeout=30)
    assert r.status_code == 204
    for _ in range(60):
        s = await db.roleplay_sessions.find_one({"_id": call["_id"]})
        if s["status"] in ("completed", "failed"):
            break
        await asyncio.sleep(2)
    assert s["status"] == "completed" and s.get("evaluation_id") and s.get("score_pct") is not None, (s["status"], s.get("fail_reason"))
    ev = await db.call_evaluations.find_one({"_id": __import__("bson").ObjectId(s["evaluation_id"])})
    assert ev["is_mystery_shop"] and ev["call_type"] == "mystery_shop" and ev["shop_client_id"] == cid and ev["user_id"] is None and ev["scorecard_name"] == "Sales Phone-Up", ev.get("scorecard_name")
    print("graded ok: score", s["score_pct"], "adherence", s.get("adherence_pct"), "card", ev["scorecard_name"])
    # the shop must not show up in the super admin's team call scores
    team = requests.get(f"{API}/api/scorecards/team?days=30", headers=H, timeout=60).json()
    assert not any(a.get("evaluation_id") == s["evaluation_id"] for a in (team.get("alerts") or [])) and cid not in json.dumps(team)
    detail_call = requests.get(f"{API}/api/shop-clients/calls/{sid}", headers=H, timeout=30).json()
    assert detail_call["evaluation"]["score_pct"] == s["score_pct"] and len(detail_call["transcript_turns"]) >= 8 and detail_call["attempt_history"] == []
    print("call detail ok")

    # report: admin + public + pdf
    rep_json = requests.get(f"{API}/api/shop-clients/{cid}/report", headers=H, timeout=60).json()
    assert rep_json["summary"]["completed"] == 1 and rep_json["people"][0]["name"] == "Sam Seller" and rep_json["people"][0]["completed"] == 1 and rep_json["criteria"], rep_json["summary"]
    pub = requests.get(f"{API}/api/public/shop-report/{client['report_token']}", timeout=60)
    assert pub.status_code == 200 and pub.json()["summary"]["completed"] == 1 and "target_id" not in pub.json()["calls"][0]
    assert requests.get(f"{API}/api/public/shop-report/nope", timeout=30).status_code == 404
    pdf = requests.get(f"{API}/api/public/shop-report/{client['report_token']}.pdf", timeout=120)
    assert pdf.status_code == 200 and pdf.headers["content-type"].startswith("application/pdf") and pdf.content[:4] == b"%PDF" and len(pdf.content) > 3000, pdf.headers
    print("report ok: json + public + pdf", len(pdf.content), "bytes; store misses most:", rep_json["criteria"][0]["text"][:60], rep_json["criteria"][0]["pass_pct"], "%")

    # proposal -> public view -> sign -> stripe invoice
    prop = requests.post(f"{API}/api/shop-clients/{cid}/proposals", headers=H, json={"sales_per_month": 20, "service_per_month": 20, "price_monthly": 400, "term_months": 3, "notes": "Kickoff call included."}, timeout=30)
    assert prop.status_code == 200, prop.text
    prop = prop.json(); ptoken = prop["token"]
    assert prop["status"] == "draft" and prop["url"].endswith(ptoken)
    view = requests.get(f"{API}/api/public/proposal/{ptoken}", timeout=30).json()
    assert view["status"] == "viewed" and any("400" in sec["body"] for sec in view["sections"]) and view["terms"]["sales_per_month"] == 20
    assert requests.post(f"{API}/api/public/proposal/{ptoken}/sign", json={"name": "Pat Manager", "email": "pat@example.invalid", "agree": False}, timeout=30).status_code == 400
    signed = requests.post(f"{API}/api/public/proposal/{ptoken}/sign", json={"name": "Pat Manager", "title": "GM", "email": "pat.manager+qa@example.com", "agree": True}, timeout=90)
    assert signed.status_code == 200, signed.text
    inv = signed.json()["invoice"]
    assert inv.get("hosted_invoice_url", "").startswith("https://") and inv["status"] == "open" and inv["amount"] == 400.0, inv
    assert requests.post(f"{API}/api/public/proposal/{ptoken}/sign", json={"name": "Pat Manager", "email": "pat@example.invalid", "agree": True}, timeout=30).status_code == 409
    props = requests.get(f"{API}/api/shop-clients/{cid}/proposals", headers=H, timeout=60).json()["proposals"]
    assert props[0]["status"] == "signed" and props[0]["signer"]["name"] == "Pat Manager" and "ip" not in props[0]["signer"]
    assert requests.delete(f"{API}/api/shop-clients/proposals/{props[0]['id']}", headers=H, timeout=30).status_code == 409
    print("proposal ok: signed, Stripe invoice", inv["status"], inv["hosted_invoice_url"][:60])
    # webhook marks paid
    from services.mystery_shops import mark_invoice_paid
    await mark_invoice_paid(db, inv.get("stripe_invoice_id") or (await db.shop_proposals.find_one({"token": ptoken}))["invoice"]["stripe_invoice_id"])
    pdoc = await db.shop_proposals.find_one({"token": ptoken})
    cdoc = await db.shop_clients.find_one({"_id": cdoc["_id"]})
    assert pdoc["status"] == "paid" and cdoc["billing"]["status"] == "paid"
    print("invoice.paid webhook path ok")
    print("ALL OK  (client kept for UI checks: run with --wipe to remove QA clients)")


asyncio.run(main())
