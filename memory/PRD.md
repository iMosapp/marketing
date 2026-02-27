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
- **Object Storage:** Emergent Integrations (image uploads)

## What's Been Implemented

### Session Feb 27, 2026 (Fork 4)
- **FIX: MONGO_URL** — Reset from Atlas to localhost:27017 for preview stability
- **UI: More Page Tile Rearrangement**
  - Moved Account Setup, Brand Kit, Review Links tiles into My Account page
  - Replaced with My Digital Card, Congrats Card, Share Review as top 3 tiles on More page
  - Quick action tiles now visible to all users (no role restriction)
- **UI: My Account Quick Actions Cleanup**
  - Removed duplicate tiles (My Digital Card, Create Congrats, Share Review Link)
  - Reorganized: Row 1 = Account Setup, Brand Kit, Review Links; Row 2 = AI Persona, Approvals, Edit Card
- **UX: Accordion behavior on More page** — Only one section open at a time, auto-scrolls clicked section into view
- **UI: Inbox Redesign** — Card-based conversation list, timeline-style thread messages, rich content detection for review/congrats/digital cards
- Verified all 5 main tabs (Inbox, Keypad, Contacts, Team, More) load correctly

### Session Feb 27, 2026 (Fork 3)
- **NEW: Facebook-Feed Style Contact Profile Page** (`/contact/[id]`)
  - Hero section with avatar, touchpoint badge, name, phone/email chips
  - Time-in-system counter, Stats bar, Quick action buttons
  - Activity Feed timeline aggregating all contact interactions
  - View-only default mode with Edit button toggle
- **NEW: Contact Events Backend** (`/api/contacts/{user_id}/{contact_id}/events`)
  - Aggregates events from messages, campaigns, congrats cards, broadcasts
  - Custom event logging, Stats endpoint
- **REBRAND: "i'M On Social" Marketing Page Overhaul**
  - Updated all marketing, sales presentation, onboarding, features pages
  - Zero "old school" references remaining
- **NEW: White Label Partner System**
  - Backend CRUD at `/api/admin/partners`
  - Partner branding cascades: partner > orgs > stores > users
  - Login returns `partner_branding`, tab bar uses partner color
  - Calendar Systems seeded as first partner
- **NEW: Object Storage Image Pipeline**
  - Emergent Object Storage for all image uploads
  - Auto-generates 3 versions: original, thumbnail (200x200), avatar (80x80)
  - Logo uploads store URLs instead of base64 blobs
- **BUGFIX: Admin Dashboard & Review Page Performance**
  - All list endpoints exclude large binary fields

### Session Feb 26, 2026 (Fork 2)
- Podium-style Review Links Landing Page (`/review/[storeSlug]`)
- Account-Level Dealership Card (`/card/store/[storeSlug]`)
- Reviews Marketing Page, Share Review Link, Review Approval Flow
- More page & My Account redesign, Logo upload, Quick Settings
- Password reset email fix, Auto-slug generation

### Previous Sessions
- Critical production login fix (3-part)
- Fixed 14 crash-inducing useState bugs
- Updated favicon

## Key API Endpoints
- `GET /api/contacts/{user_id}/{contact_id}/events` - Contact activity timeline
- `GET /api/contacts/{user_id}/{contact_id}/stats` - Contact touchpoint stats
- `POST /api/contacts/{user_id}/{contact_id}/events` - Log custom event
- `GET /api/review/page/{store_slug}` - Public review page data
- `POST /api/review/submit/{store_slug}` - Submit feedback
- `GET /api/card/store/{store_slug}` - Account-level dealership card
- `POST /api/email/send` - Send email via Resend
- `POST /api/auth/forgot-password/request` - Password reset
- `POST /api/images/upload/base64` - Image upload to object storage
- `GET /api/images/{image_key}` - Serve images from object storage
- `GET /api/admin/partners` - White-label partner CRUD

## Critical Production Notes
- `backend/server.py` uses `load_dotenv(override=True)` — NEVER change
- Frontend uses relative `/api` paths for web builds
- **MONGO_URL in preview .env MUST be mongodb://localhost:27017**
- **NEVER switch .env MONGO_URL to production Atlas in the preview pod**
- **The deployment platform's environment variables handle production**
- If login breaks after a restart, check MONGO_URL in backend/.env FIRST

## Prioritized Backlog
### P0 (Critical)
- Fix production deployment (502 Bad Gateway) — startup blocking issue

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
- Inventory Management Module
- React Hydration Error #418
- Mobile app tags sync
- Leaderboard toggle verification
