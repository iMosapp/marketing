# iMOs - Product Requirements Document

## Original Problem Statement
iMOs is a business management / CRM app for retail/service businesses. Key features include:
- User/team management with role-based invite flows (cascading invites)
- Store management with organizational hierarchy
- SMS/messaging capabilities (Twilio - mocked)
- Partner agreements, Review management
- AI assistant (Jessi)
- Lead Sources & Routing system
- Digital business card with sharing
- Role-based onboarding (Org Admin, Store Manager, Salesperson)
- Date-triggered campaigns (birthdays, anniversaries, sold dates, holidays)
- Tag-triggered campaign auto-enrollment

## Current Architecture
```
/app
├── backend/
│   ├── server.py              # Main entry, branding/logo, DB indexes on startup
│   ├── routers/
│   │   ├── admin.py           # User mgmt, Resend email invites (CID logo)
│   │   ├── contacts.py        # Contact CRUD, auto-tagging, tag-campaign enrollment
│   │   ├── date_triggers.py   # NEW: Date triggers config, holidays, processing
│   │   ├── campaigns.py       # Campaigns with trigger_tag support
│   │   ├── users.py           # User profile, onboarding
│   │   └── team_invite.py     # Team invite links
│   ├── models.py              # Pydantic models
│   └── static/                # Email assets
├── frontend/
│   ├── app/
│   │   ├── (tabs)/
│   │   │   ├── contacts.tsx   # Optimized: debounce, memoized, FlatList perf
│   │   │   └── more.tsx       # No title, Date Triggers link
│   │   ├── settings/
│   │   │   ├── date-triggers.tsx  # NEW: Dates & Holidays config tabs
│   │   │   └── invite-team.tsx    # Rebuilt: direct invite form
│   │   └── contact/[id].tsx   # Auto-tagging, campaign enrollment on save
│   └── services/api.ts
```

## What's Been Implemented
- [x] Email invites with CID-embedded iMOs logo + tagline
- [x] Add Contact modal with email field
- [x] More page: no title, Invite Team in Administration
- [x] Invite Team page rebuilt with working form
- [x] Contacts page performance optimization
- [x] Phone number underlines removed
- [x] Date-triggered campaigns (birthday/anniversary/sold date/holidays)
- [x] Auto-tagging on contact date saves
- [x] Tag-triggered campaign auto-enrollment
- [x] Holiday picker (14 US holidays)
- [x] Date Triggers settings page

## Known Issues
- React Hydration Error #418 (meta-refresh workaround)
- Mobile tags sync (needs user verification)
- Twilio SMS is MOCKED

## Upcoming Tasks
- (P1) Voice Help Assistant backend
- (P1) Set up daily cron for date trigger processing
- (P2) Training Hub, Lead Notifications, Inventory, Reports

## Credentials
- Super Admin: forest@imosapp.com / Admin123!
- Test invite email: im4est@icloud.com
