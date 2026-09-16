"""VA config + facts CRUD + industry pick tests.

Covers /api/va/config, PUT /api/va/industry, GET/POST/PUT/DELETE /api/va/facts.
"""
import os
import pytest
import requests

def _read_frontend_env():
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip().strip('"').rstrip("/")
    except Exception:
        pass
    return ""

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL") or _read_frontend_env()
assert BASE_URL, "REACT_APP_BACKEND_URL missing"

FOREST = ("forest@imosapp.com", "Admin123!")
QAMGR = ("qa-manager@invalid.imonsocial.test", "Manager123!")
TESTER = ("activation-tester@invalid.imonsocial.test", "NewPass123!")
QA_STORE_ID = "69a0b7095fddcede09591668"


def _login(email, pw):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": pw}, timeout=15)
    r.raise_for_status()
    tok = r.json().get("access_token") or r.json().get("token")
    assert tok, r.text
    return tok


def _hdr(tok):
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def forest_tok():
    return _login(*FOREST)


@pytest.fixture(scope="module")
def qamgr_tok():
    return _login(*QAMGR)


@pytest.fixture(scope="module")
def tester_tok():
    return _login(*TESTER)


# ------------------------------------------------------ /api/va/config
class TestConfig:
    def test_no_token_401(self):
        r = requests.get(f"{BASE_URL}/api/va/config", timeout=15)
        assert r.status_code in (401, 403)

    def test_forest_config(self, forest_tok):
        r = requests.get(f"{BASE_URL}/api/va/config", headers=_hdr(forest_tok), timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["available"] is True
        assert d["industry"]["source"] in ("profile", "default", "store")
        assert set(d["industry"].keys()) >= {"key", "label", "source"}
        assert d["can_pick_industry"] is True  # forest has no store
        assert isinstance(d["industries"], list) and len(d["industries"]) == 8
        assert isinstance(d["scenarios"], list) and len(d["scenarios"]) == 4
        assert "hold" in d and "safe" in d and "tone" in d
        assert set(d["facts"].keys()) >= {"store", "mine", "store_name", "can_edit_store"}

    def test_qa_manager_lab_gate(self, forest_tok, qamgr_tok):
        # industry_va was released: live by default, so a manager gets the new VA too
        feats = requests.get(f"{BASE_URL}/api/lab/features", headers=_hdr(forest_tok), timeout=15).json()
        feats_list = feats["features"] if isinstance(feats, dict) else feats
        iv = next((f for f in feats_list if f["key"] == "industry_va"), None)
        assert iv is not None
        assert iv["status"] == "live", f"feature is released, got {iv['status']}"

        r = requests.get(f"{BASE_URL}/api/va/config", headers=_hdr(qamgr_tok), timeout=15)
        assert r.status_code == 200
        assert r.json()["available"] is True


# ------------------------------------------------------ PUT /api/va/industry
class TestIndustryPick:
    def test_forest_pick_and_restore(self, forest_tok):
        # unknown
        r = requests.put(f"{BASE_URL}/api/va/industry", headers=_hdr(forest_tok), json={"industry": "bogus"}, timeout=15)
        assert r.status_code == 400

        # pick real_estate
        r = requests.put(f"{BASE_URL}/api/va/industry", headers=_hdr(forest_tok), json={"industry": "real_estate"}, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["industry"]["key"] == "real_estate"
        assert d["industry"]["source"] == "profile"
        labels = [s["label"] for s in d["scenarios"]]
        assert labels == ["New Buyer", "Seller", "Happy Client", "Showing"]

        # restore
        r = requests.put(f"{BASE_URL}/api/va/industry", headers=_hdr(forest_tok), json={"industry": "automotive"}, timeout=15)
        assert r.status_code == 200
        assert r.json()["industry"]["key"] == "automotive"

    def test_store_override_wins(self, forest_tok, qamgr_tok):
        # set QA store industry to real_estate
        r = requests.put(f"{BASE_URL}/api/admin/stores/{QA_STORE_ID}", headers=_hdr(forest_tok),
                         json={"industry": "real_estate"}, timeout=15)
        assert r.status_code in (200, 204), r.text
        try:
            cfg = requests.get(f"{BASE_URL}/api/va/config", headers=_hdr(qamgr_tok), timeout=15).json()
            # Config gate says unavailable in lab, but industry.source should still reflect store
            assert cfg["industry"]["source"] == "store"
            # qa-manager attempts to override -> 409
            r = requests.put(f"{BASE_URL}/api/va/industry", headers=_hdr(qamgr_tok), json={"industry": "automotive"}, timeout=15)
            assert r.status_code == 409, r.text
        finally:
            # RESET
            r = requests.put(f"{BASE_URL}/api/admin/stores/{QA_STORE_ID}", headers=_hdr(forest_tok),
                             json={"industry": ""}, timeout=15)
            assert r.status_code in (200, 204)


# ------------------------------------------------------ /api/va/facts CRUD
class TestFacts:
    def test_get_shape(self, forest_tok):
        r = requests.get(f"{BASE_URL}/api/va/facts", headers=_hdr(forest_tok), timeout=15)
        assert r.status_code == 200
        d = r.json()
        for k in ("store", "mine", "store_id", "store_name", "can_edit_store", "max"):
            assert k in d
        assert d["max"] == 60

    def test_add_edit_delete_mine(self, forest_tok):
        r = requests.post(f"{BASE_URL}/api/va/facts", headers=_hdr(forest_tok),
                          json={"text": "QA test mine fact", "scope": "mine"}, timeout=15)
        assert r.status_code == 200
        mine = r.json()["mine"]
        fid = next((f["id"] for f in mine if f["text"] == "QA test mine fact"), None)
        assert fid, mine

        r = requests.put(f"{BASE_URL}/api/va/facts/{fid}", headers=_hdr(forest_tok),
                         json={"text": "QA test mine fact edited", "scope": "mine"}, timeout=15)
        assert r.status_code == 200
        r = requests.put(f"{BASE_URL}/api/va/facts/notreal", headers=_hdr(forest_tok),
                         json={"text": "nope123", "scope": "mine"}, timeout=15)
        assert r.status_code == 404

        r = requests.delete(f"{BASE_URL}/api/va/facts/{fid}?scope=mine", headers=_hdr(forest_tok), timeout=15)
        assert r.status_code == 200
        r = requests.delete(f"{BASE_URL}/api/va/facts/notreal?scope=mine", headers=_hdr(forest_tok), timeout=15)
        assert r.status_code == 404

    def test_short_text_400(self, forest_tok):
        r = requests.post(f"{BASE_URL}/api/va/facts", headers=_hdr(forest_tok), json={"text": "hi", "scope": "mine"}, timeout=15)
        assert r.status_code == 400

    def test_forest_no_store_store_scope_400(self, forest_tok):
        r = requests.post(f"{BASE_URL}/api/va/facts", headers=_hdr(forest_tok),
                          json={"text": "QA store fact from forest", "scope": "store"}, timeout=15)
        assert r.status_code == 400
        assert "not on a store" in r.json().get("detail", "").lower()

    def test_tester_403_on_store(self, tester_tok):
        r = requests.post(f"{BASE_URL}/api/va/facts", headers=_hdr(tester_tok),
                          json={"text": "QA store fact from tester", "scope": "store"}, timeout=15)
        assert r.status_code == 403
        assert "manager" in r.json().get("detail", "").lower()

    def test_manager_can_add_store_fact(self, qamgr_tok):
        r = requests.post(f"{BASE_URL}/api/va/facts", headers=_hdr(qamgr_tok),
                          json={"text": "QA temp store fact from manager", "scope": "store"}, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        fid = next((f["id"] for f in d["store"] if f["text"] == "QA temp store fact from manager"), None)
        assert fid, d["store"]
        added = next(f for f in d["store"] if f["id"] == fid)
        assert added.get("added_by_name") == "QA Manager"
        # cleanup
        r = requests.delete(f"{BASE_URL}/api/va/facts/{fid}?scope=store", headers=_hdr(qamgr_tok), timeout=15)
        assert r.status_code == 200
