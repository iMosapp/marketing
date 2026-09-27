"""Widget Jessi training layer: playbook funnel (qualifying questions -> pitch -> booking form), scripted answers, specificity.
Run alone: python -m pytest tests/test_widget_playbook.py -q  (module owns its own event loop like the other widget suites)."""
import os
import time

import pytest
import requests

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
WID = "6ab72996c248f5420bf0a14a"
SCRIPT = {"q": "Do you integrate with Zapier?", "a": "Yes. Zapier and Make are both native, about a two minute setup, and HubSpot two-way sync is next."}


def _tok(email, pw):
    r = requests.post(f"{BASE}/api/auth/login", json={"email": email, "password": pw}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def mgr():
    return {"Authorization": f"Bearer {_tok('qa-manager@invalid.imonsocial.test', 'Manager123!')}"}


@pytest.fixture(scope="module", autouse=True)
def _business_with_training(mgr):
    """Business mode + a scripted answer + default playbook (offer after 2). Restores the previous kb bits afterwards."""
    before = requests.get(f"{BASE}/api/widgets/{WID}", headers=mgr, timeout=30).json()["widget"]["kb"]
    r = requests.put(f"{BASE}/api/widgets/{WID}", headers=mgr, timeout=30,
                     json={"kb": {"mode": "business", "scripts": [SCRIPT], "playbook": {"on": True, "goal": "", "questions": [], "offer_after": 2, "pitch": ""}}})
    assert r.status_code == 200, r.text
    yield
    requests.put(f"{BASE}/api/widgets/{WID}", headers=mgr, timeout=30,
                 json={"kb": {"mode": before.get("mode") or "dealership", "scripts": before.get("scripts") or [], "playbook": before.get("playbook") or {}}})


@pytest.fixture(scope="module")
def key(mgr):
    return requests.get(f"{BASE}/api/widgets/{WID}", headers=mgr, timeout=30).json()["widget"]["key"]


def test_playbook_and_scripts_are_normalized(mgr):
    r = requests.put(f"{BASE}/api/widgets/{WID}", headers=mgr, timeout=30, json={"kb": {
        "playbook": {"on": False, "goal": "x" * 200, "questions": [f"q{i}" for i in range(7)] + ["  "], "offer_after": 9, "pitch": "p"},
        "scripts": [{"q": f"q{i}", "a": f"a{i}"} for i in range(30)] + [{"q": "", "a": "no question"}, {"q": "no answer", "a": " "}]}})
    assert r.status_code == 200, r.text
    kb = r.json()["widget"]["kb"]
    assert kb["playbook"]["on"] is False and len(kb["playbook"]["goal"]) == 80 and kb["playbook"]["questions"] == [f"q{i}" for i in range(5)]
    assert kb["playbook"]["offer_after"] == 5 and kb["playbook"]["pitch"] == "p"
    assert len(kb["scripts"]) == 25 and all(s["q"] and s["a"] for s in kb["scripts"])
    # back to the module setup
    r2 = requests.put(f"{BASE}/api/widgets/{WID}", headers=mgr, timeout=30,
                      json={"kb": {"scripts": [SCRIPT], "playbook": {"on": True, "goal": "", "questions": [], "offer_after": 2, "pitch": ""}}})
    assert r2.json()["widget"]["kb"]["playbook"]["on"] is True and r2.json()["widget"]["kb"]["scripts"] == [SCRIPT]


def test_ask_uses_scripted_answer_and_first_question(mgr):
    r = requests.post(f"{BASE}/api/widgets/{WID}/ask", headers=mgr, timeout=90, json={"question": "do you guys integrate with zapier or anything like that?"})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["used"]["scripts"] == 1 and j["used"]["playbook"] is True
    low = j["reply"].lower()
    assert "zapier" in low and "make" in low, j["reply"]
    assert "?" in j["reply"]  # ends with the first qualifying question


def test_funnel_asks_then_pitches_and_opens_booking(key):
    j = requests.post(f"{BASE}/api/w/{key}/chat/start", json={"page": "https://www.imonsocial.com/", "title": "Home", "visitor": f"qa-pb-{int(time.time())}"}, timeout=30).json()
    sid = j["sid"]
    turns = ["What does your product actually do?",
             "We're a single Ford store, 12 salespeople, on DealerSocket.",
             "Reps stop following up once the deal closes."]
    replies = []
    for t in turns:
        m = requests.post(f"{BASE}/api/w/{key}/chat/{sid}/message", json={"text": t}, timeout=90)
        assert m.status_code == 200, m.text
        replies.append(m.json())
    # every reply before the pitch ends in a qualifying question, none asks for a phone number
    assert "?" in replies[0]["messages"][-1]["text"] and "?" in replies[1]["messages"][-1]["text"]
    assert all("mobile" not in r["messages"][-1]["text"].lower() and "phone number" not in r["messages"][-1]["text"].lower() for r in replies)
    assert replies[0]["offer_booking"] is False and replies[1]["offer_booking"] is False
    # after two answers: pitch + booking form offered
    assert replies[2]["offer_booking"] is True
    assert "demo" in replies[2]["messages"][-1]["text"].lower()


# ---------------------------------------------------------------- persona / person launcher (Sep 27 2026)
def test_persona_normalizes_and_prompts_as_the_named_va():
    import asyncio
    from services import widgets as W
    from services import widget_chat as C
    cfg = W.normalize_config({"appearance": {"launcher": "person", "smart_teasers": {"inventory": "Pick one? I can help.", "bogus": "x"}},
                              "persona": {"on": True, "source": "custom", "name": "Amanda", "title": "Product Specialist", "photo_url": "javascript:alert(1)"}})
    assert cfg["appearance"]["launcher"] == "person" and cfg["appearance"]["smart_teasers"] == {"inventory": "Pick one? I can help."}
    assert cfg["persona"]["photo_url"] == "" and cfg["persona"]["name"] == "Amanda"
    pub = W.public_config({"key": "k", **cfg}, {"name": "QA Jeep"}, va={"on": True, "name": "Amanda", "title": "Product Specialist", "photo": ""})
    assert pub["va"]["name"] == "Amanda" and pub["appearance"]["smart_teasers"]["inventory"] == "Pick one? I can help." and pub["appearance"]["smart_teasers"]["service"]
    off = W.public_config({"key": "k", **W.normalize_config({})}, {"name": "QA Jeep"})
    assert off["va"] == {"on": False, "name": "Jessi"}
    p = C.system_prompt({"name": "QA Jeep"}, {"mode": "dealership"}, "K", "normal", False, va={"on": True, "name": "Amanda", "title": "Product Specialist", "tone": "warm"})
    assert p.startswith("You are Amanda") and "AI assistant" in p and "Jessi" not in p
    assert C.system_prompt({"name": "QA Jeep"}, {"mode": "business"}, "K", "normal", False).startswith("You are Jessi")
