# i'M On Social — Product Requirements Document

## Original Problem Statement
A full-stack Relationship Management System (RMS) for dealerships. React Native (Expo) frontend, FastAPI backend, MongoDB. The primary goal is stability and reliable event tracking for customer interactions.

## Core Architecture
- **Frontend:** React Native (Expo Router) — Mobile + Web
- **Backend:** FastAPI (Python) on port 8001
- **Database:** MongoDB Atlas
- **Object Storage:** Emergent Object Storage (images/media)

## What's Been Implemented

### Critical Bug Fix: Congrats Card Mislabeling (March 6, 2026)
**Root Cause Identified & Fixed:** ALL card types (Birthday, Holiday, Thank You, Welcome, Anniversary) use the `/congrats/{card_id}` URL prefix. The old `resolve_event_type()` function had a simple pattern match `if '/congrats/' in content: return 'congrats_card_sent'` that caught ALL card types and mislabeled them.

**Multi-Layer Fix Applied:**
1. **Backend `resolve_event_type()`** — Now performs a DB lookup on the `congrats_cards` collection to find the actual `card_type` when a `/congrats/` URL is detected, instead of blindly returning `congrats_card_sent`
2. **Frontend `create-card.tsx`** — Now passes `event_type` parameter when navigating back to contact page or thread after card creation
3. **Frontend `contact/[id].tsx`** — Now reads `event_type` from URL params and sets `composerEventType` state
4. **Backend API title derivation** — Master feed and contact events endpoints always derive titles from `get_event_label(event_type)` using the centralized module, never trusting stored titles
5. **Data migration endpoint** — `POST /api/contacts/admin/fix-event-types` fixes old events in the DB
6. **45 regression tests pass** (38 unit + 7 API tests)

### Previous Implementations
- Centralized event type system (`event_types.py` / `eventTypes.ts`)
- Photo gallery overhaul with EXIF orientation fix
- Personal SMS fallback (carrier-agnostic messaging)
- White-label branded emails via Resend
- Comprehensive activity reporting system
- Public REST API and webhook system
- Soft-delete data retention system
- Automated lifecycle scans via APScheduler

## Key Files
- `/app/backend/utils/event_types.py` — Single source of truth for ALL event types
- `/app/frontend/utils/eventTypes.ts` — Frontend event label mapping
- `/app/backend/routers/contact_events.py` — Activity feed, events, migration endpoint
- `/app/backend/routers/messages.py` — Message sending with channel routing
- `/app/backend/routers/congrats_cards.py` — Card creation (all types)
- `/app/backend/tests/test_event_types.py` — 38 unit regression tests
- `/app/backend/tests/test_event_types_api.py` — 7 API integration tests

## Pending Issues
- P0: User must deploy latest checkpoint to production and run migration endpoint
- P0: Production email delivery (user must verify RESEND_API_KEY in production env)
- P2: React Hydration Error #418
- P2: Mobile app tags data sync
- P2: Leaderboard toggle not fully tested
- P2: Reports endpoint 404 with missing date params

## Upcoming Tasks (Prioritized Backlog)
- P0: Gamification & Leaderboards
- P1: Automated Welcome Emails
- P1: Quoting System
- P1: AI-Powered Outreach
- P1: Password hashing migration (bcrypt)
- P1: Mobile push notifications
- P1: Voice Help Assistant Backend
- P2: Full Twilio Integration (live)
- P2: WhatsApp Integration
- P2: Training Hub content
- P2: Inventory Management Module
- P2: Code cleanup (~80 files)

## Credentials
- Super Admin: `forest@imosapp.com` / `Admin123!`

## 3rd Party Integrations
- Resend (email), MongoDB Atlas, Twilio (MOCKED), OpenAI, Emergent Object Storage, Pillow
