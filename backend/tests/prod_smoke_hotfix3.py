"""Anonymous, read-only production smoke for security hotfix 3. Nothing is created or changed: every write probe is refused before any handler runs.
python tests/prod_smoke_hotfix3.py [base_url] [expected_build]"""
import json
import sys
import urllib.error
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "https://app.imonsocial.com").rstrip("/")
EXPECTED_BUILD = sys.argv[2] if len(sys.argv) > 2 else "2026-10-14.security-hotfix3"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36", "Content-Type": "application/json"}
ZERO = "0" * 24


def call(method, path, body=None, headers=None):
    req = urllib.request.Request(BASE + path, method=method, data=json.dumps(body).encode() if body is not None else None, headers={**UA, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode()[:160]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:160]


CHECKS = [
    # the holes
    ("POST", "/api/webhooks/user-created", {"external_id": "probe", "email": "probe@example.com", "name": "probe", "role": "super_admin"}, None, {401}),
    ("POST", "/api/webhooks/user-deleted", {"email": "probe@example.com"}, None, {401}),
    ("POST", "/api/webhooks/contact-created", {"external_id": "probe", "name": "probe"}, None, {401}),
    ("POST", "/api/webhooks/event", {"type": "probe"}, None, {401}),
    ("POST", "/api/webhooks/inventory/add", {"external_id": "probe", "name": "probe"}, None, {401}),
    ("GET", "/api/webhooks/inventory", None, None, {401}),
    ("PATCH", f"/api/auth/users/{ZERO}", {"email": "probe@example.com"}, None, {401}),
    ("PATCH", f"/api/auth/users/{ZERO}", {"email": "probe@example.com"}, {"X-User-ID": ZERO}, {401}),
    ("PUT", f"/api/auth/user/{ZERO}", {"phone": "+15550000000"}, None, {401}),
    ("POST", f"/api/auth/persona/{ZERO}", {"bio": "probe"}, None, {401}),
    ("GET", f"/api/auth/persona/{ZERO}/ai-prompt", None, None, {401}),
    ("PUT", f"/api/auth/users/{ZERO}/review-links", {"review_links": {}}, None, {401}),
    ("GET", f"/api/auth/user/{ZERO}", None, None, {401}),
    ("POST", "/api/auth/change-password", {"user_id": ZERO, "current_password": "x", "new_password": "Probe123!"}, None, {401}),
    ("POST", "/api/auth/complete-onboarding", {"user_id": ZERO}, None, {401}),
    ("POST", "/api/auth/test-login", {"email": "probe@example.com", "password": "probe"}, None, {410}),
    ("POST", f"/api/messages/send/{ZERO}", {"conversation_id": ZERO, "content": "probe"}, None, {401}),
    ("POST", "/api/messages/twilio-send", {"user_id": ZERO, "to": "+15005550006", "body": "probe"}, None, {401}),
    ("PUT", f"/api/profile/{ZERO}", {"bio": "probe"}, None, {401}),
    ("POST", f"/api/profile/{ZERO}/generate-bio", {}, None, {401}),
    ("GET", f"/api/notifications/?user_id={ZERO}", None, None, {401}),
    ("GET", f"/api/chat/leads?user_id={ZERO}", None, None, {401}),
    ("POST", "/api/s/create", {"original_url": "https://example.com", "link_type": "probe"}, None, {401}),
    ("POST", "/api/s/wrap", {"url": "https://example.com", "user_id": ZERO}, None, {401}),
    ("GET", "/api/s/stats/probe", None, None, {401}),
    ("GET", "/api/directory/members", None, None, {401}),
    ("GET", "/api/webhooks/unassigned-contacts", None, None, {401}),
    ("GET", "/api/setup-wizard/clients", None, None, {401}),
    # public surface must stay open
    ("GET", "/api/health", None, None, {200}),
    ("GET", "/api/legal/terms", None, None, {200}),
    ("GET", "/api/subscriptions/plans", None, None, {200}),
    ("GET", "/api/public/platform-stats", None, None, {200}),
    ("GET", "/api/webhooks/config", None, None, {200}),
    ("GET", "/api/webhooks/inventory/config/endpoints", None, None, {200}),
    ("GET", f"/api/congrats/card/{ZERO}", None, None, {404}),
    ("GET", "/api/s/probe-does-not-exist", None, None, {404}),
    ("POST", "/api/auth/login", {"email": "probe@example.com", "password": "probe"}, None, {401, 429}),
    ("GET", "/api/auth/me", None, None, {401}),
    ("POST", "/api/auth/refresh", {}, None, {401}),
    ("POST", "/api/auth/forgot-password/request", {}, None, {400, 422}),
    ("POST", "/api/cron/pilot-reminders", {}, None, {401}),
    ("GET", "/api/v1/contacts", None, None, {401}),
]


def main():
    fails = 0
    st, body = call("GET", "/api/health")
    build = ""
    try:
        build = json.loads(body).get("build", "")
    except (ValueError, AttributeError):
        build = ""
    print(f"health {st} build={build!r} expected={EXPECTED_BUILD!r} -> {'OK' if build == EXPECTED_BUILD else 'MISMATCH'}")
    fails += build != EXPECTED_BUILD
    for method, path, body, headers, want in CHECKS:
        st, text = call(method, path, body, headers)
        ok = st in want
        fails += not ok
        print(f"{'OK  ' if ok else 'FAIL'} {method:<6} {path:<60} {st} (want {sorted(want)}) {'' if ok else text}")
    print(f"\n{len(CHECKS) + 1 - fails}/{len(CHECKS) + 1} checks passed")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
