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

### Production Readiness Audit (Mar 23, 2026) -- LATEST
- **Security:** Removed `/api/auth/emergency-reset` endpoint from `auth.py`
- **Performance:** Added 20+ production MongoDB indexes for contacts, conversations, messages, campaign_enrollments, notifications, tags, campaign_pending_sends
- **Bug Fix:** Fixed "vanishing contacts" race condition in `contacts.tsx` — added `requestSeq` counter to prevent stale API responses from overwriting newer data; fixed `useFocusEffect` stale closure by adding `loadContacts` to dependency array
- **Performance:** Moved inline photo backfill to `asyncio.create_task()` background processing (no longer blocks GET /contacts response)
- **Feature:** Enhanced email template with personal signature — `build_branded_email` now includes sender's photo, name, title, phone, email, and digital card link in every outgoing email
- **Testing:** 100% pass (13/13 backend, frontend verified)

### Card Send Download Bug Fix + Session Fixes (Mar 22, 2026)
- **Card "Create & Send" Download Bug:** Removed web-specific auto-download code from `create-card.tsx`
- **CS-Login Redirect Fix:** Fixed `index.tsx` and `+html.tsx` localStorage `pwa_brand` flag sticking
- **Touchpoints Count Mismatch Fix:** Changed `_catchup_overdue_campaign_tasks()` to fire-and-forget
- **Contacts Light Mode Fix:** Added `colors` to `renderContact` useCallback dependency array
- **Photo Duplication Fix:** Backend `get_all_contact_photos` deduplicates by URL
- **Inbox Mark-as-Read:** Thread page auto-marks conversations as read on open
- **Template Variable Substitution:** Added `substitute_template_vars()` to message send endpoints

### Contact List Expandable Actions + Name Fix (Mar 22, 2026)
- Expandable Action Button for call/text/email
- Emergency Password Reset endpoint (NOW REMOVED)
- bcrypt Resilience fallback

### Inbox Swipe Actions, Task Modal & Filters (Mar 22, 2026)
- Quick Task Modal, Flagged & Archived Filters, Team Inbox Swipe Actions

### New User Onboarding Multi-Step Flow (Mar 22, 2026)
- 4-step guided onboarding, AI Bio generation

### Enhanced User Creation + Auto-Contact (Mar 21, 2026)
- Mandatory fields, Optional enrichment, SMS option, Auto-contact creation

### Jessi AI Chat Widget (Mar 21, 2026)
- AI-powered chat widget on marketing pages, lead pipeline, team inbox integration

### Campaign System Fixes (Mar 18, 2026)
- Scheduler hourly delay fix, AI toggle fix, task catch-up mechanism

---

## Key API Endpoints
- `POST /api/auth/login` — user authentication
- `GET /api/contacts/{user_id}` — contacts with sort, search, team view
- `POST /api/messages/send/{user_id}` — send messages with template vars + email signature
- `POST /api/messages/{user_id}/{conversation_id}` — send in conversation
- `GET /api/tasks/{user_id}/summary` — includes async catch-up
- `GET /api/seo/health-score/{user_id}` — cached SEO score
- `POST /api/chat/start` — start Jessi chat session

---

## Prioritized Backlog

### P1
- App Store Preparation (eas.json, app.json store config)
- Gamification & Leaderboards
- AI-Powered Outreach (contextual follow-up on "sold" tag)
- Lead Notification System Phase 2 (push notifications)
- Voice Help Assistant Backend

### P2
- Full Twilio Integration (currently MOCK)
- WhatsApp Integration
- Training Hub video content
- Inventory Management Module
- Refactor large files (admin.py 3700+ lines)
- Rename `stores` to `accounts` throughout codebase

## Known Issues
- P2: React Hydration Error #418
- P2: Mobile tags sync
- P2: Leaderboard toggle not fully tested

## Test Credentials
- Super Admin: `forest@imosapp.com` / `Admin123!`

## 3rd Party Integrations
- **Resend:** Transactional emails
- **MongoDB Atlas:** Primary database
- **Twilio:** MOCK mode
- **OpenAI:** AI features via emergentintegrations
- **apscheduler:** Backend job scheduling (9 jobs)
