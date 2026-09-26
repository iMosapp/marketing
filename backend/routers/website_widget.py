"""Website Widget: manager CRUD under /api/widgets, the public embed script + visitor handlers + Twilio ring webhooks under /api/w."""
import copy
import logging
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from routers.database import get_db
from routers.lead_sources import require_manager, require_user
from services import widget_calls as WC
from services import widget_js
from services import widgets as W

logger = logging.getLogger(__name__)

admin = APIRouter(prefix="/widgets", tags=["Website Widget"], dependencies=[Depends(require_user)])
public = APIRouter(prefix="/w", tags=["Website Widget (public)"])

XML = "application/xml"
NO_CACHE = {"Cache-Control": "no-store"}


def _now():
    return datetime.now(timezone.utc)


def _ip(request: Request) -> str:
    return (request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (request.client.host if request.client else "") or "?")


async def _stores_for(db, me: dict) -> list:
    role = me.get("role")
    if role == "super_admin":
        q: dict = {}
    elif role == "org_admin" and me.get("organization_id"):
        oid = me["organization_id"]
        q = {"organization_id": {"$in": [oid, str(oid)] + ([ObjectId(str(oid))] if ObjectId.is_valid(str(oid)) else [])}}
    else:
        ids = [str(s) for s in ([me.get("store_id")] + list(me.get("store_ids") or [])) if s]
        q = {"_id": {"$in": [ObjectId(i) for i in ids if ObjectId.is_valid(i)]}}
    rows = await db.stores.find(q, {"name": 1, "primary_color": 1, "website": 1, "website_url": 1}).sort("name", 1).limit(300).to_list(300)
    return rows


async def _load_scoped(db, me: dict, wid: str) -> dict:
    w = await db[W.COLL].find_one({"_id": ObjectId(wid)}) if ObjectId.is_valid(wid) else None
    if not w:
        raise HTTPException(status_code=404, detail="Widget not found")
    if me.get("role") != "super_admin":
        allowed = await db[W.COLL].count_documents({"_id": w["_id"], **W.scope_query(me)})
        if not allowed:
            raise HTTPException(status_code=403, detail="That widget is outside your scope")
    return w


async def _team_defaults(db, store_id: str, me: dict) -> list:
    from services.team_scope import eligible_people
    scope = await eligible_people(db, store_id, me)
    return [p["id"] for p in scope["people"] if p.get("on_team") and (p.get("phone") or "").strip()][:10]


async def _detail(db, w: dict, me: dict) -> dict:
    store = await W.store_of(db, w)
    from services.lead_timing import store_hours_status
    from services.team_scope import eligible_people
    st = store_hours_status(store)
    scope = await eligible_people(db, w.get("store_id"), me, include_everyone=me.get("role") in ("super_admin", "org_admin"))
    sid_vals = [w.get("store_id")] + ([ObjectId(w["store_id"])] if ObjectId.is_valid(str(w.get("store_id"))) else [])
    inboxes = await db.shared_inboxes.find({"store_id": {"$in": sid_vals}, "is_active": {"$ne": False}}, {"name": 1, "phone_number": 1}).to_list(50) if w.get("store_id") else []
    calls = await db[WC.COLL].find({"widget_id": str(w["_id"])}, {"name": 1, "phone": 1, "status": 1, "winner_first": 1, "seconds_to_connect": 1, "created_at": 1, "page": 1, "missed_reason": 1}).sort("created_at", -1).limit(25).to_list(25)
    return {
        "widget": W.serialize(w, store), "stats": await W.stats(db, w),
        "reps": scope["people"], "store_name": scope["store_name"],
        "inboxes": [{"id": str(i["_id"]), "name": i.get("name"), "phone_number": i.get("phone_number")} for i in inboxes],
        "store_hours": {"configured": st["configured"], "open_now": st["open"], "timezone": st["tz"], "opens_at": st["opens_at"].isoformat() if st.get("opens_at") else None},
        "store_website": store.get("website") or store.get("website_url") or "",
        "recent_calls": [{"id": str(c["_id"]), "name": c.get("name"), "phone_last4": (c.get("phone") or "")[-4:], "status": c.get("status"), "rep": c.get("winner_first"),
                          "seconds": c.get("seconds_to_connect"), "reason": c.get("missed_reason"), "host": W.host_of(c.get("page") or ""),
                          "at": c["created_at"].isoformat() if c.get("created_at") else None} for c in calls],
        "demo_url": f"{W.app_url()}/api/w/{w['key']}/demo",
    }


# ---------------------------------------------------------------- manager API
class CreateBody(BaseModel):
    store_id: str
    name: Optional[str] = ""


class PaletteBody(BaseModel):
    url: str


@admin.get("")
async def list_widgets(request: Request):
    db = get_db()
    me = request.state.user
    rows = await db[W.COLL].find({**W.scope_query(me), "is_active": {"$ne": False}}).sort("created_at", -1).to_list(200)
    stores = await _stores_for(db, me)
    have = {str(r.get("store_id")) for r in rows}
    names = {str(s["_id"]): s for s in stores}
    return {"widgets": [W.serialize(r, names.get(str(r.get("store_id")))) for r in rows],
            "stores": [{"id": str(s["_id"]), "name": s.get("name"), "has_widget": str(s["_id"]) in have} for s in stores],
            "can_manage": W.can_manage(me), "icons": list(W.ICON_CHOICES)}


@admin.post("")
async def create_widget(body: CreateBody, request: Request, _m: dict = Depends(require_manager)):
    """One widget per store. Creating again for the same store returns the existing one."""
    db = get_db()
    me = request.state.user
    if not ObjectId.is_valid(body.store_id):
        raise HTTPException(status_code=400, detail="Pick a store first")
    stores = {str(s["_id"]): s for s in await _stores_for(db, me)}
    store = stores.get(body.store_id)
    if not store:
        raise HTTPException(status_code=403, detail="That store is outside your scope")
    existing = await db[W.COLL].find_one({"store_id": body.store_id, "is_active": {"$ne": False}})
    if existing:
        return {"widget": W.serialize(existing, store), "existing": True}
    cfg = copy.deepcopy(W.DEFAULTS)
    cfg["appearance"]["bubble_color"] = W.hex_or(store.get("primary_color"), cfg["appearance"]["bubble_color"])
    cfg["appearance"]["text_color"] = W.contrast_text(cfg["appearance"]["bubble_color"])
    cfg["routing"]["call_user_ids"] = await _team_defaults(db, body.store_id, me)
    inbox = await db.shared_inboxes.find_one({"store_id": {"$in": [body.store_id, ObjectId(body.store_id)]}, "is_active": {"$ne": False}, "phone_number": {"$nin": [None, ""]}}, sort=[("created_at", 1)])
    cfg["routing"]["inbox_id"] = str(inbox["_id"]) if inbox else ""
    w = {"key": W.new_key(), "name": (body.name or "").strip()[:60] or store.get("name") or "Website Widget", "store_id": body.store_id,
         "organization_id": str(store["organization_id"]) if store.get("organization_id") else None, "store_name": store.get("name"),
         "is_active": True, "domains": [], **cfg, "stats": {}, "created_by": str(me["_id"]), "created_at": _now(), "updated_at": _now()}
    res = await db[W.COLL].insert_one(w)
    w["_id"] = res.inserted_id
    w["lead_source_id"] = await W.sync_lead_source(db, w, store)
    await db[W.COLL].update_one({"_id": w["_id"]}, {"$set": {"lead_source_id": w["lead_source_id"]}})
    logger.info(f"[Widget] created {w['key']} for store {store.get('name')} by {me.get('email')}")
    return {"widget": W.serialize(w, store), "existing": False}


@admin.post("/palette")
async def palette(body: PaletteBody, _m: dict = Depends(require_manager)):
    """Pull the brand colors off a dealership's site so the bubble can match it exactly."""
    try:
        return await W.site_palette(body.url.strip())
    except Exception as e:
        logger.info(f"[Widget] palette failed for {body.url}: {e}")
        raise HTTPException(status_code=400, detail="Couldn't read that site. Check the address or pick the color by hand.")


@admin.get("/{wid}")
async def get_widget(wid: str, request: Request):
    db = get_db()
    me = request.state.user
    return await _detail(db, await _load_scoped(db, me, wid), me)


@admin.put("/{wid}")
async def update_widget(wid: str, request: Request, _m: dict = Depends(require_manager)):
    db = get_db()
    me = request.state.user
    w = await _load_scoped(db, me, wid)
    patch = await request.json()
    if not isinstance(patch, dict):
        raise HTTPException(status_code=400, detail="Bad payload")
    merged = {**w, **{k: patch[k] for k in W.DEFAULTS if isinstance(patch.get(k), dict)}}
    for k in W.DEFAULTS:
        if isinstance(patch.get(k), dict):
            merged[k] = W._merge(w.get(k) or {}, patch[k])
    cfg = W.normalize_config(merged)
    sets = {**cfg, "updated_at": _now()}
    if "name" in patch:
        sets["name"] = str(patch.get("name") or "").strip()[:60] or w.get("name")
    if "domains" in patch:
        sets["domains"] = [W.host_of(d if "://" in d else f"https://{d}") for d in (patch.get("domains") or []) if isinstance(d, str) and d.strip()][:10]
    if "is_active" in patch:
        sets["is_active"] = bool(patch["is_active"])
    await db[W.COLL].update_one({"_id": w["_id"]}, {"$set": sets})
    w = await db[W.COLL].find_one({"_id": w["_id"]})
    store = await W.store_of(db, w)
    await W.sync_lead_source(db, w, store)
    return {"widget": W.serialize(w, store)}


@admin.post("/{wid}/rotate-key")
async def rotate_key(wid: str, request: Request, _m: dict = Depends(require_manager)):
    """New install key: the old script tag stops working (use when a key leaks or a site is retired)."""
    db = get_db()
    w = await _load_scoped(db, request.state.user, wid)
    key = W.new_key()
    await db[W.COLL].update_one({"_id": w["_id"]}, {"$set": {"key": key, "updated_at": _now(), "last_seen_at": None, "last_seen_host": None}})
    w = await db[W.COLL].find_one({"_id": w["_id"]})
    return {"widget": W.serialize(w, await W.store_of(db, w))}


@admin.delete("/{wid}")
async def delete_widget(wid: str, request: Request, _m: dict = Depends(require_manager)):
    db = get_db()
    w = await _load_scoped(db, request.state.user, wid)
    await db[W.COLL].update_one({"_id": w["_id"]}, {"$set": {"is_active": False, "updated_at": _now()}})
    if w.get("lead_source_id") and ObjectId.is_valid(str(w["lead_source_id"])):
        await db.lead_sources.update_one({"_id": ObjectId(w["lead_source_id"])}, {"$set": {"is_active": False}})
    return {"ok": True}


@admin.get("/{wid}/stats")
async def widget_stats(wid: str, request: Request):
    db = get_db()
    return await W.stats(db, await _load_scoped(db, request.state.user, wid))


# ---------------------------------------------------------------- public: the embed + visitor handlers
async def _widget_or_404(db, key: str) -> dict:
    w = await W.load(db, key)
    if not w:
        raise HTTPException(status_code=404, detail="Widget not found")
    return w


def _preview_overrides(request: Request) -> dict:
    """?c=<base64url json> lets the admin screen preview unsaved look/copy changes."""
    raw = request.query_params.get("c")
    if not raw:
        return {}
    try:
        import base64
        import json
        pad = "=" * (-len(raw) % 4)
        data = json.loads(base64.urlsafe_b64decode(raw + pad).decode("utf-8"))
        return {k: v for k, v in data.items() if k in ("appearance", "doors", "copy") and isinstance(v, dict)}
    except Exception:
        return {}


@public.get("/{key}.js")
async def widget_script(key: str, request: Request):
    db = get_db()
    w = await W.load(db, key)
    if not w:
        return Response("/* i'M On Social widget: unknown or disabled key */", media_type="application/javascript; charset=utf-8", status_code=404)
    store = await W.store_of(db, w)
    preview = request.query_params.get("preview") == "1"
    over = _preview_overrides(request)
    cfg = W.public_config(W._merge(w, over) if over else w, store, preview=preview or bool(over))
    return Response(widget_js.render(cfg), media_type="application/javascript; charset=utf-8",
                    headers={"Cache-Control": "no-store" if (preview or over) else "public, max-age=120"})


@public.get("/{key}/demo", response_class=HTMLResponse)
async def widget_demo(key: str, request: Request):
    """A stand-in dealership page with the widget installed, used for the in-app preview (and to show a client)."""
    db = get_db()
    w = await _widget_or_404(db, key)
    store = await W.store_of(db, w)
    over = _preview_overrides(request)
    cfg = W.public_config(W._merge(w, over) if over else w, store, preview=True)
    return HTMLResponse(widget_js.demo_html(store.get("name") or w.get("name") or "Your Dealership", widget_js.render(cfg)), headers=NO_CACHE)


@public.get("/{key}/config")
async def widget_config(key: str):
    db = get_db()
    w = await _widget_or_404(db, key)
    return W.public_config(w, await W.store_of(db, w))


@public.post("/{key}/event")
async def widget_event(key: str, request: Request):
    db = get_db()
    w = await W.load(db, key)
    body = await request.json()
    if not w or not isinstance(body, dict) or body.get("kind") not in ("load", "open", "greeting") or not W.allow(_ip(request), "event", 120):
        return {"ok": False}
    if not W.domain_ok(w, body.get("page") or ""):
        return {"ok": False, "reason": "domain"}
    await W.log_event(db, w, body["kind"], body)
    return {"ok": True}


@public.post("/{key}/text")
async def widget_text(key: str, request: Request):
    db = get_db()
    w = await _widget_or_404(db, key)
    body = await request.json()
    if not W.domain_ok(w, body.get("page") or ""):
        raise HTTPException(status_code=403, detail="This widget isn't set up for this website yet.")
    try:
        return await W.text_lead(db, w, body, _ip(request))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@public.post("/{key}/call")
async def widget_call(key: str, request: Request):
    db = get_db()
    w = await _widget_or_404(db, key)
    body = await request.json()
    if not W.domain_ok(w, body.get("page") or ""):
        raise HTTPException(status_code=403, detail="This widget isn't set up for this website yet.")
    if not W.normalize_config(w)["doors"]["call"]["on"]:
        raise HTTPException(status_code=400, detail="Call me now is turned off for this site.")
    try:
        return await WC.request_call(db, w, body, _ip(request))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@public.get("/{key}/call/{req_id}")
async def widget_call_status(key: str, req_id: str):
    return await WC.visitor_status(get_db(), key, req_id)


# ---------------------------------------------------------------- Twilio: the ring group
@public.post("/ring/{req_id}/{token}")
async def ring(req_id: str, token: str):
    return Response(await WC.ring_twiml(get_db(), req_id, token), media_type=XML)


@public.post("/ring-answer/{req_id}/{token}")
async def ring_answer(req_id: str, token: str, Digits: str = Form("")):
    return Response(await WC.answer_twiml(get_db(), req_id, token, Digits), media_type=XML)


@public.post("/ring-status/{req_id}/{token}")
async def ring_status(req_id: str, token: str, CallStatus: str = Form("")):
    await WC.leg_status(get_db(), req_id, token, CallStatus)
    return Response("OK", media_type="text/plain")


@public.post("/ring-customer/{req_id}")
async def ring_customer(req_id: str, CallStatus: str = Form(""), CallDuration: str = Form("0")):
    await WC.customer_status(get_db(), req_id, CallStatus, CallDuration)
    return Response("OK", media_type="text/plain")
