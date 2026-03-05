# i'M On Social — Product Requirements Document

## Original Problem Statement
Full-stack Relationship Management System (RMS/CRM) for sales teams. Key goals: ease of use ("easy button"), activity tracking, gamification, AI-powered outreach, and multi-channel communication.

## Core Architecture
- **Frontend:** React Native (Expo) web app
- **Backend:** FastAPI (Python)
- **Database:** MongoDB
- **3rd Party:** Resend (email), Twilio (SMS - MOCKED), OpenAI (AI assistant), Emergent Integrations (object storage)

## What's Been Implemented

### Authentication & Users
- JWT-based auth with role-based access
- Login persistence — extended timeout to 10s safety net

### Contact Management
- Full CRUD with photo upload/gallery
- Cancel/Save buttons, gold Save button, "Contact saved!" toast
- Phone optional when email is provided
- Photo viewer modal uses SafeAreaView (no more battery bar overlap)
- Photo gallery labels use actual card type (not hardcoded "congrats")

### Communication
- Carrier-agnostic messaging (Twilio or personal phone SMS fallback)
- Email sending via Resend with white-label branded HTML templates
- All communications logged as `contact_events`

### Home Screen Dashboard
- Quick action tiles + Action Items (pending tasks) + Recent Activity (from contact_events)
- Auto-refresh every 30 seconds

### Review Links
- Review links now load from BOTH user-level AND store-level settings
- Store-level links (Google, Yelp, Facebook, DealerRater, etc.) merge with user-level overrides
- Handles custom review links stored as arrays in store settings
- Fixed: Contact page was calling non-existent `/store/` endpoint instead of `/admin/stores/`
- All actions (Share Card, Review Link, Congrats, SMS, Email) now stay on the contact page
- Opens modals/composer locally instead of navigating to inbox thread
- Suggested actions pre-fill the composer with the message text
- User can update notes, view history, and continue working without extra navigation
- ScrollView-based rendering (fixed FlatList web virtualization bug)
- Larger tiles, auto-refresh every 30s, tappable items → contact detail
- 100 events loaded per page
- Native `<img>` tags on web with lazy loading for avatars
- Backend optimized: DB indexes on contact_events, no heavy photo blobs in feed

### Public-Facing Pages — ALL FIXED
- **No back buttons** on any customer-facing page
- **Inline "Leave a Review"** on all pages (digital card, congrats, showcase)
  - Expandable star rating + feedback form — no redirects
- **Inline "Refer a Friend"** on all pages
  - Share/copy functionality with native share sheet
- **Card type-specific events** (FIXED):
  - Birthday card → "Viewed Birthday Card" / "Downloaded Birthday Card"
  - Thank You card → "Viewed Thank You Card" / "Downloaded Thank You Card"
  - Holiday card → "Viewed Holiday Card" / "Downloaded Holiday Card"
  - Photo source stores actual card type
  - Short URL link_type uses actual card type
  - Track download/share uses actual card type
- Short URL dedup window: 5 minutes (was 1 hour)

### Reporting & Leaderboards
- Activity summary dashboard with 14+ metrics
- Store, Org, Global leaderboard levels

### Public API & Webhooks
- API-key authenticated REST API, outgoing webhook system

## Pending Issues
- P1: Production marketing site logo link causes infinite spinner (likely browser cache)
- P2: React Hydration Error #418
- P2: Mobile app `tags` data sync

## Upcoming Tasks (Priority Order)
1. (P1) AI-Powered Outreach — sold tag triggers AI-suggested follow-up messages
2. (P1) Refactor Authentication — bcrypt password hashing
3. (P1) Enrich VCF File — add link page, review link, showcase URL
4. (P1) Voice Help Assistant Backend

## Future/Backlog
- (P2) Full Twilio/Telnyx Integration (currently MOCKED)
- (P2) WhatsApp Integration
- (P2) Partner/Reseller Portal
- (P2) Full LMS, Code cleanup, contact page refactor

## Key Credentials
- Super Admin: forest@imosapp.com / Admin123!

## Mocked Services
- Twilio SMS: All SMS functionality is MOCKED
