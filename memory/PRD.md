# iMOs - Product Requirements Document

## Original Problem Statement
iMOs is a **Relationship Management System (RMS)** for retail/service businesses.

## Public Marketing Site
All 57 pages at `app.imosapp.com/imos/...` — no auth required.

### Header Nav (Customer-Facing)
- iMOs logo | Features | Solutions | Resources | Pricing | **Sign In** (outlined) | **Get Demo** (gold)

### Key CTAs
- "Schedule a Demo" -> `/imos/demo` (lead capture form)
- "Start 14-Day Free Trial" -> `/auth/signup`

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
- [x] Admin App Directory updated with all 57 public /imos/ pages
- [x] All email invite URLs updated to public /imos/ domain
- [x] /imos/login and /imos/signup redirect to actual auth pages
- [x] Team Chat: delete channel & clear history functionality
- [x] Inbox: removed SMS/Email toggle pills from header
- [x] Avatar system fixed - auto-backfill thumbnails from raw photos
- [x] Image quality upgraded to 1080px for outbound sharing
- [x] Contact list avatar backfill: auto-generates thumbnails for contacts with raw photo but missing photo_thumbnail (Feb 25, 2026)
- [x] Training Hub: Populated with 16 topics across 6 categories (Getting Started, Messaging, AI Features, Sales Tools, Campaigns, Team Features) with step-by-step instructions, video embed support, voice/text AI help (Feb 25, 2026)
- [x] SOPs: Fixed "MVPLine" branding to "iMOs" across all 13 SOPs in database and seed data. Admin > Training & SOPs page verified working (Feb 25, 2026)

## Known Issues
- Twilio SMS MOCKED
- React Hydration Error #418
- Email invite URL is hardcoded to `https://app.imosapp.com` (tech debt)

## Upcoming
- (P1) Fix hardcoded email URL with centralized config
- (P1) Voice Help Assistant Backend
- (P1) White-Label System (custom domains, org branding)

## Future/Backlog (P2)
- Enable Lead Notification System
- Build full Inventory Management Module
- Create Searchable Training Manual
- Populate Reports & Analytics section
- Fix React Hydration Error #418
- Verify mobile tags data sync
- Test leaderboard toggle functionality

## Credentials
- Super Admin: forest@imosapp.com / Admin123!

## 3rd Party Integrations
- MongoDB Atlas: Primary database
- Resend: Transactional and user-initiated emails (working)
- Twilio: SMS messaging (MOCKED)
- OpenAI: "Jessi" AI assistant

## Key DB Schema
- **contacts:** `{..., photo: <base64_string>, photo_url: <string>, photo_thumbnail: <string>}`
  - `photo`: large original upload (used for processing, excluded from list queries)
  - `photo_url`: thumbnail for display
  - `photo_thumbnail`: 96px version for UI avatars
- **contact_photos:** `{contact_id, user_id, photo_full: <1080px_base64>, updated_at}`
- **sops:** `{title, summary, department, category, is_required_reading, estimated_time, difficulty, tags, steps, related_sops, ...}`
- **users:** Same photo structure as contacts
