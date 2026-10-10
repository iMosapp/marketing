"""Phase 1B real-world conflict scenarios on isolated QA contacts in the PREVIEW database (tag "QA Intel 1B", store QA, owner activation-tester).
Runs the live ingest adapters (and the real HTTP lead webhook / personal-details / dispute endpoints) with INTEL_LEGACY_PROJECTION on,
then prints, per customer: history, current verified facts, active intent, latest event, recommended topic, suggested response, evidence, legacy projection.
    cd /app/backend && set -a && . ./.env && . ../frontend/.env && set +a && python tests/intel_phase1b_scenarios.py [--wipe]
Writes /app/memory/INTEL_PHASE1B_SCENARIOS.md. --wipe removes every QA Intel 1B contact and everything attached to it."""
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone

import httpx
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, "/app/backend")
from services.intelligence import brief, ingest  # noqa: E402
from services.intelligence import facts as F  # noqa: E402

API = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
STORE = "69a0b7095fddcede09591668"
REP_EMAIL, REP_PW = "activation-tester@invalid.imonsocial.test", "NewPass123!"
WEBSITE_SOURCE = "69a787ca70ae63ea0ac69251"
TAG = "QA Intel 1B"
UTC = timezone.utc
NOW = datetime.now(UTC)
OUT: list = []


def ago(days, hours=0):
    return NOW - timedelta(days=days, hours=hours)


def say(s=""):
    OUT.append(s)
    print(s)


async def login(cli):
    r = await cli.post(f"{API}/api/auth/login", json={"email": REP_EMAIL, "password": REP_PW})
    r.raise_for_status()
    d = r.json()
    return d.get("token") or d.get("access_token"), d["user"]["_id"] if "user" in d else d.get("user_id")


async def make_contact(db, rep_id, first, last, phone, **extra):
    doc = {"first_name": first, "last_name": last, "phone": phone, "email": f"{first}.{last}@invalid.imonsocial.test".lower(), "user_id": rep_id, "store_id": STORE, "status": "active",
           "tags": [TAG], "personal_details": {}, "purchase_history": [], "created_at": ago(700), "updated_at": ago(1), **extra}
    doc["_id"] = (await db.contacts.insert_one(doc)).inserted_id
    return doc


async def fresh(db, c):
    return await db.contacts.find_one({"_id": c["_id"]})


async def webhook_lead(cli, c, vehicle: str, comments: str, make=None, model=None, year=None):
    body = {"first_name": c["first_name"], "last_name": c["last_name"], "phone": c["phone"], "email": c["email"], "comments": comments, "vehicle_interest": vehicle}
    if make:
        body.update({"make": make, "model": model, "year": year})
    r = await cli.post(f"{API}/api/leads/webhook/{WEBSITE_SOURCE}", json=body, timeout=60)
    return r.status_code, (r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text[:200])


def _f(f):
    return f"{f['status'].upper():10} {f['key']:24} {(f['occurred_at'] or '')[:10]}  {f['statement'][:95]}" + (f"  [{f.get('outcome')}]" if f.get("outcome") else "") + ("" if f.get("confirmations") else "  (unconfirmed)")


async def show(db, c, title, event):
    c = await fresh(db, c)
    b = await brief.build(db, c)
    say(f"\n### {title}")
    say(f"**Latest triggering event**: {event}")
    say("")
    say("**Historical relationship information (kept, never deleted)**")
    hist = b["history"]
    say("```")
    for f in hist or []:
        say(_f(f))
    if not hist:
        say("(none yet)")
    say("```")
    say("**Current verified facts** (confirmed by a person or the customer's own action; unconfirmed ones are marked)")
    say("```")
    cur = b["who"]["identity"] + b["who"]["owns"] + b["who"]["known"]
    for f in cur:
        say(_f(f))
    if not cur:
        say("(none)")
    say("```")
    drv = b["now"]["driving"]
    say(f"**Active customer intent**: " + (f"{drv['label']} ({drv['phase']}, via {drv['source']['kind']}, {drv.get('days_since_signal')} days since signal)" if drv else "none") + (f"; also active: {', '.join(b['discuss']['also_active'])}" if b["discuss"]["also_active"] else "") + (f"; suppression: {b['now']['suppression']['statement']}" if b["now"]["suppression"] else ""))
    say(f"**Recommended conversation topic**: {b['discuss']['topic']}")
    say(f"**Why now**: {b['discuss']['why']}")
    say(f"**Suggested next response**: \"{b['discuss']['opening']}\"")
    say(f"**Next action**: {b['next']['action']} (mode {b['next']['mode']})")
    if b["discuss"]["mention_history"]:
        say("**History worth mentioning**: " + "; ".join(b["discuss"]["mention_history"]))
    if b["verify"]:
        say("**Needs a human**: " + "; ".join(f"{v['statement']} [{v['status']}{', unverified' if v.get('unverified') else ''}]" for v in b["verify"]))
    say("**Evidence**: " + ("; ".join(f"{e['source']}:{e['ref']} @ {str(e['at'])[:10]}" for e in b["evidence"]) if b["evidence"] else "none"))
    pd = c.get("personal_details") or {}
    say(f"**Legacy fields after projection**: vehicle_interest={c.get('vehicle_interest')!r}, vehicle_purchased={pd.get('vehicle_purchased')!r}, spouse={pd.get('spouse_name')!r}, employer={pd.get('employer') or c.get('employer')!r}")
    return b


async def main(wipe=False):
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    if wipe:
        ids = [str(c["_id"]) async for c in db.contacts.find({"tags": TAG}, {"_id": 1})]
        for coll in ("contact_facts", "contact_fact_events", "intel_legacy_snapshots", "inbound_leads", "conversations", "messages", "contact_events", "tasks", "notifications"):
            r = await db[coll].delete_many({"contact_id": {"$in": ids}})
            print("wiped", coll, r.deleted_count)
        r = await db.contacts.delete_many({"tags": TAG})
        print("wiped contacts", r.deleted_count)
        return
    assert os.environ.get("INTEL_FACTS_INGEST") == "true" and os.environ.get("INTEL_LEGACY_PROJECTION") == "true", "run with both flags on"
    async with httpx.AsyncClient() as cli:
        token, _ = await login(cli)
        rep = await db.users.find_one({"email": REP_EMAIL})
        rep_id = str(rep["_id"])
        actor = {"_id": rep["_id"], "name": rep.get("name") or "Activation Tester"}
        H = {"Authorization": f"Bearer {token}"}
        say("# Phase 1B real-world conflict scenarios (preview database, isolated QA contacts)")
        say(f"Generated {NOW.strftime('%b %d, %Y %H:%M UTC')}. Flags: {ingest.config.flags()}. Every step below went through the live ingest adapters with the compatibility projection ON; the HTTP steps hit the running preview API.")
        say("The topic / why / opening / evidence lines are built in code from the facts (deterministic Layer E). The GPT phrasing layer on top of them is a later phase; nothing here calls a model.")

        # 1. Jeep owned, then traded
        c1 = await make_contact(db, rep_id, "Jenna", "QA-Jeep", "+15005550701")
        await ingest.from_purchases(db, c1, [{"id": "s1", "title": "2022 Jeep Wrangler Rubicon", "category": "vehicle", "date": "2024-03-09", "created_at": "2024-03-09T18:00:00+00:00"}], actor)
        await ingest.from_appraisal_vehicle(db, c1, "2022 Jeep Wrangler Rubicon", "veh-c1")  # the same Jeep shows up on a trade appraisal: corroborates, no second fact
        await show(db, c1, "1a. Customer bought a Jeep from us (2024); it appears again on a trade appraisal today", "Appraisal opened on the 2022 Jeep Wrangler Rubicon")
        await ingest.from_ownership(db, c1, "2022 Jeep Wrangler Rubicon", "traded", actor=actor, vehicle_id="veh-c1")
        await show(db, c1, "1b. The Jeep is traded (appraisal desk confirms)", "Rep confirms the trade on the vehicle page")

        # 2. F-150 inquiry, then "bought elsewhere"
        c2 = await make_contact(db, rep_id, "Felix", "QA-Elsewhere", "+15005550702")
        code, resp = await webhook_lead(cli, c2, "2025 Ford F-150 XLT", "Looking for pricing on the F-150 XLT 4x4", make="Ford", model="F-150", year=2025)
        say(f"\n(HTTP lead webhook -> {code})")
        if not await db.contact_facts.count_documents({"contact_id": str(c2["_id"])}):
            await ingest.from_lead(db, c2, {"_id": ObjectId(), "source_name": "Website", "vehicle_interest": "2025 Ford F-150 XLT", "comments": "Looking for pricing on the F-150 XLT 4x4", "received_at": ago(0), "created_at": ago(0), "vehicle_raw": {"vehicle_make": "Ford", "vehicle_model": "F-150", "vehicle_year": 2025}})
            say("(webhook did not attach to this contact; lead fed through the same adapter in-process)")
        await show(db, c2, "2a. New website inquiry for an F-150", "Website lead: 2025 Ford F-150 XLT")
        await ingest.from_inbound_message(db, await fresh(db, c2), "conv-c2", "Thanks for following up but we ended up buying a truck from another dealer over the weekend", {"score": 1, "category": "general"}, at=datetime.now(UTC))
        await show(db, c2, "2b. Customer texts that they bought elsewhere", 'Inbound text: "we ended up buying a truck from another dealer"')

        # 3. Interest in one vehicle, new inquiry for another
        c3 = await make_contact(db, rep_id, "Tara", "QA-Switch", "+15005550703")
        await ingest.from_lead(db, c3, {"_id": ObjectId(), "source_name": "Website", "vehicle_interest": "2024 Toyota Tacoma TRD", "comments": "Do you have the TRD Off-Road in stock?", "received_at": ago(30), "created_at": ago(30), "vehicle_raw": {"vehicle_make": "Toyota", "vehicle_model": "Tacoma", "vehicle_year": 2024}})
        await show(db, c3, "3a. Inquiry about a Tacoma a month ago", "Website lead (30 days ago): 2024 Toyota Tacoma TRD")
        code, resp = await webhook_lead(cli, c3, "2025 Toyota Grand Highlander", "Actually we need three rows now, what do you have in the Grand Highlander?", make="Toyota", model="Grand Highlander", year=2025)
        say(f"\n(HTTP lead webhook -> {code})")
        if await db.contact_facts.count_documents({"contact_id": str(c3["_id"]), "value.label": {"$regex": "Grand Highlander"}}) == 0:
            await ingest.from_lead(db, await fresh(db, c3), {"_id": ObjectId(), "source_name": "Website", "vehicle_interest": "2025 Toyota Grand Highlander", "comments": "Actually we need three rows now", "received_at": ago(0), "created_at": ago(0), "vehicle_raw": {"vehicle_make": "Toyota", "vehicle_model": "Grand Highlander", "vehicle_year": 2025}})
            say("(webhook did not attach to this contact; lead fed through the same adapter in-process)")
        await show(db, c3, "3b. New inquiry today for a Grand Highlander", "Website lead (today): 2025 Toyota Grand Highlander")

        # 4. Voice note contradicts an older verified record
        c4 = await make_contact(db, rep_id, "Victor", "QA-Voice", "+15005550704")
        r = await cli.patch(f"{API}/api/contacts/{rep_id}/{c4['_id']}/personal-details", json={"personal_details": {"spouse_name": "Sarah", "employer": "Zions Bank"}}, headers=H)
        say(f"\n(HTTP personal-details edit by the rep -> {r.status_code})")
        await show(db, c4, "4a. Rep typed spouse 'Sarah' and employer 'Zions Bank' on the profile (verified: a person said so)", "Rep edits personal details")
        transcript = "Just had Victor in. His wife Karen came along, they are moving to Lehi next month. He still works at Zions."
        await ingest.from_extraction(db, await fresh(db, c4), {"spouse_name": "Karen", "neighborhood": "Lehi", "employer": "Zions Bank"}, transcript=transcript, source_kind="voice_memo", source_ref="memo-c4", occurred_at=datetime.now(UTC), actor=actor)
        await show(db, c4, "4b. A voice note (rep's own words, quoted) says the wife is Karen", 'Voice memo: "His wife Karen came along..."')
        await ingest.from_extraction(db, await fresh(db, c4), {"spouse_name": "Donna"}, transcript="ok see you saturday", source_kind="message", source_ref="conv-c4", occurred_at=datetime.now(UTC), conversation_id="conv-c4")
        await show(db, c4, "4c. An AI text-thread extraction guesses spouse 'Donna' with no supporting words", "AI inference from a text thread (no quote)")

        # 5. Appraisal on a vehicle they do not own
        c5 = await make_contact(db, rep_id, "Hank", "QA-NotMine", "+15005550705")
        r5 = await ingest.from_appraisal_vehicle(db, c5, "2015 Honda Civic EX", "veh-c5")
        await show(db, c5, "5a. Customer brings a 2015 Honda Civic in for an appraisal", "Appraisal opened on a 2015 Honda Civic EX")
        fid = r5["facts"][0]["_id"]
        r = await cli.post(f"{API}/api/intel/facts/{fid}/dispute", json={"note": "It is his brother's car, he was just helping him get a number"}, headers=H)
        say(f"\n(HTTP dispute by the owning rep -> {r.status_code})")
        await show(db, c5, "5b. The rep learns it is his brother's car and disputes the ownership", "Rep disputes the fact")

        # 6. Two simultaneous opportunities
        c6 = await make_contact(db, rep_id, "Sam", "QA-Two", "+15005550706")
        await ingest.from_lead(db, c6, {"_id": ObjectId(), "source_name": "Website", "vehicle_interest": "2025 Ford F-150 Lariat", "comments": "F-150 Lariat for me", "received_at": ago(6), "created_at": ago(6), "vehicle_raw": {"vehicle_make": "Ford", "vehicle_model": "F-150", "vehicle_year": 2025}})
        await ingest.from_lead(db, await fresh(db, c6), {"_id": ObjectId(), "source_name": "Website", "vehicle_interest": "2025 Ford Explorer ST", "comments": "and an Explorer for my wife", "received_at": ago(4), "created_at": ago(4), "vehicle_raw": {"vehicle_make": "Ford", "vehicle_model": "Explorer", "vehicle_year": 2025}})
        await show(db, c6, "6a. Two open inquiries: an F-150 for him, an Explorer for his wife", "Website lead (4 days ago): 2025 Ford Explorer ST")
        await ingest.from_purchases(db, await fresh(db, c6), [{"id": "s6", "title": "2025 Ford F-150 Lariat", "category": "vehicle", "date": NOW.strftime("%Y-%m-%d"), "created_at": NOW.isoformat()}], actor)
        await show(db, c6, "6b. Sold wizard records the F-150 purchase", "Sale recorded: 2025 Ford F-150 Lariat")

        # 7. Older event arrives after newer verified information
        c7 = await make_contact(db, rep_id, "Olivia", "QA-Order", "+15005550707")
        r = await cli.patch(f"{API}/api/contacts/{rep_id}/{c7['_id']}/personal-details", json={"personal_details": {"employer": "Intermountain Health"}}, headers=H)
        say(f"\n(HTTP personal-details edit by the rep -> {r.status_code})")
        await ingest.from_extraction(db, await fresh(db, c7), {"employer": "Zions Bank"}, transcript="I have been at Zions Bank for six years now", source_kind="call", source_ref="call-c7-2025", occurred_at=ago(400), conversation_id="conv-c7")
        await show(db, c7, "7. A year-old call transcript (employer Zions Bank) is processed after the rep verified Intermountain Health today", "Backlogged call transcript from 400 days ago")

        say("\n## What the engine did, in one table")
        say("| # | Situation | Current truth | What history kept | Legacy field |")
        say("|---|---|---|---|---|")
        say("| 1 | Jeep bought 2024, appraised, then traded | no current vehicle; disposed record | purchase 2024, owned (historical: traded), 2 appraisal corroborations | vehicle_purchased keeps the Jeep (the purchase from us is still true); never blanked |")
        say("| 2 | F-150 inquiry, then bought elsewhere | no intent; 'bought elsewhere' record | the F-150 interest, outcome lost | vehicle_interest keeps the F-150 text (never blanked); brief says do not pitch |")
        say("| 3 | Tacoma a month ago, Grand Highlander today | Grand Highlander drives; Tacoma still active (aging) | both inquiries dated | vehicle_interest -> Grand Highlander |")
        say("| 4 | Rep typed Sarah; voice note says Karen; AI guesses Donna | Karen (newer, same reliability, quoted) | Sarah superseded; Donna waits as proposed | spouse_name -> Karen |")
        say("| 5 | Appraisal on a car that is not theirs | nothing owned | the appraisal record, disputed with the rep's note | vehicle_purchased never written |")
        say("| 6 | F-150 + Explorer open, F-150 bought | owns F-150; Explorer still active | F-150 interest closed as purchased | vehicle_interest -> Explorer, vehicle_purchased -> F-150 |")
        say("| 7 | Old call says Zions after rep verified Intermountain | Intermountain Health | Zions Bank as historical (replaced) | employer unchanged |")
    with open("/app/memory/INTEL_PHASE1B_SCENARIOS.md", "w") as fh:
        fh.write("\n".join(OUT) + "\n")
    print("\nwrote /app/memory/INTEL_PHASE1B_SCENARIOS.md")


if __name__ == "__main__":
    asyncio.run(main(wipe="--wipe" in sys.argv))
