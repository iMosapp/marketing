# i'M On Social — Product Requirements Document

## Original Problem Statement
A full-stack Relationship Management System (RMS) for dealerships. React Native (Expo) frontend, FastAPI backend, MongoDB. The primary goal is stability and reliable event tracking for customer interactions.

## Core Architecture
- **Frontend:** React Native (Expo Router) — Mobile + Web
- **Backend:** FastAPI (Python) on port 8001
- **Database:** MongoDB Atlas
- **Object Storage:** Emergent Object Storage (images/media)

## What's Been Implemented

### Bug Fixes & Dialer Redesign (March 6, 2026)
- Fixed Thank You Card mislabeling: key was `thank_you` but create-card.tsx expected `thankyou`
- Fixed black autofill text in dark mode: global CSS now forces white text and dark background on autofilled inputs
- Redesigned dialer to match iPhone: 80px circular buttons with letter labels (ABC, DEF, etc.), matching contacts appear as you type, backspace button next to green call button, phone number auto-formats as (XXX) XXX-XXXX

### Thread & Composer Fixes (March 6, 2026)
- Removed all "new contact" handling from inbox thread (isNewContact, tag picker, contact creation form, photo picker) — contact details should only be managed from the contact page
- Fixed contact page composer to start as true single line (36px) matching inbox behavior — added numberOfLines={1} and content-aware height reset
- Added global CSS `textarea { min-height: 0 }` to prevent browser default from inflating textarea height

### Quick-Send Flow Rebuilt & Polished (March 6, 2026)
- All 4 quick action tiles (Share My Card, Review Link, Send a Card, My Showcase) now use a dedicated quick-send page
- **Visual overhaul:** Form now matches clean Add Contact styling — First/Last name split, card-based grouped inputs with dividers, no blue focus boxes, no yellow backgrounds, no colored borders
- **Global CSS fix:** Injected browser focus outline suppression and autofill background override in `_layout.tsx`
- **Corrected send flow:** SMS opens native phone messaging app (carrier-agnostic), Email sends via Resend backend, Copy Link copies to clipboard. All log events before showing confirmation
- Flow: Enter first/last name + phone/email → duplicate match on phone → preview content with Preview button → choose SMS/Email/Copy Link → send → confirmation → auto-redirect to contact page
- Send a Card has extra card type picker step (Congrats, Birthday, Holiday, Thank You, Anniversary, Welcome)
- New contacts auto-created when phone doesn't match existing
- All activity properly logged with correct event types

### Add Contact Flow Overhaul (March 6, 2026)
- "Add Contact" from home screen now goes **directly to the New Contact form** — no intermediate search modal
- **Duplicate detection** on phone/email: as you type, the app checks for existing contacts and shows a match banner
- **Voice recorder** on the form: record a voice note that gets transcribed and added to the Notes field
- **Activity feed logging**: creating a new contact now appears in the Activity tab as "New Contact Added"
- **Contacts tab auto-refreshes** when gaining focus (useFocusEffect) — no manual refresh needed
- **Referred By picker** is now a full-screen modal with KeyboardAvoidingView — no more keyboard overlap

### Relationship Intel Panel Fix (March 6, 2026)
- Fixed the Relationship Intel dropdown in the inbox thread view
- Previously: either covered the whole screen (couldn't scroll) or compressed to one line (unusable)
- Now: expands to fill space between the intel bar and the text input, hides messages while open, scrollable if content is long
- Collapses back to show messages when tapped again

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
- `/app/frontend/app/quick-send/[action].tsx` — Quick Send flow (all 4 tile types)
- `/app/frontend/app/_layout.tsx` — Root layout with global CSS injection
- `/app/backend/routers/contact_events.py` — Activity feed, events, migration endpoint
- `/app/backend/routers/messages.py` — Message sending with channel routing
- `/app/backend/routers/congrats_cards.py` — Card creation (all types)
- `/app/backend/tests/test_event_types.py` — 38 unit regression tests
- `/app/backend/tests/test_event_types_api.py` — 7 API integration tests
- `/app/backend/tests/test_quick_send_flow.py` — Quick Send backend tests

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
