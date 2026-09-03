"""Shared Internet Leads Queue - backend tests (iteration 294).

Covers: /api/leads/queue/{uid}/summary, /{uid}, /{uid}/reps, reassign, release,
/api/lead-sources/claim/{conv}, workflow queue timers, and enforce_user_ownership.
"""
import os
import pytest
import requests
from dotenv import dotenv_values

fe = dotenv_values("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or fe.get("REACT_APP_BACKEND_URL")).rstrip("/")

FOREST_ID = "69a0b7095fddcede09591667"
SOURCE_ID = "69a787ca70ae63ea0ac69251"
REP_ID = "69a53059f2b9e0be44378d69"
REP_NAME = "Test User d954485f A"


def _login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=45)
    assert r.status_code == 200, f"login {email} -> {r.status_code} {r.text[:300]}"
    d = r.json()
    tok = d.get("token") or d.get("access_token")
    assert tok, f"no token in login response: {list(d.keys())}"
    uid = str((d.get("user") or {}).get("id") or (d.get("user") or {}).get("_id") or "")
    return tok, uid


@pytest.fixture(scope="session")
def forest():
    tok, uid = _login("forest@imosapp.com", "Admin123!")
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
    return {"s": s, "id": uid or FOREST_ID, "token": tok}


@pytest.fixture(scope="session")
def plain():
    tok, uid = _login("mjeast1985@gmail.com", "NavyBean1!")
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
    return {"s": s, "id": uid, "token": tok}


def _queue(forest):
    r = forest["s"].get(f"{BASE_URL}/api/leads/queue/{forest['id']}", timeout=45)
    assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
    return r.json()


def _find(items, name):
    return next((i for i in items if name.lower() in (i.get("contact_name") or "").lower()), None)


# ── queue summary ─────────────────────────────────────────────────────────────
class TestSummary:
    def test_summary_forest(self, forest):
        r = forest["s"].get(f"{BASE_URL}/api/leads/queue/{forest['id']}/summary", timeout=45)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d["visible"] is True
        assert d["waiting"] >= 3, d
        assert d["oldest"] and set(["conversation_id", "contact_name", "waiting_seconds", "heat"]) <= set(d["oldest"])
        assert isinstance(d["names"], list) and len(d["names"]) >= 1
        assert isinstance(d["red"], int)
        assert d["mine_waiting"] >= 1, d
        assert d["mine_oldest"] is not None
        assert isinstance(d["mine_names"], list)
        assert d["heat"] in ("green", "amber", "red"), d["heat"]
        assert "_id" not in d

    def test_summary_plain_user_not_visible(self, plain):
        r = plain["s"].get(f"{BASE_URL}/api/leads/queue/{plain['id']}/summary", timeout=45)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d["visible"] is False
        assert d["mine_waiting"] == 0
        assert d["waiting"] == 0


# ── full queue ────────────────────────────────────────────────────────────────
class TestQueue:
    def test_queue_shape_and_seeded_leads(self, forest):
        d = _queue(forest)
        assert d["is_manager"] is True
        assert SOURCE_ID in d["can_claim_source_ids"], d["can_claim_source_ids"]
        names = [i["contact_name"] for i in d["unclaimed"]]
        for n in ("Queue Alpha", "Queue Bravo", "Queue Charlie"):
            assert any(n in x for x in names), f"{n} missing from unclaimed: {names}"
        waits = [i["waiting_seconds"] or 0 for i in d["unclaimed"]]
        assert waits == sorted(waits, reverse=True), f"unclaimed not sorted longest-wait-first: {waits}"
        delta = _find(d["mine"], "Mine Delta")
        echo = _find(d["mine"], "Mine Echo")
        assert delta, [i["contact_name"] for i in d["mine"]]
        assert delta["waiting_seconds"] is not None and delta["heat"] == "red", delta
        assert echo, "Mine Echo missing"
        assert echo["waiting_seconds"] is None, echo
        assert echo.get("first_reply_seconds") is not None and 60 <= echo["first_reply_seconds"] <= 200, echo
        assert d["counts"]["unclaimed"] == len(d["unclaimed"])
        assert d["counts"]["mine"] == len(d["mine"])
        assert d["counts"]["claimed"] == len(d["claimed"])

    def test_reps(self, forest):
        r = forest["s"].get(f"{BASE_URL}/api/leads/queue/{forest['id']}/reps", timeout=45)
        assert r.status_code == 200, r.text[:300]
        reps = r.json()["reps"]
        assert reps and all({"user_id", "name", "on_shift", "open_leads"} <= set(x) for x in reps)
        target = next((x for x in reps if x["user_id"] == REP_ID), None)
        assert target, f"{REP_ID} not in reps"
        assert target["name"] == REP_NAME, target["name"]


# ── security ──────────────────────────────────────────────────────────────────
class TestSecurity:
    def test_cross_user_summary_forbidden(self, plain):
        r = plain["s"].get(f"{BASE_URL}/api/leads/queue/{FOREST_ID}/summary", timeout=45)
        assert r.status_code == 403, f"expected 403 got {r.status_code} {r.text[:200]}"

    def test_no_token(self):
        r = requests.get(f"{BASE_URL}/api/leads/queue/{FOREST_ID}/summary", timeout=45)
        assert r.status_code in (401, 403), r.status_code

    def test_reps_managers_only(self, plain):
        r = plain["s"].get(f"{BASE_URL}/api/leads/queue/{plain['id']}/reps", timeout=45)
        assert r.status_code == 403, r.status_code
        assert "manager" in r.json().get("detail", "").lower()

    def test_claim_not_on_workflow(self, forest, plain):
        conv = _find(_queue(forest)["unclaimed"], "Queue Charlie")
        assert conv, "Queue Charlie not unclaimed"
        r = plain["s"].post(
            f"{BASE_URL}/api/lead-sources/claim/{conv['id']}?user_id={plain['id']}", timeout=45)
        assert r.status_code == 403, f"{r.status_code} {r.text[:200]}"
        assert "not on the" in r.json().get("detail", "").lower(), r.text[:200]
        # still unclaimed
        assert _find(_queue(forest)["unclaimed"], "Queue Charlie")


# ── reassign ──────────────────────────────────────────────────────────────────
class TestReassign:
    def test_reassign_and_restore(self, forest):
        delta = _find(_queue(forest)["mine"], "Mine Delta")
        assert delta, "Mine Delta not in mine"
        cid = delta["id"]
        r = forest["s"].post(f"{BASE_URL}/api/leads/queue/{forest['id']}/reassign/{cid}",
                             json={"to_user_id": REP_ID}, timeout=60)
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
        d = r.json()
        assert d["success"] is True
        assert d["claimed_by"] == REP_ID
        assert d["claimed_by_name"] == REP_NAME, d

        q = _queue(forest)
        assert _find(q["mine"], "Mine Delta") is None, "still in mine after reassign"
        moved = _find(q["claimed"], "Mine Delta")
        assert moved, "not in claimed after reassign"
        assert moved.get("claimed_by_name") == REP_NAME, moved.get("claimed_by_name")

        th = forest["s"].get(f"{BASE_URL}/api/messages/thread/{cid}?user_id={forest['id']}", timeout=60)
        assert th.status_code == 200, th.text[:200]
        body = th.json()
        msgs = body if isinstance(body, list) else (body.get("messages") or [])
        sys_msgs = [m.get("content", "") for m in msgs]
        assert any("Reassigned from" in c and "Test User" in c for c in sys_msgs), sys_msgs[-5:]

        # restore
        back = forest["s"].post(f"{BASE_URL}/api/leads/queue/{forest['id']}/reassign/{cid}",
                                json={"to_user_id": FOREST_ID}, timeout=60)
        assert back.status_code == 200, back.text[:300]
        assert _find(_queue(forest)["mine"], "Mine Delta"), "restore to forest failed"


# ── release + reclaim ─────────────────────────────────────────────────────────
class TestRelease:
    def test_release_mine_echo_and_reclaim(self, forest):
        echo = _find(_queue(forest)["mine"], "Mine Echo")
        assert echo, "Mine Echo not in mine"
        cid = echo["id"]
        r = forest["s"].post(f"{BASE_URL}/api/leads/queue/{forest['id']}/release/{cid}", timeout=60)
        assert r.status_code == 200, r.text[:300]
        assert r.json()["success"] is True and r.json()["released"] is True

        q = _queue(forest)
        u = _find(q["unclaimed"], "Mine Echo")
        assert u, "Mine Echo not in unclaimed after release"
        assert u["claimed"] is False

        again = forest["s"].post(f"{BASE_URL}/api/leads/queue/{forest['id']}/release/{cid}", timeout=60)
        assert again.status_code == 400, again.status_code
        assert "already in the queue" in again.json().get("detail", ""), again.text[:200]

        rc = forest["s"].post(f"{BASE_URL}/api/lead-sources/claim/{cid}?user_id={forest['id']}", timeout=60)
        assert rc.status_code == 200, f"reclaim failed {rc.status_code} {rc.text[:300]}"
        assert _find(_queue(forest)["mine"], "Mine Echo"), "Mine Echo not back in mine"

    def test_claim_alpha_then_release(self, forest):
        alpha = _find(_queue(forest)["unclaimed"], "Queue Alpha")
        assert alpha, "Queue Alpha not unclaimed"
        cid = alpha["id"]
        r = forest["s"].post(f"{BASE_URL}/api/lead-sources/claim/{cid}?user_id={forest['id']}", timeout=60)
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
        dup = forest["s"].post(f"{BASE_URL}/api/lead-sources/claim/{cid}?user_id={forest['id']}", timeout=60)
        assert dup.status_code == 400, dup.status_code
        assert "already claimed" in dup.json().get("detail", "").lower(), dup.text[:200]
        assert _find(_queue(forest)["mine"], "Queue Alpha"), "Alpha not in mine"

        rel = forest["s"].post(f"{BASE_URL}/api/leads/queue/{forest['id']}/release/{cid}", timeout=60)
        assert rel.status_code == 200, rel.text[:300]
        assert _find(_queue(forest)["unclaimed"], "Queue Alpha"), "Alpha not restored to unclaimed"


# ── workflow queue timers ─────────────────────────────────────────────────────
class TestWorkflowTimers:
    def test_timers_save_validate_restore(self, forest):
        s = forest["s"]
        g = s.get(f"{BASE_URL}/api/lead-sources/{SOURCE_ID}/workflow", timeout=45)
        assert g.status_code == 200, g.text[:300]
        base = g.json()
        cfg = base.get("workflow") if isinstance(base.get("workflow"), dict) else base
        assert isinstance(cfg, dict)
        payload = {k: v for k, v in cfg.items() if k not in ("_id", "id", "updated_at", "created_at")}
        payload.update({"timer_green_minutes": 7, "timer_amber_minutes": 20,
                        "returning_alert_minutes": 15, "returning_release_minutes": 45, "digest_hour": 19})
        p = s.put(f"{BASE_URL}/api/lead-sources/{SOURCE_ID}/workflow", json=payload, timeout=60)
        assert p.status_code == 200, f"{p.status_code} {p.text[:400]}"

        g2 = s.get(f"{BASE_URL}/api/lead-sources/{SOURCE_ID}/workflow", timeout=45).json()
        c2 = g2.get("workflow") if isinstance(g2.get("workflow"), dict) else g2
        assert c2["timer_green_minutes"] == 7, c2
        assert c2["timer_amber_minutes"] == 20
        assert c2["returning_alert_minutes"] == 15
        assert c2["returning_release_minutes"] == 45
        assert c2["digest_hour"] == 19

        bad = s.put(f"{BASE_URL}/api/lead-sources/{SOURCE_ID}/workflow",
                    json={**payload, "timer_green_minutes": 20, "timer_amber_minutes": 10}, timeout=60)
        assert bad.status_code == 400, bad.status_code
        assert "Amber must be later than green" in bad.text, bad.text[:200]

        rest = s.put(f"{BASE_URL}/api/lead-sources/{SOURCE_ID}/workflow",
                     json={**payload, "timer_green_minutes": 5, "timer_amber_minutes": 15,
                           "returning_alert_minutes": 10, "returning_release_minutes": 30, "digest_hour": 18},
                     timeout=60)
        assert rest.status_code == 200, rest.text[:300]
        g3 = s.get(f"{BASE_URL}/api/lead-sources/{SOURCE_ID}/workflow", timeout=45).json()
        c3 = g3.get("workflow") if isinstance(g3.get("workflow"), dict) else g3
        assert [c3["timer_green_minutes"], c3["timer_amber_minutes"], c3["returning_alert_minutes"],
                c3["returning_release_minutes"], c3["digest_hour"]] == [5, 15, 10, 30, 18], c3
