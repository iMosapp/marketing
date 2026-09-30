# IMOS Portability Checklist (living document)

Goal: develop, test and run i'M On Social outside the Emergent platform (GitHub + human developers + AI coding
agents), then host it independently. This file lists **every remaining Emergent dependency** and the plan to
remove it. Update the status column whenever a dependency is removed. Started Sep 30 2026 after a full audit.

Legend: READY = works anywhere today; PARTIAL = works with caveats; MISSING = does not exist yet;
EMERGENT = requires the Emergent platform.

## A. Hard dependencies (the app cannot run outside Emergent because of these)

| # | Dependency | Where | Why it blocks | Plan | Status |
|---|---|---|---|---|---|
| A1 | Private package `emergentintegrations==0.1.1` (pip index `https://d33sy5i8bnduwe.cloudfront.net/simple/`) | `backend/requirements.txt`, root `Dockerfile`, ~35 files importing `emergentintegrations.llm.chat.LlmChat`, `llm.openai.OpenAISpeechToText/OpenAITextToSpeech`, `payments.stripe.checkout.StripeCheckout` | `pip install` fails without the index; all text AI, transcription, TTS and subscription checkout import it | Step 2: add `services/ai_client.py` over the official `openai` SDK (chat, whisper, tts) and switch the 33 LLM call sites; replace `StripeCheckout` with the `stripe` SDK already used for mystery shops; drop the package and its transitive deps (`litellm`, `google-*`, `boto3`) | EMERGENT |
| A2 | `EMERGENT_LLM_KEY` (universal key) | 33 backend files (see `docs/INTEGRATIONS.md`) | Only issued by Emergent; the models `gpt-5.2`, `gpt-4o-mini`, `whisper-1`, `tts-1` are billed through it | Step 2: use `OPENAI_API_KEY` (already present for GPT-Live) for everything; watch cost and rate limits (Tier) | EMERGENT |
| A3 | Emergent Object Storage (`https://integrations.emergentagent.com/objstore/api/v1/storage`, `OBJECT_STORAGE_KEY`) | `utils/image_storage.py` (+17 modules: photos, voice notes, recordings, card renders, PDFs, audio), served via `/api/images/{path}` | All uploaded media lives in Emergent's bucket; no other backend implemented | Step 3: S3-compatible backend (R2/S3/B2) behind the same `image_storage` interface; migrate objects with the existing list-by-prefix + get calls; keep `/api/images/{path}` URLs unchanged | EMERGENT |
| A4 | Emergent-managed production MongoDB (`MONGO_URL` injected at deploy) | production only | Data lives in Emergent's cluster; connection string only in the Secrets panel | Step 4: own Atlas cluster; `mongodump`/`mongorestore`; consolidated `ensure_indexes()`; explicit `APP_ENV` instead of the `localhost` heuristic in `services/runtime_env.py` | EMERGENT |
| A5 | Emergent hosting + ingress + custom domain `app.imonsocial.com` (+ SSL) | Deploy button, `.emergent/emergent.yml`, `frontend/start-web.sh` | Backend and web export are only deployable through Emergent | Step 5: production `Dockerfile` (backend + web export) or split web (Vercel/Pages) + API (Fly/Render/Railway); Step 8: DNS cut-over | EMERGENT |
| A6 | Production secrets stored only in the Emergent Secrets panel | all 44 backend keys | No other copy of production values; Deploy also copies preview `.env` keys into prod | Step 1 done: names documented in `backend/.env.example`. Later: export values into the new host's secret manager | PARTIAL |
| A7 | Emergent Stripe test proxy (`STRIPE_API_KEY=sk_test_emergent`) for subscriptions/quotes/partner billing | `routers/subscriptions.py` | Checkout only works through Emergent's proxy; effectively test mode only | Step 2: direct `stripe` SDK with the company's key; decide live vs test | EMERGENT |
| A8 | GitHub sync only through "Save to GitHub" (no `git remote` in the pod; platform authors commits) | `.git` | Nobody can push/pull from the build environment; `main` is force-written by the platform | Step 6: once development moves outside Emergent, protect `main`, use feature branches + PRs + CI | EMERGENT |

## B. Soft dependencies (work outside Emergent with small fixes)

| # | Dependency | Where | Plan | Status |
|---|---|---|---|---|
| B1 | Hardcoded `/app/...` paths | `routers/docs.py` (docs + `memory/PRD.md`), `routers/partner_invoices.py`, `routers/promo_videos.py`, `server.py` (marketing preview) | Step 2: derive from `Path(__file__)` / `REPO_ROOT` env | PARTIAL |
| B2 | Port conventions 8001 vs 8000 vs 8080 | `server.py`, supervisor, `backend/Procfile`, root `Dockerfile` | Step 5: read `PORT` | PARTIAL |
| B3 | `is_preview_runtime()` = `localhost` in `MONGO_URL` gates SMS/ring/number-buy guards | `services/runtime_env.py` | Step 4: explicit `APP_ENV=development|staging|production` | PARTIAL |
| B4 | Web app relies on the ingress routing `/api/*` to the backend (relative `/api`) | `frontend/services/api.ts` | Step 5: same-origin reverse proxy in the new host, or build with `EXPO_PUBLIC_BACKEND_URL` for web too | PARTIAL |
| B5 | System package `libzbar0` declared only in `.emergent/system_deps.txt` | QR decoding | Step 5: add to the Dockerfile | PARTIAL |
| B6 | Tests assume the Emergent preview (`REACT_APP_BACKEND_URL` from `frontend/.env`, live Mongo, live Twilio test numbers, literal QA passwords) | `backend/tests/_http.py`, ~188 test files | Step 7: `TEST_API_URL`, isolated test DB, fake Twilio/LLM mode, credentials from env only | PARTIAL |
| B7 | Marketing image hosted on `customer-assets.emergentagent.com` | `marketing/src/App.js` line ~51 | Copy the asset into `marketing/public` | PARTIAL |
| B8 | `frontend/vercel.json` points `/api` at a dead Fly host | `frontend/vercel.json` | Fix or remove before any Vercel web deploy | STALE |

## C. Emergent files kept in the repo on purpose (required while we still build on Emergent)

| Path | What it is | Keep until |
|---|---|---|
| `.emergent/emergent.yml` | pod/job identity and base image name; regenerated per pod | Emergent is retired |
| `.emergent/system_deps.txt` | apt packages the platform installs (`libzbar0`) | Dockerfile carries the same list |
| `.emergent/cron/*` (`webhook-crons`, `watch_crons.sh`, `dispatch_webhook.sh`, `webhook_crond.sh`, `applied.hash`) | platform-managed webhook cron ("DO NOT EDIT"), regenerated on pod start; the app's own schedules are APScheduler | Emergent is retired |
| `.emergent/markers/.restore-complete`, `.emergent/summary.txt` | generated markers | Emergent is retired |
| `frontend/plugins/health-check/*`, `frontend/plugins/visual-edits/*`, `frontend/craco.config.js` | preview dev-server tooling (health endpoint, visual edit metadata); not used by Metro builds | Emergent is retired |
| `frontend/scripts/link-global-lint-deps.js` (run by `yarn start`), `frontend/watch-patch.js` (supervisor `NODE_OPTIONS`) | container workarounds for the platform linter and inotify limits | Emergent is retired (harmless elsewhere) |
| `frontend/start-web.sh` | platform's production web start (export + serve) | replaced by the new Dockerfile |
| `memory/*.md`, `design_guidelines.json`, `test_result.md`, `deployer-agent-docs/` | notes written by/for the AI build agents; `routers/docs.py` reads `memory/PRD.md` | keep `memory/` (useful history); the rest can move once agents work from GitHub |
| `test_reports/`, `.screenshots/` (now git-ignored, still on disk) | testing-agent output | already untracked |

## D. Credentials to rotate because of past Git exposure (details in the Step 1 report)
- Super-admin account password (in `memory/test_credentials.md` history and ~397 tracked test/seed/report files).
- QA account passwords (QA store manager, QA org admin, activation tester, secondary test user).
- A Resend API key committed in `backend/.env` on Feb 21 2026 (differs from the current key; confirm it is revoked).
- A production MongoDB Atlas connection string with password committed in `memory/PRD.md` on Feb 26 2026
  (Emergent-managed cluster; ask Emergent support to rotate the DB user or confirm it was rotated when the
  cluster changed).
- GitHub history still contains all of the above until the repository history is rewritten or the secrets are rotated.

## E. Migration order (approved plan, Sep 30 2026)
1. Repo hygiene, credential safety, env + developer docs **(this step, done)**
2. Backend installable anywhere: remove `emergentintegrations`, own OpenAI key, direct Stripe, relative paths, `PORT`
3. Object storage: S3-compatible backend + object migration
4. Database: own Atlas cluster, dump/restore, consolidated indexes, `APP_ENV`
5. Local dev + containers: docker-compose, production Dockerfile / split hosting
6. CI/CD on GitHub: lint, tests, type-check, web export, EAS on tag; branch protection
7. Testing cleanup: isolated test DB, fake Twilio/LLM mode, credentials from env, fix legacy 401 tests
8. Cut-over: parallel deploy, webhooks + DNS switch, decommission Emergent deployment
9. Backlog: Android FCM, Google Calendar OAuth, Wallet certs, Twilio signature `enforce`, CRM adapters
