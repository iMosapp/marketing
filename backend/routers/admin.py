"""
Admin router - handles organization, store, and user management
With Role-Based Access Control (RBAC) enforcement
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

router = APIRouter(prefix="/admin", tags=["Admin"])
logger = logging.getLogger(__name__)

# Initialize Resend for invite emails
RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "noreply@imosapp.com")

APP_URL = "https://app.imosapp.com"

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
        "from": f"iMOs <{SENDER_EMAIL}>",
        "to": email,
        "subject": f"You're Invited to Join iMOs as {role_title}",
        "html": f"""
            <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f5f5f5;">
                <div style="text-align: center; margin-bottom: 20px; padding: 20px; background-color: #1A1A2E; border-radius: 16px 16px 0 0;">
                    <img src="cid:imos-logo" alt="iMOs" width="150" style="max-width: 150px; height: auto;" />
                    <p style="margin: 8px 0 0 0; font-size: 13px; color: #ffffff; letter-spacing: 1px;">Relationship Management System</p>
                </div>
                
                <div style="background: linear-gradient(135deg, #1A1A2E 0%, #16213E 100%); padding: 30px; border-radius: 16px; color: white;">
                    <h2 style="margin-top: 0; color: #C9A962;">Welcome, {name}!</h2>
                    <p style="font-size: 16px; line-height: 1.6;">You've been invited to join <strong>iMOs</strong> as a <strong style="color: #C9A962;">{role_title}</strong>{f' by {inviter_name}' if inviter_name else ''}.</p>
                    
                    <div style="background: rgba(255,255,255,0.1); padding: 20px; border-radius: 12px; margin: 25px 0;">
                        <p style="margin: 0 0 15px 0; font-weight: 600; color: #C9A962;">Your Login Credentials:</p>
                        <table style="width: 100%; border-collapse: collapse;">
                            <tr>
                                <td style="padding: 8px 0; color: rgba(255,255,255,0.7);">Email:</td>
                                <td style="padding: 8px 0;"><code style="background: rgba(0,0,0,0.3); padding: 4px 10px; border-radius: 4px; color: #fff;">{email}</code></td>
                            </tr>
                            <tr>
                                <td style="padding: 8px 0; color: rgba(255,255,255,0.7);">Temporary Password:</td>
                                <td style="padding: 8px 0;"><code style="background: rgba(0,0,0,0.3); padding: 4px 10px; border-radius: 4px; color: #fff;">{temp_password}</code></td>
                            </tr>
                        </table>
                    </div>
                    
                    <p style="font-size: 14px; color: rgba(255,255,255,0.7); margin-bottom: 25px;">You'll be prompted to create a new password when you first log in.</p>
                    
                    <div style="text-align: center;">
                        <a href="{login_url}" style="display: inline-block; background: #C9A962; color: #000; padding: 16px 40px; text-decoration: none; border-radius: 30px; font-weight: 700; font-size: 16px;">
                            Get Started
                        </a>
                    </div>
                </div>
                
                <div style="text-align: center; margin-top: 25px; color: #888; font-size: 12px;">
                    <p style="margin: 5px 0;">iMOs - Your Relationship Management System</p>
                    <p style="margin: 5px 0; color: #aaa;">Questions? Contact support@imosapp.com</p>
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
    """Create a new organization - super_admin only"""
    user = await get_requesting_user(x_user_id)
    if not user or user.get('role') != 'super_admin':
        raise HTTPException(status_code=403, detail="Only super admins can create organizations")
    
    org_dict = org_data.dict()
    org_dict['created_at'] = datetime.utcnow()
    org_dict['active'] = True
    
    result = await get_db().organizations.insert_one(org_dict)
    org_dict['_id'] = str(result.inserted_id)
    
    return org_dict


@router.get("/organizations")
async def list_organizations(x_user_id: str = Header(None, alias="X-User-ID")):
    """List organizations - scoped by user role"""
    user = await get_requesting_user(x_user_id)
    
    if not user:
        # Fallback for backward compatibility - return all (will be restricted later)
        orgs = await get_db().organizations.find().limit(500).to_list(500)
        return [{**org, "_id": str(org["_id"])} for org in orgs]
    
    role = user.get('role', 'user')
    
    if role == 'super_admin':
        # Super admin sees all organizations
        orgs = await get_db().organizations.find().limit(500).to_list(500)
    else:
        # Non-super admins see only their organization
        org_ids = await get_scoped_organization_ids(user)
        if not org_ids:
            return []
        orgs = await get_db().organizations.find({
            "_id": {"$in": [ObjectId(oid) for oid in org_ids if oid]}
        }).limit(500).to_list(500)
    
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
            if user.get('organization_id') != org_id:
                raise HTTPException(status_code=403, detail="You can only update your own organization")
        else:
            raise HTTPException(status_code=403, detail="Only admins can update organizations")
    
    allowed_fields = ['name', 'admin_email', 'admin_phone', 'city', 'state', 'active', 'settings']
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
    """Create a new store - super_admin or org_admin only"""
    user = await get_requesting_user(x_user_id)
    
    if user:
        role = user.get('role', 'user')
        if role not in ['super_admin', 'org_admin']:
            raise HTTPException(status_code=403, detail="Only admins can create stores")
        
        # Org admins can only create stores in their org
        if role == 'org_admin':
            if store_data.organization_id != user.get('organization_id'):
                raise HTTPException(status_code=403, detail="You can only create stores in your organization")
    
    db = get_db()
    store_dict = store_data.dict()
    store_dict['created_at'] = datetime.utcnow()
    store_dict['active'] = True
    
    result = await db.stores.insert_one(store_dict)
    store_id = str(result.inserted_id)
    store_dict['_id'] = store_id
    
    # Auto-create default congrats card template for the new store
    default_template = {
        "store_id": store_id,
        "headline": "Thank You!",
        "message": "Thank you for choosing us, {customer_name}! We truly appreciate your business and look forward to serving you again.",
        "footer_text": "Your satisfaction is our priority",
        "show_salesman": True,
        "show_store_logo": True,
        "background_color": "#1A1A1A",
        "accent_color": "#C9A962",
        "text_color": "#FFFFFF",
        "created_at": datetime.utcnow(),
    }
    await db.congrats_templates.insert_one(default_template)
    
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
            # Org admin sees only their org's stores
            user_org = user.get('organization_id')
            if organization_id and organization_id != user_org:
                raise HTTPException(status_code=403, detail="You can only view stores in your organization")
            query = {'organization_id': user_org}
        elif role == 'store_manager':
            # Store manager sees only their stores
            store_ids = await get_scoped_store_ids(user)
            query = {"_id": {"$in": [ObjectId(sid) for sid in store_ids if sid]}}
        else:
            # Regular users don't see stores list
            return []
    else:
        # Fallback for backward compatibility
        query = {}
        if organization_id:
            query['organization_id'] = organization_id
    
    stores = await db.stores.find(query).limit(500).to_list(500)
    
    # Get all organizations to map names
    org_ids = list(set([s.get('organization_id') for s in stores if s.get('organization_id')]))
    orgs_map = {}
    if org_ids:
        orgs = await db.organizations.find({"_id": {"$in": [ObjectId(oid) for oid in org_ids]}}).to_list(100)
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
        'review_links', 'website', 'logo_url', 'cover_image_url', 'primary_color',
        'business_hours', 'timezone', 'social_links', 'slug', 'active'
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

# ============= USER MANAGEMENT ENDPOINTS =============
@router.post("/users")
async def create_admin_user(user_data: dict, x_user_id: str = Header(None, alias="X-User-ID")):
    """Create a user with specific role - admins only"""
    requesting_user = await get_requesting_user(x_user_id)
    
    if requesting_user:
        role = requesting_user.get('role', 'user')
        if role not in ['super_admin', 'org_admin', 'store_manager']:
            raise HTTPException(status_code=403, detail="Only admins can create users")
        
        # Org admins can only create users in their org
        if role == 'org_admin':
            if user_data.get('organization_id') != requesting_user.get('organization_id'):
                raise HTTPException(status_code=403, detail="You can only create users in your organization")
        
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
        "password": user_data.get('password'),
        "name": user_data.get('name'),
        "phone": user_data.get('phone', ''),
        "role": user_data.get('role', 'user'),
        "organization_id": user_data.get('organization_id'),
        "store_id": user_data.get('store_id'),
        "state": user_data.get('state', ''),
        "created_at": datetime.utcnow(),
        "onboarding_complete": True,
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
    
    result = await get_db().users.insert_one(user_dict)
    user_dict['_id'] = str(result.inserted_id)
    del user_dict['password']
    
    return user_dict


@router.post("/users/create")
async def create_user_with_invite(data: dict, x_user_id: str = Header(None, alias="X-User-ID")):
    """Create a user and optionally send invite email - admins only"""
    import secrets
    import string
    
    requesting_user = await get_requesting_user(x_user_id)
    
    if requesting_user:
        role = requesting_user.get('role', 'user')
        if role not in ['super_admin', 'org_admin', 'store_manager']:
            raise HTTPException(status_code=403, detail="Only admins can create users")
    
    name = data.get('name', '').strip()
    email = data.get('email', '').strip().lower()
    phone = data.get('phone', '').strip()
    user_role = data.get('role', 'user')
    send_invite = data.get('send_invite', True)
    
    # Get org and store from request, or fall back to requesting user's
    organization_id = data.get('organization_id')
    store_id = data.get('store_id')
    
    # Non-super admins can only create users in their own org
    if requesting_user and requesting_user.get('role') != 'super_admin':
        if organization_id and organization_id != requesting_user.get('organization_id'):
            raise HTTPException(status_code=403, detail="You can only create users in your organization")
        organization_id = requesting_user.get('organization_id')
    
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")
    if not email or '@' not in email:
        raise HTTPException(status_code=400, detail="Valid email is required")
    
    # Check if email exists
    existing = await get_db().users.find_one({"email": email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Generate temporary password
    temp_password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))
    
    user_dict = {
        "email": email,
        "password": temp_password,
        "name": name,
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
    
    result = await get_db().users.insert_one(user_dict)
    user_id = str(result.inserted_id)
    
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
    
    return {
        "success": True,
        "user_id": user_id,
        "email": email,
        "name": name,
        "role": user_role,
        "organization_id": organization_id,
        "store_id": store_id,
        "invite_sent": invite_sent,
        "temp_password": temp_password,
        "message": f"User created successfully. {'Invite email sent.' if invite_sent else 'Share the temporary password securely.'}"
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
            # Org admin sees only their org's users
            user_org = requesting_user.get('organization_id')
            if organization_id and organization_id != user_org:
                raise HTTPException(status_code=403, detail="You can only view users in your organization")
            query = {'organization_id': user_org}
            if store_id:
                # Verify store is in their org
                store = await get_db().stores.find_one({"_id": ObjectId(store_id)})
                if not store or store.get('organization_id') != user_org:
                    raise HTTPException(status_code=403, detail="Store not in your organization")
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
    
    allowed_fields = ['name', 'phone', 'role', 'organization_id', 'store_id', 'state', 'settings', 'is_active', 'onboarding_complete']
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
    
    result = await get_db().users.delete_one({"_id": ObjectId(user_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {"message": "User deleted"}


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
    user_data = {
        "_id": str(user["_id"]),
        "email": user.get("email"),
        "name": user.get("name"),
        "role": user.get("role"),
        "store_id": user.get("store_id"),
        "store_ids": user.get("store_ids", []),
        "organization_id": user.get("organization_id"),
        "title": user.get("title"),
        "phone": user.get("phone"),
        "photo_url": user.get("photo_url"),
        "bio": user.get("bio"),
        "is_active": user.get("is_active", True),
        "twilio_phone_number": user.get("twilio_phone_number"),
        "isImpersonating": True,  # Flag to indicate this is an impersonation session
    }
    
    return {
        "success": True,
        "token": impersonation_token,
        "user": user_data,
        "message": f"Now impersonating {user.get('name', 'user')}"
    }


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
    import bcrypt
    password = individual_data.get('password', 'Individual123!')
    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    new_individual = {
        "email": individual_data['email'],
        "name": individual_data['name'],
        "phone": individual_data.get('phone', ''),
        "title": individual_data.get('title', ''),
        "password": hashed,
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
    """Assign or update a user's iMOs phone number"""
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
        {"mvpline_number": {"$exists": True, "$ne": None, "$ne": ""}},
        {"name": 1, "email": 1, "mvpline_number": 1}
    ).limit(500).to_list(500)
    
    # Get shared inboxes with phone numbers
    shared_inboxes = await get_db().shared_inboxes.find(
        {"phone_number": {"$exists": True, "$ne": None, "$ne": ""}},
        {"name": 1, "phone_number": 1, "assigned_users": 1}
    ).limit(500).to_list(500)
    
    # Get stores with phone numbers
    stores = await get_db().stores.find(
        {"twilio_phone_number": {"$exists": True, "$ne": None, "$ne": ""}},
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


# ============= HIERARCHY MANAGEMENT ENDPOINTS =============

@router.get("/hierarchy/overview")
async def get_hierarchy_overview():
    """Get complete hierarchy overview with counts"""
    # Get all organizations with store and user counts
    orgs = await get_db().organizations.find().limit(500).to_list(500)
    
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
    stores = await get_db().stores.find({"organization_id": org_id}).to_list(100)
    
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
    store_id: Optional[str] = None
):
    """Get all users with their org/store assignments"""
    query = {}
    
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
        org_docs = await get_db().organizations.find(
            {"_id": {"$in": [ObjectId(oid) for oid in org_ids if oid]}}
        ).to_list(100)
        orgs = {str(o["_id"]): o.get("name") for o in org_docs}
    
    stores = {}
    if store_ids:
        store_docs = await get_db().stores.find(
            {"_id": {"$in": [ObjectId(sid) for sid in store_ids if sid]}}
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
async def update_user_role(user_id: str, data: dict):
    """Update a user's role"""
    role = data.get("role")


# ============= DATA ENDPOINTS =============

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

from pydantic import BaseModel

class AddTeamMemberRequest(BaseModel):
    name: str
    email: str
    phone: str
    role: str = "user"
    store_id: str
    added_by: str


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
    
    result = await db.users.insert_one(new_user)
    user_id = str(result.inserted_id)
    new_user["_id"] = user_id
    
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
    base_url = os.environ.get("SHORT_URL_DOMAIN", "https://app.imosapp.com")
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
    """Upload a logo for a store/account. Stores original + avatar."""
    db = get_db()

    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    contents = await file.read()
    if len(contents) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image must be less than 5MB")

    original_b64 = f"data:{file.content_type};base64,{base64.b64encode(contents).decode('utf-8')}"
    avatar_b64 = _resize_image(contents, 128)

    result = await db.stores.update_one(
        {"_id": ObjectId(store_id)},
        {"$set": {
            "logo_url": original_b64,
            "logo_avatar_url": avatar_b64,
            "updated_at": datetime.utcnow(),
        }}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Account not found")

    return {"success": True, "logo_url": original_b64, "logo_avatar_url": avatar_b64}


@router.post("/organizations/{org_id}/upload-logo")
async def upload_org_logo(org_id: str, file: UploadFile = File(...)):
    """Upload a logo for an organization. Stores original + avatar."""
    db = get_db()

    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    contents = await file.read()
    if len(contents) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image must be less than 5MB")

    original_b64 = f"data:{file.content_type};base64,{base64.b64encode(contents).decode('utf-8')}"
    avatar_b64 = _resize_image(contents, 128)

    result = await db.organizations.update_one(
        {"_id": ObjectId(org_id)},
        {"$set": {
            "logo_url": original_b64,
            "logo_avatar_url": avatar_b64,
            "updated_at": datetime.utcnow(),
        }}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Organization not found")

    return {"success": True, "logo_url": original_b64, "logo_avatar_url": avatar_b64}
