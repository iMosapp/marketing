# i'M On Social (iMOs) - Product Requirements Document

## Original Problem Statement
Full-stack Relationship Management System (RMS) for automotive dealerships. React/Expo frontend, FastAPI backend, MongoDB database. The platform helps salespeople manage customer relationships, send personalized communications, track activities, and build social proof.

## Architecture
- **Frontend:** React/Expo (port 3000)
- **Backend:** FastAPI (port 8001, prefixed /api)
- **Database:** MongoDB Atlas
- **Storage:** Emergent Object Storage
- **Email:** Resend (verified working)
- **SMS:** Twilio (MOCK mode)
- **AI:** OpenAI GPT-5.2 via emergentintegrations
- **Scheduler:** APScheduler for daily jobs

## Credentials
- **Super Admin:** forest@imosapp.com / Admin123!

## Key Features Implemented
- Contact management with tagging, notes, lifecycle tracking
- Multi-channel messaging (SMS, Email, Personal SMS fallback)
- Automated card generation (Congrats Cards, Birthday Cards)
- Public shareable pages (Digital Business Card, Showroom, Card Pages)
- Activity Reporting with scheduled email delivery
- White-label branded HTML emails via Resend
- Public REST API with API key authentication
- PWA manifest and meta tags for iOS standalone mode
- Email diagnostic endpoint for production troubleshooting
- Comprehensive [EMAIL-FLOW] logging
- Optimized Showcase/Showroom API (photos served via dedicated endpoints, not inline base64)

## Critical Bugs Fixed (2026-02-28)

### Email Pipeline Bugs
1. Frontend email prompt called wrong API endpoint (`/conversations/{id}` → 404 instead of `/messages/conversation/{id}/info`). Contact emails entered via prompt never saved.
2. Frontend didn't check send response status — showed failed emails as "sent"
3. Failed email events weren't tracked in `contact_events`
4. Added `getattr()` fallback for Resend SDK v2+ response objects
5. Added comprehensive `[EMAIL-FLOW]` logging at every pipeline step
6. Added diagnostic endpoint: `GET /api/messages/email-diagnostic/{user_id}/{contact_id}`

### Showroom Performance Bug
7. **Showroom "spinning wheel of death"**: API response was 2.9MB+ due to inline base64 photos. Fixed by:
   - Excluding base64 blobs from MongoDB queries
   - Serving photos via dedicated endpoints: `/api/showcase/photo/{card_id}`, `/api/showcase/user-photo/{user_id}`, `/api/showcase/store-logo/{store_id}`
   - Response size reduced from 2.9MB to 679 bytes (4,000x improvement)
   - Photos lazy-load via browser with `Cache-Control: max-age=86400`

### Inbox UX Bugs
8. Email prompt dismiss now auto-switches back to SMS mode
9. Share Showroom Link tile added to More page

## Key API Endpoints
- POST /api/messages/send/{user_id}
- GET /api/messages/email-diagnostic/{user_id}/{contact_id}
- GET /api/showcase/user/{user_id} (optimized - no inline photos)
- GET /api/showcase/photo/{card_id} (serves card photo as image)
- GET /api/showcase/user-photo/{user_id} (serves user photo)
- GET /api/showcase/store-logo/{store_id} (serves store logo)
- POST /api/birthday/create
- GET /api/birthday/card/{card_id}

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
- React Hydration Error #418
- Mobile app tags data sync

## Mocked Services
- Twilio SMS
