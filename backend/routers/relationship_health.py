"""
Relationship Health - per-contact relationship scoring + book-of-business rollup.
Reframes IMOS from "a texting app" into "a book of business manager".

Buckets:
  connected   🟢  engaged / contacted within 45 days
  cooling     🟡  no personal contact 45-90 days
  at_risk     🔴  90+ days silent
  opportunity 🔥  recent engagement signal (card view / link click / review click) or sold recently
  advocate    💙  left a review or referred someone

All inputs come from data already stored (contact fields + contact_events + tags).
No new data capture required.
"""
import logging
from datetime import datetime, timezone
from bson import ObjectId

from fastapi import APIRouter, HTTPException
from routers.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/relationship-health", tags=["relationship-health"])

BUCKET_META = {
    "opportunity": {"label": "Opportunity", "emoji": "🔥", "color": "#FF3B30", "icon": "flame",           "order": 0},
    "at_risk":     {"label": "At Risk",     "emoji": "🔴", "color": "#FF453A", "icon": "alert-circle",     "order": 1},
    "cooling":     {"label": "Cooling",     "emoji": "🟡", "color": "#FF9F0A", "icon": "time",             "order": 2},
    "advocate":    {"label": "Advocate",    "emoji": "💙", "color": "#0A84FF", "icon": "heart",            "order": 3},
    "connected":   {"label": "Connected",   "emoji": "🟢", "color": "#30D158", "icon": "checkmark-circle", "order": 4},
}

# Engagement / intent signals (customer engaging with the rep) — within 14 days => Opportunity
OPPORTUNITY_EVENTS = {
    "customer_reply", "inbound_call",
    "digital_card_viewed", "store_card_viewed", "showcase_viewed", "link_page_viewed",
    "review_page_viewed", "media_viewed", "congrats_card_viewed", "birthday_card_viewed",
    "thankyou_card_viewed",
    "card_call_clicked", "card_text_clicked", "card_email_clicked", "card_website_clicked",
    "card_review_clicked", "card_online_review_clicked", "card_refer_clicked",
    "card_quick_link_clicked", "card_social_clicked", "card_salesman_clicked",
    "link_page_link_clicked", "links_quick_link_clicked", "page_quick_link_clicked",
    "showcase_quick_link_clicked", "review_link_clicked", "online_review_clicked",
    "opt_in_clicked", "vcard_saved", "digital_card_saved",
}
# Customer became an advocate
REVIEW_EVENTS = {"review_submitted", "internal_review_submitted", "review_shared"}
ADVOCATE_TAGS = {"referral", "advocate", "referred", "review", "raving fan"}

# Events that represent a real touch / interaction (used to compute "last contact").
# Excludes record-keeping noise (creation, edits, tasks, tests).
NON_TOUCH_EVENTS = {
    "creation", "setup", "new_contact", "new_contact_added", "name_updated",
    "note_updated", "work_email_added", "add_work", "purchase_added",
    "task_created", "task_completed", "custom", "campaign_removed",
    "sms_failed", "email_failed",
}

CONTACT_PROJ = {
    "_id": 1, "first_name": 1, "last_name": 1, "company": 1, "phone": 1, "email": 1,
    "photo_thumbnail": 1, "photo_url": 1, "photo_path": 1, "vehicle": 1,
    "tags": 1, "date_sold": 1,
    "referred_by": 1, "referred_by_name": 1, "referral_notes": 1,
    "last_activity_at": 1, "created_at": 1,
}


def _as_utc(v):
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    if isinstance(v, str):
        try:
            d = datetime.fromisoformat(v.replace("Z", "+00:00"))
            return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        except Exception:
            return None
    return None


def _photo(c: dict) -> str:
    return c.get("photo_thumbnail") or c.get("photo_url") or c.get("photo_path") or ""


def _norm_name(c: dict) -> str:
    return f"{c.get('first_name','')} {c.get('last_name','')}".strip().lower()


def _is_advocate(c: dict, cid: str, advocate_ids: set, referrer_names: set) -> bool:
    tags = [str(t).lower() for t in (c.get("tags") or [])]
    return bool(
        cid in advocate_ids                                   # left a review
        or any(t in ADVOCATE_TAGS for t in tags)              # tagged advocate/referral
        or (_norm_name(c) and _norm_name(c) in referrer_names)  # they referred someone
    )


def _score(c: dict, last_touch, opp_ids: set, advocate_ids: set, referrer_names: set, now: datetime) -> dict:
    cid = str(c["_id"])
    is_advocate = _is_advocate(c, cid, advocate_ids, referrer_names)

    is_opportunity = cid in opp_ids
    ds_sold = _as_utc(c.get("date_sold"))
    if ds_sold and (now - ds_sold).days <= 30:
        is_opportunity = True

    days_since = (now - last_touch).days if last_touch else None

    if is_opportunity:
        bucket, reason = "opportunity", "Active now — recent engagement signal"
    elif days_since is None or days_since >= 90:
        bucket = "at_risk"
        reason = f"{days_since} days silent" if days_since is not None else "No contact on record"
    elif days_since >= 45:
        bucket, reason = "cooling", f"{days_since} days since last contact"
    elif is_advocate:
        bucket, reason = "advocate", "Left a review or sent a referral"
    else:
        bucket, reason = "connected", "Engaged recently"

    name = f"{c.get('first_name','')} {c.get('last_name','')}".strip() or c.get("company", "") or "Unknown"
    return {
        "contact_id": cid,
        "name": name,
        "phone": c.get("phone", ""),
        "photo_thumbnail": _photo(c),
        "vehicle": c.get("vehicle", ""),
        "bucket": bucket,
        "reason": reason,
        "days_since": days_since,
        "is_advocate": is_advocate,
        "last_touch": last_touch.isoformat() if last_touch else None,
    }


async def _gather_signals(db, user_id: str, now: datetime):
    """Return (last_touch_by_contact, opportunity_ids, advocate_ids) from contact_events."""
    from datetime import timedelta
    # Last real touch per contact (max timestamp of meaningful events)
    last_touch_map: dict = {}
    pipeline = [
        {"$match": {"user_id": user_id, "event_type": {"$nin": list(NON_TOUCH_EVENTS)}}},
        {"$group": {"_id": "$contact_id", "last": {"$max": "$timestamp"}}},
    ]
    async for row in db.contact_events.aggregate(pipeline):
        if row.get("_id") is not None:
            last_touch_map[str(row["_id"])] = _as_utc(row.get("last"))

    cutoff = now - timedelta(days=14)
    opp = await db.contact_events.find(
        {"user_id": user_id, "event_type": {"$in": list(OPPORTUNITY_EVENTS)}, "timestamp": {"$gte": cutoff}},
        {"contact_id": 1},
    ).limit(3000).to_list(3000)
    opp_ids = {str(e["contact_id"]) for e in opp if e.get("contact_id")}

    rev = await db.contact_events.find(
        {"user_id": user_id, "event_type": {"$in": list(REVIEW_EVENTS)}},
        {"contact_id": 1},
    ).limit(3000).to_list(3000)
    adv_ids = {str(e["contact_id"]) for e in rev if e.get("contact_id")}
    return last_touch_map, opp_ids, adv_ids


def _best_last_touch(c: dict, last_touch_map: dict):
    cid = str(c["_id"])
    cands = [last_touch_map.get(cid), _as_utc(c.get("last_activity_at")), _as_utc(c.get("created_at"))]
    cands = [x for x in cands if x]
    return max(cands) if cands else None


# short cache — book scans are read-heavy; matches home's 30s freshness
from cachetools import TTLCache as _TTLCache
_book_cache: _TTLCache = _TTLCache(maxsize=200, ttl=30)


async def _build_book(db, user_id: str) -> list:
    cached = _book_cache.get(user_id)
    if cached is not None:
        return cached
    now = datetime.now(timezone.utc)
    last_touch_map, opp_ids, adv_ids = await _gather_signals(db, user_id, now)
    contacts = await db.contacts.find(
        {"user_id": user_id, "status": {"$nin": ["hidden", "merged", "deleted"]}},
        CONTACT_PROJ,
    ).limit(5000).to_list(5000)
    referrer_names = {n for c in contacts if (n := str(c.get("referred_by_name") or "").strip().lower())}
    book = [_score(c, _best_last_touch(c, last_touch_map), opp_ids, adv_ids, referrer_names, now) for c in contacts]
    _book_cache[user_id] = book
    return book


@router.get("/{user_id}/summary")
async def health_summary(user_id: str):
    """Book-of-business rollup: counts per bucket."""
    db = get_db()
    book = await _build_book(db, user_id)
    counts = {k: 0 for k in BUCKET_META}
    for row in book:
        counts[row["bucket"]] = counts.get(row["bucket"], 0) + 1
    advocates = sum(1 for r in book if r["is_advocate"])
    buckets = [
        {"key": k, **BUCKET_META[k], "count": counts.get(k, 0)}
        for k in sorted(BUCKET_META, key=lambda x: BUCKET_META[x]["order"])
    ]
    return {
        "total": len(book),
        "advocates": advocates,
        "buckets": buckets,
        "needs_attention": counts.get("at_risk", 0) + counts.get("cooling", 0),
        "opportunities": counts.get("opportunity", 0),
    }


@router.get("/{user_id}/contacts")
async def health_contacts(user_id: str, bucket: str = "cooling"):
    """Drill-down list of contacts in a given bucket, worst-first (most days silent)."""
    if bucket not in BUCKET_META:
        raise HTTPException(status_code=400, detail="Invalid bucket")
    db = get_db()
    book = await _build_book(db, user_id)
    rows = [r for r in book if r["bucket"] == bucket]
    rows.sort(key=lambda r: (r["days_since"] if r["days_since"] is not None else 10000), reverse=True)
    return {"bucket": bucket, **BUCKET_META[bucket], "count": len(rows), "items": rows}


@router.get("/{user_id}/contact/{contact_id}")
async def health_one(user_id: str, contact_id: str):
    """Single-contact health (for the badge on the contact card)."""
    db = get_db()
    try:
        c = await db.contacts.find_one({"_id": ObjectId(contact_id), "user_id": user_id}, CONTACT_PROJ)
    except Exception:
        c = None
    if not c:
        raise HTTPException(status_code=404, detail="Contact not found")
    now = datetime.now(timezone.utc)
    last_touch_map, opp_ids, adv_ids = await _gather_signals(db, user_id, now)
    ref_raw = await db.contacts.distinct("referred_by_name", {"user_id": user_id})
    referrer_names = {str(n).strip().lower() for n in ref_raw if n}
    row = _score(c, _best_last_touch(c, last_touch_map), opp_ids, adv_ids, referrer_names, now)
    return {**row, **BUCKET_META[row["bucket"]]}
