"""Cleanup of iteration 289 test data: test contacts, tags, broadcast drafts."""
import requests
from dotenv import dotenv_values

BASE = dotenv_values("/app/frontend/.env")["REACT_APP_BACKEND_URL"].rstrip("/")
UID = "69a0b7095fddcede09591667"
s = requests.Session()
r = s.post(f"{BASE}/api/auth/login", json={"email": "forest@imosapp.com", "password": "Admin123!"}, timeout=30)
tok = r.json().get("token") or r.json().get("access_token")
if tok:
    s.headers.update({"Authorization": f"Bearer {tok}"})

# broadcasts
r = s.get(f"{BASE}/api/broadcast", params={"user_id": UID}, timeout=30)
for b in r.json().get("broadcasts", []):
    if b["name"].startswith("TEST_289"):
        d = s.delete(f"{BASE}/api/broadcast/{b['id']}", params={"user_id": UID}, timeout=30)
        print("del broadcast", b["name"], d.status_code)

# contacts
for term in ("TESTUI", "TESTCSV"):
    r = s.get(f"{BASE}/api/contacts/{UID}", params={"search": term, "limit": 50}, timeout=30)
    body = r.json()
    items = body.get("contacts", []) if isinstance(body, dict) else body
    for c in [x for x in items if isinstance(x, dict)]:
        if str(c.get("first_name", "")).startswith(term):
            cid = c.get("id") or c.get("_id")
            d = s.delete(f"{BASE}/api/contacts/{UID}/{cid}", timeout=30)
            print("del contact", c.get("first_name"), d.status_code)

# tags
r = s.get(f"{BASE}/api/tags/{UID}", timeout=30)
body = r.json()
tags = body.get("tags", []) if isinstance(body, dict) else body
for t in tags:
    if str(t.get("name", "")).startswith("TEST_LIST_289") or str(t.get("name", "")).startswith("TEST_UI_LIST_289"):
        tid = t.get("_id") or t.get("id")
        d = s.delete(f"{BASE}/api/tags/{UID}/{tid}", timeout=30)
        print("del tag", t.get("name"), d.status_code)

# verify
r = s.get(f"{BASE}/api/tags/{UID}", timeout=30)
body = r.json()
tags = body.get("tags", []) if isinstance(body, dict) else body
print("remaining TEST tags:", [t.get("name") for t in tags if "TEST_" in str(t.get("name"))])
p = s.get(f"{BASE}/api/broadcast/preview", params={"user_id": UID}, timeout=30)
print("total contacts now:", p.json()["count"])
