"""Public-API tests for /api/appraisals/providers/matrix* in the preview environment.
Keys are not installed in preview; starts must be refused."""
import os
import pytest
import requests
from tests import qa_creds

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://user-routing-issue.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "forest@imosapp.com"
ADMIN_PASS = qa_creds.password_for("forest@imosapp.com")
MGR_EMAIL = "qa-manager@invalid.imonsocial.test"
MGR_PASS = qa_creds.password_for("qa-manager@invalid.imonsocial.test")

SEED_RUN_ID = "6ac8063ea44ff526bd180ddd"


def _login(email: str, password: str) -> str:
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"login {email}: {r.status_code} {r.text[:200]}"
    data = r.json()
    tok = data.get("token") or data.get("access_token") or (data.get("user") or {}).get("token")
    assert tok, f"no token in login payload: {list(data.keys())}"
    return tok


@pytest.fixture(scope="module")
def admin_headers():
    return {"Authorization": f"Bearer {_login(ADMIN_EMAIL, ADMIN_PASS)}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def manager_headers():
    return {"Authorization": f"Bearer {_login(MGR_EMAIL, MGR_PASS)}", "Content-Type": "application/json"}


# ---- plan endpoint ----
def test_plan_ok_for_admin_no_keys(admin_headers):
    body = {"vehicles": [{"vin": "2T3DWRFV3LW077677", "mileage": "41200"},
                         {"year": "2022", "make": "Ford", "model": "F-150", "mileage": "28000"}],
            "zip": "84070"}
    r = requests.post(f"{API}/appraisals/providers/matrix/plan", json=body, headers=admin_headers, timeout=20)
    assert r.status_code == 200, r.text[:300]
    data = r.json()
    assert data["plan"]["calls_per_vehicle"] == 0
    assert data["plan"]["total_calls"] == 0
    vs = data["vehicles"]
    assert len(vs) == 2
    assert vs[0]["vin"] == "2T3DWRFV3LW077677"
    assert vs[0]["mileage"] == 41200
    assert vs[1]["year"] == 2022 and vs[1]["mileage"] == 28000


def test_plan_bad_vin_400(admin_headers):
    r = requests.post(f"{API}/appraisals/providers/matrix/plan", json={"vehicles": [{"vin": "BAD"}], "zip": "84070"},
                      headers=admin_headers, timeout=20)
    assert r.status_code == 400


# ---- start endpoint ----
def test_start_refused_no_keys(admin_headers):
    body = {"vehicles": [{"vin": "2T3DWRFV3LW077677", "mileage": "41200"}], "zip": "84070"}
    r = requests.post(f"{API}/appraisals/providers/matrix", json=body, headers=admin_headers, timeout=20)
    assert r.status_code == 400
    assert "No live provider key" in r.json().get("detail", "")


def test_start_bad_zip_400(admin_headers):
    body = {"vehicles": [{"vin": "2T3DWRFV3LW077677", "mileage": "41200"}], "zip": "840"}
    r = requests.post(f"{API}/appraisals/providers/matrix", json=body, headers=admin_headers, timeout=20)
    assert r.status_code == 400


# ---- list endpoint ----
def test_list_includes_seed(admin_headers):
    r = requests.get(f"{API}/appraisals/providers/matrix?limit=5", headers=admin_headers, timeout=20)
    assert r.status_code == 200
    runs = r.json().get("runs", [])
    assert isinstance(runs, list) and len(runs) >= 1
    seed = next((x for x in runs if x["id"] == SEED_RUN_ID), None)
    assert seed is not None, f"seeded run {SEED_RUN_ID} not in list"
    assert seed["status"] == "done"
    assert seed["plan"]["vehicles"] == 4
    assert seed["summary"]["both_answered"] == 3
    assert seed["rows"] == []


# ---- detail endpoint ----
def test_detail_full(admin_headers):
    r = requests.get(f"{API}/appraisals/providers/matrix/{SEED_RUN_ID}", headers=admin_headers, timeout=20)
    assert r.status_code == 200
    d = r.json()
    assert len(d["rows"]) == 3
    assert len(d["errors"]) == 1
    assert d["summary"]["median_abs_gap"] == 2100
    for row in d["rows"]:
        assert "mc" in row and "va" in row and "diff_dollars" in row


def test_detail_not_found(admin_headers):
    r = requests.get(f"{API}/appraisals/providers/matrix/000000000000000000000000", headers=admin_headers, timeout=20)
    assert r.status_code == 404


# ---- RBAC ----
def test_manager_forbidden_plan(manager_headers):
    r = requests.post(f"{API}/appraisals/providers/matrix/plan", json={"vehicles": [{"vin": "2T3DWRFV3LW077677"}], "zip": "84070"},
                      headers=manager_headers, timeout=20)
    assert r.status_code == 403


def test_manager_forbidden_start(manager_headers):
    r = requests.post(f"{API}/appraisals/providers/matrix", json={"vehicles": [{"vin": "2T3DWRFV3LW077677"}], "zip": "84070"},
                      headers=manager_headers, timeout=20)
    assert r.status_code == 403


def test_manager_forbidden_list(manager_headers):
    r = requests.get(f"{API}/appraisals/providers/matrix?limit=5", headers=manager_headers, timeout=20)
    assert r.status_code == 403


def test_manager_forbidden_detail(manager_headers):
    r = requests.get(f"{API}/appraisals/providers/matrix/{SEED_RUN_ID}", headers=manager_headers, timeout=20)
    assert r.status_code == 403


# ---- No token ----
def test_no_token_401():
    for path, method in [("/appraisals/providers/matrix/plan", "post"),
                         ("/appraisals/providers/matrix", "post"),
                         ("/appraisals/providers/matrix?limit=5", "get"),
                         (f"/appraisals/providers/matrix/{SEED_RUN_ID}", "get")]:
        fn = getattr(requests, method)
        kwargs = {"timeout": 20}
        if method == "post":
            kwargs["json"] = {"vehicles": [{"vin": "2T3DWRFV3LW077677"}], "zip": "84070"}
        r = fn(f"{API}{path}", **kwargs)
        assert r.status_code == 401, f"{method.upper()} {path} -> {r.status_code}"
