"""
AI Campaign Engine  - Powers intelligent, personalized campaign messaging.
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
from utils.text_sanitize import no_em_dash, clean_ai_text

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ai-campaigns", tags=["AI Campaigns"])

# =====================================================
# DEFAULT AI CLONE PROMPT (genericized from user input)
# =====================================================
DEFAULT_CLONE_PROMPT = """Persona:
You ARE {user_name}. Every message comes from {user_name} directly — the customer believes they are texting them personally.

Who {user_name} Is:
{user_bio}

Your Only Job — Keep the Relationship Warm:
You are a bridge, not a salesperson. Your job is simple:
1. Respond warmly and naturally to what the customer said.
2. If the conversation needs a nudge, ask ONE light question — never about something already covered.
3. Know when to stay quiet. A short "sounds good!" is often better than another question.
Keep responses SHORT — 1 to 2 sentences. If you can say it in fewer words, do.

The Right Energy:
- Like texting a friend you genuinely like
- Casual, warm, zero pressure
- Interested in THEM as a person — not just the transaction
- When they share something personal, acknowledge it before anything else
- Do not use the em dash (—) anywhere. Use a comma or a normal hyphen if needed.

Context about {store_name}:
{store_info}

CRITICAL — First Person, Always:
- You ARE {user_name}. Speak as "I" always.
- NEVER: "I'll have Forest check" / "my guy" / "my team" / third-person anything.
- RIGHT: "I'll check on that" / "Let me look into it."

YOU ARE NOT AN AI — NEVER REVEAL THIS:
- You are {user_name}. Period. You are a real person texting from their phone.
- NEVER say: "robot", "AI", "bot", "virtual assistant", "automated", "algorithm", "chatbot", "language model", or anything that suggests you are not a real human.
- NEVER say things like "before the robot started talking" or "I should have warned you."
- If a customer asks "are you a robot?" or "is this AI?" — respond naturally and warmly: "Ha, no this is actually me, just behind on texts! What's going on?" Then flag the rep.
- If a customer says anything hinting they suspect automation — play along as {user_name} would, stay warm, and immediately alert the rep that they should take over personally.
- The illusion must always be maintained. You ARE {user_name}.

MEMORY — Never Repeat Yourself:
- Read the full conversation before replying.
- If the customer already told you their budget, model preference, timeline, or anything else — DO NOT ask about it again. Not once. Ever.
- If you already asked a question and got an answer, move on. Do not circle back.
- The customer in the screenshot said "you keep repeating $10-15k range." Never be that VA.

ONE QUESTION MAX:
- If you ask a question, ask only one. Then stop.
- If the last message you sent also had a question, do NOT ask another one. Acknowledge their answer first.
- No follow-up qualifying questions after the customer has already answered something.

When to Stop Asking:
- If you have asked 2+ questions in a row with no natural back-and-forth, switch to warmth mode.
- A reply like "Sounds great, I'll let Forest know!" or "Appreciate you, talk soon!" is perfectly fine and often better.

HARD RULES — Never Break:
1. INVENTORY: You don't have live inventory. Say: "I'll check on that and get back to you."
2. PRICING: You don't know current prices. Say: "Let me get you the exact numbers."
3. APPOINTMENTS: You can't book them. Say: "I'll reach out to lock in a time."
4. COMMITMENTS: Don't commit to anything requiring specific knowledge you don't have.
5. ESCALATE WARMLY: "Great question, let me check on that and get back to you."
6. NO SALES PRESSURE: Never push, never close, never rush. The rep does that."""


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

    # Core bio / background
    if persona.get("bio"):
        bio_parts.append(persona["bio"])
    if persona.get("years_experience"):
        bio_parts.append(f"Experience: {persona['years_experience']} years in the industry")
    if persona.get("hometown"):
        bio_parts.append(f"From: {persona['hometown']}")

    # Personality / Voice
    if persona.get("tone"):
        tone = persona["tone"]
        tone_str = ', '.join(tone) if isinstance(tone, list) else str(tone)
        bio_parts.append(f"Communication style: {tone_str}")
    if persona.get("specialties"):
        specs = persona["specialties"] if isinstance(persona["specialties"], list) else [persona["specialties"]]
        bio_parts.append(f"Specialties: {', '.join(str(s) for s in specs)}")
    if persona.get("hobbies"):
        hobbies = persona["hobbies"] if isinstance(persona["hobbies"], list) else [persona["hobbies"]]
        bio_parts.append(f"Interests/hobbies: {', '.join(str(h) for h in hobbies)}")
    if persona.get("family_info"):
        bio_parts.append(f"Family: {persona['family_info']}")
    if persona.get("fun_facts"):
        facts = persona["fun_facts"] if isinstance(persona["fun_facts"], list) else [persona["fun_facts"]]
        bio_parts.append(f"Fun facts: {', '.join(str(f) for f in facts)}")
    if persona.get("personal_motto"):
        bio_parts.append(f"Personal motto: {persona['personal_motto']}")
    if persona.get("ideal_customer"):
        bio_parts.append(f"Ideal customer: {persona['ideal_customer']}")

    # Hard rules from profile
    never_say_parts = []
    if persona.get("never_say"):
        ns = persona["never_say"] if isinstance(persona["never_say"], list) else [persona["never_say"]]
        never_say_parts = [str(x) for x in ns if x]
    # Note: custom_phrases intentionally removed — listing phrases causes AI to overuse them.
    # Tone is captured in the bio/style description instead.

    user_bio = "\n".join(bio_parts) if bio_parts else f"{user_name} is a dedicated sales professional."

    # Get store info
    store_id = user.get("store_id")
    store_info = ""
    store_name = "the dealership"
    if store_id:
        try:
            store = await db.stores.find_one({"_id": ObjectId(store_id)})
            if store:
                store_name = store.get("name", "the dealership")
                store_info = f"Store: {store_name}"
                if store.get("address"):
                    store_info += f", located at {store['address']}"
                if store.get("phone"):
                    store_info += f". Store phone: {store['phone']}"
        except Exception:
            pass

    # Hydrate the template
    prompt = template.replace("{user_name}", user_name)
    prompt = prompt.replace("{user_bio}", user_bio)
    prompt = prompt.replace("{store_name}", store_name)
    prompt = prompt.replace("{store_info}", store_info)

    # Append hard behavioral rules to the end of the prompt
    if never_say_parts:
        prompt += f"\n\nNEVER say or write these phrases: {', '.join(never_say_parts)}"

    # Contact-info rule: the dedicated business line is the ONLY number a customer ever gets
    business_number = user.get("twilio_number") or user.get("mvpline_number")
    if business_number:
        from utils.text_sanitize import format_phone_display
        prompt += (
            f"\n\nPHONE NUMBER RULE: Your work number is {format_phone_display(business_number)}. "
            f"If you ever tell the customer how to call or text you, give ONLY that number. "
            f"Never share any other phone number, even if one appears earlier in the conversation."
        )

    return prompt


async def get_contact_context(user_id: str, contact_id: str) -> str:
    """Build a rich context summary using the Relationship Intelligence engine."""
    try:
        from services.relationship_intel import build_relationship_brief
        brief = await build_relationship_brief(user_id, contact_id)
        return brief.get("ai_context", "No contact information available.")
    except Exception as e:
        logger.warning(f"Relationship intel failed, falling back to basic context: {e}")
        # Fallback to basic context
        db = get_db()
        contact = await db.contacts.find_one({"_id": ObjectId(contact_id)})
        if not contact:
            return "No contact information available."
        name = f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip()
        parts = [f"Customer name: {name}"]
        if contact.get("tags"):
            parts.append(f"Tags: {', '.join(contact['tags'])}")
        if contact.get("notes"):
            parts.append(f"Notes: {contact['notes'][:300]}")
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
{f'Use this template as inspiration but make it PERSONAL using the relationship intel below: {template_hint}' if template_hint else 'Create a fresh, personalized message.'}

{format_hint}

CRITICAL RULES:
- This message must feel like it was written by a real human who KNOWS this customer
- Reference specific things from the relationship intelligence (engagement, milestones, previous conversations)
- DO NOT repeat anything from previous campaign messages listed below
- Build on the relationship narrative — this is the next chapter, not a standalone message
- If the customer has been engaging (viewing cards, clicking links), subtly acknowledge their interest
- If the relationship is cooling, be warmer and more personal to re-engage
- Match the tone to the relationship health: strong = casual/friendly, cooling = warmer/more effort

{contact_context}

Write ONLY the message text. No quotes, no explanation. Make it sound like it's coming from me personally — someone who genuinely cares about this customer."""

    emergent_key = os.environ.get("EMERGENT_LLM_KEY", "")
    if not emergent_key:
        raise HTTPException(status_code=500, detail="AI service not configured")

    try:
        chat = LlmChat(
            api_key=emergent_key,
            session_id=f"campaign-gen-{user_id}-{contact_id}",
            system_message=system_prompt,
        ).with_model("openai", "gpt-5.2")
        response = await chat.send_message(UserMessage(text=user_prompt))
        generated = await clean_ai_text(response.strip().strip('"').strip("'"), user_id)
        return {"success": True, "message": generated, "channel": channel}
    except Exception as e:
        logger.error(f"AI message generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"AI generation failed: {str(e)}")


# =====================================================
# AI VIRTUAL ASSISTANT  - Reply Handler
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
            session_id=f"campaign-reply-{user_id}-{contact_id}",
            system_message=system_prompt,
        ).with_model("openai", "gpt-5.2")
        response = await chat.send_message(UserMessage(text=user_prompt))
        generated = await clean_ai_text(response.strip().strip('"').strip("'"), user_id)

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
# AI PREVIEW  - Test AI clone for a user
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
            session_id=f"clone-preview-{user_id}",
            system_message=system_prompt,
        ).with_model("openai", "gpt-5.2")
        response = await chat.send_message(UserMessage(text=test_message))
        return {"success": True, "response": await clean_ai_text(response.strip(), user_id)}
    except Exception as e:
        logger.error(f"AI preview failed: {e}")
        raise HTTPException(status_code=500, detail=f"Preview failed: {str(e)}")
