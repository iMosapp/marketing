"""Public API v1: hashed store keys, tenant scoping, upsert/dedupe, notes append, tasks, webhooks + the change-feed outbox."""
import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from bson import ObjectId
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
from routers.database import get_db  # noqa: E402
from services import webhook_outbox as ob  # noqa: E402

pytestmark = pytest.mark.asyncio
API = open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split("\n")[0].strip()
STORE = "69a0b7095fddcede09591668"  # Forest's store; qa-manager@invalid.imonsocial.test is its store_manager
TAG = "QA PublicAPI"


async def _key(db, store_id=STORE, scopes=("read", "write")):
    raw = "imos_test_" + secrets.token_urlsafe(16)
    await db.api_keys.insert_one({"store_id": store_id, "name": "pytest", "key_hash": hashlib.sha256(raw.encode()).hexdigest(), "key_prefix": raw[:8],
                                  "scopes": list(scopes), "created_at": datetime.now(timezone.utc), "expires_at": None, "active": True, "request_count": 0, "qa": TAG})
    return raw


async def _wipe(db):
    await db.api_keys.delete_many({"qa": TAG})
    await db.contacts.delete_many({"tags": TAG})
    await db.contacts.delete_many({"external_ids.qa_crm": {"$exists": True}})
    await db.tasks.delete_many({"source": "api", "title": {"$regex": "^QA PublicAPI"}})
    await db.webhook_subscriptions.delete_many({"description": {"$regex": "^QA PublicAPI"}})
    await db.contact_events.delete_many({"description": {"$regex": "QA PublicAPI"}})


def _h(key):
    return {"X-API-Key": key, "Content-Type": "application/json"}


async def test_key_auth_and_me():
    db = get_db()
    key = await _key(db)
    try:
        async with httpx.AsyncClient(base_url=API, timeout=30) as c:
            assert (await c.get("/api/v1/me")).status_code == 401
            assert (await c.get("/api/v1/me", headers=_h("imos_bogus"))).status_code == 401
            me = await c.get("/api/v1/me", headers=_h(key))
            assert me.status_code == 200, me.text
            body = me.json()
            assert body["store"]["id"] == STORE and body["users_visible"] >= 1 and "write" in body["scopes"], body
            # revoked key is rejected
            await db.api_keys.update_one({"key_hash": hashlib.sha256(key.encode()).hexdigest()}, {"$set": {"active": False}})
            assert (await c.get("/api/v1/me", headers=_h(key))).status_code == 401
    finally:
        await _wipe(db)


async def test_tenant_scoping_and_upsert():
    db = get_db()
    key = await _key(db)
    other_store_contact = {"_id": ObjectId(), "user_id": str(ObjectId()), "store_id": str(ObjectId()), "first_name": "Other", "last_name": "Tenant",
                           "phone": "+15005550801", "status": "active", "tags": [TAG], "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc)}
    await db.contacts.insert_one(other_store_contact)
    try:
        async with httpx.AsyncClient(base_url=API, timeout=30) as c:
            # another store's contact is invisible by id and by phone
            assert (await c.get(f"/api/v1/contacts/{other_store_contact['_id']}", headers=_h(key))).status_code == 404
            r = await c.get("/api/v1/contacts", params={"phone": "5005550801"}, headers=_h(key))
            assert r.status_code == 200 and r.json()["total"] == 0, r.text
            # create
            r = await c.post("/api/v1/contacts", headers=_h(key), json={"first_name": "Quinn", "last_name": "QA-Api", "phone": "(500) 555-0802", "email": "quinn.qa@example.com",
                                                                        "tags": [TAG, "hot"], "source": "qa_crm", "external_ids": {"qa_crm": "CRM-1"}, "vehicle_interest": "2024 Tahoe"})
            assert r.status_code == 200 and r.json()["created"] is True, r.text
            cid = r.json()["id"]
            got = (await c.get(f"/api/v1/contacts/{cid}", headers=_h(key))).json()
            assert got["phone"] == "+15005550802" and got["external_ids"] == {"qa_crm": "CRM-1"} and got["store_id"] == STORE and got["user_id"], got
            # same person again (different phone format, same external id) -> update, not duplicate
            r = await c.post("/api/v1/contacts", headers=_h(key), json={"phone": "500-555-0802", "external_ids": {"qa_crm": "CRM-1"}, "tags": ["financing"], "notes": "Wants payments under 600"})
            assert r.status_code == 200 and r.json()["created"] is False and r.json()["id"] == cid, r.text
            # phone-only match also dedupes
            r = await c.post("/api/v1/contacts", headers=_h(key), json={"first_name": "Quinn", "phone": "+1 500 555 0802"})
            assert r.json()["created"] is False and r.json()["id"] == cid, r.text
            got = (await c.get(f"/api/v1/contacts/{cid}", headers=_h(key))).json()
            assert set(got["tags"]) >= {TAG, "hot", "financing"} and "under 600" in got["notes"], got
            # lookup by external id + incremental sync param
            r = await c.get("/api/v1/contacts", params={"external_id": "CRM-1"}, headers=_h(key))
            assert r.json()["total"] == 1 and r.json()["contacts"][0]["id"] == cid, r.text
            r = await c.get("/api/v1/contacts", params={"updated_since": (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(), "tag": TAG}, headers=_h(key))
            assert any(x["id"] == cid for x in r.json()["contacts"]), r.text
            assert (await c.get("/api/v1/contacts", params={"updated_since": "yesterday"}, headers=_h(key))).status_code == 400
            # notes append (never overwrite) + timeline event + purchases + tasks
            r = await c.post(f"/api/v1/contacts/{cid}/notes", headers=_h(key), json={"note": "QA PublicAPI note from CRM", "source": "QA CRM"})
            assert r.status_code == 200 and "under 600" in r.json()["notes"] and "via QA CRM] QA PublicAPI note from CRM" in r.json()["notes"], r.text
            ev = (await c.get(f"/api/v1/contacts/{cid}/events", headers=_h(key))).json()["events"]
            assert any(e["event_type"] == "note_added" for e in ev), ev
            r = await c.post(f"/api/v1/contacts/{cid}/purchases", headers=_h(key), json={"title": "2024 Chevy Tahoe", "date": "2026-09-01", "notes": "QA PublicAPI sale"})
            assert r.status_code == 200 and r.json()["purchase"]["title"] == "2024 Chevy Tahoe", r.text
            got = (await c.get(f"/api/v1/contacts/{cid}/purchases", headers=_h(key))).json()
            assert got["purchases"] and "sold" in (await c.get(f"/api/v1/contacts/{cid}", headers=_h(key))).json()["tags"], got
            r = await c.post("/api/v1/tasks", headers=_h(key), json={"contact_id": cid, "title": "QA PublicAPI follow up", "due_date": "2026-09-20T15:00:00Z", "idempotency_key": "qa-task-1"})
            assert r.status_code == 200 and r.json()["created"] is True, r.text
            r2 = await c.post("/api/v1/tasks", headers=_h(key), json={"contact_id": cid, "title": "QA PublicAPI follow up", "idempotency_key": "qa-task-1"})
            assert r2.json()["created"] is False and r2.json()["id"] == r.json()["id"]
            r = await c.get("/api/v1/tasks", params={"contact_id": cid}, headers=_h(key))
            assert r.json()["total"] >= 1
            # messages listing works (empty) and users/stores are scoped
            assert (await c.get(f"/api/v1/contacts/{cid}/messages", headers=_h(key))).status_code == 200
            users = (await c.get("/api/v1/users", headers=_h(key))).json()["users"]
            assert users and all(u.get("store_id") == STORE for u in users) and all("password" not in u for u in users), users[:2]
            stores = (await c.get("/api/v1/stores", headers=_h(key))).json()["stores"]
            assert [s["id"] for s in stores] == [STORE], stores
            # soft delete hides it
            assert (await c.delete(f"/api/v1/contacts/{cid}", headers=_h(key))).status_code == 200
            assert (await c.get(f"/api/v1/contacts/{cid}", headers=_h(key))).status_code == 404
            # read-only key cannot write
            ro = await _key(db, scopes=("read",))
            assert (await c.post("/api/v1/contacts", headers=_h(ro), json={"phone": "+15005550803"})).status_code == 403
            # csv export
            r = await c.get("/api/v1/export/contacts", params={"format": "csv", "limit": 5}, headers=_h(key))
            assert r.status_code == 200 and r.text.startswith("id,first_name,last_name,phone")
    finally:
        await _wipe(db)


async def test_webhooks_crud_and_outbox():
    db = get_db()
    key = await _key(db)
    try:
        async with httpx.AsyncClient(base_url=API, timeout=30) as c:
            evs = (await c.get("/api/v1/webhooks/events")).json()
            assert "contact.created" in evs["event_types"] and "deal.closed" in evs["descriptions"]
            assert (await c.post("/api/v1/webhooks", headers=_h(key), json={"url": "http://insecure.example", "events": ["*"]})).status_code == 400
            assert (await c.post("/api/v1/webhooks", headers=_h(key), json={"url": "https://example.com/h", "events": ["nope.event"]})).status_code == 400
            r = await c.post("/api/v1/webhooks", headers=_h(key), json={"url": "https://httpbin.org/status/204", "events": ["contact.created", "note.added"], "secret": "s3cret", "description": "QA PublicAPI hook"})
            assert r.status_code == 200 and r.json()["store_id"] == STORE and r.json()["has_secret"], r.text
            wid = r.json()["id"]
            assert any(w["id"] == wid for w in (await c.get("/api/v1/webhooks", headers=_h(key))).json()["webhooks"])
            ping = (await c.post(f"/api/v1/webhooks/{wid}/test", headers=_h(key))).json()
            assert ping["delivery_id"].startswith("evt_") and "status_code" in ping and "success" in ping, ping
            dl = (await c.get(f"/api/v1/webhooks/{wid}/deliveries", headers=_h(key))).json()["deliveries"]
            assert dl and dl[0]["event"] == "ping", dl

        # Outbox: a contact created in the app (plain insert, no API) is delivered to this store's subscription as contact.created
        sub = await db.webhook_subscriptions.find_one({"_id": ObjectId(wid)})
        sent = []

        async def fake_deliver(db_, s, event):
            sent.append((str(s["_id"]), event["event"], event["data"]))
            return {"success": True}

        real = ob.deliver
        ob.deliver = fake_deliver
        try:
            mgr = await db.users.find_one({"store_id": STORE}, {"_id": 1})
            since = datetime.now(timezone.utc)
            await db.system_cursors.update_one({"_id": ob.CURSOR_ID}, {"$set": {"last_run": since}}, upsert=True)
            import asyncio
            await asyncio.sleep(0.02)  # Mongo stores ms; the new rows must land after the cursor
            cid = ObjectId()
            now = datetime.now(timezone.utc)
            await db.contacts.insert_one({"_id": cid, "user_id": str(mgr["_id"]), "first_name": "Outbox", "last_name": "QA", "phone": "+15005550804", "status": "active",
                                          "tags": [TAG], "created_at": now, "updated_at": now})
            await db.contact_events.insert_one({"contact_id": str(cid), "user_id": str(mgr["_id"]), "event_type": "note_added", "description": "QA PublicAPI outbox note", "timestamp": now})
            await db.contact_events.insert_one({"contact_id": str(cid), "user_id": str(mgr["_id"]), "event_type": "digital_card_sent", "description": "QA PublicAPI card", "timestamp": now})
            res = await ob.run_webhook_outbox(db, now=now + timedelta(seconds=1))
            kinds = {(e, d.get("contact_id") or d.get("id")) for _, e, d in sent}
            assert ("contact.created", str(cid)) in kinds, (res, kinds)
            assert ("note.added", str(cid)) in kinds, kinds
            assert not any(e == "activity.logged" for _, e, _ in sent), "subscription only asked for contact.created + note.added"
            assert any(s == str(sub["_id"]) for s, _, _ in sent), "our subscription must have received the events"
            # nothing new -> nothing delivered, cursor advanced
            sent.clear()
            res2 = await ob.run_webhook_outbox(db)
            assert res2["delivered"] == 0 and not sent
        finally:
            ob.deliver = real
    finally:
        await _wipe(db)


async def test_in_app_key_and_webhook_management_requires_admin():
    """The Integrations screen endpoints mint keys and register webhooks: no anonymous access, and only for your own store."""
    async with httpx.AsyncClient(base_url=API, timeout=30) as c:
        assert (await c.post(f"/api/integrations/api-keys?store_id={STORE}", json={"name": "x"})).status_code == 401
        assert (await c.get(f"/api/integrations/webhooks?store_id={STORE}")).status_code == 401
        login = await c.post("/api/auth/login", json={"email": "qa-manager@invalid.imonsocial.test", "password": "Manager123!"})
        assert login.status_code == 200, login.text
        tok = login.json()["token"]
        h = {"Authorization": f"Bearer {tok}"}
        assert (await c.get(f"/api/integrations/webhooks?store_id={STORE}", headers=h)).status_code == 200
        assert (await c.get(f"/api/integrations/webhooks?store_id={ObjectId()}", headers=h)).status_code == 403
        # a key minted in-app works on /api/v1
        r = await c.post(f"/api/integrations/api-keys?store_id={STORE}", headers=h, json={"name": "QA PublicAPI ui key", "scopes": ["read"]})
        assert r.status_code == 200 and r.json()["key"], r.text
        me = await c.get("/api/v1/me", headers=_h(r.json()["key"]))
        assert me.status_code == 200 and me.json()["scopes"] == ["read"], me.text
        assert (await c.delete(f"/api/integrations/api-keys/{r.json()['id']}", headers=h)).status_code == 200
        assert (await c.get("/api/v1/me", headers=_h(r.json()["key"]))).status_code == 401


async def test_public_docs_and_openapi_match_routes():
    """Every /api/v1 path named in the published markdown really exists, and the OpenAPI/Swagger console is public."""
    import re
    async with httpx.AsyncClient(base_url=API, timeout=30) as c:
        spec = (await c.get("/api/public/openapi-v1.json")).json()
        real = set(spec["paths"])
        assert "/api/v1/me" in real and "/api/v1/webhooks/{webhook_id}/test" in real
        assert (await c.get("/api/public/reference")).status_code == 200
        docs = (await c.get("/api/public/developer-docs")).json()["docs"]
        assert {d["slug"] for d in docs} == {"api-reference", "crm-integration-guide", "automotive-crm-programs"}
        ref = next(d for d in docs if d["slug"] == "api-reference")["content"]
        assert len(ref) > 5000, "API reference markdown is missing or a stub"
        mentioned = set(re.findall(r"/api/v1/[A-Za-z0-9_{}/\-]+", ref))
        norm = {re.sub(r"\{[^}]+\}", "{}", p).rstrip("/") for p in real}
        missing = [m for m in mentioned if re.sub(r"\{[^}]+\}", "{}", m).rstrip("/").rstrip(".,") not in norm]
        assert not missing, f"documented but not implemented: {missing}"
        md = await c.get("/api/public/developer-docs/api-reference.md")
        assert md.status_code == 200 and md.headers["content-type"].startswith("text/markdown")
