"""
Demo Requests Router - Handles demo request form submissions from the marketing site
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timezone
from bson import ObjectId
import logging
import os
from pymongo import MongoClient

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/demo-requests", tags=["Demo Requests"])

# MongoDB connection
def get_db():
    client = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    return client[os.environ.get("DB_NAME", "test_database")]

class DemoRequest(BaseModel):
    name: str = Field(..., description="Full name of the requester")
    email: str = Field(..., description="Email address")
    phone: str = Field(..., description="Phone number")
    company: Optional[str] = None
    message: Optional[str] = None
    source: Optional[str] = "website_demo_request"

@router.post("")
async def create_demo_request(request: DemoRequest):
    """
    Create a demo request from the marketing website.
    This creates a lead/contact in the admin company's contacts.
    """
    db = get_db()
    
    try:
        # Find the admin company (first company or one marked as admin)
        admin_company = db.companies.find_one({"is_admin": True})
        if not admin_company:
            # Fallback to first company
            admin_company = db.companies.find_one({})
        
        if not admin_company:
            logger.warning("No admin company found for demo request")
            # Still save the request even without a company
            company_id = None
        else:
            company_id = str(admin_company["_id"])
        
        # Parse the name
        name_parts = request.name.strip().split(" ", 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ""
        
        # Create the contact/lead
        contact = {
            "first_name": first_name,
            "last_name": last_name,
            "full_name": request.name,
            "email": request.email,
            "phone": request.phone,
            "company": company_id,
            "company_name": request.company,
            "notes": f"Demo Request:\n{request.message}" if request.message else "Demo Request from website",
            "source": request.source,
            "lead_status": "new",
            "is_demo_request": True,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "tags": ["demo-request", "website-lead"],
        }
        
        result = db.contacts.insert_one(contact)
        
        # Also save to a dedicated demo_requests collection for tracking
        demo_record = {
            "contact_id": str(result.inserted_id),
            "name": request.name,
            "email": request.email,
            "phone": request.phone,
            "company": request.company,
            "message": request.message,
            "source": request.source,
            "status": "pending",
            "created_at": datetime.now(timezone.utc),
        }
        db.demo_requests.insert_one(demo_record)
        
        logger.info(f"Demo request created: {request.email}")
        
        return {
            "success": True,
            "message": "Demo request received successfully",
            "contact_id": str(result.inserted_id)
        }
        
    except Exception as e:
        logger.error(f"Error creating demo request: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to submit demo request")

@router.get("")
async def get_demo_requests():
    """Get all demo requests (admin only)"""
    db = get_db()
    
    requests = list(db.demo_requests.find({}).sort("created_at", -1).limit(100))
    
    # Serialize
    for req in requests:
        req["_id"] = str(req["_id"])
        if "contact_id" in req:
            req["contact_id"] = str(req["contact_id"])
        if "created_at" in req:
            req["created_at"] = req["created_at"].isoformat()
    
    return requests
