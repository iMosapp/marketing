# iMOs - Product Requirements Document

## Original Problem Statement
Full-stack Relationship Management System (RMS) for dealerships. The app empowers sales teams with digital cards, automated campaigns, AI assistants, review management, and customer relationship tools.

## Core Architecture
- **Frontend:** React Native (Expo) with web support
- **Backend:** FastAPI (Python)
- **Database:** MongoDB Atlas (production), localhost:27017 (preview)
- **Email:** Resend
- **SMS:** Twilio (MOCK mode)
- **AI:** OpenAI (Jessi assistant)
- **Object Storage:** Emergent Integrations (image uploads)

## What's Been Implemented

### Session Feb 27, 2026 (Fork 5 - Current)
- **FIX: Share Review Tile** — Opens share modal (Copy Link, SMS, Email, Preview) instead of settings page
- **FIX: API Docs Syntax Error** — Fixed JSX escaping in integrations Docs tab
- **BACKEND: Automated Lifecycle Scan** — APScheduler job at 6 AM UTC daily
- **FEATURE: Personal SMS Mode** — No-Twilio users: auto-send copies message + opens native SMS app + logs everything
- **FIX: iOS SMS Protocol** — `window.location.href` replaces `window.open` for iOS Safari sms: links
- **FIX: Review Star Button in Thread** — Always shows "Send Review Request" with iMOs review link
- **FEATURE: Auto-Send Actions** — Digital card, vCard, review links, congrats card all auto-send in one tap
- **FEATURE: Contact Event Tracking** — All personal SMS actions logged as events: digital_card_sent, review_request_sent, congrats_card_sent, vcard_sent, personal_sms
- **FIX: Contact Detail Quick Actions** — SMS, Email, Review, Card, Congrats all route through inbox thread for full logging. Only Call stays as direct phone dialer.
- **FEATURE: Activity Reports & Analytics** — Full reports system with date range picker, per-user breakdown, team toggle for managers, daily activity chart, email delivery via Resend, and configurable scheduled reports (daily/weekly/monthly). New endpoints: GET /api/reports/activity/{user_id}, GET /api/reports/activity-daily/{user_id}, POST /api/reports/send-email/{user_id}, GET/PUT /api/reports/preferences/{user_id}.

### Session Feb 27, 2026 (Fork 4)
- **FIX: MONGO_URL** — Reset from Atlas to localhost:27017 for preview stability
- **UI: More Page Tile Rearrangement**
  - Moved Account Setup, Brand Kit, Review Links tiles into My Account page
  - Replaced with My Digital Card, Congrats Card, Share Review as top 3 tiles on More page
  - Quick action tiles now visible to all users (no role restriction)
- **UI: My Account Quick Actions Cleanup**
  - Removed duplicate tiles (My Digital Card, Create Congrats, Share Review Link)
  - Reorganized: Row 1 = Account Setup, Brand Kit, Review Links; Row 2 = AI Persona, Approvals, Edit Card
- **UX: Accordion behavior on More page** — Only one section open at a time, auto-scrolls clicked section into view
- **UI: Inbox Redesign** — Card-based conversation list, timeline-style thread messages, rich content detection for review/congrats/digital cards
- **UI: Contact Edit Mode Layout** — Moved Basic Info fields to appear right after Tags in edit mode (no more scrolling past Activity Feed)
- **BACKEND: Contact Ownership & Soft Delete System**
  - Contact model: added `ownership_type` (org/personal), `original_user_id`, `status` (active/hidden)
  - Source tracking: manual, csv, phone_contacts, lead_form, referral
  - Imported contacts = personal to uploader; manual contacts = belong to org
  - User deletion now soft-deletes (status: deactivated, 6-month grace period)
  - Org user deactivation: personal contacts hidden, org contacts stay
  - Individual user deactivation: everything retained
  - Reactivation endpoint restores user + unhides personal contacts
  - Contact list queries auto-filter hidden contacts
- **FIX: load_dotenv(override=False)** — Platform env vars now take priority over .env file (fixes 3-day production lockout)
- **BACKEND: Public API v1** (`/api/v1/`) — Full REST API with API key auth for 3rd party CRM integrations
  - Contacts CRUD, search, filter, bulk tag/assign, export
  - Users, Conversations, Messages, Campaigns, Reviews, Tags, Orgs, Stores
  - API key management (generate, list, revoke)
- **BACKEND: Outgoing Webhook System** — 21 event types, HMAC signatures, delivery logging
  - contact.created/updated/deleted, message.sent/received, campaign.enrolled, review.submitted, etc.
  - Webhook subscription management + delivery logs

### Session Feb 27, 2026 (Fork 3)
- **NEW: Facebook-Feed Style Contact Profile Page** (`/contact/[id]`)
  - Hero section with avatar, touchpoint badge, name, phone/email chips
  - Time-in-system counter, Stats bar, Quick action buttons
  - Activity Feed timeline aggregating all contact interactions
  - View-only default mode with Edit button toggle
- **NEW: Contact Events Backend** (`/api/contacts/{user_id}/{contact_id}/events`)
  - Aggregates events from messages, campaigns, congrats cards, broadcasts
  - Custom event logging, Stats endpoint
- **REBRAND: "i'M On Social" Marketing Page Overhaul**
  - Updated all marketing, sales presentation, onboarding, features pages
  - Zero "old school" references remaining
- **NEW: White Label Partner System**
  - Backend CRUD at `/api/admin/partners`
  - Partner branding cascades: partner > orgs > stores > users
  - Login returns `partner_branding`, tab bar uses partner color
  - Calendar Systems seeded as first partner
- **NEW: Object Storage Image Pipeline**
  - Emergent Object Storage for all image uploads
  - Auto-generates 3 versions: original, thumbnail (200x200), avatar (80x80)
  - Logo uploads store URLs instead of base64 blobs
- **BUGFIX: Admin Dashboard & Review Page Performance**
  - All list endpoints exclude large binary fields

### Session Feb 26, 2026 (Fork 2)
- Podium-style Review Links Landing Page (`/review/[storeSlug]`)
- Account-Level Dealership Card (`/card/store/[storeSlug]`)
- Reviews Marketing Page, Share Review Link, Review Approval Flow
- More page & My Account redesign, Logo upload, Quick Settings
- Password reset email fix, Auto-slug generation

### Previous Sessions
- Critical production login fix (3-part)
- Fixed 14 crash-inducing useState bugs
- Updated favicon

## Key API Endpoints
- `GET /api/contacts/{user_id}/{contact_id}/events` - Contact activity timeline
- `GET /api/contacts/{user_id}/{contact_id}/stats` - Contact touchpoint stats
- `POST /api/contacts/{user_id}/{contact_id}/events` - Log custom event
- `GET /api/review/page/{store_slug}` - Public review page data
- `POST /api/review/submit/{store_slug}` - Submit feedback
- `GET /api/card/store/{store_slug}` - Account-level dealership card
- `POST /api/email/send` - Send email via Resend
- `POST /api/auth/forgot-password/request` - Password reset
- `POST /api/images/upload/base64` - Image upload to object storage
- `GET /api/images/{image_key}` - Serve images from object storage
- `GET /api/admin/partners` - White-label partner CRUD

## Critical Production Notes
- `backend/server.py` uses `load_dotenv(override=False)` — This is CRITICAL. `override=False` means deployment platform env vars (Kubernetes) take priority over the .env file. This was changed from `override=True` which was causing the .env localhost URL to stomp on the production Atlas URL, locking the user out for 3 days. NEVER change back to override=True.
- Frontend uses relative `/api` paths for web builds
- **MONGO_URL in preview .env MUST be mongodb://localhost:27017**
- **NEVER switch .env MONGO_URL to production Atlas in the preview pod**
- **The deployment platform's environment variables handle production**
- If login breaks after a restart, check MONGO_URL in backend/.env FIRST
- **DB_NAME = `imos-admin-test_database` — THIS IS THE REAL PRODUCTION DATABASE. Do NOT rename or change it. The name is misleading but confirmed correct by the owner.**
- **Production MONGO_URL does NOT contain a database name in the path — the app relies on the DB_NAME env var to connect to the correct database**

## Prioritized Backlog
### P0 (Critical)
- None currently blocking

### P1
- Refactor auth to use hashed passwords (bcrypt)
- Lead Notification System Phase 2 (push notifications)
- Voice Help Assistant backend
- Gamification leaderboard for salespeople touch points
- Campaign flow: Twilio assigned numbers / shared inboxes / task-based SMS sending with templates & AI suggestions

### P2
- Full Twilio integration (currently MOCK)
- WhatsApp integration
- Code cleanup (~80 files)
- Training Hub content
- Inventory Management Module
- React Hydration Error #418
- Mobile app tags sync
- Leaderboard toggle verification
