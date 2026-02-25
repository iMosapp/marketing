from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from bson import ObjectId

class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v, handler=None):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)

    @classmethod
    def __get_pydantic_json_schema__(cls, field_schema):
        field_schema.update(type="string")

# ============= ORGANIZATION & ACCOUNT MODELS =============

class Organization(BaseModel):
    """Top-level organization (e.g., Ken Garff Auto Group)"""
    id: Optional[str] = Field(alias="_id", default=None)
    name: str
    slug: str  # URL-friendly name
    account_type: str = "organization"  # organization or independent
    
    # Contact info
    admin_email: str
    admin_phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: str = "US"
    
    # Twilio/10DLC info
    twilio_account_sid: Optional[str] = None
    twilio_auth_token: Optional[str] = None
    ten_dlc_brand_id: Optional[str] = None
    ten_dlc_campaign_id: Optional[str] = None
    ten_dlc_status: str = "pending"  # pending, submitted, approved, rejected
    
    # Settings
    max_stores: int = 10
    max_users_per_store: int = 50
    features: List[str] = []  # enabled features
    
    # Status
    active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True

class OrganizationCreate(BaseModel):
    name: str
    account_type: str = "organization"  # organization or independent
    admin_email: str
    admin_phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: str = "US"

class Store(BaseModel):
    """A store/dealership under an organization"""
    id: Optional[str] = Field(alias="_id", default=None)
    organization_id: str
    name: str
    slug: str  # URL-friendly name
    
    # Contact info
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: str = "US"
    website: Optional[str] = None
    
    # Branding
    logo_url: Optional[str] = None
    cover_image_url: Optional[str] = None
    primary_color: str = "#007AFF"
    
    # Business Hours (24hr format, null = closed)
    business_hours: dict = Field(default_factory=lambda: {
        "monday": {"open": "09:00", "close": "18:00"},
        "tuesday": {"open": "09:00", "close": "18:00"},
        "wednesday": {"open": "09:00", "close": "18:00"},
        "thursday": {"open": "09:00", "close": "18:00"},
        "friday": {"open": "09:00", "close": "18:00"},
        "saturday": {"open": "09:00", "close": "17:00"},
        "sunday": None  # Closed
    })
    timezone: str = "America/Denver"
    
    # Social Media Links
    social_links: dict = Field(default_factory=lambda: {
        "facebook": None,
        "instagram": None,
        "twitter": None,
        "youtube": None,
        "tiktok": None,
        "linkedin": None
    })
    
    # Twilio phone number for this store
    twilio_phone_number: Optional[str] = None
    
    # Review Links
    review_links: dict = Field(default_factory=lambda: {
        "google": None,
        "yelp": None,
        "facebook": None,
        "dealerrater": None,
        "cars_com": None,
        "custom": []  # List of {name: str, url: str}
    })
    
    # Settings
    max_users: int = 50
    
    # Status
    active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True

class StoreCreate(BaseModel):
    organization_id: Optional[str] = None
    name: str
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: str = "US"

# ============= USER MODELS (Updated with roles) =============

class UserPersona(BaseModel):
    tone: str = "casual"  # casual, formal, professional
    emoji_use: str = "moderate"  # none, light, moderate, heavy
    humor_level: str = "some"  # none, some, lots
    brevity: str = "balanced"  # brief, balanced, detailed
    professional_identity: str = ""
    interests: List[str] = []
    escalation_keywords: List[str] = []

class UserCreate(BaseModel):
    email: str
    phone: str
    name: str
    password: str
    mode: str = "rep"  # rep or enterprise
    
    # Organization/Role info (optional for backward compatibility)
    organization_id: Optional[str] = None
    store_id: Optional[str] = None
    role: str = "user"  # super_admin, org_admin, store_manager, user

class User(BaseModel):
    id: Optional[str] = Field(alias="_id", default=None)
    email: str
    phone: str
    name: str
    password: str  # Should be hashed in production
    mode: str = "rep"
    
    # Organization & Role
    organization_id: Optional[str] = None  # Which org they belong to
    store_id: Optional[str] = None  # Primary store (legacy, kept for backward compatibility)
    store_ids: List[str] = []  # All stores user is assigned to (supports multi-store)
    role: str = "user"  # super_admin, org_admin, store_manager, user
    is_active: bool = True  # User status
    
    # For independents - gamification visibility
    leaderboard_visible: bool = False
    compare_scope: str = "state"  # state, region, country
    
    # iMOs settings
    mvpline_number: Optional[str] = None
    persona: Optional[UserPersona] = None
    onboarding_complete: bool = False
    
    # Stats for leaderboards
    stats: Dict[str, int] = {
        "contacts_added": 0,
        "messages_sent": 0,
        "calls_made": 0,
        "deals_closed": 0,
    }
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True

# Contact Models
# Custom Date Field model
class CustomDateField(BaseModel):
    name: str  # e.g., "Lease Expiration", "Next Service"
    date: Optional[datetime] = None
    
class Contact(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    user_id: str
    first_name: str
    last_name: Optional[str] = None
    phone: str
    email: Optional[str] = None
    photo: Optional[str] = None  # high-res photo (excluded from list queries)
    photo_thumbnail: Optional[str] = None  # tiny avatar for fast loading (~3-5KB)
    photo_url: Optional[str] = None  # thumbnail for display
    tags: List[str] = []
    notes: str = ""
    vehicle: Optional[str] = None
    
    # Important dates
    birthday: Optional[datetime] = None
    anniversary: Optional[datetime] = None
    date_sold: Optional[datetime] = None  # When they purchased/were sold to
    custom_dates: List[CustomDateField] = []  # Additional custom dates
    
    purchase_date: Optional[datetime] = None  # Legacy - alias for date_sold
    source: str = "manual"  # manual, csv, phone_contacts
    # Referral tracking
    referred_by: Optional[str] = None  # Contact ID of referrer
    referred_by_name: Optional[str] = None  # Cached name for display
    referral_count: int = 0  # Number of people this contact has referred
    referral_notes: Optional[str] = None  # Notes about the referral
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

class ContactCreate(BaseModel):
    first_name: str
    last_name: Optional[str] = None
    phone: str
    email: Optional[str] = None
    photo: Optional[str] = None  # base64 encoded image
    tags: List[str] = []
    notes: str = ""
    vehicle: Optional[str] = None
    
    # Important dates
    birthday: Optional[datetime] = None
    anniversary: Optional[datetime] = None
    date_sold: Optional[datetime] = None
    custom_dates: List[CustomDateField] = []
    
    purchase_date: Optional[datetime] = None
    referred_by: Optional[str] = None
    referred_by_name: Optional[str] = None
    referral_notes: Optional[str] = None

# Conversation Models
class Conversation(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    user_id: str
    contact_id: str
    status: str = "active"  # active, passive, archived
    ai_enabled: bool = True
    ai_mode: str = "draft_only"  # draft_only, assisted, auto_reply
    last_message_at: datetime = Field(default_factory=datetime.utcnow)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

# Message Models
class Message(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    conversation_id: str
    sender: str  # user, contact, ai
    content: str
    media_url: Optional[str] = None
    intent_detected: Optional[str] = None  # buying_intent, price_question, appointment, etc.
    ai_generated: bool = False
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

class MessageCreate(BaseModel):
    conversation_id: str
    content: str
    media_url: Optional[str] = None
    template_id: Optional[str] = None
    template_type: Optional[str] = None  # review, referral, sold, greeting, follow_up, etc.
    template_name: Optional[str] = None

# Call Models
class Call(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    user_id: str
    contact_id: str
    type: str  # inbound, outbound, missed
    duration: int = 0  # seconds
    voicemail_url: Optional[str] = None
    transcription: Optional[str] = None
    auto_text_sent: bool = False
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

class CallCreate(BaseModel):
    contact_id: str
    type: str
    duration: int = 0

# Campaign Models
class CampaignSequenceStep(BaseModel):
    step: int
    message_template: str
    delay_days: int = 0
    delay_months: int = 0
    media_urls: List[str] = []  # Media attachments for this step

class Campaign(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    user_id: str
    name: str
    type: str = "custom"  # birthday, anniversary, check_in, sold_followup, custom
    trigger_tag: str = ""  # Tag that triggers this campaign
    segment_tags: List[str] = []
    message_template: str = ""  # Legacy single message
    media_urls: List[str] = []  # Media attachments (legacy single message)
    sequences: List[CampaignSequenceStep] = []  # Multi-step sequences
    send_time: str = "10:00"  # HH:MM format
    schedule: Dict[str, Any] = {}  # frequency, timing, etc.
    active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

class CampaignCreate(BaseModel):
    name: str
    type: str = "custom"
    trigger_tag: str = ""
    segment_tags: List[str] = []
    message_template: str = ""
    media_urls: List[str] = []  # Media attachments
    sequences: List[CampaignSequenceStep] = []
    send_time: str = "10:00"
    schedule: Dict[str, Any] = {}
    active: bool = True

# Campaign Enrollment - tracks contacts enrolled in campaigns
class CampaignEnrollment(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    user_id: str
    campaign_id: str
    contact_id: str
    contact_name: str = ""
    contact_phone: str = ""
    current_step: int = 1  # Which step in the sequence
    status: str = "active"  # active, completed, paused, cancelled
    enrolled_at: datetime = Field(default_factory=datetime.utcnow)
    next_send_at: Optional[datetime] = None  # When to send the next message
    messages_sent: List[Dict[str, Any]] = []  # History of sent messages
    
    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

# Task Models
class Task(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    user_id: str
    contact_id: Optional[str] = None
    type: str  # callback, follow_up, appointment
    title: str
    description: str = ""
    due_date: datetime
    priority: str = "medium"  # low, medium, high
    completed: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

class TaskCreate(BaseModel):
    contact_id: Optional[str] = None
    type: str
    title: str
    description: str = ""
    due_date: datetime
    priority: str = "medium"  # low, medium, high
    completed: bool = False


# Message Template Models
class MessageTemplate(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    user_id: str
    name: str
    content: str
    category: str = "general"  # general, greeting, follow_up, appointment, thank_you, review_request
    is_default: bool = False  # System default templates
    usage_count: int = 0  # Track how often template is used
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class MessageTemplateCreate(BaseModel):
    name: str
    content: str
    category: str = "general"


class MessageTemplateUpdate(BaseModel):
    name: Optional[str] = None
    content: Optional[str] = None
    category: Optional[str] = None


# Customer Feedback/Review Model
class CustomerFeedback(BaseModel):
    """Stores feedback submitted via the public review page"""
    id: Optional[str] = Field(alias="_id", default=None)
    store_id: str
    contact_id: Optional[str] = None  # Link to contact if known
    
    # Customer info
    customer_name: str
    customer_phone: Optional[str] = None
    customer_email: Optional[str] = None
    
    # Feedback content
    rating: int = 5  # 1-5 stars
    text_review: Optional[str] = None
    
    # Photo consent
    photo_consent: bool = False
    photo_url: Optional[str] = None
    
    # Which platform they clicked (if any)
    review_platform_clicked: Optional[str] = None  # google, yelp, etc.
    
    # Source tracking
    salesperson_id: Optional[str] = None  # Who sent the review request
    salesperson_name: Optional[str] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True