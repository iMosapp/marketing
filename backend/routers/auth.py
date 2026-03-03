"""
Authentication router - handles login, signup, forgot password
"""
from fastapi import APIRouter, HTTPException
from bson import ObjectId
from datetime import datetime
from typing import Optional
import random
import logging
import os
import httpx
import resend
import asyncio

from models import User, UserCreate, UserPersona
from routers.database import get_db

router = APIRouter(prefix="/auth", tags=["Authentication"])
logger = logging.getLogger(__name__)

APP_URL = os.environ.get("APP_URL", "https://app.imonsocial.com")

# Resend configuration
RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "noreply@imonsocial.com")
if RESEND_API_KEY:
    resend.api_key = RESEND_API_KEY

# Store reset codes temporarily (in production, use Redis or similar)
reset_codes = {}

async def send_welcome_email(user: dict):
    """Send welcome email to new user"""
    if not RESEND_API_KEY:
        logger.warning("Resend API key not configured, skipping welcome email")
        return
    
    try:
        html_content = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background: #000; color: #fff;">
            <div style="text-align: center; margin-bottom: 30px;">
                <h1 style="color: #FF3B30; display: inline;">i</h1><h1 style="color: #34C759; display: inline;">'</h1><h1 style="color: #007AFF; display: inline;">M</h1><h1 style="color: #FFD60A; display: inline;">O</h1><h1 style="color: #34C759; display: inline;">s</h1>
            </div>
            <h2 style="color: #fff; text-align: center;">Welcome to i'M On Social, {user.get('name', 'there')}!</h2>
            <p style="color: #ccc; line-height: 1.6; text-align: center;">
                Thank you for signing up! You're now part of a community that believes in 
                timeless relationship principles powered by modern tools.
            </p>
            <div style="text-align: center; margin: 30px 0;">
                <a href="{APP_URL}/imos/login" 
                   style="background-color: #007AFF; color: white; padding: 15px 40px; 
                          text-decoration: none; border-radius: 8px; font-weight: bold; display: inline-block;">
                    Get Started
                </a>
            </div>
            <p style="color: #888; line-height: 1.6; text-align: center; font-size: 14px;">
                If you have any questions, we're here to help!
            </p>
            <div style="margin-top: 40px; padding-top: 20px; border-top: 1px solid #333; text-align: center;">
                <p style="color: #666; font-size: 12px;">
                    © 2026 i'M On Social. i'M Old School with modern tools.
                </p>
            </div>
        </div>
        """
        
        result = await asyncio.to_thread(resend.Emails.send, {
            "from": f"i'M On Social <{SENDER_EMAIL}>",
            "to": [user.get('email')],
            "subject": "Welcome to i'M On Social! 🎉",
            "html": html_content
        })
        
        logger.info(f"Welcome email sent to {user.get('email')}: {result.get('id')}")
        
        # Log in database
        await get_db().email_logs.insert_one({
            "user_id": str(user.get('_id')),
            "recipient_email": user.get('email'),
            "recipient_name": user.get('name'),
            "subject": "Welcome to i'M On Social! 🎉",
            "status": "sent",
            "resend_id": result.get('id'),
            "sent_at": datetime.utcnow(),
            "type": "welcome"
        })
        
    except Exception as e:
        logger.error(f"Failed to send welcome email: {str(e)}")

async def notify_super_admin_of_new_user(new_user: dict):
    """Send SMS notification to super admin about new user signup"""
    try:
        # Get super admin's phone number and mvpline_number
        super_admin = await get_db().users.find_one({"role": "super_admin", "mvpline_number": {"$exists": True, "$ne": None}})
        if not super_admin or not super_admin.get("mvpline_number"):
            logger.warning("No super admin with mvpline_number found for notification")
            return
        
        # Get the super admin's personal phone to notify
        admin_phone = super_admin.get("phone")
        from_number = super_admin.get("mvpline_number")
        
        if not admin_phone or not from_number:
            logger.warning("Super admin missing phone or mvpline_number")
            return
        
        # Build notification message
        org_name = "Unknown"
        if new_user.get("organization_id"):
            org = await get_db().organizations.find_one({"_id": ObjectId(new_user["organization_id"])})
            if org:
                org_name = org.get("name", "Unknown")
        
        message = f"New i'M On Social Signup!\n\nName: {new_user.get('name', 'Unknown')}\nEmail: {new_user.get('email', 'Unknown')}\nRole: {new_user.get('requested_role', 'Not specified')}\nOrg: {org_name}\n\nReview in Admin Panel → Pending Users"
        
        # Send via Twilio (check if we have credentials)
        twilio_sid = os.environ.get("TWILIO_ACCOUNT_SID")
        twilio_token = os.environ.get("TWILIO_AUTH_TOKEN")
        
        if twilio_sid and twilio_token:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"https://api.twilio.com/2010-04-01/Accounts/{twilio_sid}/Messages.json",
                    auth=(twilio_sid, twilio_token),
                    data={
                        "From": from_number,
                        "To": admin_phone,
                        "Body": message
                    }
                )
                if response.status_code == 201:
                    logger.info(f"Sent new user notification SMS to {admin_phone}")
                else:
                    logger.warning(f"Failed to send SMS: {response.text}")
        else:
            logger.info(f"Twilio not configured. Would send: {message}")
            
    except Exception as e:
        logger.error(f"Failed to notify super admin: {e}")

@router.post("/signup")
async def signup(user_data: UserCreate):
    """Create a new user account with pending status (or active for independents)"""
    # Check if user exists
    existing = await get_db().users.find_one({"email": user_data.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    user_dict = user_data.dict()
    user_dict['created_at'] = datetime.utcnow()
    user_dict['updated_at'] = datetime.utcnow()
    user_dict['onboarding_complete'] = False
    
    # Check if this is the FIRST user in the database - make them super_admin
    user_count = await get_db().users.count_documents({})
    is_first_user = user_count == 0
    
    # Check if independent (no organization_id or account_type is 'independent')
    is_independent = (
        not user_dict.get('organization_id') or 
        user_dict.get('account_type') == 'independent'
    )
    
    # Store what role they requested
    user_dict['requested_role'] = user_dict.get('role', 'Sales Rep')
    
    if is_first_user:
        # First user gets super_admin rights
        user_dict['role'] = 'super_admin'
        user_dict['status'] = 'active'
        user_dict['is_active'] = True
        user_dict['account_type'] = 'independent'
        user_dict['organization_id'] = None
        user_dict['needs_onboarding'] = False
        logger.info(f"First user {user_dict['email']} created as super_admin")
    elif is_independent:
        # Independents get full access immediately
        user_dict['role'] = 'user'  # They manage themselves
        user_dict['status'] = 'active'
        user_dict['is_active'] = True
        user_dict['account_type'] = 'independent'
        user_dict['organization_id'] = None
        # Show onboarding flow for profile setup
        user_dict['needs_onboarding'] = True
    else:
        # Organization users need admin approval
        user_dict['role'] = 'user'  # Actual role starts as basic user until approved
        user_dict['status'] = 'pending'  # pending, active, inactive
        user_dict['is_active'] = True  # Can login but has limited access
        user_dict['account_type'] = 'organization'
    
    user_dict['stats'] = {
        'contacts_added': 0,
        'messages_sent': 0,
        'calls_made': 0,
        'deals_closed': 0
    }
    user_dict['settings'] = {
        'leaderboard_visible': False,
        'compare_scope': 'state'
    }
    
    result = await get_db().users.insert_one(user_dict)
    user_dict['_id'] = str(result.inserted_id)
    
    # Send welcome email to new user
    await send_welcome_email(user_dict)
    
    # Send notification to super admin only for non-independents
    if not is_independent:
        await notify_super_admin_of_new_user(user_dict)
    
    # Remove password from response
    del user_dict['password']
    
    return user_dict

@router.post("/login")
async def login(credentials: dict):
    """Login with email and password"""
    email = credentials.get('email')
    password = credentials.get('password')
    
    user = await get_db().users.find_one({"email": email})
    if not user or user.get('password') != password:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    user['_id'] = str(user['_id'])
    # Remove password from response
    user.pop('password', None)
    
    # Convert ObjectIds to strings
    if user.get('organization_id'):
        user['organization_id'] = str(user['organization_id'])
    if user.get('store_id'):
        user['store_id'] = str(user['store_id'])
        # Include store slug for review link generation
        try:
            store = await get_db().stores.find_one({"_id": ObjectId(user['store_id'])}, {"slug": 1, "name": 1})
            if store:
                slug = store.get('slug')
                # Auto-generate slug from store name if missing
                if not slug and store.get('name'):
                    import re
                    slug = re.sub(r'[^a-z0-9]+', '-', store['name'].lower()).strip('-')
                    await get_db().stores.update_one(
                        {"_id": ObjectId(user['store_id'])},
                        {"$set": {"slug": slug}}
                    )
                if slug:
                    user['store_slug'] = slug
        except Exception:
            pass
    
    # Include org slug for org-level features
    if user.get('organization_id'):
        try:
            org = await get_db().organizations.find_one({"_id": ObjectId(user['organization_id'])}, {"slug": 1, "name": 1})
            if org:
                org_slug = org.get('slug')
                if not org_slug and org.get('name'):
                    import re
                    org_slug = re.sub(r'[^a-z0-9]+', '-', org['name'].lower()).strip('-')
                    await get_db().organizations.update_one(
                        {"_id": ObjectId(user['organization_id'])},
                        {"$set": {"slug": org_slug}}
                    )
                if org_slug:
                    user['org_slug'] = org_slug
        except Exception:
            pass

    # Resolve white-label partner branding
    partner_branding = None
    try:
        org_id = user.get('organization_id')
        store_id = user.get('store_id')
        pid = None

        # Check org-level partner first
        if org_id:
            try:
                org_doc = await get_db().organizations.find_one({"_id": ObjectId(org_id)}, {"partner_id": 1})
                if org_doc and org_doc.get("partner_id"):
                    pid = org_doc["partner_id"]
            except Exception:
                pass

        # Check store-level partner
        if not pid and store_id:
            try:
                store_doc = await get_db().stores.find_one({"_id": ObjectId(store_id)}, {"partner_id": 1})
                if store_doc and store_doc.get("partner_id"):
                    pid = store_doc["partner_id"]
            except Exception:
                pass

        # Fetch partner branding
        if pid:
            try:
                partner = await get_db().white_label_partners.find_one(
                    {"_id": ObjectId(pid), "is_active": True},
                    {"_id": 0, "created_at": 0, "updated_at": 0}
                )
                if partner:
                    partner_branding = partner
            except Exception:
                pass
    except Exception as e:
        logger.warning(f"Error resolving partner branding: {e}")

    # Track login for lifecycle tagging
    try:
        from .user_lifecycle import on_user_login
        await on_user_login(str(user['_id']))
    except Exception as e:
        logger.warning(f"Lifecycle login hook error: {e}")

    response = {
        "token": f"mock_token_{user['_id']}",
        "user": user
    }
    if partner_branding:
        response["partner_branding"] = partner_branding
    return response

@router.post("/forgot-password/request")
async def request_password_reset(data: dict):
    """Request a password reset code"""
    email = data.get('email')
    if not email:
        raise HTTPException(status_code=400, detail="Email is required")
    
    user = await get_db().users.find_one({"email": email})
    if not user:
        # Don't reveal if email exists
        return {"message": "If an account exists with this email, a reset code has been sent"}
    
    # Generate 6-digit code
    code = str(random.randint(100000, 999999))
    reset_codes[email] = {
        'code': code,
        'expires': datetime.utcnow().timestamp() + 600  # 10 minutes
    }
    
    logger.info(f"Password reset code generated for {email}")
    
    # Send reset code email via Resend
    if RESEND_API_KEY:
        try:
            params = {
                "from": f"i'M On Social <{SENDER_EMAIL}>",
                "to": [email],
                "subject": "Your i'M On Social Password Reset Code",
                "html": f"""
                <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 480px; margin: 0 auto; padding: 40px 20px; background: #ffffff;">
                    <div style="text-align: center; margin-bottom: 32px;">
                        <h2 style="color: #1A1A1A; margin: 0;">Password Reset</h2>
                    </div>
                    <p style="color: #555; font-size: 15px; line-height: 1.6;">
                        You requested a password reset for your i'M On Social account. Use the code below to reset your password. This code expires in 10 minutes.
                    </p>
                    <div style="text-align: center; margin: 32px 0;">
                        <div style="display: inline-block; background: #F0F4FF; border: 2px solid #007AFF; border-radius: 12px; padding: 16px 40px; letter-spacing: 8px; font-size: 28px; font-weight: 700; color: #007AFF;">
                            {code}
                        </div>
                    </div>
                    <p style="color: #999; font-size: 13px; text-align: center;">
                        If you didn't request this, you can safely ignore this email.
                    </p>
                </div>
                """
            }
            resend.Emails.send(params)
            logger.info(f"Password reset email sent to {email}")
        except Exception as e:
            logger.error(f"Failed to send reset email to {email}: {e}")
    else:
        logger.warning("Resend API key not configured, reset email not sent")
    
    return {
        "message": "If an account exists with this email, a reset code has been sent"
    }

@router.post("/forgot-password/verify")
async def verify_reset_code(data: dict):
    """Verify the reset code"""
    email = data.get('email')
    code = data.get('code')
    
    if not email or not code:
        raise HTTPException(status_code=400, detail="Email and code are required")
    
    stored = reset_codes.get(email)
    if not stored:
        raise HTTPException(status_code=400, detail="No reset request found for this email")
    
    if datetime.utcnow().timestamp() > stored['expires']:
        del reset_codes[email]
        raise HTTPException(status_code=400, detail="Reset code has expired")
    
    if stored['code'] != code:
        raise HTTPException(status_code=400, detail="Invalid reset code")
    
    return {"message": "Code verified", "verified": True}

@router.post("/forgot-password/reset")
async def reset_password(data: dict):
    """Reset the password with verified code"""
    email = data.get('email')
    code = data.get('code')
    new_password = data.get('new_password')
    
    if not all([email, code, new_password]):
        raise HTTPException(status_code=400, detail="Email, code, and new password are required")
    
    stored = reset_codes.get(email)
    if not stored or stored['code'] != code:
        raise HTTPException(status_code=400, detail="Invalid or expired reset code")
    
    # Update password
    result = await get_db().users.update_one(
        {"email": email},
        {"$set": {"password": new_password}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=400, detail="Failed to update password")
    
    # Clear the reset code
    del reset_codes[email]
    
    return {"message": "Password updated successfully"}


@router.post("/change-password")
async def change_password(data: dict):
    """Change password for logged-in user"""
    user_id = data.get('user_id')
    current_password = data.get('current_password')
    new_password = data.get('new_password')
    
    if not all([user_id, current_password, new_password]):
        raise HTTPException(status_code=400, detail="User ID, current password, and new password are required")
    
    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters")
    
    # Verify current password
    try:
        user = await get_db().users.find_one({"_id": ObjectId(user_id)})
    except Exception:
        raise HTTPException(status_code=404, detail="User not found")
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.get('password') != current_password:
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    
    # Update password and clear needs_password_change flag
    result = await get_db().users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {
            "password": new_password, 
            "needs_password_change": False,
            "updated_at": datetime.utcnow()
        }}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=400, detail="Failed to update password")
    
    return {"message": "Password changed successfully"}

@router.post("/admin-reset")
async def admin_password_reset(data: dict):
    """Emergency admin password reset - requires secret key"""
    secret = data.get('secret')
    email = data.get('email')
    new_password = data.get('new_password')
    
    if secret != "iM-On-Social-Emergency-Reset-2026":
        raise HTTPException(status_code=403, detail="Invalid secret")
    
    if not email or not new_password:
        raise HTTPException(status_code=400, detail="Email and new_password required")
    
    result = await get_db().users.update_one(
        {"email": email},
        {"$set": {"password": new_password, "status": "active", "is_active": True}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {"message": f"Password reset and account activated for {email}"}


@router.post("/persona/{user_id}")
async def save_persona(user_id: str, persona: UserPersona):
    """Save the AI persona settings for a user"""
    result = await get_db().users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {
            "persona": persona.dict(),
            "onboarding_complete": True
        }}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {"message": "Persona saved successfully"}


@router.post("/complete-onboarding")
async def complete_onboarding(data: dict):
    """
    Complete the onboarding process for a new user.
    Saves profile data, AI preferences, persona data, and notifies admins/managers.
    """
    db = get_db()
    user_id = data.get("user_id")
    
    # Profile verification data
    updated_name = data.get("name")
    title = data.get("title", "")
    bio = data.get("bio", "")
    
    # New comprehensive onboarding data
    communication_style = data.get("communication_style", "friendly")
    ai_greeting_style = data.get("ai_greeting_style", "assistant")
    hobbies = data.get("hobbies", "")
    family_info = data.get("family_info", "")
    fun_facts = data.get("fun_facts", "")
    
    # Legacy support
    ai_intro_style = data.get("ai_intro_style", ai_greeting_style)
    fun_fact = data.get("fun_fact", fun_facts)
    
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID required")
    
    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)})
    except Exception:
        raise HTTPException(status_code=404, detail="User not found")
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Build AI intro message based on greeting style
    user_first_name = user.get("name", "").split(" ")[0] or "your salesperson"
    intro_templates = {
        "assistant": f"Hi! I'm {user_first_name}'s assistant. {user_first_name} is with a customer right now, but I can help!",
        "team": f"Hey there! This is {user_first_name}'s team. How can we help you today?",
        "busy": f"Thanks for reaching out! {user_first_name} is currently tied up but wanted me to check in. What can I do for you?",
        "helper": f"Thanks for reaching out! {user_first_name} is with a customer right now but wanted me to check in. What can I do for you?",
    }
    ai_intro_message = intro_templates.get(ai_intro_style, intro_templates["assistant"])
    
    # Build AI persona context from collected data
    persona_context = []
    if hobbies.strip():
        persona_context.append(f"Hobbies & interests: {hobbies.strip()}")
    if family_info.strip():
        persona_context.append(f"Family: {family_info.strip()}")
    if fun_facts.strip() or fun_fact.strip():
        fact = fun_facts.strip() or fun_fact.strip()
        persona_context.append(f"Fun facts: {fact}")
    
    # Update user with comprehensive onboarding data
    update_data = {
        "onboarding_complete": True,
        "onboarding_completed_at": datetime.utcnow(),
        "ai_intro_style": ai_intro_style,
        "ai_intro_message": ai_intro_message,
        "communication_style": communication_style,
        "ai_persona_context": "\n".join(persona_context) if persona_context else "",
    }
    
    # Update name if provided and different
    if updated_name and updated_name.strip():
        update_data["name"] = updated_name.strip()
    
    # Update persona with title and bio
    persona_update = {}
    if title.strip():
        persona_update["title"] = title.strip()
    if bio.strip():
        persona_update["bio"] = bio.strip()
    
    if persona_update:
        # Merge with existing persona data
        existing_persona = user.get("persona", {})
        update_data["persona"] = {**existing_persona, **persona_update}
    
    # Store individual fields for persona training
    if hobbies.strip():
        update_data["hobbies"] = hobbies.strip()
    if family_info.strip():
        update_data["family_info"] = family_info.strip()
    
    # Add fun facts to array
    combined_fun_fact = fun_facts.strip() or fun_fact.strip()
    if combined_fun_fact:
        existing_fun_facts = user.get("fun_facts", [])
        if combined_fun_fact not in existing_fun_facts:
            existing_fun_facts.append(combined_fun_fact)
        update_data["fun_facts"] = existing_fun_facts
    
    await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": update_data}
    )
    
    # Create urgent notification for managers and admins
    await notify_onboarding_complete(user)
    
    return {"success": True, "message": "Onboarding completed!"}


async def notify_onboarding_complete(user: dict):
    """Send notifications when a user completes onboarding"""
    db = get_db()
    user_name = user.get("name", "A user")
    store_id = user.get("store_id")
    
    # Find managers to notify
    managers_to_notify = []
    
    # If user belongs to a store, notify the store manager
    if store_id:
        store_managers = await db.users.find({
            "store_id": store_id,
            "role": {"$in": ["store_manager", "org_admin"]},
            "_id": {"$ne": user.get("_id")}
        }).to_list(10)
        managers_to_notify.extend(store_managers)
    
    # Always notify super admins
    super_admins = await db.users.find({
        "role": "super_admin",
        "_id": {"$ne": user.get("_id")}
    }).to_list(10)
    managers_to_notify.extend(super_admins)
    
    # Create inbox notification for each manager
    for manager in managers_to_notify:
        manager_id = str(manager["_id"])
        
        # Create an urgent notification in their inbox
        notification = {
            "user_id": manager_id,
            "type": "onboarding_complete",
            "title": "Training Completed!",
            "message": f"{user_name} has completed their onboarding training and is ready to start using i'M On Social!",
            "related_user_id": str(user.get("_id")),
            "related_user_name": user_name,
            "priority": "urgent",
            "read": False,
            "created_at": datetime.utcnow(),
        }
        await db.notifications.insert_one(notification)
        
        # Also try to send SMS notification if they have a phone
        try:
            await send_onboarding_notification_sms(manager, user_name)
        except Exception as e:
            logger.warning(f"Failed to send onboarding SMS to {manager.get('name')}: {e}")


async def send_onboarding_notification_sms(manager: dict, user_name: str):
    """Send SMS notification about onboarding completion"""
    import os
    
    twilio_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    twilio_token = os.environ.get("TWILIO_AUTH_TOKEN")
    
    if not twilio_sid or not twilio_token:
        return
    
    manager_phone = manager.get("phone")
    from_number = manager.get("mvpline_number") or os.environ.get("TWILIO_PHONE_NUMBER")
    
    if not manager_phone or not from_number:
        return
    
    message = f"Training Complete!\n\n{user_name} has completed their i'M On Social onboarding and is ready to start!"
    
    try:
        from twilio.rest import Client
        client = Client(twilio_sid, twilio_token)
        client.messages.create(
            body=message,
            from_=from_number,
            to=manager_phone
        )
    except Exception as e:
        logger.warning(f"Twilio SMS failed: {e}")

@router.get("/user/{user_id}")
async def get_user(user_id: str):
    """Get user profile"""
    user = await get_db().users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user['_id'] = str(user['_id'])
    user.pop('password', None)
    
    return user

@router.put("/user/{user_id}")
async def update_user(user_id: str, user_data: dict):
    """Update user profile"""
    allowed_fields = ['name', 'phone', 'persona', 'settings', 'timezone']
    update_dict = {k: v for k, v in user_data.items() if k in allowed_fields}
    
    if not update_dict:
        raise HTTPException(status_code=400, detail="No valid fields to update")
    
    result = await get_db().users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": update_dict}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {"message": "User updated successfully"}


@router.patch("/users/{user_id}")
async def patch_user(user_id: str, user_data: dict):
    """Update user profile fields including photo"""
    allowed_fields = ['name', 'phone', 'persona', 'settings', 'photo_url', 'bio', 'social_links', 'timezone']
    update_dict = {k: v for k, v in user_data.items() if k in allowed_fields}
    
    if not update_dict:
        raise HTTPException(status_code=400, detail="No valid fields to update")
    
    result = await get_db().users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": update_dict}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Return the updated user data
    updated_user = await get_db().users.find_one({"_id": ObjectId(user_id)})
    if updated_user:
        updated_user["_id"] = str(updated_user["_id"])
        updated_user.pop("password", None)
    
    return updated_user


@router.get("/users/{user_id}/review-links")
async def get_review_links(user_id: str):
    """Get user's review links for quick sharing"""
    user = await get_db().users.find_one(
        {"_id": ObjectId(user_id)},
        {"review_links": 1, "custom_link_name": 1}
    )
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "review_links": user.get("review_links", {}),
        "custom_link_name": user.get("custom_link_name", "")
    }


@router.put("/users/{user_id}/review-links")
async def update_review_links(user_id: str, data: dict):
    """Save user's review links"""
    result = await get_db().users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {
            "review_links": data.get("review_links", {}),
            "custom_link_name": data.get("custom_link_name", "")
        }}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {"message": "Review links saved"}
