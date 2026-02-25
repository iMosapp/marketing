# iMOs - Product Requirements Document

## Original Problem Statement
iMOs is a **Relationship Management System (RMS)** for retail/service businesses.

## Public Marketing Site Architecture
All 56 pages live at `app.imosapp.com/imos/...` — no auth required.

### Page Types
1. **Full Pages** (10): Main hero, features, pricing, sales presentation, onboarding preview, app directory, hub, privacy, terms
2. **Static Preview Pages** (43): Each authenticated feature has a public preview with phone mockup, description, bullets, and "Sign Up Free" CTA
3. **Campaign Subfolder** (3): /campaigns, /campaigns/email, /campaigns/dashboard

### File Structure
```
/app/frontend/app/imos/
├── _layout.tsx           # Stack layout
├── _components.tsx       # Shared ImosHeader + ImosFooter (true black #000)
├── _preview.tsx          # Reusable PreviewPage component with 5 mockup types
├── _pagedata.ts          # All 43 preview page configurations centralized
├── index.tsx             # Main marketing hero page
├── hub.tsx               # Quick page links
├── app-directory.tsx     # Full 55-page catalog with search/copy/share
├── onboarding-preview.tsx # 5-role onboarding walkthrough
├── salespresentation.tsx # 10-slide sales deck
├── features.tsx          # Feature showcase
├── pricing.tsx           # Individual/Store pricing
├── privacy.tsx / terms.tsx # Legal
├── campaigns/            # Campaign subfolder
│   ├── _layout.tsx
│   ├── index.tsx / email.tsx / dashboard.tsx
└── [43 preview pages]    # inbox, contacts, dialer, team, etc.
```

## Design System
- **Background**: True black `#000`
- **Accent**: Gold `#C9A962`
- **Header**: Sticky, iMOs logo + nav (Home, Features, Pricing, Directory, Presentation) + Login/Signup
- **Footer**: Logo, Product/Company/Get Started columns, copyright
- **Mockup types**: list, stats, chat, cards, form

## What's Been Implemented
- [x] Full RMS with contacts, messaging, campaigns, AI assistant
- [x] Automated Campaign Scheduler (APScheduler)
- [x] 56 public pages at /imos/ (all verified working)
- [x] True black background across all public pages
- [x] 5 mockup types for authenticated feature previews
- [x] Responsive mobile + desktop design

## Known Issues
- React Hydration Error #418 (meta-refresh workaround)
- Mobile tags sync (needs user verification)
- Twilio SMS is MOCKED

## Upcoming
- (P1) White-Label System
- (P1) Voice Help Assistant backend
- (P2) Training Hub content, Lead Notifications, Inventory, Reports

## Credentials
- Super Admin: forest@imosapp.com / Admin123!
