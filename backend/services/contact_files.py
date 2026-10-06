"""Files and photos on a contact: business cards, VIN plates, trade-in photos, PDFs, pictures a customer texts.
Stored in object storage, read by Jessi (OCR + summary + fields), so Ask, memory search and Relationship Intel cover them.
Sensitive documents (IDs, insurance cards, credit apps) are visible to the uploading rep only and destroyed after SENSITIVE_TTL_DAYS."""
import asyncio
import base64
import hashlib
import hmac
import io
import json
import logging
import os
import re
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from bson import ObjectId

from services.llm_models import VISION_MODEL
from utils.image_storage import put_object
from utils.text_sanitize import no_em_dash

logger = logging.getLogger(__name__)

MAX_BYTES = 25 * 1024 * 1024
SENSITIVE_TTL_DAYS = 30
OPEN_TOKEN_SECONDS = 60 * 60
SCAN_TYPES = {"business_card": "Business card", "vin": "VIN / odometer", "trade_in": "Trade-in photos", "id_document": "Driver's license / ID",
              "insurance_card": "Insurance card", "credit_app": "Credit application", "receipt": "Receipt / invoice", "document": "Document", "photo": "Photo"}
SENSITIVE_TYPES = {"id_document", "insurance_card", "credit_app"}
FIELD_LABELS = {"first_name": "First name", "last_name": "Last name", "company": "Company", "title": "Job title", "phone": "Phone", "email": "Email", "website": "Website",
                "address_street": "Street", "address_city": "City", "address_state": "State", "address_zip": "ZIP", "vin": "VIN", "year": "Year", "make": "Make", "model": "Model",
                "trim": "Trim", "mileage": "Mileage", "color": "Color", "plate": "Plate", "birthday": "Birthday"}

READ_SYSTEM = (
    "You read documents and photos a salesperson files on a customer record. Reply with JSON only:\n"
    "{\"type\": one of business_card|vin|trade_in|id_document|insurance_card|credit_app|receipt|document|photo,\n"
    " \"title\": \"3 to 6 word title\",\n"
    " \"summary\": \"one or two plain sentences: what this is and anything worth remembering about the customer, no em dashes\",\n"
    " \"text\": \"every readable word in reading order, empty string if there is no text\",\n"
    " \"sensitive\": true when it shows a government ID, social security or tax number, bank, card or account numbers, an insurance policy or a signed financial form,\n"
    " \"fields\": {only keys you can read with confidence: first_name, last_name, company, title, phone, email, website, address_street, address_city, address_state, address_zip, "
    "vin, year, make, model, trim, mileage, color, plate, birthday (YYYY-MM-DD)}}\n"
    "Never write social security numbers, full card or account numbers anywhere; put [redacted] instead. Phone numbers as digits with the area code. "
    "A VIN is 17 characters, no I, O or Q. If several pages or photos are given, treat them as one document.")


def _now():
    return datetime.now(timezone.utc)


def _kind(content_type: str, name: str) -> Optional[str]:
    ct = (content_type or "").lower()
    if "pdf" in ct or (name or "").lower().endswith(".pdf"):
        return "pdf"
    if ct.startswith("image/") or re.search(r"\.(jpe?g|png|webp|heic|heif|gif)$", (name or "").lower()):
        return "image"
    return None


def _normalize_image(data: bytes):
    """EXIF-rotate, flatten, cap at 2400px and re-encode as JPEG; also a 480px thumbnail. HEIC comes through pillow_heif."""
    from PIL import Image, ImageOps
    try:
        import pillow_heif
        pillow_heif.register_heif_opener()
    except Exception:
        pass
    img = Image.open(io.BytesIO(data))
    img = ImageOps.exif_transpose(img)
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    w, h = img.size
    if max(w, h) > 2400:
        img.thumbnail((2400, 2400))
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=88)
    thumb = img.copy()
    thumb.thumbnail((480, 480))
    tb = io.BytesIO()
    thumb.save(tb, format="JPEG", quality=80)
    return out.getvalue(), tb.getvalue(), img.size


def _for_vision(jpeg: bytes) -> str:
    from PIL import Image
    img = Image.open(io.BytesIO(jpeg))
    if max(img.size) > 1600:
        img.thumbnail((1600, 1600))
    b = io.BytesIO()
    img.convert("RGB").save(b, format="JPEG", quality=85)
    return base64.b64encode(b.getvalue()).decode()


def _pdf_extract(data: bytes):
    """Text layer (first 25 pages), page count, a first-page thumbnail, and rendered pages for OCR when there is no text layer."""
    import fitz
    doc = fitz.open(stream=data, filetype="pdf")
    pages = doc.page_count
    text = "\n".join(doc[i].get_text() for i in range(min(pages, 25)))[:30000]
    thumb = doc[0].get_pixmap(matrix=fitz.Matrix(0.6, 0.6)).tobytes("jpeg") if pages else b""
    renders = []
    if len(text.strip()) < 80 and pages:
        for i in range(min(pages, 3)):
            renders.append(base64.b64encode(doc[i].get_pixmap(matrix=fitz.Matrix(1.5, 1.5)).tobytes("jpeg")).decode())
    doc.close()
    return text, pages, thumb, renders


def _parse_json(raw) -> dict:
    s = raw if isinstance(raw, str) else getattr(raw, "text", "") or str(raw)
    m = re.search(r"\{.*\}", s, re.S)
    try:
        d = json.loads(m.group(0)) if m else {}
    except json.JSONDecodeError:
        d = {}
    return d if isinstance(d, dict) else {}


async def _jessi_read(text_hint: str, images_b64: list, pdf_text: str = "") -> dict:
    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        return {}
    from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent
    chat = LlmChat(api_key=api_key, session_id=f"file_{uuid.uuid4().hex[:8]}", system_message=READ_SYSTEM).with_model(*VISION_MODEL)
    prompt = text_hint
    if pdf_text:
        prompt += f"\n\nDOCUMENT TEXT:\n{pdf_text[:12000]}"
    msg = UserMessage(text=prompt, file_contents=[ImageContent(image_base64=b) for b in images_b64[:4]] or None)
    out = await asyncio.wait_for(chat.send_message(msg), timeout=90)
    return _parse_json(out)


def _clean_fields(raw) -> dict:
    out = {}
    for k, v in (raw or {}).items() if isinstance(raw, dict) else []:
        if k in FIELD_LABELS and v not in (None, "", [], {}):
            s = " ".join(str(v).split())[:120]
            if "redact" in s.lower():
                continue
            if k == "phone":
                digits = re.sub(r"\D", "", s)
                if len(digits) < 10:
                    continue
                s = digits[-10:] if len(digits) in (10, 11) else digits
            if k == "vin":
                s = s.upper().replace(" ", "")
                if not re.fullmatch(r"[A-HJ-NPR-Z0-9]{17}", s):
                    continue
            out[k] = s
    return out


async def read_file(kind: str, data: bytes, hint: Optional[str]) -> dict:
    """Jessi's read of one file: type, title, summary, full text, fields, sensitive flag. Never raises; an empty dict means she could not read it."""
    try:
        hint_line = f"The rep says this is probably a {SCAN_TYPES.get(hint or '', '').lower() or 'document'}." if hint else "Work out what this is."
        if kind == "pdf":
            text, pages, _, renders = await asyncio.to_thread(_pdf_extract, data)
            d = await _jessi_read(hint_line + (" This is a PDF; the readable text is below." if text.strip() else " This PDF has no text layer; read the page images."), renders, text)
            if text.strip():
                d["text"] = text[:30000]
            d["pages"] = pages
        else:
            d = await _jessi_read(hint_line, [await asyncio.to_thread(_for_vision, data)])
        t = str(d.get("type") or hint or "document")
        d["type"] = t if t in SCAN_TYPES else (hint if hint in SCAN_TYPES else "document")
        d["title"] = no_em_dash(str(d.get("title") or ""))[:60]
        d["summary"] = no_em_dash(str(d.get("summary") or ""))[:600]
        d["text"] = str(d.get("text") or "")[:30000]
        d["fields"] = _clean_fields(d.get("fields"))
        d["sensitive"] = bool(d.get("sensitive")) or d["type"] in SENSITIVE_TYPES
        return d
    except Exception as e:
        logger.warning(f"[ContactFiles] read failed: {e}")
        return {}


def open_token(file_id: str, seconds: int = OPEN_TOKEN_SECONDS) -> str:
    exp = int(time.time()) + seconds
    sig = hmac.new(os.environ["JWT_SECRET"].encode(), f"{file_id}.{exp}".encode(), hashlib.sha256).hexdigest()[:32]
    return f"{file_id}.{exp}.{sig}"


def verify_open_token(token: str) -> Optional[str]:
    try:
        fid, exp, sig = token.split(".")
        if int(exp) < time.time():
            return None
        good = hmac.new(os.environ["JWT_SECRET"].encode(), f"{fid}.{exp}".encode(), hashlib.sha256).hexdigest()[:32]
        return fid if hmac.compare_digest(good, sig) else None
    except Exception:
        return None


def public(doc: dict, caller_id: str) -> dict:
    fid = str(doc["_id"])
    sensitive = bool(doc.get("sensitive"))
    url = f"/api/contact-files/open/{open_token(fid)}" if sensitive else f"/api/images/{doc.get('path')}"
    thumb = (f"/api/contact-files/open/{open_token(fid)}?thumb=1" if sensitive else f"/api/images/{doc.get('thumb_path')}") if doc.get("thumb_path") else None
    return {"id": fid, "contact_id": doc.get("contact_id"), "name": doc.get("name") or "", "kind": doc.get("kind"), "content_type": doc.get("content_type"),
            "size": doc.get("size") or 0, "pages": doc.get("pages") or 0, "scan_type": doc.get("scan_type") or "document", "scan_label": SCAN_TYPES.get(doc.get("scan_type") or "", "Document"),
            "title": doc.get("title") or "", "summary": doc.get("summary") or "", "text": (doc.get("text") or "")[:20000], "fields": doc.get("fields") or {},
            "field_labels": {k: FIELD_LABELS[k] for k in (doc.get("fields") or {}) if k in FIELD_LABELS},
            "sensitive": sensitive, "expires_at": doc["expires_at"].isoformat() if doc.get("expires_at") else "", "status": doc.get("status") or "ready",
            "source": doc.get("source") or "upload", "created_at": doc["created_at"].isoformat() if doc.get("created_at") else "",
            "applied": doc.get("applied") or [], "mine": str(doc.get("user_id")) == str(caller_id), "url": url, "thumb_url": thumb}


async def save_file(db, *, user_id: str, contact_id: str, name: str, content_type: str, data: bytes, hint: Optional[str] = None,
                    source: str = "upload", message_id: Optional[str] = None) -> dict:
    """Store + read one file. Raises ValueError for unsupported or oversized files."""
    if len(data) > MAX_BYTES:
        raise ValueError(f"That file is over {MAX_BYTES // (1024 * 1024)} MB")
    if not data:
        raise ValueError("Empty file")
    kind = _kind(content_type, name)
    if not kind:
        raise ValueError("Only photos and PDFs can be filed for now")
    fid = ObjectId()
    base = f"contact-files/{user_id}/{contact_id}/{fid}"
    thumb_path, pages = None, 0
    if kind == "image":
        try:
            data, thumb, _ = await asyncio.to_thread(_normalize_image, data)
            content_type, ext = "image/jpeg", "jpg"
        except Exception as e:
            raise ValueError(f"That image could not be read: {e}")
    else:
        content_type, ext = "application/pdf", "pdf"
        try:
            _, pages, thumb, _ = await asyncio.to_thread(_pdf_extract, data)
        except Exception as e:
            raise ValueError("That PDF could not be opened")
    path = f"{base}.{ext}"
    await asyncio.to_thread(put_object, path, data, content_type)
    if thumb:
        thumb_path = f"{base}_thumb.jpg"
        await asyncio.to_thread(put_object, thumb_path, thumb, "image/jpeg")
    now = _now()
    doc = {"_id": fid, "user_id": user_id, "contact_id": contact_id, "name": (name or f"{kind}.{ext}")[:120], "kind": kind, "content_type": content_type, "size": len(data),
           "pages": pages, "path": path, "thumb_path": thumb_path, "scan_type": hint if hint in SCAN_TYPES else "document" if kind == "pdf" else "photo", "hint": hint,
           "sensitive": hint in SENSITIVE_TYPES, "status": "reading", "source": source, "message_id": message_id, "created_at": now, "applied": []}
    if doc["sensitive"]:
        doc["expires_at"] = now + timedelta(days=SENSITIVE_TTL_DAYS)
    await db.contact_files.insert_one(doc)
    read = await read_file(kind, data, hint)
    upd = {"status": "ready" if read else "unread"}
    if read:
        upd.update({"scan_type": read["type"], "title": read["title"], "summary": read["summary"], "text": read["text"], "fields": read["fields"], "pages": read.get("pages") or pages})
        if read["sensitive"] and not doc["sensitive"]:
            upd.update({"sensitive": True, "expires_at": now + timedelta(days=SENSITIVE_TTL_DAYS)})
    await db.contact_files.update_one({"_id": fid}, {"$set": upd})
    doc.update(upd)
    try:
        label = SCAN_TYPES.get(doc.get("scan_type") or "", "File")
        await db.contact_events.insert_one({
            "event_type": "file_added", "title": f"{label} filed" if source != "mms" else f"{label} from a text filed",
            "description": (doc.get("summary") or doc.get("title") or doc["name"])[:200], "contact_id": contact_id, "user_id": user_id,
            "category": "file", "icon": "document-attach", "color": "#5AC8FA", "content": doc.get("summary") or "",
            "metadata": {"file_id": str(fid), "kind": kind, "scan_type": doc.get("scan_type"), "sensitive": doc.get("sensitive"), "source": source},
            "timestamp": now, "created_at": now,
        })
    except Exception as e:
        logger.warning(f"[ContactFiles] event log failed: {e}")
    return doc


def _destroy(doc: dict):
    for p in (doc.get("path"), doc.get("thumb_path")):
        if p:
            try:
                put_object(p, b"\0", "application/octet-stream")
            except Exception as e:
                logger.warning(f"[ContactFiles] destroy {p} failed: {e}")


async def destroy_file(db, doc: dict, reason: str = "deleted"):
    """Overwrite the stored objects (object storage has no delete) and blank the record."""
    await asyncio.to_thread(_destroy, doc)
    await db.contact_files.update_one({"_id": doc["_id"]}, {"$set": {"deleted": True, "deleted_at": _now(), "deleted_reason": reason},
                                                             "$unset": {"text": "", "fields": "", "summary": ""}})


async def purge_expired(db) -> int:
    """Daily: sensitive documents past their 30 days are destroyed."""
    n = 0
    async for doc in db.contact_files.find({"sensitive": True, "deleted": {"$ne": True}, "expires_at": {"$lt": _now()}}):
        await destroy_file(db, doc, "expired")
        n += 1
    if n:
        logger.info(f"[ContactFiles] purged {n} expired sensitive files")
    return n


def _vehicle_line(f: dict) -> str:
    parts = [f.get(k) for k in ("year", "make", "model", "trim") if f.get(k)]
    return " ".join(parts)


async def apply_fields(db, doc: dict, contact: dict, wanted: list) -> dict:
    """Write the chosen extracted fields onto the contact. Returns {applied: {field: value}}."""
    f = doc.get("fields") or {}
    sets, applied, pd = {}, {}, dict(contact.get("personal_details") or {})
    for k in wanted:
        v = f.get(k)
        if not v:
            continue
        if k in ("first_name", "last_name", "address_street", "address_city", "address_state", "address_zip"):
            sets[k] = v
        elif k == "company":
            sets["employer"] = v
        elif k == "title":
            sets["occupation"] = v
        elif k == "website":
            pd["website"] = v
        elif k == "phone":
            if not contact.get("phone"):
                sets["phone"] = f"+1{v}" if len(v) == 10 else v
            else:
                sets["phones"] = (contact.get("phones") or []) + [{"label": "work", "number": f"+1{v}" if len(v) == 10 else v}]
        elif k == "email":
            if not contact.get("email"):
                sets["email"] = v
            else:
                sets["email_work"] = v
        elif k in ("vin", "year", "make", "model", "trim", "mileage", "color", "plate"):
            line = _vehicle_line(f)
            if line and "vehicle" not in sets:
                sets["vehicle"] = line
            details = "; ".join(x for x in [f"VIN {f['vin']}" if f.get("vin") else "", f"{f['mileage']} miles" if f.get("mileage") else "", f.get("color") or "", f"plate {f['plate']}" if f.get("plate") else ""] if x)
            if details:
                pd["vehicle_details"] = details
        elif k == "birthday":
            try:
                sets["birthday"] = datetime.strptime(v, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        applied[k] = v
    if pd != (contact.get("personal_details") or {}):
        sets["personal_details"] = pd
    if sets:
        sets["updated_at"] = _now()
        await db.contacts.update_one({"_id": contact["_id"]}, {"$set": sets})
        await db.contact_files.update_one({"_id": doc["_id"]}, {"$addToSet": {"applied": {"$each": list(applied)}}})
    return {"applied": applied}


async def file_inbound_media(db, user_id: str, contact_id: str, message_id: str, urls: list, types: list):
    """A customer texted photos or a PDF: pull them from Twilio and file them on the contact (fire-and-forget from the webhook)."""
    sid, tok = os.environ.get("TWILIO_ACCOUNT_SID"), os.environ.get("TWILIO_AUTH_TOKEN")
    if not (sid and tok and user_id and contact_id):
        return
    if await db.contact_files.count_documents({"message_id": message_id}) > 0:
        return
    import httpx
    async with httpx.AsyncClient() as client:
        for i, url in enumerate(urls[:10]):
            ct = (types[i] if i < len(types) else "") or "image/jpeg"
            if not _kind(ct, ""):
                continue
            try:
                r = await client.get(url, auth=(sid, tok), follow_redirects=True, timeout=30)
                if r.status_code != 200:
                    continue
                stamp = _now().strftime("%b %-d")
                await save_file(db, user_id=user_id, contact_id=contact_id, name=f"Texted {stamp}" + ("" if len(urls) == 1 else f" ({i + 1})"), content_type=ct,
                                data=r.content, hint=None, source="mms", message_id=message_id)
            except Exception as e:
                logger.warning(f"[ContactFiles] mms file failed: {e}")


async def for_context(db, contact_id: str, caller_id: Optional[str] = None, limit: int = 30) -> list:
    """Files visible to a caller for prompts: name, type, summary, text excerpt. Sensitive files only for their uploader."""
    rows = await db.contact_files.find({"contact_id": contact_id, "deleted": {"$ne": True}}, {"name": 1, "scan_type": 1, "summary": 1, "text": 1, "fields": 1, "created_at": 1, "user_id": 1, "sensitive": 1, "kind": 1, "source": 1}).sort("created_at", -1).to_list(limit)
    return [r for r in rows if not r.get("sensitive") or (caller_id and str(r.get("user_id")) == str(caller_id))]
