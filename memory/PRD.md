# Product Requirements Document - i'M On Social

## Original Problem Statement
Full-stack Relationship Management System (RMS) for organizations, teams, and individuals. Enables digital business cards, personal reviews, social link pages, congrats cards, automated campaigns, CRM, leaderboards, and AI-powered assistance.

## Core Brand
- **Name**: i'M On Social
- **Domain**: imonsocial.com (marketing), app.imonsocial.com (app)
- **Theme**: Clean white, blue (#007AFF) primary accent, brand colors (red, yellow, green, blue)
- **Logo**: Colorful ring with iM center + "On social" text

## Architecture
- Frontend: React Native (Expo) + Expo Router
- Backend: FastAPI + MongoDB
- Marketing: Static HTML (Vercel) at `/app/marketing/build/index.html`
- Integrations: Resend (email), Twilio (SMS - mocked), OpenAI (AI assistant), Pillow (image gen)

## What's Been Implemented

### Completed (Mar 3, 2026 - This Session)
- **APP DIRECTORY PAGE**: Created static `/appdirectory/` page with 60+ pages organized by category, search filtering, collapsible sections. Tested and validated.
- **LOGIN PAGE LIGHT THEME**: Fixed `/auth/login` from dark theme to white/light theme. Tested with credentials.
- **FORGOT PASSWORD LIGHT THEME**: Fixed `/auth/forgot-password` from dark to white/light theme.
- **SALES PRESENTATION REWORK**: Complete rewrite of `/imos/salespresentation` — 10 slides, clean white theme, color-coded accents. CTA now routes to demo form with `?source=sales_presentation` tracking.
- **ONBOARDING SLIDES LIGHT THEME**: Updated all onboarding slides (slideLibraries.ts, onboarding/index.tsx, onboarding-preview.tsx, admin/onboarding-preview.tsx) from dark/gold to light/blue theme.
- **PRIVACY POLICY**: Complete rewrite with 10 official legal sections covering data collection, usage, storage, sharing, rights, retention, cookies, children's privacy, changes, and contact.
- **TERMS OF SERVICE**: Complete rewrite with 13 official legal sections covering acceptance, service description, accounts, acceptable use, billing, IP, data ownership, API terms, liability, termination, modifications, governing law, and contact.
- **PRICING UPDATE**: Starter plan changed from $49 to $79/mo.
- **LANDING PAGE LIGHT THEME**: Updated `/landing.html` CSS from dark/gold (--bg:#000, --gold:#C9A962) to light/blue (--bg:#FFFFFF, --gold:#007AFF).
- **4 AD PAGES LIGHT THEME**: Updated `ad-digital-card.html`, `ad-reviews.html`, `ad-showcase.html`, `ad-autopilot.html` from dark/gold to light/blue theme.

### Completed (Mar 3, 2026 - Previous Session)
- **MARKETING SITE REDESIGN**: Complete rewrite of `/app/marketing/build/index.html`
  - Content-driven, no stock photos, no fake testimonials
  - Podium/Kenect/Calldrip-competitive nav with dropdown menus
  - Every product card links to actual product pages on app.imosapp.com
  - Hero: "The backend work that makes you a rockstar."
  - Bottom CTA: "Salespeople just need help remembering who they know."
  - Sections: Hero, Product Grid (6 cards), Big Features (3 rows), Stats, Industries (4), How It Works, More Tools, Bottom CTA, Footer
  - All CTAs drive to demo, signup, or specific product pages

### Previously Completed (Mar 3, 2026)
- **MAJOR REBRAND**: All "iMOs" -> "i'M On Social" across ~70 files
- **New Visual Theme**: All public /imos/ pages from dark/gold to clean white + blue
- **Dropdown Navigation**: Calldrip/Podium-style Products/Solutions/Resources/Pricing menus
- **Paused Automation Visual**: Orange pause icon, strikethrough text
- **Font Size Increase**: App-wide readability improvement
- **Light Mode Fixes**: Fixed hardcoded dark conversation bubbles in thread view

### Earlier Completed
- Engagement tracking, real-time activity feed
- Contact page redesign (Feed/Details tabs)
- Pause/Resume automations per contact
- Personal SMS fallback (carrier-agnostic)
- Comprehensive reporting system with scheduled emails
- White-label branded HTML emails
- Public REST API + outgoing webhooks
- Soft-delete system for users/contacts
- Automated lifecycle engine (apscheduler)
- 60+ tag icons

## Prioritized Backlog

### P0
- Gamification & Leaderboards (implement/verify full functionality)
- Light mode UI fixes testing (thread bubbles, digital card mockup) - PENDING TEST

### P1
- AI-Powered Outreach (suggest follow-ups on `sold` tag)
- Enrich VCF file with link page, review, showcase URLs
- Voice Help Assistant backend

### P2
- Refactor contact/[id].tsx (~4200 lines -> smaller components)
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

## Key Files
- `/app/marketing/build/index.html` -- Vercel marketing site (REWRITTEN)
- `/app/marketing/build/appdirectory/index.html` -- Static app directory page
- `/app/marketing/generate_pages.py` -- Script to generate all static pages
- `/app/frontend/public/marketing.html` -- Preview copy of marketing site
- `/app/frontend/app/auth/login.tsx` -- Login page (FIXED: light theme)
- `/app/frontend/app/auth/forgot-password.tsx` -- Forgot password (FIXED: light theme)
- `/app/frontend/app/auth/signup.tsx` -- Signup page (light theme)
- `/app/frontend/app/imos/_components.tsx` -- Shared header/footer (new logo, white theme)
- `/app/frontend/app/imos/salespresentation.tsx` -- Sales presentation (REWRITTEN: 10 slides)
- `/app/frontend/app/imos/privacy.tsx` -- Privacy policy (REWRITTEN: 10 sections)
- `/app/frontend/app/imos/terms.tsx` -- Terms of service (REWRITTEN: 13 sections)
- `/app/frontend/app/imos/pricing.tsx` -- Pricing page (Starter: $79)
- `/app/frontend/app/onboarding/slideLibraries.ts` -- Onboarding slides (FIXED: light theme)
- `/app/frontend/public/landing.html` -- Landing page (FIXED: light/blue theme)
- `/app/frontend/public/ad-digital-card.html` -- Ad page (FIXED: light/blue)
- `/app/frontend/public/ad-reviews.html` -- Ad page (FIXED: light/blue)
- `/app/frontend/public/ad-showcase.html` -- Ad page (FIXED: light/blue)
- `/app/frontend/public/ad-autopilot.html` -- Ad page (FIXED: light/blue)
- `/app/frontend/app/thread/[id].tsx` -- Message thread (light mode fix pending test)
- `/app/frontend/app/contact/[id].tsx` -- Contact page (paused automation visual)
- `/app/marketing/vercel.json` -- Vercel deployment config

## Known Issues
- Twilio SMS is MOCKED
- Production email delivery may need RESEND_API_KEY verification
- Light mode thread bubbles fix needs testing
