# Security Hotfix 4C (P0, narrow): account creation / approval must respect rank and scope — report

Date: Oct 14 2026 (preview). Status: BUILT + VERIFIED IN PREVIEW, **NOT DEPLOYED**, no Expo update published.
`JWT_SECRET` untouched, no new secrets/credentials/env keys, no migration, no production change. Build label:
`2026-10-14.security-hotfix4c`. Hotfix 3 / 4 / 4B protections intact (their suites run green in the same batch, §3).

## 1. Reproduction (sandbox = preview DB, before the fix)
`qa-manager` (store_manager of STORE_A) -> `POST /api/admin/users {role: "super_admin", store_id: STORE_A, ...}` -> **200**,
document created with `role: super_admin`. Deleted immediately together with its seeded templates/campaigns. Same class of hole
confirmed by code review on `/users/create` and `/pending-users/{id}/approve`, plus five equivalent routes below.

## 2. Exact fixes (changed files)

| # | Route | Before | After |
|---|---|---|---|
| 1 | `POST /api/admin/users` | role copied from the body (store manager / org admin could mint super_admin); org admin's `store_id` never checked | `rbac.assert_placement`: role **strictly below** the caller's (super admin exempt), organization and store inside the caller's scope, store must belong to the organization, store managers must name one of their stores (400 otherwise); organization derived from the store when omitted | `routers/admin_users.py`, `routers/rbac.py` |
| 2 | `POST /api/admin/users/create` | same: any role, store never checked | same `assert_placement` rules; creator is the proven session (`_creator`) | `routers/admin_users.py` |
| 3 | `PUT /api/admin/pending-users/{id}/approve` | any org admin could approve any applicant of any dealership with any role / org / store | applicant must be **pending** and must have applied to one of the approver's organizations (404 otherwise); role / organization / `store_id` / every `store_ids` entry pass `assert_placement` | `routers/admin_users.py` |
| 4 | `GET /api/admin/pending-users`, `/count`, `PUT .../reject` | org admins saw and could delete every dealership's applicants (names, emails, phones) | scoped to the caller's organizations (`_pending_scope`); count cache only for super admins. Also fixed a 500 on legacy string org ids in the list | `routers/admin_users.py` |
| 5 | `POST /api/admin/users/add-team-member` | trusted `added_by` **from the body** for the permission check; store never checked against the caller; store manager could grant `store_manager`; temp password stored **in plaintext** | caller = session; `assert_placement(role, store)`; `added_by` ignored; password bcrypt-hashed; no SMS attempt without a phone | `routers/admin_users.py` |
| 6 | `POST /api/setup-wizard/bulk-invite` | store manager could create store managers | `assert_role_grant` per member role (store managers create reps only; `super_admin` still 400) | `routers/setup_wizard.py` |
| 7 | `POST /api/permission-templates/{tpl}/apply/{user_id}` | a store manager could apply the prebuilt **org_admin** template to **themselves** (-> org_admin), or create a custom template with `role: super_admin` and apply it | `require_hierarchy_admin` (never self, target in scope, not outranking) + `assert_role_grant(template.role)`; another organization's custom template -> 404 | `routers/permission_templates.py` |
| 8 | `POST` / `PUT /api/permission-templates` | any role string accepted on templates | role validated and `assert_role_grant` for the creator / editor | `routers/permission_templates.py` |
| 9 | `POST /api/admin/individuals` | any signed-in user could create accounts (GET was already super-admin only) | super admin only | `routers/admin.py` |
| — | ADF fallback | a post without `source_id` / vendor match could land on a **keyed** source and be refused | fallback picks the first active source **without** an API key (keyed sources are reached on purpose only) | `routers/lead_intake.py` |
| — | Operator | — | `GET /api/health/webhook-enforcement` (super admin): shared inboxes (has key?) and ADF sources carrying an API key — names/ids only, never keys | `server.py` |

Checked and already safe (no change): `POST /api/auth/signup` (role always `user`, org applicants `pending`), team-invite links /
email invites (`role: user`, store-scoped), `POST /api/webhooks/user-created` (hotfix 3 role clamp + secret),
`setup-wizard/new-account` (`require_account_creator`), `admin_hierarchy` (4B), `PUT /api/admin/users/{id}` (hotfix 4),
`partners` (4B), `customers/invite-owner` (super admin).

Frontend (same build, no OTA needed for security — server enforces): role pickers in `app/admin/users.tsx` (create + edit) only
offer roles strictly below the signed-in admin's; `app/admin/manage-team.tsx` hides "Manager" for store managers.
`store/mediaTokenStore.ts` ignores a non-token answer from older backends (see §5).

## 3. Tests
- `tests/test_security_hotfix4c.py` (13): reproduction (now 403 for every role >= caller on both create routes, no document),
  store-manager store scope (403 / 400 / 404), org-admin ceiling + organization isolation (6 cases x 2 routes), rep + anonymous
  on every creation surface, authorized creation (super admin -> org_admin; org admin -> store_manager; store manager -> rep,
  org derived from store), approval scoping (other dealership 403/404 + not listed + reject refused; own org admin: super_admin /
  org_admin / foreign store / foreign org / foreign store_ids -> 403 with the doc unchanged; store_manager + own store -> 200),
  scoped counts + super-admin approval, add-team-member body forgery + hashing, bulk-invite ceiling, permission-template
  escalation (self / rep / custom templates / other org), individuals, webhook-enforcement report (no keys), smoke build label.
- Independent testing agent (`/app/test_reports/iteration_388.json`): `tests/test_security_hotfix4c_adversarial.py` (15): bogus /
  list-typed roles, X-User-ID spoofing, extra body fields (`account_id`, `is_owner`, `status`…), nonexistent / mismatched stores,
  template PUT role change, cross-org custom template, active-user-through-approve. **One finding**: `/approve` acted on an
  already-active user of the approver's own org (role still bounded) -> fixed (`status: pending` required, 404 otherwise); the
  probe now asserts the fix. 28/28 after the fix.
- Regression batch (4C + 4B + 4B adversarial + 4 + 3 authz + 3 adversarial + webhook scope + session cutoff + twilio tenant +
  p0 closeout + BOLA middleware + company-docs access + profile): **202 passed, 1 skipped** (`/tmp/hotfix4c_regress.log`, 4m34s).
- `python tests/prod_smoke_hotfix3.py <preview>` -> **83/83** (12 new anonymous probes on the creation / approval surfaces).
- No invite email or SMS was triggered by any test (send flags false / empty phone); every created account purged.
- Secrets: `git diff` of the 4C change contains no password / key / token literal; `.env` files untouched.
- Run: `cd /app/backend && set -a && . ./.env && . ../frontend/.env && set +a && python -m pytest tests/test_security_hotfix4c.py tests/test_security_hotfix4c_adversarial.py tests/test_security_hotfix4b.py tests/test_security_hotfix4.py tests/test_security_hotfix3_authz.py tests/test_p0_security_closeout.py -q -p no:cacheprovider -W ignore::DeprecationWarning`

## 4. Remaining findings
- None critical / high open in code. Known lower-priority items unchanged from 4B §4 (per-process rate limiter, user-bound media
  tokens, legacy non-security test suites).
- Behaviour change to communicate: store managers can no longer create or approve other **store managers** (org admins can); the
  UI hides the option. `account_manager` (not in the hierarchy table) is grantable by super admins only.

## 5. Deployment compatibility (verified)
1. **4B/4C iPhone app published BEFORE the backend — safe.** Production is on build `2026-10-14.security-hotfix3`
   (`/api/health`). The new app calls `GET /api/calls/recording-token`; on that backend the path resolves to `GET /calls/{user_id}`
   with `user_id="recording-token"`, which answers `200 []` (no 401 -> no dead-session strike, no logout). The client now stores a
   token only when the answer is a real token, so media/recording URLs stay plain and the old proxy (no `?t=` check; unknown query
   params ignored) keeps serving them. All other 4B/4C client changes are UI-only.
2. **Old app with the new backend**: MMS images / voicemail / recording playback answer 401 until the OTA lands (minutes). Everything
   else works. -> publish the OTA immediately after the backend deploy.
3. **New app with the new backend**: media token minted after login, refreshed every 100 min, cleared on logout (verified on web).
4. **Expo runtime / dependencies**: `expo ~54.0.35`, `react-native 0.81.5`, `expo-updates ~29.0.18`, `runtimeVersion.policy =
   "appVersion"`, `expo.version = 1.0.4`, channel `production` (`eas.json`). `git diff f31b6c384 HEAD -- frontend/package.json
   frontend/app.json frontend/app.config.js frontend/yarn.lock` is **empty**: no native module or version change since Hotfix 4,
   so `eas update --branch production` is runtime-compatible with the 1.0.4 binary. **Owner check**: `eas build:list` /
   App Store Connect must show the live binary is 1.0.4; a 1.0.3 binary would not receive an update published for runtime 1.0.4.
5. **Rollback documentation corrected** (also in `SECURITY_HOTFIX4B_REPORT.md` §6): Hotfix 4 = **`f31b6c384`** (`d86e1deee` is the
   same code one commit earlier). `24d8f3346` already contains 37 files of 4B work and is **not** a valid Hotfix 4 rollback.
   Hotfix 4B = `1a8193ae5` (Claude-reviewed). Hotfix 4C = the commit produced by this save.
6. **Shared-inbox / ADF configurations**: preview has 9 shared inboxes (0 with a key yet — keys are generated on first
   `webhook-info` call) and 2 of 1026 lead sources with an API key. For production: after deploy call
   `GET /api/health/webhook-enforcement` as super admin -> for every listed shared inbox used by a live web form, open Team ->
   inbox -> webhook info once and re-copy the URL (now carries `?key=`); for every ADF source listed, confirm the vendor sends
   `X-API-Key` (or `?api_key=`) — otherwise its posts answer 401 (fail closed; unkeyed sources unaffected, and the no-`source_id`
   fallback never lands on a keyed source any more).

## 6. Production deployment checklist (updated; owner's GO only)
1. Save to GitHub -> Claude final review of this build (`2026-10-14.security-hotfix4c`).
2. Confirm production secrets (`GET /api/health/security-config` after deploy, or Secrets UI before): `TWILIO_WEBHOOK_VALIDATION`
   unset/`enforce`; `PUBLIC_FACING_URL`=`https://app.imonsocial.com`; `TWILIO_ACCOUNT_SID`/`TWILIO_AUTH_TOKEN` present;
   `RESEND_WEBHOOK_SECRET`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_BILLING_WEBHOOK_SECRET` set; `JWT_SECRET` unchanged;
   `SESSIONS_VALID_AFTER` as set by hotfix 2 (never in preview `.env`).
3. Optional, safe first: `eas update --branch production --message "security hotfix 4C"` (compatible with the hotfix-3 backend, §5.1).
4. Deploy backend + web. If step 3 was skipped, publish the OTA right after.
5. Within 5 minutes: `python backend/tests/prod_smoke_hotfix3.py https://app.imonsocial.com` (aborts before any probe unless the
   build label is `2026-10-14.security-hotfix4c`; 83 read-only checks); `GET /api/health/security-config` and
   `GET /api/health/webhook-enforcement` as super admin; one real inbound SMS + one click-to-call (watch `[TwilioSig]`); open an MMS
   thread and a call recording in the app; create one rep as a store manager and approve one pending signup as an org admin.
6. Tell dealership admins with shared-inbox web forms to re-copy the webhook URL; tell ADF vendors of keyed sources to send the key.
7. Rollback: redeploy `f31b6c384` (Hotfix 4) or `1a8193ae5` (Hotfix 4B); plain redeploy, no schema/secret change; reopens the fixed
   holes. Emergency lever without rollback: `TWILIO_WEBHOOK_VALIDATION=log`.

## 7. Recommendation
**GO (conditional)** on Claude's final review and the §6.2 configuration confirmation. Preview carries 202 green security tests,
an independent adversarial pass with its single finding fixed and re-verified, and an 83-check read-only smoke that refuses to run
against the wrong build.
