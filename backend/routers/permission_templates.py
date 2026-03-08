"""
Permission Templates Router
Pre-defined and custom permission sets that can be applied to users in one click.
Templates combine a role assignment + feature permissions.
"""
from fastapi import APIRouter, HTTPException, Header
from bson import ObjectId
from datetime import datetime, timezone
import logging

from routers.database import get_db, get_user_by_id
from permissions import DEFAULT_PERMISSIONS, merge_permissions

router = APIRouter(prefix="/permission-templates", tags=["Permission Templates"])
logger = logging.getLogger(__name__)


async def _log_audit(action: str, actor_id: str, actor_name: str, template_name: str, details: dict | None = None):
    """Write an entry to permission_audit_log."""
    db = get_db()
    entry = {
        "action": action,
        "actor_id": actor_id,
        "actor_name": actor_name,
        "template_name": template_name,
        "details": details or {},
        "timestamp": datetime.now(timezone.utc),
    }
    try:
        await db.permission_audit_log.insert_one(entry)
    except Exception as e:
        logger.warning(f"Failed to write audit log: {e}")

# Pre-built templates
PREBUILT_TEMPLATES = [
    {
        "id": "sales_rep",
        "name": "Sales Rep",
        "description": "Core tools for daily selling. Touchpoints, Jessi AI, templates, and training.",
        "role": "user",
        "icon": "person",
        "color": "#007AFF",
        "is_prebuilt": True,
        "permissions": {
            "my_tools": {"_enabled": True, "touchpoints": True, "ask_jessi": True, "training_hub": True, "team_chat": True},
            "campaigns": {"_enabled": True, "campaign_builder": True, "campaign_dashboard": True, "broadcast": False, "date_triggers": False},
            "content": {"_enabled": True, "sms_templates": True, "email_templates": True, "card_templates": False, "manage_showcase": False},
            "insights": {"_enabled": True, "my_performance": True, "activity_reports": False, "email_analytics": False, "leaderboard": False, "lead_attribution": False},
        },
    },
    {
        "id": "senior_rep",
        "name": "Senior Rep",
        "description": "Everything a Sales Rep gets plus campaigns, leaderboards, and performance insights.",
        "role": "user",
        "icon": "star",
        "color": "#C9A962",
        "is_prebuilt": True,
        "permissions": {
            "my_tools": {"_enabled": True, "touchpoints": True, "ask_jessi": True, "training_hub": True, "team_chat": True},
            "campaigns": {"_enabled": True, "campaign_builder": True, "campaign_dashboard": True, "broadcast": True, "date_triggers": True},
            "content": {"_enabled": True, "sms_templates": True, "email_templates": True, "card_templates": True, "manage_showcase": True},
            "insights": {"_enabled": True, "my_performance": True, "activity_reports": False, "email_analytics": False, "leaderboard": True, "lead_attribution": False},
        },
    },
    {
        "id": "sales_manager",
        "name": "Sales Manager",
        "description": "Full store access. Manage team, view all reports, run campaigns, and track performance.",
        "role": "store_manager",
        "icon": "shield-checkmark",
        "color": "#34C759",
        "is_prebuilt": True,
        "permissions": {
            "my_tools": {"_enabled": True, "touchpoints": True, "ask_jessi": True, "training_hub": True, "team_chat": True},
            "campaigns": {"_enabled": True, "campaign_builder": True, "campaign_dashboard": True, "broadcast": True, "date_triggers": True},
            "content": {"_enabled": True, "sms_templates": True, "email_templates": True, "card_templates": True, "manage_showcase": True},
            "insights": {"_enabled": True, "my_performance": True, "activity_reports": True, "email_analytics": True, "leaderboard": True, "lead_attribution": True},
        },
    },
    {
        "id": "org_admin",
        "name": "Organization Admin",
        "description": "Full org-wide access. Manage all stores, users, billing, and settings.",
        "role": "org_admin",
        "icon": "business",
        "color": "#AF52DE",
        "is_prebuilt": True,
        "permissions": {
            "my_tools": {"_enabled": True, "touchpoints": True, "ask_jessi": True, "training_hub": True, "team_chat": True},
            "campaigns": {"_enabled": True, "campaign_builder": True, "campaign_dashboard": True, "broadcast": True, "date_triggers": True},
            "content": {"_enabled": True, "sms_templates": True, "email_templates": True, "card_templates": True, "manage_showcase": True},
            "insights": {"_enabled": True, "my_performance": True, "activity_reports": True, "email_analytics": True, "leaderboard": True, "lead_attribution": True},
        },
    },
]


@router.get("/")
async def list_templates(store_id: str = None, org_id: str = None):
    """List all permission templates (prebuilt + custom for the store/org)."""
    db = get_db()
    templates = list(PREBUILT_TEMPLATES)

    # Fetch custom templates for this store/org
    query = {"is_prebuilt": {"$ne": True}}
    if store_id:
        query["$or"] = [{"store_id": store_id}, {"store_id": None}, {"store_id": {"$exists": False}}]
    if org_id:
        query["$or"] = [{"org_id": org_id}, {"org_id": None}, {"org_id": {"$exists": False}}]

    custom = await db.permission_templates.find(query).sort("name", 1).to_list(50)
    for t in custom:
        t["_id"] = str(t["_id"])
        t["id"] = t["_id"]
        t["is_prebuilt"] = False
        templates.append(t)

    return {"templates": templates}


@router.get("/audit-log")
async def get_audit_log(limit: int = 50):
    """Get recent permission template audit log entries."""
    db = get_db()
    entries = await db.permission_audit_log.find(
        {}, {"_id": 0}
    ).sort("timestamp", -1).limit(limit).to_list(limit)

    for e in entries:
        ts = e.get("timestamp")
        if ts and hasattr(ts, "isoformat"):
            e["timestamp"] = ts.isoformat() + "Z"

    return {"entries": entries}


@router.get("/{template_id}")
async def get_template(template_id: str):
    """Get a specific template by ID."""
    # Check prebuilt
    for t in PREBUILT_TEMPLATES:
        if t["id"] == template_id:
            return t

    # Check custom
    db = get_db()
    try:
        doc = await db.permission_templates.find_one({"_id": ObjectId(template_id)})
    except Exception:
        raise HTTPException(status_code=404, detail="Template not found")

    if not doc:
        raise HTTPException(status_code=404, detail="Template not found")

    doc["_id"] = str(doc["_id"])
    doc["id"] = doc["_id"]
    return doc


@router.post("/")
async def create_template(data: dict, x_user_id: str = Header(None, alias="X-User-ID")):
    """Create a custom permission template."""
    requesting = await get_user_by_id(x_user_id) if x_user_id else None
    if not requesting or requesting.get("role") not in ("super_admin", "org_admin", "store_manager"):
        raise HTTPException(status_code=403, detail="Only admins can create templates")

    name = data.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Template name is required")

    db = get_db()
    now = datetime.now(timezone.utc)

    template = {
        "name": name,
        "description": data.get("description", ""),
        "role": data.get("role", "user"),
        "icon": data.get("icon", "people"),
        "color": data.get("color", "#007AFF"),
        "permissions": data.get("permissions", DEFAULT_PERMISSIONS),
        "is_prebuilt": False,
        "store_id": data.get("store_id") or requesting.get("store_id"),
        "org_id": data.get("org_id") or requesting.get("organization_id"),
        "created_by": x_user_id,
        "created_at": now,
        "updated_at": now,
    }

    result = await db.permission_templates.insert_one(template)
    template["_id"] = str(result.inserted_id)
    template["id"] = template["_id"]
    del template["created_at"]
    del template["updated_at"]

    logger.info(f"Permission template created: {name} by {x_user_id}")
    await _log_audit("created", x_user_id, requesting.get("name", ""), name, {
        "template_id": template["id"], "role": template["role"],
    })
    return template


@router.put("/{template_id}")
async def update_template(template_id: str, data: dict, x_user_id: str = Header(None, alias="X-User-ID")):
    """Update a custom permission template. Cannot edit prebuilt templates."""
    for t in PREBUILT_TEMPLATES:
        if t["id"] == template_id:
            raise HTTPException(status_code=400, detail="Cannot edit prebuilt templates")

    requesting = await get_user_by_id(x_user_id) if x_user_id else None
    if not requesting or requesting.get("role") not in ("super_admin", "org_admin", "store_manager"):
        raise HTTPException(status_code=403, detail="Only admins can edit templates")

    db = get_db()
    update = {"updated_at": datetime.now(timezone.utc)}
    for field in ("name", "description", "role", "icon", "color", "permissions"):
        if field in data:
            update[field] = data[field]

    result = await db.permission_templates.update_one(
        {"_id": ObjectId(template_id)},
        {"$set": update}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Template not found")

    await _log_audit("edited", x_user_id, requesting.get("name", ""), data.get("name", template_id), {
        "template_id": template_id, "fields_changed": [f for f in ("name", "description", "role", "icon", "color", "permissions") if f in data],
    })
    return {"message": "Template updated"}


@router.delete("/{template_id}")
async def delete_template(template_id: str, x_user_id: str = Header(None, alias="X-User-ID")):
    """Delete a custom template."""
    for t in PREBUILT_TEMPLATES:
        if t["id"] == template_id:
            raise HTTPException(status_code=400, detail="Cannot delete prebuilt templates")

    requesting = await get_user_by_id(x_user_id) if x_user_id else None
    if not requesting or requesting.get("role") not in ("super_admin", "org_admin", "store_manager"):
        raise HTTPException(status_code=403, detail="Only admins can delete templates")

    db = get_db()
    # Fetch template name before deleting
    doc = await db.permission_templates.find_one({"_id": ObjectId(template_id)}, {"name": 1})
    tpl_name = doc.get("name", template_id) if doc else template_id

    result = await db.permission_templates.delete_one({"_id": ObjectId(template_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Template not found")

    await _log_audit("deleted", x_user_id, requesting.get("name", ""), tpl_name, {
        "template_id": template_id,
    })
    return {"message": "Template deleted"}


@router.post("/{template_id}/apply/{user_id}")
async def apply_template(template_id: str, user_id: str, x_user_id: str = Header(None, alias="X-User-ID")):
    """Apply a permission template to a user. Sets both role and feature permissions."""
    requesting = await get_user_by_id(x_user_id) if x_user_id else None
    if not requesting or requesting.get("role") not in ("super_admin", "org_admin", "store_manager"):
        raise HTTPException(status_code=403, detail="Only admins can apply templates")

    # Find the template
    template = None
    for t in PREBUILT_TEMPLATES:
        if t["id"] == template_id:
            template = t
            break

    if not template:
        db = get_db()
        try:
            doc = await db.permission_templates.find_one({"_id": ObjectId(template_id)})
            if doc:
                template = doc
        except Exception:
            pass

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    db = get_db()
    target = await db.users.find_one({"_id": ObjectId(user_id)}, {"_id": 1, "name": 1, "role": 1})
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    new_role = template.get("role", "user")
    new_permissions = template.get("permissions", DEFAULT_PERMISSIONS)

    await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {
            "role": new_role,
            "feature_permissions": new_permissions,
            "permission_template": template.get("name", ""),
            "permissions_updated_at": datetime.now(timezone.utc),
            "permissions_updated_by": x_user_id,
        }}
    )

    logger.info(f"Permission template '{template.get('name')}' applied to user {user_id} by {x_user_id}")
    await _log_audit("applied", x_user_id, requesting.get("name", ""), template.get("name", ""), {
        "template_id": template_id,
        "target_user_id": user_id,
        "target_user_name": target.get("name", ""),
        "previous_role": target.get("role", ""),
        "new_role": new_role,
    })
    return {
        "message": f"Template '{template.get('name')}' applied",
        "user_id": user_id,
        "new_role": new_role,
        "permissions": merge_permissions(new_permissions),
    }
