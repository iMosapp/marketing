"""
CRM Push — export a contact as a standards-compliant ADF 1.0 XML lead and
email it to any CRM's ADF intake address (VinSolutions, Elead, DriveCentric, etc.).
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from bson import ObjectId
from datetime import datetime, timezone
from xml.sax.saxutils import escape
import os
import re
import asyncio
import logging

from routers.database import get_db
from utils.contact_activity import log_customer_activity

router = APIRouter(prefix="/crm-push", tags=["crm-push"])
logger = logging.getLogger(__name__)


def _parse_vehicle(v: str):
    """Best-effort '2024 Toyota Tacoma TRD' -> (year, make, model+trim)."""
    if not v:
        return "", "", ""
    m = re.match(r"\s*(\d{4})\s+(\S+)\s*(.*)", v)
    if m:
        return m.group(1), m.group(2), m.group(3).strip()
    parts = v.strip().split(" ", 1)
    return "", parts[0], parts[1] if len(parts) > 1 else ""


def build_adf(contact: dict, user: dict, store_name: str) -> str:
    e = lambda x: escape(str(x or "").strip())
    year, make, model = _parse_vehicle(contact.get("vehicle") or contact.get("vehicle_interest") or "")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<?adf version="1.0"?>',
        "<adf>",
        ' <prospect status="new">',
        f"  <requestdate>{now}</requestdate>",
        f'  <id sequence="1" source="iM On Social">{e(contact.get("_id"))}</id>',
    ]
    if year or make or model:
        lines.append('  <vehicle interest="buy">')
        if year:
            lines.append(f"   <year>{e(year)}</year>")
        if make:
            lines.append(f"   <make>{e(make)}</make>")
        if model:
            lines.append(f"   <model>{e(model)}</model>")
        lines.append("  </vehicle>")
    lines.append("  <customer>")
    lines.append("   <contact>")
    lines.append(f'    <name part="first">{e(contact.get("first_name"))}</name>')
    if contact.get("last_name"):
        lines.append(f'    <name part="last">{e(contact.get("last_name"))}</name>')
    if contact.get("phone"):
        lines.append(f'    <phone type="voice">{e(contact.get("phone"))}</phone>')
    if contact.get("email"):
        lines.append(f"    <email>{e(contact.get('email'))}</email>")
    if any(contact.get(k) for k in ("address_street", "address_city", "address_state", "address_zip")):
        lines.append("    <address>")
        if contact.get("address_street"):
            lines.append(f"     <street>{e(contact.get('address_street'))}</street>")
        if contact.get("address_city"):
            lines.append(f"     <city>{e(contact.get('address_city'))}</city>")
        if contact.get("address_state"):
            lines.append(f"     <regioncode>{e(contact.get('address_state'))}</regioncode>")
        if contact.get("address_zip"):
            lines.append(f"     <postalcode>{e(contact.get('address_zip'))}</postalcode>")
        lines.append("    </address>")
    lines.append("   </contact>")
    notes = (contact.get("notes") or "").strip()
    if notes:
        lines.append(f"   <comments>{e(notes[:2000])}</comments>")
    lines.append("  </customer>")
    lines.append("  <vendor>")
    lines.append(f"   <vendorname>{e(store_name or 'iM On Social')}</vendorname>")
    lines.append("   <contact>")
    lines.append(f'    <name part="full">{e(user.get("name"))}</name>')
    if user.get("email"):
        lines.append(f"    <email>{e(user.get('email'))}</email>")
    if user.get("twilio_number") or user.get("phone"):
        lines.append(f'    <phone type="voice">{e(user.get("phone") or user.get("twilio_number"))}</phone>')
    lines.append("   </contact>")
    lines.append("  </vendor>")
    lines.append("  <provider><name>iM On Social</name></provider>")
    lines.append(" </prospect>")
    lines.append("</adf>")
    return "\n".join(lines)


async def _load(db, user_id: str, contact_id: str):
    try:
        contact = await db.contacts.find_one({"_id": ObjectId(contact_id)})
        user = await db.users.find_one({"_id": ObjectId(user_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid id")
    if not contact or not user:
        raise HTTPException(status_code=404, detail="Contact or user not found")
    store_name = ""
    if user.get("store_id"):
        try:
            store = await db.stores.find_one({"_id": ObjectId(user["store_id"])})
            store_name = (store or {}).get("name", "")
        except Exception:
            pass
    return contact, user, store_name


@router.get("/{user_id}/{contact_id}/preview")
async def preview_adf(user_id: str, contact_id: str):
    db = get_db()
    contact, user, store_name = await _load(db, user_id, contact_id)
    return {
        "xml": build_adf(contact, user, store_name),
        "crm_email": user.get("crm_intake_email", ""),
    }


class PushBody(BaseModel):
    email: str
    save_email: bool = True


@router.post("/{user_id}/{contact_id}")
async def push_to_crm(user_id: str, contact_id: str, body: PushBody):
    db = get_db()
    to_email = body.email.strip()
    if "@" not in to_email or "." not in to_email:
        raise HTTPException(status_code=400, detail="Enter a valid CRM intake email address")

    contact, user, store_name = await _load(db, user_id, contact_id)
    xml = build_adf(contact, user, store_name)

    resend_key = os.environ.get("RESEND_API_KEY")
    if not resend_key:
        raise HTTPException(status_code=503, detail="Email sending is not configured")
    import resend
    resend.api_key = resend_key
    name = f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip()
    try:
        await asyncio.to_thread(resend.Emails.send, {
            "from": f"{user.get('name', 'iM On Social')} <{os.environ.get('SENDER_EMAIL', 'notifications@send.imonsocial.com')}>",
            "to": to_email,
            "reply_to": user.get("email", "support@imonsocial.com"),
            "subject": f"New Lead: {name}",
            "text": xml,
        })
    except Exception as e:
        logger.error(f"[CrmPush] send failed: {e}")
        raise HTTPException(status_code=502, detail="Failed to send — check the address and try again")

    if body.save_email:
        await db.users.update_one({"_id": ObjectId(user_id)}, {"$set": {"crm_intake_email": to_email}})
    await db.contacts.update_one(
        {"_id": ObjectId(contact_id)},
        {"$addToSet": {"tags": "Pushed to CRM"}, "$set": {"updated_at": datetime.now(timezone.utc)}},
    )
    await log_customer_activity(
        user_id=user_id, contact_id=contact_id, event_type="crm_push",
        title="Pushed to CRM", description=f"ADF/XML lead emailed to {to_email}",
        icon="cloud-upload", color="#AF52DE", category="system",
    )
    return {"sent": True, "to": to_email}
