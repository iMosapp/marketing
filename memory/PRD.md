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

## Prioritized Backlog

### P0
- ✅ Mobile login routing fix for users with null onboarding_complete (DONE)
- Verify PWA login fix works after deployment (send Matt fix.html to clear old SW cache if issue persists)
- Verify click dedup works in production

### P1
- App Store Preparation (`eas.json`, `app.json`)
- Push Notifications (mobile alerts)
- AI-Powered Outreach (contextual follow-ups)
- Gamification & Leaderboards
- Link Analytics Dashboard

### P2
- Full Twilio / WhatsApp / Stripe integration
- Inventory Management Module
- Mobile tags sync issue
- Refactor `contact/[id].tsx` (6000+ lines) and `admin.py` monolith

## Test Credentials
- Super Admin: `forest@imosapp.com` / `Admin123!`
