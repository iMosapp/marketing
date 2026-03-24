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

### Calendar Systems Page Rebuild (Mar 24, 2026) -- LATEST
- Rebuilt `/calendar-systems/` with conversion-optimized white-label partner pitch
- New sections: "Sold Moment" trigger, Manager Adoption, Salesperson Value, CS Partnership data feed, Hidden SEO Bomb, 2-Minute Demo flow, Strategic Advantage
- Viral hook: "Take a photo with your customer. The relationship runs itself."

### Automotive Landing Page Rebuild (Mar 24, 2026)
- Rebuilt `/automotive/` with conversion-optimized sales flow: Hook > Problem > Magic Moment > SEO > How It Works > Salespeople > Roles > ROI > Proof > Demo > Close
- Hero: "Snap a Photo With Your Customer. We Run the Relationship for a Lifetime."
- Added to Resources nav across all 38 marketing HTML files

### Marketing Site Updates (Mar 24, 2026)
- **Future Vision Page** (`/future/`): Apple-style "The Future of Sales" pitch
- **Nav Integration:** Automotive Vision in Resources dropdown site-wide

### Error & Bug Fixes (Mar 24, 2026)
- 520 Notification Center Fix (lightweight count_documents)
- React #418 Showcase Hydration Fix
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
- `GET /api/campaigns/contact/{contact_id}/journey`
- `GET /notification-center/{user_id}/unread-count`
- `POST /api/demo-requests`
- `POST /api/errors/report`

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
- Refactor large files (admin.py)
- Reorganize marketing nav (automotive/dealers)
- Add real demo videos + social proof to landing pages
- Mobile tags sync issue

## Test Credentials
- Super Admin: `forest@imosapp.com` / `Admin123!`

## 3rd Party Integrations
- **Resend:** Transactional emails
- **MongoDB Atlas:** Primary database
- **Twilio:** MOCK mode
- **OpenAI:** AI features via emergentintegrations
- **apscheduler:** Backend job scheduling
