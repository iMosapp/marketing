# iMOs - Product Requirements Document

## Original Problem Statement
Full-stack Relationship Management System (RMS) for dealerships. The app empowers sales teams with digital cards, automated campaigns, AI assistants, review management, and customer relationship tools.

## Core Architecture
- **Frontend:** React Native (Expo) with web support
- **Backend:** FastAPI (Python)
- **Database:** MongoDB Atlas (production), localhost:27017 (preview)
- **Email:** Resend
- **SMS:** Twilio (MOCK mode)
- **AI:** OpenAI GPT-5.2 (Jessi assistant, Relationship Intel, AI Campaign Engine), Whisper (Voice Notes)
- **Object Storage:** Emergent Integrations (image uploads, voice notes)

## What's Been Implemented

### Session Feb 28, 2026 (Fork 10 - Current)

#### UI/UX Audit & Cleanup
- **Favicon Replacement** — New logo across all sizes
- **"Touches" Label Fix** — Shortened "Touchpoints" on contact detail page
- **More Page Cleanup** — Removed duplicate "Train Jessi AI" from Profile & AI section, enlarged profile card (60x60 avatar, 19px name), maintained quick actions
- **My Activity Enhancement** — Added "All Time" and "Custom" period pills with date range picker (native HTML date inputs on web)
- **Company Docs Redesign** — Category headers now modern cards with icon, title, description, and count badge
- **Inbox Swipe Fix** — WebSwipeableItem close overlay uses native `<div>` on web for reliable click capture, added document click listener for close-on-outside-click
- **Inbox Archive Fix** — handleArchive now uses optimistic UI update + `await loadConversations()`
- **Backend** — Added `all_time` period support to `/api/reports/user-activity/{user_id}`

### Previous Sessions (Fork 9)
- Notifications Center + Analytics Dashboard
- AI-Powered Campaign Outreach System with dual delivery modes
- Pre-Built Campaign Templates (5 templates)
- Campaign Builder UI with template picker

### Earlier Sessions
- Contact activity feed, swipe gestures, voice notes, AI relationship intel, leaderboards, photo fixes
- Public REST API, webhooks, soft-delete, lifecycle engine
- Personal SMS mode, event tracking, activity reports, white-label emails
- Operations manual, NDA system, digital signing

## Known Issues
- (P2) React Hydration Error #418
- (P2) Mobile app tags sync

## Upcoming Tasks
- (P1) Mobile Push Notifications
- (P1) Auth refactor (bcrypt)
- (P1) Clean production database for customer launch

## Future/Backlog
- (P2) Customer-facing gamification
- (P2) Full Twilio live mode
- (P2) WhatsApp integration
- (P2) TestFlight iOS build
- (P2) Training Hub content
- (P2) Inventory Management Module
- (P2) Refactor contact/[id].tsx (2000+ lines)

## Credentials
- **Super Admin:** forest@imosapp.com / Admin123!
