# IMOS Integrations

Every external service the application talks to, the environment variables it needs, where it is used, and
whether it is owned by the company or by the Emergent platform. Snapshot: Sep 30 2026. Values live in `.env`
files / the production Secrets panel only; see `backend/.env.example` for placeholders.

| Service | Owner | Status | Env vars | Code | Used for |
|---|---|---|---|---|---|
| **MongoDB** | Emergent-managed cluster in prod, local `mongod` in preview | Live | `MONGO_URL`, `DB_NAME` | `routers/database.py` | All application data (see `docs/DATABASE.md`) |
| **Twilio** | Company account (+ per-organization subaccounts) | Live, A2P 10DLC registered | `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`, `TWILIO_MESSAGING_SERVICE_SID`, optional `MYSTERY_SHOP_FROM_NUMBER`, `TWILIO_WEBHOOK_VALIDATION` (log/enforce), `TWILIO_TOKEN_KEY`, `TWILIO_TRUSTHUB_*` | `services/twilio_service.py`, `twilio_signature.py`, `twilio_errors.py`, `twilio_tenant.py`, `twilio_compliance.py`, `routers/twilio_webhooks.py`, `org_twilio.py`, `twilio_admin.py`, `dialer_webhooks.py`, `services/live_shops.py` (media streams), `routers/scripts.py` (ConversationRelay) | SMS/MMS, inbound/outbound voice, press-1 screening, voicemail + transcription, media streams to GPT-Live, ConversationRelay (Google/ElevenLabs voices by id), number search/purchase, subaccounts, Trust Hub / 10DLC compliance |
| **OpenAI GPT-Live** (realtime voice) | Company key | Live in prod; 503 in preview (no key) | `OPENAI_API_KEY` | `services/live_voice.py`, `live_shops.py`, `live_host.py`, `live_interview.py`, `voice_samples.py`, `routers/live_voice.py` | Jessi Live (WebRTC in the app), live mystery-shop callers, call host, voice interview, 5-second voice previews |
| **OpenAI text / Whisper / TTS via `emergentintegrations`** | **Emergent** (universal key) | Live | `EMERGENT_LLM_KEY` | 33 files: `routers/ai_reply.py`, `ai_campaigns.py`, `messages.py`, `home_intelligence.py`, `contact_intel.py`, `chat_widget.py`, `voice.py`, `voice_notes.py`, `calls.py`, ...; `services/jessie_service.py`, `scripts.py`, `scorecards.py`, `widget_chat.py`, `widget_crawl.py`, `voicemails.py`, `intent_detection.py`, `call_summary.py`, ... (`LlmChat`, `OpenAISpeechToText`, `OpenAITextToSpeech`); model choice in `services/llm_models.py` (`gpt-5.2`, `gpt-4o-mini`, `gpt-4.1-mini`, `whisper-1`, `tts-1`) | AI replies, drafts, Jessi chat, summaries, grading, challenge generation, widget chat, transcription, Jessi voice memos |
| **Resend** | Company account, domain `imonsocial.com` verified | Live | `RESEND_API_KEY`, `SENDER_EMAIL`, `RESEND_WEBHOOK_SECRET`, `INBOUND_EMAIL_DOMAIN`, `LEAD_SENDER_DOMAIN`, `SHOP_EMAIL_DOMAIN`, `REPORT_REPLY_TO` | `resend` SDK across routers/services (`auth.py` welcome mail, reports, invites, ADF lead pushes), `routers/resend_webhooks.py` (`email.received`), `services/lead_shops.py`, `email_shops.py` | All transactional email; inbound email for covert Lead Shops (needs `INBOUND_EMAIL_DOMAIN` + MX + webhook; **not yet configured in production**) |
| **Stripe (subscriptions, quotes, partner billing)** | **Emergent Stripe test proxy** when `STRIPE_API_KEY=sk_test_emergent` | Test mode only | `STRIPE_API_KEY`, `STRIPE_WEBHOOK_SECRET` | `routers/subscriptions.py` (`emergentintegrations.payments.stripe.checkout.StripeCheckout`), webhook `/api/webhook/stripe` | Checkout sessions, quote acceptance, partner billing |
| **Stripe (mystery-shop proposals & invoices)** | Company account (test key today) | Test mode | `STRIPE_SECRET_KEY` | direct `stripe` SDK in `routers/mystery_shops.py`, `services/mystery_shops.py` | Signed proposals create Stripe invoices |
| **Expo Push** | Expo (company's Expo account) | Live | none (tokens stored in `expo_push_tokens`) | `routers/push_notifications.py` -> `https://exp.host/--/api/v2/push/send` | Native push to iOS (Android needs FCM config, not present) |
| **Web Push (VAPID)** | Company key pair | Live | `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_MAILTO`; frontend `EXPO_PUBLIC_VAPID_KEY` | `pywebpush` in `routers/push_notifications.py` | Browser push for the PWA |
| **Emergent Object Storage** | **Emergent** | Live | `OBJECT_STORAGE_KEY` (fallback `EMERGENT_LLM_KEY`), `IMAGE_CACHE_MB` | `utils/image_storage.py` -> `https://integrations.emergentagent.com/objstore/api/v1/storage`; used by 17 modules; served through `/api/images/{path}` | Profile/contact photos, delivery photos, voice notes, recorded conversations, card renders, PDFs, audio |
| **Apple Wallet** | Company Apple Developer account (team `2JDV2RY89J`) | Configured only when certs present (503 otherwise) | `APPLE_TEAM_ID`, `APPLE_PASS_TYPE_ID`, `APPLE_PASS_P12_B64`, `APPLE_PASS_P12_PASSWORD`, `APPLE_WWDR_PEM_B64` | `routers/wallet_pass.py` | .pkpass digital business cards |
| **Google Wallet** | Company | Configured only when SA JSON present | `GOOGLE_WALLET_ISSUER_ID`, `GOOGLE_WALLET_SA_JSON_B64` | `routers/wallet_pass.py` | Google Wallet save links |
| **Google Calendar (OAuth)** | Company | Not configured anywhere | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_CALENDAR_REDIRECT_URI` | `routers/calendar.py` | Appointment sync (dormant) |
| **Picovoice Eagle** | Company key | Live in preview | `PICOVOICE_ACCESS_KEY`, `VOICE_ID_THRESHOLD` | `services/voice_id.py` | Speaker verification for voice interviews (aarch64 library workaround in `_lib_kwargs`) |
| **Nominatim / OpenStreetMap** | Public API | Live | none | inline httpx (client onboarding) | Address search |
| **GoHighLevel** | Per customer connection (none in prod) | Built, unconfigured | none (tokens per connection in Mongo) | `services/ghl.py`, `routers/ghl.py` | Power Dialer lead import + webhook |
| **ADF/XML lead intake, generic CRM webhooks** | Customers | Live | none | `routers/lead_intake.py`, `webhook_subscriptions` | Inbound leads from dealer CRMs / lead providers |
| **HubSpot / Salesforce / Zoho / Pipedrive** | - | Not implemented (backlog) | - | - | Two-way CRM sync |
| **EAS / App Store Connect** | Company Expo + Apple accounts | Live (iOS) | eas.json submit profile (Apple ID, team, ASC app id) | `frontend/eas.json`, `app.json` | OTA updates and native builds |
| **Vercel** | Company account, GitHub-connected | Live | none | `marketing/vercel.json` | Marketing site + `/s/*`, `/go/*`, `/get/*` redirects to the app |
| **Emergent hosting / deploy** | **Emergent** | Live | production secrets in the Emergent panel | `.emergent/`, Deploy button | Runs backend + web at `app.imonsocial.com` |

## Webhooks the outside world calls (must keep working after any move)
- Twilio: `/api/webhooks/twilio/incoming` (= `/sms`), `/voice`, `/voice-fallback`, `/call-whisper*`, `/voicemail-*`,
  `/call-bridge*`, `/api/scripts/roleplay/*` (relay + media stream), `/api/w/ring/*` (widget), dialer webhooks.
  Signature validation runs in `log` mode until `TWILIO_WEBHOOK_VALIDATION=enforce`.
- Resend: `/api/webhooks/resend/inbound` (`email.received`).
- Stripe: `/api/webhook/stripe`.
- Widget script: `GET /api/w/{key}.js` embedded on customer websites (domain allowlist optional).
- Public pages: `/guide/*`, `/shop-score/*`, `/shop-report/*`, `/proposal/*`, `/congrats/*`, `/s/{code}`.

## Safety switches for non-production environments
`is_preview_runtime()` (MONGO_URL contains localhost) enables: `SMS_SEND_ONLY_TO` allowlist (everything else is
mocked with `sent_mock`), `WIDGET_RING_DRY_RUN`, `LEAD_SHOP_BUY_NUMBERS=false`. In production these keys are
ignored. Twilio test numbers `+1500555xxxx` are safe targets in any environment.
