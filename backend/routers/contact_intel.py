"""
AI Contact Summary  - "Relationship Intel"
Generates an on-demand AI briefing about a contact using all available data.
"""
import os
import logging
from datetime import datetime, timezone
from bson import ObjectId

from fastapi import APIRouter, HTTPException
from routers.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/contact-intel", tags=["contact-intel"])


async def _gather_contact_context(db, user_id: str, contact_id: str) -> dict:
    """Pull all relevant data for a contact to feed into the AI summary."""
    
    # Contact details
    contact = await db.contacts.find_one(
        {"_id": ObjectId(contact_id)},
        {"photo": 0, "photo_thumbnail": 0, "photo_url": 0}
    )
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    # Messages (last 50)
    messages = await db.messages.find(
        {"contact_id": contact_id},
        {"_id": 0, "content": 1, "direction": 1, "channel": 1, "created_at": 1, "sender_name": 1}
    ).sort("created_at", -1).limit(50).to_list(50)
    
    # Contact events
    events = await db.contact_events.find(
        {"contact_id": contact_id},
        {"_id": 0, "event_type": 1, "title": 1, "description": 1, "timestamp": 1, "channel": 1}
    ).sort("timestamp", -1).limit(30).to_list(30)
    
    # Voice note transcripts
    voice_notes = await db.voice_notes.find(
        {"contact_id": contact_id},
        {"_id": 0, "transcript": 1, "duration": 1, "created_at": 1}
    ).sort("created_at", -1).limit(10).to_list(10)
    
    # Tasks
    tasks = await db.tasks.find(
        {"contact_id": contact_id},
        {"_id": 0, "title": 1, "type": 1, "status": 1, "due_date": 1}
    ).sort("created_at", -1).limit(10).to_list(10)
    
    return {
        "contact": contact,
        "messages": messages,
        "events": events,
        "voice_notes": voice_notes,
        "tasks": tasks,
    }


def _build_prompt(ctx: dict) -> str:
    """Build the AI prompt from gathered context."""
    contact = ctx["contact"]
    now = datetime.now(timezone.utc)
    
    # Contact basics
    name = f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip()
    phone = contact.get('phone', '')
    email = contact.get('email', '') or contact.get('email_work', '')
    tags = contact.get('tags', [])
    notes = contact.get('notes', '')
    birthday = contact.get('birthday', '')
    anniversary = contact.get('anniversary', '')
    date_sold = contact.get('date_sold', '')
    created = contact.get('created_at')
    
    # Relationship length
    rel_length = ""
    if created:
        if isinstance(created, str):
            try:
                created = datetime.fromisoformat(created.replace('Z', '+00:00'))
            except:
                created = None
        if created:
            days = (now - created.replace(tzinfo=timezone.utc) if created.tzinfo is None else now - created).days
            if days < 30:
                rel_length = f"{days} days"
            elif days < 365:
                rel_length = f"{days // 30} months"
            else:
                rel_length = f"{days // 365} years, {(days % 365) // 30} months"
    
    # Build context sections
    sections = []
    sections.append(f"CONTACT: {name}")
    if phone: sections.append(f"Phone: {phone}")
    if email and email.lower() not in ('none', 'null', ''): sections.append(f"Email: {email}")
    if tags: sections.append(f"Tags: {', '.join(tags)}")
    if rel_length: sections.append(f"Relationship length: {rel_length}")
    if birthday: sections.append(f"Birthday: {birthday}")
    if anniversary: sections.append(f"Anniversary: {anniversary}")
    if date_sold: sections.append(f"Date sold: {date_sold}")
    if notes: sections.append(f"Notes: {notes}")
    
    # Messages
    if ctx["messages"]:
        sections.append("\nRECENT MESSAGES (newest first):")
        for m in ctx["messages"][:30]:
            direction = "→ Sent" if m.get("direction") == "outbound" else "← Received"
            channel = m.get("channel", "sms")
            date = m.get("created_at", "")
            if isinstance(date, datetime):
                date = date.strftime("%b %d, %Y %I:%M %p")
            content = (m.get("content") or "")[:200]
            sections.append(f"  {direction} ({channel}) {date}: {content}")
    
    # Events
    if ctx["events"]:
        sections.append("\nACTIVITY EVENTS:")
        for e in ctx["events"][:20]:
            etype = e.get("event_type", "")
            title = e.get("title", "")
            desc = (e.get("description") or "")[:150]
            ts = e.get("timestamp", "")
            if isinstance(ts, datetime):
                ts = ts.strftime("%b %d, %Y")
            sections.append(f"  [{etype}] {title}  - {desc} ({ts})")
    
    # Voice notes
    if ctx["voice_notes"]:
        sections.append("\nVOICE NOTE TRANSCRIPTS:")
        for v in ctx["voice_notes"]:
            transcript = v.get("transcript", "")
            date = v.get("created_at", "")
            if isinstance(date, datetime):
                date = date.strftime("%b %d, %Y")
            if transcript:
                sections.append(f"  [{date}] {transcript[:300]}")
    
    # Tasks
    if ctx["tasks"]:
        sections.append("\nTASKS:")
        for t in ctx["tasks"]:
            sections.append(f"  {t.get('title', '')}  - {t.get('status', '')} (due: {t.get('due_date', 'N/A')})")
    
    return "\n".join(sections)


@router.post("/{user_id}/{contact_id}")
async def generate_contact_intel(user_id: str, contact_id: str):
    """Generate an AI relationship summary for a contact."""
    db = get_db()
    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="AI service not configured")
    
    # Gather all context
    ctx = await _gather_contact_context(db, user_id, contact_id)
    contact_data = _build_prompt(ctx)
    name = f"{ctx['contact'].get('first_name', '')} {ctx['contact'].get('last_name', '')}".strip()
    
    # Call GPT-5.2
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        
        system_prompt = """You are a relationship intelligence analyst for a sales CRM. Generate a concise, actionable briefing about a customer.

FORMAT YOUR RESPONSE EXACTLY LIKE THIS (use these exact section headers on their own line):

Quick Take
One or two sentences capturing the relationship status and priority level.

Key Facts
- First key fact about who they are
- What they bought or need
- Important dates or milestones

Communication Patterns
- How often they engage and through what channel
- Response patterns or preferences

Personal Notes
- Family mentions, interests, or hobbies
- Preferences or anything personal from conversations

Before Your Next Interaction
- First actionable talking point
- Something specific to mention or ask about

RULES:
- Be specific. Use actual names, dates, and details from the data.
- If there is limited data, say so honestly. Do not fabricate.
- Keep it under 250 words total.
- Write in a direct, natural tone. Like briefing a colleague before a meeting.
- Never use em dashes or double hyphens. Use commas or periods instead.
- Never use asterisks or markdown formatting.
- Use simple dashes (-) for bullet points only.
- Each section header must be on its own line with no extra punctuation.
- Focus on what is useful to know right now."""

        chat = LlmChat(
            api_key=api_key,
            session_id=f"intel_{contact_id}_{user_id}",
            system_message=system_prompt
        ).with_model("openai", "gpt-5.2")
        
        response = await chat.send_message(
            UserMessage(text=f"Generate a relationship intel briefing for this contact:\n\n{contact_data}")
        )
        
        summary_text = response if isinstance(response, str) else (response.text if hasattr(response, 'text') else str(response))
        if not summary_text:
            summary_text = "Unable to generate summary."
        
    except Exception as e:
        logger.error(f"AI summary generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"AI generation failed: {str(e)}")
    
    # Cache the summary
    now = datetime.now(timezone.utc)
    await db.contact_intel.update_one(
        {"contact_id": contact_id, "user_id": user_id},
        {"$set": {
            "contact_id": contact_id,
            "user_id": user_id,
            "summary": summary_text,
            "contact_name": name,
            "generated_at": now,
            "data_points": {
                "messages": len(ctx["messages"]),
                "events": len(ctx["events"]),
                "voice_notes": len(ctx["voice_notes"]),
                "tasks": len(ctx["tasks"]),
            },
        }},
        upsert=True,
    )
    
    return {
        "summary": summary_text,
        "contact_name": name,
        "generated_at": now.isoformat(),
        "data_points": {
            "messages": len(ctx["messages"]),
            "events": len(ctx["events"]),
            "voice_notes": len(ctx["voice_notes"]),
            "tasks": len(ctx["tasks"]),
        },
    }


@router.get("/{user_id}/{contact_id}")
async def get_cached_intel(user_id: str, contact_id: str):
    """Get the cached AI summary for a contact (if available)."""
    db = get_db()
    doc = await db.contact_intel.find_one(
        {"contact_id": contact_id, "user_id": user_id},
        {"_id": 0}
    )
    if not doc:
        return {"summary": None, "generated_at": None}
    
    return {
        "summary": doc.get("summary"),
        "contact_name": doc.get("contact_name"),
        "generated_at": doc["generated_at"].isoformat() if doc.get("generated_at") else None,
        "data_points": doc.get("data_points", {}),
    }



@router.post("/{user_id}/{contact_id}/suggest-message")
async def suggest_message(user_id: str, contact_id: str):
    """AI-powered message suggestion based on relationship context, recent activity, and upcoming events."""
    db = get_db()
    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="AI service not configured")

    ctx = await _gather_contact_context(db, user_id, contact_id)
    contact_data = _build_prompt(ctx)
    name = f"{ctx['contact'].get('first_name', '')} {ctx['contact'].get('last_name', '')}".strip()

    # Get suggested actions (upcoming birthdays, anniversaries, milestones)
    from routers.contact_events import get_suggested_actions
    try:
        actions_resp = await get_suggested_actions(user_id, contact_id)
        upcoming_actions = actions_resp.get("actions", []) if isinstance(actions_resp, dict) else []
    except Exception:
        upcoming_actions = []

    actions_text = ""
    if upcoming_actions:
        actions_text = "\n\nUPCOMING ACTIONS/REMINDERS:\n"
        for a in upcoming_actions[:5]:
            actions_text += f"- {a.get('title', '')}: {a.get('description', '')}\n"

    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage

        system_prompt = """You are a smart CRM assistant that suggests the perfect next message to send to a customer.
Based on the relationship history, recent activity, and any upcoming events, write ONE short, natural, personalized message.

RULES:
- Write in a warm, professional, first-person tone (as the salesperson)
- Keep it under 160 characters if possible (SMS-friendly)
- Reference something specific from their recent activity or an upcoming event
- If there's a birthday/anniversary coming up, prioritize that
- If there's been no contact in 30+ days, write a friendly check-in
- If they recently bought something, write a follow-up
- If they left a review, write a thank-you
- Do NOT use emojis excessively (1-2 max)
- Do NOT use placeholder brackets like [name]
- Be specific and personal, not generic
- NEVER use em-dashes (the long dash character). Use commas or short hyphens instead.

Return ONLY the message text, nothing else. No quotes, no explanation."""

        chat = LlmChat(
            api_key=api_key,
            session_id=f"suggest_{contact_id}_{user_id}",
            system_message=system_prompt
        ).with_model("openai", "gpt-5.2")

        prompt = f"Suggest a message to send to this contact:\n\n{contact_data}{actions_text}"
        response = await chat.send_message(UserMessage(text=prompt))
        suggestion = response if isinstance(response, str) else (response.text if hasattr(response, 'text') else str(response))

        # Determine intent
        intent = "general"
        if upcoming_actions:
            intent = upcoming_actions[0].get("type", "general")

        # Post-process: remove em-dashes
        clean = suggestion.strip().strip('"').strip("'")
        clean = clean.replace('\u2014', ',').replace('\u2013', '-')

        return {
            "suggestion": clean,
            "intent": intent,
            "contact_name": name,
        }

    except Exception as e:
        logger.error(f"AI message suggestion failed: {e}")
        raise HTTPException(status_code=500, detail=f"AI suggestion failed: {str(e)}")
