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
- Physical address fields on contacts (street, city, state, zip, country)
- Inbox with SMS (personal fallback + Twilio MOCK) and email channels
- All outbound communication logged as `contact_events`
- Contact Intel (AI-powered relationship insights)

### UX Overhaul — "Daily Driver" Simplification (Mar 1, 2026)
**Phase 1 — Tab Restructure & Home Tab:**
- New **Home Tab** as "daily command center" with 6 quick action tiles
- Simplified **4-tab navigation**: Home, Contacts, Inbox, Menu
- Dialer & Team moved to Menu → Tools
- All roles now land on Home tab after login

**Phase 2 — 7 Feature Enhancements (Mar 1, 2026):**
1. **Login Logo** — Rounded corners matching app icon style
2. **Share My Card** — Action sheet: "Share Landing Page" (copies /p/{userId} URL) + "Save to Contacts vCard" (downloads .vcf with landing page, review, showroom links)
3. **Review Link** — Robust clipboard copy with fallback (fixed "failed to execute" errors)
4. **Send a Card** — Template picker: Congrats, Birthday, Anniversary, Thank You, Welcome, Holiday cards
5. **Showroom** — Sticky top bar with back button + "Copy Link" at top (no scrolling)
6. **Add Contact** — Unified modal: Import from Phone / Search CRM contacts / Enter Manually + action buttons (Call, Text, Email)
7. **Quick Dial** — Two modes: Contacts search + Numeric keypad. Both log activity

**Menu Reorganization:**
- 8 clean categorized sections: Tools, Campaigns, Reports, Templates & Branding, Contacts & Leads, Profile & AI, Settings, Administration (role-gated)
- Removed duplicate quick action rows (now on Home tab)

### vCard Enhancement
- vCard now includes 4 URLs: store website, landing page, review link, showroom
- Uses Apple vCard labels for Review and Showroom links

### Cards & Celebrations
- Congrats Card creation with preview step + sharing
- Birthday Card creation with preview step + campaign integration
- Unified card template picker for all card types
- Digital Business Card (shareable profile page)

### Marketing & Public Pages
- Full `/imos/` marketing site
- 88+ preview pages under `/imos/`
- App Directory
- Onboarding flow

### Reporting & Analytics
- Activity reports with 14+ metrics and date filters
- Scheduled email delivery of reports
- Leaderboard system

### Branding & Logos
- Custom glossy 3D logo, white-label HTML email templates
- Logo transparency preservation in upload pipeline
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
1. (P0) **Card Template System — Backend** — Store custom templates in DB, CRUD API, per-store templates
2. (P0) **Onboarding Checklist Tracking** — Save user progress
3. (P1) **Gamification & Leaderboards**
4. (P1) **AI-Powered Outreach** (sold tag → AI follow-up suggestions)
5. (P1) **Auth refactor** (bcrypt password hashing)
6. (P1) **Clean production database for launch**

## Future/Backlog
- Card style customization (P2)
- Full Twilio live integration (P2)
- WhatsApp Integration (P2)
- TestFlight iOS build (P2)
- Code cleanup (~80 files, 3 files over 1700+ lines)

## Credentials
- Super Admin: `forest@imosapp.com` / `Admin123!`

## Project Health
- **Mocked**: Twilio SMS
- **Broken (Production only)**: Email delivery via Resend, SMS tallying (pending deployment)
