"""
Contact Merge Router — Detect and merge duplicate contacts within the same salesperson.
NEVER merges contacts across different salespeople.
"""
import re
import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException
from bson import ObjectId
from routers.database import get_db

router = APIRouter(prefix="/contacts", tags=["Contact Merge"])
logger = logging.getLogger(__name__)

# All collections that store contact_id and need migration during a merge
COLLECTIONS_WITH_CONTACT_ID = [
    "contact_events",
    "notifications",
    "tasks",
    "campaign_pending_sends",
    "campaign_enrollments",
    "engagement_signals",
    "conversations",
    "calls",
    "ai_outreach",
    "birthday_cards",
    "congrats_cards",
    "contact_intel",
    "contact_photos",
    "voice_notes",
    "email_logs",
]


def _normalize_phone(phone: str) -> str:
    """Extract last 10 digits from a phone number."""
    if not phone:
        return ""
    digits = re.sub(r'\D', '', phone)
    return digits[-10:] if len(digits) >= 10 else digits


@router.get("/{user_id}/duplicates")
async def detect_duplicates(user_id: str):
    """
    Detect duplicate contacts within a single salesperson's contact list.
    Groups contacts by normalized phone number (last 10 digits).
    Only returns groups with 2+ contacts (actual duplicates).
    """
    db = get_db()

    contacts = await db.contacts.find(
        {"user_id": user_id, "status": {"$ne": "deleted"}, "phone": {"$exists": True, "$ne": ""}},
        {"_id": 1, "first_name": 1, "last_name": 1, "phone": 1, "email": 1,
         "photo_thumbnail": 1, "photo_url": 1, "tags": 1, "created_at": 1,
         "notes": 1, "source": 1}
    ).to_list(5000)

    # Group by normalized phone
    phone_groups = {}
    for c in contacts:
        norm = _normalize_phone(c.get("phone", ""))
        if not norm:
            continue
        if norm not in phone_groups:
            phone_groups[norm] = []
        phone_groups[norm].append(c)

    # Only keep groups with duplicates
    duplicate_sets = []
    for phone, group in phone_groups.items():
        if len(group) < 2:
            continue

        # Enrich each contact with activity counts
        enriched = []
        for c in group:
            cid = str(c["_id"])
            event_count = await db.contact_events.count_documents({"contact_id": cid})
            conversation_count = await db.conversations.count_documents({"contact_id": cid})
            card_count = await db.congrats_cards.count_documents({"contact_id": cid})
            card_count += await db.birthday_cards.count_documents({"contact_id": cid})

            # Get last activity timestamp
            last_event = await db.contact_events.find_one(
                {"contact_id": cid}, sort=[("timestamp", -1)], projection={"timestamp": 1}
            )

            enriched.append({
                "id": cid,
                "first_name": c.get("first_name", ""),
                "last_name": c.get("last_name", ""),
                "phone": c.get("phone", ""),
                "email": c.get("email", ""),
                "photo": c.get("photo_thumbnail") or c.get("photo_url") or None,
                "tags": c.get("tags", []),
                "notes": (c.get("notes") or "")[:100],
                "source": c.get("source", ""),
                "created_at": c.get("created_at").isoformat() if c.get("created_at") else None,
                "event_count": event_count,
                "conversation_count": conversation_count,
                "card_count": card_count,
                "last_activity": last_event["timestamp"].isoformat() if last_event and last_event.get("timestamp") else None,
            })

        # Sort so the contact with more activity is first (suggested primary)
        enriched.sort(key=lambda x: x["event_count"], reverse=True)

        duplicate_sets.append({
            "phone": phone,
            "contacts": enriched,
        })

    # Sort sets by total activity (most active duplicates first)
    duplicate_sets.sort(
        key=lambda s: sum(c["event_count"] for c in s["contacts"]), reverse=True
    )

    return {
        "duplicate_count": len(duplicate_sets),
        "duplicates": duplicate_sets,
    }


@router.post("/{user_id}/merge")
async def merge_contacts(user_id: str, body: dict):
    """
    Merge a duplicate contact into a primary contact.
    Moves all related data from duplicate → primary, then soft-deletes the duplicate.

    Body: { "primary_id": "...", "duplicate_id": "..." }

    Safety checks:
    - Both contacts must belong to the same user_id
    - Both must exist and not already be deleted/merged
    """
    db = get_db()

    primary_id = body.get("primary_id", "").strip()
    duplicate_id = body.get("duplicate_id", "").strip()

    if not primary_id or not duplicate_id:
        raise HTTPException(status_code=400, detail="primary_id and duplicate_id are required")
    if primary_id == duplicate_id:
        raise HTTPException(status_code=400, detail="Cannot merge a contact with itself")

    # Validate both contacts exist and belong to the same user
    try:
        primary = await db.contacts.find_one({"_id": ObjectId(primary_id), "user_id": user_id})
        duplicate = await db.contacts.find_one({"_id": ObjectId(duplicate_id), "user_id": user_id})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid contact ID format")

    if not primary:
        raise HTTPException(status_code=404, detail="Primary contact not found or doesn't belong to this user")
    if not duplicate:
        raise HTTPException(status_code=404, detail="Duplicate contact not found or doesn't belong to this user")

    if primary.get("status") in ("deleted", "merged"):
        raise HTTPException(status_code=400, detail="Primary contact is already deleted or merged")
    if duplicate.get("status") in ("deleted", "merged"):
        raise HTTPException(status_code=400, detail="Duplicate contact is already deleted or merged")

    # --- Phase 1: Migrate all data from duplicate → primary ---
    migration_log = {}

    for collection_name in COLLECTIONS_WITH_CONTACT_ID:
        try:
            result = await db[collection_name].update_many(
                {"contact_id": duplicate_id},
                {"$set": {"contact_id": primary_id}}
            )
            if result.modified_count > 0:
                migration_log[collection_name] = result.modified_count
        except Exception as e:
            logger.warning(f"[Merge] Failed to migrate {collection_name}: {e}")

    # --- Phase 1b: Merge conversations (messages are linked via conversation_id) ---
    try:
        primary_conv = await db.conversations.find_one(
            {"contact_id": primary_id, "user_id": user_id}
        )
        # Find the duplicate's conversation(s) — contact_id was already updated to primary_id above,
        # so we look for any conversations that were the duplicate's by checking all convs for this
        # contact/user pair and excluding the primary's original conversation.
        dup_convs = []
        if primary_conv:
            all_convs = await db.conversations.find(
                {"contact_id": primary_id, "user_id": user_id}
            ).to_list(10)
            dup_convs = [c for c in all_convs if str(c["_id"]) != str(primary_conv["_id"])]
        else:
            # Primary had no conversation — the first one we find becomes the primary's
            primary_conv = await db.conversations.find_one(
                {"contact_id": primary_id, "user_id": user_id}
            )

        # Move messages from duplicate conversations into the primary conversation
        msgs_moved = 0
        for dup_conv in dup_convs:
            dup_conv_id = str(dup_conv["_id"])
            if primary_conv:
                primary_conv_id = str(primary_conv["_id"])
                result = await db.messages.update_many(
                    {"conversation_id": dup_conv_id},
                    {"$set": {"conversation_id": primary_conv_id}}
                )
                msgs_moved += result.modified_count
            # Remove the now-empty duplicate conversation
            await db.conversations.delete_one({"_id": dup_conv["_id"]})

        if msgs_moved > 0:
            migration_log["messages"] = msgs_moved
    except Exception as e:
        logger.warning(f"[Merge] Failed to merge conversations: {e}")

    # Also update short_urls metadata.contact_id
    try:
        result = await db.short_urls.update_many(
            {"metadata.contact_id": duplicate_id},
            {"$set": {"metadata.contact_id": primary_id}}
        )
        if result.modified_count > 0:
            migration_log["short_urls"] = result.modified_count
    except Exception as e:
        logger.warning(f"[Merge] Failed to migrate short_urls: {e}")

    # --- Phase 2: Merge contact fields (fill in what primary is missing) ---
    merge_updates = {}

    # Merge tags (union)
    primary_tags = set(primary.get("tags", []))
    dup_tags = set(duplicate.get("tags", []))
    merged_tags = list(primary_tags | dup_tags)
    if merged_tags != list(primary_tags):
        merge_updates["tags"] = merged_tags

    # Fill missing fields from duplicate
    for field in ["email", "email_work", "birthday", "anniversary", "date_sold",
                   "address", "city", "state", "zip_code", "vehicle", "vehicle_year",
                   "vehicle_make", "vehicle_model", "notes"]:
        if not primary.get(field) and duplicate.get(field):
            merge_updates[field] = duplicate[field]

    # Merge notes (append if both have content)
    if primary.get("notes") and duplicate.get("notes"):
        merge_updates["notes"] = f"{primary['notes']}\n\n--- Merged from duplicate ---\n{duplicate['notes']}"

    # Fill missing photo
    for photo_field in ["photo_path", "photo_thumb_path", "photo_thumbnail", "photo_url"]:
        if not primary.get(photo_field) and duplicate.get(photo_field):
            merge_updates[photo_field] = duplicate[photo_field]

    merge_updates["updated_at"] = datetime.now(timezone.utc)

    if merge_updates:
        await db.contacts.update_one(
            {"_id": ObjectId(primary_id)},
            {"$set": merge_updates}
        )

    # --- Phase 3: Soft-delete the duplicate ---
    await db.contacts.update_one(
        {"_id": ObjectId(duplicate_id)},
        {"$set": {
            "status": "merged",
            "merged_into": primary_id,
            "merged_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }}
    )

    total_migrated = sum(migration_log.values())
    logger.info(
        f"[Merge] Contact {duplicate_id} merged into {primary_id} for user {user_id}. "
        f"Migrated {total_migrated} records across {len(migration_log)} collections."
    )

    return {
        "success": True,
        "primary_id": primary_id,
        "duplicate_id": duplicate_id,
        "records_migrated": total_migrated,
        "migration_detail": migration_log,
        "fields_merged": list(merge_updates.keys()),
    }
