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

### Marketing Site Updates (Mar 24, 2026) -- LATEST
- **Automotive Vision Page** (`/automotive/`): Full Apple-style landing page with automotive-specific sales copy. Hero: "Take a photo with your customer. The relationship runs for a lifetime." Sections: Problem, Vision Flow, Search Visibility, Manager Pitch, Salesperson Pitch, Network Effect, CRM vs ROS comparison, CTA.
- **Nav Integration:** Added "Automotive Vision" to Resources dropdown across all 38 marketing HTML pages (desktop + mobile navs).
- **Future Vision Page** (`/future/`): Apple-style landing page for "The Future of Sales / Relationship Operating System" pitch.

### Operations Manual v5.0 Update (Mar 24, 2026)
- Seeded the updated Operations Manual to the database via `POST /api/docs/seed-project-scope`.

### Error Report Fixes (Mar 24, 2026)
- **520 Notification Center Fix:** Rewrote unread-count endpoint to use lightweight `count_documents()`.
- **React #418 Showcase Hardening:** Fixed SSR hydration on `/showcase/` page.

### Campaign System Fixes (Mar 24, 2026)
- **Scheduler Bug Fix:** Fixed hourly delay randomization and AI toggle override bugs.
- **Campaign Journey Feature:** New endpoint + component showing campaign timeline on contact detail page.
- **Template Variables Fix:** Centralized `resolve_template_variables()` for all campaign messages.
- **Campaign Stats:** Added MongoDB aggregation for enrollment data on campaigns list.

### Production Readiness (Mar 23-24, 2026)
- ErrorBoundary, Error Reporting System, Alert.alert web crash fix (36 files)
- Production MongoDB indexes, vanishing contacts race condition fix
- Partner Monthly Invoice System with PDF generation
- Training Hub with 8 YouTube videos, click tracking, video templates
- Digital card/showcase OG tags, custom card templates

---

## Key API Endpoints
- `POST /api/auth/login` — user authentication
- `GET /api/users/{user_id}` — user profile data
- `GET /api/campaigns/contact/{contact_id}/journey` — campaign timeline
- `GET /notification-center/{user_id}/unread-count` — optimized unread count
- `POST /api/errors/report` — frontend crash/error reports
- `POST /api/demo-requests` — marketing site demo form submissions

---

## Prioritized Backlog

### P1
- App Store Preparation (eas.json, push notifications)
- Gamification & Leaderboards (social experience)
- AI-Powered Outreach (sold tag follow-ups)
- Onboarding Drip Campaign
- Wire up email signatures to outgoing sends

### P2
- Full Twilio Integration (currently MOCK)
- WhatsApp Integration
- Stripe for partner invoices
- Inventory Management Module
- Refactor large files (admin.py 3700+ lines)
- Reorganize marketing nav structure (automotive/dealers)

## Known Issues
- P2: Mobile tags sync
- P2: Leaderboard toggle not fully tested

## Test Credentials
- Super Admin: `forest@imosapp.com` / `Admin123!`

## 3rd Party Integrations
- **Resend:** Transactional emails
- **MongoDB Atlas:** Primary database
- **Twilio:** MOCK mode
- **OpenAI:** AI features via emergentintegrations
- **apscheduler:** Backend job scheduling
- **YouTube:** Embedded video playback in Training Hub
