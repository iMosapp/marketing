"""
Scheduler Admin Router
Provides status, manual trigger, and configuration endpoints for the campaign scheduler.
"""
from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone
import logging

router = APIRouter(prefix="/scheduler", tags=["Scheduler"])
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
