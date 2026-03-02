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
1. **Share My Card** → Universal share modal (with contact search)
2. **Review Link** → Universal share modal with review URL
3. **Send a Card** → Template picker → unified create-card page
4. **My Showcase** → Universal share modal with showcase URL
5. **Quick Dial** → Full-size keypad (88×60px buttons) + contact matching as you dial
6. **Add Contact** → Search-first flow: search existing → go to contact page OR no match → New Contact / Upload .vcf

**Universal Share Modal** — Reusable component (`/components/UniversalShareModal.tsx`):
- Via Text/Email now route through internal inbox (/thread/[id]) for tracking
- Uses URL string format (URLSearchParams) for reliable cross-stack navigation on web
- **Contact auto-fill**: Typing 2+ chars in recipient name triggers debounced contact search; dropdown shows matches, tapping auto-fills name/phone/email

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
- Light & Dark mode with persistence — **all pages now theme-aware** (My Account, Contact Detail, Share Modal)
### Linktree-Style Public Link Page (Completed Mar 2, 2026)
- Public URL per user: `/l/{username}` (e.g., `/l/forestward`)
- **Social Links**: All 6 major platforms (Facebook, Instagram, LinkedIn, Twitter/X, TikTok, YouTube) pre-populated by default. Users only enter their username — the URL prefix is built automatically (matching My Profile pattern).
- **Auto-Sync from Profile**: If the link page has all-empty social usernames and the user has social links in their My Profile, the link page auto-populates from the profile on load. Users can then customize independently.
- **Data Model**: `social_links` stored as `{platform: {username, visible}}` dict. Backend builds full URLs for public display.
- Contact links (Call Me, Email Me, Digital Card, Review) with visibility toggles
- Custom links section for arbitrary URLs
- Dark/Light theme support with accent color customization
- Click tracking analytics per link
- "powered by i'MOnsocial" branded footer
- Management UI at `/settings/link-page.tsx`
- Backend: `/backend/routers/linkpage.py` (auto-creates on first access, username uniqueness)

### PWA & Installation
- Full Progressive Web App with service worker, manifest.json, and proper icons
- Smart install page at `/install.html` with device detection (iPhone/Android/Desktop), step-by-step instructions, and QR code
- Apple Touch Icon, Android Chrome icons, all favicon sizes generated from new logo
- **PWA Black Background Fix** (Mar 2, 2026): html/body elements set to `backgroundColor: #000000` with `env(safe-area-inset-bottom)` CSS to eliminate white bar at bottom on iOS standalone mode
- **Send a Card flow** now searches existing contacts before creating a card; contact info is pre-filled on the card creation page
- **Contact search** — All modals (Share My Card, Send Card, Showcase, Add Contact) use strict first_name/last_name matching only, not conversations
- **Campaign card preview** — "Preview Card" button shows a styled preview modal with card header, message, contact placeholder, and footer

### Administration
- Soft-delete user system with data retention
- Public REST API + outgoing webhooks
- Automated lifecycle scans via apscheduler

## Known Issues
- **Production email delivery** — Code works in preview; needs RESEND_API_KEY verification on production
- **Production SMS tally** — Fix in preview, pending deployment
- React Hydration Error #418 (P2)
- Phone matching edge case with heavily formatted numbers (LOW)
- ~~Thread header contact name navigation regression~~ — **FIXED** (Feb 2026)
- ~~Intel refresh scroll-to-top~~ — **FIXED** (Feb 2026)

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

### Menu Page & My Account Redesign (Mar 2, 2026)
- **Quick Actions on My Account**: 6 customizable icon tiles on My Account page. Default: Account Setup, Brand Kit, Review Links, Brand Assets, Approvals, Edit Card. Tap "Edit" to see all 18 actions, tap to add/remove (max 6). Numbered badges show order. Stored in AsyncStorage.
- **Menu page cleaned up**: Profile card, Appearance toggle, and collapsible dropdown sections only (Administration, Tools, Campaigns, Reports, Templates & Branding, Contacts & Leads, Settings). No Quick Actions, no Profile & AI.
- **Profile & AI on My Account**: My Digital Card, My Link Page, AI Persona, Voice Training moved from Menu to dedicated section on My Account page.
- **Showcase mobile fix**: Quick links bar uses flexWrap with chip-style buttons — no more horizontal overflow on mobile

### Marketing Landing Page (Mar 2, 2026)
- Public landing page at `/landing.html` — high-converting marketing page inspired by healthbusiness.ai
- Sections: Hero, How It Works (3 steps), Platform Features (6 cards), Stats bar, Who We Help (6 industries), 4-Step Process, Testimonials (3 placeholder), FAQ (5 items), Final CTA, Footer
- **Demo Booking System**: Modal form captures name, email, phone, business type, company. Saves to `demo_requests` collection with `lead_source: "landing_page"` for tracking. Backend at `POST /api/demo-requests`.
- Dark theme with gold (#C9A962) accent, Playfair Display + Inter fonts
- Fully responsive (desktop, tablet, mobile)
- Scroll animations (fade-up on section entry)
- Target audiences: Car dealers, small businesses, bartenders/hospitality, real estate, sales teams, event professionals

## Key Files
- `/app/frontend/app/settings/create-card.tsx` — Unified card creation with share flow
- `/app/frontend/components/UniversalShareModal.tsx` — Central share component
- `/app/frontend/app/(tabs)/home.tsx` — Home screen with action tiles
- `/app/backend/routers/contact_events.py` — Contact matching + event logging
- `/app/backend/routers/congrats_cards.py` — Card template system
- `/app/frontend/app/settings/showcase-approvals.tsx` — Showcase moderation
- `/app/frontend/app/l/[username].tsx` — Public Linktree-style page
- `/app/backend/routers/linkpage.py` — Link page API (CRUD + public + analytics)
- `/app/frontend/app/+html.tsx` — PWA HTML template (black background, safe area)
