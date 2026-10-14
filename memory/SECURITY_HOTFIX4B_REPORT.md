# Security Hotfix 4B (P0): hierarchy self-promotion, Twilio media proxy, Jessi WebSocket + triage — GO / NO-GO report

Date: Oct 14 2026 (preview). Status: BUILT + VERIFIED IN PREVIEW, **NOT DEPLOYED**, no Expo update published.
`JWT_SECRET` untouched, no `TWILIO_TOKEN_KEY`, no migration, no production change. Build label: `2026-10-14.security-hotfix4b`.
Every Hotfix 3 / Hotfix 4 protection is still in place (their suites run green in the same batch, §3).

## 1. Confirmed findings -> fixes (changed files)

| # | Sev | Finding (independent review) | Fix | Files |
|---|---|---|---|---|
| 1 | CRITICAL | `PUT /api/admin/hierarchy/users/{id}/assign-org`, `/change-organization`, `/assign-store` (+ `/remove-store`, `/role`) used `require_user_access`, which accepts **self** -> a rep could promote himself to super_admin / move himself into another organization or store | New `rbac.require_hierarchy_admin(min_role)`: super admin anything; otherwise caller >= min_role, **never your own account**, target inside the caller's scope and not outranking the caller. `rbac.assert_in_scope` (org / store must be one the caller manages), `rbac.assert_role_grant` (role strictly below your own), store must belong to the user's organization, removing someone from their org is super-admin only, `change-organization` is org_admin+. `/role` lost its `X-User-ID`-based identity. Same rules re-checked on `PUT /api/admin/users/{id}` (hotfix 4) | `routers/rbac.py`, `routers/admin_hierarchy.py` |
| 2 | CRITICAL | `GET /api/webhooks/twilio/media-proxy?url=` fetched **any** `https://*.twilio.com` URL with the platform `TWILIO_ACCOUNT_SID/AUTH_TOKEN` (account APIs, keys, messages, recordings of every tenant), followed redirects anywhere, was anonymous | `allowed_media_url()`: exact allowlist — scheme https, host exactly `api.twilio.com`, no userinfo/port/query/fragment/backslash/space/`%`/`..`/`//`, path must match `^/2010-04-01/Accounts/AC{32hex}/(Messages/[MS]M{32hex}/Media/ME{32hex}\|Recordings/RE{32hex})(.mp3\|.wav\|.json)?$`; the canonical URL is rebuilt (never the caller's string); credentials only go to that host; redirects are **not** auto-followed: max 2 hops, only `https://media.twiliocdn.com` (`allowed_redirect`), fetched **without** credentials; upstream 401/403/404 -> 404. Access now needs a **media token** (`?t=`, HMAC over user id + expiry with `JWT_SECRET`, 2 h, 20-byte fixed-length tag) minted for a signed-in user by `GET /api/calls/recording-token`. Contact-photo import (`contacts.py`) that fetched proxied URLs now validates through the same allowlist. Voicemail/MMS/recording URLs the backend emits are unchanged in shape; the app appends `?t=` | `routers/twilio_webhooks.py`, `services/media_tokens.py` (new), `routers/calls.py`, `routers/contacts.py` |
| 3 | HIGH | Hotfix 4's `require_signed_callback` router dependency took `Request`; on the `/api/webhooks/twilio/call-host/{pid}/{token}` **WebSocket** FastAPI failed the dependency -> Jessi live-briefing bridge broken | Dependency now takes `starlette.requests.HTTPConnection`; non-http scopes (WebSocket upgrades: Twilio does not sign Media Streams, they carry the per-call token) and GET fetches return immediately; HTTP POSTs are verified exactly as before | `services/twilio_signature.py` |
| 4 | HIGH | `GET /api/calls/recording/{call_sid}` streamed any call recording to anyone who knew the SID | `_listener()`: Bearer session or media token; recording owner must be the caller, in the caller's `get_data_filter` scope (managers), or caller is super admin; otherwise 404 | `routers/calls.py` |
| 5 | HIGH | Same-rank recovery takeover: a store manager could change another store manager's (or an org admin another org admin's) email / phone / password | `rbac.assert_recovery_editable`: email/phone/password of **another** account only by someone strictly above its role (super admin exempt); wired into `PATCH /api/auth/users/{id}`, `PUT /api/auth/user/{id}`, `PUT /api/admin/users/{id}`; non-recovery fields (title…) unchanged | `routers/rbac.py`, `routers/auth.py`, `routers/admin_users.py` |
| 6 | HIGH | Shared-inbox web-form webhook `POST /api/admin/team/shared-inboxes/{id}/webhook` was anonymous with no secret (lead injection into any dealership inbox) | Per-inbox `webhook_key` (generated on first `webhook-info` call, `secrets.token_urlsafe(24)`), required as `?key=` or `X-Webhook-Key`, constant-time compare, 401 otherwise; `webhook-info` is managers-only and scoped (org admin: own org; store manager: own stores) and returns the URL with the key. **Breaking for existing form integrations: the webhook URL must be re-copied** (see §4) | `routers/shared_inboxes.py` |
| 7 | HIGH | ADF lead intake `POST /api/leads/adf`: when a source had an `api_key`, **omitting** the header bypassed the check | Key configured -> header `X-API-Key` (or `?api_key=`) is mandatory and compared constant-time; sources without a key unchanged | `routers/lead_intake.py` |
| 8 | MED | Unsigned Twilio callbacks: `/api/webhooks/twilio/lead-call/answer\|claim\|status` (Lead Call Engine) had no signature check | Router-level `Depends(require_signed_callback)` (same validator/URL rules as hotfix 4) | `routers/lead_call_webhooks.py` |
| 9 | MED | Stripe **mystery-shop** webhook (`/api/stripe/webhook`) accepted unsigned events when `STRIPE_WEBHOOK_SECRET` was unset (billing webhook was already fail-closed) | Missing secret -> 503 + error log; `construct_event` always with the secret | `routers/mystery_shops.py` |
| 10 | MED | Google Calendar OAuth: `/api/calendar/oauth/login/{user_id}` was public, `state` was the raw user id -> anyone could bind their Google account to another user's calendar via the callback | `login` requires the signed-in owner (or super admin); `state` is a signed 10-minute single-purpose JWT (`purpose=gcal_oauth`, nonce); callback accepts only that (400 otherwise). Only `/api/calendar/oauth/callback` stays public | `routers/calendar.py`, `services/route_guard.py` |
| 11 | MED | Inventory webhooks (`/api/webhooks/inventory/*`) stored the `organization_id` from the body and matched items by `external_id` only -> an API key of org A could update/delete/read org B's units | `tenant_scope()/stamp_tenant()`: every read/write filtered by the key's organization (or store); body tenant fields overwritten with the key's | `routers/inventory_webhooks.py` |
| 12 | MED | Public AI endpoints (`/api/chat/start`, `/message`, `/capture`, `/api/help-center/ask`) unlimited -> LLM cost exposure | `services/ratelimit.throttle` (in-process, per client IP via `cf-connecting-ip`/`x-forwarded-for`): chat start 10/min 100/day, message 20/min 300/day, capture 10/min 50/day, help ask 10/min 100/day -> 429 | `services/ratelimit.py` (new), `routers/chat_widget.py`, `routers/help_center.py` |
| 13 | MED | Partner portal: `/api/partners/portal/orgs\|/{org}/stores\|/{org}/users` trusted `X-User-ID` / had no caller check; `/portal/assign-org` unauthenticated | Session via `get_current_user`; partner must manage the org (`_assert_partner_manages`), `assign-org` super-admin only, password/reset/refresh fields never returned | `routers/partners.py` |
| 14 | LOW | Recording lost on forced logout (hotfix 4 dropped the file) | `recordingStore.abandon()` now **stashes** the finished/failed file per user in AsyncStorage; `restorePending()` on next login shows it in the bar with Retry/Discard (RecordingOverlay) | `frontend/store/recordingStore.ts`, `components/recording/RecordingOverlay.tsx` |
| — | — | Operator visibility | `GET /api/health/security-config` (super admin only): booleans for Twilio validation mode, parent creds, Resend/Stripe secrets, session cutoff, Google creds + `public_facing_url` + build. No secret values | `server.py` |

Frontend (same build, needed for #2/#4): `store/mediaTokenStore.ts` + `components/common/MediaTokenGate.tsx` (mounted in `app/_layout.tsx`:
fetches the token after login, refreshes every 100 min, clears on logout); `utils/photoUrl.resolvePhotoUrl` appends `?t=` to
`/webhooks/twilio/media-proxy` and `/calls/recording/` URLs (35 call sites covered); direct consumers updated: `MessageBubble`
(MMS), `CallTranscript`, `CallLogCard`, `VoicemailInbox`, `ask-team`, `AskJessiSheet`, `EvaluationSheet`. Verified on web: login ->
`GET /api/calls/recording-token` fires once; TypeScript clean for every touched file (remaining tsc errors are pre-existing).

## 2. Tests added
- `tests/test_security_hotfix4b.py` (15): hierarchy self-promotion / cross-org / store-manager scope / org-admin ceilings / super-admin
  positive + restore, partner portal, media proxy token + 24 adversarial URL shapes + allowlisted shapes, `/call-host` WebSocket
  (bad token -> 1008, real pending doc -> opens), unsigned POSTs still 403 and production-URL-shape signature -> 200, same-rank
  recovery, Stripe fail-closed, ADF header bypass, shared-inbox key (anon/guess 401, rep 403, manager 200 -> lead created & cleaned),
  lead-call unsigned, calendar login/callback/state, inventory cross-key isolation, chat throttle, recording ownership, security-config.
- Independent testing agent (`/app/test_reports/iteration_387.json`, 0 findings) added `tests/test_security_hotfix4b_adversarial.py`
  (9): `X-User-ID` spoofing with a rep JWT, peer-rep attacks on all hierarchy routes, 12 more proxy URL shapes (punycode, cyrillic
  look-alike, trailing-dot host, IPv6, backslash host split, double-encoding, :443, NUL/CRLF, other API version), calendar state
  tampering (wrong purpose / expired / wrong secret), security-config role gate, Mongo asserted unchanged everywhere.
- `tests/prod_smoke_hotfix3.py`: 14 new inert checks (hierarchy anon 401, proxy 401, recording 401, lead-call 403, stripe never 200,
  shared-inbox 401, calendar login 401, portal 401, security-config 401), expects build `2026-10-14.security-hotfix4b`; **72 checks**.

## 3. Results (preview, Oct 14 2026)
- Full security batch (hotfix4b 15 + hotfix4 12 + hotfix3 authz 19 + adversarial 21 + webhook scope 1 + session cutoff 12 + twilio
  tenant 7 + bola + profile …): **116 passed, 1 skipped** (`/tmp/hotfix4b_regress.log`, 4m04s).
- Testing agent: 53/53 required suites + 9/9 adversarial + smoke 72/72, no unauthorized 2xx, no 500, no stray documents.
- One defect found by my own suite during the work and fixed before hand-off: media-token tags containing a `.` byte (~7 % of tokens)
  failed verification; the format is now fixed-length (3000-token fuzz: 0 failures).
- Run: `cd /app/backend && set -a && . ./.env && . ../frontend/.env && set +a && python -m pytest tests/test_security_hotfix4b.py tests/test_security_hotfix4b_adversarial.py tests/test_security_hotfix4.py tests/test_security_hotfix3_authz.py tests/test_twilio_tenant.py -q -p no:cacheprovider -W ignore::DeprecationWarning`

## 4. Remaining findings (none critical/high open in code; operational items)
1. The in-process rate limiter is per backend process (single uvicorn worker today). Multiple replicas would multiply the caps — acceptable for cost control, not a hard quota.
2. Media tokens are bearer-style (2 h, bound to the user, not to a specific recording). Someone with a user's token can fetch the recordings/media **that user** is already allowed to hear. Scope-per-resource tokens are a possible hardening, not a hole.
3. `webhook-info` for shared inboxes and lead-source API keys are organisational: dealerships with live form integrations must re-copy the URL (shared inbox) / add the `X-API-Key` header (ADF sources that have a key but whose vendor never sent it). Both fail **closed** (401) until then — check `[ADF]`/shared-inbox 401s in logs the first day.
4. Legacy test files (not security) still assume older behaviour; only the suites named in §3 are authoritative.

## 5. Required production configuration (confirm BEFORE / right after deploy via `GET /api/health/security-config` as super admin)
| Key | Required | Why |
|---|---|---|
| `TWILIO_WEBHOOK_VALIDATION` | unset or `enforce` | Hotfix 4 default; `log`/`off` would reopen every callback. Emergency lever only. |
| `PUBLIC_FACING_URL` (or `APP_URL`) | `https://app.imonsocial.com` | Signature base URL (also accepts raw request URL + forwarded host; mismatch logs `[TwilioSig] ... signature mismatch`). |
| `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN` | present (they are) | Proxy credentials (only ever sent to api.twilio.com) + parent signature fallback. |
| `RESEND_WEBHOOK_SECRET` | set (`whsec_…`) | Inbound email replies answer 503 until set (fail closed). |
| `STRIPE_WEBHOOK_SECRET` and `STRIPE_BILLING_WEBHOOK_SECRET` | set | Both Stripe webhooks answer 503 without them. |
| `JWT_SECRET` | **unchanged** | Sessions, encrypted Twilio tenant tokens, media tokens, calendar OAuth state. |
| `SESSIONS_VALID_AFTER` | as set by hotfix 2 (never in preview `.env`) | Future/malformed is clamped (hotfix 4). |
| `GOOGLE_CLIENT_ID/SECRET` | as today | Calendar OAuth start answers 503 when missing (unchanged behaviour). |

## 6. Deployment plan (owner's GO only) and rollback
1. Save to GitHub -> Claude review of this build (`BUILD = "2026-10-14.security-hotfix4b"`).
2. Deploy backend + web. Immediately `eas update` (native app needs `MediaTokenGate`; until the OTA lands, **existing native builds get 401 on MMS images, voicemail and call-recording playback** — minutes of impact, no data loss).
3. Post-deploy, within 5 minutes: `python backend/tests/prod_smoke_hotfix3.py https://app.imonsocial.com` (aborts before any probe if the build label differs; 72 read-only checks); `GET /api/health/security-config` as super admin; send one real inbound SMS + one click-to-call and watch for `[TwilioSig]` mismatches; open one MMS thread and one call recording in the app.
4. Tell dealership admins using shared-inbox web forms to re-copy the webhook URL (Team -> inbox -> webhook info).
5. Rollback: redeploy the previous checkpoint (`24d8f3346` = hotfix 4 build) — no schema/secret change in 4B, so rollback is a plain redeploy; note it reopens the §1 items. Emergency levers without rollback: `TWILIO_WEBHOOK_VALIDATION=log` (callbacks), nothing else is feature-flagged.

## 7. Recommendation
**GO (conditional)** — pending Claude's independent review of the GitHub build and the §5 configuration confirmation. Production currently still carries findings #1–#13; nothing in 4B requires a secret rotation or migration, and the preview carries 116 green security tests plus an independent 0-finding adversarial pass.
