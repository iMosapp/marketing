# i'M On Social — Product Requirements Document

## Original Problem Statement
Build a Relationship Management System (RMS) / CRM for automotive sales professionals. The platform has pivoted to a task-driven "Relationship Operating System" where the salesperson's daily workflow is guided by a central task queue and gamified competition.

## Core Architecture
- **Frontend:** React Native / Expo (web)
- **Backend:** FastAPI (Python)
- **Database:** MongoDB Atlas
- **Integrations:** Resend (email), Twilio (MOCKED), OpenAI, Emergent Object Storage, Pillow

## What's Been Implemented

### Streamlined Client Onboarding — COMPLETE (Feb 2026)
- Backend: `POST /api/setup-wizard/new-account` creates org + store + primary user in one call
- Temp password generated, user role set to `store_manager` with `needs_password_change=True`
- Store-level and user-level defaults (templates, campaigns, tags) auto-seeded
- Frontend: 3-step flow (Search → Details → Success) at `/onboarding/new-account`
- Business search via Nominatim (OpenStreetMap), swappable to Google Places later
- Success screen displays login credentials with copy-to-clipboard
- Entry points: My Account page, More menu (Administration), Admin Dashboard hero button
- Old admin links updated to point to the new consolidated flow

### Task Engine (Sprint 1-3) — COMPLETE
- Backend: Full CRUD API, auto-generation from campaigns/system triggers, idempotent scheduling
- Frontend: Today's Touchpoints page, My Performance page, Add Task form
- Home screen: "Your Day" section with Touchpoints tile + Activity Feed tile
- Unified Text flow: phone lookup → contact page → pre-filled composer → logs activity → auto-completes task

### Menu Reorganization & Permissions — COMPLETE
- Menu cleaned from 8 → 6 sections: My Tools, Campaigns, Content, Insights, Administration, Settings
- Feature Permissions: section-level master toggles + individual item overrides
- Progressive defaults (core ON, advanced OFF for new users)
- Permissions UI at `/admin/users/permissions/{id}`

### Gamification & Leaderboards — COMPLETE
- 3-tier leaderboards: My Team, My Org, Global (anonymized, privacy-gated)
- Level system: Rookie → Hustler → Closer → All-Star → Legend
- Streaks, "You vs Average", category sorting, podium, period filters
- 7 scoring categories: Digital Cards, Reviews, Cards Sent, Emails, SMS, Calls, Tasks Done

### Weekly Power Rankings Email — COMPLETE
- Branded HTML email sent to all team members every Monday at 9 AM UTC
- Shows: your rank, rank movement, level, streak, points
- Includes: podium, full rankings list, "Almost There" section
- Manual trigger + scheduled via APScheduler CronTrigger

### Earlier Completed Features
- Public REST API & outgoing webhooks
- Soft-delete user system & data retention policy
- Automated lifecycle scans, carrier-agnostic messaging
- White-label branded HTML emails via Resend
- Quick Send flow, Dialer redesign
- Comprehensive reporting system with scheduled email delivery

## Prioritized Backlog

### P0
- (None — current sprint complete)

### P1
- Google Places API integration (when user provides a key)
- Permission Roles/Templates (pre-defined role sets)
- AI-Powered Outreach (contextual follow-up suggestions)
- Refactor Authentication (bcrypt password hashing)
- Push Notifications
- Voice Help Assistant Backend

### P2
- Full Twilio Integration (live), WhatsApp Integration
- Training Hub content, Inventory Management Module
- Code cleanup (~80 files)
- Obsolete onboarding files cleanup (`admin/client-onboarding.tsx`, `admin/onboarding-settings.tsx`)

## Known Issues
- P1: Production email delivery blocked (user needs to verify RESEND_API_KEY in production env)
- P2: React Hydration Error #418, Mobile tags sync

## Key API Endpoints
- New Account: `POST /api/setup-wizard/new-account`
- Tasks: `GET/POST /api/tasks/{user_id}`, `PATCH /api/tasks/{user_id}/{task_id}`
- Permissions: `GET/PUT /api/admin/permissions/{user_id}`
- Leaderboard: `GET /api/leaderboard/v2/store|org|global/{user_id}`
- Power Rankings: `POST /api/admin/send-power-rankings`

## Test Credentials
- Super Admin: `forest@imosapp.com` / `Admin123!`
