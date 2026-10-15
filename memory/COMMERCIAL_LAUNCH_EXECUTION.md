# i'M On Social: Commercial Launch Execution Checklist (Oct 15 2026)

Sources: `SALES_READINESS_REPORT.md`, `LAUNCH_BLOCKER_REMEDIATION_PLAN.md`, `AI_VISION_STAGE2_PLAN.md`, the MMS Stage 1 report, and the intel/scorecard docs.

**Owner decisions (Oct 15):**
- Stripe: you configure it and Deploy *before* any wiring.
- Kill switch: pauses dealership texting only (platform notifications and inbound keep working).
- Vision model: **Gemini 3 Flash** (Emergent key).
- App updates: **ONE OTA** after Phase 5.

Legend: ✅ done · 🟢 ready to build in preview · 👤 owner action or approval · 🚀 production boundary (stop for approval)

**Rule for the Stripe deploy:**
- Since aa33bda82, the only changes are **new, unwired files**: `services/sender_policy.py`, `services/team_view.py`, `hooks/miniSession.ts`, tests and docs.
- No runtime module imports them (verified with grep).
- So the Stripe deploy runs exactly the code already live. Wiring starts only after that deploy.

---

## PHASE 1: Stripe live 🚀

**Done:**
- ✅ Sandbox end to end: hosted Checkout, real webhooks, declined renewal, cancel, portal.
- ✅ Production pre-flight (read-only, Oct 15):

| Check | Result |
|---|---|
| `billing_settings` | absent → no stale test portal config; the live one is created on first use |
| Stripe ids on any org | 0 |
| `stripe_events` | 0 |
| Production build | `2026-10-14.mms-stage1` |
| Checkout and portal return URLs | built from `PUBLIC_FACING_URL` = `https://app.imonsocial.com` (`admin_helpers.APP_URL` prefers it) |

The platform-managed `APP_URL` (deploy host) and `BILLING_ALLOW_TEST_MODE` (preview runtime only) are inert for billing. **Don't change them.**

**👤 Stripe Dashboard** (Live mode toggle ON):
1. The account is activated for live payments (business details, payout bank account).
2. Developers → API keys → **Create restricted key** `imonsocial-billing-live` with exactly these permissions (everything else **None**):

   | Permission | Level |
   |---|---|
   | Customers | Write |
   | Checkout Sessions | Write |
   | Subscriptions | Write |
   | Products | Write |
   | Prices | Write |
   | Customer portal | Write |

   Copy `rk_live_…`.
3. Developers → Webhooks → **Add endpoint**:
   - URL `https://app.imonsocial.com/api/billing/stripe/webhook`
   - Events, exactly six: `checkout.session.completed`, `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.paid`, `invoice.payment_failed`
   - Copy the signing secret `whsec_…`.
4. Settings → Billing → Subscriptions and emails:
   - Smart Retries ON
   - Failed-payment emails ON
   - Settings → Emails: successful payments and refunds ON

**👤 Emergent → Deployments → Secrets** (three):

| Secret | Value |
|---|---|
| `STRIPE_BILLING_SECRET_KEY` | `rk_live_…` |
| `STRIPE_BILLING_WEBHOOK_SECRET` | `whsec_…` |
| `STRIPE_MODE` | `live` |

Leave `STRIPE_API_KEY`, `STRIPE_SECRET_KEY` and `STRIPE_WEBHOOK_SECRET` alone (legacy quotes and Mystery Shops).

**🚀 Deploy** (after you say "configured").

**Then Emergent verifies:**
- Health.
- Unsigned webhook → 400.
- "Send test webhook" → 200.
- Founder page shows `mode: live`, `conversion_enabled: true`.

**Live price mapping** (lookup keys, created idempotently on the first payment link):

| Lookup key | Price |
|---|---|
| `pilot_store_monthly` | $375/mo, 5 seats |
| `pilot_seat_monthly` | $75/mo |
| `pilot_individual_monthly` | $100/mo |

**👤🚀 Controlled $100 payment** (needs your explicit approval):
1. Founder → New Customer "IMOS Billing Test": Pilot Individual, paid, not a pilot, owner = your second email and phone.
2. Activate → Send payment link → pay with your card.
3. Verify:
   - The 3 products and prices exist in live mode.
   - The live charge and receipt.
   - 3 webhook deliveries returned 200.
   - `stripe_events` has rows with `livemode: true`, each processed once.
   - Founder row: Active, $100, MRR.
   - Owner Billing: Active, portal opens.

**👤🚀 Cancel and refund** (explicit approval):
- Dashboard: refund the full $100 → cancel the subscription immediately → the app shows `canceled`.

**⚠️ Gap against your PASS rule.** Today's code keeps access ON after a cancellation (founder-controlled; verified in the sandbox, owner login 200 after cancel).
- "No paid access after cancel" needs the small **access-lock** change (planned P1):
  - `customer.subscription.deleted` blocks the org's sign-in.
  - A daily sweep blocks past_due after the grace period.
  - `invoice.paid` or founder Resume unblocks.
- It ships in the Phase 2 deploy.
- The canceled test account is re-checked right after that deploy. **Decision needed:** this order, or hold the payment test until Phase 2 deploys.

**Rollback:**
- Disable the live endpoint.
- Restore the previous secrets → Deploy (conversion pauses).
- Refund in the Dashboard.

---

## PHASE 2: Twilio guard + real provisioning

**Built today (preview only, unwired):**
- ✅ `services/sender_policy.py`: one decision per outbound text, fail-closed.
  - **Dealership = any org except IMOS's own.** IMOS's own means the OWNER_EMAIL account's org, or an org marked `internal: true`. So a legacy org can't slip through as "internal".
  - A dealership text is allowed only when the number:
    - is in the registry,
    - is assigned to the sender (shared and store numbers: same org),
    - sits in the org's **real subaccount** (not the parent, not `ACdry`),
    - and the org is `messaging_ready` **and** the number is on the org's own Messaging Service.
  - Otherwise there's a plain reason:

    | Code | Meaning |
    |---|---|
    | `no_number` | no texting number assigned |
    | `unregistered_number` | number not registered to the dealership |
    | `wrong_org` | number belongs to another organization |
    | `not_your_number` | number assigned to a teammate |
    | `no_subaccount` | dealership Twilio account not set up |
    | `wrong_account` | number not in the dealership's account |
    | `not_ready` | registration still pending |
    | `not_associated` | number not attached to the approved registration |
    | `paused` | dealership texting paused |
    | `unknown_sender` | sending number's owner unknown |
    | `unattributed` | sender unknown |

  - `platform=True` (IMOS notifications) is allowed only *without* a dealership from-number.
  - The **kill switch** `pause_dealership_texting` only pauses dealerships.
  - `log_attempt()` writes `sms_send_log`: from number, account SID, Messaging Service, org, user, decision, Twilio SID.
- ✅ `tests/test_sender_policy.py` **26 passed, 1 skipped**. The skip is the owner-org check: OWNER_EMAIL doesn't exist in preview, so the preview internal org gets `internal: true` at wiring time.
- ✅ `tests/test_send_paths_guarded.py`: AST inventory, xfail until wiring.
  - **8** sends with no attribution: `admin_users.py:1537`, `auth.py:918`, `app_directory.py:122`, `twilio_admin.py:278`, `team_invite.py:601`, `billing.py:263`, `customers.py:182`, `compliance_onboarding.py:166`.
  - **4** direct `messages.create` bypasses that send IMOS notifications from the rep's number with parent credentials: `auth.py:1552`, `lead_intake.py:2859`, `twilio_webhooks.py:758`, `twilio_webhooks.py:1110`.

**🟢 Wiring (right after the Stripe deploy):**
1. Call `check()` + `log_attempt()` at the top of `send_sms()`; on a block, return `{"success": false, "error_code", "error"}`.
2. `platform=True` at the 8 sites.
3. Route the 4 bypasses through `send_sms(platform=True)`.
4. Pass `user_id=` at the rep sites that lack it (scheduler campaign and date-trigger sends).
5. Turn the AST test strict.
6. `pn.purchase()` refuses parent-account purchases for dealership orgs.
7. Set `from_number` and `account_sid` on the main outbound message documents.
8. Add the `pause_dealership_texting` flag to `set_flags`.
9. Mark the preview internal org `internal: true`.
10. The access lock from Phase 1.
11. Update test expectations for preview QA orgs (now dealerships: they send nothing without a ready number).
12. Regression: twilio tenant/compliance, onboarding/pilot, messages, `tests/acceptance_first_dealer.py` (moved from /tmp; now in the repo).

**🚀 Deploy:**
- Check that internal IMOS texting is unchanged (your send and reply).
- Read `sms_send_log` in production.

**👤 Then:**
1. Texting Compliance → mode `live`.
2. 👤🚀 Provision one dealership subaccount.
3. 👤🚀 Buy **one** number (approval).
4. 👤🚀 Submit **one** real registration (approval, fees).
5. The poller tracks status every 10 minutes; tenant sync every 30.
6. Before approval: app texts are blocked with a clear reason; inbound text, MMS and voice still route.
7. After approval: the number is attached automatically → `messaging_ready` → outbound and inbound SMS/MMS verified.
8. `mock` mode may be used for an early dry walk; it doesn't count for acceptance.

---

## PHASE 3: Jessi Mini + My Team + one OTA (the OTA comes after Phase 5)

**Built today:**
- ✅ `hooks/miniSession.ts` (pure, unwired): once-per-connection start, `event_id` dedupe (bounded at 500), each tool `call_id` answered once, a 60-row trace, a duplicate counter.
- ✅ `scripts/check-mini-opening.ts`: **14/14 passed**.
- ✅ `services/team_view.py` (unwired):
  - Scope: org_admin = org, store_manager = their store, rep = refused, other org = refused, super_admin by org id.
  - Per rep: setup N/5, number status none/pending/ready (through `sender_policy`), last activity, 7-day contacts / cards shared / texts sent. Counts only.
- ✅ `tests/test_team_view.py`: **6/6 passed**.

**🟢 Wiring:**
1. `useLiveJessi.ts`: run `onMessage` through `routeEvent`; the trace goes to `/live-voice/{id}/events`.
2. `record_events` stores `trace` + `dup_events`.
3. `GET /api/pilot/team`.
4. A "My Team" row in the owner's pilot More plus one list screen.
5. Then the 20-call iPhone script (see the remediation plan, section 3).

Interruptions, prompts, listening and model settings stay as they are.

**👤🚀 One OTA after Phase 5:**
- Confirm `runtimeVersion` policy `appVersion` / 1.0.4 and that no native dependency changed.
- `eas update --branch production`.
- It carries the Mini fix, My Team, the MMS retry tile, "Mark Handled", and the Phase 4/5 UI.

---

## PHASE 4: Smart Call Classification + scorecard eligibility 🟢 (after Phase 3 wiring)

Build on the existing call analysis, transcription, scorecards and relationship intelligence:
- Classify each call into one of 11 categories.
- Mark it eligible for scoring or not, and pick the scorecard.
- Criteria can be N/A.
- Averages and denominators count **only eligible** calls.
- Keep the classification and its audit history; authorized corrections are logged.
- Historical scores are kept, with a safe recalculation (dry run first).
- Intelligence is always extracted.
- UI labels such as "Sales Opportunity: Sales Scorecard Applied" / "Relationship Conversation: Intelligence Captured, Not Scored".

The first step reads the existing call-analysis code (no redesign).

## PHASE 5: Jessi AI Vision 🟢 (after Phase 4) per `AI_VISION_STAGE2_PLAN.md`

- **Model:** Gemini 3 Flash through the integration playbook (Emergent key).
- **Images:** fetched securely by the backend; MIME and size checks; EXIF stripped; cached by sha256 per org.
- **Reply:** a grounded answer with an escalation path; replaces the Stage 1 fallback only when vision succeeds.
- **Intelligence:** proposed observations, never verified facts.
- **Controls:** per-org budget, kill switch, bounded retries. It can be switched on and off independently of MMS display.
- **Scenarios:** 7 (email screenshot, vehicle, equipment, trade-in, business card, document, unreadable).

## PHASE 6: First-dealership acceptance 👤🚀

Live only, no simulated services:
1. Real payment and subscription.
2. Dealership account.
3. Real subaccount and number.
4. 10DLC approval and association.
5. Rep onboarding.
6. SMS, MMS and calling.
7. Stable Mini sessions.
8. A real photo understood by Jessi.
9. A sales call scored with the right scorecard.
10. A relationship call with intelligence and no grade.
11. My Team.
12. Simplified dashboard.
13. Permissions and isolation.
14. Billing and messaging usage records (`stripe_events`, `sms_send_log`, the usage ledger).

**Cost reporting:** measured, not estimated. This session's test runtimes were sender policy 0.15 s, My Team 0.36 s and Mini checks under 2 s. Credits are visible on your Emergent usage page.
