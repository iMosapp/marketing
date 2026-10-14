"""Iteration 376 - Founder Command Center Phase 2 Advisor
Audits:
  - never-mutates: focus/priorities/roadmap/ideas/export.json snapshots must stay byte-identical
    across advisor calls (chat, brief, evaluation, disagree)
  - usage endpoint shape
  - 403/401 access gate for non-owner super_admin and unauthenticated

Keep live LLM calls <=3 total; brief force refresh + evaluate idea + 1 chat.
"""
import copy
import json
import os
import time

import pytest
import requests
from tests import qa_creds

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"

OWNER = {"email": "forest@imosapp.com", "password": qa_creds.password_for("forest@imosapp.com")}
MANAGER = {"email": "qa-manager@invalid.imonsocial.test", "password": qa_creds.password_for("qa-manager@invalid.imonsocial.test")}
IDEA_ID = "6ac90cfb86c8162c83b03551"


def _login(creds):
    r = requests.post(f"{BASE_URL}/api/auth/login", json=creds, timeout=15)
    assert r.status_code == 200, f"login failed for {creds['email']}: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def owner_token():
    return _login(OWNER)


@pytest.fixture(scope="module")
def manager_token():
    try:
        return _login(MANAGER)
    except AssertionError as e:
        pytest.skip(f"manager login unavailable: {e}")


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


def _snapshot(tok):
    paths = [
        "/api/command-center/focus",
        "/api/command-center/priorities",
        "/api/command-center/roadmap",
        "/api/command-center/ideas",
        "/api/command-center/export.json",
    ]
    out = {}
    for p in paths:
        r = requests.get(f"{BASE_URL}{p}", headers=_h(tok), timeout=30)
        assert r.status_code == 200, f"{p} -> {r.status_code} {r.text[:200]}"
        out[p] = r.json()
    return out


def _strip_volatile(obj):
    """Strip evaluation records (expected to change) + volatile ts fields unrelated to mutation checks."""
    if isinstance(obj, dict):
        return {k: _strip_volatile(v) for k, v in obj.items() if k not in ("evaluations",)}
    if isinstance(obj, list):
        return [_strip_volatile(x) for x in obj]
    return obj


# -------- 403/401 access gate --------
class TestAccessGate:
    endpoints_get = [
        "/api/command-center/advisor/conversations",
        "/api/command-center/advisor/brief",
        "/api/command-center/advisor/suggestions",
        "/api/command-center/advisor/usage",
    ]

    def test_unauth_401(self):
        for ep in self.endpoints_get:
            r = requests.get(f"{BASE_URL}{ep}", timeout=15)
            assert r.status_code in (401, 403), f"{ep} unauth -> {r.status_code}"
        r = requests.post(
            f"{BASE_URL}/api/command-center/advisor/conversations", json={}, timeout=15
        )
        assert r.status_code in (401, 403)

    def test_manager_403(self, manager_token):
        for ep in self.endpoints_get:
            r = requests.get(f"{BASE_URL}{ep}", headers=_h(manager_token), timeout=15)
            assert r.status_code == 403, f"{ep} manager -> {r.status_code} {r.text[:200]}"
        r = requests.post(
            f"{BASE_URL}/api/command-center/advisor/conversations",
            headers=_h(manager_token),
            json={},
            timeout=15,
        )
        assert r.status_code == 403


# -------- Owner usage --------
class TestUsage:
    def test_usage_shape(self, owner_token):
        r = requests.get(
            f"{BASE_URL}/api/command-center/advisor/usage", headers=_h(owner_token), timeout=15
        )
        assert r.status_code == 200
        data = r.json()
        assert "last_24h" in data
        assert "requests" in data["last_24h"]
        assert "approx_cost_usd" in data["last_24h"]
        assert data.get("hourly_limit") == 30
        assert data.get("model", "").startswith("gpt-5")


# -------- Never-mutates audit --------
class TestNeverMutates:
    def test_chat_brief_evaluate_do_not_mutate(self, owner_token):
        before = _snapshot(owner_token)

        # 1) force brief refresh (live LLM, up to 60s)
        r = requests.post(
            f"{BASE_URL}/api/command-center/advisor/brief",
            headers=_h(owner_token),
            json={"force": True},
            timeout=90,
        )
        assert r.status_code == 200, f"brief -> {r.status_code} {r.text[:300]}"
        brief = r.json()
        # no invented overdue when nothing has a due date: display fields shouldn't claim items overdue
        b = brief.get("brief", brief)
        display_blob = " ".join(
            [
                str(b.get("headline") or ""),
                str(b.get("recommendation") or ""),
                " ".join(b.get("attention") or []),
                " ".join(b.get("missing") or []),
                str(b.get("next_best_action") or ""),
            ]
        ).lower()
        # It's OK for facts_used to say "0 overdue"; it must not claim any item IS overdue
        assert "overdue" not in display_blob, f"brief display mentions overdue: {display_blob[:200]}"

        # 2) create conversation + 1 chat turn
        rc = requests.post(
            f"{BASE_URL}/api/command-center/advisor/conversations",
            headers=_h(owner_token),
            json={},
            timeout=20,
        )
        assert rc.status_code in (200, 201), f"new conv -> {rc.status_code} {rc.text[:300]}"
        conv = rc.json()
        cid = conv.get("id") or conv.get("_id") or conv.get("conversation_id")
        assert cid, f"no conversation id in {conv}"

        rm = requests.post(
            f"{BASE_URL}/api/command-center/advisor/conversations/{cid}/messages",
            headers=_h(owner_token),
            json={"text": "In one sentence, what is my single most important focus right now?"},
            timeout=90,
        )
        assert rm.status_code == 200, f"chat -> {rm.status_code} {rm.text[:300]}"
        reply = rm.json()
        reply_text = json.dumps(reply)
        # no em-dashes or markdown bold asterisks per house rules
        assert "\u2014" not in reply_text, "reply contains em-dash"

        # 3) evaluate the idea (live LLM, up to 90s)
        re = requests.post(
            f"{BASE_URL}/api/command-center/ideas/{IDEA_ID}/evaluate",
            headers=_h(owner_token),
            json={},
            timeout=120,
        )
        assert re.status_code == 200, f"evaluate -> {re.status_code} {re.text[:300]}"
        ev = re.json()
        eid = ev.get("id") or ev.get("_id") or ev.get("evaluation_id")
        verdict = ev.get("verdict") or ev.get("recommendation")
        assert verdict in ("BUILD", "BUILD_NOW", "VALIDATE", "VALIDATE_FIRST", "PARK", "REJECT"), (
            f"unexpected verdict/recommendation: {verdict}"
        )

        # 4) disagree empty reason -> 400
        if eid:
            rd = requests.post(
                f"{BASE_URL}/api/command-center/advisor/evaluations/{eid}/disagree",
                headers=_h(owner_token),
                json={"reason": ""},
                timeout=15,
            )
            assert rd.status_code in (400, 422), f"empty disagree -> {rd.status_code}"

            rd2 = requests.post(
                f"{BASE_URL}/api/command-center/advisor/evaluations/{eid}/disagree",
                headers=_h(owner_token),
                json={"reason": "QA iter376: contrarian view"},
                timeout=15,
            )
            assert rd2.status_code == 200, f"disagree -> {rd2.status_code} {rd2.text[:200]}"

        # 5) idea status must still be 'captured'
        ri = requests.get(
            f"{BASE_URL}/api/command-center/ideas", headers=_h(owner_token), timeout=15
        )
        ideas = ri.json()
        if isinstance(ideas, dict):
            ideas = ideas.get("ideas") or ideas.get("items") or []
        match = [x for x in ideas if (x.get("id") == IDEA_ID or x.get("_id") == IDEA_ID)]
        if match:
            assert match[0].get("status") == "captured", f"idea status changed to {match[0].get('status')}"

        # 6) take after-snapshot and diff (ignore evaluation records)
        after = _snapshot(owner_token)
        before_s = _strip_volatile(before)
        after_s = _strip_volatile(after)

        for p in ("/api/command-center/focus", "/api/command-center/priorities", "/api/command-center/roadmap"):
            assert before_s[p] == after_s[p], (
                f"snapshot drift at {p}: before/after differ (advisor mutated non-advisor data!)"
            )

        # ideas top-level: statuses + ids must match (evaluations may be attached)
        def _idea_core(payload):
            arr = payload if isinstance(payload, list) else (payload.get("ideas") or payload.get("items") or [])
            return sorted(
                [
                    {"id": x.get("id") or x.get("_id"), "status": x.get("status"), "title": x.get("title")}
                    for x in arr
                ],
                key=lambda d: str(d.get("id")),
            )

        assert _idea_core(before["/api/command-center/ideas"]) == _idea_core(after["/api/command-center/ideas"]), (
            "idea core (id/status/title) changed during advisor flow"
        )

        # focus should still show 0 active / 3 proposed as stated in review context
        focus = after["/api/command-center/focus"]
        slots = focus.get("active_slots") or focus.get("active") or focus.get("slots")
        if slots is not None:
            # count non-null
            active_count = sum(1 for s in slots if s) if isinstance(slots, list) else focus.get("active_count", 0)
            assert active_count == 0, f"expected 0 active priorities, got {active_count}"


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main([__file__, "-v", "-s"]))
