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

### Social Activity Feed Rebuild (Mar 24, 2026) -- LATEST
- Rebuilt Global Activity tab (`activity.tsx`) as Instagram/Facebook-style social feed
- 4 card types: Photo Moment (big visual), Engagement (compact stripe), Milestone (celebration), Text Event (expandable)
- Updated Contact Detail page feed to use same social card rendering
- Backend `classify_visual()` upgraded: contacts with photos auto-upgrade to `photo_moment`
- Removed broken filter chip pills (React Native Web flexbox bug)

### Calendar Systems Page Rebuild (Mar 24, 2026)
- Rebuilt `/calendar-systems/` with conversion-optimized white-label partner pitch
- New sections: "Sold Moment" trigger, Manager Adoption, Salesperson Value, CS Partnership data feed

### Automotive Landing Page Rebuild (Mar 24, 2026)
- Rebuilt `/automotive/` with conversion-optimized sales flow
- Hero: "Snap a Photo With Your Customer. We Run the Relationship for a Lifetime."
- Added to Resources nav across all 38 marketing HTML files

### Error & Bug Fixes (Mar 24, 2026)
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
- `GET /api/contacts/{user_id}/master-feed` — Powers global Activity feed (with visual_type classification)
- `GET /api/campaigns/contact/{contact_id}/journey`
- `GET /notification-center/{user_id}/unread-count`
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
- Object storage 500 error for some images (test_photo_new.webp)

## Test Credentials
- Super Admin: `forest@imosapp.com` / `Admin123!`

## 3rd Party Integrations
- **Resend:** Transactional emails
- **MongoDB Atlas:** Primary database
- **Twilio:** MOCK mode
- **OpenAI:** AI features via emergentintegrations
- **apscheduler:** Backend job scheduling

## Key Files Modified This Session
- `/app/frontend/app/(tabs)/activity.tsx` — Rebuilt as social feed
- `/app/frontend/app/contact/[id].tsx` — Feed section updated to social cards
- `/app/backend/routers/contact_events.py` — classify_visual() upgraded
