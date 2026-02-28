# i'M On Social (iMOs) - Product Requirements Document

## Original Problem Statement
Full-stack Relationship Management System (RMS) for automotive dealerships. React/Expo frontend, FastAPI backend, MongoDB database. The platform helps salespeople manage customer relationships, send personalized communications, track activities, and build social proof.

## Core Requirements
- Contact management with tagging, notes, and lifecycle tracking
- Multi-channel messaging (SMS, Email, Personal SMS fallback)
- Automated card generation (Congrats Cards, Birthday Cards)
- Public shareable pages (Digital Business Card, Showroom, Card Pages)
- Activity reporting with scheduled email delivery
- White-label branding ("Powered by i'M On Social")
- PWA support for iOS standalone mode
- Public REST API and webhook system for CRM integrations
- User lifecycle management with automated tagging
- Soft-delete data retention policy

## Architecture
- **Frontend:** React/Expo (port 3000)
- **Backend:** FastAPI (port 8001, prefixed /api)
- **Database:** MongoDB Atlas
- **Storage:** Emergent Object Storage
- **Email:** Resend
- **SMS:** Twilio (MOCK mode)
- **AI:** OpenAI GPT-5.2 via emergentintegrations
- **Scheduler:** APScheduler for daily jobs

## Key Features Implemented
- Authentication (JWT-based, plain-text passwords - bcrypt migration pending)
- Contact CRUD with tags, notes, activity history
- Inbox with SMS/Email modes, archive, swipe actions
- Congrats Card generation and public page
- Birthday Card generation and public page (NEW)
- The Showroom - public social proof page
- Digital Business Card
- Activity Reporting with date filters and scheduled email delivery
- White-label branded HTML emails via Resend
- Public REST API with API key authentication
- Outgoing webhooks for third-party integrations
- User lifecycle engine (automated daily scans)
- PWA manifest and meta tags for iOS standalone mode
- Share Showroom Link from More page (NEW)
- Inbox email-to-SMS mode switching fix (NEW)

## Credentials
- **Super Admin:** forest@imosapp.com / Admin123!

## Key API Endpoints
- POST /api/auth/login
- GET /api/contacts/{user_id}
- POST /api/messages/send/{user_id}
- POST /api/birthday/create
- GET /api/birthday/card/{card_id}
- GET /api/showcase/{user_id}
- GET /api/reports/activity-summary
- POST /api/reports/send-email-report

## 3rd Party Integrations
- Resend (email delivery - verified working)
- MongoDB Atlas (primary database)
- Twilio (MOCK mode)
- OpenAI GPT-5.2 (via emergentintegrations)
- Emergent Object Storage
- Pillow (image processing)

## Mocked Services
- Twilio SMS

## P0 Tasks (Completed)
- Birthday Card frontend page
- Inbox email/SMS mode switching fix
- Share Showroom Link on More page

## P1 Tasks (Upcoming)
- Gamification & Leaderboards
- AI-Powered Outreach (contextual follow-ups on "sold" tag)
- Refactor Authentication (bcrypt password hashing)
- Mobile Push Notifications (Phase 2)
- Clean production database for customer launch

## P2 Tasks (Future/Backlog)
- Full Twilio Integration (MOCK to live)
- WhatsApp Integration
- TestFlight Build for iOS
- Populate Training Hub with video content
- Full Inventory Management Module
- Code Cleanup (~80 files)
- Customer-Facing Gamification & Leaderboards
- React Hydration Error #418 fix
- Mobile app tags data sync issue

## Known Issues
- React Hydration Error #418 (P2)
- Mobile app tags data sync (P2)
