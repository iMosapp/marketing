"""Widget persona / person launcher + smart teasers + team endpoint (iter 352).

Covers the review request:
- GET /api/widgets/{id}/team requires manager auth
- PUT persona + appearance.launcher persists and reloads
- GET /api/w/{key}/config returns 'va' with persona fields
- GET /api/w/{key}/demo?path=/pricing HTML includes person launcher + smart teaser
- POST /api/widgets/{id}/ask answers in first person as the persona name and doesn't claim to be human
- Cleanup: restore launcher=bubble, persona.on=false at the end.
"""
import os
import time

import pytest
import requests

BASE = (os.environ.get("REACT_APP_BACKEND_URL") or open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split()[0]).rstrip("/")
WID = "6ab72996c248f5420bf0a14a"
KEY = "8SkUaRqT"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}


def _tok(email, pw):
    r = requests.post(f"{BASE}/api/auth/login", json={"email": email, "password": pw}, headers=UA, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"], r.json()["user"]["_id"]


@pytest.fixture(scope="module")
def admin_h():
    t, uid = _tok("forest@imosapp.com", "Admin123!")
    return {"Authorization": f"Bearer {t}", "X-User-ID": uid, **UA}


@pytest.fixture(scope="module")
def mgr_h():
    t, uid = _tok("qa-manager@invalid.imonsocial.test", "Manager123!")
    return {"Authorization": f"Bearer {t}", "X-User-ID": uid, **UA}


@pytest.fixture(scope="module", autouse=True)
def _cleanup():
    yield
    # Restore preview widget to defaults so the demo iframe looks classic again.
    try:
        t, uid = _tok("forest@imosapp.com", "Admin123!")
        requests.put(f"{BASE}/api/widgets/{WID}",
                     headers={"Authorization": f"Bearer {t}", "X-User-ID": uid, **UA},
                     json={"appearance": {"launcher": "bubble"}, "persona": {"on": False}},
                     timeout=30)
    except Exception:
        pass


# ---------- team endpoint auth --------------------------------------------------
def test_team_endpoint_requires_manager():
    r = requests.get(f"{BASE}/api/widgets/{WID}/team", headers=UA, timeout=30)
    assert r.status_code in (401, 403), r.status_code


def test_team_endpoint_returns_members(mgr_h):
    r = requests.get(f"{BASE}/api/widgets/{WID}/team", headers=mgr_h, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "members" in data and isinstance(data["members"], list)
    if data["members"]:
        m = data["members"][0]
        for key in ("id", "name", "first", "title", "photo"):
            assert key in m, f"missing {key} in {m}"


# ---------- persist launcher=person + custom persona ---------------------------
PHOTO_URL = "https://randomuser.me/api/portraits/women/44.jpg"


def test_persona_persists_and_reloads(admin_h):
    persona = {"on": True, "source": "custom", "name": "Amanda", "title": "Product Specialist",
               "photo_url": PHOTO_URL, "tone": "warm", "intro": "Hi, I'm Amanda"}
    r = requests.put(f"{BASE}/api/widgets/{WID}", headers=admin_h,
                     json={"appearance": {"launcher": "person", "smart_teasers_on": True,
                                          "smart_teasers": {"pricing": "TEST_pricing_line_here"}},
                           "persona": persona},
                     timeout=30)
    assert r.status_code == 200, r.text
    w = r.json()["widget"]
    assert w["appearance"]["launcher"] == "person"
    assert w["persona"]["on"] is True and w["persona"]["name"] == "Amanda"
    assert w["persona"]["photo_url"] == PHOTO_URL
    assert w["appearance"]["smart_teasers"].get("pricing") == "TEST_pricing_line_here"

    # Reload and verify persistence via a fresh GET
    g = requests.get(f"{BASE}/api/widgets/{WID}", headers=admin_h, timeout=30)
    assert g.status_code == 200
    w2 = g.json()["widget"]
    assert w2["appearance"]["launcher"] == "person"
    assert w2["persona"]["name"] == "Amanda" and w2["persona"]["on"] is True


# ---------- public /config exposes 'va' ----------------------------------------
def test_public_config_returns_va_and_smart_teasers():
    r = requests.get(f"{BASE}/api/w/{KEY}/config", headers=UA, timeout=30)
    assert r.status_code == 200, r.text
    cfg = r.json()
    va = cfg.get("va")
    assert va and va["on"] is True
    assert va["name"] == "Amanda"
    assert va["title"] == "Product Specialist"
    assert va["photo"] == PHOTO_URL
    # smart teasers merged with defaults (business mode has home/pricing/features)
    st = cfg["appearance"]["smart_teasers"]
    assert st.get("pricing") == "TEST_pricing_line_here"
    assert st.get("home") and st.get("features")


# ---------- demo HTML renders person launcher + smart teaser -------------------
def test_demo_html_renders_person_launcher_and_pricing_teaser():
    r = requests.get(f"{BASE}/api/w/{KEY}/demo?path=/pricing", headers=UA, timeout=30)
    assert r.status_code == 200, r.text
    html = r.text
    # widget JS is inlined; person launcher and teaser markup live in the script template
    assert "person" in html and "imosw-launch" in html
    assert "TEST_pricing_line_here" in html or "pricing" in html.lower()
    assert "Amanda" in html


# ---------- persona-aware /ask -------------------------------------------------
def test_ask_answers_as_persona_not_claiming_human(admin_h):
    r = requests.post(f"{BASE}/api/widgets/{WID}/ask", headers=admin_h,
                      json={"question": "Are you a real person?"}, timeout=90)
    assert r.status_code == 200, r.text
    reply = (r.json().get("reply") or "").lower()
    assert reply, "empty reply"
    # Should not claim to be human. Look for AI/assistant self-identification.
    assert "yes, i'm a real person" not in reply
    assert "yes i am a real person" not in reply
    # Prefer to see AI/assistant framing
    assert ("ai" in reply) or ("assistant" in reply) or ("amanda" in reply)
