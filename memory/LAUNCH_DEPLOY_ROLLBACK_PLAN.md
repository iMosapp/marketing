# Launch Compliance Release: Staged Deployment + Rollback Plan (PLAN ONLY, Oct 15 2026)

Status: **nothing deployed, no production reads or writes, no secrets changed.** Every step below that touches production needs the owner's explicit GO first. Read-only production checks run through the deployer agent (debug intent).

---

## 1. Exact release inventory

**Production today** (from the Oct 15 master audit, verified then): build `2026-10-14.mms-stage1`, live code = commit `aa33bda82`. A deploy ships the **whole repo at HEAD**, so it bundles everything since then: `git diff --stat aa33bda82 HEAD -- backend frontend` = 99 files, about +5.4k / -0.6k lines (tests included).

| Group | Main files | Effect in production |
|---|---|---|
| A. Startup reliability + job leases (built Oct 15, tested, never deployed) | `server.py` (lazy imports, background index build, single route mount), `scheduler.py`, `services/job_lease.py`, `routers/voice.py`, `routers/calendar.py`, `services/jessie_service.py`, `services/voice_intel.py`, `services/ai_outreach_service.py`, `services/compliance.py`, `services/print_card.py`, `services/appraisals/frames.py` | **Active.** Faster boot. Each shared scheduler job and boot clean-up runs on one replica per tick. Kill switch: `JOB_LEASES=off` |
| B. Outbound gate (one gate before every provider send) | `services/outbound_gate.py` (new), `services/twilio_service.py` (`send_sms` calls the gate), `services/sender_policy.py` (now wired), every send caller declares a `purpose` (`messages.py`, `broadcast.py`, `lead_intake.py`, `ai_reply.py`, `scheduler.py`, `calendar_invite.py`, widget / shops / appraisal / photo-request services, ...) | **Active.** STOP and the subscription lock are **always enforced**. Consent and sender rules depend on `CONSENT_MODE` / `SENDER_POLICY_MODE` (unset = enforce, see section 4) |
| C. Consent capture | `services/consent.py`, `routers/consent.py` (staff routes + public `/api/public/consent/{token}`), `frontend/components/compliance/ConsentSheet.tsx`, `ConsentStatusCard.tsx`, `NewContactConsent.tsx`, `consentParts.tsx`, `app/consent/[token].tsx`, `app/contact/[id].tsx`, `app/contact/new.tsx` | **Active.** Verbal consent covers requested info + transactional only. Marketing needs the customer's own written opt-in (QR / link + last 4 digits) |
| D. STOP suppression + disclosure | `services/suppression.py`, `routers/twilio_webhooks.py` (STOP / START / HELP keywords, provider error 21610), `services/disclosure.py` | **Active.** Visible change: a sender's **first** text to a contact now ends with `{business}: Reply STOP to opt out.` Marketing texts add it every time. No periodic reminder unless configured |
| E. Subscription lock | `services/billing_lock.py`, `server.py` identity middleware (403 `billing_locked`), `routers/billing.py` (`/access`, `/admin/access`, `classify-legacy`, legacy PATCH), `routers/auth.py` (login returns `billing_lock`), `frontend/components/compliance/AccessPaused.tsx`, `store/complianceStore.ts`, `services/api.ts` | **Active, no env switch.** Orgs locked only by their own Stripe subscription status (section 6) |
| F. Duplicate-send protection | `services/send_ledger.py`, `services/broadcast_queue.py`, `services/work_owner.py`, `scheduler.py` (ledger sweep, broadcast queue) | **Active.** At most one provider call per key. A crashed mid-call send becomes `unknown_outcome` and is never re-sent |
| G. My Team | `services/team_view.py`, `routers/team_view.py`, `frontend/app/my-team.tsx`, `More` entry | **Active.** Read-only manager view, organization / store scoped |
| H. Jessi Mini single greeting | `frontend/hooks/miniSession.ts`, `hooks/useLiveJessi.ts` | Web: active on deploy. Native: only after an OTA |
| I. Industry-neutral wording (UI only, no DB / API renames) | `home.tsx`, `more.tsx`, `onboarding/*`, `sold-quick.tsx` ("Share Photo"), `GlobalQuickFab.tsx`, `help.tsx`, `WelcomeTour.tsx`, `ScheduledSendsList.tsx` | Web: active. Native: after OTA |
| J. This session's fixes | `services/index_setup.py` (new), `services/team_view.py` (manager without org id), `outbound_gate.stop_or_raise` + `messages.py` (STOP also blocks "text from my phone"), `contact/[id].tsx` + `thread/[id].tsx` (no messaging-app handoff on a STOP refusal), consent card refresh, lock seeded from sign-in | Active |
| K. Tests / seeds (never run in production) | `tests/test_launch_compliance*.py`, `test_send_paths_guarded.py`, `test_sender_policy.py`, `test_team_view.py`, `test_startup_indexes.py`, `seed_launch_locked_demo.py`, `seed_consent_rep_demo.py` | None |

**New env keys:** `CONSENT_MODE`, `SENDER_POLICY_MODE` (optional, unset = `enforce`). No other new keys. Bump `BUILD` in `server.py` (now `2026-10-14.mms-stage1`) to e.g. `2026-10-1x.launch-compliance` right before deploy, so `/api/health` proves the new pods are live.

**New collections** (created on first write, nothing existing is renamed or migrated): `consent_records`, `consent_state`, `consent_links`, `sms_suppressions`, `sms_optout_events`, `sms_disclosure_state`, `sms_disclosure_events`, `sms_inbound_index`, `send_ledger`, `sms_send_log`. New field: `campaign_pending_sends.dedupe_key`.

**Native apps (iOS / Android):** the web bundle changes at deploy. Installed native apps keep the old JavaScript until an EAS OTA update (`eas update --branch production`). See section 4 for why the order matters.

---

## 2. Production database / index compatibility checks (read-only, before deploy)

| # | Check | Expected | If not |
|---|---|---|---|
| 1 | `link_pages.user_id_1` options | `unique + sparse` (= code; verified Oct 15) | Boot logs one "UNRESOLVED option mismatch"; the index is kept, nothing changes |
| 2 | `short_urls.short_code_1` | `unique` (code now declares `unique=True`) | Same as above |
| 3 | `inbound_message_dedup.message_sid_1` unique exists, or the collection has no duplicate `message_sid` | Created by the sequential step after the gather | Boot warns and inbound dedup falls back to the app-level check; dedupe the rows only with approval |
| 4 | `campaign_pending_sends` docs with `dedupe_key` | 0 (new field) | The partial unique index cannot conflict with old rows |
| 5 | The new collections from section 1 do not exist yet, or exist without conflicting indexes | Not present | The conflicting spec is logged with its exact name and options; the others are still created |
| 6 | `OWNER_EMAIL` (`forest@imonsocial.com`) user exists **and** has an `organization_id` | Yes (IMOS internal org) | All internal texts would be treated as a customer organization's texts. Set `internal: true` on the IMOS org (needs approval) before going to enforce |
| 7 | Users with a texting number: count by org, and whether each number has a `phone_numbers` registry row in its own org, `org.twilio.subaccount_sid`, `messaging_ready`, Messaging Service association | Known list | Each "not ready" sender is blocked when `SENDER_POLICY_MODE` is enforce. **Users with a number but no organization are always `unknown_sender` in enforce** (preview example: `qa-consent-rep`) |
| 8 | Orgs that `billing_lock.evaluate()` would lock: `customer.stripe_subscription_id` set and `subscription_status` in canceled (period over) / unpaid / incomplete_expired / past_due (grace over) | 0, or a known, agreed list | Their users see the access-paused screen the moment the new build starts. Agree on each one first, or set `customer.billing_status = "exception"` before deploy |
| 9 | Orgs without a Stripe subscription (legacy) | Counted | Never locked (only an admin-set `billing_legacy.expires_at` locks). `classify-legacy` dry run after deploy |
| 10 | Pending work in flight: `campaign_pending_sends` status pending, `broadcasts` status scheduled / sending | Small and known | Under the new build they go through the gate (purpose marketing for broadcasts: needs written marketing consent in enforce) |

Boot log to expect after deploy: `Database indexes created/verified: N ok, 0 unresolved option mismatch, 0 failed` (any mismatch line names the collection, index and both option sets; nothing is dropped or rebuilt automatically).

---

## 3. Stripe live secret preservation

- `STRIPE_BILLING_SECRET_KEY` and `STRIPE_BILLING_WEBHOOK_SECRET` live in the Deployment panel **Secrets**. On deploy, saved Secrets override the repo's `backend/.env`, which holds only sandbox values (`rk_test_`, preview `whsec_`). This release changes **no** Stripe key, value or code path that reads them.
- **Before deploy:** the owner confirms both values are saved in Secrets (not just once in a past environment). Never paste live keys into preview.
- Legacy `STRIPE_API_KEY` / `STRIPE_SECRET_KEY` / `STRIPE_WEBHOOK_SECRET` and platform-managed `STRIPE_*` are untouched. `BILLING_ALLOW_TEST_MODE` only works on the preview runtime.
- **After deploy:** Super admin -> Customers: `billing_config.mode == live` and `conversion_enabled == true` (only if the live key is already in place; production was on a test key on Oct 12). `curl -X POST https://app.imonsocial.com/api/billing/stripe/webhook` without a signature -> 400.
- **After any rollback:** re-check `billing_config.mode`. Emergent could not confirm whether a rollback restores an older Secrets snapshot. Keep the live key and webhook secret where the owner can re-save them.

---

## 4. Sender-policy and consent rollout mode in production (recommended)

Why staged: (a) every existing contact starts with consent **unknown**. In enforce mode, a rep's text is refused unless the contact texted in during the last 30 days, or consent is recorded. (b) Installed native apps (before the OTA) do not have the consent sheet. Their old `smartSendSMS` **falls back to the phone's own SMS app** when the server refuses, which routes around a refusal. (c) Sender readiness (section 2 #7) is unknown for production numbers.

| Stage | Settings (production Secrets, each needs approval) | What is enforced | Exit criteria |
|---|---|---|---|
| S0 (before deploy) | Add `CONSENT_MODE=shadow` and `SENDER_POLICY_MODE=shadow` | — | Saved in Secrets |
| S1 Deploy backend + web | (as S0) | STOP, subscription lock, purpose classification, recipient rules for system texts, first-text disclosure, duplicate-send ledger. Consent / sender failures are only **logged** (`sms_send_log.shadow_would_block`) | Section 7 checks pass |
| S2 OTA to native apps | `eas update --branch production` | Native apps get the consent sheet, access-paused screen, STOP refusal without the messaging-app handoff, Mini single greeting, new wording | Most active devices on the new update (Expo dashboard) |
| S3 Observe 3-7 days | — | Daily: count `shadow_would_block` by code and org. Run `GET /api/consent/admin/migration-report`, then `POST /api/consent/admin/migrate {step: lead_forms\|inbound, apply:false}` (dry run) | Owner reviews counts. Approves the backfill (`apply:true`) or leaves it |
| S4 Consent enforce | Remove `CONSENT_MODE` (or set `enforce`) | + consent per purpose; marketing needs written opt-in | Refusal rate acceptable and reps know the "They agreed · Save and send" flow |
| S5 Sender enforce | Remove `SENDER_POLICY_MODE` | + customer organizations text only from their own registered, ready numbers | Every active customer org's numbers show ready (section 2 #7) |

Emergency levers (no code change): set the mode back to `shadow` (consent / sender only); the compliance pause flag (`settings.twilio_compliance.pause_dealership_texting`) refuses all customer-organization texts while sender policy is enforced; `JOB_LEASES=off` for scheduler ownership.

## 5. STOP enforcement safeguards

- STOP, STOPALL, UNSUBSCRIBE, CANCEL, END, QUIT, OPTOUT / OPT OUT / OPT-OUT, REVOKE (and provider error 21610) write `sms_suppressions` + `sms_optout_events`, and set the contact flags. **Only the contact can lift it, by texting START.** Staff cannot.
- Checked in `outbound_gate.evaluate()` in every mode (shadow never relaxes STOP), on every provider send through `send_sms`. AST guard test: `tests/test_send_paths_guarded.py` (no direct `messages.create`, every send declares a purpose).
- "Text from my phone" (`sms_personal`, the platform never sends): `stop_or_raise` refuses opted-out contacts with 409 `opted_out` before anything is logged. The new app does not open the messaging app or the channel picker.
- **Gap until the OTA (S2):** old native apps fall back to the phone's SMS app on a refusal (the rep still has to press Send). The same is true today with Twilio's own 21610 refusals. Closing it needs the OTA. Telling reps not to text opted-out contacts covers the interim.
- Post-deploy check: one seeded QA contact (Twilio test-range number) gets STOP -> provider send refused + personal send refused + START lifts it. Production has no QA accounts, so either the owner does this on a test contact of his own, or it is skipped.

## 6. Subscription lock: migration and legacy-account exemptions

- Locked only by the org's own Stripe subscription: past_due (14-day grace, then lock), unpaid, incomplete_expired, canceled once the paid-through period ends.
- **Never locked:** super admins, the internal org (`OWNER_EMAIL` org or `internal: true`), active pilots (`billing_status: pilot`), billing exceptions (`billing_status: exception`), every org **without** a Stripe subscription (legacy), unless an admin sets `billing_legacy.expires_at` on purpose.
- While locked: team members see the access-paused screen (sign out only). The account owner (`customer.owner_user_id`, or org_admin) keeps `/api/billing/*` and gets "Restore billing". Inbound texts keep saving. Outbound texts and automations pause.
- Migration: no data migration is needed to deploy. After deploy, `POST /api/billing/admin/access/classify-legacy` (dry run) lists legacy orgs. `apply=true` (owner approval) only stamps a 90-day **review** date, never an expiry.
- Emergency unlock for one org: set `customer.billing_status = "exception"` (super admin). The cache clears within 20 s.

## 7. Staged verification checklist (after each stage)

S1 (first 15 min, then 24 h):
1. `/api/health` shows the new `BUILD` on both pods. At least 50 health checks pass. No restart loop.
2. Boot log: the index line (section 2), `[JobLease]` lines show one owner per job, no `[OutboundGate] log failed`.
3. Owner signs in: Home / Contacts / Inbox / More load. My Team opens for a manager. Super admin is never locked.
4. `GET /api/billing/admin/access`: the locked count equals the agreed list from section 2 #8.
5. `GET /api/consent/admin/policy`: `consent_mode: shadow`, `sender_policy_mode: shadow`.
6. One real conversational text from the owner's own number to his own phone: delivered, the first one carries the disclosure line, `sms_send_log` row `allowed: true`.
7. Stripe checks from section 3.
8. Scheduler: campaign tick claims, no duplicate `send_ledger` keys, no growth in `unknown_outcome`.
9. Inbound webhook: a text to a rep number lands in the thread (signature `enforce` unchanged).

S2: OTA published. On one iPhone, the consent sheet opens on a refused send (S4 only), the access-paused screen works (seeded preview demo only), and Mini greets once.
S4 / S5: refusal counts by code for 48 h. Rep feedback.

## 8. Rollback procedure and limitations

- **Procedure:** Emergent Rollback to the checkpoint just before the deploy (or a republish of `aa33bda82`). Then re-check `/api/health` build, `billing_config.mode`, and the boot log.
- **Faster than rollback for most issues:** consent / sender problems -> set the modes to `shadow`. One org wrongly locked -> billing exception. A scheduler problem -> `JOB_LEASES=off`.
- **Data safety:** all new collections and fields are additive; the old code ignores them. Nothing is dropped, renamed or migrated by this release.
- **Limitations:**
  1. STOP records made under the new build stay in `sms_suppressions`, but the old build does not read them. After a rollback, only Twilio's own carrier-level STOP protects those contacts, and only on the same sending number.
  2. Consent recorded under the new build is ignored by the old build (the old build doesn't check consent).
  3. A native OTA can't be rolled back by a server rollback. Republish the previous update (`eas update:republish`) if needed. New native JS against the old backend: `/api/billing/access`, `/api/consent/*` and `/api/team-view` answer 404. The access gate keeps its last known state (no lock on a fresh start), the consent card hides itself, My Team shows an error, and sends behave as today.
  4. Every rollback is a republish: expect the known 26-60 s 502 window from the platform health check.
  5. Secrets snapshot behaviour on rollback is unconfirmed (section 3).

## 9. Production GO / NO-GO criteria

**GO for S1 (deploy backend + web in shadow) only when ALL hold:**
- [ ] Owner approves this plan and a low-traffic window.
- [ ] Read-only checks of section 2 done. Locked-org list (#8) is empty or agreed. #6 internal org confirmed.
- [ ] `CONSENT_MODE=shadow` and `SENDER_POLICY_MODE=shadow` saved in production Secrets (owner).
- [ ] Stripe Secrets confirmed saved (section 3). No Stripe change in this release.
- [ ] Preview suites green at the deploy commit: `test_launch_compliance`, `test_launch_compliance_api`, `test_launch_compliance_stop`, `test_send_paths_guarded`, `test_sender_policy`, `test_team_view`, `test_startup_indexes`, `test_job_lease`, `test_startup_reliability_regression` (+ mini opening check).
- [ ] `BUILD` bumped. Rollback checkpoint id written down.

**NO-GO if any:** an unexplained org on the lock list; the internal org not resolvable; any failing suite above; Stripe Secrets not confirmed; the deploy window overlaps a scheduled broadcast.

**GO for S4 / S5 (enforce):** OTA adopted (S2), shadow counts reviewed, the consent backfill decision made, sender readiness confirmed per org.
