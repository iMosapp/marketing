# i'M On Social: Launch Blocker Remediation Plan (Oct 15 2026). PLAN ONLY, NOTHING IMPLEMENTED

**Inputs:**
- `SALES_READINESS_REPORT.md` (Oct 14).
- Read-only production pulls through the deployer: `deployer-agent-docs/RCA_bf277e6b-…MD`.
- A code trace.

Nothing below has been changed, deployed or published.

## 0. The launch blockers and their root causes (one line each)

| # | Blocker | Root cause (evidence) |
|---|---|---|
| B1 | **Can't take a live payment** | Production runs a sandbox key: `STRIPE_BILLING_SECRET_KEY` is `rk_test_` and `STRIPE_MODE=test`. `conversion_enabled()` correctly pauses Checkout and the portal with a 503. There's no live webhook endpoint. **Configuration only, no code.** |
| B2 | **In-app Twilio provisioning is fake in production** | There's no `settings.twilio_compliance` document, so `tenant.dry_run()` is true and *every* Twilio write is faked: subaccount, number purchase and A2P submission. The live adapter has never run against real Twilio. |
| B3 | **Dealer texts can go out under IMOS's own A2P registration** | `send_sms()` without `from_phone` falls back to `TWILIO_MESSAGING_SERVICE_SID`, which is IMOS's campaign. `pn.purchase()` buys on the **parent** account whenever the org has no real subaccount (`creds_for_org` falls back to the parent). Nothing checks whether the sender belongs to a dealership. |
| B4 | **Reps without a properly assigned, authorised number can still send** | Same code path as B3. `send_block_reason()` only acts when `enforce_ready` is on (it's off) and lets any number missing from the registry through. |
| B5 | **Jessi Mini repeats her greeting (5 of the last 10 Mini sessions)** | The client's greeting `response.create` runs **twice**. Section 3 explains. |
| B6 | Dealer managers can't see their reps' activity (P1, needed before multi-rep stores) | Pilot "More" only has Invite Your Team. You (the founder) see progress; the manager doesn't. |

**Blast radius today (PROD-READ):**
- All 4 numbered users, all 7 pool numbers and 100% of the 281 outbound texts belong to the internal **"I'm On Social"** org.
- "Rides and Dives", the only customer, has **0 numbers and 0 texts**.
- So the guards in section 2 change nothing for any existing customer.
- `SMS_SEND_ONLY_TO` and `TWILIO_MOCK_MODE` exist as production secrets but are **inert** there. The first only applies in the preview runtime; the second isn't read by any code.

---

## 1. Priority 1: Stripe live (B1). No code needed

**Already built (verified in the sandbox, Oct 11 and Oct 14):**
- Webhook `POST /api/billing/stripe/webhook`: signature-verified (unsigned or forged gets 400 in production), idempotent through `stripe_events`, handles 6 events.
- Checkout in subscription mode with org linking: `client_reference_id` + `metadata.organization_id` → `customer.stripe_customer_id` / `stripe_subscription_id` / `billing_status`.
- Seat sync, the portal (card update, invoices, cancel at period end), and the real webhook path for declined renewals and cancellations (past_due + 14-day grace + founder alert; canceled).
- The founder customer page, Hub MRR and the owner Billing screen.

**Live price mapping.** The app finds prices by lookup key, not by name, and creates them idempotently on first use:

| Lookup key | Price | Product |
|---|---|---|
| `pilot_store_monthly` | $375.00/mo, 5 seats | "i'M On Social Pilot Store" |
| `pilot_seat_monthly` | $75.00/mo | "i'M On Social Additional Seat" |
| `pilot_individual_monthly` | $100.00/mo, 1 seat | "i'M On Social Pilot Individual" |

**YOUR actions (Stripe Dashboard with Live mode ON; never paste live keys into chat or preview):**
1. Make sure the Stripe account is activated for live payments (business details, bank account for payouts).
2. **Restricted key** `imonsocial-billing-live`, with exactly these permissions:
   - Customers: Write
   - Checkout Sessions: Write
   - Subscriptions: Write
   - Products: Write
   - Prices: Write
   - Customer portal: Write
   - Everything else: None
   Copy the `rk_live_…` key.
3. **Webhook endpoint:**
   - URL: `https://app.imonsocial.com/api/billing/stripe/webhook`
   - Events: `checkout.session.completed`, `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.paid`, `invoice.payment_failed`
   - Copy the `whsec_…` signing secret.
4. **Emails and retries.** Settings → Billing:
   - Smart Retries ON.
   - Email customers about failed payments ON.
   - Successful-payment receipts ON.
   - Refund receipts ON.
5. **Secrets** (Deployments → Secrets):

   | Secret | Set to |
   |---|---|
   | `STRIPE_BILLING_SECRET_KEY` | `rk_live_…` |
   | `STRIPE_BILLING_WEBHOOK_SECRET` | `whsec_…` |
   | `STRIPE_MODE` | `live` |

   Leave `STRIPE_API_KEY`, `STRIPE_SECRET_KEY` and `STRIPE_WEBHOOK_SECRET` alone (legacy quotes and Mystery Shops).
6. **Deploy.** Pods only pick up secrets on a deploy.

**WHAT EMERGENT DOES:**
1. **Pre-flight (read-only):**
   - Confirm production has no cached `billing_settings._id="stripe_portal"` row from test mode. If one exists, the cache needs a two-line change to key it by mode.
   - Confirm 0 orgs carry a sandbox `stripe_customer_id`. Already confirmed: 0.
2. **Post-deploy:**
   - Unsigned POST → 400.
   - Dashboard "Send test webhook" → 200.
   - Founder page `billing_config` = `{mode: live, conversion_enabled: true}`, and the orange notice is gone.

**Controlled real-payment test (about 15 minutes; costs only Stripe's non-refundable fee, about $3.20):**
1. Founder → New Customer **"IMOS Billing Test"**:
   - Plan Pilot Individual ($100)
   - billing_mode paid
   - not a pilot
   - owner = your second email and phone
2. Activate → Send payment link. This creates the 3 live products and prices plus the live customer; check Dashboard → Product catalog.
3. Pay with **your own card**. Expected:
   - 3 events delivered with 200: `checkout.session.completed`, `customer.subscription.created`, `invoice.paid`.
   - Founder row: Active, $100 paid, MRR $100.
   - Owner Billing: Active, portal opens.
   - Stripe receipt email arrives.
   - Emergent reads production: one `stripe_events` row per event, `livemode: true`, processed once.
4. **Refund and cleanup:**
   - Dashboard → Payments → the $100 charge → **Refund** (full).
   - Subscriptions → **Cancel immediately** → `customer.subscription.deleted` → the app shows canceled.
   - Founder deactivates the test customer.
5. **Zero-cost alternative:** convert a Founding Partner Pilot instead. The card is saved and $0 is charged until the trial ends. This proves Checkout and the webhooks but not money movement.

**Rollback:**
- Dashboard: disable the live endpoint.
- Secrets: restore the previous test values, then Deploy. Conversion pauses again and the orange notice returns.
- Refund anything charged.
- Customer data isn't touched; `stripe_events` rows stay as the audit trail.

**Optional P1 (doesn't block the first sale):** auto-lock access after the 14-day grace or after cancellation.
- Reuse the `users.access_blocked` mechanism that ended pilots already use: a daily sweep in the existing `pilot-reminders` cron, cleared by `invoice.paid` or by founder Resume.
- About 2 hours. Today the founder alert promises an access cutoff that nothing enforces.

---

## 2. Priority 2: Twilio live provisioning (B2, B3, B4)

**Every mock/test switch that affects production Twilio:**

| Switch | Where | Production now | Effect |
|---|---|---|---|
| `twilio_compliance.mode` | Mongo `settings`; UI: Texting Compliance → mode card | **missing → `dry_run`** | All Twilio writes are fake |
| `enforce_ready` / `auto_provision` | `settings` flags; UI: Tools → Twilio Migration → Settings | off / off | No send gating; no automatic provisioning |
| `TWILIO_ACCOUNT_SID` + `TWILIO_AUTH_TOKEN` | Secrets | set | Real sends (missing would mean mock sends and dry_run) |
| `TWILIO_MESSAGING_SERVICE_SID` | Secrets | set (IMOS campaign) | Fallback sender for any send without a number |
| `TWILIO_WEBHOOK_VALIDATION` | Secrets | `enforce` | Correct |
| `SMS_SEND_ONLY_TO` | Secrets | set | **Inert in production** (preview runtime only) |
| `TWILIO_MOCK_MODE` | Secrets | set | **Inert** (not read by any code) |

Mode meanings:
- `mock` = real subaccount, real numbers and a real Trust Hub profile, with a Twilio *mock* brand and campaign: no carrier-registry (TCR) fees, can't text.
- `live` = everything real.

**Already built (reused as is):**
- Subaccount provisioning with an encrypted token.
- The full A2P state machine: secondary customer profile → A2P profile → brand → campaign → Messaging Service *inside the subaccount*.
- A poller every 10 minutes and a tenant sync every 30 minutes. They attach new rep numbers to the dealer's Messaging Service and set `messaging_ready`.
- Number purchase sets the IMOS SMS and voice webhooks.
- Inbound routing by the `To` registry; the signature token is resolved from the `AccountSid` Twilio sends (subaccount numbers validate in enforce mode).
- History is keyed by user + contact.
- The A2P onboarding form.
- `send_block_reason()` with readable reasons.

**Smallest safe changes (one backend batch, about half a day including tests).**

**S1. Sender policy for dealership orgs only.** "Dealership org" means the org has a `customer` block. Every org created from New Customer does; the internal org and legacy demo orgs don't, so their behaviour stays exactly as today.

All of it lives in one function, `tenant.sender_policy(db, from_phone, user_id, platform)`, called at the top of `send_sms()`. Texting stays allowed only when all of these hold:
- The sender has a number (otherwise the reply is "No texting number is assigned to you yet").
- The number is in the tenant registry, `assigned_user_id` is this user, and the number's org is the user's org.
- The number's `twilio_account_sid` is the org's **real subaccount** (not the parent, not `ACdry`).
- The org is `messaging_ready`, meaning its own campaign is approved.

Otherwise the result is `{"success": false, "error_code": "not_ready" | "no_number", "error": <plain reason>}`. The UI already shows send failures, and the message isn't sent anywhere.

**S2. Platform traffic stays on IMOS's Messaging Service, explicitly.**
- Add `platform=True` at the 8 call sites that legitimately send without a number: activation codes (`auth`), admin and team invites, the owner invite (`customers`), founder billing alerts, the A2P form link, the app directory and the Twilio admin test SMS.
- Add it to IMOS's own Mystery and Text Shops and courses.
- Add `user_id=` at rep call sites that lack it, such as the `scheduler` campaign sends.
- A static AST test fails the build if any `send_sms(` call doesn't pass a from-number, a `user_id` or `platform=True`.

**S3. Buy in the dealership's subaccount from the start.**
- When it's not a dry run, `pn.purchase()` refuses a dealership org whose credentials resolve to the parent: "Provision this dealership's Twilio subaccount first."
- Internal and pool purchases are unchanged.

**S4. Audit trail.** Store the `from_number` (and the account SID) on outbound message documents from now on. None are recorded today (PROD-READ).

**S5. Kill switch.** Add a `sender_policy` flag to the existing tenant flags, default ON. Turning it off with `PUT /api/admin/twilio/flags` takes effect instantly, without a deploy.

**What stays untouched:**
- Inbound handlers, existing numbers, the pool, customer records and all internal-org texting.
- No data migration.

**Tests:**
- Pytest for each rule (dealership rep with no number, parent number, unregistered number, someone else's number, ready vs not-ready org, platform pass-through, internal org unchanged, kill switch).
- The AST call-site test.
- Regression: `test_twilio_tenant`, `test_twilio_compliance`, the onboarding and pilot suites, and the disposable first-dealer walk (24 steps plus new checks: a numberless rep is blocked, an inbound reply still lands).

**YOUR actions after the guard deploy:**
1. Texting Compliance → mode **live**. That turns on real subaccounts, numbers and A2P with Twilio and carrier-registry fees.
2. Optionally turn `enforce_ready` ON. S1 already gates dealerships either way; for internal numbers outside the registry it's a no-op.
3. Have a consenting first dealer with a real EIN ready.

Optionally, run one org in `mock` first to prove the real subaccount, number and Trust Hub path without TCR fees. Its campaign can't text, and the switch to live needs a resubmit.

**Controlled live activation test (one dealer; about 1 hour, then the carrier approval wait):**
1. **Provision Twilio** → a real `AC…` subaccount appears under the parent in the Twilio Console.
2. **A2P form** → the dealer completes it → **Submit**. The poller advances the profile, then the brand, then the campaign.
3. Buy **one** number for one rep. In the Console, confirm the number sits in the **subaccount** with IMOS webhooks.
4. **Before approval:**
   - The rep's app text is **blocked** with "registration pending" and doesn't reach Twilio.
   - A text from your phone to the number **lands in the rep's thread**. That proves inbound and subaccount signature validation in enforce mode.
   - A call to the number rings the rep.
5. **After campaign approval** (days to about 2–3 weeks):
   - The number is attached to the dealer's Messaging Service and `messaging_ready` flips.
   - The rep texts your phone; status callback says delivered.
   - Your reply lands in the thread.
   - In the Console, the message appears under the subaccount and the dealer's campaign.
6. **Rollback:**
   - Mode back to `dry_run` (stops new writes).
   - Release the number or suspend the subaccount in the Console.
   - Flag `sender_policy` off only if a send path misbehaves.
   - IMOS's own numbers are never touched.

**Number transfer between parent and subaccount:** not needed with this workflow. Twilio supports it (`AccountSid` update with master credentials), but A2P status doesn't follow the number. Only build it if existing numbers ever have to move.

---

## 3. Priority 3: Jessi Realtime Mini (B5)

**Exact root cause: the Mini greeting `response.create` is sent twice in one session.** Production evidence (PROD-READ, sessions 1bc8319dc49c, fff25ee9ff71, 1799c361ce2b, plus 2 more of the last 10):
1. **No user audio ever reached the model.** The session shows two complete, byte-identical assistant rows, zero rep rows, and `tokens.audio_in = 0`. That rules out echo, noise, the listening (VAD) settings and the rep talking.
2. **Both replies were the greeting request itself.**
   - `tokens.text_in = 424`, about twice the small input of the greeting call (its per-response `instructions` plus the tool schema).
   - Per-response `instructions` replace the session instructions for that response.
   - A reply the server starts on its own, or after a rep turn, would carry the full Jessi instructions: thousands of tokens.
   - The one place that sends that payload is `onStarted()` (`useLiveJessi.ts:295-306`).
3. **`onStarted()` has no once-guard.** It's bound to **two** provider events, `session.started` (GPT-Live) and `session.created` (Realtime) (`:348-350`). When the start event reaches the client twice, everything runs twice:
   - a second greeting
   - a second `tick` / `flushTimer` interval, which leaks
   - `startedAt` is reset

   The `startedAt` reset is why the stored gap between the two greetings looks impossibly short (123–473 ms): greeting #2's timestamps are measured from the second start.
4. **The same double-fire, caught by the provider.** Two other sessions stored "Conversation already has an active response in progress": the second request arrived while the first was still generating, so it was rejected and nothing was heard.
5. **Why GPT-Live is immune.** Its greeting is `session.instructions.append` with the fixed `event_id: 'greet_1'`; a duplicate doesn't create a second spoken reply. 0 of 5 GPT-Live sessions start with a doubled opening.
6. **Not a regression.** Nothing in the voice code changed after the Oct 13 fix. The defect is intermittent: 5 of 10 Mini sessions, 0 delegations involved.

**What isn't known yet:** whether the provider sends two start events or the native data channel delivers one message twice. The fix doesn't depend on which, and the trace below will name it.

The duplicated mid-call answer (b924f52d9c64) fits the same family: a duplicated `response.done` would run the follow-up after a tool call twice.

**Smallest correction (frontend JS through an OTA, plus about 10 backend lines):**

| Fix | Where | What it does |
|---|---|---|
| F1 | `useLiveJessi.ts` | `onStarted()` runs once per connection (`startedRef` reset in `connect`) |
| F2 | `onMessage` | Ignore any provider event whose `event_id` was already seen this connection (bounded set) |
| F3 | `handleDelegation` | Handle each `call_id` once |
| F4 | client + `record_events` | Store a `trace` (first 60 provider event types with ids, every `response.create` the client sends, duplicate count) plus the app build and OTA update id on the session |

Turn-taking stays as is: no listening (VAD), prompt or engine changes. Arming listening at playback end (`output_audio_buffer.stopped`) stays an option only if the trace later shows the greeting being cut off.

**Measurable regression tests:**
- **New pure script** `scripts/check-mini-opening.ts`, same style as `check-mini-captions`, sharing a small pure helper. Expected results:

  | Scenario | Expected |
  |---|---|
  | `session.created` twice | exactly 1 greeting request, intervals created once, `startedAt` not reset |
  | `session.created` + `session.started` | 1 |
  | Same `event_id` delivered twice | handled once |
  | Duplicated `response.done` with a tool call | 1 tool result + 1 `response.create` |
  | GPT-Live path | unchanged |
- **Backend:** `test_live_voice` plus a new test that `trace` events are stored and capped.
- **Production metric** (read-only script the deployer can run):

  | Measure | Baseline Mini | Baseline GPT-Live |
  |---|---|---|
  | Doubled opening | 5/10 | 0/5 |
  | Identical neighbouring assistant rows | — | — |
  | `active_response` errors | 2/10 | — |
  | `trace.dups` | — | — |

**Acceptance on the iPhone (comparison against GPT-Live):**
- **Runs:** 10 Mini-only calls and 10 Live-first calls. Live-first needs premium seconds available; all 10 recent Mini sessions were premium_cap fallbacks.
- **Script, per call:** greeting, "who should I call today", look up a person, draft + confirm a text, interrupt mid-answer, 30 s of silence.
- **Pass, Mini:**
  - doubled opening 0/10
  - no identical neighbouring answers
  - every interruption stops her
  - the text is read back before sending
- **Pass, GPT-Live:** unchanged (0/10).
- **If the guard catches a duplicate,** `trace.dups` > 0 proves the guard worked, and it names the source.

---

## 4. Priority 4: Onboarding (B6 + acceptance)

**Already verified:** the disposable 24-step walk, 24/24 on Oct 14 (founder → owner → rep → contact → card share → inbound reply → campaign enrollment). It will be:
- moved from `/tmp` into `backend/tests/acceptance_first_dealer.py` (preview only, wipes itself);
- extended with the new checks (numberless rep blocked, My Team scoped);
- re-run after every batch.

**Minimum manager visibility, "My Team" (about 2–3 hours, reuses `services/pilot.py`):**
- **Endpoint:** `GET /api/pilot/team`.
  - Who: the pilot owner or manager, scoped to their own org (a store_manager sees only their own store).
  - Read-only, counts only, no message content.
  - Per rep: name, activated (last sign-in), setup N/5 (`pilot_checklist` stamps), texting number (none / registration pending / ready), last 7 days (contacts added, cards shared, texts sent), last activity.
- **UI:** one "My Team" row in the owner's pilot More, opening a single list screen.
  - No new tab, no toggles; reps don't see it.
  - Simplified dashboard preserved.
- **Tests:** pytest for scoping (own org only, 403 cross-org, rep 403) and the acceptance walk.

---

## 5. Deployment order

| Step | What | Who | Deploy / OTA |
|---|---|---|---|
| 1 | **Stripe live config** → Deploy → controlled $100 charge + refund (or the $0 pilot conversion) | You (config, card) + Emergent (pre-flight, verification) | Deploy (secrets only) |
| 2 | **Twilio guard batch S1–S5** in preview + full regression | Emergent | — |
| 3 | Deploy the guard → verify internal texting unchanged (your send and reply) → set mode `live` → controlled dealer activation | You + Emergent | Deploy |
| 4 | **Mini fix F1–F4** + **My Team** in preview + tests | Emergent | — |
| 5 | Deploy backend (trace + My Team) → **one OTA**, which also carries MMS Stage 1 ("Mark Handled", photo retry) → iPhone script | You publish the OTA | Deploy + OTA |
| 6 | First-dealership acceptance checklist (section 6) | You + dealer | — |

Steps 1 and 2 can run in parallel. The Twilio approval wait in step 3 overlaps steps 4–6.

**Scope and risk:**

| Item | Emergent effort | Your effort | Risk | Main mitigation |
|---|---|---|---|---|
| Stripe live | about 1 h (checks) | 45 min config + 15 min test | Low (config only; rollback = secrets + deploy) | Controlled charge, then refund |
| Twilio guard | about 0.5 day | — | **Medium** (touches every SMS send) | Only applies to dealership orgs; AST call-site test; kill-switch flag; 0 customer numbers today |
| Twilio live mode | — | Mode switch + dealer data | Medium (real fees, carrier review) | One dealer, one number; mode back to `dry_run` |
| Mini fix | about 3 h | 20 iPhone calls | Low (client guards only) | Trace proves the guard worked |
| My Team | about 3 h | — | Low (read-only) | Scoping tests |

---

## 6. First-dealership acceptance checklist (single end-to-end run)

1. ☐ **Billing.**
   - Founder → New Customer: plan, seats, billing mode (Founding Pilot, exception, or paid).
   - If paid: payment link → the dealer pays → founder row Active/Trialing → receipt arrives.
2. ☐ **Activate account** → Send owner activation link.
   - The owner signs in on iPhone and gets the Face ID offer.
   - The 0/5 checklist shows; pilot Home and More show.
3. ☐ **Texting setup.**
   - Provision Twilio (real subaccount) → A2P form → dealer completes → Submit.
   - Buy one number per rep **in the subaccount**.
4. ☐ **Reps.**
   - The owner invites each rep. Each rep activates with the texted code and signs in.
   - Their number shows as "registration pending". Sending from the app is blocked with a clear message.
5. ☐ **Day-one use without registration.**
   - Profile photo, title and bio (steps 1–2).
   - Add a customer (3).
   - Share the card by Messages or QR (4).
   - Record a voice memo (5).
   - An inbound text to the rep's number lands in the thread; calls ring.
6. ☐ **Manager.** The owner opens **My Team** and sees each rep's setup N/5, number status and last activity.
7. ☐ **Approval day.**
   - `messaging_ready` turns on. The rep texts the customer from the app → delivered.
   - The customer replies → lands in the rep's thread.
   - Enroll that customer in a campaign.
8. ☐ **Jessi.**
   - Text Jessi answers in the thread; a photo-only message gets the safe reply plus an alert to a human.
   - Live Jessi stays off for customers until the Mini iPhone script passes.
9. ☐ **Week one.**
   - Founder watches the customer page (Setup N/5, attention flags, feedback).
   - Emergent runs the read-only production checks (stripe_events, texts sent from the dealer's numbers, Mini duplicate metric).
