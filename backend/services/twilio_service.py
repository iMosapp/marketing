"""
Twilio Service - Handles SMS/MMS sending via Twilio API

Uses Messaging Service SID (A2P 10DLC compliant) when available.
Falls back to direct phone number if no Messaging Service configured.
"""
import os
import logging
from typing import Optional, List
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

logger = logging.getLogger(__name__)

# Initialize Twilio client
TWILIO_ACCOUNT_SID         = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN          = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER        = os.getenv("TWILIO_PHONE_NUMBER")
TWILIO_MESSAGING_SERVICE_SID = os.getenv("TWILIO_MESSAGING_SERVICE_SID")  # MG... — A2P compliant

# A2P: prefer messaging service; fall back to direct number
USE_MESSAGING_SERVICE = bool(TWILIO_MESSAGING_SERVICE_SID)

TWILIO_ENABLED = all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN]) and bool(
    TWILIO_MESSAGING_SERVICE_SID or TWILIO_PHONE_NUMBER
)

if TWILIO_ENABLED:
    try:
        twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        sender = f"Messaging Service {TWILIO_MESSAGING_SERVICE_SID}" if USE_MESSAGING_SERVICE else TWILIO_PHONE_NUMBER
        logger.info(f"Twilio initialized — sender: {sender}")
    except Exception as e:
        logger.error(f"Failed to initialize Twilio client: {e}")
        twilio_client = None
        TWILIO_ENABLED = False
else:
    twilio_client = None
    logger.warning("Twilio not configured — SMS/MMS will be mocked")


async def send_sms(
    to_phone: str,
    message: str,
    media_urls: Optional[List[str]] = None,
    from_phone: Optional[str] = None,  # Rep's dedicated number — overrides Messaging Service
) -> dict:
    """
    Send an SMS or MMS message via Twilio.

    When from_phone is provided (rep's dedicated Twilio number), sends directly
    from that number to maintain consistent sender identity.
    Falls back to Messaging Service SID for A2P compliance when no from_phone given.

    Args:
        to_phone:   Recipient phone number (any format — normalized to E.164)
        message:    Text message body
        media_urls: Optional media URLs for MMS (images, PDFs)
        from_phone: Rep's dedicated Twilio number — ALWAYS pass this for rep-to-customer sends
    """
    to_phone = normalize_phone(to_phone)

    if not TWILIO_ENABLED or not twilio_client:
        logger.info(f"[MOCK SMS] To: {to_phone} | from: {from_phone or 'messaging_svc'} | {message[:60]}...")
        if media_urls:
            logger.info(f"[MOCK MMS] Media: {media_urls}")
        return {
            "success": True,
            "message_sid": "MOCK_" + str(abs(hash(message + to_phone)))[:8],
            "mock": True,
        }

    try:
        params: dict = {"body": message, "to": to_phone}

        if from_phone:
            # Rep's dedicated number — use directly to maintain consistent sender identity
            params["from_"] = normalize_phone(from_phone)
            logger.debug(f"[SMS] Sending from rep number {from_phone}")
        elif USE_MESSAGING_SERVICE:
            # A2P 10DLC compliant — only for generic sends with no specific rep context
            params["messaging_service_sid"] = TWILIO_MESSAGING_SERVICE_SID
        else:
            params["from_"] = TWILIO_PHONE_NUMBER

        if media_urls:
            params["media_url"] = media_urls

        msg = twilio_client.messages.create(**params)
        logger.info(f"Twilio sent: {msg.sid} → {to_phone} from {params.get('from_', 'messaging_svc')} | status={msg.status}")

        return {
            "success":     True,
            "message_sid": msg.sid,
            "status":      msg.status,
            "mock":        False,
        }

    except TwilioRestException as e:
        logger.error(f"Twilio error → {to_phone}: [{e.code}] {e.msg}")
        return {"success": False, "error": e.msg, "error_code": e.code, "mock": False}
    except Exception as e:
        logger.error(f"SMS send error → {to_phone}: {e}")
        return {"success": False, "error": str(e), "mock": False}


async def get_twilio_status() -> dict:
    return {
        "enabled":               TWILIO_ENABLED,
        "phone_number":          TWILIO_PHONE_NUMBER,
        "messaging_service_sid": TWILIO_MESSAGING_SERVICE_SID,
        "use_messaging_service": USE_MESSAGING_SERVICE,
        "mock":                  not TWILIO_ENABLED,
    }


def normalize_phone(phone: str) -> str:
    """Normalize any phone format to E.164 (+1XXXXXXXXXX)."""
    cleaned = "".join(c for c in phone if c.isdigit() or c == "+")
    if not cleaned.startswith("+"):
        if len(cleaned) == 10:
            cleaned = "+1" + cleaned
        elif len(cleaned) == 11 and cleaned.startswith("1"):
            cleaned = "+" + cleaned
        else:
            cleaned = "+" + cleaned
    return cleaned
