# i'M On Social — Product Requirements Document

## Original Problem Statement
Build a Relationship Management System (RMS) / CRM for automotive sales professionals. The platform has pivoted to a task-driven "Relationship Operating System" where the salesperson's daily workflow is guided by a central task queue and gamified competition.

## Core Architecture
- **Frontend:** React Native / Expo (web)
- **Backend:** FastAPI (Python)
- **Database:** MongoDB Atlas
- **Integrations:** Resend (email), Twilio (MOCKED), OpenAI, Emergent Object Storage, Pillow

## What's Been Implemented

### Task Engine (Sprint 1-3) — COMPLETE
- Backend: Full CRUD API, auto-generation from campaigns/system triggers, idempotent scheduling
- Frontend: Today's Touchpoints page, My Performance page, Add Task form
- Home screen: "Your Day" section with Touchpoints tile + Activity Feed tile
- Unified Text flow: phone lookup → contact page → pre-filled composer → logs activity → auto-completes task

### Menu Reorganization & Permissions — COMPLETE
- Menu cleaned from 8 → 6 sections: My Tools, Campaigns, Content, Insights, Administration, Settings
- Feature Permissions: section-level master toggles + individual item overrides
- Progressive defaults (core ON, advanced OFF for new users)
- Permission hierarchy: Super Admin > Org Admin > Store Manager
- Permissions UI at `/admin/users/permissions/{id}`
- My Account page cleaned up (removed Quick Actions grid + My Activity dashboard)

### Gamification & Leaderboards — COMPLETE
- **3-tier leaderboards**: My Team (users in store), My Org (stores in org), Global (anonymized, privacy-gated)
- **Level system**: Rookie (0-50) → Hustler (51-200) → Closer (201-500) → All-Star (501-1000) → Legend (1001+)
- **Streaks**: Consecutive days of task completion, displayed on rank card
- **"You vs Average"**: Shows how you stack up against team average
- **7 scoring categories**: Digital Cards, Reviews, Cards Sent, Emails, SMS, Calls, Tasks Done
- **Podium display**: Gold/Silver/Bronze for top 3 with avatars
- **Period filters**: This Week / This Month / All Time
- **Category sorting**: Re-sort leaderboard by any scoring category
- **Privacy controls**: Org `leaderboard_visible` flag gates global visibility

### Earlier Completed Features
- Public REST API & outgoing webhooks
- Soft-delete user system & data retention policy
- Automated lifecycle scans (apscheduler)
- Carrier-agnostic messaging (personal SMS fallback)
- White-label branded HTML emails via Resend
- Quick Send flow overhaul, Dialer redesign

## Prioritized Backlog

### P0
- ~~Task Engine~~ DONE
- ~~Menu Reorganization~~ DONE
- ~~Feature Permissions~~ DONE
- ~~Gamification & Leaderboards~~ DONE

### P1
- AI-Powered Outreach (contextual follow-up suggestions)
- Refactor Authentication (bcrypt password hashing)
- Push Notifications
- Progressive Feature Exposure (phased UI unlocking)

### P2
- Full Twilio Integration (live)
- WhatsApp Integration
- Training Hub content
- Inventory Management Module
- Code cleanup (~80 files)

## Known Issues
- P1: Production email delivery blocked (user needs to verify RESEND_API_KEY)
- P2: React Hydration Error #418
- P2: Mobile tags sync issue

## Key API Endpoints
- Tasks: `GET/POST /api/tasks/{user_id}`, `PATCH /api/tasks/{user_id}/{task_id}`, `GET .../summary`, `GET .../performance`
- Permissions: `GET/PUT /api/admin/permissions/{user_id}`
- Leaderboard: `GET /api/leaderboard/v2/store/{user_id}`, `.../org/{user_id}`, `.../global/{user_id}` — params: period, category

## Key Files
- `/app/backend/routers/leaderboard_v2.py` — Gamification engine with levels, streaks, tiers
- `/app/backend/permissions.py` — Permission defaults and merge logic
- `/app/frontend/app/admin/leaderboard.tsx` — Leaderboard UI with podium, tiers, rank card
- `/app/frontend/app/touchpoints/` — Touchpoints, Performance, Add Task pages
- `/app/frontend/app/(tabs)/more.tsx` — Reorganized menu with permission filtering

## Test Credentials
- Super Admin: `forest@imosapp.com` / `Admin123!`
