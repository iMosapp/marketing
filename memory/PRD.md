# iMOs - Product Requirements Document

## Original Problem Statement
Full-stack Relationship Management System (RMS) for dealerships. The app empowers sales teams with digital cards, automated campaigns, AI assistants, review management, and customer relationship tools.

## Core Architecture
- **Frontend:** React Native (Expo) with web support
- **Backend:** FastAPI (Python)
- **Database:** MongoDB Atlas (production), localhost:27017 (preview)
- **Email:** Resend
- **SMS:** Twilio (MOCK mode)
- **AI:** OpenAI (Jessi assistant)

## What's Been Implemented

### Session Feb 27, 2026 (Fork 3)
- **NEW: Facebook-Feed Style Contact Profile Page** (`/contact/[id]`)
  - Hero section with avatar, touchpoint badge, name, phone/email chips
  - Time-in-system counter (days → months → years calculation)
  - Stats bar: Touchpoints, Messages, Campaigns, Referrals
  - Quick action buttons: SMS, Call, Email, Review, Card, Congrats
  - Activity Feed timeline aggregating all contact interactions
  - View-only default mode with Edit button to toggle form fields
  - View Conversation link to message thread
  - Comprehensive edit mode with all existing fields preserved
- **NEW: Contact Events Backend** (`/api/contacts/{user_id}/{contact_id}/events`)
  - Aggregates events from messages, campaigns, congrats cards, broadcasts
  - Custom event logging via POST endpoint
  - Stats endpoint returning touchpoint counts and created_at
  - Invalid ObjectId error handling
- **REBRAND: "i'M On Social" Marketing Page Overhaul**
  - Updated hero: "Meet the New Way to Be On Social"
  - Replaced all "Old School Relationship Building / Modern Tools" messaging
  - New narrative: Social Relationship OS, Reputation Operating System
  - Updated feature icons: Digital Cards, Personal Reviews, Social Links, Reputation
  - New stats: Own / Build / Connect
  - Updated feature sections: Organizations, Individuals, The Experience, Personal Reviews, Campaigns
  - Bottom CTA: "Own Your Relationships. Own Your Reputation."
  - Footer: "Social Relationship OS" tagline
  - Sales presentation slides updated
  - Legacy landing page updated
  - Zero "old school" references remaining across entire frontend

### Session Feb 26, 2026 (Fork 2)
- Podium-style Review Links Landing Page (`/review/[storeSlug]`)
- Account-Level Dealership Card (`/card/store/[storeSlug]`)
- Reviews Marketing Page (`/imos/reviews`)
- Share Review Link on My Account
- Review Approval Flow
- More page & My Account redesign
- Logo upload for accounts and organizations
- Quick Settings row for admins
- Password reset email fix
- Auto-slug generation on login

### Previous Sessions
- Critical production login fix (3-part: dotenv override, relative API paths, cache-buster)
- Fixed 14 crash-inducing useState bugs
- Updated favicon

## Key API Endpoints
- `GET /api/contacts/{user_id}/{contact_id}/events` - Contact activity timeline
- `GET /api/contacts/{user_id}/{contact_id}/stats` - Contact touchpoint stats
- `POST /api/contacts/{user_id}/{contact_id}/events` - Log custom event
- `GET /api/review/page/{store_slug}` - Public review page data
- `POST /api/review/submit/{store_slug}` - Submit feedback (pending)
- `GET /api/card/store/{store_slug}` - Account-level dealership card
- `POST /api/email/send` - Send email via Resend
- `POST /api/auth/forgot-password/request` - Password reset

## Key Files
- `/app/frontend/app/contact/[id].tsx` - Redesigned contact profile page
- `/app/backend/routers/contact_events.py` - Events endpoints
- `/app/backend/routers/contacts.py` - Contact CRUD
- `/app/frontend/services/api.ts` - Frontend API service
- `/app/frontend/app/(tabs)/more.tsx` - Style template

## Critical Production Notes
- `backend/server.py` uses `load_dotenv(override=True)` — NEVER change
- Frontend uses relative `/api` paths for web builds
- MONGO_URL in .env must be production Atlas URL for deployment
- Preview environment uses local MongoDB (localhost:27017)

## Prioritized Backlog
### P0 (Completed)
- ~~Redesign Customer Contact Record Page~~ DONE

### P1
- Refactor auth to use hashed passwords (bcrypt)
- Lead Notification System Phase 2 (push notifications)
- Voice Help Assistant backend
- Gamification leaderboard for salespeople touch points

### P2
- Full Twilio integration (currently MOCK)
- WhatsApp integration
- Code cleanup (~80 files)
- Training Hub content
- White-labeling system
- Inventory Management Module
- React Hydration Error #418
- Mobile app tags sync
- Leaderboard toggle verification
