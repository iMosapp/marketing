# Stripe Live Pre-Flight — app.imonsocial.com (READ-ONLY)
Deployment: imos-deploy-prep | DB: imos-admin-test_database | Active run: bf277e6b-3ca6-42e1-9aff-a1dba73663cc
Build (via /api/health): 2026-10-14.mms-stage1

## 1. billing_settings
Collection does NOT exist. No `stripe_portal` document; no other `_id`s.

## 2. organizations (total = 10)
- customer.stripe_customer_id set: 0
- customer.stripe_subscription_id set: 0
- customer.checkout_url set: 0
- billing_status in {awaiting_payment, unpaid, active, trialing, past_due}: 0 orgs (none to list)
- Only distinct customer.billing_status value across all 10 orgs = "exception"

## 3. stripe_events
Collection absent → total 0.

## 4. Secrets (presence / match class only — no values read)
- STRIPE_BILLING_SECRET_KEY: present, non-empty. Prefix class (rk/sk, live/test) NOT determinable via tooling (values never returned). UNVERIFIED.
- STRIPE_BILLING_WEBHOOK_SECRET: present, non-empty. whsec_ prefix NOT verifiable.
- STRIPE_MODE = "test" (confirmed via equals match) — NOT live.
- BILLING_ALLOW_TEST_MODE: present, non-empty; confirmed NOT "false" and NOT "true"/"True" (exact value not exposed).
- PUBLIC_FACING_URL = https://app.imonsocial.com (confirmed match).
- APP_URL = https://imos-deploy-prep.emergent.host (confirmed match) — emergent default, NOT app.imonsocial.com.

## 5. Build / commit
- Build tag confirmed: 2026-10-14.mms-stage1 (GET /api/health 200).
- Deployed commit NOT exposed by any read-only signal (.git stripped from pulled source; health returns build tag only). Commit aa33bda82 UNVERIFIABLE.

## Verdict: NOT live-ready
Blockers for Stripe live: STRIPE_MODE=test; APP_URL still emergent.host default; billing_settings/stripe_portal doc absent; no customers/subscriptions/checkout URLs provisioned; BILLING_ALLOW_TEST_MODE not explicitly false.
No deploy/write/restart performed — read-only pre-flight only.
