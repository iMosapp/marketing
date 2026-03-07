# i'M On Social — Product Requirements Document

## Original Problem Statement
Build a Relationship Management System (RMS) / CRM for automotive sales professionals. The platform has pivoted to a task-driven "Relationship Operating System" where the salesperson's daily workflow is guided by a central task queue called "Today's Touchpoints."

## Core Architecture
- **Frontend:** React Native / Expo (web)
- **Backend:** FastAPI (Python)
- **Database:** MongoDB Atlas
- **Integrations:** Resend (email), Twilio (MOCKED), OpenAI, Emergent Object Storage, Pillow

## What's Been Implemented

### Sprint 1: Task Engine Backend (COMPLETE — Tested)
- Enhanced `Task` model with full fields (contact, priority, source, campaign, suggested_message, idempotency_key)
- Full CRUD API at `/api/tasks/{user_id}` with filtering (today, overdue), sorting, summary, performance
- Scheduler auto-generates tasks from campaigns and system triggers (birthdays, anniversaries, dormant contacts)
- Idempotent task generation via unique partial index

### Sprint 2: "Today's Touchpoints" Frontend UI (COMPLETE — Tested)
- **Home Screen:** New "Your Day" section with Touchpoints tile (mini scoreboard, progress bar, top 3 task previews) + Activity Feed tile
- **Touchpoints Page (`/touchpoints`):** Scrollable scoreboard, progress, My Performance card, filter pills, task cards with action buttons
- **My Performance Page (`/touchpoints/performance`):** Period toggle, stats grids, click-through breakdown
- **Add Task Page (`/touchpoints/add-task`):** Contact picker, date/time, priority/action toggles

### Sprint 2.5: Unified Text/Call Flow (COMPLETE)
- Text button on task cards always routes through contact page for logging
- Phone lookup by number when task has no linked contact_id
- Auto-complete tasks after sending a message or making a call
- Fallback: log activity via API then open native SMS for contacts not in CRM

### Menu Reorganization & Permissions System (COMPLETE — Tested)
- **Menu cleaned from 8 sections → 6:** My Tools, Campaigns, Content, Insights, Administration (role-gated), Settings
- Removed duplicates (Lead Attribution, Brand Kit), moved admin items to proper section
- **Feature Permissions System:**
  - Backend: `DEFAULT_PERMISSIONS` with progressive defaults (core ON, advanced OFF for new users)
  - API: `GET/PUT /api/admin/permissions/{user_id}` for managing permissions
  - Login response includes `feature_permissions` merged with defaults
  - Section-level master toggles + individual item overrides (fully customizable)
  - Permission hierarchy: Super Admin > Org Admin > Store Manager
- **Permissions Management UI** at `/admin/users/permissions/{id}` with section toggles + per-item switches
- **"Manage Permissions" button** on user detail page
- **My Account page cleaned up:** Removed Quick Actions grid and My Activity dashboard, added My Performance shortcut, simplified Settings (Brand Kit/Integrations moved to Admin)

### Earlier Completed Features
- Public REST API & outgoing webhooks
- Soft-delete user system & data retention policy
- Automated lifecycle scans (apscheduler)
- Carrier-agnostic messaging (personal SMS fallback)
- Centralized & trackable quick actions
- Comprehensive reporting with scheduled email delivery
- White-label branded HTML emails via Resend
- Quick Send flow overhaul
- Dialer redesign (iPhone-style)

## Prioritized Backlog

### P0
- ~~Sprint 2: Today's Touchpoints Frontend~~ DONE
- ~~Sprint 3: Add Task Page~~ DONE
- ~~Menu Reorganization~~ DONE
- ~~Feature Permissions System~~ DONE
- Gamification & Leaderboards

### P1
- AI-Powered Outreach (contextual follow-up suggestions)
- Refactor Authentication (bcrypt password hashing)
- Push Notifications
- Progressive Feature Exposure (phased UI unlocking for new users)

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
- P2: Admin reports endpoint 404

## Key API Endpoints
- `GET /api/tasks/{user_id}` — Fetch tasks with filters
- `GET /api/tasks/{user_id}/summary` — Daily scoreboard and progress
- `GET /api/tasks/{user_id}/performance` — Performance stats by period
- `POST /api/tasks/{user_id}` — Create manual task
- `PATCH /api/tasks/{user_id}/{task_id}` — Update task (complete/snooze)
- `GET /api/admin/permissions/{user_id}` — Get user's feature permissions
- `PUT /api/admin/permissions/{user_id}` — Update user's feature permissions

## Key Files
- `/app/backend/permissions.py` — Permission defaults, merge logic, feature check
- `/app/backend/routers/tasks.py` — Task CRUD + summary + performance endpoints
- `/app/backend/routers/admin.py` — Permissions management endpoints (bottom of file)
- `/app/frontend/app/(tabs)/more.tsx` — Reorganized menu with permission filtering
- `/app/frontend/app/touchpoints/index.tsx` — Touchpoints page
- `/app/frontend/app/touchpoints/performance.tsx` — My Performance page
- `/app/frontend/app/touchpoints/add-task.tsx` — Add Task form
- `/app/frontend/app/admin/users/permissions/[id].tsx` — Permissions management UI

## Test Credentials
- Super Admin: `forest@imosapp.com` / `Admin123!`
