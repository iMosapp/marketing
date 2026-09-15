"""Dutch demo client "QA Autobedrijf Jansen" (preview only). Idempotent; `--wipe` removes it.
Creates the nl-NL client with a Dutch team, a couple of completed shops (Dutch transcripts/coaching), a draft proposal and a kickoff link,
so the public proposal / kickoff / report / scorecard pages can be checked in Dutch. Sets from_number to the platform number so a kickoff submit never buys a Twilio number."""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

from bson import ObjectId
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv("/app/backend/.env")
TAG = "qa_dutch_demo"
NAME = "QA Autobedrijf Jansen"
PEOPLE = [("Sanne de Vries", "sales", "+31612340001", "Verkoopadviseur", [(86, 1), (72, 30)]), ("Pieter Bakker", "sales", "+31612340002", "Verkoopadviseur", [(64, 2)]),
          ("Kees Visser", "service", "+31612340003", "Serviceadviseur", [(79, 1)]), ("Lotte Jansen", "parts", "+31612340004", "Onderdelenadviseur", [])]
EVAL = {"sales": ([("Vroeg om een afspraak", True), ("Vroeg naar een inruilauto", False), ("Vroeg het telefoonnummer van de klant", False)],
                  "Sanne nam warm op en noemde de Golf meteen, maar vroeg niet naar een inruilauto en legde geen concrete tijd vast.", ["Bied twee tijden aan voordat de klant erom vraagt.", "Vraag elk gesprek naar de inruil."], ["Warme opening met eigen naam en bedrijfsnaam."]),
        "service": ([("Achterhaalde de klacht of de gewenste service", True), ("Bood de eerste beschikbare afspraak aan", True), ("Noemde vervoersopties (haal- en brengservice, leenauto of wachtruimte)", False)],
                    "Kees plande snel, maar noemde geen leenauto of haal- en brengservice.", ["Neem het 'hoe kom ik thuis' bezwaar weg voordat het komt."], ["Duidelijke bevestiging van dag en tijd."])}


async def main(wipe: bool):
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    old = await db.shop_clients.find_one({"name": NAME})
    if old:
        cid = str(old["_id"])
        await db.roleplay_sessions.delete_many({"client_id": cid})
        await db.call_evaluations.delete_many({TAG: True})
        await db.shop_targets.delete_many({"client_id": cid})
        await db.shop_proposals.delete_many({"client_id": cid})
        await db.shop_clients.delete_one({"_id": old["_id"]})
    if wipe:
        print("wiped")
        return
    now = datetime.now(timezone.utc)
    if now.day < 4:
        now = now.replace(day=5)
    admin = await db.users.find_one({"email": "forest@imosapp.com"})
    platform = os.environ.get("MYSTERY_SHOP_FROM_NUMBER") or os.environ.get("TWILIO_PHONE_NUMBER") or ""
    doc = {"name": NAME, "brand": "Volkswagen, Skoda", "city": "Utrecht", "state": "", "timezone": "Europe/Amsterdam", "locale": "nl-NL", "vat_id": "NL123456789B01", "industry": "automotive",
           "contact_name": "Pieter Jansen", "contact_title": "Directeur", "contact_email": "pieter@invalid.imonsocial.test", "contact_phone": "+31612345678",
           "plan": {"per_month": {"sales": 4, "service": 2, "parts": 1}, "price_monthly": 450.0}, "hours": {"start": "09:00", "end": "18:00", "days": [0, 1, 2, 3, 4, 5]},
           "vehicles": ["2024 Volkswagen Golf 1.5 eTSI Style", "2022 Skoda Octavia Combi 1.0 TSI", "2023 Volkswagen ID.4 Pro"], "active": True, "record_calls": True, "text_scorecards": True,
           "notes": "Dutch QA client, safe to edit. Never tap Buy local number (real Twilio purchase).", "from_number": platform, "report_token": uuid.uuid4().hex, "kickoff_token": uuid.uuid4().hex, "billing": {},
           "created_by": str(admin["_id"]) if admin else None, "created_at": now, "updated_at": now, TAG: True}
    res = await db.shop_clients.insert_one(doc)
    cid = str(res.inserted_id)
    for name, dept, phone, title, shops in PEOPLE:
        t = await db.shop_targets.insert_one({"client_id": cid, "name": name, "phone": phone, "department": dept, "title": title, "notes": "", "active": True, "challenge_history": [], "created_at": now, "updated_at": now, TAG: True})
        results, summary, coaching, wins = EVAL.get(dept, EVAL["sales"])
        for score, days_ago in shops:
            when = now.replace(hour=14, minute=30, second=0, microsecond=0) - timedelta(days=days_ago)
            ev = await db.call_evaluations.insert_one({"call_sid": f"RP_{TAG}_{ObjectId()}", "is_mystery_shop": True, "department": "Verkoop" if dept == "sales" else "Werkplaats", "scorecard_name": "Inkomend verkoopgesprek" if dept == "sales" else "Werkplaatsafspraak-gesprek", "score_pct": score,
                                                        "critical_misses": [] if score >= 70 else ["Vroeg niet om een afspraak"], "results": [{"criterion_id": f"c{i}", "text": tx, "critical": i == 0, "passed": ok if score >= 70 else (i == 0 and False) or ok} for i, (tx, ok) in enumerate(results)],
                                                        "summary": summary.replace("Sanne", name.split(" ")[0]).replace("Kees", name.split(" ")[0]), "coaching": coaching, "wins": wins, "customer_sentiment": "neutraal", "created_at": when, TAG: True})
            await db.roleplay_sessions.insert_one({"kind": "mystery_shop", "mode": "phone", "client_id": cid, "target_id": str(t.inserted_id), "rep_name": name, "rep_phone": phone, "department": dept, "industry": "automotive", "locale": "nl-NL", "status": "completed",
                                                   "scheduled_for": when, "started_at": when, "ended_at": when + timedelta(minutes=4), "score_pct": score, "adherence_pct": score, "evaluation_id": str(ev.inserted_id), "score_token": uuid.uuid4().hex,
                                                   "script_title": "Verkoopbeller: is de Golf er nog?" if dept == "sales" else "Servicebeller: APK en een piepend geluid", "persona": {"name": "Anouk van Dijk", "voice": "female"}, "store_name": NAME,
                                                   "turns": [{"role": "customer", "text": "Goedemiddag, ik bel over de Golf die online staat, is die er nog?"}, {"role": "rep", "text": f"Goedemiddag, {name.split(' ')[0]} van Autobedrijf Jansen. Ja, die staat er nog, wilt u hem komen bekijken?"}],
                                                   "transcript": f"CUSTOMER: Goedemiddag, ik bel over de Golf die online staat, is die er nog?\nREP: Goedemiddag, {name.split(' ')[0]} van Autobedrijf Jansen. Ja, die staat er nog.",
                                                   "created_at": when, "updated_at": when, TAG: True})
    await db.shop_proposals.insert_one({"client_id": cid, "client_name": NAME, "contact_name": "Pieter Jansen", "contact_email": "pieter@invalid.imonsocial.test", "locale": "nl-NL",
                                        "terms": {"per_month": {"sales": 4, "service": 2, "parts": 1}, "sales_per_month": 4, "service_per_month": 2, "price_monthly": 450.0, "term_months": 6, "notes": ""},
                                        "status": "draft", "token": uuid.uuid4().hex, "sender_id": str(admin["_id"]) if admin else None, "sender_name": "Forest", "created_at": now, "updated_at": now, TAG: True})
    c = await db.shop_clients.find_one({"_id": res.inserted_id})
    p = await db.shop_proposals.find_one({"client_id": cid})
    print(f"seeded {NAME} id={cid}\n  report   /shop-report/{c['report_token']}\n  kickoff  /shop-kickoff/{c['kickoff_token']}\n  proposal /proposal/{p['token']}")
    s = await db.roleplay_sessions.find_one({"client_id": cid, "status": "completed"})
    print(f"  score    /shop-score/{s['score_token']}")


if __name__ == "__main__":
    asyncio.run(main("--wipe" in sys.argv))
