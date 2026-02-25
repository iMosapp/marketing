# iMOs - Product Requirements Document

## Original Problem Statement
iMOs is a **Relationship Management System (RMS)** for retail/service businesses. Key features include:
- User/team management with role-based invite flows
- Store management with organizational hierarchy
- SMS/messaging capabilities (Twilio)
- AI assistant (Jessi)
- Lead Sources & Routing
- Digital business card
- Date-triggered & tag-triggered campaigns with automated scheduling
- App Directory for browsing & sharing all app pages
- Interactive sales presentation for prospects/investors
- White-label ready for organizations
- Public marketing site at /imos/ with full page directory

## Current Architecture
```
/app
├── backend/
│   ├── server.py               # Main entry, scheduler lifecycle
│   ├── scheduler.py            # APScheduler: daily date triggers + 15m campaign steps
│   ├── routers/
│   │   ├── campaigns.py        # Campaign CRUD, enrollments, calculate_next_send_date
│   │   ├── date_triggers.py    # Date trigger configs, holidays, process logic
│   │   ├── messages.py         # Multi-channel SMS/Email sending
│   │   ├── scheduler_admin.py  # /scheduler/status, manual triggers
│   │   └── ...
├── frontend/
│   ├── app/
│   │   ├── imos/               # PUBLIC MARKETING SITE (no auth required)
│   │   │   ├── _layout.tsx     # Stack layout
│   │   │   ├── _components.tsx # Shared ImosHeader + ImosFooter
│   │   │   ├── index.tsx       # Main marketing page (Calldrip-style hero)
│   │   │   ├── hub.tsx         # Page directory with share URLs
│   │   │   ├── salespresentation.tsx  # 10-slide interactive sales deck
│   │   │   ├── features.tsx    # Feature showcase (5 sections)
│   │   │   ├── pricing.tsx     # Public pricing (Individual/Store tabs)
│   │   │   ├── privacy.tsx     # Privacy policy
│   │   │   ├── terms.tsx       # Terms of service
│   │   │   └── presentation.tsx # Redirect → salespresentation
│   │   ├── (tabs)/
│   │   ├── admin/
│   │   ├── settings/
│   │   └── auth/
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
- [x] CRM → RMS rebrand (all references)
- [x] Automated Campaign Scheduler (Feb 25, 2026)
- [x] **Public Marketing Site at /imos/** (Feb 25, 2026)
  - Main hero page: "Old School Relationship Building. Modern Tools." with Calldrip-style layout
  - Shared header with nav (Home, Features, Pricing, Hub, Presentation) + Sign Up / Login
  - Shared footer with Product, Company, Get Started link columns
  - /imos/hub: Page directory with app.imosapp.com share URLs
  - /imos/salespresentation: 10-slide interactive sales deck
  - /imos/features: 5-section feature showcase
  - /imos/pricing: Individual/Store pricing tabs
  - /imos/privacy + /imos/terms: Legal pages
  - Fully responsive (mobile hamburger menu, desktop full nav)

## Known Issues
- React Hydration Error #418 (meta-refresh workaround)
- Mobile tags sync (needs user verification)
- Twilio SMS is MOCKED (messages queued to DB, not actually sent)
- Minor: Privacy/Terms API content shows raw markdown (## and **) - needs renderer

## In Progress / Upcoming
- (P1) **White-Label System** — Org branding, custom domains, "Powered by iMOs"
- (P1) Voice Help Assistant backend
- (P2) Training Hub content
- (P2) Lead Notifications, Inventory, Reports

## Credentials
- Super Admin: forest@imosapp.com / Admin123!
- Test invite: im4est@icloud.com

## Public Page Routes (app.imosapp.com)
- /imos — Main marketing page
- /imos/hub — Page directory
- /imos/salespresentation — Sales deck
- /imos/features — Feature showcase
- /imos/pricing — Pricing plans
- /imos/privacy — Privacy policy
- /imos/terms — Terms of service
