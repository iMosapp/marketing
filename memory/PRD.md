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

### Social-Media-Style Contact Experience (Completed Mar 2, 2026)
- **Inline Composer**: Replaced the icon-based sticky action bar on contact detail pages with a full inbox-style composer:
  - SMS/Email mode toggle pills (green/purple) + Call button
  - Text input ("Type your message...")
  - Toolbar with: **+** (Send Something picker), **💬** (Log Reply), **✨** (AI Sparkle), **Send** button
  - Messages sent directly from contact page (auto-creates conversation)
- **"Send Something" Consolidated Picker**: Single + button opens a bottom-sheet modal with all sendable items:
  - My Digital Card (pre-fills card URL in composer)
  - Create a Card (opens 6-template secondary picker: Congrats, Birthday, Anniversary, Thank You, Welcome, Holiday)
  - Review Link (pre-fills review page URL in composer)
  - My Showcase (pre-fills showcase URL)
  - My Link Page (fetches link page URL from API and pre-fills)
  - Photo (open camera/gallery)
- **No more inbox redirects**: All send actions stay on the contact page and pre-fill the composer with the appropriate URL/message
- **Differentiated Toolbar Icons**: Blue + (Send Something), Orange arrow-undo (Log Reply), Purple sparkles (AI) — no longer "three green dots"
- **Personal SMS Flow**: SMS mode opens native messaging app with message pre-filled (sms: protocol); Email mode sends directly via Resend
- **AI Relationship Suggestion**: Sparkle button calls GPT-5.2 via Emergent LLM key to analyze relationship history, recent activity, and upcoming events, and generates a personalized message suggestion. User can Edit or Send Now.
- **Collapsible Date Groups**: Activity events grouped by date (Today, Yesterday, X days ago) with count badges and tap-to-collapse/expand in both:
  - Contact page Relationship Feed
  - Activity tab master feed
- **Backend**: `POST /api/contact-intel/{user_id}/{contact_id}/suggest-message` endpoint for AI-powered message suggestions.

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
- ~~"-1 days ago" for future dates~~ — **FIXED** (Mar 2026): Activity tab and contact detail timestamps now show "Tomorrow"/"Upcoming" for future dates

## Upcoming Tasks
1. (P0) **SMS/MMS Provider Integration** — User researching Telnyx vs Twilio vs Plivo for real two-way SMS/MMS with inbound webhook replies. Decision pending.
2. (P0) **Onboarding/Setup Wizard — Phase 2** — First-login user welcome flow (auto-profile, card preview, quick tour, first action)
3. (P0) **Onboarding/Setup Wizard — Phase 3** — Home checklist widget driving 14-day trial adoption
4. (P1) **Gamification & Leaderboards** — Based on activity tracking data
5. (P1) **AI-Powered Outreach** — sold tag → follow-up suggestions
6. (P1) **Auth refactor** — bcrypt password hashing
7. (P1) **Clean production database for launch**

## Future/Backlog
- **Full LMS (Learning Management System)** — Course builder, video lessons (YouTube embed), modules with "Next" progression, quizzes, completion certificates/badges, admin dashboard for tracking. Supports both internal team training and external customer-facing courses. YouTube (unlisted) recommended for video hosting.
- Custom Card Templates (user-created)
- Full Twilio live integration
- WhatsApp Integration
- TestFlight iOS build
- Code cleanup (~80 files)
- Lead Notification System Phase 2 (push notifications)
- Voice Help Assistant Backend
- Calendly-like Booking System for demos

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
- Fully responsive (desktop, tablet, mobile) — fixed mobile overflow issues
- Scroll animations (fade-up on section entry)
- Target audiences: Car dealers, small businesses, bartenders/hospitality, real estate, sales teams, event professionals

### Sponsored Ad Pages (Mar 2, 2026)
- 4 public standalone ad pages for Facebook/Instagram campaigns, all in `/public/`:
  - `/ad-digital-card.html` — Digital business card feature (voice: Onyx)
  - `/ad-showcase.html` — Customer showcase/social proof (voice: Nova)
  - `/ad-reviews.html` — One-tap review requests (voice: Echo)
  - `/ad-autopilot.html` — Automated campaigns & AI messaging (voice: Shimmer)
- Each ad: phone-frame mockup slideshow, AI voiceover (OpenAI TTS HD), animated captions, branded end card
- All CTAs point to **imonsocial.com**
- Brand: i'M On Social logo + tagline
- Listed in App Directory under "Marketing & Sales" with Preview/Copy Link/Share
- App Directory Preview handler updated: static `.html` files open in browser tab (not React router)

### Admin Setup Wizard — Phase 1 (Mar 2, 2026)
- Multi-step wizard at `/admin/setup-wizard` with 5 steps:
  1. Company Info — Name, industry, phone, address, city, state, website, admin email
  2. Branding — Logo upload, primary color picker (10 presets)
  3. Review Links — Google, Facebook, Yelp URLs
  4. Team Members — Bulk add (name, email, phone, role), creates accounts with temp passwords
  5. Summary & Launch — Review config, display credentials, activate
- Backend: `/api/setup-wizard/*` — progress tracking, bulk-invite, complete

### Client Onboarding Mission Control (Mar 2, 2026)
- Multi-client onboarding tracker at `/admin/client-onboarding`
- **"New Client" button** at top creates a fresh checklist instance
- 6-step inline checklist: Send Quote → Get Agreement Signed → Collect Payment → Configure Account → Add Team Members → Go Live
- Each step has: "What You Need" checklist, direct action links to tools, inline forms, "Save & Mark Complete"
- Reseller-ready: a field rep can sign up a new business in 15-30 minutes without knowing the app
- Backend: `/api/setup-wizard/clients` — full CRUD with `step_data` persistence
- Progress persisted in `onboarding_clients` collection

### In-App Call Screen & Activity Auto-Refresh (Mar 2, 2026)
- New call screen at `/call-screen` — contact avatar, timer, "Tap to call" → native dialer, "End Call & Log"
- Calls logged to both `calls` collection and `contact_events` (activity feed)
- Phone taps on contact detail now route through in-app call screen
- `useFocusEffect` on contact detail page auto-refreshes activity log on return from any action
- Future-proof: same screen works with Twilio VoIP when activated


### Showcase + Activity Feed Enhancement (Mar 2, 2026)
- **Showcase now pairs congrats card photos with customer feedback/reviews**, including feedback photos uploaded by the customer
- New `GET /api/showcase/feedback-photo/{feedbackId}` endpoint serves customer-uploaded feedback images
- **"Customer Feedback" header** with label, date, star rating, review text, and photo all visible per matched entry
- **Activity logging for all customer interactions** — logged to `contact_events` with category `customer_activity`:
  - `congrats_card_viewed` — when a customer opens their congrats card
  - `congrats_card_download` / `congrats_card_share` — when a customer downloads or shares their card
  - `review_submitted` — when a customer submits a review from the landing page or review page
  - `review_link_clicked` — when a customer clicks a review link
- New utility: `/backend/utils/contact_activity.py` — reusable module for finding contacts by phone/name and logging customer-initiated events
- All events appear in the contact's activity feed on the contact detail page

### Relationship Feed + Log Customer Reply (Mar 2, 2026)
- **Contact "Activity Feed" redesigned as "Relationship Feed"** — social-media-style timeline
- **"Log Customer Reply"** — inline composer to paste customer text messages + attach photos. Creates `customer_reply` events with `direction: inbound`
- **INBOUND badge** — green badge on customer reply events to distinguish them from outbound
- **CUSTOMER badge** — yellow badge on customer-initiated activity (card views, downloads, shares, reviews)
- **"Next Actions" (Suggested Actions)** — smart recommendations at top of feed:
  - Birthday reminders (within 7 days)
  - Anniversary reminders (within 7 days)
  - 30/60/90/180/365-day purchase follow-up nudges
  - Re-engagement nudge when 30+ days since last touchpoint
  - Thank-you prompt for unacknowledged customer reviews
  - Each action includes a pre-written suggested message and one-tap action button
- Backend: `POST /api/contacts/{userId}/{contactId}/log-reply`, `GET /api/contacts/{userId}/{contactId}/suggested-actions`


### Contact Page Phase 2: Compact Hero + Sticky Action Bar (Mar 2, 2026)
- **Compact left-aligned hero** — Photo tile (68px) top-left with gold touchpoint badge, name + tags inline on the right
- **Industry-agnostic highlight field** — Shows vehicle, house, product, or any custom info without labeling it
- **Tags inline** — Colored tag pills display right next to the contact name (up to 4 shown + overflow count)
- **Compact stats line** — "X touches · Y msgs · Z campaigns · N referrals" replaces the old stats box grid
- **Phone/email removed from hero** — Cleaner profile, still accessible in edit mode
- **Sticky action bar** — Always-visible bottom bar with SMS, Call, Email, Review, Card, Congrats, Log Reply buttons
- **Next Actions elevated** — Above the feed with pre-written suggested messages and one-tap action buttons
- Old standalone Tags section and Quick Actions grid removed (replaced by hero tags and sticky bar)

### Action Progress Tracker + Master Feed (Mar 2, 2026)
- **Per-contact Action Progress Tracker** — Visual checkmarks below the hero showing which key CRM actions have been completed (Contact Card, Congrats, Review Link, Link Page, Email, Text, Call). Gold progress bar (e.g., "6/7 ACTIONS"). Tapping an uncompleted action triggers that action.
- **Master Relationship Feed (Contacts tab)** — Social-media-style feed aggregating activity across ALL contacts. Newest events on top. Shows contact photo, name, tags, event type, description, relative timestamps. INBOUND badges on customer replies. Includes "Action Items" section for suggested next steps and "Upcoming" section for campaign events.
- **Feed/List View Toggle** — Toggle between social feed view and classic contacts list on the Contacts tab.
- Backend: `GET /api/contacts/{userId}/master-feed` (aggregates events + suggestions), `GET /api/contacts/{userId}/{contactId}/action-progress` (returns completion status for 7 key actions)


### Activity Tab + Gallery Profile Photo + UX Polish (Mar 2, 2026)
- **New "Activity" tab** in bottom navigation (between Contacts and Inbox) — social-media-style master feed across ALL contacts with date grouping (Today, Yesterday, etc.), contact avatars, INBOUND badges, event type icons, and relative timestamps. Includes "Action Items" and "Upcoming" sections at the top.
- **"Set as Profile Photo"** button in the photo gallery modal — tap any gallery photo to make it the contact's display picture
- **"X day relationship"** — Changed hero text from "in system" to "relationship" for a warmer, personal tone
- **Contacts tab cleaned up** — Back to pure contact list (feed view moved to Activity tab)
- Backend: `GET /api/contacts/{userId}/master-feed` powers the Activity tab


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
