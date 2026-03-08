# i'M On Social — Product Requirements Document

## Original Problem Statement
Build a Relationship Management System (RMS) / CRM for automotive sales professionals.

## Core Architecture
- **Frontend:** React Native / Expo (web)
- **Backend:** FastAPI (Python)
- **Database:** MongoDB Atlas
- **Integrations:** Resend (email), Twilio (MOCKED), OpenAI, Emergent Object Storage, Pillow

---

## CRITICAL: Image Pipeline Rules — DO NOT REVERT
- ALL images use `utils/image_storage.py` + `utils/image_urls.py` resolvers
- WebP format, served via `/api/images/` with immutable caching
- All uploads use `asyncio.to_thread()` to prevent 520 timeouts
- Migration: `/api/images/migrate-now` (1 image/call, marks oversized as skipped)

## CRITICAL: Unified Card System — DO NOT REVERT
- ALL card types use `congrats_cards.py` only
- `birthday_cards.py` is LEGACY — NOT registered in server.py
- `auto_create_card()` for all auto-creation triggers

---

## What's Been Implemented

### Engagement Intelligence System (Mar 2026) — NEW
- **Real-time "Customer Just Looked At Your Card" notifications**
- Records signals when customers: view cards, download cards, share cards, click links, save contacts, view digital cards, view showcases, click review links
- **"Second Look" detection** — flags return visits after 30+ minutes
- **5-minute deduplication** — same person, same action, same session = 1 signal
- **Hot Leads Dashboard** (`/admin/hot-leads`) with:
  - Heat scoring (signals x return visits x variety)
  - Hot Leads tab (contacts sorted by engagement)
  - Activity Feed tab (raw signal timeline)
  - Time filters: Today / 48 Hours / 7 Days
  - Quick text action (opens SMS)
  - Auto-refresh every 30 seconds
- **Notification integration** — engagement signals appear in notification center
- **Hooked into:** congrats_cards (view/download/share), short_urls (all link clicks), digital_card (contact saves)

### Leaderboard Visibility Toggle Fix (Mar 2026)
- User-level opt-in/out works across all leaderboard tiers
- Re-ranking after filtering, optimized photo URLs

### Card System & Image Fixes (Mar 2026)
- Unified card system, image migration tool
- Card creation 520 fix (asyncio.to_thread)
- Digital card text overlap fix, card preview shape fix

### Image Performance Overhaul (Feb 2026)
- All public pages optimized, batch migration, lazy migration

### Other Completed Features
- Operations Manual v3.0 & PDF Export
- Client Onboarding, Carrier-Agnostic Messaging
- Reporting System, White-Label Emails
- Public REST API & Webhooks
- Gamification & Leaderboards (scoring, levels, badges, streaks)

## Prioritized Backlog

### P1
- AI-Powered Outreach (auto-suggest on `sold` tag)
- Permission Roles/Templates
- Auth refactor (bcrypt)
- Push Notifications
- Voice Help Assistant
- Manager Feature (team-wide engagement dashboard)

### P2
- Full Twilio, WhatsApp, Training Hub, Inventory Module, Code cleanup

## Known Issues
- P1: Production email blocked (user: verify RESEND_API_KEY)
- P2: React Hydration Error #418, Mobile tags sync

## Test Credentials
- Super Admin: `forest@imosapp.com` / `Admin123!`
