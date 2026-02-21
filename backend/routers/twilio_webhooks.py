"""
Twilio Webhooks Router - Handle incoming SMS/MMS messages
"""
from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import Response
from bson import ObjectId
from datetime import datetime
from typing import Optional, List
import logging
import os
import httpx
import base64

from routers.database import get_db

router = APIRouter(prefix="/webhooks/twilio", tags=["Twilio Webhooks"])
logger = logging.getLogger(__name__)

# Backend URL for constructing media URLs
BACKEND_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://imos-marketing.preview.emergentagent.com")


async def download_and_store_media(media_url: str, media_type: str) -> Optional[str]:
    """
    Download media from Twilio URL and store it in our database.
    Returns the media_id for our own endpoint.
    """
    try:
        # Twilio requires authentication to download media
        twilio_sid = os.environ.get("TWILIO_ACCOUNT_SID")
        twilio_token = os.environ.get("TWILIO_AUTH_TOKEN")
        
        if not twilio_sid or not twilio_token:
            logger.warning("Twilio credentials not configured for media download")
            return None
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                media_url,
                auth=(twilio_sid, twilio_token),
                follow_redirects=True,
                timeout=30.0
            )
            
            if response.status_code != 200:
                logger.error(f"Failed to download media: {response.status_code}")
                return None
            
            # Convert to base64
            media_bytes = response.content
            base64_data = base64.b64encode(media_bytes).decode('utf-8')
            
            # Create data URL
            data_url = f"data:{media_type};base64,{base64_data}"
            
            # Store in database
            media_doc = {
                "data": data_url,
                "content_type": media_type,
                "size": len(media_bytes),
                "source": "twilio_inbound",
                "original_url": media_url,
                "created_at": datetime.utcnow()
            }
            
            result = await get_db().media.insert_one(media_doc)
            media_id = str(result.inserted_id)
            
            logger.info(f"Stored inbound media: {media_id} ({len(media_bytes)} bytes)")
            return media_id
            
    except Exception as e:
        logger.error(f"Error downloading/storing media: {str(e)}")
        return None


@router.post("/incoming")
async def incoming_message(
    request: Request,
    From: str = Form(...),
    To: str = Form(...),
    Body: str = Form(default=""),
    MessageSid: str = Form(default=""),
    NumMedia: str = Form(default="0"),
    MediaUrl0: Optional[str] = Form(default=None),
    MediaUrl1: Optional[str] = Form(default=None),
    MediaUrl2: Optional[str] = Form(default=None),
    MediaContentType0: Optional[str] = Form(default=None),
    MediaContentType1: Optional[str] = Form(default=None),
    MediaContentType2: Optional[str] = Form(default=None),
):
    """
    Webhook endpoint for incoming SMS/MMS from Twilio.
    
    Twilio sends a POST request with form data including:
    - From: Sender's phone number
    - To: Your Twilio number
    - Body: Message text
    - NumMedia: Number of media attachments
    - MediaUrl0, MediaUrl1, etc.: URLs to media files
    - MediaContentType0, etc.: MIME types of media
    """
    db = get_db()
    
    logger.info(f"Incoming message from {From} to {To}: {Body[:50]}...")
    
    # Normalize phone numbers
    from_phone = normalize_phone(From)
    to_phone = normalize_phone(To)
    
    # Collect media URLs
    media_urls = []
    media_types = []
    num_media = int(NumMedia) if NumMedia else 0
    
    if num_media > 0:
        if MediaUrl0:
            media_urls.append(MediaUrl0)
            media_types.append(MediaContentType0 or 'image/jpeg')
        if MediaUrl1:
            media_urls.append(MediaUrl1)
            media_types.append(MediaContentType1 or 'image/jpeg')
        if MediaUrl2:
            media_urls.append(MediaUrl2)
            media_types.append(MediaContentType2 or 'image/jpeg')
    
    try:
        # Find the contact by phone number
        contact = await db.contacts.find_one({"phone": from_phone})
        
        if not contact:
            # Try without +1 prefix
            alt_phone = from_phone.replace("+1", "") if from_phone.startswith("+1") else "+1" + from_phone.lstrip("+")
            contact = await db.contacts.find_one({"phone": {"$in": [from_phone, alt_phone, from_phone.lstrip("+")]}})
        
        if not contact:
            # Create a new contact for unknown senders
            contact = {
                "phone": from_phone,
                "first_name": "Unknown",
                "last_name": from_phone[-4:],  # Last 4 digits as placeholder
                "name": f"Unknown ({from_phone[-4:]})",
                "source": "sms_inbound",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            
            # Find a user to assign this contact to (use first super_admin or org_admin)
            admin_user = await db.users.find_one({"role": {"$in": ["super_admin", "org_admin"]}})
            if admin_user:
                contact["user_id"] = str(admin_user["_id"])
            
            result = await db.contacts.insert_one(contact)
            contact["_id"] = result.inserted_id
            logger.info(f"Created new contact for {from_phone}")
        
        contact_id = str(contact["_id"])
        user_id = contact.get("user_id")
        
        # Find or create conversation
        conversation = await db.conversations.find_one({
            "contact_id": contact_id
        })
        
        if not conversation:
            # Create new conversation
            conversation = {
                "user_id": user_id,
                "contact_id": contact_id,
                "contact_phone": from_phone,
                "contact_name": contact.get("name") or f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip(),
                "status": "active",
                "ai_enabled": False,
                "ai_mode": "suggest",
                "unread": True,
                "unread_count": 1,
                "needs_assistance": False,
                "created_at": datetime.utcnow(),
                "last_message_at": datetime.utcnow()
            }
            result = await db.conversations.insert_one(conversation)
            conversation["_id"] = result.inserted_id
            logger.info(f"Created new conversation for contact {contact_id}")
        else:
            # Update existing conversation
            await db.conversations.update_one(
                {"_id": conversation["_id"]},
                {
                    "$set": {
                        "last_message_at": datetime.utcnow(),
                        "unread": True,
                        "status": "active"
                    },
                    "$inc": {"unread_count": 1}
                }
            )
        
        conversation_id = str(conversation["_id"])
        
        # Create the message
        message = {
            "conversation_id": conversation_id,
            "content": Body,
            "sender": "contact",
            "timestamp": datetime.utcnow(),
            "status": "received",
            "twilio_sid": MessageSid,
            "from_phone": from_phone,
            "to_phone": to_phone,
        }
        
        # Add media if present - download and store permanently
        if media_urls:
            stored_media_urls = []
            stored_media_ids = []
            
            for i, twilio_url in enumerate(media_urls):
                media_type = media_types[i] if i < len(media_types) else 'image/jpeg'
                media_id = await download_and_store_media(twilio_url, media_type)
                
                if media_id:
                    # Use our own media endpoint URL
                    our_url = f"{BACKEND_URL}/api/messages/media/{media_id}"
                    stored_media_urls.append(our_url)
                    stored_media_ids.append(media_id)
                else:
                    # Fall back to Twilio URL if download failed
                    stored_media_urls.append(twilio_url)
            
            message["media_urls"] = stored_media_urls
            message["media_ids"] = stored_media_ids
            message["media_types"] = media_types
            message["has_media"] = True
            message["num_media"] = num_media
            message["original_twilio_urls"] = media_urls  # Keep original for reference
        
        await db.messages.insert_one(message)
        logger.info(f"Saved incoming message to conversation {conversation_id}")
        
        # Return empty TwiML response (no auto-reply)
        # You can customize this to send an auto-reply if needed
        twiml_response = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'
        
        return Response(content=twiml_response, media_type="application/xml")
        
    except Exception as e:
        logger.error(f"Error processing incoming message: {str(e)}")
        # Still return valid TwiML to prevent Twilio errors
        twiml_response = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'
        return Response(content=twiml_response, media_type="application/xml")


@router.post("/status")
async def message_status_callback(
    MessageSid: str = Form(...),
    MessageStatus: str = Form(...),
    To: str = Form(default=""),
    From: str = Form(default=""),
    ErrorCode: Optional[str] = Form(default=None),
    ErrorMessage: Optional[str] = Form(default=None),
):
    """
    Webhook for message delivery status updates from Twilio.
    
    Status values: queued, sent, delivered, undelivered, failed
    """
    db = get_db()
    
    logger.info(f"Status update for {MessageSid}: {MessageStatus}")
    
    try:
        # Update message status in database
        update_data = {
            "twilio_status": MessageStatus,
            "status_updated_at": datetime.utcnow()
        }
        
        if ErrorCode:
            update_data["error_code"] = ErrorCode
            update_data["error_message"] = ErrorMessage
            logger.warning(f"Message {MessageSid} failed: {ErrorCode} - {ErrorMessage}")
        
        # Map Twilio status to our status
        status_map = {
            "queued": "sending",
            "sent": "sent",
            "delivered": "delivered",
            "undelivered": "failed",
            "failed": "failed"
        }
        
        if MessageStatus in status_map:
            update_data["status"] = status_map[MessageStatus]
        
        result = await db.messages.update_one(
            {"twilio_sid": MessageSid},
            {"$set": update_data}
        )
        
        if result.modified_count > 0:
            logger.info(f"Updated message {MessageSid} status to {MessageStatus}")
        
    except Exception as e:
        logger.error(f"Error updating message status: {str(e)}")
    
    return Response(content="OK", media_type="text/plain")


@router.get("/test")
async def test_webhook():
    """Test endpoint to verify webhook is accessible"""
    return {
        "status": "ok",
        "message": "Twilio webhook endpoint is active",
        "endpoints": {
            "incoming_sms": "/api/webhooks/twilio/incoming",
            "status_callback": "/api/webhooks/twilio/status"
        }
    }


def normalize_phone(phone: str) -> str:
    """Normalize phone number to E.164 format"""
    if not phone:
        return phone
    
    # Remove all non-digit characters except +
    cleaned = ''.join(c for c in phone if c.isdigit() or c == '+')
    
    # Add + if not present
    if not cleaned.startswith('+'):
        if len(cleaned) == 10:
            cleaned = '+1' + cleaned
        elif len(cleaned) == 11 and cleaned.startswith('1'):
            cleaned = '+' + cleaned
        else:
            cleaned = '+' + cleaned
    
    return cleaned
