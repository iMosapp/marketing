"""
When may the business initiate contact with a new lead?

Two independent gates decide the timing of the intake text and the rep call ladder:
  1. Texting window (compliance): business-initiated texts/calls only inside the source's
     window, measured in the CUSTOMER's local time (area code -> tz, else store tz).
     Default 9 AM - 8 PM, the strictest common state rule.
  2. Store hours: when the store is closed and the source's after_hours_mode is
     'text_and_ai', the intake text still goes out (if inside the window), Jessi handles
     replies, and the call ladder waits for opening.

Anything pushed to the next morning is released one lead per STAGGER_SECONDS per store so
40 overnight leads do not ring the whole team at once. Jessi replying to a customer's own
text is never gated here (consumer-initiated).
"""
import logging
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

DAY_NAMES = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
DEFAULT_TZ = "America/Denver"
DEFAULT_WINDOW_START = "09:00"
DEFAULT_WINDOW_END = "20:00"
STAGGER_SECONDS = 60
OPEN_BUFFER_MINUTES = 5
LADDER_AFTER_INTAKE_SECONDS = 60
SLOTS = "lead_release_slots"


def _tz(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name or DEFAULT_TZ)
    except Exception:
        return ZoneInfo(DEFAULT_TZ)


def _hm(value: str, default: str) -> tuple[int, int]:
    try:
        h, m = (value or default).split(":")
        h, m = int(h), int(m)
        if 0 <= h <= 23 and 0 <= m <= 59:
            return h, m
    except Exception:
        pass
    h, m = default.split(":")
    return int(h), int(m)


def store_timezone(store: dict) -> str:
    return (store or {}).get("timezone") or DEFAULT_TZ


def customer_timezone(phone: str, fallback: str) -> str:
    """Area code -> IANA zone. Ambiguous numbers (toll-free, test ranges) fall back to the store."""
    try:
        import phonenumbers
        from phonenumbers import timezone as pn_tz
        zones = pn_tz.time_zones_for_number(phonenumbers.parse(phone or "", "US"))
        if len(zones) == 1 and zones[0] not in ("Etc/Unknown",):
            return zones[0]
    except Exception:
        pass
    return fallback


def store_hours_status(store: dict, now: datetime | None = None) -> dict:
    """{'configured', 'open', 'opens_at' (UTC datetime or None), 'tz', 'today'}"""
    now = now or datetime.now(timezone.utc)
    hours = (store or {}).get("business_hours") or {}
    tz = _tz(store_timezone(store))
    local = now.astimezone(tz)
    today = hours.get(DAY_NAMES[local.weekday()]) if hours else None
    if not hours:
        return {"configured": False, "open": True, "opens_at": None, "tz": str(tz.key), "today": None}
    if today and today.get("open") and today.get("close"):
        oh, om = _hm(today["open"], "09:00")
        ch, cm = _hm(today["close"], "18:00")
        open_dt = local.replace(hour=oh, minute=om, second=0, microsecond=0)
        close_dt = local.replace(hour=ch, minute=cm, second=0, microsecond=0)
        if open_dt <= local < close_dt:
            return {"configured": True, "open": True, "opens_at": None, "tz": tz.key, "today": today}
        if local < open_dt:
            opens = open_dt + timedelta(minutes=OPEN_BUFFER_MINUTES)
            return {"configured": True, "open": False, "opens_at": opens.astimezone(timezone.utc), "tz": tz.key, "today": today}
    for offset in range(1, 8):
        day = local + timedelta(days=offset)
        h = hours.get(DAY_NAMES[day.weekday()])
        if h and h.get("open"):
            oh, om = _hm(h["open"], "09:00")
            opens = day.replace(hour=oh, minute=om, second=0, microsecond=0) + timedelta(minutes=OPEN_BUFFER_MINUTES)
            return {"configured": True, "open": False, "opens_at": opens.astimezone(timezone.utc), "tz": tz.key, "today": today}
    return {"configured": True, "open": False, "opens_at": now + timedelta(hours=12), "tz": tz.key, "today": today}


def window_status(source: dict, tz_name: str, now: datetime | None = None) -> dict:
    """{'inside', 'opens_at' (UTC datetime), 'start', 'end', 'tz'} for the source's texting window."""
    now = now or datetime.now(timezone.utc)
    start = (source or {}).get("text_window_start") or DEFAULT_WINDOW_START
    end = (source or {}).get("text_window_end") or DEFAULT_WINDOW_END
    tz = _tz(tz_name)
    local = now.astimezone(tz)
    sh, sm = _hm(start, DEFAULT_WINDOW_START)
    eh, em = _hm(end, DEFAULT_WINDOW_END)
    start_dt = local.replace(hour=sh, minute=sm, second=0, microsecond=0)
    end_dt = local.replace(hour=eh, minute=em, second=0, microsecond=0)
    if end_dt <= start_dt:
        return {"inside": True, "opens_at": None, "start": start, "end": end, "tz": tz.key}
    if start_dt <= local < end_dt:
        return {"inside": True, "opens_at": None, "start": start, "end": end, "tz": tz.key}
    opens = start_dt if local < start_dt else start_dt + timedelta(days=1)
    return {"inside": False, "opens_at": opens.astimezone(timezone.utc), "start": start, "end": end, "tz": tz.key}


async def reserve_release_slot(db, scope: str, base: datetime) -> datetime:
    """Nth lead released at the same moment for the same store goes out N minutes later."""
    key = f"{scope}:{base.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M')}"
    doc = await db[SLOTS].find_one_and_update(
        {"key": key},
        {"$inc": {"count": 1}, "$setOnInsert": {"created_at": datetime.now(timezone.utc)}},
        upsert=True,
        return_document=True,
    )
    n = max(0, int((doc or {}).get("count", 1)) - 1)
    return base + timedelta(seconds=n * STAGGER_SECONDS)


def _iso(dt) -> str | None:
    return dt.astimezone(timezone.utc).isoformat() if isinstance(dt, datetime) else None


async def build_contact_plan(db, source: dict, store: dict, phone: str, now: datetime | None = None) -> dict:
    """Decide when the intake text and the call ladder may fire for one new lead."""
    now = now or datetime.now(timezone.utc)
    store_tz = store_timezone(store)
    cust_tz = customer_timezone(phone, store_tz)
    win = window_status(source, cust_tz, now)
    hours = store_hours_status(store, now)
    mode = (source or {}).get("after_hours_mode") or "text_and_ai"
    scope = str((source or {}).get("store_id") or (source or {}).get("_id") or "global")

    intake_at, intake_reason = now, None
    if not win["inside"]:
        intake_at = await reserve_release_slot(db, scope, win["opens_at"])
        intake_reason = "texting_window"

    ladder_base, ladder_reasons = now, []
    if not win["inside"]:
        ladder_base, ladder_reasons = max(ladder_base, win["opens_at"]), ["texting_window"]
    if hours["configured"] and not hours["open"] and mode == "text_and_ai" and hours["opens_at"]:
        if hours["opens_at"] > ladder_base:
            ladder_base = hours["opens_at"]
        ladder_reasons.append("store_closed")

    if not ladder_reasons:
        ladder_at = now
    elif intake_reason and intake_at >= ladder_base:
        ladder_at = intake_at + timedelta(seconds=LADDER_AFTER_INTAKE_SECONDS)
    else:
        ladder_at = await reserve_release_slot(db, f"{scope}:ladder", ladder_base)

    jessi_on = bool((source or {}).get("va_enabled", True)) or (hours["configured"] and not hours["open"] and mode == "text_and_ai")

    return {
        "computed_at": _iso(now),
        "customer_tz": cust_tz,
        "store_tz": hours["tz"],
        "window": {"start": win["start"], "end": win["end"], "inside": win["inside"], "opens_at": _iso(win["opens_at"])},
        "store": {"configured": hours["configured"], "open": hours["open"], "opens_at": _iso(hours["opens_at"]), "today": hours["today"]},
        "after_hours_mode": mode,
        "after_hours": hours["configured"] and not hours["open"],
        "intake_at": _iso(intake_at),
        "intake_deferred": intake_reason is not None,
        "intake_reason": intake_reason,
        "ladder_at": _iso(ladder_at),
        "ladder_deferred": bool(ladder_reasons),
        "ladder_reasons": ladder_reasons,
        "jessi_on": jessi_on,
    }


def parse_iso(value) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None
