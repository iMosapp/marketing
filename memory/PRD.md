# i'M On Social — Product Requirements Document

## Original Problem Statement
Full-stack Relationship Management System (RMS/CRM) for sales teams. Key goals: ease of use ("easy button"), activity tracking, gamification, AI-powered outreach, and multi-channel communication.

## Core Architecture
- **Frontend:** React Native (Expo) web app
- **Backend:** FastAPI (Python)
- **Database:** MongoDB
- **3rd Party:** Resend (email), Twilio (SMS - MOCKED), OpenAI (AI assistant), Emergent Integrations (object storage)

## What's Been Implemented

### Authentication & Users
- JWT-based auth with role-based access (super_admin, org_admin, store_admin, user)
- User management with soft-delete support

### Contact Management
- Full CRUD for contacts with photo upload/gallery
- Contact edit flow with Cancel/Save buttons, gold Save button, "Contact saved!" toast
- Phone is optional when email is provided (relaxed validation)
- "Set as Profile Photo" from gallery closes modal after success
- Photo picker with error handling and web fallback
- Quick Add form for new contacts (progressive disclosure)

### Communication
- Carrier-agnostic messaging (Twilio or personal phone SMS fallback)
- Email sending via Resend with white-label branded HTML templates
- All communications logged as `contact_events`

### Home Screen Dashboard
- Quick action tiles: Share My Card, Review Link, Send a Card, My Showcase, Keypad, Add Contact
- **Action Items section** — Shows pending campaign tasks with:
  - Task title, campaign source, channel icon
  - Red "Overdue" labels for past-due tasks
  - Green checkmark to mark as done (removes from list instantly)
  - Tapping navigates to contact page with pre-filled message
- **Recent Activity feed** — Pulls from `contact_events` collection (FIXED)
  - Tappable items with chevron → navigates to contact detail page
  - Proper icon/color mapping for all event types
  - Auto-refresh every 30 seconds + relative timestamp refresh every 60 seconds

### Notifications
- Bell notifications with deep-linking
- Lead claim flow (notification -> claim -> create contact -> pre-filled message)

### Campaigns & Automation
- Campaign management with multi-step flows
- Date-based triggers, Tag-triggered campaign enrollment
- Scheduled task processing (every 15 min)

### Reporting & Leaderboards
- Activity summary dashboard with 14+ metrics
- Date filters and scheduled email delivery
- Store, Org, Global leaderboard levels with category breakdowns

### Public API & Webhooks
- API-key authenticated REST API
- Outgoing webhook system for CRM integration

## Pending Issues
- P1: Production marketing site logo link causes infinite spinner (likely browser cache)
- P2: React Hydration Error #418
- P2: Mobile app `tags` data sync
- P2: Leaderboard toggle functionality not fully tested

## Upcoming Tasks (Priority Order)
1. (P1) AI-Powered Outreach — sold tag triggers AI-suggested follow-up messages
2. (P1) Refactor Authentication — bcrypt password hashing
3. (P1) Enrich VCF File — add link page, review link, showcase URL
4. (P1) Voice Help Assistant Backend

## Future/Backlog
- (P2) Full Twilio/Telnyx Integration (currently MOCKED)
- (P2) WhatsApp Integration
- (P2) Partner/Reseller Portal
- (P2) Full LMS (Learning Management System)
- (P2) Code cleanup (~80 files)
- (P2) Break down contact/[id].tsx (~4300 lines)

## Key Credentials
- Super Admin: forest@imosapp.com / Admin123!

## Mocked Services
- Twilio SMS: All SMS functionality is MOCKED
