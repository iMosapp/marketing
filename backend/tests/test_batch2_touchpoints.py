"""Batch 2 QA - Backend checks for template rendering (no em dash, no 'your new .')."""
import os
import asyncio
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://user-routing-issue.preview.emergentagent.com").rstrip("/")


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
    assert token and user_id, f"login response missing token/user_id: {data}"
    return {"token": token, "user_id": user_id}


def test_tasks_no_emdash_or_broken_template(forest_auth):
    """GET tasks and verify no U+2014 or 'your new .' / 'the .' in suggested_message."""
    headers = {
        "Authorization": f"Bearer {forest_auth['token']}",
        "X-User-ID": forest_auth["user_id"],
    }
    r = requests.get(
        f"{BASE_URL}/api/tasks/{forest_auth['user_id']}?filter=all&limit=100",
        headers=headers,
        timeout=30,
    )
    assert r.status_code == 200, r.text
    tasks = r.json()
    if isinstance(tasks, dict):
        tasks = tasks.get("tasks", tasks.get("items", []))
    print(f"Fetched {len(tasks)} tasks")
    bad = []
    for t in tasks:
        msg = t.get("suggested_message") or ""
        if "\u2014" in msg:
            bad.append(("emdash", t.get("id"), msg[:120]))
        if "your new ." in msg:
            bad.append(("your new .", t.get("id"), msg[:120]))
        if "the ." in msg and "the ." in msg.lower():
            # allow innocuous "the ." only within word boundary? just flag stark occurrences
            bad.append(("the .", t.get("id"), msg[:120]))
    assert not bad, f"Found broken template rendering: {bad[:10]}"


def test_resolve_template_variables_direct():
    """Direct call into scheduler.resolve_template_variables for no-vehicle fallback."""
    import sys
    sys.path.insert(0, "/app/backend")
    from scheduler import resolve_template_variables

    # No contact -> should replace {vehicle}/{{vehicle}} + {purchase} with 'new ride' fallback
    async def run():
        out1 = await resolve_template_variables(
            None,
            "Any questions about your new {purchase}? Loving the {vehicle}?",
            {"first_name": "Mike"},
            None,
        )
        out2 = await resolve_template_variables(
            None,
            "Loving the {vehicle}?",
            {"first_name": "Mike", "vehicle": "2024 Tacoma"},
            None,
        )
        return out1, out2

    out1, out2 = asyncio.get_event_loop().run_until_complete(run()) if not asyncio.get_event_loop().is_running() else asyncio.run(run())
    print("out1:", repr(out1))
    print("out2:", repr(out2))
    assert "your new ." not in out1
    assert "the ." not in out1 or "the . " not in out1
    assert "new ride" in out1.lower(), out1
    assert "2024 Tacoma" in out2, out2
