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
- POST /api/birthday/create (auto from contact_id)
- POST /api/birthday/create-manual (photo upload, mirrors congrats flow)
- GET /api/birthday/card/{card_id}
- GET /api/birthday/card/{card_id}/image (downloadable PNG)

## Completed (2026-02-28 - Session 2)
- **Birthday Card Creation Flow Cloned from Congrats Card**: Created `/settings/create-birthday-card.tsx` mirroring the congrats card flow (photo upload, name/phone/email, custom message, create, share options). Added `POST /api/birthday/create-manual` backend endpoint. Updated More page tile to navigate to the new creation page.
- **Birthday Card Campaign Integration**: Added `include_birthday_card` toggle to birthday date trigger config. When enabled (default ON), the daily scheduler and manual trigger processor auto-generate a birthday card for each matching contact and append the card link to the outgoing message. Tag-based triggers ("birthday"/"bday") also auto-create cards.
- **Card Preview Before Sending**: Both Congrats and Birthday card creation pages now have a 3-step flow: Fill Form -> Preview Card (see how it looks) -> Edit or Create & Send -> Share Options. Replaced the old "Create & Share Card" button with "Preview Card".
- **Back Button on Card View Pages**: Both `/congrats/{cardId}` and `/birthday/{cardId}` public view pages now have a "Back" button at the top to return to the share/send screen after reviewing.
- **Full Logo/Icon Rebrand**: Replaced all favicons, app icons, login logo, email logo, PWA manifest icons, splash screen, and adaptive icons across frontend/backend/marketing with the new "iM On Social" multicolor logo.
- **Onboarding Redesigned as Quick Wins Walkthrough**: 13-slide interactive flow for salespeople (role-specific for managers/admins with extra slides). Slides: Welcome → Profile Check → 8 Quick Win slides (Digital Card, Congrats Cards, Birthday Cards, Review Page, Showroom, Quick Actions, CSV Import, Campaigns) each with visual demo, benefits, and "Try It Now" button → AI Setup → Checklist → Complete.
- **Admin App Directory Expanded**: Added 3 new top-level categories: Public Customer Pages (8), Quick Win Tools (8), Analytics & Reporting (7). Now 88 total pages with Preview, Copy Link, and Share on every entry.

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
