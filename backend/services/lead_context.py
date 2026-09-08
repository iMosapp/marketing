"""What an internet lead is actually asking about, so Jessi stays on topic
(software demo vs vehicle vs general). Injected into every AI path for lead threads."""
from typing import Optional
from bson import ObjectId

SOFTWARE_DEMO_TOPIC = "a demo of i'M On Social, the software we sell"
SOFTWARE_DEMO_CUSTOMER = "a demo of i'M On Social"


def build_lead_inquiry(normalized: dict, source: dict) -> dict:
    vehicle = " ".join(filter(None, [
        normalized.get("vehicle_year"), normalized.get("vehicle_make"),
        normalized.get("vehicle_model"), normalized.get("vehicle_trim"),
    ])).strip() or (normalized.get("vehicle_interest") or "").strip()
    if vehicle.lower() in ("demo request", "the vehicle", "vehicle"):
        vehicle = ""
    attribution = normalized.get("attribution") or {}
    override = (source.get("inquiry_context") or "").strip()
    if attribution.get("kind") == "website_form":
        kind, topic = "software_demo", (override or SOFTWARE_DEMO_TOPIC)
    elif vehicle:
        kind, topic = "vehicle", (override or f"the {vehicle}")
    elif override:
        kind, topic = "general", override
    else:
        kind, topic = "general", f"an inquiry through {source.get('name') or normalized.get('source_name') or 'a lead form'}"
    return {
        "kind":        kind,
        "topic":       topic,
        "vehicle":     vehicle,
        "company":     (normalized.get("company") or "").strip(),
        "industry":    (normalized.get("industry") or "").strip(),
        "page_label":  (attribution.get("source_label") or "").strip(),
        "message":     (normalized.get("comments") or "").strip()[:500],
        "source_name": source.get("name") or normalized.get("source_name") or "",
    }


async def get_conversation_inquiry(db, conv: Optional[dict]) -> Optional[dict]:
    """Stored inquiry for a lead thread; legacy lead threads get one derived from the lead + attribution and cached."""
    if not conv or not conv.get("is_internet_lead"):
        return None
    if conv.get("inquiry"):
        return conv["inquiry"]
    lead, source = {}, {}
    if conv.get("inbound_lead_id") and ObjectId.is_valid(str(conv["inbound_lead_id"])):
        lead = await db.inbound_leads.find_one(
            {"_id": ObjectId(conv["inbound_lead_id"])}, {"vehicle_interest": 1, "comments": 1, "source_name": 1}) or {}
    if conv.get("lead_source_id") and ObjectId.is_valid(str(conv["lead_source_id"])):
        source = await db.lead_sources.find_one(
            {"_id": ObjectId(conv["lead_source_id"])}, {"name": 1, "inquiry_context": 1}) or {}
    inquiry = build_lead_inquiry({
        "vehicle_interest": lead.get("vehicle_interest", ""),
        "comments":         lead.get("comments", ""),
        "attribution":      conv.get("attribution") or {},
        "source_name":      conv.get("lead_source_name") or lead.get("source_name", ""),
    }, source or {"name": conv.get("lead_source_name", "")})
    try:
        await db.conversations.update_one({"_id": conv["_id"]}, {"$set": {"inquiry": inquiry}})
    except Exception:
        pass
    return inquiry


async def get_inquiry_for_conversation_id(db, conversation_id: str) -> Optional[dict]:
    if not conversation_id or not ObjectId.is_valid(str(conversation_id)):
        return None
    conv = await db.conversations.find_one(
        {"_id": ObjectId(conversation_id)},
        {"is_internet_lead": 1, "inquiry": 1, "inbound_lead_id": 1, "lead_source_id": 1, "lead_source_name": 1, "attribution": 1})
    return await get_conversation_inquiry(db, conv)


def is_vehicle_inquiry(inquiry: Optional[dict]) -> bool:
    """No inquiry (regular customer thread) keeps today's behaviour; a lead thread must be about a vehicle."""
    return inquiry is None or inquiry.get("kind") == "vehicle"


def inquiry_prompt_block(inquiry: Optional[dict]) -> str:
    if not inquiry:
        return ""
    kind = inquiry.get("kind") or "general"
    lines = ["", "WHAT THIS LEAD IS ABOUT (this beats your background, the contact's history and any older messages):"]
    src = inquiry.get("source_name") or "a lead form"
    page = inquiry.get("page_label")
    lines.append(f"- Came in through: {src}" + (f" ({page})" if page else ""))
    lines.append(f"- Asked for: {inquiry.get('topic')}")
    if inquiry.get("company"):
        lines.append(f"- Their company: {inquiry['company']}")
    if inquiry.get("industry"):
        lines.append(f"- Their business type: {inquiry['industry']}")
    if inquiry.get("message"):
        lines.append(f"- Their words: \"{inquiry['message'][:300]}\"")
    if kind == "software_demo":
        lines.append(
            "RULES: You are selling the software, not a product off a lot. 'Demo' means a walkthrough of the software. "
            "Never mention vehicles, inventory, test drives, trade-ins, financing or anything from another industry, "
            "even if the customer's history or your own background mentions them. "
            "If they want to set a time, help them pick a day and time for the software demo.")
    elif kind == "vehicle":
        lines.append("RULES: Stay on this vehicle inquiry unless the customer changes the subject.")
    else:
        lines.append("RULES: Stay on what they asked about. Do not assume they want a vehicle or anything else they did not mention.")
    return "\n".join(lines)
