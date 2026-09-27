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


async def get_rep_twilio_number(user_id: str) -> str | None:
    """
    Look up a rep's dedicated Twilio number by user_id.
    Always call this before send_sms() for rep-to-customer communications.
    Returns None if the rep has no dedicated number (falls back to Messaging Service).
    """
    try:
        from routers.database import get_db
        from bson import ObjectId
        db = get_db()
        rep = await db.users.find_one(
            {"_id": ObjectId(user_id)},
            {"twilio_number": 1, "mvpline_number": 1}
        )
        return (rep or {}).get("twilio_number") or (rep or {}).get("mvpline_number")
    except Exception:
        return None



MMS_SAFE_TYPES = ("image/jpeg", "image/jpg", "image/png", "image/gif")


def mms_safe_media(urls: Optional[List[str]]) -> List[str]:
    """Our image store serves WebP, which US carriers reject (Twilio 12300). Ask for a JPEG rendition."""
    out = []
    for u in urls or []:
        if not u:
            continue
        if "/api/images/" in u and "format=" not in u:
            u = f"{u}{'&' if '?' in u else '?'}format=jpeg"
        out.append(u)
    return out


def _status_callback_url() -> Optional[str]:
    base = (os.environ.get("PUBLIC_FACING_URL") or os.environ.get("APP_URL") or "").rstrip("/")
    if not base.startswith("https://") or "localhost" in base:
        return None
    return f"{base}/api/webhooks/twilio/status"


def _held_by_preview_guard(to_phone: str) -> bool:
    """SMS_SEND_ONLY_TO (preview .env): comma list of number prefixes that may really receive texts; everyone else gets a mock success.
    Only ever active on the preview runtime: Deploy copies .env keys to production, where this must be inert."""
    from services.runtime_env import is_preview_runtime
    if not is_preview_runtime():
        return False
    allow = [p.strip() for p in os.environ.get("SMS_SEND_ONLY_TO", "").split(",") if p.strip()]
    return bool(allow) and not any(to_phone.startswith(p) for p in allow)


async def send_sms(
    to_phone: str,
    message: str,
    media_urls: Optional[List[str]] = None,
    from_phone: Optional[str] = None,  # Rep's dedicated number — overrides Messaging Service
    *,
    org_id: Optional[str] = None,
    user_id: Optional[str] = None,
    contact_id: Optional[str] = None,
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
        org_id / user_id / contact_id: optional attribution for usage tracking (resolved from from_phone when omitted)
    """
    to_phone = normalize_phone(to_phone)
    from services.twilio_errors import vcard_media_to_link
    message, media_urls = vcard_media_to_link(message, mms_safe_media(media_urls))

    if from_phone:
        try:
            from routers.database import get_db
            from services.twilio_tenant import send_block_reason
            blocked = await send_block_reason(get_db(), normalize_phone(from_phone))
        except Exception as e:
            logger.debug(f"[SMS] readiness gate skipped: {e}")
            blocked = ""
        if blocked:
            logger.warning(f"[SMS] blocked from {from_phone}: {blocked}")
            return {"success": False, "error": blocked, "error_code": "not_ready", "mock": False}

    if _held_by_preview_guard(to_phone):
        logger.info(f"[SMS] preview guard: not sending to {to_phone} | {message[:60]}...")
        return {"success": True, "message_sid": "GUARD_" + str(abs(hash(message + to_phone)))[:8], "sid": "GUARD_" + str(abs(hash(message + to_phone)))[:8], "mock": True, "guarded": True}

    if not TWILIO_ENABLED or not twilio_client:
        logger.info(f"[MOCK SMS] To: {to_phone} | from: {from_phone or 'messaging_svc'} | {message[:60]}...")
        if media_urls:
            logger.info(f"[MOCK MMS] Media: {media_urls}")
        await _record_usage(from_phone, media_urls, 1, org_id, user_id)
        return {
            "success": True,
            "message_sid": "MOCK_" + str(abs(hash(message + to_phone)))[:8],
            "sid": "MOCK_" + str(abs(hash(message + to_phone)))[:8],
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
        cb = _status_callback_url()
        if cb:
            params["status_callback"] = cb  # delivery failures land in /api/webhooks/twilio/status

        client = await _client_for_sender(params.get("from_")) or twilio_client
        msg = client.messages.create(**params)
        logger.info(f"Twilio sent: {msg.sid} → {to_phone} from {params.get('from_', 'messaging_svc')} | status={msg.status}")
        await _record_usage(params.get("from_") or TWILIO_PHONE_NUMBER, media_urls, msg.num_segments, org_id, user_id)

        return {
            "success":     True,
            "message_sid": msg.sid,
            "sid":         msg.sid,
            "status":      msg.status,
            "mock":        False,
        }

    except TwilioRestException as e:
        logger.error(f"Twilio error → {to_phone}: [{e.code}] {e.msg}")
        return {"success": False, "error": e.msg, "error_code": e.code, "mock": False}
    except Exception as e:
        logger.error(f"SMS send error → {to_phone}: {e}")
        return {"success": False, "error": str(e), "mock": False}


async def _client_for_sender(from_phone: Optional[str]):
    """Numbers bought under an organization's subaccount must be sent with that subaccount's credentials."""
    if not from_phone:
        return None
    try:
        from routers.database import get_db
        from services import phone_numbers as pn
        from services import twilio_tenant as tenant
        db = get_db()
        num = await pn.by_phone(db, from_phone)
        acct = (num or {}).get("twilio_account_sid") or ""
        if not num or not acct or acct == tenant.parent_sid() or acct.startswith("ACdry"):
            return None
        org = await tenant.org_by_account_sid(db, acct)
        return tenant.client_for_org(org) if org else None
    except Exception as e:
        logger.debug(f"[SMS] subaccount client lookup skipped: {e}")
        return None


async def _record_usage(from_phone, media_urls, segments, org_id, user_id):
    try:
        from routers.database import get_db
        from services.phone_numbers import record_usage
        await record_usage(get_db(), direction="outbound", phone_number=from_phone or "", segments=int(segments or 1), mms=bool(media_urls), org_id=org_id, user_id=user_id)
    except Exception as e:
        logger.debug(f"[SMS] usage skipped: {e}")


async def fetch_message_status(sid: str, from_phone: Optional[str] = None) -> Optional[dict]:
    """Ask Twilio for a message's current status (used when no delivery receipt ever arrived)."""
    if not sid or sid.startswith(("MOCK_", "GUARD_")) or not TWILIO_ENABLED:
        return None
    try:
        client = await _client_for_sender(normalize_phone(from_phone) if from_phone else None) or twilio_client
        m = client.messages(sid).fetch()
        return {"status": m.status, "error_code": str(m.error_code) if m.error_code else None, "error_message": m.error_message,
                "date_sent": m.date_sent, "date_updated": m.date_updated, "num_media": int(m.num_media or 0)}
    except TwilioRestException as e:
        logger.warning(f"[SMS] status fetch failed for {sid}: [{e.code}] {e.msg}")
        return None
    except Exception as e:
        logger.warning(f"[SMS] status fetch error for {sid}: {e}")
        return None


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
