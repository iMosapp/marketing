# i'M On Social — Product Requirements Document

## Original Problem Statement
Full-stack Relationship Management System (RMS/CRM) for sales teams. Key goals: ease of use ("easy button"), activity tracking, gamification, AI-powered outreach, and multi-channel communication. The user envisions a "turnkey" system that minimizes their personal involvement in onboarding and training.

## Core Architecture
- **Frontend:** React Native (Expo) web app
- **Backend:** FastAPI (Python)
- **Database:** MongoDB
- **3rd Party:** Resend (email), Twilio (SMS - MOCKED), OpenAI (AI assistant), Emergent Integrations (object storage)

## What's Been Implemented

### Customer-Facing URL Fix (Mar 2026)
- **Critical Fix:** All outgoing customer-facing links (review requests, share card, showcase, link page, congrats cards) were incorrectly using `window.location.origin`, causing links to point to test/staging domains instead of production
- Added `EXPO_PUBLIC_APP_URL=https://app.imonsocial.com` to frontend env
- Fixed 10+ files: home.tsx, more.tsx, create-card.tsx, p/[userId].tsx, l/[username].tsx, brand-assets.tsx, app-directory.tsx, pricing.tsx, partner agreements
- All links now use `process.env.EXPO_PUBLIC_APP_URL || 'https://app.imonsocial.com'`
- Backend short URL system already uses `APP_URL` correctly

### Inbox Refresh Fix (Mar 2026)
- Added `useFocusEffect` from `expo-router` to inbox.tsx so conversations reload on tab focus
- Pull-to-refresh works correctly

### Photo URL Fix in SMS Composer (Mar 2026)
- Fixed photo attachments sending raw API paths in SMS body
- Now converts to absolute public URLs before inserting into message content

### Persistent Login (Mar 2026)
- HTTP-only cookies (`imos_session`) for indefinite sessions

### Dynamic Share Previews (Mar 2026)
- Short URL redirector serves dynamic OG tags for branded link previews

### Training Hub V2 (Mar 2026)
- Role-based content filtering, White Label Partner track, admin CRUD interface

### Contact Page Bug Fixes (Mar 2026)
- Photo attachments, composer text expansion, auto-refresh removal, call logging, review link tracking, referral count ticker

### Home Screen & Action Items Fix (Mar 2026)
- Notification Bell Modal, action items navigation, quick action contact picker flow

### Communication (carrier-agnostic messaging, white-label emails)
### Reporting & Activity (14+ metrics, scheduled delivery)
### Admin Onboarding Wizard, Partner Portal, First-Login Profile Completion

## Pending Issues
- P0: Production email delivery — BLOCKED on user verifying `RESEND_API_KEY` in production
- P2: React Hydration Error #418
- P2: Mobile app `tags` data sync

## Upcoming Tasks
1. (P0) Gamification & Leaderboards
2. (P1) Automated Welcome Emails after wizard user creation
3. (P1) Link Orgs from Partner Agreement View
4. (P1) Quoting System
5. (P1) AI-Powered Outreach

## Future/Backlog
- Auth refactor (bcrypt), Push notifications, Voice Help Assistant
- Full Twilio integration (currently MOCKED), WhatsApp Integration
- Inventory Management Module, Code cleanup (~80 files)

## Key Credentials
- Super Admin: forest@imosapp.com / Admin123!

## Mocked Services
- Twilio SMS: All SMS functionality is MOCKED

## Deployment Checklist
- Ensure `APP_URL=https://app.imonsocial.com` in backend .env
- Ensure `EXPO_PUBLIC_APP_URL=https://app.imonsocial.com` in frontend .env
- Verify `RESEND_API_KEY` is set in production
- Verify `MONGO_URL` points to Atlas (NOT localhost)
