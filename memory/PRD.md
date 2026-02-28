# Product Requirements Document — iMOs (i'M On Social)

## Original Problem Statement
Full-stack Relationship Management System (RMS) for managing customer relationships, communications, reviews, and team performance in automotive/sales industries.

## Core Architecture
- **Frontend**: React Native (Expo Router) for web + mobile
- **Backend**: FastAPI (Python) with MongoDB
- **3rd Party**: Resend (email), Twilio (SMS - MOCK), OpenAI (AI assistant), Emergent Integrations (object storage)

## What's Been Implemented

### Core CRM
- Contact management with tagging, campaigns, activity tracking
- Inbox with SMS (personal fallback + Twilio MOCK) and email channels
- All outbound communication logged as `contact_events`

### Cards & Celebrations
- Congrats Card creation with preview step + sharing
- Birthday Card creation with preview step + campaign integration
- Card view pages with back navigation

### Marketing & Public Pages
- Full `/imos/` marketing site (home, features, pricing, demo, etc.)
- **88 preview pages** under `/imos/` for every app feature
- App Directory with search, preview, copy link, and share functionality
- Onboarding flow with quick-win demos

### Reporting & Analytics
- Activity reports with 14+ metrics and date filters
- Scheduled email delivery of reports
- SMS tally bug fixed (personal SMS counted correctly)

### Branding
- Custom glossy 3D logo across all assets
- White-label HTML email templates
- Brand Assets download page

### Administration
- Soft-delete user system with data retention
- Public REST API + outgoing webhooks
- Automated lifecycle scans via apscheduler

## Recent Changes (Feb 28, 2026)
- **FIXED: App Directory 404s** — All pages in both admin and public App Directories now point to working `/imos/` preview routes instead of broken template URLs
- Created 17 new preview pages under `/imos/` (birthday-card, showcase, join, nda, help, tasks, notifications, search, contact-detail, voice-training, showcase-manage, store-profile, my-rankings, reports-personal, reports-team, reports-campaigns, reports-messaging)
- Added corresponding page data configs to `_pagedata.ts`
- Both `/admin/app-directory` and `/imos/app-directory` updated with correct paths

## Known Issues
- **Production email delivery** — Code works in preview; needs RESEND_API_KEY verification on production
- **Production SMS tally** — Fix deployed to preview, pending production deployment
- React Hydration Error #418 (P2)
- Mobile app tags sync (P2)

## Upcoming Tasks (Priority Order)
1. (P0) Onboarding Checklist Tracking — save user progress
2. (P1) Gamification & Leaderboards
3. (P1) AI-Powered Outreach (sold tag → AI follow-up suggestions)
4. (P1) Auth refactor (bcrypt password hashing)
5. (P1) Clean production database for launch

## Future/Backlog
- Card style customization (P2)
- Full Twilio live integration (P2)
- WhatsApp Integration (P2)
- TestFlight iOS build (P2)
- Code cleanup (~80 files)

## Credentials
- Super Admin: `forest@imosapp.com` / `Admin123!`

## Project Health
- **Mocked**: Twilio SMS
- **Broken (Production only)**: Email delivery via Resend, SMS tallying (pending deployment)
