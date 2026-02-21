"""
Role-Based Access Control (RBAC) Security Module
Provides dependencies and utilities for securing API endpoints based on user roles.

Roles hierarchy (highest to lowest):
1. super_admin - Platform owner, sees everything globally
2. org_admin - Organization admin, sees all stores/users within their org
3. store_manager - Store manager, sees users/data within their store(s)
4. user - Regular sales rep, sees only their own data
"""
from fastapi import HTTPException, Header
from functools import wraps
from typing import List, Optional
from bson import ObjectId
import logging

from routers.database import get_db, get_user_by_id

logger = logging.getLogger(__name__)


# Role hierarchy for permission checking
ROLE_HIERARCHY = {
    'super_admin': 4,
    'org_admin': 3,
    'store_manager': 2,
    'user': 1,
}


async def get_current_user(x_user_id: str = Header(None, alias="X-User-ID")) -> dict:
    """
    Extract and validate the current user from the request header.
    In production, this would validate a JWT token.
    For now, we use X-User-ID header.
    """
    if not x_user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    user = await get_user_by_id(x_user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    return user


def require_role(min_role: str):
    """
    Dependency factory that requires a minimum role level.
    Usage: @router.get("/endpoint", dependencies=[Depends(require_role("org_admin"))])
    """
    min_level = ROLE_HIERARCHY.get(min_role, 0)
    
    async def check_role(x_user_id: str = Header(None, alias="X-User-ID")):
        if not x_user_id:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        user = await get_user_by_id(x_user_id)
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        
        user_role = user.get('role', 'user')
        user_level = ROLE_HIERARCHY.get(user_role, 0)
        
        if user_level < min_level:
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient permissions. Required: {min_role}, Your role: {user_role}"
            )
        
        return user
    
    return check_role


async def get_scoped_organization_ids(user: dict) -> List[str]:
    """
    Get the list of organization IDs this user can access.
    - super_admin: all organizations
    - org_admin: only their organization
    - store_manager: only their organization (via their stores)
    - user: only their organization
    """
    db = get_db()
    role = user.get('role', 'user')
    
    if role == 'super_admin':
        # Super admin sees all
        orgs = await db.organizations.find({}, {"_id": 1}).to_list(1000)
        return [str(o["_id"]) for o in orgs]
    
    elif role == 'org_admin':
        # Org admin sees their org only
        org_id = user.get('organization_id')
        return [org_id] if org_id else []
    
    elif role == 'store_manager':
        # Store manager sees their org (determined by their stores)
        store_ids = user.get('store_ids', [])
        if user.get('store_id'):
            store_ids = list(set(store_ids + [user['store_id']]))
        
        if not store_ids:
            return []
        
        # Get org from first store
        store = await db.stores.find_one({"_id": ObjectId(store_ids[0])})
        if store and store.get('organization_id'):
            return [store['organization_id']]
        return []
    
    else:
        # Regular user can only see their own org
        org_id = user.get('organization_id')
        return [org_id] if org_id else []


async def get_scoped_store_ids(user: dict) -> List[str]:
    """
    Get the list of store IDs this user can access.
    - super_admin: all stores
    - org_admin: all stores in their organization
    - store_manager: only their assigned stores
    - user: only their assigned store
    """
    db = get_db()
    role = user.get('role', 'user')
    
    if role == 'super_admin':
        # Super admin sees all stores
        stores = await db.stores.find({}, {"_id": 1}).to_list(1000)
        return [str(s["_id"]) for s in stores]
    
    elif role == 'org_admin':
        # Org admin sees all stores in their org
        org_id = user.get('organization_id')
        if not org_id:
            return []
        stores = await db.stores.find({"organization_id": org_id}, {"_id": 1}).to_list(1000)
        return [str(s["_id"]) for s in stores]
    
    elif role == 'store_manager':
        # Store manager sees only their stores
        store_ids = list(set(user.get('store_ids', []) + ([user['store_id']] if user.get('store_id') else [])))
        return store_ids
    
    else:
        # Regular user sees only their store
        store_id = user.get('store_id')
        return [store_id] if store_id else []


async def get_scoped_user_ids(user: dict) -> List[str]:
    """
    Get the list of user IDs this user can access.
    - super_admin: all users
    - org_admin: all users in their organization
    - store_manager: all users in their stores
    - user: only themselves
    """
    db = get_db()
    role = user.get('role', 'user')
    user_id = str(user.get('_id'))
    
    if role == 'super_admin':
        # Super admin sees all users
        users = await db.users.find({}, {"_id": 1}).to_list(10000)
        return [str(u["_id"]) for u in users]
    
    elif role == 'org_admin':
        # Org admin sees all users in their org
        org_id = user.get('organization_id')
        if not org_id:
            return [user_id]
        users = await db.users.find({"organization_id": org_id}, {"_id": 1}).to_list(10000)
        return [str(u["_id"]) for u in users]
    
    elif role == 'store_manager':
        # Store manager sees users in their stores
        store_ids = await get_scoped_store_ids(user)
        if not store_ids:
            return [user_id]
        
        users = await db.users.find({
            "$or": [
                {"store_id": {"$in": store_ids}},
                {"store_ids": {"$elemMatch": {"$in": store_ids}}}
            ]
        }, {"_id": 1}).to_list(10000)
        
        # Always include self
        user_ids = [str(u["_id"]) for u in users]
        if user_id not in user_ids:
            user_ids.append(user_id)
        return user_ids
    
    else:
        # Regular user sees only themselves
        return [user_id]


async def verify_organization_access(user: dict, org_id: str) -> bool:
    """Check if user can access a specific organization."""
    allowed_orgs = await get_scoped_organization_ids(user)
    return org_id in allowed_orgs


async def verify_store_access(user: dict, store_id: str) -> bool:
    """Check if user can access a specific store."""
    allowed_stores = await get_scoped_store_ids(user)
    return store_id in allowed_stores


async def verify_user_access(user: dict, target_user_id: str) -> bool:
    """Check if user can access/manage another user."""
    allowed_users = await get_scoped_user_ids(user)
    return target_user_id in allowed_users


def enforce_org_scope(user: dict, org_id: Optional[str]) -> Optional[str]:
    """
    Enforce organization scope for queries.
    - super_admin can query any org or all orgs (None)
    - org_admin and below must query only their org
    
    Returns the org_id to use in queries.
    Raises HTTPException if access denied.
    """
    role = user.get('role', 'user')
    user_org = user.get('organization_id')
    
    if role == 'super_admin':
        # Super admin can access any org
        return org_id
    
    if role == 'org_admin':
        # Org admin must see only their org
        if org_id and org_id != user_org:
            raise HTTPException(
                status_code=403,
                detail="You can only access data within your organization"
            )
        return user_org
    
    # Store managers and users can only see their org
    if org_id and org_id != user_org:
        raise HTTPException(
            status_code=403,
            detail="You can only access data within your organization"
        )
    return user_org


async def enforce_store_scope(user: dict, store_id: Optional[str]) -> Optional[str]:
    """
    Enforce store scope for queries.
    Returns the store_id to use in queries.
    Raises HTTPException if access denied.
    """
    role = user.get('role', 'user')
    
    if role == 'super_admin':
        return store_id
    
    if role == 'org_admin':
        # Can access any store in their org
        if store_id:
            allowed = await verify_store_access(user, store_id)
            if not allowed:
                raise HTTPException(
                    status_code=403,
                    detail="You can only access stores within your organization"
                )
        return store_id
    
    if role == 'store_manager':
        # Can only access their stores
        allowed_stores = await get_scoped_store_ids(user)
        
        if store_id:
            if store_id not in allowed_stores:
                raise HTTPException(
                    status_code=403,
                    detail="You can only access your assigned stores"
                )
            return store_id
        
        # If no specific store requested, they can only see their stores
        # Return first store or None
        return allowed_stores[0] if allowed_stores else None
    
    # Regular users
    user_store = user.get('store_id')
    if store_id and store_id != user_store:
        raise HTTPException(
            status_code=403,
            detail="You can only access your own store"
        )
    return user_store


async def get_scoped_query_filter(user: dict, field_name: str = "user_id") -> dict:
    """
    Build a MongoDB query filter based on user's scope.
    This is the primary function for data access filtering.
    
    Args:
        user: The requesting user document
        field_name: The field to filter on (default: "user_id")
    
    Returns:
        MongoDB query filter dict
    """
    role = user.get('role', 'user')
    user_id = str(user.get('_id'))
    
    if role == 'super_admin':
        # Super admin sees everything
        return {}
    
    elif role == 'org_admin':
        # Org admin sees all users in their org
        user_ids = await get_scoped_user_ids(user)
        return {field_name: {"$in": user_ids}}
    
    elif role == 'store_manager':
        # Store manager sees users in their stores
        user_ids = await get_scoped_user_ids(user)
        return {field_name: {"$in": user_ids}}
    
    else:
        # Regular user sees only their own data
        return {field_name: user_id}


# Permission types for fine-grained access control
PERMISSIONS = {
    # Organization management
    'view_all_organizations': ['super_admin'],
    'manage_organizations': ['super_admin'],
    
    # Store management
    'view_all_stores': ['super_admin'],
    'view_org_stores': ['super_admin', 'org_admin'],
    'view_own_stores': ['super_admin', 'org_admin', 'store_manager'],
    'manage_stores': ['super_admin', 'org_admin'],
    
    # User management
    'view_all_users': ['super_admin'],
    'view_org_users': ['super_admin', 'org_admin'],
    'view_store_users': ['super_admin', 'org_admin', 'store_manager'],
    'manage_users': ['super_admin', 'org_admin'],
    'manage_store_users': ['super_admin', 'org_admin', 'store_manager'],
    
    # Data access
    'view_global_data': ['super_admin'],
    'view_org_data': ['super_admin', 'org_admin'],
    'view_store_data': ['super_admin', 'org_admin', 'store_manager'],
    
    # Admin features
    'view_billing': ['super_admin'],
    'view_revenue_forecast': ['super_admin'],
    'approve_users': ['super_admin', 'org_admin'],
    'impersonate_users': ['super_admin'],
    'manage_onboarding_settings': ['super_admin'],
    'view_individuals': ['super_admin'],
    
    # Internal features
    'view_internal_section': ['super_admin'],
    'manage_phone_assignments': ['super_admin'],
    'manage_partner_agreements': ['super_admin'],
    'manage_discount_codes': ['super_admin'],
}


def has_permission(user: dict, permission: str) -> bool:
    """Check if user has a specific permission."""
    role = user.get('role', 'user')
    allowed_roles = PERMISSIONS.get(permission, [])
    return role in allowed_roles


def require_permission(permission: str):
    """
    Dependency factory that requires a specific permission.
    Usage: @router.get("/endpoint", dependencies=[Depends(require_permission("view_billing"))])
    """
    async def check_permission(x_user_id: str = Header(None, alias="X-User-ID")):
        if not x_user_id:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        user = await get_user_by_id(x_user_id)
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        
        if not has_permission(user, permission):
            raise HTTPException(
                status_code=403,
                detail=f"Permission denied: {permission}"
            )
        
        return user
    
    return check_permission
