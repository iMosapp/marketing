# iMOs - Product Requirements Document

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

### Session - Feb 26, 2026
- [x] Team Chat UI Fix: Web compatibility for dropdowns and create button
- [x] Team Chat Search: Channel search/filter bar
- [x] Contact Deletion: Single and bulk delete (backend + frontend)
- [x] Digital Card UI: Social links moved above voice recorder
- [x] Admin Linking Fix: Fixed unclickable "Link Existing" buttons
- [x] User Creation Modal Fix: Web-compatible copy buttons
- [x] Inbox Email Prompt Fix: Check existing email before prompting
- [x] Congrats Card Creation Fix: Web-compatible file upload
- [x] Congrats Card Feature: Full create + share flow at /settings/create-congrats
  - **Relocated to My Account → QUICK ACTIONS** next to "My Digital Card", with "Edit Digital Card" moved down (Feb 26, 2026)
- [x] **Social Media Username-Only Inputs** (Feb 26, 2026):
  - Edit Digital Card: Social fields now show URL prefix (e.g. facebook.com/) with just username input
  - Auto-strips @ symbol from input
  - Digital Card constructs full URL from base URL + username
  - Backwards compatible with existing data (full URLs or usernames both work)
- [x] **Fixed mobile Safari login crash** (Feb 26, 2026):
  - Wrapped expo-haptics calls in try-catch to prevent login handler crash on mobile web
- [x] **Fixed ALL shareable links to use production URL** (Feb 26, 2026):
  - Business cards, congrats cards, QR codes, vCards, review links all use https://app.imosapp.com/
  - Removed all preview URL references from share/copy link code
  - Files fixed: card/[userId].tsx, thread/[id].tsx, congrats/[cardId].tsx, subscription/pricing.tsx
- [x] **Eliminated short URL redirects for business cards** (Feb 26, 2026):
  - Business cards previously shared as `https://app.imosapp.com/api/s/{code}` (backend redirect) which broke on production
  - Now uses direct links: `https://app.imosapp.com/card/{userId}` — same clean format as congrats cards
  - Removed shortUrl state and loadShortUrl API call from card/[userId].tsx
  - All outgoing links now follow consistent direct-link pattern:
    - Business cards: `https://app.imosapp.com/card/{userId}`
    - Congrats cards: `https://app.imosapp.com/congrats/{cardId}`
    - Review links: `https://app.imosapp.com/review/{storeSlug}`
    - Invite links: `https://app.imosapp.com/auth/login?email=...`
    - vCards: `https://app.imosapp.com/api/card/vcard/{userId}`
  - Short URL service (`/api/s/`) still exists in backend for legacy links but is no longer generated for new shares
- [x] **MONGO_URL deployment fix** (Feb 26, 2026):
  - Removed MONGO_URL from backend/.env to prevent overwriting production config on deploy
  - Created .env.local (gitignored) for preview environment
  - server.py loads .env then .env.local as override
- [x] **Admin password reset endpoint** (Feb 26, 2026):
  - POST /api/auth/admin-reset with secret key for emergency password resets
- [x] **Full QA audit** (Feb 26, 2026):
  - All 31 More menu routes return 200
  - Backend APIs 100% working
  - No broken links in navigation

## Architecture
- Frontend: React Native Web (Expo) with file-based routing
- Backend: FastAPI with MongoDB
- Database: MongoDB (local in preview, Emergent-hosted in production)
- 3rd Party: OpenAI (Jessi AI), Resend (email), Twilio (SMS - mocked)

### Session - Feb 26, 2026 (Fork: Build Fix)
- [x] **Fixed 4 broken Toast import paths** (Feb 26, 2026):
  - `app/(tabs)/team.tsx`: `../components/common/Toast` → `../../components/common/Toast`
  - `app/admin/onboarding-settings.tsx`: `../components/common/Toast` → `../../components/common/Toast`
  - `app/admin/lead-sources/index.tsx`: `../../components/common/Toast` → `../../../components/common/Toast`
  - `app/partner/agreement/[agreementId].tsx`: `../../components/common/Toast` → `../../../components/common/Toast`
- [x] **Verified all session fixes intact**: Login, all 5 tabs, Website field, Congrats Cards, Lead Sources, Admin Dashboard, admin-reset endpoint
- Testing: 100% pass rate (iteration_35.json)

## Known Issues
- User account inactive status on production (needs admin reactivation)
- Twilio SMS is in mock mode
- React Hydration Error #418 (cosmetic, not blocking)
- Password stored as plain text (security risk, needs bcrypt refactor)
- ~25 files still use RN Modal instead of WebModal (non-blocking, buttons work via IS_WEB checks)

## Prioritized Backlog
### P0 (Critical)
- None currently blocking

### P1 (High)
- Lead Notification System Phase 2 (push notifications)
- Voice Help Assistant Backend
- Auth refactor to bcrypt hashed passwords

### P2 (Medium)
- WhatsApp Integration
- White-Label System (custom domains, org branding)
- Full Inventory Management Module
- Searchable Training Manual
- Reports & Analytics population
- Leaderboard toggle verification
- React Hydration Error #418 fix

## Key API Endpoints
- POST /api/auth/login - User login
- POST /api/auth/admin-reset - Emergency password reset
- DELETE /api/contacts/delete - Bulk delete contacts
- DELETE /api/contacts/{id} - Single delete contact
- POST /api/congrats/create - Create congrats card
- GET /api/congrats/card/{id} - Get congrats card
- PUT /api/admin/stores/{id} - Link account to org
- PUT /api/admin/users/{id} - Link user to org

## Key DB Schema
- users: { email, password (plain text!), name, role, status, social_links, ... }
- contacts: { name, email, phone, photo, photo_thumbnail, tags, ... }
- congrats_cards: { salesman_id, customer_name, photo, message, ... }
