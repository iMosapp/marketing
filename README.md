# i'M On Social (IMOS)

**i'M On Social** is a relationship-management platform for sales teams (built first for automotive and equipment
dealerships). Sales reps text and call customers from a business number, run AI-assisted follow-ups ("Jessi", the
built-in AI assistant), send digital business cards and congratulations cards, track touchpoints and tasks, and
managers get leaderboards, call scorecards, mystery-shop training calls, lead routing and CRM integrations.
Dealerships can also install a website widget (web-to-SMS, instant callback, AI chat) with a single script tag.

This repository contains the whole product:

| Part | Path | Technology | Ships as |
|---|---|---|---|
| Mobile + web app | `frontend/` | Expo SDK 54, React Native 0.81, React 19, TypeScript, Expo Router | iOS app (App Store), Android app (not yet published), web app at `app.imonsocial.com` |
| API + background jobs | `backend/` | Python 3.11, FastAPI, Motor (MongoDB), APScheduler, WebSockets | `app.imonsocial.com/api/*` |
| Marketing site | `marketing/` | Create React App (static export, prebuilt `build/` committed) | `imonsocial.com` via Vercel |
| Internal docs | `docs/` | Markdown (some are synced into the app's Admin > Docs screen on deploy) | |

> **Current limitation (read this first):** IMOS cannot yet be run completely outside the Emergent platform.
> The backend depends on the private `emergentintegrations` package (installed from a private index), the
> `EMERGENT_LLM_KEY` for all text AI / transcription / TTS, Emergent Object Storage for uploaded media, an
> Emergent-managed production MongoDB, and Emergent hosting for `app.imonsocial.com`. The full list and the
> plan to remove each dependency live in [`docs/PORTABILITY.md`](docs/PORTABILITY.md). Everything else (Twilio,
> Resend, Stripe, GPT-Live voice, Expo/EAS, Vercel) uses the company's own accounts.

## Repository structure

```
/
├── backend/                 FastAPI application
│   ├── server.py            entry point: middleware, /api router mounting, startup tasks, websocket
│   ├── routers/             138 routers = HTTP API surface (all mounted under /api)
│   ├── services/            86 domain services (twilio, live voice, mystery shops, lead shops, widgets, ...)
│   ├── scheduler.py         APScheduler jobs (45+), started in-process by server.py
│   ├── utils/               helpers (text sanitising, image/object storage, ...)
│   ├── models.py, models/   Pydantic request/response models
│   ├── migrations/          one-off data migrations (hash_passwords.py)
│   ├── scripts/             operational scripts (pre_deploy.py, migrate_images.py, seeds)
│   ├── tests/               pytest suites + seed/probe scripts (run against a live server + Mongo)
│   ├── requirements.txt     pinned Python dependencies
│   └── .env.example         every backend environment variable, documented
├── frontend/                Expo / React Native app (iOS, Android, web)
│   ├── app/                 353 screens, file-based routes (Expo Router)
│   ├── components/          251 shared components (components/ui = shadcn-style primitives)
│   ├── services/api.ts      axios client; web uses same-origin /api, native uses EXPO_PUBLIC_BACKEND_URL
│   ├── hooks/ store/ utils/ contexts/ constants/
│   ├── babel-plugin-*.js    compile-time plugins (font cap, keyboard dismiss, modal KAV, data-testid)
│   ├── app.json, eas.json   Expo + EAS configuration (bundle id com.imonsocial.app)
│   └── .env.example         every frontend environment variable, documented
├── marketing/               static marketing site (imonsocial.com); build/ is committed and served by Vercel
├── docs/                    architecture, database, integrations, deployment, product rules, portability
├── memory/                  running product notes kept by the AI build agents (PRD.md, CHANGELOG.md, ...)
├── tests/                   Playwright smoke scripts for the production web build
├── CLAUDE.md                instructions and hard rules for AI coding agents working in this repo
└── .emergent/               Emergent platform files (required while hosted on Emergent; see docs/PORTABILITY.md)
```

## Required software (local development)

- Python 3.11 and `pip`
- Node.js 18+ and **Yarn 1.x** (`npm` is not used for the frontend; lockfile is `yarn.lock`)
- MongoDB 6/7 (local `mongod`, Docker, or an Atlas cluster)
- Expo CLI via `npx expo` (bundled), EAS CLI (`npm i -g eas-cli`) only for publishing the mobile app
- Optional: Xcode / Android Studio for native simulators

## Installing dependencies

```bash
# backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install --extra-index-url https://d33sy5i8bnduwe.cloudfront.net/simple/ -r requirements.txt
#   ^ the extra index is required for the private `emergentintegrations` package (Emergent dependency).
#     Without access to that index the install fails; see docs/PORTABILITY.md.

# frontend
cd frontend
yarn install

# marketing (only if you change the site)
cd marketing && npm install
```

System package needed by the backend image: `libzbar0` (QR decoding; declared in `.emergent/system_deps.txt`).

## Environment configuration

1. `cp backend/.env.example backend/.env` and fill in values. Minimum to boot: `MONGO_URL`, `DB_NAME`, `JWT_SECRET`,
   `APP_URL`. Texting/voice need Twilio keys; email needs Resend; AI text features need `EMERGENT_LLM_KEY`
   (Emergent only); GPT-Live voice needs `OPENAI_API_KEY`.
2. `cp frontend/.env.example frontend/.env`. On web nothing is strictly required (the app calls same-origin
   `/api`); native builds need `EXPO_PUBLIC_BACKEND_URL` and `EXPO_PUBLIC_APP_URL`.
3. Never commit `.env` files. `.gitignore` blocks them; the `.env.example` files are the documented templates.

Behaviour switch worth knowing: `backend/services/runtime_env.py` treats a `MONGO_URL` containing `localhost`
as a **preview** runtime and enables the safety guards (`SMS_SEND_ONLY_TO`, `WIDGET_RING_DRY_RUN`,
`LEAD_SHOP_BUY_NUMBERS=false`) so local development never texts or calls real people.

## Running the backend

```bash
cd backend
uvicorn server:app --host 0.0.0.0 --port 8001 --reload
# health: curl http://localhost:8001/api/health   deep check: /api/health/deep
```

The scheduler starts inside the same process (single worker only: `--workers 1`). Startup also runs idempotent
"self-heal" tasks (indexes, seeded demo data, docs sync) that are safe to repeat.

## Running the frontend

```bash
cd frontend
yarn start          # Expo web on http://localhost:3000 (proxy /api to the backend or set EXPO_PUBLIC_BACKEND_URL)
yarn ios / yarn android   # native simulators (Expo Go or a dev client)
yarn build:web      # static web export to frontend/dist
```

On the Emergent preview the platform ingress routes `/api/*` to port 8001 and everything else to the Expo web
server on port 3000, which is why the web app can use a relative `/api`. Locally, either run both behind one
proxy (e.g. nginx / `vercel dev`-style rewrite) or set `EXPO_PUBLIC_BACKEND_URL` for native testing.

## Testing (current state)

- Backend: `cd backend && python -m pytest tests/test_<area>.py -q`. The suites are **integration tests**: they
  call the running server (default `http://localhost:8001`, or `TEST_API_URL` / `REACT_APP_BACKEND_URL`) and
  the live Mongo, log in with QA accounts, and some use real Twilio test numbers (500-555-01xx) or the LLM.
  There is no isolated test database or mock mode yet. Set `TEST_ADMIN_EMAIL` / `TEST_ADMIN_PASS` (and friends)
  in your shell; many tests still fall back to literal QA passwords, which is a known cleanup item.
- Frontend: no unit tests. `npx tsc --noEmit` type-checks; `yarn lint` runs eslint. Root `tests/` holds Playwright
  smoke scripts for the production web build.
- Full-flow QA on Emergent is done by the platform's testing agent (reports in `test_reports/`, ignored by git).

Details: [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md#testing) and [`CLAUDE.md`](CLAUDE.md#testing).

## Current deployment architecture (as of Sep 2026)

| Piece | Where | How it ships |
|---|---|---|
| Backend API + web app | Emergent hosting, custom domain `app.imonsocial.com` (`imos-deploy-prep.emergent.host`) | "Save to GitHub" then "Deploy" in the Emergent UI |
| Production MongoDB | Emergent-managed cluster | `MONGO_URL` injected by Emergent |
| Production secrets | Emergent Deployments > Secrets panel | manual edits + redeploy |
| iOS app | App Store (EAS project `imos`, bundle `com.imonsocial.app`) | `eas update --branch production` for JS/OTA; `eas build --platform ios --profile production --auto-submit` for native changes |
| Marketing site | Vercel project connected to this GitHub repo (`marketing/`, no build step) | picked up on push |

Step-by-step release procedure, rollback notes and the ports used in each environment: [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).

## Deeper documentation

| Document | Content |
|---|---|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | request flow, backend layering, frontend structure, background jobs, realtime voice |
| [`docs/DATABASE.md`](docs/DATABASE.md) | MongoDB collections, tenancy fields, indexes, migrations |
| [`docs/INTEGRATIONS.md`](docs/INTEGRATIONS.md) | every external service, the env vars it needs, and where it is used |
| [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) | environments, release workflow, secrets, testing |
| [`docs/PRODUCT_RULES.md`](docs/PRODUCT_RULES.md) | non-negotiable product behaviours (AI tone rules, texting compliance, tenancy) |
| [`docs/PORTABILITY.md`](docs/PORTABILITY.md) | living checklist of Emergent dependencies and the migration plan |
| `docs/APP_SCOPE.md`, `docs/OPERATIONS_MANUAL.md`, `docs/PRODUCT_REQUIREMENTS.md`, `docs/TECH_STACK.md` | older internal docs, synced into Admin > Docs |
| `memory/CHANGELOG.md`, `memory/PRD.md` | dated log of shipped work and product decisions |
| [`CLAUDE.md`](CLAUDE.md) | rules and orientation for AI coding agents |
