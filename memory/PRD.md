# i'M On Social — Product Requirements Document

## Original Problem Statement
Full-stack Relationship Management System (RMS/CRM) for sales teams. Key goals: ease of use ("easy button"), activity tracking, gamification, AI-powered outreach, and multi-channel communication. The user envisions a "turnkey" system that minimizes their personal involvement in onboarding and training.

## Core Architecture
- **Frontend:** React Native (Expo) web app
- **Backend:** FastAPI (Python)
- **Database:** MongoDB
- **3rd Party:** Resend (email), Twilio (SMS - MOCKED), OpenAI (AI assistant), Emergent Integrations (object storage)

## What's Been Implemented

### Contact Page Bug Fixes (Mar 2026)
- **Photo Attachment:** New `pickComposerPhoto()` function properly sets `selectedMedia` state. Photo preview shows in composer with "Photo attached" label and remove button. Photo uploads to `/api/images/upload` on send and URL is included in the message.
- **Composer Text Expansion:** TextInput now has `minHeight: 44`, `maxHeight: 200`, `textAlignVertical: 'top'` for proper expansion when templates prefill long messages.
- **Auto-Refresh Disabled:** Removed 15-second polling interval that was jumping users back to the top of the activity feed. Events now only refresh on page focus and after user actions.

### Home Screen & Action Items Fix (Mar 2026)
- Notification Bell now uses `Modal` component (renders above tiles)
- Action Items navigate to contact record with prefilled composer
- Task Banner on contact page shows task context and auto-opens composer
- Quick Action tiles open Contact Picker → Contact Record flow

### Lead Tracking Back Button Fix (Mar 2026)
- Fixed hardcoded white colors on back button, period tabs, bar backgrounds

### LMS / Training Hub — Role-Based (Mar 2026)
- 4 training tracks with 21 total lessons covering all roles
- Role-based filtering, Admin CRUD at `/admin/manage-training`
- White Label Partner Guide track (5 lessons)

### Admin Onboarding Wizard, Partner Portal, First-Login Profile Completion
### Communication (carrier-agnostic messaging, white-label emails)
### Reporting & Activity (14+ metrics, scheduled delivery)

## Pending Issues
- P0: Production email delivery — BLOCKED on user verifying `RESEND_API_KEY`
- P2: React Hydration Error #418
- P2: Mobile app `tags` data sync

## Upcoming Tasks
1. (P0) Gamification & Leaderboards
2. (P1) Automated Welcome Emails after wizard user creation
3. (P1) Link Orgs from Partner Agreement View
4. (P1) Quoting System
5. (P1) AI-Powered Outreach

## Future/Backlog
- Auth refactor (bcrypt), Push notifications, Voice Help Assistant
- Full Twilio integration (currently MOCKED), WhatsApp Integration
- Inventory Management Module, Code cleanup (~80 files)

## Key Credentials
- Super Admin: forest@imosapp.com / Admin123!

## Mocked Services
- Twilio SMS: All SMS functionality is MOCKED
