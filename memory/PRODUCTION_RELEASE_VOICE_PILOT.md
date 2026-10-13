# Production release: build `2026-10-13.voice-pilot` (Founder Voice Pilot + pending approved work)

Owner GO received Oct 13 2026 (chat): controlled production deployment for the founder's own Voice AI pilot only; no account enrolled by the agent; owner enrols himself and runs the iPhone tests. Checkpoints and outcomes are recorded here as they happen.

## 1. Pre-deploy gate (workspace, read-only)
| Checkpoint | Result |
|---|---|
| Rollback checkpoint `0156acb72` preserved | `git cat-file -t` = commit (2026-10-11 23:31 UTC, "Production release: Phase 1 Stages 1-3 + Founding Partner Pilot is LIVE"); its `server.py BUILD` = `2026-10-11.phase1-pilot` = what production answered before this release. Rollback -> Deploy from it restores production exactly. |
| Release content vs `0156acb72` | Tools menu improvements (`components/hub/PinnedStrip.tsx`, `FounderQuickActions.tsx`, `app/admin/quick-wins.tsx`, `users.hub_pins` in `PATCH /api/users/{id}`): present now, absent in production. Manager security fix (`PATCH /api/users/{id}` now requires the caller to be the user or in their management scope, 403 otherwise): present now, production still has the unguarded version. Stripe TEST-mode safety gate (`services/billing.conversion_enabled`, `mode`, 503 on checkout / send link while the live key is a test key): present now, absent in production. Memo nudge (`services/memo_nudge.py`): present now, absent in production. Voice AI controls Phases 2/3/4 + founder pilot (`services/voice_controls.py`, `/api/voice-controls/*`, `app/admin/voice-pilot.tsx`): present now, absent in production. |
| `server.py BUILD` | `2026-10-13.voice-pilot` (preview `/api/health` confirms). |
| Native change? | `git diff 0156acb72..HEAD -- frontend/package.json frontend/app.json frontend/eas.json` empty: OTA update only. |
| Voice suites | 27/27 (`test_voice_pilot` 5, `test_voice_fallback` 6, `test_voice_controls` 7, `test_live_voice` 9), Oct 13. |
| Phase 1 regression before deploy | `test_p0_security_closeout.py` + `test_customer_launch_stage1.py` + `test_pilot_stage3.py`: **80 passed, 0 failed** (preview API). |

## 2. Deploy log (Oct 13 2026, container clock)
| Checkpoint | Result |
|---|---|
| Deploy dispatched (backend + web) | deploy job `22d64e5e-4b47-47dc-93f8-938753e70925`, queued 05:39 UTC |
| Production health flipped | `GET https://app.imonsocial.com/api/health` -> `"build": "2026-10-13.voice-pilot"` at 05:41:27 UTC; 6 follow-up probes 200/200/200/200/200/200 (no 502 observed) |
| Production smoke `tests/prod_smoke_voice_pilot.py` | **25 / 25 PASS**: build tag; every `/api/voice-controls/*` route now answers 401 (was 404) incl. `pilot`, `pilot/enroll`, `pilot/kill`, `me`, `accounts`, `global`, `ledger`, `watchdog`; `/api/live-voice/config` + `/session` 401; anonymous `PATCH /api/users/{id}` -> 401 (manager security fix live; the old route was unguarded); Phase 1 / billing surface unchanged (plans, customers, billing/me, checkout, pilot checklist, cron 401; Stripe webhook 400 on an unsigned body; checkout/confirm 502 mapping as before; bad login 401; public plans 200; web shell 200 incl. `/admin/voice-pilot`) |
| Previous release smoke `tests/prod_smoke_phase1_pilot.py 2026-10-13.voice-pilot` | ALL PASS (14) |
| Web bundle is the new one | `/_expo/static/js/web/entry-d33d3e5b80237195fd85cc0f990a6338.js` (9.37 MB) contains "Enrol my account only" (Voice Pilot), "Paused by the account owner" (kill switch), "Switched to Jessi" (hand-off note), `quick-wins`, `founder-quick-actions` (Tools menu) |
| Stripe TEST-mode gate | Code live (`services/billing.conversion_enabled`). Anonymous probes cannot see the founder notice; owner check: Hub > Customers > any customer -> orange `billing-mode-notice` "Stripe is in TEST mode on this server. Paid conversion is paused until the live key and webhook are configured; complimentary pilots are not affected."; New Customer still defaults to Founding Partner Pilot; Send payment link -> 503 "Billing is in Stripe TEST mode...". Production Stripe keys were confirmed test-mode in the Oct 12 audit (`STRIPE_LIVE_BILLING_AUDIT.md`); the deployer env report (requested, arrives in the Deployment panel) states the key prefix class. |
| `VOICE_FAKE_PROVIDER_ALLOWED` | Not in the repo (preview `backend/.env` only, gitignored); never added to Deployments secrets; a presence report was requested from the deployer (Deployment panel). Definitive in-app check for the owner BEFORE enrolling: Voice Pilot status card -> "Fake provider: off", "OpenAI: configured", "Build: 2026-10-13.voice-pilot". The phone can never request it anyway (`fake_provider` does not occur in the app code). |
| No production account enrolled | Enrolment is only possible through `/api/voice-controls/*`, which returned 404 until 05:41 UTC today, and the agent enrolled nobody. Owner sees it on the Voice Pilot screen before enrolling: State "Not enrolled", Other accounts enrolled **0**. Every account therefore runs the legacy caps (`controls: null`). |
| Native build needed? | No. OTA `eas update` only (owner step, section 3). |

## 3. Owner steps (in order)
1. **Save to GitHub** (pushes the release checkpoint created at the end of the deploy step; parent `81e798646`).
2. Mac, verify before publishing:
   ```
   cd <your clone>/frontend
   git pull
   git log -1 --pretty='%h %s'           # the release checkpoint ("Production release: build 2026-10-13.voice-pilot ...")
   grep '^BUILD' ../backend/server.py     # 2026-10-13.voice-pilot
   grep EXPO_PUBLIC_BACKEND_URL .env      # https://app.imonsocial.com  (this value is baked into the OTA bundle)
   grep -A2 '"updates"' app.json          # url https://u.expo.dev/178e2029-a577-4d78-9611-bd7ebec83c91
   eas whoami                             # your Expo account
   eas project:info                       # ID 178e2029-a577-4d78-9611-bd7ebec83c91, slug imos
   ```
3. Publish: `yarn install && eas update --branch production --message "$(git log -1 --pretty=%s)"`, then `eas update:list --branch production --limit 1` (runtime version 1.0.4, iOS + Android, your message).
4. iPhone: force-quit the app, open, wait ~10 s, force-quit, open again. More > Internal Operations shows **Voice Pilot** = new bundle live.
5. Voice Pilot status card before enrolling: Not enrolled, Other accounts 0, Fake provider off, OpenAI configured, Build 2026-10-13.voice-pilot. Then Enrol my account only and run the tests in `VOICE_PILOT_GO_NOGO.md` section 5.

Rollback at any time: Rollback to checkpoint `0156acb72` -> Deploy (production returns to `2026-10-11.phase1-pilot`); the old OTA bundle keeps working against either backend (additive API only).

## 4. STOP: release gate failed on the environment check (Oct 13 2026 ~05:50 UTC)
Deployer read-only report on run `ac6fbafc-e64f-4ba3-b61f-43cf6ba997f2` (promoted 05:41:09 UTC): `VOICE_FAKE_PROVIDER_ALLOWED` is **PRESENT in production with value "1"** (expected absent). Everything else passed: `OPENAI_API_KEY`, `STRIPE_BILLING_SECRET_KEY`, `STRIPE_BILLING_WEBHOOK_SECRET`, `MONGO_URL`, `DB_NAME` present; `OWNER_EMAIL` == forest@imonsocial.com; build SUCCESS, no missing-module errors; DB binding unchanged (same database as run a2c37ab1 of Oct 11, 196 collections). The Stripe key's test/live prefix cannot be read by the tooling.
Exposure while it stays: the fake provider is used only when a request carries `overrides.fake_provider: true` AND the caller is a super admin or an `@invalid.imonsocial.test` account; the phone/web app never sends that override; a fake session costs $0 (it skips OpenAI) and would only write misleading ledger rows. No account is enrolled. So no spend risk and no customer impact, but the owner's gate ("absent or disabled in production") is not met -> OTA update ON HOLD, no enrolment.
Owner fix: Deployment Panel -> Secrets -> delete `VOICE_FAKE_PROVIDER_ALLOWED` (or set it to `0`) -> Deploy (pods do not hot-reload secrets). Then the agent re-runs `tests/prod_smoke_voice_pilot.py` and re-asks the deployer for the presence report; only then `eas update`.
Follow-up requested from the deployer (pending): presence of the other preview-only `.env` switches (`BILLING_ALLOW_TEST_MODE` would silently re-enable paid conversion on a test key, `TWILIO_MOCK_MODE`, `SMS_SEND_ONLY_TO`, `WIDGET_RING_DRY_RUN`, `APPRAISAL_ALLOW_DEV_MARKET`, `INTEL_*`, `LEAD_SHOP_BUY_NUMBERS`, `MARKET_DATA_PROVIDER`) and how/when `VOICE_FAKE_PROVIDER_ALLOWED` got into production (manual vs. imported from backend/.env). If any of those is present, remove them in the same Secrets edit before the redeploy.
Backlog (not done, per "no new features during deployment"): defence in depth so `fake_provider_allowed()` also refuses when `PUBLIC_FACING_URL` is the production host.

## 5. Deployer follow-up: 10 preview-only `.env` keys are in production (same run ac6fbafc)
Mechanism (support + deployer): the Deployment Panel imports every key of `backend/.env` that production does not have yet, on every deploy (existing production keys are preserved, never overwritten; keys cannot be deleted in the panel, only edited). So each new preview toggle leaks on the first deploy after it was added. `VOICE_FAKE_PROVIDER_ALLOWED` and `BILLING_ALLOW_TEST_MODE` (both added Oct 12-13) arrived today; the others most likely on Oct 11.

| Key (production value) | Code reads it? | Effect in production right now | Fix in Secrets (edit value) |
|---|---|---|---|
| `VOICE_FAKE_PROVIDER_ALLOWED` = 1 | yes, no runtime guard | zero-spend fake voice session possible for a super admin / test-domain account sending an explicit API override; app never does | `0` |
| `BILLING_ALLOW_TEST_MODE` = 1 | yes | **Stripe TEST-mode gate bypassed**: `conversion_enabled()` true on the test key = the pre-gate state (paid Checkout / Send link buttons work against the sandbox). Complimentary pilots unaffected | `0` |
| `INTEL_FACTS_INGEST`, `INTEL_LEGACY_PROJECTION`, `INTEL_BACKFILL_EXECUTE`, `INTEL_NUDGES` = true | yes | **Relationship-intelligence engine live without the owner's GO**: new leads / messages / sales record facts, projection fills (never blanks) legacy contact fields, snapshots kept in `intel_legacy_snapshots` (byte-exact `POST /api/intel/projection/rollback`); backfill still needs an explicit owner `confirm=EXECUTE`; nudges write tasks only | `false` on all four (owner may switch on later after the planned dry run) |
| `APPRAISAL_ALLOW_DEV_MARKET` = 1 | yes | mock "DEVELOPMENT DATA" market data may seed a Suggested ACV (production has no MarketCheck key) | `0` |
| `WIDGET_RING_DRY_RUN` = true | yes, but guarded by `is_preview_runtime()` (MONGO_URL localhost) | inert in production | `false` (hygiene) |
| `LEAD_SHOP_BUY_NUMBERS` = false | guarded by `is_preview_runtime()` | inert in production | leave, or `true` (hygiene) |
| `SMS_SEND_ONLY_TO`, `STRIPE_MODE`, `TWILIO_MOCK_MODE` | no code reads them | none | leave |

Owner steps: Deployment Panel -> Secrets -> set the seven active keys above to their off values -> Deploy. Agent then: `tests/prod_smoke_voice_pilot.py` (expect 25/25) + deployer presence/value check (`VOICE_FAKE_PROVIDER_ALLOWED` != 1, `BILLING_ALLOW_TEST_MODE` != 1, `INTEL_*` != true, `APPRAISAL_ALLOW_DEV_MARKET` != 1) -> OTA go. Owner in-app checks afterwards: Voice Pilot "Fake provider off"; Hub > Customers > customer -> orange TEST-mode notice; `/admin/intelligence` config shows ingest off.
STANDING RULE from now on: every new preview-only env key must (a) default to the safe production behaviour when unset AND (b) be guarded by `services/runtime_env.is_preview_runtime()` where it changes money/data behaviour, and (c) have its production value set in Secrets right after the first deploy that carries it.
