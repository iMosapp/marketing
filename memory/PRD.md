# Product Requirements Document - i'M On Social

## Original Problem Statement
Full-stack Relationship Management System (RMS) for organizations, teams, and individuals. Enables digital business cards, personal reviews, social link pages, congrats cards, automated campaigns, CRM, leaderboards, and AI-powered assistance.

## Core Brand
- **Name**: i'M On Social
- **Domain**: imonsocial.com (marketing), app.imosapp.com (app)
- **Theme**: Clean white, blue (#007AFF) primary accent, brand colors (red, yellow, green, blue)
- **Logo**: Colorful ring with iM center + "On social" text

## Architecture
- Frontend: React Native (Expo) + Expo Router
- Backend: FastAPI + MongoDB
- Marketing: Static HTML (Vercel)
- Integrations: Resend (email), Twilio (SMS - mocked), OpenAI (AI assistant), Pillow (image gen)

## What's Been Implemented

### Completed (Mar 3, 2026)
- **MAJOR REBRAND**: All "iMOs" → "i'M On Social" across ~70 files
- **New Visual Theme**: All public /imos/ pages converted from dark/gold to clean white + blue
- **Proper Logo**: Official logo in all headers/footers via shared _components.tsx
- **Dropdown Navigation**: Calldrip/Podium-style Products/Solutions/Resources/Pricing menus
- **Marketing Site**: Rebuilt for Vercel deployment with new brand, messaging, dropdown nav
- **Paused Automation Visual**: Orange pause icon, strikethrough text, grey colors
- **Font Size Increase**: App-wide readability improvement (verified, no regressions)

### Previously Completed
- Engagement tracking (link clicks, views)
- Real-time activity feed (10s polling)
- Contact page redesign (Feed/Details tabs)
- Pause/Resume automations per contact
- Extensive light mode fixes (Inbox)
- Personal SMS fallback (carrier-agnostic)
- Comprehensive reporting system with scheduled emails
- White-label branded HTML emails
- Public REST API + outgoing webhooks
- Soft-delete system for users/contacts
- Automated lifecycle engine (apscheduler)
- 60+ tag icons
- Voice memo delete fix, photo feedback, tag creation fix

## Prioritized Backlog

### P0
- Gamification enhancements (already functional, may need UX polish)

### P1
- AI-Powered Outreach (suggest follow-ups on `sold` tag)
- Enrich VCF file with link page, review, showcase URLs
- Voice Help Assistant backend

### P2
- Refactor contact/[id].tsx (~4200 lines → smaller components)
- Full Twilio/Telnyx SMS integration
- WhatsApp integration
- Auth refactor (bcrypt hashing)
- Push notification dots on Activity tab
- Full Learning Management System
- Code cleanup (~80 files)
- React Hydration Error #418
- Mobile tags data sync

## Credentials
- Super Admin: forest@imosapp.com / Admin123!
- Contact email: forest@imonsocial.com

## Key Files
- `/app/frontend/app/imos/_components.tsx` — Shared header/footer (new logo, white theme)
- `/app/frontend/app/imos/index.tsx` — Main /imos landing page
- `/app/frontend/app/imos/pricing.tsx` — Pricing page (new white theme)
- `/app/frontend/app/imos/demo.tsx` — Demo request page (new white theme)
- `/app/marketing/build/index.html` — Vercel marketing site
- `/app/frontend/app/contact/[id].tsx` — Contact page (paused automation visual)

## Known Issues
- Twilio SMS is MOCKED
- Production email delivery may need RESEND_API_KEY verification
- Some lesser-visited /imos/ sub-pages may need individual theme spot-checks
