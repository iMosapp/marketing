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

### Auth Persistence (iOS PWA)
- 3-layer: AsyncStorage -> IndexedDB -> Cookie (`imonsocial_session`)
- Logout clears BOTH `imonsocial_session` and `imonsocial_uid` cookies

---

## What's Been Implemented

### White-Label Partner Sold Workflow System (Mar 17, 2026) -- NEW
**Backend (`/app/backend/routers/sold_workflow.py`):**
- `process_sold_workflow()` — main entry point called AFTER tag saves (never blocks)
- `is_sold_tag()` — canonical detection: `tag.strip().lower() == "sold"`
- `sold_tag_just_added()` — compares old vs new tags
- `_resolve_partner_config()` — user -> store -> org -> partner chain
- `_validate_sold_fields()` — checks partner's `sold_required_fields` array
- `revalidate_sold_workflow()` — re-runs validation after user fixes fields
- `deliver_sold_event()` — POSTs payload to partner endpoint with auth
- `process_queued_sold_deliveries()` — background job (every 5 min via APScheduler)
- Idempotency: no duplicate events for same contact when active event exists

**Hooks in contacts.py (3 locations, all non-blocking):**
- `POST /contacts/{user_id}` (create) — trigger_source="create"
- `PUT /contacts/{user_id}/{contact_id}` (update) — trigger_source="update"
- `PATCH /contacts/{user_id}/{contact_id}/tags` (tag patch) — trigger_source="tag_patch"

**API Endpoints:**
- `POST /api/sold-workflow/revalidate/{contact_id}` — re-validate after fixing fields
- `POST /api/sold-workflow/retry/{log_id}` — admin manual retry
- `GET /api/sold-workflow/contact/{contact_id}` — sold event history
- `GET /api/sold-workflow/partner/{partner_id}/events` — all partner events

**Database Schema:**
- `white_label_partners` — added: `sold_workflow_enabled`, `sold_required_fields[]`, `external_account_id_required`, `event_delivery{enabled, endpoint_url, auth_type, auth_value_encrypted}`
- `stores` (accounts) — added: `external_account_id`, `deal_or_stock_mode`
- `contacts` — added: `sold_tag_applied_at`, `sold_workflow_status`, `sold_workflow_event_id`, `sold_workflow_processed_at`, `sold_workflow_last_error`, `sold_validation_missing_fields[]`, `deal_number`, `stock_number`, `full_size_image_url`
- `sold_event_logs` — NEW collection: full audit trail with idempotency_key, payload snapshot, delivery status, retry tracking

**Frontend:**
- `SoldWorkflowModal.tsx` — missing-data prompt modal with dynamic field inputs
- Contact detail page — sold workflow status badge with Fix & Complete / Retry buttons
- White Label Partners admin — sold workflow config section (toggle, required fields, endpoint)

**Behavior Rules:**
- Sold tag ALWAYS saves (never blocked)
- date_sold set ONLY if currently empty
- Non-partner users: zero impact, sold_workflow is null
- Idempotency: one active event per contact unless failed/retryable
- Validation failed: status logged, user prompted, can fix and re-trigger
- Delivery: background queue with 3x retry, 15-min backoff

### PRD in Company Docs with PDF Export (Mar 17, 2026)
- PRD viewable/editable in-app under Company Docs > PRD tab
- Auto-sync on server startup from PRD.md
- PDF download generates formatted multi-page document

### Campaign Task Catch-Up Mechanism (Mar 17, 2026)
- Overdue campaign steps auto-create tasks when home screen loads

### Scheduler DuplicateKeyError Fix (Mar 17, 2026)
- Handles existing tasks gracefully, still advances enrollment

---

## Key API Endpoints
- `PATCH /api/contacts/{user_id}/{contact_id}/tags` — triggers sold workflow if Sold tag added
- `POST /api/sold-workflow/revalidate/{contact_id}` — re-validate sold workflow
- `POST /api/sold-workflow/retry/{log_id}` — manual delivery retry
- `GET /api/sold-workflow/contact/{contact_id}` — sold event history
- `GET /api/docs/prd` / `PUT /api/docs/prd` / `GET /api/docs/prd/pdf`
- `GET /api/tasks/{user_id}/summary` — includes catch-up mechanism

## Key DB Schema
- `white_label_partners` — sold workflow config + event delivery settings
- `stores` — `external_account_id`, `deal_or_stock_mode`
- `contacts` — sold workflow fields (status, event_id, missing_fields, etc.)
- `sold_event_logs` — full audit trail with delivery tracking
- `tasks.idempotency_key` — unique partial index

---

## Prioritized Backlog

### P0 (Completed)
- White-Label Partner Sold Workflow — IMPLEMENTED, needs production testing with Calendar Systems
- Partner Orgs Page Fix — FIXED (Mar 17, 2026): Created missing `/admin/partner-orgs.tsx` page for managing partner organizations & accounts.
- Create Partner Button Fix — FIXED (Mar 17, 2026): Two bugs: (1) `TouchableOpacity` on iOS Safari wouldn't fire clicks — replaced with native `<button>` on web. (2) Validation silently failed with no feedback when name/slug were empty — now shows alert.
- Campaign Manual Step "Sent" Bug — FIXED (Mar 18, 2026): For manual campaigns, step 1 was incorrectly marked as "sent" when the scheduler created the task. Now uses `status: "pending"` with `queued_at` in `messages_sent` until user actually completes the task. Campaign Journey shows "Ready to Send" for pending steps. Task completion updates enrollment from pending to sent.

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
- Review Page Templates (partner-specific, for future)

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
- **apscheduler:** Backend job scheduling (9 jobs including sold delivery processor)

---

## White-Label Partner Sold Workflow System (Full Spec)

### 1. Objective
Enable white-label partners to define custom sold-event requirements, integrations, and review experiences without impacting the standard platform workflow.

**Core Principle:** The platform operates exactly the same for all users until a Sold tag is applied. All partner-specific behavior is event-driven, configuration-based, and isolated from core platform logic.

### 2. Sold Event Flow
1. User applies Sold tag
2. System checks for partner (user -> store -> org -> partner_id)
3. System checks sold_workflow_enabled
4. Validate required fields from partner.sold_required_fields array
5. If fail -> sold tag still saves, date_sold still sets, workflow marked validation_failed, UI prompts user
6. If pass -> create sold_event_log, build payload, queue background delivery
7. Load review page (global or custom) [FUTURE]
8. Complete workflow

### 3. Validation Logic
- Required fields checked from partner.sold_required_fields array
- deal_or_stock_number: checks deal_number or stock_number based on account's deal_or_stock_mode
- external_account_id: delivery-blocking but NOT tag-blocking
- Sold tag always saves. date_sold set only if empty.

### 4. External Payload Structure
```json
{
  "event": "sold",
  "timestamp": "ISO datetime",
  "account_id": "store._id",
  "external_account_id": "store.external_account_id",
  "customer_name": "first_name + last_name",
  "phone_number": "contact.phone",
  "deal_number": "or stock_number based on mode",
  "full_size_image_url": "permanent accessible URL"
}
```

### 5. Status Definitions
- Contact: not_applicable, validation_failed, validated, delivery_pending, delivery_success, delivery_failed
- Delivery: not_sent, queued, sent, failed, retrying

### 6. Architecture Principles
- Configuration over customization
- Event-driven logic
- Scalable to multiple partners
- Backward compatible
- No partner-specific code branches
