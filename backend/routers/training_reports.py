"""
Training Reports Router
Provides analytics on training video engagement - who watched what, when, ranked by activity.
"""
from fastapi import APIRouter, Header
from datetime import datetime, timezone, timedelta
from typing import Optional
import logging
import re

from routers.database import get_db, get_user_by_id

router = APIRouter(prefix="/admin/training-reports", tags=["Training Reports"])
logger = logging.getLogger(__name__)

YT_ID_RE = re.compile(r'(?:youtube\.com/watch\?v=|youtu\.be/)([\w-]+)')


@router.get("/overview")
async def get_training_overview(
    days: int = 30,
    x_user_id: str = Header(None, alias="X-User-ID"),
):
    """Get overview stats for training video engagement."""
    db = get_db()
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    # Get all training video short URLs
    video_urls = await db.short_urls.find(
        {"link_type": "training_video"},
        {"_id": 0, "short_code": 1, "original_url": 1, "metadata": 1, "click_count": 1, "user_id": 1, "created_at": 1}
    ).to_list(500)

    total_videos = len(video_urls)
    total_clicks = sum(v.get("click_count", 0) for v in video_urls)

    # Group by video title
    video_stats = {}
    for v in video_urls:
        meta = v.get("metadata") or {}
        title = meta.get("video_title", "Unknown Video")
        yt_url = v.get("original_url", "")
        vid_match = YT_ID_RE.search(yt_url)
        video_id = vid_match.group(1) if vid_match else ""

        key = yt_url
        if key not in video_stats:
            video_stats[key] = {
                "title": title,
                "youtube_url": yt_url,
                "youtube_id": video_id,
                "thumbnail": f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg" if video_id else None,
                "total_clicks": 0,
                "unique_senders": set(),
            }
        video_stats[key]["total_clicks"] += v.get("click_count", 0)
        if v.get("user_id"):
            video_stats[key]["unique_senders"].add(v["user_id"])

    # Convert sets to counts
    videos = []
    for url, stat in video_stats.items():
        stat["unique_senders"] = len(stat["unique_senders"])
        videos.append(stat)
    videos.sort(key=lambda x: x["total_clicks"], reverse=True)

    # Get recent click activity from short_urls clicks array
    recent_clicks = await db.short_urls.find(
        {"link_type": "training_video", "clicks": {"$exists": True, "$ne": []}},
        {"_id": 0, "clicks": {"$slice": -20}, "metadata": 1, "original_url": 1}
    ).to_list(100)

    activity_feed = []
    for url_doc in recent_clicks:
        meta = url_doc.get("metadata") or {}
        title = meta.get("video_title", "Unknown")
        for click in (url_doc.get("clicks") or []):
            ts = click.get("timestamp")
            if isinstance(ts, str):
                try:
                    ts = datetime.fromisoformat(ts)
                except Exception:
                    ts = None
            activity_feed.append({
                "video_title": title,
                "ip": click.get("ip", ""),
                "user_agent": (click.get("user_agent", ""))[:60],
                "timestamp": ts.isoformat() if isinstance(ts, datetime) else str(ts) if ts else None,
            })
    activity_feed.sort(key=lambda x: x.get("timestamp") or "", reverse=True)

    return {
        "total_videos_tracked": total_videos,
        "total_clicks": total_clicks,
        "period_days": days,
        "videos": videos[:20],
        "recent_activity": activity_feed[:30],
    }


@router.get("/by-sender")
async def get_training_by_sender(
    x_user_id: str = Header(None, alias="X-User-ID"),
):
    """Get training video usage grouped by which salesperson sent the most."""
    db = get_db()

    pipeline = [
        {"$match": {"link_type": "training_video", "user_id": {"$ne": None}}},
        {"$group": {
            "_id": "$user_id",
            "videos_sent": {"$sum": 1},
            "total_clicks": {"$sum": "$click_count"},
            "videos": {"$push": {
                "title": {"$ifNull": ["$metadata.video_title", "Unknown"]},
                "clicks": "$click_count",
                "url": "$original_url",
            }},
        }},
        {"$sort": {"total_clicks": -1}},
        {"$limit": 50},
    ]
    results = await db.short_urls.aggregate(pipeline).to_list(50)

    # Resolve user names
    user_ids = [r["_id"] for r in results if r["_id"]]
    users = {}
    for uid in user_ids:
        try:
            u = await get_user_by_id(uid)
            if u:
                users[uid] = {"name": u.get("name", "Unknown"), "email": u.get("email", "")}
        except Exception:
            pass

    senders = []
    for r in results:
        uid = r["_id"]
        u = users.get(uid, {"name": "Unknown", "email": ""})
        senders.append({
            "user_id": uid,
            "name": u["name"],
            "email": u["email"],
            "videos_sent": r["videos_sent"],
            "total_clicks": r["total_clicks"],
            "top_videos": sorted(r.get("videos", []), key=lambda x: x.get("clicks", 0), reverse=True)[:5],
        })

    return {"senders": senders}


@router.get("/by-video")
async def get_training_by_video(
    x_user_id: str = Header(None, alias="X-User-ID"),
):
    """Get detailed click stats per video."""
    db = get_db()

    pipeline = [
        {"$match": {"link_type": "training_video"}},
        {"$group": {
            "_id": "$original_url",
            "title": {"$first": "$metadata.video_title"},
            "total_clicks": {"$sum": "$click_count"},
            "times_sent": {"$sum": 1},
            "senders": {"$addToSet": "$user_id"},
        }},
        {"$sort": {"total_clicks": -1}},
    ]
    results = await db.short_urls.aggregate(pipeline).to_list(50)

    videos = []
    for r in results:
        yt_url = r["_id"] or ""
        vid_match = YT_ID_RE.search(yt_url)
        video_id = vid_match.group(1) if vid_match else ""
        videos.append({
            "youtube_url": yt_url,
            "youtube_id": video_id,
            "thumbnail": f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg" if video_id else None,
            "title": r.get("title", "Unknown"),
            "total_clicks": r.get("total_clicks", 0),
            "times_sent": r.get("times_sent", 0),
            "unique_senders": len([s for s in (r.get("senders") or []) if s]),
        })

    return {"videos": videos}


@router.get("/viewers")
async def get_training_viewers(
    x_user_id: str = Header(None, alias="X-User-ID"),
):
    """Who watched which lessons — per-user and per-lesson video view data."""
    db = get_db()

    # Per-lesson aggregation
    lesson_pipeline = [
        {"$group": {
            "_id": "$lesson_id",
            "lesson_title": {"$first": "$lesson_title"},
            "track_id": {"$first": "$track_id"},
            "view_count": {"$sum": 1},
            "viewers": {"$addToSet": "$user_id"},
            "last_viewed": {"$max": "$viewed_at"},
        }},
        {"$sort": {"view_count": -1}},
    ]
    lessons = await db.training_video_views.aggregate(lesson_pipeline).to_list(200)

    # Per-user aggregation
    user_pipeline = [
        {"$group": {
            "_id": "$user_id",
            "lessons_viewed": {"$sum": 1},
            "last_viewed": {"$max": "$viewed_at"},
        }},
        {"$sort": {"lessons_viewed": -1}},
        {"$limit": 100},
    ]
    user_stats = await db.training_video_views.aggregate(user_pipeline).to_list(100)

    # Batch-load all user names
    all_user_ids = set()
    for u in user_stats:
        if u["_id"]: all_user_ids.add(u["_id"])
    for l in lessons:
        all_user_ids.update(v for v in l.get("viewers", []) if v)

    users_map = {}
    if all_user_ids:
        from bson import ObjectId as _ObjId
        oids = [_ObjId(uid) for uid in all_user_ids if len(uid) == 24]
        async for u in db.users.find({"_id": {"$in": oids}}, {"name": 1, "email": 1}):
            users_map[str(u["_id"])] = {"name": u.get("name", "Unknown"), "email": u.get("email", "")}

    by_user = []
    for u in user_stats:
        uid = u["_id"] or ""
        info = users_map.get(uid, {"name": "Unknown", "email": ""})
        lv = u.get("last_viewed")
        by_user.append({
            "user_id": uid,
            "name": info["name"],
            "email": info["email"],
            "lessons_viewed": u["lessons_viewed"],
            "last_viewed": lv.isoformat() if isinstance(lv, datetime) else str(lv) if lv else None,
        })

    by_lesson = []
    for l in lessons:
        viewer_names = [users_map.get(uid, {}).get("name", "Unknown") for uid in (l.get("viewers") or []) if uid]
        lv = l.get("last_viewed")
        by_lesson.append({
            "lesson_id": l["_id"],
            "lesson_title": l.get("lesson_title") or "Untitled Lesson",
            "track_id": l.get("track_id", ""),
            "view_count": l.get("view_count", 0),
            "unique_viewers": len([v for v in (l.get("viewers") or []) if v]),
            "viewer_names": sorted(viewer_names),
            "last_viewed": lv.isoformat() if isinstance(lv, datetime) else str(lv) if lv else None,
        })

    total_views = sum(l["view_count"] for l in lessons)
    return {"by_user": by_user, "by_lesson": by_lesson, "total_views": total_views}
