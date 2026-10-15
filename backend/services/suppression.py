"""Opt-out (STOP) and customer-driven re-enrollment (START), checked before every outbound text in every SENDER_POLICY_MODE.
Scope: an opt-out sent to any number of an organization stops that organization's texts to the phone; one sent to an I'm On Social
platform number stops platform texts. `sms_suppressions` holds the current state, `sms_optout_events` the audit history.
Legacy contact flags (opted_out / sms_opt_out) written before this module are honored too. Receiving an opt-out never creates
consent, and only the contact's own START (or YES / UNSTOP) lifts it: no team member can override it."""
import logging
import os
import re
import time
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

COLL = "sms_suppressions"
EVENTS = "sms_optout_events"
STOP_WORDS = {"STOP", "STOPALL", "UNSUBSCRIBE", "CANCEL", "END", "QUIT", "OPTOUT", "OPT OUT", "OPT-OUT", "REVOKE"}
START_WORDS = {"START", "UNSTOP", "SUBSCRIBE", "YES"}
HELP_WORDS = {"HELP", "INFO"}
PLATFORM = "platform"
_NL_STOP = re.compile(r"\b(stop|quit|cease)\s+(texting|messaging|contacting|sending)\b|\bunsubscribe\s+me\b|\bremove\s+me\s+from\b|"
                      r"\bdo\s+not\s+(text|message|contact)\s+me\b|\bdon'?t\s+(text|message|contact)\s+me\b|\bno\s+more\s+(texts|messages)\b|"
                      r"\btake\s+me\s+off\b", re.I)
_users_cache: dict = {}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def classify(body: str) -> Optional[str]:
    """'stop' | 'start' | 'help' for the carrier keywords (whole message), 'stop_request' for a plain-language opt-out."""
    b = re.sub(r"[\s.!]+$", "", (body or "").strip()).upper()
    if b in STOP_WORDS:
        return "stop"
    if b in START_WORDS:
        return "start"
    if b in HELP_WORDS:
        return "help"
    if len(body or "") <= 160 and _NL_STOP.search(body or ""):
        return "stop_request"
    return None


def scope_key(org_id: Optional[str]) -> str:
    return f"org:{org_id}" if org_id else PLATFORM


async def scope_for_number(db, number: str) -> Optional[str]:
    """The organization that owns a texting number (registry first, then a user's legacy number); None = platform."""
    from services import phone_numbers as pn
    from services.twilio_service import normalize_phone
    n = normalize_phone(number or "") if number else ""
    if not n:
        return None
    num = await pn.by_phone(db, n)
    if num and num.get("organization_id"):
        return str(num["organization_id"])
    u = await db.users.find_one({"$or": [{"twilio_number": n}, {"mvpline_number": n}]}, {"organization_id": 1})
    if u and u.get("organization_id"):
        return str(u["organization_id"])
    from services.inboxes import inbox_by_number
    inbox = await inbox_by_number(db, n)
    return str(inbox["organization_id"]) if inbox and inbox.get("organization_id") else None


async def _org_user_ids(db, org_id: str) -> list:
    hit = _users_cache.get(org_id)
    if hit and hit[1] > time.monotonic():
        return hit[0]
    ids = [str(u["_id"]) async for u in db.users.find({"organization_id": str(org_id)}, {"_id": 1})]
    _users_cache[org_id] = (ids, time.monotonic() + 60)
    return ids


async def _sync_contacts(db, org_id: Optional[str], phone: str, opted_out: bool) -> int:
    from services.contact_match import phone_clause
    pc = phone_clause(phone)
    if not org_id or not pc:
        return 0
    uids = await _org_user_ids(db, org_id)
    if not uids:
        return 0
    now = datetime.utcnow()
    sets = ({"opted_out": True, "opted_out_at": now, "sms_consent_status": "opted_out", "sms_opt_out": True, "sms_opt_out_at": now} if opted_out
            else {"opted_out": False, "opted_out_at": None, "sms_consent_status": "opted_in", "sms_opt_out": False})
    r = await db.contacts.update_many({"user_id": {"$in": uids}, **pc}, {"$set": sets})
    return r.modified_count


async def _event(db, action: str, phone: str, org_id: Optional[str], source: str, keyword: str, to_number: str, message_sid: str, body: str = ""):
    await db[EVENTS].insert_one({"phone": phone, "org_id": org_id, "scope": scope_key(org_id), "action": action, "source": source, "keyword": keyword,
                                 "to_number": to_number or None, "message_sid": message_sid or None, "body_excerpt": (body or "")[:80], "at": _now()})


async def opt_out(db, phone: str, org_id: Optional[str], *, source: str, keyword: str = "", to_number: str = "", message_sid: str = "", body: str = "") -> None:
    from services.consent import e164
    phone = e164(phone)
    if not phone:
        return
    key = scope_key(org_id)
    now = _now()
    await db[COLL].update_one({"_id": f"{key}:{phone}"}, {"$set": {"phone": phone, "org_id": org_id, "scope": key, "active": True, "since": now, "source": source,
                                                                   "keyword": keyword, "to_number": to_number or None, "message_sid": message_sid or None},
                                                          "$inc": {"opt_outs": 1}}, upsert=True)
    await _event(db, "opt_out", phone, org_id, source, keyword, to_number, message_sid, body)
    n = await _sync_contacts(db, org_id, phone, True)
    logger.info(f"[Suppression] {phone[-4:]} opted out of {key} ({source} {keyword}); {n} contact(s) flagged")


async def opt_in(db, phone: str, org_id: Optional[str], *, keyword: str, to_number: str = "", message_sid: str = "") -> bool:
    """Customer-driven re-enrollment only: called from the inbound webhook when the contact texts START / YES / UNSTOP."""
    from services.consent import e164
    phone = e164(phone)
    key = scope_key(org_id)
    r = await db[COLL].update_one({"_id": f"{key}:{phone}", "active": True}, {"$set": {"active": False, "resubscribed_at": _now(), "resubscribe_keyword": keyword}})
    legacy = await _sync_contacts(db, org_id, phone, False)
    if r.modified_count or legacy:
        await _event(db, "opt_in", phone, org_id, "keyword", keyword, to_number, message_sid)
    return bool(r.modified_count or legacy)


async def active(db, phone: str, org_id: Optional[str], platform: bool = False) -> Optional[dict]:
    """The opt-out that blocks this send, or None. Checks the organization scope (plus platform scope for platform sends) and legacy contact flags."""
    from services.consent import e164
    from services.contact_match import phone_clause
    phone = e164(phone)
    if not phone:
        return None
    if org_id and str(org_id).startswith("user:"):
        org_id = None  # an individual account's numbers are platform-scoped for opt-outs (scope_for_number)
    keys = ([f"{scope_key(org_id)}:{phone}"] if org_id else []) + ([f"{PLATFORM}:{phone}"] if platform or not org_id else [])
    doc = await db[COLL].find_one({"_id": {"$in": keys}, "active": True})
    if doc:
        return {"scope": doc["scope"], "since": doc.get("since"), "source": doc.get("source")}
    if org_id:
        uids = await _org_user_ids(db, org_id)
        pc = phone_clause(phone)
        if uids and pc:
            c = await db.contacts.find_one({"user_id": {"$in": uids}, **pc, "$or": [{"opted_out": True}, {"sms_opt_out": True}]}, {"_id": 1})
            if c:
                return {"scope": scope_key(org_id), "since": None, "source": "legacy_contact_flag"}
    return None


async def on_inbound(db, *, from_phone: str, to_phone: str, body: str, message_sid: str) -> Optional[str]:
    """Central keyword handling for every inbound route (rep numbers, shared inboxes, platform). Returns the classification."""
    kind = classify(body)
    if kind not in ("stop", "start", "stop_request"):
        return kind
    org_id = await scope_for_number(db, to_phone)
    if kind == "start":
        await opt_in(db, from_phone, org_id, keyword=(body or "").strip().upper()[:20], to_number=to_phone, message_sid=message_sid)
    else:
        await opt_out(db, from_phone, org_id, source="keyword" if kind == "stop" else "plain_language", keyword=(body or "").strip().upper()[:20] if kind == "stop" else "",
                      to_number=to_phone, message_sid=message_sid, body=body)
    return kind


async def on_provider_error(db, *, to_phone: str, from_phone: Optional[str], error_code) -> None:
    """Twilio 21610 = the recipient replied STOP to this sender at the provider: mirror it in the app."""
    if str(error_code) != "21610":
        return
    org_id = await scope_for_number(db, from_phone) if from_phone else None
    await opt_out(db, to_phone, org_id, source="provider_21610", to_number=from_phone or os.environ.get("TWILIO_PHONE_NUMBER", ""))


async def history(db, phone: str, org_id: Optional[str], limit: int = 50) -> list:
    from services.consent import e164
    rows = await db[EVENTS].find({"phone": e164(phone), "scope": {"$in": [scope_key(org_id), PLATFORM]}}, {"_id": 0}).sort("at", -1).to_list(limit)
    for r in rows:
        if isinstance(r.get("at"), datetime):
            r["at"] = r["at"].isoformat()
    return rows
