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
- ALL images → `utils/image_storage.py` → WebP → `/api/images/`
- NEVER add base64 fallbacks. NEVER serve base64 in responses.

### Role System
- DB may have legacy roles: `admin` (= `org_admin`), `manager` (= `store_manager`)
- Backend `permissions.py` maps both legacy and canonical role names
- Frontend `authStore.ts` normalizes roles via `normalizeUser()` on every user load
- NEVER add role checks that only match canonical names — always handle both

### Auth Persistence (iOS PWA)
- 3-layer: AsyncStorage → IndexedDB → Cookie (`imonsocial_session`)
- `/auth/me` returns COMPLETE user data (same as login: permissions, store_slug, org_slug, partner_branding)
- Cookies refreshed on every `/auth/me` call
- Cookie restore retries once on network failure (cold-start resilience)
- Login does case-insensitive, trimmed email lookup

---

## What's Been Implemented (Latest Session - Mar 17, 2026)

### Campaign Creation Fix (Mar 17, 2026)
- **FIXED:** "Create" button on New Campaign screen was non-functional due to `Alert.alert` with callbacks not reliably triggering on all platforms
- Replaced all `Alert.alert` calls in `handleSave` with `showToast` for validation errors and success messages
- Restyled Create button from a plain text link (`padding: 4`) to a prominent blue pill button with larger touch target
- Changed post-save navigation from `router.back()` to `router.replace('/campaigns')` for predictable routing
- Reduced "Ask Jessi" banner `zIndex` from 9999 to 50 to prevent potential touch interference
- Added `delay_hours` field to backend `CampaignSequenceStep` model for completeness
- Backend campaign creation API verified 100% working (7/7 tests passed)

### Duplicate Campaign Feature (Mar 17, 2026)
- **NEW:** "Duplicate Campaign" button on campaign detail page — creates a copy with "(Copy)" appended to name
- Backend: `POST /api/campaigns/{user_id}/{campaign_id}/duplicate` endpoint
- Frontend: Blue outlined button with copy icon, placed above the Delete button
- Duplicate starts paused (`active: false`) so user can review/customize before activating
- After duplicate, user is redirected to the new campaign's edit page for immediate customization

### Tag → Campaign Auto-Enrollment + Immediate Touchpoint (Mar 17, 2026)
- **FIXED:** `PATCH /api/contacts/{user_id}/{contact_id}/tags` now triggers campaign enrollment check — previously only create/update contact did
- **NEW:** When a contact is auto-enrolled in a campaign and step 1 has zero delay, the system immediately creates a task + pending_send + notification (no more waiting 15 min for the scheduler)
- **FIXED:** Campaign tasks now include `contact_name` and `contact_phone` fields — previously missing, causing "Unknown" display and broken "Send Text" button in Today's Touchpoints
- Enrollment auto-advances to step 2 after immediate processing to prevent scheduler double-fire
- Subsequent steps are handled by the existing 15-minute scheduler with correct `delay_hours` calculations
- Added `delay_hours` field to `CampaignSequenceStep` model
- Backend tested 100% (9/9 tests passed)

### Photo-Dominant OG Images (Mar 16, 2026)
- Rewrote the salesperson OG image generator: profile photo now fills ~55% of the 1200x630 frame with name/title on the right panel (was a small 260px circle)
- Created new customer card OG image endpoint (`/api/s/og-card-image/{card_id}`) — lightweight WebP (12KB) instead of the heavy 1080x1350 PNG card image
- Both cached in object storage + LRU memory cache, served as WebP at 85% quality
- OG cache invalidated automatically when salesperson updates their profile photo
- Salesperson OG: ~40KB, Customer card OG: ~12KB — both under 50KB for fast SMS previews

### Contact Import Guide Fix (Mar 17, 2026)
- Fixed inaccurate import guide at `/import-guide/`
- iCloud: Added crucial Step 1 "Open iCloud on a Computer" specifying `icloud.com` login on desktop
- Google: Text correctly references `contacts.google.com` and Export button in "top-right area"
- Replaced generated/fake screenshots with actual user screenshots annotated with red circles pointing to correct buttons
- Guide is mobile-responsive and covers both Apple (VCF) and Google (CSV) export flows

### CSV and VCF Contact Import (Mar 16, 2026)
- Built backend parsers for both Google Contacts CSV and Apple/Google VCF formats
- Auto-detect endpoint (`/api/contacts/{user_id}/import/preview`) routes by file extension
- Smart name splitting, phone label priority (Mobile > Work > Home), birthday parsing, duplicate detection
- VCF parser handles Apple's `item1.` prefix, line folding, escaped characters, structured names (N:Last;First)
- New fields on Contact model: `organization_name`, `phones[]`, `emails[]` (with label/value)
- All imported contacts set `ownership_type: "personal"` so they stay with the user, not the org
- Frontend import page supports both file types with preview stats and duplicate badges
- 40 total backend tests passed (18 CSV + 22 VCF, 100% success rate)

### Personalized OG Image for Landing Pages (Mar 16, 2026)
- Rewrote `GET /api/s/og-image/{user_id}` to generate a branded 1200x630 PNG using Pillow
- Image includes: circular salesperson photo, name, title, store name, store logo, accent color branding
- Dark theme with accent bars, divider lines, and professional layout
- Falls back to static OG image if user not found
- Updated OG tag logic in short URL redirect handler to use this endpoint for all personal link types (business_card, referral, showcase, link_page)
- OG meta tags now include correct `og:image:width` (1200) and `og:image:height` (630)
- All 13 backend tests passed (100% success rate)

### Marketing Site CTA Cleanup (Mar 16, 2026)
- Removed blue "Get a Demo" button from desktop nav bar on ALL pages (homepage + 20 feature pages + app directory)
- Removed "Schedule a Demo" primary CTA from hero sections on ALL pages
- Kept "Schedule a Demo" ONLY in: hamburger mobile menu + black bottom CTA section + footer
- Hero now shows only subtle "Start Free Trial" outline button
- Files changed: `public/index.html`, `generate_pages.py`, `build/appdirectory/index.html`, `src/App.js`
- React homepage: removed CTA section component, simplified hero to single outline button

### Previous Session - Mar 15, 2026

### My Account Page Restructure
- **"My Profile" section** moved to top: Edit Profile & Bio, My Brand Kit, Voice Training
- **"All Tools & Settings"** collapsible section replaces old Quick Actions — no 6-item limit, shows everything
- Removed old grid pill layout, customize mode, and duplication

### Role & Permission Fixes (Critical)
- `permissions.py`: Added `admin` → `org_admin` and `manager` → `store_manager` mapping
- `admin.py` impersonate endpoint: Now returns complete user data (feature_permissions, store_slug, org_slug, onboarding_complete, etc.)
- `authStore.ts`: `normalizeUser()` maps legacy roles at every user-set point
- `admin/users.tsx`: `ROLE_GROUP_MAP` ensures all users appear in the list regardless of role name
- `admin/users/[id].tsx`: `is_active` checks use `!== false` (treats undefined as active)

### Auth & Login Fixes
- Case-insensitive + trimmed email lookup in login, forgot-password, and reset-password
- `/auth/me` now returns complete user data matching login response
- Cookie refresh on every `/auth/me` call
- Retry logic for cold-start network failures

### Onboarding Fix
- `(tabs)/_layout.tsx`: Added `isImpersonating` guard to onboarding redirect

### UI Fixes
- "Manage Permissions" button: purple → orange for visibility
- Account Health header: name + buttons split into two rows (prevents text fragmentation)

### User-Specific Brand Kit & Theming (Mar 14, 2026)
- Backend: `page_theme` field in BrandKit, returned via `/api/card/data/{userId}`
- Frontend: Light/Dark toggle in Brand Kit settings
- Digital Card page dynamically themes based on brand_kit

---

## Key API Endpoints
- `POST /api/auth/login` — Case-insensitive email, trimmed
- `GET /api/auth/me` — Full session restore from cookie (complete user data)
- `POST /api/admin/users/{id}/impersonate` — Returns complete user data with permissions
- `GET /api/card/data/{userId}` — Digital card data with brand_kit theming
- `PUT /api/email/brand-kit/{entity_type}/{entity_id}` — Update brand kit (includes page_theme)
- `GET /api/s/og-image/{user_id}` — Personalized 1200x630 OG preview image (Pillow-generated)

## Key DB Schema
- `users.role` — May be: super_admin, org_admin, admin, store_manager, manager, user
- `users.email_brand_kit` — page_theme, primary_color, secondary_color, accent_color
- `users.feature_permissions` — Merged with role defaults via `merge_permissions()`
- `users.is_active` — May be true, false, or undefined (undefined = active)

---

## Prioritized Backlog

### P1
- Onboarding Task List for new salespeople
- Gamification & Leaderboards
- AI-Powered Outreach (contextual follow-up on "sold" tag)
- Lead Notification System Phase 2 (push notifications)
- Voice Help Assistant Backend
- Extend theming to other public pages (Link Page, Landing Page, Showcase)

### P2
- Full Twilio Integration (currently MOCK)
- WhatsApp Integration
- Training Hub video content
- Inventory Management Module
- Refactor large files (admin.py 3700+ lines, contact/[id].tsx)

## Known Issues
- P2: Mobile tags sync
- P2: React Hydration Error #418

---

## CRITICAL RECURRING ISSUE: Card Event Tracking / Attribution

**Status:** RECURRING — requires extra vigilance on EVERY card-related change.

**Problem:** Customer-facing card actions (view, download, share) have repeatedly produced phantom events, duplicate events, and misattributed card types. This is the #1 source of inaccurate dashboard data.

**History of failures:**
1. OG images regressed multiple times (wrong image, red background, stale iMessage cache)
2. Card download tracking hardcoded `'congrats'` for ALL card types → phantom "Congrats Card Downloaded" events
3. Two separate tracking pathways (`trackAction` + `track`) both fired on download/share → duplicate events per click
4. `ACTION_CONFIG` only had `("congrats", ...)` entries → welcome/birthday/holiday/etc. actions unrecognized

**Architecture (understand before touching):**
- **Pathway A — Card-specific:** Frontend `trackAction(action)` → `POST /api/congrats/card/{cardId}/track` → backend looks up actual `card_type` from DB → logs correct event. Also increments download/share counters on the card document.
- **Pathway B — Universal tracker:** Frontend `track(action)` → `POST /api/tracking/event` → backend uses `ACTION_CONFIG[(page, action)]` to resolve event type. The `page` param MUST match the card's actual `card_type`.
- **Single source of truth:** `/app/backend/utils/event_types.py` — all event type constants, labels, and resolution logic.

**Rules for any future card changes:**
1. NEVER hardcode a card type string in frontend tracking — always use `cardData.card_type`
2. NEVER fire both `trackAction()` AND `track()` for the same user action (download, share) — pick ONE pathway
3. **NO CODE CHANGES needed for new card types.** The system auto-resolves any card type:
   - `tracking.py` → `resolve_card_action()` dynamically generates event types for ANY card type
   - `tasks.py` → regex-based MongoDB queries (`^(?!digital_|store_).*_card_(viewed|download)`) auto-match any card type
   - `event_types.py` → `get_event_label()` dynamically generates human-readable labels (e.g., "promo_card_viewed" → "Viewed Promo Card")
   - `eventTypes.ts` → `getEventLabel()` does the same on frontend
4. The card API (`GET /api/congrats/card/{cardId}`) MUST return `card_type` in the response
5. After ANY card tracking change, verify by: creating a non-congrats card (e.g., welcome), downloading it, and checking `contact_events` collection — ZERO "congrats" events should appear

**Files involved:**
- `/app/frontend/app/congrats/[cardId].tsx` — customer-facing card page, `track()` + `trackAction()` helpers
- `/app/frontend/services/tracking.ts` — `trackCustomerAction()` sends to universal tracker
- `/app/backend/routers/tracking.py` — universal tracker endpoint + `ACTION_CONFIG`
- `/app/backend/routers/congrats_cards.py` — card-specific track endpoint (`/card/{id}/track`)
- `/app/backend/utils/event_types.py` — SINGLE SOURCE OF TRUTH for event types
- `/app/frontend/utils/eventTypes.ts` — frontend event labels

---

### Performance Dashboard Card Type Fix (Mar 17, 2026)
- **FIXED:** `customer_card_views` metric was missing `thankyou_card_viewed`, `welcome_card_viewed`, `anniversary_card_viewed` — Thank You/Welcome/Anniversary card views were invisible in performance
- **FIXED:** Card downloads (`*_card_download`) were not counted in ANY performance metric — now included in `customer_card_views`
- Updated `EVENT_CATEGORY_MAP` and `ENGAGEMENT_CATEGORY_MAP` with all card type variations
- Verified: Thank You card views + downloads now appear in both performance summary and detail drill-down
- **ROOT CAUSE:** Three bugs causing phantom "Congrats Card Downloaded" events when downloading Welcome/Birthday/etc cards:
  1. Frontend `track()` helper hardcoded `'congrats'` as the page parameter for ALL card types
  2. Download/share handlers called BOTH `trackAction()` AND `track()`, creating duplicate events through two separate backend pathways
  3. Backend `ACTION_CONFIG` only had `("congrats", ...)` entries — no welcome, birthday, holiday, etc.
- **FIX:** Card API now returns `card_type` field; frontend `track()` uses actual card type; removed duplicate `track()` calls from download/share; added all card type entries to `ACTION_CONFIG` and `EVENT_TYPE_LABELS` on both frontend and backend

## Test Credentials
- Super Admin: `forest@imosapp.com` / `Admin123!`

## 3rd Party Integrations
- **Resend:** Transactional emails
- **MongoDB Atlas:** Primary database
- **Twilio:** MOCK mode
- **OpenAI:** AI features via emergentintegrations
- **Pillow + ImageOps:** Image processing
- **qrcode:** QR code generation
- **apscheduler:** Backend job scheduling
