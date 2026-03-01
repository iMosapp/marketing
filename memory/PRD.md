# Product Requirements Document — iMOs (i'M On Social)

## Original Problem Statement
Full-stack Relationship Management System (RMS) for managing customer relationships, communications, reviews, and team performance in automotive/sales industries.

## Core Architecture
- **Frontend**: React Native (Expo Router) for web + mobile
- **Backend**: FastAPI (Python) with MongoDB
- **3rd Party**: Resend (email), Twilio (SMS - MOCK), OpenAI (AI assistant), Emergent Integrations (object storage)

## What's Been Implemented

### Core CRM
- Contact management with tagging, campaigns, activity tracking
- Physical address fields on contacts (street, city, state, zip, country)
- Inbox with SMS (personal fallback + Twilio MOCK) and email channels
- All outbound communication logged as `contact_events`
- Smart contact matching (phone last-10-digits, email) with name mismatch confirmation modal

### UX Overhaul — "Daily Driver" Simplification
**Tab Restructure**: 4 tabs (Home, Contacts, Inbox, Menu) replacing 5 tabs.

**Home Tab** — 6 daily action tiles:
1. **Share My Card** → Universal share modal
2. **Review Link** → Universal share modal with review URL
3. **Send a Card** → Template picker (Congrats, Birthday, Anniversary, Thank You, Welcome, Holiday) → navigates to unified create-card page
4. **My Showcase** → Universal share modal with showcase URL
5. **Quick Dial** → Contact search + numeric keypad
6. **Add Contact** → CRM search + phone import + manual entry

**Universal Share Modal** — Reusable component (`/components/UniversalShareModal.tsx`):
- Via Text/Email now route through internal inbox (/thread/[id]) for tracking
- Uses URL string format (URLSearchParams) for reliable cross-stack navigation on web

### Inbox Thread Enhancements
- Contact name in header is clickable → navigates to contact detail page
- **Relationship Intel bar** below SMS/Email mode banner — shows AI analysis of the contact, collapsible with Refresh
- **Auto-return from card creation**: Creating a card FROM inbox auto-returns with card link pre-filled (skips share screen)

**Sharing Flow Architecture** (Fixed Mar 1, 2026):
- All "Via SMS/Email" share actions route through internal inbox thread
- Navigation uses URL string format: `/thread/{contactId}?mode=sms&prefill=...`
- Contact find-or-create API handles deduplication before navigation
- Works across Expo Router stack boundaries (settings → thread)

### Avatar & Photo Quality
- Thumbnails generated at 256×256 @ 85% JPEG (was 96×96 @ 60%) — crisp on 3x Retina
- `resizeMode: 'cover'` on all Image components (Avatar, contacts list, contact detail hero)
- One-time migration endpoint: `POST /api/contacts/admin/regenerate-thumbnails`
- **Photo Gallery**: Tapping contact avatar opens a grid of photo tiles (profile, congrats, birthday)
  - Tap tile → full-screen view with prev/next navigation and "All Photos" grid button
  - Single photo contacts skip grid, go straight to full-screen

### Cards & Celebrations
- Unified card creation page (`/settings/create-card.tsx`) supports 6 card types via `?type=` param
- Card templates manageable by admins (`/settings/card-templates.tsx`)
- Clean, social-media-ready card image generation (1080x1350) via Pillow
- **Card success/share screen matches UniversalShareModal design** — 2×3 grid (Share Link, Copy Link, Via Text, Via Email, Preview, Show QR), pre-filled recipient fields, no raw URL
- Inbox thread "Create Card" option opens 6-type template picker, navigates with contact info pre-filled

### Showcase & Approvals
- User-level and store-level showcase views
- Moderation system for reviews and showcase entries (`/settings/showcase-approvals.tsx`)
- Public showcase pages without auth requirement

### Reporting & Analytics
- Activity reports with 14+ metrics, date filters, scheduled email delivery
- Leaderboard system
- Rich expandable activity feed on contact details

### Branding
- White-label HTML email templates via Resend
- Centralized `PoweredByFooter.tsx` + `brand.ts` config
- Light & Dark mode with persistence

### Administration
- Soft-delete user system with data retention
- Public REST API + outgoing webhooks
- Automated lifecycle scans via apscheduler

## Known Issues
- **Production email delivery** — Code works in preview; needs RESEND_API_KEY verification on production
- **Production SMS tally** — Fix in preview, pending deployment
- React Hydration Error #418 (P2)
- Phone matching edge case with heavily formatted numbers (LOW)

## Upcoming Tasks
1. (P0) **Onboarding/Setup Wizard** — Multi-step setup for new Organizations, Admins, Users
2. (P1) **Gamification & Leaderboards** — Based on activity tracking data
3. (P1) **AI-Powered Outreach** — sold tag → follow-up suggestions
4. (P1) **Auth refactor** — bcrypt password hashing
5. (P1) **Clean production database for launch**

## Future/Backlog
- Custom Card Templates (user-created)
- Full Twilio live integration
- WhatsApp Integration
- TestFlight iOS build
- Code cleanup (~80 files)
- Lead Notification System Phase 2 (push notifications)
- Voice Help Assistant Backend

## Credentials
- Super Admin: `forest@imosapp.com` / `Admin123!`

## Project Health
- **Mocked**: Twilio SMS (personal phone fallback active)
- **Broken (Production only)**: Email delivery, SMS tallying

## Key Files
- `/app/frontend/app/settings/create-card.tsx` — Unified card creation with share flow
- `/app/frontend/components/UniversalShareModal.tsx` — Central share component
- `/app/frontend/app/(tabs)/home.tsx` — Home screen with action tiles
- `/app/backend/routers/contact_events.py` — Contact matching + event logging
- `/app/backend/routers/congrats_cards.py` — Card template system
- `/app/frontend/app/settings/showcase-approvals.tsx` — Showcase moderation
