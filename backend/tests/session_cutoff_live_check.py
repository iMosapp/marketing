"""Live SESSIONS_VALID_AFTER check, usable in preview (around a backend restart) and in production (around the Deploy).

  python tests/session_cutoff_live_check.py save  /tmp/session_before.json   # BEFORE: log in, keep the token
  python tests/session_cutoff_live_check.py check /tmp/session_before.json   # AFTER: old token 401 on /auth/me + /auth/refresh, fresh login 200

Base URL: SESSION_CHECK_BASE (default REACT_APP_BACKEND_URL). Login: SESSION_CHECK_EMAIL (+ SESSION_CHECK_PASSWORD, or the
preview QA file via tests/qa_creds.py). Nothing is printed but status codes; no token or password ever leaves this process."""
import json
import os
import sys

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import qa_creds  # noqa: E402

BASE = (os.environ.get("SESSION_CHECK_BASE") or os.environ.get("REACT_APP_BACKEND_URL") or "").rstrip("/")
EMAIL = os.environ.get("SESSION_CHECK_EMAIL") or "forest@imosapp.com"


def _login():
    pw = os.environ.get("SESSION_CHECK_PASSWORD") or qa_creds.password_for(EMAIL)
    r = requests.post(f"{BASE}/api/auth/login", json={"email": EMAIL, "password": pw}, timeout=30)
    return r.status_code, (r.json().get("token") if r.status_code == 200 else None)


def _me(token):
    return requests.get(f"{BASE}/api/auth/me", headers={"Authorization": f"Bearer {token}"}, timeout=30).status_code


def _me_cookie(token):
    return requests.get(f"{BASE}/api/auth/me", cookies={"imonsocial_session": token}, timeout=30).status_code


def _refresh(token):
    return requests.post(f"{BASE}/api/auth/refresh", headers={"Authorization": f"Bearer {token}"}, json={}, timeout=30).status_code


def save(path):
    code, token = _login()
    assert code == 200 and token, f"login failed: {code}"
    assert _me(token) == 200, "token issued but /auth/me refused it"
    with open(path, "w") as fh:
        json.dump({"token": token, "base": BASE, "email": EMAIL}, fh)
    os.chmod(path, 0o600)
    print(f"saved: login 200, /auth/me 200 (token kept in {path}, mode 600)")


def check(path):
    with open(path) as fh:
        before = json.load(fh)
    old = before["token"]
    me_old, cookie_old, refresh_old = _me(old), _me_cookie(old), _refresh(old)
    code, fresh = _login()
    me_new = _me(fresh) if fresh else None
    cookie_new = _me_cookie(fresh) if fresh else None
    refresh_new = _refresh(fresh) if fresh else None
    ok = me_old == 401 and cookie_old == 401 and refresh_old == 401 and code == 200 and me_new == 200 and cookie_new == 200 and refresh_new == 200
    print(f"old token: /auth/me bearer {me_old} (want 401), /auth/me cookie {cookie_old} (want 401), /auth/refresh {refresh_old} (want 401)")
    print(f"fresh login: {code} (want 200), /auth/me bearer {me_new} (want 200), /auth/me cookie {cookie_new} (want 200), /auth/refresh {refresh_new} (want 200)")
    print("RESULT:", "PASS" if ok else "FAIL")
    try:
        os.remove(path)
    except OSError:
        pass
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in ("save", "check") or not BASE:
        print(__doc__)
        sys.exit(2)
    (save if sys.argv[1] == "save" else check)(sys.argv[2])
