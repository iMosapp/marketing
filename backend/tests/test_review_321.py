"""Backend sanity for parts/rental/collision + scorecards ack + coaching digest."""
import os
import requests
import pytest
from pathlib import Path

def _load_env():
    p = Path("/app/frontend/.env")
    for line in p.read_text().splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            return line.split("=", 1)[1].strip().rstrip("/")
    raise RuntimeError("no url")

BASE = _load_env()


def _login(email, password):
    r = requests.post(f"{BASE}/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def forest_token():
    return _login("forest@imosapp.com", "Admin123!")


@pytest.fixture(scope="module")
def mgr_token():
    return _login("qa-manager@invalid.imonsocial.test", "Manager123!")


@pytest.fixture(scope="module")
def rep_token():
    return _login("activation-tester@invalid.imonsocial.test", "NewPass123!")


def _h(t):
    return {"Authorization": f"Bearer {t}"}


# 1. Industries: automotive pack has 5 departments incl collision
def test_industries_automotive_five_depts(forest_token):
    r = requests.get(f"{BASE}/api/shop-clients/industries", headers=_h(forest_token))
    assert r.status_code == 200, r.text
    data = r.json()
    # data can be list or dict
    autos = None
    inds = data.get("industries") if isinstance(data, dict) else data
    for it in inds:
        if it.get("key") == "automotive":
            autos = it
            break
    assert autos, f"automotive not found"
    depts = autos.get("departments") or []
    keys = [d.get("key") for d in depts]
    labels = {d.get("key"): d.get("label") for d in depts}
    print("automotive depts:", keys, labels)
    assert "collision" in keys
    assert labels.get("collision") == "Body Shop"
    for d in ("parts", "rental", "collision"):
        dept = next(x for x in depts if x.get("key") == d)
        n = dept.get("challenges")
        assert isinstance(n, int) and n >= 3, f"{d} challenges={n}"


# 2. Scorecards templates include collision_phone / Body Shop
def test_scorecards_body_shop_template(mgr_token):
    r = requests.get(f"{BASE}/api/scorecards", headers=_h(mgr_token))
    assert r.status_code == 200, r.text
    j = r.json()
    templates = j.get("templates") or j.get("scorecard_templates") or []
    depts = j.get("departments") or []
    print("templates count:", len(templates), "depts:", depts)
    tkeys = [(t.get("key") or t.get("id")) for t in templates]
    tlabels = [t.get("label") or t.get("name") for t in templates]
    assert "collision_phone" in tkeys, tkeys
    assert any("Body Shop Call" == (t.get("label") or t.get("name")) for t in templates), tlabels
    assert "Body Shop" in depts, depts


# 3. Ack endpoint returns 403 for managers
def test_ack_manager_forbidden(mgr_token):
    # find an evaluation id first
    r = requests.get(f"{BASE}/api/scorecards/team", headers=_h(mgr_token))
    assert r.status_code == 200, r.text
    j = r.json()
    eval_id = None
    # dig for any evaluation id
    def find_eval(obj):
        nonlocal eval_id
        if eval_id:
            return
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k in ("evaluation_id", "id") and isinstance(v, str) and len(v) == 24 and "eval" in str(obj).lower():
                    pass
                find_eval(v)
        elif isinstance(obj, list):
            for x in obj:
                find_eval(x)
    # fallback: hit /api/scorecards/evaluations
    r2 = requests.get(f"{BASE}/api/scorecards/evaluations", headers=_h(mgr_token))
    if r2.status_code == 200:
        arr = r2.json()
        if isinstance(arr, dict):
            arr = arr.get("evaluations") or arr.get("items") or []
        if arr:
            eval_id = arr[0].get("id") or arr[0].get("_id")
    if not eval_id:
        pytest.skip("No evaluation id discoverable to ack test")
    r3 = requests.post(f"{BASE}/api/scorecards/evaluations/{eval_id}/ack", headers=_h(mgr_token))
    print("mgr ack status:", r3.status_code, r3.text[:200])
    assert r3.status_code == 403


# 4. Digest GET as super admin -> 200 with store null
def test_digest_super_admin_no_store(forest_token):
    r = requests.get(f"{BASE}/api/scorecards/digest", headers=_h(forest_token))
    assert r.status_code == 200, r.text
    j = r.json()
    print("forest digest:", j)
    assert j.get("store") in (None, "", {})


# 5. Digest send as super admin (no store) -> 400 mentioning store
def test_digest_send_super_admin_400(forest_token):
    r = requests.post(f"{BASE}/api/scorecards/digest/send", headers=_h(forest_token))
    print("forest send:", r.status_code, r.text[:300])
    assert r.status_code == 400
    assert "store" in r.text.lower()


# 6. Rep cannot GET digest
def test_rep_digest_forbidden(rep_token):
    r = requests.get(f"{BASE}/api/scorecards/digest", headers=_h(rep_token))
    print("rep digest:", r.status_code, r.text[:200])
    assert r.status_code == 403


# 7. Public shop report PDF
def test_public_pdf():
    r = requests.get(f"{BASE}/api/public/shop-report/51c51185fdbf45e3b15efbadf3e3b203.pdf")
    print("pdf status:", r.status_code, r.headers.get("content-type"))
    assert r.status_code == 200
    assert "pdf" in r.headers.get("content-type", "").lower()
    # PDF stream is FlateDecode-compressed; can't grep raw. Just ensure it's a valid PDF.
    assert r.content.startswith(b"%PDF"), r.content[:100]
