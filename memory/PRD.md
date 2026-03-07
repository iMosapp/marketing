# i'M On Social — Product Requirements Document

## Original Problem Statement
Build a Relationship Management System (RMS) / CRM for automotive sales professionals. The platform has pivoted to a task-driven "Relationship Operating System" where the salesperson's daily workflow is guided by a central task queue and gamified competition.

## Core Architecture
- **Frontend:** React Native / Expo (web)
- **Backend:** FastAPI (Python)
- **Database:** MongoDB Atlas
- **Integrations:** Resend (email), Twilio (MOCKED), OpenAI, Emergent Object Storage, Pillow, Nominatim

## What's Been Implemented

### Operations Manual v3.0 & PDF Export — COMPLETE (Feb 2026)
- Updated "i'M On Social Platform Complete Operations Manual" to v3.0 with 26 comprehensive slides
- Covers ALL features: Touchpoints, Permissions, Gamification, Leaderboards, Power Rankings, Client Onboarding, API, Webhooks, etc.
- PDF Export: `GET /api/docs/{id}/export-pdf` generates branded A4 PDF with proper formatting
- Email PDF: `POST /api/docs/{id}/email-pdf` sends PDF as email attachment via Resend
- Both PDF features are super admin only (HTTP 403 for other roles)
- Frontend doc viewer has a three-dot action menu for super admins with Download/Email options

### Streamlined Client Onboarding — COMPLETE (Feb 2026)
- Backend: `POST /api/setup-wizard/new-account` creates org + store + primary user
- Frontend: 3-step flow (Search → Details → Success) at `/onboarding/new-account`
- Business search via Nominatim, success screen with temp credentials + copy button
- Old admin onboarding links cleaned up — flow lives exclusively under My Account

### Task Engine (Touchpoints) — COMPLETE
- Backend: Full CRUD API, auto-generation, idempotent scheduling
- Frontend: Today's Touchpoints page, My Performance page, Add Task form
- Unified Text flow with auto-complete tasks

### Menu Reorganization & Permissions — COMPLETE
- 5 permission-gated sections: My Tools, Campaigns, Content, Insights, Administration
- Backend permissions system with admin UI at `/admin/users/permissions/{id}`

### Gamification & Leaderboards — COMPLETE
- 3-tier leaderboards: My Team, My Org, Global
- Level system, streaks, "You vs Average", category sorting, podium

### Weekly Power Rankings Email — COMPLETE
- Branded HTML email every Monday at 9 AM UTC via APScheduler

### Earlier Completed Features
- Public REST API & webhooks, soft-delete system, lifecycle scans
- Carrier-agnostic messaging, white-label emails, comprehensive reporting

## Prioritized Backlog

### P0
- (None — current sprint complete)

### P1
- Google Places API integration (when user provides key)
- Permission Roles/Templates (pre-defined role sets)
- AI-Powered Outreach (contextual follow-up suggestions)
- Refactor Authentication (bcrypt password hashing)
- Push Notifications
- Voice Help Assistant Backend

### P2
- Full Twilio Integration (live), WhatsApp Integration
- Training Hub content, Inventory Management Module
- Code cleanup (~80 files)

## Known Issues
- P1: Production email delivery blocked (user needs to verify RESEND_API_KEY)
- P2: React Hydration Error #418, Mobile tags sync

## Test Credentials
- Super Admin: `forest@imosapp.com` / `Admin123!`
- Operations Manual Doc ID: `69a2296073da8ea96c918d75`
