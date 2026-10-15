# TypeScript baseline (pre-existing technical debt)

- Command: `cd /app/frontend && npx tsc --noEmit`
- Recorded before the launch-compliance batch fixes: **248 errors in 54 files** (raw output: `/app/memory/ts_baseline_tsc.txt`).
- None of them sit on a line added or changed by the launch-compliance batch, and the new files (`components/compliance/*`, `app/consent/*`, `app/my-team.tsx`, `store/complianceStore.ts`) have 0 errors.
- Expo/Metro (Babel) strips types and does not block on these; fixing them is a separate technical-debt project. Do not loosen `tsconfig` to hide them.
- Check a change for NEW errors: run tsc, then compare file+line against this baseline and the lines in `git diff -U0`.

| File | Errors |
|---|---|
| `app/admin/training-reports.tsx` | 35 |
| `app/settings/create-card.tsx` | 33 |
| `app/` | 31 |
| `app/contact/[id].tsx` | 15 |
| `app/contact/new.tsx` | 13 |
| `app/admin/users.tsx` | 11 |
| `app/admin/lead-tracking.tsx` | 7 |
| `app/auth/login.tsx` | 6 |
| `app/auth/complete-profile.tsx` | 5 |
| `app/congrats/[cardId].tsx` | 5 |
| `app/jessie.tsx` | 5 |
| `app/settings/integrations.tsx` | 5 |
| `app/admin/organizations.tsx` | 4 |
| `app/auth/change-password.tsx` | 4 |
| `app/tasks/index.tsx` | 4 |
| `app/admin/index.tsx` | 3 |
| `app/admin/nda/create.tsx` | 3 |
| `app/admin/users/[id].tsx` | 3 |
| `app/my-account.tsx` | 3 |
| `app/seo-guide.tsx` | 3 |
| `app/thread/[id].tsx` | 3 |
| `store/authStore.ts` | 3 |
| `store/themeStore.ts` | 3 |
| `app/admin/brand-assets.tsx` | 2 |
| `app/admin/partner-billing.tsx` | 2 |
| `app/admin/sop/index.tsx` | 2 |
| `app/admin/stores.tsx` | 2 |
| `app/imos/pricing.tsx` | 2 |
| `app/quick-send/[action].tsx` | 2 |
| `app/search.tsx` | 2 |
| `app/showcase/[id].tsx` | 2 |
| `components/contact/FeedTab.tsx` | 2 |
| `contexts/ContactContext.tsx` | 2 |
| `app/_layout.tsx` | 1 |
| `app/admin/manage-team.tsx` | 1 |
| `app/admin/stores/[id].tsx` | 1 |
| `app/admin/white-label.tsx` | 1 |
| `app/campaigns/pending-send/[id].tsx` | 1 |
| `app/help.tsx` | 1 |
| `app/join/[code].tsx` | 1 |
| `app/l/[username].tsx` | 1 |
| `app/settings/persona.tsx` | 1 |
| `app/settings/review-approvals.tsx` | 1 |
| `app/settings/schedule.tsx` | 1 |
| `components/UniversalShareModal.tsx` | 1 |
| `components/VoicemailRecorder.tsx` | 1 |
| `components/appraisal/IdentityStep.tsx` | 1 |
| `components/appraisal/MileageStep.tsx` | 1 |
| `components/contact/HeroSection.tsx` | 1 |
| `components/notifications/LeadNotificationModal.tsx` | 1 |
| `components/scorecards/RepScores.tsx` | 1 |
| `hooks/usePushNotifications.ts` | 1 |
| `hooks/useWebSocket.ts` | 1 |
| `src/utils/calendar.ts` | 1 |
