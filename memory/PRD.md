# iMOs - Product Requirements Document

## Original Problem Statement
Full-stack Relationship Management System (RMS) for dealerships. The app empowers sales teams with digital cards, automated campaigns, AI assistants, review management, and customer relationship tools.

## Core Architecture
- **Frontend:** React Native (Expo) with web support
- **Backend:** FastAPI (Python)
- **Database:** MongoDB Atlas (production), localhost:27017 (preview)
- **Email:** Resend
- **SMS:** Twilio (MOCK mode)
- **AI:** OpenAI GPT-5.2 (Jessi assistant, Relationship Intel), Whisper (Voice Notes)
- **Object Storage:** Emergent Integrations (image uploads, voice notes)

## What's Been Implemented

### Session Feb 28, 2026 (Fork 9 - Current)
- **FEATURE: Notifications Center** — Unified, prioritized notification hub aggregating data from 6 sources: lead alerts (from `notifications` collection), overdue tasks, upcoming tasks (due within 24h), unread conversations, flagged conversations, and recent activity events (48h). Backend at `/api/notification-center/{user_id}` with category filtering (`all`, `leads`, `tasks`, `messages`, `flags`, `activity`), mark-as-read (individual and bulk), and unread count endpoint. Frontend: full-page `/notifications` with category tabs, empty state ("All caught up!"), and pull-to-refresh. NotificationBell dropdown enhanced with category filter chips, richer notification types with per-type icons/colors, and "View All" link to full page.
- **FEATURE: Comprehensive Analytics Dashboard** — Multi-level (Organization/Store/Personal) reporting dashboard at `/analytics` with: (1) Hero KPI card showing total touchpoints + trend percentage vs. previous period. (2) 10-metric KPI grid (SMS, Emails, Digital Cards, Review Invites, Congrats Cards, Calls, Voice Notes, Link Clicks, New Contacts, Total Contacts). (3) Stacked bar chart for daily activity trends (SMS/Email/Shares) with horizontal scroll. (4) Channel breakdown with horizontal progress bars. (5) Per-user performance table with medal badges for top 3 (managers only). (6) Store comparison table with per-user averages (admins only). (7) Period selector (7D/14D/30D/90D/1Y). (8) Quick links to detailed report sub-pages. Backend endpoint at `/api/reports/dashboard/{user_id}?days=N`.

### Session Feb 28, 2026 (Fork 8)
- **FEATURE: Contact Activity Feed Revamp** — Fixed timestamps, expand/collapse, search bar, note events.
- **FEATURE: Inbox Swipe Gestures (Web)** — Swipe-to-action (Archive, Task, Flag, Tag).
- **BUG FIX: Contact Photo Reverting** — Thumbnail generation on update, EXIF rotation.
- **FEATURE: Full Photo Viewer** — Modal for high-res contact photos.
- **FEATURE: Voice Notes** — Record, store, transcribe (Whisper), play back on contacts.
- **BUG FIX: Inbox Email Sending** — `_clean_email()` sanitization for None/null values.
- **FEATURE: AI Relationship Intel** — GPT-5.2 on-demand contact summary.
- **FEATURE: 3-Level Gamification Leaderboard** — Store/Org/Global with category filters.
- **FEATURE: Activity Feed Search + Notes in Timeline.**

### Session Feb 28, 2026 (Fork 7)
- **CRITICAL FIX: 5-Point Email Flow Audit.**
- **FEATURE: Operations Manual, NDA system, Digital NDA Signing.**
- **FEATURE: Signed Documents Hub, Doc Access Control.**

### Earlier Sessions (Forks 4-6)
- Personal SMS mode, contact event tracking, activity reports, white-label emails.
- Public REST API, webhooks, soft-delete system, lifecycle engine.
- UI redesigns, leaderboard visibility fixes, My Activity dashboard.

## Known Issues

### P2 (Low)
- React Hydration Error #418
- Mobile app `tags` data sync
- `GET /api/users/{user_id}` returns 405 (minor)

## Upcoming Tasks (Priority Order)

### P1
- **Mobile Push Notifications** — Real-time alerts on iOS/Android.
- **Auth Refactor** — Migrate to hashed passwords (bcrypt).
- **Clean Production Database** — Set up for first live customer launch.
- **AI-Powered Outreach** — Suggest follow-up messages when `sold` tag applied.

### P2
- Customer-facing gamification
- Full Twilio integration (live mode)
- WhatsApp integration
- TestFlight iOS build
- Training Hub content
- Inventory Management Module
- Refactor `contact/[id].tsx` (2000+ lines) into smaller components

## Credentials
- **Super Admin:** forest@imosapp.com / Admin123!

## 3rd Party Integrations
- **Resend:** Transactional emails (LIVE)
- **MongoDB Atlas:** Primary database
- **Twilio:** SMS (MOCK mode)
- **OpenAI GPT-5.2:** AI assistant + Relationship Intel
- **OpenAI Whisper:** Voice note transcription
- **Emergent Integrations:** Object storage
