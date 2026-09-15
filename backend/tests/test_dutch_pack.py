"""Phase B/C Dutch pack: client-facing pages, emails and texts in Dutch; Jessi's Dutch challenge drafts gated by a native reviewer;
CSV bulk import of dealers; per-client local number state. Never buys a Twilio number."""
import asyncio
import os
from datetime import datetime, timezone

import pytest
import requests
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

from services import industries as ind
from services import mystery_shops as ms
from services import scorecards as sc
from services import shop_report_mail as srm

BASE_URL = [l.split("=", 1)[1].strip() for l in open("/app/frontend/.env") if l.startswith("REACT_APP_BACKEND_URL=")][0].rstrip("/")
API = BASE_URL + "/api"


def _db():
    return AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


@pytest.fixture(scope="module")
def admin():
    r = requests.post(f"{API}/auth/login", json={"email": "forest@imosapp.com", "password": "Admin123!"}, timeout=30)
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json().get('token') or r.json().get('access_token')}"}


def test_dutch_texts_pure():
    p = {"client_name": "Autobedrijf Jansen", "contact_name": "Pieter Jansen", "terms": {"per_month": {"sales": 4, "service": 2, "collision": 1}, "price_monthly": 450, "term_months": 6}}
    secs = dict(ms.proposal_text(p, "nl-NL"))
    assert set(secs) == {"Wat je krijgt", "Jullie rapport", "Investering", "Jullie deel", "Opzeggen", "Akkoord"}
    assert "4 verkoop, 2 werkplaats en 1 schadeherstel" in secs["Wat je krijgt"] and "€ 450 per maand" in secs["Investering"] and "eIDAS" in secs["Akkoord"]
    en = dict(ms.proposal_text(p))
    assert "$450 per month" in en["Investment"] and "4 sales, 2 service and 1 body shop" in en["What you get"]
    subj, html = ms.proposal_email(p, "Forest", "Leuk je gesproken te hebben.", "https://x/proposal/t", "", "nl-NL")
    assert subj == "Mystery shop voorstel voor Autobedrijf Jansen" and "Hoi Pieter," in html and "€ 450 per maand" in html and "Bekijk en onderteken" in html and "Leuk je gesproken" in html
    subj_en, html_en = ms.proposal_email(p, "Forest", "", "https://x", "")
    assert subj_en.startswith("Mystery shop proposal") and "$450/month" in html_en and "Review and sign" in html_en
    assert ms.money_text(1250, "nl-NL") == "€ 1.250" and ms.money_text(1250, "en-US") == "$1,250" and ms.money_text(400, "en-GB") == "£400"
    ev = {"score_pct": 78, "results": [{"text": "Vroeg de naam van de klant", "passed": True}, {"text": "Vroeg om een afspraak", "passed": False}]}
    sms = ms.scorecard_sms({"rep_name": "Sanne de Vries", "store_name": "Autobedrijf Jansen"}, ev, "https://x/s", "", "nl")
    assert sms.startswith("Hoi Sanne, dat oefengesprek van net kwam van I'm On Social voor Autobedrijf Jansen. Je scoorde 78%.") and "Goed gedaan: Vroeg de naam" in sms and "Werk aan: Vroeg om een afspraak" in sms and "Volledige scorekaart" in sms
    assert "Hey Sanne, that practice call" in ms.scorecard_sms({"rep_name": "Sanne de Vries", "store_name": "X"}, ev, "https://x/s")
    # Dutch scorecard templates keep the criterion count and ids so grading history lines up
    for key in ("phone_up", "service_bdc", "parts_phone", "rental_phone", "collision_phone", "internet_sales"):
        en_b, nl_b = sc.template_body(key), sc.template_body(key, "nl")
        assert len(en_b["criteria"]) == len(nl_b["criteria"]) and [c["critical"] for c in en_b["criteria"]] == [c["critical"] for c in nl_b["criteria"]] and nl_b["language"] == "nl"
    assert sc.template_body("phone_up", "nl")["name"] == "Inkomend verkoopgesprek"
    assert ind.dept_label_for("service", "nl-NL") == "Werkplaats" and ind.dept_label_for("service", "en-US") == "Service" and ind.translated("automotive", "nl-NL")["business"] == "autobedrijf"
    assert ms.per_month_text_for({"sales": 4, "service": 2}, "nl-NL", " en ") == "4 verkoop en 2 werkplaats"
    fake_rep = {"language": "nl", "month_label": "september 2026", "summary": {"completed": 3, "planned": 6, "avg_score": 71, "people_shopped": 2, "needs_training": 1}, "by_department": {}}
    assert srm.summary_line(fake_rep).startswith("September 2026: 3 shops afgerond van 6 gepland, gemiddelde score 71%, 2 medewerkers gebeld, 1 heeft training nodig")


def test_dutch_client_public_pages_and_import(admin):
    r = requests.post(f"{API}/shop-clients", headers=admin, timeout=30, json={"name": "QA Autobedrijf Vermeer", "industry": "automotive", "locale": "nl-NL", "city": "Utrecht", "contact_name": "Pieter Vermeer", "contact_email": "gm-vermeer@invalid.imonsocial.test", "plan": {"per_month": {"sales": 4, "service": 2}, "price_monthly": 450}})
    assert r.status_code == 200, r.text
    c = r.json()
    cid = c["id"]
    created_ids = []
    try:
        assert c["number_state"] == {"own": False, "needs_local_number": True, "error": None}
        st = requests.get(f"{API}/shop-clients/{cid}/number", headers=admin, timeout=30).json()
        assert st["country"] == "NL" and st["kind"] == "mobile" and st["needs_local_number"] is True and st["own"] is False
        assert requests.delete(f"{API}/shop-clients/{cid}/number", headers=admin, timeout=30).status_code == 400  # nothing to release
        # Dutch phone formats normalise to E.164
        p = requests.post(f"{API}/shop-clients/{cid}/people", headers=admin, timeout=30, json={"name": "Sanne de Vries", "phone": "06 12345678", "department": "sales"})
        assert p.status_code == 200 and p.json()["phone"] == "+31612345678", p.text
        p2 = requests.post(f"{API}/shop-clients/{cid}/people", headers=admin, timeout=30, json={"name": "Kees Bakker", "phone": "0031 6 87654321", "department": "service"})
        assert p2.json()["phone"] == "+31687654321"
        assert requests.post(f"{API}/shop-clients/{cid}/people", headers=admin, timeout=30, json={"name": "Bad", "phone": "0612", "department": "sales"}).status_code == 400
        # proposal: stamped with the locale, email + public page in Dutch
        pr = requests.post(f"{API}/shop-clients/{cid}/proposals", headers=admin, timeout=30, json={"per_month": {"sales": 4, "service": 2}, "price_monthly": 450, "term_months": 6})
        assert pr.status_code == 200, pr.text
        prop = pr.json()
        prev = requests.get(f"{API}/shop-clients/proposals/{prop['id']}/email-preview", headers=admin, timeout=30).json()
        assert prev["subject"] == "Mystery shop voorstel voor QA Autobedrijf Vermeer" and "Hoi Pieter," in prev["html"] and "4 verkoop en 2 werkplaats" in prev["html"]
        pub = requests.get(f"{API}/public/proposal/{prop['token']}", timeout=30).json()
        assert pub["language"] == "nl" and pub["locale"] == "nl-NL" and pub["currency"] == "eur" and pub["sections"][0]["title"] == "Wat je krijgt" and pub["business_noun"] == "autobedrijf"
        assert [d["label"] for d in pub["departments"]][:2] == ["Verkoop", "Werkplaats"]
        # kickoff page in Dutch
        detail = requests.get(f"{API}/shop-clients/{cid}", headers=admin, timeout=30).json()
        tok = detail["kickoff_url"].rsplit("/", 1)[-1]
        k = requests.get(f"{API}/public/shop-kickoff/{tok}", timeout=30).json()
        assert k["client"]["language"] == "nl" and k["client"]["country"] == "NL" and k["client"]["offering"]["label"] == "auto" and k["client"]["customer_noun"] == "mystery shopper"
        assert any(t["id"] == "Europe/Amsterdam" for t in k["timezones"]) and k["departments"][0]["label"] == "Verkoop"
        # kickoff submit with a Dutch-formatted number (no number purchase: PUBLIC_FACING_URL guard is Twilio's problem; we patch buy to a no-op)
        bad = requests.post(f"{API}/public/shop-kickoff/{tok}", timeout=30, json={"contact_name": "Pieter", "hours": {"start": "09:00", "end": "18:00", "days": [0, 1, 2, 3, 4]}, "timezone": "Europe/Amsterdam", "vehicles": ["2024 Volkswagen Golf"], "people": [{"name": "Nieuw", "phone": "12", "department": "sales"}]})
        assert bad.status_code == 400 and "mobile number" in bad.json()["detail"]
        # public report + score payloads carry the language
        rep = requests.get(f"{API}/public/shop-report/{detail['client']['report_token']}", timeout=30).json()
        assert rep["language"] == "nl" and rep["client"]["locale"] == "nl-NL" and rep["client"]["industry_label"] == "Autobedrijf" and rep["month_label"].split(" ")[0] in ("januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus", "september", "oktober", "november", "december")
        pdf = requests.get(f"{API}/public/shop-report/{detail['client']['report_token']}.pdf", timeout=60)
        assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"
        # CSV import: semicolons, Dutch money, duplicate detection, dry run then real
        csv = ("naam;plaats;contact_name;e-mail;contact_phone;sales;service;price;vat_id\n"
               "QA Import Autobedrijf De Wit;Amersfoort;Anna de Wit;anna@invalid.imonsocial.test;06 11223344;4;2;€ 1.250,00;NL999999999B01\n"
               "QA Autobedrijf Vermeer;Utrecht;Pieter;gm-vermeer@invalid.imonsocial.test;;1;0;100;\n"
               ";Nowhere;;;;;;;\n")
        dry = requests.post(f"{API}/shop-clients/import", headers=admin, timeout=60, json={"csv": csv, "locale": "nl-NL", "dry_run": True}).json()
        assert dry["dry_run"] is True and dry["created"] == 1 and dry["skipped"] == 1 and dry["errors"] == 1, dry
        assert dry["created_items"][0]["name"] == "QA Import Autobedrijf De Wit" and dry["created_items"][0]["price"] == 1250.0 and dry["created_items"][0]["per_month"] == {"sales": 4, "service": 2} and dry["created_items"][0]["locale"] == "nl-NL"
        assert dry["skipped_items"][0]["name"] == "QA Autobedrijf Vermeer" and dry["error_items"][0]["reason"] == "name is missing"
        assert requests.get(f"{API}/shop-clients", headers=admin, timeout=30).json()["clients"].__len__() >= 1
        real = requests.post(f"{API}/shop-clients/import", headers=admin, timeout=60, json={"csv": csv, "locale": "nl-NL"}).json()
        assert real["created"] == 1 and real["created_items"][0]["id"]
        created_ids.append(real["created_items"][0]["id"])
        imp = requests.get(f"{API}/shop-clients/{created_ids[0]}", headers=admin, timeout=30).json()["client"]
        assert imp["locale"] == "nl-NL" and imp["timezone"] == "Europe/Amsterdam" and imp["contact_phone"] == "+31611223344" and imp["vat_id"] == "NL999999999B01" and imp["plan"]["price_monthly"] == 1250.0 and imp["city"] == "Amersfoort"
        again = requests.post(f"{API}/shop-clients/import", headers=admin, timeout=60, json={"csv": csv, "locale": "nl-NL", "dry_run": True}).json()
        assert again["created"] == 0 and again["skipped"] == 2
        assert requests.post(f"{API}/shop-clients/import", headers=admin, timeout=30, json={"csv": "", "dry_run": True}).status_code == 400
        tpl = requests.get(f"{API}/shop-clients/import/template", headers=admin, timeout=30).json()
        assert "name" in tpl["columns"] and "vat_id" in tpl["columns"]
    finally:
        for x in [cid, *created_ids]:
            requests.delete(f"{API}/shop-clients/{x}", headers=admin, timeout=30)


def test_dutch_review_gate(admin):
    """Dutch drafts are invisible to the caller until approved; with none approved the client falls back to the English library."""
    r = requests.post(f"{API}/shop-clients", headers=admin, timeout=30, json={"name": "QA Autobedrijf Review", "industry": "automotive", "locale": "nl-NL", "plan": {"per_month": {"sales": 1}, "price_monthly": 100}})
    cid = r.json()["id"]
    p = requests.post(f"{API}/shop-clients/{cid}/people", headers=admin, timeout=30, json={"name": "Test Persoon", "phone": "+31612340000", "department": "sales"}).json()
    slug = "qa_review_gate_nl"
    now = datetime.now(timezone.utc)
    doc = {"kind": "phone", "pool": "mystery_shop", "industry": "automotive", "shop_client_id": None, "store_id": None, "slug": slug, "source_slug": "shop_sales_price", "language": "nl", "department": "sales", "direction": "inbound",
           "category": "Verkoop", "title": "Verkoopbeller: QA review gate", "runtime": "3 tot 4 min", "purpose": "QA", "body": "Test", "success_points": ["a"], "curveballs": [], "persona": {"name": "Sanne de Vries", "voice": "female", "summary": "x", "goals": "y", "objections": [], "opening_line": "Hoi"},
           "active": True, "generated_from": "localized", "review": {"status": "needs_review", "at": now}, "created_at": now, "updated_at": now}

    async def run():
        db = _db()
        await db.scripts.delete_many({"slug": slug})
        res = await db.scripts.insert_one(doc)
        sid = str(res.inserted_id)
        try:
            client = await db.shop_clients.find_one({"_id": ObjectId(cid)})
            target = await db.shop_targets.find_one({"_id": ObjectId(p["id"])})
            nl_pool = await ms.challenge_pool(db, cid, "sales", language="nl")
            assert any(str(s["_id"]) == sid for s in nl_pool)
            assert not any(str(s["_id"]) == sid for s in await ms.challenge_pool(db, cid, "sales", language="nl", approved_only=True))
            assert not any(s.get("language") == "nl" for s in await ms.challenge_pool(db, cid, "sales"))
            pick = await ms.pick_challenge(db, client, target)
            assert pick and str(pick["_id"]) != sid  # an unreviewed Dutch draft never reaches a caller (approved Dutch ones or the English fallback do)
            assert (pick.get("language") or "en") == "en" or (pick.get("review") or {}).get("status") == "approved"
            # review endpoints
            summary = requests.get(f"{API}/shop-clients/challenges/review", headers=admin, timeout=30, params={"language": "nl", "industry": "automotive"}).json()
            assert summary["pending"] >= 1 and any(i["id"] == sid for i in summary["pending_items"]) and summary["source_total"] >= 10 and summary["by_department"]["sales"]["pending"] >= 1
            lib = requests.get(f"{API}/shop-clients/challenges", headers=admin, timeout=30, params={"language": "nl", "industry": "automotive"}).json()
            assert lib["language"] == "nl" and any(l["code"] == "nl" for l in lib["languages"]) and lib["review"]["pending"] >= 1
            mine = next(x for x in lib["challenges"] if x["id"] == sid)
            assert mine["language"] == "nl" and mine["review"]["status"] == "needs_review" and mine["source_slug"] == "shop_sales_price"
            assert not any(x["id"] == sid for x in requests.get(f"{API}/shop-clients/challenges", headers=admin, timeout=30, params={"industry": "automotive"}).json()["challenges"])
            client_pool = requests.get(f"{API}/shop-clients/{cid}/challenges", headers=admin, timeout=30).json()["challenges"]
            assert any(x["id"] == sid for x in client_pool)  # the Dutch client's tab lists Dutch drafts (so the reviewer can approve from there too)
            assert requests.put(f"{API}/shop-clients/challenges/{sid}/review", headers=admin, timeout=30, json={"status": "bogus"}).status_code == 400
            ok = requests.put(f"{API}/shop-clients/challenges/{sid}/review", headers=admin, timeout=30, json={"status": "approved"}).json()
            assert ok["review"]["status"] == "approved" and ok["review"]["by_name"]
            pick2 = await ms.pick_challenge(db, client, target)
            approved_ids = {str(s["_id"]) for s in await ms.challenge_pool(db, cid, "sales", language="nl", approved_only=True)}
            assert sid in approved_ids and pick2 and str(pick2["_id"]) in approved_ids  # approved Dutch challenges are what the caller draws from now
            back = requests.put(f"{API}/shop-clients/challenges/{sid}/review", headers=admin, timeout=30, json={"status": "needs_review"}).json()
            assert back["review"]["status"] == "needs_review"
            allr = requests.post(f"{API}/shop-clients/challenges/review/approve-all", headers=admin, timeout=30, json={"language": "nl"}).json()
            assert allr["approved"] >= 1 and allr["review"]["pending"] == 0
            assert requests.post(f"{API}/shop-clients/challenges/localize", headers=admin, timeout=30, json={"language": "fr", "industry": "automotive"}).status_code == 400
            assert requests.post(f"{API}/shop-clients/challenges/localize", headers=admin, timeout=30, json={"language": "nl", "industry": "nope"}).status_code == 400
        finally:
            await db.scripts.delete_many({"slug": slug})
    try:
        asyncio.run(run())
    finally:
        requests.delete(f"{API}/shop-clients/{cid}", headers=admin, timeout=30)
