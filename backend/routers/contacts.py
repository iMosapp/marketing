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


async def _check_tag_campaign_enrollment(user_id: str, contact_id: str, contact_data: dict):
    """Auto-enroll contact in campaigns whose trigger_tag matches any of the contact's tags"""
    db = get_db()
    contact_tags = contact_data.get('tags', [])
    if not contact_tags:
        return
    
    try:
        # Find active campaigns with trigger_tags matching this contact's tags
        campaigns = await db.campaigns.find({
            "user_id": user_id,
            "active": True,
            "trigger_tag": {"$in": contact_tags}
        }).to_list(50)
        
        for campaign in campaigns:
            campaign_id = str(campaign['_id'])
            # Check if already enrolled
            existing = await db.campaign_enrollments.find_one({
                "campaign_id": campaign_id,
                "contact_id": contact_id,
                "status": {"$in": ["active", "completed"]}
            })
            if existing:
                continue
            
            # Get contact info for enrollment
            contact = contact_data
            contact_name = f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip()
            
            sequences = campaign.get('sequences', [])
            enrollment = {
                "user_id": user_id,
                "campaign_id": campaign_id,
                "campaign_name": campaign.get('name', ''),
                "contact_id": contact_id,
                "contact_name": contact_name,
                "contact_phone": contact.get('phone', ''),
                "current_step": 1,
                "total_steps": len(sequences),
                "status": "active",
                "enrolled_at": datetime.utcnow(),
                "next_send_at": datetime.utcnow(),
                "messages_sent": [],
                "trigger_type": "tag",
                "trigger_tag": campaign.get('trigger_tag', '')
            }
            await db.campaign_enrollments.insert_one(enrollment)
            logger.info(f"Auto-enrolled {contact_name} in campaign '{campaign.get('name')}' via tag '{campaign.get('trigger_tag')}'")
    except Exception as e:
        logger.error(f"Tag campaign enrollment check failed: {e}")

@router.post("/{user_id}", response_model=Contact)
async def create_contact(user_id: str, contact_data: ContactCreate):
    """Create a new contact"""
    db = get_db()
    contact_dict = contact_data.dict()
    contact_dict['user_id'] = user_id
    contact_dict['original_user_id'] = user_id
    contact_dict['created_at'] = datetime.utcnow()
    contact_dict['updated_at'] = datetime.utcnow()
    
    # Determine ownership type based on source
    source = contact_dict.get('source', 'manual')
    if source in ('csv', 'phone_contacts'):
        contact_dict['ownership_type'] = 'personal'
    else:
        contact_dict['ownership_type'] = 'org'
    contact_dict['status'] = 'active'
    
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
    """Get all contacts accessible to a user based on their role.
    Excludes heavy photo field - uses photo_thumbnail for avatars."""
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
    
    # Exclude heavy 'photo' field from list queries — use photo_thumbnail instead
    contacts = await db.contacts.find(query, {"photo": 0}).sort("first_name", 1).limit(500).to_list(500)
    
    # Auto-backfill: find contacts missing thumbnails but having a photo in DB
    needs_backfill = [c for c in contacts if not c.get('photo_thumbnail') and not c.get('photo_url')]
    if needs_backfill:
        ids = [c['_id'] for c in needs_backfill]
        # Fetch only the photo field for these contacts
        photo_docs = await db.contacts.find(
            {"_id": {"$in": ids}, "photo": {"$exists": True, "$nin": [None, "", "None"]}},
            {"_id": 1, "photo": 1}
        ).to_list(len(ids))
        
        for pdoc in photo_docs:
            photo_data = pdoc.get('photo', '')
            if photo_data and len(photo_data) > 100:
                try:
                    thumbnail, high_res = await _process_photo(photo_data)
                    await db.contacts.update_one(
                        {"_id": pdoc['_id']},
                        {"$set": {"photo_thumbnail": thumbnail, "photo_url": thumbnail}}
                    )
                    # Also store high-res separately
                    cid = str(pdoc['_id'])
                    await db.contact_photos.update_one(
                        {"contact_id": cid},
                        {"$set": {"contact_id": cid, "photo_full": high_res, "updated_at": datetime.utcnow()}},
                        upsert=True
                    )
                    # Update the in-memory contact for this response
                    for c in contacts:
                        if c['_id'] == pdoc['_id']:
                            c['photo_thumbnail'] = thumbnail
                            c['photo_url'] = thumbnail
                            break
                    logger.info(f"Backfilled thumbnail for contact {cid}")
                except Exception as e:
                    logger.error(f"Failed to backfill thumbnail for {pdoc['_id']}: {e}")
    
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
    base_filter = await get_data_filter(user_id)
    
    update_dict = contact_data.dict()
    update_dict['updated_at'] = datetime.utcnow()
    
    # Auto-tag based on date fields
    existing_tags = set(update_dict.get('tags', []))
    if update_dict.get('birthday'):
        existing_tags.add('Birthday')
    if update_dict.get('anniversary'):
        existing_tags.add('Anniversary')
    if update_dict.get('date_sold'):
        existing_tags.add('Sold Date')
    update_dict['tags'] = list(existing_tags)
    
    # If setting a referrer, update the referrer's count
    if contact_data.referred_by:
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
    
    # Auto-enroll in tag-triggered campaigns
    await _check_tag_campaign_enrollment(user_id, contact_id, update_dict)
    
    return {"message": "Contact updated successfully"}

@router.delete("/{user_id}/{contact_id}")
async def delete_contact(user_id: str, contact_id: str):
    """Delete a single contact with role-based access check"""
    db = get_db()
    base_filter = await get_data_filter(user_id)
    
    try:
        result = await db.contacts.delete_one({
            "$and": [{"_id": ObjectId(contact_id)}, base_filter]
        })
    except Exception:
        result = await db.contacts.delete_one({
            "$and": [{"_id": contact_id}, base_filter]
        })
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    # Clean up related data
    try:
        await db.contact_photos.delete_many({"contact_id": contact_id})
    except Exception:
        pass
    
    return {"message": "Contact deleted successfully"}

@router.post("/{user_id}/bulk-delete")
async def bulk_delete_contacts(user_id: str, data: dict):
    """Delete multiple contacts at once"""
    db = get_db()
    base_filter = await get_data_filter(user_id)
    contact_ids = data.get("contact_ids", [])
    
    if not contact_ids:
        raise HTTPException(status_code=400, detail="No contact IDs provided")
    
    # Convert to ObjectIds
    obj_ids = []
    for cid in contact_ids:
        try:
            obj_ids.append(ObjectId(cid))
        except Exception:
            obj_ids.append(cid)
    
    result = await db.contacts.delete_many({
        "$and": [
            {"_id": {"$in": obj_ids}},
            base_filter
        ]
    })
    
    # Clean up related photos
    try:
        await db.contact_photos.delete_many({"contact_id": {"$in": contact_ids}})
    except Exception:
        pass
    
    return {"deleted": result.deleted_count, "requested": len(contact_ids)}

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
    """Upload a photo for a contact. Generates a tiny thumbnail for avatars
    and stores the high-res version separately for congrats cards/emails."""
    base_filter = await get_data_filter(user_id)
    db = get_db()
    
    photo_url = photo_data.get('photo_url') or photo_data.get('photo')
    if not photo_url:
        raise HTTPException(status_code=400, detail="photo_url or photo is required")
    
    update_fields = {"updated_at": datetime.utcnow()}
    
    # If it's base64 data, generate a thumbnail
    if photo_url.startswith('data:') or len(photo_url) > 1000:
        try:
            thumbnail, high_res = await _process_photo(photo_url)
            update_fields["photo_thumbnail"] = thumbnail  # ~5KB for avatars
            update_fields["photo_url"] = thumbnail  # Use thumbnail as default
            # Store high-res in separate collection to keep contacts lightweight
            await db.contact_photos.update_one(
                {"contact_id": contact_id},
                {"$set": {"contact_id": contact_id, "user_id": user_id, "photo_full": high_res, "updated_at": datetime.utcnow()}},
                upsert=True
            )
        except Exception as e:
            logger.error(f"Photo processing failed: {e}")
            update_fields["photo_url"] = photo_url
    else:
        update_fields["photo_url"] = photo_url
    
    try:
        result = await db.contacts.update_one(
            {"$and": [{"_id": ObjectId(contact_id)}, base_filter]},
            {"$set": update_fields}
        )
    except:
        result = await db.contacts.update_one(
            {"$and": [{"_id": contact_id}, base_filter]},
            {"$set": update_fields}
        )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    return {"message": "Photo uploaded successfully", "photo_url": update_fields.get("photo_url", "")}


@router.get("/{user_id}/{contact_id}/photo/full")
async def get_full_photo(user_id: str, contact_id: str):
    """Get the high-resolution photo for congrats cards, emails, or third-party use"""
    db = get_db()
    photo_doc = await db.contact_photos.find_one({"contact_id": contact_id}, {"_id": 0, "photo_full": 1})
    if not photo_doc or not photo_doc.get("photo_full"):
        # Fallback: try the contact's photo field directly
        try:
            contact = await db.contacts.find_one({"_id": ObjectId(contact_id)}, {"photo": 1, "photo_url": 1})
        except:
            contact = await db.contacts.find_one({"_id": contact_id}, {"photo": 1, "photo_url": 1})
        if contact and contact.get("photo"):
            return {"photo": contact["photo"]}
        elif contact and contact.get("photo_url"):
            return {"photo": contact["photo_url"]}
        raise HTTPException(status_code=404, detail="No high-res photo found")
    return {"photo": photo_doc["photo_full"]}


async def _process_photo(photo_data: str) -> tuple:
    """Process a photo: generate a tiny thumbnail and a reasonable high-res version.
    Returns (thumbnail_base64, highres_base64)"""
    import base64
    from PIL import Image
    import io
    
    # Extract base64 data
    if photo_data.startswith('data:'):
        header, b64data = photo_data.split(',', 1)
        prefix = header + ','
    else:
        b64data = photo_data
        prefix = 'data:image/jpeg;base64,'
    
    img_bytes = base64.b64decode(b64data)
    img = Image.open(io.BytesIO(img_bytes))
    
    # Convert to RGB if needed
    if img.mode in ('RGBA', 'P'):
        img = img.convert('RGB')
    
    # Generate thumbnail (96x96 for avatars, ~3-5KB)
    thumb = img.copy()
    thumb.thumbnail((96, 96), Image.LANCZOS)
    thumb_buffer = io.BytesIO()
    thumb.save(thumb_buffer, 'JPEG', quality=60, optimize=True)
    thumb_b64 = prefix + base64.b64encode(thumb_buffer.getvalue()).decode()
    
    # Generate high-res (1080px for social media/email/MMS sharing)
    highres = img.copy()
    highres.thumbnail((1080, 1080), Image.LANCZOS)
    highres_buffer = io.BytesIO()
    highres.save(highres_buffer, 'JPEG', quality=92, optimize=True)
    highres_b64 = prefix + base64.b64encode(highres_buffer.getvalue()).decode()
    
    return thumb_b64, highres_b64
