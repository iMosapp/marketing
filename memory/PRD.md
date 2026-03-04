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

### Marketing Website (Complete - March 2026)
- 58 files in `/app/marketing/build/` (homepage, 20+ feature pages, pricing, demo, privacy, terms, install, ad pages, all assets)
- All assets verified — zero broken references
- 72px logo standardized across all 22 HTML pages
- Logo home link fixed (href="/" for same-domain navigation)
- Mobile hamburger menu rebuilt with expandable top-level categories (Products, Solutions, Resources, Pricing)
- Live demo request form with source/UTM/ref tracking
- ~80 unique source tags across CTAs
- vercel.json: trailingSlash: true, outputDirectory: build

### App Directory (Complete - March 2026)
- Public marketing directory at `/appdirectory/` mirrors in-app admin directory exactly
- 14 categories, 94 pages total
- Search functionality across all pages
- Lead Attribution added to Analytics & Reporting and Contacts & Leads

### Turnkey Account Provisioning (Complete - March 2026)
- **Card Templates:** 6 types seeded per store (congrats, birthday, anniversary, thank you, welcome, holiday)
- **SMS Templates:** 7 per user (greeting, follow-up, appointment, thank you, review request, referral, sold)
- **Email Templates:** 5 per user (welcome, digital card, review request, follow-up, referral)
- **Campaigns:** 7 per user (New Client Welcome, Sold Follow-Up, 90-Day Check-In, Annual Re-Engage, Birthday, Anniversary, Sold Date Anniversary)
- **Date Triggers:** 6 per user (birthday, anniversary, sold date + Thanksgiving, Christmas, New Year's)
- **Tags:** 8 per store (new_client, sold, hot_lead, cold_lead, referral, VIP, past_client, follow_up)
- **Lead Sources:** 8 per store (Website, Referral, Walk-In, Social Media, Phone, Event, Email, Personal Network)
- Service: `/app/backend/services/seed_defaults.py`
- Hooked into: signup, admin user creation, store creation
- Backfill: `POST /api/admin/seed/backfill-all`

### Contact Privacy Model (Complete - March 2026)
- `ownership_type: "personal"` for manual/CSV/phone contacts → only owner sees
- `ownership_type: "org"` for lead_form/API/DMs/referral contacts → admins can see
- Admin dashboard shows activity stats without exposing personal contact details
- Bulk transfer gives new owner full access
- Backfill: `POST /api/contacts/admin/backfill-ownership`

### Birthday/Card Template Fix (March 2026)
- Fixed fallback template logic — birthday cards no longer use congrats text
- Backend: `is_fallback_template` flag in congrats_cards.py
- Store creation seeds all 6 card types properly
- Backfill: `POST /api/congrats/templates/backfill`

### Lead & Referral Tracking (Complete)
- Backend: `/app/backend/routers/demo_requests.py`
- Frontend: `/app/frontend/app/admin/lead-tracking.tsx`
- Lead Attribution accessible from More → Reports and More → Contacts & Leads
- Referral codes: `/app/frontend/utils/refLink.ts`

### Core App Features (Previous Sessions)
- Carrier-agnostic messaging (personal SMS fallback)
- Centralized action handling through inbox composer
- Activity reporting with scheduled email delivery
- White-label branded HTML emails via Resend
- Soft-delete system for users/contacts
- Public REST API with API-key auth
- Outgoing webhook system
- User lifecycle engine (automated daily via apscheduler)

## Credentials
- **Super Admin:** `forest@imosapp.com` / `Admin123!`

## Post-Deploy Commands (run once after each deploy)
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
- AI-Powered Outreach — AI-suggested follow-ups on `sold` tag
- Enrich VCF File — add link page, review link, showcase URL
- Voice Help Assistant Backend

### P2
- Break down monolithic `contact/[id].tsx` (~4200 lines)
- Full Twilio/Telnyx Integration (currently MOCKED)
- Push notification indicators on Activity tab
- Learning Management System (LMS)
- WhatsApp Integration
- Refactor auth to bcrypt hashed passwords
- Partner/Reseller Portal
- React Hydration Error #418
- Mobile app tags data sync issue

## Key Files
- `/app/marketing/build/` — Marketing site deployment root (58 files)
- `/app/backend/services/seed_defaults.py` — Turnkey account provisioning
- `/app/backend/routers/congrats_cards.py` — Card template logic (fixed fallback)
- `/app/backend/routers/contacts.py` — Contact privacy model
- `/app/backend/routers/demo_requests.py` — Lead tracking API
- `/app/backend/routers/messages.py` — Messaging (email/SMS channel fix)
- `/app/backend/services/email_service.py` — White-label email templates
- `/app/frontend/app/admin/lead-tracking.tsx` — Lead analytics dashboard

## 3rd Party Integrations
- **Resend:** Transactional emails
- **MongoDB Atlas:** Primary database
- **Twilio:** MOCK mode
- **OpenAI:** "Jessi" AI assistant
- **Vercel:** Marketing site deployment
