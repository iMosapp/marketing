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

READY_TO_BUY_RULE = {
    "tag": "Ready to Buy",
    "keywords": ["ready to buy", "ready to purchase", "coming in today", "coming in now", "on my way", "buy today", "where do i sign"],
    "color": "#FF3B30",
    "alert_enabled": True,
}


async def ensure_starter_rules(user_id: str):
    """Idempotently seed starter rules. v2 backfills the Ready to Buy alert rule
    for users who were seeded before it existed."""
    db = get_db()
    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)}, {"keyword_rules_seeded": 1, "keyword_rules_seeded_v2": 1})
    except Exception:
        return
    if not user:
        return
    now = datetime.now(timezone.utc)

    if not user.get("keyword_rules_seeded"):
        count = await db.keyword_rules.count_documents({"user_id": user_id})
        if count == 0:
            all_rules = STARTER_RULES + [READY_TO_BUY_RULE]
            await db.keyword_rules.insert_many([
                {"user_id": user_id, "tag": r["tag"], "keywords": r["keywords"], "color": r["color"],
                 "enabled": True, "alert_enabled": r.get("alert_enabled", False), "is_starter": True, "created_at": now}
                for r in all_rules
            ])
            logger.info(f"[KeywordTag] Seeded {len(all_rules)} starter rules for user {user_id}")
        await db.users.update_one({"_id": ObjectId(user_id)}, {"$set": {"keyword_rules_seeded": True, "keyword_rules_seeded_v2": True}})
        return

    if not user.get("keyword_rules_seeded_v2"):
        existing = await db.keyword_rules.find_one({"user_id": user_id, "tag": {"$regex": "^ready to buy$", "$options": "i"}})
        if not existing:
            r = READY_TO_BUY_RULE
            await db.keyword_rules.insert_one({
                "user_id": user_id, "tag": r["tag"], "keywords": r["keywords"], "color": r["color"],
                "enabled": True, "alert_enabled": True, "is_starter": True, "created_at": now,
            })
            logger.info(f"[KeywordTag] Backfilled Ready to Buy rule for user {user_id}")
        await db.users.update_one({"_id": ObjectId(user_id)}, {"$set": {"keyword_rules_seeded_v2": True}})


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
                              conversation_id: str = None, sender: str = None):
    """Match enabled keyword rules against text. Applies tags to the contact,
    marks the source message/call, and records a trigger event. Returns applied tags."""
    if not user_id or not contact_id or not text or not text.strip():
        return []
    db = get_db()
    await ensure_starter_rules(user_id)

    user = await db.users.find_one({"_id": ObjectId(user_id)}, {"store_id": 1, "organization_id": 1, "org_id": 1})
    store_id = (user or {}).get("store_id")
    org_id = (user or {}).get("organization_id") or (user or {}).get("org_id")
    scope = [{"user_id": user_id}]
    if store_id:
        scope.append({"store_id": store_id})
    if org_id:
        scope.append({"org_id": org_id})
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
        ev_res = await db.keyword_tag_events.update_one(
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

        # ── Instant keyword alert (customer messages + calls only) ──────────
        if (ev_res.upserted_id is not None and rule.get("alert_enabled")
                and (source_type == "call" or sender == "contact")):
            try:
                alert_title = f"🔥 \"{matched_kw}\" — {contact_name or 'Customer'}"
                alert_body = snippet[:140] if snippet else f"Keyword '{matched_kw}' detected"
                await db.notifications.insert_one({
                    "user_id": user_id,
                    "type": "keyword_alert",
                    "priority": "high",
                    "title": alert_title,
                    "message": alert_body,
                    "contact_id": contact_id,
                    "conversation_id": conversation_id,
                    "read": False,
                    "dismissed": False,
                    "created_at": now,
                })
                from routers.push_notifications import send_push_to_user
                push_url = f"/thread/{conversation_id}" if conversation_id else (f"/contact/{contact_id}" if contact_id else "/")
                await send_push_to_user(user_id, alert_title, alert_body, url=push_url, icon="flame")
                logger.info(f"[KeywordTag] Alert sent to {user_id} for '{matched_kw}' ({contact_name})")
            except Exception as alert_err:
                logger.warning(f"[KeywordTag] alert failed: {alert_err}")

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
                             conversation_id: str = None, sender: str = None):
    """Fire-and-forget wrapper so webhooks/send paths never block or fail."""
    async def _run():
        try:
            await run_keyword_tagging(user_id, contact_id, text, source_type, source_id, conversation_id, sender)
        except Exception as e:
            logger.warning(f"[KeywordTag] Tagging task failed: {e}")
    try:
        asyncio.create_task(_run())
    except Exception as e:
        logger.warning(f"[KeywordTag] Could not schedule tagging task: {e}")


async def scan_history_for_rule(user_id: str, rule: dict) -> dict:
    """Retroactively scan the user's past messages + call transcripts for one rule.
    Applies tags/events/source-marks exactly like the live engine. Never alerts."""
    db = get_db()
    tag = (rule.get("tag") or "").strip()
    pats = [(kw, _build_pattern(kw)) for kw in rule.get("keywords", [])]
    pats = [(k, p) for k, p in pats if p]
    summary = {"messages_matched": 0, "calls_matched": 0, "contacts_tagged": 0}
    if not tag or not pats:
        return summary

    user = await db.users.find_one({"_id": ObjectId(user_id)}, {"store_id": 1})
    store_id = (user or {}).get("store_id")

    convs = await db.conversations.find({"user_id": user_id}, {"contact_id": 1}).limit(5000).to_list(5000)
    conv_contact = {str(c["_id"]): str(c.get("contact_id") or "") for c in convs}

    tagged_contacts = set()
    name_cache: dict = {}
    now = datetime.now(timezone.utc)

    async def _get_name(cid):
        if cid in name_cache:
            return name_cache[cid]
        try:
            c = await db.contacts.find_one({"_id": ObjectId(cid)}, {"first_name": 1, "last_name": 1, "name": 1})
        except Exception:
            c = None
        nm = (c or {}).get("name") or f"{(c or {}).get('first_name', '')} {(c or {}).get('last_name', '')}".strip()
        name_cache[cid] = nm
        return nm

    async def _apply(contact_id, text, source_type, source_id, conversation_id):
        for kw, pat in pats:
            m = pat.search(text)
            if not m:
                continue
            snippet = _make_snippet(text, m.start(), m.end())
            await db.contacts.update_one({"_id": ObjectId(contact_id)}, {"$addToSet": {"tags": tag}})
            await _ensure_tag_doc(db, user_id, store_id, tag, rule.get("color"))
            await db.keyword_tag_events.update_one(
                {"contact_id": contact_id, "tag": tag, "source_id": source_id or ""},
                {"$setOnInsert": {
                    "user_id": user_id, "contact_id": contact_id,
                    "contact_name": await _get_name(contact_id),
                    "tag": tag, "keyword": kw, "rule_id": str(rule["_id"]),
                    "source_type": source_type, "source_id": source_id,
                    "conversation_id": conversation_id, "snippet": snippet,
                    "retro_scan": True, "newly_tagged": True, "created_at": now,
                }},
                upsert=True,
            )
            tagged_contacts.add(contact_id)
            return True
        return False

    # ── Messages (content + call transcripts embedded on thread messages) ────
    broad_or = []
    for kw, _ in pats:
        rx = {"$regex": re.escape(kw), "$options": "i"}
        broad_or += [{"content": rx}, {"transcript": rx}]
    msgs = await db.messages.find(
        {"conversation_id": {"$in": list(conv_contact.keys())}, "$or": broad_or},
        {"content": 1, "transcript": 1, "conversation_id": 1, "call_sid": 1, "type": 1},
    ).sort("timestamp", -1).limit(5000).to_list(5000)

    handled_call_sids = set()
    for m in msgs:
        conv_id = m.get("conversation_id", "")
        contact_id = conv_contact.get(conv_id)
        if not contact_id:
            continue
        text = f"{m.get('content', '') or ''} {m.get('transcript', '') or ''}"
        is_call = m.get("type") == "call_log" or bool(m.get("call_sid"))
        source_type = "call" if is_call else "sms"
        source_id = m.get("call_sid") if is_call and m.get("call_sid") else str(m["_id"])
        hit = await _apply(contact_id, text, source_type, source_id, conv_id)
        if hit:
            if is_call:
                summary["calls_matched"] += 1
                if m.get("call_sid"):
                    handled_call_sids.add(m["call_sid"])
                    await db.call_logs.update_one({"call_sid": m["call_sid"]}, {"$addToSet": {"auto_tags": tag}})
                await db.messages.update_one({"_id": m["_id"]}, {"$addToSet": {"auto_tags": tag}})
            else:
                summary["messages_matched"] += 1
                await db.messages.update_one({"_id": m["_id"]}, {"$addToSet": {"auto_tags": tag}})

    # ── Standalone call_logs (no thread message) ──────────────────────────────
    call_or = [{"transcript": {"$regex": re.escape(kw), "$options": "i"}} for kw, _ in pats]
    calls = await db.call_logs.find(
        {"user_id": user_id, "$or": call_or},
        {"transcript": 1, "call_sid": 1, "contact_id": 1},
    ).sort("timestamp", -1).limit(1000).to_list(1000)
    for c in calls:
        if c.get("call_sid") in handled_call_sids or not c.get("contact_id"):
            continue
        hit = await _apply(str(c["contact_id"]), c.get("transcript", "") or "", "call", c.get("call_sid") or str(c["_id"]), None)
        if hit:
            summary["calls_matched"] += 1
            await db.call_logs.update_one({"_id": c["_id"]}, {"$addToSet": {"auto_tags": tag}})

    summary["contacts_tagged"] = len(tagged_contacts)
    logger.info(f"[KeywordTag] Retro scan '{tag}' for {user_id}: {summary}")
    return summary
