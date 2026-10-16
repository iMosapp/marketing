"""T1 (iteration 406) emergency restore of the core QA accounts after the preview users/stores/orgs collections were emptied by the
_wipe_leftovers bug in tests/test_same_org_rep_isolation.py ({"user_id": {"$in": [..., None]}} deleted every doc without a user_id).
Idempotent. Re-creates only: Forest super admin, the QA store, activation-tester, then run tests/seed_qa_manager.py.
Ids are reused from orphaned contacts so their data re-attaches. All docs carry t1_restored: True."""
import asyncio
import os
import sys
from datetime import datetime, timezone

from bson import ObjectId
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from routers.auth import hash_password  # noqa: E402
from routers.database import get_db  # noqa: E402

STORE = "69a0b7095fddcede09591668"
ORG, ORG_STORE = "69a907033b77512d1d8d8a08", "69a907033b77512d1d8d8a09"
ORG_ADMIN_ID = "6aaeb322e8d5a8e2df54328a"
ACCOUNTS = [
    ("69a0b7095fddcede09591667", "forest@imosapp.com", "Admin123!", "super_admin", "Forest Ward", None, ""),
    ("6a9b2b82cc6e7504dafc33f2", "qa-manager@invalid.imonsocial.test", "Manager123!", "store_manager", "QA Manager", STORE, ""),
    ("6a978d68b8673c29063aa8b9", "activation-tester@invalid.imonsocial.test", "NewPass123!", "user", "Activation Tester", STORE, "+15005550006"),
    ("69c75782e051d06491e6fa9f", "mjeast1985@gmail.com", "NavyBean1!", "user", "MJ East", None, ""),   # live_auth REP: role user, no store / org
]


async def main():
    db = get_db()
    now = datetime.now(timezone.utc)
    await db.stores.update_one({"_id": ObjectId(STORE)}, {"$set": {"name": "i'M On social", "is_active": True, "active": True, "t1_restored": True},
                                                          "$setOnInsert": {"created_at": now}}, upsert=True)
    for oid, email, pw, role, name, store, phone in ACCOUNTS:
        await db.users.delete_many({"email": email, "_id": {"$ne": ObjectId(oid)}})
        doc = {"email": email, "password": hash_password(pw), "role": role, "name": name, "first_name": name.split()[0], "last_name": name.split()[-1],
               "store_id": store, "store_ids": [store] if store else [], "phone": phone, "is_active": True, "active": True, "status": "active",
               "onboarding_complete": True, "needs_onboarding": False, "needs_password_change": False, "phone_verified": True, "updated_at": now, "t1_restored": True}
        await db.users.update_one({"_id": ObjectId(oid)}, {"$set": doc, "$setOnInsert": {"created_at": now}}, upsert=True)
        print("restored", email)
    # Forest's TEST_Store_Org (qa-orgadmin + Photo Intelligence test org), then the documented preview Scan rollout (PRD: test_orgs = [ORG])
    await db.organizations.update_one({"_id": ObjectId(ORG)}, {"$set": {"name": "TEST_Store_Org_1772685059", "is_active": True, "t1_restored": True},
                                                               "$setOnInsert": {"created_at": now}}, upsert=True)
    await db.stores.update_one({"_id": ObjectId(ORG_STORE)}, {"$set": {"name": "TEST_Store_1772685059", "organization_id": ORG, "is_active": True, "active": True,
                                                                       "t1_restored": True}, "$setOnInsert": {"created_at": now}}, upsert=True)
    await db.users.update_one({"_id": ObjectId(ACCOUNTS[0][0])}, {"$set": {"organization_id": ORG}})
    await db.settings.update_one({"key": "jessi_mms_vision"}, {"$setOnInsert": {"replies": "off", "intelligence": "test_orgs", "paused": False, "test_org_ids": [ORG],
                                                                                "t1_restored": True}}, upsert=True)
    await db.settings.delete_one({"key": "jessi_voice", "value.notes": "Loves a quick car joke."})  # leftover of an aborted test_live_voice run
    # qa-orgadmin keeps its original id (tests pin it); tests/seed_qa_org_admin.py then fills the rest by email
    await db.users.delete_many({"email": "qa-orgadmin@invalid.imonsocial.test", "_id": {"$ne": ObjectId(ORG_ADMIN_ID)}})
    await db.users.update_one({"_id": ObjectId(ORG_ADMIN_ID)}, {"$set": {"email": "qa-orgadmin@invalid.imonsocial.test", "role": "org_admin", "organization_id": ORG,
                                                                        "store_id": ORG_STORE, "t1_restored": True}, "$setOnInsert": {"created_at": now}}, upsert=True)
    print("restored org", ORG, "store", ORG_STORE, "scan rollout")


asyncio.run(main())
