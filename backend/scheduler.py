"""
iMOs Campaign Scheduler
Runs background jobs to process date-triggered campaigns and pending campaign step messages.
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

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
        user_docs = await db.date_trigger_configs.aggregate(pipeline).to_list(10000)
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

            message = template.replace("{first_name}", contact.get("first_name", ""))
            message = message.replace("{last_name}", contact.get("last_name", ""))
            message = message.replace("{name}", contact_name)
            message = message.replace("{phone}", contact.get("phone", ""))

            send_result = {"sms": False, "email": False}

            if delivery in ("sms", "both") and contact.get("phone"):
                try:
                    await db.messages.insert_one({
                        "conversation_id": f"auto_{user_id}_{contact_id}",
                        "sender": "user",
                        "content": message,
                        "timestamp": datetime.now(timezone.utc),
                        "auto_sent": True,
                        "trigger_type": trigger_type,
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
                        await asyncio.to_thread(resend.Emails.send, {
                            "from": os.environ.get("SENDER_EMAIL", "iMOs <noreply@updates.imosapp.com>"),
                            "to": contact["email"],
                            "subject": f"A message from {user.get('name', 'Your contact')}",
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
    """Periodic job: find active enrollments with due messages and advance them."""
    from routers.database import get_db
    from routers.campaigns import calculate_next_send_date

    logger.info("[Scheduler] Processing pending campaign steps...")

    db = get_db()
    if db is None:
        logger.error("[Scheduler] DB not available")
        return

    now = datetime.utcnow()

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

                # Queue message for sending
                contact_phone = enrollment.get("contact_phone", "")
                contact_id = enrollment.get("contact_id", "")
                user_id = enrollment.get("user_id", "")

                if message_content and contact_phone:
                    await db.messages.insert_one({
                        "conversation_id": f"campaign_{user_id}_{contact_id}",
                        "sender": "user",
                        "content": message_content,
                        "timestamp": datetime.now(timezone.utc),
                        "auto_sent": True,
                        "campaign_id": enrollment["campaign_id"],
                        "campaign_step": current_step,
                    })

                logger.info(
                    f"[Scheduler] Sent step {current_step} to {enrollment.get('contact_name', 'unknown')}"
                )

                # Advance enrollment
                if current_step < len(sequences):
                    next_step = sequences[current_step]
                    next_send = calculate_next_send_date(next_step)
                    await db.campaign_enrollments.update_one(
                        {"_id": enrollment["_id"]},
                        {
                            "$set": {
                                "current_step": current_step + 1,
                                "last_sent_at": now,
                                "next_send_at": next_send,
                            },
                            "$push": {
                                "messages_sent": {
                                    "step": current_step,
                                    "sent_at": now,
                                    "content": message_content[:100],
                                }
                            },
                        },
                    )
                else:
                    await db.campaign_enrollments.update_one(
                        {"_id": enrollment["_id"]},
                        {
                            "$set": {
                                "current_step": current_step + 1,
                                "last_sent_at": now,
                                "next_send_at": None,
                                "status": "completed",
                            },
                            "$push": {
                                "messages_sent": {
                                    "step": current_step,
                                    "sent_at": now,
                                    "content": message_content[:100],
                                }
                            },
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
    except Exception as e:
        logger.error(f"[Scheduler] Fatal error in campaign step processing: {e}")
        _scheduler_state["errors"] = (_scheduler_state["errors"] + [str(e)])[-20:]


def start_scheduler():
    """Register jobs and start the APScheduler."""
    if scheduler.running:
        logger.warning("[Scheduler] Already running, skipping start.")
        return

    # Daily at 8 AM UTC — process date triggers (birthdays, anniversaries, holidays)
    scheduler.add_job(
        process_all_date_triggers,
        CronTrigger(hour=8, minute=0),
        id="daily_date_triggers",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    # Daily at 6 AM UTC — lifecycle scan (tenure tags, inactivity detection, milestone messages)
    scheduler.add_job(
        run_daily_lifecycle_scan,
        CronTrigger(hour=6, minute=0),
        id="daily_lifecycle_scan",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    # Every 15 minutes — process pending campaign step messages
    scheduler.add_job(
        process_pending_campaign_steps,
        IntervalTrigger(minutes=15),
        id="campaign_step_processor",
        replace_existing=True,
        misfire_grace_time=300,
    )

    scheduler.start()
    logger.info("[Scheduler] Started with 3 jobs: daily_lifecycle_scan (6:00 UTC), daily_date_triggers (8:00 UTC), campaign_step_processor (every 15m)")


def stop_scheduler():
    """Gracefully shut down the scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("[Scheduler] Shut down.")
