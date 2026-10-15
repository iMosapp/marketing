# I'm On Social — Commercial Launch Master Audit (READ-ONLY) — Oct 15 2026

Nothing was changed for this audit: no code edits, no deploys or republishing, no secret changes, no payments, and no production writes. The only writes were preview test suites creating and cleaning up their own QA records. Production was queried read-only through the deployer agent, for metadata only.

**How sure each finding is**
| Tag | Meaning |
|---|---|
| **[V-PROD]** | Verified in production today: deployer read-only queries, or public GETs of `/api/health`, the web root and the web JS bundle |
| **[V-CODE]** | Verified by reading the code at HEAD `77fb36372` |
| **[V-TEST]** | Verified by a test run today in preview |
| **[PRIOR]** | Taken from an earlier dated report in `/app/memory` and not re-measured today |
| **[ASSUMPTION]** | Inference; not verified |

---

## 1. Executive summary (plain English)
- **Production is up and healthy now.**
  - Both servers are Ready on build `2026-10-14.mms-stage1` [V-PROD].
  - Server `zzdlg` still fails health checks under load at times (restarts=3; a timeout was seen again at 02:53 UTC) [V-PROD].
  - The 502/520 problem is caused by the platform's health check, which only tests the front proxy. Our faster-startup build (preview) makes it much less likely, but only Emergent can remove it.
- **Two servers can double-send today.** Both production servers run every scheduled job [V-PROD]. Campaign steps, AI replies, date/birthday triggers and digests are already protected [V-CODE]. Scheduled broadcasts, customer appointment reminders and most other jobs are not [V-CODE].
  - Production send volume is near zero today: every campaign tick in the observed window claimed 0 sends [V-PROD]. So no duplicates have been measured yet, but the risk grows with the first real dealership.
  - The preview lease build closes this gap. It is tested and not deployed.
- **Live billing secrets are in place, but live mode is not yet confirmed.** `STRIPE_BILLING_SECRET_KEY` and `STRIPE_BILLING_WEBHOOK_SECRET` are in production [V-PROD]. Whether the key is a live key can only be confirmed by you on the super admin screen; the tools can't read secret values.
- **Several launch features are built in preview but not connected:**
  - Dealership sender compliance (`sender_policy.py`) is connected to no send path [V-CODE].
  - The Jessi Mini double-greeting fix (`miniSession.ts`) isn't used by the live voice hook, so the bug is still live [V-CODE].
  - The manager "My Team" service (`team_view.py`) has no endpoint and no screen [V-CODE].
- **Jessi Vision:**
  - Jessi already reads business cards, documents and PDFs filed on a contact, and reads VIN and odometer photos during appraisals. These use a real vision model (`gpt-5.4`) and are live [V-CODE + V-PROD bundle].
  - Jessi does **not** look at MMS photos in conversations, and the chat with Jessi takes no pictures [V-CODE].
  - Image findings do not feed relationship intelligence automatically.
- **Smart call classification doesn't exist.** Scorecards grade every transcribed call of 30 s or more that isn't voicemail or no-answer, using the rep's department card. "No conversation" calls are still graded and count in averages [V-CODE].
- **Canceled or unpaid subscriptions don't lose access automatically.** You are alerted and decide by hand [V-CODE].
- **Minimum to sell now:** deploy the reliability build, confirm Stripe is live, and keep dealership texting on numbers you assign and verify (or connect sender policy, about 1 hour of work). Keep Jessi Mini off for customers until the fix ships via OTA. Vision, call classification and My Team can follow.

## 2. Production GO / NO-GO
| Question | Verdict |
|---|---|
| Is production stable enough to keep running today? | **GO**: healthy, 0 sends pending, all integrity indexes present |
| Deploy the preview reliability build? | **GO, conditional** on the §5D checklist, a low-traffic window, and you confirming the live Stripe key afterwards. Risks are in §6 |
| Take card payments from a dealership today? | **NO-GO until** you confirm live mode (`billing_config.mode == live`) and the controlled $100 test passes. Interim options: Founding Partner Pilot, a billing exception, or a Dashboard Payment Link |
| Let a dealership's reps text customers today? | **CONDITIONAL**: only from numbers you assign and verify (registered and attached to the dealer's own Messaging Service). Otherwise **NO-GO** until sender policy is connected (§5 Phase D, D2) |
| Offer Jessi Mini voice to customers? | **NO-GO** until the greeting fix is connected and shipped by OTA (5 of the last 10 production Mini sessions double-greeted [PRIOR Oct 15]) |

---

## 3. PART 1 — Final production reliability review

### A. Database index conflicts
**Method.**
- Ran every `create_index` call in the startup code (79 specs) against a fake database to record each spec. Then compared each spec with the real index catalogue in preview (read-only), and with the production catalogue from the deployer.
- Also checked the production boot logs for the last 24 h.

| # | Collection.index | Error | Where | Root cause | Impact |
|---|---|---|---|---|---|
| 1 | `short_urls.short_code_1` | `IndexKeySpecsConflict` (code 86): the requested index is not unique, but the existing one is `unique:true` | **Prod** (boots 01:32:19 and 02:05:06) and preview | `server.py` `_db_housekeeping`: `db.short_urls.create_index([("short_code",1)])` is declared without `unique=True`, while the live index is unique | Uniqueness is **kept** (the stronger existing index stays). Side effect below |
| 2 | `link_pages.user_id_1` | Same name, different options: requested `unique+sparse`, existing `unique` only | **Preview only**. Prod has `unique+sparse` [V-PROD] | Preview data drift | None in prod |
| 3 | `messages._id_1` | My static check flagged it; Mongo treats `createIndex({_id:1})` as a no-op | Both | Harmless | None |

**The side effect that matters.**
- All 70+ indexes are created in one `asyncio.gather(...)`. The first error stops that step and jumps to `except: "Index creation skipped"`, so the **sequential** steps after the gather never run.
- Indexes that have never been created in production [V-PROD]:
  - **`inbound_message_dedup.message_sid` UNIQUE**, plus its 1-hour TTL. The collection has only `_id_`, with 314 docs.
  - The `notifications.created_at` TTL (90 days), `short_url_clicks.clicked_at` TTL (1 year) and `contact_events.timestamp` TTL (2 years).
- The other gather items do get created, because gather doesn't cancel its siblings. Production has every integrity index [V-PROD]:
  - `users.email` unique+sparse
  - `contact_facts.fingerprint` unique (relationship intelligence)
  - `contact_photos.contact_id` unique
  - `tasks.idempotency_key` unique and partial
  - `link_pages.user_id` unique+sparse
- Because gather reports only the *first* error, more than one conflict could hide behind it. The static comparison found no others in production.

**Impact by area**
| Area | Impact |
|---|---|
| Performance | No impact found; all query indexes are present |
| Uniqueness / data integrity | One gap: inbound Twilio retry dedup isn't enforced by the database. The atomic upsert in `routers/twilio_webhooks.py:205` still blocks sequential retries; only two truly simultaneous retries landing on both servers could both get through. **LOW risk.** |
| Tenant isolation | None; no index is involved |
| Data retention | The three TTLs have never been active, so notifications and history are kept forever. Enabling them is a data-deletion decision, not just an index fix. |

**Data-deletion warning.** Turning the TTLs on would immediately delete notifications older than 90 days, clicks older than 1 year and contact events older than 2 years. Production has 4,280 contact_events and 2,948 notifications [V-PROD]; age counts weren't possible with the read-only tool. Contact events feed leaderboards, relationship history and intelligence. **Do not enable the contact_events TTL without a retention decision.**

**Smallest safe correction (not implemented). About 20–30 min of Emergent time plus one deploy.**
1. Declare `short_urls` `short_code` with `unique=True`, matching the live index. This is a no-op on the database.
2. Use `asyncio.gather(..., return_exceptions=True)` and log each failed spec with its collection and name, so one conflict can't hide others or skip the later steps.
3. Create the `inbound_message_dedup` indexes in their own step.
   - Run a duplicate check first (aggregation in Compass or mongosh). The unique build fails if duplicates exist.
   - The 1-hour TTL would then remove the 314 old dedup rows, which is harmless.
4. Leave the three retention TTLs out until you decide how long to keep data (recommended: none on `contact_events`).
5. Optional: add a TTL for `voice_upload_chunks` (0 docs in prod, none declared today).

### B. Cross-server restart safety

**1. Interruption markers (unchanged from production, still a risk)** [V-CODE]
- On every boot, one of these runs on whichever server is starting:
  - `widget_crawl.fail_interrupted` sets every `running` crawl to `failed`.
  - `leadership.orchestrator.fail_interrupted(all_running=True)` sets every running roundtable to `interrupted`.
  - `appraisals.inspection.recover_interrupted` sets every `queued/processing` AI inspection to `failed` and resets the appraisal.
- **None of them check which server owns the work.** A restart of one server (for example `zzdlg` stuck restarting, or a new server starting during a rollout) can fail work the healthy server is still doing.
- User-visible effect: a rep sees "Interrupted by a server restart — tap analyze to retry" on an inspection that was actually running. No SMS, email or campaign path is affected.
- **Fix:** stamp in-progress records with an owner and heartbeat; at boot, fail only records whose heartbeat is stale. Effort M, about 45–60 min.

**2. Scheduler leases (preview build `services/job_lease.py`)** [V-CODE + V-TEST]
- **Ownership:** each shared job, on each run, claims `job_leases[_id=job]` atomically (an upsert with an expiry filter; `DuplicateKeyError` means another server has it).
- **Expiry and takeover:** a running claim lasts 90 s and renews every 30 s. A dead server releases within 90 s, and the next run on any server takes over.
- **Retries and missed runs:**
  - After a run, the lease is held for 0.8 × the interval (cron jobs: at most 5 min), so the other server skips that period.
  - A failed run does not retry until the next run; each job's own retry logic is unchanged.
- **Duplicate-send protection:**
  - Two servers can't run the same job at the same time unless Mongo is unreachable. In that case the guard fails open, which is today's behaviour.
  - `JOB_LEASES=off` is the kill switch.
- **Tests:** 12/12 [V-TEST], including two simulated servers running the real 56 jobs, with takeover after one stops.

**Remaining risks once the leases are deployed**
1. **Rollout overlap.** For the minute or two while old (no-lease) and new servers both run, the old servers still run every job. This is no worse than today.
2. **Fail-open on a Mongo outage.**
3. **A job that blocks the event loop for more than 90 s** can lose its lease mid-run.
4. **Request-time sends** (webhooks, manual sends, `asyncio.create_task` work) run once on whichever server got the request. The leases don't affect them, and they're single by nature.
5. **One-off scheduled jobs** (date triggers) aren't added after startup, so there's nothing extra to protect [V-CODE: all 56 `add_job` calls are inside `start_scheduler`].

**Per-job protection without leases (what production has today)**

These ratings come from reading the code; the jobs marked spot-checked were confirmed line by line today.

| Rating | Jobs |
|---|---|
| **SAFE** | `campaign_step_processor` (atomic claim) and `ai_reply_queue_processor` (atomic `find_one_and_update` claim plus stale-duplicate cancel), spot-checked `routers/ai_reply.py:1091`. Also `daily_date_triggers`, `date_preview_digest`, `weekly_keyword_digest` and memo nudges: a deterministic `_id` upsert in `date_send_guard`, unique by `_id` (`scheduler.py:443,775,882`; `services/memo_reminder.py:34`). Spot-checked; this corrects the static inventory in `SCHEDULER_OWNERSHIP_DESIGN.md`, which listed these as NONE. |
| **WEAK** (check-then-act; both servers can pass the check inside one window) | `scheduled_broadcast_processor` (`scheduler.py:2632`: `find status=scheduled`, then build recipients) and `customer_appointment_reminders` (`services/calendar_invite.py`: sends, then stamps `customer_reminder_sent_at`) — both spot-checked. Most digests and reports, push summaries, `lead_call_engine` (outbound calls), and the jobs listed as NONE/WEAK in the design doc. |

### C. Deployment inventory

**Live build** [V-PROD]
- Image `imos-deploy-prep:bf277e6b…`, built 2026-10-14 23:26:12–23:36:26 UTC. `/api/health` reports `2026-10-14.mms-stage1`.
- The source commit is not recorded in the build logs. The build started 4 minutes after `aa33bda82` (23:22, the build-tag bump) and before `2eddd0ad3` (23:27, which changed only `.emergent/emergent.yml`). The live code equals `aa33bda82` [V-PROD timing + git].
- The production web bundle contains the MMS Stage 1 UI ("Mark Handled", "Couldn't load this photo · Tap to retry") [V-PROD bundle grep].
- Native app OTA status **cannot be verified** from here. Run `eas update:list --branch production` on your Mac.

**What a full deploy would bundle today** (`git diff 2eddd0ad3..HEAD`: 24 files, +2015 / −270)

| Group | Files | Effect in production |
|---|---|---|
| Startup reliability + leases (tested) | `server.py`, `scheduler.py`, `services/job_lease.py` (new), `routers/voice.py`, `routers/calendar.py`, `services/jessie_service.py`, `services/voice_intel.py`, `services/ai_outreach_service.py`, `services/compliance.py`, `services/print_card.py`, `services/appraisals/frames.py` | **Active.** Faster boot; background index build and migrations; one server per job run; boot clean-ups once per rollout |
| Unwired launch modules | `services/sender_policy.py`, `services/team_view.py` | **Inert.** Not imported by any router or send path [V-CODE] |
| Frontend | `hooks/miniSession.ts`, `scripts/check-mini-opening.ts` | **Inert.** Not imported by any component. The web bundle is functionally unchanged; native apps unchanged until an OTA |
| Tests and tools | `tests/test_job_lease.py`, `test_startup_reliability_regression.py`, `route_table_snapshot.py`, `startup_benchmark.py`, `run_regression.sh`, `test_sender_policy.py`, `test_send_paths_guarded.py`, `test_team_view.py`, `acceptance_first_dealer.py` | Not used at runtime |
| New env keys | none (`JOB_LEASES` is optional, unset means on) | — |

**How live Stripe secrets are preserved** [V-PROD per deployer, Oct 15]
- `STRIPE_BILLING_SECRET_KEY` and `STRIPE_BILLING_WEBHOOK_SECRET` are saved in the Deployment panel's Secrets. On deploy, saved values override the test values in the repo's `backend/.env`.
- The platform-managed `STRIPE_MODE` / `STRIPE_*` (Payments tab) are regenerated on each deploy. The subscription billing code never reads them.
- A deploy does not touch the saved secrets.
- **Verify after deploy:**
  - Super admin → Customers → `billing_config.mode == live` and `conversion_enabled == true`.
  - `POST /api/billing/stripe/webhook` without a signature returns 400.

**Rollback risks**
1. **Unknown: does Rollback restore an older secret snapshot?** Emergent support could not confirm it. If it did, the live billing keys would revert to test, and live webhooks would fail their signature check. Mitigation: after any rollback, re-check `billing_config.mode`, and keep the live key and webhook secret where you can re-save them.
2. **Every rollback is a republish**, so it can cause the 26–60 s 502 window caused by the platform's health check.
3. **`job_leases` is additive.** Old code ignores it, so rollback is data-safe.
4. **Changes that are hard to undo:** the boot migrations are idempotent and were already running in production. Nothing new is destructive.

**Actual test results today (preview, one pytest process per module)**
| Suite | Result | Notes |
|---|---|---|
| test_job_lease | 12/12 pass | leases, takeover, two-server simulation |
| test_startup_reliability_regression | 9/9 pass | |
| test_sender_policy | 26 pass, 1 skip | Skip: the `OWNER_EMAIL` user has no org in preview. The earlier "future belongs to a different loop" error only happens when several modules share one process; it doesn't occur alone |
| test_send_paths_guarded | 1 **xfail** (expected) | Marked xfail until sender policy is connected: shows the send paths are **not** guarded yet |
| test_team_view | 6/6 pass | module only, no endpoint |
| test_mms_stage1 | 7/7 pass | |
| test_billing_stage2 | 10/11 | 1 stale static assertion (`STRIPE_BILLING` text in `server.py`), existing before this work |
| test_pilot_program | 10/10 | |
| test_subscriptions_quotes | 26/26 | |
| test_twilio_tenant | 7/7 | |
| test_message_delivery | 7/7 | |
| test_live_voice | 11/11 | |
| test_voice_controls | 7/7 | |
| test_jessi_onboarding | 3/3 | |
| test_security_hotfix4c | 13/13 | |
| test_appraisals_mvp2 / mvp3 / mvp4 / mvp5 | 15/15, 16/16, 7/7, 9/9 | |
| test_appraisals_mvp1 | 1/2 | QA data build-up: the Sarah fixture has 96 test vehicles and the list is capped at 50 (`services/appraisals/core.py:188`). Not a code defect [ASSUMPTION, strongly indicated] |
| test_files_voice_iter359 | 2/3 | Stale expectation: voice cap 900 s, now 3600 s |
| test_scorecards_api | 19/24 | 5 need `seed_scorecard_demo.py` first (not run: it would add demo data) |
| test_store_independent_mms | 6/19 | 13 stale: old `X-User-ID` header auth, now 401 |
| test_performance_scorecard_tiles | 0/15 | 15 stale: same header-auth 401s |
| test_partner_billing_access | 0/14 | 14 stale: same header-auth 401s |
| frontend `scripts/check-mini-opening.ts` | 13/13 PASS | The fix logic works; it is not connected to the live hook |
| Testing agent iteration_389 (Oct 15) | 100% on in-scope suites | startup + lease regression |

**Totals:** 229 passed, 50 failed, 1 skipped, 1 xfailed.
- 42 of the failures are the old header-auth model (401).
- 5 need the scorecard seed first.
- 3 are stale expectations or QA data build-up.
- **No failure points at a product regression.**

### D. Deployment verification checklist (run only after an approved deploy)
1. **Before deploying:**
   - Low-traffic window.
   - You have the live Stripe key and webhook secret on hand.
   - No secret edits in the same window (each save is its own rollout).
2. **Both servers healthy:** deployer read-only check: 2/2 Ready, restart counts, no CrashLoop within 15 min.
3. **Cold start:** in production logs, compare container start → "I'm On Social API v2.0 started" per server. Target ≤ 30 s, against about 61 s before.
4. **API availability:**
   - At least 50 `/api/health` checks on both hosts, 0 non-200.
   - 15 min monitor (every 4 s) for 502/520.
   - Build string = the new build tag.
5. **Scheduler ownership:**
   - Log line `[JobLease] 55 shared jobs run on one replica per tick` on each server.
   - `job_leases` docs appear: `lead_call_engine` and `dialer_sweep` every 15 s, `runs` increasing, a single owner per tick.
   - No `memory_gc` lease.
   - Startup leases `startup:*` appear once per rollout.
6. **Campaign delivery and duplicate prevention:**
   - `[Scheduler] Atomically claimed N sends` appears on only one server per 5-min tick.
   - Optional controlled test: a one-step campaign to an internal test number. The send log should show one message.
7. **Twilio:**
   - Inbound: send a real SMS and an MMS to an internal number. The thread shows it once and the photo renders.
   - Outbound: an SMS and an MMS from an internal rep to your phone. Delivered; status callback updates.
   - `[TwilioSig]` shows no mismatches.
8. **Jessi:**
   - Chat reply works.
   - Voice parse-task works.
   - An AI reply to an inbound customer text, in an internal test thread.
   - A photo text gives the "can't see photos" fallback and alerts the rep.
9. **Stripe:**
   - `billing_config.mode == live` and `conversion_enabled == true` (super admin).
   - Webhook without a signature returns 400.
   - **No payment** until the separate $100 approval.
10. **Rollback trigger:** a 502 rate above 1% after 10 min, or any duplicate send, means set `JOB_LEASES=off` (rollout), or Rollback, then re-check `billing_config.mode`.

---

## 4. PART 2 — Jessi AI Vision status
Production includes all code before Oct 14 23:26. `contact_files.py` landed Oct 6 and `appraisals/readers.py` Oct 7, so both are in the live build [V-CODE git + V-PROD bundle references `contact-files`].

| # | Capability | Status | Code / endpoints / UI | Real vision model? | Image bytes reach model? | Tests | Missing | Effort |
|---|---|---|---|---|---|---|---|---|
| 1 | Receive and inspect MMS pictures | **PARTIALLY BUILT, LIVE.** Photos are received, stored and shown; Jessi's reply never sees them | `routers/twilio_webhooks.py:172-235` (MediaUrl), `:575-578` `file_inbound_media()` → `services/contact_files.py:350-368` reads it as a contact file; `routers/ai_reply.py:258-275` `attachment_notice()` tells the reply model it *cannot* see the photo; MMS Stage 1 UI (`MessageBubble` retry, Mark Handled) | Yes for filing (`gpt-5.4`, `services/llm_models.py:7`); **no** in the reply | Filing: yes (`contact_files.py:166` → `ImageContent` at `:130`). Reply: **no** | test_mms_stage1 7/7 (attachments, not vision) | Feed the vision read into the AI reply (`AI_VISION_STAGE2_PLAN.md`, "not started") | L |
| 2 | Understand pictures uploaded in the app's Jessi chat | **NOT BUILT** | `/api/jessie/chat` takes text only (`routers/jessie.py:14-28`); no image picker in `app/(tabs)/jessi.tsx`, `app/jessie.tsx`, `AskJessiSheet`, `JessieFloatingChat` | No | No | — | Image field, upload, model call, UI | M |
| 3 | Read business cards and extract contact details | **BUILT, LIVE** | `services/contact_files.py` `_jessi_read` (121), `read_file` (155), `_clean_fields` (135), `apply_fields` (302); `POST /api/contact-files/{user_id}/chunk`, `POST /{user_id}/{file_id}/apply`; UI `app/contact/[id].tsx` + `components/contact/FileDetailSheet.tsx` | Yes (`gpt-5.4`) | Yes | No dedicated test file found (seed `seed_contact_files_demo.py` only) | Not triggered from chat or MMS replies; no automated test | — |
| 4 | Recognize equipment and vehicle photos | **BUILT, LIVE as the appraisal feature** (VIN and odometer reading; AI inspection findings); not part of Jessi chat | `services/appraisals/readers.py:28-35` `_vision`, `vin_from_image` (54), `odometer_from_image` (78); called from `services/appraisals/core.py:416-420`; `routers/appraisals.py` media routes | Yes | Yes | appraisals mvp2–5: 47/47 today; mvp1 1/2 (QA data) | General equipment recognition outside appraisals | M |
| 5 | Interpret screenshots and documents | **BUILT, LIVE** (as contact files) | `contact_files.py:96-109` `_pdf_extract` (text layer plus page OCR), `SCAN_TYPES` | Yes | Yes | none specific | No "screenshot" type; not available in chat or MMS | S |
| 6 | Link image findings to relationship intelligence | **NOT BUILT** (only manual apply of contact fields) | `contact_files.for_context()` (374-379) adds filed-file summaries to Jessi's text context; `voice_intel` and `contact_intel` are text/voice only | — | — | — | `contact_observations` with `source:vision`, proposed/accepted flow | M–L |
| 7 | Prepare updates, notes, tasks and follow-ups from image findings | **PARTIALLY BUILT** | Manual confirm-before-save of contact fields (`apply_fields`); no tasks, notes or follow-ups | — | — | — | Jessi-proposed actions queue | M |
| 8 | Ask for clarification when image details are uncertain | **PARTIALLY BUILT** | Appraisal readers return `confidence` and always ask the rep to confirm; contact files extract only what the model is confident about | — | — | — | Confidence-gated clarification questions in chat or SMS | S–M |
| 9 | Permissions, privacy, AI budget | **PARTIALLY BUILT.** Permissions yes; budget **no** | Contact-file access checks (`routers/contact_files.py:39-68`), sensitive types visible to the uploader only; no vision budget, flag or meter | — | — | — | Per-org vision switch, daily image budget, cost meter | S–M |
| 10 | Unsupported images, failures, duplicates | **PARTIALLY BUILT** | 25 MB limit and photo/PDF-only (`contact_files.py:211-214`); MMS refile dedupe by `message_id` (`:355`); MMS retry UI; HEIC conversion not confirmed | — | — | — | HEIC → JPEG, vision timeouts and fallback copy in chat or MMS | S |

**Don't confuse:** MMS Stage 1 is delivery, storage and display, plus a safe "I can't see photos" fallback that alerts the rep. That is **not** AI image understanding in conversations.

---

## 5. PART 3 — Other unfinished launch features

| Feature | What exists | Live or preview | Missing | Effort |
|---|---|---|---|---|
| **Smart call classification + scorecard eligibility** | Eligibility = transcript present, ≥ 30 s, outcome not voicemail/no-answer (`services/scorecards.py:23,611`); card picked by the rep's department (`pick_scorecard`); the grader returns a free-form `call_type` (e.g. "no_conversation", `:493`) but the call is **still graded**. Relationship intel already extracts from **all** transcribed calls on refresh (`voice_intel.process_conversation_intelligence`, `:53-64`, triggered from `contact_intel.py:249`) | LIVE (Sep 29) | A structured classification (sales / service / parts / support / wrong number / vendor / internal / voicemail); eligibility by department; excluding ineligible and no-conversation calls from averages (`team_stats`/`rep_stats` `:814-861` average every evaluation); a UI badge; automatic intel extraction after each call (today it runs on contact intel refresh) | Classification + eligibility L (2–3 h); "exclude no_conversation from averages" alone S |
| **Jessi Mini greeting fix** | Fix module `frontend/hooks/miniSession.ts` (once-guard plus event dedupe); harness 13/13 PASS | **Preview only, NOT WIRED.** `useLiveJessi.ts:347-351` still calls `onStarted()` on both `session.started` and `session.created` with no guard | Connect it in `useLiveJessi.ts`, publish an OTA, run 10 iPhone calls per engine | S (20–30 min) plus your OTA |
| **Manager My Team** | `services/team_view.py`: role-scoped (super/org/store manager) contacts, shares, texts, last activity, setup progress, number readiness; 6/6 tests | **Preview only, NOT WIRED** (no router, no screen). Live alternatives: Admin → My Team (user list), Leaderboard "My Team" tab, `routers/team_today.py` | Router, screen, and call/task/appointment counts | M (1–1.5 h) |
| **Twilio sender compliance** | `services/sender_policy.py` (fail-closed: dealer must have its own registry number, real subaccount, `messaging_ready`, own Messaging Service; `pause_dealership_texting` switch); 26 tests pass | **Preview only, NOT WIRED.** Not called by `services/twilio_service.send_sms` (`:94-187`). Every outbound path (about 25 callers: campaigns, broadcasts, reminders, date triggers, AI replies, lead flows, invites, OTP, mystery shops, photo requests, calendar invites, widget, onboarding…) bypasses it. Only `send_block_reason` exists, and it is off (`enforce_ready` off [PRIOR Oct 15]). Fallback sender = `TWILIO_MESSAGING_SERVICE_SID` / `TWILIO_PHONE_NUMBER` (IMOS's own registration). Opt-out, DNC and quiet hours are checked only where callers choose to. Production provisioning is `dry_run` (no `settings.twilio_compliance`) [PRIOR Oct 15] | One check inside `send_sms` after `from_phone` is resolved; `platform=True` on system sends (OTP, founder alerts); make `test_send_paths_guarded` strict; owner decision on live provisioning | M (1–1.5 h) plus your Twilio/A2P steps (external vetting can take days) |
| **MMS Stage 1** | Inbound media proxy (CDN allowlist incl. `mms.twiliocdn.com`, signed token, Twilio auth); `file_inbound_media` dedupe by `message_id`; outbound `mms_safe_media` (WebP → JPEG); Jessi photo fallback and rep alert; "Mark Handled" (`updateConversation needs_assistance:false`), photo retry UI | **Backend + web LIVE** (build mms-stage1; strings in the prod web bundle). **Native: OTA not verifiable** | Live checks from the report: valid-token 200 on a recent and an older MMS, outbound SMS/MMS, fallback alert on iPhone; publish the OTA if not done | Your checks, ~15 min |
| **Billing launch readiness** | Signature-verified webhook, idempotent via `stripe_events`, 6 events; checkout/portal blocked with 503 unless the key is live; lookup-key price catalog created on first live checkout [PRIOR]; past_due → 14-day grace plus founder alert; **canceled → founder alert only, access stays on** (`services/billing.py:465-467`); automatic access block exists only for ended pilots (`services/access_block.py`, `server.py:182-184`) | Code LIVE; **live key unverified** (secrets present [V-PROD]) | You confirm `mode: live`; the $100 controlled test; decide on automatic lock for canceled/unpaid (or keep manual); portal settings (tax, receipts) in the Stripe Dashboard; the legacy `/api/webhook/stripe` (reported unsigned [PRIOR], not re-verified) | Lock logic M (~1 h); webhook removal S |

---

## 6. Exact production deployment risks (preview build)
1. **The republish itself.** About 26–60 s of 502/520 is possible while new servers start, caused by the platform health check. Lower after this build (startup about 50% less CPU), but not zero.
2. **Scheduling behaviour changes.** Shared jobs run on one server per run instead of both. This is intended, and a leasing defect could slow or skip a job.
   - Mitigations: 12 tests, the two-server simulation, the live preview leases observed, and the `JOB_LEASES=off` kill switch (needs one secret save, which is a rollout).
3. **Boot clean-ups run once per 3-minute rollout window.** A server restarting within 3 min skips them. They are idempotent repairs.
4. **Indexes build in the background.** On an empty database, unique indexes would arrive a few seconds after the port opens. Production already has them.
5. **Old/new overlap during the rollout:** old servers run every job without leases for about 1–2 min, the same as today.
6. **Secrets:** saved secrets persist; the rollback secret-snapshot behaviour is unknown (see §3C).
7. **Unwired modules ship inert.** Confirmed by imports [V-CODE].
8. **The existing unguarded-sends, interruption-marker and index-gather issues stay the same.** Not made worse.

---

## 7. Feature-by-feature status matrix
| Feature | Production | Preview | Status |
|---|---|---|---|
| Startup speed-up (import CPU −57%, boot 7.4 s → 3.4 s) | no | yes, tested | BUILT IN PREVIEW |
| Cross-server job leases | no | yes, tested | BUILT IN PREVIEW |
| Index gather / short_code / dedup index fix | no | no | NOT BUILT |
| Server-aware interruption markers | no | no | NOT BUILT |
| MMS Stage 1 (backend + web) | yes | yes | LIVE (native OTA unverified) |
| Jessi photo fallback + rep alert | yes | yes | LIVE |
| Business card / document reading (contact files) | yes | yes | LIVE |
| Appraisal VIN / odometer vision + AI inspection | yes | yes | LIVE |
| Jessi sees MMS photos in replies | no | no | NOT BUILT (plan only) |
| Images in the app's Jessi chat | no | no | NOT BUILT |
| Vision → relationship intelligence | no | no | NOT BUILT |
| Vision budget / flags | no | no | NOT BUILT |
| Smart call classification | no | no | NOT BUILT |
| Scorecards (≥ 30 s, department card) | yes | yes | LIVE (eligibility is basic) |
| Call transcripts → relationship intel | yes (on refresh) | yes | LIVE |
| Mini greeting fix | no (bug live) | module only | BUILT, NOT WIRED |
| My Team (manager activity) | partial (user list, leaderboard, team_today) | `team_view` module | BUILT, NOT WIRED |
| Sender compliance policy | no | module only | BUILT, NOT WIRED |
| Live Twilio provisioning / A2P | dry_run [PRIOR] | — | NOT ACTIVE (owner decision) |
| Stripe billing code | yes | yes | LIVE |
| Stripe live key | secrets present, mode unverified | test | YOU TO VERIFY |
| Automatic lock on canceled / unpaid | no (manual) | no | NOT BUILT (decision) |

---

## 8. PART 4 — Master launch checklist (prioritized)

**Effort basis:** measured Emergent runs from git timestamps:
- Security Hotfix 4C ≈ 59 min (19:14 → 20:13).
- MMS Stage 1 ≈ 63 min (22:19 → 23:22).
- The 3 preview launch modules + tests ≈ 16 min (00:35 → 00:51).
- Startup reliability + leases + testing agent ≈ 40 min (≈ 02:20 → 02:59).

| Size | Emergent time (excludes your actions: OTA, Stripe/Twilio dashboards, deploy approval) |
|---|---|
| XS | ≤ 15 min |
| S | 15–30 min |
| M | 45–90 min |
| L | 2–4 h, 1–2 sessions |

### PHASE A — Production reliability and deployment safety
| # | Item | Status | Prod / Preview | Severity | Missing work | Depends on | Effort | Acceptance tests |
|---|---|---|---|---|---|---|---|---|
| A1 | Deploy the startup + lease build | built, tested | preview | **BLOCKER** (before real dealer volume) | Deploy + §3D checklist | your approval; low-traffic window | deploy + 30 min verify | §3D items 2–6 all green; 0 non-200 in 50 checks |
| A2 | Index fix (short_code unique, `return_exceptions`, dedup unique + TTL in own step) | not built | — | IMPORTANT | 3 small edits + duplicate pre-check | Compass/mongosh duplicate check on `inbound_message_dedup` | S | No "Index creation skipped" at boot; `inbound_message_dedup` has `message_sid_1` unique |
| A3 | Retention TTL decision (notifications, clicks, contact_events) | n/a | — | POST-LAUNCH | Product decision; do **not** enable contact_events TTL without one | you | XS after decision | Age counts reviewed before enabling |
| A4 | Server-aware interruption markers | not built | — | IMPORTANT | Owner + heartbeat on crawl, roundtable and inspection runs; fail only stale ones | — | M | Restarting one server doesn't fail an inspection running on the other (simulated) |
| A5 | Send the Emergent infra ticket | drafted | — | IMPORTANT | You send `EMERGENT_INFRA_TICKET.md`; also ask about Rollback and secret snapshots | Emergent | your 5 min | Support reply on probes and rollback |
| A6 | Leases for request-time duplicate risk (broadcasts / appointment reminders) | covered by A1 | preview | — | — | A1 | — | §3D item 6 |
| A7 | Stale test suites (42 header-auth, 5 seed, 3 stale) | stale | — | POST-LAUNCH | Port to token auth or delete | — | M | Suites green or removed |

### PHASE B — Jessi Vision and intelligent image processing
| # | Item | Status | Severity | Missing work | Depends on | Effort | Acceptance |
|---|---|---|---|---|---|---|---|
| B1 | Vision guardrails (per-org switch, daily image budget, HEIC → JPEG, timeouts) | not built | POST-LAUNCH (required before B2) | `services/vision.py` wrapper | — | S–M | Budget blocks after N images; HEIC MMS is read |
| B2 | MMS photo → vision → Jessi reply | not built (plan) | POST-LAUNCH | Pass the vision summary into `queue_ai_reply`; keep the fallback when vision fails | B1 | M–L | A business-card MMS gives a reply that uses the card details; failure gives today's fallback + alert |
| B3 | Vision findings → relationship intel proposals (accept/reject) | not built | POST-LAUNCH | `contact_observations` source=vision; proposals UI | B1 | M–L | Proposed fact appears; accept writes `contact_facts`; reject doesn't |
| B4 | Images in the app's Jessi chat | not built | POST-LAUNCH | Image field on `/api/jessie/chat`; picker in Jessi chat | B1 | M | Upload a card in chat → Jessi offers to create the contact |
| B5 | Clarification when uncertain | partial | POST-LAUNCH | Confidence gate → question | B2 | S | Blurry card → Jessi asks for the missing field |

### PHASE C — Smart call classification and scorecard eligibility
| # | Item | Status | Severity | Missing work | Depends on | Effort | Acceptance |
|---|---|---|---|---|---|---|---|
| C1 | Exclude no-conversation calls from averages and alerts | not built | IMPORTANT (if scorecards are sold) | Filter on `call_type` in `team_stats`/`rep_stats`/alerts | — | S | A voicemail-like 40 s call graded as no_conversation isn't in averages |
| C2 | Structured classification + department eligibility | not built | IMPORTANT | Classifier step before grading; skip non-qualifying calls; store `classification` | C1 | L | Wrong-number and vendor calls aren't graded; sales/service/parts calls are, with the right card |
| C3 | Automatic intel extraction after every relevant call | partial (on refresh) | POST-LAUNCH | Trigger extraction when the transcript lands | — | S | New call → contact facts updated without opening the contact |
| C4 | Classification badge in the UI | not built | POST-LAUNCH | Badge on call rows and scorecards | C2 | S | Badge shows the class |

### PHASE D — Remaining customer-facing launch blockers
| # | Item | Status | Prod / Preview | Severity | Missing work | Depends on | Effort | Acceptance |
|---|---|---|---|---|---|---|---|---|
| D1 | Stripe live verification + $100 test | secrets present | prod | **BLOCKER** (card payments) | You confirm `mode: live`; approved $100 test, then refund | your approval | your 15 min + 30 min verify | `billing_status` active after checkout; webhook events processed; refund shows in Stripe |
| D2 | Connect sender policy at `send_sms` | built, not wired | preview | **BLOCKER** before dealership reps text from anything but numbers you verify | Central check; `platform=True` on system sends; strict `test_send_paths_guarded` | Choose your compliance model; Twilio live provisioning (owner + A2P vetting) | M | Unassigned rep send is blocked with a clear message; IMOS internal sends pass; pause switch blocks all dealer sends |
| D3 | Mini greeting fix connected + OTA | built, not wired | preview | **BLOCKER only if Mini is offered**; else IMPORTANT | Connect `miniSession.ts`; OTA; 10 iPhone calls | your OTA | S | 0 duplicate greetings in 10 calls |
| D4 | Publish the OTA (MMS Stage 1 native UI + D3) | unknown | — | IMPORTANT | `eas update --branch production` | D3 | your 10 min | Native app shows Mark Handled + photo retry |
| D5 | My Team endpoint + screen | built, not wired | preview | IMPORTANT (multi-rep stores) | Router, screen, call/task counts | — | M | A store manager sees only their reps; counts match the database |
| D6 | Automatic lock on canceled / unpaid (or a written manual policy) | not built | — | IMPORTANT | Decision; then block like ended pilots | your decision | M | Canceled org gets the access-blocked screen after grace; resubscribe restores access |
| D7 | Legacy `/api/webhook/stripe` | live [PRIOR: unsigned] | prod | IMPORTANT | Verify; remove or require a signature | — | S | Unsigned POST gives 400 |

### PHASE E — Can safely wait until after launch
- B1–B5 (vision), C3–C4, A3 (TTL retention), A7 (stale tests).
- Android store release [PRIOR], per-rep customization in pilot mode [PRIOR], owner self-resubscribe [PRIOR], Test Clocks permission [PRIOR].

### Minimum safe commercial launch (first paying dealership)
1. **A1** deploy the reliability build, with the §3D checklist passed.
2. **D1** live Stripe confirmed and the $100 test passed. Or sell through the Pilot, a billing exception or a Payment Link while it is pending.
3. **Texting compliance:** either **D2** connected, or you assign each rep a registered dealer number before inviting them, and turn on `enforce_ready`.
4. **Jessi Mini off for customers** until D3 + D4 ship.
5. You keep handling canceled accounts by hand (D6 can wait for the first few customers).

Everything else (vision, classification, My Team, interruption markers) can follow while the first dealership onboards.

---

## 9. Prioritized implementation plan
1. **Phase A1 now** (deploy, after approval): about 30 min of verification.
2. **Smallest next development phase, "Launch Safety Pack" (preview, about 1.5–2 h):**
   - A2 index fix
   - D2 sender-policy wiring
   - D3 Mini fix wiring
   - C1 exclude no-conversation calls from averages
   - One deploy, then **one combined OTA** (D3 + MMS UI).
3. **Next:** D5 My Team, A4 interruption markers, D6 billing lock (about 2.5–3.5 h total).
4. **Then:** Phase C2 classification (about 2–3 h), then Phase B vision (B1 → B2 → B3, about 3–5 h over 2 sessions).

## 10. Already finished — do NOT rebuild
- Startup speed-up + cross-server job leases (preview, tested).
- `sender_policy.py` decision logic (26 tests).
- `team_view.py` scoping and counts (6 tests).
- `miniSession.ts` dedupe logic (13/13 harness).
- MMS Stage 1: proxy, fallback, Mark Handled, retry UI (live).
- Contact-file vision: business cards, documents, PDFs, apply-to-contact (live).
- Appraisal VIN/odometer vision + AI inspection (live).
- Scorecard grading pipeline + department cards (live).
- Call-transcript → relationship intel extraction (live).
- Stripe billing: webhook (signature + idempotency), checkout, portal, seat sync, past_due grace, test-mode safety gate (live code).
- Pilot access block (live).
- Security hotfixes 3 / 4 / 4B / 4C (live).
- Inbound MessageSid upsert dedupe (live).
- `date_send_guard` deterministic-`_id` guards (live).
- Atomic claims in campaign steps and the AI reply queue (live).
- Emergent infra ticket draft; scheduler ownership design.

## 11. Evidence index
- **Production (deployer, Oct 15):**
  - Image `bf277e6b…` built 23:26–23:36; pods `m4d99` restarts=0, `zzdlg` restarts=3 (liveness timeout again 02:53).
  - Index catalogues; boot error only on `short_urls`.
  - Both servers run "Atomically claimed" on their own 5-min schedules with 0 sends claimed.
  - Counts: messages 1,282 (outbound 339), notifications 2,948, contact_events 4,280, inbound_message_dedup 314, date_send_guard 921.
  - Date-range age counts not possible with the tool.
- **Production (public GETs):** `/api/health` build `2026-10-14.mms-stage1`; the web bundle contains "Mark Handled" and "Couldn't load this photo · Tap to retry".
- **Preview:** static index check of 79 specs (3 conflicts, 1 benign); test logs in `/tmp/audit_tests/*.log` (not saved to the repo).
- **Code pointers:** as cited in each section, at HEAD `77fb36372`.
