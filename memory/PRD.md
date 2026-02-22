# iMos - Product Requirements Document

## Original Problem Statement
iMos is a business management app for retail/service businesses. Key features include:
- User/team management with invite flows
- Store management
- SMS/messaging capabilities
- Partner agreements
- Review management
- AI assistant (Jessi)

## Current Architecture
```
/app
├── backend/         # FastAPI + MongoDB
│   ├── routers/     # API endpoints
│   └── models.py    # Pydantic models
├── frontend/        # React Native/Expo (web export)
│   ├── app/         # Screens (Expo Router)
│   ├── components/  # Reusable components
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

### Completed This Session (Feb 22, 2026)
- [x] Fixed "Ask Jessie" microphone not working on web
  - Added web platform detection (IS_WEB constant)
  - Created web-specific HTML button for mic (instead of TouchableOpacity)
  - Modified VAD to work without metering on web (assumes user is speaking)
  - Added webm audio format support for web recordings
  - Fixed blob URL handling for web audio uploads
- [x] Added EMERGENT_LLM_KEY to backend for Jessie AI responses
- [x] Verified admin seeding script creates default admin user on empty database

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

### P0 (Critical) - IN PROGRESS
- [ ] Email delivery (BLOCKED - user needs to verify domain with Resend)
- [ ] Quote drafts view/edit/delete functionality

### P1 (High Priority)
- [ ] Twilio SMS integration (currently mocked)
- [ ] Store Edit/Delete functionality
- [ ] Populate Reports section with real data (currently hardcoded)

### P2 (Medium Priority)
- [ ] Rebuild frontend dist with rebranding updates

### P3 (Low Priority/Future)
- [ ] App Store submission prep
  - App icons
  - Splash screens
  - EAS build configuration
  - Screenshots

## Test Credentials
| Email | Password | Role |
|-------|----------|------|
| forestward@gmail.com | Admin123! | super_admin |
| bridger@imosapp.com | Admin123! | super_admin |
| admin@imosapp.com | iMOs2026! | super_admin (seeded) |

## Technical Notes
- Database field `mvpline_number` preserved for data compatibility
- Internal storage keys (biometrics, calendar) unchanged
- SMS functionality is MOCKED until Twilio integration
- Marketing site updates require manual Netlify deploy
- expo-av is deprecated - will be removed in SDK 54 (migrate to expo-audio/expo-video)
- Passwords are stored in PLAINTEXT (not hashed) - be aware when working with auth

## Integrations
- **Resend:** Email sending (active but blocked - needs domain verification)
- **Netlify:** Marketing site hosting (active)
- **Twilio:** SMS/MMS (planned, not implemented)
- **EMERGENT_LLM_KEY:** Used for Jessie AI assistant (GPT-5.2 + OpenAI TTS)
