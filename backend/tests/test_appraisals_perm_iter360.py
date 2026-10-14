"""Backend regression for Trade Appraisal MVP1 - iter 360
Tests permission gate, tenant isolation, and validation.
"""
import os
import pytest
import requests
from tests import qa_creds

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://user-routing-issue.preview.emergentagent.com").rstrip("/")

CREDS = {
    "rep_perm_on": ("activation-tester@invalid.imonsocial.test", qa_creds.password_for("activation-tester@invalid.imonsocial.test")),
    "manager": ("qa-manager@invalid.imonsocial.test", qa_creds.password_for("qa-manager@invalid.imonsocial.test")),
    "orgadmin_other": ("qa-orgadmin@invalid.imonsocial.test", qa_creds.password_for("qa-orgadmin@invalid.imonsocial.test")),
    "rep_perm_off": ("mjeast1985@gmail.com", qa_creds.password_for("mjeast1985@gmail.com")),
    "super_admin": ("forest@imosapp.com", qa_creds.password_for("forest@imosapp.com")),
}

SARAH_CONTACT_ID = "6aa413008f0d53e3f2261853"


def _login(email, password):
    r = requests.post(f"{BASE}/api/auth/login", json={"email": email, "password": password}, timeout=30)
    if r.status_code != 200:
        return None
    data = r.json()
    token = data.get("token") or data.get("access_token")
    assert token, f"No token for {email}: {data}"
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def tokens():
    out = {}
    for k, (e, p) in CREDS.items():
        h = _login(e, p)
        if h is None:
            pytest.skip(f"Login failed for {k} ({e})")
        out[k] = h
    return out


class TestPermissionGate:
    def test_rep_without_permission_403(self, tokens):
        r = requests.get(f"{BASE}/api/appraisals", headers=tokens["rep_perm_off"], timeout=30)
        assert r.status_code == 403, f"expected 403, got {r.status_code}: {r.text[:300]}"
        assert "switched on" in r.text.lower() or "not switched" in r.text.lower(), r.text[:300]

    def test_store_manager_200(self, tokens):
        r = requests.get(f"{BASE}/api/appraisals", headers=tokens["manager"], timeout=30)
        assert r.status_code == 200, r.text[:300]

    def test_super_admin_200(self, tokens):
        r = requests.get(f"{BASE}/api/appraisals", headers=tokens["super_admin"], timeout=30)
        assert r.status_code == 200, r.text[:300]

    def test_rep_with_permission_200(self, tokens):
        r = requests.get(f"{BASE}/api/appraisals", headers=tokens["rep_perm_on"], timeout=30)
        assert r.status_code == 200, r.text[:300]


class TestVinValidation:
    def test_bad_check_digit(self, tokens):
        r = requests.post(f"{BASE}/api/appraisals/vin/decode",
                          json={"vin": "1HGCM82633A004351"},
                          headers=tokens["rep_perm_on"], timeout=30)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        v = data.get("validation", {})
        assert v.get("valid") is False, f"expected valid=false: {data}"
        errs = " ".join(v.get("errors", []) + [v.get("error", "")])
        assert "check digit" in errs.lower(), f"expected 'Check digit' error, got {v}"

    def test_valid_vin_decode(self, tokens):
        r = requests.post(f"{BASE}/api/appraisals/vin/decode",
                          json={"vin": "1HGCM82633A004352"},
                          headers=tokens["rep_perm_on"], timeout=30)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        veh = d.get("vehicle", {}) or d.get("decoded", {})
        assert veh.get("make") == "Honda", d
        assert veh.get("model") == "Accord", d
        assert veh.get("year") in (2003, "2003"), d
        assert veh.get("decoded_by") == "nhtsa_vpic", d


class TestTenantIsolation:
    @pytest.fixture(scope="class")
    def seed_appraisal(self, tokens):
        # ensure an appraisal exists for activation-tester on Sarah
        r = requests.post(f"{BASE}/api/appraisals",
                          json={"contact_id": SARAH_CONTACT_ID},
                          headers=tokens["rep_perm_on"], timeout=30)
        assert r.status_code in (200, 201), r.text[:300]
        appr = r.json().get("appraisal") or r.json()
        aid = appr.get("id") or appr.get("_id")
        yield aid
        requests.delete(f"{BASE}/api/appraisals/{aid}", headers=tokens["rep_perm_on"], timeout=30)

    def test_other_org_cannot_list(self, tokens, seed_appraisal):
        r = requests.get(f"{BASE}/api/appraisals", headers=tokens["orgadmin_other"], timeout=30)
        # orgadmin might get 200 (empty) or 403 if trade_appraisal is off
        if r.status_code == 200:
            ids = [a.get("id") for a in r.json().get("appraisals", r.json() if isinstance(r.json(), list) else [])]
            assert seed_appraisal not in ids, f"leaked appraisal {seed_appraisal} to other org"

    def test_other_org_cannot_get(self, tokens, seed_appraisal):
        r = requests.get(f"{BASE}/api/appraisals/{seed_appraisal}", headers=tokens["orgadmin_other"], timeout=30)
        assert r.status_code in (403, 404), r.text[:200]

    def test_other_org_cannot_mileage(self, tokens, seed_appraisal):
        r = requests.post(f"{BASE}/api/appraisals/{seed_appraisal}/mileage",
                          json={"confirmed": 10000, "source": "manual"},
                          headers=tokens["orgadmin_other"], timeout=30)
        assert r.status_code in (403, 404), r.text[:200]

    def test_other_org_cannot_get_vehicles(self, tokens):
        r = requests.get(f"{BASE}/api/appraisals/vehicles/{SARAH_CONTACT_ID}",
                         headers=tokens["orgadmin_other"], timeout=30)
        assert r.status_code in (403, 404), r.text[:200]

    def test_same_store_manager_can_list(self, tokens, seed_appraisal):
        r = requests.get(f"{BASE}/api/appraisals", headers=tokens["manager"], timeout=30)
        assert r.status_code == 200, r.text[:200]

    def test_same_store_manager_can_get(self, tokens, seed_appraisal):
        r = requests.get(f"{BASE}/api/appraisals/{seed_appraisal}", headers=tokens["manager"], timeout=30)
        assert r.status_code == 200, r.text[:200]


class TestValidationErrors:
    def test_wrong_rep_contact(self, tokens):
        # pick a contact id that doesn't belong to activation-tester? use a bogus id
        r = requests.post(f"{BASE}/api/appraisals",
                          json={"contact_id": "000000000000000000000000"},
                          headers=tokens["rep_perm_on"], timeout=30)
        assert r.status_code == 404, r.text[:200]

    def test_impossible_mileage(self, tokens):
        # create an appraisal, then try insane mileage
        r = requests.post(f"{BASE}/api/appraisals",
                          json={"contact_id": SARAH_CONTACT_ID},
                          headers=tokens["rep_perm_on"], timeout=30)
        assert r.status_code in (200, 201)
        appr = r.json().get("appraisal") or r.json()
        aid = appr.get("id") or appr.get("_id")
        r2 = requests.post(f"{BASE}/api/appraisals/{aid}/mileage",
                           json={"confirmed": 2000000, "source": "manual"},
                           headers=tokens["rep_perm_on"], timeout=30)
        requests.delete(f"{BASE}/api/appraisals/{aid}", headers=tokens["rep_perm_on"], timeout=30)
        assert r2.status_code == 400, f"expected 400, got {r2.status_code}: {r2.text[:200]}"

    def test_bogus_media_role(self, tokens):
        r = requests.post(f"{BASE}/api/appraisals",
                          json={"contact_id": SARAH_CONTACT_ID},
                          headers=tokens["rep_perm_on"], timeout=30)
        appr = r.json().get("appraisal") or r.json()
        aid = appr.get("id") or appr.get("_id")
        r2 = requests.post(f"{BASE}/api/appraisals/{aid}/media/chunk",
                           json={"upload_id": "u1", "index": 0, "total": 1,
                                 "data": "aGVsbG8=", "name": "x.png",
                                 "content_type": "image/png", "role": "bogus",
                                 "source": "captured_by_rep"},
                           headers=tokens["rep_perm_on"], timeout=30)
        requests.delete(f"{BASE}/api/appraisals/{aid}", headers=tokens["rep_perm_on"], timeout=30)
        assert r2.status_code == 400, f"expected 400, got {r2.status_code}: {r2.text[:200]}"
