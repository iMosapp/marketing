"""Contact ownership / isolation audit: non-destructive probes on SYNTHETIC data in the preview environment only.

Creates two throwaway orgs (X, Y), one store each, rep A + store manager MX in X, rep B + store manager MY in Y
(@invalid.imonsocial.test), gives A and B the same person (same phone + email, different private notes / memos),
then probes the API and the backend functions. Wipes ONLY the ids it created. Never runs the startup consolidation
job: its matching rule is replayed read-only. Each test asserts the CURRENT behaviour and records a verdict in RESULTS.

Run: cd /app/backend && set -a && . ./.env && . ../frontend/.env && set +a && \
     python -m pytest /app/docs/audits/contacts/isolation_tests/test_contact_isolation.py -q -p no:cacheprovider
"""
import asyncio
import json
import os
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pytest
import requests
from bson import ObjectId
from pymongo import MongoClient

sys.path.insert(0, "/app/backend")
from routers.auth import hash_password  # noqa: E402

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
PW = "AuditIso123!"
PHONE = "+18015550142"          # fictional 555-01xx range
PHONE_FMT = "(801) 555-0142"
EMAIL = "john.audit@invalid.imonsocial.test"
A_SECRET = "Rubicon"            # only in A's private notes / memo
B_SECRET = "Zelda"              # only in B's private notes / memo
RESULTS = {}
S = {}


def verdict(key, status, detail):
    RESULTS[key] = {"status": status, "detail": detail}


def api(method, path, who=None, **kw):
    h = {"Authorization": f"Bearer {S['tok'][who]}"} if who else {}
    r = requests.request(method, f"{BASE}/api{path}", headers=h, timeout=90, **kw)
    try:
        return r.status_code, r.json()
    except ValueError:
        return r.status_code, r.text


def mongo():
    return MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


@pytest.fixture(scope="module", autouse=True)
def synthetic():
    m = mongo()
    S["m"] = m
    now = datetime.now(timezone.utc)
    tag = {"qa_contact_audit": True}
    orgs, stores, users = {}, {}, {}
    for k in ("X", "Y"):
        orgs[k] = m.organizations.insert_one({"name": f"QA Contact Audit Org {k}", "active": True, "created_at": now, **tag}).inserted_id
        stores[k] = m.stores.insert_one({"name": f"QA Contact Audit Store {k}", "organization_id": str(orgs[k]), "created_at": now, **tag}).inserted_id
    plan = {"A": ("X", "user"), "MX": ("X", "store_manager"), "B": ("Y", "user"), "MY": ("Y", "store_manager")}
    for key, (o, role) in plan.items():
        users[key] = m.users.insert_one({
            "name": f"Audit {key}", "first_name": f"Audit{key}", "email": f"qa-contact-audit-{key.lower()}@invalid.imonsocial.test",
            "password": hash_password(PW), "role": role, "organization_id": str(orgs[o]), "store_id": str(stores[o]),
            "store_ids": [str(stores[o])], "is_active": True, "status": "active", "onboarding_complete": True, "needs_onboarding": False,
            "phone_verified": True, "created_at": now, "updated_at": now, **tag}).inserted_id
    S["uid"] = {k: str(v) for k, v in users.items()}
    S["tok"] = {}
    for key in plan:
        r = requests.post(f"{BASE}/api/auth/login", json={"email": f"qa-contact-audit-{key.lower()}@invalid.imonsocial.test", "password": PW}, timeout=30)
        assert r.status_code == 200, r.text
        S["tok"][key] = r.json()["token"]
    yield S
    ids = list(S["uid"].values())
    cids = [ObjectId(c) for c in S.get("cids", [])]
    for coll in m.list_collection_names():
        if coll.startswith("system."):
            continue
        m[coll].delete_many({"user_id": {"$in": ids}})
        if S.get("cids"):
            m[coll].delete_many({"contact_id": {"$in": S["cids"]}})
    m.contacts.delete_many({"_id": {"$in": cids}})
    m.transfer_logs.delete_many({"from_user_id": {"$in": ids}})
    m.bulk_transfers.delete_many({"from_user_id": {"$in": ids}})
    m.users.delete_many({"_id": {"$in": list(users.values())}})
    m.stores.delete_many({"_id": {"$in": list(stores.values())}})
    m.organizations.delete_many({"_id": {"$in": list(orgs.values())}})
    os.makedirs("/app/docs/audits/contacts/isolation_tests", exist_ok=True)
    with open("/app/docs/audits/contacts/isolation_tests/results.json", "w") as f:
        json.dump({"ran_at": now.isoformat(), "results": RESULTS}, f, indent=1)


def _create(who, first, notes, phone=PHONE, email=EMAIL, last="Audit"):
    st, body = api("POST", f"/contacts/{S['uid'][who]}", who, json={"first_name": first, "last_name": last, "phone": phone, "email": email, "notes": notes, "source": "manual"})
    assert st == 200, body
    S.setdefault("cids", []).append(body["_id"] if "_id" in body else body["id"])
    return S["cids"][-1]


def test_01_same_person_two_reps_two_orgs_independent():
    a = _create("A", "John", f"Met at the Jeep event downtown. Drives a {A_SECRET}.", phone=PHONE)
    b = _create("B", "John", f"Knows him from the Ford dealership. Daughter {B_SECRET} plays violin.", phone=PHONE_FMT)
    S["ca"], S["cb"] = a, b
    m = S["m"]
    ca, cb = m.contacts.find_one({"_id": ObjectId(a)}), m.contacts.find_one({"_id": ObjectId(b)})
    m.contacts.update_one({"_id": ObjectId(a)}, {"$set": {"how_we_met": {"event": "Jeep event", "summary": "Met at the Jeep event", "source": "audit"}}})
    m.contacts.update_one({"_id": ObjectId(b)}, {"$set": {"how_we_met": {"event": "Ford dealership", "summary": "Ford dealership customer", "source": "audit"}}})
    m.voice_notes.insert_many([
        {"contact_id": a, "user_id": S["uid"]["A"], "recorded_by_id": S["uid"]["A"], "transcript": f"Great chat at the Jeep event, loves his {A_SECRET}.", "transcription_status": "done", "created_at": datetime.now(timezone.utc), "duration": 5},
        {"contact_id": b, "user_id": S["uid"]["B"], "recorded_by_id": S["uid"]["B"], "transcript": f"Ford customer, daughter {B_SECRET} plays violin.", "transcription_status": "done", "created_at": datetime.now(timezone.utc), "duration": 5},
    ])
    ok = a != b and ca["user_id"] == S["uid"]["A"] and cb["user_id"] == S["uid"]["B"] and ca["phone"] == cb["phone"]
    verdict("same_phone_two_users_two_orgs", "VERIFIED" if ok else "DEFECT",
            f"two records, owners A/B, stored phones equal after normalisation={ca['phone'] == cb['phone']}, ownership_type={ca.get('ownership_type')}")
    assert ok


def test_02_lists_and_duplicate_check_are_owner_scoped():
    st, body = api("GET", f"/contacts/{S['uid']['A']}", "A")
    rows = body if isinstance(body, list) else body.get("contacts", [])
    ids = {str(r.get("_id") or r.get("id")) for r in rows}
    st2, dup = api("GET", f"/contacts/{S['uid']['A']}/check-duplicate?phone={PHONE}", "A")
    leaked = S["cb"] in ids or S["cb"] in json.dumps(dup)
    verdict("list_and_check_duplicate_scope", "VERIFIED" if (S["ca"] in ids and not leaked) else "DEFECT", f"list={st}, check-duplicate={st2}, B record visible to A={leaked}")
    assert not leaked


def test_03_cross_owner_path_is_refused():
    st, _ = api("GET", f"/contacts/{S['uid']['B']}/{S['cb']}", "A")
    st2, _ = api("GET", f"/contacts/{S['uid']['A']}/{S['cb']}", "A")
    st3, _ = api("GET", f"/voice-notes/{S['uid']['A']}/{S['cb']}", "A")
    st4, _ = api("GET", f"/jessie/history/{S['uid']['B']}", "A")
    ok = st == 403 and st2 == 404 and st3 in (403, 404) and st4 == 403
    verdict("idor_core_contact_routes", "VERIFIED" if ok else "DEFECT",
            f"B path as A={st}, B contact under A path={st2}, B voice notes under A path={st3}, B Jessi history={st4}")
    assert ok


def test_04_contact_subroutes_check_ownership():
    a, b = S["uid"]["A"], S["cb"]
    probes = {
        "GET personal-details": api("GET", f"/contacts/{a}/{b}/personal-details", "A"),
        "GET photos/all": api("GET", f"/contacts/{a}/{b}/photos/all", "A"),
        "GET photo/full": api("GET", f"/contacts/{a}/{b}/photo/full", "A"),
        "GET campaign-journey": api("GET", f"/contacts/{a}/{b}/campaign-journey", "A"),
        "PATCH toggle-automation": api("PATCH", f"/contacts/{a}/{b}/toggle-automation", "A", json={"field": "birthday"}),
        "PATCH personal-details": api("PATCH", f"/contacts/{a}/{b}/personal-details", "A", json={"personal_details": {"audit_probe": "written by rep A"}}),
    }
    after = S["m"].contacts.find_one({"_id": ObjectId(b)}, {"personal_details": 1, "notes": 1, "disabled_automations": 1})
    leaked_read = B_SECRET in json.dumps(probes["GET personal-details"][1], default=str)
    wrote = (after.get("personal_details") or {}).get("audit_probe") == "written by rep A"
    toggled = "birthday" in (after.get("disabled_automations") or [])
    summary = {k: v[0] for k, v in probes.items()}
    status = "DEFECT" if (leaked_read or wrote or toggled) else "VERIFIED"
    verdict("idor_contact_subroutes", status, f"status codes={summary}; A read B private notes={leaked_read}; A wrote B personal_details={wrote}; A toggled B automation={toggled}")


def test_05_jessi_keyword_memory_is_owner_scoped():
    from services import memory_search as ms
    from motor.motor_asyncio import AsyncIOMotorClient

    async def go():
        db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
        ua = await db.users.find_one({"_id": ObjectId(S["uid"]["A"])})
        ub = await db.users.find_one({"_id": ObjectId(S["uid"]["B"])})
        return await ms.scan(db, ua, ["Jeep"]), await ms.scan(db, ub, ["Jeep"]), await ms.scan(db, ua, [B_SECRET])
    a_jeep, b_jeep, a_zelda = asyncio.run(go())
    blob = json.dumps(a_jeep, default=str)
    ok = S["ca"] in blob and S["cb"] not in blob and not b_jeep and not a_zelda
    verdict("jessi_memory_scan_scope", "VERIFIED" if ok else "DEFECT",
            f"A 'Jeep' hits={len(a_jeep)} (A contact found={S['ca'] in blob}, B contact found={S['cb'] in blob}); B 'Jeep' hits={len(b_jeep)}; A search for B-only word hits={len(a_zelda)}")
    assert ok


def test_06_jessi_chat_find_the_guy_from_the_jeep_event():
    st, body = api("POST", "/jessie/chat", "A", json={"user_id": S["uid"]["A"], "message": "Find the guy I met at the Jeep event. What do I know about him?"})
    text = json.dumps(body, default=str)
    ok = st == 200 and B_SECRET not in text and "Ford" not in text
    verdict("jessi_chat_find_by_event", "VERIFIED" if ok else "DEFECT",
            f"status={st}; mentions A-only detail={A_SECRET in text or 'Jeep' in text}; mentions B-only detail={B_SECRET in text or 'Ford' in text}")
    assert ok


def test_07_jessi_focus_contact_across_orgs():
    from services import live_voice as lv
    from motor.motor_asyncio import AsyncIOMotorClient

    async def go():
        db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
        rep_a = await db.users.find_one({"_id": ObjectId(S["uid"]["A"])})
        mx = await db.users.find_one({"_id": ObjectId(S["uid"]["MX"])})
        by_rep = await lv.focus_contact(db, rep_a, S["cb"])
        by_mgr = await lv.focus_contact(db, mx, S["cb"])
        return by_rep, by_mgr
    by_rep, by_mgr = asyncio.run(go())
    st, body = api("POST", "/jessie/chat", "MX", json={"user_id": S["uid"]["MX"], "contact_id": S["cb"], "message": "What do you know about this person? List every family detail and note on file."})
    text = json.dumps(body, default=str)
    leaked = by_mgr is not None
    verdict("jessi_focus_contact_cross_org", "DEFECT" if leaked else "VERIFIED",
            f"rep A focus on B contact -> {'returned' if by_rep else 'None'}; store manager of org X focus on org Y contact -> {'returned' if by_mgr else 'None'}; "
            f"chat as MX with B contact in focus: status={st}, reply contains B-only detail={B_SECRET in text}")


def test_08_campaign_enroll_of_another_users_contact():
    st, camp = api("POST", f"/campaigns/{S['uid']['A']}", "A", json={"name": "QA Audit Campaign", "type": "custom", "active": False, "sequences": [{"step": 1, "delay_days": 1, "message_template": "Hi {first_name}", "channel": "sms"}]})
    cid = str((camp or {}).get("_id") or (camp or {}).get("id") or "") if st == 200 else ""
    if not cid:  # reps may not create campaigns on this store: seed a synthetic one owned by A
        cid = str(S["m"].campaigns.insert_one({"user_id": S["uid"]["A"], "name": "QA Audit Campaign", "type": "custom", "active": True, "sequences": [{"step": 1, "delay_days": 1, "message_template": "Hi", "channel": "sms"}], "created_at": datetime.now(timezone.utc), "qa_contact_audit": True}).inserted_id)
    st2, body = api("POST", f"/campaigns/{S['uid']['A']}/{cid}/enroll/{S['cb']}", "A")
    enrolled = S["m"].campaign_enrollments.count_documents({"contact_id": S["cb"]})
    ok = st2 in (403, 404) and enrolled == 0
    verdict("campaign_enroll_cross_user", "VERIFIED" if ok else "DEFECT", f"create campaign={st}; enroll B contact into A campaign={st2}; enrollments on B contact={enrolled}")
    assert ok


def test_09_team_transfer_by_a_plain_rep():
    st, body = api("POST", "/team/transfer", "A", json={"from_user_id": S["uid"]["B"], "to_user_id": S["uid"]["A"]})
    moved = S["m"].contacts.count_documents({"_id": ObjectId(S["cb"]), "user_id": S["uid"]["A"]})
    if st == 404:
        verdict("team_transfer_route", "NOT REACHABLE", "POST /api/team/transfer answers 404: routers/team.py is not mounted in server.py (dead code)")
    else:
        verdict("team_transfer_route", "DEFECT" if moved else "VERIFIED", f"status={st}; B contact moved to A={bool(moved)}")
    st2, _ = api("POST", f"/admin/team/bulk-transfer?user_id={S['uid']['A']}", "A", json={"from_user_id": S["uid"]["B"], "to_user_id": S["uid"]["A"]})
    st3, _ = api("POST", f"/admin/team/bulk-transfer?user_id={S['uid']['MX']}", "MX", json={"from_user_id": S["uid"]["B"], "to_user_id": S["uid"]["A"], "reason": "QA audit probe"})
    moved2 = S["m"].contacts.count_documents({"_id": ObjectId(S["cb"]), "user_id": S["uid"]["A"]})
    verdict("admin_bulk_transfer_route", "DEFECT" if moved2 else "VERIFIED", f"rep A={st2}; store manager of org X moving an org Y rep's book={st3}; B contact moved={bool(moved2)}")
    S["m"].contacts.update_one({"_id": ObjectId(S["cb"])}, {"$set": {"user_id": S["uid"]["B"]}})  # put the synthetic record back if a probe moved it


def test_10_startup_consolidation_rule_replayed_read_only():
    """Replays server.py _consolidate_phone_contacts matching (lines 1786-1825) without writing anything."""
    m = S["m"]
    lead = m.contacts.insert_one({"user_id": S["uid"]["B"], "first_name": "Lead", "last_name": "(0142)", "name": "Lead (0142)", "phone": PHONE, "status": "active",
                                  "ownership_type": "org", "source": "inbound_sms", "created_at": datetime.now(timezone.utc), "qa_contact_audit": True}).inserted_id
    S["cids"].append(str(lead))

    def quality(c):
        n = (c.get("name") or f"{c.get('first_name', '')} {c.get('last_name', '')}".strip()).strip()
        if not n or n in {"Contact", "Unknown", "New Lead", ""}:
            return 0
        return 1 if n.startswith("Lead (") else 2

    def plan(rows):
        groups = defaultdict(list)
        for c in rows:
            d = "".join(ch for ch in (c.get("phone") or "") if ch.isdigit())
            if not d:
                continue
            groups["1" + d if len(d) == 10 else d].append(c)
        pairs = []
        for g in groups.values():
            if len(g) < 2:
                continue
            g.sort(key=quality, reverse=True)
            for loser in g[1:]:
                if quality(loser) < quality(g[0]):
                    pairs.append((loser, g[0]))
        return pairs

    ours = list(m.contacts.find({"_id": {"$in": [ObjectId(c) for c in S["cids"]]}}, {"phone": 1, "name": 1, "first_name": 1, "last_name": 1, "user_id": 1}))
    pairs = plan(ours)
    cross = [(lo, w) for lo, w in pairs if str(lo.get("user_id")) != str(w.get("user_id"))]
    every = list(m.contacts.find({"phone": {"$exists": True, "$ne": ""}}, {"phone": 1, "name": 1, "first_name": 1, "last_name": 1, "user_id": 1}))
    all_pairs = plan(every)
    all_cross = sum(1 for lo, w in all_pairs if str(lo.get("user_id")) != str(w.get("user_id")))
    signature = m.contacts.count_documents({"merged_into": {"$exists": True}, "status": {"$nin": ["merged"]}})
    verdict("startup_phone_consolidation", "DEFECT" if cross else "VERIFIED",
            f"synthetic: org Y rep B's unnamed 'Lead (0142)' would be folded into org X rep A's named contact={bool(cross)}; "
            f"whole preview DB right now: {len(all_pairs)} merges planned, {all_cross} across different owners; "
            f"preview records carrying the consolidation signature (merged_into set, status not merged)={signature}")
    assert cross  # documents the defect; flip once fixed


def test_11_concurrent_creates_same_phone_one_user():
    def one(i):
        return api("POST", f"/contacts/{S['uid']['A']}", "A", json={"first_name": "Race", "last_name": f"Audit{i}", "phone": "+18015550177", "source": "manual"})
    with ThreadPoolExecutor(5) as ex:
        res = list(ex.map(one, range(5)))
    for st, body in res:
        if st == 200:
            S["cids"].append(body.get("_id") or body.get("id"))
    n = S["m"].contacts.count_documents({"user_id": S["uid"]["A"], "phone": "+18015550177"})
    verdict("concurrent_create_same_phone", "PARTIAL", f"5 parallel manual creates -> {n} records (manual create never dedupes server-side; the app warns via check-duplicate first)")


def test_12_same_email_two_users_and_ownership_default():
    m = S["m"]
    a = m.contacts.find_one({"_id": ObjectId(S["ca"])})
    b = m.contacts.find_one({"_id": ObjectId(S["cb"])})
    ok = a["email"] == b["email"] and a["user_id"] != b["user_id"]
    verdict("same_email_two_users", "VERIFIED" if ok else "DEFECT", f"same email kept on both records; ownership_type on a manual create={a.get('ownership_type')}")
    assert ok


def test_13_delete_cascade():
    cid = _create("A", "Delete", "throwaway", phone="+18015550188", email="")
    S["m"].voice_notes.insert_one({"contact_id": cid, "user_id": S["uid"]["A"], "transcript": "x", "created_at": datetime.now(timezone.utc)})
    st, _ = api("DELETE", f"/contacts/{S['uid']['A']}/{cid}", "A")
    gone = S["m"].contacts.count_documents({"_id": ObjectId(cid)}) == 0
    left = {c: S["m"][c].count_documents({"contact_id": cid}) for c in ("voice_notes", "contact_events", "tasks")}
    verdict("delete_contact_cascade", "PARTIAL", f"delete={st}, contact hard-deleted={gone}, records left pointing at the deleted id={left}")


def test_14_read_only_sweep_of_other_contact_id_routes():
    """GET-only probes (no writes) of contact-id routes the static scan found without an obvious owner filter."""
    a, b = S["uid"]["A"], S["cb"]
    paths = [f"/contacts/{a}/{b}/events", f"/contacts/{a}/{b}/share/text", f"/contacts/{a}/{b}/share/vcard", f"/calls/{a}/contact/{b}",
             f"/ai-outreach/relationship-brief/{a}/{b}", f"/ai-reply/history/{b}", f"/consent/contact/{b}", f"/crm-push/{a}/{b}/preview",
             f"/relationship-health/{a}/advocates/{b}/thank", f"/sold-workflow/contact/{b}", f"/home/draft/{a}/{b}"]
    out, leaks = {}, []
    for p in paths:
        st, body = api("GET", p, "A")
        blob = json.dumps(body, default=str)
        hit = any(t in blob for t in (B_SECRET, "Ford", "555-0142", "5550142", "Audit B"))
        out[p.replace(a, "{A}").replace(b, "{B_contact}")] = f"{st}{' LEAK' if hit else ''}"
        if hit:
            leaks.append(p.replace(a, "{A}").replace(b, "{B_contact}"))
    verdict("idor_other_contact_routes_get_sweep", "DEFECT" if leaks else "VERIFIED", f"{out}; leaking={leaks}")
