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

### Session Feb 27, 2026 (Fork 5 - Current)
- **FIX: Share Review Tile** — Opens share modal (Copy Link, SMS, Email, Preview) instead of settings page
- **FIX: API Docs Syntax Error** — Fixed JSX escaping in integrations Docs tab
- **BACKEND: Automated Lifecycle Scan** — APScheduler job at 6 AM UTC daily
- **FEATURE: Personal SMS Mode** — No-Twilio users: auto-send copies message + opens native SMS app + logs everything
- **FIX: iOS SMS Protocol** — `window.location.href` replaces `window.open` for iOS Safari sms: links
- **FIX: Review Star Button in Thread** — Always shows "Send Review Request" with iMOs review link
- **FEATURE: Auto-Send Actions** — Digital card, vCard, review links, congrats card all auto-send in one tap
- **FEATURE: Contact Event Tracking** — All personal SMS actions logged as events: digital_card_sent, review_request_sent, congrats_card_sent, vcard_sent, personal_sms
- **FIX: Contact Detail Quick Actions** — SMS, Email, Review, Card, Congrats all route through inbox thread for full logging. Only Call stays as direct phone dialer.
- **CRITICAL FIX: Email Sending from Inbox** — The simplified `/send/{user_id}` endpoint (which the frontend actually calls) was completely ignoring the `channel` parameter and always sending via Twilio. Emails from inbox Email Mode were never reaching customers. Fixed to properly route: email → Resend, sms_personal → log only, sms → Twilio. Confirmed working — emails now delivered via Resend with "Sent by {name} via iMOs" branding.
- **FEATURE: Activity Reports & Analytics** — Full reports system with date range picker, per-user breakdown, team toggle for managers, daily activity chart, email delivery via Resend, and configurable scheduled reports (daily/weekly/monthly). New endpoints: GET /api/reports/activity/{user_id}, GET /api/reports/activity-daily/{user_id}, POST /api/reports/send-email/{user_id}, GET/PUT /api/reports/preferences/{user_id}.

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
- **UI: Contact Edit Mode Layout** — Moved Basic Info fields to appear right after Tags in edit mode (no more scrolling past Activity Feed)
- **BACKEND: Contact Ownership & Soft Delete System**
  - Contact model: added `ownership_type` (org/personal), `original_user_id`, `status` (active/hidden)
  - Source tracking: manual, csv, phone_contacts, lead_form, referral
  - Imported contacts = personal to uploader; manual contacts = belong to org
  - User deletion now soft-deletes (status: deactivated, 6-month grace period)
  - Org user deactivation: personal contacts hidden, org contacts stay
  - Individual user deactivation: everything retained
  - Reactivation endpoint restores user + unhides personal contacts
  - Contact list queries auto-filter hidden contacts
- **FIX: load_dotenv(override=False)** — Platform env vars now take priority over .env file (fixes 3-day production lockout)
- **BACKEND: Public API v1** (`/api/v1/`) — Full REST API with API key auth for 3rd party CRM integrations
  - Contacts CRUD, search, filter, bulk tag/assign, export
  - Users, Conversations, Messages, Campaigns, Reviews, Tags, Orgs, Stores
  - API key management (generate, list, revoke)
- **BACKEND: Outgoing Webhook System** — 21 event types, HMAC signatures, delivery logging
  - contact.created/updated/deleted, message.sent/received, campaign.enrolled, review.submitted, etc.
  - Webhook subscription management + delivery logs

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

---

## CRITICAL TECHNICAL FLOWS — DO NOT MODIFY WITHOUT READING THIS

These flows have been battle-tested across multiple debugging sessions. Each design decision exists for a specific technical reason. Breaking any step will cause silent failures that are extremely hard to diagnose (messages appear "sent" in the UI but never reach the backend or the recipient).

---

### FLOW 1: Personal SMS (No Twilio Number)

**What it is:** When a user does NOT have a Twilio phone number (`user.mvpline_number` is empty), the app opens the device's native SMS/iMessage app with the recipient's phone number and message body pre-filled. The user taps "Send" in their native SMS app. The CRM still logs everything.

**File:** `/app/frontend/app/thread/[id].tsx` — `handleSend()` function

**Step-by-step flow:**
```
1. User taps Send button in the thread composer
2. handleSend() fires (this is a SYNCHRONOUS user gesture — critical for mobile browsers)
3. Check: isPersonalSMS = (messageMode === 'sms' && !user.mvpline_number)
4. If personal SMS:
   a. Update UI optimistically (show message in conversation immediately)
   b. Build the API payload (conversation_id, content, channel: 'sms_personal')
   c. Fire fetch() with keepalive:true to POST /api/messages/send/{user_id}
      — This logs the message in the backend database
      — keepalive:true ensures the request completes even when browser navigates away
   d. Build sms: URL — sms:{phone}?body={message} (Android) or sms:{phone}&body={message} (iOS)
   e. Create an <a> element, set href to the sms: URL, click it programmatically
      — This opens the native SMS/iMessage app
      — The browser goes to the background
   f. return — exit handleSend immediately, do NOT continue to the await flow
5. User sees their native SMS app with phone + message pre-filled
6. User taps Send in their native SMS app
7. Meanwhile, the keepalive fetch completes in the background — message is logged
```

**WHY each decision matters:**

- `keepalive: true` on fetch — Browser navigates away to SMS app. Without keepalive, the HTTP request is cancelled mid-flight. Without it: Messages appear "sent" in UI but never logged to backend. Inbox empty. Activity feed empty.
- `fetch()` instead of `await messagesAPI.send()` — We cannot await. The page is about to navigate away. await would block until the SMS app opens, then the promise rejects. Without it: Either SMS app doesn't open (if await blocks) or message doesn't log (if await is interrupted).
- Fire API call BEFORE opening SMS app — The fetch request needs to start before the browser navigates away. Even a few milliseconds matters. Without it: Race condition, sometimes logs sometimes doesn't depending on network speed.
- `return` after opening SMS app — The regular await-based flow below would try to run after the page navigated away, causing errors. Without it: Console errors, duplicate messages, or UI glitches when user returns to the app.
- Anchor-click technique (createElement 'a') — Direct `window.location.href = smsUrl` and `window.open(smsUrl)` are blocked by popup blockers on mobile Safari. The anchor-click bypasses this. Without it: SMS app doesn't open. User sees nothing happen. No error shown.
- iOS detection for `&` vs `?` separator — iOS iMessage uses `sms:{phone}&body={msg}`. Android uses `sms:{phone}?body={msg}`. Wrong separator = message body not pre-filled. Without it: SMS app opens but message field is blank.

**DO NOT:**
- Move the sms: link opening to AFTER an await — breaks user gesture chain on mobile Safari
- Move the fetch() to AFTER the sms: link — request may never start
- Use `await messagesAPI.send()` for personal SMS — page navigates away, promise rejects
- Add a setTimeout around the sms: link — breaks user gesture chain
- Remove `keepalive: true` — request will be cancelled when browser backgrounds

---

### FLOW 2: Email Sending (via Resend)

**What it is:** User switches to "Email Mode" in the thread composer and sends a message. The backend sends the email through Resend with branded HTML templates.

**Files:**
- Frontend: `/app/frontend/app/thread/[id].tsx` — `handleSend()` (the regular await flow, NOT the personal SMS early-return)
- Backend: `/app/backend/routers/messages.py` — two email-sending code paths
- Templates: `/app/backend/services/email_service.py` — `build_branded_email_html()`

**Step-by-step flow:**
```
1. User switches to Email Mode (toggle in composer)
2. User types message, taps Send
3. handleSend() fires — isPersonalSMS is false (email mode)
4. Skips the personal SMS early-return block
5. Enters the regular try/catch flow
6. await messagesAPI.send(user._id, { conversation_id, content, channel: 'email' })
7. Backend receives POST /api/messages/send/{user_id} with channel: 'email'
8. Backend looks up contact from conversation — gets contact.email OR contact.email_work
9. Backend calls build_branded_email_html() — generates HTML with store logo, colors, footer
10. Backend calls resend.Emails.send() with the branded HTML
11. Resend returns an email ID — message stored with status: 'sent', resend_id saved
12. Frontend receives success — reloads messages from backend
```

**CRITICAL: The backend has TWO email-sending code paths:**
- Path 1: Lines ~220-270 in messages.py (the main `/messages/{conversation_id}/send` endpoint)
- Path 2: Lines ~890-930 in messages.py (the `/messages/send/{user_id}` endpoint — THIS is what the frontend actually calls)

Both paths MUST:
- Check `contact.get('email') or contact.get('email_work')` (not just `email`)
- Use `build_branded_email_html()` for consistent branding
- Store the `resend_id` from the Resend response
- Set `channel: 'email'` on the stored message

**DO NOT:**
- Only check `contact.email` — some contacts only have `email_work`
- Hardcode "from" address — use `noreply@imosapp.com` from env/config
- Skip the branded template — user expects branded emails with store logo
- Remove either code path thinking it's duplicate — frontend uses `/send/{user_id}`, other integrations may use the other

---

### FLOW 3: Action Tiles — Pre-fill Pattern

**What it is:** Inside a conversation thread, action tiles (Share Review Link, Share Business Card, Share Landing Page, Templates, Congrats Card) pre-fill the message composer instead of auto-sending. The user then taps Send to trigger the personal SMS or email flow.

**File:** `/app/frontend/app/thread/[id].tsx`

**Pattern:** Every action tile handler calls `setMessage(composedMessage)` — NEVER `handleSend(msg)` directly.

```
User taps action tile — setMessage("Hey {name}! Here's my review link: {url}")
— Message appears in composer input field
— User can review/edit the message
— User taps Send — triggers handleSend() — personal SMS or email flow
```

**WHY pre-fill instead of auto-send:**
1. Auto-send via `handleSend()` from a tile click is inside a UI handler, NOT a direct user tap on the Send button. Mobile browsers may not treat this as a "user gesture" for the sms: protocol.
2. Auto-send via `setTimeout(() => handleSend(...))` definitely breaks user gesture chain.
3. Pre-fill gives the user control — they can edit the message or change the mode before sending.
4. Pre-fill ensures the Send button tap is the user gesture that triggers the sms: link.

**DO NOT:**
- Change any action tile from `setMessage(msg)` to `handleSend(msg)` — breaks SMS opening on mobile
- Add `setTimeout` before `handleSend` — breaks user gesture chain
- Auto-send from a modal close handler — not a user gesture

---

### FLOW 4: Contact Detail — Thread Navigation

**What it is:** Quick action buttons on the contact detail page navigate to the thread page with URL parameters that tell the thread what to do.

**File:** `/app/frontend/app/contact/[id].tsx` — `handleQuickAction()`

**URL pattern:**
```
/thread/{contact_id}?contact_name={name}&contact_phone={phone}&contact_email={email}&mode={action}
```

**Modes:**
- `mode=sms` — Opens thread in SMS mode, cursor in composer
- `mode=email` — Opens thread in Email mode
- `mode=review` — Opens thread, then shows review links modal after 800ms
- `mode=card` — Opens thread, then shows business card modal after 800ms
- `mode=congrats` — Opens thread, then shows congrats card modal after 800ms

**The `contact_phone` parameter is CRITICAL.** Without it, `contactPhone` in the thread page is empty, the `if (isPersonalSMS && contactPhone)` check fails, and the SMS app never opens. The message still gets logged but the user experience breaks silently.

---

### FLOW 5: Smart Contact Matching

**What it is:** When sending a share (Review, Card, Congrats) with recipient info, the system finds or creates a contact by matching the last 10 digits of phone or email address.

**Files:**
- Backend: `/app/backend/routers/contact_events.py` — `find-or-create-and-log`
- Frontend: `/app/frontend/hooks/useContactMatch.ts` + `/app/frontend/components/ContactMatchModal.tsx`

**Matching logic:**
```
1. Normalize phone to last 10 digits
2. Search contacts where last 10 digits of stored phone match
3. If no phone match, search by email (checks both email and email_work fields)
4. If match found AND name matches — log event, return contact
5. If match found AND name DIFFERENT — return needs_confirmation, show modal
6. If no match — create new contact, log event, return contact
```

**DO NOT:**
- Match on full phone number — formatting varies (+1, spaces, dashes)
- Only check `email` field — `email_work` was added for work emails
- Skip the name confirmation modal — users need to know when merging contacts
- Log events without a contact_id — all events MUST be tied to a contact

---

### FLOW 6: Dialer — Native Phone Call

**What it is:** User dials a number on the in-app dialer and taps the call button. The app opens the native phone app and logs the call event.

**File:** `/app/frontend/app/(tabs)/dialer.tsx` — `handleCall()` function

**Step-by-step flow:**
```
1. User enters a phone number or taps a recent contact on the dialer
2. User taps the green Call button
3. handleCall() fires
4. Log the call event with fetch+keepalive to POST /api/contacts/{user_id}/find-or-create-and-log
   — Uses keepalive so the request completes even when browser navigates to phone app
5. Open native phone app via tel: protocol using anchor-click technique
6. Phone app opens, user places the call
7. Call event is logged in the contact's activity feed
```

**Also applies to:** Contact detail page call buttons (`/app/frontend/app/contact/[id].tsx`) — both the quick action call button and the phone number chip use anchor-click.

**DO NOT:**
- Use `await api.post()` after opening `tel:` — browser navigates away, await never resolves
- Use `Linking.openURL('tel:...')` on web — unreliable on mobile Safari, use anchor-click
- Remove `keepalive: true` from the fetch — call events won't be logged

---

### Viewport & Mobile Browser Rules

**File:** `/app/frontend/app/+html.tsx`

The viewport meta tag MUST include `maximum-scale=1, user-scalable=no`:
```html
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no, shrink-to-fit=no" />
```

**Why:** iOS Safari expands the viewport when ANY element overflows horizontally or when focusing an input with font-size < 16px. Once expanded, the viewport stays wide even after navigating to other pages. The user has to pinch-to-zoom to fix it.

**Global CSS rule (in +html.tsx):**
```css
input, textarea, select { font-size: 16px !important; }
```
This prevents iOS Safari's auto-zoom-on-focus for small text inputs.

**DO NOT:**
- Remove `maximum-scale=1` from the viewport tag
- Remove the global 16px font-size rule
- Put two input fields side-by-side on mobile without testing (use stacked vertical layout)
- Use `width: 100%` with `gap` in a flex row without `minWidth: 0` on children

---

### Deployment & Environment Rules

- **Preview** (Emergent pod): Database = localhost:27017 / `imos-admin-test_database`. For development & testing only.
- **Production** (Emergent deploy): Database = MongoDB Atlas (set via platform env vars). For live customer use.
- The preview and production databases are COMPLETELY SEPARATE. Changes in one do not affect the other.
- To get code changes to production: User must click "Deploy" in Emergent. Code changes are NOT automatically deployed.
- `load_dotenv(override=False)` means platform env vars take priority over `.env` file. Changing to `override=True` will cause production lockout.

---

### Change Log — Feb 27, 2026 (Fork 8)

**Bug: Personal SMS messages not logging to inbox/activity**
- Root cause: `sms:` link opened BEFORE API call, but browser navigated away before `await messagesAPI.send()` could complete. Messages appeared sent but never reached the backend.
- Fix: Replaced `await` with `fetch()` + `keepalive: true`. API call starts, then SMS app opens, request completes in background.
- Lesson: When browser navigates away (sms:, tel:, mailto:), pending `await` will never resolve. Use `fetch` with `keepalive: true`.

**Bug: Email not checking `email_work` field**
- Root cause: Both email code paths only checked `contact.get('email')`.
- Fix: Changed to `contact.get('email') or contact.get('email_work')`.

**Bug: iOS Safari viewport expanding beyond phone screen**
- Root cause: `+html.tsx` missing `maximum-scale=1, user-scalable=no`.
- Fix: Added viewport attributes + global 16px font-size for inputs.

**Change: Share modal inputs stacked vertically**
- Phone/Email were side-by-side (50/50). Changed to 3 stacked rows to prevent overflow.

**Change: iMOs Review Link pre-fills instead of auto-sending**
- Was `handleSend(reviewMsg)` in setTimeout. Now `setMessage(reviewMsg)` matching all action tiles.

---

### FLOW 7: Photo Management — Thumbnails vs High-Res

**Architecture:**
- `photo_thumbnail`: Used EVERYWHERE in the UI (contact lists, avatars, activity feeds, conversation headers)
- `photo` (high-res): Stored ONLY for the congrats card flow, which pushes the original to a third party. High-res does NOT need to travel with the contact record.
- The contacts list API intentionally EXCLUDES the `photo` field (too heavy for lists)

**Requirements:**
- When a user uploads a new photo, the THUMBNAIL must be regenerated and persisted. The UI reads thumbnails, not originals.
- Users must be able to: upload, delete, and ROTATE photos (some go landscape/sideways)
- After changing a photo, it must persist permanently — not revert to the old one
- Rotation fix must apply to both the thumbnail and any stored version

**Current known issue:** Photo appears to revert after editing. Likely cause: thumbnail not being regenerated when a new photo is uploaded, so the old cached thumbnail keeps showing.

**Status:** NOT YET FIXED — documented for next work session. Do not touch photo code without understanding the full thumbnail/high-res split.

---

### FLOW 8: Tracking & Analytics Architecture — EVERYTHING IS TRACKED

**Core principle:** Every single user action that touches a contact MUST create BOTH:
1. A `contact_event` record (powers the contact's activity feed AND the reporting aggregations)
2. A `message` record (powers the inbox conversation thread)

**What gets tracked (non-exhaustive):**
- SMS sent (personal or Twilio) → contact_event + message
- Email sent → contact_event + message
- Digital card shared → contact_event
- Review link shared → contact_event
- Congrats card sent → contact_event
- Call placed → contact_event
- Link clicks → tracked via short URLs, feed into click rates

**Where tracking data appears:**
1. **Contact Activity Feed** — reads from `contact_events` filtered by contact_id
2. **Inbox Conversations** — reads from `messages` filtered by conversation_id
3. **Reports / Analytics** — aggregates from BOTH `messages` (SMS/email counts) AND `contact_events` (card/review/congrats counts)
4. **Leaderboard / My Rankings** — aggregates from `contact_events` by user_id
5. **Manager Dashboard** — aggregates across all users in the org

**If ANY action fails to create a contact_event, it breaks:**
- The contact's activity trail
- The user's performance stats
- The leaderboard rankings
- The manager's visibility into team activity
- Click rate analytics

**This is the #1 most important thing in the system.** Every feature, every button, every action must end with a logged event. No exceptions.

---

## Critical Production Notes
- `backend/server.py` uses `load_dotenv(override=False)` — This is CRITICAL. `override=False` means deployment platform env vars (Kubernetes) take priority over the .env file. This was changed from `override=True` which was causing the .env localhost URL to stomp on the production Atlas URL, locking the user out for 3 days. NEVER change back to override=True.
- Frontend uses relative `/api` paths for web builds
- **MONGO_URL in preview .env MUST be mongodb://localhost:27017**
- **NEVER switch .env MONGO_URL to production Atlas in the preview pod**
- **The deployment platform's environment variables handle production**
- If login breaks after a restart, check MONGO_URL in backend/.env FIRST
- **DB_NAME = `imos-admin-test_database` — THIS IS THE REAL PRODUCTION DATABASE. Do NOT rename or change it. The name is misleading but confirmed correct by the owner.**
- **Production MONGO_URL does NOT contain a database name in the path — the app relies on the DB_NAME env var to connect to the correct database**

### Session Feb 27, 2026 (Fork 6 - Current)
- **FIX: Email Delivery Verified End-to-End** — Confirmed emails are delivered via Resend from both API and Inbox UI. Three test emails sent successfully to forestward@gmail.com with unique Resend IDs.
- **FIX: Brand Context ObjectId Error** — Fixed `get_brand_context()` in `utils/email_template.py` to handle non-ObjectId IDs (e.g., `org_001`) by falling back to string-based lookups for store_id, org_id, and partner_id. This eliminates the `'org_001' is not a valid ObjectId` error in branded email templates.
- **NEW: Admin Docs Hub** — Built comprehensive Company Docs section under Admin with:
  - 8 seeded documents: Cyber Security Policy, Company Policy & Code of Conduct, Terms of Service, Privacy Policy, Data Retention Policy, Security Awareness Training, Platform Onboarding Guide, Integration & API Documentation
  - Slide-by-slide document viewer with progress bar, dot navigation, Previous/Next buttons
  - Category filters (Security, Company Policy, Legal, Training, Integrations) and search
  - Markdown rendering (bold text), tip boxes (yellow), warning boxes (red)
  - Backend: `/api/docs/` router with list, categories, single doc, and seed endpoints
  - Frontend: `/admin/docs` hub + `/admin/docs/[id]` viewer
  - Accessible from More > Administration > Company Docs (admin-only)
- **NEW: Smart Contact Matching System** — Every outbound action now creates/matches/merges contacts:
  - Match by last 10 digits of phone number or email (personal/work)
  - Name mismatch prompts user: Use Existing, Update Name, or Create New
  - Dual email support: personal + work merged under one contact
  - Flows updated: Share Review, Congrats Card, Digital Card share, Dialer
  - All actions logged as contact events (review_shared, congrats_card_sent, digital_card_shared, call_placed)
  - SMS pre-fills phone number + message body using anchor-click technique
  - Dialer opens native phone app via `tel:` protocol and logs call activity

### Session Feb 27, 2026 — Mobile Viewport Fix
- **CRITICAL FIX: iOS Safari Viewport Expansion** — The `+html.tsx` Expo template was missing `maximum-scale=1, user-scalable=no` in the viewport meta tag. iOS Safari would expand the viewport when content overflowed or when focusing small-font inputs, requiring pinch-to-zoom.
- **FIX: Share Modal Input Layout** — Changed Name/Phone/Email fields from side-by-side (50/50 row) to 3 vertically stacked rows across all share modals (Share Review, Share My Contact, Congrats Card). Eliminates horizontal overflow on narrow screens.
- **FIX: iOS Input Auto-Zoom** — Added global CSS to set input/textarea/select font-size to 16px, preventing iOS Safari's auto-zoom on focus behavior.

## Prioritized Backlog
### P0 (Critical)
- All critical issues resolved. Production email delivery verified. Personal SMS flow fixed.

### P1
- Refactor auth to use hashed passwords (bcrypt)
- Lead Notification System Phase 2 (push notifications)
- Voice Help Assistant backend
- Gamification leaderboard for salespeople touch points
- Campaign flow: Twilio assigned numbers / shared inboxes / task-based SMS sending with templates & AI suggestions

### P2
- Full Twilio integration (currently MOCK)
- WhatsApp integration
- Code cleanup (~80 files)
- Training Hub content
- Inventory Management Module
- React Hydration Error #418
- Mobile app tags sync
- Leaderboard toggle verification
