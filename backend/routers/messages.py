"""
Messages router - handles conversations and messages
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Request, Response
from bson import ObjectId
from datetime import datetime, timezone
from typing import Optional, List
import logging
import random
import base64
import os
import re
import urllib.parse
from utils.contact_activity import log_contact_event
import asyncio

from models import Message, MessageCreate
from routers.database import get_db, get_data_filter, increment_user_stat
from utils.text_sanitize import no_em_dash, clean_ai_text
from services.twilio_service import send_sms, get_twilio_status, normalize_phone, TWILIO_PHONE_NUMBER

router = APIRouter(prefix="/messages", tags=["Messages"])
logger = logging.getLogger(__name__)

# Short TTL cache for conversations list — bounded TTLCache prevents memory leaks
import time as _time
from cachetools import TTLCache
_conv_cache: TTLCache = TTLCache(maxsize=500, ttl=10)  # max 500 user entries, auto-evicts

# Import centralized event type resolution
from utils.event_types import resolve_event_type, LINK_TYPE_TO_EVENT


async def substitute_template_vars(content: str, user_id: str, contact_id: str = None) -> str:
    """Replace template variables like {first_name}, {review_link}, etc. in message content."""
    if '{' not in content:
        return content
    
    db = get_db()
    
    # Load contact data
    contact = None
    if contact_id:
        try:
            contact = await db.contacts.find_one({"_id": ObjectId(contact_id)})
        except Exception:
            pass
    
    first_name = contact.get('first_name', '') if contact else ''
    last_name = contact.get('last_name', '') if contact else ''
    full_name = f"{first_name} {last_name}".strip()
    phone = contact.get('phone', '') if contact else ''
    
    # Load sender (user) data for their profile fields
    user_doc = None
    try:
        user_doc = await db.users.find_one({"_id": ObjectId(user_id)})
    except Exception:
        pass
    
    review_url = ''
    company = ''
    sender_name = ''
    if user_doc:
        review_url = user_doc.get('review_url', '') or ''
        company = user_doc.get('company', '') or ''
        sender_name = user_doc.get('name', '') or ''
        # Also check store-level review links
        if not review_url:
            store_id = user_doc.get('store_id')
            if store_id:
                store = await db.stores.find_one({"_id": ObjectId(store_id)})
                if store:
                    review_links = store.get('review_links', {})
                    review_url = review_links.get('google', '') or review_links.get('yelp', '') or ''
    
    # Perform substitutions
    replacements = {
        '{first_name}': first_name,
        '{last_name}': last_name,
        '{name}': full_name,
        '{phone}': phone,
        '{review_link}': review_url,
        '{review_url}': review_url,
        '{company}': company,
        '{sender_name}': sender_name,
        '{sender}': sender_name,
    }
    
    result = content
    for placeholder, value in replacements.items():
        result = result.replace(placeholder, value)
    
    return result


# Email validation  - reject "None", "null", empty strings, and non-email values
_EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')

def _clean_email(val) -> str:
    """Return a valid email string or empty string. Filters out 'None', 'null', etc."""
    if not val or not isinstance(val, str):
        return ''
    val = val.strip()
    if val.lower() in ('none', 'null', 'n/a', 'undefined', ''):
        return ''
    if not _EMAIL_RE.match(val):
        return ''
    return val

def _get_contact_email(contact: dict) -> str:
    """Extract a valid email from a contact document, checking both email fields."""
    if not contact:
        return ''
    return _clean_email(contact.get('email')) or _clean_email(contact.get('email_work'))


# AI suggestion templates
AI_SUGGESTIONS = [
    "Thanks for reaching out! I'll get back to you shortly.",
    "Great question! Let me check on that for you.",
    "I appreciate your interest! When would be a good time to chat?",
    "Thanks for the update! I'll follow up with you soon.",
    "That sounds great! Let's schedule a time to discuss further.",
]

# AI Outcome types that require salesperson attention
AI_OUTCOMES = {
    "appointment_set": {"label": "Appointment Set", "priority": 1, "icon": "calendar"},
    "callback_requested": {"label": "Callback Requested", "priority": 2, "icon": "call"},
    "needs_assistance": {"label": "Needs Help", "priority": 3, "icon": "hand-left"},
    "hot_lead": {"label": "Hot Lead", "priority": 4, "icon": "flame"},
    "question_asked": {"label": "Question", "priority": 5, "icon": "help-circle"},
    "escalated": {"label": "Help", "priority": 6, "icon": "alert-circle"},
}

@router.get("/ai-outcomes")
async def get_ai_outcomes():
    """Get list of AI outcome types"""
    return AI_OUTCOMES

@router.get("/conversations/{user_id}")
async def get_conversations(user_id: str, personal_only: bool = True):
    """
    Get conversations for a user.
    
    By default (personal_only=True), shows only the user's own conversations.
    Set personal_only=False to see all accessible conversations (for admins managing team).
    """
    cache_key = f"{user_id}:{personal_only}"
    cached = _conv_cache.get(cache_key)
    if cached is not None:
        return cached

    db = get_db()
    
    if personal_only:
        # Show only this user's personal conversations
        base_filter = {"user_id": user_id}
    else:
        # Show all conversations the user has access to (admin view)
        base_filter = await get_data_filter(user_id)
    
    # Sort by: AI outcomes first (by priority), then unread, then by recency
    conversations = await db.conversations.find(base_filter).sort([
        ("ai_outcome_priority", 1),  # Lower priority number = more important
        ("unread", -1),  # Unread first
        ("last_message_at", -1)  # Then by recency
    ]).limit(100).to_list(100)
    
    if not conversations:
        return []
    
    # Batch-load contacts and last messages to avoid N+1 queries
    contact_ids = set()
    conv_ids = []
    for conv in conversations:
        conv['_id'] = str(conv['_id'])
        conv_ids.append(conv['_id'])
        cid = conv.get('contact_id')
        if cid:
            contact_ids.add(cid)
    
    # Single query for all contacts
    contact_map = {}
    if contact_ids:
        oid_list = []
        for cid in contact_ids:
            try:
                oid_list.append(ObjectId(cid))
            except Exception:
                pass
        if oid_list:
            contacts_cursor = db.contacts.find(
                {"_id": {"$in": oid_list}},
                {"photo": 0}
            )
            async for contact in contacts_cursor:
                cid_str = str(contact['_id'])
                full_name = f"{contact.get('first_name','')} {contact.get('last_name','')}".strip()
                # If stored name is a placeholder, use contact.name or phone
                if not full_name or full_name in ("Contact", "Unknown"):
                    full_name = contact.get("name", "") or contact.get("phone", "") or "Unknown"
                contact_map[cid_str] = {
                    "id": cid_str,
                    "name": full_name,
                    "phone": contact.get('phone',''),
                    "email": _get_contact_email(contact),
                    "photo": contact.get('photo_thumbnail') or contact.get('photo_url'),
                    "photo_thumbnail": contact.get('photo_thumbnail'),
                    "photo_url": contact.get('photo_url'),
                }
    
    # Single query for last messages — match both string and ObjectId conversation_id formats
    last_msg_map = {}
    if conv_ids:
        # Include both ObjectId and string versions to handle mixed storage formats
        conv_id_strings = [str(c) for c in conv_ids]
        pipeline = [
            {"$match": {"conversation_id": {"$in": conv_ids + conv_id_strings}}},
            {"$sort": {"timestamp": -1}},
            {"$group": {
                "_id": "$conversation_id",
                "content": {"$first": "$content"},
                "timestamp": {"$first": "$timestamp"},
                "sender": {"$first": "$sender"},
                "channel": {"$first": "$channel"},
                "type": {"$first": "$type"},
            }}
        ]
        async for msg in db.messages.aggregate(pipeline):
            # Store under both string and ObjectId key for lookup
            key = msg['_id']
            entry = {
                "content": msg.get('content') or ('[Call]' if msg.get('type') == 'call_log' or msg.get('channel') == 'voice' else ''),
                "timestamp": msg['timestamp'],
                "sender": msg['sender'],
            }
            last_msg_map[key]       = entry
            last_msg_map[str(key)]  = entry
    
    # Speed-to-lead: flag internet-lead conversations still waiting on a human reply
    lead_conv_ids = [c['_id'] for c in conversations if c.get('is_internet_lead')]
    if lead_conv_ids:
        from routers.lead_intake import _first_human_replies
        replied = await _first_human_replies(db, lead_conv_ids)
        for conv in conversations:
            if conv.get('is_internet_lead'):
                conv['awaiting_first_reply'] = conv['_id'] not in replied

    # Assemble results
    result = []
    for conv in conversations:
        cid = conv.get('contact_id')
        if cid and cid in contact_map:
            conv['contact'] = contact_map[cid]
        
        if conv['_id'] in last_msg_map:
            conv['last_message'] = last_msg_map[conv['_id']]
        
        result.append(conv)
    
    _conv_cache[cache_key] = result
    return result

@router.get("/conversations/{user_id}/{conversation_id}")
async def get_conversation(user_id: str, conversation_id: str):
    """Get a specific conversation with messages"""
    base_filter = await get_data_filter(user_id)
    
    conv = await get_db().conversations.find_one({
        "$and": [{"_id": ObjectId(conversation_id)}, base_filter]
    })
    
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    conv['_id'] = str(conv['_id'])
    
    # Get messages
    messages = await get_db().messages.find(
        {"conversation_id": conversation_id}
    ).sort("timestamp", 1).limit(500).to_list(500)
    
    conv['messages'] = [{
        "_id": str(m['_id']),
        "content": m['content'],
        "sender": m['sender'],
        "timestamp": m['timestamp'],
        "status": m.get('status', 'sent'),
        "has_media": m.get('has_media', False),
        "media_urls": m.get('media_urls', []),
        "ai_generated": m.get('ai_generated', False),
        "intent_detected": m.get('intent_detected'),
        "direction": m.get('direction', 'outbound'),
        "event_type": m.get('event_type', ''),
        "card_type": m.get('card_type', ''),
        "channel": m.get('channel', '')
    } for m in messages]
    
    return conv

@router.post("/conversations/{user_id}")
async def create_conversation(user_id: str, data: dict):
    """Create or get existing conversation with a contact. Always stamps rep_phone."""
    db = get_db()
    contact_id    = data.get('contact_id')
    contact_phone = data.get('contact_phone')

    # Look up the rep's Twilio number — this becomes the permanent routing key
    rep = await db.users.find_one({"_id": ObjectId(user_id)}, {"twilio_number": 1, "mvpline_number": 1})
    rep_phone = (rep or {}).get("twilio_number") or (rep or {}).get("mvpline_number")

    # Look up contact name from the contacts collection (source of truth)
    contact_name = data.get('contact_name', '')
    if not contact_name and contact_id:
        try:
            c = await db.contacts.find_one({"_id": ObjectId(contact_id)}, {"name": 1, "first_name": 1, "last_name": 1})
            if c:
                contact_name = c.get("name") or f"{c.get('first_name','')} {c.get('last_name','')}".strip()
        except Exception:
            pass

    # Try to find existing conversation — by rep_phone+contact_phone (preferred) or contact_id
    existing = None
    if rep_phone and contact_phone:
        existing = await db.conversations.find_one({"rep_phone": rep_phone, "contact_phone": contact_phone})
    if not existing and contact_id:
        existing = await db.conversations.find_one({"user_id": user_id, "contact_id": contact_id})
    if existing:
        # Backfill rep_phone and contact_name if missing
        updates = {}
        if rep_phone and not existing.get("rep_phone"):
            updates["rep_phone"] = rep_phone
        if contact_name and (not existing.get("contact_name") or existing.get("contact_name") in ("Contact", "Unknown")):
            updates["contact_name"] = contact_name
        if updates:
            await db.conversations.update_one({"_id": existing["_id"]}, {"$set": updates})
        existing['_id'] = str(existing['_id'])
        return existing

    # Create new conversation — always with rep_phone for proper routing
    conv = {
        "user_id":       user_id,
        "rep_phone":     rep_phone,       # THE ROUTING KEY — which rep's Twilio number
        "contact_id":    contact_id,
        "contact_phone": contact_phone,
        "contact_name":  contact_name,
        "status":        "active",
        "ai_enabled":    False,
        "ai_mode":       "suggest",
        "ai_handled":    False,
        "ai_outcome":    None,
        "ai_outcome_priority": 999,
        "unread":        False,
        "unread_count":  0,
        "needs_assistance": False,
        "created_at":    datetime.now(timezone.utc),
        "last_message_at": datetime.now(timezone.utc),
    }
    result = await db.conversations.insert_one(conv)
    conv['_id'] = str(result.inserted_id)
    return conv

@router.post("/send/{user_id}/{conversation_id}")
async def send_message(user_id: str, conversation_id: str, message_data: MessageCreate):
    """Send a message in a conversation"""
    base_filter = await get_data_filter(user_id)
    
    # Verify conversation exists and user has access
    conv = await get_db().conversations.find_one({
        "$and": [{"_id": ObjectId(conversation_id)}, base_filter]
    })
    
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Get recipient phone number
    to_phone = conv.get('contact_phone')
    if not to_phone:
        # Try to get from contact
        contact = await get_db().contacts.find_one({"_id": ObjectId(conv['contact_id'])})
        if contact:
            to_phone = contact.get('phone')
    
    # Substitute template variables ({review_link}, {first_name}, etc.)
    contact_id = conv.get('contact_id', '')
    resolved_content = await substitute_template_vars(message_data.content, user_id, contact_id)
    
    # Create message record
    message = {
        "conversation_id": conversation_id,
        "content": resolved_content,
        "sender": "user",
        "sender_id": user_id,
        "user_id": user_id,
        "timestamp": datetime.now(timezone.utc),
        "status": "sending",
        "media_urls": []
    }
    
    # Add template tracking fields if present
    if message_data.template_id:
        message["template_id"] = message_data.template_id
    if message_data.template_type:
        message["template_type"] = message_data.template_type
    if message_data.template_name:
        message["template_name"] = message_data.template_name
    
    result = await get_db().messages.insert_one(message)
    message['_id'] = str(result.inserted_id)
    # Keyword auto-tagging (fire-and-forget)
    try:
        from services.keyword_tagging import schedule_keyword_tagging
        schedule_keyword_tagging(user_id, contact_id, resolved_content, "sms", message['_id'], conversation_id, sender="user")
    except Exception as kt_err:
        logger.warning(f"[KeywordTag] schedule failed: {kt_err}")
    # Invalidate conversation cache so sender sees the new message immediately
    _conv_cache.pop(f"{user_id}:True", None)
    _conv_cache.pop(f"{user_id}:False", None)

    # Clear "You're Needed" flags — rep is now responding
    # Also lower future escalation threshold to 1 (rep has been personally involved)
    try:
        conv_doc = await get_db().conversations.find_one(
            {"_id": ObjectId(conversation_id)},
            {"claimed": 1, "claimed_by": 1, "contact_id": 1}
        )
        await get_db().conversations.update_one(
            {"_id": ObjectId(conversation_id)},
            {"$set": {
                "needs_assistance":            False,
                "unanswered_customer_replies": 0,
                "rep_engaged":                 True,
                "rep_last_replied_at":         datetime.now(timezone.utc),
            }}
        )
        # Reset campaign enrollment reply_count so AI escalation threshold starts fresh.
        # Without this, a customer with 28 historical replies would trigger "You're Needed"
        # on their very next message, even if the rep just personally responded.
        contact_id_for_reset = (conv_doc or {}).get("contact_id") if conv_doc else None
        if contact_id_for_reset:
            await get_db().campaign_enrollments.update_many(
                {"contact_id": contact_id_for_reset, "status": {"$in": ["active", "paused"]}},
                {"$set": {"reply_count": 0}}
            )
        # Auto-claim in Team Inbox: first reply = claim (no button tap needed)
        if conv_doc and not conv_doc.get("claimed"):
            await get_db().conversations.update_one(
                {"_id": ObjectId(conversation_id)},
                {"$set": {
                    "claimed":    True,
                    "claimed_by": user_id,
                    "claimed_at": datetime.now(timezone.utc),
                }}
            )
            logger.info(f"[Inbox] Auto-claimed conversation {conversation_id} by {user_id} on first reply")
    except Exception:
        pass

    channel = message_data.channel or 'sms'

    if channel == 'email':
        # Send via Resend (email) with branded template
        contact = await get_db().contacts.find_one({"_id": ObjectId(conv.get('contact_id', ''))})
        contact_email = _get_contact_email(contact)
        
        if contact_email:
            try:
                import resend as resend_mod
                from utils.email_template import get_brand_context, build_branded_email
                RESEND_KEY = os.environ.get("RESEND_API_KEY")
                SENDER = os.environ.get("SENDER_EMAIL", "notifications@send.imonsocial.com")
                if RESEND_KEY:
                    resend_mod.api_key = RESEND_KEY
                    user_doc = await get_db().users.find_one({"_id": ObjectId(user_id)})
                    sender_name = user_doc.get('name', "I'm On Social") if user_doc else "I'm On Social"
                    contact_name = contact.get('name', contact.get('first_name', ''))
                    
                    brand = await get_brand_context(get_db(), user_id)
                    email_html = build_branded_email(message_data.content, brand, contact_name)
                    store_name = brand.get('store_name', "I'm On Social")
                    
                    email_result = await asyncio.to_thread(resend_mod.Emails.send, {
                        "from": f"{sender_name} at {store_name} <{SENDER}>",
                        "to": [contact_email],
                        "reply_to": user_doc.get('email', SENDER) if user_doc else SENDER,
                        "subject": f"Message from {sender_name} at {store_name}",
                        "html": email_html,
                    })
                    resend_id = email_result.get('id') if isinstance(email_result, dict) else getattr(email_result, 'id', str(email_result))
                    message['status'] = 'sent'
                    message['channel'] = 'email'
                    message['resend_id'] = resend_id
                    logger.info(f"[EMAIL] Sent to {contact_email} (resend_id={resend_id}): {message_data.content[:50]}...")
                else:
                    message['status'] = 'failed'
                    message['error'] = 'Email service not configured (RESEND_API_KEY missing)'
                    logger.error("[EMAIL] RESEND_API_KEY not set")
            except Exception as e:
                message['status'] = 'failed'
                message['error'] = str(e)
                logger.error(f"[EMAIL] Failed to {contact_email}: {e}", exc_info=True)
        else:
            message['status'] = 'failed'
            message['error'] = 'No email address for contact'
            logger.warning(f"[EMAIL] No email for contact in conversation {conversation_id}")
        
        await get_db().messages.update_one(
            {"_id": ObjectId(message['_id'])},
            {"$set": {
                "status": message['status'],
                "channel": "email",
                "resend_id": message.get('resend_id'),
                "error": message.get('error'),
            }}
        )
        
        # Log as contact event (both success and failure for audit trail)
        contact_id = conv.get('contact_id')
        if contact_id:
            event_type = "email_sent" if message['status'] == 'sent' else "email_failed"
            await get_db().contact_events.insert_one({
                "contact_id": str(contact_id),
                "user_id": user_id,
                "event_type": event_type,
                "channel": "email",
                "message_id": message['_id'],
                "content_preview": message_data.content[:100],
                "recipient": contact_email,
                "status": message['status'],
                "error": message.get('error'),
                "timestamp": datetime.now(timezone.utc),
            })
    elif channel == 'sms_personal':
        # User sending from their personal phone  - just log it, no Twilio needed
        message['status'] = 'sent'
        message['channel'] = 'sms_personal'
        
        # Determine event type: prefer explicit from frontend, then resolve dynamically
        if message_data.event_type:
            event_type = message_data.event_type
            logger.info(f"Using explicit event_type={event_type} from frontend")
        else:
            event_type = await resolve_event_type(message_data.content, get_db())
        
        # Set event_type on message dict so it's returned in the API response
        message['event_type'] = event_type
        
        logger.info(f"Personal SMS logged ({event_type}) for {to_phone}: {message_data.content[:50]}...")
        
        await get_db().messages.update_one(
            {"_id": ObjectId(message['_id'])},
            {"$set": {"status": "sent", "channel": "sms_personal", "event_type": event_type}}
        )
        
        # Log as contact event for activity tracking
        contact_id = conv.get('contact_id')
        if contact_id:
            event_doc = {
                "contact_id": str(contact_id),
                "user_id": user_id,
                "event_type": event_type,
                "channel": "sms_personal",
                "message_id": message['_id'],
                "content_preview": message_data.content[:100],
                "timestamp": datetime.now(timezone.utc),
            }
            # Store explicit title for custom card types so activity feed shows real name
            if message_data.event_title:
                event_doc["title"] = message_data.event_title
            await log_contact_event(get_db(), str(contact_id), event_doc)

            # Create per-contact short URLs for any tracked links in this message
            # This ensures click attribution works per-recipient, not just the first sender
            import re as _re_msgs
            short_codes = _re_msgs.findall(r'/api/s/([A-Za-z0-9]+)', message_data.content or '')
            if short_codes and contact_id:
                try:
                    from routers.short_urls import create_short_url, get_short_url_base
                    base = get_short_url_base()
                    for code in short_codes:
                        existing_doc = await get_db().short_urls.find_one({"short_code": code})
                        if existing_doc and not existing_doc.get("metadata", {}).get("contact_id"):
                            # Check if personal version already exists
                            personal = await get_db().short_urls.find_one({
                                "original_url": existing_doc["original_url"],
                                "user_id": user_id,
                                "metadata.contact_id": str(contact_id),
                            })
                            if not personal:
                                await create_short_url(
                                    original_url=existing_doc["original_url"],
                                    link_type=existing_doc.get("link_type", "campaign_link"),
                                    reference_id=code,
                                    user_id=user_id,
                                    metadata={**existing_doc.get("metadata", {}), "contact_id": str(contact_id)},
                                )
                except Exception:
                    pass
    elif to_phone:
        # Send via Twilio (SMS) — always use the rep's dedicated number
        message['channel'] = 'sms'
        # Look up the rep's dedicated Twilio number so we never send from a pooled number
        rep_twilio_number = None
        try:
            rep_doc = await get_db().users.find_one(
                {"_id": ObjectId(user_id)},
                {"twilio_number": 1, "mvpline_number": 1}
            )
            rep_twilio_number = (rep_doc or {}).get("twilio_number") or (rep_doc or {}).get("mvpline_number")
        except Exception:
            pass
        sms_result = await send_sms(to_phone, message_data.content, from_phone=rep_twilio_number)
        
        if sms_result.get('success'):
            message['status'] = 'sent'
            message['twilio_sid'] = sms_result.get('message_sid')
            logger.info(f"SMS sent to {to_phone}: {message_data.content[:50]}...")
        else:
            message['status'] = 'failed'
            message['error'] = sms_result.get('error')
            logger.error(f"SMS failed to {to_phone}: {sms_result.get('error')}")
        
        # Update message status in DB
        await get_db().messages.update_one(
            {"_id": ObjectId(message['_id'])},
            {"$set": {"status": message['status'], "twilio_sid": sms_result.get('message_sid')}}
        )

        # Log contact event for Twilio SMS
        contact_id = conv.get('contact_id')
        if contact_id:
            sms_event_type = "sms_sent" if message['status'] == 'sent' else "sms_failed"
            if message_data.event_type:
                sms_event_type = message_data.event_type
            else:
                resolved = await resolve_event_type(message_data.content, get_db())
                if resolved != 'personal_sms':
                    sms_event_type = resolved
            await get_db().contact_events.insert_one({
                "contact_id": str(contact_id),
                "user_id": user_id,
                "event_type": sms_event_type,
                "channel": "sms",
                "message_id": message['_id'],
                "content_preview": message_data.content[:100],
                "status": message['status'],
                "timestamp": datetime.now(timezone.utc),
            })
            # Tag short URLs with contact_id for click attribution
            import re as _re
            short_codes = _re.findall(r'/api/s/([A-Za-z0-9]+)', message_data.content or '')
            if short_codes:
                await get_db().short_urls.update_many(
                    {"short_code": {"$in": short_codes}, "metadata.contact_id": {"$exists": False}},
                    {"$set": {"metadata.contact_id": str(contact_id),
                              "metadata.sent_at": datetime.now(timezone.utc).isoformat()}},
                )
    else:
        message['status'] = 'sent'
        logger.warning(f"No phone number for conversation {conversation_id}")
    
    # Update conversation
    await get_db().conversations.update_one(
        {"_id": ObjectId(conversation_id)},
        {"$set": {"last_message_at": datetime.now(timezone.utc)}}
    )
    
    # Track stat
    await increment_user_stat(user_id, "messages_sent")
    
    # Fire-and-forget milestone check for push notifications
    try:
        import asyncio as _aio
        from routers.contact_events import _quick_milestone_check
        _aio.create_task(_quick_milestone_check(user_id))
    except Exception:
        pass
    
    return message


@router.post("/twilio-send")
async def send_via_twilio(request: Request):
    """
    Send via user's dedicated Twilio number. Called instead of native SMS.
    Falls back gracefully — frontend shows native SMS if this fails.
    """
    from services.twilio_service import send_sms
    db   = get_db()
    data = await request.json()
    user_id    = data.get("user_id", "")
    to_phone   = data.get("to", "")
    body       = data.get("body", "")
    contact_id = data.get("contact_id")
    event_type = data.get("event_type", "personal_sms")
    media_urls = data.get("media_urls") or []          # ← MMS support
    if not to_phone or not body:
        raise HTTPException(status_code=400, detail="to and body are required")
    # Always use the rep's dedicated Twilio number
    rep_twilio_number = None
    try:
        rep_doc = await db.users.find_one(
            {"_id": ObjectId(user_id)},
            {"twilio_number": 1, "mvpline_number": 1}
        )
        rep_twilio_number = (rep_doc or {}).get("twilio_number") or (rep_doc or {}).get("mvpline_number")
    except Exception:
        pass
    result = await send_sms(to_phone, body, media_urls=media_urls if media_urls else None, from_phone=rep_twilio_number)
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Send failed"))
    now = datetime.utcnow()
    from services.twilio_service import normalize_phone
    # Normalize phone before lookup — prevents duplicate conversations from format mismatches
    to_phone_normalized = normalize_phone(to_phone) if to_phone else to_phone
    # Find conversation — search both normalized and raw formats
    conv = await db.conversations.find_one({"rep_phone": rep_twilio_number, "contact_phone": to_phone_normalized})
    if not conv:
        # Try raw format fallback
        digits = ''.join(c for c in to_phone if c.isdigit())
        last10 = digits[-10:] if len(digits) >= 10 else digits
        conv = await db.conversations.find_one({
            "$and": [
                {"$or": [{"user_id": user_id}, {"user_id": ObjectId(user_id) if len(user_id) == 24 else user_id}]},
                {"contact_phone": {"$regex": last10, "$options": "i"}} if last10 else {"contact_phone": to_phone}
            ]
        })
    if not conv:
        r = await db.conversations.insert_one({
            "user_id": user_id,
            "rep_phone": rep_twilio_number,
            "contact_id": contact_id,
            "contact_phone": to_phone_normalized,  # Always store normalized
            "status": "active",
            "created_at": now,
            "updated_at": now,
            "last_message_at": now,
        })
        conv_id = str(r.inserted_id)
    else:
        conv_id = str(conv["_id"])
        # ── CRITICAL: Reset YOU'RE NEEDED flags when rep manually replies ──────
        await db.conversations.update_one(
            {"_id": conv["_id"]},
            {"$set": {
                "last_message_at":         now,
                "needs_assistance":         False,
                "unanswered_customer_replies": 0,
                "rep_engaged":              True,
                "rep_last_replied_at":      now,
            }}
        )
        # Reset campaign enrollment reply_count so escalation threshold resets fresh
        if contact_id:
            await db.campaign_enrollments.update_many(
                {"contact_id": contact_id, "status": {"$in": ["active", "paused"]}},
                {"$set": {"reply_count": 0}}
            )
    await db.messages.insert_one({
        "conversation_id": conv_id,
        "user_id": user_id,
        "contact_id": contact_id,
        "content": body,
        "direction": "outbound",
        "channel": "sms",
        "sender": "user",
        "twilio_sid": result.get("message_sid"),
        "status": "sent" if not result.get("mock") else "sent_mock",
        "event_type": event_type,
        "has_media": bool(media_urls),
        "media_urls": media_urls,
        "timestamp": now,
    })
    return {"success": True, "message_sid": result.get("message_sid"), "mock": result.get("mock", False), "conversation_id": conv_id}


@router.post("/send-mms/{user_id}/{conversation_id}")
async def send_mms_message(
    user_id: str,
    conversation_id: str,
    content: str = Form(default=""),
    media: UploadFile = File(...)
):
    """Send an MMS message with media attachment"""
    base_filter = await get_data_filter(user_id)
    db = get_db()
    
    # Try to find conversation - it might be a conversation_id or contact_id
    conv = await db.conversations.find_one({
        "$and": [{"_id": ObjectId(conversation_id)}, base_filter]
    })
    
    # If not found, try to find by contact_id
    if not conv:
        conv = await db.conversations.find_one({
            "user_id": user_id,
            "contact_id": conversation_id
        })
        
        # If still not found, try to create conversation from contact
        if not conv:
            contact = await db.contacts.find_one({"_id": ObjectId(conversation_id)})
            if contact:
                # Look up rep's Twilio number for proper routing key
                rep_doc = await db.users.find_one({"_id": ObjectId(user_id)}, {"twilio_number": 1, "mvpline_number": 1})
                rep_phone_for_conv = (rep_doc or {}).get("twilio_number") or (rep_doc or {}).get("mvpline_number")
                cname = f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip() or contact.get('name', '')
                conv = {
                    "user_id":       user_id,
                    "rep_phone":     rep_phone_for_conv,   # Routing key
                    "contact_id":    conversation_id,
                    "contact_phone": contact.get('phone'),
                    "contact_name":  cname,
                    "status":        "active",
                    "ai_enabled":    False,
                    "ai_mode":       "suggest",
                    "created_at":    datetime.now(timezone.utc),
                    "last_message_at": datetime.now(timezone.utc)
                }
                result = await db.conversations.insert_one(conv)
                conv['_id'] = result.inserted_id
                logger.info(f"[Messages] Created conversation for contact {conversation_id} with rep_phone={rep_phone_for_conv}")
            else:
                raise HTTPException(status_code=404, detail="Contact not found")
    
    # Get recipient phone - try conversation first, then contact
    to_phone = conv.get('contact_phone')
    contact_id = conv.get('contact_id')
    
    if not to_phone and contact_id:
        contact = await db.contacts.find_one({"_id": ObjectId(contact_id)})
        if contact:
            to_phone = contact.get('phone')
            # Update conversation with phone for future use
            if to_phone:
                await db.conversations.update_one(
                    {"_id": conv['_id']},
                    {"$set": {"contact_phone": to_phone}}
                )
    
    if not to_phone:
        raise HTTPException(status_code=400, detail="No phone number for this contact. Please add a phone number first.")
    
    # Normalize phone number
    from services.twilio_service import normalize_phone
    to_phone = normalize_phone(to_phone)
    
    # Get the actual conversation ID
    actual_conv_id = str(conv['_id'])
    
    # Read and store media file in object storage (not MongoDB)
    media_content = await media.read()
    media_type = media.content_type or 'image/jpeg'
    
    # Upload to object storage with compression
    from utils.image_storage import upload_image
    upload_result = await upload_image(media_content, prefix="mms", entity_id=actual_conv_id)
    
    if upload_result:
        public_url = os.environ.get("PUBLIC_FACING_URL", os.environ.get("APP_URL", "https://app.imonsocial.com"))
        # Use absolute URLs everywhere — relative paths can't be loaded by the mobile app
        media_image_url = f"{public_url}/api/images/{upload_result['original_path']}?format=jpeg"
        display_url     = f"{public_url}/api/images/{upload_result['original_path']}"
        thumb_url       = f"{public_url}/api/images/{upload_result['thumbnail_path']}"
    else:
        # Fallback: store in MongoDB
        media_base64 = base64.b64encode(media_content).decode('utf-8')
        media_data_url = f"data:{media_type};base64,{media_base64}"
        media_doc = {
            "conversation_id": actual_conv_id,
            "user_id": user_id,
            "content_type": media_type,
            "filename": media.filename,
            "data": media_data_url,
            "size_bytes": len(media_content),
            "created_at": datetime.now(timezone.utc)
        }
        media_result = await db.media.insert_one(media_doc)
        media_id = str(media_result.inserted_id)
        public_url = os.environ.get("PUBLIC_FACING_URL", os.environ.get("APP_URL", "https://app.imonsocial.com"))
        # Store the API endpoint URL — NOT the raw base64 (too large for expo-image)
        media_image_url = f"{public_url}/api/messages/media/{media_id}"
        display_url     = media_image_url
        thumb_url       = media_image_url
    
    # Create message record with object storage URLs
    message = {
        "conversation_id": actual_conv_id,
        "content": content,
        "sender": "user",
        "timestamp": datetime.now(timezone.utc),
        "status": "sending",
        "media_urls": [display_url],
        "has_media": True
    }
    
    result = await db.messages.insert_one(message)
    message['_id'] = str(result.inserted_id)
    
    # Send via Twilio with public URL — use rep's dedicated number
    media_urls = [media_image_url]
    rep_twilio_number = None
    try:
        rep_doc = await db.users.find_one(
            {"_id": ObjectId(user_id)},
            {"twilio_number": 1, "mvpline_number": 1}
        )
        rep_twilio_number = (rep_doc or {}).get("twilio_number") or (rep_doc or {}).get("mvpline_number")
    except Exception:
        pass
    sms_result = await send_sms(to_phone, content or "", media_urls, from_phone=rep_twilio_number)
    
    if sms_result.get('success'):
        message['status'] = 'sent'
        message['twilio_sid'] = sms_result.get('message_sid')
        logger.info(f"MMS sent to {to_phone} with media")
    else:
        message['status'] = 'failed'
        message['error'] = sms_result.get('error')
        logger.error(f"MMS failed: {sms_result.get('error')}")
    
    # Update message status
    await db.messages.update_one(
        {"_id": ObjectId(message['_id'])},
        {"$set": {"status": message['status'], "twilio_sid": sms_result.get('message_sid')}}
    )
    
    # Update conversation
    await db.conversations.update_one(
        {"_id": conv['_id']},
        {"$set": {"last_message_at": datetime.now(timezone.utc)}}
    )
    
    await increment_user_stat(user_id, "messages_sent")
    
    # Return with actual conversation ID so frontend can update
    message['conversation_id'] = actual_conv_id
    return message


@router.get("/media/{media_id}")
async def get_media(media_id: str):
    """Get media file for MMS delivery"""
    from fastapi.responses import Response
    
    media_doc = await get_db().media.find_one({"_id": ObjectId(media_id)})
    
    if not media_doc:
        raise HTTPException(status_code=404, detail="Media not found")
    
    # Decode base64 data
    data_url = media_doc.get('data', '')
    if data_url.startswith('data:'):
        # Parse data URL
        header, encoded = data_url.split(',', 1)
        content_type = header.split(':')[1].split(';')[0]
        media_bytes = base64.b64decode(encoded)
        
        return Response(content=media_bytes, media_type=content_type)
    
    raise HTTPException(status_code=400, detail="Invalid media format")


@router.get("/twilio-status")
async def twilio_status():
    """Check Twilio configuration status"""
    return await get_twilio_status()

@router.put("/conversation/{conversation_id}/archive")
async def archive_conversation(conversation_id: str):
    """Archive a conversation"""
    result = await get_db().conversations.update_one(
        {"_id": ObjectId(conversation_id)},
        {"$set": {"status": "archived", "archived_at": datetime.now(timezone.utc)}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    return {"message": "Conversation archived"}


@router.put("/conversation/{conversation_id}/restore")
async def restore_conversation(conversation_id: str):
    """Restore an archived conversation"""
    result = await get_db().conversations.update_one(
        {"_id": ObjectId(conversation_id)},
        {"$set": {"status": "active"}, "$unset": {"archived_at": ""}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    return {"message": "Conversation restored"}



@router.post("/merge-duplicates/{user_id}")
async def merge_duplicate_conversations_for_user(user_id: str):
    """
    Find and merge duplicate conversations for a user.
    Duplicates = same (user_id, contact_phone) with different conversation IDs.
    Keeps the conversation with the most messages; moves all messages into it.
    """
    db = get_db()
    pipeline = [
        {"$match": {"user_id": user_id, "contact_phone": {"$exists": True, "$ne": None}}},
        {"$group": {
            "_id": "$contact_phone",
            "conv_ids": {"$push": "$_id"},
            "count": {"$sum": 1},
        }},
        {"$match": {"count": {"$gt": 1}}},
    ]
    groups = await db.conversations.aggregate(pipeline).to_list(100)
    merged = 0
    for g in groups:
        convs = await db.conversations.find(
            {"_id": {"$in": g["conv_ids"]}}
        ).sort("last_message_at", -1).to_list(10)
        if len(convs) < 2:
            continue
        # Keep the most recently active conversation
        keeper = convs[0]
        dupes  = convs[1:]
        keeper_id = str(keeper["_id"])
        # Backfill rep_phone on keeper if missing
        if not keeper.get("rep_phone"):
            rep = await db.users.find_one({"_id": ObjectId(user_id)}, {"twilio_number": 1, "mvpline_number": 1})
            rep_ph = (rep or {}).get("twilio_number") or (rep or {}).get("mvpline_number")
            if rep_ph:
                await db.conversations.update_one({"_id": keeper["_id"]}, {"$set": {"rep_phone": rep_ph}})
        for dupe in dupes:
            dupe_id = str(dupe["_id"])
            # Move all messages from dupe → keeper
            await db.messages.update_many(
                {"conversation_id": dupe_id},
                {"$set": {"conversation_id": keeper_id}}
            )
            # Delete the duplicate
            await db.conversations.delete_one({"_id": dupe["_id"]})
            merged += 1
            logger.info(f"[Merge] Merged {dupe_id} → {keeper_id} for phone {g['_id']}")
    return {"merged": merged, "groups_processed": len(groups)}


async def merge_conversations(data: dict):
    """
    Merge two conversations into one — moves all messages from the secondary
    conversation into the primary, then closes the secondary.
    Primary = the conversation to KEEP (with the real name / best contact).
    Secondary = the duplicate conversation to close/absorb.
    """
    db = get_db()
    primary_id   = data.get("primary_id", "")
    secondary_id = data.get("secondary_id", "")

    if not primary_id or not secondary_id:
        raise HTTPException(status_code=400, detail="primary_id and secondary_id required")
    if primary_id == secondary_id:
        raise HTTPException(status_code=400, detail="Cannot merge a conversation with itself")

    try:
        primary   = await db.conversations.find_one({"_id": ObjectId(primary_id)})
        secondary = await db.conversations.find_one({"_id": ObjectId(secondary_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid conversation ID")

    if not primary or not secondary:
        raise HTTPException(status_code=404, detail="One or both conversations not found")

    # Already merged? Return success instead of error
    if secondary.get("merged_into") == primary_id:
        return {"status": "already_merged"}

@router.post("/admin/cleanup-all-conversations")
async def cleanup_all_conversations(request: Request):
    """
    Super-admin: backfill rep_phone + fix contact names + merge duplicates.
    """
    db = get_db()
    x_user_id = request.headers.get("X-User-ID")
    user = await db.users.find_one({"_id": ObjectId(x_user_id)}, {"role": 1})
    if not user or user.get("role") not in ("super_admin", "org_admin"):
        raise HTTPException(status_code=403, detail="Super admin required")

    fixed_names   = 0
    backfilled    = 0
    total_merged  = 0

    # ── Step 1: Fix contact names ──────────────────────────────────────────────
    # Any conversation where contact_name is null/empty/"Contact"/"Unknown"/Lead(XXXX)
    bad_name_convs = await db.conversations.find({
        "$or": [
            {"contact_name": {"$exists": False}},   # missing field entirely
            {"contact_name": None},
            {"contact_name": ""},
            {"contact_name": "Contact"},
            {"contact_name": "Unknown"},
            {"contact_name": {"$regex": "^Lead \\("}},
        ]
    }).to_list(1000)

    for conv in bad_name_convs:
        contact_phone = conv.get("contact_phone")
        user_id = str(conv.get("user_id", ""))
        contact_id = conv.get("contact_id")
        new_name = None

        # Try by contact_id first
        if contact_id:
            try:
                c = await db.contacts.find_one(
                    {"$or": [{"_id": ObjectId(str(contact_id))}, {"_id": str(contact_id)}]},
                    {"name": 1, "first_name": 1, "last_name": 1}
                )
                if c:
                    new_name = c.get("name") or f"{c.get('first_name','')} {c.get('last_name','')}".strip()
            except Exception:
                pass

        # Try by phone in the user's contacts
        if not new_name and contact_phone and user_id:
            phone_variants = [contact_phone, contact_phone.lstrip("+"), "+1" + contact_phone.lstrip("+1")]
            c = await db.contacts.find_one({
                "user_id": user_id,
                "phone": {"$in": phone_variants},
                "name": {"$exists": True, "$ne": None, "$not": {"$regex": "^Lead \\("}}
            })
            if not c:
                # Try across all users
                c = await db.contacts.find_one({
                    "phone": {"$in": phone_variants},
                    "name": {"$exists": True, "$ne": None, "$not": {"$regex": "^Lead \\("}}
                })
            if c:
                new_name = c.get("name") or f"{c.get('first_name','')} {c.get('last_name','')}".strip()

        if new_name and new_name not in ("Contact", "Unknown"):
            await db.conversations.update_one(
                {"_id": conv["_id"]},
                {"$set": {"contact_name": new_name}}
            )
            fixed_names += 1

    # ── Step 2: Backfill rep_phone ─────────────────────────────────────────────
    all_convs_no_rep = await db.conversations.find(
        {"$or": [{"rep_phone": {"$exists": False}}, {"rep_phone": None}, {"rep_phone": ""}]},
        {"_id": 1, "user_id": 1}
    ).to_list(2000)

    user_phone_cache = {}
    for conv in all_convs_no_rep:
        uid = str(conv.get("user_id", ""))
        if not uid:
            continue
        if uid not in user_phone_cache:
            try:
                rep = await db.users.find_one(
                    {"$or": [{"_id": ObjectId(uid)}, {"_id": uid}]},
                    {"twilio_number": 1, "mvpline_number": 1}
                )
                user_phone_cache[uid] = (rep or {}).get("twilio_number") or (rep or {}).get("mvpline_number")
            except Exception:
                user_phone_cache[uid] = None
        rep_phone = user_phone_cache[uid]
        if rep_phone:
            await db.conversations.update_one(
                {"_id": conv["_id"]},
                {"$set": {"rep_phone": rep_phone}}
            )
            backfilled += 1

    # ── Step 3: Merge duplicates (same user_id + contact_phone) ───────────────
    all_users = await db.users.find({}, {"_id": 1}).to_list(500)
    for u in all_users:
        uid = str(u["_id"])
        pipeline = [
            {"$match": {"$or": [{"user_id": uid}, {"user_id": ObjectId(uid)}], "contact_phone": {"$exists": True, "$ne": None}}},
            {"$group": {"_id": "$contact_phone", "conv_ids": {"$push": "$_id"}, "count": {"$sum": 1}}},
            {"$match": {"count": {"$gt": 1}}},
        ]
        groups = await db.conversations.aggregate(pipeline).to_list(100)
        for g in groups:
            convs = await db.conversations.find(
                {"_id": {"$in": g["conv_ids"]}}
            ).sort("last_message_at", -1).to_list(10)
            if len(convs) < 2:
                continue
            keeper    = convs[0]
            keeper_id = str(keeper["_id"])
            for dupe in convs[1:]:
                dupe_id = str(dupe["_id"])
                await db.messages.update_many({"conversation_id": dupe_id}, {"$set": {"conversation_id": keeper_id}})
                await db.conversations.delete_one({"_id": dupe["_id"]})
                total_merged += 1

    logger.info(f"[Cleanup] Fixed {fixed_names} names, backfilled {backfilled} rep_phones, merged {total_merged} duplicates")
    return {
        "status": "complete",
        "contact_names_fixed": fixed_names,
        "conversations_backfilled_with_rep_phone": backfilled,
        "duplicate_conversations_merged": total_merged,
    }

    # Step 1: Backfill rep_phone on all conversations missing it
    backfilled = 0
    users = await db.users.find(
        {"$or": [{"twilio_number": {"$exists": True}}, {"mvpline_number": {"$exists": True}}]},
        {"_id": 1, "twilio_number": 1, "mvpline_number": 1}
    ).to_list(200)

    for u in users:
        uid = str(u["_id"])
        rep_phone = u.get("twilio_number") or u.get("mvpline_number")
        if not rep_phone:
            continue
        # Match both string and ObjectId user_id formats
        result = await db.conversations.update_many(
            {"$or": [{"user_id": uid}, {"user_id": ObjectId(uid)}], "rep_phone": {"$exists": False}},
            {"$set": {"rep_phone": rep_phone}}
        )
        if result.modified_count:
            backfilled += result.modified_count

    # Step 2: Merge duplicate conversations for all users
    total_merged = 0
    all_users = await db.users.find({}, {"_id": 1}).to_list(500)
    for u in all_users:
        uid = str(u["_id"])
        pipeline = [
            {"$match": {"$or": [{"user_id": uid}, {"user_id": ObjectId(uid)}], "contact_phone": {"$exists": True, "$ne": None}}},
            {"$group": {"_id": "$contact_phone", "conv_ids": {"$push": "$_id"}, "count": {"$sum": 1}}},
            {"$match": {"count": {"$gt": 1}}},
        ]
        groups = await db.conversations.aggregate(pipeline).to_list(100)
        for g in groups:
            convs = await db.conversations.find(
                {"_id": {"$in": g["conv_ids"]}}
            ).sort("last_message_at", -1).to_list(10)
            if len(convs) < 2:
                continue
            keeper = convs[0]
            keeper_id = str(keeper["_id"])
            for dupe in convs[1:]:
                dupe_id = str(dupe["_id"])
                await db.messages.update_many(
                    {"conversation_id": dupe_id},
                    {"$set": {"conversation_id": keeper_id}}
                )
                await db.conversations.delete_one({"_id": dupe["_id"]})
                total_merged += 1

    logger.info(f"[Cleanup] Backfilled {backfilled} conversations, merged {total_merged} duplicates")
    return {
        "status": "complete",
        "conversations_backfilled_with_rep_phone": backfilled,
        "duplicate_conversations_merged": total_merged,
    }


@router.get("/duplicate-check/{user_id}")
async def find_duplicate_conversations(user_id: str):
    """Find conversations with the same phone number — used for the merge UI."""
    db = get_db()
    convs = await db.conversations.find(
        {"user_id": user_id, "status": {"$nin": ["closed", "archived"]}},
        {"_id": 1, "contact_id": 1, "contact_name": 1, "contact_phone": 1, "last_message_at": 1, "status": 1}
    ).to_list(500)

    # Resolve real contact names for conversations showing generic placeholders
    contact_ids = [c.get("contact_id") for c in convs if c.get("contact_id") and not c.get("contact_name")]
    name_map: dict = {}
    if contact_ids:
        try:
            real_contacts = await db.contacts.find(
                {"_id": {"$in": [ObjectId(cid) for cid in contact_ids if ObjectId.is_valid(str(cid))]}},
                {"_id": 1, "name": 1, "first_name": 1, "last_name": 1}
            ).to_list(200)
            for rc in real_contacts:
                n = rc.get("name") or f"{rc.get('first_name','')} {rc.get('last_name','')}".strip()
                if n and n not in ("Contact", "Unknown"):
                    name_map[str(rc["_id"])] = n
        except Exception:
            pass

    # Group by phone number
    by_phone: dict = {}
    for c in convs:
        # Fill in real name if we found one
        if not c.get("contact_name") and c.get("contact_id"):
            c["contact_name"] = name_map.get(str(c["contact_id"]), "")

        phone = (c.get("contact_phone") or "").strip().replace(" ", "").replace("-", "")
        if not phone:
            continue
        phone_key = phone.lstrip("+").lstrip("1") if len(phone) >= 10 else phone
        if phone_key not in by_phone:
            by_phone[phone_key] = []
        c["_id"] = str(c["_id"])
        by_phone[phone_key].append(c)

    def _name_quality(c: dict) -> int:
        n = (c.get("contact_name") or "").strip()
        if not n or n in ("Contact", "Unknown", "New Lead") or n.startswith("Lead ("):
            return 0
        return 1

    duplicates = []
    for phone, group in by_phone.items():
        if len(group) > 1:
            group.sort(key=lambda x: (
                _name_quality(x),
                str(x.get("last_message_at") or "")
            ), reverse=True)
            duplicates.append({
                "phone":        phone,
                "count":        len(group),
                "conversations": group,
                "primary_id":   group[0]["_id"],
                "primary_name": group[0].get("contact_name") or f"...{phone[-4:]}",
            })

    return {"duplicates": duplicates, "total": len(duplicates)}



@router.put("/conversation/{conversation_id}/read")
async def mark_conversation_read(conversation_id: str):
    """Mark a conversation as read"""
    if not ObjectId.is_valid(conversation_id):
        raise HTTPException(status_code=400, detail="Invalid conversation ID")
    result = await get_db().conversations.update_one(
        {"_id": ObjectId(conversation_id)},
        {"$set": {"unread": False, "unread_count": 0}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    return {"message": "Conversation marked as read"}


@router.put("/conversation/{conversation_id}/unread")
async def mark_conversation_unread(conversation_id: str):
    """Mark a conversation as unread"""
    if not ObjectId.is_valid(conversation_id):
        raise HTTPException(status_code=400, detail="Invalid conversation ID")
    result = await get_db().conversations.update_one(
        {"_id": ObjectId(conversation_id)},
        {"$set": {"unread": True, "unread_count": 1}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    return {"message": "Conversation marked as unread"}


@router.delete("/conversation/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Delete a conversation and all its messages"""
    # Delete messages
    await get_db().messages.delete_many({"conversation_id": conversation_id})
    
    # Delete conversation
    result = await get_db().conversations.delete_one({"_id": ObjectId(conversation_id)})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    return {"message": "Conversation deleted"}


# ============= BULK ACTIONS =============

@router.post("/bulk/archive")
async def bulk_archive_conversations(data: dict):
    """Archive multiple conversations at once"""
    conversation_ids = data.get("conversation_ids", [])
    
    if not conversation_ids:
        raise HTTPException(status_code=400, detail="No conversation IDs provided")
    
    object_ids = [ObjectId(cid) for cid in conversation_ids]
    
    result = await get_db().conversations.update_many(
        {"_id": {"$in": object_ids}},
        {"$set": {"status": "archived", "archived_at": datetime.now(timezone.utc)}}
    )
    
    return {
        "message": f"{result.modified_count} conversations archived",
        "modified_count": result.modified_count
    }


@router.post("/bulk/restore")
async def bulk_restore_conversations(data: dict):
    """Restore multiple archived conversations at once"""
    conversation_ids = data.get("conversation_ids", [])
    
    if not conversation_ids:
        raise HTTPException(status_code=400, detail="No conversation IDs provided")
    
    object_ids = [ObjectId(cid) for cid in conversation_ids]
    
    result = await get_db().conversations.update_many(
        {"_id": {"$in": object_ids}},
        {"$set": {"status": "active"}, "$unset": {"archived_at": ""}}
    )
    
    return {
        "message": f"{result.modified_count} conversations restored",
        "modified_count": result.modified_count
    }


@router.post("/bulk/read")
async def bulk_mark_read(data: dict):
    """Mark multiple conversations as read"""
    conversation_ids = data.get("conversation_ids", [])
    
    if not conversation_ids:
        raise HTTPException(status_code=400, detail="No conversation IDs provided")
    
    object_ids = [ObjectId(cid) for cid in conversation_ids]
    
    result = await get_db().conversations.update_many(
        {"_id": {"$in": object_ids}},
        {"$set": {"unread": False, "unread_count": 0}}
    )
    
    return {
        "message": f"{result.modified_count} conversations marked as read",
        "modified_count": result.modified_count
    }


@router.post("/bulk/unread")
async def bulk_mark_unread(data: dict):
    """Mark multiple conversations as unread"""
    conversation_ids = data.get("conversation_ids", [])
    
    if not conversation_ids:
        raise HTTPException(status_code=400, detail="No conversation IDs provided")
    
    object_ids = [ObjectId(cid) for cid in conversation_ids]
    
    result = await get_db().conversations.update_many(
        {"_id": {"$in": object_ids}},
        {"$set": {"unread": True, "unread_count": 1}}
    )
    
    return {
        "message": f"{result.modified_count} conversations marked as unread",
        "modified_count": result.modified_count
    }


@router.post("/bulk/delete")
async def bulk_delete_conversations(data: dict):
    """Delete multiple conversations and their messages"""
    conversation_ids = data.get("conversation_ids", [])
    
    if not conversation_ids:
        raise HTTPException(status_code=400, detail="No conversation IDs provided")
    
    # Delete messages for all conversations
    await get_db().messages.delete_many({"conversation_id": {"$in": conversation_ids}})
    
    # Delete conversations
    object_ids = [ObjectId(cid) for cid in conversation_ids]
    result = await get_db().conversations.delete_many({"_id": {"$in": object_ids}})
    
    return {
        "message": f"{result.deleted_count} conversations deleted",
        "deleted_count": result.deleted_count
    }


@router.put("/conversations/{user_id}/{conversation_id}")
async def update_conversation(user_id: str, conversation_id: str, data: dict):
    """Update conversation settings (AI mode, status, etc.)"""
    db = get_db()
    allowed_fields = ['ai_enabled', 'ai_mode', 'status', 'unread', 'unread_count', 'needs_assistance', 'ai_handled', 'ai_outcome', 'ai_outcome_priority', 'ai_outcome_acknowledged', 'flagged']
    update_dict = {k: v for k, v in data.items() if k in allowed_fields}

    if 'ai_outcome' in update_dict:
        outcome = update_dict['ai_outcome']
        if outcome and outcome in AI_OUTCOMES:
            update_dict['ai_outcome_priority'] = AI_OUTCOMES[outcome]['priority']
            update_dict['ai_handled'] = True
        elif outcome is None:
            update_dict['ai_outcome_priority'] = 999

    if not update_dict:
        raise HTTPException(status_code=400, detail="No valid fields to update")

    # When AI is turned OFF — also clear the Waiting queue state so it
    # moves from Waiting → All and stops nagging the rep
    if update_dict.get('ai_mode') == 'off' or update_dict.get('ai_enabled') is False:
        update_dict['needs_assistance']         = False
        update_dict['unanswered_customer_replies'] = 0
        update_dict['rep_engaged']              = True

    # Try conversation lookup without strict user_id filter — our new routing
    # uses rep_phone as the primary key, so user_id may not always match.
    try:
        oid = ObjectId(conversation_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid conversation ID")

    result = await db.conversations.update_one(
        {"_id": oid},
        {"$set": update_dict}
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return {"message": "Conversation updated"}


@router.post("/schedule-delayed")
async def schedule_delayed_message(request: Request):
    """
    Schedule an automated SMS to send after a delay.
    Inserts into campaign_pending_sends queue — picked up by the scheduler every 5 min.
    Use for VCF → card link sequencing, SOLD wizard follow-ups, etc.
    """
    from datetime import timedelta
    data = await request.json()
    user_id    = data.get("user_id", "")
    to_phone   = data.get("to", "")
    body       = data.get("body", "")
    delay_s    = int(data.get("delay_seconds", 120))
    contact_id = data.get("contact_id", "")
    contact_name = data.get("contact_name", "")
    media_urls = data.get("media_urls", [])
    event_type = data.get("event_type", "sms_sent")

    if not user_id or not to_phone or not body:
        raise HTTPException(status_code=400, detail="user_id, to, body required")

    db = get_db()
    now = datetime.now(timezone.utc)
    send_at = now + timedelta(seconds=delay_s)
    # scheduler queries naive datetimes
    send_at_naive = send_at.replace(tzinfo=None)

    # Rep's dedicated Twilio number
    rep_phone = None
    try:
        rep_doc = await db.users.find_one({"_id": ObjectId(user_id)}, {"twilio_number": 1, "mvpline_number": 1})
        rep_phone = (rep_doc or {}).get("twilio_number") or (rep_doc or {}).get("mvpline_number")
    except Exception:
        pass

    # Enrich contact name if missing
    if not contact_name and contact_id:
        try:
            c = await db.contacts.find_one({"_id": ObjectId(contact_id)}, {"first_name": 1, "last_name": 1, "name": 1})
            if c:
                contact_name = c.get("name") or f"{c.get('first_name', '')} {c.get('last_name', '')}".strip()
        except Exception:
            pass

    doc = {
        "user_id":        user_id,
        "contact_id":     contact_id,
        "contact_name":   contact_name,
        "contact_phone":  to_phone,
        "rep_phone":      rep_phone,
        "message_template": body,
        "channel":        "sms",
        "delivery_mode":  "automated",
        "send_at":        send_at_naive,
        "status":         "pending",
        "step":           0,
        "enrollment_id":  "",
        "campaign_id":    "",
        "campaign_name":  "Direct Send",
        "media_urls":     media_urls,
        "event_type":     event_type,
        "created_at":     now,
        "type":           "direct_scheduled",
    }
    result = await db.campaign_pending_sends.insert_one(doc)
    logger.info(f"[ScheduleDelayed] Queued SMS to {to_phone} at {send_at.isoformat()} (id={result.inserted_id})")
    return {
        "status":          "scheduled",
        "send_at":         send_at.isoformat(),
        "pending_send_id": str(result.inserted_id),
    }


@router.get("/ai-suggest/{user_id}/{conversation_id}")
async def get_ai_suggestion(user_id: str, conversation_id: str):
    """Get AI-generated response suggestion (mocked)"""
    # In production, this would call OpenAI
    suggestion = random.choice(AI_SUGGESTIONS)
    return {"suggestion": suggestion}


@router.get("/conversation/{conversation_id}/info")
async def get_conversation_info(conversation_id: str):
    """Get conversation info including contact details and photo"""
    db = get_db()
    
    # Find conversation
    try:
        conv = await db.conversations.find_one({"_id": ObjectId(conversation_id)})
    except Exception:
        conv = await db.conversations.find_one({"_id": conversation_id})
    
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # ── Resolve AI mode — never default to False ───────────────────────────────
    # If ai_enabled is not explicitly stored, check if there are active enrollments
    # with auto_reply to determine the true state.
    stored_ai_mode    = conv.get("ai_mode") or ""
    stored_ai_enabled = conv.get("ai_enabled")   # None = unset (not explicitly off)
    if stored_ai_enabled is None:
        # Check if there's an active enrollment with AI mode set
        try:
            contact_id_check = conv.get("contact_id")
            if contact_id_check:
                enroll = await db.campaign_enrollments.find_one({
                    "contact_id": str(contact_id_check),
                    "status": {"$in": ["active", "paused"]},
                    "ai_assist_mode": {"$nin": ["off", None, ""]},
                })
                if enroll:
                    stored_ai_enabled = True
                    if not stored_ai_mode:
                        stored_ai_mode = enroll.get("ai_assist_mode", "auto_reply")
        except Exception:
            pass
    if stored_ai_enabled is None:
        stored_ai_enabled = False
    if not stored_ai_mode:
        stored_ai_mode = "off" if not stored_ai_enabled else "auto_reply"

    result = {
        "_id": str(conv["_id"]),
        "contact_name": conv.get("contact_name"),
        "contact_phone": conv.get("contact_phone"),
        "contact_email": conv.get("contact_email"),
        "contact_photo": None,
        "status": conv.get("status", "active"),
        "ai_mode":    stored_ai_mode,
        "ai_enabled": stored_ai_enabled,
    }

    # Speed-to-lead: waiting status for internet leads
    if conv.get("is_internet_lead"):
        from routers.lead_intake import _first_human_replies
        replied = await _first_human_replies(db, [str(conv["_id"])])
        ca = conv.get("created_at")
        result["is_internet_lead"] = True
        result["awaiting_first_reply"] = str(conv["_id"]) not in replied
        result["lead_received_at"] = ca.isoformat() if hasattr(ca, "isoformat") else ca
        result["lead_source_name"] = conv.get("lead_source_name")

    # ── Resolve best contact name + photo + email ──────────────────────────────
    contact_id = conv.get("contact_id")
    if contact_id:
        result["contact_id"] = str(contact_id)
        try:
            contact = await db.contacts.find_one({"_id": ObjectId(contact_id)}, {"photo": 0})
            if contact:
                result["contact_photo"] = contact.get("photo_thumbnail") or contact.get("photo_url")
                # Build full name and skip generic placeholders like "Contact" or "Lead (XXXX)"
                full = f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip()
                if not full or full in ("Contact", "Unknown"):
                    full = contact.get("name", "") or ""
                stored = result.get("contact_name") or ""
                # Use the contact's actual name if it's better than the stored one
                if full and full not in ("Contact", "Unknown") and len(full) > 2:
                    result["contact_name"] = full
                elif stored and stored not in ("Contact", "Unknown") and len(stored) > 2:
                    pass  # keep stored
                elif contact.get("phone"):
                    result["contact_name"] = contact["phone"]
                if not result["contact_email"]:
                    clean = _get_contact_email(contact)
                    if clean:
                        result["contact_email"] = clean
        except Exception:
            pass

    return result


@router.get("/thread/{conversation_id}")
async def get_thread_messages(conversation_id: str):
    """Get all messages for a conversation thread.
    Loads by contact_id so messages with mismatched conversation_ids are always included."""
    db = get_db()

    # Primary: get messages by conversation_id
    conv_ids = [conversation_id]
    contact_id_filter = None

    try:
        from bson import ObjectId as _OId
        conv = await db.conversations.find_one({"_id": _OId(conversation_id)})
        if conv:
            raw_cid = conv.get("contact_id")
            if raw_cid:
                contact_id_filter = str(raw_cid)
                # Also include sibling conversations for same contact
                siblings = await db.conversations.find(
                    {"contact_id": raw_cid, "_id": {"$ne": _OId(conversation_id)}},
                    {"_id": 1}
                ).limit(5).to_list(5)
                conv_ids.extend([str(s["_id"]) for s in siblings])
    except Exception:
        pass

    # Fetch by both conversation_id AND contact_id to catch all messages
    query: dict = {"$or": [{"conversation_id": {"$in": conv_ids}}]}
    if contact_id_filter:
        # Include messages stored with the contact_id directly or with fake conv IDs
        query["$or"].append({"contact_id": contact_id_filter})
        query["$or"].append({"conversation_id": {"$regex": contact_id_filter}})

    messages = await db.messages.find(query).sort("timestamp", 1).limit(500).to_list(500)

    # Deduplicate by _id
    seen = set()
    unique = []
    for m in messages:
        mid = str(m["_id"])
        if mid not in seen:
            seen.add(mid)
            unique.append(m)

    return [{
        "_id": str(m["_id"]),
        "content": m.get("content", ""),
        "sender": m.get("sender", "unknown"),
        "timestamp": m["timestamp"].isoformat() if m.get("timestamp") and hasattr(m["timestamp"], "isoformat") else str(m.get("timestamp", "")),
        "status": m.get("status", "sent"),
        "ai_generated": m.get("ai_generated", False),
        "intent_detected": m.get("intent_detected"),
        "channel": m.get("channel"),
        "event_type": m.get("event_type", ""),
        "card_type": m.get("card_type", ""),
        "has_media": m.get("has_media", False),
        "media_urls": m.get("media_urls", []),
        "type": m.get("type", ""),
        "call_sid": m.get("call_sid"),
        "call_status": m.get("call_status"),
        "duration_s": m.get("duration_s", 0),
        "ai_summary": m.get("ai_summary", ""),
        "has_recording": m.get("has_recording", False),
        "recording_url": m.get("recording_url"),
        "transcript": m.get("transcript", ""),
        "direction": m.get("direction", ""),
        "auto_tags": m.get("auto_tags", []),
    } for m in unique]


@router.post("/ai-suggest/{conversation_id}")
async def get_ai_suggestion_smart(conversation_id: str):
    """
    Generate a contextual AI reply suggestion using the rep's VA persona +
    full conversation history. Falls back to generic suggestion on error.
    """
    import asyncio, os
    db = get_db()

    try:
        conv = await db.conversations.find_one({"_id": ObjectId(conversation_id)})
        if not conv:
            raise ValueError("Conversation not found")

        user_id   = conv.get("user_id")
        contact_id = conv.get("contact_id")

        if not user_id:
            raise ValueError("No user_id on conversation")

        # Build system prompt from rep's VA profile
        from routers.ai_campaigns import build_clone_system_prompt, get_contact_context
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        import uuid as _uuid

        system_prompt = await build_clone_system_prompt(user_id)
        system_prompt += (
            "\n\nYou are drafting a SHORT reply suggestion for the rep to review. "
            "1-2 sentences max. Read the conversation and write a natural, on-brand response. "
            "Reply with ONLY the message text, nothing else."
        )

        # Get contact context
        contact_ctx = ""
        if contact_id:
            try:
                contact_ctx = await get_contact_context(user_id, contact_id)
            except Exception:
                pass

        # Pull last 6 messages for context
        recent_msgs = await db.messages.find(
            {"conversation_id": conversation_id}
        ).sort("timestamp", -1).limit(6).to_list(6)
        recent_msgs.reverse()
        conv_lines = "\n".join(
            f"{'Me' if m.get('sender') in ('user','ai') else 'Customer'}: {(m.get('content') or '')[:200]}"
            for m in recent_msgs if m.get('content')
        )

        user_prompt = (
            (f"Customer context:\n{contact_ctx}\n\n" if contact_ctx else "") +
            (f"Recent conversation:\n{conv_lines}\n\n" if conv_lines else "") +
            "Draft my reply to the latest customer message. Just the reply text."
        )

        emergent_key = os.environ.get("EMERGENT_LLM_KEY", "")
        chat = LlmChat(
            api_key=emergent_key,
            session_id=f"suggest-{_uuid.uuid4().hex[:12]}",
            system_message=system_prompt,
        ).with_model("openai", "gpt-5.2")

        response = await asyncio.wait_for(
            chat.send_message(UserMessage(text=user_prompt)),
            timeout=10.0,
        )
        suggestion = (response.strip() if isinstance(response, str)
                      else response.text.strip() if hasattr(response, "text")
                      else str(response)).strip('"\'')
        suggestion = no_em_dash(suggestion)
        suggestion = await clean_ai_text(suggestion, user_id)

        if suggestion:
            return {"suggestion": suggestion, "intent": "contextual"}

    except Exception as e:
        logger.warning(f"[AISuggest] GPT fallback: {e}")

    # Fallback to generic if GPT fails
    return {"suggestion": random.choice(AI_SUGGESTIONS), "intent": "general"}


@router.post("/send/{user_id}")
async def send_message_simple(user_id: str, message_data: dict):
    """Send a message (simplified endpoint that accepts conversation_id in body)"""
    conversation_id = message_data.get('conversation_id')
    content = message_data.get('content')
    contact_id = message_data.get('contact_id')
    channel = message_data.get('channel', 'sms')
    
    db = get_db()
    
    # If no conversation_id but we have contact_id, create/find conversation
    if not conversation_id and contact_id:
        existing = await db.conversations.find_one({
            "user_id": user_id,
            "contact_id": contact_id
        })
        
        if existing:
            conversation_id = str(existing["_id"])
        else:
            contact = await db.contacts.find_one({"_id": ObjectId(contact_id)})
            if not contact:
                raise HTTPException(status_code=404, detail="Contact not found")
            
            conv = {
                "user_id": user_id,
                "contact_id": contact_id,
                "contact_phone": contact.get("phone"),
                "contact_name": f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip(),
                "status": "active",
                "ai_enabled": False,
                "ai_mode": "suggest",
                "created_at": datetime.now(timezone.utc),
                "last_message_at": datetime.now(timezone.utc)
            }
            result = await db.conversations.insert_one(conv)
            conversation_id = str(result.inserted_id)
            logger.info(f"Created conversation for contact {contact_id}")
    
    if not conversation_id or not content:
        raise HTTPException(status_code=400, detail="conversation_id (or contact_id) and content required")
    
    # Substitute template variables ({review_link}, {first_name}, etc.)
    resolved_contact_id = contact_id or ''
    if not resolved_contact_id:
        conv_check = await db.conversations.find_one({"_id": ObjectId(conversation_id)})
        if conv_check:
            resolved_contact_id = conv_check.get('contact_id', '')
    content = await substitute_template_vars(content, user_id, resolved_contact_id)
    
    # Verify conversation exists and belongs to this user
    conv = await db.conversations.find_one({
        "_id": ObjectId(conversation_id),
        "user_id": user_id
    })
    
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Get recipient phone
    to_phone = conv.get('contact_phone')
    if not to_phone:
        contact = await db.contacts.find_one({"_id": ObjectId(conv.get('contact_id', ''))})
        if contact:
            to_phone = contact.get('phone')
    
    # Create message
    message = {
        "conversation_id": conversation_id,
        "content": content,
        "sender": "user",
        "sender_id": user_id,
        "user_id": user_id,
        "timestamp": datetime.now(timezone.utc),
        "status": "sending",
        "direction": "outbound",
        "channel": channel,
    }
    
    # Add template tracking if provided
    if message_data.get('template_id'):
        message['template_id'] = message_data['template_id']
        message['template_type'] = message_data.get('template_type')
        message['template_name'] = message_data.get('template_name')
    
    result = await db.messages.insert_one(message)
    message_id = str(result.inserted_id)
    message['_id'] = message_id

    # Keyword auto-tagging (fire-and-forget)
    try:
        from services.keyword_tagging import schedule_keyword_tagging
        schedule_keyword_tagging(user_id, resolved_contact_id, content, "sms", message_id, conversation_id, sender="user")
    except Exception as kt_err:
        logger.warning(f"[KeywordTag] schedule failed: {kt_err}")

    # ── Rep replied: clear YOU'RE NEEDED + lower future threshold to 1 ─────
    # Once a rep personally replies, they want to know about the NEXT message
    # immediately (not after 2+). Set rep_engaged=True so the webhook uses 1.
    # Also reset campaign enrollment reply_count so the AI escalation counter starts fresh.
    try:
        await db.conversations.update_one(
            {"_id": ObjectId(conversation_id)},
            {"$set": {
                "needs_assistance":          False,
                "unanswered_customer_replies": 0,
                "rep_engaged":               True,
                "rep_last_replied_at":       datetime.now(timezone.utc),
            }}
        )
        # Reset campaign enrollment reply_count for this contact
        conv_data = await db.conversations.find_one({"_id": ObjectId(conversation_id)}, {"contact_id": 1})
        contact_id_for_reset = (conv_data or {}).get("contact_id")
        if contact_id_for_reset:
            await db.campaign_enrollments.update_many(
                {"contact_id": contact_id_for_reset, "status": {"$in": ["active", "paused"]}},
                {"$set": {"reply_count": 0}}
            )
        # Also clear from home cache so wins feed updates
        try:
            from routers.home_intelligence import _home_cache
            _home_cache.pop(user_id, None)
        except Exception:
            pass
    except Exception:
        pass
    if channel == 'email':
        # Send via Resend with branded template
        logger.info(f"[EMAIL-FLOW] Starting email send for user={user_id}, conv={conversation_id}")
        contact_id_for_email = conv.get('contact_id', '')
        logger.info(f"[EMAIL-FLOW] Contact ID from conversation: {repr(contact_id_for_email)}")
        
        contact = None
        contact_email = ''
        try:
            if contact_id_for_email:
                contact = await db.contacts.find_one({"_id": ObjectId(contact_id_for_email)})
            logger.info(f"[EMAIL-FLOW] Contact found: {contact is not None}, email field: {repr(contact.get('email') if contact else None)}, email_work: {repr(contact.get('email_work') if contact else None)}")
        except Exception as e:
            logger.error(f"[EMAIL-FLOW] Contact lookup failed: {e}")
        
        contact_email = _get_contact_email(contact) if contact else ''
        logger.info(f"[EMAIL-FLOW] Cleaned contact_email: {repr(contact_email)}")
        
        if contact_email:
            try:
                import resend as resend_mod
                from utils.email_template import get_brand_context, build_branded_email
                RESEND_KEY = os.environ.get("RESEND_API_KEY")
                SENDER = os.environ.get("SENDER_EMAIL", "notifications@send.imonsocial.com")
                logger.info(f"[EMAIL-FLOW] RESEND_API_KEY present: {bool(RESEND_KEY)}, SENDER: {SENDER}")
                if RESEND_KEY:
                    resend_mod.api_key = RESEND_KEY
                    user_doc = await db.users.find_one({"_id": ObjectId(user_id)})
                    sender_name = user_doc.get('name', "I'm On Social") if user_doc else "I'm On Social"
                    contact_name = contact.get('first_name', contact.get('name', ''))
                    
                    # Build branded email
                    brand = await get_brand_context(db, user_id)
                    email_html = build_branded_email(content, brand, contact_name)
                    store_name = brand.get('store_name', "I'm On Social")
                    
                    from_addr = f"{sender_name} at {store_name} <{SENDER}>"
                    subject = f"Message from {sender_name} at {store_name}"
                    logger.info(f"[EMAIL-FLOW] Sending: from={from_addr}, to={contact_email}, subject={subject}")
                    
                    email_result = await asyncio.to_thread(resend_mod.Emails.send, {
                        "from": from_addr,
                        "to": [contact_email],
                        "reply_to": user_doc.get('email', SENDER) if user_doc else SENDER,
                        "subject": subject,
                        "html": email_html,
                    })
                    logger.info(f"[EMAIL-FLOW] Resend response: type={type(email_result)}, value={repr(email_result)}")
                    resend_id = email_result.get('id') if isinstance(email_result, dict) else getattr(email_result, 'id', str(email_result))
                    message['status'] = 'sent'
                    message['resend_id'] = resend_id
                    logger.info(f"[EMAIL-FLOW] SUCCESS: resend_id={resend_id}, to={contact_email}")
                else:
                    message['status'] = 'failed'
                    message['error'] = 'RESEND_API_KEY not configured'
                    logger.error("[EMAIL-FLOW] RESEND_API_KEY missing from environment")
            except Exception as e:
                message['status'] = 'failed'
                message['error'] = str(e)
                logger.error(f"[EMAIL-FLOW] EXCEPTION: {type(e).__name__}: {e}", exc_info=True)
        else:
            message['status'] = 'failed'
            message['error'] = f'No valid email for contact (raw email field: {repr(contact.get("email") if contact else "NO CONTACT")})'
            logger.warning(f"[EMAIL-FLOW] No valid email. Contact exists: {contact is not None}. Raw email: {repr(contact.get('email') if contact else None)}")
        
        await db.messages.update_one(
            {"_id": ObjectId(message_id)},
            {"$set": {"status": message['status'], "channel": "email",
                      "resend_id": message.get('resend_id'), "error": message.get('error')}}
        )
        
        # Log contact event for ALL email attempts (sent or failed)
        if conv.get('contact_id'):
            event_type = "email_sent" if message['status'] == 'sent' else "email_failed"
            await db.contact_events.insert_one({
                "contact_id": str(conv['contact_id']),
                "user_id": user_id,
                "event_type": event_type,
                "channel": "email",
                "message_id": message_id,
                "content_preview": content[:100],
                "status": message['status'],
                "error": message.get('error'),
                "timestamp": datetime.now(timezone.utc),
            })
            logger.info(f"[EMAIL-FLOW] Logged contact event: {event_type}")
    
    elif channel == 'sms_personal':
        # Personal SMS  - just log it, user sends from their own phone
        message['status'] = 'sent'
        
        # Determine event type: prefer explicit from frontend, then resolve dynamically
        explicit_event_type = message_data.get('event_type')
        if explicit_event_type:
            event_type = explicit_event_type
            logger.info(f"[PERSONAL SMS] Using explicit event_type={event_type} from frontend")
        else:
            event_type = await resolve_event_type(content, db)
        
        # Set event_type on message dict so it's returned in the API response
        message['event_type'] = event_type
        
        logger.info(f"[PERSONAL SMS] Logged ({event_type}) for {to_phone}: {content[:50]}...")
        
        await db.messages.update_one(
            {"_id": ObjectId(message_id)},
            {"$set": {"status": "sent", "channel": "sms_personal", "event_type": event_type}}
        )
        
        # Log contact event
        if conv.get('contact_id'):
            await db.contact_events.insert_one({
                "contact_id": str(conv['contact_id']),
                "user_id": user_id,
                "event_type": event_type,
                "channel": "sms_personal",
                "message_id": message_id,
                "content_preview": content[:100],
                "timestamp": datetime.now(timezone.utc),
            })
    
    else:
        # SMS via Twilio — use rep's dedicated number
        if to_phone:
            rep_twilio_number = None
            try:
                rep_doc = await db.users.find_one(
                    {"_id": ObjectId(user_id)},
                    {"twilio_number": 1, "mvpline_number": 1}
                )
                rep_twilio_number = (rep_doc or {}).get("twilio_number") or (rep_doc or {}).get("mvpline_number")
            except Exception:
                pass
            sms_result = await send_sms(to_phone, content, from_phone=rep_twilio_number)
            
            if sms_result.get('success'):
                message['status'] = 'sent'
                message['twilio_sid'] = sms_result.get('message_sid')
                logger.info(f"[SMS] Sent to {to_phone}: {content[:50]}...")
            else:
                message['status'] = 'failed'
                message['error'] = sms_result.get('error')
                logger.error(f"[SMS] Failed to {to_phone}: {sms_result.get('error')}")
            
            # Resolve event type BEFORE updating the message doc
            sms_event_type = "sms_sent" if message['status'] == 'sent' else "sms_failed"
            explicit_et = message_data.get('event_type')
            if explicit_et:
                sms_event_type = explicit_et
            else:
                resolved = await resolve_event_type(content, db)
                if resolved != 'personal_sms':
                    sms_event_type = resolved

            await db.messages.update_one(
                {"_id": ObjectId(message_id)},
                {"$set": {"status": message['status'], "channel": "sms",
                          "twilio_sid": sms_result.get('message_sid'),
                          "event_type": sms_event_type}}
            )
            message['event_type'] = sms_event_type

            # Log contact event for Twilio SMS
            if conv.get('contact_id'):
                await db.contact_events.insert_one({
                    "contact_id": str(conv['contact_id']),
                    "user_id": user_id,
                    "event_type": sms_event_type,
                    "channel": "sms",
                    "message_id": message_id,
                    "content_preview": content[:100],
                    "status": message['status'],
                    "timestamp": datetime.now(timezone.utc),
                })
        else:
            message['status'] = 'failed'
            message['error'] = 'No phone number for contact'
            await db.messages.update_one(
                {"_id": ObjectId(message_id)},
                {"$set": {"status": "failed", "channel": "sms", "error": "No phone number"}}
            )
    
    # Update conversation
    await db.conversations.update_one(
        {"_id": ObjectId(conversation_id)},
        {"$set": {"last_message_at": datetime.now(timezone.utc)}}
    )
    
    # Track stat
    await increment_user_stat(user_id, "messages_sent")
    
    return {
        "_id": message_id,
        "conversation_id": conversation_id,
        "content": content,
        "sender": "user",
        "timestamp": message["timestamp"].isoformat(),
        "status": message['status'],
        "channel": channel,
        "event_type": message.get('event_type', ''),
        "resend_id": message.get('resend_id'),
        "error": message.get('error')
    }


# ============= TWILIO WEBHOOK FOR INBOUND MESSAGES =============

async def find_inbox_owner(db, to_phone: str) -> dict:
    """
    Find the user/inbox that owns a specific Twilio phone number.
    
    Routing priority:
    1. User's personal mvpline_number
    2. Shared inbox phone_number
    3. Store's twilio_phone_number (routes to store manager or first user)
    4. Fallback to admin
    
    Returns: {"user_id": str, "inbox_type": str, "inbox_id": str or None}
    """
    # Normalize the phone for matching
    to_phone_normalized = normalize_phone(to_phone)
    to_phone_digits = to_phone_normalized.replace("+", "")
    to_phone_no_country = to_phone_digits[1:] if to_phone_digits.startswith("1") and len(to_phone_digits) == 11 else to_phone_digits
    
    # 1. Check if this is a user's personal I'm On Social number
    user = await db.users.find_one({
        "$or": [
            {"mvpline_number": to_phone_normalized},
            {"mvpline_number": to_phone_digits},
            {"mvpline_number": "+" + to_phone_digits},
            {"mvpline_number": to_phone_no_country}
        ]
    })
    
    if user:
        logger.info(f"Routed to user's personal inbox: {user.get('name')} ({user.get('email')})")
        return {
            "user_id": str(user["_id"]),
            "inbox_type": "personal",
            "inbox_id": None,
            "inbox_name": f"{user.get('name')}'s Inbox"
        }
    
    # 2. Check shared inboxes
    shared_inbox = await db.shared_inboxes.find_one({
        "$or": [
            {"phone_number": to_phone_normalized},
            {"phone_number": to_phone_digits},
            {"phone_number": "+" + to_phone_digits},
            {"phone_number": to_phone_no_country}
        ],
        "active": {"$ne": False}  # Only active inboxes
    })
    
    if shared_inbox and shared_inbox.get("assigned_users"):
        # Route to first assigned user (could implement round-robin later)
        logger.info(f"Routed to shared inbox: {shared_inbox.get('name')}")
        return {
            "user_id": shared_inbox["assigned_users"][0],
            "inbox_type": "shared",
            "inbox_id": str(shared_inbox["_id"]),
            "inbox_name": shared_inbox.get("name", "Shared Inbox")
        }
    
    # 3. Check store phone numbers
    store = await db.stores.find_one({
        "$or": [
            {"twilio_phone_number": to_phone_normalized},
            {"twilio_phone_number": to_phone_digits},
            {"twilio_phone_number": "+" + to_phone_digits},
            {"twilio_phone_number": to_phone_no_country}
        ],
        "active": {"$ne": False}
    })
    
    if store:
        # Find store manager or first user of this store
        store_user = await db.users.find_one({
            "store_id": str(store["_id"]),
            "role": "store_manager"
        })
        
        if not store_user:
            # Fallback to any user in this store
            store_user = await db.users.find_one({"store_id": str(store["_id"])})
        
        if store_user:
            logger.info(f"Routed to store inbox: {store.get('name')}")
            return {
                "user_id": str(store_user["_id"]),
                "inbox_type": "store",
                "inbox_id": str(store["_id"]),
                "inbox_name": store.get("name", "Store Inbox")
            }
    
    # 4. Fallback to admin
    admin_user = await db.users.find_one({"role": {"$in": ["super_admin", "org_admin"]}})
    if admin_user:
        logger.warning(f"No specific inbox found for {to_phone} - routing to admin: {admin_user.get('email')}")
        return {
            "user_id": str(admin_user["_id"]),
            "inbox_type": "fallback",
            "inbox_id": None,
            "inbox_name": "Admin Inbox"
        }
    
    # Last resort - any user
    any_user = await db.users.find_one({})
    if any_user:
        logger.warning(f"No admin found - routing to first user: {any_user.get('email')}")
        return {
            "user_id": str(any_user["_id"]),
            "inbox_type": "fallback",
            "inbox_id": None,
            "inbox_name": "Default Inbox"
        }
    
    return None


@router.post("/webhook/inbound")
async def twilio_inbound_webhook(request: Request):
    """
    Receive inbound SMS/MMS from Twilio.
    
    Routing Logic:
    1. User's personal mvpline_number → routes to that user's inbox
    2. Shared inbox phone_number → routes to assigned users
    3. Store's twilio_phone_number → routes to store manager
    4. Fallback → routes to admin
    
    Twilio sends POST data as form-encoded with fields like:
    - From: Sender phone number (e.g., +14155551234)
    - To: Twilio phone number (e.g., +14352362837)
    - Body: Message text content
    - NumMedia: Number of media attachments (0-10)
    - MediaUrl0, MediaUrl1, etc.: URLs of media attachments
    - MediaContentType0, etc.: Content types of media
    - MessageSid: Twilio message ID
    - AccountSid: Twilio account ID
    """
    db = get_db()
    
    try:
        # Parse form data from Twilio
        form_data = await request.form()
        
        # Extract key fields
        from_phone = form_data.get("From", "")
        to_phone = form_data.get("To", "")
        body = form_data.get("Body", "")
        message_sid = form_data.get("MessageSid", "")
        num_media = int(form_data.get("NumMedia", 0))
        
        logger.info(f"Inbound SMS/MMS from {from_phone} to {to_phone}: {body[:50]}...")
        
        # Normalize phone numbers
        from_phone = normalize_phone(from_phone)
        to_phone = normalize_phone(to_phone)
        
        # Extract media URLs if present (MMS)
        media_urls = []
        media_content_types = []
        for i in range(num_media):
            media_url = form_data.get(f"MediaUrl{i}")
            media_type = form_data.get(f"MediaContentType{i}")
            if media_url:
                media_urls.append(media_url)
                media_content_types.append(media_type)
        
        if media_urls:
            logger.info(f"Received {num_media} media attachments: {media_content_types}")
        
        # ========== ROUTING LOGIC ==========
        # Find which user/inbox should receive this message based on the "To" number
        inbox_owner = await find_inbox_owner(db, to_phone)
        
        if not inbox_owner:
            logger.error(f"No inbox owner found for {to_phone} - no users in system")
            return Response(
                content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
                media_type="application/xml"
            )
        
        target_user_id = inbox_owner["user_id"]
        inbox_type = inbox_owner["inbox_type"]
        inbox_id = inbox_owner.get("inbox_id")
        inbox_name = inbox_owner.get("inbox_name", "Inbox")
        
        logger.info(f"Message routed to {inbox_type} inbox ({inbox_name}) for user {target_user_id}")
        
        # ========== CONTACT LOOKUP ==========
        # Find existing contact for this sender (owned by the target user)
        contact = await db.contacts.find_one({
            "user_id": target_user_id,
            "$or": [
                {"phone": from_phone},
                {"phone": from_phone.replace("+", "")},
                {"phone": from_phone[2:] if from_phone.startswith("+1") else from_phone}
            ]
        })
        
        # Also check if contact exists under any user (for shared inboxes)
        if not contact and inbox_type == "shared":
            contact = await db.contacts.find_one({
                "$or": [
                    {"phone": from_phone},
                    {"phone": from_phone.replace("+", "")},
                    {"phone": from_phone[2:] if from_phone.startswith("+1") else from_phone}
                ]
            })
        
        if not contact:
            logger.info(f"No contact found for phone {from_phone} - creating new contact")
            # Create a new contact for this sender
            contact = {
                "user_id": target_user_id,
                "first_name": "Unknown",
                "last_name": from_phone,
                "phone": from_phone,
                "source": "inbound_sms",
                "tags": ["inbound"],
                "notes": f"Auto-created from inbound SMS to {inbox_name}",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }
            
            # Add shared inbox reference if applicable
            if inbox_type == "shared" and inbox_id:
                contact["shared_inbox_id"] = inbox_id
            
            result = await db.contacts.insert_one(contact)
            contact["_id"] = result.inserted_id
            logger.info(f"Created new contact for sender: {from_phone}")
        
        contact_id = str(contact["_id"])
        # Use the contact's user_id if it exists, otherwise use target_user_id
        user_id = contact.get("user_id") or target_user_id
        
        # ========== CONVERSATION LOOKUP/CREATE ==========
        # Find or create conversation
        conversation = await db.conversations.find_one({
            "user_id": user_id,
            "contact_id": contact_id
        })
        
        if not conversation:
            # Create new conversation
            conversation = {
                "user_id": user_id,
                "contact_id": contact_id,
                "contact_phone": from_phone,
                "contact_name": f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip(),
                "status": "active",
                "ai_enabled": False,
                "ai_mode": "suggest",
                "unread": True,
                "unread_count": 1,
                "inbox_type": inbox_type,  # Track which inbox this belongs to
                "inbox_id": inbox_id,
                "inbox_name": inbox_name,
                "created_at": datetime.now(timezone.utc),
                "last_message_at": datetime.now(timezone.utc)
            }
            result = await db.conversations.insert_one(conversation)
            conversation["_id"] = result.inserted_id
            logger.info(f"Created new conversation for inbound message from {from_phone}")
        else:
            # Update conversation - mark as unread with new message
            await db.conversations.update_one(
                {"_id": conversation["_id"]},
                {
                    "$set": {"last_message_at": datetime.now(timezone.utc), "unread": True},
                    "$inc": {"unread_count": 1}
                }
            )
        
        conversation_id = str(conversation["_id"])
        
        # ========== SAVE INBOUND MESSAGE ==========
        # Create the inbound message
        message = {
            "conversation_id": conversation_id,
            "content": body,
            "sender": "contact",  # This is from the contact, not the user
            "timestamp": datetime.now(timezone.utc),
            "status": "received",
            "twilio_sid": message_sid,
            "media_urls": media_urls,
            "media_content_types": media_content_types,
            "has_media": len(media_urls) > 0,
            "direction": "inbound",
            "inbox_type": inbox_type,
            "to_number": to_phone  # Track which number received this
        }
        
        insert_result = await db.messages.insert_one(message)
        logger.info(f"Saved inbound message to conversation {conversation_id} ({inbox_name})")

        # Keyword auto-tagging (fire-and-forget)
        try:
            from services.keyword_tagging import schedule_keyword_tagging
            schedule_keyword_tagging(user_id, contact_id, body or "", "sms", str(insert_result.inserted_id), conversation_id, sender="contact")
        except Exception as kt_err:
            logger.warning(f"[KeywordTag] schedule failed: {kt_err}")
        
        # ── Real-time notification via WebSocket ──
        try:
            from websocket_manager import manager as ws_manager
            contact_name = f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip() or from_phone
            ws_payload = {
                "type": "new_customer_message",
                "conversation_id": conversation_id,
                "contact_name": contact_name,
                "contact_phone": from_phone,
                "message_preview": body[:100] if body else "(media)",
                "has_media": len(media_urls) > 0,
            }
            await ws_manager.send_to_user(user_id, ws_payload)
            
            # Also create a persistent notification
            notif = {
                "user_id": user_id,
                "type": "new_message",
                "title": f"New message from {contact_name}",
                "message": body[:100] if body else "Sent media",
                "conversation_id": conversation_id,
                "contact_id": contact_id,
                "contact_name": contact_name,
                "contact_phone": from_phone,
                "read": False,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            await db.notifications.insert_one(notif)
            
            # Notify via WS to update badge
            await ws_manager.send_to_user(user_id, {"type": "notification_update", "reason": "new_message"})
        except Exception as notify_err:
            logger.error(f"Notification error: {notify_err}")
        
        # Return empty TwiML response (we don't auto-reply)
        return Response(
            content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
            media_type="application/xml"
        )
        
    except Exception as e:
        logger.error(f"Error processing Twilio webhook: {str(e)}")
        # Always return 200 to Twilio to prevent retries
        return Response(
            content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
            media_type="application/xml"
        )



@router.get("/email-diagnostic/{user_id}/{contact_id}")
async def email_diagnostic(user_id: str, contact_id: str):
    """Diagnostic endpoint to trace the entire email sending pipeline step by step."""
    db = get_db()
    steps = []
    
    # Step 1: Check user exists
    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        steps.append({"step": "user_lookup", "ok": user is not None, "name": user.get('name') if user else None})
    except Exception as e:
        steps.append({"step": "user_lookup", "ok": False, "error": str(e)})
    
    # Step 2: Check contact exists and has email
    try:
        contact = await db.contacts.find_one({"_id": ObjectId(contact_id)})
        raw_email = contact.get('email') if contact else None
        raw_email_work = contact.get('email_work') if contact else None
        clean = _get_contact_email(contact) if contact else ''
        steps.append({
            "step": "contact_lookup", "ok": contact is not None,
            "raw_email": repr(raw_email), "raw_email_work": repr(raw_email_work),
            "cleaned_email": clean, "contact_name": contact.get('first_name') if contact else None
        })
    except Exception as e:
        steps.append({"step": "contact_lookup", "ok": False, "error": str(e)})
    
    # Step 3: Check conversation exists
    try:
        conv = await db.conversations.find_one({"user_id": user_id, "contact_id": contact_id})
        steps.append({"step": "conversation_lookup", "ok": conv is not None, "conv_id": str(conv['_id']) if conv else None})
    except Exception as e:
        steps.append({"step": "conversation_lookup", "ok": False, "error": str(e)})
    
    # Step 4: Check Resend config
    RESEND_KEY = os.environ.get("RESEND_API_KEY")
    SENDER = os.environ.get("SENDER_EMAIL", "notifications@send.imonsocial.com")
    steps.append({
        "step": "resend_config",
        "ok": bool(RESEND_KEY),
        "api_key_prefix": RESEND_KEY[:10] + "..." if RESEND_KEY else "MISSING",
        "sender_email": SENDER
    })
    
    # Step 5: Check brand context
    try:
        from utils.email_template import get_brand_context
        brand = await get_brand_context(db, user_id)
        steps.append({"step": "brand_context", "ok": True, "store_name": brand.get('store_name'), "has_logo": bool(brand.get('logo_url'))})
    except Exception as e:
        steps.append({"step": "brand_context", "ok": False, "error": str(e)})
    
    # Step 6: Actually send a test email (if all checks pass)
    if clean and RESEND_KEY:
        try:
            import resend as resend_mod
            resend_mod.api_key = RESEND_KEY
            from utils.email_template import build_branded_email
            test_html = build_branded_email("This is a diagnostic test email from I'm On Social.", brand, contact.get('first_name', ''))
            sender_name = user.get('name', "I'm On Social") if user else "I'm On Social"
            store_name = brand.get('store_name', "I'm On Social")
            
            result = await asyncio.to_thread(resend_mod.Emails.send, {
                "from": f"{sender_name} at {store_name} <{SENDER}>",
                "to": [clean],
                "reply_to": user.get('email', SENDER) if user else SENDER,
                "subject": f"[DIAGNOSTIC] Test from {store_name}",
                "html": test_html,
            })
            resend_id = result.get('id') if isinstance(result, dict) else getattr(result, 'id', str(result))
            steps.append({"step": "send_test_email", "ok": True, "resend_id": resend_id, "to": clean})
        except Exception as e:
            steps.append({"step": "send_test_email", "ok": False, "error": str(e), "error_type": type(e).__name__})
    else:
        steps.append({"step": "send_test_email", "skipped": True, "reason": "No valid email" if not clean else "No RESEND_API_KEY"})
    
    all_ok = all(s.get('ok', s.get('skipped', False)) for s in steps)
    return {"diagnostic": "PASS" if all_ok else "FAIL", "steps": steps}
