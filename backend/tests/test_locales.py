"""Locales (Phase A): a Dutch or British client/store changes the voices, the language of what the AI says and writes,
how numbers are spoken, the currency on invoices, and the default timezone. en-US behaves exactly as before."""
import asyncio
import os

import pytest
import requests
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

from services import lead_call_engine as eng
from services import locales as loc
from services import mystery_shops as ms
from services import scorecards as sc
from services import scripts as scr
from services.speech import speakable, numbers_rule

BASE_URL = [l.split("=", 1)[1].strip() for l in open("/app/frontend/.env") if l.startswith("REACT_APP_BACKEND_URL=")][0].rstrip("/")
API = BASE_URL + "/api"


def _db():
    return AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


@pytest.fixture(scope="module")
def admin():
    r = requests.post(f"{API}/auth/login", json={"email": "forest@imosapp.com", "password": "Admin123!"}, timeout=30)
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json().get('token') or r.json().get('access_token')}"}


def test_locale_table_and_defaults():
    assert loc.key_of(None) == "en-US" and loc.key_of({"locale": "xx-XX"}) == "en-US" and loc.key_of({"locale": "nl-NL"}) == "nl-NL"
    assert loc.language("nl-NL") == "nl" and loc.language("en-GB") == "en" and loc.currency("en-GB") == "gbp" and loc.currency("nl-NL") == "eur" and loc.currency(None) == "usd"
    assert loc.get("nl-NL")["timezone"] == "Europe/Amsterdam" and loc.get("en-GB")["timezone"] == "Europe/London"
    assert loc.relay_voice("en-US", "female") == ("Google", "en-US-Journey-F")          # unchanged US behaviour
    assert loc.relay_voice("nl-NL", "male") == ("ElevenLabs", "UNBIyLbtFB9k7FKW8wJv")
    assert loc.relay_voice("nl-NL", "nonsense")[0] == "ElevenLabs"
    assert loc.say_voice("nl-NL") == "Polly.Laura-Neural" and loc.say_voice(None) == "Polly.Joanna-Neural"
    assert "Nederlands" in loc.language_rule("nl-NL") and "Vlaams" in loc.language_rule("nl-BE") and loc.language_rule("en-US") == "" and loc.language_rule(None) == ""
    codes = [x["code"] for x in loc.for_api()]
    assert codes == ["en-US", "en-GB", "en-IE", "nl-NL", "nl-BE"]


def test_speech_english_unchanged_and_british():
    assert speakable("$132.89") == speakable("$132.89", "en-US") == "one hundred thirty-two dollars and eighty-nine cents"
    assert speakable("(435) 275-9829") == "four three five, two seven five, nine eight two nine"
    assert speakable("£12.50", "en-GB") == "twelve pounds and fifty pence"
    assert speakable("07123 456789", "en-GB") == "oh seven one two three, four five six, seven eight nine"
    assert speakable("020 7946 0958", "en-GB") == "oh two oh, seven nine four six, oh nine five eight"
    assert speakable("€45k", "en-IE") == "forty-five thousand euros"
    assert "point" in numbers_rule("en-GB") and "GETALLEN" in numbers_rule("nl-NL")


def test_speech_dutch():
    assert speakable("€ 1.234,56", "nl-NL") == "duizendtweehonderdvierendertig euro zesenvijftig"
    assert speakable("€132,89", "nl-NL") == speakable("€132.89", "nl-NL") == "honderdtweeëndertig euro negenentachtig"
    assert speakable("12,50 euro", "nl-NL") == "twaalf euro vijftig"
    assert speakable("06-12345678", "nl-NL") == speakable("+31 6 12345678", "nl-NL") == "nul zes, twaalf, vierendertig, zesenvijftig, achtenzeventig"
    assert speakable("6,9%", "nl-NL") == "zes komma negen procent"
    assert speakable("45.000 kilometer", "nl-NL") == "vijfenveertigduizend kilometer"
    assert speakable("een Golf uit 2022", "nl-NL") == "een Golf uit tweeduizendtweeëntwintig"
    assert speakable("om 9:30", "nl-NL") == "om negen uur dertig"
    assert speakable("de 3e", "nl-NL") == "de derde"
    assert speakable("Hallo, geen cijfers", "nl-NL") == "Hallo, geen cijfers"


def test_relay_twiml_and_announcements_follow_locale():
    base = {"_id": ObjectId(), "token": "t", "persona": {"name": "Sanne de Vries", "voice": "female", "opening_line": "Hoi, ik bel over de Golf van €18.950 die online staat."}, "direction": "outbound", "rep_name": "Pieter Bakker", "department": "sales", "industry": "automotive", "store_name": "Autobedrijf Jansen"}
    nl = scr.relay_twiml({**base, "locale": "nl-NL"})
    assert 'ttsProvider="ElevenLabs"' in nl and 'voice="D6MRWCKoavI2xUJXmaCb"' in nl and 'language="nl-NL"' in nl and "achttienduizendnegenhonderdvijftig euro" in nl
    us = scr.relay_twiml({**base, "persona": {**base["persona"], "opening_line": "Hi, I'm calling about the $18,950 Golf"}})
    assert 'ttsProvider="Google"' in us and 'voice="en-US-Journey-F"' in us and 'language="en-US"' in us and "eighteen thousand nine hundred fifty dollars" in us
    gb = scr.relay_twiml({**base, "locale": "en-GB", "persona": {**base["persona"], "voice": "male"}})
    assert 'ttsProvider="ElevenLabs"' in gb and 'voice="Fahco4VZzobUeiPqni1S"' in gb and 'language="en-GB"' in gb
    ann_nl = scr.shop_announcement({**base, "locale": "nl-NL"})
    assert ann_nl.startswith("Hoi Pieter, dit is je oefengesprek") and "verkoopgesprek" in ann_nl and "Sanne" in ann_nl
    ann_us = scr.shop_announcement(base)
    assert ann_us.startswith("Hi Pieter, this is your practice call") and "sales call" in ann_us
    gate_nl = scr.shop_gate_twiml({**base, "locale": "nl-NL"})
    assert 'voice="Polly.Laura-Neural"' in gate_nl and 'language="nl-NL"' in gate_nl and "klaar" in gate_nl
    assert scr.gate_choice("", "ja klaar") == "go" and scr.gate_choice("", "niet nu") == "later" and scr.gate_choice("1", "") == "go"
    go_nl = scr.shop_go_twiml({**base, "locale": "nl-NL"})
    assert "Daar gaan we" in go_nl and 'ttsProvider="ElevenLabs"' in go_nl
    assert 'voice="Polly.Laura-Neural"' in scr.say_hangup_twiml("Tot ziens", "nl-NL") and 'voice="Polly.Joanna-Neural"' in scr.say_hangup_twiml("Bye")


def test_customer_prompt_and_grader_language():
    sys_nl = scr._customer_system({"title": "x", "purpose": "y"}, {"name": "Sanne", "summary": "s", "goals": "g", "objections": []}, "Jansen", "Pieter", [], live=True, locale="nl-NL")
    assert "ONLY natural Dutch" in sys_nl and "GETALLEN" in sys_nl
    sys_us = scr._customer_system({"title": "x", "purpose": "y"}, {"name": "Ann", "summary": "s", "goals": "g", "objections": []}, "Store", "Bud", [], live=True)
    assert "Dutch" not in sys_us and "NUMBERS:" in sys_us
    card = {"name": "Sales", "department": "Sales", "criteria": [{"id": "a", "text": "Got the name", "critical": False}]}
    assert "in natural Dutch" in sc._grader_prompt(card, "Pieter", "Sanne", "inbound", 120, "automotive", "nl")
    assert "Dutch" not in sc._grader_prompt(card, "Bud", "Ann", "inbound", 120, "automotive", "en")
    assert "Dutch" not in sc._grader_prompt(card, "Bud", "Ann", "inbound", 120)


def test_lead_call_twiml_in_dutch():
    job = {"locale": "nl-NL", "lead": {"name": "Kees Visser", "source_label": "Marktplaats", "interest": "Golf 8", "comments": "Bel me na 17:00"}, "customer_phone": "+31612345678", "deferred": False}
    ans = eng.twiml_answer(job, "https://x/claim")
    assert "Nieuwe lead via Marktplaats" in ans and 'voice="Polly.Laura-Neural"' in ans and "Geen reactie" in ans
    w = eng.whisper_text(job)
    assert w.startswith("Hij is voor jou. Nieuwe lead: Kees Visser.") and "Marktplaats" in w and "Ik verbind je nu door." in w
    bridge = eng.twiml_claimed_and_bridge(job, "+3197010000000")
    assert "zeventien uur" in bridge and "Het gesprek is beëindigd" in bridge and "<Dial" in bridge
    assert "deze lead al geclaimd" in eng.twiml_already_claimed("Anna", "nl-NL") and "Someone already" in eng.twiml_already_claimed("")
    assert "sla je over" in eng.twiml_passed("nl-NL") and "passing on this lead" in eng.twiml_passed()
    us = eng.twiml_answer({**job, "locale": "en-US"}, "https://x/claim")
    assert "New lead from Marktplaats" in us and 'voice="Polly.Joanna-Neural"' in us


def test_invoice_extras():
    assert ms.invoice_extras({"locale": "en-US"}) == {}
    nl = ms.invoice_extras({"locale": "nl-NL", "vat_id": "NL123456789B01"})
    assert nl["payment_settings"]["payment_method_types"] == ["card", "ideal", "sepa_debit"] and "Btw verlegd" in nl["footer"] and nl["custom_fields"][0]["value"] == "NL123456789B01"
    gb = ms.invoice_extras({"locale": "en-GB"})
    assert gb["payment_settings"]["payment_method_types"] == ["card", "bacs_debit"] and "footer" not in gb


def test_client_locale_api_and_voice_override(admin):
    lst = requests.get(f"{API}/shop-clients/locales", headers=admin, timeout=30).json()
    assert lst["default"] == "en-US" and any(x["code"] == "nl-NL" and x["symbol"] == "€" for x in lst["locales"])
    r = requests.post(f"{API}/shop-clients", headers=admin, timeout=30, json={"name": "QA Autobedrijf Jansen", "industry": "automotive", "locale": "nl-NL", "vat_id": "nl123456789b01", "contact_email": "gm@invalid.imonsocial.test", "plan": {"per_month": {"sales": 4}, "price_monthly": 450}})
    assert r.status_code == 200, r.text
    c = r.json()
    cid = c["id"]
    try:
        assert c["locale"] == "nl-NL" and c["language"] == "nl" and c["currency"] == "eur" and c["currency_symbol"] == "€" and c["timezone"] == "Europe/Amsterdam" and c["vat_id"] == "NL123456789B01" and c["country"] == "NL"
        bad = requests.put(f"{API}/shop-clients/{cid}", headers=admin, timeout=30, json={"locale": "fr-FR"})
        assert bad.status_code == 400
        gb = requests.put(f"{API}/shop-clients/{cid}", headers=admin, timeout=30, json={"locale": "en-GB"}).json()
        assert gb["locale"] == "en-GB" and gb["timezone"] == "Europe/London" and gb["currency"] == "gbp"
        keep = requests.put(f"{API}/shop-clients/{cid}", headers=admin, timeout=30, json={"locale": "nl-NL", "timezone": "Europe/Brussels"}).json()
        assert keep["timezone"] == "Europe/Brussels"
        # a scheduled shop for this client carries the locale so the call speaks Dutch
        p = requests.post(f"{API}/shop-clients/{cid}/people", headers=admin, timeout=30, json={"name": "Pieter Bakker", "phone": "+31612345678", "department": "sales"}).json()

        async def run():
            db = _db()
            client = await db.shop_clients.find_one({"_id": ObjectId(cid)})
            target = await db.shop_targets.find_one({"_id": ObjectId(p["id"])})
            from datetime import datetime, timedelta, timezone
            s = await ms.create_shop_call(db, client, target, datetime.now(timezone.utc) + timedelta(days=30), manual=True)
            assert s and s["locale"] == "nl-NL"
            assert 'language="nl-NL"' in scr.relay_twiml(s)
            await db.roleplay_sessions.delete_one({"_id": s["_id"]})
            # voice override round trip
            voices = await loc.set_voices(db, "nl-NL", {"female": "ElevenLabs:TESTVOICE123", "say": "Polly.Ruben"})
            assert voices["female"] == "ElevenLabs:TESTVOICE123" and loc.relay_voice("nl-NL", "female") == ("ElevenLabs", "TESTVOICE123") and loc.say_voice("nl-NL") == "Polly.Ruben"
            await loc.set_voices(db, "nl-NL", {})
            assert loc.relay_voice("nl-NL", "female") == ("ElevenLabs", "D6MRWCKoavI2xUJXmaCb") and loc.say_voice("nl-NL") == "Polly.Laura-Neural"
        asyncio.run(run())
        # super admin API for the same override
        v = requests.put(f"{API}/shop-clients/locales/nl-NL/voices", headers=admin, timeout=30, json={"voices": {"older": "ElevenLabs:OLDERVOICE"}})
        assert v.status_code == 200 and v.json()["voices"]["older"] == "ElevenLabs:OLDERVOICE"
        requests.put(f"{API}/shop-clients/locales/nl-NL/voices", headers=admin, timeout=30, json={"voices": {}})
        assert requests.get(f"{API}/shop-clients/locales", headers=admin, timeout=30).json()["locales"][3]["voices"]["older"] == "ElevenLabs:tfweP7lGJyLeNV9dH1Rm"
        assert requests.put(f"{API}/shop-clients/locales/xx-XX/voices", headers=admin, timeout=30, json={"voices": {}}).status_code == 400
    finally:
        requests.delete(f"{API}/shop-clients/{cid}", headers=admin, timeout=30)


def test_store_locale_saves(admin):
    sid = "69a0b7095fddcede09591668"
    r = requests.put(f"{API}/admin/stores/{sid}", headers=admin, timeout=30, json={"locale": "nl-NL"})
    assert r.status_code == 200, r.text

    async def run():
        db = _db()
        assert await loc.store_locale(db, sid) == "nl-NL"
        await db.stores.update_one({"_id": ObjectId(sid)}, {"$unset": {"locale": ""}})
        assert await loc.store_locale(db, sid) == "en-US"
    asyncio.run(run())
