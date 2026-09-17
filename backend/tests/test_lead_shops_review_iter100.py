"""Backend API guards + manual lead shop end-to-end for the Lead Shops review.
Uses seed from tests/seed_lead_shop_demo.py; leaves seeded shops intact."""
import os
import time
import pytest
import requests
from motor.motor_asyncio import AsyncIOMotorClient
import asyncio

_BURL = os.environ.get('REACT_APP_BACKEND_URL')
if not _BURL:
    with open('/app/frontend/.env') as _f:
        for _l in _f:
            if _l.startswith('REACT_APP_BACKEND_URL='):
                _BURL = _l.split('=', 1)[1].strip()
BASE = _BURL.rstrip('/') + '/api'
ADMIN = ("forest@imosapp.com", "Admin123!")
MANAGER = ("qa-manager@invalid.imonsocial.test", "Manager123!")
CLIENT_ID = "6aa6d7dfb4c41decb2734ec4"  # QA Jeep 979a


def login(email, pw):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin_headers():
    return {"Authorization": f"Bearer {login(*ADMIN)}"}


@pytest.fixture(scope="module")
def mgr_headers():
    return {"Authorization": f"Bearer {login(*MANAGER)}"}


@pytest.fixture(scope="module")
def seeds(admin_headers):
    r = requests.get(f"{BASE}/lead-shops", params={"client_id": CLIENT_ID}, headers=admin_headers)
    assert r.status_code == 200, r.text
    shops = r.json().get("shops") or r.json().get("items") or r.json()
    if isinstance(shops, dict):
        shops = shops.get("shops") or shops.get("items") or []
    completed = next((s for s in shops if s.get("status") == "completed"), None)
    live = next((s for s in shops if s.get("status") == "live"), None)
    assert completed and live, f"seed missing: {shops}"
    return {"completed": completed, "live": live}


# ---- Guards ----
def test_lead_shops_requires_auth():
    r = requests.post(f"{BASE}/lead-shops", json={"client_id": CLIENT_ID, "method": "adf"})
    assert r.status_code == 401


def test_lead_shops_non_admin_forbidden(mgr_headers):
    r = requests.post(f"{BASE}/lead-shops", json={"client_id": CLIENT_ID, "method": "adf"}, headers=mgr_headers)
    assert r.status_code == 403, r.text


def test_buy_number_guard(admin_headers):
    """Only safe while LEAD_SHOP_BUY_NUMBERS=false is in the backend env: with the guard off this endpoint BUYS a real Twilio number."""
    if (os.environ.get("LEAD_SHOP_BUY_NUMBERS") or "true").strip().lower() not in ("0", "false", "no", "off"):
        pytest.skip("LEAD_SHOP_BUY_NUMBERS guard is not on; never hit the buy endpoint for real")
    r = requests.post(f"{BASE}/lead-shops/numbers/buy", json={}, headers=admin_headers)
    assert r.status_code == 400
    assert "switched off" in r.text.lower() or "disabled" in r.text.lower(), r.text


def test_adf_without_lead_email(admin_headers):
    # create throwaway client, no lead_email
    tc = requests.post(f"{BASE}/shop-clients", json={"name": "TEST_no_lead_email_review", "industry": "automotive"}, headers=admin_headers)
    assert tc.status_code in (200, 201), tc.text
    cid = tc.json().get("id") or tc.json().get("_id") or (tc.json().get("client") or {}).get("id")
    assert cid
    try:
        r = requests.post(f"{BASE}/lead-shops", json={"client_id": cid, "method": "adf"}, headers=admin_headers)
        assert r.status_code == 400
        assert "crm lead email" in r.text.lower() or "lead_email" in r.text.lower(), r.text
    finally:
        requests.delete(f"{BASE}/shop-clients/{cid}", headers=admin_headers)


def test_delivered_conflict_on_completed(admin_headers, seeds):
    sid = seeds["completed"]["id"]
    r = requests.post(f"{BASE}/lead-shops/{sid}/delivered", headers=admin_headers)
    assert r.status_code == 409, r.text


def test_rescore_completed(admin_headers, seeds):
    sid = seeds["completed"]["id"]
    r = requests.post(f"{BASE}/lead-shops/{sid}/rescore", headers=admin_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    score = body.get("score") or (body.get("shop") or {}).get("score")
    assert score and isinstance(score.get("overall"), (int, float))


# ---- Manual lead shop end-to-end ----
@pytest.fixture(scope="module")
def manual_shop(admin_headers):
    payload = {
        "client_id": CLIENT_ID,
        "method": "manual",
        "department": "sales",
        "offering": "2021 Ram 1500",
        "source_name": "Website",
        "window_hours": 24,
        "challenges": ["random"],
        "notes": "iter100 review",
    }
    r = requests.post(f"{BASE}/lead-shops", json=payload, headers=admin_headers)
    assert r.status_code in (200, 201), r.text
    body = r.json()
    shop = body.get("shop") or body
    sid = shop.get("id") or shop.get("_id")
    assert sid, body
    yield sid
    requests.delete(f"{BASE}/lead-shops/{sid}", headers=admin_headers)
    # restore pool cooldown
    async def reset():
        db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
        await db.phone_number_pool.update_one({"phone_number": "+15005550311"}, {"$set": {"cooldown_until": None, "status": "available", "lead_shop_id": None}})
    asyncio.run(reset())


def test_manual_pool_cell(admin_headers, manual_shop):
    r = requests.get(f"{BASE}/lead-shops/{manual_shop}", headers=admin_headers)
    assert r.status_code == 200
    shop = r.json().get("shop") or r.json()
    cell = (shop.get("persona") or {}).get("phone") or (shop.get("persona") or {}).get("cell")
    assert cell == "+15005550311", shop.get("persona")
    assert shop.get("status") == "pending_delivery"


def test_delivered_then_inbound_text(admin_headers, manual_shop):
    r = requests.post(f"{BASE}/lead-shops/{manual_shop}/delivered", headers=admin_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    shop = body.get("shop") or body
    assert shop.get("status") == "live"

    # simulate store texting back
    r2 = requests.post(f"{BASE}/webhooks/twilio/incoming", data={
        "From": "+18015550140",
        "To": "+15005550311",
        "Body": "Hi Sam, this is Joe at QA Jeep about the Ram",
        "MessageSid": "SMleadqa_iter100",
        "NumMedia": "0",
    })
    assert r2.status_code == 200, r2.text
    assert "<Response" in r2.text

    # verify events + counts
    r3 = requests.get(f"{BASE}/lead-shops/{manual_shop}", headers=admin_headers)
    shop = r3.json().get("shop") or r3.json()
    ev_kinds = [e.get("kind") for e in shop.get("events", [])]
    assert "text_received" in ev_kinds, ev_kinds
    convos = shop.get("conversations", []) or shop.get("sessions", {}).get("text") or []
    # counts.text
    counts = (shop.get("counts") or {}).get("text") or (shop.get("counts") or {}).get("texts")
    assert counts == 1 or counts == {"count": 1} or (isinstance(counts, dict) and counts.get("count") == 1), shop.get("counts")

    # ensure NOT routed as normal inbound contact for forest
    async def check_contact():
        db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
        me = await db.users.find_one({"email": "forest@imosapp.com"})
        c = await db.contacts.find_one({"owner_id": str(me["_id"]), "name": {"$regex": r"^Lead \(0140\)"}})
        assert c is None, f"leaked as inbound contact: {c}"
    asyncio.run(check_contact())


def test_close_then_pool_reset(admin_headers, manual_shop):
    r = requests.post(f"{BASE}/lead-shops/{manual_shop}/close", headers=admin_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    shop = body.get("shop") or body
    assert shop.get("status") in ("closing", "completed")

    # poll up to 90s for completed
    deadline = time.time() + 90
    while time.time() < deadline:
        r2 = requests.get(f"{BASE}/lead-shops/{manual_shop}", headers=admin_headers)
        shop = r2.json().get("shop") or r2.json()
        if shop.get("status") == "completed":
            break
        time.sleep(3)
    assert shop.get("status") == "completed", shop.get("status")
    assert shop.get("score") and isinstance(shop["score"].get("overall"), (int, float))

    # verify pool row reset
    async def check_pool():
        db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
        row = await db.phone_number_pool.find_one({"phone_number": "+15005550311"})
        assert row["status"] == "available", row
        assert row.get("cooldown_until") is not None, row
    asyncio.run(check_pool())
