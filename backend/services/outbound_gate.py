"""The one decision every outbound SMS/MMS passes before the provider (called from services.twilio_service.send_sms).
Order: billing lock -> STOP/opt-out -> consent for the message purpose -> sender registration/ownership (sender_policy).
STOP, billing lock and consent/recipient rules are enforced in every mode. SENDER_POLICY_MODE=shadow only lets
sender-registration/ownership refusals through (logged as would-block) during rollout; unset or anything else = enforce.
CONSENT_MODE=shadow does the same for missing consent; unset = enforce.

Purposes: conversational (a team member's 1:1 text), requested_info, transactional, marketing, and system (never to a contact;
each system kind is listed below with who may receive it)."""
import logging
import os
from typing import Optional

from bson import ObjectId

logger = logging.getLogger(__name__)

PURPOSES = ("conversational", "requested_info", "transactional", "marketing", "system")
SYSTEM_KINDS = {
    "otp": {"recipient": "requester", "when_locked": True, "desc": "A sign-in or verification code the person just requested"},
    "account_invite": {"recipient": "invitee", "desc": "Invite or activation link for a person an admin just added to the account"},
    "account_setup": {"recipient": "invitee", "desc": "Texting-registration onboarding steps sent to the business's own contact person"},
    "team_alert": {"recipient": "team_member", "desc": "An alert or digest to a team member's own phone"},
    "billing_owner": {"recipient": "team_member", "when_locked": True, "desc": "Payment link to the account owner"},
    "platform_test": {"recipient": "team_member", "desc": "A super admin's test text"},
    "client_staff": {"recipient": "client_staff", "desc": "Training / mystery-shop texts to staff a business client listed"},
}
REASONS = {
    "billing_locked": "Texting is paused because this organization's subscription needs attention. Inbound texts are still saved.",
    "opted_out": "This contact texted STOP, so they can't receive texts from your organization. Only they can turn texts back on, by texting START.",
    "consent_required": "This contact has no recorded consent for this kind of message yet. Record their consent to send.",
    "marketing_consent_required": "Marketing texts need the contact's written or digital opt-in first.",
    "not_team_member": "This system text can only go to a member of the team.",
    "not_client_staff": "This text can only go to staff listed by the business client.",
    "unclassified_system": "This system text has no approved category, so it was not sent.",
    "bad_purpose": "This text has no approved purpose, so it was not sent.",
}


def sender_mode() -> str:
    return "shadow" if (os.environ.get("SENDER_POLICY_MODE") or "").strip().lower() == "shadow" else "enforce"


def consent_mode() -> str:
    return "shadow" if (os.environ.get("CONSENT_MODE") or "").strip().lower() == "shadow" else "enforce"


async def _recipient_ok(db, kind: str, phone: str, org_id: Optional[str]) -> bool:
    from services.contact_match import phone_clause
    who = SYSTEM_KINDS[kind]["recipient"]
    if who in ("requester", "invitee"):
        return True
    pc = phone_clause(phone)
    if not pc:
        return False
    if who == "team_member":
        return await db.users.find_one({**pc, "status": {"$ne": "deactivated"}}, {"_id": 1}) is not None
    if who == "client_staff":
        return (await db.shop_targets.find_one(pc, {"_id": 1}) is not None
                or await db.roleplay_sessions.find_one(phone_clause(phone, "rep_phone"), {"_id": 1}) is not None)
    return False


async def evaluate(db, *, to_phone: str, from_phone: Optional[str], purpose: Optional[str], system_kind: Optional[str] = None,
                   user_id: Optional[str] = None, org_id: Optional[str] = None, contact_id: Optional[str] = None) -> dict:
    """{allowed, code, reason, shadow, org_id, user_id, location_id, purpose, basis, needs, policy}"""
    from services import billing_lock, consent, sender_policy, suppression
    purpose = purpose or "conversational"
    if purpose not in PURPOSES:
        return {"allowed": False, "code": "bad_purpose", "reason": REASONS["bad_purpose"], "purpose": purpose, "shadow": []}
    platform = purpose == "system"
    if platform and system_kind not in SYSTEM_KINDS:
        return {"allowed": False, "code": "unclassified_system", "reason": REASONS["unclassified_system"], "purpose": purpose, "shadow": []}
    pol = await sender_policy.check(db, from_phone=from_phone, user_id=user_id, org_id=org_id, platform=platform)
    org = pol.get("org_id") or org_id
    out = {"allowed": True, "code": "ok", "reason": "", "shadow": [], "org_id": org, "user_id": pol.get("user_id"), "purpose": purpose,
           "system_kind": system_kind, "policy": pol, "basis": None, "needs": [], "location_id": None}
    uid = pol.get("user_id")
    if uid and ObjectId.is_valid(str(uid)):
        u = await db.users.find_one({"_id": ObjectId(str(uid))}, {"store_id": 1})
        out["location_id"] = str(u["store_id"]) if u and u.get("store_id") else None

    def block(code: str, reason: str = "", **extra) -> dict:
        return {**out, "allowed": False, "code": code, "reason": reason or REASONS.get(code, code), **extra}

    if org and not (platform and SYSTEM_KINDS[system_kind].get("when_locked")):
        lock = await billing_lock.org_state(db, org)
        if lock["locked"]:
            return block("billing_locked")
    platform_sender = platform and not from_phone
    hit = await suppression.active(db, to_phone, None if platform_sender else org, platform=platform_sender)
    if hit:
        return block("opted_out", suppression=hit)
    if platform:
        if not await _recipient_ok(db, system_kind, to_phone, org):
            code = "not_client_staff" if SYSTEM_KINDS[system_kind]["recipient"] == "client_staff" else "not_team_member"
            if consent_mode() == "enforce":
                return block(code)
            out["shadow"].append(code)
        out["basis"] = f"system:{system_kind}"
    else:
        el = await consent.eligible(db, org or consent.solo_scope(uid), to_phone, purpose)
        out["basis"], out["needs"] = el["basis"], el["needs"]
        if not el["ok"]:
            code = "marketing_consent_required" if purpose == "marketing" else "consent_required"
            if consent_mode() == "enforce":
                return block(code, needs=el["needs"])
            out["shadow"].append(code)
    if not pol["allowed"]:
        if sender_mode() == "enforce":
            return block(pol["code"], pol["reason"])
        out["shadow"].append(pol["code"])
    return out


async def log(db, d: dict, *, to_phone: str, from_phone: Optional[str], account_sid: Optional[str] = None, messaging_service_sid: Optional[str] = None,
              result: Optional[dict] = None, disclosure: Optional[dict] = None) -> None:
    try:
        from datetime import datetime, timezone
        await db.sms_send_log.insert_one({
            "at": datetime.now(timezone.utc), "to": to_phone, "from_number": from_phone or None, "account_sid": account_sid, "messaging_service_sid": messaging_service_sid,
            "purpose": d.get("purpose"), "system_kind": d.get("system_kind"), "org_id": d.get("org_id"), "user_id": d.get("user_id"),
            "location_id": d.get("location_id"), "allowed": d.get("allowed"), "code": d.get("code"), "basis": d.get("basis"),
            "policy_code": (d.get("policy") or {}).get("code"), "shadow_would_block": d.get("shadow") or [], "sender_mode": sender_mode(), "consent_mode": consent_mode(),
            "disclosure": (disclosure or {}).get("reason"), "message_sid": (result or {}).get("message_sid"), "success": (result or {}).get("success"),
            "error_code": (result or {}).get("error_code")})
    except Exception as e:
        logger.warning(f"[OutboundGate] log failed: {e}")


def refusal(d: dict) -> dict:
    """The send_sms result for a refused text: callers see success False plus a code the app can act on."""
    return {"success": False, "blocked": True, "error": d.get("reason") or d.get("code"), "error_code": d.get("code"), "needs": d.get("needs") or [],
            "mock": False}


async def preflight_or_raise(db, *, to_phone: str, from_phone: Optional[str], purpose: str, user_id: Optional[str], contact_id: Optional[str] = None) -> dict:
    """Manual sends from the app: refuse before anything is saved, with a structured 409 the composer turns into the consent sheet."""
    from fastapi import HTTPException
    from services.twilio_service import normalize_phone
    d = await evaluate(db, to_phone=normalize_phone(to_phone), from_phone=normalize_phone(from_phone) if from_phone else None, purpose=purpose,
                       user_id=user_id, contact_id=contact_id)
    if not d["allowed"]:
        raise HTTPException(status_code=409, detail={"code": d["code"], "message": d["reason"], "needs": d.get("needs") or [], "purpose": purpose,
                                                     "contact_id": contact_id, "phone": normalize_phone(to_phone)})
    return d



async def stop_or_raise(db, *, to_phone: str, user_id: str, contact_id: Optional[str] = None) -> None:
    """A text the team member sends from their own phone (sms_personal) never reaches the provider, so consent and sender rules
    do not apply; a STOP still does: refuse before the app logs it or opens the phone's messaging app."""
    from fastapi import HTTPException
    from services import sender_policy, suppression
    from services.twilio_service import normalize_phone
    phone = normalize_phone(to_phone)
    pol = await sender_policy.check(db, from_phone=None, user_id=user_id, org_id=None, platform=False)
    hit = await suppression.active(db, phone, pol.get("org_id"))
    if not hit and contact_id and ObjectId.is_valid(str(contact_id)):
        hit = await db.contacts.find_one({"_id": ObjectId(str(contact_id)), "$or": [{"opted_out": True}, {"sms_opt_out": True}]}, {"_id": 1})
    if hit:
        raise HTTPException(status_code=409, detail={"code": "opted_out", "message": REASONS["opted_out"], "needs": [], "purpose": "conversational",
                                                     "contact_id": contact_id, "phone": phone})
