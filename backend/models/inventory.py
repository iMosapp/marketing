"""
Inventory Models - Flexible, industry-agnostic inventory system
Supports: Automotive, Real Estate, Retail, or any other inventory type
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class InventoryStatus(str, Enum):
    AVAILABLE = "available"
    SOLD = "sold"
    PENDING = "pending"
    RESERVED = "reserved"
    OFF_MARKET = "off_market"


class InventoryCategory(str, Enum):
    # Automotive
    VEHICLE = "vehicle"
    # Real Estate
    PROPERTY = "property"
    LISTING = "listing"
    # Retail
    PRODUCT = "product"
    # Generic
    ITEM = "item"
    CUSTOM = "custom"


class InventoryItemBase(BaseModel):
    """Base model for all inventory items"""
    external_id: str  # ID from external RMS/system
    name: str  # Display name (e.g., "2024 Honda Civic", "123 Main St")
    category: str = "item"  # vehicle, property, product, item, custom
    status: str = "available"  # available, sold, pending, reserved, off_market
    
    # Pricing
    price: Optional[float] = None
    original_price: Optional[float] = None
    currency: str = "USD"
    
    # Location/Assignment
    store_id: Optional[str] = None
    organization_id: Optional[str] = None
    assigned_to_user_id: Optional[str] = None  # Sales rep assigned
    
    # Media
    images: List[str] = []  # List of image URLs
    primary_image: Optional[str] = None
    
    # Description
    description: Optional[str] = None
    short_description: Optional[str] = None
    
    # Flexible attributes - industry specific fields go here
    attributes: Dict[str, Any] = {}
    
    # Tags for filtering
    tags: List[str] = []
    
    # Visibility
    is_featured: bool = False
    is_visible: bool = True
    
    # External system reference
    source_system: Optional[str] = None  # e.g., "salesforce", "cdk", "custom"
    source_url: Optional[str] = None  # Link to item in source system


class InventoryItemCreate(InventoryItemBase):
    """Model for creating inventory via webhook"""
    pass


class InventoryItemUpdate(BaseModel):
    """Model for updating inventory via webhook"""
    external_id: str  # Required to identify the item
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


class InventoryItemDB(InventoryItemBase):
    """Full inventory item as stored in database"""
    id: Optional[str] = Field(alias="_id", default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    created_via: str = "webhook"  # webhook, manual, import
    
    # Audit trail
    previous_status: Optional[str] = None
    status_changed_at: Optional[datetime] = None
    
    # Sale info (populated when sold)
    sold_at: Optional[datetime] = None
    sold_by_user_id: Optional[str] = None
    sold_to_contact_id: Optional[str] = None
    sale_price: Optional[float] = None

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True


# ============= AUTOMOTIVE SPECIFIC =============

class VehicleAttributes(BaseModel):
    """Common attributes for vehicles"""
    vin: Optional[str] = None
    year: Optional[int] = None
    make: Optional[str] = None
    model: Optional[str] = None
    trim: Optional[str] = None
    body_style: Optional[str] = None  # sedan, suv, truck, etc.
    exterior_color: Optional[str] = None
    interior_color: Optional[str] = None
    mileage: Optional[int] = None
    fuel_type: Optional[str] = None  # gas, diesel, electric, hybrid
    transmission: Optional[str] = None  # automatic, manual
    drivetrain: Optional[str] = None  # fwd, rwd, awd, 4wd
    engine: Optional[str] = None
    mpg_city: Optional[int] = None
    mpg_highway: Optional[int] = None
    condition: Optional[str] = None  # new, used, certified
    stock_number: Optional[str] = None


# ============= REAL ESTATE SPECIFIC =============

class PropertyAttributes(BaseModel):
    """Common attributes for real estate"""
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    country: str = "US"
    property_type: Optional[str] = None  # house, condo, townhouse, land, commercial
    listing_type: Optional[str] = None  # sale, rent, lease
    bedrooms: Optional[int] = None
    bathrooms: Optional[float] = None
    square_feet: Optional[int] = None
    lot_size: Optional[float] = None  # acres
    year_built: Optional[int] = None
    parking: Optional[str] = None
    hoa_fee: Optional[float] = None
    mls_number: Optional[str] = None


# ============= RETAIL/PRODUCT SPECIFIC =============

class ProductAttributes(BaseModel):
    """Common attributes for retail products"""
    sku: Optional[str] = None
    upc: Optional[str] = None
    brand: Optional[str] = None
    manufacturer: Optional[str] = None
    weight: Optional[float] = None
    dimensions: Optional[Dict[str, float]] = None  # length, width, height
    quantity_in_stock: Optional[int] = None
    reorder_level: Optional[int] = None
    supplier: Optional[str] = None
