# i'M On Social — Product Requirements Document

## Original Problem Statement
Full-stack Relationship Management System (RMS) for sales professionals. React frontend + FastAPI backend + MongoDB.

## Core Architecture
- **Frontend:** React (Create React App) at `/app/frontend/`
- **Backend:** FastAPI at `/app/backend/`
- **Database:** MongoDB Atlas
- **Marketing Site:** Static HTML at `/app/marketing/build/`
- **App Domain:** `app.imonsocial.com`

## What's Been Implemented (This Session - March 2026)

### Quick Add Contact Form
- New contacts show only 4 fields: First Name, Last Name, Phone, Email
- Vehicle, Address, Tags, Important Dates collapsed under "More Details (optional)"
- Editing existing contacts still shows all fields
- Auto-focuses first name field for speed

### Lead Claim → Prefill Flow
- `POST /api/demo-requests/{id}/claim` creates contact from lead data
- Clicking new_lead notification → auto-claims → navigates to contact with welcome message pre-populated
- Idempotent: already-claimed leads return existing contact
- Full attribution preserved (UTMs, referral, source, tags)

### Notification Bell Fix + Deep-Linking
- **CRITICAL BUG FIX:** `getNotifColor` crashed site (undefined `colors` at module scope)
- Campaign sends + date triggers link to `/contact/{id}?prefill={message}`
- Lead notifications include full form details + link to lead tracking
- Added `date_trigger`, `new_demo_request` types

### Manual Campaign → Task + Notification System
- Manual campaign steps create: `campaign_pending_sends` + `task` + `notification`
- Date triggers create: `task` + `notification` with prefilled message

### Turnkey Default Package
- 12 SMS + 8 Email + 6 Campaigns + 6 Date Triggers + 3 Review Response + 5 Social Content
- 8 tags + 8 lead sources per store
- Idempotent backfill with per-user error handling (no more 502 crashes)

### Production Stability Fix
- `backfill-all` endpoint now has per-user error handling — one bad record can never crash the server
- Admin endpoint catches and returns errors as JSON instead of crashing

## Credentials
- **Super Admin:** `forest@imosapp.com` / `Admin123!`

## Post-Deploy Commands
```bash
curl -X POST https://app.imonsocial.com/api/admin/seed/backfill-all
curl -X POST https://app.imonsocial.com/api/congrats/templates/backfill
curl -X POST https://app.imonsocial.com/api/contacts/admin/backfill-ownership
curl -X POST https://app.imonsocial.com/api/auth/ref/backfill
```

## Prioritized Backlog

### P0
- Gamification & Leaderboards

### P1
- Onboarding UI Flow (account type, primary goal, Launch Score)
- AI-Powered Outreach (AI-suggested follow-ups on `sold` tag)
- Enrich VCF File
- Voice Help Assistant Backend

### P2
- Full Twilio/Telnyx Integration (MOCKED)
- Learning Management System (LMS)
- WhatsApp Integration
- Partner/Reseller Portal
- Break down monolithic contact/[id].tsx

## Key Files
- `/app/frontend/app/contact/[id].tsx` — Contact detail + quick add form
- `/app/backend/routers/demo_requests.py` — Lead capture + claim endpoint
- `/app/frontend/components/notifications/NotificationBell.tsx` — Bell with claim flow
- `/app/backend/routers/notifications_center.py` — Notification aggregation
- `/app/backend/scheduler.py` — Campaign + date trigger processors
- `/app/backend/services/seed_defaults.py` — Account provisioning
