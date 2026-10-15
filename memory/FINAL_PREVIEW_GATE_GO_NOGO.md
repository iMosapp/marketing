# Final Preview Gate: GO / NO-GO (Oct 15 2026, PREVIEW ONLY)

Nothing was deployed. No production reads or writes. No real Twilio texts. No live Stripe. No secrets changed.

## Verdict
**Preview: GO.** Every gate requirement is built and tested in preview.
**Production: CONDITIONAL GO.** Deploy only after the owner approves and the S1 items in section 6 are done (shadow modes saved in Secrets, read-only production checks, Stripe Secrets confirmed). Native apps stay unprotected until the OTA (S2).

## 1. Completed fixes
| # | Requirement | Status |
|---|---|---|
| 1 | Messages app bypass | Server check `POST /api/messages/native-authorize` (`services/native_handoff.py`). It checks the caller, contact ownership, that the number belongs to the contact, STOP, consent for the purpose, the subscription lock and the purpose. **Wired into every place that opens Messages** (one helper, `frontend/services/nativeMessages.ts`): contact composer + review card, thread "text from my phone", channel picker, smartSendSMS fallback, Quick Send (single + photo group), Home quick text, Touchpoints, campaign pending send, profile setup card, advocate thank-you, UniversalComposer, UniversalShareModal, Hot Leads, NDA, setup-wizard credentials, quote, partner agreement. My Account "Text review link" (it had no recipient) now goes to Quick Send, which asks for the recipient. If the check fails, nothing opens and nothing is logged, and the app shows exactly: "Couldn't check this contact's texting status. Try again." A refusal shows the reason (or the consent / STOP sheet). |
| 1b | smartSendSMS | A refused business-number send never falls back to Messages. A failed one falls back only through the server check (`blocked: true` when refused). The silent copy-to-clipboard fallback on quote / partner agreement is skipped after a refusal |
| 1c | Server bug fixed today | The advocate thank-you check was in the GET preview (it wrote an authorization on every sheet open and left the POST send with an undefined variable, ruff F821). It is now in the POST send, before anything is sent or logged |
| 2 | Contact creation integrity | "0", "undefined", "null", "abc", "None", "1234" -> 400. Nonexistent user -> 404. Another owner's account -> 403. Covers create, import and bulk writes (`services/route_guard.py`) |
| 3 | Subscription classification (preview) | Internal / Pilot / Exception / Legacy classified in preview. Legacy orgs only get a 90-day **review** date, never a lock. Live customers are not locked automatically |
| 4 | Delivery outcomes | SENT / FAILED / UNKNOWN are kept apart. UNKNOWN is never re-sent automatically |
| 5 | Preview data | 4 QA orphan contacts deleted, 2 older ones kept |

## 2. Test results (preview, at the current workspace HEAD)
- Backend launch suites: **155 passed, 0 failed** (`test_native_handoff` 16 new, `test_contact_owner_validation` 25, `test_delivery_outcomes` 10, `test_launch_compliance*`, `test_send_paths_guarded`, `test_sender_policy`, `test_team_view`, `test_startup_indexes`, `test_job_lease`, `test_startup_reliability_regression`).
- One stale assertion updated: `test_launch_compliance_stop` expected "text from my phone" to succeed after START for a contact with no consent. That send now runs the full check, so `consent_required` is the correct answer.
- Frontend (testing agent iteration_394, mobile web): server 500 and network failure both show the exact text with no send logged (contact page and thread). A 409 refusal shows "Text not sent" + the reason. On an approved send, the check runs **before** the send is logged. Quick Send returns to preview when the check fails. Home quick text was checked by code review only.
- TypeScript: 248 errors before and after (no new errors, none of the old ones touched).
- ruff F821 / F811: clean.

## 3. Remaining defects and risks
1. **Installed native apps until the OTA (S2):** the old app code opens Messages directly. The server check only protects the new web build and the new OTA. Interim: reps are told not to text opted-out contacts. Twilio carrier STOP still applies to business-number sends.
2. Once Messages is open, the app can't stop the rep from changing the recipient or the text (OS limit). The authorization is logged in `native_handoff_authorizations` (who, which number, which purpose, when) as evidence.
3. Other channel-picker apps (WhatsApp and so on) are not SMS and are not gated by the SMS check. They are still affected when "text from my phone" is logged first (the thread and contact composers check before opening the picker).
4. With consent enforced (S4), existing contacts start at "unknown". Reps texting from their own phone will see the consent sheet more often. S1 runs consent in shadow, so this has no customer impact until S4.
5. `native_handoff_authorizations` has no retention TTL (kept as audit evidence). Retention period is an owner decision.
6. Pre-existing and unrelated (not fixed, out of scope): My Account's Share Review Link sheet has no button that opens it. Its Text action is compliant.
7. Sender mapping in production is unknown until the read-only check (section 5).

## 4. Native device checklist (one iPhone + one Android, after the OTA)
Use a rep **without** a business number and a QA test contact of your own (never a customer):
- [ ] Contact page: type -> send. Messages opens with the contact's number and the text filled in. On iOS check the body is filled in (the `&body=` separator).
- [ ] Airplane mode -> send. Exactly "Couldn't check this contact's texting status. Try again." Messages does not open. Nothing is added to the timeline.
- [ ] Contact that texted STOP -> send. The STOP sheet appears and Messages does not open.
- [ ] Thread "text from my phone": same three checks.
- [ ] Quick Send (Review / Card): approved, and airplane mode.
- [ ] Photo Quick Send to 2 contacts (no business number): one Messages group with both authorized numbers.
- [ ] Home quick text, Touchpoints Text, Hot Leads text, campaign pending send "Send via native", advocate Thank-you text.
- [ ] Rep **with** a business number: a normal send goes from the business number (no Messages). A refused send shows the reason and Messages does not open.
- [ ] Locked (access-paused) account: Messages never opens.

## 5. Sender mapping (preview, read-only today) and production read-only checklist
Preview: 2 users have a texting number.
| User | Number | Org | Registry / ready | Under SENDER_POLICY_MODE=enforce |
|---|---|---|---|---|
| forest@imosapp.com (super admin) | +1 435-220-3414 | internal | registry + subaccount, `messaging_ready` false | internal org, not a customer org |
| qa-consent-rep (QA) | +1 500-555-0099 (test) | none | no registry | `unknown_sender` (blocked) |

Production (read-only, needs approval, run through the deployer agent before S5): for each user with a number, check org, `phone_numbers` registry row in the same org, `org.twilio.subaccount_sid`, `messaging_ready`, and the Messaging Service association. Also: the `OWNER_EMAIL` user has an `organization_id`, the list of orgs `billing_lock` would lock (must be 0 or agreed), and the count of legacy orgs. Full list: `LAUNCH_DEPLOY_ROLLBACK_PLAN.md` section 2.

## 6. Exact staged deployment and rollback (full detail in `LAUNCH_DEPLOY_ROLLBACK_PLAN.md`)
1. **S0 (owner, Secrets):** `CONSENT_MODE=shadow`, `SENDER_POLICY_MODE=shadow`. Confirm `STRIPE_BILLING_SECRET_KEY` / `STRIPE_BILLING_WEBHOOK_SECRET` are saved.
2. Read-only production checks (section 5). Locked-org list empty or agreed. Write down the rollback checkpoint id (the current production checkpoint).
3. Bump `BUILD` in `backend/server.py` to `2026-10-15.launch-compliance`. Save to GitHub. **Deploy** in a low-traffic window with no scheduled broadcast.
4. **S1 verify (15 min, then 24 h):** `/api/health` build on both pods, boot index line 0 failed, owner sign-in, `/api/billing/admin/access` lock count = agreed, `/api/consent/admin/policy` = shadow/shadow, and one owner-to-owner text (disclosure line, `allowed: true`). `POST /api/messages/native-authorize` without a token -> 401. Stripe webhook without a signature -> 400.
5. **S2:** `eas update --branch production` (frontend `.env` `EXPO_PUBLIC_BACKEND_URL=https://app.imonsocial.com`). Then run the device checklist (section 4).
6. **S3 (3-7 days):** review `shadow_would_block` counts and the consent migration dry run.
7. **S4 / S5:** remove `CONSENT_MODE`, then `SENDER_POLICY_MODE`, once the exit criteria are met.

**Rollback:** set the modes back to `shadow` (fastest), or `billing_status = "exception"` for one org, or `JOB_LEASES=off`. A full rollback = Emergent Rollback to the recorded checkpoint, then Deploy, then re-check `/api/health` build and `billing_config.mode`. An OTA is rolled back with `eas update:republish` of the previous update. Limits: STOP / consent records made under the new build are ignored by the old build. Expect the 26-60 s 502 window. Whether Secrets are restored on rollback is unconfirmed.

## 7. Outstanding approvals (owner)
- [ ] GO for S1 (deploy backend + web in shadow) and the time window.
- [ ] Read-only production checks (section 5), run through the deployer agent.
- [ ] Shadow modes saved in production Secrets. Stripe Secrets confirmed.
- [ ] OTA (S2) after S1 passes.
- [ ] Later: consent backfill (`apply:true`), S4 / S5 enforce, retention for `native_handoff_authorizations`.
