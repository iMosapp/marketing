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

### Session Feb 28, 2026 (Fork 8 - Current)
- **FEATURE: Contact Activity Feed Revamp** — Fixed incorrect relative timestamps ("in about five hours") by replacing `formatDistanceToNow` with absolute `format()` from date-fns. Events now show "Yesterday at 10:04 PM", "Feb 27 at 7:28 PM" etc. Added expand/collapse per event (chevron toggle), initial 5-event limit with "Show All X Events" button, and fallback title labels for events with null titles (e.g., "Email Sent" instead of blank).
- **FEATURE: Inbox Swipe Gestures (Web)** — Built `WebSwipeableItem` component using pointer events for web-compatible drag/swipe. Left swipe reveals Flag + Task actions; right swipe reveals Tag + Archive. Added `flagConversation` API, task creation from swipe, and a tag picker modal.
- **ENHANCEMENT: Flag Indicator** — Flagged conversations now show an orange flag icon next to the contact name in the inbox list.
- **BACKEND: Flag Support** — Added `flagged` to allowed fields in `update_conversation` endpoint.
- **BUG FIX: Contact Photo Reverting** — Root cause: `update_contact` endpoint never called `_process_photo()` when saving, so `photo_thumbnail` stayed stale while `photo` got overwritten. Fix: the PUT update endpoint now detects base64 photo data, generates a 96x96 avatar thumbnail (~3-5KB), stores high-res in separate `contact_photos` collection, and removes raw photo from contacts to keep queries fast.
- **ENHANCEMENT: EXIF Auto-Rotation** — Added `ImageOps.exif_transpose()` to `_process_photo()` so phone photos taken in portrait/landscape display correctly (not sideways). Works for all photo paths: contact update, dedicated upload, and congrats cards.
- **NOTE: Congrats card photos preserved** — Full-resolution photos (1080px, quality 92) still stored in `contact_photos` collection for print-quality third-party use.
- **FEATURE: Full Photo Viewer** — Tapping a contact's photo opens a full-screen modal loading the 1080px high-res version. Sharp on iPhone Pro Max.
- **FEATURE: Voice Notes on Contacts** — Record voice memos (up to 2 min) on any contact. Audio stored in Emergent object storage, auto-transcribed via OpenAI Whisper. Multiple notes per contact, most recent prominent, older notes behind "Show All". Each note logged in activity feed with green mic icon. Transcripts are searchable text.
- **BUG FIX: Inbox Email Sending** — Root cause: contact email fields containing Python `None` or string `"None"` were passing truthy checks but failing at Resend. Added `_clean_email()` validation function with regex email format check. Applied to ALL 4 email resolution paths in `messages.py` (conversation list, conversation info, primary send, simplified send). Also sanitizes `"null"`, `"N/A"`, `"undefined"` strings.
- **FEATURE: AI Relationship Intel** — On-demand GPT-5.2 powered briefing on contact detail page. Gathers all messages, events, voice notes, tasks, and contact metadata. Generates structured summary with Quick Take, Key Facts, Communication Patterns, Personal Notes, and Suggested Talking Points. Cached in `contact_intel` collection for instant re-display with a Refresh button to regenerate.
- **FEATURE: 3-Level Gamification Leaderboard** — Store-level (users in same account), Org-level (stores competing), Global (anonymized cross-org). Category breakdowns: Digital Cards, Reviews, Congrats, Emails, SMS, Voice Notes. Month/year filters, Gold/Silver/Bronze badges for top 3. Expandable user cards with per-category stats, team summary footer. Accessible from My Account via "Leaderboard" quick action (replaced Share Review link). Backend aggregates `contact_events` collection with MongoDB pipelines.
- **FEATURE: Activity Feed Search** — Search bar in the activity feed filters events client-side by title, description, or event type. Clear button resets. Shows "No matching events" when empty.
- **FEATURE: Notes in Activity Timeline** — When contact notes are saved/updated, a `note_updated` event is logged to the activity feed with an orange document-text icon. Shows the note content as the event description, creating a chronological history of note changes.

### Session Feb 28, 2026 (Fork 7)
- **CRITICAL FIX: 5-Point Email Flow Audit** — Traced every single entry point that leads to the inbox thread and fixed all disconnects:
  1. Mode initialization no longer silently falls back to SMS when `contact_email` URL param is empty
  2. `email_work` field checked everywhere (contact detail, conversation info, thread page)
  3. Card/Review/Congrats action modes respect user's preferred message mode instead of forcing SMS
  4. `handleSend` now ensures conversation exists before sending (prevents 404 from contact ID)
  5. ALL navigation paths (inbox, contact detail, search, tasks) now pass `contact_email`
- **VERIFIED: CTR Analytics** — Click-Through Rate display on "My Activity" dashboard confirmed working with per-channel (SMS/Email) breakdown.
- **FEATURE: Operations Manual** — Created comprehensive 23-slide in-app document covering full project scope, every feature, technical architecture, DO-NOT-TOUCH patterns, database schema, integrations, and deployment guide. Lives in Company Docs > Operations Manual.
- **FEATURE: NDA (Super Admin Only)** — Created 11-slide Non-Disclosure Agreement with role-based access control. Only visible to super_admin users. Added `required_role` field to docs system for document-level access control.
- **FEATURE: Digital NDA Signing System** — Full signing flow: Admin fills name/title + draws signature on canvas, enters recipient info (name, email, phone), creates shareable link. Recipient verifies identity (email+phone), reads full 9-section NDA, fills their info (name, title, company), draws signature. Both parties get confirmation emails. NDAs stored in MongoDB, manageable from `/admin/nda` with status tracking (Pending → Viewed → Signed).
- **FEATURE: Signed Documents Hub** — Unified "Signed Documents" category in Company Docs that aggregates all executed documents across types: NDAs, Partner Agreements, and Quotes. Each card shows type badge, counterparty info, signed date, and links to the detail view.
- **ENHANCEMENT: Doc Access Control** — Backend docs list and get endpoints now filter by user role. Documents with `required_role: "super_admin"` are hidden from org_admin, store_manager, and user roles.

### Session Feb 27, 2026 (Fork 6)
- **FIX: Personal SMS & Dialer Regression** — Implemented `fetch` with `keepalive: true` for reliable logging when navigating away
- **FIX: Mobile Viewport Overflow** — Added `maximum-scale=1, user-scalable=no` to viewport meta tag
- **FIX: Leaderboard Visibility** — Removed faulty `isIndependent` guard hiding tiles
- **FEATURE: My Activity Dashboard** — User analytics with time filters on My Account page
- **FEATURE: CTR Analytics** — Click-through rates for shared links by channel
- **DOCS: CHANGE_RULES.md** — Critical patterns documented to prevent regressions

### Session Feb 27, 2026 (Fork 5)
- **FIX: Share Review Tile** — Opens share modal (Copy Link, SMS, Email, Preview) instead of settings page
- **FIX: API Docs Syntax Error** — Fixed JSX escaping in integrations Docs tab
- **BACKEND: Automated Lifecycle Scan** — APScheduler job at 6 AM UTC daily
- **FEATURE: Personal SMS Mode** — No-Twilio users: auto-send copies message + opens native SMS app + logs everything
- **FIX: iOS SMS Protocol** — `window.location.href` replaces `window.open` for iOS Safari sms: links
- **FIX: Review Star Button in Thread** — Always shows "Send Review Request" with iMOs review link
- **FEATURE: Auto-Send Actions** — Digital card, vCard, review links, congrats card all auto-send in one tap
- **FEATURE: Contact Event Tracking** — All personal SMS actions logged as events: digital_card_sent, review_request_sent, congrats_card_sent, vcard_sent, personal_sms
- **FIX: Contact Detail Quick Actions** — SMS, Email, Review, Card, Congrats all route through inbox thread for full logging. Only Call stays as direct phone dialer.
- **CRITICAL FIX: Email Sending from Inbox** — The simplified `/send/{user_id}` endpoint was ignoring the `channel` parameter. Fixed to properly route: email → Resend, sms_personal → log only, sms → Twilio.
- **FEATURE: Activity Reports & Analytics** — Full reports system with date range picker, per-user breakdown, team toggle for managers, daily activity chart, email delivery via Resend, and configurable scheduled reports.
- **FEATURE: White-Label Branded Emails** — Dynamic HTML email templates using store's branding (logo, colors, custom footers).

### Session Feb 27, 2026 (Fork 4)
- **UI: More Page Tile Rearrangement** — My Digital Card, Congrats Card, Share Review as top 3 tiles
- **UI: My Account Quick Actions Cleanup**
- **UX: Accordion behavior on More page**
- **UI: Inbox Redesign** — Card-based conversation list, timeline-style thread messages
- **BACKEND: Contact Ownership & Soft Delete System**
- **BACKEND: Public REST API & Webhooks** for third-party CRM integration
- **BACKEND: Internal User Lifecycle Engine** with automated daily schedule

## Known Issues

### P0 (Critical)
- None currently

### P1 (High)
- ~~Contact Photo Reverting~~ — **FIXED in Fork 8**

### P2 (Low)
- React Hydration Error #418
- Mobile app `tags` data sync
- Leaderboard toggle not fully tested
- `GET /api/users/{user_id}` returns 405 (minor)

## Upcoming Tasks (Priority Order)

### P0
- **Gamification & Leaderboards** — Full implementation with role-based visibility

### P1
- **Clean Production Database** — Set up for first live customer launch
- **AI-Powered Outreach** — Suggest follow-up messages when `sold` tag applied
- **Auth Refactor** — Migrate to hashed passwords (bcrypt)
- **Push Notifications** — Mobile push for lead notifications

### P2
- TestFlight build guidance
- Full Twilio integration (live mode)
- WhatsApp integration
- Training Hub content
- Inventory Management Module

## Critical Technical Flows

### Email Sending from Inbox
1. User opens thread (from inbox or contact page)
2. `contact_email` passed as URL param (or loaded via `loadContactInfo` API fallback)
3. User clicks "Switch to Email" → mode switch handler checks `hasEmail` → if false, does API fallback check
4. User types message → clicks Send → `handleSend()` with `channel: 'email'`
5. Frontend calls `POST /api/messages/send/{user_id}` with `{ conversation_id, content, channel: 'email' }`
6. Backend routes to Resend, builds branded HTML email, sends, logs contact_event

### Personal SMS Flow
1. User without Twilio number types message in SMS mode
2. `handleSend()` detects `isPersonalSMS` = true
3. Uses `fetch` with `keepalive: true` to log message (survives browser navigation)
4. Creates `<a>` element with `sms:` protocol and clicks it
5. Native SMS app opens with message pre-filled

### Key Technical Patterns
- **`keepalive: true`** for any fetch that precedes browser navigation (sms:, tel:)
- **Anchor click technique** for protocol links on mobile Safari
- **Both email fields checked**: `contact.get('email') or contact.get('email_work')`
- **All contact data in navigation params**: name, phone, email, photo

## Credentials
- **Super Admin:** forest@imosapp.com / Admin123!

## 3rd Party Integrations
- **Resend:** Transactional emails (LIVE)
- **MongoDB Atlas:** Primary database
- **Twilio:** SMS (MOCK mode)
- **OpenAI:** Jessi AI assistant
- **Emergent Integrations:** Object storage
