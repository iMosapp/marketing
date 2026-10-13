# RELEASE GATE: Founding Partner Pilot (preview, Oct 11 2026)

Scope: final gate before the owner approves deployment. Nothing deployed, no new features. Evidence: `tests/release_gate_founding_pilot.py`
(re-runnable, 44 checks, log `/app/memory/release_gate_founding_pilot.log`), pytest suites (pilot 10/10, Stage 2 11/11, Phase 1 regression 158/158),
read-only production probes.

## 0. Verdict

**GO.** 43/44 gate checks pass; the one non-pass is environmental (the sandbox restricted key has no "Test Clocks: Write", so the
scheduled first charge was proven with Stripe's own `trial_end=now` instead of a clock advance; same invoice and charge path, see 3.3).

**Genuine launch blockers: none in the code.** Two production settings must exist on deploy day or a feature silently does nothing:
1. `WEBHOOK_CRON_SECRET` in Deployments > Secrets (same value as preview `backend/.env`). Without it the daily `pilot-reminders` cron gets 401
   and no day-30/60/75/90 reminder is ever sent. Needed NOW (complimentary pilots start the clock on day one).
2. Live Stripe (`STRIPE_BILLING_SECRET_KEY` live restricted key + `STRIPE_BILLING_WEBHOOK_SECRET` live endpoint). NOT needed to launch
   complimentary pilots; needed before the first owner taps "Continue after the pilot" (the button is hidden until the key exists, and the
   founder's "Send continue link" answers 503 "Billing is not configured on this server" until then). Details in section 4.

Not blockers, noted: founder gets no Alert when a converted customer's FIRST real charge succeeds (only at conversion, at failure, and at
recovery; by Stage 2 design, visible as `payment_succeeded` in the customer History); `access_block` cache is per pod with a 20 s TTL, so on a
second pod an ended pilot's existing session can live up to 20 s longer (sign-in is refused immediately everywhere).

## 1. `routers/database.get_db()`: nothing changed in production code

- `git diff 87918e171 -- backend/routers/database.py` (production checkpoint) = 0 lines; `git diff HEAD` = 0 lines. The checkpoint message
  of commit aa652690d says "adjustments in routers/database.get_db()": that wording is wrong. The only change is `backend/tests/conftest.py`:
  a module-scoped autouse pytest fixture that resets the module-level `_client/_db` between TEST MODULES, because several test modules own
  their own `asyncio.new_event_loop()` and a Motor client created on module A's loop cannot be used from module B's loop. Pytest never runs
  inside the server process; the server is untouched.
- Production request handling: uvicorn runs one event loop per worker; `get_db()` lazily creates ONE `AsyncIOMotorClient` per process
  (`maxPoolSize 50, minPoolSize 5, maxIdleTimeMS 45000, retryWrites/Reads`) on first use and caches it. Every request, every FastAPI
  `BackgroundTasks` job (cron handlers hand the work to `background.add_task`, which runs on the same loop after the response) and every
  `asyncio.create_task` in the app share that loop and that client. Stripe calls go through `asyncio.to_thread` (blocking SDK in a worker
  thread, Motor is never touched from that thread). No code path in the pilot work (or anywhere in `backend/` outside one-off scripts) calls
  `asyncio.new_event_loop()` / `run_until_complete`.
- Runtime evidence (P1): 80 concurrent requests (customers list/detail as founder, owner billing, owner checklist, 16 secret-authenticated cron
  ticks) in 40 threads -> 80 x HTTP 200 in 7.4 s; Mongo `serverStatus.connections.current` 15 before -> 23 after (pool grew by 8 under the
  burst, well under the 50 cap, idle connections close after 45 s); backend logs: 0 matches for "different loop" / "event loop is closed";
  all 16 cron ticks recorded `finished_at` in `cron_runs` (background work completed on the server loop).

## 2. End-to-end Stripe sandbox conversion (P2, real hosted Checkout, card 4242)

| Step | Result |
|---|---|
| Founder creates "QA FP Gate Motors" (Pilot Store + 1 seat, Founding Partner Pilot), activates with no payment, invites; owner activates through the link | `billing_status pilot`, `pilot_program active`, `started_at` = owner activation, `ends_at` = +90 d (Jan 9 2027), no Stripe object of any kind |
| Owner Billing before authorizing | `can_continue true`, `portal_available false`, no bare checkout link; **price $450/mo** (375 + 1 x 75); **first billing date = pilot end** (2027-01-09) |
| Owner POST `/api/billing/checkout` | hosted Checkout URL; status stays `pilot`; Stripe customer created, no subscription |
| Hosted Stripe page | "89 days free" · "Then US$450.00 per month starting January 9, 2027" · custom text "Nothing is charged today..." |
| Card 4242 entered, "Start trial" | redirect to `/billing/success`; webhook `checkout.session.completed` + `customer.subscription.created` + `invoice.paid` ($0) arrived live, signed, processed once each |
| Subscription | `trialing`, **`trial_end` == pilot `ends_at` to the second**, items `pilot_store_monthly x1` + `pilot_seat_monthly x1`, `default_payment_method` saved |
| No immediate charge | exactly one invoice: the $0 trial invoice (`amount_due 0`, `amount_paid 0`, `billing_reason subscription_create`), customer balance 0 |
| App state | `billing_status trialing`, `pilot_program.state converted` (`converted_via webhook`), `current_period_end` = trial end; audit `... > payment_link_created > owner_checkout_opened > subscription_trialing > pilot_converted` |
| Founder notification | Alert `customer_pilot_converted`: "QA FP Gate Motors chose to continue after the pilot. Payment method saved through Stripe. The first charge lands on 2027-01-09. Nothing to do." |
| Founder views | row `mrr {450, scheduled, first_charge_on 2027-01-09}`, Hub row trialing/converted; owner Billing: portal available, Continue gone |

The converted org is left in preview for the owner to look at: **QA FP Gate Motors** 6acc107efb4f03be5b390788, owner
qa-fp-gate-owner-1c4b@invalid.imonsocial.test / (password in memory/test_credentials.md, not in the repo) (sandbox subscription trialing until Jan 9 2027; `wipe_pilot_customers.py --prefix "QA FP Gate"` removes it and the Stripe customer).

## 3. Scheduled first charge (P3)

3.1 Preferred scenario, Stripe test clock: **not possible with the current sandbox restricted key** (Stripe answered `Permission denied ... Enabling
Test Clocks Write ('billing_clock_write')`). Add that permission to the TEST key only and re-run the gate script; it then creates a clock-bound
customer, a trialing subscription with the same items/metadata as our Checkout, advances the clock one hour past `trial_end`, and checks the
`subscription_cycle` invoice. (Live keys never need it: test clocks do not exist in live mode.)

3.2 Executed fallback, Stripe `trial_end=now` on a trialing subscription with a saved card (Stripe's own documented way to end a trial early):
Stripe created and paid the first invoice **$450.00 exactly once** (`subscription_update`), subscription `active`; our webhook writer moved the
customer `trialing -> active`, stamped `paid_at`, `last_payment_amount 450`, cleared grace; audit `pilot_converted > subscription_trialing >
subscription_active > payment_succeeded`; founder row `mrr {450, actual}`; re-delivering the same paid invoice changed nothing.

3.3 Why this is sufficient: the invoice/charge path Stripe runs at `trial_end` is the same whether the time arrives naturally, by clock advance,
or by `trial_end=now`; what differs is only `billing_reason`. The subscription parameters that matter (`trial_end` value, items, saved payment
method, `payment_method_collection always`) were verified on the real Checkout subscription in P2.

## 4. Never charged without authorization (P4) and reminders (P5)

- Pilot that never authorizes: backdated to day 91 -> `tick()` marks `completed`, access stays ON (`/billing/me` 200), `billing_status pilot`,
  NO Stripe customer exists for the owner's email, no subscription; founder flag "Pilot period over · decide: continue, extend or end", MRR kind
  `potential` (never counted as revenue).
- Pilot that opened Checkout and abandoned it (QA FP Demo Motors): Stripe customer exists with **0 invoices, 0 subscriptions**; the Checkout
  session expires after 24 h; `sync_from_stripe` only touches sessions of `awaiting_payment` customers, so a pilot's status never flips.
- Reminders: days 30/60/75/90 each sent exactly once (atomic `$addToSet` claim per milestone), a second `tick()` sends nothing; per milestone:
  push attempted + in-app Alert row (`customer_pilot_day_N`, link to the customer) + Resend email (4 message ids, Resend `last_event: sent`
  for each; the QA recipient is an @invalid address that bounces by design). `reminders_sent [30,60,75,90]`, `reminder_log` 4 entries with
  per-channel outcome, audit `pilot_reminder_sent` x4, `pilot_completed` x1. Push delivery to a phone cannot be observed in preview (the
  founder has no Expo token here); it is the same `send_push_to_user` helper every founder alert has used since Stage 2.
- Cron: `.emergent/crons.yml pilot-reminders` daily 15:00 UTC -> `POST /api/cron/pilot-reminders`; 401 without the secret, duplicate
  `X-Webhook-Id` acknowledged as duplicate, work in a BackgroundTask (ack < 1 s).

## 5. Ended pilot blocks an EXISTING session (P6)

Before End: bearer routes 200, cookie session restore `GET /auth/me` 200, biometric `POST /auth/refresh` 200. After End (founder, reason):
same bearer token -> 401 on `/billing/me`, `/contacts/{uid}`, `/pilot/checklist`; cookie restore 401; refresh 401; new login 403 "Your Founding
Partner Pilot with I'm On Social has ended. Text or email Forest to continue; your contacts and messages are safe." Users, store, contacts
untouched; org `active false`. Resume: the same old token works again without a new login. Mechanism: `server.py bind_identity_header` asks
`access_block.is_blocked` for every authenticated caller (one indexed lookup, 20 s cache, invalidated on the pod that ended/resumed).

## 6. Production prerequisites

Production today (read-only probes Oct 11 2026): `/api/health` build `2026-10-11.p0-security`; Stage 1 live (`/api/customers/plans` 401);
`/api/billing/me`, `/api/pilot/checklist`, `/api/cron/pilot-reminders` all 404 (Stages 2, 3 and the pilot ship together with this deploy).

| When | What | Why |
|---|---|---|
| NOW (with the deploy) | `WEBHOOK_CRON_SECRET` in Deployments > Secrets, same value as preview `backend/.env` | daily reminders; otherwise 401, nothing sent, nothing else affected |
| NOW (verify present) | `RESEND_API_KEY`, `SENDER_EMAIL`, `APP_URL=https://app.imonsocial.com`, `OWNER_EMAIL=forest@imonsocial.com` | reminder emails + links; activation emails already use Resend in production |
| NOW | `frontend/.env EXPO_PUBLIC_BACKEND_URL=https://app.imonsocial.com` (already set) before `eas update` | gets baked into the OTA bundle |
| BEFORE the first paid conversion (not needed to start complimentary pilots) | `STRIPE_BILLING_SECRET_KEY` = LIVE restricted key with: Customers write, Checkout Sessions write, Subscriptions write, Products write, Prices write, Billing Portal (configurations + sessions) write. Nothing else (no Charges, no Invoices, no Test Clocks) | the app only calls those endpoints |
| BEFORE the first paid conversion | `STRIPE_BILLING_WEBHOOK_SECRET` = signing secret of a LIVE endpoint `https://app.imonsocial.com/api/billing/stripe/webhook` with exactly: `checkout.session.completed`, `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.paid`, `invoice.payment_failed` | conversion, first charge, failures |
| BEFORE the first paid conversion | live catalog: `cd backend && PYTHONPATH=. python tests/ensure_billing_catalog.py --dry-run` then without `--dry-run` against the live key (creates the 3 lookup-key prices once; idempotent). The app also creates them lazily on the first Checkout, this just makes it deliberate | prices by lookup key |
| BEFORE the first paid conversion | Stripe Dashboard: Smart Retries / dunning on for failed payments; Customer Portal is configured by the app on first use | failed-payment policy |
| Until Stripe is configured | owner's "Continue after the pilot" is hidden (`can_continue false`), founder's "Send continue link" -> 503 toast "Billing is not configured on this server"; pilots, reminders, extend/end/resume work fully | safe partial launch |

## 7. Production release checklist

Pre-flight (preview, done): pilot suite 10/10, Stage 2 11/11, regression 158/158, gate 43/44, `/app/memory/FOUNDING_PILOT_REPORT.md`.

1. Owner says GO. Agent bumps `backend/server.py BUILD = "2026-10-11.phase1-pilot"` (one line; the only code change on deploy day).
2. Owner adds `WEBHOOK_CRON_SECRET` in Deployments > Secrets (and, if going straight to paid conversions, the two live Stripe secrets).
3. **Save to GitHub** (checkpoint = rollback target for the new code).
4. **Deploy** (backend + web + crons sync from `.emergent/crons.yml`). Wait for "Clean".
5. Backend smoke (anonymous, read-only):
   - `curl -s https://app.imonsocial.com/api/health` -> `"build": "2026-10-11.phase1-pilot"`
   - `curl -s -o /dev/null -w "%{http_code}" https://app.imonsocial.com/api/customers/plans` -> 401
   - `curl -s -o /dev/null -w "%{http_code}" https://app.imonsocial.com/api/billing/me` -> 401 (was 404)
   - `curl -s -o /dev/null -w "%{http_code}" https://app.imonsocial.com/api/pilot/checklist` -> 401 (was 404)
   - `curl -s -o /dev/null -w "%{http_code}" -X POST https://app.imonsocial.com/api/cron/pilot-reminders` -> 401 (was 404; the platform's call with the secret returns 200 at 15:00 UTC; check Deployments > crons / `cron_runs` the next day)
   - `curl -s -o /dev/null -w "%{http_code}" -X POST https://app.imonsocial.com/api/billing/stripe/webhook` -> 503 until the live webhook secret is set, 400 after (unsigned)
6. Owner smoke (signed in as forest@imonsocial.com on the web app): Hub -> Customers list renders with the summary line; New Customer form shows the BILLING choice with Founding Partner Pilot pre-selected; open any existing customer -> page renders (legacy orgs untouched: open a normal org page and a rep's Home).
7. Frontend: `cd frontend && git pull && yarn install && eas update --branch production --message "$(git log -1 --pretty=%s)"` (login screen message, New Customer form, customer page, owner Billing, pilot Home banner are frontend changes). Re-check step 6 on a phone after the OTA lands.
8. First real pilot: create the customer with Founding Partner Pilot, Activate, Invite; after the owner activates, confirm the Hub row reads "Pilot · 90 days left" and the customer History has `pilot_started`.
9. Before the first "Continue": complete the Stripe rows in section 6, then run one $0 conversion on a founder-owned test customer if desired (live Checkout with a real card creates a trialing subscription with no charge; cancel it from the portal before trial end).

Rollback (instant, no data impact): chat -> **Rollback** -> checkpoint `87918e171` (the code production runs today; Stage 1 live, Stages 2-3 absent) -> **Deploy**; `/api/health` returns to `2026-10-11.p0-security`, `/api/billing/*`, `/api/pilot/*`, `/api/cron/pilot-reminders` return 404 again. If the OTA was already pushed: `eas update --branch production --message "rollback phase 1"` from the rolled-back checkout. Data written by the pilot (`organizations.customer.pilot_program`, `users.access_blocked`, audit rows) is additive and ignored by the old code; a pilot org left `active: false` by End would need `organizations.active` set back by hand (or Resume before rolling back). A live Stripe subscription created before a rollback keeps billing on Stripe's side; cancel it in the Dashboard if needed.

## 8. Post-launch backlog (owner's decision: not before launch)
- Day-90 Decision Card (one-tap Continue / Extend / End on the Hub when a pilot period is over)
- Owner Check-In Text (prewritten check-in SMS offered with the day-30 and day-60 reminders)
- Pilot Scoreboard (every pilot's days left, setup progress and engagement side by side)
- Founder Alert on a converted customer's first successful charge (today: audit row only)
- Test-clock variant of the gate once the sandbox key gets "Test Clocks: Write"
