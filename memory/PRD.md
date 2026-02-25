# iMOs - Product Requirements Document

## Original Problem Statement
iMOs is a **Relationship Management System (RMS)** for retail/service businesses.

## Public Marketing Site
All 57 pages at `app.imosapp.com/imos/...` — no auth required.

### Header Nav (Customer-Facing)
- iMOs logo | Features | Solutions | Resources | Pricing | **Sign In** (outlined) | **Get Demo** (gold)

### Key CTAs
- "Schedule a Demo" → `/imos/demo` (lead capture form)
- "Start 14-Day Free Trial" → `/auth/signup`

### Page Structure
```
/imos/                     # Main hero page
/imos/demo                 # Schedule a Demo form (lead capture)
/imos/features             # Feature showcase
/imos/pricing              # Individual/Store pricing
/imos/hub                  # Solutions page links
/imos/app-directory        # Full 55-page catalog
/imos/onboarding-preview   # 5-role onboarding walkthrough
/imos/salespresentation    # 10-slide sales deck
/imos/privacy | /terms     # Legal
/imos/[43 preview pages]   # Static previews of every authenticated feature
/imos/campaigns/           # Campaign subfolder (index, email, dashboard)
```

### Design System
- Background: True black `#000`
- Accent: Gold `#C9A962`
- Mockup types: list, stats, chat, cards, form

## What's Been Implemented
- [x] Full RMS with contacts, messaging, campaigns, AI
- [x] Automated Campaign Scheduler (APScheduler)
- [x] 57 public pages at /imos/ (all verified)
- [x] Customer-facing header (no internal links exposed)
- [x] Schedule a Demo lead capture form
- [x] 14-day free trial messaging across all CTAs
- [x] True black background everywhere
- [x] Responsive mobile + desktop

## Known Issues
- Twilio SMS MOCKED
- React Hydration Error #418

## Upcoming
- (P1) White-Label System
- (P1) Voice Help Assistant

## Credentials
- Super Admin: forest@imosapp.com / Admin123!
