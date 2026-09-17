"""Live Jessi (GPT-Live-1): WebRTC session brokering, client delegation and the admin Voice Lab."""
import os
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from routers.database import get_db
from routers.scripts import _resolve, require_user
from services import lab
from services import live_voice as lv

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/live-voice", tags=["Live Jessi"], dependencies=[Depends(require_user)])


class SessionBody(BaseModel):
    mode: str = "assistant"
    sdp: str
    overrides: Optional[dict] = None
    contact_id: Optional[str] = None


class DelegateBody(BaseModel):
    delegation_id: Optional[str] = None
    transcript: list = []


class EventsBody(BaseModel):
    events: list = []


class ConfigBody(BaseModel):
    voice: Optional[str] = None
    energy: Optional[int] = None
    pacing: Optional[int] = None
    playful: Optional[int] = None
    brevity: Optional[int] = None
    daily_cap_min: Optional[int] = None
    idle_close_s: Optional[int] = None
    greeting: Optional[str] = None
    contact_greeting: Optional[str] = None
    notes: Optional[str] = None


def _is_super(me: dict) -> bool:
    return me.get("role") == "super_admin"


async def _super(request: Request) -> dict:
    me = await _resolve(request)
    if not _is_super(me):
        raise HTTPException(status_code=403, detail="The Voice Lab is for the app owner")
    return me


async def _available(db, me: dict) -> bool:
    return _is_super(me) or await lab.visible(db, me, lv.LAB_KEY)


async def _owned(db, live_id: str, me: dict) -> dict:
    live = await lv.get_live(db, live_id)
    if not live or (live.get("user_id") != str(me["_id"]) and not _is_super(me)):
        raise HTTPException(status_code=404, detail="Session not found")
    return live


@router.get("/config")
async def config(request: Request):
    me = await _resolve(request)
    db = get_db()
    cfg = await lv.get_config(db)
    reason = lv.configured()
    return {"available": await _available(db, me), "is_super_admin": _is_super(me), "configured": reason is None, "reason": reason,
            "voice": cfg["voice"], "greeting": lv.greeting_text(cfg, me), "idle_close_s": cfg["idle_close_s"], "usage": await lv.usage_summary(db, str(me["_id"]), cfg)}


@router.post("/session")
async def start_session(body: SessionBody, request: Request):
    me = await _resolve(request)
    db = get_db()
    if body.mode in ("lab", "shopper") and not _is_super(me):
        raise HTTPException(status_code=403, detail="The Voice Lab is for the app owner")
    if body.mode == "assistant" and not await _available(db, me):
        raise HTTPException(status_code=403, detail="Live Jessi is not switched on for your account yet")
    if not body.sdp.strip():
        raise HTTPException(status_code=400, detail="An SDP offer is required")
    try:
        return await lv.create_session(db, me, body.mode, body.sdp, body.overrides, body.contact_id)
    except lv.LiveUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e))
    except lv.LiveCapReached as e:
        raise HTTPException(status_code=429, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{live_id}/delegate")
async def delegate(live_id: str, body: DelegateBody, request: Request):
    me = await _resolve(request)
    db = get_db()
    live = await _owned(db, live_id, me)
    if live.get("status") != "open":
        raise HTTPException(status_code=409, detail="That session is closed")
    return await lv.delegate(db, live, me, body.transcript[-40:], body.delegation_id)


@router.post("/{live_id}/events")
async def events(live_id: str, body: EventsBody, request: Request):
    me = await _resolve(request)
    db = get_db()
    live = await _owned(db, live_id, me)
    sets = await lv.record_events(db, live, body.events[:400])
    return {"ok": True, "status": sets.get("status") or live.get("status"), "seconds": sets.get("seconds", live.get("seconds") or 0)}


# ── admin: Voice Lab ─────────────────────────────────────────────────────────
@router.get("/admin/config")
async def admin_config(request: Request):
    await _super(request)
    db = get_db()
    return {"config": await lv.get_config(db), "defaults": lv.DEFAULTS, "voices": lv.VOICES, "configured": lv.configured() is None, "reason": lv.configured(),
            "labels": {"energy": lv.ENERGY, "pacing": lv.PACING, "playful": lv.PLAYFUL, "brevity": lv.BREVITY}, "price_per_min": lv.PRICE_PER_MIN, "model": lv.MODEL,
            "lab_live": await lab.is_live(db, lv.LAB_KEY)}


@router.put("/admin/config")
async def admin_save(body: ConfigBody, request: Request):
    me = await _super(request)
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    if patch.get("voice") and patch["voice"] not in lv.VOICE_IDS:
        raise HTTPException(status_code=400, detail="Unknown voice")
    return {"config": await lv.save_config(get_db(), patch, me)}


@router.get("/admin/preview")
async def admin_preview(request: Request, voice: str = "", energy: int = 0, pacing: int = 0, playful: int = 0, brevity: int = 0, notes: str = ""):
    """The exact personality text GPT-Live would get for these unsaved settings."""
    me = await _super(request)
    cfg = await lv.get_config(get_db())
    patch = {k: v for k, v in {"voice": voice, "energy": energy, "pacing": pacing, "playful": playful, "brevity": brevity, "notes": notes}.items() if v}
    cfg = lv.clean_config(patch, {k: cfg[k] for k in lv.DEFAULTS})
    return {"personality": lv.personality(cfg), "greeting": lv.greeting_text(cfg, me)}


@router.get("/admin/sessions")
async def admin_sessions(request: Request, limit: int = 30, user_id: str = ""):
    await _super(request)
    db = get_db()
    await lv.close_stale(db)
    return {"sessions": await lv.list_sessions(db, limit, user_id or None), "stats": await lv.stats(db)}


@router.get("/admin/sessions/{live_id}")
async def admin_session(live_id: str, request: Request):
    await _super(request)
    live = await lv.get_live(get_db(), live_id)
    if not live:
        raise HTTPException(status_code=404, detail="Session not found")
    return lv.serialize(live, full=True)


@router.get("/{live_id}")
async def my_session(live_id: str, request: Request):
    me = await _resolve(request)
    return lv.serialize(await _owned(get_db(), live_id, me), full=True)
