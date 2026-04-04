"""
Seed Defaults Service - provisions all default data when a new user/store is created.
Ensures every account is turnkey out of the box.

Campaign philosophy: auto-create everything, but only activate customer-facing
campaigns once contacts exist. Onboarding campaigns are always active.
"""
from datetime import datetime, timezone
from routers.database import get_db
import logging

logger = logging.getLogger(__name__)

# ==================== SMS TEMPLATES (12) ====================
DEFAULT_SMS_TEMPLATES = [
    {"name": "Welcome", "content": "Hey {name}! Thanks for connecting. I just set up my digital card — tap here to save my info: {card_link}", "category": "greeting", "is_default": True},
    {"name": "Add Socials Nudge", "content": "Hey {name}, quick heads up — follow us for tips, deals, and behind-the-scenes content: {social_link}", "category": "social", "is_default": True},
    {"name": "Review Ask", "content": "Hey {name}, if you've got 20 seconds, would you mind leaving a quick review? It really helps: {review_link} — appreciate you.", "category": "review", "is_default": True},
    {"name": "Review Follow-Up", "content": "Hey {name}, just bumping this in case it got buried. If you had a good experience, a quick review means the world: {review_link}", "category": "review", "is_default": True},
    {"name": "Referral Ask", "content": "Hey {name}, know anyone who could use our help? I'd love an introduction — referrals mean more than you know. Thanks!", "category": "referral", "is_default": True},
    {"name": "Check-In", "content": "Hey {name}, just checking in. How's everything going? Let me know if you need anything — I'm here.", "category": "follow_up", "is_default": True},
    {"name": "Birthday", "content": "Happy Birthday, {name}! Hope today's a good one. If you need anything, I'm here.", "category": "birthday", "is_default": True},
    {"name": "Anniversary", "content": "Happy Anniversary, {name}! Time flies. Grateful to know you — reach out if you ever need anything.", "category": "anniversary", "is_default": True},
    {"name": "Congrats / Sold", "content": "Congratulations, {name}! So excited for you. Truly appreciate your trust — let me know if you need anything at all.", "category": "sold", "is_default": True},
    {"name": "Reactivation", "content": "Hey {name}, it's been a while! Just wanted to say hi and see how you're doing. Would love to reconnect.", "category": "reactivation", "is_default": True},
    {"name": "Winback After Feedback", "content": "Hey {name}, I saw your feedback and I want to make things right. Can we chat? I'd love a chance to fix this.", "category": "winback", "is_default": True},
    {"name": "Just Because", "content": "Hey {name}, no agenda — just saw something that reminded me of you. Hope all is well!", "category": "just_because", "is_default": True},
]

# ==================== EMAIL TEMPLATES (8) ====================
DEFAULT_EMAIL_TEMPLATES = [
    {
        "name": "Welcome + Card Setup",
        "subject": "Welcome to {company_name} — here's your digital card!",
        "html_content": '<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px"><h1 style="color:#333">Welcome, {name}!</h1><p style="color:#666;line-height:1.6">Thanks for connecting with us. Your digital business card is ready — share it with anyone, anytime.</p><div style="text-align:center;margin:30px 0"><a href="{card_link}" style="background-color:#007AFF;color:white;padding:15px 30px;text-decoration:none;border-radius:8px;font-weight:bold">View My Card</a></div><p style="color:#666;line-height:1.6">Save it, share it, or add it to your contacts. We\'re here if you need anything!</p></div>',
        "category": "greeting",
        "is_default": True,
    },
    {
        "name": "Digital Business Card",
        "subject": "{sender_name}'s Digital Business Card",
        "html_content": '<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px"><h2 style="color:#333">Here\'s my digital business card</h2><p style="color:#666;line-height:1.6">Hi {name},</p><p style="color:#666;line-height:1.6">Tap below to save my contact info, see my socials, and leave a review.</p><div style="text-align:center;margin:30px 0"><a href="{card_link}" style="background-color:#007AFF;color:white;padding:15px 30px;text-decoration:none;border-radius:8px;font-weight:bold">View My Card</a></div></div>',
        "category": "digital_card",
        "is_default": True,
    },
    {
        "name": "Review Request",
        "subject": "Quick favor, {name}?",
        "html_content": '<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px"><h2 style="color:#333">How was your experience?</h2><p style="color:#666;line-height:1.6">Hi {name},</p><p style="color:#666;line-height:1.6">If you\'ve got 20 seconds, a quick review would mean the world. It helps more than you know.</p><div style="text-align:center;margin:30px 0"><a href="{review_link}" style="background-color:#34C759;color:white;padding:15px 30px;text-decoration:none;border-radius:8px;font-weight:bold">Leave a Review</a></div><p style="color:#888;font-size:13px">No worries if not — we appreciate you either way.</p></div>',
        "category": "review_request",
        "is_default": True,
    },
    {
        "name": "Follow-Up / Check-In",
        "subject": "Just checking in, {name}",
        "html_content": '<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px"><h2 style="color:#333">Just checking in!</h2><p style="color:#666;line-height:1.6">Hi {name},</p><p style="color:#666;line-height:1.6">No agenda — just wanted to see how everything\'s going. If there\'s anything I can help with, I\'m just a reply away.</p></div>',
        "category": "follow_up",
        "is_default": True,
    },
    {
        "name": "Referral Request",
        "subject": "Know someone who could use our help, {name}?",
        "html_content": '<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px"><h2 style="color:#333">Referrals mean the world</h2><p style="color:#666;line-height:1.6">Hi {name},</p><p style="color:#666;line-height:1.6">If you know anyone who could benefit from what we do, we\'d love an introduction. A quick text or forwarding this email is all it takes.</p><div style="text-align:center;margin:30px 0"><a href="{card_link}" style="background-color:#FF9500;color:white;padding:15px 30px;text-decoration:none;border-radius:8px;font-weight:bold">Share My Card</a></div></div>',
        "category": "referral",
        "is_default": True,
    },
    {
        "name": "Congrats / Purchase",
        "subject": "Congrats, {name}!",
        "html_content": '<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px"><h1 style="color:#333">Congratulations!</h1><p style="color:#666;line-height:1.6">Hi {name},</p><p style="color:#666;line-height:1.6">So excited for you! Thank you for trusting us. If you need anything at all, don\'t hesitate to reach out.</p><div style="text-align:center;margin:30px 0"><a href="{review_link}" style="background-color:#C9A962;color:white;padding:15px 30px;text-decoration:none;border-radius:8px;font-weight:bold">Leave a Review</a></div></div>',
        "category": "sold",
        "is_default": True,
    },
    {
        "name": "Reputation Rescue",
        "subject": "I want to make this right, {name}",
        "html_content": '<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px"><h2 style="color:#333">I want to make this right</h2><p style="color:#666;line-height:1.6">Hi {name},</p><p style="color:#666;line-height:1.6">I saw your feedback and I\'m sorry about your experience. I\'d really love the chance to fix this — can we chat?</p><p style="color:#666;line-height:1.6">Feel free to reply to this email or give me a call at any time.</p></div>',
        "category": "winback",
        "is_default": True,
    },
    {
        "name": "Reactivation",
        "subject": "It's been a while, {name}!",
        "html_content": '<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px"><h2 style="color:#333">Long time no see!</h2><p style="color:#666;line-height:1.6">Hi {name},</p><p style="color:#666;line-height:1.6">Just wanted to reach out and say hi. It\'s been a while and I\'d love to reconnect. If there\'s anything I can help with, I\'m here.</p></div>',
        "category": "reactivation",
        "is_default": True,
    },
]

# ==================== REVIEW RESPONSE TEMPLATES (3) ====================
DEFAULT_REVIEW_RESPONSE_TEMPLATES = [
    {
        "name": "5-Star Response",
        "rating_range": "5",
        "content": "Thank you so much, {name}! This really made our day. We loved working with you and can't wait to do it again. If you ever need anything, don't hesitate to reach out!",
        "is_default": True,
    },
    {
        "name": "3-4 Star Response",
        "rating_range": "3-4",
        "content": "Thank you for the feedback, {name}. We appreciate your honesty — it helps us get better. If there's anything specific we can improve, we'd love to hear more. You can reach me directly anytime.",
        "is_default": True,
    },
    {
        "name": "1-2 Star Response",
        "rating_range": "1-2",
        "content": "I'm sorry about your experience, {name}. This isn't the standard we hold ourselves to. I'd really like to make this right — can we connect? Please reach out directly and I'll handle it personally.",
        "is_default": True,
    },
]

# ==================== SOCIAL CONTENT STARTERS (5) ====================
DEFAULT_SOCIAL_TEMPLATES = [
    {
        "name": "Intro Post",
        "category": "intro",
        "content": "New here? Here's what we do: [brief value prop]. Whether you need [service 1], [service 2], or just some solid advice — we've got you. Drop a comment or DM me anytime!",
        "is_default": True,
    },
    {
        "name": "Value Post",
        "category": "value",
        "content": "Quick tip: [insert helpful advice relevant to your industry]. Most people don't know this, but it can save you [time/money/hassle]. You're welcome. Need more tips? Follow along.",
        "is_default": True,
    },
    {
        "name": "Proof Post",
        "category": "proof",
        "content": "Another happy customer! [Name] came to us needing [problem] and left with [result]. Stories like this are why we do what we do. Thank you for trusting us!",
        "is_default": True,
    },
    {
        "name": "Community Post",
        "category": "community",
        "content": "Shoutout to [local business/event]! If you haven't checked them out yet, you're missing out. Supporting local is how we all win.",
        "is_default": True,
    },
    {
        "name": "Offer Post",
        "category": "offer",
        "content": "For a limited time: [offer details]. No gimmicks, no fine print. DM me or tap the link in my bio to get started. First come, first served!",
        "is_default": True,
    },
]

# ==================== DEFAULT CAMPAIGNS (6 + Five-Year) ====================
# These are Forest Ward's recommended turnkey campaigns — seeded for every new account.
# Each campaign has a matching tag (seeded separately in DEFAULT_TAGS below).

DEFAULT_CAMPAIGNS = [

    # Campaign 1: Working — Active Shopper
    {
        "name": "Working",
        "type": "nurture",
        "trigger_tag": "Working",
        "active": True,
        "delivery_mode": "manual",
        "ai_enabled": False,
        "description": "Keep the conversation alive and move toward a purchase. Trigger: Working tag.",
        "scope": "personal",
        "sequences": [
            {"step": 1, "delay_days": 0, "delay_minutes": 0, "channel": "sms", "message_template": "Hey {{name}}, this is {{salesperson_name}}. Thanks again for chatting with me today. If you need anything while you're looking things over just shoot me a message. Happy to help."},
            {"step": 2, "delay_days": 1, "channel": "sms", "message_template": "Just checking in to see if you had any questions after looking things over. I can also send more photos or videos if that helps."},
            {"step": 3, "delay_days": 3, "channel": "sms", "message_template": "Quick question for you. Are you still considering this or did you end up going another direction?"},
            {"step": 4, "delay_days": 7, "channel": "sms", "message_template": "I didn't want to lose track of you. If you're still in the market I'd be happy to help whenever you're ready."},
        ],
    },

    # Campaign 2: Sold — Year 1 Relationship
    {
        "name": "Sold",
        "type": "sold_followup",
        "trigger_tag": "Sold",
        "active": True,
        "delivery_mode": "manual",
        "ai_enabled": False,
        "description": "Reviews, referrals, service retention and relationship building. Trigger: Sold tag.",
        "scope": "personal",
        "sequences": [
            {"step": 1, "delay_days": 0, "delay_minutes": 0,  "channel": "sms", "message_template": "Congratulations again {{name}}. It was great working with you today. Let me know if you need anything at all as you get used to your new {{vehicle}}."},
            {"step": 2, "delay_days": 0, "delay_minutes": 15, "channel": "sms", "message_template": "Here's my digital card so you always have my contact info handy. If you ever need anything just text me here. {{card_link}}"},
            {"step": 3, "delay_days": 0, "delay_minutes": 30, "channel": "sms", "message_template": "One quick favor. Reviews really help customers know who to work with. If you wouldn't mind leaving a quick one I'd really appreciate it. {{review_link}}"},
            {"step": 4, "delay_days": 7,  "channel": "sms", "message_template": "Just checking in to see how everything is going with the {{vehicle}} so far."},
            {"step": 5, "delay_days": 21, "channel": "sms", "message_template": "Random question. Do you know anyone else looking for a vehicle right now? I'd be happy to help them the same way."},
            {"step": 6, "delay_days": 75, "channel": "sms", "message_template": "Your first service will probably be coming up soon. If you'd like I can help get that scheduled for you."},
            {"step": 7, "delay_days": 0, "delay_months": 6,  "channel": "sms", "message_template": "Hope you're still loving the {{vehicle}}. If you ever need anything just reach out."},
            {"step": 8, "delay_days": 0, "delay_months": 12, "channel": "sms", "message_template": "Hard to believe it's already been a year since you got your {{vehicle}}. Hope you're still loving it. If you ever need anything just reach out."},
        ],
    },

    # Campaign 3: Met — Networking / Events
    {
        "name": "Met",
        "type": "nurture",
        "trigger_tag": "Met",
        "active": True,
        "delivery_mode": "manual",
        "ai_enabled": False,
        "description": "Follow up after meeting someone at an event or networking. Trigger: Met tag.",
        "scope": "personal",
        "sequences": [
            {"step": 1, "delay_days": 0, "channel": "sms", "message_template": "Great meeting you today {{name}}. Always nice connecting with good people. Let's stay in touch."},
            {"step": 2, "delay_days": 2,  "channel": "sms", "message_template": "Just wanted to follow up after we met. If there's anything I can ever help with feel free to reach out."},
            {"step": 3, "delay_days": 30, "channel": "sms", "message_template": "Random check in. Hope everything is going well on your end."},
        ],
    },

    # Campaign 4: Birthday
    {
        "name": "Birthday",
        "type": "birthday",
        "trigger_tag": "Birthday",
        "active": True,
        "delivery_mode": "manual",
        "ai_enabled": False,
        "description": "Birthday message. Trigger: Birthday date field.",
        "scope": "personal",
        "sequences": [
            {"step": 1, "delay_days": 0, "channel": "sms", "message_template": "Happy Birthday {{name}}. Hope you have an awesome day."},
        ],
    },

    # Campaign 5: Lost Contact — Re-Engagement
    {
        "name": "Lost Contact",
        "type": "re_engagement",
        "trigger_tag": "Lost Contact",
        "active": True,
        "delivery_mode": "manual",
        "ai_enabled": False,
        "description": "Re-engage contacts after 60–90 days of silence. Trigger: Lost Contact tag.",
        "scope": "personal",
        "sequences": [
            {"step": 1, "delay_days": 0, "channel": "sms", "message_template": "Hey {{name}}, just wanted to check in. If you're still looking or need anything at all I'd be happy to help."},
        ],
    },

    # Campaign 6: Five-Year Relationship (Year 2–5)
    # Designed to run alongside the Sold campaign — picks up after Year 1
    {
        "name": "Five-Year Relationship",
        "type": "long_term",
        "trigger_tag": "Sold",
        "active": True,
        "delivery_mode": "manual",
        "ai_enabled": False,
        "description": "Long-term relationship building, referrals, repeat sales. Years 2–5 after purchase.",
        "scope": "personal",
        "sequences": [
            # Year 2
            {"step": 1,  "delay_months": 18, "channel": "sms", "message_template": "Random check in. How has the {{vehicle}} been treating you?"},
            {"step": 2,  "delay_months": 24, "channel": "sms", "message_template": "It's been two years since you got your {{vehicle}}. If you ever want to see what trade value looks like I'd be happy to run the numbers."},
            {"step": 3,  "delay_months": 24, "channel": "sms", "message_template": "Just wanted to say Happy Holidays {{name}}. Appreciate you being one of my customers."},
            # Year 3
            {"step": 4,  "delay_months": 30, "channel": "sms", "message_template": "Quick question. Are you still loving the {{vehicle}} or starting to think about something different?"},
            {"step": 5,  "delay_months": 36, "channel": "sms", "message_template": "Three years already since you picked up your {{vehicle}}. If you ever want to explore upgrading I'd be happy to help."},
            {"step": 6,  "delay_months": 38, "channel": "sms", "message_template": "By the way if you ever have a friend or family member looking for a vehicle feel free to send them my way. I'll take great care of them."},
            # Year 4
            {"step": 7,  "delay_months": 48, "channel": "sms", "message_template": "Just realized it's been four years since you got your {{vehicle}}. Time flies. Hope everything has been great with it."},
            {"step": 8,  "delay_months": 50, "channel": "sms", "message_template": "Haven't talked in a while so I figured I'd check in and say hello."},
            # Year 5
            {"step": 9,  "delay_months": 54, "channel": "sms", "message_template": "Random question. Are you planning on keeping the {{vehicle}} long term or thinking about replacing it sometime soon?"},
            {"step": 10, "delay_months": 60, "channel": "sms", "message_template": "Hard to believe it's been five years since you got your {{vehicle}}. If you'd ever like to look at upgrading or see what trade value looks like I'd be happy to help."},
        ],
    },

    # Legacy Onboarding — kept for backward compat but deactivated
    {
        "name": "New Account Onboarding",
        "type": "onboarding",
        "trigger_tag": "",
        "active": False,
        "delivery_mode": "manual",
        "ai_enabled": False,
        "description": "Legacy onboarding flow. Replaced by the new turnkey campaigns above.",
        "scope": "personal",
        "sequences": [
            {"step": 1, "action_type": "message", "channel": "email", "delay_days": 0, "message_template": "Welcome! Your first step: set up your digital card at {settings_link}"},
        ],
    },
]

# ==================== DEFAULT TAGS (5 core + 5 optional) ====================
# These are seeded at the USER level for every new account.
# Admins can promote them to account/org scope via the Tags settings.
DEFAULT_TAGS = [
    {"name": "Working",      "color": "#FF9500", "icon": "hammer",        "scope": "personal", "description": "Active shopper — currently working a deal"},
    {"name": "Sold",         "color": "#34C759", "icon": "checkmark",     "scope": "personal", "description": "Purchase completed — kick off the Sold campaign"},
    {"name": "Met",          "color": "#007AFF", "icon": "people",        "scope": "personal", "description": "Met at an event or networking — new connection"},
    {"name": "Birthday",     "color": "#FF2D55", "icon": "gift",          "scope": "personal", "description": "Birthday trigger — send annual birthday message"},
    {"name": "Lost Contact", "color": "#8E8E93", "icon": "cloud",         "scope": "personal", "description": "No engagement for 60–90 days — re-engagement campaign"},
    # Optional (created but inactive)
    {"name": "Be Back",      "color": "#5856D6", "icon": "return-down-back", "scope": "personal", "description": "Will return — follow up in a few days"},
    {"name": "Price Quote",  "color": "#FF9500", "icon": "pricetag",      "scope": "personal", "description": "Received a price quote — nurture toward decision"},
    {"name": "Referral",     "color": "#C9A962", "icon": "share",         "scope": "personal", "description": "Referred by another customer"},
    {"name": "Service",      "color": "#00BCD4", "icon": "build",         "scope": "personal", "description": "Needs service or follow-up"},
    {"name": "Trade",        "color": "#FF6B00", "icon": "swap-horizontal", "scope": "personal", "description": "Interested in trading in their vehicle"},
]

# ==================== DEFAULT DATE TRIGGERS (6) ====================
DEFAULT_DATE_TRIGGERS = [
    {
        "trigger_type": "birthday",
        "enabled": True,
        "delivery_method": "sms",
        "message_template": "Happy Birthday, {name}! Hope today's a good one. If you need anything, I'm here.",
        "include_birthday_card": True,
    },
    {
        "trigger_type": "anniversary",
        "enabled": True,
        "delivery_method": "sms",
        "message_template": "Happy Anniversary, {name}! Time flies. Grateful to know you — reach out if you ever need anything.",
        "include_birthday_card": False,
    },
    {
        "trigger_type": "sold_date",
        "enabled": True,
        "delivery_method": "sms",
        "message_template": "Hey {name}, it's the anniversary of when we started working together. Time flies! Hope everything's still great.",
        "include_birthday_card": False,
    },
    {
        "trigger_type": "holiday_thanksgiving",
        "enabled": True,
        "delivery_method": "sms",
        "message_template": "Happy Thanksgiving, {name}! Grateful for people like you. Enjoy the day!",
        "include_birthday_card": False,
        "holiday_id": "thanksgiving",
    },
    {
        "trigger_type": "holiday_christmas",
        "enabled": True,
        "delivery_method": "sms",
        "message_template": "Merry Christmas, {name}! Wishing you and yours a wonderful holiday season!",
        "include_birthday_card": False,
        "holiday_id": "christmas",
    },
    {
        "trigger_type": "holiday_new_years",
        "enabled": True,
        "delivery_method": "sms",
        "message_template": "Happy New Year, {name}! Wishing you an incredible year ahead!",
        "include_birthday_card": False,
        "holiday_id": "new_years",
    },
]

# ==================== DEFAULT TAGS (8) ====================
DEFAULT_TAGS = [
    {"name": "new_client", "color": "#34C759", "description": "New client"},
    {"name": "sold", "color": "#007AFF", "description": "Closed deal"},
    {"name": "hot_lead", "color": "#FF3B30", "description": "High priority lead"},
    {"name": "cold_lead", "color": "#8E8E93", "description": "Low priority lead"},
    {"name": "referral", "color": "#FF9500", "description": "Referred by someone"},
    {"name": "VIP", "color": "#C9A962", "description": "VIP customer"},
    {"name": "past_client", "color": "#AF52DE", "description": "Former client"},
    {"name": "negative_feedback", "color": "#FF2D55", "description": "Left negative feedback"},
]

# ==================== DEFAULT LEAD SOURCES (8) ====================
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

    # 3. Campaigns — deduplicate by name+type per user
    existing_camp_names = set()
    existing_camps_cursor = db.campaigns.find({"user_id": user_id}, {"name": 1, "type": 1})
    async for c in existing_camps_cursor:
        existing_camp_names.add((c.get("name", ""), c.get("type", "")))

    new_campaigns = [c for c in DEFAULT_CAMPAIGNS if (c["name"], c["type"]) not in existing_camp_names]
    if new_campaigns:
        docs = [{"user_id": user_id, **c, "created_at": now} for c in new_campaigns]
        await db.campaigns.insert_many(docs)
        seeded["campaigns"] = len(docs)
    else:
        seeded["campaigns"] = 0

    # 3b. Default Tags — seed the 5 core tags if user has none yet
    existing_tag_count = await db.tags.count_documents({"user_id": user_id})
    if existing_tag_count == 0:
        tag_docs = [{
            "user_id": user_id,
            "name": t["name"],
            "color": t["color"],
            "icon": t.get("icon", "pricetag"),
            "scope": t.get("scope", "personal"),
            "description": t.get("description", ""),
            "status": "approved",
            "contact_count": 0,
            "created_at": now,
        } for t in DEFAULT_TAGS]
        await db.tags.insert_many(tag_docs)
        seeded["tags"] = len(tag_docs)
    else:
        seeded["tags"] = 0

    # 4. Date Triggers
    existing_triggers = await db.date_trigger_configs.count_documents({"user_id": user_id})
    if existing_triggers == 0:
        docs = [{"user_id": user_id, **t, "created_at": now} for t in DEFAULT_DATE_TRIGGERS]
        await db.date_trigger_configs.insert_many(docs)
        seeded["date_triggers"] = len(docs)
    else:
        seeded["date_triggers"] = 0

    # 5. Review Response Templates
    existing_review = await db.review_response_templates.count_documents({"user_id": user_id})
    if existing_review == 0:
        docs = [{"user_id": user_id, **t, "created_at": now} for t in DEFAULT_REVIEW_RESPONSE_TEMPLATES]
        await db.review_response_templates.insert_many(docs)
        seeded["review_response_templates"] = len(docs)
    else:
        seeded["review_response_templates"] = 0

    # 6. Social Content Templates
    existing_social = await db.social_templates.count_documents({"user_id": user_id})
    if existing_social == 0:
        docs = [{"user_id": user_id, **t, "created_at": now} for t in DEFAULT_SOCIAL_TEMPLATES]
        await db.social_templates.insert_many(docs)
        seeded["social_templates"] = len(docs)
    else:
        seeded["social_templates"] = 0

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
    """Run seed_user_defaults for every existing user, and seed_store_defaults for every store.
    Includes per-user error handling so one failure doesn't stop the entire backfill."""
    db = get_db()
    total = {"users": 0, "sms_templates": 0, "email_templates": 0, "campaigns": 0, "date_triggers": 0, "review_response_templates": 0, "social_templates": 0, "stores": 0, "tags": 0, "lead_sources": 0, "errors": 0}

    # Seed users
    users = await db.users.find({"is_active": {"$ne": False}}, {"_id": 1}).to_list(5000)
    for user in users:
        try:
            uid = str(user["_id"])
            result = await seed_user_defaults(uid)
            total["users"] += 1
            for k, v in result.items():
                if k in total:
                    total[k] += v
        except Exception as e:
            total["errors"] += 1
            logger.error(f"Backfill error for user {user.get('_id')}: {e}")

    # Seed stores
    stores = await db.stores.find({}, {"_id": 1, "organization_id": 1}).to_list(5000)
    for store in stores:
        try:
            sid = str(store["_id"])
            org_id = str(store.get("organization_id", ""))
            result = await seed_store_defaults(sid, org_id)
            total["stores"] += 1
            for k, v in result.items():
                if k in total:
                    total[k] += v
        except Exception as e:
            total["errors"] += 1
            logger.error(f"Backfill error for store {store.get('_id')}: {e}")

    return total
