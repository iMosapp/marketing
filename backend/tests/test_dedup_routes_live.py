"""Live API test: the contacts.py dedup endpoints must be the ones served (not the deleted contact_merge.py).
Seeds a rep-owned + store-owned duplicate pair with a Twilio-safe number, exercises all 5 routes, cleans up."""
import asyncio, os, sys, json
import httpx
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
API = open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].splitlines()[0].strip() + "/api"
MANAGER = {"email": "qa-manager@invalid.imonsocial.test", "password": "Manager123!"}
PHONE_RAW = "(500) 555-0142"
PHONE_E164 = "+15005550142"


def ok(label, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + label + (f"  {extra}" if extra else ""))
    if not cond:
        sys.exit(1)


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(f"{API}/auth/login", json=MANAGER)
        ok("login", r.status_code == 200, r.text[:120])
        tok = r.json().get("token") or r.json().get("access_token")
        user = r.json().get("user") or {}
        uid = user.get("id") or user.get("_id")
        sid = str(user.get("store_id") or "")
        ok("manager has store", bool(sid), sid)
        H = {"Authorization": f"Bearer {tok}"}

        await db.contacts.delete_many({"phone": {"$in": [PHONE_RAW, PHONE_E164, "5005550142"]}})
        rep_doc = {"user_id": uid, "first_name": "Dedup", "last_name": "Rep", "phone": PHONE_RAW,
                   "status": "active", "tags": ["RepTag"], "created_at": "2026-01-01T00:00:00"}
        store_doc = {"user_id": sid, "first_name": "Dedup", "last_name": "Lead", "phone": PHONE_E164,
                     "email": "dedup@invalid.test", "status": "active", "tags": ["Internet Lead"], "created_at": "2026-02-01T00:00:00"}
        rep_id = str((await db.contacts.insert_one(rep_doc)).inserted_id)
        store_id_c = str((await db.contacts.insert_one(store_doc)).inserted_id)
        await db.contact_events.insert_one({"contact_id": store_id_c, "user_id": sid, "type": "note", "note": "seed"})

        # 1) duplicates — NEW logic includes store-owned leads (old router only looked at user_id)
        r = await c.get(f"{API}/contacts/{uid}/duplicates", headers=H)
        ok("GET /duplicates 200", r.status_code == 200, r.text[:200])
        groups = r.json().get("duplicates", [])
        hit = [g for g in groups if any(x.get("_id") in (rep_id, store_id_c) or x.get("id") in (rep_id, store_id_c) for x in (g.get("contacts") or g.get("records") or []))]
        ok("store-owned + rep contact grouped as one duplicate set (proves contacts.py served)", len(hit) == 1, json.dumps(groups)[:300])
        grp = hit[0].get("contacts") or hit[0].get("records")
        ok("group contains both records", len(grp) == 2)

        # 2) merge store lead into rep contact
        r = await c.post(f"{API}/contacts/{uid}/merge", headers=H, json={"primary_id": rep_id, "duplicate_id": store_id_c})
        ok("POST /merge 200", r.status_code == 200, r.text[:200])
        ok("merge migrated the store event", r.json().get("records_migrated", 0) >= 1, r.text[:200])
        prim = await db.contacts.find_one({"_id": ObjectId(rep_id)})
        dup = await db.contacts.find_one({"_id": ObjectId(store_id_c)})
        ok("primary gained email from duplicate", prim.get("email") == "dedup@invalid.test")
        ok("primary gained Internet Lead tag", "Internet Lead" in prim.get("tags", []))
        ok("duplicate marked merged", dup.get("status") == "merged" and dup.get("merged_into") == rep_id)
        ev = await db.contact_events.find_one({"contact_id": rep_id, "note": "seed"})
        ok("event re-pointed to primary", ev is not None)

        # 3) merged-history
        r = await c.get(f"{API}/contacts/{uid}/merged-history", headers=H)
        ok("GET /merged-history 200", r.status_code == 200, r.text[:200])
        ok("history lists primary", rep_id in r.text)

        # 4) repair-merge
        r = await c.post(f"{API}/contacts/{uid}/repair-merge", headers=H, json={"primary_id": rep_id})
        ok("POST /repair-merge 200", r.status_code == 200, r.text[:200])

        # 5) normalize-phones (admin) — primary still has raw formatted phone
        r = await c.post(f"{API}/contacts/admin/{uid}/normalize-phones", headers=H)
        ok("POST /normalize-phones 200", r.status_code == 200, r.text[:200])
        prim = await db.contacts.find_one({"_id": ObjectId(rep_id)})
        ok("primary phone normalized to E.164", prim.get("phone") == PHONE_E164, prim.get("phone"))

        # duplicates should now be empty for this pair
        r = await c.get(f"{API}/contacts/{uid}/duplicates", headers=H)
        still = [g for g in r.json().get("duplicates", []) if rep_id in json.dumps(g)]
        ok("pair no longer reported as duplicate", not still)

        # cleanup
        await db.contacts.delete_many({"_id": {"$in": [ObjectId(rep_id), ObjectId(store_id_c)]}})
        await db.contact_events.delete_many({"note": "seed"})
        print("\nALL PASSED")


asyncio.run(main())
