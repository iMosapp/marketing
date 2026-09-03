"""
Voice Memo Intelligence Extraction
Automatically analyzes voice note transcripts to extract personal details
about the customer: spouse name, kids, interests, vehicle info, etc.
Saves structured data to the contact's personal_details field.
"""
import os
import json
import logging
from datetime import datetime, timezone, timedelta

from emergentintegrations.llm.chat import LlmChat, UserMessage
from routers.database import get_db
from bson import ObjectId

logger = logging.getLogger(__name__)

SOURCE_DESCRIPTIONS = {
    "voice_note": "voice memo transcript from a salesperson about their customer",
    "text": "text-message conversation between a salesperson (REP), their AI assistant (AI) and the customer (CUSTOMER). Only extract facts about the CUSTOMER, never about the rep",
    "call": "transcript of a recorded phone call between a salesperson and their customer. Only extract facts about the customer",
}

EXTRACTION_PROMPT = """You are a CRM data extraction expert. Analyze this __SOURCE__. Extract any personal details mentioned.

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


async def extract_personal_details(transcript: str, source: str = "voice_note") -> dict:
    """Use AI to extract personal details from a voice memo, text thread or call transcript."""
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
        system_message=EXTRACTION_PROMPT.replace("__SOURCE__", SOURCE_DESCRIPTIONS.get(source, SOURCE_DESCRIPTIONS["voice_note"])),
    ).with_model("openai", "gpt-5.2")

    label = {"text": "Text conversation", "call": "Call transcript"}.get(source, "Voice memo transcript")
    try:
        response = await chat.send_message(
            UserMessage(text=f"{label}:\n\n{transcript}")
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
        if isinstance(value, list) and isinstance(merged.get(key), list):
            # Merge lists (dedup by checking stringified items)
            existing_strs = {json.dumps(item, sort_keys=True) if isinstance(item, dict) else str(item) for item in merged[key]}
            for item in value:
                item_str = json.dumps(item, sort_keys=True) if isinstance(item, dict) else str(item)
                if item_str not in existing_strs:
                    merged[key].append(item)
        else:
            # Newest info wins — a fresh voice memo is the latest ground truth
            # (new job, spouse name correction, new vehicle, etc.)
            merged[key] = value

    # Save merged details and update key contact fields
    update_fields = {"personal_details": merged, "updated_at": datetime.now(timezone.utc)}

    # Also update top-level contact fields — newest memo wins
    if new_details.get("vehicle_purchased"):
        update_fields["vehicle"] = new_details["vehicle_purchased"]

    if new_details.get("occupation"):
        update_fields["occupation"] = new_details["occupation"]

    if new_details.get("employer"):
        update_fields["employer"] = new_details["employer"]

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

    # Auto-set a follow-up so a captured memory always turns into a next action
    try:
        await _ensure_followup_from_voice(db, user_id, contact_id, details)
    except Exception as e:
        logger.warning(f"[VoiceIntel] follow-up creation failed: {e}")

    return details


async def _ensure_followup_from_voice(db, user_id: str, contact_id: str, details: dict):
    """Create a single follow-up task after a voice note (skips if one is already pending)."""
    existing = await db.tasks.find_one({
        "user_id": user_id,
        "contact_id": contact_id,
        "type": "follow_up",
        "status": {"$in": ["pending", "snoozed", None]},
    })
    if existing:
        return

    contact = await db.contacts.find_one({"_id": ObjectId(contact_id)}, {"first_name": 1})
    first = (contact or {}).get("first_name") or "your customer"
    interests = details.get("interests") or []
    if interests:
        title = f"Check in with {first} about {interests[0]}"
    elif details.get("spouse"):
        title = f"Ask {first} how {details['spouse']} is doing"
    elif details.get("referral_potential"):
        title = f"Ask {first} for a referral"
    else:
        title = f"Follow up with {first}"

    now = datetime.now(timezone.utc)
    await db.tasks.insert_one({
        "user_id": user_id,
        "contact_id": contact_id,
        "type": "follow_up",
        "title": title,
        "due_date": now + timedelta(days=3),
        "status": "pending",
        "source": "voice_note",
        "created_at": now,
    })
    logger.info(f"[VoiceIntel] auto follow-up created for {contact_id}: {title}")


def _ts(v):
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    if isinstance(v, str):
        try:
            d = datetime.fromisoformat(v.replace("Z", "+00:00"))
            return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        except Exception:
            return None
    return None


async def process_conversation_intelligence(user_id: str, contact_id: str) -> dict:
    """Run the same extractor over NEW inbox texts and recorded-call transcripts since the last pass.

    Cursor lives on the contact (conv_intel_cursor) so each text/call is analyzed once. Newest info wins.
    """
    db = get_db()
    if not ObjectId.is_valid(contact_id):
        return {}
    contact = await db.contacts.find_one({"_id": ObjectId(contact_id)}, {"conv_intel_cursor": 1, "first_name": 1})
    if not contact:
        return {}
    since = _ts((contact.get("conv_intel_cursor") or {}).get("at"))
    now = datetime.now(timezone.utc)

    conv_ids = [str(c["_id"]) async for c in db.conversations.find({"contact_id": contact_id}, {"_id": 1})]
    match = {"$or": [{"contact_id": contact_id}] + ([{"conversation_id": {"$in": conv_ids}}] if conv_ids else []),
             "sender": {"$nin": ["ai_draft", "system"]}, "type": {"$nin": ["event", "call_log"]}}
    pipeline = [{"$match": match},
                {"$addFields": {"_ts": {"$ifNull": ["$timestamp", "$created_at"]}}},
                {"$sort": {"_ts": 1}},
                {"$project": {"content": 1, "sender": 1, "direction": 1, "_ts": 1}}]
    lines, customer_chars, newest = [], 0, since
    async for m in db.messages.aggregate(pipeline):
        ts = _ts(m.get("_ts"))
        if not ts or (since and ts <= since):
            continue
        body = (m.get("content") or "").strip()
        if not body:
            continue
        inbound = m.get("sender") == "contact" or m.get("direction") == "inbound"
        who = "CUSTOMER" if inbound else ("AI" if m.get("sender") == "ai" else "REP")
        if inbound:
            customer_chars += len(body)
        lines.append(f"[{ts.strftime('%b %d')}] {who}: {body[:400]}")
        newest = ts if not newest or ts > newest else newest

    call_q = {"contact_id": contact_id, "transcript": {"$nin": [None, ""]}}
    if since:
        call_q["created_at"] = {"$gt": since}
    calls = await db.call_logs.find(call_q, {"transcript": 1, "created_at": 1, "direction": 1}).sort("created_at", 1).to_list(5)

    if customer_chars < 15 and not calls:
        if lines:
            await db.contacts.update_one({"_id": contact["_id"]}, {"$set": {"conv_intel_cursor": {"at": now, "fields": []}}})
        return {}

    details: dict = {}
    if customer_chars >= 15:
        details.update(await extract_personal_details("\n".join(lines[-60:]), source="text"))
    for c in calls:
        details.update(await extract_personal_details(c["transcript"][:6000], source="call"))
        ts = _ts(c.get("created_at"))
        newest = ts if ts and (not newest or ts > newest) else newest

    await db.contacts.update_one({"_id": contact["_id"]},
                                 {"$set": {"conv_intel_cursor": {"at": now, "fields": list(details.keys())}}})
    if not details:
        return {}
    await merge_personal_details(contact_id, details)
    field_names = ", ".join(details.keys())
    src = " + ".join(x for x, ok in (("texts", customer_chars >= 15), ("calls", bool(calls))) if ok)
    await db.contact_events.insert_one({
        "event_type": "intelligence_extracted", "title": "Personal Details Updated",
        "description": f"AI updated from {src}: {field_names}", "contact_id": contact_id, "user_id": user_id,
        "channel": "ai", "category": "intelligence", "icon": "sparkles", "color": "#AF52DE",
        "content": json.dumps(details), "metadata": {"source": src, "fields": list(details.keys())},
        "timestamp": now, "created_at": now,
    })
    logger.info(f"[ConvIntel] {contact_id}: {field_names} from {src}")
    return details
