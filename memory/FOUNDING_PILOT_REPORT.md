# Founding Partner Pilot: founder walkthrough + GO/NO-GO (Oct 11 2026, PREVIEW ONLY, nothing deployed)

Plan it implements: `/app/memory/FOUNDING_PILOT_PLAN.md` (decisions A-E taken as approved: day-90 reminder YES, early conversion = card saved now + first charge the day the pilot ends, End blocks every user of the org, New Customer defaults to the pilot, reminders by push + Alerts + email).

## 1. Result in one line
**GO for preview acceptance.** 10/10 pilot tests, 11/11 Stage 2 billing tests, 158/158 regression (Stage 1, Stage 3, P0 security, onboarding suites), and every founder / owner web flow walked by hand on the demo customers. Paying customers, legacy accounts and the Stripe webhook path behave exactly as before. Two small defects found during the walkthrough were fixed and re-verified (section 4).

## 2. What the founder sees (demo data, re-seed with `tests/seed_founding_pilot_demo.py`)
| Step | Where | Verified |
|---|---|---|
| New Customer form defaults to **Founding Partner Pilot** ("90 complimentary days from the day the owner activates. No card, no Stripe...") with **Paid from day one** underneath | Hub -> New Customer | screenshot |
| Customer created with `billing_status pilot`, agreed pricing recorded ($375 + $75 x extra), no Stripe object of any kind | API + Mongo | pytest 1 |
| **Activate** works with no payment and no exception; Invite sends the activation link; pilot stays "Not started" | /admin/customers/{org} (QA FP Demo Fresh) | walkthrough (audit rows account_activated, owner_invited) |
| Owner activates through the link -> clock starts once: `started_at`, `ends_at = +90 d`, state active, audit `pilot_started`, founder Alert "...their 90-day pilot ends Jan 9" | activation link | pytest 2 (later logins never move the clock) |
| Hub: summary "3 paying · $1,200 MRR · 2 pilots · $825 potential MRR"; row "Pilot · 90 days left · Setup 0/5 · active Oct 11 · $450 potential" | /admin/onboarding-hub | screenshot |
| Customer page: stats Seats / People active / **Potential MRR** / **Pilot: N days left** / People active (7d); step "Plan and pilot" with day N of 90; Progress & Activity with ENGAGEMENT (7-day and all-time contacts, shares, memos, texts, sign-ins); FOUNDING PARTNER PILOT panel: Send continue link, Copy continue link, Extend, End, Check Stripe | /admin/customers/{org} | screenshot |
| **Extend** (+30/60/90 + reason >= 5 chars) moves `ends_at`, audit `pilot_extended` with before/after, never re-sends passed reminders | pilot-extend sheet | walkthrough + pytest 4 |
| **End** (reason) -> org inactive, every user blocked: login 403 with "Your Founding Partner Pilot with I'm On Social has ended. Text or email Forest to continue; your contacts and messages are safe.", every API call of an existing session 401, contacts / users / store counts unchanged, Hub flag "Pilot ended" | pilot-end sheet, owner login | walkthrough (screenshot of the login message) + pytest 4 |
| **Resume** (reason) -> access back, state active, audit `pilot_resumed` | pilot-resume sheet | walkthrough + pytest 4 |
| Reminders at pilot days 30 / 60 / 75 / 90: one push + one Alert + one email each, claimed atomically so they never repeat; day 91 -> state completed, access ON, Hub flag "Pilot period over · decide", NOTHING in Stripe (asserted: no Stripe customer exists for the owner's email) | cron `pilot-reminders` daily 15:00 UTC -> `POST /api/cron/pilot-reminders` (secret + run-id dedup) | pytest 3 + 4 (backdated 31/61/76/91 days) |

## 3. What the pilot owner sees
| Step | Where | Verified |
|---|---|---|
| Home = pilot Home (`home-pilot`), no banner while > 14 days remain | Home | screenshot |
| Billing: "Pilot Store · $450/mo · Founding Partner Pilot · 120 days left · complimentary until Feb 8, 2027", button **Continue after the pilot**, no portal / no bare checkout link | /settings/billing | screenshot |
| Terms screen before authorizing: price, "First charge: Feb 8, 2027, the day your complimentary pilot ends. Nothing is charged today.", cancel-before-then line, Not now | billing-me-terms | screenshot |
| **I authorize billing from Feb 8, 2027 · Save card on Stripe** -> real Stripe sandbox Checkout: "Try i'M On Social Pilot Store and 1 more · 119 days free · Then US$450.00 per month starting February 8, 2027", custom text "Nothing is charged today..." | checkout.stripe.com | screenshot (checkout NOT completed) |
| Status stays `pilot` until Stripe confirms; the open session is reused; founder audit `owner_checkout_opened` | API | pytest 5 |
| After the card is saved: subscription `trialing`, `pilot_program.state converted`, audit `pilot_converted`, founder Alert "X chose to continue after the pilot. The first charge lands on <date>"; Stripe's $0 trial invoice is recorded as `trial_invoice`, not a payment; first real invoice at `trial_end` | webhook writer | pytest 6 (real sandbox subscription with `trial_end`) |

## 4. Defects found and fixed in this session
1. **Test harness** (`tests/conftest.py`): `routers/database.get_db()` caches one Motor client per process while many test modules own their own asyncio loop -> "Future attached to a different loop" when two modules run together. Fixed with a module-scoped autouse fixture that resets the cached client; the whole Phase 1 regression now runs in one pytest process (158 passed) and `test_pilot_program.py` + `test_billing_stage2.py` pass together (21 passed). Backend code untouched.
2. **Login screen** (`app/auth/login.tsx`): every 403 was rendered as "Your account is not active. Please contact your administrator." The backend already sent the pilot-ended sentence; the screen now shows it when the detail mentions the Pilot (other 403s unchanged).
3. **Owner Billing** (`services/billing.owner_summary`): after opening (not finishing) Checkout, a Stripe customer exists, so the "Payment method, invoices and plan" portal button appeared for an unconverted pilot. `portal_available` is now false while `billing_status == pilot`.

## 5. Guarantees re-checked
- Paid customer QA Accept Motors: customer page shows the Stripe BillingPanel (no pilot panel), owner Billing `active · Pilot Store · $375`, portal available, no Continue button, `pilot: null`. Subscription left ACTIVE.
- Legacy manager qa-manager logs in normally, no pilot flags, no block.
- Pilot routes are super_admin only (rep 403, store manager 403, partner org admin 403 for `billing_mode founding_pilot`), `/billing/checkout` 404 for legacy orgs, `pilot/start` 409 for a Stripe-paying customer, `billing-exception` path unchanged.
- No code path creates a subscription, charges a card or converts a pilot without the owner completing Stripe Checkout themselves (or the founder's explicit "Send continue link" leading to the same Checkout).

## 6. Not built (unchanged from the plan)
Owner-facing "cancel before the first charge" is the Stripe portal after conversion (available once `trialing`); no Stripe Tax; retention list "Ended pilots older than 12 months" is a Hub text line only (deletion stays manual); the founder reminder email goes to `customer.created_by` (forest) via Resend.

## 7. Ship list (when the founder says GO for production)
Save to GitHub -> Deploy (backend + cron) -> run eas update. Production prerequisites are the same as the Phase 1 acceptance report (live restricted Stripe key with Checkout/Subscriptions/Customers/Prices/Billing Portal write, live webhook with the 6 events, both secrets in Deployments, `WEBHOOK_CRON_SECRET` set for the daily cron).
