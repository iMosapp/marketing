"""Outbound calling compliance for the power dialer: TCPA / TSR (FTC) / state mini-TCPA controls.
Rules encoded here are the ones verified June 2026; counsel signs off on use. Everything is deliberately conservative."""
import re
from datetime import datetime, timezone, timedelta, date, time
from typing import Optional
from zoneinfo import ZoneInfo

import phonenumbers
from phonenumbers import geocoder, timezone as pn_tz

DNC_LIST, DNC_REGISTRY, REGISTRY_META = "dnc_list", "dnc_registry", "dnc_registry"

FEDERAL = {"start": "08:00", "end": "21:00"}
# Only rules stricter than federal. sunday/saturday = (start, end); no_sunday / no_holiday = no calls at all that day.
STATE_RULES = {
    "FL": {"start": "08:00", "end": "20:00", "max_per_day": 3, "note": "FTSA: 8am-8pm, max 3 calls per 24h on the same matter"},
    "OK": {"start": "08:00", "end": "20:00", "max_per_day": 3, "note": "OTSA: 8am-8pm, max 3 calls per 24h"},
    "MD": {"start": "08:00", "end": "20:00", "max_per_day": 3, "note": "8am-8pm, max 3 calls per 24h"},
    "WA": {"start": "08:00", "end": "20:00", "note": "8am-8pm"},
    "MA": {"start": "08:00", "end": "20:00", "note": "8am-8pm"},
    "AL": {"start": "08:00", "end": "20:00", "no_sunday": True, "no_holiday": True, "note": "8am-8pm, no Sundays or holidays"},
    "LA": {"start": "08:00", "end": "20:00", "no_sunday": True, "no_holiday": True, "note": "8am-8pm Mon-Sat, no Sundays or holidays"},
    "MS": {"start": "08:00", "end": "20:00", "no_sunday": True, "note": "8am-8pm, no Sundays"},
    "RI": {"start": "09:00", "end": "18:00", "saturday": ("10:00", "17:00"), "no_sunday": True, "no_holiday": True, "note": "9am-6pm weekdays, 10am-5pm Saturday, no Sundays or holidays"},
    "SD": {"start": "09:00", "end": "21:00", "no_sunday": True, "note": "9am-9pm, no Sundays"},
    "TX": {"start": "09:00", "end": "21:00", "sunday": ("12:00", "21:00"), "note": "9am-9pm Mon-Sat, noon-9pm Sunday"},
    "KY": {"start": "10:00", "end": "21:00", "note": "10am-9pm"},
    "UT": {"start": "08:00", "end": "21:00", "no_holiday": True, "note": "8am-9pm, no holidays"},
}
# Recording needs everyone's consent here: the dialer simply does not record calls into these states.
ALL_PARTY_RECORDING = {"CA", "CT", "DE", "FL", "IL", "MD", "MA", "MI", "MT", "NV", "NH", "OR", "PA", "WA"}
FEDERAL_MAX_PER_DAY = 3      # platform cap regardless of state (FL/OK/MD level everywhere)
ABANDON_RATE_LIMIT = 0.03    # TSR: max 3% of live answers abandoned per campaign per 30 days
ABANDON_RATE_THROTTLE = 0.025

STATE_CODES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR", "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "district of columbia": "DC", "washington, dc": "DC", "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID", "illinois": "IL", "indiana": "IN", "iowa": "IA",
    "kansas": "KS", "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD", "massachusetts": "MA", "michigan": "MI", "minnesota": "MN",
    "mississippi": "MS", "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV", "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM",
    "new york": "NY", "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK", "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI",
    "south carolina": "SC", "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT", "vermont": "VT", "virginia": "VA", "washington": "WA",
    "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
}
VALID_STATES = set(STATE_CODES.values())
FALLBACK_TZS = ("America/New_York", "America/Los_Angeles")   # unknown zone: the call must be legal in both


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def e164(phone: str) -> str:
    """+1XXXXXXXXXX for anything that looks like a US/CA number, '' when it cannot be a real number."""
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) == 10 and digits[0] not in "01":
        return f"+1{digits}"
    if (phone or "").strip().startswith("+") and 10 <= len(digits) <= 15:
        return f"+{digits}"
    return ""


def state_code(value: Optional[str]) -> Optional[str]:
    v = (value or "").strip()
    if not v:
        return None
    if len(v) == 2 and v.upper() in VALID_STATES:
        return v.upper()
    return STATE_CODES.get(v.lower())


def region(phone: str, state_hint: Optional[str] = None) -> dict:
    """Where the phone rings: state (contact's own address first, then the area code) + IANA zone (None when ambiguous, e.g. toll free)."""
    out = {"state": state_code(state_hint), "tz": None, "country": "US"}
    try:
        num = phonenumbers.parse(phone, "US")
    except Exception:
        return out
    out["country"] = phonenumbers.region_code_for_number(num) or "US"
    zones = [z for z in pn_tz.time_zones_for_number(num) if z and z != "Etc/Unknown"]
    if len(zones) == 1:
        out["tz"] = zones[0]
    if not out["state"]:
        desc = geocoder.description_for_number(num, "en") or ""
        m = re.search(r",\s*([A-Z]{2})$", desc)
        out["state"] = m.group(1) if m and m.group(1) in VALID_STATES else STATE_CODES.get(desc.strip().lower())
    return out


def us_holidays(year: int) -> set:
    def nth_weekday(month, weekday, n):
        d = date(year, month, 1)
        d += timedelta(days=(weekday - d.weekday()) % 7)
        return d + timedelta(weeks=n - 1)

    def last_weekday(month, weekday):
        d = date(year, month + 1, 1) - timedelta(days=1) if month < 12 else date(year, 12, 31)
        return d - timedelta(days=(d.weekday() - weekday) % 7)

    return {date(year, 1, 1), nth_weekday(1, 0, 3), nth_weekday(2, 0, 3), last_weekday(5, 0), date(year, 6, 19), date(year, 7, 4),
            nth_weekday(9, 0, 1), nth_weekday(10, 0, 2), date(year, 11, 11), nth_weekday(11, 3, 4), date(year, 12, 25)}


def _t(hm: str) -> time:
    h, m = (hm or "00:00").split(":")[:2]
    return time(int(h), int(m))


def window_for(state: Optional[str], d: date) -> Optional[tuple]:
    """(start, end) local times when calls are allowed on that date, None = no calls that day."""
    rule = STATE_RULES.get(state or "", {})
    start, end = _t(rule.get("start", FEDERAL["start"])), _t(rule.get("end", FEDERAL["end"]))
    wd = d.weekday()
    if d in us_holidays(d.year) and rule.get("no_holiday"):
        return None
    if wd == 6:
        if rule.get("no_sunday"):
            return None
        if rule.get("sunday"):
            start, end = _t(rule["sunday"][0]), _t(rule["sunday"][1])
    if wd == 5 and rule.get("saturday"):
        start, end = _t(rule["saturday"][0]), _t(rule["saturday"][1])
    return start, end


def _clamp(window: Optional[tuple], hours: Optional[dict]) -> Optional[tuple]:
    if not window:
        return None
    start, end = window
    if hours:
        start, end = max(start, _t(hours.get("start") or "00:00")), min(end, _t(hours.get("end") or "23:59"))
    return (start, end) if start < end else None


def next_open(state: Optional[str], tz: str, hours: Optional[dict], now: datetime) -> Optional[datetime]:
    """Next UTC instant the window opens in that zone (None when nothing in the next 10 days)."""
    zone = ZoneInfo(tz)
    local = now.astimezone(zone)
    for i in range(0, 11):
        d = (local + timedelta(days=i)).date()
        w = _clamp(window_for(state, d), hours)
        if not w:
            continue
        start = datetime.combine(d, w[0], tzinfo=zone)
        end = datetime.combine(d, w[1], tzinfo=zone)
        if i == 0 and local >= end:
            continue
        return max(start, now).astimezone(timezone.utc) if i == 0 and start <= local < end else start.astimezone(timezone.utc)
    return None


def _open_now(state, tz, hours, now) -> bool:
    local = now.astimezone(ZoneInfo(tz))
    w = _clamp(window_for(state, local.date()), hours)
    return bool(w) and w[0] <= local.time() < w[1]


def max_per_day(state: Optional[str], campaign: dict) -> int:
    cap = int(campaign.get("max_per_day") or FEDERAL_MAX_PER_DAY)
    return max(1, min(cap, STATE_RULES.get(state or "", {}).get("max_per_day", FEDERAL_MAX_PER_DAY), FEDERAL_MAX_PER_DAY))


def check_lead(lead: dict, campaign: dict, now: Optional[datetime] = None, attempts_today: int = 0) -> dict:
    """May this lead be dialed right now? {ok, reason, next_open, local_time, state, tz}."""
    now = now or now_utc()
    state, tz = lead.get("state"), lead.get("tz")
    out = {"ok": False, "reason": "", "next_open": None, "local_time": None, "state": state, "tz": tz}
    if tz:
        out["local_time"] = now.astimezone(ZoneInfo(tz)).strftime("%-I:%M %p")
    dnc = (lead.get("dnc") or {}).get("status")
    if lead.get("status") == "dnc" or dnc == "internal" or (dnc == "registry" and not registry_ok(campaign)):
        out["reason"] = "dnc"
        return out
    if int(lead.get("attempts") or 0) >= int(campaign.get("max_attempts") or 3):
        out["reason"] = "max_attempts"
        return out
    zones = [tz] if tz else list(FALLBACK_TZS)
    hours = campaign.get("hours") or None
    if not all(_open_now(state, z, hours, now) for z in zones):
        opens = [o for o in (next_open(state, z, hours, now) for z in zones) if o]
        out["reason"], out["next_open"] = "outside_window", (max(opens) if opens else None)
        return out
    if attempts_today >= max_per_day(state, campaign):
        out["reason"], out["next_open"] = "daily_cap", now + timedelta(hours=24)
        return out
    out["ok"] = True
    return out


def registry_ok(campaign: dict) -> bool:
    """National DNC hits may only be dialed on a B2B campaign where the manager switched that on explicitly."""
    return campaign.get("audience") == "b2b" and bool(campaign.get("allow_registry_b2b"))


def recording_allowed(state: Optional[str], campaign: dict) -> bool:
    return campaign.get("recording") == "on" and bool(state) and state not in ALL_PARTY_RECORDING


def throttle_lines(lines: int, answered_live: int, abandoned: int) -> int:
    """Drop to a single line as soon as the 30-day abandonment rate gets near the TSR 3% ceiling."""
    lines = max(1, min(int(lines or 1), 3))
    if abandoned <= 0:
        return lines
    if answered_live < 10 or abandoned / max(answered_live, 1) >= ABANDON_RATE_THROTTLE:
        return 1
    return lines


def abandon_message(seller_name: str, callback_number: str) -> str:
    from services.speech import speakable
    num = speakable(callback_number or "")
    return (f"Hello. This was a call from {seller_name} at {num}. We are sorry, our representative is helping another customer right now. "
            f"You can reach us at {num}. To be placed on our do not call list, press 9.")


# ── Do Not Call ───────────────────────────────────────────────────────────────
def _ten(phone: str) -> str:
    d = re.sub(r"\D", "", phone or "")
    return d[1:] if len(d) == 11 and d.startswith("1") else d


async def is_internal_dnc(db, phone: str) -> bool:
    p = e164(phone)
    return bool(p) and await db[DNC_LIST].find_one({"phone": p}, {"_id": 1}) is not None


async def is_registry_dnc(db, phone: str) -> bool:
    n = _ten(phone)
    return len(n) == 10 and await db[DNC_REGISTRY].find_one({"n": n}, {"_id": 1}) is not None


async def registry_loaded(db) -> bool:
    return await db[DNC_REGISTRY].find_one({}, {"_id": 1}) is not None


async def dnc_status(db, phone: str, campaign: Optional[dict] = None) -> dict:
    """{status: internal|registry|clear|unscrubbed, blocked, checked_at}."""
    checked = now_utc()
    if await is_internal_dnc(db, phone):
        return {"status": "internal", "blocked": True, "checked_at": checked}
    if await is_registry_dnc(db, phone):
        return {"status": "registry", "blocked": not registry_ok(campaign or {}), "checked_at": checked}
    if not await registry_loaded(db):
        return {"status": "unscrubbed", "blocked": False, "checked_at": checked}
    return {"status": "clear", "blocked": False, "checked_at": checked}


async def add_dnc(db, phone: str, source: str, by: Optional[str] = None, campaign_id: Optional[str] = None, note: str = "") -> bool:
    p = e164(phone)
    if not p:
        return False
    res = await db[DNC_LIST].update_one({"phone": p}, {"$setOnInsert": {"phone": p, "source": source, "added_at": now_utc(), "added_by": by, "campaign_id": campaign_id, "note": (note or "")[:200]}}, upsert=True)
    if res.upserted_id:
        await db.contacts.update_many({"phone": p}, {"$set": {"do_not_call": True, "do_not_call_at": now_utc(), "do_not_call_source": source}})
        await db["dialer_leads"].update_many({"phone": p, "status": {"$nin": ["done"]}}, {"$set": {"status": "dnc", "dnc": {"status": "internal", "blocked": True, "checked_at": now_utc()}, "last_outcome": "dnc"}})
    return bool(res.upserted_id)


def parse_registry_lines(text: str) -> list:
    """FTC download format: `305,5551234` per line (change files add a date column). Returns 10-digit strings."""
    out = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = re.split(r"[,\s;|]+", line)
        if len(parts) >= 2 and re.fullmatch(r"\d{3}", parts[0]) and re.fullmatch(r"\d{7}", parts[1]):
            out.append(parts[0] + parts[1])
            continue
        n = _ten(parts[0])
        if len(n) == 10:
            out.append(n)
    return out


async def import_registry(db, text: str, by: Optional[str] = None) -> dict:
    from pymongo import UpdateOne
    numbers = parse_registry_lines(text)
    added = 0
    for i in range(0, len(numbers), 5000):
        chunk = numbers[i:i + 5000]
        ops = [UpdateOne({"n": n}, {"$setOnInsert": {"n": n, "area": n[:3], "imported_at": now_utc()}}, upsert=True) for n in chunk]
        res = await db[DNC_REGISTRY].bulk_write(ops, ordered=False)
        added += res.upserted_count
    areas = sorted({n[:3] for n in numbers})
    if numbers:
        await db.settings.update_one({"key": REGISTRY_META}, {"$set": {"value.last_import_at": now_utc(), "value.last_import_by": by}, **({"$addToSet": {"value.areas": {"$each": areas}}} if areas else {})}, upsert=True)
    return {"lines": len(numbers), "added": added, "areas": areas}


async def registry_stats(db) -> dict:
    meta = ((await db.settings.find_one({"key": REGISTRY_META})) or {}).get("value") or {}
    count = await db[DNC_REGISTRY].estimated_document_count()
    last = meta.get("last_import_at")
    stale = bool(last) and (now_utc() - last.replace(tzinfo=timezone.utc) if last.tzinfo is None else now_utc() - last) > timedelta(days=31)
    return {"numbers": count, "areas": sorted(meta.get("areas") or []), "last_import_at": last.isoformat() if last else None, "stale": stale}


def rules_table() -> list:
    rows = [{"state": "US", "label": "Federal (TCPA / TSR)", "hours": "8:00 AM - 9:00 PM local time", "note": f"Max {FEDERAL_MAX_PER_DAY} calls per 24h on this platform. National DNC scrub, internal DNC honored forever, abandonment under 3%."}]
    for st, r in sorted(STATE_RULES.items()):
        rows.append({"state": st, "label": st, "hours": f"{_fmt(r['start'])} - {_fmt(r['end'])}", "note": r.get("note", "")})
    return rows


def _fmt(hm: str) -> str:
    t = _t(hm)
    return t.strftime("%-I:%M %p").replace(":00", "")
