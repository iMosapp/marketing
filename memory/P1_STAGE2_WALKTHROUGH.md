# Phase 1 Stage 2: Stripe recurring billing. Founder walkthrough + results (Oct 11 2026, preview only)

## Results
- Catalog created in the owner's TEST sandbox (acct_1TZx5C0HHTIPsg1w, "VI Ventures Group LLC"), idempotent by lookup key: pilot_store_monthly $375, pilot_seat_monthly $75, pilot_individual_monthly $100 (`python tests/ensure_billing_catalog.py [--dry-run]`, PYTHONPATH=/app/backend).
- `tests/test_billing_stage2.py` 10/10 (+1 skipped until the webhook secret exists): catalog idempotent, Checkout session (mode subscription, 2 line items, client_reference_id, customer metadata, session reuse), super-admin-only routes, anonymous confirm trusts only Stripe, webhook writer idempotent by event id, failed payment -> past_due + 14-day grace + founder notification + no suspension, recovery, seat sync both directions (app -> Stripe quantity, Stripe -> app), plan swap refused on a live subscription, seat guard, cancel at period end / resume / deleted / restart, stale-event guard, exception path intact, legacy Stripe files untouched.
- Real hosted Checkout completed in a browser with card 4242 on "QA Pilot Demo Co": $450/month, redirected to `/billing/success`, pull-confirm marked the customer Paid (billing_source checkout_return) without any webhook.
- Regression: Stage 1 suite 14/14, P0 + legacy suites 139/139. Testing agent iteration_381: all six web flows passed (founder paid/unpaid pages, cancel/resume, public return pages, owner Billing screen -> Stripe portal, legacy manager message, Hub regression).
- Nothing deployed. Mystery Shops / legacy Stripe variables and routes unchanged. `stripe.api_key` never set by the new code (isolated `StripeClient`).

## Click-through (preview, forest@imosapp.com)
1. Hub -> Customers -> **QA Pilot Demo Co** (Paid). The Plan and payment step reads "Paid through Stripe · renews Nov 11, 2026"; Activate is enabled. STRIPE BILLING panel: Sync with Stripe, Billing portal link (copies a portal URL you can text the owner), Cancel at period end / Resume, Open in Stripe (test dashboard).
2. New customer path: create one in the Hub -> step 2 **Send payment link** (texts + emails the Stripe Checkout URL to the owner) or **Copy payment link**. Pill becomes "Payment link sent / Awaiting payment"; the step button becomes **Check payment**. The owner pays on Stripe's page (never in the app); the return page says "Payment received"; the row flips to Paid even before the webhook is wired.
3. **Grant billing exception instead** stays as the manual path (super admin, reason + end date, audited).
4. **Add a seat**: with a live subscription the Stripe quantity is updated and the prorated amount is invoiced immediately; without one it only raises the limit.
5. Owner side (qa-pilot-owner-ui@invalid.imonsocial.test / PilotOwner123!): More -> Store Setup -> **Billing** -> plan, renewal, status, **Payment method, invoices and plan** (Stripe Customer Portal: card update, invoices, cancel at period end). Legacy managers see "handled by your representative".
6. Founder notifications (push + Alerts): payment failed (with the grace date), payment recovered, cancellation scheduled, subscription ended.

## Failed payment policy (documented)
`invoice.payment_failed` -> billing_status past_due, grace_until = first failure + 14 days, failed_attempts += 1, founder notified. Stripe Smart Retries keep trying; `invoice.paid` clears it. Nothing is ever suspended automatically: the founder decides from the customer page / org page. Enable in the Stripe Dashboard: Settings -> Billing -> Subscriptions and emails -> Smart Retries + "Send emails about failed payments" so the owner gets Stripe's dunning emails too.

## Webhook: registered and verified (Oct 11 2026)
Endpoint active in the owner's sandbox; `STRIPE_BILLING_WEBHOOK_SECRET` set in preview backend/.env by the owner. Verification: unsigned 400, forged 400, stale timestamp 400, self-signed 200; duplicate event id -> `{duplicate: true}` with one write; Stripe's own `customer.subscription.created` + `invoice.paid` deliveries reached the preview route (200, processed, idempotent against the pull writer); 0 x 500 in logs. Suite `test_billing_stage2.py` 11/11 twice.

### Original setup notes
Dashboard (Test mode) -> Developers -> Webhooks -> Add endpoint / destination:
- URL: `https://user-routing-issue.preview.emergentagent.com/api/billing/stripe/webhook`
- Events: `checkout.session.completed`, `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.paid`, `invoice.payment_failed`
- Copy the signing secret (`whsec_...`) into `backend/.env` -> `STRIPE_BILLING_WEBHOOK_SECRET=` via VS Code, save, then say "secret is in". The agent restarts the backend, runs the signed test (`test_webhook_rejects_unsigned_and_forged_payloads` stops skipping) and the owner can press "Send test event".
Until then the route answers 503 to everything (by design) and status changes made outside the app (failed renewals, portal cancellations) land only when the founder presses Sync with Stripe.

## Remaining risks
1. (resolved Oct 11) Webhook delivery proven end-to-end in preview; production needs its own endpoint + secret.
2. Legacy `/api/webhook/stripe` and `/api/stripe/webhook` keep their unsigned fallbacks (out of scope since the audit).
3. Pilot owner's More menu still lists non-pilot tools (Campaigns, Inventory Feed, Appraisal Rules): Stage 3 trimming.
4. No tax collection (amounts tax-exclusive); portal configuration exists in test mode only (live mode auto-creates on first use).
5. Production needs: the two new Secrets, a second webhook endpoint for `https://app.imonsocial.com/api/billing/stripe/webhook`, live-mode catalog (same script, live key), backend Deploy + EAS update. Stage 1 backend deploy was started by the owner on Oct 11.

## GO/NO-GO for Stage 3
GO: the webhook secret is in and the signed + live tests pass. Stage 3 (pilot Home + founder progress on the row) needs no Stripe decisions.
