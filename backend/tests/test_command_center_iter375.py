"""Iteration 375 - Phase 1A-min Command Center spot checks against the running server.
Covers access control, 4th-activation 409, statement approve requires reason, exports,
voice/transcribe liveness, ideas never spawn tasks/roadmap/priorities.
Leaves state clean (deletes QA ideas/notes it creates, resets any priorities it activates)."""
import asyncio
import io
import os
import wave

import pytest
import requests
from motor.motor_asyncio import AsyncIOMotorClient
from tests import qa_creds

BASE = [l.split("=",1)[1].strip() for l in open("/app/frontend/.env") if l.startswith("REACT_APP_BACKEND_URL=")][0].rstrip("/")
API = BASE + "/api"
OTHER_EMAIL = "cc-qa-other@qa.test"
OWNER = ("forest@imosapp.com", qa_creds.password_for("forest@imosapp.com"))


def _db():
    return AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


def _run(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.run_until_complete(asyncio.sleep(0.05))
        loop.close()


CC_COLLS = ["cc_blueprint", "cc_priorities", "cc_roadmap", "cc_ideas", "cc_notes"]


@pytest.fixture(scope="module", autouse=True)
def cc_guard():
    """Snapshot the founder's cc_* data before the module and put it back afterwards (the 409 test leaves 3 active)."""
    async def save():
        db = _db()
        return {c: await db[c].find({}).to_list(5000) for c in CC_COLLS}
    snap = _run(save())
    yield

    async def restore():
        db = _db()
        for c in CC_COLLS:
            await db[c].delete_many({})
            if snap[c]:
                await db[c].insert_many(snap[c])
    _run(restore())


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    r.raise_for_status()
    j = r.json()
    return {"Authorization": f"Bearer {j.get('token') or j.get('access_token')}"}


@pytest.fixture(scope="module")
def owner_h():
    return _login(*OWNER)


@pytest.fixture(scope="module")
def other_h():
    async def setup():
        db = _db()
        from routers.auth import hash_password
        await db.users.delete_many({"email": OTHER_EMAIL})
        await db.users.insert_one({"email": OTHER_EMAIL, "password": hash_password("Other123!"), "name": "Other Admin",
                                   "role": "super_admin", "status": "active", "is_owner": False})
    _run(setup())
    try:
        yield _login(OTHER_EMAIL, "Other123!")
    finally:
        async def rm():
            await _db().users.delete_many({"email": OTHER_EMAIL})
        _run(rm())


def test_access_control_owner_200(owner_h):
    assert requests.get(f"{API}/command-center/focus", headers=owner_h, timeout=30).status_code == 200


def test_access_control_unauth(owner_h):
    for path in ["focus", "blueprint", "priorities", "roadmap", "ideas", "notes", "export.json", "export.md"]:
        r = requests.get(f"{API}/command-center/{path}", timeout=30)
        assert r.status_code in (401, 403), (path, r.status_code)


def test_access_control_other_super_admin_403(other_h):
    for path in ["focus", "blueprint", "priorities", "roadmap", "ideas", "notes", "export.json", "export.md"]:
        r = requests.get(f"{API}/command-center/{path}", headers=other_h, timeout=30)
        assert r.status_code == 403, (path, r.status_code, r.text[:200])


def test_statement_approve_requires_reason(owner_h):
    r = requests.post(f"{API}/command-center/blueprint/mission/approve",
                      headers=owner_h, json={"reason": ""}, timeout=30)
    assert r.status_code in (400, 422), r.text


def test_fourth_activation_returns_409_with_three_active(owner_h):
    """Activate 3 proposed, create a 4th, expect 409 with detail.active length 3. Leave 3 active at the end."""
    pri = requests.get(f"{API}/command-center/priorities", headers=owner_h, timeout=30).json()["priorities"]
    proposed = [p for p in pri if p["status"] == "proposed" and not p.get("slot")]
    active_now = [p for p in pri if p["status"] == "active"]
    activated_here = []
    pillars = ["capture", "engage", "improve", "understand"]
    i = 0
    # top up until 3 active
    while len(active_now) + len(activated_here) < 3 and i < len(proposed):
        pid = proposed[i]["id"]
        requests.patch(f"{API}/command-center/priorities/{pid}", headers=owner_h,
                       json={"pillar": pillars[i % 4], "purpose": "QA activation"}, timeout=30)
        r = requests.post(f"{API}/command-center/priorities/{pid}/activate", headers=owner_h, timeout=30)
        if r.status_code == 200:
            activated_here.append(pid)
        i += 1
    f = requests.get(f"{API}/command-center/focus", headers=owner_h, timeout=30).json()
    assert len(f["active"]) == 3
    # create a 4th
    r = requests.post(f"{API}/command-center/priorities", headers=owner_h,
                      json={"title": "QA iter375 fourth", "pillar": "understand", "purpose": "test 409"}, timeout=30)
    fourth = r.json()["id"]
    r = requests.post(f"{API}/command-center/priorities/{fourth}/activate", headers=owner_h, timeout=30)
    assert r.status_code == 409
    body = r.json()
    assert "detail" in body and "active" in body["detail"] and len(body["detail"]["active"]) == 3
    # the 4th remained proposed
    all_pri = requests.get(f"{API}/command-center/priorities", headers=owner_h, timeout=30).json()["priorities"]
    assert next(p for p in all_pri if p["id"] == fourth)["status"] == "proposed"
    # cleanup the 4th via DB (no delete endpoint in 1A-min; mark rejected status)
    async def rm():
        from services import command_center as cc
        from bson import ObjectId
        await _db()[cc.PRIORITIES].delete_one({"_id": ObjectId(fourth)})
    _run(rm())


def test_idea_capture_does_not_create_task_or_roadmap_or_priority(owner_h):
    async def counts():
        db = _db()
        from services import command_center as cc
        return (await db.tasks.count_documents({}),
                await db[cc.ROADMAP].count_documents({}),
                await db[cc.PRIORITIES].count_documents({"status": {"$ne": "rejected"}}))
    t0, r0, p0 = _run(counts())
    r = requests.post(f"{API}/command-center/ideas", headers=owner_h,
                      json={"title": "QA iter375 idea", "source": "text"}, timeout=30)
    assert r.status_code == 200
    iid = r.json()["id"]
    t1, r1, p1 = _run(counts())
    assert t1 == t0 and r1 == r0 and p1 == p0
    # cleanup
    async def rm():
        from services import command_center as cc
        from bson import ObjectId
        await _db()[cc.IDEAS].delete_one({"_id": ObjectId(iid)})
    _run(rm())


def test_exports_contain_expected_keys(owner_h):
    ej = requests.get(f"{API}/command-center/export.json", headers=owner_h, timeout=30).json()
    for k in ("blueprint", "priorities", "roadmap", "ideas", "notes"):
        assert k in ej, k
    md = requests.get(f"{API}/command-center/export.md", headers=owner_h, timeout=30)
    assert md.status_code == 200
    text = md.text
    for needle in ("# I'm On Social", "## North Star", "## Strategic Priorities", "## 90-Day Roadmap", "## Idea Vault"):
        assert needle in text, needle


def test_exports_forbidden_for_other_admin(other_h):
    assert requests.get(f"{API}/command-center/export.json", headers=other_h, timeout=30).status_code == 403
    assert requests.get(f"{API}/command-center/export.md", headers=other_h, timeout=30).status_code == 403


def test_voice_transcribe_endpoint_alive(owner_h):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
        w.writeframes(b"\x00\x00" * 16000)  # 1 s silence
    buf.seek(0)
    r = requests.post(f"{API}/voice/transcribe", headers=owner_h,
                      files={"file": ("silence.wav", buf.getvalue(), "audio/wav")}, timeout=60)
    assert r.status_code == 200, r.text[:300]
