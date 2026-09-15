"""End-to-end verification tests for UK + Ireland English pack review."""
import os
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://user-routing-issue.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "forest@imosapp.com"
ADMIN_PASS = "Admin123!"

UK_CLIENT_ID = "6aa8b13f2c2d5fb494b1532e"
UK_PROPOSAL_TOKEN = "08fb4ad374b049a387e6ada59227a80e"
UK_KICKOFF_TOKEN = "c03ad1fa10234f6dae86a845b13f76d1"
UK_REPORT_TOKEN = "ef5113d7b7f8404e89aa54f39054c60c"
NL_REPORT_TOKEN = "61646e08ba83440bbcbae301ebd5f24e"
US_REPORT_TOKEN = "51c51185fdbf45e3b15efbadf3e3b203"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=20)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


# --- Public report endpoints ---
class TestPublicShopReport:
    def test_en_gb_report(self):
        r = requests.get(f"{BASE_URL}/api/public/shop-report/{UK_REPORT_TOKEN}", timeout=20)
        assert r.status_code == 200
        data = r.json()
        assert data.get("language") == "en-GB", f"language={data.get('language')}"
        assert data.get("client", {}).get("industry_label") == "Car dealership"
        by_dept = data.get("by_department", {})
        # Collision label should be 'Bodyshop' (one word)
        assert "collision" in by_dept
        assert by_dept["collision"].get("label") == "Bodyshop"

    def test_en_gb_report_pdf(self):
        r = requests.get(f"{BASE_URL}/api/public/shop-report/{UK_REPORT_TOKEN}.pdf", timeout=30)
        assert r.status_code == 200
        assert r.content[:4] == b"%PDF", r.content[:20]

    def test_dutch_report_regression(self):
        r = requests.get(f"{BASE_URL}/api/public/shop-report/{NL_REPORT_TOKEN}", timeout=20)
        assert r.status_code == 200
        data = r.json()
        assert data.get("language") == "nl", data.get("language")
        by_dept = data.get("by_department", {})
        assert by_dept.get("service", {}).get("label") == "Werkplaats", by_dept.get("service")

    def test_us_report_regression(self):
        r = requests.get(f"{BASE_URL}/api/public/shop-report/{US_REPORT_TOKEN}", timeout=20)
        assert r.status_code == 200
        data = r.json()
        assert data.get("language") == "en", data.get("language")
        by_dept = data.get("by_department", {})
        # US = 'Body Shop' two words
        assert by_dept.get("collision", {}).get("label") == "Body Shop", by_dept.get("collision")


# --- Bundle API validation ---
class TestBundleApi:
    def test_get_bundles_lists_gb_ie_be(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/shop-clients/number/bundles", headers=auth_headers, timeout=15)
        assert r.status_code == 200
        data = r.json()
        items = data.get("countries", [])
        countries = {it["country"] for it in items}
        assert countries == {"GB", "IE", "BE"}, countries
        for it in items:
            assert isinstance(it.get("needs"), str) and it["needs"], it

    def test_put_bundle_rejects_nl(self, auth_headers):
        r = requests.put(f"{BASE_URL}/api/shop-clients/number/bundles",
                         headers=auth_headers,
                         json={"country": "NL"}, timeout=15)
        assert r.status_code == 400, r.text

    def test_put_bundle_rejects_bad_address(self, auth_headers):
        r = requests.put(f"{BASE_URL}/api/shop-clients/number/bundles",
                         headers=auth_headers,
                         json={"country": "GB", "bundle_sid": "BU" + "0" * 32, "address_sid": "AD1"},
                         timeout=15)
        assert r.status_code == 400, r.text

    def test_put_bundle_rejects_bad_bundle_sid(self, auth_headers):
        r = requests.put(f"{BASE_URL}/api/shop-clients/number/bundles",
                         headers=auth_headers,
                         json={"country": "GB", "bundle_sid": "nope", "address_sid": "AD" + "0" * 32},
                         timeout=15)
        assert r.status_code == 400, r.text
        msg = r.json()
        detail = str(msg)
        assert "BU" in detail, detail

    def test_unauthenticated_bundle_get(self):
        r = requests.get(f"{BASE_URL}/api/shop-clients/number/bundles", timeout=15)
        assert r.status_code in (401, 403), r.status_code


# --- Bundle save + client number state ---
class TestGbBundleFlow:
    def test_save_gb_bundle_then_clear(self, auth_headers):
        # SAVE
        good = {"country": "GB",
                "bundle_sid": "BU" + "0" * 32,
                "address_sid": "AD" + "0" * 32}
        r = requests.put(f"{BASE_URL}/api/shop-clients/number/bundles",
                         headers=auth_headers, json=good, timeout=15)
        assert r.status_code == 200, r.text

        # Verify list shows GB on_file true
        r2 = requests.get(f"{BASE_URL}/api/shop-clients/number/bundles",
                          headers=auth_headers, timeout=15)
        items = r2.json()["countries"]
        gb_row = next(it for it in items if it["country"] == "GB")
        assert gb_row.get("on_file") is True, gb_row

        # Client number state should reflect bundle_on_file true
        r3 = requests.get(f"{BASE_URL}/api/shop-clients/{UK_CLIENT_ID}/number",
                          headers=auth_headers, timeout=15)
        assert r3.status_code == 200, r3.text
        ns = r3.json()
        assert ns.get("bundle_on_file") is True, ns

        # CLEANUP: clear GB bundle
        clear = {"country": "GB"}
        r4 = requests.put(f"{BASE_URL}/api/shop-clients/number/bundles",
                          headers=auth_headers, json=clear, timeout=15)
        assert r4.status_code == 200, r4.text

        # verify cleared
        r5 = requests.get(f"{BASE_URL}/api/shop-clients/number/bundles",
                          headers=auth_headers, timeout=15)
        items = r5.json()["countries"]
        gb_row = next(it for it in items if it["country"] == "GB")
        assert gb_row.get("on_file") is False, gb_row

    def test_uk_client_number_state_no_own(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/shop-clients/{UK_CLIENT_ID}/number",
                         headers=auth_headers, timeout=15)
        assert r.status_code == 200, r.text
        ns = r.json()
        assert ns.get("own") in (False, None), ns


# --- People phone normalization ---
class TestUkPeoplePhone:
    _person_id = None

    def test_add_person_valid_mobile(self, auth_headers):
        payload = {"name": "QA Sophie Walker", "phone": "07123 456789", "role": "sales"}
        r = requests.post(f"{BASE_URL}/api/shop-clients/{UK_CLIENT_ID}/people",
                          headers=auth_headers, json=payload, timeout=15)
        assert r.status_code in (200, 201), r.text
        person = r.json()
        pid = person.get("id") or person.get("_id")
        # find by GET list
        rlist = requests.get(f"{BASE_URL}/api/shop-clients/{UK_CLIENT_ID}",
                             headers=auth_headers, timeout=15)
        assert rlist.status_code == 200
        people = rlist.json().get("people", [])
        matches = [p for p in people if p.get("name") == "QA Sophie Walker"]
        assert matches, f"no person found; people={people}"
        p = matches[-1]
        assert p.get("phone", "").startswith("+44"), p
        TestUkPeoplePhone._person_id = p.get("id") or p.get("_id") or pid

    def test_add_person_invalid_mobile(self, auth_headers):
        payload = {"name": "QA Bad", "phone": "0712", "role": "sales"}
        r = requests.post(f"{BASE_URL}/api/shop-clients/{UK_CLIENT_ID}/people",
                          headers=auth_headers, json=payload, timeout=15)
        assert r.status_code == 400, r.text
        text = r.text
        assert "07123 456789" in text, text

    def test_cleanup_person(self, auth_headers):
        pid = TestUkPeoplePhone._person_id
        if not pid:
            pytest.skip("no person id")
        r = requests.delete(f"{BASE_URL}/api/shop-clients/people/{pid}",
                            headers=auth_headers, timeout=15)
        assert r.status_code in (200, 204), r.text


# --- Challenge library languages ---
class TestChallengeLibrary:
    def test_languages_include_en_gb(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/shop-clients/challenges",
                         headers=auth_headers, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        langs = data.get("languages") or []
        codes = {l.get("code") for l in langs}
        assert {"en", "nl", "en-GB"}.issubset(codes), codes
        # Verify en-GB has a label mentioning British
        row = next(l for l in langs if l["code"] == "en-GB")
        assert "British" in row.get("label", ""), row

    def test_en_gb_review_status(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/shop-clients/challenges/review?language=en-GB",
                         headers=auth_headers, timeout=15)
        assert r.status_code == 200, r.text
