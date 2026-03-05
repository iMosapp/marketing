# i'M On Social — Product Requirements Document

## Original Problem Statement
Full-stack Relationship Management System (RMS/CRM) for sales teams. Key goals: ease of use ("easy button"), activity tracking, gamification, AI-powered outreach, and multi-channel communication. The user envisions a "turnkey" system that minimizes their personal involvement in onboarding and training.

## Core Architecture
- **Frontend:** React Native (Expo) web app
- **Backend:** FastAPI (Python)
- **Database:** MongoDB
- **3rd Party:** Resend (email), Twilio (SMS - MOCKED), OpenAI (AI assistant), Emergent Integrations (object storage)

## What's Been Implemented

### Home Screen & Action Items Fix (Mar 2026)
- **Notification Bell z-index:** Migrated from `position: fixed` overlay to `Modal` component — dropdown now always renders on top of tiles
- **Action Items navigate to Contact Record:** Tasks with a `contact_id` navigate to the contact page with prefilled message in the composer. Tasks without `contact_id` go to `/tasks` page
- **Task Banner on Contact Page:** When arriving from a task, a blue "TASK" banner shows the task title and "Send below" hint. Composer auto-opens with SMS/Email mode and the message pre-filled
- **Quick Action tiles** (Share My Card, Review Link, Send a Card, Showcase) all open a Contact Picker first, then navigate to the contact record with the action auto-triggered

### Contact Detail handleQuickAction Fix (Mar 2026)
- Added missing action handlers: `digitalcard`, `linkpage`, `congrats`, `showcase`
- Contact page supports `?action=xxx` query param to auto-trigger actions
- Action progress tracker items are now all clickable and functional

### LMS / Training Hub — Role-Based (Mar 2026)
- 4 training tracks with 21 total lessons covering all roles
- Role-based filtering, Admin CRUD at `/admin/manage-training`
- White Label Partner Guide track (5 lessons)
- Partner Dashboard Training Hub link

### Admin Onboarding Wizard, Partner Portal, First-Login Profile Completion
### Communication (carrier-agnostic messaging, white-label emails)
### Reporting & Activity (14+ metrics, scheduled delivery)

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
