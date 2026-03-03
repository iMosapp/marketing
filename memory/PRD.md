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

### Marketing Website (Complete)
- 20+ static pages in `/app/marketing/build/` (homepage, features, pricing, demo, privacy, terms, install, ad pages, etc.)
- Live demo request form submitting to backend API
- Lead source tracking (~80 unique source tags on CTAs)
- UTM parameter capture on all forms
- Referral attribution system (ref codes for users/partners/resellers)
- 14-day free trial messaging on all CTAs
- Consistent 72px logo across all pages
- All internal links verified (trailing slashes, correct paths)
- vercel.json configured (`trailingSlash: true`, `outputDirectory: "build"`)
- All 58 files verified with zero broken references

### Lead & Referral Tracking
- Backend: `/app/backend/routers/demo_requests.py` — form submissions, analytics aggregation
- Backend: `/app/backend/routers/auth.py` — ref code generation, backfill endpoint
- Frontend: `/app/frontend/app/admin/lead-tracking.tsx` — admin dashboard with charts/tables
- Frontend: `/app/frontend/utils/refLink.ts` — utility to append ref codes to shared URLs

### Core App Features
- Carrier-agnostic messaging (personal SMS fallback for users without Twilio)
- Centralized action handling through inbox composer
- Activity reporting system with scheduled email delivery
- White-label branded HTML emails via Resend
- Soft-delete system for users/contacts
- Public REST API with API-key auth
- Outgoing webhook system
- User lifecycle engine (automated daily via apscheduler)
- Automated lifecycle scans

### Branding & Theme
- Full rebrand to "i'M On Social"
- Light/blue theme across auth, onboarding, sales presentation pages
- Rounded-square avatar standardization

## Credentials
- **Super Admin:** `forest@imosapp.com` / `Admin123!`

## Post-Deploy Actions
- Run: `curl -X POST https://app.imonsocial.com/api/auth/ref/backfill`

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

## 3rd Party Integrations
- **Resend:** Transactional emails
- **MongoDB Atlas:** Primary database
- **Twilio:** MOCK mode
- **OpenAI:** "Jessi" AI assistant
- **Vercel:** Marketing site deployment

## Key Files
- `/app/marketing/build/` — Marketing site deployment root
- `/app/backend/routers/demo_requests.py` — Lead tracking API
- `/app/backend/routers/messages.py` — Messaging (email/SMS channel fix)
- `/app/backend/services/email_service.py` — White-label email templates
- `/app/backend/routers/reports.py` — Activity reporting
- `/app/frontend/app/admin/lead-tracking.tsx` — Lead analytics dashboard
