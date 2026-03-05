# i'M On Social — Product Requirements Document

## Original Problem Statement
Full-stack Relationship Management System (RMS/CRM) for sales teams. Key goals: ease of use ("easy button"), activity tracking, gamification, AI-powered outreach, and multi-channel communication.

## Core Architecture
- **Frontend:** React Native (Expo) web app
- **Backend:** FastAPI (Python)
- **Database:** MongoDB
- **3rd Party:** Resend (email), Twilio (SMS - MOCKED), OpenAI (AI assistant), Emergent Integrations (object storage)

## What's Been Implemented

### Admin Onboarding Wizard (NEW - Mar 2026)
- **8-step guided wizard** at `/admin/setup-wizard` for turnkey client onboarding
- Steps: Organization & Store → Branding → Create User → Profile → Review Links → Templates → Tags → Handoff Checklist
- Create new org OR select existing org (with auto-populated store picker)
- Industry selector dropdown with 10 industry options
- Logo upload, brand color picker (10 colors), custom email footer
- User creation with auto-generated temp password + copy-to-clipboard
- User profile: headshot upload, job title, bio, social links (IG/FB/LinkedIn)
- Review links: Google, Facebook, Yelp, DealerRater, custom review links
- Pre-loaded message templates (6 defaults) with toggle on/off + add custom
- Tag creation and selection
- **Skip functionality** on Steps 2, 4, 5, 6, 7
- **Handoff Checklist**: shows completion status + user to-do items for skipped/incomplete steps
- Backend: `PUT /admin/users/{id}` now accepts `title`, `bio`, `photo_url`, `social_links`
- Backend: `PUT /admin/stores/{id}` now accepts `email_footer`, `industry`
- Backend wizard progress tracking via `/api/setup-wizard/progress/{org_id}`
- **Fully tested**: Backend 100% (10/10 tests), Frontend UI verified

### Authentication & Users
- JWT-based auth with role-based access
- Login persistence — extended timeout to 10s safety net

### Contact Management
- Full CRUD with photo upload/gallery
- Cancel/Save buttons, gold Save button, "Contact saved!" toast
- Phone optional when email is provided
- Photo viewer modal uses SafeAreaView (no more battery bar overlap)
- Photo gallery labels use actual card type (not hardcoded "congrats")

### Communication
- Carrier-agnostic messaging (Twilio or personal phone SMS fallback)
- Email sending via Resend with white-label branded HTML templates
- All communications logged as `contact_events`

### Home Screen Dashboard
- Quick action tiles + Action Items (pending tasks) + Recent Activity (from contact_events)
- Auto-refresh every 30 seconds

### Review Links
- Review links now load from BOTH user-level AND store-level settings
- Store-level links (Google, Yelp, Facebook, DealerRater, etc.) merge with user-level overrides
- All actions (Share Card, Review Link, Congrats, SMS, Email) now stay on the contact page

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
