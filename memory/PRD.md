# i'M On Social — Product Requirements Document

## Original Problem Statement
Build a Relationship Management System (RMS) / CRM for automotive sales professionals.

## Core Architecture
- **Frontend:** React Native / Expo (web)
- **Backend:** FastAPI (Python)
- **Database:** MongoDB Atlas
- **Integrations:** Resend (email), Twilio (MOCKED), OpenAI, Emergent Object Storage, Pillow, Nominatim

---

## CRITICAL: Image Pipeline Rules — DO NOT REVERT

**ALL images MUST go through `utils/image_storage.py`. ALL public API responses MUST use `utils/image_urls.py` resolvers.**

### Pipeline:
1. Raw image → WebP (max 1200px, 85% quality) → thumbnail (200x200) → avatar (80x80)
2. Stored in Emergent object storage + in-memory LRU cache (200MB)
3. Served via `/api/images/` with ETag + 1-year immutable Cache-Control

### The `photo_path` pattern:
- Every image document has `photo_path`, `photo_thumb_path`, `photo_avatar_path`
- If `photo_path` exists → serve `/api/images/{photo_path}` (instant)
- If not → lazy-migrate on first access → set photo_path → redirect

### Centralized resolvers (`utils/image_urls.py`):
- `resolve_user_photo(user)` — profile photos
- `resolve_store_logo(store)` — store logos
- `resolve_card_photo(card)` — congrats/birthday card photos
- `resolve_contact_photo(contact)` — contact avatars
- `resolve_feedback_photo(feedback)` — review photos

### NEVER DO:
- Store raw base64 as photo_url (use `upload_image()`)
- Return base64 in API responses (use resolvers)
- Use `user.get("photo_url")` directly in responses — always use `resolve_user_photo(user)`
- Use `store.get("logo_url")` directly — always use `resolve_store_logo(store)`
- Use duplicate MongoDB keys: `{"$ne": None, "$ne": ""}` — use `{"$nin": [None, ""]}`

### Migration:
- `POST /api/images/migrate-all-base64` — batch migrates + backfills (super admin, safe to re-run)

---

## What's Been Implemented (This Session)

### Image Performance — Complete Platform Overhaul (Feb 2026)
- **Showcase** — All 4 photo endpoints lazy-migrate, API returns direct `/api/images/` paths
- **Digital Card** — `resolve_user_photo` + `resolve_store_logo` for all public card data
- **Landing Page** — Same optimized resolvers
- **Congrats Card** — Upload now uses image pipeline (not base64). GET uses `resolve_card_photo`
- **Birthday Card** — Creation stores optimized URLs. GET uses optimized resolvers
- **Profile** — Photo upload uses pipeline. GET uses resolvers
- **Contact Gallery** — Returns URL paths (not base64 blobs)
- **Review Link** — Fixed popup blocker (window.location.href)
- **Batch Migration** — 27 images migrated, 4 backfilled, with auto-backfill step
- **Shared Helper** — `utils/image_urls.py` centralizes all URL resolution
- **$nin bug fixed** — Replaced all `{"$ne": None, "$ne": ""}` with `{"$nin": [None, ""]}`

### Operations Manual v3.0 & PDF Export — COMPLETE
### Streamlined Client Onboarding — COMPLETE
### Admin Cleanup — Onboarding removed from admin areas

## Prioritized Backlog

### P1
- Google Places API (when key available), Permission Roles/Templates
- AI-Powered Outreach, Auth refactor (bcrypt), Push Notifications

### P2
- Full Twilio, WhatsApp, Training Hub, Inventory Module, Code cleanup

## Known Issues
- P1: Production email blocked (user: verify RESEND_API_KEY)
- P2: React Hydration Error #418, Mobile tags sync

## Test Credentials
- Super Admin: `forest@imosapp.com` / `Admin123!`
