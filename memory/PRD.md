# i'M On Social — Product Requirements Document

## Original Problem Statement
Build a Relationship Management System (RMS) / CRM for automotive sales professionals. The platform has pivoted to a task-driven "Relationship Operating System" where the salesperson's daily workflow is guided by a central task queue and gamified competition.

## Core Architecture
- **Frontend:** React Native / Expo (web)
- **Backend:** FastAPI (Python)
- **Database:** MongoDB Atlas
- **Integrations:** Resend (email), Twilio (MOCKED), OpenAI, Emergent Object Storage, Pillow, Nominatim

---

## CRITICAL: Image Pipeline Rules — DO NOT REVERT

**ALL images in the platform MUST go through the optimized pipeline in `utils/image_storage.py`.**

### How it works:
1. Raw image → compressed to WebP (max 1200px, 85% quality)
2. Thumbnail generated (200x200 WebP, 80% quality)
3. Avatar generated (80x80 WebP, 80% quality)
4. All 3 versions uploaded to Emergent object storage
5. All 3 versions cached in in-memory LRU cache (200MB)
6. Served via `/api/images/` with ETag + 1-year immutable Cache-Control

### The "photo_path" pattern:
- Every document with an image has a `photo_path` field (users, contacts, stores, congrats_cards, customer_feedback)
- If `photo_path` exists → image is migrated → serve via `/api/images/{photo_path}` 
- If `photo_path` does NOT exist → lazy-migrate on first access → set photo_path → redirect
- Showcase API returns direct `/api/images/` WebP paths (not intermediary `/api/showcase/photo/` URLs)

### NEVER DO:
- Store raw base64 as photo_url for new uploads (use `upload_image()` from `utils/image_storage.py`)
- Return base64 blobs in API responses (return `/api/images/` URL paths)
- Set Cache-Control less than 1 year for immutable images
- Decode base64 from MongoDB on every request
- Use duplicate MongoDB query keys like `{"$ne": None, "$ne": ""}` — use `{"$nin": [None, ""]}`

### ALWAYS DO:
- Use `upload_image(data, prefix="type", entity_id="id")` for all new image uploads
- Store `photo_path`, `photo_thumb_path`, `photo_avatar_path` on the document
- Return `/api/images/{path}` URLs to the frontend
- Run `POST /api/images/migrate-all-base64` after deployment to catch stragglers

---

## What's Been Implemented

### Image Performance Overhaul v2 — COMPLETE (Feb 2026)
- ALL showcase photo endpoints serve optimized WebP via 301 redirects
- Showcase API returns direct `/api/images/` paths (zero intermediary hops)
- Profile photo upload uses image pipeline (not raw base64)
- Contact photo upload/update uses image pipeline
- Contact gallery returns URL paths (not MB of base64 JSON)
- Review link clickability fixed (window.location.href vs popup-triggering window.open)
- Batch migration endpoint with backfill step
- Fixed Python dict duplicate-key bug (`$ne` → `$nin`) across showcase.py and admin.py
- 27 images migrated from base64 to WebP, 4 records backfilled

### Operations Manual v3.0 & PDF Export — COMPLETE (Feb 2026)
### Streamlined Client Onboarding — COMPLETE (Feb 2026)
### Task Engine (Touchpoints) — COMPLETE
### Menu Reorganization & Permissions — COMPLETE
### Gamification & Leaderboards — COMPLETE
### Weekly Power Rankings Email — COMPLETE

## Prioritized Backlog

### P1
- Google Places API integration (when user provides key)
- Permission Roles/Templates (pre-defined role sets)
- AI-Powered Outreach (contextual follow-up suggestions)
- Refactor Authentication (bcrypt password hashing)
- Push Notifications, Voice Help Assistant Backend

### P2
- Full Twilio Integration (live), WhatsApp Integration
- Training Hub content, Inventory Management Module
- Code cleanup (~80 files)

## Known Issues
- P1: Production email delivery blocked (user needs to verify RESEND_API_KEY)
- P2: React Hydration Error #418, Mobile tags sync

## Test Credentials
- Super Admin: `forest@imosapp.com` / `Admin123!`
