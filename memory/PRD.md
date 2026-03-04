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

### Notification Bell Fix + Deep-Linking (Complete - March 2026)
- **CRITICAL BUG FIX:** `getNotifColor` was referencing `colors.textSecondary` at module scope where `colors` doesn't exist. Any unrecognized notification type crashed the entire app. Fixed with hardcoded hex color `#6E6E73`.
- Added `date_trigger` and `new_demo_request` types to notification icon/color functions
- **Deep-link prefill:** Campaign sends and date trigger notifications now link to `/contact/{id}?prefill={encoded_message}` — clicking an alert opens the contact record with the message pre-populated and ready to send
- **Lead notifications:** Demo request submissions now create `new_lead` notifications for the referring salesperson AND all admins, including full form details (name, email, phone, company, source, UTMs, referrer attribution)
- **Tasks page:** `campaign_send` and `date_trigger` task types navigate to contact detail with prefilled message
- **Contact detail page:** Now accepts `channel` param to auto-switch composer to email vs SMS mode

### Manual Campaign → Task + Notification System (Complete - March 2026)
When a manual campaign step fires (via 15-min scheduler or manual trigger), the system creates:
1. **campaign_pending_sends** record with message content, contact info, channel
2. **Task** on the user's to-do list (`type: campaign_send`, `priority: high`, linked to campaign/contact)
3. **Notification** (bell alert) with `action_required: true` so the user knows to act

When a **date trigger** fires (birthday, anniversary, sold date, holidays):
1. **Task** created (`type: date_trigger`, `priority: high`) with the pre-filled message
2. **Notification** (bell alert) saying "It's [Name]'s [trigger] today!"
3. Message queued for tracking

### Turnkey Default Package (Complete - March 2026)
Full auto-provisioning on new user signup:
- 12 SMS templates, 8 Email templates, 6 Campaigns (multi-step), 6 Date Triggers
- 3 Review Response templates, 5 Social Content starters
- 8 tags + 8 lead sources per store
- CRUD endpoints: `/api/review-templates`, `/api/social-templates`
- Idempotent backfill: `POST /api/admin/seed/backfill-all`

### Card Templates, Contact Privacy, Marketing Site, Lead Tracking
- All previously implemented and working (see CHANGELOG)

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
- Gamification & Leaderboards — activity-based leaderboards for users, managers, customers

### P1
- Onboarding UI Flow — account type, primary goal, Launch Score
- AI-Powered Outreach — AI-suggested follow-ups on `sold` tag
- Enrich VCF File — add link page, review link, showcase URL
- Voice Help Assistant Backend
- Production marketing site logo link infinite spinner (user verification pending)

### P2
- Break down monolithic `contact/[id].tsx` (~4200 lines)
- Full Twilio/Telnyx Integration (currently MOCKED)
- Learning Management System (LMS)
- WhatsApp Integration
- Refactor auth to bcrypt
- Partner/Reseller Portal
- React Hydration Error #418

## Key Files
- `/app/frontend/components/notifications/NotificationBell.tsx` — Notification bell (crash fixed)
- `/app/frontend/app/tasks/index.tsx` — Task list with campaign_send/date_trigger support
- `/app/frontend/app/contact/[id].tsx` — Contact detail with prefill+channel params
- `/app/backend/routers/notifications_center.py` — Notification aggregation with deep-links
- `/app/backend/routers/demo_requests.py` — Lead capture with notification creation
- `/app/backend/scheduler.py` — Campaign + date trigger processors
- `/app/backend/services/seed_defaults.py` — Account provisioning
- `/app/backend/routers/review_templates.py` — Review response templates CRUD
- `/app/backend/routers/social_templates.py` — Social content templates CRUD

## 3rd Party Integrations
- **Resend:** Transactional emails
- **MongoDB Atlas:** Primary database
- **Twilio:** MOCK mode
- **OpenAI:** "Jessi" AI assistant
- **Vercel:** Marketing site deployment
