# i'M On Social — Product Requirements Document

## Original Problem Statement
Full-stack Relationship Management System (RMS) for sales professionals. React frontend + FastAPI backend + MongoDB. Features include digital cards, review pages, automated outreach, unified inbox, AI assistant, leaderboards, and a complete static marketing website.

## Core Architecture
- **Frontend:** React (Create React App) at `/app/frontend/`
- **Backend:** FastAPI at `/app/backend/`
- **Database:** MongoDB Atlas
- **Marketing Site:** Static HTML at `/app/marketing/build/` → deployed to Vercel at `imonsocial.com`
- **App Domain:** `app.imonsocial.com`

## What's Been Implemented

### Manual Campaign → Task + Notification System (Complete - March 2026)
When a manual campaign step fires (via 15-min scheduler or manual trigger), the system creates:
1. **campaign_pending_sends** record with message content, contact info, channel
2. **Task** on the user's to-do list (`type: campaign_send`, `priority: high`, linked to campaign/contact)
3. **Notification** (bell alert) with `action_required: true` so the user knows to act

When a **date trigger** fires (birthday, anniversary, sold date, holidays):
1. **Task** created (`type: date_trigger`, `priority: high`) with the pre-filled message
2. **Notification** (bell alert) saying "It's [Name]'s [trigger] today!"
3. Message queued for tracking

**Updated Task model** includes: `source`, `campaign_id`, `campaign_name`, `pending_send_id`, `channel`, `trigger_type`, `contact_phone`, `contact_email`

Key files:
- `/app/backend/scheduler.py` — Campaign step processor + date trigger processor
- `/app/backend/routers/campaigns.py` — Manual trigger endpoint
- `/app/backend/models.py` — Updated Task model

### Turnkey Default Package (Complete - March 2026)
Full auto-provisioning on new user signup with:
- **SMS Templates (12):** Welcome, Add Socials Nudge, Review Ask, Review Follow-Up, Referral Ask, Check-In, Birthday, Anniversary, Congrats/Sold, Reactivation, Winback After Feedback, Just Because
- **Email Templates (8):** Welcome + Card Setup, Digital Business Card, Review Request, Follow-Up/Check-In, Referral Request, Congrats/Purchase, Reputation Rescue, Reactivation
- **Campaigns (6):** New Account Onboarding (5-step), First 10 Reviews Sprint (3-step), Ongoing Relationship Touches (5-step quarterly), Post-Purchase Follow-Up (5-step triggered by `sold` tag), Reputation Rescue (3-step triggered by `negative_feedback`), Social Growth Loop (3-step)
- **Date Triggers (6):** Birthday, Anniversary, Sold Date, Thanksgiving, Christmas, New Year's
- **Review Response Templates (3):** 5-Star, 3-4 Star, 1-2 Star
- **Social Content Starters (5):** Intro Post, Value Post, Proof Post, Community Post, Offer Post
- **Store-Level Defaults:** 8 tags, 8 lead sources
- **CRUD Endpoints:** `/api/review-templates/{user_id}` and `/api/social-templates/{user_id}`
- **Backfill:** `POST /api/admin/seed/backfill-all` (idempotent)

### Card Templates (Complete - March 2026)
- 6 types seeded per store (congrats, birthday, anniversary, thank you, welcome, holiday)
- Fixed fallback logic for birthday cards

### Contact Privacy Model (Complete - March 2026)
- `ownership_type: "personal"` vs `"org"` contacts
- Admin dashboard shows activity without exposing personal details

### Marketing Website (Complete - March 2026)
- 58 files in `/app/marketing/build/`
- All assets verified, mobile hamburger menu rebuilt

### Core App Features (Previous Sessions)
- Carrier-agnostic messaging (personal SMS fallback)
- Centralized action handling through inbox composer
- Activity reporting with scheduled email delivery
- White-label branded HTML emails via Resend
- Soft-delete system for users/contacts
- Public REST API with API-key auth
- Outgoing webhook system
- User lifecycle engine (automated daily via apscheduler)
- Lead & Referral Tracking

## Credentials
- **Super Admin:** `forest@imosapp.com` / `Admin123!`

## Post-Deploy Commands (run once after each deploy)
```bash
curl -X POST https://app.imonsocial.com/api/admin/seed/backfill-all
curl -X POST https://app.imonsocial.com/api/congrats/templates/backfill
curl -X POST https://app.imonsocial.com/api/contacts/admin/backfill-ownership
curl -X POST https://app.imonsocial.com/api/auth/ref/backfill
```

## Prioritized Backlog

### P0
- Gamification & Leaderboards — activity-based leaderboards for users, managers, customers

### P1
- Onboarding UI Flow — choose account type, primary goal, show "Launch Score"
- AI-Powered Outreach — AI-suggested follow-ups on `sold` tag
- Enrich VCF File — add link page, review link, showcase URL
- Voice Help Assistant Backend
- Production marketing site logo link infinite spinner (user verification pending)

### P2
- Break down monolithic `contact/[id].tsx` (~4200 lines)
- Full Twilio/Telnyx Integration (currently MOCKED)
- Push notification indicators on Activity tab
- Learning Management System (LMS)
- WhatsApp Integration
- Refactor auth to bcrypt hashed passwords
- Partner/Reseller Portal
- React Hydration Error #418
- Mobile app tags data sync issue

## Key Files
- `/app/backend/scheduler.py` — Campaign step processor + date triggers (creates tasks + notifications)
- `/app/backend/routers/campaigns.py` — Campaign CRUD + enrollment + manual trigger
- `/app/backend/services/seed_defaults.py` — Turnkey account provisioning
- `/app/backend/routers/review_templates.py` — Review response templates CRUD
- `/app/backend/routers/social_templates.py` — Social content templates CRUD
- `/app/backend/routers/tasks.py` — Task CRUD
- `/app/backend/routers/notifications.py` — Notification system
- `/app/backend/models.py` — Updated Task model with campaign fields
- `/app/backend/routers/auth.py` — Signup with auto-seeding
- `/app/backend/routers/admin.py` — Admin user/store creation + backfill

## 3rd Party Integrations
- **Resend:** Transactional emails
- **MongoDB Atlas:** Primary database
- **Twilio:** MOCK mode
- **OpenAI:** "Jessi" AI assistant
- **Vercel:** Marketing site deployment
