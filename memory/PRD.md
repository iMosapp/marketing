# i'M On Social — Product Requirements Document

## Original Problem Statement
Full-stack Relationship Management System (RMS/CRM) for sales teams. Key goals: ease of use, activity tracking, gamification, AI-powered outreach, and multi-channel communication.

## Core Architecture
- **Frontend:** React Native (Expo) web app
- **Backend:** FastAPI (Python)
- **Database:** MongoDB
- **3rd Party:** Resend (email), Twilio (SMS - MOCKED), OpenAI (AI assistant), Emergent Object Storage (images)

## What's Been Implemented

### Image Pipeline Optimization (Mar 2026)
**Backend:**
- All uploaded images auto-compressed to WebP format, capped at 1200px wide (85% quality)
- Achieved 94% size reduction (94KB JPEG → 6KB WebP in testing)
- All thumbnails (200x200) and avatars (80x80) now WebP
- Immutable cache headers (`Cache-Control: public, max-age=31536000, immutable`) — 1 year cache since UUID-based paths never change
- `hires_images` org flag: when enabled, also stores the raw uncompressed original for accounts that need high-res prints (calendars, etc.)
- MMS media moved from base64-in-MongoDB to Emergent Object Storage (compressed WebP)

**Frontend:**
- Switched from React Native's `<Image>` to `expo-image` (`Image from 'expo-image'`) on key pages: inbox, thread, contact detail
- expo-image provides: disk caching, memory caching, smooth transitions, progressive loading
- Updated all `resizeMode` props to `contentFit` for expo-image compatibility
- Created `OptimizedImage` reusable component at `/app/frontend/components/OptimizedImage.tsx`

### Production URL Fix (Mar 2026)
- Added `PUBLIC_FACING_URL` env var to prevent deployment platform from overriding customer-facing URLs
- Eliminated all `window.location.origin` from customer-facing URL construction

### Inbox Refresh Fix (Mar 2026)
- `useFocusEffect` added for reliable conversation loading

### Previous Work
- Persistent Login, Dynamic Share Previews, Training Hub V2
- Contact Page Bug Fixes, Home Screen Fixes
- Carrier-agnostic messaging, white-label emails, Reporting

## Pending Issues
- P0: Production email delivery — BLOCKED on user verifying `RESEND_API_KEY`
- P2: React Hydration Error #418
- P2: Mobile app `tags` data sync

## Upcoming Tasks
1. (P0) Gamification & Leaderboards
2. (P1) Automated Welcome Emails
3. (P1) Quoting System
4. (P1) AI-Powered Outreach

## Future/Backlog
- Auth refactor (bcrypt), Push notifications, Voice Help Assistant
- Full Twilio integration (MOCKED), WhatsApp Integration
- Inventory Management, Code cleanup (~80 files)
- Extend expo-image to remaining pages (settings, admin, etc.)

## Key Credentials
- Super Admin: forest@imosapp.com / Admin123!

## Deployment Checklist
- `PUBLIC_FACING_URL=https://app.imonsocial.com` in backend env
- `EXPO_PUBLIC_APP_URL=https://app.imonsocial.com` in frontend env
- `RESEND_API_KEY` in production
- `MONGO_URL` points to Atlas

## Mocked Services
- Twilio SMS: All SMS functionality is MOCKED
