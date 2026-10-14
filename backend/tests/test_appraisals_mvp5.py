"""Trade Appraisal MVP5 - vehicles as relationship records, reappraise, accepted != traded, follow-up bridge (tasks + campaign triggers + merge
fields with the org money gate), reporting / pipeline / search, tenant isolation. Runs against the preview backend; run the whole file in order."""
import asyncio
import os
import sys
import time
from datetime import datetime, timezone, timedelta

import pytest
from dotenv import load_dotenv
from pymongo import MongoClient
from bson import ObjectId
from tests import qa_creds

sys.path.insert(0, "/app/backend")
sys.path.insert(0, "/app/backend/tests")
load_dotenv("/app/backend/.env")
from _http import call, login, auth  # noqa: E402

REP = ("activation-tester@invalid.imonsocial.test", qa_creds.password_for("activation-tester@invalid.imonsocial.test"))
MANAGER = ("qa-manager@invalid.imonsocial.test", qa_creds.password_for("qa-manager@invalid.imonsocial.test"))
OTHER_ORG_ADMIN = ("qa-orgadmin@invalid.imonsocial.test", qa_creds.password_for("qa-orgadmin@invalid.imonsocial.test"))
SARAH = "6aa413008f0d53e3f2261853"
QA_STORE = "69a0b7095fddcede09591668"
VIN = "1FTEW1EP8KFA00005"  # valid check digit; fixed so the reappraisal lands on the same vehicles doc
STATE: dict = {}


def _db():
    return MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


def _market(hdr, aid):
    for _ in range(5):
        st, b = call("POST", f"/api/appraisals/{aid}/market/refresh", {"zip": "84070", "radius": 100}, hdr)
        if st == 200:
            return
        assert st == 429, (st, b)
        time.sleep(16)
    raise AssertionError("market refresh kept hitting the rate limit")


def _run_to_presented(rep, manager, aid, change_to=None):
    assert call("POST", f"/api/appraisals/{aid}/mileage", {"confirmed": STATE.get("miles", 61200), "source": "manual"}, rep)[0] == 200
    _market(rep, aid)
    assert call("POST", f"/api/appraisals/{aid}/expectation", {"asked": True, "value": 32000}, rep)[0] == 200
    st, b = call("POST", f"/api/appraisals/{aid}/submit", None, rep)
    assert st == 200, (st, b)
    body = {"action": "change", "value": change_to, "reason": "Fresh tires, strong unit"} if change_to else {"action": "approve"}
    st, b = call("POST", f"/api/appraisals/{aid}/decide", body, manager)
    assert st == 200, (st, b)
    st, b = call("POST", f"/api/appraisals/{aid}/present", None, rep)
    assert st == 200, (st, b)
    return b


@pytest.fixture(scope="module")
def rep():
    return auth(*login(*REP))


@pytest.fixture(scope="module")
def manager():
    return auth(*login(*MANAGER))


@pytest.fixture(scope="module")
def stranger():
    return auth(*login(*OTHER_ORG_ADMIN))


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    db = _db()
    yield
    for aid in STATE.get("appraisals", []):
        db.vehicle_appraisals.update_one({"_id": ObjectId(aid)}, {"$set": {"deleted": True}})
    if STATE.get("vehicle_id"):
        db.vehicles.update_one({"_id": ObjectId(STATE["vehicle_id"])}, {"$set": {"deleted": True}})
    db.tasks.delete_many({"appraisal_id": {"$in": STATE.get("appraisals", [])}})
    if STATE.get("campaign_id"):
        db.campaigns.delete_one({"_id": ObjectId(STATE["campaign_id"])})
        db.campaign_enrollments.delete_many({"campaign_id": STATE["campaign_id"]})
        db.campaign_pending_sends.delete_many({"campaign_id": STATE["campaign_id"]})
    db.vehicles.delete_many({"qa_mvp5": True})
    db.vehicle_appraisals.delete_many({"qa_mvp5": True})
    db.organizations.update_one({"_id": "org_001"}, {"$unset": {"allow_trade_values_in_automated_messages": ""}})


# ---------- rules: follow-up tasks + backfill ----------
def test_rules_have_task_defaults_and_backfill():
    from services.appraisals import rules as rulesvc
    clean = rulesvc.validate({"basis": {"order": ["provider_retail"]}})
    assert set(clean["follow_up"]["tasks"]) == set(rulesvc.TASK_KINDS)
    assert clean["follow_up"]["tasks"]["wants_more"]["enabled"] is True and clean["follow_up"]["tasks"]["wants_more"]["days"] == 1
    clean = rulesvc.validate({"basis": {"order": ["provider_retail"]}, "follow_up": {"tasks": {"thinking": {"enabled": False, "days": 99, "title": "x" * 200}}}})
    assert clean["follow_up"]["tasks"]["thinking"] == {"enabled": False, "days": 30, "title": "x" * 140, "description": rulesvc.DEFAULT_RULES["follow_up"]["tasks"]["thinking"]["description"]}

    async def go():
        from motor.motor_asyncio import AsyncIOMotorClient
        db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
        old = {"_id": ObjectId(), "organization_id": "qa_mvp5_org", "store_id": None, "rules": {k: v for k, v in rulesvc.DEFAULT_RULES.items() if k != "follow_up"} | {"follow_up": {"tag_on_outcome": False, "tags": {}}}, "version": 3}
        await db.appraisal_rules.insert_one(old)
        try:
            eff = await rulesvc.effective(db, "qa_mvp5_org", None)
            assert eff["version"] == 3 and eff["rules"]["follow_up"]["tasks"]["reappraisal"]["enabled"] is True
            assert "tasks" not in (await db.appraisal_rules.find_one({"_id": old["_id"]}))["rules"]["follow_up"]
        finally:
            await db.appraisal_rules.delete_one({"_id": old["_id"]})
    asyncio.run(go())


# ---------- merge fields + money gate (pure) ----------
def test_merge_values_money_gate():
    from services.appraisals.followup import merge_values, MERGE_FIELDS, MONEY_FIELDS, apply_merge_fields
    s = {"vehicle_label": "2022 Ford F-150 Lariat", "mileage": 47821, "appraised_at": datetime(2026, 10, 7, tzinfo=timezone.utc), "condition_label": "Good", "outcome_label": "Thinking about it",
         "salesperson": "Kira", "approved_by_name": "Dave", "market_retail": 34850, "suggested_acv": 29600, "approved_value": 30000, "customer_expected_value": 32000, "expectation_gap": 2000}
    off = merge_values(s, {"year": 2022, "make": "Ford", "model": "F-150", "trim": "Lariat"}, allow_money=False)
    assert set(off) == set(MERGE_FIELDS)
    assert off["trade_vehicle"] == "2022 Ford F-150 Lariat" and off["trade_mileage"] == "47,821" and off["trade_appraisal_date"] == "Oct 07, 2026" and off["trade_manager"] == "Dave"
    assert all(off[k] == "" for k in MONEY_FIELDS)
    on = merge_values(s, None, allow_money=True)
    assert on["trade_approved_value"] == "$30,000" and on["trade_customer_wants"] == "$32,000" and on["trade_gap"] == "$2,000" and on["trade_market_value"] == "$34,850"
    msg = apply_merge_fields("Hi {first_name}, about your {trade_vehicle} ({trade_mileage} mi): we offered {trade_approved_value}.", off)
    assert msg == "Hi {first_name}, about your 2022 Ford F-150 Lariat (47,821 mi): we offered ."


# ---------- the relationship flow: appraisal -> change -> present -> wants_more (tasks, intent, no traded) -> reappraise -> accepted ----------
def test_first_appraisal_wants_more_creates_tasks_and_intent(rep, manager):
    db = _db()
    st, b = call("POST", "/api/appraisals", {"contact_id": SARAH, "mode": "vehicle_here"}, rep)
    assert st == 200, (st, b)
    aid = b["appraisal"]["id"]
    STATE.setdefault("appraisals", []).append(aid)
    st, b = call("POST", f"/api/appraisals/{aid}/vehicle", {"vin": VIN, "manual": {"year": 2019, "make": "Ford", "model": "F-150", "trim": "XLT"}, "method": "manual_vin"}, rep)
    assert st == 200, (st, b)
    vid = b["appraisal"]["vehicle_id"]
    STATE["vehicle_id"] = vid
    STATE["miles"] = 61200
    # a store-wide campaign that starts on wants_more: visible to the rep, enrolls under the rep. (Campaign editing is locked for this QA store, so it is
    # inserted directly; the route-level trigger_events sanitising is checked with the super admin below.)
    uid = rep["X-User-ID"]
    cid = str(db.campaigns.insert_one({"user_id": manager["X-User-ID"], "store_id": QA_STORE, "scope": "account", "ownership_level": "store", "name": "QA MVP5 wants-more follow-up", "type": "custom",
                                       "trigger_tag": "", "trigger_events": ["trade_appraisal.wants_more"], "active": True, "delivery_mode": "manual", "ai_enabled": False,
                                       "sequences": [{"message_template": "Hi {first_name}, still thinking about the {trade_vehicle}? We offered {trade_approved_value}.", "delay_days": 1, "action_type": "message"}],
                                       "created_at": datetime.utcnow()}).inserted_id)
    STATE["campaign_id"] = cid
    su = auth(*login("forest@imosapp.com", qa_creds.password_for("forest@imosapp.com")))
    st, c = call("POST", f"/api/campaigns/{su['X-User-ID']}", {"name": "QA MVP5 sanitise", "type": "custom", "trigger_events": ["trade_appraisal.accepted", "bogus.event"], "active": False, "sequences": [], "scope": "personal"}, su)
    assert st == 200, (st, c)
    scid = c.get("_id") or c.get("id")
    assert db.campaigns.find_one({"_id": ObjectId(scid)})["trigger_events"] == ["trade_appraisal.accepted"]
    st, c = call("PUT", f"/api/campaigns/{su['X-User-ID']}/{scid}", {"trigger_events": ["trade_appraisal.closed", 42, "nope"]}, su)
    assert st == 200, (st, c)
    assert db.campaigns.find_one({"_id": ObjectId(scid)})["trigger_events"] == ["trade_appraisal.closed"]
    db.campaigns.delete_one({"_id": ObjectId(scid)})

    _run_to_presented(rep, manager, aid, change_to=18800)
    a = db.vehicle_appraisals.find_one({"_id": ObjectId(aid)})
    # desk changed the value -> manager_changed task for the rep, due today
    t = db.tasks.find_one({"appraisal_id": aid, "task_kind": "manager_changed"})
    assert t and t["user_id"] == uid and t["contact_id"] == SARAH and t["source"] == "trade_appraisal" and t["status"] == "pending", t
    assert "changed value" in t["title"].lower() and "F-150" in t["title"]
    assert db.appraisal_events.find_one({"appraisal_id": aid, "event": "trade_appraisal.approved"})

    st, b = call("POST", f"/api/appraisals/{aid}/outcome", {"outcome": "wants_more", "expected_value": 21000, "note": "Wants 21"}, rep)
    assert st == 200, (st, b)
    a = db.vehicle_appraisals.find_one({"_id": ObjectId(aid)})
    assert a["status"] == "closed" and a["outcome"] == "wants_more" and a["expectation_gap_final"] == 21000 - a["approved_value"]
    # task with the gap in the title
    t = db.tasks.find_one({"appraisal_id": aid, "task_kind": "wants_more"})
    assert t and t["priority"] == "high" and f"${21000 - a['approved_value']:,}" in t["title"] and t["title"].endswith("Sarah"), t
    assert t["due_date"] > datetime.utcnow() + timedelta(hours=20)
    assert db.tasks.count_documents({"appraisal_id": aid, "task_kind": "wants_more"}) == 1
    # vehicle: intent recorded, ownership untouched
    v = db.vehicles.find_one({"_id": ObjectId(vid)})
    assert v["trade_intent_status"] == "wants_more" and v["trade_intent_appraisal_id"] == aid and v.get("ownership_status", "owns") == "owns" and not v.get("trade_confirmed_at")
    # campaign enrolled through the existing engine
    enr = db.campaign_enrollments.find_one({"campaign_id": cid, "contact_id": SARAH})
    assert enr and enr["trigger_type"] == "trade_appraisal.wants_more" and enr["status"] == "active", enr
    assert db.campaign_pending_sends.count_documents({"campaign_id": cid, "contact_id": SARAH}) == 1
    # idempotent: a second wants_more on another appraisal would not re-enroll (already active)
    assert db.campaign_enrollments.count_documents({"campaign_id": cid, "contact_id": SARAH}) == 1


def test_template_renderer_resolves_trade_fields_with_money_gate(rep):
    """The one renderer (scheduler.resolve_template_variables): money blank by default, filled once the org allows it."""
    from scheduler import resolve_template_variables

    async def go():
        from motor.motor_asyncio import AsyncIOMotorClient
        db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
        contact = await db.contacts.find_one({"_id": ObjectId(SARAH)})
        uid = rep["X-User-ID"]
        tpl = "Hi {first_name}, about your {trade_vehicle} ({trade_mileage} mi, {trade_appraisal_date}): offered [{trade_approved_value}] wanted [{trade_customer_wants}] gap [{trade_gap}] outcome {trade_outcome}."
        off = await resolve_template_variables(db, tpl, contact, uid)
        assert "2019 Ford F-150 XLT" in off and "61,200 mi" in off and "offered [] wanted [] gap []" in off and "Wants more" in off, off
        # the org admin flips the switch; the store's org is org_001 (dangling test org) so write it directly
        await db.organizations.update_one({"_id": "org_001"}, {"$set": {"allow_trade_values_in_automated_messages": True, "name": "QA org_001"}}, upsert=True)
        try:
            on = await resolve_template_variables(db, tpl, contact, uid)
            assert "offered [$" in on and "wanted [$21,000]" in on and "gap [$" in on, on
        finally:
            await db.organizations.update_one({"_id": "org_001"}, {"$unset": {"allow_trade_values_in_automated_messages": ""}})
    asyncio.run(go())


def test_vehicle_cards_detail_and_jessi_context(rep):
    vid = STATE["vehicle_id"]
    st, b = call("GET", f"/api/appraisals/vehicles/{SARAH}", None, rep)
    assert st == 200
    card = next(v for v in b["vehicles"] if v["id"] == vid)
    assert card["ownership_status"] == "owns" and card["ownership_label"] == "Currently owns" and card["trade_intent_status"] == "wants_more" and card["trade_intent_label"] == "Wants more"
    assert card["appraisal_count"] == 1 and card["last"]["outcome"] == "wants_more" and card["last"]["customer_expected_value"] == 21000 and card["vin_masked"].endswith("0005") and card["open_appraisal_id"] is None
    assert card["opportunity"] is None  # closed 1 minute ago: nothing to revisit yet
    st, d = call("GET", f"/api/appraisals/vehicle/{vid}", None, rep)
    assert st == 200 and d["contact"]["id"] == SARAH and len(d["history"]) == 1 and d["history"][0]["status"] == "closed" and d["history"][0]["expectation_gap"] == 21000 - d["history"][0]["approved_value"]
    assert d["history"][0]["manager_delta"] is not None and d["can_appraise"] is True and d["ownership_options"]["traded"] == "Traded"
    # Jessi's lines: normalized numbers, never provider payloads
    from services.appraisals.core import for_context

    async def go():
        from motor.motor_asyncio import AsyncIOMotorClient
        db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
        rows = await for_context(db, SARAH)
        line = next(r["line"] for r in rows if r["vehicle_id"] == vid)
        assert "trade intent: wants more" in line and "dealer offered $" in line and "customer wanted $21,000" in line and "outcome: Wants more" in line
        assert "listing" not in line.lower() and "{" not in line
    asyncio.run(go())


def test_reappraise_reuses_vehicle_then_accepted_is_intent_not_traded(rep, manager):
    db = _db()
    vid = STATE["vehicle_id"]
    st, b = call("POST", "/api/appraisals", {"contact_id": SARAH, "mode": "vehicle_here", "vehicle_id": vid}, rep)
    assert st == 200, (st, b)
    a2 = b["appraisal"]
    STATE["appraisals"].append(a2["id"])
    assert a2["is_reappraisal"] is True and a2["vehicle_id"] == vid and a2["vin"] == VIN and a2["previous_appraisal_id"] == STATE["appraisals"][0] and a2["step"] == "mileage"
    assert db.vehicles.count_documents({"contact_id": SARAH, "vin": VIN, "deleted": {"$ne": True}}) == 1
    # the open reappraisal shows on the card and blocks a second Reappraise button
    st, cards = call("GET", f"/api/appraisals/vehicles/{SARAH}", None, rep)
    card = next(v for v in cards["vehicles"] if v["id"] == vid)
    assert card["open_appraisal_id"] == a2["id"] and card["appraisal_count"] == 2
    STATE["miles"] = 63900
    _run_to_presented(rep, manager, a2["id"])
    assert db.appraisal_events.find_one({"appraisal_id": a2["id"], "event": "trade_appraisal.reappraised"})
    st, b = call("POST", f"/api/appraisals/{a2['id']}/outcome", {"outcome": "accepted"}, rep)
    assert st == 200, (st, b)
    v = db.vehicles.find_one({"_id": ObjectId(vid)})
    assert v["ownership_status"] == "owns" and v["trade_intent_status"] == "accepted" and v["trade_intent_appraisal_id"] == a2["id"] and not v.get("trade_confirmed_at")
    assert v["last_appraisal"]["outcome"] == "accepted" and v["last_appraisal"]["is_reappraisal"] is True and v["current_mileage"] == 63900
    st, d = call("GET", f"/api/appraisals/vehicle/{vid}", None, rep)
    assert st == 200 and [h["is_reappraisal"] for h in d["history"]] == [False, True] and d["trade_intent_label"] == "Accepted our offer" and d["ownership_status"] == "owns"
    vh = d["value_history"]
    assert len(vh["points"]) == 2 and any(c["key"] == "mileage" and c["delta"] == 2700 for c in vh["changes"])
    # manual confirmation is the only path to traded
    st, d = call("PUT", f"/api/appraisals/vehicle/{vid}/ownership", {"status": "nonsense"}, rep)
    assert st == 400
    st, d = call("PUT", f"/api/appraisals/vehicle/{vid}/ownership", {"status": "traded", "note": "Deal 4471"}, rep)
    assert st == 200 and d["ownership_status"] == "traded" and d["trade_confirmed_at"] and d["ownership_note"] == "Deal 4471" and d["ownership_updated_by_name"]
    assert db.appraisal_events.find_one({"appraisal_id": a2["id"], "event": "trade_appraisal.trade_confirmed"})
    assert db.vehicle_appraisals.find_one({"_id": ObjectId(a2["id"])})["trade_confirmed_at"]
    st, d = call("PUT", f"/api/appraisals/vehicle/{vid}/ownership", {"status": "owns"}, rep)
    assert st == 200 and d["ownership_status"] == "owns" and d["trade_confirmed_at"] is None


def test_pipeline_search_and_reports(rep, manager, stranger):
    aid1, aid2 = STATE["appraisals"][0], STATE["appraisals"][1]
    st, p = call("GET", "/api/appraisals/pipeline", None, rep)
    assert st == 200 and p["team"] is False and p["can_team"] is False
    closed = next(g for g in p["groups"] if g["key"] == "recently_closed")
    assert {aid1, aid2} <= {i["id"] for i in closed["items"]}
    st, p = call("GET", "/api/appraisals/pipeline?team=1", None, manager)
    assert st == 200 and p["team"] is True and p["can_team"] is True
    # search by VIN fragment, outcome, status
    st, s = call("GET", f"/api/appraisals/search?q={VIN[-6:]}", None, rep)
    assert st == 200 and {a["id"] for a in s["appraisals"]} == {aid1, aid2}
    st, s = call("GET", f"/api/appraisals/search?q={VIN[-6:]}&outcome=accepted", None, rep)
    assert st == 200 and [a["id"] for a in s["appraisals"]] == [aid2] and s["appraisals"][0]["outcome_label"] == "Accepted"
    st, s = call("GET", "/api/appraisals/search?status=closed&make=ford&q=Sarah", None, rep)
    assert st == 200 and {aid1, aid2} <= {a["id"] for a in s["appraisals"]} and all(a["status"] == "closed" for a in s["appraisals"])
    # reports: manager only, numbers for the QA store
    assert call("GET", "/api/appraisals/reports/summary", None, rep)[0] == 403
    since = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
    st, r = call("GET", f"/api/appraisals/reports/summary?date_from={since}", None, manager)
    assert st == 200, (st, r)
    c = r["counts"]
    assert c["started"] >= 2 and c["reappraisals"] >= 1 and c["accepted"] >= 1 and c["wants_more"] >= 1 and c["presented"] >= 2 and c["approved"] >= 2
    assert r["averages"]["manager_response_s"] is not None and r["averages"]["expectation_gap"] is not None and r["rates"]["acceptance"] is not None
    rep_row = next(x for x in r["by_salesperson"] if x["id"] == rep["X-User-ID"])
    assert rep_row["started"] >= 2 and rep_row["accepted"] >= 1
    mgr_row = next(x for x in r["by_manager"] if x["id"] == manager["X-User-ID"])
    assert mgr_row["decisions"] >= 2 and mgr_row["avg_response_s"] is not None
    assert any(m["id"] == "Ford" for m in r["by_make"]) and r["options"]["outcomes"]["wants_more"] == "Wants more"
    st, r2 = call("GET", f"/api/appraisals/reports/summary?date_from={since}&outcome=accepted", None, manager)
    assert st == 200 and r2["counts"]["started"] >= 1 and r2["counts"]["wants_more"] == 0
    st, f = call("GET", "/api/appraisals/reports/followup", None, manager)
    assert st == 200 and aid1 in {x["id"] for x in f["wants_more"]} and aid1 in {x["id"] for x in f["large_gaps"]} and f["thresholds"]["gap"] == 2000
    # tenant isolation: another org's admin sees nothing of this
    assert call("GET", f"/api/appraisals/vehicle/{STATE['vehicle_id']}", None, stranger)[0] == 404
    assert call("GET", f"/api/appraisals/vehicles/{SARAH}", None, stranger)[0] == 404
    st, s = call("GET", f"/api/appraisals/search?q={VIN[-6:]}", None, stranger)
    assert st == 200 and s["appraisals"] == []
    st, r = call("GET", "/api/appraisals/reports/summary", None, stranger)
    assert st == 200 and r["counts"]["started"] == 0 and r["by_salesperson"] == []
    # campaign options + org setting guard
    st, o = call("GET", "/api/appraisals/campaign-options", None, rep)
    assert st == 200 and "trade_appraisal.wants_more" in o["triggers"] and "trade_gap" in o["merge_fields"] and o["allow_trade_values"] is False
    assert call("PUT", "/api/appraisals/org-settings", {"allow_trade_values_in_automated_messages": True}, rep)[0] == 403
    assert call("PUT", "/api/appraisals/org-settings", {"allow_trade_values_in_automated_messages": True}, manager)[0] == 403


def test_opportunities_and_reappraisal_tasks_from_stored_history():
    """Stale vehicle (closed 120 days ago, still owned) -> opportunity + one daily reappraisal task; no provider call anywhere."""
    from services.appraisals import relationship, followup

    async def go():
        from motor.motor_asyncio import AsyncIOMotorClient
        db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
        uid = (await db.users.find_one({"email": REP[0]}, {"_id": 1}))["_id"]
        old = datetime.now(timezone.utc) - timedelta(days=120)
        aid, vid = ObjectId(), ObjectId()
        appr = {"_id": aid, "qa_mvp5": True, "contact_id": SARAH, "contact_name": "Sarah Tester", "user_id": str(uid), "user_name": "Activation Tester", "store_id": QA_STORE, "organization_id": "org_001",
                "status": "closed", "outcome": "thinking", "outcome_label": "Thinking about it", "vehicle_id": str(vid), "vin": None, "vehicle": {"year": 2016, "make": "Subaru", "model": "Outback", "trim": "Limited"},
                "mileage_confirmed": 98000, "suggested_acv": 9000, "approved_value": 9200, "closed_at": old, "submitted_at": old, "created_at": old, "updated_at": old}
        veh = {"_id": vid, "qa_mvp5": True, "contact_id": SARAH, "user_id": str(uid), "store_id": QA_STORE, "organization_id": "org_001", "year": 2016, "make": "Subaru", "model": "Outback", "trim": "Limited", "vin": None,
               "ownership_status": "owns", "appraisal_count": 1, "created_at": old, "updated_at": old,
               "last_appraisal": {"appraisal_id": str(aid), "status": "closed", "closed_at": old, "appraised_at": old, "outcome": "thinking", "outcome_label": "Thinking about it", "approved_value": 9200, "mileage": 98000, "contact_name": "Sarah Tester"}}
        await db.vehicle_appraisals.insert_one(appr)
        await db.vehicles.insert_one(veh)
        try:
            me = await db.users.find_one({"_id": uid})
            opps = await relationship.opportunities(db, me)
            o = next(x for x in opps if x["vehicle_id"] == str(vid))
            assert o["kind"] == "stale" and o["days"] >= 120 and "Sarah's Outback" in o["title"] and o["priority"] == 2
            n1 = await followup.reappraisal_tasks(db)
            assert n1 >= 1
            t = await db.tasks.find_one({"appraisal_id": str(aid)})
            assert t and t["title"] == "Reappraise Sarah's 2016 Subaru Outback Limited" and t["vehicle_link"] == f"/vehicle/{vid}" and t["user_id"] == str(uid)
            n2 = await followup.reappraisal_tasks(db)
            assert await db.tasks.count_documents({"appraisal_id": str(aid)}) == 1, n2
            # not owned any more -> no opportunity
            await db.vehicles.update_one({"_id": vid}, {"$set": {"ownership_status": "sold"}})
            assert not any(x["vehicle_id"] == str(vid) for x in await relationship.opportunities(db, me))
        finally:
            await db.tasks.delete_many({"appraisal_id": str(aid)})
    asyncio.run(go())


def test_migration_accepted_is_not_traded():
    """MVP4 flipped the vehicle to traded on an accepted outcome. The migration undoes exactly that and nothing else."""
    from services.appraisals.relationship import migrate_accepted_traded

    async def go():
        from motor.motor_asyncio import AsyncIOMotorClient
        db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
        now = datetime.now(timezone.utc)
        bad_v, ok_v, legit_v = ObjectId(), ObjectId(), ObjectId()
        a_bad, a_legit = ObjectId(), ObjectId()
        await db.vehicles.insert_many([
            {"_id": bad_v, "qa_mvp5": True, "contact_id": SARAH, "user_id": "x", "ownership_status": "traded", "make": "Kia", "model": "Soul", "year": 2018, "created_at": now, "updated_at": now},
            {"_id": ok_v, "qa_mvp5": True, "contact_id": SARAH, "user_id": "x", "ownership_status": "owns", "make": "Kia", "model": "Rio", "year": 2018, "created_at": now, "updated_at": now},
            {"_id": legit_v, "qa_mvp5": True, "contact_id": SARAH, "user_id": "x", "ownership_status": "traded", "trade_confirmed_at": now, "ownership_updated_by": "someone", "make": "Kia", "model": "Forte", "year": 2018, "created_at": now, "updated_at": now},
        ])
        await db.vehicle_appraisals.insert_many([
            {"_id": a_bad, "qa_mvp5": True, "vehicle_id": str(bad_v), "contact_id": SARAH, "user_id": "x", "status": "closed", "outcome": "accepted", "outcome_at": now, "created_at": now, "updated_at": now},
            {"_id": a_legit, "qa_mvp5": True, "vehicle_id": str(legit_v), "contact_id": SARAH, "user_id": "x", "status": "closed", "outcome": "accepted", "outcome_at": now, "created_at": now, "updated_at": now},
        ])
        res = await migrate_accepted_traded(db)
        assert res["fixed"] >= 1
        bad = await db.vehicles.find_one({"_id": bad_v})
        assert bad["ownership_status"] == "owns" and bad["trade_intent_status"] == "accepted" and bad["trade_intent_at"] is not None and "MVP5" in bad["migration_note"]
        assert (await db.vehicles.find_one({"_id": legit_v}))["ownership_status"] == "traded"
        assert (await db.vehicles.find_one({"_id": ok_v}))["ownership_status"] == "owns"
        res2 = await migrate_accepted_traded(db)
        assert res2["fixed"] == 0 or (await db.vehicles.find_one({"_id": bad_v}))["ownership_status"] == "owns"
        assert (await db.migrations.find_one({"_id": "appraisal_accepted_not_traded"}))["runs"] >= 2
    asyncio.run(go())
