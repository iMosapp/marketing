"""
AI Reply Queue Router
Manages the intelligent, human-feeling AI reply system for inbound customer messages.

Flow:
  1. Customer replies → inbound webhook calls queue_ai_reply()
  2. Message sits in ai_reply_queue with a randomized human-feeling delay
  3. Scheduler sends it after the delay (if auto mode) or holds for approval
  4. If reply_count >= escalation_threshold → switch to approval mode + notify rep
  5. If rep doesn't act within timeout → escalate to manager

AI Modes (per campaign):
  off                    — automation paused, rep notified only
  draft_only             — AI drafts but never sends; rep sees it in inbox
  auto_reply             — AI sends automatically after human-feeling delay
  auto_with_approval     — auto until escalation threshold, then requires approval
"""
import asyncio
import logging
import os
import random
from datetime import datetime, timezone, timedelta
from typing import Optional
from bson import ObjectId
from fastapi import APIRouter, HTTPException, Request

from routers.database import get_db

router = APIRouter(prefix="/ai-reply", tags=["ai-reply"])
logger = logging.getLogger(__name__)

# AI assist mode constants
AI_MODE_OFF               = "off"
AI_MODE_DRAFT_ONLY        = "draft_only"
AI_MODE_AUTO_REPLY        = "auto_reply"
AI_MODE_AUTO_WITH_APPROVAL = "auto_with_approval"

# Queue item statuses
STATUS_PENDING   = "pending"      # waiting for send_at
STATUS_SENT      = "sent"
STATUS_APPROVED  = "approved"     # rep approved, ready to send
STATUS_REJECTED  = "rejected"     # rep took over manually
STATUS_CANCELLED = "cancelled"    # contact opted out / enrollment paused
STATUS_FAILED    = "failed"


# ── Weighted human-feeling delay ──────────────────────────────────────────────

def get_human_delay(incoming_message: str = "") -> int:
    """
    Returns delay in seconds with a natural distribution:
    - 30–45s  (30%) — quick glance at phone
    - 45–70s  (50%) — most natural, feels responsive
    - 70–90s  (20%) — slightly busy
    """
    rand = random.random()
    if rand < 0.30:
        base = random.uniform(30, 45)
    elif rand < 0.80:
        base = random.uniform(45, 70)
    else:
        base = random.uniform(70, 90)

    # Add a few extra seconds for longer messages (reading time)
    if len(incoming_message) > 80:
        base += random.uniform(5, 10)

    return int(base)


# ── Core queue function — called by inbound webhook ──────────────────────────

async def queue_ai_reply(
    contact_id: str,
    conversation_id: str,
    enrollment_id: str,
    campaign_id: str,
    assigned_user_id: str,
    incoming_message: str,
    ai_assist_mode: str,
    escalation_threshold: int = 2,
    escalation_timeout_minutes: int = 15,
    escalation_manager_id: Optional[str] = None,
    reply_count: int = 1,
) -> Optional[dict]:
    """
    Generate an AI draft and add it to the queue.
    Returns the queue document or None if mode is off/draft_only with no send.
    """
    db = get_db()

    if ai_assist_mode == AI_MODE_OFF:
        return None  # Caller already paused + notified rep

    # ── Content-based immediate escalation ──────────────────────────────────
    # If the customer's message is about specific inventory, pricing, color,
    # or scheduling, flag the conversation for rep attention NOW — don't wait
    # for a message-count threshold. Reply with a brief "let me check" then escalate.
    ESCALATION_SIGNALS = [
        "in stock", "available", "availability", "do you have",
        "price", "pricing", "cost", "how much", "what does it cost", "what's the price",
        "color", "colour", "black", "white", "blue", "red", "silver", "grey", "gray",
        "appointment", "schedule", "test drive", "come in", "come by", "stop by",
        "trade", "trade-in", "trade in", "trade value",
        "finance", "financing", "payment", "monthly",
        "vin", "specific", "which one", "which ones", "do you stock",
    ]
    msg_lower = (incoming_message or "").lower()
    is_hot_topic = any(sig in msg_lower for sig in ESCALATION_SIGNALS)

    if is_hot_topic:
        logger.info(f"[AIReply] Hot topic detected in message — sending brief reply + escalating for {contact_id}")
        # Generate a brief warm response and immediately flag for rep
        hot_reply = "Good question, let me check on that and get back to you."
        now = datetime.utcnow()
        delay = 30  # Quick reply since we're escalating anyway
        # Flag the conversation so the rep gets notified
        try:
            await db.conversations.update_one(
                {"_id": ObjectId(conversation_id)},
                {"$set": {
                    "needs_assistance": True,
                    "unanswered_customer_replies": 999,  # Forces YOU'RE NEEDED threshold
                    "you_are_needed_at": now,
                }}
            )
        except Exception:
            pass
        # Queue the brief reply
        queue_item = {
            "contact_id":       contact_id,
            "conversation_id":  conversation_id,
            "enrollment_id":    enrollment_id,
            "campaign_id":      campaign_id,
            "assigned_user_id": assigned_user_id,
            "body":             hot_reply,
            "send_at":          now + timedelta(seconds=delay),
            "status":           "pending",
            "requires_approval": False,
            "ai_mode_used":     ai_assist_mode,
            "created_at":       now,
            "hot_topic_escalation": True,
        }
        result = await db.ai_reply_queue.insert_one(queue_item)
        queue_item["_id"] = str(result.inserted_id)
        logger.info(f"[AIReply] Hot topic brief reply queued + rep escalation triggered for {contact_id}")
        return queue_item

    # ── Generate AI draft ──────────────────────────────────────────────────
    try:
        from routers.ai_campaigns import build_clone_system_prompt, get_contact_context
        from emergentintegrations.llm.chat import LlmChat, UserMessage

        system_prompt = await build_clone_system_prompt(assigned_user_id)
        system_prompt += (
            "\n\nIMPORTANT: You are responding to a customer who replied to your message. "
            "Keep it natural, short, and conversational — 1-3 sentences max. "
            "Act exactly like the salesperson would respond. Never sound like a bot."
        )

        contact_context = await get_contact_context(assigned_user_id, contact_id)

        # Pull recent conversation for context
        recent = await db.messages.find(
            {"conversation_id": conversation_id}
        ).sort("timestamp", -1).limit(8).to_list(8)
        recent.reverse()
        conv_lines = "\n".join(
            f"{'Me' if m.get('sender') in ('user','ai') else 'Customer'}: {m.get('content','')[:200]}"
            for m in recent
        )

        nl = "\n\n"
        user_prompt = (
            f"Customer context:\n{contact_context}\n\n"
            f"{'Recent conversation:' + nl + conv_lines + nl if conv_lines else ''}"
            f"Customer just said: \"{incoming_message}\"\n\n"
            "Reply naturally and briefly as me. Just the reply text, nothing else."
        )

        emergent_key = os.environ.get("EMERGENT_LLM_KEY", "")
        # Use a unique session ID per reply — conversation context is passed explicitly
        # in the user_prompt, so reusing sessions would add stale/incorrect history
        import uuid as _uuid
        session_id = f"reply-{_uuid.uuid4().hex[:16]}"
        chat = LlmChat(
            api_key=emergent_key,
            session_id=session_id,
            system_message=system_prompt,
        ).with_model("openai", "gpt-5.2")

        response = await asyncio.wait_for(
            chat.send_message(UserMessage(text=user_prompt)),
            timeout=12.0,  # Never hang longer than 12s — Twilio's webhook timeout is 15s
        )
        ai_body = (response.strip() if isinstance(response, str)
                   else response.text.strip() if hasattr(response, "text")
                   else str(response)).strip('"\'')

    except Exception as e:
        logger.error(f"[AIReply] Draft generation failed for {contact_id}: {e}")
        from utils.system_logger import syslog
        await syslog.error("ai_reply", f"Draft generation failed", error=e,
                           contact_id=contact_id, conversation_id=conversation_id,
                           user_id=assigned_user_id)
        ai_body = None

    if not ai_body:
        return None

    # ── Determine if this needs approval ─────────────────────────────────────
    needs_approval = False
    if ai_assist_mode == AI_MODE_DRAFT_ONLY:
        needs_approval = True  # Never auto-sends
    elif ai_assist_mode == AI_MODE_AUTO_WITH_APPROVAL and reply_count >= escalation_threshold:
        needs_approval = True  # Escalation threshold hit

    # ── Calculate send_at ─────────────────────────────────────────────────────
    delay = get_human_delay(incoming_message)
    send_at = datetime.now(timezone.utc) + timedelta(seconds=delay)

    # ── Build queue doc ───────────────────────────────────────────────────────
    now = datetime.now(timezone.utc)
    queue_doc = {
        "enrollment_id":               enrollment_id,
        "campaign_id":                 campaign_id,
        "contact_id":                  contact_id,
        "conversation_id":             conversation_id,
        "assigned_user_id":            assigned_user_id,
        "body":                        ai_body,
        "send_at":                     send_at,
        "status":                      STATUS_PENDING,
        "requires_approval":           needs_approval,
        "approved_by":                 None,
        "approved_at":                 None,
        "rejected_by":                 None,
        "escalated_at":                None,
        "escalation_notified_user_id": None,
        "escalation_timeout_minutes":  escalation_timeout_minutes,
        "escalation_manager_id":       escalation_manager_id,
        "delay_seconds":               delay,
        "ai_mode_used":                ai_assist_mode,
        "reply_count_at_creation":     reply_count,
        "incoming_message_preview":    incoming_message[:200],
        "created_at":                  now,
    }

    result = await db.ai_reply_queue.insert_one(queue_doc)
    queue_doc["_id"] = str(result.inserted_id)
    queue_doc["id"]  = str(result.inserted_id)

    logger.info(
        f"[AIReply] Queued reply for contact={contact_id} | "
        f"delay={delay}s | needs_approval={needs_approval} | mode={ai_assist_mode}"
    )

    # ── Notify rep of incoming + draft ────────────────────────────────────────
    try:
        contact = await db.contacts.find_one({"_id": ObjectId(contact_id)}, {"first_name": 1, "last_name": 1})
        cname = f"{contact.get('first_name','')} {contact.get('last_name','')}".strip() if contact else "Customer"

        if needs_approval:
            notif_title   = f"Review AI draft — {cname} replied"
            notif_message = (
                f"{cname} has replied {reply_count}+ times. "
                f"AI draft ready — approve before it sends.\n\"{ai_body[:100]}...\""
                if len(ai_body) > 100 else
                f"{cname} has replied {reply_count}+ times. AI draft: \"{ai_body}\""
            )
            notif_type = "ai_draft_approval_required"
        else:
            notif_title   = f"{cname} replied"
            notif_message = f"AI is responding in ~{delay//60}m {delay%60}s. Draft: \"{ai_body[:80]}\""
            notif_type    = "customer_reply_ai_handling"

        await db.notifications.insert_one({
            "user_id":         assigned_user_id,
            "type":            notif_type,
            "title":           notif_title,
            "message":         notif_message,
            "contact_id":      contact_id,
            "conversation_id": conversation_id,
            "queue_id":        str(result.inserted_id),
            "campaign_id":     campaign_id,
            "read":            False,
            "dismissed":       False,
            "created_at":      now,
        })
    except Exception as e:
        logger.warning(f"[AIReply] Notification failed (non-fatal): {e}")

    return queue_doc


# ── Scheduler functions ───────────────────────────────────────────────────────

async def process_ai_reply_queue():
    """
    Called every 60 seconds by the scheduler.
    Uses atomic find_one_and_update to claim items — prevents double-send race condition.
    """
    db  = get_db()
    now = datetime.now(timezone.utc)

    # Atomically claim due items one at a time using findOneAndUpdate
    # This is the ONLY safe way to prevent two scheduler runs from sending the same message twice
    claimed = []
    for _ in range(10):
        item = await db.ai_reply_queue.find_one_and_update(
            {
                "status":            STATUS_PENDING,
                "requires_approval": False,
                "send_at":           {"$lte": now},
            },
            {"$set": {"status": "sending", "claimed_at": now}},
            return_document=True,
        )
        if not item:
            break
        claimed.append(item)

    if not claimed:
        return

    logger.info(f"[AIReply] Processing {len(claimed)} queued replies (atomic claim)")

    for item in claimed:
        qid = item["_id"]
        try:
            phone = None
            contact = await db.contacts.find_one({"_id": ObjectId(item["contact_id"])})
            if contact:
                phone = contact.get("phone")
                if contact.get("opted_out"):
                    await db.ai_reply_queue.update_one(
                        {"_id": qid}, {"$set": {"status": STATUS_CANCELLED, "cancel_reason": "contact_opted_out"}}
                    )
                    continue

            if not phone:
                await db.ai_reply_queue.update_one(
                    {"_id": qid}, {"$set": {"status": STATUS_FAILED, "error": "no phone number"}}
                )
                continue

            # ── Rep override check — never send if AI was turned off AFTER this was queued ──
            if item.get("conversation_id"):
                try:
                    conv = await db.conversations.find_one(
                        {"_id": ObjectId(item["conversation_id"])},
                        {"ai_enabled": 1, "ai_mode": 1}
                    )
                    if conv:
                        ai_off = (
                            conv.get("ai_enabled") is False or
                            conv.get("ai_mode") in ("off", None, "")
                        )
                        if ai_off:
                            logger.info(f"[AIReply] Skipping queued item — AI turned off on conversation {item['conversation_id']}")
                            await db.ai_reply_queue.update_one(
                                {"_id": qid}, {"$set": {"status": STATUS_CANCELLED, "cancel_reason": "ai_disabled_by_rep"}}
                            )
                            continue
                except Exception:
                    pass

            from services.twilio_service import send_sms
            result = await send_sms(phone, item["body"])
            mocked = result.get("mock", True)

            await db.ai_reply_queue.update_one(
                {"_id": qid},
                {"$set": {
                    "status":      STATUS_SENT,
                    "sent_at":     now,
                    "twilio_sid":  result.get("sid"),
                    "mocked":      mocked,
                }}
            )

            # Log message to conversation
            await db.messages.insert_one({
                "conversation_id": item.get("conversation_id"),
                "content":         item["body"],
                "sender":          "ai",
                "direction":       "outbound",
                "channel":         "sms",
                "ai_generated":    True,
                "requires_review": False,
                "campaign_id":     item.get("campaign_id"),
                "twilio_sid":      result.get("sid"),
                "timestamp":       now,
                "status":          "sent" if not mocked else "sent_mock",
            })

            # Sync conversation's AI mode so the UI reflects reality
            # (new conversations default ai_enabled: False but AI is actually active)
            if item.get("conversation_id") and item.get("ai_mode_used") and item["ai_mode_used"] != "off":
                try:
                    await db.conversations.update_one(
                        {"_id": ObjectId(item["conversation_id"]),
                         "$or": [{"ai_enabled": {"$ne": True}}, {"ai_mode": {"$in": [None, "", "off"]}}]},
                        {"$set": {"ai_enabled": True, "ai_mode": item["ai_mode_used"]}}
                    )
                except Exception:
                    pass

            # Log to contact_events so the wins feed + activity feed stay current
            if item.get("contact_id"):
                try:
                    await db.contact_events.insert_one({
                        "user_id":     item.get("assigned_user_id"),
                        "contact_id":  item["contact_id"],
                        "event_type":  "ai_reply_sent",
                        "category":    "sent",
                        "title":       "AI Auto-Reply Sent",
                        "description": item["body"][:200],
                        "channel":     "sms",
                        "ai_generated": True,
                        "timestamp":   now,
                    })
                except Exception:
                    pass
            # Note: "You're Needed" badge is intentionally NOT cleared by AI replies —
            # only cleared when the rep personally sends a message (see messages.py)

            logger.info(f"[AIReply] Sent {'(MOCK) ' if mocked else ''}to {phone}")

        except Exception as e:
            logger.error(f"[AIReply] Send failed for queue {qid}: {e}")
            from utils.system_logger import syslog
            await syslog.error("ai_reply_send", f"SMS send failed", error=e,
                               queue_id=str(qid), contact_id=item.get("contact_id",""))
            await db.ai_reply_queue.update_one(
                {"_id": qid}, {"$set": {"status": STATUS_FAILED, "error": str(e)}}
            )


async def process_ai_reply_escalations():
    """
    Called every 60 seconds.
    Checks for approval-required items where the rep hasn't acted within the timeout.
    Escalates to manager.
    """
    db  = get_db()
    now = datetime.now(timezone.utc)

    # Find items awaiting approval that have timed out and not yet escalated
    pending_approval = await db.ai_reply_queue.find({
        "status":           STATUS_PENDING,
        "requires_approval": True,
        "escalated_at":     None,
    }).to_list(100)

    for item in pending_approval:
        timeout_min = item.get("escalation_timeout_minutes", 15)
        deadline    = item["created_at"].replace(tzinfo=timezone.utc) + timedelta(minutes=timeout_min)

        if now < deadline:
            continue  # Still within window

        # Timeout exceeded — escalate to manager
        manager_id = item.get("escalation_manager_id")
        if not manager_id:
            # Find store_manager or org_admin as fallback
            user = await db.users.find_one({"_id": ObjectId(item["assigned_user_id"])}) if item.get("assigned_user_id") else None
            if user and user.get("store_id"):
                store_team = await db.users.find_one({
                    "store_id": user["store_id"],
                    "role":     {"$in": ["store_manager", "org_admin", "super_admin"]},
                    "_id":      {"$ne": ObjectId(item["assigned_user_id"])},
                })
                manager_id = str(store_team["_id"]) if store_team else None

        await db.ai_reply_queue.update_one(
            {"_id": item["_id"]},
            {"$set": {
                "escalated_at":                now,
                "escalation_notified_user_id": manager_id,
            }}
        )

        if manager_id:
            contact = await db.contacts.find_one({"_id": ObjectId(item["contact_id"])}, {"first_name": 1, "last_name": 1})
            cname   = f"{contact.get('first_name','')} {contact.get('last_name','')}".strip() if contact else "a customer"
            rep     = await db.users.find_one({"_id": ObjectId(item["assigned_user_id"])}, {"name": 1}) if item.get("assigned_user_id") else None
            rep_name = rep.get("name", "An assigned rep") if rep else "An assigned rep"

            await db.notifications.insert_one({
                "user_id":     manager_id,
                "type":        "escalation_manager_required",
                "title":       f"Escalation: {cname} is waiting",
                "message":     (
                    f"{rep_name} hasn't responded to {cname}'s message in {timeout_min} minutes. "
                    f"AI draft is on hold. Please review or reassign."
                ),
                "contact_id":      item.get("contact_id"),
                "conversation_id": item.get("conversation_id"),
                "queue_id":        str(item["_id"]),
                "priority":        "urgent",
                "read":            False,
                "dismissed":       False,
                "created_at":      now,
            })
            logger.info(f"[AIReply] Escalated queue {item['_id']} to manager {manager_id}")


# ── API Endpoints ─────────────────────────────────────────────────────────────

@router.get("/pending/{user_id}")
async def get_pending_approvals(user_id: str):
    """Get all AI drafts waiting for this rep's approval."""
    db    = get_db()
    items = await db.ai_reply_queue.find({
        "assigned_user_id": user_id,
        "status":           STATUS_PENDING,
        "requires_approval": True,
    }).sort("created_at", 1).to_list(50)

    results = []
    for item in items:
        contact = await db.contacts.find_one({"_id": ObjectId(item["contact_id"])}, {"first_name": 1, "last_name": 1, "phone": 1})
        escalated = item.get("escalated_at") is not None
        timeout   = item.get("escalation_timeout_minutes", 15)
        deadline  = item["created_at"].replace(tzinfo=timezone.utc) + timedelta(minutes=timeout)
        mins_left = max(0, int((deadline - datetime.now(timezone.utc)).total_seconds() // 60))

        results.append({
            "id":             str(item["_id"]),
            "contact_id":     item["contact_id"],
            "contact_name":   f"{contact.get('first_name','')} {contact.get('last_name','')}".strip() if contact else "Unknown",
            "contact_phone":  contact.get("phone","") if contact else "",
            "conversation_id": item.get("conversation_id"),
            "campaign_id":    item.get("campaign_id"),
            "body":           item["body"],
            "incoming_preview": item.get("incoming_message_preview",""),
            "reply_count":    item.get("reply_count_at_creation", 1),
            "created_at":     item["created_at"].isoformat(),
            "escalated":      escalated,
            "minutes_until_escalation": mins_left if not escalated else 0,
        })

    return {"pending": results, "count": len(results)}


@router.post("/{queue_id}/approve")
async def approve_ai_reply(queue_id: str, request: Request):
    """Rep approves an AI draft — it sends immediately."""
    db   = get_db()
    data = await request.json()
    user_id = data.get("user_id")

    item = await db.ai_reply_queue.find_one({"_id": ObjectId(queue_id)})
    if not item:
        raise HTTPException(status_code=404, detail="Queue item not found")
    if item["status"] != STATUS_PENDING:
        raise HTTPException(status_code=400, detail=f"Item is already {item['status']}")

    now = datetime.now(timezone.utc)

    # Override body if rep edited it
    body = data.get("body") or item["body"]

    # Send now via Twilio
    contact = await db.contacts.find_one({"_id": ObjectId(item["contact_id"])})
    phone   = contact.get("phone") if contact else None
    if not phone:
        raise HTTPException(status_code=400, detail="No phone number on contact")

    from services.twilio_service import send_sms
    result = await send_sms(phone, body)

    await db.ai_reply_queue.update_one(
        {"_id": ObjectId(queue_id)},
        {"$set": {
            "status":      STATUS_APPROVED,
            "approved_by": user_id,
            "approved_at": now,
            "body":        body,
            "sent_at":     now,
            "twilio_sid":  result.get("sid"),
        }}
    )

    await db.messages.insert_one({
        "conversation_id": item.get("conversation_id"),
        "content":    body,
        "sender":     "ai",
        "direction":  "outbound",
        "channel":    "sms",
        "ai_generated":   True,
        "requires_review": False,
        "approved_by":     user_id,
        "campaign_id":     item.get("campaign_id"),
        "twilio_sid":      result.get("sid"),
        "timestamp":       now,
        "status":          "sent" if not result.get("mock") else "sent_mock",
    })

    return {"success": True, "sent": True, "body": body}


@router.post("/{queue_id}/reject")
async def reject_ai_reply(queue_id: str, request: Request):
    """Rep rejects the AI draft and will handle the conversation manually."""
    db   = get_db()
    data = await request.json()
    user_id = data.get("user_id")

    item = await db.ai_reply_queue.find_one({"_id": ObjectId(queue_id)})
    if not item:
        raise HTTPException(status_code=404, detail="Queue item not found")

    await db.ai_reply_queue.update_one(
        {"_id": ObjectId(queue_id)},
        {"$set": {
            "status":      STATUS_REJECTED,
            "rejected_by": user_id,
            "rejected_at": datetime.now(timezone.utc),
        }}
    )

    return {"success": True, "message": "Draft rejected. You're handling this conversation manually."}


@router.get("/history/{contact_id}")
async def get_contact_reply_history(contact_id: str, limit: int = 20):
    """Get AI reply history for a contact."""
    db    = get_db()
    items = await db.ai_reply_queue.find(
        {"contact_id": contact_id}
    ).sort("created_at", -1).limit(limit).to_list(limit)

    return [{
        "id":              str(i["_id"]),
        "body":            i["body"],
        "status":          i["status"],
        "requires_approval": i.get("requires_approval", False),
        "ai_mode_used":    i.get("ai_mode_used"),
        "delay_seconds":   i.get("delay_seconds"),
        "send_at":         i["send_at"].isoformat() if isinstance(i.get("send_at"), datetime) else None,
        "sent_at":         i.get("sent_at", "").isoformat() if isinstance(i.get("sent_at"), datetime) else None,
        "created_at":      i["created_at"].isoformat(),
        "escalated":       i.get("escalated_at") is not None,
    } for i in items]
