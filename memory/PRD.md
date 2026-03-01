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
- **Physical address fields** on contacts (street, city, state, zip, country) for gift sending
- Inbox with SMS (personal fallback + Twilio MOCK) and email channels
- All outbound communication logged as `contact_events`
- Contact Intel (AI-powered relationship insights)

### UX Overhaul (Mar 1, 2026)
- **New Home Tab** — "Daily command center" with 6 quick action tiles:
  - Share My Card, Review Link, Create Card, My Showroom, Quick Dial, Add Contact
  - Recent Activity feed below tiles
- **Simplified 4-tab navigation**: Home, Contacts, Inbox, Menu
  - Removed Dialer and Team as standalone tabs (moved to Menu → Tools)
  - Gold (#C9A962) active tab color for brand consistency
- **Reorganized Menu** — 8 clean categorized sections:
  - Tools, Campaigns, Reports, Templates & Branding, Contacts & Leads, Profile & AI, Settings, Administration (role-gated)
- **Quick Dial flow** — Pick contact → log call event → open native dialer
  - Follows same pattern as personal SMS: if no Twilio, hand off to phone but still log activity

### Cards & Celebrations
- Congrats Card creation with preview step + sharing
- Birthday Card creation with preview step + campaign integration
- Digital Business Card (shareable profile page)
- Showcase/Inventory display

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
- Logo transparency preservation in image upload pipeline
- Light & Dark mode with persistence

### Administration
- Soft-delete user system with data retention
- Public REST API + outgoing webhooks
- Automated lifecycle scans via apscheduler

## Known Issues
- **Production email delivery** — Code works in preview; needs RESEND_API_KEY verification on production
- **Production SMS tally** — Fix deployed to preview, pending production deployment
- React Hydration Error #418 (P2)
- Mobile app tags sync (P2)

## Upcoming Tasks (Priority Order)
1. (P0) **Card Template System** — Unified "Create Card" with template picker (Congrats, Birthday, Anniversary, custom). Templates saveable like tags, store-level.
2. (P0) Onboarding Checklist Tracking — save user progress
3. (P1) Gamification & Leaderboards
4. (P1) AI-Powered Outreach (sold tag → AI follow-up suggestions)
5. (P1) Auth refactor (bcrypt password hashing)
6. (P1) Clean production database for launch

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
