# iMOs - Product Requirements Document

## Original Problem Statement
iMOs is a business management / CRM app for retail/service businesses. Key features include:
- User/team management with role-based invite flows (cascading invites)
- Store management with organizational hierarchy
- SMS/messaging capabilities (Twilio - mocked)
- Partner agreements
- Review management
- AI assistant (Jessi)
- Lead Sources & Routing system
- Digital business card with sharing
- Role-based onboarding (Org Admin, Store Manager, Salesperson)

## User Personas
- **Super Admin:** Full system access, manages organizations, views stats
- **Org Admin:** Manages stores and store managers within an organization
- **Store Manager:** Manages salespeople and daily operations
- **Salesperson:** Manages contacts, leads, and customer relationships

## Core Requirements
1. Contact management with quick-add (first name, last name, phone, email)
2. Team hierarchy: Org > Store > Salesperson
3. Cascading invite system with branded email notifications
4. Role-based onboarding experiences
5. Digital business card with share modal
6. Admin dashboard with quick stats
7. Lead source routing and notifications

## Current Architecture
```
/app
├── backend/              # FastAPI + MongoDB
│   ├── server.py         # Main entry point, includes branding/logo endpoint
│   ├── routers/
│   │   ├── admin.py      # User management, Resend email invites (CID logo)
│   │   ├── contacts.py   # Contact CRUD
│   │   ├── users.py      # User profile, onboarding completion
│   │   ├── lead_sources.py
│   │   ├── notifications.py
│   │   └── demo_requests.py
│   ├── models.py         # Pydantic models
│   └── static/           # Email assets (imos-logo-email.png)
├── frontend/             # React Native/Expo (web export)
│   ├── app/
│   │   ├── admin/        # Admin dashboard with collapsible sections + Quick Stats
│   │   ├── card/         # Digital business card with Share Contact modal
│   │   ├── (tabs)/
│   │   │   ├── contacts.tsx  # Contact list + expanded Add Contact modal
│   │   │   ├── inbox.tsx
│   │   │   └── more.tsx      # Direct admin links
│   │   └── onboarding/
│   │       ├── index.tsx         # Role-based onboarding + cascading invites
│   │       ├── slideLibraries.ts # Slide content per role
│   │       └── types.ts
│   └── services/api.ts   # API service layer
```

## 3rd Party Integrations
- **MongoDB Atlas:** Primary database
- **Resend:** Live transactional emails (user invites with CID-embedded logo)
- **Twilio:** SMS messaging (MOCKED)
- **OpenAI:** Jessi AI assistant

## Key DB Schema
- **users:** `onboarding_complete` (boolean), `role` (string) drive UX
- **contacts:** `first_name`, `last_name`, `phone`, `email`, `tags`, `photo_url`

## What's Been Implemented
- [x] Digital card flow fix + back button
- [x] Admin dashboard redesign with collapsible sections
- [x] Quick Stats dashboard for super admins
- [x] Share Contact modal (URL, Text, Email, vCard, QR)
- [x] Role-based onboarding (Org Admin, Store Manager, Salesperson)
- [x] Cascading invite system (onboarding -> invite team)
- [x] Live email invites via Resend with CID-embedded logo
- [x] "Relationship Management System" tagline in email header
- [x] Email field in Add Contact modal (Feb 2026)
- [x] Direct admin links on More page

## Known Issues
- React Hydration Error #418 (recurring, meta-refresh workaround in place)
- Mobile `tags` data sync (needs user verification)
- Avatar consistency in inbox search dropdown
- Twilio SMS is MOCKED

## Credentials
- Super Admin: forest@imosapp.com / Admin123!
- Test invite email: im4est@icloud.com
- Additional test users in /app/TEST_DATA_TRACKER.json
