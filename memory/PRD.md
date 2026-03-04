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

### Turnkey Default Package (Complete - March 2026)
Full auto-provisioning on new user signup with:
- **SMS Templates (12):** Welcome, Add Socials Nudge, Review Ask, Review Follow-Up, Referral Ask, Check-In, Birthday, Anniversary, Congrats/Sold, Reactivation, Winback After Feedback, Just Because
- **Email Templates (8):** Welcome + Card Setup, Digital Business Card, Review Request, Follow-Up/Check-In, Referral Request, Congrats/Purchase, Reputation Rescue, Reactivation
- **Campaigns (6):** New Account Onboarding (5-step), First 10 Reviews Sprint (3-step), Ongoing Relationship Touches (5-step quarterly), Post-Purchase Follow-Up (5-step triggered by `sold` tag), Reputation Rescue (3-step triggered by `negative_feedback`), Social Growth Loop (3-step)
- **Date Triggers (6):** Birthday, Anniversary, Sold Date, Thanksgiving, Christmas, New Year's
- **Review Response Templates (3):** 5-Star, 3-4 Star, 1-2 Star
- **Social Content Starters (5):** Intro Post, Value Post, Proof Post, Community Post, Offer Post
- **Store-Level Defaults:** 8 tags (new_client, sold, hot_lead, cold_lead, referral, VIP, past_client, negative_feedback), 8 lead sources
- **CRUD Endpoints:** `/api/review-templates/{user_id}` and `/api/social-templates/{user_id}`
- **Backfill:** `POST /api/admin/seed/backfill-all` (idempotent)
- Service: `/app/backend/services/seed_defaults.py`
- Hooked into: signup, admin user creation, store creation

### Card Templates (Complete - March 2026)
- 6 types seeded per store (congrats, birthday, anniversary, thank you, welcome, holiday)
- Fixed fallback logic for birthday cards
- Backfill: `POST /api/congrats/templates/backfill`

### Contact Privacy Model (Complete - March 2026)
- `ownership_type: "personal"` vs `"org"` contacts
- Admin dashboard shows activity without exposing personal details
- Backfill: `POST /api/contacts/admin/backfill-ownership`

### Marketing Website (Complete - March 2026)
- 58 files in `/app/marketing/build/` (homepage, 20+ feature pages, pricing, demo, privacy, terms)
- All assets verified, 72px logo standardized, mobile hamburger menu rebuilt
- Live demo request form with source/UTM/ref tracking

### App Directory (Complete - March 2026)
- Public marketing directory at `/appdirectory/` mirrors in-app admin directory
- 14 categories, 94 pages total with search

### Lead & Referral Tracking (Complete)
- Backend: `/app/backend/routers/demo_requests.py`
- Frontend: `/app/frontend/app/admin/lead-tracking.tsx`
- Lead Attribution accessible from More → Reports and Contacts & Leads

### Core App Features (Previous Sessions)
- Carrier-agnostic messaging (personal SMS fallback)
- Centralized action handling through inbox composer
- Activity reporting with scheduled email delivery
- White-label branded HTML emails via Resend
- Soft-delete system for users/contacts
- Public REST API with API-key auth
- Outgoing webhook system
- User lifecycle engine (automated daily via apscheduler)

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
- `/app/backend/services/seed_defaults.py` — Turnkey account provisioning (all default data)
- `/app/backend/routers/review_templates.py` — Review response templates CRUD
- `/app/backend/routers/social_templates.py` — Social content templates CRUD
- `/app/backend/routers/auth.py` — Signup with auto-seeding
- `/app/backend/routers/admin.py` — Admin user/store creation with seeding + backfill endpoint
- `/app/backend/routers/campaigns.py` — Campaign management
- `/app/backend/routers/date_triggers.py` — Date trigger config
- `/app/marketing/build/` — Marketing site deployment root (58 files)
- `/app/backend/routers/congrats_cards.py` — Card template logic
- `/app/backend/routers/contacts.py` — Contact privacy model
- `/app/backend/routers/messages.py` — Messaging (email/SMS channel fix)
- `/app/backend/services/email_service.py` — White-label email templates

## 3rd Party Integrations
- **Resend:** Transactional emails
- **MongoDB Atlas:** Primary database
- **Twilio:** MOCK mode
- **OpenAI:** "Jessi" AI assistant
- **Vercel:** Marketing site deployment
