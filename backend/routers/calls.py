"""
Calls router - handles call logs and dialer functionality
"""
from fastapi import APIRouter, HTTPException
from bson import ObjectId
from datetime import datetime
from typing import Optional
import logging

from models import Call, CallCreate
from routers.database import get_db, get_data_filter, increment_user_stat

router = APIRouter(prefix="/calls", tags=["Calls"])
logger = logging.getLogger(__name__)

@router.post("/{user_id}", response_model=Call)
async def create_call_log(user_id: str, call_data: CallCreate):
    """Log a call"""
    call_dict = call_data.dict()
    call_dict['user_id'] = user_id
    call_dict['timestamp'] = datetime.utcnow()
    
    result = await get_db().calls.insert_one(call_dict)
    call_dict['_id'] = result.inserted_id
    
    # Track stat
    await increment_user_stat(user_id, "calls_made")
    
    # If missed call, send auto-text (mocked)
    if call_data.type == "missed":
        try:
            contact = await get_db().contacts.find_one({"_id": ObjectId(call_data.contact_id)})
        except:
            contact = await get_db().contacts.find_one({"_id": call_data.contact_id})
        
        if contact:
            logger.info(f"[MOCK] Auto-text sent to {contact['first_name']}: Hey, I just missed your call!")
            call_dict['auto_text_sent'] = True
            await get_db().calls.update_one(
                {"_id": result.inserted_id},
                {"$set": {"auto_text_sent": True}}
            )
    
    return Call(**call_dict)

@router.get("/{user_id}")
async def get_call_logs(user_id: str, call_type: Optional[str] = None):
    """Get call logs with role-based access"""
    # Get role-based data filter
    base_filter = await get_data_filter(user_id)
    
    if call_type:
        query = {"$and": [base_filter, {"type": call_type}]}
    else:
        query = base_filter
    
    calls = await get_db().calls.find(query).sort("timestamp", -1).limit(500).to_list(500)
    
    # Enrich with contact info
    result = []
    for call in calls:
        call['_id'] = str(call['_id'])
        try:
            contact = await get_db().contacts.find_one({"_id": ObjectId(call['contact_id'])})
        except:
            contact = await get_db().contacts.find_one({"_id": call['contact_id']})
        
        if contact:
            call['contact'] = {
                "name": f"{contact['first_name']} {contact.get('last_name', '')}".strip(),
                "phone": contact['phone']
            }
        result.append(call)
    
    return result

@router.post("/{user_id}/initiate")
async def initiate_call(user_id: str, data: dict):
    """Initiate an outgoing call (mocked - Twilio pending)"""
    phone_number = data.get('phone_number')
    contact_id = data.get('contact_id')
    
    if not phone_number:
        raise HTTPException(status_code=400, detail="Phone number is required")
    
    # In production, this would initiate a Twilio call
    logger.info(f"[MOCK] Initiating call to {phone_number}")
    
    # Log the call
    call_dict = {
        "user_id": user_id,
        "contact_id": contact_id,
        "phone_number": phone_number,
        "type": "outgoing",
        "duration": 0,
        "status": "initiated",
        "timestamp": datetime.utcnow()
    }
    
    result = await get_db().calls.insert_one(call_dict)
    call_dict['_id'] = str(result.inserted_id)
    
    return {
        "message": "Call initiated (mocked)",
        "call_id": call_dict['_id'],
        "status": "initiated"
    }
