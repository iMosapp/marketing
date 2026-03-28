# i'M On Social - Product Requirements Document

## Original Problem Statement
Build a Relationship Management System (RMS) / CRM for automotive sales professionals. AI-powered, human-to-human relationship building where every follow-up is deliberate, meaningful, and personal.

## Core Architecture
- **Frontend:** React Native / Expo (web PWA)
- **Backend:** FastAPI (Python) with async Motor (MongoDB driver)
- **Database:** MongoDB Atlas
- **Integrations:** Resend (email), Twilio (MOCKED), OpenAI, Emergent Object Storage, apscheduler

---

## What's Been Implemented

### Architecture Refactor — Phase 1: Shared Foundations (Mar 28, 2026) -- LATEST

Created the core building blocks for a clean, maintainable codebase:

**New files created:**
- `frontend/utils/photoUrl.ts` — Single source of truth for all photo URL resolution. `resolvePhotoUrl()`, `resolveUserPhotoUrl()`, `resolveContactPhotoUrl()`. Handles relative `/api/images/`, absolute `https://`, base64, native vs web.
- `frontend/types/index.ts` — Centralized TypeScript interfaces: `User`, `Contact`, `Message`, `Conversation`, `PartnerBranding`, `UserRole`, `AvatarSize`. Stop redefining types per-file.
- `frontend/components/Avatar.tsx` — UPGRADED: now uses `OptimizedImage` (expo-image disk cache), URL resolution via `photoUrl.ts`, consistent sizing system (`xs/sm/md/lg/xl/xxl`), backward-compatible legacy numeric size support, graceful error fallback to initials.
- `frontend/components/account/ProfilePhotoUpload.tsx` — Self-contained photo upload component. Web file picker + native camera/library, proper multipart pipeline, loading states, error handling. Extracted from `my-account.tsx`.

**Files updated:**
- `activity.tsx` — Removed inline duplicate `Avatar` component (18 lines → import shared one)
- `contacts.tsx` — Replaced raw `Image` + manual initials with shared `Avatar`
- `my-account.tsx` — Replaced 150+ lines of photo upload logic with `<ProfilePhotoUpload>` component. Removed unused imports (`Image`, `ImagePicker`).
- `contact/[id].tsx` — Replaced inline `resolvePhotoUrl()` with shared `utils/photoUrl.ts`

**Architecture principle established:** Every place in the app that shows a person's photo now uses the same Avatar component and the same URL resolver. Fixing a photo bug once fixes it everywhere.

### Auth Storage Hardening (Mar 28, 2026) -- LATEST
- Flipped storage write priority: **IndexedDB is now primary** (awaited), AsyncStorage is a fast-read cache
- All AsyncStorage reads wrapped in `safeAsyncGet` — never throws, returns null if blocked
- All AsyncStorage writes wrapped in individual try/catch — storage failures are non-fatal
- `login`, `signup`, `logout`, `loadAuth`, `startImpersonation`, `stopImpersonation` all hardened
- SW registration `.catch(() => {})` added — was causing unhandled promise rejections on iOS
- Removed `window.location.reload()` from `+html.tsx` SW cleanup — was causing login request abort race condition on mobile
- Face ID / biometric login unchanged — uses iOS Keychain (SecureStore), unaffected by localStorage restrictions

### Mobile Login iOS Fixes (Mar 28, 2026)
- Root cause: `(tabs)/_layout.tsx` used `!user.onboarding_complete` (truthy check) which evaluated to `true` for `null` values, silently redirecting users like Matt (who have `onboarding_complete: null`) to `/onboarding` on every login
- Fix: Changed to strict equality `user.onboarding_complete === false` — only new users in active onboarding flow get redirected
- `+html.tsx` SW cleanup now reloads once after unregistering old SWs (prevents stale SWs from intercepting login requests)
- `login.tsx` catch block improved: full error logging (status, code, stack), granular 402/403 messages, "close and reopen" guidance for JS runtime errors

### Click Tracking Deduplication (Mar 28, 2026)
- Added bot/prefetch user-agent filtering (iMessage, WhatsApp, Facebook, Google, etc.)
- Added IP-based dedup (same IP + same link within 60 seconds = 1 click)
- Increased contact_event dedup window from 2-5 min to 30 min
- Added DB index for click dedup queries
- Congrats card views now skip bot requests

### PWA Login Fix (Mar 28, 2026)
- Service worker v5: never intercepts navigation, only caches static assets passively
- SW registration moved to post-login (not on login page)
- Login page actively kills any existing broken service workers
- Removed `withCredentials: true` from axios (unnecessary for same-origin)
- Fixed CORS `allow_credentials` + wildcard origin conflict
- Added auto-retry on login (1 silent retry for network hiccups)
- iOS keyboard fix: proper inputmode/autocomplete/user-select attributes
- Created `fix.html` — self-service SW/cache clearing page for stuck users

### Password Security Fix (Mar 28, 2026)
- Fixed 3 user creation paths storing passwords as plain text (admin, team invite register, team invite accept)
- All now use bcrypt via `hash_password()`
- Added `admin-fix-login` diagnostic+reset endpoint (case-insensitive)
- Added `admin-fix-all-passwords` bulk migration endpoint
- Login endpoint optimized: background tasks for timezone/lifecycle, under 0.5s response

### Profile Photo & Bio Fix (Mar 28, 2026)
- Fixed duplicate PATCH `/api/users/{user_id}` in server.py not clearing `photo_path`/`photo_avatar_path`
- Fixed `refreshUserData` in my-account.tsx to sync auth store

### Previous Session Work
- Universal Link Tracking, Tracked Media, Production Stability (async motor), Campaign removal/archive

---

## Architecture Refactor Roadmap

### Phase 1 — Shared Foundations ✅ DONE (Mar 28, 2026)
- `utils/photoUrl.ts` — unified photo URL resolver
- `types/index.ts` — centralized TypeScript interfaces
- `components/Avatar.tsx` — upgraded, OptimizedImage, consistent sizing
- `components/account/ProfilePhotoUpload.tsx` — extracted from my-account.tsx
- `activity.tsx` — removed inline Avatar duplicate
- `contacts.tsx` — uses shared Avatar
- `contact/[id].tsx` — uses shared resolvePhotoUrl

### Phase 2 — Account Page Decomposition (NEXT)
Split `my-account.tsx` (1,700 lines) into:
- `components/account/ProfileInfo.tsx` — name, bio, title, phone editing
- `components/account/SocialLinks.tsx` — social handle management
- `components/account/SecuritySettings.tsx` — password change, 2FA
- `components/account/PresenceLinks.tsx` — digital card, link page, showcase links
- `my-account.tsx` reduces to ~200 lines (layout + state coordinator only)

### Phase 3 — Contact Page Decomposition (HIGH IMPACT)
Split `contact/[id].tsx` (6,000 lines) into:
- `components/contact/ContactHeader.tsx` — photo, name, tags, quick actions
- `components/contact/ConversationThread.tsx` — SMS/email message thread
- `components/contact/ActivityFeed.tsx` — CRM timeline events
- `components/contact/ContactNotes.tsx` — notes, tasks, reminders
- `components/contact/CongratsCardSender.tsx` — card sending flow
- `components/contact/AIAssistant.tsx` — AI suggestions panel
- `components/contact/ContactEditModal.tsx` — edit contact info
- `contact/[id].tsx` reduces to ~300 lines

### Phase 4 — Backend Service Layer
Extract `admin.py` (4,000 lines) into:
- `services/user_service.py` — user CRUD, role changes, activation
- `services/hierarchy_service.py` — org/store assignment logic
- `services/permission_service.py` — role-based access control
- `admin.py` becomes thin routing layer only (~300 lines)

### Phase 5 — Shared UI Components
- `components/common/StatusBadge.tsx` — active/pending/sold tags
- `components/common/EmptyState.tsx` — consistent empty screens
- `components/common/LoadingScreen.tsx` — consistent loading states
- `components/common/SectionHeader.tsx` — reusable section titles

---

## Prioritized Backlog

### P0
- ✅ Mobile login routing fix for users with null onboarding_complete (DONE)
- ✅ Architecture Phase 1 foundations (DONE)
- Verify PWA login/iOS fix works after deployment
- Deploy all Mar 28 fixes

### P1
- Architecture Phase 2 — account page decomposition
- Architecture Phase 3 — contact page decomposition  
- App Store Preparation (`eas.json`, `app.json`)
- Push Notifications (mobile alerts)
- AI-Powered Outreach (contextual follow-ups)
- Gamification & Leaderboards

### P2
- Architecture Phase 4 — backend service layer
- Architecture Phase 5 — shared UI components
- Typing indicators + read receipts (WebSocket already in place)
- Full Twilio / WhatsApp / Stripe integration
- Inventory Management Module
- Mobile tags sync issue

## Test Credentials
- Super Admin: `forest@imosapp.com` / `Admin123!`
- Test User (no store/org): `mjeast1985@gmail.com` / `NavyBean1!` (preview) / `Mjeast1985!` (production)
