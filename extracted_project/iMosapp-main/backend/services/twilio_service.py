"""
Twilio Service - Handles SMS/MMS sending via Twilio API
"""
import os
import logging
from typing import Optional, List
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

logger = logging.getLogger(__name__)

# Initialize Twilio client
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

# Check if Twilio is configured
TWILIO_ENABLED = all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER])

if TWILIO_ENABLED:
    try:
        twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        logger.info(f"Twilio client initialized with number: {TWILIO_PHONE_NUMBER}")
    except Exception as e:
        logger.error(f"Failed to initialize Twilio client: {e}")
        twilio_client = None
        TWILIO_ENABLED = False
else:
    twilio_client = None
    logger.warning("Twilio not configured - SMS/MMS will be mocked")


async def send_sms(
    to_phone: str,
    message: str,
    media_urls: Optional[List[str]] = None
) -> dict:
    """
    Send an SMS or MMS message via Twilio.
    
    Args:
        to_phone: Recipient phone number (E.164 format: +1234567890)
        message: Text message content
        media_urls: Optional list of media URLs for MMS (images, videos)
    
    Returns:
        dict with success status, message_sid, and any error info
    """
    # Normalize phone number
    to_phone = normalize_phone(to_phone)
    
    if not TWILIO_ENABLED or not twilio_client:
        # Mock mode - log and return success
        logger.info(f"[MOCK SMS] To: {to_phone}, Message: {message[:50]}...")
        if media_urls:
            logger.info(f"[MOCK MMS] Media URLs: {media_urls}")
        return {
            "success": True,
            "message_sid": "MOCK_SID_" + str(hash(message))[:10],
            "mock": True
        }
    
    try:
        # Build message parameters
        params = {
            "body": message,
            "from_": TWILIO_PHONE_NUMBER,
            "to": to_phone
        }
        
        # Add media URLs for MMS
        if media_urls:
            params["media_url"] = media_urls
        
        # Send via Twilio
        twilio_message = twilio_client.messages.create(**params)
        
        logger.info(f"Twilio message sent: {twilio_message.sid} to {to_phone}")
        
        return {
            "success": True,
            "message_sid": twilio_message.sid,
            "status": twilio_message.status,
            "mock": False
        }
        
    except TwilioRestException as e:
        logger.error(f"Twilio error sending to {to_phone}: {e.msg}")
        return {
            "success": False,
            "error": e.msg,
            "error_code": e.code,
            "mock": False
        }
    except Exception as e:
        logger.error(f"Error sending SMS to {to_phone}: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "mock": False
        }


async def get_twilio_status() -> dict:
    """Check Twilio configuration status"""
    return {
        "enabled": TWILIO_ENABLED,
        "phone_number": TWILIO_PHONE_NUMBER if TWILIO_ENABLED else None,
        "configured": bool(TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN)
    }


def normalize_phone(phone: str) -> str:
    """Normalize phone number to E.164 format"""
    # Remove all non-digit characters except +
    cleaned = ''.join(c for c in phone if c.isdigit() or c == '+')
    
    # Add + if not present and starts with country code
    if not cleaned.startswith('+'):
        # Assume US number if 10 digits
        if len(cleaned) == 10:
            cleaned = '+1' + cleaned
        elif len(cleaned) == 11 and cleaned.startswith('1'):
            cleaned = '+' + cleaned
        else:
            cleaned = '+' + cleaned
    
    return cleaned
