"""
Scheduler Admin Router
Provides status, manual trigger, and configuration endpoints for the campaign scheduler.
"""
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone
import logging

from routers.rbac import require_role

router = APIRouter(prefix="/scheduler", tags=["Scheduler"], dependencies=[Depends(require_role("super_admin"))])
logger = logging.getLogger(__name__)


@router.get("/status")
async def scheduler_status():
    """Health check for the background scheduler."""
    from scheduler import get_scheduler_state, scheduler

    state = get_scheduler_state()
    jobs = []
    if scheduler.running:
        for job in scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger),
            })

    return {
        "running": state["running"],
        "jobs": jobs,
        "last_date_trigger_run": state["last_date_trigger_run"],
        "last_campaign_step_run": state["last_campaign_step_run"],
        "last_lifecycle_scan_run": state.get("last_lifecycle_scan_run"),
        "date_trigger_results": state["date_trigger_results"],
        "campaign_step_results": state["campaign_step_results"],
        "lifecycle_scan_results": state.get("lifecycle_scan_results", {}),
        "recent_errors": state["errors"][-5:],
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/trigger/date-triggers")
async def manual_trigger_date_triggers():
    """Manually fire the daily date-trigger sweep (for testing / admin use)."""
    from scheduler import process_all_date_triggers

    logger.info("[Scheduler Admin] Manual date-trigger sweep requested")
    try:
        await process_all_date_triggers()
        from scheduler import get_scheduler_state
        return {
            "message": "Date-trigger sweep completed",
            "results": get_scheduler_state()["date_trigger_results"],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/trigger/campaign-steps")
async def manual_trigger_campaign_steps():
    """Manually fire the campaign step processor (for testing / admin use)."""
    from scheduler import process_pending_campaign_steps

    logger.info("[Scheduler Admin] Manual campaign-step processing requested")
    try:
        await process_pending_campaign_steps()
        from scheduler import get_scheduler_state
        return {
            "message": "Campaign step processing completed",
            "results": get_scheduler_state()["campaign_step_results"],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/trigger/lifecycle-scan")
async def manual_trigger_lifecycle_scan():
    """Manually fire the daily lifecycle scan (for testing / admin use)."""
    from scheduler import run_daily_lifecycle_scan

    logger.info("[Scheduler Admin] Manual lifecycle scan requested")
    try:
        await run_daily_lifecycle_scan()
        from scheduler import get_scheduler_state
        return {
            "message": "Lifecycle scan completed",
            "results": get_scheduler_state().get("lifecycle_scan_results", {}),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/campaign-reliability")
async def campaign_reliability_status():
    """The CAMPAIGN_RELIABILITY_V2 switch and the touch queue by state (read-only health check)."""
    import os
    from routers.database import get_db
    from services import campaign_reliability as rel
    db = get_db()
    env = os.environ.get(rel.FLAG, "").strip().lower()
    row = await db.settings.find_one({"key": rel.SETTINGS_KEY}, {"_id": 0}) or {}
    counts = {r["_id"]: r["n"] async for r in db.campaign_pending_sends.aggregate([{"$group": {"_id": "$status", "n": {"$sum": 1}}}])}
    oldest = await db.campaign_pending_sends.find_one({"status": "processing"}, {"locked_at": 1}, sort=[("locked_at", 1)])
    return {"enabled": await rel.enabled(db), "env": env or None, "setting": bool(row.get("enabled")), "set_by": row.get("set_by"),
            "set_at": row.get("set_at"), "counts": counts, "oldest_processing_locked_at": (oldest or {}).get("locked_at")}


@router.put("/campaign-reliability")
async def set_campaign_reliability(data: dict, current_user: dict = Depends(require_role("super_admin"))):
    """Turn the switch on or off for THIS environment's database. The env var, when set, wins."""
    from routers.database import get_db
    from services import campaign_reliability as rel
    db = get_db()
    on = bool(data.get("enabled"))
    await db.settings.update_one({"key": rel.SETTINGS_KEY}, {"$set": {"key": rel.SETTINGS_KEY, "enabled": on, "set_by": str(current_user.get("_id") or ""),
                                                                    "set_at": datetime.now(timezone.utc)}}, upsert=True)
    logger.warning(f"[Scheduler Admin] campaign reliability v2 switched {'ON' if on else 'OFF'} by {current_user.get('_id')}")
    return await campaign_reliability_status()
