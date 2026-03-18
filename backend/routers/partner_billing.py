"""
Partner Billing Router
Manages two billing layers:
- Layer 1: Platform → Partner (your negotiated pricing)
- Layer 2: Partner → Their clients (partner's pricing for their orgs/stores)
"""
from fastapi import APIRouter, HTTPException, Header
from bson import ObjectId
from datetime import datetime, timezone
import logging

from routers.database import get_db, get_user_by_id
from routers.rbac import get_user_partner_id

router = APIRouter(prefix="/admin/partner-billing", tags=["Partner Billing"])
logger = logging.getLogger(__name__)


async def get_requesting_user(user_id: str):
    if not user_id:
        return None
    return await get_user_by_id(user_id)


# ============= LAYER 1: Platform → Partner billing config =============

@router.get("/platform/{partner_id}")
async def get_platform_billing(partner_id: str, x_user_id: str = Header(None, alias="X-User-ID")):
    """Get platform billing config for a partner (super_admin only)."""
    user = await get_requesting_user(x_user_id)
    if not user or user.get('role') != 'super_admin':
        raise HTTPException(status_code=403, detail="Only super admins can view platform billing")
    
    db = get_db()
    partner = await db.white_label_partners.find_one({"_id": ObjectId(partner_id)}, {"billing_config": 1})
    if not partner:
        raise HTTPException(status_code=404, detail="Partner not found")
    
    return partner.get("billing_config", {})


@router.put("/platform/{partner_id}")
async def update_platform_billing(partner_id: str, body: dict, x_user_id: str = Header(None, alias="X-User-ID")):
    """Update platform billing config for a partner (super_admin only)."""
    user = await get_requesting_user(x_user_id)
    if not user or user.get('role') != 'super_admin':
        raise HTTPException(status_code=403, detail="Only super admins can update platform billing")
    
    db = get_db()
    billing_config = {
        "model": body.get("model", "per_store"),  # per_org, per_store, per_seat, custom
        "rate": body.get("rate"),  # amount (None = not yet negotiated)
        "currency": body.get("currency", "USD"),
        "includes_carrier": body.get("includes_carrier", False),
        "carrier_addon_rate": body.get("carrier_addon_rate"),
        "notes": body.get("notes", ""),
        "updated_at": datetime.now(timezone.utc),
        "updated_by": x_user_id,
    }
    
    await db.white_label_partners.update_one(
        {"_id": ObjectId(partner_id)},
        {"$set": {"billing_config": billing_config}}
    )
    return billing_config


@router.get("/platform-summary")
async def get_platform_billing_summary(x_user_id: str = Header(None, alias="X-User-ID")):
    """Get billing summary for all partners (super_admin only)."""
    user = await get_requesting_user(x_user_id)
    if not user or user.get('role') != 'super_admin':
        raise HTTPException(status_code=403, detail="Only super admins can view billing summary")
    
    db = get_db()
    partners = await db.white_label_partners.find(
        {"is_active": True},
        {"_id": 1, "name": 1, "billing_config": 1}
    ).to_list(100)
    
    summary = []
    for p in partners:
        pid = str(p["_id"])
        billing = p.get("billing_config", {})
        model = billing.get("model", "not_set")
        rate = billing.get("rate")
        
        # Count active orgs and stores
        org_count = await db.organizations.count_documents({"partner_id": pid, "active": {"$ne": False}})
        store_count = await db.stores.count_documents({"partner_id": pid, "active": {"$ne": False}})
        seat_count = 0
        if model == "per_seat":
            # Count active users across partner's orgs
            org_ids = [str(o["_id"]) async for o in db.organizations.find({"partner_id": pid}, {"_id": 1})]
            if org_ids:
                seat_count = await db.users.count_documents({
                    "organization_id": {"$in": org_ids},
                    "active": {"$ne": False}
                })
        
        # Calculate estimated total
        estimated_total = None
        if rate is not None:
            if model == "per_store":
                estimated_total = rate * store_count
            elif model == "per_org":
                estimated_total = rate * org_count
            elif model == "per_seat":
                estimated_total = rate * seat_count
            elif model == "custom":
                estimated_total = rate
        
        summary.append({
            "_id": pid,
            "name": p.get("name", ""),
            "billing_model": model,
            "rate": rate,
            "currency": billing.get("currency", "USD"),
            "org_count": org_count,
            "store_count": store_count,
            "seat_count": seat_count,
            "estimated_monthly": estimated_total,
            "includes_carrier": billing.get("includes_carrier", False),
            "notes": billing.get("notes", ""),
        })
    
    return summary


# ============= LAYER 2: Partner → Client billing records =============

@router.get("/client-records")
async def get_client_billing_records(x_user_id: str = Header(None, alias="X-User-ID")):
    """Get billing records for a partner's clients. Accessible by partner org_admins and super_admin."""
    user = await get_requesting_user(x_user_id)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    db = get_db()
    role = user.get('role', 'user')
    
    if role == 'super_admin':
        records = await db.partner_billing_records.find({}, {"_id": 0}).to_list(500)
        # Add _id as string
        records2 = []
        for r in await db.partner_billing_records.find({}).to_list(500):
            r["_id"] = str(r["_id"])
            records2.append(r)
        return records2
    elif role == 'org_admin':
        partner_id = await get_user_partner_id(user)
        if not partner_id:
            return []
        records = await db.partner_billing_records.find({"partner_id": partner_id}).to_list(500)
        for r in records:
            r["_id"] = str(r["_id"])
        return records
    else:
        raise HTTPException(status_code=403, detail="Only admins can view billing records")


@router.post("/client-records")
async def create_client_billing_record(body: dict, x_user_id: str = Header(None, alias="X-User-ID")):
    """Create a billing record for a partner's client."""
    user = await get_requesting_user(x_user_id)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    role = user.get('role', 'user')
    if role not in ['super_admin', 'org_admin']:
        raise HTTPException(status_code=403, detail="Only admins can create billing records")
    
    # Determine partner_id
    if role == 'super_admin':
        partner_id = body.get("partner_id")
    else:
        partner_id = await get_user_partner_id(user)
    
    if not partner_id:
        raise HTTPException(status_code=400, detail="Could not determine partner")
    
    db = get_db()
    now = datetime.now(timezone.utc)
    
    record = {
        "partner_id": partner_id,
        "client_type": body.get("client_type", "store"),  # org, store
        "client_id": body.get("client_id", ""),
        "client_name": body.get("client_name", ""),
        "billing_model": body.get("billing_model", "per_store"),  # per_org, per_store, per_seat
        "rate": body.get("rate"),
        "currency": body.get("currency", "USD"),
        "billing_contact": body.get("billing_contact", ""),
        "notes": body.get("notes", ""),
        "active": True,
        "created_by": x_user_id,
        "created_at": now,
        "updated_at": now,
    }
    
    result = await db.partner_billing_records.insert_one(record)
    record["_id"] = str(result.inserted_id)
    return record


@router.put("/client-records/{record_id}")
async def update_client_billing_record(record_id: str, body: dict, x_user_id: str = Header(None, alias="X-User-ID")):
    """Update a billing record."""
    user = await get_requesting_user(x_user_id)
    if not user or user.get('role') not in ['super_admin', 'org_admin']:
        raise HTTPException(status_code=403, detail="Only admins can update billing records")
    
    db = get_db()
    allowed_fields = ['billing_model', 'rate', 'currency', 'billing_contact', 'notes', 'active']
    update = {k: v for k, v in body.items() if k in allowed_fields}
    update['updated_at'] = datetime.now(timezone.utc)
    
    await db.partner_billing_records.update_one(
        {"_id": ObjectId(record_id)},
        {"$set": update}
    )
    return {"message": "Billing record updated"}


@router.delete("/client-records/{record_id}")
async def delete_client_billing_record(record_id: str, x_user_id: str = Header(None, alias="X-User-ID")):
    """Delete a billing record."""
    user = await get_requesting_user(x_user_id)
    if not user or user.get('role') not in ['super_admin', 'org_admin']:
        raise HTTPException(status_code=403, detail="Only admins can delete billing records")
    
    db = get_db()
    await db.partner_billing_records.delete_one({"_id": ObjectId(record_id)})
    return {"message": "Billing record deleted"}
