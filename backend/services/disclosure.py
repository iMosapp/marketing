"""Opt-out disclosure tracking: the first text from a sender to a contact identifies the business and says how to opt out; later
conversational texts stay natural. Reminders and marketing rules come from configuration (per messaging program, per
jurisdiction, per organization), never from one hard-coded frequency. Disclosure history (`sms_disclosure_events`) is kept
apart from consent: sending an opt-out notice never counts as consent."""
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

STATE = "sms_disclosure_state"
EVENTS = "sms_disclosure_events"
VERSION = "2026-06-v1"
PROGRAM_OF = {"conversational": "standard", "requested_info": "standard", "transactional": "standard", "marketing": "marketing", "system": "system"}
DEFAULT_POLICY = {
    "version": VERSION,
    # reminder_every_messages / reminder_every_days: None = no periodic reminder unless a program, jurisdiction or organization sets one
    "programs": {
        "standard": {"first_message": True, "every_message": False, "reminder_every_messages": None, "reminder_every_days": None},
        "marketing": {"first_message": True, "every_message": True, "reminder_every_messages": None, "reminder_every_days": None},
        "system": {"first_message": False, "every_message": False, "reminder_every_messages": None, "reminder_every_days": None},
    },
    "jurisdictions": {},
    "templates": {
        "standard": "{business}: Reply STOP to opt out.",
        "marketing": "{business}: Msg & data rates may apply. Reply HELP for help, STOP to opt out.",
        "system": "{business}: Reply STOP to opt out.",
    },
}
_STOP_TEXT = re.compile(r"\b(reply|text)\s+stop\b|\bstop\s+to\s+(opt|unsub|end|cancel)", re.I)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _merge(base: dict, over: Optional[dict]) -> dict:
    out = dict(base)
    for k, v in (over or {}).items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


async def effective_policy(db, org: Optional[dict] = None) -> dict:
    doc = await db.settings.find_one({"key": "disclosure_policy"}, {"_id": 0, "key": 0}) or {}
    pol = _merge(DEFAULT_POLICY, doc)
    return _merge(pol, (org or {}).get("messaging_disclosure"))


def _jurisdiction(phone: str) -> list:
    from services.compliance import region
    r = region(phone)
    return [k for k in (r.get("country"), f"{r.get('country')}-{r.get('state')}" if r.get("state") else None) if k]


def program_id(purpose: str, from_number: Optional[str], campaign_key: Optional[str]) -> str:
    if PROGRAM_OF.get(purpose) == "marketing":
        return f"marketing:{campaign_key or 'general'}"
    return f"sender:{from_number or 'platform'}"


async def plan(db, *, org: Optional[dict], purpose: str, from_number: Optional[str], phone: str, body: str,
               campaign_key: Optional[str] = None, business: str = "") -> dict:
    """What to append (if anything) so this text meets the disclosure rules. Never removes text the sender wrote."""
    category = PROGRAM_OF.get(purpose, "standard")
    pol = await effective_policy(db, org)
    rules = dict(pol["programs"].get(category) or DEFAULT_POLICY["programs"]["standard"])
    if pol.get("jurisdictions"):
        for j in _jurisdiction(phone):
            rules = _merge(rules, ((pol["jurisdictions"].get(j) or {}).get("programs") or {}).get(category))
    pid = program_id(purpose, from_number, campaign_key)
    org_id = str(org["_id"]) if org else "platform"
    sid = f"{org_id}:{pid}:{phone}"
    st = await db[STATE].find_one({"_id": sid}) or {}
    reason = None
    if not st.get("first_at"):
        reason = "first_message" if rules.get("first_message") else None
    elif rules.get("every_message"):
        reason = "every_message"
    elif rules.get("reminder_every_messages") and int(st.get("since_last") or 0) >= int(rules["reminder_every_messages"]):
        reason = "reminder_count"
    elif rules.get("reminder_every_days"):
        last = st.get("last_at")
        last = last.replace(tzinfo=timezone.utc) if isinstance(last, datetime) and last.tzinfo is None else last
        if isinstance(last, datetime) and _now() - last >= timedelta(days=float(rules["reminder_every_days"])):
            reason = "reminder_days"
    already = bool(_STOP_TEXT.search(body or ""))
    text = None
    if reason and not already:
        tpl = (pol.get("templates") or {}).get(category) or DEFAULT_POLICY["templates"]["standard"]
        text = tpl.format(business=(business or (org or {}).get("name") or "I'm On Social").strip())
    return {"state_id": sid, "org_id": org_id, "program": pid, "category": category, "reason": reason, "append": text,
            "included": bool(reason) or already, "already_in_body": already, "version": pol.get("version") or VERSION}


def apply(body: str, p: dict) -> str:
    return f"{body.rstrip()}\n\n{p['append']}" if p.get("append") else body


async def record(db, p: dict, *, phone: str, contact_id: Optional[str], message_sid: Optional[str], text: str) -> None:
    """After a successful send: a disclosure resets the counter and is logged; any other text counts toward the next reminder."""
    now = _now()
    try:
        if p.get("included"):
            await db[STATE].update_one({"_id": p["state_id"]}, {
                "$set": {"org_id": p["org_id"], "program": p["program"], "phone": phone, "last_at": now, "last_version": p["version"], "last_message_sid": message_sid,
                         "last_delivery_status": "accepted", "since_last": 0},
                "$setOnInsert": {"first_at": now}, "$inc": {"total": 1, "disclosures": 1}}, upsert=True)
            await db[EVENTS].insert_one({"state_id": p["state_id"], "org_id": p["org_id"], "program": p["program"], "phone": phone, "contact_id": contact_id,
                                         "reason": p.get("reason") or "in_body", "version": p["version"], "text": p.get("append") or "(sender's own wording)",
                                         "message_sid": message_sid, "delivery_status": "accepted", "at": now, "message_excerpt": (text or "")[-200:]})
        else:
            await db[STATE].update_one({"_id": p["state_id"]}, {"$set": {"org_id": p["org_id"], "program": p["program"], "phone": phone},
                                                                "$inc": {"total": 1, "since_last": 1}}, upsert=True)
    except Exception as e:
        logger.warning(f"[Disclosure] record failed: {e}")


async def on_status(db, message_sid: str, status: str) -> None:
    """Delivery receipt for a text that carried a disclosure."""
    if not message_sid:
        return
    r = await db[EVENTS].update_one({"message_sid": message_sid}, {"$set": {"delivery_status": status, "delivery_at": _now()}})
    if r.modified_count:
        await db[STATE].update_one({"last_message_sid": message_sid}, {"$set": {"last_delivery_status": status}})


async def status_for(db, org_id: str, phone: str) -> list:
    rows = await db[STATE].find({"org_id": str(org_id), "phone": phone}, {"_id": 0}).to_list(50)
    for r in rows:
        for k in ("first_at", "last_at"):
            if isinstance(r.get(k), datetime):
                r[k] = r[k].isoformat()
    return rows
