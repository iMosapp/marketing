# Phase 1: Simplified Customer Launch Workflow (plan, Oct 11 2026)

Goal: Create Customer -> Choose Plan -> Collect Payment -> Activate Account -> Invite Owner -> Start Onboarding, founder-driven, ~15 min to first use. Preview only until approved. No new provisioning system.

## Audit findings that shape the smallest path (read-only, verified Oct 11 2026)
1. `POST /api/setup-wizard/new-account` (setup_wizard.py:304-489) already creates org + store + store_manager owner + `onboarding_clients` row, seeds store/user defaults and auto-sends the A2P compliance form (`compliance_onboarding.auto_invite`). It returns the owner's plaintext temp password; the screen `app/onboarding/new-account.tsx` shows it with a copy button and is NOT linked from the Onboarding Hub (ACTIONS array has 7 cards, none point at it).
2. Owner/rep invitation that works today: `POST /admin/users/create` -> `activation_pending`, invite email + `ACTIVATION_SMS` ("download the app, tap Activate my account, enter the code, choose your password") -> `/auth/activate/{request,verify,complete}` (10-min codes, re-request = resend). The new-account path does not use it.
3. Billing: Flow A claimable Stripe sandbox already provisioned for this app (`acct_1UF17PGkCLOq0IAO`, US, `lifecycle_state: unclaimed`, `charges_enabled: false`, sandbox expires 2026-11-12). Catalog EMPTY (0 products, 0 prices, 0 subscriptions). Platform-registered signed webhook endpoints exist for production and preview at `/api/stripe/webhook`; that route (routers/mystery_shops.py:2043-2058) already verifies with `stripe.Webhook.construct_event` + `STRIPE_WEBHOOK_SECRET` but has an insecure fallback when the secret is empty and no event-id idempotency. The legacy `/api/webhook/stripe` (server.py:1505) + quotes/checkout use `emergentintegrations` in one-time `mode='payment'`: NOT reusable for subscriptions (left untouched).
4. Nothing enforces seats (`max_users_per_store` exists on the model, never read). `organizations.active` is display-only (login never checks it). Login refuses `is_active: False` / `status: deactivated` users (auth.py:696).
5. Permissions: a brand-new `user` (rep) already has every optional item OFF (permissions.py `_USER_PERMISSIONS`), so reps are already "pilot simple". The owner (`store_manager`) gets 25 items ON (appraisals, inventory, internet leads, campaigns, approvals...). Per-user `feature_permissions` overrides are merged at login (`merge_permissions`), editable at `PUT /admin/permissions/{user_id}`, read by the More tab. Home: `simpleHome = role === 'user' && !partner_id` (home.tsx:872) -> owners see the full Home.
6. Nothing surfaces plan / seats / billing / onboarding status anywhere; `organizations.plan` is a free string.

## Account-level data (minimum), one sub-document, written only for NEW customers
```
organizations.customer = {
  pilot: true,
  plan_key: "pilot_store_monthly" | "pilot_individual_monthly",   # Stripe price lookup_key
  seats_included: 5, seats_extra: 0,
  billing_status: "unpaid" | "awaiting_payment" | "trialing" | "active" | "past_due" | "canceled" | "manual",
  onboarding_status: "created" | "payment_link_sent" | "paid" | "activated" | "owner_invited" | "owner_active",
  owner_user_id, created_by, created_at,
  checkout_session_id, checkout_url, stripe_customer_id, stripe_subscription_id, current_period_end, paid_at,
  activated_at, activated_by, owner_invited_at, owner_activated_at, notes
}
```
Existing organizations never get this field; every list/gate treats "no customer field" as "legacy, unchanged".

## Stage 1: Customer record + founder workflow in the Onboarding Hub (no Stripe)
Backend (`routers/setup_wizard.py`, `routers/rbac.py`, `routers/admin_users.py`, `routers/auth.py`, `routers/team_invite.py`, `permissions.py`):
- `new-account` gains `plan_key`, `seats_included`, `pilot` (default true); writes `organizations.customer`; owner user created DORMANT (`is_active: False`, `activation_pending: True`, no temp password in the response); pilot owner gets `PILOT_OWNER_PERMISSIONS` overrides (keeps users / invite_team / store_profile / brand_kit / contact_tags / sms_templates / card_templates / touchpoints / my_performance; turns off appraisals, inventory, internet leads, keyword search, team chat, AI follow-ups, campaigns, showcase/review approvals, brand pages, analytics, leaderboard, manage.*). Owner can re-enable anything later with the existing permissions screen.
- New routes `/api/setup-wizard/customers` (same `require_account_creator` gate): `GET /` (rows: org, store, plan, seats used/included, billing_status, onboarding_status, owner activated, reps invited/active, has work number, A2P status), `GET /{org_id}`, `PATCH /{org_id}` (notes, plan_key, seats), `POST /{org_id}/activate` (sets owner `is_active: True`, `organizations.active: True`, `activated_at/by`), `POST /{org_id}/invite-owner` (reuses the activation email + SMS extracted into `admin_users.send_activation_invite(user)`; re-callable = resend), `POST /{org_id}/mark-paid-manual {note}` (temporary manual billing, `billing_status: "manual"`).
- `POST /auth/activate/complete`: when the user is a customer's `owner_user_id`, stamp `owner_activated_at` + `onboarding_status: owner_active` and push the founder (`created_by`) "Owner activated".
- Seat check (super_admin bypass) in `/admin/users/create`, `/setup-wizard/bulk-invite`, `/team-invite/join`: active+pending users in the org >= seats_included + seats_extra -> 400 "This plan includes N seats. Add a seat first." Only when `organizations.customer` exists.
Frontend (`app/admin/onboarding-hub.tsx`, `app/onboarding/new-account.tsx`, new `app/admin/customers/[orgId].tsx`):
- Hub: first card "New Customer" (super_admin / partner admin) + "Customers" list (status pill per row). New-account form gains Plan + Seats. Success -> customer screen with a step rail: Created / Plan / Payment / Activate / Invite owner / Onboarding; each step one button with its status, resend on invite, links to existing Users, Communications (Twilio), Compliance.
Acceptance tests (pytest against the preview API + one testing-agent UI pass):
- A1 super admin creates "QA Pilot Co": org/store/user/customer docs as specified, response has no `temp_password`, owner login -> 401/403 while dormant.
- A2 rep (activation-tester), store manager (qa-manager), non-partner org admin (qa-orgadmin) -> 403 on every `/customers` route; anonymous -> 401.
- A3 activate -> owner `is_active: True`; invite-owner -> SMS attempt to a 500-555 number logged (`sms_sent: false` is fine in preview) + email request to an @invalid.imonsocial.test address; second call = resend.
- A4 activation complete (code read from `password_reset_tokens` in the test) -> `owner_activated_at` set, founder notification row exists, owner lands on the slideshow then Home.
- A5 seat check: 6th user on a 5-seat customer refused with the message; super admin can still add; a legacy org (QA store) is never limited.
- A6 pilot owner `feature_permissions`: campaigns/manage off, invite_team on; qa-manager's permissions unchanged (snapshot compare); count of organizations without `customer` unchanged after the run.
- A7 UI: Hub -> New Customer -> form -> customer screen -> buttons; Customers list shows the row; `/admin/onboarding-hub` for qa-manager shows neither.
Rollback: platform Rollback to the Stage 1 checkpoint (taken before coding). Data: `python tests/wipe_pilot_customers.py --wipe` removes only orgs with `customer.created_by` = QA actor and name prefix "QA Pilot"; legacy docs are never written. No env change.

## Stage 2: Stripe-hosted recurring subscription, pull-confirmed, signed webhook
- Catalog `scripts/setup_stripe.py` (idempotent, lookup keys, SaaS tax code `txcd_10103001`): product "i'M On Social Pilot" with `pilot_store_monthly` (base, includes 5 seats), `pilot_seat_monthly` (extra seat), `pilot_individual_monthly`. Amounts to confirm (proposal below). Tax mode per playbook: US sandbox -> Stripe managed payments with automatic fallback to Stripe Tax.
- `POST /customers/{org_id}/checkout` -> `stripe.checkout.Session.create(mode="subscription", customer_email, client_reference_id=org_id, line_items=[base x1, seat x extra], subscription_data={metadata.org_id, trial_period_days when the founder ticks "14-day trial"}, success/cancel on app.imonsocial.com)`; stores `checkout_session_id/url`, `billing_status: awaiting_payment`, `onboarding_status: payment_link_sent`; "Text the link" / "Email the link" use the existing `send_sms` / Resend helpers; copy button.
- `POST /customers/{org_id}/refresh-billing` (also run automatically for `awaiting_payment` rows when the Customers list loads): `stripe.checkout.Session.retrieve` -> `stripe.Subscription.retrieve` -> `billing_status` (`trialing` / `active` / `past_due` / `canceled`), `stripe_customer_id`, `stripe_subscription_id`, `current_period_end`, `paid_at`. This pull is the source of truth for the pilot; nothing depends on the webhook arriving.
- Webhook: extend the existing signed `/api/stripe/webhook` (routers/mystery_shops.py): remove the unsigned fallback (400 when no secret), `stripe_events` collection keyed by event id (idempotent), handle `checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.paid`, `invoice.payment_failed` -> same writer as refresh-billing; `past_due` pushes the founder. Legacy `/api/webhook/stripe`, quotes, partner agreements untouched.
- `GET /customers/{org_id}/portal` -> `stripe.billing_portal.Session.create` (founder; owner later) for card update / invoices / cancel at period end. Small, optional inside the stage.
- Activate button: enabled when `billing_status` in (active, trialing, manual); otherwise a confirm "Not paid yet. Activate anyway?" with a required reason (stored in notes).
Acceptance tests:
- B1 catalog script idempotent (second run creates nothing; prices found by lookup key).
- B2 checkout session: `mode == "subscription"`, two line items when seats_extra > 0, `client_reference_id == org_id`, trial days present only when ticked; `checkout_url` stored; org row shows awaiting_payment.
- B3 testing agent completes the hosted Checkout with card 4242 4242 4242 4242 in test mode; `refresh-billing` -> `active` (or `trialing` with trial), subscription id stored; Customers list shows Paid.
- B4 webhook: self-signed test payloads (`stripe.WebhookSignature` with the preview secret): unsigned -> 400; `invoice.payment_failed` -> `past_due` + founder push; same event id twice -> one `stripe_events` row and one write; `customer.subscription.deleted` -> `canceled`.
- B5 regression: mystery-shop invoice webhook still marks invoices paid; legacy `/api/webhook/stripe` unchanged (existing tests); P0 suite 125 green.
- B6 portal session URL returned for a paid customer; 400 for an unpaid one.
Rollback: platform Rollback to the Stage 2 checkpoint; the Stripe catalog and test subscriptions are test-mode and harmless (cancel test subscriptions via `stripe.Subscription.delete` in the wipe script); `$unset customer.checkout_*` on QA orgs. No env change (the webhook secret and keys already exist).
Go-live dependency (not code): real charges need the owner to claim the sandbox (Emergent: Manage -> Payments -> claim; KYC) or to supply his own Stripe keys in Secrets. Until then the pilot bills "manual" (Stage 1 button) or by a Payment Link made in his own Stripe Dashboard pasted into the row.

## Stage 3: Pilot first-run for the owner + progress on the founder row (frontend, needs EAS update)
- `/auth/me` + login response add `pilot: true` and `billing_status` for users in a pilot org; `simpleHome` also true for pilot owners (store_manager) so they land on the simple Home (Welcome video / tour, card QR, Do This Next) instead of the 1,500-line full Home; the More tab is already trimmed by the Stage 1 overrides. Existing customers: `pilot` absent -> nothing changes.
- Founder row "Onboarding" step shows live progress from existing data: owner activated, photo + title set, first card share, first contact, reps invited / active, work number assigned (Twilio), A2P form status; founder push on owner activation (Stage 1) and on first card share.
Acceptance tests: C1 pilot owner login -> `home-simple`; qa-manager (legacy) -> `home-full`, More tab unchanged; C2 `/auth/me` carries `pilot` only for pilot orgs; C3 founder row progress flips as the owner acts (API-driven: photo upload, card share event to a 500-555 number); C4 P0 + Stage 1/2 suites green.
Rollback: platform Rollback to the Stage 3 checkpoint; frontend: `eas update --branch production` from the previous commit (or Rollback then re-run the standard EAS line). No data impact.

## Proposed pricing (to confirm)
- Pilot Store: $375/month, includes 5 seats (same as today's `store_standard` $75 x 5), extra seat $75/month, optional 14-day trial per customer.
- Pilot Individual: $100/month, 1 seat (today's `monthly`).

## 15-minute walkthrough (founder time ~8 min, customer ~7 min)
Create Customer form (3 min) -> plan picked in the form -> Text payment link (10 s) -> customer pays on their phone (3 min) -> Check payment / auto-refresh (10 s) -> Activate (1 tap) -> Invite owner (1 tap; SMS + email in seconds) -> owner downloads app, taps Activate, enters code, sets password (4 min) -> slideshow (skippable) -> simple Home -> shares card. Excluded: A2P registration (auto-sent at creation, carrier timeline), buying/assigning a work number (founder, ~2 min on the existing Communications screen; needed before the owner can text).

## Effort and credits
The agent cannot read credit balances. Actual usage per stage: Profile -> Account Settings -> Credit Usage -> expand the agent run -> per-job line. Save to GitHub between stages so each stage is its own ledger entry. Relative estimates (P0 = 1 session): Stage 1 ~1 session (one testing-agent run), Stage 2 ~1 to 1.5 sessions (Stripe test-mode round trips + one testing-agent run), Stage 3 ~0.5 to 1 session (UI pass).
