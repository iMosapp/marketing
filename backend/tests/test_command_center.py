"""Founder Command Center (Phase 1A-min) against the running server: owner-only access, idempotent seed that never
overwrites founder edits, the three-slot rule under 20 concurrent activations, replace / pause / complete, statement
versions + approval with reason, ideas captured by default, JSON + Markdown export.
Run: cd /app/backend && set -a && . ./.env && set +a && python -m pytest tests/test_command_center.py -q
The test snapshots and restores the five cc_* collections so the founder's real data is untouched."""
import asyncio
import os
from concurrent.futures import ThreadPoolExecutor

import pytest
import requests
from motor.motor_asyncio import AsyncIOMotorClient

from services import command_center as cc
from tests import qa_creds

BASE_URL = [l.split("=", 1)[1].strip() for l in open("/app/frontend/.env") if l.startswith("REACT_APP_BACKEND_URL=")][0].rstrip("/")
API = BASE_URL + "/api"
COLLS = [cc.BLUEPRINT, cc.PRIORITIES, cc.ROADMAP, cc.IDEAS, cc.NOTES]
OTHER_EMAIL = "cc-other-admin@qa.test"


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


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json().get('token') or r.json().get('access_token')}"}


@pytest.fixture(scope="module")
def world():
    """Snapshot the founder's cc_* data, start from an empty slate, restore afterwards. Also a non-owner super admin for the 403 check."""
    async def setup():
        db = _db()
        snap = {c: await db[c].find({}).to_list(5000) for c in COLLS}
        for c in COLLS:
            await db[c].delete_many({})
        from routers.auth import hash_password
        await db.users.delete_many({"email": OTHER_EMAIL})
        await db.users.insert_one({"email": OTHER_EMAIL, "password": hash_password("Other123!"), "name": "Other Admin", "role": "super_admin", "status": "active", "is_owner": False})
        await db.settings.update_one({"_id": "owner_visibility"}, {"$unset": {"visible.command_center": ""}})
        return snap
    snap = _run(setup())
    owner = _login("forest@imosapp.com", qa_creds.password_for("forest@imosapp.com"))
    other = _login(OTHER_EMAIL, "Other123!")
    yield {"owner": owner, "other": other}

    async def teardown():
        db = _db()
        for c in COLLS:
            await db[c].delete_many({})
            if snap[c]:
                await db[c].insert_many(snap[c])
        await db.users.delete_many({"email": OTHER_EMAIL})
    _run(teardown())


def test_owner_only_access(world):
    assert requests.get(f"{API}/command-center/focus", headers=world["other"], timeout=30).status_code == 403
    assert requests.get(f"{API}/command-center/export.json", headers=world["other"], timeout=30).status_code == 403
    assert requests.get(f"{API}/command-center/focus", timeout=30).status_code in (401, 403)
    r = requests.get(f"{API}/command-center/focus", headers=world["owner"], timeout=60)
    assert r.status_code == 200, r.text
    f = r.json()
    assert f["slots"] == 3 and f["active"] == [] and len(f["proposed"]) == 3 and f["objective"]["data"]["title"].startswith("Launch into equipment dealerships")
    assert f["objective"]["status"] == "draft" and f["next_action"]["data"]["state"] == "none"


def test_seed_is_idempotent_and_never_overwrites_edits(world):
    h = world["owner"]
    bp = requests.get(f"{API}/command-center/blueprint", headers=h, timeout=30).json()
    assert set(bp["statements"]) == set(cc.STATEMENTS) and len(bp["pillars"]) == 4 and len(bp["products"]) == 3
    assert all(p["data"]["pricing"]["status"] == "uncommitted" and all(v == "unknown" for v in p["data"]["readiness"].values()) and p["data"]["revenue"] is None for p in bp["products"])
    rm = requests.get(f"{API}/command-center/roadmap", headers=h, timeout=30).json()["phases"]
    assert [p["total"] for p in rm] == [7, 6, 6] and all(it["due"] is None and it["owner"]["name"] for p in rm for it in p["items"])
    # edit the mission, re-seed, the edit survives
    r = requests.put(f"{API}/command-center/blueprint/mission", headers=h, json={"data": {"text": "Edited mission"}, "reason": "test"}, timeout=30)
    assert r.status_code == 200 and r.json()["data"]["text"] == "Edited mission" and r.json()["status"] == "draft"
    assert requests.post(f"{API}/command-center/seed", headers=h, timeout=30).json()["added"] == []
    bp2 = requests.get(f"{API}/command-center/blueprint", headers=h, timeout=30).json()
    assert bp2["statements"]["mission"]["data"]["text"] == "Edited mission" and bp2["statements"]["mission"]["versions"] == 1
    vs = requests.get(f"{API}/command-center/blueprint/mission/versions", headers=h, timeout=30).json()["versions"]
    assert vs[0]["data"]["text"].startswith("Help businesses capture") and vs[0]["reason"] == "test"
    # approval needs a reason
    assert requests.post(f"{API}/command-center/blueprint/mission/approve", headers=h, json={"reason": ""}, timeout=30).status_code == 400
    ap = requests.post(f"{API}/command-center/blueprint/mission/approve", headers=h, json={"reason": "Board agreed"}, timeout=30).json()
    assert ap["status"] == "approved" and ap["approval_reason"] == "Board agreed"
    # a new draft after approval goes back to draft and keeps the approved text in history
    r = requests.put(f"{API}/command-center/blueprint/mission", headers=h, json={"data": {"text": "Edited mission v2"}}, timeout=30).json()
    assert r["status"] == "draft" and len(r["versions"]) == 2 and r["versions"][-1]["status"] == "approved"
    # the focus singleton is not editable through the blueprint endpoint
    assert requests.put(f"{API}/command-center/blueprint/focus", headers=h, json={"data": {"active_priority_ids": ["x"]}}, timeout=30).status_code == 400


def test_three_slot_rule_under_concurrency(world):
    h = world["owner"]
    pri = requests.get(f"{API}/command-center/priorities", headers=h, timeout=30).json()["priorities"]
    # activation needs pillar + purpose
    assert requests.post(f"{API}/command-center/priorities/{pri[0]['id']}/activate", headers=h, timeout=30).status_code == 400
    ids = []
    for i, p in enumerate(pri):
        r = requests.patch(f"{API}/command-center/priorities/{p['id']}", headers=h, json={"pillar": ["capture", "engage", "improve"][i], "purpose": "Pilot revenue"}, timeout=30)
        assert r.status_code == 200
        ids.append(p["id"])
    for _ in range(17):
        r = requests.post(f"{API}/command-center/priorities", headers=h, json={"title": "Shiny new thing", "pillar": "understand", "purpose": "Maybe revenue"}, timeout=30)
        ids.append(r.json()["id"])
    with ThreadPoolExecutor(max_workers=20) as ex:
        results = list(ex.map(lambda pid: requests.post(f"{API}/command-center/priorities/{pid}/activate", headers=h, timeout=60).status_code, ids))
    assert results.count(200) == 3 and results.count(409) == 17, results
    f = requests.get(f"{API}/command-center/focus", headers=h, timeout=30).json()
    assert len(f["active"]) == 3 and sorted(p["slot"] for p in f["active"]) == [1, 2, 3]
    # a fourth, directly: 409 with the three active ones listed
    extra = next(i for i in ids if i not in {p["id"] for p in f["active"]})
    r = requests.post(f"{API}/command-center/priorities/{extra}/activate", headers=h, timeout=30)
    assert r.status_code == 409 and len(r.json()["detail"]["active"]) == 3
    # replace needs a reason and an active target; then still exactly three
    victim = f["active"][0]["id"]
    assert requests.post(f"{API}/command-center/priorities/{extra}/replace", headers=h, json={"replace_id": victim, "reason": ""}, timeout=30).status_code == 400
    r = requests.post(f"{API}/command-center/priorities/{extra}/replace", headers=h, json={"replace_id": victim, "reason": "Pilot moved up"}, timeout=30)
    assert r.status_code == 200 and r.json()["status"] == "active"
    pri = {p["id"]: p for p in requests.get(f"{API}/command-center/priorities", headers=h, timeout=30).json()["priorities"]}
    assert pri[victim]["status"] == "replaced" and pri[victim]["replaced_by"] == extra and sum(1 for p in pri.values() if p["slot"]) == 3
    # pause frees a slot, complete frees a slot and records a win
    active = [p for p in pri.values() if p["slot"]]
    assert requests.post(f"{API}/command-center/priorities/{active[0]['id']}/pause", headers=h, timeout=30).json()["status"] == "paused"
    assert requests.post(f"{API}/command-center/priorities/{active[1]['id']}/complete", headers=h, timeout=30).json()["status"] == "completed"
    f = requests.get(f"{API}/command-center/focus", headers=h, timeout=30).json()
    assert len(f["active"]) == 1 and len(f["paused"]) == 1 and any(w["title"].startswith("Completed:") for w in f["wins"])
    # a paused one comes back when there is room
    assert requests.post(f"{API}/command-center/priorities/{active[0]['id']}/activate", headers=h, timeout=30).json()["status"] == "active"
    # finished ones never come back
    assert requests.post(f"{API}/command-center/priorities/{active[1]['id']}/activate", headers=h, timeout=30).status_code == 400
    # parking a proposed one removes it (the idea carries it); an active one can never be deleted
    proposed = next(p for p in pri.values() if p["status"] == "proposed")
    assert requests.delete(f"{API}/command-center/priorities/{active[0]['id']}", headers=h, timeout=30).status_code == 400
    assert requests.delete(f"{API}/command-center/priorities/{proposed['id']}", headers=h, timeout=30).status_code == 200
    assert proposed["id"] not in {p["id"] for p in requests.get(f"{API}/command-center/priorities", headers=h, timeout=30).json()["priorities"]}


def test_next_action_notes_ideas_and_export(world):
    h = world["owner"]
    na = requests.put(f"{API}/command-center/next-action", headers=h, json={"text": "Send the one-pagers to TracTru", "why": "Unblocks the pilot"}, timeout=30).json()
    assert na["data"]["state"] == "set" and na["data"]["text"].startswith("Send")
    w = requests.post(f"{API}/command-center/notes", headers=h, json={"kind": "waiting", "title": "Pilot dealer list", "party": "TracTru"}, timeout=30).json()
    assert w["status"] == "open"
    requests.post(f"{API}/command-center/notes", headers=h, json={"kind": "win", "title": "Journey campaigns shipped"}, timeout=30)
    assert requests.post(f"{API}/command-center/notes", headers=h, json={"kind": "bogus", "title": "x"}, timeout=30).status_code == 400
    idea = requests.post(f"{API}/command-center/ideas", headers=h, json={"title": "DNI for equipment dealers", "source": "voice"}, timeout=30).json()
    assert idea["status"] == "captured" and idea["source"] == "voice"
    assert requests.post(f"{API}/command-center/ideas", headers=h, json={"title": "   "}, timeout=30).status_code == 400
    moved = requests.patch(f"{API}/command-center/ideas/{idea['id']}", headers=h, json={"status": "parked", "pillar": "capture"}, timeout=30).json()
    assert moved["status"] == "parked" and moved["reviewed_at"]
    lst = requests.get(f"{API}/command-center/ideas", headers=h, params={"view": "new_week"}, timeout=30).json()
    assert lst["counts"]["parked"] >= 1 and any(i["id"] == idea["id"] for i in lst["ideas"])
    # an idea never created a roadmap item or a priority
    rm = requests.get(f"{API}/command-center/roadmap", headers=h, timeout=30).json()["phases"]
    assert sum(p["total"] for p in rm) == 19
    requests.patch(f"{API}/command-center/roadmap/{rm[0]['items'][0]['id']}", headers=h, json={"status": "done"}, timeout=30)
    rm = requests.get(f"{API}/command-center/roadmap", headers=h, timeout=30).json()["phases"]
    assert rm[0]["done"] == 1 and rm[0]["pct"] == 14
    f = requests.get(f"{API}/command-center/focus", headers=h, timeout=30).json()
    assert f["next_action"]["data"]["text"].startswith("Send") and len(f["waiting"]) == 1 and f["ideas_new_week"] >= 1
    ej = requests.get(f"{API}/command-center/export.json", headers=h, timeout=30).json()
    assert {"blueprint", "priorities", "roadmap", "ideas", "notes"} <= set(ej) and any(b["key"] == "focus" for b in ej["blueprint"])
    md = requests.get(f"{API}/command-center/export.md", headers=h, timeout=30).text
    for needle in ("# I'm On Social", "## North Star", "## The One Big Thing", "## Strategic Priorities", "## Four Pillars", "## Commercial Products", "## 90-Day Roadmap", "## Idea Vault", "DNI for equipment dealers", "Pricing: uncommitted", "Send the one-pagers"):
        assert needle in md, needle
