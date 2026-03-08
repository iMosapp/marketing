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

### Voice Memo Intelligence + Campaign Config + Full AI Pipeline (Mar 2026) — LATEST

1. **Voice Memo Intelligence Extraction** (`services/voice_intel.py`)
   - When a voice note is recorded, AI automatically extracts: spouse name, kids, interests, occupation, vehicle details, trade-in, purchase context, pets, neighborhood, referral potential, communication preference
   - Auto-triggers on voice note save (fire-and-forget async task in `voice_notes.py`)
   - Extracted details merge into contact's `personal_details` field (existing data preserved, new data supplements)
   - Contact event logged for activity feed visibility

2. **Enhanced Contact Profile** (in `contacts.py`)
   - `GET /contacts/{user_id}/{contact_id}/personal-details` — View extracted details
   - `PATCH /contacts/{user_id}/{contact_id}/personal-details` — Manual edits (override AI)
   - `POST /contacts/{user_id}/{contact_id}/re-extract` — Re-run extraction on all voice notes
   - Frontend: `PersonalIntelSection` component on contact detail page shows all personal intel

3. **Campaign Configuration System** (`routers/campaign_config.py`)
   - **Message modes:** `ai_suggested` (AI crafts every message), `template` (hard-coded), `hybrid` (per-step)
   - **AI tone:** casual, warm, professional
   - **Data sources:** Toggle voice memo intel and engagement signals
   - **Delivery:** Review before send, auto-send (disabled until Twilio), auto-enroll on tag
   - **Hierarchy:** Org baseline → Store (primary) → User override (with permission)
   - Frontend: `/campaign-config` settings page with radio options, switches, level selector

4. **Relationship Intelligence Engine** (upgraded `services/relationship_intel.py`)
   - Now includes personal details from voice memos in both AI context and human summary
   - AI prompt includes: spouse name, kids, interests, vehicle details, referral potential
   - Human summary shows: "Personal: Spouse: Sarah / Kids: Jake, Emma / Interests: fly fishing"

5. **Campaign Message Generation** (upgraded)
   - Scheduler checks campaign config for message_mode before generating
   - `ai_suggested` mode overrides to always use AI, `template` mode forces templates
   - AI messages reference personal details for deeply personalized touchpoints

### AI-Powered Outreach + Sold Campaign Intelligence (Mar 2026)
- "Sold" tag triggers: AI suggestions (2 options) + auto campaign enrollment
- Relationship intelligence feeds into every campaign message
- Timezone-aware scheduling (9 AM next morning)
- Frontend `/ai-outreach` with 4 tabs: Campaign, AI Suggestions, Accepted, Dismissed

### Permission Templates + Template Delete Bug Fix + Touchpoint Totals Fix (Mar 8, 2026)
1. **Permission Templates System** (`routers/permission_templates.py`)
   - Full CRUD API: Create, Read, Update, Delete custom permission templates
   - 4 prebuilt templates: Sales Rep, Senior Rep, Sales Manager, Org Admin
   - Apply template to user: sets role + feature permissions in one click
   - Frontend: `/permission-templates` management page with create/edit modal, permission toggles, apply-to-user flow
   - Navigation: Added to admin Tools section
2. **Template Delete Bug Fix** (SMS + Email templates)
   - Fixed: `Alert.alert` on web degrades to `window.alert` without callback buttons
   - Now uses `window.confirm()` on web platform for delete confirmations
3. **Cleanup:** Deleted obsolete `birthday_cards.py` router file
4. **Touchpoint Totals Bug Fix** (`routers/tasks.py` summary endpoint)
   - Fixed: SMS sent, emails sent, calls placed, cards shared, and reviews sent were NOT counted in `total_today` / `completed_today`
   - Root cause: Summary only counted items from `tasks` collection, not `contact_events` activity
   - Fix: Activity touchpoints (SMS, email, calls, cards, reviews) now add to both `total_today` and `completed_today`
5. **Template Audit Log** (`permission_audit_log` collection)
   - Tracks all permission template actions: created, edited, deleted, applied
   - Logs actor name, template name, target user (for applies), role changes, changed fields (for edits)
   - `GET /api/permission-templates/audit-log` endpoint returns recent entries
   - Frontend: "Activity Log" button on Permission Templates page opens a modal with timestamped entries
6. **Manager Team Engagement Intelligence** (NEW)
   - `GET /api/engagement/team-hot-leads/{manager_id}` — aggregates hot leads across all team members in the manager's store/org
   - `POST /api/engagement/reassign-lead` — reassign org-owned leads to different reps (personal contacts blocked)
   - Frontend: `/admin/team-engagement` page with 3 tabs (Alerts 3+, Hot Leads, Team Activity)
   - Summary cards (hot leads count, alert count, total actions, engagement signals)
   - Team activity breakdown per rep (calls, texts, emails, cards)
   - Lead reassignment modal with team member search (org-owned leads only)
   - 30-second auto-refresh, period filters (Today, 48h, 7 Days)
7. **CRITICAL: Full Touchpoint Tracking Audit & Fix** (Mar 8, 2026)
   - **BUG 1 FIXED:** Twilio SMS sends created NO contact_events — `sms_sent` was never logged. Now logs `sms_sent`/`sms_failed` in BOTH message endpoints.
   - **BUG 2 FIXED:** `cards_sent` counter matched `"congrats"` broadly, catching customer views (e.g., `congrats_card_viewed`). Now only matches `*_card_sent` and `*card_shared`.
   - **BUG 3 FIXED:** Event type mismatch: `resolve_event_type()` returns `personal_sms` but summary only counted `sms_personal`. Now counts BOTH.
   - **BUG 4 FIXED:** Failed email/SMS attempts (`email_failed`, `sms_failed`) were not counted as activity touchpoints. Now included.
   - **Consistency:** Fixed leaderboard and team engagement endpoints to match the same counting logic.
8. **Notifications + Task Context Fixes** (Mar 8, 2026)
   - **Mobile responsiveness:** NotificationBell dropdown now scales to viewport width (maxWidth: 380, min 32px margin)
   - **Task timeline events:** Creating a task for a contact now logs a `task_created` contact_event visible in the contact's activity feed
   - **Task context banner:** Clicking a task notification navigates to the contact page with an orange "Pending Task" banner showing the task title + description
   - **Event icons:** Added proper icon/color mappings for task_created, task_completed, sms_sent, sms_failed, email_failed, lead_reassigned

### Previous Features
- Engagement Intelligence, Hot Leads Dashboard
- Gamification & Leaderboards, Image Performance Overhaul
- Operations Manual, Carrier-Agnostic Messaging, Reporting System
- White-Label Emails, Public REST API & Webhooks

---

## Key API Endpoints
- `POST /api/tags/{user_id}/assign` — Triggers AI outreach + campaign auto-enrollment on "Sold"
- `GET /api/contacts/{user_id}/{contact_id}/personal-details` — Voice memo extracted details
- `PATCH /api/contacts/{user_id}/{contact_id}/personal-details` — Manual edit details
- `POST /api/contacts/{user_id}/{contact_id}/re-extract` — Re-extract from all voice notes
- `GET /api/campaign-config/effective/{user_id}` — Resolved campaign config
- `PUT /api/campaign-config/{level}/{entity_id}` — Set config (org/store/user)
- `GET /api/ai-outreach/relationship-brief/{user_id}/{contact_id}` — Full intel with personal details

## Key DB Collections
- `contacts.personal_details` — Structured personal data from voice memos
- `campaign_configs` — Hierarchical campaign configuration (level + entity_id)
- `ai_outreach` — AI-generated suggestions
- `engagement_signals` — Real-time customer interaction tracking
- `voice_notes` — Now has `intelligence_extracted` and `extracted_fields` flags

---

## Prioritized Backlog

### P1
- Auth refactor (bcrypt)
- Push Notifications
- Voice Help Assistant
- Google Places API Integration

### P2
- Full Twilio Integration (enables auto_send)
- WhatsApp, Training Hub, Inventory Module

## Known Issues
- P1: Production email blocked (user: verify RESEND_API_KEY)
- P2: React Hydration Error #418, Mobile tags sync

## Test Credentials
- Super Admin: `forest@imosapp.com` / `Admin123!`
