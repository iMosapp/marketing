"""
Centralized Event Type Resolution — SINGLE SOURCE OF TRUTH.

Every file in the backend that needs to determine, create, or label an event type
MUST import from this module. No inline event type detection anywhere else.
"""
import re
import logging

logger = logging.getLogger(__name__)

# ===== SHORT URL link_type → contact_event event_type =====
LINK_TYPE_TO_EVENT = {
    "business_card": "digital_card_sent",
    "review_request": "review_request_sent",
    "congrats_card": "congrats_card_sent",
    "showcase": "showcase_shared",
    "link_page": "link_page_shared",
    "vcard": "vcard_sent",
    "birthday_card": "birthday_card_sent",
    "thank_you_card": "thank_you_card_sent",
    "thankyou_card": "thank_you_card_sent",
    "holiday_card": "holiday_card_sent",
    "welcome_card": "welcome_card_sent",
    "anniversary_card": "anniversary_card_sent",
}

# ===== event_type → human-readable label =====
EVENT_TYPE_LABELS = {
    "email_sent": "Email Sent",
    "email_failed": "Email Failed",
    "personal_sms": "Text Sent",
    "sms_sent": "SMS Sent",
    "digital_card_sent": "Digital Card Shared",
    "digital_card_shared": "Digital Card Shared",
    "review_request_sent": "Review Invite Sent",
    "congrats_card_sent": "Congrats Card Sent",
    "birthday_card_sent": "Birthday Card Sent",
    "thank_you_card_sent": "Thank You Card Sent",
    "thankyou_card_sent": "Thank You Card Sent",
    "holiday_card_sent": "Holiday Card Sent",
    "welcome_card_sent": "Welcome Card Sent",
    "anniversary_card_sent": "Anniversary Card Sent",
    "vcard_sent": "vCard Shared",
    "showcase_shared": "Showcase Shared",
    "link_page_shared": "Link Page Shared",
    "call_placed": "Call Placed",
    "new_contact": "Contact Created",
    "link_click": "Link Clicked",
    "link_clicked": "Link Clicked",
    "voice_note": "Voice Note",
    "new_contact_added": "New Contact Added",
    "note_updated": "Note Updated",
    "customer_reply": "Customer Reply",
    "congrats_card_viewed": "Viewed Congrats Card",
    "birthday_card_viewed": "Viewed Birthday Card",
    "thankyou_card_viewed": "Viewed Thank You Card",
    "thank_you_card_viewed": "Viewed Thank You Card",
    "holiday_card_viewed": "Viewed Holiday Card",
    "welcome_card_viewed": "Viewed Welcome Card",
    "anniversary_card_viewed": "Viewed Anniversary Card",
    "digital_card_viewed": "Viewed Digital Card",
    "review_page_viewed": "Viewed Review Page",
    "review_link_clicked": "Clicked Review Link",
    "review_submitted": "Left a Review",
    "showcase_viewed": "Viewed Showcase",
    "link_page_viewed": "Viewed Link Page",
    "congrats_card_downloaded": "Congrats Card Downloaded",
    "welcome_card_downloaded": "Welcome Card Downloaded",
    "birthday_card_downloaded": "Birthday Card Downloaded",
    "holiday_card_downloaded": "Holiday Card Downloaded",
    "thankyou_card_downloaded": "Thank You Card Downloaded",
    "anniversary_card_downloaded": "Anniversary Card Downloaded",
    "congrats_card_shared": "Congrats Card Shared",
    "welcome_card_shared": "Welcome Card Shared",
    "birthday_card_shared": "Birthday Card Shared",
    "holiday_card_shared": "Holiday Card Shared",
    "thankyou_card_shared": "Thank You Card Shared",
    "anniversary_card_shared": "Anniversary Card Shared",
    "task_created": "Task Created",
    "task_completed": "Task Completed",
    "lead_reassigned": "Lead Reassigned",
    "sms_failed": "SMS Failed",
}

# ===== card_type field → event_type and display info =====
CARD_TYPE_SENT_INFO = {
    "congrats":     {"event_type": "congrats_card_sent",     "label": "Congrats Card Sent",     "icon": "gift",      "color": "#C9A962"},
    "birthday":     {"event_type": "birthday_card_sent",     "label": "Birthday Card Sent",     "icon": "gift",      "color": "#FF9500"},
    "anniversary":  {"event_type": "anniversary_card_sent",  "label": "Anniversary Card Sent",  "icon": "heart",     "color": "#FF2D55"},
    "holiday":      {"event_type": "holiday_card_sent",      "label": "Holiday Card Sent",      "icon": "snow",      "color": "#5AC8FA"},
    "thank_you":    {"event_type": "thank_you_card_sent",    "label": "Thank You Card Sent",    "icon": "thumbs-up", "color": "#34C759"},
    "thankyou":     {"event_type": "thank_you_card_sent",    "label": "Thank You Card Sent",    "icon": "thumbs-up", "color": "#34C759"},
    "welcome":      {"event_type": "welcome_card_sent",      "label": "Welcome Card Sent",      "icon": "hand-left", "color": "#007AFF"},
}

CARD_TYPE_VIEWED_INFO = {
    "congrats":     {"event_type": "congrats_card_viewed",    "label": "Viewed Congrats Card",    "icon": "eye", "color": "#C9A962"},
    "birthday":     {"event_type": "birthday_card_viewed",    "label": "Viewed Birthday Card",    "icon": "eye", "color": "#FF9500"},
    "anniversary":  {"event_type": "anniversary_card_viewed", "label": "Viewed Anniversary Card", "icon": "eye", "color": "#FF2D55"},
    "holiday":      {"event_type": "holiday_card_viewed",     "label": "Viewed Holiday Card",     "icon": "eye", "color": "#5AC8FA"},
    "thank_you":    {"event_type": "thankyou_card_viewed",    "label": "Viewed Thank You Card",   "icon": "eye", "color": "#34C759"},
    "thankyou":     {"event_type": "thankyou_card_viewed",    "label": "Viewed Thank You Card",   "icon": "eye", "color": "#34C759"},
    "welcome":      {"event_type": "welcome_card_viewed",     "label": "Viewed Welcome Card",     "icon": "eye", "color": "#007AFF"},
}

# Regex to extract short code from /api/s/{code}
_SHORT_CODE_RE = re.compile(r'/api/s/([A-Za-z0-9]+)')


def get_event_label(event_type: str) -> str:
    """Get a human-readable label for any event type."""
    return EVENT_TYPE_LABELS.get(event_type, event_type.replace("_", " ").title() if event_type else "Activity")


def get_card_sent_info(card_type: str) -> dict:
    """Get event_type, label, icon, color for a sent card."""
    return CARD_TYPE_SENT_INFO.get(card_type, {
        "event_type": f"{card_type}_card_sent",
        "label": f"{card_type.replace('_', ' ').title()} Card Sent",
        "icon": "gift",
        "color": "#C9A962",
    })


def get_card_viewed_info(card_type: str) -> dict:
    """Get event_type, label, icon, color for a viewed card."""
    return CARD_TYPE_VIEWED_INFO.get(card_type, {
        "event_type": f"{card_type}_card_viewed",
        "label": f"Viewed {card_type.replace('_', ' ').title()} Card",
        "icon": "eye",
        "color": "#C9A962",
    })


async def resolve_event_type(content: str, db, explicit_event_type: str = None) -> str:
    """
    THE authoritative function for determining event_type from message content.

    Priority:
    1. Explicit event_type passed from the frontend (highest priority)
    2. DB lookup: extract short code from /api/s/{code}, look up link_type
    3. URL pattern matching (for non-short-URL messages)
    4. Keyword detection (lowest priority)
    5. Default: 'personal_sms'
    """
    # 1. Explicit from frontend
    if explicit_event_type:
        logger.info(f"[EventType] Using explicit: {explicit_event_type}")
        return explicit_event_type

    content_lower = content.lower()

    # 2. DB lookup for short URLs
    match = _SHORT_CODE_RE.search(content)
    if match:
        short_code = match.group(1)
        try:
            doc = await db.short_urls.find_one({"short_code": short_code}, {"link_type": 1})
            if doc and doc.get("link_type"):
                resolved = LINK_TYPE_TO_EVENT.get(doc["link_type"])
                if resolved:
                    logger.info(f"[EventType] DB lookup: link_type={doc['link_type']} -> {resolved}")
                    return resolved
        except Exception as e:
            logger.warning(f"[EventType] DB lookup failed for {short_code}: {e}")

    # 3. Direct URL pattern matching
    if '/card/' in content and '/vcard/' not in content:
        return 'digital_card_sent'
    if '/review/' in content:
        return 'review_request_sent'
    if '/vcard/' in content:
        return 'vcard_sent'
    if '/showcase/' in content:
        return 'showcase_shared'
    if '/l/' in content or '/linkpage/' in content:
        return 'link_page_shared'
    if '/birthday/' in content:
        return 'birthday_card_sent'

    # 3b. /congrats/{card_id} URLs — ALL card types use this prefix, so we MUST
    #     look up the actual card_type from the DB before defaulting to congrats.
    _card_id_re = re.compile(r'/congrats/([A-Za-z0-9\-]{6,36})')
    card_id_match = _card_id_re.search(content)
    if card_id_match:
        card_id_val = card_id_match.group(1)
        # Strip query params if any (e.g. ?ref=xxx)
        card_id_val = card_id_val.split('?')[0]
        try:
            card_doc = await db.congrats_cards.find_one(
                {"card_id": card_id_val},
                {"card_type": 1}
            )
            if card_doc:
                actual_card_type = card_doc.get("card_type", "congrats")
                resolved = CARD_TYPE_SENT_INFO.get(actual_card_type, {}).get("event_type")
                if resolved:
                    logger.info(f"[EventType] Card DB lookup: card_id={card_id_val}, card_type={actual_card_type} -> {resolved}")
                    return resolved
        except Exception as e:
            logger.warning(f"[EventType] Card DB lookup failed for {card_id_val}: {e}")
        # Fallback: if DB lookup fails, still default to congrats
        return 'congrats_card_sent'

    # 4. Keyword detection — ONLY when message also contains a URL or link indicator.
    #    A plain text like "congrats on the sale!" should NOT be classified as a card send.
    has_url = bool(re.search(r'https?://', content_lower))
    if has_url:
        if 'birthday' in content_lower and ('card' in content_lower or 'happy birthday' in content_lower):
            return 'birthday_card_sent'
        if 'congrats' in content_lower or 'congratulations' in content_lower:
            return 'congrats_card_sent'
        if 'thank' in content_lower and 'card' in content_lower:
            return 'thank_you_card_sent'
        if 'anniversary' in content_lower:
            return 'anniversary_card_sent'
        if 'holiday' in content_lower:
            return 'holiday_card_sent'
        if 'welcome' in content_lower and 'card' in content_lower:
            return 'welcome_card_sent'

    # 5. Default
    return 'personal_sms'
