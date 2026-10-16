"""T1 iteration 406: targeted write / body-id probes on the seeded same-org demo (/tmp/iso_state.json). Restores anything it changes."""
import json
import os

import requests
from bson import ObjectId
from pymongo import MongoClient

BASE = open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split()[0].rstrip("/")
S = json.load(open("/tmp/iso_state.json"))
db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
A, A2, M, W = S["uid"]["A"], S["uid"]["A2"], S["uid"]["M"], S["ca"]


def call(method, path, tok, **kw):
    r = requests.request(method, BASE + "/api" + path, headers={"Authorization": f"Bearer {tok}"}, timeout=90, **kw)
    return r.status_code, r.text


def leaked(t):
    return "Harley" in t or "NADA" in t


def owner():
    return db.contacts.find_one({"_id": ObjectId(W)}, {"user_id": 1})["user_id"]


qm = requests.post(BASE + "/api/auth/login", json={"email": "qa-manager@invalid.imonsocial.test", "password": "Manager123!"}, timeout=30).json()
QM_TOK, QM = qm["token"], qm["user"]["_id"] if "_id" in qm["user"] else qm["user"].get("id")
a2 = S["tok"]["A2"]

# 1. cross-org manager reassigns Walt (ownership_type org) to themselves via /engagement/reassign-lead
st, body = call("POST", "/engagement/reassign-lead", QM_TOK, json={"contact_id": W, "new_user_id": QM})
print("1 cross-org reassign-lead:", st, body[:160], "| owner now:", owner())
if owner() != A:
    st2, b2 = call("GET", f"/contacts/{QM}/{W}", QM_TOK)
    print("  cross-org manager reads Walt after reassign:", st2, "LEAK" if leaked(b2) else "no leak")
    db.contacts.update_one({"_id": ObjectId(W)}, {"$set": {"user_id": A}})
    db.contact_events.delete_many({"contact_id": W, "event_type": "lead_reassigned"})
    print("  restored owner ->", owner())

# 2. rep A2 tries reassign-lead (must be 403)
st, body = call("POST", "/engagement/reassign-lead", a2, json={"contact_id": W, "new_user_id": A2})
print("2 A2 reassign-lead:", st, "| owner:", owner() == A)

# 3. A2 merge Walt into an own contact
mine = str(db.contacts.insert_one({"user_id": A2, "store_id": S["store"], "first_name": "T1Probe", "last_name": "Mine", "qa_same_org_iso": True}).inserted_id)
st, body = call("POST", f"/contacts/{A2}/merge", a2, json={"primary_id": mine, "duplicate_id": W})
print("3 A2 merge walt into own:", st, body[:120], "| walt merged_into:", db.contacts.find_one({"_id": ObjectId(W)}).get("merged_into"))
st, body = call("POST", f"/messages/merge-duplicates/{A2}", a2, json={"primary_id": mine, "duplicate_id": W, "contact_ids": [mine, W]})
print("3b merge-duplicates:", st, body[:120])

# 4. A2 attaches A's memo to own contact / patches it via voice-memos
st, body = call("POST", f"/voice-memos/{A2}/{S['memo']}/attach", a2, json={"contact_id": mine})
print("4 voice-memos attach A memo:", st, "LEAK" if leaked(body) else "", body[:120], "| memo contact:", db.voice_notes.find_one({"_id": ObjectId(S["memo"])})["contact_id"] == W)
st, body = call("PATCH", f"/voice-memos/{A2}/{S['memo']}", a2, json={"title": "pwned"})
print("4b voice-memos patch A memo:", st, body[:120])

# 5. tasks: A2 creates a task on Walt / edits A's task
task = db.tasks.find_one({"contact_id": W})
st, body = call("POST", f"/tasks/{A2}", a2, json={"title": "T1 probe", "contact_id": W, "type": "follow_up"})
print("5 A2 create task on Walt:", st, "LEAK" if leaked(body) else "", body[:150])
st, body = call("PATCH", f"/tasks/{A2}/{task['_id']}", a2, json={"title": "pwned"})
print("5b A2 patch A task:", st, "LEAK" if leaked(body) else "", body[:120])
db.tasks.delete_many({"title": "T1 probe"})

# 6. contact file upload onto Walt
st, body = call("POST", f"/contact-files/{A2}/chunk", a2, json={"contact_id": W, "upload_id": "t1probe", "chunk_index": 0, "total_chunks": 1, "data": "aGVsbG8=", "filename": "x.txt", "mime_type": "text/plain"})
print("6 A2 upload file onto Walt:", st, body[:150])

# 7. Jessi extract-profile / voice chat with walt
st, body = call("POST", "/jessie/extract-profile", a2, json={"user_id": A2, "contact_id": W, "transcript": "tell me about him"})
print("7 jessie extract-profile:", st, "LEAK" if leaked(body) else "no leak", body[:100])

# 8. A2 using A's user id in path
for p in (f"/contacts/{A}/{W}", f"/voice-notes/{A}/{W}", f"/contact-intel/{A}/{W}", f"/contacts/{A}?search=Walt"):
    st, body = call("GET", p, a2)
    print("8 A-path as A2", p.replace(W, "{W}").replace(A, "{A}"), st, "LEAK" if leaked(body) else "")

# 9. create conversation for A2 with Walt (opens a texting channel to A's customer?)
st, body = call("POST", f"/messages/conversations/{A2}", a2, json={"contact_id": W})
print("9 A2 create conversation with Walt:", st, "LEAK" if leaked(body) else "", body[:150])

# 10. contact-intel generate + contact-ask ask
st, body = call("POST", f"/contact-intel/{A2}/{W}", a2, json={})
print("10 contact-intel generate:", st, "LEAK" if leaked(body) else "")
st, body = call("POST", f"/contact-ask/{W}/ask", a2, json={"question": "hobbies and where we met?"})
print("10b contact-ask ask:", st, "LEAK" if leaked(body) else "")

db.contacts.delete_one({"_id": ObjectId(mine)})
w = db.contacts.find_one({"_id": ObjectId(W)})
print("FINAL walt owner==A:", w["user_id"] == A, "merged_into:", w.get("merged_into"), "notes intact:", "Harley" in (w.get("notes") or ""))
