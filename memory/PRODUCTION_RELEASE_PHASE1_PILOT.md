# Production release log: Phase 1 Stages 1-3 + Founding Partner Pilot (Oct 11 2026)

Owner GO received Oct 11 2026 (chat). Checkpoints and outcomes are recorded here as they happen.

## 1. Pre-flight (preview) - PASS
| Checkpoint | Result |
|---|---|
| Rollback checkpoint `87918e171` preserved | present in git history (`git cat-file -t` = commit, 2026-10-11 13:26 UTC). It is the code production ran before this release (build `2026-10-11.p0-security`) |
| Release contents | 72 files since `87918e171`: 23 backend, 25 frontend, rest tests/docs. All Phase 1 Stage 1-3 + pilot files present (`git diff 87918e171 --name-only`). `frontend/.env EXPO_PUBLIC_BACKEND_URL=https://app.imonsocial.com` |
| Build tag | `backend/server.py BUILD = "2026-10-11.phase1-pilot"` (only code change on release day); preview `/api/health` reports it |
| Default pilot pricing | `PILOT_PLANS.pilot_store_monthly`: $375/mo, 5 seats included, $75/mo per extra seat; `/api/customers/plans` returns the same; New Customer form pre-selects Pilot Store + Founding Partner Pilot |
| Works without live Stripe | `tests/nostripe_pilot_check.py` with the billing key removed from the preview backend: 15/15 PASS (create -> Activate -> Invite -> owner activation starts the clock -> owner Billing renders with Continue hidden; owner Continue / founder Send continue link / Check Stripe answer 503 "Billing is not configured on this server" and change nothing; Extend / End / Resume work; Hub row shows potential MRR). Key restored, backend restarted, `can_continue` true again |
| OTA compatibility | no change to `package.json`, `app.json`, `eas.json`, native folders since `87918e171`; `runtimeVersion.policy appVersion` (1.0.4) -> `eas update` is the right vehicle, no native build |
| Readiness scan | deployment_agent: pass, 0 findings |
| Test suites | pilot 10/10, Stage 2 11/11, regression 158/158, release gate 43/44 (test-clock permission only) |

## 2. Save to GitHub
Agent cannot push. Workspace HEAD before the release checkpoint: `cc2cdfc98350e333a711390be36ed1fd5449ecac` (+ uncommitted: BUILD bump, `tests/nostripe_pilot_check.py`, `tests/prod_smoke_phase1_pilot.py`; the platform checkpoints them with this step). The owner presses **Save to GitHub**; the commit SHA to record is the one `git log -1` shows after that push (verified below once available).

## 3. Production env vars - VERIFIED (direct, read-only probes after the deploy)
- `WEBHOOK_CRON_SECRET`: present AND equal to the preview value: `POST /api/cron/pilot-reminders` with that Bearer -> 200 `{"accepted": true}`, same `X-Webhook-Id` again -> `{"duplicate": true}`, wrong secret -> 401. Daily reminders will run (15:00 UTC).
- `STRIPE_BILLING_WEBHOOK_SECRET`: present (unsigned `POST /api/billing/stripe/webhook` -> 400 "missing signature"; it would be 503 if absent).
- `STRIPE_BILLING_SECRET_KEY`: present (`POST /api/billing/checkout/confirm` with a bogus session id -> the app's 502 "Stripe: no such session"; it would be 503 "Billing is not configured" if absent). NOTE: this means paid conversion is ENABLED in production: the owner's "Continue after the pilot" button will show and the founder's "Send continue link" will create real Checkout sessions. Before anyone taps it, confirm in the Stripe Dashboard that this is the LIVE restricted key with Customers / Checkout / Subscriptions / Products / Prices / Billing Portal write, that the live webhook endpoint is `https://app.imonsocial.com/api/billing/stripe/webhook` with the 6 events, and run the catalog once (`PYTHONPATH=. python tests/ensure_billing_catalog.py --dry-run`, then without the flag, against the live key).
- `MONGO_URL` / `DB_NAME`: the app serves data (`/api/subscriptions/plans` 200, login path 401 on bad credentials) -> connected.
- `RESEND_API_KEY`, `SENDER_EMAIL`, `APP_URL`, `OWNER_EMAIL`: not observable anonymously; they were already in use by the live Stage 1 (activation emails, owner flag). The deployer was also asked to confirm them as a pipeline precondition.

## 4. Backend deploy
Dispatched Oct 11 2026 23:12 UTC (job 22d64e5e-4b47-47dc-93f8-938753e70925) with the precondition "stop if WEBHOOK_CRON_SECRET is missing".
**Outcome: LIVE.** `/api/health` flipped from `2026-10-11.p0-security` to `2026-10-11.phase1-pilot` at 23:25 UTC (one Cloudflare 502 observed during the pod switch at ~23:25-23:27, then clean). The web bundle at `app.imonsocial.com` (`/_expo/static/js/web/entry-0e58efc1ae0932c161d3bdef199a244b.js`) contains the new screens ("Founding Partner Pilot", "Continue after the pilot", `pilot-sheet-submit`, `hub-customers-summary`).

## 5. Post-deploy smoke
`python tests/prod_smoke_phase1_pilot.py` (anonymous, read-only) at 23:28 UTC: **14/14 PASS**
health 200 build phase1-pilot · customers/plans 401 · customers 401 · billing/me 401 · billing/checkout 401 · pilot/checklist 401 · cron/pilot-reminders 401 · cron/leadership-morning-brief 401 · billing/stripe/webhook 400 (secret set, unsigned refused) · billing/checkout/confirm bogus id 502 (app's Stripe-error mapping, same in preview) · customers/{id}/pilot/end 401 · login bad creds 401 · subscriptions/plans 200 · web root 200.
Plus the cron secret probes in section 3 (200 accepted / duplicate / 401).

## 6. EAS update
Only after section 5 passes: `cd frontend && git pull && yarn install && eas update --branch production --message "$(git log -1 --pretty=%s)"` (owner runs it on the Mac; EXPO_PUBLIC_BACKEND_URL already points at production).

## 7. Founder-controlled production pilot account (owner-executed; the agent has no production credentials and must not guess any)
Use your own phone number and an email you control; invite nobody else; do not tap Continue / Send continue link.
1. app.imonsocial.com -> sign in as forest@imonsocial.com -> Hub -> **New Customer**. Business "Founder Pilot Test", plan Pilot Store, extra seats 0, BILLING = Founding Partner Pilot (pre-selected), contact = you. Create Customer.
   Expect: customer page, step 1 done, step 2 "Plan and pilot" done with "Founding Partner Pilot · 90 complimentary days from the day the owner activates · then $375/mo", stat Pilot "Not started", Potential MRR $375, no Stripe panel.
2. Tap **Activate** (no payment asked). Expect step 3 done; History shows `account_activated`.
3. Tap **Send activation link**. Expect the SMS on your phone (and the email). Open the link in a private window, set a password.
   Expect: you land on the simplified pilot Home (Get Set Up 0/5 checklist, tiles Digital Card / Contacts / Share / Voice Memo / Messages, tabs Home · Contacts · Messages). Founder phone gets the push/Alert "...activated... their 90-day pilot ends <date>".
4. Back as founder: Hub -> Customers row reads "Pilot · 90 days left · Setup 0/5 · active <today> · $375 potential"; customer page stat "90 days left", step "Plan and pilot" shows day 1 of 90, FOUNDING PARTNER PILOT panel with Extend / End; History has `pilot_started`.
5. Optional: as the test owner open More -> Billing. Expect "Founding Partner Pilot · 90 days left · complimentary until <date>"; the Continue button appears only if the live Stripe key is configured (do not tap it).
6. Leave the account in place or End it from the panel (reason) when done; data stays.

## 8. Final GO/NO-GO
**Backend + web: GO, live.** Native phones: GO to publish the OTA (`eas update`, section 6); the old bundle keeps working against the new backend (additive API only). Checkpoint 7 (founder-controlled production pilot) is owner-executed; nothing in it can be done or verified from this environment without production credentials. Observations, none blocking: transient 502s during the pod switch; Stripe billing keys are already configured in production (see section 3 note) so paid conversion is live-enabled; the app's 502 mapping for Stripe errors is rendered by Cloudflare as an HTML error page instead of the JSON detail (cosmetic, pre-existing Stage 2 behaviour, backlog: map to 503/424).

Release checkpoint commit: created by the platform at the end of this step (parent `cc2cdfc98350e333a711390be36ed1fd5449ecac`); the owner's **Save to GitHub** pushes it. Rollback stays `87918e171` -> Rollback -> Deploy.
