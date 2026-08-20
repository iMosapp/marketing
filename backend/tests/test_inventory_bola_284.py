"""BOLA scoping check for inventory update/delete (iteration 284)."""
import os
import requests
from dotenv import dotenv_values

BASE = (os.environ.get("REACT_APP_BACKEND_URL") or dotenv_values("/app/frontend/.env")["REACT_APP_BACKEND_URL"]).rstrip("/")
API = f"{BASE}/api"


def login(e, p):
    r = requests.post(f"{API}/auth/login", json={"email": e, "password": p}, timeout=30)
    d = r.json()
    return (d["user"].get("_id") or d["user"].get("id")), d.get("token") or d.get("access_token")


def H(t, u):
    return {"Authorization": f"Bearer {t}", "X-User-ID": u}


def test_cross_user_update_delete_scoping():
    admin_id, admin_tok = login("forest@imosapp.com", "Admin123!")
    other_id, other_tok = login("mjeast1985@gmail.com", "NavyBean1!")
    r = requests.post(f"{API}/inventory/{admin_id}", json={"year": "2000", "make": "TESTBOLA", "model": "X"},
                      headers=H(admin_tok, admin_id), timeout=30)
    item_id = r.json()["item"]["_id"]
    try:
        u = requests.put(f"{API}/inventory/{other_id}/{item_id}", json={"status": "sold"},
                         headers=H(other_tok, other_id), timeout=30)
        d = requests.delete(f"{API}/inventory/{other_id}/{item_id}", headers=H(other_tok, other_id), timeout=30)
        print("cross-user PUT:", u.status_code, u.text[:120])
        print("cross-user DELETE:", d.status_code, d.text[:120])
        assert u.status_code in (403, 404), f"BOLA: other user could update item ({u.status_code})"
        assert d.status_code in (403, 404), f"BOLA: other user could delete item ({d.status_code})"
    finally:
        requests.delete(f"{API}/inventory/{admin_id}/{item_id}", headers=H(admin_tok, admin_id), timeout=30)
