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
from utils.event_types import get_event_label

def _ts_iso(dt) -> str:
    """Convert a datetime to ISO string with UTC indicator for correct browser parsing."""
    if dt is None:
        return None
    s = dt.isoformat() if hasattr(dt, 'isoformat') else str(dt)
    if not s.endswith('Z') and '+' not in s and s != 'None':
        s += 'Z'
    return s


async def _quick_milestone_check(user_id: str):
    """Lightweight milestone check fired after each event. Non-blocking.
    Uses a single aggregation instead of 60 separate count queries.
    """
    try:
        db = get_db()
        from datetime import timedelta
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        sixty_days_ago = today_start - timedelta(days=60)

        # Single aggregation to get per-day counts — replaces 60 individual queries
        pipeline = [
            {"$match": {"user_id": user_id, "timestamp": {"$gte": sixty_days_ago}}},
            {"$group": {
                "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$timestamp"}},
                "count": {"$sum": 1},
            }},
            {"$sort": {"_id": -1}},
        ]
        daily_counts = await db.contact_events.aggregate(pipeline).to_list(65)
        day_map = {d["_id"]: d["count"] for d in daily_counts}

        today_str = today_start.strftime("%Y-%m-%d")
        today_count = day_map.get(today_str, 0)
        best_day = max((d["count"] for d in daily_counts), default=0)

        # Streak calculation from pre-fetched data — no more per-day DB calls
        streak = 0
        for i in range(60):
            day = (today_start - timedelta(days=i)).strftime("%Y-%m-%d")
            if day_map.get(day, 0) >= 5:
                streak += 1
            elif i > 0:
                break

        # Total for level (single count)
        total = await db.contact_events.count_documents({"user_id": user_id})
        levels = [(0, "Rookie"), (100, "Hustler"), (500, "Closer"), (1500, "All-Star"), (5000, "Legend")]
        level_title = next((name for threshold, name in reversed(levels) if total >= threshold), "Rookie")

        from routers.push_notifications import check_and_notify_milestones
        await check_and_notify_milestones(user_id, streak, level_title, today_count, best_day)
    except Exception as e:
        logger.debug(f"Quick milestone check failed for {user_id}: {e}")

router = APIRouter(prefix="/contacts", tags=["Contact Events"])
logger = logging.getLogger(__name__)


# ===== KEY ACTIONS FOR PROGRESS TRACKER =====
KEY_ACTIONS = [
    {"key": "digital_card_sent", "label": "Contact Card", "icon": "card", "color": "#007AFF",
     "event_types": ["digital_card_sent", "vcard_sent"]},
    {"key": "congrats_card_sent", "label": "Congrats", "icon": "gift", "color": "#C9A962",
     "event_types": ["congrats_card_sent", "birthday_card_sent", "anniversary_card_sent", "holiday_card_sent", "thank_you_card_sent", "thankyou_card_sent", "welcome_card_sent"]},
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
async def get_master_feed(user_id: str, limit: int = 25, skip: int = 0):
    """
    Aggregate a social-media-style feed across ALL contacts for a user.
    Returns recent events. Campaign/suggested data loads separately via dedicated endpoints.
    """
    db = get_db()
    # Hard cap — 50 per page allows scrolling back weeks without overloading the server
    limit = min(limit, 50)

    # 1) Recent events across all contacts (newest first)
    recent_events = await db.contact_events.find(
        {"user_id": user_id},
        {"_id": 0, "photo": 0}
    ).sort("timestamp", -1).skip(skip).limit(limit).to_list(limit)

    # Get all unique contact IDs
    contact_ids = list({e.get("contact_id") for e in recent_events if e.get("contact_id")})

    # Bulk fetch contact info — only small fields, exclude heavy photo
    contacts_map = {}
    if contact_ids:
        # Convert to ObjectIds individually — skip any invalid ones
        oids = []
        for cid in contact_ids:
            try:
                oids.append(ObjectId(cid))
            except Exception:
                pass
        if oids:
            try:
                contacts_cursor = db.contacts.find(
                    {"_id": {"$in": oids}},
                    {"_id": 1, "first_name": 1, "last_name": 1, "photo_thumbnail": 1, "photo_url": 1, "photo": 1, "tags": 1, "vehicle": 1}
                )
                async for c in contacts_cursor:
                    photo = c.get("photo_thumbnail") or c.get("photo_url")
                    if not photo:
                        raw = c.get("photo") or ""
                        if raw and not raw.startswith("data:") and len(raw) < 500:
                            photo = raw
                    contacts_map[str(c["_id"])] = {
                        "id": str(c["_id"]),
                        "name": f"{c.get('first_name', '')} {c.get('last_name', '')}".strip(),
                        "photo": photo,
                        "tags": c.get("tags", []),
                        "vehicle": c.get("vehicle", ""),
                    }
            except Exception:
                pass

    # Classify visual type for social-feed rendering
    PHOTO_EVENTS = {
        "congrats_card_sent", "birthday_card_sent", "anniversary_card_sent",
        "holiday_card_sent", "thank_you_card_sent", "thankyou_card_sent",
        "welcome_card_sent", "delivery_photo",
    }
    ENGAGEMENT_EVENTS = {
        "digital_card_viewed", "showcase_viewed", "link_page_viewed",
        "link_clicked", "review_link_clicked", "congrats_card_viewed",
        "review_page_viewed", "training_video_clicked",
    }
    MILESTONE_EVENTS = {
        "new_contact_added", "campaign_enrolled", "review_submitted",
        "referral_made",
    }

    def classify_visual(evt_type, contact_info):
        if evt_type in PHOTO_EVENTS:
            return "photo_moment"
        if evt_type in MILESTONE_EVENTS:
            return "milestone"
        # Any event where the contact has a photo → show it as a photo moment
        if contact_info.get("photo"):
            return "photo_moment"
        if evt_type in ENGAGEMENT_EVENTS:
            return "engagement"
        return "text_event"

    # Format events with contact info
    feed_items = []
    for evt in recent_events:
        if evt.get("timestamp") and hasattr(evt["timestamp"], "isoformat"):
            evt["timestamp"] = _ts_iso(evt["timestamp"])
        cid = evt.get("contact_id")
        contact_info = contacts_map.get(cid, {"id": cid, "name": "Unknown", "photo": None, "tags": [], "vehicle": ""})
        is_inbound = evt.get("direction") == "inbound" or evt.get("event_type") == "customer_reply"
        # Always derive title from centralized event type labels (fixes old data with wrong titles)
        evt_type = evt.get("event_type", "custom")
        derived_title = get_event_label(evt_type)
        visual_type = classify_visual(evt_type, contact_info)
        feed_items.append({
            "type": "event",
            "event_type": evt_type,
            "visual_type": visual_type,
            "title": derived_title,
            "description": evt.get("description", ""),
            "icon": evt.get("icon", "flag"),
            "color": evt.get("color", "#8E8E93"),
            "timestamp": evt.get("timestamp"),
            "contact": contact_info,
            "category": evt.get("category", "custom"),
            "is_inbound": is_inbound,
            "channel": evt.get("channel"),
        })

    return {
        "feed": feed_items,
        "upcoming": [],
        "suggested": [],
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

    # ── Batch-load all messages needed by events in ONE query (fixes N+1) ──
    message_ids_needed = [
        ObjectId(e["message_id"]) for e in custom_events
        if e.get("message_id") and not e.get("full_content")
    ]
    messages_by_id: dict = {}
    if message_ids_needed:
        msg_docs = await db.messages.find(
            {"_id": {"$in": message_ids_needed}}, {"body": 1, "subject": 1}
        ).to_list(len(message_ids_needed))
        messages_by_id = {str(m["_id"]): m for m in msg_docs}

    for e in custom_events:
        if e.get("timestamp") and hasattr(e["timestamp"], "isoformat"):
            e["timestamp"] = _ts_iso(e["timestamp"])
        # Always derive title from centralized event type labels (fixes old data with wrong titles)
        # Exception: if a custom title was explicitly stored (e.g., custom card names), keep it
        etype = e.get("event_type", "")
        stored_title = e.get("title", "")
        if stored_title and etype.startswith("custom_") and "_card_" in etype:
            # Keep the explicitly stored card name (e.g., "'Before' Card Sent")
            pass
        else:
            e["title"] = get_event_label(etype)
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
        # Set icon/color/category for common types that may lack them
        if etype == "personal_sms":
            e["icon"] = e.get("icon", "chatbubble")
            e["color"] = e.get("color", "#34C759")
            e["category"] = e.get("category", "message")
        elif etype == "call_placed":
            e["icon"] = e.get("icon", "call")
            e["color"] = e.get("color", "#32ADE6")
        elif etype == "email_sent":
            e["icon"] = e.get("icon", "mail")
            e["color"] = e.get("color", "#007AFF")
            e["category"] = e.get("category", "message")
        elif etype == "email_failed":
            e["icon"] = e.get("icon", "mail")
            e["color"] = e.get("color", "#FF3B30")
            e["category"] = e.get("category", "message")
        elif etype == "sms_sent":
            e["icon"] = e.get("icon", "chatbubble")
            e["color"] = e.get("color", "#34C759")
            e["category"] = e.get("category", "message")
        elif etype == "sms_failed":
            e["icon"] = e.get("icon", "chatbubble")
            e["color"] = e.get("color", "#FF3B30")
            e["category"] = e.get("category", "message")
        elif etype == "task_created":
            e["icon"] = e.get("icon", "checkbox-outline")
            e["color"] = e.get("color", "#FF9500")
            e["category"] = e.get("category", "task")
        elif etype == "task_completed":
            e["icon"] = e.get("icon", "checkmark-circle")
            e["color"] = e.get("color", "#34C759")
            e["category"] = e.get("category", "task")
        elif etype == "lead_reassigned":
            e["icon"] = e.get("icon", "swap-horizontal")
            e["color"] = e.get("color", "#C9A962")
            e["category"] = e.get("category", "system")
        # Pull full message body from pre-loaded batch (no extra DB calls)
        if e.get("message_id") and not e.get("full_content"):
            msg = messages_by_id.get(e["message_id"])
            if msg:
                e["full_content"] = msg.get("body", "")
                if msg.get("subject"):
                    e["subject"] = msg["subject"]
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

    # ── Batch-load all campaigns needed in ONE query (fixes N+1) ──
    campaign_ids_needed = [
        ObjectId(e["campaign_id"]) for e in enrollments if e.get("campaign_id")
    ]
    campaigns_by_id: dict = {}
    if campaign_ids_needed:
        camp_docs = await db.campaigns.find(
            {"_id": {"$in": campaign_ids_needed}}, {"name": 1, "type": 1}
        ).to_list(len(campaign_ids_needed))
        campaigns_by_id = {str(c["_id"]): c for c in camp_docs}

    for e in enrollments:
        campaign = campaigns_by_id.get(e.get("campaign_id", ""))
        campaign_name = campaign.get("name", "Unknown") if campaign else "Unknown"
        ts = e.get("enrolled_at")
        if ts and hasattr(ts, "isoformat"):
            ts = _ts_iso(ts)
        events.append({
            "event_type": "campaign_enrolled",
            "icon": "rocket",
            "color": "#AF52DE",
            "title": "Enrolled in Campaign",
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
                "title": "Campaign Message Sent",
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

    # ── Batch-load card templates that are missing headlines (fixes N+1) ──
    card_ids_needed = [
        ObjectId(c["card_id"]) for c in congrats
        if not c.get("headline") and c.get("card_id")
    ]
    card_headlines: dict = {}
    if card_ids_needed:
        try:
            from bson import ObjectId as ObjId
            card_docs = await db.congrats_card_templates.find(
                {"_id": {"$in": card_ids_needed}}, {"headline": 1}
            ).to_list(len(card_ids_needed))
            card_headlines = {str(d["_id"]): d.get("headline", "") for d in card_docs}
        except Exception:
            pass

    for c in congrats:
        ts = c.get("sent_at")
        if ts and hasattr(ts, "isoformat"):
            ts = _ts_iso(ts)
        ct = c.get("card_type", "congrats")
        # Use headline for custom card types so the feed shows the actual card name
        from utils.event_types import get_card_sent_info
        card_headline = c.get("headline", "").strip()
        if not card_headline and c.get("card_id"):
            card_headline = card_headlines.get(c["card_id"], "")
        info = get_card_sent_info(ct, headline=card_headline)
        events.append({
            "event_type": info["event_type"],
            "icon": info["icon"],
            "color": info["color"],
            "title": info["label"],
            "description": c.get("message", "")[:60],
            "full_content": c.get("message", ""),
            "card_id": c.get("card_id"),
            "card_type": ct,
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

    # Count campaign enrollments — match on contact_id with ANY user field
    # (campaigns.py uses "user_id", campaign_lifecycle.py uses "salesman_id")
    campaign_count = await db.campaign_enrollments.count_documents(
        {"contact_id": contact_id}
    )

    # Count congrats cards
    card_count = await db.congrats_cards_sent.count_documents(
        {"contact_id": contact_id}
    )

    # Count broadcasts
    broadcast_count = await db.broadcast_recipients.count_documents(
        {"contact_id": contact_id}
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

    # Count referrals dynamically — contacts whose referred_by equals this contact
    referral_count = 0
    try:
        oid_str = str(contact_id)
        referral_count = await db.contacts.count_documents(
            {"$or": [{"referred_by": oid_str}, {"referred_by": contact_id}], "status": {"$ne": "hidden"}}
        )
    except Exception:
        pass

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
        "referral_count": referral_count,
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
    # Store the sharing channel if provided (e.g., sms, whatsapp, email, etc.)
    if event_data.get("channel"):
        event["channel"] = event_data["channel"]

    await db.contact_events.insert_one(event)
    event.pop("_id", None)
    if hasattr(event["timestamp"], "isoformat"):
        event["timestamp"] = _ts_iso(event["timestamp"])

    # Fire-and-forget milestone check for push notifications
    import asyncio as _aio
    _aio.create_task(_quick_milestone_check(user_id))

    return event



@router.patch("/{user_id}/{contact_id}/events/latest-channel")
async def update_latest_event_channel(user_id: str, contact_id: str, payload: dict):
    """Update the channel field on the most recent event for this user+contact."""
    channel = payload.get("channel")
    if not channel:
        raise HTTPException(status_code=400, detail="channel is required")
    db = get_db()
    result = await db.contact_events.find_one_and_update(
        {"user_id": user_id, "contact_id": contact_id},
        {"$set": {"channel": channel}},
        sort=[("timestamp", -1)],
    )
    return {"updated": result is not None, "channel": channel}


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
                    "title": "Birthday coming up!",
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
                    "title": "Anniversary coming up!",
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
                "title": "Time to reconnect",
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

        # Backfill photo from recent card if available
        if phone:
            try:
                normalized = "".join(c for c in phone if c.isdigit())
                suffix = normalized[-10:] if len(normalized) >= 10 else normalized
                recent_card = await db.congrats_cards.find_one(
                    {
                        "salesman_id": user_id,
                        "customer_phone": {"$regex": suffix},
                        "photo_path": {"$exists": True, "$ne": None},
                    },
                    sort=[("created_at", -1)],
                )
                if recent_card and recent_card.get("photo_path"):
                    photo_update = {
                        "photo_path": recent_card["photo_path"],
                        "photo_source": recent_card.get("card_type", "congrats"),
                    }
                    if recent_card.get("photo_thumb_path"):
                        photo_update["photo_thumb_path"] = recent_card["photo_thumb_path"]
                        thumb_url = f"/api/images/{recent_card['photo_thumb_path']}"
                        photo_update["photo_thumbnail"] = thumb_url
                        photo_update["photo_url"] = thumb_url
                    await db.contacts.update_one(
                        {"_id": contact["_id"]}, {"$set": photo_update}
                    )
                    logger.info(f"[find-or-create] Backfilled photo from card onto new contact {first_name} {last_name}")
            except Exception as e:
                logger.warning(f"[find-or-create] Photo backfill failed: {e}")

    contact_id = str(contact["_id"])

    # Log the event
    event_channel = payload.get("event_channel") or payload.get("channel")
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
    if event_channel:
        event["channel"] = event_channel
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



@router.post("/admin/fix-event-types")
async def fix_event_types_migration():
    """
    Data migration: Fix historically wrongly-typed contact_events.
    Scans events that have event_type 'congrats_card_sent' but whose linked
    short URL or congrats card record indicates a different card type.
    Also fixes the title field to match the centralized label.
    """
    db = get_db()
    import re

    fixed_count = 0
    errors = []

    # Strategy 1: Fix events that have a content field containing a congrats card URL
    # Look up the card_id from the URL and get the actual card_type
    card_url_re = re.compile(r'/congrats/([A-Za-z0-9\-]{6,36})')
    
    wrong_events = await db.contact_events.find(
        {"event_type": "congrats_card_sent"},
        {"_id": 1, "content": 1, "content_preview": 1, "description": 1, "metadata": 1}
    ).to_list(1000)

    for evt in wrong_events:
        # Try to find a card_id from event content or metadata
        card_id = None
        card_type = None

        # Check metadata first
        if evt.get("metadata") and evt["metadata"].get("card_type"):
            card_type = evt["metadata"]["card_type"]
        if evt.get("metadata") and evt["metadata"].get("card_id"):
            card_id = evt["metadata"]["card_id"]

        # Try to extract card_id from content/description
        if not card_id:
            text = evt.get("content") or evt.get("content_preview") or evt.get("description") or ""
            match = card_url_re.search(text)
            if match:
                card_id = match.group(1).split('?')[0]

        # Look up the actual card_type from the congrats_cards collection
        if card_id and not card_type:
            try:
                card = await db.congrats_cards.find_one({"card_id": card_id}, {"card_type": 1})
                if card:
                    card_type = card.get("card_type", "congrats")
            except Exception as e:
                errors.append(f"DB lookup failed for card_id {card_id}: {e}")

        # If we found a card_type that's NOT congrats, fix the event
        if card_type and card_type != "congrats":
            from utils.event_types import get_card_sent_info
            # Fetch headline for custom card types
            headline = ""
            if card_id and card_type not in {"congrats", "birthday", "anniversary", "thank_you", "holiday", "welcome"}:
                try:
                    from bson import ObjectId as ObjId
                    card_doc = await db.congrats_card_templates.find_one({"_id": ObjId(card_id)}, {"headline": 1})
                    headline = (card_doc or {}).get("headline", "")
                except Exception:
                    pass
            info = get_card_sent_info(card_type, headline=headline)
            new_event_type = info["event_type"]
            new_title = info["label"]
            
            await db.contact_events.update_one(
                {"_id": evt["_id"]},
                {"$set": {
                    "event_type": new_event_type,
                    "title": new_title,
                    "icon": info.get("icon", "gift"),
                    "color": info.get("color", "#C9A962"),
                }}
            )
            fixed_count += 1

    # Strategy 2: Fix ALL event titles to match centralized labels
    # This ensures even correctly-typed events have the right display title
    all_event_types = await db.contact_events.distinct("event_type")
    title_fixes = 0
    for et in all_event_types:
        correct_label = get_event_label(et)
        if correct_label and correct_label != et.replace("_", " ").title():
            # Update all events of this type to have the correct title
            result = await db.contact_events.update_many(
                {"event_type": et, "title": {"$ne": correct_label}},
                {"$set": {"title": correct_label}}
            )
            title_fixes += result.modified_count

    return {
        "success": True,
        "events_retyped": fixed_count,
        "titles_fixed": title_fixes,
        "errors": errors[:10],
        "message": f"Fixed {fixed_count} wrongly-typed events and {title_fixes} titles."
    }
