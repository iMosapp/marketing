# iMOs - Product Requirements Document

## Original Problem Statement
iMOs is a **Relationship Management System (RMS)** for retail/service businesses. Key features include:
- User/team management with role-based invite flows
- Store management with organizational hierarchy
- SMS/messaging capabilities (Twilio)
- AI assistant (Jessi)
- Lead Sources & Routing
- Digital business card
- Date-triggered & tag-triggered campaigns
- App Directory for browsing & sharing all app pages
- Interactive sales presentation for prospects/investors
- White-label ready for organizations

## Current Architecture
```
/app
├── backend/
│   ├── server.py
│   ├── routers/
│   │   ├── admin.py           # User mgmt, Resend email invites
│   │   ├── app_directory.py   # Page sharing via email/SMS
│   │   ├── contacts.py        # Contact CRUD, auto-tagging, campaign enrollment
│   │   ├── date_triggers.py   # Date triggers config, holidays
│   │   └── ...
│   └── services/jessie_service.py  # AI assistant (rebranded to RMS)
├── frontend/
│   ├── app/
│   │   ├── (tabs)/
│   │   │   ├── contacts.tsx   # Optimized, thumbnails
│   │   │   └── more.tsx       # Nested indented cards, Phone in Communication
│   │   ├── imos/              # PUBLIC PAGES HUB (no auth required)
│   │   │   ├── index.tsx      # Hub landing page
│   │   │   ├── presentation.tsx  # 10-slide interactive sales deck
│   │   │   └── features.tsx   # Feature showcase (5 sections)
│   │   ├── admin/
│   │   │   ├── app-directory.tsx
│   │   │   ├── onboarding-preview.tsx
│   │   │   └── users/[id].tsx
│   │   ├── thread/[id].tsx    # Congrats card + tag/campaign enrollment
│   │   └── settings/
│   │       ├── invite-team.tsx  # Individual role option
│   │       └── ...
│   └── services/api.ts
```

## What's Been Implemented
- [x] Email invites with CID-embedded logo
- [x] Contacts page performance (thumbnail system)
- [x] More page: nested indented card-style dropdowns
- [x] App Directory (57+ pages, share via email/SMS)
- [x] Invite Team: Individual role for Super Admin
- [x] Phone/Dialer in Communication section
- [x] Onboarding Preview (5 role walkthroughs)
- [x] Campaign Tag & Enroll on congrats card
- [x] Contact ownership warnings on deactivation/deletion
- [x] **CRM → RMS rebrand** (all references across frontend + backend)
- [x] **Public Pages Hub** `/imos/` — hub, presentation, features, pricing
- [x] **Interactive Sales Presentation** — 10 slides, keyboard nav, shareable
- [x] **Features Showcase** — 5 sections, 20 features detailed
- [x] Email link fix (dynamic URL detection)

## Known Issues
- React Hydration Error #418 (meta-refresh workaround)
- Mobile tags sync (needs user verification)
- Integrations page loading spinner for users without store_id

## In Progress / Upcoming
- (P0) **White-Label System** — Org branding, custom domains, "Powered by iMOs"
- (P1) Campaign Automation backend (cron/scheduling)
- (P1) Voice Help Assistant backend
- (P2) Training Hub content
- (P2) Lead Notifications, Inventory, Reports

## Credentials
- Super Admin: forest@imosapp.com / Admin123!
- Test invite: im4est@icloud.com
