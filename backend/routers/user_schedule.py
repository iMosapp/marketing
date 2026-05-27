"""
User Availability Schedule Router

Stores per-user work schedules. Used to:
- Gate push notifications during off-hours (quiet mode)
- Route shared-inbox leads only to on-shift reps
- Show team availability in admin views

Data model (collection: user_schedules):
  user_id          str
  timezone         str        e.g. "America/Denver"
  notification_quiet bool     if True, suppress pushes outside schedule
  weekly_schedule  dict       {monday: [{start:"09:00",end:"17:00"}], ...}
  rotation_enabled bool
  rotation_anchor  str        ISO date (Monday of "Week A")
  schedule_b       dict       same shape — used when rotation_enabled
  available_override_until str|null  ISO datetime — force-available until then
  updated_at       datetime
"""
import os
import logging
from datetime import datetime, timezone, date, timedelta
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from bson import ObjectId

from routers.database import get_db

router = APIRouter(prefix="/schedule", tags=["User Schedule"])
logger = logging.getLogger(__name__)

DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

DEFAULT_SCHEDULE = {d: [] for d in DAYS}


# ── Pydantic models ───────────────────────────────────────────────────────────

class TimeBlock(BaseModel):
    start: str   # "09:00"
    end:   str   # "17:00"


class WeeklySchedule(BaseModel):
    monday:    List[TimeBlock] = []
    tuesday:   List[TimeBlock] = []
    wednesday: List[TimeBlock] = []
    thursday:  List[TimeBlock] = []
    friday:    List[TimeBlock] = []
    saturday:  List[TimeBlock] = []
    sunday:    List[TimeBlock] = []


class ScheduleUpdate(BaseModel):
    timezone:            Optional[str]           = None
    notification_quiet:  Optional[bool]          = None
    weekly_schedule:     Optional[WeeklySchedule] = None
    rotation_enabled:    Optional[bool]          = None
    rotation_anchor:     Optional[str]           = None   # "YYYY-MM-DD"
    schedule_b:          Optional[WeeklySchedule] = None
    available_override_until: Optional[str]      = None   # ISO datetime or null


# ── Utility: is user currently on shift? ─────────────────────────────────────

async def is_user_available(user_id: str) -> bool:
    """
    Returns True if the user is currently within their scheduled hours
    (or has no schedule / quiet mode disabled).
    Used by push and lead routing.
    """
    db = get_db()
    sched = await db.user_schedules.find_one({"user_id": user_id})
    if not sched:
        return True   # No schedule set → always available

    if not sched.get("notification_quiet", False):
        return True   # Quiet mode off → always send

    # Temporary override: "I'm available now"
    override = sched.get("available_override_until")
    if override:
        try:
            override_dt = datetime.fromisoformat(override.replace("Z", "+00:00"))
            if datetime.now(timezone.utc) < override_dt:
                return True
        except Exception:
            pass

    # Get current time in user's timezone
    try:
        import pytz
        tz_str = sched.get("timezone", "America/Denver")
        tz = pytz.timezone(tz_str)
        local_now = datetime.now(timezone.utc).astimezone(tz)
    except Exception:
        local_now = datetime.now(timezone.utc)

    # Determine which week schedule to use (A or B)
    weekly_sched = None
    if sched.get("rotation_enabled") and sched.get("rotation_anchor"):
        try:
            anchor = date.fromisoformat(sched["rotation_anchor"])
            today  = local_now.date()
            delta_days = (today - anchor).days
            week_num   = delta_days // 7
            is_week_b  = (week_num % 2 == 1)
            weekly_sched = sched.get("schedule_b") if is_week_b else sched.get("weekly_schedule")
        except Exception:
            weekly_sched = sched.get("weekly_schedule", {})
    else:
        weekly_sched = sched.get("weekly_schedule", {})

    if not weekly_sched:
        return True

    # ISO weekday: Monday=0 … Sunday=6
    day_name = DAYS[local_now.weekday()]
    blocks = weekly_sched.get(day_name, [])
    if not blocks:
        return False   # No hours set for this day → off

    current_hhmm = local_now.strftime("%H:%M")
    for block in blocks:
        if block.get("start", "00:00") <= current_hhmm < block.get("end", "23:59"):
            return True

    return False


async def next_available_window(user_id: str) -> Optional[str]:
    """Return human-readable 'Available from HH:MM' or None."""
    db = get_db()
    sched = await db.user_schedules.find_one({"user_id": user_id})
    if not sched or not sched.get("notification_quiet"):
        return None

    try:
        import pytz
        tz = pytz.timezone(sched.get("timezone", "America/Denver"))
        local_now = datetime.now(timezone.utc).astimezone(tz)
    except Exception:
        return None

    weekly_sched = sched.get("schedule_b") if (
        sched.get("rotation_enabled") and _is_week_b(sched, local_now)
    ) else sched.get("weekly_schedule", {})

    day_name = DAYS[local_now.weekday()]
    blocks = weekly_sched.get(day_name, [])
    current_hhmm = local_now.strftime("%H:%M")
    for block in sorted(blocks, key=lambda b: b.get("start", "")):
        if block.get("start", "") > current_hhmm:
            return block["start"]
    # Check next days
    for offset in range(1, 8):
        next_day = DAYS[(local_now.weekday() + offset) % 7]
        blocks = weekly_sched.get(next_day, [])
        if blocks:
            return f"{next_day.capitalize()} {sorted(blocks, key=lambda b: b.get('start',''))[0]['start']}"
    return None


def _is_week_b(sched: dict, local_now: datetime) -> bool:
    try:
        anchor = date.fromisoformat(sched["rotation_anchor"])
        delta_days = (local_now.date() - anchor).days
        return (delta_days // 7) % 2 == 1
    except Exception:
        return False


def _serialize_schedule(doc: dict) -> dict:
    return {
        "user_id":                   doc.get("user_id"),
        "timezone":                  doc.get("timezone", "America/Denver"),
        "notification_quiet":        doc.get("notification_quiet", False),
        "weekly_schedule":           doc.get("weekly_schedule", DEFAULT_SCHEDULE),
        "rotation_enabled":          doc.get("rotation_enabled", False),
        "rotation_anchor":           doc.get("rotation_anchor"),
        "schedule_b":                doc.get("schedule_b", DEFAULT_SCHEDULE),
        "available_override_until":  doc.get("available_override_until"),
        "updated_at":                doc.get("updated_at").isoformat() if doc.get("updated_at") else None,
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/me")
async def get_my_schedule(x_user_id: str = Header(None, alias="X-User-ID")):
    """Get the current user's schedule."""
    if not x_user_id:
        raise HTTPException(status_code=401, detail="User ID required")
    db = get_db()
    doc = await db.user_schedules.find_one({"user_id": x_user_id})
    if not doc:
        # Return defaults
        return {
            "user_id":               x_user_id,
            "timezone":              "America/Denver",
            "notification_quiet":    False,
            "weekly_schedule":       DEFAULT_SCHEDULE,
            "rotation_enabled":      False,
            "rotation_anchor":       None,
            "schedule_b":            DEFAULT_SCHEDULE,
            "available_override_until": None,
            "updated_at":            None,
        }
    return _serialize_schedule(doc)


@router.put("/me")
async def save_my_schedule(
    update: ScheduleUpdate,
    x_user_id: str = Header(None, alias="X-User-ID"),
):
    """Save / update the current user's schedule."""
    if not x_user_id:
        raise HTTPException(status_code=401, detail="User ID required")
    db = get_db()

    set_doc: dict = {"updated_at": datetime.now(timezone.utc)}
    if update.timezone              is not None: set_doc["timezone"]              = update.timezone
    if update.notification_quiet    is not None: set_doc["notification_quiet"]    = update.notification_quiet
    if update.weekly_schedule       is not None: set_doc["weekly_schedule"]       = update.weekly_schedule.dict()
    if update.rotation_enabled      is not None: set_doc["rotation_enabled"]      = update.rotation_enabled
    if update.rotation_anchor       is not None: set_doc["rotation_anchor"]       = update.rotation_anchor
    if update.schedule_b            is not None: set_doc["schedule_b"]            = update.schedule_b.dict()
    if update.available_override_until is not None:
        set_doc["available_override_until"] = update.available_override_until or None

    await db.user_schedules.update_one(
        {"user_id": x_user_id},
        {"$set": set_doc, "$setOnInsert": {"user_id": x_user_id, "created_at": datetime.now(timezone.utc)}},
        upsert=True,
    )
    doc = await db.user_schedules.find_one({"user_id": x_user_id})
    return _serialize_schedule(doc)


@router.post("/me/override")
async def set_availability_override(
    data: dict,
    x_user_id: str = Header(None, alias="X-User-ID"),
):
    """
    Temporarily mark self as available (override quiet mode).
    data: { hours: 2 } or { until_end_of_day: true } or { clear: true }
    """
    if not x_user_id:
        raise HTTPException(status_code=401, detail="User ID required")
    db = get_db()
    now = datetime.now(timezone.utc)

    if data.get("clear"):
        override_until = None
    elif data.get("until_end_of_day"):
        # End of today in user's timezone
        try:
            import pytz
            sched = await db.user_schedules.find_one({"user_id": x_user_id})
            tz_str = (sched or {}).get("timezone", "America/Denver")
            tz = pytz.timezone(tz_str)
            local = now.astimezone(tz)
            end_of_day = local.replace(hour=23, minute=59, second=59, microsecond=0)
            override_until = end_of_day.astimezone(timezone.utc).isoformat()
        except Exception:
            override_until = (now + timedelta(hours=8)).isoformat()
    else:
        hours = float(data.get("hours", 2))
        override_until = (now + timedelta(hours=hours)).isoformat()

    await db.user_schedules.update_one(
        {"user_id": x_user_id},
        {"$set": {"available_override_until": override_until, "updated_at": now},
         "$setOnInsert": {"user_id": x_user_id, "created_at": now}},
        upsert=True,
    )
    available = await is_user_available(x_user_id)
    return {"available": available, "available_override_until": override_until}


@router.get("/status/{user_id}")
async def get_user_availability(user_id: str):
    """Check if a specific user is currently on shift."""
    available = await is_user_available(user_id)
    next_window = await next_available_window(user_id) if not available else None
    return {
        "user_id":     user_id,
        "available":   available,
        "next_window": next_window,
    }


@router.get("/team")
async def get_team_availability(x_user_id: str = Header(None, alias="X-User-ID")):
    """Get current availability for all users in same account. Admin use."""
    db = get_db()
    user = await db.users.find_one({"_id": ObjectId(x_user_id)}, {"account_id": 1, "store_id": 1, "organization_id": 1})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    acct = user.get("account_id") or str(user["_id"])
    teammates = await db.users.find(
        {"$or": [{"account_id": acct}, {"store_id": user.get("store_id")}], "status": {"$ne": "deactivated"}},
        {"_id": 1, "name": 1, "timezone": 1}
    ).to_list(100)

    result = []
    for t in teammates:
        uid = str(t["_id"])
        avail = await is_user_available(uid)
        result.append({"user_id": uid, "name": t.get("name"), "available": avail})
    return result
