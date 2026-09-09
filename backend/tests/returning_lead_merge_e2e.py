"""Returning-customer e2e: lead merges into the owner's existing thread, queue/timeline honour lead_created_at,
T-5 release warning, "I've got this" keep endpoint (RBAC), auto-release after keep is skipped, flow analytics.
Safe: Twilio test-range number only, no ladder (returning owner skips it), QA manager has no push devices."""
import asyncio, os, sys
from datetime import datetime, timezone, timedelta
import httpx
from dotenv import load_dotenv
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv("/app/backend/.env")
sys.path.insert(0, "/app/backend")
API = [l.split("=", 1)[1].strip() for l in open("/app/frontend/.env") if l.startswith("REACT_APP_BACKEND_URL")][0] + "/api"
QA, QA_STORE = "6a9b2b82cc6e7504dafc33f2", "69a0b7095fddcede09591668"
TESTER = "6a978d68b8673c29063aa8b9"
WEBSITE = "69a787ca70ae63ea0ac69251"
PHONE = "+15005550171"
ok = bad = 0
def check(name, cond, extra=""):
    global ok, bad
    ok += bool(cond); bad += (not cond)
    print(("PASS " if cond else "FAIL ") + name + (f"  [{extra}]" if extra else ""))


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    now = datetime.now(timezone.utc)
    convs, flow_ids = [], []
    contact = await db.contacts.insert_one({"first_name": "Merge", "last_name": "Tester", "phone": PHONE, "user_id": QA, "store_id": QA_STORE,
                                            "status": "active", "created_at": now - timedelta(days=40)})
    cid = str(contact.inserted_id)
    personal = await db.conversations.insert_one({"user_id": QA, "contact_id": cid, "contact_phone": PHONE, "contact_name": "Merge Tester", "rep_phone": "+15005550010",
                                                  "status": "active", "ai_mode": "off", "created_at": now - timedelta(days=40), "last_message_at": now - timedelta(days=2)})
    pid = str(personal.inserted_id)
    convs.append(personal.inserted_id)
    await db.messages.insert_many([
        {"conversation_id": pid, "sender": "contact", "direction": "inbound", "content": "Old question", "timestamp": now - timedelta(days=2, minutes=5)},
        {"conversation_id": pid, "sender": "user", "content": "Old answer", "timestamp": now - timedelta(days=2)},
    ])
    from routers.lead_queue import process_returning_lead_escalations
    async with httpx.AsyncClient(timeout=60) as c:
        async def login(email, pw):
            r = await c.post(f"{API}/auth/login", json={"email": email, "password": pw})
            return {"Authorization": f"Bearer {r.json().get('token') or r.json().get('access_token')}"}
        HQ = await login("qa-manager@invalid.imonsocial.test", "Manager123!")
        HT = await login("activation-tester@invalid.imonsocial.test", "NewPass123!")
        try:
            # 1. returning customer lead merges into the existing thread
            r = await c.post(f"{API}/lead-sources/{WEBSITE}/test-lead", json={"phone": PHONE[2:], "first_name": "Merge", "last_name": "Tester", "include_ladder": False}, headers=HQ)
            check("test lead accepted", r.status_code == 200, r.text[:120])
            conv_id = r.json().get("conversation_id")
            check("lead landed in the owner's existing thread (no second conversation)", conv_id == pid, f"{conv_id} vs {pid}")
            conv = await db.conversations.find_one({"_id": personal.inserted_id})
            check("thread stamped as merged internet lead", conv.get("lead_merged") is True and conv.get("is_internet_lead") is True and conv.get("lead_count") == 2)
            check("routed to owner with release timer", conv.get("routing_kind") == "returning_owner" and conv.get("claimed_by") == QA and conv.get("release_at") is not None and conv.get("routing_resolved") is False)
            check("lead_created_at is fresh, created_at untouched", (now - (conv["lead_created_at"].replace(tzinfo=timezone.utc))).total_seconds() < 120
                  and conv["created_at"].replace(tzinfo=timezone.utc) < now - timedelta(days=39))
            check("thread AI mode preserved (rep's setting wins in hours)", conv.get("ai_mode") == "off" or conv.get("ai_mode") == "auto_reply", conv.get("ai_mode"))
            marker = await db.messages.find_one({"conversation_id": pid, "is_lead_marker": True})
            check("lead marker event inserted in the thread", marker is not None and "lead from this customer" in marker["content"], (marker or {}).get("content"))
            lead = await db.inbound_leads.find_one({"contact_id": cid}, sort=[("created_at", -1)])
            check("inbound_lead points at the merged thread", lead and lead.get("conversation_id") == pid)
            r = await c.get(f"{API}/messages/thread/{pid}", headers=HQ)
            check("thread API exposes is_lead_marker", any(m.get("is_lead_marker") for m in r.json()))
            only_one = await db.conversations.count_documents({"contact_id": cid})
            check("still exactly one conversation for this customer", only_one == 1, str(only_one))

            # 2. queue + timeline read the lead clock, not the thread's age
            r = await c.get(f"{API}/leads/queue/{QA}", headers=HQ)
            mine = [i for i in r.json()["mine"] if i["id"] == pid]
            check("merged lead shows under Mine", len(mine) == 1)
            if mine:
                it = mine[0]
                check("queue item: fresh timer, old human reply ignored (waiting)", it["waiting_seconds"] is not None and it["waiting_seconds"] < 300 and it.get("lead_merged") is True, str(it.get("waiting_seconds")))
                check("queue item carries release_at", it.get("release_at") is not None)
            r = await c.get(f"{API}/lead-sources/call-timeline/{pid}", headers=HQ)
            tl = r.json()
            ret = tl.get("returning") or {}
            check("timeline returning block", ret.get("is_returning") and ret.get("merged_thread") and ret.get("lead_count") == 2 and ret.get("release_at"), str(ret)[:160])
            check("timeline timestamps are tz-aware (UTC offset present)", str(ret.get("release_at", "")).endswith("+00:00") and str(tl.get("received_at", "")).endswith("+00:00"), f"{ret.get('release_at')} {tl.get('received_at')}")
            check("timeline: pre-lead human reply does not count", tl.get("first_human_reply_at") is None, str(tl.get("first_human_reply_at")))
            r = await c.get(f"{API}/leads/awaiting/{QA}", headers=HQ)
            check("home lead alert counts the merged lead", r.status_code == 200 and r.json().get("count", 0) >= 1, r.text[:100])

            # 3. T-5 warning
            await db.conversations.update_one({"_id": personal.inserted_id}, {"$set": {"release_at": now + timedelta(minutes=4), "owner_alert_at": now + timedelta(minutes=30)}})
            res = await process_returning_lead_escalations()
            conv = await db.conversations.find_one({"_id": personal.inserted_id})
            notif = await db.notifications.find_one({"conversation_id": pid, "type": "lead_releasing_soon", "user_id": QA})
            check("escalation job warns the owner 5 min before release", res.get("warned", 0) >= 1 and conv.get("owner_warned") is True and notif is not None, str(res))
            check("warning copy mentions I've got this", notif and "I've got this" in notif["message"] and "Releasing in" in notif["title"], (notif or {}).get("title"))
            check("lead still claimed after warning (not released)", conv.get("claimed") is True and conv.get("release_at") is not None)
            res = await process_returning_lead_escalations()
            check("warning is sent once", res.get("warned", 0) == 0, str(res))

            # 4. keep ("I've got this")
            r = await c.post(f"{API}/leads/queue/{TESTER}/keep/{pid}", headers=HT)
            check("other rep cannot keep someone else's lead (403)", r.status_code == 403, r.text[:80])
            r = await c.post(f"{API}/leads/queue/{QA}/keep/{pid}", headers=HQ)
            conv = await db.conversations.find_one({"_id": personal.inserted_id})
            check("owner keeps the lead", r.status_code == 200 and r.json().get("success") and conv.get("routing_resolved") is True and conv.get("release_at") is None and conv.get("kept_by") == QA, r.text[:80])
            notif = await db.notifications.find_one({"conversation_id": pid, "type": "lead_releasing_soon", "user_id": QA})
            check("release warning dismissed on keep", notif.get("dismissed") is True)
            sysmsg = await db.messages.find_one({"conversation_id": pid, "sender": "system", "content": {"$regex": "I've got this"}})
            check("keep logged in the thread", sysmsg is not None)
            r = await c.post(f"{API}/leads/queue/{QA}/keep/{pid}", headers=HQ)
            check("keep is idempotent", r.status_code == 200 and r.json().get("already") is True, r.text[:80])
            await db.conversations.update_one({"_id": personal.inserted_id}, {"$set": {"kept_release_probe": now - timedelta(minutes=1)}})
            res = await process_returning_lead_escalations()
            conv = await db.conversations.find_one({"_id": personal.inserted_id})
            check("kept lead never auto-releases", conv.get("claimed") is True and conv.get("claimed_by") == QA, str(res))
            r = await c.get(f"{API}/lead-sources/call-timeline/{pid}", headers=HQ)
            ret = r.json().get("returning") or {}
            check("timeline shows kept/resolved, no release_at", ret.get("resolved") is True and ret.get("release_at") is None and ret.get("kept_at"), str(ret)[:160])
            r = await c.get(f"{API}/leads/queue/{QA}", headers=HQ)
            it = next((i for i in r.json()["mine"] if i["id"] == pid), {})
            check("queue item after keep: release_at cleared, kept_at set", it.get("release_at") is None and it.get("kept_at"))

            # 5. the SAME customer comes back again -> same thread, timer re-armed; silent -> released with prev owner
            r = await c.post(f"{API}/lead-sources/{WEBSITE}/test-lead", json={"phone": PHONE[2:], "first_name": "Merge", "last_name": "Tester", "include_ladder": False}, headers=HQ)
            conv = await db.conversations.find_one({"_id": personal.inserted_id})
            check("third visit merges again, lead_count 3, timer re-armed", r.json().get("conversation_id") == pid and conv.get("lead_count") == 3 and conv.get("release_at") is not None and conv.get("routing_resolved") is False and conv.get("owner_warned") is False)
            await db.conversations.update_one({"_id": personal.inserted_id}, {"$set": {"release_at": now - timedelta(minutes=1), "owner_alerted": True}})
            res = await process_returning_lead_escalations()
            conv = await db.conversations.find_one({"_id": personal.inserted_id})
            check("silent returning lead auto-releases and remembers the owner", res.get("released", 0) >= 1 and conv.get("claimed") is False and conv.get("prev_owner_id") == QA, str(res))
            r = await c.get(f"{API}/leads/queue/{QA}", headers=HQ)
            check("released merged lead visible in the shared queue", any(i["id"] == pid for i in r.json()["unclaimed"]))
            r = await c.get(f"{API}/lead-sources/call-timeline/{pid}", headers=HQ)
            ret = r.json().get("returning") or {}
            check("timeline shows released + reason", ret.get("released_at") and ret.get("release_reason"), str(ret)[:160])

            # 6. flow analytics
            r = await c.post(f"{API}/lead-flows", json={"name": "Stats E2E Flow", "contact_mode": "text_only"}, headers=HQ)
            check("stats: create flow", r.status_code == 200, r.text[:100])
            fid = r.json()["id"]; flow_ids.append(fid)
            base = {"is_internet_lead": True, "status": "active", "store_id": QA_STORE, "user_id": QA_STORE, "flow_id": fid, "lead_source_id": WEBSITE, "contact_phone": "+15005550172", "contact_name": "Stats Lead"}
            t0 = now - timedelta(hours=2)
            ids = await db.conversations.insert_many([
                {**base, "contact_name": "Stats A", "created_at": t0, "lead_created_at": t0, "claimed": True, "claimed_by": QA, "claimed_at": t0 + timedelta(seconds=120)},
                {**base, "contact_name": "Stats B", "created_at": t0, "lead_created_at": t0, "claimed": True, "claimed_by": QA, "claimed_at": (t0 + timedelta(seconds=300)).isoformat()},
                {**base, "contact_name": "Stats C", "created_at": t0, "lead_created_at": t0, "claimed": False},
                {**base, "contact_name": "Stats T", "created_at": t0, "lead_created_at": t0, "claimed": False, "is_test": True},
            ])
            convs.extend(ids.inserted_ids)
            a, b, c3 = [str(i) for i in ids.inserted_ids[:3]]
            await db.messages.insert_many([
                {"conversation_id": a, "sender": "contact", "direction": "inbound", "content": "yes", "timestamp": t0 + timedelta(minutes=10)},
                {"conversation_id": a, "sender": "user", "content": "hi", "timestamp": t0 + timedelta(seconds=200)},
            ])
            jobs = await db.lead_call_jobs.insert_many([
                {"conversation_id": c3, "status": "exhausted", "claimed_by": None, "created_at": t0, "attempts": []},
                {"conversation_id": a, "status": "claimed", "claimed_by": QA, "created_at": t0, "attempts": []},
            ])
            r = await c.get(f"{API}/lead-flows/{fid}/stats?days=7", headers=HQ)
            s = r.json()
            check("stats: leads/claimed exclude test leads", s.get("leads") == 3 and s.get("claimed") == 2 and s.get("claimed_pct") == 67, str(s))
            check("stats: median speed-to-claim (120s, 300s -> 210s), str+datetime claimed_at both parsed", s.get("median_claim_s") == 210, str(s.get("median_claim_s")))
            check("stats: reply rate + first human reply", s.get("replied") == 1 and s.get("reply_pct") == 33 and s.get("median_first_reply_s") == 200, str(s))
            check("stats: ladder no-answer rate", s.get("ladder_runs") == 2 and s.get("no_answer") == 1 and s.get("no_answer_pct") == 50, str(s))
            r = await c.get(f"{API}/lead-flows", headers=HQ)
            f = next((x for x in r.json()["flows"] if x["id"] == fid), {})
            check("stats: library list carries stats", (f.get("stats") or {}).get("leads") == 3, str(f.get("stats")))
            r = await c.get(f"{API}/lead-flows/{fid}/stats", headers=HT)
            check("stats: reps (non-managers) get 403", r.status_code == 403, str(r.status_code))
            await db.lead_call_jobs.delete_many({"_id": {"$in": jobs.inserted_ids}})
        finally:
            for fid in flow_ids:
                await c.delete(f"{API}/lead-flows/{fid}?force=true", headers=HQ)
            await db.conversations.delete_many({"$or": [{"_id": {"$in": convs}}, {"contact_id": cid}]})
            await db.messages.delete_many({"conversation_id": {"$in": [str(i) for i in convs]}})
            await db.inbound_leads.delete_many({"contact_id": cid})
            await db.lead_deferred_actions.delete_many({"conversation_id": {"$in": [str(i) for i in convs]}})
            await db.lead_call_jobs.delete_many({"conversation_id": {"$in": [str(i) for i in convs]}})
            await db.notifications.delete_many({"conversation_id": {"$in": [str(i) for i in convs]}})
            await db.contact_events.delete_many({"contact_id": cid})
            await db.contacts.delete_one({"_id": contact.inserted_id})
            await db.ai_reply_queue.delete_many({"conversation_id": {"$in": [str(i) for i in convs]}})
    print(f"\n{ok} passed, {bad} failed")
    sys.exit(1 if bad else 0)

asyncio.run(main())
