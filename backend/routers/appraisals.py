"""Trade Appraisal (MVP1): drafts, customer, capture mode, vehicle identity (VIN photo / typed / reappraise), mileage, customer expectation,
media with provenance, audit trail, vehicles on a contact. Scoped by the platform's accessible-user rule."""
import asyncio
import base64
import logging
import re
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from permissions import is_feature_enabled, merge_permissions
from routers.database import get_db, get_data_filter
from routers.lead_sources import require_user
from services.appraisals import core
from services.appraisals import followup
from services.appraisals import inspection
from services.appraisals import intake
from services.appraisals import market
from services.appraisals import market_providers as mp
from services.appraisals.providers import ProviderUnavailable, identity_options, IDENTITY
from services.appraisals import providers as identity
from services.appraisals import readers
from services.appraisals import voice
from services.appraisals import matrix
from services.appraisals import relationship
from services.appraisals import reporting
from services.appraisals import rules as rulesvc
from services.appraisals import workflow

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/appraisals", tags=["appraisals"], dependencies=[Depends(require_user)])


class RulesBody(BaseModel):
    scope: str = "org"
    store_id: Optional[str] = None
    organization_id: Optional[str] = None
    rules: dict


class DecideBody(BaseModel):
    action: str
    value: Optional[int] = None
    reason: str = ""


class OutcomeBody(BaseModel):
    outcome: str
    expected_value: Optional[int] = None
    note: str = ""


class CreateBody(BaseModel):
    contact_id: str
    mode: str = "vehicle_here"
    vehicle_id: Optional[str] = None


class OwnershipBody(BaseModel):
    status: str
    note: Optional[str] = ""
    deal_id: Optional[str] = None


class OrgSettingsBody(BaseModel):
    allow_trade_values_in_automated_messages: bool = False
    organization_id: Optional[str] = None


class ModeBody(BaseModel):
    mode: str


class VinBody(BaseModel):
    vin: str


class VehicleBody(BaseModel):
    vin: Optional[str] = None
    manual: Optional[dict] = None
    method: str = "manual_vin"


class MileageBody(BaseModel):
    confirmed: int
    detected: Optional[int] = None
    source: str = "manual"


class ExpectationBody(BaseModel):
    asked: bool
    value: Optional[int] = None


class MediaChunk(BaseModel):
    upload_id: str
    index: int
    total: int
    data: str
    name: str = ""
    content_type: str = "application/octet-stream"
    role: str
    source: str


class VoiceChunk(BaseModel):
    upload_id: str
    index: int
    total: int
    data: str
    content_type: str = "audio/mp4"
    duration: float = 0


async def _collect_chunks(db, me: dict, prefix: str, chunk) -> tuple:
    """Buffer one base64 piece under (user, upload id); on the last piece return the assembled bytes, otherwise None and how many arrived."""
    if chunk.total < 1 or chunk.total > 400 or not (0 <= chunk.index < chunk.total) or len(chunk.data) > 900_000:
        raise HTTPException(status_code=400, detail="Bad chunk")
    upload_id = re.sub(r"[^A-Za-z0-9_-]", "", chunk.upload_id)[:64]
    if not upload_id:
        raise HTTPException(status_code=400, detail="Bad upload id")
    key = {"user_id": str(me["_id"]), "upload_id": f"{prefix}_{upload_id}"}
    await db.voice_upload_chunks.update_one({**key, "index": chunk.index}, {"$set": {"data": chunk.data, "created_at": datetime.now(timezone.utc)}}, upsert=True)
    have = await db.voice_upload_chunks.count_documents(key)
    if have < chunk.total:
        return None, have
    parts = await db.voice_upload_chunks.find(key).sort("index", 1).to_list(chunk.total)
    await db.voice_upload_chunks.delete_many(key)
    try:
        return base64.b64decode("".join(p["data"] for p in parts)), have
    except Exception:
        raise HTTPException(status_code=400, detail="That file came through damaged. Please try again.")


class FindingBody(BaseModel):
    category: Optional[str] = None
    subtype: Optional[str] = None
    location: Optional[str] = None
    location_label: Optional[str] = None
    severity: Optional[str] = None
    explanation: Optional[str] = None
    frame_ids: Optional[list] = None


class DecisionBody(BaseModel):
    decision: str


class OverrideBody(BaseModel):
    overall: Optional[str] = None
    reason: str = ""


class MarketRefreshBody(BaseModel):
    zip: Optional[str] = None
    radius: Optional[int] = None
    force: bool = False


class CompareBody(MarketRefreshBody):
    probe_zip: bool = False


class AdhocCompareBody(CompareBody):
    vin: Optional[str] = None
    mileage: Optional[int] = None
    year: Optional[int] = None
    make: Optional[str] = None
    model: Optional[str] = None
    trim: Optional[str] = None


class BookValueBody(BaseModel):
    source: Optional[str] = None
    source_label: Optional[str] = None
    value_type: Optional[str] = None
    value: Optional[int] = None
    note: Optional[str] = None


def _me(request: Request) -> dict:
    return request.state.user


def can_appraise(me: dict) -> bool:
    """Managers and admins always; reps only when my_tools.trade_appraisal was switched on for them (manager-enabled per store)."""
    if me.get("role") in ("super_admin", "org_admin", "store_manager"):
        return True
    return is_feature_enabled(merge_permissions(me.get("feature_permissions"), me.get("role") or "user"), "my_tools", "trade_appraisal")


def _allowed(me: dict):
    if not can_appraise(me):
        raise HTTPException(status_code=403, detail="Trade Appraisal is not switched on for you yet. Ask your manager.")


async def _appr(db, me: dict, appraisal_id: str) -> dict:
    a = await core.get_appraisal(db, me, appraisal_id)
    if not a:
        raise HTTPException(status_code=404, detail="Appraisal not found")
    return a


def _editable(a: dict):
    """Once submitted, the inputs are frozen until a manager sends it back (needs_info). 409 so the UI can explain instead of failing."""
    try:
        workflow.assert_editable(a)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


def _manager(me: dict):
    if not workflow.can_approve(me):
        raise HTTPException(status_code=403, detail="Appraisal approvals are not switched on for you.")


def _rules_admin(me: dict):
    if not workflow.can_edit_rules(me):
        raise HTTPException(status_code=403, detail="Only managers with the appraisal rules permission can change dealership rules.")


async def _contact(db, me: dict, contact_id: str) -> dict:
    if not ObjectId.is_valid(contact_id):
        raise HTTPException(status_code=404, detail="Contact not found")
    c = await db.contacts.find_one({"_id": ObjectId(contact_id), **(await get_data_filter(str(me["_id"])))})
    if not c:
        raise HTTPException(status_code=404, detail="Contact not found")
    return c


def _dt(s: Optional[str]) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None
    except ValueError:
        return None


@router.get("/meta")
async def meta(request: Request):
    me = _me(request)
    _allowed(me)
    act = await market.active_for(get_db(), me)
    return {"modes": core.MODES, "sources": core.SOURCES, "roles": core.ROLES, "identity": identity_options(), "steps": core.STEPS,
            "statuses": workflow.STATUS_LABELS, "outcomes": workflow.OUTCOMES, "decisions": list(workflow.DECISIONS),
            "abilities": {"manager": workflow.can_approve(me), "edit_rules": workflow.can_edit_rules(me), "provider_admin": me.get("role") in market.ADMIN_ROLES},
            "market_provider": {"name": act.name, "label": act.label, "live": act.live, "badge": act.badge}}


@router.get("/providers")
async def providers(request: Request):
    """Which market data providers are live vs mock, this month's usage per provider, calls per purpose, and the caller's dealership market rules.
    Managers and admins only; keys are never returned."""
    me = _me(request)
    if me.get("role") not in ("super_admin", "org_admin", "store_manager"):
        raise HTTPException(status_code=403, detail="Managers and admins only")
    db = get_db()
    act = await market.active_for(db, me)
    sid = me.get("store_id") or ((me.get("store_ids") or [None])[0])
    return {"market": mp.provider_options(), "active": {"name": act.name, "label": act.label, "live": act.live, "badge": act.badge}, "usage": await market.usage(db, act),
            "usage_all": await market.usage_all(db), "cost": await market.cost_summary(db, me), "identity": identity_options(), "monthly_cap": market.MONTHLY_CAP_DEFAULT,
            "cache_hours": market.CACHE_HOURS, "market_rules": await market.market_rules_for(db, me.get("organization_id"), str(sid) if sid else None),
            "comparison_admin": me.get("role") in market.ADMIN_ROLES, "dev_market_allowed": workflow.development_basis_allowed()}


def _admin(me: dict):
    if me.get("role") not in market.ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Provider comparison is for admins only")


@router.post("/providers/compare")
async def compare_providers_adhoc(body: AdhocCompareBody, request: Request):
    """Admin, deliberate: run BOTH live providers for one vehicle (VIN or year/make/model) and lay the numbers side by side. Costs paid calls every time
    unless the same request was run in the last 24h. Nothing here touches any appraisal or the engine."""
    me = _me(request)
    _admin(me)
    db = get_db()
    vehicle = {"vin": (body.vin or "").strip().upper() or None, "year": body.year, "make": body.make, "model": body.model, "trim": body.trim}
    if vehicle["vin"] and not (vehicle["year"] and vehicle["make"] and vehicle["model"]):
        try:
            dec = await identity.decode_vin(db, vehicle["vin"])
            vehicle = {**vehicle, **{k: dec.get(k) for k in ("year", "make", "model", "trim") if dec.get(k)}}
        except ProviderUnavailable as e:
            raise HTTPException(status_code=503, detail=f"VIN decoder unavailable ({e}). Give year, make and model by hand.")
    try:
        return await market.compare(db, me, vehicle=vehicle, mileage=body.mileage, zip_code=body.zip, radius=body.radius, force=body.force, probe_zip=body.probe_zip)
    except (ValueError, mp.MarketRateLimited, mp.MarketUnavailable) as e:
        raise _market_error(e)


@router.get("/providers/comparisons")
async def list_provider_comparisons(request: Request, limit: int = 50):
    me = _me(request)
    _admin(me)
    return {"comparisons": await market.list_comparisons(get_db(), me, limit)}


class MatrixBody(BaseModel):
    vehicles: list = []
    zip: str = ""
    radius: Optional[int] = None
    force: bool = False


@router.post("/providers/matrix/plan")
async def matrix_plan(body: MatrixBody, request: Request):
    """Zero API calls: how many vehicles would run and how many paid calls that costs."""
    _admin(_me(request))
    try:
        vs = matrix.clean_vehicles(body.vehicles)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"plan": matrix.plan(vs), "vehicles": vs}


@router.post("/providers/matrix")
async def matrix_start(body: MatrixBody, request: Request):
    """Admin, deliberate, runs where the keys live: up to 25 real vehicles through both live providers in the background. Poll GET /providers/matrix/{id}."""
    me = _me(request)
    _admin(me)
    try:
        return await matrix.start(get_db(), me, vehicles=body.vehicles, zip_code=body.zip, radius=body.radius, force=body.force)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/providers/matrix")
async def matrix_recent(request: Request, limit: int = 5):
    me = _me(request)
    _admin(me)
    return {"runs": await matrix.recent(get_db(), me, limit)}


@router.get("/providers/matrix/{run_id}")
async def matrix_get(run_id: str, request: Request):
    me = _me(request)
    _admin(me)
    run = await matrix.get(get_db(), me, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Matrix run not found")
    return run


@router.get("")
async def list_appraisals(request: Request, group: Optional[str] = None, q: str = "", date_from: Optional[str] = None, date_to: Optional[str] = None):
    me = _me(request)
    _allowed(me)
    db = get_db()
    out = await core.list_appraisals(db, me, group, q, _dt(date_from), _dt(date_to))
    out["status_labels"] = workflow.STATUS_LABELS
    if workflow.can_approve(me):
        out["desk"] = await workflow.desk_counts(db, me)
    return out


# ---------- dealership rules (MVP4) ----------
async def _rules_payload(db, me: dict, store_id: Optional[str], organization_id: Optional[str] = None) -> dict:
    r = await rulesvc.reach(db, me)
    stores = {s["id"]: s for s in r["stores"]}
    store_id = store_id or None
    if store_id and store_id not in stores:
        raise HTTPException(status_code=403, detail="That store is outside your reach")
    org_id = (stores[store_id]["organization_id"] if store_id else None) or (organization_id if me.get("role") == "super_admin" else None) or r["organization_id"]
    docs = await rulesvc.get_docs(db, org_id, store_id)
    eff = await rulesvc.effective(db, org_id, store_id)
    return {"organization_id": org_id, "store_id": store_id, "org_editable": r["org_editable"] and bool(org_id), "stores": r["stores"], "effective": eff,
            "org": rulesvc.public_rules_doc(docs["org"]), "store": rulesvc.public_rules_doc(docs["store"]), "warnings": rulesvc.double_count_warnings(eff["rules"]),
            "options": {"basis": rulesvc.BASIS_OPTIONS, "conditions": rulesvc.CONDITION_LABELS, "defaults": rulesvc.DEFAULT_RULES, "outcomes": workflow.OUTCOMES,
                        "roundings": [1, 5, 10, 25, 50, 100], "task_kinds": list(rulesvc.TASK_KINDS), "triggers": followup.TRIGGER_EVENTS, "merge_fields": followup.MERGE_FIELD_HELP,
                        "market_providers": {k: {**v, "configured": mp.PROVIDERS[k].configured()} for k, v in rulesvc.MARKET_PROVIDER_OPTIONS.items()}},
            "org_settings": {"allow_trade_values_in_automated_messages": await followup.org_allows_trade_values(db, org_id), "editable": me.get("role") in ("org_admin", "super_admin") and bool(org_id)},
            "can_edit": workflow.can_edit_rules(me)}


@router.get("/rules")
async def get_rules(request: Request, store_id: Optional[str] = None, organization_id: Optional[str] = None):
    """Effective rules (store override > org default > platform defaults) plus both documents and the editor options. Managers and admins."""
    me = _me(request)
    _manager(me) if not workflow.can_edit_rules(me) else None
    return await _rules_payload(get_db(), me, store_id, organization_id)


@router.put("/rules")
async def put_rules(body: RulesBody, request: Request):
    """Save the org default (org admins / super admins) or one store's override (store managers and up). Every save is a new version; the old one
    goes to history so submitted appraisals keep pointing at the rules they used."""
    me = _me(request)
    _rules_admin(me)
    db = get_db()
    r = await rulesvc.reach(db, me)
    stores = {s["id"]: s for s in r["stores"]}
    if body.scope == "store":
        if not body.store_id or body.store_id not in stores:
            raise HTTPException(status_code=403, detail="Pick one of your stores")
        org_id = stores[body.store_id]["organization_id"] or r["organization_id"]
        try:
            await rulesvc.save(db, me, organization_id=org_id, store_id=body.store_id, rules=body.rules)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        return await _rules_payload(db, me, body.store_id)
    if body.scope != "org":
        raise HTTPException(status_code=400, detail="scope must be org or store")
    org_id = (body.organization_id if me.get("role") == "super_admin" else None) or r["organization_id"]
    if not r["org_editable"] or not org_id:
        raise HTTPException(status_code=403, detail="Only organization admins change the organization default. You can set a store override.")
    try:
        await rulesvc.save(db, me, organization_id=org_id, store_id=None, rules=body.rules)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return await _rules_payload(db, me, None, org_id)


@router.delete("/rules/store/{store_id}")
async def delete_store_rules(store_id: str, request: Request):
    me = _me(request)
    _rules_admin(me)
    db = get_db()
    r = await rulesvc.reach(db, me)
    if store_id not in {s["id"] for s in r["stores"]}:
        raise HTTPException(status_code=403, detail="That store is outside your reach")
    removed = await rulesvc.remove_store_override(db, store_id)
    out = await _rules_payload(db, me, store_id)
    out["removed"] = removed
    return out


# ---------- manager desk (MVP4) ----------
@router.get("/desk")
async def desk(request: Request, group: str = "waiting", q: str = ""):
    """Waiting (oldest first), sent back, decided. Only people with the approvals permission; scoped like everything else."""
    me = _me(request)
    _manager(me)
    return await workflow.desk_list(get_db(), me, group, q)


@router.get("/desk/{appraisal_id}")
async def desk_detail(appraisal_id: str, request: Request):
    me = _me(request)
    _manager(me)
    db = get_db()
    a = await _appr(db, me, appraisal_id)
    return await workflow.desk_detail(db, a, me)


@router.post("")
async def create(body: CreateBody, request: Request):
    me = _me(request)
    _allowed(me)
    db = get_db()
    contact = await _contact(db, me, body.contact_id)
    try:
        doc = await core.create(db, me, contact, body.mode, body.vehicle_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"appraisal": core.public_appraisal(doc)}


@router.get("/vehicles/{contact_id}")
async def contact_vehicles(contact_id: str, request: Request):
    """Vehicles on a contact as relationship records: ownership, trade intent, last appraisal numbers, reappraisal opportunity (MVP5)."""
    me = _me(request)
    db = get_db()
    await _contact(db, me, contact_id)
    return {"vehicles": await relationship.contact_cards(db, me, contact_id), "can_appraise": can_appraise(me), "ownership_options": relationship.OWNERSHIP}


async def _vehicle(db, me: dict, vehicle_id: str) -> dict:
    v = await core.get_vehicle(db, me, vehicle_id)
    if not v:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return v


@router.get("/vehicle/{vehicle_id}")
async def vehicle_detail(vehicle_id: str, request: Request):
    """One vehicle: chronological appraisal history (normalized numbers), value changes over time, ownership, trade intent, opportunity."""
    me = _me(request)
    db = get_db()
    v = await _vehicle(db, me, vehicle_id)
    out = await relationship.vehicle_detail(db, me, v)
    out["can_appraise"] = can_appraise(me)
    return out


@router.put("/vehicle/{vehicle_id}/ownership")
async def vehicle_ownership(vehicle_id: str, body: OwnershipBody, request: Request):
    """Confirm what actually happened to the vehicle (traded / sold / still owns). The only way a vehicle becomes 'traded'; an accepted offer never does it."""
    me = _me(request)
    _allowed(me)
    db = get_db()
    v = await _vehicle(db, me, vehicle_id)
    try:
        v2 = await relationship.set_ownership(db, me, v, body.status, body.note or "", body.deal_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    out = await relationship.vehicle_detail(db, me, v2)
    out["can_appraise"] = can_appraise(me)
    return out


@router.get("/pipeline")
async def pipeline(request: Request, team: bool = False):
    """MY TRADE PIPELINE: needs attention, waiting on manager, approved to present, presented to follow up, reappraisal opportunities, recently closed."""
    me = _me(request)
    _allowed(me)
    return await reporting.pipeline(get_db(), me, team)


@router.get("/search")
async def search(request: Request, q: str = "", status: Optional[str] = None, outcome: Optional[str] = None, make: Optional[str] = None, user_id: Optional[str] = None,
                 store_id: Optional[str] = None, date_from: Optional[str] = None, date_to: Optional[str] = None, limit: int = 100):
    me = _me(request)
    _allowed(me)
    return await reporting.search(get_db(), me, q, status, outcome, make, user_id, store_id, _dt(date_from), _dt(date_to), limit)


@router.get("/reports/summary")
async def reports_summary(request: Request, store_id: Optional[str] = None, user_id: Optional[str] = None, manager_id: Optional[str] = None, outcome: Optional[str] = None,
                          make: Optional[str] = None, date_from: Optional[str] = None, date_to: Optional[str] = None):
    """Manager dashboard: counts, averages (ACV, approved, adjustment, gap, response time), rates, by salesperson / manager / make. Scoped."""
    me = _me(request)
    _manager(me)
    f = {k: v for k, v in {"store_id": store_id, "user_id": user_id, "manager_id": manager_id, "outcome": outcome, "make": make, "date_from": _dt(date_from), "date_to": _dt(date_to)}.items() if v}
    return await reporting.summary(get_db(), me, f)


@router.get("/reports/followup")
async def reports_followup(request: Request):
    """Manager follow-up view: waiting too long, large gaps, large adjustments, wants more / thinking, vehicles to revisit."""
    me = _me(request)
    _manager(me)
    return await reporting.followup_view(get_db(), me)


@router.get("/campaign-options")
async def campaign_options(request: Request):
    """For the campaign editor: trade appraisal triggers + merge fields, and whether this org lets dollar amounts into automated messages."""
    me = _me(request)
    db = get_db()
    org = await core.org_id_for(db, me)
    return {"triggers": followup.TRIGGER_EVENTS, "merge_fields": followup.MERGE_FIELD_HELP, "money_fields": list(followup.MONEY_FIELDS), "tags": followup.TRADE_TAG_HELP,
            "allow_trade_values": await followup.org_allows_trade_values(db, org), "organization_id": org}


@router.put("/org-settings")
async def put_org_settings(body: OrgSettingsBody, request: Request):
    """Organization-level safety switch: allow_trade_values_in_automated_messages (default OFF). Org admins and super admins only."""
    me = _me(request)
    db = get_db()
    if me.get("role") not in ("org_admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Only organization admins change this setting.")
    org = (body.organization_id if me.get("role") == "super_admin" else None) or await core.org_id_for(db, me)
    if not org:
        raise HTTPException(status_code=400, detail="No organization on your account")
    key = {"$or": [{"_id": org}] + ([{"_id": ObjectId(org)}] if ObjectId.is_valid(str(org)) else [])}
    res = await db.organizations.update_one(key, {"$set": {"allow_trade_values_in_automated_messages": bool(body.allow_trade_values_in_automated_messages),
                                                          "allow_trade_values_updated_by": str(me["_id"]), "allow_trade_values_updated_at": datetime.now(timezone.utc)}})
    if not res.matched_count:
        raise HTTPException(status_code=404, detail="Organization not found")
    return {"organization_id": org, "allow_trade_values_in_automated_messages": bool(body.allow_trade_values_in_automated_messages)}


@router.post("/vin/decode")
async def decode_vin(body: VinBody, request: Request):
    """Validate + decode a typed VIN (no appraisal needed). Returns validation errors instead of 400 so the UI can coach."""
    _allowed(_me(request))
    try:
        res = await core.identify(get_db(), "vin", vin=body.vin)
    except ProviderUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e))
    return res


@router.get("/{appraisal_id}")
async def detail(appraisal_id: str, request: Request):
    me = _me(request)
    _allowed(me)
    db = get_db()
    a = await _appr(db, me, appraisal_id)
    out = core.public_appraisal(a)
    out["media"] = await core.list_media(db, a)
    out["snapshots"] = await core.list_snapshots(db, a)
    out["activity"] = await core.activity(db, a)
    out["inspection"] = await inspection.summary(db, a)
    out["market"] = await market.summary(db, a)
    out["book_values"] = market.public_book_values(a)
    out["workflow"] = workflow.public_workflow(a)
    out["abilities"] = workflow.abilities(me, a)
    out["decisions"] = await workflow.decisions(db, a)
    calc = await workflow.latest_calculation(db, a)
    out["calculation"] = workflow.public_calc(calc) if calc else None
    if a.get("vehicle_id"):
        veh = await core.get_vehicle(db, me, a["vehicle_id"])
        out["vehicle_record"] = core.public_vehicle(veh) if veh else None
        out["history"] = await core.vehicle_appraisals(db, me, a["vehicle_id"])
    return out


@router.patch("/{appraisal_id}")
async def patch(appraisal_id: str, data: dict, request: Request):
    me = _me(request)
    _allowed(me)
    db = get_db()
    a = await _appr(db, me, appraisal_id)
    return {"appraisal": core.public_appraisal(await core.patch(db, a, me, data or {}))}


@router.delete("/{appraisal_id}")
async def delete(appraisal_id: str, request: Request):
    me = _me(request)
    _allowed(me)
    db = get_db()
    a = await _appr(db, me, appraisal_id)
    try:
        await core.delete_draft(db, a, me)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"success": True}


@router.post("/{appraisal_id}/mode")
async def set_mode(appraisal_id: str, body: ModeBody, request: Request):
    me = _me(request)
    _allowed(me)
    db = get_db()
    a = await _appr(db, me, appraisal_id)
    _editable(a)
    try:
        return {"appraisal": core.public_appraisal(await core.set_mode(db, a, me, body.mode))}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


class IntakeLinkBody(BaseModel):
    channel: str = "copy"


@router.post("/{appraisal_id}/intake-link")
async def intake_link(appraisal_id: str, body: IntakeLinkBody, request: Request):
    """Customer not at the store: mint a 7-day link to this appraisal and text it (channel sms) or hand it back to copy (channel copy)."""
    me = _me(request)
    _allowed(me)
    db = get_db()
    a = await _appr(db, me, appraisal_id)
    _editable(a)
    try:
        res = await intake.create_link(db, a, me, channel=body.channel if body.channel in ("sms", "copy") else "copy")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"intake": res, "appraisal": core.public_appraisal(await db[core.A].find_one({"_id": a["_id"]}))}


@router.delete("/{appraisal_id}/intake-link")
async def intake_link_revoke(appraisal_id: str, request: Request):
    me = _me(request)
    _allowed(me)
    db = get_db()
    a = await _appr(db, me, appraisal_id)
    if not a.get("intake"):
        raise HTTPException(status_code=404, detail="No link on this appraisal")
    res = await intake.revoke(db, a, me)
    return {"intake": res, "appraisal": core.public_appraisal(await db[core.A].find_one({"_id": a["_id"]}))}


@router.post("/{appraisal_id}/vehicle")
async def set_vehicle(appraisal_id: str, body: VehicleBody, request: Request):
    """Confirmed VIN (scanned, uploaded or typed) and/or manual vehicle fields -> vehicles doc + snapshot on the appraisal."""
    me = _me(request)
    _allowed(me)
    db = get_db()
    a = await _appr(db, me, appraisal_id)
    _editable(a)
    try:
        doc = await core.set_vehicle(db, a, me, vin=body.vin, manual=body.manual, method=body.method)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ProviderUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e))
    out = core.public_appraisal(doc)
    veh = await core.get_vehicle(db, me, doc["vehicle_id"])
    out["vehicle_record"] = core.public_vehicle(veh) if veh else None
    return {"appraisal": out}


@router.post("/{appraisal_id}/mileage")
async def set_mileage(appraisal_id: str, body: MileageBody, request: Request):
    me = _me(request)
    _allowed(me)
    db = get_db()
    a = await _appr(db, me, appraisal_id)
    _editable(a)
    try:
        return {"appraisal": core.public_appraisal(await core.set_mileage(db, a, me, body.confirmed, body.detected, body.source))}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{appraisal_id}/expectation")
async def set_expectation(appraisal_id: str, body: ExpectationBody, request: Request):
    me = _me(request)
    _allowed(me)
    db = get_db()
    a = await _appr(db, me, appraisal_id)
    _editable(a)
    try:
        return {"appraisal": core.public_appraisal(await core.set_expectation(db, a, me, body.asked, body.value))}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{appraisal_id}/media/chunk")
async def media_chunk(appraisal_id: str, chunk: MediaChunk, request: Request):
    """Base64 pieces (same protocol as contact files); on the last piece the media is stored with its provenance and, for VIN and odometer
    photos, read by Jessi. Returns {media} on the last piece."""
    me = _me(request)
    _allowed(me)
    db = get_db()
    a = await _appr(db, me, appraisal_id)
    _editable(a)
    if chunk.role not in core.ROLES or chunk.source not in core.SOURCES:
        raise HTTPException(status_code=400, detail="Bad media role or source")
    data, have = await _collect_chunks(db, me, "appr", chunk)
    if data is None:
        return {"success": True, "received": have, "total": chunk.total}
    try:
        doc = await core.save_media(db, a, me, role=chunk.role, source=chunk.source, data=data, content_type=chunk.content_type, name=chunk.name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[Appraisal] media save failed: {e}")
        raise HTTPException(status_code=500, detail="Could not store that file")
    return {"success": True, "received": chunk.total, "total": chunk.total, "media": core.public_media(doc)}


@router.post("/{appraisal_id}/media/{media_id}/snapshots")
async def media_snapshots_retry(appraisal_id: str, media_id: str, request: Request):
    """Pull the snapshots out of a walkaround video again (upload-time extraction failed, or an older video never had them). Runs in the background; poll the inspection."""
    me = _me(request)
    _allowed(me)
    db = get_db()
    a = await _appr(db, me, appraisal_id)
    m = await db[core.M].find_one({"_id": core._oid(media_id), "appraisal_id": str(a["_id"]), "deleted": {"$ne": True}})
    if not m or m.get("kind") != "video":
        raise HTTPException(status_code=404, detail="Video not found")
    if m.get("original_available") is False:
        raise HTTPException(status_code=409, detail="The original video is no longer kept, so no new snapshots can be pulled")
    if a.get("status") == "analyzing":
        raise HTTPException(status_code=409, detail="Wait for the inspection to finish first")
    now = core._now()
    await db[core.M].update_one({"_id": m["_id"]}, {"$set": {"frames_started_at": now, "frames_error": None}, "$unset": {"frames_extracted_at": ""}})
    asyncio.create_task(inspection.extract_frames(db, a, m, me, force=True))
    return {"success": True, "media": core.public_media({**m, "frames_started_at": now, "frames_error": None, "frames_extracted_at": None})}


@router.post("/{appraisal_id}/voice-note/chunk")
async def voice_note_chunk(appraisal_id: str, chunk: VoiceChunk, request: Request):
    """The rep talks about the car. Same base64-piece protocol; on the last piece the clip is stored, Whisper types it and the words are appended to
    the appraisal notes. Allowed at any point before the appraisal is closed (notes are never an input to the number)."""
    me = _me(request)
    _allowed(me)
    db = get_db()
    a = await _appr(db, me, appraisal_id)
    if a.get("status") == "closed":
        raise HTTPException(status_code=409, detail="This appraisal is closed")
    data, have = await _collect_chunks(db, me, "aprv", chunk)
    if data is None:
        return {"success": True, "received": have, "total": chunk.total}
    try:
        vn = await voice.add_voice_note(db, a, me, by="rep", data=data, content_type=chunk.content_type, duration=chunk.duration)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[Appraisal] voice note save failed: {e}")
        raise HTTPException(status_code=500, detail="Could not save that recording")
    fresh = await db[core.A].find_one({"_id": a["_id"]})
    return {"success": True, "received": chunk.total, "total": chunk.total, "voice_note": vn, "appraisal": core.public_appraisal(fresh)}


@router.delete("/{appraisal_id}/voice-note/{note_id}")
async def voice_note_delete(appraisal_id: str, note_id: str, request: Request):
    me = _me(request)
    _allowed(me)
    db = get_db()
    a = await _appr(db, me, appraisal_id)
    if a.get("status") == "closed":
        raise HTTPException(status_code=409, detail="This appraisal is closed")
    try:
        await voice.delete_voice_note(db, a, me, note_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    fresh = await db[core.A].find_one({"_id": a["_id"]})
    return {"success": True, "appraisal": core.public_appraisal(fresh)}


@router.get("/{appraisal_id}/media")
async def media(appraisal_id: str, request: Request):
    me = _me(request)
    _allowed(me)
    db = get_db()
    a = await _appr(db, me, appraisal_id)
    return {"media": await core.list_media(db, a)}


@router.delete("/{appraisal_id}/media/{media_id}")
async def delete_media(appraisal_id: str, media_id: str, request: Request):
    me = _me(request)
    _allowed(me)
    db = get_db()
    a = await _appr(db, me, appraisal_id)
    _editable(a)
    try:
        await core.delete_media(db, a, me, media_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"success": True, "media": await core.list_media(db, a)}


# ---------- AI Vehicle Inspection ----------
@router.get("/{appraisal_id}/inspection")
async def get_inspection(appraisal_id: str, request: Request):
    """Status, frames, findings, coverage and the condition report. Same shape while Jessi is still working (poll on status)."""
    me = _me(request)
    _allowed(me)
    db = get_db()
    a = await _appr(db, me, appraisal_id)
    out = await inspection.read(db, a)
    out["media"] = await core.list_media(db, a)
    out["snapshots"] = await core.list_snapshots(db, a)
    areas = {}
    for f in out["frames"]:
        for ar in f.get("areas") or []:
            areas.setdefault(f["media_id"], [])
            if ar not in areas[f["media_id"]]:
                areas[f["media_id"]].append(ar)
    for m in out["media"]:
        m["areas"] = areas.get(m["id"], [])
    out["appraisal_status"] = a.get("status")
    return out


@router.post("/{appraisal_id}/inspection/run")
async def run_inspection(appraisal_id: str, request: Request):
    """Start (or retry) the pipeline over everything on the appraisal. Frames already extracted are reused; findings are matched, not duplicated."""
    me = _me(request)
    _allowed(me)
    db = get_db()
    a = await _appr(db, me, appraisal_id)
    _editable(a)
    try:
        ins = await inspection.start_run(db, a, me)
    except ValueError as e:
        raise HTTPException(status_code=409 if "already" in str(e) else 400, detail=str(e))
    return {"status": ins.get("status"), "stage": ins.get("stage"), "run_count": ins.get("run_count")}


@router.post("/{appraisal_id}/inspection/findings")
async def add_finding(appraisal_id: str, body: FindingBody, request: Request):
    me = _me(request)
    _allowed(me)
    db = get_db()
    a = await _appr(db, me, appraisal_id)
    _editable(a)
    ins = await inspection.get_or_create(db, a)
    try:
        d = await inspection.add_finding(db, ins, a, me, body.model_dump(exclude_none=True))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    frames = {str(f["_id"]): f for f in await inspection.frames_for(db, ins)}
    return {"finding": inspection.public_finding(d, frames)}


@router.patch("/{appraisal_id}/inspection/findings/{finding_id}")
async def edit_finding(appraisal_id: str, finding_id: str, body: FindingBody, request: Request):
    me = _me(request)
    _allowed(me)
    db = get_db()
    a = await _appr(db, me, appraisal_id)
    _editable(a)
    ins = await inspection.get_or_create(db, a)
    try:
        d = await inspection.edit_finding(db, ins, a, me, finding_id, body.model_dump(exclude_none=True))
    except ValueError as e:
        raise HTTPException(status_code=404 if "not found" in str(e) else 400, detail=str(e))
    frames = {str(f["_id"]): f for f in await inspection.frames_for(db, ins)}
    return {"finding": inspection.public_finding(d, frames)}


@router.post("/{appraisal_id}/inspection/findings/{finding_id}/decision")
async def decide_finding(appraisal_id: str, finding_id: str, body: DecisionBody, request: Request):
    me = _me(request)
    _allowed(me)
    db = get_db()
    a = await _appr(db, me, appraisal_id)
    _editable(a)
    ins = await inspection.get_or_create(db, a)
    try:
        d = await inspection.decide(db, ins, a, me, finding_id, body.decision)
    except ValueError as e:
        raise HTTPException(status_code=404 if "not found" in str(e) else 400, detail=str(e))
    frames = {str(f["_id"]): f for f in await inspection.frames_for(db, ins)}
    return {"finding": inspection.public_finding(d, frames)}


@router.post("/{appraisal_id}/inspection/override")
async def override_condition(appraisal_id: str, body: OverrideBody, request: Request):
    """Manager/rep sets the final overall condition (overall=null clears it). Reason and author are kept."""
    me = _me(request)
    _allowed(me)
    db = get_db()
    a = await _appr(db, me, appraisal_id)
    _editable(a)
    ins = await inspection.get_or_create(db, a)
    try:
        await inspection.override(db, ins, a, me, body.overall, body.reason)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return await inspection.read(db, a)


# ---------- Market analysis (MVP3) ----------
def _market_error(e: Exception) -> HTTPException:
    if isinstance(e, mp.MarketRateLimited):
        return HTTPException(status_code=429, detail=str(e), headers={"Retry-After": str(int(e.retry_after) + 1)})
    if isinstance(e, mp.MarketQuotaExceeded):
        return HTTPException(status_code=429, detail=str(e), headers={"Retry-After": str(e.retry_after or 3600), "X-Quota-Monthly": "1" if e.monthly else "0"})
    if isinstance(e, mp.MarketUnavailable):
        return HTTPException(status_code=503, detail=str(e))
    return HTTPException(status_code=400, detail=str(e))


@router.get("/{appraisal_id}/market")
async def get_market(appraisal_id: str, request: Request):
    """Latest snapshot + comparables + book values + which provider is answering (live vs DEVELOPMENT DATA). Scoped through the appraisal."""
    me = _me(request)
    _allowed(me)
    db = get_db()
    a = await _appr(db, me, appraisal_id)
    return await market.read(db, a, me)


@router.post("/{appraisal_id}/market/refresh")
async def refresh_market(appraisal_id: str, body: MarketRefreshBody, request: Request):
    """Fetch market data (reused for 24h unless force). Every fetch is a new snapshot; nothing is overwritten. 429 = rate limit / quota, 503 = provider down."""
    me = _me(request)
    _allowed(me)
    db = get_db()
    a = await _appr(db, me, appraisal_id)
    _editable(a)
    try:
        res = await market.refresh(db, a, me, zip_code=body.zip, radius=body.radius, force=body.force)
    except (ValueError, mp.MarketUnavailable, mp.MarketRateLimited) as e:
        raise _market_error(e)
    out = await market.read(db, await _appr(db, me, appraisal_id), me)
    out["cached"] = res["cached"]
    return out


@router.post("/{appraisal_id}/market/compare")
async def compare_market_providers(appraisal_id: str, body: CompareBody, request: Request):
    """Admin, deliberate: both live providers for THIS appraisal's vehicle, side by side. Allowed only when the dealership rules switch comparison on.
    Comparison snapshots never become the appraisal's market snapshot and never reach the engine."""
    me = _me(request)
    _admin(me)
    db = get_db()
    a = await _appr(db, me, appraisal_id)
    mr = await market.market_rules_for(db, a.get("organization_id"), a.get("store_id"))
    if not mr.get("comparison"):
        raise HTTPException(status_code=403, detail="Provider comparison is switched off in this dealership's appraisal rules.")
    try:
        return await market.compare(db, me, appr=a, zip_code=body.zip, radius=body.radius, force=body.force, probe_zip=body.probe_zip)
    except (ValueError, mp.MarketRateLimited, mp.MarketUnavailable) as e:
        raise _market_error(e)


@router.post("/{appraisal_id}/book-values")
async def add_book_value(appraisal_id: str, body: BookValueBody, request: Request):
    me = _me(request)
    _allowed(me)
    db = get_db()
    a = await _appr(db, me, appraisal_id)
    _editable(a)
    try:
        doc = await market.add_book_value(db, a, me, body.model_dump(exclude_none=True))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"book_values": market.public_book_values(doc), "appraisal": core.public_appraisal(doc)}


@router.patch("/{appraisal_id}/book-values/{book_id}")
async def edit_book_value(appraisal_id: str, book_id: str, body: BookValueBody, request: Request):
    me = _me(request)
    _allowed(me)
    db = get_db()
    a = await _appr(db, me, appraisal_id)
    _editable(a)
    try:
        doc = await market.edit_book_value(db, a, me, book_id, body.model_dump(exclude_none=True))
    except ValueError as e:
        raise HTTPException(status_code=404 if "not found" in str(e) else 400, detail=str(e))
    return {"book_values": market.public_book_values(doc), "appraisal": core.public_appraisal(doc)}


@router.delete("/{appraisal_id}/book-values/{book_id}")
async def remove_book_value(appraisal_id: str, book_id: str, request: Request):
    me = _me(request)
    _allowed(me)
    db = get_db()
    a = await _appr(db, me, appraisal_id)
    _editable(a)
    try:
        doc = await market.remove_book_value(db, a, me, book_id)
    except ValueError as e:
        raise HTTPException(status_code=404 if "not found" in str(e) else 400, detail=str(e))
    return {"book_values": market.public_book_values(doc), "appraisal": core.public_appraisal(doc)}


# ---------- value, submission, decision, presentation, outcome (MVP4) ----------
def _wf_error(e: Exception) -> HTTPException:
    if isinstance(e, PermissionError):
        return HTTPException(status_code=403, detail=str(e))
    if isinstance(e, workflow.TransitionError):
        return HTTPException(status_code=409, detail=str(e))
    return HTTPException(status_code=400, detail=str(e))


@router.get("/{appraisal_id}/calculate")
async def calculate(appraisal_id: str, request: Request):
    """Live preview with today's data and the effective rules. Nothing is stored; the number is frozen only on submit."""
    me = _me(request)
    _allowed(me)
    db = get_db()
    a = await _appr(db, me, appraisal_id)
    out = await workflow.preview(db, a)
    out["abilities"] = workflow.abilities(me, a)
    return out


@router.get("/{appraisal_id}/calculations")
async def calculations(appraisal_id: str, request: Request):
    me = _me(request)
    _allowed(me)
    db = get_db()
    a = await _appr(db, me, appraisal_id)
    return {"calculations": await workflow.calculations(db, a)}


@router.get("/{appraisal_id}/decisions")
async def list_decisions(appraisal_id: str, request: Request):
    me = _me(request)
    _allowed(me)
    db = get_db()
    a = await _appr(db, me, appraisal_id)
    return {"decisions": await workflow.decisions(db, a)}


@router.post("/{appraisal_id}/submit")
async def submit(appraisal_id: str, request: Request):
    """Freeze the calculation (rules version, market snapshot, inspection, book values) and notify the store's managers."""
    me = _me(request)
    _allowed(me)
    db = get_db()
    a = await _appr(db, me, appraisal_id)
    try:
        doc = await workflow.submit(db, a, me)
    except (ValueError, PermissionError) as e:
        raise _wf_error(e)
    return {"appraisal": core.public_appraisal(doc), "workflow": workflow.public_workflow(doc), "abilities": workflow.abilities(me, doc), "notified": len(doc.get("notified_manager_ids") or [])}


@router.post("/{appraisal_id}/decide")
async def decide(appraisal_id: str, body: DecideBody, request: Request):
    """Manager: approve | change (value + reason) | request_info (reason) | decline (reason). Records the decision, moves the status, tells the rep."""
    me = _me(request)
    _manager(me)
    db = get_db()
    a = await _appr(db, me, appraisal_id)
    try:
        doc = await workflow.decide(db, a, me, body.action, body.value, body.reason)
    except (ValueError, PermissionError) as e:
        raise _wf_error(e)
    return await workflow.desk_detail(db, doc, me)


@router.post("/{appraisal_id}/present")
async def present(appraisal_id: str, request: Request):
    me = _me(request)
    _allowed(me)
    db = get_db()
    a = await _appr(db, me, appraisal_id)
    try:
        doc = await workflow.present(db, a, me)
    except (ValueError, PermissionError) as e:
        raise _wf_error(e)
    return {"appraisal": core.public_appraisal(doc), "workflow": workflow.public_workflow(doc), "abilities": workflow.abilities(me, doc)}


@router.post("/{appraisal_id}/outcome")
async def outcome(appraisal_id: str, body: OutcomeBody, request: Request):
    """What the customer said: accepted | wants_more (+ amount) | thinking | not_trading | other. Closes the appraisal and updates the relationship record."""
    me = _me(request)
    _allowed(me)
    db = get_db()
    a = await _appr(db, me, appraisal_id)
    try:
        doc = await workflow.record_outcome(db, a, me, body.outcome, body.expected_value, body.note)
    except (ValueError, PermissionError) as e:
        raise _wf_error(e)
    return {"appraisal": core.public_appraisal(doc), "workflow": workflow.public_workflow(doc), "abilities": workflow.abilities(me, doc)}
