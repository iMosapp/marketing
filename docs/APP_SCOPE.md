# i'M On Social — Full App Scope & Architecture

**Version:** August 2026

---

## 1. Tech Stack
- **Frontend:** React Native (Expo SDK, expo-router file-based routing) — one codebase for iOS, Android, and Web/PWA. OTA updates via EAS Update (`production` branch/channel).
- **Backend:** FastAPI (Python 3.11) on port 8001, all routes under `/api`. APScheduler for 21 background jobs.
- **Database:** MongoDB (Motor async driver). Separate preview & production databases.
- **Storage:** Emergent Object Storage — all photos/audio/cards, served via `/api/images/{path}` proxy (content-type inference + HTTP Range/206 for audio).
- **Integrations:** Twilio (SMS/MMS/Voice/recordings), OpenAI via Emergent LLM key (Jessi AI, Whisper transcription), Resend (email), Stripe (billing/partner invoices), Web Push (VAPID), imageio-ffmpeg (audio transcoding).

## 2. Repo Layout
```
/app
├── backend/
│   ├── server.py            # app entry, middleware (BOLA, CORS), startup self-heals
│   ├── scheduler.py         # all 21 APScheduler jobs + date-send engine
│   ├── routers/             # ~95 domain routers (see §3)
│   ├── services/            # twilio_service, jessie_service, ...
│   └── utils/image_storage.py  # object storage client (put/get/list, cache)
├── frontend/
│   ├── app/                 # expo-router screens (see §5)
│   ├── components/          # shared + contact/ subcomponents
│   ├── services/api.ts      # axios client (REACT_APP/EXPO_PUBLIC backend URL)
│   └── store/               # zustand stores (auth, theme)
├── docs/                    # THESE internal docs (synced to Admin → Docs on deploy)
└── memory/                  # agent working memory (PRD log, changelog, credentials)
```

## 3. Backend Domains (routers grouped)

| Domain | Routers |
|---|---|
| Auth & security | auth, rbac, permission_templates, admin_users, user_lifecycle |
| Contacts/CRM | contacts, contact_events, contact_intel, contact_merge, csv_import, tags, crm_timeline, search |
| Messaging | messages, twilio_webhooks (SMS/MMS/voice/click-to-call/press-1), broadcast, shared_inboxes, messaging_channels, opt_in, short_urls |
| AI | ai_reply, ai_campaigns, ai_outreach, jessie, va_profiles, voice (training) |
| Voice | calls, voice_notes (memos + transcription + webm conversion), twilio_admin |
| Campaigns | campaigns, campaign_config, campaign_lifecycle, date_triggers, sold_workflow |
| Cards & public | congrats_cards, digital_card, linkpage, showcase, public_review, review_templates, public_landing, public_api, seo, geo |
| Leads | lead_intake (ADF/XML/email/ROI/speed-to-lead), lead_sources, demo_requests |
| Inventory | inventory, inventory_webhooks |
| Teams/orgs | team, team_chat, team_invite, admin_hierarchy, user_schedule, leaderboard, leaderboard_v2, engagement_signals |
| Partners/billing | partners, partner_billing, partner_invoices, invoices, subscriptions, nda, white_label |
| Reporting | reports, training_reports, account_health, tracking, media_tracking, analytics (in reports) |
| Platform | admin, notifications, notifications_center, push_notifications, bug_reports, error_reporting, docs, sop, help_center, training, onboarding_settings, setup_wizard, scheduler_admin, image_router, webhooks, webhook_subscriptions, integrations, email, calendar, tasks, home_intelligence |

### Key API surfaces
- `POST /api/leads/inbound` (ADF/XML) · `POST /api/leads/inbound/email` · `GET /api/leads` · `GET /api/leads/analytics/sources` · `GET /api/leads/analytics/response-times`
- `POST /api/webhooks/twilio/call` (click-to-call) · `/call-bridge` (press-1 gate) · `/call-bridge-connect` · `/call-cancel` · `/call-progress/{sid}` · `/sms` (inbound)
- `GET|POST /api/contacts/{uid}/date-optins[/bulk]` (birthday/anniversary opt-ins)
- `GET|PUT /api/admin/stores/{id}/ai-security-settings` (intent threshold, lockout, ROI email)
- `GET|PUT /api/docs/prd` · `GET /api/docs/` (internal docs) · `GET /api/health/deep`

## 4. Key MongoDB Collections
`users, stores, organizations, contacts, conversations, messages, campaigns, campaign_enrollments, campaign_pending_sends, date_trigger_configs, date_trigger_log, date_send_guard, inbound_leads, lead_sources, inventory, voice_notes, congrats_cards, pending_calls, notifications, push_subscriptions, bug_reports, tasks, contact_events, login_attempts (TTL), migrations, company_docs (internal docs), sops, partner_agreements, partner_invoices, short_urls, broadcasts, shared_inboxes, training_*, reports_*`

## 5. Frontend Screen Map (expo-router)
- **Tabs:** Home · Contacts · Dialer (click-to-call, press-1, red hang-up) · Inbox · Activity/Touchpoints · Notifications · More
- **Contact:** `contact/[id]` (feed/details/gallery/voice memos/date opt-in toggles), `contact/new`, `contact/sold-wizard`, `thread/[id]`
- **Leads & inventory:** `leads` (Leads / Source ROI / Speed tabs), `inventory`
- **Campaigns:** `campaigns/*`, `broadcast/*`, `quick-send/[action]`
- **Settings:** `settings/date-triggers`, `settings/date-recipients`, persona, templates, tags, brand-kit, security, integrations, schedule, review-links…
- **Admin:** `admin/*` — stores (AI & Security), lead-sources (webhooks + cost), users, twilio-numbers, bug-reports, docs (PRD/Ops/Scope viewer), billing, partners, white-label, training…
- **Public (no auth):** `card/[userId]`, `l/[username]`, `review/[storeSlug]`, `showcase/*`, `congrats/[cardId]`, `birthday/[cardId]`, `opt-in/[cardId]`, `p/[userId]`, `store/[slug]`, quote/NDA/W-9 signing
- **Marketing site:** `imos/*` (imonsocial.com pages)

## 6. Security Model
- JWT (PyJWT) bearer auth; bcrypt password hashing.
- **BOLA middleware** in `server.py`: object-level authorization on protected prefixes — users can only touch their own/store-scoped data (`get_data_filter`).
- Role hierarchy: `user < store_manager < org_admin < super_admin`; RBAC checks in routers + role-gated internal docs.
- Brute-force lockout per `ip:email` (configurable per store), password-reset throttling, strict CORS from env.
- Public webhooks (Twilio, lead intake) validated by shape/ownership lookups; everything else JWT-gated.
- Media never public-bucket: served through authenticated-safe `/api/images` proxy with immutable caching.

## 7. Automation Safety Rails (why nothing double-fires)
- Quiet hours: all automated SMS defer to 9 AM contact-local.
- Date sends: manual opt-in tag required + day-of trigger only + `date_send_guard` (one send per contact/occasion/day) + single-campaign-per-occasion rule + 300-day re-enrollment block.
- Idempotency keys on notifications/digests; TTL dedup on login attempts; migration markers in `migrations` collection so one-time fixes never re-run.

---
*Source of truth: `/app/docs/APP_SCOPE.md` — synced to Admin → Docs automatically on every deploy.*
