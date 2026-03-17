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

### PRD in Company Docs with PDF Export (Mar 17, 2026)
- PRD document viewable and editable inside the app under Company Docs > PRD tab
- Backend: `GET /api/docs/prd` (auto-seeds from PRD.md), `PUT /api/docs/prd` updates content
- Backend: `GET /api/docs/prd/pdf` generates downloadable PDF (5 pages, formatted headings/bullets/page numbers)
- Frontend: Dedicated PRD page at `/admin/docs/prd` with rendered markdown view, edit mode, and download button
- Auto-sync on server startup: reads PRD.md and updates DB if content changed
- All navigation paths (chip, category card, doc list item) correctly route to PRD page

### Campaign Task Catch-Up Mechanism (Mar 17, 2026)
- **CRITICAL FIX:** Overdue campaign steps now create tasks in Today's Touchpoints even if the scheduler missed them
- `_catchup_overdue_campaign_tasks()` runs on home screen load (GET /tasks/summary, GET /tasks?filter=today)
- Detects active enrollments with `next_send_at <= now` without corresponding pending tasks
- Creates missing tasks with proper idempotency keys and pending_send records

### Scheduler DuplicateKeyError Fix (Mar 17, 2026)
- **CRITICAL FIX:** Scheduler no longer gets permanently stuck when a task already exists for a campaign step
- Checks for existing task first; if found, skips task creation but STILL advances enrollment to next step

### Campaign Scheduler Hourly Delay Bug Fix (Mar 17, 2026)
- Randomization now only applies when `delay_days > 0` or `delay_months > 0`

### Campaign AI Toggle Fix (Mar 17, 2026)
- Per-campaign `ai_enabled` flag is now the primary control

### Campaign Journey on Contact Page (Mar 17, 2026)
- Campaign progress timeline on contact detail page

### Logout Cookie Cleanup Fix (Mar 17, 2026)
- `/auth/logout` now clears both `imonsocial_session` AND `imonsocial_uid` cookies

---

## Key API Endpoints
- `GET /api/docs/prd` -- PRD document (auto-seeds from PRD.md)
- `PUT /api/docs/prd` -- Update PRD content
- `GET /api/docs/prd/pdf` -- Generate and download PRD as PDF
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

---

## White-Label Partner Sold Workflow System

**Product:** i'M On Social
**Scope:** Partner-Level Sold Event Overrides (Non-Disruptive to Core Platform)

### 1. Objective

Enable white-label partners to define custom sold-event requirements, integrations, and review experiences without impacting the standard platform workflow.

**Core Principle:**
The platform must operate exactly the same for all users until a Sold tag is applied. All partner-specific behavior is:
- Event-driven (triggered by Sold)
- Configuration-based (not hardcoded)
- Isolated from core platform logic

### 2. Core System Concept

Introduce a Partner Configuration Layer that applies rules only during the Sold event lifecycle. This layer controls:
- Required data validation
- External data delivery
- Review page experience
- Partner-specific workflows

### 3. High-Level Behavior

**Standard Usage:**
- Contacts, messaging, campaigns, etc. behave normally
- No additional required fields
- No partner-specific friction

**Sold Event Trigger:**
When a Sold tag is applied:
- System evaluates partner configuration
- Enforces required fields
- Triggers integrations
- Applies review experience overrides

### 4. Sold Event Flow

**Flow Overview:**
User applies Sold tag -> System checks for partner -> System checks sold workflow enabled -> Validate required fields -> If fail: prompt user / If pass: save sold event -> Build payload (if enabled) -> Send to partner endpoint -> Load review page (global or custom) -> Complete workflow

**Detailed Flow Steps:**

**Step 1: Sold Tag Applied**
- User applies Sold tag to contact

**Step 2: Partner Check**
- If no `partner_id` -> standard flow
- If yes -> continue

**Step 3: Sold Workflow Toggle**
- If `sold_workflow_enabled = false` -> standard flow
- If true -> begin validation

**Step 4: Validation**
- Check required fields:
  - Customer name
  - Phone number
  - Full-size image (if enabled)
  - Deal OR stock number (if enabled)
  - External account ID (if enabled)

**Step 5: Validation Outcome**
- Fail: block workflow, show UI prompt
- Pass: proceed to processing

**Step 6: Payload Build**
- Construct payload using:
  - Account + external ID
  - Customer data
  - Image URL
  - Deal/stock number
  - Timestamp

**Step 7: Endpoint Delivery**
- Send payload if enabled
- Log response
- Retry on failure

**Step 8: Review Page Selection**
- Global default OR partner template

**Step 9: Complete Workflow**
- Mark sold complete
- Update status fields

### 5. Validation Logic

```
IF account.partner_id exists
AND partner.sold_workflow_enabled = true
AND Sold tag applied

THEN require configured fields

IF missing -> block + prompt
IF complete -> proceed
```

### 6. Database Architecture

**6.1 White Label Partners** (`white_label_partners`)
- `id`
- `name`
- `status`
- `branding` (colors, logo)
- Sold Workflow:
  - `sold_workflow_enabled`
  - `sold_requires_full_size_image`
  - `sold_requires_customer_name`
  - `sold_requires_phone_number`
  - `sold_requires_deal_or_stock_number`
- External Delivery:
  - `sold_external_endpoint_enabled`
  - `sold_external_endpoint_url`
  - `external_account_id_required`
  - `external_auth_type`
  - `external_auth_value_encrypted`
- Review Page:
  - `sold_review_page_mode`
  - `sold_review_page_template_id`

**6.2 Accounts** (`accounts`)
- `id`
- `partner_id`
- `external_account_id`
- `review_page_override_enabled`
- `review_page_template_id`

**6.3 Contacts** (additions to existing `contacts`)
- `full_size_image_url`
- `deal_number`
- `stock_number`
- `sold_tag_applied_at`
- `sold_workflow_status`
- `sold_workflow_last_error`

**6.4 Sold Event Logs** (`sold_event_logs`)
- `id`
- `contact_id`
- `account_id`
- `partner_id`
- `external_account_id`
- `validation_status`
- `missing_fields`
- `payload_snapshot`
- `delivery_status`
- `delivery_attempt_count`
- `last_delivery_response_code`
- `timestamps`

**6.5 Review Templates** (`review_page_templates`)
- `id`
- `scope` (global / partner / account / user)
- `partner_id` / `account_id` / `user_id`
- `layout_config`
- `content_config`
- `styling_config`

### 7. External Payload Structure

```
{
  "account_id": "",
  "external_account_id": "",
  "customer_name": "",
  "phone_number": "",
  "deal_number": "",
  "stock_number": "",
  "full_size_image_url": "",
  "event": "sold",
  "timestamp": ""
}
```

**Rules:**
- Only include enabled fields
- Must include `external_account_id` if required
- Must support retries
- Must not block UI permanently

### 8. UI/UX: Missing Data Prompts

**Modal Title:** Complete Sold Details
**Description:** This partner requires additional details before completing the Sold workflow.

**Field Prompts:**
- **Customer Name:** Customer name is required to complete this Sold record.
- **Phone Number:** Phone number is required to complete this Sold record.
- **Full-Size Image:** A full-size image is required for this Sold workflow. Upload a high-resolution image for print use.
- **Deal / Stock Number:** Enter either a deal number or stock number to continue.
- **External Account ID:** This account is missing its partner store ID. Contact an admin or update account settings.

**Error Summary:** Missing Required Sold Information: [dynamic list of missing fields]

**Actions:**
- Save and Continue
- Cancel Sold Tag

**Success Messages:**
- Full success: Sold workflow completed successfully.
- Partial success: Sold saved. Partner delivery is retrying in the background.

### 9. Admin Settings Layout

**Internal Operations -> White Label Partners**

**List View:**
- Name
- Status
- Accounts count
- Sold workflow enabled
- Endpoint enabled

**Partner Detail Page:**
- Section A: Profile (name, branding)
- Section B: Sold Workflow (enable sold workflow, required fields toggles)
- Section C: Endpoint (enable endpoint, URL, auth settings)
- Section D: Review Page (global vs custom, template selector)

**Account Settings -> White Label Section:**
- Partner name
- External account ID
- Review override toggle
- Template selector (optional)

### 10. Permissions

- **Internal Admin:** Full control
- **Account Admin:** Edit account mapping, view workflow status
- **Sales Users:** Apply Sold tag, complete required prompts

### 11. System Rules

**Do NOT:**
- Enforce required fields globally
- Modify standard workflows
- Hardcode partner logic

**DO:**
- Enforce rules only on Sold
- Use configuration-driven logic
- Keep system modular
- Log all events and deliveries

### 12. Status Definitions

**Contact Workflow Status:**
- `not_applicable`
- `pending_validation`
- `validated`
- `delivery_pending`
- `delivery_success`
- `delivery_failed`

**Delivery Status:**
- `not_sent`
- `queued`
- `sent`
- `failed`
- `retrying`

### 13. Architecture Principles

- Configuration over customization
- Event-driven logic
- Scalable to multiple partners
- Backward compatible
- No partner-specific code branches

### 14. Final Summary

The system must implement a partner-configurable, event-driven Sold workflow where:
- All normal usage remains unchanged
- Partner rules activate only at Sold
- Required data is enforced at that moment
- Integrations and review experiences are dynamically applied
- All logic is driven by partner configuration, not hardcoding

**Final Note to Dev Team:**
Build this as a scalable partner framework, not a one-off solution. Every decision should assume multiple partners with different requirements will exist.
