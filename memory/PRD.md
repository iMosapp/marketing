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

### Campaign Template Variables Fix (Mar 24, 2026) -- LATEST
- **Critical Bug:** Campaign messages sent `{review_link}` as literal text instead of the actual review URL. Also missing: `{customer_first_name}`, `{salesman_first_name}`, `{salesman_name}`, `{purchase}`, `{review_url}`.
- **Fix:** Created a centralized `resolve_template_variables()` function in `scheduler.py` that handles ALL template variables with DB lookups for user profile and store review links. Applied to both the campaign step processor and date-triggered campaign paths. Also updated `tasks.py` to use the same shared function.
- **Variables now supported:** `{first_name}`, `{last_name}`, `{name}`, `{contact_name}`, `{customer_first_name}`, `{phone}`, `{salesman_first_name}`, `{salesman_name}`, `{review_link}`, `{review_url}`, `{purchase}`

### Alert.alert Web Crash Fix (Mar 24, 2026)
- **Root Cause:** 36+ files used `Alert.alert()` from React Native without importing `Alert`. This works on native but crashes on web with "Can't find variable: Alert". The thread page was the first to surface this via error reporting.
- **Fix:** Replaced ALL `Alert.alert()` calls across 36 files with the cross-platform `showAlert()` function from `services/alert.ts`. This function uses `window.confirm/alert` on web and `Alert.alert` on native.
- **Also fixed:** Error Reports clear button (was passing button array to `showSimpleAlert` which only accepts callback), digital card page hydration error (#418).

### Error Report Fixes Round 2 + Clear Button (Mar 24, 2026)
- **Clear Button Fix:** The Error Reports page's "Clear All" button was crashing (`showSimpleAlert` doesn't accept button arrays). Switched to `showConfirm` which properly handles confirm/cancel dialogs.
- **Card Page Hydration Fix:** Added `mounted` state pattern to `/card/[userId].tsx` to prevent React #418 on public digital card pages.
- **Share Cancel Noise Suppressed:** Filtered out benign "Abort due to cancellation of share" errors from being reported.

### React Hydration Error #418 Fix + Campaign Stats Fix (Mar 24, 2026)
- **Campaign Stats Fix:** Campaigns list page was showing "0 sent" for all campaigns because the `GET /api/campaigns/{user_id}` endpoint didn't aggregate enrollment data. Added MongoDB aggregation pipeline to compute `messages_sent_count`, `enrollments_total`, `enrollments_active`, `enrollments_completed`, and `last_sent_at` per campaign from `campaign_enrollments`. Removed `response_model=List[Campaign]` that was stripping the new fields.
- **React Hydration #418 Fix:** Public pages (`/showcase/`, `/p/`, `/l/`) were using `window.location.href` and rendering browser-specific content during initial render, causing server-client hydration mismatch.
- **Fix:** Added `mounted` state pattern to all 3 public pages. Content only renders after client mount, ensuring consistent output between SSR and hydration.
- **Pages fixed:** `/app/frontend/app/showcase/[id].tsx`, `/app/frontend/app/p/[userId].tsx`, `/app/frontend/app/l/[username].tsx`

### Production Crash Fix + ErrorBoundary (Mar 24, 2026)
- **Critical Bug Fix:** Added missing `GET /api/users/{user_id}` endpoint. Previously only `PATCH` existed, causing **405 Method Not Allowed** when My Account page tried to refresh user data. This was a likely contributor to the "everything crashing" reports.
- **ErrorBoundary:** Added a global React ErrorBoundary component wrapping the entire app. Any uncaught rendering error now shows a "Try Again" recovery screen instead of crashing the whole app to a white/blank screen. Critical for production stability with 50-60 users.
- **Error Reporting System:** Built full crash/error reporting pipeline:
  - `POST /api/errors/report` — frontend auto-sends crash data (render crashes, unhandled promise rejections, 5xx API errors, network failures)
  - `GET /api/errors/recent?limit=50&error_type=render_crash&user_id=X` — pull recent error reports with filtering
  - `DELETE /api/errors/clear` — clear old reports
  - Reports include: error message, stack trace, page/screen, user info, platform, timestamp
  - Deduplication built in (same error only reported once per 60s)
  - Also logs to backend console as WARNING for real-time visibility
  - Admin UI page at Hub > Internal Operations > Error Reports with "Copy All Reports" button, filters, and trash
  - Mobile-friendly — works on phone with one-tap copy to paste into chat

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
