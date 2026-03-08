"""
AI-Powered Outreach Service
When a 'sold' tag is applied to a contact, gathers context about the customer
relationship and generates 2 personalized follow-up message suggestions using AI.
Creates scheduled tasks for the salesperson's next morning.
"""
import os
import logging
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional
from bson import ObjectId

from emergentintegrations.llm.chat import LlmChat, UserMessage
from routers.database import get_db

logger = logging.getLogger(__name__)

OUTREACH_SYSTEM_PROMPT = """You are an expert automotive sales follow-up coach. Your job is to write personalized follow-up messages that a salesperson can send to a customer who just purchased a vehicle.

## Rules:
- Write SHORT, warm, conversational text messages (2-3 sentences max)
- Use the customer's first name
- Reference specific details about their purchase or relationship when available
- Sound natural — like a real person texting, not a corporate template
- Include a subtle call to action (e.g., asking how they're enjoying the car, inviting them to leave a review, or offering to help with anything)
- Do NOT use emojis excessively — 1 max per message, or none
- Do NOT be pushy or salesy — the sale is already done, this is relationship building
- Make each suggestion distinctly different in tone/approach

## You must respond in EXACTLY this JSON format:
{
  "suggestions": [
    {
      "message": "the follow-up text message",
      "approach": "brief 3-5 word description of the approach",
      "best_time_reason": "why this message works well"
    },
    {
      "message": "a different follow-up text message",
      "approach": "brief 3-5 word description of the approach",
      "best_time_reason": "why this message works well"
    }
  ]
}

Respond ONLY with valid JSON. No extra text."""


async def gather_customer_context(user_id: str, contact_id: str) -> dict:
    """Gather all available context about the customer relationship."""
    db = get_db()
    context = {}

    # Get contact details
    try:
        contact = await db.contacts.find_one({"_id": ObjectId(contact_id)})
        if contact:
            context["contact"] = {
                "first_name": contact.get("first_name", ""),
                "last_name": contact.get("last_name", ""),
                "phone": contact.get("phone", ""),
                "email": contact.get("email", ""),
                "tags": contact.get("tags", []),
                "notes": contact.get("notes", ""),
                "vehicle_interest": contact.get("vehicle_interest", ""),
                "vehicle_purchased": contact.get("vehicle_purchased", ""),
                "date_sold": str(contact.get("date_sold", "")) if contact.get("date_sold") else "",
                "lead_source": contact.get("lead_source", ""),
                "created_at": str(contact.get("created_at", "")),
            }
    except Exception as e:
        logger.error(f"Error fetching contact: {e}")

    # Get recent conversation history (last 10 events)
    try:
        events = await db.contact_events.find(
            {"contact_id": contact_id, "user_id": user_id},
            {"_id": 0, "event_type": 1, "title": 1, "content": 1, "timestamp": 1}
        ).sort("timestamp", -1).limit(10).to_list(10)
        context["recent_events"] = [
            {
                "type": e.get("event_type", ""),
                "title": e.get("title", ""),
                "content": (e.get("content", "") or "")[:200],
                "when": str(e.get("timestamp", "")),
            }
            for e in events
        ]
    except Exception as e:
        logger.error(f"Error fetching events: {e}")
        context["recent_events"] = []

    # Get engagement signals (card views, link clicks, etc.)
    try:
        signals = await db.engagement_signals.find(
            {"user_id": user_id, "contact_id": contact_id},
            {"_id": 0, "signal_type": 1, "created_at": 1}
        ).sort("created_at", -1).limit(5).to_list(5)
        context["engagement"] = [
            {"type": s.get("signal_type", ""), "when": str(s.get("created_at", ""))}
            for s in signals
        ]
    except Exception as e:
        logger.error(f"Error fetching signals: {e}")
        context["engagement"] = []

    # Get salesperson info
    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)}, {"name": 1, "store_id": 1})
        if user:
            context["salesperson_name"] = user.get("name", "")
            if user.get("store_id"):
                store = await db.stores.find_one(
                    {"_id": ObjectId(user["store_id"])}, {"name": 1}
                )
                if store:
                    context["dealership_name"] = store.get("name", "")
    except Exception as e:
        logger.error(f"Error fetching user/store: {e}")

    return context


async def generate_suggestions(user_id: str, contact_id: str) -> dict:
    """Generate 2 AI-powered follow-up message suggestions."""
    api_key = os.getenv("EMERGENT_LLM_KEY")
    if not api_key:
        raise ValueError("EMERGENT_LLM_KEY not configured")

    context = await gather_customer_context(user_id, contact_id)
    contact_info = context.get("contact", {})
    first_name = contact_info.get("first_name", "the customer")

    # Build the prompt with all available context
    prompt_parts = [f"Customer: {first_name} {contact_info.get('last_name', '')}"]

    if contact_info.get("vehicle_purchased"):
        prompt_parts.append(f"Vehicle purchased: {contact_info['vehicle_purchased']}")
    elif contact_info.get("vehicle_interest"):
        prompt_parts.append(f"Vehicle of interest: {contact_info['vehicle_interest']}")

    if contact_info.get("date_sold"):
        prompt_parts.append(f"Purchase date: {contact_info['date_sold']}")

    if contact_info.get("lead_source"):
        prompt_parts.append(f"Lead source: {contact_info['lead_source']}")

    if contact_info.get("notes"):
        prompt_parts.append(f"Notes: {contact_info['notes'][:300]}")

    if context.get("recent_events"):
        event_summary = ", ".join(
            [f"{e['type']}" for e in context["recent_events"][:5]]
        )
        prompt_parts.append(f"Recent interactions: {event_summary}")

    if context.get("engagement"):
        eng_summary = ", ".join([e["type"] for e in context["engagement"]])
        prompt_parts.append(f"Customer engagement: {eng_summary}")

    if context.get("salesperson_name"):
        prompt_parts.append(f"Salesperson: {context['salesperson_name']}")

    if context.get("dealership_name"):
        prompt_parts.append(f"Dealership: {context['dealership_name']}")

    full_prompt = "Generate 2 personalized follow-up message suggestions for this recently sold customer:\n\n" + "\n".join(prompt_parts)

    # Call OpenAI
    session_id = f"outreach_{user_id}_{contact_id}_{secrets.token_hex(4)}"
    chat = LlmChat(
        api_key=api_key,
        session_id=session_id,
        system_message=OUTREACH_SYSTEM_PROMPT,
    ).with_model("openai", "gpt-5.2")

    response_text = await chat.send_message(UserMessage(text=full_prompt))

    # Parse JSON response
    import json
    try:
        # Strip markdown code fences if present
        cleaned = response_text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
        if cleaned.startswith("json"):
            cleaned = cleaned[4:].strip()

        result = json.loads(cleaned)
        suggestions = result.get("suggestions", [])
    except (json.JSONDecodeError, KeyError) as e:
        logger.error(f"Failed to parse AI response: {e}\nResponse: {response_text}")
        # Fallback: create a generic suggestion
        suggestions = [
            {
                "message": f"Hey {first_name}! Congrats again on the new ride. Let me know if you need anything at all!",
                "approach": "Simple check-in",
                "best_time_reason": "Warm and personal post-sale follow-up",
            },
            {
                "message": f"Hi {first_name}, hope you're loving the new car! If you have a minute, I'd really appreciate a quick review — it means a lot. Let me know if anything comes up!",
                "approach": "Review request",
                "best_time_reason": "Captures satisfaction while it's fresh",
            },
        ]

    return {
        "suggestions": suggestions[:2],
        "context_used": {
            "has_vehicle": bool(contact_info.get("vehicle_purchased") or contact_info.get("vehicle_interest")),
            "has_events": len(context.get("recent_events", [])) > 0,
            "has_engagement": len(context.get("engagement", [])) > 0,
        },
    }


def get_next_morning(user_timezone: str) -> datetime:
    """Calculate 'next morning' (9 AM) in the user's timezone, returned as UTC."""
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(user_timezone)
    except Exception:
        # Fallback to UTC if timezone is invalid
        tz = timezone.utc

    now_local = datetime.now(tz)

    # Next morning at 9 AM local time
    if now_local.hour < 9:
        # Same day morning
        morning = now_local.replace(hour=9, minute=0, second=0, microsecond=0)
    else:
        # Tomorrow morning
        morning = (now_local + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)

    # Convert to UTC
    return morning.astimezone(timezone.utc)


async def create_outreach_record(user_id: str, contact_id: str, contact_name: str) -> str:
    """
    Generate AI suggestions and store them as an outreach record.
    Returns the record ID.
    """
    db = get_db()
    now = datetime.now(timezone.utc)

    # Check for existing pending suggestion for this contact (dedup)
    existing = await db.ai_outreach.find_one({
        "user_id": user_id,
        "contact_id": contact_id,
        "status": "pending",
    })
    if existing:
        logger.info(f"AI outreach already pending for contact {contact_id}")
        return str(existing["_id"])

    # Generate suggestions
    try:
        result = await generate_suggestions(user_id, contact_id)
        suggestions = result["suggestions"]
    except Exception as e:
        logger.error(f"AI suggestion generation failed: {e}")
        # Use fallback suggestions
        first_name = contact_name.split()[0] if contact_name else "there"
        suggestions = [
            {
                "message": f"Hey {first_name}! Congrats again on the purchase. Let me know if you need anything!",
                "approach": "Simple check-in",
                "best_time_reason": "Post-sale relationship building",
            },
            {
                "message": f"Hi {first_name}, hope you're enjoying everything! If you get a chance, a quick review would mean the world. Here if you need anything!",
                "approach": "Review request",
                "best_time_reason": "Captures satisfaction while fresh",
            },
        ]

    # Get user timezone for scheduling
    user = await db.users.find_one({"_id": ObjectId(user_id)}, {"timezone": 1})
    user_tz = (user or {}).get("timezone", "America/New_York")
    task_due = get_next_morning(user_tz)

    record = {
        "user_id": user_id,
        "contact_id": contact_id,
        "contact_name": contact_name,
        "suggestions": suggestions,
        "status": "pending",  # pending, accepted, dismissed
        "accepted_index": None,
        "task_id": None,
        "scheduled_for": task_due,
        "created_at": now,
        "updated_at": now,
    }

    result = await db.ai_outreach.insert_one(record)
    record_id = str(result.inserted_id)

    # Create a notification for the salesperson
    await db.notifications.insert_one({
        "type": "ai_outreach",
        "user_id": user_id,
        "contact_id": contact_id,
        "contact_name": contact_name,
        "title": f"AI Follow-up Ready: {contact_name}",
        "message": f"We've crafted 2 personalized follow-up messages for {contact_name}. Review and pick one!",
        "icon": "sparkles",
        "color": "#AF52DE",
        "read": False,
        "dismissed": False,
        "created_at": now,
        "link": "/ai-outreach",
    })

    logger.info(f"AI outreach created for {contact_name} (contact={contact_id}, user={user_id})")
    return record_id


async def accept_suggestion(record_id: str, suggestion_index: int) -> dict:
    """Accept a suggestion and create a scheduled task."""
    db = get_db()
    record = await db.ai_outreach.find_one({"_id": ObjectId(record_id)})
    if not record:
        raise ValueError("Outreach record not found")
    if record["status"] != "pending":
        raise ValueError("This suggestion has already been actioned")

    suggestions = record.get("suggestions", [])
    if suggestion_index < 0 or suggestion_index >= len(suggestions):
        raise ValueError("Invalid suggestion index")

    chosen = suggestions[suggestion_index]
    user_id = record["user_id"]
    contact_id = record["contact_id"]
    contact_name = record["contact_name"]
    scheduled_for = record.get("scheduled_for", datetime.now(timezone.utc))

    # Get contact phone
    contact = await db.contacts.find_one({"_id": ObjectId(contact_id)}, {"phone": 1})
    contact_phone = (contact or {}).get("phone", "")

    # Create the task
    task = {
        "user_id": user_id,
        "contact_id": contact_id,
        "contact_name": contact_name,
        "contact_phone": contact_phone,
        "type": "follow_up",
        "source": "ai_outreach",
        "title": f"AI Follow-up: {contact_name}",
        "description": f"AI-suggested follow-up ({chosen.get('approach', 'personalized')}). {chosen.get('best_time_reason', '')}",
        "suggested_message": chosen["message"],
        "action_type": "text",
        "priority": "high",
        "priority_order": 1,
        "status": "pending",
        "completed": False,
        "due_date": scheduled_for,
        "completed_at": None,
        "snoozed_until": None,
        "campaign_id": None,
        "campaign_name": None,
        "pending_send_id": None,
        "channel": "sms",
        "created_at": datetime.now(timezone.utc),
        "idempotency_key": f"ai_outreach_{record_id}",
    }

    task_result = await db.tasks.insert_one(task)
    task_id = str(task_result.inserted_id)

    # Update outreach record
    await db.ai_outreach.update_one(
        {"_id": ObjectId(record_id)},
        {"$set": {
            "status": "accepted",
            "accepted_index": suggestion_index,
            "task_id": task_id,
            "updated_at": datetime.now(timezone.utc),
        }}
    )

    logger.info(f"AI outreach accepted: record={record_id}, task={task_id}")
    return {"task_id": task_id, "scheduled_for": scheduled_for.isoformat()}
