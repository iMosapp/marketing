# Tools QA: inventory, standard, progress

Single source of truth for the screen-by-screen pass over everything reachable from the Tools tab.
Update the Status column as batches land. Statuses: `todo`, `fixed`, `ok` (checked, no changes needed), `later` (super-admin only, lowest priority).

## The standard (every screen must meet this)

Type scale lives in `frontend/constants/typography.ts` (`FS`). Pick from it, never invent sizes.

| Element | Spec |
|---|---|
| Screen title (nav bar) | 17 / 700, centered, back chevron left at 44x44 hit area, one optional action on the right |
| Large page heading (only Home/Tools style screens) | 28 / 800 |
| Section eyebrow | 12 / 700, uppercase, letterSpacing 0.8, textSecondary |
| Card / row title | 16 / 700, `numberOfLines={1}` only when the row has a fixed height, otherwise wrap |
| Body / values / inputs | 15 / 400 |
| Subtitle, supporting, chips | 13 / 400-600 |
| Meta, timestamps | 12 |
| Pills, badges | 11 / 800 |
| Primary button | gold `#C9A962`, black text, 16 / 700, radius 14 (pill 28 for full width CTAs) |
| Cards | radius 16, `colors.card` background, 1px `colors.border` |
| Screen padding | 16 horizontal, 20 between sections |
| Safe area | top via `SafeAreaView edges={['top']}`, bottom padding at least 32 on scroll content |
| Dynamic Type | `maxFontSizeMultiplier={1.2}` on titles and anything inside a fixed-height row, so iOS Large Text cannot overflow |
| Truncation | never cut a word in the middle in a fixed row: shrinkable text (`flexShrink: 1`) plus `numberOfLines` |
| Theme | reads `useThemeStore().colors` everywhere, no hardcoded `#000`/`#fff` backgrounds |
| Copy | no em dashes, sentence case, "Tools" never "More" |
| Empty state | icon + one sentence + one action, never a blank screen |
| Loading | skeleton or spinner within the card area, header still visible |
| Test ids | every button/input has `testID` + `dataSet.testid` |

## Batch order

1. My Brand (rep + manager)  DONE (13 screens, tested iteration_295)
2. Today + loose tiles  DONE (6 screens, tested iteration_296/297) (Touchpoints, Calendar, My Numbers, AI Follow-ups, Inventory)
3. Settings  DONE (6 screens, tested iteration_298) (My Profile, My VA, Notifications, Schedule, Templates, Security, Calendar Sync)
4. Learning  DONE (Training Hub, Help Center, Report a Bug)
5. Leads  DONE (tested iteration_299) (Internet Leads, Call Retries, Lead Source Queue, Lead Source Config, Connect Zapier / Make, Team Availability)
6. Manage  DONE (tested iteration_300) (Tags, Keyword Auto-Tags, Keyword Search, Campaigns, Review Center, Showcase approvals, Inventory Feed, Review Links)
7. My Performance  DONE (tested iteration_301) (Team Sales, Team Tasks, Customer Engagement, Leaderboard, Activity Reports, Email Analytics, SEO/GEO Health, VA Library)
8. Campaigns + My Tools  DONE (tested iteration_302) (Campaign Dashboard, Date Triggers, Ask Jessi, Team Chat)
9. Set Up  DONE (tested iteration_303) (Store Profile, Brand Kit, Messaging Channels, Phone Numbers, Team Members, Invite Team, Integrations)
10. Admin / Internal Operations  DONE (tested iteration_304): 27 screens converted by codemod (/app/memory/admin_codemod_batch9.py)

## Inventory

| # | Folder | Tile | Route | Rep | Manager | Status | Notes |
|---|---|---|---|---|---|---|---|
| 1 | My Brand | Broadcast | /broadcast | | x | fixed | shared header, gold accent, real empty state with CTA |
| 2 | My Brand | Send a Blast (loose) | /broadcast/new | | x | fixed | shared header, all blue -> gold, button text black on gold |
| 3 | My Brand | Create a Card to Share | /settings/create-card?generic=true | | x | fixed | shared header, em dashes removed. Open: pre-existing console warning "Unexpected text node: ." (LOW) |
| 4 | My Brand | My Digital Card / My Landing Page | /my-profile | x | x | fixed | tiles now route to My Profile (personal). Store Profile got shared header + proper no-store empty state |
| 5 | My Brand | Share My Card | /quick-send/digitalcard | x | x | fixed | shared header, gold accent |
| 6 | My Brand | Get Reviews | /quick-send/review | x | x | fixed | same screen as #5 |
| 7 | My Brand | My Link Page | /settings/link-page | x | x | fixed | shared header, eyebrow sizing |
| 8 | My Brand | My Showcase | /showroom-manage | x | x | fixed | shared header, card borders, type scale |
| 9 | My Brand | Review Link | /settings/review-links | | x | fixed | BUG: stuck on Loading forever (effect ran before user loaded). Copy now really copies. Gold accent |
| 10 | My Brand | My Templates | /settings/templates | x (Settings) | x | fixed | removed stale 22px Jessi bar padding + 82px hardcoded top, shared header, gold |
| 11 | My Brand | Card Templates | /settings/card-templates | | x | fixed | shared header, real empty state |
| 12 | My Brand | Email Signature | /email-signature | | x | fixed | BUG: raw <img> tag (crashes native), now RN Image with initials fallback. Shared header. Blue button inside the preview is the email itself, intentional |
| 13 | My Brand | Share the App | /share-app | x | x | fixed | shared header |
| 14 | Today | Touchpoints | /(tabs)/touchpoints | x | x | fixed | shared header; phone-as-name now formatted; backend: "your new ." -> "your new ride", {{vehicle}} normalized, em dashes + "Hi 5550001234" stripped on the tasks API |
| 15 | Today | Calendar | /dates-calendar | x | x | fixed | shared header |
| 16 | Today | My Numbers / My Stats | /touchpoints/performance | x | x | fixed | shared header, titled My Numbers |
| 17 | Today | AI Follow-ups | /(tabs)/ai-outreach | x | x | fixed | shared header, gold count badge, empty-message fallback, purple -> gold |
| 18 | Loose | Inventory | /inventory | x | x | fixed | shared header; feed/CSV moved to a manager-only toolbar; light blue -> gold |
| 19 | Loose | Internet Leads | /leads | | x | fixed | shared header; purple -> gold pills |
| 20 | Settings | My Profile | /my-profile | x | x | fixed | cover hero kept by design; back testid + fallback, em dashes removed, link page pill off iOS blue |
| 21 | Settings | My VA | /settings/virtual-assistant | x | x | fixed | shared header, edit pencil in header, em dashes removed |
| 22 | Settings | Notifications | /settings/notifications | x | x | fixed | shared header, Save appears in header on change, blue -> gold |
| 23 | Settings | My Schedule | /settings/schedule | x | x | fixed | shared header, Save in header, em dashes removed |
| 24 | Settings | Security | /settings/security | x | x | fixed | shared header, blue -> gold, eyebrow sizing |
| 25 | Settings | Calendar Sync | /settings/calendar | | x | fixed | shared header (titled Calendar Sync), Connect gold, blue -> gold |
| 26 | Learning | Training Hub | /training-hub | x | x | ok | rebuilt June 2026 |
| 27 | Learning | Help Center | /help | x | x | ok | rebuilt June 2026 |
| 28 | Learning | Report a Bug | /report-bug | x | x | fixed | shared header (chevron instead of X), em dash removed, Done has fallback |
| 29 | Leads | Call Retries | /settings/call-retries | | x | fixed | shared header with Save pill |
| 30 | Leads | Lead Source Queue | /admin/internet-leads | | x | fixed | shared header (titled Lead Source Queue), gear in header, blue -> gold, Unknown -> phone/New lead, AI draft em dashes stripped server-side |
| 31 | Leads | Lead Source Config | /admin/lead-sources, /new, /[id] | | x | fixed | all three screens: shared header, every #007AFF -> gold, selection highlight gold |
| 32 | Leads | Connect Zapier / Make | /admin/lead-connect | | x | fixed | shared header |
| 33 | Leads | Team Availability | /admin/team-availability | | x | fixed | shared header with Updated subtitle + refresh; backend /schedule/team no longer returns Unknown names |
| 34 | Manage | Tags | /settings/tags | | x | fixed | shared header, stale Jessi/82px top padding removed, all #007AFF -> gold |
| 35 | Manage | Keyword Auto-Tags | /settings/keyword-rules | | x | fixed | shared header, indigo -> gold (add, scope pills, submit), em dashes removed |
| 36 | Manage | Keyword Search | /keyword-search | | x | fixed | shared header with rules link |
| 37 | Manage | Campaigns | /campaigns | | org_admin+ | fixed | shared header with reorder/dashboard/new, toggles + stats gold |
| 38 | Manage | Review Center | /settings/review-approvals | | x | fixed | shared header with subtitle |
| 39 | Manage | Showcase approvals | /settings/showcase-approvals | | x | fixed | shared header |
| 40 | Manage | Inventory Feed | /admin/inventory-feed | | x | fixed | shared header |
| 41 | My Tools | Ask Jessi | /jessie | | x | fixed | shared header (titled Ask Jessi, red cancel in header while listening), black mic on gold idle button, placeholder/hint -> theme, em dash removed |
| 42 | My Tools | Team Chat | /(tabs)/team | | x | fixed | file-local COLORS palette (blue accent, hardcoded #000/#1C1C1E) deleted -> theme colors; list + chat views on shared header (chat header = channel name + member subtitle, ellipsis in header); own bubbles gold with black text; core Image -> expo-image; type scale |
| 43 | Campaigns | Campaign Dashboard | /campaigns/dashboard | | x | fixed | shared header with gear; Ready-to-send card gold with black text; status/progress/create button blue -> gold; radius 16 + borders; eyebrow |
| 44 | Campaigns | Date Triggers | /settings/date-triggers | | x | fixed | shared header (also on loading state); tabs/delivery/save gold with black text; green toggles -> gold; radius 16 + borders; em dash removed |
| 45 | My Performance | Team Sales | /reports/team-performance | | x | fixed | shared header (titled Team Sales), month chevrons gold, rows radius 16 + border, empty state with Manage team CTA. Referrals blue / Repeats purple kept as category colors (match Home tiles) |
| 46 | My Performance | Team Tasks | /team-tasks | | x | fixed | shared header with open/overdue subtitle + refresh, managers-only state has Open Touchpoints CTA, filtered-empty has Show all |
| 47 | My Performance | Customer Engagement | /touchpoints/customer-performance | | x | fixed | shared header (titled Customer Engagement) + refresh, scope pills green -> gold outline, hardcoded grays -> theme, empty state Share my card CTA |
| 48 | My Performance | Leaderboard | /admin/leaderboard | | x | fixed | shared header, Send Rankings -> header mail icon, alert() -> showAlert, core Image -> expo-image (iOS avatars), radius 16, empty state CTA |
| 49 | My Performance | Activity Reports | /reports/activity | | x | fixed | shared header (titled Activity Reports) with schedule icon, yellow/blue/green pills + buttons -> gold, chart bars gold, eyebrow sections, empty state Show last 30 days |
| 50 | My Performance | Email Analytics | /settings/email-analytics | | x | fixed | shared header + refresh, removed 28px hardcoded top padding, BUG: range pills did nothing -> now filter client-side, Sent gold, eyebrows, empty CTA |
| 51 | My Performance | SEO Health | /seo-health | | x | fixed | rebuilt on shared components/health/HealthScoreScreen.tsx: theme colors (was hardcoded #000/#FFF), shared header + share icon, gold tabs/retry/guide/fix buttons; backend Good tier color blue -> gold |
| 52 | My Performance | GEO Health | /geo-health | | x | fixed | same shared screen. BUG: guide link went to /seo-guide -> /geo-guide. Backend tip strings em dashes removed, Building tier color -> gold |
| 53 | My Performance | VA Library | /admin/va-library | | admin | fixed | shared header with add icon, BUG: window.confirm on delete (crashes native) -> showAlert, Edit blue -> gold, default avatar color gold, em dashes removed |
| 54 | My Performance | System Logs | /admin/system-logs | | admin | fixed | shared header with red Clear text button; level colors kept |
| 55 | Set Up | Store Profile | /settings/store-profile | | x | fixed | already on shared header from #4; grays -> theme, default primary color gold, testids |
| 56 | Set Up | Brand Kit | /settings/brand-kit | | x | fixed | shared header with Save; BUG: logo upload was web-only (did nothing on the phone) -> expo-image-picker; 28px hardcoded top padding removed; blue -> gold; eyebrows |
| 57 | Set Up | Messaging Channels | /settings/messaging-channels | | x | fixed | shared header with enabled-count subtitle, loading/error state with Retry, radius 16, backend WhatsApp description em dash removed |
| 58 | Set Up | Phone Numbers | /admin/twilio-numbers | | x | ok | rebuilt June 2026 |
| 59 | Set Up | Team Members | /admin/users, /admin/users/[id] | | x | fixed | list: shared header (titled Team Members, N active) with add icon; BUG: Add User modal rendered nothing on native -> real Modal; stale JESSI_BAR padding removed; expo-image; gold pickers/checkbox; empty CTA. Detail: shared header with name subtitle, all blue -> gold, purple impersonate bg -> neutral outline, Cancel labels gray, pool number current state green |
| 60 | Set Up | Invite Team | /settings/invite-team | | x | fixed | shared header, 28px hardcoded top removed, org_admin color unified to orange, blue -> gold, SMS toggle gold, Create button black text, empty state |
| 61 | Set Up | Integrations | /settings/integrations | | x | fixed | shared header (also while loading), tabs/add/modal buttons/doc pills blue -> gold; HTTP method + event dot category colors kept |
| 62 | Admin | Onboarding Hub | /admin/onboarding-hub | | super/partner | fixed | header hoisted out of the ScrollView onto shared header with subtitle |
| 63 | Admin | Account Health | /admin/account-health | | super/partner | fixed | header hoisted; BUG: period 30d/90d active style was overridden (never showed) -> fixed; pills gold + black text |
| 64 | Admin | Admin Dashboard | /admin | | super | fixed | shared header with role subtitle; menu item icon palette kept |
| 65 | Admin | Organizations | /admin/organizations | | super/partner | fixed | search + add in header; create button black text; type toggle black text |
| 66 | Admin | Accounts | /admin/stores | | super/partner | fixed | search + add in header; empty-string org name no longer renders a bare text node (150 console errors) |
| 67 | Admin | Individuals / Pending Users | /admin/individuals, /admin/pending-users | | super | fixed | add icon in header; pending count subtitle; role user blue -> gold |
| 68 | Admin | iMOS Website Leads / Hot Leads | /admin/lead-tracking, /admin/hot-leads | | super | fixed | both were plain View/ScrollView roots (no safe area) -> SafeAreaView + shared header; refresh in header |
| 69 | Admin | Partner Portal / Agreements / White Label | /partner/dashboard, /admin/partner-agreements, /admin/white-label | | super | fixed | shared headers (agreements: both access-denied and main), add/toggle icons in header, em dashes removed |
| 70 | Admin | Billing / Forecast / Quotes / Discount Codes | /admin/billing, /admin/forecasting, /admin/quotes, /admin/create-quote, /admin/discount-codes | | super | fixed | shared headers; edges top added where missing; gold fills get black text; BUG: discount-codes getDiscountColor referenced undefined `colors` (would crash <10%) -> fixed |
| 71 | Admin | Shared Inboxes / Bulk Transfer / App Directory | /admin/shared-inboxes, /admin/bulk-transfer, /admin/app-directory | | super | fixed | shared headers; BUG: bulk-transfer fetched with user_id=undefined before auth hydrated (403) -> waits for user; page palette kept |
| 72 | Admin | Company Docs / Brand Assets | /admin/docs, /admin/brand-assets | | super | fixed | brand-assets: COLORS.accent blue -> gold, palette icon in header, em dashes removed. /admin/docs is a folder route, untouched |
| 73 | Admin | Error Reports / Bug Reports | /admin/error-reports, /admin/bug-reports | | super | fixed | shared headers with count subtitle + red trash; filter pills gold/black; copy button black text |
| 74 | Admin | SOPs / Manage Training / Training Report | /admin/sops, /admin/manage-training, /admin/training-reports | | super | fixed | sops: colors.primary fallback -> accent; manage-training: all 4 views (list, new track, edit track, edit lesson) on shared header with text actions; training default color gold |

## Log

- June 2026: inventory + standard written. Batch 1 (My Brand) done: shared `components/common/ScreenHeader.tsx` (gold chevron, centered 17/700 title, right action, canGoBack fallback to Tools), 13 screens converted, 2 real bugs fixed (Review Links infinite loading, Email Signature raw <img>), all #007AFF primary accents -> theme gold. Testing agent pass 95% (iteration_295), remaining LOW items fixed same turn except the create-card text-node console warning.
- June 2026: Batch 2 (Today + loose) done: 6 screens on ScreenHeader, template renderer fixes (vehicle fallback, phone-as-name), tasks API sanitizes em dashes and phone greetings. Testing agent 100% (iteration_297).
- June 2026: Batch 3 (Settings) done: 6 screens, testing agent 90% -> 2 minor items fixed same turn (my-profile back testid/fallback, link page pill color).
- June 2026: Batch 4 (Leads + Report a Bug) done: 8 screens, backend name fallback for team availability, lead draft em dashes stripped. Testing agent 93% -> 2 minor items fixed and verified.
- June 2026: Batch 5 (Manage) done: 7 screens, testing agent 99%, the one nit (indigo Create Rule button) fixed same turn.
- Still using stale JESSI_BAR_HEIGHT padding (bar is disabled): app/settings/persona.tsx. admin/users.tsx cleaned in Batch 8.
- June 2026: Batch 6 (My Performance) done: 9 screens, SEO/GEO collapsed into one shared HealthScoreScreen, 3 real bugs fixed (GEO guide route, VA delete window.confirm on native, Email Analytics dead range filter). Testing agent pass (iteration_301); GEO tip em dashes fixed same turn. yarn.lock regenerated: the committed one failed --frozen-lockfile.
- June 2026: Batch 7 (Campaigns + My Tools) done: 4 screens, testing agent pass (iteration_302). Tester flagged Team Sales Referrals column blue as a regression: NOT one, it is the intentional category color matching the Home Sold/Referrals/Repeats tiles. LESSON: never run `yarn install` while Metro is running; it rewrites node_modules and Metro's file map goes stale (web 500 'native-only module' error). Fix = rm -rf .metro-cache && supervisorctl restart frontend.
- June 2026: Batch 8 (Set Up) done: 7 screens, testing agent pass (iteration_303); the one nit (backend WhatsApp description em dash) fixed same turn. Real bugs fixed: Brand Kit logo upload did nothing on native; Team Members Add User modal never rendered on native. Only the super-admin `later` screens remain.
- June 2026: Batch 9 (Admin) done via codemod: 27 super-admin screens. Testing agent pass (iteration_304). LESSON from the codemod: converting `data-testid={`...${x}`}` with a `[^}]+` regex breaks on template literals; and keep-line numbers must be computed AFTER header replacement shifts lines. Fixed both same turn. Every screen in TOOLS_QA is now `fixed`.
