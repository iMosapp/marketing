"""
Fix photo orientation for existing images in object storage.

The original image pipeline was missing ImageOps.exif_transpose(), causing
photos taken on phones (especially iPhones) to be stored sideways in WebP.

This script re-processes photos from the base64 originals still stored in
the congrats_cards collection, running them through the now-fixed pipeline
that applies EXIF transpose before compression.
"""
import os
import sys
import asyncio
import logging

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pymongo
from utils.image_storage import upload_image, decode_base64_image

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "imos-admin-test_database")


async def fix_orientation():
    client = pymongo.MongoClient(MONGO_URL)
    db = client[DB_NAME]

    # Find all congrats_cards that have base64 customer_photo and a photo_url
    cards = list(db.congrats_cards.find(
        {"customer_photo": {"$regex": "^data:image"}},
        {"_id": 1, "customer_name": 1, "customer_photo": 1, "photo_url": 1, "contact_id": 1}
    ))

    logger.info(f"Found {len(cards)} cards with base64 photos to re-process")

    fixed = 0
    skipped = 0
    errors = 0

    for card in cards:
        card_id = str(card["_id"])
        name = card.get("customer_name", "unknown")
        contact_id = str(card.get("contact_id", "unknown"))
        old_url = card.get("photo_url", "")

        try:
            # Decode base64 original
            base64_data = card["customer_photo"]
            image_bytes, content_type = decode_base64_image(base64_data)
            logger.info(f"Re-processing {name} ({card_id}): {len(image_bytes) // 1024}KB original")

            # Re-upload through the fixed pipeline (now includes exif_transpose)
            result = await upload_image(
                image_bytes,
                prefix="congrats",
                entity_id=contact_id
            )

            if result:
                new_url = f"/api/images/{result['original_path']}"
                new_thumb = f"/api/images/{result['thumbnail_path']}"

                # Update the card's photo_url
                db.congrats_cards.update_one(
                    {"_id": card["_id"]},
                    {"$set": {
                        "photo_url": new_url,
                        "photo_thumbnail_url": new_thumb,
                    }}
                )

                # If this photo is also the contact's profile photo, update that too
                if contact_id != "unknown":
                    contact = db.contacts.find_one(
                        {"_id": card.get("contact_id")},
                        {"photo": 1}
                    )
                    if contact and contact.get("photo") == old_url:
                        db.contacts.update_one(
                            {"_id": card.get("contact_id")},
                            {"$set": {
                                "photo": new_url,
                                "photo_thumbnail": new_thumb,
                                "photo_url": new_url,
                            }}
                        )
                        logger.info(f"  Also updated contact profile photo")

                fixed += 1
                logger.info(f"  Fixed: {old_url[:50]}... -> {new_url[:50]}...")
            else:
                skipped += 1
                logger.warning(f"  Skipped {name}: upload_image returned None")

        except Exception as e:
            errors += 1
            logger.error(f"  Error processing {name} ({card_id}): {e}")

    logger.info(f"\nMigration complete: {fixed} fixed, {skipped} skipped, {errors} errors")
    client.close()


if __name__ == "__main__":
    asyncio.run(fix_orientation())
