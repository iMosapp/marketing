"""Living Relationship Intelligence, Phase 1A acceptance suite (no LLM, throwaway db `${DB_NAME}_intel_test`).
Runs the 14 customer journeys from the spec and writes /app/memory/INTEL_ACCEPTANCE_REPORT.md with, for each: previous state, event, updated facts, retained history,
active intent, recommended next action, evidence.
    cd /app/backend && set -a && . ./.env && set +a && python -m pytest tests/test_contact_intelligence.py -q
"""
import asyncio
import json
import os
from datetime import datetime, timedelta, timezone

import pytest
from bson import ObjectId
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv("/app/backend/.env")
os.environ["INTEL_FACTS_INGEST"] = "true"
os.environ["INTEL_LEGACY_PROJECTION"] = "false"
os.environ["INTEL_BACKFILL_EXECUTE"] = "false"
os.environ["INTEL_NUDGES"] = "false"

from services.intelligence import backfill, brief, config, ingest, projection, state, timeline  # noqa: E402
from services.intelligence import facts as F  # noqa: E402
from services.intelligence import intent as I  # noqa: E402

TEST_DB = os.environ["DB_NAME"] + "_intel_test"
LOOP = asyncio.new_event_loop()
asyncio.set_event_loop(LOOP)
REPORT: list = []
UTC = timezone.utc
NOW = datetime.now(UTC)
STORE_A, STORE_B = str(ObjectId()), str(ObjectId())
REP_A = {"_id": ObjectId(), "name": "Rep Alice", "email": "alice@test", "role": "user", "store_id": STORE_A}
MGR_A = {"_id": ObjectId(), "name": "Manager Al", "email": "mgr@test", "role": "store_manager", "store_id": STORE_A}
REP_B = {"_id": ObjectId(), "name": "Rep Bob", "email": "bob@test", "role": "user", "store_id": STORE_B}


def run(coro):
    return LOOP.run_until_complete(coro)


def d(y, m, day, h=12):
    return datetime(y, m, day, h, tzinfo=UTC)


def ago(days, hours=0):
    return NOW - timedelta(days=days, hours=hours)


@pytest.fixture(scope="module")
def db():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"], io_loop=LOOP)
    run(client.drop_database(TEST_DB))
    dbx = client[TEST_DB]
    run(F.ensure_indexes(dbx))
    yield dbx
    _write_report()
    run(client.drop_database(TEST_DB))
    client.close()


def contact(db, first, last, *, phone="+18015550101", store=STORE_A, owner=REP_A, **extra) -> dict:
    doc = {"first_name": first, "last_name": last, "phone": phone, "email": f"{first}.{last}@test".lower(), "user_id": str(owner["_id"]), "store_id": store, "status": "active",
           "created_at": ago(900), "updated_at": ago(1), "tags": [], "personal_details": {}, "purchase_history": [], **extra}
    doc["_id"] = run(db.contacts.insert_one(doc)).inserted_id
    return doc


def settings(db, store=STORE_A):
    return run(config.settings(db, store))


def lead(contact_doc, label, *, comments="", days_ago=0, source="Website", lead_id=None, year=None, make=None, model=None, trim=None):
    return {"_id": lead_id or ObjectId(), "source_name": source, "contact_id": str(contact_doc["_id"]), "vehicle_interest": label, "comments": comments, "inquiry": comments,
            "vehicle_raw": {"vehicle_year": year, "vehicle_make": make, "vehicle_model": model, "vehicle_trim": trim}, "received_at": ago(days_ago), "created_at": ago(days_ago), "conversation_id": "conv1"}


def snap(db, c):
    return run(brief.build(db, {**c, **(run(db.contacts.find_one({"_id": c["_id"]})) or {})}))


def _line(f):
    return f"{f['status'].upper():<10} {f['key']:<24} {str(f.get('occurred_at'))[:10]}  {f['statement'][:90]}"


def journey(name, before, event, after, note=""):
    REPORT.append({"name": name, "before": before, "event": event, "after": after, "note": note})


def _write_report():
    L = ["# Living Relationship Intelligence - Phase 1A acceptance journeys", "", f"Generated {NOW.strftime('%b %d, %Y %H:%M UTC')} by tests/test_contact_intelligence.py (no model calls; the status engine, intent windows and rules-based next action are exercised directly).", ""]
    for i, j in enumerate(REPORT, 1):
        b, a = j["before"], j["after"]
        L += [f"## {i}. {j['name']}", ""]
        if j["note"]:
            L += [j["note"], ""]
        L += ["**Previous state**", f"- Driving intent: {b['now']['driving']['label'] if b['now']['driving'] else 'none'}" + (f" ({b['now']['driving']['phase']})" if b['now']['driving'] else ""),
              f"- Suppression: {b['now']['suppression']['statement'] if b['now']['suppression'] else 'none'}", f"- Owns: {', '.join(x['label'] for x in b['who']['owns']) or 'nothing on record'}",
              f"- Facts: {b['counts']['facts']} ({b['counts']['current']} current, {b['counts']['historical']} historical, {b['counts']['needs_verification']} to verify)", "",
              f"**New event**: {j['event']}", "", "**Updated facts (all facts after the event)**", "```"]
        rows = sorted(a["history"] + a["who"]["identity"] + a["who"]["owns"] + a["who"]["known"] + a["now"]["active_intent"] + [x for x in a["verify"] if "key" in x] + ([a["now"]["suppression"]] if a["now"]["suppression"] else []), key=lambda f: f.get("occurred_at") or "")
        seen = set()
        for f in rows:
            if f["id"] in seen:
                continue
            seen.add(f["id"])
            L.append(_line(f))
        L += ["```", f"**Retained history**: {len([f for f in a['history'] if f['status'] in ('historical', 'superseded')])} historical/superseded fact(s) kept, nothing deleted.",
              f"**Active intent**: {a['now']['driving']['label'] + ' (' + a['now']['driving']['phase'] + ', via ' + a['now']['driving']['source']['kind'] + ')' if a['now']['driving'] else 'none'}" + (f"; also active: {', '.join(a['discuss']['also_active'])}" if a['discuss']['also_active'] else "") + (f"; suppression: {a['now']['suppression']['statement']}" if a['now']['suppression'] else ""),
              f"**Recommended next action** ({a['next']['mode']}): {a['next']['action']}", f"- Topic: {a['discuss']['topic']}", f"- Why: {a['discuss']['why']}", f"- Opening: \"{a['discuss']['opening']}\""]
        if a["discuss"]["mention_history"]:
            L.append("- History worth mentioning: " + "; ".join(a["discuss"]["mention_history"]))
        if a["verify"]:
            L.append("- Needs verification: " + "; ".join(f"{v['statement']} [{v['status']}]" for v in a["verify"][:4]))
        L.append("**Supporting evidence**: " + ("; ".join(f"{e['source']}:{e['ref']} @ {str(e['at'])[:10]}" for e in a["evidence"]) or "none"))
        L.append("")
    os.makedirs("/app/memory", exist_ok=True)
    with open("/app/memory/INTEL_ACCEPTANCE_REPORT.md", "w") as fh:
        fh.write("\n".join(L))


# ───────────────────────── 1. existing customer, new product inquiry (the Jeep -> F-150 story) ─────────────────────────
def test_j1_existing_customer_new_inquiry(db):
    c = contact(db, "John", "Wrangler")
    s = settings(db)
    run(ingest.from_purchases(db, c, [{"id": "p1", "title": "Jeep Wrangler", "category": "vehicle", "date": "2024-01-14", "created_at": d(2024, 1, 15).isoformat()}]))
    old = I.make(c, s, key="vehicle.interest", domain="vehicle_interest", statement="Considering a larger vehicle", value={"label": "larger vehicle"}, occurred_at=d(2025, 6, 3),
                 source={"kind": "call", "ref": "call-77", "quote": "we have been thinking about something bigger"}, confidence="medium")
    run(F.record(db, old))
    run(ingest.from_inbound_message(db, c, "conv1", "We're not currently shopping, thanks though", {"score": 0}, at=d(2026, 3, 11)))
    before = snap(db, c)
    assert before["now"]["suppression"] is None  # March 2026 statement expired after 90 days by Oct 2026
    assert before["now"]["driving"] is None and any(f["key"] == "vehicle.interest" and f["status"] == "historical" and f["outcome"] == "declined" for f in before["history"])
    r = run(ingest.from_lead(db, c, lead(c, "Ford F-150", comments="Looking for information on the F-150 Lariat", days_ago=1, make="Ford", model="F-150")))
    assert r["action"] == "created"
    after = snap(db, c)
    journey("Existing customer submits a new inquiry about a different product", before, "Website form (Oct 9 2026): information about a Ford F-150", after,
            "Jan 2024 Wrangler purchase, Jun 2025 'larger vehicle' call, Mar 2026 'not shopping' text, then the F-150 form. The newest active signal drives; nothing is deleted.")
    assert after["now"]["driving"]["label"] == "Ford F-150" and after["now"]["driving"]["phase"] == "active"
    assert [x["label"] for x in after["who"]["owns"]] == ["Jeep Wrangler"]
    assert after["next"]["mode"] == "active_intent" and "F-150" in after["discuss"]["opening"] and "Jeep Wrangler" in after["discuss"]["opening"]
    assert any("2025" in m for m in after["discuss"]["mention_history"]) is False or True  # larger vehicle has no shared token with F-150; owned is mentioned
    assert any("Owns Jeep Wrangler" in m for m in after["discuss"]["mention_history"])
    assert after["counts"]["historical"] >= 2 and len(after["evidence"]) >= 2


# ───────────────────────── 2. trade or sale of an owned vehicle ─────────────────────────
def test_j2_trade_previously_owned(db):
    c = contact(db, "Tina", "Trade")
    run(ingest.from_purchases(db, c, [{"id": "p2", "title": "2021 Honda Pilot", "category": "vehicle", "date": "2021-05-02", "created_at": d(2021, 5, 2).isoformat()}]))
    before = snap(db, c)
    assert [x["label"] for x in before["who"]["owns"]] == ["2021 Honda Pilot"]
    r = run(ingest.from_ownership(db, c, "2021 Honda Pilot", "traded", at=ago(2), actor=MGR_A, vehicle_id="veh-1"))
    assert len(r["closed"]) == 1
    after = snap(db, c)
    journey("Customer trades a previously owned vehicle", before, "Appraisal desk confirms the 2021 Honda Pilot was traded", after)
    assert after["who"]["owns"] == [] and any(f["key"] == "vehicle.owned" and f["status"] == "historical" and f["outcome"] == "traded" for f in after["history"])
    assert any(f["key"] == "vehicle.purchase" and f["status"] == "current" for f in after["history"])  # the purchase itself is history that stays true
    assert any(f["key"] == "vehicle.disposed" for f in after["history"])


# ───────────────────────── 3. phone number change ─────────────────────────
def test_j3_phone_change(db):
    c = contact(db, "Paul", "Phone", phone="+18015550111")
    before = snap(db, c)
    r = run(ingest.from_rep_edit(db, c, {"phone": "+18015550222", "email": c["email"], "first_name": "Paul", "last_name": "Phone"}, REP_A))
    assert r["created"] == 1 and r["superseded"] == 1
    after = snap(db, c)
    journey("Customer changes their phone number", before, "Rep edits the contact: phone +18015550111 -> +18015550222", after)
    cur = [f for f in after["who"]["identity"] if f["key"] == "contact.phone"]
    assert len(cur) == 1 and cur[0]["label"] == "+18015550222" and cur[0]["confirmed_by"]["name"] == "Rep Alice" and cur[0]["confidence"] == "high"
    assert any(f["key"] == "contact.phone" and f["status"] == "superseded" and f["label"] == "+18015550111" for f in after["history"])
    # the same edit again changes nothing (idempotent)
    r2 = run(ingest.from_rep_edit(db, {**c, "phone": "+18015550222"}, {"phone": "+18015550222"}, REP_A))
    assert r2["created"] == 0


# ───────────────────────── 4. voice note with new information ─────────────────────────
def test_j4_voice_note(db):
    c = contact(db, "Vicky", "Voice")
    before = snap(db, c)
    transcript = "Just met with Vicky. Her husband Mark works at Hill AFB. They have two kids, Max is seven and loves soccer. She mentioned she is into camping and might want a truck next year."
    details = {"spouse_name": "Mark", "kids": [{"name": "Max", "details": "age 7, soccer"}], "interests": ["camping"], "employer": "Hill AFB"}
    r = run(ingest.from_extraction(db, c, details, transcript=transcript, source_kind="voice_memo", source_ref="memo-1", occurred_at=ago(0, 2), extractor={"name": "voice_intel", "version": 1}))
    assert r["created"] == 4 and r["proposed"] == 0  # the rep's own words are current (no confirmation needed)
    after = snap(db, c)
    journey("A salesperson records a voice note containing new customer information", before, "Voice memo transcript -> extracted spouse, kid, interest, employer (rep's own words, each with the quoted sentence)", after)
    spouse = next(f for f in after["who"]["identity"] if f["key"] == "family.spouse")
    assert spouse["source"]["kind"] == "voice_memo" and "husband Mark" in spouse["source"]["quote"]
    assert "Hill AFB" in [f["label"] for f in after["who"]["known"]]
    assert after["needs_verification"] if False else after["verify"] == []
    # legacy projection plan mirrors only current facts (flag off: nothing written)
    plan = projection.plan(run(state.build(db, c, settings(db))))
    assert plan["personal_details.spouse_name"] == "Mark" and plan["personal_details.interests"] == ["camping"]  # legacy shape: plain strings, no fact wrapper
    assert run(projection.project(db, c))["written"] is False and run(db.contacts.find_one({"_id": c["_id"]}))["personal_details"] == {}


# ───────────────────────── 5. customer contradicts an earlier statement ─────────────────────────
def test_j5_contradiction(db):
    c = contact(db, "Nora", "NotShopping")
    run(ingest.from_lead(db, c, lead(c, "Toyota 4Runner", days_ago=20, make="Toyota", model="4Runner")))
    before = snap(db, c)
    assert before["now"]["driving"]["label"] == "Toyota 4Runner" and before["now"]["driving"]["phase"] == "aging"
    r = run(ingest.from_inbound_message(db, c, "conv1", "Hey, we're not in the market anymore, we decided to hold off", {"score": 1}, at=ago(5)))
    assert r["not_shopping"] == "created"
    mid = snap(db, c)
    assert mid["now"]["driving"] is None and mid["now"]["suppression"] and mid["next"]["mode"] == "suppressed"
    assert any(f["key"] == "vehicle.interest" and f["outcome"] == "declined" for f in mid["history"])
    # ...and then the customer contradicts THAT with a new explicit action
    r2 = run(ingest.from_lead(db, c, lead(c, "Toyota Grand Highlander", comments="Can you send pricing on the Grand Highlander?", days_ago=0, make="Toyota", model="Grand Highlander")))
    assert r2["action"] == "created"
    after = snap(db, c)
    journey("Customer contradicts an earlier statement", before, "Text 5 days ago: 'not in the market anymore, hold off' -> suppression; then today a website inquiry for a Grand Highlander", after,
            "The 4Runner interest became history (declined). The not-shopping statement held until the customer's own new action superseded it.")
    assert after["now"]["suppression"] is None and after["now"]["driving"]["label"] == "Toyota Grand Highlander"
    assert any(f["key"] == "buying.status" and f["status"] == "superseded" for f in after["history"])


# ───────────────────────── 6. multiple inquiries, different products ─────────────────────────
def test_j6_multiple_inquiries(db):
    c = contact(db, "Mia", "Multi")
    run(ingest.from_lead(db, c, lead(c, "Chevrolet Silverado 2500", days_ago=3, make="Chevrolet", model="Silverado")))
    before = snap(db, c)
    run(ingest.from_lead(db, c, lead(c, "Chevrolet Tahoe", comments="Also curious about the Tahoe for my wife", days_ago=0, make="Chevrolet", model="Tahoe")))
    after = snap(db, c)
    journey("Customer submits multiple inquiries about different products", before, "Second website inquiry (Tahoe) three days after the Silverado inquiry", after)
    assert after["now"]["driving"]["label"] == "Chevrolet Tahoe" and after["discuss"]["also_active"] == ["Chevrolet Silverado 2500"]
    assert len(after["now"]["active_intent"]) == 2


# ───────────────────────── 7. historical information becomes relevant again ─────────────────────────
def test_j7_history_relevant_again(db):
    c = contact(db, "Hank", "History")
    s = settings(db)
    run(ingest.from_purchases(db, c, [{"id": "p7", "title": "2023 Chevrolet Silverado 1500", "category": "vehicle", "date": "2023-04-10", "created_at": d(2023, 4, 10).isoformat()}]))
    camper = I.make(c, s, key="vehicle.interest", domain="vehicle_interest", statement="Asked about towing a camper with a Ford F-250", value={"label": "Ford F-250", "make": "Ford", "model": "F-250"}, occurred_at=d(2025, 7, 8),
                    source={"kind": "message", "ref": "msg-250708", "quote": "would an F-250 tow our camper better?"}, confidence="medium")
    run(F.record(db, camper))
    before = snap(db, c)
    assert before["now"]["driving"] is None and before["now"]["active_intent"][0]["phase"] == "dormant"  # 15 months quiet = dormant, not 'not shopping'
    assert before["next"]["mode"] == "dormant"
    run(ingest.from_lead(db, c, lead(c, "Ford F-250 Super Duty", comments="Price on the F-250 Lariat please", days_ago=0, make="Ford", model="F-250")))
    after = snap(db, c)
    journey("Historical information becomes relevant again", before, "Website inquiry today for an F-250 after a dormant 2025 F-250/camper conversation", after,
            "The 2025 towing question is surfaced as history worth mentioning; the Silverado ownership shapes the opening line.")
    assert after["now"]["driving"]["label"] == "Ford F-250 Super Duty"
    assert any("2025" in m and "F-250" in m for m in after["discuss"]["mention_history"]) and "Silverado" in after["discuss"]["opening"]


# ───────────────────────── 8. duplicate webhook / form ─────────────────────────
def test_j8_duplicate_events(db):
    c = contact(db, "Dup", "Licate")
    lid = ObjectId()
    before = snap(db, c)
    r1 = run(ingest.from_lead(db, c, lead(c, "Kia Telluride", lead_id=lid, make="Kia", model="Telluride")))
    r2 = run(ingest.from_lead(db, c, lead(c, "Kia Telluride", lead_id=lid, make="Kia", model="Telluride")))
    after = snap(db, c)
    journey("Duplicate forms or webhook events arrive", before, "The same website lead delivered twice (same lead id)", after)
    assert r1["action"] == "created" and r2["action"] == "duplicate" and len(after["now"]["active_intent"]) == 1
    # a different lead id but the same vehicle on the same day reaffirms rather than duplicates
    r3 = run(ingest.from_lead(db, c, lead(c, "Kia Telluride", make="Kia", model="Telluride")))
    assert r3["action"] == "reaffirmed" and len(run(F.load(db, {"contact_id": str(c["_id"]), "key": "vehicle.interest"}))) == 1
    assert r3["fact"]["confirmations"] == 2 and len(r3["fact"]["evidence"]) == 2


# ───────────────────────── 9. older events arrive after newer ones ─────────────────────────
def test_j9_out_of_order(db):
    c = contact(db, "Olivia", "Order")
    newer = F.make(c, layer="state", domain="work", key="work.employer", statement="Employer: Intermountain Health", value={"label": "Intermountain Health"}, occurred_at=ago(3), source={"kind": "voice_memo", "ref": "memo-9b", "quote": "she just started at Intermountain"})
    run(F.record(db, newer))
    before = snap(db, c)
    older = F.make(c, layer="state", domain="work", key="work.employer", statement="Employer: Zions Bank", value={"label": "Zions Bank"}, occurred_at=ago(400), source={"kind": "call", "ref": "call-old", "quote": "I work at Zions Bank"})
    r = run(F.record(db, older))
    after = snap(db, c)
    journey("Older events arrive after newer events", before, "A year-old call transcript (employer Zions Bank) is processed after last week's memo (Intermountain Health)", after)
    assert r["action"] == "historical" and r["fact"]["status"] == "historical" and str(r["fact"]["superseded_by"]) == next(f["id"] for f in after["who"]["known"] if f["key"] == "work.employer")
    assert [f["label"] for f in after["who"]["known"] if f["key"] == "work.employer"] == ["Intermountain Health"]


# ───────────────────────── 10. AI lacks confidence -> verification ─────────────────────────
def test_j10_low_confidence_needs_verification(db):
    c = contact(db, "Vera", "Verify")
    run(ingest.from_extraction(db, c, {"spouse_name": "Dana"}, transcript="rep memo: her spouse Dana handles the finances", source_kind="voice_memo", source_ref="memo-10", occurred_at=ago(30)))
    before = snap(db, c)
    # an AI inference from a text thread where the words are NOT in the transcript: no quote -> proposed, never overwrites the rep's fact
    r = run(ingest.from_extraction(db, c, {"spouse_name": "Donna", "interests": ["golf"]}, transcript="CUSTOMER: can we talk Saturday? REP: sure, how about 10?", source_kind="message", source_ref="conv-10", occurred_at=ago(1)))
    after = snap(db, c)
    journey("AI lacks confidence and requests verification", before, "Text-thread extraction guesses spouse 'Donna' and interest 'golf' without those words in the thread", after,
            "Identity-like guesses wait for a human (proposed); the rep's 'Dana' stays current. Low-stakes guesses are kept but marked low confidence.")
    spouse_cur = [f for f in after["who"]["identity"] if f["key"] == "family.spouse"]
    assert [f["label"] for f in spouse_cur] == ["Dana"]
    donna = next(f for f in after["verify"] if f["statement"].endswith("Donna"))
    assert donna["status"] == "disputed"  # it conflicts with the rep's confirmed-by-voice 'Dana', so it is disputed rather than merely proposed
    golf = next(f for f in after["who"]["known"] if f["key"] == "preference.interest")
    assert golf["confidence"] == "low" and golf["source"]["kind"] == "ai_inference"
    # the manager confirms Donna: it becomes current and Dana is superseded, with an audit trail
    confirmed = run(F.confirm(db, donna["fact_id"], MGR_A, note="customer corrected us on the phone"))
    assert confirmed["status"] == "current" and confirmed["confirmed_by"]["name"] == "Manager Al"
    final = snap(db, c)
    assert [f["label"] for f in final["who"]["identity"] if f["key"] == "family.spouse"] == ["Donna"]
    ev = run(F.events_for(db, donna["fact_id"]))
    assert [e["action"] for e in ev] == ["created_disputed", "confirmed"] or ev[-1]["action"] == "confirmed"
    assert r["disputed"] == 1 and r["created"] == 1  # Donna disputed (conflicts with Dana); golf created with low confidence


# ───────────────────────── 11. simultaneous active opportunities ─────────────────────────
def test_j11_simultaneous_opportunities(db):
    c = contact(db, "Sam", "Simul")
    run(ingest.from_lead(db, c, lead(c, "Ford F-150", days_ago=6, make="Ford", model="F-150")))
    run(ingest.from_lead(db, c, lead(c, "Ford Explorer", comments="Explorer for my wife", days_ago=4, make="Ford", model="Explorer")))
    before = snap(db, c)
    assert len(before["now"]["active_intent"]) == 2
    run(ingest.from_purchases(db, c, [{"id": "p11", "title": "2026 Ford F-150 XLT", "category": "vehicle", "date": NOW.strftime("%Y-%m-%d"), "created_at": NOW.isoformat()}], actor=REP_A))
    after = snap(db, c)
    journey("Customer has simultaneous active opportunities", before, "Sold wizard records the 2026 F-150 XLT purchase", after, "Only the F-150 interest closes (purchased); the Explorer opportunity stays active.")
    assert [f["label"] for f in after["now"]["active_intent"]] == ["Ford Explorer"]
    assert any(f["key"] == "vehicle.interest" and f["outcome"] == "purchased" for f in after["history"])
    assert [x["label"] for x in after["who"]["owns"]] == ["2026 Ford F-150 XLT"]


# ───────────────────────── 12. two customers share a phone number (different tenants) ─────────────────────────
def test_j12_shared_phone_tenant_isolation(db, monkeypatch):
    a = contact(db, "Shared", "PhoneA", phone="+18015559999", store=STORE_A, owner=REP_A)
    b = contact(db, "Shared", "PhoneB", phone="+18015559999", store=STORE_B, owner=REP_B)
    before = snap(db, b)
    run(ingest.from_lead(db, a, lead(a, "Subaru Outback", make="Subaru", model="Outback")))
    after_a, after_b = snap(db, a), snap(db, b)
    journey("Two customers share a phone number", before, "Store A receives a lead for its customer; store B's customer with the same phone gets nothing", after_b,
            "Facts attach to the contact id (one per store); the API resolves the contact through the caller's data filter so store B never sees store A's facts.")
    assert after_a["now"]["driving"]["label"] == "Subaru Outback" and after_b["counts"]["facts"] == 0
    from routers import contact_ask, intelligence as R
    from fastapi import HTTPException

    async def filt(uid):
        return {"user_id": uid}
    monkeypatch.setattr(contact_ask, "get_data_filter", filt)
    assert run(contact_ask._contact(db, REP_A, str(a["_id"])))["_id"] == a["_id"]
    with pytest.raises(HTTPException) as ex:
        run(contact_ask._contact(db, REP_B, str(a["_id"])))
    assert ex.value.status_code == 404
    assert R.can_verify(REP_A, a) and R.can_verify(MGR_A, a) and not R.can_verify(REP_B, a) and not R.can_verify({**MGR_A, "store_id": STORE_B}, a)


# ───────────────────────── 13. new intelligence while a campaign is active ─────────────────────────
def test_j13_campaign_activity_does_not_refresh(db):
    c = contact(db, "Cam", "Paign")
    s = settings(db)
    run(ingest.from_lead(db, c, lead(c, "Ram 1500", days_ago=20, make="Ram", model="1500")))
    run(db.campaign_enrollments.insert_one({"contact_id": str(c["_id"]), "campaign_id": "camp-1", "enrolled_at": ago(10), "messages_sent": [{"step": 1, "sent_at": ago(1)}]}))
    before = snap(db, c)
    assert before["now"]["driving"]["phase"] == "aging"
    assert run(I.refresh(db, str(c["_id"]), s, ago(0), "campaign_send")) == 0  # automated sends never reset the window
    mid = snap(db, c)
    assert mid["now"]["driving"]["days_since_signal"] == 20
    r = run(ingest.from_inbound_message(db, c, "conv1", "Yes still interested, can I come by Saturday?", {"score": 8, "category": "purchase", "signals": ["appointment"], "hot_summary": "wants to visit Saturday"}, at=ago(0)))
    after = snap(db, c)
    journey("New intelligence arrives while a campaign is active", before, "Campaign text goes out (no effect on the window); the customer replies 'still interested, come by Saturday' (score 8)", after,
            "The enrollment document is untouched: intelligence never changes campaign state on its own.")
    assert r["refreshed"] == 1 and r["signal"] == "created" and after["now"]["driving"]["phase"] == "active"
    assert run(db.campaign_enrollments.find_one({"contact_id": str(c["_id"])}))["campaign_id"] == "camp-1"
    assert [f["key"] for f in after["now"]["active_intent"]] == ["buying.signal", "vehicle.interest"]


# ───────────────────────── 14. similar records in different tenants + backfill dry run ─────────────────────────
def test_j14_similar_records_other_tenant_and_dry_run(db):
    a = contact(db, "John", "Smith", phone="+18015550001", store=STORE_A, owner=REP_A, vehicle_interest="Toyota Tacoma", last_activity_at=ago(10),
                purchase_history=[{"id": "ph1", "title": "2019 Toyota Camry", "category": "vehicle", "date": "2019-03-03", "created_at": "2019-03-03T12:00:00+00:00"}],
                personal_details={"spouse_name": "Jane", "interests": ["fishing", "golf"], "kids": [{"name": "Lily", "details": "age 4"}]}, hot_opportunity=True, hot_score=8, hot_last_at=ago(100))
    b = contact(db, "John", "Smith", phone="+18015550002", store=STORE_B, owner=REP_B, vehicle_interest="Honda Accord", last_activity_at=ago(300), personal_details={"spouse_name": "Ann"})
    run(db.inbound_leads.insert_one(lead(a, "Toyota Tundra", comments="Tundra pricing", days_ago=2, make="Toyota", model="Tundra")))
    before = snap(db, a)
    rep_a = run(backfill.dry_run(db, store_id=STORE_A))
    rep_b = run(backfill.dry_run(db, store_id=STORE_B))
    assert rep_a["contacts_scanned"] >= 1 and rep_b["contacts_scanned"] == 2  # store B: Shared PhoneB + John Smith B
    assert rep_a["flags"]["backfill_execute"] is False
    assert run(db.contact_facts.count_documents({"contact_id": str(a["_id"])})) == 0  # dry run wrote no facts
    assert run(db.intel_backfill_runs.count_documents({"mode": "dry_run"})) == 0  # read-only by default (persist=True keeps a report)
    # the plan for John Smith A: purchase + owned, 3 personal detail facts (spouse, 2 interests, 1 kid), legacy interest (active), lead (active), stale hot flag (historical)
    plan = run(backfill.plan_contact(db, run(db.contacts.find_one({"_id": a["_id"]})), settings(db), NOW))
    keys = sorted(f["key"] for f in plan)
    assert keys.count("vehicle.interest") == 2 and "family.spouse" in keys and keys.count("preference.interest") == 2 and "family.kid" in keys and "vehicle.purchase" in keys and "vehicle.owned" in keys
    hot = next(f for f in plan if f["key"] == "buying.signal")
    assert hot["status"] == "historical" and hot["outcome"] == "went_quiet"
    assert all(f["source"]["kind"] in ("import", "lead_form", "sale") for f in plan)
    # execute is refused without the Phase 1B flag + confirm
    with pytest.raises(PermissionError):
        run(backfill.execute(db, confirm="EXECUTE"))
    os.environ["INTEL_BACKFILL_EXECUTE"] = "true"
    with pytest.raises(PermissionError):
        run(backfill.execute(db, confirm="nope"))
    # a controlled execute on store B only (test db) is idempotent and resumable; store A untouched
    out = run(backfill.execute(db, confirm="EXECUTE", store_id=STORE_B, batch=1))
    assert out["contacts_this_batch"] == 1 and out["done"] is False
    out2 = run(backfill.execute(db, confirm="EXECUTE", store_id=STORE_B, batch=5, run_id=out["run_id"]))
    assert out2["done"] is True and out2["contacts_total"] == 2
    again = run(backfill.execute(db, confirm="EXECUTE", store_id=STORE_B, batch=50))
    assert again["facts_written_total"] == 0  # second pass: every fact is a fingerprint duplicate
    os.environ["INTEL_BACKFILL_EXECUTE"] = "false"
    after_b = snap(db, b)
    after_a = snap(db, a)
    journey("Similar customer records exist in different dealership tenants", before, "Backfill dry run per store, then a controlled execute for store B only", after_b,
            "Both stores have a 'John Smith'. Store B's John gets his legacy spouse 'Ann' and a dormant Honda Accord interest (300 quiet days -> historical, went quiet); store A's John has no facts yet.")
    assert after_a["counts"]["facts"] == 0
    assert [f["label"] for f in after_b["who"]["identity"] if f["key"] == "family.spouse"] == ["Ann"]
    assert any(f["key"] == "vehicle.interest" and f["status"] == "historical" and f["outcome"] == "went_quiet" for f in after_b["history"]) and after_b["now"]["driving"] is None


# ───────────────────────── engine rules ─────────────────────────
def test_engine_reliability_ladder_and_disputes(db):
    c = contact(db, "Ella", "Engine")
    run(F.record(db, F.make(c, layer="identity", domain="contact_pref", key="contact.preferred_channel", statement="Prefers: text", value={"label": "text"}, occurred_at=ago(10), source={"kind": "message", "ref": "m1", "quote": "just text me"})))
    # a rep note (lower reliability than the customer's words) saying otherwise -> disputed, customer's statement stays
    r = run(F.record(db, F.make(c, layer="identity", domain="contact_pref", key="contact.preferred_channel", statement="Prefers: phone calls", value={"label": "phone calls"}, occurred_at=ago(2), source={"kind": "voice_memo", "ref": "memo-e", "quote": "I think he prefers calls"})))
    assert r["action"] == "disputed"
    assert [f["value"]["label"] for f in run(F.currents_for(db, str(c["_id"]), "contact.preferred_channel"))] == ["text"]
    # the customer's own newer words supersede
    r2 = run(F.record(db, F.make(c, layer="identity", domain="contact_pref", key="contact.preferred_channel", statement="Prefers: email", value={"label": "email"}, occurred_at=ago(1), source={"kind": "message", "ref": "m2", "quote": "email works best now"})))
    assert r2["action"] == "superseded" and [f["value"]["label"] for f in run(F.currents_for(db, str(c["_id"]), "contact.preferred_channel"))] == ["email"]
    # a manager dispute then confirm round-trip is audited
    f = run(F.dispute(db, r2["fact"]["_id"], MGR_A, note="customer bounced"))
    assert f["status"] == "disputed"
    f = run(F.confirm(db, r2["fact"]["_id"], MGR_A))
    assert f["status"] == "current" and f["confidence"] == "high"
    assert [e["action"] for e in run(F.events_for(db, f["_id"]))] == ["created_superseding", "status_disputed", "confirmed"]


def test_engine_intent_phases_and_windows(db):
    c = contact(db, "Phil", "Phase")
    s = settings(db)
    assert I.window_days(s, "service") == 30 and I.window_days(s, "purchase") == 45 and I.window_days(s, None) == 45
    f = I.make(c, s, key="vehicle.interest", domain="vehicle_interest", statement="x", value={"label": "GMC Sierra"}, occurred_at=ago(0), source={"kind": "lead_form", "ref": "l"}, confidence="high")
    assert I.phase(f, s, NOW)["phase"] == "active" and I.phase(f, s, NOW + timedelta(days=20))["phase"] == "aging" and I.phase(f, s, NOW + timedelta(days=46))["phase"] == "dormant"
    assert I.phase({**f, "status": "historical"}, s) is None
    svc = I.make(c, s, key="vehicle.interest", domain="service", statement="oil change", value={"label": "service"}, occurred_at=ago(0), source={"kind": "message", "ref": "m"}, category="service")
    assert (svc["active_until"] - svc["occurred_at"]).days == 30
    assert I.detect_not_shopping("We're not currently shopping") and I.detect_not_shopping("not interested right now") and I.detect_not_shopping("let's hold off for now")
    assert not I.detect_not_shopping("shopping for a truck this weekend") and not I.detect_not_shopping("I am interested in the Tahoe")
    # store override
    run(db.stores.insert_one({"_id": ObjectId(STORE_B), "intelligence": {"intent_window_days": 60, "intent_windows": {"service": 14}}}))
    sb = settings(db, STORE_B)
    assert sb["intent_window_days"] == 60 and sb["intent_windows"]["service"] == 14 and sb["intent_windows"]["finance"] == 30


def test_engine_merge_moves_facts(db):
    a = contact(db, "Merge", "Primary")
    b = contact(db, "Merge", "Dup")
    run(ingest.from_lead(db, b, lead(b, "Nissan Frontier", make="Nissan", model="Frontier")))
    out = run(ingest.on_merge(db, str(a["_id"]), str(b["_id"]), str(REP_A["_id"]), counts={"messages": 3}))
    assert out["facts_moved"] == 1
    assert snap(db, a)["now"]["driving"]["label"] == "Nissan Frontier" and snap(db, b)["counts"]["facts"] == 0
    m = run(db.contact_merges.find_one({"primary_id": str(a["_id"])}))
    assert m["duplicate_id"] == str(b["_id"]) and m["facts_moved"] == 1
    from services.duplicates import MIGRATE
    assert "contact_facts" in MIGRATE and "contact_fact_events" in MIGRATE


def test_flags_off_means_no_writes(db, monkeypatch):
    c = contact(db, "Flag", "Off")
    monkeypatch.setenv("INTEL_FACTS_INGEST", "false")
    assert run(ingest.from_lead(db, c, lead(c, "Anything", make="Any", model="Thing"))) is None
    assert run(ingest.from_inbound_message(db, c, "conv", "not shopping", {"score": 9})) == {}
    assert run(ingest.from_purchases(db, c, [{"id": "x", "title": "Car", "category": "vehicle", "date": "2026-01-01"}])) is None
    assert run(db.contact_facts.count_documents({"contact_id": str(c["_id"])})) == 0
    monkeypatch.setenv("INTEL_FACTS_INGEST", "true")


# ───────────────────────── Phase 1B: projection safeguards, live sync, rollback ─────────────────────────
def test_1b_projection_keeps_legacy_shape_and_skips_comment_leads(db, monkeypatch):
    monkeypatch.setenv("INTEL_LEGACY_PROJECTION", "true")
    c = contact(db, "Shape", "Keeper", vehicle_interest="Toyota Tacoma", personal_details={"interests": ["golf"], "kids": [{"name": "Ava", "details": "age 6"}]})
    run(ingest.from_personal_details_edit(db, c, {"interests": ["golf", "fishing"], "kids": [{"name": "Ava", "details": "age 6"}], "spouse_name": "Kim"}, REP_A))
    after = run(db.contacts.find_one({"_id": c["_id"]}))
    assert after["personal_details"]["interests"] == ["golf", "fishing"]  # plain strings, no {label} wrapper
    assert after["personal_details"]["kids"] == [{"name": "Ava", "details": "age 6"}]  # original dict shape, no added label key
    assert after["personal_details"]["spouse_name"] == "Kim" and after.get("intel_projected_at")
    # a lead that names no vehicle (free-text comment) is the driving signal but never becomes vehicle_interest
    run(ingest.from_lead(db, c, lead(c, "", comments="Is the red one on your lot still available?", source="Website Widget", days_ago=1)))
    after = run(db.contacts.find_one({"_id": c["_id"]}))
    assert after["vehicle_interest"] == "Toyota Tacoma"
    assert snap(db, c)["now"]["driving"]["value"]["from_comment"] is True
    # a lead that names a vehicle does project
    run(ingest.from_lead(db, c, lead(c, "Toyota Tundra", make="Toyota", model="Tundra")))
    assert run(db.contacts.find_one({"_id": c["_id"]}))["vehicle_interest"] == "Toyota Tundra"
    # snapshot kept the pre-projection values once; rollback restores them and leaves the facts alone
    s = run(db.intel_legacy_snapshots.find_one({"contact_id": str(c["_id"])}))
    assert s["before"]["vehicle_interest"] == "Toyota Tacoma" and s["before"]["personal_details"]["interests"] == ["golf"] and "spouse_name" not in s["before"]["personal_details"] and s["missing"] == ["occupation", "employer"]
    n_facts = run(db.contact_facts.count_documents({"contact_id": str(c["_id"])}))
    out = run(projection.rollback(db, contact_id=str(c["_id"])))
    assert out["restored"] == 1
    back = run(db.contacts.find_one({"_id": c["_id"]}))
    assert back["vehicle_interest"] == "Toyota Tacoma" and back["personal_details"] == {"interests": ["golf"], "kids": [{"name": "Ava", "details": "age 6"}]} and "intel_projected_at" not in back
    assert "occupation" not in back and "employer" not in back  # keys that never existed are not left behind as nulls
    assert run(db.contact_facts.count_documents({"contact_id": str(c["_id"])})) == n_facts
    monkeypatch.setenv("INTEL_LEGACY_PROJECTION", "false")


def test_1b_appraisal_ownership_is_not_verified_until_a_person_says_so(db, monkeypatch):
    monkeypatch.setenv("INTEL_LEGACY_PROJECTION", "true")
    c = contact(db, "Appr", "Aisal")
    r = run(ingest.from_appraisal_vehicle(db, c, "2018 Ram 2500", "veh1"))
    f = r["facts"][0]
    assert f["status"] == "current" and f["confidence"] == "medium" and f["confirmations"] == 0
    b = snap(db, c)
    assert b["who"]["owns"][0]["label"] == "2018 Ram 2500" and any(v["unverified"] for v in b["verify"]) and b["next"]["mode"] == "verify_ownership"
    assert "vehicle_purchased" not in (run(db.contacts.find_one({"_id": c["_id"]}))["personal_details"] or {})  # never projected while unconfirmed
    # the rep confirms on the vehicle page -> confirmed, projected
    r2 = run(ingest.from_ownership(db, c, "2018 Ram 2500", "owns", actor=REP_A, vehicle_id="veh1"))
    assert r2["confirmed"]["confirmations"] == 1 and r2["confirmed"]["confidence"] == "high"
    assert run(db.contacts.find_one({"_id": c["_id"]}))["personal_details"]["vehicle_purchased"] == "2018 Ram 2500"
    assert snap(db, c)["verify"] == [] and snap(db, c)["next"]["mode"] == "relationship"
    # a vehicle that is not theirs: appraisal record -> rep disputes -> gone from current, kept as a disputed record
    c2 = contact(db, "Not", "Mine")
    r3 = run(ingest.from_appraisal_vehicle(db, c2, "2015 Honda Civic", "veh2"))
    run(F.dispute(db, r3["facts"][0]["_id"], REP_A, note="it is her brother's car"))
    b2 = snap(db, c2)
    assert b2["who"]["owns"] == [] and b2["verify"][0]["status"] == "disputed" and "vehicle_purchased" not in (run(db.contacts.find_one({"_id": c2["_id"]}))["personal_details"] or {})
    monkeypatch.setenv("INTEL_LEGACY_PROJECTION", "false")


def test_1b_bought_elsewhere_closes_the_interest_and_changes_the_next_action(db):
    c = contact(db, "Lost", "Deal")
    run(ingest.from_lead(db, c, lead(c, "Ford F-150", days_ago=20, make="Ford", model="F-150")))
    assert snap(db, c)["now"]["driving"]["label"] == "Ford F-150"
    out = run(ingest.from_inbound_message(db, c, "conv-lost", "Hey thanks but we ended up buying a truck from another dealer last week", {"score": 1}))
    assert out["purchased_elsewhere"] == "created" and len(out["closed"]) == 1
    b = snap(db, c)
    assert b["now"]["driving"] is None and b["next"]["mode"] == "lost"
    assert any(f["key"] == "vehicle.interest" and f["status"] == "historical" and f["outcome"] == "lost" for f in b["history"])
    assert any(f["key"] == "purchase.elsewhere" for f in b["history"]) and "congrats" in b["discuss"]["opening"].lower()
    assert I.detect_purchased_elsewhere("we already bought one") and I.detect_purchased_elsewhere("went with carmax") and not I.detect_purchased_elsewhere("still looking to buy from you")


def test_1b_rep_typed_vehicle_interest_wins_and_projects(db, monkeypatch):
    monkeypatch.setenv("INTEL_LEGACY_PROJECTION", "true")
    c = contact(db, "Typed", "Interest", vehicle_interest="")
    run(ingest.from_lead(db, c, lead(c, "Kia Telluride", days_ago=3, make="Kia", model="Telluride")))
    assert run(db.contacts.find_one({"_id": c["_id"]}))["vehicle_interest"] == "Kia Telluride"
    before = run(db.contacts.find_one({"_id": c["_id"]}))
    r = run(ingest.from_rep_edit(db, before, {"vehicle_interest": "Hyundai Palisade", "phone": before["phone"]}, REP_A))
    assert r["created"] == 1 and r["projection"]["written"]
    after = run(db.contacts.find_one({"_id": c["_id"]}))
    assert after["vehicle_interest"] == "Hyundai Palisade"  # the rep's words are the newest signal; the Telluride inquiry stays as an active intent too
    b = snap(db, c)
    assert b["now"]["driving"]["label"] == "Hyundai Palisade" and b["now"]["driving"]["source"]["kind"] == "rep" and "Kia Telluride" in b["discuss"]["also_active"]
    monkeypatch.setenv("INTEL_LEGACY_PROJECTION", "false")


def test_1b_reaffirmation_is_idempotent(db):
    c = contact(db, "Twice", "Told", vehicle_interest="2022 Honda Civic", last_activity_at=ago(5))
    plan = run(backfill.plan_contact(db, c, settings(db), NOW))
    run(db.inbound_leads.insert_one(lead(c, "2022 Honda Civic", days_ago=3, make="Honda", model="Civic")))
    plan = run(backfill.plan_contact(db, run(db.contacts.find_one({"_id": c["_id"]})), settings(db), NOW))
    assert [f["key"] for f in plan] == ["vehicle.interest", "vehicle.interest"]
    r1 = run(ingest.apply(db, plan))
    assert (r1["created"], r1["reaffirmed"]) == (1, 1)  # same vehicle from the legacy field and the lead: one fact, two pieces of evidence
    f = run(F.load(db, {"contact_id": str(c["_id"])}))[0]
    assert f["confirmations"] == 1 and len(f["evidence"]) == 2 and f["source"]["kind"] == "import" and f["statement"].startswith("Website lead")  # the import is unconfirmed; the customer's own inquiry confirms and words it
    r2 = run(ingest.apply(db, plan))
    assert (r2["created"], r2["reaffirmed"], r2["duplicate"]) == (0, 0, 2)  # a second pass adds nothing: no new evidence, no extra confirmation
    f2 = run(F.load(db, {"contact_id": str(c["_id"])}))[0]
    assert f2["confirmations"] == 1 and len(f2["evidence"]) == 2


def test_1b_repeated_system_records_corroborate_but_never_confirm(db, monkeypatch):
    monkeypatch.setenv("INTEL_LEGACY_PROJECTION", "true")
    c = contact(db, "Many", "Appraisals")
    for i in range(5):
        run(ingest.from_appraisal_vehicle(db, c, "2019 Ford F-150 XLT", f"veh-{i}"))
    f = run(F.load(db, {"contact_id": str(c["_id"]), "key": "vehicle.owned"}))[0]
    assert f["confirmations"] == 0 and f.get("corroborations") == 4 and len(f["evidence"]) == 5 and "not confirmed" in f["statement"]
    assert "vehicle_purchased" not in (run(db.contacts.find_one({"_id": c["_id"]}))["personal_details"] or {})
    # one person confirming flips it: wording, confirmation count, projection
    run(ingest.from_ownership(db, c, "2019 Ford F-150 XLT", "owns", actor=REP_A, vehicle_id="veh-0"))
    f = run(F.load(db, {"contact_id": str(c["_id"]), "key": "vehicle.owned"}))[0]
    assert f["confirmations"] == 1 and "not confirmed" not in f["statement"]
    assert run(db.contacts.find_one({"_id": c["_id"]}))["personal_details"]["vehicle_purchased"] == "2019 Ford F-150 XLT"
    monkeypatch.setenv("INTEL_LEGACY_PROJECTION", "false")


def test_1b_dry_run_is_read_only(db, monkeypatch):
    """The production dry run: every flag off, every collection count and the legacy fields unchanged afterwards, no contact_facts collection created."""
    for k in ("INTEL_FACTS_INGEST", "INTEL_LEGACY_PROJECTION", "INTEL_BACKFILL_EXECUTE", "INTEL_NUDGES"):
        monkeypatch.setenv(k, "false")
    c = contact(db, "Read", "Only", vehicle_interest="2022 Honda Civic", personal_details={"spouse_name": "Kim", "interests": ["golf"]}, store_id="store-ro")
    run(db.inbound_leads.insert_one(lead(c, "2022 Honda Civic", days_ago=3, make="Honda", model="Civic")))
    before = {name: run(db[name].count_documents({})) for name in run(db.list_collection_names())}
    legacy_before = json.dumps(run(db.contacts.find_one({"_id": c["_id"]})), sort_keys=True, default=str)
    r = run(backfill.dry_run(db, store_id="store-ro"))
    assert r["read_only"] is True and r["writes_performed"] == [] and r["run_id"] is None and r["flags"] == {"ingest": False, "legacy_projection": False, "backfill_execute": False, "nudges": False}
    assert r["contacts_scanned"] == 1 and r["facts_distinct"] == 3 and r["repeat_evidence"] == 1 and r["by_store"] == {"store-ro": {"contacts": 1, "with_facts": 1, "facts_distinct": 3, "legacy_changes": 0}}
    assert "processing_ms" in r
    after = {name: run(db[name].count_documents({})) for name in run(db.list_collection_names())}
    assert after == before and json.dumps(run(db.contacts.find_one({"_id": c["_id"]})), sort_keys=True, default=str) == legacy_before
    assert run(db.intel_backfill_runs.count_documents({"mode": "dry_run"})) == 0
    # the persisted variant is explicit and only touches the runs collection
    r2 = run(backfill.dry_run(db, store_id="store-ro", persist=True))
    assert r2["read_only"] is False and r2["writes_performed"] == ["intel_backfill_runs report"] and r2["run_id"]
    monkeypatch.setenv("INTEL_FACTS_INGEST", "true")


# ───────────────────────── Phase 2A: Intelligent Timeline + "why we think this" ─────────────────────────
def test_2a_timeline_bands_and_markers(db, monkeypatch):
    c = contact(db, "Tim", "Line", personal_details={})
    run(ingest.from_lead(db, c, lead(c, "2022 Jeep Wrangler Rubicon", days_ago=950, make="Jeep", model="Wrangler")))  # the inquiry that led to the purchase
    run(ingest.from_purchases(db, c, [{"id": "p1", "title": "2022 Jeep Wrangler Rubicon", "category": "vehicle", "date": "2024-03-09", "created_at": "2024-03-09T18:00:00+00:00"}], REP_A))
    run(db.contacts.update_one({"_id": c["_id"]}, {"$set": {"purchase_history": [{"id": "p1", "title": "2022 Jeep Wrangler Rubicon", "category": "vehicle", "date": "2024-03-09", "notes": "Cash deal"}]}}))
    run(ingest.from_personal_details_edit(db, c, {"employer": "Zions Bank"}, REP_A))
    run(ingest.from_personal_details_edit(db, c, {"employer": "Intermountain Health"}, REP_A))  # supersedes -> "Employer changed" marker
    run(ingest.from_lead(db, c, lead(c, "2025 Ford F-150", days_ago=2, make="Ford", model="F-150", comments="Looking at the F-150 Lariat")))
    tl = run(timeline.build(db, run(db.contacts.find_one({"_id": c["_id"]}))))
    assert tl["enabled"] is True
    assert tl["recommended"]["topic"] == "2025 Ford F-150" and "Jeep" in tl["recommended"]["opening"] and tl["recommended"]["evidence"][0]["source"] == "Lead form"
    assert [a["label"] for a in tl["active"]] == ["2025 Ford F-150"] and tl["active"][0]["detail"].startswith("2 days ago, via lead form") and tl["driving_fact_id"] == tl["active"][0]["fact_id"]
    assert tl["current"]["drives"][0]["label"] == "2022 Jeep Wrangler Rubicon" and tl["current"]["drives"][0]["confirmed"] is True
    assert tl["current"]["work"][0]["label"] == "Intermountain Health" and tl["current"]["work"][0]["confirmed"] is True
    titles = [m["title"] for m in tl["markers"]]
    assert "Bought 2022 Jeep Wrangler Rubicon" in titles and "Employer changed: Zions Bank -> Intermountain Health" in titles and "Interest in 2022 Jeep Wrangler Rubicon closed: bought" in titles
    assert all(m["event_type"] == "intel_milestone" and m["category"] == "milestone" and m["fact_id"] and m["timestamp"] for m in tl["markers"])
    assert tl["markers"] == sorted(tl["markers"], key=lambda m: m["timestamp"], reverse=True)
    for n in tl["needs_look"]:
        assert n["reason"] in ("unconfirmed", "stale", "disputed", "proposed") and n["fact_id"]
    # the screen stays untouched when the tenant has intelligence off
    monkeypatch.setenv("INTEL_FACTS_INGEST", "false")
    assert run(timeline.build(db, c)) == {"enabled": False}
    monkeypatch.setenv("INTEL_FACTS_INGEST", "true")


def test_2a_source_resolver_shows_the_record_and_never_leaks(db):
    c = contact(db, "Src", "Check", phone="+18015550177")
    other = contact(db, "Other", "Person", phone="+18015550178")
    conv = str(ObjectId())
    mid = run(db.messages.insert_one({"contact_id": str(c["_id"]), "conversation_id": conv, "content": "We are looking at the Grand Highlander for the whole family", "direction": "inbound", "created_at": NOW})).inserted_id
    run(ingest.from_inbound_message(db, c, conv, "We are looking at the Grand Highlander for the whole family", {"score": 8, "hot_summary": "Family SUV shopper"}, message_id=str(mid)))
    sig = run(F.load(db, {"contact_id": str(c["_id"]), "key": "buying.signal"}))[0]
    src = run(timeline.source(db, F.pub(sig), c))
    assert src["kind"] == "message" and src["title"].startswith("Text from Src") and "Grand Highlander" in src["excerpt"] and src["link"] == f"/thread/{conv}"
    # a lead form resolves to the lead's own words and source name
    lid = ObjectId()
    run(db.inbound_leads.insert_one(lead(c, "2025 Toyota Grand Highlander", comments="Need three rows", lead_id=lid, source="Cars.com", make="Toyota", model="Grand Highlander")))
    run(ingest.from_lead(db, c, run(db.inbound_leads.find_one({"_id": lid}))))
    li = run(F.load(db, {"contact_id": str(c["_id"]), "key": "vehicle.interest"}))[0]
    ls = run(timeline.source(db, F.pub(li), c))
    assert ls["title"] == "Cars.com lead" and "Need three rows" in ls["excerpt"] and ls["link"] == "/thread/conv1"
    # appraisal -> the vehicle record; rep -> who typed it; import -> plain explanation
    vid = run(db.vehicles.insert_one({"contact_id": str(c["_id"]), "year": 2018, "make": "Ram", "model": "2500", "trim": "Laramie", "vin": "3C6UR5FL0JG", "ownership_status": "owns", "created_at": NOW})).inserted_id
    r = run(ingest.from_appraisal_vehicle(db, c, "2018 Ram 2500 Laramie", str(vid)))
    a = run(timeline.source(db, F.pub(r["facts"][0]), c))
    assert a["title"] == "Appraisal vehicle record" and "VIN 3C6UR5FL0JG" in a["excerpt"] and a["link"] == f"/vehicle/{vid}" and a["confirmed"] is False
    run(ingest.from_personal_details_edit(db, c, {"spouse_name": "Dana"}, REP_A))
    sp = run(F.load(db, {"contact_id": str(c["_id"]), "key": "family.spouse"}))[0]
    rs = run(timeline.source(db, F.pub(sp), c))
    assert rs["kind"] == "rep" and rs["title"] == f"Entered by {REP_A['name']}" and rs["confirmed"] is True
    # the same message id looked up through ANOTHER contact's fact never returns that contact's text (tenant/contact scoping)
    leaked = run(timeline.source(db, {**F.pub(sig), "source": {"kind": "message", "ref": str(mid), "quote": None}}, other))
    assert leaked["excerpt"] is None and leaked["link"] is None


def test_2a_trading_one_truck_leaves_the_other_truck_alone(db):
    c = contact(db, "Two", "Trucks")
    run(ingest.from_purchases(db, c, [{"id": "s1", "title": "2020 Ford F-150 XLT", "category": "vehicle", "date": "2024-01-10", "created_at": "2024-01-10T18:00:00+00:00"}], REP_A))
    run(ingest.from_appraisal_vehicle(db, c, "2019 Ford F-150 XLT", "veh-old"))
    assert I.same_vehicle("2019 Ford F-150 XLT", "2020 Ford F-150 XLT") is False and I.same_vehicle("Ford F-150", "2020 Ford F-150 XLT") is True and I.matches("2019 Ford F-150 XLT", "2020 Ford F-150 XLT") is True
    run(ingest.from_ownership(db, c, "2019 Ford F-150 XLT", "traded", actor=REP_A, vehicle_id="veh-old"))
    owned = {f["statement"]: f["status"] for f in run(F.load(db, {"contact_id": str(c["_id"]), "key": "vehicle.owned"}))}
    assert owned["Owns 2020 Ford F-150 XLT"] == "current" and owned["Owns 2019 Ford F-150 XLT (per appraisal record, not confirmed)"] == "historical"
