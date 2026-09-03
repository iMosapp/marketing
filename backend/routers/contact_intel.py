"""
AI Contact Summary  - "Relationship Intel"
Generates an on-demand AI briefing about a contact using all available data.
"""
import asyncio
import json
import os
import logging
from datetime import datetime, timezone
from bson import ObjectId

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
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
    
    # Messages (last 60): inbox texts are keyed by conversation_id + timestamp, older docs by contact_id + created_at
    messages = await db.messages.aggregate([
        {"$match": {**(await _message_match(db, contact_id)), "sender": {"$ne": "ai_draft"}, "type": {"$ne": "event"}}},
        {"$addFields": {"_ts": {"$ifNull": ["$timestamp", "$created_at"]}}},
        {"$sort": {"_ts": -1}},
        {"$limit": 60},
        {"$project": {"_id": 0, "content": 1, "sender": 1, "direction": 1, "channel": 1, "type": 1, "created_at": "$_ts"}},
    ]).to_list(60)
    
    # Contact events
    events = await db.contact_events.find(
        {"contact_id": contact_id},
        {"_id": 0, "event_type": 1, "title": 1, "description": 1, "timestamp": 1, "channel": 1}
    ).sort("timestamp", -1).limit(30).to_list(30)

    # Recorded phone calls (transcript + AI summary)
    calls = await db.call_logs.find(
        {"contact_id": contact_id},
        {"_id": 0, "transcript": 1, "ai_summary": 1, "duration_s": 1, "direction": 1, "created_at": 1}
    ).sort("created_at", -1).limit(5).to_list(5)
    
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
        "calls": calls,
        "tasks": tasks,
    }


async def _message_match(db, contact_id: str) -> dict:
    conv_ids = [str(c["_id"]) async for c in db.conversations.find({"contact_id": contact_id}, {"_id": 1})]
    ors = [{"contact_id": contact_id}]
    if conv_ids:
        ors.append({"conversation_id": {"$in": conv_ids}})
    return {"$or": ors}


def _msg_label(m: dict) -> str:
    if m.get("sender") == "contact" or m.get("direction") == "inbound":
        return "← Customer"
    if m.get("sender") == "ai":
        return "→ Jessi (AI assistant)"
    if m.get("type") == "call_log":
        return "· Call"
    return "→ You"


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
            except Exception:
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
    for label, key in (("Vehicle", "vehicle"), ("Occupation", "occupation"), ("Employer", "employer"), ("City", "address_city")):
        if contact.get(key): sections.append(f"{label}: {contact[key]}")

    # Personal details captured from voice notes, texts and calls (newest wins)
    pd = contact.get("personal_details") or {}
    pd_lines = []
    for k, v in pd.items():
        if v in (None, "", [], {}):
            continue
        if isinstance(v, list):
            v = "; ".join(json.dumps(i) if isinstance(i, dict) else str(i) for i in v)
        pd_lines.append(f"  {k.replace('_', ' ')}: {v}")
    if pd_lines:
        sections.append("\nKNOWN PERSONAL DETAILS:")
        sections.extend(pd_lines)
    
    # Messages
    if ctx["messages"]:
        sections.append("\nRECENT TEXT THREAD (newest first; Jessi is the rep's AI assistant):")
        for m in ctx["messages"][:40]:
            content = (m.get("content") or "").strip()
            if not content:
                continue
            channel = m.get("channel") or "sms"
            date = m.get("created_at", "")
            if isinstance(date, datetime):
                date = date.strftime("%b %d, %Y %I:%M %p")
            sections.append(f"  {_msg_label(m)} ({channel}) {date}: {content[:240]}")

    # Recorded calls
    if ctx.get("calls"):
        sections.append("\nRECORDED PHONE CALLS:")
        for c in ctx["calls"]:
            date = c.get("created_at", "")
            if isinstance(date, datetime):
                date = date.strftime("%b %d, %Y")
            dur = c.get("duration_s") or 0
            sections.append(f"  [{date}] {c.get('direction') or 'call'} · {dur // 60}m {dur % 60}s")
            if c.get("ai_summary"):
                sections.append(f"    Summary: {c['ai_summary'][:500]}")
            if c.get("transcript"):
                sections.append(f"    Transcript: {c['transcript'][:600]}")
    
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

    # New texts / call transcripts since the last pass update personal_details (same extractor as voice notes)
    async def _extract():
        try:
            from services.voice_intel import process_conversation_intelligence
            return await process_conversation_intelligence(user_id, contact_id)
        except Exception as e:
            logger.warning(f"[ContactIntel] conversation extraction failed: {e}")
            return {}
    extraction = asyncio.create_task(_extract())
    
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

    from utils.text_sanitize import no_em_dash
    summary_text = no_em_dash(summary_text)
    extracted = await extraction
    learned = await _learned_state(db, contact_id)
    
    # Cache the summary
    now = datetime.now(timezone.utc)
    data_points = {
        "messages": sum(1 for m in ctx["messages"] if (m.get("content") or "").strip()),
        "events": len(ctx["events"]),
        "voice_notes": len(ctx["voice_notes"]),
        "calls": len(ctx.get("calls") or []),
        "tasks": len(ctx["tasks"]),
    }
    await db.contact_intel.update_one(
        {"contact_id": contact_id, "user_id": user_id},
        {"$set": {
            "contact_id": contact_id,
            "user_id": user_id,
            "summary": summary_text,
            "contact_name": name,
            "generated_at": now,
            "data_points": data_points,
        }},
        upsert=True,
    )
    
    return {
        "summary": summary_text,
        "contact_name": name,
        "generated_at": now.isoformat(),
        "data_points": data_points,
        "details_updated": sorted((extracted or {}).get("applied", {}).keys()),
        **learned,
    }


def _jsonable(v):
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, dict):
        return {k: _jsonable(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_jsonable(x) for x in v]
    return v


async def _learned_state(db, contact_id: str) -> dict:
    """What Jessi recently learned (chip) + detail changes waiting for the rep's OK."""
    if not ObjectId.is_valid(contact_id):
        return {"last_learned": None, "suggestions": []}
    c = await db.contacts.find_one({"_id": ObjectId(contact_id)}, {"conv_intel_last": 1, "detail_suggestions": 1}) or {}
    return {"last_learned": _jsonable(c.get("conv_intel_last")), "suggestions": _jsonable(c.get("detail_suggestions") or [])}


class SuggestionDecision(BaseModel):
    action: str  # accept | reject


@router.post("/{user_id}/{contact_id}/suggestions/{suggestion_id}")
async def decide_suggestion(user_id: str, contact_id: str, suggestion_id: str, body: SuggestionDecision):
    """Rep confirms a detail change spotted in texts/calls (accept) or keeps the saved value (reject)."""
    if body.action not in ("accept", "reject"):
        raise HTTPException(status_code=400, detail="action must be accept or reject")
    from services.voice_intel import resolve_detail_suggestion
    res = await resolve_detail_suggestion(user_id, contact_id, suggestion_id, body.action == "accept")
    if not res.get("ok"):
        raise HTTPException(status_code=404, detail=res.get("error", "Not found"))
    return {"success": True, "accepted": res["accepted"], "field": res["field"], "value": res["value"],
            "suggestions": _jsonable(res["remaining"])}


def _to_utc_dt(v):
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    if isinstance(v, str):
        try:
            d = datetime.fromisoformat(v.replace('Z', '+00:00'))
            return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        except Exception:
            return None
    return None


async def _latest_activity(db, contact_id: str):
    """Newest timestamp across texts (any conversation), events, voice notes and recorded calls."""
    candidates = []
    m = await db.messages.aggregate([
        {"$match": {**(await _message_match(db, contact_id)), "sender": {"$ne": "ai_draft"}}},
        {"$addFields": {"_ts": {"$ifNull": ["$timestamp", "$created_at"]}}},
        {"$sort": {"_ts": -1}}, {"$limit": 1}, {"$project": {"_ts": 1}},
    ]).to_list(1)
    if m:
        candidates.append(_to_utc_dt(m[0].get("_ts")))
    # AI's own extraction events don't count as new customer activity
    e = await db.contact_events.find({"contact_id": contact_id, "event_type": {"$nin": ["intelligence_extracted", "detail_confirmed", "detail_kept"]}},
                                     {"timestamp": 1}).sort("timestamp", -1).limit(1).to_list(1)
    if e:
        candidates.append(_to_utc_dt(e[0].get("timestamp")))
    v = await db.voice_notes.find({"contact_id": contact_id}, {"created_at": 1}).sort("created_at", -1).limit(1).to_list(1)
    if v:
        candidates.append(_to_utc_dt(v[0].get("created_at")))
    c = await db.call_logs.find({"contact_id": contact_id}, {"created_at": 1}).sort("created_at", -1).limit(1).to_list(1)
    if c:
        candidates.append(_to_utc_dt(c[0].get("created_at")))
    candidates = [c for c in candidates if c]
    return max(candidates) if candidates else None


@router.get("/{user_id}/{contact_id}")
async def get_cached_intel(user_id: str, contact_id: str):
    """Get the cached AI summary for a contact, plus a stale flag when newer activity exists."""
    db = get_db()
    doc = await db.contact_intel.find_one(
        {"contact_id": contact_id, "user_id": user_id},
        {"_id": 0}
    )
    latest = await _latest_activity(db, contact_id)
    learned = await _learned_state(db, contact_id)
    if not doc:
        return {"summary": None, "generated_at": None, "stale": latest is not None, **learned}

    gen = _to_utc_dt(doc.get("generated_at"))
    stale = bool(latest and gen and latest > gen)
    return {
        "summary": doc.get("summary"),
        "contact_name": doc.get("contact_name"),
        "generated_at": doc["generated_at"].isoformat() if doc.get("generated_at") else None,
        "data_points": doc.get("data_points", {}),
        "stale": stale,
        **learned,
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

        # Post-process: em-dashes, banned words, business-number guard
        from utils.text_sanitize import clean_ai_text
        clean = await clean_ai_text(suggestion.strip().strip('"').strip("'"), user_id)

        return {
            "suggestion": clean,
            "intent": intent,
            "contact_name": name,
        }

    except Exception as e:
        logger.error(f"AI message suggestion failed: {e}")
        raise HTTPException(status_code=500, detail=f"AI suggestion failed: {str(e)}")
