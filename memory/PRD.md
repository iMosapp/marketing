# i'M On Social — Product Requirements Document

## Original Problem Statement
Build a Relationship Management System (RMS) / CRM for automotive sales professionals.

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

### AI-Powered Outreach + Sold Campaign Intelligence (Mar 2026) — LATEST
**The system that makes every follow-up deliberate, meaningful, and personal.**

1. **Relationship Intelligence Engine** (`services/relationship_intel.py`)
   - Compiles ALL data: contact profile, engagement signals, conversation history, campaign messages, voice notes
   - Calculates: relationship health (strong/warm/cooling/cold), engagement score, response pattern, milestones
   - Outputs both AI context (for prompt engineering) and human summary (for salesperson visibility)

2. **AI-Powered Campaign Messages** (upgraded `ai_campaigns.py`)
   - `get_contact_context()` now uses the full Relationship Intelligence Engine
   - Campaign message prompts include: engagement signals, previous messages (no repeats), relationship health, response patterns
   - Prompt instructions adapt tone based on relationship health: strong = casual, cooling = warmer

3. **Sold Tag Auto-Enrollment** (in `tags.py`)
   - When "Sold" tag is applied: AI generates 2 personalized follow-up suggestions + auto-enrolls contact in Sold Follow-Up campaign
   - Campaign auto-created from template if it doesn't exist (`ai_enabled: true`)
   - Enrollment has `trigger_type: sold_tag, auto_enrolled: true`

4. **Relationship Intelligence in Tasks** (upgraded `scheduler.py`)
   - Campaign pending sends include `relationship_brief` field
   - Tasks include `ai_generated` and `relationship_brief` for salesperson visibility

5. **Timezone-Aware Scheduling**
   - Browser timezone auto-detected on login (stored on user doc)
   - AI outreach tasks scheduled for 9 AM next morning in user's timezone
   - Campaign steps randomized between 10-12 PM user's local time

6. **Frontend: AI Outreach Dashboard** (`/ai-outreach`)
   - 4 tabs: Campaign (pending sends), AI Suggestions, Accepted, Dismissed
   - `RelBriefCard` component shows: health badge, engagement score, last contact, response pattern, milestones
   - Campaign tab: message preview, Copy, Mark as Sent, step context
   - Tap to load full relationship intelligence per contact

### Engagement Intelligence System (Mar 2026)
- Real-time tracking, "Hot Leads" dashboard, notification integration

### Previous Features
- Gamification & Leaderboards, Image Performance Overhaul, Unified Card System
- Operations Manual, Carrier-Agnostic Messaging, Reporting System
- White-Label Emails, Public REST API & Webhooks
- Centralized & Trackable Actions, Personal SMS Fallback

---

## Key API Endpoints
- `POST /api/tags/{user_id}/assign` — Triggers AI outreach + auto campaign enrollment on "Sold"
- `GET /api/ai-outreach/suggestions/{user_id}` — AI suggestion records
- `POST /api/ai-outreach/suggestions/{id}/accept` — Accept → creates task
- `GET /api/ai-outreach/relationship-brief/{user_id}/{contact_id}` — Full relationship intel
- `GET /api/campaigns/{user_id}/pending-sends` — Campaign messages with relationship briefs
- `POST /api/ai-campaigns/generate-message/{user_id}/{contact_id}` — AI message generation

## Key DB Collections
- `ai_outreach` — AI-generated suggestions with status tracking
- `campaign_enrollments` — Campaign enrollment with trigger_type and auto_enrolled fields
- `campaign_pending_sends` — Now includes relationship_brief, ai_generated, step_context
- `engagement_signals` — Real-time customer interaction tracking

---

## Prioritized Backlog

### P1
- Permission Roles/Templates
- Auth refactor (bcrypt)
- Push Notifications
- Voice Help Assistant
- Manager Feature (team-wide engagement dashboard)
- Google Places API Integration

### P2
- Full Twilio, WhatsApp, Training Hub, Inventory Module
- Delete legacy `birthday_cards.py`

## Known Issues
- P1: Production email blocked (user: verify RESEND_API_KEY)
- P2: React Hydration Error #418, Mobile tags sync

## Test Credentials
- Super Admin: `forest@imosapp.com` / `Admin123!`
