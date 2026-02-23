# iMos - Product Requirements Document

## Original Problem Statement
iMos is a business management app for retail/service businesses. Key features include:
- User/team management with invite flows
- Store management
- SMS/messaging capabilities
- Partner agreements
- Review management
- AI assistant (Jessi)
- Lead Sources & Routing system

## Current Architecture
```
/app
├── backend/         # FastAPI + MongoDB
│   ├── routers/     # API endpoints
│   │   ├── lead_sources.py    # Lead routing system
│   │   └── notifications.py   # Lead notification system
│   └── models.py    # Pydantic models
├── frontend/        # React Native/Expo (web export)
│   ├── app/         # Screens (Expo Router)
│   │   ├── admin/lead-sources/  # Lead Sources management
│   │   └── (tabs)/inbox.tsx     # My/Team inbox toggle
│   ├── components/
│   │   └── notifications/       # Lead notification modal
│   ├── hooks/
│   │   └── useNotifications.ts  # Notification polling hook
│   └── store/       # Zustand state
└── marketing/       # Separate Vite React site (Netlify)
```

## Current Branding
- **Slogan:** "Innovation meets old school"
- **Title:** "Innovative Messaging Operating System"
- **Colors:** 
  - "Innovative" - White
  - "Messaging Operating" - Blue (#5B9BD5)
  - "System" - Purple (#9B7BC7)
  - Buttons - Blue (#007AFF)
- **Logo:** Text-only branding (no image logo)

## Deployments
- **App:** `app.imosapp.com` (Emergent)
- **Marketing:** `www.imosapp.com` (Netlify)

## Default Admin Credentials (for fresh deployments)
- **Email:** admin@imosapp.com
- **Password:** iMOs2026!

## What's Been Implemented

### Core Features
- [x] User authentication (login/logout)
- [x] Email-based team invitations
- [x] Store profile management
- [x] Business hours configuration
- [x] Social media links
- [x] Partner agreements system
- [x] Invoice viewing
- [x] AI assistant (Jessi) - with web microphone fix
- [x] WebSafeButton component (mobile web fix)
- [x] Lead Sources & Routing System

### Completed This Session (Feb 22, 2026)

#### Lead Sources & Routing Feature (NEW)
- [x] **Backend API (100% tested)**
  - Full CRUD for lead sources: create, read, update, delete
  - Webhook endpoint for inbound leads: `POST /api/lead-sources/inbound/{source_id}`
  - API key authentication for webhooks
  - Three assignment methods:
    - **Jump Ball**: First team member to respond claims the lead
    - **Round Robin**: Auto-assign to next team member in rotation
    - **Weighted Round Robin**: Auto-assign to member with fewest leads
  - Team inbox queries: `GET /api/lead-sources/team-inbox/{team_id}`
  - User inbox queries: `GET /api/lead-sources/user-inbox/{user_id}`
  - Lead claiming: `POST /api/lead-sources/claim/{conversation_id}`
  - Lead source statistics

- [x] **Lead Assignment Notifications (Backend Complete)**
  - Notifications API: `GET /api/notifications/`, `POST /api/notifications/{id}/action`
  - Automatic notification creation when leads are ingested
  - Jump Ball: Notifies ALL team members
  - Round Robin/Weighted: Notifies assigned user only
  - Action tracking: Call, Text, Email, or Dismiss
  - When user claims via action, other team notifications are auto-dismissed

- [x] **Frontend Pages**
  - Lead Sources list page (`/admin/lead-sources`)
  - New Lead Source form (`/admin/lead-sources/new`)
  - Lead Source detail/edit page (`/admin/lead-sources/[id]`)
  - My Inbox / Team Inbox toggle in Inbox screen
  - Menu item in More tab

#### Previously Completed
- [x] **Broadcast Feature - Loading Bug Fix**
- [x] **Broadcast Feature - Web Button Clickability**
- [x] Fixed "Ask Jessie" microphone not working on web
- [x] Fixed inbox toolbar buttons not working on web
- [x] Fixed "New Message" modal black screen in Email mode
- [x] Fixed thread/message attachment buttons not working on web
- [x] Fixed photo upload dialogs on web
- [x] Fixed voice-to-text in thread not working on web

### Completed This Session (Feb 22, 2026 - Continued)
- [x] **VERIFIED: Team Inbox Light Mode Text Visibility** - Contact names properly display in light/Email mode
- [x] **VERIFIED: Thread Page Theming** - Conversation thread respects saved mode (light/dark) from AsyncStorage
- [x] **VERIFIED: Lead Claim Contact Assignment** - Claimed leads now appear in user's Contacts list (user_id correctly set)
- [x] **VERIFIED: Toast Notification System** - Web-compatible toast for create/delete actions
- [x] **VERIFIED: Delete Lead Source on Web** - Custom modal replaces mobile-only Alert.alert

### Previously Completed (Feb 2026)
- [x] Password reset for forest@imosapp.com
- [x] Full rebranding: mvpline.com → imosapp.com
- [x] Verified mobile button fix working  
- [x] UI Rebranding: iMOs colorful logo (i=red, M=blue, O=yellow, s=green)
- [x] Fixed mobile save buttons on Organizations/Stores/Users modals (WebSafeButton)
- [x] Enhanced User creation with temp password display & copy functionality
- [x] First-time password change prompt for new users with temp passwords
- [x] User creation with org/store assignment
- [x] Delete user functionality in user detail page
- [x] All MVP references updated to iMOs/AI throughout app
- [x] Created Reports section with permission-based views (org/store/user levels)
- [x] Reports: Overview, Messaging, Campaigns, Team, Personal pages

## Prioritized Backlog

### P0 (Critical) - RESOLVED
- [x] **RESOLVED: Admin Panel** - All pages verified working (Organizations, Accounts, Users, Individuals, Quotes, Discount Codes, Partner Agreements, Shared Inboxes, Directory, Pending Users)
- [x] **RESOLVED: Create Lead Source Button** - Was unresponsive on web due to FastAPI 307 redirect using HTTP instead of HTTPS
- [ ] Email delivery (BLOCKED - user needs to verify domain with Resend)
- [ ] SMS functionality (BLOCKED - Twilio toll-free number pending verification)

### P1 (High Priority)
- [ ] **Fix Auth State Persistence** - Login doesn't persist on navigation/refresh (high impact on UX)
- [ ] **Fix Lead Notification Modal** - Modal UI created but blocked by React #418 hydration error on web. Backend API is complete and working.
- [ ] Quote drafts view/edit/delete functionality
- [ ] Complete broadcast sending logic (needs Twilio)
- [ ] Populate Reports section with real data (currently hardcoded)

### P2 (Medium Priority)
- [ ] Store Edit/Delete functionality
- [ ] Searchable Training Manual with screenshots

### P3 (Low Priority/Future)
- [ ] App Store submission prep (icons, splash screens)

## Completed This Session (Feb 23, 2026)

### Inventory Webhook System (NEW - Industry Agnostic)
- [x] **Backend API (100% tested)**
  - Full CRUD for inventory via webhooks
  - Supports ANY industry: Automotive, Real Estate, Retail, Custom
  - Flexible attributes system for industry-specific fields
  - Endpoints:
    - `POST /api/webhooks/inventory/add` - Add/upsert inventory
    - `POST /api/webhooks/inventory/update` - Partial update
    - `POST /api/webhooks/inventory/delete` - Soft/hard delete
    - `POST /api/webhooks/inventory/bulk` - Bulk operations
    - `GET /api/webhooks/inventory` - List with filters
    - `GET /api/webhooks/inventory/{external_id}` - Get single item
    - `GET /api/webhooks/inventory/config/endpoints` - Integration docs
  - Features:
    - External ID support for CRM sync
    - Status tracking (available, sold, pending, reserved, off_market)
    - Sale tracking with timestamps and prices
    - Soft delete (archive) by default
    - Filtering by category, status, price range, tags
    - Full audit trail

### Search Functionality Added (NEW)
- [x] **Organizations page** - Magnifying glass icon opens search bar
- [x] **Stores page** - Magnifying glass icon opens search bar  
- [x] **Users page** - Already had search (verified working)
- [x] Search filters: name, email, city, state, organization name

### Soft Delete with Audit Trail (NEW)
- [x] **Webhook user deletion** now tracks deletion source
  - `deletion_source` field records who deleted (e.g., "Salesforce CRM", "Manual", etc.)
  - `deletion_reason` provides human-readable context
- [x] **Users page** separates Active and Inactive users
  - Inactive users section with visual distinction
  - Shows deletion source (e.g., "Deleted by: Salesforce CRM")
  - Allows managers to see deleted users before permanent removal
- [x] **Reactivate User Feature** (NEW)
  - Backend endpoint: `PUT /api/admin/users/{id}/reactivate`
  - Frontend: "Reactivate User" button on inactive user detail page
  - Clears deletion tracking and restores user to active status

## Inventory Webhooks API Reference

### Endpoints
| Method | Path | Description |
|--------|------|-------------|
| POST | /api/webhooks/inventory/add | Add or upsert inventory item |
| POST | /api/webhooks/inventory/update | Partial update (only provided fields) |
| POST | /api/webhooks/inventory/delete | Soft delete (archive) or hard delete |
| POST | /api/webhooks/inventory/bulk | Multiple operations in one request |
| GET | /api/webhooks/inventory | List items with filters |
| GET | /api/webhooks/inventory/{external_id} | Get single item |
| GET | /api/webhooks/inventory/config/endpoints | Integration documentation |

### Example: Add Vehicle (Automotive)
```json
{
  "external_id": "VIN_1HGCV1F34NA123456",
  "name": "2024 Honda Civic LX",
  "category": "vehicle",
  "status": "available",
  "price": 25995,
  "attributes": {
    "vin": "1HGCV1F34NA123456",
    "year": 2024,
    "make": "Honda",
    "model": "Civic",
    "mileage": 12
  }
}
```

### Example: Add Property (Real Estate)
```json
{
  "external_id": "MLS_12345",
  "name": "4BR Home in South Jordan",
  "category": "property",
  "status": "available",
  "price": 575000,
  "attributes": {
    "address": "123 Main St",
    "bedrooms": 4,
    "bathrooms": 3.5,
    "square_feet": 3200
  }
}
```

### Example: Mark as Sold
```json
{
  "external_id": "VIN_1HGCV1F34NA123456",
  "status": "sold",
  "price": 24500
}
```

## Lead Sources API Reference

### Endpoints
| Method | Path | Description |
|--------|------|-------------|
| GET | /api/lead-sources?store_id=X | List lead sources |
| POST | /api/lead-sources?store_id=X | Create lead source |
| GET | /api/lead-sources/{id} | Get lead source details |
| PATCH | /api/lead-sources/{id} | Update lead source |
| DELETE | /api/lead-sources/{id} | Delete lead source |
| POST | /api/lead-sources/inbound/{id} | Webhook for inbound leads |
| POST | /api/lead-sources/claim/{conv_id}?user_id=X | Claim a lead |
| GET | /api/lead-sources/team-inbox/{team_id} | Get team's leads |
| GET | /api/lead-sources/user-inbox/{user_id} | Get user's leads |
| GET | /api/lead-sources/stats/{id} | Get lead source stats |

### Webhook Authentication
Include `X-API-Key` header with the API key provided when creating the lead source.

### Example Webhook Payload
```json
{
  "name": "John Doe",
  "phone": "+15551234567",
  "email": "john@example.com",
  "notes": "Interested in SUV"
}
```

## Test Credentials
| Email | Password | Role |
|-------|----------|------|
| forest@imosapp.com | Admin123! | super_admin |
| forestward@gmail.com | Admin123! | super_admin |
| matthew@imosapp.com | Matthew2026! | super_admin |
| bridger@imosapp.com | Admin123! | super_admin |
| admin@imosapp.com | iMOs2026! | super_admin (seeded) |

## Completed This Session (Dec 23, 2025)

### Technical Standards Document Created
- [x] Created `/app/memory/STANDARDS.md` with:
  - API route conventions (all routes under `/api/` prefix)
  - Database collection naming standards
  - Frontend naming conventions ("Account" in UI, "stores" in DB)
  - Code organization structure
  - Admin panel route documentation

### Admin Panel Verification & Fix
- [x] **Verified all admin panel pages are working:**
  - Organizations (list, view, create) ✓
  - Accounts/Stores (list, view, create) ✓
  - Users (list, search, view by role groups) ✓
  - Individuals (list, view) ✓
  - Quotes (list with filters) ✓
  - Discount Codes (list, deactivate) ✓
  - Partner Agreements (list, stats) ✓
  - Company Directory (list, filter by role) ✓
  - Pending Users (list pending approvals) ✓
- [x] **Fixed Shared Inboxes page:**
  - Issue: API returned "User not found" due to race condition
  - Fix: Added `user._id` dependency to useEffect and guard in loadData
  - Now shows: Sales Team, Support, B Team inboxes with assigned users

### Testing Results
- Backend API: 94% pass rate (30/32 tests)
- Frontend UI: 95% pass rate (all pages load, minor Playwright click issue)
- Test report: `/app/test_reports/iteration_9.json`

## Technical Notes
- Database field `mvpline_number` preserved for data compatibility
- Internal storage keys (biometrics, calendar) unchanged
- SMS functionality is MOCKED until Twilio integration
- Marketing site updates require manual Netlify deploy
- expo-av is deprecated - will be removed in SDK 54 (migrate to expo-audio/expo-video)
- Passwords are stored in PLAINTEXT (not hashed) - be aware when working with auth
- Lead sources use MongoDB collections: `lead_sources`, `conversations`, `contacts`
- **FastAPI redirect_slashes=False** - Required to prevent HTTP redirects when behind HTTPS proxy
- Route definitions use empty string `""` instead of `"/"` to avoid trailing slash issues

## Integrations
- **Resend:** Email sending (active but blocked - needs domain verification)
- **Netlify:** Marketing site hosting (active)
- **Twilio:** SMS/MMS (credentials configured, pending toll-free verification)
- **EMERGENT_LLM_KEY:** Used for Jessie AI assistant (GPT-5.2 + OpenAI TTS)
