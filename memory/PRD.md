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
│   │   ├── notifications.py   # Lead notification system
│   │   └── demo_requests.py   # Website demo form submissions
│   └── models.py    # Pydantic models
├── frontend/        # React Native/Expo (web export)
│   ├── app/         # Screens (Expo Router)
│   │   ├── admin/lead-sources/  # Lead Sources management
│   │   ├── imos.tsx             # Marketing landing page
│   │   └── (tabs)/inbox.tsx     # My/Team inbox toggle
│   ├── components/
│   │   └── notifications/       # Lead notification modal
│   ├── hooks/
│   │   └── useNotifications.ts  # Notification polling hook
│   ├── public/
│   │   ├── favicon.ico          # iMOS branded favicon
│   │   └── favicon.png          # Apple touch icon
│   └── store/       # Zustand state
```

## Current Branding
- **Tagline:** "I'm Old School. With a modern twist."
- **Colors:** 
  - "I" - Red (#FF3B30)
  - "'" - Green (#34C759)
  - "m" - Blue (#007AFF)
  - "Old" - Yellow (#FFD60A)
  - "School" - Green (#34C759)
  - "With a modern twist." - Blue (#007AFF)
  - Buttons - Blue (#007AFF)
- **Logo:** iMOS colorful text logo
  - "i" - Red
  - "M" - Blue  
  - "O" - Yellow
  - "S" - Green
  - Glowing/neon effect on dark background
- **Favicon:** Red "i" + Blue "M" on black background
- **Logo URL:** `https://customer-assets.emergentagent.com/job_35683d39-9c8e-4a2d-a3f7-89b34db8b170/artifacts/g39ale0a_ChatGPT%20Image%20Feb%2023%2C%202026%2C%2004_06_33%20PM.png`
- **Local Logo Files:**
  - `/app/frontend/assets/images/imos-logo-white-v3.png`
  - `/app/frontend/dist/marketing-preview/imos-logo.png`

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

### P1 (High Priority) - SEVERAL FIXED
- [x] **FIXED: Shared Inboxes Page** - Was showing "User not found" error, now loads correctly with all inbox data
- [x] **FIXED: Auth State Persistence** - Login now persists on navigation/refresh via AsyncStorage
- [x] **FIXED: Root URL Black Screen** - Added HTML meta redirect to `/auth/login` as workaround for Expo web hydration issue
- [x] **FIXED: Settings Pages Loading** - Templates, Tags, Calendar, Integrations all fixed (race condition)
- [x] **FIXED: Quote Management** - View, edit, delete, resend functionality now working with web-compatible alerts
- [x] **FIXED: Partner Agreements Management** - Admin detail page with edit, delete, send functionality
- [ ] **React Hydration Error #418** - Root cause still exists in Expo web, but workaround in place
- [ ] Complete broadcast sending logic (needs Twilio)
- [ ] Populate Reports section with real data (currently hardcoded)

### P2 (Medium Priority)
- [ ] Store Edit/Delete functionality
- [x] **DONE: Training Hub** - Searchable tutorials with voice help

### P3 (Low Priority/Future)
- [ ] App Store submission prep (icons, splash screens)

## Completed This Session (Continued - Feb 24, 2026)

### Customizable UI & Training Hub (COMPLETED - Feb 24, 2026)
- [x] **Customize Menu Page** (`frontend/app/customize-menu.tsx`)
  - Toggle OFF features you don't use to reduce overwhelm
  - "Show All" / "Hide All" quick actions
  - Organized by category
  - Settings saved to AsyncStorage
- [x] **Training Hub** (`frontend/app/training-hub.tsx`)
  - Voice Help: Ask questions by voice or text, get AI answers
  - Searchable training topics organized by category
  - Topics: Getting Started, Messaging, AI Features, Sales Tools, Campaigns, Team
- [x] **Updated More Page** with "Customize" button and Training Hub

### Voice Training for AI (COMPLETED - Feb 24, 2026)
- [x] **Created Voice Training page** (`frontend/app/voice-training.tsx`)
  - Modern, voice-first experience for training your AI
  - 4-step guided flow: Intro, Hobbies, Family, Expertise
  - Just tap and talk naturally - no forms to fill
  - Examples provided to help get started
  - AI extracts structured data (bio, hobbies, interests, specialties, etc.)
  - "See Results" page shows what AI learned about you
  - One-tap "Save to My AI Profile" button
- [x] **Backend endpoint** (`/api/jessie/extract-profile`)
  - Uses GPT-5.2 to parse natural speech into profile fields
  - Context-aware extraction based on which question was answered
- [x] **Updated My Account page** with Voice Training quick action
- **Files Created:**
  - `frontend/app/voice-training.tsx`
- **Files Modified:**
  - `backend/routers/jessie.py` - Added extract-profile endpoint
  - `backend/services/jessie_service.py` - Added extract_profile_info function
  - `frontend/app/my-account.tsx` - Added Voice Training card

### Contacts Page & Thread Bugs Fixed (COMPLETED - Feb 24, 2026)
- [x] **Fixed white screen issue** - Thread page now uses dark mode for both SMS and Email
- [x] **Added clear visual mode indicator** - New banner below header:
  - **Blue banner** with chat icon for SMS Mode
  - **Green banner** with mail icon for Email Mode
  - One-tap "Switch to SMS/Email" button to change modes
- [x] **Fixed phone icon** - Now opens tel: link to trigger phone dialer
- [x] **Fixed chat icon** - Now navigates directly to thread in SMS mode
- [x] **Fixed email icon** - Now navigates directly to thread in Email mode
- [x] **Replaced Alert.alert** with web-compatible alerts in contacts page
- **Files Modified:** 
  - `frontend/app/(tabs)/contacts.tsx` - Fixed action buttons
  - `frontend/app/thread/[id].tsx` - Added mode banner, always dark mode

### My Account Page - Clickable Profile (COMPLETED - Feb 24, 2026)
- [x] **Profile card is now clickable** on the More page
  - Shows pencil/edit badge on avatar to indicate it's tappable
  - Shows chevron arrow for navigation hint
  - Displays user photo if available, otherwise initials
- [x] **New "My Account" page** (`frontend/app/my-account.tsx`)
  - Large profile photo with camera button overlay
  - One-tap buttons for: Change Photo, My Digital Card, Train Jessie AI, AI Persona
  - Upgrade & Rewards section: Upgrade Plan, Refer a Friend
  - Quick access to Security, Notifications, Brand Kit, Calendar, Integrations
  - Account info showing phone, organization, store
- [x] **Profile photo upload** works with both camera and library picker
- [x] **Sign Out button** moved to bottom of More page (cleaner profile card)

### Team Tab Notification Badge (COMPLETED - Feb 24, 2026)
- [x] **Removed top-right floating notification button** (per user feedback)
  - User found it distracting and covering UI elements
- [x] **Added unread badge to Team tab** in bottom navigation
  - Shows red badge with unread count when there are new team messages
  - Badge clears when user taps on Team tab
  - Polls for new messages every 10 seconds
  - **Files Modified:** `frontend/app/(tabs)/_layout.tsx`
  - **Files Removed (from layout):** `QuickAlertButton` component no longer rendered

### Quotes & Partner Agreements Management (COMPLETED - Feb 24, 2026)
- [x] **Quote Management - Full CRUD Operations**
  - **Quote Detail Page** (`frontend/app/admin/quote/[id].tsx`)
    - Back button to navigate to quotes list
    - Edit button for updating notes
    - Delete button (only for draft quotes)
    - Resend button to send quote to customer
  - **Web-Compatible Alerts** - Fixed silent failures on web
    - Uses `showAlert`, `showSimpleAlert`, `showConfirm` from `services/alert.ts`
    - Uses `window.confirm/alert` for web, `Alert.alert` for native
  - **Backend Endpoints Added:**
    - `PATCH /api/subscriptions/quotes/{id}` - Update quote (notes, status)
    - `POST /api/subscriptions/quotes/{id}/send` - Send/resend quote to customer
  - **Test Report:** `/app/test_reports/iteration_13.json`

- [x] **Partner Agreement Management - New Admin Detail Page**
  - **New Page Created:** `frontend/app/admin/partner-agreement/[id].tsx`
    - Full agreement details view
    - Back button for navigation
    - Edit button to update partner info
    - Copy Agreement Link button
    - Send to Partner button
    - Delete Agreement button (only for non-signed agreements)
  - **Backend Endpoints Added:**
    - `DELETE /api/partners/agreements/{id}` - Delete non-signed agreements
    - `POST /api/partners/agreements/{id}/send` - Send agreement link to partner
  - **Fixed API to return** `created_at` and `sent_at` fields in agreement details
  - **Updated List Page** (`frontend/app/admin/partner-agreements.tsx`)
    - Agreements now link to admin detail page instead of signing page
    - Uses web-compatible alerts

## Completed This Session (Feb 24, 2026)

### Critical Bug Fixes (COMPLETED - Feb 24, 2026)
- [x] **FIXED: Signup Button Not Working on Web** (P0 - Showstopper)
  - **Root Cause:** React Native's `Alert.alert()` doesn't work on web browsers - calls silently fail
  - **Fix:** Added Platform.OS check and use `window.alert()` for web, `Alert.alert()` for native
  - **Files Modified:** `frontend/app/auth/signup.tsx`
  - **Verified:** 100% test pass rate - signup creates user, sends welcome email, redirects to onboarding
  - **Test Report:** `/app/test_reports/iteration_11.json`

### Profile Photos/Avatars Feature (COMPLETED - Feb 24, 2026)
- [x] **Profile photos now follow users/contacts everywhere in the app**
  - Avatars show uploaded photos when available, fallback to color-coded initials
  - **Updated Components:**
    - `frontend/app/(tabs)/inbox.tsx` - Conversation list shows contact photos
    - `frontend/app/(tabs)/contacts.tsx` - Already supported photos
    - `frontend/app/thread/[id].tsx` - Thread header shows contact avatar
    - `frontend/app/admin/users.tsx` - Admin user list shows photos
    - `frontend/app/admin/leaderboard.tsx` - Leaderboard shows user photos
    - `frontend/app/my-rankings.tsx` - Rankings shows user photos
  - **New Component:** `frontend/components/Avatar.tsx` - Reusable avatar with photo/initials support
  - **Backend APIs updated:** All relevant endpoints now return photo fields
  - **Verified:** 100% test pass rate (9/9 tests)
  - **Test Report:** `/app/test_reports/iteration_12.json`

- [x] **Congrats Card photos automatically populate contact avatars**
  - When creating a congrats card with a photo, the photo is saved to the contact's profile
  - Only updates if contact doesn't already have a photo
  - Shows success message when photo is updated
  - **Files Modified:** `backend/routers/congrats_cards.py`, `frontend/app/thread/[id].tsx`

- [x] **iMOs logo branding throughout the app**
  - Replaced "iMOs" text with the actual logo image across the app
  - **Updated locations:**
    - Inbox filter pill (third pill now shows logo)
    - Signup page subtitle ("Start your journey with [logo]")
    - More page profile section (phone number with logo)
    - More page version text ("[logo] v1.0.0")
    - Onboarding welcome page ("Welcome to [logo]!")
    - Onboarding AI intro slide ("The Magic Behind [logo]")
  - **Files Modified:** `inbox.tsx`, `signup.tsx`, `more.tsx`, `onboarding/index.tsx`

### Team Chat Feature (COMPLETED - Feb 24, 2026)
- [x] **Internal Team Chat System (Slack-like)**
  - New "Team" tab in bottom navigation
  - **Channel Types:**
    - Organization-wide channels (all members across locations)
    - Store channels (per-location teams)
    - Custom groups (hand-picked members like "All GMs")
    - Direct Messages (1-on-1 private chats)
  - **Features:**
    - @mentions with notifications
    - Voice-to-text input for quick messages
    - Broadcast messaging capability
    - Unread message counts
    - Real-time polling for new messages
  - **Use Case:** "Hey @Jimmy, you have a customer out front" → push notification to team
  - **Files Created:**
    - `backend/routers/team_chat.py` - Full API for channels, messages, members
    - `frontend/app/(tabs)/team.tsx` - Team Chat UI
  - **Database Collections:** `team_channels`, `team_messages`, `team_read_status`

- [x] **Quick Alert Button (Floating Panic Button)**
  - Red floating button with lightning bolt appears on all screens
  - Pulsing animation to draw attention
  - **Preset Alerts (one-tap send):**
    - "Customer waiting at front"
    - "Need backup on sales floor"
    - "Manager to register please"
    - "Team huddle in 5 minutes"
    - "Phone call holding - who can take?"
    - "Customer arrived for pickup"
  - Custom message option for anything else
  - Broadcasts to entire team with notification
  - **Files Created:** `frontend/components/QuickAlertButton.tsx`

### UI/UX Fixes (COMPLETED - Feb 24, 2026)
- [x] **Keypad Search Button Fix** - Search and History buttons now work correctly on web
  - WebIconButton component renders native HTML `<button>` on web for proper click handling
  - Fixed number display overlapping with header icons by adding proper spacing
- [x] **Refresh App Button on Login** - Added "Refresh App" button at bottom of login screen for web users
  - Calls `window.location.reload()` to force refresh the app
- [x] **Sign Out Button Moved to Profile Card** - Logout button moved from bottom of More page to profile card header
  - Red logout icon on right side of profile card for easy access
  - Added "Are you sure you want to log out?" confirmation dialog for both web and mobile
  - Prevents accidental logout when scrolling

## Completed Previous Session (Feb 23, 2026)

### Logo Update (COMPLETED - Feb 23, 2026)
- [x] **Login Page** - Updated to use new iMOS colorful logo (red i, blue M, yellow O, green S)
- [x] **Landing Page (imos.tsx)** - Navigation bar updated with new logo
- [x] **Landing Page Footer** - Updated with new logo
- [x] **Marketing Preview** - Logo file updated in dist folder
- [x] **Assets** - New logo saved to `/app/frontend/assets/images/imos-logo-white-v3.png`

### Marketing Landing Page Overhaul (COMPLETED - Feb 23, 2026)
- [x] **New Tagline** - "I'm Old School" with colorful letters + "With a modern twist." subtitle in blue
- [x] **Hero Section** - Left-aligned text with iPhone mockup showing text conversation
- [x] **Phone Mockup** - Displays realistic SMS conversation about vehicle anniversary follow-up
- [x] **Navigation** - Features, How It Works, Pricing, Testimonials, FAQ, Sign In, Get Started
- [x] **All nav links functional** - Scroll to sections or navigate to auth pages
- [x] **Pricing Section** - Starter ($49), Professional ($79), Enterprise (Custom)
- [x] **FAQ Section** - 5 common questions with answers
- [x] **Demo Request Form** - "Watch Demo" opens modal form that creates leads in database
- [x] **Header 95% transparent** - With backdrop blur effect
- [x] **Favicon** - New iMOS branded favicon (red i, blue M)
- [x] **Meta tags** - Updated title, description, Open Graph tags

### Demo Request System (NEW - Feb 23, 2026)
- [x] Created `/app/backend/routers/demo_requests.py`
- [x] POST `/api/demo-requests` - Creates contact with tags `demo-request`, `website-lead`
- [x] GET `/api/demo-requests` - Lists all demo requests
- [x] Modal form on landing page with name, email, phone, company, message fields
- [x] Success confirmation message after submission

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

### Settings Pages Race Condition Fixes
- [x] **Fixed SMS Templates page (`/settings/templates`):**
  - Issue: Page stuck on loading spinner
  - Fix: Added `user?._id` dependency to useEffect
- [x] **Fixed Contact Tags page (`/settings/tags`):**
  - Issue: Page stuck on loading spinner  
  - Fix: Added `user?._id` dependency to useEffect
- [x] **Fixed Calendar Settings page (`/settings/calendar`):**
  - Issue: Page stuck on loading spinner
  - Fix: Added `user?._id` dependency to useEffect
- [x] **Fixed Integrations page (`/settings/integrations`):**
  - Issue: Page stuck on loading spinner
  - Fix: Added `user?.store_id` and `user?._id` dependencies to useEffect

### Auth & Navigation Fixes
- [x] **Fixed Root URL Black Screen:**
  - Issue: `/` showed black screen due to Expo web hydration error
  - Fix: Added meta refresh and JS redirect in `public/index.html` to `/auth/login`
- [x] **Auth State Persistence Verified:**
  - AsyncStorage already stores auth data
  - loadAuth() is called on app mount in `_layout.tsx`
  - Tested: Login → Reload → User stays logged in ✅
- [x] **Added Protected Route Guards:**
  - Added auth check to `(tabs)/_layout.tsx`
  - Redirects unauthenticated users to login

### Testing Results
- Backend API: 94% pass rate (30/32 tests)
- Frontend UI: 95%+ pass rate (all pages now loading correctly)
- Test reports: `/app/test_reports/iteration_9.json`, `/app/test_reports/iteration_10.json`

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
