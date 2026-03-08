# i'M On Social — Product Requirements Document

## Original Problem Statement
Build a Relationship Management System (RMS) / CRM for automotive sales professionals.

## Core Architecture
- **Frontend:** React Native / Expo (web)
- **Backend:** FastAPI (Python)
- **Database:** MongoDB Atlas
- **Integrations:** Resend (email), Twilio (MOCKED), OpenAI (GPT-5.2 via emergentintegrations), Emergent Object Storage, Pillow

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

### AI-Powered Outreach (Mar 2026) — NEW
- **Trigger:** When "Sold" tag is applied to a contact, AI generates 2 personalized follow-up messages
- **AI Engine:** OpenAI GPT-5.2 via emergentintegrations (`EMERGENT_LLM_KEY`)
- **Context Gathering:** Pulls contact info, conversation history, engagement signals, salesperson & dealership details
- **Scheduling:** Tasks scheduled for next morning (9 AM) in user's auto-detected timezone
- **Timezone Detection:** Browser timezone sent on login, stored on user document
- **Frontend:** `/ai-outreach` page with Pending/Accepted/Dismissed tabs, suggestion cards with accept/dismiss actions
- **Navigation:** Accessible from Home page tile and Admin Tools section
- **Key Files:** `services/ai_outreach_service.py`, `routers/ai_outreach.py`, hook in `routers/tags.py`
- **DB Collection:** `ai_outreach` — stores suggestions with status tracking

### Engagement Intelligence System (Mar 2026)
- Real-time "Customer Just Looked At Your Card" notifications
- "Second Look" detection — flags return visits after 30+ minutes
- 5-minute deduplication
- Hot Leads Dashboard (`/admin/hot-leads`) with heat scoring
- Notification integration

### Leaderboard Visibility Toggle Fix (Mar 2026)
- User-level opt-in/out works across all leaderboard tiers

### Card System & Image Fixes (Mar 2026)
- Unified card system, image migration tool
- Card creation 520 fix, digital card text overlap fix, card preview shape fix

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
- Permission Roles/Templates
- Auth refactor (bcrypt)
- Push Notifications
- Voice Help Assistant
- Manager Feature (team-wide engagement dashboard)
- Google Places API Integration

### P2
- Full Twilio, WhatsApp, Training Hub, Inventory Module, Code cleanup
- Delete legacy `birthday_cards.py`

## Known Issues
- P1: Production email blocked (user: verify RESEND_API_KEY)
- P2: React Hydration Error #418, Mobile tags sync

## Test Credentials
- Super Admin: `forest@imosapp.com` / `Admin123!`
