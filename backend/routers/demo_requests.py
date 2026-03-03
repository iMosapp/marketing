"""
Demo Request Router - Captures leads from the marketing site, ads, and in-app CTAs.
Tracks source, channel, UTM parameters for full-funnel attribution.
"""
from fastapi import APIRouter
from bson import ObjectId
from datetime import datetime, timezone, timedelta
from typing import Optional

from routers.database import get_db

router = APIRouter(prefix="/demo-requests", tags=["demo-requests"])

# Channel classification based on UTM or source
CHANNEL_MAP = {
    "facebook": "paid_social",
    "instagram": "paid_social",
    "tiktok": "paid_social",
    "linkedin": "paid_social",
    "twitter": "paid_social",
    "x": "paid_social",
    "snapchat": "paid_social",
    "youtube": "paid_social",
    "google": "paid_search",
    "bing": "paid_search",
    "email": "email",
    "newsletter": "email",
}


def classify_channel(source: str, utm_source: str, utm_medium: str) -> str:
    """Auto-classify the lead channel from UTM params or source."""
    utm_src = (utm_source or "").lower()
    utm_med = (utm_medium or "").lower()
    src = (source or "").lower()

    if utm_src in CHANNEL_MAP:
        return CHANNEL_MAP[utm_src]
    if "cpc" in utm_med or "ppc" in utm_med or "paid" in utm_med:
        return "paid_search"
    if "social" in utm_med:
        return "paid_social"
    if "email" in utm_med:
        return "email"
    if "referral" in utm_med:
        return "referral"
    if "sales_presentation" in src:
        return "sales_presentation"
    if "imos" in src:
        return "in_app"
    if src:
        return "organic"
    return "direct"


def parse_source_page(source: str) -> str:
    """Extract the page name from a source like 'digital_card_hero'."""
    if not source:
        return "unknown"
    parts = source.rsplit("_", 1)
    if len(parts) == 2 and parts[1] in ("nav", "hero", "cta", "footer"):
        return parts[0]
    return source


def parse_source_position(source: str) -> str:
    """Extract the CTA position from a source like 'digital_card_hero'."""
    if not source:
        return "unknown"
    parts = source.rsplit("_", 1)
    if len(parts) == 2 and parts[1] in ("nav", "hero", "cta", "footer"):
        return parts[1]
    return "direct"


def _classify_referrer_type(ref_code: str, role: str) -> str:
    """Classify the referrer type based on ref code prefix or role."""
    code = ref_code.upper()
    if code.startswith("PARTNER_"):
        return "partner"
    if code.startswith("RESELLER_"):
        return "reseller"
    if code.startswith("REF_"):
        return "referral"
    if code.startswith("TEAM_"):
        return "internal"
    if role in ("super_admin", "admin"):
        return "internal"
    return "user"


@router.post("")
async def create_demo_request(data: dict):
    """Capture a demo request with full attribution tracking."""
    db = get_db()

    required = ["name", "email"]
    for field in required:
        if not data.get(field):
            return {"status": "error", "message": f"{field} is required"}

    source = data.get("source", "").strip()
    utm_source = data.get("utm_source", "").strip()
    utm_medium = data.get("utm_medium", "").strip()
    utm_campaign = data.get("utm_campaign", "").strip()
    utm_content = data.get("utm_content", "").strip()
    utm_term = data.get("utm_term", "").strip()

    demo = {
        "name": data.get("name", "").strip(),
        "email": data.get("email", "").strip().lower(),
        "phone": data.get("phone", "").strip(),
        "company": data.get("company", "").strip(),
        "team_size": data.get("team_size", "").strip(),
        "message": data.get("message", "").strip(),
        "source": source,
        "source_page": parse_source_page(source),
        "source_position": parse_source_position(source),
        "channel": classify_channel(source, utm_source, utm_medium),
        "utm_source": utm_source,
        "utm_medium": utm_medium,
        "utm_campaign": utm_campaign,
        "utm_content": utm_content,
        "utm_term": utm_term,
        "referrer": data.get("referrer", "").strip(),
        "referred_by": data.get("ref", "").strip(),
        "status": "new",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    # Resolve ref code to user if present
    ref_code = data.get("ref", "").strip()
    if ref_code:
        ref_user = await db.users.find_one({"ref_code": ref_code}, {"_id": 1, "name": 1, "role": 1, "organization_id": 1})
        if ref_user:
            demo["referred_by_user_id"] = str(ref_user["_id"])
            demo["referred_by_name"] = ref_user.get("name", "")
            demo["referred_by_role"] = ref_user.get("role", "")
            demo["referrer_type"] = _classify_referrer_type(ref_code, ref_user.get("role", ""))

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


@router.get("/analytics")
async def demo_analytics(days: int = 30):
    """Aggregate demo request analytics for the admin dashboard."""
    db = get_db()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    # Total counts
    total_all = await db.demo_requests.count_documents({})
    total_period = await db.demo_requests.count_documents({"created_at": {"$gte": cutoff}})
    total_new = await db.demo_requests.count_documents({"status": "new"})

    # Previous period for comparison
    prev_cutoff = (datetime.now(timezone.utc) - timedelta(days=days * 2)).isoformat()
    total_prev = await db.demo_requests.count_documents({
        "created_at": {"$gte": prev_cutoff, "$lt": cutoff}
    })

    # By channel
    channel_pipeline = [
        {"$match": {"created_at": {"$gte": cutoff}}},
        {"$group": {"_id": "$channel", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    channel_stats = []
    async for doc in db.demo_requests.aggregate(channel_pipeline):
        channel_stats.append({"channel": doc["_id"] or "direct", "count": doc["count"]})

    # By source page
    page_pipeline = [
        {"$match": {"created_at": {"$gte": cutoff}}},
        {"$group": {"_id": "$source_page", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    page_stats = []
    async for doc in db.demo_requests.aggregate(page_pipeline):
        page_stats.append({"page": doc["_id"] or "unknown", "count": doc["count"]})

    # By CTA position
    position_pipeline = [
        {"$match": {"created_at": {"$gte": cutoff}}},
        {"$group": {"_id": "$source_position", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    position_stats = []
    async for doc in db.demo_requests.aggregate(position_pipeline):
        position_stats.append({"position": doc["_id"] or "unknown", "count": doc["count"]})

    # By full source (page + position)
    source_pipeline = [
        {"$match": {"created_at": {"$gte": cutoff}}},
        {"$group": {"_id": "$source", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    source_stats = []
    async for doc in db.demo_requests.aggregate(source_pipeline):
        source_stats.append({"source": doc["_id"] or "direct", "count": doc["count"]})

    # By UTM campaign (for paid ads)
    campaign_pipeline = [
        {"$match": {"created_at": {"$gte": cutoff}, "utm_campaign": {"$nin": ["", None]}}},
        {"$group": {
            "_id": {"campaign": "$utm_campaign", "source": "$utm_source", "medium": "$utm_medium"},
            "count": {"$sum": 1},
        }},
        {"$sort": {"count": -1}},
    ]
    campaign_stats = []
    async for doc in db.demo_requests.aggregate(campaign_pipeline):
        campaign_stats.append({
            "campaign": doc["_id"].get("campaign", ""),
            "utm_source": doc["_id"].get("source", ""),
            "utm_medium": doc["_id"].get("medium", ""),
            "count": doc["count"],
        })

    # Daily trend
    daily_pipeline = [
        {"$match": {"created_at": {"$gte": cutoff}}},
        {"$addFields": {"date": {"$substr": ["$created_at", 0, 10]}}},
        {"$group": {"_id": "$date", "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}},
    ]
    daily_trend = []
    async for doc in db.demo_requests.aggregate(daily_pipeline):
        daily_trend.append({"date": doc["_id"], "count": doc["count"]})

    # Recent requests (last 10)
    recent = []
    async for doc in db.demo_requests.find({}, {"_id": 0}).sort("created_at", -1).limit(10):
        recent.append(doc)

    # By referrer (for attribution to users/partners)
    referrer_pipeline = [
        {"$match": {"created_at": {"$gte": cutoff}, "referred_by": {"$nin": ["", None]}}},
        {"$group": {
            "_id": {"ref_code": "$referred_by", "name": "$referred_by_name", "type": "$referrer_type"},
            "count": {"$sum": 1},
        }},
        {"$sort": {"count": -1}},
    ]
    referrer_stats = []
    async for doc in db.demo_requests.aggregate(referrer_pipeline):
        referrer_stats.append({
            "ref_code": doc["_id"].get("ref_code", ""),
            "name": doc["_id"].get("name", "Unknown"),
            "type": doc["_id"].get("type", "user"),
            "count": doc["count"],
        })

    return {
        "summary": {
            "total_all_time": total_all,
            "total_period": total_period,
            "total_previous_period": total_prev,
            "total_new": total_new,
            "period_days": days,
        },
        "by_channel": channel_stats,
        "by_page": page_stats,
        "by_position": position_stats,
        "by_source": source_stats,
        "by_campaign": campaign_stats,
        "by_referrer": referrer_stats,
        "daily_trend": daily_trend,
        "recent_requests": recent,
    }


@router.patch("/{request_id}/status")
async def update_demo_status(request_id: str, data: dict):
    """Update the status of a demo request (new, contacted, scheduled, closed)."""
    db = get_db()
    status = data.get("status", "").strip()
    if status not in ("new", "contacted", "scheduled", "closed", "lost"):
        return {"status": "error", "message": "Invalid status"}

    result = await db.demo_requests.update_one(
        {"_id": ObjectId(request_id)},
        {"$set": {"status": status, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    if result.modified_count == 0:
        return {"status": "error", "message": "Request not found"}
    return {"status": "success"}
