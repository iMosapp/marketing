"""Vehicles as long-term relationship records (MVP5): cards, detail + chronological appraisal history, value history, ownership / trade-intent,
reappraisal opportunities (no provider calls, ever) and the one-off migration for MVP4's accepted→traded behaviour."""
import logging
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId

from services.appraisals import core, rules as rulesvc
from services.appraisals.core import A, V, _now, _oid, _name, vehicle_label
from utils.activity_log import log_activity

logger = logging.getLogger(__name__)

OWNERSHIP = {"owns": "Currently owns", "traded": "Traded", "sold": "Sold", "no_longer_owns": "No longer owns", "unknown": "Unknown"}
TRADE_INTENT = {"accepted": "Accepted our offer", "wants_more": "Wants more", "thinking": "Thinking about it", "not_trading": "Not trading", "other": "Other"}
REAPPRAISE_DAYS = 90          # value is stale after this many days
REVISIT_DAYS = 7              # wants_more / thinking become an opportunity after a week
OPEN_STATUSES = {"draft", "capturing", "analyzing", "ready", "submitted", "needs_info", "resubmitted", "approved", "changed", "presented"}


def _dt(v) -> Optional[datetime]:
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    return None


def days_since(v) -> Optional[int]:
    d = _dt(v)
    return int((_now() - d).total_seconds() // 86400) if d else None


def mask_vin(vin: Optional[str]) -> Optional[str]:
    return f"••••••{vin[-4:]}" if vin and len(vin) >= 4 else None


def history_entry(a: dict) -> dict:
    """One normalized line of history per appraisal. Numbers only, never provider payloads."""
    ms = a.get("market_summary") or {}
    adj = a.get("manager_adjustment") or {}
    gap = (a["customer_expected_value"] - a["approved_value"]) if (a.get("customer_expected_value") and a.get("approved_value")) else None
    return {"id": str(a["_id"]), "date": a.get("closed_at") or a.get("submitted_at") or a.get("created_at"), "created_at": a.get("created_at"), "status": a.get("status"),
            "status_label": _status_label(a.get("status")), "is_reappraisal": bool(a.get("is_reappraisal")), "mileage": a.get("mileage_confirmed"),
            "market_retail": ms.get("estimated_retail"), "market_provider_label": ms.get("provider_label"), "market_live": ms.get("live"), "market_confidence": ms.get("confidence"),
            "condition": a.get("condition_final"), "condition_label": rulesvc.CONDITION_LABELS.get(a.get("condition_final") or "", None),
            "suggested_acv": a.get("suggested_acv"), "suggested_low": a.get("suggested_low"), "suggested_high": a.get("suggested_high"),
            "approved_value": a.get("approved_value"), "approved_by_name": a.get("approved_by_name"), "manager_delta": adj.get("delta"),
            "customer_expected_value": a.get("customer_expected_value"), "expectation_gap": gap, "outcome": a.get("outcome"), "outcome_label": _outcome_label(a.get("outcome")),
            "outcome_note": a.get("outcome_note"), "declined_reason": a.get("declined_reason"), "salesperson": a.get("user_name"), "user_id": a.get("user_id"),
            "presented_at": a.get("presented_at"), "closed_at": a.get("closed_at"), "trade_confirmed_at": a.get("trade_confirmed_at"), "deal_id": a.get("deal_id")}


def _status_label(s):
    from services.appraisals.workflow import STATUS_LABELS
    return STATUS_LABELS.get(s or "", s)


def _outcome_label(o):
    from services.appraisals.workflow import OUTCOMES
    return OUTCOMES.get(o or "", None)


def _pct(new, old):
    return round((new - old) / old * 100, 1) if old else None


def value_history(history: list) -> dict:
    """Points oldest→newest plus plain-English change lines. A list for now; the series shape is chart-ready."""
    pts = [{"date": h["date"], "appraisal_id": h["id"], "mileage": h["mileage"], "market_retail": h["market_retail"], "suggested_acv": h["suggested_acv"],
            "approved_value": h["approved_value"], "customer_expected_value": h["customer_expected_value"]} for h in history]
    changes = []
    if len(pts) >= 2:
        first, last = pts[0], pts[-1]
        for key, label in (("market_retail", "Market retail"), ("suggested_acv", "Suggested ACV"), ("approved_value", "Dealer approved"), ("customer_expected_value", "Customer wanted")):
            a, b = first.get(key), last.get(key)
            if a and b:
                changes.append({"key": key, "label": label, "from": a, "to": b, "delta": b - a, "pct": _pct(b, a)})
        if first.get("mileage") is not None and last.get("mileage") is not None:
            changes.append({"key": "mileage", "label": "Mileage", "from": first["mileage"], "to": last["mileage"], "delta": last["mileage"] - first["mileage"], "pct": None})
    d0, d1 = (days_since(pts[0]["date"]), days_since(pts[-1]["date"])) if len(pts) >= 2 else (None, None)
    return {"points": pts, "changes": changes, "span_days": (d0 - d1) if d0 is not None and d1 is not None else None}


def opportunity_for(v: dict, last: Optional[dict], open_exists: bool) -> Optional[dict]:
    """POTENTIAL REAPPRAISAL: still owns (or unknown), last appraisal closed, no open appraisal, and either stale (90+ days) or an unfinished
    conversation (wants more / thinking) a week old. Pure: never touches a provider."""
    if not last or open_exists or v.get("ownership_status") not in (None, "owns", "unknown"):
        return None
    if last.get("status") != "closed":
        return None
    d = days_since(last.get("closed_at") or last.get("date"))
    if d is None:
        return None
    first = (v.get("contact_first_name") or "").strip()
    who = f"{first}'s" if first else "This"
    model = (v.get("model") or vehicle_label(v) or "vehicle").strip()
    if d >= REAPPRAISE_DAYS:
        return {"kind": "stale", "days": d, "outcome": last.get("outcome"), "title": f"{who} {model} was appraised {d} days ago. Consider updating the value.", "priority": 2}
    if last.get("outcome") in ("wants_more", "thinking") and d >= REVISIT_DAYS:
        why = "wanted more" if last["outcome"] == "wants_more" else "was still thinking"
        return {"kind": last["outcome"], "days": d, "outcome": last.get("outcome"), "title": f"{who} {model}: {first or 'the customer'} {why} {d} days ago. Worth a call, then a fresh value.", "priority": 1}
    return None


async def _contact_first(db, contact_id: Optional[str]) -> str:
    c = await db.contacts.find_one({"_id": _oid(contact_id)}, {"first_name": 1, "name": 1}) if _oid(contact_id) else None
    return ((c or {}).get("first_name") or ((c or {}).get("name") or "").split(" ")[0] or "").strip()


async def vehicle_card(db, me: dict, v: dict, appraisals: Optional[list] = None) -> dict:
    """What the Contact → Vehicles card shows: no hunting through old appraisals."""
    rows = appraisals if appraisals is not None else await db[A].find({"vehicle_id": str(v["_id"]), "deleted": {"$ne": True}, **(await core.scope(me))}).sort("created_at", -1).to_list(50)
    hist = [history_entry(a) for a in rows]
    last = hist[0] if hist else None
    last_closed = next((h for h in hist if h["status"] == "closed"), None)
    open_exists = any(h["status"] in OPEN_STATUSES for h in hist)
    v2 = dict(v, contact_first_name=await _contact_first(db, v.get("contact_id")))
    card = core.public_vehicle(v)
    card.update({"vin_masked": mask_vin(v.get("vin")), "ownership_label": OWNERSHIP.get(v.get("ownership_status") or "owns", "Unknown"), "trade_intent_status": v.get("trade_intent_status"),
                 "trade_intent_label": TRADE_INTENT.get(v.get("trade_intent_status") or "", None), "trade_confirmed_at": v.get("trade_confirmed_at"), "deal_id": v.get("deal_id"),
                 "first_seen": v.get("created_at"), "last_updated": v.get("updated_at"), "appraisal_count": len(hist), "last": last, "open_appraisal_id": next((h["id"] for h in hist if h["status"] in OPEN_STATUSES), None),
                 "opportunity": opportunity_for(v2, last_closed if last and last["status"] == "closed" else None, open_exists)})
    return card


async def contact_cards(db, me: dict, contact_id: str) -> list:
    """Vehicles with at least one visible appraisal (a vehicle whose only draft was discarded is noise, not a record)."""
    rows = await db[V].find({"contact_id": contact_id, "deleted": {"$ne": True}, **(await core.scope(me))}).sort("created_at", -1).to_list(50)
    cards = [await vehicle_card(db, me, v) for v in rows]
    return [c for c in cards if c["appraisal_count"] or c.get("trade_confirmed_at") or c.get("ownership_updated_at")]


async def vehicle_detail(db, me: dict, v: dict) -> dict:
    rows = await db[A].find({"vehicle_id": str(v["_id"]), "deleted": {"$ne": True}, **(await core.scope(me))}).sort("created_at", 1).to_list(100)
    hist = [history_entry(a) for a in rows]
    card = await vehicle_card(db, me, v, list(reversed(rows)))
    c = await db.contacts.find_one({"_id": _oid(v.get("contact_id"))}, {"first_name": 1, "last_name": 1, "name": 1, "phone": 1}) if _oid(v.get("contact_id")) else None
    card.update({"history": hist, "value_history": value_history([h for h in hist if h["status"] in ("closed", "presented", "approved", "changed", "declined")] or hist),
                 "contact": {"id": v.get("contact_id"), "name": core._contact_name(c) if c else None, "phone": (c or {}).get("phone")}, "ownership_options": OWNERSHIP,
                 "can_appraise": True, "ownership_note": v.get("ownership_note"), "ownership_updated_by_name": v.get("ownership_updated_by_name"), "ownership_updated_at": v.get("ownership_updated_at")})
    return card


async def set_ownership(db, me: dict, v: dict, status: str, note: str = "", deal_id: Optional[str] = None, sold_vehicle_id: Optional[str] = None) -> dict:
    """Manual confirmation of what actually happened to the vehicle. Only this (or a linked deal) may mark it traded/sold; an accepted offer never does."""
    if status not in OWNERSHIP:
        raise ValueError("Pick a valid ownership status")
    now = _now()
    upd = {"ownership_status": status, "ownership_note": (note or "")[:300], "ownership_updated_at": now, "ownership_updated_by": str(me["_id"]), "ownership_updated_by_name": _name(me), "updated_at": now}
    if deal_id is not None:
        upd["deal_id"] = deal_id or None
    if sold_vehicle_id is not None:
        upd["sold_vehicle_id"] = sold_vehicle_id or None
    if status in ("traded", "sold"):
        upd.update({"trade_confirmed_at": now, "trade_confirmed_by": str(me["_id"]), "trade_confirmed_by_name": _name(me)})
    else:
        upd.update({"trade_confirmed_at": None, "trade_confirmed_by": None, "trade_confirmed_by_name": None})
    await db[V].update_one({"_id": v["_id"]}, {"$set": upd})
    last = await db[A].find_one({"vehicle_id": str(v["_id"]), "deleted": {"$ne": True}}, sort=[("created_at", -1)])
    if last:
        a_upd = {"trade_confirmed_at": upd.get("trade_confirmed_at"), "trade_confirmed_by": upd.get("trade_confirmed_by"), "updated_at": now}
        if deal_id is not None:
            a_upd["deal_id"] = deal_id or None
        await db[A].update_one({"_id": last["_id"]}, {"$set": a_upd})
        await core.audit(db, last, me, "ownership_updated", f"{OWNERSHIP[status]}" + (f" · {note[:80]}" if note else ""), meta={"ownership_status": status, "deal_id": deal_id})
        if status in ("traded", "sold"):
            from services.appraisals import workflow
            await workflow.emit(db, last, "trade_confirmed", me, {"ownership_status": status})
    label = vehicle_label(v)
    try:
        from services.intelligence import ingest as intel_ingest
        _c = await db.contacts.find_one({"_id": ObjectId(v["contact_id"])}) if v.get("contact_id") and ObjectId.is_valid(str(v.get("contact_id"))) else None
        if _c:
            await intel_ingest.from_ownership(db, _c, label, status, actor=me, vehicle_id=str(v["_id"]))
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[Appraisals] facts ingest skipped: {e}")
    await log_activity(db, user_id=str(me["_id"]), contact_id=v.get("contact_id"), event_type="trade_confirmed" if status in ("traded", "sold") else "vehicle_ownership_updated",
                       description=(f"Trade confirmed — {label}" if status == "traded" else f"{label}: {OWNERSHIP[status]}") + (f" · {note[:80]}" if note else ""),
                       metadata={"vehicle_id": str(v["_id"]), "ownership_status": status, "deal_id": deal_id})
    return await db[V].find_one({"_id": v["_id"]})


async def opportunities(db, me: dict, limit: int = 50, user_id: Optional[str] = None) -> list:
    """Vehicles worth a fresh value, computed from stored history only. Uses the vehicles.last_appraisal index; no provider calls."""
    q = {"deleted": {"$ne": True}, "ownership_status": {"$in": [None, "owns", "unknown"]}, "last_appraisal.status": "closed", **(await core.scope(me))}
    if user_id:
        q["user_id"] = user_id
    out = []
    async for v in db[V].find(q).sort("last_appraisal.closed_at", 1).limit(400):
        la = v.get("last_appraisal") or {}
        open_exists = await db[A].count_documents({"vehicle_id": str(v["_id"]), "deleted": {"$ne": True}, "status": {"$in": list(OPEN_STATUSES)}}) > 0
        v2 = dict(v, contact_first_name=await _contact_first(db, v.get("contact_id")))
        opp = opportunity_for(v2, {"status": la.get("status"), "closed_at": la.get("closed_at"), "date": la.get("appraised_at"), "outcome": la.get("outcome")}, open_exists)
        if opp:
            out.append({**opp, "vehicle_id": str(v["_id"]), "vehicle_label": vehicle_label(v), "contact_id": v.get("contact_id"), "contact_name": la.get("contact_name") or (v2["contact_first_name"] or None),
                        "appraisal_id": la.get("appraisal_id"), "last_appraised_at": la.get("appraised_at"), "approved_value": la.get("approved_value"), "customer_expected_value": la.get("customer_expected_value"),
                        "outcome_label": la.get("outcome_label"), "salesperson": la.get("salesperson"), "user_id": v.get("user_id"), "mileage": la.get("mileage")})
        if len(out) >= limit:
            break
    out.sort(key=lambda o: (o["priority"], -o["days"]))
    return out


# ---------- MVP4 → MVP5 correction: an accepted offer is intent, not a completed trade ----------
async def migrate_accepted_traded(db) -> dict:
    """Only vehicles flipped to 'traded' by the MVP4 outcome path: ownership traded, no manual/deal confirmation, and the latest appraisal on them
    closed as accepted. Legitimate traded vehicles (confirmed by a person or a deal) are untouched. Idempotent; records a summary in `migrations`."""
    fixed, checked = 0, 0
    async for v in db[V].find({"ownership_status": "traded", "trade_confirmed_at": {"$in": [None]}, "deleted": {"$ne": True}}):
        checked += 1
        last = await db[A].find_one({"vehicle_id": str(v["_id"]), "deleted": {"$ne": True}}, sort=[("created_at", -1)])
        if last and last.get("outcome") == "accepted" and not v.get("ownership_updated_by"):
            await db[V].update_one({"_id": v["_id"]}, {"$set": {"ownership_status": "owns", "trade_intent_status": "accepted", "trade_intent_at": last.get("outcome_at"),
                                                               "migration_note": "MVP5: accepted offer kept as intent; ownership reset to owns until a trade is confirmed", "updated_at": _now()}})
            fixed += 1
    await db.migrations.update_one({"_id": "appraisal_accepted_not_traded"}, {"$set": {"ran_at": _now(), "checked": checked, "fixed": fixed}, "$inc": {"runs": 1}}, upsert=True)
    logger.info(f"[Appraisal] migration accepted→intent: checked {checked}, fixed {fixed}")
    return {"checked": checked, "fixed": fixed}
