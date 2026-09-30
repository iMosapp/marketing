# IMOS Deployment

Snapshot Sep 30 2026. This documents how things ship **today**. The target independent architecture is tracked in
`docs/PORTABILITY.md` and will replace parts of this file in later steps.

## 1. Environments

| | Preview (build) | Production |
|---|---|---|
| Where | Emergent pod: supervisor runs backend `:8001` (`uvicorn --reload`), Expo web `:3000`, local `mongod`, marketing `serve :3001` | Emergent deployment `imos-deploy-prep.emergent.host` with custom domain **app.imonsocial.com** (backend + Expo web export behind one ingress) |
| URL | `REACT_APP_BACKEND_URL` in `frontend/.env` (changes per pod) | https://app.imonsocial.com |
| Database | local Mongo, `DB_NAME` per pod | Emergent-managed MongoDB (`MONGO_URL` injected) |
| Secrets | `backend/.env`, `frontend/.env` (never committed) | Emergent Deployments > Secrets ("Custom Keys"). **Deploy also copies preview `backend/.env` keys into production** unless overridden there, so never add a preview-only switch without gating it on `is_preview_runtime()` |
| Marketing | `marketing/build` served locally | Vercel serves the committed `marketing/build` (no build step) at imonsocial.com |
| Mobile | Expo Go / dev client against preview when `EXPO_PUBLIC_BACKEND_URL` points at it | App Store build + `eas update` channel `production` |

Routing: the ingress sends `/api/*` to the backend and everything else to the web export, so the browser app uses a
relative `/api`. Native apps use `EXPO_PUBLIC_BACKEND_URL` (baked into the bundle, default `https://app.imonsocial.com`).

## 2. Release workflow (current, manual)

1. **Save to GitHub** (Emergent chat button). Commits are authored by the platform; there is no local remote.
2. **Deploy** (Emergent UI) when anything under `backend/` changed (also rebuilds the web export). Startup
   self-heals run automatically (indexes, seeds, docs sync).
3. **`eas update`** when anything under `frontend/` changed (JS/TS/assets only). From the Mac clone:
   ```
   cd ~/imonsocial-clone/frontend && git checkout -- app.json yarn.lock 2>/dev/null; git pull && yarn install && eas update --branch production --message "$(git log -1 --pretty=%s)"
   ```
   `EXPO_PUBLIC_BACKEND_URL` / `EXPO_PUBLIC_APP_URL` must be `https://app.imonsocial.com` when publishing (eas.json
   forces them for the production build profile; check `frontend/.env` before running `eas update`).
4. **Native build** only for native changes (new permission, native module, `app.json`, icons): bump `expo.version`,
   then `eas build --platform ios --profile production --auto-submit`.
5. Marketing: Vercel picks up pushes to `marketing/`.

Users must fully close and reopen the app twice after an OTA update (first open downloads, second runs).

## 3. Rollback
- Backend/web: Emergent checkpoint rollback (platform UI). No independent rollback exists yet.
- Mobile: `eas update:republish` a previous update, or publish a fix.
- Database: no application-level backups; rely on the managed cluster's snapshots until step 4 of the portability plan.

## 4. Production checklist for secrets
Required in production: `MONGO_URL`, `DB_NAME`, `JWT_SECRET`, `APP_URL`/`PUBLIC_FACING_URL=https://app.imonsocial.com`,
`CORS_ORIGINS`, Twilio (`TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`, `TWILIO_MESSAGING_SERVICE_SID`),
Resend (`RESEND_API_KEY`, `SENDER_EMAIL`), `EMERGENT_LLM_KEY`, `OBJECT_STORAGE_KEY`, `OPENAI_API_KEY`, VAPID keys,
`STRIPE_API_KEY`/`STRIPE_SECRET_KEY`/`STRIPE_WEBHOOK_SECRET`, `ADMIN_EMAIL`, `SALES_EMAIL`.
Optional/pending: `INBOUND_EMAIL_DOMAIN`, `LEAD_SENDER_DOMAIN`, `RESEND_WEBHOOK_SECRET` (Lead Shops; **empty in
production as of Sep 29 2026**), `PICOVOICE_ACCESS_KEY`, Apple/Google Wallet certs, `TWILIO_WEBHOOK_VALIDATION=enforce`.
Full matrix: `backend/.env.example`.

## 5. Ports and process model
- Backend listens on 8001 (`server.py`, supervisor). `backend/Procfile` uses `${PORT:-8000}`, the root `Dockerfile`
  8080: three conventions, to be unified in a later step. Run **one** uvicorn worker: the scheduler lives in-process.
- Frontend dev server 3000 (`yarn start` = `expo start --web`). `frontend/start-web.sh` (export + `serve dist`) is
  the platform's production web start.
- Marketing 3001 in preview only.

## 6. Legacy / alternative deployment files (classification, Sep 30 2026)
| File | Classification | Notes |
|---|---|---|
| `frontend/eas.json`, `frontend/app.json`, `frontend/app.config.js` | ACTIVE | EAS project `imos`, bundle `com.imonsocial.app`, Apple team + ASC ids |
| `marketing/vercel.json` | ACTIVE | Vercel config for imonsocial.com incl. `/s`, `/go`, `/get` redirects |
| `frontend/start-web.sh` | ACTIVE (Emergent) | Web export + serve, used by the platform |
| `.emergent/*` | ACTIVE (Emergent) | Platform config; see PORTABILITY.md |
| `backend/Procfile` | POTENTIALLY USEFUL | Heroku/Railway style start command |
| `backend/railway.toml` | POTENTIALLY USEFUL | Railway (nixpacks) deploy config |
| `Dockerfile` (root) | POTENTIALLY USEFUL / STALE | Backend-only image, port 8080, Fly.io era; needs the private pip index |
| `fly.toml` | STALE | Dead Fly app `02221223pmwebapp`; keep only as a template |
| `frontend/vercel.json` | STALE | Rewrites `/api` to the dead Fly host; must be fixed or removed before any Vercel web deploy |
| `marketing/netlify.toml` | STALE | Netlify alternative to the Vercel config |
| `backend/scripts/pre_deploy.py` | POTENTIALLY USEFUL | Compile/import check, not wired to anything |

## 7. Testing
- Backend integration tests: `cd backend && python -m pytest tests/<file> -q`; they need the server on `:8001`
  (or `TEST_API_URL`), the live Mongo, QA accounts (`TEST_ADMIN_EMAIL`/`TEST_ADMIN_PASS` ...), and in some cases
  Twilio test numbers or the LLM. Run modules one per process (each owns its event loop). About 250 older tests still
  send bare `X-User-ID` and fail with 401 since the Sep 27 2026 security hardening.
- Frontend: `npx tsc --noEmit`, `yarn lint`. Root `tests/` = Playwright smoke scripts.
- No CI exists; nothing runs automatically on push. This is portability step 6.
