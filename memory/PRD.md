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
- Photo deletion removes DB references only; object storage cleanup is deferred.

### Role System
- DB may have legacy roles: `admin` (= `org_admin`), `manager` (= `store_manager`)
- Backend `permissions.py` maps both legacy and canonical role names
- Frontend `authStore.ts` normalizes roles via `normalizeUser()` on every user load

### Auth Persistence (iOS PWA)
- 3-layer: AsyncStorage -> IndexedDB -> Cookie (`imonsocial_session`)
- Logout clears BOTH `imonsocial_session` and `imonsocial_uid` cookies

---

## What's Been Implemented

### Photo Gallery Fixes (Mar 23, 2026) -- LATEST
- **Bug Fix:** Fixed wrong photo selection in full-screen viewer — `renderItem` was using `galleryWidth || screenWidth` but `getItemLayout` used `screenWidth`, causing mismatched scroll offsets. Now both use `screenWidth` consistently.
- **Feature:** Added photo delete button (red trash icon) in full-screen viewer bottom bar with confirmation dialog. Handles profile, history, congrats, and birthday photos.
- **Backend:** New `DELETE /api/contacts/{user_id}/{contact_id}/photos` endpoint — profile deletion promotes latest history photo; history/congrats/birthday deletion removes DB references.
- **Testing:** 100% pass (11/11 backend, all frontend gallery features verified)

### Production Readiness Audit (Mar 23, 2026)
- **Security:** Removed `/api/auth/emergency-reset` endpoint from `auth.py`
- **Performance:** Added 20+ production MongoDB indexes for contacts, conversations, messages, campaign_enrollments, notifications, tags, campaign_pending_sends
- **Bug Fix:** Fixed "vanishing contacts" race condition in `contacts.tsx` — added `requestSeq` counter to prevent stale API responses from overwriting newer data; fixed `useFocusEffect` stale closure
- **Performance:** Moved inline photo backfill to `asyncio.create_task()` background processing
- **Feature:** Enhanced email template with personal signature — `build_branded_email` now includes sender's photo, name, title, phone, email, and digital card link

### Prior Session Work (Mar 22, 2026)
- New User Onboarding Fix, Date Picker Fix, Inbox Swipe Enhancements
- Bcrypt Auth Fallback, App-wide Font Bump
- Contacts UI Polish (expandable action button, dark mode fix)
- Relationship Intel routing fix, Template Variables fix
- Inbox Unread Logic Fix, Contact Photo Deduplication
- Sticky Redirect Loop Fix, Touchpoints Mismatch Fix
- Card "Create & Send" Fix

---

## Key API Endpoints
- `POST /api/auth/login` — user authentication
- `GET /api/contacts/{user_id}` — contacts with sort, search, team view
- `DELETE /api/contacts/{user_id}/{contact_id}/photos` — delete gallery photo
- `PATCH /api/contacts/{user_id}/{contact_id}/profile-photo` — set profile photo
- `GET /api/contacts/{user_id}/{contact_id}/photos/all` — get all deduplicated photos
- `POST /api/messages/send/{user_id}` — send messages with template vars + email signature
- `GET /api/tasks/{user_id}/summary` — includes async catch-up

---

## Prioritized Backlog

### P1
- App Store Preparation (eas.json, app.json store config, push notifications)
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
