"""
CRM Timeline Export — Public activity timeline links with optional store-level PIN.
Allows stores to paste a link into their CRM that shows real-time activity for a contact.
"""
from fastapi import APIRouter, HTTPException, Request, Response
from bson import ObjectId
from datetime import datetime, timezone
from typing import Optional
import uuid
import logging

from routers.database import get_db

router = APIRouter(prefix="/crm", tags=["CRM Timeline"])
logger = logging.getLogger(__name__)


# ─── Token Management ────────────────────────────────────────────────

@router.post("/timeline-token/{user_id}/{contact_id}")
async def get_or_create_timeline_token(user_id: str, contact_id: str):
    """Generate or retrieve a secure CRM timeline token for a contact."""
    db = get_db()
    # Try exact match first, then fallback to just contact_id (for impersonation/hierarchy access)
    contact = await db.contacts.find_one(
        {"_id": ObjectId(contact_id), "user_id": user_id},
        {"crm_link_token": 1, "name": 1}
    )
    if not contact:
        contact = await db.contacts.find_one(
            {"_id": ObjectId(contact_id)},
            {"crm_link_token": 1, "name": 1}
        )
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    token = contact.get("crm_link_token")
    if not token:
        token = str(uuid.uuid4())
        await db.contacts.update_one(
            {"_id": ObjectId(contact_id)},
            {"$set": {"crm_link_token": token}}
        )

    return {"token": token, "contact_id": contact_id}


@router.post("/mark-copied/{user_id}/{contact_id}")
async def mark_crm_link_copied(user_id: str, contact_id: str):
    """Mark that the CRM link has been copied for this contact."""
    db = get_db()
    result = await db.contacts.update_one(
        {"_id": ObjectId(contact_id)},
        {"$set": {"crm_link_copied_at": datetime.now(timezone.utc)}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Contact not found")
    return {"success": True}


# ─── Public Timeline (no auth required) ──────────────────────────────

@router.get("/timeline/{token}")
async def get_public_timeline(token: str, pin: Optional[str] = None):
    """
    Public endpoint — returns the activity timeline for a contact.
    If the store has PIN protection enabled, requires a valid PIN.
    """
    db = get_db()

    # Find the contact by token (strip any trailing garbage that iOS share sheet may append)
    clean_token = token.split(" ")[0].split("%20")[0].strip()
    contact = await db.contacts.find_one(
        {"crm_link_token": clean_token},
        {"_id": 1, "name": 1, "first_name": 1, "last_name": 1, "phone": 1, "email": 1,
         "user_id": 1, "tags": 1, "photo": 1, "photo_thumbnail": 1, "photo_url": 1,
         "created_at": 1}
    )
    if not contact:
        raise HTTPException(status_code=404, detail="Timeline not found")

    contact_id_str = str(contact["_id"])
    contact_name = contact.get("name") or f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip() or "Unknown"
    user_id = contact.get("user_id")

    # Get the salesperson info
    try:
        user = await db.users.find_one(
            {"_id": ObjectId(user_id)},
            {"_id": 0, "name": 1, "store_id": 1, "photo": 1, "title": 1}
        )
    except Exception:
        user = None

    # Check store PIN if enabled
    store_id = user.get("store_id") if user else None
    store = None
    if store_id:
        try:
            store = await db.stores.find_one(
                {"_id": ObjectId(store_id)},
                {"_id": 0, "name": 1, "crm_pin_enabled": 1, "crm_pin": 1,
                 "primary_color": 1, "logo_url": 1}
            )
        except Exception:
            pass

    pin_required = store.get("crm_pin_enabled", False) if store else False
    store_pin = store.get("crm_pin", "") if store else ""

    if pin_required and store_pin:
        if not pin:
            return {
                "pin_required": True,
                "store_name": store.get("name", ""),
                "store_logo": store.get("logo_url", ""),
            }
        if pin != store_pin:
            raise HTTPException(status_code=403, detail="Invalid PIN")

    # ── Build unified timeline from ALL sources (mirrors contact detail page) ──

    from utils.event_types import get_event_label, get_card_sent_info

    def _ts(dt) -> str:
        if dt is None:
            return None
        s = dt.isoformat() if hasattr(dt, "isoformat") else str(dt)
        if not s.endswith("Z") and "+" not in s and s != "None":
            s += "Z"
        return s

    timeline = []

    # 1) contact_events
    raw_events = await db.contact_events.find(
        {"contact_id": contact_id_str, "user_id": user_id},
        {"_id": 0}
    ).sort("timestamp", -1).limit(500).to_list(500)
    for e in raw_events:
        etype = e.get("event_type", "custom")
        e["timestamp"] = _ts(e.get("timestamp"))
        # For custom card types: use stored title if available (it has the real card name)
        stored_title = e.get("title", "")
        if stored_title and etype.startswith("custom_") and "_card_" in etype:
            pass  # Keep the explicitly stored card name
        else:
            e["title"] = get_event_label(etype)
        # Carry over description / content
        if not e.get("description"):
            e["description"] = (e.get("content_preview") or e.get("content") or "")[:120]
        for k in list(e.keys()):
            if isinstance(e[k], ObjectId):
                e[k] = str(e[k])
        # Classify direction
        inbound_types = {
            "customer_reply", "digital_card_viewed", "congrats_card_viewed",
            "birthday_card_viewed", "thankyou_card_viewed", "thank_you_card_viewed",
            "holiday_card_viewed", "welcome_card_viewed", "anniversary_card_viewed",
            "review_page_viewed", "review_link_clicked", "review_submitted",
            "showcase_viewed", "link_page_viewed", "link_clicked",
        }
        if etype in inbound_types or etype == "customer_reply" or e.get("direction") == "inbound":
            e["direction"] = "inbound"
        else:
            e["direction"] = "outbound"
        timeline.append(e)

    # 2) Messages (actual SMS/email bodies) from conversations
    try:
        conv = await db.conversations.find_one(
            {"user_id": user_id, "contact_id": contact_id_str},
            {"_id": 1}
        )
        if conv:
            conv_id = str(conv["_id"])
            messages = await db.messages.find(
                {"conversation_id": conv_id},
                {"_id": 0, "conversation_id": 0}
            ).sort("timestamp", -1).limit(200).to_list(200)
            for m in messages:
                sender = m.get("sender", "user")
                msg_type = m.get("type", "sms")
                direction = "outbound" if sender == "user" else "inbound"
                icon = "chatbubble" if msg_type == "sms" else "mail"
                color = "#007AFF" if direction == "outbound" else "#8E8E93"
                body = m.get("body") or m.get("content") or ""
                timeline.append({
                    "event_type": f"message_{direction}",
                    "icon": icon,
                    "color": color,
                    "title": f"{'Sent' if direction == 'outbound' else 'Received'} {(m.get('channel') or msg_type or 'sms').upper().replace('SMS_PERSONAL','SMS')}",
                    "description": body[:120],
                    "full_content": body,
                    "channel": m.get("channel", msg_type),
                    "subject": m.get("subject"),
                    "timestamp": _ts(m.get("timestamp")),
                    "category": "message",
                    "direction": direction,
                })
    except Exception:
        pass

    # 3) Campaign enrollments
    try:
        enrollments = await db.campaign_enrollments.find(
            {"contact_id": contact_id_str, "user_id": user_id},
            {"_id": 0}
        ).sort("enrolled_at", -1).to_list(20)
        for en in enrollments:
            campaign = None
            if en.get("campaign_id"):
                try:
                    campaign = await db.campaigns.find_one(
                        {"_id": ObjectId(en["campaign_id"])},
                        {"_id": 0, "name": 1}
                    )
                except Exception:
                    pass
            cname = campaign.get("name", "Unknown") if campaign else "Unknown"
            timeline.append({
                "event_type": "campaign_enrolled",
                "icon": "rocket",
                "color": "#AF52DE",
                "title": "Enrolled in Campaign",
                "description": cname,
                "timestamp": _ts(en.get("enrolled_at")),
                "category": "campaign",
                "direction": "outbound",
            })
            for msg in (en.get("messages_sent") or []):
                timeline.append({
                    "event_type": "campaign_message_sent",
                    "icon": "megaphone",
                    "color": "#FF9500",
                    "title": "Campaign Message Sent",
                    "description": f"{cname} - Step {msg.get('step', '?')}",
                    "full_content": msg.get("body") or msg.get("message") or "",
                    "channel": msg.get("channel", "sms"),
                    "timestamp": _ts(msg.get("sent_at")),
                    "category": "campaign",
                    "direction": "outbound",
                })
    except Exception:
        pass

    # 4) Congrats / greeting cards
    try:
        congrats = await db.congrats_cards_sent.find(
            {"contact_id": contact_id_str, "user_id": user_id},
            {"_id": 0}
        ).sort("sent_at", -1).to_list(20)
        for c in congrats:
            ct = c.get("card_type", "congrats")
            headline = c.get("headline", "")
            info = get_card_sent_info(ct, headline=headline)
            timeline.append({
                "event_type": info["event_type"],
                "icon": info["icon"],
                "color": info["color"],
                "title": info["label"],
                "description": (c.get("message") or "")[:80],
                "timestamp": _ts(c.get("sent_at")),
                "category": "card",
                "direction": "outbound",
            })
    except Exception:
        pass

    # 5) Broadcast messages
    try:
        broadcasts = await db.broadcast_recipients.find(
            {"contact_id": contact_id_str, "user_id": user_id},
            {"_id": 0}
        ).sort("sent_at", -1).to_list(20)
        for b in broadcasts:
            full_msg = b.get("message") or ""
            timeline.append({
                "event_type": "broadcast_sent",
                "icon": "megaphone",
                "color": "#FF2D55",
                "title": "Broadcast Message",
                "description": full_msg[:80],
                "full_content": full_msg,
                "channel": b.get("channel", "sms"),
                "timestamp": _ts(b.get("sent_at")),
                "category": "broadcast",
                "direction": "outbound",
            })
    except Exception:
        pass

    # Sort everything by timestamp descending
    timeline.sort(key=lambda x: x.get("timestamp") or "", reverse=True)

    # Also fetch notes/voice notes
    notes = []
    try:
        notes_cursor = db.voice_notes.find(
            {"contact_id": contact_id_str, "user_id": user_id},
            {"_id": 0, "text": 1, "created_at": 1, "type": 1}
        ).sort("created_at", -1).limit(50)
        notes = await notes_cursor.to_list(50)
        for n in notes:
            if isinstance(n.get("created_at"), datetime):
                n["created_at"] = n["created_at"].isoformat() + "Z" if n["created_at"].tzinfo is None else n["created_at"].isoformat()
    except Exception:
        pass

    return {
        "pin_required": False,
        "contact": {
            "name": contact_name,
            "phone": contact.get("phone", ""),
            "email": contact.get("email", ""),
            "photo": contact.get("photo_thumbnail") or contact.get("photo_url") or contact.get("photo", ""),
            "tags": contact.get("tags", []),
            "created_at": contact.get("created_at").isoformat() + "Z" if isinstance(contact.get("created_at"), datetime) else contact.get("created_at", ""),
        },
        "salesperson": {
            "name": user.get("name", "") if user else "",
            "title": user.get("title", "") if user else "",
            "photo": user.get("photo", "") if user else "",
        },
        "store": {
            "name": store.get("name", "") if store else "",
            "color": store.get("primary_color", "#007AFF") if store else "#007AFF",
            "logo": store.get("logo_url", "") if store else "",
        },
        "events": timeline,
        "notes": notes,
        "total_events": len(timeline),
    }


# ─── PIN Verification (cookie-based session) ─────────────────────────

@router.post("/timeline/{token}/verify-pin")
async def verify_timeline_pin(token: str, data: dict):
    """Verify the store PIN for a timeline link. Returns a session token."""
    db = get_db()
    pin = data.get("pin", "")

    contact = await db.contacts.find_one(
        {"crm_link_token": token},
        {"user_id": 1}
    )
    if not contact:
        raise HTTPException(status_code=404, detail="Timeline not found")

    user_id = str(contact.get("user_id", ""))
    user = await db.users.find_one({"_id": ObjectId(user_id)}, {"store_id": 1})
    store_id = user.get("store_id") if user else None

    if not store_id:
        raise HTTPException(status_code=400, detail="No store configured")

    store = await db.stores.find_one(
        {"_id": ObjectId(store_id)},
        {"crm_pin": 1, "crm_pin_enabled": 1}
    )

    if not store or not store.get("crm_pin_enabled"):
        return {"verified": True}

    if pin != store.get("crm_pin", ""):
        raise HTTPException(status_code=403, detail="Invalid PIN")

    # Return a session token the frontend can store
    session_token = str(uuid.uuid4())
    await db.crm_pin_sessions.insert_one({
        "session_token": session_token,
        "store_id": str(store_id),
        "created_at": datetime.now(timezone.utc),
    })

    return {"verified": True, "session_token": session_token}


@router.get("/timeline/{token}/check-session")
async def check_pin_session(token: str, session: Optional[str] = None):
    """Check if a session token is valid for this timeline's store."""
    if not session:
        return {"valid": False}

    db = get_db()
    contact = await db.contacts.find_one({"crm_link_token": token}, {"user_id": 1})
    if not contact:
        return {"valid": False}

    user = await db.users.find_one({"_id": ObjectId(str(contact["user_id"]))}, {"store_id": 1})
    store_id = str(user.get("store_id", "")) if user else ""

    s = await db.crm_pin_sessions.find_one({
        "session_token": session,
        "store_id": store_id,
    })
    return {"valid": bool(s)}


# ─── Store PIN Settings ──────────────────────────────────────────────

@router.get("/pin-settings/{store_id}")
async def get_pin_settings(store_id: str):
    """Get CRM PIN settings for a store."""
    db = get_db()
    store = await db.stores.find_one(
        {"_id": ObjectId(store_id)},
        {"_id": 0, "crm_pin_enabled": 1, "crm_pin": 1}
    )
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    return {
        "crm_pin_enabled": store.get("crm_pin_enabled", False),
        "crm_pin": store.get("crm_pin", ""),
    }


@router.put("/pin-settings/{store_id}")
async def update_pin_settings(store_id: str, data: dict):
    """Update CRM PIN settings for a store."""
    db = get_db()
    update = {}
    if "crm_pin_enabled" in data:
        update["crm_pin_enabled"] = bool(data["crm_pin_enabled"])
    if "crm_pin" in data:
        pin = str(data["crm_pin"]).strip()
        if pin and (len(pin) < 4 or len(pin) > 8):
            raise HTTPException(status_code=400, detail="PIN must be 4-8 digits")
        update["crm_pin"] = pin

    if not update:
        raise HTTPException(status_code=400, detail="No fields to update")

    result = await db.stores.update_one(
        {"_id": ObjectId(store_id)},
        {"$set": update}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Store not found")

    return {"success": True, **update}


# ─── CRM Export Stats ─────────────────────────────────────────────────

@router.get("/export-stats/{user_id}")
async def get_crm_export_stats(user_id: str):
    """Get stats on how many contacts have CRM links vs not."""
    db = get_db()
    total = await db.contacts.count_documents({"user_id": user_id})
    exported = await db.contacts.count_documents({
        "user_id": user_id,
        "crm_link_copied_at": {"$exists": True, "$ne": None}
    })
    return {
        "total_contacts": total,
        "crm_linked": exported,
        "not_linked": total - exported,
    }


# ─── CRM Adoption Dashboard ──────────────────────────────────────────

@router.get("/adoption-dashboard/{user_id}")
async def get_crm_adoption_dashboard(user_id: str):
    """
    Manager-level dashboard showing CRM link adoption across the team.
    Returns per-salesperson stats and recent linking activity.
    """
    db = get_db()

    # Get the requesting user's store
    user = await db.users.find_one({"_id": ObjectId(user_id)}, {"store_id": 1})
    if not user or not user.get("store_id"):
        raise HTTPException(status_code=404, detail="User or store not found")

    store_id = str(user["store_id"])

    # Get all users in the store
    team_cursor = db.users.find(
        {"store_id": store_id, "status": {"$ne": "deleted"}},
        {"_id": 1, "name": 1, "photo": 1, "title": 1, "role": 1}
    )
    team = await team_cursor.to_list(100)

    # Build per-user stats
    members = []
    total_contacts = 0
    total_linked = 0

    for member in team:
        uid = str(member["_id"])
        mc = await db.contacts.count_documents({"user_id": uid})
        ml = await db.contacts.count_documents({
            "user_id": uid,
            "crm_link_copied_at": {"$exists": True, "$ne": None}
        })
        total_contacts += mc
        total_linked += ml
        members.append({
            "user_id": uid,
            "name": member.get("name", "Unknown"),
            "photo": member.get("photo", ""),
            "title": member.get("title", ""),
            "role": member.get("role", ""),
            "total_contacts": mc,
            "crm_linked": ml,
            "not_linked": mc - ml,
            "pct": round((ml / mc * 100) if mc > 0 else 0, 1),
        })

    # Sort by linked percentage descending
    members.sort(key=lambda m: m["pct"], reverse=True)

    # Recent CRM link activity (last 20 links copied across the store)
    all_user_ids = [str(m["_id"]) for m in team]
    recent_cursor = db.contacts.find(
        {
            "user_id": {"$in": all_user_ids},
            "crm_link_copied_at": {"$exists": True, "$ne": None},
        },
        {"_id": 0, "first_name": 1, "last_name": 1, "name": 1, "phone": 1,
         "user_id": 1, "crm_link_copied_at": 1}
    ).sort("crm_link_copied_at", -1).limit(20)
    recent_raw = await recent_cursor.to_list(20)

    # Build a user_id -> name map
    name_map = {str(m["_id"]): m.get("name", "?") for m in team}

    recent = []
    for r in recent_raw:
        cname = r.get("name") or f"{r.get('first_name', '')} {r.get('last_name', '')}".strip() or r.get("phone", "?")
        ts = r.get("crm_link_copied_at")
        if isinstance(ts, datetime):
            ts = ts.isoformat() + "Z" if ts.tzinfo is None else ts.isoformat()
        recent.append({
            "contact_name": cname,
            "salesperson": name_map.get(r.get("user_id", ""), "?"),
            "copied_at": ts,
        })

    return {
        "store_id": store_id,
        "total_contacts": total_contacts,
        "total_linked": total_linked,
        "total_not_linked": total_contacts - total_linked,
        "overall_pct": round((total_linked / total_contacts * 100) if total_contacts > 0 else 0, 1),
        "members": members,
        "recent_activity": recent,
    }
