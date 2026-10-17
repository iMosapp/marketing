"""Guard rails for test cleanup (after the Oct 16 2026 preview incident: {"user_id": {"$in": [..., None]}} in a loop over every collection
also matched every document WITHOUT a user_id, so users, stores, organizations and settings were deleted).

- require_preview_db(): refuses unless MONGO_URL points at a local MongoDB (preview pods only; production uses a managed cluster).
- valid_ids(): only 24-hex ids survive, never None / "" / junk.
- wipe_by_owner(): deletes rows owned by the given test users / contacts in data collections only; account and configuration
  collections (PROTECTED) are never touched here: delete those by exact _id or by the test's own tag."""
import os
import re
from urllib.parse import urlsplit

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
PRODUCTION_HOSTS = ("imonsocial.com",)
PROTECTED = {"users", "stores", "organizations", "settings", "migrations", "job_leases", "partners", "shared_inboxes", "lead_sources",
             "twilio_numbers", "subscriptions", "ai_clone_prompts", "agents", "ai_va_profiles", "voice_ai_global", "app_settings"}
_HEX24 = re.compile(r"^[0-9a-f]{24}$")


class UnsafeCleanup(RuntimeError):
    pass


def _host(url: str) -> str:
    return (urlsplit(url).hostname or "").lower()


def require_preview_db() -> None:
    mongo = os.environ.get("MONGO_URL") or ""
    hosts = {h.split(":")[0].strip("[]").lower() for h in re.sub(r"^mongodb(\+srv)?://([^@/]*@)?", "", mongo).split("/")[0].split(",") if h}
    if not mongo or mongo.startswith("mongodb+srv://") or not hosts or not hosts <= LOCAL_HOSTS:
        raise UnsafeCleanup("Refusing: tests and cleanups only run against the local preview MongoDB (MONGO_URL is not localhost)")
    api = _host(os.environ.get("REACT_APP_BACKEND_URL") or "")
    if any(api == h or api.endswith("." + h) for h in PRODUCTION_HOSTS):
        raise UnsafeCleanup(f"Refusing: REACT_APP_BACKEND_URL points at production ({api})")


def valid_ids(values) -> list:
    return [str(v) for v in values or [] if v is not None and _HEX24.match(str(v))]


async def wipe_by_owner(db, user_ids, contact_ids=()) -> dict:
    """Delete the test users' / contacts' rows from every data collection. Empty id lists delete nothing."""
    require_preview_db()
    uids, cids = valid_ids(user_ids), valid_ids(contact_ids)
    removed = {}
    if not uids and not cids:
        return removed
    for coll in await db.list_collection_names():
        if coll.startswith("system.") or coll in PROTECTED:
            continue
        n = 0
        if uids:
            n += (await db[coll].delete_many({"user_id": {"$in": uids}})).deleted_count
        if cids:
            n += (await db[coll].delete_many({"contact_id": {"$in": cids}})).deleted_count
        if n:
            removed[coll] = n
    return removed
