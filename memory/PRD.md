# i'M On Social - Product Requirements Document

## Original Problem Statement
Build a Relationship Management System (RMS) / CRM for automotive sales professionals. AI-powered, human-to-human relationship building where every follow-up is deliberate, meaningful, and personal.

## Core Architecture
- **Frontend:** React Native / Expo (web)
- **Backend:** FastAPI (Python) with async Motor (MongoDB driver)
- **Database:** MongoDB Atlas
- **Integrations:** Resend (email), Twilio (MOCKED), OpenAI, Emergent Object Storage, apscheduler

---

## What's Been Implemented (This Session)

### Campaign Removal / Archive (Mar 27, 2026) -- LATEST
- **`POST /api/contacts/{user_id}/{contact_id}/campaign-journey/remove`**: Archives enrollment, cancels pending sends, logs contact_event.
- **Trash icon** on Campaign Journey card for one-click removal
- Archived campaigns preserved in DB for history but hidden from active journey
- Contact can be manually re-enrolled anytime

### Browser-Friendly Campaign Tools (Mar 27, 2026)
- **`GET /api/campaigns/{user_id}/list-campaigns`**: Lists all campaigns with IDs (paste in browser)
- **`GET /api/campaigns/{user_id}/{campaign_id}/rewrap-links`**: Browser-friendly URL rewrap

### Production Stability Fix (Mar 27, 2026)
- Converted 3 files from sync pymongo → async motor (was blocking event loop)
- Throttled catchup task, cached task_summary + unread_count
- Bulk activity feed, connection pool config, new DB indexes
- Result: 215ms concurrent vs 60s+ timeouts

### Tracked Media System (Mar 27, 2026)
- Upload-tracked endpoint, branded viewing page, open tracking, composer toggle

### Universal URL Tracking (Mar 27, 2026)
- Auto-wrap in: Campaigns, Training Hub, Templates, Scheduler

---

## Prioritized Backlog

### P0
- Deploy (stability fix + all features)
- Run `rewrap-links` on production campaign

### P1
- Link Analytics Dashboard
- App Store Preparation
- AI-Powered Outreach
- Gamification & Leaderboards

### P2
- Full Twilio, WhatsApp, Stripe, Inventory
- Mobile tags sync, file refactoring

## Test Credentials
- Super Admin: `forest@imosapp.com` / `Admin123!`
