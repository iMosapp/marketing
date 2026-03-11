"""
Universal customer interaction tracking.
Single endpoint for ALL customer-facing pages to log clicks, views, and actions.

ARCHITECTURE:
- Every customer-facing page calls POST /api/tracking/event for each click/action
- The frontend passes contact_id (from `cid` URL param, set by short URL redirect) for accurate attribution
- Falls back to phone/name lookup if contact_id is not available
- Events are logged to contact_events collection → counted in daily touchpoints, leaderboard, performance dashboard
"""
import logging
from datetime import datetime, timezone
from fastapi import APIRouter
from routers.database import get_db
from utils.contact_activity import log_activity_for_customer, log_customer_activity

router = APIRouter(prefix="/tracking", tags=["Tracking"])
logger = logging.getLogger(__name__)

# Maps (page, action) → (event_type, title template, icon, color)
ACTION_CONFIG = {
    # ── Congrats / Birthday / Holiday / Thank You / Welcome cards ──
    ("congrats", "viewed"): ("congrats_card_viewed", "Viewed Card", "eye", "#C9A962"),
    ("congrats", "internal_review_submitted"): ("internal_review_submitted", "Submitted Internal Review", "star", "#FFD60A"),
    ("congrats", "online_review_clicked"): ("online_review_clicked", "Clicked Leave a Review Online", "open", "#FBBC04"),
    ("congrats", "download_clicked"): ("congrats_card_downloaded", "Downloaded Card Image", "download", "#34C759"),
    ("congrats", "share_clicked"): ("congrats_card_shared", "Shared Card", "share-social", "#007AFF"),
    ("congrats", "share_facebook"): ("congrats_card_shared", "Shared Card (Facebook)", "logo-facebook", "#1877F2"),
    ("congrats", "share_twitter"): ("congrats_card_shared", "Shared Card (Twitter)", "logo-twitter", "#1DA1F2"),
    ("congrats", "share_instagram"): ("congrats_card_shared", "Shared Card (Instagram)", "logo-instagram", "#E4405F"),
    ("congrats", "share_linkedin"): ("congrats_card_shared", "Shared Card (LinkedIn)", "logo-linkedin", "#0A66C2"),
    ("congrats", "salesman_card_clicked"): ("card_salesman_clicked", "Clicked Salesman Digital Card", "person", "#C9A962"),
    ("congrats", "my_card_clicked"): ("card_quick_link_clicked", "Clicked My Card Link", "card", "#C9A962"),
    ("congrats", "my_page_clicked"): ("page_quick_link_clicked", "Clicked My Page Link", "globe", "#007AFF"),
    ("congrats", "showcase_clicked"): ("showcase_quick_link_clicked", "Clicked Showcase Link", "images", "#5856D6"),
    ("congrats", "links_clicked"): ("links_quick_link_clicked", "Clicked Links Page", "link", "#007AFF"),
    ("congrats", "opt_in_clicked"): ("opt_in_clicked", "Clicked Opt-In for Showcase", "star", "#C9A962"),

    # ── Digital business card ──
    ("card", "viewed"): ("digital_card_viewed", "Viewed Digital Card", "eye", "#007AFF"),
    ("card", "call_clicked"): ("card_call_clicked", "Clicked Call from Card", "call", "#34C759"),
    ("card", "text_clicked"): ("card_text_clicked", "Clicked Text from Card", "chatbubble", "#5856D6"),
    ("card", "email_clicked"): ("card_email_clicked", "Clicked Email from Card", "mail", "#FF9500"),
    ("card", "vcard_saved"): ("vcard_saved", "Saved Contact (vCard)", "person-add", "#34C759"),
    ("card", "website_clicked"): ("card_website_clicked", "Clicked Website from Card", "globe", "#007AFF"),
    ("card", "social_clicked"): ("card_social_clicked", "Clicked Social Link", "logo-instagram", "#E1306C"),
    ("card", "share_clicked"): ("card_share_clicked", "Shared Digital Card", "share-social", "#007AFF"),
    ("card", "review_clicked"): ("card_review_clicked", "Clicked Review from Card", "star", "#FBBC04"),
    ("card", "online_review_clicked"): ("card_online_review_clicked", "Clicked Online Review from Card", "open", "#FBBC04"),
    ("card", "internal_review_submitted"): ("card_internal_review_submitted", "Submitted Review from Card", "star", "#FFD60A"),
    ("card", "refer_clicked"): ("card_refer_clicked", "Clicked Refer a Friend", "people", "#34C759"),
    ("card", "directions_clicked"): ("card_directions_clicked", "Clicked Directions from Card", "navigate", "#34C759"),

    # ── Store card / showroom ──
    ("store_card", "viewed"): ("store_card_viewed", "Viewed Store Card", "eye", "#5AC8FA"),
    ("store_card", "call_clicked"): ("store_call_clicked", "Clicked Call from Store Card", "call", "#34C759"),
    ("store_card", "text_clicked"): ("store_text_clicked", "Clicked Text from Store Card", "chatbubble", "#5856D6"),
    ("store_card", "email_clicked"): ("store_email_clicked", "Clicked Email from Store Card", "mail", "#FF9500"),
    ("store_card", "website_clicked"): ("store_website_clicked", "Clicked Website from Store Card", "globe", "#007AFF"),
    ("store_card", "directions_clicked"): ("store_directions_clicked", "Clicked Directions from Store", "navigate", "#34C759"),
    ("store_card", "team_member_clicked"): ("store_team_clicked", "Clicked Team Member Card", "person", "#5856D6"),
    ("store_card", "review_link_clicked"): ("store_review_clicked", "Clicked Review Link from Store", "star", "#FBBC04"),

    # ── Review page ──
    ("review", "viewed"): ("review_page_viewed", "Viewed Review Page", "eye", "#FBBC04"),
    ("review", "review_link_clicked"): ("review_link_clicked", "Clicked Review Link", "open", "#FBBC04"),
    ("review", "review_submitted"): ("review_submitted", "Submitted a Review", "star", "#FFD60A"),

    # ── Link page ──
    ("link_page", "viewed"): ("link_page_viewed", "Viewed Link Page", "eye", "#5AC8FA"),
    ("link_page", "link_clicked"): ("link_page_link_clicked", "Clicked Link", "open", "#007AFF"),
}


@router.post("/event")
async def track_event(data: dict):
    """
    Universal tracking endpoint for customer-facing pages.

    Required: page, action, salesperson_id
    Preferred: contact_id (from cid URL param — most reliable attribution)
    Fallback: customer_phone, customer_name (legacy phone/name lookup)
    Optional: card_id, url, platform, description, metadata
    """
    page = data.get("page", "")
    action = data.get("action", "")
    salesperson_id = data.get("salesperson_id")
    contact_id = data.get("contact_id")
    customer_phone = data.get("customer_phone")
    customer_name = data.get("customer_name")
    metadata = data.get("metadata", {})

    if not salesperson_id:
        return {"tracked": False, "reason": "no salesperson_id"}

    config = ACTION_CONFIG.get((page, action))
    if not config:
        event_type = f"{page}_{action}"
        title = f"{action.replace('_', ' ').title()}"
        icon = "flag"
        color = "#8E8E93"
    else:
        event_type, title, icon, color = config

    # Build metadata
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
        event = None

        # ── Path 1: Direct contact_id (most reliable — from cid URL param) ──
        if contact_id:
            event = await log_customer_activity(
                user_id=salesperson_id,
                contact_id=contact_id,
                event_type=event_type,
                title=title,
                description=description,
                icon=icon,
                color=color,
                category="customer_activity",
                metadata=metadata,
            )

        # ── Path 2: Fallback to phone/name lookup ──
        if not event and (customer_phone or customer_name):
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
            logger.info(f"[Tracking] {page}/{action} logged for salesperson {salesperson_id} contact {contact_id or customer_phone or customer_name}")
            return {"tracked": True, "event_type": event_type}
        else:
            logger.warning(f"[Tracking] {page}/{action} — contact not found (cid={contact_id}, phone={customer_phone}, name={customer_name})")
            return {"tracked": False, "reason": "contact_not_found"}
    except Exception as e:
        logger.error(f"[Tracking] Failed: {e}")
        return {"tracked": False, "reason": str(e)}


# ── Engagement scoring weights ──
SCORE_WEIGHTS = {
    "viewed": 1,
    "digital_card_viewed": 1, "congrats_card_viewed": 1, "review_page_viewed": 1,
    "link_page_viewed": 1, "store_card_viewed": 1, "showcase_viewed": 1,
    "card_call_clicked": 3, "card_text_clicked": 3, "card_email_clicked": 3,
    "store_call_clicked": 3, "store_text_clicked": 3, "store_email_clicked": 3,
    "card_social_clicked": 2, "card_website_clicked": 2, "store_website_clicked": 2,
    "card_directions_clicked": 2, "store_directions_clicked": 2,
    "vcard_saved": 4, "card_share_clicked": 4,
    "congrats_card_downloaded": 3, "congrats_card_shared": 4,
    "card_salesman_clicked": 2, "card_quick_link_clicked": 2,
    "page_quick_link_clicked": 2, "showcase_quick_link_clicked": 2,
    "links_quick_link_clicked": 2, "opt_in_clicked": 3,
    "review_link_clicked": 3, "review_submitted": 5, "internal_review_submitted": 5,
    "card_review_clicked": 3, "card_online_review_clicked": 3,
    "card_refer_clicked": 5, "card_internal_review_submitted": 5,
    "link_page_link_clicked": 2, "store_team_clicked": 2, "store_review_clicked": 3,
}
DEFAULT_WEIGHT = 1


@router.get("/customer-rankings/{user_id}")
async def get_customer_rankings(user_id: str, period: str = "month", scope: str = "user"):
    """
    Get ranked list of contacts by engagement score.
    
    period: today, week, month, all
    scope: user (my contacts), org (store-wide), global
    """
    db = get_db()
    from datetime import timedelta
    
    now = datetime.now(timezone.utc)
    if period == "today":
        since = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "week":
        since = now - timedelta(days=7)
    elif period == "month":
        since = now - timedelta(days=30)
    else:
        since = datetime(2020, 1, 1, tzinfo=timezone.utc)
    
    # Build match filter — timestamps are stored as datetime objects
    match_filter = {"timestamp": {"$gte": since}}
    
    if scope == "user":
        match_filter["user_id"] = user_id
    elif scope == "org":
        user_doc = await db.users.find_one({"_id": user_id}, {"store_id": 1})
        if not user_doc:
            user_doc = await db.users.find_one({"id": user_id}, {"store_id": 1})
        store_id = user_doc.get("store_id") if user_doc else None
        if store_id:
            store_users = await db.users.find({"store_id": store_id}, {"_id": 1, "id": 1}).to_list(500)
            user_ids = list(set([str(u.get("_id", "")) for u in store_users] + [u.get("id", "") for u in store_users]))
            match_filter["user_id"] = {"$in": user_ids}
        else:
            match_filter["user_id"] = user_id
    # scope == "global" → no user filter
    
    # Aggregate events by contact
    pipeline = [
        {"$match": match_filter},
        {"$match": {"contact_id": {"$exists": True, "$ne": None}}},
        {"$group": {
            "_id": "$contact_id",
            "events": {"$push": {"event_type": "$event_type", "title": "$title", "timestamp": "$timestamp"}},
            "event_count": {"$sum": 1},
            "last_activity": {"$max": "$timestamp"},
            "user_id": {"$first": "$user_id"},
        }},
        {"$sort": {"event_count": -1}},
        {"$limit": 50},
    ]
    
    raw_rankings = await db.contact_events.aggregate(pipeline).to_list(50)
    
    # Enrich with contact info and calculate weighted score
    rankings = []
    for r in raw_rankings:
        contact_id = r["_id"]
        
        # Calculate weighted score
        score = 0
        event_breakdown = {}
        for ev in r.get("events", []):
            et = ev.get("event_type", "")
            weight = SCORE_WEIGHTS.get(et, DEFAULT_WEIGHT)
            score += weight
            event_breakdown[et] = event_breakdown.get(et, 0) + 1
        
        # Get contact name/phone
        from bson import ObjectId as BsonObjectId
        contact_queries = [{"id": contact_id}]
        try:
            contact_queries.append({"_id": BsonObjectId(contact_id)})
        except Exception:
            pass
        contact = await db.contacts.find_one(
            {"$or": contact_queries},
            {"_id": 0, "first_name": 1, "last_name": 1, "phone": 1, "photo_url": 1, "tags": 1}
        )
        if not contact:
            contact = {"first_name": "Unknown", "last_name": "", "phone": ""}
        
        name = f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip() or contact.get("phone", "Unknown")
        
        rankings.append({
            "contact_id": contact_id,
            "name": name,
            "phone": contact.get("phone", ""),
            "photo_url": contact.get("photo_url", ""),
            "tags": contact.get("tags", []),
            "score": score,
            "event_count": r["event_count"],
            "last_activity": r["last_activity"],
            "salesperson_id": r.get("user_id", ""),
            "breakdown": event_breakdown,
        })
    
    # Sort by weighted score (not just event count)
    rankings.sort(key=lambda x: x["score"], reverse=True)
    
    return {"rankings": rankings, "period": period, "scope": scope}