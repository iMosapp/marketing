"""Sales = purchase records. Single source of truth for everything "sold" on a contact.

Model
- contact.purchase_history[]  : one record per purchase {id, title, category, date "YYYY-MM-DD" | None, notes, created_at, source}
- contact.date_sold / vehicle : DERIVED from the most recent dated purchase (kept for automations, filters, hero chip)
- contact.sold_count          : DERIVED = number of purchase records
Sold Units, the 12-month chart and the home tiles count purchase records, so a customer who bought in July and
September shows up in both months. Dates are calendar dates (no time, no time zone) end to end.
"""
from datetime import datetime, timedelta, timezone
import logging
import uuid

from bson import ObjectId

logger = logging.getLogger(__name__)

CORRECTION_WINDOW_DAYS = 7  # same title within a week = the same sale being corrected, not a second purchase
STATUS_ALIVE = {"$nin": ["hidden", "merged", "deleted"]}


def ymd(v) -> str | None:
    """Any date-ish value -> 'YYYY-MM-DD' (calendar date, the date portion as sent). None if unusable."""
    if v is None or v == "":
        return None
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d")
    s = str(v).strip()
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        try:
            datetime.strptime(s[:10], "%Y-%m-%d")
            return s[:10]
        except ValueError:
            return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except Exception:
        return None


def to_dt(day: str | None) -> datetime | None:
    return datetime.strptime(day, "%Y-%m-%d") if day else None


def _norm_title(t) -> str:
    return " ".join(str(t or "").split()).lower()


def normalize_entry(e: dict) -> dict:
    """Both historical shapes -> one shape. Old 'repeat' archives were {date, vehicle, notes, is_repeat} with no id/title."""
    return {
        "id": e.get("id") or str(uuid.uuid4()),
        "title": (e.get("title") or e.get("vehicle") or "").strip(),
        "category": e.get("category") or "vehicle",
        "date": ymd(e.get("date")),
        "notes": ("" if (e.get("notes") or "") == "Previous purchase" else (e.get("notes") or "")).strip(),
        "created_at": e.get("created_at") or datetime.now(timezone.utc).isoformat(),
        **({"source": e["source"]} if e.get("source") else {}),
    }


def dedupe(entries: list) -> list:
    """Same calendar date + same title (or one of them untitled) is one purchase. Keeps the titled / oldest record."""
    out: list = []
    for e in sorted(entries, key=lambda x: (x.get("created_at") or "")):
        hit = next((o for o in out if o["date"] == e["date"] and e["date"] and (_norm_title(o["title"]) == _norm_title(e["title"]) or not o["title"] or not e["title"])), None)
        if hit:
            if not hit["title"] and e["title"]:
                hit["title"] = e["title"]
            if not hit["notes"] and e["notes"]:
                hit["notes"] = e["notes"]
            continue
        out.append(e)
    return out


def sort_entries(entries: list) -> list:
    return sorted(entries, key=lambda e: (e.get("date") or "", e.get("created_at") or ""), reverse=True)


def derived(entries: list) -> dict:
    dated = [e for e in entries if e.get("date")]
    latest = sort_entries(dated)[0] if dated else (sort_entries(entries)[0] if entries else None)
    return {"date_sold": to_dt(latest["date"]) if latest and latest.get("date") else None,
            "vehicle": (latest or {}).get("title") or "",
            "sold_count": len(entries)}


async def load_entries(db, contact_id) -> tuple[dict | None, list]:
    c = await db.contacts.find_one({"_id": ObjectId(str(contact_id))}, {"purchase_history": 1, "date_sold": 1, "vehicle": 1, "prev_vehicle": 1, "personal_details": 1, "user_id": 1})
    if not c:
        return None, []
    entries = [normalize_entry(e) for e in (c.get("purchase_history") or []) if isinstance(e, dict)]
    return c, entries


async def save_entries(db, contact: dict, entries: list, keep_vehicle_text: bool = False) -> dict:
    """Write the records and re-derive date_sold / vehicle / sold_count. Never deletes anything the caller kept."""
    entries = sort_entries(dedupe(entries))
    d = derived(entries)
    sets = {"purchase_history": entries, "sold_count": d["sold_count"], "date_sold": d["date_sold"], "updated_at": datetime.now(timezone.utc)}
    if not (keep_vehicle_text and contact.get("vehicle")):
        sets["vehicle"] = d["vehicle"] or contact.get("vehicle") or ""
    latest = entries[0] if entries else None
    if latest and latest.get("category", "vehicle") == "vehicle" and latest.get("title") and not keep_vehicle_text:
        sets["personal_details.vehicle_purchased"] = latest["title"]
    await db.contacts.update_one({"_id": contact["_id"]}, {"$set": sets, "$unset": {"prev_vehicle": ""}})
    return {**d, "entries": entries}


def _match(entries: list, day: str | None, title: str | None) -> dict | None:
    """The record a sale/correction refers to: same date (title-compatible), else same title within the correction window."""
    nt = _norm_title(title)
    if day:
        same_day = [e for e in entries if e.get("date") == day and (not nt or not e["title"] or _norm_title(e["title"]) == nt)]
        if same_day:
            return next((e for e in same_day if _norm_title(e["title"]) == nt), None) or next((e for e in same_day if not e["title"]), None) or same_day[0]
    if nt and day:
        d0 = to_dt(day)
        for e in sort_entries(entries):
            if _norm_title(e["title"]) == nt and e.get("date") and abs((to_dt(e["date"]) - d0).days) <= CORRECTION_WINDOW_DAYS:
                return e
    return None


async def record_sale(db, contact_id: str, sale_date=None, title: str | None = None, category: str = "vehicle", notes: str = "",
                      only_if_unsold: bool = False, source: str = "wizard") -> dict:
    """Record (or correct) a sale. Returns {"kind": first|repeat|same|skipped|missing, ...derived}.
    - A new calendar date (and no same-titled sale within 7 days) = a NEW purchase record; earlier purchases stay.
    - Same date, or same title within 7 days = the same sale: update it (wizard re-runs, backdating, adding the vehicle after the date).
    - only_if_unsold (tag paths): just make sure at least one purchase exists; never touch existing records."""
    c, entries = await load_entries(db, contact_id)
    if not c:
        return {"kind": "missing"}
    day = ymd(sale_date) or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if only_if_unsold:
        if entries:
            return {"kind": "skipped", **derived(entries)}
        entries.append(normalize_entry({"title": title or c.get("vehicle") or "", "category": category, "date": day, "notes": notes, "source": source}))
        return {"kind": "first", **(await save_entries(db, c, entries))}
    hit = _match(entries, day, title)
    if hit:
        hit["date"] = day
        if title:
            hit["title"] = title.strip()
        if notes:
            hit["notes"] = notes.strip()
        if category and title:
            hit["category"] = category
        return {"kind": "same", **(await save_entries(db, c, entries))}
    entries.append(normalize_entry({"title": title or "", "category": category, "date": day, "notes": notes, "source": source}))
    out = await save_entries(db, c, entries)
    kind = "first" if len(entries) == 1 else "repeat"
    if kind == "repeat":
        logger.info(f"[Sales] Repeat buyer {contact_id}: {len(entries)} purchases, latest {day}")
    return {"kind": kind, **out}


async def add_purchase(db, contact_id: str, title: str, category: str = "other", day=None, notes: str = "", source: str = "manual") -> dict | None:
    """Purchase History '+ Add' / edit paths. A dated purchase merges with the matching sale (see record_sale); undated ones are just appended."""
    c, entries = await load_entries(db, contact_id)
    if not c:
        return None
    day = ymd(day)
    if day:
        hit = _match(entries, day, title)
        if hit:
            hit.update({"title": title.strip(), "category": category or hit["category"], "notes": (notes or "").strip()})
            await save_entries(db, c, entries)
            return hit
    e = normalize_entry({"title": title, "category": category, "date": day, "notes": notes, "source": source})
    entries.append(e)
    await save_entries(db, c, entries)
    return e


async def update_purchase(db, contact_id: str, purchase_id: str, fields: dict) -> bool:
    c, entries = await load_entries(db, contact_id)
    hit = next((e for e in entries if e["id"] == purchase_id), None) if c else None
    if not hit:
        return False
    if "title" in fields:
        hit["title"] = (fields["title"] or "").strip()
    if "category" in fields and fields["category"]:
        hit["category"] = fields["category"]
    if "date" in fields:
        hit["date"] = ymd(fields["date"])
    if "notes" in fields:
        hit["notes"] = (fields["notes"] or "").strip()
    await save_entries(db, c, entries)
    return True


async def delete_purchase(db, contact_id: str, purchase_id: str) -> bool:
    c, entries = await load_entries(db, contact_id)
    if not c:
        return False
    keep = [e for e in entries if e["id"] != purchase_id]
    if len(keep) == len(entries):
        return False
    await save_entries(db, c, keep)
    return True


async def sync_from_contact_fields(db, contact_id: str, date_sold, vehicle: str | None):
    """The contact edit form changed Date Sold (and/or vehicle): that edits the most recent purchase, it never forks a copy."""
    c, entries = await load_entries(db, contact_id)
    if not c:
        return
    day = ymd(date_sold)
    if not day and not entries:
        return
    if not entries:
        entries.append(normalize_entry({"title": vehicle or "", "category": "vehicle", "date": day, "source": "contact_form"}))
    else:
        latest = sort_entries(entries)[0]
        if day:
            latest["date"] = day
        if vehicle and not latest.get("title"):
            latest["title"] = vehicle.strip()
    await save_entries(db, c, entries, keep_vehicle_text=True)


def units_pipeline(match: dict, start_day: str | None = None, end_day: str | None = None, filter_type: str = "sold") -> list:
    """Aggregation that turns contacts into one row per purchase record ('unit').
    Contacts that only ever had the legacy date_sold/vehicle fields count as one unit (the repair migrates them, this is belt and braces)."""
    legacy_unit = [{"id": {"$concat": ["legacy-", {"$toString": "$_id"}]}, "title": {"$ifNull": ["$vehicle", ""]}, "category": "vehicle",
                    "date": {"$dateToString": {"format": "%Y-%m-%d", "date": "$date_sold"}}}]
    pipe = [
        {"$match": {**match, "$or": [{"purchase_history.0": {"$exists": True}}, {"date_sold": {"$type": "date"}}]}},
        {"$addFields": {"_units": {"$cond": [{"$gt": [{"$size": {"$ifNull": ["$purchase_history", []]}}, 0]}, "$purchase_history",
                                              {"$cond": [{"$eq": [{"$type": "$date_sold"}, "date"]}, legacy_unit, []]}]}}},
        {"$addFields": {"_n_units": {"$size": "$_units"}}},
        {"$unwind": "$_units"},
        {"$addFields": {"_day": {"$substrCP": [{"$ifNull": ["$_units.date", ""]}, 0, 10]}}},
        {"$match": {"_day": {"$regex": r"^\d{4}-\d{2}-\d{2}$"}}},
    ]
    if start_day or end_day:
        rng: dict = {}
        if start_day:
            rng["$gte"] = start_day
        if end_day:
            rng["$lt"] = end_day
        pipe.append({"$match": {"_day": rng}})
    if filter_type == "referrals":
        pipe.append({"$match": {"referred_by": {"$exists": True, "$nin": [None, ""]}}})
    elif filter_type == "repeats":
        pipe.append({"$match": {"_n_units": {"$gt": 1}}})
    return pipe


async def count_units(db, match: dict, start_day: str | None, end_day: str | None, filter_type: str = "sold") -> int:
    rows = await db.contacts.aggregate(units_pipeline(match, start_day, end_day, filter_type) + [{"$count": "n"}]).to_list(1)
    return int(rows[0]["n"]) if rows else 0


async def units_by_month(db, match: dict, start_day: str, filter_type: str = "sold") -> dict:
    rows = await db.contacts.aggregate(units_pipeline(match, start_day, None, filter_type) + [
        {"$group": {"_id": {"$substrCP": ["$_day", 0, 7]}, "total": {"$sum": 1}}}]).to_list(200)
    return {r["_id"]: r["total"] for r in rows}


async def list_units(db, match: dict, start_day: str, end_day: str, filter_type: str = "sold", limit: int = 500) -> list:
    return await db.contacts.aggregate(units_pipeline(match, start_day, end_day, filter_type) + [
        {"$sort": {"_day": -1, "_units.created_at": -1}}, {"$limit": limit},
        {"$project": {"_id": 1, "first_name": 1, "last_name": 1, "phone": 1, "user_id": 1, "referred_by_name": 1, "photo_thumbnail": 1,
                      "unit": "$_units", "day": "$_day", "n_units": "$_n_units"}}]).to_list(limit)


async def repair_all(db) -> dict:
    """One-time (idempotent) migration to the purchase-record model. Additive: merges duplicate/blank archive rows,
    creates a record for any sale that only lived in date_sold/vehicle, re-derives counts. Never drops a purchase."""
    fixed = scanned = 0
    cur = db.contacts.find({"$or": [{"purchase_history.0": {"$exists": True}}, {"date_sold": {"$ne": None}}]},
                           {"purchase_history": 1, "date_sold": 1, "vehicle": 1, "prev_vehicle": 1, "sold_count": 1, "personal_details": 1})
    async for c in cur:
        scanned += 1
        raw = [e for e in (c.get("purchase_history") or []) if isinstance(e, dict)]
        entries = dedupe([normalize_entry(e) for e in raw])
        sold_day = ymd(c.get("date_sold"))
        if sold_day and not any(e.get("date") == sold_day for e in entries):
            # the current sale was never written as a record (legacy contact, or the repeat archive only kept the OLD one)
            hit = _match(entries, sold_day, c.get("vehicle"))
            if hit and not hit.get("date"):
                hit["date"] = sold_day
            else:
                entries.append(normalize_entry({"title": c.get("vehicle") or "", "category": "vehicle", "date": sold_day, "source": "migrated"}))
        entries = sort_entries(entries)
        d = derived(entries)
        before = (len(raw), int(c.get("sold_count") or 0), ymd(c.get("date_sold")))
        after = (len(entries), d["sold_count"], ymd(d["date_sold"]))
        shapes_ok = all(set(e.keys()) >= {"id", "title", "date"} and e.get("date") == ymd(e.get("date")) for e in raw)
        if before != after or not shapes_ok or c.get("prev_vehicle"):
            await save_entries(db, c, entries, keep_vehicle_text=True)
            fixed += 1
    return {"scanned": scanned, "fixed": fixed}
