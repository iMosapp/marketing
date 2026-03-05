# i'M On Social — Product Requirements Document

## Original Problem Statement
Full-stack Relationship Management System (RMS/CRM) for sales teams. Key goals: ease of use ("easy button"), activity tracking, gamification, AI-powered outreach, and multi-channel communication.

## Core Architecture
- **Frontend:** React Native (Expo) web app
- **Backend:** FastAPI (Python)
- **Database:** MongoDB
- **3rd Party:** Resend (email), Twilio (SMS - MOCKED), OpenAI (AI assistant), Emergent Integrations (object storage)

## What's Been Implemented

### Production URL Fix — All Customer-Facing Links (Mar 2026)
- **Root Cause:** Deployment platform auto-overrides `APP_URL` env var with the staging/deploy domain, causing ALL outgoing links (review requests, share card, short URLs, invite links, NDA links) to point to the wrong domain
- **Backend Fix:** Added `PUBLIC_FACING_URL=https://app.imonsocial.com` env var that takes priority over `APP_URL`. Updated all routers: `short_urls.py`, `auth.py`, `team_invite.py`, `app_directory.py`, `nda.py`
- **Frontend Fix:** Eliminated ALL `window.location.origin` usage for customer-facing URLs across 13+ files. All now use `process.env.EXPO_PUBLIC_APP_URL || 'https://app.imonsocial.com'`
- **Files fixed:** home.tsx, more.tsx, create-card.tsx, p/[userId].tsx, l/[username].tsx, brand-assets.tsx, app-directory.tsx, pricing.tsx, partner agreements, nda, contact/[id].tsx

### Inbox Refresh Fix (Mar 2026)
- Added `useFocusEffect` to inbox.tsx for reliable conversation loading

### Photo URL Fix in SMS Composer (Mar 2026)
- Converts relative image paths to absolute production URLs

### Previous Session Work
- Persistent Login (HTTP-only cookies)
- Dynamic Share Previews (OG tags)
- Training Hub V2 (role-based, admin CRUD)
- Contact Page Bug Fixes
- Home Screen & Action Items Fix
- Carrier-agnostic messaging, white-label emails
- Reporting & Activity (14+ metrics)
- Admin Onboarding Wizard, Partner Portal

## Pending Issues
- P0: Production email delivery — BLOCKED on user verifying `RESEND_API_KEY`
- P2: React Hydration Error #418
- P2: Mobile app `tags` data sync

## Upcoming Tasks
1. (P0) Gamification & Leaderboards
2. (P1) Automated Welcome Emails
3. (P1) Quoting System
4. (P1) AI-Powered Outreach

## Future/Backlog
- Auth refactor (bcrypt), Push notifications, Voice Help Assistant
- Full Twilio integration (MOCKED), WhatsApp Integration
- Inventory Management, Code cleanup (~80 files)

## Key Credentials
- Super Admin: forest@imosapp.com / Admin123!

## Deployment Checklist
- Ensure `PUBLIC_FACING_URL=https://app.imonsocial.com` in backend env
- Ensure `EXPO_PUBLIC_APP_URL=https://app.imonsocial.com` in frontend env
- Verify `RESEND_API_KEY` is set in production
- Verify `MONGO_URL` points to Atlas
