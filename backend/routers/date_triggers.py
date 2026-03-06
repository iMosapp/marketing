"""
Date Triggers Router
Handles automated date-based messaging: birthdays, anniversaries, sold dates, and holidays.
Contacts with matching dates automatically receive messages using saved templates.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
import logging
import os
import asyncio

from routers.database import get_db, get_data_filter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/date-triggers", tags=["Date Triggers"])

# US holidays with fixed dates (month, day)
AVAILABLE_HOLIDAYS = [
    {"id": "new_years", "name": "New Year's Day", "month": 1, "day": 1},
    {"id": "valentines", "name": "Valentine's Day", "month": 2, "day": 14},
    {"id": "st_patricks", "name": "St. Patrick's Day", "month": 3, "day": 17},
    {"id": "mothers_day", "name": "Mother's Day", "month": 5, "day": 12, "note": "2nd Sunday of May (approx)"},
    {"id": "memorial_day", "name": "Memorial Day", "month": 5, "day": 27, "note": "Last Monday of May (approx)"},
    {"id": "fathers_day", "name": "Father's Day", "month": 6, "day": 15, "note": "3rd Sunday of June (approx)"},
    {"id": "independence_day", "name": "Independence Day", "month": 7, "day": 4},
    {"id": "labor_day", "name": "Labor Day", "month": 9, "day": 1, "note": "1st Monday of Sept (approx)"},
    {"id": "halloween", "name": "Halloween", "month": 10, "day": 31},
    {"id": "veterans_day", "name": "Veterans Day", "month": 11, "day": 11},
    {"id": "thanksgiving", "name": "Thanksgiving", "month": 11, "day": 28, "note": "4th Thursday of Nov (approx)"},
    {"id": "christmas_eve", "name": "Christmas Eve", "month": 12, "day": 24},
    {"id": "christmas", "name": "Christmas Day", "month": 12, "day": 25},
    {"id": "new_years_eve", "name": "New Year's Eve", "month": 12, "day": 31},
]


class DateTriggerConfig(BaseModel):
    trigger_type: str  # birthday, anniversary, sold_date, holiday
    enabled: bool = True
    delivery_method: str = "sms"  # sms, email, both
    message_template: str = ""
    holiday_id: Optional[str] = None  # Only for holiday type
    include_birthday_card: Optional[bool] = True  # Auto-generate birthday card


class DateTriggerConfigUpdate(BaseModel):
    enabled: Optional[bool] = None
    delivery_method: Optional[str] = None
    message_template: Optional[str] = None


# ============= GET AVAILABLE HOLIDAYS =============
@router.get("/holidays")
async def get_holidays():
    """Return list of available holidays"""
    return AVAILABLE_HOLIDAYS


# ============= GET USER'S DATE TRIGGER CONFIG =============
@router.get("/{user_id}/config")
async def get_date_trigger_config(user_id: str):
    """Get all date trigger configurations for a user"""
    db = get_db()
    
    configs = await db.date_trigger_configs.find(
        {"user_id": user_id},
        {"_id": 0}
    ).to_list(100)
    
    return configs


# ============= UPSERT DATE TRIGGER CONFIG =============
@router.put("/{user_id}/config/{trigger_type}")
async def upsert_date_trigger_config(user_id: str, trigger_type: str, config: DateTriggerConfig):
    """Create or update a date trigger configuration"""
    db = get_db()
    
    valid_types = ["birthday", "anniversary", "sold_date"]
    if trigger_type not in valid_types and not trigger_type.startswith("holiday_"):
        raise HTTPException(status_code=400, detail=f"Invalid trigger type. Use: {valid_types} or holiday_<id>")
    
    doc = {
        "user_id": user_id,
        "trigger_type": trigger_type,
        "enabled": config.enabled,
        "delivery_method": config.delivery_method,
        "message_template": config.message_template,
        "holiday_id": config.holiday_id,
        "include_birthday_card": config.include_birthday_card if trigger_type == "birthday" else None,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    
    await db.date_trigger_configs.update_one(
        {"user_id": user_id, "trigger_type": trigger_type},
        {"$set": doc},
        upsert=True
    )
    
    return {"message": "Configuration saved", "trigger_type": trigger_type}


# ============= DELETE DATE TRIGGER CONFIG =============
@router.delete("/{user_id}/config/{trigger_type}")
async def delete_date_trigger_config(user_id: str, trigger_type: str):
    """Delete a date trigger configuration"""
    db = get_db()
    await db.date_trigger_configs.delete_one({"user_id": user_id, "trigger_type": trigger_type})
    return {"message": "Configuration deleted"}


# ============= BULK UPDATE HOLIDAY CONFIGS =============
@router.put("/{user_id}/holidays")
async def update_holiday_configs(user_id: str, holidays: List[dict]):
    """Update all holiday trigger configs at once"""
    db = get_db()
    
    # Remove all existing holiday configs for this user
    await db.date_trigger_configs.delete_many({
        "user_id": user_id,
        "trigger_type": {"$regex": "^holiday_"}
    })
    
    # Insert new ones
    for h in holidays:
        if h.get("enabled"):
            doc = {
                "user_id": user_id,
                "trigger_type": f"holiday_{h['id']}",
                "enabled": True,
                "delivery_method": h.get("delivery_method", "sms"),
                "message_template": h.get("message_template", ""),
                "holiday_id": h["id"],
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            await db.date_trigger_configs.insert_one(doc)
    
    return {"message": f"Holiday configs updated", "count": len([h for h in holidays if h.get('enabled')])}


# ============= PROCESS DATE TRIGGERS =============
@router.post("/{user_id}/process")
async def process_date_triggers(user_id: str):
    """
    Check all contacts for matching dates and send messages.
    Handles: birthdays, anniversaries, sold dates, and holidays.
    Should be called daily (e.g., via cron or admin action).
    """
    db = get_db()
    
    # Get user's timezone
    user = await db.users.find_one({"_id": __import__('bson').ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user_tz = user.get("timezone", "America/Denver")
    
    # Get today's date in user's timezone
    try:
        import pytz
        tz = pytz.timezone(user_tz)
        local_now = datetime.now(tz)
    except Exception:
        local_now = datetime.now(timezone.utc)
    
    today_month = local_now.month
    today_day = local_now.day
    
    # Get user's trigger configs
    configs = await db.date_trigger_configs.find(
        {"user_id": user_id, "enabled": True}
    ).to_list(100)
    
    if not configs:
        return {"message": "No active date triggers configured", "sent": 0}
    
    base_filter = await get_data_filter(user_id)
    sent_count = 0
    results = []
    
    for config in configs:
        trigger_type = config["trigger_type"]
        template = config.get("message_template", "")
        delivery = config.get("delivery_method", "sms")
        
        if not template:
            continue
        
        contacts_to_message = []
        
        if trigger_type in ("birthday", "anniversary", "sold_date"):
            # Map trigger type to contact field
            field_map = {
                "birthday": "birthday",
                "anniversary": "anniversary",
                "sold_date": "date_sold",
            }
            date_field = field_map[trigger_type]
            
            # Find contacts with this date field set
            contacts = await db.contacts.find({
                **base_filter,
                date_field: {"$exists": True, "$ne": None}
            }).to_list(1000)
            
            for contact in contacts:
                dt = contact.get(date_field)
                if dt and isinstance(dt, datetime):
                    if dt.month == today_month and dt.day == today_day:
                        contacts_to_message.append(contact)
        
        elif trigger_type.startswith("holiday_"):
            # Holiday trigger  - find matching holiday
            holiday_id = config.get("holiday_id") or trigger_type.replace("holiday_", "")
            holiday = next((h for h in AVAILABLE_HOLIDAYS if h["id"] == holiday_id), None)
            
            if holiday and holiday["month"] == today_month and holiday["day"] == today_day:
                # Send to all contacts tagged "Holiday" or "Holidays"
                contacts = await db.contacts.find({
                    **base_filter,
                    "tags": {"$in": ["Holiday", "Holidays", "holiday", "holidays"]}
                }).to_list(1000)
                contacts_to_message = contacts
        
        # Send messages to matched contacts
        for contact in contacts_to_message:
            contact_id = str(contact["_id"])
            contact_name = f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip()
            
            # Check if already sent today (avoid duplicates)
            today_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
            already_sent = await db.date_trigger_log.find_one({
                "user_id": user_id,
                "contact_id": contact_id,
                "trigger_type": trigger_type,
                "sent_at": {"$gte": today_start.isoformat()}
            })
            
            if already_sent:
                continue
            
            # Personalize template
            message = template.replace("{first_name}", contact.get("first_name", ""))
            message = message.replace("{last_name}", contact.get("last_name", ""))
            message = message.replace("{name}", contact_name)
            message = message.replace("{phone}", contact.get("phone", ""))
            
            # Send via configured method
            send_result = {"sms": False, "email": False}

            # Auto-create birthday card if this is a birthday trigger with include_birthday_card
            if trigger_type == "birthday" and config.get("include_birthday_card", True):
                try:
                    from routers.birthday_cards import auto_create_birthday_card
                    bday_result = await auto_create_birthday_card(user_id, contact_id, custom_message=None)
                    if bday_result and bday_result.get("short_url"):
                        message += f"\n\nView your birthday card: {bday_result['short_url']}"
                        logger.info(f"[DateTrigger] Birthday card created for {contact_name}: {bday_result.get('card_id')}")
                    elif bday_result and bday_result.get("already_exists"):
                        # Card already exists today, look up its URL
                        existing_card = await db.birthday_cards.find_one(
                            {"card_id": bday_result["card_id"]}, {"short_url": 1, "card_id": 1}
                        )
                        if existing_card and existing_card.get("short_url"):
                            message += f"\n\nView your birthday card: {existing_card['short_url']}"
                except Exception as e:
                    logger.error(f"[DateTrigger] Birthday card creation failed for {contact_name}: {e}")
            
            if delivery in ("sms", "both") and contact.get("phone"):
                # Queue SMS via existing message system
                try:
                    await db.messages.insert_one({
                        "conversation_id": f"auto_{user_id}_{contact_id}",
                        "sender": "user",
                        "content": message,
                        "timestamp": datetime.now(timezone.utc),
                        "auto_sent": True,
                        "trigger_type": trigger_type,
                        "template_type": trigger_type.split("_")[0] if not trigger_type.startswith("holiday") else "holiday",
                    })
                    send_result["sms"] = True
                except Exception as e:
                    logger.error(f"SMS send failed for {contact_name}: {e}")
            
            if delivery in ("email", "both") and contact.get("email"):
                try:
                    resend_key = os.environ.get("RESEND_API_KEY")
                    if resend_key:
                        import resend
                        resend.api_key = resend_key
                        sender_name = user.get('name', "i'M On Social")
                        await asyncio.to_thread(resend.Emails.send, {
                            "from": f"{sender_name} <{os.environ.get('SENDER_EMAIL', 'notifications@send.imonsocial.com')}>",
                            "to": contact["email"],
                            "reply_to": user.get('email', 'support@imonsocial.com'),
                            "subject": f"A message from {sender_name}",
                            "html": f"<div style='font-family:sans-serif;max-width:500px;margin:0 auto;padding:20px;'><p>{message}</p></div>"
                        })
                        send_result["email"] = True
                except Exception as e:
                    logger.error(f"Email send failed for {contact_name}: {e}")
            
            # Log the send
            await db.date_trigger_log.insert_one({
                "user_id": user_id,
                "contact_id": contact_id,
                "contact_name": contact_name,
                "trigger_type": trigger_type,
                "delivery_method": delivery,
                "message_preview": message[:100],
                "send_result": send_result,
                "sent_at": datetime.now(timezone.utc).isoformat(),
            })
            
            sent_count += 1
            results.append({
                "contact": contact_name,
                "trigger": trigger_type,
                "delivery": delivery,
            })
    
    return {
        "message": f"Date triggers processed. {sent_count} messages sent.",
        "sent": sent_count,
        "details": results,
    }


# ============= GET TRIGGER LOG =============
@router.get("/{user_id}/log")
async def get_trigger_log(user_id: str, limit: int = 50):
    """Get recent date trigger send log"""
    db = get_db()
    logs = await db.date_trigger_log.find(
        {"user_id": user_id},
        {"_id": 0}
    ).sort("sent_at", -1).limit(limit).to_list(limit)
    return logs


# ============= AUTO-TAG CONTACT ON DATE SAVE =============
async def auto_tag_contact_for_dates(contact_data: dict, db):
    """When a contact has date fields, auto-apply matching tags"""
    tags_to_add = []
    
    if contact_data.get("birthday"):
        tags_to_add.append("Birthday")
    if contact_data.get("anniversary"):
        tags_to_add.append("Anniversary")
    if contact_data.get("date_sold"):
        tags_to_add.append("Sold Date")
    
    return tags_to_add
