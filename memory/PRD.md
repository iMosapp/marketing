# iMOs - Product Requirements Document

## Original Problem Statement
iMOs is a **Relationship Management System (RMS)** for retail/service businesses.

## Public Marketing Site
All 57 pages at `app.imosapp.com/imos/...` — no auth required.

### Design System
- Background: True black `#000`
- Accent: Gold `#C9A962`

## What's Been Implemented
- [x] Full RMS with contacts, messaging, campaigns, AI
- [x] Automated Campaign Scheduler (APScheduler)
- [x] 57 public pages at /imos/ (all verified)
- [x] Customer-facing header, Schedule a Demo, 14-day free trial
- [x] All email invite URLs updated to production domain
- [x] Team Chat: delete channel, clear history, real-time WebSocket
- [x] **Team Chat Web Compatibility Fix** (Feb 26, 2026):
  - Fixed 3-dot menu dropdown on channel list (was not clickable due to Pressable event conflicts)
  - Fixed chat header dropdown menu (Clear History, Delete Channel)
  - Replaced Pressable overlay pattern with backdrop+dropdown siblings using responder system
  - Create Channel panel, channel row click, message input all verified working on web
- [x] **Delete Contacts — Single + Bulk** (Feb 26, 2026):
  - Backend: DELETE /api/contacts/{user_id}/{contact_id} and POST /api/contacts/{user_id}/bulk-delete
  - Frontend: Select mode with checkboxes, select all, bulk delete with confirmation
  - Long-press on contact enters select mode
- [x] **Digital Card Layout — Social Links above Voice Recorder** (Feb 26, 2026):
  - Reordered Social Media Links section above Voicemail Greeting in my-profile.tsx
- [x] **Team Chat Channel Search/Filter Bar** (Feb 26, 2026):
  - Added search input above channel list in Team Chat
  - Filters channels by name in real-time, clear button to reset
- [x] **Inbox Email Prompt Fix** (Feb 26, 2026):
  - Email prompt no longer shows when contact already has an email address
  - Backend conversation info endpoint now returns contact_email
  - Frontend loadContactInfo fetches email from contact record as fallback
- [x] **Congrats Card Web Fix + Create Page** (Feb 26, 2026):
  - Fixed "Object error" on web: FormData photo now uses fetch+blob conversion
  - New "Create Congrats Card" page at /settings/create-congrats
  - Full sharing options after creation: Copy Link, Download, View Card, SMS, Email, Facebook, Twitter
  - **Relocated to My Account → QUICK ACTIONS** next to "My Digital Card", with "Edit Digital Card" moved down (Feb 26, 2026)
- [x] **Social Media Username-Only Inputs** (Feb 26, 2026):
  - Edit Digital Card: Social fields now show URL prefix (e.g. facebook.com/) with just username input
  - Auto-strips @ symbol from input
  - Digital Card constructs full URL from base URL + username
  - Backwards compatible with existing data (full URLs or usernames both work)
  - Admin > Organizations, Accounts, Users pages all accessible
  - User detail page has Change Organization and Assign Store modals
  - **NEW: "Link Existing Account"** button on Org detail page — opens searchable panel of unlinked accounts, one-click to link
  - **NEW: "Link Existing User"** button on Org detail page — opens searchable panel of unlinked users, one-click to link
- [x] Inbox: removed SMS/Email toggle pills, inline email prompt
- [x] Avatar system: auto-backfill thumbnails from raw photos (Feb 25, 2026)
- [x] Image quality: 1080px for outbound sharing (Feb 25, 2026)
- [x] Training Hub: 16 topics, 6 categories, step-by-step, video embed ready, Jessi AI help (Feb 25, 2026)
- [x] SOPs: Fixed "MVPLine" to "iMOs", 13 SOPs verified working (Feb 25, 2026)
- [x] Invite Team: vertical role tiles, "Create & Copy Invite" with copyable credentials (Feb 25, 2026)
- [x] Delete pending invites: trash icon on team member rows (Feb 25, 2026)
- [x] **Notification System Phase 1** (Feb 25, 2026):
  - WebSocket real-time connection (`/api/ws/{user_id}`)
  - Notification bell with dropdown on More and Inbox pages
  - Team chat broadcasts via WebSocket to channel members
  - Inbound customer messages create notifications + WebSocket events
  - Unread badges on Inbox and Team tabs (with real-time updates)
  - Notification CRUD: list, unread count, mark read, mark all read, clear all
  - 15-second polling fallback for badge counts

## Known Issues
- Twilio SMS MOCKED
- React Hydration Error #418
- Email invite URL is hardcoded to `https://app.imosapp.com` (INTENTIONAL — do not change)
- Authentication uses plain-text passwords (security risk, bcrypt refactor planned)

## Upcoming
- (P1) Push notifications for mobile (Phase 2 — Expo Push)
- (P1) Voice Help Assistant Backend
- (P1) Refactor authentication to use hashed passwords (bcrypt)

## Future/Backlog (P2)
- WhatsApp Integration
- White-Label System (custom domains, org branding)
- Enable Lead Notification System advanced features
- Build full Inventory Management Module
- Create Searchable Training Manual
- Populate Reports & Analytics section
- Fix React Hydration Error #418
- Verify mobile tags data sync
- Test leaderboard toggle functionality

## Credentials
- Super Admin: forest@imosapp.com / Admin123!

## 3rd Party Integrations
- MongoDB Atlas: Primary database
- Resend: Transactional and user-initiated emails (working)
- Twilio: SMS messaging (MOCKED)
- OpenAI: "Jessi" AI assistant

## Key DB Schema
- **notifications:** `{user_id, type, title, message, data, read, created_at, conversation_id?, contact_id?, channel_id?}`
  - Types: new_message, new_lead, team_mention, team_broadcast, team_chat, jump_ball
- **contacts:** `{..., photo, photo_url, photo_thumbnail}`
- **contact_photos:** `{contact_id, photo_full, updated_at}`
- **sops:** `{title, summary, department, category, is_required_reading, estimated_time, steps, ...}`
