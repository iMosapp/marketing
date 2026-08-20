import asyncio, os, sys
sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
from motor.motor_asyncio import AsyncIOMotorClient

STORE_ID = "69a0b7095fddcede09591668"


async def main():
    from routers import database
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    database.db = db
    try:
        database.set_db(db)
    except Exception:
        pass

    from services import intent_detection
    from routers import auth as auth_router
    from routers import ai_reply

    store_user = await db.users.find_one({"email": "forestward@gmail.com"}, {"_id": 1, "store_id": 1})
    print("store_user:", store_user)
    su_id = str(store_user["_id"]) if store_user else None

    th = await intent_detection._get_hot_threshold(db, su_id)
    print("hot_threshold store user:", th)
    th_none = await intent_detection._get_hot_threshold(db, "000000000000000000000000")
    print("hot_threshold unknown user (expect 7):", th_none)

    ls = await auth_router._get_lockout_settings({"store_id": STORE_ID})
    print("lockout settings store:", ls)
    ls2 = await auth_router._get_lockout_settings({})
    print("lockout settings default:", ls2)

    ctx = await ai_reply._search_inventory_context(db, su_id, "Do you have any red Tacomas?")
    print("inventory ctx (tacoma):", repr(ctx))
    ctx2 = await ai_reply._search_inventory_context(db, su_id, "Thanks, talk soon!")
    print("inventory ctx (unrelated):", repr(ctx2))

    # cleanup QA bug report
    res = await db.bug_reports.delete_many({"description": {"$regex": "TEST-QA push check"}})
    print("deleted bug reports:", res.deleted_count)

asyncio.run(main())
