# iMOs - Product Requirements Document

## CRITICAL — DO NOT MODIFY (Production will break)
- **backend/.env** MUST contain `MONGO_URL` with the production Atlas connection string. NEVER remove it.
- **backend/server.py** MUST use `load_dotenv(override=True)`. NEVER change to `override=False`. The Emergent platform injects `MONGO_URL=localhost` which is WRONG for production.
- **backend/.env.local** MUST NOT be loaded or created. It gets deployed to production and overrides the correct MONGO_URL.
- **DB_NAME** in `.env` MUST be `imos-admin-test_database` — this is the production database name.
- **frontend/services/api.ts** MUST use relative `/api` path for web (`Platform.OS === 'web'`). NEVER use `EXPO_PUBLIC_BACKEND_URL` for web — it bakes dead preview URLs into the JS bundle and breaks production.
- **ALL frontend files** that make API calls MUST use `Platform.OS === 'web' ? '' : (process.env.EXPO_PUBLIC_BACKEND_URL || '')` for the base URL. NEVER use env vars directly on web.

---

## Current Architecture

### Stack
- **Frontend**: React Native Web (Expo SDK 54, Expo Router 6) — runs on port 3000
- **Backend**: FastAPI 0.110.1 — runs on port 8001, all routes prefixed with `/api`
- **Database**: MongoDB Atlas (pymongo 4.5.0, motor 3.3.1)
- **Runtime**: Python 3.11, React 19.1.0, React Native 0.81.5

### Environment Variables

#### Backend (`/app/backend/.env`)
| Key | Value | Purpose |
|-----|-------|---------|
| DB_NAME | imos-admin-test_database | Production database name |
| MONGO_URL | mongodb+srv://imos-admin:d6daj3slqs2c73egs2k0@customer-apps.tuuucd.mongodb.net/imos-admin-test_database?... | Production MongoDB Atlas |
| CORS_ORIGINS | * | CORS config |
| RESEND_API_KEY | re_9NvFreuG_6deEy2V99qDhwjFCAx5fERPD | Resend email service |
| SENDER_EMAIL | noreply@imosapp.com | From address for emails |
| EMERGENT_LLM_KEY | sk-emergent-f03D630881c37F9Cf1 | OpenAI via Emergent |
| TWILIO_ACCOUNT_SID | ACb3417cc4bd67d30b8f9fa1f2baa13233 | Twilio (MOCK mode) |
| TWILIO_AUTH_TOKEN | d14071fb3d46653f5b46a52c4150be66 | Twilio (MOCK mode) |
| TWILIO_PHONE_NUMBER | +18557657326 | Twilio phone |
| APP_URL | https://app.imosapp.com | Production app URL |

#### Frontend (`/app/frontend/.env`)
| Key | Value | Purpose |
|-----|-------|---------|
| REACT_APP_BACKEND_URL | (preview URL - changes per fork) | Preview only |
| EXPO_PUBLIC_BACKEND_URL | (preview URL - changes per fork) | Preview only — IGNORED on web |
| WDS_SOCKET_PORT | 443 | WebSocket |
| EXPO_TUNNEL_SUBDOMAIN | (changes per fork) | Expo tunnel |
| EXPO_PACKAGER_HOSTNAME | (changes per fork) | Expo packager |
| EXPO_USE_FAST_RESOLVER | 1 | Metro bundler |

---

## Database Schema (MongoDB Atlas: `imos-admin-test_database`)

### Collections Referenced in Code (74 total)
| Collection | Purpose |
|-----------|---------|
| users | User accounts (5 docs in production) |
| contacts | Contact records |
| contact_photos | Contact profile photos |
| conversations | SMS/messaging conversations |
| messages | Individual messages |
| threads | Message threads |
| calls | Call logs |
| voicemails | Voicemail records |
| tags | Contact tags |
| tasks | Task/reminder records |
| campaigns | SMS campaign definitions |
| campaign_enrollments | Campaign enrollment tracking |
| campaign_settings | Campaign configuration |
| campaign_templates | Campaign message templates |
| email_campaigns | Email campaign definitions |
| email_templates | Email template content |
| email_logs | Email send logs |
| templates | SMS templates |
| template_sends | Template send tracking |
| broadcast (in code as broadcast) | Mass message broadcasts |
| congrats_cards | Congratulations cards |
| congrats_templates | Congrats card templates |
| card_shares | Digital card share events |
| card_events | Digital card interaction events |
| organizations | Organization records |
| stores | Store/dealership records |
| teams | Team definitions |
| team_channels | Team chat channels |
| team_messages | Team chat messages |
| team_members | Team membership |
| team_invites | Team invitation records |
| team_read_status | Team message read status |
| shared_inboxes | Shared phone number inboxes |
| lead_sources | Lead source configurations |
| notifications | User notifications |
| activity | Activity log entries |
| member_activities | Member activity tracking |
| ai_messages | AI assistant (Jessi) messages |
| sops | Standard Operating Procedures |
| sop_feedback | SOP feedback |
| sop_progress | SOP completion tracking |
| partner_agreements | Partner/reseller agreements |
| partner_templates | Partner agreement templates |
| partners | Partner records |
| invoices | Invoice records |
| subscriptions | Subscription records |
| subscription_quotes | Subscription quote records |
| subscription_cancellations | Cancellation records |
| payment_transactions | Payment records |
| discount_codes | Discount/promo codes |
| inventory | Inventory items |
| integrations | API key/webhook configs |
| api_keys | API keys |
| webhooks | Webhook definitions |
| webhook_events | Webhook event logs |
| webhook_logs | Webhook delivery logs |
| short_urls | URL shortener records |
| short_url_clicks | Short URL click tracking |
| date_trigger_configs | Birthday/anniversary triggers |
| date_trigger_log | Trigger execution log |
| onboarding_settings | New user onboarding config |
| demo_requests | Demo request submissions |
| customer_feedback | Customer feedback records |
| referrals | Referral tracking |
| invite_shares | Invitation share tracking |
| companies | Company records |
| media | Media/file uploads |
| sms_queue | SMS send queue |
| weekly_kpis | Weekly KPI snapshots |
| sync_logs | Data sync logs |
| impersonation_sessions | Admin impersonation sessions |
| transfer_logs | Contact transfer logs |
| bulk_transfers | Bulk transfer operations |
| reports (in code as weekly_kpis) | Report data |

### Key User Schema
```json
{
  "email": "string",
  "password": "string (PLAIN TEXT - security risk)",
  "name": "string",
  "role": "super_admin | org_admin | store_manager | user",
  "status": "active | inactive | null",
  "is_active": "boolean | null",
  "phone": "string",
  "organization_id": "string",
  "store_id": "string",
  "social_links": { "instagram": "", "facebook": "", "linkedin": "", "twitter": "", "tiktok": "", "website": "" },
  "bio": "string",
  "title": "string",
  "leaderboard_visible": "boolean",
  "onboarding_completed": "boolean"
}
```

### Key Contact Schema
```json
{
  "user_id": "string",
  "first_name": "string",
  "last_name": "string",
  "email": "string",
  "phone": "string",
  "tags": ["string"],
  "notes": "string",
  "photo": "string (URL)",
  "source": "string",
  "created_at": "datetime"
}
```

---

## Backend API Routes (all prefixed with `/api`)

### Authentication (`/api/auth`)
- POST `/login` — User login (plain text password comparison)
- POST `/signup` — User registration
- POST `/forgot-password/request` — Generate reset code (DOES NOT send email)
- POST `/forgot-password/verify` — Verify reset code
- POST `/forgot-password/reset` — Reset password
- POST `/admin-reset` — Emergency password reset (secret: `iMOs-Emergency-Reset-2026`)

### Contacts (`/api/contacts`)
- GET `/` — List contacts for user
- POST `/` — Create contact
- GET `/{id}` — Get single contact
- PUT `/{id}` — Update contact
- DELETE `/{id}` — Delete single contact
- POST `/delete` — Bulk delete contacts
- POST `/import` — Import contacts from CSV

### Admin (`/api/admin`)
- GET `/users` — List all users
- POST `/users` — Create user
- GET `/users/{id}` — Get user details
- PUT `/users/{id}` — Update user
- DELETE `/users/{id}` — Delete user
- GET `/organizations` — List organizations
- GET `/stores` — List stores
- GET `/activity-feed` — Activity feed
- POST `/impersonate` — Impersonate user

### Messages (`/api/messages`)
- GET `/{conversation_id}` — Get messages for conversation
- POST `/send` — Send message (Twilio - MOCKED)

### Team Chat (`/api/team-chat`)
- GET `/channels` — List channels
- POST `/channels` — Create channel
- GET `/channels/{id}/messages` — Get channel messages
- POST `/channels/{id}/messages` — Send message

### Campaigns (`/api/campaigns`)
- GET `/` — List campaigns
- POST `/` — Create campaign
- GET `/{id}` — Campaign details
- PUT `/{id}` — Update campaign

### Digital Card (`/api/card`)
- GET `/{userId}` — Get public digital card

### Congrats Cards (`/api/congrats`)
- POST `/create` — Create congrats card
- GET `/{id}` — Get congrats card

### Lead Sources (`/api/lead-sources`)
- GET `/` — List lead sources
- POST `/` — Create lead source
- GET `/{id}` — Lead source details
- PUT `/{id}` — Update lead source
- POST `/claim/{id}` — Claim a lead
- GET `/team-inbox/{id}` — Team inbox conversations

### Other Routes
- `/api/tags` — Tag CRUD
- `/api/tasks` — Task CRUD
- `/api/templates` — SMS template CRUD
- `/api/email` — Email template CRUD + sending
- `/api/broadcast` — Mass messaging
- `/api/calendar` — Calendar integration
- `/api/integrations` — API keys/webhooks
- `/api/partners` — Partner management
- `/api/invoices` — Invoice management
- `/api/subscriptions` — Subscription management
- `/api/reports` — Report generation
- `/api/leaderboard` — Leaderboard data
- `/api/directory` — Company directory
- `/api/sop` — SOPs
- `/api/jessie` — AI assistant (OpenAI)
- `/api/voice` — Voice features
- `/api/notifications` — Notification CRUD
- `/api/search` — Global search
- `/api/profile` — Profile management
- `/api/webhooks` — Webhook management
- `/api/date-triggers` — Date-based triggers
- `/api/onboarding-settings` — Onboarding config
- `/api/demo-requests` — Demo request handling
- `/api/team-invite` — Team invitations
- `/api/review` — Public review pages
- `/api/p` — Public landing pages
- `/api/s` — URL shortener
- `/api/scheduler` — Scheduler admin
- `/api/admin/app-directory` — App directory sharing
- `/api/admin/team` — Shared inboxes & transfers
- `/api/webhooks/twilio` — Twilio webhooks
- `/api/webhooks/inventory` — Inventory webhooks

### Utility Endpoints (in server.py)
- GET `/api/health` — Health check
- GET `/api/debug/db-info` — Database diagnostic (TEMPORARY)
- GET `/api/branding/logo` — Branding logo
- GET/PUT `/api/users/{id}/leaderboard-settings` — Leaderboard prefs
- GET/PUT `/api/users/{id}/review-links` — Review links
- GET/PUT `/api/users/{id}/persona` — AI persona
- PATCH `/api/users/{id}` — Partial user update
- GET `/api/activity/{id}` — User activity
- POST `/api/webhook/stripe` — Stripe webhook
- WS `/api/ws/{user_id}` — WebSocket connection

---

## Frontend Routes

### Tab Navigation (`app/(tabs)/`)
| Route | File | Purpose |
|-------|------|---------|
| /inbox | inbox.tsx | Message inbox (My/Team) |
| /dialer | dialer.tsx | Phone dialer |
| /contacts | contacts.tsx | Contact list |
| /team | team.tsx | Team chat |
| /more | more.tsx | Settings/menu hub |

### Main Menu (More tab → router.push paths)
| Section | Route | Page |
|---------|-------|------|
| **Essentials** | /training-hub | Training Hub |
| | /jessie | Ask Jessi (AI) |
| | /tasks | Tasks & Reminders |
| **Communication** | /(tabs)/dialer | Phone/Dialer |
| | /broadcast | Broadcast |
| | /campaigns | SMS Campaigns |
| | /campaigns/email | Email Campaigns |
| | /campaigns/dashboard | Campaign Dashboard |
| | /settings/date-triggers | Date Triggers |
| **Templates & Branding** | /settings/templates | SMS Templates |
| | /settings/email-templates | Email Templates |
| | /settings/brand-kit | Brand Kit |
| | /settings/congrats-template | Congrats Cards |
| **Performance** | /analytics | Analytics |
| | /reports | Reports |
| | /settings/email-analytics | Email Analytics |
| | /admin/my-rankings | My Rankings |
| **Contacts & Leads** | /admin/lead-sources | Lead Sources |
| | /contacts/import | Import Contacts |
| | /settings/tags | Contact Tags |
| | /settings/review-links | Review Links |
| | /settings/review-approvals | Review Approvals |
| **Profile & AI** | /settings/my-profile | Digital Card |
| | /settings/persona | AI Persona |
| **Settings** | /settings/security | Security |
| | /settings/toggle-style | SMS/Email Toggle |
| | /settings/calendar | Calendar |
| | /settings/integrations | Integrations |
| **Administration** | /admin | Admin Dashboard |
| | /admin/app-directory | App Directory |
| | /settings/invite-team | Invite Team |
| | /admin/organizations | Organizations |
| | /admin/stores | Accounts/Stores |
| | /admin/users | Users |
| | /admin/individuals | Individuals |
| | /admin/pending-users | Pending Users |
| | /admin/partner-agreements | Partner Agreements |
| | /admin/directory | Company Directory |
| | /admin/shared-inboxes | Shared Inboxes |
| | /admin/bulk-transfer | Bulk Transfer |
| | /admin/phone-assignments | Phone Assignments |
| | /admin/quotes | View Quotes |
| | /admin/create-quote | Create Quote |
| | /admin/discount-codes | Discount Codes |

### Public/Standalone Routes
| Route | File | Purpose |
|-------|------|---------|
| /card/[userId] | card/[userId].tsx | Public digital business card |
| /congrats/[cardId] | congrats/[cardId].tsx | Public congrats card |
| /p/[userId] | p/[userId].tsx | Public landing page |
| /review/[storeSlug] | review/[storeSlug].tsx | Public review page |
| /join/[code] | join/[code].tsx | Team join via invite code |
| /my-account | my-account.tsx | My Account (Create Congrats Card here) |

### Legacy `/imos/` Routes (mirror pages for public/embedded access)
Full set of ~40 pages under `/app/imos/` that mirror the main app routes for public or embedded use.

---

## 3rd Party Integrations

| Service | Status | Used For |
|---------|--------|----------|
| **MongoDB Atlas** | ACTIVE | Primary database |
| **Resend** | ACTIVE (but email delivery may be failing) | Transactional emails |
| **OpenAI** (via Emergent LLM key) | ACTIVE | Jessi AI assistant |
| **Twilio** | MOCKED | SMS messaging |
| **Stripe** | WEBHOOK ONLY | Payment processing (webhook handler exists) |

---

## Key Custom Components

| Component | Location | Purpose |
|-----------|----------|---------|
| WebModal | /components/WebModal.tsx | Web-safe modal (replaces RN Modal) |
| Toast | /components/common/Toast.tsx | Non-blocking toast notifications |
| Alert Service | /services/alert.ts | Web-safe alert wrappers |
| API Service | /services/api.ts | Axios-based API client (relative URL on web) |

---

## What's Been Implemented (Completed)

### Core App
- Multi-role auth (super_admin, org_admin, store_manager, user) — plain text passwords
- Contact management with CRUD, bulk delete, import, photo support
- Team chat with channels
- Digital business card creation, editing, sharing (production URLs)
- Congrats card creation and sharing (production URLs)
- Admin panel (users, orgs, stores, pending users, partner agreements)
- Lead source management with round-robin/jump-ball routing
- AI assistant (Jessi) powered by OpenAI
- SMS/email templates, campaigns, broadcasts
- Task/reminder system
- Date triggers (birthdays, anniversaries)
- Leaderboard and rankings
- Reports and analytics
- Training hub (no content yet)
- URL shortener
- WebSocket support
- SOP system
- Partner agreement signing

### Recent Session Fixes (Feb 26, 2026)
- Fixed production login (frontend was using dead preview URLs)
- Fixed production database connection (platform MONGO_URL override)
- Fixed 4 broken Toast import paths
- Fixed 5 files using EXPO_PUBLIC_BACKEND_URL directly
- Removed hardcoded APP_URL from 3 backend files
- Replaced 17+ Modal components with WebModal
- Replaced Alert.alert with toast notifications across 19 files
- Added Website field to digital business card
- Fixed Resend email API key and sender format
- Added admin-reset endpoint for emergency password recovery
- Standardized all shareable links to use app.imosapp.com
- Fixed double-URL SMS share bug
- Relocated Create Congrats Card to My Account
- Added Delete Contact button
- Changed favicon

### Session Feb 26, 2026 (Fork 2)
- **NEW FEATURE**: Podium-style Review Links Landing Page (`/review/[storeSlug]`)
  - Clean light theme with store logo, name, and brand kit integration
  - All review links displayed upfront (Google, Yelp, Facebook, DealerRater, custom)
  - Click tracking at store and salesperson level (`POST /api/review/track-click/{store_slug}`)
  - Click statistics endpoint (`GET /api/review/click-stats/{store_id}`)
  - Store info footer (phone, website, address)
- **FIXED**: Password reset emails now sent via Resend (was generating code but never emailing it)
- **FIXED**: Removed insecure debug endpoint `/api/debug/db-info`
- **FIXED**: Forgot-password endpoint no longer leaks `dev_code` in response

---

## Known Issues

| Priority | Issue | Status |
|----------|-------|--------|
| P0 | Email delivery failing (Resend) | MONITORING (Resend key active, password reset emails now sending) |
| P0 | Forgot-password endpoint doesn't send email | FIXED (Feb 26, 2026) |
| P0 | Debug endpoint `/api/debug/db-info` exposes DB info | FIXED - REMOVED (Feb 26, 2026) |
| P1 | Passwords stored in plain text | NOT FIXED |
| P1 | Dead links in App Directory (user reported) | INVESTIGATING |
| P2 | ~25 files still use RN Modal instead of WebModal | LOW PRIORITY |
| P2 | Twilio SMS in mock mode | DEFERRED |
| P2 | React Hydration Error #418 | COSMETIC |

---

## Credentials

| Account | Email | Password | Role |
|---------|-------|----------|------|
| Super Admin | forest@imosapp.com | Admin123! | super_admin |
| Preview Seed | admin@imosapp.com | iMOs2026! | super_admin |
| Admin Reset Secret | — | iMOs-Emergency-Reset-2026 | — |

---

## File Structure Summary
```
/app/
├── backend/
│   ├── .env                    # Production env vars (MONGO_URL, keys)
│   ├── server.py               # Main app, startup, utility routes, WebSocket
│   ├── requirements.txt        # Python dependencies
│   ├── routers/                # 47 route files
│   │   ├── database.py         # MongoDB connection (get_db)
│   │   ├── auth.py             # Login, signup, forgot-password, admin-reset
│   │   ├── contacts.py         # Contact CRUD
│   │   ├── admin.py            # Admin user management
│   │   ├── messages.py         # Messaging
│   │   ├── team_chat.py        # Team chat
│   │   ├── campaigns.py        # Campaigns
│   │   ├── lead_sources.py     # Lead routing
│   │   ├── jessie.py           # AI assistant
│   │   ├── email.py            # Email via Resend
│   │   └── ... (37 more)
│   └── tests/                  # Test files
├── frontend/
│   ├── .env                    # Frontend env vars
│   ├── package.json            # Dependencies
│   ├── app/                    # Expo Router pages
│   │   ├── _layout.tsx         # Root layout with ToastProvider
│   │   ├── (tabs)/             # 5 main tabs
│   │   ├── admin/              # ~30 admin pages
│   │   ├── settings/           # ~15 settings pages
│   │   ├── imos/               # ~40 legacy/public mirror pages
│   │   ├── card/[userId].tsx   # Public digital card
│   │   ├── congrats/[cardId].tsx # Public congrats card
│   │   └── ... (other routes)
│   ├── components/
│   │   ├── WebModal.tsx        # Web-safe modal
│   │   └── common/Toast.tsx    # Toast notification system
│   ├── services/
│   │   ├── api.ts              # API client (relative URL on web)
│   │   └── alert.ts            # Web-safe alerts
│   ├── hooks/
│   │   └── useWebSocket.ts     # WebSocket hook
│   └── store/
│       └── authStore.ts        # Auth state (Zustand)
└── memory/
    └── PRD.md                  # This file
```
