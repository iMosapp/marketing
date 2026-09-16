"""My VA settings that are not the persona itself: which industry the VA speaks, and the facts it is allowed to answer with."""
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from routers.database import get_db
from routers.scripts import _resolve, require_user
from services import industries as ind
from services import va_prompt

router = APIRouter(prefix="/va", tags=["My VA"], dependencies=[Depends(require_user)])


class IndustryBody(BaseModel):
    industry: str


class FactBody(BaseModel):
    text: str
    scope: str = "mine"  # mine | store


def _clean(text: str) -> str:
    t = " ".join((text or "").split())
    if len(t) < 3:
        raise HTTPException(status_code=400, detail="Write the fact out, that is too short")
    return t[:240]


async def _fresh(db, me: dict) -> dict:
    return await db.users.find_one({"_id": ObjectId(str(me["_id"]))})


@router.get("/config")
async def config(request: Request):
    me = await _fresh(get_db(), await _resolve(request))
    return await va_prompt.config(get_db(), me)


@router.put("/industry")
async def set_industry(body: IndustryBody, request: Request):
    """Reps whose store has no Industry setting pick their own; a store setting always wins."""
    db = get_db()
    me = await _fresh(db, await _resolve(request))
    if body.industry not in ind.VA:
        raise HTTPException(status_code=400, detail="Unknown industry")
    cur = await ind.va_industry_for(db, me)
    if cur["source"] == "store":
        raise HTTPException(status_code=409, detail=f"Your store is set to {cur['label']}; ask your manager to change it on the store")
    await db.users.update_one({"_id": me["_id"]}, {"$set": {"industry": body.industry, "updated_at": datetime.now(timezone.utc)}})
    return await va_prompt.config(db, await _fresh(db, me))


@router.get("/facts")
async def facts(request: Request):
    db = get_db()
    me = await _fresh(db, await _resolve(request))
    out = await va_prompt.facts_for(db, me)
    return {**out, "store": [_fact_out(f) for f in out["store"]], "mine": [_fact_out(f) for f in out["mine"]], "max": va_prompt.MAX_FACTS}


def _fact_out(f: dict) -> dict:
    at = f.get("at")
    return {"id": f.get("id"), "text": f.get("text"), "added_by_name": f.get("added_by_name"), "at": at.isoformat() if hasattr(at, "isoformat") else at}


async def _target(db, me: dict, scope: str):
    """(collection, filter) the fact lives in; store facts need a manager on that store."""
    if scope == "store":
        info = await va_prompt.facts_for(db, me)
        if not info["store_id"]:
            raise HTTPException(status_code=400, detail="Your account is not on a store")
        if not info["can_edit_store"]:
            raise HTTPException(status_code=403, detail="Managers edit the store's facts; add yours under My facts")
        return db.stores, {"_id": ObjectId(info["store_id"])}
    return db.users, {"_id": me["_id"]}


@router.post("/facts")
async def add_fact(body: FactBody, request: Request):
    db = get_db()
    me = await _fresh(db, await _resolve(request))
    scope = "store" if body.scope == "store" else "mine"
    coll, flt = await _target(db, me, scope)
    cur = (await coll.find_one(flt, {"va_facts": 1}) or {}).get("va_facts") or []
    if len(cur) >= va_prompt.MAX_FACTS:
        raise HTTPException(status_code=400, detail=f"That is {va_prompt.MAX_FACTS} facts already, remove one first")
    await coll.update_one(flt, {"$push": {"va_facts": va_prompt._fact(_clean(body.text), me, scope)}})
    return await facts(request)


@router.put("/facts/{fact_id}")
async def edit_fact(fact_id: str, body: FactBody, request: Request):
    db = get_db()
    me = await _fresh(db, await _resolve(request))
    coll, flt = await _target(db, me, "store" if body.scope == "store" else "mine")
    res = await coll.update_one({**flt, "va_facts.id": fact_id}, {"$set": {"va_facts.$.text": _clean(body.text), "va_facts.$.edited_at": datetime.now(timezone.utc)}})
    if not res.matched_count:
        raise HTTPException(status_code=404, detail="Fact not found")
    return await facts(request)


@router.delete("/facts/{fact_id}")
async def delete_fact(fact_id: str, request: Request, scope: Optional[str] = "mine"):
    db = get_db()
    me = await _fresh(db, await _resolve(request))
    coll, flt = await _target(db, me, "store" if scope == "store" else "mine")
    res = await coll.update_one(flt, {"$pull": {"va_facts": {"id": fact_id}}})
    if not res.modified_count:
        raise HTTPException(status_code=404, detail="Fact not found")
    return await facts(request)
