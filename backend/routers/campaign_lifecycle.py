"""
Campaign Lifecycle Router - Automated follow-up campaigns
Features:
- Sold campaign with customizable cadence
- Holiday campaigns (Thanksgiving, Christmas, etc.)
- Birthday campaigns
- Purchase anniversary
- Auto-enrollment from congrats cards
- Permission controls
"""
from fastapi import APIRouter, HTTPException
from bson import ObjectId
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from pydantic import BaseModel
from routers.database import get_db
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/campaigns", tags=["campaigns"])


# ============= MODELS =============
class CampaignStep(BaseModel):
    day: int  # Day offset from enrollment (0 = same day, 1 = next day, etc.)
    message: str
    enabled: bool = True
    time_of_day: str = "10:00"  # When to send (HH:MM)


class CampaignTemplate(BaseModel):
    name: str
    description: str
    type: str  # sold, birthday, holiday, anniversary, custom
    steps: List[CampaignStep]
    pause_on_reply: bool = True
    skip_weekends: bool = False
    active: bool = True


class EnrollmentData(BaseModel):
    contact_id: str
    contact_name: str
    contact_phone: str
    enrolled_by: str  # salesman_id
    trigger: str  # congrats_card, review_invite, manual
    purchase_date: Optional[str] = None
    purchase_details: Optional[str] = None


# ============= DEFAULT SOLD CAMPAIGN =============
DEFAULT_SOLD_CAMPAIGN = {
    "name": "Sold - New Customer",
    "description": "Post-sale follow-up sequence for new customers",
    "type": "sold",
    "steps": [
        {
            "day": 1,
            "message": "Hey {customer_first_name}! It's {salesman_first_name}. Just wanted to check in - any questions about your new {purchase} I may have forgot to go over? I'm here to help!",
            "enabled": True,
            "time_of_day": "10:00"
        },
        {
            "day": 7,
            "message": "Hope you're loving the new {purchase}, {customer_first_name}! 🚗 If any of your friends or family are looking, I'd love to help them out too. Just send them my way!",
            "enabled": True,
            "time_of_day": "11:00"
        },
        {
            "day": 14,
            "message": "Hey {customer_first_name}! Quick favor - if you have a minute, would you mind leaving us a quick review? It really helps! {review_link}",
            "enabled": True,
            "time_of_day": "14:00"
        },
        {
            "day": 30,
            "message": "Hey {customer_first_name}, it's been a month! How's everything going with the {purchase}? Let me know if you need anything!",
            "enabled": True,
            "time_of_day": "10:00"
        },
        {
            "day": 75,
            "message": "Hi {customer_first_name}! Coming up on your first service - want me to help you get that scheduled? I can make sure they take great care of you!",
            "enabled": True,
            "time_of_day": "09:00"
        },
        {
            "day": 365,
            "message": "Wow {customer_first_name}, can't believe it's been a YEAR! 🎉 Is it worn out yet? 😂 Hope you're still loving it. Let me know if there's anything I can do for you!",
            "enabled": True,
            "time_of_day": "10:00"
        }
    ],
    "pause_on_reply": True,
    "skip_weekends": True,
    "active": True
}

# ============= HOLIDAY CAMPAIGNS =============
HOLIDAY_CAMPAIGNS = {
    "thanksgiving": {
        "name": "Thanksgiving",
        "message": "Happy Thanksgiving, {customer_first_name}! 🦃 Hope you have a wonderful day with your family. - {salesman_first_name}",
        "month": 11,  # November
        "week": 4,  # 4th week
        "weekday": 3  # Thursday
    },
    "christmas": {
        "name": "Christmas/Holidays",
        "message": "Happy Holidays, {customer_first_name}! 🎄 Wishing you and your family a joyful season. Enjoy the time with your loved ones! - {salesman_first_name}",
        "month": 12,
        "day": 24
    },
    "new_year": {
        "name": "New Year",
        "message": "Happy New Year, {customer_first_name}! 🎉 Wishing you an amazing year ahead. Here's to new adventures! - {salesman_first_name}",
        "month": 1,
        "day": 1
    },
    "july_4th": {
        "name": "4th of July",
        "message": "Happy 4th of July, {customer_first_name}! 🇺🇸 Hope you have a great day celebrating! - {salesman_first_name}",
        "month": 7,
        "day": 4
    },
    "memorial_day": {
        "name": "Memorial Day",
        "message": "Happy Memorial Day, {customer_first_name}! Taking a moment to honor those who served. Hope you have a meaningful day. - {salesman_first_name}",
        "month": 5,
        "week": -1,  # Last week
        "weekday": 0  # Monday
    },
    "labor_day": {
        "name": "Labor Day",
        "message": "Happy Labor Day, {customer_first_name}! Hope you're enjoying the long weekend! - {salesman_first_name}",
        "month": 9,
        "week": 1,  # First week
        "weekday": 0  # Monday
    }
}


# ============= STORE CAMPAIGN SETTINGS =============
@router.get("/settings/{store_id}")
async def get_campaign_settings(store_id: str):
    """Get campaign settings for a store"""
    db = get_db()
    
    settings = await db.campaign_settings.find_one({"store_id": store_id})
    
    if not settings:
        # Return defaults
        return {
            "store_id": store_id,
            "sold_campaign": DEFAULT_SOLD_CAMPAIGN,
            "holidays_enabled": True,
            "birthdays_enabled": True,
            "anniversaries_enabled": True,
            "permissions": {
                "managers_can_edit_campaigns": True,
                "salespeople_can_edit_own_cadence": False,
                "salespeople_can_pause_campaigns": True,
                "salespeople_can_skip_steps": True
            }
        }
    
    # Don't return _id
    settings.pop("_id", None)
    return settings


@router.post("/settings/{store_id}")
async def save_campaign_settings(store_id: str, data: dict):
    """Save campaign settings for a store"""
    db = get_db()
    
    data["store_id"] = store_id
    data["updated_at"] = datetime.now(timezone.utc)
    
    await db.campaign_settings.update_one(
        {"store_id": store_id},
        {"$set": data, "$setOnInsert": {"created_at": datetime.now(timezone.utc)}},
        upsert=True
    )
    
    return {"success": True, "message": "Campaign settings saved"}


# ============= CAMPAIGN TEMPLATES =============
@router.get("/templates/{store_id}")
async def get_campaign_templates(store_id: str):
    """Get all campaign templates for a store"""
    db = get_db()
    
    templates = await db.campaign_templates.find(
        {"store_id": store_id}
    ).to_list(100)
    
    # If no custom templates, return defaults
    if not templates:
        return [{
            "id": "default_sold",
            "is_default": True,
            **DEFAULT_SOLD_CAMPAIGN
        }]
    
    return [{
        "id": str(t["_id"]),
        "is_default": False,
        **{k: v for k, v in t.items() if k not in ["_id", "store_id"]}
    } for t in templates]


@router.post("/templates/{store_id}")
async def create_campaign_template(store_id: str, template: CampaignTemplate):
    """Create a new campaign template for a store"""
    db = get_db()
    
    template_dict = template.dict()
    template_dict["store_id"] = store_id
    template_dict["created_at"] = datetime.now(timezone.utc)
    
    result = await db.campaign_templates.insert_one(template_dict)
    
    return {
        "success": True,
        "template_id": str(result.inserted_id),
        "message": "Campaign template created"
    }


@router.put("/templates/{store_id}/{template_id}")
async def update_campaign_template(store_id: str, template_id: str, template: CampaignTemplate):
    """Update a campaign template"""
    db = get_db()
    
    template_dict = template.dict()
    template_dict["updated_at"] = datetime.now(timezone.utc)
    
    result = await db.campaign_templates.update_one(
        {"_id": ObjectId(template_id), "store_id": store_id},
        {"$set": template_dict}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Template not found")
    
    return {"success": True, "message": "Template updated"}


# ============= ENROLLMENT =============
@router.post("/enroll")
async def enroll_in_campaign(data: EnrollmentData, campaign_id: str = "default_sold"):
    """Enroll a contact in a campaign"""
    db = get_db()
    
    # Get salesman info
    try:
        salesman = await db.users.find_one({"_id": ObjectId(data.enrolled_by)})
    except Exception:
        raise HTTPException(status_code=404, detail="Salesman not found")
    
    if not salesman:
        raise HTTPException(status_code=404, detail="Salesman not found")
    
    store_id = salesman.get("store_id")
    
    # Get campaign template
    if campaign_id == "default_sold":
        campaign = DEFAULT_SOLD_CAMPAIGN.copy()
    else:
        campaign = await db.campaign_templates.find_one({"_id": ObjectId(campaign_id)})
        if not campaign:
            campaign = DEFAULT_SOLD_CAMPAIGN.copy()
    
    # Create enrollment
    enrollment = {
        "contact_id": data.contact_id,
        "contact_name": data.contact_name,
        "contact_phone": data.contact_phone,
        "salesman_id": data.enrolled_by,
        "salesman_name": salesman.get("name", ""),
        "store_id": store_id,
        "campaign_id": campaign_id,
        "campaign_name": campaign.get("name", "Sold Campaign"),
        "trigger": data.trigger,
        "purchase_date": data.purchase_date or datetime.now(timezone.utc).isoformat(),
        "purchase_details": data.purchase_details,
        "enrolled_at": datetime.now(timezone.utc),
        "current_step": 0,
        "status": "active",  # active, paused, completed, cancelled
        "steps_completed": [],
        "next_send_date": None,
        "paused_reason": None
    }
    
    # Calculate first step send date
    steps = campaign.get("steps", [])
    if steps:
        first_step = steps[0]
        enrollment["next_send_date"] = calculate_next_send_date(
            first_step["day"],
            first_step.get("time_of_day", "10:00"),
            campaign.get("skip_weekends", False)
        )
    
    result = await db.campaign_enrollments.insert_one(enrollment)
    
    return {
        "success": True,
        "enrollment_id": str(result.inserted_id),
        "message": f"Enrolled in {campaign.get('name', 'campaign')}",
        "next_message_date": enrollment["next_send_date"].isoformat() if enrollment["next_send_date"] else None
    }


def calculate_next_send_date(day_offset: int, time_of_day: str, skip_weekends: bool) -> datetime:
    """Calculate when the next message should be sent"""
    now = datetime.now(timezone.utc)
    
    # Parse time
    hour, minute = map(int, time_of_day.split(":"))
    
    # Calculate target date
    target = now + timedelta(days=day_offset)
    target = target.replace(hour=hour, minute=minute, second=0, microsecond=0)
    
    # Skip weekends if needed
    if skip_weekends:
        while target.weekday() >= 5:  # Saturday = 5, Sunday = 6
            target += timedelta(days=1)
    
    return target


# ============= ENROLLMENT MANAGEMENT =============
@router.get("/enrollments/{salesman_id}")
async def get_my_enrollments(salesman_id: str, status: str = "active"):
    """Get all campaign enrollments for a salesman"""
    db = get_db()
    
    query = {"salesman_id": salesman_id}
    if status != "all":
        query["status"] = status
    
    enrollments = await db.campaign_enrollments.find(query).sort("enrolled_at", -1).to_list(100)
    
    return [{
        "id": str(e["_id"]),
        "contact_name": e.get("contact_name"),
        "contact_phone": e.get("contact_phone"),
        "campaign_name": e.get("campaign_name"),
        "status": e.get("status"),
        "current_step": e.get("current_step"),
        "next_send_date": e.get("next_send_date").isoformat() if e.get("next_send_date") else None,
        "enrolled_at": e.get("enrolled_at").isoformat() if e.get("enrolled_at") else None,
    } for e in enrollments]


@router.post("/enrollments/{enrollment_id}/pause")
async def pause_enrollment(enrollment_id: str, reason: str = "manual"):
    """Pause a campaign enrollment"""
    db = get_db()
    
    result = await db.campaign_enrollments.update_one(
        {"_id": ObjectId(enrollment_id)},
        {"$set": {
            "status": "paused",
            "paused_reason": reason,
            "paused_at": datetime.now(timezone.utc)
        }}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Enrollment not found")
    
    return {"success": True, "message": "Campaign paused"}


@router.post("/enrollments/{enrollment_id}/resume")
async def resume_enrollment(enrollment_id: str):
    """Resume a paused campaign enrollment"""
    db = get_db()
    
    enrollment = await db.campaign_enrollments.find_one({"_id": ObjectId(enrollment_id)})
    if not enrollment:
        raise HTTPException(status_code=404, detail="Enrollment not found")
    
    # Recalculate next send date based on current step
    # For now, just set to active
    await db.campaign_enrollments.update_one(
        {"_id": ObjectId(enrollment_id)},
        {"$set": {
            "status": "active",
            "paused_reason": None,
            "resumed_at": datetime.now(timezone.utc)
        }}
    )
    
    return {"success": True, "message": "Campaign resumed"}


@router.post("/enrollments/{enrollment_id}/skip")
async def skip_step(enrollment_id: str):
    """Skip the current step in a campaign"""
    db = get_db()
    
    enrollment = await db.campaign_enrollments.find_one({"_id": ObjectId(enrollment_id)})
    if not enrollment:
        raise HTTPException(status_code=404, detail="Enrollment not found")
    
    current_step = enrollment.get("current_step", 0)
    
    await db.campaign_enrollments.update_one(
        {"_id": ObjectId(enrollment_id)},
        {
            "$set": {"current_step": current_step + 1},
            "$push": {"steps_completed": {
                "step": current_step,
                "skipped": True,
                "skipped_at": datetime.now(timezone.utc)
            }}
        }
    )
    
    return {"success": True, "message": "Step skipped"}


# ============= BIRTHDAY CAMPAIGNS =============
@router.post("/birthday/update/{contact_id}")
async def update_contact_birthday(contact_id: str, birthday: str):
    """Update a contact's birthday for birthday campaigns"""
    db = get_db()
    
    # Parse birthday (MM-DD or YYYY-MM-DD)
    try:
        if len(birthday) == 5:  # MM-DD
            month, day = map(int, birthday.split("-"))
            birthday_data = {"month": month, "day": day}
        else:  # YYYY-MM-DD
            parts = birthday.split("-")
            birthday_data = {
                "year": int(parts[0]) if len(parts) > 2 else None,
                "month": int(parts[1] if len(parts) > 2 else parts[0]),
                "day": int(parts[2] if len(parts) > 2 else parts[1])
            }
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid birthday format. Use MM-DD or YYYY-MM-DD")
    
    await db.contacts.update_one(
        {"_id": ObjectId(contact_id)},
        {"$set": {"birthday": birthday_data}}
    )
    
    return {"success": True, "message": "Birthday saved"}


@router.get("/birthdays/upcoming/{salesman_id}")
async def get_upcoming_birthdays(salesman_id: str, days: int = 30):
    """Get contacts with upcoming birthdays"""
    db = get_db()
    
    today = datetime.now(timezone.utc)
    
    # Get all contacts with birthdays
    contacts = await db.contacts.find({
        "owner_id": salesman_id,
        "birthday": {"$exists": True}
    }).to_list(500)
    
    upcoming = []
    for contact in contacts:
        birthday = contact.get("birthday", {})
        if not birthday.get("month") or not birthday.get("day"):
            continue
        
        # Calculate this year's birthday
        try:
            this_year_bday = datetime(today.year, birthday["month"], birthday["day"], tzinfo=timezone.utc)
            if this_year_bday < today:
                this_year_bday = datetime(today.year + 1, birthday["month"], birthday["day"], tzinfo=timezone.utc)
            
            days_until = (this_year_bday - today).days
            
            if 0 <= days_until <= days:
                upcoming.append({
                    "contact_id": str(contact["_id"]),
                    "name": contact.get("name"),
                    "phone": contact.get("phone"),
                    "birthday": f"{birthday['month']:02d}-{birthday['day']:02d}",
                    "days_until": days_until,
                    "date": this_year_bday.strftime("%B %d")
                })
        except Exception:
            continue
    
    # Sort by days until birthday
    upcoming.sort(key=lambda x: x["days_until"])
    
    return upcoming


# ============= HOLIDAY SCHEDULE =============
@router.get("/holidays/schedule")
async def get_holiday_schedule():
    """Get the holiday campaign schedule"""
    return HOLIDAY_CAMPAIGNS


@router.get("/holidays/upcoming")
async def get_upcoming_holidays(days: int = 60):
    """Get upcoming holidays in the next N days"""
    today = datetime.now(timezone.utc)
    upcoming = []
    
    for key, holiday in HOLIDAY_CAMPAIGNS.items():
        # Calculate this year's date
        try:
            if "day" in holiday:
                holiday_date = datetime(today.year, holiday["month"], holiday["day"], tzinfo=timezone.utc)
            elif "week" in holiday:
                # Calculate based on week of month
                first_of_month = datetime(today.year, holiday["month"], 1, tzinfo=timezone.utc)
                if holiday["week"] == -1:  # Last week
                    # Find last occurrence of weekday in month
                    if holiday["month"] == 12:
                        next_month = datetime(today.year + 1, 1, 1, tzinfo=timezone.utc)
                    else:
                        next_month = datetime(today.year, holiday["month"] + 1, 1, tzinfo=timezone.utc)
                    last_day = next_month - timedelta(days=1)
                    while last_day.weekday() != holiday["weekday"]:
                        last_day -= timedelta(days=1)
                    holiday_date = last_day
                else:
                    # Find nth occurrence of weekday
                    current = first_of_month
                    while current.weekday() != holiday["weekday"]:
                        current += timedelta(days=1)
                    holiday_date = current + timedelta(weeks=holiday["week"] - 1)
            else:
                continue
            
            # If passed, calculate next year
            if holiday_date < today:
                holiday_date = holiday_date.replace(year=today.year + 1)
            
            days_until = (holiday_date - today).days
            
            if 0 <= days_until <= days:
                upcoming.append({
                    "key": key,
                    "name": holiday["name"],
                    "date": holiday_date.strftime("%B %d, %Y"),
                    "days_until": days_until,
                    "message_preview": holiday["message"][:100] + "..."
                })
        except Exception as e:
            logger.warning(f"Error calculating holiday {key}: {e}")
            continue
    
    upcoming.sort(key=lambda x: x["days_until"])
    return upcoming


# ============= TRIGGER FROM CONGRATS CARD =============
@router.post("/trigger/congrats-card")
async def trigger_from_congrats_card(data: dict):
    """
    Trigger campaign enrollment from a congrats card.
    Called automatically when a congrats card is created.
    """
    db = get_db()
    
    salesman_id = data.get("salesman_id")
    customer_name = data.get("customer_name")
    customer_phone = data.get("customer_phone")
    
    if not all([salesman_id, customer_name]):
        return {"success": False, "message": "Missing required fields"}
    
    # Find or create contact
    contact = None
    if customer_phone:
        contact = await db.contacts.find_one({
            "owner_id": salesman_id,
            "phone": customer_phone
        })
    
    contact_id = str(contact["_id"]) if contact else None
    
    # Enroll in sold campaign
    enrollment_data = EnrollmentData(
        contact_id=contact_id or "new",
        contact_name=customer_name,
        contact_phone=customer_phone or "",
        enrolled_by=salesman_id,
        trigger="congrats_card",
        purchase_date=datetime.now(timezone.utc).isoformat()
    )
    
    result = await enroll_in_campaign(enrollment_data, "default_sold")
    
    return result
