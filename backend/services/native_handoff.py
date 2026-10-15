"""Native Messages handoff: before the app opens the phone's own Messages app for a recipient, the server authorizes that exact
recipient and purpose through the same outbound gate as platform texts: the caller and their organization, ownership of the intended
contact (and that the number is that contact's), STOP / opt-out, consent for the purpose, and subscription access. Sender registration
does not apply (the platform does not send). An authorization covers one recipient and one purpose and is valid for TTL_S seconds;
the app builds the Messages link only from the authorized number. Limitation: once Messages is open, the app can't guarantee the
recipient or the text stay unchanged."""
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from bson import ObjectId
from fastapi import HTTPException

COLL = "native_handoff_authorizations"
TTL_S = 120


def _oid(value, what: str) -> ObjectId:
    if not value or not ObjectId.is_valid(str(value)) or len(str(value)) != 24:
        raise HTTPException(status_code=400, detail=f"Invalid {what}")
    return ObjectId(str(value))


async def _may_act_for(caller: str, owner: str) -> bool:
    from services.route_guard import manager_can_access
    return owner == caller or (ObjectId.is_valid(owner) and await manager_can_access(caller, owner))


def _numbers(contact: dict) -> set:
    from services.twilio_service import normalize_phone
    raw = [contact.get("phone")] + [(p or {}).get("value") for p in (contact.get("phones") or []) if isinstance(p, dict)]
    return {normalize_phone(n) for n in raw if n}


async def authorize(db, caller_id: str, *, phone: Optional[str] = None, contact_id: Optional[str] = None, purpose: Optional[str] = None,
                    system_kind: Optional[str] = None, pending_send_id: Optional[str] = None) -> dict:
    """The authorization record, or HTTPException: 400 bad input / phone not the contact's, 403 not yours, 404 unknown, 409 refused by the gate."""
    from services import outbound_gate
    from services.twilio_service import normalize_phone
    caller = str(caller_id)
    if pending_send_id:
        ps = await db.campaign_pending_sends.find_one({"_id": _oid(pending_send_id, "pending send id")})
        if not ps:
            raise HTTPException(status_code=404, detail="Pending send not found")
        if not await _may_act_for(caller, str(ps.get("user_id") or "")):
            raise HTTPException(status_code=403, detail="Access denied — you can only access your own data")
        camp = await db.campaigns.find_one({"_id": ObjectId(ps["campaign_id"])}, {"message_purpose": 1}) if ObjectId.is_valid(str(ps.get("campaign_id") or "")) else None
        purpose = ps.get("purpose") or (camp or {}).get("message_purpose") or "marketing"  # the server decides a campaign's purpose
        contact_id = contact_id or ps.get("contact_id") or None
        phone = phone or ps.get("contact_phone")
    contact = None
    if contact_id:
        contact = await db.contacts.find_one({"_id": _oid(contact_id, "contact id")}, {"user_id": 1, "phone": 1, "phones": 1, "opted_out": 1, "sms_opt_out": 1})
        if not contact:
            raise HTTPException(status_code=404, detail="Contact not found")
        if not await _may_act_for(caller, str(contact.get("user_id") or "")):
            raise HTTPException(status_code=403, detail="Access denied — you can only access your own data")
        numbers = _numbers(contact)
        to = normalize_phone(phone) if phone else normalize_phone(contact.get("phone") or "")
        if not to or to not in numbers:
            raise HTTPException(status_code=400, detail="That number is not this contact's number")
    else:
        to = normalize_phone(phone or "")
        if len(to.lstrip("+")) < 10:
            raise HTTPException(status_code=400, detail="A valid phone number is required")
    refusal = {"contact_id": contact_id, "phone": to}
    if contact and (contact.get("opted_out") or contact.get("sms_opt_out")):
        raise HTTPException(status_code=409, detail={"code": "opted_out", "message": outbound_gate.REASONS["opted_out"], "needs": [], "purpose": purpose or "conversational", **refusal})
    d = await outbound_gate.evaluate(db, to_phone=to, from_phone=None, purpose=purpose, system_kind=system_kind, user_id=caller,
                                     contact_id=contact_id, native=True)
    if not d["allowed"]:
        raise HTTPException(status_code=409, detail={"code": d["code"], "message": d["reason"], "needs": d.get("needs") or [], "purpose": d.get("purpose"), **refusal})
    now = datetime.now(timezone.utc)
    doc = {"_id": secrets.token_urlsafe(18), "user_id": caller, "org_id": d.get("org_id"), "contact_id": contact_id, "phone": to,
           "purpose": d["purpose"], "system_kind": system_kind, "pending_send_id": pending_send_id, "basis": d.get("basis"),
           "shadow_would_block": d.get("shadow") or [], "sender": d.get("sender"), "issued_at": now, "expires_at": now + timedelta(seconds=TTL_S)}
    await db[COLL].insert_one(doc)
    return doc


def public(doc: dict) -> dict:
    return {"authorized": True, "token": doc["_id"], "phone": doc["phone"], "purpose": doc["purpose"], "contact_id": doc.get("contact_id"),
            "expires_at": doc["expires_at"].isoformat(), "ttl_s": TTL_S, "basis": doc.get("basis"), "shadow": doc.get("shadow_would_block") or []}
