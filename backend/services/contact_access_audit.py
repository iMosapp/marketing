"""Audit trail for super-admin access to contacts owned outside the admin's own organization.

The identity middleware binds the proven caller for each /api request; `note()` is called wherever a single contact is opened through the
shared ownership checks (contact_scope.owned_contact, contact detail, Jessi focus). One row per caller + contact + action per request.
Rows hold ids, roles, the action and why access was allowed: never names, phones, notes or transcripts."""
import logging
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId

logger = logging.getLogger(__name__)

COLL = "contact_access_audit"
_CTX: ContextVar[Optional[dict]] = ContextVar("contact_access_ctx", default=None)


def bind(caller_id: str, method: str, path: str) -> None:
    _CTX.set({"caller": caller_id, "method": method, "path": path[:200], "seen": set()})


async def _caller(db, ctx: dict) -> dict:
    if "role" not in ctx:
        u = await db.users.find_one({"_id": ObjectId(ctx["caller"])}, {"role": 1, "organization_id": 1}) if ObjectId.is_valid(ctx["caller"]) else None
        ctx["role"], ctx["org"] = (u or {}).get("role"), str((u or {}).get("organization_id") or "")
    return ctx


async def _owner_org(db, owner_id: str, contact: dict) -> str:
    if ObjectId.is_valid(owner_id):
        u = await db.users.find_one({"_id": ObjectId(owner_id)}, {"organization_id": 1})
        if u:
            return str(u.get("organization_id") or "")
        s = await db.stores.find_one({"_id": ObjectId(owner_id)}, {"organization_id": 1})   # store-owned lead
        if s:
            return str(s.get("organization_id") or "")
    return str(contact.get("organization_id") or "")


async def note(db, contact_id: str, action: Optional[str] = None, contact: Optional[dict] = None) -> None:
    """Record a super admin opening a contact that belongs to another organization (or to no organization). Never raises."""
    ctx = _CTX.get()
    if not ctx or not ctx.get("caller"):
        return
    try:
        await _caller(db, ctx)
        if ctx["role"] != "super_admin":
            return
        cid = str(contact_id)
        act = action or f"{ctx['method']} {ctx['path']}"
        key = (cid, act)
        if key in ctx["seen"]:
            return
        ctx["seen"].add(key)
        if contact is None or "user_id" not in contact:
            contact = await db.contacts.find_one({"_id": ObjectId(cid)}, {"user_id": 1, "organization_id": 1}) if ObjectId.is_valid(cid) else None
        if not contact:
            return
        owner = str(contact.get("user_id") or "")
        owner_org = await _owner_org(db, owner, contact)
        if owner == ctx["caller"] or (owner_org and owner_org == ctx["org"]):
            return
        await db[COLL].insert_one({"at": datetime.now(timezone.utc), "actor_id": ctx["caller"], "actor_role": "super_admin", "actor_org_id": ctx["org"] or None,
                                   "contact_id": cid, "owner_id": owner or None, "owner_org_id": owner_org or None, "action": act,
                                   "reason": "super_admin_platform_access"})
    except Exception as e:
        logger.warning(f"[ContactAudit] not recorded: {type(e).__name__}")


async def recent(db, limit: int = 200, actor_id: Optional[str] = None, contact_id: Optional[str] = None) -> list:
    q = {k: v for k, v in (("actor_id", actor_id), ("contact_id", contact_id)) if v}
    rows = await db[COLL].find(q).sort("at", -1).limit(min(max(limit, 1), 1000)).to_list(1000)
    return [{**{k: v for k, v in r.items() if k != "_id"}, "id": str(r["_id"]), "at": r["at"].isoformat()} for r in rows]
