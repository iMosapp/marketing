"""Helper for iteration 291 frontend tests: create pending users, read codes, cleanup."""
import sys
import uuid
import requests
from dotenv import dotenv_values
from pymongo import MongoClient
from bson import ObjectId

fe = dotenv_values("/app/frontend/.env")
be = dotenv_values("/app/backend/.env")
BASE = fe["REACT_APP_BACKEND_URL"].rstrip("/")
db = MongoClient(be["MONGO_URL"])[be["DB_NAME"]]


def admin():
    r = requests.post(f"{BASE}/api/auth/login", json={"email": "forest@imosapp.com", "password": "Admin123!"}, timeout=60)
    r.raise_for_status()
    d = r.json()
    t = d.get("token") or d.get("access_token")
    return {"Authorization": f"Bearer {t}", "X-User-ID": str(d["user"]["_id"])}


def create(phone, send_sms=True):
    email = f"test-291-{uuid.uuid4().hex[:6]}@invalid.imonsocial.test"
    r = requests.post(f"{BASE}/api/admin/users/create", headers=admin(), json={
        "first_name": "Zeta", "last_name": "Tester", "email": email,
        "phone": phone, "role": "user", "send_invite": False, "send_sms": send_sms,
    }, timeout=90)
    print(r.status_code)
    d = r.json()
    print("EMAIL:", email)
    print("ID:", d.get("user_id"))
    print("TEMP_PASSWORD:", d.get("temp_password"))
    print("ACTIVATION_FLOW:", d.get("activation_flow"), "URL:", d.get("activate_url"))
    return d


def code(phone_or_email, purpose="activate"):
    import re
    digits = re.sub(r"\D", "", phone_or_email)
    if "@" in phone_or_email:
        u = db.users.find_one({"email": phone_or_email.lower()})
    else:
        u = db.users.find_one({"phone": f"+1{digits[-10:]}"})
    doc = db.password_reset_tokens.find_one({"user_id": str(u["_id"]), "purpose": purpose}, sort=[("created_at", -1)])
    print("CODE:", doc["code"] if doc else None)
    return doc["code"] if doc else None


def cleanup():
    users = list(db.users.find({"email": {"$regex": "^test-291-"}}))
    h = admin()
    for u in users:
        r = requests.delete(f"{BASE}/api/admin/users/{u['_id']}/hard", headers=h, timeout=60)
        print("deleted", u["email"], r.status_code)
    n = db.contacts.delete_many({"email": {"$regex": "^test-291-"}}).deleted_count
    n2 = db.users.delete_many({"email": {"$regex": "^TEST-activate-"}}).deleted_count
    n3 = db.contacts.delete_many({"email": {"$regex": "^TEST-activate-"}}).deleted_count
    print("contacts removed:", n + n3, "leftover users removed:", n2)


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "create":
        create(sys.argv[2], send_sms=(sys.argv[3] == "1" if len(sys.argv) > 3 else True))
    elif cmd == "code":
        code(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "activate")
    elif cmd == "cleanup":
        cleanup()
