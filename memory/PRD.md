# iMOs - Product Requirements Document

## Original Problem Statement
iMOs is a business management / CRM app for retail/service businesses. Key features include:
- User/team management with role-based invite flows (cascading invites)
- Store management with organizational hierarchy
- SMS/messaging capabilities (Twilio)
- Partner agreements, Review management
- AI assistant (Jessi)
- Lead Sources & Routing system
- Digital business card with sharing
- Role-based onboarding (Org Admin, Store Manager, Salesperson)
- Date-triggered campaigns (birthdays, anniversaries, sold dates, holidays)
- Tag-triggered campaign auto-enrollment
- App Directory for super admins to browse & share all app pages

## Current Architecture
```
/app
├── backend/
│   ├── server.py              # Main entry, DB indexes on startup
│   ├── routers/
│   │   ├── admin.py           # User mgmt, Resend email invites (dynamic URL)
│   │   ├── app_directory.py   # NEW: Page sharing via email/SMS
│   │   ├── contacts.py        # Contact CRUD, auto-tagging, thumbnails
│   │   ├── date_triggers.py   # Date triggers config, holidays
│   │   ├── campaigns.py       # Campaigns with trigger_tag support
│   │   └── ...
│   ├── models.py
│   └── static/
├── frontend/
│   ├── app/
│   │   ├── (tabs)/
│   │   │   ├── contacts.tsx   # Optimized: debounce, memoized, FlatList
│   │   │   └── more.tsx       # Nested indented card-style dropdowns
│   │   ├── admin/
│   │   │   └── app-directory.tsx  # NEW: Page catalog with share functionality
│   │   ├── settings/
│   │   │   ├── date-triggers.tsx
│   │   │   └── invite-team.tsx
│   │   └── ...
│   └── services/api.ts
```

## What's Been Implemented
- [x] Email invites with CID-embedded iMOs logo + tagline
- [x] Add Contact modal with email field
- [x] More page: nested indented card-style dropdowns (Feb 2026)
- [x] Invite Team page rebuilt with working form
- [x] Contacts page performance optimization (thumbnail system)
- [x] Phone number underlines removed
- [x] Date-triggered campaigns foundation
- [x] Auto-tagging on contact date saves
- [x] Tag-triggered campaign auto-enrollment
- [x] Holiday picker (14 US holidays)
- [x] Avatar pills size increase in inbox
- [x] **App Directory panel** - 57 pages, 11 categories, Preview/Copy/Share (Feb 2026)
- [x] **Email link fix** - Dynamic URL detection for preview vs production (Feb 2026)

## Known Issues
- React Hydration Error #418 (meta-refresh workaround)
- Mobile tags sync (needs user verification)
- Twilio SMS integration (real, but may need verification)
- Avatar consistency in inbox search dropdown (unverified)

## In Progress Tasks
- (P1) Complete Campaign Automation (backend cron/scheduling needed)

## Upcoming Tasks
- (P1) Implement Voice Help Assistant backend
- (P1) Set up daily cron for date trigger processing
- (P2) Training Hub content
- (P2) Lead Notification System
- (P2) Inventory Management Module
- (P2) Searchable Training Manual
- (P2) Reports & Analytics

## Credentials
- Super Admin: forest@imosapp.com / Admin123!
- Test invite email: im4est@icloud.com
