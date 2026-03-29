"""
admin.py — Organizations, stores, billing, phone assignments, stats, and misc admin.

Split architecture:
  admin_users.py      — User CRUD, pending users, impersonation, permissions
  admin_hierarchy.py  — Org/store assignment, role changes, hierarchy views
  admin_helpers.py    — Shared utilities (safe_objectid, send_invite_email, etc.)
"""
from fastapi import APIRouter, HTTPException, Header, UploadFile, File
from bson import ObjectId
from datetime import datetime
from typing import Optional
import logging
import os
import asyncio
import resend
import base64

from models import Organization, OrganizationCreate, Store, StoreCreate
from routers.database import get_db, get_user_by_id
from routers.rbac import (
    get_scoped_organization_ids,
    get_scoped_store_ids,
    get_scoped_user_ids,
    verify_organization_access,
    verify_store_access,
    verify_user_access,
    has_permission,
    ROLE_HIERARCHY
)

from routers.auth import hash_password

router = APIRouter(prefix="/admin", tags=["Admin"])
logger = logging.getLogger(__name__)

def safe_objectid(val):
    """Convert a string to ObjectId, return None if invalid."""
    try:
        return ObjectId(val)
    except Exception:
        return None

# Initialize Resend for invite emails
RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "notifications@send.imonsocial.com")

APP_URL = os.environ.get("PUBLIC_FACING_URL", os.environ.get("APP_URL", "https://app.imonsocial.com"))

if RESEND_API_KEY:
    resend.api_key = RESEND_API_KEY


async def send_invite_email(email: str, name: str, temp_password: str, role: str, inviter_name: str = None):
    """Send invite email to new user with embedded logo via CID attachment"""
    import base64 as b64_mod
    
    if not RESEND_API_KEY:
        logger.warning("Resend API key not configured, skipping invite email")
        return False
    
    role_title = {
        'org_admin': 'Organization Administrator',
        'store_manager': 'Store Manager',
        'user': 'Team Member'
    }.get(role, 'Team Member')
    
    login_url = f"{APP_URL}/imos/login"
    
    # Read the optimized logo and encode for CID attachment
    logo_b64 = ""
    logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "imos-logo-email.png")
    try:
        with open(logo_path, "rb") as f:
            logo_b64 = b64_mod.b64encode(f.read()).decode()
    except Exception as e:
        logger.warning(f"Could not read logo file: {e}")
    
    email_payload = {
        "from": f"i'M On Social <{SENDER_EMAIL}>",
        "to": email,
        "reply_to": "support@imonsocial.com",
        "subject": f"You're Invited to Join i'M On Social as {role_title}",
        "html": f"""
            <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f5f5f5;">
                <div style="background-color: #ffffff; border-radius: 16px; overflow: hidden; border: 1px solid #e5e5e5;">
                    <div style="text-align: center; padding: 32px 20px 20px 20px; border-bottom: 1px solid #eee;">
                        <img src="cid:imos-logo" alt="i'M On Social" width="100" height="100" style="width: 100px; height: 100px; border-radius: 50%; display: block; margin: 0 auto;" />
                        <p style="margin: 10px 0 0 0; font-size: 13px; color: #888; letter-spacing: 1px;">Relationship Management System</p>
                    </div>
                    
                    <div style="padding: 32px 30px; background-color: #ffffff;">
                        <h2 style="margin: 0 0 8px 0; color: #111; font-size: 22px;">Welcome, {name}!</h2>
                        <p style="font-size: 15px; line-height: 1.6; color: #444; margin: 0 0 24px 0;">You've been invited to join <strong>i'M On Social</strong> as a <strong style="color: #007AFF;">{role_title}</strong>{f' by {inviter_name}' if inviter_name else ''}.</p>
                        
                        <div style="background-color: #f8f9fa; padding: 20px 24px; border-radius: 12px; margin: 0 0 24px 0; border: 1px solid #e9ecef;">
                            <p style="margin: 0 0 14px 0; font-weight: 700; color: #333; font-size: 14px;">Your Login Credentials</p>
                            <table style="width: 100%; border-collapse: collapse;">
                                <tr>
                                    <td style="padding: 8px 0; color: #666; font-size: 14px; width: 160px;">Email:</td>
                                    <td style="padding: 8px 0;"><code style="background: #fff; padding: 5px 12px; border-radius: 6px; color: #111; font-size: 14px; border: 1px solid #ddd;">{email}</code></td>
                                </tr>
                                <tr>
                                    <td style="padding: 8px 0; color: #666; font-size: 14px;">Temporary Password:</td>
                                    <td style="padding: 8px 0;"><code style="background: #fff; padding: 5px 12px; border-radius: 6px; color: #111; font-size: 14px; font-weight: 600; border: 1px solid #ddd;">{temp_password}</code></td>
                                </tr>
                            </table>
                        </div>
                        
                        <p style="font-size: 14px; color: #666; margin: 0 0 28px 0;">You'll be prompted to create a new password when you first log in.</p>
                        
                        <div style="text-align: center;">
                            <a href="{login_url}" style="display: inline-block; background-color: #007AFF; color: #ffffff; padding: 14px 40px; text-decoration: none; border-radius: 8px; font-weight: 700; font-size: 16px;">
                                Get Started
                            </a>
                        </div>
                    </div>
                </div>
                
                <div style="text-align: center; margin-top: 24px; color: #999; font-size: 12px;">
                    <p style="margin: 5px 0;">i'M On Social &mdash; Your Relationship Management System</p>
                    <p style="margin: 5px 0;">Questions? Contact support@imonsocial.com</p>
                </div>
            </div>
            """
    }
    
    # Add logo as inline CID attachment if available
    if logo_b64:
        email_payload["attachments"] = [{
            "filename": "imos-logo.png",
            "content": logo_b64,
            "content_id": "imos-logo",
        }]
    
    try:
        result = await asyncio.to_thread(resend.Emails.send, email_payload)
        logger.info(f"Invite email sent to {email}, resend_id: {result.get('id')}")
        return True
    except Exception as e:
        logger.error(f"Failed to send invite email to {email}: {str(e)}")
        return False


async def get_requesting_user(x_user_id: str = Header(None, alias="X-User-ID")) -> dict:
    """Helper to get the requesting user for RBAC checks"""
    if not x_user_id:
        return None
    return await get_user_by_id(x_user_id)


# ============= ORGANIZATION ENDPOINTS =============
@router.post("/organizations")
async def create_organization(
    org_data: OrganizationCreate,
    x_user_id: str = Header(None, alias="X-User-ID")
):
    """Create a new organization - super_admin or partner org_admin"""
    user = await get_requesting_user(x_user_id)
    if not user:
        raise HTTPException(status_code=403, detail="Authentication required")
    
    role = user.get('role', 'user')
    partner_id = None
    
    if role == 'super_admin':
        pass  # Can create any org
    elif role == 'org_admin':
        # Check if user belongs to a partner — allow partner admins to create orgs
        from routers.rbac import get_user_partner_id
        partner_id = await get_user_partner_id(user)
        if not partner_id:
            raise HTTPException(status_code=403, detail="Only super admins or partner admins can create organizations")
    else:
        raise HTTPException(status_code=403, detail="Only admins can create organizations")
    
    org_dict = org_data.dict()
    org_dict['created_at'] = datetime.utcnow()
    org_dict['active'] = True
    
    # For super_admin: use partner_id from payload if provided
    # For partner admin: override with their own partner_id
    if partner_id:
        org_dict['partner_id'] = partner_id
    elif role == 'super_admin' and org_dict.get('partner_id'):
        partner_id = org_dict['partner_id']
    else:
        org_dict.pop('partner_id', None)
    
    result = await get_db().organizations.insert_one(org_dict)
    org_dict['_id'] = str(result.inserted_id)
    
    # Auto-assign org to partner's organization_ids list
    if partner_id:
        try:
            await get_db().white_label_partners.update_one(
                {"_id": ObjectId(partner_id)},
                {"$addToSet": {"organization_ids": str(result.inserted_id)}}
            )
        except Exception:
            pass
    
    return org_dict


@router.get("/organizations")
async def list_organizations(x_user_id: str = Header(None, alias="X-User-ID")):
    """List organizations - scoped by user role"""
    user = await get_requesting_user(x_user_id)
    
    if not user:
        # Fallback for backward compatibility - return all (will be restricted later)
        orgs = await get_db().organizations.find({}, {"logo_url": 0, "email_brand_kit.logo_url": 0}).limit(500).to_list(500)
        return [{**org, "_id": str(org["_id"])} for org in orgs]
    
    role = user.get('role', 'user')
    
    if role == 'super_admin':
        # Super admin sees all organizations
        orgs = await get_db().organizations.find({}, {"logo_url": 0, "email_brand_kit.logo_url": 0}).limit(500).to_list(500)
    else:
        # Non-super admins see only their organization
        org_ids = await get_scoped_organization_ids(user)
        if not org_ids:
            return []
        orgs = await get_db().organizations.find({
            "_id": {"$in": [oid for oid in (safe_objectid(x) for x in org_ids) if oid is not None]}
        }, {"logo_url": 0, "email_brand_kit.logo_url": 0}).limit(500).to_list(500)
    
    return [{**org, "_id": str(org["_id"])} for org in orgs]


@router.get("/organizations/{org_id}")
async def get_organization(org_id: str, x_user_id: str = Header(None, alias="X-User-ID")):
    """Get a specific organization - with access check"""
    user = await get_requesting_user(x_user_id)
    
    # Check access if user is authenticated
    if user and user.get('role') != 'super_admin':
        has_access = await verify_organization_access(user, org_id)
        if not has_access:
            raise HTTPException(status_code=403, detail="Access denied to this organization")
    
    org = await get_db().organizations.find_one({"_id": ObjectId(org_id)})
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    org['_id'] = str(org['_id'])
    return org

@router.put("/organizations/{org_id}")
async def update_organization(
    org_id: str,
    org_data: dict,
    x_user_id: str = Header(None, alias="X-User-ID")
):
    """Update an organization - super_admin or org_admin of that org"""
    user = await get_requesting_user(x_user_id)
    
    if user:
        role = user.get('role', 'user')
        if role == 'super_admin':
            pass  # Can update any org
        elif role == 'org_admin':
            from routers.rbac import get_scoped_organization_ids
            allowed_orgs = await get_scoped_organization_ids(user)
            if org_id not in allowed_orgs:
                raise HTTPException(status_code=403, detail="You can only update organizations in your scope")
        else:
            raise HTTPException(status_code=403, detail="Only admins can update organizations")
    
    allowed_fields = ['name', 'email', 'website', 'admin_email', 'admin_phone', 'city', 'state', 'active', 'settings', 'hires_images']
    update_dict = {k: v for k, v in org_data.items() if k in allowed_fields}
    
    result = await get_db().organizations.update_one(
        {"_id": ObjectId(org_id)},
        {"$set": update_dict}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    return {"message": "Organization updated"}


@router.delete("/organizations/{org_id}")
async def delete_organization(org_id: str, x_user_id: str = Header(None, alias="X-User-ID")):
    """Delete an organization - super_admin only"""
    user = await get_requesting_user(x_user_id)
    if not user or user.get('role') != 'super_admin':
        raise HTTPException(status_code=403, detail="Only super admins can delete organizations")
    
    result = await get_db().organizations.delete_one({"_id": ObjectId(org_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    # Delete associated stores
    await get_db().stores.delete_many({"organization_id": org_id})
    
    return {"message": "Organization deleted"}


@router.get("/organizations/{org_id}/users")
async def get_organization_users(
    org_id: str,
    store_id: str = None,
    role: str = None,
    x_user_id: str = Header(None, alias="X-User-ID")
):
    """Get all users in an organization - with access check"""
    db = get_db()
    user = await get_requesting_user(x_user_id)
    
    # Check access if user is authenticated
    if user and user.get('role') != 'super_admin':
        has_access = await verify_organization_access(user, org_id)
        if not has_access:
            raise HTTPException(status_code=403, detail="Access denied to this organization")
    
    # Build filter
    query = {"organization_id": org_id}
    if store_id:
        # Check store access for non-super admins
        if user and user.get('role') not in ['super_admin', 'org_admin']:
            has_store_access = await verify_store_access(user, store_id)
            if not has_store_access:
                raise HTTPException(status_code=403, detail="Access denied to this store")
        
        query["$or"] = [
            {"store_ids": store_id},
            {"store_id": store_id}
        ]
    if role:
        query["role"] = role
    
    users = await db.users.find(query, {"password": 0}).to_list(500)
    
    # Convert ObjectIds to strings
    for user_doc in users:
        user_doc['_id'] = str(user_doc['_id'])
        if user_doc.get('organization_id'):
            user_doc['organization_id'] = str(user_doc['organization_id'])
    
    return users


@router.get("/organizations/{org_id}/leaderboard")
async def get_organization_leaderboard(
    org_id: str,
    store_id: Optional[str] = None,
    metric: str = "contacts_added",
    x_user_id: str = Header(None, alias="X-User-ID")
):
    """Get leaderboard for an organization - with RBAC"""
    db = get_db()
    user = await get_requesting_user(x_user_id)
    
    # Check access if user is authenticated
    if user and user.get('role') != 'super_admin':
        has_access = await verify_organization_access(user, org_id)
        if not has_access:
            raise HTTPException(status_code=403, detail="Access denied to this organization")
    
    # Build query
    query = {"organization_id": org_id}
    if store_id:
        # Check store access for managers
        if user and user.get('role') == 'store_manager':
            has_store_access = await verify_store_access(user, store_id)
            if not has_store_access:
                raise HTTPException(status_code=403, detail="Access denied to this store")
        query["$or"] = [
            {"store_id": store_id},
            {"store_ids": store_id}
        ]
    
    # Get users in org/store
    users = await db.users.find(query, {"password": 0}).limit(500).to_list(500)
    
    # Sort by metric
    sorted_users = sorted(
        users,
        key=lambda u: u.get('stats', {}).get(metric, 0),
        reverse=True
    )
    
    # Build leaderboard
    leaderboard = []
    for i, u in enumerate(sorted_users):
        leaderboard.append({
            "rank": i + 1,
            "user_id": str(u['_id']),
            "name": u.get('name', 'Unknown'),
            "photo_url": u.get('photo_url'),
            "metric_value": u.get('stats', {}).get(metric, 0),
            "store_id": u.get('store_id'),
            "role": u.get('role', 'user')
        })
    
    return {
        "organization_id": org_id,
        "store_id": store_id,
        "metric": metric,
        "leaderboard": leaderboard
    }


# ============= STORE ENDPOINTS =============
@router.post("/stores")
async def create_store(store_data: StoreCreate, x_user_id: str = Header(None, alias="X-User-ID")):
    """Create a new store - super_admin or org_admin only (partner-aware)"""
    user = await get_requesting_user(x_user_id)
    
    if user:
        role = user.get('role', 'user')
        if role not in ['super_admin', 'org_admin']:
            raise HTTPException(status_code=403, detail="Only admins can create stores")
        
        # Org admins: check they can access the target org (partner-scoped)
        if role == 'org_admin':
            from routers.rbac import get_scoped_organization_ids
            allowed_orgs = await get_scoped_organization_ids(user)
            if store_data.organization_id and store_data.organization_id not in allowed_orgs:
                raise HTTPException(status_code=403, detail="You can only create stores in your organizations")
    
    db = get_db()
    store_dict = store_data.dict()
    store_dict['created_at'] = datetime.utcnow()
    store_dict['active'] = True
    
    # Auto-link to partner if created by partner admin or if org has a partner
    if not store_dict.get('partner_id') and store_dict.get('organization_id'):
        try:
            org = await db.organizations.find_one(
                {"_id": ObjectId(store_dict['organization_id'])}, {"partner_id": 1}
            )
            if org and org.get('partner_id'):
                store_dict['partner_id'] = org['partner_id']
        except Exception:
            pass
    
    result = await db.stores.insert_one(store_dict)
    store_id = str(result.inserted_id)
    store_dict['_id'] = store_id
    
    # Auto-create default card templates for all card types
    card_type_defaults = {
        "congrats": {"headline": "Congratulations!", "message": "Thank you for choosing us, {customer_name}! We truly appreciate your business.", "accent_color": "#C9A962"},
        "birthday": {"headline": "Happy Birthday!", "message": "Wishing you the happiest of birthdays, {customer_name}!", "accent_color": "#FF2D55"},
        "anniversary": {"headline": "Happy Anniversary!", "message": "Celebrating this special milestone with you, {customer_name}!", "accent_color": "#FF6B6B"},
        "thankyou": {"headline": "Thank You!", "message": "We truly appreciate your loyalty and trust, {customer_name}!", "accent_color": "#34C759"},
        "welcome": {"headline": "Welcome!", "message": "We're so excited to have you, {customer_name}! Welcome to the family.", "accent_color": "#007AFF"},
        "holiday": {"headline": "Happy Holidays!", "message": "Warm wishes this holiday season, {customer_name}! Thank you for being part of our family.", "accent_color": "#5AC8FA"},
    }
    templates_to_insert = []
    for ctype, defaults in card_type_defaults.items():
        templates_to_insert.append({
            "store_id": store_id,
            "card_type": ctype,
            "headline": defaults["headline"],
            "message": defaults["message"],
            "footer_text": "",
            "show_salesman": True,
            "show_store_logo": True,
            "background_color": "#1A1A1A",
            "accent_color": defaults["accent_color"],
            "text_color": "#FFFFFF",
            "created_at": datetime.utcnow(),
        })
    await db.congrats_templates.insert_many(templates_to_insert)

    # Seed store-level defaults (tags, lead sources)
    try:
        from services.seed_defaults import seed_store_defaults
        await seed_store_defaults(store_id, store_dict.get("organization_id", ""))
    except Exception as e:
        logger.error(f"Failed to seed store defaults for {store_id}: {e}")
    
    return store_dict

@router.get("/stores")
async def list_stores(
    organization_id: Optional[str] = None,
    x_user_id: str = Header(None, alias="X-User-ID")
):
    """List stores - scoped by user role"""
    db = get_db()
    user = await get_requesting_user(x_user_id)
    
    if user:
        role = user.get('role', 'user')
        
        if role == 'super_admin':
            # Super admin can filter or see all
            query = {}
            if organization_id:
                query['organization_id'] = organization_id
        elif role == 'org_admin':
            # Org admin sees stores in all their orgs (partner-aware)
            from routers.rbac import get_scoped_organization_ids
            allowed_orgs = await get_scoped_organization_ids(user)
            if organization_id and organization_id not in allowed_orgs:
                raise HTTPException(status_code=403, detail="You can only view stores in your organizations")
            if organization_id:
                query = {'organization_id': organization_id}
            else:
                query = {'organization_id': {'$in': allowed_orgs}}
        elif role == 'store_manager':
            # Store manager sees only their stores
            store_ids = await get_scoped_store_ids(user)
            query = {"_id": {"$in": [oid for oid in (safe_objectid(x) for x in store_ids) if oid is not None]}}
        else:
            # Regular users don't see stores list
            return []
    else:
        # Fallback for backward compatibility
        query = {}
        if organization_id:
            query['organization_id'] = organization_id
    
    # Exclude large binary fields from list queries
    _exclude_large = {"logo_url": 0, "email_brand_kit.logo_url": 0, "cover_image_url": 0}
    stores = await db.stores.find(query, _exclude_large).limit(500).to_list(500)
    
    # Get all organizations to map names
    org_ids = list(set([s.get('organization_id') for s in stores if s.get('organization_id')]))
    orgs_map = {}
    if org_ids:
        valid_oids = []
        for oid in org_ids:
            try:
                valid_oids.append(ObjectId(oid))
            except Exception:
                pass
        if valid_oids:
            orgs = await db.organizations.find({"_id": {"$in": valid_oids}}, {"logo_url": 0}).to_list(100)
            orgs_map = {str(o['_id']): o.get('name', 'Unknown') for o in orgs}
    
    # Count users per store
    result = []
    for store in stores:
        store_id = str(store["_id"])
        user_count = await db.users.count_documents({
            "$or": [
                {"store_ids": store_id},
                {"store_id": store_id}
            ]
        })
        result.append({
            **store,
            "_id": store_id,
            "organization_name": orgs_map.get(store.get('organization_id'), 'Unassigned'),
            "user_count": user_count
        })
    
    return result


@router.get("/stores/{store_id}")
async def get_store(store_id: str, x_user_id: str = Header(None, alias="X-User-ID")):
    """Get a specific store - with access check"""
    user = await get_requesting_user(x_user_id)
    
    if user and user.get('role') not in ['super_admin', 'org_admin']:
        has_access = await verify_store_access(user, store_id)
        if not has_access:
            raise HTTPException(status_code=403, detail="Access denied to this store")
    
    store = await get_db().stores.find_one({"_id": ObjectId(store_id)})
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    store['_id'] = str(store['_id'])
    return store

@router.put("/stores/{store_id}")
async def update_store(store_id: str, store_data: dict):
    """Update a store with all profile fields"""
    allowed_fields = [
        'name', 'organization_id', 'state', 'settings', 'phone', 'address', 'city',
        'zip_code', 'country', 'website',
        'review_links', 'logo_url', 'cover_image_url', 'primary_color',
        'business_hours', 'timezone', 'social_links', 'slug', 'active',
        'email_footer', 'industry',
        # White-label partner / sold workflow fields
        'external_account_id', 'deal_or_stock_mode', 'partner_id',
    ]
    update_dict = {k: v for k, v in store_data.items() if k in allowed_fields}
    update_dict['updated_at'] = datetime.utcnow()
    
    result = await get_db().stores.update_one(
        {"_id": ObjectId(store_id)},
        {"$set": update_dict}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Store not found")
    
    return {"message": "Store updated"}

# ============= REVIEW LINKS ENDPOINTS =============
@router.get("/stores/{store_id}/review-links")
async def get_store_review_links(store_id: str):
    """Get review links for a store"""
    store = await get_db().stores.find_one({"_id": ObjectId(store_id)})
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    
    return store.get('review_links', {
        "google": None,
        "yelp": None,
        "facebook": None,
        "dealerrater": None,
        "cars_com": None,
        "custom": []
    })

@router.put("/stores/{store_id}/review-links")
async def update_store_review_links(store_id: str, review_links: dict):
    """Update review links for a store"""
    result = await get_db().stores.update_one(
        {"_id": ObjectId(store_id)},
        {"$set": {"review_links": review_links, "updated_at": datetime.utcnow()}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Store not found")
    
    return {"message": "Review links updated", "review_links": review_links}

@router.get("/users/{user_id}/store-review-links")
async def get_user_store_review_links(user_id: str):
    """Get review links for the store the user belongs to"""
    user = await get_db().users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    store_id = user.get('store_id')
    if not store_id:
        return {
            "google": None,
            "yelp": None,
            "facebook": None,
            "dealerrater": None,
            "cars_com": None,
            "custom": []
        }
    
    store = await get_db().stores.find_one({"_id": ObjectId(store_id)})
    if not store:
        return {
            "google": None,
            "yelp": None,
            "facebook": None,
            "dealerrater": None,
            "cars_com": None,
            "custom": []
        }
    
    return store.get('review_links', {
        "google": None,
        "yelp": None,
        "facebook": None,
        "dealerrater": None,
        "cars_com": None,
        "custom": []
    })

# ============= STORE CAMPAIGN SETTINGS =============
@router.get("/stores/{store_id}/campaign-settings")
async def get_store_campaign_settings(store_id: str):
    """Get campaign permission settings for a store"""
    store = await get_db().stores.find_one({"_id": ObjectId(store_id)})
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    
    settings = store.get("settings", {})
    campaign_settings = settings.get("campaigns", {
        "managers_can_edit": True,
        "sales_can_edit": False
    })
    
    return campaign_settings


@router.put("/stores/{store_id}/campaign-settings")
async def update_store_campaign_settings(store_id: str, campaign_settings: dict):
    """Update campaign permission settings for a store"""
    allowed_fields = ['managers_can_edit', 'sales_can_edit']
    update_dict = {k: v for k, v in campaign_settings.items() if k in allowed_fields}
    
    result = await get_db().stores.update_one(
        {"_id": ObjectId(store_id)},
        {"$set": {
            "settings.campaigns": update_dict,
            "updated_at": datetime.utcnow()
        }}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Store not found")
    
    return {"message": "Campaign settings updated", "settings": update_dict}


@router.delete("/stores/{store_id}")
async def delete_store(store_id: str):
    """Delete a store"""
    result = await get_db().stores.delete_one({"_id": ObjectId(store_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Store not found")
    
    return {"message": "Store deleted"}

# ============= PLATFORM STATS =============
@router.get("/stats")
async def get_platform_stats():
    """Get platform-wide statistics"""
    total_users = await get_db().users.count_documents({})
    total_orgs = await get_db().organizations.count_documents({})
    total_stores = await get_db().stores.count_documents({})
    total_contacts = await get_db().contacts.count_documents({})
    total_campaigns = await get_db().campaigns.count_documents({})
    total_messages = await get_db().messages.count_documents({})
    pending_users = await get_db().users.count_documents({"status": "pending"})
    
    return {
        "total_users": total_users,
        "total_organizations": total_orgs,
        "total_stores": total_stores,
        "total_contacts": total_contacts,
        "total_campaigns": total_campaigns,
        "total_messages": total_messages,
        "pending_users": pending_users
    }


@router.get("/stats/detailed")
async def get_detailed_stats():
    """Get detailed statistics with active/inactive counts for admin dashboard tiles"""
    db = get_db()
    
    # Organizations counts
    orgs_active = await db.organizations.count_documents({"active": {"$ne": False}})
    orgs_inactive = await db.organizations.count_documents({"active": False})
    
    # Stores counts
    stores_active = await db.stores.count_documents({"active": {"$ne": False}})
    stores_inactive = await db.stores.count_documents({"active": False})
    
    # Users counts (users with organization)
    users_active = await db.users.count_documents({
        "is_active": {"$ne": False},
        "organization_id": {"$exists": True, "$ne": None}
    })
    users_inactive = await db.users.count_documents({
        "is_active": False,
        "organization_id": {"$exists": True, "$ne": None}
    })
    
    # Individuals counts (sole proprietors - no organization)
    individuals_active = await db.users.count_documents({
        "is_active": {"$ne": False},
        "$or": [
            {"organization_id": {"$exists": False}},
            {"organization_id": None},
            {"is_individual": True}
        ]
    })
    individuals_inactive = await db.users.count_documents({
        "is_active": False,
        "$or": [
            {"organization_id": {"$exists": False}},
            {"organization_id": None},
            {"is_individual": True}
        ]
    })
    
    # Partner agreements count
    partner_agreements = await db.partner_agreements.count_documents({})
    
    # Total employees (all active users)
    total_employees = await db.users.count_documents({"is_active": {"$ne": False}})
    
    return {
        "orgs_active": orgs_active,
        "orgs_inactive": orgs_inactive,
        "stores_active": stores_active,
        "stores_inactive": stores_inactive,
        "users_active": users_active,
        "users_inactive": users_inactive,
        "individuals_active": individuals_active,
        "individuals_inactive": individuals_inactive,
        "partner_agreements": partner_agreements,
        "total_employees": total_employees,
    }


@router.get("/stats/data")
async def get_data_stats(
    time_range: Optional[str] = None,
    organization_id: Optional[str] = None
):
    """
    Get running totals for the Data section of admin dashboard.
    
    time_range options:
    - "7d" = Last 7 days
    - "30d" = Last 30 days
    - "90d" = Last 90 days
    - None or "all" = All time
    
    organization_id: If provided, filters data to only that organization's users
    """
    from datetime import timedelta
    
    db = get_db()
    
    # Calculate date filter based on time_range
    date_filter = {}
    if time_range and time_range != "all":
        days_map = {"7d": 7, "30d": 30, "90d": 90}
        days = days_map.get(time_range, 0)
        if days > 0:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            date_filter = {"created_at": {"$gte": cutoff_date}}
    
    # Get user IDs for organization scope if provided
    org_user_ids = None
    if organization_id:
        org_users = await db.users.find(
            {"organization_id": organization_id},
            {"_id": 1}
        ).to_list(10000)
        org_user_ids = [str(u["_id"]) for u in org_users]
    
    # Helper to add org filter to queries
    def add_org_filter(query, user_field="user_id"):
        if org_user_ids is not None:
            query[user_field] = {"$in": org_user_ids}
        return query
    
    # Total messages (sent & received)
    msg_query = add_org_filter({**date_filter} if date_filter else {})
    total_messages = await db.messages.count_documents(msg_query)
    
    # Total calls
    call_query = add_org_filter({**date_filter} if date_filter else {})
    total_calls = await db.calls.count_documents(call_query)
    
    # AI-sent messages (MVP messages)
    ai_query = {
        "$or": [
            {"is_ai_generated": True},
            {"sender_type": "ai"},
            {"ai_generated": True}
        ]
    }
    if date_filter:
        ai_query = {"$and": [ai_query, date_filter]}
    ai_query = add_org_filter(ai_query)
    ai_messages = await db.messages.count_documents(ai_query)
    
    # Total contacts
    contact_query = add_org_filter({**date_filter} if date_filter else {}, "owner_id")
    total_contacts = await db.contacts.count_documents(contact_query)
    
    # Campaigns initiated
    campaign_query = add_org_filter({**date_filter} if date_filter else {}, "created_by")
    total_campaigns = await db.campaigns.count_documents(campaign_query)
    
    # Card shares (track when cards are shared/saved)
    collections = await db.list_collection_names()
    card_query = add_org_filter({**date_filter} if date_filter else {})
    card_shares = await db.card_shares.count_documents(card_query) if "card_shares" in collections else 0
    
    # Congrats Cards
    congrats_query = add_org_filter({**date_filter} if date_filter else {})
    congrats_cards = await db.congrats_cards.count_documents(congrats_query) if "congrats_cards" in collections else 0
    
    # Referrals
    referral_query = add_org_filter({**date_filter} if date_filter else {})
    total_referrals = await db.referrals.count_documents(referral_query) if "referrals" in collections else 0
    
    # Template-based message counts - using template_type field
    # Review templates sent
    review_query = {**({**date_filter} if date_filter else {})}
    review_query["template_type"] = "review"
    review_query = add_org_filter(review_query)
    review_templates_sent = await db.messages.count_documents(review_query)
    
    # Referral templates sent
    referral_template_query = {**({**date_filter} if date_filter else {})}
    referral_template_query["template_type"] = "referral"
    referral_template_query = add_org_filter(referral_template_query)
    referral_templates_sent = await db.messages.count_documents(referral_template_query)
    
    # Sold templates sent
    sold_query = {**({**date_filter} if date_filter else {})}
    sold_query["template_type"] = "sold"
    sold_query = add_org_filter(sold_query)
    sold_templates_sent = await db.messages.count_documents(sold_query)
    
    return {
        "total_messages": total_messages,
        "total_calls": total_calls,
        "ai_messages": ai_messages,
        "total_contacts": total_contacts,
        "total_campaigns": total_campaigns,
        "card_shares": card_shares,
        "congrats_cards": congrats_cards,
        "total_referrals": total_referrals,
        "review_templates_sent": review_templates_sent,
        "referral_templates_sent": referral_templates_sent,
        "sold_templates_sent": sold_templates_sent,
        "time_range": time_range or "all",
        "organization_id": organization_id
    }


@router.get("/congrats-cards")
async def get_congrats_cards(
    organization_id: Optional[str] = None,
    limit: int = 100
):
    """
    Get all congrats cards for admin data view.
    """
    db = get_db()
    
    # Build query
    query = {}
    if organization_id:
        # Get user IDs for this organization
        org_users = await db.users.find(
            {"organization_id": organization_id},
            {"_id": 1}
        ).to_list(10000)
        user_ids = [str(u["_id"]) for u in org_users]
        query["salesman_id"] = {"$in": user_ids}
    
    # Get congrats cards
    cards = await db.congrats_cards.find(query).sort("created_at", -1).limit(limit).to_list(limit)
    
    # Get user and store info for display
    user_ids = list(set([c.get("salesman_id") for c in cards if c.get("salesman_id")]))
    store_ids = list(set([c.get("store_id") for c in cards if c.get("store_id")]))
    
    users = {}
    stores = {}
    
    if user_ids:
        user_docs = await db.users.find({"_id": {"$in": [ObjectId(uid) for uid in user_ids if uid]}}, {"_id": 1, "name": 1}).limit(500).to_list(500)
        users = {str(u["_id"]): u.get("name", "Unknown") for u in user_docs}
    
    if store_ids:
        store_docs = await db.stores.find({"_id": {"$in": [ObjectId(sid) for sid in store_ids if sid]}}, {"_id": 1, "name": 1}).limit(500).to_list(500)
        stores = {str(s["_id"]): s.get("name", "Unknown") for s in store_docs}
    
    # Format response
    result = []
    for card in cards:
        result.append({
            "_id": str(card["_id"]),
            "customer_name": card.get("customer_name", "Unknown"),
            "customer_photo_url": card.get("customer_photo_url"),
            "salesman_id": card.get("salesman_id"),
            "salesman_name": users.get(card.get("salesman_id"), "Unknown"),
            "store_id": card.get("store_id"),
            "store_name": stores.get(card.get("store_id"), ""),
            "custom_message": card.get("custom_message"),
            "card_url": card.get("card_url"),
            "created_at": card.get("created_at", "").isoformat() if card.get("created_at") else None,
            "view_count": card.get("view_count", 0),
            "share_count": card.get("share_count", 0),
        })
    
    return result


@router.get("/activity/recent")
async def get_recent_activity(
    limit: int = 20,
    organization_id: Optional[str] = None
):
    """
    Get recent activity for the admin ticker.
    Returns a mix of recent messages, calls, template sends, etc.
    """
    from datetime import timedelta
    
    db = get_db()
    activities = []
    
    # Get user IDs for organization scope if provided
    org_user_ids = None
    user_map = {}
    
    if organization_id:
        org_users = await db.users.find(
            {"organization_id": organization_id},
            {"_id": 1, "name": 1}
        ).to_list(10000)
        org_user_ids = [str(u["_id"]) for u in org_users]
        user_map = {str(u["_id"]): u.get("name", "User") for u in org_users}
    else:
        # Get all users for name mapping
        all_users = await db.users.find({}, {"_id": 1, "name": 1}).to_list(10000)
        user_map = {str(u["_id"]): u.get("name", "User") for u in all_users}
    
    # Get recent messages with templates
    msg_query = {"template_type": {"$exists": True, "$ne": None}}
    if org_user_ids:
        msg_query["user_id"] = {"$in": org_user_ids}
    
    recent_template_msgs = await db.messages.find(msg_query).sort("timestamp", -1).limit(limit).to_list(limit)
    
    for msg in recent_template_msgs:
        user_name = user_map.get(msg.get("user_id"), "Someone")
        template_type = msg.get("template_type", "message")
        template_name = msg.get("template_name", template_type.title())
        
        # Get contact name if available
        contact_name = "a customer"
        if msg.get("conversation_id"):
            conv = await db.conversations.find_one({"_id": ObjectId(msg["conversation_id"])})
            if conv and conv.get("contact_id"):
                try:
                    contact = await db.contacts.find_one({"_id": ObjectId(conv["contact_id"])})
                    if contact:
                        contact_name = f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip() or "a customer"
                except:
                    pass
        
        activities.append({
            "type": "template_send",
            "template_type": template_type,
            "user_name": user_name,
            "contact_name": contact_name,
            "template_name": template_name,
            "timestamp": msg.get("timestamp"),
            "icon": get_template_icon(template_type),
            "color": get_template_color(template_type),
            "text": f"{user_name} sent {template_name} to {contact_name}"
        })
    
    # Get recent calls
    call_query = {}
    if org_user_ids:
        call_query["user_id"] = {"$in": org_user_ids}
    
    recent_calls = await db.calls.find(call_query).sort("timestamp", -1).limit(5).to_list(5)
    
    for call in recent_calls:
        user_name = user_map.get(call.get("user_id"), "Someone")
        call_type = call.get("type", "call")
        duration = call.get("duration", 0)
        
        contact_name = "a customer"
        if call.get("contact_id"):
            try:
                contact = await db.contacts.find_one({"_id": ObjectId(call["contact_id"])})
                if contact:
                    contact_name = f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip() or "a customer"
            except:
                pass
        
        action = "called" if call_type == "outbound" else "received call from"
        duration_text = f" ({duration}s)" if duration > 0 else ""
        
        activities.append({
            "type": "call",
            "call_type": call_type,
            "user_name": user_name,
            "contact_name": contact_name,
            "timestamp": call.get("timestamp"),
            "icon": "call",
            "color": "#34C759",
            "text": f"{user_name} {action} {contact_name}{duration_text}"
        })
    
    # Get recent regular messages (non-template)
    reg_msg_query = {"sender": "user", "template_type": {"$exists": False}}
    if org_user_ids:
        reg_msg_query["user_id"] = {"$in": org_user_ids}
    
    recent_msgs = await db.messages.find(reg_msg_query).sort("timestamp", -1).limit(5).to_list(5)
    
    for msg in recent_msgs:
        user_name = user_map.get(msg.get("user_id"), "Someone")
        
        contact_name = "a customer"
        if msg.get("conversation_id"):
            conv = await db.conversations.find_one({"_id": ObjectId(msg["conversation_id"])})
            if conv and conv.get("contact_id"):
                try:
                    contact = await db.contacts.find_one({"_id": ObjectId(conv["contact_id"])})
                    if contact:
                        contact_name = f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip() or "a customer"
                except:
                    pass
        
        activities.append({
            "type": "message",
            "user_name": user_name,
            "contact_name": contact_name,
            "timestamp": msg.get("timestamp"),
            "icon": "chatbubble",
            "color": "#007AFF",
            "text": f"{user_name} messaged {contact_name}"
        })
    
    # Sort all activities by timestamp
    activities.sort(key=lambda x: x.get("timestamp") or datetime.min, reverse=True)
    
    # Limit to requested amount
    return activities[:limit]


def get_template_icon(template_type: str) -> str:
    """Get icon name for template type"""
    icons = {
        "review": "star",
        "referral": "share",
        "sold": "checkmark-circle",
        "greeting": "hand-right",
        "follow_up": "refresh",
        "appointment": "calendar",
        "thank_you": "heart",
    }
    return icons.get(template_type, "document-text")


def get_template_color(template_type: str) -> str:
    """Get color for template type"""
    colors = {
        "review": "#FFD60A",
        "referral": "#5856D6",
        "sold": "#34C759",
        "greeting": "#FF9500",
        "follow_up": "#007AFF",
        "appointment": "#AF52DE",
        "thank_you": "#FF2D55",
    }
    return colors.get(template_type, "#8E8E93")


@router.get("/individuals")
async def get_individuals():
    """
    Get all individual/sole proprietor users (users without an organization).
    These are users who signed up as individuals, not part of any organization.
    """
    db = get_db()
    
    # Find users without organization_id or with is_individual flag
    individuals = await db.users.find(
        {
            "$or": [
                {"organization_id": {"$exists": False}},
                {"organization_id": None},
                {"is_individual": True}
            ]
        },
        {"password": 0}  # Exclude password
    ).sort("created_at", -1).limit(500).to_list(500)
    
    return [{
        "_id": str(u["_id"]),
        "name": u.get("name", ""),
        "email": u.get("email", ""),
        "phone": u.get("phone", ""),
        "title": u.get("title", ""),
        "is_active": u.get("is_active", True),
        "created_at": u.get("created_at"),
        "last_login": u.get("last_login"),
        "subscription_status": u.get("subscription_status", ""),
        "photo_url": u.get("photo_url", ""),
    } for u in individuals]


@router.post("/individuals")
async def create_individual(
    individual_data: dict,
    x_user_id: str = Header(None, alias="X-User-ID")
):
    """
    Create an individual user (sole proprietor, not part of an organization).
    """
    db = get_db()
    
    # Validate required fields
    if not individual_data.get('email'):
        raise HTTPException(status_code=400, detail="Email is required")
    if not individual_data.get('name'):
        raise HTTPException(status_code=400, detail="Name is required")
    
    # Check if email already exists
    existing = await db.users.find_one({"email": individual_data['email']})
    if existing:
        raise HTTPException(status_code=400, detail="Email already exists")
    
    # Create individual user
    password = individual_data.get('password', 'Individual123!')
    
    new_individual = {
        "email": individual_data['email'],
        "name": individual_data['name'],
        "phone": individual_data.get('phone', ''),
        "title": individual_data.get('title', ''),
        "password": hash_password(password),
        "role": "user",
        "is_individual": True,
        "is_active": True,
        "organization_id": None,
        "store_id": None,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    result = await db.users.insert_one(new_individual)
    new_individual['_id'] = str(result.inserted_id)
    del new_individual['password']
    
    return new_individual


# ============= BILLING & REVENUE ENDPOINTS =============
@router.get("/billing/summary")
async def get_billing_summary(
    time_range: Optional[str] = None,
    organization_id: Optional[str] = None
):
    """
    Get billing summary with revenue, commissions, and profit metrics.
    """
    from datetime import timedelta
    
    db = get_db()
    
    # Calculate date filter
    date_filter = {}
    if time_range and time_range != "all":
        days_map = {"7d": 7, "30d": 30, "90d": 90, "12m": 365}
        days = days_map.get(time_range, 30)
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        date_filter = {"created_at": {"$gte": cutoff_date}}
    
    # Build query for payments
    payment_query = {"payment_status": "paid"}
    if date_filter:
        payment_query.update(date_filter)
    
    # Get user IDs for organization scope
    if organization_id:
        org_users = await db.users.find(
            {"organization_id": organization_id},
            {"_id": 1}
        ).to_list(10000)
        org_user_ids = [str(u["_id"]) for u in org_users]
        payment_query["user_id"] = {"$in": org_user_ids}
    
    # Fetch all paid transactions
    transactions = await db.payment_transactions.find(payment_query).to_list(10000)
    
    # Calculate totals
    total_revenue = sum(t.get("amount", 0) for t in transactions)
    transaction_count = len(transactions)
    
    # Calculate by plan type
    plan_breakdown = {}
    for t in transactions:
        plan = t.get("plan_id", "unknown")
        if plan not in plan_breakdown:
            plan_breakdown[plan] = {"count": 0, "revenue": 0}
        plan_breakdown[plan]["count"] += 1
        plan_breakdown[plan]["revenue"] += t.get("amount", 0)
    
    # Monthly revenue breakdown (last 12 months)
    monthly_revenue = []
    for i in range(11, -1, -1):
        month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        month_start = month_start - timedelta(days=i*30)
        month_end = month_start + timedelta(days=30)
        
        month_total = sum(
            t.get("amount", 0) for t in transactions
            if t.get("created_at") and month_start <= t["created_at"] < month_end
        )
        
        monthly_revenue.append({
            "month": month_start.strftime("%b"),
            "revenue": month_total
        })
    
    # Commission calculations (25% default)
    commission_rate = 0.25
    total_commissions = total_revenue * commission_rate
    net_revenue = total_revenue - total_commissions
    
    # Bonus pool (10% of net)
    bonus_pool_rate = 0.10
    bonus_pool = net_revenue * bonus_pool_rate
    company_retained = net_revenue - bonus_pool
    
    return {
        "total_revenue": total_revenue,
        "transaction_count": transaction_count,
        "total_commissions": total_commissions,
        "net_revenue": net_revenue,
        "bonus_pool": bonus_pool,
        "company_retained": company_retained,
        "commission_rate": commission_rate,
        "bonus_pool_rate": bonus_pool_rate,
        "plan_breakdown": plan_breakdown,
        "monthly_revenue": monthly_revenue,
        "time_range": time_range or "all"
    }


@router.get("/billing/transactions")
async def get_billing_transactions(
    limit: int = 50,
    skip: int = 0,
    organization_id: Optional[str] = None
):
    """
    Get recent payment transactions.
    """
    db = get_db()
    
    # Build query
    query = {"payment_status": "paid"}
    
    # Organization scope
    if organization_id:
        org_users = await db.users.find(
            {"organization_id": organization_id},
            {"_id": 1}
        ).to_list(10000)
        org_user_ids = [str(u["_id"]) for u in org_users]
        query["user_id"] = {"$in": org_user_ids}
    
    # Get transactions with pagination
    transactions = await db.payment_transactions.find(query)\
        .sort("created_at", -1)\
        .skip(skip)\
        .limit(limit)\
        .to_list(limit)
    
    # Get user details for each transaction
    result = []
    for t in transactions:
        user = None
        if t.get("user_id"):
            user = await db.users.find_one(
                {"_id": ObjectId(t["user_id"])},
                {"name": 1, "email": 1}
            )
        
        result.append({
            "_id": str(t["_id"]),
            "amount": t.get("amount", 0),
            "plan_id": t.get("plan_id", ""),
            "plan_type": t.get("plan_type", ""),
            "payment_status": t.get("payment_status", ""),
            "created_at": t.get("created_at"),
            "user_id": t.get("user_id"),
            "user_name": user.get("name", "Unknown") if user else "Unknown",
            "user_email": user.get("email", "") if user else "",
            "session_id": t.get("session_id", ""),
        })
    
    # Get total count
    total_count = await db.payment_transactions.count_documents(query)
    
    return {
        "transactions": result,
        "total": total_count,
        "limit": limit,
        "skip": skip
    }


@router.get("/billing/mrr")
async def get_mrr_metrics():
    """
    Get Monthly Recurring Revenue metrics.
    """
    db = get_db()
    
    # Get active subscriptions
    active_users = await db.users.find({
        "is_active": True,
        "subscription_status": {"$in": ["active", "trialing"]}
    }).to_list(10000)
    
    # Calculate MRR based on subscription types
    mrr = 0
    subscriber_count = 0
    plan_counts = {"monthly": 0, "annual": 0, "intro": 0}
    
    for user in active_users:
        plan = user.get("subscription_plan", "monthly")
        
        if plan == "monthly":
            mrr += 100
            plan_counts["monthly"] += 1
        elif plan == "annual":
            mrr += 1000 / 12  # Monthly portion of annual
            plan_counts["annual"] += 1
        elif plan == "intro":
            mrr += 50  # Intro rate
            plan_counts["intro"] += 1
        else:
            mrr += 100  # Default to monthly
            
        subscriber_count += 1
    
    # Calculate ARR
    arr = mrr * 12
    
    # Average revenue per user
    arpu = mrr / subscriber_count if subscriber_count > 0 else 0
    
    return {
        "mrr": mrr,
        "arr": arr,
        "subscriber_count": subscriber_count,
        "arpu": arpu,
        "plan_counts": plan_counts
    }


# ============= PHONE NUMBER ASSIGNMENT ENDPOINTS =============
@router.get("/phone-assignments/users")
async def get_users_for_phone_assignment():
    """Get all users with their phone assignment status"""
    users = await get_db().users.find(
        {},
        {"password": 0}  # Exclude password
    ).sort("name", 1).limit(500).to_list(500)
    
    return [{
        "_id": str(u["_id"]),
        "name": u.get("name", "Unknown"),
        "email": u.get("email", ""),
        "phone": u.get("phone", ""),
        "mvpline_number": u.get("mvpline_number"),
        "role": u.get("role", "user"),
        "store_id": u.get("store_id"),
        "organization_id": u.get("organization_id")
    } for u in users]


@router.put("/phone-assignments/users/{user_id}")
async def update_user_phone_assignment(user_id: str, data: dict):
    """Assign or update a user's i'M On Social phone number"""
    mvpline_number = data.get("mvpline_number")
    
    # If assigning a number, check it's not already assigned
    if mvpline_number:
        # Normalize the phone number
        mvpline_number = normalize_phone_number(mvpline_number)
        
        # Check if this number is already assigned to another user
        existing = await get_db().users.find_one({
            "mvpline_number": mvpline_number,
            "_id": {"$ne": ObjectId(user_id)}
        })
        
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"This phone number is already assigned to {existing.get('name', 'another user')}"
            )
        
        # Check if this number is assigned to a shared inbox
        shared_inbox = await get_db().shared_inboxes.find_one({
            "phone_number": mvpline_number
        })
        
        if shared_inbox:
            raise HTTPException(
                status_code=400,
                detail=f"This phone number is assigned to shared inbox: {shared_inbox.get('name')}"
            )
    
    result = await get_db().users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"mvpline_number": mvpline_number, "updated_at": datetime.utcnow()}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    
    logger.info(f"Updated user {user_id} mvpline_number to {mvpline_number}")
    return {"message": "Phone number updated", "mvpline_number": mvpline_number}


@router.get("/phone-assignments/summary")
async def get_phone_assignments_summary():
    """Get a summary of all phone number assignments"""
    # Get users with phone numbers
    users_with_phones = await get_db().users.find(
        {"mvpline_number": {"$exists": True, "$nin": [None, ""]}},
        {"name": 1, "email": 1, "mvpline_number": 1}
    ).limit(500).to_list(500)
    
    # Get shared inboxes with phone numbers
    shared_inboxes = await get_db().shared_inboxes.find(
        {"phone_number": {"$exists": True, "$nin": [None, ""]}},
        {"name": 1, "phone_number": 1, "assigned_users": 1}
    ).limit(500).to_list(500)
    
    # Get stores with phone numbers
    stores = await get_db().stores.find(
        {"twilio_phone_number": {"$exists": True, "$nin": [None, ""]}},
        {"name": 1, "twilio_phone_number": 1}
    ).limit(500).to_list(500)
    
    return {
        "users": [{
            "_id": str(u["_id"]),
            "name": u.get("name"),
            "email": u.get("email"),
            "phone_number": u.get("mvpline_number"),
            "type": "personal"
        } for u in users_with_phones],
        "shared_inboxes": [{
            "_id": str(i["_id"]),
            "name": i.get("name"),
            "phone_number": i.get("phone_number"),
            "assigned_users_count": len(i.get("assigned_users", [])),
            "type": "shared"
        } for i in shared_inboxes],
        "stores": [{
            "_id": str(s["_id"]),
            "name": s.get("name"),
            "phone_number": s.get("twilio_phone_number"),
            "type": "store"
        } for s in stores],
        "totals": {
            "users": len(users_with_phones),
            "shared_inboxes": len(shared_inboxes),
            "stores": len(stores),
            "total": len(users_with_phones) + len(shared_inboxes) + len(stores)
        }
    }


def normalize_phone_number(phone: str) -> str:
    """Normalize phone number to E.164 format"""
    if not phone:
        return None
    
    # Remove all non-digit characters except +
    cleaned = ''.join(c for c in phone if c.isdigit() or c == '+')
    
    # Add + if not present
    if not cleaned.startswith('+'):
        # Assume US number if 10 digits
        if len(cleaned) == 10:
            cleaned = '+1' + cleaned
        elif len(cleaned) == 11 and cleaned.startswith('1'):
            cleaned = '+' + cleaned
        else:
            cleaned = '+' + cleaned
    
    return cleaned


# Hierarchy endpoints moved to admin_hierarchy.py

@router.get("/data/messages")
async def get_data_messages(
    x_user_id: str = Header(None, alias="X-User-ID"),
    limit: int = 100
):
    """Get messages data for admin dashboard"""
    db = get_db()
    user = await get_requesting_user(x_user_id)
    
    query = {}
    if user and user.get('role') not in ['super_admin', 'org_admin']:
        store_ids = await get_scoped_store_ids(user)
        if store_ids:
            query['store_id'] = {'$in': store_ids}
    
    messages = await db.messages.find(query).sort('created_at', -1).limit(limit).to_list(limit)
    
    # Get user names
    user_ids = list(set(m.get('user_id') for m in messages if m.get('user_id')))
    users = {}
    if user_ids:
        user_docs = await db.users.find({'_id': {'$in': [ObjectId(uid) for uid in user_ids]}}).to_list(100)
        users = {str(u['_id']): u.get('name') for u in user_docs}
    
    result = []
    for m in messages:
        result.append({
            '_id': str(m['_id']),
            'contact_name': m.get('contact_name'),
            'contact_phone': m.get('contact_phone'),
            'user_name': users.get(m.get('user_id')),
            'content': m.get('content') or m.get('body') or '',
            'direction': m.get('direction', 'outbound'),
            'created_at': m.get('created_at', datetime.utcnow()).isoformat(),
            'status': m.get('status')
        })
    
    return result


@router.get("/data/calls")
async def get_data_calls(
    x_user_id: str = Header(None, alias="X-User-ID"),
    limit: int = 100
):
    """Get calls data for admin dashboard"""
    db = get_db()
    user = await get_requesting_user(x_user_id)
    
    query = {}
    if user and user.get('role') not in ['super_admin', 'org_admin']:
        store_ids = await get_scoped_store_ids(user)
        if store_ids:
            query['store_id'] = {'$in': store_ids}
    
    calls = await db.calls.find(query).sort('created_at', -1).limit(limit).to_list(limit)
    
    user_ids = list(set(c.get('user_id') for c in calls if c.get('user_id')))
    users = {}
    if user_ids:
        user_docs = await db.users.find({'_id': {'$in': [ObjectId(uid) for uid in user_ids]}}).to_list(100)
        users = {str(u['_id']): u.get('name') for u in user_docs}
    
    result = []
    for c in calls:
        result.append({
            '_id': str(c['_id']),
            'contact_name': c.get('contact_name'),
            'contact_phone': c.get('contact_phone') or c.get('from_number') or c.get('to_number'),
            'user_name': users.get(c.get('user_id')),
            'direction': c.get('direction', 'outbound'),
            'duration': c.get('duration', 0),
            'status': c.get('status', 'completed'),
            'created_at': c.get('created_at', datetime.utcnow()).isoformat()
        })
    
    return result


@router.get("/data/ai-messages")
async def get_data_ai_messages(
    x_user_id: str = Header(None, alias="X-User-ID"),
    limit: int = 100
):
    """Get AI messages/interactions data"""
    db = get_db()
    
    ai_messages = await db.ai_messages.find({}).sort('created_at', -1).limit(limit).to_list(limit)
    
    result = []
    for m in ai_messages:
        result.append({
            '_id': str(m['_id']),
            'contact_name': m.get('contact_name'),
            'user_name': m.get('user_name'),
            'prompt': m.get('prompt'),
            'response': m.get('response'),
            'ai_type': m.get('ai_type') or m.get('type'),
            'created_at': m.get('created_at', datetime.utcnow()).isoformat()
        })
    
    return result


@router.get("/data/card-shares")
async def get_data_card_shares(
    x_user_id: str = Header(None, alias="X-User-ID"),
    limit: int = 100
):
    """Get digital card share data"""
    db = get_db()
    
    shares = await db.card_shares.find({}).sort('created_at', -1).limit(limit).to_list(limit)
    
    user_ids = list(set(s.get('user_id') for s in shares if s.get('user_id')))
    users = {}
    if user_ids:
        user_docs = await db.users.find({'_id': {'$in': [ObjectId(uid) for uid in user_ids]}}).to_list(100)
        users = {str(u['_id']): u.get('name') for u in user_docs}
    
    result = []
    for s in shares:
        result.append({
            '_id': str(s['_id']),
            'user_name': users.get(s.get('user_id')),
            'contact_name': s.get('contact_name'),
            'share_type': s.get('share_type') or s.get('method'),
            'view_count': s.get('view_count', 0),
            'created_at': s.get('created_at', datetime.utcnow()).isoformat()
        })
    
    return result


@router.get("/data/referrals")
async def get_data_referrals(
    x_user_id: str = Header(None, alias="X-User-ID"),
    limit: int = 100
):
    """Get referrals data"""
    db = get_db()
    
    referrals = await db.referrals.find({}).sort('created_at', -1).limit(limit).to_list(limit)
    
    result = []
    for r in referrals:
        result.append({
            '_id': str(r['_id']),
            'referrer_name': r.get('referrer_name'),
            'referee_name': r.get('referee_name'),
            'referee_phone': r.get('referee_phone'),
            'status': r.get('status', 'pending'),
            'store_name': r.get('store_name'),
            'created_at': r.get('created_at', datetime.utcnow()).isoformat()
        })
    
    return result


@router.get("/data/campaigns")
async def get_data_campaigns(
    x_user_id: str = Header(None, alias="X-User-ID"),
    limit: int = 100
):
    """Get campaigns data"""
    db = get_db()
    
    campaigns = await db.campaigns.find({}).sort('created_at', -1).limit(limit).to_list(limit)
    
    result = []
    for c in campaigns:
        result.append({
            '_id': str(c['_id']),
            'name': c.get('name', 'Untitled Campaign'),
            'type': c.get('type'),
            'status': c.get('status', 'draft'),
            'sent_count': c.get('sent_count', 0),
            'open_count': c.get('open_count', 0),
            'click_count': c.get('click_count', 0),
            'store_name': c.get('store_name'),
            'created_at': c.get('created_at', datetime.utcnow()).isoformat()
        })
    
    return result


@router.get("/data/review-templates")
async def get_data_review_templates(
    x_user_id: str = Header(None, alias="X-User-ID"),
    limit: int = 100
):
    """Get review templates sent data"""
    db = get_db()
    
    templates = await db.template_sends.find({'template_type': 'review'}).sort('created_at', -1).limit(limit).to_list(limit)
    
    result = []
    for t in templates:
        result.append({
            '_id': str(t['_id']),
            'template_name': t.get('template_name'),
            'user_name': t.get('user_name'),
            'contact_name': t.get('contact_name'),
            'contact_phone': t.get('contact_phone'),
            'status': t.get('status', 'sent'),
            'created_at': t.get('created_at', datetime.utcnow()).isoformat()
        })
    
    return result


@router.get("/data/referral-templates")
async def get_data_referral_templates(
    x_user_id: str = Header(None, alias="X-User-ID"),
    limit: int = 100
):
    """Get referral templates sent data"""
    db = get_db()
    
    templates = await db.template_sends.find({'template_type': 'referral'}).sort('created_at', -1).limit(limit).to_list(limit)
    
    result = []
    for t in templates:
        result.append({
            '_id': str(t['_id']),
            'template_name': t.get('template_name'),
            'user_name': t.get('user_name'),
            'contact_name': t.get('contact_name'),
            'contact_phone': t.get('contact_phone'),
            'status': t.get('status', 'sent'),
            'created_at': t.get('created_at', datetime.utcnow()).isoformat()
        })
    
    return result


@router.get("/data/sold-templates")
async def get_data_sold_templates(
    x_user_id: str = Header(None, alias="X-User-ID"),
    limit: int = 100
):
    """Get sold/congrats templates sent data"""
    db = get_db()
    
    templates = await db.template_sends.find({'template_type': {'$in': ['sold', 'congrats']}}).sort('created_at', -1).limit(limit).to_list(limit)
    
    result = []
    for t in templates:
        result.append({
            '_id': str(t['_id']),
            'template_name': t.get('template_name'),
            'user_name': t.get('user_name'),
            'contact_name': t.get('contact_name'),
            'contact_phone': t.get('contact_phone'),
            'status': t.get('status', 'sent'),
            'created_at': t.get('created_at', datetime.utcnow()).isoformat()
        })
    
    return result


@router.get("/contacts")
async def get_admin_contacts(
    x_user_id: str = Header(None, alias="X-User-ID"),
    limit: int = 500
):
    """Get all contacts for admin view"""
    db = get_db()
    user = await get_requesting_user(x_user_id)
    
    query = {}
    if user and user.get('role') not in ['super_admin', 'org_admin']:
        store_ids = await get_scoped_store_ids(user)
        if store_ids:
            query['store_id'] = {'$in': store_ids}
    
    contacts = await db.contacts.find(query).sort('created_at', -1).limit(limit).to_list(limit)
    
    # Get user and store names - filter out invalid ObjectIds
    user_ids = [uid for uid in set(c.get('assigned_to') or c.get('user_id') for c in contacts if c.get('assigned_to') or c.get('user_id')) if uid and len(str(uid)) == 24]
    store_ids = [sid for sid in set(c.get('store_id') for c in contacts if c.get('store_id')) if sid and len(str(sid)) == 24]
    
    users = {}
    stores = {}
    
    if user_ids:
        try:
            user_docs = await db.users.find({'_id': {'$in': [ObjectId(uid) for uid in user_ids]}}).to_list(100)
            users = {str(u['_id']): u.get('name') for u in user_docs}
        except:
            pass
    
    if store_ids:
        try:
            store_docs = await db.stores.find({'_id': {'$in': [ObjectId(sid) for sid in store_ids]}}).to_list(100)
            stores = {str(s['_id']): s.get('name') for s in store_docs}
        except:
            pass
    
    result = []
    for c in contacts:
        created_at = c.get('created_at')
        if isinstance(created_at, str):
            created_at_str = created_at
        elif created_at:
            created_at_str = created_at.isoformat()
        else:
            created_at_str = datetime.utcnow().isoformat()
            
        result.append({
            '_id': str(c['_id']),
            'first_name': c.get('first_name'),
            'last_name': c.get('last_name'),
            'phone': c.get('phone'),
            'email': c.get('email'),
            'user_name': users.get(c.get('assigned_to') or c.get('user_id')),
            'store_name': stores.get(c.get('store_id')),
            'status': c.get('status'),
            'created_at': created_at_str
        })
    
    return result

    valid_roles = ["super_admin", "org_admin", "store_manager", "user"]
    
    if role not in valid_roles:
        raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of: {valid_roles}")
    
    result = await get_db().users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"role": role, "updated_at": datetime.utcnow()}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {"message": "User role updated", "role": role}



@router.post("/migrate-mms-media")
async def migrate_mms_media():
    """
    Migrate existing messages with Twilio media URLs to use our stored media.
    This fixes the issue where images disappear after logout/login.
    """
    import httpx
    import base64
    import os
    
    BACKEND_URL = os.environ.get("REACT_APP_BACKEND_URL", "")
    twilio_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    twilio_token = os.environ.get("TWILIO_AUTH_TOKEN")
    
    if not twilio_sid or not twilio_token:
        return {"error": "Twilio credentials not configured", "migrated": 0}
    
    # Find messages with Twilio media URLs
    messages = await get_db().messages.find({
        "has_media": True,
        "media_urls": {"$regex": "api.twilio.com"}
    }).limit(500).to_list(500)
    
    migrated_count = 0
    errors = []
    
    async with httpx.AsyncClient() as client:
        for msg in messages:
            try:
                new_media_urls = []
                new_media_ids = []
                
                for i, url in enumerate(msg.get("media_urls", [])):
                    if "api.twilio.com" not in url:
                        new_media_urls.append(url)
                        continue
                    
                    # Download from Twilio
                    media_type = msg.get("media_types", [])[i] if i < len(msg.get("media_types", [])) else "image/jpeg"
                    
                    try:
                        response = await client.get(
                            url,
                            auth=(twilio_sid, twilio_token),
                            follow_redirects=True,
                            timeout=30.0
                        )
                        
                        if response.status_code == 200:
                            media_bytes = response.content
                            base64_data = base64.b64encode(media_bytes).decode('utf-8')
                            data_url = f"data:{media_type};base64,{base64_data}"
                            
                            media_doc = {
                                "data": data_url,
                                "content_type": media_type,
                                "size": len(media_bytes),
                                "source": "migration",
                                "original_url": url,
                                "created_at": datetime.utcnow()
                            }
                            
                            result = await get_db().media.insert_one(media_doc)
                            media_id = str(result.inserted_id)
                            
                            our_url = f"{BACKEND_URL}/api/messages/media/{media_id}"
                            new_media_urls.append(our_url)
                            new_media_ids.append(media_id)
                        else:
                            new_media_urls.append(url)  # Keep original if download fails
                            
                    except Exception as e:
                        new_media_urls.append(url)
                        errors.append(f"Error downloading {url}: {str(e)}")
                
                # Update message with new URLs
                if new_media_ids:
                    await get_db().messages.update_one(
                        {"_id": msg["_id"]},
                        {"$set": {
                            "media_urls": new_media_urls,
                            "media_ids": new_media_ids,
                            "original_twilio_urls": msg.get("media_urls", [])
                        }}
                    )
                    migrated_count += 1
                    
            except Exception as e:
                errors.append(f"Error processing message {msg['_id']}: {str(e)}")
    
    return {
        "migrated": migrated_count,
        "total_found": len(messages),
        "errors": errors[:10]  # Limit errors returned
    }


# ============= TEAM MANAGEMENT FOR MANAGERS =============

# AddTeamMemberRequest moved to admin_users.py


@router.post("/backfill-onboarding")
async def backfill_onboarding(x_user_id: str = Header(alias="X-User-ID")):
    """Bulk-mark all existing active users as onboarding_complete.
    This fixes users created before the onboarding system was implemented."""
    caller = await get_user_by_id(x_user_id)
    if not caller or caller.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Super admin only")
    db = get_db()
    result = await db.users.update_many(
        {"onboarding_complete": {"$ne": True}, "status": {"$ne": "pending"}},
        {"$set": {"onboarding_complete": True, "needs_onboarding": False}}
    )
    return {"updated": result.modified_count, "message": f"Marked {result.modified_count} existing users as onboarding complete"}
