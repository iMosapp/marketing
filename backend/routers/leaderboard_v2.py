"""
Leaderboard v2  - Gamification engine with Store, Org, and Global levels.
Aggregates contact_events by user for ranked competition with category breakdowns.
"""
import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException
from bson import ObjectId

from routers.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/leaderboard/v2", tags=["Leaderboard V2"])

# Categories tracked for scoring
CATEGORIES = {
    "digital_cards": {"events": ["digital_card_sent"], "label": "Digital Cards", "icon": "card"},
    "reviews": {"events": ["review_request_sent"], "label": "Reviews", "icon": "star"},
    "congrats": {"events": ["congrats_card_sent"], "label": "Congrats", "icon": "gift"},
    "emails": {"events": ["email_sent"], "label": "Emails", "icon": "mail"},
    "sms": {"events": ["personal_sms", "sms_sent"], "label": "SMS", "icon": "chatbubble"},
    "voice_notes": {"events": ["voice_note"], "label": "Voice Notes", "icon": "mic"},
}

BADGE_THRESHOLDS = {1: "gold", 2: "silver", 3: "bronze"}


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


async def _aggregate_user_scores(user_ids: list, date_filter: dict) -> dict:
    """Aggregate event counts per user per category."""
    db = get_db()
    all_event_types = []
    for cat in CATEGORIES.values():
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
    return scores


def _rank_users(user_docs: list, scores: dict, category: str = "total") -> list:
    """Rank users by a category score, assign badges."""
    ranked = []
    for u in user_docs:
        uid = str(u["_id"])
        user_scores = scores.get(uid, {cat: 0 for cat in CATEGORIES})
        user_scores.setdefault("total", sum(v for k, v in user_scores.items() if k != "total"))
        sort_val = user_scores.get(category, user_scores.get("total", 0))
        ranked.append({
            "user_id": uid,
            "name": u.get("name", "Unknown"),
            "role": u.get("role", ""),
            "photo": u.get("photo_thumbnail") or u.get("photo_url"),
            "scores": {k: v for k, v in user_scores.items()},
            "sort_score": sort_val,
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

    date_filter = _build_date_filter(month, year)
    scores = await _aggregate_user_scores(user_ids, date_filter)
    ranked = _rank_users(users, scores, category)

    # Team summary
    total_score = sum(s.get("total", 0) for s in scores.values())
    avg_score = round(total_score / len(users), 1) if users else 0

    return {
        "level": "store",
        "store_id": store_id,
        "org_id": org_id,
        "month": month,
        "year": year,
        "category": category,
        "members": len(users),
        "your_user_id": user_id,
        "leaderboard": ranked,
        "team_summary": {
            "team_total": total_score,
            "members": len(users),
            "avg_score": avg_score,
        },
        "categories": {k: {"label": v["label"], "icon": v["icon"]} for k, v in CATEGORIES.items()},
    }


@router.get("/org/{user_id}")
async def org_leaderboard(
    user_id: str,
    month: Optional[int] = None,
    year: Optional[int] = None,
    category: str = "total",
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

    # Get all stores in the org
    stores_cursor = db.users.aggregate([
        {"$match": {"$or": [{"organization_id": org_id}, {"org_id": org_id}]}},
        {"$group": {"_id": "$store_id", "members": {"$sum": 1}, "users": {"$push": {"id": {"$toString": "$_id"}, "name": "$name"}}}},
    ])
    stores = await stores_cursor.to_list(100)

    # Get all user IDs across all stores
    all_user_ids = []
    for s in stores:
        for u in s.get("users", []):
            all_user_ids.append(u["id"])

    date_filter = _build_date_filter(month, year)
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
):
    """Global leaderboard  - all users across all orgs (anonymized)."""
    db = get_db()

    # Get all active users (limit 500 for performance)
    users = await db.users.find(
        {"status": {"$ne": "deactivated"}},
        {"password": 0, "email": 0, "phone": 0}
    ).limit(500).to_list(500)

    user_ids = [str(u["_id"]) for u in users]
    date_filter = _build_date_filter(month, year)
    scores = await _aggregate_user_scores(user_ids, date_filter)
    ranked = _rank_users(users, scores, category)

    # Anonymize  - only show initials and store/org
    for entry in ranked:
        parts = entry["name"].split()
        entry["display_name"] = f"{parts[0][0]}. {parts[-1][0]}." if len(parts) >= 2 else f"User #{entry['rank']}"
        entry["photo"] = None  # No photos in global view

    # Find requesting user's rank
    your_rank = next((e["rank"] for e in ranked if e["user_id"] == user_id), None)

    total_score = sum(s.get("total", 0) for s in scores.values())
    return {
        "level": "global",
        "month": month,
        "year": year,
        "category": category,
        "total_users": len(ranked),
        "your_rank": your_rank,
        "leaderboard": ranked[:50],
        "team_summary": {
            "platform_total": total_score,
            "active_users": len([r for r in ranked if r["sort_score"] > 0]),
            "avg_score": round(total_score / max(len(ranked), 1), 1),
        },
        "categories": {k: {"label": v["label"], "icon": v["icon"]} for k, v in CATEGORIES.items()},
    }
