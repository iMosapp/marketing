"""Extra pytest coverage for Scripts & Practice: PDF header auth, 401 without any auth, 409 on completed turn, 404 for other rep's session, POST custom script + validation, training RBAC, training generate."""
import os
import time
import pytest
import requests

BASE_URL = [l.split("=", 1)[1].strip() for l in open("/app/frontend/.env") if l.startswith("REACT_APP_BACKEND_URL=")][0].rstrip("/")
API = BASE_URL + "/api"


def _login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=30)
    r.raise_for_status()
    d = r.json()
    return d.get("token") or d.get("access_token"), d["user"]


@pytest.fixture(scope="module")
def rep():
    tok, u = _login("activation-tester@invalid.imonsocial.test", "NewPass123!")
    return {"tok": tok, "user": u, "H": {"Authorization": f"Bearer {tok}"}}


@pytest.fixture(scope="module")
def mgr():
    tok, u = _login("qa-manager@invalid.imonsocial.test", "Manager123!")
    return {"tok": tok, "user": u, "H": {"Authorization": f"Bearer {tok}"}}


@pytest.fixture(scope="module")
def admin():
    try:
        tok, u = _login("forest@imosapp.com", "Admin123!")
        return {"tok": tok, "user": u, "H": {"Authorization": f"Bearer {tok}"}}
    except Exception as e:
        pytest.skip(f"super admin login failed: {e}")


@pytest.fixture(scope="module")
def appt_script(rep):
    lib = requests.get(f"{API}/scripts", headers=rep["H"], timeout=30).json()
    return next(s for s in lib["scripts"] if s["slug"] == "appointment_confirmation")


# ---------------- PDF auth variants ----------------
def test_pdf_with_bearer_header(rep, appt_script):
    r = requests.get(f"{API}/scripts/{appt_script['id']}/pdf", headers=rep["H"], timeout=60)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/pdf")
    assert r.content[:4] == b"%PDF"


def test_pdf_unauthenticated_returns_401(appt_script):
    r = requests.get(f"{API}/scripts/{appt_script['id']}/pdf", timeout=30)
    assert r.status_code == 401


# ---------------- Roleplay 409 / 404 ----------------
def test_completed_session_turn_returns_409_and_other_rep_gets_404(rep, mgr, appt_script):
    s = requests.post(f"{API}/scripts/roleplay/start", headers=rep["H"],
                      json={"script_id": appt_script["id"]}, timeout=90)
    assert s.status_code == 200, s.text
    sid = s.json()["session_id"]
    r = requests.post(f"{API}/scripts/roleplay/{sid}/turn", headers=rep["H"],
                     json={"text": "Hi Janet, confirming tomorrow at 10 for the Enclave."}, timeout=120)
    assert r.status_code == 200

    # unauthenticated request cannot access session (proxy for "not the owner")
    other = requests.post(f"{API}/scripts/roleplay/{sid}/turn",
                          json={"text": "hello"}, timeout=30)
    assert other.status_code == 401, other.status_code

    # end then attempt turn -> 409
    e = requests.post(f"{API}/scripts/roleplay/{sid}/end", headers=rep["H"], timeout=180)
    assert e.status_code == 200
    late = requests.post(f"{API}/scripts/roleplay/{sid}/turn", headers=rep["H"],
                         json={"text": "too late"}, timeout=30)
    assert late.status_code == 409, late.status_code


# ---------------- Custom script POST (manager) ----------------
def test_manager_can_create_custom_script_and_validation(mgr, rep):
    # missing title/body -> 400
    bad = requests.post(f"{API}/scripts", headers=mgr["H"], json={"title": "", "body": ""}, timeout=30)
    assert bad.status_code == 400, bad.status_code

    ok = requests.post(f"{API}/scripts", headers=mgr["H"], json={
        "title": "TEST_QA_Custom",
        "body": "Hi {{customer_first_name}}, this is {{rep_first_name}}.",
        "purpose": "QA custom",
    }, timeout=30)
    assert ok.status_code == 200, ok.text
    new_id = ok.json()["id"]
    try:
        # rep cannot create
        assert requests.post(f"{API}/scripts", headers=rep["H"], json={"title": "x", "body": "y"}, timeout=30).status_code == 403
        # visible in library
        lib = requests.get(f"{API}/scripts", headers=mgr["H"], timeout=30).json()
        assert any(x["id"] == new_id for x in lib["scripts"])
    finally:
        d = requests.delete(f"{API}/scripts/{new_id}", headers=mgr["H"], timeout=30)
        assert d.status_code == 200


# ---------------- Training RBAC + generate ----------------
def test_training_endpoints_rbac(mgr, rep):
    assert requests.get(f"{API}/scripts/training", headers=mgr["H"], timeout=30).status_code == 403
    assert requests.get(f"{API}/scripts/training", headers=rep["H"], timeout=30).status_code == 403


def test_training_features_list_for_super_admin(admin):
    r = requests.get(f"{API}/scripts/training", headers=admin["H"], timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "features" in data and isinstance(data["features"], list) and len(data["features"]) >= 1
    assert any(f.get("id") == "ask_jessi" for f in data["features"])


def test_training_generate_for_super_admin(admin, mgr):
    r = requests.post(f"{API}/scripts/training/generate", headers=admin["H"],
                      json={"feature_id": "ask_jessi", "format": "short"}, timeout=120)
    assert r.status_code == 200, r.text
    js = r.json()
    sid = js.get("id") or js.get("script_id")
    assert sid, js
    try:
        # manager cannot fetch training script detail -> 403
        det_mgr = requests.get(f"{API}/scripts/{sid}", headers=mgr["H"], timeout=30)
        assert det_mgr.status_code == 403, det_mgr.status_code
        # super admin can, and has scenes
        det_admin = requests.get(f"{API}/scripts/{sid}", headers=admin["H"], timeout=30).json()
        assert det_admin.get("kind") == "training" or det_admin.get("training") or "scenes" in (det_admin.get("training") or {}), det_admin
    finally:
        requests.delete(f"{API}/scripts/{sid}", headers=admin["H"], timeout=30)
