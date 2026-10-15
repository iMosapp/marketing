"""Queue a broadcast's recipients exactly once, from the Send button or the scheduled-broadcast job, on any replica.
The broadcast is claimed atomically (status -> queuing); every recipient row carries a deterministic dedupe_key with a unique
index, so a retry after a crash, a double tap or two replicas can never queue anyone twice. A claim left in `queuing` by a dead
replica is handed back to the scheduler (recover_stale), which re-runs the same idempotent queueing."""
import logging
import os
from datetime import datetime, timedelta, timezone

from bson import ObjectId
from pymongo import ReturnDocument, UpdateOne
from pymongo.errors import BulkWriteError

logger = logging.getLogger(__name__)

STALE_QUEUING_S = 600


def _public_media(urls) -> list:
    base = os.environ.get("PUBLIC_FACING_URL", os.environ.get("APP_URL", "https://app.imonsocial.com"))
    out = []
    for u in urls or []:
        if isinstance(u, str) and u.startswith(("http://", "https://")):
            out.append(u)
        elif isinstance(u, str) and u.startswith("/api/"):
            out.append(f"{base}{u}")
    return out


async def _enable_jessi(db, contacts: list, user_id: str, rep_number, now) -> int:
    n = 0
    for c in contacts:
        if not c.get("phone"):
            continue
        cid = str(c["_id"])
        conv = await db.conversations.find_one({"$or": [{"rep_phone": rep_number, "contact_phone": c["phone"]}, {"user_id": user_id, "contact_id": cid}]})
        if conv:
            await db.conversations.update_one({"_id": conv["_id"]}, {"$set": {"ai_enabled": True, "ai_mode": "auto"}})
        else:
            await db.conversations.insert_one({"user_id": user_id, "rep_phone": rep_number, "contact_id": cid, "contact_phone": c["phone"],
                                               "contact_name": f"{c.get('first_name', '')} {c.get('last_name', '')}".strip(), "status": "active",
                                               "ai_enabled": True, "ai_mode": "auto", "created_at": now, "last_message_at": now})
        n += 1
    return n


async def queue(db, broadcast_id: str, from_statuses: tuple, owner_id: str | None = None) -> dict:
    """{claimed, queued, jessi_enabled, estimated_completion}. claimed False = someone else has it (or it was already sent)."""
    from services.job_lease import INSTANCE_ID
    from services.twilio_service import get_rep_twilio_number
    now = datetime.now(timezone.utc)
    q = {"_id": ObjectId(broadcast_id), "status": {"$in": list(from_statuses)}}
    if owner_id:
        q["created_by"] = owner_id
    b = await db.broadcasts.find_one_and_update(q, {"$set": {"status": "queuing", "queue_owner": INSTANCE_ID, "queue_claimed_at": now}},
                                                return_document=ReturnDocument.AFTER)
    if not b:
        return {"claimed": False}
    user_id = b.get("created_by", "")
    try:
        rep_number = await get_rep_twilio_number(user_id)
        stagger = int(b.get("stagger_seconds", 10))
        media = _public_media(b.get("media_urls"))
        ids = [ObjectId(r) for r in b.get("recipients", []) if ObjectId.is_valid(str(r))]
        contacts = await db.contacts.find({"_id": {"$in": ids}}, {"_id": 1, "phone": 1, "first_name": 1, "last_name": 1}).to_list(5000)
        ops, i = [], 0
        naive = now.replace(tzinfo=None)
        for c in contacts:
            if not c.get("phone"):
                continue
            first = c.get("first_name", "there")
            cid = str(c["_id"])
            key = f"broadcast:{broadcast_id}:{cid}"
            ops.append(UpdateOne({"dedupe_key": key}, {"$setOnInsert": {
                "dedupe_key": key, "user_id": user_id, "contact_id": cid, "contact_name": f"{c.get('first_name', '')} {c.get('last_name', '')}".strip(),
                "contact_phone": c["phone"], "rep_phone": rep_number, "message_template": (b.get("message", "")).replace("{first_name}", first).replace("{name}", first),
                "media_urls": media, "channel": "sms", "delivery_mode": "auto", "send_at": naive + timedelta(seconds=i * stagger), "status": "pending",
                "step": 0, "enrollment_id": "", "campaign_id": "", "campaign_name": b.get("name", "Broadcast"), "broadcast_id": broadcast_id,
                "type": "broadcast", "purpose": "marketing", "created_at": naive}}, upsert=True))
            i += 1
        if ops:
            try:
                await db.campaign_pending_sends.bulk_write(ops, ordered=False)
            except BulkWriteError as e:
                if any(err.get("code") != 11000 for err in e.details.get("writeErrors", [])):
                    raise
        queued = await db.campaign_pending_sends.count_documents({"broadcast_id": broadcast_id, "type": "broadcast"})
        jessi = await _enable_jessi(db, contacts, user_id, rep_number, now) if b.get("jessi_replies") else 0
        done_at = (now + timedelta(seconds=i * stagger)).isoformat()
        await db.broadcasts.update_one({"_id": b["_id"], "status": "queuing"}, {"$set": {"status": "sending", "sent_at": now.isoformat(), "queued_count": queued,
                                                                                         "estimated_completion": done_at}})
        logger.info(f"[Broadcast] '{b.get('name')}' queued {queued} recipient(s) once (replica {INSTANCE_ID})")
        return {"claimed": True, "queued": queued, "jessi_enabled": jessi, "estimated_completion": done_at, "stagger": stagger}
    except Exception as e:
        logger.error(f"[Broadcast] queueing {broadcast_id} failed: {e}")
        await db.broadcasts.update_one({"_id": b["_id"], "status": "queuing"}, {"$set": {"status": "failed", "error": str(e)[:300]}})
        raise


async def recover_stale(db) -> int:
    """A replica died mid-queue: hand the broadcast back to the scheduler, which re-runs the idempotent queueing."""
    cut = datetime.now(timezone.utc) - timedelta(seconds=STALE_QUEUING_S)
    r = await db.broadcasts.update_many({"status": "queuing", "queue_claimed_at": {"$lt": cut}},
                                        {"$set": {"status": "scheduled", "scheduled_at": datetime.now(timezone.utc).isoformat(), "requeued_after_crash": True}})
    if r.modified_count:
        logger.warning(f"[Broadcast] {r.modified_count} broadcast(s) left mid-queue by a stopped replica were re-queued")
    return r.modified_count
