"""Tiny shared HTTP helper for ad-hoc preview checks (browser UA so Cloudflare lets python through)."""
import json
import os
import urllib.error
import urllib.request

API = os.environ.get("REACT_APP_BACKEND_URL") or open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split()[0]
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}


def call(method, path, body=None, headers=None, raw=False):
    req = urllib.request.Request(API + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json", **UA, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            data = r.read().decode()
            return r.status, (data if raw else json.loads(data or "null"))
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:200]


def login(email, pw):
    st, b = call("POST", "/api/auth/login", {"email": email, "password": pw})
    assert st == 200, (st, b)
    return b["token"], b["user"]["_id"]


def auth(tok, uid):
    return {"Authorization": "Bearer " + tok, "X-User-ID": uid}
