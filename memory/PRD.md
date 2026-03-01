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

### UX Overhaul — "Daily Driver" Simplification (Mar 1, 2026)
**Tab Restructure**: 4 tabs (Home, Contacts, Inbox, Menu) replacing 5 tabs.

**Home Tab** — 6 daily action tiles:
1. **Share My Card** → Universal share modal (Share Link, Copy Link, Via Text, Via Email, Save vCard, Show QR)
2. **Review Link** → Universal share modal with review URL
3. **Send a Card** → Template picker (Congrats, Birthday, Anniversary, Thank You, Welcome, Holiday)
4. **My Showroom** → Universal share modal with showroom URL
5. **Quick Dial** → Contact search + numeric keypad, logs calls as activity
6. **Add Contact** → CRM search + phone import + manual entry + inline Call/Text/Email actions

**Universal Share Modal** — Reusable component (`/components/UniversalShareModal.tsx`) matching existing "Share My Contact" UI pattern:
- Optional recipient fields (Name, Phone, Email)
- 6 action buttons: Share Link, Copy Link, Via Text, Via Email, Save vCard, Show QR
- Used by Share My Card, Review Link, and My Showroom tiles

**Personal Landing Page** (`/p/{userId}`) — Enhanced with:
- "View My Showroom" link
- "Save My Contact" (vCard download)
- Existing: Leave a Review, Refer a Friend, Call/Text/Email buttons

**vCard Enhancement**: Now includes 4 URLs — store website, landing page, review link (labeled), showroom (labeled)

**Menu Reorganization**: 8 clean categorized sections — Tools, Campaigns, Reports, Templates & Branding, Contacts & Leads, Profile & AI, Settings, Administration (role-gated)

**Showroom**: Sticky top bar with back button + "Copy Link" button at top

**Login**: Rounded logo corners, all roles land on Home tab

### Cards & Celebrations
- Unified card template picker for 6+ card types
- Congrats/Birthday card creation with preview + sharing
- Digital Business Card

### Reporting & Analytics
- Activity reports with 14+ metrics, date filters, scheduled email delivery
- Leaderboard system

### Branding
- White-label HTML email templates
- Logo transparency preservation
- Light & Dark mode with persistence

### Administration
- Soft-delete user system with data retention
- Public REST API + outgoing webhooks
- Automated lifecycle scans via apscheduler

## Known Issues
- **Production email delivery** — Code works in preview; needs RESEND_API_KEY verification on production
- **Production SMS tally** — Fix in preview, pending deployment
- React Hydration Error #418 (P2)

## Upcoming Tasks
1. (P0) **Card Template System — Backend** — Dynamic templates in DB, CRUD API, per-store
2. (P0) **Onboarding Checklist Tracking**
3. (P1) **Gamification & Leaderboards**
4. (P1) **AI-Powered Outreach** (sold tag → follow-up suggestions)
5. (P1) **Auth refactor** (bcrypt password hashing)
6. (P1) **Clean production database for launch**

## Future/Backlog
- Card style customization, Full Twilio live, WhatsApp, TestFlight iOS, Code cleanup

## Credentials
- Super Admin: `forest@imosapp.com` / `Admin123!`

## Project Health
- **Mocked**: Twilio SMS
- **Broken (Production only)**: Email delivery, SMS tallying
