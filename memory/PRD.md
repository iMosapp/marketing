# i'M On Social - Product Requirements Document

## Original Problem Statement
Build a Relationship Management System (RMS) / CRM for automotive sales professionals. AI-powered, human-to-human relationship building where every follow-up is deliberate, meaningful, and personal.

## Core Architecture
- **Frontend:** React Native / Expo (web)
- **Backend:** FastAPI (Python)
- **Database:** MongoDB Atlas
- **Integrations:** Resend (email), Twilio (MOCKED), OpenAI (via emergentintegrations), Emergent Object Storage, Pillow, qrcode

---

## CRITICAL RULES

### Image Pipeline
- ALL images -> `utils/image_storage.py` -> WebP -> `/api/images/`
- NEVER add base64 fallbacks. NEVER serve base64 in responses.

### Role System
- DB may have legacy roles: `admin` (= `org_admin`), `manager` (= `store_manager`)
- Backend `permissions.py` maps both legacy and canonical role names
- Frontend `authStore.ts` normalizes roles via `normalizeUser()` on every user load

### Auth Persistence (iOS PWA)
- 3-layer: AsyncStorage -> IndexedDB -> Cookie (`imonsocial_session`)
- Logout clears BOTH `imonsocial_session` and `imonsocial_uid` cookies

---

## What's Been Implemented

### Campaign Dashboard Fix (Mar 19, 2026)
- **Bug Fix:** `GET /campaigns/{user_id}` was returning 500 because `CampaignSequenceStep.step` was required but some DB records lacked it. Made it default to 0 and auto-assign sequentially on load.
- **Bug Fix:** `GET /campaigns/scheduler/pending` endpoint didn't exist — dashboard pending/upcoming counts were always 0. Created new endpoint.
- **Bug Fix:** `POST /campaigns/scheduler/process` had wrong name (backend had `/trigger`). Added alias endpoint.
- **Bug Fix:** Route ordering — moved static `/scheduler/*` routes before `/{user_id}` to prevent FastAPI matching "scheduler" as a user_id.
- **Testing:** 12/12 backend, 100% frontend pass. Dashboard now shows 2 Active, 11 Upcoming, 22 Completed.

### Contact List Expandable Actions + Name Fix (Mar 22, 2026) -- LATEST
- **Expandable Action Button:** Replaced 3 always-visible call/text/email icons with single paper-plane "reach out" button that fans out on tap, collapsed back with X button
- **Name Wrapping Fix:** `numberOfLines={1}` prevents long names from wrapping to second line
- **Emergency Password Reset:** Added `/api/auth/emergency-reset` endpoint (secret-protected) for production lockout recovery
- **bcrypt Resilience:** Made bcrypt import graceful — falls back to plaintext comparison if bcrypt not installed

### Inbox Swipe Actions, Task Modal & Filters (Mar 22, 2026)
- **Quick Task Modal:** Swiping Task on any inbox item now opens a customizable form (title, type: Call/Text/Email/Meeting/Follow Up, priority: Low/Medium/High, due date quick picks: Today/Tomorrow/3 Days/Next Week, optional note) instead of silently auto-creating a generic task
- **Flagged & Archived Filters:** Added Flagged (orange flag icon) and Archived (archive icon) filter pills to inbox filter bar, so flagged/archived conversations are actually accessible
- **Team Inbox Swipe Actions:** Team inbox items now support swipe gestures — swipe right for Claim (green, unclaimed only) + Task (blue), swipe left for Tag (purple)
- **WebSwipeableItem z-index Fix:** Fixed click interception bug where action buttons weren't clickable after swiping. Content layer now dynamically lowers z-index when swiped open, with overlay to prevent accidental navigation
- **Testing:** 100% frontend pass across all swipe actions, filters, and task modal

### New User Onboarding Multi-Step Flow (Mar 22, 2026)
- **Feature:** 4-step guided onboarding for new salesperson accounts (/auth/complete-profile)
- **Steps:** 1) Change temp password, 2) About You (photo, title, company, hometown, hobbies, tone), 3) Social Links (website, Instagram, Facebook, LinkedIn, Twitter, TikTok, review URL), 4) AI Bio generation + Digital Card preview
- **Pre-fill:** Creator-provided data (title, company, socials) auto-populates form fields
- **AI Bio:** Generates professional bio via GPT-5.2 using Emergent LLM Key
- **Skip/Back:** Users can skip any step or go back; finishing marks `onboarding_complete: true`
- **Backend Fixes:** Added missing allowed fields (company, website, review_url, social_twitter, social_tiktok, tone_preference) to PUT /api/profile endpoint; fixed social field mapping to store under social_links.*; added needs_password_change/company/website/review_url/tone_preference to GET profile response
- **Testing:** 16/16 backend, 100% frontend pass

### Enhanced User Creation + Auto-Contact (Mar 21, 2026)
- **Mandatory fields:** First name, last name, email, phone
- **Optional enrichment:** Title, company, website, Instagram/Facebook/LinkedIn/Twitter URLs — saved to user profile for onboarding pre-fill
- **SMS option:** Toggle to send login info + App Store/Google Play links + temp password via text
- **Auto-contact creation:** New user automatically added as a Contact under the creator with "new-user" tag (triggers onboarding campaigns)
- **Result card:** Shows SMS sent status, contact created badge, tap-to-copy password
- **Testing:** 100% backend (13/13), frontend code review passed

### Jessi AI Chat Widget (Mar 21, 2026)
- **New Feature:** AI-powered chat widget on all 35 marketing site pages (floating blue bubble → expandable chat panel)
- **Backend:** `/api/chat/start`, `/api/chat/message`, `/api/chat/capture` — sessions, AI conversation via Emergent LLM Key (GPT-5.2), auto-extraction of name/email/phone from messages
- **Lead Pipeline:** When visitor shares contact info, automatically creates Contact (tagged `new-lead`, `website-chat`), Conversation (unread, `needs_assistance=True`, `claimed=False`), Message (full chat transcript), and Notification for admin
- **Claimable Leads:** `GET /api/chat/leads` returns unclaimed chat leads for the org; `POST /api/chat/claim/{id}` lets any salesperson claim a lead, reassigning conversation + contact to them (appears in their personal inbox)
- **Team Inbox Integration:** Frontend Team Inbox tab now loads unclaimed Jessi chat leads as "Website Leads" with Jump Ball badge and claim button
- **Proactive Nudge:** After 30 seconds on a marketing page, a subtle "Have questions? I'm here to help!" tooltip slides up from the bubble. Clicking opens chat, X dismisses. Only shows once per session.
- **Close Behavior:** Clicking X closes the widget for the entire browser session (sessionStorage), does not reappear
- **Files:** `/app/backend/routers/chat_widget.py`, `/app/marketing/build/chat-widget.js`, `/app/frontend/app/(tabs)/inbox.tsx` (Team Inbox fetch + claim routing)
- **Testing:** 100% backend (23/23 across 2 iterations), 100% frontend pass

### Demo Leads → Inbox Integration (Mar 21, 2026)
- **New Feature:** Demo form submissions now auto-create a contact (tagged `new-lead`, `demo-request`) + inbox conversation + first message with lead context
- **Lead source tracking:** Every page-specific source (e.g., `dealers_page`, `seo_page`, `pitch_salons`) maps to a human-readable label in the inbox message ("New lead from Automotive", "New lead from SEO & AEO")
- **Bug fix:** Marketing forms were sending `lead_source` but backend only read `source` — now reads both
- **Bug fix:** `business_type` from forms was not being stored — now captured

### CS Login PWA + Marketing Fixes (Mar 21, 2026)
- **PWA Fix:** Rebuilt `/cs/index.html` as complete standalone login page — no SPA redirect, API login directly in static HTML, stores token for SPA pickup
- **Marketing Links:** Fixed `/cs/` → `/cs-login` in 4 calendar-systems marketing links
- **Copy:** Changed all "5-year" to "lifetime" across dealers, calendar-systems, outreach, tiktok pages

### Digital Card Reviews Auto-Approve Fix (Mar 21, 2026)
- **Bug Fix:** Reviews submitted via review pages and landing pages defaulted to `approved: False`, so they never appeared in the card's "What Customers Say" section
- **Fix:** 4+ star reviews now auto-approve on submission (both `public_review.py` and `public_landing.py`). Under 4 stars still require moderation.
- **Data fix:** Retroactively approved existing 4+ star reviews stuck as unapproved

### Email Signature Generator (Mar 21, 2026)
- **New Feature:** Email Signature page at `/email-signature`, accessible from My Brand section in Hub
- **Features:** Pick link destination (Digital Card, Showcase, Link Page, Landing Page), live preview with photo/name/title/phone/email/social links, copy rich HTML or plain text, step-by-step instructions for Gmail, Outlook, iPhone, and Gmail mobile
- **File:** `/app/frontend/app/email-signature.tsx`

### Automotive Page Redesign (Mar 21, 2026)
- **Redesign:** Rebuilt `/dealers/` page from custom one-off design to use shared `pitch.css` industry template
- **Now matches:** powersports, real estate, salons, restaurants, and all other industry pages
- **Sections:** Dark hero, problem, stat bar, before/after flip, value cards, flow timeline, sales team grid, objections, dark closer CTA

### Why i'M On Social Page Fix (Mar 21, 2026)
- **Bug Fix:** Page had no site navigation or footer — was a dead-end for visitors
- **Fix:** Added full marketing site nav (Products/Solutions/Resources/Pricing dropdowns), footer, and demo modal to match all other marketing pages
- **Updated:** All 3 copies synced (frontend/public, marketing/build, marketing/build-preview)

### SEO Share Bug Fix (Mar 21, 2026)
- **Bug Fix:** SEO Health Score share text said "Check out my digital card:" but didn't include the actual card URL
- **Fix:** Appended the user's digital card URL (`/card/{userId}`) to the `shareText` prop in `seo-health.tsx`
- **Impact:** All share channels (SMS, email, link share) now include the full card URL in the message body

### Enhanced Products Dropdown + SEO & Store Reviews Pages (Mar 21, 2026)
- **Products Nav:** Reorganized into 3 sections (Your Digital Presence, Engagement, Visibility & Intelligence) with 11 items including new Store Reviews, Voice Notes, SEO & AEO, Personal Landing Pages (renamed from Link Pages)
- **New Pages:** Created `/seo/` (SEO & AEO feature page with AEO explanation) and `/store-reviews/` (store review hub feature page)
- **Automotive Fix:** Updated nav link from `/salespresentation/` to `/dealers/` across all pages
- **Scope:** Updated 61+ marketing and pitch pages total across all nav changes

### Industry Pitch Pages + Nav Integration (Mar 21, 2026)
- **Feature:** Created 8 industry-specific pitch landing pages with unique messaging tailored to each vertical
- **Industries:** Real Estate, Salons & Spas, Restaurants & Hospitality, Powersports & Recreation, Home Services, Fitness & Personal Training, Insurance & Financial, Medical & Dental
- **Nav Integration:** Updated Solutions > By Industry dropdown across ALL 47+ marketing pages (26 original + 21 hex-color variant) with 10-industry 2-column grid
- **Full Marketing Nav:** Updated all 8 pitch pages to use the full marketing site navigation (Products, Solutions, Resources, Pricing) instead of simplified nav
- **Directory:** Internal directory page at `/pitch/` with all URLs and copy-all button
- **Testing:** 100% pass rate across all pages and nav elements

### Inbox Multi-Channel Composer & Navigation Fix (Mar 21, 2026)
- **Feature:** Integrated `ChannelPicker` into `/app/frontend/app/thread/[id].tsx` so inbox composer shows all org-enabled messaging channels (SMS, WhatsApp, Messenger, Telegram, LinkedIn, Clipboard) instead of just SMS/Email toggle
- **Fix:** Changed `router.push()` to `router.replace()` in `create-card.tsx` (navigateToThread) and `quick-send/[action].tsx` to prevent deep navigation stack buildup (4-swipe-back problem)
- **Testing:** 19/19 backend, 100% frontend pass

### Calendar Systems Landing Page (Mar 20, 2026)
- Rebuilt `/marketing/build/calendar-systems/index.html` with full sales presentation content
- 11 sections covering: core reframe, problem statement, stat comparison, before/after flip, 5 value propositions, how-it-works flow, salesperson benefits, objection handling, white-label features, positioning statement, and closing vision
- Content sourced from user's detailed sales pitch, rewritten conversationally (not word-for-word)

### SEO Health Score Performance Fix (Mar 19, 2026)
- **Bug Fix:** Store query was using `{"store_id": store_id}` instead of `{"_id": ObjectId(store_id)}` — stores were never found
- **Performance:** Added 5-minute TTL in-memory cache (`_score_cache`) to avoid recomputing on every page load
- **Performance:** Replaced `find().to_list()` with MongoDB aggregation pipelines for reviews and short_urls
- **Frontend:** Fixed blank screen on SEO Health page — now shows error state with retry button instead of returning null
- **Feature:** Added "Share My Score" button on SEO Health page + share icon in header — opens UniversalShareModal with score info, digital card link, QR code, and all share channels
- **Testing:** 14/14 backend tests pass, 100% frontend pass

### SEO Health Score Dashboard (Mar 18, 2026)
- Backend: GET /api/seo/health-score/{user_id} — calculates 0-100 score across 5 weighted factors
- Factors: Profile Completeness (20), Review Strength (20), Content Distribution (20), Search Visibility (20), Activity & Freshness (20)
- Backend: GET /api/seo/health-score/team/{store_id} — team leaderboard ranked by score
- Frontend: Dedicated /seo-health page with score circle, factor breakdown, tips, and team tab
- Frontend: SEO Health widget on Home screen

### White-Label Partner Sold Workflow System (Mar 17, 2026)
- Full sold-event pipeline with validation, delivery, and retry
- Idempotency: one active event per contact

### SEO & AEO Phase 1 & 2 (Mar 18, 2026)
- Dynamic sitemap.xml, robots.txt, meta tags, Schema.org JSON-LD
- SEO-friendly salesperson URLs, store directory pages, UTM tracking

### Marketing Page Fixes (Feb-Mar 2026)
- Book a Demo modal, header/logo standardization across 29 pages

### Campaign System Fixes (Mar 18, 2026)
- Scheduler hourly delay fix, AI toggle fix, task catch-up mechanism

### RBAC Security Fix (Mar 18, 2026)
- Partner admin scoping on hierarchy endpoints

---

## Key API Endpoints
- `POST /api/chat/start` — start anonymous chat session
- `POST /api/chat/message` — send visitor message, get Jessi AI response
- `POST /api/chat/capture` — manually capture lead contact info
- `GET /api/chat/leads?user_id=` — unclaimed chat widget leads for org
- `POST /api/chat/claim/{conv_id}?user_id=` — claim a chat lead
- `GET /api/messaging-channels/user/{user_id}` — org-enabled messaging channels
- `GET /api/messaging-channels/available` — all available channel definitions
- `GET /api/seo/health-score/{user_id}` — cached SEO score (5-min TTL)
- `GET /api/seo/health-score/team/{store_id}` — team leaderboard
- `PATCH /api/contacts/{user_id}/{contact_id}/tags` — triggers sold workflow
- `GET /api/tasks/{user_id}/summary` — includes catch-up mechanism
- `GET /api/seo/sitemap.xml` — dynamic sitemap

---

## Prioritized Backlog

### P1
- App Store Preparation (eas.json, app.json store config)
- Gamification & Leaderboards
- AI-Powered Outreach (contextual follow-up on "sold" tag)
- Lead Notification System Phase 2 (push notifications)
- Voice Help Assistant Backend
- Refactor Authentication (bcrypt)

### P2
- Rename `stores` → `accounts` throughout the codebase
- Full Twilio Integration (currently MOCK)
- WhatsApp Integration
- Training Hub video content
- Inventory Management Module
- Refactor large files (admin.py 3700+ lines)

## Known Issues
- P2: Mobile tags sync
- P2: React Hydration Error #418
- P2: Leaderboard toggle not fully tested

## Test Credentials
- Super Admin: `forest@imosapp.com` / `Admin123!`

## 3rd Party Integrations
- **Resend:** Transactional emails
- **MongoDB Atlas:** Primary database
- **Twilio:** MOCK mode
- **OpenAI:** AI features via emergentintegrations
- **apscheduler:** Backend job scheduling (9 jobs)
