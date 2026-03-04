"""
Seed Defaults Service - provisions all default data when a new user/store is created.
Ensures every account is turnkey out of the box.
"""
from datetime import datetime, timezone
from routers.database import get_db
import logging

logger = logging.getLogger(__name__)

# ==================== SMS TEMPLATES ====================
DEFAULT_SMS_TEMPLATES = [
    {"name": "Greeting", "content": "Hi {name}! Thanks for reaching out. How can I help you today?", "category": "greeting", "is_default": True},
    {"name": "Follow Up", "content": "Hi {name}, I wanted to follow up on our conversation. Do you have any questions?", "category": "follow_up", "is_default": True},
    {"name": "Appointment", "content": "Hi {name}, I'd love to schedule a time to chat. What works best for you?", "category": "appointment", "is_default": True},
    {"name": "Thank You", "content": "Thank you so much for your time today, {name}! Please let me know if you need anything else.", "category": "thank_you", "is_default": True},
    {"name": "Review Request", "content": "Hi {name}! If you had a great experience, we'd really appreciate a review. Here's the link: ", "category": "review", "is_default": True},
    {"name": "Referral Request", "content": "Hi {name}! If you know anyone who could benefit from our services, I'd love an introduction. Referrals mean the world to us!", "category": "referral", "is_default": True},
    {"name": "Congratulations - Sold!", "content": "Congratulations on your new purchase, {name}! Thank you for trusting us. Please reach out if you have any questions!", "category": "sold", "is_default": True},
]

# ==================== EMAIL TEMPLATES ====================
DEFAULT_EMAIL_TEMPLATES = [
    {
        "name": "Welcome Email",
        "subject": "Welcome to {company_name}!",
        "html_content": '<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px"><h1 style="color:#333">Welcome, {name}!</h1><p style="color:#666;line-height:1.6">Thank you for connecting with us. We\'re excited to have you!</p><p style="color:#666;line-height:1.6">If you have any questions, don\'t hesitate to reach out.</p></div>',
        "category": "greeting",
        "is_default": True,
    },
    {
        "name": "Digital Business Card",
        "subject": "{sender_name}'s Digital Business Card",
        "html_content": '<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px"><h2 style="color:#333">Here\'s my digital business card</h2><p style="color:#666;line-height:1.6">Hi {name},</p><p style="color:#666;line-height:1.6">Here\'s my digital business card with all my contact information:</p><div style="text-align:center;margin:30px 0"><a href="{card_link}" style="background-color:#007AFF;color:white;padding:15px 30px;text-decoration:none;border-radius:8px;font-weight:bold">View My Card</a></div></div>',
        "category": "digital_card",
        "is_default": True,
    },
    {
        "name": "Review Request",
        "subject": "We'd love your feedback, {name}!",
        "html_content": '<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px"><h2 style="color:#333">How was your experience?</h2><p style="color:#666;line-height:1.6">Hi {name},</p><p style="color:#666;line-height:1.6">We hope you had a great experience! Your feedback means the world to us.</p><div style="text-align:center;margin:30px 0"><a href="{review_link}" style="background-color:#34C759;color:white;padding:15px 30px;text-decoration:none;border-radius:8px;font-weight:bold">Leave a Review</a></div></div>',
        "category": "review_request",
        "is_default": True,
    },
    {
        "name": "Follow Up",
        "subject": "Just checking in, {name}",
        "html_content": '<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px"><h2 style="color:#333">Just checking in!</h2><p style="color:#666;line-height:1.6">Hi {name},</p><p style="color:#666;line-height:1.6">I wanted to follow up and see how everything is going. Please let me know if there\'s anything I can help with!</p></div>',
        "category": "follow_up",
        "is_default": True,
    },
    {
        "name": "Referral Request",
        "subject": "Know someone who could use our help?",
        "html_content": '<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px"><h2 style="color:#333">Know someone who could use our help?</h2><p style="color:#666;line-height:1.6">Hi {name},</p><p style="color:#666;line-height:1.6">If you know anyone who could benefit from our services, we\'d love an introduction. Referrals mean the world to us!</p></div>',
        "category": "referral",
        "is_default": True,
    },
]

# ==================== DEFAULT CAMPAIGNS ====================
DEFAULT_CAMPAIGNS = [
    {
        "name": "New Client Welcome",
        "type": "custom",
        "trigger_tag": "new_client",
        "segment_tags": [],
        "active": True,
        "send_time": "10:00",
        "delivery_mode": "manual",
        "ai_enabled": False,
        "ownership_level": "user",
        "sequences": [
            {"step": 1, "action_type": "message", "channel": "sms", "delay_days": 0, "delay_months": 0, "message_template": "Welcome aboard, {name}! I'm so glad we connected. If you have any questions, I'm just a text away.", "media_urls": [], "ai_generated": False, "step_context": "welcome new client", "card_type": ""},
            {"step": 2, "action_type": "message", "channel": "email", "delay_days": 1, "delay_months": 0, "message_template": "Hi {name}, I wanted to send over my digital business card so you always have my info handy. Looking forward to working together!", "media_urls": [], "ai_generated": False, "step_context": "send digital card", "card_type": ""},
            {"step": 3, "action_type": "message", "channel": "sms", "delay_days": 7, "delay_months": 0, "message_template": "Hi {name}, just checking in! How's everything going? Let me know if you need anything.", "media_urls": [], "ai_generated": False, "step_context": "first week check-in", "card_type": ""},
        ],
    },
    {
        "name": "Sold Follow-Up",
        "type": "sold_followup",
        "trigger_tag": "sold",
        "segment_tags": [],
        "active": True,
        "send_time": "10:00",
        "delivery_mode": "manual",
        "ai_enabled": False,
        "ownership_level": "user",
        "sequences": [
            {"step": 1, "action_type": "send_card", "card_type": "congrats", "channel": "sms", "delay_days": 0, "delay_months": 0, "message_template": "Congratulations on your purchase, {name}! Here's a little something from us.", "media_urls": [], "ai_generated": False, "step_context": "send congrats card"},
            {"step": 2, "action_type": "message", "channel": "sms", "delay_days": 3, "delay_months": 0, "message_template": "Hi {name}, how's everything going with your new purchase? Let me know if you have any questions!", "media_urls": [], "ai_generated": False, "step_context": "post-sale check-in", "card_type": ""},
            {"step": 3, "action_type": "message", "channel": "sms", "delay_days": 14, "delay_months": 0, "message_template": "Hi {name}! If you've had a great experience, we'd really appreciate a quick review. It helps more than you know!", "media_urls": [], "ai_generated": False, "step_context": "ask for review", "card_type": ""},
            {"step": 4, "action_type": "message", "channel": "sms", "delay_days": 30, "delay_months": 0, "message_template": "Hi {name}, do you know anyone who might be looking for help? Referrals mean the world to us!", "media_urls": [], "ai_generated": False, "step_context": "ask for referral", "card_type": ""},
        ],
    },
    {
        "name": "90-Day Check-In",
        "type": "check_in",
        "trigger_tag": "",
        "segment_tags": ["sold"],
        "active": True,
        "send_time": "10:00",
        "delivery_mode": "manual",
        "ai_enabled": False,
        "ownership_level": "user",
        "sequences": [
            {"step": 1, "action_type": "message", "channel": "sms", "delay_days": 90, "delay_months": 0, "message_template": "Hi {name}! It's been a few months and I wanted to check in. How's everything going? I'm always here if you need anything.", "media_urls": [], "ai_generated": False, "step_context": "quarterly check-in", "card_type": ""},
        ],
    },
    {
        "name": "Annual Re-Engage",
        "type": "custom",
        "trigger_tag": "",
        "segment_tags": ["sold"],
        "active": True,
        "send_time": "10:00",
        "delivery_mode": "manual",
        "ai_enabled": False,
        "ownership_level": "user",
        "sequences": [
            {"step": 1, "action_type": "message", "channel": "sms", "delay_days": 0, "delay_months": 12, "message_template": "Hi {name}! Can you believe it's been a year? Time flies! I hope you're doing well. Let me know if there's anything I can help with.", "media_urls": [], "ai_generated": False, "step_context": "annual anniversary", "card_type": ""},
        ],
    },
    {
        "name": "Birthday Campaign",
        "type": "birthday",
        "trigger_tag": "",
        "segment_tags": [],
        "active": True,
        "send_time": "09:00",
        "delivery_mode": "manual",
        "ai_enabled": False,
        "ownership_level": "user",
        "sequences": [
            {"step": 1, "action_type": "send_card", "card_type": "birthday", "channel": "sms", "delay_days": 0, "delay_months": 0, "message_template": "Happy Birthday, {name}! Hope your day is as amazing as you are!", "media_urls": [], "ai_generated": False, "step_context": "send birthday card"},
            {"step": 2, "action_type": "message", "channel": "sms", "delay_days": 1, "delay_months": 0, "message_template": "Hope you had a wonderful birthday, {name}! Just wanted to say we appreciate you.", "media_urls": [], "ai_generated": False, "step_context": "day-after follow-up", "card_type": ""},
        ],
    },
    {
        "name": "Anniversary Campaign",
        "type": "anniversary",
        "trigger_tag": "",
        "segment_tags": [],
        "active": True,
        "send_time": "10:00",
        "delivery_mode": "manual",
        "ai_enabled": False,
        "ownership_level": "user",
        "sequences": [
            {"step": 1, "action_type": "message", "channel": "sms", "delay_days": 0, "delay_months": 0, "message_template": "Happy Anniversary, {name}! Wishing you and yours a wonderful celebration today.", "media_urls": [], "ai_generated": False, "step_context": "anniversary greeting", "card_type": ""},
            {"step": 2, "action_type": "message", "channel": "sms", "delay_days": 7, "delay_months": 0, "message_template": "Hi {name}! Hope you had a great anniversary celebration. Let me know if there's anything I can help with!", "media_urls": [], "ai_generated": False, "step_context": "post-anniversary check-in", "card_type": ""},
        ],
    },
    {
        "name": "Sold Date Anniversary",
        "type": "custom",
        "trigger_tag": "",
        "segment_tags": ["sold"],
        "active": True,
        "send_time": "10:00",
        "delivery_mode": "manual",
        "ai_enabled": False,
        "ownership_level": "user",
        "sequences": [
            {"step": 1, "action_type": "message", "channel": "sms", "delay_days": 0, "delay_months": 0, "message_template": "Hi {name}! It's the anniversary of when we started working together. Time flies! Hope everything is still going great.", "media_urls": [], "ai_generated": False, "step_context": "purchase anniversary", "card_type": ""},
            {"step": 2, "action_type": "message", "channel": "sms", "delay_days": 3, "delay_months": 0, "message_template": "By the way, {name} — if you know anyone who could use our help, I'd love an introduction. Referrals mean the world!", "media_urls": [], "ai_generated": False, "step_context": "referral ask after anniversary", "card_type": ""},
        ],
    },
]

# ==================== DEFAULT DATE TRIGGERS ====================
DEFAULT_DATE_TRIGGERS = [
    {
        "trigger_type": "birthday",
        "enabled": True,
        "delivery_method": "sms",
        "message_template": "Happy Birthday, {name}! Wishing you an amazing day!",
        "include_birthday_card": True,
    },
    {
        "trigger_type": "anniversary",
        "enabled": True,
        "delivery_method": "sms",
        "message_template": "Happy Anniversary, {name}! Celebrating this special day with you.",
        "include_birthday_card": False,
    },
    {
        "trigger_type": "sold_date",
        "enabled": True,
        "delivery_method": "sms",
        "message_template": "Hi {name}! It's the anniversary of when we first connected. Hope you're doing great!",
        "include_birthday_card": False,
    },
    {
        "trigger_type": "holiday",
        "enabled": True,
        "delivery_method": "sms",
        "message_template": "Happy Holidays, {name}! Wishing you and your family a wonderful season!",
        "include_birthday_card": False,
        "holiday_id": "thanksgiving",
    },
    {
        "trigger_type": "holiday",
        "enabled": True,
        "delivery_method": "sms",
        "message_template": "Merry Christmas, {name}! Wishing you a joyful holiday season!",
        "include_birthday_card": False,
        "holiday_id": "christmas",
    },
    {
        "trigger_type": "holiday",
        "enabled": True,
        "delivery_method": "sms",
        "message_template": "Happy New Year, {name}! Wishing you an incredible year ahead!",
        "include_birthday_card": False,
        "holiday_id": "new_years",
    },
]

# ==================== DEFAULT TAGS ====================
DEFAULT_TAGS = [
    {"name": "new_client", "color": "#34C759", "description": "New client"},
    {"name": "sold", "color": "#007AFF", "description": "Closed deal"},
    {"name": "hot_lead", "color": "#FF3B30", "description": "High priority lead"},
    {"name": "cold_lead", "color": "#8E8E93", "description": "Low priority lead"},
    {"name": "referral", "color": "#FF9500", "description": "Referred by someone"},
    {"name": "VIP", "color": "#C9A962", "description": "VIP customer"},
    {"name": "past_client", "color": "#AF52DE", "description": "Former client"},
    {"name": "follow_up", "color": "#5AC8FA", "description": "Needs follow-up"},
]

# ==================== DEFAULT LEAD SOURCES ====================
DEFAULT_LEAD_SOURCES = [
    {"name": "Website", "type": "inbound", "color": "#007AFF"},
    {"name": "Referral", "type": "inbound", "color": "#34C759"},
    {"name": "Walk-In", "type": "inbound", "color": "#FF9500"},
    {"name": "Social Media", "type": "inbound", "color": "#AF52DE"},
    {"name": "Phone Call", "type": "inbound", "color": "#5AC8FA"},
    {"name": "Event", "type": "inbound", "color": "#FF2D55"},
    {"name": "Email", "type": "inbound", "color": "#FFD60A"},
    {"name": "Personal Network", "type": "outbound", "color": "#C9A962"},
]


async def seed_user_defaults(user_id: str):
    """Provision all default data for a new user. Safe to call multiple times (idempotent)."""
    db = get_db()
    now = datetime.now(timezone.utc)
    seeded = {}

    # 1. SMS Templates
    existing_sms = await db.templates.count_documents({"user_id": user_id})
    if existing_sms == 0:
        docs = [{"user_id": user_id, **t, "usage_count": 0, "created_at": now, "updated_at": now} for t in DEFAULT_SMS_TEMPLATES]
        await db.templates.insert_many(docs)
        seeded["sms_templates"] = len(docs)
    else:
        seeded["sms_templates"] = 0

    # 2. Email Templates
    existing_email = await db.email_templates.count_documents({"user_id": user_id})
    if existing_email == 0:
        docs = [{"user_id": user_id, **t, "created_at": now} for t in DEFAULT_EMAIL_TEMPLATES]
        await db.email_templates.insert_many(docs)
        seeded["email_templates"] = len(docs)
    else:
        seeded["email_templates"] = 0

    # 3. Campaigns
    existing_camps = await db.campaigns.count_documents({"user_id": user_id})
    if existing_camps == 0:
        docs = [{"user_id": user_id, **c, "created_at": now} for c in DEFAULT_CAMPAIGNS]
        await db.campaigns.insert_many(docs)
        seeded["campaigns"] = len(docs)
    else:
        seeded["campaigns"] = 0

    # 4. Date Triggers
    existing_triggers = await db.date_trigger_configs.count_documents({"user_id": user_id})
    if existing_triggers == 0:
        docs = [{"user_id": user_id, **t, "created_at": now} for t in DEFAULT_DATE_TRIGGERS]
        await db.date_trigger_configs.insert_many(docs)
        seeded["date_triggers"] = len(docs)
    else:
        seeded["date_triggers"] = 0

    logger.info(f"Seeded defaults for user {user_id}: {seeded}")
    return seeded


async def seed_store_defaults(store_id: str, organization_id: str = ""):
    """Provision default data at the store/org level. Safe to call multiple times."""
    db = get_db()
    now = datetime.now(timezone.utc)
    seeded = {}

    # 1. Tags (store-level)
    existing_tags = await db.tags.count_documents({"store_id": store_id})
    if existing_tags == 0:
        docs = [{"store_id": store_id, "organization_id": organization_id, **t, "is_default": True, "created_at": now} for t in DEFAULT_TAGS]
        await db.tags.insert_many(docs)
        seeded["tags"] = len(docs)
    else:
        seeded["tags"] = 0

    # 2. Lead Sources (store-level)
    existing_sources = await db.lead_sources.count_documents({"store_id": store_id})
    if existing_sources == 0:
        docs = [{"store_id": store_id, "organization_id": organization_id, **s, "is_default": True, "active": True, "created_at": now} for s in DEFAULT_LEAD_SOURCES]
        await db.lead_sources.insert_many(docs)
        seeded["lead_sources"] = len(docs)
    else:
        seeded["lead_sources"] = 0

    logger.info(f"Seeded store defaults for {store_id}: {seeded}")
    return seeded


async def backfill_all_users():
    """Run seed_user_defaults for every existing user, and seed_store_defaults for every store."""
    db = get_db()
    total = {"users": 0, "sms_templates": 0, "email_templates": 0, "campaigns": 0, "date_triggers": 0, "stores": 0, "tags": 0, "lead_sources": 0}

    # Seed users
    users = await db.users.find({"is_active": {"$ne": False}}, {"_id": 1}).to_list(5000)
    for user in users:
        uid = str(user["_id"])
        result = await seed_user_defaults(uid)
        total["users"] += 1
        for k, v in result.items():
            total[k] += v

    # Seed stores
    stores = await db.stores.find({}, {"_id": 1, "organization_id": 1}).to_list(5000)
    for store in stores:
        sid = str(store["_id"])
        org_id = store.get("organization_id", "")
        result = await seed_store_defaults(sid, org_id)
        total["stores"] += 1
        for k, v in result.items():
            total[k] += v

    return total
