"""Scan with Jessi (Visual Intelligence Engine, Phase B). A rep photographs a business card (or picks a photo / PDF) before a contact
exists: it is stored and read once by the shared reader (services.contact_files, GPT-5.4), kept owner-only until the rep saves it to a
new or existing contact, and only the details the rep ticks are written. Nothing is sent to anyone."""
import re
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId

from routers.database import get_data_filter
from services import contact_files as cf
from services import doc_reminders as dr
from services import mms_vision as mv

CARD_FIELDS = ("first_name", "last_name", "company", "title", "phone", "phone_office", "email", "website",
               "address_street", "address_city", "address_state", "address_zip")
CURRENT = {"first_name": lambda c: c.get("first_name"), "last_name": lambda c: c.get("last_name"), "company": lambda c: c.get("employer"),
           "title": lambda c: c.get("occupation"), "phone": lambda c: c.get("phone"), "email": lambda c: c.get("email"),
           "website": lambda c: (c.get("personal_details") or {}).get("website"), "address_street": lambda c: c.get("address_street"),
           "address_city": lambda c: c.get("address_city"), "address_state": lambda c: c.get("address_state"), "address_zip": lambda c: c.get("address_zip")}


async def status(db, user_id: str) -> dict:
    """Scan with Jessi follows the Automatic Photo Intelligence rollout (test orgs first) and Pause All."""
    cfg = await mv.settings(db)
    return {"enabled": await mv.capability(db, "intelligence", user_id), "paused": cfg["paused"]}


def _digits(v) -> str:
    return re.sub(r"\D", "", str(v or ""))[-10:]


async def matches(db, caller: dict, fields: dict, company: bool = False) -> list:
    """Contacts this rep can already see that look like the card: same phone (either number), same email, or same first + last name.
    company=True (documents) also matches the company on the paper against the contact's employer."""
    cid = str(caller["_id"])
    scope = {"user_id": cid} if caller.get("role") == "super_admin" else await get_data_filter(cid)
    ors, phones = [], [d for d in (_digits(fields.get("phone")), _digits(fields.get("phone_office"))) if len(d) >= 7]
    for d in phones:
        ors += [{"phone": {"$regex": re.escape(d) + "$"}}, {"phones.number": {"$regex": re.escape(d) + "$"}}]
    email = str(fields.get("email") or "").strip().lower()
    if "@" in email:
        rx = {"$regex": f"^{re.escape(email)}$", "$options": "i"}
        ors += [{"email": rx}, {"email_work": rx}]
    fn, ln = str(fields.get("first_name") or "").strip(), str(fields.get("last_name") or "").strip()
    if fn and ln:
        ors.append({"first_name": {"$regex": f"^{re.escape(fn)}$", "$options": "i"}, "last_name": {"$regex": f"^{re.escape(ln)}$", "$options": "i"}})
    co = str(fields.get("company") or "").strip() if company else ""
    if len(co) >= 3:
        ors.append({"employer": {"$regex": f"^{re.escape(co)}$", "$options": "i"}})
    if not ors:
        return []
    rows = await db.contacts.find({**scope, "$or": ors, "status": {"$nin": ["hidden", "merged", "deleted"]}},
                                  {"first_name": 1, "last_name": 1, "phone": 1, "phones": 1, "email": 1, "email_work": 1, "employer": 1, "occupation": 1,
                                   "photo_thumbnail": 1, "personal_details.website": 1, "address_street": 1, "address_city": 1, "address_state": 1,
                                   "address_zip": 1}).to_list(5)
    out = []
    for c in rows:
        why = []
        if any(_digits(c.get("phone")) == d or any(_digits(p.get("number")) == d for p in c.get("phones") or [] if isinstance(p, dict)) for d in phones):
            why.append("same phone")
        if "@" in email and email in (str(c.get("email") or "").lower(), str(c.get("email_work") or "").lower()):
            why.append("same email")
        if fn and ln and (c.get("first_name") or "").lower() == fn.lower() and (c.get("last_name") or "").lower() == ln.lower():
            why.append("same name")
        if len(co) >= 3 and (c.get("employer") or "").lower() == co.lower():
            why.append("same company")
        out.append({"id": str(c["_id"]), "name": f"{c.get('first_name') or ''} {c.get('last_name') or ''}".strip() or "Unnamed",
                    "phone": c.get("phone") or "", "email": c.get("email") or "", "company": c.get("employer") or "", "why": why,
                    "photo_thumbnail": c.get("photo_thumbnail") or "",
                    "current": {k: str(f(c) or "") for k, f in CURRENT.items()}})
    return out


def view(doc: dict, caller_id: str) -> dict:
    """What the review screen shows: Jessi found (summary), the card details, how sure she is, and whether it is a private document."""
    v = cf.public(doc, caller_id)
    sens = bool(doc.get("sensitive"))
    f = {} if sens else {k: str(doc.get("fields", {}).get(k) or "") for k in CARD_FIELDS if (doc.get("fields") or {}).get(k)}
    conf = float(doc.get("confidence") or 0)
    return {**{k: v[k] for k in ("id", "kind", "scan_type", "scan_label", "title", "status", "sensitive", "thumb_url", "url", "created_at",
                                 "doc_type", "doc_label", "dates", "reminders")},
            "contact_id": doc.get("contact_id") or "", "summary": "" if sens else v["summary"], "fields": f,
            "labels": {k: cf.FIELD_LABELS[k] for k in CARD_FIELDS}, "is_card": doc.get("scan_type") == "business_card" and not sens,
            "confidence": conf, "check": bool(f) and conf < 0.6, "paused": doc.get("unread_reason") == "paused", "reused": bool(doc.get("read_cached"))}


async def save_to_contact(db, user_id: str, doc: dict, contact: dict, wanted: list, values: dict, reminders: Optional[list] = None) -> dict:
    """Attach the scan to the contact (same stored file, same reading, no second analysis), log it on the timeline, then write ONLY the
    ticked details (the rep's edits win over what Jessi read). Existing values change only when the rep ticked them (Replace).
    `reminders` = keys of the suggested reminders the rep ticked on a document (rep tasks, never sent to the customer)."""
    now = datetime.now(timezone.utc)
    sets = {"contact_id": str(contact["_id"]), "saved_at": now}
    edited = {k: " ".join(str(values[k]).split())[:200] for k in CARD_FIELDS if isinstance(values.get(k), str) and values[k].strip()}
    if edited and not doc.get("sensitive"):
        sets["fields"] = {**(doc.get("fields") or {}), **edited}
    await db.contact_files.update_one({"_id": doc["_id"]}, {"$set": sets})
    doc = {**doc, **sets}
    sens = bool(doc.get("sensitive"))
    label = "Private document" if sens else dr.doc_label(doc) or cf.SCAN_TYPES.get(doc.get("scan_type") or "", "File")
    await db.contact_events.insert_one({
        "event_type": "file_added", "title": f"{label} scanned with Jessi", "contact_id": str(contact["_id"]), "user_id": user_id,
        "description": "Visible to the rep who scanned it, removed after 30 days." if sens else (doc.get("summary") or doc.get("title") or "")[:200],
        "content": "" if sens else doc.get("summary") or "", "category": "file", "icon": "scan", "color": "#5AC8FA",
        "metadata": {"file_id": str(doc["_id"]), "kind": doc.get("kind"), "scan_type": doc.get("scan_type"), "sensitive": sens, "source": "scan",
                     "capture": doc.get("capture")}, "timestamp": now, "created_at": now})
    applied = {}
    wanted = [k for k in wanted or [] if k in CARD_FIELDS and not sens]
    if wanted:
        applied = (await cf.apply_fields(db, doc, contact, wanted))["applied"]
        if applied:
            await db.contact_events.insert_one({
                "event_type": "file_applied", "title": "Details added from a business card",
                "description": ", ".join(f"{cf.FIELD_LABELS[k]}: {v}" for k, v in applied.items())[:200], "contact_id": str(contact["_id"]),
                "user_id": user_id, "category": "file", "icon": "checkmark-done", "color": "#34C759",
                "metadata": {"file_id": str(doc["_id"]), "fields": list(applied), "source": "scan"}, "timestamp": now, "created_at": now})
    made = []
    for key in [k for k in reminders or [] if isinstance(k, str)][:dr.MAX_SUGGESTIONS]:
        try:
            made.append(await dr.decide(db, user_id, doc, contact, key))
        except ValueError:
            continue
    return {"applied": applied, "labels": {k: cf.FIELD_LABELS[k] for k in applied}, "contact_id": str(contact["_id"]), "file_id": str(doc["_id"]),
            "reminders": [m for m in made if m.get("status") == "created"]}


async def pending(db, caller_id: str, scan_id: str) -> Optional[dict]:
    if not ObjectId.is_valid(scan_id or ""):
        return None
    return await db.contact_files.find_one({"_id": ObjectId(scan_id), "user_id": caller_id, "source": "scan", "deleted": {"$ne": True}})
