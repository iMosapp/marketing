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

### Performance Sprint (Mar 30, 2026) -- LATEST

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

## Prioritized Backlog

### P0
- ✅ Mobile login routing fix for users with null onboarding_complete (DONE)
- ✅ Architecture Phase 1 foundations (DONE)
- Verify PWA login/iOS fix works after deployment
- Deploy all Mar 28 fixes

### P1
- Architecture Phase 2 — account page decomposition
- Architecture Phase 3 — contact page decomposition  
- App Store Preparation (`eas.json`, `app.json`)
- Push Notifications (mobile alerts)
- AI-Powered Outreach (contextual follow-ups)
- Gamification & Leaderboards

### P2
- Architecture Phase 4 — backend service layer
- Architecture Phase 5 — shared UI components
- Typing indicators + read receipts (WebSocket already in place)
- Full Twilio / WhatsApp / Stripe integration
- Inventory Management Module
- Mobile tags sync issue

## Test Credentials
- Super Admin: `forest@imosapp.com` / `Admin123!`
- Test User (no store/org): `mjeast1985@gmail.com` / `NavyBean1!` (preview) / `Mjeast1985!` (production)
