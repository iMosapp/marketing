"""Platform cron webhooks (.emergent/crons.yml). Each endpoint checks the shared secret, claims the run id once and hands the work to a background task."""
import hmac
import json
import logging
import os
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request

from routers.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/cron", tags=["Cron"])
RUNS = "cron_runs"


def _check(authorization: str | None):
    secret = os.environ.get("WEBHOOK_CRON_SECRET") or ""
    token = authorization[7:].strip() if authorization and authorization.startswith("Bearer ") else ""
    if not secret or not token or not hmac.compare_digest(token, secret):
        raise HTTPException(status_code=401, detail="Unauthorized")


async def _envelope(request: Request) -> dict:
    raw = await request.body()
    if not raw:
        return {}
    try:
        body = json.loads(raw)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid request body")
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Invalid request body")
    return body


async def _claim(db, name: str, run_id: str) -> str | None:
    """First delivery of a run id wins; a duplicate is acknowledged and does nothing."""
    key = f"{name}:{run_id or datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
    r = await db[RUNS].update_one({"_id": key}, {"$setOnInsert": {"name": name, "run_id": run_id, "at": datetime.now(timezone.utc), "result": None}}, upsert=True)
    return key if r.upserted_id is not None else None


async def _morning_brief(db, key: str):
    from services.leadership import morning
    try:
        res = await morning.tick(db)
    except Exception as e:
        logger.exception("[Cron] morning brief tick failed")
        res = {"error": str(e)[:300]}
    await db[RUNS].update_one({"_id": key}, {"$set": {"result": res, "finished_at": datetime.now(timezone.utc)}})
    logger.info("[Cron] leadership morning brief: %s", res)


@router.post("/leadership-morning-brief")
async def leadership_morning_brief(request: Request, background: BackgroundTasks, authorization: str | None = Header(None), x_webhook_id: str | None = Header(None)):
    # Cron endpoints must ack 2xx immediately; enqueue/background the actual work.
    _check(authorization)
    body = await _envelope(request)
    key = await _claim(get_db(), "lt-morning-brief", str(x_webhook_id or body.get("run_id") or ""))
    if not key:
        return {"ok": True, "duplicate": True}
    background.add_task(_morning_brief, get_db(), key)
    return {"ok": True, "accepted": True, "run": key}


async def _pilot_reminders(db, key: str):
    from services import pilot_program
    try:
        res = await pilot_program.tick(db)
    except Exception as e:
        logger.exception("[Cron] pilot reminders tick failed")
        res = {"error": str(e)[:300]}
    await db[RUNS].update_one({"_id": key}, {"$set": {"result": res, "finished_at": datetime.now(timezone.utc)}})
    logger.info("[Cron] pilot reminders: %s", res)


@router.post("/pilot-reminders")
async def pilot_reminders(request: Request, background: BackgroundTasks, authorization: str | None = Header(None), x_webhook_id: str | None = Header(None)):
    # Cron endpoints must ack 2xx immediately; enqueue/background the actual work.
    _check(authorization)
    body = await _envelope(request)
    key = await _claim(get_db(), "pilot-reminders", str(x_webhook_id or body.get("run_id") or ""))
    if not key:
        return {"ok": True, "duplicate": True}
    background.add_task(_pilot_reminders, get_db(), key)
    return {"ok": True, "accepted": True, "run": key}
