# CHANGELOG — iMOs App

## Aug 2026 — Click-to-Call Press-1 Gate + In-Call UI (COMPLETED)
- Rep answers their cell and must **press 1** before the customer is dialed — hang-ups/voicemail no longer trigger customer calls (`twilio_webhooks.py`: Gather gate + `/call-bridge-connect`).
- Dialer shows live call status + **red hang-up button** (`/call-cancel` kills both legs; `/call-progress` polled every 2s, fed by status callbacks).

## Aug 2026 — Dialer Fixes (COMPLETED)
- Tap a contact = **stages** the number; only the green button places the call (search results, keypad matches, recents; recents keep a one-tap call icon).
- Search now server-side over the FULL contact book by name or phone digits (was client-filtering the first 50 loaded contacts).
- Layout overflow fixed: keypad sizes to screen height, search-focus swaps to results view (number/status can no longer overlap the search bar or tabs).

## Aug 2026 — Birthday/Anniversary Opt-In Overhaul (COMPLETED)
- **Incident:** editing birthdays fired texts immediately, one contact got two different AI birthday texts. Root cause: auto-applied Birthday tag + save-time campaign enrollment scheduled for "now" via two paths.
- **New rule:** date sends fire ONLY on the actual date, ONLY for contacts manually tagged `Birthday`/`Anniversary`, with a same-day guard (doubles impossible) + single-campaign-per-occasion + 300-day re-enrollment block. Tags never auto-applied; date tags never instant-fire tag campaigns.
- Anniversary = sold-date anniversary: `{years}` variable + auto anniversary card with the car photo.
- New **Date Recipients** screen (search/filter/bulk ON-OFF) + per-contact toggles on the profile; morning **preview digest** (8 AM local SMS + notification) an hour before sends.
- One-time startup migration wiped all previously auto-applied tags and cancelled queued buggy sends (runs itself on production deploy).

## Aug 2026 — Voice Memo Playback Fixed + Webm Conversion (COMPLETED)
- Root cause: storage PUT returns `path`, code read `url` → every memo saved with an EMPTY audio link. Fixed; startup self-heal relinks old memos by contact+timestamp matching (5/5 in preview).
- Audio served with content-type inference + HTTP Range (206) for iOS AVPlayer.
- Web-recorded `.webm` memos now auto-transcode to m4a (imageio-ffmpeg AAC) at upload; stored webm memos convert at startup.

## Aug 2026 — Speed-to-Lead, Photo Reminders, Monthly ROI Email (COMPLETED)
- Leads dashboard: **Speed tab** (team avg + per-rep first-human-reply leaderboard) + color-coded "Replied in Xm" badge per lead.
- Inventory: missing-photos banner + daily 9 AM push to store admins.
- 1st-of-month per-store **ROI email** (leads/replied/sold/spend/$-per-lead/$-per-sale); recipient configurable in Admin → Store → AI & Security; test endpoint `POST /api/leads/analytics/roi-email-test`.

## Aug 2026 — Internal Docs System Refresh (COMPLETED)
- New `/app/docs/`: PRODUCT_REQUIREMENTS.md, OPERATIONS_MANUAL.md (v6, replaces stale v5.0), APP_SCOPE.md.
- `sync_repo_docs()` startup task upserts them into Admin → Docs (hash-guarded) — production docs refresh automatically on deploy.


## Jun, 2026 — Photo Gallery Header Behind Notch (COMPLETED)
- **Bug:** In the contact photo gallery, the close (X) and camera buttons sat up under the iPhone status bar/notch and were untappable — user had to force-close the app.
- **Root cause:** The gallery is a RN `<Modal>`, and `react-native-safe-area-context`'s `SafeAreaView`/insets return **0 inside a Modal** (Modal renders outside the SafeAreaProvider tree), so the header rendered at y=0 under the notch.
- **Fix (`contact/[id].tsx`):** Capture `useSafeAreaInsets()` at the screen level (valid there) and apply it explicitly — `paddingTop: insets.top + 12` on the gallery top bar and `paddingBottom: insets.bottom + 12` on the full-photo bottom bar. Replaced the ineffective in-Modal `SafeAreaView` with a plain `View`.
- **Verified:** Web preview — gallery opens, header renders (X · Photos · camera), no regression. Native notch offset can't be shown on web (insets=0 there) but is the standard fix.
- **Note:** Same "controls under the notch" pattern may exist in other RN Modals across the app (user mentioned seeing it elsewhere) — not yet swept.
- **Deploy note:** Native frontend change — ships via `eas update --branch production`.


## Jun, 2026 — Date Picker Invisible in Light Mode (COMPLETED)
- **Bug:** The birthday/date picker text was invisible and couldn't be changed. Root cause: the native `DateTimePicker` hardcoded `textColor="#FFFFFF"` + `themeVariant="dark"`, but the sheet background follows the theme (`colors.card`). In light mode that's white text on a white sheet → invisible; you can't scroll a spinner you can't see.
- **Fix:** Made the picker theme-adaptive — `textColor={colors.text}` + `themeVariant={mode}` (from `useThemeStore`). Applied to the contact birthday/anniversary/custom-date picker AND the automation-date picker (`contact/[id].tsx`), plus the same latent bug in `AppointmentModal.tsx` (date + time), `campaigns/new.tsx`, and `campaigns/[id].tsx`. No hardcoded white pickers remain.
- **Note:** The native `DateTimePicker` doesn't render on web preview (web uses a custom scroll picker), so this is verified by code/type-check only; visual confirmation is on device.
- **Deploy note:** Native frontend change — ships via `eas update --branch production`.


## Jun, 2026 — Gallery Sections, Camera, Use-in-Card & Security Phase 3 (COMPLETED)
- **Photo Sections (frontend `contact/[id].tsx`):** The contact photo gallery is now grouped into sections with gold headers — **Texted In** (customer MMS), **You Sent**, **Cards** (congrats/birthday), **Profile** (current + history). Global photo indices preserved so the full-photo viewer still works. Verified on web: TEXTED IN · 1, CARDS · 1, PROFILE · 4 render with per-tile set-as-profile icons.
- **Camera Option (frontend):** The gallery "Add Photo" now shows a native chooser — **Take Photo** (camera) or **Choose from Library**. Camera uses `launchCameraAsync` + camera-permission request; both defer their launch until the photo-viewer modal fully dismisses (iOS `onDismiss` + Android/web timeout). Web goes straight to the file picker.
- **Use for Card (frontend):** Added a "Use for Card" button (gift icon) to the full-photo viewer. It routes to `/settings/create-card` with `prefillPhoto=<url>`; `create-card.tsx` now reads that param (init + effect) and pre-loads the recipient photo. Verified on web (photo pre-populates the card).
- **Security Phase 3 (backend):**
  - **Login rate limiting** (`auth.py`): MongoDB-backed brute-force protection keyed by `ip:email` — 8 failed attempts → 15-min lockout (429), cleared on success. TTL index auto-cleans `login_attempts` after 1 day. Real client IP via `cf-connecting-ip`/`x-forwarded-for`. Verified: 8×401 then 429.
  - **Password-reset per-IP throttle** (`auth.py`): max 6 reset requests per IP / 10 min (adds to existing per-account 3/10-min + code lockout); stores `request_ip` on reset tokens.
  - **Strict CORS** (`server.py`): allowed origins now read from `CORS_ORIGINS` env (comma-separated). Preview set to preview/prod/custom-domain/localhost. `"*"` still supported for permissive mode. Native apps unaffected (no Origin header).
  - Env vars: `LOGIN_MAX_FAILS`, `LOGIN_LOCKOUT_MINUTES`, `RESET_IP_MAX`, `RESET_IP_WINDOW_MIN`, `CORS_ORIGINS`.
- **⚠️ Production action needed:** Set `CORS_ORIGINS` in the PRODUCTION backend `.env` to the real web origins before/at deploy (it currently defaults to permissive there). Deploy backend via the Deploy button; push the native UI via `eas update --branch production`.


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

## Jun 2026 — Text Wrapping Fixes + Dialer Name Search
- Home "Today's Touchpoints" scoreboard: restructured from 1 row of 6 to 2 rows of 3 (number + label side-by-side), with numberOfLines/maxFontSizeMultiplier caps so labels never wrap at large Dynamic Type sizes (home.tsx)
- NotificationBell dropdown title: "Notifications" now single-line with adjustsFontSizeToFit + maxFontSizeMultiplier (NotificationBell.tsx)
- Dialer: added "Search contacts by name" bar at top of dial pad; typing a name shows matching contacts full-screen with tap-to-call (dialer.tsx). Tap calls via existing Twilio click-to-call flow
- Root cause of wrapping: user's iPhone large accessibility font scale multiplying fontSize
- Verified via web preview screenshots (login → home scoreboard, dialer search "Forest" → match → call button, notifications dropdown)

## Jun 2026 — Four Features: Backdate Sold Date, Delete Texted Photos, Dialer Recents, Report a Bug
- **Backdate Sold Date**: "SALE DATE" picker (default today, max today) added to /sold-quick and /contact/sold-wizard step 2. New PATCH /api/contacts/{uid}/{cid}/date-sold endpoint. Purchases POST now uses the chosen date. Failure surfaces a warning alert instead of silent swallow
- **Delete Texted Photos**: DELETE /photos now accepts photo_type message_in/message_out → adds normalized URL to contact.hidden_gallery_urls; gallery GET /photos/all filters hidden. _norm_media_url strips scheme+domain so proxy/base-url differences still match
- **Dialer Recents**: Keypad/Recents segmented toggle on dialer. GET /api/contacts/{uid}/recent-calls (contact_events call_placed/call_received joined with contacts). Consecutive calls to same contact collapsed with (n) count
- **Report a Bug**: /report-bug form (category chips + description) → POST /api/bug-reports/{uid} (stores db.bug_reports + Resend email to all super_admins). Admin screen /admin/bug-reports (filters, Start/Resolve/Reopen status flow, role guard + error/retry UI). Hub entries: Settings→Report a Bug, Internal Ops→Bug Reports
- **Security**: /api/bug-reports/ added to BOLA PROTECTED_PREFIXES (POST now requires JWT matching path user). GET/PATCH admin endpoints verify JWT (Authorization Bearer) + super_admin role from DB — X-User-ID header alone no longer accepted
- Testing: testing agent iteration_283 (17 backend pytest all pass + full frontend flows); all flagged issues fixed and re-verified via curl + screenshots
- LEARNING: Metro watcher in this pod often serves stale bundles — run `sudo supervisorctl restart frontend` after edits before screenshot verification

## Jun 2026 — Live Inventory, Intent Sensitivity, Bug Push, Lockout Settings
- **Live Inventory (inventory-ready, user chose option c)**: new /app/backend/routers/inventory.py (CRUD + CSV import, feeds same db.inventory as HomeNet-compatible webhook API); /app/frontend/app/inventory.tsx management screen (search, filters, add modal, CSV upload via DocumentPicker, mark sold, delete); Hub → Manage → Inventory entry; Jessi (ai_reply.py) now searches store inventory on availability/pricing questions via _search_inventory_context and answers with real vehicle facts (price/color/mileage/stock#) instead of generic escalation — still flags convo + pushes rep. AI-suspect messages always escalate
- **Intent Sensitivity**: per-store intent_hot_threshold (1-10, default 7) on stores collection; intent_detection._get_hot_threshold; admin UI pills in /admin/stores/[id] "AI & Security" section; GET/PUT /api/admin/stores/{id}/ai-security-settings
- **Bug Push Alert**: bug_reports._push_super_admins → send_push_to_user for all super_admins on new report (background task, logged)
- **Lockout Settings**: per-store login_max_fails (3-50) + lockout_minutes (1-1440); auth._get_lockout_settings resolves on failed login; same admin UI section
- Fixes from testing (iteration_284): guarded ObjectId for legacy org ids in admin_hierarchy get_store (500 → 200); inventory PUT/DELETE now BOLA-scoped via _scope_query (cross-user → 404); /inventory auth guard + no infinite spinner; seeded vehicles backfilled with store_id; vehicle name wraps 2 lines
- 3 demo vehicles seeded in preview DB (Tacoma/F-150/Civic, store 69a0b7095fddcede09591668)

## Jun 2026 — Inventory Photos, Sensitivity Preview, Weekly Bug Digest
- **Inventory Photos**: POST /api/inventory/{uid}/{item_id}/photo (base64 → object storage via upload_image, prefix 'inventory'); inventory.tsx cards show 62px thumbnail or dashed add-photo placeholder (ImagePicker, tap photo to replace). Jessi's _search_inventory_context now returns (context, media_urls) — top matching vehicle's photo (photo_full_path as absolute PUBLIC_FACING_URL) attaches to the queued AI reply; ai_reply queue_doc carries media_urls; sender passes media_urls to send_sms (MMS) and logs has_media/media_urls on the message so it renders in the inbox thread
- **Sensitivity Preview**: GET /api/admin/stores/{id}/intent-preview (recent intent-scored conversations of store users, joined w/ contact names); admin AI & Security section lists them with score badges + live "WOULD ALERT" highlight vs currently selected threshold pill
- **Weekly Bug Digest**: bug_reports.send_weekly_bug_digest (skips when no open/in_progress reports; HTML digest w/ status badges, reporter, age) + scheduler job weekly_bug_digest CronTrigger mon 15:00 UTC (~8-9am Mountain), registered & verified via /api/scheduler/status
- FIX: digest age calc handles tz-naive Mongo datetimes
- NOTE: preview env Resend domain (send.imonsocial.com) not verified → digest email only sends in PRODUCTION (same limitation as all preview emails)
- Demo data seeded in preview: red photo on Tacoma, 3 intent-scored conversations (scores 8/6/4) owned by forestward@gmail.com with demo_seed:true flag

## Jun 2026 — ADF/XML Lead Intake Completion (Email + Inventory Match)
- DISCOVERED existing full lead intake engine (lead_intake.py): POST /api/leads/adf (ADF XML parser, plain-text ACK per spec), POST /api/leads/webhook/{source_id} (Zapier-style JSON/form normalizer + X-API-Key), lead sources CRUD w/ jump-ball/round-robin assignment, AI first message, after-hours scheduling, intake workflows
- NEW: POST /api/leads/email-inbound — provider-agnostic inbound-email webhook (SendGrid Inbound Parse multipart, Mailgun Routes, CloudMailin JSON w/ base64 attachments, quoted-printable). Scans all fields+attachments for <adf> block; failures logged to db.lead_email_failures
- NEW: _match_lead_inventory — leads' vehicle of interest auto-matched to live store inventory (make/model regex + year/trim ranking); stored on inbound_leads.matched_inventory; AI first message + fallback template now quote real stock (name, color, price, stock#)
- serialize_lead_source now returns adf_url + email_inbound_url (PUBLIC_FACING_URL based) and absolutizes legacy relative webhook_url
- Admin lead source detail page (/admin/lead-sources/[id]) shows 3 connection blocks: Webhook URL, ADF/XML URL, Email Lead Intake (with CloudMailin/SendGrid setup hint)
- Fixed preview test source TEST_Lead_Source_VA_Picker store_id (was a user id)
- Tested e2e: ADF POST creates lead+contact+conversation w/ matched Tacoma + stock-aware draft; email-inbound verified in CloudMailin JSON + SendGrid multipart attachment formats; all QA leads cleaned up

## Jun 2026 — Leads Dashboard + Source ROI Tracking
- GET /api/leads/ enhanced: matched_inventory, has_reply (distinct inbound messages per conversation), comments; now JWT-gated via _require_auth (intake POSTs remain public for providers)
- NEW GET /api/leads/analytics/sources?days= — per-source funnel: leads → sent → replied → sold with reply_rate/sold_rate (replied = conversation has inbound msg; sold = contact.date_sold set); totals summary
- NEW /app/frontend/app/leads.tsx — "Internet Leads" dashboard: Leads tab (status filters, source/status/REPLIED badges, vehicle interest, matched in-stock vehicle box w/ photo+price+stock#, tap → thread) + Source ROI tab (30/90/365-day windows, totals, per-source reply/sold progress bars)
- Hub → Manage → "Internet Leads" entry added
- Tested e2e with QA leads (matched Tacoma/Civic, seeded reply + sale → 50% rates verified), 401 for unauth list; QA data cleaned

## Jun 2026 — Lead Cost Entry, New Lead Push, Auto Photo Text
- **Lead Cost**: lead_sources.monthly_cost (LeadSourceUpdate + serialize); analytics computes period_cost (monthly*days/30), cost_per_lead, cost_per_sale per source; admin lead source edit form has MONTHLY COST input; ROI tab shows $ PER SALE / PER LEAD / SPENT tiles + hint when unset
- **New Lead Push**: process_inbound_lead pushes assigned rep instantly ("🔥 New Lead — {name}", vehicle + IN STOCK note, deep-link /thread/{conv_id}) via send_push_to_user create_task (additive to intake workflow blast; only fires when a rep is assigned via round-robin/weighted)
- **Auto Photo Text**: matched vehicle's photo (photo_full_path absolute URL) stored as inbound_leads.media_urls; process_queued_leads passes media_urls to send_sms (MMS) and logs has_media on the message
- Verified: PATCH monthly_cost 1200 → 30d analytics $1200 per lead/sale; lead media_urls carries Tacoma photo; ROI UI screenshot shows dollar tiles. QA data cleaned (test source keeps $1200 cost as demo)

## Contact Detail Screen Refactor (Aug 21, 2026) — self-tested e2e via screenshots
- Split monolithic `app/contact/[id].tsx` (5,288 → 2,985 lines) into 12 render-only components under `components/contact/`:
  HeroSection, EditFormTop, EditFormBottom, FeedTab, DetailsTab, CallsTab, ComposerBar,
  ShareModals, PickerModals, DateModals, AddTaskModal, GalleryModal.
- Zero logic/visual changes: all state + handlers stay in parent, components are prop-driven (mirrors thread/[id] refactor pattern).
- `getEventTitle` moved to `utils/contactHelpers.tsx` (shared by parent + FeedTab); months/getDaysInMonth moved into DateModals.
- All data-testids preserved verbatim. Verified: Feed/Details/Calls tabs, edit mode, AddTask modal, photo gallery modal, feed date-group collapse — all render + behave identically on preview.

## Touchpoints Swipe Actions (Aug 22, 2026) — self-tested e2e via screenshots
- `app/touchpoints/index.tsx`: TaskCard bottom row now Call + Text ONLY; Done & Snooze moved to swipe gestures.
- Swipe right → gold Done (completes task); swipe left → gray Snooze (24h). Native uses gesture-handler Swipeable (inbox pattern), web uses WebSwipeableItem. Hint line "Swipe right = Done · Swipe left = Snooze" above list.
- Card border/radius moved to swipe wrapper so actions reveal inside the rounded frame.
- Also fixed pre-existing crash: dormant-cleanup banner called undefined `loadTasks()` → now `loadData()`.
- Verified on preview: both swipe directions reveal + snap open on Overdue cards.

## Voice Memo Intel Update Fix (Aug 2026) — backend, tested e2e in preview
- Bug: `services/voice_intel.py merge_personal_details` never overwrote existing values (scalars kept old value; top-level employer/occupation/vehicle only set when empty) → new employment/spouse info from fresh memos was silently discarded.
- Fix: newest memo wins — scalar personal_details fields overwrite, lists still merge+dedup, top-level vehicle/occupation/employer always updated when extracted.
- Verified live: gpt-5.2 extraction via EMERGENT_LLM_KEY works; test contact employer "Old Company Inc"→"Tesla", spouse "Karen"→"Sarah". NOTE: user saw this in PRODUCTION — requires backend redeploy to take effect there.

## Salesperson Quick Actions (Aug 23, 2026) — self-tested e2e via screenshots + curl
- Home quick actions now 6 tiles (3 rows × 2): SOLD! · Send Photo · Review · Card · Voice Note · New Contact.
- NEW /quick-send/photo screen: snap/pick photo → search contact → caption → MMS via smartSendSMS (Twilio) or native-SMS fallback w/ photo link; logs photo_sent event. Industry-neutral copy per user (auto-adjacent: insurance/real estate).
- NEW AI master switch: gold "AI ON"/gray "AI OFF" pill in Home header → PATCH /users/{id} ai_master_paused (added to allowed_fields in server.py patch_user_profile AND auth.py patch_user — NOTE: /api/users/{id} routes to server.py:1003, auth.py version is at /api/auth/users/{id}).
- Backend gate: queue_ai_reply (ai_reply.py) returns None when assigned user has ai_master_paused=true — stops ALL AI drafts/auto-replies.
- Voice Note tile → contact picker → /contact/{id}?capture=true (existing deep-link auto-starts recorder). Verified recorder auto-started.
- Production needs BOTH: backend redeploy (AI gate + allowed_fields) AND eas update (Home/photo screen).

## Card QR + Photo to Many + Undo Snackbar (Aug 23, 2026) — all self-tested e2e
- Card QR: Home Card tile picker now has "Card QR Code" → UniversalShareModal opens straight to a REAL scannable QR (react-native-qrcode-svg; replaced the old placeholder icon for ALL QR views). New props: startWithQR.
- Photo to Many: /quick-send/photo now multi-select (checkmark rows, "Next — Text N people" bar, recipient chips + Add on send step). Uploads once, loops smartSendSMS per person; native fallback uses comma-joined sms: recipients.
- Undo snackbar: touchpoints swipe Done/Snooze shows 5s "Done — {name} [UNDO]" bar. Backend: new `reopen` action in PATCH /api/tasks/{uid}/{tid} (restores pending, clears snooze/completed, restores due_date, deletes task_completed event, reverts pending_send). Verified via curl + UI.
- Production: needs backend redeploy (reopen action) + eas update (all frontend).
