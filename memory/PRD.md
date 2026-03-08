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

### Image Upload on Production:
- All image uploads MUST use `asyncio.to_thread()` to run synchronous upload code in a thread pool
- This prevents event loop blocking that causes 520 proxy timeouts
- Use `_sync_upload_bytes()` helper in congrats_cards.py as a reference pattern
- Migration endpoint processes 1 image per call with gc.collect() after each

### NEVER DO:
- Store raw base64 as photo_url (use `upload_image()`)
- Return base64 in API responses (use resolvers)
- Use `user.get("photo_url")` directly in responses — always use `resolve_user_photo(user)`
- Use duplicate MongoDB keys: `{"$ne": None, "$ne": ""}` — use `{"$nin": [None, ""]}`

---

## CRITICAL: Unified Card System — DO NOT REVERT

**ALL card types (congrats, birthday, anniversary, thankyou, welcome, holiday) MUST use `congrats_cards.py`.**

- `auto_create_card(user_id, contact_id, card_type="birthday")` creates cards in `congrats_cards` collection
- GET endpoints check `congrats_cards` first, then fall back to legacy `birthday_cards` collection
- `birthday_cards.py` is LEGACY — its router is NOT registered in `server.py`

---

## What's Been Implemented

### Leaderboard Visibility Toggle Fix (Mar 2026)
- Toggle now respects user-level `settings.leaderboard_visible` across all tiers
- Opted-out users hidden from others but can see their own rank
- Re-ranking after filtering (no gaps)
- Profile photos use optimized WebP pipeline

### Card Preview Photo Shape Fix (Mar 2026)
- Preview now uses rounded square (borderRadius: 20/16) to match delivered card

### Digital Card Text Overlap Fix (Mar 2026)
- Removed "Tap corner for QR code" text that overlapped social icons
- Tightened photo/spacing to fit all content cleanly

### Card Creation 520 Fix (Mar 2026)
- Image upload in congrats card creation now uses asyncio.to_thread
- Prevents event loop blocking on production

### Image Migration Tool (Mar 2026)
- `/api/images/migrate-now` — processes 1 image per call via thread pool
- `/api/images/migrate-check` — instant count of remaining images
- Skips oversized images (>3MB) and marks failed ones to prevent retry crashes
- Admin Dashboard button loops automatically

### Unified Card System (Mar 2026)
- Consolidated birthday_cards into congrats_cards
- All auto-creation triggers updated (scheduler, date_triggers, tags)

### Image Performance Overhaul (Feb 2026)
- All public pages optimized (Showcase, Cards, Digital Card, etc.)
- Batch migration endpoint, lazy migration, $nin bug fixed

### Other Completed Features
- Operations Manual v3.0 & PDF Export
- Streamlined Client Onboarding
- Carrier-Agnostic Messaging (Personal SMS fallback)
- Comprehensive Reporting System
- White-Label Branded Emails
- Public REST API & Webhook System

## Prioritized Backlog

### P1
- AI-Powered Outreach (auto-suggest on `sold` tag)
- Permission Roles/Templates
- Auth refactor (bcrypt)
- Push Notifications
- Voice Help Assistant
- Google Places API (when key available)

### P2
- Full Twilio, WhatsApp, Training Hub, Inventory Module, Code cleanup

## Known Issues
- P1: Production email blocked (user: verify RESEND_API_KEY)
- P2: React Hydration Error #418, Mobile tags sync

## Test Credentials
- Super Admin: `forest@imosapp.com` / `Admin123!`
