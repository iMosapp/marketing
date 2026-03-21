"""
Chat Widget API — Jessi-powered live chat for the marketing website.
Sessions are anonymous until the visitor shares contact info,
then a contact + inbox thread is created automatically.
"""

import os
import uuid
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Request

router = APIRouter(prefix="/chat", tags=["Chat Widget"])
logger = logging.getLogger("chat_widget")

# In-memory session store (lightweight, resets on restart — fine for chat)
_sessions: dict = {}

JESSI_SYSTEM_PROMPT = """You are Jessi, the friendly AI assistant for i'M On Social — the relationship engine for sales professionals.

ABOUT i'M ON SOCIAL:
- It's a platform that turns salespeople into personal brands and automates follow-up so they never lose a customer after the sale.
- Key features: Digital Business Cards (shareable, trackable), Personal Review Pages, Showcase/Landing Pages, AI-Powered Follow-Up Campaigns, Shared Team Inbox, Congrats Cards (photo with customer becomes a branded card they share), Leaderboards & Gamification, SEO & AEO visibility, Jessi AI assistant, Voice Notes.
- Industries served: Automotive dealerships, Real Estate, Powersports, Salons & Spas, Restaurants, Home Services, Fitness, Insurance & Financial, Medical & Dental, and any sales team.
- For organizations: manage teams, stores, and reputation across locations with white-label options.
- For individuals: own your personal brand, collect reviews, build an online presence.
- Pricing: custom based on team size — encourage them to book a demo for specifics.
- Competitors: Podium, Kenect, Matador AI — but those are chatbots that replace people. i'M On Social makes people unforgettable.

YOUR PERSONALITY:
- Warm, knowledgeable, conversational — not salesy or robotic.
- You genuinely want to help them understand if i'M On Social is right for their business.
- Keep responses concise (2-4 sentences max). Don't dump feature lists unless asked.

YOUR STRATEGY:
- First 2-3 messages: Answer their questions helpfully and naturally.
- Around message 3-4: Naturally weave in asking for their name and what business they're with, so you can personalize the conversation.
- Around message 4-5: After you have some info, say something like "I'd love to have someone from our team reach out who specializes in [their industry]. What's the best email or phone to reach you?"
- Once you have their contact info: Thank them warmly and let them know a team member will be in touch shortly. You can say "Let me grab my manager — they'll want to connect with you personally."
- If they don't want to share info, that's fine — keep being helpful and suggest they book a demo at imonsocial.com when ready.

IMPORTANT:
- Never make up pricing numbers. Say "pricing depends on team size — a quick demo call is the best way to get specifics."
- Never fabricate features that don't exist.
- If asked something you don't know, say "Great question — that's something our team can dive deeper into on a call."
"""


def _get_db(request: Request):
    return request.app.state.db


@router.post("/start")
async def start_session(request: Request):
    """Start an anonymous chat session."""
    data = await request.json()
    session_id = str(uuid.uuid4())
    _sessions[session_id] = {
        "id": session_id,
        "messages": [],
        "lead_captured": False,
        "contact_info": {},
        "page_source": data.get("page", "website"),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    return {
        "session_id": session_id,
        "greeting": "Hi! I'm Jessi from i'M On Social. What can I help you with today?"
    }


@router.post("/message")
async def send_message(request: Request):
    """Send a visitor message and get Jessi's AI response."""
    data = await request.json()
    session_id = data.get("session_id")
    message = (data.get("message") or "").strip()

    if not session_id or session_id not in _sessions:
        return {"error": "Invalid session", "response": "Sorry, your session expired. Please refresh the page to start a new chat."}

    if not message:
        return {"error": "Empty message", "response": ""}

    session = _sessions[session_id]
    session["messages"].append({"role": "visitor", "text": message, "ts": datetime.now(timezone.utc).isoformat()})

    # Check if visitor shared contact info in this message
    _try_extract_contact(session, message)

    try:
        api_key = os.getenv("EMERGENT_LLM_KEY")
        if not api_key:
            return {"response": "I'm having a technical hiccup — try again in a moment!", "lead_captured": session["lead_captured"]}

        from emergentintegrations.llm.chat import LlmChat, UserMessage

        chat = LlmChat(
            api_key=api_key,
            session_id=f"chat_widget_{session_id}",
            system_message=JESSI_SYSTEM_PROMPT
        ).with_model("openai", "gpt-4o-mini")

        # Build conversation context
        msg_count = len([m for m in session["messages"] if m["role"] == "visitor"])
        context_hint = ""
        if msg_count >= 3 and not session["contact_info"].get("name"):
            context_hint = "\n[INTERNAL NOTE: This is message #{}. Try to naturally ask for their name and business.]".format(msg_count)
        elif msg_count >= 4 and not session["contact_info"].get("email"):
            context_hint = "\n[INTERNAL NOTE: You know their name. Now try to get their email or phone so a team member can follow up.]"
        elif session["lead_captured"]:
            context_hint = "\n[INTERNAL NOTE: You have their contact info. Wrap up warmly — mention you'll grab your manager to connect with them personally.]"

        full_message = message + context_hint
        response = await chat.send_message(UserMessage(text=full_message))
        response_text = response if isinstance(response, str) else str(response)

        session["messages"].append({"role": "jessi", "text": response_text, "ts": datetime.now(timezone.utc).isoformat()})

        # If lead was just captured, create the inbox thread
        if session["lead_captured"] and not session.get("inbox_created"):
            db = _get_db(request)
            await _create_inbox_lead(db, session)
            session["inbox_created"] = True

        return {
            "response": response_text,
            "lead_captured": session["lead_captured"],
        }

    except Exception as e:
        logger.error(f"Chat AI error: {e}")
        return {"response": "Give me one second — let me think about that...", "lead_captured": session["lead_captured"]}


@router.post("/capture")
async def capture_lead(request: Request):
    """Manually capture contact info from the widget form."""
    data = await request.json()
    session_id = data.get("session_id")

    if not session_id or session_id not in _sessions:
        return {"error": "Invalid session"}

    session = _sessions[session_id]
    if data.get("name"):
        session["contact_info"]["name"] = data["name"].strip()
    if data.get("email"):
        session["contact_info"]["email"] = data["email"].strip()
    if data.get("phone"):
        session["contact_info"]["phone"] = data["phone"].strip()

    # Mark as captured if we have at least name + one contact method
    if session["contact_info"].get("name") and (session["contact_info"].get("email") or session["contact_info"].get("phone")):
        session["lead_captured"] = True

        if not session.get("inbox_created"):
            db = _get_db(request)
            await _create_inbox_lead(db, session)
            session["inbox_created"] = True

    return {"status": "ok", "lead_captured": session["lead_captured"]}


def _try_extract_contact(session: dict, message: str):
    """Try to detect if the visitor shared contact info in their message."""
    import re
    msg_lower = message.lower()

    # Email
    email_match = re.search(r'[\w.+-]+@[\w-]+\.[\w.]+', message)
    if email_match:
        session["contact_info"]["email"] = email_match.group()

    # Phone (basic patterns)
    phone_match = re.search(r'(\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})', message)
    if phone_match:
        session["contact_info"]["phone"] = phone_match.group()

    # Name detection is harder — skip auto-detect, let the AI handle it
    # But if they say "I'm X" or "My name is X"
    name_match = re.search(r"(?:i'm|my name is|this is|i am)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)", message, re.IGNORECASE)
    if name_match:
        session["contact_info"]["name"] = name_match.group(1).strip()

    # Mark captured if we have enough
    if session["contact_info"].get("name") and (session["contact_info"].get("email") or session["contact_info"].get("phone")):
        session["lead_captured"] = True


async def _create_inbox_lead(db, session: dict):
    """Create a contact + inbox conversation from the chat session."""
    try:
        info = session["contact_info"]
        page_source = session.get("page_source", "website")

        source_labels = {
            "seo_page": "SEO & AEO", "store_reviews_page": "Store Reviews",
            "digital_card_page": "Digital Cards", "showcase_page": "Showcase",
            "dealers_page": "Automotive", "pitch_powersports": "Powersports",
            "pitch_real_estate": "Real Estate", "pitch_salons": "Salons & Spas",
            "pitch_restaurants": "Restaurants", "pitch_home_services": "Home Services",
            "pitch_fitness": "Fitness", "pitch_insurance": "Insurance & Financial",
            "homepage": "Homepage", "pricing_page": "Pricing",
        }
        pretty_source = source_labels.get(page_source, page_source.replace("_", " ").title())

        # Find an admin user to own this lead
        admin = await db.users.find_one({"role": {"$in": ["super_admin", "admin"]}}, {"_id": 1})
        if not admin:
            return
        owner_id = str(admin["_id"])

        # Create contact
        name = info.get("name", "Website Visitor")
        name_parts = name.split(" ", 1)
        contact_filter = []
        if info.get("email"):
            contact_filter.append({"email": info["email"]})
        if info.get("phone"):
            contact_filter.append({"phone": info["phone"]})

        existing = None
        if contact_filter:
            existing = await db.contacts.find_one({"user_id": owner_id, "$or": contact_filter}, {"_id": 1})

        if existing:
            contact_id = str(existing["_id"])
        else:
            result = await db.contacts.insert_one({
                "user_id": owner_id,
                "first_name": name_parts[0],
                "last_name": name_parts[1] if len(name_parts) > 1 else "",
                "email": info.get("email", ""),
                "phone": info.get("phone", ""),
                "source": f"chat_widget_{page_source}",
                "tags": ["new-lead", "website-chat"],
                "notes": f"Started chat on {pretty_source} page",
                "created_at": datetime.now(timezone.utc),
            })
            contact_id = str(result.inserted_id)

        # Create conversation
        existing_conv = await db.conversations.find_one({"user_id": owner_id, "contact_id": contact_id})
        if existing_conv:
            conv_id = str(existing_conv["_id"])
            await db.conversations.update_one(
                {"_id": existing_conv["_id"]},
                {"$set": {"unread": True, "last_message_at": datetime.now(timezone.utc), "ai_outcome": "new_lead", "ai_outcome_priority": 1,
                          "unread_count": (existing_conv.get("unread_count", 0) or 0) + 1}}
            )
        else:
            result = await db.conversations.insert_one({
                "user_id": owner_id,
                "contact_id": contact_id,
                "contact_phone": info.get("phone", ""),
                "status": "active",
                "unread": True,
                "unread_count": 1,
                "ai_enabled": False,
                "ai_outcome": "new_lead",
                "ai_outcome_priority": 1,
                "needs_assistance": True,
                "created_at": datetime.now(timezone.utc),
                "last_message_at": datetime.now(timezone.utc),
            })
            conv_id = str(result.inserted_id)

        # Build transcript
        transcript_lines = [f"Website chat from {pretty_source} page"]
        if info.get("email"):
            transcript_lines.append(f"Email: {info['email']}")
        if info.get("phone"):
            transcript_lines.append(f"Phone: {info['phone']}")
        transcript_lines.append("")
        transcript_lines.append("--- Chat Transcript ---")
        for msg in session.get("messages", []):
            speaker = "Visitor" if msg["role"] == "visitor" else "Jessi"
            transcript_lines.append(f"{speaker}: {msg['text'][:200]}")

        await db.messages.insert_one({
            "conversation_id": conv_id,
            "user_id": owner_id,
            "contact_id": contact_id,
            "direction": "inbound",
            "channel": "chat_widget",
            "body": "\n".join(transcript_lines),
            "type": "lead_chat",
            "read": False,
            "created_at": datetime.now(timezone.utc),
        })

        # Also create a notification
        await db.notifications.insert_one({
            "user_id": owner_id,
            "type": "new_lead",
            "title": f"New chat lead: {name}",
            "message": f"{name} started a chat on the {pretty_source} page",
            "lead_source": f"chat_{page_source}",
            "read": False,
            "created_at": datetime.now(timezone.utc),
        })

    except Exception as e:
        logger.error(f"Failed to create inbox lead from chat: {e}")
        import traceback
        traceback.print_exc()
