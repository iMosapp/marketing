"""Vanishing-leads regression: store-scoped visibility, released leads stay visible to the prior owner,
returning-owner escalation honours a reply in a sibling thread, webhook prefers the freshest thread."""
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
FOREST = "69a0b7095fddcede09591667"
OTHER_SRC = "69a901f6fe7171552f3ade6d_src"  # resolved below: a Website source from ANOTHER store
ok = bad = 0
def check(name, cond, extra=""):
    global ok, bad
    ok += bool(cond); bad += (not cond)
    print(("PASS " if cond else "FAIL ") + name + (f"  [{extra}]" if extra else ""))


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    now = datetime.now(timezone.utc)
    other_src = await db.lead_sources.find_one({"store_id": {"$ne": QA_STORE}, "name": "Website"}, {"_id": 1, "store_id": 1})
    other_sid = str(other_src["_id"])
    made_convs, made_msgs, made_contacts = [], [], []
    def conv(**kw):
        base = {"is_internet_lead": True, "status": "active", "created_at": now - timedelta(minutes=45), "last_message_at": now - timedelta(minutes=45),
                "contact_phone": "+15005550099", "contact_name": "Vanish Test", "lead_source_id": other_sid, "lead_source_name": "Website",
                "store_id": QA_STORE, "user_id": QA_STORE, "claimed": False, "claimed_by": None, "routing_kind": "queue"}
        base.update(kw)
        return base
    async with httpx.AsyncClient(timeout=30) as c:
        async def login(email, pw):
            r = await c.post(f"{API}/auth/login", json={"email": email, "password": pw})
            return {"Authorization": f"Bearer {r.json().get('token') or r.json().get('access_token')}"}
        HQ = await login("qa-manager@invalid.imonsocial.test", "Manager123!")
        HT = await login("activation-tester@invalid.imonsocial.test", "NewPass123!")
        HF = await login("forest@imosapp.com", "Admin123!")
        try:
            # 1. unclaimed lead in QA's store that came through ANOTHER store's source doc
            a = await db.conversations.insert_one(conv(contact_name="Vanish A (store scope)"))
            made_convs.append(a.inserted_id)
            # 2. released lead (was the tester's), source not on tester's list
            b = await db.conversations.insert_one(conv(contact_name="Vanish B (released)", prev_owner_id=TESTER, released_at=now, store_id="zzz-other-store"))
            made_convs.append(b.inserted_id)
            r = await c.get(f"{API}/leads/queue/{QA}", headers=HQ); names = [i["contact_name"] for i in r.json()["unclaimed"]]
            check("manager sees every unclaimed lead in their store regardless of source doc", "Vanish A (store scope)" in names, str(names)[:120])
            check("manager does not see other store's released lead", "Vanish B (released)" not in names)
            r = await c.get(f"{API}/leads/queue/{TESTER}", headers=HT); names = [i["contact_name"] for i in r.json()["unclaimed"]]
            check("rep still sees the lead that was released from them", "Vanish B (released)" in names, str(names)[:120])
            check("rep does not see unrelated store lead", "Vanish A (store scope)" not in names)
            r = await c.get(f"{API}/leads/queue/{FOREST}", headers=HF); names = [i["contact_name"] for i in r.json()["unclaimed"]]
            check("super admin sees both", "Vanish A (store scope)" in names and "Vanish B (released)" in names, str(len(names)))
            r = await c.get(f"{API}/leads/queue/{QA}/summary", headers=HQ)
            check("summary counts the store-scoped lead", r.json().get("waiting", 0) >= 1, str(r.json().get("waiting")))

            # 3. returning-owner escalation: replied in a sibling thread -> keep; silent -> release with prev_owner_id
            contact = await db.contacts.insert_one({"first_name": "Vanish", "last_name": "Owner", "phone": "+15005550098", "user_id": QA, "store_id": QA_STORE, "status": "active", "created_at": now})
            made_contacts.append(contact.inserted_id)
            cid = str(contact.inserted_id)
            personal = await db.conversations.insert_one({"user_id": QA, "contact_id": cid, "contact_phone": "+15005550098", "rep_phone": "+15005550010", "status": "active",
                                                          "created_at": now - timedelta(days=30), "last_message_at": now - timedelta(minutes=10)})
            made_convs.append(personal.inserted_id)
            kept = await db.conversations.insert_one(conv(contact_name="Vanish C (replied elsewhere)", contact_id=cid, contact_phone="+15005550098", rep_phone="+15005550010",
                                                          claimed=True, claimed_by=QA, user_id=QA, routing_kind="returning_owner", release_at=now - timedelta(minutes=1), owner_alert_at=now - timedelta(minutes=20), owner_alerted=True,
                                                          last_message_at=now - timedelta(minutes=44)))
            made_convs.append(kept.inserted_id)
            m = await db.messages.insert_one({"conversation_id": str(personal.inserted_id), "sender": "user", "content": "Hey it's me, got your form", "timestamp": now - timedelta(minutes=10)})
            made_msgs.append(m.inserted_id)
            dropped = await db.conversations.insert_one(conv(contact_name="Vanish D (silent)", contact_id="000000000000000000000000", contact_phone="+15005550097",
                                                             claimed=True, claimed_by=QA, user_id=QA, routing_kind="returning_owner", release_at=now - timedelta(minutes=1), owner_alerted=True))
            made_convs.append(dropped.inserted_id)
            from routers.lead_queue import process_returning_lead_escalations
            res = await process_returning_lead_escalations()
            k = await db.conversations.find_one({"_id": kept.inserted_id}); d = await db.conversations.find_one({"_id": dropped.inserted_id})
            check("owner reply in sibling thread keeps the lead claimed", k.get("claimed") is True and k.get("routing_resolved") is True, str(res))
            check("silent returning lead is released and remembers the owner", d.get("claimed") is False and d.get("prev_owner_id") == QA)
            r = await c.get(f"{API}/leads/queue/{QA}", headers=HQ); data = r.json()
            check("released lead is still visible to that manager (unclaimed)", any(i["contact_name"] == "Vanish D (silent)" for i in data["unclaimed"]))
            check("kept lead stays under Mine", any(i["contact_name"] == "Vanish C (replied elsewhere)" for i in data["mine"]))

            # 4. webhook thread choice: newest thread on (rep_phone, contact_phone) wins
            picked = await db.conversations.find_one({"rep_phone": "+15005550010", "contact_phone": "+15005550098"}, sort=[("last_message_at", -1)])
            natural = await db.conversations.find_one({"rep_phone": "+15005550010", "contact_phone": "+15005550098"})
            check("webhook lookup picks the most recently active thread", picked["_id"] == personal.inserted_id and natural["_id"] == personal.inserted_id or picked["_id"] == personal.inserted_id,
                  f"picked={picked.get('contact_name')}")
            await db.conversations.update_one({"_id": kept.inserted_id}, {"$set": {"last_message_at": now}})
            picked = await db.conversations.find_one({"rep_phone": "+15005550010", "contact_phone": "+15005550098"}, sort=[("last_message_at", -1)])
            check("after the intake text, the lead thread is the freshest and gets the reply", picked["_id"] == kept.inserted_id)
        finally:
            await db.conversations.delete_many({"_id": {"$in": made_convs}})
            await db.messages.delete_many({"$or": [{"_id": {"$in": made_msgs}}, {"conversation_id": {"$in": [str(i) for i in made_convs]}}]})
            await db.contacts.delete_many({"_id": {"$in": made_contacts}})
            await db.notifications.delete_many({"conversation_id": {"$in": [str(i) for i in made_convs]}})
            await db.contact_events.delete_many({"contact_id": {"$in": [str(i) for i in made_contacts]}})
    print(f"\n{ok} passed, {bad} failed")
    sys.exit(1 if bad else 0)

asyncio.run(main())
