# P0 Security Close-Out: production runbook (Oct 11 2026)

## Release contents
- Backend only. `git diff 495482d2a -- frontend` is empty: no OTA / EAS update, no native build.
- Files: `routers/{setup_wizard,team_invite,onboarding_settings,scheduler_admin,email,subscriptions,rbac}.py`, `server.py` (`PRIVATE_PREFIXES` + `BUILD = "2026-10-11.p0-security"`), tests only otherwise.
- No database migration, no new env var, no secret change.

## Pre-deploy checks (done Oct 11 2026)
1. Delta vs checkpoint `495482d2a` = P0 files only (see above).
2. Role compatibility: `tests/test_p0_security_closeout.py` + 5 repaired suites, 125 passed against the preview API with real JWT sessions for rep / store_manager / org_admin / super_admin.
3. Public flows kept: `GET /team-invite/validate/{code}`, `validate-email/{code}`, `POST /team-invite/join`, `POST /team-invite/accept`, `GET /subscriptions/plans`, `discount-codes/validate/{code}`, quote `public|accept|create-payment|payment-status`, `checkout`, `w9/{token}`.
4. Frontend consumers all go through `services/api.ts` axios client (Bearer injected on every call since the Sep 27 2026 security model), so the live OTA bundle is compatible.
5. No external/machine consumers of the secured routes: not in `.emergent/crons.yml`, `marketing/`, `scripts/`, backend services, or docs. Only the in-app screens.
6. Known behaviour change beyond owner/manager/rep/super-admin: partner (reseller) org admins can still list their own accounts (`partner/accounts` scoped by `assert_partner_scope`) but quote create/edit/send and discount codes are now super_admin only. No quote in preview carries a `partner_id`.

## Deploy
1. Save to GitHub.
2. Deploy (backend). Expect ~3-6 min.
3. Verify: `curl -s https://app.imonsocial.com/api/health` -> `"build": "2026-10-11.p0-security"`.

## RESULT (Oct 11 2026)
- Deployed 12:17-12:22 UTC, outcome "Clean". Health build tag flipped from `2026-10-10.intel-2a` to `2026-10-11.p0-security` at 12:22:27 UTC (one ~30 s edge 520 during the pod swap, then 200).
- Anonymous smoke: 17 GET + 11 POST/PUT/DELETE probes all 401; public flows all as expected (see list below). Authenticated owner/manager checks pending the owner's own login.

## Production smoke tests (read-only, no customer data touched)
- Anonymous, must be 401: `/api/setup-wizard/clients`, `/api/team-invite/user/<any>/invite-link`, `/api/onboarding-settings/global`, `/api/scheduler/status`, `/api/subscriptions/my-subscription?email=x@y.z`, `/api/email/templates/<any>`, `/api/subscriptions/quotes`.
- Anonymous, must stay public: `/api/subscriptions/plans` 200, `/api/team-invite/validate/zzzzzzzz` 404 (unknown code, route alive), `/api/subscriptions/discount-codes/validate/NOPE` 200.
- Owner (forest@imonsocial.com) in the app: Hub -> Onboarding Hub loads recent accounts; Setup Wizard opens; Discount Codes / Quotes lists load; Email templates load. A store manager: Team invite link renders.

## Rollback (instant, no data impact)
1. Emergent chat -> Rollback -> choose checkpoint `495482d2a` ("checkpoint: before P0 security close-out").
2. Deploy again. `/api/health` build returns to `2026-10-10.intel-2a`.
3. Nothing to undo in Mongo: P0 wrote no data and changed no schema.
Trigger rollback if: owner cannot open Onboarding Hub / Setup Wizard, invite links fail for managers, `/join/{code}` or `/auth/activate` fail for a new hire, or the health build tag never flips (deploy failed).
