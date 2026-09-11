"""Backend tests for Call Scorecards. Requires `python tests/seed_scorecard_demo.py` (graded demo calls for the Activation Tester)."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://user-routing-issue.preview.emergentagent.com").rstrip("/")
MANAGER = {"email": "qa-manager@invalid.imonsocial.test", "password": "Manager123!"}
REP = {"email": "activation-tester@invalid.imonsocial.test", "password": "NewPass123!"}
REP_ID = "6a978d68b8673c29063aa8b9"
DEMO_SIDS = ["CA_scdemo_good_001", "CA_scdemo_miss_002", "CA_scdemo_mid_003"]


def _login(creds):
    r = requests.post(f"{BASE_URL}/api/auth/login", json=creds, timeout=20)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json().get('token') or r.json().get('access_token')}"}


@pytest.fixture(scope="module")
def mgr():
    return _login(MANAGER)


@pytest.fixture(scope="module")
def rep():
    return _login(REP)


@pytest.fixture(scope="module")
def card(mgr):
    r = requests.post(f"{BASE_URL}/api/scorecards", json={"template_key": "service_bdc", "name": "PyTest Service Card"}, headers=mgr, timeout=20)
    assert r.status_code == 200, r.text
    c = r.json()
    yield c
    requests.delete(f"{BASE_URL}/api/scorecards/{c['id']}", headers=mgr, timeout=20)


class TestLibrary:
    def test_unauth(self):
        assert requests.get(f"{BASE_URL}/api/scorecards", timeout=20).status_code == 401

    def test_manager_list(self, mgr):
        d = requests.get(f"{BASE_URL}/api/scorecards", headers=mgr, timeout=20).json()
        assert d["can_manage"] is True
        assert {t["key"] for t in d["templates"]} == {"internet_sales", "service_bdc", "phone_up"}
        assert "reps" in d and "inboxes" in d and "departments" in d
        assert any(c["name"] == "Internet Sales Call" for c in d["scorecards"])

    def test_rep_list_no_manage(self, rep):
        d = requests.get(f"{BASE_URL}/api/scorecards", headers=rep, timeout=20).json()
        assert d["can_manage"] is False and "reps" not in d

    def test_rep_cannot_create(self, rep):
        assert requests.post(f"{BASE_URL}/api/scorecards", json={"template_key": "phone_up"}, headers=rep, timeout=20).status_code == 403

    def test_template_card(self, card):
        assert card["name"] == "PyTest Service Card" and card["department"] == "Service BDC"
        assert len(card["criteria"]) == 8 and card["critical_count"] == 1
        assert all({"id", "text", "hint", "weight", "critical"} <= set(c) for c in card["criteria"])

    def test_bad_template(self, mgr):
        assert requests.post(f"{BASE_URL}/api/scorecards", json={"template_key": "nope"}, headers=mgr, timeout=20).status_code == 400

    def test_blank_needs_name(self, mgr):
        assert requests.post(f"{BASE_URL}/api/scorecards", json={"criteria": []}, headers=mgr, timeout=20).status_code == 400

    def test_update_and_validation(self, mgr, card):
        cid = card["id"]
        r = requests.put(f"{BASE_URL}/api/scorecards/{cid}", json={"criteria": []}, headers=mgr, timeout=20)
        assert r.status_code == 400
        body = {"name": "PyTest Service Card v2", "criteria": [{"text": "Asked for the appointment", "weight": 9, "critical": True}, {"text": "  "}],
                "applies_to": {"user_ids": [REP_ID], "inbox_ids": [], "source_ids": []}, "alert_below_pct": 70, "notify_rep": False}
        r = requests.put(f"{BASE_URL}/api/scorecards/{cid}", json=body, headers=mgr, timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["name"] == "PyTest Service Card v2"
        assert len(d["criteria"]) == 1 and d["criteria"][0]["weight"] == 5 and d["criteria"][0]["critical"] is True
        assert d["applies_to"]["user_ids"] == [REP_ID] and d["alert_below_pct"] == 70 and d["notify_rep"] is False
        r = requests.put(f"{BASE_URL}/api/scorecards/{cid}", json={"clear_alert_below": True, "applies_to": {"user_ids": [], "inbox_ids": [], "source_ids": []}}, headers=mgr, timeout=20)
        assert r.json()["alert_below_pct"] is None and r.json()["applies_to"]["user_ids"] == []

    def test_rep_cannot_update(self, rep, card):
        assert requests.put(f"{BASE_URL}/api/scorecards/{card['id']}", json={"name": "x"}, headers=rep, timeout=20).status_code == 403

    def test_duplicate_and_delete(self, mgr, card):
        r = requests.post(f"{BASE_URL}/api/scorecards/{card['id']}/duplicate", headers=mgr, timeout=20)
        assert r.status_code == 200 and r.json()["name"].endswith("(copy)") and r.json()["is_default"] is False
        dup = r.json()["id"]
        assert requests.delete(f"{BASE_URL}/api/scorecards/{dup}", headers=mgr, timeout=20).json()["deleted"] is True
        names = [c["id"] for c in requests.get(f"{BASE_URL}/api/scorecards", headers=mgr, timeout=20).json()["scorecards"]]
        assert dup not in names

    def test_single_default(self, mgr, card):
        r = requests.put(f"{BASE_URL}/api/scorecards/{card['id']}", json={"is_default": True}, headers=mgr, timeout=20)
        assert r.json()["is_default"] is True
        cards = requests.get(f"{BASE_URL}/api/scorecards", headers=mgr, timeout=20).json()["scorecards"]
        assert sum(1 for c in cards if c["is_default"]) == 1
        internet = next(c for c in cards if c["name"] == "Internet Sales Call")
        r = requests.put(f"{BASE_URL}/api/scorecards/{internet['id']}", json={"is_default": True}, headers=mgr, timeout=20)
        assert r.json()["is_default"] is True

    def test_unknown_card(self, mgr):
        assert requests.get(f"{BASE_URL}/api/scorecards/000000000000000000000000", headers=mgr, timeout=20).status_code == 404
        assert requests.get(f"{BASE_URL}/api/scorecards/not-an-id", headers=mgr, timeout=20).status_code == 404


class TestEvaluations:
    def test_rep_mine(self, rep):
        d = requests.get(f"{BASE_URL}/api/scorecards/evaluations/mine?days=30", headers=rep, timeout=20).json()
        assert d["user"]["id"] == REP_ID
        assert d["stats"]["count"] >= 3 and d["stats"]["avg_score"] is not None
        assert isinstance(d["stats"]["criteria"], list) and d["stats"]["criteria"][0]["pass_rate"] is not None
        sids = {e["call_sid"] for e in d["evaluations"]}
        assert set(DEMO_SIDS) <= sids
        ev = next(e for e in d["evaluations"] if e["call_sid"] == "CA_scdemo_miss_002")
        assert ev["score_pct"] < 50 and len(ev["critical_misses"]) == 2 and ev["summary"] and ev["coaching"]
        assert "—" not in ev["summary"] and all("—" not in t for t in ev["coaching"])

    def test_eval_for_call(self, rep, mgr):
        r = requests.get(f"{BASE_URL}/api/scorecards/evaluations/call/CA_scdemo_good_001", headers=rep, timeout=20)
        assert r.status_code == 200 and r.json()["evaluation"]["score_pct"] >= 80 and r.json()["can_manage"] is False
        r = requests.get(f"{BASE_URL}/api/scorecards/evaluations/call/CA_scdemo_good_001", headers=mgr, timeout=20)
        assert r.json()["can_manage"] is True
        assert requests.get(f"{BASE_URL}/api/scorecards/evaluations/call/CA_does_not_exist", headers=mgr, timeout=20).status_code == 404

    def test_rep_cannot_see_others(self, rep, mgr):
        d = requests.get(f"{BASE_URL}/api/scorecards/evaluations/mine", headers=mgr, timeout=20).json()
        assert d["user"]["name"] == "QA Manager" and d["stats"]["count"] == 0

    def test_override_recomputes(self, mgr, rep):
        ev = requests.get(f"{BASE_URL}/api/scorecards/evaluations/call/CA_scdemo_miss_002", headers=mgr, timeout=20).json()["evaluation"]
        target = next(r for r in ev["results"] if r["critical"] and r["passed"] is False)
        before = ev["score_pct"]
        r = requests.put(f"{BASE_URL}/api/scorecards/evaluations/{ev['id']}/override", json={"criterion_id": target["criterion_id"], "passed": True}, headers=mgr, timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        got = next(x for x in d["results"] if x["criterion_id"] == target["criterion_id"])
        assert got["passed"] is True and got["override"]["by_name"] and d["graded_by"] == "manager"
        assert d["score_pct"] > before and target["criterion_id"] not in d["critical_misses"]
        # revert to the AI answer clears the override marker
        r = requests.put(f"{BASE_URL}/api/scorecards/evaluations/{ev['id']}/override", json={"criterion_id": target["criterion_id"], "passed": False}, headers=mgr, timeout=20)
        d = r.json()
        got = next(x for x in d["results"] if x["criterion_id"] == target["criterion_id"])
        assert got["override"] is None and d["score_pct"] == before and d["graded_by"] == "ai"
        assert requests.put(f"{BASE_URL}/api/scorecards/evaluations/{ev['id']}/override", json={"criterion_id": "bogus", "passed": True}, headers=mgr, timeout=20).status_code == 400
        assert requests.put(f"{BASE_URL}/api/scorecards/evaluations/{ev['id']}/override", json={"criterion_id": target["criterion_id"], "passed": True}, headers=rep, timeout=20).status_code == 403

    def test_rescore_requires_manager(self, rep):
        assert requests.post(f"{BASE_URL}/api/scorecards/evaluations/rescore/CA_scdemo_good_001", json={}, headers=rep, timeout=20).status_code == 403

    def test_rescore_unknown_call(self, mgr):
        assert requests.post(f"{BASE_URL}/api/scorecards/evaluations/rescore/CA_nope", json={}, headers=mgr, timeout=20).status_code == 404


class TestManagerViews:
    def test_team(self, mgr):
        d = requests.get(f"{BASE_URL}/api/scorecards/team?days=30", headers=mgr, timeout=20).json()
        assert d["calls"] >= 3 and d["avg_score"] is not None
        rep_row = next(r for r in d["reps"] if r["user_id"] == REP_ID)
        assert rep_row["count"] >= 3 and rep_row["critical_misses"] >= 2 and rep_row["weakest"]
        assert d["heatmap"] == {} and d["criteria"] == []
        assert len(d["alerts"]) >= 2 and all(a["critical_misses"] for a in d["alerts"])

    def test_team_heatmap_for_card(self, mgr):
        cards = requests.get(f"{BASE_URL}/api/scorecards", headers=mgr, timeout=20).json()["scorecards"]
        internet = next(c for c in cards if c["name"] == "Internet Sales Call")
        d = requests.get(f"{BASE_URL}/api/scorecards/team?days=30&scorecard_id={internet['id']}", headers=mgr, timeout=20).json()
        assert len(d["criteria"]) == 9 and REP_ID in d["heatmap"]
        assert set(d["heatmap"][REP_ID]) == {c["id"] for c in d["criteria"]}

    def test_team_forbidden_for_rep(self, rep):
        assert requests.get(f"{BASE_URL}/api/scorecards/team", headers=rep, timeout=20).status_code == 403

    def test_rep_drilldown(self, mgr, rep):
        d = requests.get(f"{BASE_URL}/api/scorecards/rep/{REP_ID}?days=30", headers=mgr, timeout=20).json()
        assert d["user"]["id"] == REP_ID and d["stats"]["count"] >= 3 and d["can_manage"] is True
        assert requests.get(f"{BASE_URL}/api/scorecards/rep/{REP_ID}", headers=rep, timeout=20).status_code == 200  # self
        mgr_id = requests.get(f"{BASE_URL}/api/scorecards/evaluations/mine", headers=mgr, timeout=20).json()["user"]["id"]
        assert requests.get(f"{BASE_URL}/api/scorecards/rep/{mgr_id}", headers=rep, timeout=20).status_code == 403

    def test_mute(self, mgr):
        r = requests.put(f"{BASE_URL}/api/scorecards/alerts/mute", json={"rep_id": REP_ID, "muted": True}, headers=mgr, timeout=20)
        assert r.status_code == 200
        assert REP_ID in requests.get(f"{BASE_URL}/api/scorecards/team", headers=mgr, timeout=20).json()["muted_reps"]
        assert requests.get(f"{BASE_URL}/api/scorecards/rep/{REP_ID}", headers=mgr, timeout=20).json()["muted"] is True
        requests.put(f"{BASE_URL}/api/scorecards/alerts/mute", json={"rep_id": REP_ID, "muted": False}, headers=mgr, timeout=20)
        assert REP_ID not in requests.get(f"{BASE_URL}/api/scorecards/team", headers=mgr, timeout=20).json()["muted_reps"]


class TestCallsIntegration:
    def test_contact_calls_carry_evaluation(self, rep):
        d = requests.get(f"{BASE_URL}/api/scorecards/evaluations/mine", headers=rep, timeout=20).json()
        ev = next(e for e in d["evaluations"] if e["call_sid"] == "CA_scdemo_good_001")
        r = requests.get(f"{BASE_URL}/api/calls/{REP_ID}/contact/{ev['contact_id']}", headers=rep, timeout=20)
        assert r.status_code == 200
        rec = next(x for x in r.json()["recordings"] if x["call_sid"] == "CA_scdemo_good_001")
        assert rec["evaluation"]["id"] == ev["id"] and rec["evaluation"]["score_pct"] == ev["score_pct"]
