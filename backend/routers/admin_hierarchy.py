"""
admin_hierarchy.py — User hierarchy management: org/store assignment, role changes.
Extracted from admin.py for focused ownership of hierarchy logic.
All hierarchy bugs start here — single place to look and fix.
"""
from fastapi import APIRouter, HTTPException, Header
from bson import ObjectId
from datetime import datetime
from typing import Optional
import logging

from routers.database import get_db
from routers.admin_helpers import safe_objectid, get_requesting_user
from routers.rbac import (
    get_scoped_organization_ids,
    get_scoped_store_ids,
    get_scoped_user_ids,
)

router = APIRouter(prefix="/admin", tags=["Admin - Hierarchy"])
logger = logging.getLogger(__name__)

@router.get("/hierarchy/overview")
async def get_hierarchy_overview(x_user_id: str = Header(None, alias="X-User-ID")):
    """Get complete hierarchy overview with counts - scoped by user role"""
    user = await get_requesting_user(x_user_id)
    role = user.get('role', 'user') if user else None

    if user and role != 'super_admin':
        from routers.rbac import get_scoped_organization_ids
        allowed_org_ids = await get_scoped_organization_ids(user)
        org_filter = {"_id": {"$in": [oid for oid in (safe_objectid(x) for x in allowed_org_ids) if oid is not None]}}
    else:
        org_filter = {}

    orgs = await get_db().organizations.find(org_filter).limit(500).to_list(500)
    
    result = []
    for org in orgs:
        org_id = str(org["_id"])
        
        # Count stores for this org
        store_count = await get_db().stores.count_documents({"organization_id": org_id})
        
        # Count users for this org (including org admins)
        user_count = await get_db().users.count_documents({"organization_id": org_id})
        
        # Count org admins
        admin_count = await get_db().users.count_documents({
            "organization_id": org_id,
            "role": {"$in": ["org_admin", "super_admin"]}
        })
        
        result.append({
            "_id": org_id,
            "name": org.get("name"),
            "account_type": org.get("account_type", "organization"),
            "active": org.get("active", True),
            "store_count": store_count,
            "user_count": user_count,
            "admin_count": admin_count,
            "city": org.get("city"),
            "state": org.get("state")
        })
    
    # Count unassigned users
    unassigned_count = await get_db().users.count_documents({
        "$or": [
            {"organization_id": None},
            {"organization_id": ""},
            {"organization_id": {"$exists": False}}
        ]
    })
    
    return {
        "organizations": result,
        "unassigned_users": unassigned_count,
        "total_organizations": len(result),
        "total_stores": await get_db().stores.count_documents({}),
        "total_users": await get_db().users.count_documents({})
    }


@router.get("/hierarchy/organization/{org_id}")
async def get_organization_hierarchy(org_id: str):
    """Get full hierarchy for a specific organization"""
    org = await get_db().organizations.find_one({"_id": ObjectId(org_id)})
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    # Get all stores for this org
    stores = await get_db().stores.find({"organization_id": org_id}, {"logo_url": 0, "email_brand_kit.logo_url": 0, "cover_image_url": 0}).to_list(100)
    
    # Get all users for this org
    users = await get_db().users.find(
        {"organization_id": org_id},
        {"password": 0}
    ).limit(500).to_list(500)
    
    # Build store data with user assignments
    store_data = []
    for store in stores:
        store_id = str(store["_id"])
        
        # Find users assigned to this store (check both store_id and store_ids)
        store_users = [u for u in users if 
            u.get("store_id") == store_id or 
            store_id in u.get("store_ids", [])]
        
        store_data.append({
            "_id": store_id,
            "name": store.get("name"),
            "phone": store.get("phone"),
            "city": store.get("city"),
            "state": store.get("state"),
            "active": store.get("active", True),
            "user_count": len(store_users),
            "users": [{
                "_id": str(u["_id"]),
                "name": u.get("name"),
                "email": u.get("email"),
                "role": u.get("role", "user"),
                "is_active": u.get("is_active", True)
            } for u in store_users]
        })
    
    # Find org admins (users with org_admin role for this org)
    org_admins = [u for u in users if u.get("role") in ["org_admin", "super_admin"]]
    
    # Find unassigned users (in org but not assigned to any store)
    all_store_ids = [str(s["_id"]) for s in stores]
    unassigned = [u for u in users if 
        u.get("store_id") not in all_store_ids and
        not any(sid in all_store_ids for sid in u.get("store_ids", []))]
    
    return {
        "organization": {
            "_id": str(org["_id"]),
            "name": org.get("name"),
            "account_type": org.get("account_type"),
            "admin_email": org.get("admin_email"),
            "admin_phone": org.get("admin_phone"),
            "city": org.get("city"),
            "state": org.get("state"),
            "active": org.get("active", True)
        },
        "admins": [{
            "_id": str(u["_id"]),
            "name": u.get("name"),
            "email": u.get("email"),
            "role": u.get("role"),
            "is_active": u.get("is_active", True)
        } for u in org_admins],
        "stores": store_data,
        "unassigned_users": [{
            "_id": str(u["_id"]),
            "name": u.get("name"),
            "email": u.get("email"),
            "role": u.get("role", "user"),
            "is_active": u.get("is_active", True)
        } for u in unassigned],
        "stats": {
            "total_stores": len(stores),
            "total_users": len(users),
            "total_admins": len(org_admins),
            "unassigned_count": len(unassigned)
        }
    }


@router.get("/hierarchy/store/{store_id}")
async def get_store_hierarchy(store_id: str):
    """Get all users for a specific store"""
    store = await get_db().stores.find_one({"_id": ObjectId(store_id)})
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    
    # Get organization info
    org = None
    if store.get("organization_id"):
        org = await get_db().organizations.find_one({"_id": ObjectId(store["organization_id"])})
    
    # Get users assigned to this store (check both store_id and store_ids)
    users = await get_db().users.find({
        "$or": [
            {"store_id": store_id},
            {"store_ids": store_id}
        ]
    }, {"password": 0}).limit(500).to_list(500)
    
    # Get users in the org who are NOT assigned to this store (for adding)
    org_users_not_in_store = []
    if store.get("organization_id"):
        org_users_not_in_store = await get_db().users.find({
            "organization_id": store["organization_id"],
            "store_id": {"$ne": store_id},
            "store_ids": {"$nin": [store_id]}
        }, {"password": 0}).limit(500).to_list(500)
    
    return {
        "store": {
            "_id": str(store["_id"]),
            "name": store.get("name"),
            "organization_id": store.get("organization_id"),
            "phone": store.get("phone"),
            "address": store.get("address"),
            "city": store.get("city"),
            "state": store.get("state"),
            "active": store.get("active", True)
        },
        "organization": {
            "_id": str(org["_id"]) if org else None,
            "name": org.get("name") if org else None
        } if org else None,
        "users": [{
            "_id": str(u["_id"]),
            "name": u.get("name"),
            "email": u.get("email"),
            "phone": u.get("phone"),
            "role": u.get("role", "user"),
            "is_active": u.get("is_active", True),
            "store_ids": u.get("store_ids", [])
        } for u in users],
        "available_users": [{
            "_id": str(u["_id"]),
            "name": u.get("name"),
            "email": u.get("email"),
            "role": u.get("role", "user")
        } for u in org_users_not_in_store],
        "user_count": len(users)
    }


@router.get("/hierarchy/users")
async def get_all_users_hierarchy(
    filter: Optional[str] = None,  # unassigned, org_admins, store_managers
    organization_id: Optional[str] = None,
    store_id: Optional[str] = None,
    x_user_id: str = Header(None, alias="X-User-ID")
):
    """Get all users with their org/store assignments - scoped by user role"""
    user = await get_requesting_user(x_user_id)
    role = user.get('role', 'user') if user else None

    query = {}

    # Apply RBAC scoping for non-super-admins
    if user and role != 'super_admin':
        from routers.rbac import get_scoped_organization_ids
        allowed_org_ids = await get_scoped_organization_ids(user)
        if allowed_org_ids:
            query["organization_id"] = {"$in": allowed_org_ids}
        else:
            return {"users": [], "total": 0}

    if filter == "unassigned":
        query["$or"] = [
            {"organization_id": None},
            {"organization_id": ""},
            {"organization_id": {"$exists": False}}
        ]
    elif filter == "org_admins":
        query["role"] = "org_admin"
    elif filter == "store_managers":
        query["role"] = "store_manager"
    
    if organization_id:
        query["organization_id"] = organization_id
    
    if store_id:
        query["$or"] = [
            {"store_id": store_id},
            {"store_ids": store_id}
        ]
    
    users = await get_db().users.find(query, {"password": 0}).limit(500).to_list(500)
    
    # Get org and store names for display
    org_ids = list(set([u.get("organization_id") for u in users if u.get("organization_id")]))
    store_ids = []
    for u in users:
        if u.get("store_id"):
            store_ids.append(u["store_id"])
        store_ids.extend(u.get("store_ids", []))
    store_ids = list(set(store_ids))
    
    orgs = {}
    if org_ids:
        valid_org_oids = [oid for oid in (safe_objectid(x) for x in org_ids) if oid is not None]
        if valid_org_oids:
            org_docs = await get_db().organizations.find(
                {"_id": {"$in": valid_org_oids}}
            ).to_list(100)
            orgs = {str(o["_id"]): o.get("name") for o in org_docs}
    
    stores = {}
    if store_ids:
        valid_store_oids = [oid for oid in (safe_objectid(x) for x in store_ids) if oid is not None]
        if valid_store_oids:
            store_docs = await get_db().stores.find(
                {"_id": {"$in": valid_store_oids}}
            ).to_list(100)
            stores = {str(s["_id"]): s.get("name") for s in store_docs}
    
    result = []
    for u in users:
        user_stores = []
        if u.get("store_id"):
            user_stores.append({
                "id": u["store_id"],
                "name": stores.get(u["store_id"], "Unknown")
            })
        for sid in u.get("store_ids", []):
            if sid != u.get("store_id"):
                user_stores.append({
                    "id": sid,
                    "name": stores.get(sid, "Unknown")
                })
        
        result.append({
            "_id": str(u["_id"]),
            "name": u.get("name"),
            "email": u.get("email"),
            "phone": u.get("phone"),
            "role": u.get("role", "user"),
            "is_active": u.get("is_active", True),
            "organization_id": u.get("organization_id"),
            "organization_name": orgs.get(u.get("organization_id")),
            "stores": user_stores
        })
    
    return {
        "users": result,
        "total": len(result)
    }


@router.put("/hierarchy/users/{user_id}/assign-org")
async def assign_user_to_org(user_id: str, data: dict):
    """Assign or change a user's organization"""
    org_id = data.get("organization_id")
    role = data.get("role", "user")
    
    # Validate org exists if assigning
    if org_id:
        org = await get_db().organizations.find_one({"_id": ObjectId(org_id)})
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found")
    
    update_data = {
        "organization_id": org_id,
        "role": role,
        "updated_at": datetime.utcnow()
    }
    
    # If removing from org, also remove store assignments
    if not org_id:
        update_data["store_id"] = None
        update_data["store_ids"] = []
    
    result = await get_db().users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": update_data}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {"message": "User organization updated", "organization_id": org_id, "role": role}


@router.put("/hierarchy/users/{user_id}/assign-store")
async def assign_user_to_store(user_id: str, data: dict):
    """Add a user to a store (supports multi-store assignment)"""
    store_id = data.get("store_id")
    
    if not store_id:
        raise HTTPException(status_code=400, detail="store_id is required")
    
    # Validate store exists
    store = await get_db().stores.find_one({"_id": ObjectId(store_id)})
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    
    # Get user
    user = await get_db().users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Auto-assign to org if not already assigned
    org_update = {}
    if not user.get("organization_id") and store.get("organization_id"):
        org_update["organization_id"] = store["organization_id"]
    
    # Add to store_ids array (and set store_id for backward compatibility)
    current_stores = user.get("store_ids", [])
    if store_id not in current_stores:
        current_stores.append(store_id)
    
    result = await get_db().users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {
            "store_id": current_stores[0] if current_stores else None,  # Primary store
            "store_ids": current_stores,
            "updated_at": datetime.utcnow(),
            **org_update
        }}
    )
    
    return {"message": "User added to store", "store_ids": current_stores}


@router.put("/hierarchy/users/{user_id}/remove-store")
async def remove_user_from_store(user_id: str, data: dict):
    """Remove a user from a store"""
    store_id = data.get("store_id")
    
    if not store_id:
        raise HTTPException(status_code=400, detail="store_id is required")
    
    user = await get_db().users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    current_stores = user.get("store_ids", [])
    if store_id in current_stores:
        current_stores.remove(store_id)
    
    # Update store_id (primary) if it was removed
    new_primary = current_stores[0] if current_stores else None
    if user.get("store_id") == store_id:
        new_primary = current_stores[0] if current_stores else None
    
    result = await get_db().users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {
            "store_id": new_primary,
            "store_ids": current_stores,
            "updated_at": datetime.utcnow()
        }}
    )
    
    return {"message": "User removed from store", "store_ids": current_stores}


@router.put("/hierarchy/users/{user_id}/role")
async def update_user_role(user_id: str, data: dict, x_user_id: str = Header(None, alias="X-User-ID")):
    """Update a user's role"""
    requesting = await get_requesting_user(x_user_id)
    if not requesting:
        raise HTTPException(status_code=401, detail="Authentication required")
    req_role = requesting.get("role", "user")
    if req_role not in ("super_admin", "org_admin", "store_manager"):
        raise HTTPException(status_code=403, detail="Only admins can change user roles")

    role = data.get("role")
    valid_roles = ["user", "account_manager", "store_manager", "org_admin", "super_admin"]
    if not role or role not in valid_roles:
        raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of: {', '.join(valid_roles)}")

    db = get_db()
    target = await db.users.find_one({"_id": ObjectId(user_id)}, {"_id": 1})
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"role": role, "role_updated_at": datetime.utcnow()}}
    )
    return {"status": "ok", "role": role}


# ============= DATA ENDPOINTS =============


@router.put("/hierarchy/users/{user_id}/change-organization")
async def change_user_organization(user_id: str, data: dict):
    """Move a user to a different organization"""
    db = get_db()
    new_org_id = data.get("organization_id")
    
    if not new_org_id:
        raise HTTPException(status_code=400, detail="organization_id is required")
    
    # Verify the organization exists
    org = await db.organizations.find_one({"_id": ObjectId(new_org_id)})
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    # Get the user
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Update the user - clear store assignments since they're moving to a new org
    result = await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {
            "organization_id": new_org_id,
            "store_id": None,
            "store_ids": [],
            "updated_at": datetime.utcnow()
        }}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "message": f"User moved to {org.get('name', 'new organization')}",
        "organization_id": new_org_id,
        "organization_name": org.get('name')
    }


@router.get("/roles")
async def get_available_roles():
    """Get list of available roles with descriptions"""
    return {
        "roles": [
            {
                "id": "super_admin",
                "label": "Super Admin",
                "description": "Platform-wide access to all organizations and settings",
                "color": "#FF3B30"
            },
            {
                "id": "org_admin",
                "label": "Org Admin",
                "description": "Full access to one organization and all its stores",
                "color": "#FF9500"
            },
            {
                "id": "store_manager",
                "label": "Store Manager",
                "description": "Full access to manage one or more stores",
                "color": "#34C759"
            },
            {
                "id": "user",
                "label": "Sales Rep",
                "description": "Basic access to their assigned store(s)",
                "color": "#007AFF"
            }
        ]
    }

