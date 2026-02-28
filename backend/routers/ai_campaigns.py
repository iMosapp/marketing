"""
AI Campaign Engine — Powers intelligent, personalized campaign messaging.
- AI Clone Prompt management (global + per-user)
- AI message generation using contact activity context
- Campaign AI reply handling (virtual assistant)
"""
import os
import random
import logging
from datetime import datetime, timezone
from typing import Optional
from bson import ObjectId
from fastapi import APIRouter, HTTPException

from routers.database import get_db, get_user_by_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ai-campaigns", tags=["AI Campaigns"])

# =====================================================
# DEFAULT AI CLONE PROMPT (genericized from user input)
# =====================================================
DEFAULT_CLONE_PROMPT = """Persona:
You are {user_name}'s Virtual Assistant. You know {user_name} personally and reflect their style, background, expertise, and personality. You never act generic - you respond the way {user_name} would, with confidence, warmth, directness, and a supportive tone.

Who {user_name} Is:
{user_bio}

Your Core Goals:
1. Represent {user_name} professionally but with their signature edge.
2. Be helpful, likable, and informative while keeping a forward-thinking, optimistic vibe.
3. Answer questions about {user_name}'s services, programs, or expertise with accuracy.
4. Whenever appropriate, guide people toward scheduling a call or learning more.
5. Keep responses clear, conversational, and confidently delivered.

Tone & Style:
- Professional + slightly sarcastic
- Friendly, warm, and encouraging
- Informative first, opinionated second
- No fluff, no corporate cliches
- Straightforward, confident, and human
- Keep responses as short as possible
- Respond to the customer as if you're speaking for {user_name}, not an AI

Behavior Rules:
- Never make promises {user_name} wouldn't make.
- Never overhype or exaggerate.
- Don't invent capabilities or false details.
- Keep explanations easy to follow and real-world practical.
- When scheduling is needed, offer to set up a time or provide a link.
- Do not use the em dash (-) in any response. If you need separation, use a comma or a normal hyphen (-) instead.

Context about {store_name}:
{store_info}

Never Say:
- That you're "just an AI."
- That the customer should check with the real {user_name}. You are their assistant and responding on their behalf.
- Long apologies.
- Robotic phrases."""


# =====================================================
# AI CLONE PROMPT MANAGEMENT
# =====================================================

@router.get("/clone-prompt/global")
async def get_global_clone_prompt():
    """Get the global default AI clone prompt template."""
    db = get_db()
    prompt_doc = await db.ai_clone_prompts.find_one({"scope": "global"})
    if prompt_doc:
        prompt_doc["_id"] = str(prompt_doc["_id"])
        return prompt_doc
    return {"scope": "global", "prompt": DEFAULT_CLONE_PROMPT, "is_default": True}


@router.put("/clone-prompt/global")
async def update_global_clone_prompt(data: dict):
    """Update the global AI clone prompt template (admin only)."""
    db = get_db()
    prompt_text = data.get("prompt", "").strip()
    if not prompt_text:
        raise HTTPException(status_code=400, detail="Prompt text is required")

    result = await db.ai_clone_prompts.update_one(
        {"scope": "global"},
        {"$set": {
            "scope": "global",
            "prompt": prompt_text,
            "updated_at": datetime.now(timezone.utc),
        }},
        upsert=True,
    )
    return {"success": True, "message": "Global prompt updated"}


@router.get("/clone-prompt/user/{user_id}")
async def get_user_clone_prompt(user_id: str):
    """Get a user's personal AI clone prompt override (falls back to global)."""
    db = get_db()
    user_prompt = await db.ai_clone_prompts.find_one({"scope": "user", "user_id": user_id})
    if user_prompt:
        user_prompt["_id"] = str(user_prompt["_id"])
        return user_prompt

    # Fall back to global
    global_prompt = await db.ai_clone_prompts.find_one({"scope": "global"})
    if global_prompt:
        global_prompt["_id"] = str(global_prompt["_id"])
        global_prompt["is_fallback"] = True
        return global_prompt

    return {"scope": "global", "prompt": DEFAULT_CLONE_PROMPT, "is_default": True, "is_fallback": True}


@router.put("/clone-prompt/user/{user_id}")
async def update_user_clone_prompt(user_id: str, data: dict):
    """Update a user's personal AI clone prompt override."""
    db = get_db()
    prompt_text = data.get("prompt", "").strip()
    if not prompt_text:
        raise HTTPException(status_code=400, detail="Prompt text is required")

    await db.ai_clone_prompts.update_one(
        {"scope": "user", "user_id": user_id},
        {"$set": {
            "scope": "user",
            "user_id": user_id,
            "prompt": prompt_text,
            "updated_at": datetime.now(timezone.utc),
        }},
        upsert=True,
    )
    return {"success": True, "message": "Personal prompt updated"}


@router.delete("/clone-prompt/user/{user_id}")
async def reset_user_clone_prompt(user_id: str):
    """Reset user's prompt to use the global default."""
    db = get_db()
    await db.ai_clone_prompts.delete_one({"scope": "user", "user_id": user_id})
    return {"success": True, "message": "Reset to global default"}


# =====================================================
# AI MESSAGE GENERATION
# =====================================================

async def build_clone_system_prompt(user_id: str) -> str:
    """Build the fully hydrated system prompt for a user's AI clone."""
    db = get_db()

    # Get the prompt template
    user_prompt = await db.ai_clone_prompts.find_one({"scope": "user", "user_id": user_id})
    if user_prompt:
        template = user_prompt["prompt"]
    else:
        global_prompt = await db.ai_clone_prompts.find_one({"scope": "global"})
        template = (global_prompt or {}).get("prompt", DEFAULT_CLONE_PROMPT)

    # Get user profile data
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        return template

    persona = user.get("persona", {})
    user_name = user.get("name", "the salesperson")
    bio_parts = []
    if persona.get("bio"):
        bio_parts.append(persona["bio"])
    if persona.get("hobbies"):
        hobbies = persona["hobbies"] if isinstance(persona["hobbies"], list) else [persona["hobbies"]]
        bio_parts.append(f"Hobbies: {', '.join(hobbies)}")
    if persona.get("family_info"):
        bio_parts.append(f"Family: {persona['family_info']}")
    if persona.get("hometown"):
        bio_parts.append(f"From: {persona['hometown']}")
    if persona.get("years_experience"):
        bio_parts.append(f"Experience: {persona['years_experience']} years")
    if persona.get("fun_facts"):
        facts = persona["fun_facts"] if isinstance(persona["fun_facts"], list) else [persona["fun_facts"]]
        bio_parts.append(f"Fun facts: {', '.join(facts)}")

    user_bio = "\n".join(bio_parts) if bio_parts else f"{user_name} is a dedicated sales professional."

    # Get store info
    store_id = user.get("store_id")
    store_info = ""
    store_name = "the dealership"
    if store_id:
        store = await db.stores.find_one({"_id": ObjectId(store_id)})
        if store:
            store_name = store.get("name", "the dealership")
            store_info = f"Store: {store_name}"
            if store.get("address"):
                store_info += f", located at {store['address']}"

    # Hydrate the template
    prompt = template.replace("{user_name}", user_name)
    prompt = prompt.replace("{user_bio}", user_bio)
    prompt = prompt.replace("{store_name}", store_name)
    prompt = prompt.replace("{store_info}", store_info)

    return prompt


async def get_contact_context(user_id: str, contact_id: str) -> str:
    """Build a context summary of the contact's history for AI message generation."""
    db = get_db()

    contact = await db.contacts.find_one({"_id": ObjectId(contact_id)})
    if not contact:
        return "No contact information available."

    first_name = contact.get("first_name", "")
    last_name = contact.get("last_name", "")
    name = f"{first_name} {last_name}".strip() or "the customer"

    parts = [f"Customer name: {name}"]

    if contact.get("phone"):
        parts.append(f"Phone: {contact['phone']}")
    if contact.get("email"):
        parts.append(f"Email: {contact['email']}")
    if contact.get("tags"):
        parts.append(f"Tags: {', '.join(contact['tags'])}")
    if contact.get("notes"):
        parts.append(f"Notes: {contact['notes'][:300]}")
    if contact.get("vehicle_interest"):
        parts.append(f"Vehicle interest: {contact['vehicle_interest']}")
    if contact.get("date_sold"):
        parts.append(f"Sold date: {contact['date_sold']}")

    # Recent activity (last 10 events)
    events = await db.contact_events.find(
        {"contact_id": contact_id, "user_id": user_id}
    ).sort("timestamp", -1).limit(10).to_list(10)

    if events:
        parts.append("\nRecent activity:")
        for ev in events:
            ev_type = ev.get("event_type", "").replace("_", " ").title()
            desc = ev.get("description", "")
            ts = ev.get("timestamp")
            ts_str = ts.strftime("%b %d") if isinstance(ts, datetime) else ""
            parts.append(f"- {ts_str}: {ev_type}{': ' + desc[:100] if desc else ''}")

    # Recent messages (last 5)
    messages = await db.messages.find(
        {"contact_id": contact_id}
    ).sort("timestamp", -1).limit(5).to_list(5)

    if messages:
        parts.append("\nRecent messages:")
        for msg in messages:
            sender = "Me" if msg.get("sender") == "user" else name
            content = msg.get("content", "")[:150]
            parts.append(f"- {sender}: {content}")

    return "\n".join(parts)


@router.post("/generate-message/{user_id}/{contact_id}")
async def generate_campaign_message(user_id: str, contact_id: str, data: dict):
    """
    Generate an AI-powered campaign message for a contact.
    Uses the user's AI clone personality and contact's activity history.
    """
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    import uuid

    db = get_db()
    step_context = data.get("step_context", "")
    channel = data.get("channel", "sms")
    campaign_name = data.get("campaign_name", "")
    template_hint = data.get("template_hint", "")

    # Build system prompt with AI clone personality
    system_prompt = await build_clone_system_prompt(user_id)

    # Build contact context
    contact_context = await get_contact_context(user_id, contact_id)

    # Build the generation request
    if channel == "email":
        format_hint = "Write a short, professional email. Include a subject line on the first line prefixed with 'Subject: '."
    else:
        format_hint = "Write a short SMS text message. Keep it under 160 characters if possible. Be conversational and personal."

    user_prompt = f"""Generate a {channel} message for this campaign step.

Campaign: {campaign_name}
Step context: {step_context}
{f'Use this template as a starting point but personalize it: {template_hint}' if template_hint else 'Create a fresh, personalized message.'}

{format_hint}

Customer context:
{contact_context}

Write ONLY the message text. No quotes, no explanation. Make it sound like it's coming from me personally."""

    emergent_key = os.environ.get("EMERGENT_LLM_KEY", "")
    if not emergent_key:
        raise HTTPException(status_code=500, detail="AI service not configured")

    try:
        chat = LlmChat(
            api_key=emergent_key,
            model="gpt-5.2",
            session_id=f"campaign-gen-{user_id}-{uuid.uuid4()}",
            system_message=system_prompt,
        )
        response = await chat.send_message_async(UserMessage(content=user_prompt))
        generated = response.strip().strip('"').strip("'")
        return {"success": True, "message": generated, "channel": channel}
    except Exception as e:
        logger.error(f"AI message generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"AI generation failed: {str(e)}")


# =====================================================
# AI VIRTUAL ASSISTANT — Reply Handler
# =====================================================

@router.post("/handle-reply/{user_id}/{contact_id}")
async def handle_customer_reply(user_id: str, contact_id: str, data: dict):
    """
    Handle an inbound customer reply during an automated campaign.
    The AI clone responds with a 1-3 minute simulated delay.
    Returns the generated reply (actual sending is handled by the scheduler/caller).
    """
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    import uuid

    db = get_db()
    customer_message = data.get("message", "")
    conversation_id = data.get("conversation_id", "")

    if not customer_message:
        raise HTTPException(status_code=400, detail="Message is required")

    # Build system prompt with AI clone personality
    system_prompt = await build_clone_system_prompt(user_id)
    system_prompt += "\n\nIMPORTANT: You are responding to a customer who replied to a message from you. Keep it natural, short, and conversational. Act exactly like the salesperson would."

    # Build context
    contact_context = await get_contact_context(user_id, contact_id)

    # Get recent conversation for context
    recent_messages = []
    if conversation_id:
        msgs = await db.messages.find(
            {"conversation_id": conversation_id}
        ).sort("timestamp", -1).limit(10).to_list(10)
        msgs.reverse()
        for m in msgs:
            role = "assistant" if m.get("sender") == "user" else "user"
            recent_messages.append(f"{'Me' if role == 'assistant' else 'Customer'}: {m.get('content', '')[:200]}")

    conversation_str = "\n".join(recent_messages) if recent_messages else ""

    user_prompt = f"""A customer just replied to my message. Generate my response.

Customer context:
{contact_context}

{f'Recent conversation:{chr(10)}{conversation_str}' if conversation_str else ''}

Customer just said: "{customer_message}"

Reply naturally and briefly as me. Just the reply text, nothing else."""

    emergent_key = os.environ.get("EMERGENT_LLM_KEY", "")
    if not emergent_key:
        raise HTTPException(status_code=500, detail="AI service not configured")

    try:
        chat = LlmChat(
            api_key=emergent_key,
            model="gpt-5.2",
            session_id=f"campaign-reply-{user_id}-{contact_id}-{uuid.uuid4()}",
            system_message=system_prompt,
        )
        response = await chat.send_message_async(UserMessage(content=user_prompt))
        generated = response.strip().strip('"').strip("'")

        # Random delay 1-3 minutes (returned as metadata, not actually delayed here)
        delay_seconds = random.randint(60, 180)

        return {
            "success": True,
            "reply": generated,
            "delay_seconds": delay_seconds,
            "note": "Caller should wait delay_seconds before sending to simulate human timing.",
        }
    except Exception as e:
        logger.error(f"AI reply generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"AI reply failed: {str(e)}")


# =====================================================
# AI PREVIEW — Test AI clone for a user
# =====================================================

@router.post("/preview-clone/{user_id}")
async def preview_ai_clone(user_id: str, data: dict):
    """Preview what the AI clone would say in response to a test message."""
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    import uuid

    test_message = data.get("message", "Tell me about yourself")

    system_prompt = await build_clone_system_prompt(user_id)
    emergent_key = os.environ.get("EMERGENT_LLM_KEY", "")
    if not emergent_key:
        raise HTTPException(status_code=500, detail="AI service not configured")

    try:
        chat = LlmChat(
            api_key=emergent_key,
            model="gpt-5.2",
            session_id=f"clone-preview-{user_id}-{uuid.uuid4()}",
            system_message=system_prompt,
        )
        response = await chat.send_message_async(UserMessage(content=test_message))
        return {"success": True, "response": response.strip()}
    except Exception as e:
        logger.error(f"AI preview failed: {e}")
        raise HTTPException(status_code=500, detail=f"Preview failed: {str(e)}")
