# MVPLine - Digital Business Card Enhancement

## Session: February 21, 2026
- Migrated project from user's local folder to Emergent workspace
- Configured Expo web export for static serving (expo export --platform web)
- Seeded test database with admin users
- App is now running at preview URL

## Things To Remind User In Future Sessions
- **Voice Cloning for Jessi**: User wants to explore ElevenLabs voice cloning to give Jessi a custom voice. They will provide an audio sample (1-5 minutes of clear speech) to create a cloned voice. This would replace the current OpenAI TTS "nova" voice.

## Original Problem Statement
Enhance the "Digital Business Card" feature within the MVPLine application with:
1. Bug fixes for fun facts, social links, and voicemail recorder
2. QR code generating a link to a publicly accessible, mobile-formatted landing page
3. Public landing page ("visual storyboard") with profile, social links, reviews, and refer-a-friend
4. Customer review system with photo uploads and approval workflow

## Core Requirements
- **Bug Fixes:** Fun facts not saving, voice recorder not starting, social links not storing
- **QR Code:** Generate link to public `/p/{userId}` landing page
- **Public Landing Page:** Mobile-friendly profile display with social links, reviews, refer-a-friend
- **Review System:** Submit reviews with photo uploads, approval workflow before display

## User Personas
- **Sales Professionals:** Use digital business cards to share contact info
- **Customers:** Leave reviews and referrals via public landing page

## Architecture
```
/app
├── backend/
│   ├── routers/
│   │   ├── profile.py        # Profile CRUD
│   │   ├── public_landing.py # Public landing page API
│   │   ├── public_review.py  # Review submission API
│   │   ├── voice.py          # Voicemail & voice-to-text
│   │   ├── onboarding_settings.py # Onboarding branding/messages
│   │   ├── team_invite.py    # Team invite link management
│   │   ├── jessie.py         # NEW - Jessie AI Assistant API
│   │   └── rbac.py           # NEW - Role-Based Access Control module
│   ├── services/
│   │   └── jessie_service.py # NEW - Jessie AI service (GPT-5.2 + TTS)
│   └── server.py
└── frontend/
    ├── app/
    │   ├── jessie.tsx         # NEW - Jessie AI chat page
    │   ├── admin/
    │   │   └── onboarding-settings.tsx  # Admin branding center
    │   ├── join/
    │   │   └── [code].tsx              # Team member signup page
    │   ├── settings/
    │   │   ├── my-profile.tsx  # Profile editor
    │   │   └── persona.tsx     # AI persona settings
    │   ├── card/
    │   │   └── [userId].tsx    # Digital card display
    │   └── p/
    │       └── [userId].tsx    # Public landing page
    └── components/
        ├── VoicemailRecorder.tsx
        └── VoiceInput.tsx
```

## What's Been Implemented

### February 21, 2026 (Session 8 - Current)

#### Feature: iMOSapp.com Landing Page Logo - COMPLETE
- Generated AI-human handshake logo using image generation tool
- Logo features robotic AI hand with circuit patterns shaking a human hand
- Integrated into landing page hero section at `/app/frontend/app/imos.tsx`
- Added `Image` component with proper styling for both web and mobile
- Logo URL: `https://static.prod-images.emergentagent.com/jobs/aca65436-af09-4c87-a476-6757d45879e3/images/8f2bbe5337ce1d58d812afb189af3569f807308ff8c36bf5d0c051e6562b1a0c.png`
- Positioned prominently above the "Innovation Meets Old School" badge
- Responsive sizing: 280px on web, 200px on mobile

### February 20, 2026 (Session 7)

#### Bug Fix: Keyboard Covering Congrats Card Input - COMPLETE
- Fixed keyboard overlay issue on Congrats Card modal in thread view
- Restructured modal with proper KeyboardAvoidingView implementation:
  - Uses `justifyContent: 'flex-end'` for bottom-sheet positioning
  - Separated backdrop from modal content
  - Added `maxHeight: '80%'` to leave room for keyboard
  - Added `keyboardShouldPersistTaps='handled'` for proper input handling
  - All interactive elements have data-testid attributes
- Also fixed thread message loading issue by adding `user?._id` to useEffect dependencies
- File modified: `/app/frontend/app/thread/[id].tsx`

#### Enhancement: Premium Haptic Feedback - COMPLETE
- Added haptic feedback throughout the app for a premium mobile experience:
  
  **Congrats Card Creation** (`thread/[id].tsx`):
  - Medium impact when tapping "Create Card & Send Link"
  - Success notification when card is created
  - Error notification if creation fails
  
  **Message Sending** (`thread/[id].tsx`):
  - Light impact when sending messages
  
  **Jessi AI Assistant** (`jessie.tsx`):
  - Light impact when sending text message
  - Success notification when Jessi responds
  - Error notification on failures
  
  **Tasks** (`tasks/index.tsx`):
  - Success notification when completing a task
  - Light impact when toggling task status
  - Warning notification before delete confirmation
  - Error notification on failures
  
  **Dialer** (`dialer.tsx`):
  - Heavy impact when initiating a call
  - Light impact when selecting a contact
  
  **Contacts** (`contacts.tsx`):
  - Light impact when starting a conversation
  - Light impact on pull-to-refresh
  
  **Login** (`auth/login.tsx`):
  - Light impact on login button press
  - Success notification on successful login
  - Warning notification for validation errors
  - Error notification on login failures

  **Pull-to-Refresh** (all list screens):
  - Light impact on refresh trigger
  - Added to: Inbox, Contacts, Tasks, Directory, Users, Leaderboard

- Created reusable haptics utility at `/app/frontend/utils/haptics.ts`
- Uses `expo-haptics` library (already installed)
- Note: Haptic feedback is native-only - works on iOS/Android devices only

#### Bug Fix: SOP Filter Pills Height Standardization - COMPLETE
- Changed pills from variable `paddingVertical` to fixed `height: 36`
- Switched from FlatList to ScrollView for more reliable horizontal rendering
- Added proper centering and font styling

#### P1: RBAC Permissions Verification - COMPLETE
- Verified backend RBAC implementation in `/app/backend/routers/rbac.py`
- Role hierarchy: super_admin > org_admin > store_manager > user
- store_manager can access own data and data within assigned stores
- All admin APIs properly enforce backend role checks

#### P2: My Agreement & My Invoices Pages - COMPLETE
- **Backend:** Created `/app/backend/routers/invoices.py` with full CRUD:
  - `GET /api/invoices/user/{user_id}` - Get user's invoices
  - `GET /api/invoices/store/{store_id}` - Get store invoices
  - `GET /api/invoices/organization/{org_id}` - Get org invoices
  - `GET /api/invoices/{invoice_id}` - Get invoice detail
  - `POST /api/invoices/` - Create invoice (admin only)
  - `PATCH /api/invoices/{invoice_id}/status` - Update status (admin only)
- **Frontend:** Updated `/app/frontend/app/admin/my-invoices.tsx`:
  - Now calls live backend API instead of returning empty mock
  - Added haptic feedback on refresh and invoice click
  - Added proper status colors and date formatting
  - Added "Request Support" button with email link to billing@mvpline.com
- **Frontend:** Updated `/app/frontend/app/admin/my-agreement.tsx`:
  - Added haptic feedback on refresh, back, and PDF open actions
  - Added "Request Support" button with email link to support@mvpline.com
- Partner agreement endpoint was already implemented at `/api/partners/user/{user_id}/agreement`

#### Bug Fix: SOP Filter Pills Padding - COMPLETE
- Added `flexDirection: 'row'` and `alignItems: 'center'` to filterContainer
- Added `flexDirection: 'row'` to filterChip for consistent rendering
- Increased paddingTop to 8px for better spacing

#### SOP Workflow Navigation - COMPLETE
- Added "Continue" button after completing an SOP that takes user to the next incomplete SOP
- Added `loadNextSOP()` function to find the next uncompleted training
- Button shows "Continue" with arrow icon when next SOP exists, "Done" when all complete
- Added haptic feedback for step navigation

#### Training Progress Widget - COMPLETE
- Added new admin dashboard widget showing team training progress
- **Backend:** Created `GET /api/sop/team/progress` endpoint in `/app/backend/routers/sop.py`
  - Returns summary stats (total SOPs, fully trained, in progress, not started)
  - Returns individual team member progress with completion percentages
  - Role-scoped: super_admin sees all, org_admin sees their org, store_manager sees their store
- **Frontend:** Added widget to admin dashboard under TOOLS section
  - Shows completion rate badge
  - Summary stats in a 3-column layout
  - Top 3 team members with progress bars
  - "+X more team members" link
  - Tapping widget navigates to Training & SOPs page

### February 20, 2026 (Session 6)

#### Feature: Internal SOP System - COMPLETE
- Comprehensive Standard Operating Procedure system for MVPLine employees
- Backend: `/app/backend/routers/sop.py` with RBAC protection
- Frontend: `/app/frontend/app/admin/sop/` (index.tsx, [id].tsx)
- Database seeded with 13 SOPs across 8 categories:
  - Getting Started (Welcome, AI Persona)
  - Daily Operations (Inbox, Contacts)
  - Customer Communication (Messaging, Congrats Cards)
  - Tools & Features (Campaigns, Tasks)
  - Admin Tasks (Admin Panel, Approving Users)
  - Best Practices (Response Time, Customer Relationships)
  - Troubleshooting (Common Issues)
- Features:
  - Progress tracking per user
  - Required reading assignments
  - Step-by-step navigation with tips/warnings
  - Deep links to relevant app screens
  - Search and category filtering
- Access: INTERNAL section of Admin Panel (super_admin only)

#### Feature: Jessi AI Assistant - COMPLETE
- Renamed from "Jessie" to "Jessi"
- Voice-enabled AI assistant for MVPLine help
- Uses GPT-5.2 for text generation via emergentintegrations
- Uses OpenAI TTS (nova voice - energetic, 1.15x speed) for voice responses
- Voice Activity Detection (VAD) - auto-sends after 1.2s silence
- Text input option added back
- Scrollable response text
- Conversation memory with session management stored in MongoDB
- API Endpoints:
  - `POST /api/jessie/chat` - Send text message, optional voice response
  - `POST /api/jessie/voice-chat` - Voice input with voice response
  - `GET /api/jessie/history/{user_id}` - Get chat history
  - `DELETE /api/jessie/history/{user_id}` - Clear chat history
  - `POST /api/jessie/tts` - Text-to-speech standalone
- Frontend: `/app/frontend/app/jessie.tsx` with chat UI, voice recording, audio playback
- Menu integration: "Ask Jessi" in More menu

#### Feature: Backend RBAC Enforcement - COMPLETE (CRITICAL SECURITY)
- Created `/app/backend/routers/rbac.py` security module
- All admin endpoints now enforce role-based access control
- Endpoints secured with RBAC:
  - `GET /api/admin/organizations` - scoped by role
  - `GET /api/admin/stores` - scoped by role
  - `GET /api/admin/users` - scoped by role
  - `POST/PUT/DELETE` operations - restricted by role
- Uses `X-User-ID` header for authentication
- Role hierarchy: super_admin > org_admin > store_manager > user
- Tested and verified:
  - Manager sees only 1 organization (their own)
  - Manager sees only 1 store (their assigned)
  - Super admin sees all 3 organizations and 6 stores
  - Regular users cannot access admin data

#### UI/UX Improvements - COMPLETE
- Role-based login redirect (admins → More tab, users → Inbox)
- Active/Inactive user separation in Users list with visual divider
- Active/Inactive store separation in Stores list with visual divider

### February 20, 2026 (Session 5)

#### Feature: Role-Based Access Control (RBAC) System - COMPLETE
- Created centralized permissions utility (`/app/frontend/utils/permissions.ts`)
- Role hierarchy: super_admin > org_admin > store_manager > user
- Admin panel now conditionally shows sections based on user role:

**Store Manager (store_manager) sees:**
- **MY STORES section**: My Stores, My Team (only their assigned stores)
- **DATA section**: All data scoped to their stores only
- **TOOLS section**:
  - My Invoices (view their invoices/receipts)
  - Leaderboards (their team only)
  - Activity (their team only)
  - Training Preview
  - Onboarding Settings
- **Does NOT see**: Organizations, Individuals, Revenue Forecast, Billing, Pending Users, INTERNAL section

**Org Admin (org_admin) sees:**
- **CUSTOMERS section**: Stores, Users (within their org only)
- **DATA section**: All data within their organization
- **TOOLS section**: Pending Users, Leaderboards, Activity, Training Preview
- **Does NOT see**: Organizations, Individuals, Revenue Forecast, Billing, INTERNAL section

**Super Admin (super_admin) sees:**
- Everything including INTERNAL section

#### Bug Fix: Keyboard Covering Text Inputs - COMPLETE
- Added `KeyboardAvoidingView` to multiple pages with text inputs:
  - `/settings/congrats-template.tsx` - Congrats Card Style settings
  - `/settings/my-profile.tsx` - Profile editor
  - `/admin/onboarding-settings.tsx` - Admin onboarding settings
  - `/settings/templates.tsx` - Message templates modal
- Added `keyboardShouldPersistTaps="handled"` and extra bottom padding to ScrollViews
- Keyboard now stays below input fields on mobile

#### Feature: Invite Team via SMS with Analytics - COMPLETE
- **Backend:** `/app/backend/routers/onboarding_settings.py`
  - GET/PUT `/api/onboarding-settings/global` - Platform-wide settings
  - GET/PUT `/api/onboarding-settings/organization/{org_id}` - Org-level settings
  - GET/PUT `/api/onboarding-settings/store/{store_id}` - Store-level settings
  - GET `/api/onboarding-settings/placeholders` - Available message placeholders
  - POST `/api/onboarding-settings/preview-message` - Preview messages with filled placeholders
- **Frontend:** `/app/frontend/app/admin/onboarding-settings.tsx`
  - SMS Messages section (Welcome, Training Complete, Team Invite, Team Welcome)
  - Available Placeholders reference box
  - App Links section (App Store, Google Play, Web App URLs)
  - Branding section (Company name, Primary/Accent colors, Logo URL)
  - Automation toggles (Training Required, Auto-Send Welcome SMS, Auto-Send Team Invite)
  - Message preview modal

#### Phase 3: Team Member Join Flow - COMPLETE
- **Backend:** `/app/backend/routers/team_invite.py`
  - POST `/api/team-invite/create` - Create team invite link
  - GET `/api/team-invite/validate/{code}` - Validate invite and return store info
  - POST `/api/team-invite/join` - Create user account from invite
  - GET `/api/team-invite/store/{store_id}` - List all invites for a store
  - DELETE `/api/team-invite/{invite_id}` - Deactivate an invite
  - GET `/api/team-invite/user/{user_id}/invite-link` - Get/create personal share link
- **Frontend:** `/app/frontend/app/join/[code].tsx`
  - Public team invite page with store branding
  - Form captures: Name, Phone, Email
  - "Join Now" button creates account
  - Success state with next steps (Download App, Start Training)
  - Error handling for invalid/expired invites

### February 20, 2026 (Session 4)
- **Digital Business Card Share Options** - COMPLETE
- **Revenue Forecaster Multi-Year Projections** - COMPLETE
- **Campaign Permissions Feature** - COMPLETE
- **Congrats Card Keyboard Bug Fix** - COMPLETE
- **URL Shortener Environment Variables** - COMPLETE

### February 20, 2026 (Session 3)
- **URL Shortener System** - COMPLETE
- **Congrats Cards in Admin DATA Section** - COMPLETE
- **Campaign Edit Page** - COMPLETE
- **Enhanced Interactive Onboarding with Visual Demos** - COMPLETE

### February 20, 2026 (Session 2)
- **Congrats Card Feature** - COMPLETE
- **Interactive Onboarding Training** - COMPLETE
- **Impersonate User Feature** - COMPLETE
- **Profile Save UX Improvements** - COMPLETE

### February 20, 2026 (Session 1)
- **Public Landing Page** - COMPLETE
- **Review Approval System** - COMPLETE
- **QR Code Update** - COMPLETE

## Prioritized Backlog

### P0 (Critical)
- [x] Onboarding Settings Admin UI
- [x] Team Member Join Flow (Public invite page)
- [x] Jessie AI Assistant (voice-enabled chat)
- [x] Backend RBAC Enforcement (critical security)
- [ ] Quote → Account Creation flow (Stripe integration pending)

### P1 (High)
- [ ] "Manage Team" for Managers - UI to list/deactivate users, billing summaries
- [ ] "My Account" Pages - My Agreement & My Invoices for managers
- [ ] End-to-end MMS testing (blocked on Twilio approval)
- [ ] SMS automation triggers (needs Twilio approval)
- [ ] Stripe Quotes integration

### P2 (Medium)
- [ ] DMS integrations (myKaarma, Xtime, Tekion, Pipedrive)
- [ ] Zapier integration
- [ ] Luxury UI/UX theme

## Known Blockers
- **Twilio A2P 10DLC:** Outbound SMS/MMS blocked pending carrier approval
- **Stripe Quotes:** User hasn't set up Stripe yet for quote flow
- **Voicemail Recorder:** Web platform limitation - only works on mobile

## 3rd Party Integrations
- **Stripe:** Payments (uses test key) - Quote integration pending user setup
- **OpenAI GPT-5.2:** Text generation for Jessie AI (via emergentintegrations)
- **OpenAI TTS:** Voice generation for Jessie AI (shimmer voice via emergentintegrations)
- **OpenAI Whisper:** Voice-to-text (via emergentintegrations)
- **Twilio:** SMS/MMS (blocked pending approval)

## Test Credentials
- **Super Admin:** forest@mvpline.com / MVPLine2024!
- **Store Manager:** manager@mvpline.com / Manager123!
- **Sales Rep:** sales@mvpline.com / Sales123!
- **Test Store ID:** 699637981b07c23426a5324a
- **Test Invite Code:** xah25yz9 (expires 2026-03-22)

## Database Collections Added
- `onboarding_settings`: Store branding, messages, and automation settings
- `team_invites`: Team invitation links with codes and expiration
- `sms_queue`: Queued SMS messages for automation (pending Twilio)
- `jessie_sessions`: Jessie AI conversation sessions and history
