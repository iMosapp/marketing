"""Market analysis (MVP3 + provider validation): one normalized snapshot per fetch (never overwritten; a refresh adds a new one and the appraisal points
at the latest), comparables with I'm On Social's own match quality, a confidence read, manual book values, and an admin-only provider comparison that
keeps every provider's number separate (never averaged). No ACV here: that is MVP4."""
import asyncio
import json
import logging
import os
import re
import statistics
import time
from datetime import datetime, timezone, timedelta
from typing import Optional

from bson import ObjectId

from services.appraisals import market_providers as mp, rules as rulesvc
from services.appraisals.core import A, _now, _oid, _name, audit, scope
from utils.image_storage import put_object

logger = logging.getLogger(__name__)

SNAP, COMP, USAGE = "vehicle_market_snapshots", "vehicle_comparables", "market_provider_usage"
CALLS, COMPARISONS = "market_provider_calls", "market_provider_comparisons"
CACHE_HOURS = 24
MONTHLY_CAP_DEFAULT = 450  # free tier is 500 calls / month; keep headroom
MONTHLY_CAPS = {"marketcheck": ("MARKETCHECK_MONTHLY_CAP", 450), "vinaudit": ("VINAUDIT_MONTHLY_CAP", 100)}
ADMIN_ROLES = ("super_admin", "org_admin")
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
    if not comps and prediction and prediction.get("certainty") is not None:
        # Statistical providers (VinAudit): no listings to match, so the provider's own certainty and sample size carry the read.
        c, n = int(prediction["certainty"]), int(prediction.get("sample_count") or 0)
        reasons.append(f"{prediction.get('model') or 'The provider'} reports {c}% statistical certainty")
        reasons.append(f"{n} sales records in the period; no individual listings to match against your trade")
        score = c if n >= 10 else min(c, 70 if n >= 5 else 44)
        if n < 10:
            reasons.append("Thin sample, so confidence is capped")
        level = "high" if score >= 75 else "medium" if score >= 45 else "low"
        return {"level": level, "score": max(0, min(100, score)), "reasons": reasons}
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
        retail, retail_source, retail_label = prediction["predicted_retail"], provider.retail_source, prediction.get("model")
    elif med is not None:
        retail, retail_source, retail_label = med, "comps_median", f"Median of {len(basis)} {'exact/strong' if basis is good else ''} comparables".replace("  ", " ")
    else:
        retail, retail_source, retail_label = None, None, None
    wholesale = (prediction or {}).get("estimated_wholesale")
    band = (prediction or {}).get("price_band") or {}
    miles = [c["mileage"] for c in comps if c.get("mileage") is not None]
    doms = [c["dom"] for c in comps if c.get("dom") is not None]
    avg_miles = int(statistics.mean(miles)) if miles else (stats or {}).get("miles", {}).get("mean")
    counts = {q: sum(1 for c in comps if c["match"]["quality"] == q) for q in MATCH_ORDER}
    if len(basis) >= 4:
        price_range, range_basis = {"low": basis[len(basis) // 4], "high": basis[(3 * len(basis)) // 4]}, ("exact/strong comparables" if basis is good and good else "all comparables")
    elif basis:
        price_range, range_basis = {"low": basis[0], "high": basis[-1]}, ("exact/strong comparables" if basis is good and good else "all comparables")
    elif band.get("below") and band.get("above"):
        price_range, range_basis = {"low": band["below"], "high": band["above"]}, f"{provider.label} below/above market band"
    else:
        price_range, range_basis = None, None
    return {"estimated_retail": retail, "retail_source": retail_source, "retail_label": retail_label,
            "estimated_wholesale": wholesale, "wholesale_source": "mock_model" if wholesale and not provider.live else None,
            "estimated_trade_in": (prediction or {}).get("estimated_trade_in"), "trade_in_source": (prediction or {}).get("trade_in_source"),
            "msrp": (prediction or {}).get("msrp"),
            "price_range": price_range, "price_range_basis": range_basis,
            "avg_market_price": int(statistics.mean(prices)) if prices else (stats or {}).get("price", {}).get("mean"),
            "median_market_price": int(statistics.median(prices)) if prices else (stats or {}).get("price", {}).get("median"),
            "price_min": prices[0] if prices else (stats or {}).get("price", {}).get("min"), "price_max": prices[-1] if prices else (stats or {}).get("price", {}).get("max"),
            "price_stddev": int(statistics.pstdev(prices)) if len(prices) >= 2 else (stats or {}).get("price", {}).get("stddev"),
            "listing_count": num_found, "comps_returned": len(comps), "comps_used": len(priced), "match_counts": counts, "comps_kind": provider.comps_kind,
            "avg_dom": int(statistics.mean(doms)) if doms else (stats or {}).get("dom", {}).get("mean"),
            "median_dom": int(statistics.median(doms)) if doms else (stats or {}).get("dom", {}).get("median"),
            "avg_miles": avg_miles, "mileage_vs_market": (int(mileage) - int(avg_miles)) if (mileage is not None and avg_miles is not None) else None,
            "provider_certainty": (prediction or {}).get("certainty"), "sample_count": (prediction or {}).get("sample_count"), "lookup_id": (prediction or {}).get("lookup_id"),
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
            "calls": s.get("calls"), "quota": s.get("quota"), "purpose": s.get("purpose") or "appraisal", "fallback_from": s.get("fallback_from"), "response_ms": s.get("response_ms")}


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


def monthly_cap(provider: mp.MarketDataProvider) -> Optional[int]:
    if not provider.live:
        return None
    env, default = MONTHLY_CAPS.get(provider.name, (None, MONTHLY_CAP_DEFAULT))
    return int((os.environ.get(env) if env else None) or default)


async def usage(db, provider: mp.MarketDataProvider) -> dict:
    row = await db[USAGE].find_one({"provider": provider.name, "month": _month()}) or {}
    return {"provider": provider.name, "label": provider.label, "live": provider.live, "configured": provider.configured(), "month": _month(),
            "calls": row.get("calls") or 0, "snapshots": row.get("snapshots") or 0, "comparisons": row.get("comparisons") or 0, "failures": row.get("failures") or 0,
            "cap": monthly_cap(provider), "quota_remaining": row.get("last_quota_remaining"), "rate_remaining": row.get("last_rate_remaining"),
            "last_at": row.get("updated_at"), "blocked_until": row.get("blocked_until")}


async def usage_all(db) -> list:
    return [await usage(db, mp.PROVIDERS[n]) for n in mp.LIVE_PROVIDERS]


async def _ledger(db, provider: mp.MarketDataProvider, *, purpose: str, appr: Optional[dict], me: dict, target: dict, zip_code: Optional[str], calls: int, ms: int,
                  ok: bool, error: Optional[str] = None, quota: Optional[dict] = None, snapshot_id: Optional[ObjectId] = None):
    """One row per provider fetch (success or failure) so API cost per appraisal / per month can be read back. Never stores credentials."""
    q = quota or {}
    now = _now()
    await db[CALLS].insert_one({"_id": ObjectId(), "provider": provider.name, "live": provider.live, "purpose": purpose, "appraisal_id": str(appr["_id"]) if appr else None,
                                "snapshot_id": str(snapshot_id) if snapshot_id else None, "user_id": str(me["_id"]), "store_id": (appr or {}).get("store_id") or me.get("store_id"),
                                "organization_id": (appr or {}).get("organization_id") or me.get("organization_id"), "vin": target.get("vin"), "year": target.get("year"),
                                "make": target.get("make"), "model": target.get("model"), "zip": zip_code, "calls": int(calls or 0), "calls_estimated": not ok, "response_ms": int(ms or 0), "ok": bool(ok),
                                "error": (error or "")[:300] or None, "quota_remaining": q.get("quota_remaining"), "at": now})
    inc = {"calls": int(calls or 0)}
    if ok:
        inc["snapshots" if purpose == "appraisal" else "comparisons"] = 1
    else:
        inc["failures"] = 1
    sets = {"updated_at": now}
    if q.get("quota_remaining") is not None:
        sets["last_quota_remaining"] = q["quota_remaining"]
    if q.get("rate_remaining") is not None:
        sets["last_rate_remaining"] = q["rate_remaining"]
    await db[USAGE].update_one({"provider": provider.name, "month": _month()}, {"$inc": inc, "$set": sets}, upsert=True)


async def cost_summary(db, me: dict, month: Optional[str] = None) -> dict:
    """Calls per provider and per purpose this month, within the caller's reach; appraisal count gives a calls-per-appraisal read."""
    month = month or _month()
    start = datetime.strptime(month, "%Y-%m").replace(tzinfo=timezone.utc)
    end = (start.replace(year=start.year + 1, month=1) if start.month == 12 else start.replace(month=start.month + 1))
    match = {"at": {"$gte": start, "$lt": end}, **(await scope(me))}
    rows = await db[CALLS].aggregate([{"$match": match}, {"$group": {"_id": {"provider": "$provider", "purpose": "$purpose"}, "calls": {"$sum": "$calls"}, "fetches": {"$sum": 1},
                                                                       "failures": {"$sum": {"$cond": ["$ok", 0, 1]}}, "avg_ms": {"$avg": "$response_ms"},
                                                                       "appraisals": {"$addToSet": "$appraisal_id"}}}]).to_list(50)
    out = []
    for r in rows:
        n_appr = len([a for a in r["appraisals"] if a])
        out.append({"provider": r["_id"]["provider"], "purpose": r["_id"]["purpose"], "calls": r["calls"], "fetches": r["fetches"], "failures": r["failures"],
                    "avg_ms": int(r["avg_ms"] or 0), "appraisals": n_appr, "calls_per_appraisal": round(r["calls"] / n_appr, 2) if n_appr else None})
    out.sort(key=lambda x: (x["provider"], x["purpose"]))
    return {"month": month, "rows": out}


async def market_rules_for(db, organization_id: Optional[str], store_id: Optional[str]) -> dict:
    eff = await rulesvc.effective(db, organization_id, store_id)
    return eff["rules"].get("market") or dict(rulesvc.DEFAULT_RULES["market"])


async def providers_for(db, appr: dict) -> tuple:
    """(primary provider, fallback provider | None, market rules) for this appraisal's dealership."""
    mr = await market_rules_for(db, appr.get("organization_id"), appr.get("store_id"))
    prov, fb = mp.for_rules(mr)
    return prov, fb, mr


async def active_for(db, me: dict) -> mp.MarketDataProvider:
    """Provider the caller's own store/org would pull from (for screens without an appraisal in hand)."""
    sid = me.get("store_id") or ((me.get("store_ids") or [None])[0])
    mr = await market_rules_for(db, me.get("organization_id"), str(sid) if sid else None)
    return mp.for_rules(mr)[0]


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
    prov, fb, mr = await providers_for(db, appr)
    snap = await latest_snapshot(db, appr)
    hist = await db[SNAP].find({"appraisal_id": str(appr["_id"]), "purpose": {"$ne": "comparison"}}, {"fetched_at": 1, "provider_label": 1, "live": 1, "result.estimated_retail": 1, "result.comps_used": 1, "requested.zip": 1}).sort("fetched_at", -1).to_list(20)
    return {"provider": {"name": prov.name, "label": prov.label, "live": prov.live, "badge": prov.badge, "calls_per_fetch": prov.calls_per_fetch,
                         "fallback": {"name": fb.name, "label": fb.label} if fb else None, "rules_fallback": mr.get("fallback")},
            "zip": {**(await resolve_zip(db, appr, me)), "radius": appr.get("market_radius") or mp.DEFAULT_RADIUS},
            "snapshot": public_snapshot(snap) if snap else None, "comparables": await comparables_for(db, snap) if snap else [],
            "history": [{"id": str(h["_id"]), "fetched_at": h.get("fetched_at"), "provider_label": h.get("provider_label"), "live": h.get("live"),
                         "estimated_retail": (h.get("result") or {}).get("estimated_retail"), "comps_used": (h.get("result") or {}).get("comps_used"), "zip": (h.get("requested") or {}).get("zip")} for h in hist],
            "book_values": public_book_values(appr), "book_sources": BOOK_SOURCES, "value_types": VALUE_TYPES, "match_labels": MATCH_LABELS,
            "usage": await usage(db, prov), "mileage": appr.get("mileage_confirmed"), "vehicle": appr.get("vehicle"),
            "comparison": {"allowed": bool(mr.get("comparison")) and me.get("role") in ADMIN_ROLES, "latest": await latest_comparison(db, appr)}}


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


async def _guard_monthly(db, provider: mp.MarketDataProvider, need: Optional[int] = None):
    if not provider.live:
        return
    u = await usage(db, provider)
    if u.get("blocked_until") and u["blocked_until"].replace(tzinfo=timezone.utc) > _now():
        raise mp.MarketQuotaExceeded(f"The {provider.label} monthly quota is used up. Market data comes back when the quota resets.", None, True)
    if u["cap"] is not None and u["calls"] + (need or provider.calls_per_fetch) > u["cap"]:
        env = MONTHLY_CAPS.get(provider.name, ("the monthly cap", None))[0]
        raise mp.MarketQuotaExceeded(f"This month's {provider.label} budget ({u['cap']} calls) is spent. It resets on the 1st; ask an admin to raise {env}.", None, True)


def _comps(target: dict, listings: list) -> list:
    comps = [{**l, "match": match_quality(target, l)} for l in listings if not (l.get("make") and _norm(l["make"]) != _norm(target["make"]))]
    comps.sort(key=lambda c: (-c["match"]["score"], c.get("distance_mi") if c.get("distance_mi") is not None else 999, c.get("price") or 0))
    return comps


async def _fetch_logged(db, prov: mp.MarketDataProvider, *, purpose: str, appr: Optional[dict], me: dict, target: dict, zip_code: str, radius: int, dealer_type: str, **opts) -> tuple:
    """One provider fetch with timing + ledger row. Raises the provider's own exception after recording the failure (quota failures also block the month)."""
    t0 = time.monotonic()
    try:
        res = await prov.fetch(vin=target["vin"], year=target["year"], make=target["make"], model=target["model"], trim=target["trim"], mileage=target["mileage"],
                               zip_code=zip_code, radius=radius, dealer_type=dealer_type, **opts)
    except mp.MarketUnavailable as e:
        ms = int((time.monotonic() - t0) * 1000)
        await _ledger(db, prov, purpose=purpose, appr=appr, me=me, target=target, zip_code=zip_code, calls=getattr(e, "calls", prov.calls_per_fetch if prov.live else 0), ms=ms, ok=False, error=str(e))
        if isinstance(e, mp.MarketQuotaExceeded) and e.monthly:
            await db[USAGE].update_one({"provider": prov.name, "month": _month()}, {"$set": {"blocked_until": _now() + timedelta(hours=6), "updated_at": _now()}}, upsert=True)
        if appr:
            await audit(db, appr, me, "market_fetch_failed", str(e)[:200], meta={"provider": prov.name, "purpose": purpose, "quota": isinstance(e, mp.MarketQuotaExceeded)})
        raise
    return res, int((time.monotonic() - t0) * 1000)


def _snapshot_doc(sid: ObjectId, appr: Optional[dict], me: dict, prov: mp.MarketDataProvider, requested: dict, res: dict, result: dict, raw_bits: dict, now, *, purpose: str,
                  ms: int, is_latest: bool, previous: Optional[dict] = None, fallback_from: Optional[str] = None) -> dict:
    return {"_id": sid, "appraisal_id": str(appr["_id"]) if appr else None, "vehicle_id": (appr or {}).get("vehicle_id"), "contact_id": (appr or {}).get("contact_id"),
            "user_id": (appr or {}).get("user_id") or str(me["_id"]), "store_id": (appr or {}).get("store_id") or me.get("store_id"),
            "organization_id": (appr or {}).get("organization_id") or me.get("organization_id"), "provider": prov.name, "provider_label": prov.label, "live": prov.live,
            "badge": prov.badge, "purpose": purpose, "fallback_from": fallback_from, "requested": requested, "prediction": res.get("prediction"), "stats": res.get("stats"),
            "result": result, "quota": res.get("quota") or {}, "calls": res.get("calls") or 0, "response_ms": ms, **raw_bits, "fetched_at": now,
            "expires_at": now + timedelta(hours=CACHE_HOURS), "is_latest": is_latest, "superseded_by": None, "previous_snapshot_id": str(previous["_id"]) if previous else None,
            "fetched_by": str(me["_id"]), "fetched_by_name": _name(me)}


async def _store_comps(db, sid: ObjectId, appr: Optional[dict], me: dict, prov: mp.MarketDataProvider, comps: list, now, purpose: str):
    if comps:
        await db[COMP].insert_many([{"_id": ObjectId(), "snapshot_id": str(sid), "appraisal_id": str(appr["_id"]) if appr else None, "user_id": (appr or {}).get("user_id") or str(me["_id"]),
                                     "store_id": (appr or {}).get("store_id") or me.get("store_id"), "organization_id": (appr or {}).get("organization_id") or me.get("organization_id"),
                                     "provider": prov.name, "live": prov.live, "purpose": purpose, "rank": i + 1, "fetched_at": now, **c} for i, c in enumerate(comps)])


async def refresh(db, appr: dict, me: dict, *, zip_code: Optional[str] = None, radius: Optional[int] = None, force: bool = False) -> dict:
    """Fetch (or reuse within 24h) market data for this appraisal from the dealership's primary provider. Each fetch is a NEW snapshot; older ones stay for
    the audit trail. A fallback provider is tried ONLY when the dealership rules name one; otherwise the failure is raised and nothing is invented."""
    target = _target(appr)
    z = (zip_code or "").strip()[:5] or (await resolve_zip(db, appr, me))["zip"]
    if not z or not re.fullmatch(r"\d{5}", z):
        raise ValueError("Give me a 5-digit ZIP for the market search (the store has none on file).")
    rad = int(radius or appr.get("market_radius") or mp.DEFAULT_RADIUS)
    rad = max(10, min(rad, 500))
    prov, fb, mr = await providers_for(db, appr)
    dealer_type = (os.environ.get("MARKET_DEALER_TYPE") or "franchise").lower()
    dealer_type = dealer_type if dealer_type in mp.DEALER_TYPES else "franchise"
    requested = {**target, "zip": z, "radius": rad, "dealer_type": dealer_type, "car_type": "used", "provider": prov.name}
    latest = await latest_snapshot(db, appr)
    if latest and not force and latest.get("requested") == requested and latest.get("fetched_at") and latest["fetched_at"].replace(tzinfo=timezone.utc) > _now() - timedelta(hours=CACHE_HOURS):
        return {"snapshot": latest, "cached": True}
    mp.check_rate(str(me["_id"]), appr.get("store_id"))
    await _guard_monthly(db, prov)
    used, fallback_from = prov, None
    try:
        res, ms = await _fetch_logged(db, prov, purpose="appraisal", appr=appr, me=me, target=target, zip_code=z, radius=rad, dealer_type=dealer_type)
    except mp.MarketUnavailable as e:
        if not fb:
            raise
        await audit(db, appr, me, "market_fallback", f"{prov.label} failed ({str(e)[:120]}). Dealership rules allow {fb.label} as the fallback, pulling from it.",
                    meta={"from": prov.name, "to": fb.name})
        await _guard_monthly(db, fb)
        res, ms = await _fetch_logged(db, fb, purpose="appraisal", appr=appr, me=me, target=target, zip_code=z, radius=rad, dealer_type=dealer_type)
        used, fallback_from = fb, prov.name
        requested = {**requested, "provider": fb.name}
    now = _now()
    sid = ObjectId()
    comps = _comps(target, res["listings"])
    result = _summarize(res.get("prediction"), comps, res.get("stats"), res.get("num_found") or 0, target["mileage"], used, res.get("notes") or [])
    raw_bits = await _store_raw(appr, sid, res.get("raw") or {})
    doc = _snapshot_doc(sid, appr, me, used, requested, res, result, raw_bits, now, purpose="appraisal", ms=ms, is_latest=True, previous=latest, fallback_from=fallback_from)
    await db[SNAP].insert_one(doc)
    if latest:
        await db[SNAP].update_one({"_id": latest["_id"]}, {"$set": {"is_latest": False, "superseded_by": str(sid)}})
    await _store_comps(db, sid, appr, me, used, comps, now, "appraisal")
    summ = {"snapshot_id": str(sid), "provider": used.name, "provider_label": used.label, "live": used.live, "badge": used.badge, "estimated_retail": result["estimated_retail"],
            "estimated_wholesale": result["estimated_wholesale"], "estimated_trade_in": result.get("estimated_trade_in"), "comps_used": result["comps_used"],
            "listing_count": result["listing_count"], "confidence": result["confidence"]["level"], "fetched_at": now, "fallback_from": fallback_from}
    await db[A].update_one({"_id": appr["_id"]}, {"$set": {"market_snapshot_id": str(sid), "market_zip": z, "market_radius": rad, "market_summary": summ, "updated_at": now}})
    await _ledger(db, used, purpose="appraisal", appr=appr, me=me, target=target, zip_code=z, calls=res.get("calls") or 0, ms=ms, ok=True, quota=res.get("quota"), snapshot_id=sid)
    await audit(db, appr, me, "market_snapshot", f"{used.label}: est. retail {('$' + format(result['estimated_retail'], ',')) if result['estimated_retail'] else 'n/a'} · {result['comps_used']} comps · {result['confidence']['level']} confidence"
                + (" · DEVELOPMENT DATA" if not used.live else "") + (f" · fallback from {prov.label}" if fallback_from else ""),
                meta={"snapshot_id": str(sid), "provider": used.name, "live": used.live, "zip": z, "radius": rad, "calls": res.get("calls") or 0, "fallback_from": fallback_from})
    return {"snapshot": doc, "cached": False}


# ---------- provider comparison (admin, deliberate; never averaged) ----------
def _card(prov: mp.MarketDataProvider, snap: Optional[dict] = None, *, status: str = "ok", error: Optional[str] = None, cached: bool = False) -> dict:
    r, p, req = (snap or {}).get("result") or {}, (snap or {}).get("prediction") or {}, (snap or {}).get("requested") or {}
    has_listings = bool(r.get("comps_returned"))
    return {"provider": prov.name, "label": prov.label, "badge": prov.badge, "live": prov.live if snap else None, "status": status, "error": error, "cached": cached,
            "configured": prov.configured(), "snapshot_id": str(snap["_id"]) if snap else None, "fetched_at": (snap or {}).get("fetched_at"), "response_ms": (snap or {}).get("response_ms"),
            "calls": (snap or {}).get("calls"), "lookup_id": p.get("lookup_id"),
            "estimated_retail": r.get("estimated_retail"), "retail_label": r.get("retail_label"), "retail_source": r.get("retail_source"),
            "estimated_wholesale": r.get("estimated_wholesale") if snap and prov.live else None, "wholesale_source": r.get("wholesale_source") if prov.live else None,
            "estimated_trade_in": r.get("estimated_trade_in"), "trade_in_source": r.get("trade_in_source"),
            "comps_median": r.get("median_market_price"), "comps_average": r.get("avg_market_price"), "price_range": r.get("price_range"), "price_range_basis": r.get("price_range_basis"),
            "comps_count": r.get("comps_used") if has_listings else r.get("listing_count"), "comps_kind": r.get("comps_kind") or prov.comps_kind, "listing_count": r.get("listing_count"),
            "mileage": req.get("mileage"), "mileage_used": p.get("mileage_used"), "avg_miles": r.get("avg_miles"), "zip": req.get("zip"), "radius": req.get("radius"),
            "zip_applies": prov.name != "vinaudit", "confidence": r.get("confidence"), "provider_certainty": r.get("provider_certainty"), "notes": r.get("notes") or []}


def _difference(cards: list) -> dict:
    """Two independent observations, reported as a gap. Symmetric percent so neither provider is the reference; no combined value is ever produced."""
    vals = {c["provider"]: c.get("estimated_retail") for c in cards if c.get("estimated_retail")}
    a, b = vals.get("marketcheck"), vals.get("vinaudit")
    if not a or not b:
        return {"available": False, "reason": "Both providers need a retail estimate before a difference can be shown."}
    d = a - b
    return {"available": True, "dollars": d, "percent": round(abs(d) / ((a + b) / 2) * 100, 1), "higher": "marketcheck" if d > 0 else "vinaudit" if d < 0 else None,
            "note": "MarketCheck retail minus VinAudit retail; percent is the symmetric gap. Neither provider is treated as correct."}


def public_comparison(c: dict) -> dict:
    return {"id": str(c["_id"]), "appraisal_id": c.get("appraisal_id"), "purpose": c.get("purpose"), "vehicle": c.get("vehicle"), "zip": c.get("zip"), "radius": c.get("radius"),
            "providers": c.get("providers") or [], "difference": c.get("difference"), "calls_total": c.get("calls_total"), "created_at": c.get("created_at"),
            "by_name": c.get("by_name"), "store_id": c.get("store_id")}


async def latest_comparison(db, appr: dict) -> Optional[dict]:
    c = await db[COMPARISONS].find_one({"appraisal_id": str(appr["_id"])}, sort=[("created_at", -1)])
    return public_comparison(c) if c else None


async def list_comparisons(db, me: dict, limit: int = 50) -> list:
    rows = await db[COMPARISONS].find(await scope(me)).sort("created_at", -1).to_list(max(1, min(limit, 200)))
    return [public_comparison(c) for c in rows]


async def compare(db, me: dict, *, appr: Optional[dict] = None, vehicle: Optional[dict] = None, mileage: Optional[int] = None, zip_code: Optional[str] = None,
                  radius: Optional[int] = None, force: bool = False, purpose: str = "comparison", probe_zip: bool = False) -> dict:
    """Pull BOTH live providers for the same vehicle and lay them side by side. Admin only, on purpose: every run costs paid calls (MarketCheck 2, VinAudit 2).
    Comparison snapshots are tagged purpose=comparison, never become the appraisal's latest snapshot and never feed the engine. Reused within 24h unless force."""
    if appr:
        target = _target(appr)
    else:
        v = vehicle or {}
        if not (v.get("year") and v.get("make") and v.get("model")):
            raise ValueError("Give the year, make and model (or a VIN that decodes) to compare providers.")
        target = {"vin": v.get("vin"), "year": int(v["year"]), "make": v["make"], "model": v["model"], "trim": v.get("trim"), "mileage": int(mileage) if mileage is not None else None}
    z = (zip_code or "").strip()[:5] or ((await resolve_zip(db, appr, me))["zip"] if appr else None)
    if not z or not re.fullmatch(r"\d{5}", z):
        raise ValueError("Give me a 5-digit ZIP for the comparison.")
    rad = max(10, min(int(radius or (appr or {}).get("market_radius") or mp.DEFAULT_RADIUS), 500))
    dealer_type = (os.environ.get("MARKET_DEALER_TYPE") or "franchise").lower()
    dealer_type = dealer_type if dealer_type in mp.DEALER_TYPES else "franchise"
    mp.check_rate(str(me["_id"]), (appr or {}).get("store_id") or me.get("store_id"))
    if not any(mp.PROVIDERS[n].configured() for n in mp.LIVE_PROVIDERS):
        raise mp.MarketUnavailable("No live market data provider key is installed on this server, so there is nothing to compare.")
    cards, now = [], _now()
    tenant = {"organization_id": (appr or {}).get("organization_id") or me.get("organization_id")}
    for name in mp.LIVE_PROVIDERS:
        prov = mp.PROVIDERS[name]
        opts = {"value_types": mp.VA_VALUE_TYPES, "send_zip": probe_zip} if name == "vinaudit" else {}
        if not prov.configured():
            cards.append(_card(prov, status="not_configured", error=f"{prov.label} key is not installed on this server."))
            continue
        requested = {**target, "zip": z, "radius": rad, "dealer_type": dealer_type, "car_type": "used", "provider": prov.name, "purpose": "comparison", **({"value_types": list(mp.VA_VALUE_TYPES), "probe_zip": probe_zip} if name == "vinaudit" else {})}
        prior = await db[SNAP].find_one({"purpose": "comparison", "provider": prov.name, "requested": requested, **tenant, "fetched_at": {"$gt": now - timedelta(hours=CACHE_HOURS)}}, sort=[("fetched_at", -1)])
        if prior and not force:
            cards.append(_card(prov, prior, cached=True))
            continue
        try:
            await _guard_monthly(db, prov, need=2 if name == "vinaudit" else None)
            res, ms = await _fetch_logged(db, prov, purpose=purpose, appr=appr, me=me, target=target, zip_code=z, radius=rad, dealer_type=dealer_type, **opts)
        except mp.MarketUnavailable as e:
            cards.append(_card(prov, status="quota" if isinstance(e, mp.MarketQuotaExceeded) else "error", error=str(e)))
            continue
        sid = ObjectId()
        comps = _comps(target, res["listings"])
        result = _summarize(res.get("prediction"), comps, res.get("stats"), res.get("num_found") or 0, target["mileage"], prov, res.get("notes") or [])
        raw_bits = await _store_raw(appr or {"user_id": str(me["_id"]), "_id": "comparison"}, sid, res.get("raw") or {})
        doc = _snapshot_doc(sid, appr, me, prov, requested, res, result, raw_bits, now, purpose="comparison", ms=ms, is_latest=False)
        await db[SNAP].insert_one(doc)
        await _store_comps(db, sid, appr, me, prov, comps, now, "comparison")
        await _ledger(db, prov, purpose=purpose, appr=appr, me=me, target=target, zip_code=z, calls=res.get("calls") or 0, ms=ms, ok=True, quota=res.get("quota"), snapshot_id=sid)
        cards.append(_card(prov, doc))
    comp = {"_id": ObjectId(), "appraisal_id": str(appr["_id"]) if appr else None, "purpose": purpose, "vehicle": target, "zip": z, "radius": rad, "providers": cards,
            "difference": _difference(cards), "calls_total": sum(int(c.get("calls") or 0) for c in cards if not c.get("cached")), "user_id": str(me["_id"]), "by_name": _name(me),
            "store_id": (appr or {}).get("store_id") or me.get("store_id"), **tenant, "created_at": now}
    await db[COMPARISONS].insert_one(comp)
    if appr:
        await audit(db, appr, me, "market_comparison", " · ".join(f"{c['label']}: {('$' + format(c['estimated_retail'], ',')) if c.get('estimated_retail') else c['status']}" for c in cards),
                    meta={"comparison_id": str(comp["_id"]), "calls": comp["calls_total"]})
    return public_comparison(comp)


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
