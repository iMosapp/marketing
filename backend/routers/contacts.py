"""
Contacts router - handles contact CRUD operations
"""
from fastapi import APIRouter, HTTPException, Body
from bson import ObjectId
from datetime import datetime, timezone, timedelta
from typing import List, Optional
import logging

from models import Contact, ContactCreate
from routers.database import get_db, get_data_filter, get_user_by_id, get_accessible_user_ids, increment_user_stat

router = APIRouter(prefix="/contacts", tags=["Contacts"])
logger = logging.getLogger(__name__)


async def _check_tag_campaign_enrollment(user_id: str, contact_id: str, contact_data: dict):
    """Auto-enroll contact in campaigns whose trigger_tag matches any of the contact's tags.
    Also immediately creates the first touchpoint task so it appears in Today's Touchpoints."""
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
            now = datetime.utcnow()

            # Calculate first step send time
            first_step = sequences[0] if sequences else None
            if first_step:
                delay_h = first_step.get('delay_hours', 0)
                delay_d = first_step.get('delay_days', 0)
                delay_m = first_step.get('delay_months', 0)
                if delay_h or delay_d or delay_m:
                    first_send = now + timedelta(hours=delay_h, days=delay_d + delay_m * 30)
                else:
                    first_send = now  # immediate
            else:
                first_send = now

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
                "enrolled_at": now,
                "next_send_at": first_send,
                "messages_sent": [],
                "trigger_type": "tag",
                "trigger_tag": campaign.get('trigger_tag', '')
            }
            enroll_result = await db.campaign_enrollments.insert_one(enrollment)
            logger.info(f"Auto-enrolled {contact_name} in campaign '{campaign.get('name')}' via tag '{campaign.get('trigger_tag')}'")

            # --- Immediately create task for the first step if due now ---
            if first_step and first_send <= now:
                delivery_mode = campaign.get('delivery_mode', 'manual')
                if delivery_mode != 'automated':
                    action_type = first_step.get('action_type', 'message')
                    channel = first_step.get('channel', 'sms')
                    message_content = first_step.get('message_template', first_step.get('message', ''))

                    if action_type == 'send_card':
                        card_type = first_step.get('card_type', 'congrats')
                        card_labels = {
                            'congrats': 'Congrats Card', 'birthday': 'Birthday Card',
                            'anniversary': 'Anniversary Card', 'thankyou': 'Thank You Card',
                            'welcome': 'Welcome Card', 'holiday': 'Holiday Card',
                        }
                        title = f"Send {card_labels.get(card_type, card_type.title() + ' Card')} to {contact_name}"
                        desc = f"Campaign '{campaign.get('name', '')}' step 1: {title}"
                        task_message = title
                    else:
                        title = f"Send {channel.upper()} to {contact_name}"
                        desc = f"Campaign '{campaign.get('name', '')}' step 1: {message_content[:200]}"
                        task_message = message_content

                    pending_result = await db.campaign_pending_sends.insert_one({
                        "user_id": user_id,
                        "campaign_id": campaign_id,
                        "campaign_name": campaign.get('name', ''),
                        "contact_id": contact_id,
                        "contact_name": contact_name,
                        "contact_phone": contact.get('phone', ''),
                        "step": 1,
                        "action_type": action_type,
                        "message": task_message,
                        "channel": channel,
                        "status": "pending",
                        "created_at": now,
                    })
                    await db.tasks.insert_one({
                        "user_id": user_id,
                        "contact_id": contact_id,
                        "type": "campaign_send",
                        "title": title,
                        "description": desc,
                        "due_date": now,
                        "priority": "high",
                        "priority_order": 1,
                        "status": "pending",
                        "completed": False,
                        "source": "campaign",
                        "campaign_id": campaign_id,
                        "contact_name": contact_name,
                        "contact_phone": contact.get('phone', ''),
                        "pending_send_id": str(pending_result.inserted_id),
                        "channel": channel,
                        "created_at": now,
                    })
                    await db.notifications.insert_one({
                        "user_id": user_id,
                        "type": "campaign_send",
                        "title": f"Campaign: {campaign.get('name', '')}",
                        "message": f"Time to send step 1 to {contact_name}",
                        "contact_name": contact_name,
                        "contact_id": contact_id,
                        "campaign_id": campaign_id,
                        "pending_send_step": 1,
                        "action_required": True,
                        "read": False,
                        "dismissed": False,
                        "created_at": now,
                    })

                    # Advance enrollment to step 2 so the scheduler doesn't double-fire step 1
                    next_send = None
                    if len(sequences) > 1:
                        s2 = sequences[1]
                        dh = s2.get('delay_hours', 0)
                        dd = s2.get('delay_days', 0)
                        dm = s2.get('delay_months', 0)
                        next_send = now + timedelta(hours=dh, days=dd + dm * 30) if (dh or dd or dm) else now

                    update_set = {"current_step": 2, "last_sent_at": now}
                    if next_send and len(sequences) > 1:
                        update_set["next_send_at"] = next_send
                    else:
                        update_set["status"] = "completed"
                        update_set["next_send_at"] = None

                    await db.campaign_enrollments.update_one(
                        {"_id": enroll_result.inserted_id},
                        {
                            "$set": update_set,
                            "$push": {"messages_sent": {"step": 1, "action_type": action_type, "sent_at": now, "content": message_content[:100]}}
                        }
                    )
                    logger.info(f"Immediately created task for step 1 of '{campaign.get('name')}' → {contact_name}")
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

    # Sold workflow hook — runs AFTER all saves, never blocks
    sold_result = None
    try:
        from routers.sold_workflow import process_sold_workflow
        sold_result = await process_sold_workflow(
            user_id=user_id,
            contact_id=str(result.inserted_id),
            contact_data=contact_dict,
            old_tags=[],  # No old tags on create
            trigger_source="create",
        )
    except Exception as e:
        logger.warning(f"Sold workflow error (non-blocking): {e}")

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

@router.get("/{user_id}")
async def get_contacts(
    user_id: str,
    search: Optional[str] = None,
    view_mode: Optional[str] = None,
    sort_by: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    paginated: bool = False,  # Set True by new frontend — returns {contacts, total, has_more}
                              # Old clients get plain array for backward compatibility
):
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
        # Use last_activity_at index if field exists on contacts (populated by log_contact_event)
        # Falls back to in-memory sort for contacts that predate the field (first deploy only)
        indexed_count = await db.contacts.count_documents({**query, "last_activity_at": {"$exists": True}})
        total = await db.contacts.count_documents(query)

        if indexed_count > total * 0.8:
            # Most contacts have the field — use the fast indexed sort
            contacts = await db.contacts.find(query, {"photo": 0}).sort(
                [("last_activity_at", -1), ("updated_at", -1)]
            ).skip(skip).limit(limit).to_list(limit)
        else:
            # Backfill not yet run — fall back to in-memory sort (temporary)
            activity_pipeline = [
                {"$match": {"user_id": user_id}},
                {"$group": {"_id": "$contact_id", "last_activity": {"$max": "$timestamp"}}},
            ]
            activity_results = await db.contact_events.aggregate(activity_pipeline).to_list(2000)
            activity_map = {r["_id"]: r["last_activity"] for r in activity_results}
            all_contacts = await db.contacts.find(query, {"photo": 0}).to_list(2000)
            epoch = datetime(2000, 1, 1)
            for c in all_contacts:
                cid = str(c.get("_id", ""))
                c["_last_activity"] = activity_map.get(cid, c.get("updated_at", c.get("created_at", epoch)))
            all_contacts.sort(key=lambda c: c.get("_last_activity", epoch), reverse=True)
            for c in all_contacts:
                c.pop("_last_activity", None)
            total = len(all_contacts)
            contacts = all_contacts[skip: skip + limit]
    else:
        sort_spec = [("first_name", 1), ("last_name", 1)]
        total = await db.contacts.count_documents(query)
        contacts = await db.contacts.find(query, {"photo": 0}).sort(sort_spec).skip(skip).limit(limit).to_list(limit)
    
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
    # Run as background task to not block the response
    needs_backfill = [c for c in contacts if not c.get('photo_thumbnail') and not c.get('photo_url')]
    if needs_backfill:
        import asyncio
        async def _backfill_photos(ids_to_backfill):
            try:
                photo_docs = await db.contacts.find(
                    {"_id": {"$in": ids_to_backfill}, "photo": {"$exists": True, "$nin": [None, "", "None"]}},
                    {"_id": 1, "photo": 1}
                ).to_list(len(ids_to_backfill))
                for pdoc in photo_docs:
                    photo_data = pdoc.get('photo', '')
                    if photo_data and len(photo_data) > 100:
                        try:
                            thumbnail, high_res = await _process_photo(photo_data)
                            await db.contacts.update_one(
                                {"_id": pdoc['_id']},
                                {"$set": {"photo_thumbnail": thumbnail, "photo_url": thumbnail}}
                            )
                            cid = str(pdoc['_id'])
                            await db.contact_photos.update_one(
                                {"contact_id": cid},
                                {"$set": {"contact_id": cid, "photo_full": high_res, "updated_at": datetime.utcnow()}},
                                upsert=True
                            )
                            logger.info(f"Backfilled thumbnail for contact {cid}")
                        except Exception as e:
                            logger.error(f"Failed to backfill thumbnail for {pdoc['_id']}: {e}")
            except Exception as e:
                logger.error(f"Photo backfill batch failed: {e}")
        # Only backfill if not already running (prevents task accumulation)
        if needs_backfill and not getattr(_backfill_photos, '_running', False):
            asyncio.create_task(_backfill_photos([c['_id'] for c in needs_backfill]))
    
    results = []
    for c in contacts:
        c_dict = {**c, "_id": str(c["_id"])}
        # Enrich with salesperson name for team view
        if salesperson_map:
            c_dict["salesperson_name"] = salesperson_map.get(c.get("user_id", ""), "")
        results.append(Contact(**c_dict))

    return {
        "contacts": results,
        "total": total,
        "skip": skip,
        "limit": limit,
        "has_more": (skip + limit) < total,
    } if paginated else results  # plain array for old clients

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

    # Capture old tags BEFORE save for sold workflow detection
    db = get_db()
    _old_contact_for_tags = await db.contacts.find_one(
        {"_id": ObjectId(contact_id)}, {"tags": 1}
    )
    _old_tags = _old_contact_for_tags.get("tags", []) if _old_contact_for_tags else []
    
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

    # Sold workflow hook — runs AFTER all saves, never blocks
    sold_result = None
    try:
        from routers.sold_workflow import process_sold_workflow
        sold_result = await process_sold_workflow(
            user_id=user_id,
            contact_id=contact_id,
            contact_data=update_dict,
            old_tags=_old_tags,
            trigger_source="update",
        )
    except Exception as e:
        logger.warning(f"Sold workflow error (non-blocking): {e}")

    response = {"message": "Contact updated successfully"}
    if sold_result:
        response["sold_workflow"] = sold_result
    return response

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
                # Check if this URL already exists in photo_history before pushing
                existing_history = await db.contacts.find_one(
                    {"_id": ObjectId(contact_id), "photo_history.url": old_url},
                    {"_id": 1}
                )
                if not existing_history:
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



@router.delete("/{user_id}/{contact_id}/photos")
async def delete_contact_photo(user_id: str, contact_id: str, data: dict = Body(...)):
    """Delete a photo from a contact's gallery. Handles profile, history, congrats, and birthday photos."""
    db = get_db()
    photo_url = data.get("photo_url", "")
    photo_type = data.get("photo_type", "")
    if not photo_url:
        raise HTTPException(status_code=400, detail="photo_url is required")

    try:
        oid = ObjectId(contact_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid contact_id")

    if photo_type == "profile":
        # Remove current profile photo; promote most recent history photo if available
        contact = await db.contacts.find_one({"_id": oid}, {"photo_history": 1})
        history = contact.get("photo_history", []) if contact else []

        if history:
            # Pop last history entry as new profile
            new_profile = history[-1]
            await db.contacts.update_one(
                {"_id": oid},
                {
                    "$set": {
                        "photo": new_profile["url"],
                        "photo_url": new_profile["url"],
                        "photo_thumbnail": new_profile.get("thumbnail_url", new_profile["url"]),
                        "updated_at": datetime.utcnow(),
                    },
                    "$pop": {"photo_history": 1},
                    "$unset": {"photo_path": "", "photo_thumb_path": "", "photo_avatar_path": ""},
                }
            )
        else:
            # No history — just clear the profile photo
            await db.contacts.update_one(
                {"_id": oid},
                {
                    "$set": {"updated_at": datetime.utcnow()},
                    "$unset": {
                        "photo": "", "photo_url": "", "photo_thumbnail": "",
                        "photo_path": "", "photo_thumb_path": "", "photo_avatar_path": "",
                    },
                }
            )
        # Also remove from contact_photos collection
        await db.contact_photos.delete_one({"contact_id": contact_id})

    elif photo_type == "history":
        # Remove from photo_history array
        await db.contacts.update_one(
            {"_id": oid},
            {"$pull": {"photo_history": {"url": photo_url}}}
        )

    elif photo_type == "congrats":
        # Remove from congrats_cards (match by photo URL)
        await db.congrats_cards.update_one(
            {"$or": [
                {"photo_url": photo_url},
                {"customer_photo": photo_url},
            ]},
            {"$unset": {"photo_url": "", "photo_thumbnail_url": "", "photo_path": "", "photo_thumb_path": "", "customer_photo": ""}}
        )

    elif photo_type == "birthday":
        await db.birthday_cards.update_one(
            {"$or": [
                {"photo_url": photo_url},
                {"customer_photo": photo_url},
            ]},
            {"$unset": {"photo_url": "", "photo_thumbnail_url": "", "photo_path": "", "photo_thumb_path": "", "customer_photo": ""}}
        )
    else:
        raise HTTPException(status_code=400, detail="Invalid photo_type")

    return {"message": "Photo deleted"}



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

    # Capture old tags BEFORE save for sold workflow detection
    old_contact = await db.contacts.find_one({"_id": ObjectId(contact_id), "user_id": user_id}, {"tags": 1})
    old_tags = old_contact.get("tags", []) if old_contact else []

    result = await db.contacts.update_one(
        {"_id": ObjectId(contact_id), "user_id": user_id},
        {"$set": {"tags": tags, "updated_at": datetime.now(timezone.utc)}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Contact not found")

    # Trigger campaign enrollment for any new tags
    contact = await db.contacts.find_one({"_id": ObjectId(contact_id)})
    if contact:
        contact["_id"] = str(contact["_id"])
        await _check_tag_campaign_enrollment(user_id, contact_id, contact)

    # Sold workflow hook — runs AFTER tag save, never blocks it
    sold_result = None
    try:
        from routers.sold_workflow import process_sold_workflow
        sold_result = await process_sold_workflow(
            user_id=user_id,
            contact_id=contact_id,
            contact_data={"tags": tags},
            old_tags=old_tags,
            trigger_source="tag_patch",
        )
    except Exception as e:
        logger.warning(f"Sold workflow error (non-blocking): {e}")

    response = {"tags": tags}
    if sold_result:
        response["sold_workflow"] = sold_result
    return response




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
    ).to_list(2000)
    
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

    # Deduplicate by URL — keep first occurrence (profile > history > congrats > birthday)
    seen_urls = set()
    unique_photos = []
    for p in photos:
        url = p.get("url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique_photos.append(p)
    
    return {"photos": unique_photos, "total": len(unique_photos)}


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



@router.get("/{user_id}/{contact_id}/campaign-journey")
async def get_contact_campaign_journey(user_id: str, contact_id: str):
    """Get all campaign enrollments for a contact with full step details."""
    db = get_db()

    enrollments = await db.campaign_enrollments.find(
        {"contact_id": contact_id, "user_id": user_id, "status": {"$ne": "archived"}},
    ).to_list(100)

    # Pre-load pending sends and tasks for this contact to cross-reference
    pending_sends = await db.campaign_pending_sends.find(
        {"contact_id": contact_id, "user_id": user_id}
    ).to_list(200)
    ps_by_key = {}
    for ps in pending_sends:
        key = f"{ps.get('campaign_id')}_{ps.get('step')}"
        ps_by_key[key] = ps

    campaign_tasks = await db.tasks.find(
        {"contact_id": contact_id, "user_id": user_id, "type": "campaign_send"}
    ).to_list(200)
    task_by_key = {}
    for t in campaign_tasks:
        cid = t.get("campaign_id", "")
        # Get step from pending_send
        psid = t.get("pending_send_id", "")
        if psid:
            for ps in pending_sends:
                if str(ps.get("_id")) == psid:
                    key = f"{cid}_{ps.get('step')}"
                    task_by_key[key] = t
                    break

    journeys = []
    for enrollment in enrollments:
        enrollment_id = str(enrollment.get("_id", ""))
        campaign_id = enrollment.get("campaign_id", "")
        campaign = None
        try:
            campaign = await db.campaigns.find_one(
                {"_id": ObjectId(campaign_id)},
                {"_id": 0, "name": 1, "sequences": 1, "type": 1, "trigger_tag": 1, "ai_enabled": 1, "delivery_mode": 1}
            )
        except Exception:
            pass
        if not campaign:
            campaign = await db.campaigns.find_one(
                {"_id": campaign_id},
                {"_id": 0, "name": 1, "sequences": 1, "type": 1, "trigger_tag": 1, "ai_enabled": 1, "delivery_mode": 1}
            )
        if not campaign:
            continue

        sequences = campaign.get("sequences", [])
        current_step = enrollment.get("current_step", 1)
        messages_sent = enrollment.get("messages_sent", [])
        status = enrollment.get("status", "active")
        delivery_mode = campaign.get("delivery_mode", "manual")

        steps = []
        for i, seq in enumerate(sequences):
            step_num = i + 1
            sent_record = next((m for m in messages_sent if m.get("step") == step_num), None)
            ps_key = f"{campaign_id}_{step_num}"
            ps_doc = ps_by_key.get(ps_key)
            task_doc = task_by_key.get(ps_key)

            step_info = {
                "step": step_num,
                "message": seq.get("message_template", "") or seq.get("message", ""),
                "channel": seq.get("channel", "sms"),
                "delay_hours": seq.get("delay_hours", 0),
                "delay_days": seq.get("delay_days", 0),
                "delay_months": seq.get("delay_months", 0),
                "ai_generated": seq.get("ai_generated", False),
                "step_context": seq.get("step_context", ""),
                "enrollment_id": enrollment_id,
                "campaign_id": campaign_id,
            }

            # Include pending_send_id if exists
            if ps_doc:
                step_info["pending_send_id"] = str(ps_doc["_id"])
                # Use the actual message from pending send (may have template vars replaced)
                if ps_doc.get("message"):
                    step_info["full_message"] = ps_doc["message"]

            if sent_record:
                record_status = sent_record.get("status")
                if record_status is None:
                    if delivery_mode == "manual":
                        if task_doc and task_doc.get("completed"):
                            record_status = "sent"
                        elif task_doc and not task_doc.get("completed"):
                            record_status = "pending"
                        elif ps_doc and ps_doc.get("status") in ("sent", "pending_user_action"):
                            record_status = "sent"
                        elif ps_doc and ps_doc.get("status") == "pending":
                            record_status = "pending"
                        else:
                            record_status = "sent"
                    else:
                        record_status = "sent"

                if record_status == "pending":
                    # ── KEY FIX: only "pending_send" if actually DUE NOW ──
                    # If send_at is in the future, it's "upcoming" not "ready to send"
                    is_due_now = True
                    if ps_doc and ps_doc.get("send_at"):
                        ps_send_at = ps_doc["send_at"]
                        if hasattr(ps_send_at, "replace"):
                            ps_send_at_utc = ps_send_at.replace(tzinfo=None) if ps_send_at.tzinfo else ps_send_at
                        else:
                            ps_send_at_utc = ps_send_at
                        is_due_now = ps_send_at_utc <= datetime.utcnow()

                    if is_due_now:
                        step_info["status"] = "pending_send"
                        queued = sent_record.get("queued_at", sent_record.get("sent_at"))
                        step_info["queued_at"] = queued.isoformat() if queued else None
                    else:
                        # Step exists in queue but not due yet — show scheduled time
                        step_info["status"] = "upcoming"
                        if ps_doc and ps_doc.get("send_at"):
                            step_info["scheduled_at"] = ps_doc["send_at"].isoformat() if hasattr(ps_doc["send_at"], "isoformat") else str(ps_doc["send_at"])
                else:
                    step_info["status"] = "sent"
                    sent_at = sent_record.get("sent_at")
                    step_info["sent_at"] = sent_at.isoformat() if sent_at else None
            elif step_num == current_step and status == "active":
                step_info["status"] = "next"
                # Use ps_doc.send_at for precise timing (pre-scheduled queue)
                if ps_doc and ps_doc.get("send_at"):
                    step_info["scheduled_at"] = ps_doc["send_at"].isoformat() if hasattr(ps_doc["send_at"], "isoformat") else str(ps_doc["send_at"])
                else:
                    next_send = enrollment.get("next_send_at")
                    step_info["scheduled_at"] = next_send.isoformat() if next_send else None
            elif step_num > current_step or status == "active":
                step_info["status"] = "upcoming"
                # Add scheduled_at from pre-scheduled queue so frontend shows "Sends Apr 2 7:51 PM"
                if ps_doc and ps_doc.get("send_at"):
                    step_info["scheduled_at"] = ps_doc["send_at"].isoformat() if hasattr(ps_doc["send_at"], "isoformat") else str(ps_doc["send_at"])
            else:
                step_info["status"] = "upcoming"
                if ps_doc and ps_doc.get("send_at"):
                    step_info["scheduled_at"] = ps_doc["send_at"].isoformat() if hasattr(ps_doc["send_at"], "isoformat") else str(ps_doc["send_at"])

            steps.append(step_info)

        journeys.append({
            "campaign_name": campaign.get("name", enrollment.get("campaign_name", "Unknown")),
            "campaign_type": campaign.get("type", ""),
            "trigger_tag": campaign.get("trigger_tag", ""),
            "ai_enabled": campaign.get("ai_enabled", False),
            "status": status,
            "current_step": current_step,
            "total_steps": len(sequences),
            "enrolled_at": enrollment.get("enrolled_at", "").isoformat() if enrollment.get("enrolled_at") else None,
            "next_send_at": enrollment.get("next_send_at", "").isoformat() if enrollment.get("next_send_at") else None,
            "enrollment_id": enrollment_id,
            "steps": steps,
        })

    return journeys


@router.post("/{user_id}/{contact_id}/campaign-journey/mark-sent")
async def mark_campaign_step_sent(user_id: str, contact_id: str, body: dict):
    """Mark a campaign step as sent from the contact page. Single action that updates everything."""
    db = get_db()
    enrollment_id = body.get("enrollment_id", "")
    step_num = body.get("step")
    pending_send_id = body.get("pending_send_id", "")

    if not enrollment_id or not step_num:
        raise HTTPException(status_code=400, detail="enrollment_id and step are required")

    now = datetime.now(timezone.utc)

    # 1. Update or create enrollment messages_sent entry
    # Try to update existing entry first
    result = await db.campaign_enrollments.update_one(
        {"_id": ObjectId(enrollment_id), "messages_sent.step": step_num},
        {"$set": {
            "messages_sent.$.status": "sent",
            "messages_sent.$.sent_at": now,
            "last_sent_at": now,
        }}
    )
    # If no existing entry matched, push a new one
    if result.modified_count == 0:
        await db.campaign_enrollments.update_one(
            {"_id": ObjectId(enrollment_id)},
            {
                "$push": {"messages_sent": {
                    "step": step_num,
                    "status": "sent",
                    "sent_at": now,
                    "delivery_mode": "manual",
                }},
                "$set": {"last_sent_at": now},
            }
        )

    # 2. Update pending send
    if pending_send_id:
        await db.campaign_pending_sends.update_one(
            {"_id": ObjectId(pending_send_id)},
            {"$set": {"status": "sent", "sent_at": now}}
        )

    # 3. Complete associated task
    task = None
    if pending_send_id:
        task = await db.tasks.find_one({
            "user_id": user_id, "pending_send_id": pending_send_id, "type": "campaign_send"
        })
    if not task:
        # Fallback: find by campaign_id and contact_id
        enrollment = await db.campaign_enrollments.find_one({"_id": ObjectId(enrollment_id)})
        if enrollment:
            task = await db.tasks.find_one({
                "user_id": user_id,
                "contact_id": contact_id,
                "campaign_id": enrollment.get("campaign_id", ""),
                "type": "campaign_send",
                "completed": {"$ne": True},
            })

    if task:
        await db.tasks.update_one(
            {"_id": task["_id"]},
            {"$set": {"status": "completed", "completed": True, "completed_at": now}}
        )

    # 4. Log one clean activity event
    enrollment = await db.campaign_enrollments.find_one({"_id": ObjectId(enrollment_id)})
    campaign_name = (enrollment or {}).get("campaign_name", "Campaign")
    contact_name = (enrollment or {}).get("contact_name", "contact")

    await db.contact_events.insert_one({
        "event_type": "campaign_step_sent",
        "user_id": user_id,
        "contact_id": contact_id,
        "title": f"Sent Step {step_num} of {campaign_name}",
        "description": f"Manually sent campaign step {step_num} to {contact_name}",
        "timestamp": now,
        "source": "campaign_journey",
    })

    return {"success": True, "message": f"Step {step_num} marked as sent"}


@router.post("/{user_id}/{contact_id}/campaign-journey/remove")
async def remove_campaign_enrollment(user_id: str, contact_id: str, data: dict = {}):
    """
    Archive a campaign enrollment for a contact and cancel any pending sends.
    The enrollment history is preserved (status → 'archived') so you can see
    what was sent in the past. The contact can be manually re-enrolled later.
    """
    db = get_db()
    enrollment_id = data.get("enrollment_id")
    if not enrollment_id:
        raise HTTPException(status_code=400, detail="enrollment_id is required")

    # Find the enrollment
    enrollment = await db.campaign_enrollments.find_one({
        "_id": ObjectId(enrollment_id),
        "contact_id": contact_id,
    })
    if not enrollment:
        raise HTTPException(status_code=404, detail="Enrollment not found")

    campaign_id = enrollment.get("campaign_id", "")
    campaign_name = enrollment.get("campaign_name", "")

    # If campaign_name not on enrollment, look it up
    if not campaign_name and campaign_id:
        try:
            campaign = await db.campaigns.find_one({"_id": ObjectId(campaign_id)}, {"name": 1})
            campaign_name = campaign.get("name", "") if campaign else ""
        except Exception:
            pass

    # Archive the enrollment (keep history, mark as archived)
    now = datetime.now(timezone.utc)
    await db.campaign_enrollments.update_one(
        {"_id": ObjectId(enrollment_id)},
        {"$set": {
            "status": "archived",
            "archived_at": now,
            "archived_by": user_id,
            "previous_status": enrollment.get("status", "active"),
        }}
    )

    # Cancel any pending sends for this enrollment
    cancelled = await db.campaign_pending_sends.update_many(
        {
            "campaign_id": campaign_id,
            "contact_id": contact_id,
            "status": "pending",
        },
        {"$set": {"status": "cancelled", "cancelled_at": now}}
    )

    # Log the action as a contact event
    contact = await db.contacts.find_one({"_id": ObjectId(contact_id)}, {"first_name": 1, "last_name": 1})
    contact_name = f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip() if contact else "Contact"

    await db.contact_events.insert_one({
        "user_id": user_id,
        "contact_id": contact_id,
        "contact_name": contact_name,
        "event_type": "campaign_removed",
        "icon": "close-circle",
        "color": "#FF3B30",
        "title": "Campaign Removed",
        "description": f"Removed '{campaign_name}' campaign. {cancelled.modified_count} pending sends cancelled.",
        "category": "campaigns",
        "timestamp": now,
        "metadata": {
            "campaign_id": campaign_id,
            "campaign_name": campaign_name,
            "enrollment_id": enrollment_id,
            "cancelled_sends": cancelled.modified_count,
        },
    })

    return {
        "success": True,
        "message": f"Campaign '{campaign_name}' removed from contact",
        "cancelled_pending_sends": cancelled.modified_count,
    }
