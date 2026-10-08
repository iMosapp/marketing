"""Customer trade link (public token page) + automatic trade tags. Runs against the preview backend with the shared QA accounts."""
import io
import os
import sys

import pytest
import requests
from dotenv import load_dotenv

sys.path.insert(0, "/app/backend")
sys.path.insert(0, "/app/backend/tests")
load_dotenv("/app/backend/.env")
from _http import API, call, login, auth  # noqa: E402
from services.appraisals import followup  # noqa: E402

REP = ("activation-tester@invalid.imonsocial.test", "NewPass123!")
OTHER_ORG_ADMIN = ("qa-orgadmin@invalid.imonsocial.test", "OrgAdmin123!")
SARAH = "6aa413008f0d53e3f2261853"
REP_ID = "6a978d68b8673c29063aa8b9"
VIN = "2T3DWRFV3LW077677"  # decodes at NHTSA: 2020 Toyota RAV4


@pytest.fixture(scope="module")
def rep():
    return auth(*login(*REP))


@pytest.fixture(scope="module")
def stranger():
    return auth(*login(*OTHER_ORG_ADMIN))


@pytest.fixture(scope="module")
def appraisal(rep):
    st, b = call("POST", "/api/appraisals", {"contact_id": SARAH, "mode": "vehicle_here"}, rep)
    assert st == 200, b
    yield b["appraisal"]
    call("DELETE", f"/api/appraisals/{b['appraisal']['id']}", None, rep)


def _jpeg() -> bytes:
    from PIL import Image
    im = Image.new("RGB", (900, 700), (40, 40, 48))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=80)
    return buf.getvalue()


def test_link_lifecycle_public_page_photo_submit(rep, stranger, appraisal):
    aid = appraisal["id"]
    st, b = call("POST", f"/api/appraisals/{aid}/intake-link", {"channel": "copy"}, rep)
    assert st == 200, b
    it = b["intake"]
    assert it["url"].startswith("https://") and "/api/public/trade/" in it["url"] and it["short_url"] and it["expires_at"] and it["sent_via"] == "copy"
    assert b["appraisal"]["mode"] == "customer_sent" and b["appraisal"]["intake"]["url"] == it["url"] and "intake_token" not in b["appraisal"]
    token = it["url"].rsplit("/", 1)[1]
    # same link is reused while valid
    st, b2 = call("POST", f"/api/appraisals/{aid}/intake-link", {"channel": "copy"}, rep)
    assert st == 200 and b2["intake"]["url"] == it["url"]
    # a stranger cannot mint or see it
    st, _ = call("POST", f"/api/appraisals/{aid}/intake-link", {"channel": "copy"}, stranger)
    assert st == 404
    # public page (no auth) renders for the customer; opened_at gets stamped
    r = requests.get(f"{API}/api/public/trade/{token}")
    assert r.status_code == 200 and "Hi Sarah" in r.text and "noindex" in r.text and "Bearer" not in r.text
    ctx = requests.get(f"{API}/api/public/trade/{token}/context").json()
    assert ctx["state"] == "open" and ctx["have_vin"] is False and len(ctx["questions"]) == 6 and ctx["customer"] == "Sarah"
    assert not any(k in ctx for k in ("suggested_acv", "approved_value", "user_id", "contact_id")), "no values, no ids on the public side"
    assert requests.get(f"{API}/api/public/trade/this-token-does-not-exist-xx").status_code == 404
    # photo upload goes through the normal media path with source customer_supplied
    r = requests.post(f"{API}/api/public/trade/{token}/photo", data={"role": "exterior"}, files={"file": ("ext.jpg", _jpeg(), "image/jpeg")})
    assert r.status_code == 200, r.text
    assert r.json()["role"] == "exterior" and r.json()["thumb"]
    r = requests.post(f"{API}/api/public/trade/{token}/photo", data={"role": "bogus"}, files={"file": ("x.jpg", _jpeg(), "image/jpeg")})
    assert r.status_code == 200 and r.json()["role"] == "photo"
    # submit: VIN decodes and sets the vehicle; mileage stays "reported"
    body = {"vin": VIN, "mileage": "76189", "zip": "80215", "condition": {"overall": "good", "accidents": "no", "warning_lights": "no", "tires": "worn", "smoke": "no", "keys": "2", "junk": "x"},
            "notes": "New brakes last month", "wants": "21000"}
    r = requests.post(f"{API}/api/public/trade/{token}/submit", json=body)
    assert r.status_code == 200 and r.json()["vehicle_set"] is True, r.text
    st, a = call("GET", f"/api/appraisals/{aid}", None, rep)
    assert st == 200
    assert a["vin"] == VIN and a["vehicle"]["make"] == "Toyota" and a["step"] == "mileage" and a["mileage_confirmed"] is None and a["identity_method"] == "customer_link"
    ci = a["customer_intake"]
    assert ci["mileage"] == 76189 and ci["zip"] == "80215" and ci["condition"] == {"overall": "good", "accidents": "no", "warning_lights": "no", "tires": "worn", "smoke": "no", "keys": "2"}
    assert ci["notes"] == "New brakes last month" and ci["wants"] == 21000 and ci["photo_count"] == 2
    assert a["intake"]["opened_at"] and a["intake"]["submitted_at"] and a["intake"]["photo_count"] == 2
    assert a["customer_expected_value"] is None, "a number mentioned on the link is not the recorded expectation"
    srcs = {(m["role"], m["source"]) for m in a["media"]}
    assert ("exterior", "customer_supplied") in srcs and ("photo", "customer_supplied") in srcs
    actions = {x["action"] for x in a.get("activity") or []}
    assert {"intake_link_created", "customer_intake", "vehicle_identified"} <= actions, actions
    # customer page now shows the thank-you state but still accepts more photos; then the rep turns the link off
    assert "Sent to" in requests.get(f"{API}/api/public/trade/{token}").text
    st, b = call("DELETE", f"/api/appraisals/{aid}/intake-link", None, rep)
    assert st == 200 and b["intake"]["revoked_at"]
    assert requests.get(f"{API}/api/public/trade/{token}").status_code == 410
    r = requests.post(f"{API}/api/public/trade/{token}/submit", json={"notes": "late"})
    assert r.status_code == 400
    r = requests.post(f"{API}/api/public/trade/{token}/photo", data={"role": "exterior"}, files={"file": ("ext.jpg", _jpeg(), "image/jpeg")})
    assert r.status_code == 400


def test_sms_channel_needs_a_phone_or_sends(rep):
    st, b = call("POST", "/api/appraisals", {"contact_id": SARAH, "mode": "vehicle_here"}, rep)
    aid = b["appraisal"]["id"]
    try:
        st, b = call("POST", f"/api/appraisals/{aid}/intake-link", {"channel": "sms"}, rep)
        assert st in (200, 400), b
        if st == 200:
            assert b["intake"]["sent_via"] == "sms" and b["intake"]["sent_to"]
            # the text shows in the rep's inbox thread with the customer, as a sent bubble
            st, convs = call("GET", f"/api/messages/conversations/{REP_ID}", None, rep)
            assert st == 200
            sarah = [c for c in (convs if isinstance(convs, list) else convs.get("conversations", [])) if str(c.get("contact_id")) == SARAH]
            assert sarah, "no inbox conversation with Sarah"
            mine = []
            for conv in sarah:  # shared-inbox threads with Sarah 403 for the rep; the trade link sits in the rep's own thread
                st, t = call("GET", f"/api/messages/thread/{conv.get('id') or conv.get('_id')}", None, rep)
                if st != 200:
                    continue
                msgs = t if isinstance(t, list) else t.get("messages", [])
                mine = [m for m in msgs if b["intake"]["short_url"] in (m.get("content") or "")]
                if mine:
                    break
            assert mine and mine[-1]["sender"] == "user" and mine[-1].get("status") in ("sent", "sent_mock", "delivered"), mine[-1:]
        else:
            assert "phone" in b["detail"].lower() or "Text failed" in b["detail"]
    finally:
        call("DELETE", f"/api/appraisals/{aid}", None, rep)


def test_gap_tag_buckets():
    f = followup.gap_tag
    assert f({"customer_expected_value": 30000, "approved_value": 30500}) == "trade-gap-none"
    assert f({"customer_expected_value": 30000, "approved_value": 29500}) == "trade-gap-under-1k"
    assert f({"customer_expected_value": 30000, "suggested_acv": 28000}) == "trade-gap-1k-3k"
    assert f({"customer_expected_value": 30000, "approved_value": 26999}) == "trade-gap-3k-plus"
    assert f({"customer_expected_value": None, "approved_value": 26999}) is None
    assert set(followup.TRADE_TAG_HELP) == set(followup.TRADE_TAGS)


@pytest.mark.asyncio
async def test_trade_tags_replace_previous_trade_state(monkeypatch):
    from bson import ObjectId
    from motor.motor_asyncio import AsyncIOMotorClient
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    cid = ObjectId()
    await db.contacts.insert_one({"_id": cid, "first_name": "Tag", "last_name": "Test", "user_id": "6a978d68b8673c29063aa8b9", "tags": ["vip", "trade-thinking", "trade-gap-3k-plus"]})
    seen = []

    async def fake_apply(user_id, contact_id, tags, source=""):
        seen.append((contact_id, tags, source))
        return []
    import services.tag_workflows as tw
    monkeypatch.setattr(tw, "apply_tag_workflows", fake_apply)
    appr = {"contact_id": str(cid), "user_id": "6a978d68b8673c29063aa8b9", "organization_id": None, "store_id": None, "customer_expected_value": 30000, "approved_value": 29600}
    try:
        assert await followup.apply_trade_tags(db, appr, "submitted") == ["trade-appraised"]
        new = await followup.apply_trade_tags(db, appr, "wants_more")
        assert new == ["trade-wants-more", "trade-gap-under-1k"]
        c = await db.contacts.find_one({"_id": cid})
        assert c["tags"] == ["vip", "trade-appraised", "trade-wants-more", "trade-gap-under-1k"], c["tags"]
        assert seen[-1] == (str(cid), ["trade-wants-more", "trade-gap-under-1k"], "trade_appraisal")
        assert await followup.apply_trade_tags(db, appr, "approved") == [], "approved is not an outcome; no tag churn"
        assert await followup.apply_trade_tags(db, {**appr, "contact_id": None}, "accepted") == []
    finally:
        await db.contacts.delete_one({"_id": cid})
