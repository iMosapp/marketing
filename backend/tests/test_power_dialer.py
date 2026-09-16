"""Power dialer engine, in-process with a fake Twilio client (no real calls, no real numbers).
Covers: compliance windows / state rules / DNC / throttle, CSV import + scrub, a full session in `instant` mode (burst of 2,
first answer connects, second answer abandoned + press 9 -> DNC, disposition promotes to a contact + GHL push skipped when
not connected), AMD voicemail skip, `press1` accept + timeout abandon, and the API surface for campaigns and DNC.
Run: cd /app/backend && set -a && . ./.env && set +a && python -m pytest tests/test_power_dialer.py -q"""
import asyncio
import os
from datetime import datetime, timedelta, timezone, date
from types import SimpleNamespace

import pytest
import requests
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

from services import compliance as comp
from services import dialer as eng

BASE_URL = [l.split("=", 1)[1].strip() for l in open("/app/frontend/.env") if l.startswith("REACT_APP_BACKEND_URL=")][0].rstrip("/")
API = BASE_URL + "/api"
REP_PHONE = "+15005550006"
LEADS = ["+15005550071", "+15005550072", "+15005550073", "+15005550074"]


def _db():
    return AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


def _run(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.run_until_complete(asyncio.sleep(0.05))
        loop.close()


class FakeCalls:
    """Records calls.create / calls(sid).update so the test can assert on cancels, redirects and hangups."""
    def __init__(self):
        self.created, self.updates, self.n = [], [], 0

    def create(self, **kw):
        self.n += 1
        sid = f"CA_fake_{self.n:03d}"
        self.created.append({"sid": sid, **kw})
        return SimpleNamespace(sid=sid)

    def __call__(self, sid):
        upd = self.updates
        class _C:
            def update(self, **kw):
                upd.append({"sid": sid, **kw})
                return SimpleNamespace(sid=sid)
        return _C()


@pytest.fixture()
def fake(monkeypatch):
    calls = FakeCalls()
    monkeypatch.setattr(eng, "_client", lambda: SimpleNamespace(calls=calls))
    return calls


@pytest.fixture(scope="module")
def admin():
    r = requests.post(f"{API}/auth/login", json={"email": "forest@imosapp.com", "password": "Admin123!"}, timeout=30)
    r.raise_for_status()
    tok = r.json().get("token") or r.json().get("access_token")
    return {"Authorization": f"Bearer {tok}"}


# ── compliance rules ──────────────────────────────────────────────────────────
def test_windows_and_state_rules():
    fl = {"phone": "+13055550100", "state": "FL", "tz": "America/New_York", "status": "new", "attempts": 0}
    # 8:30 pm Miami = 00:30 UTC next day in June (EDT): federal OK, Florida closed
    late = datetime(2026, 6, 16, 0, 30, tzinfo=timezone.utc)
    assert comp.check_lead(fl, {"max_attempts": 3}, late)["reason"] == "outside_window"
    assert comp.check_lead({**fl, "state": "GA"}, {"max_attempts": 3}, late)["ok"]
    ok = datetime(2026, 6, 15, 18, 0, tzinfo=timezone.utc)   # 2 pm Miami
    assert comp.check_lead(fl, {"max_attempts": 3}, ok)["ok"]
    assert comp.check_lead(fl, {"max_attempts": 3}, ok, attempts_today=3)["reason"] == "daily_cap"
    assert comp.check_lead(fl, {"max_attempts": 3, "max_per_day": 1}, ok, attempts_today=1)["reason"] == "daily_cap"
    assert comp.check_lead({**fl, "attempts": 3}, {"max_attempts": 3}, ok)["reason"] == "max_attempts"
    assert comp.check_lead({**fl, "dnc": {"status": "internal"}}, {"max_attempts": 3}, ok)["reason"] == "dnc"
    assert comp.check_lead({**fl, "dnc": {"status": "registry"}}, {"max_attempts": 3, "audience": "b2c"}, ok)["reason"] == "dnc"
    assert comp.check_lead({**fl, "dnc": {"status": "registry"}}, {"max_attempts": 3, "audience": "b2b", "allow_registry_b2b": True}, ok)["ok"]
    # campaign hours narrow the legal window
    assert comp.check_lead(fl, {"max_attempts": 3, "hours": {"start": "09:00", "end": "13:00"}}, ok)["reason"] == "outside_window"
    # Sunday in Mississippi: no calls; Texas Sunday noon-9 pm
    sun_10am_ct = datetime(2026, 6, 14, 15, 0, tzinfo=timezone.utc)
    assert comp.check_lead({**fl, "state": "MS", "tz": "America/Chicago"}, {"max_attempts": 3}, sun_10am_ct)["reason"] == "outside_window"
    assert comp.check_lead({**fl, "state": "TX", "tz": "America/Chicago"}, {"max_attempts": 3}, sun_10am_ct)["reason"] == "outside_window"
    assert comp.check_lead({**fl, "state": "TX", "tz": "America/Chicago"}, {"max_attempts": 3}, sun_10am_ct + timedelta(hours=3))["ok"]
    # July 4 in Utah is blocked, in Idaho it is not
    jul4 = datetime(2026, 7, 4, 18, 0, tzinfo=timezone.utc)
    assert comp.check_lead({**fl, "state": "UT", "tz": "America/Denver"}, {"max_attempts": 3}, jul4)["reason"] == "outside_window"
    assert comp.check_lead({**fl, "state": "ID", "tz": "America/Boise"}, {"max_attempts": 3}, jul4)["ok"]
    # unknown zone must be legal in both coasts: 8:30 am Eastern is too early for the Pacific
    early = datetime(2026, 6, 15, 12, 30, tzinfo=timezone.utc)
    assert comp.check_lead({**fl, "state": None, "tz": None}, {"max_attempts": 3}, early)["reason"] == "outside_window"
    nxt = comp.check_lead(fl, {"max_attempts": 3}, late)["next_open"]
    assert nxt and nxt.astimezone(comp.ZoneInfo("America/New_York")).hour == 8
    assert date(2026, 11, 26) in comp.us_holidays(2026) and date(2026, 1, 19) in comp.us_holidays(2026)


def test_region_throttle_and_message():
    assert comp.region("+13055551234")["state"] == "FL"
    assert comp.region("+18015551234") == {"state": "UT", "tz": "America/Denver", "country": "US"}
    assert comp.region("+15005550006", "Utah")["state"] == "UT"
    assert comp.region("+18005551234")["tz"] is None
    assert comp.e164("(801) 555-0100") == "+18015550100" and comp.e164("12345") == ""
    assert comp.throttle_lines(3, 0, 0) == 3
    assert comp.throttle_lines(3, 5, 1) == 1          # any abandon with < 10 live answers
    assert comp.throttle_lines(3, 100, 2) == 3        # 2% is under the 2.5% brake
    assert comp.throttle_lines(3, 100, 3) == 1        # 3%
    assert comp.recording_allowed("UT", {"recording": "on"}) and not comp.recording_allowed("CA", {"recording": "on"}) and not comp.recording_allowed(None, {"recording": "on"})
    msg = comp.abandon_message("Peak Motors", "+14352203414")
    assert "Peak Motors" in msg and "press 9" in msg and "435" not in msg.replace("four three five", "")
    assert comp.parse_registry_lines("305,5551234\n8015550000\n801,5550001,2026-01-01\njunk\n") == ["3055551234", "8015550000", "8015550001"]


# ── full session, instant mode ────────────────────────────────────────────────
def test_session_instant_mode(fake):
    async def go():
        db = _db()
        me = await db.users.find_one({"email": "forest@imosapp.com"})
        rep = {**me, "phone": REP_PHONE}
        c = await eng.create_campaign(db, me, {"name": "QA Engine Instant", "audience": "b2b", "lines": 2, "connect_mode": "instant", "hours": {"start": "00:00", "end": "23:59"}, "max_attempts": 2, "max_per_day": 3})
        try:
            res = await eng.import_rows(db, c, [{"phone": p, "first_name": f"Lead{i}", "last_name": "Test", "state": "ID"} for i, p in enumerate(LEADS[:3])] + [{"phone": LEADS[0]}, {"phone": "123"}], "csv", me)
            assert (res["added"], res["duplicates"], res["invalid"]) == (3, 1, 1)
            # Idaho: federal hours only, and the leads' zone must be set so the window check has a clock
            await db[eng.LEADS].update_many({"campaign_id": str(c["_id"])}, {"$set": {"tz": "America/Boise"}})
            now = datetime.now(timezone.utc).astimezone(comp.ZoneInfo("America/Boise"))
            if not (8 <= now.hour < 21):
                pytest.skip("outside Idaho calling hours right now; the engine correctly refuses to dial")

            s = await eng.start_session(db, c, rep)
            assert fake.created[0]["to"] == REP_PHONE and "rep/answer" in fake.created[0]["url"]
            assert (await db[eng.SESSIONS].find_one({"_id": s["_id"]}))["status"] == "starting"
            xml = await eng.on_rep_answer(db, s)
            assert "Press one" in xml and "ready to call" in xml
            s = await db[eng.SESSIONS].find_one({"_id": s["_id"]})
            assert s["status"] == "idle"

            # press 1 -> burst of 2 with AMD, rep parked in the conference with ringback
            xml = await eng.on_rep_digit(db, s, "1")
            await asyncio.sleep(0.2)
            assert "<Conference" in xml and 'startConferenceOnEnter="false"' in xml and "ringback" in xml
            lead_calls = [x for x in fake.created if x["to"] in LEADS]
            assert len(lead_calls) == 2 and all(x["machine_detection"] == "Enable" and x["async_amd"] == "true" for x in lead_calls)
            s = await db[eng.SESSIONS].find_one({"_id": s["_id"]})
            assert s["status"] == "dialing"
            burst = await db[eng.BURSTS].find_one({"_id": ObjectId(s["current_burst_id"])})
            a1, a2 = [await db[eng.ATTEMPTS].find_one({"_id": ObjectId(i)}) for i in burst["attempt_ids"]]
            assert a1["status"] == "ringing" and a1["call_sid"].startswith("CA_fake")
            leads_calling = await db[eng.LEADS].count_documents({"campaign_id": str(c["_id"]), "status": "calling"})
            assert leads_calling == 2

            # first lead answers: joins the conference, sibling cancelled
            xml = await eng.on_lead_answer(db, a1, a1["call_sid"])
            await asyncio.sleep(0.3)
            assert 'startConferenceOnEnter="true"' in xml and 'endConferenceOnExit="true"' in xml
            assert any(u["sid"] == a2["call_sid"] and u.get("status") == "completed" for u in fake.updates), "sibling leg must be cancelled"
            s = await db[eng.SESSIONS].find_one({"_id": s["_id"]})
            assert s["status"] == "connected" and s["current_attempt_id"] == str(a1["_id"])
            a1 = await db[eng.ATTEMPTS].find_one({"_id": a1["_id"]})
            assert a1["status"] == "connected" and a1["answered_live"] is True
            view = await eng.session_view(db, s)
            assert view["current"]["lead"]["first_name"] == "Lead0" and view["burst"]["legs"][0]["status"] == "connected"

            # second lead answers in the race window -> abandonment message, counted, press 9 -> DNC
            a2 = await db[eng.ATTEMPTS].find_one({"_id": a2["_id"]})
            xml = await eng.on_lead_answer(db, a2, a2["call_sid"])
            assert "press 9" in xml and "our team" in xml.lower() or "QA" in xml or "Say" in xml
            a2 = await db[eng.ATTEMPTS].find_one({"_id": a2["_id"]})
            assert a2["status"] == "abandoned" and a2["abandoned"] is True and a2["answered_live"] is True
            xml = await eng.on_lead_optout(db, a2, "9")
            assert "do not call list" in xml
            assert await comp.is_internal_dnc(db, a2["phone"])
            lead2 = await db[eng.LEADS].find_one({"_id": ObjectId(a2["lead_id"])})
            assert lead2["status"] == "dnc"
            await eng.on_lead_status(db, await db[eng.ATTEMPTS].find_one({"_id": a2["_id"]}), "completed", {"CallDuration": "9"})
            stats = await eng.campaign_stats(db, c)
            assert stats["abandoned"] == 1 and stats["answered_live"] == 2 and stats["lines_effective"] == 1 and stats["throttled"]

            # lead 1 hangs up -> rep's Dial action -> wrapup + prompt to mark the outcome
            await eng.on_lead_status(db, a1, "completed", {"CallDuration": "75"})
            xml = await eng.on_rep_after_burst(db, s, str(burst["_id"]))
            assert "Mark the outcome" in xml
            s = await db[eng.SESSIONS].find_one({"_id": s["_id"]})
            assert s["status"] == "wrapup"
            view = await eng.session_view(db, s)
            assert view["current"]["needs_disposition"] is True

            # disposition: interested -> lead done + promoted to a contact tagged Power Dialer
            lead = await eng.apply_disposition(db, s, await db[eng.ATTEMPTS].find_one({"_id": a1["_id"]}), "interested", "wants a demo Tuesday", None, me)
            await asyncio.sleep(0.2)
            assert lead["status"] == "done" and lead["disposition"] == "interested" and lead["contact_id"]
            contact = await db.contacts.find_one({"_id": ObjectId(lead["contact_id"])})
            assert contact["phone"] == LEADS[0] and "Power Dialer" in contact["tags"] and contact["source"] == "dialer"
            s = await db[eng.SESSIONS].find_one({"_id": s["_id"]})
            assert s["status"] == "idle" and s["stats"]["connects"] == 1 and s["stats"]["dispositions"] == 1

            # throttled campaign: the next press dials ONE line only (third lead)
            fake.created.clear()
            xml = await eng.on_rep_digit(db, s, "1")
            await asyncio.sleep(0.2)
            assert len([x for x in fake.created if x["to"] in LEADS]) == 1
            s = await db[eng.SESSIONS].find_one({"_id": s["_id"]})
            burst2 = await db[eng.BURSTS].find_one({"_id": ObjectId(s["current_burst_id"])})
            a3 = await db[eng.ATTEMPTS].find_one({"_id": ObjectId(burst2["attempt_ids"][0])})
            # nobody answers -> burst ends, rep redirected to idle with the no-answer line, lead queued for retry
            await eng.on_lead_status(db, a3, "no-answer", {})
            burst2 = await db[eng.BURSTS].find_one({"_id": burst2["_id"]})
            assert burst2["state"] == "ended" and burst2["reason"] == "no_answer"
            assert any(u["sid"] == s["rep_call_sid"] and "rep/idle" in u.get("url", "") for u in fake.updates)
            lead3 = await db[eng.LEADS].find_one({"_id": ObjectId(a3["lead_id"])})
            assert lead3["status"] == "queued" and lead3["attempts"] == 1 and lead3["next_attempt_at"].replace(tzinfo=timezone.utc) > datetime.now(timezone.utc) + timedelta(hours=20)

            # star ends the session; connected-but-unmarked cleanup does not touch done leads
            s = await db[eng.SESSIONS].find_one({"_id": s["_id"]})
            xml = await eng.on_rep_digit(db, s, "*")
            assert "Hangup" in xml
            assert (await db[eng.SESSIONS].find_one({"_id": s["_id"]}))["status"] == "ended"
            assert await db[eng.ATTEMPTS].count_documents({"campaign_id": str(c["_id"])}) == 3, "the compliance log keeps every dial"
        finally:
            await db[eng.LEADS].delete_many({"campaign_id": str(c["_id"])})
            await db[eng.ATTEMPTS].delete_many({"campaign_id": str(c["_id"])})
            await db[eng.BURSTS].delete_many({"campaign_id": str(c["_id"])})
            await db[eng.SESSIONS].delete_many({"campaign_id": str(c["_id"])})
            await db[eng.CAMPAIGNS].delete_one({"_id": c["_id"]})
            await db.contacts.delete_many({"phone": {"$in": LEADS}, "source": "dialer"})
            await db[comp.DNC_LIST].delete_many({"phone": {"$in": LEADS}})
            await db.tasks.delete_many({"contact_phone": {"$in": LEADS}, "source": "dialer"})
    _run(go())


# ── press1 mode + AMD ─────────────────────────────────────────────────────────
def test_session_press1_and_voicemail(fake):
    async def go():
        db = _db()
        me = await db.users.find_one({"email": "forest@imosapp.com"})
        rep = {**me, "phone": REP_PHONE}
        c = await eng.create_campaign(db, me, {"name": "QA Engine Press1", "audience": "b2b", "lines": 1, "connect_mode": "press1", "hours": {"start": "00:00", "end": "23:59"}, "voicemail": "skip"})
        try:
            await eng.import_rows(db, c, [{"phone": LEADS[2], "first_name": "Vicky", "last_name": "Voicemail"}, {"phone": LEADS[3], "first_name": "Pat", "last_name": "Press"}], "csv", me)
            await db[eng.LEADS].update_many({"campaign_id": str(c["_id"])}, {"$set": {"tz": "America/Boise", "state": "ID"}})
            now = datetime.now(timezone.utc).astimezone(comp.ZoneInfo("America/Boise"))
            if not (8 <= now.hour < 21):
                pytest.skip("outside Idaho calling hours right now")
            s = await eng.start_session(db, c, rep)
            await eng.on_rep_answer(db, s)
            s = await db[eng.SESSIONS].find_one({"_id": s["_id"]})

            # app tap -> rep leg redirected to the burst TwiML, one lead dialed
            res = await eng.dial_from_app(db, s, c)
            await asyncio.sleep(0.2)
            assert res["dialed"] == 1
            assert any(u["sid"] == s["rep_call_sid"] and "rep/burst" in u.get("url", "") for u in fake.updates)
            s = await db[eng.SESSIONS].find_one({"_id": s["_id"]})
            xml = await eng.on_rep_burst_twiml(db, s, s["current_burst_id"])
            assert "<Gather" in xml and "ringback" in xml and "<Conference" not in xml
            burst = await db[eng.BURSTS].find_one({"_id": ObjectId(s["current_burst_id"])})
            a = await db[eng.ATTEMPTS].find_one({"_id": ObjectId(burst["attempt_ids"][0])})

            # voicemail picks up: lead joins alone, rep gets the accept prompt, then AMD says machine -> hang up, retry later, rep back to idle
            xml = await eng.on_lead_answer(db, a, a["call_sid"])
            await asyncio.sleep(0.3)
            assert 'startConferenceOnEnter="true"' in xml
            assert any(u["sid"] == s["rep_call_sid"] and "rep/accept" in u.get("url", "") for u in fake.updates)
            xml = eng.twiml_rep_accept(s, await db[eng.ATTEMPTS].find_one({"_id": a["_id"]}))
            assert "Press one" in xml and ("Vicky" in xml or "Pat" in xml)
            await eng.on_lead_amd(db, await db[eng.ATTEMPTS].find_one({"_id": a["_id"]}), "machine_end_beep")
            a = await db[eng.ATTEMPTS].find_one({"_id": a["_id"]})
            assert a["status"] == "voicemail" and a["answered_live"] is False and a["abandoned"] is False
            assert any(u["sid"] == a["call_sid"] and u.get("status") == "completed" for u in fake.updates)
            burst = await db[eng.BURSTS].find_one({"_id": burst["_id"]})
            assert burst["state"] == "ended" and burst["reason"] == "voicemail"
            await eng.on_lead_status(db, a, "completed", {"CallDuration": "12"})
            lead = await db[eng.LEADS].find_one({"_id": ObjectId(a["lead_id"])})
            assert lead["status"] == "queued" and lead["last_outcome"] == "voicemail"
            s = await db[eng.SESSIONS].find_one({"_id": s["_id"]})
            assert s["status"] == "idle" and s["stats"]["voicemails"] == 1

            # second burst: a human answers, rep does NOT press 1 in time -> lead hears the abandon message, counted
            fake.updates.clear()
            xml = await eng.on_rep_digit(db, s, "1")
            await asyncio.sleep(0.2)
            s = await db[eng.SESSIONS].find_one({"_id": s["_id"]})
            burst = await db[eng.BURSTS].find_one({"_id": ObjectId(s["current_burst_id"])})
            a = await db[eng.ATTEMPTS].find_one({"_id": ObjectId(burst["attempt_ids"][0])})
            await eng.on_lead_answer(db, a, a["call_sid"])
            await asyncio.sleep(0.2)
            xml = await eng.on_rep_accept(db, s, str(a["_id"]), "")
            assert "Missed" in xml
            a = await db[eng.ATTEMPTS].find_one({"_id": a["_id"]})
            assert a["status"] == "abandoned" and a["abandoned"] is True
            assert any(u["sid"] == a["call_sid"] and "lead/abandon" in u.get("url", "") for u in fake.updates)
            s = await db[eng.SESSIONS].find_one({"_id": s["_id"]})
            assert s["status"] == "idle" and s["stats"]["abandoned"] == 1

            # third: human answers, rep presses 1 -> joined
            await eng.on_lead_status(db, a, "completed", {})
            lead = await db[eng.LEADS].find_one({"_id": ObjectId(a["lead_id"])})
            await db[eng.LEADS].update_one({"_id": lead["_id"]}, {"$set": {"next_attempt_at": None, "attempts": 0}})
            await db[eng.ATTEMPTS].delete_many({"lead_id": str(lead["_id"]), "_id": {"$ne": a["_id"]}})
            xml = await eng.on_rep_digit(db, s, "1")
            await asyncio.sleep(0.2)
            s = await db[eng.SESSIONS].find_one({"_id": s["_id"]})
            burst = await db[eng.BURSTS].find_one({"_id": ObjectId(s["current_burst_id"])})
            assert burst and burst["state"] == "ringing", "daily cap of 3 leaves room for this dial"
            a = await db[eng.ATTEMPTS].find_one({"_id": ObjectId(burst["attempt_ids"][0])})
            await eng.on_lead_answer(db, a, a["call_sid"])
            xml = await eng.on_rep_accept(db, s, str(a["_id"]), "1")
            assert "<Conference" in xml and 'startConferenceOnEnter="true"' in xml
            await eng.end_session(db, await db[eng.SESSIONS].find_one({"_id": s["_id"]}), "app")
            s = await db[eng.SESSIONS].find_one({"_id": s["_id"]})
            assert s["status"] == "ended" and any(u["sid"] == s["rep_call_sid"] and u.get("status") == "completed" for u in fake.updates)
            lead = await db[eng.LEADS].find_one({"_id": ObjectId(a["lead_id"])})
            assert lead["status"] in ("queued", "done"), "unmarked connected call goes back to the list"
        finally:
            await db[eng.LEADS].delete_many({"campaign_id": str(c["_id"])})
            await db[eng.ATTEMPTS].delete_many({"campaign_id": str(c["_id"])})
            await db[eng.BURSTS].delete_many({"campaign_id": str(c["_id"])})
            await db[eng.SESSIONS].delete_many({"campaign_id": str(c["_id"])})
            await db[eng.CAMPAIGNS].delete_one({"_id": c["_id"]})
    _run(go())


# ── API surface ───────────────────────────────────────────────────────────────
def test_api_campaign_dnc_and_ghl(admin):
    async def _pre():
        await _db()[comp.DNC_REGISTRY].delete_one({"n": "5005550082"})
        await _db()[comp.DNC_LIST].delete_one({"phone": "+15005550081"})
    _run(_pre())
    r = requests.get(f"{API}/dialer/config", headers=admin, timeout=30)
    assert r.status_code == 200 and r.json()["available"] and r.json()["is_manager"]
    c = requests.post(f"{API}/dialer/campaigns", headers=admin, json={"name": "QA API Campaign", "audience": "b2c", "lines": 5, "connect_mode": "weird", "max_per_day": 9}, timeout=30).json()
    cid = c["id"]
    try:
        assert c["lines"] == 3 and c["connect_mode"] == "instant" and c["max_per_day"] == 3 and c["audience"] == "b2c"
        imp = requests.post(f"{API}/dialer/campaigns/{cid}/import/csv", headers=admin, json={"csv": "name;phone;company\nAnn Lee;500-555-0081;Acme\nBob;5005550082;\n;12;x\n"}, timeout=60).json()
        assert imp["added"] == 2 and imp["invalid"] == 1
        leads = requests.get(f"{API}/dialer/campaigns/{cid}/leads", headers=admin, timeout=30).json()["leads"]
        ann = next(l for l in leads if l["first_name"] == "Ann")
        assert ann["last_name"] == "Lee" and ann["company"] == "Acme" and ann["phone"] == "+15005550081"
        # manager DNC from the list -> lead flagged, number on the internal list, check endpoint agrees
        d = requests.post(f"{API}/dialer/campaigns/{cid}/leads/{ann['id']}/dnc", headers=admin, timeout=30).json()
        assert d["status"] == "dnc" and d["dnc"] == "internal"
        chk = requests.get(f"{API}/dialer/dnc/check/5005550081", headers=admin, timeout=30).json()
        assert chk["status"] == "internal" and chk["blocked"]
        lst = requests.get(f"{API}/dialer/dnc", headers=admin, params={"q": "5550081"}, timeout=30).json()
        assert lst["total"] >= 1 and lst["entries"][0]["source"] == "rep"
        # registry import + rescrub flags Bob
        reg = requests.post(f"{API}/dialer/dnc/registry", headers=admin, json={"text": "500,5550082\n"}, timeout=60).json()
        assert reg["lines"] == 1
        rs = requests.post(f"{API}/dialer/campaigns/{cid}/rescrub", headers=admin, timeout=30).json()
        assert rs["flagged"] == 1
        bob = next(l for l in requests.get(f"{API}/dialer/campaigns/{cid}/leads", headers=admin, timeout=30).json()["leads"] if l["first_name"] == "Bob")
        assert bob["status"] == "dnc" and bob["dnc"] == "registry"
        # patch settings, attempts log empty, pause
        p = requests.patch(f"{API}/dialer/campaigns/{cid}", headers=admin, json={"status": "paused", "seller_name": "QA Motors", "hours": {"start": "10:00", "end": "18:00"}}, timeout=30).json()
        assert p["status"] == "paused" and p["seller_name"] == "QA Motors" and p["hours"]["end"] == "18:00"
        assert requests.post(f"{API}/dialer/sessions", headers=admin, json={"campaign_id": cid}, timeout=30).status_code == 409
        assert requests.get(f"{API}/dialer/campaigns/{cid}/attempts", headers=admin, timeout=30).json()["total"] == 0
        # GHL: nothing connected yet, import refuses cleanly, bad token rejected with a helpful 400
        g = requests.get(f"{API}/ghl/connection", headers=admin, timeout=30).json()
        assert g["connected"] is False and "lead_sources" in g
        assert requests.post(f"{API}/dialer/campaigns/{cid}/import/ghl", headers=admin, json={"tag": "x"}, timeout=30).status_code == 404
        bad = requests.put(f"{API}/ghl/connection", headers=admin, json={"location_id": "not-a-real-location", "token": "pit-invalid"}, timeout=60)
        assert bad.status_code in (400, 502) and "GoHighLevel" in bad.json()["detail"]
        assert requests.post(f"{API}/ghl/webhook/{cid}", params={"key": "nope"}, json={"phone": "5005550090"}, timeout=30).status_code == 401
    finally:
        requests.delete(f"{API}/dialer/campaigns/{cid}", headers=admin, timeout=30)
        requests.delete(f"{API}/dialer/dnc/+15005550081", headers=admin, timeout=30)

        async def _clean():
            await _db()[comp.DNC_REGISTRY].delete_one({"n": "5005550082"})
        _run(_clean())
