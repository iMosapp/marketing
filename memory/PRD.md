# i'M On Social — Product Requirements Document

## Original Problem Statement
Full-stack Relationship Management System (RMS/CRM) for sales teams. Key goals: ease of use ("easy button"), activity tracking, gamification, AI-powered outreach, and multi-channel communication. The user envisions a "turnkey" system that minimizes personal involvement in onboarding and training.

## Core Architecture
- **Frontend:** React Native (Expo) web app
- **Backend:** FastAPI (Python)
- **Database:** MongoDB
- **Object Storage:** Emergent Object Storage (images, media)
- **Email:** Resend via `notifications@send.imonsocial.com`
- **SMS:** Twilio (MOCKED)
- **AI:** OpenAI (Jessi assistant)

---

## What's Been Implemented

### Email System Overhaul (Mar 2026)
- **Sender address:** Changed from `noreply@imonsocial.com` to `notifications@send.imonsocial.com` (verified subdomain, protects main domain reputation)
- **Reply-To headers on ALL 14 email sends:**
  - User-to-customer messages → reply goes to that user's email (e.g., `forest@imonsocial.com`)
  - System emails (welcome, reset, invites, reports, NDA) → reply goes to `support@imonsocial.com`
- **Fixed 2 hardcoded NDA emails** and **1 scheduler email** that weren't reading from `.env`
- **Architecture:** Google Workspace handles human email, Resend handles automated email, subdomain isolation protects deliverability

### Facebook-Style Photo Gallery (Mar 2026)
- **Thumbnail grid** loads instantly — tiny WebP thumbnails (~2-6KB each) instead of 18 full-size images
- **Horizontal swipe viewer** — tap any thumbnail → full-screen FlatList with snap-to-page (Instagram-like)
- **"Set as Profile Photo"** button visible in full-screen view for any non-profile photo
- **Photo counter badge** ("1 of 11") while swiping
- **Grid/viewer toggle** — easy navigation between grid and full-screen
- **Backend:** `photos/all` endpoint returns both `thumbnail_url` and `url` per photo
- **Auto-migration:** Base64 congrats/birthday card photos lazily migrated to WebP object storage on first gallery load

### Full-Resolution Photo Support (Mar 2026)
- **`hires_images` toggle** on org settings — admin can enable per-organization
- **When enabled:** uploads store raw uncompressed original alongside compressed WebP
- **Upload response includes `raw_url`** (full-res) — only when flag is ON
- **Cleanup flow:** `raw_url` is ephemeral (only returned at upload time, not persisted in DB). After sending full-res to partner via API/webhook, discard the URL. Compressed WebP stays for in-app display.
- **Admin UI:** Toggle on org detail page → "Full-Resolution Photos" ON/OFF
- **Model:** `OrganizationCreate` includes `hires_images: bool = False`

### CDN-Like Image Caching Layer (Mar 2026)
- **In-memory LRU cache** (200MB, configurable via `IMAGE_CACHE_MB` env var): hot images served from RAM in <1ms
- **ETag + 304 Not Modified:** browsers with cached images get zero-body responses (~0.7ms)
- **Immutable cache headers** (`Cache-Control: public, max-age=31536000, immutable`): browser never re-validates (UUID-based paths)
- **Cache warming on upload:** newly uploaded images are pre-cached in RAM immediately
- **Cache stats:** `GET /api/images/cache-stats` for monitoring
- **Performance:** cached fetches ~0.9ms, 304 responses ~0.7ms

### Image Pipeline Optimization (Mar 2026)
- **All originals auto-compressed to WebP** (1200px max, 85% quality) — tested 94% size reduction (94KB JPEG → 6KB WebP)
- **Thumbnails** (200x200 WebP) and **avatars** (80x80 WebP) generated on every upload
- **MMS media** moved from base64-in-MongoDB to compressed WebP in Object Storage
- **Frontend:** `expo-image` (disk + memory caching, transitions) on inbox, thread, contact pages
- **`OptimizedImage` component** at `/app/frontend/components/OptimizedImage.tsx`

### Existing Image Migration (Mar 2026)
- **Migration script:** `/app/backend/scripts/migrate_images.py`
- **Forest Ward's profile photo:** 2.9MB base64 blob in MongoDB → 99KB WebP in Object Storage (96% reduction). Was being sent in EVERY API response.
- **Store logo:** 210KB PNG → 33KB WebP (84% reduction)
- **Contact thumbnails:** base64 blobs → WebP in Object Storage

### Production URL Fix (Mar 2026)
- **Root cause:** Deployment platform auto-overrides `APP_URL` with staging domain
- **Backend fix:** Added `PUBLIC_FACING_URL` env var (takes priority over `APP_URL`). Updated: `short_urls.py`, `auth.py`, `team_invite.py`, `app_directory.py`, `nda.py`
- **Frontend fix:** Eliminated ALL `window.location.origin` usage across 13+ files. All customer-facing URLs use `process.env.EXPO_PUBLIC_APP_URL || 'https://app.imonsocial.com'`

### Inbox Refresh Fix (Mar 2026)
- Added `useFocusEffect` from `expo-router` to `inbox.tsx`
- Conversations reload every time user focuses the Inbox tab
- Pull-to-refresh also correctly triggers `loadConversations`

### Photo URL Fix in SMS Composer (Mar 2026)
- Fixed photo attachments sending raw relative API paths in SMS body
- Now converts to absolute production URLs before inserting into message content

### Activity Event Type Resolution Fix (Mar 2026)
- **Root cause:** Backend event type detection used `/api/s/` as a catch-all that incorrectly classified ALL short URL messages as `congrats_card_sent` — e.g., digital business cards, review invites, showcases all showed as "Congrats Card Sent" in the activity feed
- **Fix (3 layers):**
  1. **Explicit `event_type` from frontend:** Added `event_type` field to `MessageCreate` model. Frontend now passes the correct event type when composing messages from quick actions (digital card, review invite, showcase, link page, vCard)
  2. **DB-lookup fallback:** When no explicit event_type is provided, the backend extracts the short code from `/api/s/{code}` URLs in the message, looks up the `link_type` from the `short_urls` collection, and maps it to the correct event type via `_LINK_TYPE_TO_EVENT`
  3. **Keyword fallback:** For messages without short URLs, keyword-based detection (e.g., "congrats", "birthday") still works
- **Frontend changes:** Both `contact/[id].tsx` (composerEventType state) and `thread/[id].tsx` (pendingEventType state) now track and pass event_type through the send API
- **Result:** Activity feed now accurately shows "Digital Card Shared", "Review Invite Sent", etc. instead of all showing "Congrats Card Sent"

### Photo Gallery v2 Rewrite (Mar 2026)
- **Issues fixed:** 1) Black screen when opening gallery (photos didn't load for legacy contacts), 2) X close button hidden under iOS status bar
- **New gallery features:**
  - `resolvePhotoUrl()` helper converts relative image paths (`/api/images/...`) to absolute URLs for native mobile
  - Full-screen swipeable viewer uses `Dimensions.get('window')` for explicit sizing (fixes FlatList height collapse)
  - Gallery top bar has iOS safe area padding (`paddingTop: 56` on iOS)
  - Modern layout: close button (top-left), photo counter (center), upload button (top-right)
  - Bottom bar: photo label, date, Grid button, Set as Profile button (for non-profile photos)
  - Thumbnail grid view with type labels
  - Empty state with "Add Photo" CTA
- **Files changed:** `frontend/app/contact/[id].tsx` (gallery modal rewrite + resolvePhotoUrl + Dimensions import)

### Previous Session Work
- **Persistent Login:** HTTP-only cookies (`imos_session`) for indefinite sessions
- **Dynamic Share Previews:** Short URL redirector serves dynamic OG tags for branded link previews
- **Training Hub V2:** Role-based content filtering, White Label Partner track, admin CRUD interface
- **Contact Page Bug Fixes:** Photo attachments, composer text expansion, auto-refresh removal, call logging, review link tracking, referral count ticker
- **Home Screen Fixes:** Notification bell modal (z-index), action items navigation, quick action contact picker flow
- **Carrier-Agnostic Messaging:** Personal SMS fallback with native SMS app, all activity logged as `contact_events`
- **White-Label Emails:** Dynamic HTML templates with store logo, brand colors, custom footers
- **Reporting & Activity:** 14+ metrics, date filters, scheduled email delivery
- **Admin Onboarding Wizard, Partner Portal, First-Login Profile Completion**
- **Public REST API & Outgoing Webhooks** for third-party CRM integrations
- **Soft-Delete System** for users and data retention policy for contacts
- **Internal Lifecycle Engine** (automated daily via `apscheduler`)

---

## Key API Endpoints

### Images
- `POST /api/images/upload` — Upload image (auto-compresses to WebP, returns `raw_url` if org has `hires_images`)
- `POST /api/images/upload-base64` — Upload base64 image
- `GET /api/images/{path}` — Serve image (CDN-cached, ETag, immutable)
- `GET /api/images/cache-stats` — Cache monitoring
- `DELETE /api/images/raw/{path}` — Flag raw original for cleanup

### Contacts
- `GET /api/contacts/{user_id}/{contact_id}/photos/all` — All photos with `thumbnail_url` + `url`
- `PATCH /api/contacts/{user_id}/{contact_id}/profile-photo` — Set profile photo

### Messages
- `POST /api/messages/send/{user_id}` — Send message (handles email, SMS, personal SMS channels; accepts optional `event_type` for accurate activity tracking)
- `POST /api/messages/send/{user_id}/{conversation_id}` — Send message (Pydantic endpoint, also accepts `event_type`)
- `POST /api/messages/send-mms/{user_id}` — Send MMS (now uses object storage, not MongoDB)

### Auth
- `POST /api/auth/login` — Login (sets `imos_session` cookie)
- `GET /api/auth/me` — Restore session from cookie
- `POST /api/auth/logout` — Clear session

### Short URLs
- `POST /api/s/create` — Create short URL (uses `PUBLIC_FACING_URL`)
- `GET /api/s/{short_code}` — Redirect with dynamic OG tags

---

## Pending Issues
- P0: Production email delivery — user needs to verify `RESEND_API_KEY` and test with new `notifications@send.imonsocial.com` sender
- P2: React Hydration Error #418
- P2: Mobile app `tags` data sync

## Upcoming Tasks
1. (P0) **Gamification & Leaderboards** — leaderboards for users and managers based on activity tracking data
2. (P1) **Automated Welcome Emails** — after user creation, send credentials
3. (P1) **Quoting System** — flexible quoting with discounts and partner commissions
4. (P1) **AI-Powered Outreach** — on `sold` tag, AI suggests contextual follow-up message

## Future/Backlog
- Extend `expo-image` to remaining pages (settings, admin, etc.)
- Auth refactor (bcrypt password hashing)
- Push notifications (Lead Notification System Phase 2)
- Voice Help Assistant backend
- Full Twilio integration (currently MOCKED)
- WhatsApp Integration
- Inventory Management Module
- Code cleanup (~80 files)

---

## Environment & Deployment

### Key Credentials
- Super Admin: `forest@imosapp.com` / `Admin123!`

### Email Configuration
- **Sender:** `SENDER_EMAIL=notifications@send.imonsocial.com`
- **Reply-To (user messages):** user's own email from DB
- **Reply-To (system emails):** `support@imonsocial.com` (alias → `forest@imonsocial.com`)

### Deployment Checklist
- `PUBLIC_FACING_URL=https://app.imonsocial.com` in backend env
- `EXPO_PUBLIC_APP_URL=https://app.imonsocial.com` in frontend env
- `SENDER_EMAIL=notifications@send.imonsocial.com` in backend env
- `RESEND_API_KEY` set in production
- `MONGO_URL` points to Atlas (NOT localhost)
- Optional: `IMAGE_CACHE_MB=200` (default) to tune image cache size

### Mocked Services
- Twilio SMS: All SMS functionality is MOCKED

### Key Files
- `/app/backend/utils/image_storage.py` — Image upload, compression, LRU cache, object storage
- `/app/backend/routers/image_router.py` — Image serving with CDN-like caching + hires flag check
- `/app/backend/routers/messages.py` — Email/SMS/MMS routing with reply-to headers
- `/app/backend/routers/contacts.py` — Contact CRUD, photos/all with thumbnails, profile photo
- `/app/backend/scripts/migrate_images.py` — One-time base64 → object storage migration
- `/app/frontend/app/contact/[id].tsx` — Contact page with Facebook-style photo gallery
- `/app/frontend/app/(tabs)/inbox.tsx` — Inbox with useFocusEffect refresh
- `/app/frontend/app/admin/organizations/[id].tsx` — Org settings with hires_images toggle
- `/app/frontend/components/OptimizedImage.tsx` — Reusable expo-image wrapper
