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
- Admin Dashboard → Internal Administration → "Migrate All Images" button (super admin only)

---

## CRITICAL: Unified Card System — DO NOT REVERT

**ALL card types (congrats, birthday, anniversary, thankyou, welcome, holiday) MUST use `congrats_cards.py`.**

### Architecture:
- `congrats_cards.py` is the SINGLE router for all card types
- `auto_create_card(user_id, contact_id, card_type="birthday")` creates cards in `congrats_cards` collection
- GET endpoints check `congrats_cards` first, then fall back to legacy `birthday_cards` collection
- `birthday_cards.py` is LEGACY — its router is NOT registered in `server.py`
- Scheduler, date_triggers, and tags all import from `congrats_cards.auto_create_card`

### NEVER DO:
- Import from `birthday_cards.py` — always use `congrats_cards.auto_create_card`
- Create new cards in the `birthday_cards` collection
- Re-register the `birthday_cards.router` in `server.py`

---

## What's Been Implemented

### Unified Card System (Mar 2026)
- Consolidated birthday_cards into congrats_cards as single unified system
- All card types: congrats, birthday, anniversary, thankyou, welcome, holiday
- Backward-compatible: old birthday cards still accessible via fallback queries
- All auto-creation triggers updated (scheduler, date_triggers, tags)
- Frontend birthday page uses unified /api/congrats/card/{cardId} endpoint

### Image Migration Admin Button (Mar 2026)
- Super admin "Migrate All Images" button in Admin Dashboard → Internal Administration
- Calls POST /api/images/migrate-all-base64 with loading/success feedback

### Image Performance — Complete Platform Overhaul (Feb 2026)
- Showcase, Digital Card, Congrats/Birthday Card, Landing Page, Profile, Contact Gallery
- Batch migration endpoint, lazy migration, shared helper, $nin bug fixed

### Operations Manual v3.0 & PDF Export — COMPLETE
### Streamlined Client Onboarding — COMPLETE
### Admin Cleanup — Onboarding removed from admin areas
### Carrier-Agnostic Messaging — Personal SMS fallback
### Comprehensive Reporting System — Activity metrics with email delivery
### White-Label Branded Emails — Dynamic HTML templates

## Prioritized Backlog

### P1
- Google Places API (when key available), Permission Roles/Templates
- AI-Powered Outreach, Auth refactor (bcrypt), Push Notifications
- Gamification & Leaderboards, Voice Help Assistant

### P2
- Full Twilio, WhatsApp, Training Hub, Inventory Module, Code cleanup

## Known Issues
- P1: Production email blocked (user: verify RESEND_API_KEY)
- P2: React Hydration Error #418, Mobile tags sync

## Test Credentials
- Super Admin: `forest@imosapp.com` / `Admin123!`
