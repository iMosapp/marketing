# Security Hotfix 3 (P0): authentication / authorization close-out — Deployment Readiness Report

Date: Oct 14 2026 (preview). Status: BUILT + VERIFIED IN PREVIEW, **NOT DEPLOYED**. `JWT_SECRET` untouched. Production (`2026-10-13.voice-pilot`) still carries the holes below until the owner says GO.

## 1. Findings -> fixes -> proof

| # | Finding (Claude Code review) | Exploitable before? | Fix (where) | Locked by |
|---|---|---|---|---|
| 1 | `PATCH /api/auth/users/{user_id}` modifiable without a session | YES (anonymous 200, any user's email/phone) | `server.py bind_identity_header`: default deny for every `/api/*` route not on the public allowlist (`services/route_guard.is_public`); `{user_id}` path AND `?user_id=` query bound to the caller or a manager inside the same org/stores (`route_guard.route_user_id/query_user_id/manager_can_access`); handler re-checks with `assert_self_or_scoped_manager` | `test_security_hotfix3_authz.py::test_patch_user_email_and_phone`, `::test_user_id_routes_enforce_organization_boundaries`, adversarial `test_cross_org_patch_users_denied_and_db_untouched` |
| 2 | Identity middleware skipped all `/api/auth/*` | YES (every account route under /auth ran without a proven caller) | `/api/auth/` is no longer excluded; only the login/activation/forgot-password flows are on `PUBLIC_PREFIXES`/`PUBLIC_PATTERNS`. X-User-ID is never trusted alone: must equal the Bearer caller, stripped when unproven | `::test_auth_routes_no_longer_skip_the_identity_gate`, `::test_spoofed_x_user_id_with_a_real_token_is_refused`, `::test_anonymous_write_surface_is_exactly_the_public_allowlist` (28-route anonymous sweep) |
| 3 | `POST /api/messages/send` as another user | YES (SMS from any rep's Twilio number) | sender forced to the caller; conversation routes check ownership (owner / scoped manager), strangers get 404 (existence hidden), bulk/archive by a stranger affects 0 docs | `::test_messages_send_as_another_user`, `::test_conversation_routes_check_ownership`, adversarial conversation-ownership probes |
| 4 | `POST /api/auth/persona/{user_id}` edits any AI persona | YES | same `{user_id}` binding + `assert_self_or_scoped_manager`; `GET .../ai-prompt` closed too | `::test_persona_and_review_links`, adversarial cross-org persona probe (DB verified untouched) |
| 5 | `/api/profile/*` + review links writable by anyone | YES | writes need the owner (PUT `/api/profile`, `PUT /auth/users/{id}/review-links`); public reads (link page, congrats card) stay open and were moved to the authenticated `api` client in the app where they needed a session (`inbox.tsx`, `congrats/[cardId].tsx`) | `::test_profile_writes_need_the_owner_reads_stay_public`, `::test_congrats_card_page_needs_no_session`, adversarial `social_links` regression |
| 6 | `POST /api/auth/test-login` had no brute-force protection | YES (unlimited password guesses, bypassed the lockout on `/auth/login`) | endpoint removed: permanent **410 Gone**, no diagnostic leakage. Real login keeps `_check_login_lockout` (8 fails -> 429 lockout) | `::test_test_login_is_gone`, adversarial `test-login` probe |

Also closed in the same change (found while verifying): external webhooks (`/api/webhooks/user-created|user-deleted|contact-created|event`, `/api/webhooks/inventory/*`) fail closed without `X-Webhook-Secret`/`X-API-Key` and are bound to the authenticated organisation (body `role`/`organization_id` cannot elevate or cross orgs; new users are created as `user` in that org; cross-org `store_id` -> 400); short links (`/api/s`) mint only for a session and attribute `user_id` to the caller; `change-password` / `complete-onboarding` bound to the caller; `/api/notifications`, `/api/chat/leads`, `/api/team-chat/channels`, `/api/broadcast` query identity bound.

Follow-up from the independent probe (Oct 14): webhook auth now runs as a FastAPI dependency (`Depends(verify_webhook_signature)` / `Depends(verify_api_key)`), so an anonymous caller gets **401 before body validation** (no required-field disclosure through 422). Cross-user conversation routes intentionally answer **404** (hide existence) — documented here instead of changing to 403.

## 2. Test evidence (preview, Oct 14 2026)
- `tests/test_security_hotfix3_authz.py` 19/19 (anonymous / other rep / foreign manager / own manager / super admin on every route).
- `tests/test_security_hotfix3_adversarial.py` 21/21 + `tests/test_security_hotfix3_webhook_scope.py` 1/1 (independent testing agent, `/app/test_reports/iteration_385.json`).
- Regression in the same run: `test_session_cutoff.py` 12, `test_session_restore.py` 6, `test_company_docs_access.py` 7, `test_preview_only_flags.py` 3 -> **69/69 green**.
- Legacy suites repaired to real JWT sessions (`tests/live_auth.py`), frontend inbox / link page / congrats page verified with the authenticated client.
- Run everything: `cd /app/backend && set -a && . ./.env && . ../frontend/.env && set +a && python -m pytest tests/test_security_hotfix3_authz.py tests/test_security_hotfix3_adversarial.py tests/test_security_hotfix3_webhook_scope.py -q`

## 3. What ships
- Backend only for the security fixes (`server.py`, `services/route_guard.py`, `routers/auth.py`, `profile.py`, `messages.py`, `short_urls.py`, `webhooks.py`, `inventory_webhooks.py`, `congrats_cards.py`). `BUILD = "2026-10-14.security-hotfix3"`.
- Frontend (needs `eas update`): `inbox.tsx` and `congrats/[cardId].tsx` use the authenticated `api` client (otherwise those two screens get 401 on the new backend); plus the recording-bar fix from the same day (see PRD).
- No DB migration, no env change, no secret rotation. `JWT_SECRET` stays (Fernet key for Twilio tenant tokens / inventory feeds / contact-file links).

## 4. Deploy order (on the owner's GO only)
1. Save to GitHub.
2. Deploy (backend). `SESSIONS_VALID_AFTER` for hotfix 2 is created by hand in Secrets = the UTC minute of this deploy (never in preview `.env`).
3. Verify: `curl -s https://app.imonsocial.com/api/health` -> `"build": "2026-10-14.security-hotfix3"`, then `cd /app/backend && python tests/prod_smoke_hotfix3.py` (anonymous, read-only: 28 probes must answer 401/410, public pages 200).
4. `cd frontend && git pull && yarn install && eas update --branch production --message "$(git log -1 --pretty=%s)"` so inbox / congrats / recording bar reach devices (old bundle: inbox + congrats show 401 until updated).
5. Rollback: checkpoint `fac70ee70` (= production today) -> Rollback -> Deploy. Roll forward only afterwards: any checkpoint at or before it reopens all six holes.

## 5. Residual / out of scope (unchanged, documented)
- Stripe legacy unsigned webhook fallbacks (P2), Twilio signature `log` mode, partner billing header-only auth: pre-existing, listed in `LAUNCH_READINESS_AUDIT.md`.
- Owner steps after hotfix 2 remain: password rotations, Atlas credential confirmation, Resend key revocation.
