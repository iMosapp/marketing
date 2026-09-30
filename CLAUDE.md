# CLAUDE.md - guide for AI coding agents working on i'M On Social (IMOS)

You are working on a production SaaS with paying dealership customers and real customer conversations in the
database. Read this file, then `README.md`, `docs/ARCHITECTURE.md`, `docs/PRODUCT_RULES.md` and
`docs/PORTABILITY.md` before changing anything.

## What IMOS does
Relationship OS for sales teams (automotive/equipment dealerships first): a business-number SMS/voice inbox with an AI
assistant ("Jessi") that drafts and sends texts, calls customers, hosts calls and onboards reps; digital business cards
and congratulations cards; touchpoints, tasks, campaigns and lead routing; manager tools (leaderboards, call
scorecards, weekly digests); AI mystery-shop training calls and covert Lead Shops for dealership QA; a website widget
(Text Us / Call Me Now / Jessi chat) installed with one script tag; multi-tenant Twilio with 10DLC compliance;
Stripe billing and a partner/white-label program.

## Architecture in one screen
- **Frontend** `frontend/` - Expo SDK 54 / React Native 0.81 / React 19 / TypeScript / Expo Router. `app/` = routes
  (353 screens), `components/` (251), `services/api.ts` (axios; web = relative `/api`, native =
  `EXPO_PUBLIC_BACKEND_URL`), `hooks/`, `store/` (zustand), `contexts/`. Compile-time Babel plugins add font caps,
  keyboard dismissal, modal keyboard avoidance and `testID`s to every component. Ships as iOS app (EAS OTA), Android
  (unpublished) and web at app.imonsocial.com.
- **Backend** `backend/` - FastAPI on Python 3.11. `server.py` mounts 138 routers under `/api`, runs security
  middleware (`bind_identity_header`, `enforce_user_ownership`, path-aware CORS), startup self-heals, the WebSocket
  hub and the in-process APScheduler (45+ jobs, **single worker only**). Domain logic in `services/` (86 modules).
- **Database** - MongoDB via Motor, ~194 collections, ObjectId ids, no ORM. Media is NOT in Mongo: it is in object
  storage and referenced by path (`/api/images/{path}`). See `docs/DATABASE.md`.
- **Realtime voice** - Twilio media streams bridged to OpenAI GPT-Live (`services/live_shops.Bridge`), Twilio
  ConversationRelay fallback, WebRTC in the app for Jessi Live.
- **Integrations** - Twilio, Resend, Stripe, OpenAI GPT-Live (own key), OpenAI text/Whisper/TTS through the
  Emergent `emergentintegrations` library, Expo Push + Web Push, Emergent Object Storage, Picovoice, Apple/Google
  Wallet, GoHighLevel. Table with env vars: `docs/INTEGRATIONS.md`.

## Multi-tenant model
`organizations` -> `stores` -> `users` (roles `super_admin`, `org_admin`, `store_manager`, `user`; plus partner
accounts). Customer data (`contacts`, `conversations`, `messages`, `tasks`, `campaigns`, cards ...) is owned by
`user_id`; store/org scoping via `store_id` / `organization_id`. Mystery-shop customers are `shop_clients`
(iMOS-admin-only tenants). Every data query must be scoped with `routers/database.py` helpers or the `routers/rbac.py`
dependencies (`require_store_access`, `require_org_access`, `require_user_access`, `bind_query_user`).

## Authentication
Custom JWT (PyJWT HS256, 30 days, `JWT_SECRET`), bcrypt passwords, Mongo-backed lockout, activation and reset
links, impersonation tokens (`impersonate_*`). `X-User-ID` is a legacy header that the middleware binds to the
verified bearer token; never trust it alone and never add a route that relies on it without `Authorization`.
Frontend keeps the token in AsyncStorage (`services/api.ts` interceptor); raw `fetch()` calls must add the header.

## Important directories
| Path | Purpose |
|---|---|
| `backend/server.py` | app wiring, middleware, startup, websocket, scheduler start |
| `backend/routers/` | HTTP API; `mystery_shops.py`, `messages.py`, `twilio_webhooks.py`, `auth.py`, `admin*.py` are the big ones |
| `backend/services/` | domain logic; `twilio_service`, `live_shops`, `live_voice`, `mystery_shops`, `lead_shops`, `widgets`, `jessie_service` |
| `backend/utils/text_sanitize.py` | `no_em_dash()`, `clean_ai_text()`: mandatory on all AI output |
| `backend/utils/image_storage.py` | object storage client (Emergent today) |
| `backend/scheduler.py` | all scheduled jobs |
| `backend/tests/` | integration tests + seed scripts (see Testing) |
| `frontend/app/` | screens; `(tabs)/`, `admin/`, `thread/[id].tsx`, public pages (`guide/`, `shop-score/`, `congrats/`) |
| `frontend/components/` | UI; `ui/` primitives, `common/SheetGrabber.tsx`, `mystery-shops/`, `thread/`, `widget/` |
| `frontend/babel-plugin-*.js`, `babel.config.js` | compile-time behaviour; clear `.metro-cache`/`node_modules/.cache` after edits |
| `docs/` | architecture, database, integrations, deployment, product rules, portability |
| `memory/PRD.md`, `memory/CHANGELOG.md` | dated decisions and shipped work; append, do not rewrite history |
| `.emergent/` | platform files; do not edit or delete while the project is built on Emergent |

## Coding conventions found in the project
- Python: services are plain modules with module-level constants; routers use Pydantic `*Body` models, `require_*`
  dependencies, `serialize_*` output helpers, `HTTPException` with plain-English `detail`. Datetimes are
  `datetime.now(timezone.utc)`; Mongo returns naive datetimes, make them aware before subtracting. Wrap `me["_id"]`
  in `ObjectId(...)` when updating users (it is a string after auth). Log with `logger = logging.getLogger(__name__)`
  and `[Tag]` prefixes. Any new fetch of a user-supplied URL goes through `services/safe_fetch.safe_client()`.
- Every AI text path: `no_em_dash()` / `clean_ai_text()`; prompts use the persona resolver
  (`services/persona_gender.describe`).
- Preview-only behaviour switches must be gated on `services/runtime_env.is_preview_runtime()`; assume every `.env`
  key reaches production.
- TypeScript: named exports for components, default exports for screens, small components, `tid('x')` /
  `data-testid` on every interactive or informative element (kebab-case, function not style), `useToast` for
  feedback, `Sheet`/`SheetGrabber` for bottom sheets, no hand-added `KeyboardAvoidingView`/`maxFontSizeMultiplier`.
- Comments are rare and one line; no multi-paragraph docstrings. Keep diffs focused: do not refactor around a fix.
- i18n: public shop pages support `en-US`, `en-GB`, `en-IE`, `nl-NL`, `nl-BE` (`services/locales.py`, `frontend` i18n
  keys). Do not hardcode English into those pages.

## How to inspect existing functionality before modifying it
1. Find the route: `grep -rn "\"/your-path" backend/routers` and read the whole handler plus the service it calls.
2. Check who else uses the service function (`grep -rn "function_name(" backend`), including `scheduler.py`
   (jobs), `twilio_webhooks.py`/`resend_webhooks.py` (webhooks), `live_*.py` (voice delegations) and the frontend
   (`grep -rn "/your-path" frontend/app frontend/components frontend/services frontend/hooks`).
3. Check feature flags in Test Lab (`routers/lab.py`, `settings` collection) and per-client toggles
   (`shop_clients`, `stores`) that may gate the behaviour.
4. Look at the dated entry in `memory/PRD.md` for the why; many "odd" behaviours are deliberate owner decisions
   (see `docs/PRODUCT_RULES.md`).
5. Reproduce on the preview with curl (`REACT_APP_BACKEND_URL` in `frontend/.env`) or a screenshot before changing
   code; add a regression test next to the existing ones.

## Testing (current limitations)
- Backend tests are **integration tests** against a running server (`http://localhost:8001` or `TEST_API_URL`) and
  the live Mongo. Many log in as QA accounts, use Twilio test numbers (`+1500555xxxx`) and some call the LLM. Run
  one module per pytest process (`cd backend && python -m pytest tests/test_x.py -q`). ~250 legacy tests still send
  bare `X-User-ID` and fail with 401. There is no isolated test DB or mock mode yet (portability step 7).
- Credentials for QA accounts come from `TEST_ADMIN_EMAIL` / `TEST_ADMIN_PASS` etc. in your shell (see
  `backend/.env.example`). Never write them into files that get committed.
- Frontend: `npx tsc --noEmit`, `yarn lint`; no unit tests. Root `tests/` holds Playwright smoke scripts.
- In the Emergent preview only `+1500555xxxx` numbers and `@invalid.imonsocial.test` emails are safe; several buttons
  ring the owner's real phone.

## Current Emergent dependencies (do not try to remove them unless the task says so)
`emergentintegrations` package + private pip index, `EMERGENT_LLM_KEY` (all text AI/Whisper/TTS), Emergent Object
Storage (`OBJECT_STORAGE_KEY`), Emergent-managed production MongoDB, Emergent hosting and Secrets panel for
`app.imonsocial.com`, Emergent Stripe test proxy for subscriptions, "Save to GitHub" as the only push path. Full
list and plan: `docs/PORTABILITY.md`.

## Mandatory rules
- **NEVER modify production customer data for testing.** Use preview/local data and QA accounts only.
- **NEVER expose credentials** in output, logs, screenshots, comments or docs.
- **NEVER commit secrets.** `.env` files, keys, certificates and test credentials stay out of Git (`.gitignore`
  enforces this; `.env.example` files hold placeholders only).
- **NEVER bypass organization or tenant isolation.** Every query is scoped by `user_id` / `store_id` /
  `organization_id` through the RBAC helpers; never trust `X-User-ID` alone.
- **NEVER deploy directly to production without explicit human approval.** The owner runs Deploy and `eas update`.
- **NEVER perform a destructive database migration without an explicit migration and rollback plan** written down
  and approved first.
- **NEVER assume a feature is unused merely because it appears unreferenced** without checking dynamic imports,
  the router list in `server.py`, `scheduler.py` jobs, webhooks (`twilio_webhooks.py`, `resend_webhooks.py`,
  Stripe), live-voice delegations, public pages and the mobile app.
- **ALWAYS preserve backwards compatibility** (API shapes, stored document fields, public URLs, webhook paths)
  unless the task explicitly authorizes a breaking change.
- **ALWAYS work in a feature branch** once the independent GitHub workflow is established (today the Emergent
  platform writes `main` directly; do not fight it until step 6 of the portability plan).
- **ALWAYS run applicable tests before requesting merge approval** (the module's pytest file, `tsc --noEmit`,
  and a preview smoke check for UI changes).
- ALWAYS end a code-changing reply with the owner's "Ship it" block (Save to GitHub, Deploy, the exact `eas update`
  command) and record behaviour changes in `memory/PRD.md`.
