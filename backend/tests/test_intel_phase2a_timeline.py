"""
Phase 2A - Intelligent Timeline backend tests
Endpoints:
  GET /api/intel/contacts/{id}/timeline
  GET /api/intel/facts/{fact_id}/source
"""
import os
import pytest
import requests
from tests import qa_creds

def _load_backend_url():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if not v:
        # fallback to frontend/.env
        try:
            with open("/app/frontend/.env") as f:
                for ln in f:
                    if ln.startswith("REACT_APP_BACKEND_URL="):
                        v = ln.split("=", 1)[1].strip().strip('"')
                        break
        except Exception:
            pass
    assert v, "REACT_APP_BACKEND_URL not set"
    return v.rstrip("/")


BASE_URL = _load_backend_url()

SAM_ID = "6aca90147e9b715d761b6078"
SARAH_ID = "6aa413008f0d53e3f2261853"

REP_EMAIL = "activation-tester@invalid.imonsocial.test"
REP_PASS = qa_creds.password_for("activation-tester@invalid.imonsocial.test")
MGR_EMAIL = "qa-manager@invalid.imonsocial.test"
MGR_PASS = qa_creds.password_for("qa-manager@invalid.imonsocial.test")
OADM_EMAIL = "qa-orgadmin@invalid.imonsocial.test"
OADM_PASS = qa_creds.password_for("qa-orgadmin@invalid.imonsocial.test")


def _login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"login {email} -> {r.status_code}: {r.text[:300]}"
    j = r.json()
    tok = j.get("token") or j.get("access_token")
    assert tok, f"no token in login response: {j}"
    return tok


@pytest.fixture(scope="module")
def rep_token():
    return _login(REP_EMAIL, REP_PASS)


@pytest.fixture(scope="module")
def mgr_token():
    return _login(MGR_EMAIL, MGR_PASS)


@pytest.fixture(scope="module")
def oadm_token():
    return _login(OADM_EMAIL, OADM_PASS)


def _h(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


SCORE_KEYS = {"confidence", "confidence_score", "score"}


def _assert_no_scores(obj, path="root"):
    if isinstance(obj, dict):
        for k, v in obj.items():
            assert k not in SCORE_KEYS, f"raw score key '{k}' found at {path}"
            _assert_no_scores(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _assert_no_scores(v, f"{path}[{i}]")


# -------- Sam timeline --------
class TestSamTimeline:
    def test_timeline_shape(self, rep_token):
        r = requests.get(f"{BASE_URL}/api/intel/contacts/{SAM_ID}/timeline",
                         headers=_h(rep_token), timeout=20)
        assert r.status_code == 200, r.text[:400]
        tl = r.json()
        assert tl.get("enabled") is True
        assert tl.get("can_verify") is True

        rec = tl.get("recommended") or {}
        assert rec.get("topic") == "2025 Ford Explorer ST", f"recommended.topic={rec.get('topic')}"

        active = tl.get("active") or []
        assert active, "active is empty"
        assert active[0]["label"] == "2025 Ford Explorer ST"
        assert "via lead form" in (active[0].get("detail") or ""), f"detail={active[0].get('detail')}"
        assert tl.get("driving_fact_id") == active[0].get("fact_id")

        drives = (tl.get("current") or {}).get("drives") or []
        assert drives, "current.drives empty"
        assert drives[0]["label"] == "2025 Ford F-150 Lariat"
        assert drives[0].get("confirmed") is True

        markers = tl.get("markers") or []
        assert len(markers) >= 2, f"markers len={len(markers)}"
        for m in markers:
            assert m.get("event_type") == "intel_milestone"
            assert m.get("category") == "milestone"
            assert m.get("fact_id")
            assert m.get("timestamp")
        # newest first
        tss = [m["timestamp"] for m in markers]
        assert tss == sorted(tss, reverse=True), "markers not sorted newest first"

        # no raw score fields anywhere in the strip-exposed sections
        for section in ("recommended", "active", "current", "needs_look", "markers"):
            _assert_no_scores(tl.get(section), section)

        # stash for later tests
        pytest._sam_active_fact = active[0]["fact_id"]
        bought = [m for m in markers if (m.get("title") or "").startswith("Bought")]
        assert bought, "no 'Bought ...' marker"
        pytest._sam_bought_fact = bought[0]["fact_id"]

    def test_source_lead_form(self, rep_token):
        fid = pytest._sam_active_fact
        r = requests.get(f"{BASE_URL}/api/intel/facts/{fid}/source",
                         headers=_h(rep_token), timeout=20)
        assert r.status_code == 200, r.text[:400]
        s = r.json()
        assert s.get("kind") == "lead_form"
        assert "lead" in (s.get("title") or "").lower()
        assert (s.get("excerpt") or "").strip() == "and an Explorer for my wife"
        assert s.get("confirmed") is True

    def test_source_sale(self, rep_token):
        fid = pytest._sam_bought_fact
        r = requests.get(f"{BASE_URL}/api/intel/facts/{fid}/source",
                         headers=_h(rep_token), timeout=20)
        assert r.status_code == 200, r.text[:400]
        s = r.json()
        assert s.get("kind") == "sale"
        assert s.get("link") == f"/contact/{SAM_ID}?purchase=s6", f"link={s.get('link')}"


# -------- Permissions --------
class TestPermissions:
    def test_orgadmin_other_org_404_timeline(self, oadm_token):
        r = requests.get(f"{BASE_URL}/api/intel/contacts/{SAM_ID}/timeline",
                         headers=_h(oadm_token), timeout=20)
        assert r.status_code == 404, f"got {r.status_code}: {r.text[:200]}"

    def test_orgadmin_other_org_404_source(self, oadm_token):
        fid = getattr(pytest, "_sam_active_fact", None)
        if not fid:
            pytest.skip("need sam fact id")
        r = requests.get(f"{BASE_URL}/api/intel/facts/{fid}/source",
                         headers=_h(oadm_token), timeout=20)
        assert r.status_code == 404

    def test_manager_same_store_can_verify(self, mgr_token):
        r = requests.get(f"{BASE_URL}/api/intel/contacts/{SAM_ID}/timeline",
                         headers=_h(mgr_token), timeout=20)
        assert r.status_code == 200
        assert r.json().get("can_verify") is True


# -------- Sarah timeline --------
class TestSarahTimeline:
    def test_timeline(self, rep_token):
        r = requests.get(f"{BASE_URL}/api/intel/contacts/{SARAH_ID}/timeline",
                         headers=_h(rep_token), timeout=20)
        assert r.status_code == 200, r.text[:400]
        tl = r.json()
        assert tl.get("enabled") is True
        drives = (tl.get("current") or {}).get("drives") or []
        assert drives, "sarah current.drives empty"
        assert drives[0]["confirmed"] is True  # confirmed ownership sorts first (Sarah is shared QA data; the specific truck may change)
        assert drives[0].get("confirmed") is True
        unconfirmed_after = [d for d in drives[1:] if not d.get("confirmed")]
        assert len(unconfirmed_after) >= 1, f"expected unconfirmed drives after confirmed; got {drives}"

        needs = tl.get("needs_look") or []
        assert len(needs) >= 8, f"needs_look len={len(needs)}"
        allowed = {"unconfirmed", "stale", "disputed", "proposed"}
        for n in needs:
            assert n.get("reason") in allowed, f"reason={n.get('reason')}"

        # grab an unconfirmed drive fact for next test
        for d in drives:
            if not d.get("confirmed") and d.get("fact_id"):
                pytest._sarah_unconf_fact = d["fact_id"]
                break
        assert getattr(pytest, "_sarah_unconf_fact", None), "no unconfirmed drive with fact_id"

        for section in ("recommended", "active", "current", "needs_look", "markers"):
            _assert_no_scores(tl.get(section), section)

    def test_source_appraisal(self, rep_token):
        fid = pytest._sarah_unconf_fact
        r = requests.get(f"{BASE_URL}/api/intel/facts/{fid}/source",
                         headers=_h(rep_token), timeout=20)
        assert r.status_code == 200, r.text[:400]
        s = r.json()
        assert s.get("kind") == "appraisal", f"kind={s.get('kind')}"
        assert s.get("title") == "Appraisal vehicle record"
        assert s.get("confirmed") is False
        assert (s.get("link") or "").startswith("/vehicle/"), f"link={s.get('link')}"
