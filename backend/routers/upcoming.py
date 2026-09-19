"""Upcoming: one agenda of everything coming up for a rep (tasks, appointments, Jessi's queued texts, dates)."""
import logging
from datetime import datetime, timezone, timedelta, date
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Request
from bson import ObjectId

from routers.database import get_db
from routers.rbac import get_current_user
from routers.tasks import _serialize, _fill_missing_contact_names

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/upcoming", tags=["Upcoming"])

MANAGER_ROLES = ("super_admin", "org_admin", "store_manager")
DATE_FIELDS = (("birthday", "birthday", "birthday"), ("date_sold", "sold", "anniversary"), ("anniversary", "anniversary", "anniversary"))


async def _authorize(request: Request, user_id: str) -> dict:
    me = await get_current_user(request)
    if str(me.get("_id")) != user_id and me.get("role") not in MANAGER_ROLES:
        raise HTTPException(status_code=403, detail="Not your agenda")
    return me


async def _local_tz(db, user_id: str):
    user = await db.users.find_one({"_id": ObjectId(user_id)}, {"timezone": 1, "store_id": 1})
    tz_name = (user or {}).get("timezone")
    if (not tz_name or tz_name == "UTC") and (user or {}).get("store_id") and ObjectId.is_valid(str(user["store_id"])):
        store = await db.stores.find_one({"_id": ObjectId(str(user["store_id"]))}, {"timezone": 1})
        tz_name = (store or {}).get("timezone") or tz_name
    try:
        return ZoneInfo(tz_name) if tz_name else timezone.utc
    except Exception:
        return timezone.utc


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _next_occurrence(d: datetime, start: date, end: date):
    """First anniversary of d (month/day) that falls in [start, end)."""
    for year in (start.year, start.year + 1):
        try:
            cand = date(year, d.month, d.day)
        except ValueError:
            cand = date(year, 2, 28)
        if start <= cand < end:
            return cand
    return None


async def _task_items(db, user_id: str, today_end: datetime, window_end: datetime):
    tasks = await db.tasks.find({
        "user_id": user_id,
        "status": {"$in": ["pending", "snoozed", None]},
        "due_date": {"$gt": today_end, "$lte": window_end},
    }).sort("due_date", 1).limit(300).to_list(300)
    rows = [_serialize(t) for t in tasks]
    await _fill_missing_contact_names(db, rows)
    items = []
    for t in rows:
        is_appt = t.get("type") == "appointment"
        items.append({
            "kind": "appointment" if is_appt else "task",
            "id": t["_id"],
            "at": t["due_date"],
            "owner": "you",
            "title": t.get("title") or ("Appointment" if is_appt else "Task"),
            "subtitle": (t.get("appointment_type") or "").replace("_", " ").capitalize() if is_appt else (t.get("description") or ""),
            "contact_id": t.get("contact_id") or "",
            "contact_name": t.get("contact_name") or "",
            "contact_phone": t.get("contact_phone") or "",
            "task_type": t.get("type") or "manual",
            "source": t.get("source") or "",
        })
    return items


async def _send_items(db, user_id: str, now_naive: datetime, window_end_naive: datetime):
    sends = await db.campaign_pending_sends.find({
        "user_id": user_id, "status": "pending",
        "send_at": {"$gt": now_naive, "$lte": window_end_naive},
    }, {
        "send_at": 1, "delivery_mode": 1, "campaign_name": 1, "contact_name": 1, "contact_id": 1,
        "contact_phone": 1, "message_template": 1, "channel": 1, "step": 1, "media_urls": 1, "type": 1, "event_type": 1,
    }).sort("send_at", 1).limit(300).to_list(300)
    items = []
    for s in sends:
        auto = s.get("delivery_mode", "auto") in ("auto", "automated")
        first = (s.get("contact_name") or "").split(" ")[0]
        body = (s.get("message_template") or "")
        for ph in ("{{first_name}}", "{{name}}", "{first_name}", "{name}"):
            body = body.replace(ph, first or "there")
        name = s.get("campaign_name") or "Text"
        if s.get("type") == "direct_scheduled":
            name = "Review request" if s.get("event_type") == "review_request_sent" else ("Delivery photo" if s.get("media_urls") else "Digital card link")
        items.append({
            "kind": "auto_text" if auto else "manual_text",
            "id": str(s["_id"]),
            "at": _aware(s["send_at"]).isoformat(),
            "owner": "jessi" if auto else "you",
            "title": name if auto else f"Send: {name}",
            "subtitle": body.strip().replace("\n", " ")[:140],
            "body": body,
            "contact_id": s.get("contact_id") or "",
            "contact_name": s.get("contact_name") or "",
            "contact_phone": s.get("contact_phone") or "",
            "channel": s.get("channel") or "sms",
            "step": s.get("step"),
            "has_media": bool(s.get("media_urls")),
        })
    return items


async def _date_items(db, user_id: str, tz, start: date, end: date):
    active = {}
    for _field, _etype, occasion in DATE_FIELDS:
        ctype = "sold_date" if _field == "date_sold" else occasion
        active[_field] = await db.campaigns.count_documents({
            "user_id": user_id, "active": True, "$or": [{"type": ctype}, {"date_type": ctype}],
        }) > 0
    docs = await db.contacts.find(
        {"user_id": user_id, "status": {"$nin": ["hidden", "merged", "deleted"]},
         "$or": [{"birthday": {"$ne": None}}, {"date_sold": {"$ne": None}}, {"anniversary": {"$ne": None}}]},
        {"first_name": 1, "last_name": 1, "phone": 1, "vehicle": 1, "birthday": 1, "date_sold": 1, "anniversary": 1,
         "tags": 1, "disabled_automations": 1},
    ).to_list(5000)
    items = []
    for c in docs:
        tags_l = [t.lower() for t in c.get("tags", []) if isinstance(t, str)]
        sold_d = c.get("date_sold")
        name = f"{c.get('first_name', '')} {c.get('last_name', '')}".strip()
        for field, etype, occasion in DATE_FIELDS:
            d = c.get(field)
            if not isinstance(d, datetime):
                continue
            if field == "anniversary" and isinstance(sold_d, datetime) and (sold_d.month, sold_d.day) == (d.month, d.day):
                continue
            occ = _next_occurrence(d, start, end)
            if not occ:
                continue
            if field == "date_sold" and d.year >= occ.year:
                continue
            years = occ.year - d.year if 1930 < d.year < occ.year else None
            label = {"birthday": "Birthday", "sold": f"{years} year sold anniversary" if years else "Sold anniversary",
                     "anniversary": f"{years} year anniversary" if years else "Anniversary"}[etype]
            ctype = "sold_date" if field == "date_sold" else occasion
            handled = active[field] and occasion in tags_l and ctype not in (c.get("disabled_automations") or [])
            items.append({
                "kind": "date",
                "id": f"{str(c['_id'])}_{field}",
                "at": datetime.combine(occ, datetime.min.time(), tzinfo=tz).replace(hour=9).isoformat(),
                "all_day": True,
                "owner": "jessi" if handled else "you",
                "title": label,
                "subtitle": c.get("vehicle") or "",
                "contact_id": str(c["_id"]),
                "contact_name": name,
                "contact_phone": c.get("phone") or "",
                "occasion": etype,
                "years": years,
                "handled": handled,
            })
    return items


@router.get("/{user_id}")
async def get_upcoming(user_id: str, request: Request, days: int = 14):
    await _authorize(request, user_id)
    days = max(1, min(days, 60))
    db = get_db()
    tz = await _local_tz(db, user_id)
    now = datetime.now(timezone.utc)
    local_now = now.astimezone(tz)
    local_midnight = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = (local_midnight + timedelta(days=1)).astimezone(timezone.utc)
    window_end = today_end + timedelta(days=days)
    tomorrow = local_now.date() + timedelta(days=1)

    items = (
        await _task_items(db, user_id, today_end, window_end)
        + await _send_items(db, user_id, now.replace(tzinfo=None), window_end.replace(tzinfo=None))
        + await _date_items(db, user_id, tz, tomorrow, tomorrow + timedelta(days=days))
    )

    groups: dict = {}
    for it in items:
        local = datetime.fromisoformat(it["at"]).astimezone(tz)
        key = local.date().isoformat()
        it["time"] = None if it.get("all_day") else local.strftime("%-I:%M %p")
        it["date"] = key
        groups.setdefault(key, []).append(it)
    for rows in groups.values():
        rows.sort(key=lambda r: (r.get("all_day", False) and 1 or 0, r["at"]))

    return {
        "timezone": getattr(tz, "key", "UTC"),
        "today": local_now.date().isoformat(),
        "days": days,
        "counts": {
            "you": sum(1 for i in items if i["owner"] == "you"),
            "jessi": sum(1 for i in items if i["owner"] == "jessi"),
            "dates": sum(1 for i in items if i["kind"] == "date"),
            "total": len(items),
        },
        "groups": [{"date": k, "items": groups[k]} for k in sorted(groups)],
    }


async def _own_pending_send(db, user_id: str, send_id: str) -> dict:
    if not ObjectId.is_valid(send_id):
        raise HTTPException(status_code=400, detail="Bad id")
    s = await db.campaign_pending_sends.find_one({"_id": ObjectId(send_id), "user_id": user_id})
    if not s:
        raise HTTPException(status_code=404, detail="Queued text not found")
    if s.get("status") != "pending":
        raise HTTPException(status_code=409, detail=f"This text is already {s.get('status')}")
    return s


async def _refresh_enrollment(db, enrollment_id: str):
    if not enrollment_id or not ObjectId.is_valid(enrollment_id):
        return
    nxt = await db.campaign_pending_sends.find_one({"enrollment_id": enrollment_id, "status": "pending"}, sort=[("send_at", 1)])
    await db.campaign_enrollments.update_one(
        {"_id": ObjectId(enrollment_id), "status": "active"},
        {"$set": {"next_send_at": (nxt or {}).get("send_at"), **({} if nxt else {"status": "completed"})}},
    )


@router.post("/{user_id}/sends/{send_id}/send-now")
async def send_now(user_id: str, send_id: str, request: Request):
    """Pull a queued text forward; the scheduler picks it up within a minute."""
    await _authorize(request, user_id)
    db = get_db()
    s = await _own_pending_send(db, user_id, send_id)
    now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.campaign_pending_sends.update_one({"_id": s["_id"]}, {"$set": {"send_at": now_naive, "send_now_requested_at": now_naive}})
    await _refresh_enrollment(db, s.get("enrollment_id") or "")
    return {"ok": True, "send_at": now_naive.replace(tzinfo=timezone.utc).isoformat()}


@router.post("/{user_id}/sends/{send_id}/cancel")
async def cancel_send(user_id: str, send_id: str, request: Request):
    """Skip one queued text; the rest of the campaign keeps going."""
    await _authorize(request, user_id)
    db = get_db()
    s = await _own_pending_send(db, user_id, send_id)
    now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.campaign_pending_sends.update_one({"_id": s["_id"]}, {"$set": {"status": "skipped", "skipped_at": now_naive, "skipped_via": "upcoming"}})
    await _refresh_enrollment(db, s.get("enrollment_id") or "")
    return {"ok": True}
