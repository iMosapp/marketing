"""Phase D UK / Ireland pack: British wording on client pages, emails and texts; British trade words for the AI shopper and grader;
en-IE clients draw from the en-GB challenge library; per-country Twilio regulatory bundles for GB / IE / BE numbers. Never buys a Twilio number."""
import asyncio
import os

import pytest
import requests
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

from services import i18n
from services import industries as ind
from services import locales as loc
from services import mystery_shops as ms
from services import scorecards as sc
from services import shop_numbers as sn
from services.speech import speakable

BASE_URL = [l.split("=", 1)[1].strip() for l in open("/app/frontend/.env") if l.startswith("REACT_APP_BACKEND_URL=")][0].rstrip("/")
API = BASE_URL + "/api"


def _db():
    return AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


@pytest.fixture(scope="module")
def admin():
    r = requests.post(f"{API}/auth/login", json={"email": "forest@imosapp.com", "password": "Admin123!"}, timeout=30)
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json().get('token') or r.json().get('access_token')}"}


def test_uk_texts_pure():
    assert (loc.dialect("en-GB"), loc.dialect("en-IE"), loc.dialect("nl-BE"), loc.dialect("en-US"), loc.dialect(None), loc.dialect("xx")) == ("en-GB", "en-IE", "nl", "en", "en", "en")
    assert "part exchange" in loc.language_rule("en-GB") and "MOT" in loc.language_rule("en-GB") and "pounds" in loc.language_rule("en-GB")
    assert "NCT" in loc.language_rule("en-IE") and "MOT" not in loc.language_rule("en-IE") and "kilometres" in loc.language_rule("en-IE") and "Eircode" in loc.language_rule("en-IE")
    assert loc.language_rule("en-US") == "" and loc.language_rule("nl-NL").startswith("LANGUAGE: Write and speak ONLY natural Dutch")
    # i18n overlay: only the words that differ, everything else falls through to English
    assert "mobile numbers" in i18n.t("en-GB", "prop.part.body") and "cell numbers" in i18n.t("en", "prop.part.body")
    assert "Electronic Communications Act 2000" in i18n.t("en-GB", "prop.agree.body") and "Electronic Commerce Act 2000" in i18n.t("en-IE", "prop.agree.body") and "ESIGN" in i18n.t("en", "prop.agree.body")
    assert "Bacs" in i18n.t("en-GB", "prop.invest.body", price="£450", term=6) and "SEPA" in i18n.t("en-IE", "prop.invest.body", price="€450", term=6)
    assert i18n.t("en-GB", "pdf.avg") == "Average score" and i18n.t("en-IE", "mail.open_report") == "Open the live report" and i18n.month_label(__import__("datetime").datetime(2026, 9, 1), "en-GB") == "September 2026"
    # industry words
    assert ind.dept_label_for("collision", "en-GB") == "Bodyshop" and ind.dept_label_for("collision", "en-IE") == "Bodyshop" and ind.dept_label_for("collision", "en-US") == "Body Shop" and ind.dept_label_for("service", "nl-NL") == "Werkplaats"
    uk = ind.translated("automotive", "en-GB")
    assert uk["label"] == "Car dealership" and uk["departments"][0]["rep"] == "a sales executive" and uk["departments"][4]["prefix"] == "Bodyshop caller:" and uk["departments"][1]["label"] == "Service"
    assert ind.translated("automotive", "en-US")["departments"][0]["rep"] == "a salesperson" and ind.translated("real_estate", "en-GB")["label"] == "Real estate"
    assert ms.per_month_text_for({"sales": 4, "service": 2, "collision": 1}, "en-GB", " and ") == "4 sales, 2 service and 1 bodyshop"
    assert ms.per_month_text_for({"sales": 4, "collision": 1}, "en-US", " and ") == "4 sales and 1 body shop"
    # proposal + email + sms in British English, money in pounds / euro
    p = {"client_name": "Arnold Motors", "contact_name": "Tom Hughes", "terms": {"per_month": {"sales": 4, "collision": 1}, "price_monthly": 450, "term_months": 6}}
    secs = dict(ms.proposal_text(p, "en-GB"))
    assert set(secs) == {"What you get", "Your report", "Investment", "Your part", "Cancel", "Agreement"}
    assert "4 sales and 1 bodyshop" in secs["What you get"] and "£450 per month" in secs["Investment"] and "Bacs" in secs["Investment"] and "mobile numbers" in secs["Your part"] and "Electronic Communications Act" in secs["Agreement"]
    ie = dict(ms.proposal_text(p, "en-IE"))
    assert "€450 per month" in ie["Investment"] and "SEPA" in ie["Investment"] and "Electronic Commerce Act" in ie["Agreement"]
    subj, html = ms.proposal_email(p, "Forest", "Good to talk.", "https://x/proposal/t", "", "en-GB")
    assert subj == "Mystery shop proposal for Arnold Motors" and "Hi Tom," in html and "£450/month" in html and "4 sales and 1 bodyshop" in html
    ev = {"score_pct": 78, "results": [{"text": "Asked for the caller's name", "passed": True}, {"text": "Offered an appointment", "passed": False}]}
    sms = ms.scorecard_sms({"rep_name": "Tom Hughes", "store_name": "Arnold Motors"}, ev, "https://x/s", "", "en-GB")
    assert sms.startswith("Hi Tom, that practice call just now was from I'm On Social for Arnold Motors. You scored 78%.") and "Nailed: Asked for the caller's name" in sms
    assert ms.scorecard_sms({"rep_name": "Tom Hughes", "store_name": "X"}, ev, "https://x/s").startswith("Hey Tom, that practice call")
    # grader + challenge library routing
    assert "British English" in sc.grader_language_rule("en-GB") and "Irish" in sc.grader_language_rule("en-IE") and sc.grader_language_rule("nl-NL").startswith("- LANGUAGE: the call is in Dutch") and sc.grader_language_rule("en") == "" and sc.grader_language_rule(None) == ""
    assert "UK dealership" in sc._grader_prompt({"name": "Phone up", "criteria": []}, "Tom", "Sophie", "inbound", 120, "automotive", "en-GB")
    assert ms.challenge_language({"locale": "en-IE"}) == "en-GB" and ms.challenge_language({"locale": "en-GB"}) == "en-GB" and ms.challenge_language({"locale": "nl-NL"}) == "nl" and ms.challenge_language({"locale": "en-US"}) == "en" and ms.challenge_language({}) == "en"
    assert ms.language_filter("en-GB") == {"language": "en-GB"} and "en-GB" in ms.LANGUAGE_NAMES
    sysm = ms._localize_system("en-GB", "automotive", ind.translated("automotive", "en-GB")["departments"][4], 2)
    assert "part exchange" in sysm and "Bodyshop caller:" in sysm and "3 to 4 min" in sysm and "tot" not in sysm
    # numbers the way a Brit or an Irish person says them
    uk_say = speakable("The Golf is £18,950 with 42,000 miles. Call me on 07123 456789.", "en-GB")
    assert "eighteen thousand nine hundred fifty pounds" in uk_say and "forty-two thousand miles" in uk_say and "oh seven one two three, four five six, seven eight nine" in uk_say
    ie_say = speakable("It is €24,500, I am on 087 123 4567.", "en-IE")
    assert "twenty-four thousand five hundred euros" in ie_say and "oh eight seven, one two three, four five six seven" in ie_say
    # number state / bundle rules
    st = sn.number_state({"locale": "en-GB", "name": "x"}, {})
    assert st["country"] == "GB" and st["kind"] == "mobile" and st["needs_bundle"] is True and st["bundle_on_file"] is False and st["needs_local_number"] is True
    assert sn.number_state({"locale": "en-GB"}, {"GB": {"bundle_sid": "BU" + "a" * 32}})["bundle_on_file"] is True
    assert sn.number_state({"locale": "nl-NL"}, {})["needs_bundle"] is False and sn.number_state({"locale": "en-US", "from_number": "+1435"}, {})["needs_local_number"] is False


def test_uk_client_public_pages_and_bundles(admin):
    r = requests.post(f"{API}/shop-clients", headers=admin, timeout=30, json={"name": "QA Arnold Motors Leeds", "industry": "automotive", "locale": "en-GB", "city": "Leeds", "contact_name": "Tom Hughes", "contact_email": "gm-leeds@invalid.imonsocial.test", "plan": {"per_month": {"sales": 4, "collision": 1}, "price_monthly": 450}})
    assert r.status_code == 200, r.text
    c = r.json()
    cid = c["id"]
    bu, ad = "BU" + "0" * 32, "AD" + "0" * 32
    try:
        assert c["locale"] == "en-GB" and c["currency"] == "gbp" and c["country"] == "GB" and c["number_state"] == {"own": False, "needs_local_number": True, "error": None}
        assert c["timezone"] == "Europe/London"
        # bundles: none on file -> state says so; validation; save; state flips; clear
        st = requests.get(f"{API}/shop-clients/{cid}/number", headers=admin, timeout=30).json()
        assert st["country"] == "GB" and st["needs_bundle"] is True and "UK" in st["bundle_needs"]
        b0 = requests.get(f"{API}/shop-clients/number/bundles", headers=admin, timeout=30).json()
        assert {x["country"] for x in b0["countries"]} == {"GB", "IE", "BE"}
        gb_before = next(x for x in b0["countries"] if x["country"] == "GB")
        assert requests.put(f"{API}/shop-clients/number/bundles", headers=admin, timeout=30, json={"country": "NL", "bundle_sid": bu, "address_sid": ad}).status_code == 400
        assert requests.put(f"{API}/shop-clients/number/bundles", headers=admin, timeout=30, json={"country": "GB", "bundle_sid": "nope", "address_sid": ad}).status_code == 400
        assert requests.put(f"{API}/shop-clients/number/bundles", headers=admin, timeout=30, json={"country": "GB", "bundle_sid": bu, "address_sid": "AD1"}).status_code == 400
        if not gb_before["on_file"]:
            saved = requests.put(f"{API}/shop-clients/number/bundles", headers=admin, timeout=30, json={"country": "gb", "bundle_sid": bu, "address_sid": ad}).json()
            gb = next(x for x in saved["countries"] if x["country"] == "GB")
            assert gb["on_file"] is True and gb["bundle_sid"] == bu and gb["address_sid"] == ad
            assert requests.get(f"{API}/shop-clients/{cid}/number", headers=admin, timeout=30).json()["bundle_on_file"] is True
            cleared = requests.put(f"{API}/shop-clients/number/bundles", headers=admin, timeout=30, json={"country": "GB"}).json()
            assert next(x for x in cleared["countries"] if x["country"] == "GB")["on_file"] is False
        assert requests.delete(f"{API}/shop-clients/{cid}/number", headers=admin, timeout=30).status_code == 400
        # UK mobiles normalise to +44
        p = requests.post(f"{API}/shop-clients/{cid}/people", headers=admin, timeout=30, json={"name": "Sophie Walker", "phone": "07123 456789", "department": "sales"})
        assert p.status_code == 200 and p.json()["phone"] == "+447123456789", p.text
        bad = requests.post(f"{API}/shop-clients/{cid}/people", headers=admin, timeout=30, json={"name": "Bad", "phone": "0712", "department": "sales"})
        assert bad.status_code == 400 and "07123 456789" in bad.json()["detail"]
        # proposal: British wording, pounds
        pr = requests.post(f"{API}/shop-clients/{cid}/proposals", headers=admin, timeout=30, json={"per_month": {"sales": 4, "collision": 1}, "price_monthly": 450, "term_months": 6})
        assert pr.status_code == 200, pr.text
        prop = pr.json()
        prev = requests.get(f"{API}/shop-clients/proposals/{prop['id']}/email-preview", headers=admin, timeout=30).json()
        assert "Hi Tom," in prev["html"] and "4 sales and 1 bodyshop" in prev["html"] and "£450/month" in prev["html"]
        pub = requests.get(f"{API}/public/proposal/{prop['token']}", timeout=30).json()
        assert pub["language"] == "en-GB" and pub["locale"] == "en-GB" and pub["currency"] == "gbp" and pub["business_noun"] == "dealership"
        secs = {s["title"]: s["body"] for s in pub["sections"]}
        assert "mobile numbers" in secs["Your part"] and "Electronic Communications Act" in secs["Agreement"] and "£450 per month" in secs["Investment"]
        assert [d["label"] for d in pub["departments"]][-1] == "Bodyshop"
        # kickoff page
        detail = requests.get(f"{API}/shop-clients/{cid}", headers=admin, timeout=30).json()
        assert detail["departments"][-1]["label"] == "Body Shop"  # admin surface stays English until Phase E
        tok = detail["kickoff_url"].rsplit("/", 1)[-1]
        k = requests.get(f"{API}/public/shop-kickoff/{tok}", timeout=30).json()
        assert k["client"]["language"] == "en-GB" and k["client"]["country"] == "GB" and k["client"]["offering"]["label"] == "vehicle" and "forecourt" in k["client"]["offering"]["field_help"]
        assert any(t["id"] == "Europe/London" for t in k["timezones"]) and k["departments"][-1]["label"] == "Bodyshop" and k["departments"][0]["rep"] == "a sales executive"
        # report + pdf carry the dialect; department labels British
        rep = requests.get(f"{API}/public/shop-report/{detail['client']['report_token']}", timeout=30).json()
        assert rep["language"] == "en-GB" and rep["client"]["locale"] == "en-GB" and rep["client"]["industry_label"] == "Car dealership" and rep["by_department"]["collision"]["label"] == "Bodyshop"
        assert rep["month_label"].split(" ")[0] in ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")
        pdf = requests.get(f"{API}/public/shop-report/{detail['client']['report_token']}.pdf", timeout=60)
        assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"
        # an Irish client draws from the British challenge library (approved only), falling back to English while none exist
        async def run():
            db = _db()
            client = await db.shop_clients.find_one({"_id": ObjectId(cid)})
            await db.shop_clients.update_one({"_id": client["_id"]}, {"$set": {"locale": "en-IE"}})
            client["locale"] = "en-IE"
            target = await db.shop_targets.find_one({"_id": ObjectId(p.json()["id"])})
            pick = await ms.pick_challenge(db, client, target)
            assert pick and (pick.get("language") or "en") in ("en", "en-GB")
            assert not any(s.get("language") == "en-GB" for s in await ms.challenge_pool(db, cid, "sales"))
        asyncio.run(run())
        lib = requests.get(f"{API}/shop-clients/challenges", headers=admin, timeout=30, params={"language": "en-GB", "industry": "automotive"}).json()
        assert lib["language"] == "en-GB" and any(l["code"] == "en-GB" for l in lib["languages"]) and lib["review"]["language_label"].startswith("British")
    finally:
        gb_now = next(x for x in requests.get(f"{API}/shop-clients/number/bundles", headers=admin, timeout=30).json()["countries"] if x["country"] == "GB")
        if gb_now["bundle_sid"] == bu:
            requests.put(f"{API}/shop-clients/number/bundles", headers=admin, timeout=30, json={"country": "GB"})
        requests.delete(f"{API}/shop-clients/{cid}", headers=admin, timeout=30)
