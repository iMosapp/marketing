# i'M On Social — Product Requirements Document

## Original Problem Statement
Build a Relationship Management System (RMS) / CRM for automotive sales professionals. AI-powered, human-to-human relationship building where every follow-up is deliberate, meaningful, and personal.

## Core Architecture
- **Frontend:** React Native / Expo (web)
- **Backend:** FastAPI (Python)
- **Database:** MongoDB Atlas
- **Integrations:** Resend (email), Twilio (MOCKED), OpenAI (via emergentintegrations), Emergent Object Storage, Pillow, qrcode

---

## CRITICAL RULES — READ BEFORE TOUCHING ANY CODE

### Image Pipeline — DO NOT REVERT, DO NOT ADD BASE64 FALLBACKS
- ALL images go through `utils/image_storage.py` → WebP format → served via `/api/images/`
- `utils/image_urls.py` resolves all photo URLs
- Immutable caching on all `/api/images/` responses
- All uploads use `asyncio.to_thread()` to prevent 520 timeouts
- EXIF orientation fixed BEFORE pre-shrink in `congrats_cards.py`
- **NEVER add `data:` / base64 fallbacks anywhere.** The entire database was migrated OFF base64. Adding it back destroys performance.
- **NEVER serve base64 in API responses.** Gallery, contact lists, card endpoints — ONLY `/api/images/` paths and `http` URLs.
- **NEVER add lazy migration during reads.** Gallery endpoint is pure read-only. No processing, no converting, no fallbacks.

### Unified Card System — DO NOT REVERT
- ALL card types use `congrats_cards.py` only
- `birthday_cards.py` is LEGACY — NOT registered in server.py

### General Rules for ALL Agents
- **READ THIS PRD FIRST** before writing any code. Understand what's been built and what the constraints are.
- **DO NOT revert completed migrations.** If data has been migrated to a new format, do NOT add backwards-compatible fallbacks to the old format.
- **Speed is the #1 priority.** Every API response, every image load, every page render must be as fast as possible.
- **When fixing a bug, do NOT introduce old patterns.** If you see old code that contradicts these rules, the old code is wrong — these rules are correct.

---

## What's Been Implemented

### My Presence Visual Command Center (Mar 13, 2026) — LATEST
- **REBUILT:** "My Account" page into "My Presence" visual hub
- Header changed from "My Account" to "My Presence"
- 5 presence cards with visual mini-previews: Digital Card, Showcase, Review Link, Link Page, Landing Page
- Each card shows a styled visual representation of the page (avatar+contacts, photo grid, stars, link pills, hero CTA)
- Preview panels are tappable — opens the actual page
- Action buttons render in horizontal rows: Preview, Edit, Copy Link, Manage, Approve, Share
- All navigation and clipboard functionality working
- **Tested:** 95% frontend pass (iteration 203)

### Photo Gallery — Speed + History (Mar 13, 2026)
- Gallery endpoint (`GET /photos/all`) ONLY serves `/api/images/` WebP paths and `http` URLs — ZERO base64
- Added photo history tracking: when a contact's profile photo is changed, the old WebP URL is saved to `photo_history` array
- Gallery includes historical photos going forward (only fast `/api/images/` and `http` paths)
- `PATCH /profile-photo` clears stale `photo_path` fields via `$unset` to ensure correct photo displays
- **Rule: NEVER add base64 data URLs to this endpoint. It was intentionally stripped out.**

### Instagram-Style Photo Gallery (Mar 13, 2026)
- **REBUILT:** Contact photo gallery from scratch with Instagram-style 3-column square grid
- Backend `/photos/all` endpoint rewritten to be pure read-only — no lazy migration during gallery load, instant response
- Photos preloaded when contact page mounts (gallery opens instantly on tap)
- Grid uses `onLayout` to measure actual container width for precise pixel-based tile sizing
- Gallery constrained to `maxWidth: 480px` on web, centered on desktop
- Profile photo shows gold badge overlay; non-profile photos show "Set as Profile" quick-action button
- Shimmer skeleton placeholders while loading
- Full-screen swipeable viewer with "Back to Grid" and "Set as Profile" actions
- **Tested:** 13/13 backend + 100% frontend (iteration 202)

### EXIF Orientation Fix (Mar 13, 2026)
- Fixed sideways iPhone photos in card upload pipeline
- `ImageOps.exif_transpose()` now applied BEFORE pre-shrink resize in `congrats_cards.py`
- Previously: EXIF stripped during JPEG pre-shrink → photos permanently sideways

### Channel Tracking in Composer (Mar 13, 2026)
- Added `PATCH /api/contacts/{user_id}/{contact_id}/events/latest-channel` endpoint
- Composer's `onSent(channelId)` now patches the event with the actual channel used (messenger, whatsapp, sms, etc.)

### Share Channel Tracking (Mar 13, 2026)
- Activity feed shows colored channel badges ("SMS", "WhatsApp", "Email", etc.)
- Backend stores `channel` field in `contact_events` via both `log_contact_event` and `find-or-create-and-log`
- All frontend sharing flows pass `event_channel` to backend

### Lead Sources API 500 Fix (Mar 13, 2026)
- Reordered routes in `lead_sources.py` — specific paths (`team-inbox`, `user-inbox`, `stats`) before generic `/{source_id}`

### Previous Features (see CHANGELOG.md for full history)
- Voice Memo Intelligence + Campaign Config + Full AI Pipeline
- AI-Powered Outreach + Sold Campaign Intelligence
- Card Analytics Dashboard, Digital Card Sharing with QR codes
- Performance Dashboard with clickable tiles
- CRM Timeline Export, Duplicate Contact Merge
- Hub Navigation, ChannelPicker, Auth Refactor (bcrypt)
- Jessi AI Assistant v2.0, Account Health Dashboard
- And 50+ more features and bug fixes

---

## Key API Endpoints
- `GET /api/contacts/{user_id}/{contact_id}/photos/all` — Fast read-only gallery photos
- `PATCH /api/contacts/{user_id}/{contact_id}/events/latest-channel` — Update event channel
- `POST /api/contacts/{user_id}/{contact_id}/events` — Log event with optional `channel`
- `POST /api/contacts/{user_id}/find-or-create-and-log` — Create/find + log with `event_channel`

## Key DB Collections
- `contact_events` — Stores `channel` field (sms, whatsapp, email, messenger, etc.)
- `congrats_cards` — Photo paths used by gallery
- `birthday_cards` — Photo paths used by gallery

---

## Prioritized Backlog

### P1
- Onboarding Task List for new salespeople
- Voice Help Assistant
- Google Places API Integration

### P2
- Full Twilio Integration (currently MOCK)
- WhatsApp Integration
- Training Hub video content
- Inventory Management Module
- Refactor large files (admin.py 3600+ lines, contact/[id].tsx 5600+ lines)

## Known Issues
- P2: Mobile tags sync
- P2: React Hydration Error #418

## Test Credentials
- Super Admin: `forest@imosapp.com` / `Admin123!`
- Contact with photos: `69a0c06f7626f14d125f8c34`

## 3rd Party Integrations
- **Resend:** Transactional emails
- **MongoDB Atlas:** Primary database
- **Twilio:** MOCK mode
- **OpenAI:** AI features via emergentintegrations
- **Pillow + ImageOps:** Image processing with EXIF handling
- **qrcode:** QR code generation
- **apscheduler:** Backend job scheduling
