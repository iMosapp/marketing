# Phase 1 Stage 3: Simplified Pilot Customer Onboarding — Founder Walkthrough

Built and tested in PREVIEW on Oct 11 2026. Nothing deployed. Legacy customers, Stripe logic and every existing screen are untouched: the whole stage is keyed on one runtime flag (`user.pilot`) that only members of a launch customer marked `customer.pilot` ever carry.

## What a pilot customer gets

**First login.** Activation link -> set password -> straight to the simplified Home. No slideshow, no Jessi welcome, no "finish your profile first" gate (`app/index.tsx`, `app/auth/login.tsx` both short-circuit on `pilot`).

**Home** (`components/home/PilotHome.tsx`)
- Header: avatar (opens the account sheet), greeting, QR button (card QR with scan stats), alerts bell.
- **GET SET UP** card: 5 steps, progress bar, the next step highlighted. Tapping a step takes them to the place that completes it. Steps auto-complete from real activity and the card collapses to "You're all set up" when all five are done.
  1. Complete your profile and photo -> `/my-account` (photo + name)
  2. Complete your digital business card -> `/my-account` (title + bio)
  3. Add your first contact -> `/contact/new` (any contact they create)
  4. Share your digital card -> share sheet (a text/email share with a recipient, or anyone scanning their QR)
  5. Record your first customer voice memo -> `/voice-memos` (any voice note)
- **EVERY DAY** tiles: Digital Card (hero), Contacts, Share, Voice Memo, Messages.
- "Have a question or hit a snag? **Send feedback**".

**Tabs:** Home · Contacts · Messages. Tasks and Phone are hidden from the bar (still routable by deep link, nothing deleted).

**More / avatar sheet:** My Profile & Card, Billing (owner only -> Stripe Customer Portal), Invite Your Team (owner only), Notifications, Settings, Send Feedback, Help & Support, Terms & Privacy, Sign out. No tool hub, no "All tools".

**Send Feedback** (`/report-bug`): Question / Problem / Suggestion, one text box, "Goes to the founder with your name and company". Reuses the bug-report pipeline: super admins get the email + push (push deep-links to the customer page for pilot users), the row is tagged `pilot`, `organization_name`, `screen`.

## What the founder gets

**Hub -> Customers** rows now carry a second line: `Setup 3/5 · active Oct 11 · 1 open issue · <first attention flag>` (or `Owner not signed in · no activity` until the owner activates).

**Customer page** (`/admin/customers/{org}`) gains, under the 5-step rail:
- **PROGRESS & ACTIVITY**: `Setup N/5` with the five step markers (Profile · Card · Contact · Share · Memo), "Active today / yesterday / N days ago", and plain-language attention flags: Payment failed · Payment link unpaid 3+ days · Billing exception expired / ends within a week · Owner has not activated (2+ days) · Owner not invited yet · Setup stalled at N/5 · No activity for a week · N open issues.
- **QUESTIONS & PROBLEMS**: the customer's feedback (category pill, who, screen, date, OPEN/RESOLVED, text), newest first; "Manage" opens the existing Bug Reports admin screen.

## How it is computed (no migrations)
- `routers/auth.py` `_apply_pilot_flags`: at login/refresh, if the user's org has `customer.pilot`, the session user gets `pilot`, `pilot_owner`, `pilot_billing_status`. Legacy orgs have no `customer` field so nothing changes for them.
- `services/pilot.py`: every step is derived from existing collections (`users`, `contacts`, `contact_events`, `card_scans`, `voice_notes`). The only write is the first-completion timestamp per step on `users.pilot_checklist.{step}`; stamps never move. `founder_view` adds `progress` (only once the owner has signed in), `last_activity` (login / contact event / voice memo), `issues_open`, `issues[]` (detail page only) and `attention[]` to every customer row.
- `routers/pilot.py`: `GET /api/pilot/checklist` (404 "Not a pilot account" for everyone else).
- `routers/bug_reports.py`: categories `bug | question | problem | suggestion | other` (anything else -> `other`), description capped at 4000 chars, account context attached server-side (never trusted from the client).

## Tests
- Backend: `cd /app/backend && set -a && . ./.env && . ../frontend/.env && set +a && python -m pytest tests/test_pilot_stage3.py tests/test_pilot_stage3_api_checks.py -q` -> 19 passed (creates + wipes "QA Pilot S3 *"). Regression Stage 1 + P0 + onboarding: 84 passed.
- Web (testing agent iteration_382): pilot owner lands on `/home`, checklist/tiles/tabs/share modal/QR/feedback/More/account sheet/settings all as specified; contact step auto-completed from a real contact; founder Hub rows + customer page verified; legacy qa-manager and forest unchanged (full Home, 5 tabs, full hub, Report a Bug). One cosmetic duplicate on the Hub row was fixed after the run.

## Demo in preview
- Pilot owner: **qa-pilot-owner-ui@invalid.imonsocial.test / PilotOwner123!** ("QA Pilot Owner Co", Paid, 0/5 done, one open Question in the founder view).
- Founder: forest@imosapp.com -> Hub -> Customers -> QA Pilot Owner Co.

## Known limits / later
- Steps 1 and 2 both point at My Profile (that is where photo, name, title and bio live); the card step completes once title + bio are filled.
- The share step counts a share with a recipient or a QR scan; just opening the QR screen does not count.
- Founder "Manage" opens the existing Bug Reports admin list (statuses open / in_progress / resolved are edited there).
- Not built: an in-app reply to feedback (founder answers by text/email today), per-step nudges, pilot analytics.

## Ship (when you say GO; not before)
Save to GitHub -> Deploy -> run `cd frontend && git pull && yarn install && eas update --branch production --message "$(git log -1 --pretty=%s)"`.
