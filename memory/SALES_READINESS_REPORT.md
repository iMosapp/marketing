# i'M On Social: SALES READINESS REPORT (Oct 14 2026)

I didn't change any code, secrets, deploys, OTA updates, phone numbers or live charges.
- Production was inspected read-only: anonymous smoke tests, plus deployer read-only debug of secrets, the database and logs.
- Preview tests used disposable data only: "QA Sales Ready *" orgs, Stripe **sandbox**, 500-555 numbers and Twilio `dry_run`. All of it was wiped afterwards.

Evidence labels:
- **VERIFIED** = run today.
- **PROD-READ** = read from production by the deployer, read-only.
- **CODE** = I read the source but didn't run it.
- **EARLIER** = passed in an earlier session and wasn't re-run today.

## Decision: CONDITIONAL GO (founder-assisted first dealership)

The app can onboard and run a dealership today. Two things are still missing:
- **Taking a card.** Stripe is in TEST mode in production.
- **Letting reps text customers from their own registered number.** The tenant A2P/number workflow runs in fake `dry_run` mode in production.

The first dealership can start this week if:
- You bill it as a Founding Partner Pilot or a billing exception (no Stripe needed), or with a Stripe Payment Link you confirm by hand.
- Its texting goes live through the compliant workflow in section 3, which needs your approval plus a controlled first real registration.

The model "text on day one from IMOS's own 10DLC campaign, then move the number silently later" is **not compliant**. Twilio's ISV rules and the app's own compliance module both say each dealership must be its own brand. Section 3 explains why and gives a compliant workflow that still makes the dealer live on day one.

## Gate results

| Gate | Result | One line |
|---|---|---|
| 1 Stripe billing | **PARTIAL** | Subscription billing works end to end in the sandbox, including real webhook deliveries, a declined renewal and cancellation. Production is still TEST mode with no live endpoint. |
| 2 Twilio provisioning / transfer | **FAIL** (activation workflow) | The manual parent-number path works. In production, in-app tenant provisioning and A2P run as `dry_run` (fake). Number transfer isn't built. The day-one-on-IMOS-campaign model isn't compliant. |
| 3 Jessi Realtime Mini | **FAIL** | The duplicate opening greeting happened in production in 3 of 8 recent Mini sessions, plus one duplicated mid-call answer. It isn't a regression, it isn't caused by settings, and it isn't the model improvising. It's a duplicated response trigger in the Mini opening path. |
| 4 End-to-end onboarding | **PARTIAL** | 24 of 24 API steps passed for a disposable dealership: founder, owner, rep, contact, card share, inbound reply and campaign enrollment. Outbound texting depends on Gate 2. The dealer manager has no view of rep activity. |
| 5 Dashboard / menu simplification | **PASS** (notes) | New customers start simplified (3 tabs, pilot Home and More). Permissions are scoped: a cross-org read gets 403. Small leftovers only. |

## 0. Production baseline (PROD-READ + VERIFIED)
- **MMS Stage 1 is LIVE.** Run bf277e6b, commit aa33bda82, promoted 23:38Z. `/api/health` reports build `2026-10-14.mms-stage1`.
  - Anonymous production smoke: **83/83**. Every unsigned Twilio webhook gets 403 (enforce mode works). The media proxy and recordings return 401 without a token.
  - Not yet verified live: a real MMS photo loading with a valid token (recent and older), outbound SMS/MMS, Jessi's photo fallback and alert, and "Mark Handled" in the app. The OTA isn't published yet.
- **Secrets:**
  - `TWILIO_WEBHOOK_VALIDATION=enforce`
  - `VOICE_FAKE_PROVIDER_ALLOWED=0`
  - `BILLING_ALLOW_TEST_MODE=0`
  - **`STRIPE_MODE=test`**
  - `OWNER_EMAIL` and `PUBLIC_FACING_URL` are correct.
  - `INTEL_BACKFILL_EXECUTE` and `INTEL_LEGACY_PROJECTION` are false.
  - The deployer couldn't read the Stripe key prefix. The Oct 12 audit found `rk_test_`.
- **Data:**
  - 10 organizations. Only "Rides and Dives" has a customer record (billing exception).
  - 0 Stripe customers and 0 `stripe_events`.
  - 0 Twilio subaccounts.
  - **There's no `settings.twilio_compliance` document, so the code defaults to `dry_run`.**
- **Logs:**
  - 16 `[TwilioSig]` rejections, all unsigned probes.
  - `/api/billing/stripe/webhook` returned 400 twice; both were my unsigned and forged probes.
  - `/api/webhook/stripe` returned 200 (see P1-7).
  - No live-voice errors.

---

## Gate 1: Stripe billing (PARTIAL)

**What works (VERIFIED in the sandbox)**
- **Path:** `services/billing.py` uses its own `StripeClient` on `STRIPE_BILLING_SECRET_KEY`.
  - Checkout runs in `mode=subscription`.
  - Prices come from lookup keys: `pilot_store_monthly` $375 (5 seats), `pilot_seat_monthly` $75, `pilot_individual_monthly` $100.
  - The org is linked through `client_reference_id` plus metadata.
- **Webhook:** `POST /api/billing/stripe/webhook`.
  - Verified with `construct_event`. Missing signature → 400, forged → 400 (VERIFIED in production).
  - Idempotent through `stripe_events` keyed by event id.
  - Handles 6 events: `checkout.session.completed`, `customer.subscription.created/updated/deleted`, `invoice.paid`, `invoice.payment_failed`.
- **Test runs:**
  - `test_billing_stage2.py`: **10/11**. The one failure is a stale source assertion: `server.py` now mentions `STRIPE_BILLING` in the security-config booleans. Not a product defect.
  - `test_pilot_program.py`: **10/10**.
  - Release gate `release_gate_founding_pilot.py`: **43/44**. It covered real hosted Checkout with card 4242, trialing until the pilot end, a $0 trial invoice, signed webhooks processed once, founder MRR rows, a $450 first charge, idempotent re-delivery, reminders on days 30/60/75/90, and ended-pilot access blocked then resumed. The one "fail" is only that the sandbox key lacks Test Clocks permission; a fallback was used.
  - New today, **declined renewal and cancellation through REAL sandbox webhooks** (card `pm_card_chargeCustomerFail`):
    - trialing → `invoice.payment_failed` delivered → `past_due`, `grace_until` +14 days, `failed_attempts` 1
    - Founder alert "Payment failed for …"
    - The owner can still sign in, the Billing screen shows past_due, and the Stripe portal opens (card update and invoices).
    - `customer.subscription.deleted` → `canceled`.
  - Everything was wiped afterwards, including the Stripe customers.
- **Visibility:**
  - Founder: `/admin/customers/{org}` (billing panel, MRR actual/scheduled/potential, Check Stripe) and the Onboarding Hub summary.
  - Owner: `/settings/billing` (status, first charge date, portal).
  - Invoices and receipts are hosted by Stripe: the portal has invoice history; receipt emails are a Stripe Dashboard setting.

**Gaps**
- **P0 (external config): production isn't live.**
  - With `STRIPE_MODE=test` and `BILLING_ALLOW_TEST_MODE=0`, the safety gate correctly pauses checkout and portal in production with a 503 and the orange notice.
  - There's no live webhook endpoint.
  - Live setup checklist: `STRIPE_LIVE_BILLING_AUDIT.md` §3–4.
- **P1:** `past_due` and `canceled` never block access automatically.
  - The founder alert says "access stays on until <grace date>", but nothing enforces that date. The founder has to act by hand.
  - That's acceptable for the first few dealers. Before scaling, either add an automatic lock after grace or change the wording.
- **P1:** The legacy `/api/webhook/stripe` (quotes and partner agreements, `STRIPE_API_KEY`, emergentintegrations) still accepts unsigned payloads. An empty unsigned POST to production returned 200. Dealership billing doesn't use it. Disable it or add signature checks.
- **P2:**
  - After a cancellation, the owner can't resubscribe from their screen unless the founder sends a new payment link.
  - Stripe events beyond the 6 handled ones (`trial_will_end`, disputes) are ignored.

**Still needs a real, controlled transaction (after you approve the live config):**
1. Live restricted key and live webhook endpoint (6 events) in Secrets, then Deploy.
2. Unsigned POST → 400, and "Send test webhook" from the Dashboard → 200.
3. One founder-owned test customer pays with your own card through Checkout (pilot trial = $0 now). Confirm one live `stripe_events` row and the founder row showing "Paid/Trialing".
4. Open the portal, cancel at period end, then revert.

I didn't create any live charge, refund or subscription.

## Gate 2: Twilio number provisioning and transfer (FAIL for the activation workflow)

**What works (VERIFIED or EARLIER)**
- **Tests:** tenant suite `test_twilio_tenant.py` **7/7** and compliance suite `test_twilio_compliance.py` **4/4**. Both run fake or dry-run.
- **State machine:** subaccount provisioning (encrypted token), number search, purchase and assign, the full A2P sequence (Trust Hub secondary profile → A2P profile → brand → campaign → messaging service), reject and resubmit, and an audit log.
- **Disposable E2E** (`dry_run`): fake subaccount provisioned, fake number bought and assigned to the rep, and an **inbound reply to the rep's number routed into the rep's thread** (VERIFIED).
- **Webhook continuity (CODE):**
  - Inbound routing uses the `To` number registry.
  - The signature token is resolved from the `AccountSid` Twilio sends, so a number moved to a subaccount still validates in enforce mode.
- **History continuity (CODE):** conversations and contacts are keyed by `user_id` plus contact, not by number or account, so history survives a number move.
- **Registration-pending restriction:**
  - `enforce_ready` plus `send_block_reason()` holds outbound texts from a number until its org is `messaging_ready`.
  - It's OFF by default.
- **Manual parent path that works in production today:**
  1. Buy a number in the Twilio Console on the parent account and add it to IMOS's Messaging Service.
  2. Tools → Twilio Migration → import.
  3. Phone Numbers → assign.

**Gaps**
- **P0 (config, not verified live):** with no `settings.twilio_compliance` document in production, the mode is **`dry_run`**.
  - Every in-app "Provision Twilio", "Add number" and "Submit compliance" in production produces **fake SIDs, a fake number and a fake approval**. A founder could believe a dealer is registered when nothing reached Twilio.
  - The `live` adapter has **never run against real Twilio**; tests use dry-run and scripted adapters.
  - Moving to `live` (real Trust Hub calls and TCR fees) needs your approval and one controlled first registration.
- **P0 (compliance, CODE):** a rep with **no assigned number** texts customers through **IMOS's platform Messaging Service**: `send_sms` without `from_phone` → `messaging_service_sid`.
  - The dealer's traffic then goes out under IMOS's brand, from a random IMOS pool number.
  - The customer's reply goes to whoever owns that pool number.
  - Today's mitigation: never let a rep text before a number is assigned. A small fix (needs approval) would refuse rep sends that have no number.
- **MISSING:** transfer between parent and subaccount.
  - Twilio supports it: a POST on the IncomingPhoneNumber with `AccountSid=<subaccount>` using master credentials, inside the same hierarchy.
  - **A2P status doesn't travel with the number.** It must leave the parent Messaging Service first and join an approved campaign in the subaccount.
  - The app has no transfer routine, no trigger on campaign approval, and no rollback.
- **Unsupported assumption:** that the dealer's traffic can be "live day one on IMOS's 10DLC". Under Twilio's ISV guidance, sending a customer's traffic under the ISV's own brand or campaign is non-compliant and can get the parent account suspended. That would hit **every** customer and IMOS's own messages. The app's own `services/twilio_compliance.py` docstring says the same.

### Compliant activation workflow for a new dealership (live on day one, texting when approved)
1. **Day 0, at the sale.** Founder creates the customer: New Customer → plan → Founding Pilot / exception / payment link. Then:
   - Send the A2P onboarding form (`/a2p-onboarding/{token}`): EIN, legal name, website, privacy/terms, sample messages.
   - Buy the dealer's numbers **directly in the dealer's subaccount**. This needs `live` mode, or the Console until then.
   - Assign one number per rep **before** inviting reps.
   - Turn `enforce_ready` ON.
2. **Day 0–1, live without A2P:**
   - Card sharing, QR, contacts and voice memos.
   - Texting from the rep's own phone Messages app (`sms:` composer). This is person-to-person, so it's compliant.
   - Email.
   - Calls on the new number. Voice doesn't need A2P.
   - Inbound texts to the new number.
   - Jessi text assist.
   - App texts from the dealer number wait with a clear "texting starts when your registration is approved" reason.
3. **Submit** brand and campaign under the **dealer's** profile. Approval takes days to weeks.
4. **On approval:**
   - The number is attached to the dealer's Messaging Service.
   - `messaging_ready` flips and app texting turns on.
   - No number moves, so no webhook or history risk.
5. **Never** route dealer sales traffic through IMOS's campaign. Only IMOS's own activation and notification texts belong there.

If you still want the parent-first model, get Twilio's written confirmation first. Then the transfer routine needs to be built and tested (P1, about one session):
- Detach from the parent Messaging Service.
- Move `AccountSid`.
- Attach to the tenant Messaging Service.
- Update the registry.
- Audit and roll back on failure.

## Gate 3: Jessi Realtime Mini vs GPT-Live (FAIL)

**What happened in production (PROD-READ)**
- **3 of 8** recent Mini sessions (1799c361ce2b, fff25ee9ff71, 1bc8319dc49c) begin with **two byte-identical assistant greetings**.
  - The second starts **123–473 ms** after the first.
  - There's no rep turn and no noise turn between them, and no errors.
- Session b924f52d9c64 also has a **duplicated non-greeting answer**.
- The listening settings are identical in the clean sessions (server_vad 0.6 / 700 ms / near_field), so settings aren't the cause.
- All of these ran on the image before MMS Stage 1. That doesn't matter: no voice code changed between the two builds.

**Cause analysis**
- **Not a regression.** `git log c8d4b298d..HEAD` shows nothing touched `live_voice.py`, `useLiveJessi.ts` or `miniCaptions.ts` since the Oct 13 fix. Your "it was working" is consistent with an intermittent defect (3 of 8).
- **Not the model improvising, and not echo or noise.**
  - The two rows are separate conversation items (captions are keyed by item id) with identical text, a gap far shorter than the 700 ms needed to detect a turn, and no user item in between.
  - The cause is **a second response being created right after the first one finishes**.
- **Most likely triggers, ranked (CODE):**
  1. `onStarted()` is bound to both `session.created` and `session.started` with **no once-guard**. Each call sends `response.create` with "Say exactly this …".
  2. `enableMiniListening()` runs on the greeting's `response.done` (which comes before playback ends over WebRTC) and turns on server VAD with `create_response: true` while the greeting is still playing.
  3. A provider-side double item.
- **Why it can't be narrowed further:** raw events, `response.create` sends, user items without transcripts, and the app bundle id **aren't stored**.
- **There's no repetition detection or recovery anywhere.**

**Minimal fix (NOT done; needs your approval; ships as an OTA plus a small backend logging change):**
- Fire the greeting once per session.
- Turn listening on at `output_audio_buffer.stopped` (playback end), keeping the 8 s safety net.
- Duplicate-response guard: if an assistant item repeats the previous one exactly with no rep turn between, cancel it and delete the item.
- Store the first ~40 provider event types and the app update id on each session.

Then run 10 iPhone calls each on "Mini only" and "Live first" with the existing script (`VOICE_MINI_PARITY_REPORT.md`).

**Other GPT-Live vs Mini differences (CODE, verified by tests: `test_live_voice` 11/11, Mini caption replay all passed)**

| | GPT-Live (`gpt-live-1`) | Realtime Mini |
|---|---|---|
| Opening | `session.instructions.append`, model takes the turn itself | client `response.create` "say exactly", turn detection off until the greeting ends |
| Turn taking / interruption | handled by the model | server_vad 0.6 / 300 / 700, interrupt_response, near_field noise reduction, language-pinned transcription |
| Tools | native delegation | one `delegate` function tool, then output, then a client `response.create` |
| Context / handoff | same profile, same 26 tools, same 40-turn handoff | same |
| Usage / cost | server clock, $0.05/min | token-based (client report), about $0.010–0.020/min estimated |
| Caps | voice policies, ledger, watchdog, kill switch (owner org: enabled, live_first, not killed) | same |

**Scripted comparison:** I re-ran `voice_prompt_parity_eval.py` today. It's a **SIMULATED text stand-in, not real audio**. Results with current prompts:

| | Quality | Concise | Adherence | Flow | Context | Simple replies ≤ 2 sentences |
|---|---|---|---|---|---|---|
| Mini | 4.6 | 4.3 | 4.6 | 4.7 | 5.0 | 91% |
| GPT-Live | 4.3 | 4.0 | 4.2 | 4.4 | 5.0 | 82% |

Output: `/tmp/sr/VOICE_MINI_PARITY_EVAL_NOW.md`. The prompts aren't the problem; the defect is in the event flow.

**Launch impact: P1.** Live Jessi is a Test Lab feature and isn't in the pilot Home. Keep it off for customers until the fix passes the iPhone script. If you want to demo live voice to prospects, treat it as P0 for that feature.

## Gate 4: End-to-end onboarding (PARTIAL)

**Disposable walk (VERIFIED, `/tmp/sr/e2e_sales_ready.py`): 24/24 passed, all wiped.**

| Step | Result |
|---|---|
| Founder creates dealership | org, store and a dormant owner; the owner can't sign in yet (401) |
| Billing | exception recorded, no charge |
| Account | activated |
| Owner invite | text and email sent; link points to `https://app.imonsocial.com/auth/activate?token=…` |
| Owner activation | link, code, password |
| Owner sign-in | pilot owner / store_manager, lands on Home (no slideshow); GET SET UP checklist 0/5 (profile, card, contact, share, memo); founder notified |
| Owner invites salesperson | invite email plus activation text (App Store link) |
| Rep defaults seeded | 12 SMS and 8 email templates, 1 campaign "Sold", 8 tags |
| Rep activation | phone, texted code, password; signs in as a pilot rep with their own checklist |
| Number (dry_run) | provisioned and assigned |
| Contact and card share | contact created; card share logged; checklist steps contact and share done |
| Texting | conversation created; outbound text attempted (fails on the fake number, as expected); **inbound customer reply landed in the rep's thread** |
| Campaign | contact enrolled in "Sold" |
| Owner visibility | sees the rep in the team list and can open the rep's conversations |

**Other suites:**
- `test_new_account_onboarding` 13/13, `test_customer_launch_stage1` 14/14 (VERIFIED).
- Pilot UI (pilot Home, 3 tabs, pilot More, share, QR, feedback): testing-agent iteration_382 (EARLIER).
- Face ID offer on the first password login: `biometric-offer-card` in `login.tsx` (CODE).

**Gaps**
- **P0 dependency (Gate 2):** first-customer texting from the rep's own number needs a real number in an approved campaign. Until then, use the Messages-app path.
- **P1:** the dealer owner/manager in pilot mode has **no rep-activity view**. Pilot More only has Invite Your Team. You (the founder) see the progress; the manager doesn't.
- **P1:** Android isn't on the Play Store. The activation text says "Android coming soon", so Android reps use the web app.
- **P2:** Jessi SMS onboarding (welcome text, vCard, voice interview, photo request) is **Test Lab gated** and texts from **your** number. The AI profile interview is also lab-only. For the first dealers, do profile, photo and personalization in person or over the phone with the founder.
- **Manual dependencies:**
  - Founder: create, activate, invite, numbers, A2P form.
  - Profile photo uploaded by the rep in My Profile.
  - Only one seeded campaign; review-request links have to be set by hand.

No unsolicited texts were sent. All test numbers were in the 500-555 range and emails were `@invalid`.

## Gate 5: Dashboard and menu simplification (PASS with notes)

**What works**
- **Defaults:** every customer created from New Customer gets `pilot: true`, so owner and reps both land on the simplified app (VERIFIED: login flags in the E2E; UI EARLIER, iteration_382):
  - Home, Contacts, Messages. Tasks and Phone are hidden from the bar.
  - Pilot Home with the 5-step checklist.
  - Pilot More: Profile & Card, Billing (owner), Invite team (owner), Notifications, Settings, Feedback, Help.
- **Non-pilot apps:** Home and More are chosen by role (`simpleHome` for reps) and filtered by `feature_permissions`.
- **Per-rep controls (VERIFIED):**
  - The owner reads and writes a rep's feature permissions (200).
  - Reading a user in another organization gets **403**, so the explore agent's suspected scope gap does not exist.
  - Permission Templates use the Hotfix 4C guards.
  - Test Lab and owner tools are guarded on both the client and the server.
- **Mobile vs desktop:** the same Expo Router screens run on web and native. No web-only navigation bypasses permissions (CODE). Native device UI wasn't tested this session.

**Notes**
- **P2:** in pilot mode every user gets the same fixed simple set. Per-rep toggles have no visible effect and there's no in-app screen for them. That's fine for launch: a manager can't make it simpler than it already is.
- **P2:** some hidden tools stay callable through the API. Example: a rep with the broadcast tile hidden still gets 200 on their own broadcast list. Server-side `feature_permissions` checks exist only for some features (trade appraisal, campaign settings).
- **P2 test debt:** `test_permission_templates`, `test_permissions_api` and `test_rbac_permissions` fail because they still use the old `X-User-ID`-only auth and old credentials. The product behaviour was verified by the E2E instead.

---

## Launch blockers, by priority

**P0: blocks taking payment, activating a customer, or delivering core service**
1. **Production Stripe isn't live** (TEST mode, no live webhook).
   - Fix: live restricted key, live endpoint (6 events), Secrets, Deploy, then one controlled founder-card transaction. *Needs owner config and approval.*
   - Selling this week without it: Founding Partner Pilot, billing exception, or a Dashboard Payment Link.
2. **Dealer texting registration isn't operational in production.**
   - The compliance/tenant mode is `dry_run` (fake), and the live adapter has never been validated.
   - Fix: owner decision → set `live` → one controlled real registration → `enforce_ready` ON. *Needs approval.*
3. **Compliance model decision.** Use the compliant workflow above. Don't put dealer traffic on IMOS's 10DLC campaign. *Owner decision.*
4. **Reps with no number text through IMOS's Messaging Service**, and replies get misrouted.
   - Mitigation now: assign a number before inviting any rep.
   - Small code fix: refuse sends when the rep has no number. *Needs approval.*

**P1: fix before scaling**

5. Mini duplicate opening and answers. Keep Live Jessi off for customers; apply the minimal fix and run the iPhone script.
6. `past_due` and `canceled` never auto-lock (founder alert wording is misleading).
7. Unsigned legacy `/api/webhook/stripe`.
8. Dealer manager has no team-activity view in pilot mode.
9. Android app not live.
10. No parent→subaccount transfer routine (only needed for the parent-first model or migrating existing numbers).
11. MMS Stage 1 finishing steps:
    - Publish the OTA ("Mark Handled" plus photo retry).
    - Live MMS checks: valid-token 200 on a recent and an older MMS, outbound SMS/MMS, Jessi photo fallback and alert.

**P2: after customers are paying**

12. Jessi SMS onboarding and the voice interview stay founder-led (Test Lab).
13. Hidden-but-callable APIs.
14. No per-rep customization in pilot mode.
15. Only one seeded campaign.
16. Stale test suites.
17. Sandbox key lacks Test Clocks permission.
18. No owner self-resubscribe after cancel.
19. Mini listening knobs live in code defaults until saved in the Voice Lab.

## What needs what

| Needs | Items |
|---|---|
| **Live validation** | first live Stripe transaction; first real A2P registration (`live` mode); first real dealer number with an inbound/outbound round trip; MMS token 200 on a real message; Mini fix on the iPhone |
| **Code fix** (after approval) | block rep sends without a number (P0-4); Mini duplicate guard and logging (P1-5); grace lock or wording (P1-6); legacy webhook (P1-7); manager team card (P1-8); transfer routine (P1-10, only if needed) |
| **External config / approval** | Stripe live key, endpoint and Secrets + Deploy (P0-1); compliance mode `live` + `enforce_ready` (P0-2); compliance model decision (P0-3); Expo OTA for MMS Stage 1; Play Store (P1-9) |

## Checklist: onboarding the first paying dealership
1. **Billing.** Pick one:
   - (a) Founding Partner Pilot (no card), or
   - (b) billing exception plus a Stripe Dashboard Payment Link, confirmed by hand, or
   - (c) after P0-1, in-app Checkout.
2. **Create the customer.** Onboarding Hub → New Customer → plan and seats → Activate → Send owner activation link. Confirm the owner signs in and sees the 0/5 checklist.
3. **Texting setup.** Send the A2P form the same day.
   - Numbers: buy one per rep in the dealer's **subaccount** (after P0-2) or in the Console, then import and assign.
   - **Assign a number to every rep before inviting them.** Turn `enforce_ready` ON.
4. **Reps.** The owner invites reps from Invite Your Team. Each rep activates (texted code), signs in, and gets the Face ID offer.
5. **First 30 minutes with each rep, in person or on the phone:**
   - Photo, title and bio (checklist 1–2)
   - Add one customer (3)
   - Share the card by Messages or QR (4)
   - Record one voice memo (5)
6. **When the campaign is approved:** `messaging_ready` flips. Send one test text to your own phone from the rep's number, then reply to it. Confirm the reply lands in the rep's thread.
7. **Every day for the first week:**
   - Watch the founder customer page: Setup N/5, last activity, attention flags, feedback.
   - Act yourself on any `past_due`.
   - Keep Live Jessi off.

## Test artefacts
- **Production smoke:** `tests/prod_smoke_hotfix3.py https://app.imonsocial.com 2026-10-14.mms-stage1` → 83/83.
- **Scripts (outside the repo):**
  - `/tmp/sr/e2e_sales_ready.py` (24/24)
  - `/tmp/sr/stripe_fail_cancel2.py` (real sandbox webhooks: declined renewal and cancel)
  - Logs in `/tmp/sr/*.log`
- **Release gate:** re-run 43/44. Its demo org and Stripe sandbox customer were wiped afterwards; re-running the command recreates them.
- **Cleanup:** 0 "QA Sales Ready" / "QA FP Gate" / "QA Pilot Billing" organizations or users left in preview. Preview Twilio compliance mode is still `dry_run`.
