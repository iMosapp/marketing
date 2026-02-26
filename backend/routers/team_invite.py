"""
Team Invite Router
Handles team member invitations and account creation from invite links
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime
from bson import ObjectId
import secrets
import os
import logging
import asyncio

from routers.database import get_db

router = APIRouter(prefix="/team-invite", tags=["Team Invite"])
logger = logging.getLogger(__name__)


APP_URL = os.environ.get("APP_URL", "https://app.imosapp.com")




# ============= MODELS =============

class TeamInviteCreate(BaseModel):
    store_id: str
    created_by: str  # User ID of the person who created the invite
    expires_days: int = 30


class TeamMemberJoin(BaseModel):
    invite_code: str
    name: str
    phone: str
    email: str


class EmailInviteRequest(BaseModel):
    store_id: str
    created_by: str
    recipient_email: EmailStr
    recipient_name: Optional[str] = None
    custom_message: Optional[str] = None
    expires_days: int = 7


class AcceptInviteRequest(BaseModel):
    invite_code: str
    name: str
    email: EmailStr
    password: str
    phone: Optional[str] = None


class InviteLinkResponse(BaseModel):
    invite_code: str
    invite_url: str
    store_name: str
    expires_at: datetime


# ============= HELPER FUNCTIONS =============

def generate_invite_code(length: int = 8) -> str:
    """Generate a short, URL-safe invite code"""
    chars = 'abcdefghkmnpqrstuvwxyz23456789'  # Exclude confusing chars
    return ''.join(secrets.choice(chars) for _ in range(length))


# ============= ENDPOINTS =============

@router.post("/create")
async def create_team_invite(data: TeamInviteCreate):
    """Create a new team invite link for a store"""
    db = get_db()
    
    # Verify store exists
    store = await db.stores.find_one({"_id": ObjectId(data.store_id)})
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    
    # Verify user exists
    user = await db.users.find_one({"_id": ObjectId(data.created_by)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Generate unique invite code
    invite_code = generate_invite_code()
    
    # Check for uniqueness
    existing = await db.team_invites.find_one({"invite_code": invite_code})
    while existing:
        invite_code = generate_invite_code()
        existing = await db.team_invites.find_one({"invite_code": invite_code})
    
    # Create invite record
    from datetime import timedelta
    expires_at = datetime.utcnow() + timedelta(days=data.expires_days)
    
    invite = {
        "invite_code": invite_code,
        "store_id": data.store_id,
        "organization_id": store.get("organization_id"),
        "created_by": data.created_by,
        "created_at": datetime.utcnow(),
        "expires_at": expires_at,
        "is_active": True,
        "uses_count": 0,
    }
    
    result = await db.team_invites.insert_one(invite)
    invite["_id"] = str(result.inserted_id)
    
    # Generate full URL
    import os
    base_url = APP_URL
    invite_url = f"{base_url}/imos/signup?invite={invite_code}"
    
    return {
        "invite_code": invite_code,
        "invite_url": invite_url,
        "store_name": store.get("name"),
        "expires_at": expires_at.isoformat(),
        "created_by_name": user.get("name"),
    }


@router.get("/validate/{invite_code}")
async def validate_invite(invite_code: str):
    """Validate an invite code and return store info"""
    db = get_db()
    
    invite = await db.team_invites.find_one({
        "invite_code": invite_code,
        "is_active": True
    })
    
    if not invite:
        raise HTTPException(status_code=404, detail="Invalid or expired invite code")
    
    # Check expiration
    if invite.get("expires_at") and invite["expires_at"] < datetime.utcnow():
        raise HTTPException(status_code=400, detail="This invite link has expired")
    
    # Get store info
    store = await db.stores.find_one({"_id": ObjectId(invite["store_id"])})
    if not store:
        raise HTTPException(status_code=404, detail="Store no longer exists")
    
    # Get organization info
    org = None
    if store.get("organization_id"):
        org_doc = await db.organizations.find_one({"_id": ObjectId(store["organization_id"])})
        if org_doc:
            org = {"name": org_doc.get("name")}
    
    # Get onboarding settings
    settings = await db.onboarding_settings.find_one({"store_id": invite["store_id"]})
    if not settings and store.get("organization_id"):
        settings = await db.onboarding_settings.find_one({
            "organization_id": store["organization_id"],
            "store_id": None
        })
    if not settings:
        settings = await db.onboarding_settings.find_one({"is_global": True})
    
    return {
        "valid": True,
        "store_id": invite["store_id"],
        "store_name": store.get("name"),
        "store_logo": store.get("logo_url"),
        "organization": org,
        "branding": settings.get("branding") if settings else None,
        "app_links": settings.get("app_links") if settings else None,
    }


@router.post("/join")
async def join_team(data: TeamMemberJoin):
    """
    Create a new user account from a team invite link.
    Returns the new user and triggers onboarding.
    """
    db = get_db()
    
    # Validate invite
    invite = await db.team_invites.find_one({
        "invite_code": data.invite_code,
        "is_active": True
    })
    
    if not invite:
        raise HTTPException(status_code=404, detail="Invalid or expired invite code")
    
    if invite.get("expires_at") and invite["expires_at"] < datetime.utcnow():
        raise HTTPException(status_code=400, detail="This invite link has expired")
    
    # Check if email or phone already exists
    existing_email = await db.users.find_one({"email": data.email.lower().strip()})
    if existing_email:
        raise HTTPException(status_code=400, detail="An account with this email already exists")
    
    # Normalize phone
    phone_clean = ''.join(c for c in data.phone if c.isdigit())
    if len(phone_clean) == 10:
        phone_clean = '1' + phone_clean
    phone_normalized = '+' + phone_clean if phone_clean else ''
    
    existing_phone = await db.users.find_one({"phone": phone_normalized})
    if existing_phone:
        raise HTTPException(status_code=400, detail="An account with this phone number already exists")
    
    # Get store info
    store = await db.stores.find_one({"_id": ObjectId(invite["store_id"])})
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    
    # Generate temporary password
    temp_password = secrets.token_urlsafe(8)
    
    # Create user account
    new_user = {
        "name": data.name.strip(),
        "email": data.email.lower().strip(),
        "phone": phone_normalized,
        "password": temp_password,  # Will be hashed by auth system on first login
        "role": "user",  # Default role for team members
        "store_id": invite["store_id"],
        "store_ids": [invite["store_id"]],
        "organization_id": invite.get("organization_id"),
        "created_at": datetime.utcnow(),
        "invited_by": invite["created_by"],
        "invite_code": data.invite_code,
        "is_active": True,
        "onboarding_complete": False,  # Requires training
        "status": "active",
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
    
    # Increment invite usage
    await db.team_invites.update_one(
        {"_id": invite["_id"]},
        {"$inc": {"uses_count": 1}}
    )
    
    # Get onboarding settings for welcome message
    settings = await db.onboarding_settings.find_one({"store_id": invite["store_id"]})
    if not settings and invite.get("organization_id"):
        settings = await db.onboarding_settings.find_one({
            "organization_id": invite["organization_id"],
            "store_id": None
        })
    if not settings:
        settings = await db.onboarding_settings.find_one({"is_global": True})
    
    # Generate training link
    import os
    base_url = APP_URL
    training_link = f"{base_url}/imos/onboarding-preview"
    
    # Queue welcome SMS (if auto-send is enabled)
    sms_queued = False
    if settings and settings.get("auto_send_welcome_sms"):
        message_template = settings.get("messages", {}).get("team_welcome_sms", "")
        if message_template:
            message = message_template.replace("{training_link}", training_link)
            message = message.replace("{user_name}", data.name.strip())
            message = message.replace("{store_name}", store.get("name", ""))
            
            # Queue SMS for sending (would integrate with Twilio)
            sms_queue = {
                "user_id": user_id,
                "phone": phone_normalized,
                "message": message,
                "status": "pending",
                "type": "team_welcome",
                "created_at": datetime.utcnow(),
            }
            await db.sms_queue.insert_one(sms_queue)
            sms_queued = True
    
    # Remove password from response
    del new_user["password"]
    
    return {
        "success": True,
        "user": new_user,
        "training_link": training_link,
        "sms_queued": sms_queued,
        "store_name": store.get("name"),
        "message": f"Welcome to {store.get('name')}! Complete your training to get started."
    }


@router.get("/store/{store_id}")
async def get_store_invites(store_id: str):
    """Get all active invite links for a store"""
    db = get_db()
    
    invites = await db.team_invites.find({
        "store_id": store_id,
        "is_active": True
    }).sort("created_at", -1).to_list(100)
    
    # Get creator names
    creator_ids = list(set([i.get("created_by") for i in invites if i.get("created_by")]))
    creators = {}
    if creator_ids:
        creator_docs = await db.users.find(
            {"_id": {"$in": [ObjectId(cid) for cid in creator_ids]}},
            {"_id": 1, "name": 1}
        ).to_list(100)
        creators = {str(c["_id"]): c.get("name", "Unknown") for c in creator_docs}
    
    import os
    base_url = APP_URL
    
    result = []
    for invite in invites:
        result.append({
            "_id": str(invite["_id"]),
            "invite_code": invite["invite_code"],
            "invite_url": f"{base_url}/imos/signup?invite={invite['invite_code']}",
            "created_by_name": creators.get(invite.get("created_by"), "Unknown"),
            "created_at": invite.get("created_at"),
            "expires_at": invite.get("expires_at"),
            "uses_count": invite.get("uses_count", 0),
            "is_active": invite.get("is_active", True),
        })
    
    return result


@router.delete("/{invite_id}")
async def deactivate_invite(invite_id: str):
    """Deactivate an invite link"""
    db = get_db()
    
    result = await db.team_invites.update_one(
        {"_id": ObjectId(invite_id)},
        {"$set": {"is_active": False, "deactivated_at": datetime.utcnow()}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Invite not found")
    
    return {"message": "Invite deactivated successfully"}


@router.get("/user/{user_id}/invite-link")
async def get_user_share_link(user_id: str):
    """
    Get or create a personal share link for a user to invite team members.
    This link is tied to the user's store.
    """
    db = get_db()
    
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    store_id = user.get("store_id")
    if not store_id:
        raise HTTPException(status_code=400, detail="User is not assigned to a store")
    
    # Check for existing active invite from this user
    existing = await db.team_invites.find_one({
        "store_id": store_id,
        "created_by": user_id,
        "is_active": True,
        "expires_at": {"$gt": datetime.utcnow()}
    })
    
    if existing:
        import os
        base_url = APP_URL
        return {
            "invite_code": existing["invite_code"],
            "invite_url": f"{base_url}/imos/signup?invite={existing['invite_code']}",
            "expires_at": existing.get("expires_at").isoformat() if existing.get("expires_at") else None,
            "uses_count": existing.get("uses_count", 0),
        }
    
    # Create new invite
    from datetime import timedelta
    invite_code = generate_invite_code()
    
    # Ensure uniqueness
    existing_code = await db.team_invites.find_one({"invite_code": invite_code})
    while existing_code:
        invite_code = generate_invite_code()
        existing_code = await db.team_invites.find_one({"invite_code": invite_code})
    
    expires_at = datetime.utcnow() + timedelta(days=90)  # Personal links last 90 days
    
    invite = {
        "invite_code": invite_code,
        "store_id": store_id,
        "organization_id": user.get("organization_id"),
        "created_by": user_id,
        "created_at": datetime.utcnow(),
        "expires_at": expires_at,
        "is_active": True,
        "uses_count": 0,
        "is_personal": True,
    }
    
    await db.team_invites.insert_one(invite)
    
    import os
    base_url = APP_URL
    
    return {
        "invite_code": invite_code,
        "invite_url": f"{base_url}/imos/signup?invite={invite_code}",
        "expires_at": expires_at.isoformat(),
        "uses_count": 0,
    }



# ============= SHARE VIA SMS WITH ANALYTICS =============

class ShareInviteViaSMS(BaseModel):
    user_id: str
    recipient_phone: str
    recipient_name: Optional[str] = None
    custom_message: Optional[str] = None


@router.post("/share-via-sms")
async def share_invite_via_sms(data: ShareInviteViaSMS):
    """
    Share team invite link via SMS with full tracking/analytics.
    Creates a tracked share record for analytics.
    """
    db = get_db()
    
    # Get user and their store
    user = await db.users.find_one({"_id": ObjectId(data.user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    store_id = user.get("store_id")
    if not store_id:
        raise HTTPException(status_code=400, detail="User is not assigned to a store")
    
    # Get store info
    store = await db.stores.find_one({"_id": ObjectId(store_id)})
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    
    # Get or create user's invite link
    from datetime import timedelta
    
    existing_invite = await db.team_invites.find_one({
        "store_id": store_id,
        "created_by": data.user_id,
        "is_active": True,
        "expires_at": {"$gt": datetime.utcnow()}
    })
    
    if existing_invite:
        invite_code = existing_invite["invite_code"]
    else:
        # Create new invite
        invite_code = generate_invite_code()
        existing_code = await db.team_invites.find_one({"invite_code": invite_code})
        while existing_code:
            invite_code = generate_invite_code()
            existing_code = await db.team_invites.find_one({"invite_code": invite_code})
        
        expires_at = datetime.utcnow() + timedelta(days=90)
        
        new_invite = {
            "invite_code": invite_code,
            "store_id": store_id,
            "organization_id": user.get("organization_id"),
            "created_by": data.user_id,
            "created_at": datetime.utcnow(),
            "expires_at": expires_at,
            "is_active": True,
            "uses_count": 0,
            "is_personal": True,
        }
        await db.team_invites.insert_one(new_invite)
    
    # Normalize phone
    phone_clean = ''.join(c for c in data.recipient_phone if c.isdigit())
    if len(phone_clean) == 10:
        phone_clean = '1' + phone_clean
    recipient_phone = '+' + phone_clean if phone_clean else ''
    
    if not recipient_phone:
        raise HTTPException(status_code=400, detail="Invalid phone number")
    
    # Build invite URL
    import os
    base_url = APP_URL
    invite_url = f"{base_url}/imos/signup?invite={invite_code}"
    
    # Get onboarding settings for message template
    settings = await db.onboarding_settings.find_one({"store_id": store_id})
    if not settings and user.get("organization_id"):
        settings = await db.onboarding_settings.find_one({
            "organization_id": user["organization_id"],
            "store_id": None
        })
    if not settings:
        settings = await db.onboarding_settings.find_one({"is_global": True})
    
    # Build message
    if data.custom_message:
        message = data.custom_message
        # Ensure link is in message
        if "{invite_link}" in message:
            message = message.replace("{invite_link}", invite_url)
        elif invite_url not in message:
            message = f"{message}\n\n{invite_url}"
    else:
        # Use template from settings or default
        template = settings.get("messages", {}).get("team_invite_sms", "") if settings else ""
        if template:
            message = template.replace("{app_link}", invite_url)
            message = message.replace("{user_name}", data.recipient_name or "")
            message = message.replace("{store_name}", store.get("name", ""))
        else:
            sender_name = user.get("name", "Your colleague")
            message = f"Hey{' ' + data.recipient_name if data.recipient_name else ''}! {sender_name} invited you to join {store.get('name')}. Download the app and start your training: {invite_url}"
    
    # Create tracked share record for analytics
    share_record = {
        "type": "team_invite",
        "invite_code": invite_code,
        "shared_by": data.user_id,
        "shared_by_name": user.get("name"),
        "store_id": store_id,
        "organization_id": user.get("organization_id"),
        "recipient_phone": recipient_phone,
        "recipient_name": data.recipient_name,
        "message": message,
        "invite_url": invite_url,
        "created_at": datetime.utcnow(),
        "status": "pending",
        "clicked": False,
        "joined": False,
    }
    share_result = await db.invite_shares.insert_one(share_record)
    share_id = str(share_result.inserted_id)
    
    # Queue SMS for sending
    sms_record = {
        "share_id": share_id,
        "user_id": data.user_id,
        "phone": recipient_phone,
        "message": message,
        "type": "team_invite_share",
        "status": "pending",
        "created_at": datetime.utcnow(),
    }
    await db.sms_queue.insert_one(sms_record)
    
    # Try to send immediately via Twilio
    sms_sent = False
    sms_error = None
    try:
        from services.twilio_service import send_sms
        result = await send_sms(recipient_phone, message)
        if result.get("success"):
            sms_sent = True
            await db.sms_queue.update_one(
                {"share_id": share_id},
                {"$set": {"status": "sent", "sent_at": datetime.utcnow(), "twilio_sid": result.get("sid")}}
            )
            await db.invite_shares.update_one(
                {"_id": share_result.inserted_id},
                {"$set": {"status": "sent", "sent_at": datetime.utcnow()}}
            )
        else:
            sms_error = result.get("error", "Unknown error")
    except Exception as e:
        sms_error = str(e)
    
    return {
        "success": True,
        "share_id": share_id,
        "invite_code": invite_code,
        "invite_url": invite_url,
        "recipient_phone": recipient_phone,
        "message_sent": sms_sent,
        "sms_error": sms_error,
        "message_preview": message[:100] + "..." if len(message) > 100 else message,
    }


@router.get("/shares/{user_id}")
async def get_user_invite_shares(user_id: str, limit: int = 50):
    """
    Get analytics for invite shares by a user.
    Shows who they shared with, who clicked, and who joined.
    """
    db = get_db()
    
    shares = await db.invite_shares.find({
        "shared_by": user_id
    }).sort("created_at", -1).limit(limit).to_list(limit)
    
    # Calculate stats
    total_shares = len(shares)
    total_clicked = sum(1 for s in shares if s.get("clicked"))
    total_joined = sum(1 for s in shares if s.get("joined"))
    
    result = []
    for share in shares:
        result.append({
            "_id": str(share["_id"]),
            "recipient_phone": share.get("recipient_phone", "")[-4:].rjust(len(share.get("recipient_phone", "")), "*"),  # Mask phone
            "recipient_name": share.get("recipient_name"),
            "invite_code": share.get("invite_code"),
            "status": share.get("status"),
            "clicked": share.get("clicked", False),
            "clicked_at": share.get("clicked_at"),
            "joined": share.get("joined", False),
            "joined_at": share.get("joined_at"),
            "created_at": share.get("created_at"),
        })
    
    return {
        "shares": result,
        "stats": {
            "total_shares": total_shares,
            "total_clicked": total_clicked,
            "total_joined": total_joined,
            "click_rate": round(total_clicked / total_shares * 100, 1) if total_shares > 0 else 0,
            "conversion_rate": round(total_joined / total_shares * 100, 1) if total_shares > 0 else 0,
        }
    }


@router.get("/analytics/store/{store_id}")
async def get_store_invite_analytics(store_id: str, days: int = 30):
    """
    Get store-wide invite share analytics.
    Shows team growth metrics and top sharers.
    """
    db = get_db()
    
    from datetime import timedelta
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # Get all shares for this store in the time period
    shares = await db.invite_shares.find({
        "store_id": store_id,
        "created_at": {"$gte": start_date}
    }).limit(500).to_list(500)
    
    # Get unique sharers with their stats
    sharer_stats = {}
    for share in shares:
        sharer_id = share.get("shared_by")
        if sharer_id not in sharer_stats:
            sharer_stats[sharer_id] = {
                "name": share.get("shared_by_name", "Unknown"),
                "shares": 0,
                "clicks": 0,
                "joins": 0,
            }
        sharer_stats[sharer_id]["shares"] += 1
        if share.get("clicked"):
            sharer_stats[sharer_id]["clicks"] += 1
        if share.get("joined"):
            sharer_stats[sharer_id]["joins"] += 1
    
    # Sort by joins (most effective sharers)
    top_sharers = sorted(
        [{"user_id": k, **v} for k, v in sharer_stats.items()],
        key=lambda x: (x["joins"], x["clicks"], x["shares"]),
        reverse=True
    )[:10]
    
    # Overall stats
    total_shares = len(shares)
    total_clicked = sum(1 for s in shares if s.get("clicked"))
    total_joined = sum(1 for s in shares if s.get("joined"))
    
    return {
        "period_days": days,
        "total_shares": total_shares,
        "total_clicked": total_clicked,
        "total_joined": total_joined,
        "click_rate": round(total_clicked / total_shares * 100, 1) if total_shares > 0 else 0,
        "conversion_rate": round(total_joined / total_shares * 100, 1) if total_shares > 0 else 0,
        "top_sharers": top_sharers,
        "unique_sharers": len(sharer_stats),
    }



# ============= EMAIL INVITE ENDPOINTS =============

@router.post("/send-email-invite")
async def send_email_invite(data: EmailInviteRequest):
    """
    Send a team invite via email.
    Creates an invite record and sends an email with a unique invite link.
    """
    import resend
    
    db = get_db()
    
    # Verify store exists
    store = await db.stores.find_one({"_id": ObjectId(data.store_id)})
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    
    # Verify sender exists
    sender = await db.users.find_one({"_id": ObjectId(data.created_by)})
    if not sender:
        raise HTTPException(status_code=404, detail="Sender not found")
    
    # Check if email already exists
    existing_user = await db.users.find_one({"email": data.recipient_email.lower().strip()})
    if existing_user:
        raise HTTPException(status_code=400, detail="A user with this email already exists")
    
    # Generate unique invite code
    invite_code = generate_invite_code(12)  # Longer code for email invites
    
    # Check for uniqueness
    existing = await db.team_invites.find_one({"invite_code": invite_code})
    while existing:
        invite_code = generate_invite_code(12)
        existing = await db.team_invites.find_one({"invite_code": invite_code})
    
    # Create invite record
    from datetime import timedelta
    expires_at = datetime.utcnow() + timedelta(days=data.expires_days)
    
    invite = {
        "invite_code": invite_code,
        "store_id": data.store_id,
        "organization_id": store.get("organization_id"),
        "created_by": data.created_by,
        "created_at": datetime.utcnow(),
        "expires_at": expires_at,
        "is_active": True,
        "uses_count": 0,
        "invite_type": "email",
        "recipient_email": data.recipient_email.lower().strip(),
        "recipient_name": data.recipient_name,
    }
    
    result = await db.team_invites.insert_one(invite)
    invite["_id"] = str(result.inserted_id)
    
    # Generate invite URL
    base_url = APP_URL
    invite_url = f"{base_url}/imos/signup?invite={invite_code}"
    
    # Send email via Resend
    RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
    SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "noreply@imosapp.com")
    
    if not RESEND_API_KEY:
        logger.warning("Resend API key not configured - invite created but email not sent")
        return {
            "success": True,
            "invite_code": invite_code,
            "invite_url": invite_url,
            "email_sent": False,
            "message": "Invite created but email service not configured"
        }
    
    resend.api_key = RESEND_API_KEY
    
    # Build email content
    sender_name = sender.get("name", "Your colleague")
    store_name = store.get("name", "our team")
    recipient_name = data.recipient_name or "there"
    
    custom_msg = ""
    if data.custom_message:
        custom_msg = f"""
        <p style="color: #666; line-height: 1.6; font-style: italic; border-left: 3px solid #007AFF; padding-left: 15px; margin: 20px 0;">
            "{data.custom_message}"
        </p>
        """
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin: 0; padding: 0; background-color: #f5f5f5; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
        <div style="max-width: 600px; margin: 0 auto; background-color: white; border-radius: 12px; overflow: hidden; margin-top: 20px; margin-bottom: 20px;">
            <div style="background: linear-gradient(135deg, #007AFF, #00C7BE); padding: 30px; text-align: center;">
                <h1 style="color: white; margin: 0; font-size: 24px;">You're Invited!</h1>
            </div>
            <div style="padding: 30px;">
                <p style="color: #333; font-size: 16px; line-height: 1.6;">
                    Hi {recipient_name},
                </p>
                <p style="color: #666; line-height: 1.6;">
                    <strong>{sender_name}</strong> has invited you to join <strong>{store_name}</strong> on iMos.
                </p>
                {custom_msg}
                <p style="color: #666; line-height: 1.6;">
                    Click the button below to set up your account and get started:
                </p>
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{invite_url}" style="display: inline-block; background-color: #007AFF; color: white; padding: 14px 32px; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 16px;">
                        Accept Invitation
                    </a>
                </div>
                <p style="color: #999; font-size: 13px; text-align: center;">
                    This invite expires in {data.expires_days} days.
                </p>
                <hr style="border: none; border-top: 1px solid #eee; margin: 25px 0;">
                <p style="color: #999; font-size: 12px; text-align: center;">
                    If you didn't expect this invitation, you can safely ignore this email.
                </p>
            </div>
        </div>
    </body>
    </html>
    """
    
    try:
        email_result = await asyncio.to_thread(
            resend.Emails.send,
            {
                "from": f"iMOs <{SENDER_EMAIL}>",
                "to": [data.recipient_email],
                "subject": f"{sender_name} invited you to join {store_name}",
                "html": html_content,
            }
        )
        
        # Log the email send
        await db.email_logs.insert_one({
            "user_id": data.created_by,
            "recipient_email": data.recipient_email,
            "recipient_name": data.recipient_name,
            "subject": f"Team Invite from {sender_name}",
            "type": "team_invite",
            "invite_code": invite_code,
            "status": "sent",
            "resend_id": email_result.get("id"),
            "sent_at": datetime.utcnow(),
        })
        
        return {
            "success": True,
            "invite_code": invite_code,
            "invite_url": invite_url,
            "email_sent": True,
            "message": f"Invitation sent to {data.recipient_email}"
        }
        
    except Exception as e:
        logger.error(f"Failed to send invite email: {str(e)}")
        
        # Log the failed attempt
        await db.email_logs.insert_one({
            "user_id": data.created_by,
            "recipient_email": data.recipient_email,
            "type": "team_invite",
            "invite_code": invite_code,
            "status": "failed",
            "error": str(e),
            "attempted_at": datetime.utcnow(),
        })
        
        return {
            "success": True,
            "invite_code": invite_code,
            "invite_url": invite_url,
            "email_sent": False,
            "message": f"Invite created but email failed to send: {str(e)}"
        }


@router.post("/accept")
async def accept_invite(data: AcceptInviteRequest):
    """
    Accept a team invite and create a user account.
    This is used when a user clicks the invite link and sets up their password.
    """
    db = get_db()
    
    # Find and validate invite
    invite = await db.team_invites.find_one({
        "invite_code": data.invite_code,
        "is_active": True
    })
    
    if not invite:
        raise HTTPException(status_code=404, detail="Invalid or expired invite code")
    
    # Check expiration
    if invite.get("expires_at") and invite["expires_at"] < datetime.utcnow():
        raise HTTPException(status_code=400, detail="This invite link has expired")
    
    # Check if email already exists
    existing_email = await db.users.find_one({"email": data.email.lower().strip()})
    if existing_email:
        raise HTTPException(status_code=400, detail="An account with this email already exists. Try logging in.")
    
    # Get store info
    store = await db.stores.find_one({"_id": ObjectId(invite["store_id"])})
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    
    # Normalize phone if provided
    phone_normalized = None
    if data.phone:
        phone_clean = ''.join(c for c in data.phone if c.isdigit())
        if len(phone_clean) == 10:
            phone_clean = '1' + phone_clean
        phone_normalized = '+' + phone_clean if phone_clean else None
    
    # Create user account
    new_user = {
        "name": data.name.strip(),
        "email": data.email.lower().strip(),
        "phone": phone_normalized,
        "password": data.password,  # In production, hash this!
        "role": "user",
        "store_id": invite["store_id"],
        "store_ids": [invite["store_id"]],
        "organization_id": invite.get("organization_id"),
        "created_at": datetime.utcnow(),
        "invited_by": invite["created_by"],
        "invite_code": data.invite_code,
        "is_active": True,
        "status": "active",  # Active immediately since they were invited
        "account_type": "organization",
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
    
    # Increment invite usage and mark email invite as used
    update_data = {"$inc": {"uses_count": 1}}
    if invite.get("invite_type") == "email":
        update_data["$set"] = {
            "is_active": False,  # Email invites are single-use
            "used_at": datetime.utcnow(),
            "used_by": user_id
        }
    
    await db.team_invites.update_one(
        {"_id": invite["_id"]},
        update_data
    )
    
    # Update any share records
    await db.invite_shares.update_one(
        {"invite_code": data.invite_code, "joined": False},
        {"$set": {"joined": True, "joined_at": datetime.utcnow(), "joined_user_id": user_id}}
    )
    
    # Remove password from response
    del new_user["password"]
    
    return {
        "success": True,
        "user": new_user,
        "store_name": store.get("name"),
        "message": f"Welcome to {store.get('name')}! Your account is ready."
    }


@router.get("/validate-email/{invite_code}")
async def validate_email_invite(invite_code: str):
    """
    Validate an email invite code and return pre-filled info.
    Returns the recipient's email if it was an email invite.
    """
    db = get_db()
    
    invite = await db.team_invites.find_one({
        "invite_code": invite_code,
        "is_active": True
    })
    
    if not invite:
        raise HTTPException(status_code=404, detail="Invalid or expired invite code")
    
    # Check expiration
    if invite.get("expires_at") and invite["expires_at"] < datetime.utcnow():
        raise HTTPException(status_code=400, detail="This invite link has expired")
    
    # Get store info
    store = await db.stores.find_one({"_id": ObjectId(invite["store_id"])})
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    
    # Get organization info
    org = None
    if store.get("organization_id"):
        org_doc = await db.organizations.find_one({"_id": ObjectId(store["organization_id"])})
        if org_doc:
            org = {"name": org_doc.get("name")}
    
    # Get inviter info
    inviter = None
    if invite.get("created_by"):
        inviter_doc = await db.users.find_one({"_id": ObjectId(invite["created_by"])})
        if inviter_doc:
            inviter = {"name": inviter_doc.get("name")}
    
    return {
        "valid": True,
        "invite_type": invite.get("invite_type", "link"),
        "store_id": invite["store_id"],
        "store_name": store.get("name"),
        "store_logo": store.get("logo_url"),
        "organization": org,
        "inviter": inviter,
        # Pre-fill email if it was an email invite
        "recipient_email": invite.get("recipient_email") if invite.get("invite_type") == "email" else None,
        "recipient_name": invite.get("recipient_name"),
        "expires_at": invite.get("expires_at").isoformat() if invite.get("expires_at") else None,
    }
