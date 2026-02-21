from fastapi import FastAPI, APIRouter, HTTPException, status
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import os
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Optional
import random
from models import (
    User, UserCreate, UserPersona,
    Contact, ContactCreate,
    Conversation, Message, MessageCreate,
    Call, CallCreate,
    Campaign, CampaignCreate, CampaignEnrollment,
    Task, TaskCreate,
    Organization, OrganizationCreate,
    Store, StoreCreate
)

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============= ROLE-BASED ACCESS HELPERS =============
async def get_user_by_id(user_id: str) -> dict:
    """Get user by ID, returns None if not found"""
    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if user:
            user['_id'] = str(user['_id'])
        return user
    except:
        return None

async def get_accessible_user_ids(user: dict) -> List[str]:
    """Get list of user IDs that this user can access based on role"""
    role = user.get('role', 'user')
    user_id = str(user.get('_id'))
    
    if role == 'super_admin':
        # Super admin can see all users
        all_users = await db.users.find({}, {"_id": 1}).to_list(10000)
        return [str(u['_id']) for u in all_users]
    
    elif role == 'org_admin':
        # Org admin can see all users in their organization
        org_id = user.get('organization_id')
        if not org_id:
            return [user_id]
        org_users = await db.users.find({"organization_id": org_id}, {"_id": 1}).to_list(10000)
        return [str(u['_id']) for u in org_users]
    
    elif role == 'store_manager':
        # Store manager can see all users in their store
        store_id = user.get('store_id')
        if not store_id:
            return [user_id]
        store_users = await db.users.find({"store_id": store_id}, {"_id": 1}).to_list(10000)
        return [str(u['_id']) for u in store_users]
    
    else:
        # Regular user can only see their own data
        return [user_id]

async def get_data_filter(user_id: str) -> dict:
    """
    Returns a MongoDB query filter for data access based on user role.
    This is the CORE function for role-based data filtering.
    
    - super_admin: {} (all data)
    - org_admin: {"user_id": {"$in": [all users in org]}}
    - store_manager: {"user_id": {"$in": [all users in store]}}
    - user: {"user_id": user_id}
    """
    user = await get_user_by_id(user_id)
    if not user:
        # If user not found, return filter that matches nothing
        return {"user_id": "__NONE__"}
    
    accessible_ids = await get_accessible_user_ids(user)
    
    # For regular users, return simple filter
    if len(accessible_ids) == 1 and accessible_ids[0] == user_id:
        return {"user_id": user_id}
    
    # For admins/managers, return $in filter
    return {"user_id": {"$in": accessible_ids}}

async def verify_user_access(requesting_user_id: str, target_user_id: str) -> bool:
    """
    Verify that requesting_user can access data for target_user.
    Returns True if access is allowed, False otherwise.
    """
    user = await get_user_by_id(requesting_user_id)
    if not user:
        return False
    
    accessible_ids = await get_accessible_user_ids(user)
    return target_user_id in accessible_ids

async def increment_user_stat(user_id: str, stat_name: str, amount: int = 1):
    """Increment a user's stat for leaderboard tracking"""
    await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$inc": {f"stats.{stat_name}": amount}}
    )

# ============= AUTH ENDPOINTS =============
@api_router.post("/auth/signup", response_model=User)
async def signup(user_data: UserCreate):
    """Register a new user"""
    # Check if user exists
    existing = await db.users.find_one({"email": user_data.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Generate MVPLine number (mock)
    mvpline_number = f"+1555{random.randint(1000000, 9999999)}"
    
    user_dict = user_data.dict()
    user_dict['mvpline_number'] = mvpline_number
    user_dict['created_at'] = datetime.utcnow()
    user_dict['updated_at'] = datetime.utcnow()
    
    # Add default role and stats if not provided
    if 'role' not in user_dict:
        user_dict['role'] = 'user'
    if 'stats' not in user_dict:
        user_dict['stats'] = {
            "contacts_added": 0,
            "messages_sent": 0,
            "calls_made": 0,
            "deals_closed": 0
        }
    user_dict['leaderboard_visible'] = False
    user_dict['compare_scope'] = 'state'
    
    result = await db.users.insert_one(user_dict)
    user_dict['_id'] = str(result.inserted_id)
    
    return user_dict

@api_router.post("/auth/login")
async def login(credentials: dict):
    """Login user"""
    email = credentials.get('email')
    password = credentials.get('password')
    
    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password required")
        
    user = await db.users.find_one({"email": email})
    if not user or user.get('password') != password:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    user['_id'] = str(user['_id'])
    return {"user": user, "token": f"mock_token_{user['_id']}"}

@api_router.post("/auth/forgot-password")
async def forgot_password(data: dict):
    """Request password reset - generates a reset token"""
    email = data.get('email')
    
    if not email:
        raise HTTPException(status_code=400, detail="Email is required")
    
    user = await db.users.find_one({"email": email})
    if not user:
        # Don't reveal if user exists
        return {"message": "If an account with that email exists, a reset code has been sent."}
    
    # Generate a 6-digit reset code
    reset_code = str(random.randint(100000, 999999))
    expiry = datetime.utcnow() + timedelta(hours=1)
    
    # Store the reset token
    await db.password_resets.update_one(
        {"email": email},
        {"$set": {
            "email": email,
            "code": reset_code,
            "expires_at": expiry,
            "created_at": datetime.utcnow()
        }},
        upsert=True
    )
    
    # In production, send email here
    logger.info(f"[MOCK EMAIL] Password reset code for {email}: {reset_code}")
    
    return {
        "message": "If an account with that email exists, a reset code has been sent.",
        # In dev mode, return the code for testing (remove in production)
        "dev_code": reset_code
    }

@api_router.post("/auth/verify-reset-code")
async def verify_reset_code(data: dict):
    """Verify the reset code is valid"""
    email = data.get('email')
    code = data.get('code')
    
    if not email or not code:
        raise HTTPException(status_code=400, detail="Email and code are required")
    
    reset_record = await db.password_resets.find_one({"email": email, "code": code})
    
    if not reset_record:
        raise HTTPException(status_code=400, detail="Invalid or expired reset code")
    
    if reset_record.get('expires_at') and reset_record['expires_at'] < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Reset code has expired")
    
    return {"message": "Code verified", "valid": True}

@api_router.post("/auth/reset-password")
async def reset_password(data: dict):
    """Reset password using the verified code"""
    email = data.get('email')
    code = data.get('code')
    new_password = data.get('new_password')
    
    if not email or not code or not new_password:
        raise HTTPException(status_code=400, detail="Email, code, and new password are required")
    
    if len(new_password) < 4:
        raise HTTPException(status_code=400, detail="Password must be at least 4 characters")
    
    # Verify code is still valid
    reset_record = await db.password_resets.find_one({"email": email, "code": code})
    
    if not reset_record:
        raise HTTPException(status_code=400, detail="Invalid or expired reset code")
    
    if reset_record.get('expires_at') and reset_record['expires_at'] < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Reset code has expired")
    
    # Update the password
    result = await db.users.update_one(
        {"email": email},
        {"$set": {"password": new_password, "updated_at": datetime.utcnow()}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Delete the reset record
    await db.password_resets.delete_one({"email": email})
    
    return {"message": "Password reset successfully"}

# ============= ONBOARDING ENDPOINTS =============
@api_router.post("/onboarding/profile/{user_id}")
async def save_persona(user_id: str, persona: UserPersona):
    """Save user persona from onboarding"""
    try:
        from bson import ObjectId
        # Try with ObjectId first, then with string
        result = await db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {
                "persona": persona.dict(),
                "onboarding_complete": True,
                "updated_at": datetime.utcnow()
            }}
        )
        if result.matched_count == 0:
            result = await db.users.update_one(
                {"_id": user_id},
                {"$set": {
                    "persona": persona.dict(),
                    "onboarding_complete": True,
                    "updated_at": datetime.utcnow()
                }}
            )
    except:
        # If ObjectId conversion fails, try with string
        result = await db.users.update_one(
            {"_id": user_id},
            {"$set": {
                "persona": persona.dict(),
                "onboarding_complete": True,
                "updated_at": datetime.utcnow()
            }}
        )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {"message": "Profile updated successfully"}

@api_router.get("/onboarding/profile/{user_id}")
async def get_persona(user_id: str):
    """Get user persona"""
    try:
        from bson import ObjectId
        # Try with ObjectId first, then with string
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            user = await db.users.find_one({"_id": user_id})
    except:
        # If ObjectId conversion fails, try with string
        user = await db.users.find_one({"_id": user_id})
        
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return user.get('persona', {})

# ============= CONTACT ENDPOINTS =============
@api_router.post("/contacts/{user_id}", response_model=Contact)
async def create_contact(user_id: str, contact_data: ContactCreate):
    """Create a new contact"""
    contact_dict = contact_data.dict()
    contact_dict['user_id'] = user_id
    contact_dict['created_at'] = datetime.utcnow()
    contact_dict['updated_at'] = datetime.utcnow()
    
    result = await db.contacts.insert_one(contact_dict)
    contact_dict['_id'] = result.inserted_id
    
    # Track stat for leaderboard
    await increment_user_stat(user_id, "contacts_added")
    
    return Contact(**contact_dict)

@api_router.get("/contacts/{user_id}", response_model=List[Contact])
async def get_contacts(user_id: str, search: Optional[str] = None):
    """Get all contacts accessible to a user based on their role"""
    # Get role-based data filter
    base_filter = await get_data_filter(user_id)
    
    # Build the final query
    if search:
        query = {
            "$and": [
                base_filter,
                {"$or": [
                    {"first_name": {"$regex": search, "$options": "i"}},
                    {"last_name": {"$regex": search, "$options": "i"}},
                    {"phone": {"$regex": search, "$options": "i"}}
                ]}
            ]
        }
    else:
        query = base_filter
    
    contacts = await db.contacts.find(query).to_list(1000)
    return [Contact(**{**contact, "_id": str(contact["_id"])}) for contact in contacts]

@api_router.get("/contacts/{user_id}/{contact_id}", response_model=Contact)
async def get_contact(user_id: str, contact_id: str):
    """Get a specific contact with role-based access check"""
    # Get role-based data filter
    base_filter = await get_data_filter(user_id)
    
    try:
        contact = await db.contacts.find_one({
            "$and": [
                {"_id": ObjectId(contact_id)},
                base_filter
            ]
        })
    except:
        contact = await db.contacts.find_one({
            "$and": [
                {"_id": contact_id},
                base_filter
            ]
        })
    
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    contact['_id'] = str(contact['_id'])
    return Contact(**contact)

@api_router.put("/contacts/{user_id}/{contact_id}")
async def update_contact(user_id: str, contact_id: str, contact_data: ContactCreate):
    """Update a contact with role-based access check"""
    # Get role-based data filter
    base_filter = await get_data_filter(user_id)
    
    update_dict = contact_data.dict()
    update_dict['updated_at'] = datetime.utcnow()
    
    # If setting a referrer, update the referrer's count
    if contact_data.referred_by:
        # Increment referrer's referral_count (only if accessible)
        await db.contacts.update_one(
            {"$and": [{"_id": contact_data.referred_by}, base_filter]},
            {"$inc": {"referral_count": 1}}
        )
    
    try:
        result = await db.contacts.update_one(
            {"$and": [{"_id": ObjectId(contact_id)}, base_filter]},
            {"$set": update_dict}
        )
    except:
        result = await db.contacts.update_one(
            {"$and": [{"_id": contact_id}, base_filter]},
            {"$set": update_dict}
        )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    return {"message": "Contact updated successfully"}

@api_router.get("/contacts/{user_id}/{contact_id}/referrals")
async def get_contact_referrals(user_id: str, contact_id: str):
    """Get all contacts referred by this contact with role-based access"""
    # Get role-based data filter
    base_filter = await get_data_filter(user_id)
    
    referrals = await db.contacts.find({
        "$and": [
            base_filter,
            {"referred_by": contact_id}
        ]
    }).to_list(1000)
    
    return [{
        "_id": str(r["_id"]),
        "first_name": r.get("first_name", ""),
        "last_name": r.get("last_name", ""),
        "phone": r.get("phone", ""),
        "vehicle": r.get("vehicle", ""),
        "tags": r.get("tags", []),
        "created_at": r.get("created_at")
    } for r in referrals]

@api_router.post("/contacts/{user_id}/import")
async def import_contacts(user_id: str, contacts: List[ContactCreate]):
    """Bulk import contacts from CSV"""
    imported = []
    for contact_data in contacts:
        # Check for duplicates by phone (only check for this user's contacts)
        existing = await db.contacts.find_one({
            "user_id": user_id,
            "phone": contact_data.phone
        })
        
        if existing:
            continue
        
        contact_dict = contact_data.dict()
        contact_dict['user_id'] = user_id
        contact_dict['source'] = 'csv'
        contact_dict['created_at'] = datetime.utcnow()
        contact_dict['updated_at'] = datetime.utcnow()
        
        result = await db.contacts.insert_one(contact_dict)
        contact_dict['_id'] = result.inserted_id
        imported.append(contact_dict)
    
    return {
        "imported": len(imported),
        "skipped": len(contacts) - len(imported)
    }

# ============= CONVERSATION & MESSAGE ENDPOINTS =============
@api_router.get("/messages/conversations/{user_id}")
async def get_conversations(user_id: str):
    """Get all conversations accessible to a user based on their role"""
    # Get role-based data filter
    base_filter = await get_data_filter(user_id)
    
    conversations = await db.conversations.find(base_filter).sort("last_message_at", -1).to_list(1000)
    
    result = []
    for conv in conversations:
        conv['_id'] = str(conv['_id'])
        
        # Get contact info
        try:
            contact = await db.contacts.find_one({"_id": ObjectId(conv['contact_id'])})
        except:
            contact = await db.contacts.find_one({"_id": conv['contact_id']})
        
        if contact:
            conv['contact'] = {
                "id": str(contact['_id']),
                "name": f"{contact['first_name']} {contact.get('last_name', '')}".strip(),
                "phone": contact['phone']
            }
        
        # Get last message
        last_msg = await db.messages.find_one(
            {"conversation_id": str(conv['_id'])},
            sort=[("timestamp", -1)]
        )
        if last_msg:
            conv['last_message'] = {
                "content": last_msg['content'],
                "timestamp": last_msg['timestamp'],
                "sender": last_msg['sender']
            }
        
        result.append(conv)
    
    return result

@api_router.get("/messages/thread/{conversation_id}")
async def get_message_thread(conversation_id: str):
    """Get all messages in a conversation"""
    messages = await db.messages.find(
        {"conversation_id": conversation_id}
    ).sort("timestamp", 1).to_list(1000)
    
    # Convert ObjectId to string for all messages
    result = []
    for msg in messages:
        msg['_id'] = str(msg['_id'])
        result.append(msg)
    
    return result

@api_router.post("/messages/send/{user_id}")
async def send_message(user_id: str, message_data: MessageCreate):
    """Send a message"""
    # Get or create conversation
    conversation = await db.conversations.find_one({
        "user_id": user_id,
        "contact_id": message_data.conversation_id  # This should be contact_id in the request
    })
    
    if not conversation:
        # Create new conversation
        conv_dict = {
            "user_id": user_id,
            "contact_id": message_data.conversation_id,
            "status": "active",
            "ai_enabled": True,
            "ai_mode": "draft_only",
            "last_message_at": datetime.utcnow(),
            "created_at": datetime.utcnow()
        }
        result = await db.conversations.insert_one(conv_dict)
        conversation_id = str(result.inserted_id)
    else:
        conversation_id = str(conversation['_id'])
        # Update last message time
        await db.conversations.update_one(
            {"_id": conversation['_id']},
            {"$set": {"last_message_at": datetime.utcnow()}}
        )
    
    # Save message
    msg_dict = {
        "conversation_id": conversation_id,
        "sender": "user",
        "content": message_data.content,
        "media_url": message_data.media_url,
        "timestamp": datetime.utcnow()
    }
    
    result = await db.messages.insert_one(msg_dict)
    msg_dict['_id'] = result.inserted_id
    
    # Track stat for leaderboard
    await increment_user_stat(user_id, "messages_sent")
    
    # Mock: Send via Twilio here in production
    logger.info(f"[MOCK] Sending SMS: {message_data.content}")
    
    return {"message": "Message sent", "id": str(result.inserted_id)}

@api_router.post("/messages/ai-suggest/{conversation_id}")
async def ai_suggest_reply(conversation_id: str):
    """Get AI-generated reply suggestion"""
    # Mock AI suggestion for now
    suggestions = [
        "Thanks for reaching out! I'll get back to you shortly.",
        "Great question! Let me check on that for you.",
        "I appreciate you following up. When's a good time to chat?",
        "Absolutely! I'd love to help you with that."
    ]
    
    return {
        "suggestion": random.choice(suggestions),
        "confidence": 0.85
    }

# ============= CALL ENDPOINTS =============
@api_router.post("/calls/{user_id}", response_model=Call)
async def create_call_log(user_id: str, call_data: CallCreate):
    """Log a call"""
    call_dict = call_data.dict()
    call_dict['user_id'] = user_id
    call_dict['timestamp'] = datetime.utcnow()
    
    result = await db.calls.insert_one(call_dict)
    call_dict['_id'] = result.inserted_id
    
    # If missed call, send auto-text
    if call_data.type == "missed":
        try:
            contact = await db.contacts.find_one({"_id": ObjectId(call_data.contact_id)})
        except:
            contact = await db.contacts.find_one({"_id": call_data.contact_id})
        
        if contact:
            logger.info(f"[MOCK] Auto-text sent to {contact['first_name']}: Hey, I just missed your call!")
            call_dict['auto_text_sent'] = True
            await db.calls.update_one(
                {"_id": result.inserted_id},
                {"$set": {"auto_text_sent": True}}
            )
    
    return Call(**call_dict)

@api_router.get("/calls/{user_id}")
async def get_call_logs(user_id: str, call_type: Optional[str] = None):
    """Get call logs with role-based access"""
    # Get role-based data filter
    base_filter = await get_data_filter(user_id)
    
    if call_type:
        query = {"$and": [base_filter, {"type": call_type}]}
    else:
        query = base_filter
    
    calls = await db.calls.find(query).sort("timestamp", -1).to_list(1000)
    
    # Enrich with contact info
    result = []
    for call in calls:
        call['_id'] = str(call['_id'])
        try:
            contact = await db.contacts.find_one({"_id": ObjectId(call['contact_id'])})
        except:
            contact = await db.contacts.find_one({"_id": call['contact_id']})
        
        if contact:
            call['contact'] = {
                "name": f"{contact['first_name']} {contact.get('last_name', '')}".strip(),
                "phone": contact['phone']
            }
        result.append(call)
    
    return result

# ============= CAMPAIGN ENDPOINTS =============
def calculate_next_send_date(step: dict, from_date: datetime = None) -> datetime:
    """Calculate when the next message should be sent based on delay"""
    if from_date is None:
        from_date = datetime.utcnow()
    
    delay_days = step.get('delay_days', 0)
    delay_months = step.get('delay_months', 0)
    
    # Add months first
    if delay_months > 0:
        from_date = from_date + timedelta(days=delay_months * 30)
    
    # Then add days
    if delay_days > 0:
        from_date = from_date + timedelta(days=delay_days)
    
    return from_date

def personalize_message(template: str, contact: dict) -> str:
    """Replace placeholders in message template"""
    message = template
    message = message.replace('{name}', contact.get('first_name') or 'there')
    message = message.replace('{first_name}', contact.get('first_name') or '')
    message = message.replace('{last_name}', contact.get('last_name') or '')
    message = message.replace('{vehicle}', contact.get('vehicle') or 'vehicle')
    message = message.replace('{phone}', contact.get('phone') or '')
    return message

# ============= CAMPAIGN SCHEDULER ENDPOINTS (must be before {campaign_id} routes) =============
@api_router.post("/campaigns/scheduler/process")
async def process_pending_messages():
    """Process all pending campaign messages - should be called by a cron job or scheduler"""
    now = datetime.utcnow()
    
    # Find all enrollments with pending messages
    pending = await db.campaign_enrollments.find({
        "status": "active",
        "next_send_at": {"$lte": now}
    }).to_list(1000)
    
    results = {
        "processed": 0,
        "sent": 0,
        "completed": 0,
        "errors": 0,
        "messages": []
    }
    
    for enrollment in pending:
        results["processed"] += 1
        
        try:
            # Get campaign
            campaign = await db.campaigns.find_one({"_id": ObjectId(enrollment["campaign_id"])})
            if not campaign or not campaign.get('active', False):
                # Campaign was deleted or deactivated
                await db.campaign_enrollments.update_one(
                    {"_id": enrollment["_id"]},
                    {"$set": {"status": "cancelled"}}
                )
                continue
            
            # Get contact
            contact = await db.contacts.find_one({"_id": ObjectId(enrollment["contact_id"])})
            if not contact:
                await db.campaign_enrollments.update_one(
                    {"_id": enrollment["_id"]},
                    {"$set": {"status": "cancelled"}}
                )
                continue
            
            # Get current step
            sequences = campaign.get('sequences', [])
            current_step_num = enrollment.get('current_step', 1)
            
            if current_step_num > len(sequences):
                # Campaign complete
                await db.campaign_enrollments.update_one(
                    {"_id": enrollment["_id"]},
                    {"$set": {"status": "completed", "next_send_at": None}}
                )
                results["completed"] += 1
                continue
            
            # Get the message template for current step
            current_step = sequences[current_step_num - 1]
            message_template = current_step.get('message_template', '')
            
            # Personalize the message
            personalized_message = personalize_message(message_template, contact)
            
            # Send the message (mock - in production this would use Twilio)
            logger.info(f"[CAMPAIGN MESSAGE] To: {contact.get('phone')} | Message: {personalized_message[:100]}...")
            
            # Record the sent message
            sent_record = {
                "step": current_step_num,
                "message": personalized_message,
                "sent_at": now.isoformat(),
                "status": "sent"
            }
            
            # Calculate next send date
            next_step_num = current_step_num + 1
            next_send_at = None
            
            if next_step_num <= len(sequences):
                next_step = sequences[next_step_num - 1]
                next_send_at = calculate_next_send_date(next_step, now)
                new_status = "active"
            else:
                new_status = "completed"
                results["completed"] += 1
            
            # Update enrollment
            await db.campaign_enrollments.update_one(
                {"_id": enrollment["_id"]},
                {
                    "$set": {
                        "current_step": next_step_num,
                        "status": new_status,
                        "next_send_at": next_send_at
                    },
                    "$push": {
                        "messages_sent": sent_record
                    }
                }
            )
            
            results["sent"] += 1
            results["messages"].append({
                "contact_id": str(enrollment["contact_id"]),
                "contact_phone": contact.get('phone'),
                "message_preview": personalized_message[:50] + "...",
                "step": current_step_num
            })
            
        except Exception as e:
            logger.error(f"Error processing enrollment {enrollment['_id']}: {str(e)}")
            results["errors"] += 1
    
    logger.info(f"Campaign scheduler: processed={results['processed']}, sent={results['sent']}, completed={results['completed']}, errors={results['errors']}")
    
    return results

@api_router.get("/campaigns/scheduler/pending")
async def get_pending_messages():
    """Get count of pending campaign messages"""
    now = datetime.utcnow()
    
    pending_count = await db.campaign_enrollments.count_documents({
        "status": "active",
        "next_send_at": {"$lte": now}
    })
    
    upcoming_count = await db.campaign_enrollments.count_documents({
        "status": "active",
        "next_send_at": {"$gt": now}
    })
    
    return {
        "pending": pending_count,
        "upcoming": upcoming_count,
        "timestamp": now.isoformat()
    }

@api_router.post("/campaigns/{user_id}", response_model=Campaign)
async def create_campaign(user_id: str, campaign_data: CampaignCreate):
    """Create a nurture campaign"""
    campaign_dict = campaign_data.dict()
    campaign_dict['user_id'] = user_id
    campaign_dict['created_at'] = datetime.utcnow()
    
    result = await db.campaigns.insert_one(campaign_dict)
    campaign_dict['_id'] = result.inserted_id
    
    logger.info(f"Campaign created: {campaign_dict['name']} with {len(campaign_dict.get('sequences', []))} steps")
    
    return Campaign(**campaign_dict)

@api_router.get("/campaigns/{user_id}", response_model=List[Campaign])
async def get_campaigns(user_id: str):
    """Get all campaigns with role-based access"""
    # Get role-based data filter
    base_filter = await get_data_filter(user_id)
    
    campaigns = await db.campaigns.find(base_filter).to_list(1000)
    return [Campaign(**{**camp, "_id": str(camp["_id"])}) for camp in campaigns]

@api_router.get("/campaigns/{user_id}/{campaign_id}")
async def get_campaign(user_id: str, campaign_id: str):
    """Get a specific campaign with role-based access check"""
    # Get role-based data filter
    base_filter = await get_data_filter(user_id)
    
    campaign = await db.campaigns.find_one({"$and": [{"_id": ObjectId(campaign_id)}, base_filter]})
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    campaign['_id'] = str(campaign['_id'])
    return campaign

@api_router.put("/campaigns/{user_id}/{campaign_id}")
async def update_campaign(user_id: str, campaign_id: str, update_data: dict):
    """Update a campaign with role-based access check"""
    # Get role-based data filter
    base_filter = await get_data_filter(user_id)
    
    allowed_fields = ['name', 'type', 'trigger_tag', 'segment_tags', 'sequences', 'send_time', 'active']
    update_dict = {k: v for k, v in update_data.items() if k in allowed_fields}
    
    result = await db.campaigns.update_one(
        {"$and": [{"_id": ObjectId(campaign_id)}, base_filter]},
        {"$set": update_dict}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    return {"message": "Campaign updated successfully"}

@api_router.delete("/campaigns/{user_id}/{campaign_id}")
async def delete_campaign(user_id: str, campaign_id: str):
    """Delete a campaign and its enrollments with role-based access check"""
    # Get role-based data filter
    base_filter = await get_data_filter(user_id)
    
    # Delete campaign
    result = await db.campaigns.delete_one({"$and": [{"_id": ObjectId(campaign_id)}, base_filter]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Delete all enrollments for this campaign (campaign belongs to user, so enrollments do too)
    await db.campaign_enrollments.delete_many({"campaign_id": campaign_id})
    
    return {"message": "Campaign deleted successfully"}

# ============= CAMPAIGN ENROLLMENT ENDPOINTS =============
@api_router.post("/campaigns/{user_id}/{campaign_id}/enroll/{contact_id}")
async def enroll_contact_in_campaign(user_id: str, campaign_id: str, contact_id: str):
    """Enroll a contact in a campaign with role-based access check"""
    # Get role-based data filter
    base_filter = await get_data_filter(user_id)
    
    # Get campaign (with role-based access)
    campaign = await db.campaigns.find_one({"$and": [{"_id": ObjectId(campaign_id)}, base_filter]})
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    if not campaign.get('active', False):
        raise HTTPException(status_code=400, detail="Campaign is not active")
    
    # Get contact (with role-based access)
    contact = await db.contacts.find_one({"$and": [{"_id": ObjectId(contact_id)}, base_filter]})
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    # Check if already enrolled
    existing = await db.campaign_enrollments.find_one({
        "campaign_id": campaign_id,
        "contact_id": contact_id,
        "status": "active"
    })
    if existing:
        raise HTTPException(status_code=400, detail="Contact is already enrolled in this campaign")
    
    # Calculate when to send first message
    sequences = campaign.get('sequences', [])
    first_step = sequences[0] if sequences else None
    
    if first_step:
        next_send = calculate_next_send_date(first_step)
    else:
        next_send = datetime.utcnow()
    
    # Create enrollment
    enrollment = {
        "user_id": user_id,
        "campaign_id": campaign_id,
        "contact_id": contact_id,
        "contact_name": f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip(),
        "contact_phone": contact.get('phone', ''),
        "current_step": 1,
        "status": "active",
        "enrolled_at": datetime.utcnow(),
        "next_send_at": next_send,
        "messages_sent": []
    }
    
    result = await db.campaign_enrollments.insert_one(enrollment)
    enrollment['_id'] = str(result.inserted_id)
    
    logger.info(f"Contact {contact_id} enrolled in campaign {campaign_id}, first message at {next_send}")
    
    return enrollment

@api_router.get("/campaigns/{user_id}/{campaign_id}/enrollments")
async def get_campaign_enrollments(user_id: str, campaign_id: str, status: str = None):
    """Get all enrollments for a campaign with role-based access"""
    # Get role-based data filter
    base_filter = await get_data_filter(user_id)
    
    # First verify user has access to this campaign
    campaign = await db.campaigns.find_one({"$and": [{"_id": ObjectId(campaign_id)}, base_filter]})
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Get enrollments for this campaign (with role-based user_id filter)
    query = {"$and": [{"campaign_id": campaign_id}, base_filter]}
    if status:
        query["$and"].append({"status": status})
    
    enrollments = await db.campaign_enrollments.find(query).to_list(1000)
    return [{**e, "_id": str(e["_id"])} for e in enrollments]

@api_router.delete("/campaigns/{user_id}/{campaign_id}/enrollments/{enrollment_id}")
async def cancel_enrollment(user_id: str, campaign_id: str, enrollment_id: str):
    """Cancel a campaign enrollment with role-based access check"""
    # Get role-based data filter
    base_filter = await get_data_filter(user_id)
    
    result = await db.campaign_enrollments.update_one(
        {"$and": [{"_id": ObjectId(enrollment_id)}, base_filter]},
        {"$set": {"status": "cancelled"}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Enrollment not found")
    
    return {"message": "Enrollment cancelled"}

# Auto-enroll contacts when they receive a trigger tag
async def auto_enroll_contact_by_tag(user_id: str, contact_id: str, tag: str):
    """Auto-enroll a contact in campaigns when they get a specific tag"""
    # Find campaigns with this trigger tag
    campaigns = await db.campaigns.find({
        "user_id": user_id,
        "trigger_tag": tag,
        "active": True
    }).to_list(100)
    
    enrolled_campaigns = []
    
    for campaign in campaigns:
        campaign_id = str(campaign['_id'])
        
        # Check if already enrolled
        existing = await db.campaign_enrollments.find_one({
            "campaign_id": campaign_id,
            "contact_id": contact_id,
            "status": {"$in": ["active", "completed"]}
        })
        
        if not existing:
            try:
                # Get contact
                contact = await db.contacts.find_one({"_id": ObjectId(contact_id)})
                if not contact:
                    continue
                
                # Calculate when to send first message
                sequences = campaign.get('sequences', [])
                first_step = sequences[0] if sequences else None
                
                if first_step:
                    next_send = calculate_next_send_date(first_step)
                else:
                    next_send = datetime.utcnow()
                
                # Create enrollment
                enrollment = {
                    "user_id": user_id,
                    "campaign_id": campaign_id,
                    "contact_id": contact_id,
                    "contact_name": f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip(),
                    "contact_phone": contact.get('phone', ''),
                    "current_step": 1,
                    "status": "active",
                    "enrolled_at": datetime.utcnow(),
                    "next_send_at": next_send,
                    "messages_sent": []
                }
                
                await db.campaign_enrollments.insert_one(enrollment)
                enrolled_campaigns.append(campaign['name'])
                logger.info(f"Auto-enrolled contact {contact_id} in campaign '{campaign['name']}' via tag '{tag}'")
                
            except Exception as e:
                logger.error(f"Failed to auto-enroll contact {contact_id} in campaign {campaign_id}: {str(e)}")
    
    return enrolled_campaigns

# ============= TASK ENDPOINTS =============
@api_router.post("/tasks/{user_id}", response_model=Task)
async def create_task(user_id: str, task_data: TaskCreate):
    """Create a task/reminder"""
    task_dict = task_data.dict()
    task_dict['user_id'] = user_id
    task_dict['created_at'] = datetime.utcnow()
    
    result = await db.tasks.insert_one(task_dict)
    task_dict['_id'] = result.inserted_id
    
    return Task(**task_dict)

@api_router.get("/tasks/{user_id}")
async def get_tasks(user_id: str, completed: Optional[bool] = None):
    """Get tasks with role-based access"""
    # Get role-based data filter
    base_filter = await get_data_filter(user_id)
    
    if completed is not None:
        query = {"$and": [base_filter, {"completed": completed}]}
    else:
        query = base_filter
    
    tasks = await db.tasks.find(query).sort("due_date", 1).to_list(1000)
    return [Task(**{**task, "_id": str(task["_id"])}) for task in tasks]

@api_router.put("/tasks/{user_id}/{task_id}")
async def update_task(user_id: str, task_id: str, task_data: dict):
    """Update a task with role-based access check"""
    # Get role-based data filter
    base_filter = await get_data_filter(user_id)
    
    # Only allow updating specific fields
    allowed_fields = ["completed", "title", "description", "due_date", "type", "priority"]
    update_dict = {k: v for k, v in task_data.items() if k in allowed_fields}
    update_dict["updated_at"] = datetime.utcnow()
    
    try:
        result = await db.tasks.update_one(
            {"$and": [{"_id": ObjectId(task_id)}, base_filter]},
            {"$set": update_dict}
        )
    except:
        result = await db.tasks.update_one(
            {"$and": [{"_id": task_id}, base_filter]},
            {"$set": update_dict}
        )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return {"message": "Task updated successfully"}

@api_router.delete("/tasks/{user_id}/{task_id}")
async def delete_task(user_id: str, task_id: str):
    """Delete a task with role-based access check"""
    # Get role-based data filter
    base_filter = await get_data_filter(user_id)
    
    try:
        result = await db.tasks.delete_one(
            {"$and": [{"_id": ObjectId(task_id)}, base_filter]}
        )
    except:
        result = await db.tasks.delete_one(
            {"$and": [{"_id": task_id}, base_filter]}
        )
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return {"message": "Task deleted successfully"}

# ============= AI ENDPOINTS =============
@api_router.post("/ai/generate-message")
async def generate_ai_message(
    user_id: str,
    context: str,
    intent: str = "follow_up"
):
    """Generate AI message using OpenAI (mocked for now)"""
    # In production, this would use OpenAI with user's persona
    
    templates = {
        "follow_up": "Hey! Just wanted to check in and see how everything's going. Let me know if you need anything!",
        "birthday": "Happy birthday! 🎉 Hope you have an amazing day!",
        "check_in": "Hey there! Just thinking about you and wanted to say hi. How have you been?",
        "missed_call": "Hey, I just missed your call — I'll ring you back shortly. Anything specific you needed?"
    }
    
    return {
        "generated_message": templates.get(intent, templates["follow_up"]),
        "intent": intent
    }

@api_router.post("/ai/detect-intent")
async def detect_intent(data: dict):
    """Detect intent in a message (mocked)"""
    message = data.get('message', '')
    message_lower = message.lower()
    
    intents = {
        "buying_intent": ["buy", "purchase", "interested in", "want to get"],
        "price_question": ["price", "cost", "how much", "$"],
        "appointment": ["meet", "appointment", "schedule", "come in"],
        "urgent": ["asap", "urgent", "immediately", "now"],
        "angry": ["angry", "upset", "frustrated", "terrible"]
    }
    
    detected = []
    for intent, keywords in intents.items():
        if any(kw in message_lower for kw in keywords):
            detected.append(intent)
    
    return {
        "intents": detected,
        "escalate": "urgent" in detected or "angry" in detected
    }

# ============= ADMIN ENDPOINTS =============

def generate_slug(name: str) -> str:
    """Generate URL-friendly slug from name"""
    import re
    slug = name.lower()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    return slug.strip('-')

async def check_admin_access(user_id: str, required_role: str = "org_admin"):
    """Check if user has required admin access"""
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    role_hierarchy = ["user", "store_manager", "org_admin", "super_admin"]
    user_role = user.get("role", "user")
    
    if role_hierarchy.index(user_role) < role_hierarchy.index(required_role):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    return user

# ----- Organization Management -----
@api_router.post("/admin/organizations")
async def create_organization(org_data: OrganizationCreate, admin_user_id: str = None):
    """Create a new organization"""
    # Generate slug
    slug = generate_slug(org_data.name)
    
    # Check if slug exists
    existing = await db.organizations.find_one({"slug": slug})
    if existing:
        slug = f"{slug}-{random.randint(1000, 9999)}"
    
    org_dict = org_data.dict()
    org_dict['slug'] = slug
    org_dict['created_at'] = datetime.utcnow()
    org_dict['updated_at'] = datetime.utcnow()
    
    result = await db.organizations.insert_one(org_dict)
    org_dict['_id'] = str(result.inserted_id)
    
    logger.info(f"Organization created: {org_dict['name']} ({org_dict['_id']})")
    
    return org_dict

@api_router.get("/admin/organizations")
async def list_organizations(admin_user_id: str = None):
    """List all organizations (super admin only)"""
    # In production, verify super_admin role
    orgs = await db.organizations.find({}).to_list(1000)
    return [{**org, "_id": str(org["_id"])} for org in orgs]

@api_router.get("/admin/organizations/{org_id}")
async def get_organization(org_id: str):
    """Get organization details"""
    org = await db.organizations.find_one({"_id": ObjectId(org_id)})
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    org['_id'] = str(org['_id'])
    
    # Get store count
    store_count = await db.stores.count_documents({"organization_id": org_id})
    org['store_count'] = store_count
    
    # Get user count
    user_count = await db.users.count_documents({"organization_id": org_id})
    org['user_count'] = user_count
    
    return org

@api_router.put("/admin/organizations/{org_id}")
async def update_organization(org_id: str, update_data: dict):
    """Update organization details"""
    allowed_fields = ['name', 'admin_email', 'admin_phone', 'address', 'city', 'state', 'country',
                      'twilio_account_sid', 'twilio_auth_token', 'ten_dlc_status', 'max_stores', 
                      'max_users_per_store', 'features', 'active']
    
    update_dict = {k: v for k, v in update_data.items() if k in allowed_fields}
    update_dict['updated_at'] = datetime.utcnow()
    
    result = await db.organizations.update_one(
        {"_id": ObjectId(org_id)},
        {"$set": update_dict}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    return {"message": "Organization updated successfully"}

@api_router.delete("/admin/organizations/{org_id}")
async def delete_organization(org_id: str):
    """Delete an organization and all related data"""
    # Delete all stores
    await db.stores.delete_many({"organization_id": org_id})
    
    # Update all users to remove org association
    await db.users.update_many(
        {"organization_id": org_id},
        {"$set": {"organization_id": None, "store_id": None, "role": "user"}}
    )
    
    # Delete organization
    result = await db.organizations.delete_one({"_id": ObjectId(org_id)})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    return {"message": "Organization deleted successfully"}

# ----- Store Management -----
@api_router.post("/admin/stores")
async def create_store(store_data: StoreCreate):
    """Create a new store under an organization"""
    # Verify organization exists
    org = await db.organizations.find_one({"_id": ObjectId(store_data.organization_id)})
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    # Check store limit
    store_count = await db.stores.count_documents({"organization_id": store_data.organization_id})
    if store_count >= org.get('max_stores', 10):
        raise HTTPException(status_code=400, detail="Organization has reached maximum store limit")
    
    # Generate slug
    slug = generate_slug(store_data.name)
    existing = await db.stores.find_one({"organization_id": store_data.organization_id, "slug": slug})
    if existing:
        slug = f"{slug}-{random.randint(1000, 9999)}"
    
    store_dict = store_data.dict()
    store_dict['slug'] = slug
    store_dict['created_at'] = datetime.utcnow()
    store_dict['updated_at'] = datetime.utcnow()
    
    result = await db.stores.insert_one(store_dict)
    store_dict['_id'] = str(result.inserted_id)
    
    logger.info(f"Store created: {store_dict['name']} under org {store_data.organization_id}")
    
    return store_dict

@api_router.get("/admin/organizations/{org_id}/stores")
async def list_stores(org_id: str):
    """List all stores for an organization"""
    stores = await db.stores.find({"organization_id": org_id}).to_list(1000)
    
    # Add user counts
    result = []
    for store in stores:
        store['_id'] = str(store['_id'])
        store['user_count'] = await db.users.count_documents({"store_id": store['_id']})
        result.append(store)
    
    return result

@api_router.get("/admin/stores/{store_id}")
async def get_store(store_id: str):
    """Get store details"""
    store = await db.stores.find_one({"_id": ObjectId(store_id)})
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    
    store['_id'] = str(store['_id'])
    store['user_count'] = await db.users.count_documents({"store_id": store_id})
    
    return store

@api_router.put("/admin/stores/{store_id}")
async def update_store(store_id: str, update_data: dict):
    """Update store details"""
    allowed_fields = ['name', 'phone', 'address', 'city', 'state', 'country', 
                      'twilio_phone_number', 'max_users', 'active']
    
    update_dict = {k: v for k, v in update_data.items() if k in allowed_fields}
    update_dict['updated_at'] = datetime.utcnow()
    
    result = await db.stores.update_one(
        {"_id": ObjectId(store_id)},
        {"$set": update_dict}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Store not found")
    
    return {"message": "Store updated successfully"}

@api_router.delete("/admin/stores/{store_id}")
async def delete_store(store_id: str):
    """Delete a store"""
    # Update users to remove store association
    await db.users.update_many(
        {"store_id": store_id},
        {"$set": {"store_id": None}}
    )
    
    result = await db.stores.delete_one({"_id": ObjectId(store_id)})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Store not found")
    
    return {"message": "Store deleted successfully"}

# ----- User Management (Admin) -----
@api_router.get("/admin/organizations/{org_id}/users")
async def list_org_users(org_id: str, store_id: str = None, role: str = None):
    """List all users in an organization"""
    query = {"organization_id": org_id}
    if store_id:
        query["store_id"] = store_id
    if role:
        query["role"] = role
    
    users = await db.users.find(query, {"password": 0}).to_list(1000)
    return [{**u, "_id": str(u["_id"])} for u in users]

@api_router.post("/admin/users")
async def create_admin_user(user_data: dict):
    """Create a user with specific role (admin function)"""
    # Check required fields
    if not user_data.get('email') or not user_data.get('password') or not user_data.get('name'):
        raise HTTPException(status_code=400, detail="Email, password, and name are required")
    
    # Check if email exists
    existing = await db.users.find_one({"email": user_data['email']})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Validate organization and store if provided
    if user_data.get('organization_id'):
        org = await db.organizations.find_one({"_id": ObjectId(user_data['organization_id'])})
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found")
    
    if user_data.get('store_id'):
        store = await db.stores.find_one({"_id": ObjectId(user_data['store_id'])})
        if not store:
            raise HTTPException(status_code=404, detail="Store not found")
    
    # Generate MVPLine number
    mvpline_number = f"+1555{random.randint(1000000, 9999999)}"
    
    user_dict = {
        "email": user_data['email'],
        "password": user_data['password'],  # Should hash in production
        "name": user_data['name'],
        "phone": user_data.get('phone', ''),
        "mode": user_data.get('mode', 'rep'),
        "organization_id": user_data.get('organization_id'),
        "store_id": user_data.get('store_id'),
        "role": user_data.get('role', 'user'),
        "mvpline_number": mvpline_number,
        "onboarding_complete": False,
        "leaderboard_visible": False,
        "compare_scope": "state",
        "stats": {
            "contacts_added": 0,
            "messages_sent": 0,
            "calls_made": 0,
            "deals_closed": 0
        },
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    result = await db.users.insert_one(user_dict)
    user_dict['_id'] = str(result.inserted_id)
    del user_dict['password']  # Don't return password
    
    logger.info(f"Admin created user: {user_dict['email']} with role {user_dict['role']}")
    
    return user_dict

@api_router.put("/admin/users/{user_id}")
async def update_admin_user(user_id: str, update_data: dict):
    """Update user details (admin function)"""
    allowed_fields = ['name', 'email', 'phone', 'role', 'organization_id', 'store_id', 
                      'leaderboard_visible', 'compare_scope', 'active']
    
    update_dict = {k: v for k, v in update_data.items() if k in allowed_fields}
    update_dict['updated_at'] = datetime.utcnow()
    
    # Handle password update separately
    if update_data.get('password'):
        update_dict['password'] = update_data['password']  # Should hash in production
    
    result = await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": update_dict}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {"message": "User updated successfully"}

@api_router.delete("/admin/users/{user_id}")
async def delete_admin_user(user_id: str):
    """Delete a user (admin function)"""
    result = await db.users.delete_one({"_id": ObjectId(user_id)})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Also delete user's data
    await db.contacts.delete_many({"user_id": user_id})
    await db.tasks.delete_many({"user_id": user_id})
    await db.campaigns.delete_many({"user_id": user_id})
    await db.conversations.delete_many({"user_id": user_id})
    
    return {"message": "User and related data deleted successfully"}

# ----- Admin Dashboard Stats -----
@api_router.get("/admin/stats")
async def get_admin_stats(org_id: str = None):
    """Get platform-wide or org-specific statistics"""
    if org_id:
        # Org-specific stats
        stores = await db.stores.count_documents({"organization_id": org_id})
        users = await db.users.count_documents({"organization_id": org_id})
        
        # Get all user IDs in this org
        org_users = await db.users.find({"organization_id": org_id}, {"_id": 1}).to_list(10000)
        user_ids = [str(u["_id"]) for u in org_users]
        
        contacts = await db.contacts.count_documents({"user_id": {"$in": user_ids}})
        messages = await db.messages.count_documents({"user_id": {"$in": user_ids}})
        campaigns = await db.campaigns.count_documents({"user_id": {"$in": user_ids}})
        
        return {
            "organization_id": org_id,
            "stores": stores,
            "users": users,
            "contacts": contacts,
            "messages": messages,
            "campaigns": campaigns
        }
    else:
        # Platform-wide stats
        return {
            "organizations": await db.organizations.count_documents({}),
            "stores": await db.stores.count_documents({}),
            "users": await db.users.count_documents({}),
            "contacts": await db.contacts.count_documents({}),
            "messages": await db.messages.count_documents({}),
            "campaigns": await db.campaigns.count_documents({})
        }

@api_router.get("/admin/organizations/{org_id}/leaderboard")
async def get_org_leaderboard(org_id: str, store_id: str = None, metric: str = "contacts_added"):
    """Get leaderboard for an organization or store"""
    query = {"organization_id": org_id}
    if store_id:
        query["store_id"] = store_id
    
    # Get users with their stats
    users = await db.users.find(query, {"password": 0}).sort(f"stats.{metric}", -1).to_list(100)
    
    leaderboard = []
    for rank, user in enumerate(users, 1):
        leaderboard.append({
            "rank": rank,
            "user_id": str(user["_id"]),
            "name": user.get("name", "Unknown"),
            "store_id": user.get("store_id"),
            "stats": user.get("stats", {}),
            "metric_value": user.get("stats", {}).get(metric, 0)
        })
    
    return {
        "metric": metric,
        "organization_id": org_id,
        "store_id": store_id,
        "leaderboard": leaderboard
    }

# ============= REGIONAL LEADERBOARD (Sole Proprietors) =============
# US States by region for regional comparison
US_REGIONS = {
    "northeast": ["CT", "ME", "MA", "NH", "RI", "VT", "NJ", "NY", "PA"],
    "midwest": ["IL", "IN", "MI", "OH", "WI", "IA", "KS", "MN", "MO", "NE", "ND", "SD"],
    "south": ["DE", "FL", "GA", "MD", "NC", "SC", "VA", "DC", "WV", "AL", "KY", "MS", "TN", "AR", "LA", "OK", "TX"],
    "west": ["AZ", "CO", "ID", "MT", "NV", "NM", "UT", "WY", "AK", "CA", "HI", "OR", "WA"]
}

def get_region_for_state(state: str) -> str:
    """Get region name for a given state abbreviation"""
    state = state.upper() if state else ""
    for region, states in US_REGIONS.items():
        if state in states:
            return region
    return "unknown"

@api_router.get("/leaderboard/regional")
async def get_regional_leaderboard(
    user_id: str,
    scope: str = "state",  # state, region, country
    metric: str = "contacts_added"
):
    """Get regional leaderboard for sole proprietors"""
    # Get the requesting user
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Build query for sole proprietors who have opted in
    query = {
        "leaderboard_visible": True,
        "$or": [
            {"organization_id": None},
            {"organization_id": {"$exists": False}}
        ]
    }
    
    # Get user's location
    user_org = None
    if user.get("organization_id"):
        user_org = await db.organizations.find_one({"_id": ObjectId(user["organization_id"])})
    
    user_state = user_org.get("state") if user_org else user.get("state", "")
    user_region = get_region_for_state(user_state)
    user_country = user_org.get("country", "US") if user_org else user.get("country", "US")
    
    # Filter by scope
    if scope == "state" and user_state:
        # For sole proprietors, we need to join with their org data
        # For now, we'll filter after fetching
        pass
    elif scope == "region":
        # Will filter by region states
        pass
    # country scope = no location filter
    
    # Get all visible sole proprietors
    visible_users = await db.users.find(query, {"password": 0}).sort(f"stats.{metric}", -1).to_list(1000)
    
    # Filter by location and build leaderboard
    leaderboard = []
    user_rank = None
    
    for idx, u in enumerate(visible_users):
        # Get user's state from their org or user record
        u_state = u.get("state", "")
        if u.get("organization_id"):
            u_org = await db.organizations.find_one({"_id": ObjectId(u["organization_id"])})
            if u_org:
                u_state = u_org.get("state", "")
        
        u_region = get_region_for_state(u_state)
        u_country = u.get("country", "US")
        
        # Check if user matches scope
        include = False
        if scope == "country":
            include = u_country == user_country
        elif scope == "region":
            include = u_region == user_region and u_region != "unknown"
        elif scope == "state":
            include = u_state.upper() == user_state.upper() if u_state and user_state else False
        
        if include:
            rank = len(leaderboard) + 1
            entry = {
                "rank": rank,
                "user_id": str(u["_id"]),
                "name": u.get("name", "Anonymous"),
                "state": u_state,
                "stats": u.get("stats", {}),
                "metric_value": u.get("stats", {}).get(metric, 0),
                "is_you": str(u["_id"]) == user_id
            }
            leaderboard.append(entry)
            
            if str(u["_id"]) == user_id:
                user_rank = rank
    
    # If user isn't visible but wants to see their rank
    if user_rank is None and user.get("leaderboard_visible"):
        # User is visible but wasn't in the filtered results
        pass
    
    return {
        "metric": metric,
        "scope": scope,
        "user_state": user_state,
        "user_region": user_region,
        "user_rank": user_rank,
        "total_in_scope": len(leaderboard),
        "leaderboard": leaderboard[:50]  # Limit to top 50
    }

@api_router.put("/users/{user_id}/leaderboard-settings")
async def update_leaderboard_settings(user_id: str, settings: dict):
    """Update user's leaderboard visibility and comparison settings"""
    allowed_fields = ["leaderboard_visible", "compare_scope"]
    update_dict = {k: v for k, v in settings.items() if k in allowed_fields}
    
    if "compare_scope" in update_dict:
        if update_dict["compare_scope"] not in ["state", "region", "country"]:
            raise HTTPException(status_code=400, detail="Invalid compare_scope. Use: state, region, or country")
    
    update_dict["updated_at"] = datetime.utcnow()
    
    result = await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": update_dict}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {"message": "Leaderboard settings updated"}

@api_router.get("/users/{user_id}/leaderboard-settings")
async def get_leaderboard_settings(user_id: str):
    """Get user's leaderboard settings"""
    user = await db.users.find_one({"_id": ObjectId(user_id)}, {"password": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "leaderboard_visible": user.get("leaderboard_visible", False),
        "compare_scope": user.get("compare_scope", "state"),
        "state": user.get("state", ""),
        "country": user.get("country", "US")
    }

# ============= UTILITY ENDPOINTS =============
@api_router.get("/")
async def root():
    return {"message": "MVPLine API", "version": "1.0"}

@api_router.get("/user/{user_id}")
async def get_user(user_id: str):
    """Get user profile"""
    try:
        from bson import ObjectId
        # Try with ObjectId first, then with string
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            user = await db.users.find_one({"_id": user_id})
    except:
        # If ObjectId conversion fails, try with string
        user = await db.users.find_one({"_id": user_id})
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user['_id'] = str(user['_id'])
    return user

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
