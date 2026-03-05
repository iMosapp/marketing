# i'M On Social — Product Requirements Document

## Original Problem Statement
Full-stack Relationship Management System (RMS/CRM) for sales teams. Key goals: ease of use ("easy button"), activity tracking, gamification, AI-powered outreach, and multi-channel communication.

## Core Architecture
- **Frontend:** React Native (Expo) web app
- **Backend:** FastAPI (Python)
- **Database:** MongoDB
- **3rd Party:** Resend (email), Twilio (SMS - MOCKED), OpenAI (AI assistant), Emergent Integrations (object storage)

## What's Been Implemented

### Admin Onboarding Wizard (Mar 2026)
- 7-step guided wizard at `/admin/setup-wizard` for turnkey client onboarding
- Steps: Org & Store -> Branding -> Team Roster (Bulk) -> Review Links -> Templates -> Tags -> Handoff
- Bulk team creation with auto-generated temp passwords and CSV download
- Users created with `onboarding_complete=false` for first-login profile completion

### Partner Portal & Scoped Wizard (Mar 2026)
- **Partner Dashboard** (`/partner/dashboard`): Shows assigned orgs, locations, users with expandable cards
- **Partner Onboard Wizard** (`/partner/onboard`): 5-step scoped wizard (Location -> Branding -> Team -> Reviews -> Handoff)
- Partners can only add stores + users to orgs they're assigned to (cannot modify orgs)
- Backend portal endpoints: `GET /partners/portal/orgs`, `GET /partners/portal/orgs/{id}/stores`, `GET /partners/portal/orgs/{id}/users`
- Admin can assign orgs to partners via `POST /partners/portal/assign-org`
- Admin dashboard has "Partner Portal" link to preview what partners see

### First-Login Profile Completion (Mar 2026)
- `/auth/complete-profile` — 4-step guided onboarding for new users
- Steps: Upload Headshot -> Title & Bio -> Social Links -> Set Password
- Auto-redirect from login when `onboarding_complete === false`

### Partner Agreements (Mar 2026)
- **Custom Commission Structure**: Free-form text field for describing commission deals
- **White Label Checkbox**: Flag partners for white-label platform access
- Both show on agreement cards, detail pages, and in create/edit modals
- White-label partners also have commission notes on `/admin/white-label`

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
2. (P1) Quoting System
3. (P1) AI-Powered Outreach
4. (P1) Auth refactor (bcrypt)
5. (P1) Push notifications

## Future/Backlog
- Full Twilio integration, WhatsApp, Training Hub, Inventory Module, Code cleanup

## Key Credentials
- Super Admin: forest@imosapp.com / Admin123!

## Mocked Services
- Twilio SMS: All SMS functionality is MOCKED
