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
from utils.text_sanitize import no_em_dash, clean_ai_text

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


# ── Live inventory lookup for Jessi ──────────────────────────────────────────

_INV_STOPWORDS = {
    "the", "and", "you", "your", "have", "has", "does", "what", "which", "with",
    "how", "much", "many", "any", "are", "was", "for", "can", "could", "would",
    "come", "there", "that", "this", "one", "ones", "get", "got", "still", "about",
    "price", "pricing", "cost", "stock", "available", "availability", "color",
    "colour", "much", "like", "want", "looking", "interested", "info", "more",
}


async def _search_inventory_context(db, user_id: str, message: str):
    """Search the store's live inventory for vehicles matching the customer's
    message. Returns (bullet_list_str, media_urls) — ('' , []) if no matches."""
    import re as _re
    import os as _os
    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)}, {"store_id": 1})
        if not user:
            return "", []
        sid = user.get("store_id")
        scope = {"store_id": str(sid)} if sid else {"$or": [
            {"created_by_user_id": user_id}, {"assigned_to_user_id": user_id}]}

        raw_tokens = [w for w in _re.findall(r"[a-z0-9]+", (message or "").lower())
                      if len(w) >= 3 and w not in _INV_STOPWORDS]
        tokens = []
        for t in raw_tokens[:8]:
            tokens.append(t)
            if t.endswith("s") and len(t) > 3:
                tokens.append(t[:-1])  # "tacomas" should match "Tacoma"
        if not tokens:
            return "", []

        token_ors = []
        for t in tokens:
            rx = {"$regex": t, "$options": "i"}
            token_ors += [
                {"name": rx}, {"description": rx},
                {"attributes.make": rx}, {"attributes.model": rx},
                {"attributes.color": rx}, {"attributes.trim": rx},
            ]
        query = {
            "status": "available", "is_visible": {"$ne": False},
            "$and": [scope, {"$or": token_ors}],
        }
        items = await db.inventory.find(query).limit(12).to_list(12)
        if not items:
            return "", []

        def _hits(it):
            blob = f"{it.get('name', '')} {it.get('description', '')} " + \
                   " ".join(str(v) for v in (it.get("attributes") or {}).values())
            blob = blob.lower()
            return sum(1 for t in set(tokens) if t in blob)

        items.sort(key=_hits, reverse=True)
        public_url = _os.environ.get("PUBLIC_FACING_URL", _os.environ.get("APP_URL", "https://app.imonsocial.com")).rstrip("/")
        lines, media = [], []
        for it in items[:3]:
            a = it.get("attributes") or {}
            bits = [it.get("name", "")]
            if a.get("color"):
                bits.append(str(a["color"]))
            if it.get("price"):
                bits.append(f"${it['price']:,.0f}")
            if a.get("mileage"):
                bits.append(f"{a['mileage']} miles")
            if a.get("stock_number"):
                bits.append(f"Stock #{a['stock_number']}")
            lines.append(" — ".join(str(b) for b in bits if b))
            # Attach the top matching vehicle's photo so Jessi can text the exact car
            if not media:
                if it.get("photo_full_path"):
                    media.append(f"{public_url}/api/images/{it['photo_full_path']}")
                elif it.get("photo_url"):
                    pu = it["photo_url"]
                    media.append(pu if pu.startswith("http") else f"{public_url}{pu}")
        return "\n".join(f"• {l}" for l in lines), media
    except Exception as e:
        logger.debug(f"[AIReply] Inventory search failed: {e}")
        return "", []


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

    # Master AI switch — rep can pause ALL AI replies from the Home screen
    try:
        if assigned_user_id:
            _u = await db.users.find_one({"_id": ObjectId(assigned_user_id)}, {"ai_master_paused": 1})
            if _u and _u.get("ai_master_paused"):
                logger.info(f"AI master paused for user {assigned_user_id} — skipping AI reply")
                # Never let the silence go unnoticed — tell the rep a customer is waiting
                try:
                    contact_doc = await db.contacts.find_one(
                        {"_id": ObjectId(contact_id)}, {"first_name": 1, "last_name": 1, "name": 1}
                    )
                    cname = ((contact_doc or {}).get("name")
                             or f"{(contact_doc or {}).get('first_name','')} {(contact_doc or {}).get('last_name','')}".strip()
                             or "A customer")
                    await db.notifications.insert_one({
                        "user_id":         assigned_user_id,
                        "type":            "ai_paused_customer_waiting",
                        "title":           f"{cname} replied — AI is paused",
                        "message":         f"\"{(incoming_message or '')[:80]}\" — Jessi is OFF (Home AI switch). Reply yourself or turn AI back on.",
                        "contact_id":      contact_id,
                        "conversation_id": conversation_id,
                        "read":            False,
                        "dismissed":       False,
                        "created_at":      datetime.utcnow(),
                    })
                    from routers.push_notifications import send_push_to_user
                    asyncio.create_task(send_push_to_user(
                        assigned_user_id,
                        f"{cname} replied — AI is paused",
                        "Jessi didn't respond because your Home AI switch is off. Reply or resume AI.",
                        f"/thread/{conversation_id}",
                        "alert-circle",
                    ))
                except Exception:
                    pass
                return None
    except Exception:
        pass

    if ai_assist_mode == AI_MODE_OFF:
        logger.info(f"[AIReply] Mode off — not queuing for conversation {conversation_id}")
        return None  # Caller already paused + notified rep

    # ── Content-based immediate escalation ──────────────────────────────────
    # If the customer's message is about specific inventory, pricing, color,
    # or scheduling, flag the conversation for rep attention NOW — don't wait
    # for a message-count threshold. Reply with a brief "let me check" then escalate.
    ESCALATION_SIGNALS = [
        # Inventory / pricing — require specific question phrasing
        "in stock", "available", "availability", "do you have",
        "price", "pricing", "cost", "how much", "what does it cost", "what's the price",
        # Color questions (requires the word "color/colour" OR question phrasing with a color)
        "what color", "what colour", "which color", "which colour",
        "do you have it in", "come in ", "does it come",
        "color name", "colour name",
        # Scheduling / visit intent
        "appointment", "schedule", "test drive", "come in", "come by", "stop by",
        # Trade / finance
        "trade", "trade-in", "trade in", "trade value",
        "finance", "financing", "payment", "monthly",
        "vin", "specific", "which one", "which ones", "do you stock",
        # Customer suspects AI — rep MUST take over immediately
        "robot", "are you a robot", "is this ai", "is this a bot", "are you real",
        "talking to a person", "real person", "automated", "chatbot", "ai bot",
        "computer", "are you human", "is this automated", "machine", "is this jessi",
        "who is this", "who am i talking to",
    ]
    msg_lower = (incoming_message or "").lower()
    is_hot_topic = any(sig in msg_lower for sig in ESCALATION_SIGNALS)

    # Customer suspects AI — a rep MUST take over, never let Jessi keep talking
    AI_SUSPECT_SIGNALS = [
        "robot", "are you a robot", "is this ai", "is this a bot", "are you real",
        "talking to a person", "real person", "automated", "chatbot", "ai bot",
        "computer", "are you human", "is this automated", "machine", "is this jessi",
        "who is this", "who am i talking to",
    ]
    is_ai_suspect = any(sig in msg_lower for sig in AI_SUSPECT_SIGNALS)

    # ── Scheduling / appointment approval hold ────────────────────────────────
    # The rep must approve before Jessi commits to ANY time or visit. This applies
    # in every mode, including full auto - we never let AI lock in an appointment
    # on the dealer's behalf. Jessi still DRAFTS the reply; it just waits for a tap.
    SCHEDULING_SIGNALS = [
        "appointment", "schedule", "reschedule", "rescheduling", "test drive",
        "come in", "come by", "come down", "swing by", "stop by", "drop by",
        "what time", "what day", "book a", "book it", "set a time", "set up a time",
        "lock in", "lock it in", "lock that in", "pencil me in", "pick it up", "pickup",
        "today", "tonight", "tomorrow", "this afternoon", "this evening", "this morning",
        "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
        "o'clock", " am", " pm", "a.m.", "p.m.",
    ]
    import re as _re_sched
    # A short reply that contains a time-like token ("6?", "6pm", "3:30", "at 6")
    # counts as scheduling when the recent thread was about setting a time.
    _has_time_token = bool(_re_sched.search(r"\b\d{1,2}(:\d{2})?\s*(am|pm|a\.m\.|p\.m\.)?\b", msg_lower))
    _recent_for_sched = await db.messages.find(
        {"conversation_id": conversation_id}, {"content": 1}
    ).sort("timestamp", -1).limit(5).to_list(5)
    _recent_blob = " ".join((m.get("content") or "") for m in _recent_for_sched).lower()
    _sched_context = any(s in _recent_blob for s in (
        "what time", "what day", "come in", "come by", "come down", "appointment",
        "schedule", "test drive", "lock", "book", "set up a time", "stop by", "swing by",
    ))
    is_scheduling = (
        any(sig in msg_lower for sig in SCHEDULING_SIGNALS)
        or (_has_time_token and _sched_context)
        or (_sched_context and len(msg_lower.strip()) <= 12)
    )
    # AI-suspicion always wins over scheduling (a human must step in, no draft hold).
    if is_ai_suspect:
        is_scheduling = False

    # Flag the conversation as Waiting when Jessi is holding an appointment draft.
    if is_scheduling:
        try:
            await db.conversations.update_one(
                {"_id": ObjectId(conversation_id)},
                {"$set": {"needs_assistance": True, "you_are_needed_at": datetime.utcnow()}}
            )
        except Exception:
            pass

    # Full auto mode ("Jessi is handling this") means the rep asked Jessi to answer
    # everything herself. Routine inventory/pricing/scheduling questions must NOT be
    # handed to a human - Jessi answers naturally and keeps auto-sending. The only
    # exception is when the customer suspects a bot, where a human must step in.
    suppress_hot_escalation = (ai_assist_mode == AI_MODE_AUTO_REPLY and not is_ai_suspect)

    # If the question is inventory/pricing-related (not AI-suspicion), try LIVE
    # inventory first — Jessi can answer with real availability and pricing.
    inventory_context, inventory_media = "", []
    if is_hot_topic and not is_ai_suspect:
        inventory_context, inventory_media = await _search_inventory_context(db, assigned_user_id, incoming_message)

    if is_hot_topic and not inventory_context and not suppress_hot_escalation and not is_scheduling:
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
        # Push the rep immediately — hot topic can't wait
        if assigned_user_id:
            try:
                contact_doc = await db.contacts.find_one({"_id": ObjectId(contact_id)}, {"first_name": 1, "last_name": 1})
                cname_hot = f"{contact_doc.get('first_name','')} {contact_doc.get('last_name','')}".strip() if contact_doc else "a customer"
                from routers.push_notifications import send_push_to_user
                asyncio.create_task(send_push_to_user(
                    assigned_user_id,
                    f"You're Needed — {cname_hot}",
                    f"Asked: \"{(incoming_message or '')[:80]}\" — Jessi passed it to you.",
                    f"/thread/{conversation_id}",
                    "alert-circle",
                ))
            except Exception:
                pass
        # Queue the brief reply — but only if no hot-topic reply is already pending
        # Also cancel any normal pending reply so we don't send TWO responses
        existing_hot = await db.ai_reply_queue.find_one({
            "conversation_id": conversation_id,
            "status":          "pending",
            "hot_topic_escalation": True,
        })
        if existing_hot:
            logger.info(f"[AIReply] Hot topic already queued for {conversation_id} — skipping duplicate")
            return existing_hot

        # Cancel any normal (non-hot-topic) pending reply so only one response goes out
        await db.ai_reply_queue.update_many(
            {
                "conversation_id": conversation_id,
                "status":          STATUS_PENDING,
                "hot_topic_escalation": {"$ne": True},
            },
            {"$set": {"status": STATUS_CANCELLED, "cancel_reason": "superseded_by_hot_topic"}}
        )

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

    if is_hot_topic and inventory_context and not suppress_hot_escalation and not is_scheduling:
        # Jessi has live inventory facts — answer with real data, but still flag
        # the conversation and notify the rep so they can jump in.
        logger.info(f"[AIReply] Live inventory match — Jessi answering with real data for {contact_id}")
        try:
            await db.conversations.update_one(
                {"_id": ObjectId(conversation_id)},
                {"$set": {"needs_assistance": True, "you_are_needed_at": datetime.utcnow()}}
            )
        except Exception:
            pass
        if assigned_user_id:
            try:
                contact_doc = await db.contacts.find_one({"_id": ObjectId(contact_id)}, {"first_name": 1, "last_name": 1})
                cname_inv = f"{contact_doc.get('first_name','')} {contact_doc.get('last_name','')}".strip() if contact_doc else "a customer"
                from routers.push_notifications import send_push_to_user
                asyncio.create_task(send_push_to_user(
                    assigned_user_id,
                    f"Inventory Question — {cname_inv}",
                    f"Asked: \"{(incoming_message or '')[:70]}\" — Jessi replied with live inventory.",
                    f"/thread/{conversation_id}",
                    "car-sport",
                ))
            except Exception:
                pass

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
        inv_block = ""
        if inventory_context:
            inv_block = (
                "LIVE INVENTORY MATCHES (current and accurate — quote these facts):\n"
                f"{inventory_context}\n"
                "Answer the customer's question using ONLY these vehicles. Mention price/color/mileage "
                "when relevant. If none of them fit what they asked, say you'll double-check what's on the lot.\n\n"
            )
        user_prompt = (
            f"Customer context:\n{contact_context}\n\n"
            f"{inv_block}"
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
        ai_body = no_em_dash(ai_body)
        ai_body = await clean_ai_text(ai_body, assigned_user_id)

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

    # Appointment/time-setting: rep must approve before it sends, in EVERY mode.
    # Jessi never commits to a time on the dealer's behalf without a "Looks Good".
    if is_scheduling:
        needs_approval = True

    # ── Calculate send_at ─────────────────────────────────────────────────────
    delay = get_human_delay(incoming_message)

    # If the customer sent multiple messages recently (rapid-fire), add a short
    # extra buffer so any in-flight messages can arrive before the reply goes out.
    try:
        recent_inbound_count = await db.messages.count_documents({
            "conversation_id": conversation_id,
            "sender":          {"$in": ["contact", "inbound"]},
            "timestamp":       {"$gte": datetime.now(timezone.utc) - timedelta(seconds=30)},
        })
        if recent_inbound_count > 1:
            delay = max(delay, 45)   # Always wait at least 45s when customer is sending fast
            logger.info(f"[AIReply] {recent_inbound_count} rapid messages detected — extended delay to {delay}s")
    except Exception:
        pass

    send_at = datetime.now(timezone.utc) + timedelta(seconds=delay)

    # ── Build queue doc ───────────────────────────────────────────────────────
    now = datetime.now(timezone.utc)

    # Determine the rep's Twilio number NOW (at queue time) so the reply always
    # goes from the correct number — even if the conversation's user_id is stale.
    # Priority: look up by assigned_user_id, then fall back to conversation's user_id.
    rep_send_from = None
    for uid_to_check in [assigned_user_id]:
        if uid_to_check:
            try:
                rep_doc = await db.users.find_one(
                    {"_id": ObjectId(uid_to_check)},
                    {"twilio_number": 1, "mvpline_number": 1}
                )
                rep_send_from = (rep_doc or {}).get("twilio_number") or (rep_doc or {}).get("mvpline_number")
                if rep_send_from:
                    break
            except Exception:
                pass

    queue_doc = {
        "enrollment_id":               enrollment_id,
        "campaign_id":                 campaign_id,
        "contact_id":                  contact_id,
        "conversation_id":             conversation_id,
        "assigned_user_id":            assigned_user_id,
        "rep_twilio_number":           rep_send_from,   # stored at queue time — always correct
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
        "media_urls":                  inventory_media or [],
        "created_at":                  now,
    }

    # ── Cancel any existing pending reply for this conversation ─────────────────
    # When the customer sends multiple messages quickly, this ensures only ONE
    # consolidated reply goes out — the one with the full context of all messages.
    cancelled = await db.ai_reply_queue.update_many(
        {
            "conversation_id": conversation_id,
            "status":          STATUS_PENDING,
        },
        {"$set": {"status": STATUS_CANCELLED, "cancel_reason": "superseded_by_newer_message"}}
    )
    if cancelled.modified_count:
        logger.info(f"[AIReply] Cancelled {cancelled.modified_count} stale pending reply(s) for conv {conversation_id} — consolidating into one response")

    result = await db.ai_reply_queue.insert_one(queue_doc)
    queue_doc["_id"] = str(result.inserted_id)
    queue_doc["id"]  = str(result.inserted_id)

    logger.info(
        f"[AIReply] Queued reply for contact={contact_id} | "
        f"delay={delay}s | needs_approval={needs_approval} | mode={ai_assist_mode}"
    )
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

        # Push notification — only fire for "You're Needed" scenarios, not routine AI replies
        if needs_approval:
            try:
                from routers.push_notifications import send_push_to_user
                asyncio.create_task(send_push_to_user(
                    assigned_user_id,
                    f"You're Needed — {cname}",
                    f"Jessi needs your help. Review the AI draft before it sends.",
                    f"/thread/{conversation_id}",
                    "alert-circle",
                ))
            except Exception:
                pass
    except Exception as e:
        logger.warning(f"[AIReply] Notification failed (non-fatal): {e}")

    return queue_doc


# ── Scheduler functions ───────────────────────────────────────────────────────

async def process_ai_reply_queue():
    """
    Called every 60 seconds by the scheduler.
    Uses atomic find_one_and_update to claim items — prevents double-send race condition.
    Also cancels stale duplicate items for the same conversation before claiming.
    """
    db  = get_db()
    now = datetime.now(timezone.utc)

    # ── Cancel stale duplicates first ─────────────────────────────────────────
    # If multiple pending items exist for the same conversation, keep only the
    # most recently created one. This handles backed-up queues after outages.
    try:
        pipeline = [
            {"$match": {"status": STATUS_PENDING, "requires_approval": False, "send_at": {"$lte": now}}},
            {"$sort": {"created_at": -1}},
            {"$group": {
                "_id": "$conversation_id",
                "latest_id": {"$first": "$_id"},
                "all_ids":   {"$push": "$_id"},
                "count":     {"$sum": 1},
            }},
            {"$match": {"count": {"$gt": 1}}},
        ]
        dupes = await db.ai_reply_queue.aggregate(pipeline).to_list(50)
        for group in dupes:
            stale_ids = [i for i in group["all_ids"] if i != group["latest_id"]]
            if stale_ids:
                await db.ai_reply_queue.update_many(
                    {"_id": {"$in": stale_ids}},
                    {"$set": {"status": STATUS_CANCELLED, "cancel_reason": "stale_duplicate_cancelled"}},
                )
                logger.info(f"[AIReply] Cancelled {len(stale_ids)} stale duplicates for conv {group['_id']}")
    except Exception as dedup_err:
        logger.warning(f"[AIReply] Stale dedup step failed (non-fatal): {dedup_err}")

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
                        _mode = (conv.get("ai_mode") or "").strip()
                        _explicitly_on = _mode in ("auto_reply", "draft_only", "auto_with_approval")
                        ai_off = not _explicitly_on and (
                            conv.get("ai_enabled") is False or
                            _mode in ("off", "")
                        )
                        if ai_off:
                            logger.info(f"[AIReply] Skipping queued item — AI turned off on conversation {item['conversation_id']}")
                            await db.ai_reply_queue.update_one(
                                {"_id": qid}, {"$set": {"status": STATUS_CANCELLED, "cancel_reason": "ai_disabled_by_rep"}}
                            )
                            continue
                except Exception:
                    pass

            # ── Cooldown check — don't send if AI already replied within the last 90 seconds ──
            # This catches the race condition where two replies are queued close together
            # and the first fires before the cancel-and-replace can clean up the second.
            if item.get("conversation_id"):
                try:
                    cooldown_cutoff = now - timedelta(seconds=90)
                    recent_ai_send = await db.messages.find_one({
                        "conversation_id": item["conversation_id"],
                        "sender":          "ai",
                        "ai_generated":    True,
                        "timestamp":       {"$gte": cooldown_cutoff},
                    })
                    if recent_ai_send:
                        logger.info(
                            f"[AIReply] Cooldown — AI already sent to conv {item['conversation_id']} "
                            f"within 90s ({str(recent_ai_send.get('timestamp',''))[:19]}). Cancelling duplicate."
                        )
                        await db.ai_reply_queue.update_one(
                            {"_id": qid},
                            {"$set": {"status": STATUS_CANCELLED, "cancel_reason": "cooldown_90s"}}
                        )
                        continue
                except Exception as cooldown_err:
                    logger.debug(f"[AIReply] Cooldown check failed (non-fatal): {cooldown_err}")

            from services.twilio_service import send_sms

            # Use rep_twilio_number stored at queue time first (most accurate)
            # Fall back to looking up assigned_user_id's number
            rep_twilio_number = item.get("rep_twilio_number")
            if not rep_twilio_number:
                rep_uid = item.get("assigned_user_id")
                if rep_uid:
                    try:
                        rep_doc = await db.users.find_one(
                            {"_id": ObjectId(rep_uid)},
                            {"twilio_number": 1, "mvpline_number": 1}
                        )
                        rep_twilio_number = (rep_doc or {}).get("twilio_number") or (rep_doc or {}).get("mvpline_number")
                    except Exception:
                        pass
            result = await send_sms(phone, item["body"], from_phone=rep_twilio_number, media_urls=item.get("media_urls") or None)
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

            # ── Post-send cleanup: cancel any remaining pending items for this conversation ──
            # Prevents a second reply from firing if it was queued but not yet claimed.
            if item.get("conversation_id"):
                try:
                    cleaned = await db.ai_reply_queue.update_many(
                        {
                            "conversation_id": item["conversation_id"],
                            "status":          STATUS_PENDING,
                            "_id":             {"$ne": qid},
                        },
                        {"$set": {"status": STATUS_CANCELLED, "cancel_reason": "cancelled_after_send"}}
                    )
                    if cleaned.modified_count:
                        logger.info(f"[AIReply] Post-send: cancelled {cleaned.modified_count} pending item(s) for conv {item['conversation_id']}")
                except Exception:
                    pass

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
                "has_media":       bool(item.get("media_urls")),
                "media_urls":      item.get("media_urls") or [],
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

            # Full-auto self-heal: when Jessi answers in full auto_reply mode, she has
            # HANDLED this exchange. Clear the Waiting/You're-Needed state and dismiss any
            # lingering alerts so the conversation stays with Jessi and doesn't look like
            # it was handed to a human. Skip for hot-topic escalations (AI-suspicion) and
            # approval-gated drafts, which genuinely need the rep.
            if (item.get("conversation_id")
                    and item.get("ai_mode_used") == AI_MODE_AUTO_REPLY
                    and not item.get("requires_approval")
                    and not item.get("hot_topic_escalation")):
                try:
                    await db.conversations.update_one(
                        {"_id": ObjectId(item["conversation_id"])},
                        {"$set": {"needs_assistance": False, "unanswered_customer_replies": 0}}
                    )
                    await db.notifications.update_many(
                        {"conversation_id": item["conversation_id"], "type": "you_are_needed", "dismissed": {"$ne": True}},
                        {"$set": {"dismissed": True, "read": True}}
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
            # Push the manager immediately
            try:
                from routers.push_notifications import send_push_to_user
                asyncio.create_task(send_push_to_user(
                    manager_id,
                    f"Escalation: {cname} is waiting",
                    f"{rep_name} hasn't responded in {timeout_min}m. Customer needs a reply.",
                    f"/thread/{item.get('conversation_id', '')}",
                    "alert-circle",
                ))
            except Exception:
                pass
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
    # Use the rep's dedicated number — look up via assigned_user_id or approving user
    rep_twilio_number = None
    try:
        rep_uid = item.get("assigned_user_id") or user_id
        if rep_uid:
            rep_doc = await db.users.find_one(
                {"_id": ObjectId(rep_uid)},
                {"twilio_number": 1, "mvpline_number": 1}
            )
            rep_twilio_number = (rep_doc or {}).get("twilio_number") or (rep_doc or {}).get("mvpline_number")
    except Exception:
        pass
    result = await send_sms(phone, body, from_phone=rep_twilio_number)

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

    # Rep approved the draft — the exchange is handled, so leave the Waiting queue
    # and dismiss any lingering alerts. Jessi stays on and keeps the conversation.
    if item.get("conversation_id"):
        try:
            await db.conversations.update_one(
                {"_id": ObjectId(item["conversation_id"])},
                {"$set": {"needs_assistance": False, "unanswered_customer_replies": 0}}
            )
            await db.notifications.update_many(
                {"conversation_id": item["conversation_id"],
                 "type": {"$in": ["you_are_needed", "ai_draft_approval_required"]},
                 "dismissed": {"$ne": True}},
                {"$set": {"dismissed": True, "read": True}}
            )
        except Exception:
            pass

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


async def send_silence_followups():
    """
    Runs hourly — sends follow-ups at 10 AM in each rep's local timezone.
    Targets conversations where:
      - Customer replied 2+ times then went silent for 20-28h
      - No reply has been sent after their last message
      - Max 2 total follow-ups per conversation
    """
    import pytz
    db  = get_db()
    now_utc = datetime.now(timezone.utc)
    now     = now_utc.replace(tzinfo=None)

    window_start = now - timedelta(hours=28)
    window_end   = now - timedelta(hours=20)

    logger.info("[SilenceFollowup] Hourly check running...")

    candidates = await db.conversations.find({
        "ai_enabled":        True,
        "ai_mode":           {"$nin": ["off", None, ""]},
        "status":            {"$nin": ["closed", "archived"]},
        "last_message_at":   {"$gte": window_start, "$lte": window_end},
        "unanswered_customer_replies": {"$gte": 2},
        "silence_followups_sent": {"$lt": 2},
    }).limit(200).to_list(200)

    sent = 0
    skipped = 0

    for conv in candidates:
        conv_id    = str(conv["_id"])
        contact_id = conv.get("contact_id")
        user_id    = conv.get("user_id")

        if not contact_id or not user_id:
            skipped += 1
            continue

        # ── Check rep's local time — only send during their 10 AM hour ──────────
        try:
            rep = await db.users.find_one({"_id": ObjectId(user_id)}, {"timezone": 1})
            rep_tz_str = (rep or {}).get("timezone", "America/Denver")
            rep_tz     = pytz.timezone(rep_tz_str)
            local_hour = now_utc.astimezone(rep_tz).hour
            if local_hour != 10:
                skipped += 1
                continue   # Not 10 AM for this rep yet — check again next hour
        except Exception:
            # Fall back to Mountain Time if timezone lookup fails
            try:
                mt = pytz.timezone("America/Denver")
                local_hour = now_utc.astimezone(mt).hour
                if local_hour != 10:
                    skipped += 1
                    continue
            except Exception:
                pass

        # ── Verify last message is from customer (not already replied to) ─────
        last_msg = await db.messages.find_one(
            {"conversation_id": conv_id},
            sort=[("timestamp", -1)]
        )
        if not last_msg or last_msg.get("sender") not in ("contact", "inbound"):
            skipped += 1
            continue

        # ── Generate warm follow-up ───────────────────────────────────────────
        try:
            from routers.ai_campaigns import build_clone_system_prompt
            from emergentintegrations.llm.chat import LlmChat, UserMessage
            import os, uuid as _uuid2

            system_prompt = await build_clone_system_prompt(user_id)
            system_prompt += (
                "\n\nThis is a follow-up for someone who replied but then went quiet. "
                "Be warm, brief, zero-pressure — 1 sentence only. "
                "Something like 'Hey, just checking in!' or 'Hope things are going well!' "
                "Never ask a sales question. Make it feel human, not automated."
            )

            recent = await db.messages.find({"conversation_id": conv_id}).sort("timestamp",-1).limit(4).to_list(4)
            recent.reverse()
            ctx = "\n".join(
                f"{'Me' if m.get('sender') in ('user','ai') else 'Them'}: {(m.get('content') or '')[:100]}"
                for m in recent if m.get("content")
            )

            chat = LlmChat(
                api_key=os.environ.get("EMERGENT_LLM_KEY",""),
                session_id=f"followup-{_uuid2.uuid4().hex[:10]}",
                system_message=system_prompt,
            ).with_model("openai","gpt-5.2")

            result = await asyncio.wait_for(
                chat.send_message(UserMessage(text=f"Recent conversation:\n{ctx}\n\nWrite one warm follow-up sentence.")),
                timeout=10.0,
            )
            body = (result.strip() if isinstance(result, str)
                    else result.text.strip() if hasattr(result,"text") else "").strip('"\'')
            body = await clean_ai_text(body, user_id)

            if not body:
                skipped += 1
                continue

            delay = 60 + (sent * 30)  # stagger sends slightly
            await db.ai_reply_queue.insert_one({
                "contact_id":         contact_id,
                "conversation_id":    conv_id,
                "enrollment_id":      "silence_followup",
                "campaign_id":        "",
                "assigned_user_id":   user_id,
                "body":               body,
                "send_at":            now + timedelta(seconds=delay),
                "status":             "pending",
                "requires_approval":  False,
                "ai_mode_used":       conv.get("ai_mode","auto_reply"),
                "is_silence_followup": True,
                "created_at":         now,
            })

            await db.conversations.update_one(
                {"_id": conv["_id"]},
                {"$inc": {"silence_followups_sent": 1},
                 "$set": {"last_silence_followup_at": now}}
            )
            sent += 1

        except Exception as e:
            logger.warning(f"[SilenceFollowup] Failed for conv {conv_id}: {e}")
            skipped += 1

    if sent > 0:
        logger.info(f"[SilenceFollowup] Sent {sent} follow-ups, {skipped} skipped (wrong hour or no gap)")
    return {"sent": sent, "skipped": skipped}
    """
    Daily job — finds conversations where:
      - Customer replied 2+ times (showed genuine interest)
      - Customer's last message was 20-28 hours ago (went silent)
      - No AI or rep reply was sent AFTER that last customer message
      - Not already sent a follow-up today
    Sends a single warm follow-up. Max 2 total follow-ups per conversation.
    """
    db  = get_db()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    window_start = now - timedelta(hours=28)
    window_end   = now - timedelta(hours=20)

    logger.info("[SilenceFollowup] Running daily silence follow-up check...")

    # Find conversations with recent customer activity that then went quiet
    candidates = await db.conversations.find({
        "ai_enabled":        True,
        "ai_mode":           {"$nin": ["off", None, ""]},
        "status":            {"$nin": ["closed", "archived"]},
        "last_message_at":   {"$gte": window_start, "$lte": window_end},
        "unanswered_customer_replies": {"$gte": 2},
        "silence_followups_sent": {"$lt": 2},   # max 2 total
    }).limit(100).to_list(100)

    sent = 0
    skipped = 0

    for conv in candidates:
        conv_id = str(conv["_id"])
        contact_id = conv.get("contact_id")
        user_id    = conv.get("user_id")

        if not contact_id or not user_id:
            skipped += 1
            continue

        # Verify: last message in this conversation is FROM the contact (not already replied)
        last_msg = await db.messages.find_one(
            {"conversation_id": conv_id},
            sort=[("timestamp", -1)]
        )
        if not last_msg or last_msg.get("sender") not in ("contact", "inbound"):
            skipped += 1  # Last message was already a reply — don't follow up
            continue

        # Get contact info for a personalized follow-up
        contact = await db.contacts.find_one({"_id": ObjectId(contact_id)}, {"name":1,"first_name":1,"phone":1})
        first_name = (contact or {}).get("first_name") or (contact or {}).get("name","").split()[0] if contact else ""

        # Build a warm, non-pushy follow-up using the rep's VA
        try:
            from routers.ai_campaigns import build_clone_system_prompt
            from emergentintegrations.llm.chat import LlmChat, UserMessage
            import os, uuid as _uuid2

            system_prompt = await build_clone_system_prompt(user_id)
            system_prompt += (
                "\n\nThis is a follow-up message for someone who replied but then went quiet. "
                "Be warm, brief, and zero-pressure. Do NOT ask a sales question. "
                "Something like 'Hey, just checking in!' or 'Hope things are going well!' "
                "1 sentence max. Make it feel human, not automated."
            )

            # Get last few messages for context
            recent = await db.messages.find({"conversation_id": conv_id}).sort("timestamp",-1).limit(4).to_list(4)
            recent.reverse()
            ctx = "\n".join(f"{'Me' if m.get('sender') in ('user','ai') else 'Them'}: {(m.get('content') or '')[:100]}" for m in recent if m.get("content"))

            chat = LlmChat(
                api_key=os.environ.get("EMERGENT_LLM_KEY",""),
                session_id=f"followup-{_uuid2.uuid4().hex[:10]}",
                system_message=system_prompt,
            ).with_model("openai","gpt-5.2")

            reply_text = await asyncio.wait_for(
                chat.send_message(UserMessage(text=f"Recent conversation:\n{ctx}\n\nWrite one warm follow-up sentence.")),
                timeout=10.0,
            )
            body = (reply_text.strip() if isinstance(reply_text, str)
                    else reply_text.text.strip() if hasattr(reply_text,"text") else "").strip('"\'')
            body = await clean_ai_text(body, user_id)

            if not body:
                skipped += 1
                continue

            # Queue with a small delay so it doesn't feel instant
            delay = 300 + (sent * 60)   # stagger: 5min + 1min per prior send
            await db.ai_reply_queue.insert_one({
                "contact_id":      contact_id,
                "conversation_id": conv_id,
                "enrollment_id":   "silence_followup",
                "campaign_id":     "",
                "assigned_user_id":user_id,
                "body":            body,
                "send_at":         now + timedelta(seconds=delay),
                "status":          "pending",
                "requires_approval": False,
                "ai_mode_used":    conv.get("ai_mode","auto_reply"),
                "is_silence_followup": True,
                "created_at":      now,
            })

            # Mark this conversation so we don't double-send
            await db.conversations.update_one(
                {"_id": conv["_id"]},
                {"$inc": {"silence_followups_sent": 1},
                 "$set": {"last_silence_followup_at": now}}
            )
            sent += 1

        except Exception as e:
            logger.warning(f"[SilenceFollowup] Failed for conv {conv_id}: {e}")
            skipped += 1

    logger.info(f"[SilenceFollowup] Done: {sent} follow-ups queued, {skipped} skipped")
    return {"sent": sent, "skipped": skipped}

