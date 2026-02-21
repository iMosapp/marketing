"""
SOP (Standard Operating Procedure) Router
Internal documentation system for MVPLine employees
Only accessible by MVPLine internal team members (super_admin role)
"""
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, Field
from bson import ObjectId
from datetime import datetime
from typing import Optional, List
from enum import Enum
import logging

from routers.database import get_db, get_user_by_id

router = APIRouter(prefix="/sop", tags=["SOP"])
logger = logging.getLogger(__name__)


# ============= MODELS =============
class SOPDepartment(str, Enum):
    ALL = "all"
    SALES = "sales"
    SUPPORT = "support"
    BILLING = "billing"
    ADMIN = "admin"
    ONBOARDING = "onboarding"
    MANAGEMENT = "management"
    PARTNERS = "partners"


class SOPCategory(str, Enum):
    GETTING_STARTED = "getting_started"
    DAILY_OPERATIONS = "daily_operations"
    CUSTOMER_COMMUNICATION = "customer_communication"
    ADMIN_TASKS = "admin_tasks"
    TROUBLESHOOTING = "troubleshooting"
    BEST_PRACTICES = "best_practices"
    POLICIES = "policies"
    TOOLS_FEATURES = "tools_features"


class SOPStep(BaseModel):
    order: int
    title: str
    description: str
    screenshot_url: Optional[str] = None
    video_url: Optional[str] = None
    tip: Optional[str] = None
    warning: Optional[str] = None
    link_text: Optional[str] = None
    link_url: Optional[str] = None


class SOPCreate(BaseModel):
    title: str
    summary: str
    department: str = "all"
    category: str
    steps: List[dict]
    tags: List[str] = []
    estimated_time: Optional[str] = None
    difficulty: str = "beginner"
    related_sops: List[str] = []
    video_walkthrough_url: Optional[str] = None
    is_required_reading: bool = False
    is_published: bool = True


class SOPUpdate(BaseModel):
    title: Optional[str] = None
    summary: Optional[str] = None
    department: Optional[str] = None
    category: Optional[str] = None
    steps: Optional[List[dict]] = None
    tags: Optional[List[str]] = None
    estimated_time: Optional[str] = None
    difficulty: Optional[str] = None
    related_sops: Optional[List[str]] = None
    video_walkthrough_url: Optional[str] = None
    is_required_reading: Optional[bool] = None
    is_published: Optional[bool] = None


# Check if user is internal MVPLine employee
async def verify_internal_access(user_id: str) -> dict:
    """Verify user is an internal MVPLine employee"""
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    user = await get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    # Only allow internal roles
    internal_roles = ['super_admin', 'org_admin', 'store_manager']
    if user.get('role') not in internal_roles:
        raise HTTPException(status_code=403, detail="Access restricted to internal employees")
    
    return user


@router.get("/")
async def list_sops(
    department: Optional[str] = None,
    category: Optional[str] = None,
    search: Optional[str] = None,
    x_user_id: str = Header(None, alias="X-User-ID")
):
    """List all SOPs, optionally filtered by department or category"""
    user = await verify_internal_access(x_user_id)
    db = get_db()
    
    # Build query
    query = {"is_published": True}
    
    if department and department != "all":
        query["department"] = department
    
    if category:
        query["category"] = category
    
    if search:
        query["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"summary": {"$regex": search, "$options": "i"}},
            {"tags": {"$regex": search, "$options": "i"}}
        ]
    
    sops = await db.sops.find(query).sort("category", 1).to_list(200)
    
    # Get user's reading progress
    user_id = str(user.get('_id'))
    progress_docs = await db.sop_progress.find({"user_id": user_id}).to_list(200)
    progress_map = {p["sop_id"]: p for p in progress_docs}
    
    result = []
    for sop in sops:
        sop_id = str(sop["_id"])
        progress = progress_map.get(sop_id, {})
        result.append({
            **sop,
            "_id": sop_id,
            "is_completed": progress.get("completed", False),
            "current_step": progress.get("current_step", 0),
            "last_viewed_at": progress.get("last_viewed_at")
        })
    
    return result


@router.get("/categories")
async def get_categories(x_user_id: str = Header(None, alias="X-User-ID")):
    """Get all SOP categories with counts"""
    await verify_internal_access(x_user_id)
    db = get_db()
    
    pipeline = [
        {"$match": {"is_published": True}},
        {"$group": {"_id": "$category", "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}}
    ]
    
    result = await db.sops.aggregate(pipeline).to_list(50)
    
    category_labels = {
        "getting_started": "Getting Started",
        "daily_operations": "Daily Operations",
        "customer_communication": "Customer Communication",
        "admin_tasks": "Admin Tasks",
        "troubleshooting": "Troubleshooting",
        "best_practices": "Best Practices",
        "policies": "Policies & Guidelines",
        "tools_features": "Tools & Features"
    }
    
    return [
        {
            "id": r["_id"],
            "name": category_labels.get(r["_id"], r["_id"]),
            "count": r["count"]
        }
        for r in result
    ]


@router.get("/departments")
async def get_departments(x_user_id: str = Header(None, alias="X-User-ID")):
    """Get all departments with SOP counts"""
    await verify_internal_access(x_user_id)
    db = get_db()
    
    pipeline = [
        {"$match": {"is_published": True}},
        {"$group": {"_id": "$department", "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}}
    ]
    
    result = await db.sops.aggregate(pipeline).to_list(50)
    
    dept_labels = {
        "all": "All Departments",
        "sales": "Sales Team",
        "support": "Customer Support",
        "billing": "Billing & Accounts",
        "admin": "Administration",
        "onboarding": "Onboarding",
        "management": "Management",
        "partners": "Partners & Resellers"
    }
    
    dept_icons = {
        "all": "people",
        "sales": "trending-up",
        "support": "headset",
        "billing": "card",
        "admin": "shield-checkmark",
        "onboarding": "rocket",
        "management": "briefcase",
        "partners": "handshake"
    }
    
    return [
        {
            "id": r["_id"],
            "name": dept_labels.get(r["_id"], r["_id"]),
            "icon": dept_icons.get(r["_id"], "document"),
            "count": r["count"]
        }
        for r in result
    ]


@router.get("/required")
async def get_required_reading(x_user_id: str = Header(None, alias="X-User-ID")):
    """Get all required reading SOPs for the user"""
    user = await verify_internal_access(x_user_id)
    db = get_db()
    
    # Get required SOPs
    sops = await db.sops.find({
        "is_published": True,
        "is_required_reading": True
    }).to_list(50)
    
    # Get user's progress
    user_id = str(user.get('_id'))
    progress_docs = await db.sop_progress.find({
        "user_id": user_id,
        "completed": True
    }).to_list(100)
    completed_ids = {p["sop_id"] for p in progress_docs}
    
    result = []
    for sop in sops:
        sop_id = str(sop["_id"])
        result.append({
            **sop,
            "_id": sop_id,
            "is_completed": sop_id in completed_ids
        })
    
    return {
        "sops": result,
        "total": len(result),
        "completed": len([s for s in result if s["is_completed"]])
    }


@router.get("/{sop_id}")
async def get_sop(sop_id: str, x_user_id: str = Header(None, alias="X-User-ID")):
    """Get a specific SOP with full details"""
    user = await verify_internal_access(x_user_id)
    db = get_db()
    
    sop = await db.sops.find_one({"_id": ObjectId(sop_id)})
    if not sop:
        raise HTTPException(status_code=404, detail="SOP not found")
    
    # Update last viewed
    user_id = str(user.get('_id'))
    await db.sop_progress.update_one(
        {"user_id": user_id, "sop_id": sop_id},
        {
            "$set": {"last_viewed_at": datetime.utcnow()},
            "$setOnInsert": {"completed": False, "current_step": 0}
        },
        upsert=True
    )
    
    # Get user's progress
    progress = await db.sop_progress.find_one({"user_id": user_id, "sop_id": sop_id})
    
    # Get related SOPs
    related = []
    if sop.get("related_sops"):
        related_docs = await db.sops.find({
            "_id": {"$in": [ObjectId(rid) for rid in sop["related_sops"]]}
        }).to_list(10)
        related = [{"_id": str(r["_id"]), "title": r["title"]} for r in related_docs]
    
    sop["_id"] = str(sop["_id"])
    sop["is_completed"] = progress.get("completed", False) if progress else False
    sop["current_step"] = progress.get("current_step", 0) if progress else 0
    sop["related_sops_details"] = related
    
    return sop


@router.post("/{sop_id}/progress")
async def update_progress(
    sop_id: str,
    current_step: int,
    completed: bool = False,
    x_user_id: str = Header(None, alias="X-User-ID")
):
    """Update user's reading progress on an SOP"""
    user = await verify_internal_access(x_user_id)
    db = get_db()
    
    user_id = str(user.get('_id'))
    
    update_data = {
        "current_step": current_step,
        "last_viewed_at": datetime.utcnow()
    }
    
    if completed:
        update_data["completed"] = True
        update_data["completed_at"] = datetime.utcnow()
    
    await db.sop_progress.update_one(
        {"user_id": user_id, "sop_id": sop_id},
        {"$set": update_data},
        upsert=True
    )
    
    return {"success": True}


@router.post("/{sop_id}/feedback")
async def submit_feedback(
    sop_id: str,
    helpful: bool,
    comment: Optional[str] = None,
    x_user_id: str = Header(None, alias="X-User-ID")
):
    """Submit feedback on an SOP"""
    user = await verify_internal_access(x_user_id)
    db = get_db()
    
    user_id = str(user.get('_id'))
    
    await db.sop_feedback.insert_one({
        "user_id": user_id,
        "sop_id": sop_id,
        "helpful": helpful,
        "comment": comment,
        "created_at": datetime.utcnow()
    })
    
    return {"success": True}


# ============= ADMIN ENDPOINTS (Super Admin Only) =============

@router.post("/")
async def create_sop(sop_data: SOPCreate, x_user_id: str = Header(None, alias="X-User-ID")):
    """Create a new SOP - super_admin only"""
    user = await verify_internal_access(x_user_id)
    
    if user.get('role') != 'super_admin':
        raise HTTPException(status_code=403, detail="Only super admins can create SOPs")
    
    db = get_db()
    
    sop_dict = sop_data.dict()
    sop_dict["created_at"] = datetime.utcnow()
    sop_dict["updated_at"] = datetime.utcnow()
    sop_dict["created_by"] = str(user.get('_id'))
    
    result = await db.sops.insert_one(sop_dict)
    sop_dict["_id"] = str(result.inserted_id)
    
    return sop_dict


@router.put("/{sop_id}")
async def update_sop(
    sop_id: str,
    sop_data: SOPUpdate,
    x_user_id: str = Header(None, alias="X-User-ID")
):
    """Update an existing SOP - super_admin only"""
    user = await verify_internal_access(x_user_id)
    
    if user.get('role') != 'super_admin':
        raise HTTPException(status_code=403, detail="Only super admins can update SOPs")
    
    db = get_db()
    
    update_dict = {k: v for k, v in sop_data.dict().items() if v is not None}
    update_dict["updated_at"] = datetime.utcnow()
    update_dict["updated_by"] = str(user.get('_id'))
    
    result = await db.sops.update_one(
        {"_id": ObjectId(sop_id)},
        {"$set": update_dict}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="SOP not found")
    
    return {"success": True}


@router.delete("/{sop_id}")
async def delete_sop(sop_id: str, x_user_id: str = Header(None, alias="X-User-ID")):
    """Delete an SOP - super_admin only"""
    user = await verify_internal_access(x_user_id)
    
    if user.get('role') != 'super_admin':
        raise HTTPException(status_code=403, detail="Only super admins can delete SOPs")
    
    db = get_db()
    
    result = await db.sops.delete_one({"_id": ObjectId(sop_id)})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="SOP not found")
    
    # Also delete progress and feedback
    await db.sop_progress.delete_many({"sop_id": sop_id})
    await db.sop_feedback.delete_many({"sop_id": sop_id})
    
    return {"success": True}


@router.get("/team/progress")
async def get_team_training_progress(
    organization_id: Optional[str] = None,
    store_id: Optional[str] = None,
    x_user_id: str = Header(None, alias="X-User-ID")
):
    """Get training progress for team members - for admin dashboard widget"""
    user = await verify_internal_access(x_user_id)
    db = get_db()
    
    user_role = user.get('role', 'user')
    user_org_id = user.get('organization_id')
    user_store_id = user.get('store_id')
    
    # Get total published SOPs
    total_sops = await db.sops.count_documents({"is_published": True})
    
    if total_sops == 0:
        return {
            "total_sops": 0,
            "team_members": [],
            "summary": {
                "total_members": 0,
                "fully_trained": 0,
                "in_progress": 0,
                "not_started": 0,
                "completion_rate": 0
            }
        }
    
    # Build user query based on role
    user_query = {"is_active": True}
    
    if user_role == 'super_admin':
        if organization_id:
            user_query["organization_id"] = organization_id
        if store_id:
            user_query["store_id"] = store_id
    elif user_role == 'org_admin':
        user_query["organization_id"] = user_org_id
        if store_id:
            user_query["store_id"] = store_id
    elif user_role == 'store_manager':
        user_query["store_id"] = user_store_id
    else:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Get team members
    team_members = await db.users.find(user_query).to_list(100)
    
    # Get progress for each team member
    team_progress = []
    fully_trained = 0
    in_progress = 0
    not_started = 0
    
    for member in team_members:
        member_id = str(member.get('_id'))
        
        # Count completed SOPs for this member
        completed_count = await db.sop_progress.count_documents({
            "user_id": member_id,
            "completed": True
        })
        
        completion_percentage = round((completed_count / total_sops) * 100) if total_sops > 0 else 0
        
        # Categorize
        if completion_percentage == 100:
            fully_trained += 1
            status = "complete"
        elif completion_percentage > 0:
            in_progress += 1
            status = "in_progress"
        else:
            not_started += 1
            status = "not_started"
        
        team_progress.append({
            "_id": member_id,
            "name": f"{member.get('first_name', '')} {member.get('last_name', '')}".strip() or member.get('email', 'Unknown'),
            "email": member.get('email'),
            "role": member.get('role', 'user'),
            "completed": completed_count,
            "total": total_sops,
            "percentage": completion_percentage,
            "status": status
        })
    
    # Sort by completion percentage (lowest first to prioritize those needing training)
    team_progress.sort(key=lambda x: x['percentage'])
    
    total_members = len(team_members)
    completion_rate = round((fully_trained / total_members) * 100) if total_members > 0 else 0
    
    return {
        "total_sops": total_sops,
        "team_members": team_progress[:10],  # Top 10 for widget
        "summary": {
            "total_members": total_members,
            "fully_trained": fully_trained,
            "in_progress": in_progress,
            "not_started": not_started,
            "completion_rate": completion_rate
        }
    }


@router.post("/seed")
async def seed_sops(x_user_id: str = Header(None, alias="X-User-ID")):
    """Seed the database with initial SOPs - super_admin only"""
    user = await verify_internal_access(x_user_id)
    
    if user.get('role') != 'super_admin':
        raise HTTPException(status_code=403, detail="Only super admins can seed SOPs")
    
    db = get_db()
    
    # Check if already seeded
    count = await db.sops.count_documents({})
    if count > 0:
        return {"message": f"SOPs already exist ({count} found). Delete existing to re-seed."}
    
    # Comprehensive SOP content
    sops = [
        # ============= GETTING STARTED =============
        {
            "title": "Welcome to MVPLine",
            "summary": "Your complete guide to getting started with MVPLine. Learn the basics and set yourself up for success.",
            "department": "all",
            "category": "getting_started",
            "is_required_reading": True,
            "estimated_time": "10 minutes",
            "difficulty": "beginner",
            "tags": ["onboarding", "basics", "setup"],
            "steps": [
                {
                    "order": 1,
                    "title": "Understanding MVPLine",
                    "description": "MVPLine is an AI-powered communication platform designed for sales professionals. It helps you manage customer relationships, automate follow-ups, and close more deals.",
                    "tip": "Think of MVPLine as your personal sales assistant that never sleeps!"
                },
                {
                    "order": 2,
                    "title": "The Main Navigation",
                    "description": "The app has 4 main tabs at the bottom:\n\n• **Inbox** - Your conversations with customers\n• **Contacts** - Your customer database\n• **Dialer** - Make calls with one tap\n• **More** - Settings, tools, and features",
                    "tip": "You can swipe between tabs for faster navigation"
                },
                {
                    "order": 3,
                    "title": "Setting Up Your Profile",
                    "description": "Go to More → My Digital Card to set up your profile. This includes:\n\n• Your photo\n• Bio and personal information\n• Social media links\n• Voicemail greeting",
                    "link_text": "Go to My Profile",
                    "link_url": "/settings/my-profile"
                },
                {
                    "order": 4,
                    "title": "Your Digital Business Card",
                    "description": "Your profile becomes a shareable digital business card! Customers can:\n\n• View your photo and bio\n• Read reviews from your customers\n• Contact you directly\n• Leave referrals",
                    "tip": "Share your card link in your email signature for maximum impact"
                },
                {
                    "order": 5,
                    "title": "Getting Help with Jessi",
                    "description": "Jessi is your AI assistant built into MVPLine. Tap 'Ask Jessi' from the More menu to:\n\n• Ask questions about features\n• Get help with tasks\n• Learn tips and tricks",
                    "link_text": "Talk to Jessi",
                    "link_url": "/jessie"
                }
            ],
            "is_published": True
        },
        {
            "title": "Setting Up Your AI Persona",
            "summary": "Customize how AI responds to your customers. Your persona defines your communication style.",
            "department": "all",
            "category": "getting_started",
            "is_required_reading": True,
            "estimated_time": "5 minutes",
            "difficulty": "beginner",
            "tags": ["ai", "persona", "setup", "communication"],
            "steps": [
                {
                    "order": 1,
                    "title": "What is an AI Persona?",
                    "description": "Your AI persona defines how the AI communicates with customers on your behalf. It includes your:\n\n• Communication style (formal, casual, friendly)\n• Tone and personality\n• Common phrases you use\n• Industry-specific language"
                },
                {
                    "order": 2,
                    "title": "Accessing Persona Settings",
                    "description": "Go to More → AI Persona Settings to configure your communication style.",
                    "link_text": "Go to Persona Settings",
                    "link_url": "/settings/persona"
                },
                {
                    "order": 3,
                    "title": "Choosing Your Style",
                    "description": "Select a communication style that matches how you naturally talk to customers:\n\n• **Professional** - Formal, business-like\n• **Friendly** - Warm and approachable\n• **Casual** - Relaxed and conversational\n• **Enthusiastic** - High-energy and excited",
                    "tip": "Choose what feels most natural to you - customers can tell when communication feels forced"
                },
                {
                    "order": 4,
                    "title": "Adding Custom Phrases",
                    "description": "Add phrases you commonly use. The AI will incorporate these into messages:\n\n• Greetings you like to use\n• Your signature sign-offs\n• Industry terms you prefer"
                }
            ],
            "is_published": True
        },
        
        # ============= DAILY OPERATIONS =============
        {
            "title": "Managing Your Inbox",
            "summary": "Master your inbox to stay on top of customer conversations and never miss an opportunity.",
            "department": "sales",
            "category": "daily_operations",
            "estimated_time": "8 minutes",
            "difficulty": "beginner",
            "tags": ["inbox", "messages", "conversations", "daily"],
            "steps": [
                {
                    "order": 1,
                    "title": "Understanding the Inbox",
                    "description": "Your inbox shows all customer conversations. Each conversation displays:\n\n• Customer name and photo\n• Last message preview\n• Time since last activity\n• AI outcome badges (Hot Lead, Appt Set, etc.)",
                    "link_text": "Go to Inbox",
                    "link_url": "/(tabs)/inbox"
                },
                {
                    "order": 2,
                    "title": "AI Outcome Badges",
                    "description": "Look for colored badges that indicate AI-detected outcomes:\n\n• 🔥 **Hot Lead** - High interest customer\n• 📅 **Appt Set** - Appointment scheduled\n• 📞 **Call Back** - Customer requested callback\n• ⚠️ **Needs Help** - Requires your attention\n• ❓ **Question** - Customer has a question",
                    "tip": "Prioritize Hot Leads and Needs Help badges first"
                },
                {
                    "order": 3,
                    "title": "Swipe Actions",
                    "description": "Swipe on any conversation for quick actions:\n\n• Swipe right → Call the customer\n• Swipe left → Archive conversation\n• Long press → More options",
                    "tip": "Swipe actions save time - you can handle most tasks without opening the conversation"
                },
                {
                    "order": 4,
                    "title": "Starting New Conversations",
                    "description": "Tap the + button in the top right to:\n\n• Send a new message to existing contact\n• Add a new contact and message them\n• Send a template message"
                },
                {
                    "order": 5,
                    "title": "Search and Filter",
                    "description": "Use the search bar to find conversations by:\n\n• Customer name\n• Phone number\n• Message content\n• Tags"
                }
            ],
            "is_published": True
        },
        {
            "title": "Working with Contacts",
            "summary": "Build and manage your customer database for better relationships and more sales.",
            "department": "sales",
            "category": "daily_operations",
            "estimated_time": "7 minutes",
            "difficulty": "beginner",
            "tags": ["contacts", "customers", "database", "crm"],
            "steps": [
                {
                    "order": 1,
                    "title": "Viewing Your Contacts",
                    "description": "The Contacts tab shows all your customers. You can:\n\n• Search by name or phone\n• Filter by tags\n• Sort by recent activity\n• View contact details",
                    "link_text": "Go to Contacts",
                    "link_url": "/(tabs)/contacts"
                },
                {
                    "order": 2,
                    "title": "Adding New Contacts",
                    "description": "Add contacts by:\n\n• Tapping the + button\n• Importing from your phone\n• Bulk import from CSV file\n• Automatic creation from incoming messages"
                },
                {
                    "order": 3,
                    "title": "Contact Details",
                    "description": "Tap any contact to see their full profile:\n\n• Contact information\n• Conversation history\n• Notes and tags\n• Deal information\n• Activity timeline"
                },
                {
                    "order": 4,
                    "title": "Using Tags",
                    "description": "Tags help organize contacts:\n\n• Create custom tags (Hot Lead, Past Customer, etc.)\n• Filter contacts by tag\n• Use tags for targeted campaigns\n• Track customer journey stages",
                    "link_text": "Manage Tags",
                    "link_url": "/settings/tags"
                },
                {
                    "order": 5,
                    "title": "Contact Notes",
                    "description": "Add notes to remember important details:\n\n• Customer preferences\n• Vehicle interests\n• Follow-up reminders\n• Special requests",
                    "tip": "Good notes = better customer relationships = more sales"
                }
            ],
            "is_published": True
        },
        
        # ============= CUSTOMER COMMUNICATION =============
        {
            "title": "Sending Messages Like a Pro",
            "summary": "Learn the best practices for customer communication that closes deals.",
            "department": "sales",
            "category": "customer_communication",
            "estimated_time": "10 minutes",
            "difficulty": "intermediate",
            "tags": ["messaging", "communication", "sales", "templates"],
            "steps": [
                {
                    "order": 1,
                    "title": "Opening a Conversation",
                    "description": "Tap on any inbox item or contact to open the conversation thread. You'll see:\n\n• Full message history\n• Customer info at top\n• Message input at bottom\n• Quick action buttons"
                },
                {
                    "order": 2,
                    "title": "Using Message Templates",
                    "description": "Templates save time on common messages. Access them by:\n\n• Tapping the template icon in the message bar\n• Or go to More → Message Templates to manage them",
                    "link_text": "Manage Templates",
                    "link_url": "/settings/templates",
                    "tip": "Create templates for: Initial outreach, follow-ups, appointment confirmations, thank you messages"
                },
                {
                    "order": 3,
                    "title": "Personalization Variables",
                    "description": "Templates can include variables that auto-fill:\n\n• {first_name} - Customer's first name\n• {vehicle} - Vehicle of interest\n• {your_name} - Your name\n• {dealership} - Your dealership name"
                },
                {
                    "order": 4,
                    "title": "AI-Assisted Responses",
                    "description": "Let AI help craft responses:\n\n• Tap the AI wand icon for suggestions\n• AI considers conversation context\n• Edit before sending\n• AI learns your style over time"
                },
                {
                    "order": 5,
                    "title": "Sending Photos and Media",
                    "description": "Attach media to messages:\n\n• Vehicle photos\n• Documents\n• Video walkarounds\n• Location pins"
                },
                {
                    "order": 6,
                    "title": "Message Timing Best Practices",
                    "description": "When to message matters:\n\n• Respond within 5 minutes when possible\n• Avoid late night messages (after 9 PM)\n• Weekend mornings are great for follow-ups\n• Set reminders for optimal timing",
                    "warning": "Never send automated messages before 8 AM or after 9 PM"
                }
            ],
            "is_published": True
        },
        {
            "title": "Sending Congrats Cards",
            "summary": "Celebrate customer purchases with personalized congratulations cards.",
            "department": "sales",
            "category": "customer_communication",
            "estimated_time": "5 minutes",
            "difficulty": "beginner",
            "tags": ["congrats", "cards", "celebrations", "customer-experience"],
            "steps": [
                {
                    "order": 1,
                    "title": "What are Congrats Cards?",
                    "description": "Congrats Cards are digital thank-you cards you send when a customer makes a purchase. They:\n\n• Show appreciation\n• Include your photo and message\n• Can be shared on social media\n• Generate referrals"
                },
                {
                    "order": 2,
                    "title": "Customizing Your Card Style",
                    "description": "Go to More → Congrats Card Style to customize:\n\n• Card colors and theme\n• Headline message\n• Thank you text\n• Your photo and branding",
                    "link_text": "Customize Card",
                    "link_url": "/settings/congrats-template"
                },
                {
                    "order": 3,
                    "title": "Sending a Card",
                    "description": "To send a Congrats Card:\n\n1. Open the customer's conversation\n2. Tap the gift/card icon\n3. Add customer's photo (optional)\n4. Customize message\n5. Send!"
                },
                {
                    "order": 4,
                    "title": "Tracking Card Views",
                    "description": "See who views your cards:\n\n• View count tracking\n• Social shares\n• Referral clicks\n• Review prompts"
                }
            ],
            "is_published": True
        },
        
        # ============= TOOLS & FEATURES =============
        {
            "title": "Nurture Campaigns",
            "summary": "Set up automated follow-up campaigns to stay top of mind with customers.",
            "department": "sales",
            "category": "tools_features",
            "estimated_time": "12 minutes",
            "difficulty": "intermediate",
            "tags": ["campaigns", "automation", "follow-up", "nurture"],
            "steps": [
                {
                    "order": 1,
                    "title": "What are Nurture Campaigns?",
                    "description": "Nurture Campaigns automatically send scheduled messages to contacts. Use them for:\n\n• Birthday wishes\n• Service reminders\n• Holiday greetings\n• Follow-up sequences"
                },
                {
                    "order": 2,
                    "title": "Viewing Your Campaigns",
                    "description": "Go to More → Nurture Campaigns to see all your campaigns and their status.",
                    "link_text": "View Campaigns",
                    "link_url": "/campaigns"
                },
                {
                    "order": 3,
                    "title": "Creating a Campaign",
                    "description": "To create a new campaign:\n\n1. Tap + Create Campaign\n2. Choose campaign type\n3. Write your message sequence\n4. Set timing and triggers\n5. Activate campaign"
                },
                {
                    "order": 4,
                    "title": "Campaign Types",
                    "description": "Built-in campaign types:\n\n• **Birthday** - Sends on contact's birthday\n• **Anniversary** - Purchase anniversary\n• **Service Reminder** - Based on mileage/time\n• **Custom** - Your own triggers"
                },
                {
                    "order": 5,
                    "title": "Campaign Dashboard",
                    "description": "Monitor campaign performance:\n\n• Active enrollments\n• Messages sent\n• Response rates\n• Upcoming sends",
                    "link_text": "Campaign Dashboard",
                    "link_url": "/campaigns/dashboard"
                },
                {
                    "order": 6,
                    "title": "Enrolling Contacts",
                    "description": "Add contacts to campaigns:\n\n• Automatic enrollment based on criteria\n• Manual enrollment from contact profile\n• Bulk enrollment via contact list"
                }
            ],
            "is_published": True
        },
        {
            "title": "Tasks and Reminders",
            "summary": "Never forget a follow-up with the built-in task management system.",
            "department": "sales",
            "category": "tools_features",
            "estimated_time": "6 minutes",
            "difficulty": "beginner",
            "tags": ["tasks", "reminders", "follow-up", "productivity"],
            "steps": [
                {
                    "order": 1,
                    "title": "Accessing Tasks",
                    "description": "Go to More → Tasks & Reminders to view and manage your to-do list.",
                    "link_text": "View Tasks",
                    "link_url": "/tasks"
                },
                {
                    "order": 2,
                    "title": "Creating a Task",
                    "description": "Create tasks for:\n\n• Follow-up calls\n• Send quotes\n• Schedule appointments\n• Personal reminders"
                },
                {
                    "order": 3,
                    "title": "Linking Tasks to Contacts",
                    "description": "Connect tasks to specific customers:\n\n• See task when viewing contact\n• One-tap to call or message\n• Track completion by customer"
                },
                {
                    "order": 4,
                    "title": "Setting Due Dates and Reminders",
                    "description": "Configure when you're reminded:\n\n• Due date and time\n• Push notification reminders\n• Multiple reminder options\n• Recurring tasks"
                }
            ],
            "is_published": True
        },
        
        # ============= ADMIN TASKS =============
        {
            "title": "Admin Panel Overview",
            "summary": "For managers and admins - learn to manage your team and organization.",
            "department": "management",
            "category": "admin_tasks",
            "estimated_time": "15 minutes",
            "difficulty": "intermediate",
            "tags": ["admin", "management", "team", "organization"],
            "steps": [
                {
                    "order": 1,
                    "title": "Accessing the Admin Panel",
                    "description": "Go to More → Admin Panel to access management tools. You'll see different options based on your role:\n\n• **Super Admin** - Full access to everything\n• **Org Admin** - Manage your organization\n• **Store Manager** - Manage your store's team",
                    "link_text": "Go to Admin Panel",
                    "link_url": "/admin"
                },
                {
                    "order": 2,
                    "title": "Dashboard Overview",
                    "description": "The admin dashboard shows:\n\n• Key metrics and KPIs\n• Recent activity\n• Pending tasks\n• Team performance summary"
                },
                {
                    "order": 3,
                    "title": "Managing Users",
                    "description": "In the Users section you can:\n\n• View all team members\n• Add new users\n• Edit user roles\n• Activate/deactivate accounts",
                    "link_text": "Manage Users",
                    "link_url": "/admin/users"
                },
                {
                    "order": 4,
                    "title": "Managing Stores",
                    "description": "In the Stores section:\n\n• View all stores in your org\n• Add new store locations\n• Assign users to stores\n• Configure store settings",
                    "link_text": "Manage Stores",
                    "link_url": "/admin/stores"
                },
                {
                    "order": 5,
                    "title": "Viewing Reports",
                    "description": "Access performance reports:\n\n• Revenue forecasting\n• Team leaderboards\n• Activity feeds\n• Detailed analytics"
                }
            ],
            "is_published": True
        },
        {
            "title": "Approving New Users",
            "summary": "How to review and approve new user signups for your organization.",
            "department": "management",
            "category": "admin_tasks",
            "estimated_time": "5 minutes",
            "difficulty": "beginner",
            "tags": ["admin", "users", "approval", "onboarding"],
            "steps": [
                {
                    "order": 1,
                    "title": "Checking Pending Users",
                    "description": "Go to More → Pending Users to see new signup requests. You'll see a badge count showing pending approvals.",
                    "link_text": "View Pending Users",
                    "link_url": "/admin/pending-users"
                },
                {
                    "order": 2,
                    "title": "Reviewing a Request",
                    "description": "For each pending user, review:\n\n• Name and email\n• How they signed up\n• Requested organization/store\n• Any notes they provided"
                },
                {
                    "order": 3,
                    "title": "Approving Users",
                    "description": "To approve:\n\n1. Tap on the pending user\n2. Select their role (Sales Rep, Manager, etc.)\n3. Assign to a store\n4. Tap Approve"
                },
                {
                    "order": 4,
                    "title": "Rejecting Users",
                    "description": "To reject:\n\n1. Tap on the pending user\n2. Tap Reject\n3. Optionally add a reason\n4. They'll receive a notification",
                    "warning": "Rejection is permanent - be sure before rejecting"
                }
            ],
            "is_published": True
        },
        
        # ============= BEST PRACTICES =============
        {
            "title": "Response Time Best Practices",
            "summary": "Speed-to-lead is everything. Learn how to respond faster and close more deals.",
            "department": "sales",
            "category": "best_practices",
            "estimated_time": "8 minutes",
            "difficulty": "beginner",
            "tags": ["speed", "response", "leads", "best-practices"],
            "steps": [
                {
                    "order": 1,
                    "title": "Why Speed Matters",
                    "description": "Statistics show:\n\n• Responding within 5 minutes = 9x higher contact rate\n• After 30 minutes, lead quality drops 21x\n• 78% of customers buy from first responder",
                    "tip": "Set your phone to prioritize MVPLine notifications"
                },
                {
                    "order": 2,
                    "title": "Enable Push Notifications",
                    "description": "Make sure notifications are enabled:\n\n1. Go to phone Settings\n2. Find MVPLine\n3. Enable all notifications\n4. Enable sound and badges"
                },
                {
                    "order": 3,
                    "title": "Use Quick Replies",
                    "description": "Save time with templates:\n\n• Set up common responses\n• Use personalization variables\n• One-tap sending\n• AI suggestions"
                },
                {
                    "order": 4,
                    "title": "Handle Overflow",
                    "description": "When too busy to respond:\n\n• AI can send initial response\n• Set auto-away messages\n• Escalate to teammates\n• Schedule follow-up tasks"
                },
                {
                    "order": 5,
                    "title": "Track Your Metrics",
                    "description": "Monitor your response times:\n\n• Average response time\n• Response rate\n• Compare to team average\n• Set personal goals"
                }
            ],
            "is_published": True
        },
        {
            "title": "Building Customer Relationships",
            "summary": "Transform transactions into long-term relationships that drive referrals.",
            "department": "sales",
            "category": "best_practices",
            "estimated_time": "10 minutes",
            "difficulty": "intermediate",
            "tags": ["relationships", "customers", "referrals", "loyalty"],
            "steps": [
                {
                    "order": 1,
                    "title": "Beyond the Transaction",
                    "description": "The best salespeople don't just sell - they build relationships:\n\n• Remember personal details\n• Follow up without selling\n• Celebrate milestones\n• Be genuinely helpful"
                },
                {
                    "order": 2,
                    "title": "Using Contact Notes",
                    "description": "Document everything:\n\n• Family names and details\n• Hobbies and interests\n• Vehicle preferences\n• Important dates",
                    "tip": "Review notes before every interaction"
                },
                {
                    "order": 3,
                    "title": "Stay Top of Mind",
                    "description": "Regular touchpoints:\n\n• Birthday campaigns\n• Service reminders\n• Holiday greetings\n• Helpful content sharing"
                },
                {
                    "order": 4,
                    "title": "Asking for Referrals",
                    "description": "The best time to ask:\n\n• Right after purchase excitement\n• After positive service experience\n• When customer compliments you\n• Include in Congrats Card"
                },
                {
                    "order": 5,
                    "title": "Handling Complaints",
                    "description": "Turn complaints into opportunities:\n\n• Respond immediately\n• Apologize sincerely\n• Solve the problem\n• Follow up to confirm resolution",
                    "tip": "A well-handled complaint can create your most loyal customer"
                }
            ],
            "is_published": True
        },
        
        # ============= TROUBLESHOOTING =============
        {
            "title": "Troubleshooting Common Issues",
            "summary": "Quick fixes for the most common problems you might encounter.",
            "department": "all",
            "category": "troubleshooting",
            "estimated_time": "5 minutes",
            "difficulty": "beginner",
            "tags": ["troubleshooting", "help", "issues", "fixes"],
            "steps": [
                {
                    "order": 1,
                    "title": "Messages Not Sending",
                    "description": "If messages aren't going through:\n\n1. Check your internet connection\n2. Pull down to refresh the inbox\n3. Close and reopen the app\n4. Check if recipient blocked you",
                    "tip": "If still not working, contact support"
                },
                {
                    "order": 2,
                    "title": "Notifications Not Working",
                    "description": "If you're not getting notifications:\n\n1. Check phone Settings → MVPLine → Notifications\n2. Make sure Do Not Disturb is off\n3. Check if battery saver is blocking\n4. Log out and back in"
                },
                {
                    "order": 3,
                    "title": "App Running Slow",
                    "description": "To speed up the app:\n\n1. Close other apps\n2. Restart your phone\n3. Check for app updates\n4. Clear the app cache"
                },
                {
                    "order": 4,
                    "title": "Login Issues",
                    "description": "If you can't log in:\n\n1. Double-check your email spelling\n2. Use 'Forgot Password' to reset\n3. Check if account is still active\n4. Contact your admin if locked out"
                },
                {
                    "order": 5,
                    "title": "Contacting Support",
                    "description": "If you need more help:\n\n• Ask Jessi first (tap 'Ask Jessi')\n• Email support@mvpline.com\n• Include screenshots of the issue\n• Describe steps to reproduce",
                    "link_text": "Ask Jessi for Help",
                    "link_url": "/jessie"
                }
            ],
            "is_published": True
        }
    ]
    
    # Insert all SOPs
    for sop in sops:
        sop["created_at"] = datetime.utcnow()
        sop["updated_at"] = datetime.utcnow()
        sop["created_by"] = str(user.get('_id'))
    
    result = await db.sops.insert_many(sops)
    
    return {"message": f"Successfully seeded {len(result.inserted_ids)} SOPs"}
