"""Anonymous, read-only production smoke for security hotfix 3/4.
python tests/prod_smoke_hotfix3.py [base_url] [expected_build]

Safety: the build label is checked FIRST and the script exits (code 2) before a single probe when it is missing or different,
because on an older backend the write probes would reach their handlers. Every write probe below also carries an inert body
(empty or an id that cannot exist), so even a mis-targeted run creates nothing."""
import json
import sys
import urllib.error
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "https://app.imonsocial.com").rstrip("/")
DEFAULT_BUILD = "2026-10-14.mms-stage1"
EXPECTED_BUILD = sys.argv[2] if __name__ == "__main__" and len(sys.argv) > 2 else DEFAULT_BUILD
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36", "Content-Type": "application/json"}
ZERO = "0" * 24


def call(method, path, body=None, headers=None):
    req = urllib.request.Request(BASE + path, method=method, data=json.dumps(body).encode() if body is not None else None, headers={**UA, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode()[:160]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:160]


def preflight(expected: str = EXPECTED_BUILD, fetch=None) -> tuple[bool, str]:
    """(ok, build). ok only when /api/health answers 200 with exactly the expected build label."""
    st, body = (fetch or call)("GET", "/api/health")
    try:
        build = json.loads(body).get("build", "") if st == 200 else ""
    except (ValueError, AttributeError):
        build = ""
    return (st == 200 and bool(expected) and build == expected), build


# (method, path, body, headers, accepted statuses). Bodies are inert: {} or ids that cannot exist.
CHECKS = [
    # hotfix 3: the holes
    ("POST", "/api/webhooks/user-created", {}, None, {401}),
    ("POST", "/api/webhooks/user-deleted", {}, None, {401}),
    ("POST", "/api/webhooks/contact-created", {}, None, {401}),
    ("POST", "/api/webhooks/event", {}, None, {401}),
    ("POST", "/api/webhooks/inventory/add", {}, None, {401}),
    ("GET", "/api/webhooks/inventory", None, None, {401}),
    ("PATCH", f"/api/auth/users/{ZERO}", {}, None, {401}),
    ("PATCH", f"/api/auth/users/{ZERO}", {}, {"X-User-ID": ZERO}, {401}),
    ("PUT", f"/api/auth/user/{ZERO}", {}, None, {401}),
    ("POST", f"/api/auth/persona/{ZERO}", {}, None, {401}),
    ("GET", f"/api/auth/persona/{ZERO}/ai-prompt", None, None, {401}),
    ("PUT", f"/api/auth/users/{ZERO}/review-links", {}, None, {401}),
    ("GET", f"/api/auth/user/{ZERO}", None, None, {401}),
    ("POST", "/api/auth/change-password", {}, None, {401}),
    ("POST", "/api/auth/complete-onboarding", {}, None, {401}),
    ("POST", "/api/auth/test-login", {}, None, {410}),
    ("POST", f"/api/messages/send/{ZERO}", {}, None, {401}),
    ("POST", "/api/messages/twilio-send", {}, None, {401}),
    ("PUT", f"/api/profile/{ZERO}", {}, None, {401}),
    ("POST", f"/api/profile/{ZERO}/generate-bio", {}, None, {401}),
    ("GET", f"/api/notifications/?user_id={ZERO}", None, None, {401}),
    ("GET", f"/api/chat/leads?user_id={ZERO}", None, None, {401}),
    ("POST", "/api/s/create", {}, None, {401}),
    ("POST", "/api/s/wrap", {}, None, {401}),
    ("GET", "/api/s/stats/probe", None, None, {401}),
    ("GET", "/api/directory/members", None, None, {401}),
    ("GET", "/api/webhooks/unassigned-contacts", None, None, {401}),
    ("GET", "/api/setup-wizard/clients", None, None, {401}),
    # hotfix 4
    ("POST", f"/api/messages/conversations/{ZERO}", {}, None, {401}),
    ("POST", f"/api/voice-notes/{ZERO}/{ZERO}/chunk", {}, None, {401}),
    ("POST", "/api/webhooks/twilio/call", {}, None, {401}),
    ("POST", "/api/webhooks/twilio/call-cancel", {}, None, {401}),
    ("GET", "/api/webhooks/twilio/call-progress/CA0", None, None, {401}),
    ("POST", "/api/webhooks/twilio/incoming", {}, None, {403}),       # unsigned Twilio callback
    ("POST", "/api/webhooks/twilio/status", {}, None, {403}),
    ("POST", "/api/webhooks/twilio/voice", {}, None, {403}),
    ("POST", "/api/webhooks/twilio/recording-complete", {}, None, {403}),
    ("POST", "/api/webhooks/twilio/trusthub-status", {}, None, {403}),
    ("POST", "/api/messages/webhook/inbound", {}, None, {403}),
    ("POST", "/api/webhooks/dialer/rep/status", {}, None, {403}),
    ("GET", "/api/webhooks/twilio/media-proxy?url=https%3A%2F%2Fexample.com%2Fx", None, None, {401}),  # media token first
    ("POST", "/api/webhooks/resend/inbound", {}, None, {401, 503}),
    ("POST", f"/api/card/save/{ZERO}", {"contact_id": ZERO, "campaign_id": ZERO}, None, {404}),
    ("PUT", f"/api/admin/users/{ZERO}", {}, None, {401}),
    # hotfix 4b
    ("PUT", f"/api/admin/hierarchy/users/{ZERO}/assign-org", {}, None, {401}),
    ("PUT", f"/api/admin/hierarchy/users/{ZERO}/assign-store", {}, None, {401}),
    ("PUT", f"/api/admin/hierarchy/users/{ZERO}/change-organization", {}, None, {401}),
    ("PUT", f"/api/admin/hierarchy/users/{ZERO}/role", {}, None, {401}),
    ("POST", "/api/partners/portal/assign-org", {}, None, {401}),
    ("GET", f"/api/partners/portal/orgs/{ZERO}/users", None, None, {401}),
    ("GET", "/api/calls/recording/CA0", None, None, {401}),
    ("GET", "/api/calls/recording-token", None, None, {401}),
    ("GET", f"/api/calendar/oauth/login/{ZERO}", None, None, {401}),
    ("GET", "/api/calendar/oauth/callback?code=x&state=" + ZERO, None, None, {400}),
    ("POST", "/api/webhooks/twilio/lead-call/status", {}, None, {403}),
    ("POST", "/api/stripe/webhook", {}, None, {400, 503}),
    ("POST", f"/api/admin/team/shared-inboxes/{ZERO}/webhook", {}, None, {401, 404}),
    ("POST", "/api/webhooks/inventory/update", {}, None, {401}),
    # hotfix 4c: account creation / approval surfaces are never anonymous
    ("POST", "/api/admin/users", {}, None, {401}),
    ("POST", "/api/admin/users/create", {}, None, {401}),
    ("POST", "/api/admin/users/add-team-member", {}, None, {401}),
    ("PUT", f"/api/admin/pending-users/{ZERO}/approve", {}, None, {401}),
    ("PUT", f"/api/admin/pending-users/{ZERO}/reject", {}, None, {401}),
    ("GET", "/api/admin/pending-users", None, None, {401}),
    ("POST", "/api/admin/individuals", {}, None, {401}),
    ("POST", "/api/setup-wizard/bulk-invite", {}, None, {401}),
    ("POST", f"/api/permission-templates/org_admin/apply/{ZERO}", {}, None, {401}),
    ("POST", "/api/permission-templates/", {}, None, {401}),
    ("GET", "/api/health/webhook-enforcement", None, None, {401}),
    # public surface must stay open
    ("GET", "/api/health", None, None, {200}),
    ("GET", "/api/legal/terms", None, None, {200}),
    ("GET", "/api/subscriptions/plans", None, None, {200}),
    ("GET", "/api/public/platform-stats", None, None, {200}),
    ("GET", "/api/webhooks/config", None, None, {200}),
    ("GET", "/api/webhooks/inventory/config/endpoints", None, None, {200}),
    ("GET", f"/api/congrats/card/{ZERO}", None, None, {404}),
    ("GET", "/api/s/probe-does-not-exist", None, None, {404}),
    ("POST", "/api/auth/login", {}, None, {400, 401, 422, 429}),
    ("GET", "/api/auth/me", None, None, {401}),
    ("POST", "/api/auth/refresh", {}, None, {401}),
    ("POST", "/api/auth/forgot-password/request", {}, None, {400, 422}),
    ("POST", "/api/cron/pilot-reminders", {}, None, {401}),
    ("GET", "/api/v1/contacts", None, None, {401}),
]


def main():
    ok, build = preflight()
    print(f"health build={build!r} expected={EXPECTED_BUILD!r} -> {'OK' if ok else 'MISMATCH'}")
    if not ok:
        print("ABORT: build label missing or different; no probe was sent (an older backend would execute the write probes).")
        sys.exit(2)
    fails = 0
    for method, path, body, headers, want in CHECKS:
        st, text = call(method, path, body, headers)
        good = st in want
        fails += not good
        print(f"{'OK  ' if good else 'FAIL'} {method:<6} {path:<66} {st} (want {sorted(want)}) {'' if good else text}")
    print(f"\n{len(CHECKS) - fails}/{len(CHECKS)} checks passed")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
