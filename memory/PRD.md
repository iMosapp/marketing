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
- Onboarding Preview for super admins to walk through each role's experience
- Campaign Tag & Enroll on send (congrats card flow)

## Current Architecture
```
/app
├── backend/
│   ├── server.py
│   ├── routers/
│   │   ├── admin.py           # User mgmt, Resend email invites (dynamic URL)
│   │   ├── app_directory.py   # Page sharing via email/SMS
│   │   ├── contacts.py        # Contact CRUD, auto-tagging, thumbnails, campaign enrollment
│   │   ├── date_triggers.py   # Date triggers config, holidays
│   │   ├── campaigns.py       # Campaigns with trigger_tag support
│   │   └── ...
│   ├── models.py
│   └── static/
├── frontend/
│   ├── app/
│   │   ├── (tabs)/
│   │   │   ├── contacts.tsx   # Optimized: debounce, memoized, FlatList
│   │   │   └── more.tsx       # Nested indented cards, Phone in Communication
│   │   ├── admin/
│   │   │   ├── app-directory.tsx   # Page catalog with share functionality
│   │   │   ├── onboarding-preview.tsx  # Interactive role walkthrough
│   │   │   └── users/[id].tsx  # Contact ownership warnings
│   │   ├── thread/[id].tsx    # Congrats card with tag picker + campaign enrollment
│   │   ├── settings/
│   │   │   ├── invite-team.tsx  # Individual role option for super admins
│   │   │   ├── date-triggers.tsx
│   │   │   └── ...
│   │   └── onboarding/
│   │       ├── index.tsx
│   │       ├── slideLibraries.ts  # Role-specific onboarding slides
│   │       └── types.ts
│   └── services/api.ts
```

## What's Been Implemented
- [x] Email invites with CID-embedded iMOs logo + tagline
- [x] Add Contact modal with email field
- [x] More page: nested indented card-style dropdowns
- [x] Invite Team page rebuilt with working form
- [x] Contacts page performance optimization (thumbnail system)
- [x] Phone number underlines removed
- [x] Date-triggered campaigns foundation
- [x] Auto-tagging on contact date saves
- [x] Tag-triggered campaign auto-enrollment
- [x] Holiday picker (14 US holidays)
- [x] Avatar pills size increase in inbox
- [x] App Directory panel (57+ pages, 11 categories, Preview/Copy/Share)
- [x] Email link fix (dynamic URL detection for preview vs production)
- [x] Invite Team: Individual role option for Super Admin (no org required)
- [x] Phone/Dialer added to Communication section on More page
- [x] Onboarding Preview: interactive walkthrough for all 5 roles
- [x] Campaign Tag & Enroll on congrats card send (tag picker + auto-enrollment)
- [x] Contact ownership warnings on user deactivation/deletion

## Known Issues
- React Hydration Error #418 (meta-refresh workaround)
- Mobile tags sync (needs user verification)
- Avatar consistency in inbox search dropdown (unverified)

## In Progress Tasks
- (P1) Complete Campaign Automation backend (scheduling/cron for date triggers)

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
