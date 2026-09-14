"""Flow editor rep pool: GET /lead-flows/{id} must list the flow's own team (flow store + every store / shared inbox whose
sources use the flow), not the caller's store. Repro of "only 3 people as options" when an admin edits another store's flow."""
import asyncio
import os
from datetime import datetime, timezone

import httpx
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

API = os.environ.get("TEST_API_URL", "http://localhost:8001").rstrip("/")
QA_STORE = "69a0b7095fddcede09591668"
OTHER_STORE = "69ac0449ed33c7b2ec6c71aa"  # TEST_NewBiz, 1 member
SALES_INBOX = "6aa3673e65d794ba9962f1bc"


async def _login(c, email, pw):
    r = await c.post(f"{API}/api/auth/login", json={"email": email, "password": pw})
    r.raise_for_status()
    d = r.json()
    u = d.get("user") or {}
    return {"Authorization": f"Bearer {d.get('token') or d.get('access_token')}", "X-User-ID": str(u.get("_id") or u.get("id") or d.get("user_id"))}


async def _run():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    now = datetime.now(timezone.utc)
    flow = await db.lead_flows.insert_one({"name": "QA cross-store flow", "store_id": OTHER_STORE, "owner_user_id": None, "contact_mode": "text_and_call",
                                           "call_attempts": [{"user_ids": ["@inbox"], "delay_seconds": 0}], "workflow_user_ids": [], "created_at": now, "updated_at": now, "qa_flow_reps": True})
    src = await db.lead_sources.insert_one({"name": "QA cross-store source", "store_id": QA_STORE, "inbox_id": SALES_INBOX, "team_id": SALES_INBOX, "flow_id": str(flow.inserted_id),
                                            "is_active": True, "created_at": now, "qa_flow_reps": True})
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            h = await _login(c, "forest@imosapp.com", "Admin123!")
            r = await c.get(f"{API}/api/lead-flows/{flow.inserted_id}", headers=h)
            assert r.status_code == 200, r.text
            reps = r.json()["reps"]
            ids = {p["id"] for p in reps}
            names = {p["name"] for p in reps}
            # the flow's own store (before the fix this was the whole pool when the caller sat on that store)
            other_member = await db.users.find_one({"$or": [{"store_id": OTHER_STORE}, {"store_id": ObjectId(OTHER_STORE)}]}, {"_id": 1})
            assert other_member and str(other_member["_id"]) in ids, "flow store member missing"
            # the source's store team + its shared inbox members must be pickable
            inbox = await db.shared_inboxes.find_one({"_id": ObjectId(SALES_INBOX)}, {"assigned_user_ids": 1})
            for uid in inbox["assigned_user_ids"]:
                assert str(uid) in ids, f"inbox member {uid} missing"
            assert "QA Manager" in names and "Activation Tester" in names, names
            via = {p["name"]: p["via"] for p in reps}
            assert "inbox" in via["QA Manager"] and "store" in via["QA Manager"], via["QA Manager"]
            tf = r.json()["team_from"]
            assert "Sales" in tf["inboxes"] and "QA cross-store source" in tf["sources"] and len(tf["stores"]) == 2, tf
            # super admin also gets everyone else, flagged off-team, so a wiring gap never blocks them
            off = [p for p in reps if p["on_team"] is False]
            assert off and all(p["via"] == [] for p in off) and reps.index(off[0]) > max(i for i, p in enumerate(reps) if p["on_team"]), "off-team rows must trail the team"
            reps = [p for p in reps if p["on_team"]]
            ids = {p["id"] for p in reps}
            assert "QA Manager" in {p["name"] for p in reps} and str(other_member["_id"]) in ids
            assert r.json()["store_hours"] is None or r.json()["store_hours"]["store_name"] == "TEST_NewBiz_1772880969"
            # control: the QA flow (same store as its sources) still lists the QA team
            r2 = await c.get(f"{API}/api/lead-flows/6aa5802ad1f3a6cbc1df3b65", headers=h)
            assert r2.status_code == 200 and any(p["name"] == "Activation Tester" for p in r2.json()["reps"])
            print(f"OK: {len(reps)} people on the cross-store flow; QA Manager via {via['QA Manager']}")
    finally:
        await db.lead_flows.delete_many({"qa_flow_reps": True})
        await db.lead_sources.delete_many({"qa_flow_reps": True})


def test_flow_reps_pool_spans_source_stores_and_inboxes():
    asyncio.run(_run())
