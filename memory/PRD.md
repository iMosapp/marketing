# i'M On Social — Product Requirements Document

## Original Problem Statement
Full-stack Relationship Management System (RMS) for sales professionals. React frontend + FastAPI backend + MongoDB. Features include digital cards, review pages, automated outreach, unified inbox, AI assistant, leaderboards, and a complete static marketing website.

## Core Architecture
- **Frontend:** React (Create React App) at `/app/frontend/`
- **Backend:** FastAPI at `/app/backend/`
- **Database:** MongoDB Atlas
- **Marketing Site:** Static HTML at `/app/marketing/build/` → deployed to Vercel at `imonsocial.com`
- **App Domain:** `app.imonsocial.com`

## What's Been Implemented

### Lead Claim → Prefill Flow (Complete - March 2026)
- **Claim endpoint:** `POST /api/demo-requests/{id}/claim` creates a contact from the lead, assigns to the claiming user, returns `{ contact_id, prefill_message }`
- **NotificationBell:** Clicking a `new_lead` notification auto-claims the lead and navigates to `/contact/{id}` with a personalized welcome message pre-populated in the composer
- **Idempotent:** Claiming again returns `already_claimed` with the existing contact
- **Notification update:** After claiming, the notification link updates from `/admin/lead-tracking` to `/contact/{contact_id}`
- **Attribution preserved:** Contact inherits UTM data, referral info, source, and gets tagged `['new_client', 'hot_lead']`

### Notification Bell Fix + Deep-Linking (Complete - March 2026)
- **CRITICAL BUG FIX:** `getNotifColor` crashed the site by referencing undefined `colors` at module scope
- Campaign sends + date triggers link to `/contact/{id}?prefill={message}` — ready to send
- Lead notifications include full form details + link to lead tracking
- Added `date_trigger`, `new_demo_request` types to icon/color functions

### Manual Campaign → Task + Notification System (Complete - March 2026)
When manual campaign steps fire: creates `campaign_pending_sends` + `task` (to-do) + `notification` (bell)
When date triggers fire: creates `task` + `notification` with prefilled message

### Turnkey Default Package (Complete - March 2026)
12 SMS + 8 Email + 6 Campaigns + 6 Date Triggers + 3 Review Response + 5 Social Content + 8 tags + 8 lead sources — all auto-provisioned on signup, with idempotent backfill.

### Card Templates, Contact Privacy, Marketing Site, Lead Tracking
All previously implemented and working.

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
- Production logo link spinner (user verification pending)

### P2
- Break down monolithic `contact/[id].tsx` (~4200 lines)
- Full Twilio/Telnyx Integration (MOCKED)
- Learning Management System (LMS)
- WhatsApp Integration
- Refactor auth to bcrypt
- Partner/Reseller Portal
- React Hydration Error #418

## Key Files
- `/app/backend/routers/demo_requests.py` — Lead capture + claim endpoint
- `/app/frontend/components/notifications/NotificationBell.tsx` — Bell with claim flow
- `/app/backend/routers/notifications_center.py` — Notification aggregation with deep-links
- `/app/backend/scheduler.py` — Campaign + date trigger processors
- `/app/backend/services/seed_defaults.py` — Account provisioning
- `/app/frontend/app/tasks/index.tsx` — Task list with campaign_send/date_trigger support
- `/app/frontend/app/contact/[id].tsx` — Contact detail with prefill+channel params

## 3rd Party Integrations
- **Resend:** Transactional emails
- **MongoDB Atlas:** Primary database
- **Twilio:** MOCK mode
- **OpenAI:** "Jessi" AI assistant
- **Vercel:** Marketing site deployment
