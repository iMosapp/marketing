# i'M On Social - Product Requirements Document

## Original Problem Statement
Build a Relationship Management System (RMS) / CRM for automotive sales professionals. AI-powered, human-to-human relationship building where every follow-up is deliberate, meaningful, and personal.

## Core Architecture
- **Frontend:** React Native / Expo (web)
- **Backend:** FastAPI (Python)
- **Database:** MongoDB Atlas
- **Marketing Site:** Static HTML in `/app/marketing/build/`
- **Integrations:** Resend (email), Twilio (MOCKED), OpenAI (via emergentintegrations), Emergent Object Storage, Pillow, qrcode, apscheduler

---

## What's Been Implemented

### Tracked Media System + Composer Integration (Mar 27, 2026) -- LATEST
- **`POST /api/media/upload-tracked`**: Upload photo/video, get a tracked short URL. Viewing page auto-pulls salesperson branding.
- **`GET /api/media/view/{media_id}`**: Branded HTML viewing page with OG tags, view logging, deduplication.
- **`GET /api/media/stats/{media_id}`**: View analytics (count, last viewed).
- **Frontend Composer**: "Track Opens" toggle in message composer (thread/[id].tsx). On by default. When media is attached, user can choose tracked link vs raw MMS.
- **Video attachments enabled**: Previously "Coming Soon", now fully functional with tracking.
- **Testing**: 19/19 backend + frontend tests passed (iteration_247).

### Universal URL Tracking System (Mar 27, 2026)
- **`POST /api/s/wrap`**: Universal URL wrapper, idempotent, auto-detects link types.
- **`POST /api/s/wrap-bulk`**: Bulk URL wrapping.
- **`POST /api/campaigns/{user_id}/{campaign_id}/rewrap-links`**: Fix existing campaign links.
- **Auto-wrap everywhere**: Campaign edits, Training Hub lessons, Message Templates, Scheduler.
- **Testing**: 20/20 tests passed (iteration_246).

### Previous Work
- Contact-to-User workflow, Activity Feed grouping, RBAC fix, UI fixes
- Scheduler stability (safe_job wrapper), Campaign hourly delay + AI toggle fixes
- Marketing presentation decks, SEO guide routing

---

## Key API Endpoints
- `POST /api/media/upload-tracked` — Tracked media upload
- `GET /api/media/view/{media_id}` — Branded viewing page
- `GET /api/media/stats/{media_id}` — View analytics
- `POST /api/s/wrap` / `POST /api/s/wrap-bulk` — URL tracking
- `POST /api/campaigns/{user_id}/{campaign_id}/rewrap-links` — Fix campaign links
- `POST /api/auth/login`, `POST /api/admin/users/create`

---

## Prioritized Backlog

### P0
- Deploy and run `rewrap-links` on production "Onboarding Videos" campaign

### P1
- Link Analytics Dashboard (click-through rates, video watch rates)
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

## Key Files (This Session)
- `/app/backend/routers/media_tracking.py` — NEW: Tracked media upload + viewing page
- `/app/backend/routers/short_urls.py` — Added wrap/wrap-bulk endpoints
- `/app/backend/routers/campaigns.py` — rewrap-links + auto-wrap in update
- `/app/backend/routers/training.py` — Auto-wrap in lesson create/update
- `/app/backend/routers/templates.py` — Auto-wrap in template create/update
- `/app/backend/scheduler.py` — _auto_wrap_urls helper
- `/app/frontend/app/thread/[id].tsx` — Track Opens toggle, video attachments
