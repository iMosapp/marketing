"""T1 iteration 406: texting + campaign smoke with the same-org demo accounts (fresh org, no store restrictions). Self-cleaning."""
import json
import os

import requests
from bson import ObjectId
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
S = json.load(open("/tmp/iso_state.json"))
made, camps = [], []
try:
    for who in ("A", "M"):
        h = {"Authorization": f"Bearer {S['tok'][who]}"}
        u = S["uid"][who]
        c = requests.post(f"{BASE}/contacts/{u}", json={"first_name": "TEST_T1", "last_name": f"Text{who}", "phone": "+1500555018" + ("1" if who == "A" else "2")}, headers=h).json()
        cid = c.get("_id") or c.get("id"); made.append(cid)
        conv = requests.post(f"{BASE}/messages/conversations/{u}", json={"contact_id": cid}, headers=h).json()
        conv = conv.get("_id") or conv.get("id")
        print(who, "consent", requests.post(f"{BASE}/consent/contact/{cid}", json={"scopes": ["requested_info", "transactional"]}, headers=h).status_code)
        r = requests.post(f"{BASE}/messages/send/{u}/{conv}", json={"conversation_id": conv, "content": "T1 smoke", "channel": "sms"}, headers=h, timeout=60)
        print(who, "send", r.status_code, r.text[:200])
        r = requests.post(f"{BASE}/campaigns/{u}", json={"name": "TEST_T1 Camp", "active": False, "sequences": [{"step": 1, "delay_days": 1, "message_template": "Hi", "channel": "sms"}]}, headers=h)
        print(who, "campaign create", r.status_code, r.text[:150])
        if r.status_code == 200:
            camp = r.json().get("_id") or r.json().get("id"); camps.append((u, camp, h))
            e = requests.post(f"{BASE}/campaigns/{u}/{camp}/enroll/{cid}", headers=h)
            print(who, "enroll own", e.status_code, e.text[:120])
            if who == "M":
                e = requests.post(f"{BASE}/campaigns/{u}/{camp}/enroll/{S['ca']}", headers=h)
                print("M enroll rep A's Walt (manager scope)", e.status_code, e.text[:120])
    h2 = {"Authorization": f"Bearer {S['tok']['A2']}"}
    r = requests.post(f"{BASE}/campaigns/{S['uid']['A2']}", json={"name": "TEST_T1 Camp", "active": False}, headers=h2)
    if r.status_code == 200:
        camp = r.json().get("_id") or r.json().get("id"); camps.append((S["uid"]["A2"], camp, h2))
        e = requests.post(f"{BASE}/campaigns/{S['uid']['A2']}/{camp}/enroll/{S['ca']}", headers=h2)
        print("A2 enroll A's Walt", e.status_code, e.text[:120])
finally:
    for u, camp, h in camps:
        requests.delete(f"{BASE}/campaigns/{u}/{camp}", headers=h)
    for coll in ("conversations", "messages", "contact_events", "campaign_enrollments", "consent_records", "consent_state"):
        db[coll].delete_many({"contact_id": {"$in": made + [S["ca"]]}, "campaign_id": {"$in": [c for _, c, _ in camps]}} if coll == "campaign_enrollments" else {"contact_id": {"$in": made}})
    db.contacts.delete_many({"_id": {"$in": [ObjectId(c) for c in made if c]}})
    print("cleaned")
