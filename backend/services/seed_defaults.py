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

# ==================== DEFAULT CAMPAIGNS (6) ====================
DEFAULT_CAMPAIGNS = [
    # Campaign 1: New Account Onboarding
    {
        "name": "New Account Onboarding",
        "type": "onboarding",
        "trigger_tag": "",
        "segment_tags": [],
        "active": True,
        "send_time": "10:00",
        "delivery_mode": "manual",
        "ai_enabled": False,
        "ownership_level": "user",
        "description": "Gets new users to 'live + shareable' in under a week. Auto-activates on signup.",
        "sequences": [
            {"step": 1, "action_type": "message", "channel": "email", "delay_days": 0, "delay_months": 0, "message_template": "Welcome to i'M On Social! Here's your 3-step quick start:\n\n1. Claim your card URL\n2. Add your logo + brand colors\n3. Add your socials + primary CTA\n\nTap here to get started: {settings_link}", "media_urls": [], "ai_generated": False, "step_context": "welcome + checklist", "card_type": ""},
            {"step": 2, "action_type": "message", "channel": "email", "delay_days": 1, "delay_months": 0, "message_template": "Your QR code is ready! Here are 3 ways to use it today:\n\n- Add to your email signature\n- Print for your desk/counter\n- Include on your business card\n\nDownload it here: {qr_link}", "media_urls": [], "ai_generated": False, "step_context": "QR code + share pack", "card_type": ""},
            {"step": 3, "action_type": "message", "channel": "email", "delay_days": 3, "delay_months": 0, "message_template": "Time to set up your review flow! Connect your Google, Facebook, or Yelp review link so customers can leave you a review with one tap.\n\nSet it up here: {review_setup_link}", "media_urls": [], "ai_generated": False, "step_context": "review flow setup", "card_type": ""},
            {"step": 4, "action_type": "message", "channel": "email", "delay_days": 5, "delay_months": 0, "message_template": "Your congrats card template is ready to customize! Next time you close a deal, send a branded congrats card with one tap — complete with review links and referral buttons.\n\nCustomize it here: {congrats_setup_link}", "media_urls": [], "ai_generated": False, "step_context": "congrats card setup", "card_type": ""},
            {"step": 5, "action_type": "message", "channel": "email", "delay_days": 7, "delay_months": 0, "message_template": "You're all set! Here are 3 ways to launch today:\n\n1. Post your digital card link to socials\n2. Text your card to 10 contacts\n3. Print your QR code\n\nYou've got this!", "media_urls": [], "ai_generated": False, "step_context": "launch prompt", "card_type": ""},
        ],
    },
    # Campaign 2: First 10 Reviews Sprint
    {
        "name": "First 10 Reviews Sprint",
        "type": "review_sprint",
        "trigger_tag": "",
        "segment_tags": [],
        "active": False,
        "send_time": "10:00",
        "delivery_mode": "manual",
        "ai_enabled": False,
        "ownership_level": "user",
        "description": "Quick sprint to get your first 10 reviews. Activate once you have contacts loaded.",
        "sequences": [
            {"step": 1, "action_type": "message", "channel": "sms", "delay_days": 0, "delay_months": 0, "message_template": "Hey {name}, if you've got 20 seconds, would you mind leaving a quick review? It really helps more than you know: {review_link} — appreciate you.", "media_urls": [], "ai_generated": False, "step_context": "initial review ask - warm, personal, short", "card_type": ""},
            {"step": 2, "action_type": "message", "channel": "sms", "delay_days": 2, "delay_months": 0, "message_template": "Hey {name}, just bumping this in case life got busy. A quick review would mean a lot: {review_link}. Thanks!", "media_urls": [], "ai_generated": False, "step_context": "follow-up to non-clickers - different wording, shorter", "card_type": ""},
            {"step": 3, "action_type": "message", "channel": "sms", "delay_days": 5, "delay_months": 0, "message_template": "Last one from me on this, {name} — no worries if it's not your thing. But if you've got a sec: {review_link}. Either way, appreciate you!", "media_urls": [], "ai_generated": False, "step_context": "final polite ping", "card_type": ""},
        ],
    },
    # Campaign 3: Ongoing Relationship Touches (5 touches/year)
    {
        "name": "Ongoing Relationship Touches",
        "type": "relationship",
        "trigger_tag": "",
        "segment_tags": [],
        "active": False,
        "send_time": "10:00",
        "delivery_mode": "manual",
        "ai_enabled": False,
        "ownership_level": "user",
        "description": "Stay remembered without being annoying. 5 touches/year per contact. Activate once contacts are loaded.",
        "sequences": [
            {"step": 1, "action_type": "message", "channel": "sms", "delay_days": 0, "delay_months": 0, "message_template": "Hey {name}, just checking in. How's everything going? Let me know if you need anything — I'm here.", "media_urls": [], "ai_generated": False, "step_context": "quarterly check-in #1", "card_type": ""},
            {"step": 2, "action_type": "message", "channel": "sms", "delay_days": 0, "delay_months": 3, "message_template": "Hey {name}, hope you're having a great season! Quick tip: [seasonal value relevant to your industry]. Let me know if I can help with anything.", "media_urls": [], "ai_generated": False, "step_context": "seasonal value ping", "card_type": ""},
            {"step": 3, "action_type": "message", "channel": "sms", "delay_days": 0, "delay_months": 6, "message_template": "Hey {name}, just checking in again. How's everything? If anything's come up, I'm always around.", "media_urls": [], "ai_generated": False, "step_context": "quarterly check-in #2", "card_type": ""},
            {"step": 4, "action_type": "message", "channel": "sms", "delay_days": 0, "delay_months": 9, "message_template": "Hey {name}, no agenda — just saw something that reminded me of you. Hope all is well! Reach out anytime.", "media_urls": [], "ai_generated": False, "step_context": "just because touch", "card_type": ""},
            {"step": 5, "action_type": "message", "channel": "sms", "delay_days": 0, "delay_months": 12, "message_template": "Hey {name}, can you believe it's been a year? Time flies. Grateful to know you — reach out if you ever need anything.", "media_urls": [], "ai_generated": False, "step_context": "annual milestone", "card_type": ""},
        ],
    },
    # Campaign 4: Post-Purchase / Post-Service Follow-up
    {
        "name": "Post-Purchase Follow-Up",
        "type": "sold_followup",
        "trigger_tag": "sold",
        "segment_tags": [],
        "active": True,
        "send_time": "10:00",
        "delivery_mode": "manual",
        "ai_enabled": False,
        "ownership_level": "user",
        "description": "Triggered when 'sold' tag is applied. Drives reviews, referrals, and repeat business.",
        "sequences": [
            {"step": 1, "action_type": "send_card", "card_type": "congrats", "channel": "sms", "delay_days": 0, "delay_months": 0, "message_template": "Congratulations, {name}! So excited for you. Here's a little something from us.", "media_urls": [], "ai_generated": False, "step_context": "same-day congrats card + thank you"},
            {"step": 2, "action_type": "message", "channel": "sms", "delay_days": 2, "delay_months": 0, "message_template": "Hey {name}, if you had a great experience, a quick review would mean the world: {review_link}. Appreciate you!", "media_urls": [], "ai_generated": False, "step_context": "review ask - only if engaged or no negative feedback", "card_type": ""},
            {"step": 3, "action_type": "message", "channel": "sms", "delay_days": 14, "delay_months": 0, "message_template": "Hey {name}, everything still going great? Let me know if anything comes up — I'm here for you.", "media_urls": [], "ai_generated": False, "step_context": "2-week check-in", "card_type": ""},
            {"step": 4, "action_type": "message", "channel": "sms", "delay_days": 30, "delay_months": 0, "message_template": "Hey {name}, know anyone who could use our help? Referrals mean more than you know. No pressure — just thought I'd ask!", "media_urls": [], "ai_generated": False, "step_context": "30-day soft referral ask", "card_type": ""},
            {"step": 5, "action_type": "message", "channel": "sms", "delay_days": 180, "delay_months": 0, "message_template": "Hey {name}! It's been about 6 months. Just wanted to check in and make sure everything's still great. Reach out anytime!", "media_urls": [], "ai_generated": False, "step_context": "6-month check-in + value tip", "card_type": ""},
        ],
    },
    # Campaign 5: Reputation Rescue
    {
        "name": "Reputation Rescue",
        "type": "reputation_rescue",
        "trigger_tag": "negative_feedback",
        "segment_tags": [],
        "active": True,
        "send_time": "09:00",
        "delivery_mode": "manual",
        "ai_enabled": False,
        "ownership_level": "user",
        "description": "Triggered by 1-3 star rating or negative feedback. Save the relationship, don't argue on the internet.",
        "sequences": [
            {"step": 1, "action_type": "message", "channel": "sms", "delay_days": 0, "delay_months": 0, "message_template": "Hey {name}, I saw your feedback and I'm sorry about your experience. I want to make this right. Can we chat? Call or text me anytime.", "media_urls": [], "ai_generated": False, "step_context": "immediate apology + offer to fix", "card_type": ""},
            {"step": 2, "action_type": "message", "channel": "sms", "delay_days": 1, "delay_months": 0, "message_template": "Hey {name}, just making sure you saw my last message. I really do want to fix this. Let me know the best way to reach you.", "media_urls": [], "ai_generated": False, "step_context": "day-1 follow-up if no response", "card_type": ""},
            {"step": 3, "action_type": "message", "channel": "sms", "delay_days": 7, "delay_months": 0, "message_template": "Hi {name}, I know things didn't go as expected. If you're open to it, I'd love a second chance. Either way, I appreciate your honesty.", "media_urls": [], "ai_generated": False, "step_context": "close the loop - second chance ask", "card_type": ""},
        ],
    },
    # Campaign 6: Social Growth Loop
    {
        "name": "Social Growth Loop",
        "type": "social_growth",
        "trigger_tag": "",
        "segment_tags": ["sold", "new_client"],
        "active": False,
        "send_time": "11:00",
        "delivery_mode": "manual",
        "ai_enabled": False,
        "ownership_level": "user",
        "description": "Turn happy customers into followers. Only sends to contacts who engaged (clicked/replied).",
        "sequences": [
            {"step": 1, "action_type": "message", "channel": "sms", "delay_days": 0, "delay_months": 0, "message_template": "Hey {name}! We post tips, behind-the-scenes, and customer shoutouts. Give us a follow if you're into it: {social_link}", "media_urls": [], "ai_generated": False, "step_context": "follow ask bundled with thank-you energy", "card_type": ""},
            {"step": 2, "action_type": "message", "channel": "sms", "delay_days": 7, "delay_months": 0, "message_template": "Hey {name}, here's a taste of what we post: [link to best recent post]. Follow along for more!", "media_urls": [], "ai_generated": False, "step_context": "show what you post + top links", "card_type": ""},
            {"step": 3, "action_type": "message", "channel": "sms", "delay_days": 30, "delay_months": 0, "message_template": "Hey {name}, we're doing something fun this month — stay tuned on our socials! {social_link}", "media_urls": [], "ai_generated": False, "step_context": "optional giveaway/series tease", "card_type": ""},
        ],
    },
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
        "trigger_type": "holiday",
        "enabled": True,
        "delivery_method": "sms",
        "message_template": "Happy Thanksgiving, {name}! Grateful for people like you. Enjoy the day!",
        "include_birthday_card": False,
        "holiday_id": "thanksgiving",
    },
    {
        "trigger_type": "holiday",
        "enabled": True,
        "delivery_method": "sms",
        "message_template": "Merry Christmas, {name}! Wishing you and yours a wonderful holiday season!",
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
    """Run seed_user_defaults for every existing user, and seed_store_defaults for every store."""
    db = get_db()
    total = {"users": 0, "sms_templates": 0, "email_templates": 0, "campaigns": 0, "date_triggers": 0, "review_response_templates": 0, "social_templates": 0, "stores": 0, "tags": 0, "lead_sources": 0}

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
