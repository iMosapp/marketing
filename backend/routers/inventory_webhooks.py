"""
Inventory Webhooks Router - Industry-agnostic inventory sync via webhooks
Supports: Automotive, Real Estate, Retail, or any industry

Webhook endpoints:
- POST /api/webhooks/inventory/add - Add new inventory item
- POST /api/webhooks/inventory/update - Update existing item  
- POST /api/webhooks/inventory/delete - Remove item
- POST /api/webhooks/inventory/bulk - Bulk operations
- GET /api/webhooks/inventory - List all inventory
- GET /api/webhooks/inventory/{external_id} - Get single item
"""
from fastapi import APIRouter, Depends, HTTPException, Header, Request, Query
from typing import Optional, List, Dict, Any
from datetime import datetime
from bson import ObjectId
import logging
import os

from .database import get_db

# Import inline to avoid models package conflict
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Define models inline since there's a naming conflict with models.py
from pydantic import BaseModel


class InventoryItemCreate(BaseModel):
    """Model for creating inventory via webhook"""
    external_id: str
    name: str
    category: str = "item"
    status: str = "available"
    price: Optional[float] = None
    original_price: Optional[float] = None
    currency: str = "USD"
    store_id: Optional[str] = None
    organization_id: Optional[str] = None
    assigned_to_user_id: Optional[str] = None
    images: List[str] = []
    primary_image: Optional[str] = None
    description: Optional[str] = None
    short_description: Optional[str] = None
    attributes: Dict[str, Any] = {}
    tags: List[str] = []
    is_featured: bool = False
    is_visible: bool = True
    source_system: Optional[str] = None
    source_url: Optional[str] = None


class InventoryItemUpdate(BaseModel):
    """Model for updating inventory via webhook"""
    external_id: str
    name: Optional[str] = None
    category: Optional[str] = None
    status: Optional[str] = None
    price: Optional[float] = None
    original_price: Optional[float] = None
    store_id: Optional[str] = None
    assigned_to_user_id: Optional[str] = None
    images: Optional[List[str]] = None
    primary_image: Optional[str] = None
    description: Optional[str] = None
    short_description: Optional[str] = None
    attributes: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None
    is_featured: Optional[bool] = None
    is_visible: Optional[bool] = None


class InventoryItemDelete(BaseModel):
    """Model for deleting inventory via webhook"""
    external_id: str

router = APIRouter(prefix="/webhooks/inventory", tags=["inventory-webhooks"])
logger = logging.getLogger(__name__)


# ============= AUTHENTICATION =============

async def verify_api_key(x_api_key: str = Header(None, alias="X-API-Key")):
    """Verify API key for webhook authentication"""
    if not x_api_key:
        raise HTTPException(status_code=401, detail="X-API-Key required")
    
    db = get_db()
    
    # Check organization API keys
    org = await db.organizations.find_one({"api_key": x_api_key})
    if org:
        return {"type": "organization", "id": str(org["_id"]), "name": org.get("name")}
    
    # Check store API keys
    store = await db.stores.find_one({"api_key": x_api_key})
    if store:
        return {"type": "store", "id": str(store["_id"]), "name": store.get("name")}
    
    raise HTTPException(status_code=401, detail="Invalid API key")


def serialize_item(item: dict) -> dict:
    """Convert MongoDB document to JSON-serializable dict"""
    if item:
        item["_id"] = str(item["_id"])
        # Convert datetime objects
        for key in ["created_at", "updated_at", "sold_at", "status_changed_at"]:
            if key in item and item[key]:
                item[key] = item[key].isoformat()
    return item


def tenant_scope(auth: dict) -> dict:
    """Mongo filter for the tenant behind the API key: an organization key sees its organization, a store key its store."""
    return {"organization_id": auth["id"]} if auth["type"] == "organization" else {"store_id": auth["id"]}


async def stamp_tenant(db, auth: dict, data: dict) -> dict:
    """Written items carry the key's tenant, never the body's. A store named by an organization key must be that org's."""
    if auth["type"] == "organization":
        data["organization_id"] = auth["id"]
        sid = data.get("store_id")
        if sid:
            store = await db.stores.find_one({"_id": ObjectId(str(sid))}, {"organization_id": 1}) if ObjectId.is_valid(str(sid)) else None
            if not store or str(store.get("organization_id") or "") != auth["id"]:
                raise HTTPException(status_code=400, detail="store_id is not in your organization")
    else:
        data["store_id"] = auth["id"]
        store = await db.stores.find_one({"_id": ObjectId(auth["id"])}, {"organization_id": 1}) if ObjectId.is_valid(auth["id"]) else None
        if store and store.get("organization_id"):
            data["organization_id"] = str(store["organization_id"])
    return data


# ============= WEBHOOK ENDPOINTS =============

@router.post("/add")
async def webhook_inventory_add(
    item: InventoryItemCreate,
    request: Request,
    _auth: dict = Depends(verify_api_key),
):
    """
    Add a new inventory item from external system.
    If item with same external_id exists, it will be updated instead.
    
    Example payload:
    {
        "external_id": "VIN123456789",
        "name": "2024 Honda Civic LX",
        "category": "vehicle",
        "status": "available",
        "price": 25000,
        "attributes": {
            "vin": "VIN123456789",
            "year": 2024,
            "make": "Honda",
            "model": "Civic",
            "trim": "LX",
            "mileage": 0,
            "exterior_color": "Crystal Black Pearl"
        },
        "images": ["https://example.com/car1.jpg"],
        "tags": ["new", "sedan", "honda"]
    }
    """
    db = get_db()
    scope = tenant_scope(_auth)
    
    # Check if item exists (inside this tenant only)
    existing = await db.inventory.find_one({"external_id": item.external_id, **scope})
    
    now = datetime.utcnow()
    
    if existing:
        # Update existing item
        update_data = await stamp_tenant(db, _auth, item.model_dump(exclude_unset=True))
        update_data["updated_at"] = now
        
        await db.inventory.update_one(
            {"_id": existing["_id"]},
            {"$set": update_data}
        )
        
        logger.info(f"Inventory webhook: Updated item {item.external_id}")
        return {
            "status": "updated",
            "item_id": str(existing["_id"]),
            "external_id": item.external_id,
            "message": "Inventory item updated successfully"
        }
    else:
        # Create new item
        new_item = await stamp_tenant(db, _auth, item.model_dump())
        new_item["created_at"] = now
        new_item["updated_at"] = now
        new_item["created_via"] = "webhook"
        
        result = await db.inventory.insert_one(new_item)
        
        logger.info(f"Inventory webhook: Created item {item.external_id}")
        return {
            "status": "created",
            "item_id": str(result.inserted_id),
            "external_id": item.external_id,
            "message": "Inventory item created successfully"
        }


@router.post("/update")
async def webhook_inventory_update(
    item: InventoryItemUpdate,
    request: Request,
    _auth: dict = Depends(verify_api_key),
):
    """
    Update an existing inventory item.
    Only provided fields will be updated.
    
    Example payload:
    {
        "external_id": "VIN123456789",
        "status": "sold",
        "price": 24500
    }
    """
    db = get_db()
    
    # Find existing item (inside this tenant only)
    existing = await db.inventory.find_one({"external_id": item.external_id, **tenant_scope(_auth)})
    
    if not existing:
        raise HTTPException(
            status_code=404, 
            detail=f"Inventory item with external_id '{item.external_id}' not found"
        )
    
    # Build update dict with only provided fields (tenant fields come from the key)
    update_data = await stamp_tenant(db, _auth, item.model_dump(exclude_unset=True, exclude={"external_id"}))
    update_data["updated_at"] = datetime.utcnow()
    
    # Track status changes
    if "status" in update_data and update_data["status"] != existing.get("status"):
        update_data["previous_status"] = existing.get("status")
        update_data["status_changed_at"] = datetime.utcnow()
        
        # If marked as sold, record sale timestamp
        if update_data["status"] == "sold":
            update_data["sold_at"] = datetime.utcnow()
            if "price" in update_data:
                update_data["sale_price"] = update_data["price"]
    
    # Merge attributes if provided (don't replace entirely)
    if "attributes" in update_data and existing.get("attributes"):
        merged_attrs = {**existing.get("attributes", {}), **update_data["attributes"]}
        update_data["attributes"] = merged_attrs
    
    await db.inventory.update_one(
        {"_id": existing["_id"]},
        {"$set": update_data}
    )
    
    logger.info(f"Inventory webhook: Updated item {item.external_id}")
    return {
        "status": "updated",
        "item_id": str(existing["_id"]),
        "external_id": item.external_id,
        "fields_updated": list(update_data.keys()),
        "message": "Inventory item updated successfully"
    }


@router.post("/delete")
async def webhook_inventory_delete(
    item: InventoryItemDelete,
    request: Request,
    hard_delete: bool = Query(False, description="Permanently remove item (default: soft delete)"),
    _auth: dict = Depends(verify_api_key),
):
    """
    Delete/archive an inventory item.
    By default performs soft delete (sets is_visible=false).
    Use hard_delete=true to permanently remove.
    
    Example payload:
    {
        "external_id": "VIN123456789"
    }
    """
    db = get_db()
    
    existing = await db.inventory.find_one({"external_id": item.external_id, **tenant_scope(_auth)})
    
    if not existing:
        return {
            "status": "not_found",
            "external_id": item.external_id,
            "message": "Item not found - may have already been deleted"
        }
    
    if hard_delete:
        # Permanent delete
        await db.inventory.delete_one({"_id": existing["_id"]})
        logger.info(f"Inventory webhook: Hard deleted item {item.external_id}")
        return {
            "status": "deleted",
            "item_id": str(existing["_id"]),
            "external_id": item.external_id,
            "delete_type": "hard",
            "message": "Inventory item permanently deleted"
        }
    else:
        # Soft delete - mark as invisible/archived
        await db.inventory.update_one(
            {"_id": existing["_id"]},
            {
                "$set": {
                    "is_visible": False,
                    "status": "off_market",
                    "archived_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
            }
        )
        logger.info(f"Inventory webhook: Soft deleted item {item.external_id}")
        return {
            "status": "archived",
            "item_id": str(existing["_id"]),
            "external_id": item.external_id,
            "delete_type": "soft",
            "message": "Inventory item archived (soft delete)"
        }


@router.post("/bulk")
async def webhook_inventory_bulk(
    request: Request,
    _auth: dict = Depends(verify_api_key),
):
    """
    Bulk operations for inventory items.
    Supports adding, updating, and deleting multiple items in one request.
    
    Example payload:
    {
        "operations": [
            {"action": "add", "item": {...}},
            {"action": "update", "item": {...}},
            {"action": "delete", "external_id": "..."}
        ]
    }
    """
    db = get_db()
    scope = tenant_scope(_auth)
    
    body = await request.json()
    operations = body.get("operations", [])
    
    if not operations:
        raise HTTPException(status_code=400, detail="No operations provided")
    
    results = {
        "total": len(operations),
        "successful": 0,
        "failed": 0,
        "details": []
    }
    
    for op in operations:
        action = op.get("action")
        try:
            if action == "add":
                item_data = op.get("item", {})
                item = InventoryItemCreate(**item_data)
                
                existing = await db.inventory.find_one({"external_id": item.external_id, **scope})
                now = datetime.utcnow()
                
                if existing:
                    update_data = await stamp_tenant(db, _auth, item.model_dump(exclude_unset=True))
                    update_data["updated_at"] = now
                    await db.inventory.update_one({"_id": existing["_id"]}, {"$set": update_data})
                    results["details"].append({"action": "add", "external_id": item.external_id, "result": "updated"})
                else:
                    new_item = await stamp_tenant(db, _auth, item.model_dump())
                    new_item["created_at"] = now
                    new_item["updated_at"] = now
                    new_item["created_via"] = "webhook"
                    await db.inventory.insert_one(new_item)
                    results["details"].append({"action": "add", "external_id": item.external_id, "result": "created"})
                
                results["successful"] += 1
                
            elif action == "update":
                item_data = op.get("item", {})
                item = InventoryItemUpdate(**item_data)
                
                existing = await db.inventory.find_one({"external_id": item.external_id, **scope})
                if existing:
                    update_data = await stamp_tenant(db, _auth, item.model_dump(exclude_unset=True, exclude={"external_id"}))
                    update_data["updated_at"] = datetime.utcnow()
                    await db.inventory.update_one({"_id": existing["_id"]}, {"$set": update_data})
                    results["details"].append({"action": "update", "external_id": item.external_id, "result": "updated"})
                    results["successful"] += 1
                else:
                    results["details"].append({"action": "update", "external_id": item.external_id, "result": "not_found"})
                    results["failed"] += 1
                    
            elif action == "delete":
                external_id = op.get("external_id")
                existing = await db.inventory.find_one({"external_id": external_id, **scope})
                if existing:
                    await db.inventory.update_one(
                        {"_id": existing["_id"]},
                        {"$set": {"is_visible": False, "status": "off_market", "updated_at": datetime.utcnow()}}
                    )
                    results["details"].append({"action": "delete", "external_id": external_id, "result": "archived"})
                    results["successful"] += 1
                else:
                    results["details"].append({"action": "delete", "external_id": external_id, "result": "not_found"})
                    results["failed"] += 1
            else:
                results["details"].append({"action": action, "result": "unknown_action"})
                results["failed"] += 1
                
        except Exception as e:
            results["details"].append({"action": action, "error": str(e)})
            results["failed"] += 1
    
    logger.info(f"Inventory webhook bulk: {results['successful']} successful, {results['failed']} failed")
    return results


# ============= QUERY ENDPOINTS =============

@router.get("")
async def list_inventory(
    category: Optional[str] = Query(None, description="Filter by category (vehicle, property, product, etc.)"),
    status: Optional[str] = Query(None, description="Filter by status (available, sold, pending)"),
    store_id: Optional[str] = Query(None, description="Filter by store"),
    tag: Optional[str] = Query(None, description="Filter by tag"),
    search: Optional[str] = Query(None, description="Search in name and description"),
    is_featured: Optional[bool] = Query(None, description="Filter featured items"),
    min_price: Optional[float] = Query(None, description="Minimum price"),
    max_price: Optional[float] = Query(None, description="Maximum price"),
    sort_by: str = Query("updated_at", description="Sort field"),
    sort_order: str = Query("desc", description="Sort order (asc/desc)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    include_hidden: bool = Query(False, description="Include hidden/archived items"),
    _auth: dict = Depends(verify_api_key),
):
    """
    List inventory items with filtering and pagination (this tenant's items only).
    """
    db = get_db()
    
    # Build query
    query = dict(tenant_scope(_auth))
    
    if not include_hidden:
        query["is_visible"] = {"$ne": False}
    
    if category:
        query["category"] = category
    if status:
        query["status"] = status
    if store_id and _auth["type"] == "organization":
        query["store_id"] = store_id
    if tag:
        query["tags"] = tag
    if is_featured is not None:
        query["is_featured"] = is_featured
    if min_price is not None:
        query["price"] = {"$gte": min_price}
    if max_price is not None:
        query.setdefault("price", {})["$lte"] = max_price
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"description": {"$regex": search, "$options": "i"}},
            {"short_description": {"$regex": search, "$options": "i"}}
        ]
    
    # Sort
    sort_direction = -1 if sort_order == "desc" else 1
    
    # Execute query
    cursor = db.inventory.find(query).sort(sort_by, sort_direction).skip(skip).limit(limit)
    items = await cursor.to_list(length=limit)
    total = await db.inventory.count_documents(query)
    
    # Serialize
    items = [serialize_item(item) for item in items]
    
    return {
        "items": items,
        "total": total,
        "skip": skip,
        "limit": limit,
        "has_more": (skip + limit) < total
    }


@router.get("/{external_id}")
async def get_inventory_item(
    external_id: str,
    _auth: dict = Depends(verify_api_key),
):
    """Get a single inventory item by external_id (this tenant's only)"""
    db = get_db()
    
    item = await db.inventory.find_one({"external_id": external_id, **tenant_scope(_auth)})
    
    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    
    return serialize_item(item)


# ============= CONFIGURATION ENDPOINT =============

@router.get("/config/endpoints")
async def get_inventory_webhook_config():
    """
    Get webhook configuration and example payloads for integration setup.
    Share this with your RMS/inventory system to configure webhooks.
    """
    base_url = os.environ.get("REACT_APP_BACKEND_URL", "https://app.imonsocial.com")
    
    return {
        "webhook_endpoints": {
            "add_item": {
                "url": f"{base_url}/api/webhooks/inventory/add",
                "method": "POST",
                "description": "Add or update inventory item"
            },
            "update_item": {
                "url": f"{base_url}/api/webhooks/inventory/update",
                "method": "POST", 
                "description": "Update existing item (partial update)"
            },
            "delete_item": {
                "url": f"{base_url}/api/webhooks/inventory/delete",
                "method": "POST",
                "description": "Archive or delete item"
            },
            "bulk_operations": {
                "url": f"{base_url}/api/webhooks/inventory/bulk",
                "method": "POST",
                "description": "Multiple operations in one request"
            },
            "list_items": {
                "url": f"{base_url}/api/webhooks/inventory",
                "method": "GET",
                "description": "Query inventory with filters"
            }
        },
        "authentication": {
            "method": "API Key",
            "header": "X-API-Key",
            "description": "Include your API key in the X-API-Key header"
        },
        "example_payloads": {
            "automotive": {
                "external_id": "VIN_1HGCV1F34NA123456",
                "name": "2024 Honda Civic LX Sedan",
                "category": "vehicle",
                "status": "available",
                "price": 25995,
                "images": ["https://example.com/civic-front.jpg", "https://example.com/civic-side.jpg"],
                "primary_image": "https://example.com/civic-front.jpg",
                "description": "Brand new 2024 Honda Civic with Honda Sensing suite",
                "tags": ["new", "sedan", "honda", "fuel-efficient"],
                "attributes": {
                    "vin": "1HGCV1F34NA123456",
                    "year": 2024,
                    "make": "Honda",
                    "model": "Civic",
                    "trim": "LX",
                    "body_style": "sedan",
                    "exterior_color": "Crystal Black Pearl",
                    "interior_color": "Black",
                    "mileage": 12,
                    "fuel_type": "gas",
                    "transmission": "CVT",
                    "drivetrain": "FWD",
                    "engine": "2.0L 4-Cylinder",
                    "mpg_city": 31,
                    "mpg_highway": 40,
                    "condition": "new",
                    "stock_number": "HC2024-001"
                }
            },
            "real_estate": {
                "external_id": "MLS_12345678",
                "name": "Modern 4BR Home in South Jordan",
                "category": "property",
                "status": "available",
                "price": 575000,
                "images": ["https://example.com/home-front.jpg"],
                "description": "Beautiful modern home with mountain views",
                "tags": ["single-family", "4-bedroom", "south-jordan"],
                "attributes": {
                    "address": "123 Mountain View Dr",
                    "city": "South Jordan",
                    "state": "UT",
                    "zip_code": "84095",
                    "property_type": "house",
                    "listing_type": "sale",
                    "bedrooms": 4,
                    "bathrooms": 3.5,
                    "square_feet": 3200,
                    "lot_size": 0.25,
                    "year_built": 2022,
                    "parking": "3-car garage",
                    "hoa_fee": 50,
                    "mls_number": "12345678"
                }
            },
            "retail_product": {
                "external_id": "SKU_WIDGET_001",
                "name": "Premium Widget Pro",
                "category": "product",
                "status": "available",
                "price": 49.99,
                "original_price": 79.99,
                "images": ["https://example.com/widget.jpg"],
                "description": "Our best-selling premium widget",
                "tags": ["sale", "popular", "widgets"],
                "attributes": {
                    "sku": "WIDGET_001",
                    "brand": "WidgetCo",
                    "quantity_in_stock": 150,
                    "weight": 2.5
                }
            },
            "status_update": {
                "external_id": "VIN_1HGCV1F34NA123456",
                "status": "sold",
                "price": 24500
            },
            "bulk_operation": {
                "operations": [
                    {"action": "add", "item": {"external_id": "ITEM_001", "name": "Item 1", "category": "product", "price": 100}},
                    {"action": "update", "item": {"external_id": "ITEM_002", "status": "sold"}},
                    {"action": "delete", "external_id": "ITEM_003"}
                ]
            }
        },
        "supported_categories": ["vehicle", "property", "listing", "product", "item", "custom"],
        "supported_statuses": ["available", "sold", "pending", "reserved", "off_market"]
    }
