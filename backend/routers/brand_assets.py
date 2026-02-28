from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from datetime import datetime, timezone
import uuid, base64, logging
from routers.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/brand-assets", tags=["brand-assets"])


@router.get("/{user_id}")
async def get_brand_assets(user_id: str):
    """Get all custom brand assets uploaded by a user."""
    db = get_db()
    assets = await db.brand_assets.find(
        {"user_id": user_id, "deleted": {"$ne": True}},
        {"_id": 0}
    ).to_list(100)
    return {"assets": assets}


@router.post("/upload")
async def upload_brand_asset(
    user_id: str = Form(...),
    file: UploadFile = File(...),
    label: str = Form(None),
):
    """Upload a custom brand asset (logo, icon, image)."""
    db = get_db()

    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File must be less than 10MB")

    b64 = base64.b64encode(contents).decode("utf-8")
    data_url = f"data:{file.content_type};base64,{b64}"
    asset_id = str(uuid.uuid4())[:12]

    asset_doc = {
        "id": asset_id,
        "user_id": user_id,
        "label": label or file.filename or "Brand Asset",
        "description": f"Uploaded {file.filename or 'image'}",
        "url": data_url,
        "size": "Original",
        "category": "custom",
        "filename": file.filename,
        "content_type": file.content_type,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "deleted": False,
    }

    await db.brand_assets.insert_one(asset_doc)
    asset_doc.pop("_id", None)

    return {"success": True, "asset": asset_doc}


@router.delete("/{user_id}/{asset_id}")
async def delete_brand_asset(user_id: str, asset_id: str):
    """Soft-delete a custom brand asset."""
    db = get_db()
    result = await db.brand_assets.update_one(
        {"id": asset_id, "user_id": user_id},
        {"$set": {"deleted": True}},
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Asset not found")
    return {"success": True}
