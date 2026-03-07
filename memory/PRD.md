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
- **Home Screen (`home.tsx`):** New "Your Day" section with Touchpoints tile (mini scoreboard, progress bar, top 3 task previews) and Activity Feed tile
- **Touchpoints Page (`/touchpoints`):** Horizontally scrolling scoreboard (actions + engagement), progress bar, My Performance card, filter pills (All/Overdue/Campaigns/Birthdays/Follow-ups), task cards with avatars/badges/suggested messages/action buttons (Call/Text/Done/Snooze), FAB for adding tasks
- **My Performance Page (`/touchpoints/performance`):** Period toggle (Today/Week/Month), summary banner with trend %, Communication/Sharing/Engagement stat grids, Click-Through Breakdown list
- **Add Task Page (`/touchpoints/add-task`):** Contact picker modal, task title/notes, date/time selector, priority toggles (High/Medium/Low), primary action type (Call/Text/Email/Card/Other), gold Save button

### Earlier Completed Features
- Public REST API & outgoing webhooks
- Soft-delete user system & data retention policy
- Automated lifecycle scans (apscheduler)
- Carrier-agnostic messaging (personal SMS fallback)
- Centralized & trackable quick actions
- Comprehensive reporting system with scheduled email delivery
- White-label branded HTML emails via Resend
- Quick Send flow overhaul
- Inbox & Contact page fixes
- Dialer redesign (iPhone-style)
- Global CSS fixes (dark mode autofill, focus outlines)

## Prioritized Backlog

### P0
- ~~Sprint 2: Today's Touchpoints Frontend~~ DONE
- ~~Sprint 3: Add Task Page~~ DONE
- Gamification & Leaderboards (user has expressed strong interest)

### P1
- Menu Reorganization
- AI-Powered Outreach (contextual follow-up suggestions)
- Refactor Authentication (bcrypt password hashing)
- Push Notifications

### P2
- Full Twilio Integration (live)
- WhatsApp Integration
- Training Hub content
- Inventory Management Module
- Code cleanup (~80 files)

## Known Issues
- P1: Production email delivery blocked (user needs to verify RESEND_API_KEY in production)
- P2: React Hydration Error #418
- P2: Mobile tags sync issue
- P2: Leaderboard toggle not fully tested
- P2: Admin reports endpoint 404

## Key API Endpoints
- `GET /api/tasks/{user_id}` — Fetch tasks with filters
- `GET /api/tasks/{user_id}/summary` — Daily scoreboard and progress
- `GET /api/tasks/{user_id}/performance` — Performance stats by period
- `POST /api/tasks/{user_id}` — Create manual task
- `PATCH /api/tasks/{user_id}/{task_id}` — Update task (complete/snooze)

## Test Credentials
- Super Admin: `forest@imosapp.com` / `Admin123!`
