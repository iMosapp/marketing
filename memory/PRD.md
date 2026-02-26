# iMOs - Product Requirements Document

## CRITICAL — DO NOT MODIFY (Production will break)
- **backend/.env** MUST contain `MONGO_URL` with the production Atlas connection string. NEVER remove it.
- **backend/server.py** MUST use `load_dotenv(override=True)`. NEVER change to `override=False`. The Emergent platform injects `MONGO_URL=localhost` which is WRONG for production.
- **backend/.env.local** MUST NOT be loaded or created. It gets deployed to production and overrides the correct MONGO_URL.
- **DB_NAME** in `.env` MUST be `imos-admin-test_database` — this is the production database name.
- **frontend/services/api.ts** MUST use relative `/api` path for web (`Platform.OS === 'web'`). NEVER use `EXPO_PUBLIC_BACKEND_URL` for web — it bakes dead preview URLs into the JS bundle and breaks production login.
- **Production MONGO_URL**: `mongodb+srv://imos-admin:d6daj3slqs2c73egs2k0@customer-apps.tuuucd.mongodb.net/imos-admin-test_database?appName=congrats-card-fix&maxPoolSize=5&retryWrites=true&timeoutMS=10000&w=majority`
- **Production database**: `imos-admin-test_database` (NOT `imos-admin-mvpline_db`)

## Original Problem Statement
Full-stack Relationship Management System (RMS) for sales teams. Features include contacts management, team chat, digital business cards, congrats cards, AI assistant (Jessi), admin panel, lead routing, and more.

## Core Requirements
- Multi-role authentication (super_admin, org_admin, store_manager, user)
- Contact management with bulk operations
- Team chat with channels
- Digital business card creation and sharing
- Congrats card creation and sharing
- Admin panel with user/org/store management
- AI assistant (Jessi) powered by OpenAI
- Email via Resend, SMS via Twilio (currently mocked)
- Training hub, leaderboard, reports

## What's Been Implemented

### Session - Feb 26, 2026 (Original)
- [x] Team Chat UI Fix: Web compatibility for dropdowns and create button
- [x] Team Chat Search: Channel search/filter bar
- [x] Contact Deletion: Single and bulk delete (backend + frontend)
- [x] Digital Card UI: Social links moved above voice recorder
- [x] Admin Linking Fix: Fixed unclickable "Link Existing" buttons
- [x] User Creation Modal Fix: Web-compatible copy buttons
- [x] Inbox Email Prompt Fix: Check existing email before prompting
- [x] Congrats Card Creation Fix: Web-compatible file upload
- [x] Congrats Card Feature: Full create + share flow at /settings/create-congrats
  - Relocated to My Account → QUICK ACTIONS
- [x] Social Media Username-Only Inputs
- [x] Fixed mobile Safari login crash (expo-haptics try-catch)
- [x] Fixed ALL shareable links to use production URL (app.imosapp.com)
- [x] Eliminated short URL redirects for business cards (direct links)
- [x] Admin password reset endpoint (POST /api/auth/admin-reset)
- [x] Full QA audit (all 31 More menu routes return 200)
- [x] Replaced 17 Modal components with WebModal
- [x] Replaced Alert.alert with toast notifications across 19 files
- [x] Website field added to digital business card
- [x] Favicon changed
- [x] Resend email integration fixed (API key + sender format)
- [x] Delete Contact button on edit page

### Session - Feb 26, 2026 (Fork: Build Fix & Production Login)
- [x] **Fixed 4 broken Toast import paths** that prevented app from loading
- [x] **FIXED PRODUCTION LOGIN (ROOT CAUSE)**: Frontend was baking dead preview URLs into JS bundle via `EXPO_PUBLIC_BACKEND_URL`. Changed `api.ts` to use relative `/api` path on web.
- [x] **FIXED PRODUCTION DATABASE CONNECTION**: Platform injects `MONGO_URL=localhost` which overwrites production config. Fixed with `load_dotenv(override=True)` and hardcoding production MONGO_URL in `.env`.
- [x] **Removed .env.local loading**: File was getting deployed to production and overriding correct MONGO_URL with localhost.
- [x] **Removed hardcoded APP_URL** from auth.py, team_invite.py, short_urls.py — now reads from env var.
- [x] **Added resilient DB connection**: `get_db()` tries `get_default_database()` first, falls back to `DB_NAME`. Added 30s connection timeouts.
- [x] **Added debug endpoint** `/api/debug/db-info` for diagnosing production DB issues.
- [x] **Reset user passwords** via admin-reset endpoint on production.
- Testing: 100% pass rate (iteration_35.json)

## Architecture
- Frontend: React Native Web (Expo) with file-based routing
- Backend: FastAPI with MongoDB
- Database: MongoDB Atlas (production), localhost (preview via supervisor env var)
- 3rd Party: OpenAI (Jessi AI), Resend (email), Twilio (SMS - mocked)

## Known Issues
- Twilio SMS is in mock mode
- React Hydration Error #418 (cosmetic, not blocking)
- Passwords stored as plain text (security risk, needs bcrypt refactor)
- ~25 files still use RN Modal instead of WebModal (non-blocking, buttons work via IS_WEB checks)
- Forgot-password endpoint doesn't send email via Resend (just logs code)
- Email (Resend) may not be sending — user reported not receiving emails

## Prioritized Backlog

### P0 (Critical)
- Fix Resend email delivery (user reported not receiving emails at forest@imosapp.com)
- Remove debug endpoint `/api/debug/db-info` from production (contains sensitive info)

### P1 (High)
- Auth refactor to bcrypt hashed passwords
- Fix forgot-password to actually send reset code via Resend email
- Lead Notification System Phase 2 (push notifications)
- Voice Help Assistant Backend

### P2 (Medium)
- Code Cleanup (~80 dead files, route extraction from server.py)
- Full Twilio Integration (move from MOCK to live)
- WhatsApp Integration
- White-Label System (custom domains, org branding)
- Full Inventory Management Module
- Training Hub content
- Leaderboard toggle verification
- React Hydration Error #418 fix
- Migrate remaining ~25 Modal → WebModal

## Key API Endpoints
- POST /api/auth/login - User login
- POST /api/auth/admin-reset - Emergency password reset (secret: iMOs-Emergency-Reset-2026)
- GET /api/debug/db-info - Database diagnostic (TEMPORARY - remove for production)
- DELETE /api/contacts/delete - Bulk delete contacts
- DELETE /api/contacts/{id} - Single delete contact
- POST /api/congrats/create - Create congrats card
- GET /api/health - Health check

## Key DB Schema
- users: { email, password (plain text!), name, role, status, is_active, social_links, ... }
- contacts: { name, email, phone, photo, tags, user_id, ... }
- congrats_cards: { salesman_id, customer_name, photo, message, ... }
- conversations: { user_id, contact_id, status, ai_enabled, ai_mode, ... }

## Credentials
- Super Admin: forest@imosapp.com / Admin123!
- Preview seed admin: admin@imosapp.com / iMOs2026!

## Key Files
- `/app/backend/server.py` — Main backend, admin-reset endpoint, debug endpoint
- `/app/backend/.env` — Production MONGO_URL, Resend key, Twilio keys
- `/app/backend/routers/database.py` — DB connection with get_default_database() fallback
- `/app/frontend/services/api.ts` — API client, relative URL fix for web
- `/app/frontend/components/WebModal.tsx` — Web-safe modal replacement
- `/app/frontend/components/common/Toast.tsx` — Toast notification system
