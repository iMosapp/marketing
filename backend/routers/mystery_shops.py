"""Mystery Shop Clients (super admin): client stores, the people we shop, AI shop calls, the store report, proposals + Stripe invoices."""
import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel

from routers.database import get_db
from routers.scripts import require_user, _resolve
from services import mystery_shops as ms
from services import scripts as scr
from utils.text_sanitize import no_em_dash

logger = logging.getLogger(__name__)
ADMIN_ROLES = {"super_admin", "admin"}


async def require_admin(request: Request) -> dict:
    me = await _resolve(request)
    if not me:
        raise HTTPException(status_code=401, detail="Authentication required")
    if me.get("role") not in ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Mystery shop clients are managed by iMOS admins")
    return me


router = APIRouter(prefix="/shop-clients", tags=["Mystery Shop Clients"], dependencies=[Depends(require_user)])
public_router = APIRouter(prefix="/public", tags=["Mystery Shop Clients"])
stripe_router = APIRouter(tags=["Mystery Shop Clients"])


def _oid(v, what="Record") -> ObjectId:
    if not ObjectId.is_valid(str(v or "")):
        raise HTTPException(status_code=404, detail=f"{what} not found")
    return ObjectId(str(v))


def _phone(v: str) -> str:
    from routers.twilio_webhooks import normalize_phone
    p = normalize_phone(v or "")
    if not p or len(p) < 11:
        raise HTTPException(status_code=400, detail="Enter a full cell number with area code")
    return p


async def _client(db, cid: str) -> dict:
    c = await db.shop_clients.find_one({"_id": _oid(cid, "Client")})
    if not c:
        raise HTTPException(status_code=404, detail="Client not found")
    return c


class ClientBody(BaseModel):
    name: Optional[str] = None
    brand: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    timezone: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_title: Optional[str] = None
    plan: Optional[dict] = None
    hours: Optional[dict] = None
    vehicles: Optional[list] = None
    active: Optional[bool] = None
    record_calls: Optional[bool] = None
    notes: Optional[str] = None
    from_number: Optional[str] = None
    scorecards: Optional[dict] = None


class PersonBody(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    department: Optional[str] = None
    title: Optional[str] = None
    notes: Optional[str] = None
    active: Optional[bool] = None


class ShopNowBody(BaseModel):
    target_id: str
    script_id: Optional[str] = None


class PlanBody(BaseModel):
    month: Optional[str] = None


class ChallengeBody(BaseModel):
    title: str
    department: str
    purpose: Optional[str] = ""
    body: str
    success_points: Optional[list] = None
    persona: Optional[dict] = None
    runtime: Optional[str] = ""


class ProposalBody(BaseModel):
    sales_per_month: int
    service_per_month: int
    price_monthly: float
    term_months: int = 3
    notes: Optional[str] = ""
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None


class SignBody(BaseModel):
    name: str
    title: Optional[str] = ""
    email: str
    agree: bool


class SendBody(BaseModel):
    note: Optional[str] = ""
    to: Optional[str] = None


class KickoffPerson(BaseModel):
    id: Optional[str] = None
    name: str
    phone: str
    department: Optional[str] = "sales"
    title: Optional[str] = ""


class KickoffBody(BaseModel):
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_title: Optional[str] = None
    timezone: Optional[str] = None
    hours: Optional[dict] = None
    vehicles: Optional[list] = None
    people: list[KickoffPerson] = []
    remove_ids: list[str] = []


def _client_fields(body: ClientBody) -> dict:
    d = {k: v for k, v in body.dict().items() if v is not None}
    if "name" in d:
        d["name"] = d["name"].strip()[:120]
    if "plan" in d:
        p = d["plan"] or {}
        d["plan"] = {"sales_per_month": max(0, min(200, int(p.get("sales_per_month") or 0))), "service_per_month": max(0, min(200, int(p.get("service_per_month") or 0))), "price_monthly": max(0.0, float(p.get("price_monthly") or 0))}
    if "hours" in d:
        h = {**ms.DEFAULT_HOURS, **(d["hours"] or {})}
        d["hours"] = {"start": str(h.get("start") or "09:00")[:5], "end": str(h.get("end") or "18:00")[:5], "days": sorted({int(x) for x in (h.get("days") or []) if 0 <= int(x) <= 6})}
    if "vehicles" in d:
        d["vehicles"] = [str(v).strip()[:80] for v in d["vehicles"] if str(v).strip()][:30]
    if "from_number" in d and d["from_number"]:
        d["from_number"] = _phone(d["from_number"])
    if "contact_phone" in d and d["contact_phone"]:
        d["contact_phone"] = d["contact_phone"].strip()[:30]
    if "scorecards" in d:
        d["scorecards"] = {k: (str(v) if v else None) for k, v in (d["scorecards"] or {}).items() if k in ms.DEPARTMENTS}
    return d


async def _progress(db, client: dict) -> dict:
    rep = await ms.build_report(db, client)
    return {"progress": rep["by_department"], "avg_score": rep["summary"]["avg_score"], "completed": rep["summary"]["completed"], "planned": rep["summary"]["planned"], "needs_training": rep["summary"]["needs_training"],
            "people": await db.shop_targets.count_documents({"client_id": str(client["_id"]), "active": {"$ne": False}})}


# ---------------------------------------------------------------- clients
@router.get("")
async def list_clients(request: Request):
    await require_admin(request)
    db = get_db()
    rows = await db.shop_clients.find({}).sort("name", 1).to_list(200)
    return {"clients": [ms.serialize_client(c, await _progress(db, c)) for c in rows], "departments": ms.DEPARTMENTS, "from_number_default": os.environ.get("MYSTERY_SHOP_FROM_NUMBER") or os.environ.get("TWILIO_PHONE_NUMBER", "")}


@router.post("")
async def create_client(body: ClientBody, request: Request):
    me = await require_admin(request)
    d = _client_fields(body)
    if not d.get("name"):
        raise HTTPException(status_code=400, detail="Give the client a name")
    now = datetime.now(timezone.utc)
    doc = {"brand": "", "city": "", "state": "", "timezone": "America/Denver", "contact_name": "", "contact_email": "", "contact_phone": "", "contact_title": "",
           "plan": {"sales_per_month": 0, "service_per_month": 0, "price_monthly": 0.0}, "hours": dict(ms.DEFAULT_HOURS), "vehicles": [], "active": True, "record_calls": True, "notes": "",
           **d, "report_token": uuid.uuid4().hex, "billing": {}, "created_by": str(me["_id"]), "created_at": now, "updated_at": now}
    res = await get_db().shop_clients.insert_one(doc)
    return ms.serialize_client(await get_db().shop_clients.find_one({"_id": res.inserted_id}))


@router.get("/{cid}")
async def get_client(cid: str, request: Request):
    await require_admin(request)
    db = get_db()
    c = await _client(db, cid)
    cards = await db.scorecards.find({"active": {"$ne": False}}, {"name": 1, "department": 1, "store_id": 1}).sort("name", 1).to_list(200)
    await ms.ensure_kickoff_token(db, c)
    return {"client": ms.serialize_client(c, await _progress(db, c)), "people": [ms.serialize_target(t) for t in await db.shop_targets.find({"client_id": cid}).sort([("department", 1), ("name", 1)]).to_list(300)],
            "scorecard_options": [{"id": str(x["_id"]), "name": x.get("name"), "department": x.get("department")} for x in cards],
            "report_url": f"{scr._app_url()}/shop-report/{c.get('report_token')}", "kickoff_url": ms.kickoff_url(c), "kickoff": c.get("kickoff") or {}, "departments": ms.DEPARTMENTS}


@router.put("/{cid}")
async def update_client(cid: str, body: ClientBody, request: Request):
    await require_admin(request)
    db = get_db()
    await _client(db, cid)
    d = _client_fields(body)
    if "name" in d and not d["name"]:
        raise HTTPException(status_code=400, detail="Name cannot be empty")
    await db.shop_clients.update_one({"_id": ObjectId(cid)}, {"$set": {**d, "updated_at": datetime.now(timezone.utc)}})
    c = await _client(db, cid)
    return ms.serialize_client(c, await _progress(db, c))


@router.delete("/{cid}")
async def delete_client(cid: str, request: Request):
    await require_admin(request)
    db = get_db()
    await _client(db, cid)
    await db.roleplay_sessions.update_many({"kind": "mystery_shop", "client_id": cid, "status": "scheduled"}, {"$set": {"status": "canceled", "fail_reason": "Client removed", "updated_at": datetime.now(timezone.utc)}})
    await db.shop_targets.delete_many({"client_id": cid})
    await db.shop_clients.delete_one({"_id": ObjectId(cid)})
    return {"ok": True}


# ---------------------------------------------------------------- people
@router.post("/{cid}/people")
async def add_person(cid: str, body: PersonBody, request: Request):
    await require_admin(request)
    db = get_db()
    await _client(db, cid)
    if not (body.name or "").strip():
        raise HTTPException(status_code=400, detail="Name is required")
    dept = body.department if body.department in ms.DEPARTMENTS else "sales"
    phone = _phone(body.phone or "")
    if await db.shop_targets.find_one({"client_id": cid, "phone": phone}):
        raise HTTPException(status_code=409, detail="Someone with that cell number is already on this client")
    now = datetime.now(timezone.utc)
    doc = {"client_id": cid, "name": body.name.strip()[:80], "phone": phone, "department": dept, "title": (body.title or "").strip()[:60], "notes": (body.notes or "").strip()[:400], "active": True, "challenge_history": [], "created_at": now, "updated_at": now}
    res = await db.shop_targets.insert_one(doc)
    return ms.serialize_target(await db.shop_targets.find_one({"_id": res.inserted_id}))


@router.put("/people/{tid}")
async def update_person(tid: str, body: PersonBody, request: Request):
    await require_admin(request)
    db = get_db()
    t = await db.shop_targets.find_one({"_id": _oid(tid, "Person")})
    if not t:
        raise HTTPException(status_code=404, detail="Person not found")
    d = {k: v for k, v in body.dict().items() if v is not None}
    if "phone" in d:
        d["phone"] = _phone(d["phone"])
    if "department" in d and d["department"] not in ms.DEPARTMENTS:
        d.pop("department")
    if "name" in d:
        d["name"] = d["name"].strip()[:80]
        if not d["name"]:
            raise HTTPException(status_code=400, detail="Name cannot be empty")
    await db.shop_targets.update_one({"_id": t["_id"]}, {"$set": {**d, "updated_at": datetime.now(timezone.utc)}})
    if d.get("name") or d.get("phone") or d.get("department"):
        await db.roleplay_sessions.update_many({"kind": "mystery_shop", "target_id": tid, "status": "scheduled"}, {"$set": {k2: v2 for k2, v2 in (("rep_name", d.get("name")), ("rep_phone", d.get("phone")), ("department", d.get("department"))) if v2}})
    return ms.serialize_target(await db.shop_targets.find_one({"_id": t["_id"]}))


@router.delete("/people/{tid}")
async def delete_person(tid: str, request: Request):
    await require_admin(request)
    db = get_db()
    t = await db.shop_targets.find_one({"_id": _oid(tid, "Person")})
    if not t:
        raise HTTPException(status_code=404, detail="Person not found")
    await db.roleplay_sessions.update_many({"kind": "mystery_shop", "target_id": tid, "status": "scheduled"}, {"$set": {"status": "canceled", "fail_reason": "Person removed", "updated_at": datetime.now(timezone.utc)}})
    await db.shop_targets.delete_one({"_id": t["_id"]})
    return {"ok": True}


# ---------------------------------------------------------------- calls
@router.get("/{cid}/calls")
async def list_calls(cid: str, request: Request, month: Optional[str] = None):
    await require_admin(request)
    db = get_db()
    c = await _client(db, cid)
    start, end = ms.month_bounds(month, ms._tz(c))
    rows = await db.roleplay_sessions.find({"kind": "mystery_shop", "client_id": cid, "scheduled_for": {"$gte": start, "$lt": end}}).sort("scheduled_for", -1).to_list(500)
    return {"calls": [ms.serialize_call(s) for s in rows], "month": start.astimezone(ms._tz(c)).strftime("%Y-%m")}


@router.post("/{cid}/calls/shop-now")
async def shop_now(cid: str, body: ShopNowBody, request: Request):
    me = await require_admin(request)
    db = get_db()
    c = await _client(db, cid)
    t = await db.shop_targets.find_one({"_id": _oid(body.target_id, "Person"), "client_id": cid})
    if not t:
        raise HTTPException(status_code=404, detail="Person not found")
    if await db.roleplay_sessions.find_one({"kind": "mystery_shop", "target_id": body.target_id, "status": {"$in": ["dialing", "live", "grading"]}}):
        raise HTTPException(status_code=409, detail=f"{t['name']} is already on a shop call")
    script = None
    if body.script_id:
        script = await db.scripts.find_one({"_id": _oid(body.script_id, "Challenge"), "pool": "mystery_shop"})
    call = await ms.create_shop_call(db, c, t, datetime.now(timezone.utc), created_by=str(me["_id"]), manual=True, script=script)
    if not call:
        raise HTTPException(status_code=400, detail=f"No {ms.DEPT_LABEL.get(t.get('department'), '')} challenges in the pool yet")
    ok = await ms.place_shop_call(db, call)
    s = await db.roleplay_sessions.find_one({"_id": call["_id"]})
    if not ok:
        raise HTTPException(status_code=503, detail=s.get("fail_reason") or "The call could not be placed")
    return ms.serialize_call(s)


@router.post("/{cid}/plan-month")
async def plan_month(cid: str, body: PlanBody, request: Request):
    me = await require_admin(request)
    db = get_db()
    c = await _client(db, cid)
    made = await ms.plan_month(db, c, body.month, created_by=str(me["_id"]))
    return {"created": made}


@router.get("/calls/{sid}")
async def get_call(sid: str, request: Request):
    await require_admin(request)
    db = get_db()
    s = await db.roleplay_sessions.find_one({"_id": _oid(sid, "Call"), "kind": "mystery_shop"})
    if not s:
        raise HTTPException(status_code=404, detail="Call not found")
    s = await scr.reconcile_dialing(db, s)
    ev = await db.call_evaluations.find_one({"_id": ObjectId(s["evaluation_id"])}) if s.get("evaluation_id") and ObjectId.is_valid(str(s["evaluation_id"])) else None
    out = ms.serialize_call(s)
    out.update({"persona": s.get("persona"), "transcript_turns": [scr._turn_out(t) for t in s.get("turns", [])], "attempt_history": [{**h, "at": h["at"].isoformat()} for h in s.get("attempt_history", []) if h.get("at")],
                "evaluation": {"id": str(ev["_id"]), "score_pct": ev.get("score_pct"), "scorecard_name": ev.get("scorecard_name"), "critical_misses": ev.get("critical_misses") or [], "summary": ev.get("summary"),
                               "wins": ev.get("wins") or [], "coaching": ev.get("coaching") or [], "results": ev.get("results") or [], "adherence": ev.get("adherence") or {}, "customer_sentiment": ev.get("customer_sentiment")} if ev else None})
    return out


@router.delete("/calls/{sid}")
async def cancel_call(sid: str, request: Request):
    await require_admin(request)
    db = get_db()
    s = await db.roleplay_sessions.find_one({"_id": _oid(sid, "Call"), "kind": "mystery_shop"})
    if not s:
        raise HTTPException(status_code=404, detail="Call not found")
    if s.get("status") not in ("scheduled", "unreachable", "failed"):
        raise HTTPException(status_code=409, detail="Only scheduled or unreachable shops can be removed")
    await db.roleplay_sessions.update_one({"_id": s["_id"]}, {"$set": {"status": "canceled", "updated_at": datetime.now(timezone.utc)}})
    await db.shop_targets.update_one({"_id": _oid(s["target_id"], "Person")}, {"$pull": {"challenge_history": s.get("script_id")}})
    return {"ok": True}


@router.post("/calls/{sid}/retry")
async def retry_call(sid: str, request: Request):
    await require_admin(request)
    db = get_db()
    s = await db.roleplay_sessions.find_one({"_id": _oid(sid, "Call"), "kind": "mystery_shop"})
    if not s or s.get("status") not in ("unreachable", "failed", "scheduled"):
        raise HTTPException(status_code=409, detail="This shop cannot be retried")
    await db.roleplay_sessions.update_one({"_id": s["_id"]}, {"$set": {"status": "scheduled", "scheduled_for": datetime.now(timezone.utc), "attempts": 0, "manual": True, "fail_reason": None, "outcome": None, "turns": [], "updated_at": datetime.now(timezone.utc)}})
    call = await db.roleplay_sessions.find_one({"_id": s["_id"]})
    await db.roleplay_sessions.update_one({"_id": s["_id"]}, {"$set": {"status": "dialing"}})
    if not await ms.place_shop_call(db, call):
        raise HTTPException(status_code=503, detail="The call could not be placed")
    return ms.serialize_call(await db.roleplay_sessions.find_one({"_id": s["_id"]}))


# ---------------------------------------------------------------- challenges
def _challenge_out(s: dict) -> dict:
    return {**scr.serialize_script(s), "department": s.get("department"), "client_specific": bool(s.get("shop_client_id")), "shop_client_id": s.get("shop_client_id")}


@router.get("/{cid}/challenges")
async def list_challenges(cid: str, request: Request):
    await require_admin(request)
    db = get_db()
    await _client(db, cid)
    return {"challenges": [_challenge_out(s) for s in await ms.challenge_pool(db, cid)], "curveballs": ms.CURVEBALLS}


@router.post("/{cid}/challenges")
async def add_challenge(cid: str, body: ChallengeBody, request: Request):
    me = await require_admin(request)
    db = get_db()
    await _client(db, cid)
    if body.department not in ms.DEPARTMENTS:
        raise HTTPException(status_code=400, detail="Department must be sales or service")
    if not body.title.strip() or not body.body.strip():
        raise HTTPException(status_code=400, detail="Title and the challenge text are required")
    persona = body.persona or {}
    if not (persona.get("name") or "").strip() or not (persona.get("opening_line") or "").strip():
        raise HTTPException(status_code=400, detail="The shopper needs a name and an opening line")
    now = datetime.now(timezone.utc)
    doc = {"kind": "phone", "pool": "mystery_shop", "shop_client_id": cid, "store_id": None, "slug": f"shop_custom_{ObjectId()}", "department": body.department, "category": "Service" if body.department == "service" else "Sales calls",
           "direction": "inbound", "title": body.title.strip()[:120], "runtime": (body.runtime or "").strip()[:40], "purpose": no_em_dash(body.purpose or "")[:400], "body": no_em_dash(body.body)[:8000],
           "success_points": [str(p).strip()[:160] for p in (body.success_points or []) if str(p).strip()][:12],
           "persona": {"name": str(persona.get("name"))[:60], "voice": persona.get("voice") if persona.get("voice") in ("female", "male", "young", "older") else "female", "summary": no_em_dash(str(persona.get("summary") or ""))[:400],
                       "goals": no_em_dash(str(persona.get("goals") or ""))[:200], "objections": [no_em_dash(str(o))[:160] for o in (persona.get("objections") or []) if str(o).strip()][:6], "opening_line": no_em_dash(str(persona.get("opening_line")))[:240]},
           "created_by": str(me["_id"]), "created_by_name": me.get("name"), "active": True, "created_at": now, "updated_at": now}
    res = await db.scripts.insert_one(doc)
    return _challenge_out(await db.scripts.find_one({"_id": res.inserted_id}))


@router.delete("/challenges/{script_id}")
async def delete_challenge(script_id: str, request: Request):
    await require_admin(request)
    db = get_db()
    s = await db.scripts.find_one({"_id": _oid(script_id, "Challenge"), "pool": "mystery_shop"})
    if not s:
        raise HTTPException(status_code=404, detail="Challenge not found")
    if not s.get("shop_client_id"):
        await db.scripts.update_one({"_id": s["_id"]}, {"$set": {"active": False, "updated_at": datetime.now(timezone.utc)}})
    else:
        await db.scripts.delete_one({"_id": s["_id"]})
    return {"ok": True}


# ---------------------------------------------------------------- report
@router.get("/{cid}/report")
async def client_report(cid: str, request: Request, month: Optional[str] = None):
    await require_admin(request)
    db = get_db()
    c = await _client(db, cid)
    rep = await ms.build_report(db, c, month)
    rep["report_url"] = f"{scr._app_url()}/shop-report/{c.get('report_token')}"
    return rep


@router.post("/{cid}/report/rotate-link")
async def rotate_report_link(cid: str, request: Request):
    await require_admin(request)
    db = get_db()
    await _client(db, cid)
    tok = uuid.uuid4().hex
    await db.shop_clients.update_one({"_id": ObjectId(cid)}, {"$set": {"report_token": tok}})
    return {"report_token": tok, "report_url": f"{scr._app_url()}/shop-report/{tok}"}


@public_router.get("/shop-report/{token}.pdf")
async def public_report_pdf(token: str, month: Optional[str] = None):
    db = get_db()
    c = await db.shop_clients.find_one({"report_token": token})
    if not c or len(token) < 16:
        raise HTTPException(status_code=404, detail="Report not found")
    rep = await ms.build_report(db, c, month)
    data = await asyncio.to_thread(ms.report_pdf, rep)
    fname = "".join(ch if ch.isalnum() or ch in " -_" else "" for ch in f"{c.get('name')} mystery shop {rep['month']}").strip().replace(" ", "_")
    return Response(content=data, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{fname}.pdf"'})


@public_router.get("/shop-report/{token}")
async def public_report(token: str, month: Optional[str] = None):
    db = get_db()
    c = await db.shop_clients.find_one({"report_token": token})
    if not c or len(token) < 16:
        raise HTTPException(status_code=404, detail="Report not found")
    rep = await ms.build_report(db, c, month)
    for call in rep["calls"]:
        call.pop("target_id", None)
    return rep


# ---------------------------------------------------------------- proposals + billing
@router.get("/{cid}/proposals")
async def list_proposals(cid: str, request: Request):
    await require_admin(request)
    db = get_db()
    await _client(db, cid)
    rows = await db.shop_proposals.find({"client_id": cid}).sort("created_at", -1).to_list(50)
    out = []
    for p in rows:
        if (p.get("invoice") or {}).get("stripe_invoice_id") and (p.get("invoice") or {}).get("status") != "paid":
            p["invoice"] = await ms.refresh_invoice(db, p)
            if p["invoice"].get("status") == "paid":
                p["status"] = "paid"
        out.append({**ms.serialize_proposal(p), "url": f"{scr._app_url()}/proposal/{p.get('token')}"})
    return {"proposals": out}


@router.post("/{cid}/proposals")
async def create_proposal(cid: str, body: ProposalBody, request: Request):
    me = await require_admin(request)
    db = get_db()
    c = await _client(db, cid)
    if body.price_monthly <= 0:
        raise HTTPException(status_code=400, detail="Set a monthly price")
    now = datetime.now(timezone.utc)
    doc = {"client_id": cid, "client_name": c.get("name"), "contact_name": (body.contact_name or c.get("contact_name") or "").strip(), "contact_email": (body.contact_email or c.get("contact_email") or "").strip().lower(),
           "terms": {"sales_per_month": max(0, body.sales_per_month), "service_per_month": max(0, body.service_per_month), "price_monthly": round(float(body.price_monthly), 2), "term_months": max(1, min(24, body.term_months)), "notes": no_em_dash(body.notes or "")[:1500]},
           "status": "draft", "token": uuid.uuid4().hex, "sender_id": str(me["_id"]), "sender_name": me.get("name") or "I'm On Social", "created_at": now, "updated_at": now}
    res = await db.shop_proposals.insert_one(doc)
    await db.shop_clients.update_one({"_id": c["_id"]}, {"$set": {"plan": {"sales_per_month": doc["terms"]["sales_per_month"], "service_per_month": doc["terms"]["service_per_month"], "price_monthly": doc["terms"]["price_monthly"]}}})
    p = await db.shop_proposals.find_one({"_id": res.inserted_id})
    return {**ms.serialize_proposal(p), "url": f"{scr._app_url()}/proposal/{p['token']}"}


@router.post("/proposals/{pid}/send")
async def send_proposal(pid: str, request: Request, body: Optional[SendBody] = None):
    me = await require_admin(request)
    db = get_db()
    p = await db.shop_proposals.find_one({"_id": _oid(pid, "Proposal")})
    if not p:
        raise HTTPException(status_code=404, detail="Proposal not found")
    body = body or SendBody()
    to = (body.to or "").strip().lower()
    if to and ("@" not in to or "." not in to.split("@")[-1]):
        raise HTTPException(status_code=400, detail="That email address does not look right")
    if to and to != p.get("contact_email"):
        await db.shop_proposals.update_one({"_id": p["_id"]}, {"$set": {"contact_email": to}})
        await db.shop_clients.update_one({"_id": ObjectId(p["client_id"]), "contact_email": {"$in": ["", None, p.get("contact_email")]}}, {"$set": {"contact_email": to}})
        p["contact_email"] = to
    if not p.get("contact_email"):
        raise HTTPException(status_code=400, detail="Add the client's contact email first")
    note = no_em_dash(body.note or "").strip()[:1500]
    url = f"{scr._app_url()}/proposal/{p['token']}"
    subject, html = ms.proposal_email(p, me.get("name") or "Forest", note, url, "cid:imos-logo")
    key = os.environ.get("RESEND_API_KEY")
    if not key:
        raise HTTPException(status_code=503, detail="Email is not configured, copy the link instead")
    import resend
    resend.api_key = key
    sender = os.environ.get("SENDER_EMAIL", "notifications@send.imonsocial.com")
    payload = {"from": f"I'm On Social <{sender}>", "to": [p["contact_email"]], "reply_to": me.get("email") or "support@imonsocial.com", "subject": subject, "html": html}
    logo = ms.logo_b64()
    if logo:
        payload["attachments"] = [{"filename": "imos-logo.png", "content": logo, "content_id": "imos-logo"}]
    try:
        await asyncio.to_thread(resend.Emails.send, payload)
    except Exception as e:
        logger.warning(f"[MysteryShop] proposal email failed: {e}")
        raise HTTPException(status_code=503, detail="The email did not go out, copy the link instead")
    now = datetime.now(timezone.utc)
    await db.shop_proposals.update_one({"_id": p["_id"]}, {"$set": {"status": "sent" if p.get("status") in ("draft", "sent") else p.get("status"), "sent_at": now, "sent_note": note, "updated_at": now}})
    await db.users.update_one({"_id": me["_id"]}, {"$set": {"shop_proposal_note": note}})
    return {"ok": True, "url": url, "to": p["contact_email"]}


@router.get("/proposals/{pid}/email-preview")
async def proposal_email_preview(pid: str, request: Request, note: Optional[str] = None):
    """Exactly what the GM receives: same template as /send, logo inlined so the app can render it."""
    me = await require_admin(request)
    db = get_db()
    p = await db.shop_proposals.find_one({"_id": _oid(pid, "Proposal")})
    if not p:
        raise HTTPException(status_code=404, detail="Proposal not found")
    default_note = p.get("sent_note") if p.get("sent_note") is not None else (me.get("shop_proposal_note") or "")
    note_txt = default_note if note is None else note
    logo = ms.logo_b64()
    subject, html = ms.proposal_email(p, me.get("name") or "Forest", note_txt, f"{scr._app_url()}/proposal/{p['token']}", f"data:image/png;base64,{logo}" if logo else "")
    sender = os.environ.get("SENDER_EMAIL", "notifications@send.imonsocial.com")
    return {"subject": subject, "html": html, "to": p.get("contact_email") or "", "from": f"I'm On Social <{sender}>", "reply_to": me.get("email") or "support@imonsocial.com", "default_note": default_note}


@router.delete("/proposals/{pid}")
async def delete_proposal(pid: str, request: Request):
    await require_admin(request)
    db = get_db()
    p = await db.shop_proposals.find_one({"_id": _oid(pid, "Proposal")})
    if not p:
        raise HTTPException(status_code=404, detail="Proposal not found")
    if p.get("status") in ("signed", "paid"):
        raise HTTPException(status_code=409, detail="Signed proposals are kept for your records")
    await db.shop_proposals.delete_one({"_id": p["_id"]})
    return {"ok": True}


@public_router.get("/proposal/{token}")
async def public_proposal(token: str):
    db = get_db()
    p = await db.shop_proposals.find_one({"token": token})
    if not p or len(token) < 16:
        raise HTTPException(status_code=404, detail="Proposal not found")
    if p.get("status") in ("draft", "sent"):
        await db.shop_proposals.update_one({"_id": p["_id"]}, {"$set": {"status": "viewed", "viewed_at": datetime.now(timezone.utc)}})
        p["status"] = "viewed"
    if (p.get("invoice") or {}).get("stripe_invoice_id") and (p.get("invoice") or {}).get("status") != "paid":
        p["invoice"] = await ms.refresh_invoice(db, p)
    out = ms.serialize_proposal(p)
    out["sections"] = [{"title": a, "body": b} for a, b in ms.proposal_text(p)]
    out["invoice"] = {"hosted_invoice_url": (p.get("invoice") or {}).get("hosted_invoice_url"), "status": (p.get("invoice") or {}).get("status"), "amount": (p.get("invoice") or {}).get("amount")}
    out["kickoff_url"] = await _kickoff_for(db, p) if p.get("status") in ("signed", "paid") else None
    return out


async def _kickoff_for(db, p: dict) -> Optional[str]:
    c = await db.shop_clients.find_one({"_id": ObjectId(p["client_id"])}) if ObjectId.is_valid(str(p.get("client_id"))) else None
    if not c:
        return None
    await ms.ensure_kickoff_token(db, c)
    return ms.kickoff_url(c)


@public_router.post("/proposal/{token}/sign")
async def sign_proposal(token: str, body: SignBody, request: Request):
    db = get_db()
    p = await db.shop_proposals.find_one({"token": token})
    if not p or len(token) < 16:
        raise HTTPException(status_code=404, detail="Proposal not found")
    if p.get("status") in ("signed", "paid"):
        raise HTTPException(status_code=409, detail="This proposal is already signed")
    if not body.agree or len(body.name.strip()) < 3 or "@" not in body.email:
        raise HTTPException(status_code=400, detail="Type your full name, a valid email and tick the agreement box")
    now = datetime.now(timezone.utc)
    signer = {"name": body.name.strip()[:120], "title": (body.title or "").strip()[:80], "email": body.email.strip().lower()[:160], "signature_type": "typed",
              "ip": (request.headers.get("x-forwarded-for") or (request.client.host if request.client else "") or "").split(",")[0].strip(), "user_agent": request.headers.get("user-agent", "")[:300], "signed_at": now}
    await db.shop_proposals.update_one({"_id": p["_id"]}, {"$set": {"status": "signed", "signer": signer, "signed_at": now, "updated_at": now}})
    await db.shop_clients.update_one({"_id": ObjectId(p["client_id"])}, {"$set": {"billing.status": "signed", "billing.signed_at": now, "billing.proposal_id": str(p["_id"]), **({"contact_email": signer["email"]} if not (await db.shop_clients.find_one({"_id": ObjectId(p["client_id"])}) or {}).get("contact_email") else {})}})
    p = await db.shop_proposals.find_one({"_id": p["_id"]})
    invoice = {}
    try:
        invoice = await ms.create_invoice_for(db, p)
    except Exception as e:
        logger.warning(f"[MysteryShop] invoice creation failed for proposal {p['_id']}: {e}")
        await db.shop_proposals.update_one({"_id": p["_id"]}, {"$set": {"invoice": {"error": str(e)[:200]}}})
    return {"ok": True, "signed_at": now.isoformat(), "invoice": {"hosted_invoice_url": invoice.get("hosted_invoice_url"), "status": invoice.get("status"), "amount": invoice.get("amount")}, "kickoff_url": await _kickoff_for(db, p)}


# ---------------------------------------------------------------- store kickoff (the GM fills in people, hours, vehicles on a public form)
@router.post("/{cid}/kickoff/rotate-link")
async def rotate_kickoff_link(cid: str, request: Request):
    await require_admin(request)
    db = get_db()
    c = await _client(db, cid)
    tok = uuid.uuid4().hex
    await db.shop_clients.update_one({"_id": c["_id"]}, {"$set": {"kickoff_token": tok}})
    c["kickoff_token"] = tok
    return {"kickoff_token": tok, "kickoff_url": ms.kickoff_url(c)}


async def _kickoff_client(db, token: str) -> dict:
    c = await db.shop_clients.find_one({"kickoff_token": token}) if len(token or "") >= 16 else None
    if not c:
        raise HTTPException(status_code=404, detail="Setup link not found")
    return c


def _kickoff_out(c: dict, people: list) -> dict:
    return {"client": {"id": str(c["_id"]), "name": c.get("name"), "brand": c.get("brand", ""), "city": c.get("city", ""), "state": c.get("state", ""), "contact_name": c.get("contact_name", ""), "contact_email": c.get("contact_email", ""),
                       "contact_phone": c.get("contact_phone", ""), "contact_title": c.get("contact_title", ""), "timezone": c.get("timezone") or "America/Denver", "hours": ms._hours(c), "vehicles": c.get("vehicles") or [],
                       "plan": (c.get("plan") or {}), "kickoff": {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in (c.get("kickoff") or {}).items()}},
            "people": [{"id": str(t["_id"]), "name": t.get("name", ""), "phone": t.get("phone", ""), "department": t.get("department", "sales"), "title": t.get("title", "")} for t in people],
            "departments": ms.DEPARTMENTS, "timezones": [{"id": a, "label": b} for a, b in ms.TIMEZONES], "sender_name": (c.get("kickoff") or {}).get("sender_name") or "Forest"}


@public_router.get("/shop-kickoff/{token}")
async def public_kickoff(token: str):
    db = get_db()
    c = await _kickoff_client(db, token)
    people = await db.shop_targets.find({"client_id": str(c["_id"]), "active": {"$ne": False}}).sort([("department", 1), ("name", 1)]).to_list(300)
    return _kickoff_out(c, people)


@public_router.post("/shop-kickoff/{token}")
async def submit_kickoff(token: str, body: KickoffBody, request: Request):
    db = get_db()
    c = await _kickoff_client(db, token)
    cid = str(c["_id"])
    upd = {}
    for k in ("contact_name", "contact_email", "contact_phone", "contact_title"):
        v = getattr(body, k)
        if v is not None:
            upd[k] = v.strip()[:160] if k == "contact_email" else v.strip()[:120]
    if upd.get("contact_email"):
        upd["contact_email"] = upd["contact_email"].lower()
        if "@" not in upd["contact_email"]:
            raise HTTPException(status_code=400, detail="That contact email does not look right")
    if body.timezone:
        if body.timezone not in {a for a, _ in ms.TIMEZONES}:
            raise HTTPException(status_code=400, detail="Pick a time zone from the list")
        upd["timezone"] = body.timezone
    if body.hours is not None:
        h = {**ms.DEFAULT_HOURS, **(body.hours or {})}
        days = sorted({int(x) for x in (h.get("days") or []) if 0 <= int(x) <= 6})
        if not days:
            raise HTTPException(status_code=400, detail="Pick at least one day we may call")
        s, e = ms._hm(str(h.get("start")), "09:00"), ms._hm(str(h.get("end")), "18:00")
        if (e[0], e[1]) <= (s[0], s[1]):
            raise HTTPException(status_code=400, detail="Closing time has to be after opening time")
        upd["hours"] = {"start": f"{s[0]:02d}:{s[1]:02d}", "end": f"{e[0]:02d}:{e[1]:02d}", "days": days}
    if body.vehicles is not None:
        upd["vehicles"] = [str(v).strip()[:80] for v in body.vehicles if str(v).strip()][:30]
    existing = {str(t["_id"]): t for t in await db.shop_targets.find({"client_id": cid}).to_list(300)}
    seen_phones, added, now = set(), 0, datetime.now(timezone.utc)
    for person in body.people:
        name = (person.name or "").strip()[:80]
        if not name:
            raise HTTPException(status_code=400, detail="Every person needs a name")
        try:
            phone = _phone(person.phone or "")
        except HTTPException:
            raise HTTPException(status_code=400, detail=f"Enter a full cell number with area code for {name}")
        if phone in seen_phones:
            raise HTTPException(status_code=400, detail=f"{name} has the same cell number as someone else on the list")
        seen_phones.add(phone)
        dept = person.department if person.department in ms.DEPARTMENTS else "sales"
        title = (person.title or "").strip()[:60]
        cur = existing.get(person.id or "")
        dup = await db.shop_targets.find_one({"client_id": cid, "phone": phone, **({"_id": {"$ne": cur["_id"]}} if cur else {})})
        if dup and str(dup["_id"]) in body.remove_ids:
            dup = None
        if dup:
            raise HTTPException(status_code=400, detail=f"{name}'s cell number is already on the list as {dup.get('name')}")
        if cur:
            await db.shop_targets.update_one({"_id": cur["_id"]}, {"$set": {"name": name, "phone": phone, "department": dept, "title": title, "active": True, "updated_at": now}})
            if (cur.get("name"), cur.get("phone"), cur.get("department")) != (name, phone, dept):
                await db.roleplay_sessions.update_many({"kind": "mystery_shop", "target_id": str(cur["_id"]), "status": "scheduled"}, {"$set": {"rep_name": name, "rep_phone": phone, "department": dept}})
        else:
            await db.shop_targets.insert_one({"client_id": cid, "name": name, "phone": phone, "department": dept, "title": title, "notes": "Added by the store on the kickoff form", "active": True, "challenge_history": [], "created_at": now, "updated_at": now})
            added += 1
    for rid in body.remove_ids:
        if rid in existing:
            await db.roleplay_sessions.update_many({"kind": "mystery_shop", "target_id": rid, "status": "scheduled"}, {"$set": {"status": "canceled", "fail_reason": "Removed by the store", "updated_at": now}})
            await db.shop_targets.delete_one({"_id": existing[rid]["_id"]})
    kick = {**(c.get("kickoff") or {}), "submitted_at": now, "submissions": int((c.get("kickoff") or {}).get("submissions") or 0) + 1,
            "ip": (request.headers.get("x-forwarded-for") or (request.client.host if request.client else "") or "").split(",")[0].strip()}
    await db.shop_clients.update_one({"_id": c["_id"]}, {"$set": {**upd, "kickoff": kick, "updated_at": now}})
    c = await db.shop_clients.find_one({"_id": c["_id"]})
    people = await db.shop_targets.find({"client_id": cid, "active": {"$ne": False}}).sort([("department", 1), ("name", 1)]).to_list(300)
    try:
        await ms.notify_kickoff(db, c, added, len(people))
    except Exception as e:
        logger.warning(f"[MysteryShop] kickoff notify failed: {e}")
    return {"ok": True, **_kickoff_out(c, people), "added": added}


@stripe_router.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    """Claimable-sandbox webhook (Flow A path). Only invoice events matter here; everything else is acknowledged."""
    import stripe
    payload = await request.body()
    secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
    try:
        event = stripe.Webhook.construct_event(payload, request.headers.get("stripe-signature", ""), secret) if secret else stripe.Event.construct_from(__import__("json").loads(payload), stripe.api_key)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid signature")
    obj, kind = event["data"]["object"], event["type"]
    if kind in ("invoice.paid", "invoice.payment_succeeded"):
        await ms.mark_invoice_paid(get_db(), obj["id"])
    return {"status": "ok"}
