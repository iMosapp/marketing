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

### Click Tracking Deduplication (Mar 28, 2026) -- LATEST
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
- Verify PWA login fix works after deployment
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
