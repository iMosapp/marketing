# iMOs - Product Requirements Document

## Original Problem Statement
iMOs is a **Relationship Management System (RMS)** for retail/service businesses.

## Current Architecture
```
/app/frontend/app/imos/          # ALL PUBLIC PAGES (no auth required)
├── _layout.tsx                  # Stack layout
├── _components.tsx              # Shared ImosHeader + ImosFooter
├── index.tsx                    # Main marketing page (Calldrip-style hero)
├── hub.tsx                      # Page hub with quick links
├── app-directory.tsx            # Full 55-page catalog with search, copy, share
├── onboarding-preview.tsx       # 5-role onboarding walkthrough
├── salespresentation.tsx        # 10-slide interactive sales deck
├── features.tsx                 # Feature showcase (5 sections, 20 features)
├── pricing.tsx                  # Individual/Store pricing tabs
├── privacy.tsx                  # Privacy policy
├── terms.tsx                    # Terms of service
└── presentation.tsx             # Redirect → salespresentation
```

## What's Been Implemented
- [x] Full RMS with contacts, messaging, campaigns, AI assistant
- [x] Email invites, contact management, team hierarchy
- [x] CRM → RMS rebrand, MVPLine → iMOs rebrand
- [x] Automated Campaign Scheduler (APScheduler: daily date triggers + 15m campaign steps)
- [x] **Complete Public Marketing Site at /imos/** (Feb 25, 2026)
  - Main hero: "Old School Relationship Building. Modern Tools." (Calldrip-inspired)
  - Shared header: Home, Features, Pricing, Directory, Presentation + Sign Up / Log In
  - Shared footer: Product, Company, Get Started sections
  - /imos/app-directory: 55-page catalog across 11 categories with search, copy (app.imosapp.com URLs), share
  - /imos/onboarding-preview: 5-role interactive onboarding walkthrough
  - /imos/salespresentation: 10-slide fullscreen sales deck with keyboard nav
  - /imos/features, /imos/pricing, /imos/privacy, /imos/terms
  - Fully responsive (mobile hamburger menu, desktop full nav)

## Public Page Routes (app.imosapp.com)
| Route | Description |
|-------|-------------|
| /imos | Main marketing page |
| /imos/app-directory | Full 55-page catalog with search & share |
| /imos/onboarding-preview | 5-role onboarding walkthrough |
| /imos/hub | Quick page links |
| /imos/salespresentation | Sales deck (10 slides) |
| /imos/features | Feature showcase |
| /imos/pricing | Pricing plans |
| /imos/privacy | Privacy policy |
| /imos/terms | Terms of service |

## Known Issues
- React Hydration Error #418 (meta-refresh workaround)
- Mobile tags sync (needs user verification)
- Twilio SMS is MOCKED

## In Progress / Upcoming
- (P1) **White-Label System** — Org branding, custom domains
- (P1) Voice Help Assistant backend
- (P2) Training Hub content, Lead Notifications, Inventory, Reports

## Credentials
- Super Admin: forest@imosapp.com / Admin123!
