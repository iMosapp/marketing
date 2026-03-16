# i'M On Social - Product Requirements Document

## Original Problem Statement
Build a Relationship Management System (RMS) / CRM for automotive sales professionals. AI-powered, human-to-human relationship building where every follow-up is deliberate, meaningful, and personal.

## Core Architecture
- **Frontend:** React Native / Expo (web)
- **Backend:** FastAPI (Python)
- **Database:** MongoDB Atlas
- **Integrations:** Resend (email), Twilio (MOCKED), OpenAI (via emergentintegrations), Emergent Object Storage, Pillow, qrcode

---

## CRITICAL RULES

### Image Pipeline
- ALL images → `utils/image_storage.py` → WebP → `/api/images/`
- NEVER add base64 fallbacks. NEVER serve base64 in responses.

### Role System
- DB may have legacy roles: `admin` (= `org_admin`), `manager` (= `store_manager`)
- Backend `permissions.py` maps both legacy and canonical role names
- Frontend `authStore.ts` normalizes roles via `normalizeUser()` on every user load
- NEVER add role checks that only match canonical names — always handle both

### Auth Persistence (iOS PWA)
- 3-layer: AsyncStorage → IndexedDB → Cookie (`imonsocial_session`)
- `/auth/me` returns COMPLETE user data (same as login: permissions, store_slug, org_slug, partner_branding)
- Cookies refreshed on every `/auth/me` call
- Cookie restore retries once on network failure (cold-start resilience)
- Login does case-insensitive, trimmed email lookup

---

## What's Been Implemented (Latest Session - Mar 16, 2026)

### Marketing Site CTA Cleanup (Mar 16, 2026)
- Removed blue "Get a Demo" button from desktop nav bar on ALL pages (homepage + 20 feature pages + app directory)
- Removed "Schedule a Demo" primary CTA from hero sections on ALL pages
- Kept "Schedule a Demo" ONLY in: hamburger mobile menu + black bottom CTA section + footer
- Hero now shows only subtle "Start Free Trial" outline button
- Files changed: `public/index.html`, `generate_pages.py`, `build/appdirectory/index.html`, `src/App.js`
- React homepage: removed CTA section component, simplified hero to single outline button

### Previous Session - Mar 15, 2026

### My Account Page Restructure
- **"My Profile" section** moved to top: Edit Profile & Bio, My Brand Kit, Voice Training
- **"All Tools & Settings"** collapsible section replaces old Quick Actions — no 6-item limit, shows everything
- Removed old grid pill layout, customize mode, and duplication

### Role & Permission Fixes (Critical)
- `permissions.py`: Added `admin` → `org_admin` and `manager` → `store_manager` mapping
- `admin.py` impersonate endpoint: Now returns complete user data (feature_permissions, store_slug, org_slug, onboarding_complete, etc.)
- `authStore.ts`: `normalizeUser()` maps legacy roles at every user-set point
- `admin/users.tsx`: `ROLE_GROUP_MAP` ensures all users appear in the list regardless of role name
- `admin/users/[id].tsx`: `is_active` checks use `!== false` (treats undefined as active)

### Auth & Login Fixes
- Case-insensitive + trimmed email lookup in login, forgot-password, and reset-password
- `/auth/me` now returns complete user data matching login response
- Cookie refresh on every `/auth/me` call
- Retry logic for cold-start network failures

### Onboarding Fix
- `(tabs)/_layout.tsx`: Added `isImpersonating` guard to onboarding redirect

### UI Fixes
- "Manage Permissions" button: purple → orange for visibility
- Account Health header: name + buttons split into two rows (prevents text fragmentation)

### User-Specific Brand Kit & Theming (Mar 14, 2026)
- Backend: `page_theme` field in BrandKit, returned via `/api/card/data/{userId}`
- Frontend: Light/Dark toggle in Brand Kit settings
- Digital Card page dynamically themes based on brand_kit

---

## Key API Endpoints
- `POST /api/auth/login` — Case-insensitive email, trimmed
- `GET /api/auth/me` — Full session restore from cookie (complete user data)
- `POST /api/admin/users/{id}/impersonate` — Returns complete user data with permissions
- `GET /api/card/data/{userId}` — Digital card data with brand_kit theming
- `PUT /api/email/brand-kit/{entity_type}/{entity_id}` — Update brand kit (includes page_theme)

## Key DB Schema
- `users.role` — May be: super_admin, org_admin, admin, store_manager, manager, user
- `users.email_brand_kit` — page_theme, primary_color, secondary_color, accent_color
- `users.feature_permissions` — Merged with role defaults via `merge_permissions()`
- `users.is_active` — May be true, false, or undefined (undefined = active)

---

## Prioritized Backlog

### P1
- Onboarding Task List for new salespeople
- Gamification & Leaderboards
- AI-Powered Outreach (contextual follow-up on "sold" tag)
- Lead Notification System Phase 2 (push notifications)
- Voice Help Assistant Backend
- Extend theming to other public pages (Link Page, Landing Page, Showcase)

### P2
- Full Twilio Integration (currently MOCK)
- WhatsApp Integration
- Training Hub video content
- Inventory Management Module
- Refactor large files (admin.py 3700+ lines, contact/[id].tsx)

## Known Issues
- P2: Mobile tags sync
- P2: React Hydration Error #418

## Test Credentials
- Super Admin: `forest@imosapp.com` / `Admin123!`

## 3rd Party Integrations
- **Resend:** Transactional emails
- **MongoDB Atlas:** Primary database
- **Twilio:** MOCK mode
- **OpenAI:** AI features via emergentintegrations
- **Pillow + ImageOps:** Image processing
- **qrcode:** QR code generation
- **apscheduler:** Backend job scheduling
