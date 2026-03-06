"""
One-time migration: Move all base64 images from MongoDB fields to Object Storage (WebP).
Re-compress any existing object storage images that aren't WebP.

Targets:
- users.photo_url (base64 → object storage WebP)
- contacts.photo (base64 → object storage WebP)
- contacts.photo_thumbnail (base64 → object storage WebP)
- stores.logo_url (PNG/JPEG in storage → re-compress to WebP)

Run: python3 /app/backend/scripts/migrate_images.py
"""
import asyncio
import os
import sys
import logging

# Add backend to path
sys.path.insert(0, "/app/backend")

from motor.motor_asyncio import AsyncIOMotorClient
from utils.image_storage import upload_image, get_object, put_object, _compress_image, init_storage

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("migrate_images")

MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = "imos-admin-test_database"


async def migrate_base64_field(db, collection_name, doc_id, field_name, prefix, entity_id):
    """Migrate a single base64 field to object storage."""
    coll = db[collection_name]
    doc = await coll.find_one({"_id": doc_id}, {field_name: 1})
    if not doc:
        return False

    value = doc.get(field_name, "")
    if not value or not isinstance(value, str):
        return False

    # Only migrate base64 data URIs
    if not value.startswith("data:"):
        return False

    logger.info(f"  Migrating {collection_name}.{field_name} for {doc_id} ({len(value)} chars base64)")

    result = await upload_image(value, prefix=prefix, entity_id=entity_id)
    if not result:
        logger.error(f"  FAILED to upload {collection_name}.{field_name} for {doc_id}")
        return False

    new_url = f"/api/images/{result['original_path']}"
    thumb_url = f"/api/images/{result['thumbnail_path']}"
    avatar_url = f"/api/images/{result['avatar_path']}"

    # Update the document
    update = {field_name: new_url}
    if field_name == "photo_url":
        update["photo_thumbnail_url"] = thumb_url
        update["photo_avatar_url"] = avatar_url
    elif field_name == "photo":
        update["photo_thumbnail"] = thumb_url

    await coll.update_one({"_id": doc_id}, {"$set": update})
    logger.info(f"  ✓ Migrated → {new_url}")
    return True


async def recompress_storage_image(db, collection_name, doc_id, field_name, prefix, entity_id):
    """Re-compress an existing object storage image to WebP if it's not already."""
    coll = db[collection_name]
    doc = await coll.find_one({"_id": doc_id}, {field_name: 1})
    if not doc:
        return False

    value = doc.get(field_name, "")
    if not value or not isinstance(value, str):
        return False

    # Only process object storage paths that aren't already WebP
    if not value.startswith("/api/images/"):
        return False
    if ".webp" in value:
        logger.info(f"  Already WebP: {value}")
        return False

    # Extract the storage path
    storage_path = value.replace("/api/images/", "")
    logger.info(f"  Re-compressing {collection_name}.{field_name}: {storage_path}")

    try:
        # Fetch original from storage
        data, content_type = get_object(storage_path)
        logger.info(f"  Original: {len(data)} bytes ({content_type})")

        # Re-upload with compression
        result = await upload_image(data, prefix=prefix, entity_id=entity_id)
        if not result:
            logger.error(f"  FAILED to re-compress")
            return False

        new_url = f"/api/images/{result['original_path']}"
        thumb_url = f"/api/images/{result['thumbnail_path']}"
        avatar_url = f"/api/images/{result['avatar_path']}"

        update = {field_name: new_url}
        if "logo" in field_name:
            update["logo_thumbnail_url"] = thumb_url
            update["logo_avatar_url"] = avatar_url

        await coll.update_one({"_id": doc_id}, {"$set": update})
        logger.info(f"  ✓ Re-compressed → {new_url}")
        return True
    except Exception as e:
        logger.error(f"  Error re-compressing: {e}")
        return False


async def main():
    logger.info("=" * 60)
    logger.info("IMAGE MIGRATION: base64 → Object Storage (WebP)")
    logger.info("=" * 60)

    # Initialize storage
    init_storage()

    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    migrated = 0
    recompressed = 0

    # 1. Migrate user photos (base64 → object storage)
    logger.info("\n--- Users with base64 photos ---")
    async for user in db.users.find(
        {"photo_url": {"$regex": "^data:"}},
        {"photo_url": 1, "name": 1}
    ):
        uid = str(user["_id"])
        logger.info(f"User: {user.get('name', uid)}")
        if await migrate_base64_field(db, "users", user["_id"], "photo_url", "users", uid):
            migrated += 1

    # 2. Migrate contact photos (base64 → object storage)
    logger.info("\n--- Contacts with base64 photos ---")
    async for contact in db.contacts.find(
        {"photo": {"$regex": "^data:"}},
        {"photo": 1, "first_name": 1}
    ):
        cid = str(contact["_id"])
        logger.info(f"Contact: {contact.get('first_name', cid)}")
        if await migrate_base64_field(db, "contacts", contact["_id"], "photo", "contacts", cid):
            migrated += 1

    # 3. Migrate contact thumbnails (base64 → object storage)
    logger.info("\n--- Contacts with base64 thumbnails ---")
    async for contact in db.contacts.find(
        {"photo_thumbnail": {"$regex": "^data:"}},
        {"photo_thumbnail": 1, "first_name": 1}
    ):
        cid = str(contact["_id"])
        logger.info(f"Contact thumbnail: {contact.get('first_name', cid)}")
        if await migrate_base64_field(db, "contacts", contact["_id"], "photo_thumbnail", "contacts", cid):
            migrated += 1

    # 4. Re-compress store logos (PNG/JPEG → WebP)
    logger.info("\n--- Store logos to re-compress ---")
    async for store in db.stores.find(
        {"logo_url": {"$regex": "^/api/images/", "$not": {"$regex": "\\.webp"}}},
        {"logo_url": 1, "name": 1}
    ):
        sid = str(store["_id"])
        logger.info(f"Store: {store.get('name', sid)}")
        if await recompress_storage_image(db, "stores", store["_id"], "logo_url", "logos", sid):
            recompressed += 1

    # 5. Re-compress user photos already in object storage but not WebP
    logger.info("\n--- User photos to re-compress ---")
    async for user in db.users.find(
        {"photo_url": {"$regex": "^/api/images/", "$not": {"$regex": "\\.webp"}}},
        {"photo_url": 1, "name": 1}
    ):
        uid = str(user["_id"])
        logger.info(f"User: {user.get('name', uid)}")
        if await recompress_storage_image(db, "users", user["_id"], "photo_url", "users", uid):
            recompressed += 1

    logger.info("\n" + "=" * 60)
    logger.info(f"MIGRATION COMPLETE: {migrated} base64→storage, {recompressed} re-compressed to WebP")
    logger.info("=" * 60)

    client.close()


if __name__ == "__main__":
    asyncio.run(main())
