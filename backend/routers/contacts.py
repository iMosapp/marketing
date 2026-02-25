"""
Contacts router - handles contact CRUD operations
"""
from fastapi import APIRouter, HTTPException
from bson import ObjectId
from datetime import datetime
from typing import List, Optional
import logging

from models import Contact, ContactCreate
from routers.database import get_db, get_data_filter, increment_user_stat

router = APIRouter(prefix="/contacts", tags=["Contacts"])
logger = logging.getLogger(__name__)

@router.post("/{user_id}", response_model=Contact)
async def create_contact(user_id: str, contact_data: ContactCreate):
    """Create a new contact"""
    contact_dict = contact_data.dict()
    contact_dict['user_id'] = user_id
    contact_dict['created_at'] = datetime.utcnow()
    contact_dict['updated_at'] = datetime.utcnow()
    
    # Auto-tag based on date fields
    existing_tags = set(contact_dict.get('tags', []))
    if contact_dict.get('birthday'):
        existing_tags.add('Birthday')
    if contact_dict.get('anniversary'):
        existing_tags.add('Anniversary')
    if contact_dict.get('date_sold'):
        existing_tags.add('Sold Date')
    contact_dict['tags'] = list(existing_tags)
    
    result = await get_db().contacts.insert_one(contact_dict)
    contact_dict['_id'] = result.inserted_id
    
    # Auto-enroll in tag-triggered campaigns
    await _check_tag_campaign_enrollment(user_id, str(result.inserted_id), contact_dict)
    
    # Track stat for leaderboard
    await increment_user_stat(user_id, "contacts_added")
    
    return Contact(**contact_dict)

@router.get("/{user_id}", response_model=List[Contact])
async def get_contacts(user_id: str, search: Optional[str] = None):
    """Get all contacts accessible to a user based on their role"""
    db = get_db()
    base_filter = await get_data_filter(user_id)
    
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
    
    contacts = await db.contacts.find(query).sort("first_name", 1).limit(500).to_list(500)
    return [Contact(**{**c, "_id": str(c["_id"])}) for c in contacts]

@router.get("/{user_id}/{contact_id}", response_model=Contact)
async def get_contact(user_id: str, contact_id: str):
    """Get a specific contact with role-based access check"""
    # Get role-based data filter
    base_filter = await get_data_filter(user_id)
    
    try:
        contact = await get_db().contacts.find_one({
            "$and": [
                {"_id": ObjectId(contact_id)},
                base_filter
            ]
        })
    except:
        contact = await get_db().contacts.find_one({
            "$and": [
                {"_id": contact_id},
                base_filter
            ]
        })
    
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    contact['_id'] = str(contact['_id'])
    return Contact(**contact)

@router.put("/{user_id}/{contact_id}")
async def update_contact(user_id: str, contact_id: str, contact_data: ContactCreate):
    """Update a contact with role-based access check"""
    # Get role-based data filter
    base_filter = await get_data_filter(user_id)
    
    update_dict = contact_data.dict()
    update_dict['updated_at'] = datetime.utcnow()
    
    # If setting a referrer, update the referrer's count
    if contact_data.referred_by:
        # Increment referrer's referral_count (only if accessible)
        await get_db().contacts.update_one(
            {"$and": [{"_id": contact_data.referred_by}, base_filter]},
            {"$inc": {"referral_count": 1}}
        )
    
    try:
        result = await get_db().contacts.update_one(
            {"$and": [{"_id": ObjectId(contact_id)}, base_filter]},
            {"$set": update_dict}
        )
    except:
        result = await get_db().contacts.update_one(
            {"$and": [{"_id": contact_id}, base_filter]},
            {"$set": update_dict}
        )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    return {"message": "Contact updated successfully"}

@router.get("/{user_id}/{contact_id}/referrals")
async def get_contact_referrals(user_id: str, contact_id: str):
    """Get all contacts referred by this contact with role-based access"""
    # Get role-based data filter
    base_filter = await get_data_filter(user_id)
    
    referrals = await get_db().contacts.find({
        "$and": [
            base_filter,
            {"referred_by": contact_id}
        ]
    }).limit(100).to_list(100)
    
    return [{
        "_id": str(r["_id"]),
        "first_name": r.get("first_name", ""),
        "last_name": r.get("last_name", ""),
        "phone": r.get("phone", ""),
        "vehicle": r.get("vehicle", ""),
        "tags": r.get("tags", []),
        "created_at": r.get("created_at")
    } for r in referrals]

@router.post("/{user_id}/import")
async def import_contacts(user_id: str, contacts: List[ContactCreate]):
    """Bulk import contacts from CSV"""
    imported = []
    for contact_data in contacts:
        # Check for duplicates by phone (only check for this user's contacts)
        existing = await get_db().contacts.find_one({
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
        
        result = await get_db().contacts.insert_one(contact_dict)
        contact_dict['_id'] = result.inserted_id
        imported.append(contact_dict)
    
    return {
        "imported": len(imported),
        "skipped": len(contacts) - len(imported)
    }

@router.post("/{user_id}/{contact_id}/photo")
async def upload_contact_photo(user_id: str, contact_id: str, photo_data: dict):
    """Upload a photo for a contact"""
    base_filter = await get_data_filter(user_id)
    
    photo_url = photo_data.get('photo_url')
    if not photo_url:
        raise HTTPException(status_code=400, detail="photo_url is required")
    
    try:
        result = await get_db().contacts.update_one(
            {"$and": [{"_id": ObjectId(contact_id)}, base_filter]},
            {"$set": {"photo_url": photo_url, "updated_at": datetime.utcnow()}}
        )
    except:
        result = await get_db().contacts.update_one(
            {"$and": [{"_id": contact_id}, base_filter]},
            {"$set": {"photo_url": photo_url, "updated_at": datetime.utcnow()}}
        )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    return {"message": "Photo uploaded successfully", "photo_url": photo_url}
