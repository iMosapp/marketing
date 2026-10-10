"""Living Relationship Intelligence API (Phase 1A): read the facts and the brief, confirm or dispute with the right permissions, suggest corrections, plan the backfill.
Nothing here sends a message or changes a contact's legacy fields."""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from routers.contact_ask import _contact, require_user
from routers.database import get_db
from services.intelligence import backfill, brief, config, ingest, projection, state, timeline
from services.intelligence import facts as F
from services.lead_flows import MANAGER_ROLES, user_store_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/intel", tags=["Intelligence"], dependencies=[Depends(require_user)])
EXEC_ROLES = {"super_admin", "admin"}


class NoteBody(BaseModel):
    note: Optional[str] = ""


class SuggestBody(BaseModel):
    key: str
    statement: str
    value: Optional[dict] = None
    layer: str = "state"
    domain: str = "note"
    occurred_at: Optional[str] = None
    note: Optional[str] = ""


class ExecuteBody(BaseModel):
    confirm: str = ""
    store_id: Optional[str] = None
    batch: int = 200
    run_id: Optional[str] = None


class RollbackBody(BaseModel):
    confirm: str = ""
    contact_id: Optional[str] = None


def can_verify(user: dict, contact: dict) -> bool:
    """Owner rep, or a manager/admin of the contact's store, or the platform owner/super admin."""
    uid, role = str(user["_id"]), user.get("role")
    if str(contact.get("user_id") or "") == uid or role in EXEC_ROLES or user.get("is_owner"):
        return True
    if role in MANAGER_ROLES:
        sid = user_store_id(user)
        return bool(sid) and str(contact.get("store_id") or "") == sid
    return False


def _manager(user: dict):
    if user.get("role") not in MANAGER_ROLES and not user.get("is_owner"):
        raise HTTPException(status_code=403, detail="Managers only")


async def _fact_and_contact(db, user: dict, fact_id: str) -> tuple:
    from bson import ObjectId
    f = F.hydrate(await db[F.FACTS].find_one({"_id": ObjectId(fact_id)})) if ObjectId.is_valid(fact_id) else None
    if not f:
        raise HTTPException(status_code=404, detail="Fact not found")
    return f, await _contact(db, user, f["contact_id"])


@router.get("/config")
async def get_config(request: Request, store_id: Optional[str] = None):
    me = request.state.user
    return {"flags": config.flags(), "settings": await config.settings(get_db(), store_id or user_store_id(me)), "phase": "1A"}


@router.get("/contacts/{contact_id}/facts")
async def list_facts(contact_id: str, request: Request, status: Optional[str] = None, layer: Optional[str] = None, key: Optional[str] = None, limit: int = 500):
    db = get_db()
    me = request.state.user
    contact = await _contact(db, me, contact_id)
    q: dict = {"contact_id": str(contact["_id"])}
    if status:
        q["status"] = {"$in": status.split(",")}
    if layer:
        q["layer"] = {"$in": layer.split(",")}
    if key:
        q["key"] = key
    rows = await F.load(db, q, sort=[("occurred_at", -1)], limit=max(1, min(2000, limit)))
    return {"facts": [F.pub(f) for f in rows], "can_verify": can_verify(me, contact), "flags": config.flags()}


@router.get("/contacts/{contact_id}/state")
async def get_state(contact_id: str, request: Request):
    db = get_db()
    contact = await _contact(db, request.state.user, contact_id)
    return await state.build(db, contact, await config.settings(db, contact.get("store_id")))


@router.get("/contacts/{contact_id}/brief")
async def get_brief(contact_id: str, request: Request):
    db = get_db()
    me = request.state.user
    contact = await _contact(db, me, contact_id)
    out = await brief.build(db, contact)
    out["can_verify"] = can_verify(me, contact)
    return out


@router.get("/contacts/{contact_id}/timeline")
async def get_timeline(contact_id: str, request: Request):
    """Recommended / Active / Current / Historical markers for the contact screen; {"enabled": false} while ingest is off so the screen stays unchanged."""
    db = get_db()
    me = request.state.user
    contact = await _contact(db, me, contact_id)
    out = await timeline.build(db, contact)
    out["can_verify"] = can_verify(me, contact)
    return out


@router.get("/facts/{fact_id}/source")
async def fact_source(fact_id: str, request: Request):
    """Why we think this: the record behind the fact (excerpt, when, who, where to open it)."""
    db = get_db()
    f, contact = await _fact_and_contact(db, request.state.user, fact_id)
    return await timeline.source(db, F.pub(f), contact)


@router.get("/facts/{fact_id}/events")
async def fact_events(fact_id: str, request: Request):
    db = get_db()
    f, _ = await _fact_and_contact(db, request.state.user, fact_id)
    return {"fact": F.pub(f), "events": await F.events_for(db, f["_id"])}


@router.post("/facts/{fact_id}/confirm")
async def confirm_fact(fact_id: str, body: NoteBody, request: Request):
    db = get_db()
    me = request.state.user
    f, contact = await _fact_and_contact(db, me, fact_id)
    if not can_verify(me, contact):
        raise HTTPException(status_code=403, detail="Only the contact's owner or a manager of this store can confirm a fact; you can suggest a correction instead")
    out = F.pub(await F.confirm(db, f["_id"], me, note=body.note or ""))
    return {"fact": out, "projection": await ingest.sync_legacy(db, f["contact_id"], contact.get("store_id"))}


@router.post("/facts/{fact_id}/dispute")
async def dispute_fact(fact_id: str, body: NoteBody, request: Request):
    db = get_db()
    me = request.state.user
    f, contact = await _fact_and_contact(db, me, fact_id)
    if not can_verify(me, contact):
        raise HTTPException(status_code=403, detail="Only the contact's owner or a manager of this store can dispute a fact; you can suggest a correction instead")
    out = F.pub(await F.dispute(db, f["_id"], me, note=body.note or ""))
    return {"fact": out, "projection": await ingest.sync_legacy(db, f["contact_id"], contact.get("store_id"))}


@router.post("/contacts/{contact_id}/facts/suggest")
async def suggest_fact(contact_id: str, body: SuggestBody, request: Request):
    """Anyone who can see the contact may suggest; it lands as current+confirmed for verifiers and as proposed for everyone else. Verified facts are never silently overwritten."""
    db = get_db()
    me = request.state.user
    contact = await _contact(db, me, contact_id)
    if body.layer not in F.LAYERS:
        raise HTTPException(status_code=400, detail="Unknown layer")
    verifier = can_verify(me, contact)
    at = ingest._ts(body.occurred_at) if body.occurred_at else None
    f = F.make(contact, layer=body.layer, domain=body.domain, key=body.key.strip(), statement=body.statement.strip(), value=body.value, occurred_at=at,
               source={"kind": "rep", "ref": f"user:{me['_id']}", "quote": (body.note or "")[:220] or None}, confidence="high" if verifier else "medium", actor=me if verifier else None)
    if not verifier:
        f["status"] = "proposed"
        f["source"]["suggested_by"] = {"user_id": str(me["_id"]), "name": me.get("name") or me.get("email")}
    r = await F.record(db, f, me if verifier else None)
    proj = await ingest.sync_legacy(db, str(contact["_id"]), contact.get("store_id")) if r["action"] != "duplicate" else {"written": False, "sets": {}}
    return {"fact": F.pub(r["fact"]), "action": r["action"], "as_verifier": verifier, "projection": proj}


@router.get("/backfill/dry-run")
async def backfill_dry_run(request: Request, store_id: Optional[str] = None, limit: Optional[int] = None, persist: bool = False):
    """Read-only inventory of what the backfill would write. Store managers see their own store; owner/super admin any store or all."""
    me = request.state.user
    _manager(me)
    if me.get("role") not in EXEC_ROLES and not me.get("is_owner"):
        store_id = user_store_id(me)
        if not store_id:
            raise HTTPException(status_code=403, detail="No store on your account")
    return await backfill.dry_run(get_db(), store_id=store_id, limit=limit, persist=persist)


@router.get("/backfill/runs")
async def backfill_runs(request: Request):
    _manager(request.state.user)
    return {"runs": await backfill.runs(get_db())}


@router.post("/backfill/execute")
async def backfill_execute(body: ExecuteBody, request: Request):
    me = request.state.user
    if me.get("role") not in EXEC_ROLES and not me.get("is_owner"):
        raise HTTPException(status_code=403, detail="Owner or super admin only")
    try:
        return await backfill.execute(get_db(), confirm=body.confirm, store_id=body.store_id, batch=max(1, min(1000, body.batch)), run_id=body.run_id)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.get("/projection/snapshots")
async def projection_snapshots(request: Request):
    """How many contacts have had legacy fields rewritten by the projection (each keeps its pre-projection values for rollback)."""
    _manager(request.state.user)
    db = get_db()
    return {"contacts_projected": await db[projection.SNAPSHOTS].count_documents({}), "flags": config.flags()}


@router.post("/projection/rollback")
async def projection_rollback(body: RollbackBody, request: Request):
    """Owner / super admin only, confirm=ROLLBACK: legacy fields go back to their pre-projection values; facts stay."""
    me = request.state.user
    if me.get("role") not in EXEC_ROLES and not me.get("is_owner"):
        raise HTTPException(status_code=403, detail="Owner or super admin only")
    if body.confirm != "ROLLBACK":
        raise HTTPException(status_code=400, detail="confirm must be ROLLBACK")
    return await projection.rollback(get_db(), contact_id=body.contact_id)
