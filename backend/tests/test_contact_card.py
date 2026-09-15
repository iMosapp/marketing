"""Contact card: the shop number as a .vcf reps save. Settings (name), per-client link + page + vcf (English and Dutch), texting it to people.
Sends only go to 500-555 test numbers (Twilio accepts them as queued and never delivers)."""
import requests
from services import mystery_shops as ms

BASE_URL = [l.split("=", 1)[1].strip() for l in open("/app/frontend/.env") if l.startswith("REACT_APP_BACKEND_URL=")][0].rstrip("/")
API = BASE_URL + "/api"


def _admin():
    r = requests.post(f"{API}/auth/login", json={"email": "forest@imosapp.com", "password": "Admin123!"}, timeout=30)
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json().get('token') or r.json().get('access_token')}"}


def test_vcard_pure():
    card = {"name": "Mystery Shop", "org": "I'm On Social"}
    v = ms.contact_vcard(card, "+14352203414", {"name": "QA Jeep", "locale": "en-US"})
    assert v.startswith("BEGIN:VCARD\r\nVERSION:3.0\r\nN:;Mystery Shop;;;\r\nFN:Mystery Shop\r\nORG:I'm On Social\r\nTEL;TYPE=CELL,VOICE:+14352203414\r\nNOTE:Practice calls and scorecard texts for QA Jeep come from this number. \r\n I'm On Social.\r\n")
    assert "PHOTO;ENCODING=b;TYPE=PNG:" in v and v.endswith("END:VCARD\r\n") and all(len(line) <= 75 for line in v.split("\r\n"))
    unfold = lambda t: t.replace("\r\n ", "")
    nl = unfold(ms.contact_vcard({"name": "Oefengesprek", "org": "I'm On Social"}, "+31970101234", {"name": "Autobedrijf Jansen", "locale": "nl-NL"}))
    assert "FN:Oefengesprek" in nl and "NOTE:Oefengesprekken en scorekaart-berichten voor Autobedrijf Jansen komen van dit nummer." in nl
    assert "NOTE:Practice calls and scorecard texts from I'm On Social come from this number." in unfold(ms.contact_vcard(card, "+14352203414", None))
    sms = ms.contact_sms(card, {"name": "QA Jeep", "locale": "en-US"}, {"name": "Sam Seller"}, "Forest", "https://x/c/t")
    assert sms == "Hi Sam, Forest here with I'm On Social. QA Jeep signed the team up for practice calls and scorecards from this number. Save it as a contact so you know it's us when we call: https://x/c/t"
    assert ms.contact_sms(card, {"name": "Jansen", "locale": "nl-NL"}, {"name": "Kees de Vries"}, "Forest", "https://x").startswith("Hoi Kees, Forest hier van I'm On Social. Jansen heeft het team aangemeld voor oefengesprekken")
    page = ms.contact_page(card, "+14352203414", {"name": "QA Jeep", "locale": "en-GB"}, "https://x/t.vcf")
    assert "Save Mystery Shop to your contacts" in page and "(435) 220-3414" in page and 'href="https://x/t.vcf"' in page and "noindex" in page
    assert "Sla Mystery Shop op in je contacten" in ms.contact_page(card, "+31612345678", {"name": "J", "locale": "nl-NL"}, "https://x.vcf") and "+31 6 12345678" in ms.contact_page(card, "+31612345678", None, "x")
    assert ms._pretty_phone("+31970101234") == "+31 97 0101234" and ms._pretty_phone("+447123456789") == "+44 7123 456789"


def test_contact_card_api():
    admin = _admin()
    # settings: name is editable, validated, and flows into every link
    orig = requests.get(f"{API}/shop-clients/number/contact-card", headers=admin, timeout=30).json()
    assert orig["org"] == "I'm On Social" and orig["url"].endswith("/api/public/shop-contact/platform") and orig["vcf_url"].endswith("/platform.vcf") and orig["phone_number"].startswith("+")
    assert requests.put(f"{API}/shop-clients/number/contact-card", headers=admin, json={"name": "   "}, timeout=30).status_code == 400
    assert requests.get(f"{API}/shop-clients/number/contact-card", timeout=30).status_code in (401, 403)
    c = requests.post(f"{API}/shop-clients", headers=admin, timeout=30, json={"name": "QA Contact Card Motors", "industry": "automotive", "locale": "en-US", "city": "Provo", "plan": {"per_month": {"sales": 2}, "price_monthly": 200}}).json()
    cid = c["id"]
    try:
        renamed = requests.put(f"{API}/shop-clients/number/contact-card", headers=admin, json={"name": "Practice Call"}, timeout=30).json()
        assert renamed["name"] == "Practice Call"
        empty = requests.get(f"{API}/shop-clients/{cid}/contact-card", headers=admin, timeout=30).json()
        assert empty["name"] == "Practice Call" and empty["total"] == 0 and empty["sent"] == 0 and empty["mms"] is True and "QA Contact Card Motors" in empty["sms_preview"]
        tok = empty["url"].rsplit("/", 1)[-1]
        assert len(tok) == 32 and empty["vcf_url"] == empty["url"] + ".vcf"
        assert requests.get(f"{API}/shop-clients/{cid}/contact-card", headers=admin, timeout=30).json()["url"] == empty["url"]  # token is stable
        assert requests.post(f"{API}/shop-clients/{cid}/contact-card/send", headers=admin, json={"target_ids": []}, timeout=30).status_code == 400
        # public page + vcf on the preview host, in the client's language, renamed
        page = requests.get(f"{API}/public/shop-contact/{tok}", timeout=30)
        assert page.status_code == 200 and page.headers["content-type"].startswith("text/html") and "Save Practice Call to your contacts" in page.text and "QA Contact Card Motors" in page.text
        vcf = requests.get(f"{API}/public/shop-contact/{tok}.vcf", timeout=30)
        assert vcf.status_code == 200 and vcf.headers["content-type"].startswith("text/vcard") and 'filename="Practice_Call.vcf"' in vcf.headers["content-disposition"]
        assert "FN:Practice Call" in vcf.text and f"TEL;TYPE=CELL,VOICE:{empty['phone_number']}" in vcf.text and "QA Contact Card Motors" in vcf.text.replace("\r\n ", "")
        assert requests.get(f"{API}/public/shop-contact/platform.vcf", timeout=30).status_code == 200 and requests.get(f"{API}/public/shop-contact/nope", timeout=30).status_code == 404
        assert requests.get(f"{API}/public/shop-contact/logo.png", timeout=30).headers["content-type"] == "image/png"
        # people + send (500-555 test numbers only)
        a = requests.post(f"{API}/shop-clients/{cid}/people", headers=admin, json={"name": "Card Alpha", "phone": "(500) 555-0181", "department": "sales"}, timeout=30).json()
        b = requests.post(f"{API}/shop-clients/{cid}/people", headers=admin, json={"name": "Card Bravo", "phone": "(500) 555-0182", "department": "sales"}, timeout=30).json()
        assert a["contact_card_sent_at"] is None and a["contact_card_ok"] is None
        one = requests.post(f"{API}/shop-clients/{cid}/contact-card/send", headers=admin, json={"target_ids": [a["id"]]}, timeout=60).json()
        assert one["sent"] == 1 and one["failed"] == [] and one["results"][0]["phone"] == "+15005550181"
        st = requests.get(f"{API}/shop-clients/{cid}/contact-card", headers=admin, timeout=30).json()
        assert st["sent"] == 1 and st["total"] == 2 and next(p for p in st["people"] if p["id"] == a["id"])["ok"] is True and next(p for p in st["people"] if p["id"] == b["id"])["ok"] is None
        people = requests.get(f"{API}/shop-clients/{cid}", headers=admin, timeout=30).json()["people"]
        assert next(p for p in people if p["id"] == a["id"])["contact_card_ok"] is True and next(p for p in people if p["id"] == a["id"])["contact_card_sent_at"]
        everyone = requests.post(f"{API}/shop-clients/{cid}/contact-card/send", headers=admin, json={"target_ids": []}, timeout=60).json()
        assert everyone["sent"] == 2 and requests.get(f"{API}/shop-clients/{cid}/contact-card", headers=admin, timeout=30).json()["sent"] == 2
    finally:
        requests.put(f"{API}/shop-clients/number/contact-card", headers=admin, json={"name": orig["name"], "org": orig["org"]}, timeout=30)
        requests.delete(f"{API}/shop-clients/{cid}", headers=admin, timeout=30)
