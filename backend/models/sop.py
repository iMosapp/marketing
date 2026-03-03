"""
SOP (Standard Operating Procedure) Models
Internal documentation system for i'M On Social employees
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class SOPDepartment(str, Enum):
    """Departments that can have SOPs"""
    ALL = "all"
    SALES = "sales"
    SUPPORT = "support"
    BILLING = "billing"
    ADMIN = "admin"
    ONBOARDING = "onboarding"
    MANAGEMENT = "management"
    PARTNERS = "partners"


class SOPCategory(str, Enum):
    """Categories of SOPs"""
    GETTING_STARTED = "getting_started"
    DAILY_OPERATIONS = "daily_operations"
    CUSTOMER_COMMUNICATION = "customer_communication"
    ADMIN_TASKS = "admin_tasks"
    TROUBLESHOOTING = "troubleshooting"
    BEST_PRACTICES = "best_practices"
    POLICIES = "policies"
    TOOLS_FEATURES = "tools_features"


class SOPStep(BaseModel):
    """Individual step in an SOP"""
    order: int
    title: str
    description: str
    screenshot_url: Optional[str] = None
    video_url: Optional[str] = None
    tip: Optional[str] = None
    warning: Optional[str] = None
    link_text: Optional[str] = None
    link_url: Optional[str] = None


class SOPCreate(BaseModel):
    """Create a new SOP"""
    title: str
    summary: str
    department: SOPDepartment = SOPDepartment.ALL
    category: SOPCategory
    steps: List[SOPStep]
    tags: List[str] = []
    estimated_time: Optional[str] = None  # e.g., "5 minutes"
    difficulty: str = "beginner"  # beginner, intermediate, advanced
    related_sops: List[str] = []  # List of SOP IDs
    video_walkthrough_url: Optional[str] = None
    is_required_reading: bool = False
    is_published: bool = True


class SOPUpdate(BaseModel):
    """Update an existing SOP"""
    title: Optional[str] = None
    summary: Optional[str] = None
    department: Optional[SOPDepartment] = None
    category: Optional[SOPCategory] = None
    steps: Optional[List[SOPStep]] = None
    tags: Optional[List[str]] = None
    estimated_time: Optional[str] = None
    difficulty: Optional[str] = None
    related_sops: Optional[List[str]] = None
    video_walkthrough_url: Optional[str] = None
    is_required_reading: Optional[bool] = None
    is_published: Optional[bool] = None


class SOPReadProgress(BaseModel):
    """Track user's reading progress"""
    user_id: str
    sop_id: str
    completed: bool = False
    completed_at: Optional[datetime] = None
    current_step: int = 0
    last_viewed_at: datetime = Field(default_factory=datetime.utcnow)


class SOPFeedback(BaseModel):
    """User feedback on an SOP"""
    user_id: str
    sop_id: str
    helpful: bool
    comment: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
