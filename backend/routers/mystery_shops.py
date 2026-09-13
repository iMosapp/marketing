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
from services import industries as ind
from services import mystery_shops as ms
from services import scorecards as sc
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
    industry: Optional[str] = None
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
    offerings: Optional[list] = None
    active: Optional[bool] = None
    record_calls: Optional[bool] = None
    notes: Optional[str] = None
    from_number: Optional[str] = None
    scorecards: Optional[dict] = None
    text_scorecards: Optional[bool] = None


class DemoBody(BaseModel):
    name: str
    phone: str
    department: Optional[str] = "sales"
    industry: Optional[str] = None
    title: Optional[str] = ""
    store_name: Optional[str] = ""
    vehicle: Optional[str] = ""
    script_id: Optional[str] = None
    text_scorecard: bool = True


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
    industry: Optional[str] = None
    direction: Optional[str] = None
    purpose: Optional[str] = ""
    body: str
    success_points: Optional[list] = None
    persona: Optional[dict] = None
    runtime: Optional[str] = ""
    curveballs: Optional[list] = None
    generated_from: Optional[str] = None


class GenerateBody(BaseModel):
    department: str
    scenario: str
    count: Optional[int] = 1
    client_id: Optional[str] = None


class ProposalBody(BaseModel):
    sales_per_month: Optional[int] = 0
    service_per_month: Optional[int] = 0
    per_month: Optional[dict] = None
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
    offerings: Optional[list] = None
    people: list[KickoffPerson] = []
    remove_ids: list[str] = []


def _client_fields(body: ClientBody) -> dict:
    d = {k: v for k, v in body.dict().items() if v is not None}
    if "name" in d:
        d["name"] = d["name"].strip()[:120]
    if "industry" in d:
        if d["industry"] not in ind.INDUSTRIES:
            raise HTTPException(status_code=400, detail="Pick an industry from the list")
    if "plan" in d:
        p = d["plan"] or {}
        per = p.get("per_month") if isinstance(p.get("per_month"), dict) else {k: p.get(f"{k}_per_month") for k in ("sales", "service") if p.get(f"{k}_per_month") is not None}
        d["plan"] = {"per_month": {k: max(0, min(200, int(v or 0))) for k, v in per.items() if k in ind.all_dept_keys()}, "price_monthly": max(0.0, float(p.get("price_monthly") or 0))}
    if "hours" in d:
        h = {**ms.DEFAULT_HOURS, **(d["hours"] or {})}
        d["hours"] = {"start": str(h.get("start") or "09:00")[:5], "end": str(h.get("end") or "18:00")[:5], "days": sorted({int(x) for x in (h.get("days") or []) if 0 <= int(x) <= 6})}
    if "offerings" in d and "vehicles" not in d:
        d["vehicles"] = d.pop("offerings")
    d.pop("offerings", None)
    if "vehicles" in d:
        d["vehicles"] = [str(v).strip()[:80] for v in d["vehicles"] if str(v).strip()][:30]
    if "from_number" in d and d["from_number"]:
        d["from_number"] = _phone(d["from_number"])
    if "contact_phone" in d and d["contact_phone"]:
        d["contact_phone"] = d["contact_phone"].strip()[:30]
    if "scorecards" in d:
        d["scorecards"] = {k: (str(v) if v else None) for k, v in (d["scorecards"] or {}).items() if k in ind.all_dept_keys()}
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
    await ms.rename_legacy_quick_bucket(db)
    rows = await db.shop_clients.find({}).sort("name", 1).to_list(200)
    return {"clients": [ms.serialize_client(c, await _progress(db, c)) for c in rows], "departments": ms.DEPARTMENTS, "industries": ind.for_api(), "from_number_default": await ms.default_from_number(db)}


@router.get("/industries")
async def list_industries(request: Request):
    """Every industry pack: nouns, departments, what the caller can mention. The app renders pickers from this, never from constants."""
    await require_admin(request)
    db = get_db()
    counts = {}
    async for row in db.scripts.aggregate([{"$match": {"pool": "mystery_shop", "shop_client_id": None, "active": {"$ne": False}}}, {"$group": {"_id": "$department", "n": {"$sum": 1}}}]):
        counts[row["_id"]] = row["n"]
    out = ind.for_api()
    for i in out:
        for d in i["departments"]:
            d["challenges"] = counts.get(d["key"], 0)
    return {"industries": out, "default": ind.DEFAULT_INDUSTRY}


# ---------------------------------------------------------------- the Mystery Shop caller number
class NumberBody(BaseModel):
    phone_number: str


def _e164(v: str) -> str:
    from routers.twilio_webhooks import normalize_phone
    p = normalize_phone(v or "")
    if not p or len(p) < 11:
        raise HTTPException(status_code=400, detail="That is not a full phone number")
    return p


async def _number_use(db, phone: str) -> str:
    """Plain-English label for what a Twilio number on the account is already doing."""
    variants = [phone, phone.replace("+", ""), phone[-10:]]
    u = await db.users.find_one({"$or": [{"twilio_number": {"$in": variants}}, {"mvpline_number": {"$in": variants}}]}, {"name": 1, "first_name": 1})
    if u:
        return f"{(u.get('name') or u.get('first_name') or 'A rep').split(' ')[0]}'s rep line"
    ib = await db.inboxes.find_one({"phone_number": {"$in": variants}, "is_active": {"$ne": False}}, {"name": 1})
    if ib:
        return f"Team inbox: {ib.get('name') or 'shared'}"
    c = await db.shop_clients.find_one({"from_number": phone}, {"name": 1})
    if c:
        return f"Shop calls for {c.get('name')}"
    if phone == (os.environ.get("TWILIO_PHONE_NUMBER") or ""):
        return "Platform number (codes, alerts)"
    return "Not in use"


async def _number_state(db) -> dict:
    from routers.twilio_admin import _get_twilio_client, _twilio_call
    saved = await ms.saved_shop_number(db)
    current = await ms.default_from_number(db)
    owned, error = [], None
    try:
        numbers = await _twilio_call(_get_twilio_client().incoming_phone_numbers.list)
        for tn in numbers:
            owned.append({"phone": tn.phone_number, "sid": tn.sid, "friendly_name": tn.friendly_name or "", "voice": bool((tn.capabilities or {}).get("voice", True)),
                          "use": "Main Mystery Shop number" if saved and saved.get("value") == tn.phone_number else await _number_use(db, tn.phone_number)})
    except HTTPException as he:
        error = he.detail
    except Exception as e:
        error = f"Could not reach Twilio ({type(e).__name__})"
    owned.sort(key=lambda n: (n["use"] != "Main Mystery Shop number", n["use"] != "Not in use", n["phone"]))
    return {"current": current, "source": "saved" if saved else ("platform" if current else "none"), "saved_at": (saved or {}).get("updated_at"), "owned": owned, "twilio_error": error,
            "clients_with_own_number": [{"id": str(c["_id"]), "name": c.get("name"), "from_number": c.get("from_number")} for c in await db.shop_clients.find({"from_number": {"$nin": ["", None]}}, {"name": 1, "from_number": 1}).to_list(100)]}


@router.get("/number")
async def shop_number(request: Request):
    """Which number every shop call and scorecard text comes from, plus every number on the Twilio account to pick from."""
    await require_admin(request)
    return await _number_state(get_db())


async def _save_shop_number(db, me: dict, phone: str, sid: Optional[str], friendly: Optional[str]):
    from routers.twilio_admin import _get_twilio_client, _twilio_call
    now = datetime.now(timezone.utc)
    await db.settings.update_one({"key": ms.SHOP_NUMBER_KEY}, {"$set": {"value": phone, "sid": sid, "friendly_name": friendly, "updated_at": now, "updated_by": str(me["_id"])}}, upsert=True)
    if sid:
        try:
            await _twilio_call(_get_twilio_client().incoming_phone_numbers(sid).update, friendly_name="Mystery Shops")
        except Exception as e:
            logger.debug(f"[MysteryShop] friendly name update skipped: {e}")


@router.put("/number")
async def set_shop_number(body: NumberBody, request: Request):
    """Pick one of the numbers already on the account as the main Mystery Shop number."""
    from routers.twilio_admin import _get_twilio_client, _twilio_call
    me = await require_admin(request)
    db = get_db()
    phone = _e164(body.phone_number)
    owned = await _twilio_call(_get_twilio_client().incoming_phone_numbers.list)
    tn = next((n for n in owned if n.phone_number == phone), None)
    if not tn:
        raise HTTPException(status_code=400, detail="That number is not on your Twilio account. Pick one from the list or buy a new one.")
    if not (tn.capabilities or {}).get("voice", True):
        raise HTTPException(status_code=400, detail="That number cannot place voice calls")
    await _save_shop_number(db, me, phone, tn.sid, tn.friendly_name)
    return await _number_state(db)


@router.delete("/number")
async def clear_shop_number(request: Request):
    """Back to the platform number."""
    await require_admin(request)
    db = get_db()
    await db.settings.delete_one({"key": ms.SHOP_NUMBER_KEY})
    return await _number_state(db)


@router.get("/number/search")
async def search_shop_numbers(request: Request, area_code: Optional[str] = None, contains: Optional[str] = None):
    """Voice + SMS capable US numbers available to buy, by area code or digits."""
    from routers.twilio_admin import _get_twilio_client, _twilio_call, NUMBER_MONTHLY_COST
    await require_admin(request)
    ac = "".join(ch for ch in (area_code or "") if ch.isdigit())
    digits = "".join(ch for ch in (contains or "") if ch.isdigit() or ch == "*")
    if ac and len(ac) != 3:
        raise HTTPException(status_code=400, detail="Area code is 3 digits")
    if not ac and not digits:
        raise HTTPException(status_code=400, detail="Give me an area code or a few digits to look for")
    params = {"limit": 12, "voice_enabled": True, "sms_enabled": True}
    if ac:
        params["area_code"] = ac
    if digits:
        params["contains"] = digits
    try:
        found = await _twilio_call(lambda: _get_twilio_client().available_phone_numbers("US").local.list(**params))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Twilio search failed ({type(e).__name__})")
    return {"numbers": [{"phone": n.phone_number, "locality": n.locality or "", "region": n.region or "", "monthly_cost_usd": NUMBER_MONTHLY_COST} for n in found], "monthly_cost_usd": NUMBER_MONTHLY_COST}


@router.post("/number/buy")
async def buy_shop_number(body: NumberBody, request: Request):
    """Buy a number from Twilio, point its webhooks at us, and make it the main Mystery Shop number."""
    from routers.twilio_admin import _get_twilio_client, _twilio_call, NUMBER_MONTHLY_COST
    me = await require_admin(request)
    db = get_db()
    phone = _e164(body.phone_number)
    base = scr._app_url()
    try:
        bought = await _twilio_call(_get_twilio_client().incoming_phone_numbers.create, phone_number=phone, friendly_name="Mystery Shops",
                                    voice_url=f"{base}/api/webhooks/twilio/voice", voice_method="POST", sms_url=f"{base}/api/webhooks/twilio/incoming", sms_method="POST", timeout=30)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Twilio would not sell that number: {str(e)[:160]}")
    ms_sid = os.environ.get("TWILIO_MESSAGING_SERVICE_SID")
    if ms_sid:
        try:
            await _twilio_call(_get_twilio_client().messaging.v1.services(ms_sid).phone_numbers.create, phone_number_sid=bought.sid)
        except Exception as e:
            logger.warning(f"[MysteryShop] could not add {phone} to the messaging service: {e}")
    await db.phone_number_pool.insert_one({"phone_number": bought.phone_number, "twilio_sid": bought.sid, "status": "mystery_shop", "assigned_user_id": None, "purpose": "mystery_shop", "monthly_cost_usd": NUMBER_MONTHLY_COST,
                                           "purchased_at": datetime.now(timezone.utc), "purchased_by": str(me["_id"])})
    await _save_shop_number(db, me, bought.phone_number, bought.sid, "Mystery Shops")
    logger.info(f"[MysteryShop] bought {bought.phone_number} ({bought.sid}) as the main shop number")
    return await _number_state(db)


@router.post("/demo")
async def demo_shop(body: DemoBody, request: Request):
    """Shop anyone right now: no client, no proposal. Lands in the built-in Quick shops bucket."""
    me = await require_admin(request)
    db = get_db()
    name = (body.name or "").strip()[:80]
    if len(name) < 2:
        raise HTTPException(status_code=400, detail="Who are we calling? Add their name")
    phone = _phone(body.phone or "")
    industry = body.industry if body.industry in ind.INDUSTRIES else ind.industry_of_dept(body.department)
    dept = body.department if body.department in ind.dept_keys(industry) else ind.dept_keys(industry)[0]
    if await db.roleplay_sessions.find_one({"kind": "mystery_shop", "rep_phone": phone, "status": {"$in": ["dialing", "live", "grading"]}}):
        raise HTTPException(status_code=409, detail=f"{name} is already on a shop call")
    script = None
    if body.script_id:
        script = await db.scripts.find_one({"_id": _oid(body.script_id, "Challenge"), "pool": "mystery_shop", "active": {"$ne": False}})
        if not script:
            raise HTTPException(status_code=404, detail="That challenge is gone, pick another")
    r = await ms.demo_shop(db, me, name, phone, dept, (body.title or "").strip()[:60], (body.store_name or "").strip()[:80], (body.vehicle or "").strip()[:80], script, body.text_scorecard, industry)
    if r.get("error"):
        raise HTTPException(status_code=400, detail=r["error"])
    if not r.get("ok"):
        raise HTTPException(status_code=503, detail=(r.get("call") or {}).get("fail_reason") or "The call could not be placed")
    return {"call": ms.serialize_call(r["call"]), "client_id": r["client_id"]}


@router.get("/demo/challenges")
async def demo_challenges(request: Request, department: Optional[str] = None, industry: Optional[str] = None):
    await require_admin(request)
    return {"challenges": [_challenge_out(s) for s in await ms.challenge_pool(get_db(), None, department, industry)]}


@router.get("/challenges")
async def library(request: Request, department: Optional[str] = None, industry: Optional[str] = None):
    """The global challenge library (every client's caller draws from it), filterable by industry."""
    await require_admin(request)
    rows = await ms.challenge_pool(get_db(), None, department, industry)
    return {"challenges": [_challenge_out(s) for s in rows], "departments": ind.dept_options(industry or ind.DEFAULT_INDUSTRY), "industries": ind.for_api()}


class SeedBody(BaseModel):
    industry: str
    department: Optional[str] = None


@router.post("/challenges/seed")
async def seed_starters(body: SeedBody, request: Request):
    """Jessi writes the starter challenges for an industry (2 per department that has fewer than 2) into the global library."""
    me = await require_admin(request)
    if body.industry not in ind.INDUSTRIES:
        raise HTTPException(status_code=400, detail="Pick an industry from the list")
    try:
        made = await ms.seed_starters(get_db(), me, body.industry, body.department)
    except Exception as e:
        logger.warning(f"[MysteryShop] seed failed: {e}")
        raise HTTPException(status_code=503, detail="Jessi is busy right now, try again in a moment")
    return {"created": [_challenge_out(s) for s in made]}


@router.post("")
async def create_client(body: ClientBody, request: Request):
    me = await require_admin(request)
    d = _client_fields(body)
    if not d.get("name"):
        raise HTTPException(status_code=400, detail="Give the client a name")
    now = datetime.now(timezone.utc)
    doc = {"brand": "", "city": "", "state": "", "timezone": "America/Denver", "contact_name": "", "contact_email": "", "contact_phone": "", "contact_title": "",
           "plan": {"per_month": {}, "price_monthly": 0.0}, "hours": dict(ms.DEFAULT_HOURS), "vehicles": [], "active": True, "record_calls": True, "notes": "", "industry": ind.DEFAULT_INDUSTRY,
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
            "report_url": f"{scr._app_url()}/shop-report/{c.get('report_token')}", "kickoff_url": ms.kickoff_url(c), "kickoff": c.get("kickoff") or {}, "departments": ind.dept_options(ind.key_of(c))}


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
    c = await _client(db, cid)
    keys = ind.dept_keys(ind.key_of(c))
    dept = body.department if body.department in keys else keys[0]
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
    if "department" in d and d["department"] not in ind.all_dept_keys():
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
        raise HTTPException(status_code=400, detail=f"No {ind.dept_label(t.get('department'))} challenges in the pool yet. Open the Challenge Library and let Jessi write the starters.")
    ok = await ms.dial_now(db, call)
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
                "evaluation": {"id": str(ev["_id"]), "score_pct": ev.get("score_pct"), "scorecard_name": ev.get("scorecard_name"), "critical_misses": sc.miss_labels(ev), "summary": ev.get("summary"),
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
    return {**scr.serialize_script(s), "department": s.get("department"), "department_label": ind.dept_label(s.get("department")), "industry": s.get("industry") or ind.industry_of_dept(s.get("department")), "client_specific": bool(s.get("shop_client_id")), "shop_client_id": s.get("shop_client_id"), "curveballs": s.get("curveballs") or [], "generated": bool(s.get("generated_from"))}


CATEGORY_BY_DEPT = {"sales": "Sales calls", "service": "Service", "parts": "Parts", "rental": "Rental"}


def _challenge_fields(body: ChallengeBody) -> dict:
    if body.department not in ind.all_dept_keys():
        raise HTTPException(status_code=400, detail="Pick a department from the list")
    if not body.title.strip() or not body.body.strip():
        raise HTTPException(status_code=400, detail="Title and the challenge text are required")
    persona = body.persona or {}
    if not (persona.get("name") or "").strip() or not (persona.get("opening_line") or "").strip():
        raise HTTPException(status_code=400, detail="The shopper needs a name and an opening line")
    return {"department": body.department, "industry": ind.industry_of_dept(body.department), "direction": "outbound" if body.direction == "outbound" else "inbound", "category": CATEGORY_BY_DEPT.get(body.department) or ind.dept_label(body.department), "title": no_em_dash(body.title.strip())[:120], "runtime": (body.runtime or "").strip()[:40], "purpose": no_em_dash(body.purpose or "")[:400], "body": no_em_dash(body.body)[:8000],
            "success_points": [str(p).strip()[:160] for p in (body.success_points or []) if str(p).strip()][:12], "curveballs": [no_em_dash(str(c)).strip()[:160] for c in (body.curveballs or []) if str(c).strip()][:4],
            "persona": {"name": str(persona.get("name")).strip()[:60], "voice": persona.get("voice") if persona.get("voice") in ("female", "male", "young", "older") else "female", "summary": no_em_dash(str(persona.get("summary") or ""))[:400],
                        "goals": no_em_dash(str(persona.get("goals") or ""))[:200], "objections": [no_em_dash(str(o))[:160] for o in (persona.get("objections") or []) if str(o).strip()][:6], "opening_line": no_em_dash(str(persona.get("opening_line")))[:240]}}


async def _insert_challenge(db, me: dict, body: ChallengeBody, cid: Optional[str]) -> dict:
    now = datetime.now(timezone.utc)
    doc = {"kind": "phone", "pool": "mystery_shop", "shop_client_id": cid, "store_id": None, "slug": f"shop_custom_{ObjectId()}", **_challenge_fields(body),
           "generated_from": (body.generated_from or "").strip()[:3000] or None, "created_by": str(me["_id"]), "created_by_name": me.get("name"), "active": True, "created_at": now, "updated_at": now}
    res = await db.scripts.insert_one(doc)
    return _challenge_out(await db.scripts.find_one({"_id": res.inserted_id}))


@router.post("/challenges")
async def add_global_challenge(body: ChallengeBody, request: Request):
    me = await require_admin(request)
    return await _insert_challenge(get_db(), me, body, None)


@router.post("/challenges/generate")
async def generate_challenges(body: GenerateBody, request: Request):
    """Plain-words scenario in, 1 to 5 challenge drafts out. Nothing is saved until Forest hits save on a draft."""
    await require_admin(request)
    if body.department not in ind.all_dept_keys():
        raise HTTPException(status_code=400, detail="Pick a department from the list")
    if len((body.scenario or "").strip()) < 15:
        raise HTTPException(status_code=400, detail="Describe the situation in a sentence or two")
    client = await get_db().shop_clients.find_one({"_id": _oid(body.client_id, "Client")}) if body.client_id else None
    try:
        drafts = await ms.generate_challenges(body.department, body.scenario, body.count or 1, client, ind.industry_of_dept(body.department))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.warning(f"[MysteryShop] generate failed: {e}")
        raise HTTPException(status_code=503, detail="Jessi is busy right now, try again in a moment")
    return {"drafts": drafts, "scenario": body.scenario.strip()}


@router.put("/challenges/{script_id}")
async def update_challenge(script_id: str, body: ChallengeBody, request: Request):
    await require_admin(request)
    db = get_db()
    s = await db.scripts.find_one({"_id": _oid(script_id, "Challenge"), "pool": "mystery_shop"})
    if not s:
        raise HTTPException(status_code=404, detail="Challenge not found")
    await db.scripts.update_one({"_id": s["_id"]}, {"$set": {**_challenge_fields(body), "updated_at": datetime.now(timezone.utc)}})
    await db.roleplay_sessions.update_many({"kind": "mystery_shop", "script_id": script_id, "status": "scheduled"}, {"$set": {"script_title": body.title.strip()[:120]}})
    return _challenge_out(await db.scripts.find_one({"_id": s["_id"]}))


@router.get("/{cid}/challenges")
async def list_challenges(cid: str, request: Request):
    await require_admin(request)
    db = get_db()
    await _client(db, cid)
    c = await _client(db, cid)
    return {"challenges": [_challenge_out(s) for s in await ms.challenge_pool(db, cid, None, ind.key_of(c))], "departments": ind.dept_options(ind.key_of(c))}


@router.post("/{cid}/challenges")
async def add_challenge(cid: str, body: ChallengeBody, request: Request):
    me = await require_admin(request)
    db = get_db()
    await _client(db, cid)
    return await _insert_challenge(db, me, body, cid)


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


@public_router.get("/shop-score/{token}")
async def public_score(token: str):
    """The scorecard link texted to the person who got shopped: score, wins, coaching, recording. No login."""
    db = get_db()
    s = await db.roleplay_sessions.find_one({"kind": "mystery_shop", "score_token": token}) if len(token or "") >= 16 else None
    if not s:
        raise HTTPException(status_code=404, detail="Scorecard not found")
    ev = await db.call_evaluations.find_one({"_id": ObjectId(s["evaluation_id"])}) if s.get("evaluation_id") and ObjectId.is_valid(str(s["evaluation_id"])) else None
    if not ev:
        raise HTTPException(status_code=404, detail="Scorecard not ready yet")
    client = await db.shop_clients.find_one({"_id": _oid(s["client_id"])}) if ObjectId.is_valid(str(s.get("client_id"))) else None
    await db.roleplay_sessions.update_one({"_id": s["_id"]}, {"$inc": {"score_views": 1}, "$set": {"score_viewed_at": datetime.now(timezone.utc)}})
    return ms.public_score(s, ev, client or {})



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
    keys = ind.dept_keys(ind.key_of(c))
    per = body.per_month if isinstance(body.per_month, dict) and body.per_month else {"sales": body.sales_per_month or 0, "service": body.service_per_month or 0}
    per = {k: max(0, min(200, int(v or 0))) for k, v in per.items() if k in keys}
    if not any(per.values()):
        raise HTTPException(status_code=400, detail="Set how many shops per month")
    doc = {"client_id": cid, "client_name": c.get("name"), "contact_name": (body.contact_name or c.get("contact_name") or "").strip(), "contact_email": (body.contact_email or c.get("contact_email") or "").strip().lower(),
           "terms": {"per_month": per, "sales_per_month": per.get("sales", 0), "service_per_month": per.get("service", 0), "price_monthly": round(float(body.price_monthly), 2), "term_months": max(1, min(24, body.term_months)), "notes": no_em_dash(body.notes or "")[:1500]},
           "status": "draft", "token": uuid.uuid4().hex, "sender_id": str(me["_id"]), "sender_name": me.get("name") or "I'm On Social", "created_at": now, "updated_at": now}
    res = await db.shop_proposals.insert_one(doc)
    await db.shop_clients.update_one({"_id": c["_id"]}, {"$set": {"plan": {"per_month": per, "price_monthly": doc["terms"]["price_monthly"]}}})
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
    c = await db.shop_clients.find_one({"_id": ObjectId(p["client_id"])}) if ObjectId.is_valid(str(p.get("client_id"))) else None
    pack = ind.get(ind.key_of(c))
    out["per_month"] = ms.terms_per_month(p.get("terms") or {})
    out["departments"] = ind.dept_options(ind.key_of(c))
    out["offering"] = pack["offering"]
    out["business_noun"] = pack["business"]
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
                       "contact_phone": c.get("contact_phone", ""), "contact_title": c.get("contact_title", ""), "timezone": c.get("timezone") or "America/Denver", "hours": ms._hours(c), "vehicles": ms.offerings_of(c),
                       "offerings": ms.offerings_of(c), "industry": ind.key_of(c), "offering": ind.get(ind.key_of(c))["offering"], "customer_noun": ind.get(ind.key_of(c))["customer"], "business_noun": ind.get(ind.key_of(c))["business"],
                       "plan": {**(c.get("plan") or {}), "per_month": ms.plan_per_month(c)}, "kickoff": {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in (c.get("kickoff") or {}).items()}},
            "people": [{"id": str(t["_id"]), "name": t.get("name", ""), "phone": t.get("phone", ""), "department": t.get("department", "sales"), "title": t.get("title", "")} for t in people],
            "departments": ind.dept_options(ind.key_of(c)), "timezones": [{"id": a, "label": b} for a, b in ms.TIMEZONES], "sender_name": (c.get("kickoff") or {}).get("sender_name") or "Forest"}


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
    offerings = body.offerings if body.offerings is not None else body.vehicles
    if offerings is not None:
        upd["vehicles"] = [str(v).strip()[:80] for v in offerings if str(v).strip()][:30]
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
        keys = ind.dept_keys(ind.key_of(c))
        dept = person.department if person.department in keys else keys[0]
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
