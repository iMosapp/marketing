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
- ALL images -> `utils/image_storage.py` -> WebP -> `/api/images/`
- NEVER add base64 fallbacks. NEVER serve base64 in responses.

### Role System
- DB may have legacy roles: `admin` (= `org_admin`), `manager` (= `store_manager`)
- Backend `permissions.py` maps both legacy and canonical role names
- Frontend `authStore.ts` normalizes roles via `normalizeUser()` on every user load
- NEVER add role checks that only match canonical names -- always handle both

### Auth Persistence (iOS PWA)
- 3-layer: AsyncStorage -> IndexedDB -> Cookie (`imonsocial_session`)
- `/auth/me` returns COMPLETE user data (same as login: permissions, store_slug, org_slug, partner_branding)
- Cookies refreshed on every `/auth/me` call
- Cookie restore retries once on network failure (cold-start resilience)
- Login does case-insensitive, trimmed email lookup
- Logout clears BOTH `imonsocial_session` and `imonsocial_uid` cookies

---

## What's Been Implemented

### PRD in Company Docs (Mar 17, 2026)
- **NEW FEATURE:** PRD document viewable and editable inside the app under Company Docs > PRD tab
- Backend: `GET /api/docs/prd` fetches PRD (auto-seeds from PRD.md if not in DB), `PUT /api/docs/prd` updates content
- Frontend: Dedicated PRD page at `/admin/docs/prd` with rendered markdown view and edit mode
- Markdown renderer supports H1/H2/H3 headings, bullet lists, inline code, bold text, horizontal rules
- Edit mode: textarea with raw markdown, Cancel/Save toolbar, Save disabled until changes detected
- PRD stored in `company_docs` collection with slug `product-requirements-document`

### Campaign Scheduler Hourly Delay Bug Fix (Mar 17, 2026)
- **CRITICAL FIX:** Campaign steps with hourly delays not firing on schedule
- Randomization now only applies when `delay_days > 0` or `delay_months > 0`

### Campaign AI Toggle Fix (Mar 17, 2026)
- Per-campaign `ai_enabled` flag is now the primary control

### Campaign Journey on Contact Page (Mar 17, 2026)
- **NEW FEATURE:** Campaign progress timeline on contact detail page
- Backend endpoint: `GET /api/contacts/{user_id}/{contact_id}/campaign-journey`

### Logout Cookie Cleanup Fix (Mar 17, 2026)
- `/auth/logout` now clears both `imonsocial_session` AND `imonsocial_uid` cookies

---

## Key API Endpoints
- `GET /api/docs/prd` -- PRD document (auto-seeds from PRD.md)
- `PUT /api/docs/prd` -- Update PRD content
- `GET /api/contacts/{user_id}/{contact_id}/campaign-journey` -- Campaign progress timeline
- `POST /api/auth/login` -- Case-insensitive email, trimmed
- `GET /api/auth/me` -- Full session restore from cookie
- `POST /api/auth/logout` -- Clears both cookies

## Key DB Schema
- `users.role` -- May be: super_admin, org_admin, admin, store_manager, manager, user
- `company_docs` -- slug: "product-requirements-document" stores the PRD

---

## Prioritized Backlog

### P1
- Gamification & Leaderboards
- AI-Powered Outreach (contextual follow-up on "sold" tag)
- Lead Notification System Phase 2 (push notifications)
- Voice Help Assistant Backend
- Refactor Authentication (bcrypt)

### P2
- Full Twilio Integration (currently MOCK)
- WhatsApp Integration
- Training Hub video content
- Inventory Management Module
- Refactor large files (admin.py 3700+ lines)

## Known Issues
- P2: Mobile tags sync
- P2: React Hydration Error #418
- P2: Leaderboard toggle not fully tested

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
