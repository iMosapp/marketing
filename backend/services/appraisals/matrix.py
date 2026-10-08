"""Validation matrix: a deliberate list of real vehicles through BOTH live providers, run in the background where the keys live (production),
one `market_provider_comparisons` row per vehicle (purpose=matrix) and one run document the Provider Lab polls. Nothing here touches an appraisal,
a snapshot-of-record or the engine, and nothing is averaged: every number stays the provider's own."""
import asyncio
import logging
import statistics
from datetime import timezone
from typing import Optional

from bson import ObjectId

from services.appraisals import market, market_providers as mp
from services.appraisals import providers as identity
from services.appraisals.core import _now, _name, scope

logger = logging.getLogger(__name__)

RUNS = "market_provider_matrix_runs"
MAX_ROWS = 25
PAUSE_S = 1.0


def plan(vehicles: list) -> dict:
    mc, va = mp.PROVIDERS["marketcheck"], mp.PROVIDERS["vinaudit"]
    per_vehicle = (mc.calls_per_fetch if mc.configured() else 0) + (len(mp.VA_VALUE_TYPES) if va.configured() else 0)
    return {"vehicles": len(vehicles), "marketcheck": "configured" if mc.configured() else "not configured (skipped)", "vinaudit": "configured" if va.configured() else "not configured (skipped)",
            "calls_per_vehicle": per_vehicle, "total_calls": per_vehicle * len(vehicles)}


def clean_vehicles(raw: list) -> list:
    out = []
    for r in raw or []:
        if not isinstance(r, dict):
            continue
        vin = str(r.get("vin") or "").strip().upper()
        if vin and len(vin) != 17:
            raise ValueError(f"'{vin}' is not a 17-character VIN")
        try:
            year = int(r["year"]) if r.get("year") else None
            mileage = int(str(r["mileage"]).replace(",", "")) if r.get("mileage") not in (None, "") else None
        except (TypeError, ValueError):
            raise ValueError(f"Bad year or mileage on {vin or 'a row'}")
        zip_code = str(r.get("zip") or "").strip() or None
        if zip_code and not zip_code.isdigit():
            raise ValueError(f"Bad ZIP on {vin or 'a row'}")
        v = {"vin": vin or None, "year": year, "make": (r.get("make") or "").strip() or None, "model": (r.get("model") or "").strip() or None, "trim": (r.get("trim") or "").strip() or None,
             "mileage": mileage, "zip": zip_code}
        if v["vin"] or (v["year"] and v["make"] and v["model"]):
            out.append(v)
    if not out:
        raise ValueError("Give at least one vehicle: a VIN, or year, make and model")
    return out[:MAX_ROWS]


def _band(card: dict) -> str:
    pr = card.get("price_range") or {}
    return f"{pr.get('low', '')}-{pr.get('high', '')}" if pr else ""


def row_for(comp: dict, vehicle: dict, mileage: Optional[int], zip_code: Optional[str]) -> dict:
    cards = {c["provider"]: c for c in comp.get("providers") or []}
    mc, va, d = cards.get("marketcheck", {}), cards.get("vinaudit", {}), comp.get("difference") or {}
    return {"vin": vehicle.get("vin"), "year": vehicle.get("year"), "make": vehicle.get("make"), "model": vehicle.get("model"), "trim": vehicle.get("trim"), "mileage": mileage, "zip": zip_code,
            "mc": {"status": mc.get("status"), "retail": mc.get("estimated_retail"), "comps_median": mc.get("comps_median"), "comps_avg": mc.get("comps_average"), "range": _band(mc),
                   "comps": mc.get("comps_count"), "confidence": (mc.get("confidence") or {}).get("level"), "ms": mc.get("response_ms"), "calls": mc.get("calls") or 0, "error": mc.get("error"), "cached": bool(mc.get("cached"))},
            "va": {"status": va.get("status"), "retail": va.get("estimated_retail"), "trade_in": va.get("estimated_trade_in"), "range": _band(va), "records": va.get("comps_count"),
                   "certainty": va.get("provider_certainty"), "confidence": (va.get("confidence") or {}).get("level"), "ms": va.get("response_ms"), "calls": va.get("calls") or 0, "error": va.get("error"), "cached": bool(va.get("cached"))},
            "diff_dollars": d.get("dollars") if d.get("available") else None, "diff_percent": d.get("percent") if d.get("available") else None,
            "calls_total": comp.get("calls_total") or 0, "comparison_id": comp.get("id")}


def summary(rows: list, errors: list) -> dict:
    diffs = [r["diff_dollars"] for r in rows if r.get("diff_dollars") is not None]
    pcts = [r["diff_percent"] for r in rows if r.get("diff_percent") is not None]
    mc_ok = sum(1 for r in rows if r["mc"].get("retail"))
    va_ok = sum(1 for r in rows if r["va"].get("retail"))
    return {"vehicles": len(rows), "skipped": len(errors), "calls_total": sum(int(r.get("calls_total") or 0) for r in rows),
            "marketcheck_answered": mc_ok, "vinaudit_answered": va_ok, "both_answered": len(diffs),
            "marketcheck_higher": sum(1 for x in diffs if x > 0), "vinaudit_higher": sum(1 for x in diffs if x < 0),
            "median_abs_gap": round(statistics.median(abs(x) for x in diffs)) if diffs else None, "median_abs_percent": round(statistics.median(abs(x) for x in pcts), 1) if pcts else None,
            "mc_median_ms": round(statistics.median(r["mc"]["ms"] for r in rows if r["mc"].get("ms"))) if any(r["mc"].get("ms") for r in rows) else None,
            "va_median_ms": round(statistics.median(r["va"]["ms"] for r in rows if r["va"].get("ms"))) if any(r["va"].get("ms") for r in rows) else None,
            "provider_errors": [{"vin": r.get("vin"), "provider": p, "error": r[p]["error"]} for r in rows for p in ("mc", "va") if r[p].get("error")]}


def public_run(d: dict) -> dict:
    return {"id": str(d["_id"]), "status": d.get("status"), "zip": d.get("zip"), "radius": d.get("radius"), "force": bool(d.get("force")), "plan": d.get("plan"), "by_name": d.get("by_name"),
            "total": len(d.get("vehicles") or []), "done": len(d.get("rows") or []) + len(d.get("errors") or []), "rows": d.get("rows") or [], "errors": d.get("errors") or [],
            "summary": d.get("summary"), "created_at": d.get("created_at"), "finished_at": d.get("finished_at"), "last_error": d.get("last_error")}


async def start(db, me: dict, *, vehicles: list, zip_code: str, radius: Optional[int], force: bool) -> dict:
    """Validate, write the run, kick the worker, return at once; the Lab polls `get`."""
    vs = clean_vehicles(vehicles)
    if not (zip_code or "").strip().isdigit() or len(zip_code.strip()) != 5:
        raise ValueError("A 5-digit default ZIP is required")
    p = plan(vs)
    if p["total_calls"] == 0:
        raise ValueError("No live provider key is installed on this server, so there is nothing to run. Keys live in the backend secrets.")
    running = await db[RUNS].find_one({"status": "running", "user_id": str(me["_id"])})
    if running and (_now() - running["updated_at"].replace(tzinfo=timezone.utc)).total_seconds() < 600:
        raise ValueError("A matrix is already running for you. Let it finish first.")
    now = _now()
    doc = {"_id": ObjectId(), "user_id": str(me["_id"]), "by_name": _name(me), "store_id": str(me.get("store_id")) if me.get("store_id") else None, "organization_id": str(me.get("organization_id")) if me.get("organization_id") else None,
           "status": "running", "zip": zip_code.strip(), "radius": radius, "force": bool(force), "plan": p, "vehicles": vs, "rows": [], "errors": [], "summary": None,
           "created_at": now, "updated_at": now, "finished_at": None, "last_error": None}
    await db[RUNS].insert_one(doc)
    asyncio.create_task(_work(db, me, doc))
    logger.info(f"[Matrix] run {doc['_id']} started by {doc['by_name']}: {p}")
    return public_run(doc)


async def _work(db, me: dict, doc: dict):
    rows, errors = [], []
    try:
        for v in doc["vehicles"]:
            vehicle = {k: v.get(k) for k in ("vin", "year", "make", "model", "trim")}
            if vehicle["vin"] and not (vehicle["year"] and vehicle["make"] and vehicle["model"]):
                try:
                    dec = await identity.decode_vin(db, vehicle["vin"])
                    vehicle.update({k: dec.get(k) for k in ("year", "make", "model", "trim") if dec.get(k)})
                except Exception as e:  # noqa: BLE001
                    errors.append({"vin": vehicle["vin"], "error": f"VIN decode failed ({e}); add year, make and model"})
                    await db[RUNS].update_one({"_id": doc["_id"]}, {"$set": {"errors": errors, "updated_at": _now()}})
                    continue
            zip_code = v.get("zip") or doc["zip"]
            try:
                comp = await market.compare(db, me, vehicle=vehicle, mileage=v.get("mileage"), zip_code=zip_code, radius=doc.get("radius"), force=doc.get("force"), purpose="matrix")
                rows.append(row_for(comp, vehicle, v.get("mileage"), zip_code))
            except Exception as e:  # noqa: BLE001
                errors.append({"vin": vehicle.get("vin"), "error": str(e)[:300]})
            await db[RUNS].update_one({"_id": doc["_id"]}, {"$set": {"rows": rows, "errors": errors, "updated_at": _now()}})
            await asyncio.sleep(PAUSE_S)
        await db[RUNS].update_one({"_id": doc["_id"]}, {"$set": {"status": "done", "summary": summary(rows, errors), "finished_at": _now(), "updated_at": _now()}})
        logger.info(f"[Matrix] run {doc['_id']} done: {len(rows)} rows, {len(errors)} skipped")
    except Exception as e:  # noqa: BLE001
        logger.error(f"[Matrix] run {doc['_id']} failed: {e}")
        await db[RUNS].update_one({"_id": doc["_id"]}, {"$set": {"status": "failed", "last_error": str(e)[:300], "summary": summary(rows, errors), "finished_at": _now(), "updated_at": _now()}})


async def get(db, me: dict, run_id: str) -> Optional[dict]:
    if not ObjectId.is_valid(run_id):
        return None
    d = await db[RUNS].find_one({"_id": ObjectId(run_id), **(await scope(me))})
    return public_run(d) if d else None


async def recent(db, me: dict, limit: int = 5) -> list:
    rows = await db[RUNS].find(await scope(me), {"rows": 0, "vehicles": 0}).sort("created_at", -1).to_list(max(1, min(limit, 20)))
    return [{**public_run({**d, "rows": [], "vehicles": []}), "total": d.get("plan", {}).get("vehicles", 0), "done": d.get("plan", {}).get("vehicles", 0) if d.get("status") != "running" else None} for d in rows]
