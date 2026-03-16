"""
Contacts router - handles contact CRUD operations
"""
from fastapi import APIRouter, HTTPException, Body
from bson import ObjectId
from datetime import datetime, timezone
from typing import List, Optional
import logging

from models import Contact, ContactCreate
from routers.database import get_db, get_data_filter, get_user_by_id, get_accessible_user_ids, increment_user_stat

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


async def _check_date_campaign_enrollment(user_id: str, contact_id: str, contact_data: dict):
    """Auto-enroll contact in date-based campaigns when date fields are present"""
    db = get_db()
    
    # Map contact date fields to campaign date_type/type values
    date_field_map = {
        "birthday": ["birthday"],
        "anniversary": ["anniversary"],
        "date_sold": ["sold_date"],
    }
    
    try:
        for contact_field, campaign_types in date_field_map.items():
            date_val = contact_data.get(contact_field)
            if not date_val:
                continue
            
            # Find active date campaigns matching this date type
            type_conditions = []
            for ct in campaign_types:
                type_conditions.append({"type": ct})
                type_conditions.append({"date_type": ct})
            
            campaigns = await db.campaigns.find({
                "user_id": user_id,
                "active": True,
                "$or": type_conditions
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
                
                contact_name = f"{contact_data.get('first_name', '')} {contact_data.get('last_name', '')}".strip()
                sequences = campaign.get('sequences', [])
                
                enrollment = {
                    "user_id": user_id,
                    "campaign_id": campaign_id,
                    "campaign_name": campaign.get('name', ''),
                    "contact_id": contact_id,
                    "contact_name": contact_name,
                    "contact_phone": contact_data.get('phone', ''),
                    "current_step": 1,
                    "total_steps": len(sequences),
                    "status": "active",
                    "enrolled_at": datetime.utcnow(),
                    "next_send_at": datetime.utcnow(),
                    "messages_sent": [],
                    "trigger_type": campaign_types[0]
                }
                await db.campaign_enrollments.insert_one(enrollment)
                logger.info(f"Auto-enrolled {contact_name} in date campaign '{campaign.get('name')}' ({campaign_types[0]})")
    except Exception as e:
        logger.error(f"Date campaign enrollment check failed: {e}")

@router.post("/{user_id}", response_model=Contact)
async def create_contact(user_id: str, contact_data: ContactCreate):
    """Create a new contact"""
    db = get_db()
    contact_dict = contact_data.dict()
    contact_dict['user_id'] = user_id
    contact_dict['original_user_id'] = user_id
    contact_dict['created_at'] = datetime.utcnow()
    contact_dict['updated_at'] = datetime.utcnow()
    
    # Determine ownership type AUTOMATICALLY based on source
    # Phone imports = personal (user's own contacts, go with them if they leave)
    # Everything created in the app = org (stays with the dealership)
    # Users cannot override this — ownership is a business rule, not a user preference
    source = contact_dict.get('source', 'manual')
    if source == 'phone_import':
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
    contact_dict['_id'] = str(result.inserted_id)
    
    # Auto-enroll in tag-triggered campaigns
    await _check_tag_campaign_enrollment(user_id, str(result.inserted_id), contact_dict)
    
    # Auto-enroll in date-based campaigns (birthday, anniversary, sold_date)
    await _check_date_campaign_enrollment(user_id, str(result.inserted_id), contact_dict)
    
    # Track stat for leaderboard
    await increment_user_stat(user_id, "contacts_added")
    
    # Log "new contact added" to activity feed
    try:
        user_doc = await db.users.find_one({"_id": ObjectId(user_id)}, {"_id": 0, "name": 1, "org_id": 1})
        user_name = user_doc.get("name", "User") if user_doc else "User"
        org_id = user_doc.get("org_id", "") if user_doc else ""
        contact_name = f"{contact_dict.get('first_name', '')} {contact_dict.get('last_name', '')}".strip()
        await db.contact_events.insert_one({
            "event_type": "new_contact_added",
            "title": "New Contact Added",
            "description": f"{user_name} added {contact_name}",
            "contact_id": str(result.inserted_id),
            "user_id": user_id,
            "org_id": org_id,
            "channel": "system",
            "category": "contact",
            "icon": "person-add",
            "color": "#AF52DE",
            "content": f"Added new contact: {contact_name}",
            "timestamp": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc),
        })
    except Exception as e:
        logger.error(f"Failed to log new contact event: {e}")
    
    return Contact(**contact_dict)


@router.get("/{user_id}/check-duplicate")
async def check_duplicate_contact(user_id: str, phone: Optional[str] = None, email: Optional[str] = None):
    """Check if a contact with this phone or email already exists for this user."""
    db = get_db()
    if not phone and not email:
        return {"matches": []}
    
    conditions = []
    if phone:
        # Normalize: strip spaces, dashes, parens — match last 10 digits
        clean = ''.join(c for c in phone if c.isdigit())
        if len(clean) >= 7:
            # Match on last 10 digits to handle +1 prefix variations
            suffix = clean[-10:] if len(clean) >= 10 else clean
            conditions.append({"phone": {"$regex": suffix + "$"}})
    if email:
        email_clean = email.strip().lower()
        if len(email_clean) >= 3:
            conditions.append({"email": {"$regex": f"^{email_clean}$", "$options": "i"}})
    
    if not conditions:
        return {"matches": []}
    
    matches = await db.contacts.find(
        {"user_id": user_id, "$or": conditions, "status": {"$ne": "hidden"}},
        {"_id": 1, "first_name": 1, "last_name": 1, "phone": 1, "email": 1, "photo_thumbnail": 1}
    ).to_list(5)
    
    return {"matches": [
        {
            "id": str(m["_id"]),
            "first_name": m.get("first_name", ""),
            "last_name": m.get("last_name", ""),
            "phone": m.get("phone", ""),
            "email": m.get("email", ""),
            "photo_thumbnail": m.get("photo_thumbnail", ""),
        }
        for m in matches
    ]}

@router.get("/{user_id}", response_model=List[Contact])
async def get_contacts(user_id: str, search: Optional[str] = None, view_mode: Optional[str] = None, sort_by: Optional[str] = None):
    """Get contacts based on view mode.
    
    view_mode:
    - None / 'mine' (default): Only the user's own contacts (all roles)
    - 'team': (managers/admins only) All org contacts from team members, excluding personal contacts.
              Enriched with salesperson_name. View-only on the frontend.
    
    Salespeople ONLY ever see their own contacts. The 'team' mode is ignored for regular users.
    Personal contacts are NEVER visible to anyone except the owner.
    """
    db = get_db()
    user = await get_user_by_id(user_id)
    if not user:
        return []
    
    role = user.get("role", "user")
    is_manager = role in ("super_admin", "org_admin", "store_manager")
    
    # Status filter (reusable)
    status_filter = {"$or": [
        {"status": {"$nin": ["hidden", "merged", "deleted"]}},
        {"status": {"$exists": False}},
        {"original_user_id": user_id, "status": {"$nin": ["merged", "deleted"]}},
    ]}
    
    if view_mode == "team" and is_manager:
        # Team view: all org contacts from accessible users (excluding personal)
        accessible_ids = await get_accessible_user_ids(user)
        privacy_filter = {"$and": [
            {"user_id": {"$in": accessible_ids}},
            {"ownership_type": {"$ne": "personal"}},
            status_filter,
        ]}
    else:
        # Default: only user's own contacts (same for ALL roles)
        privacy_filter = {"$and": [
            {"user_id": user_id},
            status_filter,
        ]}
    
    if search:
        query = {
            "$and": [
                privacy_filter,
                {"$or": [
                    {"first_name": {"$regex": search, "$options": "i"}},
                    {"last_name": {"$regex": search, "$options": "i"}},
                    {"phone": {"$regex": search, "$options": "i"}},
                    {"email": {"$regex": search, "$options": "i"}},
                    {"tags": {"$regex": search, "$options": "i"}}
                ]}
            ]
        }
    else:
        query = privacy_filter
    
    # Determine sort order
    if sort_by == "recent":
        # Sort by most recent ACTIVITY (text, email, call, etc.) — not just updated_at
        # Aggregate contact_events to find latest interaction per contact
        activity_pipeline = [
            {"$match": {"user_id": user_id}},
            {"$group": {"_id": "$contact_id", "last_activity": {"$max": "$timestamp"}}},
        ]
        activity_results = await db.contact_events.aggregate(activity_pipeline).to_list(1000)
        activity_map = {r["_id"]: r["last_activity"] for r in activity_results}

        contacts = await db.contacts.find(query, {"photo": 0}).limit(500).to_list(500)

        # Sort: contacts with recent activity first, then by updated_at as fallback
        epoch = datetime(2000, 1, 1)
        for c in contacts:
            cid = str(c.get("_id", ""))
            c["_last_activity"] = activity_map.get(cid, c.get("updated_at", c.get("created_at", epoch)))
        contacts.sort(key=lambda c: c.get("_last_activity", epoch), reverse=True)
        for c in contacts:
            c.pop("_last_activity", None)
    else:
        sort_spec = [("first_name", 1), ("last_name", 1)]
        contacts = await db.contacts.find(query, {"photo": 0}).sort(sort_spec).limit(500).to_list(500)
    
    # For team view: enrich with salesperson names
    salesperson_map = {}
    if view_mode == "team" and is_manager:
        sp_ids = list(set(c.get("user_id", "") for c in contacts))
        if sp_ids:
            sp_docs = await db.users.find(
                {"_id": {"$in": [ObjectId(sid) for sid in sp_ids if len(sid) == 24]}},
                {"_id": 1, "name": 1}
            ).to_list(len(sp_ids))
            salesperson_map = {str(d["_id"]): d.get("name", "Unknown") for d in sp_docs}
    
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
    
    results = []
    for c in contacts:
        c_dict = {**c, "_id": str(c["_id"])}
        # Enrich with salesperson name for team view
        if salesperson_map:
            c_dict["salesperson_name"] = salesperson_map.get(c.get("user_id", ""), "")
        results.append(Contact(**c_dict))
    return results

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
    
    # Process photo if it's a new base64 upload → compress to WebP via image pipeline
    photo_val = update_dict.get('photo')
    if photo_val and (photo_val.startswith('data:') or len(photo_val) > 1000):
        # Save old photo to history before replacing
        try:
            db = get_db()
            old_contact = await db.contacts.find_one(
                {"_id": ObjectId(contact_id)},
                {"photo_path": 1, "photo_thumb_path": 1, "photo_url": 1, "photo_thumbnail": 1, "photo": 1}
            )
            if old_contact:
                old_url = None
                old_thumb = None
                if old_contact.get("photo_path"):
                    old_url = f"/api/images/{old_contact['photo_path']}"
                    old_thumb = f"/api/images/{old_contact.get('photo_thumb_path', old_contact['photo_path'])}"
                elif old_contact.get("photo_url") and old_contact["photo_url"].startswith(("/api/images/", "http")):
                    old_url = old_contact["photo_url"]
                    old_thumb = old_contact.get("photo_thumbnail") or old_url
                elif old_contact.get("photo") and old_contact["photo"].startswith(("/api/images/", "http")):
                    old_url = old_contact["photo"]
                    old_thumb = old_contact.get("photo_thumbnail") or old_url
                if old_url:
                    await db.contacts.update_one(
                        {"_id": ObjectId(contact_id)},
                        {"$push": {"photo_history": {
                            "url": old_url, "thumbnail_url": old_thumb or old_url,
                            "replaced_at": datetime.now(timezone.utc).isoformat(),
                            "type": "profile"
                        }}}
                    )
        except Exception as e:
            logger.warning(f"Failed to save photo history: {e}")
        try:
            from utils.image_storage import upload_image
            result = await upload_image(photo_val, prefix="contacts", entity_id=contact_id)
            if result:
                update_dict['photo_path'] = result['original_path']
                update_dict['photo_thumb_path'] = result['thumbnail_path']
                update_dict['photo_avatar_path'] = result['avatar_path']
                update_dict['photo_thumbnail'] = f"/api/images/{result['thumbnail_path']}"
                update_dict['photo_url'] = f"/api/images/{result['thumbnail_path']}"
                # Don't store the huge raw base64 in the contacts collection
                update_dict.pop('photo', None)
            else:
                # Fallback to old processing
                thumbnail, high_res = await _process_photo(photo_val)
                update_dict['photo_thumbnail'] = thumbnail
                update_dict['photo_url'] = thumbnail
                update_dict.pop('photo', None)
                db = get_db()
                await db.contact_photos.update_one(
                    {"contact_id": contact_id},
                    {"$set": {"contact_id": contact_id, "user_id": user_id, "photo_full": high_res, "updated_at": datetime.utcnow()}},
                    upsert=True
                )
        except Exception as e:
            logger.error(f"Photo processing during update failed: {e}")
            update_dict['photo_url'] = photo_val
    
    # Auto-tag based on date fields
    existing_tags = set(update_dict.get('tags', []))
    if update_dict.get('birthday'):
        existing_tags.add('Birthday')
    if update_dict.get('anniversary'):
        existing_tags.add('Anniversary')
    if update_dict.get('date_sold'):
        existing_tags.add('Sold Date')
    update_dict['tags'] = list(existing_tags)
    
    # If setting a referrer, update the referrer's count (only when referred_by actually changes)
    if contact_data.referred_by:
        try:
            # Check if referred_by actually changed
            existing = await get_db().contacts.find_one(
                {"$and": [{"_id": ObjectId(contact_id)}, base_filter]},
                {"referred_by": 1}
            )
            old_ref = str(existing.get("referred_by", "")) if existing else ""
            new_ref = str(contact_data.referred_by)
            if old_ref != new_ref:
                # Increment the new referrer's count
                try:
                    await get_db().contacts.update_one(
                        {"$and": [{"_id": ObjectId(new_ref)}, base_filter]},
                        {"$inc": {"referral_count": 1}}
                    )
                except Exception:
                    await get_db().contacts.update_one(
                        {"$and": [{"_id": new_ref}, base_filter]},
                        {"$inc": {"referral_count": 1}}
                    )
                # Decrement the old referrer's count if there was one
                if old_ref:
                    try:
                        await get_db().contacts.update_one(
                            {"$and": [{"_id": ObjectId(old_ref)}, base_filter]},
                            {"$inc": {"referral_count": -1}}
                        )
                    except Exception:
                        pass
        except Exception as e:
            logger.error(f"Referral count update failed: {e}")
    
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
    
    # Auto-enroll in date-based campaigns if date fields were updated
    await _check_date_campaign_enrollment(user_id, contact_id, update_dict)
    
    return {"message": "Contact updated successfully"}

@router.patch("/{user_id}/{contact_id}/profile-photo")
async def set_profile_photo(user_id: str, contact_id: str, data: dict = Body(...)):
    """Set a contact's profile photo from an existing photo URL."""
    db = get_db()
    photo_url = data.get("photo_url", "")
    if not photo_url:
        raise HTTPException(status_code=400, detail="photo_url is required")

    # Save old photo to history before replacing
    try:
        old_contact = await db.contacts.find_one(
            {"_id": ObjectId(contact_id)},
            {"photo_path": 1, "photo_thumb_path": 1, "photo_url": 1, "photo_thumbnail": 1, "photo": 1}
        )
        if old_contact:
            old_url = None
            old_thumb = None
            if old_contact.get("photo_path"):
                old_url = f"/api/images/{old_contact['photo_path']}"
                old_thumb = f"/api/images/{old_contact.get('photo_thumb_path', old_contact['photo_path'])}"
            elif old_contact.get("photo_url") and old_contact["photo_url"].startswith(("/api/images/", "http")):
                old_url = old_contact["photo_url"]
                old_thumb = old_contact.get("photo_thumbnail") or old_url
            elif old_contact.get("photo") and old_contact["photo"].startswith(("/api/images/", "http")):
                old_url = old_contact["photo"]
                old_thumb = old_contact.get("photo_thumbnail") or old_url
            if old_url and old_url != photo_url:
                await db.contacts.update_one(
                    {"_id": ObjectId(contact_id)},
                    {"$push": {"photo_history": {
                        "url": old_url, "thumbnail_url": old_thumb or old_url,
                        "replaced_at": datetime.now(timezone.utc).isoformat(),
                        "type": "profile"
                    }}}
                )
    except Exception as e:
        logger.warning(f"Failed to save photo history on profile-photo set: {e}")

    try:
        result = await db.contacts.update_one(
            {"_id": ObjectId(contact_id)},
            {
                "$set": {"photo": photo_url, "photo_url": photo_url, "photo_thumbnail": photo_url, "updated_at": datetime.utcnow()},
                "$unset": {"photo_path": "", "photo_thumb_path": "", "photo_avatar_path": ""}
            }
        )
    except Exception:
        result = await db.contacts.update_one(
            {"_id": contact_id},
            {
                "$set": {"photo": photo_url, "photo_url": photo_url, "photo_thumbnail": photo_url, "updated_at": datetime.utcnow()},
                "$unset": {"photo_path": "", "photo_thumb_path": "", "photo_avatar_path": ""}
            }
        )

    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Contact not found")

    return {"message": "Profile photo updated"}


@router.patch("/{user_id}/{contact_id}/toggle-automation")
async def toggle_automation(user_id: str, contact_id: str, data: dict = Body(...)):
    """Toggle a specific automation (birthday/anniversary/sold_date) on or off for a contact."""
    db = get_db()
    field = data.get("field", "")
    if field not in ("birthday", "anniversary", "sold_date"):
        raise HTTPException(status_code=400, detail="Invalid automation field")

    contact = await db.contacts.find_one({"_id": ObjectId(contact_id)}, {"disabled_automations": 1})
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    disabled = contact.get("disabled_automations", [])
    if field in disabled:
        disabled.remove(field)
        enabled = True
    else:
        disabled.append(field)
        enabled = False

    await db.contacts.update_one(
        {"_id": ObjectId(contact_id)},
        {"$set": {"disabled_automations": disabled}}
    )
    return {"field": field, "enabled": enabled, "disabled_automations": disabled}


@router.get("/{user_id}/{contact_id}/personal-details")
async def get_personal_details(user_id: str, contact_id: str):
    """Get the AI-extracted personal details for a contact."""
    db = get_db()
    contact = await db.contacts.find_one(
        {"_id": ObjectId(contact_id)},
        {"personal_details": 1, "vehicle": 1, "notes": 1}
    )
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    details = contact.get("personal_details", {})
    return {
        "personal_details": details,
        "vehicle": contact.get("vehicle", ""),
        "has_details": len(details) > 0,
    }


@router.patch("/{user_id}/{contact_id}/personal-details")
async def update_personal_details(user_id: str, contact_id: str, data: dict = Body(...)):
    """Manually update personal details for a contact. Merges with existing."""
    db = get_db()
    contact = await db.contacts.find_one({"_id": ObjectId(contact_id)}, {"personal_details": 1})
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    existing = contact.get("personal_details", {})
    # Manual edits override AI extractions
    merged = {**existing, **data.get("personal_details", {})}

    # Remove null/empty values from manual edits
    merged = {k: v for k, v in merged.items() if v is not None and v != "" and v != []}

    await db.contacts.update_one(
        {"_id": ObjectId(contact_id)},
        {"$set": {"personal_details": merged, "updated_at": datetime.now(timezone.utc)}}
    )

    return {"personal_details": merged}


@router.post("/{user_id}/{contact_id}/re-extract")
async def re_extract_intelligence(user_id: str, contact_id: str):
    """Re-run AI extraction on all voice notes for this contact."""
    db = get_db()
    notes = await db.voice_notes.find(
        {"contact_id": contact_id, "user_id": user_id, "transcript": {"$ne": ""}},
        {"_id": 1, "transcript": 1}
    ).to_list(50)

    if not notes:
        return {"message": "No voice notes with transcripts found", "extracted": 0}

    from services.voice_intel import process_voice_note_intelligence
    count = 0
    for note in notes:
        transcript = note.get("transcript", "")
        if transcript and len(transcript.strip()) >= 10:
            await process_voice_note_intelligence(user_id, contact_id, transcript, str(note["_id"]))
            count += 1

    return {"message": f"Re-extracted intelligence from {count} voice notes", "extracted": count}


@router.patch("/{user_id}/{contact_id}/tags")
async def update_contact_tags(user_id: str, contact_id: str, data: dict = Body(...)):
    """Update tags on a contact without requiring the full contact payload."""
    db = get_db()
    tags = data.get("tags", [])
    if not isinstance(tags, list):
        raise HTTPException(status_code=400, detail="tags must be a list")
    
    result = await db.contacts.update_one(
        {"_id": ObjectId(contact_id), "user_id": user_id},
        {"$set": {"tags": tags, "updated_at": datetime.now(timezone.utc)}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Contact not found")
    return {"tags": tags}




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
async def import_contacts(user_id: str, contacts: List[ContactCreate], source: str = "csv"):
    """Bulk import contacts from CSV or phone"""
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
        contact_dict['original_user_id'] = user_id
        contact_dict['source'] = source
        # Phone imports are personal; CSV/other imports are org
        contact_dict['ownership_type'] = 'personal' if source == 'phone_import' else 'org'
        contact_dict['status'] = 'active'
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
    
    # If it's base64 data, compress to WebP via image pipeline
    if photo_url.startswith('data:') or len(photo_url) > 1000:
        try:
            from utils.image_storage import upload_image
            result = await upload_image(photo_url, prefix="contacts", entity_id=contact_id)
            if result:
                update_fields["photo_path"] = result["original_path"]
                update_fields["photo_thumb_path"] = result["thumbnail_path"]
                update_fields["photo_avatar_path"] = result["avatar_path"]
                update_fields["photo_thumbnail"] = f"/api/images/{result['thumbnail_path']}"
                update_fields["photo_url"] = f"/api/images/{result['thumbnail_path']}"
            else:
                # Fallback
                thumbnail, high_res = await _process_photo(photo_url)
                update_fields["photo_thumbnail"] = thumbnail
                update_fields["photo_url"] = thumbnail
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
    """Process a photo: auto-rotate using EXIF, generate a tiny thumbnail and a reasonable high-res version.
    Returns (thumbnail_base64, highres_base64)"""
    import base64
    from PIL import Image, ImageOps
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
    
    # Auto-rotate based on EXIF orientation (fixes sideways photos from phones)
    img = ImageOps.exif_transpose(img)
    
    # Convert to RGB if needed
    if img.mode in ('RGBA', 'P'):
        img = img.convert('RGB')
    
    # Generate thumbnail (256x256 for avatars  - crisp on 3x Retina, ~10-15KB)
    thumb = img.copy()
    thumb.thumbnail((256, 256), Image.LANCZOS)
    thumb_buffer = io.BytesIO()
    thumb.save(thumb_buffer, 'JPEG', quality=85, optimize=True)
    thumb_b64 = prefix + base64.b64encode(thumb_buffer.getvalue()).decode()
    
    # Generate high-res (1080px for social media/email/MMS sharing)
    highres = img.copy()
    highres.thumbnail((1080, 1080), Image.LANCZOS)
    highres_buffer = io.BytesIO()
    highres.save(highres_buffer, 'JPEG', quality=92, optimize=True)
    highres_b64 = prefix + base64.b64encode(highres_buffer.getvalue()).decode()
    
    return thumb_b64, highres_b64


@router.post("/admin/regenerate-thumbnails")
async def regenerate_thumbnails():
    """One-time migration: regenerate all contact thumbnails at higher quality (256x256 @ 85%)."""
    db = get_db()
    contacts = await db.contacts.find(
        {"photo": {"$exists": True, "$nin": [None, "", "None"]}},
        {"_id": 1, "photo": 1}
    ).to_list(5000)
    
    updated = 0
    failed = 0
    for c in contacts:
        try:
            photo_data = c.get("photo", "")
            if photo_data and len(photo_data) > 100:
                thumbnail, high_res = await _process_photo(photo_data)
                await db.contacts.update_one(
                    {"_id": c["_id"]},
                    {"$set": {"photo_thumbnail": thumbnail, "photo_url": thumbnail}}
                )
                await db.contact_photos.update_one(
                    {"contact_id": str(c["_id"])},
                    {"$set": {"contact_id": str(c["_id"]), "photo_full": high_res}},
                    upsert=True
                )
                updated += 1
        except Exception as e:
            failed += 1
            logger.error(f"Failed to regenerate thumbnail for {c['_id']}: {e}")
    
    return {"updated": updated, "failed": failed, "total_processed": len(contacts)}


@router.get("/{user_id}/{contact_id}/photos/all")
async def get_all_contact_photos(user_id: str, contact_id: str):
    """Get all photos for a contact — fast read-only, WebP pipeline only. No base64."""
    db = get_db()
    photos = []

    try:
        contact = await db.contacts.find_one(
            {"_id": ObjectId(contact_id)},
            {"photo_path": 1, "photo_thumb_path": 1, "photo_url": 1,
             "photo_thumbnail": 1, "first_name": 1, "phone": 1, "photo_history": 1}
        )
    except Exception:
        contact = None

    # 1. Current profile photo — only fast paths
    if contact:
        if contact.get("photo_path"):
            photos.append({
                "type": "profile", "label": "Profile Photo",
                "url": f"/api/images/{contact['photo_path']}",
                "thumbnail_url": f"/api/images/{contact.get('photo_thumb_path', contact['photo_path'])}",
            })
        elif contact.get("photo_url") and contact["photo_url"].startswith(("/api/images/", "http")):
            photos.append({
                "type": "profile", "label": "Profile Photo",
                "url": contact["photo_url"],
                "thumbnail_url": contact.get("photo_thumbnail") or contact["photo_url"],
            })

    # 2. Photo history — previous profile photos (only fast URLs)
    if contact and contact.get("photo_history"):
        for hist in reversed(contact["photo_history"]):
            url = hist.get("url", "")
            if url.startswith(("/api/images/", "http")):
                photos.append({
                    "type": "history", "label": "Previous Photo",
                    "url": url,
                    "thumbnail_url": hist.get("thumbnail_url") or url,
                    "date": hist.get("replaced_at"),
                })

    # 3. Congrats card photos — only fast paths, skip base64
    congrats_filter = {"user_id": user_id, "$or": []}
    if contact_id:
        congrats_filter["$or"].append({"contact_id": contact_id})
    if contact and contact.get("phone"):
        phone = contact["phone"].replace("+", "").replace("-", "").replace(" ", "").replace("(", "").replace(")", "")
        if len(phone) > 6:
            congrats_filter["$or"].append({"customer_phone": {"$regex": phone[-10:]}})

    if congrats_filter["$or"]:
        congrats = await db.congrats_cards.find(
            congrats_filter,
            {"card_id": 1, "customer_name": 1, "created_at": 1,
             "photo_path": 1, "photo_thumb_path": 1,
             "photo_url": 1, "photo_thumbnail_url": 1,
             "customer_photo": 1, "_id": 1}
        ).sort("created_at", -1).to_list(50)
        for c in congrats:
            if c.get("photo_path"):
                full_url = f"/api/images/{c['photo_path']}"
                thumb_url = f"/api/images/{c.get('photo_thumb_path', c['photo_path'])}"
            elif c.get("photo_url") and c["photo_url"].startswith("/api/images/"):
                full_url = c["photo_url"]
                thumb_url = c.get("photo_thumbnail_url") or full_url
            elif c.get("customer_photo") and c["customer_photo"].startswith(("/api/images/", "http")):
                full_url = c["customer_photo"]
                thumb_url = full_url
            else:
                continue
            photos.append({
                "type": "congrats",
                "label": c.get("customer_name", "Card"),
                "card_id": c.get("card_id"),
                "url": full_url, "thumbnail_url": thumb_url,
                "date": c["created_at"].isoformat() if c.get("created_at") else None,
            })

    # 4. Birthday card photos — only fast paths, skip base64
    bday_cards = await db.birthday_cards.find(
        {"contact_id": contact_id},
        {"card_id": 1, "customer_name": 1, "created_at": 1, "customer_photo": 1,
         "photo_path": 1, "photo_thumb_path": 1,
         "photo_url": 1, "photo_thumbnail_url": 1, "_id": 1}
    ).sort("created_at", -1).to_list(50)
    for bc in bday_cards:
        if bc.get("photo_path"):
            full_url = f"/api/images/{bc['photo_path']}"
            thumb_url = f"/api/images/{bc.get('photo_thumb_path', bc['photo_path'])}"
        elif bc.get("photo_url") and bc["photo_url"].startswith("/api/images/"):
            full_url = bc["photo_url"]
            thumb_url = bc.get("photo_thumbnail_url") or full_url
        elif bc.get("customer_photo") and bc["customer_photo"].startswith(("/api/images/", "http")):
            full_url = bc["customer_photo"]
            thumb_url = bc["customer_photo"]
        else:
            continue
        photos.append({
            "type": "birthday",
            "label": bc.get("customer_name", "Birthday"),
            "card_id": bc.get("card_id"),
            "url": full_url, "thumbnail_url": thumb_url,
            "date": bc["created_at"].isoformat() if bc.get("created_at") else None,
        })

    return {"photos": photos, "total": len(photos)}


@router.post("/admin/backfill-ownership")
async def backfill_contact_ownership():
    """Set ownership_type on all contacts based on source.
    manual/csv/phone_contacts → personal, everything else → org.
    Corrects any misclassified contacts."""
    db = get_db()
    
    # Set personal for manual, csv, phone_contacts sources
    personal_result = await db.contacts.update_many(
        {"source": {"$in": ["manual", "csv", "phone_contacts"]}, "ownership_type": {"$ne": "personal"}},
        {"$set": {"ownership_type": "personal"}}
    )
    
    # Set org for all other sources that aren't already set
    org_result = await db.contacts.update_many(
        {"source": {"$nin": ["manual", "csv", "phone_contacts"]}, "ownership_type": {"$ne": "org"}},
        {"$set": {"ownership_type": "org"}}
    )
    
    return {
        "status": "success",
        "personal_contacts": personal_result.modified_count,
        "org_contacts": org_result.modified_count
    }
