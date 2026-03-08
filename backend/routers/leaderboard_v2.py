"""
Leaderboard v2  - Gamification engine with Store, Org, and Global levels.
Aggregates contact_events by user for ranked competition with category breakdowns.
Includes streaks, levels/titles, and "you vs average" comparison.
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException
from bson import ObjectId

from routers.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/leaderboard/v2", tags=["Leaderboard V2"])

# Categories tracked for scoring
CATEGORIES = {
    "digital_cards": {"events": ["digital_card_sent", "digital_card_shared"], "label": "Digital Cards", "icon": "card"},
    "reviews": {"events": ["review_request_sent", "review_shared"], "label": "Reviews", "icon": "star"},
    "cards": {"events": [
        "congrats_card_sent", "birthday_card_sent", "thank_you_card_sent",
        "thankyou_card_sent", "holiday_card_sent", "welcome_card_sent",
        "anniversary_card_sent"
    ], "label": "Cards Sent", "icon": "gift"},
    "emails": {"events": ["email_sent"], "label": "Emails", "icon": "mail"},
    "sms": {"events": ["personal_sms", "sms_sent"], "label": "SMS", "icon": "chatbubble"},
    "calls": {"events": ["call_placed", "call_received"], "label": "Calls", "icon": "call"},
    "tasks": {"events": ["__tasks__"], "label": "Tasks Done", "icon": "checkbox"},
}

BADGE_THRESHOLDS = {1: "gold", 2: "silver", 3: "bronze"}

# Level system — cumulative score thresholds
LEVELS = [
    {"min": 0, "title": "Rookie", "color": "#8E8E93", "icon": "shield-outline"},
    {"min": 51, "title": "Hustler", "color": "#007AFF", "icon": "flash"},
    {"min": 201, "title": "Closer", "color": "#AF52DE", "icon": "flame"},
    {"min": 501, "title": "All-Star", "color": "#FF9500", "icon": "star"},
    {"min": 1001, "title": "Legend", "color": "#C9A962", "icon": "trophy"},
]


def get_level(score: int) -> dict:
    """Determine a user's level based on their total score."""
    level = LEVELS[0]
    for l in LEVELS:
        if score >= l["min"]:
            level = l
    next_level = None
    for l in LEVELS:
        if l["min"] > score:
            next_level = l
            break
    return {
        "title": level["title"],
        "color": level["color"],
        "icon": level["icon"],
        "score": score,
        "next_level": next_level["title"] if next_level else None,
        "next_at": next_level["min"] if next_level else None,
        "progress_pct": round(((score - level["min"]) / max((next_level["min"] if next_level else level["min"] + 500) - level["min"], 1)) * 100) if next_level else 100,
    }


def _build_date_filter(month: Optional[int], year: Optional[int]) -> dict:
    """Build a MongoDB date range filter."""
    if not year:
        return {}
    if month:
        start = datetime(year, month, 1, tzinfo=timezone.utc)
        if month == 12:
            end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            end = datetime(year, month + 1, 1, tzinfo=timezone.utc)
    else:
        start = datetime(year, 1, 1, tzinfo=timezone.utc)
        end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    return {"timestamp": {"$gte": start, "$lt": end}}


def _build_date_filter_v2(period: str = "month", month: Optional[int] = None, year: Optional[int] = None) -> dict:
    """Build date filter from a period string (week/month/all) or explicit month/year."""
    if month or year:
        return _build_date_filter(month, year)
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "week":
        start = today_start - timedelta(days=7)
    elif period == "month":
        start = today_start - timedelta(days=30)
    elif period == "all":
        return {}
    else:
        start = today_start - timedelta(days=30)
    return {"timestamp": {"$gte": start, "$lt": now}}


async def _aggregate_user_scores(user_ids: list, date_filter: dict) -> dict:
    """Aggregate event counts per user per category, including completed tasks."""
    db = get_db()
    all_event_types = []
    for cat in CATEGORIES.values():
        if "__tasks__" not in cat["events"]:
            all_event_types.extend(cat["events"])

    match = {"user_id": {"$in": user_ids}, "event_type": {"$in": all_event_types}}
    match.update(date_filter)

    pipeline = [
        {"$match": match},
        {"$group": {
            "_id": {"user_id": "$user_id", "event_type": "$event_type"},
            "count": {"$sum": 1}
        }}
    ]
    cursor = db.contact_events.aggregate(pipeline)
    results = await cursor.to_list(5000)

    # Build per-user score maps
    scores = {}
    for r in results:
        uid = r["_id"]["user_id"]
        etype = r["_id"]["event_type"]
        count = r["count"]
        if uid not in scores:
            scores[uid] = {cat: 0 for cat in CATEGORIES}
            scores[uid]["total"] = 0
        for cat_key, cat_def in CATEGORIES.items():
            if etype in cat_def["events"]:
                scores[uid][cat_key] += count
                scores[uid]["total"] += count

    # Add task completion counts
    task_match: dict = {"user_id": {"$in": user_ids}, "status": "completed"}
    if "timestamp" in date_filter:
        task_match["completed_at"] = date_filter["timestamp"]
    elif date_filter:
        for k, v in date_filter.items():
            if k == "timestamp":
                task_match["completed_at"] = v

    task_pipeline = [
        {"$match": task_match},
        {"$group": {"_id": "$user_id", "count": {"$sum": 1}}},
    ]
    task_results = await db.tasks.aggregate(task_pipeline).to_list(500)
    for r in task_results:
        uid = r["_id"]
        count = r["count"]
        if uid not in scores:
            scores[uid] = {cat: 0 for cat in CATEGORIES}
            scores[uid]["total"] = 0
        scores[uid]["tasks"] = count
        scores[uid]["total"] += count

    return scores


async def _get_streak(user_id: str) -> int:
    """Calculate how many consecutive days the user has completed at least one task."""
    db = get_db()
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    streak = 0
    for i in range(60):  # check up to 60 days back
        day_start = today - timedelta(days=i)
        day_end = day_start + timedelta(days=1)
        count = await db.tasks.count_documents({
            "user_id": user_id,
            "status": "completed",
            "completed_at": {"$gte": day_start, "$lt": day_end},
        })
        if count > 0:
            streak += 1
        else:
            if i == 0:
                continue  # today might not have tasks yet
            break
    return streak


def _rank_users(user_docs: list, scores: dict, category: str = "total") -> list:
    """Rank users by a category score, assign badges."""
    from utils.image_urls import resolve_user_photo
    ranked = []
    for u in user_docs:
        uid = str(u["_id"])
        user_scores = scores.get(uid, {cat: 0 for cat in CATEGORIES})
        user_scores.setdefault("total", sum(v for k, v in user_scores.items() if k != "total"))
        sort_val = user_scores.get(category, user_scores.get("total", 0))
        visible = u.get("settings", {}).get("leaderboard_visible", True)
        ranked.append({
            "user_id": uid,
            "name": u.get("name", "Unknown"),
            "role": u.get("role", ""),
            "photo": resolve_user_photo(u),
            "scores": {k: v for k, v in user_scores.items()},
            "sort_score": sort_val,
            "visible": visible,
        })
    ranked.sort(key=lambda x: x["sort_score"], reverse=True)
    for i, entry in enumerate(ranked):
        entry["rank"] = i + 1
        entry["badge"] = BADGE_THRESHOLDS.get(i + 1)
    return ranked


@router.get("/store/{user_id}")
async def store_leaderboard(
    user_id: str,
    month: Optional[int] = None,
    year: Optional[int] = None,
    category: str = "total",
    period: str = "month",
):
    """Leaderboard for users within the same store/account."""
    db = get_db()
    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)})
    except Exception:
        raise HTTPException(status_code=404, detail="Invalid user ID")
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    org_id = user.get("organization_id") or user.get("org_id") or ""
    store_id = user.get("store_id") or ""

    # Find all users in the same store
    query = {}
    if store_id:
        query["store_id"] = store_id
    elif org_id:
        query["$or"] = [{"organization_id": org_id}, {"org_id": org_id}]
    else:
        query["_id"] = ObjectId(user_id)

    users = await db.users.find(query, {"password": 0}).to_list(200)
    user_ids = [str(u["_id"]) for u in users]

    date_filter = _build_date_filter_v2(period, month, year)
    scores = await _aggregate_user_scores(user_ids, date_filter)
    ranked = _rank_users(users, scores, category)

    # Filter out users who opted out (but always show the requesting user)
    ranked = [e for e in ranked if e["user_id"] == user_id or e.get("visible", True)]
    # Re-rank after filtering
    for i, e in enumerate(ranked):
        e["rank"] = i + 1
        e["badge"] = BADGE_THRESHOLDS.get(i + 1)

    # Your stats
    your_scores = scores.get(user_id, {cat: 0 for cat in CATEGORIES})
    your_scores.setdefault("total", 0)
    your_total = your_scores.get("total", 0)
    streak = await _get_streak(user_id)
    level = get_level(your_total)

    # Team averages
    totals = [s.get("total", 0) for s in scores.values()]
    avg_score = round(sum(totals) / max(len(totals), 1), 1)

    return {
        "level": "store",
        "store_id": store_id,
        "org_id": org_id,
        "period": period,
        "category": category,
        "members": len(users),
        "your_user_id": user_id,
        "leaderboard": ranked,
        "your_stats": {
            "rank": next((e["rank"] for e in ranked if e["user_id"] == user_id), None),
            "scores": your_scores,
            "streak": streak,
            "level": level,
            "vs_avg": round(your_total - avg_score, 1),
            "team_avg": avg_score,
        },
        "team_summary": {
            "team_total": sum(totals),
            "members": len(users),
            "avg_score": avg_score,
        },
        "categories": {k: {"label": v["label"], "icon": v["icon"]} for k, v in CATEGORIES.items()},
        "levels": LEVELS,
    }


@router.get("/org/{user_id}")
async def org_leaderboard(
    user_id: str,
    month: Optional[int] = None,
    year: Optional[int] = None,
    category: str = "total",
    period: str = "month",
):
    """Leaderboard ranking stores/accounts within the same org."""
    db = get_db()
    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)})
    except Exception:
        raise HTTPException(status_code=404, detail="Invalid user ID")
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    org_id = user.get("organization_id") or user.get("org_id") or ""
    if not org_id:
        return {"level": "org", "leaderboard": [], "message": "No organization found"}

    stores_cursor = db.users.aggregate([
        {"$match": {"$or": [{"organization_id": org_id}, {"org_id": org_id}]}},
        {"$group": {"_id": "$store_id", "members": {"$sum": 1}, "users": {"$push": {"id": {"$toString": "$_id"}, "name": "$name"}}}},
    ])
    stores = await stores_cursor.to_list(100)

    all_user_ids = []
    for s in stores:
        for u in s.get("users", []):
            all_user_ids.append(u["id"])

    date_filter = _build_date_filter_v2(period, month, year)
    scores = await _aggregate_user_scores(all_user_ids, date_filter)

    # Aggregate scores per store
    store_rankings = []
    for s in stores:
        store_id = s["_id"] or "default"
        store_user_ids = [u["id"] for u in s.get("users", [])]
        store_total = sum(scores.get(uid, {}).get("total", 0) for uid in store_user_ids)
        store_cats = {cat: 0 for cat in CATEGORIES}
        for uid in store_user_ids:
            for cat in CATEGORIES:
                store_cats[cat] += scores.get(uid, {}).get(cat, 0)

        # Get store name from the store collection or use store_id
        store_doc = await db.stores.find_one({"_id": store_id if not ObjectId.is_valid(store_id) else ObjectId(store_id)}) if store_id != "default" else None
        store_name = (store_doc or {}).get("name", store_id or "Main Store")

        store_rankings.append({
            "store_id": store_id,
            "store_name": store_name,
            "members": s["members"],
            "scores": {**store_cats, "total": store_total},
            "sort_score": store_cats.get(category, store_total) if category != "total" else store_total,
        })

    store_rankings.sort(key=lambda x: x["sort_score"], reverse=True)
    for i, s in enumerate(store_rankings):
        s["rank"] = i + 1
        s["badge"] = BADGE_THRESHOLDS.get(i + 1)

    return {
        "level": "org",
        "org_id": org_id,
        "month": month,
        "year": year,
        "category": category,
        "stores": len(store_rankings),
        "leaderboard": store_rankings,
        "categories": {k: {"label": v["label"], "icon": v["icon"]} for k, v in CATEGORIES.items()},
    }


@router.get("/global/{user_id}")
async def global_leaderboard(
    user_id: str,
    month: Optional[int] = None,
    year: Optional[int] = None,
    category: str = "total",
    period: str = "month",
):
    """Global leaderboard - all users across all orgs (anonymized). Respects leaderboard_visible."""
    db = get_db()

    # Check if requesting user's org allows global visibility
    req_user = await db.users.find_one({"_id": ObjectId(user_id)}, {"organization_id": 1, "org_id": 1})
    req_org_id = (req_user or {}).get("organization_id") or (req_user or {}).get("org_id") or ""

    # Only include users from orgs that have leaderboard_visible=true (or the requesting user's org)
    visible_org_ids = set()
    if req_org_id:
        visible_org_ids.add(req_org_id)
    async for org in db.organizations.find({"leaderboard_visible": True}, {"_id": 1}):
        visible_org_ids.add(str(org["_id"]))

    # Get users from visible orgs + users without an org
    user_query = {"status": {"$ne": "deactivated"}}
    if visible_org_ids:
        user_query["$or"] = [
            {"organization_id": {"$in": list(visible_org_ids)}},
            {"org_id": {"$in": list(visible_org_ids)}},
            {"organization_id": {"$in": [None, ""]}},
        ]

    users = await db.users.find(user_query, {"password": 0, "email": 0, "phone": 0}).limit(500).to_list(500)
    user_ids = [str(u["_id"]) for u in users]

    date_filter = _build_date_filter_v2(period, month, year)
    scores = await _aggregate_user_scores(user_ids, date_filter)
    ranked = _rank_users(users, scores, category)

    # Filter out users who opted out (but always show the requesting user)
    ranked = [e for e in ranked if e["user_id"] == user_id or e.get("visible", True)]
    # Re-rank after filtering
    for i, e in enumerate(ranked):
        e["rank"] = i + 1
        e["badge"] = BADGE_THRESHOLDS.get(i + 1)

    # Anonymize — only show initials and level
    for entry in ranked:
        parts = entry["name"].split()
        entry["display_name"] = f"{parts[0][0]}. {parts[-1][0]}." if len(parts) >= 2 else f"User #{entry['rank']}"
        entry["photo"] = None
        entry["level"] = get_level(entry["sort_score"])
        # Mark if this is the requesting user
        entry["is_you"] = entry["user_id"] == user_id

    your_rank = next((e["rank"] for e in ranked if e["user_id"] == user_id), None)
    your_scores = scores.get(user_id, {})
    your_total = your_scores.get("total", 0)
    streak = await _get_streak(user_id)

    total_score = sum(s.get("total", 0) for s in scores.values())
    return {
        "level": "global",
        "period": period,
        "category": category,
        "total_users": len(ranked),
        "your_rank": your_rank,
        "your_stats": {
            "rank": your_rank,
            "scores": your_scores,
            "streak": streak,
            "level": get_level(your_total),
        },
        "leaderboard": ranked[:50],
        "team_summary": {
            "platform_total": total_score,
            "active_users": len([r for r in ranked if r["sort_score"] > 0]),
            "avg_score": round(total_score / max(len(ranked), 1), 1),
        },
        "categories": {k: {"label": v["label"], "icon": v["icon"]} for k, v in CATEGORIES.items()},
        "levels": LEVELS,
    }
