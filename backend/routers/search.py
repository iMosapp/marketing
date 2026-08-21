"""
Search router - handles global search across contacts, conversations, and campaigns
"""
from fastapi import APIRouter, HTTPException, Query
from bson import ObjectId
from datetime import datetime
from typing import Optional, List
import logging
import re

from routers.database import get_db, get_data_filter

router = APIRouter(prefix="/search", tags=["Search"])
logger = logging.getLogger(__name__)


@router.get("/{user_id}")
async def global_search(
    user_id: str,
    q: str = Query(..., min_length=1, description="Search query"),
    types: Optional[str] = Query(None, description="Comma-separated types: contacts,conversations,campaigns"),
    limit: int = Query(20, ge=1, le=50, description="Max results per type")
):
    """
    Global search across contacts, conversations, and campaigns.
    Returns categorized results with relevance scoring.
    """
    # Get role-based data filter
    base_filter = await get_data_filter(user_id)
    
    # Parse types filter
    search_types = types.split(",") if types else ["contacts", "conversations", "campaigns"]
    search_types = [t.strip().lower() for t in search_types]
    
    results = {
        "query": q,
        "contacts": [],
        "conversations": [],
        "campaigns": [],
        "total_count": 0
    }
    
    # Create case-insensitive regex pattern
    search_pattern = {"$regex": re.escape(q), "$options": "i"}
    
    # Search Contacts
    if "contacts" in search_types:
        contact_query = {
            "$and": [
                base_filter,
                {"$or": [
                    {"first_name": search_pattern},
                    {"last_name": search_pattern},
                    {"phone": search_pattern},
                    {"email": search_pattern},
                    {"notes": search_pattern},
                    {"tags": search_pattern},
                    {"vehicle": search_pattern}
                ]}
            ]
        }
        
        contacts = await get_db().contacts.find(contact_query, {"photo": 0}).limit(limit).to_list(limit)
        
        for contact in contacts:
            results["contacts"].append({
                "id": str(contact["_id"]),
                "type": "contact",
                "title": f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip(),
                "subtitle": contact.get("phone", "") or contact.get("email", ""),
                "icon": "person",
                "color": "#007AFF",
                "tags": contact.get("tags", []),
                "photo": contact.get("photo_thumbnail") or contact.get("photo_url"),
                "match_field": _get_match_field(contact, q)
            })
    
    # Search Conversations
    if "conversations" in search_types:
        # First get conversations accessible to user
        conversations = await get_db().conversations.find(base_filter).limit(500).to_list(500)
        
        matching_conversations = []
        for conv in conversations:
            conv_id = str(conv["_id"])
            
            # Get contact info for this conversation
            contact = None
            if conv.get("contact_id"):
                try:
                    contact = await get_db().contacts.find_one({"_id": ObjectId(conv["contact_id"])})
                except Exception:
                    contact = await get_db().contacts.find_one({"_id": conv["contact_id"]})
            
            contact_name = ""
            if contact:
                contact_name = f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip()
            
            # Check if contact name matches
            name_match = q.lower() in contact_name.lower() if contact_name else False
            
            # Check if any messages in this conversation match
            message_match = await get_db().messages.find_one({
                "conversation_id": conv_id,
                "content": search_pattern
            })
            
            if name_match or message_match:
                # Get last message preview
                last_msg = await get_db().messages.find_one(
                    {"conversation_id": conv_id},
                    sort=[("timestamp", -1)]
                )
                
                matching_conversations.append({
                    "id": conv_id,
                    "type": "conversation",
                    "title": contact_name or "Unknown Contact",
                    "subtitle": last_msg["content"][:100] if last_msg else "No messages",
                    "icon": "chatbubble",
                    "color": "#34C759",
                    "unread": conv.get("unread", False),
                    "ai_outcome": conv.get("ai_outcome"),
                    "status": conv.get("status", "active"),
                    "last_message_at": conv.get("last_message_at").isoformat() if conv.get("last_message_at") else None,
                    "match_field": "name" if name_match else "message"
                })
                
                if len(matching_conversations) >= limit:
                    break
        
        results["conversations"] = matching_conversations
    
    # Search Campaigns
    if "campaigns" in search_types:
        campaign_query = {
            "$and": [
                base_filter,
                {"$or": [
                    {"name": search_pattern},
                    {"message_template": search_pattern},
                    {"segment_tags": search_pattern}
                ]}
            ]
        }
        
        campaigns = await get_db().campaigns.find(campaign_query).limit(limit).to_list(limit)
        
        for camp in campaigns:
            # Get enrollment count
            enrollment_count = await get_db().campaign_enrollments.count_documents({
                "campaign_id": str(camp["_id"]),
                "status": "active"
            })
            
            results["campaigns"].append({
                "id": str(camp["_id"]),
                "type": "campaign",
                "title": camp.get("name", "Unnamed Campaign"),
                "subtitle": f"{enrollment_count} contacts enrolled",
                "icon": "megaphone",
                "color": "#FF9500",
                "active": camp.get("active", False),
                "type_name": camp.get("type", "custom"),
                "match_field": _get_match_field(camp, q)
            })
    
    # Calculate total count
    results["total_count"] = (
        len(results["contacts"]) + 
        len(results["conversations"]) + 
        len(results["campaigns"])
    )
    
    return results


def _get_match_field(doc: dict, query: str) -> str:
    """Determine which field matched the search query"""
    query_lower = query.lower()
    
    # Check common fields
    for field in ["first_name", "last_name", "name", "phone", "email", "notes", "message_template"]:
        if field in doc and doc[field]:
            if query_lower in str(doc[field]).lower():
                return field
    
    # Check tags
    if "tags" in doc:
        for tag in doc.get("tags", []):
            if query_lower in tag.lower():
                return "tags"
    
    return "other"


def _make_snippet(text: str, q: str, pad: int = 70) -> str:
    idx = text.lower().find(q.lower())
    if idx == -1:
        return text[:140] + ("…" if len(text) > 140 else "")
    s = max(0, idx - pad)
    e = min(len(text), idx + len(q) + pad)
    return ("…" if s > 0 else "") + text[s:e].strip() + ("…" if e < len(text) else "")


@router.get("/{user_id}/messages")
async def search_messages(
    user_id: str,
    q: str = Query(..., min_length=2, description="Keyword to find in messages and call transcripts"),
    limit: int = Query(30, ge=1, le=100),
):
    """Deep keyword search across SMS message text and call transcripts.
    Returns message-level hits so the UI can jump straight to the match."""
    db = get_db()
    base_filter = await get_data_filter(user_id)
    rx = {"$regex": re.escape(q), "$options": "i"}

    convs = await db.conversations.find(
        base_filter, {"contact_id": 1, "contact_name": 1, "contact_phone": 1}
    ).limit(2000).to_list(2000)
    conv_map = {str(c["_id"]): c for c in convs}

    results = []
    seen_call_sids = set()

    msgs = await db.messages.find({
        "conversation_id": {"$in": list(conv_map.keys())},
        "$or": [{"content": rx}, {"transcript": rx}],
    }).sort("timestamp", -1).limit(limit).to_list(limit)

    for m in msgs:
        conv = conv_map.get(m.get("conversation_id", ""), {})
        is_call = m.get("type") == "call_log" or m.get("channel") == "voice"
        transcript = m.get("transcript", "") or ""
        content = m.get("content", "") or ""
        hay = transcript if (is_call and q.lower() in transcript.lower()) else content
        if q.lower() not in hay.lower():
            hay = transcript or content
        if m.get("call_sid"):
            seen_call_sids.add(m["call_sid"])
        ts = m.get("timestamp")
        results.append({
            "message_id": str(m["_id"]),
            "conversation_id": m.get("conversation_id"),
            "contact_id": str(conv.get("contact_id", "") or ""),
            "contact_name": conv.get("contact_name") or conv.get("contact_phone") or "Unknown",
            "source": "call" if is_call else "sms",
            "sender": m.get("sender", ""),
            "snippet": _make_snippet(hay, q),
            "auto_tags": m.get("auto_tags", []),
            "timestamp": ts.isoformat() if hasattr(ts, "isoformat") else str(ts or ""),
        })

    # Call recordings whose transcript matched but have no thread message
    calls = await db.call_logs.find(
        {"$and": [base_filter, {"transcript": rx}]}
    ).sort("timestamp", -1).limit(limit).to_list(limit)

    for c in calls:
        if c.get("call_sid") in seen_call_sids:
            continue
        conv_id = None
        message_id = None
        msg = await db.messages.find_one({"call_sid": c.get("call_sid"), "type": "call_log"}, {"_id": 1, "conversation_id": 1})
        if msg:
            message_id = str(msg["_id"])
            conv_id = msg.get("conversation_id")
        elif c.get("contact_id"):
            conv = await db.conversations.find_one({"contact_id": c["contact_id"]}, {"_id": 1})
            if conv:
                conv_id = str(conv["_id"])
        ts = c.get("timestamp")
        results.append({
            "message_id": message_id,
            "conversation_id": conv_id,
            "contact_id": str(c.get("contact_id", "") or ""),
            "contact_name": c.get("contact_name") or c.get("contact_phone") or "Unknown",
            "source": "call",
            "sender": "",
            "snippet": _make_snippet(c.get("transcript", ""), q),
            "auto_tags": c.get("auto_tags", []),
            "timestamp": ts.isoformat() if hasattr(ts, "isoformat") else str(ts or ""),
        })

    results.sort(key=lambda r: r.get("timestamp") or "", reverse=True)
    results = results[:limit]
    return {"query": q, "results": results, "total": len(results)}


@router.get("/{user_id}/suggestions")
async def get_search_suggestions(
    user_id: str,
    q: str = Query(..., min_length=1, description="Partial search query"),
    limit: int = Query(5, ge=1, le=10)
):
    """
    Get search suggestions based on partial query.
    Returns contact names and campaign names that match.
    """
    base_filter = await get_data_filter(user_id)
    search_pattern = {"$regex": f"^{re.escape(q)}", "$options": "i"}
    
    suggestions = []
    
    # Get contact name suggestions
    contacts = await get_db().contacts.find({
        "$and": [
            base_filter,
            {"$or": [
                {"first_name": search_pattern},
                {"last_name": search_pattern}
            ]}
        ]
    }).limit(limit).to_list(limit)
    
    for contact in contacts:
        name = f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip()
        if name and name not in suggestions:
            suggestions.append(name)
    
    # Get campaign name suggestions
    if len(suggestions) < limit:
        campaigns = await get_db().campaigns.find({
            "$and": [
                base_filter,
                {"name": search_pattern}
            ]
        }).limit(limit - len(suggestions)).to_list(limit - len(suggestions))
        
        for camp in campaigns:
            if camp.get("name") and camp["name"] not in suggestions:
                suggestions.append(camp["name"])
    
    return {"suggestions": suggestions[:limit]}
