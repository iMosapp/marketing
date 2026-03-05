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
- JWT-based auth with role-based access
- **Login persistence** — extended timeout to 10s safety net so AsyncStorage can load before redirect
- User management with soft-delete support

### Contact Management
- Full CRUD with photo upload/gallery
- Cancel/Save buttons, gold Save button, "Contact saved!" toast
- Phone optional when email is provided
- "Set as Profile Photo" closes modal after success

### Communication
- Carrier-agnostic messaging (Twilio or personal phone SMS fallback)
- Email sending via Resend with white-label branded HTML templates
- All communications logged as `contact_events`

### Home Screen Dashboard
- Quick action tiles: Share My Card, Review Link, Send a Card, My Showcase, Keypad, Add Contact
- **Action Items section** — pending campaign tasks with overdue indicators + mark done
- **Recent Activity feed** — pulls from `contact_events`, auto-refresh 30s, tappable items

### Activity Tab (Bottom Nav)
- **Rewritten with FlatList virtualization** — prevents freezing on large datasets
- 52px avatar tiles, 16px bold names (larger, more readable)
- Auto-refresh every 30 seconds + pull-to-refresh
- Tappable items with chevron → navigate to contact page
- Date grouping (Today, Yesterday, etc.)
- Reduced load from 100 to 50 items

### Card Type Tracking (FIXED)
- **Birthday card → "Viewed Birthday Card"** (was always "Viewed Congrats Card")
- **Thank You card → "Viewed Thank You Card"**
- **Holiday card → "Viewed Holiday Card"**
- Short URL dedup window reduced from 1 hour to 5 minutes (captures re-visits)

### Reporting & Leaderboards
- Activity summary dashboard with 14+ metrics
- Store, Org, Global leaderboard levels

### Public API & Webhooks
- API-key authenticated REST API
- Outgoing webhook system for CRM integration

## Pending Issues
- P1: Production marketing site logo link causes infinite spinner (likely browser cache)
- P2: React Hydration Error #418
- P2: Mobile app `tags` data sync

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
