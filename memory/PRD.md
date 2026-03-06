# i'M On Social — Product Requirements Document

## Original Problem Statement
Full-stack Relationship Management System (RMS/CRM) for sales teams. Key goals: ease of use, activity tracking, gamification, AI-powered outreach, and multi-channel communication.

## Core Architecture
- **Frontend:** React Native (Expo) web app
- **Backend:** FastAPI (Python)
- **Database:** MongoDB
- **3rd Party:** Resend (email), Twilio (SMS - MOCKED), OpenAI (AI assistant), Emergent Object Storage (images)

## What's Been Implemented

### CDN-Like Image Caching Layer (Mar 2026)
- **In-memory LRU cache** (200MB, configurable via `IMAGE_CACHE_MB` env var): hot images served from RAM in <1ms
- **ETag + 304 Not Modified**: browsers with cached images get zero-body responses (~0.7ms)
- **Immutable cache headers** (`Cache-Control: public, max-age=31536000, immutable`): browser never re-validates
- **Cache warming on upload**: newly uploaded images are pre-cached in RAM
- **Cache stats endpoint**: `GET /api/images/cache-stats` for monitoring
- Performance: cached fetches ~0.9ms, 304 responses ~0.7ms

### Image Pipeline Optimization (Mar 2026)
- All originals auto-compressed to WebP (1200px max, 85% quality) — 94% size reduction
- Thumbnails (200x200) and avatars (80x80) also WebP
- `hires_images` org flag preserves raw uncompressed originals for print-quality accounts
- MMS media moved from base64-in-MongoDB to compressed WebP in Object Storage
- Frontend: expo-image on inbox, thread, contact pages (disk + memory caching)

### Production URL Fix (Mar 2026)
- `PUBLIC_FACING_URL` env var prevents deployment platform from overriding customer-facing URLs
- Eliminated all `window.location.origin` from 13+ files

### Previous Work
- Persistent Login, Dynamic Share Previews, Training Hub V2
- Contact Page Bug Fixes, Home Screen Fixes
- Carrier-agnostic messaging, white-label emails, Reporting
- Inbox refresh fix (useFocusEffect)

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
- Extend expo-image to remaining pages (settings, admin, etc.)
- Auth refactor (bcrypt), Push notifications, Voice Help Assistant
- Full Twilio integration (MOCKED), WhatsApp Integration
- Inventory Management, Code cleanup (~80 files)

## Key Credentials
- Super Admin: forest@imosapp.com / Admin123!

## Deployment Checklist
- `PUBLIC_FACING_URL=https://app.imonsocial.com` in backend env
- `EXPO_PUBLIC_APP_URL=https://app.imonsocial.com` in frontend env
- `RESEND_API_KEY` in production
- `MONGO_URL` points to Atlas
- Optional: `IMAGE_CACHE_MB=200` (default) to tune image cache size

## Mocked Services
- Twilio SMS: All SMS functionality is MOCKED
