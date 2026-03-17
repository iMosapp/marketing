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

### Campaign Task Catch-Up Mechanism (Mar 17, 2026)
- **CRITICAL FIX:** Overdue campaign steps now create tasks in Today's Touchpoints even if the scheduler missed them
- Added `_catchup_overdue_campaign_tasks()` function in `tasks.py` that runs on home screen load
- Detects active enrollments with `next_send_at <= now` that have no corresponding pending task
- Creates missing tasks with proper idempotency keys and pending_send records
- Called from both `GET /tasks/{user_id}/summary` and `GET /tasks/{user_id}?filter=today`

### Scheduler DuplicateKeyError Fix (Mar 17, 2026)
- **CRITICAL FIX:** Scheduler no longer gets permanently stuck when a task already exists for a campaign step
- Before: DuplicateKeyError on `tasks.insert_one` would prevent enrollment advancement, causing infinite retry loop
- After: Checks for existing task first; if found, logs and skips task creation but STILL advances enrollment to next step
- Prevents orphaned `campaign_pending_sends` from accumulating

### PRD in Company Docs (Mar 17, 2026)
- PRD document viewable and editable inside the app under Company Docs > PRD tab
- Backend: `GET /api/docs/prd` (auto-seeds from PRD.md), `PUT /api/docs/prd` updates content
- Frontend: Dedicated PRD page at `/admin/docs/prd` with rendered markdown view and edit mode
- Auto-sync on server startup: reads PRD.md and updates DB if content changed

### Campaign Scheduler Hourly Delay Bug Fix (Mar 17, 2026)
- Randomization now only applies when `delay_days > 0` or `delay_months > 0`

### Campaign AI Toggle Fix (Mar 17, 2026)
- Per-campaign `ai_enabled` flag is now the primary control

### Campaign Journey on Contact Page (Mar 17, 2026)
- Campaign progress timeline on contact detail page
- Backend endpoint: `GET /api/contacts/{user_id}/{contact_id}/campaign-journey`

### Logout Cookie Cleanup Fix (Mar 17, 2026)
- `/auth/logout` now clears both `imonsocial_session` AND `imonsocial_uid` cookies

---

## Key API Endpoints
- `GET /api/docs/prd` -- PRD document (auto-seeds from PRD.md)
- `PUT /api/docs/prd` -- Update PRD content
- `GET /api/tasks/{user_id}/summary` -- Daily summary (now includes catch-up)
- `GET /api/tasks/{user_id}?filter=today` -- Today's tasks (now includes catch-up)
- `POST /api/scheduler/trigger/campaign-steps` -- Manual scheduler trigger
- `GET /api/contacts/{user_id}/{contact_id}/campaign-journey` -- Campaign progress timeline
- `POST /api/auth/login` -- Case-insensitive email, trimmed
- `GET /api/auth/me` -- Full session restore from cookie
- `POST /api/auth/logout` -- Clears both cookies

## Key DB Schema
- `users.role` -- May be: super_admin, org_admin, admin, store_manager, manager, user
- `company_docs` -- slug: "product-requirements-document" stores the PRD
- `campaign_enrollments` -- status, current_step, next_send_at drive the scheduler
- `tasks.idempotency_key` -- Unique partial index, prevents duplicate campaign tasks

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
