"""Channel mix for report checks (preview, idempotent, --wipe): QA Jeep 979a gets one COMPLETED text shop and one COMPLETED
email shop this month next to its phone shops, with graded evaluations, so the report / PDF / scorecard can be checked.
Run: cd /app/backend && set -a && . ./.env && set +a && python tests/seed_channel_mix.py [--wipe]"""
import asyncio
import os
import sys
import uuid
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

from services import mystery_shops as ms

CLIENT_NAME = "QA Jeep 979a"


async def main(wipe: bool):
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    client = await db.shop_clients.find_one({"name": CLIENT_NAME})
    if not client:
        print("client missing"); return
    cid = str(client["_id"])
    old = await db.roleplay_sessions.find({"client_id": cid, "qa_channel_seed": True}, {"evaluation_id": 1}).to_list(20)
    await db.call_evaluations.delete_many({"_id": {"$in": [ObjectId(o["evaluation_id"]) for o in old if o.get("evaluation_id")]}})
    await db.roleplay_sessions.delete_many({"client_id": cid, "qa_channel_seed": True})
    if wipe:
        print("wiped"); return
    target = await db.shop_targets.find_one({"client_id": cid, "department": "sales"}) or await db.shop_targets.find_one({"client_id": cid})
    me = await db.users.find_one({"email": "forest@imosapp.com"})
    now = ms._now()
    out = []
    for mode, hours_ago, score, turns, subj in (
        ("text", 30, 57, [
            {"role": "customer", "text": "Hey, I'm looking at the used SUV you have listed online. Any idea what the monthly payment would be on it?", "at": now - timedelta(hours=30)},
            {"role": "rep", "text": "Hi there! My name is Sam! Who is this?", "at": now - timedelta(hours=30) + timedelta(seconds=45), "delay_s": 45},
            {"role": "customer", "text": "It's Marcus. Trying to get a ballpark monthly on that used SUV before I come in. What would it be with like 3k down?", "at": now - timedelta(hours=30) + timedelta(minutes=2)},
            {"role": "rep", "text": "Sounds great! What SUV are you looking at?", "at": now - timedelta(hours=30) + timedelta(minutes=4), "delay_s": 120},
            {"role": "customer", "text": "The 2021 Grand Cherokee, about 24k.", "at": now - timedelta(hours=30) + timedelta(minutes=5)},
            {"role": "rep", "text": "With 3k down over 72 months you are around $380 a month before taxes. Want to come see it tomorrow at 5:30?", "at": now - timedelta(hours=30) + timedelta(minutes=6), "delay_s": 60},
        ], None),
        ("email", 50, 71, [
            {"role": "customer", "text": "Hi, is the 2022 Wrangler Sahara still available? What is the out-the-door price?", "at": now - timedelta(hours=50)},
            {"role": "rep", "text": "Hi Priya, yes it is still here. I would love to get you in for a look. When works?", "at": now - timedelta(hours=50) + timedelta(minutes=48), "delay_s": 2880},
            {"role": "customer", "text": "Maybe Saturday. Can you send the out-the-door number first?", "at": now - timedelta(hours=50) + timedelta(minutes=55)},
            {"role": "rep", "text": "Sure, it is $46,900 plus tax and a $399 doc fee. Saturday at 10?", "at": now - timedelta(hours=50) + timedelta(hours=2), "delay_s": 3900},
        ], "Re: 2022 Wrangler Sahara availability"),
    ):
        started = now - timedelta(hours=hours_ago)
        sid = ObjectId()
        persona = {"name": "Marcus Hale" if mode == "text" else "Priya Bennett", "goals": "Get a ballpark payment before driving over"}
        ev_id = ObjectId()
        results = [{"criterion_id": "text_first", "text": f"Replied to the first {'text' if mode == 'text' else 'email'} within {'5 minutes' if mode == 'text' else '30 minutes'}", "critical": True, "weight": 2, "passed": mode == "text", "evidence": "45 seconds" if mode == "text" else "48 minutes"},
                   {"criterion_id": "text_pace", "text": "Kept every reply under two minutes" if mode == "text" else "Kept every reply under two hours", "critical": False, "weight": 1, "passed": True, "evidence": ""},
                   {"criterion_id": "ask_name", "text": "Asked for the customer's name", "critical": False, "weight": 1, "passed": True, "evidence": "Who is this?"},
                   {"criterion_id": "appt", "text": "Asked for a specific appointment time", "critical": True, "weight": 2, "passed": True, "evidence": "tomorrow at 5:30"},
                   {"criterion_id": "price", "text": "Answered the price or payment question directly", "critical": False, "weight": 1, "passed": mode == "email", "evidence": ""}]
        summary = ("Marcus wanted a ballpark payment on a used SUV. Sam replied inside a minute, asked who it was and what vehicle, gave a payment range and set a time for tomorrow." if mode == "text"
                   else "Priya asked if the Wrangler was available and for an out-the-door number. Sam took 48 minutes to reply and answered the price on the second email, then offered Saturday at 10.")
        await db.call_evaluations.insert_one({"_id": ev_id, "call_sid": f"RP_{sid}", "roleplay_session_id": str(sid), "is_mystery_shop": True, "shop_client_id": cid, "shop_target_id": str(target["_id"]), "score_pct": score, "summary": summary,
                                              "wins": ["Fast first reply" if mode == "text" else "Answered the price plainly"], "coaching": ["Answer the payment question before asking for the visit" if mode == "text" else "Reply to the first email within 30 minutes"],
                                              "critical_misses": [] if mode == "text" else ["Replied to the first email within 30 minutes"], "results": results, "channel": mode, "graded_by": "ai", "scorecard_name": f"Sales Phone-Up ({mode})",
                                              "transcript": "\n".join(f"{'REP' if t['role'] == 'rep' else 'CUSTOMER'}: {t['text']}" for t in turns), "rep_name": target["name"], "created_at": now, "qa_channel_seed": True})
        doc = {"_id": sid, "kind": "mystery_shop", "mode": mode, "status": "completed", "user_id": None, "client_id": cid, "target_id": str(target["_id"]), "rep_name": target["name"], "rep_phone": target.get("phone"), "rep_email": target.get("email") or "sam@qajeep.example",
               "department": target.get("department") or "sales", "industry": "automotive", "store_name": CLIENT_NAME, "locale": client.get("locale"), "script_id": "seed", "script_title": "Shopper: payment before I drive over" if mode == "text" else "Shopper: is it still available?",
               "direction": "outbound", "persona": persona, "curveballs": [], "scheduled_for": started, "started_at": started, "ended_at": started + timedelta(hours=3), "attempts": 1, "max_attempts": 1, "manual": True, "notify_sms": False,
               "token": uuid.uuid4().hex, "score_token": uuid.uuid4().hex, "turns": turns, "from_number": "+15005550140", "from_email": "marcus.hale@shopper.example", "subject": subj, "outcome": "replied", "end_reason": "shopper_done",
               "evaluation_id": str(ev_id), "score_pct": score, "adherence_pct": 60, "created_by": str(me["_id"]), "created_at": started, "updated_at": now, "qa_channel_seed": True}
        await db.roleplay_sessions.insert_one(doc)
        out.append((mode, str(sid), doc["score_token"]))
    for mode, sid, tok in out:
        print(f"{mode}: session {sid}  scorecard /shop-score/{tok}")
    print(f"report: /shop-report/{client.get('report_token')}   shops tab: /admin/mystery-shops/{cid}?tab=calls")


if __name__ == "__main__":
    asyncio.run(main("--wipe" in sys.argv))
