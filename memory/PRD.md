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

### Production Stability Fix — 502/Timeout Errors (Mar 27, 2026) -- LATEST
Root cause: Every page load fired 5-6 heavy API calls simultaneously, and `_catchup_overdue_campaign_tasks` ran unthrottled on every task_summary call doing 50+ DB queries. Combined with N+1 queries in the activity feed, this created a cascading failure under normal usage.

**Fixes applied:**
- **Throttled catchup task**: `_catchup_overdue_campaign_tasks` now runs max once per user per 5 minutes (was every page load)
- **Cached task_summary**: Response cached for 30s to prevent redundant queries during rapid navigation
- **Bulk activity feed**: Replaced N+1 per-event user/contact lookups with 2 bulk `$in` queries
- **New DB indexes**: Added compound indexes on `campaign_enrollments` (user_id + status + next_send_at) and `campaign_pending_sends` (campaign_id + contact_id + step + status)

### Tracked Media System + Composer Integration (Mar 27, 2026)
- `POST /api/media/upload-tracked`: Upload photo/video, get tracked viewing link
- `GET /api/media/view/{media_id}`: Branded viewing page with open logging
- Frontend "Track Opens" toggle in message composer
- Video attachments enabled (was "Coming Soon")

### Universal URL Tracking System (Mar 27, 2026)
- `POST /api/s/wrap` / `POST /api/s/wrap-bulk`: Universal URL wrapping
- Auto-wrap in: Campaign edits, Training Hub lessons, Message Templates, Scheduler

---

## Key API Endpoints
- `POST /api/media/upload-tracked` — Tracked media upload
- `GET /api/media/view/{media_id}` — Branded viewing page
- `POST /api/s/wrap` / `POST /api/s/wrap-bulk` — URL tracking
- `POST /api/campaigns/{user_id}/{campaign_id}/rewrap-links` — Fix campaign links
- `GET /api/tasks/{user_id}/summary` — Now cached 30s
- `GET /api/activity/{user_id}` — Now uses bulk lookups

---

## Prioritized Backlog

### P0
- Deploy stability fix to production (critical for stopping 502 errors)
- Deploy and run `rewrap-links` on production "Onboarding Videos" campaign

### P1
- Link Analytics Dashboard
- App Store Preparation
- AI-Powered Outreach
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

## Key Files Modified This Session
- `/app/backend/routers/tasks.py` — Throttled catchup, cached summary
- `/app/backend/server.py` — Bulk activity feed, new DB indexes
- `/app/backend/routers/media_tracking.py` — NEW: Tracked media system
- `/app/backend/routers/short_urls.py` — wrap/wrap-bulk endpoints
- `/app/backend/routers/campaigns.py` — rewrap-links + auto-wrap
- `/app/backend/routers/training.py` — Auto-wrap in lessons
- `/app/backend/routers/templates.py` — Auto-wrap in templates
- `/app/backend/scheduler.py` — _auto_wrap_urls helper
- `/app/frontend/app/thread/[id].tsx` — Track Opens toggle, video attachments
