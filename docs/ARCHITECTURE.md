# IMOS Architecture

Status: written Sep 30 2026 from a read-only audit of the repository. Update it when the shape changes.

## 1. Big picture

```
 iPhone / Android app ──┐                          ┌── Twilio (SMS, voice, ConversationRelay, media streams)
 (Expo, EAS OTA)        │  HTTPS /api/*  + WSS     │── OpenAI GPT-Live (realtime voice, own key)
 Web app (Expo web) ────┼──────────────▶ FastAPI ──┼── OpenAI text/Whisper/TTS via emergentintegrations (Emergent key)
 app.imonsocial.com     │               backend    │── Resend (email out + inbound webhook)
 Website widget (JS) ───┘  /api/w/*     │          │── Stripe (subscriptions via Emergent proxy; own key for shop billing)
 Marketing site (Vercel) /s/* redirects ┘          │── Expo Push + Web Push (VAPID)
                                        │          │── Emergent Object Storage (media)
                                        ▼          └── Picovoice, Nominatim, GoHighLevel, Apple/Google Wallet
                                   MongoDB (194 collections)
                                        ▲
                              APScheduler (in-process, 45+ jobs)
```

One FastAPI process serves the API, the WebSocket hub and the scheduler. The web frontend is a static Expo export
served next to the API by the host (same origin, so the browser calls a relative `/api`). Native apps call
`EXPO_PUBLIC_BACKEND_URL`.

## 2. Backend (`backend/`)

### Entry point: `server.py`
- Creates the FastAPI app, registers middleware, mounts every router under `APIRouter(prefix="/api")`, exposes
  `/api/health`, `/api/health/deep`, `/health`, `/`, the WebSocket `/api/ws/{user_id}` and a handful of legacy
  routes, then runs startup tasks and starts `scheduler.py`.
- Middleware order matters:
  1. `PathAwareCORS` - allowlist from `CORS_ORIGINS` (+ `*.imonsocial.com`), wide open only for public lead-intake
     prefixes (`/api/demo-requests`, `/api/public/go-card`, `/api/w/`).
  2. `bind_identity_header` - `X-User-ID` is never trusted alone; it must equal the user proven by
     `Authorization: Bearer <jwt | impersonate_*>` or it is injected from the token.
  3. `enforce_user_ownership` - BOLA guard for `/{user_id}/` path segments on contacts, tasks, campaigns, etc.
- Startup self-heals (idempotent, run on every boot): index creation (`inbound_message_dedup` unique + TTL), docs
  sync from `docs/*.md` into the `docs` collection, Kubota demo shop client, call guides, sample shop, platform
  Twilio number assignment to `ADMIN_EMAIL`'s user, persona gender backfill.

### Layers
| Layer | Location | Role |
|---|---|---|
| Routers | `routers/*.py` (138) | HTTP handlers, request models (Pydantic), auth deps, serialisation (`serialize_*` helpers) |
| Services | `services/*.py` (86) | Domain logic: `twilio_service`, `live_shops`, `live_voice`, `mystery_shops`, `lead_shops`, `widgets`, `widget_chat`, `call_guides`, `scorecards`, `jessie_service`, `ai_reply`, ... |
| Utils | `utils/*.py` | `text_sanitize` (em-dash ban, banned words), `image_storage` (object storage client + disk cache) |
| Models | `models.py`, `models/` | Pydantic schemas (users, personas, inventory, SOPs) |
| Scheduler | `scheduler.py` | `AsyncIOScheduler`; every job wrapped by `safe_job()`; single-worker requirement |
| Realtime | `websocket_manager.py` | per-user WebSocket connections for inbox/live updates |

### Authentication & tenancy (see `docs/DATABASE.md` for fields)
- `routers/auth.py`: signup/login, bcrypt (legacy plaintext migrated by `migrations/hash_passwords.py`), PyJWT
  HS256 tokens (30 days, `JWT_SECRET`), Mongo-backed lockout (`login_attempts`), reset codes, activation links.
- Roles: `super_admin` (platform owner), `org_admin` (organization), `store_manager` (store), `user` (rep), plus
  partner accounts for the referral/partner program. Impersonation tokens `impersonate_*` resolved in
  `routers/rbac.py`.
- Scope helpers: `routers/database.py` (`get_accessible_user_ids`, `get_data_filter`, `verify_user_access`) and
  `routers/rbac.py` (`require_store_access`, `require_org_access`, `require_user_access`, `bind_query_user`).
  Every admin route must use these; never trust `X-User-ID` on its own.

### Key domains (where to look)
| Domain | Routers | Services |
|---|---|---|
| Messaging inbox (SMS/MMS, AI replies, drafts, delivery receipts) | `messages.py`, `twilio_webhooks.py`, `ai_reply.py`, `shared_inboxes.py` | `twilio_service.py`, `twilio_errors.py`, `ai_outreach_service.py`, `intent_detection.py` |
| Contacts, tasks, touchpoints, campaigns | `contacts.py`, `tasks.py`, `campaigns.py`, `ai_campaigns.py`, `home_intelligence.py` | `contact_ask.py`, `appointment_changes.py` |
| Jessi (AI assistant): chat, live voice, drafts, onboarding | `voice.py`, `live_voice.py`, `jessi_onboarding.py` | `jessie_service.py`, `live_voice.py`, `live_actions.py`, `live_host.py`, `live_interview.py` |
| Mystery shops / lead shops / call guides / scorecards | `mystery_shops.py` (+ `public_router`), `scripts.py`, `lead_shops.py` | `mystery_shops.py`, `live_shops.py`, `text_shops.py`, `email_shops.py`, `lead_shops.py`, `call_guides.py`, `kubota_pack.py`, `persona_gender.py`, `voice_samples.py`, `scorecards.py` |
| Website widget (Text Us / Call Me / Jessi chat) | `website_widget.py`, `chat_widget.py` | `widgets.py`, `widget_js.py`, `widget_chat.py`, `widget_crawl.py`, `widget_calls.py`, `safe_fetch.py` |
| Cards, wallet passes, QR, short links | `congrats_cards.py`, `digital_card.py`, `wallet_pass.py`, `short_urls.py` | `image_storage` |
| Multi-tenant Twilio, compliance | `org_twilio.py`, `twilio_admin.py`, `compliance.py` | `twilio_tenant.py`, `twilio_compliance.py` |
| Billing | `subscriptions.py`, `partner_billing.py`, `partner_invoices.py`, mystery-shop proposals | Stripe |
| Admin | `admin.py`, `admin_users.py`, `admin_hierarchy.py`, `white_label.py`, `docs.py`, `lab.py` (Test Lab feature flags) | |

### Realtime voice
- GPT-Live: `services/live_shops.Bridge` relays a Twilio media stream (`audio/pcmu` 8 kHz) to
  `wss://api.openai.com/v1/live/sessions` (model `gpt-live-1`, `OPENAI_API_KEY`). Subclasses handle the shopper,
  the host and the interview. Watchdogs: `READY_DEADLINE_S`, `FIRST_VOICE_S`, minute caps.
- Fallback: Twilio ConversationRelay (`routers/scripts.relay_twiml`, voices from `services/locales.py`) for
  Dutch clients and whenever the key is missing.
- Browser: `hooks/liveRtc.web.ts` / `liveRtc.native.ts` (WebRTC) for Jessi Live in the app.

## 3. Frontend (`frontend/`)
- Expo Router: every file in `app/` is a route; `app/(tabs)/` is the tab bar; `app/_layout.tsx` wires providers
  (auth, theme, toast, Live Jessi, WebSocket). Public (no-login) routes are listed in the layout (`publicRoutes`).
- Data: axios (`services/api.ts`) with the JWT from AsyncStorage; `hooks/useWebSocket.ts` for live updates;
  zustand for small cross-screen state (`store/draftStore.ts`).
- UI kit: `components/ui/*` primitives; feature components grouped by domain; sheets use `SheetGrabber`.
- Compile-time Babel plugins (`babel.config.js`) inject accessibility/keyboard/testid behaviour into every
  `Text`, `TextInput`, `ScrollView`, `Modal` in `app/` and `components/`.
- Web-specific: relative `/api`, `window.history` navigation in tests, `public/` static ads.

## 4. Background work
- All scheduled work is APScheduler inside the API process (`scheduler.py`), so the backend must run as a single
  worker. Jobs include lifecycle scans, report emails, campaign steps, push digests, tag expiry, inventory feeds,
  webhook outbox, Jessi onboarding, compliance polling, Twilio tenant sync, mystery-shop planners
  (`_shop_calls_due` every 2 min, `_lead_shops_sweep` every 1 min), coaching digests.
- Long-running asyncio tasks are also spawned from routers (`ring_later`, grading, `place_shop_call`); the scheduler
  ticks are the restart fallback.
- The `.emergent/cron/*` scripts are platform tooling, not app logic.

## 5. Public/no-login surfaces
`/api/public/*` (guides, scorecards, reports, proposals, voice samples), `/api/w/{key}.js` widget bundle and
its `/api/w/*` endpoints, `/api/s/{code}` short links, Twilio/Resend/Stripe webhooks (`/api/webhooks/*`,
`/api/webhook/stripe`), card image renders. These must stay unauthenticated but rate-limited/tokenised.

## 6. Where things are hard-wired (portability notes)
- Port 8001 (`server.py`, supervisor), `/app/...` absolute paths (`routers/docs.py`, `partner_invoices.py`,
  `promo_videos.py`, `server.py` marketing preview), `is_preview_runtime()` = `localhost` in `MONGO_URL`.
- See `docs/PORTABILITY.md`.
