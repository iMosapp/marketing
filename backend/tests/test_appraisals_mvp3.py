"""Trade Appraisal MVP3 - Market data + comparables + valuation foundation. Runs against the preview backend (mock provider, no MarketCheck key)
plus in-process unit tests for the MarketCheck provider (httpx.MockTransport), match quality, confidence and the token bucket."""
import os
import sys
import time
import urllib.error
import urllib.request
import json

import httpx
import pytest
from dotenv import load_dotenv

sys.path.insert(0, "/app/backend")
sys.path.insert(0, "/app/backend/tests")
load_dotenv("/app/backend/.env")
from _http import call, login, auth, API, UA  # noqa: E402
from services.appraisals import market, market_providers as mp  # noqa: E402

REP = ("activation-tester@invalid.imonsocial.test", "NewPass123!")
MANAGER = ("qa-manager@invalid.imonsocial.test", "Manager123!")
OTHER_ORG_ADMIN = ("qa-orgadmin@invalid.imonsocial.test", "OrgAdmin123!")
SARAH = "6aa413008f0d53e3f2261853"


def _new_appraisal(hdr, year=2019, make="Ford", model="F-150", trim="XLT", miles=61200):
    st, b = call("POST", "/api/appraisals", {"contact_id": SARAH, "mode": "vehicle_here"}, hdr)
    assert st == 200, (st, b)
    aid = b["appraisal"]["id"]
    st, _ = call("POST", f"/api/appraisals/{aid}/vehicle", {"manual": {"year": year, "make": make, "model": model, "trim": trim}, "method": "manual_vehicle"}, hdr)
    assert st == 200
    st, _ = call("POST", f"/api/appraisals/{aid}/mileage", {"confirmed": miles, "source": "manual"}, hdr)
    assert st == 200
    return aid


@pytest.fixture(scope="module")
def rep():
    return auth(*login(*REP))


@pytest.fixture(scope="module")
def manager():
    return auth(*login(*MANAGER))


@pytest.fixture(scope="module")
def stranger():
    return auth(*login(*OTHER_ORG_ADMIN))


@pytest.fixture(scope="module")
def appraisal(rep):
    aid = _new_appraisal(rep)
    yield aid
    call("DELETE", f"/api/appraisals/{aid}", None, rep)


# ---------- flow against the preview backend (mock provider) ----------
def test_meta_has_market_step_and_provider(rep):
    st, b = call("GET", "/api/appraisals/meta", None, rep)
    assert st == 200
    assert b["steps"] == ["customer", "mode", "identity", "mileage", "inspection", "market", "expectation", "review"]
    assert b["market_provider"]["name"] in ("mock", "marketcheck")
    if b["market_provider"]["name"] == "mock":
        assert b["market_provider"]["live"] is False and b["market_provider"]["badge"] == "DEVELOPMENT DATA — NOT LIVE"


def test_market_empty_then_refresh_builds_normalized_snapshot(rep, appraisal):
    st, b = call("GET", f"/api/appraisals/{appraisal}/market", None, rep)
    assert st == 200 and b["snapshot"] is None and b["comparables"] == [] and b["book_values"] == []
    assert b["provider"]["badge"] and "radius" in b["zip"]
    st, b = call("POST", f"/api/appraisals/{appraisal}/market/refresh", {"zip": "84070", "radius": 100}, rep)
    assert st == 200, (st, b)
    s, r = b["snapshot"], b["snapshot"]["result"]
    assert b["cached"] is False and s["is_latest"] is True
    assert s["requested"]["zip"] == "84070" and s["requested"]["radius"] == 100 and s["requested"]["car_type"] == "used"
    for k in ("estimated_retail", "estimated_wholesale", "price_range", "avg_market_price", "median_market_price", "listing_count", "comps_used", "avg_dom", "avg_miles",
              "mileage_vs_market", "confidence", "match_counts", "notes", "retail_source"):
        assert k in r, k
    assert r["estimated_retail"] > 0 and r["listing_count"] >= r["comps_used"] > 0
    assert r["confidence"]["level"] in ("high", "medium", "low") and r["confidence"]["reasons"]
    if not s["live"]:
        assert s["badge"] == "DEVELOPMENT DATA — NOT LIVE" and any("Development data" in n for n in r["notes"])
    comps = b["comparables"]
    assert len(comps) == r["comps_returned"] and comps[0]["rank"] == 1
    scores = [c["match"]["score"] for c in comps]
    assert scores == sorted(scores, reverse=True), "best comparables first"
    for c in comps:
        assert c["match"]["quality"] in ("exact", "strong", "close", "loose") and c["match"]["label"].endswith(" MATCH") and c["match"]["why"]
        assert c["make"] == "Ford" and c["price"] and c["mileage"]
    assert sum(r["match_counts"].values()) == len(comps)
    # appraisal now points at the snapshot and the detail payload carries the summary
    st, d = call("GET", f"/api/appraisals/{appraisal}", None, rep)
    assert st == 200 and d["market_snapshot_id"] == s["id"] and d["market_zip"] == "84070" and d["market"]["estimated_retail"] == r["estimated_retail"]
    assert any(a["action"] == "market_snapshot" for a in d["activity"])


def test_refresh_reuses_within_24h_and_force_adds_a_new_snapshot(rep, appraisal):
    st, first = call("GET", f"/api/appraisals/{appraisal}/market", None, rep)
    sid = first["snapshot"]["id"]
    st, b = call("POST", f"/api/appraisals/{appraisal}/market/refresh", {"zip": "84070", "radius": 100}, rep)
    assert st == 200 and b["cached"] is True and b["snapshot"]["id"] == sid
    st, b = call("POST", f"/api/appraisals/{appraisal}/market/refresh", {"zip": "84070", "radius": 100, "force": True}, rep)
    assert st == 200 and b["cached"] is False and b["snapshot"]["id"] != sid
    ids = [h["id"] for h in b["history"]]
    assert sid in ids and b["snapshot"]["id"] in ids and len(ids) >= 2, "older snapshots are kept, never overwritten"
    # a different ZIP is a different request -> new snapshot without force
    st, b2 = call("POST", f"/api/appraisals/{appraisal}/market/refresh", {"zip": "30301", "radius": 50}, rep)
    assert st == 200 and b2["cached"] is False and b2["snapshot"]["requested"]["zip"] == "30301" and b2["snapshot"]["requested"]["radius"] == 50
    st, b3 = call("GET", f"/api/appraisals/{appraisal}/market", None, rep)
    assert b3["zip"]["zip"] == "30301" and b3["zip"]["zip_source"] == "appraisal" and b3["zip"]["radius"] == 50


def test_refresh_validation(rep):
    aid = _new_appraisal(rep)
    try:
        st, b = call("POST", f"/api/appraisals/{aid}/market/refresh", {"zip": "12"}, rep)
        assert st == 400 and "ZIP" in b
    finally:
        call("DELETE", f"/api/appraisals/{aid}", None, rep)
    st, b = call("POST", "/api/appraisals", {"contact_id": SARAH, "mode": "vehicle_here"}, rep)
    aid = b["appraisal"]["id"]
    try:
        st, b = call("POST", f"/api/appraisals/{aid}/market/refresh", {"zip": "84070"}, rep)
        assert st == 400 and "year, make and model" in b
    finally:
        call("DELETE", f"/api/appraisals/{aid}", None, rep)


def test_book_values_crud(rep, appraisal):
    st, b = call("POST", f"/api/appraisals/{appraisal}/book-values", {"source": "black_book", "value_type": "wholesale", "value": 24500, "note": "Clean"}, rep)
    assert st == 200, (st, b)
    bv = b["book_values"]
    assert len(bv) == 1 and bv[0]["source_label"] == "Black Book" and bv[0]["value_type_label"] == "Wholesale" and bv[0]["value"] == 24500 and bv[0]["entered_by_name"]
    bid = bv[0]["id"]
    st, b = call("POST", f"/api/appraisals/{appraisal}/book-values", {"source": "other", "source_label": "Auction sheet", "value_type": "trade_in", "value": 23000}, rep)
    assert st == 200 and len(b["book_values"]) == 2 and b["book_values"][1]["source_label"] == "Auction sheet"
    st, b = call("PATCH", f"/api/appraisals/{appraisal}/book-values/{bid}", {"value": 25000, "note": "Adjusted for miles"}, rep)
    assert st == 200 and b["book_values"][0]["value"] == 25000 and b["book_values"][0]["note"] == "Adjusted for miles" and b["book_values"][0]["source"] == "black_book"
    st, b = call("POST", f"/api/appraisals/{appraisal}/book-values", {"source": "nope", "value": 1}, rep)
    assert st == 400
    st, b = call("POST", f"/api/appraisals/{appraisal}/book-values", {"source": "mmr", "value": 0}, rep)
    assert st == 400
    st, b = call("PATCH", f"/api/appraisals/{appraisal}/book-values/000000000000000000000000", {"value": 1000}, rep)
    assert st == 404
    st, d = call("GET", f"/api/appraisals/{appraisal}", None, rep)
    assert len(d["book_values"]) == 2 and d["book_values_count"] == 2 and d["market"]["book_values"] == 2
    acts = [a["action"] for a in d["activity"]]
    assert "book_value_added" in acts and "book_value_edited" in acts
    st, b = call("DELETE", f"/api/appraisals/{appraisal}/book-values/{bid}", None, rep)
    assert st == 200 and len(b["book_values"]) == 1 and b["book_values"][0]["source"] == "other"
    st, b = call("GET", f"/api/appraisals/{appraisal}/market", None, rep)
    assert len(b["book_values"]) == 1 and b["book_sources"]["mmr"] == "Manheim MMR" and b["value_types"]["trade_in"] == "Trade-in"


def test_tenant_isolation(rep, manager, stranger, appraisal):
    for method, path, body in (("GET", f"/api/appraisals/{appraisal}/market", None), ("POST", f"/api/appraisals/{appraisal}/market/refresh", {"zip": "84070", "force": True}),
                               ("POST", f"/api/appraisals/{appraisal}/book-values", {"source": "kbb", "value": 20000}), ("GET", f"/api/appraisals/{appraisal}", None)):
        st, _ = call(method, path, body, stranger)
        assert st == 404, (method, path, st)
    st, b = call("GET", f"/api/appraisals/{appraisal}/market", None, manager)
    assert st == 200 and b["snapshot"] is not None, "manager of the rep's store reads the rep's market data"
    st, b = call("GET", f"/api/appraisals/{appraisal}/market", None, rep)
    assert st == 200 and len(b["history"]) >= 3, "the stranger's refresh attempt added nothing"


def test_providers_route_is_manager_only(rep, manager):
    st, _ = call("GET", "/api/appraisals/providers", None, rep)
    assert st == 403
    st, b = call("GET", "/api/appraisals/providers", None, manager)
    assert st == 200, (st, b)
    names = {p["name"]: p for p in b["market"]}
    assert {"marketcheck", "mock"} <= set(names) and sum(1 for p in b["market"] if p["active"]) == 1
    assert names["marketcheck"]["live"] is True and names["mock"]["live"] is False
    assert names["marketcheck"]["badge"] == "Source: MarketCheck" and names["mock"]["badge"] == "DEVELOPMENT DATA — NOT LIVE"
    assert "usage" in b and b["usage"]["month"] and b["cache_hours"] == 24


def test_rate_limit_returns_429_with_retry_after(rep):
    aid = _new_appraisal(rep, year=2018, make="Toyota", model="Camry", trim="SE", miles=70000)
    try:
        seen = None
        for i in range(9):
            req = urllib.request.Request(API + f"/api/appraisals/{aid}/market/refresh", method="POST", data=json.dumps({"zip": "84070", "force": True}).encode(),
                                         headers={"Content-Type": "application/json", **UA, **rep})
            try:
                with urllib.request.urlopen(req, timeout=40) as r:
                    assert r.status == 200
            except urllib.error.HTTPError as e:
                seen = (e.code, e.headers.get("Retry-After"), e.read().decode()[:200])
                break
        assert seen and seen[0] == 429 and seen[1] and "Too many market refreshes" in seen[2], seen
    finally:
        call("DELETE", f"/api/appraisals/{aid}", None, rep)


# ---------- unit: I'm On Social calculations ----------
def test_match_quality_tiers():
    t = {"year": 2019, "trim": "XLT", "mileage": 60000}
    exact = market.match_quality(t, {"year": 2019, "trim": "XLT", "mileage": 62000, "distance_mi": 12})
    assert exact["quality"] == "exact" and exact["score"] == 100 and exact["label"] == "EXACT MATCH"
    strong = market.match_quality(t, {"year": 2018, "trim": "XLT", "mileage": 70000, "distance_mi": 20})
    assert strong["quality"] == "strong" and strong["score"] == 75 and "2018 vs your 2019" in strong["why"]
    close = market.match_quality(t, {"year": 2018, "trim": "Lariat", "mileage": 72000, "distance_mi": 20})
    assert close["quality"] == "close" and close["score"] == 55
    loose = market.match_quality(t, {"year": 2016, "trim": "Lariat", "mileage": 150000, "distance_mi": 150, "is_certified": True})
    assert loose["quality"] == "loose" and loose["score"] == 0
    unknown = market.match_quality(t, {"year": 2019, "trim": None, "mileage": None})
    assert unknown["quality"] == "strong" and unknown["score"] == 80 and "Trim not confirmed on one side" in unknown["why"]


def test_confidence_levels():
    comps_good = [{"price": 20000 + i * 100, "match": {"quality": "exact"}} for i in range(6)]
    c = market.confidence({"predicted_retail": 20300, "model": "x"}, comps_good, 40)
    assert c["level"] == "high" and c["score"] >= 75
    c = market.confidence(None, [{"price": 15000, "match": {"quality": "loose"}}, {"price": 30000, "match": {"quality": "loose"}}, {"price": 9000, "match": {"quality": "close"}}], 3)
    assert c["level"] == "low" and "No exact or strong matches nearby" in c["reasons"]
    c = market.confidence(None, [], 0)
    assert c["level"] == "low" and c["score"] == 0


def test_token_bucket():
    b = mp.TokenBucket(capacity=2, refill_per_s=100)
    assert b.take("k")[0] and b.take("k")[0]
    ok, wait = b.take("k")
    assert not ok and 0 < wait <= 0.011
    time.sleep(0.02)
    assert b.take("k")[0], "refills"
    assert b.take("other")[0], "buckets are per key"
    assert mp.MockMarketProvider().configured() and mp.MockMarketProvider().live is False


# ---------- unit: MarketCheck provider against a fake MarketCheck ----------
SEARCH_RESPONSE = {"num_found": 37, "listings": [
    {"id": "abc-1", "vin": "1FTEW1EP5KFA00001", "heading": "2019 Ford F-150 XLT", "price": 28990, "miles": 58000, "dom": 21, "dom_active": 14, "dist": 8.4, "inventory_type": "used",
     "exterior_color": "Oxford White", "vdp_url": "https://dealer.example/vdp/1", "first_seen_at": 1700000000, "media": {"photo_links": ["https://img.example/1.jpg"]},
     "dealer": {"id": 1, "name": "Ken Garff Ford", "dealer_type": "franchise", "city": "Salt Lake City", "state": "UT", "zip": "84101"},
     "build": {"year": 2019, "make": "Ford", "model": "F-150", "trim": "XLT", "body_type": "Pickup", "drivetrain": "4WD"}},
    {"id": "abc-2", "vin": "1FTEW1EP5KFA00002", "price": 26500, "miles": 81000, "dom": 65, "dist": 44.0, "inventory_type": "used", "is_certified": 1,
     "dealer": {"id": 2, "name": "Larry H. Miller", "dealer_type": "franchise", "city": "Provo", "state": "UT"}, "build": {"year": 2018, "make": "Ford", "model": "F-150", "trim": "Lariat"}}],
    "stats": {"price": {"min": 26500, "max": 28990, "count": 2, "mean": 27745, "median": 27745, "stddev": 1245, "percentiles": {"25.0": 26500, "75.0": 28990}},
              "miles": {"min": 58000, "max": 81000, "count": 2, "mean": 69500, "median": 69500}, "dom": {"mean": 43, "median": 43, "min": 21, "max": 65, "count": 2}}}


def _fake(handler):
    os.environ["MARKETCHECK_API_KEY"] = "test-key"
    return mp.MarketCheckProvider(transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_marketcheck_success_normalizes_prediction_listings_and_stats():
    seen = []

    def handler(req: httpx.Request):
        seen.append(req)
        assert req.url.params["api_key"] == "test-key", "auth is always the api_key query param"
        if req.url.path.endswith("/predict/car/us/marketcheck_price"):
            assert req.url.params["vin"] == "1FTEW1EP5KFA12345" and req.url.params["miles"] == "61200" and req.url.params["dealer_type"] == "franchise" and req.url.params["zip"] == "84070"
            return httpx.Response(200, json={"marketcheck_price": 27850, "msrp": 44120}, headers={"Quota-Remaining": "488", "RateLimit-Remaining": "4"})
        assert req.url.path.endswith("/search/car/active")
        p = req.url.params
        assert p["year"] == "2019" and p["make"] == "Ford" and p["model"] == "F-150" and p["car_type"] == "used" and p["rows"] == "50" and p["radius"] == "100" and p["stats"] == "price,miles,dom"
        return httpx.Response(200, json=SEARCH_RESPONSE, headers={"Quota-Remaining": "487"})

    res = await _fake(handler).fetch(vin="1FTEW1EP5KFA12345", year=2019, make="Ford", model="F-150", trim="XLT", mileage=61200, zip_code="84070", radius=100, dealer_type="franchise")
    assert len(seen) == 2 and res["calls"] == 2
    assert res["prediction"] == {"predicted_retail": 27850, "msrp": 44120, "model": "MarketCheck Price (ML)"}
    assert res["num_found"] == 37 and res["quota"]["quota_remaining"] == 487 and res["quota"]["rate_remaining"] == 4
    l = res["listings"][0]
    assert l["listing_id"] == "abc-1" and l["year"] == 2019 and l["trim"] == "XLT" and l["mileage"] == 58000 and l["price"] == 28990 and l["distance_mi"] == 8.4
    assert l["dealer_name"] == "Ken Garff Ford" and l["city"] == "Salt Lake City" and l["state"] == "UT" and l["photo_url"] == "https://img.example/1.jpg" and l["is_certified"] is False
    assert res["listings"][1]["is_certified"] is True and res["listings"][1]["trim"] == "Lariat"
    assert set(res["listings"][0]) == set(mp.LISTING_FIELDS)
    assert res["stats"]["price"]["median"] == 27745 and res["stats"]["price"]["p75"] == 28990 and res["stats"]["dom"]["mean"] == 43
    comps = [{**x, "match": market.match_quality({"year": 2019, "trim": "XLT", "mileage": 61200}, x)} for x in res["listings"]]
    summ = market._summarize(res["prediction"], comps, res["stats"], 37, 61200, mp.PROVIDERS["marketcheck"], [])
    assert summ["estimated_retail"] == 27850 and summ["retail_source"] == "marketcheck_price" and summ["estimated_wholesale"] is None and summ["wholesale_source"] is None
    assert summ["listing_count"] == 37 and summ["comps_used"] == 2 and summ["match_counts"]["exact"] == 1


@pytest.mark.asyncio
async def test_marketcheck_degrades_when_prediction_fails_but_search_works():
    def handler(req):
        if "predict" in req.url.path:
            return httpx.Response(400, json={"code": 400, "message": "VIN could not be decoded"})
        return httpx.Response(200, json=SEARCH_RESPONSE)

    res = await _fake(handler).fetch(vin="1FTEW1EP5KFA12345", year=2019, make="Ford", model="F-150", trim="XLT", mileage=61200, zip_code="84070", radius=100, dealer_type="franchise")
    assert res["prediction"] is None and len(res["listings"]) == 2 and any("could not price this VIN" in n for n in res["notes"])
    comps = [{**x, "match": market.match_quality({"year": 2019, "trim": "XLT", "mileage": 61200}, x)} for x in res["listings"]]
    summ = market._summarize(None, comps, res["stats"], 37, 61200, mp.PROVIDERS["marketcheck"], res["notes"])
    assert summ["retail_source"] == "comps_median" and summ["estimated_retail"] == 27745


@pytest.mark.asyncio
async def test_marketcheck_skips_prediction_without_vin():
    calls = []

    def handler(req):
        calls.append(req.url.path)
        return httpx.Response(200, json=SEARCH_RESPONSE)

    res = await _fake(handler).fetch(vin=None, year=2019, make="Ford", model="F-150", trim="XLT", mileage=61200, zip_code="84070", radius=100, dealer_type="franchise")
    assert calls == ["/v2/search/car/active"] and res["calls"] == 1 and res["prediction"] is None


@pytest.mark.asyncio
async def test_marketcheck_quota_and_rate_limit_handling():
    def monthly(req):
        return httpx.Response(429, json={"code": 429, "message": "quota"}, headers={"Quota-Remaining": "0", "Retry-After": "1814400"})

    with pytest.raises(mp.MarketQuotaExceeded) as ei:
        await _fake(monthly).fetch(vin="1FTEW1EP5KFA12345", year=2019, make="Ford", model="F-150", trim="XLT", mileage=61200, zip_code="84070", radius=100, dealer_type="franchise")
    assert ei.value.monthly is True and ei.value.retry_after == 1814400 and "monthly quota" in str(ei.value)

    def per_second(req):
        return httpx.Response(429, json={"code": 429, "message": "slow down"}, headers={"RateLimit-Remaining": "0", "Quota-Remaining": "300", "Retry-After": "1"})

    with pytest.raises(mp.MarketQuotaExceeded) as ei:
        await _fake(per_second).fetch(vin=None, year=2019, make="Ford", model="F-150", trim=None, mileage=None, zip_code="84070", radius=100, dealer_type="franchise")
    assert ei.value.monthly is False and ei.value.retry_after == 1

    def unauthorized(req):
        return httpx.Response(401, json={"code": 401, "message": "bad key"})

    with pytest.raises(mp.MarketUnavailable) as ei:
        await _fake(unauthorized).fetch(vin=None, year=2019, make="Ford", model="F-150", trim=None, mileage=None, zip_code="84070", radius=100, dealer_type="franchise")
    assert "rejected the API key" in str(ei.value)

    attempts = {"n": 0}

    def flaky(req):
        attempts["n"] += 1
        return httpx.Response(503) if attempts["n"] == 1 else httpx.Response(200, json=SEARCH_RESPONSE)

    res = await _fake(flaky).fetch(vin=None, year=2019, make="Ford", model="F-150", trim=None, mileage=None, zip_code="84070", radius=100, dealer_type="franchise")
    assert attempts["n"] == 2 and len(res["listings"]) == 2, "5xx is retried once"

    def nothing(req):
        return httpx.Response(200, json={"num_found": 0, "listings": []})

    with pytest.raises(mp.MarketUnavailable):
        await _fake(nothing).fetch(vin=None, year=2019, make="Ford", model="F-150", trim=None, mileage=None, zip_code="84070", radius=100, dealer_type="franchise")


def test_active_provider_falls_back_to_mock_without_key_and_never_silently():
    saved = os.environ.pop("MARKETCHECK_API_KEY", None)
    try:
        assert mp.active().name == "mock" and mp.active().badge == "DEVELOPMENT DATA — NOT LIVE"
        os.environ["MARKETCHECK_API_KEY"] = "k"
        assert mp.active().name == "marketcheck" and mp.active().live is True
        os.environ["MARKET_DATA_PROVIDER"] = "mock"
        assert mp.active().name == "mock", "an explicit override still shows the mock badge"
    finally:
        os.environ.pop("MARKET_DATA_PROVIDER", None)
        if saved is None:
            os.environ.pop("MARKETCHECK_API_KEY", None)
        else:
            os.environ["MARKETCHECK_API_KEY"] = saved
