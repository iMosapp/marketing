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

## What's Been Implemented

### Core Features
- [x] User authentication (login/logout)
- [x] Email-based team invitations
- [x] Store profile management
- [x] Business hours configuration
- [x] Social media links
- [x] Partner agreements system
- [x] Invoice viewing
- [x] AI assistant (Jessi)
- [x] WebSafeButton component (mobile web fix)

### Completed This Session (Feb 2026)
- [x] Password reset for forest@imosapp.com
- [x] Full rebranding: mvpline.com → imosapp.com
  - Updated all email addresses
  - Updated all URLs
  - Updated app.json (name, slug, scheme)
  - Updated database user emails
- [x] Verified mobile button fix working

## Prioritized Backlog

### P0 (Critical) - COMPLETE
- ~~Rebranding from mvpline to imosapp.com~~

### P1 (High Priority)
- [ ] Twilio SMS integration (currently mocked)
- [ ] Store Edit/Delete functionality

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
| forest@imosapp.com | Admin123! | super_admin |
| bridger@imosapp.com | Admin123! | super_admin |
| manager@imosapp.com | Admin123! | store_manager |

## Technical Notes
- Database field `mvpline_number` preserved for data compatibility
- Internal storage keys (biometrics, calendar) unchanged
- SMS functionality is MOCKED until Twilio integration
- Marketing site updates require manual Netlify deploy

## Integrations
- **Resend:** Email sending (active)
- **Netlify:** Marketing site hosting (active)
- **Twilio:** SMS/MMS (planned, not implemented)
