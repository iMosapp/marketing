"""Production smoke for build 2026-10-13.voice-pilot (anonymous, read-only). python tests/prod_smoke_voice_pilot.py [expected_build]"""
import json
import sys
import urllib.error
import urllib.request

BASE = "https://app.imonsocial.com"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
EXPECTED_BUILD = sys.argv[1] if len(sys.argv) > 1 else "2026-10-13.voice-pilot"


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
    # release identity
    ("GET", "/api/health", None, (200,), f'"build": "{EXPECTED_BUILD}"'),
    # voice controls are live but locked (404 before this release)
    ("GET", "/api/voice-controls/pilot", None, (401,), None),
    ("POST", "/api/voice-controls/pilot/enroll", {"premium_min": 2, "backup_min": 10, "hard_usd": 20}, (401,), None),
    ("POST", "/api/voice-controls/pilot/kill", {}, (401,), None),
    ("GET", "/api/voice-controls/me", None, (401,), None),
    ("GET", "/api/voice-controls/accounts", None, (401,), None),
    ("GET", "/api/voice-controls/global", None, (401,), None),
    ("GET", "/api/voice-controls/ledger", None, (401,), None),
    ("POST", "/api/voice-controls/watchdog", {}, (401,), None),
    # live Jessi unchanged for anonymous callers
    ("GET", "/api/live-voice/config", None, (401,), None),
    ("POST", "/api/live-voice/session", {"mode": "assistant", "sdp": "v=0", "overrides": {"fake_provider": True}}, (401,), None),
    # manager security fix: anonymous PATCH on a profile is refused (used to be unguarded)
    ("PATCH", "/api/users/000000000000000000000000", {"hub_pins": ["x"]}, (401, 403), None),
    # Phase 1 / billing surface still locked, pilot + Stripe paths answer as before
    ("GET", "/api/customers/plans", None, (401,), None),
    ("GET", "/api/customers", None, (401,), None),
    ("GET", "/api/billing/me", None, (401,), None),
    ("POST", "/api/billing/checkout", {}, (401,), None),
    ("GET", "/api/pilot/checklist", None, (401,), None),
    ("POST", "/api/cron/pilot-reminders", {}, (401,), None),
    ("POST", "/api/billing/stripe/webhook", {}, (400, 503), None),
    ("POST", "/api/billing/checkout/confirm", {"session_id": "cs_test_nope"}, (400, 404, 502, 503), None),
    ("POST", "/api/customers/000000000000000000000000/pilot/end", {"reason": "anon probe"}, (401,), None),
    ("POST", "/api/auth/login", {"email": "nobody@invalid.imonsocial.test", "password": "x"}, (401,), None),
    ("GET", "/api/subscriptions/plans", None, (200,), None),
    ("GET", "/", None, (200,), None),
    ("GET", "/admin/voice-pilot", None, (200,), None),  # web bundle serves the new route shell
]

if __name__ == "__main__":
    fails = 0
    for method, path, body, ok, must in CHECKS:
        st, text = hit(method, path, body)
        good = st in ok and (must is None or must in text)
        fails += 0 if good else 1
        print(f"{'PASS' if good else 'FAIL'} {method:5} {path:55} -> {st} (want {ok}{' + ' + must if must else ''}) {'' if good else text}")
    print(f"\n{len(CHECKS) - fails}/{len(CHECKS)} passed")
    sys.exit(1 if fails else 0)
