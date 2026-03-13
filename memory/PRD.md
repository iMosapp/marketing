# i'M On Social — Product Requirements Document

## Original Problem Statement
Build a Relationship Management System (RMS) / CRM for automotive sales professionals. The vision: AI-powered, human-to-human relationship building where every follow-up is deliberate, meaningful, and personal. Salespeople record voice memos, and the system extracts personal details (family, interests, vehicle info) to power AI-generated campaign messages that nurture long-term relationships for repeat and referral business.

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

## CRITICAL: Unified Card System — DO NOT REVERT
- ALL card types use `congrats_cards.py` only
- `birthday_cards.py` is LEGACY — NOT registered in server.py

---

## What's Been Implemented

### Voice Memo Intelligence + Campaign Config + Full AI Pipeline (Mar 2026) — LATEST

1. **Voice Memo Intelligence Extraction** (`services/voice_intel.py`)
   - When a voice note is recorded, AI automatically extracts: spouse name, kids, interests, occupation, vehicle details, trade-in, purchase context, pets, neighborhood, referral potential, communication preference
   - Auto-triggers on voice note save (fire-and-forget async task in `voice_notes.py`)
   - Extracted details merge into contact's `personal_details` field (existing data preserved, new data supplements)
   - Contact event logged for activity feed visibility

2. **Enhanced Contact Profile** (in `contacts.py`)
   - `GET /contacts/{user_id}/{contact_id}/personal-details` — View extracted details
   - `PATCH /contacts/{user_id}/{contact_id}/personal-details` — Manual edits (override AI)
   - `POST /contacts/{user_id}/{contact_id}/re-extract` — Re-run extraction on all voice notes
   - Frontend: `PersonalIntelSection` component on contact detail page shows all personal intel

3. **Campaign Configuration System** (`routers/campaign_config.py`)
   - **Message modes:** `ai_suggested` (AI crafts every message), `template` (hard-coded), `hybrid` (per-step)
   - **AI tone:** casual, warm, professional
   - **Data sources:** Toggle voice memo intel and engagement signals
   - **Delivery:** Review before send, auto-send (disabled until Twilio), auto-enroll on tag
   - **Hierarchy:** Org baseline → Store (primary) → User override (with permission)
   - Frontend: `/campaign-config` settings page with radio options, switches, level selector

4. **Relationship Intelligence Engine** (upgraded `services/relationship_intel.py`)
   - Now includes personal details from voice memos in both AI context and human summary
   - AI prompt includes: spouse name, kids, interests, vehicle details, referral potential
   - Human summary shows: "Personal: Spouse: Sarah / Kids: Jake, Emma / Interests: fly fishing"

5. **Campaign Message Generation** (upgraded)
   - Scheduler checks campaign config for message_mode before generating
   - `ai_suggested` mode overrides to always use AI, `template` mode forces templates
   - AI messages reference personal details for deeply personalized touchpoints

### AI-Powered Outreach + Sold Campaign Intelligence (Mar 2026)
- "Sold" tag triggers: AI suggestions (2 options) + auto campaign enrollment
- Relationship intelligence feeds into every campaign message
- Timezone-aware scheduling (9 AM next morning)
- Frontend `/ai-outreach` with 4 tabs: Campaign, AI Suggestions, Accepted, Dismissed

### Card Analytics Dashboard (Mar 8, 2026)
- **NEW:** Comprehensive card analytics page at `/analytics/cards` accessible from the main Analytics dashboard
- **Summary KPIs:** Total cards created, views, downloads, shares with trend percentages vs previous period
- **Card Type Breakdown:** Bar chart visualization of all 6 card types (Congrats, Birthday, Anniversary, Thank You, Welcome, Holiday) with per-type views/downloads/shares
- **Daily Trend Chart:** Bar chart showing daily card creation activity over selected period
- **Top Performing Cards:** Ranked table sorted by engagement score (views + downloads×2 + shares×3)
- **Team Performance (Managers):** Per-salesperson breakdown with card counts, engagement scores, and vs-average comparison badges
- **Personal Card Mix (Salespeople):** Percentage breakdown of card types used
- **Date Filtering:** 7D, 14D, 30D, 90D, 1Y period selectors
- **Role-Aware:** Super admins see org-wide, store managers see store-wide, salespeople see personal
- **Backend:** `GET /api/reports/card-analytics/{user_id}` — MongoDB aggregation pipeline
- **Tested:** 16/16 backend tests passed, all frontend sections verified

### Card Labeling Bug Fix (Mar 8, 2026)
- **BUG FIXED:** All card types (Birthday, Holiday, Thank You, etc.) sent from the inbox were incorrectly labeled as "Congrats Card"
- **Root cause:** Hardcoded labels, faulty `.includes('congrats')` detection, and no mechanism to pass card type during creation
- **Fix:** Added card type selector (6 types: Congrats, Birthday, Anniversary, Thank You, Welcome, Holiday) to creation modal, passes `card_type` to backend, message rendering now uses `event_type` field for dynamic label/icon/color
- **Backend:** `POST /api/congrats/create` now accepts `card_type` parameter; messages store explicit `event_type` (e.g., `birthday_card_sent`)
- **Frontend:** Dynamic modal title, preview text, and thread message rendering based on card type
- **Tested:** 9/9 backend tests passed, all frontend flows verified

### Contact Stats Bar Bug Fix (Mar 8, 2026)
- **BUG FIXED:** Campaigns and Referrals counters on the contact card stats bar were always showing 0
- **Root cause 1 (Campaigns):** Two enrollment systems exist — `campaigns.py` stores `user_id`, `campaign_lifecycle.py` stores `salesman_id`. The stats query only filtered by `user_id`, missing lifecycle enrollments.
- **Root cause 2 (Referrals):** Stats displayed `contact.referral_count` (a manually-maintained counter) instead of dynamically counting contacts with `referred_by` matching the contact.
- **Fix:** Stats endpoint (`/api/contacts/{user_id}/{contact_id}/stats`) now queries campaign_enrollments by `contact_id` only (catches both field naming conventions), and dynamically counts referrals from the contacts collection.
- **Frontend:** Updated ContactStats interface and display to use `stats.referral_count` from API.
- **Tested:** 6/6 backend + frontend tests passed

### Digital Card Labeling Bug Fix (Mar 8, 2026)
- **BUG FIXED:** Digital business card messages with historical `congrats_card_sent` event_type were incorrectly labeled as "Congrats Card"
- **Root cause:** 3 issues: (1) `contentLower` referenced before definition, (2) `isDigitalCard=true` did not prevent congrats fallback, (3) display priority checked congrats before digital card
- **Fix in** `/app/frontend/app/thread/[id].tsx`: (1) Moved `contentLower` before `isDigitalCard`, (2) Added `!isDigitalCard` guards to prevent congrats label on digital card content, (3) Swapped display priority: `isDigitalCard` now checked BEFORE `isCongratsCard`
- **Enhanced detection:** Now catches `/card/`, `/p/`, "digital card", "digital business card", "save my contact", and both `digital_card_sent` and `digital_card_shared` event_types
- **Tested:** 8/8 backend tests passed, all 7 card label scenarios verified via frontend

### Permission Templates + Template Delete Bug Fix + Touchpoint Totals Fix (Mar 8, 2026)
1. **Permission Templates System** (`routers/permission_templates.py`)
   - Full CRUD API: Create, Read, Update, Delete custom permission templates
   - 4 prebuilt templates: Sales Rep, Senior Rep, Sales Manager, Org Admin
   - Apply template to user: sets role + feature permissions in one click
   - Frontend: `/permission-templates` management page with create/edit modal, permission toggles, apply-to-user flow
   - Navigation: Added to admin Tools section
2. **Template Delete Bug Fix** (SMS + Email templates)
   - Fixed: `Alert.alert` on web degrades to `window.alert` without callback buttons
   - Now uses `window.confirm()` on web platform for delete confirmations
3. **Cleanup:** Deleted obsolete `birthday_cards.py` router file
4. **Touchpoint Totals Bug Fix** (`routers/tasks.py` summary endpoint)
   - Fixed: SMS sent, emails sent, calls placed, cards shared, and reviews sent were NOT counted in `total_today` / `completed_today`
   - Root cause: Summary only counted items from `tasks` collection, not `contact_events` activity
   - Fix: Activity touchpoints (SMS, email, calls, cards, reviews) now add to both `total_today` and `completed_today`
5. **Template Audit Log** (`permission_audit_log` collection)
   - Tracks all permission template actions: created, edited, deleted, applied
   - Logs actor name, template name, target user (for applies), role changes, changed fields (for edits)
   - `GET /api/permission-templates/audit-log` endpoint returns recent entries
   - Frontend: "Activity Log" button on Permission Templates page opens a modal with timestamped entries
6. **Manager Team Engagement Intelligence** (NEW)
   - `GET /api/engagement/team-hot-leads/{manager_id}` — aggregates hot leads across all team members in the manager's store/org
   - `POST /api/engagement/reassign-lead` — reassign org-owned leads to different reps (personal contacts blocked)
   - Frontend: `/admin/team-engagement` page with 3 tabs (Alerts 3+, Hot Leads, Team Activity)
   - Summary cards (hot leads count, alert count, total actions, engagement signals)
   - Team activity breakdown per rep (calls, texts, emails, cards)
   - Lead reassignment modal with team member search (org-owned leads only)
   - 30-second auto-refresh, period filters (Today, 48h, 7 Days)
7. **CRITICAL: Full Touchpoint Tracking Audit & Fix** (Mar 8, 2026)
   - **BUG 1 FIXED:** Twilio SMS sends created NO contact_events — `sms_sent` was never logged. Now logs `sms_sent`/`sms_failed` in BOTH message endpoints.
   - **BUG 2 FIXED:** `cards_sent` counter matched `"congrats"` broadly, catching customer views (e.g., `congrats_card_viewed`). Now only matches `*_card_sent` and `*card_shared`.
   - **BUG 3 FIXED:** Event type mismatch: `resolve_event_type()` returns `personal_sms` but summary only counted `sms_personal`. Now counts BOTH.
   - **BUG 4 FIXED:** Failed email/SMS attempts (`email_failed`, `sms_failed`) were not counted as activity touchpoints. Now included.
   - **Consistency:** Fixed leaderboard and team engagement endpoints to match the same counting logic.
8. **Notifications + Task Context Fixes** (Mar 8, 2026)
   - **Mobile responsiveness:** NotificationBell dropdown now scales to viewport width (maxWidth: 380, min 32px margin)
   - **Task timeline events:** Creating a task for a contact now logs a `task_created` contact_event visible in the contact's activity feed
   - **Task context banner:** Clicking a task notification navigates to the contact page with an orange "Pending Task" banner showing the task title + description
   - **Event icons:** Added proper icon/color mappings for task_created, task_completed, sms_sent, sms_failed, email_failed, lead_reassigned

### Unified Add Contact + Review Tracking Fix + Native Dialer (Mar 9, 2026)
1. **Unified Add Contact Flow** — The `+` button on the Contacts page now navigates to `/contact/new` (same form as Home page), replacing the old modal. Removed modal state, JSX, and 80+ lines of styles.
2. **Review Link Tracking Fix (Home Page)** — Quick-send from Home page now creates trackable short URLs with `contact_id` metadata, fixing misattribution where link clicks were attributed to the wrong contact (e.g., Bridger Ward instead of actual recipient).
3. **Short URL `cid` Dedup Fix** — Backend `short_urls.py` redirect handler had a bug where `cid not in original_url` matched the salesperson ID in the `sp=` parameter, skipping the `cid` append. Fixed to check `f"cid={cid}" not in original_url`.
4. **VCF Save Contact Fix** — Digital card's "Save My Contact" button now navigates directly to the VCF URL (`/api/card/vcard/{userId}`) instead of using JavaScript blob download. This triggers iOS Safari's native "Add to Contacts" dialog.
5. **Native iPhone Dialer** — Completely redesigned the dialer to match iOS native keypad: pure black background, dark grey circular buttons (#333) with letter labels, large auto-formatted number display, contact matching as you type (name + formatted phone), green call button center, backspace (right of call, only when digits entered), long-press backspace to clear all.
6. **Showcase Opt-In / Media Release System** — New customer consent flow for showcase and social media featuring:
   - New page `/opt-in/{cardId}` with toggle options: Showcase Page, Social Media (Instagram/TikTok/Facebook), Include Photo
   - "Want to be featured?" banner on congrats/thank-you cards (one-time per customer: opt-IN hides forever, "No thanks" keeps showing persistently)
   - Backend: `POST /api/opt-in/submit/{card_id}` saves consent, `GET /api/opt-in/check-consent` checks one-time status
   - **Salesperson approval required** — customer consent does NOT auto-approve for showcase; salesperson must manually approve
   - Consent stored in `showcase_consents` collection with phone-based deduplication
7. **Digital Card Cleanup** — Removed redundant phone/email text from card face (Call/Text/Email/QR buttons already handle that). Card now flows: Photo → Name → Title → Store → Social Icons → Save My Contact → Call/Text/Email/QR
8. **Two-Step Review Flow (All Cards)** — Internal "Had a great experience?" star rating + text review → after submit, transforms to green banner: "Thanks! Want to share it online? Leave a Google review — it means the world" → links to public review page. Implemented on both digital business card (`/card/{userId}`) and congrats cards (`/congrats/{cardId}`)

### Previous Features
- Engagement Intelligence, Hot Leads Dashboard
- Gamification & Leaderboards, Image Performance Overhaul
- Operations Manual, Carrier-Agnostic Messaging, Reporting System
- White-Label Emails, Public REST API & Webhooks

---

## Key API Endpoints
- `POST /api/tags/{user_id}/assign` — Triggers AI outreach + campaign auto-enrollment on "Sold"
- `GET /api/contacts/{user_id}/{contact_id}/personal-details` — Voice memo extracted details
- `PATCH /api/contacts/{user_id}/{contact_id}/personal-details` — Manual edit details
- `POST /api/contacts/{user_id}/{contact_id}/re-extract` — Re-extract from all voice notes
- `GET /api/campaign-config/effective/{user_id}` — Resolved campaign config
- `PUT /api/campaign-config/{level}/{entity_id}` — Set config (org/store/user)
- `GET /api/ai-outreach/relationship-brief/{user_id}/{contact_id}` — Full intel with personal details

## Key DB Collections
- `contacts.personal_details` — Structured personal data from voice memos
- `campaign_configs` — Hierarchical campaign configuration (level + entity_id)
- `ai_outreach` — AI-generated suggestions
- `engagement_signals` — Real-time customer interaction tracking
- `voice_notes` — Now has `intelligence_extracted` and `extracted_fields` flags

---

## Prioritized Backlog

### P1
- Voice Help Assistant
- Google Places API Integration
- AI-Powered Outreach (sold tag triggers)
- App Store Deployment Setup
- Pre-built date-based campaign templates in template picker
- Campaign Creation Redesign (**COMPLETED** — Mar 12, 2026)
- Send Health Report (**COMPLETED** — Mar 13, 2026)
- Personal Intelligence Editing Fix (**COMPLETED** — Mar 13, 2026)
- Scheduled Monthly Health Reports (**COMPLETED** — Mar 13, 2026)
- Configurable Messaging Channels (**COMPLETED** — Mar 13, 2026)
- Hub Navigation Reorganization (**COMPLETED** — Mar 13, 2026)
- Jessi Bar Login Regression Fix (**COMPLETED** — Mar 13, 2026)

### P2
- Full Twilio Integration (enables auto_send)
- WhatsApp, Training Hub, Inventory Module
- Code Cleanup: refactor admin.py, break down contact/[id].tsx

### Contact Tracking Misattribution Fix (Mar 8, 2026)
- **BUG FIXED:** When a link (review invite, digital card, showcase, link page) was clicked, the system attributed the view to the WRONG contact — it guessed from the "most recent message" instead of tracking the specific contact the link was sent to.
- **Root cause:** All tracking pages (public_review.py, digital_card.py, showcase.py, linkpage.py) used a heuristic that looked up the most recent message containing the link type → found the conversation → got the contact_id. If a user sent the same link to multiple contacts, the view was always attributed to the most recent one.
- **Fix:** Short URL redirect handler now appends `&cid=<contact_id>` (from stored metadata) to the redirect URL. All 4 tracking pages (review, digital card, showcase, link page) now accept an optional `cid` query parameter and use it directly, falling back to the legacy heuristic only for old links without the parameter.
- **Files changed:** `short_urls.py` (redirect + og-image handler reordered), `public_review.py`, `digital_card.py`, `showcase.py`, `linkpage.py`


### Share Card/Landing Page URL & Label Fixes (Mar 8, 2026)
- **Home screen "Share My Card":** Changed URL from `/p/` (landing page) → `/card/` (digital business card)
- **Contact page "Share Your Stuff":** Renamed mislabeled "Share Landing Page" → **"Share Digital Card"** (shares `/card/`), added new **"Share Landing Page"** tile (shares `/p/`)
- **Digital card visitor "Save My Contact":** Now directly downloads VCF file — no modal. Owner still sees "Share My Contact" with full sharing options.
- **Tested:** All 7 features verified.

## Recent Fixes (Mar 9, 2026)
- **Login Autofill Styling Fix:** Added CSS rules targeting `:-webkit-autofill` pseudo-class in `+html.tsx` to prevent browser autofill from showing black/yellow backgrounds on input fields. Uses `transition: background-color 5000s` approach for universal light/dark theme compatibility.
- **Setup Wizard Keyboard Dismissal Fix:** Root cause was `getS(colors)` creating a new StyleSheet on every re-render, invalidating all `useMemo` component wrappers (`SectionCard`, `Label`, `StepHeader`, `BtnRow`), causing React to unmount/remount TextInputs. Fixed by memoizing styles: `const s = useMemo(() => getS(colors), [colors])`.
- **Admin Users List Crash Fix (P0):** `GET /api/admin/hierarchy/users` was crashing with 500 error because some users have non-ObjectId `organization_id` values like `'org_001'`. Added `safe_objectid()` helper function to gracefully handle invalid ObjectIds across all admin endpoints. Also applied to `/api/admin/organizations` and `/api/admin/stores` list endpoints.
- **Role Change Now Works:** With the users list endpoint fixed, the entire flow works: list users → click user → click pencil → select new role → save.
- **Setup Wizard Relocated:** Moved "Onboard New Account" from the buried "Internal Administration" section to the top-level "Customer Infrastructure" section for faster access.
- **Role Edit Touch Target:** Increased pencil icon touch target from 4px to 10px padding for easier tapping.

- **User Delete Bug Fixed:** `useToast` was imported but never called as a hook in `/app/frontend/app/admin/users/[id].tsx`, making `showToast` undefined. After a successful backend delete, `showToast('User deleted')` threw a TypeError, caught by the catch block which showed "Failed to delete user". Added `const { showToast } = useToast()`. This also fixes toast errors for ALL other operations on that page (toggle status, role change, store assignment, etc.).

- **Brand Kit Logo Upload:** Added direct file upload to the Brand Kit page (`/settings/brand-kit`). Users can now upload a logo directly instead of only pasting a URL. The uploaded logo is synced to the store's `logo_url` field on save. Also fixed relative logo URLs in email templates by resolving them to absolute URLs using `APP_URL`.

- **Digital Card Sharing Redesign (Mar 9, 2026):**
  - Upgraded server-generated card image (Pillow): now includes store logo, QR code with tracked short URL, branded footer, accent bars, and clean typography
  - QR code + printed short URL are baked INTO the image — so even when shared as a photo (camera roll → Instagram), the tracking chain survives
  - Added OG meta tags to short URL handler for congrats cards — social platforms (Facebook, iMessage, Twitter) now show the full card image as a rich preview
  - Fixed share flow to always use tracked short URL (was using `window.location.href`)
  - Added Web Share API support for "Save Card" button — triggers native share sheet on mobile for direct camera roll save
  - Instagram share now downloads the card image first, then instructs user to post from gallery

- **Card Page + Performance Overhaul (Mar 9, 2026):**
  - Store logo on card page is now a hyperlink to the company's website
  - Salesman signature section links to their digital business card page
  - "My Card" quick link now correctly goes to `/card/{salesman_id}` (was going to wrong route)
  - Google review link now uses the actual Google review URL from store's `review_links` (was using a dead slug-based route)
  - All quick links (My Card, Showcase, Call, Text, Email) are now on ONE row — removed `flexWrap` and reduced spacing
  - Performance page labels fixed: "MY CARD" for digital business card shares, "CARD SHARES" for congrats/birthday/thank you cards
  - All performance tiles are now clickable — tapping opens a detail modal with recent activity (contact name, event type, timestamp), and tapping a contact navigates to their detail page
  - New backend endpoint: `GET /api/tasks/{user_id}/performance/detail?category=texts&period=week` returns recent events for a category

### Event Tracking Fix — All Send Paths (Mar 9, 2026)
- **Root cause:** Quick-send flows were calling `/messages/send/{userId}` (missing conversation_id → 404 silently caught) so no `contact_event` was created → no performance dashboard credit
- **Fixed files:** `quick-send/[action].tsx` (3 send methods: SMS, email, copy), `thread/[id].tsx` (personal SMS fetch URL), `touchpoints/index.tsx` (fallback send), `more.tsx` (showcase + birthday shares)
- **Fix:** All send paths now route through `/contacts/{userId}/{contactId}/events` (same collection performance dashboard queries) or `find-or-create-and-log` for flows without a contact yet
- **Tested:** 11/11 backend tests + all frontend tests passed (iteration 166)

### Performance Scorecard + Clickable Tiles (Mar 9, 2026)
- **Daily Scorecard:** Added hero card at top of performance page showing today's touchpoints vs yesterday, trend arrow (green up / red down), and motivational message. Always shows today's data regardless of period filter.
- **All tiles clickable:** Every tile in Communication, Sharing, Engagement, and Click-Through Breakdown sections now opens a detail modal showing individual events attributed to that category. Each event shows contact name, event label, timestamp, and navigates to the contact profile on tap.
- **New "Showcase" tile:** Added under Sharing section counting `showroom_shared` events.
- **New Leads clickable:** Now opens detail showing recently added contacts with source info.
- **Separated card views:** Click-Through Breakdown now has "My Card Views" (personal digital business card) and "Customer Card Views" (congrats, birthday, holiday cards combined) as separate tiles.
- **Streak counter:** Tracks consecutive days with 5+ touchpoints. Shows flame icon, day count, "ON FIRE" badge at 7+ days, and contextual message ("Today counts! Keep going!" or "Need X more to keep it alive").
- **Tested:** 15/15 backend tests + all frontend UI tests passed (iteration 167)

### Phase 2: Review Follow-Up Campaign + Smart Auto-Complete (Mar 9, 2026)
- **Review Follow-Up campaign:** 6th prebuilt template with `trigger_tag: review_sent`. 2 steps: Day 2 gentle check-in, Day 5 final nudge.
- **Auto-tag on review send:** When a review invite is sent (via quick-send or more.tsx), "Review Sent" tag is auto-applied with `auto_create_tag: true`. This triggers the Review Follow-Up campaign.
- **Smart auto-complete:** When a customer clicks the review link (tracked via short_urls.py), the system auto-completes all active review campaign enrollments, deletes pending sends, and marks related tasks as complete. No more nagging.
- **Tag normalization:** Tag names with spaces ("Review Sent") now correctly match template trigger_tags with underscores ("review_sent").
- **Tested:** 14/14 backend tests passed (iteration 168)

### Personal Best Tracking + Web Push Notifications (Mar 9, 2026)
- **Personal bests:** Performance page now shows Best Day (with date), Best Week, and Today's count side by side. Today tile shows "X to beat" when below personal best, or "NEW RECORD!" when above.
- **Web Push Notifications:** Service Worker (`sw-push.js`) registered for push notifications. Backend stores subscriptions via VAPID keys. Milestone notifications fire on: streak milestones (7, 14, 21, 30, 60, 90 days), level ups (Rookie → Legend), and new personal bests. Notifications tracked in `user_milestones` collection to avoid duplicates.
- **Push subscription CRUD:** `POST /api/push/subscribe/{userId}`, `DELETE /api/push/unsubscribe/{userId}`, `GET /api/push/vapid-key`
- **Tested:** 16/16 backend tests + all frontend UI tests passed (iteration 169)

### Congrats Card Quick Links + Review Text Update (Mar 9, 2026)
- **Review CTA text:** After internal review, changed "Leave a Google review" → "Leave an online review" and linked to the multi-platform review page (`/review/{storeSlug}`) instead of directly to Google
- **Quick links row:** Replaced `My Card | Showcase | Call | Text | Email` with the 4 composer "Share Your Stuff" items (minus VCF): `My Card | My Page | Showcase | Links`
  - My Card → `/card/{userId}` (digital business card)
  - My Page → `/p/{userId}` (personal landing page)
  - Showcase → `/showcase/{userId}` (delivery showcase)
  - Links → `/l/{username}` (link page with all social links)
- **Rationale:** Keep customers in the salesperson's ecosystem; store link removed to prevent leads going to other reps. Call/Text/Email still accessible via the My Card page (one tap from salesman name).
- **Link Page username:** Fetched via `/api/linkpage/user/{userId}` on card load; Links button hidden if no username configured.

### Auth Refactor + Persistent Sessions + Push Notifications + Leaderboard Enhancement (Mar 9, 2026)
1. **Auth Refactor (bcrypt):**
   - All passwords now hashed with bcrypt (signup, change-password, reset-password, admin user creation, setup wizard)
   - Login uses `verify_password()` which supports both bcrypt hashes and legacy plain-text (auto-upgrades to bcrypt on successful login)
   - Migration script at `/app/backend/migrations/hash_passwords.py` — already run on all 123 existing users
   - Helper functions `hash_password()` and `verify_password()` in `auth.py`, imported by `admin.py` and `setup_wizard.py`
2. **Persistent Sessions:**
   - Already implemented: `imos_session` cookie with 10-year expiry set on login
   - Frontend `loadAuth()` first checks localStorage, then falls back to cookie restoration via `GET /api/auth/me`
   - Users stay logged in until explicit logout
3. **Push Notifications on Event Creation:**
   - `_quick_milestone_check()` helper in `contact_events.py` — calculates today's event count, streak, best day, and level
   - Fired as `asyncio.create_task()` (fire-and-forget) after each event insertion in `contact_events.py` and `messages.py`
   - Calls `check_and_notify_milestones()` from `push_notifications.py` which is idempotent
4. **Leaderboard Period Filters:**
   - Replaced old month/year selectors with period tabs: This Week | This Month | All Time
   - Frontend API calls updated to pass `period` parameter
   - Backend already supported `period` parameter — no backend changes needed

### CRM Timeline Export (Mar 9, 2026)
1. **Public Activity Timeline Links:**
   - Each contact gets a unique, secure URL: `/timeline/{uuid-token}`
   - No login required — the token IS the security (like Google Docs "anyone with link")
   - Shows: store branding, contact info + tags, stats bar (activities, notes, customer since), full activity timeline grouped by date with icons
   - Backend: `/app/backend/routers/crm_timeline.py` — token generation, public timeline, PIN verification, settings
   - Frontend: `/app/frontend/app/timeline/[token].tsx` — clean read-only timeline page
2. **Optional Store-Level PIN Protection:**
   - Toggle in Settings > Integrations > RMS tab
   - 4-8 digit PIN, auto-generated when enabled
   - PIN verified once per session (stored in localStorage), then transparent
   - PIN sessions stored in `crm_pin_sessions` collection
3. **Copy CRM Link Button:**
   - Added to contact detail "Share Your Stuff" modal as "CRM Timeline Link" with gold "Copy" button
   - Generates token on first copy, marks contact as `crm_link_copied_at`
4. **CRM Link Filter on Contacts:**
   - Three filter tabs: All | CRM Linked | Not in CRM
   - Uses `crm_link_copied_at` field on contact model
5. **Export Stats:** `GET /api/crm/export-stats/{user_id}` returns total/linked/not_linked counts

### CRM Adoption Dashboard (Mar 9, 2026)
- Manager-level dashboard at `/admin/crm-dashboard`
- Shows: overall adoption % with progress bar, per-salesperson breakdown (ranked, color-coded progress bars), recent links copied feed
- Backend endpoint: `GET /api/crm/adoption-dashboard/{user_id}` — aggregates stats across all team members in the store
- Accessible from Settings > Integrations > RMS tab via "Dashboard" button
- Bug fix: CRM link Copy button was using `contact._id` (undefined) — fixed to use URL param `id`

### Duplicate Contact Merge Tool (Mar 11, 2026)
- **NEW FEATURE:** Full duplicate detection and merge system for contacts under the same salesperson.
- **Detection:** `GET /api/contacts/{user_id}/duplicates` — groups contacts by normalized phone (last 10 digits) within same salesperson, enriched with event/chat/card counts.
- **Merge:** `POST /api/contacts/{user_id}/merge` — migrates data across 15+ collections (`contact_events`, `conversations`, `tasks`, `campaigns`, `cards`, etc.), merges tags/notes/photos, soft-deletes duplicate with `status: "merged"`.
- **Safety:** Never merges across different salespeople. Rejects self-merge, cross-user merge, already-merged contacts.
- **Frontend:** New `/contacts/duplicates` page with "Most Active" badge, activity stats, one-click merge with confirmation.
- **Tested:** 13/13 backend tests passed (iteration 186), frontend verified.

### Contact Tracking Attribution Fix (Mar 11, 2026)
- **BUG FIXED (P0):** Short URL redirects for card links were passing the **card_id** as `cid` (contact_id) instead of the actual contact's ObjectId. This caused all card-view tracking events to be misattributed or lost.
- **Root cause:** `short_urls.py` used `reference_id` as fallback for `cid`. For card links, `reference_id` = card_id (NOT a contact_id). Metadata never stored the contact_id.
- **Fix 1 (`congrats_cards.py`):** Both `create_congrats_card` and `auto_create_card` now resolve the contact by phone+salesman_id and store `contact_id` in short URL metadata AND card document.
- **Fix 2 (`short_urls.py`):** Redirect handler now checks `link_type` — for `_card` types, only uses `metadata.contact_id` (never falls back to `reference_id`).
- **Fix 3:** Card endpoint resilience — 3 fallback lookups (card_id → birthday_cards → ObjectId → short_urls reference) + logging.
- **Per-salesperson isolation verified:** All contact lookups scope by `user_id` — same customer under different salespeople = separate records.
- **Tested:** 10/10 backend tests passed (iteration 185).

### Activity Feed Data Integrity Fix (Mar 11, 2026)
- **BUG FIXED (P0):** Activity Feed showing "Unknown" for all contact names/photos
- **Root cause:** `master-feed` endpoint used a single list comprehension `[ObjectId(cid) for cid in contact_ids]` to convert ALL contact_ids at once. If even ONE invalid contact_id existed (e.g., test data like `abc123def456`), the entire comprehension failed silently (`except: pass`), leaving `contacts_map` empty — so ALL events showed "Unknown".
- **Fix 1 (`contact_events.py`):** Changed to per-item ObjectId conversion with try/except — invalid IDs are skipped, valid ones still resolve correctly.
- **Fix 2 (`contact_activity.py`):** Added ObjectId validation in `log_customer_activity` — prevents storing events with invalid contact_ids.
- **Fix 3 (`tracking.py`):** Added ObjectId validation on incoming `contact_id` in tracking endpoint — rejects garbage IDs at the entry point.
- **Tested:** 13/13 backend tests passed, frontend Activity tab fully verified (iteration 184).

### Login Screen Loading Optimization (Mar 12, 2026)
- **BUG FIXED (P0):** Login screen took ~5 seconds to load with a spinner, then flickered/reloaded before settling.
- **Root causes found and fixed:**
  1. **Double `loadAuth()` calls** — Both `_layout.tsx` and `index.tsx` called `loadAuth()` simultaneously on mount, causing overlapping state updates and flicker. Fixed by removing the duplicate call from `index.tsx`.
  2. **Expensive retry logic on desktop** — `readWithRetry()` retried AsyncStorage reads with 300ms/600ms delays, even on desktop. Now only retries on iOS PWA where cold-boot race conditions exist.
  3. **Unnecessary cookie restore for fresh visitors** — When no local session exists, the app was making a network request to `/auth/me` (which always returned 401). Removed this for the empty-session path.
  4. **1-second retry delay** — A `setTimeout` in `index.tsx` added a 1-second wait before showing login. Removed entirely.
  5. **Black→white background flash** — Index spinner had hardcoded `#000` background while login page uses theme colors. Now uses `colors.bg` from theme store consistently.
  6. **Concurrent loadAuth prevention** — Added singleton promise pattern to prevent multiple simultaneous calls from causing state race conditions.
- **Files changed:** `store/authStore.ts`, `app/index.tsx`, `app/_layout.tsx`
- **Result:** Login screen now loads in ~2.3 seconds (down from ~5s) with no flicker or color flash

## Known Issues
- P2: Mobile tags sync
- P2: Leaderboard toggle not fully tested
- P2: React Hydration Error #418

### Campaign Creation Redesign — Unified Tag & Date Triggers (Mar 12, 2026)
- **NEW FEATURE:** Completely redesigned campaign creation to unify "Tag-Based" and "Date-Based" campaigns into a single, clear workflow.
- **Frontend (`campaigns/new.tsx`):**
  - New trigger type picker: "Tag-Based" (blue, shows SmartTagPicker) vs "Date-Based" (orange, shows Birthday/Anniversary/Sold Date options)
  - Each date type option has icon, description, and auto-fill for campaign name and default message
  - Green info box explains auto-enrollment when a date type is selected
  - Pre-built template selector properly sets trigger type to 'tag'
  - Updated validation: tag campaigns require a trigger tag, date campaigns require a date type
  - Save payload now includes `date_type` for date-based campaigns
- **Frontend (`campaigns/[id].tsx`):**
  - Edit campaign now shows Tag-Based vs Date-Based toggle
  - Date-based campaigns show the date type picker (Birthday/Anniversary/Sold Date) 
  - Switching trigger type marks campaign as having changes
- **Backend (`models.py`):** Added `date_type` field to both `Campaign` and `CampaignCreate` models
- **Backend (`campaigns.py`):**
  - `date_type` added to allowed update fields
  - `check_date_triggers` refactored to handle birthday, anniversary, AND sold_date (was only birthday + anniversary)
  - Uses both legacy `type` field and new `date_type` field for campaign matching
- **Backend (`contacts.py`):**
  - New `_check_date_campaign_enrollment()` helper auto-enrolls contacts in date campaigns when created/updated with date fields
  - Called on both `create_contact` and `update_contact` endpoints
  - Maps: `birthday` → birthday campaigns, `anniversary` → anniversary campaigns, `date_sold` → sold_date campaigns
- **Tested:** 11/11 backend tests + all frontend UI tests passed (iteration 189)

### In-App Onboarding Guide (Mar 12, 2026)
- **NEW PAGE:** Created `/admin/onboarding-guide.tsx` — a clean, scannable reference guide for super admins showing the complete 7-step account setup process.
- Each step shows: numbered card, icon, description, required fields (as colored pills), and a pro tip.
- Includes "What Happens After Setup" section explaining the new user's first login experience.
- Big "Start New Account Setup" CTA button links directly to the setup wizard.
- Added to the admin panel's Customer Infrastructure section as "Onboarding Guide" link.
- **BUG FIX:** Step 3 (Team Roster) in the setup wizard was missing a "Skip" button — users got stuck with no way to advance if they didn't want to add team members. Added `onSkip` prop to the BtnRow.

### Unified Onboarding Hub + TOS Acceptance (Mar 12, 2026)
- **NEW PAGE:** Created `/admin/onboarding-hub.tsx` — consolidated onboarding center replacing the separate "Onboard New Account" and "Onboarding Guide" links.
  - 7 action cards: New Org & Store, Add Store to Existing Org, Add Team Members, Add Individual Account, Partner/Reseller Onboard, White Label Partner, Internal Employee
  - Role-based visibility: super_admin sees all 7, org_admin sees 3, store_manager sees 1
  - Collapsible "Setup Wizard Quick-Reference Guide" built-in with 7-step wizard + "After Setup" section
  - Recently Added Users section at bottom
- **TOS ACCEPTANCE:** Added mandatory Terms of Service opt-in to the first-time password change screen (`/auth/change-password`):
  - User must click "Read Terms of Service" link first (opens in new tab)
  - Checkbox remains disabled until TOS is reviewed
  - Warning text "You must read the Terms of Service before accepting"
  - Backend stores `tos_accepted: true` and `tos_accepted_at` timestamp in user record
- **TERMS & PRIVACY UPDATED:**
  - Terms: Added sections 7 (Contact Data & CRM), 8 (Data Ownership & Portability), 9 (Data Transfer), 10 (SMS/Communication Terms) — now 16 sections total
  - Privacy: Added sections 3 (Contact Data You Store), 7 (Data Transfer & Portability) — now 12 sections total
  - Both updated to March 12, 2026
- **Files changed:** `admin/onboarding-hub.tsx` (new), `admin/index.tsx`, `auth/change-password.tsx`, `imos/terms.tsx`, `imos/privacy.tsx`, `backend/routers/auth.py`
- **Tested:** iteration 190 — 6/6 backend tests + all frontend UI tests passed

### Account Health / Retention Dashboard (Mar 13, 2026)
- **NEW BACKEND:** `/api/account-health/overview` — Lists all user accounts with health scores (0-100), sorted worst-first. Aggregates contacts, messages, touchpoints, campaigns, login recency.
- **NEW BACKEND:** `/api/account-health/user/{user_id}` — Detailed health report with 9 metric categories, event breakdown bar chart, recent activity timeline, account info.
- **NEW BACKEND:** `/api/account-health/org/{org_id}` — Org-level aggregate health report across all users.
- **Health Score Algorithm:** Activity (40pts: login recency), Contacts (20pts), Messages (20pts), Campaigns+Touchpoints (20pts). Grades: >=70 Healthy (green), >=40 At Risk (orange), <40 Critical (red).
- **NEW FRONTEND:** `/admin/account-health` — Dashboard with summary cards (Healthy/At Risk/Critical counts), search, filter pills, 30d/90d period toggle, sortable account list with health score circles.
- **NEW FRONTEND:** `/admin/account-health/[id]` — Detailed user health report with health banner, 9 metric tiles, touchpoint breakdown bars, recent activity timeline, account info.
- **Admin Panel:** Added "Account Health" link (teal pulse icon) in Customer Infrastructure section.
- **Tested:** iteration 191 — 19/19 backend tests + all frontend UI verified

### Personal Intelligence Editing Fix (Mar 13, 2026)
- **BUG FIXED (P0):** AI-extracted Personal Intelligence on contact detail page was READ-ONLY. Users could not edit spouse, kids, interests, or other extracted data.
- **Root cause:** `PersonalIntelSection` in `contact/[id].tsx` only displayed data, had no edit UI, and never called the existing `PATCH /api/contacts/{user_id}/{contact_id}/personal-details` endpoint.
- **Fix:** Extracted component to standalone `/app/frontend/components/PersonalIntelSection.tsx` with full edit/save/cancel functionality:
  - View mode: displays all personal details with Edit button
  - Edit mode: 16 editable fields (spouse, kids, interests, occupation, vehicle, etc.) with Save/Cancel
  - "Add Personal Intelligence" dashed button when no data exists
  - Calls PATCH endpoint on save, shows success/error toasts
- **Tested:** iteration 192 — 8/8 backend + 100% frontend verified

### Send Health Report Feature (Mar 13, 2026)
- **NEW BACKEND:** `POST /api/account-health/user/{user_id}/send-report` — Generates comprehensive HTML health report email and sends via Resend. Includes health score, account info, key metrics (contacts, messages, touchpoints, campaigns, enrollments, tasks, links, cards), touchpoint breakdown bars, and recent activity timeline.
- **NEW BACKEND:** `POST /api/account-health/org/{org_id}/send-report` — Org-level aggregate report with per-team-member breakdown table.
- **NEW FRONTEND (Overview):** Paper-plane quick-send icon on each account row. Opens modal pre-filled with user's email.
- **NEW FRONTEND (Detail):** Gold "Send Report" button in header. Modal with recipient email, name, optional personal note, and Send/Cancel.
- **Use case:** Partners/resellers/admins can email health snapshots to account contacts for retention reviews.
- **Note:** Email sending requires verified Resend domain (works in production, not preview).
- **Tested:** iteration 193 — 12/12 backend + 100% frontend verified

### Scheduled Monthly Health Reports (Mar 13, 2026)
- **NEW BACKEND CRUD:** Full schedule management at `/api/account-health/schedules`:
  - `POST` creates schedule (scope: user/org, target_id, recipient_email, note)
  - `GET` lists all schedules sorted by creation date
  - `PUT /{id}` toggles active/pauses and edits email/note
  - `DELETE /{id}` removes a schedule
- **Scheduler Job:** Added `run_monthly_health_reports` to APScheduler (daily at 22:00 UTC). Only sends emails on the last day of each month. Updates `last_sent_at` on each schedule after successful send.
- **NEW FRONTEND Tab:** "Scheduled Reports" tab on Account Health dashboard with:
  - "New Monthly Schedule" button opens inline form
  - Individual/Organization scope toggle
  - Quick-pick account chips with health score badges for fast selection
  - Schedule list with active toggle (green), delete, target info, email, last-sent date
  - Empty state with helpful guidance
- **Quick Actions:** Calendar icon on each overview row lets admins jump to schedule creation pre-filled with that account's data.
- **DB Collection:** `health_report_schedules` stores scope, target_id/name, recipient, note, frequency, active, created_by, created_at, last_sent_at
- **Tested:** iteration 194 — 12/12 backend + 100% frontend verified

## Recent UI Fixes (Mar 8, 2026)
- **AI Suggestion Bubble:** Changed from dark green solid background to light green outline with subtle tint — text now readable in light mode
- **AI Outreach Page:** Converted all hardcoded dark-mode colors to use theme store (`useThemeStore`) — now properly renders in both light and dark modes
- **OG Image / iMessage Link Preview Fix:** Created white-background OG image (`og-image.png`) and added `/api/s/og-image/{user_id}` endpoint that composites store logos onto white. All link previews now guaranteed to have WHITE background instead of showing transparency artifacts (red/brown tint)


### Configurable Messaging Channels (Mar 13, 2026)
- **NEW BACKEND:** Full CRUD at `/api/messaging-channels/`:
  - `GET /available` — Returns all 7 channels: SMS, WhatsApp, Facebook Messenger, Telegram, LinkedIn, Email, Copy to Clipboard
  - `GET /org/{org_id}` — Returns enabled channels for organization
  - `PUT /org/{org_id}` — Updates org's enabled channels (validates channel IDs)
  - `GET /user/{user_id}` — Returns user's channels based on their org config (falls back to SMS default)
- **NEW FRONTEND Settings Page:** `/settings/messaging-channels` with:
  - 7 channel cards with branded icons, descriptions, and toggle switches
  - Color-coded active borders (green accent for SMS, WhatsApp green, FB blue, etc.)
  - "Requires phone number" indicator on SMS/WhatsApp
  - Dynamic info banner: changes text based on single vs multi-channel mode
  - "Share Experience Preview" shows either "opens directly" (1 channel) or picker preview (multi)
  - Prevents disabling all channels (minimum 1 required)
- **NEW Reusable ChannelPicker Component:** `/components/ChannelPicker.tsx`
  - Bottom-sheet style modal with channel icons in a grid
  - **Smart routing:** 1 channel → auto-opens directly (zero friction), 2+ → shows picker
  - URL schemes: WhatsApp (`wa.me`), Telegram (`t.me/share`), LinkedIn, Messenger, SMS, Email, Clipboard
  - `useChannelPicker()` hook for easy integration
  - Disabled state for channels requiring phone when contact has no phone
- **Integration:** Wired into contact detail page message composer — replaces hardcoded `sms://` with dynamic channel routing
- **Menu:** Added to More > Administration as "Messaging Channels" with WhatsApp green icon
- **Tested:** iteration 195 — 19/19 backend + 100% frontend verified

### Smart Contact Search + Voice-to-Task (Mar 8, 2026)

### Hub Navigation Reorganization (Mar 13, 2026)
- **MAJOR UX OVERHAUL:** Completely restructured the "More" menu (35+ flat items) into a clean, role-aware "Hub" with 9 organized sections:
  1. **My Brand** (gold) — Digital Card, Link Page, Showcase, Review Link, Templates, Card Templates
  2. **My Tools** (blue) — Today's Touchpoints, Ask Jessi, AI Follow-ups, Team Chat
  3. **Campaigns** (red) — SMS/Email Campaigns, Dashboard, Broadcast, Date Triggers
  4. **My Performance** (green) — My Stats, Customer Engagement, Leaderboard, Reports, Email Analytics
  5. **Setup & Manage** (orange, admin-only) — Store Profile, Brand Kit, Messaging Channels, Review Links, Tags, Team, Integrations
  6. **Account Management** (blue, super_admin/partner-only) — Onboarding Hub, Account Health, Admin Dashboard, Organizations, Users
  7. **Internal Operations** (gray, super_admin-only) — Partners, Revenue, Billing, Phone Assignments, Bulk Transfer
  8. **Learning** — Training Hub, SOPs & Guides
  9. **Settings** — Security, Calendar, Help Center
- **Role-aware visibility:** Salesperson sees sections 1-4 + Learning + Settings only. Admin adds Setup & Manage. Super admin/partner adds Account Management + Internal Operations.
- **Bottom tab renamed:** "Menu" → "Hub" with `apps` icon
- **Jessi Bar regression fix:** Used `useSegments()` from expo-router to detect auth/login/index/onboarding routes and hide "Ask Jessi" bar. No longer depends on cached user state.
- **Tested:** iteration 196 — 100% (15/15 frontend tests passed)


- **Smart Contact Search:** All 6 home screen tiles and card sending now search by first name, last name, phone number, AND email. Backend `/api/contacts/{user_id}` also includes email in search query.
- **Voice Recorder 5 Minutes:** Contact page voice recorder max length increased from 2 minutes to 5 minutes.
- **Voice-to-Task:** New task page (`/tasks/new`) includes voice recording button. Speaks task → transcribed via Whisper → AI (gpt-4o-mini) extracts title, type, priority, due date, and due time. Backend endpoint: `POST /api/voice/parse-task`.
- **Tested:** 11/11 backend tests passed, all frontend features verified.

### Unified Add Contact Flow (Mar 8, 2026)
- **UNIFIED:** The "+" button on the Contacts page now navigates to `/contact/new` (same as Home page's "Add Contact" tile), replacing the previous custom inline modal
- **Animation fix:** Removed the old modal-based add contact flow that caused a "jumping" animation glitch on open
- **Cleanup:** Removed modal state variables, modal JSX, and 80+ lines of modal styles from `contacts.tsx`
- **Tested:** 8/8 frontend tests passed

### Favicon & PWA Branding Fix (Mar 9, 2026)
- **Favicon:** Regenerated all favicon/icon files (favicon.ico, favicon-16/32.png, apple-touch-icon, logo192, logo512, android-chrome icons) with **rounded corners** on the white tile background — corners are now transparent instead of sharp square
- **PWA Home Screen Label:** Changed manifest `short_name` from "iMOs" to "On Social" — when users "Add to Home Screen", the tile label now reads "On Social"
- **Meta Tags:** Updated `apple-mobile-web-app-title` to "On Social" in both `index.html` and `_layout.tsx`
- **Icon link tags:** Added explicit PNG favicon links (`favicon-32x32.png`, `favicon-16x16.png`) for better browser compatibility

### Generic Tag → Campaign Engine (Phase 1) (Mar 9, 2026)
- **Generic auto-enrollment:** Replaced hardcoded "sold"-only campaign enrollment with a generic engine. ANY tag that matches a campaign's `trigger_tag` now auto-creates the campaign (from prebuilt templates) and enrolls the contact. Works for: `sold`, `be_back`, `service_due`, `referral`, `vip`.
- **Skip campaign toggle:** `POST /api/tags/{user_id}/assign` now accepts `skip_campaign: true` to apply a tag WITHOUT triggering campaign enrollment. Default is false (campaigns trigger).
- **Tag picker in card creation:** The create card page (`/settings/create-card`) now shows all available tags as selectable colored chips. Users pick tags during card creation → tags applied to contact → campaign auto-enrolls.
- **Campaign toggle UI:** When tags are selected, a "Start follow-up campaign" toggle appears (default ON, green). Users can turn it off to apply tags without campaigns.
- **Card creation backend:** `POST /api/congrats/create` accepts optional `tags` (JSON array) and `skip_campaign` Form parameters.
- **Tested:** 13/13 backend tests passed, all frontend UI tests passed.

### Auto "Recent" Tag + Photo Backfill (Mar 9, 2026)
- **Auto "Recent" tag:** Every card creation automatically applies a "Recent" tag to the contact with a `tag_timestamps.Recent` timestamp. Tag is auto-created as a system tag (color: #5856D6) if it doesn't exist.
- **Photo → Avatar backfill:** When a NEW contact is created via `find-or-create-and-log` (during card sharing), the system looks for a recent card matching that phone and backfills the photo as the contact's avatar.
- **Scheduler: 14-day expiry:** New daily job `daily_recent_tag_expiry` runs at 4 AM UTC. Removes "Recent" tag from contacts where it was applied >14 days ago.
- **Tested:** 11/11 backend tests passed (iteration 165).

### Comprehensive Event Attribution Audit & Fix (Mar 10, 2026)
- **ROOT CAUSE:** `thread/[id].tsx` personal SMS flow used raw `fetch()` with `keepalive:true` that iOS Safari PWA kills when navigating to `sms:` URL. Also `convId` could be a contact ID instead of conversation ID causing silent 404s.
- **FULL AUDIT COMPLETED** — Every file that opens `sms:`, `tel:`, or `mailto:` for a logged-in user was audited and fixed:
  - `thread/[id].tsx`: Replaced raw fetch+keepalive with `await api.post()` + `sendBeacon` fallback
  - `contacts.tsx`: Added `await contactsAPI.logEvent(call_placed)` before `tel:` (was missing)
  - `inbox.tsx`: Added `await contactsAPI.logEvent(call_placed)` to handleQuickCall (was missing)
  - `dialer.tsx`: Replaced fetch+keepalive with `await api.post()` before `tel:`
  - `tasks/index.tsx`: Added `await contactsAPI.logEvent(call_placed)` before `tel:` (was missing)
  - `admin/hot-leads.tsx`: Added `await api.post(events)` before `sms:` (was missing)
  - `touchpoints/index.tsx`: Added `await contactsAPI.logEvent(call_placed)` to handleCall (was missing)
  - `more.tsx`: Moved event logging BEFORE native app open for all 6 paths
- **KEY PATTERN**: Every send uses `await` BEFORE opening native app. No fire-and-forget.
- **Tested**: iterations 172 (15/15), 173 (11/11), 174 (35/35 + all frontend pages)

### Session Persistence Fix (Mar 10, 2026)
- **Cookie**: Set `secure=True` for HTTPS production
- **Axios**: Added `withCredentials: true` for reliable cookie sending
- **401 Auto-Restore**: Added response interceptor that tries cookie-based `/api/auth/me` session restore on 401 before logging out — prevents unnecessary logouts when AsyncStorage is cleared by iOS

### Push Notifications — Live (Mar 10, 2026)
- **Registration**: Push subscription now registers on app startup (was only on Performance page)
- **Engagement Alerts**: When a customer views a card or engages, the salesperson gets a push notification
- **New Lead Alerts**: When a demo request comes in, admins get a push notification
- **Milestone Notifications**: Streak achievements, level ups, personal bests (was already built)
- **Test Endpoint**: `POST /api/push/test/{userId}` for verifying push is working
- **Service Worker**: `sw-push.js` handles incoming pushes and notification clicks
- **Tested**: iteration 175 (13/13 backend, all frontend pages verified)

### SMS Attribution Fix — Card Shares Counted As Texts (Mar 10, 2026)
- **ROOT CAUSE:** Thread page's personal SMS flow was passing `pendingEventType` (e.g., `holiday_card_sent`) to the `/messages/send` endpoint. The performance dashboard only counts `sms_sent + personal_sms + sms_personal + sms_failed` as texts — card-type events were invisible to the texts counter.
- **FIX:** Personal SMS flow no longer passes `pendingEventType` to the messages/send endpoint. Backend's `resolve_event_type` defaults to `personal_sms`. The card-specific event is already logged separately by the card creation flow.
- **Messages.py**: Testing agent also fixed `event_type` not being returned in the API response for sms_personal channel.
- **Result:** SMS sends now always create `personal_sms` events → counted in Texts on both Today's Touchpoints and My Performance dashboard.
- **Tested**: iteration 176 (14/14 backend, frontend verified)


### CRM Timeline Enhancement — Full Conversation History (Mar 10, 2026)
- **PROBLEM:** CRM timeline export only showed `contact_events` — missing the salesperson's actual messages (SMS/email bodies) and other interactions (campaigns, cards, broadcasts)
- **FIX:** Backend now fetches from **5 data sources**: `contact_events`, `messages` (via conversations), `campaign_enrollments`, `congrats_cards_sent`, `broadcast_recipients`
- **Direction Classification**: Each event tagged as `outbound` (salesperson) or `inbound` (customer engagement). Inbound types: `*_viewed`, `customer_reply`, `review_page_viewed`, `review_link_clicked`, etc.
- **Message Content**: Actual SMS/email bodies included via `full_content` field (using `content` field from messages collection)
- **Frontend**: Stats bar shows Total Activities / Salesperson / Customer / Notes counts. Direction badges (blue "Salesperson", green "Customer") on each event. Message content displayed inline.
- **Tested**: iteration 177 (17/17 backend tests passed, 100% frontend verified)

### CRM Link iOS Share Sheet Bug Fix (Mar 10, 2026)
- **PROBLEM:** iOS share sheet concatenated the `text` field ("Activity timeline for...") with the `url` when user selected "Copy", resulting in broken tokens with `%20Activity%20timeline%20f...` appended
- **FIX (Frontend):** Removed `text` from `navigator.share()` — only sends `title` and `url` now
- **FIX (Backend):** Added defensive token parsing — strips any trailing garbage after the UUID before DB lookup
- **Result:** Both new clean links AND old broken links now work

### "Show All Events" Button Fix (Mar 10, 2026)
- **PROBLEM:** The "Show All X Events" button on the contact detail page only limited the FIRST date group to 5 events, but all subsequent date groups were always fully rendered. If the first group naturally had ≤5 events, clicking "Show All" had zero visible effect.
- **FIX:** Replaced per-group limiting with a running total counter across all groups. Now exactly 5 events show when collapsed (across all date groups), and all events show when expanded.
- **File:** `/app/frontend/app/contact/[id].tsx` lines 3042-3160

## Test Credentials
- Super Admin: `forest@imosapp.com` / `Admin123!`

### Unified "Texts Sent" Metric (Mar 10, 2026)
- **PROBLEM:** Sending a card (Welcome, Congrats, Birthday, etc.) via text didn't count as a "text sent" on dashboards. Only plain SMS was counted. Cards = texts since users open the SMS app.
- **FIX:** Single source of truth `SMS_EVENT_TYPES` in `tasks.py` includes all SMS event types. Updated: daily tasks, performance dashboard, detail drilldown, leaderboard, engagement team stats.
- **Impact:** Texts count 58 → 202 (144 card/link sends now counted). No double-counting in totals.

### Jessie AI Support Agent — v2.0 Upgrade (Mar 10, 2026)
- **PROBLEM:** Jessie was extremely slow (10-15s+ per response) because it replayed the ENTIRE chat history through separate LLM API calls for every message. Knowledge was also shallow — just a paragraph overview.
- **FIX (Speed):** Eliminated the O(n²) history replay. Now passes last 8 messages as text context in the system prompt, then makes a SINGLE LLM call. Response time: **1.4-3.3 seconds** (was 10-15s+).
- **FIX (Knowledge):** Replaced the shallow prompt with a comprehensive ~4000-word knowledge base covering every feature, screen, navigation path, workflow, troubleshooting step, and onboarding flow.
- **FIX (Context):** Injects user-specific context (name, role, org, contact count, activity count) so Jessie gives personalized answers and knows whether the user has admin access.
- **FIX (Frontend):** Text input now skips TTS generation (instant text response). Voice input still gets TTS.
- **Model:** Switched from gpt-5.2 to gpt-4o-mini for faster responses (knowledge base compensates).

### Jessie Floating Chat Button + Context-Aware Panel (Mar 10, 2026)
- **Feature:** Persistent floating gold chat button (bottom-right, above tab bar) on every authenticated page
- **Panel:** Slide-up chat panel with text input, message history, gold user bubbles
- **Context-Aware:** Uses `usePathname()` to detect current page and inject it into the greeting and backend prompt (e.g., "I see you're on the Brand Kit Settings")
- **Hidden on:** Auth pages, public pages (timeline, review, card), and the dedicated Jessie page

### Jessi Phase 2: Live Data Awareness (Mar 10, 2026)
- **Live Stats Injection:** Jessi now pulls today's real-time touchpoint data (texts, calls, emails), pending/overdue tasks, unread conversations, and hot lead count. She references these naturally ("You've sent 52 texts today, have 15 hot leads needing attention").
- **Contact-Aware:** When opened from a contact record, Jessi fetches the contact's name, tags, last interaction date, recent activity, and pending tasks. She gives tag-specific advice (sold → thank-you card + review; hot lead → immediate follow-up; dormant → re-engagement). Also warns if contact hasn't been contacted in 7+ or 30+ days.
- **Proactive Suggestions:** Context-driven nudges based on page + data: pending tasks, hot leads needing attention, unread messages, today's progress level.
- **Files:** `/app/backend/services/jessie_service.py` (3 new context functions), `/app/frontend/components/JessieFloatingChat.tsx` (passes contact_id), `/app/backend/routers/jessie.py` (accepts contact_id)

### Jessi Phase 3: Data Lookup Agent (Mar 10, 2026)
- **Feature:** Jessi can now query the database in real-time based on the user's question. 7 lookup capabilities:
  1. **Contact Search** — "Tell me about Sarah Johnson" → finds matching contacts with phone, email, tags
  2. **Hot Leads** — "Who are my hot leads?" → lists all hot leads with last contact date
  3. **Tasks** — "What tasks do I have?" → shows pending/overdue with priority and contact names
  4. **Weekly/Monthly Stats** — "How did I do this week?" → real touchpoint breakdown
  5. **Team Performance** — "How's my team doing?" → each member's touchpoint count (manager/admin only)
  6. **Unread Messages** — "Any unread messages?" → lists unread conversations or confirms inbox is clear
  7. **Dormant Contacts** — "Who am I neglecting?" → contacts with no activity in 14+ days
- **How it works:** Keyword matching on the user's message triggers pre-fetch queries. Results are injected into the LLM system prompt. No extra LLM calls = no added latency.
- **Lookups only — no write actions.** Jessi reads data but never modifies anything.
- **File:** `/app/backend/services/jessie_service.py` — `_build_data_lookups()` function
- **Files:** `/app/frontend/components/JessieFloatingChat.tsx` (new), `/app/frontend/app/_layout.tsx` (import + render)
- **Files:** `/app/backend/services/jessie_service.py` (complete rewrite), `/app/frontend/app/jessie.tsx` (TTS optimization)
- **Tested:** iteration 178 (12/12 passed)


### Bug Fix: Dead Review Link on Digital Card (Mar 10, 2026)
- **PROBLEM:** After submitting an internal review on a congrats card page, the "Leave an online review" link did nothing. The `storeSlug` was always null because `GET /api/auth/user/{user_id}` didn't include store info.
- **FIX:** Enriched the `/api/auth/user/{user_id}` endpoint to include `store` object (slug, name) by querying the stores collection when `store_id` is present.
- **File:** `/app/backend/routers/auth.py` lines 817-843

### Bug Fix: Company Docs "Load Documents" Button (Mar 10, 2026)
- **PROBLEM:** The seed endpoint returned "Docs already seeded" and refused to re-seed when docs existed. Pressing "Load Documents" appeared to do nothing.
- **FIX:** Changed the seed endpoint to always clear existing seeded docs and re-seed. AI-generated docs (Articles of Incorporation) are preserved.
- **File:** `/app/backend/routers/docs.py` line 446

### Feature: AI-Generated Articles of Incorporation (Mar 10, 2026)
- **Feature:** New `POST /api/docs/generate-articles-of-incorporation` endpoint uses OpenAI via emergentintegrations to generate a professional 10-section Articles of Incorporation document specific to i'M On Social LLC.
- **Integration:** Uses `LlmChat` with gpt-4o-mini, outputs JSON array for reliable parsing into slides.
- **File:** `/app/backend/routers/docs.py` line 933

### Bug Fix: Company Docs Category Pills Jumping (Mar 10, 2026)
- **PROBLEM:** Category filter chips in the Company Docs page had inconsistent sizes, causing them to jump around when scrolling or switching categories.
- **FIX:** Changed pills from dynamic `paddingVertical: 8` to fixed `height: 36` with `justifyContent: 'center'` and `minWidth: 56`.
- **File:** `/app/frontend/app/admin/docs/index.tsx` line 454

### Bug Fix: Home Screen Keypad Jumping (Mar 10, 2026)
- **PROBLEM:** When typing on the keypad and contact matches appeared, they pushed the keypad buttons down, causing the numbers to jump around.
- **FIX:** Changed contact matches to use `position: 'absolute'` with `top: '100%'` to overlay on top of the keypad instead of pushing it down. Added scrollable container with maxHeight: 120.
- **File:** `/app/frontend/app/(tabs)/home.tsx` lines 264-333

### Company Docs Seed Updated (Mar 10, 2026)
- Frontend `seedDocs()` now chains: seed base docs → seed operations manual → generate articles of incorporation
- **File:** `/app/frontend/app/admin/docs/index.tsx` line 122


### Bug Fix: Keyword Detection Misclassifying Texts as Card Events (Mar 10, 2026)
- **PROBLEM:** A regular text message containing the word "congrats" (e.g., "Hey Forest, saw you opened the congrats...") was being logged as "Congrats Card Sent" in the activity feed. The `resolve_event_type()` function in `utils/event_types.py` used keyword matching that triggered on ANY message containing "congrats", "birthday", "anniversary", etc. — even plain conversational texts with no card or link involved.
- **FIX:** Keyword-based event type detection now only triggers when the message also contains a URL (`https?://`). Plain text messages without links always default to `personal_sms`.
- **File:** `/app/backend/utils/event_types.py` lines 194-207

### Auth Persistence Hardening (Mar 11, 2026)
- **PROBLEM:** Users on production (iOS PWA) getting logged out 3-4 times/day despite 10-year cookie and localStorage persistence.
- **ROOT CAUSE:** The `loadAuth()` function had a silent failure mode — if `JSON.parse(userStr)` threw (corrupted data from iOS memory pressure, interrupted writes, etc.), the entire try block jumped to catch, which set `isLoading: false` WITHOUT attempting the cookie fallback. User silently landed on login screen.
- **FIXES:**
  1. `loadAuth()` catch block now attempts cookie restore (`GET /auth/me`) as last resort instead of giving up
  2. All `JSON.parse` calls wrapped in `safeParse()` helper — corrupted data triggers cookie restore instead of crash
  3. API request interceptor now reads user from **Zustand in-memory state first** (instant), falls back to AsyncStorage only on cold boot. Eliminates per-request AsyncStorage reads that could return null under memory pressure.
  4. Fallback timeout reduced from 30s to 8s with automatic retry
- **Files:** `/app/frontend/store/authStore.ts`, `/app/frontend/services/api.ts`, `/app/frontend/app/index.tsx`


### Company Docs Content Update (Mar 10, 2026)
- **Operations Manual updated to v4.0** with 27 slides covering all current features:
  - Updated Jessi AI slide (16) with Phase 2/3 capabilities: floating chat, context awareness, voice, live data lookups
  - Updated Digital Business Cards slide (12) with congrats card image generation (Pillow + QR codes)
  - Updated Activity Tracking slide (8) with centralized event type resolution system
  - Added Performance Dashboard & CRM Timeline slide (26)
  - Updated Third-Party Integrations slide (21) with Pillow and qrcode libraries
  - Updated API Reference slide (25) with new endpoints (Jessi, CRM timeline, docs)
  - Updated Onboarding Guide with Jessi, leaderboards, performance dashboard
  - Version bumped to 4.0, date to March 2026
- All 8 base docs re-seeded with app-specific content
- Articles of Incorporation preserved across re-seeds



### Universal Customer Click Tracking System (Mar 11, 2026)
- **PROBLEM:** Customer interactions on shared pages (digital cards, congrats cards, review pages, link pages, store cards) were NOT being tracked. The tracking system had been partially implemented (backend endpoint + frontend utility created) but never wired into any frontend pages. Additionally, the `cid` (contact_id) URL parameter — appended by the short URL redirect handler for accurate attribution — was never read by any customer-facing page.
- **ROOT CAUSE (5 issues):**
  1. `cid` URL param not read by ANY customer-facing page (card, congrats, review, link page, store card)
  2. `cid` not passed to backend API calls for accurate page-view tracking
  3. `trackCustomerAction` imported but never called on digital card page; not even imported on other 4 pages
  4. Link page click tracking only incremented a counter, didn't create contact_events
  5. Tracking endpoint didn't support `contact_id` directly (only phone/name lookup)
- **FIX — Backend (`/app/backend/routers/tracking.py`):**
  - Added `contact_id` support as preferred attribution path (direct `log_customer_activity` call)
  - Falls back to `customer_phone`/`customer_name` lookup if no `contact_id`
  - Expanded `ACTION_CONFIG` from ~20 to 45+ mapped actions across all 5 page types
  - Every action has: event_type, human-readable title, icon, brand color
- **FIX — Frontend (ALL 5 customer-facing pages):**
  - `/app/frontend/app/card/[userId].tsx`: Reads `cid`, passes to `GET /card/data/{userId}?cid=...`, tracks: Call, Text, Email, Social links (per platform), Website, Save Contact, Review CTA, Online Review, Refer a Friend, Share (via link/copy/SMS/email/QR)
  - `/app/frontend/app/congrats/[cardId].tsx`: Reads `cid`, tracks: Download, Share (per platform), Internal Review, Online Review, Quick links (My Card, My Page, Showcase, Links), Salesman card link, Opt-in
  - `/app/frontend/app/review/[storeSlug].tsx`: Reads `cid`, passes to `GET /review/page/{slug}?sp=...&cid=...`, tracks: Review platform clicks (Google, Yelp, etc.), Feedback submission
  - `/app/frontend/app/l/[username].tsx`: Reads `cid`, passes to `GET /linkpage/public/{username}?cid=...`, tracks: All link clicks (dual: legacy counter + universal tracking)
  - `/app/frontend/app/card/store/[storeSlug].tsx`: Reads `sp`/`cid`, tracks: Call, Email, Website, Directions, Team member card clicks
- **DO NOT REVERT:** The tracking wiring in these 5 files is critical. Every `onPress` handler that opens a URL or triggers an action MUST call `trackCustomerAction` BEFORE the action. If adding new CTAs, follow the same pattern.
- **Architecture:**
  - Short URL redirect → appends `?cid=<contact_id>` → customer-facing page reads `cid` → passes to `trackCustomerAction('page', 'action', { salesperson_id, contact_id })` → `POST /api/tracking/event` → `log_customer_activity()` → `contact_events` collection → feeds into: activity feed, daily touchpoints, leaderboard, performance dashboard
- **Tested:** 13/13 backend tests passed, all 5 frontend pages verified (iteration 180)

## DO NOT REVERT — Universal Tracking Invariants
1. Every customer-facing page MUST read `cid` from URL params

### Customer Performance Rankings (Mar 11, 2026)
- **NEW FEATURE:** Customer engagement leaderboard — ranks contacts by weighted interaction scores
- **Backend:** `GET /api/tracking/customer-rankings/{user_id}?period=today|week|month|all&scope=user|org|global`
  - Aggregates `contact_events` per contact, applies `SCORE_WEIGHTS` (review=5, call/text/email=3, page view=1, etc.)
  - Returns: ranked list with score, event_count, breakdown, last_activity, contact info
- **Frontend:** `/app/frontend/app/touchpoints/customer-performance.tsx`
  - Period filters: Today, This Week, This Month, All Time
  - Scope filters: My Contacts, Organization, Global
  - Heat labels: Very Engaged (red), Engaged (orange), Warm (yellow), Cool (gray)
  - Score bars with visual indicator
  - Tap contact → detail modal with full activity breakdown + "View Contact" button
- **Touchpoints index:** Added "Customer Performance" tile below "My Performance"
- **Home screen:** Removed "AI Follow-ups" tile (moved to Menu > My Tools)
- **Menu:** Added "Customer Performance" under Insights, "AI Follow-ups" under My Tools
- **Tested:** 12/12 backend tests passed, all frontend verified (iteration 181)

### Jessi Top Bar (Mar 11, 2026)
- Replaced floating gold chat bubble with slim 22px "Have questions? Ask Jessi" bar at top of every screen
- Root layout applies `paddingTop: 22` for logged-in users so content doesn't overlap
- Bar shows on ALL screens (HIDDEN_ROUTES cleared) — user explicitly requested no hiding
- File: `/app/frontend/components/JessieFloatingChat.tsx`, `/app/frontend/app/_layout.tsx`

2. Every customer-facing page MUST pass `cid` to its backend data API call
3. Every clickable CTA MUST call `trackCustomerAction` BEFORE the action
4. The tracking endpoint MUST accept `contact_id` as preferred attribution (no phone/name lookup needed)
5. `trackCustomerAction` is fire-and-forget — NEVER block user actions on tracking

### Role-Based Access Control (RBAC) Menu Redesign (Mar 11, 2026)
- **PROBLEM:** All roles (User, Store Manager, Org Admin, Super Admin) saw the same cluttered menu. The Administration section was identical for everyone with admin access.
- **FIX — Backend (`/app/backend/permissions.py`):**
  - Complete rewrite with 4 role-based permission templates: `_USER_PERMISSIONS`, `_STORE_MANAGER_PERMISSIONS`, `_ORG_ADMIN_PERMISSIONS`, `_SUPER_ADMIN_PERMISSIONS`
  - `merge_permissions()` now takes a `role` parameter and uses the appropriate template as the base
  - User-specific overrides are still preserved (merged on top of role defaults)
  - Legacy roles (`admin`, `manager`) gracefully fall back to user permissions
- **Permission tiers:**
  - **User:** No Admin section, no Broadcast, no Card Templates, no Leaderboard, no Lead Attribution. Has Date Triggers, Manage Showcase, Activity Reports, Email Analytics enabled.
  - **Store Manager:** Simplified Admin (7 items: Users, Invite Team, Store Profile, Brand Kit, Review Approvals, Showcase Approvals, Contact Tags). Gets Broadcast, Card Templates, Leaderboard.
  - **Org Admin:** Full Admin (12 items: +Admin Dashboard, Review Links, Lead Sources, Integrations, Accounts). Gets Lead Attribution.
  - **Super Admin:** Everything + Internal Administration + Organizations.
- **Features enabled by default for ALL roles:** Date Triggers, Manage Showcase, Activity Reports, Email Analytics
- **FIX — Frontend (`/app/frontend/app/(tabs)/more.tsx`):**
  - Admin section now uses `perm('admin')` instead of hardcoded `isAdmin` check
  - Each admin item has a `permKey` that maps to the backend permission template
  - Items without a matching permission are filtered out
- **FIX — Backend callers updated:** `auth.py` (login), `admin.py` (get/set permissions), `permission_templates.py` (apply template) all pass user's role to `merge_permissions()`
- **Tested:** 11/11 backend tests passed, all frontend verified (iteration 182)

### Customer Performance UI Fix (Mar 11, 2026)
- **PROBLEM:** Period and scope filter pills were overlapping/smashed together, tiles too small. User requested matching the My Performance page design.
- **FIX:** Replaced horizontal `ScrollView` pills with equal-width `flex: 1` buttons in a `flexDirection: 'row'` container. Period filters use gold accent, scope filters use green accent. Added solid background when selected, proper padding (8px), borderRadius 10. Tiles enlarged with bigger rank badges (32px), larger scores (18pt), and more padding.

### Contextual OG Meta Tags for Link Previews (Mar 11, 2026)
- **PROBLEM:** All shared links (cards, review requests, digital business cards) showed the generic "i'M On Social" logo in iMessage/SMS previews. Titles were generic, descriptions were empty or irrelevant.
- **FIX (`/app/backend/routers/short_urls.py`):**
  - **Card links** (congrats, birthday, anniversary, thankyou, welcome, holiday): Now show the customer's actual photo (from object storage `photo_url`) as `og:image`, with contextual titles like "Congrats Forest!", "Happy Birthday Forest!", "Thank You Forest!". Description shows "From [Salesperson] at [Store Name]".
  - **Review request links**: Show the dealership's logo with "Share Your Experience with [Store Name]" title.
  - **Digital business card links**: Show the salesperson's photo with "[Name]'s Digital Card" title.
  - **Showcase/link pages**: Contextual titles with store name.
  - Card type detection expanded from only `congrats_card` to ALL card types: congrats_card, birthday_card, thank_you_card, thankyou_card, holiday_card, welcome_card, anniversary_card.
  - Customer names are properly title-cased.
  - Card lookup checks both `congrats_cards` and `birthday_cards` collections.
  - OG image fallback chain: customer photo → generated card image → store logo → static default.
- **Impact:** Every shared link now shows a personalized, branded preview instead of the generic app logo. Customers see their own photo when receiving a card link, making them far more likely to open it.
- **Tested:** 14/14 backend tests passed (iteration 183).

- **File:** `/app/frontend/app/touchpoints/customer-performance.tsx`
- **Tested:** All frontend verified (iteration 182)

### OG Tag iMessage Fix — Universal HTML Response (Mar 11, 2026)
- **PROBLEM:** User deployed and sent a card via iMessage but the preview still showed the generic iM On Social logo. Two root causes identified:
  1. **create-card page** (`/app/frontend/app/settings/create-card.tsx`) was building the share URL locally as `app.imonsocial.com/congrats/{cardId}` instead of using the backend's tracked short URL. This bypassed the OG handler entirely.
  2. **Short URL handler** relied on bot user-agent detection to serve OG tags. iMessage on iPhone fetches previews with a normal Safari user-agent (not "AppleBot"), so it got a 302 redirect → SPA default OG tags → generic logo.
- **FIX 1 (`create-card.tsx`):** Changed line 122 to use `res.data?.short_url` from the backend response, falling back to the direct URL only if the short URL is unavailable.
- **FIX 2 (`short_urls.py`):** Removed all bot/crawler user-agent detection. ALL requests to short URLs now receive an HTML page with contextual OG meta tags + a `<script>window.location.replace(url)</script>` JS redirect. This ensures:
  - iMessage, WhatsApp, Facebook, etc. always get the OG tags for rich previews
  - Normal browsers redirect instantly via JavaScript (no visible delay)
  - `<noscript>` fallback uses `meta http-equiv="refresh"` for clients without JS
- **Impact:** Every shared link now shows contextual previews in ALL messaging apps, regardless of their user-agent.



### Contact Ownership & Visibility Policy (Mar 12, 2026)
- **Feature:** Implemented clear contact ownership and visibility rules as a core business policy.
- **Ownership Rules (Automatic — no user toggle):**
  - Contacts created in the app (manual, CSV, lead form, etc.) → `ownership_type: 'org'` (belongs to the company)
  - Contacts imported from phone → `ownership_type: 'personal'` (belongs to the user)
  - Users **cannot** override ownership — the "Share with Team" toggle has been removed from both new and edit contact forms
- **Visibility Rules:**
  - **Salespeople/Users:** Only see their OWN contacts (regardless of ownership type)
  - **Managers/Admins:** Default view "My Contacts" shows only their own contacts with full interaction (message, call, send cards)
  - **Managers/Admins:** "Team Contacts" toggle shows all `org` contacts from team members — **view-only** (no action buttons for other users' contacts, salesperson name displayed)
  - **Personal contacts** are NEVER visible to anyone except the owner, not even admins
- **When a salesperson leaves:**
  - `org` contacts can be bulk-transferred to another specific user
  - `personal` contacts stay hidden/archived
- **Backend changes:**
  - `GET /api/contacts/{user_id}` now accepts `view_mode` query param: `mine` (default) or `team`
  - `team` mode enriches contacts with `salesperson_name` field
  - `POST /api/contacts/{user_id}` ownership is forced by source, ignoring any user-provided value
- **Frontend changes:**
  - New "My Contacts / Team Contacts" segmented control on Contacts page (only for managers/admins)
  - Team view: shows eye icon and salesperson name, hides call/text/email buttons for other users' contacts
  - Removed "Share with Team" toggle from contact/[id].tsx (both new and edit modes)
- **Files:** `contacts.py`, `models.py`, `contacts.tsx`, `contact/[id].tsx`, `api.ts`
- **Tested:** 11/11 backend tests passed, all frontend verified (iteration 187)


### Auth Persistence Fix — iOS PWA Session Survival (Mar 12, 2026)
- **Root cause:** iOS kills PWA processes after ~15 min of inactivity. On cold boot, AsyncStorage reads can return null temporarily, causing `loadAuth()` to fail and redirect to login.
- **Fix — Triple-layer auth persistence:** AsyncStorage with retry + IndexedDB backup + Cookie fallback + Retry before redirect
- **Also fixed:** 7 pages reading user from AsyncStorage directly (race condition) → now use Zustand auth store
- **Files:** `authStore.ts`, `index.tsx`, `_layout.tsx` + 7 page files

### UI Consistency — Performance Page Pills (Mar 12, 2026)
- Added "All Time" to My Performance. Made all pills compact, single-line, horizontal scroll across both performance pages.
- **Files:** `performance.tsx`, `customer-performance.tsx`, `tasks.py`


### Data Isolation Fixes — Cross-User Data Bleed (Mar 12, 2026)
- **Issue 1 (Photo Bleed):** Congrats card photos were queried by phone number without `user_id` filter, causing one user's photos to appear on another user's contact. Fixed by adding `user_id` to the congrats card query.
- **Issue 2 (Contact Creation):** `_id` was returned as ObjectId (not string), causing frontend redirect to fail and show "Unknown". Fixed by converting to `str(result.inserted_id)`. Also fixed: `source` field was missing from `ContactCreate` model, so phone_import ownership was never set.
- **Issue 3 (Contact Isolation):** Photos, activity, and tasks are now fully isolated per user. No cross-user data sharing.
- **Issue 4 (Task Bleed):** System-generated tasks (dormant contacts, birthdays, anniversaries) were using `get_data_filter()` which returns org-wide contacts for managers. Fixed to use strict `user_id` filter so tasks are only generated for the user's OWN contacts.
- **Tested:** 12/12 backend tests passed (iteration 188)
- **Files:** `contacts.py`, `tasks.py`, `models.py`


### Personalization Token Inserter — "Smart Merge Tags" (Mar 12, 2026)
- **Feature:** Reusable `PersonalizeButton` component that opens a bottom-sheet dropdown with all available merge tags (first_name, last_name, full_name, phone, email, my_name, my_phone, company, date_sold).
- **Integrated in:** Campaign editor, New campaign, Thread compose, Date triggers, Broadcast messages
- **UX:** Tapping a tag inserts `{tag_key}` at the end of the message. Each tag shows an icon, label, key preview, and gold pill.
- **Files:** `components/PersonalizeButton.tsx` (NEW), `campaigns/[id].tsx`, `campaigns/new.tsx`, `thread/[id].tsx`, `settings/date-triggers.tsx`, `broadcast/new.tsx`
