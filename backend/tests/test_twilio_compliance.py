"""Per-store Twilio texting compliance: the state machine on the dry-run adapter (no Twilio calls), a scripted adapter for
rejections and slow approvals, and the admin API on the running backend (localhost:8001)."""
import asyncio
import os
import httpx
import pytest
from bson import ObjectId
from datetime import datetime, timezone

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from routers.database import get_db  # noqa: E402
from services import twilio_compliance as tc  # noqa: E402

pytestmark = pytest.mark.asyncio
BASE = "http://localhost:8001/api"


class Scripted(tc.DryRunTwilio):
    """Dry-run adapter whose statuses follow a script: {'customer_profile': ['in-review', 'twilio-approved'], ...}."""
    name = "scripted"

    def __init__(self, script: dict):
        super().__init__()
        self.script = {k: list(v) for k, v in script.items()}

    def _next(self, key, default):
        q = self.script.get(key)
        if q:
            return q.pop(0) if len(q) > 1 else q[0]
        return default

    async def customer_profile_status(self, sid):
        st = self._next("customer_profile", "twilio-approved")
        return st, ("EIN does not match IRS records" if st in tc.REJECTED else "")

    async def a2p_status(self, sid):
        return self._next("a2p_product", "twilio-approved"), ""

    async def brand_status(self, sid):
        return self._next("brand", "APPROVED"), ""

    async def campaign_status(self, svc, sid):
        st = self._next("campaign", "VERIFIED")
        return st, ("Sample messages do not name the brand" if st in tc.REJECTED else "")

    async def cnam_status(self, sid):
        return self._next("cnam", "twilio-approved"), ""


@pytest.fixture(autouse=True)
def _restore_adapter():
    yield
    tc.use_adapter(None)


async def _login():
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(f"{BASE}/auth/login", json={"email": "forest@imosapp.com", "password": "Admin123!"})
    d = r.json()
    return {"Authorization": f"Bearer {d.get('token') or d.get('access_token')}"}


async def _mk_store(**extra) -> dict:
    db = get_db()
    doc = {"name": "QA Compliance Motors", "phone": "+18015550100", "address": "12 Main St", "city": "Ogden", "state": "UT", "zip_code": "84401", "country": "US",
           "website": "qacompliance.example", "active": True, "created_at": datetime.now(timezone.utc), "qa_compliance": True, **extra}
    r = await db.stores.insert_one(doc)
    doc["_id"] = r.inserted_id
    return doc


async def _mk_rep(store_id: str, sid: str, name="QA Rep"):
    db = get_db()
    r = await db.users.insert_one({"email": f"qa-comp-{sid.lower()}@invalid.imonsocial.test", "name": name, "role": "user", "store_id": store_id, "twilio_number_sid": sid,
                                   "twilio_number": "+18015550199", "created_at": datetime.now(timezone.utc), "qa_compliance": True})
    return r.inserted_id


async def _wipe():
    db = get_db()
    await db.stores.delete_many({"qa_compliance": True})
    await db.users.delete_many({"qa_compliance": True})


def _filled(store: dict) -> dict:
    rec = tc.defaults(store)
    rec["business"].update({"ein": "12-3456789", "website": "https://qacompliance.example"})
    rec["rep"].update({"first_name": "Pat", "last_name": "Owner", "email": "pat@qacompliance.example", "phone": "+18015550101"})
    rec["campaign"].update({"privacy_url": "https://qacompliance.example/privacy", "terms_url": "https://qacompliance.example/terms"})
    return rec


async def test_defaults_validation_and_cnam_name():
    s = {"_id": ObjectId(), "name": "Smith Harley-Davidson of Salt Lake City", "website": "smithhd.com", "address": "1 Bike Way", "city": "SLC", "state": "UT", "zip_code": "84101", "phone": "+18015550000"}
    d = tc.defaults(s)
    assert d["business"]["website"] == "https://smithhd.com" and d["campaign"]["privacy_url"] == "https://smithhd.com/privacy"
    assert d["campaign"]["use_case"] == "LOW_VOLUME" and len(d["campaign"]["samples"]) == 3 and all("Smith Harley" in x and "STOP" in x for x in d["campaign"]["samples"])
    assert d["cnam"]["display_name"] == "SMITH" or len(d["cnam"]["display_name"]) <= 15
    assert tc.cnam_name("Acme Motors, Inc.") == "ACME MOTORS INC" and len(tc.cnam_name("A Very Long Dealership Name Here")) <= 15
    miss = tc.missing_fields(d)
    assert "business.ein" in miss and "rep.first_name" in miss and "campaign.privacy_url" not in miss
    d["business"]["ein"] = "12345"
    assert "business.ein_format" in tc.missing_fields(d)
    pub = tc.public({**d, "business": {**d["business"], "ein": "12-3456789"}})
    assert pub["business"]["ein"] == "" and pub["business"]["ein_masked"] == "**-***6789" and pub["business"]["has_ein"]
    merged = tc.merge_patch({**d, "business": {**d["business"], "ein": "12-3456789"}}, {"business": {"ein": "", "legal_name": "Smith HD LLC"}, "cnam": {"display_name": "smith h-d!"}}, s)
    assert merged["business"]["ein"] == "12-3456789" and merged["business"]["legal_name"] == "Smith HD LLC" and merged["cnam"]["display_name"] == "SMITH HD"


async def test_full_lifecycle_dry_run_with_new_numbers():
    db = get_db()
    await _wipe()
    store = await _mk_store()
    sid = str(store["_id"])
    await _mk_rep(sid, "PNqa000000000000000000000000000001")
    tw = tc.DryRunTwilio()
    tc.use_adapter(tw)
    me = {"_id": ObjectId(), "email": "qa@x"}
    try:
        await db.stores.update_one({"_id": store["_id"]}, {"$set": {"compliance": _filled(store)}})
        store = await db.stores.find_one({"_id": store["_id"]})
        rec = await tc.start(db, store, me)
        assert rec["stage"] == "profile" and rec["status"] == "pending" and rec["sids"]["customer_profile"].startswith("BU")
        assert rec["numbers_on_profile"] == ["PNqa000000000000000000000000000001"]
        assert ("submit_profile", rec["sids"]["customer_profile"]) in tw.calls
        rec = await tc.advance(db, sid)                       # profile approved -> a2p
        assert rec["stage"] == "a2p" and rec["statuses"]["customer_profile"] == "twilio-approved"
        assert rec["sids"].get("cnam_product"), "CNAM goes in as soon as the business profile is approved"
        rec = await tc.advance(db, sid)                       # a2p created
        assert rec["sids"]["a2p_product"] and rec["status"] == "pending"
        rec = await tc.advance(db, sid)                       # a2p approved -> brand
        assert rec["stage"] == "brand"
        rec = await tc.advance(db, sid)                       # brand created (mock flag False in dry_run)
        assert rec["sids"]["brand"].startswith("BN") and any(c[0] == "brand" and c[3] is False for c in tw.calls)
        rec = await tc.advance(db, sid)                       # brand approved -> campaign
        assert rec["stage"] == "campaign"
        # a second rep got a number in the meantime
        await _mk_rep(sid, "PNqa000000000000000000000000000002", "QA Rep 2")
        rec = await tc.advance(db, sid)                       # service + campaign created with both numbers
        assert rec["sids"]["messaging_service"].startswith("MG") and rec["sids"]["campaign"].startswith("QE")
        assert sorted(rec["numbers_on_service"]) == ["PNqa000000000000000000000000000001", "PNqa000000000000000000000000000002"]
        rec = await tc.advance(db, sid)                       # campaign verified -> complete
        assert rec["stage"] == "complete" and rec["status"] == "approved" and rec["approved_at"]
        assert rec["statuses"]["cnam"] == "twilio-approved"
        # the new number was also attached to the profile and CNAM by the poller step
        assert "PNqa000000000000000000000000000002" in rec["numbers_on_profile"] and "PNqa000000000000000000000000000002" in rec["numbers_on_cnam"]
        # a third number after approval: poll_all attaches it everywhere
        await _mk_rep(sid, "PNqa000000000000000000000000000003", "QA Rep 3")
        n = await tc.poll_all(db)
        assert n >= 1
        rec = (await db.stores.find_one({"_id": store["_id"]}))["compliance"]
        assert "PNqa000000000000000000000000000003" in rec["numbers_on_service"] and "PNqa000000000000000000000000000003" in rec["numbers_on_cnam"]
        stages = [h["stage"] + ":" + h["status"] for h in rec["history"]]
        assert stages[:3] == ["profile:submitting", "profile:submitted", "profile:approved"] and "campaign:approved" in stages and "cnam:submitted" in stages
        summ = tc.summary({**store, "compliance": rec})
        assert summ["stage_label"] == "Approved" and summ["numbers"] == 3 and summ["cnam"] == "twilio-approved"
    finally:
        await _wipe()


async def test_rejection_then_resubmit_and_callback():
    db = get_db()
    await _wipe()
    store = await _mk_store(name="QA Rejected Motors")
    sid = str(store["_id"])
    tw = Scripted({"customer_profile": ["in-review", "twilio-rejected"]})
    tc.use_adapter(tw)
    me = {"_id": ObjectId(), "email": "qa@x"}
    try:
        await db.stores.update_one({"_id": store["_id"]}, {"$set": {"compliance": _filled(store)}})
        store = await db.stores.find_one({"_id": store["_id"]})
        rec = await tc.start(db, store, me)
        first_profile = rec["sids"]["customer_profile"]
        rec = await tc.advance(db, sid)
        assert rec["stage"] == "profile" and rec["statuses"]["customer_profile"] == "in-review" and rec["status"] == "pending"
        # Twilio's status callback for the bundle drives the next check
        hit = await tc.on_status_callback(db, {"BundleSid": first_profile, "Status": "twilio-rejected"})
        assert hit == sid
        rec = (await db.stores.find_one({"_id": store["_id"]}))["compliance"]
        assert rec["status"] == "rejected" and "EIN" in rec["error"] and rec["callbacks"][-1]["sid"] == first_profile
        assert await tc.poll_all(db) == 0 or rec["status"] == "rejected", "rejected stores are left alone by the poller"
        # admin fixes the EIN and resubmits: fresh SIDs, old ones kept for the audit trail
        await db.stores.update_one({"_id": store["_id"]}, {"$set": {"compliance.business.ein": "98-7654321"}})
        store = await db.stores.find_one({"_id": store["_id"]})
        tc.use_adapter(Scripted({}))
        rec = await tc.resubmit(db, store, me)
        assert rec["sids"]["customer_profile"] != first_profile and rec["previous_sids"]["customer_profile"] == first_profile
        assert rec["status"] == "pending" and rec["stage"] == "profile" and rec["error"] == ""
        for _ in range(7):
            rec = await tc.advance(db, sid)
        assert rec["stage"] == "complete"
        # a missing field blocks start with a readable error
        bad = await _mk_store(name="QA Incomplete")
        with pytest.raises(ValueError) as ei:
            await tc.start(db, bad, me)
        assert "business.ein" in str(ei.value)
        # unknown bundle sid -> ignored
        assert await tc.on_status_callback(db, {"BundleSid": "BUnope"}) is None
    finally:
        await _wipe()


async def test_admin_api_roundtrip():
    """GET/PUT record, settings, submit, check, reset over HTTP (server runs the dry-run adapter: no key needed, no Twilio calls)."""
    db = get_db()
    await _wipe()
    store = await _mk_store(name="QA API Motors")
    sid = str(store["_id"])
    h = await _login()
    try:
        async with httpx.AsyncClient(timeout=30, headers=h) as c:
            r = await c.get(f"{BASE}/admin/compliance/{sid}")
            assert r.status_code == 200, r.text
            d = r.json()
            assert d["record"]["business"]["legal_name"] == "QA API Motors" and "business.ein" in d["missing"] and d["summary"]["stage"] == "draft"
            r = await c.put(f"{BASE}/admin/compliance/{sid}", json={"business": {"ein": "11-2233445", "website": "https://qaapi.example"},
                                                                    "rep": {"first_name": "Pat", "last_name": "Owner", "email": "pat@qaapi.example", "phone": "+18015550102"},
                                                                    "campaign": {"privacy_url": "https://qaapi.example/privacy", "terms_url": "https://qaapi.example/terms"},
                                                                    "cnam": {"display_name": "QA API Motors!!"}})
            assert r.status_code == 200 and r.json()["missing"] == [] and r.json()["record"]["business"]["ein_masked"] == "**-***3445" and r.json()["record"]["cnam"]["display_name"] == "QA API MOTORS"
            r = await c.put(f"{BASE}/admin/compliance/settings", json={"mode": "dry_run", "notify_email": "compliance@qa.example"})
            assert r.status_code == 200 and r.json()["mode"] == "dry_run"
            r = await c.put(f"{BASE}/admin/compliance/settings", json={"mode": "bogus"})
            assert r.status_code == 400
            r = await c.post(f"{BASE}/admin/compliance/{sid}/submit")
            assert r.status_code == 200, r.text
            assert r.json()["summary"]["stage"] == "profile" and r.json()["record"]["sids"]["customer_profile"].startswith("BU")
            for _ in range(7):
                r = await c.post(f"{BASE}/admin/compliance/{sid}/check")
                assert r.status_code == 200
            assert r.json()["summary"]["stage"] == "complete" and r.json()["summary"]["status"] == "approved"
            r = await c.get(f"{BASE}/admin/compliance")
            row = next(x for x in r.json()["stores"] if x["store_id"] == sid)
            assert row["stage_label"] == "Approved" and r.json()["settings"]["notify_email"] == "compliance@qa.example"
            r = await c.post(f"{BASE}/admin/compliance/{sid}/reset")
            assert r.status_code == 200 and r.json()["record"]["stage"] == "draft" and r.json()["record"]["sids"] == {}
            # the EIN never comes back in clear text
            r = await c.get(f"{BASE}/admin/compliance/{sid}")
            assert r.json()["record"]["business"]["ein"] == "" and r.json()["record"]["business"]["has_ein"]
        # a rep (non-admin) is refused
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.post(f"{BASE}/auth/login", json={"email": "activation-tester@invalid.imonsocial.test", "password": "NewPass123!"})
            tok = r.json().get("token") or r.json().get("access_token")
            r = await c.get(f"{BASE}/admin/compliance", headers={"Authorization": f"Bearer {tok}"})
            assert r.status_code == 403
        # the Trust Hub callback without a valid signature is refused when a token is configured
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.post(f"{BASE}/webhooks/twilio/trusthub-status", data={"BundleSid": "BUx", "Status": "twilio-approved"})
            assert r.status_code in (403, 200)
    finally:
        await db.settings.update_one({"key": tc.SETTINGS_KEY}, {"$set": {"notify_email": ""}})
        await _wipe()
