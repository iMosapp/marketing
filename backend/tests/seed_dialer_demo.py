"""Preview-only demo data for the Power Dialer UI: a campaign with a mixed lead list, an ENDED session and its attempt log,
so the campaign detail (Leads / Call log / Settings), the session screen (ended state) and the DNC list can be looked at
without placing a single call. Idempotent. `--wipe` removes everything it created.
Run: cd /app/backend && set -a && . ./.env && set +a && python tests/seed_dialer_demo.py [--wipe]"""
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services import compliance as comp  # noqa: E402
from services import dialer as eng  # noqa: E402

NAME = "QA Demo: Utah dealers"
LEADS = [("Sam", "Seller", "Peak Motors", "+15005550101", "UT"), ("Val", "Advisor", "Canyon Auto", "+15005550102", "UT"), ("Bea", "Buyer", "", "+13055550103", "FL"),
         ("Tex", "Owner", "Lone Star Cars", "+12145550104", "TX"), ("Cal", "Manager", "Bay Motors", "+14155550105", "CA"), ("Dee", "Director", "Miami Wheels", "+17865550106", "FL")]


async def main(wipe: bool):
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    me = await db.users.find_one({"email": "forest@imosapp.com"})
    old = await db[eng.CAMPAIGNS].find_one({"name": NAME})
    if old:
        cid = str(old["_id"])
        for coll in (eng.LEADS, eng.ATTEMPTS, eng.BURSTS, eng.SESSIONS):
            await db[coll].delete_many({"campaign_id": cid})
        await db[eng.CAMPAIGNS].delete_one({"_id": old["_id"]})
    await db[comp.DNC_LIST].delete_many({"phone": {"$in": [l[3] for l in LEADS]}})
    if wipe:
        print("wiped")
        return
    c = await eng.create_campaign(db, me, {"name": NAME, "audience": "b2b", "lines": 2, "connect_mode": "instant", "seller_name": "i'M On Social", "script": "Hi {first name}, this is Forest with i'M On Social. Quick one: who handles your internet leads today?", "rep_ids": [str(me["_id"])]})
    await eng.import_rows(db, c, [{"first_name": f, "last_name": l, "company": co, "phone": p, "state": st} for f, l, co, p, st in LEADS], "csv", me)
    await comp.add_dnc(db, LEADS[5][3], "press9", campaign_id=str(c["_id"]), note="Pressed 9 on the abandonment message")
    now = datetime.now(timezone.utc)
    s = {"campaign_id": str(c["_id"]), "user_id": str(me["_id"]), "store_id": c.get("store_id"), "status": "ended", "token": "demo", "rep_phone": "+15005550006", "caller_id": "+14352203414",
         "started_at": now - timedelta(hours=2), "ended_at": now - timedelta(hours=1, minutes=40), "end_reason": "app", "last_activity_at": now - timedelta(hours=1, minutes=40),
         "rep_call_sid": "CA_demo_rep", "conference": "dialer-demo", "current_burst_id": None, "current_attempt_id": None,
         "stats": {"bursts": 3, "dials": 5, "connects": 2, "voicemails": 1, "abandoned": 1, "dispositions": 2}}
    sid = (await db[eng.SESSIONS].insert_one(s)).inserted_id
    leads = {l["phone"]: l async for l in db[eng.LEADS].find({"campaign_id": str(c["_id"])})}
    def att(phone, minutes_ago, **kw):
        l = leads[phone]
        base = {"burst_id": "demo", "session_id": str(sid), "campaign_id": str(c["_id"]), "lead_id": str(l["_id"]), "user_id": str(me["_id"]), "phone": phone, "caller_id": "+14352203414",
                "started_at": now - timedelta(minutes=minutes_ago), "ended_at": now - timedelta(minutes=minutes_ago - 1), "answered_live": False, "abandoned": False, "answered_by": "human",
                "lead_name": eng.lead_name(l), "lead_state": l.get("state"), "lead_tz": l.get("tz"), "local_time": "11:15 AM", "token": "demo", "disposition": None, "notes": "",
                "compliance": {"audience": "b2b", "mode": "instant", "dnc": "clear", "window_ok": True, "lines": 2}}
        return {**base, **kw}
    await db[eng.ATTEMPTS].insert_many([
        att(LEADS[0][3], 118, status="connected", answered_live=True, connected_at=now - timedelta(minutes=118), talk_s=214, duration_s=220, disposition="interested", notes="Wants a demo Tuesday 10am", dispositioned_at=now - timedelta(minutes=113)),
        att(LEADS[1][3], 118, status="canceled", answered_by=None),
        att(LEADS[2][3], 110, status="voicemail", answered_by="machine_end_beep"),
        att(LEADS[3][3], 105, status="connected", answered_live=True, connected_at=now - timedelta(minutes=105), talk_s=61, disposition="callback", notes="Call back Thursday afternoon", dispositioned_at=now - timedelta(minutes=102)),
        att(LEADS[5][3], 105, status="abandoned", answered_live=True, abandoned=True, optout_pressed=True),
    ])
    await db[eng.LEADS].update_one({"_id": leads[LEADS[0][3]]["_id"]}, {"$set": {"status": "done", "disposition": "interested", "attempts": 1, "last_outcome": "interested", "notes": "Wants a demo Tuesday 10am"}})
    await db[eng.LEADS].update_one({"_id": leads[LEADS[1][3]]["_id"]}, {"$set": {"status": "queued", "attempts": 1, "last_outcome": "canceled", "next_attempt_at": now + timedelta(hours=20)}})
    await db[eng.LEADS].update_one({"_id": leads[LEADS[2][3]]["_id"]}, {"$set": {"status": "queued", "attempts": 1, "last_outcome": "voicemail", "next_attempt_at": now + timedelta(hours=22)}})
    await db[eng.LEADS].update_one({"_id": leads[LEADS[3][3]]["_id"]}, {"$set": {"status": "callback", "disposition": "callback", "attempts": 1, "prio": 0, "last_outcome": "callback", "next_attempt_at": now + timedelta(days=2)}})
    print(f"campaign {c['_id']}  session {sid}  -> /dialer/campaign/{c['_id']}  /dialer/session/{sid}")


if __name__ == "__main__":
    asyncio.run(main("--wipe" in sys.argv))
