# Test Credentials

## Super Admin
- Email: forest@imosapp.com
- Password: Admin123!

## Test User (No Store / No Org)
- Email: mjeast1985@gmail.com
- Password: NavyBean1!
- Notes: onboarding_complete: null, store_id: null, org_id: null, role: user, status: active

## Activation-Flow Test User (created June 2026, preview only)
- Email: activation-tester@invalid.imonsocial.test
- Phone: +15005550006 (Twilio test number, never a real person)
- Password: NewPass123! (set via /api/auth/activate/complete)
- Notes: role user, phone_verified true. Safe to reuse for /auth/activate or forgot-password tests.

## QA Store Manager (preview only, seeded June 2026 via backend/tests/seed_qa_manager.py, idempotent)
- Email: qa-manager@invalid.imonsocial.test
- Password: Manager123!
- Notes: role store_manager on Forest's store 69a0b7095fddcede09591668 ("i'M On social"). Use for any manager screen that needs a store (Lead Source Config, Connect Zapier / Make, Proof spend editor). forest@imosapp.com is super_admin with NO store_id in preview, so store-scoped lists come back empty for him.

## SMS SAFETY RULE
- Twilio credentials in preview are LIVE. Only ever use 500-555-XXXX phone numbers (Twilio test range) for any code / invite / broadcast test. Never trigger flows against real numbers (e.g. forest's 8016349122).

## Preview URL note (June 2026)
- REACT_APP_BACKEND_URL in frontend/.env is the ONLY valid preview host (currently https://user-routing-issue.preview.emergentagent.com). imos-deploy-prep.preview.emergentagent.com is a stale preview that shows the Emergent "wake up servers" page.
- Web-only: /help and /inbox URLs are shadowed by static marketing pages; navigate in-app (history.pushState + popstate) when scripting.

## Shared Inbox demo data (preview only, `cd /app/backend && python tests/seed_inbox_demo.py` re-seeds idempotently, `--wipe` removes)
- Sales inbox (+15005550200, jump ball, members QA Manager + Activation Tester + Forest) and Service inbox (+15005550210, round robin, members QA Manager + Activation Tester), store 69a0b7095fddcede09591668.
- Demo customers are Twilio test numbers +15005550031 / 32 / 33 ("Lead (0031)" etc). SMS/push are stubbed during seeding only; live actions in the UI hit real Twilio (harmless: 500-555 numbers are rejected).
- Manager UI: log in as qa-manager; rep UI: activation-tester. Hub > Manage > Inboxes = /inboxes (library) and /inboxes/{id} (editor).
