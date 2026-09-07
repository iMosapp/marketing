"""Batch 2 QA Retest (iteration 297) - verify em-dash strip, phone greeting sanitize."""
import os
import re
import sys
import asyncio
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")

PHONE_GREETING_RE = re.compile(r"\b(Hi|Hey|Hello)\s+\+?\d[\d\s().-]{6,}\d\b")


@pytest.fixture(scope="module")
def forest_auth():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": "forest@imosapp.com", "password": "Admin123!"},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    token = data.get("access_token") or data.get("token")
    user = data.get("user") or {}
    user_id = user.get("id") or user.get("_id") or data.get("user_id")
    assert token and user_id, data
    return {"token": token, "user_id": user_id}


def test_tasks_no_emdash_no_phone_greeting(forest_auth):
    headers = {
        "Authorization": f"Bearer {forest_auth['token']}",
        "X-User-ID": forest_auth["user_id"],
    }
    r = requests.get(
        f"{BASE_URL}/api/tasks/{forest_auth['user_id']}?filter=all&limit=200",
        headers=headers,
        timeout=30,
    )
    assert r.status_code == 200, r.text
    tasks = r.json()
    if isinstance(tasks, dict):
        tasks = tasks.get("tasks", tasks.get("items", []))
    print(f"Fetched {len(tasks)} tasks")
    bad_emdash = []
    bad_phone = []
    fields = ["suggested_message", "description", "title", "campaign_name"]
    for t in tasks:
        for f in fields:
            val = t.get(f) or ""
            if isinstance(val, str) and "\u2014" in val:
                bad_emdash.append((f, t.get("id"), val[:140]))
        msg = t.get("suggested_message") or ""
        if isinstance(msg, str) and PHONE_GREETING_RE.search(msg):
            bad_phone.append((t.get("id"), msg[:160]))
    assert not bad_emdash, f"em-dash found: {bad_emdash[:8]}"
    assert not bad_phone, f"phone greeting found: {bad_phone[:8]}"


def test_resolve_template_variables_phone_guard():
    sys.path.insert(0, "/app/backend")
    from scheduler import resolve_template_variables

    async def run():
        a = await resolve_template_variables(
            None, "Hi {first_name}!", {"contact_name": "+1 (555) 000-1234"}, None
        )
        b = await resolve_template_variables(
            None, "Hi {first_name}!", {"first_name": "5550001234"}, None
        )
        c = await resolve_template_variables(
            None, "Hi {first_name}!", {"first_name": "Mike"}, None
        )
        return a, b, c

    a, b, c = asyncio.run(run())
    print("a:", repr(a))
    print("b:", repr(b))
    print("c:", repr(c))
    assert a == "Hi there!", a
    assert b == "Hi there!", b
    assert c == "Hi Mike!", c
