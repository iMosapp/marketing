# i'M On Social — Product Requirements Document

## Original Problem Statement
Full-stack Relationship Management System (RMS/CRM) for sales teams. Key goals: ease of use ("easy button"), activity tracking, gamification, AI-powered outreach, and multi-channel communication. The user envisions a "turnkey" system that minimizes their personal involvement in onboarding and training.

## Core Architecture
- **Frontend:** React Native (Expo) web app
- **Backend:** FastAPI (Python)
- **Database:** MongoDB
- **3rd Party:** Resend (email), Twilio (SMS - MOCKED), OpenAI (AI assistant), Emergent Integrations (object storage)

## What's Been Implemented

### Home Screen Quick Actions Fix (Mar 2026)
- **CRITICAL FIX:** All Home quick actions (Share My Card, Review Link, Send a Card, My Showcase) now navigate to a **contact picker** → then to the **contact record** to complete the action
- Previous behavior incorrectly opened generic share modals with no contact context
- Contact detail page now supports `?action=xxx` query param to auto-trigger the relevant action (digitalcard, review, congrats, showcase)
- `handleQuickAction` in contact page now handles ALL action keys: sms, call, email, review, card, gift, congrats, digitalcard, linkpage, showcase
- Action progress tracker items on the contact page are now all clickable and functional

### LMS / Training Hub — Role-Based (Mar 2026)
- **4 training tracks** with 21 total lessons:
  - **Sales Team Onboarding** (6 lessons) — for `user`, `manager`, `admin`, `store_manager`
  - **Partner & Reseller Onboarding** (6 lessons) — for `partner`, `reseller`, `admin`, `super_admin`
  - **White Label Partner Guide** (5 lessons, NEW) — for `partner`, `reseller`, `admin`, `super_admin`
  - **Manager's Playbook** (4 lessons) — for `manager`, `admin`, `store_manager`, `super_admin`
- **Role-based filtering**: Users only see tracks matching their role; `super_admin` and `admin` see all
- **Admin Manage Training page** (`/admin/manage-training`): Full CRUD for tracks and lessons
- **Partner Dashboard** Training Hub link for easy partner access
- **Progress tracking**: Users can mark lessons complete with persistent progress bars

### Admin Onboarding Wizard (Mar 2026)
- 7-step guided wizard at `/admin/setup-wizard` for turnkey client onboarding
- Bulk team creation with auto-generated temp passwords and CSV download

### Partner Portal & Scoped Wizard (Mar 2026)
- **Partner Dashboard** (`/partner/dashboard`): Shows assigned orgs, locations, users
- **Partner Onboard Wizard** (`/partner/onboard`): 5-step scoped wizard

### First-Login Profile Completion (Mar 2026)
- `/auth/complete-profile` — 4-step guided onboarding for new users

### Communication
- Carrier-agnostic messaging (Twilio or personal phone SMS fallback)
- Email via Resend with white-label branded HTML templates
- All logged as `contact_events`

### Reporting & Activity
- Activity summary dashboard with 14+ metrics
- Schedulable email delivery

## Pending Issues
- P0: Production email delivery — BLOCKED on user verifying `RESEND_API_KEY`
- P2: React Hydration Error #418
- P2: Mobile app `tags` data sync

## Upcoming Tasks
1. (P0) Gamification & Leaderboards
2. (P1) Automated Welcome Emails after wizard user creation
3. (P1) Link Orgs from Partner Agreement View
4. (P1) Quoting System
5. (P1) AI-Powered Outreach

## Future/Backlog
- Auth refactor (bcrypt), Push notifications, Voice Help Assistant
- Full Twilio integration (currently MOCKED), WhatsApp Integration
- Inventory Management Module, Code cleanup (~80 files)

## Key Credentials
- Super Admin: forest@imosapp.com / Admin123!

## Mocked Services
- Twilio SMS: All SMS functionality is MOCKED
