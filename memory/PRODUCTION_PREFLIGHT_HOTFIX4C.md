# Production preflight — Security Hotfix 4C (read-only, Oct 14 2026 ~21:00 UTC)

Reviewed build: local HEAD `83cd92757` = GitHub main `83cd927` (Claude CONDITIONAL GO). Working tree clean. Expected build label
`2026-10-14.security-hotfix4c`. Nothing deployed, nothing published, no setting changed during this preflight.

Access I had: public production endpoints (GET only), the Twilio account API (read-only, same account as production), the repo and the
preview environment. Access I did NOT have: production Secrets panel, production pod logs, production MongoDB, EAS account (CLI not
logged in). Everything in those four is marked UNVERIFIED below with the exact owner check.

## A. Production environment

| Setting | Status | Evidence / what to check |
|---|---|---|
| Build live now | `2026-10-14.security-hotfix3`, healthy, DB connected, scheduler 56 jobs | `GET https://app.imonsocial.com/api/health`, `/api/health/deep` |
| `PUBLIC_FACING_URL=https://app.imonsocial.com` | UNVERIFIED value; **effectively safe either way** | Preview `.env` carries it (Deploy copies missing keys); every code path defaults to `https://app.imonsocial.com`; the signature validator also accepts the request's own host (`Host`/`X-Forwarded-Host`). Owner: Deployment Panel -> Secrets -> confirm value. |
| `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` | PASS (in use) | Production sends and receives SMS today with them; the same account answered the read-only Twilio inventory below. |
| `TWILIO_WEBHOOK_VALIDATION=enforce` **explicitly** | **ACTION REQUIRED** | Not present in preview `.env` (code default = enforce from 4C, = `log` on the live build). Owner: add `TWILIO_WEBHOOK_VALIDATION` = `enforce` in Secrets before Deploy. Emergency lever later: `log`. |
| `RESEND_WEBHOOK_SECRET` | **ACTION REQUIRED / UNVERIFIED** | Preview value is empty. If production lacks it, Deploy copies the empty value and inbound email replies answer 503 (fail closed) until set. Owner: Resend dashboard -> Webhooks -> endpoint for `https://app.imonsocial.com/api/webhooks/resend/inbound` -> signing secret `whsec_...` -> Secrets. Set it BEFORE Deploy (inert on the live build). |
| `STRIPE_WEBHOOK_SECRET` | UNVERIFIED | Must be the signing secret of the Stripe endpoint pointing at `https://app.imonsocial.com/api/stripe/webhook` (mystery-shop payments). If production lacks it, Deploy would copy the PREVIEW endpoint's secret -> every Stripe event answers 400. Owner: confirm presence + endpoint match in Stripe dashboard. |
| `STRIPE_BILLING_WEBHOOK_SECRET` | PASS (verified present Oct 11 release) | Hotfix 4 already fails closed without it; nothing changed. |
| `JWT_SECRET` unchanged | PASS by mechanism, value UNVERIFIED | Deploy never overwrites an existing key; no code/env change touches it; preview and 4C code read it unchanged (sessions, Twilio tenant Fernet, media tokens, calendar state). |
| `SESSIONS_VALID_AFTER` unchanged | PASS | Absent from preview `.env` (nothing to copy); production value untouched; a future/malformed value is clamped (hotfix 4). |
| No new `TWILIO_TOKEN_KEY` | PASS | Absent from preview `.env`; code only reads it if present (pre-existing optional override). |
| Preview `.env` keys that Deploy would ADD if production lacks them | NOTE | 58 keys; no NEW key since the hotfix-3 deploy. Preview-only switches all default safe or are preview-runtime gated (`SMS_SEND_ONLY_TO`, `WIDGET_RING_DRY_RUN`, `LEAD_SHOP_BUY_NUMBERS`, `TWILIO_MOCK_MODE` inert in prod). Already-known production leftovers from Oct 13 (`VOICE_FAKE_PROVIDER_ALLOWED=1`, `BILLING_ALLOW_TEST_MODE=1`, `INTEL_*=true`, `APPRAISAL_ALLOW_DEV_MARKET=1`) are unchanged by 4C — owner's standing cleanup, not a 4C blocker. |

## B. Twilio communication readiness (read-only Twilio API, same account as production)

- Account: one parent account (`Full`, active). **Subaccounts: 0** -> no encrypted subaccount tokens are in use, so "can stored
  subaccount credentials still be decrypted" is moot (PASS); signatures are checked with the parent token that production already uses.
- Numbers: **7** (`+1801***298` Mystery Shops, `+1435***444`, `+1385***045`, `+1844***102` Mystery Shops, `+1435***829`, `+1385***263`,
  `+1435***414`). Every `sms_url` and `voice_url` = `https://app.imonsocial.com/api/webhooks/twilio/incoming` / `.../voice`; no fallback or
  status URL points anywhere else. 6 numbers sit in the A2P Messaging Service whose inbound URL is also
  `https://app.imonsocial.com/api/webhooks/twilio/incoming` (campaign VERIFIED; the empty second service's FAILED campaign is unused).
- Twilio Debugger, last 7 days: **zero** webhook errors on `/api/webhooks/twilio/incoming`, `/voice`, `/status`, `/recording` -> production
  returned 2xx to every inbound SMS / voice callback. 99x `30006` (undeliverable landline/carrier — delivery, not webhooks).
  73x `15003` = HTTP **404** from `POST /api/scripts/roleplay/status/{sid}?t=...` (practice/mystery-shop call status callbacks whose
  session row is gone) — daily since **Oct 7**, i.e. pre-dates every hotfix; cosmetic, not security, not a 4C blocker (noted for later).
- `[TwilioSig]` lines in production logs (last 24–48 h): **UNVERIFIED** (no log access). The live build runs the same validator in `log`
  mode, so any mismatch would already appear as `[TwilioSig] ... signature mismatch`. Owner check (2 min): Deployment Panel -> Logs ->
  search `TwilioSig` over 48 h. Expected healthy result: none (or only `missing X-Twilio-Signature` from non-Twilio probes).
- Stored Twilio credentials / webhooks: nothing to change; no test message sent.

## C. Dealership webhook impact (shared-inbox web forms + ADF sources with an API key)

- **UNVERIFIED for production**: the affected list lives in the production database, which this preflight could not read; the new
  `GET /api/health/webhook-enforcement` exists only once 4C is deployed. Preview (test data) has 9 inboxes / 2 keyed sources — not
  representative.
- SMS lead flow is NOT affected (Twilio numbers above, parent account, same URLs). Only two integration types change:
  1. **Shared-inbox web-form webhook** `POST /api/admin/team/shared-inboxes/{id}/webhook` — now requires the per-inbox key in the URL.
     Any form provider still posting to the old URL gets 401 from the moment 4C is live.
  2. **ADF lead sources that carry an API key** `POST /api/leads/adf?source_id=...` — the vendor must send `X-API-Key` (or `?api_key=`);
     sources without a key are untouched; the no-`source_id` fallback never lands on a keyed source any more.
- Pre-deploy enumeration the owner can do in the live app as super admin (5 min): Lead Sources screen -> note every source showing an
  API key and whether it received a lead recently; Team -> Shared Inboxes (per dealership) -> note inboxes whose "webhook" URL has been
  handed to a form provider. Post-deploy: `GET /api/health/webhook-enforcement` lists every inbox (has_key) and every keyed ADF source
  with dealership name — no keys shown.
- Migration checklist (per dealership, fill before cutover): dealership | integration (inbox name / ADF source) | active? (lead in last
  30 d) | responsible person | replacement: inbox -> open webhook info once, re-copy URL into the form provider; ADF -> vendor adds
  `X-API-Key` | done ✔.
- If the owner cannot confirm the list before Deploy, the honest statement is: **a dealership with a live web-form inbox or a keyed ADF
  feed stops receiving those leads from Deploy until its config is updated** (SMS/calls unaffected). Alternative that removes the window
  (NOT built, would need Claude re-review): a `WEBHOOK_KEY_ENFORCEMENT=log` grace switch for those two routes.

## D. iPhone OTA readiness

| Check | Status | Evidence |
|---|---|---|
| App Store binary runs runtime `1.0.4` | **UNVERIFIED** (EAS CLI not logged in here) | Owner: `eas build:list --platform ios --limit 3` or App Store Connect -> live version must be 1.0.4. |
| OTA targets production | PASS (config) | `eas.json` production profile channel `production`; command `eas update --branch production`. `runtimeVersion.policy = appVersion`, `expo.version = 1.0.4`, `updates.url` = project `178e2029-…`. |
| Frontend production API URL | PASS | `frontend/.env` `EXPO_PUBLIC_BACKEND_URL=https://app.imonsocial.com`; `eas.json` production env sets the same. Must stay so on the machine that publishes (it is baked into the bundle). |
| Compatible with the CURRENT backend (hotfix 3) | PASS (code-verified) | `GET /api/calls/recording-token` on the live build resolves to `GET /calls/{user_id}` and answers `200 []`; the client only stores a real token, so media/recording URLs stay plain and the old proxy serves them; no 401 -> no dead-session logout. All other 4B/4C app changes are UI-only. |
| Changes since the last PUBLISHED OTA | **UNVERIFIED which update is last** | Owner: `eas update:list --branch production --limit 3` shows the commit of the last update. Frontend commits since Oct 11 (phase1-pilot): aa65269 (Founding Partner pilot), c74686b (Tools menu), f201803 (Stripe gate UI), 81e7986 (Voice Pilot), 04ceefc/c8d4b29 (Mini Jessi captions), dabe71f (recording bar + hotfix 3), 4B/4C: 15 files (media token gate/store, resolvePhotoUrl `?t=`, MessageBubble/CallTranscript/CallLogCard/VoicemailInbox/ask-team/AskJessiSheet/EvaluationSheet, recording stash/restore, role pickers). |
| Native dependency changes | PASS | `git diff f31b6c384 HEAD -- frontend/package.json frontend/app.json frontend/app.config.js frontend/yarn.lock` is empty; `yarn.lock` tracked and clean. |
| Unreviewed `yarn install` changes | PASS | Publish with `yarn install --frozen-lockfile` (fails if the lockfile would change). |

OTA publication procedure (owner's machine, when approved):
```
git fetch && git checkout 83cd927          # the reviewed build
cd frontend && yarn install --frozen-lockfile
grep EXPO_PUBLIC_BACKEND_URL .env           # must print https://app.imonsocial.com
eas whoami                                   # the project owner account
eas update --branch production --message "security hotfix 4C (media token gate, role pickers, recording stash)"
eas update:list --branch production --limit 1   # note group id + runtime 1.0.4
```
On the iPhone: force-quit the app, reopen twice (checkAutomatically ON_LOAD); Settings/About shows the new update id if the app exposes it;
then open an MMS thread (image loads), play a voicemail / call recording, log out and in (recording bar restores nothing = fine).

## Phase 2 — deployment sequence (owner's GO only)
1. Secrets (Deployment Panel, before anything): add `TWILIO_WEBHOOK_VALIDATION=enforce`; set `RESEND_WEBHOOK_SECRET`; confirm
   `STRIPE_WEBHOOK_SECRET` is the production endpoint's; confirm `PUBLIC_FACING_URL`, `JWT_SECRET`, `SESSIONS_VALID_AFTER` present and untouched.
2. Logs: search `TwilioSig` (48 h) -> no mismatches. Dealership list (C) filled in; responsible people warned.
3. Publish the OTA (procedure above). Verify on the iPhone. Wait as long as you like — it is compatible with the live backend.
4. Deploy backend + web from GitHub `83cd927` (the Deploy button builds the saved commit; no `git pull`, no dependency update).
5. `GET https://app.imonsocial.com/api/health` -> `build: 2026-10-14.security-hotfix4c`; `/api/health/deep` healthy.
6. Signed in as super admin (app or browser): `GET /api/health/security-config` -> `twilio.webhook_validation_mode: enforce`, `resend.webhook_secret_set: true`, `stripe.*: true`, `sessions.jwt_secret_set: true`.
7. `python backend/tests/prod_smoke_hotfix3.py https://app.imonsocial.com` (aborts before any probe unless the build label matches; 83 read-only checks).
8. `GET /api/health/webhook-enforcement` -> work the dealership checklist (re-copy inbox URLs, vendors add `X-API-Key`).
9. Phase 3 checks below; Twilio Debugger watch for new errors on `/api/webhooks/twilio/incoming`.
10. Monitor 24 h: production logs for `[TwilioSig]`, `[ADF]` 401s, shared-inbox 401s, `[MediaProxy]`/`Media token required`; Twilio Debugger; Resend webhook delivery page (no 503s).

## Phase 3 — real functionality checks (designated test account + Forest's number only)
| # | Flow | How | Automated? |
|---|---|---|---|
| 1 | Login / session restore / logout | iPhone + web | API-scriptable with a production test account (not available to me) |
| 2 | Create a contact | iPhone | manual (API-scriptable) |
| 3 | Share a digital business card | iPhone -> open link in Safari | manual |
| 4 | Send + receive SMS | text Forest's number from the app, reply from the phone | manual (Twilio Debugger confirms 2xx) |
| 5 | Send + view MMS image | reply with a photo from the phone -> thread shows it (media token path) | manual |
| 6 | Inbound + outbound call | click-to-call Forest; call the IMOS number | manual |
| 7 | Jessi Live call briefing | start a live briefing (WebSocket `/call-host`) | manual |
| 8 | Voice memo record + play | + menu -> memo -> play | manual |
| 9 | Call recording playback | open a recorded call -> play, seek | manual |
| 10 | Campaign enrollment + scheduled follow-up | enroll the test contact (Forest's number) in a 1-step campaign; wait for the step | manual, no customer campaign |
| 11 | Inbound lead from web form | post one lead to a shared inbox with the NEW keyed URL (`curl`) | automated-able |
| 12 | Inbound email reply | reply to an outbound email from the test contact | manual |
| 13 | Store manager creates a salesperson | as a store-manager test account, add a rep in own store; try role Manager (expect refusal) | API-scriptable |
| 14 | Org admin approves a pending user | sign up a test applicant to the test dealership; approve as org admin | API-scriptable |
| 15 | Cross-dealership isolation | as the test rep: open another dealership's contact/conversation/user ids -> 404/403 | automated (hotfix suites cover this in preview; in production run the read-only smoke only) |

## Phase 4 — rollback and recovery (config first, code last)
| Symptom | First response (keeps 4C) | If not enough |
|---|---|---|
| Twilio rejects legitimate callbacks (inbound SMS/calls stop; Twilio Debugger shows 403/`15003` on `/incoming`) | Secrets: `TWILIO_WEBHOOK_VALIDATION=log` -> Deploy (same build). Then read `[TwilioSig]` lines to see the URL/token mismatch and fix the setting. | — |
| Shared-inbox webhook 401 | Dealership re-copies the URL from webhook info (carries `?key=`). | — (no code lever; rollback would reopen anonymous lead injection) |
| ADF 401 | Vendor sends `X-API-Key`; or the dealership regenerates/removes the key on that source in Lead Sources. | — |
| Missing production secret (`security-config` shows false) | Add the key in Secrets -> Deploy (same build). Resend/Stripe answer 503 (fail closed) meanwhile, nothing is accepted unsigned. | — |
| MMS / recording playback 401 in the app | Old binary without the OTA: publish/receive the OTA (force-quit twice). Web: hard reload. Server side: `GET /api/calls/recording-token` as the user must return a token. | — |
| Login / session problems | Do NOT touch `JWT_SECRET`. Check `SESSIONS_VALID_AFTER` unchanged; `/api/auth/me` 200 with a fresh login; cutoff is clamped so a bad value cannot lock everyone out. | Rollback to 4B (`1a8193ae5`) — same auth code as 4C. |
| Backend fails to start / 5xx after Deploy | Deployment logs; `/api/health/deep`. Config fix + redeploy same build. | Rollback: **`1a8193ae5` (Hotfix 4B, Claude-reviewed)** first; `f31b6c384` (Hotfix 4) only if 4B also fails. `24d8f3346` is NOT a valid Hotfix 4 point. Rollback never changes secrets; `JWT_SECRET` and encrypted credentials survive. Never roll back past hotfix 3 (`dabe71fb7`): everything older has the known holes. |
