# iMOs - Product Requirements Document

## Original Problem Statement
Full-stack Relationship Management System (RMS) for dealerships. The app empowers sales teams with digital cards, automated campaigns, AI assistants, review management, and customer relationship tools.

## Core Architecture
- **Frontend:** React Native (Expo) with web support
- **Backend:** FastAPI (Python)
- **Database:** MongoDB Atlas (production), localhost:27017 (preview)
- **Email:** Resend (verified working)
- **SMS:** Twilio (MOCK mode)
- **AI:** OpenAI GPT-5.2, Whisper
- **Object Storage:** Emergent Integrations

## What's Been Implemented

### Session Feb 28, 2026 (Fork 10 - Current)

#### The Showroom — Social Proof Landing Page (NEW)
- **Public page** at `/showcase/{user_id}` — Instagram-style feed of delivery photos + reviews
- **Three levels:** Per-user, per-store, per-org
- **Auto-populated** from congrats cards, matched with reviews by phone/name
- **CTAs:** "Leave a Review" button linking to digital card page, "View My Digital Business Card" link
- **Share:** Shareable link + QR code
- **Management:** Hide/show individual entries
- **"The Showroom" tile** in More > Performance section
- Backend: `/app/backend/routers/showcase.py` (6 endpoints)
- Frontend: `/app/frontend/app/showcase/[id].tsx`

#### Email System Verified Working
- Full E2E flow: Frontend → Resend API → Gmail delivery confirmed

#### UI/UX Audit & Cleanup
- More Page: Removed duplicate "Train Jessi AI", enlarged profile card
- My Activity: Added "All Time" + "Custom" date range picker
- Company Docs: Modern category cards
- Inbox Swipe: Fixed close overlay + archive optimistic UI

### Previous Sessions
- AI Campaign Engine, Pre-Built Templates, Notifications Center, Analytics Dashboard
- Contact activity feed, voice notes, AI relationship intel, leaderboards
- Public REST API, webhooks, soft-delete, lifecycle engine
- Personal SMS mode, event tracking, activity reports, white-label emails

## Known Issues
- (P2) React Hydration Error #418
- (P2) Mobile app tags sync

## Upcoming Tasks
- (P1) Mobile Push Notifications
- (P1) Auth refactor (bcrypt)
- (P1) Clean production database

## Future/Backlog
- (P2) Customer-facing gamification
- (P2) Full Twilio live mode
- (P2) WhatsApp integration
- (P2) TestFlight iOS build
- (P2) Training Hub content
- (P2) Inventory Management Module

## Credentials
- **Super Admin:** forest@imosapp.com / Admin123!
