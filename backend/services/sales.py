"""Single source of truth for recording a sale on a contact (date_sold / sold_count / purchase_history).

Why: the Sold flows call several endpoints (date-sold, congrats card w/ Sold tag, tags PATCH). Each used to
infer "already has date_sold => repeat buyer" and $inc sold_count, so ONE sale produced sold_count=2 and a
bogus purchase_history entry. Everything now funnels through record_sale(), which is idempotent per transaction.
"""
from datetime import datetime, timedelta
import logging

from bson import ObjectId

logger = logging.getLogger(__name__)

CORRECTION_WINDOW = timedelta(days=7)  # re-running the flow / fixing the date within a week = same sale


def _as_dt(v):
    if isinstance(v, datetime):
        return v.replace(tzinfo=None)
    if isinstance(v, str) and v:
        try:
            return datetime.fromisoformat(v.replace("Z", "+00:00")).replace(tzinfo=None)
        except Exception:
            return None
    return None


async def record_sale(db, contact_id: str, sale_date: datetime | None = None, only_if_unsold: bool = False) -> dict:
    """Record a sale. Returns {"kind": first|same|repeat|skipped|missing}.
    - first:  no prior sale -> date_sold, sold_count=1
    - same:   prior sale on the same day, or recorded < 7 days ago (flow re-run / date correction) -> update date only
    - repeat: a genuinely earlier sale exists -> archive it to purchase_history, bump sold_count
    only_if_unsold=True (tag paths): never treat an existing sale as a repeat, just ensure the first sale exists."""
    now = datetime.utcnow()
    sale_date = _as_dt(sale_date) or now
    c = await db.contacts.find_one({"_id": ObjectId(contact_id)},
                                   {"date_sold": 1, "sold_count": 1, "vehicle": 1, "prev_vehicle": 1, "sold_recorded_at": 1})
    if not c:
        return {"kind": "missing"}
    prev = _as_dt(c.get("date_sold"))
    count = int(c.get("sold_count") or 0)
    if not prev:
        await db.contacts.update_one({"_id": c["_id"]}, {
            "$set": {"date_sold": sale_date, "sold_count": max(count, 1), "sold_recorded_at": now, "updated_at": now},
            "$unset": {"prev_vehicle": ""},
        })
        return {"kind": "first", "date_sold": sale_date}
    if only_if_unsold:
        if count < 1:
            await db.contacts.update_one({"_id": c["_id"]}, {"$set": {"sold_count": 1}})
        return {"kind": "skipped", "date_sold": prev}
    recorded_at = _as_dt(c.get("sold_recorded_at"))
    same_transaction = prev.date() == sale_date.date() or (recorded_at is not None and now - recorded_at < CORRECTION_WINDOW)
    if same_transaction:
        await db.contacts.update_one({"_id": c["_id"]}, {
            "$set": {"date_sold": sale_date, "sold_count": max(count, 1), "sold_recorded_at": recorded_at or now, "updated_at": now},
            "$unset": {"prev_vehicle": ""},
        })
        return {"kind": "same", "date_sold": sale_date}
    prev_entry = {"date": prev.isoformat(), "vehicle": c.get("prev_vehicle") or c.get("vehicle", ""),
                  "notes": "Previous purchase", "is_repeat": True}
    await db.contacts.update_one({"_id": c["_id"]}, {
        "$push": {"purchase_history": prev_entry},
        "$set": {"date_sold": sale_date, "sold_count": max(count, 1) + 1, "sold_recorded_at": now, "updated_at": now},
        "$unset": {"prev_vehicle": ""},
    })
    logger.info(f"[Sales] Repeat buyer {contact_id}: previous {prev.date()} archived, sold_count={max(count, 1) + 1}")
    return {"kind": "repeat", "date_sold": sale_date, "sold_count": max(count, 1) + 1}


async def repair_false_repeats(db) -> dict:
    """One-time cleanup for contacts double-counted by the old inference.
    A purchase_history entry whose date is the same day as the contact's current date_sold was created by the
    same transaction, not an earlier purchase. sold_count becomes 1 + remaining distinct earlier purchases."""
    fixed = 0
    async for c in db.contacts.find({"sold_count": {"$gt": 1}}, {"date_sold": 1, "purchase_history": 1, "sold_count": 1}):
        cur = _as_dt(c.get("date_sold"))
        hist = c.get("purchase_history") or []
        keep, seen = [], set()
        for h in hist:
            d = _as_dt(h.get("date"))
            if cur and d and d.date() == cur.date() and h.get("is_repeat"):
                continue  # bogus: same transaction
            key = d.date().isoformat() if d else repr(h)
            if key in seen:
                continue  # duplicate archive of the same earlier sale
            seen.add(key)
            keep.append(h)
        new_count = 1 + len([h for h in keep if h.get("is_repeat") or h.get("date")])
        if new_count != c.get("sold_count") or len(keep) != len(hist):
            await db.contacts.update_one({"_id": c["_id"]}, {"$set": {"sold_count": new_count, "purchase_history": keep}})
            fixed += 1
    return {"fixed": fixed}
