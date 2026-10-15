"""Startup index handling (services/index_setup.py): one conflicting spec is reported with its exact name and options, never repaired, and never stops
the other specs. Runs against a throwaway preview collection that is dropped at the end; link_pages is only read."""
import asyncio
import secrets

from services import index_setup

loop = asyncio.get_event_loop_policy().get_event_loop()  # shared with the other launch suites: get_db() caches one Motor client per process
if loop.is_closed():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)


def run(coro):
    return loop.run_until_complete(coro)


def adb():
    from routers.database import get_db
    return get_db()


def test_conflict_is_reported_and_others_still_created():
    db = adb()
    coll = db[f"qa_index_probe_{secrets.token_hex(3)}"]
    try:
        run(coll.create_index("user_id", unique=True))
        results = run(asyncio.gather(
            index_setup.ensure(coll, "user_id", unique=True, sparse=True),
            index_setup.ensure(coll, [("org_id", 1), ("at", -1)]),
            index_setup.ensure(coll, "email", unique=True, sparse=True),
            return_exceptions=True,
        ))
        ok, mismatches, failed = index_setup.summarize(results)
        assert (ok, len(mismatches), len(failed)) == (2, 1, 0)
        assert f"{coll.name}.user_id_1" in mismatches[0] and "existing index kept" in mismatches[0] and "'sparse': True" in mismatches[0]
        info = run(coll.index_information())
        assert "org_id_1_at_-1" in info and "email_1" in info
        assert info["user_id_1"].get("unique") and not info["user_id_1"].get("sparse")  # existing index untouched
    finally:
        run(coll.drop())


def test_other_errors_name_the_collection():
    db = adb()
    coll = db[f"qa_index_probe_{secrets.token_hex(3)}"]
    try:
        results = run(asyncio.gather(index_setup.ensure(coll, "x", expireAfterSeconds="bad"), return_exceptions=True))
        ok, mismatches, failed = index_setup.summarize(results)
        assert ok == 0 and not mismatches and len(failed) == 1 and coll.name in str(failed[0])
    finally:
        run(coll.drop())


def test_link_pages_always_have_user_id():
    """Why unique non-sparse (preview) and unique+sparse (production) behave the same: every link page is written with a user_id."""
    db = adb()
    assert run(db.link_pages.count_documents({"$or": [{"user_id": {"$exists": False}}, {"user_id": None}]})) == 0
