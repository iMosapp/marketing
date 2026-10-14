"""Backend tests for the new Agent Hub feature (agents router + widget/lead-source/inbox deploy pickers)."""
import os
import time

import pytest
import requests
from tests import qa_creds

def _load_env():
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip()
    except Exception:
        pass
    return os.environ.get("REACT_APP_BACKEND_URL", "")


BASE_URL = _load_env().rstrip("/")
API = f"{BASE_URL}/api"

SUPER = {"email": "forest@imosapp.com", "password": qa_creds.password_for("forest@imosapp.com")}
MANAGER = {"email": "qa-manager@invalid.imonsocial.test", "password": qa_creds.password_for("qa-manager@invalid.imonsocial.test")}
USER = {"email": "activation-tester@invalid.imonsocial.test", "password": qa_creds.password_for("activation-tester@invalid.imonsocial.test")}

WIDGET_ID = "6ab72996c248f5420bf0a14a"
MANAGER_STORE_ID = "69a0b7095fddcede09591668"


def _login(creds):
    r = requests.post(f"{API}/auth/login", json=creds, timeout=30)
    assert r.status_code == 200, r.text
    j = r.json()
    tok = j.get("token") or j.get("access_token")
    assert tok, j
    return tok


@pytest.fixture(scope="module")
def super_tok():
    return _login(SUPER)


@pytest.fixture(scope="module")
def mgr_tok():
    return _login(MANAGER)


@pytest.fixture(scope="module")
def user_tok():
    return _login(USER)


def H(t):
    return {"Authorization": f"Bearer {t}"}


# ---------------------------------------------------------------- cleanup state
created_ids = []


@pytest.fixture(scope="module", autouse=True)
def _cleanup(super_tok):
    yield
    # best-effort cleanup
    for aid in created_ids:
        try:
            requests.delete(f"{API}/agents/{aid}", headers=H(super_tok), timeout=15)
        except Exception:
            pass
    # ensure widget persona is off
    try:
        requests.put(f"{API}/widgets/{WIDGET_ID}", headers=H(super_tok),
                     json={"persona": {"on": False, "source": "custom", "agent_id": ""}}, timeout=15)
    except Exception:
        pass


# ============================================================ list
class TestList:
    def test_super_can_edit(self, super_tok):
        r = requests.get(f"{API}/agents", headers=H(super_tok), timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["can_edit"] is True
        assert isinstance(d["agents"], list)
        assert len(d["starters"]) == 6
        starter_keys = {s["key"] for s in d["starters"]}
        assert {"internet_sales", "service_scheduler", "website_concierge", "after_hours", "spanish", "demo_setter"} == starter_keys
        assert "friendly" in d["tones"]
        assert "auto" in d["languages"]

    def test_manager_read_only(self, mgr_tok):
        r = requests.get(f"{API}/agents", headers=H(mgr_tok), timeout=20)
        assert r.status_code == 200
        assert r.json()["can_edit"] is False

    def test_user_forbidden(self, user_tok):
        r = requests.get(f"{API}/agents", headers=H(user_tok), timeout=20)
        assert r.status_code == 403


# ============================================================ create
class TestCreate:
    def test_after_hours_starter(self, super_tok):
        r = requests.post(f"{API}/agents", headers=H(super_tok), json={"starter_key": "after_hours"}, timeout=20)
        assert r.status_code == 200, r.text
        a = r.json()["agent"]
        assert a["name"] == "Riley"
        assert a["title"] == "After-Hours Assistant"
        assert a["tone"] == "casual"
        assert len(a["hand_to_human"]) >= 1
        created_ids.append(a["id"])

    def test_spanish_starter(self, super_tok):
        r = requests.post(f"{API}/agents", headers=H(super_tok), json={"starter_key": "spanish"}, timeout=20)
        assert r.status_code == 200
        a = r.json()["agent"]
        assert a["name"] == "Sofía"
        assert a["language"] == "es"
        created_ids.append(a["id"])

    def test_blank_name_only(self, super_tok):
        r = requests.post(f"{API}/agents", headers=H(super_tok), json={"name": "TEST_QA Blank", "status": "draft"}, timeout=20)
        assert r.status_code == 200
        a = r.json()["agent"]
        assert a["name"] == "TEST_QA Blank"
        assert a["status"] == "draft"
        created_ids.append(a["id"])

    def test_missing_name(self, super_tok):
        r = requests.post(f"{API}/agents", headers=H(super_tok), json={}, timeout=20)
        assert r.status_code == 400
        assert "name" in r.json().get("detail", "").lower()

    def test_manager_cannot_create(self, mgr_tok):
        r = requests.post(f"{API}/agents", headers=H(mgr_tok), json={"starter_key": "after_hours"}, timeout=20)
        assert r.status_code == 403


# ============================================================ update + get
class TestUpdateGet:
    def test_update_normalizes(self, super_tok):
        r = requests.post(f"{API}/agents", headers=H(super_tok), json={"name": "TEST_Update"}, timeout=20)
        aid = r.json()["agent"]["id"]
        created_ids.append(aid)
        payload = {
            "name": "TEST_Updated", "tone": "nonsense", "language": "zz", "status": "weird",
            "facts": [" fact one  ", "fact2"], "hand_to_human": ["Price"],
        }
        r = requests.put(f"{API}/agents/{aid}", headers=H(super_tok), json=payload, timeout=20)
        assert r.status_code == 200
        a = r.json()["agent"]
        assert a["name"] == "TEST_Updated"
        assert a["tone"] == "friendly"  # fallback
        assert a["language"] == "auto"
        assert a["status"] == "active"
        assert "fact one" in a["facts"]

        # GET returns can_edit + used_by
        r = requests.get(f"{API}/agents/{aid}", headers=H(super_tok), timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert d["can_edit"] is True
        assert "used_by" in d["agent"]

    def test_manager_cannot_update(self, super_tok, mgr_tok):
        r = requests.post(f"{API}/agents", headers=H(super_tok), json={"name": "TEST_Mgr"}, timeout=20)
        aid = r.json()["agent"]["id"]
        created_ids.append(aid)
        r = requests.put(f"{API}/agents/{aid}", headers=H(mgr_tok), json={"name": "No"}, timeout=20)
        assert r.status_code == 403


# ============================================================ try (real LLM)
class TestTry:
    def test_try_sms_in_character(self, super_tok):
        r = requests.post(f"{API}/agents", headers=H(super_tok), json={"starter_key": "after_hours"}, timeout=20)
        aid = r.json()["agent"]["id"]
        created_ids.append(aid)
        r = requests.post(
            f"{API}/agents/{aid}/try", headers=H(super_tok),
            json={"channel": "sms", "messages": [{"role": "customer", "text": "Hey is the blue Tacoma still available and what is the best price?"}]},
            timeout=45,
        )
        assert r.status_code == 200, r.text
        reply = r.json()["reply"]
        assert isinstance(reply, str) and len(reply) > 0
        # agent is told to hand off on price - should NOT quote $
        assert "$" not in reply

    def test_try_webchat(self, super_tok):
        r = requests.post(f"{API}/agents", headers=H(super_tok), json={"starter_key": "website_concierge"}, timeout=20)
        aid = r.json()["agent"]["id"]
        created_ids.append(aid)
        r = requests.post(
            f"{API}/agents/{aid}/try", headers=H(super_tok),
            json={"channel": "webchat", "messages": [{"role": "customer", "text": "What are your hours?"}]},
            timeout=45,
        )
        assert r.status_code == 200
        assert len(r.json()["reply"]) > 0

    def test_manager_can_try(self, super_tok, mgr_tok):
        r = requests.post(f"{API}/agents", headers=H(super_tok), json={"starter_key": "internet_sales"}, timeout=20)
        aid = r.json()["agent"]["id"]
        created_ids.append(aid)
        r = requests.post(
            f"{API}/agents/{aid}/try", headers=H(mgr_tok),
            json={"channel": "sms", "messages": [{"role": "customer", "text": "Hi, got a Camry?"}]},
            timeout=45,
        )
        assert r.status_code == 200


# ============================================================ deploy
class TestDeploy:
    def test_targets_super_only(self, super_tok, mgr_tok):
        r = requests.post(f"{API}/agents", headers=H(super_tok), json={"starter_key": "after_hours"}, timeout=20)
        aid = r.json()["agent"]["id"]
        created_ids.append(aid)

        r = requests.get(f"{API}/agents/{aid}/targets", headers=H(super_tok), timeout=20)
        assert r.status_code == 200
        t = r.json()
        assert "widgets" in t and "lead_sources" in t and "inboxes" in t

        r = requests.get(f"{API}/agents/{aid}/targets", headers=H(mgr_tok), timeout=20)
        assert r.status_code == 403

    def test_deploy_lead_source_and_undeploy(self, super_tok):
        r = requests.post(f"{API}/agents", headers=H(super_tok), json={"starter_key": "internet_sales"}, timeout=20)
        aid = r.json()["agent"]["id"]
        created_ids.append(aid)

        r = requests.get(f"{API}/agents/{aid}/targets", headers=H(super_tok), timeout=20)
        sources = r.json()["lead_sources"]
        if not sources:
            pytest.skip("no lead sources in preview")
        src_id = sources[0]["id"]

        r = requests.put(f"{API}/agents/{aid}/deploy", headers=H(super_tok),
                         json={"kind": "lead_source", "target_id": src_id, "on": True}, timeout=20)
        assert r.status_code == 200
        used = r.json()["used_by"]
        assert any(u["kind"] == "lead_source" and u["id"] == src_id for u in used)

        # workflow reflects it
        r = requests.get(f"{API}/lead-sources/{src_id}/workflow", headers=H(super_tok), timeout=20)
        assert r.status_code == 200
        wf = r.json()
        assert wf.get("agent_id") == aid, wf

        # undeploy
        r = requests.put(f"{API}/agents/{aid}/deploy", headers=H(super_tok),
                         json={"kind": "lead_source", "target_id": src_id, "on": False}, timeout=20)
        assert r.status_code == 200
        assert not any(u["id"] == src_id for u in r.json()["used_by"])

    def test_deploy_widget(self, super_tok):
        r = requests.post(f"{API}/agents", headers=H(super_tok), json={"starter_key": "website_concierge"}, timeout=20)
        aid = r.json()["agent"]["id"]
        created_ids.append(aid)

        r = requests.put(f"{API}/agents/{aid}/deploy", headers=H(super_tok),
                         json={"kind": "widget", "target_id": WIDGET_ID, "on": True}, timeout=20)
        assert r.status_code == 200

        r = requests.get(f"{API}/widgets/{WIDGET_ID}", headers=H(super_tok), timeout=20)
        assert r.status_code == 200
        w = r.json().get("widget") or r.json()
        persona = w.get("persona") or {}
        assert persona.get("on") is True
        assert persona.get("source") == "agent"
        assert persona.get("agent_id") == aid

        # undeploy
        requests.put(f"{API}/agents/{aid}/deploy", headers=H(super_tok),
                     json={"kind": "widget", "target_id": WIDGET_ID, "on": False}, timeout=20)

    def test_deploy_inbox(self, super_tok):
        r = requests.post(f"{API}/agents", headers=H(super_tok), json={"starter_key": "service_scheduler"}, timeout=20)
        aid = r.json()["agent"]["id"]
        created_ids.append(aid)

        r = requests.get(f"{API}/inboxes", headers=H(super_tok), timeout=20)
        if r.status_code != 200:
            pytest.skip("no inboxes list")
        data = r.json()
        boxes = data.get("inboxes") or data.get("items") or data
        if not boxes:
            pytest.skip("no inboxes in preview")
        inbox_id = boxes[0]["id"] if "id" in boxes[0] else boxes[0]["_id"]

        r = requests.put(f"{API}/agents/{aid}/deploy", headers=H(super_tok),
                         json={"kind": "inbox", "target_id": inbox_id, "on": True}, timeout=20)
        assert r.status_code == 200

        r = requests.get(f"{API}/inboxes/{inbox_id}", headers=H(super_tok), timeout=20)
        assert r.status_code == 200
        j = r.json()
        box = j.get("inbox") or j
        assert box.get("agent_id") == aid

        requests.put(f"{API}/agents/{aid}/deploy", headers=H(super_tok),
                     json={"kind": "inbox", "target_id": inbox_id, "on": False}, timeout=20)

    def test_deploy_bad_kind(self, super_tok):
        r = requests.post(f"{API}/agents", headers=H(super_tok), json={"starter_key": "after_hours"}, timeout=20)
        aid = r.json()["agent"]["id"]
        created_ids.append(aid)
        r = requests.put(f"{API}/agents/{aid}/deploy", headers=H(super_tok),
                         json={"kind": "spaceship", "target_id": WIDGET_ID, "on": True}, timeout=20)
        assert r.status_code == 400

    def test_deploy_archived_blocked(self, super_tok):
        r = requests.post(f"{API}/agents", headers=H(super_tok), json={"name": "TEST_Arch", "status": "archived"}, timeout=20)
        aid = r.json()["agent"]["id"]
        created_ids.append(aid)
        r = requests.put(f"{API}/agents/{aid}/deploy", headers=H(super_tok),
                         json={"kind": "widget", "target_id": WIDGET_ID, "on": True}, timeout=20)
        assert r.status_code == 400

    def test_manager_cannot_deploy(self, super_tok, mgr_tok):
        r = requests.post(f"{API}/agents", headers=H(super_tok), json={"starter_key": "after_hours"}, timeout=20)
        aid = r.json()["agent"]["id"]
        created_ids.append(aid)
        r = requests.put(f"{API}/agents/{aid}/deploy", headers=H(mgr_tok),
                         json={"kind": "widget", "target_id": WIDGET_ID, "on": True}, timeout=20)
        assert r.status_code == 403


# ============================================================ delete / archive
class TestDelete:
    def test_delete_undeployed(self, super_tok):
        r = requests.post(f"{API}/agents", headers=H(super_tok), json={"name": "TEST_Del"}, timeout=20)
        aid = r.json()["agent"]["id"]
        r = requests.delete(f"{API}/agents/{aid}", headers=H(super_tok), timeout=20)
        assert r.status_code == 200
        assert r.json()["archived"] is False
        # confirm gone
        r = requests.get(f"{API}/agents/{aid}", headers=H(super_tok), timeout=20)
        assert r.status_code == 404

    def test_delete_deployed_archives(self, super_tok):
        r = requests.post(f"{API}/agents", headers=H(super_tok), json={"starter_key": "website_concierge"}, timeout=20)
        aid = r.json()["agent"]["id"]
        created_ids.append(aid)
        requests.put(f"{API}/agents/{aid}/deploy", headers=H(super_tok),
                     json={"kind": "widget", "target_id": WIDGET_ID, "on": True}, timeout=20)
        r = requests.delete(f"{API}/agents/{aid}", headers=H(super_tok), timeout=20)
        assert r.status_code == 200
        assert r.json()["archived"] is True
        # excluded from list
        r = requests.get(f"{API}/agents", headers=H(super_tok), timeout=20)
        assert not any(a["id"] == aid for a in r.json()["agents"])
        # included with include_archived
        r = requests.get(f"{API}/agents?include_archived=true", headers=H(super_tok), timeout=20)
        assert any(a["id"] == aid for a in r.json()["agents"])
        # cleanup widget
        requests.put(f"{API}/widgets/{WIDGET_ID}", headers=H(super_tok),
                     json={"persona": {"on": False, "source": "custom", "agent_id": ""}}, timeout=15)


# ============================================================ legacy va-profiles mapping
class TestLegacyVAProfiles:
    def test_va_profiles_shape(self, super_tok):
        r = requests.get(f"{API}/va-profiles", headers=H(super_tok), timeout=20)
        assert r.status_code == 200
        profiles = r.json()["profiles"]
        if profiles:
            p = profiles[0]
            for k in ("_id", "name", "tagline", "bio", "tone", "avatar_color"):
                assert k in p


# ============================================================ widget ask with agent (real LLM)
class TestWidgetAskWithAgent:
    def test_ask_uses_agent_and_handoff(self, super_tok):
        r = requests.post(f"{API}/agents", headers=H(super_tok), json={"starter_key": "after_hours"}, timeout=20)
        aid = r.json()["agent"]["id"]
        agent_name = r.json()["agent"]["name"]
        created_ids.append(aid)
        requests.put(f"{API}/agents/{aid}/deploy", headers=H(super_tok),
                     json={"kind": "widget", "target_id": WIDGET_ID, "on": True}, timeout=20)
        time.sleep(1)
        r = requests.post(f"{API}/widgets/{WIDGET_ID}/ask", headers=H(super_tok),
                          json={"question": "What are your hours?"}, timeout=45)
        assert r.status_code == 200, r.text
        d = r.json()
        used = d.get("used") or {}
        assert used.get("agent") == agent_name, d

        # handoff topic - include both tokens from "Price or payments"
        r = requests.post(f"{API}/widgets/{WIDGET_ID}/ask", headers=H(super_tok),
                          json={"question": "What is the price and monthly payments on the Pro plan?"}, timeout=45)
        assert r.status_code == 200
        d = r.json()
        assert d.get("handoff") is True, d

        # cleanup widget
        requests.put(f"{API}/agents/{aid}/deploy", headers=H(super_tok),
                     json={"kind": "widget", "target_id": WIDGET_ID, "on": False}, timeout=20)
        r = requests.get(f"{API}/widgets/{WIDGET_ID}", headers=H(super_tok), timeout=20)
        w = r.json().get("widget") or r.json()
        assert (w.get("persona") or {}).get("on") is False


# ============================================================ picker endpoints (lead sources / inboxes)
class TestPickerSaves:
    def test_lead_source_workflow_save_and_clear(self, super_tok):
        r = requests.post(f"{API}/agents", headers=H(super_tok), json={"starter_key": "internet_sales"}, timeout=20)
        aid = r.json()["agent"]["id"]
        created_ids.append(aid)
        r = requests.get(f"{API}/lead-sources?store_id={MANAGER_STORE_ID}", headers=H(super_tok), timeout=20)
        assert r.status_code == 200
        sources = r.json().get("sources") or r.json().get("lead_sources") or r.json().get("items") or []
        src = next((s for s in sources if s.get("kind") not in ("website_widget", "inbox_direct")), None)
        if not src:
            pytest.skip("no suitable source")
        sid = src.get("_id") or src.get("id")

        r = requests.put(f"{API}/lead-sources/{sid}/workflow", headers=H(super_tok),
                         json={"agent_id": aid}, timeout=20)
        assert r.status_code == 200
        r = requests.get(f"{API}/lead-sources/{sid}/workflow", headers=H(super_tok), timeout=20)
        wf = r.json()
        assert wf.get("agent_id") == aid

        requests.put(f"{API}/lead-sources/{sid}/workflow", headers=H(super_tok),
                     json={"agent_id": None}, timeout=20)
        r = requests.get(f"{API}/lead-sources/{sid}/workflow", headers=H(super_tok), timeout=20)
        wf = r.json()
        assert not wf.get("agent_id")

    def test_inbox_agent_save_and_clear(self, super_tok):
        r = requests.post(f"{API}/agents", headers=H(super_tok), json={"starter_key": "service_scheduler"}, timeout=20)
        aid = r.json()["agent"]["id"]
        created_ids.append(aid)
        r = requests.get(f"{API}/inboxes", headers=H(super_tok), timeout=20)
        boxes = r.json().get("inboxes") or r.json().get("items") or []
        if not boxes:
            pytest.skip("no inboxes")
        iid = boxes[0].get("id") or boxes[0].get("_id")
        r = requests.put(f"{API}/inboxes/{iid}", headers=H(super_tok), json={"agent_id": aid}, timeout=20)
        assert r.status_code == 200
        r = requests.get(f"{API}/inboxes/{iid}", headers=H(super_tok), timeout=20)
        box = r.json().get("inbox") or r.json()
        assert box.get("agent_id") == aid
        requests.put(f"{API}/inboxes/{iid}", headers=H(super_tok), json={"agent_id": ""}, timeout=20)
        r = requests.get(f"{API}/inboxes/{iid}", headers=H(super_tok), timeout=20)
        box = r.json().get("inbox") or r.json()
        assert not box.get("agent_id")
