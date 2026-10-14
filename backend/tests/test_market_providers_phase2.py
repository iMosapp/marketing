"""Provider validation phase: VinAuditProvider inside the existing MarketDataProvider abstraction, dealership market rules (primary / fallback / comparison),
admin provider comparison that never averages, call ledger, failure behaviour and security. Live keys are never needed: both providers run on httpx.MockTransport.
API-level checks run against the preview backend (mock provider there) using the shared QA accounts."""
import json
import os
import sys

import httpx
import pytest
from dotenv import load_dotenv
from tests import qa_creds

sys.path.insert(0, "/app/backend")
sys.path.insert(0, "/app/backend/tests")
load_dotenv("/app/backend/.env")
from _http import call, login, auth  # noqa: E402
from services.appraisals import market, market_providers as mp, rules as rulesvc, engine  # noqa: E402

REP = ("activation-tester@invalid.imonsocial.test", qa_creds.password_for("activation-tester@invalid.imonsocial.test"))
MANAGER = ("qa-manager@invalid.imonsocial.test", qa_creds.password_for("qa-manager@invalid.imonsocial.test"))
OTHER_ORG_ADMIN = ("qa-orgadmin@invalid.imonsocial.test", qa_creds.password_for("qa-orgadmin@invalid.imonsocial.test"))
SARAH = "6aa413008f0d53e3f2261853"
VIN = "1FTEW1EP5KFA12345"
SENTINEL_MC, SENTINEL_VA = "SENTINEL-MC-KEY-7731", "SENTINEL-VA-KEY-9920"

VA_RETAIL = {"vin": VIN, "success": True, "id": "2019_ford_f-150_xlt", "vehicle": "2019 Ford F-150 XLT", "mean": 32400.4, "stdev": 2100, "count": 188, "mileage": 61200, "certainty": 97,
             "period": ["2026-07-09", "2026-10-07"], "prices": {"above": 34500.4, "average": 32400.4, "below": 30300.4, "distribution": [{"group": {"count": 40, "max": 29900, "min": 27500}}, {"group": {"count": 60, "max": 33000, "min": 29900}}, {"group": {"count": 88, "max": 37900, "min": 33000}}]},
             "adjustments": {"mileage": {"adjustment": -350, "average": 68000.5, "input": 61200}, "history": {"records": [], "adjustment": 0}, "condition": {"input": None, "adjustment": 0}, "known_damage": {"input": None, "adjustment": 0}}, "type": "retail"}
VA_TRADEIN = {**VA_RETAIL, "mean": 27950.0, "type": "tradein"}
MC_PREDICT = {"marketcheck_price": 34850, "msrp": 44120}
MC_SEARCH = {"num_found": 12, "listings": [
    {"id": "l1", "vin": "1FTEW1EP0KFA00001", "price": 35990, "miles": 58000, "dom": 21, "dist": 8.4, "dealer": {"name": "Ken Garff Ford", "dealer_type": "franchise", "city": "Salt Lake City", "state": "UT"}, "build": {"year": 2019, "make": "Ford", "model": "F-150", "trim": "XLT"}},
    {"id": "l2", "vin": "1FTEW1EP0KFA00002", "price": 33500, "miles": 70000, "dom": 40, "dist": 20.0, "dealer": {"name": "Larry H. Miller", "dealer_type": "franchise", "city": "Provo", "state": "UT"}, "build": {"year": 2019, "make": "Ford", "model": "F-150", "trim": "XLT"}},
    {"id": "l3", "vin": "1FTEW1EP0KFA00003", "price": 34900, "miles": 61000, "dom": 12, "dist": 31.0, "dealer": {"name": "Tim Dahle", "dealer_type": "franchise", "city": "Sandy", "state": "UT"}, "build": {"year": 2019, "make": "Ford", "model": "F-150", "trim": "XLT"}}],
    "stats": {"price": {"min": 33500, "max": 35990, "count": 3, "mean": 34797, "median": 34900, "stddev": 1020, "percentiles": {"25.0": 33500, "75.0": 35990}}, "miles": {"mean": 63000, "median": 61000, "min": 58000, "max": 70000, "count": 3}, "dom": {"mean": 24, "median": 21, "min": 12, "max": 40, "count": 3}}}
TARGET = dict(vin=VIN, year=2019, make="Ford", model="F-150", trim="XLT", mileage=61200, zip_code="84070", radius=100, dealer_type="franchise")


def va_provider(handler):
    os.environ["VINAUDIT_API_KEY"] = SENTINEL_VA
    return mp.VinAuditProvider(transport=httpx.MockTransport(handler))


def mc_provider(handler):
    os.environ["MARKETCHECK_API_KEY"] = SENTINEL_MC
    return mp.MarketCheckProvider(transport=httpx.MockTransport(handler))


def va_ok(req: httpx.Request):
    assert req.url.host == "marketvalue.vinaudit.com" and req.url.path == "/v2/marketvalue"
    assert req.url.params["key"] == SENTINEL_VA and req.url.params["vin"] == VIN and req.url.params["format"] == "json"
    return httpx.Response(200, json=VA_TRADEIN if req.url.params.get("type") == "tradein" else VA_RETAIL)


def mc_ok(req: httpx.Request):
    assert req.url.params["api_key"] == SENTINEL_MC
    return httpx.Response(200, json=MC_PREDICT if "predict" in req.url.path else MC_SEARCH, headers={"Quota-Remaining": "4990"})


# ---------- VinAudit normalization ----------
@pytest.mark.asyncio
async def test_vinaudit_retail_and_tradein_normalize_into_the_existing_contract():
    seen = []

    def handler(req):
        seen.append(dict(req.url.params))
        return va_ok(req)

    res = await va_provider(handler).fetch(**TARGET, value_types=("retail", "tradein"))
    assert [s["type"] for s in seen] == ["retail", "tradein"] and all(s["mileage"] == "61200" and s["period"] == "90" for s in seen) and "zip" not in seen[0]
    assert res["calls"] == 2 and res["listings"] == [] and res["num_found"] == 188
    p = res["prediction"]
    assert p["predicted_retail"] == 32400 and p["model"] == "VinAudit Market Value (retail)" and p["certainty"] == 97 and p["sample_count"] == 188
    assert p["estimated_trade_in"] == 27950 and p["trade_in_source"] == "vinaudit_tradein" and "estimated_wholesale" not in p, "trade-in is trade-in; nothing is relabelled wholesale"
    assert p["price_band"] == {"below": 30300, "average": 32400, "above": 34500} and p["lookup_id"] == "2019_ford_f-150_xlt" and p["mileage_used"] == 61200
    assert res["stats"]["price"] == {"mean": 32400, "median": None, "min": 27500, "max": 37900, "count": 188, "stddev": 2100, "p25": None, "p75": None}
    assert res["stats"]["miles"]["mean"] == 68000
    assert set(res["raw"]) == {"retail", "tradein"} and res["raw"]["retail"]["type"] == "retail", "raw payloads kept separately per value type"
    assert SENTINEL_VA not in json.dumps(res), "the key never leaks into the normalized result"


@pytest.mark.asyncio
async def test_vinaudit_default_is_retail_only_one_call_and_missing_mileage_is_noted():
    seen = []

    def handler(req):
        seen.append(dict(req.url.params))
        return va_ok(req)

    res = await va_provider(handler).fetch(**{**TARGET, "mileage": None})
    assert len(seen) == 1 and seen[0]["type"] == "retail" and "mileage" not in seen[0] and res["calls"] == 1
    assert "estimated_trade_in" not in res["prediction"] and any("average mileage" in n for n in res["notes"])


@pytest.mark.asyncio
async def test_vinaudit_requires_a_17_char_vin():
    with pytest.raises(mp.MarketUnavailable):
        await va_provider(va_ok).fetch(**{**TARGET, "vin": None})
    with pytest.raises(mp.MarketUnavailable):
        await va_provider(va_ok).fetch(**{**TARGET, "vin": "SHORT"})


@pytest.mark.asyncio
async def test_vinaudit_zip_probe_is_explicit_and_noted():
    seen = []

    def handler(req):
        seen.append(dict(req.url.params))
        return va_ok(req)

    res = await va_provider(handler).fetch(**TARGET, send_zip=True)
    assert seen[0]["zip"] == "84070" and any("probe" in n for n in res["notes"])


@pytest.mark.asyncio
async def test_vinaudit_error_codes():
    async def run(payload, status=200):
        return await va_provider(lambda req: httpx.Response(status, json=payload)).fetch(**TARGET)

    for code in ("invalid_vin", "no_data"):
        with pytest.raises(mp.MarketUnavailable) as e:
            await run({"success": False, "error": "x", "vin": VIN, "data": code})
        assert "VinAudit" in str(e.value)
    with pytest.raises(mp.MarketQuotaExceeded) as e:
        await run({"success": False, "error": "rate_limit_exceeded"})
    assert e.value.monthly is False
    with pytest.raises(mp.MarketQuotaExceeded) as e:
        await run({"success": False, "error": "billing_limit_exceeded"})
    assert e.value.monthly is True
    with pytest.raises(mp.MarketUnavailable) as e:
        await run({"success": False, "error": "invalid_key"})
    assert "VINAUDIT_API_KEY" in str(e.value)
    with pytest.raises(mp.MarketQuotaExceeded):
        await run({}, status=429)
    with pytest.raises(mp.MarketUnavailable):
        await run({}, status=401)


@pytest.mark.asyncio
async def test_vinaudit_retries_once_on_5xx_then_gives_up():
    n = {"c": 0}

    def flaky(req):
        n["c"] += 1
        return httpx.Response(503, text="down")

    with pytest.raises(mp.MarketUnavailable):
        await va_provider(flaky).fetch(**TARGET)
    assert n["c"] == 2


@pytest.mark.asyncio
async def test_vinaudit_tradein_failure_keeps_retail():
    def handler(req):
        if req.url.params.get("type") == "tradein":
            return httpx.Response(200, json={"success": False, "data": "no_data", "error": "x"})
        return va_ok(req)

    res = await va_provider(handler).fetch(**TARGET, value_types=("retail", "tradein"))
    assert res["prediction"]["predicted_retail"] == 32400 and "estimated_trade_in" not in res["prediction"] and any("tradein" in n for n in res["notes"])


# ---------- summarize / confidence / engine with a VinAudit snapshot ----------
@pytest.mark.asyncio
async def test_summary_of_a_vinaudit_fetch_uses_provider_band_and_certainty_and_engine_treats_it_as_vinaudit():
    res = await va_provider(va_ok).fetch(**TARGET, value_types=("retail", "tradein"))
    r = market._summarize(res["prediction"], [], res["stats"], res["num_found"], 61200, mp.PROVIDERS["vinaudit"], res["notes"])
    assert r["estimated_retail"] == 32400 and r["retail_source"] == "vinaudit_retail" and r["estimated_wholesale"] is None and r["estimated_trade_in"] == 27950
    assert r["price_range"] == {"low": 30300, "high": 34500} and "band" in r["price_range_basis"] and r["comps_used"] == 0 and r["listing_count"] == 188 and r["comps_kind"] == "sales records"
    assert r["avg_market_price"] == 32400 and r["median_market_price"] is None and r["avg_miles"] == 68000 and r["mileage_vs_market"] == -6800
    assert r["confidence"]["level"] == "high" and r["confidence"]["score"] == 97 and r["provider_certainty"] == 97
    mkt = {"live": True, "estimated_retail": r["estimated_retail"], "retail_source": r["retail_source"], "provider_label": "VinAudit", "comps_used": 0, "median_market_price": None}
    b = engine.resolve_basis(rulesvc.DEFAULT_RULES, mkt, [], None, False)
    assert b and b["key"] == "provider_retail" and b["amount"] == 32400 and "VinAudit" in b["reason"]
    assert engine.resolve_basis(rulesvc.DEFAULT_RULES, {**mkt, "live": False}, [], None, False) is None, "development data is still refused as a basis in production"


def test_confidence_capped_on_thin_vinaudit_samples():
    c = market.confidence({"certainty": 99, "sample_count": 3, "model": "VinAudit Market Value (retail)"}, [], 3)
    assert c["level"] == "low" and c["score"] == 44
    c = market.confidence({"certainty": 99, "sample_count": 7, "model": "VinAudit Market Value (retail)"}, [], 7)
    assert c["level"] == "medium" and c["score"] == 70


# ---------- rules ----------
def test_market_rules_validate_and_default():
    d = rulesvc.validate({})["market"]
    assert d == {**rulesvc.DEFAULT_RULES["market"]} and d["primary"] == "marketcheck" and d["fallback"] == "none" and d["comparison"] is False
    ok = rulesvc.validate({"market": {"primary": "marketcheck", "fallback": "vinaudit", "comparison": True}})["market"]
    assert ok["fallback"] == "vinaudit" and ok["comparison"] is True
    for bad in ({"primary": "kbb"}, {"primary": "vinaudit", "fallback": "vinaudit"}, {"fallback": "mock"}):
        with pytest.raises(ValueError):
            rulesvc.validate({"market": bad})


def test_for_rules_never_substitutes_the_other_live_provider_silently(monkeypatch):
    monkeypatch.delenv("MARKET_DATA_PROVIDER", raising=False)
    monkeypatch.setenv("MARKETCHECK_API_KEY", "")
    monkeypatch.setenv("VINAUDIT_API_KEY", SENTINEL_VA)
    prov, fb = mp.for_rules({"primary": "marketcheck", "fallback": "none"})
    assert prov.name == "mock" and fb is None, "unconfigured primary degrades to badged development data, not to VinAudit"
    prov, fb = mp.for_rules({"primary": "marketcheck", "fallback": "vinaudit"})
    assert prov.name == "mock" and fb is None, "fallback only applies when the primary is live"
    monkeypatch.setenv("MARKETCHECK_API_KEY", SENTINEL_MC)
    prov, fb = mp.for_rules({"primary": "marketcheck", "fallback": "vinaudit"})
    assert prov.name == "marketcheck" and fb.name == "vinaudit"
    prov, fb = mp.for_rules({"primary": "marketcheck", "fallback": "none"})
    assert prov.name == "marketcheck" and fb is None
    prov, fb = mp.for_rules({"primary": "vinaudit", "fallback": "marketcheck"})
    assert prov.name == "vinaudit" and fb.name == "marketcheck"


# ---------- compare / refresh through market.py with mocked providers and a real DB ----------
class FakeUploads:
    def __call__(self, *a, **k):
        raise RuntimeError("no object storage in tests")


@pytest.fixture
def db():
    from motor.motor_asyncio import AsyncIOMotorClient
    return AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


@pytest.fixture
def admin_me():
    return {"_id": __import__("bson").ObjectId(), "role": "super_admin", "name": "Lab Admin", "organization_id": "org-lab", "store_id": "store-lab"}


def _patch_providers(monkeypatch, mc_handler, va_handler):
    monkeypatch.setenv("MARKETCHECK_API_KEY", SENTINEL_MC)
    monkeypatch.setenv("VINAUDIT_API_KEY", SENTINEL_VA)
    monkeypatch.delenv("MARKET_DATA_PROVIDER", raising=False)
    monkeypatch.setitem(mp.PROVIDERS, "marketcheck", mp.MarketCheckProvider(transport=httpx.MockTransport(mc_handler)))
    monkeypatch.setitem(mp.PROVIDERS, "vinaudit", mp.VinAuditProvider(transport=httpx.MockTransport(va_handler)))
    monkeypatch.setattr(market, "put_object", FakeUploads())
    monkeypatch.setattr(market, "_month", lambda: TEST_MONTH)
    mp.USER_BUCKET._state.clear()
    mp.STORE_BUCKET._state.clear()


TEST_MONTH = "0000-test"


async def _cleanup(db, admin_me):
    await db[market.SNAP].delete_many({"organization_id": "org-lab"})
    await db[market.COMP].delete_many({"organization_id": "org-lab"})
    await db[market.CALLS].delete_many({"user_id": str(admin_me["_id"])})
    await db[market.COMPARISONS].delete_many({"user_id": str(admin_me["_id"])})
    await db[market.USAGE].delete_many({"month": TEST_MONTH})


@pytest.mark.asyncio
async def test_compare_keeps_two_observations_separate_and_never_averages(db, monkeypatch, admin_me):
    _patch_providers(monkeypatch, mc_ok, va_ok)
    c = await market.compare(db, admin_me, vehicle={"vin": VIN, "year": 2019, "make": "Ford", "model": "F-150", "trim": "XLT"}, mileage=61200, zip_code="84070", radius=100, force=True)
    cards = {x["provider"]: x for x in c["providers"]}
    mc, va = cards["marketcheck"], cards["vinaudit"]
    assert mc["status"] == "ok" and mc["estimated_retail"] == 34850 and mc["estimated_wholesale"] is None and mc["estimated_trade_in"] is None and mc["comps_count"] == 3 and mc["comps_median"] == 34900 and mc["comps_kind"] == "active listings"
    assert mc["zip"] == "84070" and mc["radius"] == 100 and mc["zip_applies"] is True and mc["live"] is True and mc["calls"] == 2 and mc["confidence"]["level"] in ("high", "medium")
    assert va["status"] == "ok" and va["estimated_retail"] == 32400 and va["estimated_trade_in"] == 27950 and va["estimated_wholesale"] is None and va["comps_count"] == 188 and va["comps_kind"] == "sales records"
    assert va["zip_applies"] is False and va["calls"] == 2 and va["provider_certainty"] == 97 and va["lookup_id"] == "2019_ford_f-150_xlt"
    d = c["difference"]
    assert d["available"] and d["dollars"] == 2450 and d["percent"] == 7.3 and d["higher"] == "marketcheck"
    blob = json.dumps(c, default=str).lower()
    assert "combined" not in blob and "33625" not in blob and SENTINEL_MC.lower() not in blob and SENTINEL_VA.lower() not in blob
    assert c["calls_total"] == 4 and c["purpose"] == "comparison"
    snaps = await db[market.SNAP].find({"requested.vin": VIN, "purpose": "comparison", "organization_id": "org-lab"}).to_list(10)
    assert len(snaps) >= 2 and all(s["is_latest"] is False and s["appraisal_id"] is None for s in snaps), "comparison snapshots never become a snapshot of record"
    rows = await db[market.CALLS].find({"user_id": str(admin_me["_id"])}).to_list(10)
    assert sorted((r["provider"], r["calls"], r["ok"]) for r in rows) == [("marketcheck", 2, True), ("vinaudit", 2, True)]
    # cache: the same request within 24h reuses both answers and spends nothing
    again = await market.compare(db, admin_me, vehicle={"vin": VIN, "year": 2019, "make": "Ford", "model": "F-150", "trim": "XLT"}, mileage=61200, zip_code="84070", radius=100)
    assert all(x["cached"] for x in again["providers"]) and again["calls_total"] == 0
    forced = await market.compare(db, admin_me, vehicle={"vin": VIN, "year": 2019, "make": "Ford", "model": "F-150", "trim": "XLT"}, mileage=61200, zip_code="84070", radius=100, force=True)
    assert not any(x["cached"] for x in forced["providers"]) and forced["calls_total"] == 4
    await _cleanup(db, admin_me)


@pytest.mark.asyncio
async def test_compare_when_one_or_both_providers_fail(db, monkeypatch, admin_me):
    def mc_down(req):
        return httpx.Response(500, text="boom")

    _patch_providers(monkeypatch, mc_down, va_ok)
    c = await market.compare(db, admin_me, vehicle={"vin": VIN, "year": 2019, "make": "Ford", "model": "F-150"}, mileage=61200, zip_code="84070", force=True)
    cards = {x["provider"]: x for x in c["providers"]}
    assert cards["marketcheck"]["status"] == "error" and cards["marketcheck"]["estimated_retail"] is None and "MarketCheck" in cards["marketcheck"]["error"]
    assert cards["vinaudit"]["status"] == "ok" and cards["vinaudit"]["estimated_retail"] == 32400, "VinAudit keeps working when MarketCheck fails"
    assert c["difference"]["available"] is False
    failed = await db[market.CALLS].find_one({"user_id": str(admin_me["_id"]), "provider": "marketcheck", "ok": False})
    assert failed and failed["calls_estimated"] is True

    def va_down(req):
        return httpx.Response(200, json={"success": False, "error": "rate_limit_exceeded"})

    _patch_providers(monkeypatch, mc_ok, va_down)
    c = await market.compare(db, admin_me, vehicle={"vin": VIN, "year": 2019, "make": "Ford", "model": "F-150"}, mileage=61200, zip_code="84071", force=True)
    cards = {x["provider"]: x for x in c["providers"]}
    assert cards["marketcheck"]["status"] == "ok" and cards["marketcheck"]["estimated_retail"] == 34850, "MarketCheck keeps working when VinAudit fails"
    assert cards["vinaudit"]["status"] == "quota" and cards["vinaudit"]["estimated_retail"] is None

    _patch_providers(monkeypatch, mc_down, va_down)
    c = await market.compare(db, admin_me, vehicle={"vin": VIN, "year": 2019, "make": "Ford", "model": "F-150"}, mileage=61200, zip_code="84072", force=True)
    assert all(x["status"] != "ok" and x["estimated_retail"] is None for x in c["providers"]) and c["difference"]["available"] is False, "both fail: no value is invented"
    await _cleanup(db, admin_me)


@pytest.mark.asyncio
async def test_compare_requires_zip_and_vehicle(db, monkeypatch, admin_me):
    _patch_providers(monkeypatch, mc_ok, va_ok)
    with pytest.raises(ValueError):
        await market.compare(db, admin_me, vehicle={"vin": VIN, "year": 2019, "make": "Ford", "model": "F-150"}, mileage=61200, zip_code=None)
    with pytest.raises(ValueError):
        await market.compare(db, admin_me, vehicle={"vin": VIN}, mileage=61200, zip_code="84070")


@pytest.mark.asyncio
async def test_refresh_fallback_only_when_rules_name_it(db, monkeypatch, admin_me):
    from bson import ObjectId

    def mc_down(req):
        return httpx.Response(503, text="maintenance")

    _patch_providers(monkeypatch, mc_down, va_ok)
    appr = {"_id": ObjectId(), "user_id": str(admin_me["_id"]), "store_id": "store-lab", "organization_id": "org-lab", "vin": VIN, "vehicle": {"year": 2019, "make": "Ford", "model": "F-150", "trim": "XLT", "vin": VIN},
            "mileage_confirmed": 61200, "contact_id": None, "vehicle_id": None, "deleted": False, "status": "draft"}
    await db[market.A].insert_one(appr)
    try:
        async def rules_none(db_, org, store):
            return {"primary": "marketcheck", "fallback": "none", "comparison": False}
        monkeypatch.setattr(market, "market_rules_for", rules_none)
        with pytest.raises(mp.MarketUnavailable):
            await market.refresh(db, appr, admin_me, zip_code="84070", force=True)
        assert await market.latest_snapshot(db, appr) is None, "no snapshot, no number: the engine will ask for a book value or the manager"

        async def rules_fb(db_, org, store):
            return {"primary": "marketcheck", "fallback": "vinaudit", "comparison": False}
        monkeypatch.setattr(market, "market_rules_for", rules_fb)
        res = await market.refresh(db, appr, admin_me, zip_code="84070", force=True)
        s = res["snapshot"]
        assert s["provider"] == "vinaudit" and s["fallback_from"] == "marketcheck" and s["live"] is True and s["result"]["estimated_retail"] == 32400 and s["result"]["retail_source"] == "vinaudit_retail"
        assert s["requested"]["provider"] == "vinaudit" and s["is_latest"] is True and s["purpose"] == "appraisal"
        acts = await db["appraisal_activity"].find({"appraisal_id": str(appr["_id"])}).to_list(20)
        assert {a["action"] for a in acts} >= {"market_fetch_failed", "market_fallback", "market_snapshot"}
        a2 = await db[market.A].find_one({"_id": appr["_id"]})
        assert a2["market_summary"]["provider"] == "vinaudit" and a2["market_summary"]["fallback_from"] == "marketcheck"
    finally:
        await db[market.A].delete_one({"_id": appr["_id"]})
        await db["appraisal_activity"].delete_many({"appraisal_id": str(appr["_id"])})
        await _cleanup(db, admin_me)
        await db[market.SNAP].delete_many({"appraisal_id": str(appr["_id"])})


# ---------- API: tenant isolation + no credentials in payloads (preview backend, mock provider) ----------
@pytest.fixture(scope="module")
def rep():
    return auth(*login(*REP))


@pytest.fixture(scope="module")
def manager():
    return auth(*login(*MANAGER))


@pytest.fixture(scope="module")
def stranger():
    return auth(*login(*OTHER_ORG_ADMIN))


def test_providers_route_lists_vinaudit_and_never_returns_keys(manager, rep):
    st, b = call("GET", "/api/appraisals/providers", None, manager)
    assert st == 200, b
    names = {p["name"]: p for p in b["market"]}
    assert {"marketcheck", "vinaudit", "mock"} <= set(names) and names["vinaudit"]["live"] is True and names["vinaudit"]["comps_kind"] == "sales records"
    assert "configured" in names["vinaudit"] and sum(1 for p in b["market"] if p["active"]) == 1
    assert {u["provider"] for u in b["usage_all"]} == {"marketcheck", "vinaudit"} and all({"calls", "cap", "comparisons", "failures"} <= set(u) for u in b["usage_all"])
    assert b["market_rules"]["primary"] in ("marketcheck", "vinaudit") and "cost" in b and b["cost"]["month"]
    blob = json.dumps(b).lower()
    for bad in ("api_key", "vinaudit_api_key", "marketcheck_api_key", "key="):
        assert bad not in blob, bad
    assert "key_present" not in blob
    st, _ = call("GET", "/api/appraisals/providers", None, rep)
    assert st == 403


def test_comparison_routes_are_admin_only(manager, rep):
    for hdr in (rep, manager):
        st, b = call("POST", "/api/appraisals/providers/compare", {"vin": VIN, "mileage": 61200, "zip": "84070"}, hdr)
        assert st == 403, (st, b)
        st, _ = call("GET", "/api/appraisals/providers/comparisons", None, hdr)
        assert st == 403


def test_other_org_admin_sees_no_comparisons_and_cannot_compare_our_appraisal(stranger, rep):
    st, b = call("GET", "/api/appraisals/providers/comparisons", None, stranger)
    assert st == 200 and b["comparisons"] == [], b
    st, b = call("POST", "/api/appraisals", {"contact_id": SARAH, "mode": "vehicle_here"}, rep)
    assert st == 200
    aid = b["appraisal"]["id"]
    try:
        st, b = call("POST", f"/api/appraisals/{aid}/market/compare", {"zip": "84070"}, stranger)
        assert st == 404, (st, b)
        st, b = call("POST", f"/api/appraisals/{aid}/market/compare", {"zip": "84070"}, rep)
        assert st == 403
        st, b = call("GET", f"/api/appraisals/{aid}/market", None, rep)
        assert st == 200 and b["comparison"]["allowed"] is False and b["comparison"]["latest"] is None and "fallback" in b["provider"]
    finally:
        call("DELETE", f"/api/appraisals/{aid}", None, rep)


def test_rules_payload_exposes_market_provider_options(manager):
    st, b = call("GET", "/api/appraisals/rules", None, manager)
    assert st == 200, b
    assert set(b["options"]["market_providers"]) == {"marketcheck", "vinaudit"} and b["effective"]["rules"]["market"]["primary"] in ("marketcheck", "vinaudit")
    assert "configured" in b["options"]["market_providers"]["vinaudit"]
