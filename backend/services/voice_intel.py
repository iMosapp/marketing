"""
Voice Memo Intelligence Extraction
Automatically analyzes voice note transcripts to extract personal details
about the customer: spouse name, kids, interests, vehicle info, etc.
Saves structured data to the contact's personal_details field.
"""
import os
import json
import logging
from datetime import datetime, timezone

from emergentintegrations.llm.chat import LlmChat, UserMessage
from routers.database import get_db
from bson import ObjectId

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """You are a CRM data extraction expert. Analyze this voice memo transcript from an automotive salesperson about their customer. Extract any personal details mentioned.

## Rules:
- Only extract information that is EXPLICITLY mentioned in the transcript
- Do NOT guess or fabricate any details
- If a field is not mentioned, set it to null
- For arrays (kids, interests, important_dates), return empty array if not mentioned
- For kids, include name and any details mentioned (age, school, etc.)
- For interests, include hobbies, sports teams, activities, etc.
- For important_dates, include any dates mentioned with what they're for
- vehicle_details should capture specifics: model, color, trim, features they liked

## Respond in EXACTLY this JSON format:
{
  "spouse_name": "string or null",
  "spouse_details": "any details about spouse, job, etc. or null",
  "kids": [{"name": "string", "details": "age, school, etc."}],
  "interests": ["hobby1", "hobby2"],
  "occupation": "string or null",
  "employer": "string or null",
  "vehicle_purchased": "year make model trim or null",
  "vehicle_color": "string or null",
  "vehicle_details": "specific features, packages, why they chose it, or null",
  "trade_in": "what they traded in or null",
  "purchase_context": "why they bought, what drove the decision, or null",
  "important_dates": [{"date": "string", "description": "what it's for"}],
  "pets": "string or null",
  "favorite_restaurant": "string or null",
  "neighborhood": "where they live or null",
  "referral_potential": "any mention of friends/family who might buy or null",
  "personal_notes": "any other personal tidbits worth remembering or null",
  "communication_preference": "how they prefer to be contacted or null"
}

Respond ONLY with valid JSON."""


async def extract_personal_details(transcript: str) -> dict:
    """Use AI to extract personal details from a voice memo transcript."""
    api_key = os.getenv("EMERGENT_LLM_KEY")
    if not api_key:
        logger.warning("No EMERGENT_LLM_KEY - skipping extraction")
        return {}

    if not transcript or len(transcript.strip()) < 10:
        return {}

    import secrets
    session_id = f"extract_{secrets.token_hex(6)}"

    chat = LlmChat(
        api_key=api_key,
        session_id=session_id,
        system_message=EXTRACTION_PROMPT,
    ).with_model("openai", "gpt-5.2")

    try:
        response = await chat.send_message(
            UserMessage(text=f"Voice memo transcript:\n\n{transcript}")
        )

        # Parse JSON
        cleaned = response.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
        if cleaned.startswith("json"):
            cleaned = cleaned[4:].strip()

        extracted = json.loads(cleaned)

        # Clean nulls — only keep fields with actual values
        result = {}
        for key, value in extracted.items():
            if value is None:
                continue
            if isinstance(value, list) and len(value) == 0:
                continue
            if isinstance(value, str) and not value.strip():
                continue
            result[key] = value

        return result

    except (json.JSONDecodeError, Exception) as e:
        logger.error(f"Voice memo extraction failed: {e}")
        return {}


async def merge_personal_details(contact_id: str, new_details: dict):
    """Merge newly extracted details into the contact's personal_details field.
    Existing values are preserved — new data supplements, doesn't overwrite.
    """
    if not new_details:
        return

    db = get_db()
    contact = await db.contacts.find_one(
        {"_id": ObjectId(contact_id)},
        {"personal_details": 1}
    )
    existing = (contact or {}).get("personal_details", {})

    merged = {**existing}

    for key, value in new_details.items():
        if key not in merged or not merged[key]:
            # No existing value — use new
            merged[key] = value
        elif isinstance(value, list) and isinstance(merged.get(key), list):
            # Merge lists (dedup by checking stringified items)
            existing_strs = {json.dumps(item, sort_keys=True) if isinstance(item, dict) else str(item) for item in merged[key]}
            for item in value:
                item_str = json.dumps(item, sort_keys=True) if isinstance(item, dict) else str(item)
                if item_str not in existing_strs:
                    merged[key].append(item)
        # If existing has a value and new has a value for a string field, keep existing
        # (user's explicit edits should not be overwritten by AI)

    # Save merged details and update key contact fields
    update_fields = {"personal_details": merged, "updated_at": datetime.now(timezone.utc)}

    # Also update top-level contact fields if they're empty
    if new_details.get("vehicle_purchased"):
        existing_vehicle = (contact or {}).get("vehicle", "") or ""
        if not existing_vehicle:
            update_fields["vehicle"] = new_details["vehicle_purchased"]

    await db.contacts.update_one(
        {"_id": ObjectId(contact_id)},
        {"$set": update_fields}
    )

    logger.info(f"Personal details merged for contact {contact_id}: {list(new_details.keys())}")
    return merged


async def process_voice_note_intelligence(user_id: str, contact_id: str, transcript: str, voice_note_id: str):
    """Full pipeline: extract details from transcript and merge into contact."""
    if not transcript or len(transcript.strip()) < 10:
        return

    logger.info(f"Extracting intelligence from voice note {voice_note_id} for contact {contact_id}")

    # Extract details
    details = await extract_personal_details(transcript)
    if not details:
        logger.info(f"No personal details extracted from voice note {voice_note_id}")
        return

    # Merge into contact
    await merge_personal_details(contact_id, details)

    # Update the voice note record with extraction status
    db = get_db()
    await db.voice_notes.update_one(
        {"_id": ObjectId(voice_note_id)},
        {"$set": {
            "intelligence_extracted": True,
            "extracted_fields": list(details.keys()),
            "extracted_at": datetime.now(timezone.utc),
        }}
    )

    # Log as contact event
    field_names = ", ".join(details.keys())
    await db.contact_events.insert_one({
        "event_type": "intelligence_extracted",
        "title": "Personal Details Extracted",
        "description": f"AI extracted: {field_names}",
        "contact_id": contact_id,
        "user_id": user_id,
        "channel": "ai",
        "category": "intelligence",
        "icon": "sparkles",
        "color": "#AF52DE",
        "content": json.dumps(details),
        "metadata": {"voice_note_id": voice_note_id, "fields": list(details.keys())},
        "timestamp": datetime.now(timezone.utc),
        "created_at": datetime.now(timezone.utc),
    })

    logger.info(f"Intelligence extracted from voice note {voice_note_id}: {field_names}")
    return details
