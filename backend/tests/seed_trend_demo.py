"""Preview-only demo data for the Score Trends chart + Weekly Leaderboard on the Kubota Demo client (idempotent, `--wipe` removes).
Adds graded shops over the past six weeks for Tyler Brandt and a second salesperson, plus one parts shop, cloned from the Kubota sample scorecard."""
import asyncio
import os
import sys
import uuid
from datetime import timedelta

from bson import ObjectId
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from services import kubota_sample_shop as ks  # noqa: E402
from services import mystery_shops as ms  # noqa: E402
from services import scripts as scr  # noqa: E402

SEED_KEY = "trend_demo"
# (person, department, days_ago, score, adherence)
SHOPS = [
    ("tyler", "eq_sales", 40, 61, 58), ("tyler", "eq_sales", 33, 66, 63), ("tyler", "eq_sales", 26, 72, 70), ("tyler", "eq_sales", 19, 70, 74), ("tyler", "eq_sales", 12, 81, 79), ("tyler", "eq_sales", 9, 84, 82),
    ("tyler", "eq_sales", 1, 91, 88),
    ("maya", "eq_sales", 27, 78, 75), ("maya", "eq_sales", 13, 80, 77), ("maya", "eq_sales", 8, 76, 74), ("maya", "eq_sales", 1, 79, 80),
    ("maya", "eq_parts", 0, 86, 84),
]
PEOPLE = {"maya": {"name": "Maya Torres", "phone": "+15005550198", "email": "", "department": "eq_sales", "title": "Sales specialist", "notes": "Trend demo"}}


async def main(wipe: bool):
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    client = await db.shop_clients.find_one({"seed_key": ms.KUBOTA_DEMO_KEY})
    if not client:
        print("Kubota Demo client missing; start the backend once first")
        return
    cid = str(client["_id"])
    if wipe:
        r1 = await db.roleplay_sessions.delete_many({"seed_key": SEED_KEY})
        r2 = await db.call_evaluations.delete_many({"seed_key": SEED_KEY})
        r3 = await db.shop_targets.delete_many({"seed_key": SEED_KEY})
        print(f"wiped {r1.deleted_count} shops, {r2.deleted_count} evaluations, {r3.deleted_count} people")
        return
    if await db.roleplay_sessions.find_one({"seed_key": SEED_KEY}):
        print("already seeded")
        return
    tyler = await db.shop_targets.find_one({"client_id": cid, "seed_key": ks.SEED_KEY})
    if not tyler:
        print("Kubota sample person missing; start the backend once first")
        return
    ids = {"tyler": str(tyler["_id"])}
    for key, p in PEOPLE.items():
        cur = await db.shop_targets.find_one({"client_id": cid, "phone": p["phone"]})
        if not cur:
            res = await db.shop_targets.insert_one({**p, "client_id": cid, "seed_key": SEED_KEY, "active": True, "challenge_history": [], "created_at": ms._now(), "updated_at": ms._now()})
            ids[key] = str(res.inserted_id)
        else:
            ids[key] = str(cur["_id"])
    names = {"tyler": tyler["name"], **{k: v["name"] for k, v in PEOPLE.items()}}
    phones = {"tyler": tyler.get("phone"), **{k: v["phone"] for k, v in PEOPLE.items()}}
    now = ms._now()
    n = 0
    for who, dept, days_ago, score, adh in SHOPS:
        when = (now - timedelta(days=days_ago)).replace(hour=10 + (n % 6), minute=(n * 7) % 60, second=0, microsecond=0)
        if when > now:
            when = now - timedelta(hours=1)
        sid = ObjectId()
        duration_s = 300 + n * 11
        results = [dict(r, passed=(i / max(1, len(ks.RESULTS)) * 100) < score, ai_passed=True, confidence=0.9, override=None) for i, r in enumerate(ks.RESULTS)]
        ev = {"call_sid": f"RP_{sid}", "is_roleplay": False, "is_mystery_shop": True, "roleplay_session_id": str(sid), "assignment_id": None, "shop_client_id": cid, "shop_target_id": ids[who],
              "user_id": None, "rep_name": names[who], "store_id": None, "contact_id": None, "contact_name": f"{ks.PERSONA['name']} (mystery shopper)", "conversation_id": None, "inbox_id": None,
              "scorecard_id": None, "scorecard_name": "Equipment Sales Call" if dept == "eq_sales" else "Equipment Parts Call", "department": "Sales" if dept == "eq_sales" else "Parts", "duration_s": duration_s, "direction": "inbound", "call_at": when,
              "results": results, "score_pct": score, "critical_misses": [] if score >= 70 else [ks.RESULTS[-1]["criterion_id"]] if ks.RESULTS and ks.RESULTS[-1].get("criterion_id") else [],
              "summary": ks.SUMMARY, "wins": ks.WINS[:2], "coaching": ks.COACHING[:2], "customer_sentiment": "positive" if score >= 75 else "neutral", "call_type": "mystery_shop",
              "script_id": None, "script_title": "Kubota Sales Practice Call" if dept == "eq_sales" else "Kubota Parts Practice Call", "channel": "call", "adherence": {**ks.ADHERENCE, "score_pct": adh},
              "transcript": scr.transcript_text({"turns": ks.TURNS}), "model": "seed", "graded_by": "seed", "seed_key": SEED_KEY,
              "created_at": when + timedelta(seconds=duration_s + 40), "updated_at": when + timedelta(seconds=duration_s + 40), "alerts_sent_at": None, "alerted_user_ids": []}
        ev_res = await db.call_evaluations.insert_one(ev)
        await db.roleplay_sessions.insert_one({
            "_id": sid, "kind": "mystery_shop", "seed_key": SEED_KEY, "client_id": cid, "target_id": ids[who], "rep_name": names[who], "rep_phone": phones[who], "department": dept, "industry": "equipment",
            "status": "completed", "outcome": "completed", "direction": "inbound", "difficulty": "medium", "manual": True, "attempts": 1, "max_attempts": 1,
            "live_transport": "gpt-live", "live_end_reason": "customer_ended", "live_seconds": duration_s,
            "script_id": None, "script_title": ev["script_title"], "persona": dict(ks.PERSONA), "curveballs": [],
            "scheduled_for": when, "started_at": when, "ended_at": when + timedelta(seconds=duration_s), "turns": [{**t, "at": when + timedelta(seconds=i * 12), "audio_url": None, "mood": "neutral"} for i, t in enumerate(ks.TURNS[:8])],
            "score_pct": score, "adherence_pct": adh, "evaluation_id": str(ev_res.inserted_id), "score_token": uuid.uuid4().hex, "score_sms_status": None,
            "created_at": when, "updated_at": when + timedelta(seconds=duration_s + 40)})
        n += 1
    print(f"seeded {n} graded shops for {', '.join(names.values())} on Kubota Demo ({cid})")


if __name__ == "__main__":
    asyncio.run(main("--wipe" in sys.argv))
