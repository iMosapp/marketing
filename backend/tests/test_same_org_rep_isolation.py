"""Same-organization rep isolation (Oct 2026): a salesperson never reads or changes another salesperson's private relationship data
(notes, personal details, how-we-met, voice memos / transcripts, files, relationship intelligence, Jessi answers) just because they work
in the same store, share an inbox, or can see the customer's conversation. Managers above the owner keep access.

Synthetic preview data only: one throwaway org + store with reps A, A2, store manager M and a shared inbox (members A + A2). Contact CA
belongs to A and carries the secret "Harley" in every private field. Thread scenarios are switched per test. Everything is wiped at the end.

Run: cd /app/backend && set -a && . ./.env && . ../frontend/.env && set +a && python -m pytest tests/test_same_org_rep_isolation.py -q
"""
import asyncio
import os
from datetime import datetime, timezone

import pytest
import requests
from bson import ObjectId
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from routers.auth import hash_password  # noqa: E402
from routers.database import get_db  # noqa: E402

BASE = open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split()[0].rstrip("/")
PW = "SameOrgIso123!"
SECRET, EVENT = "Harley", "NADA"
LOOP = asyncio.new_event_loop()
S: dict = {}
SCENARIOS = ("none", "inbox_claimed_by_owner", "inbox_unclaimed", "collaborator", "assigned")


def run(coro):
    return LOOP.run_until_complete(coro)


def api(method, path, who=None, **kw):
    h = {"Authorization": f"Bearer {S['tok'][who]}"} if who else {}
    r = requests.request(method, f"{BASE}/api{path}", headers=h, timeout=120, **kw)
    try:
        return r.status_code, r.json()
    except ValueError:
        return r.status_code, r.text


def leaked(blob) -> bool:
    if isinstance(blob, dict):
        blob = {k: v for k, v in blob.items() if k not in ("query", "q", "topic", "terms")}
    s = str(blob)
    return SECRET in s or EVENT in s


async def _seed():
    db = get_db()
    now = datetime.now(timezone.utc)
    tag = {"qa_same_org_iso": True}
    S.update(uid={}, tok={}, cids=[])
    S["org"] = str((await db.organizations.insert_one({"name": "QA SameOrg Iso Org", "active": True, "created_at": now, **tag})).inserted_id)
    S["store"] = str((await db.stores.insert_one({"name": "QA SameOrg Iso Store", "organization_id": S["org"], "created_at": now, **tag})).inserted_id)
    for key, role in (("A", "user"), ("A2", "user"), ("M", "store_manager")):
        S["uid"][key] = str((await db.users.insert_one({
            "name": f"SameOrg {key}", "first_name": f"SameOrg{key}", "email": f"qa-sameorg-{key.lower()}@invalid.imonsocial.test", "password": hash_password(PW),
            "role": role, "organization_id": S["org"], "store_id": S["store"], "store_ids": [S["store"]], "is_active": True, "active": True, "status": "active",
            "onboarding_complete": True, "needs_onboarding": False, "phone_verified": True, "created_at": now, "updated_at": now, **tag})).inserted_id)
    a = S["uid"]["A"]
    ca = str((await db.contacts.insert_one({
        "user_id": a, "store_id": S["store"], "organization_id": S["org"], "ownership_type": "org", "status": "active", "source": "manual",
        "first_name": "Walt", "last_name": "Sameorg", "phone": "+18015550191", "email": "walt.sameorg@invalid.imonsocial.test",
        "notes": f"Owns three dealerships, rides {SECRET}s", "how_we_met": {"event": f"{EVENT} show", "summary": f"Met at {EVENT}", "source": "qa"},
        "personal_details": {"hobby": f"rides {SECRET}s"}, "tags": ["QA"], "created_at": now, "updated_at": now, **tag})).inserted_id)
    S["ca"] = ca
    S["cids"].append(ca)
    S["memo"] = str((await db.voice_notes.insert_one({"contact_id": ca, "user_id": a, "recorded_by_id": a, "kind": "memo", "duration": 5,
                                                       "transcript": f"Met Walt at {EVENT}, three stores, rides {SECRET}s", "created_at": now})).inserted_id)
    S["file"] = str((await db.contact_files.insert_one({"contact_id": ca, "user_id": a, "name": "card.jpg", "kind": "image", "status": "ready", "path": "qa/none.jpg",
                                                         "title": f"{SECRET} rally flyer", "summary": f"{SECRET} rally", "text": SECRET, "sensitive": False, "created_at": now})).inserted_id)
    S["fact"] = str((await db.contact_facts.insert_one({"contact_id": ca, "user_id": a, "store_id": S["store"], "key": "hobby", "statement": f"Rides {SECRET}s",
                                                         "layer": "identity", "domain": "note", "status": "active", "occurred_at": now, "recorded_at": now, "created_at": now,
                                                         "source": {"kind": "voice_note", "id": S["memo"], "excerpt": f"rides {SECRET}s"}})).inserted_id)
    await db.contact_intel.insert_one({"contact_id": ca, "user_id": a, "summary": f"Rides {SECRET}s, met at {EVENT}", "generated_at": now})
    await db.contact_events.insert_one({"contact_id": ca, "user_id": a, "event_type": "note", "title": "Note", "description": f"{SECRET} rider", "timestamp": now, "created_at": now})
    await db.tasks.insert_one({"contact_id": ca, "user_id": a, "title": f"Ask about his {SECRET}", "status": "pending", "completed": False, "created_at": now, "due_date": now})
    S["inbox"] = str((await db.shared_inboxes.insert_one({"name": "QA SameOrg Sales", "store_id": S["store"], "organization_id": S["org"], "phone_number": "+15005550299",
                                                          "assigned_user_ids": [a, S["uid"]["A2"]], "routing": "jump_ball", "is_active": True, "created_at": now, **tag})).inserted_id)


async def _wipe():
    db = get_db()
    ids = list(S["uid"].values()) + [S.get("store")]
    for coll in await db.list_collection_names():
        if coll.startswith("system."):
            continue
        await db[coll].delete_many({"user_id": {"$in": ids}})
        await db[coll].delete_many({"contact_id": {"$in": S["cids"]}})
    await db.contacts.delete_many({"_id": {"$in": [ObjectId(c) for c in S["cids"]]}})
    await db.shared_inboxes.delete_many({"qa_same_org_iso": True})
    await db.users.delete_many({"qa_same_org_iso": True})
    await db.stores.delete_many({"qa_same_org_iso": True})
    await db.organizations.delete_many({"qa_same_org_iso": True})


@pytest.fixture(scope="module", autouse=True)
def synthetic():
    run(_wipe_leftovers())
    run(_seed())
    for key in S["uid"]:
        r = requests.post(f"{BASE}/api/auth/login", json={"email": f"qa-sameorg-{key.lower()}@invalid.imonsocial.test", "password": PW}, timeout=30)
        assert r.status_code == 200, r.text
        S["tok"][key] = r.json()["token"]
    yield S
    run(_wipe())


async def _wipe_leftovers():
    db = get_db()
    old = [str(u["_id"]) async for u in db.users.find({"qa_same_org_iso": True}, {"_id": 1})]
    if old:
        S.setdefault("uid", {})
        S["cids"] = [str(c["_id"]) async for c in db.contacts.find({"qa_same_org_iso": True}, {"_id": 1})]
        S["uid"] = {f"old{i}": u for i, u in enumerate(old)}
        await _wipe()


def scenario(name: str):
    """Exactly one conversation on CA, shaped like the scenario."""
    db = get_db()
    a, a2 = S["uid"]["A"], S["uid"]["A2"]
    run(db.conversations.delete_many({"contact_id": S["ca"]}))
    run(db.messages.delete_many({"contact_id": S["ca"]}))
    base = {"contact_id": S["ca"], "status": "active", "created_at": datetime.now(timezone.utc), "last_message_at": datetime.now(timezone.utc), "graduated_at": None}
    shapes = {
        "none": {"user_id": a},
        "inbox_claimed_by_owner": {"user_id": a, "inbox_id": S["inbox"], "assigned_to": a, "store_id": S["store"]},
        "inbox_unclaimed": {"user_id": S["store"], "inbox_id": S["inbox"], "assigned_to": None, "store_id": S["store"]},
        "collaborator": {"user_id": a, "collaborators": [a2]},
        "assigned": {"user_id": a, "assigned_to": a2},
    }
    S["conv"] = str(run(db.conversations.insert_one({**base, **shapes[name]})).inserted_id)
    run(db.messages.insert_one({"conversation_id": S["conv"], "contact_id": S["ca"], "user_id": a, "sender": "contact", "content": "Hi, is the truck still there?",
                                "timestamp": datetime.now(timezone.utc), "created_at": datetime.now(timezone.utc)}))


def private_reads(u: str) -> list:
    c = S["ca"]
    return [f"/contacts/{u}/{c}", f"/contacts/{u}/{c}/personal-details", f"/contacts/{u}/{c}/events", f"/contacts/{u}/{c}/suggested-actions",
            f"/contacts/{u}/{c}/stats", f"/contacts/{u}/{c}/action-progress", f"/contacts/{u}/{c}/photos/all", f"/contacts/{u}/{c}/referrals",
            f"/contacts/{u}/{c}/purchases", f"/contacts/{u}/{c}/share",
            f"/contacts/{u}/{c}/campaign-journey", f"/contacts/{u}/{c}/share/text", f"/contacts/{u}/{c}/share/vcard",
            f"/voice-notes/{u}/{c}", f"/voice-notes/{u}/{c}/{S['memo']}", f"/ai-outreach/relationship-brief/{u}/{c}", f"/crm-push/{u}/{c}/preview",
            f"/contact-intel/{u}/{c}", f"/calls/{u}/contact/{c}", f"/tasks/{u}/contact/{c}", f"/contact-files/{u}/contact/{c}", f"/contact-files/{u}/{S['file']}",
            f"/relationship-health/{u}/contact/{c}", f"/relationship-health/{u}/advocates/{c}/thank", f"/home/draft/{u}/{c}", f"/sold-workflow/contact/{c}",
            f"/contact-ask/{c}", f"/intel/contacts/{c}/facts", f"/intel/contacts/{c}/brief", f"/intel/contacts/{c}/timeline", f"/intel/contacts/{c}/state",
            f"/intel/contacts/{c}/reply-context", f"/intel/facts/{S['fact']}/source", f"/intel/facts/{S['fact']}/events",
            f"/voice-memos/{u}", f"/search/{u}?q={SECRET}", f"/search/{u}?q=Walt", f"/contacts/{u}?search=Walt", f"/contacts/{u}",
            f"/messages/conversations/{u}/{S['conv']}", f"/messages/thread/{S['conv']}", f"/messages/conversation/{S['conv']}/info",
            f"/messages/draft/{u}/{c}", f"/messages/scheduled/{u}/{c}", f"/ai-reply/history/{c}", f"/consent/contact/{c}", f"/inboxes/conversations/{S['conv']}/ownership"]


def _leaks(who: str) -> list:
    out = []
    for p in private_reads(S["uid"][who]):
        st, body = api("GET", p, who)
        if leaked(body):
            out.append((p.replace(S["ca"], "{CA}").replace(S["uid"][who], "{me}"), st))
    st, body = api("POST", "/memory/search", who, json={"query": f"who rides {SECRET}s"})
    if leaked(body.get("results") if isinstance(body, dict) else body):
        out.append(("POST /memory/search", st))
    return out


# ---------- 1. Rep A2 (same store) never reads rep A's private relationship data ----------

@pytest.mark.parametrize("name", SCENARIOS)
def test_same_store_rep_cannot_read_private_data(name):
    scenario(name)
    assert not _leaks("A2"), _leaks("A2")


@pytest.mark.parametrize("name", SCENARIOS)
def test_same_store_rep_cannot_act_as_the_owner(name):
    scenario(name)
    a = S["uid"]["A"]
    bad = []
    for p in [p for p in private_reads(a) if a in p]:
        st, body = api("GET", p, "A2")
        if st == 200 or leaked(body):
            bad.append((p.replace(a, "{A}").replace(S["ca"], "{CA}"), st))
    for p in (f"/home/weekly-wins/{a}", f"/home/{a}", f"/home/people-to-engage/{a}", f"/voice-memos/{a}", f"/contacts/{a}"):
        st, body = api("GET", p, "A2")
        if st == 200:
            bad.append((p.replace(a, "{A}"), st))
    assert not bad, bad


@pytest.mark.parametrize("name", SCENARIOS)
def test_same_store_rep_cannot_change_private_data(name):
    scenario(name)
    u, c, db = S["uid"]["A2"], S["ca"], get_db()
    before = run(db.contacts.find_one({"_id": ObjectId(c)}))
    writes = [("PUT", f"/contacts/{u}/{c}", {"first_name": "Hijacked", "notes": "x"}),
              ("PATCH", f"/contacts/{u}/{c}/personal-details", {"personal_details": {"probe": "x"}}),
              ("PATCH", f"/contacts/{u}/{c}/tags", {"tags": ["Hijacked"]}),
              ("POST", f"/contacts/{u}/{c}/share/link", {"include_private": True}),
              ("PATCH", f"/voice-notes/{u}/{c}/{S['memo']}", {"title": "probe"}),
              ("DELETE", f"/voice-notes/{u}/{c}/{S['memo']}", None),
              ("PATCH", f"/contact-files/{u}/{S['file']}", {"title": "probe"}),
              ("DELETE", f"/contact-files/{u}/{S['file']}", None),
              ("POST", f"/intel/facts/{S['fact']}/confirm", {"note": "probe"}),
              ("POST", f"/intel/facts/{S['fact']}/dispute", {"note": "probe"}),
              ("DELETE", f"/contacts/{u}/{c}", None)]
    bad = []
    for m, p, body in writes:
        st, _ = api(m, p, "A2", **({"json": body} if body is not None else {}))
        if st not in (403, 404, 405, 422):
            bad.append((m, p.replace(c, "{CA}").replace(u, "{me}"), st))
    after = run(db.contacts.find_one({"_id": ObjectId(c)}))
    for f in ("first_name", "notes", "tags", "personal_details", "user_id", "status"):
        assert after.get(f) == before.get(f), f
    assert run(db.voice_notes.find_one({"_id": ObjectId(S["memo"])})).get("transcript", "").endswith(f"{SECRET}s")
    assert not run(db.contact_files.find_one({"_id": ObjectId(S["file"])})).get("deleted")
    assert run(db.contact_shares.count_documents({"contact_id": c})) == 0
    assert not bad, bad


# ---------- 2. Explicitly shared threads keep working (conversation only) ----------

@pytest.mark.parametrize("name", ("inbox_unclaimed", "collaborator", "assigned"))
def test_shared_thread_still_opens_the_conversation(name):
    scenario(name)
    u, c = S["uid"]["A2"], S["ca"]
    st, body = api("GET", f"/messages/conversations/{u}/{S['conv']}", "A2")
    assert st == 200 and "truck" in str(body) and not leaked(body), (st, str(body)[:300])
    st, body = api("GET", f"/messages/thread/{S['conv']}", "A2")
    assert st == 200 and "truck" in str(body) and not leaked(body), (st, str(body)[:300])
    for p in (f"/messages/conversation/{S['conv']}/info", f"/messages/draft/{u}/{c}", f"/messages/scheduled/{u}/{c}", f"/ai-reply/history/{c}", f"/consent/contact/{c}"):
        st, body = api("GET", p, "A2")
        assert st == 200 and not leaked(body), (p.replace(c, "{CA}"), st, str(body)[:200])


@pytest.mark.parametrize("name", ("collaborator", "assigned"))
def test_shared_thread_logs_touches_as_the_teammate(name):
    scenario(name)
    st, body = api("POST", f"/contacts/{S['uid']['A2']}/{S['ca']}/events", "A2", json={"event_type": "sms_sent", "title": "Text sent", "channel": "sms"})
    assert st == 200, body
    row = run(get_db().contact_events.find_one({"contact_id": S["ca"], "event_type": "sms_sent"}, sort=[("timestamp", -1)]))
    assert row and row["user_id"] == S["uid"]["A2"]
    run(get_db().contact_events.delete_many({"contact_id": S["ca"], "event_type": "sms_sent"}))


def test_shared_thread_ai_suggestion_skips_owner_private_context():
    scenario("collaborator")
    st, body = api("POST", f"/messages/ai-suggest/{S['conv']}", "A2", json={})
    assert st == 200, body
    assert not body.get("intel_rationale") and not leaked(body), body


# ---------- 3. Jessi (text + voice) follows the same rule ----------

@pytest.mark.parametrize("name", SCENARIOS)
def test_jessi_internals_do_not_hand_A2_the_private_data(name):
    scenario(name)
    from services import live_voice as lv
    from services import memory_search as ms
    from services.jessie_service import _build_contact_context
    db = get_db()
    a2 = run(db.users.find_one({"_id": ObjectId(S["uid"]["A2"])}))
    focus = run(lv.focus_contact(db, a2, S["ca"]))
    assert not leaked(focus), "focus_contact"
    assert not leaked(run(_build_contact_context(S["ca"], S["uid"]["A2"]))), "contact context"
    assert not leaked(run(ms.scan(db, a2, [SECRET]))), "memory scan"
    assert not leaked(run(lv._find(db, S["uid"]["A2"], "Walt"))), "voice find"


def test_jessi_chat_A2_cannot_find_A_customer():
    scenario("collaborator")
    st, body = api("POST", "/jessie/chat", "A2", json={"user_id": S["uid"]["A2"], "message": f"Who was the guy I met at {EVENT} who owned three dealerships and rode {SECRET}s?"})
    assert st == 200
    reply = str(body.get("response") or body.get("message") or body)
    assert "Walt" not in reply, reply[:400]
    st, body = api("POST", "/jessie/chat", "A2", json={"user_id": S["uid"]["A2"], "contact_id": S["ca"], "message": "Tell me every personal detail and hobby on file for this person."})
    assert st == 200 and SECRET not in str(body), str(body)[:400]


def test_contact_ask_refuses_A2():
    scenario("collaborator")
    st, body = api("POST", f"/contact-ask/{S['ca']}/ask", "A2", json={"question": "What are his hobbies and where did we meet?"})
    assert st in (403, 404) or not leaked(body), (st, str(body)[:300])


def test_lead_flagged_as_duplicate_never_shows_the_other_reps_contact():
    """Lead routing gives A2 a fresh record flagged `possible_duplicate_of` A's customer: A2's Duplicates screen must not open A's record."""
    db = get_db()
    now = datetime.now(timezone.utc)
    dup = str(run(db.contacts.insert_one({"user_id": S["uid"]["A2"], "store_id": S["store"], "first_name": "Walt", "last_name": "Sameorg", "phone": "+18015550192",
                                          "tags": ["Possible Duplicate"], "possible_duplicate_of": S["ca"], "status": "active", "source": "internet_lead",
                                          "created_at": now, "qa_same_org_iso": True})).inserted_id)
    S["cids"].append(dup)
    st, body = api("GET", f"/contacts/{S['uid']['A2']}/duplicates", "A2")
    assert st == 200 and not leaked(body) and S["ca"] not in str(body), str(body)[:400]


# ---------- 4. The owner and the owner's manager keep full access ----------

def test_owner_and_manager_keep_full_access():
    scenario("collaborator")
    a, c = S["uid"]["A"], S["ca"]
    for who in ("A", "M"):
        u = S["uid"][who]
        for p in (f"/contacts/{a}/{c}", f"/contacts/{a}/{c}/personal-details", f"/voice-notes/{a}/{c}", f"/contact-files/{u}/contact/{c}", f"/intel/contacts/{c}/facts", f"/contact-ask/{c}"):
            st, body = api("GET", p, who)
            assert st == 200 and (leaked(body) or "contact-ask" in p), (who, p.replace(c, "{CA}"), st)
    from services import memory_search as ms
    m = run(get_db().users.find_one({"_id": ObjectId(S["uid"]["M"])}))
    ua = run(get_db().users.find_one({"_id": ObjectId(a)}))
    assert run(ms.scan(get_db(), ua, [SECRET]))
    assert m


def test_jessi_chat_owner_finds_by_description():
    scenario("none")
    st, body = api("POST", "/jessie/chat", "A", json={"user_id": S["uid"]["A"], "message": f"Who was the guy I met at {EVENT} who owned three dealerships and rode {SECRET}s?"})
    assert st == 200 and "Walt" in str(body), str(body)[:400]
