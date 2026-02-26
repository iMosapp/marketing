# iMOs - Product Requirements Document

## Original Problem Statement
Full-stack Relationship Management System (RMS) for dealerships. The app empowers sales teams with digital cards, automated campaigns, AI assistants, review management, and customer relationship tools.

## Core Architecture
- **Frontend:** React Native (Expo) with web support
- **Backend:** FastAPI (Python)
- **Database:** MongoDB Atlas (production)
- **Email:** Resend
- **SMS:** Twilio (MOCK mode)
- **AI:** OpenAI (Jessi assistant)

## What's Been Implemented

### Session Feb 26, 2026 (Fork 2)
- **NEW: Podium-style Review Links Landing Page** (`/review/[storeSlug]`)
  - Light theme, store branding (logo + name from brand kit)
  - All review platform links (Google, Yelp, Facebook, DealerRater, custom)
  - Click tracking at store and salesperson level
  - Direct feedback form with approval workflow
- **NEW: Account-Level Dealership Card** (`/card/store/[storeSlug]`)
  - Store branding, contact actions (Call, Email, Website, Directions)
  - Team member roster with links to individual cards
  - Approved testimonials section
  - Leave-a-review feedback form (pending approval)
- **NEW: Reviews Marketing Page** (`/imos/reviews`)
  - Full marketing page with hero, 6 features, 4-step how-it-works, CTAs
  - "See Live Example" links to review landing page
- **NEW: Share Review Link** tile on My Account
  - Opens share modal with Copy, Text, Email, Preview options
  - Generates tracking URL with salesperson ID
- **UPDATED: Main Marketing Page** (`/imos`)
  - Added "Reviews" to hero features
  - Added "Reviews & Reputation" section to How It Works
- **UPDATED: App Directory**
  - Added "Public Landing Pages" category (Review Links, Dealership Card, Digital Card, Congrats Card)
  - Added "Reviews & Reputation" page under Marketing & Sales
- **UPDATED: Review Approval Flow**
  - All feedback saves as `approved: false` (pending)
  - Only approved reviews show on public cards
  - Managers/admins see store-level pending reviews
- **FIXED: Digital card SMS/Email buttons** not working on web (popup blocker issue)
- **FIXED: Password reset emails** now sent via Resend
- **FIXED: Removed `/api/debug/db-info`** security exposure
- **UPDATED: More page** - Bell/logout stacked vertically, count badges hidden, card-like profile tile
- **UPDATED: My Account** - Rearranged Quick Actions, moved Voice Training to More > Profile & AI

### Previous Sessions
- Critical production login fix (3-part: dotenv override, relative API paths, cache-buster)
- Fixed 14 crash-inducing useState bugs
- Updated favicon
- Various UI rearrangements

## Key API Endpoints
- `GET /api/review/page/{store_slug}` - Public review page data
- `POST /api/review/track-click/{store_slug}` - Track review link clicks
- `GET /api/review/click-stats/{store_id}` - Click statistics
- `POST /api/review/submit/{store_slug}` - Submit feedback (saves as pending)
- `GET /api/card/store/{store_slug}` - Account-level dealership card
- `GET /api/card/data/{user_id}` - Individual digital card
- `GET /api/p/reviews/pending/{user_id}` - Pending reviews for approval
- `POST /api/p/reviews/approve/{review_id}` - Approve a review
- `POST /api/p/reviews/reject/{review_id}` - Reject a review
- `POST /api/email/send` - Send email via Resend
- `POST /api/auth/forgot-password/request` - Password reset (now sends email)

## DB Schema Notes
- `customer_feedback`: Has `approved` boolean field. Only `approved: true` shows on public pages.
- `review_link_clicks`: Tracks every click with store_id, platform, salesperson_id
- `stores.review_click_counts`: Aggregated click counts per platform

## Critical Production Notes
- `backend/server.py` MUST use `load_dotenv(override=True)` — NEVER change
- Frontend uses relative `/api` paths for web builds
- MONGO_URL in .env must be the production Atlas URL for deployment

## Prioritized Backlog
### P1
- Refactor auth to use hashed passwords (bcrypt)
- Lead Notification System Phase 2 (push notifications)
- Voice Help Assistant backend

### P2
- Full Twilio integration (currently MOCK)
- WhatsApp integration
- Code cleanup (~80 files)
- Training Hub content
- White-labeling system
- Inventory Management Module
- React Hydration Error #418
