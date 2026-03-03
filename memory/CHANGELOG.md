# CHANGELOG — iMOs App

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
