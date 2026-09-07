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
3. Settings  <- next (My Profile, My VA, Notifications, Schedule, Templates, Security, Calendar Sync)
4. Learning (Training Hub, Help Center, Report a Bug)
5. Leads (Internet Leads, Call Retries, Lead Source Queue, Lead Source Config, Connect Zapier / Make, Team Availability)
6. Manage (Tags, Keyword Auto-Tags, Keyword Search, Campaigns, Review Center, Showcase approvals, Inventory Feed, Review Links)
7. My Performance (My Stats, Team Sales, Team Tasks, Customer Engagement, Leaderboard, Activity Reports, Email Analytics, SEO/GEO Health, VA Library)
8. Campaigns + My Tools (Campaign Dashboard, Date Triggers, Ask Jessi, Team Chat)
9. Set Up (Store Profile, Brand Kit, Messaging Channels, Phone Numbers, Team Members, Invite Team, Integrations)
10. Admin / Internal Operations (super admin only, `later`)

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
| 20 | Settings | My Profile | /my-profile | x | | todo | |
| 21 | Settings | My VA | /settings/virtual-assistant | x | x | todo | |
| 22 | Settings | Notifications | /settings/notifications | x | x | todo | |
| 23 | Settings | My Schedule | /settings/schedule | x | x | todo | |
| 24 | Settings | Security | /settings/security | x | x | todo | |
| 25 | Settings | Calendar Sync | /settings/calendar | | x | todo | |
| 26 | Learning | Training Hub | /training-hub | x | x | ok | rebuilt June 2026 |
| 27 | Learning | Help Center | /help | x | x | ok | rebuilt June 2026 |
| 28 | Learning | Report a Bug | /report-bug | x | x | todo | |
| 29 | Leads | Call Retries | /settings/call-retries | | x | todo | |
| 30 | Leads | Lead Source Queue | /admin/internet-leads | | x | todo | |
| 31 | Leads | Lead Source Config | /admin/lead-sources | | x | todo | |
| 32 | Leads | Connect Zapier / Make | /admin/lead-connect | | x | todo | |
| 33 | Leads | Team Availability | /admin/team-availability | | x | todo | |
| 34 | Manage | Tags | /settings/tags | | x | todo | |
| 35 | Manage | Keyword Auto-Tags | /settings/keyword-rules | | x | todo | |
| 36 | Manage | Keyword Search | /keyword-search | | x | todo | |
| 37 | Manage | Campaigns | /campaigns | | org_admin+ | todo | |
| 38 | Manage | Review Center | /settings/review-approvals | | x | todo | |
| 39 | Manage | Showcase approvals | /settings/showcase-approvals | | x | todo | |
| 40 | Manage | Inventory Feed | /admin/inventory-feed | | x | todo | |
| 41 | My Tools | Ask Jessi | /jessie | | x | todo | |
| 42 | My Tools | Team Chat | /(tabs)/team | | x | todo | |
| 43 | Campaigns | Campaign Dashboard | /campaigns/dashboard | | x | todo | |
| 44 | Campaigns | Date Triggers | /settings/date-triggers | | x | todo | |
| 45 | My Performance | Team Sales | /reports/team-performance | | x | todo | |
| 46 | My Performance | Team Tasks | /team-tasks | | x | todo | |
| 47 | My Performance | Customer Engagement | /touchpoints/customer-performance | | x | todo | |
| 48 | My Performance | Leaderboard | /admin/leaderboard | | x | todo | |
| 49 | My Performance | Activity Reports | /reports/activity | | x | todo | |
| 50 | My Performance | Email Analytics | /settings/email-analytics | | x | todo | |
| 51 | My Performance | SEO Health | /seo-health | | x | todo | |
| 52 | My Performance | GEO Health | /geo-health | | x | todo | |
| 53 | My Performance | VA Library | /admin/va-library | | admin | todo | |
| 54 | My Performance | System Logs | /admin/system-logs | | admin | later | |
| 55 | Set Up | Store Profile | /settings/store-profile | | x | todo | shared with #4 |
| 56 | Set Up | Brand Kit | /settings/brand-kit | | x | todo | |
| 57 | Set Up | Messaging Channels | /settings/messaging-channels | | x | todo | |
| 58 | Set Up | Phone Numbers | /admin/twilio-numbers | | x | ok | rebuilt June 2026 |
| 59 | Set Up | Team Members | /admin/users, /admin/users/[id] | | x | todo | |
| 60 | Set Up | Invite Team | /settings/invite-team | | x | todo | |
| 61 | Set Up | Integrations | /settings/integrations | | x | todo | |
| 62 | Admin | Onboarding Hub | /admin/onboarding-hub | | super/partner | later | |
| 63 | Admin | Account Health | /admin/account-health | | super/partner | later | |
| 64 | Admin | Admin Dashboard | /admin | | super | later | |
| 65 | Admin | Organizations | /admin/organizations | | super/partner | later | |
| 66 | Admin | Accounts | /admin/stores | | super/partner | later | |
| 67 | Admin | Individuals / Pending Users | /admin/individuals, /admin/pending-users | | super | later | |
| 68 | Admin | iMOS Website Leads / Hot Leads | /admin/lead-tracking, /admin/hot-leads | | super | later | |
| 69 | Admin | Partner Portal / Agreements / White Label | /partner/dashboard, /admin/partner-agreements, /admin/white-label | | super | later | |
| 70 | Admin | Billing / Forecast / Quotes / Discount Codes | /admin/billing, /admin/forecasting, /admin/quotes, /admin/create-quote, /admin/discount-codes | | super | later | |
| 71 | Admin | Shared Inboxes / Bulk Transfer / App Directory | /admin/shared-inboxes, /admin/bulk-transfer, /admin/app-directory | | super | later | |
| 72 | Admin | Company Docs / Brand Assets | /admin/docs, /admin/brand-assets | | super | later | |
| 73 | Admin | Error Reports / Bug Reports | /admin/error-reports, /admin/bug-reports | | super | later | |
| 74 | Admin | SOPs / Manage Training / Training Report | /admin/sops, /admin/manage-training, /admin/training-reports | | super | later | |

## Log

- June 2026: inventory + standard written. Batch 1 (My Brand) done: shared `components/common/ScreenHeader.tsx` (gold chevron, centered 17/700 title, right action, canGoBack fallback to Tools), 13 screens converted, 2 real bugs fixed (Review Links infinite loading, Email Signature raw <img>), all #007AFF primary accents -> theme gold. Testing agent pass 95% (iteration_295), remaining LOW items fixed same turn except the create-card text-node console warning.
- June 2026: Batch 2 (Today + loose) done: 6 screens on ScreenHeader, template renderer fixes (vehicle fallback, phone-as-name), tasks API sanitizes em dashes and phone greetings. Testing agent 100% (iteration_297).
- Still using stale JESSI_BAR_HEIGHT padding (bar is disabled): app/settings/tags.tsx, app/settings/persona.tsx, app/admin/users.tsx. Remove in their batches.
