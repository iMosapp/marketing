"""Appraisal workflow (MVP4): status machine, immutable calculation snapshots, submit → manager decision → present → outcome → close,
notifications, relationship intelligence and campaign hooks. Three numbers stay separate forever: market value, I'm On Social suggested ACV,
manager-approved value."""
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId

from permissions import is_feature_enabled, merge_permissions
from services.appraisals import core, engine, inspection, market, rules as rulesvc
from services.appraisals.core import A, V, _now, _oid, _name, audit, vehicle_label
from utils.activity_log import log_activity

logger = logging.getLogger(__name__)

CALC, DEC, EVT = "appraisal_calculations", "appraisal_decisions", "appraisal_events"
STATUSES = ["draft", "capturing", "analyzing", "ready", "submitted", "needs_info", "resubmitted", "approved", "changed", "declined", "presented", "closed"]
STATUS_LABELS = {"draft": "Draft", "capturing": "Capturing", "analyzing": "Inspecting", "ready": "Ready", "submitted": "Waiting for manager", "needs_info": "Manager wants more",
                 "resubmitted": "Resubmitted", "approved": "Approved", "changed": "Approved (changed)", "declined": "Declined", "presented": "Presented", "closed": "Closed"}
TRANSITIONS = {
    "draft": {"capturing", "analyzing", "ready", "submitted"}, "capturing": {"analyzing", "ready", "submitted", "draft"}, "analyzing": {"ready", "draft", "capturing", "needs_info"},
    "ready": {"submitted", "analyzing", "draft"}, "submitted": {"approved", "changed", "needs_info", "declined"}, "needs_info": {"resubmitted", "analyzing"},
    "resubmitted": {"approved", "changed", "needs_info", "declined"}, "approved": {"presented"}, "changed": {"presented"}, "declined": {"closed"}, "presented": {"closed"}, "closed": set(),
}
LOCKED = {"submitted", "resubmitted", "approved", "changed", "declined", "presented", "closed"}
OPEN_FOR_DECISION = {"submitted", "resubmitted"}
OUTCOMES = {"accepted": "Accepted", "wants_more": "Wants more", "thinking": "Thinking about it", "not_trading": "Not trading", "other": "Other"}
DECISIONS = ("approve", "change", "request_info", "decline")
MANAGER_ROLES = rulesvc.MANAGER_ROLES


class TransitionError(ValueError):
    pass


# ---------- permissions ----------
def _perms(me: dict) -> dict:
    return merge_permissions(me.get("feature_permissions"), me.get("role") or "user")


def can_approve(me: dict) -> bool:
    return is_feature_enabled(_perms(me), "manage", "appraisal_approvals")


def can_edit_rules(me: dict) -> bool:
    return is_feature_enabled(_perms(me), "manage", "appraisal_rules")


def can_decide_on(me: dict, appr: dict) -> tuple:
    """Managers with the approvals permission decide. A salesperson never decides their own appraisal unless the permission was granted to
    them explicitly (not just inherited from a manager role they also hold). Super admins may (the audit trail says who)."""
    if not can_approve(me):
        return False, "You do not have appraisal approval permission."
    if str(me.get("_id")) == str(appr.get("user_id")) and me.get("role") != "super_admin":
        explicit = ((me.get("feature_permissions") or {}).get("manage") or {}).get("appraisal_approvals") is True
        if not explicit:
            return False, "You cannot approve your own appraisal. Another manager has to."
    return True, ""


def abilities(me: dict, appr: dict) -> dict:
    """What the signed-in person can do with this appraisal right now; the UI shows exactly these buttons."""
    st = appr.get("status") or "draft"
    ok, why = can_decide_on(me, appr) if st in OPEN_FOR_DECISION else (False, "")
    return {"status": st, "status_label": STATUS_LABELS.get(st, st), "locked": st in LOCKED, "edit": st not in LOCKED, "submit": st in ("draft", "ready", "needs_info"),
            "resubmit": st == "needs_info", "decide": ok, "decide_blocked_reason": why if st in OPEN_FOR_DECISION else "", "present": st in ("approved", "changed"),
            "outcome": st in ("presented", "declined"), "manager": can_approve(me), "edit_rules": can_edit_rules(me)}


def assert_editable(appr: dict):
    if appr.get("status") in LOCKED:
        raise ValueError(f"This appraisal is {STATUS_LABELS.get(appr['status'], appr['status']).lower()}; it cannot be changed right now.")


# ---------- status machine ----------
def can_transition(frm: str, to: str) -> bool:
    return to in TRANSITIONS.get(frm or "draft", set())


async def transition(db, appr: dict, me: dict, to: str, action: str, detail: str = "", meta: Optional[dict] = None, extra: Optional[dict] = None) -> dict:
    frm = appr.get("status") or "draft"
    if not can_transition(frm, to):
        raise TransitionError(f"Cannot go from {STATUS_LABELS.get(frm, frm)} to {STATUS_LABELS.get(to, to)}.")
    now = _now()
    await db[A].update_one({"_id": appr["_id"]}, {"$set": {"status": to, "updated_at": now, **(extra or {})},
                                                  "$push": {"status_history": {"from": frm, "to": to, "by": str(me["_id"]), "by_name": _name(me), "at": now, "action": action}}})
    await audit(db, appr, me, action, detail, frm, to, meta)
    return await db[A].find_one({"_id": appr["_id"]})


# ---------- inputs + calculation ----------
async def gather_inputs(db, appr: dict) -> dict:
    snap = await market.latest_snapshot(db, appr)
    mkt = None
    if snap:
        r = snap.get("result") or {}
        mkt = {"snapshot_id": str(snap["_id"]), "provider": snap.get("provider"), "provider_label": snap.get("provider_label"), "live": snap.get("live"), "badge": snap.get("badge"),
               "estimated_retail": r.get("estimated_retail"), "retail_source": r.get("retail_source"), "retail_label": r.get("retail_label"), "estimated_wholesale": r.get("estimated_wholesale"),
               "median_market_price": r.get("median_market_price"), "avg_market_price": r.get("avg_market_price"), "price_range": r.get("price_range"),
               "confidence": (r.get("confidence") or {}).get("level"), "comps_used": r.get("comps_used"), "listing_count": r.get("listing_count"), "fetched_at": snap.get("fetched_at")}
    ins = await inspection.summary(db, appr)
    cond = {"overall": ins.get("final_overall"), "label": ins.get("final_overall_label"), "confirmed": ins.get("confirmed"), "overridden": ins.get("overridden"),
            "inspection_status": ins.get("status")} if ins else None
    ins_doc = await db["appraisal_inspections"].find_one({"appraisal_id": str(appr["_id"])}, {"run_count": 1, "updated_at": 1})
    eff = await rulesvc.effective(db, appr.get("organization_id"), appr.get("store_id"))
    return {"vehicle": appr.get("vehicle") or {}, "mileage": appr.get("mileage_confirmed"), "condition": cond, "market": mkt, "book_values": appr.get("book_values") or [],
            "customer_expected_value": appr.get("customer_expected_value"), "market_snapshot_id": str(snap["_id"]) if snap else None,
            "inspection_id": str(ins_doc["_id"]) if ins_doc else None, "inspection_run_count": (ins_doc or {}).get("run_count"), "rules_version": eff["version"],
            "rules_source": eff["source"], "rules_id": eff["rules_id"], "rules_snapshot": eff["rules"], "now_year": _now().year,
            "allow_development_basis": development_basis_allowed()}


def development_basis_allowed() -> bool:
    """Mock market data may start a Suggested ACV only where APPRAISAL_ALLOW_DEV_MARKET=1 (preview/dev). Production never sets it, so without a live
    provider the number has to come from a book value or the manager."""
    return (os.environ.get("APPRAISAL_ALLOW_DEV_MARKET") or "").strip() == "1"


def run_engine(inputs: dict) -> dict:
    out = engine.calculate(vehicle=inputs["vehicle"], mileage=inputs["mileage"], condition=inputs["condition"], market=inputs["market"], book_values=inputs["book_values"],
                           customer_expected_value=inputs["customer_expected_value"], rules=inputs["rules_snapshot"], now_year=inputs["now_year"],
                           allow_development_basis=bool(inputs.get("allow_development_basis")))
    out["warnings"] = list(dict.fromkeys(out["warnings"] + rulesvc.double_count_warnings(inputs["rules_snapshot"])))
    return out


def public_calc(c: dict) -> dict:
    inp = c.get("inputs") or {}
    return {"id": str(c["_id"]), "version": c.get("version"), "trigger": c.get("trigger"), "output": c.get("output"), "engine_version": c.get("engine_version"),
            "rules_version": inp.get("rules_version"), "rules_source": inp.get("rules_source"), "market_snapshot_id": inp.get("market_snapshot_id"), "inspection_id": inp.get("inspection_id"),
            "inspection_run_count": inp.get("inspection_run_count"), "condition": inp.get("condition"), "market": inp.get("market"), "mileage": inp.get("mileage"),
            "book_values": inp.get("book_values"), "customer_expected_value": inp.get("customer_expected_value"), "created_by_name": c.get("created_by_name"), "created_at": c.get("created_at")}


async def preview(db, appr: dict) -> dict:
    """Live calculation with today's data and rules. Never stored; what the rep sees before submitting."""
    inputs = await gather_inputs(db, appr)
    out = run_engine(inputs)
    return {"output": out, "rules_version": inputs["rules_version"], "rules_source": inputs["rules_source"], "market_snapshot_id": inputs["market_snapshot_id"],
            "inspection_id": inputs["inspection_id"], "condition": inputs["condition"], "market": inputs["market"], "preview": True}


async def snapshot_calculation(db, appr: dict, me: dict, trigger: str) -> dict:
    """Immutable: a new version each time; the appraisal points at the latest."""
    inputs = await gather_inputs(db, appr)
    out = run_engine(inputs)
    n = await db[CALC].count_documents({"appraisal_id": str(appr["_id"])})
    doc = {"_id": ObjectId(), "appraisal_id": str(appr["_id"]), "contact_id": appr.get("contact_id"), "vehicle_id": appr.get("vehicle_id"), "user_id": appr["user_id"],
           "store_id": appr.get("store_id"), "organization_id": appr.get("organization_id"), "version": n + 1, "trigger": trigger, "inputs": inputs, "output": out,
           "engine_version": engine.ENGINE_VERSION, "created_by": str(me["_id"]), "created_by_name": _name(me), "created_at": _now()}
    await db[CALC].insert_one(doc)
    return doc


async def calculations(db, appr: dict) -> list:
    rows = await db[CALC].find({"appraisal_id": str(appr["_id"])}).sort("version", -1).to_list(50)
    return [public_calc(c) for c in rows]


async def latest_calculation(db, appr: dict) -> Optional[dict]:
    if appr.get("calculation_id"):
        c = await db[CALC].find_one({"_id": _oid(appr["calculation_id"])})
        if c:
            return c
    return await db[CALC].find_one({"appraisal_id": str(appr["_id"])}, sort=[("version", -1)])


# ---------- managers / notifications ----------
async def managers_for(db, appr: dict, exclude_user_id: Optional[str] = None) -> list:
    sid, org = appr.get("store_id"), appr.get("organization_id")
    ors = []
    if sid:
        vals = [sid] + ([ObjectId(sid)] if ObjectId.is_valid(str(sid)) else [])
        ors += [{"store_id": {"$in": vals}}, {"store_ids": {"$in": vals}}]
    if org:
        vals = [org] + ([ObjectId(org)] if ObjectId.is_valid(str(org)) else [])
        ors.append({"organization_id": {"$in": vals}, "role": "org_admin"})
    if not ors:
        return []
    rows = await db.users.find({"$or": ors, "role": {"$in": list(MANAGER_ROLES)}, "status": {"$ne": "deactivated"}},
                               {"name": 1, "first_name": 1, "last_name": 1, "email": 1, "role": 1, "feature_permissions": 1}).to_list(60)
    out = [u for u in rows if can_approve(u) and str(u["_id"]) != str(exclude_user_id or "")]
    return out[:25]


async def _notify(user_id: str, ntype: str, title: str, body: str, link: str, appr: dict, icon: str = "car-sport"):
    try:
        from routers.notifications import create_notification
        from routers.push_notifications import send_push_to_user
        await create_notification(ntype, title, body, user_id=user_id, contact_id=appr.get("contact_id"), contact_name=appr.get("contact_name"), priority="high", link=link)
        await send_push_to_user(user_id, title, body, url=link, icon=icon)
    except Exception as e:
        logger.warning(f"[Appraisal] notification to {user_id} skipped: {e}")


def _money(v) -> str:
    return f"${int(v):,}" if v is not None else "n/a"


async def notify_managers(db, appr: dict, me: dict, resubmitted: bool = False):
    out = appr.get("suggested_acv")
    body = f"{appr.get('contact_name')} · {vehicle_label(appr.get('vehicle') or {})} · Suggested ACV {_money(out)}" + (f" · Customer wants {_money(appr['customer_expected_value'])}" if appr.get("customer_expected_value") else "")
    if appr.get("manager_review_required"):
        body += " · Needs your eyes"
    title = "Trade appraisal resubmitted" if resubmitted else "Trade appraisal ready"
    mgrs = await managers_for(db, appr, exclude_user_id=str(me["_id"]))
    for u in mgrs:
        await _notify(str(u["_id"]), "appraisal_resubmitted" if resubmitted else "appraisal_submitted", title, body, f"/appraisal/desk/{appr['_id']}", appr)
    return [str(u["_id"]) for u in mgrs]


# ---------- relationship intelligence + events ----------
def relationship_summary(appr: dict) -> dict:
    """What Jessi and the contact record need. Normalized numbers only, never provider JSON."""
    ms = appr.get("market_summary") or {}
    gap = (appr["customer_expected_value"] - appr["approved_value"]) if (appr.get("customer_expected_value") and appr.get("approved_value")) else None
    return {"appraisal_id": str(appr["_id"]), "vehicle_id": appr.get("vehicle_id"), "vehicle_label": vehicle_label(appr.get("vehicle") or {}) if appr.get("vehicle") else None, "vin": appr.get("vin"),
            "mileage": appr.get("mileage_confirmed"), "condition": appr.get("condition_final"), "condition_label": rulesvc.CONDITION_LABELS.get(appr.get("condition_final") or "", None),
            "appraised_at": appr.get("submitted_at") or appr.get("created_at"), "market_retail": ms.get("estimated_retail"), "market_provider_label": ms.get("provider_label"), "market_live": ms.get("live"),
            "suggested_acv": appr.get("suggested_acv"), "approved_value": appr.get("approved_value"), "approved_by_name": appr.get("approved_by_name"), "approved_at": appr.get("approved_at"),
            "customer_expected_value": appr.get("customer_expected_value"), "expectation_gap": gap, "outcome": appr.get("outcome"), "outcome_label": OUTCOMES.get(appr.get("outcome") or "", None),
            "status": appr.get("status"), "status_label": STATUS_LABELS.get(appr.get("status") or "", ""), "presented_at": appr.get("presented_at"), "closed_at": appr.get("closed_at"),
            "salesperson": appr.get("user_name"), "is_reappraisal": bool(appr.get("is_reappraisal")), "manager_delta": (appr.get("manager_adjustment") or {}).get("delta"),
            "contact_name": appr.get("contact_name"), "updated_at": _now()}


def merge_context(appr: dict) -> dict:
    """Merge fields for campaigns / AI drafts: {trade_vehicle} {trade_mileage} {trade_appraisal_date} {trade_approved_value} {trade_customer_wants} {trade_gap} {trade_condition} {trade_outcome}."""
    s = relationship_summary(appr)
    d = s.get("appraised_at")
    return {"trade_vehicle": s.get("vehicle_label") or "", "trade_mileage": f"{s['mileage']:,}" if s.get("mileage") is not None else "",
            "trade_appraisal_date": d.strftime("%b %d, %Y") if isinstance(d, datetime) else "", "trade_approved_value": _money(s["approved_value"]) if s.get("approved_value") else "",
            "trade_customer_wants": _money(s["customer_expected_value"]) if s.get("customer_expected_value") else "", "trade_gap": _money(s["expectation_gap"]) if s.get("expectation_gap") else "",
            "trade_condition": s.get("condition_label") or "", "trade_outcome": s.get("outcome_label") or "", "trade_suggested_acv": _money(s["suggested_acv"]) if s.get("suggested_acv") else "",
            "trade_salesperson": s.get("salesperson") or ""}


async def sync_relationship(db, appr: dict):
    s = relationship_summary(appr)
    if appr.get("contact_id") and _oid(appr["contact_id"]):
        await db.contacts.update_one({"_id": ObjectId(appr["contact_id"])}, {"$set": {"trade_appraisal": s}})
    if appr.get("vehicle_id") and _oid(appr["vehicle_id"]):
        await db[V].update_one({"_id": ObjectId(appr["vehicle_id"])}, {"$set": {"last_appraisal": s, "updated_at": _now()}})


async def emit(db, appr: dict, event: str, me: Optional[dict] = None, extra: Optional[dict] = None):
    """trade_appraisal.* events: structured rows for the campaign system / reporting, then the follow-up bridge (campaign triggers + tasks)."""
    doc = {"event": f"trade_appraisal.{event}", "appraisal_id": str(appr["_id"]), "contact_id": appr.get("contact_id"), "vehicle_id": appr.get("vehicle_id"), "user_id": appr.get("user_id"),
           "store_id": appr.get("store_id"), "organization_id": appr.get("organization_id"), "actor_id": str(me["_id"]) if me else None, "context": merge_context(appr),
           "numbers": {"suggested_acv": appr.get("suggested_acv"), "approved_value": appr.get("approved_value"), "customer_expected_value": appr.get("customer_expected_value"),
                       "market_retail": (appr.get("market_summary") or {}).get("estimated_retail")}, **(extra or {}), "created_at": _now()}
    await db[EVT].insert_one(doc)
    try:
        from services.appraisals import followup
        return await followup.on_event(db, appr, event)
    except Exception as e:
        logger.warning(f"[Appraisal] follow-up bridge skipped for {event}: {e}")
        return {}


# ---------- rep actions ----------
def _ready_to_submit(appr: dict):
    v = appr.get("vehicle") or {}
    if not (appr.get("vin") or (v.get("make") and v.get("model"))):
        raise ValueError("Identify the vehicle before submitting.")
    if appr.get("mileage_confirmed") is None:
        raise ValueError("Confirm the mileage before submitting.")


async def submit(db, appr: dict, me: dict) -> dict:
    """Freeze the calculation (rules + market snapshot + inspection + book values of this moment) and hand it to the desk."""
    _ready_to_submit(appr)
    frm = appr.get("status") or "draft"
    resub = frm == "needs_info"
    to = "resubmitted" if resub else "submitted"
    if not can_transition(frm, to):
        raise TransitionError(f"Cannot submit from {STATUS_LABELS.get(frm, frm)}.")
    calc = await snapshot_calculation(db, appr, me, "resubmit" if resub else "submit")
    out = calc["output"]
    inp = calc["inputs"]
    now = _now()
    extra = {"suggested_acv": out["suggested_acv"], "suggested_low": out["suggested_low"], "suggested_high": out["suggested_high"],
             "suggested_range": {"low": out["suggested_low"], "high": out["suggested_high"]} if out["suggested_acv"] is not None else None,
             "calculation_id": str(calc["_id"]), "calculation_version": calc["version"], "rules_version": inp["rules_version"], "rules_source": inp["rules_source"],
             "market_snapshot_id": inp["market_snapshot_id"], "inspection_id": inp["inspection_id"], "condition_final": (inp["condition"] or {}).get("overall"),
             "manager_review_required": out["manager_review_required"], "review_reasons": out["review_reasons"], "submitted_by": str(me["_id"]), "submitted_by_name": _name(me),
             "submitted_at": now, "needs_info_request": None, **({"first_submitted_at": now} if not appr.get("first_submitted_at") else {})}
    detail = f"Suggested ACV {_money(out['suggested_acv'])}" + (f" ({_money(out['suggested_low'])}–{_money(out['suggested_high'])})" if out["suggested_acv"] is not None else "") \
        + f" · rules v{inp['rules_version']} ({inp['rules_source']}) · calc v{calc['version']}" + (" · manager review required" if out["manager_review_required"] else "")
    appr = await transition(db, appr, me, to, "resubmitted" if resub else "submitted", detail, {"calculation_id": str(calc["_id"]), "review_reasons": out["review_reasons"]}, extra)
    await log_activity(db, user_id=appr["user_id"], contact_id=appr["contact_id"], event_type="appraisal_submitted",
                       description=f"{'Resubmitted' if resub else 'Submitted'} {vehicle_label(appr.get('vehicle') or {})} for approval · suggested {_money(out['suggested_acv'])}",
                       metadata={"appraisal_id": str(appr["_id"]), "suggested_acv": out["suggested_acv"], "calculation_version": calc["version"]})
    await emit(db, appr, "resubmitted" if resub else "submitted", me)
    if appr.get("is_reappraisal") and not resub:
        await emit(db, appr, "reappraised", me)
    await sync_relationship(db, appr)
    notified = await notify_managers(db, appr, me, resubmitted=resub)
    await db[A].update_one({"_id": appr["_id"]}, {"$set": {"notified_manager_ids": notified}})
    appr["notified_manager_ids"] = notified
    return appr


async def present(db, appr: dict, me: dict) -> dict:
    if appr.get("status") not in ("approved", "changed"):
        raise TransitionError("Only an approved appraisal can be presented to the customer.")
    appr = await transition(db, appr, me, "presented", "presented", f"Presented {_money(appr.get('approved_value'))} to {appr.get('contact_name')}", None,
                            {"presented_at": _now(), "presented_by": str(me["_id"]), "presented_by_name": _name(me)})
    await log_activity(db, user_id=appr["user_id"], contact_id=appr["contact_id"], event_type="appraisal_presented",
                       description=f"Presented {_money(appr.get('approved_value'))} for {vehicle_label(appr.get('vehicle') or {})}", metadata={"appraisal_id": str(appr["_id"]), "approved_value": appr.get("approved_value")})
    await emit(db, appr, "presented", me)
    await sync_relationship(db, appr)
    return appr


async def record_outcome(db, appr: dict, me: dict, outcome: str, expected_value: Optional[int] = None, note: str = "") -> dict:
    if outcome not in OUTCOMES:
        raise ValueError("Pick what the customer said")
    if appr.get("status") not in ("presented", "declined"):
        raise TransitionError("Present the approved value first, then record what the customer said.")
    now = _now()
    extra = {"outcome": outcome, "outcome_label": OUTCOMES[outcome], "outcome_note": (note or "")[:1000], "outcome_at": now, "outcome_by": str(me["_id"]), "closed_at": now}
    if outcome == "wants_more" and expected_value:
        if not (0 < int(expected_value) < 5_000_000):
            raise ValueError("That amount does not look right")
        extra.update({"customer_expected_value": int(expected_value), "expectation_asked": True, "customer_expected_value_before_outcome": appr.get("customer_expected_value")})
    cev = extra.get("customer_expected_value", appr.get("customer_expected_value"))
    if cev and appr.get("approved_value"):
        extra["expectation_gap_final"] = int(cev) - int(appr["approved_value"])
    detail = OUTCOMES[outcome] + (f" · wants {_money(extra['customer_expected_value'])}" if extra.get("customer_expected_value") else "") + (f" · {note[:80]}" if note else "")
    appr = await transition(db, appr, me, "closed", "outcome_recorded", detail, {"outcome": outcome}, extra)
    await log_activity(db, user_id=appr["user_id"], contact_id=appr["contact_id"], event_type="appraisal_outcome",
                       description=f"{OUTCOMES[outcome]} on {_money(appr.get('approved_value'))} for {vehicle_label(appr.get('vehicle') or {})}" + (f" · wants {_money(appr['customer_expected_value'])}" if outcome == 'wants_more' and appr.get('customer_expected_value') else ""),
                       metadata={"appraisal_id": str(appr["_id"]), "outcome": outcome, "approved_value": appr.get("approved_value"), "customer_expected_value": appr.get("customer_expected_value")})
    res = await emit(db, appr, outcome, me) or {}
    await emit(db, appr, "closed", me)
    if res.get("tags"):
        await audit(db, appr, me, "follow_up_tagged", f"Contact tagged {', '.join(res['tags'])} for lists and tag workflows", meta={"tags": res["tags"]})
    if appr.get("vehicle_id"):
        # Intent, not a completed trade: the vehicle stays "owns" until someone confirms the trade on the vehicle record (or a deal does).
        await db[V].update_one({"_id": _oid(appr["vehicle_id"])}, {"$set": {"trade_intent_status": outcome, "trade_intent_at": now, "trade_intent_appraisal_id": str(appr["_id"]), "updated_at": now}})
    await sync_relationship(db, appr)
    return appr


# ---------- manager actions ----------
async def decide(db, appr: dict, me: dict, action: str, value: Optional[int] = None, reason: str = "") -> dict:
    if action not in DECISIONS:
        raise ValueError("Unknown decision")
    ok, why = can_decide_on(me, appr)
    if not ok:
        raise PermissionError(why)
    if appr.get("status") not in OPEN_FOR_DECISION:
        raise TransitionError(f"This appraisal is {STATUS_LABELS.get(appr.get('status'), appr.get('status')).lower()}, not waiting for a decision.")
    reason = (reason or "").strip()[:1000]
    calc = await latest_calculation(db, appr)
    system = appr.get("suggested_acv")
    now = _now()
    sub_at = appr.get("submitted_at")
    response_s = int((now - sub_at.replace(tzinfo=timezone.utc)).total_seconds()) if isinstance(sub_at, datetime) else None
    dec = {"_id": ObjectId(), "appraisal_id": str(appr["_id"]), "contact_id": appr.get("contact_id"), "user_id": appr.get("user_id"), "store_id": appr.get("store_id"),
           "organization_id": appr.get("organization_id"), "calculation_id": str(calc["_id"]) if calc else None, "calculation_version": (calc or {}).get("version"), "action": action,
           "system_suggested_acv": system, "manager_approved_value": None, "delta": None, "delta_percentage": None, "reason": reason, "manager_id": str(me["_id"]), "manager_name": _name(me),
           "from_status": appr.get("status"), "to_status": None, "submitted_at": sub_at, "decided_at": now, "response_s": response_s}
    extra = {"decision_id": str(dec["_id"]), "decided_at": now}
    if action == "approve":
        if system is None:
            raise ValueError("There is no suggested ACV to approve; enter the value instead.")
        to = "approved"
        dec.update({"manager_approved_value": int(system), "delta": 0, "delta_percentage": 0.0, "to_status": to})
        extra.update({"approved_value": int(system), "approved_by": str(me["_id"]), "approved_by_name": _name(me), "approved_at": now, "manager_adjustment": None, "declined_reason": None})
        detail = f"Approved the suggested {_money(system)}" + (f" · {reason}" if reason else "")
        act_type, act_desc = "appraisal_approved", f"Manager {_name(me)} approved {_money(system)} for {vehicle_label(appr.get('vehicle') or {})}"
    elif action == "change":
        if value is None or not (0 < int(value) < 5_000_000):
            raise ValueError("Enter the approved trade value")
        to = "changed"
        delta = int(value) - int(system) if system is not None else None
        pct = round(delta / system * 100, 2) if (delta is not None and system) else None
        dec.update({"manager_approved_value": int(value), "delta": delta, "delta_percentage": pct, "to_status": to})
        extra.update({"approved_value": int(value), "approved_by": str(me["_id"]), "approved_by_name": _name(me), "approved_at": now, "declined_reason": None,
                      "manager_adjustment": {"system_suggested_acv": system, "manager_approved_value": int(value), "delta": delta, "delta_percentage": pct, "manager_id": str(me["_id"]),
                                             "manager_name": _name(me), "at": now, "reason": reason}})
        detail = f"Approved {_money(value)} (suggested {_money(system)}, {'+' if (delta or 0) >= 0 else '-'}{_money(abs(delta)) if delta is not None else 'n/a'})" + (f" · {reason}" if reason else "")
        act_type, act_desc = "appraisal_approved", f"Manager {_name(me)} approved {_money(value)} for {vehicle_label(appr.get('vehicle') or {})}" + (f" (suggested {_money(system)})" if system is not None else "")
    elif action == "request_info":
        if len(reason) < 3:
            raise ValueError("Tell the salesperson what you need")
        to = "needs_info"
        dec["to_status"] = to
        extra.update({"needs_info_request": {"reason": reason, "by": str(me["_id"]), "by_name": _name(me), "at": now}})
        detail = f"Needs more information: {reason}"
        act_type, act_desc = "appraisal_needs_info", f"Manager {_name(me)} asked for more on {vehicle_label(appr.get('vehicle') or {})}: {reason[:120]}"
    else:
        if len(reason) < 3:
            raise ValueError("Give a reason for declining")
        to = "declined"
        dec["to_status"] = to
        extra.update({"declined_reason": reason, "declined_by": str(me["_id"]), "declined_by_name": _name(me), "declined_at": now})
        detail = f"Declined: {reason}"
        act_type, act_desc = "appraisal_declined", f"Manager {_name(me)} declined the appraisal of {vehicle_label(appr.get('vehicle') or {})}: {reason[:120]}"
    await db[DEC].insert_one(dec)
    appr = await transition(db, appr, me, to, f"decision_{action}", detail, {"decision_id": str(dec["_id"]), "delta": dec.get("delta")}, extra)
    await log_activity(db, user_id=appr["user_id"], contact_id=appr["contact_id"], event_type=act_type, description=act_desc,
                       metadata={"appraisal_id": str(appr["_id"]), "action": action, "approved_value": appr.get("approved_value"), "suggested_acv": system, "reason": reason})
    await emit(db, appr, {"approve": "approved", "change": "approved", "request_info": "needs_info", "decline": "declined"}[action], me, {"decision": action})
    await sync_relationship(db, appr)
    titles = {"approve": ("Trade approved", f"{appr.get('contact_name')} · {vehicle_label(appr.get('vehicle') or {})} · Approved {_money(appr.get('approved_value'))}. Present it when you are ready."),
              "change": ("Trade approved (value changed)", f"{appr.get('contact_name')} · {vehicle_label(appr.get('vehicle') or {})} · Approved {_money(appr.get('approved_value'))} (suggested was {_money(system)})."),
              "request_info": ("Manager needs more", f"{appr.get('contact_name')} · {vehicle_label(appr.get('vehicle') or {})} · {reason[:140]}"),
              "decline": ("Trade appraisal declined", f"{appr.get('contact_name')} · {vehicle_label(appr.get('vehicle') or {})} · {reason[:140]}")}
    if str(appr["user_id"]) != str(me["_id"]):
        t, b = titles[action]
        await _notify(str(appr["user_id"]), f"appraisal_{to}", t, b, f"/appraisal/{appr['_id']}", appr, icon="checkmark-circle" if action in ("approve", "change") else "alert-circle")
    return appr


async def decisions(db, appr: dict) -> list:
    rows = await db[DEC].find({"appraisal_id": str(appr["_id"])}).sort("decided_at", 1).to_list(50)
    return [{"id": str(d["_id"]), **{k: d.get(k) for k in ("action", "system_suggested_acv", "manager_approved_value", "delta", "delta_percentage", "reason", "manager_name", "from_status",
                                                            "to_status", "decided_at", "response_s", "calculation_version")}} for d in rows]


def public_workflow(appr: dict) -> dict:
    """Workflow fields the stepper / desk show. Three numbers, three fields."""
    return {k: appr.get(k) for k in ("suggested_acv", "suggested_low", "suggested_high", "suggested_range", "calculation_id", "calculation_version", "rules_version", "rules_source",
                                     "manager_review_required", "review_reasons", "submitted_by_name", "submitted_at", "first_submitted_at", "approved_value", "approved_by_name", "approved_at",
                                     "manager_adjustment", "needs_info_request", "declined_reason", "declined_by_name", "presented_at", "presented_by_name", "outcome", "outcome_label",
                                     "outcome_note", "outcome_at", "closed_at", "expectation_gap_final", "condition_final", "status_history", "notified_manager_ids")}


# ---------- manager desk ----------
DESK_GROUPS = {"waiting": sorted(OPEN_FOR_DECISION), "sent_back": ["needs_info"], "decided": ["approved", "changed", "declined", "presented", "closed"]}


def _age_s(dt) -> Optional[int]:
    if not isinstance(dt, datetime):
        return None
    dt = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    return max(0, int((_now() - dt).total_seconds()))


def desk_row(a: dict) -> dict:
    row = core.public_appraisal(a)
    row.update({k: a.get(k) for k in ("review_reasons", "submitted_by_name", "first_submitted_at", "manager_adjustment", "declined_by_name", "expectation_gap_final")})
    row["status_label"] = STATUS_LABELS.get(a.get("status") or "", a.get("status"))
    row["waiting_s"] = _age_s(a.get("submitted_at")) if a.get("status") in OPEN_FOR_DECISION else None
    row["expectation_gap"] = (a["customer_expected_value"] - a["suggested_acv"]) if (a.get("customer_expected_value") and a.get("suggested_acv") is not None) else None
    row["market_retail"] = (a.get("market_summary") or {}).get("estimated_retail")
    row["market_live"] = (a.get("market_summary") or {}).get("live")
    return row


async def desk_counts(db, me: dict) -> dict:
    base = {"deleted": {"$ne": True}, **(await core.scope(me))}
    return {g: await db[A].count_documents({**base, "status": {"$in": sts}}) for g, sts in DESK_GROUPS.items()}


async def desk_list(db, me: dict, group: str = "waiting", q: str = "", limit: int = 80) -> dict:
    """The desk manager's queue. Waiting = oldest submission first (nobody waits forever); the rest newest first."""
    import re
    group = group if group in DESK_GROUPS else "waiting"
    base = {"deleted": {"$ne": True}, **(await core.scope(me)), "status": {"$in": DESK_GROUPS[group]}}
    q = (q or "").strip()
    if q:
        rx = {"$regex": re.escape(q), "$options": "i"}
        base["$or"] = [{"contact_name": rx}, {"vin": rx}, {"stock_number": rx}, {"user_name": rx}, {"vehicle.make": rx}, {"vehicle.model": rx}]
    sort = [("submitted_at", 1)] if group == "waiting" else [("updated_at", -1)]
    rows = await db[A].find(base).sort(sort).to_list(limit)
    return {"group": group, "appraisals": [desk_row(a) for a in rows], "counts": await desk_counts(db, me)}


async def desk_detail(db, appr: dict, me: dict) -> dict:
    """Everything the desk needs on one screen: the three numbers, customer wants + gap, condition + confirmed issues, market snapshot + comps,
    book values, the frozen breakdown, rep notes, decisions and the audit trail."""
    out = desk_row(appr)
    out.update(public_workflow(appr))
    out["abilities"] = abilities(me, appr)
    calc = await latest_calculation(db, appr)
    out["calculation"] = public_calc(calc) if calc else None
    out["decisions"] = await decisions(db, appr)
    out["activity"] = await core.activity(db, appr)
    out["media"] = await core.list_media(db, appr)
    out["snapshots"] = await core.list_snapshots(db, appr)
    mk = await market.read(db, appr, me)
    out["market"] = {k: mk.get(k) for k in ("provider", "snapshot", "comparables", "book_values", "match_labels", "history")}
    ins_doc = await db["appraisal_inspections"].find_one({"appraisal_id": str(appr["_id"])}, {"_id": 1})
    out["inspection"] = await inspection.read(db, appr) if ins_doc else None
    if appr.get("vehicle_id"):
        veh = await core.get_vehicle(db, me, appr["vehicle_id"])
        out["vehicle_record"] = core.public_vehicle(veh) if veh else None
        out["history"] = await core.vehicle_appraisals(db, me, appr["vehicle_id"])
    return out
