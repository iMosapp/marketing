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
- ALL images go through `utils/image_storage.py` -> WebP format -> served via `/api/images/`
- `utils/image_urls.py` resolves all photo URLs
- Immutable caching on all `/api/images/` responses
- All uploads use `asyncio.to_thread()` to prevent 520 timeouts
- EXIF orientation fixed BEFORE pre-shrink in `congrats_cards.py`
- **NEVER add `data:` / base64 fallbacks anywhere.**
- **NEVER serve base64 in API responses.**
- **NEVER add lazy migration during reads.**

### Unified Card System — DO NOT REVERT
- ALL card types use `congrats_cards.py` only
- `birthday_cards.py` is LEGACY — NOT registered in server.py

### General Rules for ALL Agents
- **READ THIS PRD FIRST** before writing any code.
- **DO NOT revert completed migrations.**
- **Speed is the #1 priority.**
- **When fixing a bug, do NOT introduce old patterns.**

---

## What's Been Implemented

### User-Specific Brand Kit & Theming (Mar 14, 2026) — LATEST
- **Backend:** `BrandKitUpdate` Pydantic model includes `page_theme` field (dark/light)
- **Backend:** `GET /api/card/data/{userId}` now returns `brand_kit` object with `page_theme`, `primary_color`, `secondary_color`, `accent_color`, `logo_url`, `company_name`
- **Backend:** Brand kit cascades: user -> store -> organization fallback
- **Frontend (Settings):** Brand Kit page at `/settings/brand-kit` has Light/Dark theme toggle with visual previews
- **Frontend (Card):** Digital Card page at `/card/{userId}` dynamically themes based on `brand_kit.page_theme`
- **Theming:** `buildTheme()` function creates full palette (bg, card, text, accent, etc.) for light/dark modes
- **Theming:** `getDynamicStyles()` creates theme-dependent StyleSheet for interactive elements
- **Accent Colors:** User's primary/accent color applied to photo borders, dividers, titles, CTA buttons, section headers
- **Tested:** 100% backend (10 pytest tests), 100% frontend (iteration 204)

### Auth: Persistent Login (Mar 14, 2026)
- 3-layer auth persistence: AsyncStorage, IndexedDB, readable cookie
- Fixed onboarding loop for existing users
- Fixed user setup wizard credentials and email invites

### UI/UX Fixes (Mar 14, 2026)
- Bottom nav bar stabilized with standard iOS styling
- Contacts page header compacted
- Removed floating action button from touchpoints
- OG image previews fixed for all shareable links
- Document auto-deduplication
- Cookie/storage keys renamed from `imos_` to `imonsocial_`

### My Presence Visual Command Center (Mar 13, 2026)
- Rebuilt "My Account" into "My Presence" visual hub
- 5 presence cards with mini-previews: Digital Card, Showcase, Review Link, Link Page, Landing Page

### Previous Features (see CHANGELOG.md for full history)
- Voice Memo Intelligence + Campaign Config + Full AI Pipeline
- AI-Powered Outreach + Sold Campaign Intelligence
- Card Analytics Dashboard, Digital Card Sharing with QR codes
- Performance Dashboard with clickable tiles
- CRM Timeline Export, Duplicate Contact Merge
- Hub Navigation, ChannelPicker, Auth Refactor (bcrypt)
- Jessi AI Assistant v2.0, Account Health Dashboard
- Instagram-Style Photo Gallery, EXIF Orientation Fix
- And 50+ more features and bug fixes

---

## Key API Endpoints
- `GET /api/card/data/{userId}` — Digital card data with brand_kit theming
- `GET /api/email/brand-kit/{entity_type}/{entity_id}` — Get brand kit settings
- `PUT /api/email/brand-kit/{entity_type}/{entity_id}` — Update brand kit settings (includes page_theme)
- `GET /api/contacts/{user_id}/{contact_id}/photos/all` — Fast read-only gallery photos
- `POST /api/contacts/{user_id}/find-or-create-and-log` — Create/find + log with event_channel

## Key DB Collections
- `users.email_brand_kit` — Stores `page_theme`, `primary_color`, `secondary_color`, `accent_color`, etc.
- `contact_events` — Stores `channel` field (sms, whatsapp, email, messenger, etc.)
- `congrats_cards` — Photo paths used by gallery

---

## Prioritized Backlog

### P1
- Onboarding Task List for new salespeople
- Gamification & Leaderboards
- AI-Powered Outreach (contextual follow-up on "sold" tag)
- Lead Notification System Phase 2 (push notifications)
- Voice Help Assistant Backend

### P2
- Full Twilio Integration (currently MOCK)
- WhatsApp Integration
- Training Hub video content
- Inventory Management Module
- Refactor large files (admin.py 3600+ lines, contact/[id].tsx 5600+ lines)
- Extend theming to other public pages (Link Page /l/{userId}, Landing Page /p/{userId}, Showcase)

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
