"""Resend inbound email: customers' email replies land in the thread like a text.
Setup (one time): enable Receiving on a subdomain in Resend (e.g. reply.imonsocial.com, MX record), set INBOUND_EMAIL_DOMAIN
to that subdomain, and point a Resend webhook for `email.received` at POST /api/webhooks/resend/inbound
(optionally set RESEND_WEBHOOK_SECRET to verify signatures). Outbound thread emails then use
reply_to = reply+{conversation_id}@{INBOUND_EMAIL_DOMAIN} so replies route straight back to the thread."""
import asyncio
import base64
import hmac
import hashlib
import html as html_lib
import logging
import os
import re
from datetime import datetime, timezone

import httpx
from bson import ObjectId
from fastapi import APIRouter, Request, Response

from routers.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks/resend", tags=["Resend Webhooks"])

REPLY_RE = re.compile(r"reply\+([0-9a-f]{24})@", re.I)
QUOTE_CUTS = [
    re.compile(r"^On .{2,200} wrote:\s*$", re.M),
    re.compile(r"^-{2,}\s*Original Message\s*-{2,}\s*$", re.M | re.I),
    re.compile(r"^From:\s.+\n(Sent|Date):\s.+", re.M),
    re.compile(r"^Sent from my (iPhone|iPad|Galaxy|Android).*$", re.M),
    re.compile(r"^_{5,}\s*$", re.M),
]


def reply_to_address(conversation_id: str) -> str | None:
    domain = (os.environ.get("INBOUND_EMAIL_DOMAIN") or "").strip().lower()
    return f"reply+{conversation_id}@{domain}" if domain else None


def _verify_svix(headers, body: bytes) -> bool:
    secret = os.environ.get("RESEND_WEBHOOK_SECRET", "").strip()
    if not secret:
        return True
    msg_id, ts, sigs = headers.get("svix-id"), headers.get("svix-timestamp"), headers.get("svix-signature", "")
    if not (msg_id and ts and sigs):
        return False
    try:
        if abs(datetime.now(timezone.utc).timestamp() - int(ts)) > 300:
            return False
        key = base64.b64decode(secret.split("_", 1)[1] if secret.startswith("whsec_") else secret)
    except Exception:
        return False
    expected = base64.b64encode(hmac.new(key, f"{msg_id}.{ts}.".encode() + body, hashlib.sha256).digest()).decode()
    return any(hmac.compare_digest(expected, s.split(",", 1)[1]) for s in sigs.split(" ") if "," in s)


def _strip_html(h: str) -> str:
    h = re.sub(r"(?is)<(script|style|head).*?</\1>", " ", h or "")
    h = re.sub(r"(?i)<br\s*/?>|</(p|div|tr|li|h[1-6]|blockquote|table)>", "\n", h)
    text = html_lib.unescape(re.sub(r"<[^>]+>", "", h))
    return "\n".join(re.sub(r"[ \t\xa0]+", " ", l).strip() for l in text.split("\n"))


def clean_reply(text: str) -> str:
    """Keep only the customer's fresh words: drop quoted history and signatures."""
    t = (text or "").replace("\r\n", "\n").strip()
    cut = len(t)
    for rx in QUOTE_CUTS:
        m = rx.search(t)
        if m and m.start() < cut:
            cut = m.start()
    t = t[:cut]
    lines = [l for l in t.split("\n") if not l.lstrip().startswith(">")]
    t = "\n".join(lines)
    t = re.sub(r"\n{3,}", "\n\n", t).strip()
    return t[:4000]


async def _fetch_email(email_id: str) -> dict | None:
    key = os.environ.get("RESEND_API_KEY", "")
    if not key:
        logger.error("[ResendInbound] RESEND_API_KEY missing")
        return None
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(f"https://api.resend.com/emails/receiving/{email_id}", headers={"Authorization": f"Bearer {key}"})
        if r.status_code != 200:
            logger.error(f"[ResendInbound] fetch {email_id} failed {r.status_code}: {r.text[:200]}")
            return None
        return r.json()


def _addr(v) -> str:
    if isinstance(v, dict):
        v = v.get("email") or v.get("address") or ""
    m = re.search(r"<([^>]+)>", str(v or ""))
    return (m.group(1) if m else str(v or "")).strip().lower()


async def _route(db, to_list: list, from_email: str):
    """Conversation for this reply: reply+<conv> address first, then the sender's email on a contact."""
    for to in to_list:
        m = REPLY_RE.search(str(to if not isinstance(to, dict) else to.get("email") or ""))
        if m:
            conv = await db.conversations.find_one({"_id": ObjectId(m.group(1))})
            if conv:
                return conv
    if not from_email:
        return None
    rx = {"$regex": f"^{re.escape(from_email)}$", "$options": "i"}
    contacts = await db.contacts.find({"$or": [{"email": rx}, {"work_email": rx}, {"emails": rx}]}, {"_id": 1, "user_id": 1}).to_list(20)
    if not contacts:
        return None
    ids = [str(c["_id"]) for c in contacts]
    return await db.conversations.find_one({"contact_id": {"$in": ids}}, sort=[("last_message_at", -1)])


async def ingest_received_email(db, email: dict, email_id: str) -> dict:
    if await db.messages.find_one({"resend_email_id": email_id}, {"_id": 1}):
        return {"status": "duplicate"}
    from_email = _addr(email.get("from"))
    to_list = email.get("to") or []
    conv = await _route(db, to_list, from_email)
    subject = (email.get("subject") or "").strip()
    body = clean_reply(email.get("text") or _strip_html(email.get("html") or ""))
    if not conv:
        await db.inbound_email_unmatched.insert_one({"email_id": email_id, "from": from_email, "to": to_list, "subject": subject, "preview": body[:300], "created_at": datetime.now(timezone.utc)})
        logger.warning(f"[ResendInbound] no conversation for {from_email} -> {to_list}")
        return {"status": "unmatched"}
    if not body:
        body = f"(email with no text) {subject}".strip()
    conversation_id = str(conv["_id"])
    contact_id = conv.get("contact_id")
    user_id = conv.get("assigned_to") or conv.get("user_id")
    now = datetime.now(timezone.utc)
    msg = {"conversation_id": conversation_id, "contact_id": contact_id, "user_id": user_id, "content": body, "sender": "contact", "channel": "email",
           "subject": subject, "email_from": from_email, "direction": "inbound", "status": "received", "resend_email_id": email_id, "timestamp": now}
    ins = await db.messages.insert_one(msg)
    await db.conversations.update_one({"_id": conv["_id"]}, {"$set": {"last_message_at": now, "unread": True, "status": "active", "needs_assistance": True, "last_message_preview": body[:120], "last_channel": "email"},
                                                            "$inc": {"unread_count": 1, "unanswered_customer_replies": 1}})
    contact = await db.contacts.find_one({"_id": ObjectId(contact_id)}, {"name": 1, "first_name": 1, "last_name": 1}) if contact_id and ObjectId.is_valid(str(contact_id)) else None
    contact_name = (contact or {}).get("name") or f"{(contact or {}).get('first_name', '')} {(contact or {}).get('last_name', '')}".strip() or conv.get("contact_name") or from_email
    if contact_id:
        await db.contact_events.insert_one({"contact_id": str(contact_id), "user_id": user_id, "event_type": "email_received", "channel": "email", "title": "Email reply received",
                                            "description": (subject or body)[:200], "content": body[:1000], "message_id": str(ins.inserted_id), "conversation_id": conversation_id,
                                            "icon": "mail", "color": "#AF52DE", "timestamp": now, "created_at": now})
    if user_id:
        try:
            from websocket_manager import manager as ws_manager
            await ws_manager.send_to_user(str(user_id), {"type": "new_customer_message", "conversation_id": conversation_id, "contact_name": contact_name, "message_preview": body[:100], "channel": "email"})
            await db.notifications.insert_one({"user_id": str(user_id), "type": "new_message", "title": f"Email from {contact_name}", "message": (subject + ": " if subject else "") + body[:100],
                                               "conversation_id": conversation_id, "contact_id": str(contact_id) if contact_id else None, "contact_name": contact_name, "read": False, "created_at": now.isoformat()})
            await ws_manager.send_to_user(str(user_id), {"type": "notification_update", "reason": "new_message"})
            from routers.push_notifications import send_push_to_user
            asyncio.create_task(send_push_to_user(str(user_id), f"Email from {contact_name}", body[:120], f"/thread/{conversation_id}", "mail"))
        except Exception as e:
            logger.warning(f"[ResendInbound] notify failed: {e}")
    logger.info(f"[ResendInbound] {from_email} -> conversation {conversation_id} ({len(body)} chars)")
    return {"status": "ok", "conversation_id": conversation_id, "message_id": str(ins.inserted_id)}


@router.post("/inbound")
async def resend_inbound(request: Request):
    body = await request.body()
    if not _verify_svix(request.headers, body):
        logger.warning("[ResendInbound] bad signature")
        return Response(status_code=401, content="bad signature")
    try:
        event = await request.json()
    except Exception:
        return Response(status_code=400, content="bad json")
    if event.get("type") != "email.received":
        return {"ignored": event.get("type")}
    email_id = (event.get("data") or {}).get("email_id") or (event.get("data") or {}).get("id")
    if not email_id:
        return Response(status_code=400, content="missing email_id")
    email = await _fetch_email(email_id)
    if not email:
        # Resend keeps the message; a retry can pick it up
        return Response(status_code=502, content="fetch failed")
    return await ingest_received_email(get_db(), email, email_id)
