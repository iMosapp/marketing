# i'M On Social: First Customer Launch Readiness Audit

Date: Oct 11 2026 (container clock). Read-only. No code changed. Evidence labels used throughout:
- **VERIFIED** = exercised today against the preview API / UI by the auditing agent.
- **TESTED EARLIER** = passed a testing-agent or pytest run in a previous session (date given), not re-run today.
- **CODE ONLY** = read in the source, never exercised. Not production-ready by this audit's standard.
- **PROD UNKNOWN** = depends on production secrets / data the agent cannot see.

---

## 1. Current-state readiness assessment

### 1.1 Super-admin creation of a company / customer account
| | |
|---|---|
| Built & working | **Onboarding Hub** `/admin/onboarding-hub` (VERIFIED renders: 7 entry cards) -> **Setup Wizard** `/admin/setup-wizard` (multi-step: org -> store -> branding -> owner user via `POST /admin/organizations`, `POST /admin/stores`, `POST /admin/users/create`). One-shot variant `POST /api/setup-wizard/new-account` creates org + store + store_manager owner (temp password), seeds user + store defaults, writes an `onboarding_clients` tracking row, sends the A2P 10DLC compliance form (text + email) and, when the `auto_provision` flag is on (it is OFF: VERIFIED `GET /admin/twilio/flags`), provisions a Twilio subaccount. |
| Where in admin | More > Account Management > Onboarding Hub; Organizations `/admin/organizations`, Stores `/admin/stores`, Users `/admin/users`, Individuals `/admin/individuals`, Pending Users. |
| Partial / disconnected | No single "Customer" object: a customer is an `organizations` row + `stores` row + users + an `onboarding_clients` row + (later) a Stripe customer, none of which reference a plan, seats or billing status in one place. `organizations.plan` is a free string. There is no status machine (lead -> paid -> invited -> active). |
| Broken / untested | `tests/test_setup_wizard.py` and `tests/test_onboarding_team_invite.py` FAIL today (12 of 80 in the sample run): they send bare `X-User-ID` (401 since the Sep 27 hardening) and one hard-coded invite code (404). They are stale tests, not proof of breakage, but it means the wizard has no passing automated coverage. |
| Manual configuration | Twilio number purchase + assignment (see 1.4), A2P submission, Resend domain, plan/price (hard-coded in code). |
| Essential before first customer | **CRITICAL SECURITY (VERIFIED today, preview):** `routers/setup_wizard.py` and `routers/team_invite.py` have zero auth dependencies and are not covered by the ownership middleware. Unauthenticated `GET /api/setup-wizard/clients` returned 18 onboarding records with names, emails and phones. Unauthenticated `GET /api/team-invite/user/{user_id}/invite-link` **mints a live store-join link** for any user id (`https://app.imonsocial.com/imos/signup?invite=...`, 90-day, multi-use). Also open: `GET /api/setup-wizard/progress/{org_id}`, `GET /api/team-invite/store/{store_id}`, `GET /api/onboarding-settings/store/{store_id}`, `GET /api/scheduler/status`, `GET /api/email/templates/{user_id}`, `GET /api/subscriptions/my-subscription?email=`. Must be closed before any paying tenant exists. |
| Can wait | White-label partner layer, partner/reseller onboarding, bulk transfer, Individuals (non-org accounts). |

### 1.2 Owner and salesperson accounts, permissions, invitations
| | |
|---|---|
| Built & working | Roles `super_admin > org_admin > store_manager > user` (`routers/rbac.py`), legacy aliases `admin`/`manager`/`salesperson` still present in data (VERIFIED: preview users by role include all seven strings). `POST /admin/users/create` -> temp password, `activation_pending`, activation **email (Resend) + SMS code** -> `/auth/activate` (request / verify / complete) -> set password -> `needs_password_change` honoured by `login.tsx` -> change-password screen. Reactivate / soft-delete / pending-user approval exist. **Jessi SMS onboarding** (Add team member with "Let Jessi onboard them by text": intro text, contact card, voice interview, write-up, photo, single-use 72 h activation link) TESTED EARLIER Sep 22 2026 (iteration_346, pytest 14/14); gated to super admins via Test Lab (`services/lab.py`, status `lab`). |
| Where in admin | Users `/admin/users` (+ `/admin/users/[id]`), Add team member sheet, Jessi Onboarding `/admin/onboarding-jessi`, Pending Users, Permission Templates `/permission-templates`. |
| Partial / disconnected | **Two invitation systems**: (a) `auth.py` activation codes/links written to `password_reset_tokens`, used by admin-created users; (b) `team_invite.py` 8-char codes (30 / 90-day, multi-use, `/imos/signup?invite=`, `/join/[code]`) used by self-serve team joins and the onboarding slideshow. Different expiry, different revoke semantics, (b) is unauthenticated (see 1.1). `PUT /admin/hierarchy/users/{id}/role` has no role dependency (CODE ONLY, needs a check). |
| Broken / untested | Team-invite pytest stale (see 1.1). Password policy is length >= 6 only (`auth.py`). |
| Manual configuration | None beyond Twilio/Resend being live. |
| Essential | Lock down `team_invite.py` + `setup_wizard.py`; pick ONE invitation path for pilots (recommendation: admin-created users + activation SMS/email, the path with the newest tests); seat limit check at invite time (does not exist). |
| Can wait | Jessi SMS onboarding as the default (keep as opt-in; it needs a sender work number and live Twilio voice), self-serve signup, pending-user approvals. |

### 1.3 Stripe: customers, subscriptions, pricing, checkout, status, invoices, cancellation, failures
| | |
|---|---|
| Built & working | `GET /api/subscriptions/plans` (VERIFIED preview + production, public). Hosted Checkout via `emergentintegrations` `StripeCheckout` with `STRIPE_API_KEY` (preview key is the Emergent sandbox `sk_test_...`; TESTED EARLIER June 2026: checkout URL returned). Quote flow: admin creates quote -> customer accepts at `/quote/accept/[id]` -> checkout -> webhook marks quote paid. Pricing UI `app/subscription/pricing.tsx`, success/cancel pages. Discount codes. Platform revenue dashboard `/admin/billing` (summary / MRR / transactions). A **second, more correct Stripe integration** exists for Mystery Shops (`services/mystery_shops.py`: raw `stripe` SDK, `Customer.create`, `Invoice.create/finalize/send`, webhook verified with `STRIPE_WEBHOOK_SECRET` when set). |
| Where in admin | Quotes `/admin/quotes`, Create Quote, Discount Codes, Billing & Revenue (owner tools). |
| **Partial / disconnected (the big one)** | The "subscription" checkout is a **one-time payment**: `emergentintegrations` `CheckoutSessionRequest` creates sessions with `mode='payment'` (VERIFIED by reading the installed library). **No recurring Stripe Subscription object is ever created.** The app-side `subscriptions` collection gets `status: "trialing"` from the status poll and nothing ever advances it. Preview DB: 0 `subscriptions`, 1 `payment_transactions` (VERIFIED). `POST /subscriptions/cancel` writes a DB flag only, never calls Stripe. No Customer Portal, no invoice list, no reactivation, no seat change, no dunning. Plans are hard-coded dicts in `routers/subscriptions.py` ($100/mo, $1,000/yr individual; store $75/user min 5; $65/user at 6+; 7/14-day trials). Quote PDF literally says "PENDING -- Payment information to be collected separately". `app/imos/billing.tsx` is a placeholder page. Partner billing / partner invoices are manual ledgers, not Stripe. |
| Broken / untested | **Webhook `/api/webhook/stripe` performs no signature verification**: `StripeCheckout(api_key, webhook_url=...)` is built without `webhook_secret`, so the library falls back to `json.loads(payload)`; anything POSTed is processed, errors are swallowed and answered `200 {"status":"received"}` (VERIFIED: an empty POST to production returns 200). Only `checkout.session.completed` is handled; no `invoice.payment_failed`, `customer.subscription.updated/deleted`; no event-id idempotency. `STRIPE_WEBHOOK_SECRET` exists in the preview `.env` but this handler never reads it. |
| Access gating | **None.** No middleware, dependency or UI banner ties app access to payment state (grep for past_due / paywall: only admin display fields). |
| Manual configuration (PROD UNKNOWN) | Whether production has a live `STRIPE_API_KEY` (PRD says "claim the Emergent sandbox into your own account"), whether a webhook endpoint is registered in the Stripe Dashboard pointing at `https://app.imonsocial.com/api/webhook/stripe`, and whether `STRIPE_WEBHOOK_SECRET` is set in production secrets. |
| Essential | A real recurring subscription (Stripe Subscription or Payment Link in subscription mode), verified webhook with the lifecycle events, billing status on the org, soft/hard access gate, Customer Portal link for invoices / card / cancel. |
| Can wait | Discount codes, quotes with PDF, partner billing, multi-currency (Dutch market plumbing exists). |

### 1.4 Company configuration: branding, phone numbers, messaging registration, campaigns
| | |
|---|---|
| Built & working | **Twilio**: platform-level SMS is LIVE through a Messaging Service, `a2p_compliant: true` (VERIFIED `GET /admin/twilio/status`). Org-scoped provisioning `/admin/organizations/{org}/twilio/*` (subaccount, number search / purchase / assign / suspend / release, audit, usage) and legacy inventory `/admin/twilio/*` with a released-number pool; UI `/admin/org-twilio/{org}`, `/admin/twilio-numbers`, `/admin/phone-assignments`. **A2P 10DLC**: tokenized client form `/a2p-onboarding/{token}` with reminders, stall detection, daily digest and an automated preflight (EIN, entity, website, privacy / terms language) TESTED EARLIER (`tests/test_compliance_onboarding.py`). **Branding**: white-label partner (logo, colours, powered-by, slug) at the partner level; store `primary_color` / `email_footer` from the wizard; per-user email brand kit. **Seeds**: new user gets 12 SMS + 8 email templates, 1 campaign ("Sold" long-term follow-up), 8 tags, 6 date triggers, review-response and social templates; new store gets tags + 8 lead-source labels + congrats-card templates. **Email**: Resend, sender `notifications@send.imonsocial.com`. |
| Where in admin | Set Up section (store profile, brand kit, messaging channels, phone numbers, integrations), Compliance `/admin/compliance`, Org Twilio, White Label. |
| Partial / disconnected | Twilio `auto_provision` is OFF and `webhook_validation` is `log` (VERIFIED). A new rep does **not** get a number automatically; an admin buys and assigns one. The actual Twilio brand / campaign submission after the compliance form is a human step ("Reviewed and ready. Submit to Twilio"). SMS sending is **not blocked** before a tenant's own A2P approval (only carrier filtering applies). Seeded store lead sources use a different schema than `lead_sources.py` (no team / assignment / webhook), so they are labels, not working intake endpoints. `seed_defaults.py` defines `DEFAULT_TAGS` twice (second wins) and its header promises 6 campaigns while 1 exists. No validation stops a seeded review-ask template from sending with an empty `{review_link}`. |
| Broken / untested | No toll-free verification flow. Store-settings screen for hours / review links not located under a predictable name (needs confirmation). |
| Manual configuration | Per tenant: buy number(s), assign to reps, run the A2P form, submit to Twilio, fill store hours / review links / website / logo, create a real lead source if they take web leads. Platform: Resend domain, `TWILIO_*`, `RESEND_*`. |
| Essential | For the pilot's six features (card, contacts, photo, voice memo, review requests, simple follow-up) a tenant needs: one assigned work number per rep (or the shared store number), review link, logo, hours. Everything else can be defaulted. |
| Can wait | Lead sources / internet leads, inventory feeds, call ladders, DNI, white-label branding, tenant-level A2P (use the platform Messaging Service for pilots if Twilio terms allow; confirm). |

### 1.5 First-login onboarding and training
| | |
|---|---|
| Built & working | Gate in `app/index.tsx`: not signed in -> login; `jessi_welcome_pending` -> `/welcome-jessi`; else `!onboarding_complete` -> `/onboarding` slideshow (skippable) -> Home. `needs_password_change` -> `/auth/change-password`. `simpleHome` (role `user`, no partner) shows the first-run Welcome Video / Welcome Tour (TESTED EARLIER June 2026). Profile Setup Banner in More (photo + bio, 2 items). Jessi voice interview builds persona / bio / card (Test Lab). Help Center with AI, Guides, Courses & Certification, script practice. Training content rewrite for the simplified app (June 2026). |
| Partial / disconnected | **Three different "finish your profile" flows** (`/onboarding` slideshow, `/auth/complete-profile` 3-step used only by the Calendar Systems brand login, `/profile-setup` 3-step from the More banner) that set `onboarding_complete` through different rules; the slideshow also stores a device-local `onboarding_done_{userId}` flag that can diverge from the server. **No 5-step checklist, no progress indicator, no "first successful action"** anywhere. Training is 100% opt-in. The More tab has 10+ permission-gated sections (1,929 lines) and Home is 1,500 lines with Jessi live voice, My 3, Do This Next, wins and a tools block: not a pilot screen. |
| Essential | One onboarding path, one checklist, a pilot Home. |
| Can wait | Courses, certification, mystery shops, interview sim as onboarding. |

### 1.6 Customer visibility, usage tracking, support
| | |
|---|---|
| Built & working | **Account Health** `/admin/account-health` (VERIFIED renders: 114 accounts, Healthy / At Risk / Critical, 30d/90d, per-account contacts / messages / touchpoints / days since login, weekly Monday slip email, TESTED EARLIER 16/16). Admin dashboard `/admin`, Hierarchy overview, Activity Feed, Team Engagement, Hot Leads, Leaderboard, Jessi Onboarding funnel, System Logs, Error Reports. **Bug reports** email + push every super admin and a Monday digest. Platform stats endpoint. Push log collection. |
| Partial / disconnected | Nothing shows **billing status, plan, seats, setup progress, invited vs activated users, open issues** together. Account Health is per user, not per company. No notification to the founder when a customer's owner activates or finishes setup. No AI-cost per tenant (usage logs exist for the Command Center / Leadership Team only). |
| Essential | One per-company row with those six columns (Phase 4 below), built as a tab inside Account Health rather than a new admin system. |

### 1.7 Tenant isolation, secure invitations, webhook reliability
| | |
|---|---|
| Built & working | `bind_identity_header` (X-User-ID must match the Bearer JWT; all `/api/admin/*` need a proven caller) and `enforce_user_ownership` (BOLA middleware over 27 resource prefixes) in `server.py`; rbac deps `require_store_access` / `require_org_access` / `require_user_access` / `bind_query_user`; login lockout per ip+email (VERIFIED today: 15-minute lockout engaged after the failing-login tests ran); password-reset rate limits; impersonation sessions; SSRF-safe fetcher; widget abuse caps. Resend webhooks verified with svix. ~1,400 lines of rbac / security tests (`test_security_hardening.py` passes today). |
| Gaps (VERIFIED unless noted) | Open routers listed in 1.1 (invite-link mint is a tenant-join hole). Stripe webhook unsigned + non-idempotent. `TWILIO_WEBHOOK_VALIDATION` defaults to `log` (spoofable inbound SMS / voice webhooks until `enforce`; PRD notes the public-URL match was never confirmed). Password minimum 6, no complexity. Scoping of contacts / messages is `user_id`-based resolved from store / org membership (fine, but every new router must opt in; the two open routers show the pattern is easy to miss). No dead-letter / retry record for Stripe or Twilio webhooks (CODE ONLY). |

---

## 2. Existing features to reuse (do not rebuild)
1. `POST /api/setup-wizard/new-account` + Onboarding Hub + Setup Wizard screens as the "Create Company" step (add plan / seats / billing fields, add auth).
2. `POST /admin/users/create` + activation SMS / email + `/auth/activate` + `needs_password_change` as the only invitation path for pilots.
3. `permissions.py` role templates + per-user `feature_permissions` + Permission Templates screen as the mechanism to hide advanced tools (add a `pilot` template; the More tab already reads these keys).
4. `services/lab.py` Test Lab (`lab` / `live`) for owner-only experiments; `OWNER_TOOLS` for founder tools.
5. `services/seed_defaults.py` for templates / tags / triggers (trim to the pilot set).
6. Mystery-shop Stripe code (`services/mystery_shops.py`, raw SDK + signed webhook) as the reference for the subscription implementation.
7. `/subscriptions/plans` + pricing page + success / cancel pages (switch the checkout to subscription mode).
8. Account Health rows + weekly alert as the base of the Founder Customer Console.
9. Compliance onboarding (A2P form, preflight, reminders) as-is.
10. Org Twilio provisioning + number pool as-is (manual step by the founder).
11. `simpleHome`, Welcome Video / Tour, Profile Setup Banner, `CaptureStorySheet` memo prompt, card share -> memo nudge (built Oct 11) as the backbone of the pilot Home + checklist.
12. Bug reports -> super-admin email / push as the support channel.

## 3. Critical blockers to onboarding a paying customer
| # | Blocker | Evidence | Fix size |
|---|---|---|---|
| B1 | Unauthenticated `team_invite.py` / `setup_wizard.py` / `onboarding_settings.py` / `scheduler_admin.py` / email templates / my-subscription | VERIFIED preview | S (1 session) |
| B2 | No recurring billing: checkout is `mode='payment'`; nothing in Stripe renews | VERIFIED (library + DB) | M-L |
| B3 | Stripe webhook unsigned, non-idempotent, handles one event, swallows errors | VERIFIED | S-M (part of B2) |
| B4 | No billing status on the company and no access gate | VERIFIED (grep + code) | M (part of B2) |
| B5 | No one-place customer record / status (lead -> paid -> invited -> active) | code | M |
| B6 | No pilot feature set: a new rep lands on the full Home / More tab | code + UI | M |
| B7 | No onboarding checklist / first action | code + UI | M |
| B8 | Production Stripe key, webhook endpoint and `STRIPE_WEBHOOK_SECRET` status unknown | PROD UNKNOWN | config |
| B9 | Twilio webhook validation in `log` mode | VERIFIED flags | config + 24 h log check |

Non-blocking but fix during the pilot: password policy (>= 8), `PUT /hierarchy/users/{id}/role` guard, seed cleanup (duplicate `DEFAULT_TAGS`, placeholder lead sources), three profile flows -> one, stale pytest suites.

---

## 4. Phase 2 design: the launch workflow (one internal admin flow)

`Create Company -> Configure Plan -> Generate Payment Link -> Confirm Payment or Authorized Trial -> Invite Owner -> Complete Setup -> Invite Reps -> First Customer Interaction -> Active`

Implemented as ONE screen: Onboarding Hub > **New Customer** (reusing the Setup Wizard form) that writes a `customers` view onto the existing `organizations` doc:

```
organizations.customer = {
  status: "created" | "awaiting_payment" | "trial" | "paid" | "owner_invited" | "setup_complete" | "reps_invited" | "active" | "past_due" | "canceled",
  plan_id, seats_included, seat_price, trial_until, authorized_trial_by,
  stripe_customer_id, stripe_subscription_id, payment_link_url,
  owner_user_id, invited_user_ids[], activated_user_ids[],
  first_customer_interaction_at, activated_at, notes
}
```
Each step is a button on the company row; the status advances from events already emitted today (user activation, first card share / contact / memo / review request / message) plus the Stripe webhook. No new admin system: the row lives in Account Health > Customers (Phase 4).

**Customer-facing pilot experience** (role `user` or `store_manager` in an org with `feature_set: "pilot"`):
- Home: 5-step checklist card (below), Do This Next, Card QR button, Text / Call / Record on the contact page. Hidden: Jessi live voice, My 3, wins, tools block.
- More tab: My Brand (card, review link), My Tools (tasks, voice memos), Team (owner only: add team member), Help. Everything else off through a `pilot` permission template; owner can enable tools per user with the existing Permission Templates screen.
- Advanced tools stay in the codebase and in `permissions.py`; nothing is deleted.

## 5. Phase 3 design: billing (smallest reliable process)
1. **One subscription per company**: Stripe Product "i'M On Social Pilot" with two Prices: base (includes N seats, e.g. 5) and an extra-seat Price (quantity = seats above N). Monthly. Trial days on the Checkout / Payment Link (14) when "Authorized trial" is chosen; otherwise card now.
2. **Payment collection**: Stripe Checkout in `mode="subscription"` (raw `stripe` SDK, already a dependency) created from the admin row ("Generate payment link") with `customer_email`, `client_reference_id = org_id`, `metadata.org_id`. The founder sends the URL (or the owner gets it inside the invitation). Optional: Stripe Dashboard Payment Link pasted into the row for the very first customers (zero code).
3. **Webhook** `/api/webhook/stripe` rewritten with `stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)`, `stripe_events` collection keyed by event id (idempotent), handlers for `checkout.session.completed`, `customer.subscription.created/updated/deleted`, `invoice.paid`, `invoice.payment_failed`; each writes `organizations.customer.status` + `billing` snapshot; failures return 500 so Stripe retries; a `webhook_failures` row per exception.
4. **Invoice visibility, card update, cancel, reactivate**: Stripe **Customer Portal** session (`billing_portal.Session.create`) from an "Billing" button for the owner (and from the founder row). Cancellation at period end and reactivation happen in the portal; the webhook mirrors them. No custom invoice UI.
5. **Failed payment**: `invoice.payment_failed` -> status `past_due`, owner push + email ("update your card") using existing `send_push_to_user` / Resend, founder alert in the console; Stripe Smart Retries do the dunning. After the Stripe retry window `customer.subscription.deleted` -> `canceled`.
6. **Billing status synchronised with access**: FastAPI dependency `require_active_billing(org)` on the login response (frontend reads `billing_state`): `trial` / `active` normal; `past_due` -> dismissible banner for 7 days; `canceled` / `unpaid` -> locked screen with "Pay now" (portal) for owners and "Ask your manager" for reps. Super admins bypass. Seat check at invite time (`POST /admin/users/create` refuses beyond `seats_included + extra_seats`).
7. **Production configuration needed (names only)**: `STRIPE_API_KEY` (live, from the owner's own Stripe account after claiming or replacing the sandbox), `STRIPE_WEBHOOK_SECRET` (from the Dashboard webhook endpoint `https://app.imonsocial.com/api/webhook/stripe` with the five events above), Price ids as env (`STRIPE_PRICE_PILOT_BASE`, `STRIPE_PRICE_PILOT_SEAT`) or a `billing_plans` collection editable in the console, Customer Portal configured in the Dashboard (allow cancel at period end, card update, invoice history). Nothing else.

## 6. Phase 4 design: five-step onboarding (non-technical rep, no training)
Backend `GET /api/onboarding/checklist/{user_id}` computed from data already written today (no new flags):
1. **Make it yours**: photo + name + title saved (`users.photo_url`, `title`).
2. **Share your card**: first `digital_card_shared` / `card_qr_shown` event.
3. **Add your first person**: first contact created by you (card share creates one automatically).
4. **Tell Jessi about them**: first voice memo on a contact (`voice_notes`), prompted by the Oct 11 card -> memo push.
5. **Ask for a review or send a follow-up**: first review request or first outbound text / scheduled follow-up.
Home (pilot) renders the card with 0-5 progress, the next step as the only gold button, and "You're set" when done; the first successful action is step 2 (share the card to one person), reachable in under a minute from a fresh login. Copy passes `no_em_dash`. The three legacy profile flows are left in place but not routed to for pilot orgs.

## 7. Phase 5 design: Founder Customer Console
Yes, the existing admin can carry it: add a **Customers** tab to `/admin/account-health` (same gate, same data loader) listing one row per organization with `customer.status`, plan / seats, billing (from the Stripe snapshot), setup progress (owner checklist %), invited vs activated users, last activity (reuse health rows), open bug reports count, and actions: Generate payment link, Resend owner invite, Open Stripe portal, Mark trial authorized, Pause. Detail = the existing org page. No second admin system.

---

## 8. Recommended minimal implementation phases, effort and credit impact
Engineering estimate = what a human developer would quote. Agent execution = expected wall-clock in Emergent sessions including testing-agent runs. Credit impact is relative (L / M / H); the agent cannot quote credit numbers; billing phases cost more because each Stripe iteration needs live test-mode round trips and a testing-agent pass.

| Phase | Scope | Eng. estimate | Agent execution | Credits |
|---|---|---|---|---|
| **P0 Security close-out** (before any customer) | Auth deps on `team_invite`, `setup_wizard`, `onboarding_settings`, `scheduler_admin`, `email` templates, `my-subscription`; disable public invite-link mint; `TWILIO_WEBHOOK_VALIDATION=enforce` after a 24 h log check; password >= 8; role-change guard; regression tests | 1-2 days | 1 session (2-3 h) | L |
| **P1 Launch workflow glue** | `organizations.customer` status + fields; New Customer screen on the Hub reusing `new-account`; step buttons; events advance status; seat count on invite | 3-5 days | 1-2 sessions | M |
| **P2 Billing** | Subscription-mode Checkout, signed idempotent webhook with 5 events, portal session, access gate + banners, failed-payment alerts, env for price ids; Stripe test-mode end-to-end | 5-8 days | 2-3 sessions | H |
| **P3 Pilot mode + checklist** | `feature_set: pilot` on org, `pilot` permission template, pilot Home, checklist endpoint + card, card -> memo nudge already done | 4-6 days | 2 sessions | M-H |
| **P4 Founder Customer Console** | Customers tab in Account Health, actions, founder alerts on activation / past_due | 2-4 days | 1-2 sessions | M |
| **P5 Cleanup (during pilot)** | One profile flow, seed cleanup, stale tests, toll-free / tenant A2P decision | 2-3 days | 1 session | L-M |
| Total | | ~17-28 dev days | ~8-11 sessions | |

Order: P0 -> P1 -> P2 -> P3 -> P4 -> P5. P0 + P1 + a Dashboard-made Payment Link already allow a founder-assisted pilot (payment confirmed by hand in the console) while P2 is built.

## 9. Production test checklist (run in production with a disposable company; nothing here touches existing customers)
1. `GET /api/admin/twilio/flags` as owner: `webhook_validation` is `enforce`; no `[TwilioSig]` warnings in the previous 24 h of logs.
2. Unauthenticated `GET /api/setup-wizard/clients`, `/api/team-invite/user/{id}/invite-link`, `/api/onboarding-settings/store/{id}`, `/api/scheduler/status`, `/api/email/templates/{id}` all return 401.
3. Stripe Dashboard: live key in production secrets, webhook endpoint registered with the five events, signing secret set; `stripe trigger checkout.session.completed` (test mode) reaches `/api/webhook/stripe` and is recorded once in `stripe_events`; an unsigned POST returns 400.
4. Create Company "Pilot Test Co" from the Hub -> row appears in Customers with status `created`.
5. Generate payment link -> pay with a Stripe test card (or real card refunded) -> status `paid` within a minute; portal opens; invoice visible; cancel at period end then reactivate; `invoice.payment_failed` via `4000 0000 0000 0341` -> `past_due`, owner push + founder alert, banner shows, lock after grace.
6. Invite owner -> activation SMS and email arrive -> set password -> change-password -> pilot Home (not the slideshow) -> checklist 0/5.
7. Owner uploads photo + title (1/5), shares card by text to a Twilio 500-555 test number (2/5, contact created 3/5), memo push arrives after 60 s, records memo (4/5), sends a review request (5/5) -> "You're set"; founder row shows setup 100%.
8. Owner invites one rep -> seat counted; a 6th seat beyond the plan is refused with a clear message.
9. Rep's More tab shows only My Brand / My Tools / Help; Account Management, Leads, Campaigns, Command Center absent; owner enables Campaigns for the rep through Permission Templates and it appears.
10. Tenant isolation: owner of Pilot Test Co gets 404 / 403 on another org's contacts, facts, invites and Twilio pages.
11. Bug report from the rep reaches the founder's email and push.
12. Delete the disposable company and Stripe test customer; confirm no residue in `organizations`, `users`, `stripe_events`.

## 10. GO / NO-GO for the first five customers
- **NO-GO today for taking money through the app**: the subscription checkout does not create a subscription, the webhook is unsigned, and two unauthenticated routers expose onboarding data and mint team-join links.
- **CONDITIONAL GO for a founder-assisted pilot after P0 (one session)**: create the company in the Onboarding Hub, bill with a Payment Link made in the Stripe Dashboard (subscription mode, trial if agreed), confirm payment by hand, invite the owner with the activation SMS / email path, buy and assign numbers manually, and watch Account Health. This collects the first real payments with zero billing code at the cost of founder time per customer.
- **FULL GO after P1-P4**: self-contained workflow, billing synchronised with access, pilot Home with the five-step checklist, one console row per customer.
