# i'M On Social — Product Requirements Document

## Original Problem Statement
Full-stack Relationship Management System (RMS/CRM) for sales teams. Key goals: ease of use ("easy button"), activity tracking, gamification, AI-powered outreach, and multi-channel communication. The user envisions a "turnkey" system that minimizes their personal involvement in onboarding and training.

## Core Architecture
- **Frontend:** React Native (Expo) web app
- **Backend:** FastAPI (Python)
- **Database:** MongoDB
- **3rd Party:** Resend (email), Twilio (SMS - MOCKED), OpenAI (AI assistant), Emergent Integrations (object storage)

## What's Been Implemented

### LMS / Training Hub — Role-Based (Mar 2026)
- **4 training tracks** with 21 total lessons:
  - **Sales Team Onboarding** (6 lessons) — for `user`, `manager`, `admin`, `store_manager`
  - **Partner & Reseller Onboarding** (6 lessons) — for `partner`, `reseller`, `admin`, `super_admin`
  - **White Label Partner Guide** (5 lessons) — for `partner`, `reseller`, `admin`, `super_admin`
  - **Manager's Playbook** (4 lessons) — for `manager`, `admin`, `store_manager`, `super_admin`
- **Role-based filtering**: Users only see tracks matching their role; `super_admin` and `admin` see all
- **Admin Manage Training page** (`/admin/manage-training`): Full CRUD for tracks (create, edit, delete) and lessons (create, edit, delete) with role assignment
- **Partner Dashboard Training Hub link**: Partners can access training directly from their portal
- **Progress tracking**: Users can mark lessons complete, with persistent progress bars
- Pre-populated with comprehensive content on messaging, onboarding, selling, branding, and support

### Admin Onboarding Wizard (Mar 2026)
- 7-step guided wizard at `/admin/setup-wizard` for turnkey client onboarding
- Bulk team creation with auto-generated temp passwords and CSV download

### Partner Portal & Scoped Wizard (Mar 2026)
- **Partner Dashboard** (`/partner/dashboard`): Shows assigned orgs, locations, users
- **Partner Onboard Wizard** (`/partner/onboard`): 5-step scoped wizard

### First-Login Profile Completion (Mar 2026)
- `/auth/complete-profile` — 4-step guided onboarding for new users

### Partner Agreements (Mar 2026)
- Custom Commission Structure, White Label Checkbox

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
1. (P0) Make Training Hub Content Editable — DONE (admin CRUD at /admin/manage-training)
2. (P0) Gamification & Leaderboards
3. (P1) Automated Welcome Emails after wizard user creation
4. (P1) Link Orgs from Partner Agreement View
5. (P1) Quoting System
6. (P1) AI-Powered Outreach

## Future/Backlog
- Auth refactor (bcrypt)
- Push notifications
- Voice Help Assistant
- Full Twilio integration (currently MOCKED)
- WhatsApp Integration
- Inventory Management Module
- Code cleanup (~80 files)

## Key Credentials
- Super Admin: forest@imosapp.com / Admin123!

## Mocked Services
- Twilio SMS: All SMS functionality is MOCKED
