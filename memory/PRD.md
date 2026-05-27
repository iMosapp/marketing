# i'M On Social - Product Requirements Document

## Original Problem Statement
Build a Relationship Management System (RMS) / CRM for automotive sales professionals. AI-powered, human-to-human relationship building where every follow-up is deliberate, meaningful, and personal.

## Core Architecture
- **Frontend:** React Native / Expo (web PWA)
- **Backend:** FastAPI (Python) with async Motor (MongoDB driver)
- **Database:** MongoDB Atlas
- **Integrations:** Resend (email), Twilio (MOCKED), OpenAI, Emergent Object Storage, apscheduler

---

## What's Been Implemented

### Architecture Refactor — Phase 1: Shared Foundations (Mar 28, 2026) -- LATEST

Created the core building blocks for a clean, maintainable codebase:

**New files created:**
- `frontend/utils/photoUrl.ts` — Single source of truth for all photo URL resolution. `resolvePhotoUrl()`, `resolveUserPhotoUrl()`, `resolveContactPhotoUrl()`. Handles relative `/api/images/`, absolute `https://`, base64, native vs web.
- `frontend/types/index.ts` — Centralized TypeScript interfaces: `User`, `Contact`, `Message`, `Conversation`, `PartnerBranding`, `UserRole`, `AvatarSize`. Stop redefining types per-file.
- `frontend/components/Avatar.tsx` — UPGRADED: now uses `OptimizedImage` (expo-image disk cache), URL resolution via `photoUrl.ts`, consistent sizing system (`xs/sm/md/lg/xl/xxl`), backward-compatible legacy numeric size support, graceful error fallback to initials.
- `frontend/components/account/ProfilePhotoUpload.tsx` — Self-contained photo upload component. Web file picker + native camera/library, proper multipart pipeline, loading states, error handling. Extracted from `my-account.tsx`.

**Files updated:**
- `activity.tsx` — Removed inline duplicate `Avatar` component (18 lines → import shared one)
- `contacts.tsx` — Replaced raw `Image` + manual initials with shared `Avatar`
- `my-account.tsx` — Replaced 150+ lines of photo upload logic with `<ProfilePhotoUpload>` component. Removed unused imports (`Image`, `ImagePicker`).
- `contact/[id].tsx` — Replaced inline `resolvePhotoUrl()` with shared `utils/photoUrl.ts`

**Architecture principle established:** Every place in the app that shows a person's photo now uses the same Avatar component and the same URL resolver. Fixing a photo bug once fixes it everywhere.

### AI Clone Profile Builder (Mar 28, 2026) -- LATEST
Rebuilt `settings/persona.tsx` from "AI Persona" settings into a natural 5-step "Build Your Profile" wizard:

- **Step 1 "Your Story"**: Bio, family, hometown, years experience, motto. WHY banner: "Shows on your Digital Card, Link Page, and Landing Page"
- **Step 2 "Your World"**: Vehicles/possessions (new), hobbies, specialties, interests, fun facts. WHY banner: "Makes your profile feel real"
- **Step 3 "Your Voice"**: Communication tone, emoji, humor, response length. NEW: "Things you never say" + "Your go-to phrases". WHY banner: "How Jessi responds to your customers as you"
- **Step 4 "Your Tools"**: Ideal customer description (new), scheduling link (new), payment link (new), other key links (new). WHY banner: "Jessi can share these directly"
- **Step 5 "Final Touches"**: Greeting style, signature, escalation keywords, AI bio generator

Backend:
- `UserPersona` model in `models.py` extended with all new fields: `vehicles`, `never_say`, `custom_phrases`, `ideal_customer`, `scheduling_link`, `payment_link`, `key_links`
- NEW `GET /api/auth/persona/{user_id}/ai-prompt` — compiles the full AI clone system prompt matching the doc structure (Who you are → Tone & Style → Behavior Rules → Key Links)
- The compiled prompt is used by Jessi, suggested replies, and future Twilio automated texting

Zero AI/persona language visible to users. Everything framed as "building your profile" and "helping customers get to know you."

### Auth Storage Hardening (Mar 28, 2026) -- LATEST
- Flipped storage write priority: **IndexedDB is now primary** (awaited), AsyncStorage is a fast-read cache
- All AsyncStorage reads wrapped in `safeAsyncGet` — never throws, returns null if blocked
- All AsyncStorage writes wrapped in individual try/catch — storage failures are non-fatal
- `login`, `signup`, `logout`, `loadAuth`, `startImpersonation`, `stopImpersonation` all hardened
- SW registration `.catch(() => {})` added — was causing unhandled promise rejections on iOS
- Removed `window.location.reload()` from `+html.tsx` SW cleanup — was causing login request abort race condition on mobile
- Face ID / biometric login unchanged — uses iOS Keychain (SecureStore), unaffected by localStorage restrictions

### Mobile Login iOS Fixes (Mar 28, 2026)
- Root cause: `(tabs)/_layout.tsx` used `!user.onboarding_complete` (truthy check) which evaluated to `true` for `null` values, silently redirecting users like Matt (who have `onboarding_complete: null`) to `/onboarding` on every login
- Fix: Changed to strict equality `user.onboarding_complete === false` — only new users in active onboarding flow get redirected
- `+html.tsx` SW cleanup now reloads once after unregistering old SWs (prevents stale SWs from intercepting login requests)
- `login.tsx` catch block improved: full error logging (status, code, stack), granular 402/403 messages, "close and reopen" guidance for JS runtime errors

### Click Tracking Deduplication (Mar 28, 2026)
- Added bot/prefetch user-agent filtering (iMessage, WhatsApp, Facebook, Google, etc.)
- Added IP-based dedup (same IP + same link within 60 seconds = 1 click)
- Increased contact_event dedup window from 2-5 min to 30 min
- Added DB index for click dedup queries
- Congrats card views now skip bot requests

### PWA Login Fix (Mar 28, 2026)
- Service worker v5: never intercepts navigation, only caches static assets passively
- SW registration moved to post-login (not on login page)
- Login page actively kills any existing broken service workers
- Removed `withCredentials: true` from axios (unnecessary for same-origin)
- Fixed CORS `allow_credentials` + wildcard origin conflict
- Added auto-retry on login (1 silent retry for network hiccups)
- iOS keyboard fix: proper inputmode/autocomplete/user-select attributes
- Created `fix.html` — self-service SW/cache clearing page for stuck users

### Password Security Fix (Mar 28, 2026)
- Fixed 3 user creation paths storing passwords as plain text (admin, team invite register, team invite accept)
- All now use bcrypt via `hash_password()`
- Added `admin-fix-login` diagnostic+reset endpoint (case-insensitive)
- Added `admin-fix-all-passwords` bulk migration endpoint
- Login endpoint optimized: background tasks for timezone/lifecycle, under 0.5s response

### Profile Photo & Bio Fix (Mar 28, 2026)
- Fixed duplicate PATCH `/api/users/{user_id}` in server.py not clearing `photo_path`/`photo_avatar_path`
- Fixed `refreshUserData` in my-account.tsx to sync auth store

### Previous Session Work
- Universal Link Tracking, Tracked Media, Production Stability (async motor), Campaign removal/archive

---

## Architecture Refactor Roadmap

### Phase 3 — Contact Page Partial Decomposition ✅ DONE (Mar 28, 2026)
Reduced `contact/[id].tsx` from **6,060 lines → 5,017 lines** (1,043 lines extracted).

New files:
- `components/contact/contactStyles.ts` — all 245 StyleSheet definitions (~903 lines)
- `utils/contactHelpers.ts` — utility functions (`getTimeInSystem`, `formatEventTime`, `formatDateUTC`), constants (`QUICK_ACTIONS`, `EVENT_CATEGORY_ICON`), and `IntelRenderer` component (~150 lines)

What remains in contact/[id].tsx: the deeply interlinked state machine (40+ state vars), business logic, and JSX. The remaining 5,000 lines require a React Context pattern to properly decompose — documented as Phase 3b.

### Phase 2 — Account Page Decomposition ✅ DONE (Mar 28, 2026)
Split `my-account.tsx` from **1,533 lines → 424 lines** (72% reduction).

New components created under `components/account/`:
- `PresenceCard.tsx` — reusable card wrapper for all presence assets (preview panel + header + action buttons)
- `PresenceLinks.tsx` — all 8 presence items (Digital Card, Showcase, Review Link, Link Page, Landing Page, Templates, Card Templates, Email Signature)
- `StoreManagement.tsx` — store presence & settings section for managers
- `ShareReviewModal.tsx` — review link share modal (SMS/email/copy)
- `AccountInfoCard.tsx` — read-only account info rows

`my-account.tsx` is now a ~400-line coordinator: state + layout only. Adding/fixing any presence card now takes 5 minutes instead of hunting through 1,500 lines.

### Phase 1 — Shared Foundations ✅ DONE (Mar 28, 2026)
- `utils/photoUrl.ts` — unified photo URL resolver
- `types/index.ts` — centralized TypeScript interfaces
- `components/Avatar.tsx` — upgraded, OptimizedImage, consistent sizing
- `components/account/ProfilePhotoUpload.tsx` — extracted from my-account.tsx
- `activity.tsx` — removed inline Avatar duplicate
- `contacts.tsx` — uses shared Avatar
- `contact/[id].tsx` — uses shared resolvePhotoUrl

### Phase 2 — Account Page Decomposition ✅ DONE
- `my-account.tsx` 1,533 → 424 lines
- 5 new focused components under `components/account/`

### PWA Session Persistence Fix — Logout on Every Resume (Apr 3, 2026) -- LATEST

**Root cause 1 (PRIMARY):** `manifest.json` had `"start_url": "/auth/login"`. Every cold launch from the iOS home screen icon opened the login page directly — bypassing `loadAuth` and ignoring any stored session. Changed to `"start_url": "/"` so the root `index.tsx` handles auth routing correctly (authenticated → home, not → login).

**Root cause 2:** When iOS clears storage (localStorage/IDB) while the JS context survives, `loadAuth()` would find nothing in storage and leave `isAuthenticated: false`. Added in-memory recovery: if the Zustand store already has a valid user/token, re-persist to storage and continue authenticated without hitting login.

**Root cause 3:** `(tabs)/_layout.tsx` auth redirect had no grace period — any momentary `isAuthenticated: false` during `loadAuth` async reads would immediately redirect to login. Added 600ms grace period that re-checks the final store state before redirecting.

**Verified:** `manifest.json` start_url is now `/`, storage recovery path is in place, grace period prevents race condition logouts.

### Hub "Setup & Manage" Disappearing Fix (Apr 2, 2026)

**Root cause:** `GET /api/users/{user_id}` and `PATCH /api/users/{user_id}` in `server.py` returned the raw MongoDB document without calling `merge_permissions()`. The raw DB `feature_permissions.admin._enabled` was `null`/missing for users whose permissions were set before the permissions system existed. Every call to `refreshUserData()` (triggered by any profile edit) replaced the store's properly-merged permissions with the raw DB value → `perm('admin')` returned false → "Setup & Manage" section disappeared.

**Fix:** Added `merge_permissions(user.get("feature_permissions"), user.get("role"))` to both:
- `GET /api/users/{user_id}` → always returns merged permissions
- `PATCH /api/users/{user_id}` → patch response also returns merged permissions

All other user-returning endpoints (`/auth/login`, `/auth/me`, `/admin/impersonate`) were already calling `merge_permissions`. This was the only missing path.

**Verified:** GET and PATCH both now return `admin._enabled: True` for super_admin. Section will no longer vanish after profile edits.

### New User → My Presence Redirect (Apr 2, 2026)

On first login (or any login where profile is incomplete — no bio yet), users now land directly on `/my-account` (My Presence) instead of the Hub. Once they have a bio set OR `onboarding_complete === true`, subsequent logins go to `/(tabs)/home`.

**Change:** `getProfileGatedRoute` in `login.tsx` — one line: `'/(tabs)/more'` → `'/my-account'`  
**Verified:** Matt (no bio) → /my-account ✅, Forest (complete) → /home ✅

### Profile Edit UX Fix (Apr 2, 2026)

Two UX improvements to make profile editing discoverable:

**Hub page (more.tsx):**
- Replaced small "Tap to edit profile" hint text (confusing, small target) with a full-width "Edit Profile" button with pencil icon
- Button uses `colors.card` background + gold border + gold text — matches app design system
- Full width, 11px vertical padding — very easy to tap

**My Presence page (my-account.tsx):**
- Removed "Edit" button from top-right nav header (users weren't finding it)
- Added prominent "Edit Profile" button directly below avatar, above the name field
- Button is full-width with pencil icon — impossible to miss
- Inline pencil icons (name, email, phone) remain for quick edits

### Upload Progress Bars (Apr 2, 2026)

Added visual upload progress feedback for cover photo and profile photo uploads on the My Presence page.

**Cover photo (my-account.tsx):**
- Semi-transparent overlay slides up from the bottom of the cover image during upload
- Shows "Uploading 2.3 MB" label + "67%" counter
- Smooth animated gold progress bar fills left → right
- Uses `Animated.Value` with `interpolate` for 60fps animation
- Tracks file size from `file.size` (web) or `asset.fileSize` (native)

**Profile photo (ProfilePhotoUpload.tsx):**
- Overlay covers the avatar with dark tint during upload
- Shows percentage counter + thin gold progress bar
- Badge spinner replaces camera icon during upload
- "Uploading 2.3 MB..." text appears below avatar

**Progress source:** `axios onUploadProgress` callback with `evt.progress` (axios 1.x normalized 0-1) falling back to `loaded/total` for older versions.

### Cover Photo Upload Fix — [object Object] Error (Apr 2, 2026)

**Root cause:** Three combined issues causing `[object Object]` on iOS cover/profile photo uploads:
1. Global axios default `Content-Type: application/json` wasn't overridden for FormData on React Native — server received JSON content type with multipart body → FastAPI returned 422 with `detail` as array → truthy array bypassed `||` fallback → `[object Object]` shown
2. `ProfilePhotoUpload.tsx` explicitly set `Content-Type: multipart/form-data` without boundary — breaks multipart parsing entirely  
3. Error display code used `err?.response?.data?.detail || fallback` — when detail is an array (422 validation error), the `||` fallback isn't used

**Fixes:**
- `services/api.ts`: Added FormData detection in request interceptor — auto-deletes Content-Type for all FormData requests so axios sets correct `multipart/form-data; boundary=...`
- `components/account/ProfilePhotoUpload.tsx`: Removed explicit wrong Content-Type header
- `app/my-account.tsx` + `ProfilePhotoUpload.tsx`: Fixed error display to handle array/object detail gracefully
- `profile.py` backend: Added logging and HEIC-friendly content type validation
- iOS HEIC handling: Cover photo now uses `asset.mimeType` and converts HEIC → JPEG type before upload

### Campaign Removal Fix (Apr 2, 2026)

Fixed campaign removal being incomplete — tasks remained in Touchpoints and campaign could reappear in journey.

**Bugs fixed:**
1. `remove_campaign_enrollment` only cancelled `status:"pending"` sends — now cancels `["pending","pending_user_action","processing"]` using `enrollment_id` filter (not campaign_id+contact_id, which was too broad)
2. Active tasks were never dismissed on removal — now `status="dismissed"` so they vanish from Touchpoints immediately
3. Campaign journey query only excluded `"archived"` — now excludes both `"archived"` and `"cancelled"` enrollments
4. Re-enrollment after removal now works cleanly — old sends are cancelled, new sends are fresh

**Verified:** 12/12 backend+frontend tests pass.

### Task Resurrection Bug Fix (Apr 2, 2026)
Fixed critical bug where marking tasks "Done" in Today's Touchpoints would cause them to reappear on next page load. Three bugs found and fixed:

**Bug 1 (Catchup resurrection)**: `_catchup_overdue_campaign_tasks` found completed tasks by idempotency key, deleted them, but lacked a `continue` — so it fell through and created a brand new "pending" task immediately. Fix: `continue` for completed/dismissed tasks.

**Bug 2 (pending_send not marked)**: Task completion didn't update `campaign_pending_sends.status = "done"`. Fix: added update in `update_task` complete action so catchup's query `status: {$in: ["pending", "pending_user_action"]}` never sees it again.

**Bug 3 (campaign history invisible)**: Tasks created by catchup (not scheduler) had no `messages_sent` entry in enrollment. The update `messages_sent.$.status = "sent"` failed silently. Fix: added upsert pattern — pushes new entry if none exists, so campaign journey always shows sent steps correctly.

**Bug 4 (re-enrollment key collision)**: `ps_by_key` used `campaign_id + step` as dict key, causing wrong step display for re-enrolled contacts. Fix: now uses `enrollment_id + step` as preferred key with `campaign_id + step` as fallback.

**Bug 5 (delay_minutes missing)**: `CampaignJourney.tsx` `formatDelay()` didn't show minutes. Fix: added `delay_minutes` to interface and display.

**Verified:** 14/14 backend + frontend tests pass. Task stays gone after Done, campaign journey shows 'sent', future steps (6mo/1yr) show as upcoming with scheduled dates.

### Performance Sprint (Mar 30, 2026)

**N+1 query elimination (contact_events.py):**
- Batch-load all `message_id` lookups in ONE query (was: up to 50 separate DB calls per contact page)
- Batch-load all campaign name lookups in ONE query (was: up to 20 separate DB calls)
- Batch-load all card template headline lookups in ONE query (was: up to 20 separate DB calls)
- Net: contact page now does ~5 DB calls instead of potentially ~90

**OOM risk eliminated (contacts.py):**
- Changed 3x `to_list(None)` (unbounded) to `to_list(100/200)` in campaign-journey endpoint

**7 new compound indexes added (server.py):**
- `campaign_enrollments`: `(contact_id, user_id, status)`
- `campaign_pending_sends`: `(contact_id, user_id)`
- `tasks`: `(contact_id, user_id, type)`
- `congrats_cards_sent`: `(contact_id, user_id)`
- `contacts`: `(user_id, phone)` and `(user_id, email)` for dedup
- `messages._id` explicit index for batch lookups

**Slow-request monitoring middleware (server.py):**
- Logs any request >2s with `[SLOW REQUEST]` prefix — identifies future bottlenecks

### Bug Fixes (Mar 30, 2026) -- LATEST

**Hub "My Brand" Layout Fix:**
- `renderBrandItem` in `more.tsx` now uses same `styles.menuItemCard` StyleSheet as regular menu items
- Root cause: React Native Web doesn't apply `flexDirection: row` reliably on inline-styled `TouchableOpacity`; StyleSheet.create() styles work correctly

**Generic Card Creation Fixed (3 bugs):**
- **Backend 500 crash**: `congrats_cards.py` line 507 used `contents` variable when no photo was provided (UnboundLocalError). Fixed with proper `elif`/`else` branches for photo-present-but-failed vs no-photo cases
- **Frontend preview crash**: `create-card.tsx` preview screen called `photo.uri` without null check; wrapped in `{photo && ...}`
- **Template reload bug**: `useEffect` watched `cardType` (static URL param) instead of `selectedType` (reactive state); now also handles users with only `org_id` (no `store_id`)

### Pre-Deployment Build Fix ✅ (Mar 28, 2026)
Production build `expo export --platform web` was failing with:
`SyntaxError: utils/contactHelpers.ts: Unexpected token (JSX in .ts file)`

Fixes: Renamed `contactHelpers.ts` → `contactHelpers.tsx`, fixed import path depth.
Production build now completes cleanly. Confirmed with `expo export --platform web` → `dist/` generated.

### Pre-Deployment Health Check ✅ PASSED (Mar 28, 2026) — CLEARED
Full regression test: **21/21 backend tests + 5/5 frontend tests = 100%**

Minor fixes applied post-testing:
- `admin_helpers.py` + `admin.py`: `APP_URL` now reads from `PUBLIC_FACING_URL`/`APP_URL` env var (was hardcoded)
- `admin_users.py`: Renamed `convert_to_individual` to `convert_to_individual_helper` (was missing @router decorator — orphaned function)
- `admin_users.py`: Renamed duplicate `reactivate_user` (POST) to `reactivate_user_post` (naming clarity, both routes still work)
- `profile.py`: `upload_image()` now returns 400 on corrupted/invalid image files (was 500)

**CLEARED FOR DEPLOYMENT** ✅

### Phase 4 — Backend Admin Service Layer ✅ DONE (Mar 28, 2026) -- LATEST
Split `admin.py` from **4,058 lines → 3 focused files + shared helpers**:

| File | Lines | Owns |
|---|---|---|
| `admin.py` | 2,027 | Orgs, stores, billing, phone assignments, stats, misc |
| `admin_users.py` | 1,552 | User CRUD, pending users, impersonation, permissions, logos |
| `admin_hierarchy.py` | 547 | Org/store assignment, role changes, hierarchy views |
| `admin_helpers.py` | 129 | `safe_objectid`, `get_requesting_user`, `send_invite_email` |

All endpoints verified working (200 OK). Server.py registers all 3 routers. Future user/hierarchy bugs have a clear, focused home.

### Phase 3c — New Contact Form as Separate Route ✅ DONE (Mar 28, 2026)
Extracted the new contact creation form into `app/contact/new.tsx` (791 lines, standalone).
- Expo Router automatically routes `/contact/new` → `new.tsx` (preferred over `[id].tsx`)
- Owns all its own state: contact form, device contacts picker, voice recorder, duplicate detection, tag picker, referral picker, date picker
- `contact/[id].tsx` reduced from 5,017 → 4,427 lines (-590 lines, 12% more reduction)
- The two pages share nothing — future changes to new contact form can't break existing contact view

**Phase 3 total reduction:** 6,060 → 4,427 lines in `[id].tsx` (27% reduction overall)
New files extracted: `contactStyles.ts`, `contactHelpers.ts`, `ContactContext.tsx`, `contact/new.tsx`
Created `contexts/ContactContext.tsx` — the full contract for the contact page state.
- Defines ~80 typed fields covering ALL state variables and handler signatures
- Exports `useContact()` hook — sub-components call this instead of receiving 30+ props
- Pattern: parent owns state → wraps with Provider → children use `useContact()`

**Why full extraction wasn't done in this session:**
The contact page modals alone reference 30+ state vars + 15+ handlers with non-obvious naming conventions (`addTagFromHero` vs `addTag`, `confirmDateSelection` not `handleConfirmDate`, etc.). Extracting them without running the full component test suite risks subtle undefined-variable bugs in a production-critical screen. The TypeScript compiler errors from missing context fields become the exact "Phase 3c TODO list."

**Phase 3c — Contact Page Component Extraction (NEXT)**
With the context contract defined, each extraction follows the same 3-step pattern:
1. Add missing items to `ContactContext.tsx` 
2. Build `ctxValue` in the main component  
3. Create sub-component calling `useContact()` instead of props

Priority extraction order (easiest → hardest):
1. `TagPickerModal.tsx` — 30 lines, 8 context items, self-contained
2. `ReferralPickerModal.tsx` — 25 lines, 6 context items
3. `CampaignPickerModal.tsx` — 25 lines, 6 context items
4. `DatePickerModal.tsx` — 80 lines, 12 context items
5. `ToolbarModals.tsx` — templates + review links + business card (~200 lines)
6. `ActivityFeed.tsx` — the big one (~530 lines)

### Phase 4 — Backend Service Layer
Extract `admin.py` (4,000 lines) into:
- `services/user_service.py` — user CRUD, role changes, activation
- `services/hierarchy_service.py` — org/store assignment logic
- `services/permission_service.py` — role-based access control
- `admin.py` becomes thin routing layer only (~300 lines)

### Phase 5 — Shared UI Components
- `components/common/StatusBadge.tsx` — active/pending/sold tags
- `components/common/EmptyState.tsx` — consistent empty screens
- `components/common/LoadingScreen.tsx` — consistent loading states
- `components/common/SectionHeader.tsx` — reusable section titles

---


## Prioritized Backlog — Updated May 4, 2026

## Prioritized Backlog — Updated May 20, 2026

## Prioritized Backlog — Updated May 27, 2026

### P0 — This Week
- **App Store / TestFlight Launch** — Blocked on Apple Team ID + bundle ID. See App Store Roadmap below.
- **Twilio 10DLC Integration** — LLC/business docs ready. Phase 1: remove mock mode, STOP/UNSTOP webhooks, Messaging Service SID. Registration URLs now live: `/terms`, `/privacy`, `/sms-terms` on `imonsocial.com`.

### P1 — Next Sprint
- **Payment Collection — Stripe vs Elavon** — HOLD, user decision pending. Stub exists at `/subscriptions/quotes/{id}/create-payment`.
- **Virtual Assistant → Inbox Wiring** — Phase 2 of VA: wire the clone to pre-load a draft reply in the composer (Assist mode). Foundation built (persona + `/api/auth/persona/{id}/sample-message` endpoint working).
- **Reseller Portal for Quotes** — Resellers can't create quotes themselves yet. Admin-only for now.
- **Push Notifications** — Mobile alerts for new leads, messages, campaign triggers.

### P2 — Upcoming
- Architecture Phase 3b — Contact page component extraction (ContactContext shell built)
- AI-Powered Outreach — contextual follow-up suggestions
- WhatsApp Integration
- Inventory Management Module
- Mobile tags sync issue
- Stripe/Elavon payment wiring once decision made

### P3 — Backlog
- Typing indicators + read receipts (WebSocket already in place)
- Redis cache (scale beyond 5K users)
- Reseller self-service quote portal

---

## Completed Work — May 2026 Sprint

### Partner Agreements
- PDF generation + download button (admin detail page)
- Auto-email signed PDF + partner copy on W-9 verification
- "Send Link via Text" → creates contact, opens native SMS pre-filled
- Partner phone field in edit modal; Save button fixed (SafeAreaView)
- W-9 verify bug fixed (`agreementId` → `agreement.id`)

### Quote System
- Full digital signing flow: public page `/quote/accept/{id}`, IP/timestamp/hash capture
- Signed PDF generated on acceptance (fpdf2), emailed to customer + admin
- "Send Link via Text" → contact created + native SMS opens
- Custom price override field (no more 25% discount cap)
- Quote subject line: "I'm On Social Quote — Q-XXXXXX"
- SMS opt-in on public signing page (ToS + Privacy links)
- Quote email link `target="_blank"` + resilient button (fire-and-forget logging)

### Virtual Assistant
- New `/settings/virtual-assistant` page — completeness score (7/12), personality chips, what VA knows, live sample message preview (4 scenarios), AI Generate button
- `POST /api/auth/persona/{id}/sample-message` endpoint (GPT-5.2, confirmed working in user's voice)
- Hub: "Manage Profile" + "My Virtual Assistant" buttons visible immediately
- Persona wizard: gold banner links to VA page

### Simplified Onboarding
- `profile-setup.tsx` rebuilt: 3 screens (Name+Photo → Bio+AI → Send First Card)
- VCF/vCard endpoint: `GET /api/profile/{userId}/vcard.vcf` — iPhone "Add to Contacts" tap
- First card send: VCF link + digital card link in one SMS

### Contact Page Improvements
- Feed redesigned: clean Activity-tab style rows (small icon + label + time), single card per day group
- Manual task creation: "Add Task" button next to "Log Customer Reply", modal with title/when/priority/notes
- Full relationship history: no more 5-event cap, 100 events per page, "Load Older History" pagination
- Contact feed expand/collapse on tap (shows message content)

### Internet Lead Intake System
- `POST /api/leads/adf` — full ADF/XML parser (Cars.com, AutoTrader, OEM)
- `POST /api/leads/webhook/{source_id}` — smart field normalizer (60+ field name variations)
- After-hours timing engine — reads store `business_hours` + timezone, queues leads, fires at opening
- AI first message generation in rep's cloned voice
- Scheduler job every 2 min processes queued leads
- Admin dashboard `/admin/internet-leads` — live feed with status, after-hours countdown, AI draft preview

### Branding & Compliance
- "i'M On Social" → "I'm On Social" (global, all 326 instances)
- `brand.ts`: name + poweredByText → "Powered by VI Ventures Group LLC"
- Footer: "Powered by VI Ventures Group LLC" in app + all marketing pages
- Wyoming governing law (replaced Texas everywhere)
- New `/imos/sms-terms` page — full Twilio 10DLC compliant messaging policy
- Terms contact section: "I'm On Social is operated by VI Ventures Group LLC"

### Marketing Site (imonsocial.com)
- `/privacy`, `/terms`, `/sms-terms` — proper legal pages (replaced marketing feature cards)
- Demo forms: SMS opt-in checkbox on ALL 54 pages (homepage modal, generated pages, industry pages, ad pages, presentations)
- `Contact Us` footer → opens Contact Us modal (free-text message, distinct from Book a Demo)
- Hero CTA buttons (Schedule a Demo / Start Free Trial) removed from product page top sections
- Footer `ft-inner` wrapper fixed (was rendering vertically)
- JavaScript double-brace bug fixed — modal buttons now work on all subpages
- `openContactModal()` / `openDemoModal()` — separate modals, correct functions on every page
- "Book a Demo" nav button → correct on all pages
- All `app.imosapp.com` URLs → `app.imonsocial.com`
- Footer copyright: `© 2026 I'm On Social. Powered by VI Ventures Group LLC.`

### Bug Fixes
- `saveBio` undefined crash on `/my-account` — function was missing, now restored
- `image_storage.py` uploads blocking event loop — wrapped in `asyncio.to_thread` (fixes 60s timeouts)
- `messages.py` `channel` variable deleted — caused 100% send failure across all SMS/email
- Activity tab header clipping on large status bars — `useSafeAreaInsets()` replaces `paddingTop: 48`
- TikTok icon invisible in light mode — `#FFFFFF` → `#69C9D0`
- Super Admin role now assignable from Admin → Users (only by super_admin)
- 502/OOM crashes — conversations 10s TTL cache, upload async fix


## App Store Launch Roadmap (Target: This Week)

### What Needs to Happen (Your Side)
1. **Apple Developer Account** — Confirm active at developer.apple.com ($99/yr). Get your **Team ID** from Membership tab.
2. **Bundle ID** — Decide on `com.imonsocial.app` (or similar). Register it in App Store Connect → Identifiers.
3. **App Store Connect listing** — Create new App record, fill in name/description/category/screenshots.
4. **Google Play Console** — Create account at play.google.com/console ($25 one-time). Create app listing.

### What the Agent Does (Code Side)
1. Update `app.json` — bundle ID, version, build number, iOS/Android config
2. Create `eas.json` — preview profile (TestFlight) + production profile
3. Create `expo-build-properties` config for iOS capabilities
4. Run `eas build --platform ios --profile preview` → uploads to TestFlight
5. Run `eas build --platform android --profile preview` → generates AAB for Play Console

### Blockers (Need From You Before Agent Can Build)
- Apple Team ID (from developer.apple.com → Account → Membership)
- Bundle ID decision (e.g. `com.imonsocial.app`)
- Confirm EAS/Expo account credentials (or agent creates new)

### TestFlight Timeline (Once Blockers Cleared)
- Build time: ~20-30 min (EAS cloud build)
- Apple review for TestFlight: 1-2 days (internal), instant (external after first approval)
- Google Play Internal Testing: same-day after AAB upload

---

## Scale Roadmap (6-12 Month Horizon)

### Current State (Mar 2026)
- Single MongoDB instance (Atlas), single FastAPI process, in-process TTLCache
- Pre-scheduled campaign queue (done), contacts pagination (done), last_activity_at index (done)
- TTL indexes on contact_events (2yr), notifications (90d), short_url_clicks (1yr)
- Estimated comfortable capacity: **1K–5K active users**

### Scale Tier 1: 1K → 10K users (~$200–500/mo infra)
**Priority: HIGH — do before launch to paying customers**
- [ ] **Redis cache** — Replace in-process `TTLCache` with Redis. One change, ~$30/mo.
  - Solves: cache survives deploys (no cold-cache OOM spikes), all pods share one cache
  - Files to change: `routers/seo.py`, `routers/tasks.py`, `routers/notifications_center.py`
  - Use `redis.asyncio` with `aioredis`, same TTL logic, just a different backend
- [ ] **2 FastAPI workers** — Change supervisor to run Gunicorn with 2-4 Uvicorn workers
  - `gunicorn -w 4 -k uvicorn.workers.UvicornWorker server:app --bind 0.0.0.0:8001`
  - Doubles throughput with zero code changes
- [ ] **MongoDB Atlas M10 → M30** — More RAM means more of the working set fits in memory, fewer disk reads
- [ ] **Cloudflare CDN for images** — Put Cloudflare in front of object storage URLs
  - Serves images from edge nodes globally, removes all image load from your server

### Scale Tier 2: 10K → 100K users (~$1K–3K/mo infra)
- [ ] **WebSockets for inbox** — Replace polling with push (already have WebSocket infra in place)
  - Currently: every user polls `/messages/conversations/{id}` on every page open
  - Fix: server pushes new message events to connected clients
  - Impact: eliminates ~70% of all API requests at this scale
- [ ] **MongoDB read replicas** — Route read-heavy queries (contact list, activity feed) to replica
  - Write to primary, read from secondary — doubles effective read throughput
- [ ] **Separate analytics DB** — Move `contact_events`, `short_url_clicks` to ClickHouse or BigQuery
  - These collections will be billions of rows at this scale
  - ClickHouse handles time-series analytics at 100× less cost than MongoDB
- [ ] **Contact list virtual scroll** — Currently renders all visible contacts; React Window for true virtualization
- [ ] **`last_activity_at` full rollout** — Complete `log_contact_event()` adoption across all 20 call sites

### Scale Tier 3: 100K → 1M users (~$10K–50K/mo infra)
- [ ] **MongoDB sharding on `user_id`** — Partition all collections across multiple nodes
  - All queries already have `user_id` as the first field in compound indexes (ready for this)
  - Requires MongoDB Atlas M50+ with sharding enabled
- [ ] **Kafka event streaming** — Replace direct DB inserts for events with a Kafka topic
  - Decouples event producers from consumers (analytics, notifications, campaigns)
  - Campaign queue already follows the correct pattern — just needs Kafka as the transport
- [ ] **Dedicated microservices** — Split scheduler, campaign processor, and media pipeline into separate containers
- [ ] **Redis Cluster** — Replace single Redis with a cluster for cache at this scale

### Comparison: Us vs the Big Players

| Concern | Us (now) | At 100K users | Facebook/WhatsApp |
|---------|----------|----------------|-------------------|
| Messaging | HTTP polling | WebSockets | Persistent TCP/XMPP |
| Cache | In-process TTLCache | Redis | Memcached (100TB+) |
| Images | Object storage ✅ | + CDN | CDN edge in 100+ cities |
| Job queue | Pre-scheduled DB queue ✅ | Same | Kafka (100B msgs/day) |
| Database | Single MongoDB | + Read replica | Sharded MySQL + Cassandra |
| Workers | 1 FastAPI process | 4 Gunicorn workers | Thousands of pods |

**What we do RIGHT that most early-stage apps don't:**
- Object storage for images (not in DB) ✅
- Pre-scheduled campaign queue (not polling enrollments) ✅
- Compound indexes on all major query paths ✅
- TTL indexes to prevent unbounded collection growth ✅
- Async Python throughout (no blocking calls) ✅
- JWT stateless auth (horizontally scalable) ✅

**Key insight from WhatsApp:** They ran 500M users with 32 engineers by keeping it simple — Erlang + PostgreSQL, no fancy microservices. Simplicity scales. The architecture choices made here (pre-scheduled queues, indexed sorts, bounded collections) are the right foundation.

---

## Test Credentials
- Super Admin: `forest@imosapp.com` / `Admin123!`
- Test User (no store/org): `mjeast1985@gmail.com` / `NavyBean1!` (preview) / `Mjeast1985!` (production)

---

## Partner Agreement System (Apr 26, 2026) — VERIFIED ROCK SOLID ✅

Full end-to-end partner agreement + W-9 onboarding:
- Public signing page: `/partner/agreement/{id}` — full MPA + Exhibit A, typed signature, IP capture, W-9 upload
- Admin list: `/admin/partner-agreements` — 4 counters, 5 filter tabs, W-9 status badges (Verified/Awaiting Review/Pending)

## User Termination / Twilio Number Pool (May 20, 2026) — TESTED 14/14 PASS

When a rep is terminated (deactivated), their dedicated Twilio number is automatically held in the pool for reassignment. Inbound SMS to pooled numbers routes to the store's active manager.

**Backend:**
- `DELETE /api/admin/users/{id}` — auto-releases `twilio_number` to `phone_number_pool` with previous owner context. Returns `number_released_to_pool`.
- `PUT + POST /api/admin/users/{id}/reactivate` — both return `pooled_number_available` if old number still in pool.
- `GET /api/admin/twilio/pool` — new endpoint listing all pooled numbers with previous owner context.
- `GET /api/admin/twilio/numbers` — enriched with `previous_owner` for pool entries.
- `twilio_webhooks.py` — pooled number inbound routes to store_manager, falls back to super_admin.

**Frontend:**
- Deactivation dialog shows Twilio number and pool notice.
- Reactivation toast mentions pooled number if still available.


## Training Completion Certificates (May 27, 2026) — VERIFIED ✅

**Backend (`training.py`):**
- `GET /training/certificate/{track_id}` — verifies 100% completion, generates A4 landscape PDF, saves record idempotently (same cert_id on repeat downloads)
- `GET /training/certificates/{user_id}` — list all earned certificates
- PDF design: gold border frame, employee name (large), track name in gold, completion date, unique cert ID footer with "Powered by VI Ventures Group LLC"
- `training_certificates` collection stores: user_id, track_id, track_title, user_name, cert_id, completed_at_str

**Frontend (`training-hub.tsx`):**
- Track list card: "Certificate" gold pill appears below track title when 100% complete
- Lesson list: "Get Your Certificate" full-width gold button at top when all lessons done
- Celebration modal: pops automatically when last lesson is marked complete — ribbon icon, track name, "Download Certificate" button
- Web: triggers PDF download via Blob URL; Native: opens PDF URL via Linking

**Verified:** PDF generates correctly (1943 bytes, valid `%PDF-1.3` header). Certificate record saved to DB with cert_id `CC2C5F40FA2A201B`. Manager's Playbook shows 100% + green checkmark on track list.



## Internal Training Curriculum (May 27, 2026) — LIVE ✅

Seeded 8 comprehensive training tracks (53 lessons) into the existing Training Hub LMS. Now shows **85 total lessons** (includes the 5 pre-existing tracks).

### New Tracks Added
| Track | Audience | Lessons |
|---|---|---|
| Platform Setup & Configuration | Admin/Manager | 8 |
| Customer Support Playbook | Admin/Manager | 6 |
| Account Onboarding | Admin/Manager | 8 |
| Account Management | Admin/Manager | 5 |
| Billing & Subscriptions | Admin/Super Admin | 6 |
| Technical Reference | Super Admin only | 7 |
| Sales Process | All roles | 7 |
| Marketing Playbook | Admin/Super Admin | 6 |

**Delivery system:** Training Hub (`/training-hub`) — role-gated, progress tracked per user, completion checkboxes, video-ready (add YouTube URLs via Manage Training)

**Seed script:** `/app/backend/scripts/seed_internal_training.py` — re-runnable (skips existing tracks)

**Next steps for user:**
1. Redeploy to production
2. Add YouTube training videos via Hub → Learning → Manage Training → edit each lesson
3. Assign tracks to new hires as part of onboarding checklist



## Demo Lead Email Link Fix (May 27, 2026) — VERIFIED ✅

**Problem:** Email "View in Dashboard →" linked to `/admin/hot-leads` (Engagement Intelligence page — wrong!). No conv_id was passed so the email couldn't link to the actual thread.

**Fix in `demo_requests.py`:**
- `conv_id = ""` initialized before try block so it's always in scope
- Email now fires AFTER contact + conversation is created → `conv_id` is available
- `_email_new_lead(demo, conv_id=conv_id)` passes the real thread ID
- Button in email: `"Open Conversation Thread →"` → links to `/thread/{conv_id}`
- If no conv_id (error): falls back to `"Open Inbox →"` → `/inbox`
- Push notification link updated from `/admin/hot-leads` → `/inbox`

**Action required for production:**
1. **Redeploy** to push fix to `app.imonsocial.com`
2. **Configure shared inbox**: App → Hub → Set Up → Shared Inboxes → Edit inbox → toggle "Receive Website Leads" ON → Save



## Smart Lead Routing — On-Shift Reps Only (May 27, 2026) — VERIFIED ✅

**What changed in `lead_intake.py`:**

New helper `_get_on_shift_reps(user_ids, fallback_all=True)`:
- Checks each rep's schedule via `is_user_available()`
- Returns only on-shift reps if any exist
- **Falls back to all reps if 0 are on shift** — lead is never silently dropped
- Fully non-blocking with exception guard

**3 places updated:**
1. **Notification blast** (`_fire_intake_workflow`) — `notif_recipients = await _get_on_shift_reps(workflow_user_ids)` — only on-shift reps get push + SMS + in-app
2. **Intake text sender** — uses first on-shift rep's Twilio number (not always rep[0])
3. **Round-robin / weighted assignment** (`_resolve_assignment`) — skips off-shift members

**Verified via live logs:**
- `[SmartRoute] 1/1 reps on shift → routing to on-shift only` (rep available)
- `[SmartRoute] 0/1 reps on shift → falling back to all reps` (rep off-shift, safe fallback)
- Log format: `reps_notified=1/1` (on-shift notified / total)



## Website Leads → Shared Inbox Routing (May 27, 2026) — VERIFIED ✅

**How it works:**
1. Admin opens a shared inbox → Edit → toggles **"Receive Website Leads"** ON
2. Only one inbox can have this flag (toggling ON auto-clears all others)
3. Every demo request from imonsocial.com now routes through that inbox's full workflow:
   - Assigned reps get notified (in-app + push + SMS if configured)
   - Intake text fires automatically
   - VA profile handles the conversation
   - Jump Ball / round-robin assignment applies

**Backend changes:**
- `SharedInboxUpdate` model: added `receives_demo_requests: Optional[bool]`
- `update_shared_inbox`: when set to True, auto-clears all other inboxes (exclusive)
- List response: includes `receives_demo_requests` flag
- `demo_requests.py`: added `_route_demo_to_inbox()` — finds inbox with flag=True, builds normalized lead + source dict, calls `process_inbound_lead()`
- Fully non-blocking (asyncio.create_task) — demo form always returns success instantly

**Frontend changes:**
- `shared-inboxes.tsx`: "Receive Website Leads" toggle in Edit modal (green card when active)
- Inbox card shows "● Receiving website leads" badge when active

**Verified:** Full curl test — submitted demo request → backend logs confirmed routing to 'Website Demo Leads' inbox via lead_intake pipeline.

**Action required:** Redeploy to push to production.



## Demo Request Lead Routing to sales@imonsocial.com (May 27, 2026) — VERIFIED ✅

**Problem:** Demo requests from imonsocial.com were saved to DB and creating in-app notifications, but no email alert was going out. Leads were landing in Admin → Hot Leads page which wasn't in the navigation.

**Fixes:**
1. **Email notification added** — `_email_new_lead()` in `demo_requests.py` sends a clean HTML email to `sales@imonsocial.com` on every new form submission. Includes name, email (clickable), phone (clickable), company, industry, message, source, UTM params, and a "View in Dashboard →" button linking to `/admin/hot-leads`.
2. **`SALES_EMAIL=sales@imonsocial.com`** added to `backend/.env` (separate from `ADMIN_EMAIL=forest@imonsocial.com`)
3. **Hot Leads added to Hub nav** — Account Management section now shows "Hot Leads" (flame icon) for super admins linking directly to `/admin/hot-leads`

**Email sender:** `I'm On Social Leads <noreply@imonsocial.com>` with `reply-to` set to the lead's email address so replying directly goes to the prospect.

**Action required:** Redeploy to push to production.



## Team Availability Admin View (May 27, 2026) — VERIFIED ✅

**Backend (`user_schedule.py`):**
- `GET /schedule/team` enriched: returns `role`, `today_blocks`, `next_window`, `override_until`, `quiet_mode`, `has_schedule` for every teammate
- All 59 availability checks now run in-memory (no N+1 DB calls per user) — batch-loaded schedules via single `find()`
- Sorted: on-shift first, then alphabetically

**Frontend (`/admin/team-availability`):**
- Summary bar: On Shift / Off Shift / Total counts
- Per-rep row: initials avatar (green = on shift, grey = off), name, role badge, status
- Shows: "On shift", "Override active until X:XX", or "Off shift" + "Next: Wednesday 09:00"
- Calendar icon → jumps to their schedule page
- Auto-refreshes every 30 seconds; manual refresh button
- "Updated HH:MM" timestamp so admin knows how fresh the data is
- Accessible from Hub → Set Up → "Team Availability"



## Agent Scheduling + Notification Quiet Hours (May 27, 2026) — VERIFIED ✅

**Backend: `/app/backend/routers/user_schedule.py` (new)**
- `user_schedules` DB collection per user
- Per-day time blocks (multiple shifts per day for split schedules)
- Rotating Week A / Week B (anchor date determines which week is active)
- `is_user_available(user_id)` — timezone-aware, checks override first
- `next_available_window()` — returns human-readable "Next: Wednesday 09:00"
- `POST /schedule/me/override` — force-available for +2h / +4h / EOD / clear
- `GET /schedule/status/{user_id}` — live availability check
- `GET /schedule/team` — team-wide availability for admins

**Push integration:**
- `send_push_to_user()` in `push_notifications.py` now checks `is_user_available()` before sending
- Off-shift reps skip all push notifications (You're Needed, new lead, customer reply, etc.)

**Frontend: `/app/frontend/app/settings/schedule.tsx` (new)**
- Live status pill (green=available, red=off-shift) with override time
- "Respect My Schedule" quiet mode toggle
- Timezone display (auto-detected from account)
- Rotating Schedule toggle + Week A/B tabs + anchor date field
- 4 quick presets (Mon–Fri 9–5, Mon–Fri 8–6, Mon–Sat 9–5, Clear All)
- Day grid — tap any day to edit hours (add multiple shifts per day)
- Day editor: Add Shift, Mark as Off, time input with validation
- Override buttons: +2h, +4h, End of day, Turn off override
- Accessible from Hub → Settings → "My Schedule"



## "You're Needed" Escalation Push (May 27, 2026) — VERIFIED ✅

Push notifications now fire at every escalation trigger point, regardless of SMS/phone settings.

**3 trigger points in `ai_reply.py`:**
1. **Hot-topic immediate** — when customer asks about inventory/pricing/scheduling/color, Jessi says "let me check" and fires push immediately: `"You're Needed — {name}" / "Asked: '{question}' — Jessi passed it to you."`
2. **Reply-count threshold** — when `needs_approval=True` (rep hasn't responded after N replies): `"You're Needed — {name}" / "Jessi needs your help. Review AI draft before it sends."`
3. **Manager escalation** — when rep times out (15 min default), manager gets: `"Escalation: {name} is waiting" / "{rep} hasn't responded in Xm."`

**Fix in `twilio_webhooks.py`:**
- "You're Needed" push was buried inside `if sms_urn_enabled and rep_personal_phone and rep_twilio_number` → moved to fire unconditionally after the notification insert. Removed duplicate nested push to prevent double-firing.



## Stripe Quote Payment Integration (May 27, 2026) — VERIFIED ✅

**What was built:**
When a customer digitally signs a quote, a Stripe Checkout Session is **automatically generated** for the exact monthly amount and sent in the email + SMS.

**Backend changes (`subscriptions.py`):**
- `_create_quote_payment_session()` — creates Stripe checkout session from `quote.pricing.final_price`, stores in `payment_transactions`, saves `stripe_checkout_url` + `stripe_session_id` on the quote
- `accept_quote` — now awaits Stripe session creation and returns `stripe_checkout_url` in the response
- `_email_accepted_quote` — replaced the TODO payment link with the live Stripe URL
- `GET /subscriptions/quotes/{id}/public` — now exposes `stripe_checkout_url` and `payment_status`
- `POST /subscriptions/quotes/{id}/create-payment` — "Pay Now" button can regenerate session
- `GET /subscriptions/quotes/{id}/payment-status?session_id=...` — polls Stripe and updates DB
- `server.py` Stripe webhook — handles `type="quote_payment"` to mark quote as paid

**Frontend changes (`quote/accept/[quoteId].tsx`):**
- Accepted state shows **"Pay $X/month" button** (orange, prominent)
- Handles `?payment=success&session_id=...` URL params returned from Stripe
- Polls payment status after return — transitions to "Payment Complete" state
- Handles `?payment=cancelled` — shows retry button
- `stripe_checkout_url` stored so button works even on page refresh

**Requires:** `STRIPE_API_KEY=sk_live_...` in production secrets (already configured by user).



## Twilio 10DLC Live + Push Notifications (May 27, 2026) — VERIFIED ✅

**Twilio:**
- Updated `docs.py` — Twilio label: "DEVELOPMENT MODE" → "LIVE (A2P 10DLC)"
- Added `GET /api/admin/twilio/status` — full live status, A2P compliance, push subscription count
- Added `POST /api/admin/twilio/test-sms` — admin test button to verify SMS delivery

**Push Notifications:**
- New `hooks/usePushNotifications.ts` — browser permission state, enable/disable, subscription
- Hub → Settings section: Push Notifications item with green/red/grey status dot
- `send_daily_task_digest()` in `push_notifications.py` — morning push with today's touchpoint count
- `send_push_to_users()` broadcast helper
- `morning_push_digest` scheduler job — daily at 2pm UTC (7am PDT)

**Status:** Twilio LIVE + A2P 10DLC confirmed. 6 active push subscriptions in production DB.



## Shared Inbox Edit/Webhook + VA Picker (May 27, 2026) — VERIFIED ✅

**Bug fixes:**
- Fixed backend crash: added `from fastapi import Request` to `shared_inboxes.py` (NameError on startup)
- Fixed delete endpoint: added missing `@router.delete("/shared-inboxes/{inbox_id}")` decorator
- Fixed list response: now returns `va_profile_id` and `va_prompt_override` so Edit modal pre-fills correctly

**New features:**
- `va_profile_id` added to `WorkflowConfig`, `serialize_lead_source`, and `save_workflow_config` in `lead_sources.py`
- Lead Sources workflow page now shows a proper VA picker (list of VA Library profiles with avatars) instead of just a "Manage VA Library →" link

**Verified:** Full CRUD curl tests pass (create, list, edit with va_profile_id, webhook-info, delete). Backend healthy.


## Inbox 5-Tab Redesign (May 20, 2026) — TESTED 10/10 PASS

Replaced scrollable pill filters with a fixed 5-tab bar:
- **Assigned** (blue) — Active conversations the rep owns
- **Waiting** (orange) — Paused / needs_assistance, customer replied
- **AI Active** (green) — AI is handling the conversation
- **Unassigned** (purple) — No assigned rep / inbound pool
- **All** (gold) — Everything

Each tab shows a live count badge. Active tab highlighted with a colored bottom border.

**AI mode quick-toggle** on every conversation row: `Human | Assist | Auto` pill that cycles on tap (optimistic update + API call). Lets reps change AI mode without opening the thread.


- Phone Numbers page shows "Previously: [name] (released X ago)" for pool entries.


- Admin detail: `/admin/partner-agreement/{id}` — Legal record (IP/timestamp/hash), W-9 panel with verify button, Full Agreement collapsible
- Company: VI Ventures Group LLC | Tiers: Referral 10%/15%, Reseller 20%/30%/40%
- Custom commission notes override standard tiers in Exhibit A when set
- Markdown renderer improved: handles inline **bold** and *italic* within list items
- Bugs fixed: agreementId undefined on W-9 verify, get_agreement missing w9_status/w9_file_url/custom_terms/commission_duration, list_agreements missing w9_status, duplicate route decorator, create_default_templates referenced undefined variables
- Backend: 26/26 tests pass | Frontend: All flows verified via Playwright
Quote signing system complete
