# i'M On Social — Complete Operations Manual

**Version:** August 2026 (v6) · Replaces v5.0 (March 2026)
**Audience:** Owner / admins / future contractors

---

## 1. Environments

| | Preview (dev) | Production (live) |
|---|---|---|
| Where | Emergent preview pod | `app.imonsocial.com` (imos-deploy-prep.emergent.host) |
| Backend | FastAPI + MongoDB (preview DB) | FastAPI + MongoDB (production DB, separate data) |
| Phones | n/a | iOS App Store + Android internal track + Web PWA |
| Who changes it | The build agent | Deploy button + `eas update` only |

**Rule:** bugs are fixed in Preview first, then shipped. Always state whether an issue is on Preview or Production when reporting.

## 2. Release Workflow (after every update)

1. **Save to GitHub** (button in Emergent chat)
2. **Deploy** (button in Emergent) → ships the backend + web
3. On your Mac: `cd ~/imos && git pull`
4. `cd frontend` then:
   ```
   eas update --branch production --message "what changed"
   ```
   (Your local `frontend/.env` holds the production URLs — it is gitignored and never overwritten by git pull.)

- **Backend-only change** → steps 1–2 are enough.
- **App UI change** → all 4 steps. Phones pick it up after fully closing + reopening the app.
- **Native change** (new permission, native package, icon) → requires a full `eas build`; the agent will call this out explicitly when needed.

## 3. Scheduled Automations (21 jobs)

| Job | Schedule (UTC) | What it does |
|---|---|---|
| `ai_reply_queue_processor` | continuous interval | Sends/queues Jessi AI replies |
| `ai_reply_escalation_processor` | interval | Escalates unsure AI replies to the rep |
| `campaign_step_processor` | every 5 min | Sends due campaign steps (quiet hours → defers to 9 AM local) |
| `internet_lead_processor` | interval | Processes queued internet-lead first messages |
| `scheduled_broadcast_processor` | interval | Fires scheduled broadcasts |
| `sold_delivery_processor` | interval | Sends sold-workflow delivery texts |
| `daily_date_triggers` | daily 08:00 | Birthday/anniversary/sold-date engine: opt-in tag gate, day-of campaign enrollment, same-day double-send guard, anniversary card w/ car photo |
| `date_preview_digest` | hourly :05 | At each rep's 8 AM local: SMS + notification listing today's date sends |
| `morning_push_digest` | daily 14:00 | Push digest of today's touchpoints |
| `daily_lifecycle_scan` | daily | Long-term campaign lifecycle scan |
| `daily_photo_reminder` | daily 15:00 | Push to store admins if in-stock vehicles are missing photos |
| `daily_recent_tag_expiry` | daily | Expires "recent" tags |
| `daily_report_delivery` | daily | Emails daily reports |
| `daily_system_tasks` | daily | Housekeeping |
| `silence_followup_daily` | daily | Nudges silent conversations |
| `weekly_bug_digest` | Mon 15:00 | Emails unresolved bug reports |
| `weekly_power_rankings` | weekly | Leaderboard rankings |
| `monthly_roi_email` | 1st, 14:30 | Per-store lead-source ROI email (cost, leads, replied, sold, $/lead, $/sale) — recipient set in Admin → Store → AI & Security |
| `monthly_health_reports` | monthly | Account health reports |
| `monthly_partner_invoices` | monthly | Generates partner invoices |
| `memory_gc` | interval | Cache/memory cleanup |

Health check: `GET /api/health/deep` → shows DB + scheduler job count.

## 4. Startup Self-Heals (run automatically on every deploy)
- **Twilio webhook verification** — re-points numbers at the right URLs.
- **Voice-note relink** — repairs any note with a missing audio link.
- **Webm → m4a conversion** — converts web-recorded memos so iPhones can play them.
- **Date opt-in reset** (one-time, Aug 2026) — wiped auto-applied Birthday/Anniversary tags and cancelled the old save-time enrollments.
- **Doc sync** — pushes `/app/docs/*.md` into Admin → Docs when their content changes.
- **Phone consolidation** — merges duplicate contacts by phone.

## 5. Daily / Weekly / Monthly Operating Rhythm

**Daily (rep):** answer the 8 AM date-send digest (opt people out via Manage Recipients if needed) · work the Leads dashboard (speed-to-lead — under 5 minutes wins) · clear touchpoints · check inbox escalations.

**Daily (admin):** watch the missing-photo banner in Inventory · review new-lead pushes · check Bug Reports.

**Weekly:** Monday bug digest email · review Speed tab leaderboard · leaderboard/power rankings.

**Monthly:** 1st-of-month ROI email lands — adjust lead-source spend; enter next month's costs in Admin → Lead Sources · review partner invoices.

## 6. Admin How-Tos

- **Lead sources:** Admin → Lead Sources → New → copy the ADF/webhook or email-intake URL to the provider; set `monthly_cost` for ROI math.
- **Date recipients (birthday/anniversary):** Settings → Date Triggers → Manage Recipients → search/filter → select → Turn ON/OFF. Or per-contact: Contact → Details → Important Dates toggles. **Nothing sends without the tag.**
- **Intent sensitivity:** Admin → Store → AI & Security → slider + preview of which past conversations would flag.
- **Login lockout:** same screen — attempts (3–50) and lockout minutes (1–1440).
- **ROI report email:** same screen — blank = owner default.
- **Inventory:** Inventory screen → add/edit vehicles + photos; webhook endpoints exist for HomeNet/vAuto when credentials arrive.
- **Twilio numbers:** Admin → Twilio Numbers (assign/release; released numbers return to pool).
- **Internal docs:** Admin → Docs. PRD / Ops Manual / App Scope sync from the repo on deploy; edit the repo files to change them.

## 7. Click-to-Call Flow (how calling works)
1. Rep taps a contact → number stages on the keypad → green button starts the call.
2. Twilio rings the **rep's cell** from their business number.
3. Rep answers and hears "Calling {name}. **Press 1 to connect**, or hang up to cancel."
4. Only after pressing 1 is the customer dialed (caller ID = rep's business number, recorded from answer).
5. In the app: live status + red hang-up button (kills both legs). Voicemail pickup or hang-up = customer never dialed.

## 8. Troubleshooting

| Symptom | Check |
|---|---|
| Voice memo won't play | Fixed Aug 2026 (empty audio links + webm). Self-heals on deploy. New failures: check `/api/images/{audio_path}` returns 200/206. |
| Birthday text went out unexpectedly | Should be impossible post-Aug 2026: verify contact does NOT carry the `Birthday`/`Anniversary` tag; check `date_send_guard` collection. |
| Duplicate sends | Same-day guard + single-campaign rule prevents this; if seen, capture the two message SIDs + timestamps. |
| Lead didn't arrive | Check source webhook URL, then `/api/leads` + backend logs for the parse error. |
| Call never rang customer | Expected if rep didn't press 1. Otherwise check Twilio call logs for the parent CallSid. |
| App UI not updating after eas update | Fully close and reopen the app twice (first open downloads, second runs). |
| Preview UI stale for the agent | `sudo supervisorctl restart frontend` (Metro cache). |

## 9. Environment Variables (names only — values live in `.env`, never in git)
`MONGO_URL, DB_NAME, JWT_SECRET, CORS_ORIGINS, RESEND_API_KEY, SENDER_EMAIL, EMERGENT_LLM_KEY, TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER, TWILIO_MESSAGING_SERVICE_SID, APP_URL, PUBLIC_FACING_URL, VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY, VAPID_MAILTO, ADMIN_EMAIL, SALES_EMAIL, STRIPE_SECRET_KEY, LOGIN_MAX_FAILS, LOGIN_LOCKOUT_MINUTES, RESET_IP_MAX, RESET_IP_WINDOW_MIN`

⚠️ **Open security task:** rotate all production secrets before giving any contractor codebase access.

## 10. Support & Escalation
- In-app: Report a Bug (pushes admins instantly; Monday digest email).
- Platform/deploy issues (domains, env, hosting): Emergent Support.
- Twilio delivery issues: Twilio console logs by CallSid/MessageSid.

---
*Source of truth: `/app/docs/OPERATIONS_MANUAL.md` — synced to Admin → Docs automatically on every deploy.*
