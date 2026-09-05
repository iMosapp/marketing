"""
Twilio Webhooks Router - Handle incoming SMS/MMS messages
"""
import asyncio
from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import Response
from bson import ObjectId
from datetime import datetime, timezone
from typing import Optional, List
import logging
import os
import re
import httpx
import base64

from routers.database import get_db

# ── Satisfied-reply detection (auto-clears the Waiting flag) ─────────────────
_SAT_WORDS = {
    "thanks", "thank", "thx", "ty", "perfect", "awesome", "great", "ok", "okay",
    "kk", "cool", "sweet", "appreciate", "appreciated", "understood", "gotcha",
}
_SAT_PHRASES = [
    "sounds good", "sounds great", "sounds perfect", "got it", "see you", "see ya",
    "will do", "no problem", "no worries", "that works", "works for me",
    "looking forward", "you too", "have a good", "all good", "thank you",
    "cant wait", "can't wait",
]
_NEG_WORDS = {
    "not", "don't", "dont", "cant", "can't", "wont", "won't", "wrong", "never",
    "stop", "bad", "upset", "issue", "unhappy", "frustrated", "waiting", "still",
    "but", "actually", "instead", "cancel", "refund",
}


def _is_satisfied_reply(text: str) -> bool:
    """Short positive closer, no question, no pushback — nothing left for the rep to do."""
    t = (text or "").strip().lower()
    if not t or len(t) > 80 or "?" in t:
        return False
    cleaned = t.replace("no problem", "").replace("no worries", "")
    words = set(re.findall(r"[a-z']+", cleaned))
    if words & _NEG_WORDS:
        return False
    return bool(words & _SAT_WORDS) or any(p in t for p in _SAT_PHRASES)

router = APIRouter(prefix="/webhooks/twilio", tags=["Twilio Webhooks"])
logger = logging.getLogger(__name__)

# Backend URL for constructing media URLs
BACKEND_URL = os.environ.get("PUBLIC_FACING_URL", os.environ.get("APP_URL", os.environ.get("REACT_APP_BACKEND_URL", "https://app.imonsocial.com")))


async def download_and_store_media(media_url: str, media_type: str) -> Optional[str]:
    """
    Return a proxied URL that serves Twilio media with authentication.
    The proxy approach is more reliable than downloading — no upload timeout risk.
    """
    if not media_url or not media_url.startswith("http"):
        return None
    import urllib.parse
    public_url = os.environ.get("PUBLIC_FACING_URL", os.environ.get("APP_URL", "https://app.imonsocial.com"))
    encoded = urllib.parse.quote(media_url, safe='')
    return f"{public_url}/api/webhooks/twilio/media-proxy?url={encoded}"


@router.get("/media-proxy")
async def proxy_twilio_media(url: str):
    """
    Proxy endpoint for Twilio media — fetches with Twilio auth and returns to client.
    This lets the app display inbound MMS photos without needing Twilio credentials client-side.
    """
    import urllib.parse
    twilio_sid   = os.environ.get("TWILIO_ACCOUNT_SID")
    twilio_token = os.environ.get("TWILIO_AUTH_TOKEN")
    if not twilio_sid or not twilio_token:
        raise HTTPException(status_code=500, detail="Twilio credentials not configured")
    try:
        decoded_url = urllib.parse.unquote(url)
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                decoded_url,
                auth=(twilio_sid, twilio_token),
                follow_redirects=True,
                timeout=20.0,
            )
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail="Media fetch failed")
        content_type = resp.headers.get("content-type", "image/jpeg")
        from fastapi.responses import Response as FastAPIResponse
        return FastAPIResponse(
            content=resp.content,
            media_type=content_type,
            headers={"Cache-Control": "public, max-age=86400"},
        )
    except Exception as e:
        logger.error(f"[MediaProxy] Error: {e}")
        raise HTTPException(status_code=500, detail="Media proxy error")


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

    # ── iMessage Tapback / Reaction Filter ──────────────────────────────────────
    # When an iPhone user "hearts", "likes", or reacts to a message, iOS sends a
    # special SMS like: Liked "your message text"
    # These are NOT real replies — silently ignore them so Jessi never responds.
    _TAPBACK_PREFIXES = (
        'liked "', 'loved "', 'disliked "', 'laughed at "',
        'emphasized "', 'questioned "',
        "liked \u201c", "loved \u201c", "disliked \u201c",  # curly quotes
        "laughed at \u201c", "emphasized \u201c", "questioned \u201c",
    )
    if Body and Body.lower().strip().startswith(_TAPBACK_PREFIXES):
        logger.info(f"[Webhook] iMessage tapback ignored from {from_phone}: {Body[:60]}")
        return Response(
            content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
            media_type="application/xml"
        )

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
            # Internet lead replying to its intake text: the lead thread already knows its contact
            # (owned by the store or the assigned rep) - reuse it instead of minting "Lead (1234)".
            lead_conv = await db.conversations.find_one(
                {"rep_phone": to_phone, "contact_phone": from_phone, "is_internet_lead": True, "contact_id": {"$ne": None}},
                {"contact_id": 1},
            )
            if lead_conv and ObjectId.is_valid(str(lead_conv.get("contact_id"))):
                contact = await db.contacts.find_one({"_id": ObjectId(lead_conv["contact_id"])})
                if contact:
                    logger.info(f"[Webhook] Reusing internet-lead contact {lead_conv['contact_id']} for {from_phone}")
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
                    {
                        "$or": [{"phone": from_phone}, {"phone": alt_phone}, {"phone": from_phone.lstrip("+")}],
                        "name": {"$nin": ["Contact", "Unknown", "New Lead", "", None], "$not": {"$regex": "^Lead \\("}}
                    },
                    {"name": 1, "first_name": 1, "last_name": 1, "photo_url": 1, "photo_thumbnail": 1}
                )
                if any_contact and any_contact.get("name"):
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
                # download_and_store_media now returns a full public URL
                full_url = await download_and_store_media(twilio_url, media_type)
                
                if full_url:
                    stored_media_urls.append(full_url)
                    stored_media_ids.append(full_url)
                else:
                    # Fallback: use Twilio URL directly
                    stored_media_urls.append(twilio_url)
            
            message["media_urls"] = stored_media_urls
            message["media_ids"] = stored_media_ids
            message["media_types"] = media_types
            message["has_media"] = True
            message["num_media"] = num_media
            message["original_twilio_urls"] = media_urls  # Keep original for reference
        
        msg_insert = await db.messages.insert_one(message)
        logger.info(f"Saved incoming message to conversation {conversation_id}")

        # ── Keyword auto-tagging (fire-and-forget) ──────────────────────────────
        try:
            from services.keyword_tagging import schedule_keyword_tagging
            schedule_keyword_tagging(user_id, contact_id, Body or "", "sms", str(msg_insert.inserted_id), conversation_id, sender="contact")
        except Exception as kt_err:
            logger.warning(f"[KeywordTag] schedule failed: {kt_err}")

        # ── "call me Thursday" -> task on the contact (fire-and-forget, never touches routing) ──
        try:
            from routers.tasks import extract_task_from_text, text_has_schedule_hint
            if text_has_schedule_hint(Body or ""):
                _cn = (contact.get("name") or f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip() or f"({from_phone[-4:]})")
                asyncio.create_task(extract_task_from_text(user_id, contact_id, _cn, Body or "", str(msg_insert.inserted_id)))
        except Exception as tx_err:
            logger.warning(f"[TaskExtract] schedule failed: {tx_err}")

        # ── Customer texted back while a voicemail retry was open -> close it + ping the rep (fire-and-forget) ──
        if (Body or "").strip().upper() not in ("STOP", "STOPALL", "UNSUBSCRIBE", "CANCEL", "END", "QUIT"):
            try:
                from services.call_followup import on_customer_replied
                asyncio.create_task(on_customer_replied(user_id, contact_id, conversation_id, Body or ""))
            except Exception as cr_err:
                logger.warning(f"[CallRetry] reply hook failed: {cr_err}")

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
            projection={"unanswered_customer_replies": 1, "ai_mode": 1, "ai_enabled": 1, "rep_sms_notified_at": 1, "needs_assistance": 1, "ai_paused_for_human": 1}
        )
        conv_unanswered = (convo_update or {}).get("unanswered_customer_replies", 1) if convo_update else 1
        logger.info(f"[Webhook] Unanswered count for conv {conversation_id}: {conv_unanswered}")

        # ── Auto-clear Waiting: customer answered happily after an AI reply ─────
        # A short positive closer means nothing is left to do — clear the flag,
        # reset the counter, dismiss You're-Needed alerts. AI mode untouched.
        # NEVER auto-clear while Jessi is paused on a fact question: "ok thanks"
        # after "let me check on that" still needs the rep's real answer.
        is_satisfied = _is_satisfied_reply(Body) and not (convo_update or {}).get("ai_paused_for_human")
        if is_satisfied and convo_update:
            _cf = convo_update
            _ai_on = _cf.get("ai_enabled") is not False and _cf.get("ai_mode") not in ("off", "draft_only", "assisted")
            if _ai_on:
                try:
                    await db.conversations.update_one(
                        {"_id": ObjectId(conversation_id)},
                        {"$set": {"needs_assistance": False, "unanswered_customer_replies": 0}},
                    )
                    if _cf.get("needs_assistance"):
                        await db.notifications.update_many(
                            {"conversation_id": conversation_id, "type": "you_are_needed", "dismissed": {"$ne": True}},
                            {"$set": {"dismissed": True, "read": True}},
                        )
                    conv_unanswered = 0
                    try:
                        await db.waiting_clear_log.insert_one({
                            "user_id": user_id, "conversation_id": conversation_id,
                            "reason": "satisfied", "cleared_at": datetime.utcnow(),
                        })
                    except Exception:
                        pass
                    logger.info(f"[Webhook] Customer sounded satisfied — auto-cleared Waiting for conv {conversation_id}")
                except Exception as sce:
                    logger.warning(f"[Webhook] Satisfied auto-clear failed: {sce}")

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

        # ── Buying Intent Detection — fire-and-forget, never blocks response ──────
        if user_id and contact_id and Body and Body.strip() and conversation_id:
            try:
                cname = contact.get("name") or f"{contact.get('first_name','')} {contact.get('last_name','')}".strip() or from_phone
                from services.intent_detection import process_inbound_intent
                asyncio.create_task(process_inbound_intent(
                    db=db,
                    message=Body,
                    contact_name=cname,
                    contact_id=str(contact_id),
                    conversation_id=str(conversation_id),
                    user_id=str(user_id),
                ))
            except Exception as _ie:
                logger.debug(f"[Webhook] Intent detection task creation failed (non-fatal): {_ie}")

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
        # An EXPLICIT active ai_mode (auto_reply/draft_only/auto_with_approval) always wins,
        # even if a stale ai_enabled=False flag is on the conversation.
        _conv_mode = (conversation.get("ai_mode") or "").strip()
        _conv_explicitly_on = _conv_mode in ("auto_reply", "draft_only", "auto_with_approval")
        conv_ai_off = not _conv_explicitly_on and (
            conversation.get("ai_enabled") is False or
            _conv_mode in ("off", "")
        )

        active_enrollments = await db.campaign_enrollments.find({
            "contact_id": contact_id, "status": {"$in": ["active", "paused"]},
        }).to_list(10)

        # Track whether escalation already fired for this conversation
        max_reply_count = 0
        enrollment_ai_queued = False

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
            # CRITICAL: If the rep explicitly set the conversation to auto_reply
            # ("Jessi is handling this"), that ALWAYS wins over campaign mode —
            # replies auto-send with no approval gate and no escalation suppression.
            if conv_ai_off:
                ai_mode = "off"
            elif _conv_mode == "auto_reply":
                ai_mode = "auto_reply"
            else:
                ai_mode = (campaign or {}).get("ai_assist_mode") or enrollment.get("ai_assist_mode") or "off"
            if ai_mode not in ("off", None):
                enrollment_ai_queued = True
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
        # NOTE: enrollment_ai_queued is tracked in the loop above from the mode that
        # ACTUALLY fired — never from stale enrollment ai_assist_mode fields.
        if not conv_ai_off and not enrollment_ai_queued and not is_stop:
            conv_ai_mode = _conv_mode
            if conv_ai_mode in ("auto_reply", "draft_only", "auto_with_approval"):
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
            else:
                logger.info(
                    f"[Webhook] No AI queued for conv {conversation_id} — "
                    f"ai_mode={conversation.get('ai_mode')!r}, ai_enabled={conversation.get('ai_enabled')!r}"
                )
        elif conv_ai_off and not is_stop:
            logger.info(f"[Webhook] AI suppressed for conv {conversation_id} — rep turned AI off")

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

        if effective_reply_count >= urn_threshold and not is_stop and user_id and not is_satisfied:
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
                    "title":           f"{cname_esc} needs you - {effective_reply_count} messages waiting",
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
                    notif_prefs2 = (rep_user or {}).get("notification_settings", {}) if rep_user else {}
                    notification_mode = (rep_user or {}).get("notification_mode", "both") if rep_user else "both"
                    sms_urn_enabled = (notif_prefs2.get("sms_you_are_needed", True)
                                       and notification_mode in ("sms", "both"))
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
                notif_type  = "you_are_needed" if (max_reply_count >= 2 and not is_satisfied) else "customer_reply"
                notif_title = (f"{cname} needs you - {max_reply_count} unanswered" if notif_type == "you_are_needed"
                               else f"{cname} replied")
                await db.notifications.insert_one({
                    "user_id": user_id, "type": notif_type,
                    "title": notif_title,
                    "message": Body[:200],
                    "contact_id": contact_id, "conversation_id": conversation_id,
                    "campaign_paused": len(active_enrollments) > 0,
                    "priority": "urgent" if notif_type == "you_are_needed" else "normal",
                    "read": False, "dismissed": False, "created_at": datetime.utcnow(),
                })

                # Send push for EVERY customer reply (not just escalations)
                notification_mode = (rep_user or {}).get("notification_mode", "both") if rep_user else "both"
                if notification_mode in ("push", "both"):
                    try:
                        from routers.push_notifications import send_push_to_user
                        push_msg = (f"{effective_reply_count} messages without a reply"
                                    if notif_type == "you_are_needed" else Body[:100])
                        asyncio.create_task(send_push_to_user(
                            user_id,
                            notif_title,
                            push_msg,
                            f"/thread/{conversation_id}",
                            "alert-circle" if notif_type == "you_are_needed" else "chatbubble",
                        ))
                    except Exception:
                        pass
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

        if MessageStatus in ("delivered", "undelivered", "failed"):
            await _record_send_receipt(db, MessageSid, MessageStatus, ErrorCode or "", ErrorMessage or "")

        if MessageStatus in ("failed", "undelivered"):
            await _handle_failed_outbound(db, MessageSid, From, ErrorCode or "", ErrorMessage or "")
        
    except Exception as e:
        logger.error(f"Error updating message status: {str(e)}")
    
    return Response(content="OK", media_type="text/plain")


async def _record_send_receipt(db, sid: str, status: str, code: str, error: str):
    """Carrier receipt for a scheduled/broadcast send: stamp the pending-send row once and roll the
    broadcast's delivered / undelivered counters (idempotent - Twilio may repeat callbacks)."""
    final = "delivered" if status == "delivered" else "undelivered"
    res = await db.campaign_pending_sends.find_one_and_update(
        {"message_sid": sid, "delivery_status": {"$nin": ["delivered", "undelivered"]}},
        {"$set": {"delivery_status": final, "delivery_error": (f"{code} {error}".strip() if final == "undelivered" else ""),
                  "delivered_at": datetime.now(timezone.utc) if final == "delivered" else None}},
        projection={"broadcast_id": 1},
    )
    if res and res.get("broadcast_id") and ObjectId.is_valid(str(res["broadcast_id"])):
        await db.broadcasts.update_one({"_id": ObjectId(res["broadcast_id"])},
                                       {"$inc": {"delivered_count" if final == "delivered" else "undelivered_count": 1}})


MEDIA_ERROR_CODES = {"11200", "12300", "12400", "21620", "21623", "30008"}


async def _handle_failed_outbound(db, sid: str, from_number: str, code: str, error: str):
    """A text we thought went out did not. Resend text-only when the photo was the problem, then tell the rep."""
    msg = await db.messages.find_one({"twilio_sid": sid})
    if not msg or msg.get("failure_handled"):
        return
    await db.messages.update_one({"_id": msg["_id"]}, {"$set": {"failure_handled": True}})
    conv = await db.conversations.find_one({"_id": ObjectId(msg["conversation_id"])}) if msg.get("conversation_id") and ObjectId.is_valid(str(msg.get("conversation_id"))) else None
    user_id = str(msg.get("user_id") or (conv or {}).get("assigned_to") or (conv or {}).get("user_id") or "")
    contact_id = str(msg.get("contact_id") or (conv or {}).get("contact_id") or "")
    phone = (conv or {}).get("contact_phone") or ""
    if not phone and contact_id and ObjectId.is_valid(contact_id):
        phone = ((await db.contacts.find_one({"_id": ObjectId(contact_id)}, {"phone": 1})) or {}).get("phone", "")
    name = "your customer"
    if contact_id and ObjectId.is_valid(contact_id):
        c = await db.contacts.find_one({"_id": ObjectId(contact_id)}, {"first_name": 1, "last_name": 1})
        if c:
            name = f"{c.get('first_name', '')} {c.get('last_name', '')}".strip() or name

    resent = False
    if msg.get("has_media") and code in MEDIA_ERROR_CODES and phone and msg.get("content") and not msg.get("retry_of"):
        from services.twilio_service import send_sms
        r = await send_sms(phone, msg["content"], from_phone=from_number or None)
        if r.get("success"):
            resent = True
            now = datetime.now(timezone.utc)
            await db.messages.insert_one({
                "conversation_id": msg.get("conversation_id"), "user_id": msg.get("user_id"), "contact_id": msg.get("contact_id"),
                "content": msg["content"], "sender": msg.get("sender", "user"), "direction": "outbound", "channel": "sms",
                "ai_generated": bool(msg.get("ai_generated")), "twilio_sid": r.get("message_sid"), "status": "sent",
                "retry_of": sid, "media_dropped": True, "timestamp": now,
            })
            logger.info(f"[Status] {sid} failed with {code}; resent text-only as {r.get('message_sid')}")

    if not user_id:
        return
    try:
        from routers.push_notifications import send_push_to_user
        who = "Jessi's text" if msg.get("ai_generated") else "Your text"
        if resent:
            title, body = f"{who} to {name}: photo did not go through", "The carrier rejected the picture, so the message was re-sent without it."
        else:
            title, body = f"{who} to {name} did not deliver", f"{(error or 'Carrier rejected the message')[:80]}. Open the thread to try again."
        await send_push_to_user(user_id, title, body, url=f"/thread/{msg.get('conversation_id')}" if msg.get("conversation_id") else "/inbox", icon="alert-circle")
    except Exception as e:
        logger.debug(f"[Status] failure push skipped: {e}")


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
    task_id        = body.get("task_id", "")  # task the rep tapped Call from (auto-completes once connected)

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
        "task_id":           task_id or None,
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
            status_callback_event=["initiated", "ringing", "answered", "completed"],
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
            "message":  f"Calling your phone ({rep_personal_phone[-4:]})... answer and press 1 to connect to {customer_phone_e164}",
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


def _split_stereo_wav(wav_path: str):
    """Split a stereo wav into (left, right) mono wavs. Returns None if not stereo."""
    import wave
    import audioop
    with wave.open(wav_path, "rb") as w:
        ch, width, rate = w.getnchannels(), w.getsampwidth(), w.getframerate()
        frames = w.readframes(w.getnframes())
    if ch != 2:
        return None
    out_paths = []
    for tag, l_w, r_w in (("L", 1, 0), ("R", 0, 1)):
        mono = audioop.tomono(frames, width, l_w, r_w)
        p = wav_path[:-4] + f"_{tag}.wav"
        with wave.open(p, "wb") as out:
            out.setnchannels(1)
            out.setsampwidth(width)
            out.setframerate(rate)
            out.writeframes(mono)
        out_paths.append(p)
    return out_paths[0], out_paths[1]


def _whisper_segments(result):
    """Extract [(start_seconds, text)] from a verbose_json Whisper response."""
    segs = getattr(result, "segments", None)
    if segs is None and isinstance(result, dict):
        segs = result.get("segments")
    out = []
    for s in segs or []:
        if isinstance(s, dict):
            start, text = s.get("start", 0), (s.get("text") or "").strip()
            nsp = s.get("no_speech_prob", 0)
        else:
            start, text = getattr(s, "start", 0), (getattr(s, "text", "") or "").strip()
            nsp = getattr(s, "no_speech_prob", 0)
        if text and (nsp or 0) < 0.5:
            out.append((float(start or 0), text))
    return out


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
    pending    = None

    # Check pending_calls (outbound calls store context here)
    if CallSid:
        pending = await db.pending_calls.find_one({"call_sid": CallSid})
        if pending:
            user_id      = pending.get("user_id") or pending.get("rep_user_id")
            contact_id   = pending.get("contact_id")
            from_phone   = pending.get("customer_phone") or from_phone
            direction    = "outbound"
            # Task auto-complete + voicemail retry now happen AFTER the transcript says who answered (see _transcribe_and_save)

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
        transcript_segments = []
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
                    import requests as _req, uuid as _uuid
                    # .wav preserves the dual channels (rep = one channel, customer = the other)
                    wav_url = RecordingUrl if RecordingUrl.endswith(".wav") else f"{RecordingUrl}.wav"
                    logger.info(f"[Voice] Downloading recording from Twilio: {wav_url[:60]}...")

                    def _download():
                        r = _req.get(wav_url, auth=(tw_sid, tw_token), timeout=60)
                        return r.status_code, r.content

                    status_code, content = await _aio.to_thread(_download)

                    if status_code == 200 and content:
                        tmp_path = f"/tmp/call_{_uuid.uuid4().hex}.wav"
                        with open(tmp_path, "wb") as f:
                            f.write(content)
                        logger.info(f"[Voice] Downloaded {len(content)} bytes — transcribing with Whisper...")

                        split_paths = None
                        try:
                            from emergentintegrations.llm.openai import OpenAISpeechToText
                            stt = OpenAISpeechToText(api_key=emergent_key)

                            try:
                                split_paths = await _aio.to_thread(_split_stereo_wav, tmp_path)
                            except Exception as sp_err:
                                logger.warning(f"[Voice] Channel split failed, mono fallback: {sp_err}")

                            if split_paths:
                                # Speaker names: rep from users, customer from contact
                                rep_name = "Rep"
                                try:
                                    if user_id and ObjectId.is_valid(str(user_id)):
                                        rep_doc = await db.users.find_one({"_id": ObjectId(user_id)}, {"name": 1})
                                        rep_name = ((rep_doc or {}).get("name") or "Rep").strip().split()[0] or "Rep"
                                except Exception:
                                    pass
                                cust_name = "Customer"
                                if contact:
                                    cust_name = (contact.get("first_name") or (contact.get("name") or "").split(" ")[0] or "Customer").strip() or "Customer"

                                # Dual-channel: LEFT = parent leg, RIGHT = dialed party.
                                # Outbound click-to-call: parent = rep. Inbound: parent = customer.
                                left_name, right_name = (rep_name, cust_name) if direction == "outbound" else (cust_name, rep_name)

                                async def _tx_verbose(p):
                                    with open(p, "rb") as af:
                                        return await _aio.wait_for(
                                            stt.transcribe(af, language="en", response_format="verbose_json"),
                                            timeout=120.0,
                                        )

                                lres = await _tx_verbose(split_paths[0])
                                rres = await _tx_verbose(split_paths[1])
                                entries = (
                                    [(t, left_name,  "rep" if left_name == rep_name else "customer", txt) for t, txt in _whisper_segments(lres)] +
                                    [(t, right_name, "rep" if right_name == rep_name else "customer", txt) for t, txt in _whisper_segments(rres)]
                                )
                                entries.sort(key=lambda e: e[0])
                                for t, nm, role, txt in entries:
                                    if transcript_segments and transcript_segments[-1]["speaker"] == nm:
                                        transcript_segments[-1]["text"] += " " + txt
                                    else:
                                        transcript_segments.append({"speaker": nm, "role": role, "start": round(t, 1), "text": txt})
                                transcript = "\n".join(f"{s['speaker']}: {s['text']}" for s in transcript_segments)
                                logger.info(f"[Voice] Dual-channel transcript: {len(transcript_segments)} turns for {contact_name}")

                            if not transcript:
                                # Mono fallback (old single-channel recordings)
                                with open(tmp_path, "rb") as audio_file:
                                    result = await _aio.wait_for(
                                        stt.transcribe(audio_file, language="en"),
                                        timeout=90.0
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
                            for _p in [tmp_path] + list(split_paths or []):
                                try:
                                    _ost.remove(_p)
                                except Exception:
                                    pass
                    else:
                        logger.warning(f"[Voice] Recording download failed: HTTP {status_code} from {wav_url[:60]}")
                        from utils.system_logger import syslog
                        await syslog.warning("voice_transcription", f"Recording download failed HTTP {status_code}", recording_url=wav_url[:80], call_sid=CallSid)
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
                        "You are an expert sales CRM assistant. Analyze this sales call transcript and produce a structured summary.\n\n"
                        "Format your response EXACTLY like this:\n\n"
                        "**CALL SUMMARY**\n"
                        "2-3 sentences capturing what the call was about and the overall outcome.\n\n"
                        "**KEY DETAILS**\n"
                        "• Vehicle/product interest: [what they want]\n"
                        "• Budget: [if mentioned]\n"
                        "• Timeline: [urgency or timeframe]\n"
                        "• Objections: [concerns raised]\n"
                        "• Personal notes: [anything personal — spouse, kids, job, etc.]\n\n"
                        "**FOLLOW-UP ACTIONS**\n"
                        "List 2-4 specific, actionable next steps the rep should take. Be concrete — not 'follow up' but 'Text John about the F-150 availability'.\n\n"
                        "Skip any section where nothing was mentioned. Keep total response under 200 words."
                    ),
                ).with_model("openai", "gpt-5.2")
                resp = await _aio.wait_for(
                    chat.send_message(UserMessage(text=f"Transcript:\n{transcript}")),
                    timeout=20.0
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
            "transcript_segments": transcript_segments,
            "ai_summary":       ai_summary,
            "direction":        direction,
            "timestamp":        now,
            "created_at":       now,
        })

        # Outbound click-to-call: voicemail / no answer -> retry task; live person -> complete the task you called from
        if pending and direction == "outbound":
            try:
                from services.call_followup import detect_outcome, apply_call_outcome
                _outcome = await detect_outcome(transcript, dur)
                await db.call_logs.update_one({"call_sid": CallSid}, {"$set": {"outcome": _outcome}})
                await apply_call_outcome(pending, _outcome, dur, source="transcript")
                if _outcome != "connected":
                    ai_summary = (f"[{'Voicemail' if _outcome == 'voicemail' else 'No answer'}] " + ai_summary).strip()
            except Exception as _oe:
                logger.warning(f"[Voice] call outcome handling failed: {_oe}")

        # Auto-extract scheduled appointments from the call ("I'll call you tomorrow at 2")
        if transcript and user_id and not (pending and direction == "outbound" and ai_summary.startswith("[Voicemail]")):
            try:
                from routers.tasks import extract_appointment_from_call
                asyncio.create_task(extract_appointment_from_call(
                    user_id, contact_id or "", contact_name or "", transcript, CallSid
                ))
            except Exception as appt_err:
                logger.warning(f"[Voice] Appointment extraction schedule failed: {appt_err}")

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
                "transcript_segments": transcript_segments,
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
            _pc = pending or await db.pending_calls.find_one({"call_sid": CallSid})
            conv_id_for_update = (_pc or {}).get("conversation_id")
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

            # ── Keyword auto-tagging on the call transcript ─────────────────────
            if transcript:
                try:
                    from services.keyword_tagging import run_keyword_tagging
                    await run_keyword_tagging(user_id, contact_id, transcript, "call", CallSid, conv_id_for_update)
                except Exception as kt_err:
                    logger.warning(f"[KeywordTag] call transcript tagging failed: {kt_err}")

        # Push notification to rep
        if user_id:
            notif_msg = ai_summary or (transcript[:100] if transcript else "Recording ready to review")
            await db.notifications.insert_one({
                "user_id":       user_id,
                "type":          "call_recorded",
                "priority":      "normal",
                "title":         f"Call summary ready - {contact_name}",
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

    # Press-1 gate: the customer is NOT dialed until the rep confirms.
    # Stops voicemail pickups and hang-ups from dialing the customer anyway.
    from xml.sax.saxutils import escape as _xesc
    say_name = "the customer"
    try:
        cid = pending.get("contact_id")
        if cid:
            c = await db.contacts.find_one({"_id": ObjectId(cid)}, {"first_name": 1, "last_name": 1})
            if c:
                say_name = f"{c.get('first_name', '')} {c.get('last_name', '')}".strip() or say_name
    except Exception:
        pass

    app_url = os.environ.get('PUBLIC_FACING_URL', os.environ.get('APP_URL', 'https://app.imonsocial.com'))
    _action = f"{app_url}/api/webhooks/twilio/call-bridge-connect"
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Gather input="dtmf speech" action="{_action}" method="POST" numDigits="1" timeout="15" speechTimeout="auto" hints="yes, one, connect">
    <Say>Calling {_xesc(say_name)}. Press 1 on your phone's keypad, or say yes, to connect.</Say>
    <Pause length="5"/>
    <Say>Press 1, or say yes, to connect.</Say>
  </Gather>
  <Gather input="dtmf speech" action="{_action}" method="POST" numDigits="1" timeout="8" speechTimeout="auto" hints="yes, one, connect">
    <Say>Last chance. Press 1 or say yes to connect the call.</Say>
  </Gather>
  <Say>No input received. Call cancelled. Goodbye.</Say>
  <Hangup/>
</Response>"""

    logger.info(f"[Voice] Press-1 gate for {caller_number} → {customer_phone}")
    return Response(content=twiml, media_type="application/xml")


@router.post("/call-bridge-connect")
async def call_bridge_connect(
    request: Request,
    CallSid: str = Form(default=""),
    Digits:  str = Form(default=""),
    SpeechResult: str = Form(default=""),
):
    """Rep confirmed at the press-1 gate. Accepts DTMF 1 OR spoken yes/one/connect
    (speech backup for carriers that mangle DTMF)."""
    db = get_db()
    call_sid = CallSid or request.query_params.get("CallSid", "")
    pending = await db.pending_calls.find_one({"call_sid": call_sid}) if call_sid else None

    speech = (SpeechResult or "").lower()
    speech_ok = any(w in speech for w in ("yes", "yeah", "yep", "one", "connect")) and "no " not in f"{speech} "
    confirmed = Digits == "1" or speech_ok

    if not pending or not confirmed:
        logger.info(f"[Voice] Press-1 gate declined (digits='{Digits}', speech='{speech}') for SID={call_sid} — customer NOT dialed")
        return Response(
            content='<?xml version="1.0" encoding="UTF-8"?><Response><Say>Call cancelled. Goodbye.</Say><Hangup/></Response>',
            media_type="application/xml"
        )

    customer_phone = pending.get("customer_phone", "")
    caller_number  = pending.get("rep_twilio_number", "")
    _app = os.environ.get('PUBLIC_FACING_URL', os.environ.get('APP_URL', 'https://app.imonsocial.com'))
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say>Connecting your call now.</Say>
  <Dial callerId="{caller_number}" timeout="30"
        record="record-from-answer-dual"
        action="{_app}/api/webhooks/twilio/call-bridge-result" method="POST"
        recordingStatusCallback="{_app}/api/webhooks/twilio/recording-complete"
        recordingStatusCallbackMethod="POST">
    <Number>{customer_phone}</Number>
  </Dial>
</Response>"""

    logger.info(f"[Voice] Press-1 confirmed — bridging {caller_number} → {customer_phone}")
    return Response(content=twiml, media_type="application/xml")


@router.post("/call-bridge-result")
async def call_bridge_result(
    request: Request,
    CallSid: str = Form(default=""),
    DialCallStatus: str = Form(default=""),
    DialCallDuration: str = Form(default="0"),
    DialCallSid: str = Form(default=""),
):
    """<Dial action>: how the customer leg ended. busy / no-answer / failed -> retry task now;
    completed -> the recording transcript decides voicemail vs. connected (fallback by duration if no recording)."""
    db = get_db()
    dur = int(DialCallDuration or 0)
    logger.info(f"[Voice] Dial result {CallSid}: {DialCallStatus} ({dur}s)")
    pending = await db.pending_calls.find_one({"call_sid": CallSid}) if CallSid else None
    if pending:
        await db.pending_calls.update_one({"_id": pending["_id"]}, {"$set": {
            "dial_status": DialCallStatus, "dial_duration_s": dur, "customer_call_sid": DialCallSid, "dial_ended_at": datetime.now(timezone.utc)}})
        from services.call_followup import apply_call_outcome
        if DialCallStatus in ("busy", "no-answer", "failed", "canceled") or (DialCallStatus in ("completed", "answered") and dur < 8):
            asyncio.create_task(apply_call_outcome(pending, "busy" if DialCallStatus == "busy" else "no_answer", dur, source="dial_status"))
        elif DialCallStatus in ("completed", "answered"):
            async def _fallback():
                await asyncio.sleep(240)
                fresh = await db.pending_calls.find_one({"_id": pending["_id"]})
                if fresh and not fresh.get("outcome_applied"):
                    await apply_call_outcome(fresh, "connected" if dur >= 60 else "voicemail", dur, source="duration_fallback")
            asyncio.create_task(_fallback())
    return Response(content='<?xml version="1.0" encoding="UTF-8"?><Response><Hangup/></Response>', media_type="application/xml")


@router.post("/call-cancel")
async def cancel_click_to_call(request: Request):
    """Red hang-up button in the app — kills the rep leg (customer leg dies with it)."""
    body = await request.json()
    call_sid = body.get("call_sid", "")
    if not call_sid:
        raise HTTPException(status_code=400, detail="call_sid required")
    tw_sid   = os.environ.get("TWILIO_ACCOUNT_SID", "")
    tw_token = os.environ.get("TWILIO_AUTH_TOKEN", "")
    if not tw_sid or not tw_token:
        raise HTTPException(status_code=500, detail="Twilio credentials not configured")
    try:
        import asyncio as _aio
        from twilio.rest import Client as _TC
        client = _TC(tw_sid, tw_token)
        await _aio.to_thread(lambda: client.calls(call_sid).update(status="completed"))
    except Exception as e:
        logger.warning(f"[Voice] Call cancel failed for {call_sid}: {e}")
    db = get_db()
    await db.pending_calls.update_one({"call_sid": call_sid}, {"$set": {"status": "canceled"}})
    logger.info(f"[Voice] Call {call_sid} cancelled from the app")
    return {"success": True}


@router.get("/call-progress/{call_sid}")
async def call_progress(call_sid: str):
    """Live status for the dialer in-call UI (fed by the status callback webhook)."""
    db = get_db()
    doc = await db.pending_calls.find_one({"call_sid": call_sid}, {"status": 1})
    return {"status": (doc or {}).get("status", "unknown")}



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
    db = get_db()
    if CallSid and CallStatus:
        try:
            await db.pending_calls.update_one(
                {"call_sid": CallSid}, {"$set": {"status": CallStatus}}
            )
        except Exception:
            pass
    if CallStatus in ("completed", "failed", "busy", "no-answer"):
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
        record="record-from-answer-dual"
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
