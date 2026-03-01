"""
Contact Events router - tracks all touchpoints and interactions with a contact.
Aggregates data from messages, campaigns, congrats cards, and custom events
into a unified "Facebook-feed" style timeline.
"""
from fastapi import APIRouter, HTTPException
from bson import ObjectId
from datetime import datetime, timezone
from typing import Optional
import logging

from routers.database import get_db

router = APIRouter(prefix="/contacts", tags=["Contact Events"])
logger = logging.getLogger(__name__)


@router.get("/{user_id}/{contact_id}/events")
async def get_contact_events(user_id: str, contact_id: str, limit: int = 50):
    db = get_db()

    events = []

    # 1) Custom logged events from contact_events collection
    custom_events = await db.contact_events.find(
        {"contact_id": contact_id},
        {"_id": 0}
    ).sort("timestamp", -1).limit(limit).to_list(limit)
    for e in custom_events:
        if e.get("timestamp") and hasattr(e["timestamp"], "isoformat"):
            e["timestamp"] = e["timestamp"].isoformat()
        events.append(e)

    # 2) Messages sent to/from this contact
    conv = await db.conversations.find_one(
        {"user_id": user_id, "contact_id": contact_id},
        {"_id": 1}
    )
    if conv:
        conv_id = str(conv["_id"])
        messages = await db.messages.find(
            {"conversation_id": conv_id},
            {"_id": 0, "conversation_id": 0}
        ).sort("timestamp", -1).limit(limit).to_list(limit)
        for m in messages:
            sender = m.get("sender", "user")
            msg_type = m.get("type", "sms")
            direction = "outbound" if sender == "user" else "inbound"
            icon = "chatbubble" if msg_type == "sms" else "mail"
            color = "#007AFF" if direction == "outbound" else "#8E8E93"
            body_preview = (m.get("body") or "")[:80]
            ts = m.get("timestamp")
            if ts and hasattr(ts, "isoformat"):
                ts = ts.isoformat()
            events.append({
                "event_type": f"message_{direction}",
                "icon": icon,
                "color": color,
                "title": f"{'Sent' if direction == 'outbound' else 'Received'} {msg_type.upper()}",
                "description": body_preview,
                "timestamp": ts,
                "category": "message",
            })

    # 3) Campaign enrollments for this contact
    enrollments = await db.campaign_enrollments.find(
        {"contact_id": contact_id, "user_id": user_id},
        {"_id": 0}
    ).sort("enrolled_at", -1).to_list(20)
    for e in enrollments:
        campaign = await db.campaigns.find_one(
            {"_id": ObjectId(e["campaign_id"])},
            {"_id": 0, "name": 1, "type": 1}
        ) if e.get("campaign_id") else None
        campaign_name = campaign.get("name", "Unknown") if campaign else "Unknown"
        ts = e.get("enrolled_at")
        if ts and hasattr(ts, "isoformat"):
            ts = ts.isoformat()
        events.append({
            "event_type": "campaign_enrolled",
            "icon": "rocket",
            "color": "#AF52DE",
            "title": f"Enrolled in Campaign",
            "description": campaign_name,
            "timestamp": ts,
            "category": "campaign",
        })
        # Add individual campaign messages sent
        for msg in (e.get("messages_sent") or []):
            msg_ts = msg.get("sent_at")
            if msg_ts and hasattr(msg_ts, "isoformat"):
                msg_ts = msg_ts.isoformat()
            events.append({
                "event_type": "campaign_message_sent",
                "icon": "megaphone",
                "color": "#FF9500",
                "title": f"Campaign Message Sent",
                "description": f"{campaign_name} - Step {msg.get('step', '?')}",
                "timestamp": msg_ts,
                "category": "campaign",
            })

    # 4) Congrats cards sent to this contact
    congrats = await db.congrats_cards_sent.find(
        {"contact_id": contact_id, "user_id": user_id},
        {"_id": 0}
    ).sort("sent_at", -1).to_list(20)
    for c in congrats:
        ts = c.get("sent_at")
        if ts and hasattr(ts, "isoformat"):
            ts = ts.isoformat()
        events.append({
            "event_type": "congrats_card_sent",
            "icon": "gift",
            "color": "#C9A962",
            "title": "Sent Congrats Card",
            "description": c.get("message", "")[:60],
            "timestamp": ts,
            "category": "card",
        })

    # 5) Broadcast messages involving this contact
    broadcasts = await db.broadcast_recipients.find(
        {"contact_id": contact_id, "user_id": user_id},
        {"_id": 0}
    ).sort("sent_at", -1).to_list(20)
    for b in broadcasts:
        ts = b.get("sent_at")
        if ts and hasattr(ts, "isoformat"):
            ts = ts.isoformat()
        events.append({
            "event_type": "broadcast_sent",
            "icon": "megaphone",
            "color": "#FF2D55",
            "title": "Broadcast Message",
            "description": (b.get("message") or "")[:60],
            "timestamp": ts,
            "category": "broadcast",
        })

    # Sort all events by timestamp descending
    def sort_key(e):
        ts = e.get("timestamp")
        if not ts:
            return ""
        return ts

    events.sort(key=sort_key, reverse=True)

    return {
        "events": events[:limit],
        "total": len(events),
    }


@router.get("/{user_id}/{contact_id}/stats")
async def get_contact_stats(user_id: str, contact_id: str):
    db = get_db()

    # Count messages
    conv = await db.conversations.find_one(
        {"user_id": user_id, "contact_id": contact_id},
        {"_id": 1}
    )
    message_count = 0
    if conv:
        message_count = await db.messages.count_documents(
            {"conversation_id": str(conv["_id"]), "sender": "user"}
        )

    # Count campaign enrollments
    campaign_count = await db.campaign_enrollments.count_documents(
        {"contact_id": contact_id, "user_id": user_id}
    )

    # Count congrats cards
    card_count = await db.congrats_cards_sent.count_documents(
        {"contact_id": contact_id, "user_id": user_id}
    )

    # Count broadcasts
    broadcast_count = await db.broadcast_recipients.count_documents(
        {"contact_id": contact_id, "user_id": user_id}
    )

    # Count custom events
    custom_count = await db.contact_events.count_documents(
        {"contact_id": contact_id}
    )

    # Get contact created_at for "time in system"
    contact = None
    try:
        contact = await db.contacts.find_one(
            {"_id": ObjectId(contact_id)},
            {"_id": 0, "created_at": 1}
        )
    except Exception:
        pass  # Invalid ObjectId format
    created_at = None
    if contact and contact.get("created_at"):
        created_at = contact["created_at"].isoformat() if hasattr(contact["created_at"], "isoformat") else str(contact["created_at"])

    total_touchpoints = message_count + campaign_count + card_count + broadcast_count + custom_count

    return {
        "total_touchpoints": total_touchpoints,
        "messages_sent": message_count,
        "campaigns": campaign_count,
        "cards_sent": card_count,
        "broadcasts": broadcast_count,
        "custom_events": custom_count,
        "created_at": created_at,
    }


@router.post("/{user_id}/{contact_id}/events")
async def log_contact_event(user_id: str, contact_id: str, event_data: dict):
    db = get_db()

    event = {
        "contact_id": contact_id,
        "user_id": user_id,
        "event_type": event_data.get("event_type", "custom"),
        "icon": event_data.get("icon", "flag"),
        "color": event_data.get("color", "#007AFF"),
        "title": event_data.get("title", "Custom Event"),
        "description": event_data.get("description", ""),
        "category": event_data.get("category", "custom"),
        "timestamp": datetime.now(timezone.utc),
    }

    await db.contact_events.insert_one(event)
    event.pop("_id", None)
    if hasattr(event["timestamp"], "isoformat"):
        event["timestamp"] = event["timestamp"].isoformat()

    return event



@router.post("/{user_id}/find-or-create-and-log")
async def find_or_create_contact_and_log_event(user_id: str, payload: dict):
    """
    Smart contact matching: find by phone (last 10 digits) or email, create if not found.
    If name mismatch, return match info so frontend can prompt user.
    Supports dual email (personal + work).
    """
    db = get_db()

    phone = (payload.get("phone") or "").strip()
    email = (payload.get("email") or "").strip().lower()
    name = (payload.get("name") or "").strip()
    event_type = payload.get("event_type", "custom")
    event_title = payload.get("event_title", "Activity")
    event_description = payload.get("event_description", "")
    event_icon = payload.get("event_icon", "flag")
    event_color = payload.get("event_color", "#007AFF")
    force_action = payload.get("force_action")  # 'use_existing', 'update_name', 'create_new'

    if not phone and not email:
        raise HTTPException(status_code=400, detail="Phone or email is required")

    # --- Find existing contact ---
    contact = None

    # Match by phone (last 10 digits)
    if phone:
        normalized = "".join(c for c in phone if c.isdigit())
        if len(normalized) >= 10:
            suffix = normalized[-10:]
            contact = await db.contacts.find_one({
                "user_id": user_id,
                "phone": {"$regex": suffix},
                "status": {"$ne": "deleted"},
            })
        if not contact:
            contact = await db.contacts.find_one({
                "user_id": user_id,
                "phone": phone,
                "status": {"$ne": "deleted"},
            })

    # Match by email (personal or work) if no phone match
    if not contact and email:
        contact = await db.contacts.find_one({
            "user_id": user_id,
            "$or": [
                {"email": {"$regex": f"^{email}$", "$options": "i"}},
                {"email_work": {"$regex": f"^{email}$", "$options": "i"}},
            ],
            "status": {"$ne": "deleted"},
        })

    # --- Handle match with name mismatch ---
    if contact and name and not force_action:
        existing_name = f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip()
        if existing_name.lower() != name.lower() and existing_name:
            return {
                "match_found": True,
                "needs_confirmation": True,
                "contact_id": str(contact["_id"]),
                "existing_name": existing_name,
                "provided_name": name,
                "phone": contact.get("phone", ""),
                "email": contact.get("email", ""),
            }

    # --- Process based on force_action or auto ---
    created = False

    if contact and force_action == "update_name" and name:
        parts = name.split(" ", 1)
        await db.contacts.update_one(
            {"_id": contact["_id"]},
            {"$set": {
                "first_name": parts[0],
                "last_name": parts[1] if len(parts) > 1 else "",
                "updated_at": datetime.now(timezone.utc),
            }}
        )
        contact["first_name"] = parts[0]
        contact["last_name"] = parts[1] if len(parts) > 1 else ""

    elif contact and force_action == "create_new":
        # User wants a separate contact
        contact = None

    # Merge email onto existing contact if missing
    if contact and email:
        if not contact.get("email"):
            await db.contacts.update_one(
                {"_id": contact["_id"]},
                {"$set": {"email": email, "updated_at": datetime.now(timezone.utc)}}
            )
        elif contact.get("email", "").lower() != email.lower() and not contact.get("email_work"):
            await db.contacts.update_one(
                {"_id": contact["_id"]},
                {"$set": {"email_work": email, "updated_at": datetime.now(timezone.utc)}}
            )

    # Merge phone onto existing contact if missing
    if contact and phone and not contact.get("phone"):
        await db.contacts.update_one(
            {"_id": contact["_id"]},
            {"$set": {"phone": phone, "updated_at": datetime.now(timezone.utc)}}
        )

    if not contact:
        parts = name.split(" ", 1) if name else [phone or email]
        first_name = parts[0]
        last_name = parts[1] if len(parts) > 1 else ""

        new_contact = {
            "first_name": first_name,
            "last_name": last_name,
            "phone": phone,
            "email": email,
            "email_work": "",
            "user_id": user_id,
            "original_user_id": user_id,
            "ownership_type": "org",
            "source": "manual",
            "status": "active",
            "tags": [],
            "notes": "",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        result = await db.contacts.insert_one(new_contact)
        new_contact["_id"] = result.inserted_id
        contact = new_contact
        created = True

    contact_id = str(contact["_id"])

    # Log the event
    event = {
        "contact_id": contact_id,
        "user_id": user_id,
        "event_type": event_type,
        "icon": event_icon,
        "color": event_color,
        "title": event_title,
        "description": event_description,
        "category": "outreach",
        "timestamp": datetime.now(timezone.utc),
    }
    await db.contact_events.insert_one(event)
    event.pop("_id", None)

    return {
        "contact_id": contact_id,
        "contact_created": created,
        "contact_name": f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip(),
        "contact_phone": contact.get("phone", ""),
        "contact_email": contact.get("email", ""),
        "event_logged": True,
        "match_found": not created,
        "needs_confirmation": False,
    }
