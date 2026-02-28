# iMOs - Product Requirements Document

## Original Problem Statement
Full-stack Relationship Management System (RMS) for dealerships. The app empowers sales teams with digital cards, automated campaigns, AI assistants, review management, and customer relationship tools.

## Core Architecture
- **Frontend:** React Native (Expo) with web support
- **Backend:** FastAPI (Python)
- **Database:** MongoDB Atlas (production), localhost:27017 (preview)
- **Email:** Resend
- **SMS:** Twilio (MOCK mode)
- **AI:** OpenAI GPT-5.2 (Jessi assistant, Relationship Intel, AI Campaign Engine), Whisper (Voice Notes)
- **Object Storage:** Emergent Integrations (image uploads, voice notes)

## What's Been Implemented

### Session Feb 28, 2026 (Fork 9 - Current)

#### Phase 1: Notifications Center + Analytics Dashboard
- **Notifications Center** — Unified hub aggregating 7 data sources: lead alerts, overdue tasks, upcoming tasks, unread messages, flagged convos, recent activity events, and pending campaign sends. Backend at `/api/notification-center/{user_id}` with category filtering (`all`, `leads`, `tasks`, `messages`, `campaigns`, `flags`, `activity`), mark-as-read, unread count. Frontend: full `/notifications` page with category tabs + enhanced NotificationBell dropdown.
- **Analytics Dashboard** — Multi-level (Org/Store/Personal) dashboard at `/analytics` with: KPI hero card + 10-metric grid, stacked daily trend chart, channel breakdown bars, per-user performance table, store comparison table, period selector (7D-1Y). Backend at `/api/reports/dashboard/{user_id}?days=N`.

#### Phase 2: AI-Powered Campaign Outreach System
- **AI Clone Prompt System** — Global default prompt template (genericized from user's provided prompt) with per-user overrides. Dynamically hydrates {user_name}, {user_bio}, {store_name}, {store_info} from user profile data. Endpoints: GET/PUT global, GET/PUT/DELETE per-user at `/api/ai-campaigns/clone-prompt/*`.
- **AI Message Generation** — GPT-5.2 generates personalized campaign messages using contact's activity history, conversation context, and salesperson's clone personality. Supports both SMS and email channels. Endpoint: POST `/api/ai-campaigns/generate-message/{user_id}/{contact_id}`.
- **AI Virtual Assistant Reply Handler** — Handles inbound customer replies during automated campaigns. Returns generated reply with 1-3 minute randomized delay for human-like timing. Endpoint: POST `/api/ai-campaigns/handle-reply/{user_id}/{contact_id}`.
- **AI Clone Preview** — Test the AI personality. Endpoint: POST `/api/ai-campaigns/preview-clone/{user_id}`.
- **Enhanced Campaign Model** — Added `delivery_mode` (automated/manual), `ai_enabled`, `ownership_level` (user/store/org). Each step now has `channel` (sms/email), `ai_generated`, `step_context`.
- **Dual Delivery Modes**:
  - **Automated:** Messages auto-send between 10AM-12PM (randomized), AI handles replies with 1-3 min delay.
  - **Manual:** Creates notification + pending send record. User opens notification, reviews pre-populated message, clicks send to open native SMS/email app.
- **Pending Sends System** — CRUD for manual campaign pending sends. Endpoints at `/api/campaigns/{user_id}/pending-sends`. Frontend page at `/campaigns/pending-send/[id]` with editable message, send via native app, mark complete/skip.
- **Enhanced Campaign Builder** — New sections: Delivery Mode cards (Automated/Manual), AI-Powered Messages toggle, Campaign Level selector (Personal/Store/Org for admins), channel selector per step (SMS/Email), AI context per step.
- **Enhanced Scheduler** — Dual mode campaign processing: automated sends logged + queued, manual sends create notifications. Randomized send times 10AM-12PM.

### Previous Sessions
- Contact activity feed, swipe gestures, voice notes, AI relationship intel, leaderboards, photo fixes
- Public REST API, webhooks, soft-delete system, lifecycle engine
- Personal SMS mode, contact event tracking, activity reports, white-label emails
- Operations manual, NDA system, digital signing

## Known Issues
- (P2) React Hydration Error #418
- (P2) Mobile app tags sync

## Upcoming Tasks
- (P1) Mobile Push Notifications
- (P1) Auth refactor (bcrypt)
- (P1) Clean production database for customer launch

## Future/Backlog
- (P2) Customer-facing gamification
- (P2) Full Twilio live mode
- (P2) WhatsApp integration
- (P2) TestFlight iOS build
- (P2) Training Hub content
- (P2) Inventory Management Module
- (P2) Refactor contact/[id].tsx (2000+ lines)

## Credentials
- **Super Admin:** forest@imosapp.com / Admin123!

## 3rd Party Integrations
- **OpenAI GPT-5.2** — Jessi assistant, Relationship Intel, AI Campaign Engine (via emergentintegrations)
- **OpenAI Whisper** — Voice note transcription (via emergentintegrations)
- **Resend** — Transactional emails
- **MongoDB Atlas** — Primary database
- **Twilio** — SMS (MOCK mode)
- **Emergent Object Storage** — File storage
