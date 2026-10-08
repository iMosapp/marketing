"""Validation matrix (services/appraisals/matrix.py): a deliberate list of vehicles through BOTH live providers in the background, one comparison row
per vehicle, a run document the Provider Lab polls, nothing averaged. Providers run on httpx.MockTransport with sentinel keys; no live key is needed.
Run: cd /app/backend && set -a && . ./.env && set +a && python -m pytest tests/test_provider_matrix.py -q"""
import asyncio
import json
import os
import sys

import httpx
import pytest

sys.path.insert(0, "/app/backend")
sys.path.insert(0, "/app/backend/tests")
from test_market_providers_phase2 import SENTINEL_MC, SENTINEL_VA, VIN, mc_ok, va_ok, _patch_providers, _cleanup  # noqa: E402
from services.appraisals import market, matrix, market_providers as mp  # noqa: E402
from services.appraisals import providers as identity  # noqa: E402

VIN2 = "1FTEW1EP5KFA54321"


@pytest.fixture
def db():
    from motor.motor_asyncio import AsyncIOMotorClient
    return AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


@pytest.fixture
def admin_me():
    return {"_id": __import__("bson").ObjectId(), "role": "super_admin", "name": "Lab Admin", "organization_id": "org-lab", "store_id": "store-lab"}


async def _wait(db, run_id: str, me: dict, timeout: float = 20.0) -> dict:
    for _ in range(int(timeout / 0.25)):
        r = await matrix.get(db, me, run_id)
        if r and r["status"] != "running":
            return r
        await asyncio.sleep(0.25)
    raise AssertionError("matrix run did not finish in time")


def test_clean_vehicles_validates_and_caps():
    vs = matrix.clean_vehicles([{"vin": VIN.lower(), "mileage": "61,200", "zip": "84070"}, {"year": "2022", "make": "Ford", "model": "F-150", "mileage": 28000}, {"year": 2022}, "junk"])
    assert vs[0]["vin"] == VIN and vs[0]["mileage"] == 61200 and vs[0]["zip"] == "84070"
    assert vs[1]["vin"] is None and vs[1]["year"] == 2022 and vs[1]["make"] == "Ford" and vs[1]["zip"] is None
    assert len(vs) == 2, "rows without a VIN or year/make/model are dropped"
    with pytest.raises(ValueError):
        matrix.clean_vehicles([{"vin": "SHORT"}])
    with pytest.raises(ValueError):
        matrix.clean_vehicles([{"vin": VIN, "mileage": "lots"}])
    with pytest.raises(ValueError):
        matrix.clean_vehicles([{"vin": VIN, "zip": "ABCDE"}])
    with pytest.raises(ValueError):
        matrix.clean_vehicles([])
    assert len(matrix.clean_vehicles([{"vin": VIN}] * 40)) == matrix.MAX_ROWS


def test_plan_counts_only_configured_providers(monkeypatch):
    monkeypatch.setenv("MARKETCHECK_API_KEY", "")
    monkeypatch.setenv("VINAUDIT_API_KEY", "")
    monkeypatch.setitem(mp.PROVIDERS, "marketcheck", mp.MarketCheckProvider())
    monkeypatch.setitem(mp.PROVIDERS, "vinaudit", mp.VinAuditProvider())
    p = matrix.plan([{"vin": VIN}, {"vin": VIN2}])
    assert p["calls_per_vehicle"] == 0 and p["total_calls"] == 0 and "not configured" in p["marketcheck"]
    monkeypatch.setenv("MARKETCHECK_API_KEY", SENTINEL_MC)
    monkeypatch.setenv("VINAUDIT_API_KEY", SENTINEL_VA)
    p = matrix.plan([{"vin": VIN}, {"vin": VIN2}])
    assert p["calls_per_vehicle"] == mp.PROVIDERS["marketcheck"].calls_per_fetch + len(mp.VA_VALUE_TYPES) and p["total_calls"] == 2 * p["calls_per_vehicle"]


@pytest.mark.asyncio
async def test_start_refuses_without_keys_or_zip(db, admin_me, monkeypatch):
    monkeypatch.setenv("MARKETCHECK_API_KEY", "")
    monkeypatch.setenv("VINAUDIT_API_KEY", "")
    monkeypatch.setitem(mp.PROVIDERS, "marketcheck", mp.MarketCheckProvider())
    monkeypatch.setitem(mp.PROVIDERS, "vinaudit", mp.VinAuditProvider())
    with pytest.raises(ValueError, match="No live provider key"):
        await matrix.start(db, admin_me, vehicles=[{"vin": VIN}], zip_code="84070", radius=100, force=False)
    _patch_providers(monkeypatch, mc_ok, va_ok)
    with pytest.raises(ValueError, match="ZIP"):
        await matrix.start(db, admin_me, vehicles=[{"vin": VIN}], zip_code="840", radius=100, force=False)
    assert await db[matrix.RUNS].count_documents({"user_id": str(admin_me["_id"])}) == 0, "nothing is written when validation fails"


@pytest.mark.asyncio
async def test_run_lands_rows_summary_and_recent(db, admin_me, monkeypatch):
    _patch_providers(monkeypatch, mc_ok, va_ok)
    monkeypatch.setattr(matrix, "PAUSE_S", 0.01)

    async def fake_decode(_db, vin):
        if vin == VIN2:
            raise identity.ProviderUnavailable("decoder down")
        return {"year": 2019, "make": "Ford", "model": "F-150", "trim": "XLT"}
    monkeypatch.setattr(identity, "decode_vin", fake_decode)
    try:
        run = await matrix.start(db, admin_me, vehicles=[{"vin": VIN, "mileage": 61200}, {"year": 2019, "make": "Ford", "model": "F-150", "mileage": 61200, "zip": "84111"}, {"vin": VIN2, "mileage": 1000}],
                                 zip_code="84070", radius=100, force=True)
        assert run["status"] == "running" and run["total"] == 3 and run["done"] == 0 and run["plan"]["total_calls"] == 3 * 4
        with pytest.raises(ValueError, match="already running"):
            await matrix.start(db, admin_me, vehicles=[{"vin": VIN}], zip_code="84070", radius=100, force=False)
        done = await _wait(db, run["id"], admin_me)
        assert done["status"] == "done" and done["done"] == 3 and len(done["rows"]) == 2 and len(done["errors"]) == 1
        assert done["errors"][0]["vin"] == VIN2 and "VIN decode failed" in done["errors"][0]["error"]
        r0, r1 = done["rows"]
        assert r0["vin"] == VIN and r0["year"] == 2019 and r0["zip"] == "84070" and r1["vin"] is None and r1["zip"] == "84111", "a row's own ZIP wins over the default"
        assert r0["mc"]["retail"] == 34850 and r0["va"]["retail"] == 32400 and r0["va"]["trade_in"] == 27950 and r0["mc"]["comps"] == 3
        assert r0["diff_dollars"] == 34850 - 32400 and r0["diff_percent"] is not None and r0["calls_total"] == 4 and r0["comparison_id"]
        assert r1["mc"]["retail"] and r1["va"]["retail"] is None and r1["va"]["error"] and r1["diff_dollars"] is None, "VinAudit is VIN-only: a year/make/model row only gets a MarketCheck answer"
        s = done["summary"]
        assert s == {**s, "vehicles": 2, "skipped": 1, "calls_total": 5, "marketcheck_answered": 2, "vinaudit_answered": 1, "both_answered": 1, "marketcheck_higher": 1, "vinaudit_higher": 0, "median_abs_gap": 2450}
        assert s["mc_median_ms"] is not None and [e["provider"] for e in s["provider_errors"]] == ["va"]
        blob = json.dumps(done, default=str)
        assert SENTINEL_MC not in blob and SENTINEL_VA not in blob, "keys never leak into the run"
        comps = await db[market.COMPARISONS].find({"user_id": str(admin_me["_id"]), "purpose": "matrix"}).to_list(10)
        assert len(comps) == 2, "one comparison row per vehicle, tagged matrix"
        recent = await matrix.recent(db, admin_me, 5)
        assert recent and recent[0]["id"] == run["id"] and recent[0]["rows"] == [] and recent[0]["total"] == 3 and recent[0]["summary"]["both_answered"] == 1
        other = {"_id": __import__("bson").ObjectId(), "role": "store_manager", "name": "Other", "organization_id": "org-x", "store_id": "store-x"}
        assert await matrix.get(db, other, run["id"]) is None, "another tenant cannot read the run"
        assert await matrix.get(db, admin_me, "not-an-id") is None
    finally:
        await db[matrix.RUNS].delete_many({"user_id": str(admin_me["_id"])})
        await _cleanup(db, admin_me)


@pytest.mark.asyncio
async def test_run_keeps_going_when_a_provider_fails(db, admin_me, monkeypatch):
    def mc_down(req):
        return httpx.Response(500, json={"error": "boom"})
    _patch_providers(monkeypatch, mc_down, va_ok)
    monkeypatch.setattr(matrix, "PAUSE_S", 0.01)
    try:
        run = await matrix.start(db, admin_me, vehicles=[{"vin": VIN, "year": 2019, "make": "Ford", "model": "F-150", "mileage": 61200}], zip_code="84070", radius=100, force=True)
        done = await _wait(db, run["id"], admin_me)
        assert done["status"] == "done" and len(done["rows"]) == 1
        r = done["rows"][0]
        assert r["mc"]["retail"] is None and r["mc"]["error"] and r["va"]["retail"] == 32400 and r["diff_dollars"] is None
        s = done["summary"]
        assert s["marketcheck_answered"] == 0 and s["vinaudit_answered"] == 1 and s["both_answered"] == 0 and s["median_abs_gap"] is None
        assert s["provider_errors"] and s["provider_errors"][0]["provider"] == "mc"
    finally:
        await db[matrix.RUNS].delete_many({"user_id": str(admin_me["_id"])})
        await _cleanup(db, admin_me)
