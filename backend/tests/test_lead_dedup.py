"""Lead dedup: formatted phones, unique-name fallback, same-name conflict flag, store isolation, duplicates screen + merge.
Runs process_inbound_lead with push/SMS/ladder stubbed against a throwaway lead source; cleans up everything.
run: cd /app/backend && python tests/test_lead_dedup.py
"""
import asyncio, os, sys
from datetime import datetime, timezone
sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
from bson import ObjectId

STORE_ID = "69a0b7095fddcede09591668"   # forest's store (preview)
FOREST = "69a0b7095fddcede09591667"
OTHER_STORE = "69a901f6fe7171552f3ade6d"
R = []


def check(name, ok, info=""):
    R.append((name, ok)); print(("PASS  " if ok else "FAIL  ") + name + (f"  {info}" if info and not ok else ""))


async def main():
    from routers.database import get_db
    db = get_db()
    import routers.lead_intake as li
    import routers.push_notifications as pn
    import services.twilio_service as tw
    async def _noop(*a, **k): return {"success": True, "mock": True}
    pn.send_push_to_user = _noop; tw.send_sms = _noop
    async def _no_wf(*a, **k): return None
    li._fire_intake_workflow = _no_wf
    from routers.contacts import find_duplicate_contacts, merge_contacts
    now = datetime.now(timezone.utc)
    src = await db.lead_sources.insert_one({"name": "QA Dedup Source", "store_id": STORE_ID, "is_active": True, "assignment_method": "jump_ball",
                                             "workflow_user_ids": [FOREST], "contact_mode": "text_only", "va_enabled": False, "created_at": now})
    source = await db.lead_sources.find_one({"_id": src.inserted_id})
    made = {"contacts": [], "conversations": [], "inbound_leads": []}

    async def lead(first, last, phone, email="", **extra):
        n = {"first_name": first, "last_name": last, "full_name": f"{first} {last}", "phone": phone, "email": email,
             "source_name": "QA Dedup Source", "is_test": True, "attribution": {"kind": "website_form", "source_label": "the QA page"}, **extra}
        r = await li.process_inbound_lead(n, source, db)
        cid = r.get("contact_id"); made["conversations"].append(r.get("conversation_id")); made["inbound_leads"].append(r.get("lead_id"))
        if cid and ObjectId(cid) not in made["contacts"]:
            made["contacts"].append(ObjectId(cid))
        return r

    try:
        # 1. formatted phone on an old imported contact
        c1 = await db.contacts.insert_one({"first_name": "Dedup", "last_name": "Formatted", "phone": "(500) 555-0177", "user_id": FOREST,
                                           "photo_url": "https://example.com/p.jpg", "status": "active", "created_at": now})
        made["contacts"].append(c1.inserted_id)
        r = await lead("Dedup", "Formatted", "5005550177", "nomatch@example.com")
        check("formatted phone matches, no duplicate", r.get("contact_id") == str(c1.inserted_id) and r.get("is_new_contact") is False, r)

        # 2. richest record wins when two match (store-owned lead stub vs rep-owned with photo)
        s2 = await db.contacts.insert_one({"first_name": "Dedup", "last_name": "Rich", "phone": "+15005550178", "user_id": STORE_ID, "status": "active", "created_at": now})
        c2 = await db.contacts.insert_one({"first_name": "Dedup", "last_name": "Rich", "phone": "500-555-0178", "user_id": FOREST,
                                           "photo_thumbnail": "x.jpg", "status": "active", "created_at": now})
        made["contacts"] += [s2.inserted_id, c2.inserted_id]
        r = await lead("Dedup", "Rich", "+1 (500) 555-0178")
        check("rep-owned contact with photo preferred", r.get("contact_id") == str(c2.inserted_id), r.get("contact_id"))

        # 3. unique name, phone missing on the existing contact -> attach + fill phone
        c3 = await db.contacts.insert_one({"first_name": "Dedup", "last_name": "Nameonly", "phone": "", "email": "", "user_id": FOREST, "status": "active", "created_at": now})
        made["contacts"].append(c3.inserted_id)
        r = await lead("Dedup", "Nameonly", "5005550179", "dedup.nameonly@example.com")
        c3d = await db.contacts.find_one({"_id": c3.inserted_id})
        check("unique name attaches + fills phone/email", r.get("contact_id") == str(c3.inserted_id) and c3d.get("phone") == "+15005550179"
              and c3d.get("email") == "dedup.nameonly@example.com", (r.get("contact_id"), c3d.get("phone")))

        # 4. same name, DIFFERENT phone -> new contact, both flagged, shows in duplicates, merge works
        c4 = await db.contacts.insert_one({"first_name": "Dedup", "last_name": "Conflict", "phone": "+15005550180", "user_id": FOREST, "status": "active", "created_at": now})
        made["contacts"].append(c4.inserted_id)
        r = await lead("Dedup", "Conflict", "5005550181")
        newc = await db.contacts.find_one({"_id": ObjectId(r["contact_id"])})
        c4d = await db.contacts.find_one({"_id": c4.inserted_id})
        check("same name different phone = new contact flagged", r["contact_id"] != str(c4.inserted_id)
              and newc.get("possible_duplicate_of") == str(c4.inserted_id) and "Possible Duplicate" in (newc.get("tags") or [])
              and "Possible Duplicate" in (c4d.get("tags") or []), (r["contact_id"], newc.get("tags")))
        dups = await find_duplicate_contacts(FOREST)
        grp = [g for g in dups["duplicates"] if g.get("reason") == "name" and any(x["id"] == r["contact_id"] for x in g["contacts"])]
        check("name-conflict pair listed on Duplicates screen", len(grp) == 1 and len(grp[0]["contacts"]) == 2, len(grp))
        m = await merge_contacts(FOREST, {"primary_id": str(c4.inserted_id), "duplicate_id": r["contact_id"]})
        c4d = await db.contacts.find_one({"_id": c4.inserted_id}); newc = await db.contacts.find_one({"_id": ObjectId(r["contact_id"])})
        conv = await db.conversations.find_one({"_id": ObjectId(r["conversation_id"])})
        check("merge moves thread + clears flags", m.get("success") and newc.get("status") == "merged" and conv.get("contact_id") == str(c4.inserted_id)
              and "Possible Duplicate" not in (c4d.get("tags") or []), (newc.get("status"), conv.get("contact_id")))

        # 5. store-owned lead contact merges into the rep's contact via Duplicates (phone group includes store-owned)
        s5 = await db.contacts.insert_one({"first_name": "Dedup", "last_name": "Storelead", "phone": "+15005550182", "user_id": STORE_ID, "status": "active", "created_at": now})
        c5 = await db.contacts.insert_one({"first_name": "Dedup", "last_name": "Storelead", "phone": "(500) 555-0182", "user_id": FOREST, "status": "active", "created_at": now})
        made["contacts"] += [s5.inserted_id, c5.inserted_id]
        dups = await find_duplicate_contacts(FOREST)
        grp = [g for g in dups["duplicates"] if g.get("reason") == "phone" and any(x["id"] == str(s5.inserted_id) for x in g["contacts"])]
        check("store-owned lead shows in rep's Duplicates", len(grp) == 1 and any(x.get("store_owned") for x in grp[0]["contacts"]), len(grp))
        m = await merge_contacts(FOREST, {"primary_id": str(c5.inserted_id), "duplicate_id": str(s5.inserted_id)})
        check("merge accepts store-owned duplicate", m.get("success") is True, m)

        # 6. cross-store isolation: same phone in ANOTHER store must not be attached
        c6 = await db.contacts.insert_one({"first_name": "Dedup", "last_name": "Otherstore", "phone": "+15005550183", "user_id": "000000000000000000000001",
                                           "store_id": OTHER_STORE, "status": "active", "created_at": now})
        made["contacts"].append(c6.inserted_id)
        r = await lead("Dedup", "Otherstore", "5005550183")
        check("other store's contact is not attached", r.get("contact_id") != str(c6.inserted_id) and r.get("is_new_contact") is True, r.get("contact_id"))

        # 7. merged contacts are never matched again
        r = await lead("Dedup", "Storelead", "+15005550182")
        check("merged record skipped, live one matched", r.get("contact_id") == str(c5.inserted_id), r.get("contact_id"))
    finally:
        cids = [str(x) for x in made["contacts"]]
        await db.contacts.delete_many({"_id": {"$in": made["contacts"]}})
        await db.conversations.delete_many({"$or": [{"contact_id": {"$in": cids}}, {"_id": {"$in": [ObjectId(x) for x in made["conversations"] if x and ObjectId.is_valid(x)]}}]})
        await db.inbound_leads.delete_many({"$or": [{"contact_id": {"$in": cids}}, {"source_id": str(src.inserted_id)}]})
        for col in ("messages", "contact_events", "notifications", "tasks", "lead_call_jobs", "lead_deferred_actions", "ai_reply_queue"):
            await db[col].delete_many({"contact_id": {"$in": cids}})
        await db.lead_release_slots.delete_many({})
        await db.lead_sources.delete_one({"_id": src.inserted_id})
        print(f"\n{sum(1 for _, ok in R if ok)}/{len(R)} passed")

asyncio.run(main())
