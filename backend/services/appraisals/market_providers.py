"""Market data providers (MVP3, provider validation phase). The appraisal workflow only ever sees normalized dicts:
  MarketDataProvider -> MarketCheckProvider (live; needs MARKETCHECK_API_KEY, verified against docs.marketcheck.com)
                     -> VinAuditProvider (live; needs VINAUDIT_API_KEY, verified against data.vinaudit.com/docs/api/market/values)
                     -> MockMarketProvider (deterministic development data, always badged DEVELOPMENT DATA — NOT LIVE)
Nothing outside this file knows a provider's URL shapes or response fields. Providers are never averaged together: each fetch is one observation."""
import asyncio
import hashlib
import logging
import os
import random
import time
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

MC_BASE = "https://api.marketcheck.com/v2"
MAX_ROWS = 50
DEFAULT_RADIUS = 100
DEALER_TYPES = ("franchise", "independent")
LISTING_FIELDS = ("listing_id", "vin", "year", "make", "model", "trim", "mileage", "price", "msrp", "distance_mi", "dealer_name", "dealer_type", "city", "state",
                  "zip", "dom", "dom_active", "exterior_color", "is_certified", "vdp_url", "photo_url", "first_seen_at", "heading", "body_type", "drivetrain")


class MarketUnavailable(Exception):
    """The outside service failed or is not configured. Never swap in fake numbers for this."""


class MarketQuotaExceeded(MarketUnavailable):
    def __init__(self, message: str, retry_after: Optional[int] = None, monthly: bool = False):
        super().__init__(message)
        self.retry_after, self.monthly = retry_after, monthly


class MarketRateLimited(Exception):
    def __init__(self, retry_after: float):
        super().__init__(f"Too many market refreshes. Try again in {int(retry_after) + 1} seconds.")
        self.retry_after = retry_after


def _i(v) -> Optional[int]:
    try:
        return int(round(float(v))) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _f(v) -> Optional[float]:
    try:
        return round(float(v), 1) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


class MarketDataProvider:
    name = "base"
    label = ""
    live = False
    badge = ""
    retail_source = "base"          # what `result.retail_source` says when the provider's own estimate is used (the engine whitelists these)
    calls_per_fetch = 1             # typical paid calls per fetch, for budgeting before a pull
    comps_kind = "active listings"  # what `comps_count` means for this provider

    def configured(self) -> bool:
        return False

    async def fetch(self, *, vin: Optional[str], year: int, make: str, model: str, trim: Optional[str], mileage: Optional[int], zip_code: str,
                    radius: int, dealer_type: str, **opts) -> dict:
        """-> {prediction: {predicted_retail, msrp, estimated_wholesale?, estimated_trade_in?, model, ...} | None, listings: [normalized], stats: {price, miles, dom} | None,
        num_found, quota: {...}, raw: {...}, calls: int, notes: [str]}. `opts` are provider-specific (VinAudit: value_types, send_zip) and ignored by the others."""
        raise NotImplementedError


# ---------- MarketCheck ----------
def parse_quota(headers) -> dict:
    """RateLimit-* = per-second window, Quota-* = monthly quota (AGENTS.md); both are read proactively."""
    h = {k.lower(): v for k, v in dict(headers or {}).items()}
    return {"quota_remaining": _i(h.get("quota-remaining")), "quota_limit": _i(h.get("quota-limit")), "rate_remaining": _i(h.get("ratelimit-remaining")),
            "rate_limit": _i(h.get("ratelimit-limit")), "retry_after": _i(h.get("retry-after"))}


class MarketCheckProvider(MarketDataProvider):
    name = "marketcheck"
    label = "MarketCheck"
    live = True
    badge = "Source: MarketCheck"
    retail_source = "marketcheck_price"
    calls_per_fetch = 2

    def __init__(self, transport=None):
        self._transport = transport

    def key(self) -> str:
        return (os.environ.get("MARKETCHECK_API_KEY") or "").strip()

    def configured(self) -> bool:
        return bool(self.key())

    async def _get(self, cx: httpx.AsyncClient, path: str, params: dict) -> tuple:
        """One GET; api_key is ALWAYS a query param. 429 -> MarketQuotaExceeded (monthly when Quota-Remaining is 0 or Retry-After is long),
        5xx retried once with backoff, 4xx returned as {_error} so the caller can degrade (no data is not an outage)."""
        q = {k: v for k, v in params.items() if v not in (None, "")}
        q["api_key"] = self.key()
        for attempt in range(2):
            try:
                r = await cx.get(f"{MC_BASE}{path}", params=q)
            except httpx.HTTPError as e:
                if attempt == 0:
                    await asyncio.sleep(0.8)
                    continue
                raise MarketUnavailable(f"MarketCheck did not answer ({e.__class__.__name__}).")
            quota = parse_quota(r.headers)
            if r.status_code == 429:
                monthly = quota.get("quota_remaining") == 0 or (quota.get("retry_after") or 0) > 120
                raise MarketQuotaExceeded("The MarketCheck monthly quota is used up. Market data comes back when the quota resets." if monthly
                                          else "MarketCheck is being called too fast. Try again in a moment.", quota.get("retry_after"), monthly)
            if r.status_code == 401:
                raise MarketUnavailable("MarketCheck rejected the API key. Check MARKETCHECK_API_KEY.")
            if r.status_code == 403:
                raise MarketUnavailable("This MarketCheck plan does not include that endpoint.")
            if r.status_code >= 500:
                if attempt == 0:
                    await asyncio.sleep(1.2)
                    continue
                raise MarketUnavailable(f"MarketCheck is having trouble right now ({r.status_code}).")
            if r.status_code >= 400:
                try:
                    msg = (r.json() or {}).get("message") or r.text[:160]
                except ValueError:
                    msg = r.text[:160]
                return {"_error": r.status_code, "_message": msg}, quota
            return r.json(), quota
        raise MarketUnavailable("MarketCheck did not answer.")

    async def fetch(self, *, vin, year, make, model, trim, mileage, zip_code, radius, dealer_type, **opts) -> dict:
        notes, raw, calls, quota, prediction = [], {}, 0, {}, None
        async with httpx.AsyncClient(timeout=30, transport=self._transport) as cx:
            if vin and len(vin) == 17 and mileage is not None:
                data, quota = await self._get(cx, "/predict/car/us/marketcheck_price", {"vin": vin, "miles": int(mileage), "zip": zip_code, "dealer_type": dealer_type})
                calls += 1
                raw["predict"] = data
                if "_error" in data:
                    notes.append(f"MarketCheck Price could not price this VIN ({data['_message']}); the estimate comes from comparables.")
                elif _i(data.get("marketcheck_price")) is not None:
                    prediction = {"predicted_retail": _i(data.get("marketcheck_price")), "msrp": _i(data.get("msrp")), "model": "MarketCheck Price (ML)"}
                else:
                    notes.append("MarketCheck Price returned no price for this VIN; the estimate comes from comparables.")
            else:
                notes.append("No 17-character VIN or confirmed mileage, so the ML price prediction was skipped; the estimate comes from comparables.")
            params = {"year": year, "make": make, "model": model, "zip": zip_code, "radius": radius, "car_type": "used", "rows": MAX_ROWS,
                      "stats": "price,miles,dom", "sort_by": "dist", "sort_order": "asc", "has_price": "true"}
            data, q2 = await self._get(cx, "/search/car/active", params)
            calls += 1
            raw["search"] = data
            quota = {**quota, **{k: v for k, v in q2.items() if v is not None}}
        listings, stats, num_found = [], None, 0
        if "_error" in data:
            notes.append(f"MarketCheck inventory search returned nothing usable ({data['_message']}).")
        else:
            listings = [self.normalize_listing(l) for l in (data.get("listings") or [])]
            stats = self.normalize_stats(data.get("stats"))
            num_found = _i(data.get("num_found")) or len(listings)
        if prediction is None and not listings:
            raise MarketUnavailable("MarketCheck had neither a price prediction nor active listings for this vehicle.")
        return {"prediction": prediction, "listings": listings, "stats": stats, "num_found": num_found, "quota": quota, "raw": raw, "calls": calls, "notes": notes}

    @staticmethod
    def normalize_listing(l: dict) -> dict:
        b, d, media = l.get("build") or {}, l.get("dealer") or l.get("mc_dealership") or {}, l.get("media") or {}
        photos = media.get("photo_links_cached") or media.get("photo_links") or []
        return {"listing_id": l.get("id"), "vin": l.get("vin"), "year": _i(b.get("year")), "make": b.get("make"), "model": b.get("model"), "trim": b.get("trim"),
                "mileage": _i(l.get("miles")), "price": _i(l.get("price")), "msrp": _i(l.get("msrp")), "distance_mi": _f(l.get("dist")), "dealer_name": d.get("name"),
                "dealer_type": d.get("dealer_type"), "city": d.get("city"), "state": d.get("state"), "zip": d.get("zip"), "dom": _i(l.get("dom")),
                "dom_active": _i(l.get("dom_active")), "exterior_color": l.get("exterior_color") or l.get("base_ext_color"), "is_certified": bool(l.get("is_certified")),
                "vdp_url": l.get("vdp_url"), "photo_url": photos[0] if photos else None, "first_seen_at": _i(l.get("first_seen_at")), "heading": l.get("heading"),
                "body_type": b.get("body_type"), "drivetrain": b.get("drivetrain")}

    @staticmethod
    def normalize_stats(s: Optional[dict]) -> Optional[dict]:
        if not isinstance(s, dict):
            return None
        out = {}
        for key, field in (("price", "price"), ("miles", "miles"), ("dom", "dom")):
            v = s.get(field)
            if not isinstance(v, dict) or "result" in v:
                continue
            pct = v.get("percentiles") or {}
            out[key] = {"mean": _i(v.get("mean")), "median": _i(v.get("median")), "min": _i(v.get("min")), "max": _i(v.get("max")), "count": _i(v.get("count")),
                        "stddev": _i(v.get("stddev")), "p25": _i(pct.get("25.0")), "p75": _i(pct.get("75.0"))}
        return out or None


# ---------- VinAudit Market Values ----------
VA_URL = "https://marketvalue.vinaudit.com/v2/marketvalue"
VA_PERIOD_DAYS = 90
VA_VALUE_TYPES = ("retail", "tradein")
VA_SOFT_ERRORS = {"invalid_vin": "VinAudit could not decode that VIN.", "no_data": "VinAudit has too few sales records for a reliable value.",
                  "invalid_zip": "VinAudit rejected the ZIP.", "invalid_state_or_province": "VinAudit rejected the state."}
VA_FATAL_ERRORS = {"invalid_key": "VinAudit rejected the API key. Check VINAUDIT_API_KEY.", "missing_key": "VinAudit got no API key. Check VINAUDIT_API_KEY.",
                   "api_not_enabled": "This VinAudit account does not include the Market Values API.", "failed_request": "VinAudit could not process the request."}


class VinAuditProvider(MarketDataProvider):
    """VinAudit Market Values API: one statistical value per call (`type` = retail | tradein) from sales records over `period` days, by 17-character VIN.
    No listings and no documented ZIP parameter. `mean` is the typed value; `prices.*` stay the retail distribution, so trade-in is read from `mean` only."""
    name = "vinaudit"
    label = "VinAudit"
    live = True
    badge = "Source: VinAudit"
    retail_source = "vinaudit_retail"
    calls_per_fetch = 1
    comps_kind = "sales records"

    def __init__(self, transport=None):
        self._transport = transport

    @staticmethod
    def key() -> str:
        return (os.environ.get("VINAUDIT_API_KEY") or "").strip()

    def configured(self) -> bool:
        return bool(self.key())

    async def _get(self, cx: httpx.AsyncClient, params: dict) -> tuple:
        """One GET; the key is ALWAYS the `key` query param. VinAudit reports most failures as HTTP 200 + success:false + a code, so both paths are mapped."""
        params = {k: v for k, v in params.items() if v not in (None, "")}
        params["key"] = self.key()
        for attempt in (0, 1):
            try:
                r = await cx.get(VA_URL, params=params)
            except httpx.HTTPError as e:
                if attempt == 0:
                    await asyncio.sleep(0.8)
                    continue
                raise MarketUnavailable(f"VinAudit did not answer ({type(e).__name__}).")
            quota = parse_quota(r.headers)
            if r.status_code >= 500:
                if attempt == 0:
                    await asyncio.sleep(1.2)
                    continue
                raise MarketUnavailable(f"VinAudit is having trouble ({r.status_code}).")
            if r.status_code in (401, 403):
                raise MarketUnavailable("VinAudit rejected the API key. Check VINAUDIT_API_KEY.")
            if r.status_code == 429:
                raise MarketQuotaExceeded("VinAudit rate limit reached.", quota.get("retry_after"), False)
            try:
                data = r.json()
            except ValueError:
                raise MarketUnavailable("VinAudit returned something that is not JSON.")
            if r.status_code < 400 and isinstance(data, dict) and data.get("success"):
                return data, quota
            code = self._error_code(data if isinstance(data, dict) else {})
            if code == "rate_limit_exceeded":
                raise MarketQuotaExceeded("VinAudit rate limit reached.", quota.get("retry_after"), False)
            if code == "billing_limit_exceeded":
                raise MarketQuotaExceeded("The VinAudit prepaid balance or billing limit is used up.", None, True)
            if code in VA_FATAL_ERRORS:
                raise MarketUnavailable(VA_FATAL_ERRORS[code])
            if code in VA_SOFT_ERRORS:
                return {"_error": code, "_message": VA_SOFT_ERRORS[code]}, quota
            msg = str((data or {}).get("error") or (data or {}).get("message") or f"HTTP {r.status_code}")[:160]
            return {"_error": code or str(r.status_code), "_message": f"VinAudit: {msg}"}, quota
        raise MarketUnavailable("VinAudit did not answer.")

    @staticmethod
    def _error_code(data: dict) -> Optional[str]:
        known = set(VA_SOFT_ERRORS) | set(VA_FATAL_ERRORS) | {"rate_limit_exceeded", "billing_limit_exceeded"}
        for k in ("data", "error_code", "code", "error"):
            v = data.get(k)
            if isinstance(v, str) and v.strip().lower() in known:
                return v.strip().lower()
        return None

    async def fetch(self, *, vin, year, make, model, trim, mileage, zip_code, radius, dealer_type, value_types=None, send_zip=False, **opts) -> dict:
        if not vin or len(str(vin)) != 17:
            raise MarketUnavailable("VinAudit values by VIN only, and this vehicle has no 17-character VIN.")
        types = tuple(t for t in (value_types or ("retail",)) if t in VA_VALUE_TYPES) or ("retail",)
        notes, raw, calls, quota, got = [], {}, 0, {}, {}
        if mileage is None:
            notes.append("No confirmed mileage, so VinAudit priced at its average mileage for this vehicle.")
        base = {"vin": vin, "format": "json", "period": VA_PERIOD_DAYS, "mileage": int(mileage) if mileage is not None else None}
        if send_zip and zip_code:
            base["zip"] = zip_code
            notes.append("ZIP was sent as a probe; VinAudit does not document a ZIP parameter.")
        async with httpx.AsyncClient(timeout=30, transport=self._transport) as cx:
            for t in types:
                data, q = await self._get(cx, {**base, "type": t})
                calls += 1
                raw[t] = data
                quota = {**quota, **{k: v for k, v in q.items() if v is not None}}
                if "_error" in data:
                    notes.append(f"VinAudit {t}: {data['_message']}")
                else:
                    got[t] = data
        retail = got.get("retail")
        if not retail or _i(retail.get("mean")) is None:
            raise MarketUnavailable(next((n for n in notes if n.startswith("VinAudit retail")), "VinAudit returned no retail value for this VIN."))
        prices = retail.get("prices") or {}
        groups = [(g.get("group") if isinstance(g.get("group"), dict) else g) for g in (prices.get("distribution") or []) if isinstance(g, dict)]
        mins = [_i(g.get("min")) for g in groups if _i(g.get("min")) is not None]
        maxs = [_i(g.get("max")) for g in groups if _i(g.get("max")) is not None]
        adj = retail.get("adjustments") or {}
        prediction = {"predicted_retail": _i(retail.get("mean")), "msrp": None, "model": "VinAudit Market Value (retail)", "certainty": _i(retail.get("certainty")),
                      "sample_count": _i(retail.get("count")), "period": retail.get("period"), "mileage_used": _i(retail.get("mileage")), "lookup_id": retail.get("id"),
                      "vehicle": retail.get("vehicle"), "price_band": {"below": _i(prices.get("below")), "average": _i(prices.get("average")), "above": _i(prices.get("above"))},
                      "adjustments": {k: adj.get(k) for k in ("mileage", "condition", "known_damage") if isinstance(adj.get(k), dict)}}
        ti = got.get("tradein")
        if ti and _i(ti.get("mean")) is not None:
            prediction["estimated_trade_in"], prediction["trade_in_source"] = _i(ti["mean"]), "vinaudit_tradein"
        stats = {"price": {"mean": _i(prices.get("average")), "median": None, "min": min(mins) if mins else None, "max": max(maxs) if maxs else None,
                           "count": _i(retail.get("count")), "stddev": _i(retail.get("stdev")), "p25": None, "p75": None}}
        avg_miles = _i((adj.get("mileage") or {}).get("average"))
        if avg_miles:
            stats["miles"] = {"mean": avg_miles, "median": None, "min": None, "max": None, "count": None, "stddev": None, "p25": None, "p75": None}
        period = retail.get("period")
        notes.append(f"VinAudit used {prediction['sample_count'] or 0} sales records" + (f" from {period[0]} to {period[1]}" if isinstance(period, list) and len(period) == 2 else "")
                     + "; it returns no individual listings, so comparables and match quality are not available from this provider.")
        return {"prediction": prediction, "listings": [], "stats": stats, "num_found": prediction["sample_count"] or 0, "quota": quota, "raw": raw, "calls": calls, "notes": notes}


# ---------- Mock ----------
_LUXURY = {"bmw", "mercedes-benz", "mercedes", "audi", "lexus", "porsche", "tesla", "cadillac", "lincoln", "acura", "infiniti", "volvo", "land rover", "jaguar", "genesis", "rivian"}
_TRUCKY = ("f-150", "f150", "f-250", "silverado", "sierra", "ram", "tundra", "tacoma", "tahoe", "suburban", "expedition", "4runner", "wrangler", "yukon", "sequoia", "frontier", "ranger", "colorado", "gladiator")
_DEALERS = ("Summit Auto Group", "Riverbend Motors", "Canyon Ridge Auto", "Metro Car Center", "Northgate Motors", "Pioneer Auto Plaza", "Lakeside Pre-Owned",
            "Valley Premier Cars", "Heritage Motor Co", "Westfield Auto Mall", "Redstone Auto", "Blue Sky Motors", "Main Street Auto", "Highline Pre-Owned")
_CITIES = {"0": ("Worcester", "MA"), "1": ("Albany", "NY"), "2": ("Richmond", "VA"), "3": ("Orlando", "FL"), "4": ("Columbus", "OH"), "5": ("Des Moines", "IA"),
           "6": ("Springfield", "IL"), "7": ("Austin", "TX"), "8": ("Sandy", "UT"), "9": ("Fresno", "CA")}
_COLORS = ("White", "Black", "Silver", "Gray", "Blue", "Red", "Charcoal", "Pearl White")
_TRIMS = ("LX", "EX", "EX-L", "Sport", "Touring", "SE", "SEL", "Limited", "XLT", "Lariat", "LT", "LTZ", "Premium", "Base")


def mock_retail(year: Optional[int], make: Optional[str], model: Optional[str], mileage: Optional[int]) -> int:
    """Simple depreciation curve. Development data only; never shown without the NOT LIVE badge."""
    now_year = time.gmtime().tm_year
    age = max(0, now_year - int(year or now_year))
    mk, md = (make or "").lower(), (model or "").lower()
    base = 56000 if mk in _LUXURY else 47000 if any(t in md for t in _TRUCKY) else 31000
    value = base * (0.87 ** min(age, 15))
    expected = age * 12500
    if mileage is not None:
        value -= (int(mileage) - expected) * 0.07
    return int(max(2500, round(value / 50) * 50))


class MockMarketProvider(MarketDataProvider):
    name = "mock"
    label = "Development data"
    live = False
    badge = "DEVELOPMENT DATA — NOT LIVE"
    retail_source = "mock_model"
    calls_per_fetch = 0

    def configured(self) -> bool:
        return True

    async def fetch(self, *, vin, year, make, model, trim, mileage, zip_code, radius, dealer_type, **opts) -> dict:
        seed = hashlib.sha1(f"{vin or ''}|{year}|{make}|{model}|{trim}|{mileage}|{zip_code}|{radius}".encode()).hexdigest()
        rng = random.Random(seed)
        retail = mock_retail(year, make, model, mileage)
        age = max(0, time.gmtime().tm_year - int(year or time.gmtime().tm_year))
        msrp = int(round(retail / max(0.2, 0.87 ** min(age, 15)) / 100) * 100)
        city, state = _CITIES.get(str(zip_code or "8")[0], ("Sandy", "UT"))
        our_miles = int(mileage) if mileage is not None else age * 12500
        trims = [t for t in _TRIMS if t.lower() != (trim or "").lower()]
        listings = []
        for i in range(rng.randint(11, 16)):
            yr = int(year or time.gmtime().tm_year) + rng.choice((-1, 0, 0, 0, 0, 1))
            tr = (trim or rng.choice(_TRIMS)) if rng.random() < 0.55 else rng.choice(trims)
            mi = max(500, int(our_miles * rng.uniform(0.78, 1.3)))
            price = retail * (1 + (our_miles - mi) * 0.07 / max(retail, 1)) * rng.uniform(0.93, 1.09) + (yr - int(year or yr)) * 900
            dist = round(rng.uniform(2, min(radius or DEFAULT_RADIUS, 100)), 1)
            cert = rng.random() < 0.2
            listings.append({"listing_id": f"mock-{seed[:6]}-{i}", "vin": None, "year": yr, "make": make, "model": model, "trim": tr, "mileage": mi,
                             "price": int(round(price / 25) * 25 + (900 if cert else 0)), "msrp": msrp, "distance_mi": dist, "dealer_name": rng.choice(_DEALERS),
                             "dealer_type": rng.choice(DEALER_TYPES), "city": city, "state": state, "zip": str(zip_code or ""), "dom": rng.randint(4, 95),
                             "dom_active": rng.randint(3, 60), "exterior_color": rng.choice(_COLORS), "is_certified": cert, "vdp_url": None, "photo_url": None,
                             "first_seen_at": int(time.time()) - rng.randint(3, 90) * 86400, "heading": f"{yr} {make} {model} {tr}", "body_type": None, "drivetrain": None})
        prices = sorted(l["price"] for l in listings)
        miles_ = sorted(l["mileage"] for l in listings)
        doms = sorted(l["dom"] for l in listings)
        n = len(listings)
        stats = {k: {"mean": int(sum(v) / n), "median": v[n // 2], "min": v[0], "max": v[-1], "count": n, "stddev": int((sum((x - sum(v) / n) ** 2 for x in v) / n) ** 0.5),
                     "p25": v[n // 4], "p75": v[(3 * n) // 4]} for k, v in (("price", prices), ("miles", miles_), ("dom", doms))}
        return {"prediction": {"predicted_retail": retail, "msrp": msrp, "estimated_wholesale": int(round(retail * 0.86 / 50) * 50), "model": "Mock depreciation curve"},
                "listings": listings, "stats": stats, "num_found": n + rng.randint(2, 30), "quota": {}, "raw": {"mock": True, "seed": seed}, "calls": 0,
                "notes": ["Development data generated on this server. Not a market quote. Add MARKETCHECK_API_KEY to go live."]}


# ---------- registry ----------
PROVIDERS = {p.name: p for p in (MarketCheckProvider(), VinAuditProvider(), MockMarketProvider())}
LIVE_PROVIDERS = ("marketcheck", "vinaudit")


def get(name: Optional[str]) -> Optional[MarketDataProvider]:
    return PROVIDERS.get((name or "").strip().lower())


def forced() -> Optional[MarketDataProvider]:
    """MARKET_DATA_PROVIDER forces a provider on purpose (dev / preview). Only honoured when that provider is configured; never silent (badges)."""
    f = get(os.environ.get("MARKET_DATA_PROVIDER"))
    return f if f and f.configured() else None


def active() -> MarketDataProvider:
    """Platform default when no dealership rule says otherwise: the forced provider, else MarketCheck when the key is present, else the mock."""
    f = forced()
    if f:
        return f
    mc = PROVIDERS["marketcheck"]
    return mc if mc.configured() else PROVIDERS["mock"]


def for_rules(market_rules: Optional[dict]) -> tuple:
    """(primary, fallback | None) from dealership rules. A configured primary wins; an unconfigured one degrades to development data (badged), never to
    the other live provider. The fallback is only returned when the rules name it AND it is configured AND it differs from the primary."""
    f = forced()
    if f:
        return f, None
    mr = market_rules or {}
    primary = get(mr.get("primary")) or PROVIDERS["marketcheck"]
    prov = primary if primary.configured() else PROVIDERS["mock"]
    fb = get(mr.get("fallback")) if (mr.get("fallback") or "none") != "none" else None
    fb = fb if (fb and fb.live and fb.configured() and fb.name != prov.name and prov.live) else None
    return prov, fb


def provider_options() -> list:
    act = active().name
    return [{"name": p.name, "label": p.label, "live": p.live, "badge": p.badge, "configured": p.configured(), "active": p.name == act,
             "calls_per_fetch": p.calls_per_fetch, "comps_kind": p.comps_kind} for p in PROVIDERS.values()]


# ---------- in-process token buckets (per user / per store) ----------
class TokenBucket:
    def __init__(self, capacity: int, refill_per_s: float):
        self.capacity, self.refill, self._state = capacity, refill_per_s, {}

    def take(self, key: str) -> tuple:
        """-> (allowed, retry_after_seconds)."""
        now = time.monotonic()
        tokens, last = self._state.get(key, (float(self.capacity), now))
        tokens = min(float(self.capacity), tokens + (now - last) * self.refill)
        if tokens >= 1:
            self._state[key] = (tokens - 1, now)
            return True, 0.0
        self._state[key] = (tokens, now)
        return False, (1 - tokens) / self.refill


USER_BUCKET = TokenBucket(capacity=6, refill_per_s=6 / 60)      # 6 refreshes a minute per rep
STORE_BUCKET = TokenBucket(capacity=30, refill_per_s=30 / 60)   # 30 a minute per store


def check_rate(user_id: str, store_id: Optional[str]):
    ok, wait = USER_BUCKET.take(f"u:{user_id}")
    if not ok:
        raise MarketRateLimited(wait)
    ok, wait = STORE_BUCKET.take(f"s:{store_id or user_id}")
    if not ok:
        raise MarketRateLimited(wait)
