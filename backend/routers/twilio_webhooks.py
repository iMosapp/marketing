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
    if MessageSid:
        already = await db.messages.find_one({"twilio_sid": MessageSid})
        if already:
            logger.warning(f"[Webhook] Duplicate MessageSid {MessageSid} — ignoring Twilio retry")
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
        rep_user = await db.users.find_one({
            "$or": [{"twilio_number": to_phone}, {"mvpline_number": to_phone}],
            "is_active": {"$ne": False},
        })
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

        # ── Step 2: Find or create contact for the sender ────────────────────
        alt_phone = from_phone.replace("+1", "") if from_phone.startswith("+1") else "+1" + from_phone.lstrip("+")
        contact = await db.contacts.find_one({
            "$or": [
                {"phone": from_phone},
                {"phone": alt_phone},
                {"phone": from_phone.lstrip("+")},
            ]
        })

        is_new_contact = False
        if not contact:
            is_new_contact = True
            contact = {
                "phone":       from_phone,
                "first_name":  "New",
                "last_name":   "Lead",
                "name":        f"Lead ({from_phone[-4:]})",
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
            logger.info(f"[Webhook] New contact created for {from_phone}, assigned to {rep_user_id}")
        elif not contact.get("user_id") and rep_user_id:
            # Assign orphan contact to the rep
            await db.contacts.update_one(
                {"_id": contact["_id"]},
                {"$set": {"user_id": rep_user_id}}
            )
            contact["user_id"] = rep_user_id

        contact_id = str(contact["_id"])
        user_id    = contact.get("user_id") or rep_user_id
        is_stop    = False   # will be set properly after message is saved
        
        # Find or create conversation
        conversation = await db.conversations.find_one({
            "contact_id": contact_id
        })
        
        if not conversation:
            # Create new conversation
            conversation = {
                "user_id": user_id,
                "contact_id": contact_id,
                "contact_phone": from_phone,
                "contact_name": contact.get("name") or f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip(),
                "status": "active",
                "ai_enabled": False,
                "ai_mode": "suggest",
                "unread": True,
                "unread_count": 1,
                "needs_assistance": False,
                "created_at": datetime.utcnow(),
                "last_message_at": datetime.utcnow()
            }
            result = await db.conversations.insert_one(conversation)
            conversation["_id"] = result.inserted_id
            logger.info(f"Created new conversation for contact {contact_id}")
        else:
            # Update existing conversation
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

        # ── Increment conversation-level unanswered count ──────────────────────
        # This is the reliable source for YOU'RE NEEDED — works even when there
        # is no campaign enrollment (conversation-level AI mode).
        convo_update = await db.conversations.find_one_and_update(
            {"_id": ObjectId(conversation_id)},
            {"$inc": {"unanswered_customer_replies": 1}},
            return_document=True,
            projection={"unanswered_customer_replies": 1, "ai_mode": 1, "ai_enabled": 1, "rep_sms_notified_at": 1}
        )
        conv_unanswered = (convo_update or {}).get("unanswered_customer_replies", 1) if convo_update else 1

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
                logger.debug(f"[Webhook] contact_event insert skipped: {_ce}")

        # ── SMS system notification to rep's personal cell ─────────────────────
        # Sends via the rep's dedicated Twilio number so it arrives as a real text.
        # Includes a direct link so the rep can tap and land on the conversation.
        if rep_user and not is_stop:
            try:
                # Read rep's notification preferences (default: all on, 30-min throttle)
                notif_prefs = rep_user.get("notification_settings", {})
                sms_active_enabled  = notif_prefs.get("sms_active_conversation", True)
                throttle_minutes    = int(notif_prefs.get("sms_active_throttle_minutes", 30))

                rep_personal_phone = (rep_user.get("phone") or "").strip()
                rep_twilio_number  = (rep_user.get("twilio_number") or rep_user.get("mvpline_number") or "").strip()

                if sms_active_enabled and rep_personal_phone and rep_twilio_number:
                    rep_cell = normalize_phone(rep_personal_phone)
                    # Don't text the rep if THEY are the one who just texted in
                    if rep_cell == normalize_phone(from_phone):
                        raise ValueError("Rep texted themselves — skip notification")

                    app_url   = os.environ.get("PUBLIC_FACING_URL", os.environ.get("APP_URL", "https://app.imonsocial.com"))
                    conv_link = f"{app_url}/thread/{conversation_id}"
                    contact_display = (
                        contact.get("first_name") or
                        contact.get("name") or
                        from_phone[-4:]
                    )

                    # Rate-limit to throttle_minutes per conversation
                    last_notified = conversation.get("rep_sms_notified_at")
                    throttled = (
                        isinstance(last_notified, datetime) and
                        (datetime.utcnow() - last_notified).total_seconds() < throttle_minutes * 60
                    )

                    if not throttled:
                        tw_sid   = os.environ.get("TWILIO_ACCOUNT_SID", "")
                        tw_token = os.environ.get("TWILIO_AUTH_TOKEN", "")
                        if tw_sid and tw_token:
                            preview_text = (Body or "").strip()[:60]
                            notif_msg = (
                                f"I'm On Social: {contact_display} replied to you.\n"
                                f'"{preview_text}{"..." if len((Body or "")) > 60 else ""}"\n\n'
                                f"Open conversation:\n{conv_link}"
                            )
                            # Fire-and-forget — NEVER await Twilio calls inside a webhook
                            # Twilio requires a response within 15s; blocking here causes retries
                            async def _send_active_sms(to=rep_cell, frm=rep_twilio_number, body=notif_msg, sid=tw_sid, tok=tw_token, conv_id=conversation_id):
                                try:
                                    from twilio.rest import Client as _TC
                                    _TC(sid, tok).messages.create(to=to, from_=frm, body=body)
                                    await db.conversations.update_one(
                                        {"_id": ObjectId(conv_id)},
                                        {"$set": {"rep_sms_notified_at": datetime.utcnow()}}
                                    )
                                    logger.info(f"[Webhook] Sent active-conversation SMS to {to}")
                                except Exception as _e:
                                    logger.debug(f"[Webhook] Active SMS skipped: {_e}")
                            asyncio.create_task(_send_active_sms())
                            # Also send push notification (instant, works when app is open)
                            try:
                                from routers.push_notifications import send_push_to_user
                                app_url_push = os.environ.get("PUBLIC_FACING_URL", os.environ.get("APP_URL", "https://app.imonsocial.com"))
                                asyncio.create_task(send_push_to_user(
                                    user_id or rep_user_id or "",
                                    f"{contact_display} replied",
                                    (Body or "").strip()[:100],
                                    f"{app_url_push}/thread/{conversation_id}",
                                    "chatbubble"
                                ))
                            except Exception:
                                pass
            except Exception as sms_notif_err:
                logger.debug(f"[Webhook] Rep SMS notification skipped: {sms_notif_err}")

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

        if not enrollment_ai_queued and not is_stop:
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
            urn_threshold = int(notif_prefs_esc.get("you_are_needed_threshold", 2))

        effective_reply_count = max(max_reply_count, conv_unanswered)

        if effective_reply_count >= urn_threshold and not is_stop and user_id:
            try:
                cname_esc = contact.get("name") or f"{contact.get('first_name','')} {contact.get('last_name','')}".strip() or from_phone
                # Mark conversation as needing rep attention
                await db.conversations.update_one(
                    {"_id": ObjectId(conversation_id)},
                    {"$set": {
                        "needs_assistance":          True,
                        "unanswered_customer_replies": max_reply_count,
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

                # Send URGENT SMS to rep's personal cell — fire-and-forget, never block webhook
                try:
                    notif_prefs2   = (rep_user or {}).get("notification_settings", {}) if rep_user else {}
                    sms_urn_enabled = notif_prefs2.get("sms_you_are_needed", True)
                    rep_personal_phone = (rep_user.get("phone") or "").strip() if rep_user else ""
                    rep_twilio_number  = (rep_user.get("twilio_number") or rep_user.get("mvpline_number") or "").strip() if rep_user else ""
                    if sms_urn_enabled and rep_personal_phone and rep_twilio_number:
                        tw_sid2   = os.environ.get("TWILIO_ACCOUNT_SID", "")
                        tw_token2 = os.environ.get("TWILIO_AUTH_TOKEN", "")
                        if tw_sid2 and tw_token2:
                            app_url2  = os.environ.get("PUBLIC_FACING_URL", os.environ.get("APP_URL", "https://app.imonsocial.com"))
                            conv_link2 = f"{app_url2}/thread/{conversation_id}"
                            from services.twilio_service import normalize_phone as _np2
                            urgent_to = _np2(rep_personal_phone)
                            urgent_frm = rep_twilio_number
                            urgent_body = (
                                f"⚠️ I'm On Social: YOU'RE NEEDED\n"
                                f"{cname_esc} has texted {effective_reply_count} times without a reply.\n\n"
                                f"Open now:\n{conv_link2}"
                            )
                            async def _send_urgent_sms(to=urgent_to, frm=urgent_frm, body=urgent_body, sid=tw_sid2, tok=tw_token2):
                                try:
                                    from twilio.rest import Client as _TC2
                                    _TC2(sid, tok).messages.create(to=to, from_=frm, body=body)
                                    logger.info(f"[Webhook] Sent YOU'RE NEEDED SMS to {to}")
                                except Exception as _ue:
                                    logger.warning(f"[Webhook] Urgent SMS failed: {_ue}")
                            asyncio.create_task(_send_urgent_sms())
                            # Push notification
                            try:
                                from routers.push_notifications import send_push_to_user
                                push_app_url = os.environ.get("PUBLIC_FACING_URL", os.environ.get("APP_URL", "https://app.imonsocial.com"))
                                asyncio.create_task(send_push_to_user(
                                    user_id,
                                    f"⚠️ {cname_esc} needs you",
                                    f"{max_reply_count} messages without a reply",
                                    f"{push_app_url}/thread/{conversation_id}",
                                    "alert-circle"
                                ))
                            except Exception:
                                pass
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
