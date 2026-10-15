"""Dealership outbound-texting guard: one decision for every outbound SMS/MMS before it reaches Twilio.

Every organization except IMOS's own (the OWNER_EMAIL account's org, or an org explicitly marked `internal: true`) is treated as a
dealership: unknown means dealership, so nothing slips through as "internal" by accident. Its texts may only leave from a
number in the tenant registry, assigned to the sender, owned by the dealership's real Twilio subaccount, attached to the
dealership's own approved A2P Messaging Service. Anything uncertain fails closed. IMOS platform notifications (activation codes,
invites, founder alerts) are sent with `platform=True` on IMOS's own registration. The kill switch only ever pauses dealership
texting; it can never let unregistered dealership traffic through."""
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId

logger = logging.getLogger(__name__)

LOG = "sms_send_log"
PAUSE_KEY = "pause_dealership_texting"

REASONS = {
    "paused": "Texting is paused for business accounts right now. Inbound texts still arrive.",
    "no_number": "No texting number is assigned to you yet. Ask your manager to set one up.",
    "unregistered_number": "This number is not registered to your organization in I'm On Social, so it cannot text.",
    "wrong_org": "This number belongs to a different organization, so it cannot text for you.",
    "not_your_number": "This number is assigned to someone else on your team.",
    "no_subaccount": "Your organization's texting account is not set up yet, so texting is not available.",
    "wrong_account": "This number is not in your organization's texting account, so it cannot text.",
    "not_ready": "Texting is not active yet: your organization's texting registration (A2P 10DLC) is still pending approval.",
    "not_associated": "This number is not attached to your organization's approved texting registration yet.",
    "unknown_sender": "We could not confirm who owns this sending number, so the text was not sent.",
    "unattributed": "We could not confirm who is sending this text, so it was not sent.",
}


_internal_cache: dict = {}


async def internal_org_ids(db) -> set:
    """IMOS's own organization(s): the owner's org plus any org flagged `internal: true` (cached per process for 5 minutes)."""
    now = datetime.now(timezone.utc).timestamp()
    if _internal_cache.get("at", 0) > now - 300:
        return _internal_cache["ids"]
    ids = set()
    owner = (os.environ.get("OWNER_EMAIL") or "").strip().lower()
    if owner:
        u = await db.users.find_one({"email": owner}, {"organization_id": 1})
        if u and u.get("organization_id"):
            ids.add(str(u["organization_id"]))
    async for o in db.organizations.find({"internal": True}, {"_id": 1}):
        ids.add(str(o["_id"]))
    _internal_cache.update(at=now, ids=ids)
    return ids


def _real_subaccount(sid: str, parent_sid: str) -> bool:
    return bool(sid) and sid.startswith("AC") and not sid.startswith("ACdry") and sid != parent_sid


def decide(*, platform: bool, paused: bool, org: Optional[dict], internal_org: bool, number: Optional[dict], user_id: Optional[str],
           from_phone: Optional[str], internal_number: bool, parent_sid: str) -> tuple[bool, str]:
    """Pure decision: (allowed, code). `org` is the sender's organization (None = could not be resolved)."""
    if platform and not from_phone:
        return True, "platform"
    if org is None:
        if from_phone and internal_number:
            return True, "internal"
        return False, ("unknown_sender" if from_phone else "unattributed")
    if internal_org:
        return True, "internal"
    if paused:
        return False, "paused"
    if not from_phone:
        return False, "no_number"
    if not number or number.get("status") == "RELEASED":
        return False, "unregistered_number"
    oid = str(org.get("_id"))
    if str(number.get("organization_id") or "") != oid:
        return False, "wrong_org"
    if (number.get("number_type") or "USER") == "USER" and user_id and str(number.get("assigned_user_id") or "") != str(user_id):
        return False, "not_your_number"
    t = org.get("twilio") or {}
    if not _real_subaccount(t.get("subaccount_sid") or "", parent_sid):
        return False, "no_subaccount"
    if (number.get("twilio_account_sid") or "") != t["subaccount_sid"]:
        return False, "wrong_account"
    if not t.get("messaging_ready"):
        return False, "not_ready"
    ms = t.get("messaging_service_sid") or ""
    if not ms or (number.get("messaging_service_sid") or "") != ms:
        return False, "not_associated"
    return True, "dealership_ready"


async def _org(db, org_id) -> Optional[dict]:
    if org_id and ObjectId.is_valid(str(org_id)):
        return await db.organizations.find_one({"_id": ObjectId(str(org_id))})
    return None


async def check(db, *, from_phone: Optional[str], user_id: Optional[str] = None, org_id: Optional[str] = None,
                platform: bool = False) -> dict:
    """Resolve sender, organization and number, then decide. Returns {allowed, code, reason, org_id, user_id, number}."""
    from services import phone_numbers as pn
    number = await pn.by_phone(db, from_phone, include_released=True) if from_phone else None
    user = None
    if user_id and ObjectId.is_valid(str(user_id)):
        user = await db.users.find_one({"_id": ObjectId(str(user_id))}, {"organization_id": 1})
    if not user and number and number.get("assigned_user_id") and ObjectId.is_valid(number["assigned_user_id"]):
        user = await db.users.find_one({"_id": ObjectId(number["assigned_user_id"])}, {"organization_id": 1})
    if not user and from_phone:
        user = await db.users.find_one({"$or": [{"twilio_number": from_phone}, {"mvpline_number": from_phone}]}, {"organization_id": 1})
    org = await _org(db, (user or {}).get("organization_id") or (number or {}).get("organization_id") or org_id)
    internal = False
    if from_phone and org is None:
        internal = from_phone == (os.environ.get("TWILIO_PHONE_NUMBER") or "") or \
            await db.phone_number_pool.find_one({"phone_number": from_phone}, {"_id": 1}) is not None
    internal_org = bool(org) and str(org["_id"]) in await internal_org_ids(db)
    flags = await db.settings.find_one({"key": "twilio_compliance"}, {PAUSE_KEY: 1}) or {}
    allowed, code = decide(platform=platform, paused=bool(flags.get(PAUSE_KEY)), org=org, internal_org=internal_org, number=number,
                           user_id=str(user["_id"]) if user else user_id, from_phone=from_phone, internal_number=internal,
                           parent_sid=os.environ.get("TWILIO_ACCOUNT_SID") or "")
    return {"allowed": allowed, "code": code, "reason": "" if allowed else REASONS[code],
            "org_id": str(org["_id"]) if org else None, "user_id": str(user["_id"]) if user else user_id,
            "dealership": bool(org) and not internal_org, "number": number}


async def log_attempt(db, decision: dict, *, to_phone: str, from_phone: Optional[str], account_sid: Optional[str],
                      messaging_service_sid: Optional[str], platform: bool, result: Optional[dict]) -> None:
    """Audit trail for every outbound attempt: the real sender number, account and registration used (or why it was refused)."""
    try:
        await db[LOG].insert_one({
            "at": datetime.now(timezone.utc), "to": to_phone, "from_number": from_phone or None, "account_sid": account_sid or None,
            "messaging_service_sid": messaging_service_sid or None, "platform": platform, "org_id": decision.get("org_id"),
            "user_id": decision.get("user_id"), "dealership": decision.get("dealership"), "allowed": decision.get("allowed"),
            "code": decision.get("code"), "message_sid": (result or {}).get("message_sid"), "success": (result or {}).get("success"),
            "error_code": (result or {}).get("error_code")})
    except Exception as e:
        logger.warning(f"[SenderPolicy] log failed: {e}")
