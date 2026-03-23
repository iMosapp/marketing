# i'M On Social - Product Requirements Document

## Original Problem Statement
Build a Relationship Management System (RMS) / CRM for automotive sales professionals. AI-powered, human-to-human relationship building where every follow-up is deliberate, meaningful, and personal.

## Core Architecture
- **Frontend:** React Native / Expo (web)
- **Backend:** FastAPI (Python)
- **Database:** MongoDB Atlas
- **Integrations:** Resend (email), Twilio (MOCKED), OpenAI (via emergentintegrations), Emergent Object Storage, Pillow, qrcode

---

## What's Been Implemented

### Production Crash Fix + ErrorBoundary (Mar 24, 2026) -- LATEST
- **Critical Bug Fix:** Added missing `GET /api/users/{user_id}` endpoint. Previously only `PATCH` existed, causing **405 Method Not Allowed** when My Account page tried to refresh user data. This was a likely contributor to the "everything crashing" reports.
- **ErrorBoundary:** Added a global React ErrorBoundary component wrapping the entire app. Any uncaught rendering error now shows a "Try Again" recovery screen instead of crashing the whole app to a white/blank screen. Critical for production stability with 50-60 users.
- **Error Reporting System:** Built full crash/error reporting pipeline:
  - `POST /api/errors/report` — frontend auto-sends crash data (render crashes, unhandled promise rejections, 5xx API errors, network failures)
  - `GET /api/errors/recent?limit=50&error_type=render_crash&user_id=X` — pull recent error reports with filtering
  - `DELETE /api/errors/clear` — clear old reports
  - Reports include: error message, stack trace, page/screen, user info, platform, timestamp
  - Deduplication built in (same error only reported once per 60s)
  - Also logs to backend console as WARNING for real-time visibility

### Training Hub + Video Quick-Send Templates (Mar 23, 2026)
- **Training Hub:** Populated "Onboarding Videos" track with 8 YouTube tutorial videos (Saving The App, Setting Up Your Profile, Home Screen, Contacts, Inbox, Best Practices, The 30 Second Workflow, Tags & Campaigns). Videos play inline via embedded YouTube player on web, or open in browser on native.
- **Quick-Send Templates:** Added 8 video message templates (category: "training_video") to the template system. Auto-seeded for existing users when they open templates. Each has a friendly message + YouTube link with {name} variable.
- **Template Categories:** Added training_video, referral, sold, review categories to the frontend category picker.
- **YouTube Embed:** Enhanced training-hub.tsx to embed YouTube videos inline (16:9 aspect ratio iframe) with fallback to Linking.openURL on native.

### UI Fixes (Mar 23, 2026)
- **Persona page:** Pushed header below Ask Jessi bar (paddingTop 60→82 iOS, 20→40 Android). Added "Save Changes" button at bottom next to "Retrain My AI".
- **Touchpoints badge:** Moved "X pending" from title row overflow position to subtitle line below "Today's Touchpoints".
- **Root route:** Removed static public/index.html that was intercepting Expo Router and showing marketing page instead of login redirect.

### Showcase Approvals Photo Fix + Gallery Delete (Mar 23, 2026)
- Fixed showcase photos not loading (switched from react-native Image to expo-image, kept relative URLs)
- Added photo delete button in gallery viewer
- Fixed gallery wrong-photo selection (consistent screenWidth in FlatList)

### Production Readiness Audit (Mar 23, 2026)
- Removed emergency-reset security endpoint
- Added 20+ production MongoDB indexes
- Fixed "vanishing contacts" race condition
- Moved photo backfill to async background
- Enhanced email template with personal signature block

---

## Key API Endpoints
- `POST /api/auth/login` — user authentication
- `GET /api/users/{user_id}` — **NEW** user profile data (was 405 before fix)
- `PATCH /api/users/{user_id}` — update user profile fields
- `POST /api/errors/report` — **NEW** receive frontend crash/error reports
- `GET /api/errors/recent` — **NEW** admin view of recent errors (filterable)
- `DELETE /api/errors/clear` — **NEW** clear error reports
- `GET /api/contacts/{user_id}` — contacts with sort, search, team view
- `GET /api/training/tracks` — all training tracks with lesson counts
- `GET /api/training/tracks/{track_id}` — track detail with lessons
- `POST /api/training/seed` — seed default training content
- `GET /api/templates/{user_id}` — user's message templates (auto-seeds missing defaults)
- `GET /api/showcase/pending/{user_id}` — pending showcase entries
- `DELETE /api/contacts/{user_id}/{contact_id}/photos` — delete gallery photo

---

## Prioritized Backlog

### P1
- **Phase 3: Onboarding Drip Campaign** — Automated campaign tied to "new_customer" tag, sends 1 video per day over 8 days
- Wire up email signatures to actual outgoing message sends (messages.py)
- App Store Preparation (eas.json, push notifications)
- Gamification & Leaderboards

### P2
- Full Twilio Integration (currently MOCK)
- WhatsApp Integration
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
- **YouTube:** Embedded video playback in Training Hub
