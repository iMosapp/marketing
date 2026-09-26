"""Website Widget: manager CRUD under /api/widgets, the public embed script + visitor handlers + Twilio ring webhooks under /api/w."""
import copy
import logging
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from routers.database import get_db
from routers.lead_sources import require_manager, require_user
from services import widget_calls as WC
from services import widget_chat as WCH
from services import widget_crawl as WCR
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
        "widget": W.serialize(w, store), "stats": await W.stats(db, w), "door_stats": await W.door_stats(db, w, 7),
        "reps": scope["people"], "store_name": scope["store_name"],
        "inboxes": [{"id": str(i["_id"]), "name": i.get("name"), "phone_number": i.get("phone_number")} for i in inboxes],
        "store_hours": {"configured": st["configured"], "open_now": st["open"], "timezone": st["tz"], "opens_at": st["opens_at"].isoformat() if st.get("opens_at") else None},
        "store_website": store.get("website") or store.get("website_url") or "",
        "recent_calls": [{"id": str(c["_id"]), "name": c.get("name"), "phone_last4": (c.get("phone") or "")[-4:], "status": c.get("status"), "rep": c.get("winner_first"),
                          "seconds": c.get("seconds_to_connect"), "reason": c.get("missed_reason"), "host": W.host_of(c.get("page") or ""),
                          "at": c["created_at"].isoformat() if c.get("created_at") else None} for c in calls],
        "demo_url": f"{W.app_url()}/api/w/{w['key']}/demo", "can_manage": W.can_manage(me),
        "facts": [{"id": f.get("id"), "text": f.get("text"), "added_by_name": f.get("added_by_name")} for f in store.get("va_facts") or [] if f.get("text")],
        "recent_chats": [{"id": c["sid"], "status": c.get("status"), "name": c.get("name") or "Visitor", "turns": c.get("turns", 0), "reason": c.get("handoff_reason") or "",
                          "host": c.get("host") or "", "at": c["created_at"].isoformat() if c.get("created_at") else None, "mode": c.get("mode") or "jessi", "agent": c.get("rep_first") or "",
                          "booked": bool(c.get("booking")), "live": bool(c.get("visitor_seen_at")) and (_now() - c["visitor_seen_at"].replace(tzinfo=timezone.utc)).total_seconds() < 120 and c.get("status") != "closed",
                          "last": next((m["text"] for m in reversed(c.get("messages") or []) if m.get("role") == "visitor"), "")[:120]}
                         for c in await db[WCH.COLL].find({"widget_id": str(w["_id"])}, {"messages": {"$slice": -6}, "sid": 1, "status": 1, "name": 1, "turns": 1, "handoff_reason": 1, "host": 1, "created_at": 1, "mode": 1, "rep_first": 1, "booking": 1, "visitor_seen_at": 1}).sort("created_at", -1).limit(20).to_list(20)],
    }


# ---------------------------------------------------------------- manager API
class CreateBody(BaseModel):
    store_id: str
    name: Optional[str] = ""


class PaletteBody(BaseModel):
    url: str


class AskBody(BaseModel):
    question: str


class FactBody(BaseModel):
    text: str


class CrawlBody(BaseModel):
    url: str


class RepText(BaseModel):
    text: str


class LeadBody(BaseModel):
    name: Optional[str] = ""
    phone: Optional[str] = ""


# ---------------------------------------------------------------- live chats (reps jump in) — declared before /{wid} so "chats" never reads as a widget id
async def _chat_scoped(db, me: dict, sid: str):
    s = await db[WCH.COLL].find_one({"sid": sid})
    if not s:
        raise HTTPException(status_code=404, detail="That chat is gone")
    w = await db[W.COLL].find_one({"_id": ObjectId(s["widget_id"])}) if ObjectId.is_valid(str(s.get("widget_id"))) else None
    if not w:
        raise HTTPException(status_code=404, detail="Widget not found")
    if me.get("role") != "super_admin" and not await db[W.COLL].count_documents({"_id": w["_id"], **W.scope_query(me)}):
        raise HTTPException(status_code=403, detail="That chat is outside your scope")
    return w, s


@admin.get("/chats/live")
async def live_chats(request: Request):
    """Web chats happening right now on the stores I can see, newest first."""
    db = get_db()
    me = request.state.user
    widgets = await db[W.COLL].find({**W.scope_query(me), "is_active": {"$ne": False}}, {"store_name": 1}).to_list(200)
    names = {str(w["_id"]): w.get("store_name") or "" for w in widgets}
    rows = await WCH.live_list(db, list(names))
    return {"chats": [WCH.summary(s, names.get(str(s.get("widget_id")), "")) for s in rows], "me": str(me["_id"])}


@admin.get("/chats/by-conversation/{conversation_id}")
async def chat_for_conversation(conversation_id: str, request: Request):
    db = get_db()
    s = await WCH.for_conversation(db, conversation_id)
    if not s:
        return {"chat": None}
    try:
        w, s = await _chat_scoped(db, request.state.user, s["sid"])
    except HTTPException:
        return {"chat": None}
    return {"chat": WCH.summary(s, w.get("store_name") or "")}


@admin.get("/chats/{sid}")
async def chat_detail(sid: str, request: Request):
    db = get_db()
    w, s = await _chat_scoped(db, request.state.user, sid)
    if s.get("mode") == "human" and str(s.get("rep_user_id")) == str(request.state.user["_id"]):
        await WCH.mark_read(db, s)
        s["rep_unread"] = 0
    return {**WCH.rep_view(s), "store_name": w.get("store_name") or "", "widget_id": str(w["_id"])}


@admin.post("/chats/{sid}/join")
async def chat_join(sid: str, request: Request):
    db = get_db()
    w, s = await _chat_scoped(db, request.state.user, sid)
    try:
        return await WCH.join(db, w, s, request.state.user)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@admin.post("/chats/{sid}/message")
async def chat_rep_message(sid: str, body: RepText, request: Request):
    db = get_db()
    w, s = await _chat_scoped(db, request.state.user, sid)
    try:
        return await WCH.rep_message(db, w, s, request.state.user, body.text)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@admin.post("/chats/{sid}/leave")
async def chat_leave(sid: str, request: Request):
    db = get_db()
    w, s = await _chat_scoped(db, request.state.user, sid)
    return await WCH.leave(db, w, s, request.state.user)


@admin.post("/chats/{sid}/end")
async def chat_end(sid: str, request: Request):
    db = get_db()
    w, s = await _chat_scoped(db, request.state.user, sid)
    return await WCH.end(db, w, s, request.state.user)


@admin.post("/chats/{sid}/lead")
async def chat_save_lead(sid: str, body: LeadBody, request: Request):
    db = get_db()
    w, s = await _chat_scoped(db, request.state.user, sid)
    try:
        return await WCH.save_lead(db, w, s, request.state.user, body.name or "", body.phone or "")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


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


@admin.get("/{wid}/door-stats")
async def widget_door_stats(wid: str, request: Request, days: int = 7):
    db = get_db()
    return await W.door_stats(db, await _load_scoped(db, request.state.user, wid), days if days in (0, 7, 30) else 7)


@admin.post("/{wid}/ask")
async def ask_jessi(wid: str, body: AskBody, request: Request):
    """'Test Jessi' in the editor: what she would say to a visitor, with what she used."""
    db = get_db()
    w = await _load_scoped(db, request.state.user, wid)
    q = " ".join(body.question.split())[:500]
    if not q:
        raise HTTPException(status_code=400, detail="Type a question first")
    return await WCH.ask(db, w, q)


@admin.post("/{wid}/facts")
async def add_fact(wid: str, body: FactBody, request: Request, _m: dict = Depends(require_manager)):
    """Store facts are shared with SMS Jessi (My VA -> store facts); this just edits them from the widget's store."""
    db = get_db()
    w = await _load_scoped(db, request.state.user, wid)
    text = " ".join(body.text.split())
    if len(text) < 3 or not (w.get("store_id") and ObjectId.is_valid(str(w["store_id"]))):
        raise HTTPException(status_code=400, detail="Write the fact out, that is too short")
    from services.va_prompt import _fact
    fact = _fact(text, request.state.user, "store")
    await db.stores.update_one({"_id": ObjectId(w["store_id"])}, {"$push": {"va_facts": fact}})
    return {"fact": {"id": fact["id"], "text": fact["text"], "added_by_name": fact.get("added_by_name")}}


@admin.delete("/{wid}/facts/{fact_id}")
async def remove_fact(wid: str, fact_id: str, request: Request, _m: dict = Depends(require_manager)):
    db = get_db()
    w = await _load_scoped(db, request.state.user, wid)
    if w.get("store_id") and ObjectId.is_valid(str(w["store_id"])):
        await db.stores.update_one({"_id": ObjectId(w["store_id"])}, {"$pull": {"va_facts": {"id": fact_id}}})
    return {"ok": True}


# ---------------------------------------------------------------- manager: Jessi reads the website -> draft KB
@admin.post("/{wid}/crawl")
async def crawl_start(wid: str, body: CrawlBody, request: Request, bg: BackgroundTasks, _m: dict = Depends(require_manager)):
    db = get_db()
    w = await _load_scoped(db, request.state.user, wid)
    try:
        job = await WCR.start(db, w, body.url, request.state.user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if job["status"] == "running" and not job.get("pages"):
        bg.add_task(WCR.run, job["id"])
    return job


@admin.get("/{wid}/crawl")
async def crawl_status(wid: str, request: Request):
    db = get_db()
    w = await _load_scoped(db, request.state.user, wid)
    return {"job": await WCR.latest(db, w)}


@admin.post("/{wid}/crawl/apply")
async def crawl_apply(wid: str, request: Request, _m: dict = Depends(require_manager)):
    db = get_db()
    w = await _load_scoped(db, request.state.user, wid)
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Bad payload")
    return await WCR.apply(db, w, body, request.state.user)


# ---------------------------------------------------------------- manager: upload the header photo / bubble icon
@admin.post("/{wid}/upload")
async def widget_upload(wid: str, request: Request, file: UploadFile = File(...), target: str = Form("avatar"), _m: dict = Depends(require_manager)):
    """Returns app-relative /api/images/... URLs; the app makes them absolute for the dealer's site."""
    db = get_db()
    w = await _load_scoped(db, request.state.user, wid)
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(status_code=400, detail="That file is not an image")
    data = await file.read()
    if len(data) > 8 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Keep it under 8 MB")
    from utils.image_storage import upload_image
    try:
        res = await upload_image(data, prefix="widgets", entity_id=str(w["_id"]))
    except Exception as e:
        logger.warning(f"[Widget] upload failed: {e}")
        res = None
    if not res:
        raise HTTPException(status_code=502, detail="Could not store that image, try again")
    urls = {k: f"/api/images/{res[p]}" for k, p in (("original_url", "original_path"), ("thumbnail_url", "thumbnail_path"), ("avatar_url", "avatar_path")) if res.get(p)}
    return {"target": target if target in ("avatar", "icon") else "avatar", **urls, "url": urls.get("avatar_url" if target == "icon" else "thumbnail_url") or urls.get("original_url")}


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
        return {k: v for k, v in data.items() if k in ("appearance", "doors", "copy", "kb") and isinstance(v, dict)}
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
    path = request.query_params.get("path", "")[:200]
    door = request.query_params.get("door", "")
    return HTMLResponse(widget_js.demo_html(store.get("name") or w.get("name") or "Your Dealership", widget_js.render(cfg), path, door if door in ("text", "call", "chat") else ""), headers=NO_CACHE)


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
    if not w or not isinstance(body, dict) or body.get("kind") not in ("load", "open", "greeting", "door") or not W.allow(_ip(request), "event", 120):
        return {"ok": False}
    if body["kind"] == "door" and body.get("door") not in W.DOORS:
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


# ---------------------------------------------------------------- public: Chat now (Jessi)
async def _chat_session(db, key: str, sid: str):
    w = await _widget_or_404(db, key)
    s = await WCH.load(db, key, sid)
    if not s:
        raise HTTPException(status_code=404, detail="That chat has ended. Start a new one.")
    return w, s


@public.post("/{key}/chat/start")
async def chat_start(key: str, request: Request):
    db = get_db()
    w = await _widget_or_404(db, key)
    body = await request.json()
    if not W.domain_ok(w, body.get("page") or ""):
        raise HTTPException(status_code=403, detail="This widget isn't set up for this website yet.")
    if not W.normalize_config(w)["doors"]["chat"]["on"]:
        raise HTTPException(status_code=400, detail="Chat is turned off for this site.")
    try:
        return await WCH.start(db, w, body, _ip(request))
    except ValueError as e:
        raise HTTPException(status_code=429, detail=str(e))


@public.get("/{key}/chat/{sid}")
async def chat_state(key: str, sid: str):
    db = get_db()
    _, s = await _chat_session(db, key, sid)
    await WCH.touch_visitor(db, s)
    return WCH.public_state(s)


@public.get("/{key}/chat/{sid}/slots")
async def chat_slots(key: str, sid: str):
    db = get_db()
    w, _ = await _chat_session(db, key, sid)
    return WCH.slots(await W.store_of(db, w))


@public.post("/{key}/chat/{sid}/book")
async def chat_book(key: str, sid: str, request: Request):
    db = get_db()
    w, s = await _chat_session(db, key, sid)
    body = await request.json()
    if body.get("website"):
        return {**WCH.public_state(s), "reply": "Thanks!", "booked": True}
    try:
        return await WCH.book(db, w, s, body, _ip(request))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@public.post("/{key}/chat/{sid}/message")
async def chat_message(key: str, sid: str, request: Request):
    db = get_db()
    w, s = await _chat_session(db, key, sid)
    body = await request.json()
    try:
        return await WCH.reply(db, w, s, body.get("text") or "", _ip(request))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@public.post("/{key}/chat/{sid}/contact")
async def chat_contact(key: str, sid: str, request: Request):
    db = get_db()
    w, s = await _chat_session(db, key, sid)
    body = await request.json()
    if body.get("website"):
        return {**WCH.public_state(s), "reply": "Thanks!", "handoff": True}
    try:
        return await WCH.give_contact(db, w, s, body, _ip(request))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@public.post("/{key}/chat/{sid}/human")
async def chat_human(key: str, sid: str):
    db = get_db()
    w, s = await _chat_session(db, key, sid)
    return await WCH.request_human(db, w, s)


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
