# i'M On Social - Product Requirements Document

## Original Problem Statement
Build a Relationship Management System (RMS) / CRM for automotive sales professionals. AI-powered, human-to-human relationship building where every follow-up is deliberate, meaningful, and personal.

## Core Architecture
- **Frontend:** React Native / Expo (web)
- **Backend:** FastAPI (Python)
- **Database:** MongoDB Atlas
- **Marketing Site:** Static HTML in `/app/marketing/build/` (deployed to Vercel via GitHub)
- **Integrations:** Resend (email), Twilio (MOCKED), OpenAI (via emergentintegrations), Emergent Object Storage, Pillow, qrcode, apscheduler

---

## What's Been Implemented

### Bug Fix: Modal header hidden behind Jessi bar (Mar 25, 2026) -- LATEST
- Fixed "Add User" modal in admin/users.tsx where header (Cancel/Add User/Create) was obscured by the Jessi floating bar
- Added `paddingTop: JESSI_BAR_HEIGHT` to both modal overlays

### Bug Fix: "First name is required" validation error (Mar 25, 2026)
- Fixed setup-wizard.tsx payload missing `first_name` and `last_name` fields when calling `POST /api/admin/users/create`
- The invite-team.tsx was already correct; only setup-wizard was affected

### Social Activity Feed Rebuild (Mar 24, 2026)
- Rebuilt Global Activity tab (`activity.tsx`) as Instagram/Facebook-style social feed
- 4 card types: Photo Moment (big visual), Engagement (compact stripe), Milestone (celebration), Text Event (expandable)
- Updated Contact Detail page feed to use same social card rendering
- Backend `classify_visual()` upgraded: contacts with photos auto-upgrade to `photo_moment`
- Removed broken filter chip pills (React Native Web flexbox bug)

### SMS Deep Link Fix (Mar 24, 2026)
- Changed `window.open(url, '_blank')` to `window.location.href = url` for iOS compatibility

### Review Landing Page Redesign (Mar 24, 2026)
- Rebuilt `/review/[storeSlug].tsx` with clean white background, large logo, platform tiles

### Global React Hydration Fix (Mar 24, 2026)
- Added `mounted` state gate to `_layout.tsx` to prevent #418 SSR errors

### Campaign System Fixes (Mar 24, 2026)
- Campaign Scheduler hourly delay + AI toggle override bugs
- Campaign Journey Feature (new endpoint + component)
- Logout cookie cleanup

### Production Readiness (Mar 23-24, 2026)
- ErrorBoundary, Error Reporting, Alert.alert web fix
- Production MongoDB indexes, vanishing contacts race condition
- Partner Monthly Invoice System with PDF generation
- Training Hub with 8 YouTube videos
- Digital card/showcase OG tags, custom card templates

---

## Key API Endpoints
- `POST /api/auth/login`
- `GET /api/contacts/{user_id}/master-feed` -- Powers global Activity feed
- `GET /api/campaigns/contact/{contact_id}/journey`
- `GET /notification-center/{user_id}/unread-count`
- `POST /api/admin/users/create` -- User creation with invite (requires first_name, last_name)
- `POST /api/demo-requests`

---

## Prioritized Backlog

### P1
- App Store Preparation (eas.json, push notifications)
- Gamification & Leaderboards (social experience)
- AI-Powered Outreach (sold tag follow-ups)
- Onboarding Drip Campaign

### P2
- Full Twilio Integration (currently MOCK)
- WhatsApp Integration
- Stripe for partner invoices
- Inventory Management Module
- Refactor large files (admin.py, contact/[id].tsx)
- Mobile tags sync issue

## Test Credentials
- Super Admin: `forest@imosapp.com` / `Admin123!`

## 3rd Party Integrations
- **Resend:** Transactional emails
- **MongoDB Atlas:** Primary database
- **Twilio:** MOCK mode
- **OpenAI:** AI features via emergentintegrations
- **apscheduler:** Backend job scheduling

## Key Files Modified This Session
- `/app/frontend/app/admin/setup-wizard.tsx` -- Fixed missing first_name/last_name in user creation payload
