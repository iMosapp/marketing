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
- **7-step guided wizard** at `/admin/setup-wizard` for turnkey client onboarding
- Steps: Organization & Store -> Branding -> **Team Roster (Bulk)** -> Review Links -> Templates -> Tags -> Handoff
- Create new org OR select existing org (with store picker)
- Industry selector, logo upload, brand color picker, email footer
- **Bulk Team Roster**: Add multiple team members (name, email, phone, role) and create all at once
  - Each user gets auto-generated temp password
  - Users created with `onboarding_complete=false` and `needs_password_change=true`
- **Handoff Checklist**: Full credential table with Copy All + CSV Download, configuration status, remaining items
- Skip functionality on Steps 2, 4, 5, 6

### First-Login Profile Completion (Mar 2026)
- New page at `/auth/complete-profile` — 4-step guided onboarding for new users
- Steps: Upload Headshot -> Title & Bio -> Social Links -> Set Password
- Users with `onboarding_complete === false` are automatically redirected here after login
- Super admins are excluded from the redirect
- On completion, sets `onboarding_complete = true` and lands on dashboard
- Skip button available on each step
- Helpful tips and clear instructions throughout

### Backend Changes (Mar 2026)
- `POST /api/admin/users` now accepts `onboarding_complete` and `needs_password_change` fields
- `PUT /api/profile/{user_id}` now accepts `onboarding_complete`, `social_instagram`, `social_facebook`, `social_linkedin`
- `PUT /api/admin/users/{id}` accepts `title`, `bio`, `photo_url`, `social_links`
- `PUT /api/admin/stores/{id}` accepts `email_footer`, `industry`
- `StoreCreate` model now includes `website` and `industry` fields

### Authentication & Users
- JWT-based auth with role-based access
- Login flow checks: password change -> onboarding complete -> default route

### Contact Management
- Full CRUD with photo upload/gallery
- Phone optional when email provided

### Communication
- Carrier-agnostic messaging (Twilio or personal phone SMS fallback)
- Email sending via Resend with white-label branded HTML templates
- All communications logged as `contact_events`

### Reporting & Leaderboards
- Activity summary dashboard with 14+ metrics
- Store, Org, Global leaderboard levels

### Public API & Webhooks
- API-key authenticated REST API, outgoing webhook system

## Pending Issues
- P0: Production email delivery — BLOCKED on user verifying `RESEND_API_KEY` in production
- P2: React Hydration Error #418
- P2: Mobile app `tags` data sync

## Upcoming Tasks (Priority Order)
1. (P0) **Gamification & Leaderboards** — leaderboards for users, managers, and customers based on activity
2. (P1) **Quoting System** — flexible quoting with discounts and partner commissions
3. (P1) **AI-Powered Outreach** — sold tag triggers AI-suggested follow-up messages
4. (P1) **Refactor Authentication** — bcrypt password hashing
5. (P1) **Lead Notification System Phase 2** — mobile push notifications
6. (P1) **Voice Help Assistant Backend**

## Future/Backlog
- (P2) Code Cleanup (~80 files)
- (P2) Full Twilio/Telnyx Integration (currently MOCKED)
- (P2) WhatsApp Integration
- (P2) Training Hub content
- (P2) Inventory Management Module
- (P2) Partner/Reseller Portal

## Key Credentials
- Super Admin: forest@imosapp.com / Admin123!

## Mocked Services
- Twilio SMS: All SMS functionality is MOCKED
