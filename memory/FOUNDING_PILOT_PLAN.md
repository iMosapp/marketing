# Founding Partner Pilot: gap analysis + plan (Oct 11 2026, awaiting approval, no code written)

Business model: first customers get 90 days complimentary, agree to $375/mo per store (5 seats) + $75/seat, and are charged only if they explicitly elect to continue. Pilot starts when the owner activates. No card to begin. No automatic billing or conversion at day 90.

## 1. Gap analysis (what Stages 1-3 do today vs the requirement)

| # | Requirement | Today | Gap | Smallest change |
|---|---|---|---|---|
| 1 | Founder creates a 90-day complimentary pilot customer | New Customer form creates `billing_status: unpaid`; the only no-Stripe path is **Grant billing exception** (reason + fixed end date <= 180 d, label "Exception") | No pilot concept; exception has a fixed end date set at grant time, not at owner activation; labelled as an exception | New `billing_status: "pilot"` + `customer.pilot_program{}`; New Customer form gets a Billing choice defaulting to "Founding Partner Pilot (90 days)"; step 2 also gets "Start 90-day pilot" for an existing unpaid customer |
| 2 | Pilot begins when the owner activates | `on_owner_activated` stamps `owner_activated_at` + notifies the founder | Nothing starts a clock | In `on_owner_activated`: if `pilot_program.state == pending` -> `started_at = now`, `ends_at = now + 90 d`, `state active`, audit `pilot_started`; founder push text gains "their 90-day pilot ends Jan 9" |
| 3 | No Stripe payment or card to begin | `activate()` allows `BILLING_OK = {active, trialing, exception}`; Stripe is only touched by payment link / checkout | `pilot` not allowed | Add `pilot` to `BILLING_OK`; no Stripe customer is created until conversion (asserted by test) |
| 4 | Hub shows days remaining, onboarding progress, engagement, potential MRR | Row has Setup N/5, last activity, open issues, attention flags; stats Seats / People active / Monthly | No days left, no engagement counts, no MRR framing or totals | `row()` adds `days_left`, `mrr` (amount + seat_price x seats_extra), `engagement` (7-day and total: contacts, card shares, voice memos, texts sent, people active); Hub row line + a one-line summary above the list ("3 pilots · $1,125 potential MRR · 1 paying · $450 MRR"); ProgressCard gets ENGAGEMENT + "Potential MRR"; stat "Monthly" reads "Potential MRR" for pilots |
| 5 | Founder reminders at days 30, 60, 75 | Platform cron exists (`.emergent/crons.yml` -> `routers/cron.py`, secret + run-id dedup, live in preview: 28 runs); founder push + Alerts helper exists (`billing._notify_founder`) | No pilot job | Daily cron `pilot-reminders` -> `POST /api/cron/pilot-reminders` -> `services/pilot_program.tick()`: for each active pilot, each milestone in [30, 60, 75, 90] not yet in `reminders_sent` and `day >= milestone` -> one push + Alert to the founder (`customer_pilot_day_{n}`), stamped so it never repeats. Day 90 = "pilot period is over, nothing was charged, decide: continue / extend / end" (proposed addition, see decisions) |
| 6 | Customer can affirmatively convert at the agreed pricing | `create_checkout` (super admin "Send payment link") already works from `exception`; owner Billing screen only *opens* a founder-created `checkout_url`; no owner-initiated route | Owner cannot start Checkout on their own; pilot status would be left as is | New `POST /api/billing/checkout` (same guard as `/billing/me`: store_manager+ of own launch-customer org) -> `create_checkout`; owner Billing shows "Founding Partner Pilot · N days left · then $375/mo for 5 seats + $75/seat" + **Continue after the pilot**; `apply_subscription` stamps `pilot_program.converted_at / state converted`, audit `pilot_converted`, founder push "X continued after the pilot". Founder's existing Send payment link keeps working as the assisted path |
| 7 | No automatic billing or conversion at expiry | Nothing automatic today either; attention flag "Billing exception expired" | Need an explicit "over, undecided" state | At `ends_at` the status stays `pilot`, `state completed`; nothing in Stripe; attention "Pilot period over · decide" (escalates to "14+ days without a decision"); owner Billing + Home show "Your pilot ended on X. Continue for $375/mo" |
| 8 | Founder can extend or end, with audit trail | Exception can be re-granted (audit `billing_exception_granted`); no end action; org `active: false` does not block login (only `user.dormant` does) | No extend/end/resume; no access gate for an ended org | Super-admin routes `POST /customers/{org}/pilot/extend {days 30|60|90, reason}`, `/pilot/end {reason}`, `/pilot/resume {reason}`; audit `pilot_extended / pilot_ended / pilot_resumed` with before/after dates; `_apply_pilot_flags` (login + /auth/me) refuses users of an ended pilot with a clear message |
| 9 | Expired pilots: defined access + retention policy, no automatic deletion | None | Policy missing | Written policy (section 3), enforced only by the founder's End action; retention list in the Hub ("Ended pilots older than 12 months"), deletion stays manual via the existing org tools |
| 10 | Paying customers, legacy orgs, Stripe untouched | Everything keyed on `organizations.customer`; legacy orgs have none | - | All new logic keyed on `billing_status == "pilot"` / `customer.pilot_program`; `exception`, `active`, `past_due`, webhook, portal, seat sync unchanged; the only Stripe-touching change is the optional `trial_end` at conversion (decision B) |

## 2. Data model (additive, no migration)
```
organizations.customer.billing_status: "pilot"            # new value; "exception" stays for ad-hoc free access
organizations.customer.pilot_program: {
  kind: "founding_partner", days: 90,
  granted_at, granted_by, granted_by_name,
  state: "pending" | "active" | "completed" | "converted" | "ended",
  started_at, ends_at,                                    # set on owner activation
  reminders_sent: [30, 60, 75, 90],
  extensions: [{days, reason, by, by_name, at, ends_at_before, ends_at_after}],
  ended_at, ended_by, ended_reason, resumed_at,
  converted_at, converted_via: "owner_checkout" | "payment_link"
}
```
Agreed pricing is already on the record (`plan_key pilot_store_monthly`, `amount 375`, `seat_price 75`, `seats_included 5`, `seats_extra`). Potential MRR = `amount + seat_price * seats_extra`.

## 3. Expired-pilot access and data-retention policy (proposed)
1. Day 90 with no decision: access continues unchanged; nothing is charged; founder gets the day-90 reminder and a persistent attention flag; owner sees "Your pilot ended on X. Continue for $375/mo" in Billing and a quiet banner on Home. No automatic lockout, ever.
2. Founder **Extend** (+30/60/90, reason): `ends_at` moves, reminders for milestones already passed are not re-sent, audit row.
3. Founder **End** (reason): `organizations.active false`, `state ended`; every user of the org is refused at login and at session refresh with "Your pilot with I'm On Social has ended on X. Text or email Forest to continue." Data (contacts, messages, voice memos, card, files) stays exactly as is. Audit row. **Resume** (reason) reverses it.
4. Retention: data of ended pilots is kept 12 months; the Hub lists "Ended pilots older than 12 months" so the founder can decide; deletion stays manual through the existing organization tools (nothing automatic). Export on request = existing contact export.
5. Converted: `billing_status` follows Stripe (`trialing` until the first charge, then `active`); all Stage 2 behaviour applies from then on (portal, seats, past-due grace, cancel at period end).

## 4. Exact files affected
Backend
- `services/customers.py`: `BILLING_OK` + "pilot"; `new_pilot_program()`, `start_pilot_program()` (called from `on_owner_activated`), `extend_pilot()`, `end_pilot()`, `resume_pilot()`, `pilot_days()`; `row()` adds `pilot_program`, `days_left`, `mrr`, `engagement`.
- `services/pilot.py`: `engagement(db, user_ids)` counts; `attention()` pilot rules ("Pilot ends in N days" at <= 14, "Pilot period over · decide", "Pilot over 14+ days without a decision"); `founder_view` returns `engagement`.
- NEW `services/pilot_program.py` (~80 lines): `tick(db)` reminders, `notify_founder()` moved here from `billing._notify_founder` (billing keeps calling it).
- `services/billing.py`: `RESUBSCRIBE_OK` + "pilot"; `create_checkout` keeps `billing_status pilot` until paid (already true), optional `subscription_data.trial_end = ends_at` (decision B); `apply_subscription` stamps conversion + audit + founder push; `owner_summary` adds `pilot {state, days_left, ends_at, started_at}` and exposes `checkout_url` for pilots.
- `routers/customers.py`: `POST /{org}/pilot/start`, `/pilot/extend`, `/pilot/end`, `/pilot/resume` (super_admin only, same pattern as `/billing-exception`).
- `routers/billing.py`: `POST /checkout` (owner-initiated, guard shared with `/me`).
- `routers/setup_wizard.py`: new-account body `billing_mode: "founding_pilot" | "paid"` (default `founding_pilot` when `pilot` is true); writes `pilot_program` + audit `pilot_granted`.
- `routers/auth.py`: `_apply_pilot_flags` refuses `state == ended` (403 with the message), adds `pilot_days_left` / `pilot_state` to the session user.
- `routers/cron.py` + `.emergent/crons.yml`: `pilot-reminders` daily at 15:00 UTC (09:00 Mountain).
- Tests: NEW `tests/test_pilot_program.py`; regression suites unchanged.

Frontend
- `app/onboarding/new-account.tsx`: Billing choice (Founding Partner Pilot default / Paid from day one), body field.
- `app/admin/customers/[orgId].tsx`: `billingOk` includes `pilot`; step 2 copy for pilot (started / ends / days left / agreed pricing); actions Extend pilot, End pilot, Resume access; "Start 90-day pilot" secondary for unpaid; stat label "Potential MRR".
- NEW `components/customers/PilotSheet.tsx` (~60 lines): extend/end/resume sheet (day chips 30/60/90, reason).
- `components/customers/ProgressCard.tsx`: ENGAGEMENT row + days left + potential MRR.
- `components/customers/StatusPill.tsx`: `pilot: 'Pilot'` label + colour.
- `components/customers/BillingPanel.tsx`: pilot variant (Send payment link = "Send the continue link", no Cancel / portal while unconverted).
- `app/admin/onboarding-hub.tsx`: row line "Pilot · 62 days left · $375 potential MRR"; summary line above the Customers list; "Ended pilots older than 12 months" rows.
- `app/settings/billing.tsx`: pilot block + **Continue after the pilot** -> `POST /billing/checkout` -> open URL.
- `components/pilot/PilotMore.tsx`: Billing row subtitle "Founding Partner Pilot · N days left" (owner).
- `components/home/PilotHome.tsx`: quiet banner only in the last 14 days or after the end ("Your pilot ends in N days · Continue").

Untouched: Stripe webhook handling, portal, seat sync, failed-payment policy, exception path, legacy routes, Mystery Shops Stripe, `wipe_pilot_customers.py` (prefix arg works).

## 5. Scope
Backend ~350 lines (+~250 test), frontend ~250 lines, config 10 lines. One session of work, then testing agent. No deploy, no EAS update.

## 6. Test plan
Backend (`tests/test_pilot_program.py`, live preview API + Mongo + Stripe sandbox, prefix "QA FP Pilot", cleans up incl. any Stripe test customer)
1. Create with `billing_mode founding_pilot` -> `billing_status pilot`, `pilot_program pending`, no `stripe_customer_id`; Activate succeeds without payment; Invite; owner activates through the real link -> `started_at`, `ends_at = +90 d`, `state active`, audit `pilot_started`, founder notification.
2. Hub row: `days_left`, `mrr 375 (+75 x extra)`, `engagement` keys; detail page `issues` untouched.
3. Reminders: backdate `started_at` to 31 / 61 / 76 / 91 days -> `tick()` sends exactly the due milestones once; second run sends nothing; `reminders_sent` stamped; notification types `customer_pilot_day_30..90`.
4. Extend +30 with reason -> `ends_at` +30, audit `pilot_extended` (before/after); End with reason -> org inactive, `state ended`, audit, owner login 403 with the pilot-ended message, `/auth/me` 403, contacts/messages counts unchanged; Resume -> login works again.
5. Conversion: owner `POST /billing/checkout` -> Stripe Checkout session in the sandbox (subscription mode, `trial_end = ends_at` when >= 48 h away), status still `pilot`; `apply_subscription` with a trialing then active subscription -> `trialing` -> `active`, `converted_at`, audit `pilot_converted`, founder notified. Expired pilot without a subscription stays `pilot / completed`, no Stripe customer created (no automatic conversion).
6. Guards: legacy org `/billing/checkout` 404; rep 403; paid customer `pilot/start` 409; `billing-exception` path unchanged; cron route 401 without the secret, duplicate run id acknowledged.
7. Regression: Stage 1 (14), Stage 2 (11), Stage 3 (19), P0 security (49), onboarding suites.

Frontend (testing agent, web): New Customer default pilot -> customer page step 2 pilot copy + Extend/End; Hub row + summary; owner Billing "Continue after the pilot" opens a `checkout.stripe.com` URL (not paid); ended pilot login message; QA Accept Motors (paid) and legacy qa-manager/forest unchanged.

## 7. Decisions needed before coding
A. Day-90 reminder: add it (recommended) or strictly 30/60/75 only.
B. Conversion before day 90: (recommended) Checkout with `trial_end = pilot ends_at` so the card is saved now and the first charge lands the day after the pilot (the customer keeps every free day); or start billing immediately at conversion.
C. End-pilot access: block sign-in for every user of the org (recommended) or owner-only.
D. New Customer default: Founding Partner Pilot pre-selected (recommended) with "Paid from day one" as the alternative.
E. Reminder channel: push + Alerts (existing founder channel) or also email.
