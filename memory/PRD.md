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

## Current Architecture
```
/app
├── backend/
│   ├── server.py               # Main entry, scheduler lifecycle
│   ├── scheduler.py            # APScheduler: daily date triggers + 15m campaign steps
│   ├── routers/
│   │   ├── admin.py
│   │   ├── app_directory.py
│   │   ├── campaigns.py        # Campaign CRUD, enrollments, calculate_next_send_date
│   │   ├── contacts.py
│   │   ├── date_triggers.py    # Date trigger configs, holidays, process logic
│   │   ├── messages.py         # Multi-channel SMS/Email sending
│   │   ├── scheduler_admin.py  # /scheduler/status, manual triggers
│   │   └── ...
│   └── services/jessie_service.py
├── frontend/
│   ├── app/
│   │   ├── (tabs)/
│   │   │   ├── contacts.tsx
│   │   │   └── more.tsx
│   │   ├── imos/               # PUBLIC PAGES HUB
│   │   │   ├── index.tsx
│   │   │   ├── presentation.tsx
│   │   │   └── features.tsx
│   │   ├── admin/
│   │   │   ├── app-directory.tsx
│   │   │   └── onboarding-preview.tsx
│   │   └── settings/
│   │       └── invite-team.tsx
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
- [x] CRM → RMS rebrand (all references)
- [x] Public Pages Hub `/imos/` — hub, presentation, features
- [x] Interactive Sales Presentation — 10 slides, keyboard nav
- [x] Features Showcase — 5 sections, 20 features detailed
- [x] Email link fix (dynamic URL detection)
- [x] **Automated Campaign Scheduler** (Feb 25, 2026)
  - APScheduler with 2 jobs: daily date triggers (8 AM UTC), campaign step processor (every 15m)
  - Birthday, anniversary, sold-date, and holiday matching
  - Deduplication via date_trigger_log
  - Manual trigger endpoints for admin testing
  - Health/status API: GET /api/scheduler/status

## Known Issues
- React Hydration Error #418 (meta-refresh workaround)
- Mobile tags sync (needs user verification)
- Twilio SMS is MOCKED (messages queued to DB, not actually sent)

## In Progress / Upcoming
- (P1) **White-Label System** — Org branding, custom domains, "Powered by iMOs"
- (P1) Voice Help Assistant backend
- (P2) Training Hub content
- (P2) Lead Notifications, Inventory, Reports

## Credentials
- Super Admin: forest@imosapp.com / Admin123!
- Test invite: im4est@icloud.com
