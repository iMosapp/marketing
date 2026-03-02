"""
Demo Request Router — Captures leads from the marketing landing page.
"""
from fastapi import APIRouter
from bson import ObjectId
from datetime import datetime, timezone

from routers.database import get_db

router = APIRouter(prefix="/demo-requests", tags=["demo-requests"])


@router.post("")
async def create_demo_request(data: dict):
    """Capture a demo request from the landing page."""
    db = get_db()

    required = ["name", "email"]
    for field in required:
        if not data.get(field):
            return {"status": "error", "message": f"{field} is required"}

    demo = {
        "name": data.get("name", "").strip(),
        "email": data.get("email", "").strip().lower(),
        "phone": data.get("phone", "").strip(),
        "business_type": data.get("business_type", "").strip(),
        "company": data.get("company", "").strip(),
        "message": data.get("message", "").strip(),
        "lead_source": data.get("lead_source", "landing_page"),
        "status": "new",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    await db.demo_requests.insert_one({**demo, "_id": ObjectId()})
    return {"status": "success", "message": "Demo request received! We'll be in touch soon."}


@router.get("")
async def list_demo_requests():
    """List all demo requests (admin)."""
    db = get_db()
    requests = []
    async for doc in db.demo_requests.find({}, {"_id": 0}).sort("created_at", -1):
        requests.append(doc)
    return requests
