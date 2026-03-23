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
- Photo deletion removes DB references only; object storage cleanup deferred.
- **Backend returns RELATIVE URLs** (`/api/images/...`). Frontend resolves against page origin (web) or prepends EXPO_PUBLIC_BACKEND_URL (native).

### Role System
- DB may have legacy roles: `admin` (= `org_admin`), `manager` (= `store_manager`)
- Backend `permissions.py` maps both legacy and canonical role names
- Frontend `authStore.ts` normalizes roles via `normalizeUser()` on every user load

### Auth Persistence (iOS PWA)
- 3-layer: AsyncStorage -> IndexedDB -> Cookie (`imonsocial_session`)
- Logout clears BOTH `imonsocial_session` and `imonsocial_uid` cookies

---

## What's Been Implemented

### Showcase Approvals Photo Fix + Gallery Delete (Mar 23, 2026) -- LATEST
- **Bug Fix:** Showcase Approvals photos not loading — root cause: used `Image` from react-native (poor WebP support) instead of `Image` from expo-image. Added `resolveUrl()` for native URL resolution.
- **Root Cause Note:** Supervisor env overrides `APP_URL` with internal preview domain that 404s on images. Absolute URL approach abandoned in favor of relative URLs + frontend resolution.
- **Feature:** Added photo delete button (red trash icon) in gallery full-screen viewer with confirmation dialog
- **Backend:** New `DELETE /api/contacts/{user_id}/{contact_id}/photos` — profile deletion promotes latest history photo
- **Bug Fix:** Gallery FlatList wrong photo selection — `renderItem` width now consistently uses `screenWidth` to match `getItemLayout`
- **Testing:** 100% pass (13/13 backend, all frontend verified)

### Production Readiness Audit (Mar 23, 2026)
- Removed `/api/auth/emergency-reset` security endpoint
- Added 20+ production MongoDB indexes
- Fixed "vanishing contacts" race condition (`requestSeq` counter)
- Moved photo backfill to async background task
- Enhanced email template with personal signature block

### Prior Session Work (Mar 22, 2026)
- New User Onboarding Fix, Date Picker Fix, Inbox Swipe Enhancements
- Bcrypt Auth Fallback, App-wide Font Bump, Contacts UI Polish
- Template Variables fix, Inbox Unread Logic Fix, Photo Deduplication
- Sticky Redirect Loop Fix, Touchpoints Mismatch Fix, Card "Create & Send" Fix

---

## Key API Endpoints
- `POST /api/auth/login` — user authentication
- `GET /api/contacts/{user_id}` — contacts with sort, search, team view
- `DELETE /api/contacts/{user_id}/{contact_id}/photos` — delete gallery photo
- `PATCH /api/contacts/{user_id}/{contact_id}/profile-photo` — set profile photo
- `GET /api/showcase/pending/{user_id}` — pending showcase entries for approval
- `GET /api/showcase/user/{user_id}` — public showcase entries
- `POST /api/messages/send/{user_id}` — send messages with email signature

---

## Prioritized Backlog

### P1
- Wire up email signatures to actual outgoing message sends (messages.py)
- App Store Preparation (eas.json, push notifications)
- Gamification & Leaderboards
- AI-Powered Outreach (contextual follow-up on "sold" tag)

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
