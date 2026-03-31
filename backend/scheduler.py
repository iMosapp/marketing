"""
i'M On Social Campaign Scheduler
Runs background jobs to process date-triggered campaigns and pending campaign step messages.
"""
import asyncio
import logging
import random
import re
from datetime import datetime, timezone, timedelta
from bson import ObjectId
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

# Cache for user/store data to avoid repeated DB lookups within a single scheduler run
_user_cache = {}
_store_cache = {}

_URL_RE = re.compile(r'https?://[^\s<>"\')\]]+')


async def _auto_wrap_urls(media_urls: list, message: str, user_id: str, campaign_id: str, campaign_name: str, step_num: int) -> tuple:
    """Wrap any raw (untracked) URLs in media_urls and message text with tracked short URLs.
    Returns (wrapped_media_urls, wrapped_message)."""
    from routers.short_urls import create_short_url

    def _is_tracked(url):
        return "/api/s/" in url

    def _link_type(url):
        if "youtube.com" in url or "youtu.be" in url:
            return "training_video"
        return "campaign_link"

    url_map = {}

    # Wrap media_urls
    wrapped_media = []
    for url in media_urls:
        if url and not _is_tracked(url):
            if url not in url_map:
                try:
                    result = await create_short_url(
                        original_url=url, link_type=_link_type(url),
                        reference_id=campaign_id, user_id=user_id,
                        metadata={"campaign_id": campaign_id, "campaign_name": campaign_name, "step": step_num, "source": "auto_wrap"},
                    )
                    url_map[url] = result["short_url"]
                except Exception as e:
                    logger.warning(f"[AutoWrap] Failed to wrap {url}: {e}")
                    url_map[url] = url
            wrapped_media.append(url_map[url])
        else:
            wrapped_media.append(url)

    # Wrap URLs in message
    for url in _URL_RE.findall(message):
        if not _is_tracked(url) and url not in url_map:
            try:
                result = await create_short_url(
                    original_url=url, link_type=_link_type(url),
                    reference_id=campaign_id, user_id=user_id,
                    metadata={"campaign_id": campaign_id, "campaign_name": campaign_name, "step": step_num, "source": "auto_wrap"},
                )
                url_map[url] = result["short_url"]
            except Exception as e:
                logger.warning(f"[AutoWrap] Failed to wrap {url}: {e}")

    for old_url, new_url in url_map.items():
        message = message.replace(old_url, new_url)

    return wrapped_media, message


async def resolve_template_variables(db, message: str, contact: dict, user_id: str) -> str:
    """Replace ALL template variables in a message with real values.
    
    Supports: {first_name}, {last_name}, {name}, {contact_name}, {phone},
              {customer_first_name}, {salesman_first_name}, {salesman_name},
              {review_link}, {review_url}, {purchase}
    """
    if not message:
        return message
    
    # Contact info
    contact_first = (contact.get("first_name") or contact.get("contact_name", "").split()[0] if contact.get("contact_name") else "there")
    contact_last = (contact.get("last_name") or (" ".join(contact.get("contact_name", "").split()[1:]) if contact.get("contact_name") else ""))
    contact_full = f"{contact_first} {contact_last}".strip() or "there"
    
    message = message.replace("{first_name}", contact_first)
    message = message.replace("{last_name}", contact_last)
    message = message.replace("{name}", contact_first)
    message = message.replace("{contact_name}", contact_full)
    message = message.replace("{customer_first_name}", contact_first)
    message = message.replace("{phone}", contact.get("phone", ""))
    
    # Salesman (user) info - fetch once and cache
    if "{salesman_first_name}" in message or "{salesman_name}" in message or "{review_link}" in message or "{review_url}" in message:
        if user_id not in _user_cache:
            _user_cache[user_id] = await db.users.find_one({"_id": ObjectId(user_id)}) or {}
        user_doc = _user_cache[user_id]
        
        user_name = user_doc.get("name", "")
        user_first = user_name.split()[0] if user_name else ""
        message = message.replace("{salesman_first_name}", user_first)
        message = message.replace("{salesman_name}", user_name)
        
        # Review link
        if "{review_link}" in message or "{review_url}" in message:
            review_url = user_doc.get("review_url", "") or ""
            if not review_url:
                store_id = user_doc.get("store_id")
                if store_id:
                    store_key = str(store_id)
                    if store_key not in _store_cache:
                        _store_cache[store_key] = await db.stores.find_one({"_id": ObjectId(store_id)}) or {}
                    store = _store_cache[store_key]
                    rl = store.get("review_links", {})
                    review_url = rl.get("google", "") or rl.get("yelp", "") or rl.get("facebook", "") or ""
            message = message.replace("{review_link}", review_url)
            message = message.replace("{review_url}", review_url)
    
    # Purchase info
    if "{purchase}" in message:
        purchase = contact.get("purchase", "") or contact.get("vehicle", "") or contact.get("product", "") or "purchase"
        message = message.replace("{purchase}", purchase)
    
    return message

scheduler = AsyncIOScheduler()

# Track scheduler state for health endpoint
_scheduler_state = {
    "last_date_trigger_run": None,
    "last_campaign_step_run": None,
    "last_lifecycle_scan_run": None,
    "date_trigger_results": {},
    "campaign_step_results": {},
    "lifecycle_scan_results": {},
    "errors": [],
}


def get_scheduler_state() -> dict:
    return {**_scheduler_state, "running": scheduler.running}


def safe_job(func):
    """Wraps any async scheduler job so unhandled exceptions are logged
    but NEVER propagate up to crash the main server process."""
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logger.error(f"[Scheduler] CAUGHT unhandled error in {func.__name__}: {e}", exc_info=True)
            _scheduler_state["errors"].append({
                "job": func.__name__,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            # Keep only last 20 errors
            if len(_scheduler_state["errors"]) > 20:
                _scheduler_state["errors"] = _scheduler_state["errors"][-20:]
    wrapper.__name__ = func.__name__
    return wrapper


async def run_daily_lifecycle_scan():
    """Daily job: scan all users for tenure milestones, inactivity, and activity levels."""
    logger.info("[Scheduler] Starting daily lifecycle scan...")
    try:
        from routers.user_lifecycle import run_lifecycle_scan
        results = await run_lifecycle_scan()
        _scheduler_state["last_lifecycle_scan_run"] = datetime.now(timezone.utc).isoformat()
        _scheduler_state["lifecycle_scan_results"] = {
            **results,
            "ran_at": datetime.now(timezone.utc).isoformat(),
        }
        logger.info(f"[Scheduler] Lifecycle scan complete: {results}")
    except Exception as e:
        msg = f"[Scheduler] Error in lifecycle scan: {e}"
        logger.error(msg)
        _scheduler_state["errors"] = (_scheduler_state["errors"] + [msg])[-20:]


async def send_scheduled_reports():
    """Check for users who want reports delivered today and send them."""
    logger.info("[Scheduler] Checking for scheduled report deliveries...")
    try:
        from routers.database import get_db
        db = get_db()
        today = datetime.now(timezone.utc)
        dow = today.weekday()  # 0=Mon
        dom = today.day

        prefs_cursor = db.report_preferences.find({
            "email_enabled": True,
            "frequency": {"$in": ["daily", "weekly", "monthly"]},
        })
        sent = 0
        async for pref in prefs_cursor:
            freq = pref.get("frequency")
            should_send = False
            if freq == "daily":
                should_send = True
            elif freq == "weekly" and pref.get("day_of_week", 1) == dow:
                should_send = True
            elif freq == "monthly" and pref.get("day_of_month", 1) == dom:
                should_send = True

            if should_send:
                uid = pref["user_id"]
                email = pref.get("email_to")
                try:
                    from routers.reports import send_report_email
                    if freq == "daily":
                        start = (today - timedelta(days=1)).strftime("%Y-%m-%d")
                    elif freq == "weekly":
                        start = (today - timedelta(days=7)).strftime("%Y-%m-%d")
                    else:
                        start = (today - timedelta(days=30)).strftime("%Y-%m-%d")
                    end = today.strftime("%Y-%m-%d")
                    await send_report_email(uid, start, end, team=True, recipient_email=email)
                    sent += 1
                    logger.info(f"[Scheduler] Sent {freq} report to {email or uid}")
                except Exception as e:
                    logger.error(f"[Scheduler] Failed report for {uid}: {e}")

        logger.info(f"[Scheduler] Scheduled reports: {sent} sent")
    except Exception as e:
        msg = f"[Scheduler] Error in scheduled reports: {e}"
        logger.error(msg)
        _scheduler_state["errors"] = (_scheduler_state["errors"] + [msg])[-20:]


async def process_all_date_triggers():
    """Daily job: iterate all users with active date-trigger configs and fire messages."""
    from routers.database import get_db
    logger.info("[Scheduler] Starting daily date-trigger sweep...")

    db = get_db()
    if db is None:
        logger.error("[Scheduler] DB not available")
        return

    try:
        # Find distinct user_ids that have at least one enabled config
        pipeline = [
            {"$match": {"enabled": True}},
            {"$group": {"_id": "$user_id"}},
        ]
        user_docs = await db.date_trigger_configs.aggregate(pipeline).to_list(500)
        user_ids = [d["_id"] for d in user_docs]

        logger.info(f"[Scheduler] Found {len(user_ids)} users with active date triggers")

        total_sent = 0
        for user_id in user_ids:
            try:
                result = await _run_date_triggers_for_user(db, user_id)
                total_sent += result
            except Exception as e:
                msg = f"[Scheduler] Error processing date triggers for user {user_id}: {e}"
                logger.error(msg)
                _scheduler_state["errors"] = (_scheduler_state["errors"] + [msg])[-20:]

        _scheduler_state["last_date_trigger_run"] = datetime.now(timezone.utc).isoformat()
        _scheduler_state["date_trigger_results"] = {
            "users_processed": len(user_ids),
            "messages_sent": total_sent,
            "ran_at": datetime.now(timezone.utc).isoformat(),
        }
        logger.info(f"[Scheduler] Date-trigger sweep complete. {total_sent} messages sent for {len(user_ids)} users.")
    except Exception as e:
        logger.error(f"[Scheduler] Fatal error in date-trigger sweep: {e}")
        _scheduler_state["errors"] = (_scheduler_state["errors"] + [str(e)])[-20:]


async def _run_date_triggers_for_user(db, user_id: str) -> int:
    """Process all date triggers for a single user. Returns count of messages sent."""
    import os
    import pytz
    from routers.database import get_data_filter
    from routers.date_triggers import AVAILABLE_HOLIDAYS

    user = await db.users.find_one({"_id": __import__("bson").ObjectId(user_id)})
    if not user:
        return 0

    user_tz = user.get("timezone", "America/Denver")
    try:
        tz = pytz.timezone(user_tz)
        local_now = datetime.now(tz)
    except Exception:
        local_now = datetime.now(timezone.utc)

    today_month = local_now.month
    today_day = local_now.day

    configs = await db.date_trigger_configs.find(
        {"user_id": user_id, "enabled": True}
    ).to_list(100)

    if not configs:
        return 0

    base_filter = await get_data_filter(user_id)
    sent_count = 0

    for config in configs:
        trigger_type = config["trigger_type"]
        template = config.get("message_template", "")
        delivery = config.get("delivery_method", "sms")

        if not template:
            continue

        contacts_to_message = []

        if trigger_type in ("birthday", "anniversary", "sold_date"):
            field_map = {
                "birthday": "birthday",
                "anniversary": "anniversary",
                "sold_date": "date_sold",
            }
            date_field = field_map[trigger_type]

            contacts = await db.contacts.find(
                {**base_filter, date_field: {"$exists": True, "$ne": None}}
            ).to_list(1000)

            for contact in contacts:
                dt = contact.get(date_field)
                if dt and isinstance(dt, datetime):
                    if dt.month == today_month and dt.day == today_day:
                        # Skip contacts that have this automation disabled
                        disabled = contact.get("disabled_automations", [])
                        if trigger_type in disabled:
                            continue
                        contacts_to_message.append(contact)

        elif trigger_type.startswith("holiday_"):
            holiday_id = config.get("holiday_id") or trigger_type.replace("holiday_", "")
            holiday = next((h for h in AVAILABLE_HOLIDAYS if h["id"] == holiday_id), None)
            if holiday and holiday["month"] == today_month and holiday["day"] == today_day:
                contacts = await db.contacts.find(
                    {**base_filter, "tags": {"$in": ["Holiday", "Holidays", "holiday", "holidays"]}}
                ).to_list(1000)
                contacts_to_message = contacts

        for contact in contacts_to_message:
            contact_id = str(contact["_id"])
            contact_name = f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip()

            today_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
            already_sent = await db.date_trigger_log.find_one({
                "user_id": user_id,
                "contact_id": contact_id,
                "trigger_type": trigger_type,
                "sent_at": {"$gte": today_start.isoformat()},
            })
            if already_sent:
                continue

            message = await resolve_template_variables(db, template, contact, user_id)

            send_result = {"sms": False, "email": False}

            # Auto-create a birthday card if this is a birthday trigger
            if trigger_type == "birthday" and config.get("include_birthday_card", True):
                try:
                    from routers.congrats_cards import auto_create_card
                    bday_result = await auto_create_card(user_id, contact_id, card_type="birthday")
                    if bday_result and bday_result.get("short_url"):
                        message += f"\n\nView your birthday card: {bday_result['short_url']}"
                        logger.info(f"[Scheduler] Birthday card created for {contact_name}: {bday_result.get('card_id')}")
                    elif bday_result and bday_result.get("already_exists"):
                        existing_card = await db.congrats_cards.find_one(
                            {"card_id": bday_result["card_id"]}, {"short_url": 1}
                        )
                        if existing_card and existing_card.get("short_url"):
                            message += f"\n\nView your birthday card: {existing_card['short_url']}"
                except Exception as e:
                    logger.error(f"[Scheduler] Birthday card creation failed for {contact_name}: {e}")

            # Friendly trigger labels
            trigger_labels = {
                "birthday": "Birthday",
                "anniversary": "Anniversary",
                "sold_date": "Sold Date Anniversary",
                "holiday_thanksgiving": "Thanksgiving",
                "holiday_christmas": "Christmas",
                "holiday_new_years": "New Year's",
            }
            trigger_label = trigger_labels.get(trigger_type, trigger_type.replace("_", " ").title())

            # Create a TASK on the user's to-do list
            await db.tasks.insert_one({
                "user_id": user_id,
                "contact_id": contact_id,
                "type": "date_trigger",
                "title": f"{trigger_label}: Send {delivery.upper()} to {contact_name}",
                "description": message,
                "due_date": datetime.now(timezone.utc),
                "priority": "high",
                "completed": False,
                "source": "date_trigger",
                "trigger_type": trigger_type,
                "channel": delivery,
                "contact_phone": contact.get("phone", ""),
                "contact_email": contact.get("email", ""),
                "created_at": datetime.now(timezone.utc),
            })

            # Create a notification (bell alert)
            await db.notifications.insert_one({
                "user_id": user_id,
                "type": "date_trigger",
                "title": f"{trigger_label} Today",
                "message": f"It's {contact_name}'s {trigger_label.lower()} today! Send them a message.",
                "contact_name": contact_name,
                "contact_id": contact_id,
                "trigger_type": trigger_type,
                "action_required": True,
                "read": False,
                "dismissed": False,
                "created_at": datetime.now(timezone.utc),
            })

            # Also queue the message for tracking
            if delivery in ("sms", "both") and contact.get("phone"):
                try:
                    await db.messages.insert_one({
                        "conversation_id": f"auto_{user_id}_{contact_id}",
                        "sender": "user",
                        "content": message,
                        "timestamp": datetime.now(timezone.utc),
                        "auto_sent": False,
                        "trigger_type": trigger_type,
                        "pending_manual_send": True,
                    })
                    send_result["sms"] = True
                except Exception as e:
                    logger.error(f"[Scheduler] SMS queue failed for {contact_name}: {e}")

            if delivery in ("email", "both") and contact.get("email"):
                try:
                    resend_key = os.environ.get("RESEND_API_KEY")
                    if resend_key:
                        import resend
                        resend.api_key = resend_key
                        sender_name = user.get('name', "i'M On Social")
                        await asyncio.to_thread(resend.Emails.send, {
                            "from": f"{sender_name} <{os.environ.get('SENDER_EMAIL', 'notifications@send.imonsocial.com')}>",
                            "to": contact["email"],
                            "reply_to": user.get('email', 'support@imonsocial.com'),
                            "subject": f"A message from {sender_name}",
                            "html": f"<div style='font-family:sans-serif;max-width:500px;margin:0 auto;padding:20px;'><p>{message}</p></div>",
                        })
                        send_result["email"] = True
                except Exception as e:
                    logger.error(f"[Scheduler] Email failed for {contact_name}: {e}")

            await db.date_trigger_log.insert_one({
                "user_id": user_id,
                "contact_id": contact_id,
                "contact_name": contact_name,
                "trigger_type": trigger_type,
                "delivery_method": delivery,
                "message_preview": message[:100],
                "send_result": send_result,
                "sent_at": datetime.now(timezone.utc).isoformat(),
            })
            sent_count += 1

    return sent_count


async def process_pending_campaign_steps():
    """Periodic job: find active enrollments with due messages and advance them.
    Handles two delivery modes:
    - automated: Logs message + queues for Twilio delivery (or mock)
    - manual: Creates a notification for the user to send manually
    AI-enabled campaigns generate personalized content per step.
    """
    from routers.database import get_db
    from routers.campaigns import calculate_next_send_date

    logger.info("[Scheduler] Processing pending campaign steps...")

    db = get_db()
    if db is None:
        logger.error("[Scheduler] DB not available")
        return

    now = datetime.now(timezone.utc)

    try:
        pending = await db.campaign_enrollments.find({
            "status": "active",
            "next_send_at": {"$lte": now},
        }).to_list(500)

        logger.info(f"[Scheduler] Found {len(pending)} pending campaign messages")

        processed = 0
        for enrollment in pending:
            try:
                campaign = await db.campaigns.find_one(
                    {"_id": __import__("bson").ObjectId(enrollment["campaign_id"])}
                )
                if not campaign or not campaign.get("active", False):
                    continue

                sequences = campaign.get("sequences", [])
                current_step = enrollment.get("current_step", 1)

                if current_step > len(sequences):
                    await db.campaign_enrollments.update_one(
                        {"_id": enrollment["_id"]},
                        {"$set": {"status": "completed"}},
                    )
                    continue

                step = sequences[current_step - 1]
                message_content = step.get("message_template", "") or step.get("message", "")
                channel = step.get("channel", "sms")
                ai_generated = step.get("ai_generated", False) or campaign.get("ai_enabled", False)
                delivery_mode = campaign.get("delivery_mode", "manual")

                contact_id = enrollment.get("contact_id", "")
                user_id = enrollment.get("user_id", "")
                contact_phone = enrollment.get("contact_phone", "")

                # Determine whether to use AI for this step
                # Campaign's ai_enabled toggle is the primary control
                campaign_ai_enabled = campaign.get("ai_enabled", False)
                use_ai = campaign_ai_enabled and ai_generated
                if campaign_ai_enabled:
                    # Check store-level config for overrides only when campaign has AI on
                    try:
                        from routers.campaign_config import get_effective_config
                        user_doc = await db.users.find_one({"_id": ObjectId(user_id)}, {"store_id": 1, "organization_id": 1})
                        if user_doc:
                            config = await get_effective_config(
                                user_id=user_id,
                                store_id=user_doc.get("store_id"),
                                org_id=user_doc.get("organization_id"),
                            )
                            msg_mode = config.get("message_mode", "ai_suggested")
                            if msg_mode == "template":
                                use_ai = False  # Store forces templates only
                            elif msg_mode == "ai_suggested":
                                use_ai = True  # AI for all steps when campaign AI is on
                            # "hybrid" respects the step's own ai_generated flag
                    except Exception as e:
                        logger.warning(f"[Scheduler] Campaign config lookup failed: {e}")

                # AI message generation if enabled
                if use_ai and contact_id and user_id:
                    try:
                        from routers.ai_campaigns import generate_campaign_message
                        ai_data = {
                            "step_context": step.get("step_context", f"Step {current_step} of {campaign.get('name', '')}"),
                            "channel": channel,
                            "campaign_name": campaign.get("name", ""),
                            "template_hint": message_content,
                        }
                        ai_result = await generate_campaign_message(user_id, contact_id, ai_data)
                        if ai_result.get("success"):
                            message_content = ai_result["message"]
                            logger.info(f"[Scheduler] AI generated message for step {current_step}")
                    except Exception as e:
                        logger.warning(f"[Scheduler] AI generation failed, using template: {e}")

                # Build relationship intelligence brief for the task
                relationship_brief = ""
                try:
                    from services.relationship_intel import build_relationship_brief
                    brief = await build_relationship_brief(user_id, contact_id)
                    relationship_brief = brief.get("human_summary", "")
                except Exception as e:
                    logger.warning(f"[Scheduler] Relationship intel failed: {e}")

                if not message_content:
                    message_content = f"Hi {enrollment.get('contact_name', 'there')}!"

                # ===== DELIVERY =====
                if delivery_mode == "automated":
                    # AUTOMATED: Log the message and queue for sending
                    conv_id = f"campaign_{user_id}_{contact_id}"
                    await db.messages.insert_one({
                        "conversation_id": conv_id,
                        "sender": "user",
                        "content": message_content,
                        "timestamp": now,
                        "auto_sent": True,
                        "campaign_id": enrollment["campaign_id"],
                        "campaign_step": current_step,
                        "channel": channel,
                        "user_id": user_id,
                        "contact_id": contact_id,
                    })

                    # Log contact event
                    event_type = "email_sent" if channel == "email" else "sms_sent"
                    await db.contact_events.insert_one({
                        "event_type": event_type,
                        "user_id": user_id,
                        "contact_id": contact_id,
                        "org_id": enrollment.get("org_id", ""),
                        "description": f"Campaign '{campaign.get('name', '')}' step {current_step}",
                        "timestamp": now,
                        "auto_campaign": True,
                    })

                    logger.info(
                        f"[Scheduler] AUTO-SENT step {current_step} to {enrollment.get('contact_name', 'unknown')} via {channel}"
                    )

                else:
                    # MANUAL: Create a pending send + task for the user's to-do list
                    action_type = step.get("action_type", "message")
                    contact_display = enrollment.get("contact_name", "contact")
                    idem_key = f"campaign_{enrollment['campaign_id']}_{contact_id}_{current_step}"

                    # Check if task already exists for this step (prevents stuck enrollments)
                    existing_task = await db.tasks.find_one({"idempotency_key": idem_key})
                    if existing_task:
                        # Task already exists (from a previous partial run or immediate processing)
                        # If it's still pending, just skip. If completed, still advance the enrollment.
                        logger.info(
                            f"[Scheduler] Task already exists for step {current_step} (status={existing_task.get('status')}), advancing enrollment"
                        )
                    else:
                        # Auto-wrap raw URLs in media and message for click tracking
                        raw_media = step.get("media_urls", [])
                        try:
                            wrapped_media, wrapped_message = await _auto_wrap_urls(
                                raw_media, message_content, user_id,
                                enrollment["campaign_id"], campaign.get("name", ""), current_step,
                            )
                        except Exception as e:
                            logger.warning(f"[Scheduler] Auto-wrap failed, using raw URLs: {e}")
                            wrapped_media, wrapped_message = raw_media, message_content

                        # Create pending send record
                        pending_result = await db.campaign_pending_sends.insert_one({
                            "user_id": user_id,
                            "contact_id": contact_id,
                            "contact_name": enrollment.get("contact_name", ""),
                            "contact_phone": contact_phone,
                            "contact_email": enrollment.get("contact_email", ""),
                            "campaign_id": enrollment["campaign_id"],
                            "campaign_name": campaign.get("name", ""),
                            "step": current_step,
                            "channel": channel,
                            "message": wrapped_message,
                            "media_urls": wrapped_media,
                            "relationship_brief": relationship_brief,
                            "ai_generated": bool(ai_generated),
                            "step_context": step.get("step_context", ""),
                            "status": "pending",
                            "created_at": now,
                        })

                        if action_type == "send_card":
                            card_type = step.get("card_type", "congrats")
                            task_title = f"Send {card_type.title()} Card to {contact_display}"
                            task_desc = f"Campaign '{campaign.get('name', '')}' step {current_step}: Send a {card_type} card to {contact_display}."
                        else:
                            task_title = f"Send {channel.upper()} to {contact_display}"
                            task_desc = f"Campaign '{campaign.get('name', '')}' step {current_step}: {message_content[:200]}"

                        # Replace ALL template variables in the message
                        clean_message = await resolve_template_variables(db, message_content, {
                            "first_name": enrollment.get("contact_name", "").split()[0] if enrollment.get("contact_name") else "there",
                            "last_name": enrollment.get("contact_name", "").split()[-1] if enrollment.get("contact_name") else "",
                            "contact_name": enrollment.get("contact_name", ""),
                            "phone": enrollment.get("contact_phone", ""),
                        }, user_id)

                        try:
                            await db.tasks.insert_one({
                                "user_id": user_id,
                                "contact_id": contact_id,
                                "contact_name": enrollment.get("contact_name", ""),
                                "contact_phone": enrollment.get("contact_phone", ""),
                                "type": "campaign_send",
                                "title": task_title,
                                "description": task_desc,
                                "suggested_message": clean_message,
                                "relationship_brief": relationship_brief,
                                "ai_generated": bool(ai_generated),
                                "action_type": "card" if action_type == "send_card" else ("email" if channel == "email" else "text"),
                                "due_date": now,
                                "priority": "high",
                                "priority_order": 1,
                                "status": "pending",
                                "completed": False,
                                "source": "campaign",
                                "campaign_id": enrollment["campaign_id"],
                                "campaign_name": campaign.get("name", ""),
                                "pending_send_id": str(pending_result.inserted_id),
                                "channel": channel,
                                "created_at": now,
                                "idempotency_key": idem_key,
                            })
                        except Exception as task_err:
                            # DuplicateKeyError or other - log but continue to advance enrollment
                            logger.warning(f"[Scheduler] Task insert failed (will still advance): {task_err}")

                        # Create a notification (bell alert)
                        await db.notifications.insert_one({
                            "user_id": user_id,
                            "type": "campaign_send",
                            "title": f"Campaign: {campaign.get('name', '')}",
                            "message": f"Time to send step {current_step} to {contact_display}",
                            "contact_name": enrollment.get("contact_name", ""),
                            "contact_id": contact_id,
                            "campaign_id": enrollment["campaign_id"],
                            "pending_send_step": current_step,
                            "action_required": True,
                            "read": False,
                            "dismissed": False,
                            "created_at": now,
                        })

                        logger.info(
                            f"[Scheduler] MANUAL task + notification created for step {current_step} to {enrollment.get('contact_name', 'unknown')}"
                        )

                # Advance enrollment
                # For manual mode: mark as "pending" (user still needs to send)
                # For automated mode: mark as "sent" (message was auto-delivered)
                is_manual = delivery_mode == "manual"
                msg_record = {
                    "step": current_step,
                    "content": message_content[:100],
                    "channel": channel,
                    "delivery_mode": delivery_mode,
                }
                if is_manual:
                    msg_record["status"] = "pending"
                    msg_record["queued_at"] = now
                else:
                    msg_record["status"] = "sent"
                    msg_record["sent_at"] = now

                if current_step < len(sequences):
                    next_step = sequences[current_step]
                    next_send = calculate_next_send_date(next_step)

                    # Only randomize send time for daily+ delays (not hourly)
                    # This prevents breaking campaigns with short intervals
                    step_delay_hours = next_step.get('delay_hours', 0)
                    step_delay_days = next_step.get('delay_days', 0)
                    step_delay_months = next_step.get('delay_months', 0)
                    is_daily_or_longer = step_delay_days > 0 or step_delay_months > 0

                    if is_daily_or_longer:
                        try:
                            import pytz
                            user_doc = await db.users.find_one({"_id": __import__("bson").ObjectId(user_id)})
                            user_tz_str = (user_doc or {}).get("timezone", "America/Denver")
                            user_tz = pytz.timezone(user_tz_str)
                            # Properly convert naive UTC datetime to local time
                            utc_aware = next_send.replace(tzinfo=timezone.utc)
                            local_send = utc_aware.astimezone(user_tz)
                            random_hour = random.randint(10, 11)
                            random_minute = random.randint(0, 59)
                            local_send = local_send.replace(hour=random_hour, minute=random_minute, second=0)
                            candidate = local_send.astimezone(timezone.utc).replace(tzinfo=None)
                            # Ensure the randomized time is in the future
                            now_naive = datetime.utcnow()
                            if candidate <= now_naive:
                                candidate = candidate + timedelta(days=1)
                            next_send = candidate
                        except Exception:
                            pass

                    update_set = {
                        "current_step": current_step + 1,
                        "next_send_at": next_send,
                    }
                    if not is_manual:
                        update_set["last_sent_at"] = now

                    await db.campaign_enrollments.update_one(
                        {"_id": enrollment["_id"]},
                        {
                            "$set": update_set,
                            "$push": {"messages_sent": msg_record},
                        },
                    )
                else:
                    update_set = {
                        "current_step": current_step + 1,
                        "next_send_at": None,
                        "status": "completed",
                    }
                    if not is_manual:
                        update_set["last_sent_at"] = now

                    await db.campaign_enrollments.update_one(
                        {"_id": enrollment["_id"]},
                        {
                            "$set": update_set,
                            "$push": {"messages_sent": msg_record},
                        },
                    )

                processed += 1

            except Exception as e:
                msg = f"[Scheduler] Error processing enrollment {enrollment.get('_id')}: {e}"
                logger.error(msg)
                _scheduler_state["errors"] = (_scheduler_state["errors"] + [msg])[-20:]

        _scheduler_state["last_campaign_step_run"] = datetime.now(timezone.utc).isoformat()
        _scheduler_state["campaign_step_results"] = {
            "pending_found": len(pending),
            "processed": processed,
            "ran_at": datetime.now(timezone.utc).isoformat(),
        }
        logger.info(f"[Scheduler] Campaign steps complete. Processed {processed}/{len(pending)}.")
        _user_cache.clear()
        _store_cache.clear()
    except Exception as e:
        logger.error(f"[Scheduler] Fatal error in campaign step processing: {e}")
        _scheduler_state["errors"] = (_scheduler_state["errors"] + [str(e)])[-20:]


async def generate_daily_system_tasks():
    """Daily job: generate system tasks (dormant contacts, birthdays, anniversaries) for all active users."""
    from routers.database import get_db
    logger.info("[Scheduler] Generating daily system tasks...")
    db = get_db()
    if db is None:
        return

    try:
        # Get all active users
        users = await db.users.find(
            {"is_active": True, "status": {"$ne": "deactivated"}},
            {"_id": 1}
        ).to_list(1000)

        total_created = 0
        for u in users:
            uid = str(u["_id"])
            try:
                from routers.tasks import generate_system_tasks
                result = await generate_system_tasks(uid)
                total_created += result.get("created", 0) if isinstance(result, dict) else 0
            except Exception as e:
                logger.error(f"[Scheduler] System task gen failed for {uid}: {e}")

        _scheduler_state["last_system_tasks_run"] = datetime.now(timezone.utc).isoformat()
        logger.info(f"[Scheduler] System tasks: {total_created} created for {len(users)} users")
    except Exception as e:
        logger.error(f"[Scheduler] Fatal error in system task gen: {e}")


async def send_weekly_power_rankings_job():
    """Weekly job to send power rankings emails to all teams."""
    from routers.database import get_db
    from services.power_rankings import send_weekly_power_rankings
    db = get_db()
    try:
        count = await send_weekly_power_rankings(db)
        logger.info(f"[Scheduler] Power Rankings: sent {count} emails")
    except Exception as e:
        logger.error(f"[Scheduler] Power Rankings error: {e}")


async def expire_recent_tags():
    """Daily job: remove 'Recent' tag from contacts where it was applied more than 14 days ago."""
    logger.info("[Scheduler] Starting Recent tag expiry scan...")
    try:
        from routers.database import get_db
        db = get_db()

        cutoff = datetime.now(timezone.utc) - timedelta(days=14)

        # Find contacts with 'Recent' tag applied before the cutoff
        expired = await db.contacts.find(
            {
                "tags": "Recent",
                "$or": [
                    {"tag_timestamps.Recent": {"$lt": cutoff}},
                    # If no timestamp recorded, use created_at as fallback
                    {"tag_timestamps.Recent": {"$exists": False}, "created_at": {"$lt": cutoff}},
                ],
            },
            {"_id": 1, "first_name": 1, "last_name": 1},
        ).to_list(500)

        removed = 0
        for c in expired:
            await db.contacts.update_one(
                {"_id": c["_id"]},
                {
                    "$pull": {"tags": "Recent"},
                    "$unset": {"tag_timestamps.Recent": ""},
                },
            )
            removed += 1

        _scheduler_state["last_recent_tag_expiry_run"] = datetime.now(timezone.utc).isoformat()
        _scheduler_state["recent_tag_expiry_results"] = {"removed": removed, "ran_at": datetime.now(timezone.utc).isoformat()}
        logger.info(f"[Scheduler] Recent tag expiry complete: removed from {removed} contacts")
    except Exception as e:
        msg = f"[Scheduler] Error in Recent tag expiry: {e}"
        logger.error(msg)
        _scheduler_state["errors"] = (_scheduler_state["errors"] + [msg])[-20:]


async def run_monthly_health_reports_job():
    """Wrapper for the scheduler — calls the account_health module's function."""
    logger.info("[Scheduler] Running monthly health reports check...")
    try:
        from routers.account_health import run_monthly_health_reports
        sent = await run_monthly_health_reports()
        _scheduler_state["last_health_report_run"] = datetime.now(timezone.utc).isoformat()
        _scheduler_state["health_report_results"] = {"sent": sent, "ran_at": datetime.now(timezone.utc).isoformat()}
        logger.info(f"[Scheduler] Monthly health reports: {sent} sent")
    except Exception as e:
        msg = f"[Scheduler] Error in monthly health reports: {e}"
        logger.error(msg)
        _scheduler_state["errors"] = (_scheduler_state["errors"] + [msg])[-20:]


async def run_monthly_partner_invoices_job():
    """Generate monthly invoices for all active white-label partners on the 1st."""
    now = datetime.now(timezone.utc)
    if now.day != 1:
        return
    logger.info("[Scheduler] Running monthly partner invoice generation...")
    try:
        from routers.partner_invoices import generate_monthly_invoices
        result = await generate_monthly_invoices()
        logger.info(f"[Scheduler] Monthly invoices: {result}")
    except Exception as e:
        msg = f"[Scheduler] Error in monthly invoice generation: {e}"
        logger.error(msg)
        _scheduler_state["errors"] = (_scheduler_state["errors"] + [msg])[-20:]



async def process_sold_deliveries_job():
    """Wrapper for the scheduler — processes queued sold workflow deliveries."""
    logger.info("[Scheduler] Processing queued sold deliveries...")
    try:
        from routers.sold_workflow import process_queued_sold_deliveries
        await process_queued_sold_deliveries()
    except Exception as e:
        msg = f"[Scheduler] Error in sold deliveries: {e}"
        logger.error(msg)
        _scheduler_state["errors"] = (_scheduler_state["errors"] + [msg])[-20:]



def start_scheduler():
    """Register jobs and start the APScheduler."""
    if scheduler.running:
        logger.warning("[Scheduler] Already running, skipping start.")
        return

    # Daily at 8 AM UTC  - process date triggers (birthdays, anniversaries, holidays)
    scheduler.add_job(
        safe_job(process_all_date_triggers),
        CronTrigger(hour=8, minute=0),
        id="daily_date_triggers",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    # Daily at 6 AM UTC  - lifecycle scan (tenure tags, inactivity detection, milestone messages)
    scheduler.add_job(
        safe_job(run_daily_lifecycle_scan),
        CronTrigger(hour=6, minute=0),
        id="daily_lifecycle_scan",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    # Daily at 7 AM UTC  - send scheduled reports
    scheduler.add_job(
        safe_job(send_scheduled_reports),
        CronTrigger(hour=7, minute=0),
        id="daily_report_delivery",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    # Every 15 minutes  - process pending campaign step messages
    scheduler.add_job(
        safe_job(process_pending_campaign_steps),
        IntervalTrigger(minutes=15),
        id="campaign_step_processor",
        replace_existing=True,
        misfire_grace_time=300,
    )

    # Daily at 5:30 AM UTC - generate system tasks (dormant contacts, birthdays, anniversaries)
    scheduler.add_job(
        safe_job(generate_daily_system_tasks),
        CronTrigger(hour=5, minute=30),
        id="daily_system_tasks",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    # Weekly Monday at 9 AM UTC - send power rankings emails
    scheduler.add_job(
        safe_job(send_weekly_power_rankings_job),
        CronTrigger(day_of_week='mon', hour=9, minute=0),
        id="weekly_power_rankings",
        replace_existing=True,
        misfire_grace_time=7200,
    )

    # Daily at 4 AM UTC - expire "Recent" tags older than 14 days
    scheduler.add_job(
        safe_job(expire_recent_tags),
        CronTrigger(hour=4, minute=0),
        id="daily_recent_tag_expiry",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    # Daily at 10 PM UTC - check if last day of month → send scheduled health reports
    scheduler.add_job(
        safe_job(run_monthly_health_reports_job),
        CronTrigger(hour=22, minute=0),
        id="monthly_health_reports",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    # Every 5 minutes - process queued sold workflow deliveries
    scheduler.add_job(
        safe_job(process_sold_deliveries_job),
        IntervalTrigger(minutes=5),
        id="sold_delivery_processor",
        replace_existing=True,
        misfire_grace_time=120,
    )

    # Daily at 6 AM UTC on the 1st - generate monthly partner invoices
    scheduler.add_job(
        safe_job(run_monthly_partner_invoices_job),
        CronTrigger(day=1, hour=6, minute=30),
        id="monthly_partner_invoices",
        replace_existing=True,
        misfire_grace_time=7200,
    )

    scheduler.start()
    logger.info("[Scheduler] Started with 10 jobs: daily_system_tasks (5:30 UTC), daily_lifecycle_scan (6:00 UTC), daily_report_delivery (7:00 UTC), daily_date_triggers (8:00 UTC), campaign_step_processor (every 15m), weekly_power_rankings (Mon 9:00 UTC), daily_recent_tag_expiry (4:00 UTC), monthly_health_reports (22:00 UTC), sold_delivery_processor (every 5m), monthly_partner_invoices (1st @ 6:30 UTC)")


def stop_scheduler():
    """Gracefully shut down the scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("[Scheduler] Shut down.")
