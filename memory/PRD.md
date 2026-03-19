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

### SEO Health Score Performance Fix (Mar 19, 2026) -- LATEST
- **Bug Fix:** Store query was using `{"store_id": store_id}` instead of `{"_id": ObjectId(store_id)}` — stores were never found
- **Performance:** Added 5-minute TTL in-memory cache (`_score_cache`) to avoid recomputing on every page load
- **Performance:** Replaced `find().to_list()` with MongoDB aggregation pipelines for reviews and short_urls
- **Frontend:** Fixed blank screen on SEO Health page — now shows error state with retry button instead of returning null
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
