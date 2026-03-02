"""
Setup Wizard API — Tracks wizard progress and handles bulk setup operations.
Most actual creation (org, store, users) is delegated to existing endpoints.
"""
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime, timezone
from bson import ObjectId
from routers.database import get_db
import secrets
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/setup-wizard", tags=["Setup Wizard"])


class WizardProgress(BaseModel):
    """Track which steps of the wizard have been completed"""
    organization_id: Optional[str] = None
    store_id: Optional[str] = None
    current_step: int = 1
    completed_steps: List[int] = []
    completed: bool = False


class BulkTeamMember(BaseModel):
    name: str
    email: EmailStr
    phone: Optional[str] = ""
    role: str = "user"  # user, store_manager


class BulkInviteRequest(BaseModel):
    store_id: str
    members: List[BulkTeamMember]


def serialize(doc: dict) -> dict:
    """Remove ObjectId fields for JSON serialization"""
    if doc and "_id" in doc:
        doc["_id"] = str(doc["_id"])
    return doc


@router.get("/progress/{org_id}")
async def get_wizard_progress(org_id: str, x_user_id: str = Header(None, alias="X-User-ID")):
    """Get the wizard progress for an organization"""
    db = get_db()
    progress = await db.setup_wizard_progress.find_one(
        {"organization_id": org_id}, {"_id": 0}
    )
    if not progress:
        return {
            "organization_id": org_id,
            "current_step": 1,
            "completed_steps": [],
            "completed_step_ids": [],
            "completed": False,
        }
    return progress


@router.post("/progress/{org_id}")
async def save_wizard_progress(org_id: str, data: dict, x_user_id: str = Header(None, alias="X-User-ID")):
    """Save wizard progress for an organization"""
    db = get_db()
    await db.setup_wizard_progress.update_one(
        {"organization_id": org_id},
        {"$set": {
            "organization_id": org_id,
            "store_id": data.get("store_id"),
            "current_step": data.get("current_step", 1),
            "completed_steps": data.get("completed_steps", []),
            "completed_step_ids": data.get("completed_step_ids", []),
            "completed": data.get("completed", False),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )
    return {"success": True}


@router.post("/bulk-invite")
async def bulk_invite_team_members(data: BulkInviteRequest, x_user_id: str = Header(None, alias="X-User-ID")):
    """
    Create multiple team members at once. For each member:
    1. Creates user account with temp password
    2. Assigns to the store
    3. Returns list of created users (with temp passwords for admin to share)
    """
    db = get_db()

    if not x_user_id:
        raise HTTPException(status_code=401, detail="User ID required")

    # Verify store exists
    store = await db.stores.find_one({"_id": ObjectId(data.store_id)})
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")

    org_id = store.get("organization_id", "")
    results = []

    for member in data.members:
        email = member.email.lower().strip()
        try:
            # Check if email already exists
            existing = await db.users.find_one({"email": email})
            if existing:
                results.append({
                    "name": member.name,
                    "email": email,
                    "status": "skipped",
                    "reason": "Email already exists",
                })
                continue

            # Normalize phone
            phone = ""
            if member.phone:
                phone_clean = "".join(c for c in member.phone if c.isdigit())
                if len(phone_clean) == 10:
                    phone_clean = "1" + phone_clean
                phone = "+" + phone_clean if phone_clean else ""

            # Generate temp password
            temp_password = secrets.token_urlsafe(8)

            # Create user
            new_user = {
                "name": member.name.strip(),
                "email": email,
                "phone": phone,
                "password": temp_password,
                "role": member.role,
                "organization_id": org_id,
                "store_id": data.store_id,
                "store_ids": [data.store_id],
                "mode": "rep",
                "is_active": True,
                "status": "active",
                "onboarding_complete": False,
                "account_type": "org",
                "leaderboard_visible": False,
                "compare_scope": "state",
                "stats": {"contacts_added": 0, "messages_sent": 0, "calls_made": 0, "deals_closed": 0},
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }

            result = await db.users.insert_one(new_user)
            user_id = str(result.inserted_id)

            results.append({
                "name": member.name,
                "email": email,
                "temp_password": temp_password,
                "user_id": user_id,
                "status": "created",
            })

        except Exception as e:
            logger.error(f"Error creating user {email}: {e}")
            results.append({
                "name": member.name,
                "email": email,
                "status": "error",
                "reason": str(e),
            })

    created_count = sum(1 for r in results if r["status"] == "created")
    return {
        "success": True,
        "total": len(data.members),
        "created": created_count,
        "skipped": len(data.members) - created_count,
        "results": results,
    }


@router.post("/complete/{org_id}")
async def mark_wizard_complete(org_id: str, x_user_id: str = Header(None, alias="X-User-ID")):
    """Mark the setup wizard as complete for this organization"""
    db = get_db()
    await db.setup_wizard_progress.update_one(
        {"organization_id": org_id},
        {"$set": {
            "completed": True,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "completed_by": x_user_id,
        }},
        upsert=True,
    )
    # Also mark on the org itself if org_id is a valid ObjectId
    try:
        if ObjectId.is_valid(org_id):
            await db.organizations.update_one(
                {"_id": ObjectId(org_id)},
                {"$set": {"setup_complete": True, "updated_at": datetime.now(timezone.utc).isoformat()}}
            )
    except Exception as e:
        logger.warning(f"Could not update org {org_id} setup_complete flag: {e}")
    return {"success": True, "message": "Setup wizard completed"}


# ─── Multi-Client Onboarding CRUD ───

class ClientCreate(BaseModel):
    client_name: str
    contact_email: Optional[str] = ""
    contact_phone: Optional[str] = ""
    industry: Optional[str] = ""
    notes: Optional[str] = ""


@router.get("/clients")
async def list_onboarding_clients(x_user_id: str = Header(None, alias="X-User-ID")):
    """List all onboarding client records"""
    db = get_db()
    cursor = db.onboarding_clients.find({}, {"_id": 1, "client_name": 1, "contact_email": 1, "contact_phone": 1, "industry": 1, "notes": 1, "completed_step_ids": 1, "step_data": 1, "status": 1, "created_at": 1})
    results = []
    async for doc in cursor.sort("created_at", -1):
        doc["_id"] = str(doc["_id"])
        results.append(doc)
    return results


@router.post("/clients")
async def create_onboarding_client(data: ClientCreate, x_user_id: str = Header(None, alias="X-User-ID")):
    """Create a new client onboarding record"""
    db = get_db()
    doc = {
        "client_name": data.client_name,
        "contact_email": data.contact_email or "",
        "contact_phone": data.contact_phone or "",
        "industry": data.industry or "",
        "notes": data.notes or "",
        "completed_step_ids": [],
        "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": x_user_id or "",
    }
    result = await db.onboarding_clients.insert_one(doc)
    doc["_id"] = str(result.inserted_id)
    return doc


@router.put("/clients/{client_id}")
async def update_onboarding_client(client_id: str, data: dict, x_user_id: str = Header(None, alias="X-User-ID")):
    """Update a client onboarding record (step progress, status, etc.)"""
    db = get_db()
    allowed = {"completed_step_ids", "status", "client_name", "contact_email", "contact_phone", "industry", "notes", "step_data"}
    update = {k: v for k, v in data.items() if k in allowed}
    update["updated_at"] = datetime.now(timezone.utc).isoformat()

    await db.onboarding_clients.update_one(
        {"_id": ObjectId(client_id)},
        {"$set": update},
    )
    return {"success": True}
