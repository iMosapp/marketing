"""Contact ownership security hotfix (Oct 2026): tenant boundaries for contacts, relationship data, Jessi, transfers and lead routing.

Synthetic preview data only: two throwaway orgs X / Y (one store each); org X: reps A, A2, store manager MX, org admin OAX; org Y: rep B,
store manager MY. A and B both know the same person (same phone + email) with different private notes / memos. Everything created is
wiped at the end (users, orgs, stores, contacts and every row pointing at them). Never touches real accounts' data except reading the
super-admin login for the audit check (rows it writes about synthetic contacts are removed).

Run: cd /app/backend && set -a && . ./.env && . ../frontend/.env && set +a && python -m pytest tests/test_contact_ownership_hotfix.py -q
"""
import asyncio
import os
import re
from datetime import datetime, timedelta, timezone

import pytest
import requests
from bson import ObjectId
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from routers.auth import hash_password  # noqa: E402
from routers.database import get_db  # noqa: E402
from tests import qa_creds  # noqa: E402

BASE = open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split()[0].rstrip("/")
PW = "HotfixIso123!"
PHONE, PHONE_FMT, EMAIL = "+18015550142", "(801) 555-0142", "john.hotfix@invalid.imonsocial.test"
A_SECRET, B_SECRET = "Rubicon", "Zelda"
LOOP = asyncio.new_event_loop()
S: dict = {}


def run(coro):
    return LOOP.run_until_complete(coro)


def api(method, path, who=None, **kw):
    h = {"Authorization": f"Bearer {S['tok'][who]}"} if who else {}
    r = requests.request(method, f"{BASE}/api{path}", headers=h, timeout=90, **kw)
    try:
        return r.status_code, r.json()
    except ValueError:
        return r.status_code, r.text


def login(email, pw):
    r = requests.post(f"{BASE}/api/auth/login", json={"email": email, "password": pw}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


def contact(cid):
    return run(get_db().contacts.find_one({"_id": ObjectId(cid)}))


def new_contact(who, first, notes="", phone=PHONE, email=EMAIL, last="Hotfix", source="manual"):
    st, body = api("POST", f"/contacts/{S['uid'][who]}", who, json={"first_name": first, "last_name": last, "phone": phone, "email": email, "notes": notes, "source": source})
    assert st == 200, body
    cid = body.get("_id") or body.get("id")
    S["cids"].append(cid)
    return cid


async def _seed():
    db = get_db()
    now = datetime.now(timezone.utc)
    tag = {"qa_contact_hotfix": True}
    S.update(orgs={}, stores={}, uid={}, tok={}, cids=[], extra_oids=[])
    for k in ("X", "Y"):
        S["orgs"][k] = str((await db.organizations.insert_one({"name": f"QA Hotfix Org {k}", "active": True, "created_at": now, **tag})).inserted_id)
        S["stores"][k] = str((await db.stores.insert_one({"name": f"QA Hotfix Store {k}", "organization_id": S["orgs"][k], "created_at": now, **tag})).inserted_id)
    plan = {"A": ("X", "user"), "A2": ("X", "user"), "MX": ("X", "store_manager"), "OAX": ("X", "org_admin"), "B": ("Y", "user"), "MY": ("Y", "store_manager")}
    for key, (o, role) in plan.items():
        S["uid"][key] = str((await db.users.insert_one({
            "name": f"Hotfix {key}", "first_name": f"Hotfix{key}", "email": f"qa-hotfix-{key.lower()}@invalid.imonsocial.test", "password": hash_password(PW),
            "role": role, "organization_id": S["orgs"][o], "store_id": S["stores"][o], "store_ids": [S["stores"][o]], "is_active": True, "active": True,
            "status": "active", "onboarding_complete": True, "needs_onboarding": False, "phone_verified": True, "created_at": now, "updated_at": now, **tag})).inserted_id)


async def _wipe():
    db = get_db()
    ids = [i for i in S["uid"].values() if i and ObjectId.is_valid(str(i))]   # never None in $in: it would match every doc without a user_id
    cids = [c for c in S["cids"] if c and ObjectId.is_valid(str(c))]
    stores = [s for s in S["stores"].values() if s and ObjectId.is_valid(str(s))]
    for coll in await db.list_collection_names():
        if coll.startswith("system."):
            continue
        if ids + stores:
            await db[coll].delete_many({"user_id": {"$in": ids + stores}})
        if cids:
            await db[coll].delete_many({"contact_id": {"$in": cids}})
    await db.contacts.delete_many({"_id": {"$in": [ObjectId(c) for c in cids] + S["extra_oids"]}})
    await db.contacts.delete_many({"store_id": {"$in": list(S["stores"].values())}})
    await db.bulk_transfers.delete_many({"from_user_id": {"$in": ids}})
    await db.contact_access_audit.delete_many({"contact_id": {"$in": cids}})
    await db.inbound_leads.delete_many({"store_id": {"$in": list(S["stores"].values())}})
    await db.users.delete_many({"_id": {"$in": [ObjectId(i) for i in ids]}})
    await db.stores.delete_many({"_id": {"$in": [ObjectId(i) for i in S["stores"].values()]}})
    await db.organizations.delete_many({"_id": {"$in": [ObjectId(i) for i in S["orgs"].values()]}})


@pytest.fixture(scope="module", autouse=True)
def synthetic():
    run(_seed())
    for key in S["uid"]:
        S["tok"][key] = login(f"qa-hotfix-{key.lower()}@invalid.imonsocial.test", PW)
    S["ca"] = new_contact("A", "John", f"Met at the Jeep event. Drives a {A_SECRET}.")
    S["cb"] = new_contact("B", "John", f"Ford dealership customer. Daughter {B_SECRET} plays violin.", phone=PHONE_FMT)
    db = get_db()
    now = datetime.now(timezone.utc)
    run(db.contacts.update_one({"_id": ObjectId(S["ca"])}, {"$set": {"how_we_met": {"event": "Jeep event", "summary": "Met at the Jeep event", "source": "qa"},
                                                                       "personal_details": {"hobby": f"off-roading in a {A_SECRET}"}}}))
    run(db.contacts.update_one({"_id": ObjectId(S["cb"])}, {"$set": {"how_we_met": {"event": "Ford dealership", "summary": "Ford customer", "source": "qa"},
                                                                       "personal_details": {"family": f"daughter {B_SECRET}"}}}))
    S["memo_a"] = str(run(db.voice_notes.insert_one({"contact_id": S["ca"], "user_id": S["uid"]["A"], "recorded_by_id": S["uid"]["A"], "transcript": f"Jeep event chat, loves his {A_SECRET}", "created_at": now, "duration": 4})).inserted_id)
    S["memo_b"] = str(run(db.voice_notes.insert_one({"contact_id": S["cb"], "user_id": S["uid"]["B"], "recorded_by_id": S["uid"]["B"], "transcript": f"Ford customer, daughter {B_SECRET}", "created_at": now, "duration": 4})).inserted_id)
    yield S
    run(_wipe())


# ---------- 1. Startup consolidation is gone; nothing merges across organizations ----------

def test_startup_phone_consolidation_is_not_scheduled():
    src = open("/app/backend/server.py").read()
    assert "_consolidate_phone_contacts" not in src and 'run_once("consolidate_phone_contacts"' not in src


def test_same_phone_two_orgs_stay_independent():
    a, b = contact(S["ca"]), contact(S["cb"])
    assert a["user_id"] == S["uid"]["A"] and b["user_id"] == S["uid"]["B"] and a["phone"] == b["phone"] and a["email"] == b["email"]
    assert not a.get("merged_into") and not b.get("merged_into")


def test_duplicates_tools_never_cross_organizations():
    st, body = api("GET", f"/contacts/{S['uid']['A']}/duplicates", "A")
    assert st == 200 and S["cb"] not in str(body)
    st, body = api("POST", f"/contacts/{S['uid']['A']}/merge", "A", json={"primary_id": S["ca"], "duplicate_id": S["cb"]})
    assert st == 404, body
    st, _ = api("POST", f"/contacts/{S['uid']['MX']}/merge", "MX", json={"primary_id": S["ca"], "duplicate_id": S["cb"]})
    assert st == 404
    b = contact(S["cb"])
    assert b["user_id"] == S["uid"]["B"] and b.get("status") == "active" and not b.get("merged_into")
    assert run(get_db().voice_notes.count_documents({"contact_id": S["cb"]})) == 1


def test_same_org_duplicates_still_work():
    dup = new_contact("A", "John", "second card for the same guy")
    st, body = api("GET", f"/contacts/{S['uid']['A']}/duplicates", "A")
    assert st == 200 and dup in str(body) and S["ca"] in str(body)
    st, body = api("POST", f"/contacts/{S['uid']['A']}/merge", "A", json={"primary_id": S["ca"], "duplicate_id": dup})
    assert st == 200, body
    assert contact(dup)["status"] == "merged"


# ---------- 2. A valid contact id never grants access by itself ----------

def _cross_reads(who, uid_key):
    u, b = S["uid"][uid_key], S["cb"]
    return [f"/contacts/{u}/{b}", f"/contacts/{u}/{b}/personal-details", f"/contacts/{u}/{b}/events", f"/contacts/{u}/{b}/stats",
            f"/contacts/{u}/{b}/suggested-actions", f"/contacts/{u}/{b}/action-progress", f"/contacts/{u}/{b}/photos/all", f"/contacts/{u}/{b}/photo/full",
            f"/contacts/{u}/{b}/campaign-journey", f"/contacts/{u}/{b}/referrals", f"/contacts/{u}/{b}/purchases", f"/contacts/{u}/{b}/share",
            f"/contacts/{u}/{b}/share/text", f"/contacts/{u}/{b}/share/vcard", f"/voice-notes/{u}/{b}", f"/voice-notes/{u}/{b}/{S['memo_b']}",
            f"/ai-outreach/relationship-brief/{u}/{b}", f"/crm-push/{u}/{b}/preview", f"/contact-intel/{u}/{b}", f"/calls/{u}/contact/{b}",
            f"/tasks/{u}/contact/{b}", f"/contact-files/{u}/contact/{b}", f"/relationship-health/{u}/contact/{b}", f"/relationship-health/{u}/advocates/{b}/thank",
            f"/messages/scheduled/{u}/{b}", f"/home/draft/{u}/{b}", f"/ai-reply/history/{b}", f"/consent/contact/{b}", f"/sold-workflow/contact/{b}",
            f"/contact-ask/{b}", f"/intel/contacts/{b}/facts", f"/intel/contacts/{b}/brief", f"/intel/contacts/{b}/timeline", f"/appraisals/vehicles/{b}"]


@pytest.mark.parametrize("who", ["A", "MX", "OAX"])
def test_other_org_contact_reads_are_404(who):
    leaks = []
    for p in _cross_reads(who, who):
        st, body = api("GET", p, who)
        blob = str(body)
        if st == 200 or B_SECRET in blob or "Ford" in blob:
            leaks.append((p.replace(S["cb"], "{B}"), st))
    assert not leaks, leaks


@pytest.mark.parametrize("who", ["A", "MX"])
def test_other_org_contact_writes_are_refused_and_change_nothing(who):
    u, b = S["uid"][who], S["cb"]
    before = contact(b)
    writes = [
        ("PUT", f"/contacts/{u}/{b}", {"first_name": "Hijacked", "notes": "x"}),
        ("PATCH", f"/contacts/{u}/{b}/personal-details", {"personal_details": {"probe": "x"}}),
        ("PATCH", f"/contacts/{u}/{b}/toggle-automation", {"field": "birthday"}),
        ("PATCH", f"/contacts/{u}/{b}/tags", {"tags": ["Hijacked"]}),
        ("PATCH", f"/contacts/{u}/{b}/birthday", {"birthday": "01-01"}),
        ("PATCH", f"/contacts/{u}/{b}/vehicle", {"vehicle": "x"}),
        ("POST", f"/contacts/{u}/{b}/events", {"event_type": "note", "title": "probe"}),
        ("POST", f"/contacts/{u}/{b}/share/link", {"include_private": True}),
        ("POST", f"/contacts/{u}/{b}/purchases", {"title": "probe"}),
        ("POST", f"/crm/mark-copied/{u}/{b}", None),
        ("POST", f"/crm/timeline-token/{u}/{b}", None),
        ("POST", f"/crm-push/{u}/bulk", {"email": "crm@invalid.imonsocial.test", "contact_ids": [b]}),
        ("DELETE", f"/voice-notes/{u}/{b}/{S['memo_b']}", None),
        ("DELETE", f"/contacts/{u}/{b}", None),
        ("POST", f"/campaigns/birthday/update/{b}?birthday=01-01", None),
        ("POST", f"/sold-workflow/revalidate/{b}", None),
    ]
    bad = []
    for m, p, body in writes:
        st, resp = api(m, p, who, **({"json": body} if body is not None else {}))
        if st not in (403, 404):
            bad.append((m, p.replace(b, "{B}").replace(u, "{me}"), st))
    after = contact(b)
    assert after is not None, "B's contact was deleted"
    for f in ("first_name", "notes", "tags", "personal_details", "disabled_automations", "birthday", "vehicle", "crm_link_copied_at", "crm_link_token", "user_id"):
        assert after.get(f) == before.get(f), f
    assert run(get_db().voice_notes.count_documents({"_id": ObjectId(S["memo_b"])})) == 1
    assert run(get_db().contact_shares.count_documents({"contact_id": b})) == 0
    assert not bad, bad


def test_own_and_managed_contacts_still_open():
    a, ca = S["uid"]["A"], S["ca"]
    for who in ("A", "MX", "OAX"):
        u = S["uid"][who] if who != "A" else a
        for p in (f"/contacts/{a}/{ca}", f"/contacts/{a}/{ca}/personal-details", f"/contacts/{a}/{ca}/events", f"/voice-notes/{a}/{ca}", f"/contacts/{a}/{ca}/share/text"):
            st, body = api("GET", p, who)
            assert st == 200, (who, p, st)
        assert u
    st, body = api("GET", f"/voice-notes/{a}/{ca}", "MX")
    assert A_SECRET in str(body)
    st, body = api("PATCH", f"/contacts/{a}/{ca}/personal-details", "A", json={"personal_details": {"kids": "two"}})
    assert st == 200 and contact(ca)["personal_details"].get("kids") in ("two", ["two"])
    st, _ = api("PATCH", f"/contacts/{a}/{ca}/toggle-automation", "A", json={"field": "birthday"})
    assert st == 200


# ---------- 3. Jessi follows the caller's boundaries ----------

def test_jessi_focus_and_context_respect_org_boundaries():
    from services import live_voice as lv
    from services.jessie_service import _build_contact_context
    db = get_db()
    users = {k: run(db.users.find_one({"_id": ObjectId(S["uid"][k])})) for k in ("A", "MX", "OAX", "MY")}
    assert run(lv.focus_contact(db, users["MX"], S["cb"])) is None
    assert run(lv.focus_contact(db, users["OAX"], S["cb"])) is None
    assert run(lv.focus_contact(db, users["A"], S["cb"])) is None
    assert run(lv.focus_contact(db, users["MX"], S["ca"])) is not None
    assert run(lv.focus_contact(db, users["MY"], S["cb"])) is not None
    assert run(_build_contact_context(S["cb"], S["uid"]["MX"])) == ""
    assert A_SECRET in run(_build_contact_context(S["ca"], S["uid"]["MX"]))


def test_jessi_memory_search_is_owner_scoped():
    from services import memory_search as ms
    db = get_db()
    ua, ub = (run(db.users.find_one({"_id": ObjectId(S["uid"][k])})) for k in ("A", "B"))
    a_hits = run(ms.scan(db, ua, ["Jeep"]))
    assert a_hits and S["ca"] in str(a_hits) and S["cb"] not in str(a_hits)
    assert not run(ms.scan(db, ub, ["Jeep"]))
    assert not run(ms.scan(db, ua, [B_SECRET]))


def test_jessi_chat_manager_with_other_org_contact_in_focus():
    st, body = api("POST", "/jessie/chat", "MX", json={"user_id": S["uid"]["MX"], "contact_id": S["cb"], "message": "What do you know about this person? List every family detail on file."})
    assert st == 200 and B_SECRET not in str(body)


def test_jessi_chat_find_by_event():
    st, body = api("POST", "/jessie/chat", "A", json={"user_id": S["uid"]["A"], "message": "Find the guy I met at the Jeep event. What do I know about him?"})
    assert st == 200 and B_SECRET not in str(body) and "Ford" not in str(body)


# ---------- 4. Bulk transfer ----------

def test_bulk_transfer_scope_and_personal_contacts():
    db = get_db()
    org_c = new_contact("A2", "Org", "dealership customer", phone="+18015550161", email="")
    per_c = new_contact("A2", "Personal", "my cousin", phone="+18015550162", email="", source="phone_import")
    assert contact(per_c)["ownership_type"] == "personal"
    convs = {c: str(run(db.conversations.insert_one({"user_id": S["uid"]["A2"], "contact_id": c, "status": "active", "created_at": datetime.now(timezone.utc)})).inserted_id) for c in (org_c, per_c)}
    # outsiders: another org's manager, a plain rep
    st, _ = api("POST", f"/admin/team/bulk-transfer?user_id={S['uid']['MY']}", "MY", json={"from_user_id": S["uid"]["A2"], "to_user_id": S["uid"]["B"]})
    assert st == 403
    st, _ = api("POST", f"/admin/team/bulk-transfer?user_id={S['uid']['A']}", "A", json={"from_user_id": S["uid"]["A2"], "to_user_id": S["uid"]["A"]})
    assert st == 403
    st, _ = api("POST", f"/admin/team/bulk-transfer?user_id={S['uid']['MX']}", "MX", json={"from_user_id": S["uid"]["A2"], "to_user_id": S["uid"]["B"]})
    assert st == 403
    st, prev = api("GET", f"/admin/team/bulk-transfer/preview?user_id={S['uid']['MY']}&from_user_id={S['uid']['A2']}", "MY")
    assert st == 403
    st, prev = api("GET", f"/admin/team/bulk-transfer/preview?user_id={S['uid']['MX']}&from_user_id={S['uid']['A2']}", "MX")
    assert st == 200 and prev["items_to_transfer"]["contacts"] == 1 and prev["personal_contacts_kept"] == 1
    assert contact(org_c)["user_id"] == S["uid"]["A2"]
    # legitimate: store manager moves A2's dealership book to A (same store)
    st, body = api("POST", f"/admin/team/bulk-transfer?user_id={S['uid']['MX']}", "MX", json={"from_user_id": S["uid"]["A2"], "to_user_id": S["uid"]["A"], "reason": "QA hotfix"})
    assert st == 200, body
    assert contact(org_c)["user_id"] == S["uid"]["A"] and contact(per_c)["user_id"] == S["uid"]["A2"]
    assert run(db.conversations.find_one({"_id": ObjectId(convs[org_c])}))["user_id"] == S["uid"]["A"]
    assert run(db.conversations.find_one({"_id": ObjectId(convs[per_c])}))["user_id"] == S["uid"]["A2"]
    st, hist = api("GET", f"/admin/team/bulk-transfer/history?user_id={S['uid']['MY']}", "MY")
    assert st == 200 and "QA hotfix" not in str(hist)
    st, hist = api("GET", f"/admin/team/bulk-transfer/history?user_id={S['uid']['MX']}", "MX")
    assert st == 200 and "QA hotfix" in str(hist)


# ---------- 5. Lead routing never takes a rep's contact ----------

def _lead(phone, first="Lead", last="Hotfix", email=""):
    from routers.lead_intake import process_inbound_lead
    source = {"_id": ObjectId(), "name": "QA Hotfix Source", "store_id": S["stores"]["X"], "assignment_method": "round_robin", "workflow_user_ids": [S["uid"]["A2"]],
              "returning_stale_days": 30, "contact_mode": "text_only", "intake_text": ""}
    normalized = {"first_name": first, "last_name": last, "phone": phone, "email": email, "no_intake_text": True, "is_test": True, "source_name": "QA Hotfix"}
    res = run(process_inbound_lead(normalized, source, get_db()))
    lead = run(get_db().inbound_leads.find_one({"_id": ObjectId(str(res.get("_id") or res.get("lead_id") or res.get("id")))})) if isinstance(res, dict) else None
    lead = lead or run(get_db().inbound_leads.find_one({"phone": phone, "store_id": S["stores"]["X"]}, sort=[("created_at", -1)]))
    S["cids"].append(lead["contact_id"])
    return lead


def _quiet(cid, days=80):
    run(get_db().contacts.update_one({"_id": ObjectId(cid)}, {"$set": {"created_at": datetime.now(timezone.utc) - timedelta(days=days)}}))
    run(get_db().contact_events.delete_many({"contact_id": cid}))


def test_lead_routing_never_moves_a_quiet_reps_personal_contact():
    per = new_contact("A", "Pat", "personal friend", phone="+18015550171", email="", source="phone_import")
    _quiet(per)
    lead = _lead("+18015550171", "Pat", "Hotfix")
    c = contact(per)
    assert c["user_id"] == S["uid"]["A"] and "Possible Duplicate" not in (c.get("tags") or [])
    assert lead["contact_id"] != per
    new = contact(lead["contact_id"])
    assert new["user_id"] == S["uid"]["A2"] and new.get("possible_duplicate_of") == per


def test_lead_routing_never_moves_a_quiet_reps_dealership_contact():
    org = new_contact("A", "Quinn", "dealership customer", phone="+18015550172", email="")
    _quiet(org)
    run(get_db().voice_notes.insert_one({"contact_id": org, "user_id": S["uid"]["A"], "transcript": "private memo", "created_at": datetime.now(timezone.utc)}))
    lead = _lead("+18015550172", "Quinn", "Hotfix")
    assert contact(org)["user_id"] == S["uid"]["A"]
    assert lead["contact_id"] != org and contact(lead["contact_id"])["user_id"] == S["uid"]["A2"]
    assert run(get_db().voice_notes.count_documents({"contact_id": lead["contact_id"]})) == 0


def test_lead_routing_active_owner_still_gets_their_customer():
    org = new_contact("A", "Riley", "engaged customer", phone="+18015550173", email="")
    lead = _lead("+18015550173", "Riley", "Hotfix")
    assert lead["contact_id"] == org and lead["routing_kind"] == "returning_owner" and lead["assigned_to"] == S["uid"]["A"]
    assert contact(org)["user_id"] == S["uid"]["A"]


def test_lead_routing_store_owned_lead_is_still_assigned():
    oid = run(get_db().contacts.insert_one({"user_id": S["stores"]["X"], "store_id": S["stores"]["X"], "first_name": "Sam", "last_name": "Hotfix", "phone": "+18015550174",
                                            "ownership_type": "org", "status": "active", "source": "internet_lead", "created_at": datetime.now(timezone.utc)})).inserted_id
    S["cids"].append(str(oid))
    lead = _lead("+18015550174", "Sam", "Hotfix")
    assert lead["contact_id"] == str(oid) and contact(str(oid))["user_id"] == S["uid"]["A2"]


def test_lead_name_only_match_never_edits_a_personal_contact():
    per = new_contact("A", "Morgan", "personal, no phone saved", phone="", email="", last="Uniquehotfix", source="phone_import")
    lead = _lead("+18015550175", "Morgan", "Uniquehotfix")
    c = contact(per)
    assert lead["contact_id"] != per and not c.get("phone")


def test_inbox_handoff_keeps_personal_contacts():
    from services import inboxes
    per = new_contact("A", "Casey", "personal", phone="+18015550176", email="", source="phone_import")
    org = new_contact("A", "Drew", "dealership", phone="+18015550177", email="")
    run(inboxes._move_book(get_db(), per, S["uid"]["A"], S["uid"]["A2"]))
    run(inboxes._move_book(get_db(), org, S["uid"]["A"], S["uid"]["A2"]))
    assert contact(per)["user_id"] == S["uid"]["A"] and contact(org)["user_id"] == S["uid"]["A2"]


# ---------- 6. Existing workflows: campaign enrollment ----------

def test_campaign_enrollment_own_contact_ok_other_org_refused():
    db = get_db()
    camp = str(run(db.campaigns.insert_one({"user_id": S["uid"]["A"], "name": "QA Hotfix Campaign", "type": "custom", "active": True,
                                            "sequences": [{"step": 1, "delay_days": 3, "message_template": "Hi {first_name}", "channel": "sms"}],
                                            "created_at": datetime.now(timezone.utc)})).inserted_id)
    st, body = api("POST", f"/campaigns/{S['uid']['A']}/{camp}/enroll/{S['cb']}", "A")
    assert st == 404
    st, body = api("POST", f"/campaigns/{S['uid']['A']}/{camp}/enroll/{S['ca']}", "A")
    assert st == 200, body
    assert run(db.campaign_enrollments.count_documents({"contact_id": S["ca"], "campaign_id": camp})) == 1
    run(db.campaign_enrollments.delete_many({"campaign_id": camp}))
    run(db.campaign_pending_sends.delete_many({"campaign_id": camp}))
    run(db.campaigns.delete_one({"_id": ObjectId(camp)}))


# ---------- 8. Super-admin cross-organization access is audited ----------

def test_super_admin_cross_org_access_is_audited_without_content():
    forest = login("forest@imosapp.com", qa_creds.password_for("forest@imosapp.com"))
    r = requests.get(f"{BASE}/api/contacts/{S['uid']['B']}/{S['cb']}/personal-details", headers={"Authorization": f"Bearer {forest}"}, timeout=30)
    assert r.status_code == 200
    rows = run(get_db().contact_access_audit.find({"contact_id": S["cb"]}).to_list(10))
    assert rows, "no audit row"
    row = rows[0]
    assert row["actor_role"] == "super_admin" and row["owner_id"] == S["uid"]["B"] and row["owner_org_id"] == S["orgs"]["Y"]
    assert "personal-details" in row["action"] and row["reason"] == "super_admin_platform_access"
    assert B_SECRET not in str(rows) and PHONE not in str(rows) and "John" not in str(rows)
    r = requests.get(f"{BASE}/api/admin/contact-access-audit?contact_id={S['cb']}", headers={"Authorization": f"Bearer {forest}"}, timeout=30)
    assert r.status_code == 200 and r.json()["rows"]
    st, _ = api("GET", f"/admin/contact-access-audit?contact_id={S['cb']}", "MX")
    assert st == 403
    # managers inside their own org are not "cross-organization": nothing logged for them
    n = run(get_db().contact_access_audit.count_documents({"contact_id": S["ca"]}))
    api("GET", f"/contacts/{S['uid']['A']}/{S['ca']}", "MX")
    assert run(get_db().contact_access_audit.count_documents({"contact_id": S["ca"]})) == n


# ---------- regressions in other tenant-boundary fixes ----------

def test_partner_agreement_dedupe_is_scoped():
    src = open("/app/backend/routers/partners.py").read()
    assert re.search(r'"\$and": \[\{"\$or": user_scope\}, \{"\$or": or_clauses\}\]', src)


def test_inbound_sms_name_enrichment_stays_in_the_org():
    src = open("/app/backend/routers/twilio_webhooks.py").read()
    assert '"user_id": {"$in": _peers}' in src
