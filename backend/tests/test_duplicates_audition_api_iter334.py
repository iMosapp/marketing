"""Iteration 334 API-level tests for Duplicate Cleanup endpoints and GPT-Live shopper audition endpoints.

Covers:
- GET /api/contacts/{uid}/duplicates (as activation-tester) with QA Dup seed
- POST /api/contacts/{uid}/merge (200 / 400 / 404)
- GET /api/shop-clients/live-status (forest 200, activation-tester 401/403)
- GET /api/shop-clients/audition/options (forest 200, activation-tester 401/403)
- POST /api/live-voice/session mode 'shopper'/'lab' -> 403 for tester, 503 for forest (no OPENAI_API_KEY)
- POST /api/live-voice/session mode 'xyz' -> 400 or 503
"""
import asyncio
import os
import pytest
import requests
from bson import ObjectId
from datetime import datetime, timezone, timedelta

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", ".env"))

from routers.database import get_db  # noqa: E402

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")

FOREST = ("forest@imosapp.com", "Admin123!")
TESTER = ("activation-tester@invalid.imonsocial.test", "NewPass123!")


def _login(email, password):
    r = requests.post(f"{BASE}/api/auth/login", json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, r.text
    return r.json()["token"], r.json()["user"]


@pytest.fixture(scope="module")
def forest():
    tok, u = _login(*FOREST)
    return {"h": {"Authorization": f"Bearer {tok}"}, "id": u.get("id") or u.get("_id"), "user": u}


@pytest.fixture(scope="module")
def tester():
    tok, u = _login(*TESTER)
    return {"h": {"Authorization": f"Bearer {tok}"}, "id": u.get("id") or u.get("_id"), "user": u}


# --- seed helpers -----------------------------------------------------------
def _c(uid, first, last, phone="", email="", days_ago=0):
    at = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return {"_id": ObjectId(), "user_id": uid, "first_name": first, "last_name": last, "phone": phone, "email": email,
            "status": "active", "tags": ["QA Dup"], "created_at": at, "updated_at": at, "last_activity_at": at}


async def _reseed(uid):
    db = get_db()
    await db.contacts.delete_many({"user_id": uid, "tags": "QA Dup"})
    rows = [
        _c(uid, "Tod", "Berry", "+15005550401"),
        _c(uid, "Todd", "Berry", "+15005550402", days_ago=30),
        _c(uid, "Sarah", "Same", "+15005550411"),
        _c(uid, "Sarah", "Same", "(500) 555-0411", days_ago=3),
        _c(uid, "Emil", "Twin", "+15005550421", email="twin@invalid.imonsocial.test"),
        _c(uid, "E.", "Twin", "+15005550422", email="Twin@invalid.imonsocial.test"),
        _c(uid, "Mike", "Solo", "+15005550431"),
        _c(uid, "Mike", "Snow", "+15005550432"),
    ]
    await db.contacts.insert_many(rows)
    return rows


async def _wipe(uid):
    db = get_db()
    await db.contacts.delete_many({"user_id": uid, "tags": "QA Dup"})


@pytest.fixture
def seeded(tester):
    rows = asyncio.get_event_loop().run_until_complete(_reseed(tester["id"]))
    yield rows
    asyncio.get_event_loop().run_until_complete(_wipe(tester["id"]))


# --- Duplicate cleanup ------------------------------------------------------
def test_duplicates_list_shape_and_reasons(tester, seeded):
    r = requests.get(f"{BASE}/api/contacts/{tester['id']}/duplicates", headers=tester["h"], timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    dups = data["duplicates"]
    assert isinstance(dups, list) and data["total_groups"] == len(dups)
    # Only QA-Dup groups (Mike Solo/Snow must not appear)
    for s in dups:
        assert s["reason"] in {"phone", "email", "name"}
        assert s["contacts"], "each set has contacts"
        assert s["contacts"] == sorted(
            s["contacts"], key=lambda c: (-(c.get("event_count", 0) + c.get("conversation_count", 0)))
        ) or all(("event_count" in c and "conversation_count" in c) for c in s["contacts"])
        for c in s["contacts"]:
            assert set(["id", "first_name", "last_name", "phone", "email", "event_count", "conversation_count"]).issubset(c.keys())
    by_reason = {s["reason"]: s for s in dups}
    assert set(by_reason) >= {"phone", "email", "name"}
    assert by_reason["phone"]["reason_label"] == "Same phone number"
    assert by_reason["email"]["reason_label"] == "Same email"
    assert by_reason["name"]["reason_label"].startswith("Sounds alike") and "Tod Berry" in by_reason["name"]["reason_label"] and "Todd Berry" in by_reason["name"]["reason_label"]
    # Mike Solo / Mike Snow not grouped
    assert not any("Solo" in s.get("name", "") or "Snow" in s.get("name", "") for s in dups)


def test_merge_success_and_error_paths(tester, seeded):
    # find twin pair via /duplicates
    r = requests.get(f"{BASE}/api/contacts/{tester['id']}/duplicates", headers=tester["h"], timeout=20)
    assert r.status_code == 200
    twin = next(s for s in r.json()["duplicates"] if s["reason"] == "email")
    ids = [c["id"] for c in twin["contacts"]]
    primary, dup = ids[0], ids[1]

    # merge
    ok = requests.post(f"{BASE}/api/contacts/{tester['id']}/merge", headers=tester["h"], json={"primary_id": primary, "duplicate_id": dup}, timeout=20)
    assert ok.status_code == 200, ok.text
    body = ok.json()
    assert body["success"] is True and body["primary_id"] == primary and "records_migrated" in body

    # duplicate now has status merged
    from routers.database import get_db as _gdb
    db = _gdb()
    doc = asyncio.get_event_loop().run_until_complete(db.contacts.find_one({"_id": ObjectId(dup)}))
    assert doc["status"] == "merged"

    # 400 when equal
    bad = requests.post(f"{BASE}/api/contacts/{tester['id']}/merge", headers=tester["h"], json={"primary_id": primary, "duplicate_id": primary}, timeout=20)
    assert bad.status_code == 400, bad.text

    # 400 when missing
    bad2 = requests.post(f"{BASE}/api/contacts/{tester['id']}/merge", headers=tester["h"], json={"primary_id": primary}, timeout=20)
    assert bad2.status_code in (400, 422), bad2.text

    # 404 unknown
    missing = str(ObjectId())
    nf = requests.post(f"{BASE}/api/contacts/{tester['id']}/merge", headers=tester["h"], json={"primary_id": primary, "duplicate_id": missing}, timeout=20)
    assert nf.status_code == 404, nf.text


# --- Shop clients ----------------------------------------------------------
def test_live_status_forest(forest):
    r = requests.get(f"{BASE}/api/shop-clients/live-status", headers=forest["h"], timeout=20)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["on"] is False and d["configured"] is False and d["lab_live"] is True
    assert "OPENAI_API_KEY" in d["reason"]
    assert "clients_on" in d and "clients_off" in d


def test_audition_options_forest(forest):
    r = requests.get(f"{BASE}/api/shop-clients/audition/options", headers=forest["h"], timeout=20)
    assert r.status_code == 200, r.text
    d = r.json()
    ids = [v["id"] for v in d["voices"]]
    first8 = ids[:8]
    expected = {"gleam", "marin", "delta", "meridian", "cinder", "willow", "vesper", "stone"}
    assert set(first8) == expected, first8
    # no Portuguese voices
    for v in d["voices"]:
        assert "portuguese" not in v.get("accent", "").lower()
    assert d["configured"] is False and isinstance(d["reason"], str)


def test_shop_client_endpoints_forbid_tester(tester):
    for path in ("/api/shop-clients/live-status", "/api/shop-clients/audition/options"):
        r = requests.get(f"{BASE}{path}", headers=tester["h"], timeout=20)
        assert r.status_code in (401, 403), (path, r.status_code, r.text)


# --- Live voice session ----------------------------------------------------
def test_shopper_session_tester_forbidden(tester):
    r = requests.post(f"{BASE}/api/live-voice/session", headers=tester["h"],
                      json={"mode": "shopper", "sdp": "v=0 x"}, timeout=20)
    assert r.status_code == 403, r.text


def test_shopper_session_forest_503(forest):
    r = requests.post(f"{BASE}/api/live-voice/session", headers=forest["h"],
                      json={"mode": "shopper", "sdp": "v=0 x"}, timeout=20)
    assert r.status_code == 503, r.text
    assert "OPENAI_API_KEY" in r.text


def test_lab_session_forest_503(forest):
    r = requests.post(f"{BASE}/api/live-voice/session", headers=forest["h"],
                      json={"mode": "lab", "sdp": "v=0 x"}, timeout=20)
    assert r.status_code == 503, r.text
    assert "OPENAI_API_KEY" in r.text


def test_unknown_mode(forest):
    r = requests.post(f"{BASE}/api/live-voice/session", headers=forest["h"],
                      json={"mode": "xyz", "sdp": "v=0 x"}, timeout=20)
    assert r.status_code in (400, 503), r.text
