"""Sold Units = purchase records. Replays the Bridger Ward story end to end against the running API + DB.
Run: cd /app/backend && python tests/sales_units_test.py
"""
import asyncio
import os
import sys
from datetime import datetime

import requests
from bson import ObjectId
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")
API = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
sys.path.insert(0, "/app/backend")
from services import sales  # noqa: E402


def login():
    r = requests.post(f"{API}/api/auth/login", json={"email": "forest@imosapp.com", "password": "Admin123!"}, timeout=30).json()
    return r.get("token") or r.get("access_token"), r["user"]["_id"] if "user" in r else r.get("user_id")


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    token, uid = login()
    H = {"Authorization": f"Bearer {token}"}
    if not uid:
        uid = str((await db.users.find_one({"email": "forest@imosapp.com"}, {"_id": 1}))["_id"])
    await db.contacts.delete_many({"user_id": uid, "last_name": "QA-Units"})

    # ---- 1. new customer, Sold wizard in July: one call = date + vehicle
    c = requests.post(f"{API}/api/contacts/{uid}/find-or-create-and-log", headers=H, json={"name": "Bridger QA-Units", "phone": "+15005550701", "event_type": "congrats_card_sent", "event_title": "Sold"}, timeout=30).json()
    cid = c["contact_id"]
    r = requests.patch(f"{API}/api/contacts/{uid}/{cid}/date-sold", headers=H, json={"date": "2026-07-13", "title": "2022 Road Glide", "category": "vehicle"}, timeout=30).json()
    assert r["sale"] == "first" and r["sold_count"] == 1 and r["date_sold"] == "2026-07-13", r
    doc = await db.contacts.find_one({"_id": ObjectId(cid)})
    assert doc["date_sold"] == datetime(2026, 7, 13) and doc["vehicle"] == "2022 Road Glide" and len(doc["purchase_history"]) == 1
    print("july sale -> 1 record, date_sold Jul 13 ok")

    # ---- 2. second vehicle in September: NEW record, July stays
    r = requests.patch(f"{API}/api/contacts/{uid}/{cid}/date-sold", headers=H, json={"date": "2026-09-01", "title": "2022 Toyota Supra", "category": "vehicle"}, timeout=30).json()
    assert r["sale"] == "repeat" and r["sold_count"] == 2, r
    p = requests.get(f"{API}/api/contacts/{uid}/{cid}/purchases", headers=H, timeout=30).json()["purchases"]
    assert [(x["title"], x["date"]) for x in p] == [("2022 Toyota Supra", "2026-09-01"), ("2022 Road Glide", "2026-07-13")], p
    doc = await db.contacts.find_one({"_id": ObjectId(cid)})
    assert doc["date_sold"] == datetime(2026, 9, 1) and doc["vehicle"] == "2022 Toyota Supra" and doc["sold_count"] == 2
    print("september sale -> 2 records, july kept, date_sold Sep 1 ok")

    # ---- 3. Sold Units counts UNITS: Bridger in July AND September, dates as calendar days
    jul = requests.get(f"{API}/api/users/{uid}/sold-contacts", headers=H, params={"month": 7, "year": 2026}, timeout=30).json()["contacts"]
    sep = requests.get(f"{API}/api/users/{uid}/sold-contacts", headers=H, params={"month": 9, "year": 2026}, timeout=30).json()["contacts"]
    j = [x for x in jul if x["_id"] == cid]
    s = [x for x in sep if x["_id"] == cid]
    assert len(j) == 1 and j[0]["vehicle"] == "2022 Road Glide" and j[0]["date_sold"] == "2026-07-13" and j[0]["sold_count"] == 2, j
    assert len(s) == 1 and s[0]["vehicle"] == "2022 Toyota Supra" and s[0]["date_sold"] == "2026-09-01", s
    summ = requests.get(f"{API}/api/users/{uid}/sold-monthly-summary", headers=H, params={"month": 9, "year": 2026}, timeout=30).json()
    by = {(m["year"], m["month"]): m["total"] for m in summ["months"]}
    perf = requests.get(f"{API}/api/users/{uid}/sold-performance", headers=H, params={"month": 9, "year": 2026}, timeout=30).json()
    assert perf["current_month"]["total"] == by[(2026, 9)] and perf["current_month"]["repeats"] >= 1, (perf["current_month"], by[(2026, 9)])
    reps = requests.get(f"{API}/api/users/{uid}/sold-contacts", headers=H, params={"month": 9, "year": 2026, "filter_type": "repeats"}, timeout=30).json()["contacts"]
    assert any(x["_id"] == cid for x in reps)
    print(f"sold units: Jul={by[(2026, 7)]} Sep={by[(2026, 9)]}, Bridger in both, repeats filter ok")

    # ---- 4. wizard re-run for the same vehicle two days later = correction, not a third purchase
    r = requests.patch(f"{API}/api/contacts/{uid}/{cid}/date-sold", headers=H, json={"date": "2026-09-03", "title": "2022 Toyota Supra"}, timeout=30).json()
    assert r["sale"] == "same" and r["sold_count"] == 2, r
    # ---- 5. the OLD app build still sends date-only, then the purchase separately: still one record
    r1 = requests.patch(f"{API}/api/contacts/{uid}/{cid}/date-sold", headers=H, json={"date": "2026-09-20"}, timeout=30).json()
    r2 = requests.post(f"{API}/api/contacts/{uid}/{cid}/purchases", headers=H, json={"title": "2026 Pan America", "category": "vehicle", "date": "2026-09-20", "notes": ""}, timeout=30).json()
    p = requests.get(f"{API}/api/contacts/{uid}/{cid}/purchases", headers=H, timeout=30).json()["purchases"]
    assert r1["sale"] == "repeat" and [(x["title"], x["date"]) for x in p] == [("2026 Pan America", "2026-09-20"), ("2022 Toyota Supra", "2026-09-03"), ("2022 Road Glide", "2026-07-13")], p
    print("correction within 7 days + old two-call flow -> no duplicates ok")

    # ---- 6. edit / delete a record re-derives the contact
    pan = p[0]
    assert requests.put(f"{API}/api/contacts/{uid}/{cid}/purchases/{pan['id']}", headers=H, json={"date": "2026-10-02"}, timeout=30).json()["success"]
    doc = await db.contacts.find_one({"_id": ObjectId(cid)})
    assert doc["date_sold"] == datetime(2026, 10, 2) and doc["vehicle"] == "2026 Pan America"
    assert requests.delete(f"{API}/api/contacts/{uid}/{cid}/purchases/{pan['id']}", headers=H, timeout=30).json()["success"]
    doc = await db.contacts.find_one({"_id": ObjectId(cid)})
    assert doc["date_sold"] == datetime(2026, 9, 3) and doc["vehicle"] == "2022 Toyota Supra" and doc["sold_count"] == 2, (doc["date_sold"], doc["vehicle"], doc["sold_count"])
    print("edit date -> date_sold follows; delete -> falls back to the previous purchase ok")

    # ---- 7. Date Sold edited on the contact form edits the latest record (and a 2 AM UTC save does not move the day)
    full = requests.get(f"{API}/api/contacts/{uid}/{cid}", headers=H, timeout=30).json()
    body = {k: full.get(k) for k in ("first_name", "last_name", "phone", "email", "notes", "tags", "vehicle")}
    body["date_sold"] = "2026-09-05"
    assert requests.put(f"{API}/api/contacts/{uid}/{cid}", headers=H, json=body, timeout=30).status_code == 200
    p = requests.get(f"{API}/api/contacts/{uid}/{cid}/purchases", headers=H, timeout=30).json()["purchases"]
    doc = await db.contacts.find_one({"_id": ObjectId(cid)})
    assert p[0]["date"] == "2026-09-05" and p[0]["title"] == "2022 Toyota Supra" and len(p) == 2 and doc["date_sold"] == datetime(2026, 9, 5), (p, doc["date_sold"])
    body["date_sold"] = "2026-09-06T02:00:00.000Z"  # an old build sending a UTC instant: the day it names is what we keep
    requests.put(f"{API}/api/contacts/{uid}/{cid}", headers=H, json=body, timeout=30)
    doc = await db.contacts.find_one({"_id": ObjectId(cid)})
    assert doc["date_sold"] == datetime(2026, 9, 6), doc["date_sold"]
    print("contact form Date Sold -> edits latest record, calendar day preserved ok")

    # ---- 8. repair: a production-shaped mess (wizard row + blank 'repeat' archive + date_sold only for the latest)
    legacy = {"user_id": uid, "first_name": "Legacy", "last_name": "QA-Units", "phone": "+15005550702", "status": "active", "vehicle": "2022 Toyota Supra", "date_sold": datetime(2026, 9, 1), "sold_count": 4, "prev_vehicle": "2022 Road Glide",
              "purchase_history": [{"id": "a1", "title": "2022 Road Glide", "category": "vehicle", "date": "2026-07-13", "notes": "", "created_at": "2026-07-13T20:00:00+00:00"},
                                   {"date": "2026-07-13T00:00:00", "vehicle": "2022 Road Glide", "notes": "Previous purchase", "is_repeat": True}]}
    lid = (await db.contacts.insert_one(legacy)).inserted_id
    await db.contacts.insert_one({"user_id": uid, "first_name": "OnlyDateSold", "last_name": "QA-Units", "phone": "+15005550703", "status": "active", "vehicle": "2026 Pan America", "date_sold": datetime(2026, 9, 5)})
    r = await sales.repair_all(db)
    doc = await db.contacts.find_one({"_id": lid})
    got = [(e["title"], e["date"]) for e in doc["purchase_history"]]
    assert got == [("2022 Toyota Supra", "2026-09-01"), ("2022 Road Glide", "2026-07-13")] and doc["sold_count"] == 2 and "prev_vehicle" not in doc, (got, doc["sold_count"])
    only = await db.contacts.find_one({"phone": "+15005550703", "last_name": "QA-Units"})
    assert [(e["title"], e["date"]) for e in only["purchase_history"]] == [("2026 Pan America", "2026-09-05")] and only["sold_count"] == 1
    sep = requests.get(f"{API}/api/users/{uid}/sold-contacts", headers=H, params={"month": 9, "year": 2026}, timeout=30).json()["contacts"]
    assert sum(1 for x in sep if x["name"].endswith("QA-Units")) == 3, [(x["name"], x["vehicle"], x["date_sold"]) for x in sep if "QA" in x["name"]]
    print(f"repair merged the blank archive, wrote the missing Supra + legacy records, counts fixed ({r}) ok")

    await db.contacts.delete_many({"user_id": uid, "last_name": "QA-Units"})
    print("ALL OK")


asyncio.run(main())
