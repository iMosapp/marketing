"""Read-only, counts-only historical merge assessment (services/merge_assessment.py): it finds a synthetic cross-organization merge,
reports integers only, and writes nothing.

Run: cd /app/backend && set -a && . ./.env && . ../frontend/.env && set +a && python -m pytest tests/test_merge_assessment.py -q
"""
import ast
import asyncio
import json
import os
import re
from datetime import datetime, timezone

import pytest
import requests
from bson import ObjectId
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from routers.auth import hash_password  # noqa: E402
from routers.database import get_db  # noqa: E402
from services import merge_assessment as ma  # noqa: E402
from tests import qa_creds  # noqa: E402

BASE = open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split()[0].rstrip("/")
LOOP = asyncio.new_event_loop()
S: dict = {}
WRITES = {"insert_one", "insert_many", "update_one", "update_many", "replace_one", "delete_one", "delete_many", "bulk_write", "drop",
          "create_index", "create_indexes", "drop_index", "find_one_and_update", "find_one_and_replace", "find_one_and_delete", "rename"}


def run(c):
    return LOOP.run_until_complete(c)


async def _seed():
    db = get_db()
    now = datetime.now(timezone.utc)
    tag = {"qa_merge_assess": True}
    S["orgs"] = [str((await db.organizations.insert_one({"name": f"QA MergeAssess {k}", "created_at": now, **tag})).inserted_id) for k in "XY"]
    S["users"] = [str((await db.users.insert_one({"name": f"QA MergeAssess {k}", "email": f"qa-merge-assess-{k.lower()}@invalid.imonsocial.test", "role": "user",
                                                  "organization_id": o, "password": hash_password("x"), "created_at": now, **tag})).inserted_id)
                  for k, o in zip("XY", S["orgs"])]
    ux, uy = S["users"]
    S["w"] = str((await db.contacts.insert_one({"user_id": uy, "first_name": "Winner", "phone": "+15005550401", "created_at": now, **tag})).inserted_id)
    S["l"] = str((await db.contacts.insert_one({"user_id": ux, "first_name": "Lead (0401)", "phone": "+15005550401", "merged_into": S["w"], "merged_at": now, "created_at": now, **tag})).inserted_id)
    conv = str((await db.conversations.insert_one({"user_id": ux, "contact_id": S["w"], "created_at": now, **tag})).inserted_id)
    await db.messages.insert_one({"conversation_id": conv, "contact_id": S["w"], "user_id": ux, "content": "private text", "created_at": now, **tag})
    await db.voice_notes.insert_one({"contact_id": S["w"], "user_id": ux, "transcript": "private memo", "created_at": now, **tag})


async def _wipe():
    db = get_db()
    for coll in ("organizations", "users", "contacts", "conversations", "messages", "voice_notes"):
        await db[coll].delete_many({"qa_merge_assess": True})


class _SpyColl:
    def __init__(self, coll, seen):
        self._c, self._seen = coll, seen

    def __getattr__(self, name):
        self._seen.add(name)
        return getattr(self._c, name)


class _SpyDB:
    """Records every collection method the scan touches on the real database."""
    def __init__(self, db):
        self._db, self.seen = db, set()

    def __getitem__(self, name):
        return _SpyColl(self._db[name], self.seen)

    def __getattr__(self, name):
        return _SpyColl(self._db[name], self.seen)


@pytest.fixture(scope="module", autouse=True)
def synthetic():
    run(_wipe())
    run(_seed())
    yield
    run(_wipe())


def test_module_never_calls_a_write_method():
    tree = ast.parse(open(ma.__file__).read())
    called = {n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert not (called & WRITES), called & WRITES


def test_read_only_wrapper_refuses_writes():
    ro = ma.ReadOnlyDB(get_db())
    for name in ("insert_one", "update_many", "delete_many", "replace_one", "bulk_write", "find_one_and_update", "drop"):
        with pytest.raises(PermissionError):
            getattr(ro.contacts, name)
    with pytest.raises(PermissionError):
        ro.contacts.aggregate([{"$match": {}}, {"$out": "x"}])
    with pytest.raises(PermissionError):
        ro.contacts.aggregate([{"$merge": {"into": "x"}}])
    with pytest.raises(PermissionError):
        ro.contacts.find({}, None)


def test_finds_the_cross_org_merge_counts_only_and_writes_nothing():
    spy = _SpyDB(get_db())
    out = run(ma.run(spy))
    assert spy.seen and spy.seen <= {"find", "count_documents", "aggregate"}, spy.seen
    assert out["read_only"] and out["counts_only"] and not out["caps_hit"]
    assert out["cross_tenant_merges"] >= 1 and out["merges_by_owner_relation"].get("cross_organization", 0) >= 1
    assert out["cross_tenant_merges_by_kind"].get("startup_consolidation", 0) >= 1
    rows = out["rows_from_loser_owner_on_other_tenant_contact"]
    assert rows["conversations"] >= 1 and rows["messages"] >= 1 and rows["voice_notes"] >= 1 and rows["messages_in_those_conversations"] >= 1
    assert out["conversations_owner_tenant_differs_from_contact_tenant"] >= 1
    blob = json.dumps(out)
    assert not re.search(r"[0-9a-f]{24}", blob) and "@" not in blob and "+1" not in blob and "Winner" not in blob and "private" not in blob


def test_endpoint_is_super_admin_only_and_needs_confirm():
    forest = requests.post(f"{BASE}/api/auth/login", json={"email": "forest@imosapp.com", "password": qa_creds.password_for("forest@imosapp.com")}, timeout=30).json()["token"]
    h = {"Authorization": f"Bearer {forest}"}
    assert requests.get(f"{BASE}/api/admin/contact-merge-assessment", headers=h, timeout=60).status_code == 400
    r = requests.get(f"{BASE}/api/admin/contact-merge-assessment?confirm=COUNTS_ONLY", headers=h, timeout=120)
    assert r.status_code == 200 and r.json()["cross_tenant_merges"] >= 1
    mgr = requests.post(f"{BASE}/api/auth/login", json={"email": "qa-manager@invalid.imonsocial.test", "password": qa_creds.password_for("qa-manager@invalid.imonsocial.test")}, timeout=30).json()["token"]
    assert requests.get(f"{BASE}/api/admin/contact-merge-assessment?confirm=COUNTS_ONLY", headers={"Authorization": f"Bearer {mgr}"}, timeout=60).status_code == 403
    assert requests.get(f"{BASE}/api/admin/contact-merge-assessment?confirm=COUNTS_ONLY", timeout=60).status_code == 401
