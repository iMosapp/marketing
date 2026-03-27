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

### Production Stability Audit + Fixes (Mar 27, 2026) -- LATEST
**Problem:** 86 error reports — 502 Bad Gateway and 60s timeouts crashing production.

**Root Causes Found & Fixed:**
1. **Synchronous pymongo blocking event loop** — `notifications_center.py`, `notifications.py`, `lead_sources.py` all used synchronous `MongoClient` instead of async `motor`. Every call blocked ALL other requests. **FIXED: Fully converted to async motor.**
2. **N+1 queries in activity feed** — Individual `find_one` per event for user/contact names. **FIXED: 2 bulk `$in` queries replace 20+ individual calls.**
3. **Unthrottled catchup task** — `_catchup_overdue_campaign_tasks` ran on every page load (50+ DB queries). **FIXED: Throttled to 1x per 5min/user.**
4. **No response caching** — Task summary and unread count recomputed on every navigation. **FIXED: 30s and 15s TTL caches.**
5. **Missing DB indexes** — Campaign enrollment queries lacked compound indexes. **FIXED: Added.**
6. **No connection pool config** — Default MongoDB pool. **FIXED: maxPoolSize=50, minPoolSize=5, retryWrites/Reads.**

**Performance Results:**
| Endpoint | Before | After |
|---|---|---|
| task/summary | 60s+ timeout | 353ms (119ms cached) |
| activity feed | 60s+ timeout | 227ms |
| unread-count | 60s+ (blocking) | 128ms (cached) |
| 5 concurrent calls | Server crash | 215ms total |

**Testing:** 21/21 backend + frontend tests passed (iteration_248).

### Tracked Media System (Mar 27, 2026)
- Upload-tracked endpoint, branded viewing page, open tracking, composer toggle

### Universal URL Tracking (Mar 27, 2026)
- Auto-wrap in: Campaigns, Training Hub, Templates, Scheduler
- Manual wrap/bulk-wrap endpoints

---

## Prioritized Backlog

### P0
- **Deploy stability fix to production** (stops 502 crashes)
- Run `rewrap-links` on production "Onboarding Videos" campaign

### P1
- Link Analytics Dashboard
- App Store Preparation
- AI-Powered Outreach
- Gamification & Leaderboards

### P2
- Full Twilio, WhatsApp, Stripe, Inventory Module
- Mobile tags sync, file refactoring

## Test Credentials
- Super Admin: `forest@imosapp.com` / `Admin123!`

## Key Files Modified This Session
- `/app/backend/routers/notifications_center.py` — REWRITTEN: async + caching
- `/app/backend/routers/notifications.py` — REWRITTEN: async
- `/app/backend/routers/lead_sources.py` — Converted sync→async
- `/app/backend/routers/tasks.py` — Throttled catchup, cached summary
- `/app/backend/routers/database.py` — Connection pool config
- `/app/backend/server.py` — Bulk activity feed, DB indexes
- `/app/backend/routers/media_tracking.py` — NEW: Tracked media
- `/app/backend/routers/short_urls.py` — wrap/wrap-bulk
- `/app/backend/routers/campaigns.py` — rewrap-links + auto-wrap
- `/app/backend/routers/templates.py` — Auto-wrap
- `/app/backend/scheduler.py` — Auto-wrap helper
- `/app/frontend/app/thread/[id].tsx` — Track Opens toggle
