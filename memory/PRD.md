# i'M On Social — Product Requirements Document

## Original Problem Statement
Build a Relationship Management System (RMS) / CRM for automotive sales professionals. The vision: AI-powered, human-to-human relationship building where every follow-up is deliberate, meaningful, and personal. Salespeople record voice memos, and the system extracts personal details (family, interests, vehicle info) to power AI-generated campaign messages that nurture long-term relationships for repeat and referral business.

## Core Architecture
- **Frontend:** React Native / Expo (web)
- **Backend:** FastAPI (Python)
- **Database:** MongoDB Atlas
- **Integrations:** Resend (email), Twilio (MOCKED), OpenAI (GPT-5.2 via emergentintegrations), Emergent Object Storage, Pillow

---

## CRITICAL: Image Pipeline Rules — DO NOT REVERT
- ALL images use `utils/image_storage.py` + `utils/image_urls.py` resolvers
- WebP format, served via `/api/images/` with immutable caching
- All uploads use `asyncio.to_thread()` to prevent 520 timeouts

## CRITICAL: Unified Card System — DO NOT REVERT
- ALL card types use `congrats_cards.py` only
- `birthday_cards.py` is LEGACY — NOT registered in server.py

---

## What's Been Implemented

### Share Channel Tracking (Mar 13, 2026) — LATEST
- **NEW FEATURE:** When sharing digital cards, review links, showcases, or any content, the sharing channel (SMS, WhatsApp, Email, Messenger, Telegram, LinkedIn, Clipboard) is now tracked and displayed in the activity feed.
- **Backend:** `POST /api/contacts/{user_id}/{contact_id}/events` and `POST /api/contacts/{user_id}/find-or-create-and-log` now accept and store a `channel` field in `contact_events`.
- **Frontend Activity Feed:** Events with a channel show a colored badge next to the event title (e.g., green "SMS" badge, green "WhatsApp" badge, orange "Email" badge).
- **Frontend Contact Detail:** Expanded events show channel badges with appropriate icons for all 7 channel types.
- **Files updated:** `contact_events.py`, `activity.tsx`, `contact/[id].tsx`, `more.tsx`, `UniversalShareModal.tsx`, `create-card.tsx`, `touchpoints/index.tsx`, `dialer.tsx`
- **Tested:** 18/18 backend tests + 100% frontend verified (iteration 201)

### Lead Sources API 500 Fix (Mar 13, 2026) — LATEST
- **BUG FIXED:** `GET /api/lead-sources/team-inbox/{team_id}`, `/user-inbox/{user_id}`, and `/stats/{source_id}` were caught by the generic `/{source_id}` route, causing 500 errors when trying to convert route names like "team-inbox" to ObjectId.
- **Fix:** Reordered routes in `lead_sources.py` — specific path routes now defined before the generic `/{source_id}` catch-all.
- **Tested:** All 3 routes return correct responses (200/404 as appropriate).

### Previous Features (see CHANGELOG.md for full history)
- Voice Memo Intelligence + Campaign Config + Full AI Pipeline
- AI-Powered Outreach + Sold Campaign Intelligence
- Card Analytics Dashboard, Card Labeling Bug Fix
- Digital Card Sharing Redesign with QR codes
- Performance Dashboard with clickable tiles
- CRM Timeline Export with PIN protection
- Duplicate Contact Merge Tool
- Hub Navigation Reorganization
- Configurable Messaging Channels (ChannelPicker)
- Auth Refactor (bcrypt), Persistent Sessions, Web Push Notifications
- Jessi AI Assistant (v2.0 with live data awareness)
- Account Health Dashboard with scheduled reports
- And 50+ more features and bug fixes

---

## Key API Endpoints
- `POST /api/contacts/{user_id}/{contact_id}/events` — Log event with optional `channel` field
- `POST /api/contacts/{user_id}/find-or-create-and-log` — Create/find contact and log event with optional `event_channel`
- `GET /api/contacts/{user_id}/master-feed` — Activity feed with channel badges
- `GET /api/lead-sources/team-inbox/{team_id}` — Fixed route ordering
- `GET /api/lead-sources/user-inbox/{user_id}` — Fixed route ordering

## Key DB Collections
- `contact_events` — Now stores `channel` field (e.g., 'sms', 'whatsapp', 'email')
- `contacts.personal_details` — Structured personal data from voice memos
- `campaign_configs` — Hierarchical campaign configuration

---

## Prioritized Backlog

### P1
- Onboarding Task List for new salespeople
- Voice Help Assistant
- Google Places API Integration
- App Store Deployment Setup

### P2
- Full Twilio Integration (currently MOCK)
- WhatsApp Integration
- Populate Training Hub with video content
- Inventory Management Module
- Refactor large monolithic files (admin.py, contact/[id].tsx)

## Known Issues
- P2: Mobile tags sync
- P2: Leaderboard toggle not fully tested
- P2: React Hydration Error #418

## Test Credentials
- Super Admin: `forest@imosapp.com` / `Admin123!`

## 3rd Party Integrations
- **Resend:** Transactional emails
- **MongoDB Atlas:** Primary database
- **Twilio:** Configured but in MOCK mode
- **OpenAI:** AI features via emergentintegrations
- **Pillow:** Image manipulation
- **qrcode:** QR code generation
- **apscheduler:** Backend job scheduling
