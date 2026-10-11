# Founder Acceptance Report: Phase 1 (Stages 1, 2, 3) — Simplified Pilot Customer Launch

- Date: Oct 11 2026 (walkthrough) / re-verified Oct 11 2026 (this report)
- Environment: PREVIEW only (`https://user-routing-issue.preview.emergentagent.com`). Nothing deployed. Production untouched.
- Code under acceptance: checkpoint `211857481` ("Phase 1 Stage 3 ... built and tested in preview").
- Walkthrough customer: **QA Accept Motors** (org `6acbea92a284f605698a9743`, Provo UT), brand-new pilot organization created in the Hub for this acceptance run. Owner Avery Acceptance (`qa-accept-owner@invalid.imonsocial.test`, +1 500-555-0940, Twilio test range). Second salesperson Sam Salesperson (`qa-accept-rep@invalid.imonsocial.test`).
- Stripe: owner's TEST sandbox `acct_1TZx5C0HHTIPsg1w` via the restricted key `STRIPE_BILLING_SECRET_KEY` + signed webhook `STRIPE_BILLING_WEBHOOK_SECRET` (both in preview `backend/.env`, values never printed).
- Evidence sources for every PASS below: live preview API as the founder (`GET /api/customers/{org}`, `GET /api/customers`), Mongo (`organizations.customer`, `customer_audit_log`, `stripe_events`, `users.pilot_checklist`, `contacts`, `contact_events`, `voice_notes`, `bug_reports`, `notifications`), the Stripe sandbox API (subscription, customer, invoice), the 12 screenshots in `/app/memory/acceptance/`, and the automated suites re-run today (44/44).

**Verdict in one line: GO for the founder-assisted pilot launch, once the Production Stripe checklist (section 4) is completed and the deploy sequence (section 5) is followed. NO-GO for public self-serve signup (not in scope, not built).**

---

## 1. Step-by-step results

Timestamps are UTC from the audit log / Stripe. "Automated" = proven by the pytest suite re-run today rather than clicked on QA Accept Motors.

| # | Stage | Step | Result | Evidence |
|---|---|---|---|---|
| 1 | 1 | Founder opens Hub -> **New Customer**, picks Pilot Store ($375/mo, 5 seats, 0 extra), enters owner -> customer created | **PASS** | audit `customer_created` 19:59:14; `customer.plan_key pilot_store_monthly`, `amount 375`, `seats_included 5`, `billing_status unpaid`; org `active: false`; owner `is_active: false`, dormant, no `temp_password` in the response (screenshot 08 = the form's first screen) |
| 2 | 1 | Dormant owner cannot log in, cannot "forgot password", cannot self-activate before the invite | **PASS** (automated) | `test_customer_launch_stage1.py` 14/14 today (401 login, 403 activate/request, forgot refused) |
| 3 | 2 | Founder presses **Send payment link** (hosted Stripe Checkout, mode subscription, SMS + email to the owner) | **PASS** | audit `payment_link_created` 19:59:46 + `payment_link_sent` 19:59:47; row flipped to "Payment link sent / Awaiting payment"; Stripe Checkout session carried `client_reference_id` = org id and customer metadata `organization_id`, `source customer_launch` (verified on `cus_VQJXjf6NfTFUod`) |
| 4 | 2 | Owner pays on Stripe's hosted page (test card 4242) | **PASS** | Stripe: subscription `sub_1UPSyD0HHTIPsg1w9Pw5rm4D` **active**, 1 item `pilot_store_monthly` x1 at $375.00; invoice `in_1UPSyB0HHTIPsg1w6mtUyiYb` **paid $375.00 USD**; current period end Nov 11 2026 |
| 5 | 2 | Return page `/billing/success` -> pull-confirm marks the customer Paid (works even without webhooks) | **PASS** | `billing_status active`, `subscription_status active`, `paid_at` 20:03:46, `onboarding_status paid`; audit `payment_succeeded` |
| 6 | 2 | Signed webhooks received, verified, processed once each (idempotent by event id) | **PASS** | `stripe_events`: `invoice.paid`, `checkout.session.completed`, `customer.subscription.created` all `processed: true`, org id attached, received 20:03:46; unsigned/forged/duplicate behaviour: `test_billing_stage2.py` 11/11 today |
| 7 | 1 | Founder **Activate account** (refused until paid or exception) | **PASS** | audit `account_activated` 20:06:41; org `active: true`; owner `is_active: true`; customer page step 3 green ("The company is live and the owner can be invited") |
| 8 | 1 | Founder **Invite the owner** (72 h single-use activation link, SMS + email) | **PASS** | audit `owner_invited` 20:06:43; `invite_count 1`; page shows "link sent Oct 11, 2026, expires Oct 14, 2026" (screenshot 02) |
| 9 | 1+3 | Owner opens the link, sets a password, is logged in and lands **directly on the simplified pilot Home** (no slideshow, no profile gate) | **PASS** | audit `owner_activated` 20:10:00; `onboarding_status owner_active`; founder received push + Alert `customer_owner_activated` ("Avery Acceptance activated QA Accept Motors"); fresh-owner Home state shown in screenshot 09 (0 of 5, first step highlighted) |
| 10 | 3 | Checklist step 1: Complete your profile and photo | **PASS** | `pilot_checklist.profile` 20:13:05; `users.photo_url` set |
| 11 | 3 | Checklist step 2: Complete your digital business card (title + bio) | **PASS** | `pilot_checklist.card` 20:14:13; title "Owner, QA Accept Motors" |
| 12 | 3 | Checklist step 3: Add your first contact | **PASS** | `pilot_checklist.contact` 20:14:57; `contact_events new_contact_added`; owner now has 2 contacts |
| 13 | 3 | Checklist step 4: Share your digital card (text/email to a recipient) | **PASS** | `pilot_checklist.share` 20:15:06; `contact_events digital_card_shared` |
| 14 | 3 | Checklist step 5: Record your first customer voice memo | **PASS** | `pilot_checklist.memo` 20:16:18; 1 row in `voice_notes` |
| 15 | 3 | Checklist auto-completes from real activity and collapses to "You're all set up" | **PASS** | `GET /api/pilot/checklist` -> `done 5 / total 5 / complete true`; Home shows the green banner + five tiles (screenshot 10) |
| 16 | 3 | Pilot UI restricted: tabs Home · Contacts · Messages; More = Profile & Card, Billing (owner), Invite Your Team (owner), Notifications, Settings, Send Feedback, Help, Sign out; Billing opens plan + Stripe portal button | **PASS** | screenshots 10, 12, 14, 15, 16 |
| 17 | 3 | Owner sends feedback (**Question**) from Home -> founder gets push + it appears on the customer page and the Hub row | **PASS** | `bug_reports` row category `question`, status `open`, `pilot true`, `organization_name`, `screen home` (tagged server-side); founder push "Question from Avery Acceptance · QA Accept Motors" 20:17:19; customer page QUESTIONS & PROBLEMS · 1 OPEN (screenshot 02/04); Hub row "Setup complete · active Oct 11 · 1 open issue" (screenshot 01); Bug Reports admin list (screenshot 07) |
| 18 | 1+3 | Owner invites a second salesperson (**Invite Your Team**) within the 5 included seats | **PASS** | user Sam Salesperson created 20:17:22 (role user, activation pending); customer page Seats **2/5**, "1/2 people activated"; seat limit on every creation path: Stage 1 suite |
| 19 | 3 | Founder view: Hub -> Customers row carries progress / last activity / open issues; customer page has PROGRESS & ACTIVITY (5 markers, "Active today") + QUESTIONS & PROBLEMS + STRIPE BILLING panel | **PASS** | `GET /api/customers` row: `progress 5/5`, `last_activity 20:17:18`, `issues_open 1`, `attention ["1 open issue"]`; screenshots 01, 02, 04 |
| 20 | 2 | Failed renewal policy: `invoice.payment_failed` -> Past due + 14-day grace + founder push, never auto-suspended; `invoice.paid` recovers | **PASS** (automated) | `test_billing_stage2.py` today; not triggered on QA Accept Motors (would need a Stripe test clock) |
| 21 | 2 | Cancel at period end / Resume / Billing portal link / Sync with Stripe / Add a seat (Stripe quantity + prorated invoice) | **PASS** (automated + testing agent iteration_381) | `test_billing_stage2.py`; buttons present on QA Accept Motors (screenshot 04) and left untouched so the walkthrough subscription stays clean |
| 22 | all | Legacy customers untouched: non-pilot users keep the full Home, 5 tabs, full Hub, "Report a Bug"; legacy orgs have no `customer` block so no flags; Mystery Shops / legacy Stripe variables and routes unchanged | **PASS** | testing agent iteration_382 (qa-manager, forest); `test_billing_stage2.py::legacy stripe files untouched`; 37 legacy orgs without `customer` |
| 23 | all | Automated regression today | **PASS** | `test_customer_launch_stage1.py` 14 + `test_billing_stage2.py` 11 + `test_pilot_stage3.py` 9 + `test_pilot_stage3_api_checks.py` 10 = **44 passed** (log `/app/memory/acceptance/pytest_stages.log`) |

**Result: 23/23 PASS, 0 FAIL.**

Not exercised in this walkthrough (by design of the preview environment, listed so nothing is assumed):
- Live-mode Stripe (real card, real money). Everything above ran in the test sandbox.
- Real SMS delivery to the owner. The owner's number is in Twilio's 500-555 test range (rejected on purpose); the agent used the activation / payment links from the email and the database. Production customers will have real numbers.
- Native iOS app. The walkthrough ran on the web build; the pilot screens are React Native and ship to phones with the EAS update in section 5.
- Push to a physical device. The founder account in preview has no Expo token, so both founder notifications landed in Alerts (and are recorded in `notifications`). Production forest has device tokens.

---

## 2. Screenshots (`/app/memory/acceptance/`)

| File | What it shows | Steps |
|---|---|---|
| `01_founder_hub_customers.png` | Hub -> Customers: QA Accept Motors "Pilot Store · 2/5 seats · Avery Acceptance · Setup complete · active Oct 11 · 1 open issue", pills Owner active / Paid | 17, 18, 19 |
| `02_founder_customer_page_top.png` | Customer page: Seats 2/5, People active 1, Monthly $375; the 5-step rail all green (Created, Paid through Stripe renews Nov 11, Activated, Owner invited + expiry, Owner active); PROGRESS & ACTIVITY "Setup complete · Active today"; QUESTIONS & PROBLEMS · 1 OPEN | 1, 5, 7, 8, 9, 15, 17, 19 |
| `04_founder_progress_and_issues.png` | Same page scrolled: the open Question, and the STRIPE BILLING panel (Stripe: active · renews Nov 11, Last payment $375 on Oct 11; Sync / Billing portal link / Cancel at period end / Open in Stripe) | 17, 19, 21 |
| `07_founder_bug_reports_admin.png` | Bug Reports admin list ("Manage" target) where feedback status is changed | 17 |
| `08_founder_new_customer_form.png` | Hub -> New Customer, first screen (business lookup) | 1 |
| `09_pilot_first_login_checklist_0of5.png` | What a brand-new pilot owner sees at first login: GET SET UP 0 of 5, first step highlighted, EVERY DAY tiles, tabs Home · Contacts · Messages (captured on the QA Pilot Owner Co owner, who is still at 0/5) | 9 |
| `10_pilot_home_top.png` | QA Accept Motors owner's Home after the walkthrough: "You're all set up", Digital Card / Contacts / Share / Voice Memo / Messages, "Send feedback" | 15, 16 |
| `12_pilot_more_menu.png` | Pilot More menu (owner variant with Billing + Invite Your Team) | 16 |
| `13_pilot_send_feedback.png` | Send Feedback: Question / Problem / Suggestion + one text box | 17 |
| `14_pilot_owner_billing.png` | Owner Billing: Pilot Store · $375/mo · 5 seats · Paid · renews Nov 11 · last payment; "Payment method, invoices and plan" (Stripe Customer Portal) | 16, 21 |
| `15_pilot_contacts_tab.png` | Pilot Contacts tab | 12, 16 |
| `16_pilot_voice_memos.png` | Pilot Voice Memos screen | 14, 16 |

Re-capture any time: `cd /app/memory/acceptance && set -a && . /app/frontend/.env && set +a && python3 capture.py [founder|owner]`.

---

## 3. Remaining issues, ranked

No blocking (High) issues were found.

| Rank | Severity | Issue | Impact | Recommendation |
|---|---|---|---|---|
| 1 | Medium (operational) | **Pilot customers get no texting number as part of the pilot flow.** The very first real question from the walkthrough owner was "How do I get my own texting number so customers see my dealership name?". The customer page already shows "0 with a work number · texting registration: not_started". | Messages tile works only once the founder provisions a number (Communications `/admin/org-twilio/{org}`) and A2P registration (`/admin/compliance`). | Add to the founder's post-activation playbook (provision number -> assign to owner -> start compliance) on activation day. Later: a Hub step "Give them a number". Not a code blocker for GO. |
| 2 | Medium (pre-existing) | Legacy Stripe webhook routes `/api/webhook/stripe` and `/api/stripe/webhook` keep their unsigned fallbacks (audit P2). | Outside the pilot path (`/api/billing/stripe/webhook` is signed and idempotent). Risk sits on the legacy quote / Mystery Shop flows. | Separate P2 ticket; do not mix into this release. |
| 3 | Medium (product gap) | No in-app reply to customer feedback. The founder answers by text/email; status changes happen in Bug Reports admin. | Fine for a handful of pilot customers; does not scale. | Backlog "Reply To Feedback" (one tap from the customer page -> SMS). |
| 4 | Low (cosmetic) | Each Checkout writes three identical `subscription_active` HISTORY rows (one per webhook event that confirms the same state). | Noise in the customer HISTORY list. | Skip the audit row when the status did not change. 5-line fix, can ride with the first post-launch patch. |
| 5 | Low (release hygiene) | `server.py BUILD` is still `2026-10-11.p0-security`. | `/api/health` could not prove that the new pod is live after the deploy. | Bump to `2026-10-11.phase1-pilot` as step 0 of the deploy (section 5). |
| 6 | Low | No Stripe Tax; amounts are tax-exclusive. | Sales tax on SaaS varies by state; the pilot is a founder-managed B2B motion. | Decide with the accountant before scaling past the pilot; Stripe Tax can be turned on later without code changes to the plan model. |
| 7 | Low | Checklist steps 1 and 2 both open My Profile (that is where photo, name, title and bio live). | Slight redundancy. | Leave; the second step completes as soon as title + bio are filled. |
| 8 | Info | `activation-tester` (legacy QA rep) renders the full Home instead of the simple Home. | Pre-existing, by design: the account carries a `partner_id`. | None. |

---

## 4. Production Stripe configuration checklist (live mode)

Everything below is done in the Stripe Dashboard of the same account (`acct_1TZx5C0HHTIPsg1w`, "VI Ventures Group LLC") with the **Test mode toggle OFF**, plus two secrets in Emergent Deployments. No code changes.

1. **Account ready for live charges**: business verification (KYC) complete, payout bank account added, public business name / support email / statement descriptor set (this is what shows on the owner's card statement), branding (logo + accent) for Checkout and the Customer Portal.
2. **Live restricted key** (Developers -> API keys -> Create restricted key), name it `imonsocial-billing-prod`. Permissions needed by `services/billing.py` (verified against every Stripe call in the file): Customers **write**, Checkout Sessions **write**, Subscriptions **write** (covers subscription items for seats), Products **write**, Prices **write**, Customer portal (Billing Portal configurations + sessions) **write**. Nothing else: invoice data arrives inside the signed webhook payloads, so no Invoices permission; no Webhook Endpoints, Payouts or Balance (the preview key is cut the same way and a `webhook_endpoints.list` call was refused with a permission error during this verification, as intended). Copy the `rk_live_...` once.
3. **Live webhook endpoint** (Developers -> Webhooks -> Add destination): URL `https://app.imonsocial.com/api/billing/stripe/webhook`, API version default, exactly these 6 events: `checkout.session.completed`, `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.paid`, `invoice.payment_failed`. Copy the signing secret `whsec_...`. (Leave the existing preview endpoint in test mode alone.)
4. **Secrets in Emergent -> Deployments -> Secrets** (production backend): `STRIPE_BILLING_SECRET_KEY` = the `rk_live_` key, `STRIPE_BILLING_WEBHOOK_SECRET` = the live `whsec_`. Do not touch `STRIPE_SECRET_KEY` / `STRIPE_WEBHOOK_SECRET` / `STRIPE_API_KEY` (Mystery Shops / legacy flows).
5. **Live catalog**: the three prices (lookup keys `pilot_store_monthly` $375, `pilot_seat_monthly` $75, `pilot_individual_monthly` $100) are created idempotently by lookup key. Either run `PYTHONPATH=/app/backend python tests/ensure_billing_catalog.py --dry-run` then `--live` against the live key (the script refuses a live key without `--live`), or let the first production **Send payment link** create them. Verify in Products that each price shows the lookup key and "recurring monthly".
6. **Dunning** (Settings -> Billing -> Subscriptions and emails): Smart Retries ON, "Send emails about failed payments" ON, "Send a reminder before renewal" optional. The app's own policy (Past due + 14-day grace + founder push, never auto-suspend) sits on top of these.
7. **Customer Portal** (Settings -> Billing -> Customer portal): the app creates its own configuration on first use (`billing_settings._id = stripe_portal`, metadata `app=imonsocial`) with card update, invoice history and cancel-at-period-end; just make sure the portal is enabled for the account and the business information is filled in.
8. **Customer emails** (Settings -> Emails): successful payment receipts ON so owners get Stripe's receipt; refunds ON.
9. **Smoke test on day one**: create the first real customer in the Hub, press Copy payment link, open it yourself, confirm the hosted Checkout shows "Pilot Store $375.00 / month" with the right business name, then close it without paying (the session is reused when the owner opens the texted link). Check Developers -> Webhooks shows 2xx deliveries once the owner pays.
10. **Rotate** the preview `rk_test` key if it was ever pasted anywhere outside `backend/.env` (it was not, per the Stage 2 verification: no `rk_test_` / `whsec_` strings in logs or git).

---

## 5. Production deployment and rollback procedure

**What ships**: backend (routers `customers`, `billing`, `pilot`, `bug_reports`, `auth` pilot flags, `setup_wizard new-account`, services `customers`, `billing`, `pilot`) + web + native frontend (Hub New Customer, customer page, billing pages, pilot Home/More/Feedback, login routing). No database migration (every new field lives under `organizations.customer`, `users.pilot_checklist`, `stripe_events`, `billing_settings`). Two new env vars (section 4, step 4); nothing else changes in the environment.

**Current production state (checked Oct 11 2026, read-only)**: `/api/health` build `2026-10-11.p0-security`; `/api/customers/plans` -> 401 (Stage 1 backend is already live from the owner's Oct 11 deploy); `/api/billing/me` and `/api/pilot/checklist` -> 404 (Stages 2 and 3 not live). The native app has not received a Phase 1 EAS update yet; the first `eas update` below ships Stages 1-3 together.

**Order matters**: secrets first, then backend, then frontend. Until the backend is live the new frontend screens would call routes that 404; until the secrets are in, the billing routes answer 503 and "Send payment link" fails cleanly.

0. Say GO. The agent bumps `server.py BUILD` to `2026-10-11.phase1-pilot` (one line) and re-runs the 44 tests. Nothing else changes.
1. Complete section 4 steps 1-4 (live key, live webhook, both secrets in Deployments).
2. **Save to GitHub.**
3. **Deploy** (backend + web, ~3-6 min). Verify:
   - `curl -s https://app.imonsocial.com/api/health` -> `"build": "2026-10-11.phase1-pilot"`
   - `curl -s -o /dev/null -w "%{http_code}" https://app.imonsocial.com/api/billing/me` -> `401` (route live, auth required)
   - `curl -s -o /dev/null -w "%{http_code}" https://app.imonsocial.com/api/pilot/checklist` -> `401`
   - `curl -s -o /dev/null -w "%{http_code}" -X POST https://app.imonsocial.com/api/billing/stripe/webhook` -> `400` (signature missing; `503` means the webhook secret is not loaded)
   - Stripe Dashboard -> the live endpoint -> "Send test event" (`invoice.paid`) -> 200 (acknowledged, ignored: unknown customer).
4. **Frontend**: confirm `frontend/.env` has `EXPO_PUBLIC_BACKEND_URL=https://app.imonsocial.com` (it does today), then on the Mac: `cd frontend && git pull && yarn install && eas update --branch production --message "$(git log -1 --pretty=%s)"`. No native build is needed (no native module or app version change).
5. **Owner-side smoke (production, forest@imonsocial.com)**: Hub shows the New Customer card and the Customers list; open an existing legacy org page and your own Home to confirm nothing changed for legacy accounts; create the first real customer, Copy payment link, open it, close it.
6. **First pilot customer**: Send payment link -> owner pays -> Hub row Paid -> Activate -> Invite owner -> watch the Progress & Activity card. Provision their texting number the same day (section 3, issue 1).

**Rollback (instant, no data impact)**
- Emergent chat -> **Rollback** -> checkpoint `87918e171` ("Phase 1 Stage 1: Customer Launch Workflow verified in preview"). That is the code production runs today (Stage 1 backend live, Stages 2-3 absent). Then **Deploy** again; `/api/health` goes back to `2026-10-11.p0-security`, `/api/billing/*` and `/api/pilot/*` return 404 again.
- If the frontend was already pushed: `eas update --branch production --message "rollback phase 1"` from the rolled-back checkout so phones get the previous bundle (web rolls back with the Deploy).
- Nothing to undo in Mongo: Stage 2/3 only add fields and collections that the old code ignores (`organizations.customer.stripe_*`, `users.pilot_checklist`, `stripe_events`, `billing_settings`). Legacy orgs were never written to.
- Stripe: a subscription created in live mode before a rollback keeps billing. Cancel it from the Stripe Dashboard if the customer should not be charged, or leave it and re-deploy (the app re-syncs from Stripe via Sync with Stripe).
- Secrets can stay in place; the old code never reads them.
- Deeper rollback (removes Stage 1 as well): checkpoint `afff51e84` ("before Stage 1 customer launch workflow"); only if Stage 1 itself misbehaves in production, which the Oct 11 deploy has not shown.

**Trigger rollback if**: the health build tag never flips (deploy failed), legacy users cannot open Home / Hub, `/auth/activate` fails for a new hire, or the Stripe endpoint answers 5xx on real deliveries (Stripe retries for 3 days, so a short outage loses nothing).

---

## 6. GO / NO-GO recommendation

**GO for the founder-assisted pilot launch (Stages 1-3) with these conditions:**
1. Section 4 completed (live restricted key with the listed permissions, live webhook with the 6 events, both secrets in Deployments, dunning ON).
2. Deploy order in section 5 (secrets -> Deploy -> verify -> EAS update), health tag confirmed.
3. The first real customer is walked through by the founder personally (payment link, activation, invite, first login) while watching the customer page, and their texting number is provisioned the same day.
4. Preview QA data stays in preview: nothing from `QA *` orgs exists in production, and the wipe script (`python tests/wipe_pilot_customers.py`) is never run against production.

Why GO: 23/23 walkthrough steps passed against a brand-new organization, with every state change confirmed in the database and in Stripe, not just on screen; 44/44 automated tests on the same code today; webhook signing + idempotency and the no-auto-suspend policy proven; legacy customers, Mystery Shops Stripe and all existing screens untouched (one runtime flag gates the whole pilot experience); a clean, data-safe rollback exists.

**NO-GO for public self-serve signup.** It was never in Phase 1 scope and the pieces are not there: no public plan picker, no self-serve Checkout without a founder-created customer record, no automatic access gate on unpaid/past-due accounts (by policy the founder decides), no in-app support reply, no texting-number self-provisioning, no tax handling. Keep signups founder-assisted through the Hub until a later phase decides otherwise.

**After GO, in this order**: (1) Reply To Feedback from the customer page, (2) texting-number step in the Hub for pilot customers, (3) skip duplicate `subscription_active` audit rows, (4) Customers tab inside Account Health (P4).
