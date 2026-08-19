# CHANGELOG — iMOs App

## Jun, 2026 — Contact Gallery: Include All Past Photos (COMPLETED)
- **Request:** The contact photo gallery should include every photo tied to a contact — especially photos the customer texted in (e.g., "their Jeep on the rocks in Moab") — so any can be set as the contact photo for a birthday text/card.
- **Backend (`contacts.py` `GET /photos/all`):** Added a new source — MMS photos from the `messages` collection for the contact's conversations. Includes inbound (customer-sent, labeled "From {first_name}") and outbound (rep-sent, "You sent") images. Image-only filter (skips `.vcf` contact cards and non-images); raw `api.twilio.com` media URLs are wrapped in the auth media-proxy so they display.
- **Backend (`contacts.py` PATCH `/profile-photo`):** When a Twilio/proxy MMS photo is set as the profile, it's now downloaded and re-uploaded to object storage (durable) so the avatar survives Twilio media retention. Falls back to storing the URL directly if fetch fails.
- **Frontend (`contact/[id].tsx`):** Both "set as profile" handlers now use the durable `photo_url` returned by the backend. The existing gallery grid already renders all photo types with a tap-to-set-profile action, so MMS photos are immediately usable.
- **Verified:** Seeded inbound MMS (object-storage + raw Twilio + a `.vcf`) → gallery correctly listed the two images (Twilio one proxy-wrapped), skipped the `.vcf`; set-as-profile returned 200 for both durable and fallback paths. Test data cleaned up.
- **Deploy note:** Backend change (Deploy button) + native frontend (`eas update --branch production`).


## Jun, 2026 — Contact Gallery "Add Photo" Picker Fix (COMPLETED)
- **Bug:** In Contact → tap avatar → photo viewer → "Add Photo", the image picker never opened on iOS — it flashed and returned to the contact. Root cause: iOS cannot present the image-picker view controller while the photo-viewer `Modal` is still dismissing.
- **Fix (frontend, `contact/[id].tsx`):** Defer launching the picker until the Modal has fully closed — added `Modal onDismiss` (iOS) with a `pendingPickRef` flag + a 350ms timeout fallback for Android/web. Both the header camera button and the empty-state "Add Photo" button now route through `requestAddPhotoFromGallery`.
- **Also made it persist:** New helper `uploadGalleryPhoto` picks the photo and immediately saves it via `POST /api/contacts/{user}/{id}/photo` (the previous code used a non-existent PATCH route), then refreshes the gallery. Backend endpoint verified via curl (returns compressed `photo_url`).
- **Deploy note:** Native frontend change — requires `eas update --branch production` to reach the live app.


## Jun, 2026 — Inbox Contact-Card (.vcf) Rendering Fix (COMPLETED)
- **Bug:** Outbound "tap to save my number" intro messages attach a `.vcf` contact card (media_url `/api/profile/{id}/vcard.vcf`, content-type `text/vcard`). The customer's phone renders it as a native contact card (with embedded photo), but the app's own inbox tried to render the `.vcf` via `<Image>` → blank gray placeholder box.
- **Fix (frontend only, `thread/[id].tsx`):** Detect `.vcf`/`/vcard` media URLs and render a dedicated Contact Card tile (rep's profile photo + name + "Contact Card · Tap to save", tap opens the vCard) instead of a broken image. Added `myPhoto` state fetched from `/api/profile/{user._id}`.
- **Verified** on web preview (seeded a test vCard message, screenshot confirmed the tile renders; test data cleaned up).
- **Deploy note:** Native frontend change — requires `eas update --branch production` to reach the live app.


## Mar 3, 2026 — Send Something Picker Cleanup (COMPLETED)
- **Consolidated picker:** Removed "Enroll in Campaign" from the + button menu, moved "Create a Card" to #5, added "Photos" sub-menu (Photo Library + Camera) at #6
- **Final order:** My Digital Card → Review Link → My Showcase → My Link Page → Create a Card → Photos

## Mar 2, 2026 — Activity Logging & Call Screen Fixes (COMPLETED)
- **No em-dashes in AI suggestions:** Updated system prompt + added post-processing to replace em-dashes (—) with commas and en-dashes (–) with hyphens in `/api/contact-intel/{user_id}/{contact_id}/suggest-message`
- **Call button → Call Screen on web:** Previously web just opened `tel:` with no duration logging. Now routes through `/call-screen` on all platforms so call duration is tracked and logged to the activity feed
- **Verified Log Customer Reply:** Both the green "Log Customer Reply" button (in feed) and the orange ↩️ button (in composer toolbar) open the same inline composer. Backend endpoint confirmed working.
- **Testing:** 100% pass rate (iteration_99.json)

## Mar 2, 2026 — Light Mode Deep Cleanup (COMPLETED)
- **Fixed Contact Detail page light mode visibility:** Stats bar (touches, msgs, campaigns, referrals), feed titles, descriptions, date headers, tags, voice note timestamps, and 15+ additional styles now use theme-aware colors
- **Fixed IntelRenderer component:** Was using hardcoded `#FFFFFF` white text; now uses `colors.text`/`colors.textSecondary` from themeStore
- **Fixed Leaderboard page:** User names, roles, scores, stat labels, and footer labels all use theme-aware colors (8 style fixes)
- **Fixed across 15+ files:** thread/[id].tsx, admin/data/* (6 files), showroom-manage.tsx, admin/contacts.tsx, admin/white-label.tsx
- **Reverted unsafe changes:** Static StyleSheets (help.tsx, forecasting.tsx, admin/index.tsx tickerStyles, more.tsx shareStyles, onboarding demoStyles) kept with safe neutral colors since they don't have access to dynamic `colors` parameter
- **Testing:** 100% pass rate — all pages verified in both light and dark mode (iteration_98.json)

## Mar 2, 2026 — Light Mode Theme Audit (COMPLETED)
- **Full app-wide refactor of 250+ .tsx files** to support light mode
- Automated + manual transformation: hardcoded hex colors → dynamic `useThemeStore` + `getStyles(colors)` pattern
- Key conversions:
  - thread/[id].tsx: Dynamic color mapping with custom local theme
  - contact/[id].tsx: getS() dynamic stylesheet
  - inbox.tsx: Preserved local theme system
  - admin pages, settings, leaderboard, create-card, onboarding, showroom-manage, white-label, call-screen
- Fixed: Thread page toolbar/composer dark background
- Fixed: Contact detail page missing useLocalSearchParams
- Fixed: Corrupted color values from substring replacement
- Fixed: Double-brace JSX syntax errors
- Fixed: Module-scope colors.xxx references
- Fixed: Duplicate colors declarations
- Fixed: Inner component styles access (home.tsx ContactActionModal, training-hub.tsx VideoEmbed)
- **Testing:** 100% pass rate in both light and dark mode (iteration_97.json)

## Mar 2, 2026 — Tags UI + Search by Tag + Timezone Fix
- Contact tags moved to dedicated scrollable strip with "+" button
- Backend search extended to query contacts by tags
- Global timezone fix: Backend middleware ensures UTC timestamps
- Frontend date grouping logic corrected

## Mar 2, 2026 — Help Center AI Redesign
- Replaced category pills with search bar + AI assistant
- New backend endpoint: POST /api/help-center/ask
- Two modes: Article Browse and AI Chat

## Mar 2, 2026 — Menu Cleanup
- Removed Phone Dialer, reordered Campaigns
- Removed SMS/Email Toggle and Notifications sections

## Mar 2, 2026 — Date-Based Automations
- Editable and removable Birthday, Anniversary, Sold Date automations
