# Phase 1 Stage 1: founder walkthrough + results (Oct 11 2026, preview only)

## Results
- Backend: `tests/test_customer_launch_stage1.py` 14/14 against the live preview API (creation dormant + no credentials, role boundaries, partner scoping, tenant isolation, activation order, exception rules, single-use 72 h link, founder notification, seat limits on every creation path, legacy orgs untouched). P0 regression 128/128 (`test_new_account_onboarding.py` updated to the new contract).
- Frontend: testing agent iteration_100, web flows F1-F8 all passed as forest (super admin) and qa-manager (must see nothing).
- Bug found and fixed while running the suite: `new-account` validated extra seats AFTER inserting org/store/user, so a bad seat count left an orphan legacy org. Validation now runs before any write.
- Nothing deployed. Stripe untouched. Rollback target: checkpoint `afff51e84`.

## Click-through (preview, forest@imosapp.com)
1. More/Tools -> Onboarding Hub (`/admin/onboarding-hub`). First card, gold border: **New Customer**. Below the cards: **Customers** list with a status pill per row (Created / Activated / Owner invited / Owner active, billing line Unpaid / Exception / Paid).
2. New Customer -> search the business or **Enter manually** -> business fields, contact (name, mobile, email), **Plan** (Pilot Store $375/mo incl. 5 seats, Pilot Individual $100/mo), extra-seat stepper on the Store plan -> **Create Customer**. No password is shown anywhere: the owner account exists but is dormant.
3. You land on the customer page: Seats x/y, People active, Monthly amount, **Add a seat ($75/mo)**, then the 5-step rail:
   1. Customer created (done)
   2. Plan and payment: **Grant billing exception** (reason + 30/60/90 days). Recorded as an exception, never as a payment. Stripe checkout replaces this in Stage 2.
   3. Activate account (enabled once paid or excepted): turns the company on.
   4. Invite the owner: **Send activation link** (text + email, single use, 72 h). **Resend** supersedes the old link.
   5. Owner signs in and sets up: you get a push + Alerts entry "Dana activated QA Pilot Demo Co". Link to the org's team / phone numbers screen.
   Notes box (saved on blur) and History (who did what, when) at the bottom.
4. Owner side: taps the link -> `/auth/activate?token=` -> picks a password -> lands in the app with the pilot permission set (campaigns / approvals / inventory off, invite team on). Until then any login attempt is refused.
5. Demo row left in preview: **QA Pilot Demo Co** (Created / Unpaid). Remove with `cd /app/backend && set -a && . ./.env && set +a && python tests/wipe_pilot_customers.py`.

## GO/NO-GO recommendation for Stage 2 (Billing)
GO, with two conditions decided by the owner before coding:
1. Pricing confirmed as provisional (Pilot Store $375 incl. 5 seats + $75/seat, Pilot Individual $100) or changed.
2. Which Stripe account charges real cards: claim the Emergent sandbox (`acct_1UF17PGkCLOq0IAO`, unclaimed, expires 2026-11-12) or paste the owner's own Stripe keys into Secrets. Stage 2 code is identical either way; test mode runs first.
Stage 1 ships on its own too (backend Deploy + EAS update) if the owner wants the exception-based pilot live before billing.
