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

### Brand Kit Theme Support for All Public Pages (Mar 26, 2026) -- LATEST
- **Problem:** User's Brand Kit page_theme (light/dark) setting only worked on the Digital Business Card. Showcase, Landing Page, and Link Page were all hardcoded to dark mode.
- **Fix:** 
  - Backend: Added `brand_kit` with `page_theme` to showcase (`showcase.py`), landing page (`public_landing.py`), and link page (`linkpage.py`) API responses. Uses user → store → org fallback chain.
  - Frontend: Made `showcase/[id].tsx`, `p/[userId].tsx`, and `l/[username].tsx` theme-aware with dynamic color objects computed from `data.brand_kit.page_theme`.
- All public pages now respect the Brand Kit light/dark toggle.

### Bug Fix: Modal header hidden behind Jessi bar (Mar 25, 2026)
- Fixed "Add User" modal in admin/users.tsx where header was obscured by the Jessi floating bar
- Added `paddingTop: JESSI_BAR_HEIGHT` to both modal overlays

### Bug Fix: "First name is required" validation error (Mar 25, 2026)
- Fixed setup-wizard.tsx payload missing `first_name` and `last_name` fields when calling `POST /api/admin/users/create`

### Social Activity Feed Rebuild (Mar 24, 2026)
- Rebuilt Global Activity tab as Instagram/Facebook-style social feed with 4 card types

### SMS Deep Link Fix (Mar 24, 2026)
- Changed `window.open` to `window.location.href` for iOS compatibility

### Review Landing Page Redesign (Mar 24, 2026)
- Rebuilt `/review/[storeSlug].tsx` with clean white background, large logo, platform tiles

### Global React Hydration Fix (Mar 24, 2026)
- Added `mounted` state gate to `_layout.tsx` to prevent #418 SSR errors

### Campaign System Fixes (Mar 24, 2026)
- Scheduler hourly delay + AI toggle override bugs + Campaign Journey Feature

---

## Key API Endpoints
- `POST /api/auth/login`
- `GET /api/showcase/user/{user_id}` — Now includes `brand_kit.page_theme`
- `GET /api/showcase/store/{store_id}` — Now includes `brand_kit.page_theme`
- `GET /api/p/data/{user_id}` — Now includes `brand_kit.page_theme`
- `GET /api/linkpage/public/{username}` — Theme now synced from brand_kit
- `GET /api/campaigns/contact/{contact_id}/journey`
- `POST /api/admin/users/create`

---

## Prioritized Backlog

### P1
- App Store Preparation (eas.json, push notifications)
- Gamification & Leaderboards
- AI-Powered Outreach (sold tag follow-ups)

### P2
- Full Twilio Integration (currently MOCK)
- WhatsApp Integration
- Stripe for partner invoices
- Inventory Management Module
- Mobile tags sync issue
- Refactor large files (admin.py, contact/[id].tsx)

## Test Credentials
- Super Admin: `forest@imosapp.com` / `Admin123!`

## 3rd Party Integrations
- **Resend:** Transactional emails
- **MongoDB Atlas:** Primary database
- **Twilio:** MOCK mode
- **OpenAI:** AI features via emergentintegrations
- **apscheduler:** Backend job scheduling

## Key Files Modified This Session
- `/app/backend/routers/showcase.py` — Added brand_kit to user/store showcase responses
- `/app/backend/routers/public_landing.py` — Added brand_kit to landing page response
- `/app/backend/routers/linkpage.py` — Override theme from brand_kit page_theme
- `/app/frontend/app/showcase/[id].tsx` — Made all colors theme-aware
- `/app/frontend/app/p/[userId].tsx` — Made all colors theme-aware (container, sections, modals, cards)
- `/app/frontend/app/admin/users.tsx` — Fixed modal header behind Jessi bar
- `/app/frontend/app/admin/setup-wizard.tsx` — Fixed missing first_name/last_name in payload
