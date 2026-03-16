"""
Campaigns router - handles campaign CRUD, enrollments, and scheduler
"""
from fastapi import APIRouter, HTTPException
from bson import ObjectId
from datetime import datetime, timedelta, timezone
from typing import List, Optional
import logging

from models import Campaign, CampaignCreate
from routers.database import get_db, get_data_filter, get_user_by_id

router = APIRouter(prefix="/campaigns", tags=["Campaigns"])
logger = logging.getLogger(__name__)


# =====================================================
# PRE-BUILT CAMPAIGN TEMPLATES
# =====================================================

PREBUILT_TEMPLATES = [
    {
        "id": "sold_followup",
        "name": "Sold - Complete Follow-Up",
        "description": "A 5-step journey from delivery day through the 1-year anniversary. Builds a lasting relationship with genuine, personal touchpoints.",
        "type": "sold_followup",
        "trigger_tag": "sold",
        "icon": "car",
        "color": "#34C759",
        "delivery_mode": "manual",
        "ai_enabled": True,
        "sequences": [
            {
                "step": 1,
                "delay_days": 3,
                "delay_months": 0,
                "channel": "sms",
                "ai_generated": True,
                "step_context": "First check-in 3 days after delivery. Make sure everything is going well with the vehicle. Ask if they have any questions about features or settings. Keep it warm and personal.",
                "message_template": "Hey {name}, it's been a few days - just wanted to make sure everything's going smooth with the {vehicle}. Any questions about features, settings, how anything works? I'm here for you even after the papers are signed. Don't be a stranger!",
                "media_urls": [],
            },
            {
                "step": 2,
                "delay_days": 14,
                "delay_months": 0,
                "channel": "sms",
                "ai_generated": True,
                "step_context": "Two weeks in. Casual referral ask. Not pushy - just a natural 'if you know anyone' ask. Mention you'd take care of them the same way.",
                "message_template": "Hey {name}, hope you're loving the {vehicle}! Quick question - do you have any friends or family that might be in the market? I'd love to take care of them the same way I took care of you. No pressure at all, just thought I'd mention it!",
                "media_urls": [],
            },
            {
                "step": 3,
                "delay_days": 0,
                "delay_months": 2,
                "channel": "sms",
                "ai_generated": True,
                "step_context": "Around 75 days. First service is coming up. Offer to help schedule, mention loaner car availability. Be helpful and proactive, not salesy.",
                "message_template": "Hey {name}, heads up - you're getting close to your first service on the {vehicle}. Want me to get something scheduled for you? I can also check on a loaner if you need one while it's in. Just let me know and I'll handle everything!",
                "media_urls": [],
            },
            {
                "step": 4,
                "delay_days": 0,
                "delay_months": 7,
                "channel": "sms",
                "ai_generated": True,
                "step_context": "7-month touch base. Just checking in naturally. Going through notes, thought of them. No agenda, just genuine relationship maintenance.",
                "message_template": "Hey {name}, was just going through my notes and thought of you. How's the {vehicle} treating you? Everything running good? No agenda here - just wanted to check in. I'm always around if you ever need anything.",
                "media_urls": [],
            },
            {
                "step": 5,
                "delay_days": 0,
                "delay_months": 12,
                "channel": "sms",
                "ai_generated": True,
                "step_context": "1-year anniversary! Reference their delivery day. Express genuine surprise at how fast time flew. Ask how the vehicle is holding up. If there's a congrats photo from delivery, reference it warmly. Celebrate the milestone.",
                "message_template": "Hey {name}, can you believe it's been a YEAR already?! I was looking back at your delivery day and honestly it feels like last month. How's the {vehicle} holding up? I hope it's been everything you wanted and more. Here's to many more miles - congrats on the 1-year mark!",
                "media_urls": [],
            },
        ],
    },
    {
        "id": "be_back_nurture",
        "name": "Be-Back / Working Customer",
        "description": "Stay top of mind with customers who visited but haven't bought yet. Gentle, value-driven follow-ups that keep the door open without being pushy.",
        "type": "custom",
        "trigger_tag": "be_back",
        "icon": "refresh",
        "color": "#FF9500",
        "delivery_mode": "manual",
        "ai_enabled": True,
        "sequences": [
            {
                "step": 1,
                "delay_days": 1,
                "delay_months": 0,
                "channel": "sms",
                "ai_generated": True,
                "step_context": "Day after visit. Thank them for coming in. Reference the vehicle(s) they were looking at if known. Keep it casual and low-pressure. Let them know you're available.",
                "message_template": "Hey {name}, great meeting you yesterday! I know car shopping can be a lot, so no rush on anything. Just wanted you to know I'm here whenever you're ready or if any questions come up. I'll keep an eye out for anything I think you'd like.",
                "media_urls": [],
            },
            {
                "step": 2,
                "delay_days": 5,
                "delay_months": 0,
                "channel": "sms",
                "ai_generated": True,
                "step_context": "5 days after visit. Provide value - maybe a new option came in, or market insight. Not a hard sell. Create curiosity.",
                "message_template": "Hey {name}, just wanted to drop a quick note. A few things have changed on the lot since you were here and I saw something that made me think of you. Want me to send over some details? No pressure either way.",
                "media_urls": [],
            },
            {
                "step": 3,
                "delay_days": 14,
                "delay_months": 0,
                "channel": "sms",
                "ai_generated": True,
                "step_context": "Two weeks out. Last personal check-in before spacing out. Acknowledge their timeline. Offer to be a resource even if they're not buying from you.",
                "message_template": "Hey {name}, hope the search is going well! I know you'll find the right one when the timing is right. If you ever want a second opinion or just want to bounce ideas off someone, I'm always around. No sales pitch, I promise.",
                "media_urls": [],
            },
            {
                "step": 4,
                "delay_days": 0,
                "delay_months": 1,
                "channel": "sms",
                "ai_generated": True,
                "step_context": "One month. Quick, casual check-in. Show you remember them. Keep the relationship warm.",
                "message_template": "Hey {name}, just a quick check-in - still looking or did you find something you love? Either way, I'm happy for you. Let me know if I can ever help!",
                "media_urls": [],
            },
        ],
    },
    {
        "id": "service_reminder",
        "name": "Service Reminder Series",
        "description": "Proactive service reminders that position you as their go-to person for everything vehicle-related. Builds loyalty and drives service revenue.",
        "type": "custom",
        "trigger_tag": "service_due",
        "icon": "construct",
        "color": "#007AFF",
        "delivery_mode": "manual",
        "ai_enabled": True,
        "sequences": [
            {
                "step": 1,
                "delay_days": 0,
                "delay_months": 0,
                "channel": "sms",
                "ai_generated": True,
                "step_context": "Service reminder triggered. Let them know you noticed their service is coming up. Offer to schedule and arrange everything. Mention loaner car if applicable.",
                "message_template": "Hey {name}, just a heads up - looks like your {vehicle} is coming up on a service. Want me to get something on the books for you? I can check on a loaner too if you need one. Just let me know and I'll handle all the details!",
                "media_urls": [],
            },
            {
                "step": 2,
                "delay_days": 7,
                "delay_months": 0,
                "channel": "sms",
                "ai_generated": True,
                "step_context": "Gentle follow-up if they haven't responded. Maybe mention current service specials if available. Keep it helpful, not nagging.",
                "message_template": "Hey {name}, just circling back on that service for the {vehicle}. I don't want you to miss anything important. I can usually get you in pretty quick if you want me to set it up. Just say the word!",
                "media_urls": [],
            },
            {
                "step": 3,
                "delay_days": 3,
                "delay_months": 0,
                "channel": "sms",
                "ai_generated": True,
                "step_context": "Post-service follow-up (triggered after service is completed). Check that everything went well. Show you care about the experience beyond the sale.",
                "message_template": "Hey {name}, how'd the service go on the {vehicle}? Everything taken care of? I always want to make sure my people are being treated right. Let me know if there's anything that wasn't handled!",
                "media_urls": [],
            },
        ],
    },
    {
        "id": "referral_thank_you",
        "name": "Referral Thank You & Nurture",
        "description": "When someone refers a friend, show genuine appreciation and keep them engaged as a brand ambassador. Makes them feel valued and encourages more referrals.",
        "type": "custom",
        "trigger_tag": "referral",
        "icon": "people",
        "color": "#AF52DE",
        "delivery_mode": "manual",
        "ai_enabled": True,
        "sequences": [
            {
                "step": 1,
                "delay_days": 0,
                "delay_months": 0,
                "channel": "sms",
                "ai_generated": True,
                "step_context": "Immediate thank you for the referral. Be genuinely grateful. Let them know you'll take great care of the person they sent. Make them feel like a VIP.",
                "message_template": "Hey {name}, I just wanted to say THANK YOU for sending your friend my way. That means a lot to me - seriously. I'm going to take great care of them, you have my word. You're the best!",
                "media_urls": [],
            },
            {
                "step": 2,
                "delay_days": 7,
                "delay_months": 0,
                "channel": "sms",
                "ai_generated": True,
                "step_context": "One week later. Quick update on the referral (without sharing private details). Show them their referral is being handled well.",
                "message_template": "Hey {name}, just wanted to give you a quick update - things are going great with the connection you made. Really appreciate you thinking of me. You've got good people in your circle!",
                "media_urls": [],
            },
            {
                "step": 3,
                "delay_days": 0,
                "delay_months": 3,
                "channel": "sms",
                "ai_generated": True,
                "step_context": "3-month check-in. Maintain the relationship. They're a referral source - treat them like gold. Ask how they're doing. Casually keep the referral door open.",
                "message_template": "Hey {name}, been a few months - just wanted to check in and see how you're doing! Hope everything's great on your end. You know I always appreciate you, and if you ever run into anyone else looking, you know where to find me!",
                "media_urls": [],
            },
        ],
    },
    {
        "id": "vip_customer_care",
        "name": "VIP Customer Experience",
        "description": "Premium touchpoints for your best customers. These are the ones who buy, refer, and advocate for you. Treat them like the unforgettable people they are.",
        "type": "custom",
        "trigger_tag": "vip",
        "icon": "diamond",
        "color": "#FFD60A",
        "delivery_mode": "manual",
        "ai_enabled": True,
        "sequences": [
            {
                "step": 1,
                "delay_days": 0,
                "delay_months": 0,
                "channel": "sms",
                "ai_generated": True,
                "step_context": "VIP tag just applied. Welcome them to VIP status. Make them feel special. Let them know they have priority access to you.",
                "message_template": "Hey {name}, just wanted to let you know - you're one of my VIP people. That means you've got my direct line for anything, anytime. New inventory, service needs, questions about your {vehicle} - you come first. I appreciate you!",
                "media_urls": [],
            },
            {
                "step": 2,
                "delay_days": 0,
                "delay_months": 1,
                "channel": "sms",
                "ai_generated": True,
                "step_context": "Monthly VIP touch. Share something exclusive - early access to inventory, a market insight, or just a genuine personal check-in. Make them feel like an insider.",
                "message_template": "Hey {name}, just wanted to reach out with a quick insider update. We've got some interesting things coming in that I thought you might want first look at. Want me to keep you posted? Hope everything's going great with you!",
                "media_urls": [],
            },
            {
                "step": 3,
                "delay_days": 0,
                "delay_months": 3,
                "channel": "email",
                "ai_generated": True,
                "step_context": "Quarterly VIP email. More detailed touchpoint. Could include market trends, trade-in value update, or seasonal vehicle tips. Position yourself as their trusted automotive advisor.",
                "message_template": "Subject: Quick update for you, {name}\n\nHey {name},\n\nJust wanted to drop you a quick note. As one of my top customers, I like to keep you in the loop.\n\nA few things on my radar that might interest you:\n- Market values have been shifting, and your {vehicle} is holding strong\n- Some great new inventory hitting the lot soon\n- If you ever want a no-obligation trade appraisal, just say the word\n\nHope everything's going well. Don't hesitate to reach out for anything!\n\nTalk soon,\n{salesperson_name}",
                "media_urls": [],
            },
            {
                "step": 4,
                "delay_days": 0,
                "delay_months": 6,
                "channel": "sms",
                "ai_generated": True,
                "step_context": "6-month VIP check-in. Personal, warm, and genuine. Reference the relationship. Keep the bond strong.",
                "message_template": "Hey {name}, can't believe it's been 6 months already. Just wanted to check in and see how everything's going with the {vehicle} and life in general. You know I'm always in your corner. Let's catch up soon!",
                "media_urls": [],
            },
        ],
    },
    {
        "id": "review_followup",
        "name": "Review Follow-Up",
        "description": "Gentle follow-up after sending a review invite. Auto-completes when the customer clicks the review link — no nagging.",
        "type": "custom",
        "trigger_tag": "review_sent",
        "icon": "star",
        "color": "#FFD60A",
        "delivery_mode": "manual",
        "ai_enabled": True,
        "sequences": [
            {
                "step": 1,
                "delay_days": 2,
                "delay_months": 0,
                "channel": "sms",
                "ai_generated": True,
                "step_context": "It's been 2 days since you sent the review invite. Gently check if they had a chance to leave a review. Don't be pushy — keep it casual and appreciative.",
                "message_template": "Hey {name}, hope you're enjoying the new ride! If you get a sec, I'd really appreciate a quick review. It helps me out a ton. No pressure at all though!",
                "media_urls": [],
            },
            {
                "step": 2,
                "delay_days": 3,
                "delay_months": 0,
                "channel": "sms",
                "ai_generated": True,
                "step_context": "Final gentle nudge about the review. This is the last follow-up — keep it light and thankful regardless of whether they leave one.",
                "message_template": "Hey {name}, last thing from me on this - just wanted to say thanks again for your business. If you ever get a chance to share your experience, it would mean the world. Either way, I'm here for anything you need!",
                "media_urls": [],
            },
        ],
    },
]


@router.get("/templates/prebuilt")
async def get_prebuilt_templates():
    """Get all pre-built campaign templates."""
    # Return templates without full message content for the selector UI
    summaries = []
    for t in PREBUILT_TEMPLATES:
        summaries.append({
            "id": t["id"],
            "name": t["name"],
            "description": t["description"],
            "type": t["type"],
            "trigger_tag": t["trigger_tag"],
            "icon": t["icon"],
            "color": t["color"],
            "delivery_mode": t["delivery_mode"],
            "ai_enabled": t["ai_enabled"],
            "step_count": len(t["sequences"]),
            "total_duration": _calc_duration(t["sequences"]),
        })
    return summaries


@router.get("/templates/prebuilt/{template_id}")
async def get_prebuilt_template(template_id: str):
    """Get a specific pre-built template with full details."""
    for t in PREBUILT_TEMPLATES:
        if t["id"] == template_id:
            return t
    raise HTTPException(status_code=404, detail="Template not found")


def _calc_duration(sequences: list) -> str:
    """Calculate total campaign duration as a readable string."""
    total_days = 0
    for s in sequences:
        total_days += s.get("delay_days", 0) + s.get("delay_months", 0) * 30
    if total_days >= 365:
        return f"{total_days // 365} year{'s' if total_days >= 730 else ''}"
    if total_days >= 30:
        return f"{total_days // 30} month{'s' if total_days >= 60 else ''}"
    return f"{total_days} days"


async def check_campaign_permission(user_id: str, action: str = "edit") -> dict:
    """
    Check if user has permission to perform campaign actions.
    
    Returns:
        dict with 'allowed' boolean and 'reason' string
    
    Permission levels:
    - super_admin, org_admin: Always allowed
    - store_manager: Allowed unless store settings explicitly disable
    - user (sales): Only if store settings enable 'allow_sales_campaigns'
    """
    db = get_db()
    user = await get_user_by_id(user_id)
    
    if not user:
        return {"allowed": False, "reason": "User not found"}
    
    role = user.get("role", "user")
    
    # Super admins and org admins always have full access
    if role in ["super_admin", "org_admin"]:
        return {"allowed": True, "reason": "Admin access"}
    
    # Get user's store settings
    store_id = user.get("store_id")
    if not store_id and user.get("store_ids"):
        store_id = user.get("store_ids")[0]  # Use primary store
    
    if not store_id:
        # No store assigned - default to allowed for managers
        if role == "store_manager":
            return {"allowed": True, "reason": "Manager default access"}
        return {"allowed": False, "reason": "No store assigned"}
    
    # Get store settings
    store = await db.stores.find_one({"_id": ObjectId(store_id)})
    if not store:
        return {"allowed": False, "reason": "Store not found"}
    
    settings = store.get("settings", {})
    campaign_settings = settings.get("campaigns", {})
    
    # Store managers - check if manager campaigns are disabled
    if role == "store_manager":
        if campaign_settings.get("managers_can_edit", True):
            return {"allowed": True, "reason": "Manager access enabled"}
        return {"allowed": False, "reason": "Campaign editing disabled for managers at this store"}
    
    # Sales reps - check if sales campaigns are enabled
    if role == "user":
        if campaign_settings.get("sales_can_edit", False):
            return {"allowed": True, "reason": "Sales access enabled"}
        return {"allowed": False, "reason": "Campaign editing not enabled for sales at this store"}
    
    return {"allowed": False, "reason": "Unknown role"}

def calculate_next_send_date(step: dict) -> datetime:
    """Calculate when the next message should be sent based on step configuration.
    Supports delay_hours, delay_days, delay_months fields.
    """
    now = datetime.utcnow()

    delay_hours = step.get('delay_hours', 0)
    delay_days = step.get('delay_days', 0)
    delay_months = step.get('delay_months', 0)
    if delay_hours or delay_days or delay_months:
        return now + timedelta(hours=delay_hours, days=delay_days + delay_months * 30)

    # Legacy fields
    delay_value = step.get('delay_value', 1)
    delay_unit = step.get('delay_unit', 'days')
    
    if delay_unit == 'minutes':
        return now + timedelta(minutes=delay_value)
    elif delay_unit == 'hours':
        return now + timedelta(hours=delay_value)
    elif delay_unit == 'days':
        return now + timedelta(days=delay_value)
    elif delay_unit == 'weeks':
        return now + timedelta(weeks=delay_value)
    else:
        return now + timedelta(days=delay_value)

@router.get("/{user_id}/permissions")
async def get_campaign_permissions(user_id: str):
    """Check if user has campaign editing permissions"""
    permission = await check_campaign_permission(user_id)
    return permission


@router.post("/{user_id}", response_model=Campaign)
async def create_campaign(user_id: str, campaign_data: CampaignCreate):
    """Create a nurture campaign with permission check"""
    # Check permissions
    permission = await check_campaign_permission(user_id, "create")
    if not permission["allowed"]:
        raise HTTPException(status_code=403, detail=permission["reason"])
    
    campaign_dict = campaign_data.dict()
    campaign_dict['user_id'] = user_id
    campaign_dict['created_at'] = datetime.utcnow()
    
    # Prevent exact duplicate campaigns (same name + type for same user)
    existing = await get_db().campaigns.find_one({
        "user_id": user_id,
        "name": campaign_dict.get("name"),
        "type": campaign_dict.get("type"),
    })
    if existing:
        existing["_id"] = str(existing["_id"])
        return Campaign(**existing)
    
    result = await get_db().campaigns.insert_one(campaign_dict)
    campaign_dict['_id'] = result.inserted_id
    
    logger.info(f"Campaign created: {campaign_dict['name']} with {len(campaign_dict.get('sequences', []))} steps")
    
    return Campaign(**campaign_dict)

@router.get("/{user_id}", response_model=List[Campaign])
async def get_campaigns(user_id: str):
    """Get campaigns for a user: their own + store-level campaigns they should see."""
    db = get_db()
    user = await get_user_by_id(user_id)
    
    # Build query: user's own campaigns OR store-level campaigns from their store
    conditions = [{"user_id": user_id}]
    
    if user:
        store_id = user.get("store_id")
        if not store_id and user.get("store_ids"):
            store_id = user.get("store_ids", [None])[0]
        if store_id:
            # Include store-level campaigns from any user in the same store
            store_user_ids = []
            async for u in db.users.find({"store_id": store_id}, {"_id": 1}):
                store_user_ids.append(str(u["_id"]))
            if store_user_ids:
                conditions.append({
                    "user_id": {"$in": store_user_ids},
                    "ownership_level": "store"
                })
    
    campaigns = await db.campaigns.find({"$or": conditions}).limit(500).to_list(500)
    
    # Deduplicate by name+type (prefer user's own over store-level)
    seen = {}
    result = []
    for camp in campaigns:
        key = (camp.get("name"), camp.get("type"))
        if key not in seen:
            seen[key] = camp
            result.append(camp)
        elif camp.get("user_id") == user_id:
            # User's own version takes priority
            idx = next(i for i, c in enumerate(result) if (c.get("name"), c.get("type")) == key)
            result[idx] = camp
    
    return [Campaign(**{**camp, "_id": str(camp["_id"])}) for camp in result]

# ============= PENDING SENDS (Manual Campaigns) =============
# NOTE: These routes MUST be above /{user_id}/{campaign_id} to avoid route collision.

@router.get("/{user_id}/pending-sends")
async def get_pending_sends(user_id: str):
    """Get all pending manual campaign messages waiting for user to send."""
    db = get_db()
    pending = await db.campaign_pending_sends.find({
        "user_id": user_id,
        "status": "pending",
    }).sort("created_at", -1).to_list(100)
    for p in pending:
        p["_id"] = str(p["_id"])
    return pending


@router.post("/{user_id}/pending-sends/{send_id}/complete")
async def mark_pending_send_complete(user_id: str, send_id: str):
    """Mark a manual campaign send as completed (user has sent the message)."""
    db = get_db()
    result = await db.campaign_pending_sends.update_one(
        {"_id": ObjectId(send_id), "user_id": user_id},
        {"$set": {"status": "sent", "sent_at": datetime.now(timezone.utc)}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Pending send not found")
    send_doc = await db.campaign_pending_sends.find_one({"_id": ObjectId(send_id)})
    if send_doc:
        channel = send_doc.get("channel", "sms")
        event_type = "email_sent" if channel == "email" else "sms_sent"
        await db.contact_events.insert_one({
            "event_type": event_type,
            "user_id": user_id,
            "contact_id": send_doc.get("contact_id", ""),
            "description": f"Campaign '{send_doc.get('campaign_name', '')}' step {send_doc.get('step', 0)} (manual)",
            "timestamp": datetime.now(timezone.utc),
            "manual_campaign": True,
        })
    return {"success": True, "message": "Marked as sent"}


@router.post("/{user_id}/pending-sends/{send_id}/skip")
async def skip_pending_send(user_id: str, send_id: str):
    """Skip a manual campaign send."""
    db = get_db()
    result = await db.campaign_pending_sends.update_one(
        {"_id": ObjectId(send_id), "user_id": user_id},
        {"$set": {"status": "skipped", "skipped_at": datetime.utcnow()}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Pending send not found")
    return {"success": True, "message": "Skipped"}


@router.get("/{user_id}/{campaign_id}")
async def get_campaign(user_id: str, campaign_id: str):
    """Get a specific campaign with role-based access check"""
    base_filter = await get_data_filter(user_id)
    
    campaign = await get_db().campaigns.find_one({"$and": [{"_id": ObjectId(campaign_id)}, base_filter]})
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    campaign['_id'] = str(campaign['_id'])
    return campaign

@router.put("/{user_id}/{campaign_id}")
async def update_campaign(user_id: str, campaign_id: str, update_data: dict):
    """Update a campaign with role-based access and permission check"""
    # Check permissions
    permission = await check_campaign_permission(user_id, "edit")
    if not permission["allowed"]:
        raise HTTPException(status_code=403, detail=permission["reason"])
    
    base_filter = await get_data_filter(user_id)
    
    allowed_fields = ['name', 'type', 'trigger_tag', 'date_type', 'segment_tags', 'sequences', 'send_time', 'active', 'media_urls', 'message_template', 'delivery_mode', 'ai_enabled', 'ownership_level', 'action_type', 'card_type']
    update_dict = {k: v for k, v in update_data.items() if k in allowed_fields}
    
    result = await get_db().campaigns.update_one(
        {"$and": [{"_id": ObjectId(campaign_id)}, base_filter]},
        {"$set": update_dict}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    return {"message": "Campaign updated successfully"}

@router.delete("/{user_id}/{campaign_id}")
async def delete_campaign(user_id: str, campaign_id: str):
    """Delete a campaign and its enrollments with role-based access and permission check"""
    # Check permissions
    permission = await check_campaign_permission(user_id, "delete")
    if not permission["allowed"]:
        raise HTTPException(status_code=403, detail=permission["reason"])
    
    base_filter = await get_data_filter(user_id)
    
    result = await get_db().campaigns.delete_one({"$and": [{"_id": ObjectId(campaign_id)}, base_filter]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Delete all enrollments for this campaign
    await get_db().campaign_enrollments.delete_many({"campaign_id": campaign_id})
    
    return {"message": "Campaign deleted successfully"}


# ============= ENROLLMENT ENDPOINTS =============
@router.post("/{user_id}/{campaign_id}/enroll/{contact_id}")
async def enroll_contact_in_campaign(user_id: str, campaign_id: str, contact_id: str):
    """Enroll a contact in a campaign with role-based access check"""
    base_filter = await get_data_filter(user_id)
    
    # Get campaign (with role-based access)
    campaign = await get_db().campaigns.find_one({"$and": [{"_id": ObjectId(campaign_id)}, base_filter]})
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    if not campaign.get('active', False):
        raise HTTPException(status_code=400, detail="Campaign is not active")
    
    # Get contact (with role-based access)
    contact = await get_db().contacts.find_one({"$and": [{"_id": ObjectId(contact_id)}, base_filter]})
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    # Check if already enrolled
    existing = await get_db().campaign_enrollments.find_one({
        "campaign_id": campaign_id,
        "contact_id": contact_id,
        "status": "active"
    })
    if existing:
        raise HTTPException(status_code=400, detail="Contact is already enrolled in this campaign")
    
    # Calculate when to send first message
    sequences = campaign.get('sequences', [])
    first_step = sequences[0] if sequences else None
    
    if first_step:
        next_send = calculate_next_send_date(first_step)
    else:
        next_send = datetime.utcnow()
    
    # Create enrollment
    enrollment = {
        "user_id": user_id,
        "campaign_id": campaign_id,
        "contact_id": contact_id,
        "contact_name": f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip(),
        "contact_phone": contact.get('phone', ''),
        "current_step": 1,
        "status": "active",
        "enrolled_at": datetime.utcnow(),
        "next_send_at": next_send,
        "messages_sent": []
    }
    
    result = await get_db().campaign_enrollments.insert_one(enrollment)
    enrollment['_id'] = str(result.inserted_id)
    
    logger.info(f"Contact {contact_id} enrolled in campaign {campaign_id}, first message at {next_send}")
    
    return enrollment

@router.get("/{user_id}/{campaign_id}/enrollments")
async def get_campaign_enrollments(user_id: str, campaign_id: str, status: str = None):
    """Get all enrollments for a campaign with role-based access"""
    base_filter = await get_data_filter(user_id)
    
    # First verify user has access to this campaign
    campaign = await get_db().campaigns.find_one({"$and": [{"_id": ObjectId(campaign_id)}, base_filter]})
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Get enrollments for this campaign (with role-based user_id filter)
    query = {"$and": [{"campaign_id": campaign_id}, base_filter]}
    if status:
        query["$and"].append({"status": status})
    
    enrollments = await get_db().campaign_enrollments.find(query).limit(500).to_list(500)
    return [{**e, "_id": str(e["_id"])} for e in enrollments]

@router.delete("/{user_id}/{campaign_id}/enrollments/{enrollment_id}")
async def cancel_enrollment(user_id: str, campaign_id: str, enrollment_id: str):
    """Cancel a campaign enrollment with role-based access check"""
    base_filter = await get_data_filter(user_id)
    
    result = await get_db().campaign_enrollments.update_one(
        {"$and": [{"_id": ObjectId(enrollment_id)}, base_filter]},
        {"$set": {"status": "cancelled"}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Enrollment not found")
    
    return {"message": "Enrollment cancelled"}

# ============= SCHEDULER ENDPOINTS =============
@router.post("/scheduler/trigger")
async def trigger_scheduler():
    """Manually trigger the campaign scheduler to process pending messages"""
    now = datetime.utcnow()
    
    # Find all active enrollments with messages due
    pending = await get_db().campaign_enrollments.find({
        "status": "active",
        "next_send_at": {"$lte": now}
    }).to_list(100)
    
    processed = 0
    for enrollment in pending:
        try:
            # Get campaign
            campaign = await get_db().campaigns.find_one({"_id": ObjectId(enrollment['campaign_id'])})
            if not campaign or not campaign.get('active', False):
                continue
            
            sequences = campaign.get('sequences', [])
            current_step = enrollment.get('current_step', 1)
            
            if current_step > len(sequences):
                # Campaign complete
                await get_db().campaign_enrollments.update_one(
                    {"_id": enrollment['_id']},
                    {"$set": {"status": "completed"}}
                )
                continue
            
            # Get current step
            step = sequences[current_step - 1]
            action_type = step.get('action_type', 'message')
            delivery_mode = campaign.get('delivery_mode', 'manual')
            
            if action_type == 'send_card':
                card_type = step.get('card_type', 'congrats')
                card_labels = {
                    'congrats': 'Congrats Card', 'birthday': 'Birthday Card',
                    'anniversary': 'Anniversary Card', 'thankyou': 'Thank You Card',
                    'welcome': 'Welcome Card', 'holiday': 'Holiday Card',
                }
                card_label = card_labels.get(card_type, card_type.title() + ' Card')
                
                if delivery_mode == 'automated':
                    # TODO: Auto-generate and send card via Twilio when live
                    logger.info(f"[MOCK] Auto-sending {card_label} to {enrollment['contact_phone']}")
                else:
                    contact_display = enrollment.get('contact_name', 'contact')
                    pending_result = await get_db().campaign_pending_sends.insert_one({
                        "user_id": enrollment['user_id'],
                        "campaign_id": enrollment['campaign_id'],
                        "campaign_name": campaign.get('name', ''),
                        "contact_id": enrollment.get('contact_id', ''),
                        "contact_name": contact_display,
                        "contact_phone": enrollment.get('contact_phone', ''),
                        "step": current_step,
                        "action_type": "send_card",
                        "card_type": card_type,
                        "message": f"Send a {card_label} to {contact_display}",
                        "channel": step.get('channel', 'sms'),
                        "status": "pending",
                        "created_at": now,
                    })
                    # Create task on to-do list
                    await get_db().tasks.insert_one({
                        "user_id": enrollment['user_id'],
                        "contact_id": enrollment.get('contact_id', ''),
                        "type": "campaign_send",
                        "title": f"Send {card_label} to {contact_display}",
                        "description": f"Campaign '{campaign.get('name', '')}' step {current_step}: Send a {card_label} to {contact_display}.",
                        "due_date": now,
                        "priority": "high",
                        "completed": False,
                        "source": "campaign",
                        "campaign_id": enrollment['campaign_id'],
                        "pending_send_id": str(pending_result.inserted_id),
                        "channel": step.get('channel', 'sms'),
                        "created_at": now,
                    })
                    # Notification bell
                    await get_db().notifications.insert_one({
                        "user_id": enrollment['user_id'],
                        "type": "campaign_send",
                        "title": f"Campaign: {campaign.get('name', '')}",
                        "message": f"Time to send {card_label} to {contact_display}",
                        "contact_name": contact_display,
                        "contact_id": enrollment.get('contact_id', ''),
                        "campaign_id": enrollment['campaign_id'],
                        "pending_send_step": current_step,
                        "action_required": True,
                        "read": False,
                        "dismissed": False,
                        "created_at": now,
                    })
                    logger.info(f"Created task + notification: {card_label} for {contact_display}")
            else:
                message_content = step.get('message_template', step.get('message', ''))
                
                if delivery_mode == 'automated':
                    # Mock: Log the message that would be sent
                    logger.info(f"[MOCK] Sending campaign message to {enrollment['contact_phone']}: {message_content[:50]}...")
                else:
                    contact_display = enrollment.get('contact_name', 'contact')
                    channel = step.get('channel', 'sms')
                    pending_result = await get_db().campaign_pending_sends.insert_one({
                        "user_id": enrollment['user_id'],
                        "campaign_id": enrollment['campaign_id'],
                        "campaign_name": campaign.get('name', ''),
                        "contact_id": enrollment.get('contact_id', ''),
                        "contact_name": contact_display,
                        "contact_phone": enrollment.get('contact_phone', ''),
                        "step": current_step,
                        "action_type": "message",
                        "message": message_content,
                        "channel": channel,
                        "status": "pending",
                        "created_at": now,
                    })
                    # Create task on to-do list
                    await get_db().tasks.insert_one({
                        "user_id": enrollment['user_id'],
                        "contact_id": enrollment.get('contact_id', ''),
                        "type": "campaign_send",
                        "title": f"Send {channel.upper()} to {contact_display}",
                        "description": f"Campaign '{campaign.get('name', '')}' step {current_step}: {message_content[:200]}",
                        "due_date": now,
                        "priority": "high",
                        "completed": False,
                        "source": "campaign",
                        "campaign_id": enrollment['campaign_id'],
                        "pending_send_id": str(pending_result.inserted_id),
                        "channel": channel,
                        "created_at": now,
                    })
                    # Notification bell
                    await get_db().notifications.insert_one({
                        "user_id": enrollment['user_id'],
                        "type": "campaign_send",
                        "title": f"Campaign: {campaign.get('name', '')}",
                        "message": f"Time to send step {current_step} to {contact_display}",
                        "contact_name": contact_display,
                        "contact_id": enrollment.get('contact_id', ''),
                        "campaign_id": enrollment['campaign_id'],
                        "pending_send_step": current_step,
                        "action_required": True,
                        "read": False,
                        "dismissed": False,
                        "created_at": now,
                    })
                    logger.info(f"Created task + notification for {contact_display}")
            
            # Calculate next send time
            if current_step < len(sequences):
                next_step = sequences[current_step]
                next_send = calculate_next_send_date(next_step)
            else:
                next_send = None
            
            # Build log entry
            step_description = step.get('card_type', '') if action_type == 'send_card' else (step.get('message_template', '')[:100])
            
            # Update enrollment
            update_set = {
                "current_step": current_step + 1,
                "last_sent_at": now,
            }
            if next_send:
                update_set["next_send_at"] = next_send
            else:
                update_set["status"] = "completed"
                update_set["next_send_at"] = None
            
            await get_db().campaign_enrollments.update_one(
                {"_id": enrollment['_id']},
                {
                    "$set": update_set,
                    "$push": {"messages_sent": {
                        "step": current_step,
                        "action_type": action_type,
                        "sent_at": now,
                        "content": step_description,
                    }}
                }
            )
            
            processed += 1
            
        except Exception as e:
            logger.error(f"Error processing enrollment {enrollment['_id']}: {e}")
    
    return {
        "message": f"Scheduler triggered, processed {processed} messages",
        "processed": processed,
        "pending_found": len(pending)
    }

@router.post("/scheduler/check-date-triggers/{user_id}")
async def check_date_triggers(user_id: str):
    """Check for contacts with birthdays/anniversaries/sold dates today and auto-enroll in campaigns"""
    db = get_db()
    today = datetime.utcnow()
    today_month = today.month
    today_day = today.day
    
    # Get base filter for user's data
    base_filter = await get_data_filter(user_id)
    
    # Find date-based campaigns using both legacy 'type' field and new 'date_type' field
    date_type_configs = [
        {"date_type": "birthday", "contact_field": "birthday", "campaign_filter": {"$or": [{"type": "birthday"}, {"date_type": "birthday"}]}},
        {"date_type": "anniversary", "contact_field": "anniversary", "campaign_filter": {"$or": [{"type": "anniversary"}, {"date_type": "anniversary"}]}},
        {"date_type": "sold_date", "contact_field": "date_sold", "campaign_filter": {"$or": [{"type": "sold_date"}, {"date_type": "sold_date"}]}},
    ]
    
    enrolled_count = 0
    stats = {}
    
    for config in date_type_configs:
        campaigns = await db.campaigns.find({
            "$and": [
                {**config["campaign_filter"], "active": True},
                base_filter
            ]
        }).to_list(100)
        
        stats[f"{config['date_type']}_campaigns"] = len(campaigns)
        
        if not campaigns:
            continue
        
        contacts = await db.contacts.find({
            "$and": [
                base_filter,
                {config["contact_field"]: {"$exists": True, "$ne": None}}
            ]
        }).limit(500).to_list(500)
        
        for campaign in campaigns:
            for contact in contacts:
                date_val = contact.get(config["contact_field"])
                if date_val and isinstance(date_val, datetime):
                    if date_val.month == today_month and date_val.day == today_day:
                        existing = await db.campaign_enrollments.find_one({
                            "campaign_id": str(campaign['_id']),
                            "contact_id": str(contact['_id']),
                            "enrolled_at": {"$gte": today - timedelta(days=30)}
                        })
                        
                        if not existing:
                            enrollment = {
                                "user_id": user_id,
                                "campaign_id": str(campaign['_id']),
                                "campaign_name": campaign['name'],
                                "contact_id": str(contact['_id']),
                                "contact_name": f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip(),
                                "contact_phone": contact.get('phone', ''),
                                "current_step": 1,
                                "total_steps": len(campaign.get('sequences', [])),
                                "status": "active",
                                "enrolled_at": today,
                                "next_send_at": today,
                                "messages_sent": [],
                                "trigger_type": config["date_type"]
                            }
                            await db.campaign_enrollments.insert_one(enrollment)
                            enrolled_count += 1
                            logger.info(f"Auto-enrolled {enrollment['contact_name']} in {config['date_type']} campaign: {campaign['name']}")
    
    return {
        "message": "Date trigger check complete",
        "enrolled": enrolled_count,
        **stats
    }
