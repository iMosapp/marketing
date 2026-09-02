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

## SMS SAFETY RULE
- Twilio credentials in preview are LIVE. Only ever use 500-555-XXXX phone numbers (Twilio test range) for any code / invite / broadcast test. Never trigger flows against real numbers (e.g. forest's 8016349122).
