"""
admin_users.py — User management: CRUD, pending users, impersonation, permissions.
Extracted from admin.py for focused ownership of user logic.
The single source of truth for how users are created, modified, and managed.
"""
from fastapi import APIRouter, HTTPException, Header, Body, UploadFile, File
from bson import ObjectId
from datetime import datetime, timezone
from typing import Optional
import logging
import secrets
import os
import base64
import asyncio
from pydantic import BaseModel

from routers.database import get_db, get_user_by_id
from routers.admin_helpers import (
    safe_objectid, get_requesting_user,
    send_invite_email, APP_URL, SENDER_EMAIL
)
from routers.rbac import (
    get_scoped_organization_ids,
    get_scoped_store_ids,
    get_scoped_user_ids,
    verify_user_access,
    has_permission,
    ROLE_HIERARCHY,
)
from routers.auth import hash_password

router = APIRouter(prefix="/admin", tags=["Admin - Users"])
logger = logging.getLogger(__name__)


class AddTeamMemberRequest(BaseModel):
    name: str
    email: str
    phone: str
    role: str = "user"
    store_id: str
    added_by: str

# ============= USER MANAGEMENT ENDPOINTS =============
@router.post("/users")
async def create_admin_user(user_data: dict, x_user_id: str = Header(None, alias="X-User-ID")):
    """Create a user with specific role - admins only"""
    requesting_user = await get_requesting_user(x_user_id)
    
    if requesting_user:
        role = requesting_user.get('role', 'user')
        if role not in ['super_admin', 'org_admin', 'store_manager']:
            raise HTTPException(status_code=403, detail="Only admins can create users")
        
        # Org admins can only create users in their orgs (partner-scoped)
        if role == 'org_admin':
            from routers.rbac import get_scoped_organization_ids
            allowed_orgs = await get_scoped_organization_ids(requesting_user)
            if user_data.get('organization_id') and user_data.get('organization_id') not in allowed_orgs:
                raise HTTPException(status_code=403, detail="You can only create users in your organizations")
        
        # Store managers can only create users in their stores
        if role == 'store_manager':
            allowed_stores = await get_scoped_store_ids(requesting_user)
            if user_data.get('store_id') not in allowed_stores:
                raise HTTPException(status_code=403, detail="You can only create users in your assigned stores")
            # Copy org from manager
            user_data['organization_id'] = requesting_user.get('organization_id')
    
    # Check if email exists
    existing = await get_db().users.find_one({"email": user_data.get('email')})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    user_dict = {
        "email": user_data.get('email'),
        "password": hash_password(user_data.get('password', '')),
        "name": user_data.get('name'),
        "phone": user_data.get('phone', ''),
        "role": user_data.get('role', 'user'),
        "organization_id": user_data.get('organization_id'),
        "store_id": user_data.get('store_id'),
        "state": user_data.get('state', ''),
        "created_at": datetime.utcnow(),
        "onboarding_complete": user_data.get('onboarding_complete', True),
        "needs_password_change": user_data.get('needs_password_change', False),
        "stats": {
            'contacts_added': 0,
            'messages_sent': 0,
            'calls_made': 0,
            'deals_closed': 0
        },
        "settings": {
            'leaderboard_visible': False,
            'compare_scope': 'state'
        }
    }
    
    # Auto-inherit partner_id from the organization
    org_id = user_data.get('organization_id')
    if org_id:
        try:
            org = await get_db().organizations.find_one(
                {"_id": ObjectId(org_id)}, {"partner_id": 1}
            )
            if org and org.get('partner_id'):
                user_dict['partner_id'] = org['partner_id']
        except Exception as e:
            logger.error(f"Failed to inherit partner_id: {e}")
    
    result = await get_db().users.insert_one(user_dict)
    user_dict['_id'] = str(result.inserted_id)
    
    # Seed all default templates, campaigns, and triggers
    try:
        from services.seed_defaults import seed_user_defaults
        await seed_user_defaults(str(result.inserted_id))
    except Exception as e:
        logger.error(f"Failed to seed defaults for admin user: {e}")
    
    del user_dict['password']
    
    return user_dict


@router.post("/users/create")
async def create_user_with_invite(data: dict, x_user_id: str = Header(None, alias="X-User-ID")):
    """Create a user and optionally send invite email/SMS - admins only"""
    import secrets
    import string
    
    requesting_user = await get_requesting_user(x_user_id)
    
    if requesting_user:
        role = requesting_user.get('role', 'user')
        if role not in ['super_admin', 'org_admin', 'store_manager']:
            raise HTTPException(status_code=403, detail="Only admins can create users")
    
    first_name = data.get('first_name', '').strip()
    last_name = data.get('last_name', '').strip()
    name = data.get('name', '').strip() or f"{first_name} {last_name}".strip()
    email = data.get('email', '').strip().lower()
    phone = data.get('phone', '').strip()
    user_role = data.get('role', 'user')
    send_invite = data.get('send_invite', True)
    send_sms = data.get('send_sms', False)
    
    # Optional enrichment fields
    title = data.get('title', '').strip()
    company = data.get('company', '').strip()
    website = data.get('website', '').strip()
    social_links = {}
    for key in ['instagram', 'facebook', 'linkedin', 'twitter', 'tiktok', 'youtube']:
        val = data.get(f'social_{key}', '').strip()
        if val:
            social_links[key] = val
    
    # Get org and store from request, or fall back to requesting user's
    organization_id = data.get('organization_id')
    store_id = data.get('store_id')
    
    # Non-super admins can only create users in their own org (partner-scoped)
    if requesting_user and requesting_user.get('role') != 'super_admin':
        from routers.rbac import get_scoped_organization_ids
        allowed_orgs = await get_scoped_organization_ids(requesting_user)
        if organization_id and organization_id not in allowed_orgs:
            raise HTTPException(status_code=403, detail="You can only create users in your organizations")
        if not organization_id:
            organization_id = requesting_user.get('organization_id')
    
    if not first_name:
        raise HTTPException(status_code=400, detail="First name is required")
    if not last_name:
        raise HTTPException(status_code=400, detail="Last name is required")
    if not email or '@' not in email:
        raise HTTPException(status_code=400, detail="Valid email is required")
    if not phone:
        raise HTTPException(status_code=400, detail="Phone number is required")
    
    # Check if email exists
    existing = await get_db().users.find_one({"email": email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Generate temporary password
    temp_password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))
    
    user_dict = {
        "email": email,
        "password": hash_password(temp_password),
        "name": name,
        "first_name": first_name,
        "last_name": last_name,
        "phone": phone,
        "role": user_role,
        "organization_id": organization_id,
        "store_id": store_id,
        "store_ids": [store_id] if store_id else [],
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "onboarding_complete": False,
        "status": "active",
        "is_active": True,
        "needs_password_change": True,
        "stats": {
            'contacts_added': 0,
            'messages_sent': 0,
            'calls_made': 0,
            'deals_closed': 0
        },
        "settings": {
            'leaderboard_visible': True,
            'compare_scope': 'state'
        }
    }
    
    # Add enrichment fields if provided
    if title:
        user_dict["title"] = title
    if company:
        user_dict["company"] = company
    if website:
        user_dict["website"] = website
    if social_links:
        user_dict["social_links"] = social_links
    
    # Auto-inherit partner_id from the organization
    if organization_id:
        try:
            org = await get_db().organizations.find_one(
                {"_id": ObjectId(organization_id)}, {"partner_id": 1}
            )
            if org and org.get('partner_id'):
                user_dict['partner_id'] = org['partner_id']
                logger.info(f"Auto-inherited partner_id {org['partner_id']} for user in org {organization_id}")
        except Exception as e:
            logger.error(f"Failed to inherit partner_id from org {organization_id}: {e}")
    
    result = await get_db().users.insert_one(user_dict)
    user_id = str(result.inserted_id)
    
    # Seed all default templates, campaigns, and triggers
    try:
        from services.seed_defaults import seed_user_defaults
        await seed_user_defaults(user_id)
    except Exception as e:
        logger.error(f"Failed to seed defaults for new user {user_id}: {e}")
    
    # Send invite email if requested
    invite_sent = False
    if send_invite and email:
        # Get inviter name for email
        inviter_name = None
        if x_user_id:
            inviter = await get_db().users.find_one({"_id": ObjectId(x_user_id)})
            if inviter:
                inviter_name = inviter.get('name')
        
        invite_sent = await send_invite_email(
            email=email,
            name=name,
            temp_password=temp_password,
            role=user_role,
            inviter_name=inviter_name
        )
        if invite_sent:
            logger.info(f"Invite email sent to {email}")
        else:
            logger.warning(f"Failed to send invite email to {email}")
    
    # Send SMS if requested
    sms_sent = False
    if send_sms and phone:
        try:
            sms_body = (
                f"Welcome to i'M On Social, {first_name}! "
                f"Your login: {email}\n"
                f"Temp password: {temp_password}\n\n"
                f"Download the app:\n"
                f"Apple: https://apps.apple.com/app/im-on-social/id6743597907\n"
                f"Android: https://play.google.com/store/apps/details?id=com.imonsocial.app\n\n"
                f"Or log in at: https://app.imonsocial.com"
            )
            from services.twilio_service import send_sms as send_sms_func
            await send_sms_func(phone, sms_body)
            sms_sent = True
            logger.info(f"Invite SMS sent to {phone}")
        except Exception as e:
            logger.warning(f"Failed to send invite SMS to {phone}: {e}")
    
    # Link source contact to the new user (tag + store info)
    source_contact_id = data.get('source_contact_id')
    if source_contact_id:
        try:
            # Build update: tags + linked user/store info
            role_tag = f"imos_{user_role}"
            contact_update: dict = {
                "linked_user_id": user_id,
                "linked_role": user_role,
                "updated_at": datetime.utcnow(),
            }
            if store_id:
                store_doc = await get_db().stores.find_one({"_id": ObjectId(store_id)}, {"name": 1})
                if store_doc:
                    contact_update["linked_store_id"] = store_id
                    contact_update["linked_store_name"] = store_doc.get("name", "")
            if organization_id:
                org_doc = await get_db().organizations.find_one({"_id": ObjectId(organization_id)}, {"name": 1})
                if org_doc:
                    contact_update["linked_org_name"] = org_doc.get("name", "")
            await get_db().contacts.update_one(
                {"_id": ObjectId(source_contact_id)},
                {
                    "$set": contact_update,
                    "$addToSet": {"tags": {"$each": ["imos_user", role_tag]}},
                }
            )
            logger.info(f"Linked contact {source_contact_id} to new user {user_id}")
        except Exception as e:
            logger.error(f"Failed to link source contact {source_contact_id}: {e}")

    # Auto-create the new user as a Contact under the creator (only if NOT converting existing contact)
    contact_created = False
    if x_user_id and not source_contact_id:
        try:
            contact_doc = {
                "user_id": x_user_id,
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "phone": phone,
                "tags": ["new-user"],
                "source": "user_creation",
                "status": "active",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }
            if title:
                contact_doc["title"] = title
            if company:
                contact_doc["company"] = company
            await get_db().contacts.insert_one(contact_doc)
            contact_created = True
            logger.info(f"Auto-created contact for new user {email} under creator {x_user_id}")
        except Exception as e:
            logger.error(f"Failed to auto-create contact for {email}: {e}")
    
    return {
        "success": True,
        "user_id": user_id,
        "email": email,
        "name": name,
        "role": user_role,
        "organization_id": organization_id,
        "store_id": store_id,
        "invite_sent": invite_sent,
        "sms_sent": sms_sent,
        "contact_created": contact_created,
        "temp_password": temp_password,
        "message": f"User created successfully. {'Invite email sent.' if invite_sent else ''} {'SMS sent.' if sms_sent else ''} {'Added to your contacts.' if contact_created else ''}".strip()
    }


@router.get("/users")
async def list_users(
    organization_id: Optional[str] = None,
    store_id: Optional[str] = None,
    role: Optional[str] = None,
    x_user_id: str = Header(None, alias="X-User-ID")
):
    """List users - scoped by requesting user's role"""
    requesting_user = await get_requesting_user(x_user_id)
    
    if requesting_user:
        user_role = requesting_user.get('role', 'user')
        
        if user_role == 'super_admin':
            # Super admin can use any filters
            query = {}
            if organization_id:
                query['organization_id'] = organization_id
            if store_id:
                query['$or'] = [{"store_id": store_id}, {"store_ids": store_id}]
        elif user_role == 'org_admin':
            # Org admin sees users in all their orgs (partner-scoped)
            from routers.rbac import get_scoped_organization_ids
            allowed_orgs = await get_scoped_organization_ids(requesting_user)
            if organization_id and organization_id not in allowed_orgs:
                raise HTTPException(status_code=403, detail="You can only view users in your organizations")
            if organization_id:
                query = {'organization_id': organization_id}
            else:
                query = {'organization_id': {'$in': allowed_orgs}}
            if store_id:
                # Verify store is in their partner orgs
                store = await get_db().stores.find_one({"_id": ObjectId(store_id)})
                if not store or store.get('organization_id') not in allowed_orgs:
                    raise HTTPException(status_code=403, detail="Store not in your organizations")
                query['$or'] = [{"store_id": store_id}, {"store_ids": store_id}]
        elif user_role == 'store_manager':
            # Store manager sees only users in their stores
            allowed_stores = await get_scoped_store_ids(requesting_user)
            query = {
                "$or": [
                    {"store_id": {"$in": allowed_stores}},
                    {"store_ids": {"$elemMatch": {"$in": allowed_stores}}}
                ]
            }
        else:
            # Regular users don't see other users
            return []
        
        if role:
            query['role'] = role
    else:
        # Fallback for backward compatibility
        query = {}
        if organization_id:
            query['organization_id'] = organization_id
        if store_id:
            query['store_id'] = store_id
        if role:
            query['role'] = role
    
    users = await get_db().users.find(query, {"password": 0}).limit(500).to_list(500)
    return [{**user, "_id": str(user["_id"])} for user in users]


@router.get("/users/{user_id}")
async def get_admin_user(user_id: str, x_user_id: str = Header(None, alias="X-User-ID")):
    """Get a specific user (admin view) - with access check"""
    requesting_user = await get_requesting_user(x_user_id)
    
    if requesting_user and requesting_user.get('role') != 'super_admin':
        has_access = await verify_user_access(requesting_user, user_id)
        if not has_access:
            raise HTTPException(status_code=403, detail="Access denied to this user")
    
    user = await get_db().users.find_one({"_id": ObjectId(user_id)}, {"password": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user['_id'] = str(user['_id'])
    return user


@router.put("/users/{user_id}/reset-password")
async def admin_reset_password(
    user_id: str,
    data: dict,
    x_user_id: str = Header(None, alias="X-User-ID")
):
    """Admin resets a user's password"""
    requesting_user = await get_requesting_user(x_user_id)
    if not requesting_user or requesting_user.get('role') not in ('super_admin', 'admin', 'manager'):
        raise HTTPException(status_code=403, detail="Only admins can reset passwords")
    
    new_password = data.get('new_password', '').strip()
    if not new_password or len(new_password) < 4:
        raise HTTPException(status_code=400, detail="Password must be at least 4 characters")
    
    from routers.auth import hash_password
    hashed = hash_password(new_password)
    
    result = await get_db().users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"password": hashed, "needs_password_change": True}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {"message": "Password reset successfully"}


@router.put("/users/{user_id}")
async def update_admin_user(
    user_id: str,
    user_data: dict,
    x_user_id: str = Header(None, alias="X-User-ID")
):
    """Update a user - with RBAC enforcement"""
    requesting_user = await get_requesting_user(x_user_id)
    
    if requesting_user:
        if requesting_user.get('role') != 'super_admin':
            has_access = await verify_user_access(requesting_user, user_id)
            if not has_access:
                raise HTTPException(status_code=403, detail="Access denied to this user")
        
        # Prevent privilege escalation - only super_admin can set super_admin role
        if user_data.get('role') == 'super_admin' and requesting_user.get('role') != 'super_admin':
            raise HTTPException(status_code=403, detail="Only super admins can grant super admin role")
    
    allowed_fields = ['name', 'phone', 'role', 'organization_id', 'store_id', 'state', 'settings', 'is_active', 'onboarding_complete', 'title', 'bio', 'photo_url', 'social_links', 'social_instagram', 'social_facebook', 'social_linkedin']
    update_dict = {k: v for k, v in user_data.items() if k in allowed_fields}
    
    result = await get_db().users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": update_dict}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {"message": "User updated"}




@router.put("/users/{user_id}/reactivate")
async def reactivate_user(
    user_id: str,
    x_user_id: str = Header(None, alias="X-User-ID")
):
    """
    Reactivate a deactivated/inactive user.
    Clears deletion tracking fields and sets is_active=True.
    """
    requesting_user = await get_requesting_user(x_user_id)
    
    if requesting_user:
        role = requesting_user.get('role', 'user')
        if role not in ['super_admin', 'org_admin', 'store_manager']:
            raise HTTPException(status_code=403, detail="Only managers and admins can reactivate users")
        
        if role != 'super_admin':
            has_access = await verify_user_access(requesting_user, user_id)
            if not has_access:
                raise HTTPException(status_code=403, detail="Access denied to this user")
    
    db = get_db()
    
    # Get the user first to check they exist and are inactive
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.get('is_active', True):
        raise HTTPException(status_code=400, detail="User is already active")
    
    # Reactivate the user
    result = await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {
            "$set": {
                "is_active": True,
                "status": user.get('previous_status', 'active'),
                "reactivated_at": datetime.utcnow(),
                "reactivated_by": x_user_id,
                "updated_at": datetime.utcnow()
            },
            "$unset": {
                "deleted_at": "",
                "deletion_source": "",
                "deletion_reason": "",
                "previous_status": ""
            }
        }
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=500, detail="Failed to reactivate user")
    
    logger.info(f"User {user_id} reactivated by {x_user_id}")
    
    return {
        "message": "User reactivated successfully",
        "user_id": user_id,
        "user_name": user.get('name')
    }


@router.delete("/users/{user_id}")
async def delete_admin_user(user_id: str, x_user_id: str = Header(None, alias="X-User-ID")):
    """Delete a user - super_admin or org_admin only"""
    requesting_user = await get_requesting_user(x_user_id)
    
    if requesting_user:
        role = requesting_user.get('role', 'user')
        if role not in ['super_admin', 'org_admin']:
            raise HTTPException(status_code=403, detail="Only admins can delete users")
        
        if role != 'super_admin':
            has_access = await verify_user_access(requesting_user, user_id)
            if not has_access:
                raise HTTPException(status_code=403, detail="Access denied to this user")
    
    # SOFT DELETE: Never truly delete users - deactivate instead
    from datetime import timedelta
    now = datetime.utcnow()
    grace_end = now + timedelta(days=180)  # 6-month access purge
    hard_delete = now + timedelta(days=365)  # 12-month data retention
    
    # Get the user being deleted
    user_to_deactivate = await get_db().users.find_one({"_id": ObjectId(user_id)})
    if not user_to_deactivate:
        raise HTTPException(status_code=404, detail="User not found")
    
    is_individual = not user_to_deactivate.get('organization_id') and not user_to_deactivate.get('store_id')
    
    # Deactivate user (never hard delete)
    result = await get_db().users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {
            "is_active": False,
            "status": "deactivated",
            "deactivated_at": now,
            "deactivated_by": x_user_id or "system",
            "grace_period_end": grace_end,
            "hard_delete_date": hard_delete,
        }}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Handle contacts based on ownership
    if not is_individual:
        # ORG USER: Personal contacts stay personal (removed from org view).
        # Org/shared contacts transfer to the organization.
        
        # 1. Personal contacts: hide from org — these belong to the user, not the company
        personal_count = await get_db().contacts.count_documents(
            {"user_id": user_id, "ownership_type": "personal"}
        )
        if personal_count > 0:
            await get_db().contacts.update_many(
                {"user_id": user_id, "ownership_type": "personal"},
                {"$set": {
                    "status": "hidden",
                    "hidden_at": now,
                    "hidden_reason": "user_deactivated",
                    "original_user_id": user_id,
                }}
            )
        
        # 2. Org/shared contacts: stay visible, transfer to org ownership
        org_contact_count = await get_db().contacts.count_documents(
            {"user_id": user_id, "ownership_type": {"$ne": "personal"}}
        )
        await get_db().contacts.update_many(
            {"user_id": user_id, "ownership_type": {"$ne": "personal"}},
            {"$set": {
                "original_user_id": user_id,
                "user_deactivated": True,
                "transferred_to_org_at": now,
            }}
        )
        
        archived_count = personal_count
        logger.info(f"User {user_id} deactivated. {personal_count} personal contacts hidden (stay with user), {org_contact_count} org contacts retained by org.")
    else:
        # INDIVIDUAL USER: they keep everything, just deactivated
        archived_count = 0
        org_contact_count = 0
        logger.info(f"Individual user {user_id} deactivated. All contacts retained. Hard delete: {hard_delete.isoformat()}")
    
    # Fire lifecycle hooks
    try:
        from .user_lifecycle import on_user_deactivated
        await on_user_deactivated(user_id, x_user_id)
    except Exception as e:
        logger.warning(f"Lifecycle deactivation hook error: {e}")
    
    return {
        "message": "User deactivated",
        "grace_period_end": grace_end.isoformat(),
        "hard_delete_date": hard_delete.isoformat(),
        "personal_contacts_archived": archived_count,
        "org_contacts_retained": org_contact_count,
        "conversion_available": not is_individual,
    }


@router.delete("/users/{user_id}/hard")
async def hard_delete_user(user_id: str, x_user_id: str = Header(None, alias="X-User-ID")):
    """Permanently delete a user from the system. Super admin only.
    Contacts are kept and reassigned to 'unassigned'."""
    requesting_user = await get_requesting_user(x_user_id)
    if not requesting_user or requesting_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Only super admins can hard delete")

    db = get_db()
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Reassign their contacts to 'unassigned' so data is preserved
    contacts_updated = await db.contacts.update_many(
        {"user_id": user_id},
        {"$set": {"original_user_id": user_id, "user_id": "unassigned", "user_deactivated": True}}
    )

    # Remove archived contacts for this user
    await db.archived_contacts.delete_many({"original_user_id": user_id})

    # Delete the user document
    await db.users.delete_one({"_id": ObjectId(user_id)})

    logger.info(f"User {user_id} ({user.get('name')}) hard deleted by {x_user_id}. {contacts_updated.modified_count} contacts reassigned.")

    return {
        "message": "User permanently deleted",
        "contacts_reassigned": contacts_updated.modified_count,
    }
async def convert_to_individual(user_id: str, x_user_id: str = Header(None, alias="X-User-ID")):
    """Convert a deactivated org user to an individual account with their personal data.
    Restores archived personal contacts and strips org association."""
    db = get_db()
    
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.get("is_active", True) and user.get("status") != "deactivated":
        raise HTTPException(status_code=400, detail="User must be deactivated first")
    
    # 1. Restore archived personal contacts back to the contacts collection
    archived = await db.archived_contacts.find(
        {"original_user_id": user_id}
    ).to_list(None)
    
    restored_count = 0
    if archived:
        for contact in archived:
            contact.pop("archived_at", None)
            contact.pop("archive_reason", None)
            contact.pop("retain_until", None)
            contact.pop("_id", None)
            contact["status"] = "active"
            contact.pop("hidden_at", None)
            contact.pop("hidden_reason", None)
            contact.pop("purge_date", None)
            contact.pop("hard_delete_date", None)
        
        await db.contacts.insert_many(archived)
        restored_count = len(archived)
        
        # Remove the hidden personal contacts (they've been restored from archive)
        await db.contacts.delete_many({
            "user_id": user_id,
            "ownership_type": "personal",
            "status": "hidden",
            "hidden_reason": "user_deactivated"
        })
        
        # Clean up archive
        await db.archived_contacts.delete_many({"original_user_id": user_id})
    
    # 2. Convert user to individual (strip org/store)
    await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {
            "is_active": True,
            "status": "active",
            "role": "individual",
            "organization_id": None,
            "store_id": None,
            "converted_from_org": user.get("organization_id"),
            "converted_at": datetime.utcnow(),
            "converted_by": x_user_id or "system",
        }, "$unset": {
            "deactivated_at": "",
            "deactivated_by": "",
            "grace_period_end": "",
            "hard_delete_date": "",
        }}
    )
    
    return {
        "message": "User converted to individual account",
        "personal_contacts_restored": restored_count,
        "org_contacts_stayed_with_store": True,
    }




@router.post("/users/{user_id}/reactivate")
async def reactivate_user(user_id: str, x_user_id: str = Header(None, alias="X-User-ID")):
    """Reactivate a deactivated user and restore their hidden contacts"""
    db = get_db()
    requesting_user = await get_requesting_user(x_user_id)
    if requesting_user:
        role = requesting_user.get('role', 'user')
        if role not in ['super_admin', 'org_admin']:
            raise HTTPException(status_code=403, detail="Only admins can reactivate users")
    
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Reactivate the user
    await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {
            "is_active": True,
            "status": "active",
            "deactivated_at": None,
            "deactivated_by": None,
            "grace_period_end": None,
        }}
    )
    
    # Restore their hidden personal contacts
    restored = await db.contacts.update_many(
        {"user_id": user_id, "status": "hidden", "hidden_reason": "user_deactivated"},
        {"$set": {"status": "active"}, "$unset": {"hidden_at": "", "hidden_reason": "", "purge_date": "", "hard_delete_date": ""}}
    )
    
    # Also restore any archived personal contacts
    archived = await db.archived_contacts.find({"original_user_id": user_id}).to_list(None)
    archive_restored = 0
    if archived:
        for contact in archived:
            contact.pop("archived_at", None)
            contact.pop("archive_reason", None)
            contact.pop("retain_until", None)
            contact.pop("_id", None)
            contact["status"] = "active"
        await db.contacts.insert_many(archived)
        await db.archived_contacts.delete_many({"original_user_id": user_id})
        archive_restored = len(archived)
    
    # Unflag org contacts
    await db.contacts.update_many(
        {"user_id": user_id, "user_deactivated": True},
        {"$unset": {"user_deactivated": ""}}
    )
    
    logger.info(f"User {user_id} reactivated. {restored.modified_count} contacts unhidden, {archive_restored} restored from archive.")
    
    # Fire lifecycle hooks
    try:
        from .user_lifecycle import on_user_reactivated
        await on_user_reactivated(user_id, x_user_id)
    except Exception as e:
        logger.warning(f"Lifecycle reactivation hook error: {e}")
    
    return {"message": "User reactivated", "contacts_restored": restored.modified_count}


@router.get("/users/{user_id}/detail")
async def get_user_detail(user_id: str, x_user_id: str = Header(None, alias="X-User-ID")):
    """Get detailed user info - with access check"""
    db = get_db()
    requesting_user = await get_requesting_user(x_user_id)
    
    if requesting_user and requesting_user.get('role') != 'super_admin':
        has_access = await verify_user_access(requesting_user, user_id)
        if not has_access:
            raise HTTPException(status_code=403, detail="Access denied to this user")
    
    user = await db.users.find_one({"_id": ObjectId(user_id)}, {"password": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user['_id'] = str(user['_id'])
    
    # Get organization if user has one
    organization = None
    if user.get('organization_id'):
        try:
            org = await db.organizations.find_one({"_id": ObjectId(user['organization_id'])})
            if org:
                organization = {
                    "_id": str(org['_id']),
                    "name": org.get('name', 'Unknown')
                }
        except:
            pass
    
    # Get stores the user is assigned to
    stores = []
    store_ids = user.get('store_ids', [])
    if not store_ids and user.get('store_id'):
        store_ids = [user['store_id']]
    
    for store_id in store_ids:
        try:
            store = await db.stores.find_one({"_id": ObjectId(store_id)})
            if store:
                stores.append({
                    "_id": str(store['_id']),
                    "name": store.get('name', 'Unknown'),
                    "city": store.get('city'),
                    "state": store.get('state')
                })
        except:
            pass
    
    # Get available stores for assignment (in same org, not already assigned)
    # For super_admin viewing, show all stores if user has no org
    available_stores = []
    if user.get('organization_id'):
        org_stores = await db.stores.find({
            "organization_id": user['organization_id'],
            "active": True
        }).to_list(100)
        
        assigned_ids = set(store_ids)
        for store in org_stores:
            store_id_str = str(store['_id'])
            if store_id_str not in assigned_ids:
                available_stores.append({
                    "_id": store_id_str,
                    "name": store.get('name', 'Unknown'),
                    "city": store.get('city'),
                    "state": store.get('state')
                })
    elif requesting_user and requesting_user.get('role') == 'super_admin':
        # Super admin can see all active stores for users without an org
        all_stores = await db.stores.find({"active": True}).to_list(100)
        assigned_ids = set(store_ids)
        for store in all_stores:
            store_id_str = str(store['_id'])
            if store_id_str not in assigned_ids:
                available_stores.append({
                    "_id": store_id_str,
                    "name": store.get('name', 'Unknown'),
                    "city": store.get('city'),
                    "state": store.get('state')
                })
    
    return {
        "user": user,
        "organization": organization,
        "stores": stores,
        "available_stores": available_stores
    }


@router.post("/users/{user_id}/impersonate")
async def impersonate_user(user_id: str):
    """
    Generate an impersonation token for an admin to act as another user.
    Returns a token and user data that can be used to temporarily become that user.
    """
    db = get_db()
    
    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)})
    except Exception:
        raise HTTPException(status_code=404, detail="User not found")
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Generate impersonation token (using same mock pattern as auth)
    import secrets
    impersonation_token = f"impersonate_{secrets.token_hex(12)}"
    
    # Store the impersonation session (optional - for tracking)
    await db.impersonation_sessions.insert_one({
        "token": impersonation_token,
        "target_user_id": user_id,
        "created_at": datetime.utcnow(),
        "expires_at": datetime.utcnow()  # Can add expiration if needed
    })
    
    # Prepare user data (same format as login response)
    from permissions import merge_permissions
    
    # Merge feature permissions with role-based defaults
    feature_permissions = merge_permissions(
        user.get('feature_permissions'), 
        user.get('role', 'user')
    )
    
    # Resolve store slug and name
    store_slug = None
    store_name = None
    if user.get('store_id'):
        try:
            store = await db.stores.find_one({"_id": ObjectId(user['store_id'])}, {"slug": 1, "name": 1})
            if store:
                store_name = store.get('name')
                slug = store.get('slug')
                if not slug and store_name:
                    import re as re_mod
                    slug = re_mod.sub(r'[^a-z0-9]+', '-', store_name.lower()).strip('-')
                store_slug = slug
        except Exception:
            pass
    
    # Resolve org slug and name — check both org_id and organization_id fields
    org_slug = None
    org_name = None
    org_id = user.get('organization_id') or user.get('org_id')
    if org_id:
        try:
            org = await db.organizations.find_one({"_id": ObjectId(org_id)}, {"slug": 1, "name": 1})
            if org:
                org_name = org.get('name')
                o_slug = org.get('slug')
                if not o_slug and org_name:
                    import re as re_mod
                    o_slug = re_mod.sub(r'[^a-z0-9]+', '-', org_name.lower()).strip('-')
                org_slug = o_slug
        except Exception:
            pass
    
    user_data = {
        "_id": str(user["_id"]),
        "email": user.get("email"),
        "name": user.get("name"),
        "role": user.get("role"),
        "store_id": user.get("store_id"),
        "store_ids": user.get("store_ids", []),
        "store_name": store_name or user.get("store_name"),
        "organization_id": user.get("organization_id") or user.get("org_id"),
        "org_id": user.get("organization_id") or user.get("org_id"),
        "organization_name": org_name or user.get("organization_name"),
        "title": user.get("title"),
        "phone": user.get("phone"),
        "photo_url": user.get("photo_url"),
        "bio": user.get("bio"),
        "username": user.get("username"),
        "social_links": user.get("social_links", {}),
        "persona": user.get("persona", {}),
        "is_active": user.get("is_active", True),
        "onboarding_complete": user.get("onboarding_complete", True),
        "twilio_phone_number": user.get("twilio_phone_number"),
        "mvpline_number": user.get("mvpline_number"),
        "feature_permissions": feature_permissions,
        "email_brand_kit": user.get("email_brand_kit", {}),
        "isImpersonating": True,
    }
    
    # Resolve partner_id: check user record first, then fall back to org
    partner_id = user.get("partner_id")
    if not partner_id and org_id:
        try:
            org_doc = await db.organizations.find_one(
                {"_id": ObjectId(org_id)}, {"partner_id": 1}
            )
            if org_doc and org_doc.get("partner_id"):
                partner_id = org_doc["partner_id"]
        except Exception:
            pass
    if partner_id:
        user_data["partner_id"] = partner_id
    if store_slug:
        user_data["store_slug"] = store_slug
    if org_slug:
        user_data["org_slug"] = org_slug
    
    # Convert any remaining ObjectIds to strings
    for k, v in user_data.items():
        if isinstance(v, ObjectId):
            user_data[k] = str(v)

    # Use same robust serializer as /auth/login to handle nested ObjectIds and datetimes
    import json as json_mod
    from fastapi.responses import JSONResponse

    def _serialize(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, ObjectId):
            return str(obj)
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    response_payload = {
        "success": True,
        "token": impersonation_token,
        "user": user_data,
        "message": f"Now impersonating {user.get('name', 'user')}"
    }
    return JSONResponse(content=json_mod.loads(json_mod.dumps(response_payload, default=_serialize)))


# ============= PENDING USERS =============
@router.get("/pending-users")
async def get_pending_users():
    """Get all users with pending status"""
    users = await get_db().users.find(
        {"status": "pending"},
        {"password": 0}
    ).sort("created_at", -1).limit(500).to_list(500)
    
    # Get org names for display
    org_ids = list(set([u.get("organization_id") for u in users if u.get("organization_id")]))
    orgs = {}
    if org_ids:
        org_docs = await get_db().organizations.find(
            {"_id": {"$in": [ObjectId(oid) for oid in org_ids if oid]}}
        ).to_list(100)
        orgs = {str(o["_id"]): o.get("name") for o in org_docs}
    
    result = []
    for u in users:
        result.append({
            "_id": str(u["_id"]),
            "name": u.get("name"),
            "email": u.get("email"),
            "phone": u.get("phone"),
            "requested_role": u.get("requested_role", "Not specified"),
            "organization_id": u.get("organization_id"),
            "organization_name": orgs.get(u.get("organization_id")),
            "status": u.get("status", "pending"),
            "created_at": u.get("created_at"),
        })
    
    return result

@router.get("/pending-users/count")
async def get_pending_users_count():
    """Get count of pending users (for notification badge)"""
    count = await get_db().users.count_documents({"status": "pending"})
    return {"count": count}

@router.put("/pending-users/{user_id}/approve")
async def approve_pending_user(user_id: str, data: dict):
    """Approve a pending user and configure their access"""
    user = await get_db().users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    update_data = {
        "status": "active",
        "updated_at": datetime.utcnow()
    }
    
    # Optional: Set role, org, store during approval
    if data.get("role"):
        update_data["role"] = data["role"]
    if data.get("organization_id"):
        update_data["organization_id"] = data["organization_id"]
    if data.get("store_id"):
        update_data["store_id"] = data["store_id"]
        if "store_ids" not in update_data:
            update_data["store_ids"] = [data["store_id"]]
    if data.get("store_ids"):
        update_data["store_ids"] = data["store_ids"]
    if data.get("mvpline_number"):
        update_data["mvpline_number"] = data["mvpline_number"]
    
    await get_db().users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": update_data}
    )
    
    return {"message": "User approved", "user_id": user_id}

@router.put("/pending-users/{user_id}/reject")
async def reject_pending_user(user_id: str, data: dict = {}):
    """Reject/delete a pending user"""
    reason = data.get("reason", "Application rejected")
    
    # Option: Could mark as rejected instead of deleting
    result = await get_db().users.delete_one({
        "_id": ObjectId(user_id),
        "status": "pending"
    })
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Pending user not found")
    
    return {"message": "User rejected", "reason": reason}



@router.post("/users/add-team-member")
async def add_team_member(data: AddTeamMemberRequest):
    """
    Add a new team member to a store.
    This is used by store managers to add users to their team.
    Triggers onboarding flow and sends welcome SMS.
    """
    import secrets
    import os
    
    db = get_db()
    
    # Verify the store exists
    store = await db.stores.find_one({"_id": ObjectId(data.store_id)})
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    
    # Verify the adding user has permission
    adding_user = await db.users.find_one({"_id": ObjectId(data.added_by)})
    if not adding_user:
        raise HTTPException(status_code=404, detail="Adding user not found")
    
    # Check if adding user is a manager of this store
    if adding_user.get("role") not in ["super_admin", "org_admin", "store_manager"]:
        raise HTTPException(status_code=403, detail="You don't have permission to add team members")
    
    # Normalize email
    email = data.email.lower().strip()
    
    # Check if email already exists
    existing = await db.users.find_one({"email": email})
    if existing:
        raise HTTPException(status_code=400, detail="A user with this email already exists")
    
    # Normalize phone
    phone_clean = ''.join(c for c in data.phone if c.isdigit())
    if len(phone_clean) == 10:
        phone_clean = '1' + phone_clean
    phone = '+' + phone_clean if phone_clean else ''
    
    # Check if phone already exists
    if phone:
        existing_phone = await db.users.find_one({"phone": phone})
        if existing_phone:
            raise HTTPException(status_code=400, detail="A user with this phone number already exists")
    
    # Generate temporary password
    temp_password = secrets.token_urlsafe(8)
    
    # Create user
    new_user = {
        "name": data.name.strip(),
        "email": email,
        "phone": phone,
        "password": temp_password,  # Should be hashed in production
        "role": data.role if data.role in ["user", "store_manager"] else "user",
        "store_id": data.store_id,
        "store_ids": [data.store_id],
        "organization_id": store.get("organization_id"),
        "created_at": datetime.utcnow(),
        "added_by": data.added_by,
        "is_active": True,
        "status": "active",
        "onboarding_complete": False,
        "settings": {
            "leaderboard_visible": False,
            "compare_scope": "store"
        },
        "stats": {
            "contacts_added": 0,
            "messages_sent": 0,
            "calls_made": 0,
            "deals_closed": 0
        }
    }
    
    # Auto-inherit partner_id from the organization
    org_id = store.get("organization_id")
    if org_id:
        try:
            org = await db.organizations.find_one(
                {"_id": ObjectId(org_id)}, {"partner_id": 1}
            )
            if org and org.get('partner_id'):
                new_user['partner_id'] = org['partner_id']
        except Exception:
            pass
    
    result = await db.users.insert_one(new_user)
    user_id = str(result.inserted_id)
    new_user["_id"] = user_id
    
    # Seed all default templates, campaigns, and triggers
    try:
        from services.seed_defaults import seed_user_defaults
        await seed_user_defaults(user_id)
    except Exception as e:
        logger.error(f"Failed to seed defaults for user {user_id}: {e}")
    
    # Get onboarding settings
    settings = await db.onboarding_settings.find_one({"store_id": data.store_id})
    if not settings and store.get("organization_id"):
        settings = await db.onboarding_settings.find_one({
            "organization_id": store["organization_id"],
            "store_id": None
        })
    if not settings:
        settings = await db.onboarding_settings.find_one({"is_global": True})
    
    # Generate training link
    base_url = os.environ.get("SHORT_URL_DOMAIN", "https://app.imonsocial.com")
    training_token = secrets.token_urlsafe(16)
    training_link = f"{base_url}/onboarding?token={training_token}"
    
    # Build welcome message
    message_template = ""
    if settings:
        message_template = settings.get("messages", {}).get("team_welcome_sms", "")
    
    if message_template:
        message = message_template.replace("{training_link}", training_link)
        message = message.replace("{user_name}", data.name.strip())
        message = message.replace("{store_name}", store.get("name", ""))
    else:
        message = f"Welcome to {store.get('name')}! Complete your training to get started: {training_link}"
    
    # Queue welcome SMS
    sms_sent = False
    sms_error = None
    if settings and settings.get("auto_send_welcome_sms", True):
        try:
            from services.twilio_service import send_sms
            result_sms = await send_sms(phone, message)
            if result_sms.get("success"):
                sms_sent = True
        except Exception as e:
            sms_error = str(e)
    
    # Create activity log
    await db.activity.insert_one({
        "type": "team_member_added",
        "user_id": user_id,
        "actor_id": data.added_by,
        "actor_name": adding_user.get("name"),
        "store_id": data.store_id,
        "organization_id": store.get("organization_id"),
        "details": {
            "new_user_name": data.name.strip(),
            "new_user_email": email,
            "new_user_role": data.role,
        },
        "created_at": datetime.utcnow()
    })
    
    # Remove sensitive data
    del new_user["password"]
    
    return {
        "success": True,
        "user": new_user,
        "training_link": training_link,
        "sms_sent": sms_sent,
        "sms_error": sms_error,
        "message": f"{data.name} has been added to your team."
    }




@router.put("/users/{user_id}/status")
async def update_user_status(user_id: str, data: dict):
    """
    Activate or deactivate a user.
    Used by managers to manage their team.
    """
    db = get_db()
    
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    status = data.get("status")
    if status not in ["active", "inactive"]:
        raise HTTPException(status_code=400, detail="Invalid status. Must be 'active' or 'inactive'")
    
    update_data = {
        "status": status,
        "updated_at": datetime.utcnow()
    }
    
    if status == "inactive":
        update_data["deactivated_at"] = datetime.utcnow()
        update_data["deactivated_by"] = data.get("deactivated_by")
    else:
        update_data["reactivated_at"] = datetime.utcnow()
        update_data["reactivated_by"] = data.get("reactivated_by")
    
    await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": update_data}
    )
    
    # Log activity
    actor_id = data.get("deactivated_by") or data.get("reactivated_by")
    if actor_id:
        actor = await db.users.find_one({"_id": ObjectId(actor_id)})
        await db.activity.insert_one({
            "type": f"user_{status}",
            "user_id": user_id,
            "actor_id": actor_id,
            "actor_name": actor.get("name") if actor else "Unknown",
            "store_id": user.get("store_id"),
            "organization_id": user.get("organization_id"),
            "details": {
                "user_name": user.get("name"),
                "user_email": user.get("email"),
            },
            "created_at": datetime.utcnow()
        })
    
    return {"success": True, "status": status}



def _resize_image(contents: bytes, max_size: int = 128) -> str:
    """Resize image to avatar size and return base64 data URL."""
    from PIL import Image
    import io
    img = Image.open(io.BytesIO(contents)).convert("RGBA")
    img.thumbnail((max_size, max_size), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{b64}"


@router.post("/stores/{store_id}/upload-logo")
async def upload_store_logo(store_id: str, file: UploadFile = File(...)):
    """Upload a logo for a store/account. Stores original + generates thumbnail & avatar."""
    db = get_db()

    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image must be less than 10MB")

    try:
        from utils.image_storage import upload_image
        result = await upload_image(contents, prefix="logos/stores", entity_id=store_id)
        if result:
            logo_url = f"/api/images/{result['original_path']}"
            thumb_url = f"/api/images/{result['thumbnail_path']}"
            avatar_url = f"/api/images/{result['avatar_path']}"
        else:
            raise Exception("Upload returned None")
    except Exception as e:
        logger.warning(f"Object storage upload failed, falling back to base64: {e}")
        logo_url = f"data:{file.content_type};base64,{base64.b64encode(contents).decode('utf-8')}"
        avatar_url = _resize_image(contents, 128)
        thumb_url = avatar_url

    await db.stores.update_one(
        {"_id": ObjectId(store_id)},
        {"$set": {
            "logo_url": logo_url,
            "logo_thumbnail_url": thumb_url,
            "logo_avatar_url": avatar_url,
            "updated_at": datetime.utcnow(),
        }}
    )

    return {"success": True, "logo_url": logo_url, "thumbnail_url": thumb_url, "avatar_url": avatar_url}


@router.post("/organizations/{org_id}/upload-logo")
async def upload_org_logo(org_id: str, file: UploadFile = File(...)):
    """Upload a logo for an organization. Stores original + generates thumbnail & avatar."""
    db = get_db()

    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image must be less than 10MB")

    try:
        from utils.image_storage import upload_image
        result = await upload_image(contents, prefix="logos/orgs", entity_id=org_id)
        if result:
            logo_url = f"/api/images/{result['original_path']}"
            thumb_url = f"/api/images/{result['thumbnail_path']}"
            avatar_url = f"/api/images/{result['avatar_path']}"
        else:
            raise Exception("Upload returned None")
    except Exception as e:
        logger.warning(f"Object storage upload failed, falling back to base64: {e}")
        logo_url = f"data:{file.content_type};base64,{base64.b64encode(contents).decode('utf-8')}"
        avatar_url = _resize_image(contents, 128)
        thumb_url = avatar_url

    await db.organizations.update_one(
        {"_id": ObjectId(org_id)},
        {"$set": {
            "logo_url": logo_url,
            "logo_thumbnail_url": thumb_url,
            "logo_avatar_url": avatar_url,
            "updated_at": datetime.utcnow(),
        }}
    )

    return {"success": True, "logo_url": logo_url, "thumbnail_url": thumb_url, "avatar_url": avatar_url}


@router.post("/seed/backfill-all")
async def backfill_all_user_defaults():
    """Backfill default templates, campaigns, and date triggers for ALL existing users."""
    try:
        from services.seed_defaults import backfill_all_users
        result = await backfill_all_users()
        return {"status": "success", **result}
    except Exception as e:
        import traceback
        logger.error(f"Backfill error: {traceback.format_exc()}")
        return {"status": "error", "message": str(e)}



# ============= FEATURE PERMISSIONS =============



@router.get("/permissions/{user_id}")
async def get_user_permissions(user_id: str, x_user_id: str = Header(None, alias="X-User-ID")):
    """Get a user's feature permissions (merged with defaults)."""
    from permissions import merge_permissions
    requesting = await get_requesting_user(x_user_id)
    db = get_db()
    target = await db.users.find_one({"_id": ObjectId(user_id)}, {"feature_permissions": 1, "name": 1, "email": 1, "role": 1})
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    perms = merge_permissions(target.get("feature_permissions"), target.get("role", "user"))
    return {
        "user_id": user_id,
        "name": target.get("name", ""),
        "email": target.get("email", ""),
        "role": target.get("role", "user"),
        "permissions": perms,
    }


@router.put("/permissions/{user_id}")
async def update_user_permissions(user_id: str, data: dict, x_user_id: str = Header(None, alias="X-User-ID")):
    """Update a user's feature permissions. Only admins can call this."""
    requesting = await get_requesting_user(x_user_id)
    if not requesting:
        raise HTTPException(status_code=401, detail="Authentication required")
    req_role = requesting.get("role", "user")
    if req_role not in ("super_admin", "org_admin", "store_manager"):
        raise HTTPException(status_code=403, detail="Only admins can manage permissions")
    db = get_db()
    target = await db.users.find_one({"_id": ObjectId(user_id)}, {"_id": 1})
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    permissions = data.get("permissions", {})
    await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"feature_permissions": permissions, "permissions_updated_at": datetime.utcnow()}}
    )
    from permissions import merge_permissions
    target_user = await db.users.find_one({"_id": ObjectId(user_id)}, {"role": 1})
    target_role = target_user.get("role", "user") if target_user else "user"
    return {"status": "ok", "permissions": merge_permissions(permissions, target_role)}


@router.post("/send-power-rankings")
async def trigger_power_rankings(x_user_id: str = Header(None, alias="X-User-ID")):
    """Manually trigger the weekly Power Rankings email. Admin only."""
    requesting = await get_requesting_user(x_user_id)
    if requesting.get("role") not in ("super_admin", "org_admin"):
        raise HTTPException(status_code=403, detail="Admin only")
    db = get_db()
    from services.power_rankings import send_weekly_power_rankings
    count = await send_weekly_power_rankings(db)
    return {"status": "ok", "emails_sent": count}


