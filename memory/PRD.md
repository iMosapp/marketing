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

### Session Feb 28, 2026 (Fork 9 - Current)

#### Notifications Center + Analytics Dashboard
- **Notifications Center** — Unified hub aggregating 7 data sources with category filtering, mark-as-read, full-page UI.
- **Analytics Dashboard** — Multi-level (Org/Store/Personal) dashboard with KPI hero card, 10-metric grid, trend chart, channel breakdown, per-user table, store comparison, period selector.

#### AI-Powered Campaign Outreach System
- **AI Clone Prompt System** — Global default prompt (genericized from user's provided prompt) + per-user overrides. Dynamically hydrates from user profile data.
- **AI Message Generation** — GPT-5.2 generates personalized messages using contact history + salesperson persona. SMS and email channels.
- **AI Virtual Assistant Reply Handler** — Handles inbound replies with 1-3 min human-like delay.
- **Dual Delivery Modes** — Automated (10AM-12PM sends, AI replies) vs Manual (notification -> review -> send via native app).
- **Enhanced Campaign Model** — delivery_mode, ai_enabled, ownership_level (user/store/org), channel + ai_generated per step.
- **Pending Sends System** — CRUD for manual campaign pending sends with review page.
- **Enhanced Campaign Builder** — Delivery Mode cards, AI toggle, Campaign Level, channel selector per step.

#### Pre-Built Campaign Templates (5 templates)
1. **Sold - Complete Follow-Up** (5 steps, 1 year) — Day 3 check-in, Day 14 referral ask, Month 2 first service reminder, Month 7 touch base, Month 12 anniversary celebration. Trigger: `sold`
2. **Be-Back / Working Customer** (4 steps, 1 month) — Day 1 thank you, Day 5 value add, Day 14 resource offer, Month 1 final check. Trigger: `be_back`
3. **Service Reminder Series** (3 steps, 10 days) — Proactive service notification, 1-week follow-up, post-service experience check. Trigger: `service_due`
4. **Referral Thank You & Nurture** (3 steps, 3 months) — Immediate thank you, 1-week referral update, 3-month relationship maintenance. Trigger: `referral`
5. **VIP Customer Experience** (4 steps, 10 months) — VIP welcome, monthly insider updates, quarterly email insights, 6-month personal check-in. Trigger: `vip`
- Template picker screen with metadata badges (steps, duration, trigger tag, AI) + "Build Custom" option.
- All templates AI-enabled with step-level context hints for personalized generation.

### Previous Sessions
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
