"""
Universal customer interaction tracking.
Single endpoint for ALL customer-facing pages to log clicks, views, and actions.
"""
import logging
from datetime import datetime, timezone
from fastapi import APIRouter
from routers.database import get_db
from utils.contact_activity import log_activity_for_customer

router = APIRouter(prefix="/tracking", tags=["Tracking"])
logger = logging.getLogger(__name__)

# Maps (page, action) → (event_type, title template, icon, color)
ACTION_CONFIG = {
    # Congrats card
    ("congrats", "internal_review_submitted"): ("internal_review_submitted", "Submitted Internal Review", "star", "#FFD60A"),
    ("congrats", "online_review_clicked"): ("online_review_clicked", "Clicked Leave a Review Online", "open", "#FBBC04"),
    # Digital business card
    ("card", "viewed"): ("digital_card_viewed", "Viewed Digital Card", "eye", "#007AFF"),
    ("card", "call_clicked"): ("card_call_clicked", "Clicked Call from Card", "call", "#34C759"),
    ("card", "text_clicked"): ("card_text_clicked", "Clicked Text from Card", "chatbubble", "#5856D6"),
    ("card", "email_clicked"): ("card_email_clicked", "Clicked Email from Card", "mail", "#FF9500"),
    ("card", "vcard_saved"): ("vcard_saved", "Saved Contact (vCard)", "person-add", "#34C759"),
    ("card", "website_clicked"): ("card_website_clicked", "Clicked Website from Card", "globe", "#007AFF"),
    ("card", "social_clicked"): ("card_social_clicked", "Clicked Social Link", "logo-instagram", "#E1306C"),
    ("card", "share_clicked"): ("card_share_clicked", "Shared Digital Card", "share-social", "#007AFF"),
    ("card", "review_clicked"): ("card_review_clicked", "Clicked Review Link from Card", "star", "#FBBC04"),
    ("card", "directions_clicked"): ("card_directions_clicked", "Clicked Directions", "navigate", "#34C759"),
    # Store showroom
    ("showroom", "viewed"): ("showroom_viewed", "Viewed Store Showroom", "eye", "#5AC8FA"),
    ("showroom", "website_clicked"): ("showroom_website_clicked", "Clicked Website from Showroom", "globe", "#007AFF"),
    ("showroom", "directions_clicked"): ("showroom_directions_clicked", "Clicked Directions from Showroom", "navigate", "#34C759"),
    ("showroom", "team_member_clicked"): ("showroom_team_clicked", "Clicked Team Member Card", "person", "#5856D6"),
    # Review page
    ("review", "viewed"): ("review_page_viewed", "Viewed Review Page", "eye", "#FBBC04"),
    ("review", "review_link_clicked"): ("review_link_clicked", "Clicked Review Link", "open", "#FBBC04"),
    ("review", "review_submitted"): ("review_submitted", "Submitted a Review", "star", "#FFD60A"),
    # Link page
    ("link_page", "viewed"): ("link_page_viewed", "Viewed Link Page", "eye", "#5AC8FA"),
    ("link_page", "link_clicked"): ("link_page_link_clicked", "Clicked Link", "open", "#007AFF"),
}


@router.post("/event")
async def track_event(data: dict):
    """
    Universal tracking endpoint for customer-facing pages.
    
    Required: page, action, salesperson_id
    Optional: customer_phone, customer_name, card_id, metadata
    """
    page = data.get("page", "")
    action = data.get("action", "")
    salesperson_id = data.get("salesperson_id")
    customer_phone = data.get("customer_phone")
    customer_name = data.get("customer_name")
    metadata = data.get("metadata", {})
    
    if not salesperson_id:
        return {"tracked": False, "reason": "no salesperson_id"}
    
    config = ACTION_CONFIG.get((page, action))
    if not config:
        # Unknown action — still log it with generic info
        event_type = f"{page}_{action}"
        title = f"{action.replace('_', ' ').title()}"
        icon = "flag"
        color = "#8E8E93"
    else:
        event_type, title, icon, color = config
    
    # Add page-specific context to metadata
    metadata["page"] = page
    metadata["action"] = action
    if data.get("card_id"):
        metadata["card_id"] = data["card_id"]
    if data.get("url"):
        metadata["url"] = data["url"]
    if data.get("platform"):
        metadata["platform"] = data["platform"]
        title = f"{title} ({data['platform'].replace('_', ' ').title()})"
    
    description = data.get("description", "")
    
    try:
        event = await log_activity_for_customer(
            user_id=salesperson_id,
            customer_phone=customer_phone,
            customer_name=customer_name,
            event_type=event_type,
            title=title,
            description=description,
            icon=icon,
            color=color,
            category="customer_activity",
            metadata=metadata,
        )
        if event:
            logger.info(f"[Tracking] {page}/{action} logged for salesperson {salesperson_id}")
            return {"tracked": True, "event_type": event_type}
        else:
            logger.warning(f"[Tracking] {page}/{action} — contact not found for {customer_phone or customer_name}")
            return {"tracked": False, "reason": "contact_not_found"}
    except Exception as e:
        logger.error(f"[Tracking] Failed: {e}")
        return {"tracked": False, "reason": str(e)}
