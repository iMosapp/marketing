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
- Campaign Manual Step "Sent" Bug — FIXED (Mar 18, 2026): For manual campaigns, step 1 was incorrectly marked as "sent" when the scheduler created the task. Now uses `status: "pending"` with `queued_at` in `messages_sent` until user actually completes the task. Campaign Journey shows "Ready to Send" for pending steps.
- Interactive Campaign Journey — IMPLEMENTED (Mar 18, 2026):
  - Campaigns collapsed by default on contact page (tap header to expand)
  - Tappable "Ready to Send" / "Next Up" steps open action modal with full message text
  - "Copy Message" button copies to clipboard, "Mark as Sent" updates enrollment + task + activity log in one action
  - Legacy data cross-referenced with task/pending_send status for accurate display
  - New endpoint: POST /api/contacts/{uid}/{cid}/campaign-journey/mark-sent
- Partner Admin Access & Billing System — IMPLEMENTED (Mar 18, 2026):
  - RBAC: org_admin users linked to a partner now see ALL partner orgs, stores, and users (not just their own)
  - New orgs created by partner admins auto-link to partner (partner_id)
  - New stores auto-inherit partner_id from their org
  - Layer 1 Billing: Super admin sets negotiated pricing per partner (per_org, per_store, per_seat, custom + carrier add-ons)
  - Layer 2 Billing: Partner admins create billing records for their clients (flexible models)
  - Billing summary dashboard shows active org/store/seat counts + estimated monthly per partner
- Partner Admin UI Access — FIXED (Mar 18, 2026):
  - Login/me endpoints now include `partner_id` in user object when user belongs to a partner org
  - Frontend More tab detects `user.partner_id` to show Account Management section
  - Partner admins see: Organizations, Accounts, Users, Onboarding Hub, Account Health, Leaderboard, Activity Feed
  - Super admin-only items (Admin Dashboard, Individuals, Pending Users, Lead Attribution) hidden for partners
  - Partner admin org_admin role + partner_id = full partner-scoped access
- Partner Dropdown on Create Organization — IMPLEMENTED (Mar 18, 2026):
  - Super admins see a "White-Label Partner" dropdown in the Create Organization modal
  - Dropdown fetches all partners from `GET /api/admin/partners`
  - Selecting a partner sends `partner_id` in the create org payload
  - Backend auto-links org to partner's `organization_ids` list
  - "None (No Partner)" option available for standalone orgs
  - Non-super-admin users don't see the dropdown
- Delete Confirmation Dialogs Audit & Fix — IMPLEMENTED (Mar 18, 2026):
  - CRITICAL FIX: White-label partner delete now requires confirmation with clear warning about consequences
  - Fixed: quotes.tsx delete/archive actions upgraded from raw `confirm()` to `showConfirm`
  - Fixed: invite-team.tsx member removal upgraded from `window.confirm` to `showConfirm`
  - Verified all other delete actions (orgs, users, contacts, campaigns, broadcasts, tags, templates, shared inboxes) already had proper confirmation dialogs
- White-Label Partner Admin Flow Fixed — IMPLEMENTED (Mar 18, 2026):
  - CRITICAL FIX: All 3 user creation endpoints (/users, /users/create, /users/add-team-member) now auto-inherit partner_id from the org
  - CRITICAL FIX: Impersonation endpoint now resolves partner_id from org if not directly on the user record
  - Result: Impersonated/logged-in partner admins now correctly see the full Account Management section

### P1
- Gamification & Leaderboards
- AI-Powered Outreach (contextual follow-up on "sold" tag)
- Lead Notification System Phase 2 (push notifications)
- Voice Help Assistant Backend
- Refactor Authentication (bcrypt)

### P2
- Rename `stores` → `accounts` throughout the codebase (user-requested)
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
