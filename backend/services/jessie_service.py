"""
Jessi AI Assistant Service — v2.0
Fast, deeply knowledgeable support agent for i'M On Social.
"""
import os
import json
from datetime import datetime, timezone
from typing import Optional
from bson import ObjectId
from dotenv import load_dotenv

load_dotenv()

from emergentintegrations.llm.chat import LlmChat, UserMessage
from emergentintegrations.llm.openai import OpenAITextToSpeech

from routers.database import get_db

# ─────────────────────────────────────────────────────────
# Deep knowledge base — covers every feature, screen, flow
# ─────────────────────────────────────────────────────────
KNOWLEDGE_BASE = """You are Jessi, the AI support agent for i'M On Social — a relationship management system (RMS) built for automotive sales professionals. You know EVERYTHING about this tool. You are warm, encouraging, concise, and always helpful.

## APP NAVIGATION
The app has 5 bottom tabs:
1. **Home** — Dashboard with today's tasks, touchpoint goals, performance stats, streak counter, and quick-action buttons (SMS, Email, Call, Card).
2. **Contacts** — Customer database. Search, filter, tag. Tap a contact to see their full record (details, activity feed, notes, tasks).
3. **Activity** — Real-time feed showing all actions across the team (who sent what, who viewed what).
4. **Inbox** — Unified messaging center. All SMS/MMS conversations with customers. Send texts, photos, voice messages.
5. **Menu** (grid icon) — Access to ALL other features. This is the main hub for everything not on the bottom bar.

## MENU SCREEN (MORE TAB) — COMPLETE LISTING
The Menu screen organizes everything into sections:

**Communication:**
- Dialer — Phone pad to call customers directly
- Touchpoints — Daily/weekly touchpoint tracker with goals
- AI Outreach — AI-generated personalized messages

**My Tools:**
- My Profile — Edit bio, photo, fun facts, social links, expertise
- My Digital Card — Your shareable digital business card with QR code
- My Showcase — Photo/video gallery of your work, inventory highlights
- My Link Page — Personal landing page with all your links
- My Review Link — Direct link to request Google/DealerRater reviews
- Templates — Pre-written message templates for quick sends

**Sales:**
- Tasks — Follow-up reminders, campaign tasks, date-trigger tasks
- Campaigns — Automated message sequences for lead nurturing
- Leaderboard — Compete with teammates on touchpoint metrics
- AI Outreach — AI-suggested follow-up messages

**Manager Tools** (visible to managers/admins only):
- Team Dashboard — Team activity overview, performance metrics
- Manage Team — Add/remove team members, change roles
- Activity Feed — Monitor all team activity in real-time
- Hot Leads — Active leads requiring attention
- CRM Dashboard — Customer relationship analytics
- Reports — Detailed performance reports
- Lead Sources — Track where leads are coming from
- Lead Tracking — Pipeline management

**Settings:**
- Store Profile — Company name, address, logo, colors, branding
- Brand Kit — Upload logo, set brand colors for cards and emails
- Tags — Create/manage customer tags (sold, hot lead, be-back, etc.)
- Card Templates — Customize congrats/birthday/holiday card designs
- Email Templates — Create reusable email templates
- Date Triggers — Auto-tasks for birthdays, anniversaries, holidays
- Review Links — Configure Google review link
- Integrations — Connect external services
- Security — Password, session settings
- Invite Team — Send team invitations

**Support:**
- Jessi (that's you!) — AI help assistant
- Training Hub — Video tutorials and how-to guides
- SOPs — Standard operating procedures (admin only)

## CONTACT RECORD — DETAILED FEATURES
When you tap a contact, you see their full record:
- **Header**: Name, phone, email, photo, tags
- **Quick Actions**: Call, SMS, Email buttons (at the bottom)
- **Activity Feed**: Complete timeline of ALL interactions — texts sent, calls placed, cards shared, customer views, campaign messages, notes, tags applied. Click "Show All X Events" to expand.
- **Voice Notes**: Record audio notes about the customer. Tap the microphone icon.
- **Tasks**: Follow-up reminders linked to this contact.
- **Tags**: Apply tags like "sold", "hot lead", "be-back", "referral", "dormant"
- **Edit**: Update contact details, add notes, change assigned salesperson
- **CRM Link**: Share a public timeline URL showing the full relationship history (great for managers reviewing customer interactions)

**Sending a Text from a Contact:**
1. Open the contact record
2. Tap the SMS button at the bottom
3. Type your message OR select a template
4. Tap send — this opens your native SMS app with the message pre-filled
5. The event is automatically logged in the activity feed

**Sending a Card (Congrats, Birthday, etc.):**
1. Open the contact record or conversation thread
2. Tap the gift/card icon
3. Choose card type (Congrats, Birthday, Holiday, Thank You, Welcome, Anniversary)
4. Customize the message
5. Send via SMS — the card link is included in the text
6. This counts as BOTH a card sent AND a text sent in your stats

**Recording a Voice Note:**
1. Open the contact record
2. Scroll to the Notes section
3. Tap the microphone icon
4. Speak your note
5. It's automatically transcribed and saved

## INBOX — MESSAGING
- Shows all SMS conversations sorted by most recent
- Tap a conversation to open the thread
- Bottom toolbar: SMS button, Email button, Call button
- Within a thread: Type messages, attach photos, send cards, use templates
- Templates: Tap the template icon to insert a pre-written message
- Voice messages: Record and send audio clips

## CAMPAIGNS
Automated message sequences:
- Create a campaign with multiple steps (SMS or email)
- Set timing between steps (e.g., Day 1: Welcome, Day 3: Follow-up, Day 7: Check-in)
- Enroll contacts manually or via tags
- Monitor campaign progress and delivery status

## LEADERBOARD
- Tracks touchpoints: texts sent, calls made, emails sent, cards shared
- Ranks team members by total activity
- Streak tracking — consecutive days of meeting goals
- Level system: Rookie → Hustler → Closer → All-Star → Legend

## DIGITAL BUSINESS CARD
- Your personal digital card with photo, name, title, contact info
- Includes QR code for easy sharing
- Shareable link — send via text or email
- Customers can save your contact directly from the card
- Customize colors to match your brand

## TOUCHPOINTS / PERFORMANCE DASHBOARD
- "Texts Sent" now includes ALL texts: plain SMS + card sends + review links + showcase shares + link page shares
- "Calls" tracks calls placed and received
- "Emails" tracks emails sent
- "Cards" tracks congrats/birthday/holiday/thank you cards sent
- "Reviews" tracks review link shares
- Total touchpoints = texts + emails + calls + engagement signals

## TAGS
Common tags and their meanings:
- **sold** — Customer has purchased. Triggers AI follow-up suggestion.
- **hot lead** — Actively interested, requires immediate follow-up
- **be-back** — Customer who visited but didn't buy, likely to return
- **referral** — Referred by another customer
- **dormant** — Inactive customer, may need re-engagement
- **service** — Customer is in for service
- Tags can be created and customized in Settings > Tags

## ONBOARDING FLOW (SETUP WIZARD)
New users go through these steps:
1. Create account / Accept team invitation
2. Set up profile (name, title, photo)
3. Add bio and fun facts (voice-enabled — speak naturally and AI extracts the info)
4. Configure digital business card
5. Import or add first contacts
6. Send first message

## TROUBLESHOOTING — COMMON ISSUES

**"My texts aren't counting on the dashboard"**
→ All texts now count, including card sends. If you just deployed, refresh the app. The dashboard counts events from the contact_events collection.

**"I got logged out"**
→ The app uses persistent sessions. If you're on iOS Safari, make sure you're not in private browsing mode. Try logging back in — your data is safe.

**"My digital card looks wrong"**
→ Go to Settings > Brand Kit to update your logo and colors. Changes apply to all cards and the digital business card.

**"Push notifications aren't working"**
→ Make sure you've granted notification permissions. On iOS, go to Settings > Notifications > i'M On Social and enable them. In the app, you should see a notification prompt on first login.

**"I can't see manager/admin features"**
→ Your role may be set to 'user'. Ask your admin to change your role to 'manager' or 'admin' in Manage Team.

**"How do I share my digital card?"**
→ Go to Menu > My Digital Card. Tap the share button. You can copy the link, send via text, or show the QR code.

**"How do I send a congrats card when someone buys?"**
→ Open the customer's contact record. Tap the card/gift icon. Select "Congrats" card type. Customize the message and send.

**"How do I set up a campaign?"**
→ Go to Menu > Campaigns. Tap + to create. Add steps with messages and timing. Then enroll contacts by selecting them or using a tag filter.

**"How do I track my team's performance?"**
→ Go to Menu > Team Dashboard or Menu > Leaderboard. You'll see everyone's activity, touchpoint counts, and rankings.

**"A customer said they didn't get my text"**
→ The app opens your native SMS app to send. Check your phone's Messages app to confirm it actually sent. The app logs the event when you tap send, but delivery depends on your carrier.

**"How do I change a user's role?"**
→ Admin only: Go to Menu > Manage Team. Find the user, tap their name. Change the Role dropdown and save.

**"How do I delete a contact?"**
→ Open the contact record. Tap Edit. Scroll to the bottom and tap Delete Contact.

## GUIDELINES FOR YOUR RESPONSES
- Keep answers concise: 2-4 sentences for simple questions, step-by-step for how-to
- Always give specific navigation paths: "Go to Menu > Settings > Tags"
- Be encouraging: "Great question!", "You're on the right track!"
- If unsure, say so: "I'm not 100% sure about that, but here's what I'd try..."
- Use the person's name occasionally
- For complex tasks, number the steps
- If someone seems frustrated, be empathetic first, then solve
"""


async def get_or_create_chat_session(user_id: str) -> dict:
    """Get existing chat session or create a new one for the user"""
    db = get_db()
    session = await db.jessie_sessions.find_one(
        {"user_id": user_id, "is_active": True}
    )
    if session:
        return {
            "_id": str(session["_id"]),
            "session_id": session["session_id"],
            "messages": session.get("messages", []),
            "created_at": session.get("created_at"),
        }
    import secrets
    session_id = f"jessie_{user_id}_{secrets.token_hex(8)}"
    new_session = {
        "user_id": user_id,
        "session_id": session_id,
        "messages": [],
        "is_active": True,
        "created_at": datetime.now(timezone.utc),
    }
    result = await db.jessie_sessions.insert_one(new_session)
    new_session["_id"] = str(result.inserted_id)
    return new_session


async def save_message(user_id: str, role: str, content: str, audio_url: Optional[str] = None):
    """Save a message to the user's chat history"""
    db = get_db()
    message = {
        "role": role,
        "content": content,
        "audio_url": audio_url,
        "timestamp": datetime.now(timezone.utc),
    }
    await db.jessie_sessions.update_one(
        {"user_id": user_id, "is_active": True},
        {"$push": {"messages": message}, "$set": {"updated_at": datetime.now(timezone.utc)}}
    )
    return message


async def get_chat_history(user_id: str, limit: int = 20) -> list:
    """Get recent chat history"""
    db = get_db()
    session = await db.jessie_sessions.find_one({"user_id": user_id, "is_active": True})
    if not session:
        return []
    messages = session.get("messages", [])
    return messages[-limit:] if len(messages) > limit else messages


async def _build_user_context(user_id: str) -> str:
    """Fetch user info + live stats for personalized context injection."""
    db = get_db()
    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)}, {"_id": 0, "password": 0, "password_hash": 0})
    except Exception:
        return ""
    if not user:
        return ""

    name = user.get("name", "").split()[0] or "there"
    role = user.get("role", "user")
    org_id = user.get("organization_id")
    org_name = ""
    if org_id:
        try:
            org = await db.stores.find_one({"_id": ObjectId(org_id)}, {"name": 1, "_id": 0})
            org_name = org.get("name", "") if org else ""
        except Exception:
            pass

    # Quick stats
    contact_count = await db.contacts.count_documents({"user_id": user_id})
    event_count = await db.contact_events.count_documents({"user_id": user_id})

    parts = ["\n\n## CURRENT USER CONTEXT"]
    parts.append(f"- Name: {name}")
    parts.append(f"- Role: {role}")
    if org_name:
        parts.append(f"- Organization: {org_name}")
    parts.append(f"- Total contacts: {contact_count}")
    parts.append(f"- Total logged activities: {event_count}")
    if role in ("admin", "super_admin"):
        parts.append("- Has access to ALL admin/manager features")
    elif role == "manager":
        parts.append("- Has access to manager features (team dashboard, reports, manage team)")
    else:
        parts.append("- Standard user role — if they ask about admin features, tell them to contact their manager")

    # ── LIVE STATS: Today's touchpoints ──
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    try:
        pipeline = [
            {"$match": {"user_id": user_id, "timestamp": {"$gte": today_start}}},
            {"$group": {"_id": "$event_type", "count": {"$sum": 1}}},
        ]
        today_events = {doc["_id"]: doc["count"] async for doc in db.contact_events.aggregate(pipeline)}

        sms_types = [
            "personal_sms", "sms_sent", "sms_personal", "sms_failed",
            "congrats_card_sent", "birthday_card_sent", "holiday_card_sent",
            "thank_you_card_sent", "thankyou_card_sent", "anniversary_card_sent",
            "welcome_card_sent", "digital_card_sent", "digital_card_shared",
            "card_shared", "vcard_sent", "review_request_sent", "review_shared",
            "review_invite_sent", "link_page_shared", "showcase_shared", "showroom_shared",
        ]
        texts_today = sum(today_events.get(t, 0) for t in sms_types)
        calls_today = today_events.get("call_placed", 0)
        emails_today = today_events.get("email_sent", 0) + today_events.get("email_failed", 0)

        parts.append("\n### Today's Activity (live)")
        parts.append(f"- Texts sent today: {texts_today}")
        parts.append(f"- Calls made today: {calls_today}")
        parts.append(f"- Emails sent today: {emails_today}")
    except Exception:
        pass

    # ── LIVE STATS: Pending tasks ──
    try:
        pending_tasks = await db.tasks.count_documents({
            "assigned_to": user_id,
            "status": {"$in": ["pending", "active"]},
        })
        overdue_tasks = await db.tasks.count_documents({
            "assigned_to": user_id,
            "status": {"$in": ["pending", "active"]},
            "due_date": {"$lt": datetime.now(timezone.utc)},
        })
        parts.append(f"- Pending tasks: {pending_tasks}")
        if overdue_tasks:
            parts.append(f"- OVERDUE tasks: {overdue_tasks} (mention this proactively!)")
    except Exception:
        pass

    # ── LIVE STATS: Unread messages ──
    try:
        unread = await db.conversations.count_documents({
            "user_id": user_id,
            "unread_count": {"$gt": 0},
        })
        if unread > 0:
            parts.append(f"- Unread conversations: {unread}")
    except Exception:
        pass

    # ── LIVE STATS: Hot leads ──
    try:
        hot_leads = await db.contacts.count_documents({
            "user_id": user_id,
            "tags": {"$in": ["hot lead", "hot_lead"]},
        })
        if hot_leads > 0:
            parts.append(f"- Hot leads requiring attention: {hot_leads}")
    except Exception:
        pass

    parts.append(f"\nAddress this user as {name}. Use their live stats to give proactive, personalized suggestions.")
    return "\n".join(parts)


async def _build_contact_context(contact_id: str, user_id: str) -> str:
    """When user is on a contact record, fetch that contact's details for deep context."""
    if not contact_id:
        return ""
    db = get_db()
    try:
        contact = await db.contacts.find_one(
            {"_id": ObjectId(contact_id), "user_id": user_id},
            {"_id": 0, "password": 0}
        )
    except Exception:
        return ""
    if not contact:
        return ""

    name = f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip() or "Unknown"
    tags = contact.get("tags", [])
    phone = contact.get("phone", "")
    email = contact.get("email", "")
    created = contact.get("created_at")
    created_str = created.strftime("%b %d, %Y") if hasattr(created, "strftime") else str(created or "unknown")

    parts = [f"\n\n## CONTACT BEING VIEWED: {name}"]
    parts.append(f"- Phone: {phone or 'not set'}")
    parts.append(f"- Email: {email or 'not set'}")
    parts.append(f"- Tags: {', '.join(tags) if tags else 'none'}")
    parts.append(f"- Customer since: {created_str}")

    # Recent activity for this contact
    try:
        recent = await db.contact_events.find(
            {"contact_id": str(contact_id), "user_id": user_id},
            {"_id": 0, "event_type": 1, "timestamp": 1}
        ).sort("timestamp", -1).limit(5).to_list(5)
        if recent:
            last_ts = recent[0].get("timestamp")
            if last_ts:
                from datetime import timedelta
                days_since = (datetime.now(timezone.utc) - last_ts).days if hasattr(last_ts, "date") else None
                if days_since is not None:
                    parts.append(f"- Last interaction: {days_since} day(s) ago")
                    if days_since > 7:
                        parts.append("  ⚠ It's been over a week — suggest a follow-up!")
                    if days_since > 30:
                        parts.append("  ⚠ Over a month with no contact — this customer may be going cold!")
            parts.append(f"- Recent activity ({len(recent)} most recent):")
            for ev in recent[:5]:
                parts.append(f"  • {ev.get('event_type', '?')}")
        else:
            parts.append("- No activity recorded yet — suggest making first contact!")
    except Exception:
        pass

    # Check for tasks related to this contact
    try:
        contact_tasks = await db.tasks.count_documents({
            "contact_id": str(contact_id),
            "user_id": user_id,
            "status": {"$in": ["pending", "active"]},
        })
        if contact_tasks:
            parts.append(f"- Pending tasks for this contact: {contact_tasks}")
    except Exception:
        pass

    # Tag-specific suggestions
    if "sold" in tags:
        parts.append("\nThis customer has PURCHASED. Suggest: thank-you card, review request, referral ask, or check-in in 2 weeks.")
    elif "hot lead" in tags or "hot_lead" in tags:
        parts.append("\nThis is a HOT LEAD. Suggest: immediate follow-up call or text, schedule a test drive, address any concerns.")
    elif "be-back" in tags or "be_back" in tags:
        parts.append("\nThis is a BE-BACK customer. Suggest: friendly check-in, share new inventory, offer to answer questions.")
    elif "dormant" in tags:
        parts.append("\nThis customer is DORMANT. Suggest: re-engagement text, share something personal, or a holiday card.")

    parts.append("\nUse this contact info naturally. If the user asks what to do next, give specific, actionable advice based on the tags and activity history.")
    return "\n".join(parts)


async def _build_proactive_suggestion(user_id: str, current_page: str) -> str:
    """Generate a proactive suggestion based on the page and user data."""
    db = get_db()
    suggestions = []

    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    try:
        # Check pending tasks
        pending = await db.tasks.count_documents({
            "assigned_to": user_id,
            "status": {"$in": ["pending", "active"]},
        })
        if pending > 0 and "home" in current_page.lower():
            suggestions.append(f"You have {pending} pending task{'s' if pending != 1 else ''}. Consider starting with your highest-priority follow-ups.")

        # Check hot leads
        hot = await db.contacts.count_documents({
            "user_id": user_id,
            "tags": {"$in": ["hot lead", "hot_lead"]},
        })
        if hot > 0:
            suggestions.append(f"You have {hot} hot lead{'s' if hot != 1 else ''} that may need attention today.")

        # Check unread
        unread = await db.conversations.count_documents({
            "user_id": user_id,
            "unread_count": {"$gt": 0},
        })
        if unread > 0:
            suggestions.append(f"You have {unread} unread conversation{'s' if unread != 1 else ''} waiting in your inbox.")

        # Check today's progress
        today_total = await db.contact_events.count_documents({
            "user_id": user_id,
            "timestamp": {"$gte": today_start},
        })
        if today_total == 0:
            suggestions.append("No touchpoints logged yet today — time to get started! A quick text or call goes a long way.")
        elif today_total < 10:
            suggestions.append(f"You've logged {today_total} touchpoint{'s' if today_total != 1 else ''} today. Keep the momentum going!")

    except Exception:
        pass

    if not suggestions:
        return ""

    return "\n\n## PROACTIVE SUGGESTIONS (share these naturally when relevant)\n" + "\n".join(f"- {s}" for s in suggestions)


async def chat_with_jessie(user_id: str, user_message: str, current_page: str = "", contact_id: str = "") -> dict:
    """
    Send a message to Jessi and get a response.
    v2: Passes history as context instead of replaying through LLM (10x faster).
    v2.1: Live stats, contact awareness, and proactive suggestions.
    """
    api_key = os.getenv("EMERGENT_LLM_KEY")
    if not api_key:
        raise ValueError("EMERGENT_LLM_KEY not configured")

    session = await get_or_create_chat_session(user_id)

    # Build context: knowledge base + user context + contact context + proactive + history
    user_context = await _build_user_context(user_id)
    contact_context = await _build_contact_context(contact_id, user_id) if contact_id else ""
    proactive = await _build_proactive_suggestion(user_id, current_page) if current_page else ""
    history = await get_chat_history(user_id, limit=8)

    # Page context
    page_context = ""
    if current_page:
        page_context = f"\n\n## CURRENT PAGE\nThe user is currently on: **{current_page}**. Tailor your help to this page when relevant."

    # Format history as text context (NOT replayed through LLM calls)
    history_text = ""
    if history:
        history_text = "\n\n## RECENT CONVERSATION\n"
        for msg in history:
            role_label = "User" if msg["role"] == "user" else "Jessi"
            history_text += f"{role_label}: {msg['content']}\n"

    system_prompt = KNOWLEDGE_BASE + user_context + contact_context + page_context + proactive + history_text

    # Single LLM call — no history replay
    chat = LlmChat(
        api_key=api_key,
        session_id=session["session_id"],
        system_message=system_prompt,
    ).with_model("openai", "gpt-4o-mini")

    # Save user message
    await save_message(user_id, "user", user_message)

    # Get response (single call, no replay)
    response_text = await chat.send_message(UserMessage(text=user_message))

    # Save assistant message
    await save_message(user_id, "assistant", response_text)

    return {
        "text": response_text,
        "session_id": session["session_id"],
    }


async def generate_voice_response(text: str) -> bytes:
    """Generate voice audio from Jessi's text response."""
    api_key = os.getenv("EMERGENT_LLM_KEY")
    if not api_key:
        raise ValueError("EMERGENT_LLM_KEY not configured")
    tts = OpenAITextToSpeech(api_key=api_key)
    audio_bytes = await tts.generate_speech(
        text=text,
        model="tts-1",
        voice="nova",
        speed=1.15,
        response_format="mp3",
    )
    return audio_bytes


async def generate_voice_response_base64(text: str) -> str:
    """Generate voice as base64 for direct embedding in responses"""
    api_key = os.getenv("EMERGENT_LLM_KEY")
    if not api_key:
        raise ValueError("EMERGENT_LLM_KEY not configured")
    tts = OpenAITextToSpeech(api_key=api_key)
    audio_base64 = await tts.generate_speech_base64(
        text=text,
        model="tts-1",
        voice="nova",
        speed=1.15,
        response_format="mp3",
    )
    return audio_base64


async def clear_chat_history(user_id: str):
    """Clear chat history for a user (start fresh conversation)"""
    db = get_db()
    await db.jessie_sessions.update_one(
        {"user_id": user_id, "is_active": True},
        {"$set": {"is_active": False, "ended_at": datetime.now(timezone.utc)}},
    )
    return {"message": "Chat history cleared"}


async def extract_profile_info(text: str, context: str = "intro") -> dict:
    """Extract structured profile information from natural speech."""
    api_key = os.getenv("EMERGENT_LLM_KEY")
    if not api_key:
        raise ValueError("EMERGENT_LLM_KEY not configured")

    extraction_prompts = {
        "intro": """Extract from this self-introduction:
- bio: A 1-2 sentence professional bio
- years_experience: Number or phrase
- specialties: List of skills
- personal_motto: Any motto mentioned""",
        "hobbies": """Extract from this description:
- hobbies: List of hobbies
- interests: List of interests""",
        "family": """Extract from this personal description:
- family_info: Brief family summary
- fun_facts: List of interesting facts""",
        "expertise": """Extract from this expertise description:
- specialties: List of areas of expertise
- fun_facts: List of achievements
- personal_motto: Any philosophy mentioned""",
    }

    prompt = extraction_prompts.get(context, extraction_prompts["intro"])
    system_prompt = f"""You are a profile data extractor. Extract structured information from the user's speech.

{prompt}

IMPORTANT: Only extract what was mentioned. Return empty arrays [] for missing lists, null for missing fields.
For bio, write in third person. Return ONLY valid JSON."""

    chat = LlmChat(
        api_key=api_key,
        system_message=system_prompt,
    ).with_model("openai", "gpt-4o-mini")

    response = await chat.send_message(UserMessage(text=f'Here\'s what they said:\n\n"{text}"'))

    try:
        response_text = response.strip()
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
        extracted = json.loads(response_text)
        return {k: v for k, v in extracted.items() if v is not None and v != [] and v != ""}
    except json.JSONDecodeError:
        return {"bio": text[:200] if len(text) > 200 else text}
