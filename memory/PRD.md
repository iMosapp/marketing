# i'M On Social - Product Requirements Document

## Original Problem Statement
Build a Relationship Management System (RMS) / CRM for automotive sales professionals. AI-powered, human-to-human relationship building where every follow-up is deliberate, meaningful, and personal.

## Core Architecture
- **Frontend:** React Native / Expo (web)
- **Backend:** FastAPI (Python)
- **Database:** MongoDB Atlas
- **Integrations:** Resend (email), Twilio (MOCKED), OpenAI (via emergentintegrations), Emergent Object Storage, Pillow, qrcode

---

## CRITICAL RULES

### Image Pipeline
- ALL images -> `utils/image_storage.py` -> WebP -> `/api/images/`
- NEVER add base64 fallbacks. NEVER serve base64 in responses.

### Role System
- DB may have legacy roles: `admin` (= `org_admin`), `manager` (= `store_manager`)
- Backend `permissions.py` maps both legacy and canonical role names
- Frontend `authStore.ts` normalizes roles via `normalizeUser()` on every user load

### Auth Persistence (iOS PWA)
- 3-layer: AsyncStorage -> IndexedDB -> Cookie (`imonsocial_session`)
- Logout clears BOTH `imonsocial_session` and `imonsocial_uid` cookies

---

## What's Been Implemented

### Campaign Dashboard Fix (Mar 19, 2026)
- **Bug Fix:** `GET /campaigns/{user_id}` was returning 500 because `CampaignSequenceStep.step` was required but some DB records lacked it. Made it default to 0 and auto-assign sequentially on load.
- **Bug Fix:** `GET /campaigns/scheduler/pending` endpoint didn't exist — dashboard pending/upcoming counts were always 0. Created new endpoint.
- **Bug Fix:** `POST /campaigns/scheduler/process` had wrong name (backend had `/trigger`). Added alias endpoint.
- **Bug Fix:** Route ordering — moved static `/scheduler/*` routes before `/{user_id}` to prevent FastAPI matching "scheduler" as a user_id.
- **Testing:** 12/12 backend, 100% frontend pass. Dashboard now shows 2 Active, 11 Upcoming, 22 Completed.

### Inbox Multi-Channel Composer & Navigation Fix (Mar 21, 2026) -- LATEST
- **Feature:** Integrated `ChannelPicker` into `/app/frontend/app/thread/[id].tsx` so inbox composer shows all org-enabled messaging channels (SMS, WhatsApp, Messenger, Telegram, LinkedIn, Clipboard) instead of just SMS/Email toggle
- **Fix:** Changed `router.push()` to `router.replace()` in `create-card.tsx` (navigateToThread) and `quick-send/[action].tsx` to prevent deep navigation stack buildup (4-swipe-back problem)
- **Testing:** 19/19 backend, 100% frontend pass

### Calendar Systems Landing Page (Mar 20, 2026)
- Rebuilt `/marketing/build/calendar-systems/index.html` with full sales presentation content
- 11 sections covering: core reframe, problem statement, stat comparison, before/after flip, 5 value propositions, how-it-works flow, salesperson benefits, objection handling, white-label features, positioning statement, and closing vision
- Content sourced from user's detailed sales pitch, rewritten conversationally (not word-for-word)

### SEO Health Score Performance Fix (Mar 19, 2026)
- **Bug Fix:** Store query was using `{"store_id": store_id}` instead of `{"_id": ObjectId(store_id)}` — stores were never found
- **Performance:** Added 5-minute TTL in-memory cache (`_score_cache`) to avoid recomputing on every page load
- **Performance:** Replaced `find().to_list()` with MongoDB aggregation pipelines for reviews and short_urls
- **Frontend:** Fixed blank screen on SEO Health page — now shows error state with retry button instead of returning null
- **Feature:** Added "Share My Score" button on SEO Health page + share icon in header — opens UniversalShareModal with score info, digital card link, QR code, and all share channels
- **Testing:** 14/14 backend tests pass, 100% frontend pass

### SEO Health Score Dashboard (Mar 18, 2026)
- Backend: GET /api/seo/health-score/{user_id} — calculates 0-100 score across 5 weighted factors
- Factors: Profile Completeness (20), Review Strength (20), Content Distribution (20), Search Visibility (20), Activity & Freshness (20)
- Backend: GET /api/seo/health-score/team/{store_id} — team leaderboard ranked by score
- Frontend: Dedicated /seo-health page with score circle, factor breakdown, tips, and team tab
- Frontend: SEO Health widget on Home screen

### White-Label Partner Sold Workflow System (Mar 17, 2026)
- Full sold-event pipeline with validation, delivery, and retry
- Idempotency: one active event per contact

### SEO & AEO Phase 1 & 2 (Mar 18, 2026)
- Dynamic sitemap.xml, robots.txt, meta tags, Schema.org JSON-LD
- SEO-friendly salesperson URLs, store directory pages, UTM tracking

### Marketing Page Fixes (Feb-Mar 2026)
- Book a Demo modal, header/logo standardization across 29 pages

### Campaign System Fixes (Mar 18, 2026)
- Scheduler hourly delay fix, AI toggle fix, task catch-up mechanism

### RBAC Security Fix (Mar 18, 2026)
- Partner admin scoping on hierarchy endpoints

---

## Key API Endpoints
- `GET /api/messaging-channels/user/{user_id}` — org-enabled messaging channels
- `GET /api/messaging-channels/available` — all available channel definitions
- `GET /api/seo/health-score/{user_id}` — cached SEO score (5-min TTL)
- `GET /api/seo/health-score/team/{store_id}` — team leaderboard
- `PATCH /api/contacts/{user_id}/{contact_id}/tags` — triggers sold workflow
- `GET /api/tasks/{user_id}/summary` — includes catch-up mechanism
- `GET /api/seo/sitemap.xml` — dynamic sitemap

---

## Prioritized Backlog

### P1
- Gamification & Leaderboards
- AI-Powered Outreach (contextual follow-up on "sold" tag)
- Lead Notification System Phase 2 (push notifications)
- Voice Help Assistant Backend
- Refactor Authentication (bcrypt)

### P2
- Rename `stores` → `accounts` throughout the codebase
- Full Twilio Integration (currently MOCK)
- WhatsApp Integration
- Training Hub video content
- Inventory Management Module
- Refactor large files (admin.py 3700+ lines)

## Known Issues
- P2: Mobile tags sync
- P2: React Hydration Error #418
- P2: Leaderboard toggle not fully tested

## Test Credentials
- Super Admin: `forest@imosapp.com` / `Admin123!`

## 3rd Party Integrations
- **Resend:** Transactional emails
- **MongoDB Atlas:** Primary database
- **Twilio:** MOCK mode
- **OpenAI:** AI features via emergentintegrations
- **apscheduler:** Backend job scheduling (9 jobs)
