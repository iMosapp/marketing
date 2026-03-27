# i'M On Social - Product Requirements Document

## Original Problem Statement
Build a Relationship Management System (RMS) / CRM for automotive sales professionals. AI-powered, human-to-human relationship building where every follow-up is deliberate, meaningful, and personal.

## Core Architecture
- **Frontend:** React Native / Expo (web)
- **Backend:** FastAPI (Python) with async Motor (MongoDB driver)
- **Database:** MongoDB Atlas
- **Integrations:** Resend (email), Twilio (MOCKED), OpenAI, Emergent Object Storage, apscheduler

---

## What's Been Implemented

### Profile Photo & Bio Fix (Feb 2026) -- LATEST
- Fixed duplicate PATCH `/api/users/{user_id}` route in `server.py` that was NOT clearing `photo_path`/`photo_avatar_path` when `photo_url` was updated
- Root cause: `resolve_user_photo()` prioritizes `photo_path` over `photo_url`, so stale cached paths caused digital cards to show old photos
- Also improved `refreshUserData` in `my-account.tsx` to sync auth store after fetch

### Campaign Removal / Archive (Mar 27, 2026)
- Trash icon on Campaign Journey card for one-click removal
- Archived campaigns preserved in DB for history

### Production Stability Fix (Mar 27, 2026)
- Converted 3 files from sync pymongo to async motor
- Throttled catchup task, cached task_summary + unread_count
- Bulk activity feed, connection pool config, new DB indexes

### Tracked Media System (Mar 27, 2026)
- Upload-tracked endpoint, branded viewing page, open tracking, composer toggle

### Universal URL Tracking (Mar 27, 2026)
- Auto-wrap in: Campaigns, Training Hub, Templates, Scheduler

---

## Prioritized Backlog

### P0
- Deploy latest fixes (profile photo + stability)

### P1
- App Store Preparation (`eas.json`, `app.json`)
- Push Notifications (mobile alerts for leads/messages)
- AI-Powered Outreach (contextual follow-ups for `sold` tags)
- Gamification & Leaderboards
- Link Analytics Dashboard

### P2
- Full Twilio / WhatsApp / Stripe integration
- Inventory Management Module
- Mobile tags sync issue
- Refactor `contact/[id].tsx` (6000+ lines) and `admin.py` monolith

## Test Credentials
- Super Admin: `forest@imosapp.com` / `Admin123!`
