"""
Relationship Intelligence Engine
Compiles all data sources into a rich "relationship brief" that powers
AI-generated campaign messages. Every touchpoint is deliberate because
the AI knows the full story.
"""
import logging
from datetime import datetime, timezone, timedelta
from bson import ObjectId
from typing import Optional

from routers.database import get_db

logger = logging.getLogger(__name__)


async def build_relationship_brief(user_id: str, contact_id: str, campaign_context: Optional[dict] = None) -> dict:
    """
    Build a comprehensive relationship intelligence brief.
    Returns both machine-readable data (for AI) and a human-readable summary (for the salesperson).
    """
    db = get_db()
    now = datetime.now(timezone.utc)

    brief = {
        "contact": {},
        "relationship_health": "unknown",
        "engagement_score": 0,
        "last_interaction_days": None,
        "engagement_signals": [],
        "conversation_summary": [],
        "previous_campaign_messages": [],
        "response_pattern": "unknown",
        "milestones": [],
        "ai_context": "",
        "human_summary": "",
    }

    # === CONTACT PROFILE ===
    contact = await db.contacts.find_one(
        {"_id": ObjectId(contact_id)},
        {"photo": 0, "photo_thumbnail": 0, "photo_url": 0}
    )
    if not contact:
        brief["human_summary"] = "Contact not found."
        return brief

    first_name = contact.get("first_name", "")
    last_name = contact.get("last_name", "")
    name = f"{first_name} {last_name}".strip() or "Unknown"
    brief["contact"] = {
        "name": name,
        "first_name": first_name,
        "phone": contact.get("phone", ""),
        "email": contact.get("email", ""),
        "tags": contact.get("tags", []),
        "notes": contact.get("notes", ""),
        "vehicle_interest": contact.get("vehicle_interest", ""),
        "vehicle_purchased": contact.get("vehicle_purchased", ""),
        "date_sold": str(contact.get("date_sold", "")) if contact.get("date_sold") else "",
        "lead_source": contact.get("lead_source", ""),
        "birthday": str(contact.get("birthday", "")) if contact.get("birthday") else "",
    }

    # === RELATIONSHIP TIMELINE ===
    created_at = contact.get("created_at")
    if created_at:
        if isinstance(created_at, str):
            try:
                created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            except Exception:
                created_at = None
        if created_at:
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            days_known = (now - created_at).days
            brief["days_known"] = days_known
            if days_known < 7:
                brief["milestones"].append("Brand new relationship")
            elif days_known < 30:
                brief["milestones"].append(f"New relationship ({days_known} days)")
            elif days_known < 90:
                brief["milestones"].append(f"Building relationship ({days_known // 30} months)")
            elif days_known < 365:
                brief["milestones"].append(f"Established relationship ({days_known // 30} months)")
            else:
                brief["milestones"].append(f"Long-term relationship ({days_known // 365}+ years)")

    date_sold = contact.get("date_sold")
    if date_sold:
        if isinstance(date_sold, str):
            try:
                date_sold = datetime.fromisoformat(date_sold.replace("Z", "+00:00"))
            except Exception:
                date_sold = None
        if isinstance(date_sold, datetime):
            if date_sold.tzinfo is None:
                date_sold = date_sold.replace(tzinfo=timezone.utc)
            days_since_sale = (now - date_sold).days
            brief["days_since_sale"] = days_since_sale
            if days_since_sale < 7:
                brief["milestones"].append(f"Just purchased {days_since_sale} days ago")
            elif days_since_sale < 30:
                brief["milestones"].append(f"Purchased {days_since_sale} days ago — still in honeymoon phase")
            elif days_since_sale < 90:
                brief["milestones"].append(f"Purchased {days_since_sale // 30} months ago — first service window approaching")
            elif days_since_sale >= 335 and days_since_sale <= 395:
                brief["milestones"].append("Approaching 1-year anniversary!")

    # === ENGAGEMENT SIGNALS (card views, link clicks, contact saves) ===
    signals = await db.engagement_signals.find(
        {"user_id": user_id, "contact_id": contact_id},
        {"_id": 0}
    ).sort("created_at", -1).limit(20).to_list(20)

    engagement_score = 0
    for s in signals:
        sig_type = s.get("signal_type", "")
        sig_time = s.get("created_at")
        if isinstance(sig_time, datetime):
            if sig_time.tzinfo is None:
                sig_time = sig_time.replace(tzinfo=timezone.utc)
            hours_ago = (now - sig_time).total_seconds() / 3600
            # Recency-weighted scoring
            if hours_ago < 24:
                engagement_score += 10
            elif hours_ago < 72:
                engagement_score += 5
            elif hours_ago < 168:  # 1 week
                engagement_score += 2
            else:
                engagement_score += 1

        brief["engagement_signals"].append({
            "type": sig_type,
            "when": str(s.get("created_at", "")),
            "details": s.get("details", {}),
            "contact_name": s.get("contact_name", ""),
        })

    brief["engagement_score"] = min(engagement_score, 100)

    # === CONVERSATION HISTORY ===
    events = await db.contact_events.find(
        {"contact_id": contact_id, "user_id": user_id},
        {"_id": 0, "event_type": 1, "title": 1, "description": 1, "timestamp": 1, "channel": 1}
    ).sort("timestamp", -1).limit(15).to_list(15)

    for e in events:
        brief["conversation_summary"].append({
            "type": e.get("event_type", ""),
            "title": e.get("title", ""),
            "description": (e.get("description", "") or "")[:200],
            "when": str(e.get("timestamp", "")),
            "channel": e.get("channel", ""),
        })

    # Last interaction
    if events:
        last_event_time = events[0].get("timestamp")
        if isinstance(last_event_time, datetime):
            if last_event_time.tzinfo is None:
                last_event_time = last_event_time.replace(tzinfo=timezone.utc)
            brief["last_interaction_days"] = (now - last_event_time).days

    # === PREVIOUS CAMPAIGN MESSAGES (what was already said) ===
    campaign_sends = await db.campaign_pending_sends.find(
        {"contact_id": contact_id, "user_id": user_id},
        {"_id": 0, "message": 1, "step": 1, "campaign_name": 1, "status": 1, "created_at": 1, "channel": 1}
    ).sort("created_at", -1).limit(10).to_list(10)

    for cs in campaign_sends:
        brief["previous_campaign_messages"].append({
            "campaign": cs.get("campaign_name", ""),
            "step": cs.get("step", 0),
            "message": (cs.get("message", "") or "")[:300],
            "status": cs.get("status", ""),
            "channel": cs.get("channel", ""),
            "when": str(cs.get("created_at", "")),
        })

    # === MESSAGES (actual conversation) ===
    messages = await db.messages.find(
        {"contact_id": contact_id}
    ).sort("timestamp", -1).limit(10).to_list(10)

    msg_summary = []
    inbound_count = 0
    outbound_count = 0
    for m in messages:
        sender = m.get("sender", "")
        if sender == "user":
            outbound_count += 1
        else:
            inbound_count += 1
        msg_summary.append({
            "from": "Salesperson" if sender == "user" else name,
            "content": (m.get("content", "") or "")[:150],
            "when": str(m.get("timestamp", "")),
        })

    # === RESPONSE PATTERN ===
    if inbound_count > 0 and outbound_count > 0:
        ratio = inbound_count / outbound_count
        if ratio > 0.7:
            brief["response_pattern"] = "highly_responsive"
        elif ratio > 0.3:
            brief["response_pattern"] = "moderately_responsive"
        else:
            brief["response_pattern"] = "low_responsive"
    elif outbound_count > 3 and inbound_count == 0:
        brief["response_pattern"] = "not_responsive"
    else:
        brief["response_pattern"] = "new_relationship"

    # === RELATIONSHIP HEALTH ===
    health_score = 0
    if brief["engagement_score"] > 20:
        health_score += 30
    elif brief["engagement_score"] > 5:
        health_score += 15

    if brief["response_pattern"] in ("highly_responsive", "moderately_responsive"):
        health_score += 30
    elif brief["response_pattern"] == "new_relationship":
        health_score += 15

    if brief["last_interaction_days"] is not None:
        if brief["last_interaction_days"] < 7:
            health_score += 30
        elif brief["last_interaction_days"] < 30:
            health_score += 20
        elif brief["last_interaction_days"] < 90:
            health_score += 10

    if len(brief["milestones"]) > 0:
        health_score += 10

    if health_score >= 70:
        brief["relationship_health"] = "strong"
    elif health_score >= 40:
        brief["relationship_health"] = "warm"
    elif health_score >= 20:
        brief["relationship_health"] = "cooling"
    else:
        brief["relationship_health"] = "cold"

    # === BUILD AI CONTEXT (what the AI reads) ===
    ai_parts = []
    ai_parts.append(f"=== RELATIONSHIP INTELLIGENCE: {name} ===")
    ai_parts.append(f"Relationship health: {brief['relationship_health'].upper()} (score: {health_score}/100)")
    ai_parts.append(f"Response pattern: {brief['response_pattern'].replace('_', ' ')}")

    if brief.get("engagement_score", 0) > 0:
        ai_parts.append(f"\nENGAGEMENT ACTIVITY (score: {brief['engagement_score']}/100):")
        for sig in brief["engagement_signals"][:5]:
            ai_parts.append(f"  - {sig['type'].replace('_', ' ').title()}: {sig['when']}")

    if brief["milestones"]:
        ai_parts.append(f"\nMILESTONES: {' | '.join(brief['milestones'])}")

    vehicle = contact.get("vehicle_purchased") or contact.get("vehicle_interest") or ""
    if vehicle:
        ai_parts.append(f"Vehicle: {vehicle}")

    if contact.get("notes"):
        ai_parts.append(f"Notes: {contact['notes'][:300]}")

    if brief["previous_campaign_messages"]:
        ai_parts.append("\nPREVIOUS MESSAGES IN THIS CAMPAIGN (DO NOT repeat these):")
        for pm in brief["previous_campaign_messages"][:5]:
            ai_parts.append(f"  Step {pm['step']} ({pm['campaign']}): \"{pm['message'][:150]}\"")

    if msg_summary:
        ai_parts.append("\nRECENT CONVERSATION:")
        for ms in msg_summary[:5]:
            ai_parts.append(f"  {ms['from']}: {ms['content']}")

    if brief["conversation_summary"]:
        ai_parts.append("\nACTIVITY TIMELINE:")
        for cs in brief["conversation_summary"][:5]:
            ai_parts.append(f"  {cs['type']}: {cs['title']} ({cs['when'][:10]})")

    brief["ai_context"] = "\n".join(ai_parts)

    # === BUILD HUMAN SUMMARY (what the salesperson reads) ===
    human_parts = []
    human_parts.append(f"Relationship: {brief['relationship_health'].upper()}")

    if brief.get("engagement_score", 0) > 15:
        human_parts.append(f"Engagement: Active (score {brief['engagement_score']})")
        recent_signals = [s["type"].replace("_", " ").title() for s in brief["engagement_signals"][:3]]
        if recent_signals:
            human_parts.append(f"Recent activity: {', '.join(recent_signals)}")
    elif brief.get("engagement_score", 0) > 0:
        human_parts.append(f"Engagement: Moderate (score {brief['engagement_score']})")
    else:
        human_parts.append("Engagement: No recent signals")

    if brief["milestones"]:
        human_parts.append(f"Timeline: {brief['milestones'][-1]}")

    if brief["last_interaction_days"] is not None:
        if brief["last_interaction_days"] == 0:
            human_parts.append("Last contact: Today")
        elif brief["last_interaction_days"] == 1:
            human_parts.append("Last contact: Yesterday")
        else:
            human_parts.append(f"Last contact: {brief['last_interaction_days']} days ago")

    human_parts.append(f"Responsiveness: {brief['response_pattern'].replace('_', ' ').title()}")

    brief["human_summary"] = " | ".join(human_parts)

    return brief
