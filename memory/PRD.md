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
- **88+ preview pages** under `/imos/` for every app feature
- App Directory with search, preview, copy link, and share functionality
- Onboarding flow with quick-win demos

### Reporting & Analytics
- Activity reports with 14+ metrics and date filters
- Scheduled email delivery of reports
- SMS tally bug fixed (personal SMS counted correctly)

### Branding & Logos
- Custom glossy 3D logo across all assets
- White-label HTML email templates
- Brand Assets download page
- **FIXED: Logo transparency preservation** — image upload now detects and preserves PNG transparency across originals, thumbnails, and avatars

### Administration
- Soft-delete user system with data retention
- Public REST API + outgoing webhooks
- Automated lifecycle scans via apscheduler

## Recent Changes (Feb 28, 2026)
1. **FIXED: App Directory 404s** — All pages in both admin and public App Directories now point to working `/imos/` preview routes. Created 17 new preview pages.
2. **FIXED: Logo black background bug** — Root cause: `image_storage.py` was converting all uploads to JPEG (destroying transparency). Now:
   - Detects PNG alpha channel and preserves it
   - Thumbnails and avatars keep PNG format when source has transparency
   - Added `backgroundColor: 'transparent'` to all logo Image styles across 8 frontend files
   - Affected files: `/card/[userId].tsx`, `/p/[userId].tsx`, `/congrats/[cardId].tsx`, `/birthday/[cardId].tsx`, `/showcase/[id].tsx`, `/join/[code].tsx`, `/card/store/[storeSlug].tsx`, `/review/[storeSlug].tsx`, `/settings/store-profile.tsx`

## Known Issues
- **Production email delivery** — Code works in preview; needs RESEND_API_KEY verification on production
- **Production SMS tally** — Fix deployed to preview, pending production deployment
- React Hydration Error #418 (P2)
- Mobile app tags sync (P2)

## Action Required by User
- **Re-upload your iM On Social logo** as a transparent PNG via Settings > Store Profile on production. The system will now preserve transparency.

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
