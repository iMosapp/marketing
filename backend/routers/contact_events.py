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

def _ts_iso(dt) -> str:
    """Convert a datetime to ISO string with UTC indicator for correct browser parsing."""
    if dt is None:
        return None
    s = dt.isoformat() if hasattr(dt, 'isoformat') else str(dt)
    if not s.endswith('Z') and '+' not in s and s != 'None':
        s += 'Z'
    return s

router = APIRouter(prefix="/contacts", tags=["Contact Events"])
logger = logging.getLogger(__name__)


# ===== KEY ACTIONS FOR PROGRESS TRACKER =====
KEY_ACTIONS = [
    {"key": "digital_card_sent", "label": "Contact Card", "icon": "card", "color": "#007AFF",
     "event_types": ["digital_card_sent", "vcard_sent"]},
    {"key": "congrats_card_sent", "label": "Congrats", "icon": "gift", "color": "#C9A962",
     "event_types": ["congrats_card_sent"]},
    {"key": "review_request_sent", "label": "Review Link", "icon": "star", "color": "#FFD60A",
     "event_types": ["review_request_sent"]},
    {"key": "link_page_shared", "label": "Link Page", "icon": "link", "color": "#AF52DE",
     "event_types": ["link_page_shared"]},
    {"key": "email_sent", "label": "Email", "icon": "mail", "color": "#34C759",
     "event_types": ["email_sent"]},
    {"key": "personal_sms", "label": "Text", "icon": "chatbubble", "color": "#007AFF",
     "event_types": ["personal_sms"]},
    {"key": "call_placed", "label": "Call", "icon": "call", "color": "#30D158",
     "event_types": ["call_placed"]},
]


@router.get("/{user_id}/master-feed")
async def get_master_feed(user_id: str, limit: int = 50, skip: int = 0):
    """
    Aggregate a social-media-style feed across ALL contacts for a user.
    Returns recent events + upcoming campaign actions + suggested next steps.
    """
    db = get_db()

    now = datetime.now(timezone.utc)

    # 1) Recent events across all contacts (newest first)
    recent_events = await db.contact_events.find(
        {"user_id": user_id},
        {"_id": 0, "photo": 0}
    ).sort("timestamp", -1).skip(skip).limit(limit).to_list(limit)

    # Get all contact IDs referenced
    contact_ids = list({e.get("contact_id") for e in recent_events if e.get("contact_id")})

    # Bulk fetch contact info
    contacts_map = {}
    if contact_ids:
        try:
            oids = [ObjectId(cid) for cid in contact_ids]
            contacts_cursor = db.contacts.find(
                {"_id": {"$in": oids}},
                {"_id": 1, "first_name": 1, "last_name": 1, "photo": 1, "photo_thumbnail": 1, "photo_url": 1, "tags": 1, "vehicle": 1}
            )
            async for c in contacts_cursor:
                contacts_map[str(c["_id"])] = {
                    "id": str(c["_id"]),
                    "name": f"{c.get('first_name', '')} {c.get('last_name', '')}".strip(),
                    "photo": c.get("photo_thumbnail") or c.get("photo_url") or c.get("photo"),
                    "tags": c.get("tags", []),
                    "vehicle": c.get("vehicle", ""),
                }
        except Exception:
            pass

    # Format events with contact info
    feed_items = []
    for evt in recent_events:
        if evt.get("timestamp") and hasattr(evt["timestamp"], "isoformat"):
            evt["timestamp"] = _ts_iso(evt["timestamp"])
        cid = evt.get("contact_id")
        contact_info = contacts_map.get(cid, {"id": cid, "name": "Unknown", "photo": None, "tags": [], "vehicle": ""})
        is_inbound = evt.get("direction") == "inbound" or evt.get("event_type") == "customer_reply"
        feed_items.append({
            "type": "event",
            "event_type": evt.get("event_type", "custom"),
            "title": evt.get("title", "Activity"),
            "description": evt.get("description", ""),
            "icon": evt.get("icon", "flag"),
            "color": evt.get("color", "#8E8E93"),
            "timestamp": evt.get("timestamp"),
            "contact": contact_info,
            "category": evt.get("category", "custom"),
            "is_inbound": is_inbound,
            "channel": evt.get("channel"),
        })

    # 2) Upcoming campaign events (next 48 hours)
    upcoming = []
    try:
        enrollments = await db.campaign_enrollments.find(
            {"user_id": user_id, "status": "active"}
        ).to_list(100)
        for enrollment in enrollments[:20]:
            cid = enrollment.get("contact_id")
            contact_info = contacts_map.get(cid)
            if not contact_info:
                try:
                    c = await db.contacts.find_one({"_id": ObjectId(cid)}, {"_id": 0, "first_name": 1, "last_name": 1, "photo": 1, "photo_thumbnail": 1, "photo_url": 1})
                    if c:
                        contact_info = {"id": cid, "name": f"{c.get('first_name','')} {c.get('last_name','')}".strip(), "photo": c.get("photo_thumbnail") or c.get("photo_url") or c.get("photo"), "tags": [], "vehicle": ""}
                except Exception:
                    pass
            if contact_info:
                try:
                    campaign = await db.campaigns.find_one({"_id": ObjectId(enrollment.get("campaign_id"))}, {"_id": 0, "name": 1, "steps": 1})
                    if campaign:
                        step_idx = enrollment.get("current_step", 0)
                        steps = campaign.get("steps", [])
                        if step_idx < len(steps):
                            upcoming.append({
                                "type": "campaign_upcoming",
                                "title": f"Campaign: {campaign['name']}",
                                "description": f"Step {step_idx + 1} of {len(steps)}  - {steps[step_idx].get('type', 'action')}",
                                "icon": "rocket",
                                "color": "#AF52DE",
                                "contact": contact_info,
                                "campaign_name": campaign["name"],
                                "step_number": step_idx + 1,
                                "total_steps": len(steps),
                            })
                except Exception:
                    pass
    except Exception as e:
        logger.error(f"Error fetching campaign upcoming: {e}")

    # 3) Suggested actions across all contacts
    suggested = []
    try:
        all_contacts = await db.contacts.find(
            {"user_id": user_id, "status": {"$ne": "deleted"}},
            {"_id": 1, "first_name": 1, "last_name": 1, "photo": 1, "birthday": 1, "date_sold": 1, "purchase_date": 1, "tags": 1}
        ).to_list(500)

        for contact in all_contacts:
            cid = str(contact["_id"])
            name = contact.get("first_name", "")

            # Birthday check
            bday = contact.get("birthday")
            if bday and hasattr(bday, "month"):
                try:
                    bday_aware = bday.replace(year=now.year, tzinfo=timezone.utc) if not getattr(bday, 'tzinfo', None) else bday.replace(year=now.year)
                    days_until = (bday_aware - now).days % 365
                    if days_until <= 3:
                        suggested.append({
                            "type": "suggested",
                            "priority": 0,
                            "title": f"Birthday {'today' if days_until == 0 else f'in {days_until}d'}!",
                            "description": f"Send {name} a birthday card",
                            "icon": "gift",
                            "color": "#FF9500",
                            "contact": {"id": cid, "name": f"{name} {contact.get('last_name','')}".strip(), "photo": contact.get("photo_thumbnail") or contact.get("photo_url") or contact.get("photo"), "tags": contact.get("tags", [])},
                            "action": "congrats",
                            "suggested_message": f"Happy Birthday, {name}! Hope you have an amazing day!",
                        })
                except Exception:
                    pass

            # 30-day follow-up
            sold = contact.get("date_sold") or contact.get("purchase_date")
            if sold and hasattr(sold, "date"):
                try:
                    sold_aware = sold.replace(tzinfo=timezone.utc) if not getattr(sold, 'tzinfo', None) else sold
                    days_since = (now - sold_aware).days
                    for milestone in [30, 60, 90]:
                        if milestone - 2 <= days_since <= milestone + 2:
                            suggested.append({
                                "type": "suggested",
                                "priority": 1,
                                "title": f"{milestone}-day check-in",
                                "description": f"Follow up with {name}",
                                "icon": "time",
                                "color": "#34C759",
                                "contact": {"id": cid, "name": f"{name} {contact.get('last_name','')}".strip(), "photo": contact.get("photo_thumbnail") or contact.get("photo_url") or contact.get("photo"), "tags": contact.get("tags", [])},
                                "action": "sms",
                                "suggested_message": f"Hey {name}! It's been {milestone} days  - how's everything going? Let me know if you need anything!",
                            })
                            break
                except Exception:
                    pass

        suggested.sort(key=lambda x: x.get("priority", 99))
    except Exception as e:
        logger.error(f"Error generating suggested actions: {e}")

    return {
        "feed": feed_items,
        "upcoming": upcoming[:10],
        "suggested": suggested[:10],
        "total_events": len(feed_items),
        "has_more": len(feed_items) == limit,
    }


@router.get("/{user_id}/{contact_id}/action-progress")
async def get_action_progress(user_id: str, contact_id: str):
    """Return which key CRM actions have been completed for this contact."""
    db = get_db()

    event_types = await db.contact_events.distinct(
        "event_type", {"contact_id": contact_id, "user_id": user_id}
    )
    msg_types = await db.messages.distinct(
        "channel", {"contact_id": contact_id, "user_id": user_id}
    )
    all_types = set(event_types + msg_types)

    progress = []
    for action in KEY_ACTIONS:
        done = any(t in all_types for t in action["event_types"])
        progress.append({
            "key": action["key"],
            "label": action["label"],
            "icon": action["icon"],
            "color": action["color"],
            "done": done,
        })

    completed = sum(1 for p in progress if p["done"])
    return {
        "progress": progress,
        "completed": completed,
        "total": len(progress),
    }


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
            e["timestamp"] = _ts_iso(e["timestamp"])
        # Ensure full_content is available for rich preview
        if not e.get("full_content"):
            e["full_content"] = e.get("content") or e.get("content_preview") or e.get("description") or ""
        # Ensure description exists for collapsed view
        if not e.get("description"):
            e["description"] = (e.get("content_preview") or e.get("content") or e.get("full_content") or "")[:80]
        # Mark inbound customer replies
        if e.get("event_type") == "customer_reply":
            e["direction"] = "inbound"
            if e.get("photo"):
                e["has_photo"] = True
                e.pop("photo", None)  # Don't send base64 in list response
        # Ensure title exists
        if not e.get("title"):
            etype = e.get("event_type", "")
            if etype == "personal_sms":
                e["title"] = "Sent Personal SMS"
                e["icon"] = e.get("icon", "chatbubble")
                e["color"] = e.get("color", "#34C759")
                e["category"] = "message"
            elif etype == "call_placed":
                e["title"] = e.get("title", "Outbound Call")
            elif etype == "email_sent":
                e["title"] = "Sent Email"
                e["icon"] = e.get("icon", "mail")
                e["color"] = e.get("color", "#007AFF")
                e["category"] = "message"
        # Pull full message body from messages collection if we have a message_id
        if e.get("message_id") and not e.get("full_content"):
            try:
                msg = await db.messages.find_one({"_id": ObjectId(e["message_id"])}, {"body": 1, "subject": 1})
                if msg:
                    e["full_content"] = msg.get("body", "")
                    if msg.get("subject"):
                        e["subject"] = msg["subject"]
            except Exception:
                pass
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
            channel = m.get("channel", msg_type)
            direction = "outbound" if sender == "user" else "inbound"
            icon = "chatbubble" if msg_type == "sms" else "mail"
            color = "#007AFF" if direction == "outbound" else "#8E8E93"
            body = m.get("body") or ""
            ts = m.get("timestamp")
            if ts and hasattr(ts, "isoformat"):
                ts = _ts_iso(ts)
            events.append({
                "event_type": f"message_{direction}",
                "icon": icon,
                "color": color,
                "title": f"{'Sent' if direction == 'outbound' else 'Received'} {msg_type.upper()}",
                "description": body[:80],
                "full_content": body,
                "channel": channel,
                "subject": m.get("subject"),
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
            ts = _ts_iso(ts)
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
                msg_ts = _ts_iso(msg_ts)
            events.append({
                "event_type": "campaign_message_sent",
                "icon": "megaphone",
                "color": "#FF9500",
                "title": f"Campaign Message Sent",
                "description": f"{campaign_name} - Step {msg.get('step', '?')}",
                "full_content": msg.get("body") or msg.get("message") or f"{campaign_name} - Step {msg.get('step', '?')}",
                "channel": msg.get("channel", "sms"),
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
            ts = _ts_iso(ts)
        events.append({
            "event_type": "congrats_card_sent",
            "icon": "gift",
            "color": "#C9A962",
            "title": "Sent Congrats Card",
            "description": c.get("message", "")[:60],
            "full_content": c.get("message", ""),
            "card_id": c.get("card_id"),
            "card_type": c.get("card_type", "congrats"),
            "link": f"/congrats/{c.get('card_id')}" if c.get("card_id") else None,
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
            ts = _ts_iso(ts)
        full_msg = b.get("message") or ""
        events.append({
            "event_type": "broadcast_sent",
            "icon": "megaphone",
            "color": "#FF2D55",
            "title": "Broadcast Message",
            "description": full_msg[:60],
            "full_content": full_msg,
            "channel": b.get("channel", "sms"),
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

    # Count link click/view events
    click_event_types = [
        "digital_card_viewed", "review_page_viewed", "showcase_viewed",
        "link_page_viewed", "link_clicked", "review_link_clicked",
        "congrats_card_viewed",
    ]
    link_clicks = await db.contact_events.count_documents(
        {"contact_id": contact_id, "event_type": {"$in": click_event_types}}
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
        created_at = _ts_iso(contact["created_at"])

    total_touchpoints = message_count + campaign_count + card_count + broadcast_count + custom_count

    return {
        "total_touchpoints": total_touchpoints,
        "messages_sent": message_count,
        "campaigns": campaign_count,
        "cards_sent": card_count,
        "broadcasts": broadcast_count,
        "custom_events": custom_count,
        "link_clicks": link_clicks,
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
        event["timestamp"] = _ts_iso(event["timestamp"])

    return event


@router.post("/{user_id}/{contact_id}/log-reply")
async def log_customer_reply(user_id: str, contact_id: str, reply_data: dict):
    """Log a manually pasted customer reply with optional photo attachment."""
    db = get_db()

    text = (reply_data.get("text") or "").strip()
    photo_data = reply_data.get("photo")  # base64 or URL
    reply_timestamp = reply_data.get("timestamp")  # optional  - user can set when reply happened

    if not text and not photo_data:
        raise HTTPException(status_code=400, detail="Reply must have text or a photo")

    ts = datetime.now(timezone.utc)
    if reply_timestamp:
        try:
            ts = datetime.fromisoformat(reply_timestamp.replace("Z", "+00:00"))
        except Exception:
            pass

    event = {
        "contact_id": contact_id,
        "user_id": user_id,
        "event_type": "customer_reply",
        "icon": "chatbubble-ellipses",
        "color": "#30D158",
        "title": "Customer Reply",
        "description": text[:80] if text else "Sent a photo",
        "full_content": text,
        "category": "customer_activity",
        "direction": "inbound",
        "timestamp": ts,
    }
    if photo_data:
        event["photo"] = photo_data

    await db.contact_events.insert_one(event)
    event.pop("_id", None)
    if hasattr(event["timestamp"], "isoformat"):
        event["timestamp"] = _ts_iso(event["timestamp"])
    # Don't return base64 photo in response
    event.pop("photo", None)
    event["has_photo"] = bool(photo_data)

    return event


@router.get("/{user_id}/{contact_id}/suggested-actions")
async def get_suggested_actions(user_id: str, contact_id: str):
    """Generate suggested next actions for a contact based on their data and activity."""
    db = get_db()

    contact = await db.contacts.find_one(
        {"_id": ObjectId(contact_id), "user_id": user_id},
        {"_id": 0, "first_name": 1, "last_name": 1, "birthday": 1, "anniversary": 1,
         "date_sold": 1, "purchase_date": 1, "tags": 1, "created_at": 1, "phone": 1}
    )
    if not contact:
        return {"actions": []}

    name = contact.get("first_name", "Customer")
    actions = []
    now = datetime.now(timezone.utc)

    # Check birthday
    bday = contact.get("birthday")
    if bday:
        if hasattr(bday, "month"):
            try:
                bday_this_year = bday.replace(year=now.year, tzinfo=timezone.utc) if not bday.tzinfo else bday.replace(year=now.year)
                days_until = (bday_this_year - now).days % 365
            except Exception:
                days_until = 999
            if days_until <= 7:
                actions.append({
                    "type": "birthday",
                    "priority": "high",
                    "icon": "gift",
                    "color": "#FF9500",
                    "title": f"Birthday coming up!",
                    "description": f"{name}'s birthday is {'today' if days_until == 0 else f'in {days_until} day' + ('s' if days_until > 1 else '')}",
                    "suggested_message": f"Happy Birthday, {name}! Hope you have an amazing day! - Sent with care from your friends at the dealership",
                    "action": "congrats",
                })

    # Check anniversary
    ann = contact.get("anniversary")
    if ann:
        if hasattr(ann, "month"):
            try:
                ann_this_year = ann.replace(year=now.year, tzinfo=timezone.utc) if not ann.tzinfo else ann.replace(year=now.year)
                days_until = (ann_this_year - now).days % 365
            except Exception:
                days_until = 999
            if days_until <= 7:
                actions.append({
                    "type": "anniversary",
                    "priority": "high",
                    "icon": "heart",
                    "color": "#FF2D55",
                    "title": f"Anniversary coming up!",
                    "description": f"{name}'s anniversary is {'today' if days_until == 0 else f'in {days_until} day' + ('s' if days_until > 1 else '')}",
                    "suggested_message": f"Happy Anniversary, {name}! Wishing you and your family all the best! Hope you're still loving the ride.",
                    "action": "sms",
                })

    # Check date sold (30/60/90 day touchpoints)
    sold = contact.get("date_sold") or contact.get("purchase_date")
    if sold and hasattr(sold, "date"):
        sold_aware = sold.replace(tzinfo=timezone.utc) if not getattr(sold, 'tzinfo', None) else sold
        days_since = (now - sold_aware).days
        for milestone in [30, 60, 90, 180, 365]:
            if milestone - 3 <= days_since <= milestone + 3:
                actions.append({
                    "type": "follow_up",
                    "priority": "medium" if milestone <= 90 else "low",
                    "icon": "car",
                    "color": "#34C759",
                    "title": f"{milestone}-day follow-up",
                    "description": f"It's been {milestone} days since {name}'s purchase",
                    "suggested_message": f"Hey {name}! It's been {milestone} days since you drove off the lot. How are you loving your ride? Let me know if there's anything I can help with!",
                    "action": "sms",
                })
                break

    # Check last activity  - nudge if no touchpoint in 30+ days
    last_event = await db.contact_events.find_one(
        {"contact_id": contact_id, "event_type": {"$nin": ["customer_reply", "congrats_card_viewed"]}},
        {"_id": 0, "timestamp": 1},
        sort=[("timestamp", -1)]
    )
    if last_event and last_event.get("timestamp"):
        le_ts = last_event["timestamp"]
        le_ts_aware = le_ts.replace(tzinfo=timezone.utc) if not getattr(le_ts, 'tzinfo', None) else le_ts
        days_since_contact = (now - le_ts_aware).days
        if days_since_contact >= 30 and not any(a["type"] in ["birthday", "anniversary", "follow_up"] for a in actions):
            actions.append({
                "type": "re_engage",
                "priority": "medium",
                "icon": "time",
                "color": "#FF9F0A",
                "title": f"Time to reconnect",
                "description": f"It's been {days_since_contact} days since your last touchpoint with {name}",
                "suggested_message": f"Hey {name}! Just checking in  - haven't connected in a while. Hope everything's going great! Let me know if there's anything you need.",
                "action": "sms",
            })

    # Check for recent customer feedback that hasn't been thanked
    recent_feedback = await db.contact_events.find_one(
        {"contact_id": contact_id, "event_type": "review_submitted"},
        {"_id": 0, "timestamp": 1, "description": 1},
        sort=[("timestamp", -1)]
    )
    if recent_feedback:
        # Check if there's been a thank-you sent after the feedback
        thank_you = await db.contact_events.find_one(
            {"contact_id": contact_id, "event_type": {"$in": ["personal_sms", "email_sent"]},
             "timestamp": {"$gt": recent_feedback["timestamp"]}},
            {"_id": 0}
        )
        if not thank_you:
            actions.append({
                "type": "thank_feedback",
                "priority": "high",
                "icon": "star",
                "color": "#FFD60A",
                "title": "Thank them for their review!",
                "description": f"{name} left a review  - send a thank you",
                "suggested_message": f"Hey {name}! Thank you so much for leaving that review  - it really means a lot! If you know anyone else looking, I'd love to help them out too.",
                "action": "sms",
            })

    # Sort by priority
    prio_order = {"high": 0, "medium": 1, "low": 2}
    actions.sort(key=lambda a: prio_order.get(a.get("priority", "low"), 2))

    return {"actions": actions}


@router.get("/{user_id}/{contact_id}/reply-photo/{event_index}")
async def get_reply_photo(user_id: str, contact_id: str, event_index: int):
    """Serve a photo from a customer reply event."""
    db = get_db()
    import base64
    from fastapi.responses import Response

    # Find customer reply events with photos for this contact
    replies = await db.contact_events.find(
        {"contact_id": contact_id, "event_type": "customer_reply", "photo": {"$exists": True}},
        {"photo": 1}
    ).sort("timestamp", -1).to_list(100)

    if event_index < 0 or event_index >= len(replies):
        raise HTTPException(status_code=404, detail="Photo not found")

    photo_data = replies[event_index].get("photo", "")
    if not photo_data:
        raise HTTPException(status_code=404, detail="Photo not found")

    if photo_data.startswith("data:"):
        parts = photo_data.split(",", 1)
        if len(parts) == 2:
            header = parts[0]
            b64 = parts[1]
            mime = header.split(":")[1].split(";")[0] if ":" in header else "image/png"
            try:
                image_bytes = base64.b64decode(b64)
                return Response(content=image_bytes, media_type=mime, headers={"Cache-Control": "public, max-age=86400"})
            except Exception:
                raise HTTPException(status_code=500, detail="Failed to decode photo")
    if photo_data.startswith("http"):
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=photo_data)
    raise HTTPException(status_code=404, detail="Photo format not supported")
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

