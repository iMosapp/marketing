"""Memo nudge: ~90 s after a rep adds a contact or shares their card, one push asks them to record a voice memo while it is fresh.
Same tap target as the post-sale prompt (/contact/{id}?capture=true opens the recorder). One nudge per contact per 24 h; skipped when a
memo was recorded in the meantime. In-process timer (like the sold-wizard reminder): a restart inside the 90 s window drops it."""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from bson import ObjectId

from routers.database import get_db

logger = logging.getLogger(__name__)

DELAY_S = 90
COOLDOWN_H = 24
CARD_EVENTS = {"digital_card_shared", "vcf_shared", "card_qr_shown"}
SKIP_SOURCES = {"phone_import", "phone_contacts", "csv", "dms", "crm", "api"}

TEXT = {
    "new_contact": (lambda first: (f"You just added {first}. Tell me about them",
                                   "Tap and talk for a minute while it is fresh: who they are, what they want, anything personal. I'll save it to their profile.")),
    "card": (lambda first: (f"You just shared your card with {first}",
                            "Tap and talk for a minute while it is fresh: how you met, what they are looking for, anything personal. I'll save it to their profile.")),
}


def schedule(user_id: str, contact_id: str, reason: str, delay_s: int = DELAY_S):
    """reason: 'new_contact' | 'card'. Fire-and-forget; returns the task, or None outside an event loop."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return None
    return loop.create_task(_run(user_id, str(contact_id), reason, delay_s))


def _is_after(value, moment: datetime) -> bool:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return False
    if not isinstance(value, datetime):
        return False
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value > moment


async def claim(db, user_id: str, contact_id: str, reason: str) -> dict | None:
    """Atomically mark the contact as nudged (one per 24 h); returns the contact when this caller won."""
    now = datetime.now(timezone.utc)
    try:
        oid = ObjectId(contact_id)
    except Exception:
        return None
    return await db.contacts.find_one_and_update(
        {"_id": oid, "user_id": user_id,
         "$or": [{"memo_nudge_at": {"$exists": False}}, {"memo_nudge_at": {"$lt": (now - timedelta(hours=COOLDOWN_H)).isoformat()}}]},
        {"$set": {"memo_nudge_at": now.isoformat(), "memo_nudge_reason": reason}},
        projection={"first_name": 1},
    )


async def _run(user_id: str, contact_id: str, reason: str, delay_s: int):
    try:
        db = get_db()
        started = datetime.now(timezone.utc)
        contact = await claim(db, user_id, contact_id, reason)
        if not contact:
            return
        await asyncio.sleep(delay_s)
        note = await db.voice_notes.find_one({"contact_id": contact_id, "user_id": user_id}, sort=[("created_at", -1)], projection={"created_at": 1})
        if note and _is_after(note.get("created_at"), started):
            logger.info(f"[MemoNudge] skipped, memo already recorded for {contact_id}")
            return
        first = (contact.get("first_name") or "").strip() or "them"
        title, body = TEXT[reason](first)
        from routers.push_notifications import send_push_to_user
        await send_push_to_user(user_id, title, body, f"/contact/{contact_id}?capture=true", "mic")
        logger.info(f"[MemoNudge] sent ({reason}) for contact {contact_id}")
    except Exception as e:
        logger.warning(f"[MemoNudge] failed for contact {contact_id}: {e}")
