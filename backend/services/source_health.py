"""Source health: spot lead sources that normally produce but have gone quiet (broken Zap, dead vendor feed).

A source "normally produces" when it received at least MIN_LEADS_28D real leads in the last 28 days.
It is "quiet" when the time since its last lead is >= max(48 h, 3x its usual gap between leads).
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from bson import ObjectId

logger = logging.getLogger(__name__)

MIN_LEADS_28D = 4
FLOOR_HOURS = 48
GAP_MULTIPLIER = 3
REMIND_AFTER_DAYS = 7
MANAGER_ROLES = ["manager", "store_manager", "org_admin", "admin", "super_admin"]


def _utc(v) -> Optional[datetime]:
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    if isinstance(v, str):
        try:
            d = datetime.fromisoformat(v.replace("Z", "+00:00"))
            return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def humanize_hours(h: float) -> str:
    if h < 1:
        return f"{max(1, int(round(h * 60)))} min"
    if h < 48:
        return f"{int(round(h))} hour{'s' if round(h) != 1 else ''}"
    d = h / 24
    return f"{d:.0f} days" if d >= 10 else f"{d:.1f}".rstrip("0").rstrip(".") + " days"


async def source_health(db, store_id: Optional[str] = None, now: Optional[datetime] = None) -> list[dict]:
    """Health row per active lead source (optionally one store). Sorted quiet first."""
    now = now or datetime.now(timezone.utc)
    since = now - timedelta(days=28)
    q: dict = {"is_active": {"$ne": False}}
    if store_id:
        q["store_id"] = store_id
    sources = await db.lead_sources.find(q, {"name": 1, "store_id": 1, "health_alert_sent_at": 1}).to_list(2000)
    if not sources:
        return []
    ids = [str(s["_id"]) for s in sources]
    stats: dict = {}
    async for row in db.inbound_leads.aggregate([
        {"$match": {"source_id": {"$in": ids}, "is_test": {"$ne": True}, "received_at": {"$gte": since}}},
        {"$group": {"_id": "$source_id", "n": {"$sum": 1}, "last": {"$max": "$received_at"}}},
    ]):
        stats[row["_id"]] = row
    # sources with nothing in 28 days still need their true last lead for the message
    stale_ids = [i for i in ids if i not in stats]
    if stale_ids:
        async for row in db.inbound_leads.aggregate([
            {"$match": {"source_id": {"$in": stale_ids}, "is_test": {"$ne": True}}},
            {"$group": {"_id": "$source_id", "last": {"$max": "$received_at"}, "n": {"$sum": 1}}},
        ]):
            stats[row["_id"]] = {"n": 0, "last": row["last"], "lifetime": row["n"]}

    out = []
    for s in sources:
        sid = str(s["_id"])
        st = stats.get(sid) or {}
        n28 = int(st.get("n") or 0)
        last = _utc(st.get("last"))
        quiet_h = (now - last).total_seconds() / 3600 if last else None
        expected_gap_h = (28 * 24) / n28 if n28 else None
        threshold_h = max(FLOOR_HOURS, GAP_MULTIPLIER * expected_gap_h) if expected_gap_h else None
        if last is None:
            status = "new"
        elif n28 < MIN_LEADS_28D:
            status = "quiet" if quiet_h is not None and quiet_h >= 28 * 24 and (st.get("lifetime") or 0) >= MIN_LEADS_28D else "slow"
        elif quiet_h is not None and threshold_h is not None and quiet_h >= threshold_h:
            status = "quiet"
        else:
            status = "healthy"
        watched = n28 >= MIN_LEADS_28D
        out.append({
            "source_id": sid, "source_name": s.get("name"), "store_id": s.get("store_id"), "status": status,
            "leads_28d": n28, "last_lead_at": last.isoformat() if last else None,
            "quiet_hours": round(quiet_h, 1) if quiet_h is not None else None,
            "expected_gap_hours": round(expected_gap_h, 1) if watched and expected_gap_h else None,
            "alert_after_hours": round(threshold_h, 1) if watched and threshold_h else None,
            "alert_sent_at": _utc(s.get("health_alert_sent_at")).isoformat() if _utc(s.get("health_alert_sent_at")) else None,
        })
    order = {"quiet": 0, "slow": 1, "healthy": 2, "new": 3}
    out.sort(key=lambda r: (order[r["status"]], -(r["leads_28d"])))
    return out


def alert_copy(row: dict) -> tuple[str, str]:
    quiet = humanize_hours(row["quiet_hours"] or 0)
    if row.get("expected_gap_hours"):
        usual = f"It usually gets one every {humanize_hours(row['expected_gap_hours'])}."
    else:
        usual = "It used to produce every month."
    return (f"{row['source_name']} has gone quiet",
            f"No leads in {quiet}. {usual} Check the Zap or the vendor feed before more leads go missing.")


async def run_source_health_alerts() -> int:
    """Scheduler job: push store managers once per quiet streak (re-nudge after REMIND_AFTER_DAYS)."""
    from routers.database import get_db
    from routers.push_notifications import send_push_to_user
    db = get_db()
    now = datetime.now(timezone.utc)
    rows = [r for r in await source_health(db) if r["status"] == "quiet"]
    sent = 0
    for r in rows:
        try:
            last = _utc(r["last_lead_at"])
            alerted = _utc(r["alert_sent_at"])
            if alerted and last and alerted > last:
                streak_alerts = await db.source_health_alert_log.count_documents({"source_id": r["source_id"], "sent_at": {"$gt": last}})
                if streak_alerts >= 2 or (now - alerted) < timedelta(days=REMIND_AFTER_DAYS):
                    continue
            if not r.get("store_id"):
                continue
            managers = await db.users.find({"store_id": r["store_id"], "role": {"$in": MANAGER_ROLES},
                                            "status": {"$nin": ["disabled", "suspended"]}}, {"_id": 1, "notification_settings": 1}).to_list(50)
            title, body = alert_copy(r)
            delivered = 0
            for m in managers:
                if (m.get("notification_settings") or {}).get("source_health_alerts") is False:
                    continue
                await send_push_to_user(str(m["_id"]), title, body, "/admin/lead-connect", "pulse")
                delivered += 1
            await db.lead_sources.update_one({"_id": ObjectId(r["source_id"])}, {"$set": {"health_alert_sent_at": now, "health_status": "quiet"}})
            await db.source_health_alert_log.insert_one({**r, "sent_at": now, "recipients": delivered})
            sent += delivered
        except Exception as e:
            logger.warning(f"[SourceHealth] Failed for {r.get('source_name')}: {e}")
    if sent:
        logger.info(f"[SourceHealth] Sent {sent} quiet-source pushes")
    return sent
