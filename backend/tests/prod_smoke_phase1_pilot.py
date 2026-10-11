"""Production smoke (anonymous, read-only). python tests/prod_smoke_phase1_pilot.py [expected_build]"""
import json
import sys
import urllib.error
import urllib.request

BASE = "https://app.imonsocial.com"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
EXPECTED_BUILD = sys.argv[1] if len(sys.argv) > 1 else "2026-10-11.phase1-pilot"


def hit(method, path, body=None):
    req = urllib.request.Request(BASE + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json", **UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode()[:200]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:200]
    except Exception as e:
        return 0, str(e)[:200]


CHECKS = [
    ("GET", "/api/health", None, (200,), f'"build": "{EXPECTED_BUILD}"'),
    ("GET", "/api/customers/plans", None, (401,), None),
    ("GET", "/api/customers", None, (401,), None),
    ("GET", "/api/billing/me", None, (401,), None),
    ("POST", "/api/billing/checkout", {}, (401,), None),
    ("GET", "/api/pilot/checklist", None, (401,), None),
    ("POST", "/api/cron/pilot-reminders", {}, (401,), None),
    ("POST", "/api/cron/leadership-morning-brief", {}, (401,), None),
    ("POST", "/api/billing/stripe/webhook", {}, (400, 503), None),
    ("POST", "/api/billing/checkout/confirm", {"session_id": "cs_test_nope"}, (400, 404, 502, 503), None),  # 502 = the app's own mapping of a Stripe "no such session" error (same in preview)
    ("POST", "/api/customers/000000000000000000000000/pilot/end", {"reason": "anon probe"}, (401,), None),
    ("POST", "/api/auth/login", {"email": "nobody@invalid.imonsocial.test", "password": "x"}, (401,), None),
    ("GET", "/api/subscriptions/plans", None, (200,), None),
    ("GET", "/", None, (200,), None),
]

ok_all = True
for method, path, body, expect, must_contain in CHECKS:
    st, txt = hit(method, path, body)
    ok = st in expect and (must_contain is None or must_contain in txt)
    ok_all &= ok
    print(f"{'PASS' if ok else 'FAIL'} {method} {path} -> {st} (expected {expect}){' · ' + txt[:90] if (not ok or path == '/api/health') else ''}")
print("\nALL PASS" if ok_all else "\nFAILURES PRESENT")
sys.exit(0 if ok_all else 1)
