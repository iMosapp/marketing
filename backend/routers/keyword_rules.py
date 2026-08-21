"""Keyword Rules router — manage keyword→tag rules and view auto-tag activity."""
from fastapi import APIRouter, HTTPException, Query
from bson import ObjectId
from datetime import datetime, timezone
import logging

from routers.database import get_db
from services.keyword_tagging import ensure_starter_rules

router = APIRouter(prefix="/keyword-rules", tags=["Keyword Rules"])
logger = logging.getLogger(__name__)

RULE_COLORS = ["#007AFF", "#FF9500", "#34C759", "#AF52DE", "#FF2D55", "#5856D6", "#00C7BE", "#FFD60A"]

ADMIN_ROLES = ("super_admin", "org_admin", "store_manager", "admin")


async def _user_ctx(user_id: str):
    """Returns (store_id, org_id, role, is_admin) for team-rule scoping."""
    db = get_db()
    try:
        u = await db.users.find_one({"_id": ObjectId(user_id)}, {"store_id": 1, "organization_id": 1, "org_id": 1, "role": 1})
    except Exception:
        u = None
    u = u or {}
    role = u.get("role", "user")
    return u.get("store_id"), (u.get("organization_id") or u.get("org_id")), role, role in ADMIN_ROLES


def _can_manage(rule: dict, user_id: str, store_id, org_id, is_admin: bool) -> bool:
    if rule.get("user_id"):
        return rule["user_id"] == user_id
    if rule.get("store_id"):
        return is_admin and rule["store_id"] == store_id
    if rule.get("org_id"):
        return is_admin and rule["org_id"] == org_id
    return False


def _clean_keywords(raw) -> list:
    if not isinstance(raw, list):
        return []
    seen = set()
    out = []
    for k in raw:
        kw = str(k).strip().lower()
        if kw and kw not in seen:
            seen.add(kw)
            out.append(kw)
    return out


@router.get("/{user_id}")
async def list_rules(user_id: str):
    db = get_db()
    await ensure_starter_rules(user_id)
    store_id, org_id, role, is_admin = await _user_ctx(user_id)
    scope = [{"user_id": user_id}]
    if store_id:
        scope.append({"store_id": store_id})
    if org_id:
        scope.append({"org_id": org_id})
    rules = await db.keyword_rules.find({"$or": scope}).sort("created_at", 1).to_list(200)

    # Hit counts per rule
    rule_ids = [str(r["_id"]) for r in rules]
    counts = {}
    if rule_ids:
        pipeline = [
            {"$match": {"rule_id": {"$in": rule_ids}}},
            {"$group": {"_id": "$rule_id", "count": {"$sum": 1}}},
        ]
        counts = {r["_id"]: r["count"] async for r in db.keyword_tag_events.aggregate(pipeline)}

    for r in rules:
        r["scope"] = "personal" if r.get("user_id") else "team"
        r["editable"] = _can_manage(r, user_id, store_id, org_id, is_admin)
        r["_id"] = str(r["_id"])
        r["hit_count"] = counts.get(r["_id"], 0)
        r["created_at"] = r["created_at"].isoformat() if hasattr(r.get("created_at"), "isoformat") else str(r.get("created_at", ""))
    return rules


@router.post("/{user_id}")
async def create_rule(user_id: str, data: dict):
    db = get_db()
    tag = (data.get("tag") or "").strip()
    keywords = _clean_keywords(data.get("keywords", []))
    if not tag:
        raise HTTPException(status_code=400, detail="Tag name is required")
    if not keywords:
        raise HTTPException(status_code=400, detail="At least one keyword is required")

    requested_scope = data.get("scope", "personal")
    store_id, org_id, role, is_admin = await _user_ctx(user_id)

    rule = {
        "tag": tag,
        "keywords": keywords,
        "color": data.get("color") or RULE_COLORS[0],
        "enabled": data.get("enabled", True),
        "alert_enabled": bool(data.get("alert_enabled", False)),
        "created_by": user_id,
        "created_at": datetime.now(timezone.utc),
    }

    if requested_scope == "team":
        if not is_admin:
            raise HTTPException(status_code=403, detail="Only managers can create team rules")
        if not store_id and not org_id:
            raise HTTPException(status_code=400, detail="No store or organization on your account for team rules")
        dup_scope = {"store_id": store_id} if store_id else {"org_id": org_id}
        existing = await db.keyword_rules.find_one({**dup_scope, "tag": {"$regex": f"^{tag}$", "$options": "i"}})
        if existing:
            raise HTTPException(status_code=400, detail=f"A team rule for tag '{tag}' already exists")
        rule.update(dup_scope)
    else:
        existing = await db.keyword_rules.find_one({"user_id": user_id, "tag": {"$regex": f"^{tag}$", "$options": "i"}})
        if existing:
            raise HTTPException(status_code=400, detail=f"A rule for tag '{tag}' already exists")
        rule["user_id"] = user_id

    result = await db.keyword_rules.insert_one(rule)
    rule["_id"] = str(result.inserted_id)
    rule["scope"] = "personal" if rule.get("user_id") else "team"
    rule["editable"] = True
    rule["hit_count"] = 0
    rule["created_at"] = rule["created_at"].isoformat()
    return rule


@router.put("/{user_id}/{rule_id}")
async def update_rule(user_id: str, rule_id: str, data: dict):
    db = get_db()
    try:
        rule = await db.keyword_rules.find_one({"_id": ObjectId(rule_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid rule ID")
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    store_id, org_id, role, is_admin = await _user_ctx(user_id)
    if not _can_manage(rule, user_id, store_id, org_id, is_admin):
        raise HTTPException(status_code=403, detail="You don't have permission to edit this rule")

    update = {"updated_at": datetime.now(timezone.utc)}
    if "tag" in data and str(data["tag"]).strip():
        update["tag"] = str(data["tag"]).strip()
    if "keywords" in data:
        keywords = _clean_keywords(data["keywords"])
        if not keywords:
            raise HTTPException(status_code=400, detail="At least one keyword is required")
        update["keywords"] = keywords
    if "color" in data and data["color"]:
        update["color"] = data["color"]
    if "enabled" in data:
        update["enabled"] = bool(data["enabled"])
    if "alert_enabled" in data:
        update["alert_enabled"] = bool(data["alert_enabled"])

    await db.keyword_rules.update_one({"_id": ObjectId(rule_id)}, {"$set": update})
    updated = await db.keyword_rules.find_one({"_id": ObjectId(rule_id)})
    updated["_id"] = str(updated["_id"])
    updated["created_at"] = updated["created_at"].isoformat() if hasattr(updated.get("created_at"), "isoformat") else str(updated.get("created_at", ""))
    if "updated_at" in updated and hasattr(updated["updated_at"], "isoformat"):
        updated["updated_at"] = updated["updated_at"].isoformat()
    return updated


@router.delete("/{user_id}/{rule_id}")
async def delete_rule(user_id: str, rule_id: str):
    db = get_db()
    try:
        rule = await db.keyword_rules.find_one({"_id": ObjectId(rule_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid rule ID")
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    store_id, org_id, role, is_admin = await _user_ctx(user_id)
    if not _can_manage(rule, user_id, store_id, org_id, is_admin):
        raise HTTPException(status_code=403, detail="You don't have permission to delete this rule")
    await db.keyword_rules.delete_one({"_id": ObjectId(rule_id)})
    return {"message": "Rule deleted"}


@router.post("/{user_id}/{rule_id}/scan")
async def scan_rule_history(user_id: str, rule_id: str):
    """One-tap retro scan: apply this rule to all past messages + call transcripts."""
    from services.keyword_tagging import scan_history_for_rule
    db = get_db()
    try:
        rule = await db.keyword_rules.find_one({"_id": ObjectId(rule_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid rule ID")
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return await scan_history_for_rule(user_id, rule)


@router.get("/{user_id}/events")
async def list_events(user_id: str, limit: int = Query(30, ge=1, le=100), contact_id: str = Query(None)):
    """Recent auto-tag trigger events — shows which call/message applied each tag."""
    db = get_db()
    query = {"user_id": user_id}
    if contact_id:
        query["contact_id"] = contact_id
    events = await db.keyword_tag_events.find(query).sort("created_at", -1).limit(limit).to_list(limit)
    for e in events:
        e["_id"] = str(e["_id"])
        e["created_at"] = e["created_at"].isoformat() if hasattr(e.get("created_at"), "isoformat") else str(e.get("created_at", ""))
        # Resolve the message_id for jump-to navigation when source is a call
        if e.get("source_type") == "call" and e.get("source_id"):
            msg = await db.messages.find_one({"call_sid": e["source_id"], "type": "call_log"}, {"_id": 1, "conversation_id": 1})
            if msg:
                e["message_id"] = str(msg["_id"])
                e["conversation_id"] = e.get("conversation_id") or msg.get("conversation_id")
        elif e.get("source_type") == "sms":
            e["message_id"] = e.get("source_id")
    return events
