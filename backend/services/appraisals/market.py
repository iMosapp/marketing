"""Market analysis (MVP3): one normalized snapshot per fetch (never overwritten; a refresh adds a new one and the appraisal points at the latest),
comparables with I'm On Social's own match quality, a confidence read, and manual book values. No ACV here: that is MVP4."""
import asyncio
import json
import logging
import os
import re
import statistics
from datetime import datetime, timezone, timedelta
from typing import Optional

from bson import ObjectId

from services.appraisals import market_providers as mp
from services.appraisals.core import A, _now, _oid, _name, audit
from utils.image_storage import put_object

logger = logging.getLogger(__name__)

SNAP, COMP, USAGE = "vehicle_market_snapshots", "vehicle_comparables", "market_provider_usage"
CACHE_HOURS = 24
MONTHLY_CAP_DEFAULT = 450  # free tier is 500 calls / month; keep headroom
BOOK_SOURCES = {"black_book": "Black Book", "mmr": "Manheim MMR", "jd_power": "J.D. Power (NADA)", "kbb": "Kelley Blue Book", "galves": "Galves", "other": "Other"}
VALUE_TYPES = {"wholesale": "Wholesale", "retail": "Retail", "trade_in": "Trade-in"}
MATCH_LABELS = {"exact": "EXACT MATCH", "strong": "STRONG MATCH", "close": "CLOSE MATCH", "loose": "LOOSE MATCH"}
MATCH_ORDER = ("exact", "strong", "close", "loose")


def _month() -> str:
    return _now().strftime("%Y-%m")


def _norm(s: Optional[str]) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


# ---------- I'm On Social calculations (not market data) ----------
def match_quality(target: dict, listing: dict) -> dict:
    """Score 0-100 from year, trim, mileage, distance and certification. EXACT >= 90, STRONG >= 70, CLOSE >= 50, else LOOSE."""
    score, why = 100, []
    ty, ly = target.get("year"), listing.get("year")
    if ty and ly:
        d = abs(int(ty) - int(ly))
        if d == 0:
            why.append("Same model year")
        elif d == 1:
            score -= 15
            why.append(f"{ly} vs your {ty}")
        elif d == 2:
            score -= 30
            why.append(f"Two model years off ({ly})")
        else:
            score -= 50
            why.append(f"{d} model years off")
    tt, lt = _norm(target.get("trim")), _norm(listing.get("trim"))
    if tt and lt and tt == lt:
        why.append(f"Same trim ({listing.get('trim')})")
    elif not tt or not lt:
        score -= 10
        why.append("Trim not confirmed on one side")
    else:
        score -= 20
        why.append(f"Different trim ({listing.get('trim')} vs {target.get('trim')})")
    tm, lm = target.get("mileage"), listing.get("mileage")
    if tm is not None and lm is not None:
        pct = abs(int(lm) - int(tm)) / max(int(tm), 1000)
        if pct <= 0.10:
            why.append("Mileage within 10%")
        elif pct <= 0.25:
            score -= 10
            why.append(f"Mileage {int(pct * 100)}% apart")
        elif pct <= 0.50:
            score -= 20
            why.append(f"Mileage {int(pct * 100)}% apart")
        else:
            score -= 30
            why.append(f"Mileage {int(pct * 100)}% apart")
    else:
        score -= 10
        why.append("Mileage unknown")
    dist = listing.get("distance_mi")
    if dist is not None:
        if dist <= 50:
            pass
        elif dist <= 100:
            score -= 5
            why.append(f"{int(dist)} mi away")
        else:
            score -= 10
            why.append(f"{int(dist)} mi away")
    if listing.get("is_certified"):
        score -= 5
        why.append("Certified pre-owned (asking price runs higher)")
    score = max(0, score)
    q = "exact" if score >= 90 else "strong" if score >= 70 else "close" if score >= 50 else "loose"
    return {"quality": q, "label": MATCH_LABELS[q], "score": score, "why": why}


def confidence(prediction: Optional[dict], comps: list, num_found: int) -> dict:
    """How much to trust the snapshot. Reasons are written for the rep, not the engineer."""
    score, reasons = 0, []
    if prediction and prediction.get("predicted_retail"):
        score += 30
        reasons.append(f"Price prediction available ({prediction.get('model') or 'model'})")
    else:
        reasons.append("No price prediction; estimate comes from comparables")
    good = [c for c in comps if c["match"]["quality"] in ("exact", "strong") and c.get("price")]
    priced = [c for c in comps if c.get("price")]
    if len(good) >= 5:
        score += 35
        reasons.append(f"{len(good)} exact or strong matches")
    elif len(good) >= 3:
        score += 25
        reasons.append(f"{len(good)} exact or strong matches")
    elif len(good) >= 1:
        score += 15
        reasons.append(f"Only {len(good)} exact or strong match{'es' if len(good) > 1 else ''}")
    else:
        reasons.append("No exact or strong matches nearby")
    if len(priced) >= 10:
        score += 15
    elif len(priced) >= 5:
        score += 10
    elif len(priced) >= 1:
        score += 5
    reasons.append(f"{len(priced)} priced comparables of {num_found} listings in range" if priced else "No priced comparables")
    if len(priced) >= 3:
        prices = [c["price"] for c in priced]
        spread = statistics.pstdev(prices) / max(statistics.mean(prices), 1)
        if spread < 0.08:
            score += 20
            reasons.append("Asking prices are tightly grouped")
        elif spread < 0.15:
            score += 12
            reasons.append("Asking prices are fairly consistent")
        elif spread < 0.25:
            score += 5
            reasons.append("Asking prices vary quite a bit")
        else:
            reasons.append("Asking prices are all over the place")
    level = "high" if score >= 75 else "medium" if score >= 45 else "low"
    return {"level": level, "score": min(100, score), "reasons": reasons}


def _summarize(prediction: Optional[dict], comps: list, stats: Optional[dict], num_found: int, mileage: Optional[int], provider: mp.MarketDataProvider, notes: list) -> dict:
    priced = [c for c in comps if c.get("price")]
    prices = sorted(c["price"] for c in priced)
    good = sorted(c["price"] for c in priced if c["match"]["quality"] in ("exact", "strong"))
    basis = good if len(good) >= 3 else prices
    med = int(statistics.median(basis)) if basis else None
    if prediction and prediction.get("predicted_retail"):
        retail, retail_source, retail_label = prediction["predicted_retail"], ("mock_model" if not provider.live else "marketcheck_price"), prediction.get("model")
    elif med is not None:
        retail, retail_source, retail_label = med, "comps_median", f"Median of {len(basis)} {'exact/strong' if basis is good else ''} comparables".replace("  ", " ")
    else:
        retail, retail_source, retail_label = None, None, None
    wholesale = (prediction or {}).get("estimated_wholesale")
    miles = [c["mileage"] for c in comps if c.get("mileage") is not None]
    doms = [c["dom"] for c in comps if c.get("dom") is not None]
    avg_miles = int(statistics.mean(miles)) if miles else (stats or {}).get("miles", {}).get("mean")
    counts = {q: sum(1 for c in comps if c["match"]["quality"] == q) for q in MATCH_ORDER}
    return {"estimated_retail": retail, "retail_source": retail_source, "retail_label": retail_label,
            "estimated_wholesale": wholesale, "wholesale_source": "mock_model" if wholesale and not provider.live else None,
            "msrp": (prediction or {}).get("msrp"),
            "price_range": {"low": basis[len(basis) // 4], "high": basis[(3 * len(basis)) // 4]} if len(basis) >= 4 else ({"low": basis[0], "high": basis[-1]} if basis else None),
            "price_range_basis": ("exact/strong comparables" if basis is good and good else "all comparables") if basis else None,
            "avg_market_price": int(statistics.mean(prices)) if prices else (stats or {}).get("price", {}).get("mean"),
            "median_market_price": int(statistics.median(prices)) if prices else (stats or {}).get("price", {}).get("median"),
            "price_min": prices[0] if prices else None, "price_max": prices[-1] if prices else None,
            "price_stddev": int(statistics.pstdev(prices)) if len(prices) >= 2 else None,
            "listing_count": num_found, "comps_returned": len(comps), "comps_used": len(priced), "match_counts": counts,
            "avg_dom": int(statistics.mean(doms)) if doms else (stats or {}).get("dom", {}).get("mean"),
            "median_dom": int(statistics.median(doms)) if doms else (stats or {}).get("dom", {}).get("median"),
            "avg_miles": avg_miles, "mileage_vs_market": (int(mileage) - int(avg_miles)) if (mileage is not None and avg_miles is not None) else None,
            "confidence": confidence(prediction, comps, num_found), "notes": notes}


# ---------- lookups ----------
async def resolve_zip(db, appr: dict, me: dict) -> dict:
    """Appraisal's own ZIP first (remembered per appraisal), then the store's, then the rep's profile."""
    if appr.get("market_zip"):
        return {"zip": appr["market_zip"], "zip_source": "appraisal"}
    if appr.get("store_id"):
        st = await db.stores.find_one({"_id": _oid(appr["store_id"])}, {"zip_code": 1, "zip": 1, "name": 1})
        z = (st or {}).get("zip_code") or (st or {}).get("zip")
        if z and re.fullmatch(r"\d{5}", str(z).strip()[:5]):
            return {"zip": str(z).strip()[:5], "zip_source": "store", "store_name": (st or {}).get("name")}
    for k in ("zip_code", "zip", "postal_code"):
        z = me.get(k)
        if z and re.fullmatch(r"\d{5}", str(z).strip()[:5]):
            return {"zip": str(z).strip()[:5], "zip_source": "profile"}
    return {"zip": None, "zip_source": None}


async def latest_snapshot(db, appr: dict) -> Optional[dict]:
    return await db[SNAP].find_one({"appraisal_id": str(appr["_id"]), "is_latest": True})


def public_snapshot(s: dict) -> dict:
    return {"id": str(s["_id"]), "appraisal_id": s.get("appraisal_id"), "provider": s.get("provider"), "provider_label": s.get("provider_label"), "live": s.get("live"),
            "badge": s.get("badge"), "requested": s.get("requested"), "result": s.get("result"), "prediction": s.get("prediction"), "stats": s.get("stats"),
            "fetched_at": s.get("fetched_at"), "expires_at": s.get("expires_at"), "is_latest": s.get("is_latest"), "fetched_by_name": s.get("fetched_by_name"),
            "calls": s.get("calls"), "quota": s.get("quota")}


def public_comp(c: dict) -> dict:
    out = {k: c.get(k) for k in mp.LISTING_FIELDS}
    out.update({"id": str(c["_id"]), "snapshot_id": c.get("snapshot_id"), "match": c.get("match"), "rank": c.get("rank"), "live": c.get("live")})
    return out


async def comparables_for(db, snap: dict) -> list:
    rows = await db[COMP].find({"snapshot_id": str(snap["_id"])}).sort("rank", 1).to_list(mp.MAX_ROWS)
    return [public_comp(c) for c in rows]


def public_book_values(appr: dict) -> list:
    return [{"id": b.get("id"), "source": b.get("source"), "source_label": b.get("source_label") or BOOK_SOURCES.get(b.get("source") or "", "Other"),
             "value_type": b.get("value_type"), "value_type_label": VALUE_TYPES.get(b.get("value_type") or "", ""), "value": b.get("value"), "note": b.get("note") or "",
             "entered_by": b.get("entered_by"), "entered_by_name": b.get("entered_by_name"), "entered_at": b.get("entered_at"), "updated_at": b.get("updated_at")}
            for b in (appr.get("book_values") or [])]


async def usage(db, provider: mp.MarketDataProvider) -> dict:
    row = await db[USAGE].find_one({"provider": provider.name, "month": _month()}) or {}
    cap = int((os.environ.get("MARKETCHECK_MONTHLY_CAP") or MONTHLY_CAP_DEFAULT)) if provider.live else None
    return {"provider": provider.name, "month": _month(), "calls": row.get("calls") or 0, "snapshots": row.get("snapshots") or 0, "cap": cap,
            "quota_remaining": row.get("last_quota_remaining"), "rate_remaining": row.get("last_rate_remaining"), "last_at": row.get("updated_at"),
            "blocked_until": row.get("blocked_until")}


async def summary(db, appr: dict) -> Optional[dict]:
    """Short form for the detail payload / review row / Jessi."""
    s = await latest_snapshot(db, appr)
    if not s:
        return None
    r = s.get("result") or {}
    return {"snapshot_id": str(s["_id"]), "provider": s.get("provider"), "provider_label": s.get("provider_label"), "live": s.get("live"), "badge": s.get("badge"),
            "estimated_retail": r.get("estimated_retail"), "estimated_wholesale": r.get("estimated_wholesale"), "comps_used": r.get("comps_used"),
            "listing_count": r.get("listing_count"), "confidence": (r.get("confidence") or {}).get("level"), "fetched_at": s.get("fetched_at"),
            "book_values": len(appr.get("book_values") or [])}


async def read(db, appr: dict, me: dict) -> dict:
    prov = mp.active()
    snap = await latest_snapshot(db, appr)
    hist = await db[SNAP].find({"appraisal_id": str(appr["_id"])}, {"fetched_at": 1, "provider_label": 1, "live": 1, "result.estimated_retail": 1, "result.comps_used": 1, "requested.zip": 1}).sort("fetched_at", -1).to_list(20)
    return {"provider": {"name": prov.name, "label": prov.label, "live": prov.live, "badge": prov.badge},
            "zip": {**(await resolve_zip(db, appr, me)), "radius": appr.get("market_radius") or mp.DEFAULT_RADIUS},
            "snapshot": public_snapshot(snap) if snap else None, "comparables": await comparables_for(db, snap) if snap else [],
            "history": [{"id": str(h["_id"]), "fetched_at": h.get("fetched_at"), "provider_label": h.get("provider_label"), "live": h.get("live"),
                         "estimated_retail": (h.get("result") or {}).get("estimated_retail"), "comps_used": (h.get("result") or {}).get("comps_used"), "zip": (h.get("requested") or {}).get("zip")} for h in hist],
            "book_values": public_book_values(appr), "book_sources": BOOK_SOURCES, "value_types": VALUE_TYPES, "match_labels": MATCH_LABELS,
            "usage": await usage(db, prov), "mileage": appr.get("mileage_confirmed"), "vehicle": appr.get("vehicle")}


# ---------- refresh ----------
def _target(appr: dict) -> dict:
    v = appr.get("vehicle") or {}
    if not (v.get("year") and v.get("make") and v.get("model")):
        raise ValueError("Market data needs at least the year, make and model. Finish the vehicle step first.")
    return {"vin": appr.get("vin") or v.get("vin"), "year": int(v["year"]), "make": v["make"], "model": v["model"], "trim": v.get("trim") or v.get("series"),
            "mileage": appr.get("mileage_confirmed")}


async def _store_raw(appr: dict, sid: ObjectId, raw: dict) -> dict:
    path = f"appraisals/{appr['user_id']}/{appr['_id']}/market/{sid}.json"
    try:
        await asyncio.to_thread(put_object, path, json.dumps(raw, default=str).encode(), "application/json")
        return {"raw_ref": path, "raw_inline": None}
    except Exception as e:
        logger.warning(f"[Market] raw payload not stored in object storage, kept inline: {e}")
        return {"raw_ref": None, "raw_inline": raw}


async def _guard_monthly(db, provider: mp.MarketDataProvider):
    if not provider.live:
        return
    u = await usage(db, provider)
    if u.get("blocked_until") and u["blocked_until"].replace(tzinfo=timezone.utc) > _now():
        raise mp.MarketQuotaExceeded("The MarketCheck monthly quota is used up. Market data comes back when the quota resets.", None, True)
    if u["cap"] is not None and u["calls"] + 2 > u["cap"]:
        raise mp.MarketQuotaExceeded(f"This month's MarketCheck budget ({u['cap']} calls) is spent. It resets on the 1st; ask an admin to raise MARKETCHECK_MONTHLY_CAP.", None, True)


async def refresh(db, appr: dict, me: dict, *, zip_code: Optional[str] = None, radius: Optional[int] = None, force: bool = False) -> dict:
    """Fetch (or reuse within 24h) market data for this appraisal. Each fetch is a NEW snapshot; older ones stay for the audit trail."""
    target = _target(appr)
    z = (zip_code or "").strip()[:5] or (await resolve_zip(db, appr, me))["zip"]
    if not z or not re.fullmatch(r"\d{5}", z):
        raise ValueError("Give me a 5-digit ZIP for the market search (the store has none on file).")
    rad = int(radius or appr.get("market_radius") or mp.DEFAULT_RADIUS)
    rad = max(10, min(rad, 500))
    prov = mp.active()
    dealer_type = (os.environ.get("MARKET_DEALER_TYPE") or "franchise").lower()
    dealer_type = dealer_type if dealer_type in mp.DEALER_TYPES else "franchise"
    requested = {**target, "zip": z, "radius": rad, "dealer_type": dealer_type, "car_type": "used", "provider": prov.name}
    latest = await latest_snapshot(db, appr)
    if latest and not force and latest.get("requested") == requested and latest.get("fetched_at") and latest["fetched_at"].replace(tzinfo=timezone.utc) > _now() - timedelta(hours=CACHE_HOURS):
        return {"snapshot": latest, "cached": True}
    mp.check_rate(str(me["_id"]), appr.get("store_id"))
    await _guard_monthly(db, prov)
    try:
        res = await prov.fetch(vin=target["vin"], year=target["year"], make=target["make"], model=target["model"], trim=target["trim"], mileage=target["mileage"],
                               zip_code=z, radius=rad, dealer_type=dealer_type)
    except mp.MarketQuotaExceeded as e:
        if e.monthly:
            await db[USAGE].update_one({"provider": prov.name, "month": _month()}, {"$set": {"blocked_until": _now() + timedelta(hours=6), "updated_at": _now()}}, upsert=True)
        await audit(db, appr, me, "market_fetch_failed", str(e)[:200], meta={"provider": prov.name, "quota": True})
        raise
    except mp.MarketUnavailable as e:
        await audit(db, appr, me, "market_fetch_failed", str(e)[:200], meta={"provider": prov.name})
        raise
    now = _now()
    sid = ObjectId()
    comps = []
    for l in res["listings"]:
        if l.get("make") and _norm(l["make"]) != _norm(target["make"]):
            continue
        comps.append({**l, "match": match_quality(target, l)})
    comps.sort(key=lambda c: (-c["match"]["score"], c.get("distance_mi") if c.get("distance_mi") is not None else 999, c.get("price") or 0))
    result = _summarize(res.get("prediction"), comps, res.get("stats"), res.get("num_found") or 0, target["mileage"], prov, res.get("notes") or [])
    raw_bits = await _store_raw(appr, sid, res.get("raw") or {})
    doc = {"_id": sid, "appraisal_id": str(appr["_id"]), "vehicle_id": appr.get("vehicle_id"), "contact_id": appr.get("contact_id"), "user_id": appr["user_id"],
           "store_id": appr.get("store_id"), "organization_id": appr.get("organization_id"), "provider": prov.name, "provider_label": prov.label, "live": prov.live,
           "badge": prov.badge, "requested": requested, "prediction": res.get("prediction"), "stats": res.get("stats"), "result": result, "quota": res.get("quota") or {},
           "calls": res.get("calls") or 0, **raw_bits, "fetched_at": now, "expires_at": now + timedelta(hours=CACHE_HOURS), "is_latest": True, "superseded_by": None,
           "previous_snapshot_id": str(latest["_id"]) if latest else None, "fetched_by": str(me["_id"]), "fetched_by_name": _name(me)}
    await db[SNAP].insert_one(doc)
    if latest:
        await db[SNAP].update_one({"_id": latest["_id"]}, {"$set": {"is_latest": False, "superseded_by": str(sid)}})
    if comps:
        await db[COMP].insert_many([{"_id": ObjectId(), "snapshot_id": str(sid), "appraisal_id": str(appr["_id"]), "user_id": appr["user_id"], "store_id": appr.get("store_id"),
                                     "organization_id": appr.get("organization_id"), "provider": prov.name, "live": prov.live, "rank": i + 1, "fetched_at": now, **c}
                                    for i, c in enumerate(comps)])
    summ = {"snapshot_id": str(sid), "provider": prov.name, "provider_label": prov.label, "live": prov.live, "badge": prov.badge, "estimated_retail": result["estimated_retail"],
            "estimated_wholesale": result["estimated_wholesale"], "comps_used": result["comps_used"], "listing_count": result["listing_count"],
            "confidence": result["confidence"]["level"], "fetched_at": now}
    await db[A].update_one({"_id": appr["_id"]}, {"$set": {"market_snapshot_id": str(sid), "market_zip": z, "market_radius": rad, "market_summary": summ, "updated_at": now}})
    q = res.get("quota") or {}
    await db[USAGE].update_one({"provider": prov.name, "month": _month()},
                               {"$inc": {"calls": res.get("calls") or 0, "snapshots": 1}, "$set": {"updated_at": now, **({"last_quota_remaining": q["quota_remaining"]} if q.get("quota_remaining") is not None else {}),
                                                                                                    **({"last_rate_remaining": q["rate_remaining"]} if q.get("rate_remaining") is not None else {})}}, upsert=True)
    await audit(db, appr, me, "market_snapshot", f"{prov.label}: est. retail {('$' + format(result['estimated_retail'], ',')) if result['estimated_retail'] else 'n/a'} · {result['comps_used']} comps · {result['confidence']['level']} confidence"
                + (" · DEVELOPMENT DATA" if not prov.live else ""), meta={"snapshot_id": str(sid), "provider": prov.name, "live": prov.live, "zip": z, "radius": rad, "calls": res.get("calls") or 0})
    return {"snapshot": doc, "cached": False}


# ---------- manual book values ----------
def _book(data: dict, me: dict, existing: Optional[dict] = None) -> dict:
    src = (data.get("source") or (existing or {}).get("source") or "").strip().lower()
    if src not in BOOK_SOURCES:
        raise ValueError("Pick a book value source")
    vt = (data.get("value_type") or (existing or {}).get("value_type") or "wholesale").strip().lower()
    if vt not in VALUE_TYPES:
        raise ValueError("Value type must be wholesale, retail or trade-in")
    val = data.get("value", (existing or {}).get("value"))
    try:
        val = int(val)
    except (TypeError, ValueError):
        raise ValueError("Enter the book value as a whole dollar amount")
    if not (0 < val < 5_000_000):
        raise ValueError("That amount does not look right")
    label = (data.get("source_label") or "").strip()[:60] if src == "other" else BOOK_SOURCES[src]
    now = _now()
    return {"id": (existing or {}).get("id") or str(ObjectId()), "source": src, "source_label": label or BOOK_SOURCES[src], "value_type": vt, "value": val,
            "note": str(data.get("note") if data.get("note") is not None else (existing or {}).get("note") or "")[:300],
            "entered_by": (existing or {}).get("entered_by") or str(me["_id"]), "entered_by_name": (existing or {}).get("entered_by_name") or _name(me),
            "entered_at": (existing or {}).get("entered_at") or now, "updated_at": now, "updated_by": str(me["_id"])}


async def add_book_value(db, appr: dict, me: dict, data: dict) -> dict:
    b = _book(data, me)
    await db[A].update_one({"_id": appr["_id"]}, {"$push": {"book_values": b}, "$set": {"updated_at": _now()}})
    await audit(db, appr, me, "book_value_added", f"{b['source_label']} {VALUE_TYPES[b['value_type']].lower()} ${b['value']:,}", meta={"book_id": b["id"]})
    return await db[A].find_one({"_id": appr["_id"]})


async def edit_book_value(db, appr: dict, me: dict, book_id: str, data: dict) -> dict:
    cur = next((x for x in appr.get("book_values") or [] if x.get("id") == book_id), None)
    if not cur:
        raise ValueError("Book value not found")
    b = _book(data, me, cur)
    await db[A].update_one({"_id": appr["_id"], "book_values.id": book_id}, {"$set": {"book_values.$": b, "updated_at": _now()}})
    await audit(db, appr, me, "book_value_edited", f"{b['source_label']} {VALUE_TYPES[b['value_type']].lower()} ${b['value']:,}", meta={"book_id": b["id"], "was": cur.get("value")})
    return await db[A].find_one({"_id": appr["_id"]})


async def remove_book_value(db, appr: dict, me: dict, book_id: str) -> dict:
    cur = next((x for x in appr.get("book_values") or [] if x.get("id") == book_id), None)
    if not cur:
        raise ValueError("Book value not found")
    await db[A].update_one({"_id": appr["_id"]}, {"$pull": {"book_values": {"id": book_id}}, "$set": {"updated_at": _now()}})
    await audit(db, appr, me, "book_value_removed", f"{cur.get('source_label')} ${int(cur.get('value') or 0):,}", meta={"book_id": book_id})
    return await db[A].find_one({"_id": appr["_id"]})
