"""
Messages router - handles conversations and messages
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Request, Response
from bson import ObjectId
from datetime import datetime
from typing import Optional, List
import logging
import random
import base64
import os
import urllib.parse
import asyncio

from models import Message, MessageCreate
from routers.database import get_db, get_data_filter, increment_user_stat
from services.twilio_service import send_sms, get_twilio_status, normalize_phone, TWILIO_PHONE_NUMBER

router = APIRouter(prefix="/messages", tags=["Messages"])
logger = logging.getLogger(__name__)

# Email validation — reject "None", "null", empty strings, and non-email values
import re
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
    ]).limit(500).to_list(500)
    
    result = []
    for conv in conversations:
        conv['_id'] = str(conv['_id'])
        
        # Get contact info
        try:
            contact = await db.contacts.find_one({"_id": ObjectId(conv['contact_id'])}, {"photo": 0})
        except:
            contact = await db.contacts.find_one({"_id": conv['contact_id']}, {"photo": 0})
        
        if contact:
            conv['contact'] = {
                "id": str(contact['_id']),
                "name": f"{contact['first_name']} {contact.get('last_name', '')}".strip(),
                "phone": contact['phone'],
                "email": contact.get('email') or contact.get('email_work') or '',
                "photo": contact.get('photo_thumbnail') or contact.get('photo_url'),
                "photo_thumbnail": contact.get('photo_thumbnail'),
                "photo_url": contact.get('photo_url'),
            }
        
        # Get last message
        last_msg = await db.messages.find_one(
            {"conversation_id": str(conv['_id'])},
            sort=[("timestamp", -1)]
        )
        if last_msg:
            conv['last_message'] = {
                "content": last_msg['content'],
                "timestamp": last_msg['timestamp'],
                "sender": last_msg['sender']
            }
        
        result.append(conv)
    
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
        "direction": m.get('direction', 'outbound')
    } for m in messages]
    
    return conv

@router.post("/conversations/{user_id}")
async def create_conversation(user_id: str, data: dict):
    """Create or get existing conversation with a contact"""
    contact_id = data.get('contact_id')
    contact_phone = data.get('contact_phone')
    
    # Try to find existing conversation
    if contact_id:
        existing = await get_db().conversations.find_one({
            "user_id": user_id,
            "contact_id": contact_id
        })
        if existing:
            existing['_id'] = str(existing['_id'])
            return existing
    
    # Create new conversation
    conv = {
        "user_id": user_id,
        "contact_id": contact_id,
        "contact_phone": contact_phone,
        "status": "active",
        "ai_enabled": False,
        "ai_mode": "suggest",
        "ai_handled": False,  # Has AI communicated in this conversation
        "ai_outcome": None,   # Current AI-detected outcome type
        "ai_outcome_priority": 999,  # Priority for sorting (lower = more important)
        "unread": False,
        "unread_count": 0,
        "needs_assistance": False,
        "created_at": datetime.utcnow(),
        "last_message_at": datetime.utcnow()
    }
    
    result = await get_db().conversations.insert_one(conv)
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
    
    # Create message record
    message = {
        "conversation_id": conversation_id,
        "content": message_data.content,
        "sender": "user",
        "user_id": user_id,
        "timestamp": datetime.utcnow(),
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
    
    channel = message_data.channel or 'sms'
    
    if channel == 'email':
        # Send via Resend (email) with branded template
        contact = await get_db().contacts.find_one({"_id": ObjectId(conv.get('contact_id', ''))})
        contact_email = (contact.get('email') or contact.get('email_work')) if contact else None
        
        if contact_email:
            try:
                import resend as resend_mod
                from utils.email_template import get_brand_context, build_branded_email
                RESEND_KEY = os.environ.get("RESEND_API_KEY")
                SENDER = os.environ.get("SENDER_EMAIL", "noreply@imosapp.com")
                if RESEND_KEY:
                    resend_mod.api_key = RESEND_KEY
                    user_doc = await get_db().users.find_one({"_id": ObjectId(user_id)})
                    sender_name = user_doc.get('name', 'iMOs') if user_doc else 'iMOs'
                    contact_name = contact.get('name', contact.get('first_name', ''))
                    
                    brand = await get_brand_context(get_db(), user_id)
                    email_html = build_branded_email(message_data.content, brand, contact_name)
                    store_name = brand.get('store_name', 'iMOs')
                    
                    email_result = await asyncio.to_thread(resend_mod.Emails.send, {
                        "from": f"{sender_name} at {store_name} <{SENDER}>",
                        "to": [contact_email],
                        "subject": f"Message from {sender_name} at {store_name}",
                        "html": email_html,
                    })
                    resend_id = email_result.get('id') if isinstance(email_result, dict) else str(email_result)
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
                logger.error(f"[EMAIL] Failed to {contact_email}: {e}")
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
        
        # Log as contact event
        contact_id = conv.get('contact_id')
        if contact_id and message['status'] == 'sent':
            await get_db().contact_events.insert_one({
                "contact_id": str(contact_id),
                "user_id": user_id,
                "event_type": "email_sent",
                "channel": "email",
                "message_id": message['_id'],
                "content_preview": message_data.content[:100],
                "recipient": contact_email,
                "timestamp": datetime.utcnow(),
            })
    elif channel == 'sms_personal':
        # User sending from their personal phone — just log it, no Twilio needed
        message['status'] = 'sent'
        message['channel'] = 'sms_personal'
        
        # Detect content type for activity tracking
        content_lower = message_data.content.lower()
        event_type = 'personal_sms'
        if '/card/' in message_data.content:
            event_type = 'digital_card_sent'
        elif '/review/' in message_data.content:
            event_type = 'review_request_sent'
        elif 'congrats' in content_lower or '/api/s/' in message_data.content:
            event_type = 'congrats_card_sent'
        elif '/vcard/' in message_data.content:
            event_type = 'vcard_sent'
        
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
                "timestamp": datetime.utcnow(),
            }
            await get_db().contact_events.insert_one(event_doc)
    elif to_phone:
        # Send via Twilio (SMS)
        message['channel'] = 'sms'
        sms_result = await send_sms(to_phone, message_data.content)
        
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
    else:
        message['status'] = 'sent'
        logger.warning(f"No phone number for conversation {conversation_id}")
    
    # Update conversation
    await get_db().conversations.update_one(
        {"_id": ObjectId(conversation_id)},
        {"$set": {"last_message_at": datetime.utcnow()}}
    )
    
    # Track stat
    await increment_user_stat(user_id, "messages_sent")
    
    return message


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
                # Create new conversation for this contact
                conv = {
                    "user_id": user_id,
                    "contact_id": conversation_id,
                    "contact_phone": contact.get('phone'),
                    "contact_name": f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip() or contact.get('name'),
                    "status": "active",
                    "ai_enabled": False,
                    "ai_mode": "suggest",
                    "created_at": datetime.utcnow(),
                    "last_message_at": datetime.utcnow()
                }
                result = await db.conversations.insert_one(conv)
                conv['_id'] = result.inserted_id
                logger.info(f"Created new conversation for contact {conversation_id}")
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
    
    # Read and store media file
    media_content = await media.read()
    media_type = media.content_type or 'image/jpeg'
    
    # Store media in database
    media_base64 = base64.b64encode(media_content).decode('utf-8')
    media_data_url = f"data:{media_type};base64,{media_base64}"
    
    media_doc = {
        "conversation_id": actual_conv_id,
        "user_id": user_id,
        "content_type": media_type,
        "filename": media.filename,
        "data": media_data_url,
        "size_bytes": len(media_content),
        "created_at": datetime.utcnow()
    }
    
    media_result = await db.media.insert_one(media_doc)
    media_id = str(media_result.inserted_id)
    
    # Create publicly accessible URL for the media
    backend_url = "https://app.imosapp.com"
    media_url = f"{backend_url}/api/messages/media/{media_id}"
    
    # Create message record
    message = {
        "conversation_id": actual_conv_id,
        "content": content,
        "sender": "user",
        "timestamp": datetime.utcnow(),
        "status": "sending",
        "media_urls": [media_data_url],
        "media_ids": [media_id],
        "has_media": True
    }
    
    result = await db.messages.insert_one(message)
    message['_id'] = str(result.inserted_id)
    
    # Send via Twilio
    media_urls = [media_url] if media_url else None
    sms_result = await send_sms(to_phone, content or "📷", media_urls)
    
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
        {"$set": {"last_message_at": datetime.utcnow()}}
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
        {"$set": {"status": "archived", "archived_at": datetime.utcnow()}}
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


@router.put("/conversation/{conversation_id}/read")
async def mark_conversation_read(conversation_id: str):
    """Mark a conversation as read"""
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
        {"$set": {"status": "archived", "archived_at": datetime.utcnow()}}
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
    base_filter = await get_data_filter(user_id)
    
    allowed_fields = ['ai_enabled', 'ai_mode', 'status', 'unread', 'unread_count', 'needs_assistance', 'ai_handled', 'ai_outcome', 'ai_outcome_priority', 'ai_outcome_acknowledged', 'flagged']
    update_dict = {k: v for k, v in data.items() if k in allowed_fields}
    
    # If setting ai_outcome, auto-set the priority
    if 'ai_outcome' in update_dict:
        outcome = update_dict['ai_outcome']
        if outcome and outcome in AI_OUTCOMES:
            update_dict['ai_outcome_priority'] = AI_OUTCOMES[outcome]['priority']
            update_dict['ai_handled'] = True
        elif outcome is None:
            update_dict['ai_outcome_priority'] = 999
    
    if not update_dict:
        raise HTTPException(status_code=400, detail="No valid fields to update")
    
    result = await get_db().conversations.update_one(
        {"$and": [{"_id": ObjectId(conversation_id)}, base_filter]},
        {"$set": update_dict}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    return {"message": "Conversation updated"}


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
    except:
        conv = await db.conversations.find_one({"_id": conversation_id})
    
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    result = {
        "_id": str(conv["_id"]),
        "contact_name": conv.get("contact_name"),
        "contact_phone": conv.get("contact_phone"),
        "contact_email": conv.get("contact_email"),
        "contact_photo": None,
        "status": conv.get("status", "active"),
    }
    
    # Try to get contact photo and email
    contact_id = conv.get("contact_id")
    if contact_id:
        try:
            contact = await db.contacts.find_one({"_id": ObjectId(contact_id)}, {"photo": 0})
            if contact:
                result["contact_photo"] = contact.get("photo_thumbnail") or contact.get("photo_url")
                result["contact_name"] = f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip() or result["contact_name"]
                if not result["contact_email"] and (contact.get("email") or contact.get("email_work")):
                    result["contact_email"] = contact.get("email") or contact.get("email_work")
        except:
            pass
    
    return result


@router.get("/thread/{conversation_id}")
async def get_thread_messages(conversation_id: str):
    """Get messages for a conversation thread (simplified endpoint)"""
    # Get messages
    messages = await get_db().messages.find(
        {"conversation_id": conversation_id}
    ).sort("timestamp", 1).limit(500).to_list(500)
    
    return [{
        "_id": str(m['_id']),
        "content": m['content'],
        "sender": m['sender'],
        "timestamp": m['timestamp'].isoformat() if hasattr(m['timestamp'], 'isoformat') else str(m['timestamp']),
        "status": m.get('status', 'sent'),
        "ai_generated": m.get('ai_generated', False),
        "intent_detected": m.get('intent_detected'),
        "channel": m.get('channel'),
        "has_media": m.get('has_media', False),
        "media_urls": m.get('media_urls', [])
    } for m in messages]


@router.post("/ai-suggest/{conversation_id}")
async def get_ai_suggestion_simple(conversation_id: str):
    """Get AI-generated response suggestion (simplified endpoint)"""
    suggestion = random.choice(AI_SUGGESTIONS)
    return {"suggestion": suggestion, "intent": "general"}


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
                "created_at": datetime.utcnow(),
                "last_message_at": datetime.utcnow()
            }
            result = await db.conversations.insert_one(conv)
            conversation_id = str(result.inserted_id)
            logger.info(f"Created conversation for contact {contact_id}")
    
    if not conversation_id or not content:
        raise HTTPException(status_code=400, detail="conversation_id (or contact_id) and content required")
    
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
        "timestamp": datetime.utcnow(),
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
    
    # Route based on channel
    if channel == 'email':
        # Send via Resend with branded template
        contact = await db.contacts.find_one({"_id": ObjectId(conv.get('contact_id', ''))})
        contact_email = (contact.get('email') or contact.get('email_work')) if contact else None
        
        if contact_email:
            try:
                import resend as resend_mod
                from utils.email_template import get_brand_context, build_branded_email
                RESEND_KEY = os.environ.get("RESEND_API_KEY")
                SENDER = os.environ.get("SENDER_EMAIL", "noreply@imosapp.com")
                if RESEND_KEY:
                    resend_mod.api_key = RESEND_KEY
                    user_doc = await db.users.find_one({"_id": ObjectId(user_id)})
                    sender_name = user_doc.get('name', 'iMOs') if user_doc else 'iMOs'
                    contact_name = contact.get('first_name', contact.get('name', ''))
                    
                    # Build branded email
                    brand = await get_brand_context(db, user_id)
                    email_html = build_branded_email(content, brand, contact_name)
                    store_name = brand.get('store_name', 'iMOs')
                    
                    email_result = await asyncio.to_thread(resend_mod.Emails.send, {
                        "from": f"{sender_name} at {store_name} <{SENDER}>",
                        "to": [contact_email],
                        "subject": f"Message from {sender_name} at {store_name}",
                        "html": email_html,
                    })
                    resend_id = email_result.get('id') if isinstance(email_result, dict) else str(email_result)
                    message['status'] = 'sent'
                    message['resend_id'] = resend_id
                    logger.info(f"[EMAIL] Sent to {contact_email} (resend_id={resend_id}): {content[:50]}...")
                else:
                    message['status'] = 'failed'
                    message['error'] = 'RESEND_API_KEY not configured'
                    logger.error("[EMAIL] RESEND_API_KEY missing")
            except Exception as e:
                message['status'] = 'failed'
                message['error'] = str(e)
                logger.error(f"[EMAIL] Failed to {contact_email}: {e}")
        else:
            message['status'] = 'failed'
            message['error'] = 'No email address for contact'
            logger.warning(f"[EMAIL] No email for contact in conv {conversation_id}")
        
        await db.messages.update_one(
            {"_id": ObjectId(message_id)},
            {"$set": {"status": message['status'], "channel": "email",
                      "resend_id": message.get('resend_id'), "error": message.get('error')}}
        )
        
        # Log contact event
        if message['status'] == 'sent' and conv.get('contact_id'):
            await db.contact_events.insert_one({
                "contact_id": str(conv['contact_id']),
                "user_id": user_id,
                "event_type": "email_sent",
                "channel": "email",
                "message_id": message_id,
                "content_preview": content[:100],
                "timestamp": datetime.utcnow(),
            })
    
    elif channel == 'sms_personal':
        # Personal SMS — just log it, user sends from their own phone
        message['status'] = 'sent'
        
        # Detect content type
        content_lower = content.lower()
        event_type = 'personal_sms'
        if '/card/' in content:
            event_type = 'digital_card_sent'
        elif '/review/' in content:
            event_type = 'review_request_sent'
        elif 'congrats' in content_lower:
            event_type = 'congrats_card_sent'
        elif '/vcard/' in content:
            event_type = 'vcard_sent'
        
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
                "timestamp": datetime.utcnow(),
            })
    
    else:
        # SMS via Twilio
        if to_phone:
            sms_result = await send_sms(to_phone, content)
            
            if sms_result.get('success'):
                message['status'] = 'sent'
                message['twilio_sid'] = sms_result.get('message_sid')
                logger.info(f"[SMS] Sent to {to_phone}: {content[:50]}...")
            else:
                message['status'] = 'failed'
                message['error'] = sms_result.get('error')
                logger.error(f"[SMS] Failed to {to_phone}: {sms_result.get('error')}")
            
            await db.messages.update_one(
                {"_id": ObjectId(message_id)},
                {"$set": {"status": message['status'], "channel": "sms",
                          "twilio_sid": sms_result.get('message_sid')}}
            )
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
        {"$set": {"last_message_at": datetime.utcnow()}}
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
    
    # 1. Check if this is a user's personal iMOs number
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
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
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
                "created_at": datetime.utcnow(),
                "last_message_at": datetime.utcnow()
            }
            result = await db.conversations.insert_one(conversation)
            conversation["_id"] = result.inserted_id
            logger.info(f"Created new conversation for inbound message from {from_phone}")
        else:
            # Update conversation - mark as unread with new message
            await db.conversations.update_one(
                {"_id": conversation["_id"]},
                {
                    "$set": {"last_message_at": datetime.utcnow(), "unread": True},
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
            "timestamp": datetime.utcnow(),
            "status": "received",
            "twilio_sid": message_sid,
            "media_urls": media_urls,
            "media_content_types": media_content_types,
            "has_media": len(media_urls) > 0,
            "direction": "inbound",
            "inbox_type": inbox_type,
            "to_number": to_phone  # Track which number received this
        }
        
        await db.messages.insert_one(message)
        logger.info(f"Saved inbound message to conversation {conversation_id} ({inbox_name})")
        
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
                "created_at": datetime.utcnow().isoformat(),
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
