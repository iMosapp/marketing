"""Phase 2/3 Website Widget: Jessi chat door, page rules, KB, and preview overrides.

Runs against the live backend at REACT_APP_BACKEND_URL. Uses 500-555 phones.
Leaves the widget clean: chat door on, page_rules [], no QA facts/specials/never/notes.
Pre-existing store fact 'We take walk-ins weekdays until 6 pm' is preserved.

    cd /app/backend && set -a && . ./.env && . ../frontend/.env && set +a && \
        python -m pytest tests/test_website_widget_jessi.py -v
"""
import base64
import json
import os
import time
import re
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
STORE = "69a0b7095fddcede09591668"
WID = "6ab72996c248f5420bf0a14a"
MGR = ("qa-manager@invalid.imonsocial.test", "Manager123!")
REP = ("activation-tester@invalid.imonsocial.test", "NewPass123!")
PRESERVED_FACT = "We take walk-ins weekdays until 6 pm"
RUN = str(int(time.time()))[-6:]


def _login(email, pw):
    r = requests.post(f"{BASE}/api/auth/login", json={"email": email, "password": pw}, timeout=30)
    r.raise_for_status()
    tok = r.json().get("token") or r.json().get("access_token")
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def mgr():
    return _login(*MGR)


@pytest.fixture(scope="module")
def rep():
    return _login(*REP)


@pytest.fixture(scope="module")
def key(mgr):
    r = requests.get(f"{BASE}/api/widgets/{WID}", headers=mgr, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["widget"]["key"]


# ---------- GET detail structure ----------
def test_manager_detail_shape(mgr):
    r = requests.get(f"{BASE}/api/widgets/{WID}", headers=mgr, timeout=30)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j.get("can_manage") is True
    assert isinstance(j.get("facts"), list)
    assert isinstance(j.get("recent_chats"), list)
    w = j["widget"]
    kb = w.get("kb") or {}
    for f in ("welcome", "specials", "never", "notes", "share_listed_prices"):
        assert f in kb, f"kb.{f} missing"
    chat = (w.get("doors") or {}).get("chat") or {}
    for f in ("on", "label", "intro", "button", "placeholder", "human"):
        assert f in chat, f"doors.chat.{f} missing"
    assert isinstance((w.get("appearance") or {}).get("page_rules"), list)


def test_rep_read_only(rep):
    r = requests.get(f"{BASE}/api/widgets/{WID}", headers=rep, timeout=30)
    assert r.status_code == 200
    assert r.json().get("can_manage") is False
    put = requests.put(f"{BASE}/api/widgets/{WID}", json={"name": "x"}, headers=rep, timeout=30)
    assert put.status_code == 403
    fact = requests.post(f"{BASE}/api/widgets/{WID}/facts", json={"text": "sneaky rep fact"}, headers=rep, timeout=30)
    assert fact.status_code == 403


# ---------- PUT round-trip ----------
def test_put_page_rules_kb_chat_roundtrip(mgr):
    body = {
        "appearance": {
            "page_rules": [
                {"match": "/inventory", "greeting": "Looking at a specific vehicle? Ask Jessi.", "door": "chat"},
                {"match": "pricing", "greeting": "Price question? Text us.", "door": "text"},
                {"match": "/foo", "door": "chat"},  # missing greeting -> dropped
                {"match": "/bar", "greeting": "bad door", "door": "sms"},  # bad door -> ''
            ] + [{"match": f"/x{i}", "greeting": f"g{i}"} for i in range(15)],  # exceed 12 -> capped
        },
        "doors": {"chat": {"on": True, "label": "Chat with Jessi"}},
        "kb": {
            "welcome": "Hey, Jessi here.",
            "specials": [{"title": "$39 oil change", "details": "Synthetic blend", "ends": "2027-01-31"}],
            "never": ["employment"],
            "notes": "Family owned since 1982",
            "share_listed_prices": True,
        },
    }
    r = requests.put(f"{BASE}/api/widgets/{WID}", json=body, headers=mgr, timeout=30)
    assert r.status_code == 200, r.text
    w = r.json()["widget"]
    rules = (w.get("appearance") or {}).get("page_rules") or []
    assert len(rules) <= 12, f"expected max 12, got {len(rules)}"
    # No rule without a greeting should remain
    assert all(r.get("greeting") for r in rules), rules
    # bad door became ''
    bar = next((r for r in rules if r.get("match") == "/bar"), None)
    assert bar and bar.get("door") == "", bar
    # good rules preserved
    inv = next(r for r in rules if r["match"] == "/inventory")
    assert inv["greeting"] == "Looking at a specific vehicle? Ask Jessi." and inv["door"] == "chat"

    # round-trip via GET
    g = requests.get(f"{BASE}/api/widgets/{WID}", headers=mgr, timeout=30).json()["widget"]
    assert g["doors"]["chat"]["label"] == "Chat with Jessi"
    assert g["kb"]["welcome"] == "Hey, Jessi here."
    assert g["kb"]["never"] == ["employment"]
    assert g["kb"]["notes"] == "Family owned since 1982"
    assert g["kb"]["share_listed_prices"] is True
    assert g["kb"]["specials"] and g["kb"]["specials"][0]["title"] == "$39 oil change"


# ---------- facts create + delete ----------
def test_facts_add_and_remove(mgr):
    qa_text = f"QA fact {RUN}: we deliver within 100 miles"
    r = requests.post(f"{BASE}/api/widgets/{WID}/facts", json={"text": qa_text}, headers=mgr, timeout=30)
    assert r.status_code in (200, 201), r.text
    fid = r.json()["fact"]["id"]
    # Appears in GET
    facts = requests.get(f"{BASE}/api/widgets/{WID}", headers=mgr, timeout=30).json()["facts"]
    assert any(f["id"] == fid for f in facts)
    # Ensure preserved fact still present
    assert any(PRESERVED_FACT in (f.get("text") or "") for f in facts), "preserved fact was removed"
    # Delete
    d = requests.delete(f"{BASE}/api/widgets/{WID}/facts/{fid}", headers=mgr, timeout=30)
    assert d.status_code == 200
    facts2 = requests.get(f"{BASE}/api/widgets/{WID}", headers=mgr, timeout=30).json()["facts"]
    assert not any(f["id"] == fid for f in facts2)
    assert any(PRESERVED_FACT in (f.get("text") or "") for f in facts2)


# ---------- Ask Jessi (LLM, up to 30s) ----------
def test_ask_jessi_hours_and_pricing(mgr):
    r = requests.post(f"{BASE}/api/widgets/{WID}/ask", json={"question": "What are your hours?"}, headers=mgr, timeout=45)
    assert r.status_code == 200, r.text
    j = r.json()
    assert "reply" in j and "handoff" in j and "used" in j
    used = j["used"]
    for k in ("facts", "specials", "inventory_matches", "inventory_total", "hours"):
        assert k in used, f"used.{k} missing"
    assert "\u2014" not in j["reply"], "em dash found in reply"

    r2 = requests.post(f"{BASE}/api/widgets/{WID}/ask",
                      json={"question": "How much is the cheapest truck with financing?"},
                      headers=mgr, timeout=45)
    assert r2.status_code == 200
    j2 = r2.json()
    assert j2.get("handoff") is True, j2
    assert "\u2014" not in j2["reply"]


# ---------- Public chat flow ----------
def test_public_chat_full_flow(mgr, key):
    # Ensure chat is on & welcome set
    requests.put(f"{BASE}/api/widgets/{WID}", json={"doors": {"chat": {"on": True}}, "kb": {"welcome": "Hey, Jessi here."}},
                 headers=mgr, timeout=30)
    page = "https://qa-dealer.test/inventory"
    r = requests.post(f"{BASE}/api/w/{key}/chat/start",
                      json={"page": page, "title": "QA", "visitor": f"vqa{RUN}"}, timeout=30)
    assert r.status_code == 200, r.text
    j = r.json()
    sid = j["sid"]
    assert j.get("greeting") == "Hey, Jessi here.", j

    state = requests.get(f"{BASE}/api/w/{key}/chat/{sid}", timeout=30)
    assert state.status_code == 200
    assert isinstance(state.json().get("messages"), list)

    m1 = requests.post(f"{BASE}/api/w/{key}/chat/{sid}/message",
                       json={"text": "Are you open Saturday?"}, timeout=60)
    assert m1.status_code == 200, m1.text
    assert m1.json().get("reply")

    m2 = requests.post(f"{BASE}/api/w/{key}/chat/{sid}/message",
                       json={"text": "What is my trade worth?"}, timeout=60)
    assert m2.status_code == 200
    j2 = m2.json()
    assert j2.get("handoff") or j2.get("need_contact"), j2

    c = requests.post(f"{BASE}/api/w/{key}/chat/{sid}/contact",
                      json={"name": "QA Visitor", "phone": "5005550031"}, timeout=45)
    assert c.status_code == 200, c.text
    jc = c.json()
    # handoff creates a lead — check response signals
    assert jc.get("handoff") is True or jc.get("status") == "handed_off", jc

    # Fresh session -> /human asks for contact
    r2 = requests.post(f"{BASE}/api/w/{key}/chat/start",
                       json={"page": page, "visitor": f"vqa2{RUN}"}, timeout=30)
    assert r2.status_code == 200
    sid2 = r2.json()["sid"]
    h = requests.post(f"{BASE}/api/w/{key}/chat/{sid2}/human", timeout=30)
    assert h.status_code == 200
    assert h.json().get("need_contact") is True, h.json()

    # bad sid -> 404
    bad = requests.get(f"{BASE}/api/w/{key}/chat/nope123", timeout=30)
    assert bad.status_code == 404


def test_chat_off_blocks_start(mgr, key):
    # Turn off
    requests.put(f"{BASE}/api/widgets/{WID}", json={"doors": {"chat": {"on": False}}}, headers=mgr, timeout=30)
    r = requests.post(f"{BASE}/api/w/{key}/chat/start",
                     json={"page": "https://qa-dealer.test/", "visitor": f"voff{RUN}"}, timeout=30)
    assert r.status_code == 400, r.text
    # Turn back on
    requests.put(f"{BASE}/api/widgets/{WID}", json={"doors": {"chat": {"on": True}}}, headers=mgr, timeout=30)


# ---------- Preview & script ----------
def test_preview_and_script_privacy(key):
    r = requests.get(f"{BASE}/api/w/{key}/demo", params={"path": "/inventory"}, timeout=30)
    assert r.status_code == 200
    assert 'window.IMOS_WIDGET_PATH = "/inventory"' in r.text, r.text[:2000]

    c = base64.urlsafe_b64encode(json.dumps({"kb": {"welcome": "Howdy"}}).encode()).decode().rstrip("=")
    r2 = requests.get(f"{BASE}/api/w/{key}/demo", params={"c": c}, timeout=30)
    assert r2.status_code == 200
    assert 'chat_welcome":"Howdy' in r2.text

    js = requests.get(f"{BASE}/api/w/{key}.js", timeout=30)
    assert js.status_code == 200
    assert "page_rules" in js.text
    # KB notes/specials text must not be in public JS (non-preview)
    assert "Family owned since 1982" not in js.text
    assert "$39 oil change" not in js.text


# ---------- Regression: text + call still work ----------
def test_regression_text_and_call_preview(key):
    # Widget must accept the qa-dealer.test domain OR have no domains restriction.
    # The test setup in fixture left domains open in cleanup.
    page = "https://qa-dealer.test/"
    r = requests.post(f"{BASE}/api/w/{key}/text",
                     json={"name": f"QA Text {RUN}", "phone": f"5005550{RUN[-3:]}",
                           "message": "regression", "page": page,
                           "visitor": f"vreg{RUN}"}, timeout=30)
    # Either 200 (ok) or 403 (domain restricted). Both non-500.
    assert r.status_code in (200, 403), r.text

    assert os.environ.get("WIDGET_RING_DRY_RUN", "").lower() == "true", "WIDGET_RING_DRY_RUN must be true"


# ---------- Cleanup: restore clean state ----------
@pytest.fixture(scope="module", autouse=True)
def _final_cleanup(mgr):
    yield
    # Reset kb + page rules + chat on, defaults for doors
    body = {
        "appearance": {"page_rules": []},
        "doors": {
            "chat": {"on": True, "label": "Chat with Jessi", "intro": "", "button": "", "placeholder": "", "human": ""},
        },
        "kb": {"welcome": "", "specials": [], "never": [], "notes": "", "share_listed_prices": False},
    }
    try:
        requests.put(f"{BASE}/api/widgets/{WID}", json=body, headers=mgr, timeout=30)
    except Exception:
        pass
    # Remove any QA facts we might have left
    try:
        facts = requests.get(f"{BASE}/api/widgets/{WID}", headers=mgr, timeout=30).json().get("facts") or []
        for f in facts:
            if "QA fact" in (f.get("text") or "") and PRESERVED_FACT not in (f.get("text") or ""):
                requests.delete(f"{BASE}/api/widgets/{WID}/facts/{f['id']}", headers=mgr, timeout=30)
    except Exception:
        pass
