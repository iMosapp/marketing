# i'M On Social - Product Requirements Document

## Original Problem Statement
Build a Relationship Management System (RMS) / CRM for automotive sales professionals. AI-powered, human-to-human relationship building where every follow-up is deliberate, meaningful, and personal.

## Core Architecture
- **Frontend:** React Native / Expo (web)
- **Backend:** FastAPI (Python)
- **Database:** MongoDB Atlas
- **Marketing Site:** Static HTML in `/app/marketing/build/` (deployed to Vercel via GitHub)
- **Integrations:** Resend (email), Twilio (MOCKED), OpenAI (via emergentintegrations), Emergent Object Storage, Pillow, qrcode, apscheduler

---

## What's Been Implemented

### Tracked Media System (Mar 27, 2026) -- LATEST
- **`POST /api/media/upload-tracked`**: Upload photo or video, get a tracked short URL. When recipient opens it, view is logged as contact_event with full analytics.
- **`GET /api/media/view/{media_id}`**: Branded viewing page showing photo/video full-screen with salesperson branding, caption, and OG meta tags. Logs views with deduplication.
- **`GET /api/media/stats/{media_id}`**: View stats for tracked media (view count, last viewed, etc.)
- Viewing page auto-pulls salesperson name, store branding, and accent color.
- Views logged as `media_viewed` contact_events + engagement signals.

### Universal URL Tracking System (Mar 27, 2026)
- **`POST /api/s/wrap`**: Universal URL wrapper — auto-detects YouTube, review links. Idempotent.
- **`POST /api/s/wrap-bulk`**: Bulk URL wrapping.
- **`POST /api/campaigns/{user_id}/{campaign_id}/rewrap-links`**: Fix existing campaign links.
- **Auto-wrap in Campaign Edits**: `PUT /api/campaigns/{user_id}/{campaign_id}` auto-wraps URLs.
- **Auto-wrap in Training Hub**: Lesson create/update auto-wraps `video_url`.
- **Auto-wrap in Templates**: Template create/update auto-wraps all URLs in content.
- **Auto-wrap in Scheduler**: Background campaign step processor wraps URLs before creating pending sends.

### Previous Work (see CHANGELOG for full history)
- Contact-to-User workflow, Activity Feed grouping, RBAC fix, UI fixes
- Scheduler stability (safe_job wrapper), Campaign hourly delay + AI toggle fixes
- Marketing presentation decks, SEO guide routing

---

## Key API Endpoints (New)
- `POST /api/media/upload-tracked` — Upload photo/video, get tracked link
- `GET /api/media/view/{media_id}` — Branded viewing page
- `GET /api/media/stats/{media_id}` — View analytics
- `POST /api/s/wrap` — Universal URL tracking
- `POST /api/s/wrap-bulk` — Bulk URL tracking
- `POST /api/campaigns/{user_id}/{campaign_id}/rewrap-links` — Fix campaign links

---

## Prioritized Backlog

### P0
- Deploy and run `rewrap-links` on production "Onboarding Videos" campaign
- Integrate tracked media upload into frontend composer (thread/[id].tsx)

### P1
- App Store Preparation (eas.json, push notifications)
- AI-Powered Outreach (sold tag follow-ups)
- Gamification & Leaderboards
- Link Analytics Dashboard (click-through rates by campaign, video watch rates)

### P2
- Full Twilio Integration (currently MOCK)
- WhatsApp Integration
- Stripe for partner invoices
- Inventory Management Module
- Mobile tags sync issue
- Refactor large files (admin.py, contact/[id].tsx)

## Test Credentials
- Super Admin: `forest@imosapp.com` / `Admin123!`

## 3rd Party Integrations
- **Resend:** Transactional emails
- **MongoDB Atlas:** Primary database
- **Twilio:** MOCK mode
- **OpenAI:** AI features via emergentintegrations
- **apscheduler:** Backend job scheduling

## Key Files Modified This Session
- `/app/backend/routers/short_urls.py` — Added `wrap` and `wrap-bulk` endpoints
- `/app/backend/routers/campaigns.py` — Added `rewrap-links` endpoint, auto-wrap in `update_campaign`
- `/app/backend/routers/training.py` — Auto-wrap in lesson create/update
- `/app/backend/routers/templates.py` — Auto-wrap in template create/update
- `/app/backend/routers/media_tracking.py` — NEW: Tracked media upload + viewing page
- `/app/backend/scheduler.py` — `_auto_wrap_urls` helper for background jobs
- `/app/backend/server.py` — Registered media_tracking router
