"""Keyword auto-tagging engine — scans SMS + call transcripts against user-defined rules."""
import asyncio
import logging
import re
from datetime import datetime, timezone
from bson import ObjectId

from routers.database import get_db

logger = logging.getLogger(__name__)

STARTER_RULES = [
    {"tag": "Appointment", "keywords": ["appointment", "appointments", "appt"], "color": "#007AFF"},
    {"tag": "Trade", "keywords": ["trade", "trade-in", "trade in"], "color": "#FF9500"},
    {"tag": "Financing", "keywords": ["financing", "finance", "loan", "apr", "credit"], "color": "#34C759"},
    {"tag": "Test Drive", "keywords": ["test drive", "test-drive"], "color": "#AF52DE"},
    {"tag": "Price", "keywords": ["price", "pricing", "payment", "payments", "monthly"], "color": "#FF2D55"},
]


async def ensure_starter_rules(user_id: str):
    """Idempotently seed the 5 starter rules for a user (once, ever)."""
    db = get_db()
    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)}, {"keyword_rules_seeded": 1})
    except Exception:
        return
    if not user or user.get("keyword_rules_seeded"):
        return
    count = await db.keyword_rules.count_documents({"user_id": user_id})
    if count == 0:
        now = datetime.now(timezone.utc)
        await db.keyword_rules.insert_many([
            {"user_id": user_id, "tag": r["tag"], "keywords": r["keywords"], "color": r["color"],
             "enabled": True, "is_starter": True, "created_at": now}
            for r in STARTER_RULES
        ])
        logger.info(f"[KeywordTag] Seeded {len(STARTER_RULES)} starter rules for user {user_id}")
    await db.users.update_one({"_id": ObjectId(user_id)}, {"$set": {"keyword_rules_seeded": True}})


def _build_pattern(keyword: str):
    kw = keyword.strip()
    if not kw:
        return None
    parts = [re.escape(p) for p in kw.split()]
    return re.compile(r"\b" + r"[\s\-]+".join(parts) + r"\b", re.IGNORECASE)


def _make_snippet(text: str, start: int, end: int) -> str:
    s = max(0, start - 60)
    e = min(len(text), end + 60)
    return ("…" if s > 0 else "") + text[s:e].strip() + ("…" if e < len(text) else "")


async def run_keyword_tagging(user_id: str, contact_id: str, text: str,
                              source_type: str, source_id: str = None,
                              conversation_id: str = None):
    """Match enabled keyword rules against text. Applies tags to the contact,
    marks the source message/call, and records a trigger event. Returns applied tags."""
    if not user_id or not contact_id or not text or not text.strip():
        return []
    db = get_db()
    await ensure_starter_rules(user_id)

    user = await db.users.find_one({"_id": ObjectId(user_id)}, {"store_id": 1})
    store_id = (user or {}).get("store_id")
    scope = [{"user_id": user_id}]
    if store_id:
        scope.append({"store_id": store_id})
    rules = await db.keyword_rules.find({"$or": scope, "enabled": True}).to_list(200)
    if not rules:
        return []

    try:
        contact = await db.contacts.find_one({"_id": ObjectId(contact_id)}, {"first_name": 1, "last_name": 1, "name": 1})
    except Exception:
        contact = None
    contact_name = ""
    if contact:
        contact_name = contact.get("name") or f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip()

    applied = []
    now = datetime.now(timezone.utc)

    for rule in rules:
        matched_kw = None
        snippet = ""
        for kw in rule.get("keywords", []):
            pat = _build_pattern(kw)
            if not pat:
                continue
            m = pat.search(text)
            if m:
                matched_kw = kw
                snippet = _make_snippet(text, m.start(), m.end())
                break
        if not matched_kw:
            continue

        tag = rule.get("tag", "").strip()
        if not tag:
            continue

        res = await db.contacts.update_one({"_id": ObjectId(contact_id)}, {"$addToSet": {"tags": tag}})
        await _ensure_tag_doc(db, user_id, store_id, tag, rule.get("color"))

        # Record the trigger event (idempotent per source+tag+contact)
        await db.keyword_tag_events.update_one(
            {"contact_id": contact_id, "tag": tag, "source_id": source_id or ""},
            {"$setOnInsert": {
                "user_id": user_id,
                "contact_id": contact_id,
                "contact_name": contact_name,
                "tag": tag,
                "keyword": matched_kw,
                "rule_id": str(rule["_id"]),
                "source_type": source_type,
                "source_id": source_id,
                "conversation_id": conversation_id,
                "snippet": snippet,
                "newly_tagged": res.modified_count > 0,
                "created_at": now,
            }},
            upsert=True,
        )
        applied.append(tag)

    # Mark the triggering source doc with the applied tags
    if applied and source_id:
        try:
            if source_type == "sms":
                await db.messages.update_one({"_id": ObjectId(source_id)}, {"$addToSet": {"auto_tags": {"$each": applied}}})
            elif source_type == "call":
                await db.call_logs.update_one({"call_sid": source_id}, {"$addToSet": {"auto_tags": {"$each": applied}}})
                await db.messages.update_one({"call_sid": source_id, "type": "call_log"}, {"$addToSet": {"auto_tags": {"$each": applied}}})
        except Exception as mark_err:
            logger.warning(f"[KeywordTag] Failed to mark source {source_id}: {mark_err}")

    if applied:
        logger.info(f"[KeywordTag] Applied {applied} to contact {contact_id} ({contact_name}) from {source_type}")
    return applied


async def _ensure_tag_doc(db, user_id: str, store_id, tag_name: str, color: str = None):
    """Make sure a tag document exists so the tag shows in the Tags manager."""
    rx = {"$regex": f"^{re.escape(tag_name)}$", "$options": "i"}
    scope = [{"user_id": user_id, "name": rx}]
    if store_id:
        scope.append({"store_id": store_id, "name": rx})
    existing = await db.tags.find_one({"$or": scope})
    if existing:
        return
    await db.tags.insert_one({
        "name": tag_name,
        "color": color or "#5856D6",
        "icon": "pricetag",
        "scope": "personal",
        "user_id": user_id,
        "status": "approved",
        "auto_keyword": True,
        "created_at": datetime.now(timezone.utc),
    })


def schedule_keyword_tagging(user_id: str, contact_id: str, text: str,
                             source_type: str, source_id: str = None,
                             conversation_id: str = None):
    """Fire-and-forget wrapper so webhooks/send paths never block or fail."""
    async def _run():
        try:
            await run_keyword_tagging(user_id, contact_id, text, source_type, source_id, conversation_id)
        except Exception as e:
            logger.warning(f"[KeywordTag] Tagging task failed: {e}")
    try:
        asyncio.create_task(_run())
    except Exception as e:
        logger.warning(f"[KeywordTag] Could not schedule tagging task: {e}")
