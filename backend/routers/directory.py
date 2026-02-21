"""
Company Directory & Performance Tracking
Roles: Partners, Resellers, Support, Billing, Admin, Dev, Sales, CSM
"""
from fastapi import APIRouter, HTTPException, Query
from bson import ObjectId
from datetime import datetime, timedelta
from typing import Optional, List
from pydantic import BaseModel, EmailStr
import logging

from routers.database import get_db

router = APIRouter(prefix="/directory", tags=["directory"])
logger = logging.getLogger(__name__)


# ============= MODELS =============

TEAM_ROLES = [
    "partner",
    "reseller", 
    "support",
    "billing",
    "admin",
    "dev",
    "sales",
    "csm",  # Customer Success Manager
]

ROLE_LABELS = {
    "partner": "Partner",
    "reseller": "Reseller",
    "support": "Support",
    "billing": "Billing",
    "admin": "Admin",
    "dev": "Developer",
    "sales": "Sales",
    "csm": "CSM",
}


class TeamMemberCreate(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    phone: Optional[str] = None
    role: str
    title: Optional[str] = None
    department: Optional[str] = None
    # Reseller/Partner specific
    company_name: Optional[str] = None
    commission_percent: Optional[float] = None
    agreement_doc_url: Optional[str] = None
    agreement_signed_at: Optional[datetime] = None
    # Profile
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    linkedin_url: Optional[str] = None
    timezone: Optional[str] = "America/New_York"
    is_active: bool = True


class TeamMemberUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    role: Optional[str] = None
    title: Optional[str] = None
    department: Optional[str] = None
    company_name: Optional[str] = None
    commission_percent: Optional[float] = None
    agreement_doc_url: Optional[str] = None
    agreement_signed_at: Optional[datetime] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    linkedin_url: Optional[str] = None
    timezone: Optional[str] = None
    is_active: Optional[bool] = None
    # Pay/compensation
    hourly_rate: Optional[float] = None
    base_salary: Optional[float] = None


class WeeklyKPIInput(BaseModel):
    hours_worked: float
    demos_done: int
    week_start: Optional[str] = None  # ISO date string, defaults to current week


# ============= TEAM DIRECTORY =============

@router.get("/roles")
async def get_roles():
    """Get all available team roles"""
    return {
        "roles": TEAM_ROLES,
        "labels": ROLE_LABELS,
    }


@router.post("/members")
async def create_team_member(data: TeamMemberCreate):
    """Create a new team member"""
    db = get_db()
    
    if data.role not in TEAM_ROLES:
        raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of: {TEAM_ROLES}")
    
    # Check for duplicate email
    existing = await db.team_members.find_one({"email": data.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already exists in directory")
    
    member = {
        **data.dict(),
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        # Performance metrics (will be updated by tracking)
        "metrics": {
            "quotes_sent": 0,
            "quotes_accepted": 0,
            "total_revenue": 0.0,
            "total_discounts_given": 0.0,
            "avg_discount_percent": 0.0,
            "avg_deal_size": 0.0,
            "avg_days_to_close": 0.0,
            "total_commission_earned": 0.0,
        }
    }
    
    result = await db.team_members.insert_one(member)
    
    logger.info(f"Team member created: {data.first_name} {data.last_name} ({data.role})")
    
    return {
        "id": str(result.inserted_id),
        "message": "Team member created successfully",
    }


@router.get("/members")
async def list_team_members(
    role: Optional[str] = None,
    is_active: Optional[bool] = True,
    search: Optional[str] = None,
):
    """List all team members with optional filters"""
    db = get_db()
    
    query = {}
    if role:
        query["role"] = role
    if is_active is not None:
        query["is_active"] = is_active
    if search:
        query["$or"] = [
            {"first_name": {"$regex": search, "$options": "i"}},
            {"last_name": {"$regex": search, "$options": "i"}},
            {"email": {"$regex": search, "$options": "i"}},
            {"company_name": {"$regex": search, "$options": "i"}},
        ]
    
    members = await db.team_members.find(query).sort("last_name", 1).to_list(500)
    
    return [
        {
            "id": str(m["_id"]),
            "first_name": m["first_name"],
            "last_name": m["last_name"],
            "email": m["email"],
            "phone": m.get("phone"),
            "role": m["role"],
            "role_label": ROLE_LABELS.get(m["role"], m["role"]),
            "title": m.get("title"),
            "department": m.get("department"),
            "company_name": m.get("company_name"),
            "commission_percent": m.get("commission_percent"),
            "avatar_url": m.get("avatar_url"),
            "is_active": m.get("is_active", True),
            "metrics": m.get("metrics", {}),
            "created_at": m["created_at"].isoformat() if m.get("created_at") else None,
        }
        for m in members
    ]


@router.get("/members/{member_id}")
async def get_team_member(member_id: str):
    """Get a team member's full profile"""
    db = get_db()
    
    member = await db.team_members.find_one({"_id": ObjectId(member_id)})
    if not member:
        raise HTTPException(status_code=404, detail="Team member not found")
    
    # Get their activity history
    activities = await db.member_activities.find(
        {"member_id": member_id}
    ).sort("created_at", -1).limit(20).to_list(20)
    
    return {
        "id": str(member["_id"]),
        "first_name": member["first_name"],
        "last_name": member["last_name"],
        "email": member["email"],
        "phone": member.get("phone"),
        "role": member["role"],
        "role_label": ROLE_LABELS.get(member["role"], member["role"]),
        "title": member.get("title"),
        "department": member.get("department"),
        "company_name": member.get("company_name"),
        "commission_percent": member.get("commission_percent"),
        "agreement_doc_url": member.get("agreement_doc_url"),
        "agreement_signed_at": member.get("agreement_signed_at").isoformat() if member.get("agreement_signed_at") else None,
        "avatar_url": member.get("avatar_url"),
        "bio": member.get("bio"),
        "linkedin_url": member.get("linkedin_url"),
        "timezone": member.get("timezone"),
        "is_active": member.get("is_active", True),
        "metrics": member.get("metrics", {}),
        "created_at": member["created_at"].isoformat() if member.get("created_at") else None,
        "recent_activities": [
            {
                "id": str(a["_id"]),
                "type": a["type"],
                "description": a["description"],
                "amount": a.get("amount"),
                "created_at": a["created_at"].isoformat(),
            }
            for a in activities
        ],
    }


@router.put("/members/{member_id}")
async def update_team_member(member_id: str, data: TeamMemberUpdate):
    """Update a team member"""
    db = get_db()
    
    update_data = {k: v for k, v in data.dict().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    if "role" in update_data and update_data["role"] not in TEAM_ROLES:
        raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of: {TEAM_ROLES}")
    
    update_data["updated_at"] = datetime.utcnow()
    
    result = await db.team_members.update_one(
        {"_id": ObjectId(member_id)},
        {"$set": update_data}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Team member not found")
    
    return {"success": True, "message": "Team member updated"}


@router.delete("/members/{member_id}")
async def delete_team_member(member_id: str):
    """Soft delete a team member (set inactive)"""
    db = get_db()
    
    result = await db.team_members.update_one(
        {"_id": ObjectId(member_id)},
        {"$set": {"is_active": False, "updated_at": datetime.utcnow()}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Team member not found")
    
    return {"success": True, "message": "Team member deactivated"}


# ============= PERFORMANCE TRACKING =============

@router.post("/members/{member_id}/track-activity")
async def track_activity(
    member_id: str,
    activity_type: str,
    description: str,
    amount: Optional[float] = None,
    quote_id: Optional[str] = None,
    deal_id: Optional[str] = None,
    days_to_close: Optional[int] = None,
    discount_percent: Optional[float] = None,
):
    """Track an activity for a team member"""
    db = get_db()
    
    # Verify member exists
    member = await db.team_members.find_one({"_id": ObjectId(member_id)})
    if not member:
        raise HTTPException(status_code=404, detail="Team member not found")
    
    activity = {
        "member_id": member_id,
        "type": activity_type,
        "description": description,
        "amount": amount,
        "quote_id": quote_id,
        "deal_id": deal_id,
        "days_to_close": days_to_close,
        "discount_percent": discount_percent,
        "created_at": datetime.utcnow(),
    }
    
    await db.member_activities.insert_one(activity)
    
    # Update member metrics based on activity type
    metrics_update = {}
    
    if activity_type == "quote_sent":
        metrics_update["metrics.quotes_sent"] = 1
    elif activity_type == "quote_accepted":
        metrics_update["metrics.quotes_accepted"] = 1
        if amount:
            metrics_update["metrics.total_revenue"] = amount
            # Calculate commission if applicable
            if member.get("commission_percent"):
                commission = amount * (member["commission_percent"] / 100)
                metrics_update["metrics.total_commission_earned"] = commission
    elif activity_type == "discount_applied":
        if discount_percent:
            metrics_update["metrics.total_discounts_given"] = discount_percent
    
    if metrics_update:
        await db.team_members.update_one(
            {"_id": ObjectId(member_id)},
            {"$inc": metrics_update}
        )
    
    # Recalculate averages
    await recalculate_member_metrics(member_id)
    
    return {"success": True, "message": "Activity tracked"}


async def recalculate_member_metrics(member_id: str):
    """Recalculate average metrics for a team member"""
    db = get_db()
    
    # Get all activities for this member
    activities = await db.member_activities.find({"member_id": member_id}).to_list(None)
    
    if not activities:
        return
    
    # Calculate averages
    accepted_quotes = [a for a in activities if a["type"] == "quote_accepted"]
    discounts = [a for a in activities if a.get("discount_percent")]
    close_times = [a for a in activities if a.get("days_to_close")]
    
    avg_deal_size = 0
    avg_discount = 0
    avg_days_to_close = 0
    
    if accepted_quotes:
        amounts = [a["amount"] for a in accepted_quotes if a.get("amount")]
        if amounts:
            avg_deal_size = sum(amounts) / len(amounts)
    
    if discounts:
        discount_values = [a["discount_percent"] for a in discounts]
        avg_discount = sum(discount_values) / len(discount_values)
    
    if close_times:
        days_values = [a["days_to_close"] for a in close_times]
        avg_days_to_close = sum(days_values) / len(days_values)
    
    await db.team_members.update_one(
        {"_id": ObjectId(member_id)},
        {"$set": {
            "metrics.avg_deal_size": round(avg_deal_size, 2),
            "metrics.avg_discount_percent": round(avg_discount, 2),
            "metrics.avg_days_to_close": round(avg_days_to_close, 1),
        }}
    )


# ============= LEADERBOARDS =============

@router.get("/leaderboard")
async def get_leaderboard(
    metric: str = "total_revenue",
    role: Optional[str] = None,
    period: str = "all_time",
    limit: int = 10,
):
    """Get leaderboard rankings by various metrics"""
    db = get_db()
    
    valid_metrics = [
        "total_revenue",
        "quotes_sent",
        "quotes_accepted",
        "avg_deal_size",
        "avg_days_to_close",
        "total_commission_earned",
    ]
    
    if metric not in valid_metrics:
        raise HTTPException(status_code=400, detail=f"Invalid metric. Must be one of: {valid_metrics}")
    
    query = {"is_active": True}
    if role:
        query["role"] = role
    
    # For time-based filtering, we'd need to aggregate from activities
    # For now, use cumulative metrics
    sort_field = f"metrics.{metric}"
    sort_order = -1  # Descending (higher is better)
    
    # For avg_days_to_close, lower is better
    if metric == "avg_days_to_close":
        sort_order = 1
    
    members = await db.team_members.find(query).sort(sort_field, sort_order).limit(limit).to_list(limit)
    
    leaderboard = []
    for rank, m in enumerate(members, 1):
        metrics = m.get("metrics", {})
        leaderboard.append({
            "rank": rank,
            "id": str(m["_id"]),
            "name": f"{m['first_name']} {m['last_name']}",
            "role": m["role"],
            "role_label": ROLE_LABELS.get(m["role"], m["role"]),
            "company_name": m.get("company_name"),
            "avatar_url": m.get("avatar_url"),
            "metric_value": metrics.get(metric, 0),
            "metric_name": metric,
            "all_metrics": {
                "total_revenue": metrics.get("total_revenue", 0),
                "quotes_sent": metrics.get("quotes_sent", 0),
                "quotes_accepted": metrics.get("quotes_accepted", 0),
                "conversion_rate": round(
                    (metrics.get("quotes_accepted", 0) / max(metrics.get("quotes_sent", 1), 1)) * 100, 1
                ),
                "avg_deal_size": metrics.get("avg_deal_size", 0),
                "avg_days_to_close": metrics.get("avg_days_to_close", 0),
                "avg_discount_percent": metrics.get("avg_discount_percent", 0),
                "total_commission_earned": metrics.get("total_commission_earned", 0),
            },
        })
    
    return {
        "metric": metric,
        "period": period,
        "role_filter": role,
        "leaderboard": leaderboard,
    }


@router.get("/stats/overview")
async def get_directory_stats():
    """Get overall directory statistics"""
    db = get_db()
    
    # Count by role
    pipeline = [
        {"$match": {"is_active": True}},
        {"$group": {"_id": "$role", "count": {"$sum": 1}}},
    ]
    role_counts = await db.team_members.aggregate(pipeline).to_list(None)
    
    # Calculate totals
    total_members = sum(r["count"] for r in role_counts)
    
    # Aggregate performance metrics
    all_members = await db.team_members.find({"is_active": True}).to_list(None)
    
    total_revenue = sum(m.get("metrics", {}).get("total_revenue", 0) for m in all_members)
    total_quotes_sent = sum(m.get("metrics", {}).get("quotes_sent", 0) for m in all_members)
    total_quotes_accepted = sum(m.get("metrics", {}).get("quotes_accepted", 0) for m in all_members)
    total_commission = sum(m.get("metrics", {}).get("total_commission_earned", 0) for m in all_members)
    
    # Calculate averages across team
    members_with_deals = [m for m in all_members if m.get("metrics", {}).get("quotes_accepted", 0) > 0]
    avg_deal_size = 0
    avg_days_to_close = 0
    
    if members_with_deals:
        avg_deal_size = sum(m.get("metrics", {}).get("avg_deal_size", 0) for m in members_with_deals) / len(members_with_deals)
        avg_days_to_close = sum(m.get("metrics", {}).get("avg_days_to_close", 0) for m in members_with_deals) / len(members_with_deals)
    
    return {
        "total_members": total_members,
        "by_role": {r["_id"]: r["count"] for r in role_counts},
        "role_labels": ROLE_LABELS,
        "performance": {
            "total_revenue": round(total_revenue, 2),
            "total_quotes_sent": total_quotes_sent,
            "total_quotes_accepted": total_quotes_accepted,
            "overall_conversion_rate": round((total_quotes_accepted / max(total_quotes_sent, 1)) * 100, 1),
            "avg_deal_size": round(avg_deal_size, 2),
            "avg_days_to_close": round(avg_days_to_close, 1),
            "total_commission_paid": round(total_commission, 2),
        },
    }


# ============= RESELLER SPECIFIC =============

@router.get("/resellers")
async def list_resellers():
    """List all resellers with their performance data"""
    db = get_db()
    
    resellers = await db.team_members.find({
        "role": {"$in": ["reseller", "partner"]},
        "is_active": True,
    }).sort("metrics.total_revenue", -1).to_list(100)
    
    return [
        {
            "id": str(r["_id"]),
            "name": f"{r['first_name']} {r['last_name']}",
            "company_name": r.get("company_name"),
            "email": r["email"],
            "phone": r.get("phone"),
            "role": r["role"],
            "commission_percent": r.get("commission_percent", 0),
            "agreement_doc_url": r.get("agreement_doc_url"),
            "agreement_signed_at": r.get("agreement_signed_at").isoformat() if r.get("agreement_signed_at") else None,
            "metrics": r.get("metrics", {}),
            "score": calculate_reseller_score(r.get("metrics", {})),
        }
        for r in resellers
    ]


def calculate_reseller_score(metrics: dict) -> int:
    """Calculate a performance score (0-100) for a reseller"""
    score = 0
    
    # Revenue contribution (max 40 points)
    revenue = metrics.get("total_revenue", 0)
    if revenue >= 100000:
        score += 40
    elif revenue >= 50000:
        score += 30
    elif revenue >= 25000:
        score += 20
    elif revenue >= 10000:
        score += 10
    elif revenue > 0:
        score += 5
    
    # Conversion rate (max 25 points)
    quotes_sent = metrics.get("quotes_sent", 0)
    quotes_accepted = metrics.get("quotes_accepted", 0)
    if quotes_sent > 0:
        conversion = (quotes_accepted / quotes_sent) * 100
        if conversion >= 50:
            score += 25
        elif conversion >= 30:
            score += 20
        elif conversion >= 20:
            score += 15
        elif conversion >= 10:
            score += 10
        elif conversion > 0:
            score += 5
    
    # Speed to close (max 20 points)
    avg_days = metrics.get("avg_days_to_close", 0)
    if avg_days > 0:
        if avg_days <= 7:
            score += 20
        elif avg_days <= 14:
            score += 15
        elif avg_days <= 30:
            score += 10
        elif avg_days <= 60:
            score += 5
    
    # Deal size (max 15 points)
    avg_deal = metrics.get("avg_deal_size", 0)
    if avg_deal >= 5000:
        score += 15
    elif avg_deal >= 2500:
        score += 10
    elif avg_deal >= 1000:
        score += 5
    
    return min(score, 100)


@router.post("/resellers/{member_id}/upload-agreement")
async def upload_reseller_agreement(
    member_id: str,
    agreement_url: str,
    commission_percent: float,
):
    """Update reseller agreement details"""
    db = get_db()
    
    result = await db.team_members.update_one(
        {"_id": ObjectId(member_id)},
        {"$set": {
            "agreement_doc_url": agreement_url,
            "commission_percent": commission_percent,
            "agreement_signed_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }}
    )


# ============= WEEKLY KPI TRACKING =============

def get_week_start(date: datetime = None) -> datetime:
    """Get the Monday of the current week"""
    if date is None:
        date = datetime.utcnow()
    return date - timedelta(days=date.weekday())


@router.post("/members/{member_id}/kpi")
async def submit_weekly_kpi(member_id: str, data: WeeklyKPIInput):
    """Submit weekly KPIs for a team member (hours worked, demos done)"""
    db = get_db()
    
    member = await db.team_members.find_one({"_id": ObjectId(member_id)})
    if not member:
        raise HTTPException(status_code=404, detail="Team member not found")
    
    # Determine week start
    if data.week_start:
        week_start = datetime.fromisoformat(data.week_start.replace('Z', '+00:00'))
    else:
        week_start = get_week_start()
    week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Calculate earnings for this week
    metrics = member.get("metrics", {})
    hourly_rate = member.get("hourly_rate", 0)
    commission_earned = metrics.get("total_commission_earned", 0)
    total_revenue = metrics.get("total_revenue", 0)
    
    # Earnings = hourly pay + commission
    weekly_pay = data.hours_worked * hourly_rate if hourly_rate else 0
    earnings_per_hour = 0
    if data.hours_worked > 0:
        # Total earnings (commission + base pay) / hours worked
        total_earnings = weekly_pay + commission_earned
        earnings_per_hour = round(total_earnings / data.hours_worked, 2)
    
    # Upsert weekly KPI record
    kpi_record = {
        "member_id": member_id,
        "week_start": week_start,
        "hours_worked": data.hours_worked,
        "demos_done": data.demos_done,
        "weekly_pay": weekly_pay,
        "commission_earned": commission_earned,
        "total_earnings": weekly_pay + commission_earned,
        "earnings_per_hour": earnings_per_hour,
        "updated_at": datetime.utcnow(),
    }
    
    await db.weekly_kpis.update_one(
        {"member_id": member_id, "week_start": week_start},
        {"$set": kpi_record},
        upsert=True
    )
    
    # Update member's current week KPIs
    await db.team_members.update_one(
        {"_id": ObjectId(member_id)},
        {"$set": {
            "current_week_kpi": {
                "week_start": week_start.isoformat(),
                "hours_worked": data.hours_worked,
                "demos_done": data.demos_done,
                "earnings_per_hour": earnings_per_hour,
            },
            "updated_at": datetime.utcnow(),
        }}
    )
    
    logger.info(f"KPI submitted for {member['first_name']} {member['last_name']}: {data.hours_worked}hrs, {data.demos_done} demos, ${earnings_per_hour}/hr")
    
    return {
        "success": True,
        "week_start": week_start.isoformat(),
        "hours_worked": data.hours_worked,
        "demos_done": data.demos_done,
        "earnings_per_hour": earnings_per_hour,
    }


@router.get("/members/{member_id}/kpi-history")
async def get_kpi_history(member_id: str, weeks: int = 12):
    """Get KPI history for a team member"""
    db = get_db()
    
    history = await db.weekly_kpis.find(
        {"member_id": member_id}
    ).sort("week_start", -1).limit(weeks).to_list(weeks)
    
    return [
        {
            "week_start": h["week_start"].isoformat(),
            "hours_worked": h["hours_worked"],
            "demos_done": h["demos_done"],
            "weekly_pay": h.get("weekly_pay", 0),
            "commission_earned": h.get("commission_earned", 0),
            "total_earnings": h.get("total_earnings", 0),
            "earnings_per_hour": h.get("earnings_per_hour", 0),
        }
        for h in history
    ]


@router.get("/leaderboard/efficiency")
async def get_efficiency_leaderboard(
    role: Optional[str] = None,
    period: str = "current_week",
    limit: int = 20,
):
    """
    Get leaderboard ranked by earnings per hour ($/hr)
    Gold/Silver/Bronze based on who earns the most per hour worked
    """
    db = get_db()
    
    query = {"is_active": True}
    if role:
        query["role"] = role
    
    # Get current week's start
    week_start = get_week_start()
    week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
    
    if period == "current_week":
        # Get this week's KPIs
        kpis = await db.weekly_kpis.find({
            "week_start": week_start,
            "hours_worked": {"$gt": 0}  # Only include those who logged hours
        }).sort("earnings_per_hour", -1).to_list(limit)
        
        # Get member details
        leaderboard = []
        for rank, kpi in enumerate(kpis, 1):
            member = await db.team_members.find_one({"_id": ObjectId(kpi["member_id"])})
            if member and (not role or member.get("role") == role):
                leaderboard.append({
                    "rank": rank,
                    "id": kpi["member_id"],
                    "name": f"{member['first_name']} {member['last_name']}",
                    "role": member["role"],
                    "role_label": ROLE_LABELS.get(member["role"], member["role"]),
                    "avatar_url": member.get("avatar_url"),
                    "hours_worked": kpi["hours_worked"],
                    "demos_done": kpi["demos_done"],
                    "earnings_per_hour": kpi["earnings_per_hour"],
                    "total_earnings": kpi.get("total_earnings", 0),
                    "trophy": "gold" if rank == 1 else "silver" if rank == 2 else "bronze" if rank == 3 else None,
                })
    else:
        # All time or custom period - aggregate from history
        pipeline = [
            {"$match": {"hours_worked": {"$gt": 0}}},
            {"$group": {
                "_id": "$member_id",
                "total_hours": {"$sum": "$hours_worked"},
                "total_demos": {"$sum": "$demos_done"},
                "total_earnings": {"$sum": "$total_earnings"},
                "weeks_tracked": {"$sum": 1},
            }},
            {"$addFields": {
                "avg_earnings_per_hour": {
                    "$cond": [
                        {"$gt": ["$total_hours", 0]},
                        {"$divide": ["$total_earnings", "$total_hours"]},
                        0
                    ]
                }
            }},
            {"$sort": {"avg_earnings_per_hour": -1}},
            {"$limit": limit},
        ]
        
        aggregated = await db.weekly_kpis.aggregate(pipeline).to_list(limit)
        
        leaderboard = []
        for rank, agg in enumerate(aggregated, 1):
            member = await db.team_members.find_one({"_id": ObjectId(agg["_id"])})
            if member and (not role or member.get("role") == role):
                leaderboard.append({
                    "rank": rank,
                    "id": agg["_id"],
                    "name": f"{member['first_name']} {member['last_name']}",
                    "role": member["role"],
                    "role_label": ROLE_LABELS.get(member["role"], member["role"]),
                    "avatar_url": member.get("avatar_url"),
                    "hours_worked": round(agg["total_hours"], 1),
                    "demos_done": agg["total_demos"],
                    "earnings_per_hour": round(agg["avg_earnings_per_hour"], 2),
                    "total_earnings": round(agg["total_earnings"], 2),
                    "weeks_tracked": agg["weeks_tracked"],
                    "trophy": "gold" if rank == 1 else "silver" if rank == 2 else "bronze" if rank == 3 else None,
                })
    
    return {
        "period": period,
        "week_start": week_start.isoformat() if period == "current_week" else None,
        "leaderboard": leaderboard,
    }


@router.put("/members/{member_id}/compensation")
async def update_member_compensation(
    member_id: str,
    hourly_rate: Optional[float] = None,
    base_salary: Optional[float] = None,
    commission_percent: Optional[float] = None,
):
    """Update a member's compensation details for earnings calculation"""
    db = get_db()
    
    update_data = {"updated_at": datetime.utcnow()}
    if hourly_rate is not None:
        update_data["hourly_rate"] = hourly_rate
    if base_salary is not None:
        update_data["base_salary"] = base_salary
    if commission_percent is not None:
        update_data["commission_percent"] = commission_percent
    
    result = await db.team_members.update_one(
        {"_id": ObjectId(member_id)},
        {"$set": update_data}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Team member not found")
    
    return {"success": True, "message": "Compensation updated"}

    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Team member not found")
    
    return {"success": True, "message": "Agreement updated"}
