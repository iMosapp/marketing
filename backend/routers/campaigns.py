"""
Campaigns router - handles campaign CRUD, enrollments, and scheduler
"""
from fastapi import APIRouter, HTTPException
from bson import ObjectId
from datetime import datetime, timedelta
from typing import List, Optional
import logging

from models import Campaign, CampaignCreate
from routers.database import get_db, get_data_filter, get_user_by_id

router = APIRouter(prefix="/campaigns", tags=["Campaigns"])
logger = logging.getLogger(__name__)


async def check_campaign_permission(user_id: str, action: str = "edit") -> dict:
    """
    Check if user has permission to perform campaign actions.
    
    Returns:
        dict with 'allowed' boolean and 'reason' string
    
    Permission levels:
    - super_admin, org_admin: Always allowed
    - store_manager: Allowed unless store settings explicitly disable
    - user (sales): Only if store settings enable 'allow_sales_campaigns'
    """
    db = get_db()
    user = await get_user_by_id(user_id)
    
    if not user:
        return {"allowed": False, "reason": "User not found"}
    
    role = user.get("role", "user")
    
    # Super admins and org admins always have full access
    if role in ["super_admin", "org_admin"]:
        return {"allowed": True, "reason": "Admin access"}
    
    # Get user's store settings
    store_id = user.get("store_id")
    if not store_id and user.get("store_ids"):
        store_id = user.get("store_ids")[0]  # Use primary store
    
    if not store_id:
        # No store assigned - default to allowed for managers
        if role == "store_manager":
            return {"allowed": True, "reason": "Manager default access"}
        return {"allowed": False, "reason": "No store assigned"}
    
    # Get store settings
    store = await db.stores.find_one({"_id": ObjectId(store_id)})
    if not store:
        return {"allowed": False, "reason": "Store not found"}
    
    settings = store.get("settings", {})
    campaign_settings = settings.get("campaigns", {})
    
    # Store managers - check if manager campaigns are disabled
    if role == "store_manager":
        if campaign_settings.get("managers_can_edit", True):
            return {"allowed": True, "reason": "Manager access enabled"}
        return {"allowed": False, "reason": "Campaign editing disabled for managers at this store"}
    
    # Sales reps - check if sales campaigns are enabled
    if role == "user":
        if campaign_settings.get("sales_can_edit", False):
            return {"allowed": True, "reason": "Sales access enabled"}
        return {"allowed": False, "reason": "Campaign editing not enabled for sales at this store"}
    
    return {"allowed": False, "reason": "Unknown role"}

def calculate_next_send_date(step: dict) -> datetime:
    """Calculate when the next message should be sent based on step configuration"""
    now = datetime.utcnow()
    delay_value = step.get('delay_value', 1)
    delay_unit = step.get('delay_unit', 'days')
    
    if delay_unit == 'minutes':
        return now + timedelta(minutes=delay_value)
    elif delay_unit == 'hours':
        return now + timedelta(hours=delay_value)
    elif delay_unit == 'days':
        return now + timedelta(days=delay_value)
    elif delay_unit == 'weeks':
        return now + timedelta(weeks=delay_value)
    else:
        return now + timedelta(days=delay_value)

@router.get("/{user_id}/permissions")
async def get_campaign_permissions(user_id: str):
    """Check if user has campaign editing permissions"""
    permission = await check_campaign_permission(user_id)
    return permission


@router.post("/{user_id}", response_model=Campaign)
async def create_campaign(user_id: str, campaign_data: CampaignCreate):
    """Create a nurture campaign with permission check"""
    # Check permissions
    permission = await check_campaign_permission(user_id, "create")
    if not permission["allowed"]:
        raise HTTPException(status_code=403, detail=permission["reason"])
    
    campaign_dict = campaign_data.dict()
    campaign_dict['user_id'] = user_id
    campaign_dict['created_at'] = datetime.utcnow()
    
    result = await get_db().campaigns.insert_one(campaign_dict)
    campaign_dict['_id'] = result.inserted_id
    
    logger.info(f"Campaign created: {campaign_dict['name']} with {len(campaign_dict.get('sequences', []))} steps")
    
    return Campaign(**campaign_dict)

@router.get("/{user_id}", response_model=List[Campaign])
async def get_campaigns(user_id: str):
    """Get all campaigns with role-based access"""
    base_filter = await get_data_filter(user_id)
    
    campaigns = await get_db().campaigns.find(base_filter).to_list(1000)
    return [Campaign(**{**camp, "_id": str(camp["_id"])}) for camp in campaigns]

@router.get("/{user_id}/{campaign_id}")
async def get_campaign(user_id: str, campaign_id: str):
    """Get a specific campaign with role-based access check"""
    base_filter = await get_data_filter(user_id)
    
    campaign = await get_db().campaigns.find_one({"$and": [{"_id": ObjectId(campaign_id)}, base_filter]})
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    campaign['_id'] = str(campaign['_id'])
    return campaign

@router.put("/{user_id}/{campaign_id}")
async def update_campaign(user_id: str, campaign_id: str, update_data: dict):
    """Update a campaign with role-based access and permission check"""
    # Check permissions
    permission = await check_campaign_permission(user_id, "edit")
    if not permission["allowed"]:
        raise HTTPException(status_code=403, detail=permission["reason"])
    
    base_filter = await get_data_filter(user_id)
    
    allowed_fields = ['name', 'type', 'trigger_tag', 'segment_tags', 'sequences', 'send_time', 'active', 'media_urls', 'message_template']
    update_dict = {k: v for k, v in update_data.items() if k in allowed_fields}
    
    result = await get_db().campaigns.update_one(
        {"$and": [{"_id": ObjectId(campaign_id)}, base_filter]},
        {"$set": update_dict}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    return {"message": "Campaign updated successfully"}

@router.delete("/{user_id}/{campaign_id}")
async def delete_campaign(user_id: str, campaign_id: str):
    """Delete a campaign and its enrollments with role-based access and permission check"""
    # Check permissions
    permission = await check_campaign_permission(user_id, "delete")
    if not permission["allowed"]:
        raise HTTPException(status_code=403, detail=permission["reason"])
    
    base_filter = await get_data_filter(user_id)
    
    result = await get_db().campaigns.delete_one({"$and": [{"_id": ObjectId(campaign_id)}, base_filter]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Delete all enrollments for this campaign
    await get_db().campaign_enrollments.delete_many({"campaign_id": campaign_id})
    
    return {"message": "Campaign deleted successfully"}

# ============= ENROLLMENT ENDPOINTS =============
@router.post("/{user_id}/{campaign_id}/enroll/{contact_id}")
async def enroll_contact_in_campaign(user_id: str, campaign_id: str, contact_id: str):
    """Enroll a contact in a campaign with role-based access check"""
    base_filter = await get_data_filter(user_id)
    
    # Get campaign (with role-based access)
    campaign = await get_db().campaigns.find_one({"$and": [{"_id": ObjectId(campaign_id)}, base_filter]})
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    if not campaign.get('active', False):
        raise HTTPException(status_code=400, detail="Campaign is not active")
    
    # Get contact (with role-based access)
    contact = await get_db().contacts.find_one({"$and": [{"_id": ObjectId(contact_id)}, base_filter]})
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    # Check if already enrolled
    existing = await get_db().campaign_enrollments.find_one({
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
    
    result = await get_db().campaign_enrollments.insert_one(enrollment)
    enrollment['_id'] = str(result.inserted_id)
    
    logger.info(f"Contact {contact_id} enrolled in campaign {campaign_id}, first message at {next_send}")
    
    return enrollment

@router.get("/{user_id}/{campaign_id}/enrollments")
async def get_campaign_enrollments(user_id: str, campaign_id: str, status: str = None):
    """Get all enrollments for a campaign with role-based access"""
    base_filter = await get_data_filter(user_id)
    
    # First verify user has access to this campaign
    campaign = await get_db().campaigns.find_one({"$and": [{"_id": ObjectId(campaign_id)}, base_filter]})
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Get enrollments for this campaign (with role-based user_id filter)
    query = {"$and": [{"campaign_id": campaign_id}, base_filter]}
    if status:
        query["$and"].append({"status": status})
    
    enrollments = await get_db().campaign_enrollments.find(query).to_list(1000)
    return [{**e, "_id": str(e["_id"])} for e in enrollments]

@router.delete("/{user_id}/{campaign_id}/enrollments/{enrollment_id}")
async def cancel_enrollment(user_id: str, campaign_id: str, enrollment_id: str):
    """Cancel a campaign enrollment with role-based access check"""
    base_filter = await get_data_filter(user_id)
    
    result = await get_db().campaign_enrollments.update_one(
        {"$and": [{"_id": ObjectId(enrollment_id)}, base_filter]},
        {"$set": {"status": "cancelled"}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Enrollment not found")
    
    return {"message": "Enrollment cancelled"}

# ============= SCHEDULER ENDPOINTS =============
@router.post("/scheduler/trigger")
async def trigger_scheduler():
    """Manually trigger the campaign scheduler to process pending messages"""
    now = datetime.utcnow()
    
    # Find all active enrollments with messages due
    pending = await get_db().campaign_enrollments.find({
        "status": "active",
        "next_send_at": {"$lte": now}
    }).to_list(100)
    
    processed = 0
    for enrollment in pending:
        try:
            # Get campaign
            campaign = await get_db().campaigns.find_one({"_id": ObjectId(enrollment['campaign_id'])})
            if not campaign or not campaign.get('active', False):
                continue
            
            sequences = campaign.get('sequences', [])
            current_step = enrollment.get('current_step', 1)
            
            if current_step > len(sequences):
                # Campaign complete
                await get_db().campaign_enrollments.update_one(
                    {"_id": enrollment['_id']},
                    {"$set": {"status": "completed"}}
                )
                continue
            
            # Get current step message
            step = sequences[current_step - 1]
            message_content = step.get('message', '')
            
            # Mock: Log the message that would be sent
            logger.info(f"[MOCK] Sending campaign message to {enrollment['contact_phone']}: {message_content[:50]}...")
            
            # Calculate next send time
            if current_step < len(sequences):
                next_step = sequences[current_step]
                next_send = calculate_next_send_date(next_step)
            else:
                next_send = None
            
            # Update enrollment
            update_data = {
                "current_step": current_step + 1,
                "last_sent_at": now,
                "$push": {"messages_sent": {
                    "step": current_step,
                    "sent_at": now,
                    "content": message_content[:100]
                }}
            }
            
            if next_send:
                update_data["next_send_at"] = next_send
            else:
                update_data["status"] = "completed"
                update_data["next_send_at"] = None
            
            await get_db().campaign_enrollments.update_one(
                {"_id": enrollment['_id']},
                {"$set": {k: v for k, v in update_data.items() if not k.startswith('$')},
                 "$push": update_data.get("$push", {})} if "$push" in update_data else {"$set": update_data}
            )
            
            processed += 1
            
        except Exception as e:
            logger.error(f"Error processing enrollment {enrollment['_id']}: {e}")
    
    return {
        "message": f"Scheduler triggered, processed {processed} messages",
        "processed": processed,
        "pending_found": len(pending)
    }

@router.post("/scheduler/check-date-triggers/{user_id}")
async def check_date_triggers(user_id: str):
    """Check for contacts with birthdays/anniversaries today and auto-enroll in campaigns"""
    db = get_db()
    today = datetime.utcnow()
    today_month = today.month
    today_day = today.day
    
    # Get base filter for user's data
    base_filter = await get_data_filter(user_id)
    
    # Find birthday campaigns
    birthday_campaigns = await db.campaigns.find({
        "$and": [
            {"type": "birthday", "active": True},
            base_filter
        ]
    }).to_list(100)
    
    # Find anniversary campaigns  
    anniversary_campaigns = await db.campaigns.find({
        "$and": [
            {"type": "anniversary", "active": True},
            base_filter
        ]
    }).to_list(100)
    
    enrolled_count = 0
    
    # Process birthday campaigns
    for campaign in birthday_campaigns:
        # Find contacts with birthday today (using MongoDB date aggregation)
        contacts = await db.contacts.find({
            "$and": [
                base_filter,
                {"birthday": {"$exists": True, "$ne": None}}
            ]
        }).to_list(1000)
        
        for contact in contacts:
            birthday = contact.get('birthday')
            if birthday and isinstance(birthday, datetime):
                if birthday.month == today_month and birthday.day == today_day:
                    # Check if already enrolled in this campaign recently
                    existing = await db.campaign_enrollments.find_one({
                        "campaign_id": str(campaign['_id']),
                        "contact_id": str(contact['_id']),
                        "enrolled_at": {"$gte": today - timedelta(days=30)}
                    })
                    
                    if not existing:
                        # Auto-enroll
                        enrollment = {
                            "user_id": user_id,
                            "campaign_id": str(campaign['_id']),
                            "campaign_name": campaign['name'],
                            "contact_id": str(contact['_id']),
                            "contact_name": f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip(),
                            "contact_phone": contact.get('phone', ''),
                            "current_step": 1,
                            "total_steps": len(campaign.get('sequences', [])),
                            "status": "active",
                            "enrolled_at": today,
                            "next_send_at": today,
                            "messages_sent": [],
                            "trigger_type": "birthday"
                        }
                        await db.campaign_enrollments.insert_one(enrollment)
                        enrolled_count += 1
                        logger.info(f"Auto-enrolled {enrollment['contact_name']} in birthday campaign: {campaign['name']}")
    
    # Process anniversary campaigns
    for campaign in anniversary_campaigns:
        contacts = await db.contacts.find({
            "$and": [
                base_filter,
                {"anniversary": {"$exists": True, "$ne": None}}
            ]
        }).to_list(1000)
        
        for contact in contacts:
            anniversary = contact.get('anniversary')
            if anniversary and isinstance(anniversary, datetime):
                if anniversary.month == today_month and anniversary.day == today_day:
                    existing = await db.campaign_enrollments.find_one({
                        "campaign_id": str(campaign['_id']),
                        "contact_id": str(contact['_id']),
                        "enrolled_at": {"$gte": today - timedelta(days=30)}
                    })
                    
                    if not existing:
                        enrollment = {
                            "user_id": user_id,
                            "campaign_id": str(campaign['_id']),
                            "campaign_name": campaign['name'],
                            "contact_id": str(contact['_id']),
                            "contact_name": f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip(),
                            "contact_phone": contact.get('phone', ''),
                            "current_step": 1,
                            "total_steps": len(campaign.get('sequences', [])),
                            "status": "active",
                            "enrolled_at": today,
                            "next_send_at": today,
                            "messages_sent": [],
                            "trigger_type": "anniversary"
                        }
                        await db.campaign_enrollments.insert_one(enrollment)
                        enrolled_count += 1
                        logger.info(f"Auto-enrolled {enrollment['contact_name']} in anniversary campaign: {campaign['name']}")
    
    return {
        "message": f"Date trigger check complete",
        "enrolled": enrolled_count,
        "birthday_campaigns": len(birthday_campaigns),
        "anniversary_campaigns": len(anniversary_campaigns)
    }
