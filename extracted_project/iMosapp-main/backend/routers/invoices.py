"""
Invoices router - Manages user invoices and billing history
"""
from fastapi import APIRouter, HTTPException, Header
from bson import ObjectId
from datetime import datetime, timedelta
from typing import Optional, List
import logging
from pydantic import BaseModel

from routers.database import get_db, get_user_by_id
from routers.rbac import get_scoped_store_ids, get_scoped_organization_ids

router = APIRouter(prefix="/invoices", tags=["Invoices"])
logger = logging.getLogger(__name__)


class InvoiceCreate(BaseModel):
    user_id: str
    amount: float
    description: str
    due_date: Optional[str] = None
    invoice_type: str = "subscription"  # subscription, one_time, overage


@router.get("/user/{user_id}")
async def get_user_invoices(
    user_id: str,
    status: Optional[str] = None,
    x_user_id: str = Header(None, alias="X-User-ID")
):
    """
    Get invoices for a specific user.
    Users can only see their own invoices unless they're an admin.
    """
    db = get_db()
    
    # Verify requesting user
    requesting_user = await get_user_by_id(x_user_id) if x_user_id else None
    
    # Users can see their own invoices, admins can see others
    if requesting_user:
        if str(requesting_user.get('_id')) != user_id:
            role = requesting_user.get('role', 'user')
            if role not in ['super_admin', 'org_admin']:
                raise HTTPException(status_code=403, detail="You can only view your own invoices")
    
    # Get user to find their store/org context
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Build query
    query = {
        "$or": [
            {"user_id": user_id},
            {"user_email": user.get("email")},
        ]
    }
    
    # Add store-level invoices
    if user.get("store_id"):
        query["$or"].append({"store_id": user.get("store_id")})
    
    # Add org-level invoices
    if user.get("organization_id"):
        query["$or"].append({"organization_id": user.get("organization_id")})
    
    if status:
        query["status"] = status
    
    invoices = await db.invoices.find(query).sort("created_at", -1).to_list(100)
    
    # Format response
    result = []
    for inv in invoices:
        result.append({
            "_id": str(inv["_id"]),
            "invoice_number": inv.get("invoice_number", f"INV-{str(inv['_id'])[-6:].upper()}"),
            "amount": inv.get("amount", 0),
            "status": inv.get("status", "pending"),
            "description": inv.get("description", ""),
            "invoice_type": inv.get("invoice_type", "subscription"),
            "due_date": inv.get("due_date"),
            "paid_at": inv.get("paid_at"),
            "created_at": inv.get("created_at"),
            "pdf_url": inv.get("pdf_url"),
        })
    
    return result


@router.get("/store/{store_id}")
async def get_store_invoices(
    store_id: str,
    status: Optional[str] = None,
    x_user_id: str = Header(None, alias="X-User-ID")
):
    """
    Get invoices for a specific store.
    Only store managers and admins can view store invoices.
    """
    db = get_db()
    
    # Verify access
    if x_user_id:
        user = await get_user_by_id(x_user_id)
        if user:
            role = user.get('role', 'user')
            allowed_stores = await get_scoped_store_ids(user)
            if role not in ['super_admin'] and store_id not in allowed_stores:
                raise HTTPException(status_code=403, detail="Access denied to this store")
    
    # Build query
    query = {"store_id": store_id}
    if status:
        query["status"] = status
    
    invoices = await db.invoices.find(query).sort("created_at", -1).to_list(100)
    
    # Format response
    result = []
    for inv in invoices:
        result.append({
            "_id": str(inv["_id"]),
            "invoice_number": inv.get("invoice_number", f"INV-{str(inv['_id'])[-6:].upper()}"),
            "amount": inv.get("amount", 0),
            "status": inv.get("status", "pending"),
            "description": inv.get("description", ""),
            "invoice_type": inv.get("invoice_type", "subscription"),
            "due_date": inv.get("due_date"),
            "paid_at": inv.get("paid_at"),
            "created_at": inv.get("created_at"),
            "pdf_url": inv.get("pdf_url"),
        })
    
    return result


@router.get("/organization/{org_id}")
async def get_organization_invoices(
    org_id: str,
    status: Optional[str] = None,
    x_user_id: str = Header(None, alias="X-User-ID")
):
    """
    Get invoices for an organization.
    Only org admins and super admins can view org invoices.
    """
    db = get_db()
    
    # Verify access
    if x_user_id:
        user = await get_user_by_id(x_user_id)
        if user:
            role = user.get('role', 'user')
            allowed_orgs = await get_scoped_organization_ids(user)
            if role not in ['super_admin'] and org_id not in allowed_orgs:
                raise HTTPException(status_code=403, detail="Access denied to this organization")
    
    # Build query
    query = {"organization_id": org_id}
    if status:
        query["status"] = status
    
    invoices = await db.invoices.find(query).sort("created_at", -1).to_list(100)
    
    # Format response
    result = []
    for inv in invoices:
        result.append({
            "_id": str(inv["_id"]),
            "invoice_number": inv.get("invoice_number", f"INV-{str(inv['_id'])[-6:].upper()}"),
            "amount": inv.get("amount", 0),
            "status": inv.get("status", "pending"),
            "description": inv.get("description", ""),
            "invoice_type": inv.get("invoice_type", "subscription"),
            "due_date": inv.get("due_date"),
            "paid_at": inv.get("paid_at"),
            "created_at": inv.get("created_at"),
            "store_name": inv.get("store_name"),
            "pdf_url": inv.get("pdf_url"),
        })
    
    return result


@router.get("/{invoice_id}")
async def get_invoice_detail(
    invoice_id: str,
    x_user_id: str = Header(None, alias="X-User-ID")
):
    """Get a specific invoice by ID."""
    db = get_db()
    
    invoice = await db.invoices.find_one({"_id": ObjectId(invoice_id)})
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    # Verify access
    if x_user_id:
        user = await get_user_by_id(x_user_id)
        if user:
            user_id = str(user.get('_id'))
            role = user.get('role', 'user')
            
            # Check if user owns this invoice or has admin access
            is_owner = (
                invoice.get("user_id") == user_id or 
                invoice.get("user_email") == user.get("email")
            )
            is_store_member = invoice.get("store_id") == user.get("store_id")
            is_org_member = invoice.get("organization_id") == user.get("organization_id")
            
            if role == 'user' and not is_owner:
                raise HTTPException(status_code=403, detail="Access denied")
            elif role == 'store_manager' and not (is_owner or is_store_member):
                raise HTTPException(status_code=403, detail="Access denied")
            elif role == 'org_admin' and not (is_owner or is_org_member):
                raise HTTPException(status_code=403, detail="Access denied")
    
    return {
        "_id": str(invoice["_id"]),
        "invoice_number": invoice.get("invoice_number", f"INV-{str(invoice['_id'])[-6:].upper()}"),
        "amount": invoice.get("amount", 0),
        "status": invoice.get("status", "pending"),
        "description": invoice.get("description", ""),
        "invoice_type": invoice.get("invoice_type", "subscription"),
        "line_items": invoice.get("line_items", []),
        "subtotal": invoice.get("subtotal", invoice.get("amount", 0)),
        "tax": invoice.get("tax", 0),
        "total": invoice.get("total", invoice.get("amount", 0)),
        "due_date": invoice.get("due_date"),
        "paid_at": invoice.get("paid_at"),
        "payment_method": invoice.get("payment_method"),
        "created_at": invoice.get("created_at"),
        "pdf_url": invoice.get("pdf_url"),
        "notes": invoice.get("notes"),
    }


@router.post("/")
async def create_invoice(
    invoice_data: InvoiceCreate,
    x_user_id: str = Header(None, alias="X-User-ID")
):
    """Create a new invoice - Admin only."""
    db = get_db()
    
    # Verify admin access
    if x_user_id:
        user = await get_user_by_id(x_user_id)
        if not user or user.get('role') not in ['super_admin', 'org_admin']:
            raise HTTPException(status_code=403, detail="Only admins can create invoices")
    else:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    # Get target user
    target_user = await db.users.find_one({"_id": ObjectId(invoice_data.user_id)})
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Generate invoice number
    count = await db.invoices.count_documents({})
    invoice_number = f"INV-{datetime.utcnow().strftime('%Y%m')}-{str(count + 1).zfill(4)}"
    
    # Create invoice
    invoice = {
        "invoice_number": invoice_number,
        "user_id": invoice_data.user_id,
        "user_email": target_user.get("email"),
        "user_name": f"{target_user.get('first_name', '')} {target_user.get('last_name', '')}".strip(),
        "store_id": target_user.get("store_id"),
        "organization_id": target_user.get("organization_id"),
        "amount": invoice_data.amount,
        "subtotal": invoice_data.amount,
        "tax": 0,
        "total": invoice_data.amount,
        "description": invoice_data.description,
        "invoice_type": invoice_data.invoice_type,
        "status": "pending",
        "due_date": datetime.fromisoformat(invoice_data.due_date) if invoice_data.due_date else datetime.utcnow() + timedelta(days=30),
        "created_at": datetime.utcnow(),
        "created_by": x_user_id,
    }
    
    result = await db.invoices.insert_one(invoice)
    invoice["_id"] = str(result.inserted_id)
    
    return invoice


@router.patch("/{invoice_id}/status")
async def update_invoice_status(
    invoice_id: str,
    status: str,
    x_user_id: str = Header(None, alias="X-User-ID")
):
    """Update invoice status - Admin only."""
    db = get_db()
    
    # Verify admin access
    if x_user_id:
        user = await get_user_by_id(x_user_id)
        if not user or user.get('role') not in ['super_admin', 'org_admin']:
            raise HTTPException(status_code=403, detail="Only admins can update invoices")
    else:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    valid_statuses = ["pending", "paid", "overdue", "cancelled", "refunded"]
    if status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")
    
    update_data = {"status": status}
    if status == "paid":
        update_data["paid_at"] = datetime.utcnow()
    
    result = await db.invoices.update_one(
        {"_id": ObjectId(invoice_id)},
        {"$set": update_data}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    return {"success": True, "status": status}
