"""Restore the Website lead source workflow to its pre-test intake_text wording."""
import requests
from dotenv import dotenv_values

fe = dotenv_values("/app/frontend/.env")
BASE = fe["REACT_APP_BACKEND_URL"].rstrip("/")
s = requests.Session()
r = s.post(f"{BASE}/api/auth/login", json={"email": "forest@imosapp.com", "password": "Admin123!"}, timeout=30)
tok = r.json().get("token") or r.json().get("access_token")
s.headers.update({"Authorization": f"Bearer {tok}", "X-User-ID": "69a0b7095fddcede09591667"})
cfg = {
    "intake_text": "Hi {{first_name}}, thanks for booking a demo of I'm On Social! This is our team, what time works best today?",
    "workflow_user_ids": ["6a978d68b8673c29063aa8b9"],
    "contact_mode": "text_and_call",
    "call_attempts": [{"user_ids": ["6a978d68b8673c29063aa8b9"], "delay_seconds": 0},
                      {"user_ids": ["6a978d68b8673c29063aa8b9"], "delay_seconds": 60}],
    "website_default": True,
    "website_pages": ["pricing"],
    "va_enabled": False,
}
p = s.put(f"{BASE}/api/lead-sources/69a787ca70ae63ea0ac69251/workflow", json=cfg, timeout=30)
print(p.status_code, p.text[:200])
print(s.get(f"{BASE}/api/lead-sources/69a787ca70ae63ea0ac69251/workflow", timeout=30).json())
