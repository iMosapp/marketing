"""Tolerant contact matching for leads and inbound texts.
Phones are matched on their last 10 digits regardless of stored format ("(801) 634-9122" == "+18016349122")."""
import re
from datetime import datetime, timezone
from typing import Optional, Tuple
from bson import ObjectId

NOT_MERGED = {"$nin": ["merged", "deleted", "hidden"]}


def phone_digits(phone: Optional[str]) -> str:
    d = re.sub(r"\D", "", phone or "")
    return d[-10:] if len(d) >= 10 else d


def phone_regex(phone: Optional[str]) -> Optional[str]:
    """Regex that matches the same last-10-digit number in any formatting."""
    d = phone_digits(phone)
    if len(d) < 7:
        return None
    return r"\D*".join(d) + r"\D*$"


def phone_clause(phone: Optional[str], field: str = "phone") -> Optional[dict]:
    rx = phone_regex(phone)
    return {field: {"$regex": rx}} if rx else None


async def store_user_ids(db, store_id: str) -> list:
    if not store_id:
        return []
    users = await db.users.find({"store_id": store_id}, {"_id": 1}).to_list(1000)
    return [str(u["_id"]) for u in users]


def _rank(c: dict, active_rep_ids: set):
    owner = str(c.get("user_id") or "")
    created = c.get("created_at") or datetime.now(timezone.utc)
    if isinstance(created, str):
        try:
            created = datetime.fromisoformat(created.replace("Z", "+00:00"))
        except Exception:
            created = datetime.now(timezone.utc)
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    has_photo = bool(c.get("photo_url") or c.get("photo_thumbnail") or c.get("photo"))
    return (0 if owner in active_rep_ids else 1, 0 if has_photo else 1, created)


def source_owner_ids(source: dict) -> list:
    """Reps wired to a lead source (notified / called) - their books belong to the store's contact universe."""
    ids = list(source.get("workflow_user_ids") or [])
    for a in source.get("call_attempts") or []:
        ids += list(a.get("user_ids") or [])
    return [str(i) for i in ids if i]


async def find_existing_contact(db, phone: str, email: str, first: str, last: str, store_id: str,
                                extra_owner_ids: Optional[list] = None) -> Tuple[Optional[dict], str, Optional[dict]]:
    """Returns (contact, how, name_conflict). how in phone|email|name|''.
    name_conflict = a same-name contact in the store that has a DIFFERENT phone (possible duplicate, not auto-attached)."""
    rep_ids = list(dict.fromkeys(await store_user_ids(db, store_id) + [str(x) for x in (extra_owner_ids or []) if x]))
    active = await db.users.find({"_id": {"$in": [ObjectId(r) for r in rep_ids if ObjectId.is_valid(r)]},
                                  "active": {"$ne": False}, "status": {"$nin": ["deactivated", "inactive"]}}, {"_id": 1}).to_list(1000)
    active_ids = {str(u["_id"]) for u in active}
    scope = {"$or": [{"store_id": store_id}, {"user_id": {"$in": [store_id] + rep_ids}}]} if (store_id or rep_ids) else {}

    ors = []
    pc = phone_clause(phone)
    if pc:
        ors.append(pc)
    if email:
        ors.append({"email": {"$regex": f"^{re.escape(email.strip())}$", "$options": "i"}})
    if ors:
        cands = await db.contacts.find({"$and": [scope or {}, {"status": NOT_MERGED}, {"$or": ors}]}).to_list(50)
        if cands:
            cands.sort(key=lambda c: _rank(c, active_ids))
            best = cands[0]
            how = "phone" if pc and re.search(pc["phone"]["$regex"], best.get("phone") or "") else "email"
            return best, how, None

    first, last = (first or "").strip(), (last or "").strip()
    if not first or not last:
        return None, "", None
    name_q = {"$and": [scope or {}, {"status": NOT_MERGED,
              "first_name": {"$regex": f"^{re.escape(first)}$", "$options": "i"},
              "last_name": {"$regex": f"^{re.escape(last)}$", "$options": "i"}}]}
    same_name = await db.contacts.find(name_q).to_list(5)
    if len(same_name) != 1:
        return None, "", None
    c = same_name[0]
    existing_digits = phone_digits(c.get("phone"))
    lead_digits = phone_digits(phone)
    if not existing_digits or not lead_digits or existing_digits == lead_digits:
        return c, "name", None
    return None, "", c
