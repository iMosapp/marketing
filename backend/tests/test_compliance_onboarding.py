"""Client A2P onboarding: invite (text + email), public form save/submit, team notifications, reminders cadence, pre-flight,
review + submit gate, numbers exit path. Fake Twilio SMS / Resend / HTTP so nothing leaves the box."""
import os
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from bson import ObjectId
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from routers.database import get_db  # noqa: E402
from services import compliance_onboarding as ob  # noqa: E402
from services import compliance_preflight as pf  # noqa: E402
from services import twilio_compliance as tc  # noqa: E402

pytestmark = pytest.mark.asyncio
SENT: list[dict] = []
PAGES: dict[str, tuple] = {}


async def _fake_sms(to, body):
    SENT.append({"channel": "text", "to": to, "body": body})
    return {"ok": True, "sid": "SMfake"}


async def _fake_email(to, subject, html, text):
    SENT.append({"channel": "email", "to": to, "subject": subject, "text": text})
    return {"ok": True, "id": "em_fake"}


async def _fake_fetch(url):
    return PAGES.get(url, (None, "", url))


@pytest.fixture(autouse=True)
def fakes(monkeypatch):
    SENT.clear()
    monkeypatch.setattr(ob, "_sms", _fake_sms)
    monkeypatch.setattr(ob, "_email", _fake_email)
    monkeypatch.setattr(pf, "fetch", _fake_fetch)
    yield


@pytest_asyncio.fixture
async def store():
    DB = get_db()
    doc = {"name": "QA Onboard Motors LLC", "country": "US", "phone": "+15005550140", "website": "https://qa-onboard.example", "address": "1 Test Way", "city": "Ogden", "state": "UT", "active": True, "organization_id": "org_qa_onboard", "created_at": datetime.now(timezone.utc)}
    r = await DB.stores.insert_one(doc)
    s = await DB.stores.find_one({"_id": r.inserted_id})
    yield s
    await DB.stores.delete_one({"_id": s["_id"]})
    await DB.notifications.delete_many({"type": "compliance", "title": {"$regex": "QA Onboard"}})


ME = {"_id": ObjectId(), "email": "qa-admin@invalid.imonsocial.test", "role": "super_admin"}


async def _fresh(store):
    return await get_db().stores.find_one({"_id": store["_id"]})


async def test_invite_public_form_and_return(store):
    DB = get_db()
    await DB.settings.update_one({"key": tc.SETTINGS_KEY}, {"$set": {"notify_email": "team@invalid.imonsocial.test"}, "$setOnInsert": {"key": tc.SETTINGS_KEY}}, upsert=True)
    out = await ob.send_to_client(DB, store, "invite", "gm@invalid.imonsocial.test", "+15005550141", "both", ME)
    assert out["ok"] and {r["channel"] for r in out["results"]} == {"text", "email"}
    assert [x for x in SENT if x["channel"] == "text"][0]["body"].count("/a2p-onboarding/") == 1
    # team got the "form sent" email + in-app
    assert any(x["channel"] == "email" and x["to"] == "team@invalid.imonsocial.test" and "form sent" in x["subject"] for x in SENT)
    s = await _fresh(store)
    rec = s["compliance"]
    assert ob.onboarding_status(rec) == "sent"
    tok = rec["onboarding"]["token"]
    assert await ob.store_by_token(DB, tok)
    assert "token" not in tc.public(rec)["onboarding"]
    # client opens, saves a partial, then submits with gaps
    rec = await ob.client_opened(DB, s)
    assert ob.onboarding_status(rec) == "opened"
    view = ob.client_view(s, rec)
    assert view["business"]["ein"] == "" and "sender_name" in view
    s = await _fresh(store)
    rec = await ob.client_save(DB, s, {"business": {"ein": "12-3456789", "postal_code": "84401"}, "rep": {"first_name": "Casey", "last_name": "Client", "email": "casey@qa-onboard.example"}, "contact": {"name": "Casey Client", "email": "casey@qa-onboard.example", "phone": "+15005550141"}})
    assert rec["business"]["ein"] == "12-3456789" and ob.onboarding_status(rec) == "in_progress"
    s = await _fresh(store)
    SENT.clear()
    rec = await ob.client_save(DB, s, {"campaign": {"privacy_url": ""}}, submit=True)
    assert ob.onboarding_status(rec) == "returned_incomplete" and "campaign.privacy_url" in rec["onboarding"]["returned_missing"]
    assert any("form returned" in x.get("subject", "") and "privacy" in x["text"] for x in SENT)
    # complete it -> returned
    s = await _fresh(store)
    rec = await ob.client_save(DB, s, {"campaign": {"privacy_url": "https://qa-onboard.example/privacy"}}, submit=True)
    assert ob.onboarding_status(rec) == "returned" and rec["onboarding"]["returned_missing"] == []
    assert tc.summary(await _fresh(store))["next_action"].startswith("Form is back")
    # locked once submitted to Twilio
    await DB.stores.update_one({"_id": store["_id"]}, {"$set": {"compliance.stage": "profile", "compliance.status": "pending"}})
    with pytest.raises(ValueError):
        await ob.client_save(DB, await _fresh(store), {"business": {"city": "X"}})


async def test_reminders_cadence_and_stall(store):
    DB = get_db()
    await ob.send_to_client(DB, store, "invite", "gm@invalid.imonsocial.test", "", "email", ME)
    SENT.clear()
    assert await ob.run_reminders(DB) == 0  # day 0: nothing due
    for day, expect in ((2, 1), (5, 2), (9, 3)):
        await DB.stores.update_one({"_id": store["_id"]}, {"$set": {"compliance.onboarding.first_sent_at": datetime.now(timezone.utc) - timedelta(days=day, minutes=5), "compliance.onboarding.last_sent_at": datetime.now(timezone.utc) - timedelta(days=1)}})
        assert await ob.run_reminders(DB) == 1
        rec = (await _fresh(store))["compliance"]
        assert rec["onboarding"]["reminders_sent"] == expect
    assert sum(1 for x in SENT if x["channel"] == "email" and "Reminder" in x["subject"]) == 3
    # 4th pass: flagged as stalled, team told, no more client mail
    n_before = len([x for x in SENT if x["to"] == "gm@invalid.imonsocial.test"])
    await DB.stores.update_one({"_id": store["_id"]}, {"$set": {"compliance.onboarding.last_sent_at": datetime.now(timezone.utc) - timedelta(days=1)}})
    assert await ob.run_reminders(DB) == 0
    rec = (await _fresh(store))["compliance"]
    assert rec["onboarding"].get("flagged_at") and ob.onboarding_status(rec) == "stalled"
    assert len([x for x in SENT if x["to"] == "gm@invalid.imonsocial.test"]) == n_before
    assert any(e["event"] == "stalled" for e in rec["events"])
    assert await DB.notifications.count_documents({"type": "compliance", "event": "stalled", "title": {"$regex": "QA Onboard"}}) >= 1


async def test_preflight_scores_and_hints(store):
    DB = get_db()
    rec = tc.defaults(store)
    rec["business"].update({"ein": "123456789", "postal_code": "84401", "legal_name": "QA Onboard Motors LLC"})
    rec["rep"].update({"first_name": "Casey", "last_name": "Client", "email": "casey@gmail.com", "phone": "+15005550141"})
    rec["campaign"]["samples"][1] = "Check this out bit.ly/abc from us"
    numbers = []
    PAGES.clear()
    PAGES["https://qa-onboard.example"] = (200, "Welcome to QA Onboard Motors", "https://qa-onboard.example")
    PAGES["https://qa-onboard.example/privacy"] = (200, "We collect your mobile number for SMS updates. No mobile information will be shared with third parties or affiliates for marketing or promotional purposes.", "")
    PAGES["https://qa-onboard.example/terms"] = (200, "Reply STOP to opt out, HELP for help. Message frequency varies. Msg & data rates may apply.", "")
    r = await pf.run(rec, numbers, store)
    by = {c["key"]: c for c in r["checks"]}
    assert by["privacy"]["level"] == "pass" and by["terms"]["level"] == "pass" and by["website"]["level"] == "pass"
    assert by["samples_short"]["level"] == "block" and "Sample 2" in by["samples_short"]["detail"]
    assert by["rep_email"]["level"] == "warn" and "free mailbox" in by["rep_email"]["detail"]
    assert by["numbers"]["level"] == "warn"
    assert r["verdict"] == "reject" and r["blockers"] == 1
    # fix the shortener + rep email + a dead terms page -> block on terms
    rec["campaign"]["samples"][1] = "Hey Jordan, Sam from QA Onboard Motors here, the Wrangler is in. Reply STOP to opt out."
    rec["rep"]["email"] = "casey@qa-onboard.example"
    PAGES["https://qa-onboard.example/terms"] = (404, "", "")
    r = await pf.run(rec, [{"sid": "PN1", "number": "+15005550001", "owner": "Rep"}], store)
    by = {c["key"]: c for c in r["checks"]}
    assert by["terms"]["level"] == "block" and by["numbers"]["level"] == "pass"
    PAGES["https://qa-onboard.example/terms"] = (200, "Reply STOP to opt out, HELP for help. Message frequency varies. Msg & data rates may apply.", "")
    r = await pf.run(rec, [{"sid": "PN1", "number": "+15005550001", "owner": "Rep"}], store)
    assert r["blockers"] == 0 and r["verdict"] in ("likely", "needs_work") and r["score"] >= 85
    # missing privacy statement is a warn with the sentence to paste
    PAGES["https://qa-onboard.example/privacy"] = (200, "We may text you about your vehicle.", "")
    r = await pf.run(rec, [], store)
    by = {c["key"]: c for c in r["checks"]}
    assert by["privacy"]["level"] == "warn" and "No mobile information" in by["privacy"]["fix"]


async def test_twilio_status_change_notifies_team(store):
    DB = get_db()
    class Fake(tc.DryRunTwilio):
        pass
    tc.use_adapter(Fake())
    try:
        rec = tc.defaults(store)
        rec["business"].update({"ein": "123456789", "postal_code": "84401"})
        rec["rep"].update({"first_name": "Casey", "last_name": "Client", "email": "casey@qa-onboard.example", "phone": "+15005550141"})
        await DB.stores.update_one({"_id": store["_id"]}, {"$set": {"compliance": rec}})
        out = await tc.start(DB, await _fresh(store), ME)
        assert out["stage"] == "profile"
        for _ in range(8):
            out = await tc.advance(DB, str(store["_id"]))
        assert out["stage"] == "complete"
        events = [e["event"] for e in (await _fresh(store))["compliance"]["events"]]
        assert events.count("twilio_status") >= 4
        assert any("APPROVED" in e["title"] for e in (await _fresh(store))["compliance"]["events"])
    finally:
        tc.use_adapter(None)


async def test_numbers_exit_path_and_portout_packet(store):
    DB = get_db()
    uid = ObjectId()
    await DB.users.insert_one({"_id": uid, "name": "QA Rep", "email": "qa-rep-onboard@invalid.imonsocial.test", "store_id": str(store["_id"]), "twilio_number": "+15005550777", "twilio_number_sid": "PNqaonboard", "role": "user"})
    try:
        view = await ob.numbers_view(DB, await _fresh(store))
        assert view["numbers"][0]["status"] == "active" and view["portout_url"].count("/port-out/") == 1
        rec = await ob.set_number_status(DB, await _fresh(store), "PNqaonboard", "port_requested", ME, "carrier said Friday")
        assert rec["numbers_plan"]["PNqaonboard"]["status"] == "port_requested"
        await DB.settings.update_one({"key": tc.SETTINGS_KEY}, {"$set": {"portout_pin": "1234", "portout_service_address": "375 Beale St, San Francisco, CA 94105"}}, upsert=True)
        s = await _fresh(store)
        packet = ob.portout_packet(s, s["compliance"], await ob.settings(DB), (await ob.numbers_view(DB, s))["numbers"])
        assert packet["authorized_name"] == "Twilio, Inc." and packet["pin"] == "1234" and packet["numbers"][0]["number"] == "+15005550777" and len(packet["steps"]) == 6
        SENT.clear()
        r = await ob.send_portout(DB, s, ME, "gm@invalid.imonsocial.test", "+15005550141")
        assert r["ok"] and any("/port-out/" in x.get("text", x.get("body", "")) for x in SENT)
        # release (dry run: no Twilio) clears the rep's number
        rec = await ob.release_number(DB, await _fresh(store), "PNqaonboard", ME)
        assert rec["numbers_plan"]["PNqaonboard"]["status"] == "released"
        assert not (await DB.users.find_one({"_id": uid})).get("twilio_number_sid")
        view = await ob.numbers_view(DB, await _fresh(store))
        assert view["numbers"][0]["status"] == "released" and view["numbers"][0].get("gone")
    finally:
        await DB.users.delete_one({"_id": uid})
        await DB.settings.update_one({"key": tc.SETTINGS_KEY}, {"$unset": {"portout_pin": "", "portout_service_address": ""}})
