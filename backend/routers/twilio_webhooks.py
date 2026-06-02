"""
Twilio Webhooks Router - Handle incoming SMS/MMS messages
"""
import asyncio
from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import Response
from bson import ObjectId
from datetime import datetime
from typing import Optional, List
import logging
import os
import httpx
import base64

from routers.database import get_db

router = APIRouter(prefix="/webhooks/twilio", tags=["Twilio Webhooks"])
logger = logging.getLogger(__name__)

# Backend URL for constructing media URLs
BACKEND_URL = os.environ.get("REACT_APP_BACKEND_URL", "")


async def download_and_store_media(media_url: str, media_type: str) -> Optional[str]:
    """
    Download media from Twilio URL and store it in our database.
    Returns the media_id for our own endpoint.
    """
    try:
        # Twilio requires authentication to download media
        twilio_sid = os.environ.get("TWILIO_ACCOUNT_SID")
        twilio_token = os.environ.get("TWILIO_AUTH_TOKEN")
        
        if not twilio_sid or not twilio_token:
            logger.warning("Twilio credentials not configured for media download")
            return None
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                media_url,
                auth=(twilio_sid, twilio_token),
                follow_redirects=True,
                timeout=30.0
            )
            
            if response.status_code != 200:
                logger.error(f"Failed to download media: {response.status_code}")
                return None
            
            # Convert to base64
            media_bytes = response.content
            base64_data = base64.b64encode(media_bytes).decode('utf-8')
            
            # Create data URL
            data_url = f"data:{media_type};base64,{base64_data}"
            
            # Store in database
            media_doc = {
                "data": data_url,
                "content_type": media_type,
                "size": len(media_bytes),
                "source": "twilio_inbound",
                "original_url": media_url,
                "created_at": datetime.utcnow()
            }
            
            result = await get_db().media.insert_one(media_doc)
            media_id = str(result.inserted_id)
            
            logger.info(f"Stored inbound media: {media_id} ({len(media_bytes)} bytes)")
            return media_id
            
    except Exception as e:
        logger.error(f"Error downloading/storing media: {str(e)}")
        return None


@router.post("/incoming")
async def incoming_message(
    request: Request,
    From: str = Form(...),
    To: str = Form(...),
    Body: str = Form(default=""),
    MessageSid: str = Form(default=""),
    NumMedia: str = Form(default="0"),
    MediaUrl0: Optional[str] = Form(default=None),
    MediaUrl1: Optional[str] = Form(default=None),
    MediaUrl2: Optional[str] = Form(default=None),
    MediaContentType0: Optional[str] = Form(default=None),
    MediaContentType1: Optional[str] = Form(default=None),
    MediaContentType2: Optional[str] = Form(default=None),
):
    """
    Webhook endpoint for incoming SMS/MMS from Twilio.
    
    Twilio sends a POST request with form data including:
    - From: Sender's phone number
    - To: Your Twilio number
    - Body: Message text
    - NumMedia: Number of media attachments
    - MediaUrl0, MediaUrl1, etc.: URLs to media files
    - MediaContentType0, etc.: MIME types of media
    """
    db = get_db()
    
    logger.info(f"Incoming message from {From} to {To}: {Body[:50]}...")
    
    # Normalize phone numbers
    from_phone = normalize_phone(From)
    to_phone   = normalize_phone(To)
    
    # ── Deduplication: reject Twilio retries for the same MessageSid ──────────
    # Use an atomic upsert so parallel webhook retries can't both slip through.
    if MessageSid:
        try:
            dup_result = await db.inbound_message_dedup.update_one(
                {"message_sid": MessageSid},
                {"$setOnInsert": {"message_sid": MessageSid, "created_at": __import__("datetime").datetime.utcnow()}},
                upsert=True,
            )
            if not dup_result.upserted_id:
                # Already in the table — this is a Twilio retry
                logger.warning(f"[Webhook] Duplicate MessageSid {MessageSid} (atomic check) — ignoring Twilio retry")
                return Response(
                    content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
                    media_type="application/xml"
                )
        except Exception as dedup_err:
            # Fall back to the legacy messages check if upsert fails
            logger.warning(f"[Webhook] Atomic dedup failed, falling back: {dedup_err}")
            already = await db.messages.find_one({"twilio_sid": MessageSid})
            if already:
                logger.warning(f"[Webhook] Duplicate MessageSid {MessageSid} (legacy check) — ignoring")
                return Response(
                    content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
                    media_type="application/xml"
                )
    
    # Collect media URLs
    media_urls  = []
    media_types = []
    num_media = int(NumMedia) if NumMedia else 0
    if num_media > 0:
        if MediaUrl0: media_urls.append(MediaUrl0); media_types.append(MediaContentType0 or 'image/jpeg')
        if MediaUrl1: media_urls.append(MediaUrl1); media_types.append(MediaContentType1 or 'image/jpeg')
        if MediaUrl2: media_urls.append(MediaUrl2); media_types.append(MediaContentType2 or 'image/jpeg')
    
    try:
        # ── Step 1: Route by To: number → find the rep who owns this number ──
        # Important: do NOT filter by is_active here — a rep's dedicated number
        # should always route to them even if their account isn't fully active yet.
        rep_user = await db.users.find_one({
            "$or": [{"twilio_number": to_phone}, {"mvpline_number": to_phone}],
            "status": {"$ne": "deactivated"},  # only exclude hard-deactivated accounts
        })
        if rep_user:
            logger.info(f"[Webhook] Inbound {to_phone} → rep={rep_user.get('name')} ({rep_user.get('_id')})")
        else:
            logger.warning(f"[Webhook] No rep found for {to_phone} — will fall back to pool/super_admin")
        if not rep_user:
            # Check if this is a pooled number (rep was terminated)
            pool_entry = await db.phone_number_pool.find_one({
                "phone_number": to_phone,
                "status": "pool",
            })
            if pool_entry and pool_entry.get("previous_store_id"):
                # Route to the store manager for that store
                store_id = pool_entry["previous_store_id"]
                rep_user = await db.users.find_one({
                    "$or": [{"store_id": store_id}, {"store_ids": store_id}],
                    "role": {"$in": ["store_manager", "org_admin"]},
                    "status": {"$ne": "deactivated"},
                    "is_active": {"$ne": False},
                })
                if rep_user:
                    logger.info(f"[Webhook] Pooled number {to_phone} routed to store manager {rep_user.get('name')} (store: {store_id})")
                else:
                    logger.info(f"[Webhook] Pooled number {to_phone} — no store manager found for store {store_id}, falling back to super_admin")
        if not rep_user:
            # Fall back to first super_admin
            rep_user = await db.users.find_one({"role": {"$in": ["super_admin", "org_admin"]}})
        
        rep_user_id = str(rep_user["_id"]) if rep_user else None
        rep_name    = (rep_user.get("name") or "").split()[0] if rep_user else "your rep"

        # ── Step 2: Find or create contact — STRICT REP NAMESPACE ───────────────
        # CRITICAL: Only look in the rep's namespace (user_id = rep_user_id).
        # Never look at other reps' contacts — the same customer phone number
        # exists in multiple reps' contact books and MUST stay isolated.
        alt_phone = from_phone.replace("+1", "") if from_phone.startswith("+1") else "+1" + from_phone.lstrip("+")
        contact = await db.contacts.find_one({
            "user_id": rep_user_id,
            "$or": [
                {"phone": from_phone},
                {"phone": alt_phone},
                {"phone": from_phone.lstrip("+")},
            ]
        })

        is_new_contact = False
        if not contact:
            is_new_contact = True
            # Enrich: try to find the contact's real name from any other rep's namespace
            # This prevents "Lead (9122)" when "Forest Ward" is already known in the system
            enriched_name = f"Lead ({from_phone[-4:]})"
            enriched_photo = None
            enriched_first = "New"
            enriched_last  = "Lead"
            try:
                any_contact = await db.contacts.find_one(
                    {"$or": [{"phone": from_phone}, {"phone": alt_phone}, {"phone": from_phone.lstrip("+")}]},
                    {"name": 1, "first_name": 1, "last_name": 1, "photo_url": 1, "photo_thumbnail": 1}
                )
                if any_contact and any_contact.get("name") and not any_contact["name"].startswith("Lead ("):
                    enriched_name  = any_contact["name"]
                    enriched_first = any_contact.get("first_name") or enriched_name.split()[0]
                    enriched_last  = any_contact.get("last_name")  or (" ".join(enriched_name.split()[1:]) if " " in enriched_name else "")
                    enriched_photo = any_contact.get("photo_url") or any_contact.get("photo_thumbnail")
                    logger.info(f"[Webhook] Enriched new contact name from system: {enriched_name}")
            except Exception:
                pass

            contact = {
                "phone":       from_phone,
                "first_name":  enriched_first,
                "last_name":   enriched_last,
                "name":        enriched_name,
                "photo_url":   enriched_photo,
                "source":      "sms_inbound",
                "user_id":     rep_user_id,
                "original_user_id": rep_user_id,
                "tags":        ["Inbound Lead"],
                "status":      "active",
                "created_at":  datetime.utcnow(),
                "updated_at":  datetime.utcnow(),
            }
            result = await db.contacts.insert_one(contact)
            contact["_id"] = result.inserted_id
            logger.info(f"[Webhook] New contact '{enriched_name}' created for {from_phone} in rep {rep_user_id}'s namespace")

        contact_id = str(contact["_id"])
        user_id    = rep_user_id   # ALWAYS use the number owner's user_id — never the contact's stored user_id

        is_stop = False

        # ── Step 3: Find or create conversation — PRIMARY KEY: (rep_phone, contact_phone) ──
        # This is the ONLY correct key. The same customer can have conversations
        # with 100 different reps — each is completely isolated by rep_phone.
        conversation = await db.conversations.find_one({
            "rep_phone":     to_phone,     # Jessi's +13854443045 — the number the customer texted
            "contact_phone": from_phone,   # The customer's phone
        })

        if not conversation:
            # Backfill: check old-model conversations for this rep+contact pair
            phone_variants = [from_phone, alt_phone, from_phone.lstrip("+")]
            conversation = await db.conversations.find_one({
                "user_id":      rep_user_id,
                "contact_id":   contact_id,
            })
            if not conversation:
                # Also try by phone (catches conversations before this rep was assigned)
                conversation = await db.conversations.find_one({
                    "user_id":       rep_user_id,
                    "contact_phone": {"$in": phone_variants},
                }, sort=[("last_message_at", -1)])
            if conversation:
                # Backfill rep_phone so future lookups use the fast path
                # Also update contact_name in case it was "Contact" or "Lead (XXXX)"
                updated_name = contact.get("name") or conversation.get("contact_name", "")
                await db.conversations.update_one(
                    {"_id": conversation["_id"]},
                    {"$set": {
                        "rep_phone":     to_phone,
                        "contact_phone": from_phone,
                        "user_id":       rep_user_id,
                        "contact_id":    contact_id,
                        "contact_name":  updated_name if updated_name and not updated_name.startswith("Lead (") else conversation.get("contact_name", updated_name),
                    }}
                )
                logger.info(f"[Webhook] Backfilled rep_phone={to_phone} on existing conversation {conversation['_id']}")

        if not conversation:
            contact_name = (contact.get("name") or f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip() or f"({from_phone[-4:]})")
            conversation = {
                "user_id":       rep_user_id,
                "rep_phone":     to_phone,
                "contact_id":    contact_id,
                "contact_phone": from_phone,
                "contact_name":  contact_name,
                "status":        "active",
                "ai_enabled":    False,
                "ai_mode":       "suggest",
                "unread":        True,
                "unread_count":  1,
                "needs_assistance": False,
                "created_at":    datetime.utcnow(),
                "last_message_at": datetime.utcnow()
            }
            result = await db.conversations.insert_one(conversation)
            conversation["_id"] = result.inserted_id
            logger.info(f"[Webhook] New conversation: rep_phone={to_phone} contact_phone={from_phone} user={rep_user_id}")
        else:
            await db.conversations.update_one(
                {"_id": conversation["_id"]},
                {
                    "$set": {
                        "last_message_at": datetime.utcnow(),
                        "unread": True,
                        "status": "active"
                    },
                    "$inc": {"unread_count": 1}
                }
            )
        
        conversation_id = str(conversation["_id"])
        
        # Create the message
        message = {
            "conversation_id": conversation_id,
            "content": Body,
            "sender": "contact",
            "timestamp": datetime.utcnow(),
            "status": "received",
            "twilio_sid": MessageSid,
            "from_phone": from_phone,
            "to_phone": to_phone,
        }
        
        # Add media if present - download and store permanently
        if media_urls:
            stored_media_urls = []
            stored_media_ids = []
            
            for i, twilio_url in enumerate(media_urls):
                media_type = media_types[i] if i < len(media_types) else 'image/jpeg'
                media_id = await download_and_store_media(twilio_url, media_type)
                
                if media_id:
                    # Use our own media endpoint URL
                    our_url = f"{BACKEND_URL}/api/messages/media/{media_id}"
                    stored_media_urls.append(our_url)
                    stored_media_ids.append(media_id)
                else:
                    # Fall back to Twilio URL if download failed
                    stored_media_urls.append(twilio_url)
            
            message["media_urls"] = stored_media_urls
            message["media_ids"] = stored_media_ids
            message["media_types"] = media_types
            message["has_media"] = True
            message["num_media"] = num_media
            message["original_twilio_urls"] = media_urls  # Keep original for reference
        
        await db.messages.insert_one(message)
        logger.info(f"Saved incoming message to conversation {conversation_id}")

        # ── Auto-reopen closed conversation when customer replies ──────────────
        # If the conversation was marked closed, reopen it so the rep sees it
        # in their active inbox instead of the Closed tab.
        if conversation.get("status") == "closed":
            await db.conversations.update_one(
                {"_id": ObjectId(conversation_id)},
                {"$set": {
                    "status":            "active",
                    "reopened_at":       datetime.utcnow(),
                    "reopened_reason":   "customer_replied",
                    "needs_assistance":  True,   # Immediately flag for rep attention
                }}
            )
            logger.info(f"[Webhook] Auto-reopened closed conversation {conversation_id} (customer replied)")

        # ── Increment conversation-level unanswered count ──────────────────────
        # Uses AFTER so we get the new incremented value, not the pre-increment value
        from pymongo import ReturnDocument as _RD
        convo_update = await db.conversations.find_one_and_update(
            {"_id": ObjectId(conversation_id)},
            {"$inc": {"unanswered_customer_replies": 1}},
            return_document=_RD.AFTER,
            projection={"unanswered_customer_replies": 1, "ai_mode": 1, "ai_enabled": 1, "rep_sms_notified_at": 1}
        )
        conv_unanswered = (convo_update or {}).get("unanswered_customer_replies", 1) if convo_update else 1
        logger.info(f"[Webhook] Unanswered count for conv {conversation_id}: {conv_unanswered}")

        # ── Log contact_event so wins feed + activity feed reflect the reply ─────
        if user_id and contact_id and Body and Body.strip():
            try:
                cname = contact.get("name") or f"{contact.get('first_name','')} {contact.get('last_name','')}".strip() or from_phone
                await db.contact_events.insert_one({
                    "user_id":      user_id,
                    "contact_id":   contact_id,
                    "contact_name": cname,
                    "event_type":   "customer_reply",
                    "category":     "inbound",
                    "title":        f"{cname} replied via SMS",
                    "description":  Body[:200],
                    "channel":      "sms",
                    "timestamp":    datetime.utcnow(),
                })
                # Bust the home screen cache so wins feed refreshes immediately
                try:
                    from routers.home_intelligence import _home_cache
                    _home_cache.pop(user_id, None)
                except Exception:
                    pass
            except Exception as _ce:
                logger.warning(f"[Webhook] contact_event insert FAILED (wins feed affected): {_ce}")

        # ── SMS system notification to rep's personal cell ─────────────────────
        if rep_user and not is_stop:
            try:
                notif_prefs        = rep_user.get("notification_settings", {})
                sms_active_enabled = notif_prefs.get("sms_active_conversation", True)
                throttle_minutes   = int(notif_prefs.get("sms_active_throttle_minutes", 30))
                rep_personal_phone = normalize_phone((rep_user.get("phone") or "").strip())
                rep_twilio_number  = (rep_user.get("twilio_number") or rep_user.get("mvpline_number") or "").strip()

                if not rep_personal_phone:
                    logger.warning(f"[Webhook] SMS skipped — rep {rep_user.get('name','?')} has no personal phone set in profile")
                elif not rep_twilio_number:
                    logger.warning(f"[Webhook] SMS skipped — rep {rep_user.get('name','?')} has no Twilio number assigned")
                elif sms_active_enabled:
                    rep_cell = normalize_phone(rep_personal_phone)
                    if rep_cell == normalize_phone(from_phone):
                        logger.debug(f"[Webhook] Active SMS skipped — rep texted their own number")
                    else:
                        app_url   = os.environ.get("PUBLIC_FACING_URL", os.environ.get("APP_URL", "https://app.imonsocial.com"))
                        conv_link = f"imos://thread/{conversation_id}"   # Deep link opens iOS app directly
                        conv_link_web = f"{app_url}/thread/{conversation_id}"  # Web fallback
                        contact_display = contact.get("first_name") or contact.get("name") or from_phone[-4:]

                        # Use convo_update for throttle check (has the freshest rep_sms_notified_at)
                        fresh_conv    = convo_update or {}
                        last_notified = fresh_conv.get("rep_sms_notified_at") or conversation.get("rep_sms_notified_at")
                        throttled = (
                            isinstance(last_notified, datetime) and
                            (datetime.utcnow() - last_notified).total_seconds() < throttle_minutes * 60
                        )

                        if throttled:
                            logger.debug(f"[Webhook] Active SMS throttled for {conversation_id} ({throttle_minutes}m window)")
                        else:
                            tw_sid   = os.environ.get("TWILIO_ACCOUNT_SID", "")
                            tw_token = os.environ.get("TWILIO_AUTH_TOKEN", "")
                            if not tw_sid or not tw_token:
                                logger.warning("[Webhook] Active SMS skipped — TWILIO_ACCOUNT_SID or TWILIO_AUTH_TOKEN not set")
                            else:
                                preview_text = (Body or "").strip()[:60]
                                notif_msg = (
                                    f"I'm On Social: {contact_display} replied to you.\n"
                                    f'"{preview_text}{"..." if len((Body or "")) > 60 else ""}"\n\n'
                                    f"Open conversation:\n{conv_link}"
                                )
                                async def _send_active_sms(to=rep_cell, frm=rep_twilio_number, body=notif_msg, sid=tw_sid, tok=tw_token, conv_id=conversation_id):
                                    try:
                                        from twilio.rest import Client as _TC
                                        _TC(sid, tok).messages.create(to=to, from_=frm, body=body)
                                        await db.conversations.update_one(
                                            {"_id": ObjectId(conv_id)},
                                            {"$set": {"rep_sms_notified_at": datetime.utcnow()}}
                                        )
                                        logger.info(f"[Webhook] Active-conversation SMS sent to {to}")
                                    except Exception as _e:
                                        logger.warning(f"[Webhook] Active-conversation SMS FAILED to {to}: {_e}")
                                asyncio.create_task(_send_active_sms())
                                # Push notification
                                try:
                                    from routers.push_notifications import send_push_to_user
                                    asyncio.create_task(send_push_to_user(
                                        user_id or rep_user_id or "",
                                        f"{contact_display} replied",
                                        (Body or "").strip()[:100],
                                        f"{app_url}/thread/{conversation_id}",
                                        "chatbubble"
                                    ))
                                except Exception:
                                    pass
            except Exception as sms_notif_err:
                logger.warning(f"[Webhook] Rep SMS notification error: {sms_notif_err}")

        # ── AUTO-ENROLL: new contacts OR existing with no active enrollment ──────
        if rep_user_id and not is_stop:
            try:
                rep = await db.users.find_one({"_id": ObjectId(rep_user_id)}, {"default_campaign_id": 1, "name": 1})
                default_camp_id = (rep or {}).get("default_campaign_id")
                if default_camp_id:
                    campaign = await db.campaigns.find_one({"_id": ObjectId(default_camp_id), "active": True})
                    if campaign:
                        # Check not already enrolled
                        existing = await db.campaign_enrollments.find_one({
                            "contact_id": contact_id,
                            "campaign_id": default_camp_id,
                            "status": {"$in": ["active", "paused"]},
                        })
                        if not existing:
                            rep_first = ((rep or {}).get("name") or "").split()[0] or "your rep"
                            first_name = contact.get("first_name") or "there"
                            # Personalize first step message
                            sequences = campaign.get("sequences") or []
                            first_msg = ""
                            if sequences:
                                first_msg = (sequences[0].get("message") or "")
                                first_msg = first_msg.replace("{{firstName}}", first_name).replace("{{salespersonName}}", rep_first)

                            enrollment = {
                                "campaign_id":   default_camp_id,
                                "contact_id":    contact_id,
                                "user_id":       rep_user_id,
                                "contact_phone": from_phone,
                                "contact_name":  contact.get("name",""),
                                "status":        "active",   # Start active — paused when we process the reply
                                "current_step":  1,
                                "reply_count":   1,
                                "last_reply_at": datetime.utcnow(),
                                "enrolled_at":   datetime.utcnow(),
                                "next_send_at":  datetime.utcnow(),
                                "messages_sent": 0,
                                "ai_assist_mode": campaign.get("ai_assist_mode", "off"),
                            }
                            enroll_result = await db.campaign_enrollments.insert_one(enrollment)
                            logger.info(f"[Webhook] Auto-enrolled {contact_id} in campaign {default_camp_id}")

                            # If campaign has AI mode and a first message, queue it
                            ai_mode = campaign.get("ai_assist_mode", "off")
                            if ai_mode not in ("off", None):
                                try:
                                    from routers.ai_reply import queue_ai_reply
                                    asyncio.create_task(queue_ai_reply(
                                        contact_id=contact_id,
                                        conversation_id=conversation_id,
                                        enrollment_id=str(enroll_result.inserted_id),
                                        campaign_id=default_camp_id,
                                        assigned_user_id=rep_user_id,
                                        incoming_message=Body,
                                        ai_assist_mode=ai_mode,
                                        escalation_threshold=int(campaign.get("escalation_threshold", 3)),
                                        escalation_timeout_minutes=int(campaign.get("escalation_timeout_minutes", 15)),
                                        reply_count=1,
                                    ))
                                    logger.info(f"[Webhook] AI reply queued for new inbound from {from_phone}")
                                except Exception as qe:
                                    logger.error(f"[Webhook] AI queue error: {qe}")
            except Exception as ae:
                logger.error(f"[Webhook] Auto-enroll error: {ae}")
        body_upper = Body.strip().upper()
        is_stop   = body_upper in ("STOP", "STOPALL", "UNSUBSCRIBE", "CANCEL", "END", "QUIT")
        is_unstop = body_upper in ("UNSTOP", "START", "SUBSCRIBE")

        if is_stop:
            await db.contacts.update_one(
                {"_id": contact["_id"]},
                {"$set": {"opted_out": True, "opted_out_at": datetime.utcnow(), "sms_consent_status": "opted_out"}}
            )
            await db.campaign_enrollments.update_many(
                {"contact_id": contact_id, "status": "active"},
                {"$set": {"status": "opted_out", "paused_reason": "contact_opted_out"}}
            )
            await db.ai_reply_queue.update_many(
                {"contact_id": contact_id, "status": "pending"},
                {"$set": {"status": "cancelled", "cancel_reason": "contact_opted_out"}}
            )
            logger.info(f"[Webhook] {from_phone} opted out (STOP)")
            return Response(
                content='<?xml version="1.0" encoding="UTF-8"?><Response><Message>You have been unsubscribed. Reply START to re-subscribe.</Message></Response>',
                media_type="application/xml"
            )

        if is_unstop:
            await db.contacts.update_one(
                {"_id": contact["_id"]},
                {"$set": {"opted_out": False, "opted_out_at": None, "sms_consent_status": "opted_in"}}
            )
            if user_id:
                cname = contact.get("first_name") or "Customer"
                await db.notifications.insert_one({
                    "user_id": user_id, "type": "contact_resubscribed",
                    "title": f"{cname} re-subscribed", "message": f"{from_phone} replied START.",
                    "contact_id": contact_id, "read": False, "dismissed": False, "created_at": datetime.utcnow(),
                })
            return Response(
                content='<?xml version="1.0" encoding="UTF-8"?><Response><Message>You are re-subscribed. Reply STOP to unsubscribe.</Message></Response>',
                media_type="application/xml"
            )

        # ── Pause campaign enrollments + trigger AI reply ─────────────────────
        # Check conversation's ai_mode FIRST — rep's explicit override wins.
        # If the rep turned AI off for this conversation, never queue AI regardless of campaign.
        conv_ai_off = (
            conversation.get("ai_enabled") is False or
            conversation.get("ai_mode") in ("off", None, "")
        )

        active_enrollments = await db.campaign_enrollments.find({
            "contact_id": contact_id, "status": {"$in": ["active", "paused"]},
        }).to_list(10)

        # Track whether escalation already fired for this conversation
        max_reply_count = 0

        for enrollment in active_enrollments:
            campaign = None
            if enrollment.get("campaign_id"):
                try:
                    campaign = await db.campaigns.find_one({"_id": ObjectId(enrollment["campaign_id"])})
                except Exception:
                    pass

            new_reply_count = (enrollment.get("reply_count") or 0) + 1
            max_reply_count = max(max_reply_count, new_reply_count)
            await db.campaign_enrollments.update_one(
                {"_id": enrollment["_id"]},
                {"$set": {
                    "reply_count": new_reply_count, "last_reply_at": datetime.utcnow(),
                    "status": "paused", "paused_reason": "customer_replied",
                }}
            )

            # Use campaign's ai_assist_mode, fall back to enrollment's stored mode
            # (campaign may have been deleted — enrollment still knows its mode)
            # CRITICAL: Skip if the rep explicitly turned AI off on this conversation
            if conv_ai_off:
                ai_mode = "off"
            else:
                ai_mode = (campaign or {}).get("ai_assist_mode") or enrollment.get("ai_assist_mode") or "off"
            if ai_mode not in ("off", None):
                # Fire-and-forget — don't block the webhook waiting for GPT
                # The webhook must return to Twilio quickly to avoid retries
                async def _fire_ai_reply(enroll=enrollment, camp=campaign, rc=new_reply_count):
                    try:
                        from routers.ai_reply import queue_ai_reply
                        await queue_ai_reply(
                            contact_id=contact_id,
                            conversation_id=conversation_id,
                            enrollment_id=str(enroll["_id"]),
                            campaign_id=enroll.get("campaign_id", ""),
                            assigned_user_id=user_id or enroll.get("user_id", ""),
                            incoming_message=Body,
                            ai_assist_mode=ai_mode,
                            escalation_threshold=int((camp or {}).get("escalation_threshold", 2)),
                            escalation_timeout_minutes=int((camp or {}).get("escalation_timeout_minutes", 15)),
                            escalation_manager_id=(camp or {}).get("escalation_manager_id"),
                            reply_count=rc,
                        )
                    except Exception as bg_err:
                        logger.error(f"[Webhook] Background AI reply failed: {bg_err}")
                asyncio.create_task(_fire_ai_reply())

        # ── CONVERSATION-LEVEL AI: definitive override ────────────────────────────
        # If the rep set this conversation to Auto Reply, queue AI regardless of
        # campaign enrollment state. This is what users actually expect when they
        # toggle "Auto Reply" in Conversation Settings.
        enrollment_ai_queued = any(
            ((campaign or {}).get("ai_assist_mode") or e.get("ai_assist_mode") or "off") not in ("off", None)
            for e in active_enrollments
            for campaign in [None]  # campaign already fetched above, use enrollment fallback
        ) if active_enrollments else False

        if not conv_ai_off and not enrollment_ai_queued and not is_stop:
            conv_ai_mode    = conversation.get("ai_mode") or ""
            conv_ai_enabled = conversation.get("ai_enabled", False)
            if conv_ai_enabled and conv_ai_mode in ("auto_reply", "draft_only", "auto_with_approval"):
                logger.info(f"[Webhook] Conversation-level AI ({conv_ai_mode}) queuing reply for {contact_id}")
                async def _fire_conv_ai(mode=conv_ai_mode):
                    try:
                        from routers.ai_reply import queue_ai_reply
                        await queue_ai_reply(
                            contact_id=contact_id,
                            conversation_id=conversation_id,
                            enrollment_id="conversation_direct",
                            campaign_id="",
                            assigned_user_id=user_id or rep_user_id or "",
                            incoming_message=Body,
                            ai_assist_mode=mode,
                            escalation_threshold=3,
                            escalation_timeout_minutes=15,
                            reply_count=1,
                        )
                    except Exception as ce:
                        logger.error(f"[Webhook] Conversation AI reply failed: {ce}")
                asyncio.create_task(_fire_conv_ai())

        # ── "You're Needed" escalation ─────────────────────────────────────────
        # Uses BOTH enrollment count AND conversation-level unanswered count.
        # This fires for everyone — even contacts with no campaign enrollment.
        urn_threshold = 2  # Default — must be defined before the if block
        if not is_stop and user_id and rep_user:
            notif_prefs_esc = rep_user.get("notification_settings", {})
            configured_threshold = int(notif_prefs_esc.get("you_are_needed_threshold", 2))
            # If rep has personally replied before, drop threshold to 1
            # (they've been involved — notify immediately on next customer reply)
            rep_engaged = conversation.get("rep_engaged", False)
            urn_threshold = 1 if rep_engaged else configured_threshold

        effective_reply_count = max(max_reply_count, conv_unanswered)

        if effective_reply_count >= urn_threshold and not is_stop and user_id:
            try:
                cname_esc = contact.get("name") or f"{contact.get('first_name','')} {contact.get('last_name','')}".strip() or from_phone
                # If the stored name is a generic auto-generated "Lead (XXXX)", try to find
                # a real named contact that matches by phone number digits
                if cname_esc.startswith("Lead (") or not cname_esc or cname_esc == from_phone:
                    phone_tail = from_phone[-7:].lstrip("+0")
                    better = await db.contacts.find_one({
                        "user_id": user_id,
                        "phone": {"$regex": phone_tail[-7:]},
                        "name": {"$exists": True, "$not": {"$regex": "^Lead \\("}},
                    })
                    if not better:
                        better = await db.contacts.find_one({
                            "user_id": user_id,
                            "$or": [
                                {"phone": {"$regex": phone_tail[-4:]}},
                                {"mobile": {"$regex": phone_tail[-4:]}},
                            ],
                            "name": {"$exists": True, "$not": {"$regex": "^Lead \\("}},
                        })
                    if better:
                        cname_esc = better.get("name") or f"{better.get('first_name','')} {better.get('last_name','')}".strip() or cname_esc
                # Mark conversation as needing rep attention.
                # Use conv_unanswered (current unanswered count since rep's last reply)
                # NOT max_reply_count (lifetime campaign total — never resets).
                await db.conversations.update_one(
                    {"_id": ObjectId(conversation_id)},
                    {"$set": {
                        "needs_assistance":          True,
                        "unanswered_customer_replies": conv_unanswered,
                        "you_are_needed_at":         datetime.utcnow(),
                    }}
                )
                # Bust home cache so urgency shows immediately
                try:
                    from routers.home_intelligence import _home_cache
                    _home_cache.pop(user_id, None)
                except Exception:
                    pass
                # Create high-priority "You're Needed" notification
                await db.notifications.insert_one({
                    "user_id":         user_id,
                    "type":            "you_are_needed",
                    "priority":        "urgent",
                    "title":           f"{cname_esc} needs you — {effective_reply_count} messages waiting",
                    "message":         f"You have {effective_reply_count} unanswered messages from {cname_esc}. The AI has been helping but your personal touch is needed.",
                    "contact_id":      contact_id,
                    "conversation_id": conversation_id,
                    "reply_count":     max_reply_count,
                    "read":            False,
                    "dismissed":       False,
                    "created_at":      datetime.utcnow(),
                })
                logger.info(f"[Webhook] 'You Are Needed' escalation for {contact_id} ({max_reply_count} replies)")

                # Always push the rep — regardless of SMS/phone settings
                try:
                    from routers.push_notifications import send_push_to_user
                    asyncio.create_task(send_push_to_user(
                        user_id,
                        f"You're Needed — {cname_esc}",
                        f"{effective_reply_count} messages without a reply. Jessi needs you.",
                        f"/thread/{conversation_id}",
                        "alert-circle",
                    ))
                except Exception:
                    pass

                # Send URGENT SMS to rep's personal cell — fire-and-forget, never block webhook
                try:
                    notif_prefs2   = (rep_user or {}).get("notification_settings", {}) if rep_user else {}
                    sms_urn_enabled = notif_prefs2.get("sms_you_are_needed", True)
                    rep_personal_phone = normalize_phone((rep_user.get("phone") or "").strip()) if rep_user else ""
                    rep_twilio_number  = (rep_user.get("twilio_number") or rep_user.get("mvpline_number") or "").strip() if rep_user else ""
                    if sms_urn_enabled and rep_personal_phone and rep_twilio_number:
                        tw_sid2   = os.environ.get("TWILIO_ACCOUNT_SID", "")
                        tw_token2 = os.environ.get("TWILIO_AUTH_TOKEN", "")
                        if tw_sid2 and tw_token2:
                            app_url2  = os.environ.get("PUBLIC_FACING_URL", os.environ.get("APP_URL", "https://app.imonsocial.com"))
                            deep_link2 = f"imos://thread/{conversation_id}"
                            web_link2  = f"{app_url2}/thread/{conversation_id}"
                            from services.twilio_service import normalize_phone as _np2
                            urgent_to = _np2(rep_personal_phone)
                            urgent_frm = rep_twilio_number
                            urgent_body = (
                                f"⚠️ I'm On Social: YOU'RE NEEDED\n"
                                f"{cname_esc} has texted {effective_reply_count} times without a reply.\n\n"
                                f"Open app: {deep_link2}\n"
                                f"Or web: {web_link2}"
                            )
                            async def _send_urgent_sms(to=urgent_to, frm=urgent_frm, body=urgent_body, sid=tw_sid2, tok=tw_token2):
                                try:
                                    from twilio.rest import Client as _TC2
                                    _TC2(sid, tok).messages.create(to=to, from_=frm, body=body)
                                    logger.info(f"[Webhook] Sent YOU'RE NEEDED SMS to {to}")
                                except Exception as _ue:
                                    logger.warning(f"[Webhook] Urgent SMS failed: {_ue}")
                            asyncio.create_task(_send_urgent_sms())
                except Exception as urg_err:
                    logger.warning(f"[Webhook] Urgent rep SMS setup failed: {urg_err}")
            except Exception as esc_err:
                logger.warning(f"[Webhook] Escalation notification failed: {esc_err}")

        # ── Notify assigned rep ───────────────────────────────────────────────
        if user_id:
            try:
                cname = contact.get("name") or f"{contact.get('first_name','')} {contact.get('last_name','')}".strip() or from_phone
                notif_type  = "you_are_needed" if max_reply_count >= 2 else "customer_reply"
                notif_title = (f"{cname} needs you — {max_reply_count} unanswered" if max_reply_count >= 2
                               else f"{cname} replied")
                await db.notifications.insert_one({
                    "user_id": user_id, "type": notif_type,
                    "title": notif_title,
                    "message": Body[:200],
                    "contact_id": contact_id, "conversation_id": conversation_id,
                    "campaign_paused": len(active_enrollments) > 0,
                    "priority": "urgent" if max_reply_count >= 2 else "normal",
                    "read": False, "dismissed": False, "created_at": datetime.utcnow(),
                })
            except Exception:
                pass

        return Response(
            content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
            media_type="application/xml"
        )

    except Exception as e:
        logger.error(f"Error processing incoming message: {str(e)}")
        return Response(
            content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
            media_type="application/xml"
        )


@router.post("/status")
async def message_status_callback(
    MessageSid: str = Form(...),
    MessageStatus: str = Form(...),
    To: str = Form(default=""),
    From: str = Form(default=""),
    ErrorCode: Optional[str] = Form(default=None),
    ErrorMessage: Optional[str] = Form(default=None),
):
    """
    Webhook for message delivery status updates from Twilio.
    
    Status values: queued, sent, delivered, undelivered, failed
    """
    db = get_db()
    
    logger.info(f"Status update for {MessageSid}: {MessageStatus}")
    
    try:
        # Update message status in database
        update_data = {
            "twilio_status": MessageStatus,
            "status_updated_at": datetime.utcnow()
        }
        
        if ErrorCode:
            update_data["error_code"] = ErrorCode
            update_data["error_message"] = ErrorMessage
            logger.warning(f"Message {MessageSid} failed: {ErrorCode} - {ErrorMessage}")
        
        # Map Twilio status to our status
        status_map = {
            "queued": "sending",
            "sent": "sent",
            "delivered": "delivered",
            "undelivered": "failed",
            "failed": "failed"
        }
        
        if MessageStatus in status_map:
            update_data["status"] = status_map[MessageStatus]
        
        result = await db.messages.update_one(
            {"twilio_sid": MessageSid},
            {"$set": update_data}
        )
        
        if result.modified_count > 0:
            logger.info(f"Updated message {MessageSid} status to {MessageStatus}")
        
    except Exception as e:
        logger.error(f"Error updating message status: {str(e)}")
    
    return Response(content="OK", media_type="text/plain")


@router.get("/test")
async def test_webhook():
    """Test endpoint to verify webhook is accessible"""
    return {
        "status": "ok",
        "message": "Twilio webhook endpoint is active",
        "endpoints": {
            "incoming_sms": "/api/webhooks/twilio/incoming",
            "status_callback": "/api/webhooks/twilio/status"
        }
    }



@router.post("/call")
async def initiate_outbound_call(request: Request):
    """
    Click-to-Call: Rep taps Call in the app → their personal cell rings first →
    when they answer, Twilio bridges them to the customer.
    Customer's caller ID shows the rep's dedicated Twilio number (not the rep's personal cell).
    
    Body: { rep_user_id, customer_phone, contact_id (optional), conversation_id (optional) }
    """
    import asyncio as _aio
    body = await request.json()
    rep_user_id    = body.get("rep_user_id", "")
    customer_phone = body.get("customer_phone", "")
    contact_id     = body.get("contact_id", "")
    conversation_id = body.get("conversation_id", "")  # thread to log the call in

    if not rep_user_id or not customer_phone:
        raise HTTPException(status_code=400, detail="rep_user_id and customer_phone required")

    db = get_db()
    rep = await db.users.find_one({"_id": ObjectId(rep_user_id)})
    if not rep:
        raise HTTPException(status_code=404, detail="Rep not found")

    rep_personal_phone = normalize_phone((rep.get("phone") or "").strip())
    rep_twilio_number  = normalize_phone((rep.get("twilio_number") or rep.get("mvpline_number") or "").strip())
    customer_phone_e164 = normalize_phone(customer_phone)

    if not rep_personal_phone:
        raise HTTPException(status_code=400, detail="Rep has no personal phone number set. Add it in your profile.")
    if not rep_twilio_number:
        raise HTTPException(status_code=400, detail="Rep has no dedicated Twilio number assigned.")
    if not customer_phone_e164:
        raise HTTPException(status_code=400, detail="Invalid customer phone number")

    tw_sid   = os.environ.get("TWILIO_ACCOUNT_SID", "")
    tw_token = os.environ.get("TWILIO_AUTH_TOKEN", "")
    if not tw_sid or not tw_token:
        raise HTTPException(status_code=500, detail="Twilio credentials not configured")

    app_url  = os.environ.get("PUBLIC_FACING_URL", os.environ.get("APP_URL", "https://app.imonsocial.com"))
    rep_name = (rep.get("name") or "").split()[0] or "your rep"

    # Store call context in DB — retrieved by CallSid when the bridge fires.
    # Also store conversation_id so we can add a call entry to the thread.
    pending_call_doc = {
        "customer_phone":    customer_phone_e164,
        "rep_twilio_number": rep_twilio_number,
        "rep_name":          rep_name,
        "rep_user_id":       rep_user_id,
        "contact_id":        contact_id or None,
        "conversation_id":   conversation_id or None,
        "created_at":        datetime.utcnow(),
    }

    try:
        from twilio.rest import Client as _TC
        client = _TC(tw_sid, tw_token)
        call = await _aio.to_thread(
            client.calls.create,
            to=rep_personal_phone,
            from_=rep_twilio_number,
            url=f"{app_url}/api/webhooks/twilio/call-bridge",
            status_callback=f"{app_url}/api/webhooks/twilio/call-status",
            status_callback_method="POST",
        )
        # Store with the real CallSid
        pending_call_doc["call_sid"] = call.sid
        await db.pending_calls.insert_one(pending_call_doc)

        logger.info(f"[Voice] Outbound call: rep={rep_personal_phone} → customer={customer_phone_e164} | SID={call.sid}")

        # Log call event in contact_events (Activity feed)
        try:
            contact = await db.contacts.find_one({"_id": ObjectId(contact_id)}) if contact_id else None
            contact_name = (contact or {}).get("name") or f"({customer_phone[-4:]})"
            await db.contact_events.insert_one({
                "user_id":       rep_user_id,
                "contact_id":    contact_id or None,
                "contact_name":  contact_name,
                "event_type":    "outbound_call",
                "category":      "call",
                "title":         f"Called {contact_name}",
                "description":   f"Outbound call to {customer_phone_e164} via {rep_twilio_number}",
                "channel":       "voice",
                "call_sid":      call.sid,
                "timestamp":     datetime.utcnow(),
            })
        except Exception:
            pass

        # Write a "Call Placed" entry to the inbox thread so the call is visible there too
        if conversation_id:
            try:
                await db.messages.insert_one({
                    "conversation_id": conversation_id,
                    "user_id":         rep_user_id,
                    "contact_id":      contact_id or None,
                    "sender":          "user",
                    "direction":       "outbound",
                    "channel":         "voice",
                    "type":            "call_log",
                    "content":         f"📱 Outbound call placed to {customer_phone_e164}",
                    "call_sid":        call.sid,
                    "call_status":     "placed",
                    "duration_s":      0,
                    "has_recording":   False,
                    "timestamp":       datetime.utcnow(),
                    "status":          "sent",
                })
                logger.info(f"[Voice] Call message added to thread {conversation_id}")
            except Exception as _me:
                logger.warning(f"[Voice] Failed to add call message to thread: {_me}")

        return {
            "success":  True,
            "call_sid": call.sid,
            "status":   call.status,
            "message":  f"Calling your phone ({rep_personal_phone[-4:]})... pick up to connect to {customer_phone_e164}",
        }
    except Exception as e:
        logger.error(f"[Voice] Outbound call failed: {e}")
        raise HTTPException(status_code=500, detail=f"Call failed: {str(e)}")


@router.get("/call-whisper")
@router.post("/call-whisper")
async def call_whisper(
    request: Request,
    From:  str = Form(default=""),
    To:    str = Form(default=""),
):
    """
    Played to the REP when they answer — before the customer is connected.
    Twilio sends the call's From/To in the POST body automatically.
    """
    db = get_db()
    caller_phone = normalize_phone(From) if From else ""

    # Try to find the contact's name
    display = "a customer"
    if caller_phone:
        try:
            contact = await db.contacts.find_one({
                "$or": [{"phone": caller_phone}, {"phone": caller_phone.lstrip("+")}]
            }, {"first_name": 1, "last_name": 1, "name": 1})
            if contact:
                full = f"{contact.get('first_name','')} {contact.get('last_name','')}".strip()
                if not full or full in ("Contact", "Unknown"):
                    full = contact.get("name", "") or ""
                if full and full not in ("Contact", "Unknown"):
                    display = full
                else:
                    display = f"a customer ending in {caller_phone[-4:]}"
            else:
                display = f"a customer ending in {caller_phone[-4:]}"
        except Exception:
            display = f"a customer ending in {caller_phone[-4:]}" if caller_phone else "a customer"

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say>I'm On Social. Incoming call from {display}.</Say>
</Response>"""
    return Response(content=twiml, media_type="application/xml")


@router.post("/recording-complete")
async def handle_recording_complete(
    request:           Request,
    RecordingUrl:      str = Form(default=""),
    RecordingSid:      str = Form(default=""),
    RecordingStatus:   str = Form(default=""),
    RecordingDuration: str = Form(default="0"),
    CallSid:           str = Form(default=""),
    TranscriptionText: str = Form(default=""),
    From:              str = Form(default=""),
    To:                str = Form(default=""),
):
    """
    Called by Twilio when a call recording is ready.
    1. Uses CallSid to look up who the call was between (from pending_calls or contact_events)
    2. Downloads the recording and transcribes with Whisper
    3. Extracts key info with GPT
    4. Saves to contact record (call_logs + notes)
    """
    import asyncio as _aio, os as _os

    # Only process completed recordings
    if RecordingStatus and RecordingStatus not in ("completed", ""):
        return Response(content="OK", media_type="text/plain")
    if not RecordingUrl:
        return Response(content="OK", media_type="text/plain")

    db = get_db()
    logger.info(f"[Voice] Recording ready: SID={RecordingSid} | CallSid={CallSid} | duration={RecordingDuration}s")

    # ── Resolve call context from CallSid ─────────────────────────────────────
    user_id    = None
    contact_id = None
    from_phone = normalize_phone(From) if From else ""
    direction  = "inbound"

    # Check pending_calls (outbound calls store context here)
    if CallSid:
        pending = await db.pending_calls.find_one({"call_sid": CallSid})
        if pending:
            user_id      = pending.get("user_id") or pending.get("rep_user_id")
            contact_id   = pending.get("contact_id")
            from_phone   = pending.get("customer_phone") or from_phone
            direction    = "outbound"

    # Check contact_events for inbound call that was logged
    if not user_id and CallSid:
        event = await db.contact_events.find_one({"call_sid": CallSid})
        if event:
            user_id    = event.get("user_id")
            contact_id = event.get("contact_id")
            direction  = event.get("category") or "inbound"

    # Resolve contact if we have a phone but no contact_id yet
    if not contact_id and from_phone:
        contact = await db.contacts.find_one({
            "$or": [{"phone": from_phone}, {"phone": from_phone.lstrip("+")}]
        })
        if contact:
            contact_id = str(contact["_id"])
            if not user_id:
                user_id = contact.get("user_id")

    # If still no user, find the rep who owns the To: number
    if not user_id and To:
        to_normalized = normalize_phone(To)
        rep = await db.users.find_one({
            "$or": [{"twilio_number": to_normalized}, {"mvpline_number": to_normalized}]
        })
        if rep:
            user_id = str(rep["_id"])

    # Final fallback: infer from_phone from From field if not set
    if not from_phone and From:
        from_phone = normalize_phone(From)

    # Resolve contact from phone if not found yet
    if not contact_id and from_phone:
        contact = await db.contacts.find_one({
            "$or": [{"phone": from_phone}, {"phone": from_phone.lstrip("+")}]
        })
        if contact:
            contact_id = str(contact["_id"])
            if not user_id:
                user_id = contact.get("user_id")

    contact = await db.contacts.find_one({"_id": ObjectId(contact_id)}) if contact_id else None
    contact_name = (contact or {}).get("name") or f"Unknown ({(from_phone or '')[-4:]})"

    logger.info(f"[Voice] Processing recording for contact={contact_name} | user={user_id} | direction={direction}")

    # ── Transcribe + extract in background ────────────────────────────────────
    async def _transcribe_and_save():
        transcript = (TranscriptionText or "").strip()
        ai_summary = ""
        now        = datetime.utcnow()

        # Transcribe with Whisper if no Twilio transcript provided
        if not transcript and RecordingUrl:
            try:
                tw_sid   = _os.environ.get("TWILIO_ACCOUNT_SID", "")
                tw_token = _os.environ.get("TWILIO_AUTH_TOKEN", "")
                emergent_key = _os.environ.get("EMERGENT_LLM_KEY", "")

                if not tw_sid or not tw_token:
                    logger.warning("[Voice] Transcription skipped — Twilio credentials not set")
                    from utils.system_logger import syslog
                    await syslog.warning("voice_transcription", "Twilio credentials not set — cannot download recording")
                elif not emergent_key:
                    logger.warning("[Voice] Transcription skipped — EMERGENT_LLM_KEY not set")
                    from utils.system_logger import syslog
                    await syslog.warning("voice_transcription", "EMERGENT_LLM_KEY not set — Whisper unavailable")
                else:
                    import requests as _req, tempfile, uuid as _uuid
                    mp3_url = RecordingUrl if RecordingUrl.endswith(".mp3") else f"{RecordingUrl}.mp3"
                    logger.info(f"[Voice] Downloading recording from Twilio: {mp3_url[:60]}...")

                    # Use synchronous requests in a thread to avoid httpx async complexity
                    def _download():
                        r = _req.get(mp3_url, auth=(tw_sid, tw_token), timeout=30)
                        return r.status_code, r.content

                    status_code, content = await _aio.to_thread(_download)

                    if status_code == 200 and content:
                        tmp_path = f"/tmp/call_{_uuid.uuid4().hex}.mp3"
                        with open(tmp_path, "wb") as f:
                            f.write(content)
                        logger.info(f"[Voice] Downloaded {len(content)} bytes — transcribing with Whisper...")

                        try:
                            from emergentintegrations.llm.openai import OpenAISpeechToText
                            stt = OpenAISpeechToText(api_key=emergent_key)
                            # Must pass an opened binary file object — litellm rejects bare path strings
                            with open(tmp_path, "rb") as audio_file:
                                result = await _aio.wait_for(
                                    stt.transcribe(audio_file, language="en"),
                                    timeout=60.0
                                )
                            if hasattr(result, "text"):
                                transcript = result.text.strip()
                            elif isinstance(result, str):
                                transcript = result.strip()
                            elif isinstance(result, dict):
                                transcript = result.get("text", "").strip()
                            logger.info(f"[Voice] Whisper transcript ({len(transcript)} chars) for {contact_name}")
                        finally:
                            import os as _ost
                            try: _ost.remove(tmp_path)
                            except: pass
                    else:
                        logger.warning(f"[Voice] Recording download failed: HTTP {status_code} from {mp3_url[:60]}")
                        from utils.system_logger import syslog
                        await syslog.warning("voice_transcription", f"Recording download failed HTTP {status_code}", recording_url=mp3_url[:80], call_sid=CallSid)
            except Exception as transcribe_err:
                logger.warning(f"[Voice] Transcription failed: {transcribe_err}", exc_info=True)
                from utils.system_logger import syslog
                await syslog.error("voice_transcription", "Whisper transcription failed", error=transcribe_err, call_sid=CallSid, contact=contact_name)

        # Extract key info with GPT
        if transcript:
            try:
                from emergentintegrations.llm.chat import LlmChat, UserMessage
                import uuid as _uuid2
                chat = LlmChat(
                    api_key=_os.environ.get("EMERGENT_LLM_KEY", ""),
                    session_id=f"call-ai-{_uuid2.uuid4().hex[:12]}",
                    system_message=(
                        "You are a CRM assistant analyzing a sales call transcript.\n"
                        "Extract these if mentioned — be brief and use bullet points:\n"
                        "- What they're looking for (product, model, year, color)\n"
                        "- Budget or price range\n"
                        "- Timeline / urgency\n"
                        "- Objections or concerns\n"
                        "- Next steps or commitments\n"
                        "Max 120 words. Skip any category not mentioned."
                    ),
                ).with_model("openai", "gpt-5.2")
                resp = await _aio.wait_for(
                    chat.send_message(UserMessage(text=f"Transcript:\n{transcript}")),
                    timeout=15.0
                )
                ai_summary = (resp.strip() if isinstance(resp, str)
                              else resp.text.strip() if hasattr(resp, "text") else "").strip()
            except Exception as gpt_err:
                logger.warning(f"[Voice] GPT extraction failed: {gpt_err}")

        # ── Save everything ────────────────────────────────────────────────────
        dur = int(RecordingDuration or 0)

        # call_logs collection
        await db.call_logs.insert_one({
            "user_id":          user_id,
            "contact_id":       contact_id,
            "contact_name":     contact_name,
            "contact_phone":    from_phone,
            "call_sid":         CallSid,
            "recording_sid":    RecordingSid,
            "recording_url":    RecordingUrl,
            "duration_s":       dur,
            "transcript":       transcript,
            "ai_summary":       ai_summary,
            "direction":        direction,
            "timestamp":        now,
            "created_at":       now,
        })

        if contact_id:
            # Note on contact record
            note_body = f"{'📞' if direction == 'inbound' else '📱'} {'Inbound' if direction == 'inbound' else 'Outbound'} call — {dur}s"
            if transcript:
                note_body += f"\n\nTranscript:\n{transcript[:600]}{'...' if len(transcript) > 600 else ''}"
            if ai_summary:
                note_body += f"\n\nKey Info Extracted:\n{ai_summary}"

            await db.notes.insert_one({
                "user_id":       user_id,
                "contact_id":    contact_id,
                "type":          "call_log",
                "body":          note_body,
                "ai_summary":    ai_summary,
                "recording_url": RecordingUrl,
                "transcript":    transcript,
                "duration_s":    dur,
                "call_sid":      CallSid,
                "direction":     direction,
                "timestamp":     now,
                "created_at":    now,
            })

            # Contact event (shows in Activity feed)
            await db.contact_events.update_one(
                {"call_sid": CallSid, "event_type": {"$in": ["inbound_call", "outbound_call"]}},
                {"$set": {
                    "has_recording": True,
                    "ai_summary":    ai_summary,
                    "transcript":    transcript[:200] if transcript else "",
                    "duration_s":    dur,
                }},
            )

            # Update the thread message with recording + summary (so inbox shows the full call card)
            pending = await db.pending_calls.find_one({"call_sid": CallSid})
            conv_id_for_update = (pending or {}).get("conversation_id")
            if conv_id_for_update:
                duration_label = f"{dur // 60}m {dur % 60}s" if dur >= 60 else f"{dur}s"
                call_content = f"📱 Outbound call — {duration_label}"
                if ai_summary:
                    call_content += f"\n\n{ai_summary}"
                await db.messages.update_one(
                    {"call_sid": CallSid, "type": "call_log"},
                    {"$set": {
                        "content":       call_content,
                        "call_status":   "completed",
                        "duration_s":    dur,
                        "has_recording": True,
                        "recording_url": RecordingUrl,
                        "transcript":    transcript,
                        "ai_summary":    ai_summary,
                    }},
                    upsert=False,
                )
                logger.info(f"[Voice] Thread message updated with recording for conv {conv_id_for_update}")

        # Push notification to rep
        if user_id:
            notif_msg = ai_summary or (transcript[:100] if transcript else "Recording ready to review")
            await db.notifications.insert_one({
                "user_id":       user_id,
                "type":          "call_recorded",
                "priority":      "normal",
                "title":         f"Call summary ready — {contact_name}",
                "message":       notif_msg,
                "contact_id":    contact_id,
                "recording_url": RecordingUrl,
                "read":          False,
                "dismissed":     False,
                "created_at":    now,
            })

        logger.info(f"[Voice] Call log + AI summary saved for {contact_name} (transcript={len(transcript)} chars, summary={len(ai_summary)} chars)")

    _aio.create_task(_transcribe_and_save())
    return Response(content="OK", media_type="text/plain")


@router.post("/call-cancel")
async def cancel_call(request: Request):
    """Cancel an in-progress or ringing Twilio call (rep tapped Cancel in the app)."""
    import asyncio as _aio
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    call_sid = body.get("call_sid", "")
    if not call_sid:
        return {"success": False, "detail": "No call_sid provided"}
    try:
        tw_sid   = os.environ.get("TWILIO_ACCOUNT_SID", "")
        tw_token = os.environ.get("TWILIO_AUTH_TOKEN", "")
        if tw_sid and tw_token:
            from twilio.rest import Client as _TC
            await _aio.to_thread(
                _TC(tw_sid, tw_token).calls(call_sid).update,
                status="canceled"
            )
            logger.info(f"[Voice] Call {call_sid} canceled by rep")
    except Exception as e:
        logger.warning(f"[Voice] Cancel call failed: {e}")
    return {"success": True}


@router.post("/call-bridge")
@router.get("/call-bridge")
async def call_bridge_twiml(
    request: Request,
    CallSid: str = Form(default=""),
):
    """
    TwiML returned when the REP answers their personal phone.
    Looks up the call context from the pending_calls collection using CallSid.
    This is reliable — no URL param encoding issues.
    """
    db = get_db()

    # Twilio sends CallSid in the POST body when rep answers
    # Also check query params as fallback
    call_sid = CallSid or request.query_params.get("CallSid", "")
    logger.info(f"[Voice] call-bridge triggered | CallSid={call_sid}")

    pending = None
    if call_sid:
        pending = await db.pending_calls.find_one({"call_sid": call_sid})

    if not pending:
        logger.error(f"[Voice] call-bridge: no pending_call found for SID={call_sid}")
        return Response(
            content='<?xml version="1.0" encoding="UTF-8"?><Response><Say>Sorry, something went wrong connecting your call. Please try again.</Say></Response>',
            media_type="application/xml"
        )

    customer_phone  = pending.get("customer_phone", "")
    caller_number   = pending.get("rep_twilio_number", "")

    if not customer_phone:
        logger.error(f"[Voice] call-bridge: no customer_phone in pending_call {call_sid}")
        return Response(
            content='<?xml version="1.0" encoding="UTF-8"?><Response><Say>Configuration error. Please try again.</Say></Response>',
            media_type="application/xml"
        )

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say>Connecting your call now.</Say>
  <Dial callerId="{caller_number}" timeout="30"
        record="record-from-answer"
        recordingStatusCallback="{os.environ.get('PUBLIC_FACING_URL', os.environ.get('APP_URL', 'https://app.imonsocial.com'))}/api/webhooks/twilio/recording-complete"
        recordingStatusCallbackMethod="POST">
    <Number>{customer_phone}</Number>
  </Dial>
</Response>"""

    logger.info(f"[Voice] Bridging {caller_number} → {customer_phone}")
    return Response(content=twiml, media_type="application/xml")



@router.post("/call-status")
async def handle_call_status(
    request: Request,
    CallSid:    str = Form(default=""),
    CallStatus: str = Form(default=""),
    To:         str = Form(default=""),
    From:       str = Form(default=""),
    Duration:   str = Form(default="0"),
):
    """Updates call status in the DB (optional logging)."""
    logger.info(f"[Voice] Call status: {CallSid} → {CallStatus} | duration={Duration}s")
    if CallStatus in ("completed", "failed", "busy", "no-answer"):
        db = get_db()
        try:
            await db.contact_events.update_one(
                {"call_sid": CallSid},
                {"$set": {"call_status": CallStatus, "call_duration_s": int(Duration or 0)}}
            )
        except Exception:
            pass
    return Response(content="OK", media_type="text/plain")




@router.post("/voice")
async def handle_inbound_voice(
    request: Request,
    To:     str = Form(default=""),
    From:   str = Form(default=""),
    CallSid: str = Form(default=""),
):
    """
    Handles inbound voice calls to a rep's Twilio number.
    - Looks up which rep owns the called number
    - Dials the rep's personal cell phone
    - If rep doesn't answer, records a voicemail
    """
    db   = get_db()
    to_phone   = normalize_phone(To)
    from_phone = normalize_phone(From)

    logger.info(f"[Voice] Inbound call from {from_phone} to {to_phone} | SID={CallSid}")

    # Find the rep who owns this Twilio number — same strict lookup as SMS
    rep_user = await db.users.find_one({
        "$or": [{"twilio_number": to_phone}, {"mvpline_number": to_phone}],
        "status": {"$ne": "deactivated"},   # Same rule as SMS — only exclude hard-deactivated
    })
    if not rep_user:
        rep_user = await db.users.find_one({"role": {"$in": ["super_admin", "org_admin"]}})
        if rep_user:
            logger.warning(f"[Voice] No rep found for {to_phone} — falling back to super_admin ({rep_user.get('name')})")

    rep_personal_phone = normalize_phone((rep_user.get("phone") or "").strip()) if rep_user else ""
    rep_name           = (rep_user.get("name") or "I'm On Social").split()[0] if rep_user else "I'm On Social"
    app_url            = os.environ.get("PUBLIC_FACING_URL", os.environ.get("APP_URL", "https://app.imonsocial.com"))

    # Log the call — strict rep namespace (same as SMS)
    is_bridge_back_call = False
    try:
        rep_with_this_number = await db.users.find_one({
            "$or": [{"twilio_number": from_phone}, {"mvpline_number": from_phone}]
        }, {"_id": 1})
        if rep_with_this_number:
            is_bridge_back_call = True
            logger.info(f"[Voice] Skipping inbound_call log — from_phone {from_phone} is a rep's Twilio number (bridge-back)")
    except Exception:
        pass

    if rep_user and not is_bridge_back_call:
        try:
            rep_user_id = str(rep_user["_id"])
            # Strict namespace: only look for contact in THIS rep's contacts
            contact = await db.contacts.find_one({
                "user_id": rep_user_id,
                "$or": [{"phone": from_phone}, {"phone": from_phone.lstrip("+")}]
            })
            if not contact:
                contact = None
            contact_id   = str(contact["_id"]) if contact else None
            contact_name = (contact or {}).get("name") or f"({from_phone[-4:]})"
            await db.contact_events.insert_one({
                "user_id":      rep_user_id,
                "contact_id":   contact_id,
                "contact_name": contact_name,
                "event_type":   "inbound_call",
                "category":     "call",
                "title":        f"{contact_name} called",
                "description":  f"Inbound call from {from_phone} to {to_phone}",
                "channel":      "voice",
                "rep_phone":    to_phone,       # The Twilio number that received the call
                "call_sid":     CallSid,
                "timestamp":    datetime.utcnow(),
            })
            # Find conversation using the strict key: (rep_phone, contact_phone)
            conv = await db.conversations.find_one({
                "rep_phone":     to_phone,
                "contact_phone": from_phone,
            })
            if conv:
                await db.conversations.update_one(
                    {"_id": conv["_id"]},
                    {"$set": {"last_call_at": datetime.utcnow()}}
                )
        except Exception as _ce:
            logger.warning(f"[Voice] Event log error: {_ce}")

    # Build TwiML — dial the rep's personal cell, plain and simple
    app_url = os.environ.get("PUBLIC_FACING_URL", os.environ.get("APP_URL", "https://app.imonsocial.com"))

    if rep_personal_phone:
        # Rep whisper: Twilio calls the whisper URL when rep answers
        # Use a simple inline URL — no complex query params
        import urllib.parse as _up
        whisper_url  = f"{app_url}/api/webhooks/twilio/call-whisper"
        fallback_url = f"{app_url}/api/webhooks/twilio/voice-fallback"
        recording_cb = f"{app_url}/api/webhooks/twilio/recording-complete"

        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Dial callerId="{to_phone}" timeout="25"
        record="record-from-answer"
        recordingStatusCallback="{recording_cb}"
        recordingStatusCallbackMethod="POST"
        action="{fallback_url}">
    <Number url="{whisper_url}" method="POST">{rep_personal_phone}</Number>
  </Dial>
</Response>"""
    else:
        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say>Hi, you've reached {rep_name}. Please leave a message after the tone.</Say>
  <Record maxLength="120" transcribe="true"
          transcribeCallback="{app_url}/api/webhooks/twilio/recording-complete"
          recordingStatusCallback="{app_url}/api/webhooks/twilio/recording-complete"
          recordingStatusCallbackMethod="POST" />
  <Say>Thank you. Goodbye!</Say>
</Response>"""

    return Response(content=twiml, media_type="application/xml")


@router.post("/voice-fallback")
async def handle_voice_fallback(
    request: Request,
    DialCallStatus: str = Form(default=""),
    To:  str = Form(default=""),
    From: str = Form(default=""),
    CallSid: str = Form(default=""),
):
    """
    Called by Twilio after the <Dial> completes.
    If the rep didn't answer, record a voicemail.
    """
    from_phone = normalize_phone(From)
    db = get_db()

    rep_user = await db.users.find_one({
        "$or": [{"twilio_number": normalize_phone(To)}, {"mvpline_number": normalize_phone(To)}],
    })
    rep_name = (rep_user.get("name") or "the team").split()[0] if rep_user else "the team"
    app_url  = os.environ.get("PUBLIC_FACING_URL", os.environ.get("APP_URL", "https://app.imonsocial.com"))

    logger.info(f"[Voice] Dial status={DialCallStatus} from {from_phone}")

    if DialCallStatus in ("no-answer", "busy", "failed", "canceled"):
        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say>Sorry, {rep_name} is unavailable right now. Leave a message after the tone and we'll get back to you quickly.</Say>
  <Record maxLength="120" transcribe="true" transcribeCallback="{app_url}/api/webhooks/twilio/voicemail-transcription" />
  <Say>Thank you, talk soon!</Say>
</Response>"""
    else:
        twiml = """<?xml version="1.0" encoding="UTF-8"?><Response></Response>"""

    return Response(content=twiml, media_type="application/xml")


@router.post("/voicemail-transcription")
async def handle_voicemail_transcription(
    request: Request,
    TranscriptionText: str = Form(default=""),
    RecordingUrl:      str = Form(default=""),
    CallSid:           str = Form(default=""),
    From:              str = Form(default=""),
    To:                str = Form(default=""),
):
    """Stores voicemail transcription and notifies the rep."""
    db         = get_db()
    from_phone = normalize_phone(From)
    to_phone   = normalize_phone(To)

    rep_user = await db.users.find_one({
        "$or": [{"twilio_number": to_phone}, {"mvpline_number": to_phone}],
    })
    if not rep_user:
        rep_user = await db.users.find_one({"role": "super_admin"})

    contact = await db.contacts.find_one({
        "$or": [{"phone": from_phone}, {"phone": from_phone.lstrip("+")}]
    })
    contact_name = (contact or {}).get("name") or f"Unknown ({from_phone[-4:]})"
    user_id      = str(rep_user["_id"]) if rep_user else None

    # Save voicemail as a message
    await db.messages.insert_one({
        "user_id":       user_id,
        "contact_id":    str(contact["_id"]) if contact else None,
        "contact_phone": from_phone,
        "content":       TranscriptionText or "(Voicemail — no transcription)",
        "recording_url": RecordingUrl,
        "sender":        "contact",
        "direction":     "inbound",
        "channel":       "voicemail",
        "call_sid":      CallSid,
        "timestamp":     datetime.utcnow(),
    })

    # Notify rep
    if user_id:
        await db.notifications.insert_one({
            "user_id":     user_id,
            "type":        "voicemail",
            "title":       f"Voicemail from {contact_name}",
            "message":     TranscriptionText[:200] if TranscriptionText else "New voicemail",
            "contact_id":  str(contact["_id"]) if contact else None,
            "recording_url": RecordingUrl,
            "read":        False,
            "dismissed":   False,
            "created_at":  datetime.utcnow(),
        })
        logger.info(f"[Voice] Voicemail saved from {from_phone} | transcription: {TranscriptionText[:50]}")

    return Response(content="OK", media_type="text/plain")



def normalize_phone(phone: str) -> str:
    """Normalize phone number to E.164 format"""
    if not phone:
        return phone
    
    # Remove all non-digit characters except +
    cleaned = ''.join(c for c in phone if c.isdigit() or c == '+')
    
    # Add + if not present
    if not cleaned.startswith('+'):
        if len(cleaned) == 10:
            cleaned = '+1' + cleaned
        elif len(cleaned) == 11 and cleaned.startswith('1'):
            cleaned = '+' + cleaned
        else:
            cleaned = '+' + cleaned
    
    return cleaned
