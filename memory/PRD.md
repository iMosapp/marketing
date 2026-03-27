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

### Universal URL Tracking System (Mar 27, 2026) -- LATEST
- **`POST /api/s/wrap`**: Universal URL wrapper — pass any URL, get back a tracked short URL. Auto-detects YouTube as `training_video`, review links as `review_request`. Idempotent.
- **`POST /api/s/wrap-bulk`**: Bulk URL wrapping for multiple URLs at once.
- **`POST /api/campaigns/{user_id}/{campaign_id}/rewrap-links`**: Admin endpoint to scan existing campaign steps for raw URLs and wrap them with tracking. Also patches unsent pending sends.
- **Auto-wrap in Campaign Edits**: `PUT /api/campaigns/{user_id}/{campaign_id}` now auto-wraps URLs in `sequences.media_urls` and `sequences.message_template`.
- **Auto-wrap in Training Hub**: Lesson create/update endpoints auto-wrap `video_url` with tracking.
- **Auto-wrap in Scheduler**: Background campaign step processor wraps raw URLs before creating pending sends.
- **Full test coverage**: 20/20 backend tests passed.

### Convert Contact to User Workflow (Mar 26, 2026)
- "Import from Contact" in Add User Modal
- Backend Auto-Linking with tags and linked_* fields
- Linked App Account Card on contact detail page

### Activity Feed Grouping (Mar 27, 2026)
- Consecutive actions by same contact grouped under single photo

### RBAC Fix, UI Fixes, Light Mode, Marketing Decks (Mar 27, 2026)
- Regular users locked out of admin pages
- Jessi bar padding on Templates/Tags/Users pages
- Light mode readability on landing page
- Tags and Lead Sources separated into distinct nav items
- 12 static HTML sales presentation decks

### Scheduler Stability (Mar 27, 2026)
- `safe_job` wrapper prevents APScheduler exceptions from crashing API server
- Campaign hourly delay + AI toggle bugs fixed

---

## Key API Endpoints
- `POST /api/auth/login`
- `POST /api/admin/users/create` — Accepts `source_contact_id`
- `PUT /api/admin/users/{user_id}/reset-password`
- `GET /api/contacts/{user_id}?search=X`
- `GET /api/campaigns/contact/{contact_id}/journey`
- `POST /api/s/wrap` — Universal URL tracking
- `POST /api/s/wrap-bulk` — Bulk URL tracking
- `POST /api/campaigns/{user_id}/{campaign_id}/rewrap-links` — Rewrap campaign links

---

## Prioritized Backlog

### P0
- Deploy and run `rewrap-links` on production "Onboarding Videos" campaign

### P1
- App Store Preparation (eas.json, push notifications)
- AI-Powered Outreach (sold tag follow-ups)
- Gamification & Leaderboards

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
- `/app/backend/scheduler.py` — `_auto_wrap_urls` helper for background jobs
