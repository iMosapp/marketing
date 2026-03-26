# i'M On Social - Product Requirements Document

## Original Problem Statement
Build a Relationship Management System (RMS) / CRM for automotive sales professionals. AI-powered, human-to-human relationship building where every follow-up is deliberate, meaningful, and personal.

## Core Architecture
- **Frontend:** React Native / Expo (web)
- **Backend:** FastAPI (Python)
- **Database:** MongoDB Atlas
- **Marketing Site:** Static HTML in `/app/marketing/build/` (deployed to Vercel via GitHub)
- **Integrations:** Resend (email), Twilio (MOCKED), OpenAI (via emergentintegrations), Emergent Object Storage, Pillow, qrcode, apscheduler

---

## What's Been Implemented

### Convert Contact to User Workflow (Mar 26, 2026) -- LATEST
- **"Import from Contact" in Add User Modal:** Admins can search CRM contacts by name/email/phone directly in the Add User modal and auto-fill the form fields.
- **Backend Auto-Linking:** When creating a user from a contact (`source_contact_id`), the backend automatically:
  - Tags the source contact with `imos_user` and role-specific tag (e.g., `imos_store_manager`)
  - Sets `linked_user_id`, `linked_store_name`, `linked_store_id`, `linked_org_name`, `linked_role` on the contact document
  - Skips auto-creating a duplicate contact (since the contact already exists)
- **Linked App Account Card:** Contact detail page displays a blue card showing the linked user's role and store/org when a contact has been converted to an app user.
- **Fix:** Contact Pydantic model updated with `linked_*` fields so they're included in API responses.
- **Fix:** Contact search API response handling — properly handles both list and object response formats.

### AI Persona Wizard Redesign (Mar 26, 2026)
- Converted the overwhelming single-scroll AI Persona page into a 4-step wizard
- Each step shows only 3-5 fields max

### Auth: Forgot Password Email Case Bug + Admin Password Reset (Mar 26, 2026)
- Fixed email casing bug in forgot password flow
- Added `PUT /api/admin/users/{user_id}/reset-password` endpoint

### Brand Kit Theme Support for All Public Pages (Mar 26, 2026)
- All public pages (Showcase, Landing Page, Link Page) now respect Brand Kit light/dark toggle

### Address & Mapping (Mar 26, 2026)
- Added Zip Code, Country, Website to Orgs, Stores, Users
- Added "Get Directions" deep-link button to Digital Card

### Campaign System Fixes (Mar 24, 2026)
- Scheduler hourly delay + AI toggle override bugs + Campaign Journey Feature

---

## Key API Endpoints
- `POST /api/auth/login`
- `POST /api/admin/users/create` — Accepts `source_contact_id` for contact-to-user conversion
- `PUT /api/admin/users/{user_id}/reset-password`
- `GET /api/contacts/{user_id}?search=X` — Returns plain JSON array
- `GET /api/campaigns/contact/{contact_id}/journey`

---

## Prioritized Backlog

### P1
- App Store Preparation (eas.json, push notifications)
- AI-Powered Outreach (sold tag follow-ups)
- Gamification & Leaderboards

### P2
- Full Twilio Integration (currently MOCK)
- WhatsApp Integration
- Stripe for partner invoices
- Inventory Management Module
- Mobile tags sync issue
- Refactor large files (admin.py, contact/[id].tsx)

## Test Credentials
- Super Admin: `forest@imosapp.com` / `Admin123!`

## 3rd Party Integrations
- **Resend:** Transactional emails
- **MongoDB Atlas:** Primary database
- **Twilio:** MOCK mode
- **OpenAI:** AI features via emergentintegrations
- **apscheduler:** Backend job scheduling

## Key Files Modified This Session
- `/app/frontend/app/admin/users.tsx` — Import from Contact search UI, response format fix
- `/app/backend/routers/admin.py` — source_contact_id handling with auto-tagging and store linking
- `/app/frontend/app/contact/[id].tsx` — Linked App Account card, linked_* fields in state
- `/app/backend/models.py` — Added linked_* fields to Contact Pydantic model
