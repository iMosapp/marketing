"""Morning nudge: any voice memo still not attached to a contact gets one reminder a day, at 8 in the rep's own timezone."""
import logging
from datetime import datetime, timedelta, timezone

import pytz
from bson import ObjectId

logger = logging.getLogger(__name__)

MIN_AGE_HOURS = 10          # a memo from an hour ago is not forgotten yet
NUDGE_HOUR = 8


def _label(n: dict) -> str:
    return n.get("title") or (n.get("summary") or n.get("transcript") or "").strip()[:40] or "an untitled memo"


async def run(db) -> dict:
    from routers.notifications import create_notification
    from routers.push_notifications import send_push_to_user
    from routers.user_schedule import resolve_user_tz
    cutoff = datetime.now(timezone.utc) - timedelta(hours=MIN_AGE_HOURS)
    user_ids = await db.voice_notes.distinct("user_id", {"unattached": True, "created_at": {"$lt": cutoff}})
    sent = 0
    for uid in user_ids:
        if not ObjectId.is_valid(str(uid)):
            continue
        try:
            local = datetime.now(pytz.timezone(await resolve_user_tz(uid)))
        except Exception:
            continue
        if local.hour != NUDGE_HOUR:
            continue
        guard = await db.date_send_guard.find_one_and_update({"_id": f"memo_nudge_{uid}_{local.strftime('%Y-%m-%d')}"},
                                                             {"$setOnInsert": {"created_at": datetime.utcnow()}}, upsert=True)
        if guard:
            continue
        memos = await db.voice_notes.find({"user_id": uid, "unattached": True}, {"title": 1, "summary": 1, "transcript": 1}).sort("created_at", -1).to_list(20)
        if not memos:
            continue
        n = len(memos)
        first = _label(memos[0])
        title = "A voice memo is waiting for a name" if n == 1 else f"{n} voice memos are waiting for names"
        body = (f"\"{first}\" is not attached to anyone yet. File it while you still remember who it was." if n == 1
                else f"\"{first}\" and {n - 1} more are not attached to anyone yet. File them while you still remember who they were.")
        try:
            nid = await create_notification("memo_reminder", title, body, user_id=uid, action_required=False, priority="normal")
            await db.notifications.update_one({"_id": ObjectId(nid)}, {"$set": {"link": "/voice-memos"}})
        except Exception as e:
            logger.warning(f"[MemoReminder] notification failed for {uid}: {e}")
        try:
            await send_push_to_user(uid, title, body, url="/voice-memos", icon="mic")
        except Exception as e:
            logger.warning(f"[MemoReminder] push failed for {uid}: {e}")
        sent += 1
    if sent:
        logger.info(f"[MemoReminder] nudged {sent} rep(s)")
    return {"checked": len(user_ids), "nudged": sent}
