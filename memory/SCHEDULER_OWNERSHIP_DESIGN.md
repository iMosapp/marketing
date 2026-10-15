# Scheduler & boot clean-up ownership across replicas — design (Oct 15 2026, preview only)

## Problem
Production runs **2 replicas**. Each one starts its own APScheduler (56 jobs) and its own boot clean-ups, and there is no leader election. Confirmed in production logs: "Campaign scheduler started" / "[Scheduler] Started with 56 jobs" appears on both pods, and "Phone consolidation" merged the same duplicate on both boots.

## Inventory: existing idempotency protection (scheduler.py `start_scheduler`, 56 jobs)
| Protection | Jobs |
|---|---|
| **SAFE**: atomic claim | `campaign_step_processor`. It claims each due send with `find_one_and_update` on `status`, `locked_at` and `worker_id` (scheduler.py ~1064–1082). |
| **SAFE by nature**: idempotent `update_many`, no external effect | `expire_stale_waiting`, `daily_recent_tag_expiry`, `dissolve_stale_hot_leads` |
| **LOCAL**: acts on this process only | `memory_gc` (`gc.collect()`) |
| **WEAK**: check-then-act. Two instances inside the same window can both pass the check. | `contact_files_purge`, `inspection_video_purge`, `appraisal_reappraisal_tasks`, `hourly_inventory_feeds`, `daily_system_tasks`, `slow_lead_alert`, `red_leads_digest`, `mystery_shop_planner`, `lead_shops_sweep`, `sold_delivery_processor` |
| **NONE found**: user-visible side effects | All other jobs, including: `lead_call_engine` (15 s, outbound calls), `mystery_shop_dialer` (calls), `scheduled_broadcast_processor` (mass SMS/email), `customer_appointment_reminders` (customer SMS), `daily_date_triggers` (birthday/holiday SMS), `date_preview_digest` / `weekly_keyword_digest` (SMS), `ai_reply_queue_processor` / `ai_reply_escalation_processor` (AI SMS + LLM spend), `internet_lead_processor` / `lead_deferred_actions` (lead SMS), `lead_queue_escalations` (alerts + auto-release), `morning_push_digest`, `held_push_summaries`, `task_reminder_processor`, `highlight_nudge_processor`, `inbox_silent_owner_escalation` (push), `daily_report_delivery`, `weekly_power_rankings`, `weekly_bug_digest`, `weekly_account_health_alert`, `monthly_roi_email`, `monthly_health_reports`, `mystery_shop_monthly_report`, `mystery_shop_weekly_digest`, `coaching_digest_weekly` (email), `monthly_partner_invoices` (invoices), `silence_followup_daily` (SMS), `jessi_onboarding` (SMS/calls), `twilio_tenant_sync`, `twilio_compliance_poll` (Twilio API), `webhook_outbox` (customer webhooks), `voice_meter_watchdog`, `dialer_sweep` (DB-based, confirmed in `services/dialer.sweep` and `services/voice_controls.watchdog`) |

**Implication.** Until now, every unprotected job could run twice in the same minute on two replicas. Daily and weekly cron jobs fire at the same wall-clock second on both replicas, which makes duplicates most likely there. These are exactly the duplicates the business can't afford (double customer SMS or double calls).

## Design: per-job lease, both schedulers keep running
- **Collection `job_leases`**, one doc per job: `{_id: job_id, owner, until, claimed_at, finished_at, running, runs}`.
- **Claim (atomic):**

  ```
  update_one({_id: job, until <= now}, {$set: {owner: me, until: now + 90s, ...}}, upsert=True)
  ```

  - If the lease is held and not expired, the filter doesn't match. The upsert then tries to insert the same `_id` and raises `DuplicateKeyError`, so this replica doesn't run the tick.
  - If no doc exists, both replicas race on the insert and exactly one wins.
- **While running:** the owner renews `until = now + 90s` every 30 s. A replica that dies or hangs stops renewing, and its lease expires within 90 s.
- **After the run (success or exception):** `until = max(now, started + min_gap)`, `running = false`.
  - Interval jobs: `min_gap = 0.8 × interval`.
  - Cron jobs: `min_gap = min(0.8 × period, 300 s)`. Both replicas fire cron jobs at the same instant, so the loser always lands inside the gap.
  - The other replica's tick for the same period is therefore skipped, and the next period runs normally.
- **Takeover:** there is no leader and no hand-off step. Whichever replica ticks first after the lease expires runs the job. The worst-case gap is one interval plus 90 s.
- **Local jobs** (`LOCAL_JOBS = {"memory_gc"}`) are not wrapped, so they run on every replica.
- **One-off jobs** added later (DateTrigger, per-request) aren't wrapped. Only the jobs registered in `start_scheduler` are.
- **Fail-open:** if the lease call itself fails with a `PyMongoError`, the tick runs, which is the behaviour before leases. The job's own DB work would fail anyway if Mongo were down.
- **Kill switch:** `JOB_LEASES=off` (env) disables all guarding without a code change. Every replica then runs every job again.
- **Boot clean-ups:** `run_once(key, fn, window_s=180)` claims `startup:<key>` for 180 s with no release.
  - The first replica of a rollout runs it; a replica booting within 3 min skips it.
  - A later restart, more than 3 min afterwards, runs it again. All of these tasks are idempotent repairs.
  - Wrapped tasks: `appraisal_accepted_migration`, `backfill_account_ids`, `reset_rep_tools_switches`, `consolidate_phone_contacts`, `voice_note_backfill`, `push_device_dedupe`, `date_optin_migration`, `sales_units_repair`, `quick_shops_cleanup`, `kubota_demo_seed`, `doc_sync`, `activity_backfill`, `fix_twilio_webhooks`, `db_housekeeping` (prompt cleanup + index build), `assign_admin_number`, `campaign_delivery_mode_migration`.
- **Not wrapped on purpose (per process):** `locales.load_overrides` (in-memory cache), the object-storage init (in-process key), `recover_interrupted` / `fail_interrupted` (see Risks), `ensure_owner_flag`, `migrate_va_profiles` and the scheduler start itself.

### Why not a single leader?
A single-leader lease adds a renewal loop and a hand-off gap. A cron tick that fires during the hand-off would be missed for the whole day. Per-job leases give the same at-most-once-per-tick guarantee, and each job fails over on its own on the next tick.

## Verification (preview)
`tests/test_job_lease.py` has 12 tests against the preview Mongo; all pass:
- 20 concurrent claims → exactly 1 wins.
- Two replicas firing the same tick → the job runs once, and the next tick inside the gap is skipped.
- The next period runs again after the gap.
- A replica that dies holding a lease: the other replica takes over after expiry.
- A long-running job keeps its lease through renewal; the other replica can't steal it.
- A Mongo error runs the tick (fail-open).
- A job exception still releases the lease.
- `guard_jobs` wraps the shared jobs and leaves `memory_gc` alone; `JOB_LEASES=off` wraps nothing.
- All 56 real jobs are guarded with the expected gaps.
- A boot clean-up runs on one replica per rollout window.
- Lease docs carry owner and times.
- **Production topology simulation:** two schedulers register the real 56 jobs (bodies swapped for recorders, triggers sped up to 1 s) and run side by side for 5 s. Then replica A shuts down.
  - No overlapping runs.
  - Each job ran about once per second across both replicas, never twice in one tick.
  - B kept every job running after A stopped.
  - `memory_gc` ran on both replicas.
- **Live preview:** 55 shared jobs guarded. `job_leases` shows `lead_call_engine` / `dialer_sweep` claimed every 15 s, `lead_deferred_actions` every 30 s and the 1-minute processors every minute. `campaign_step_processor` still logs "Atomically claimed N sends".

## Risks / follow-ups
- **The interruption markers are not replica-aware (existing issue, unchanged).** `widget_crawl.fail_interrupted`, `leadership.fail_interrupted(all_running=True)` and `appraisals.inspection.recover_interrupted` mark every "running" item as interrupted when *any* replica boots. A single-replica restart can therefore fail work that is still in progress on the other replica. The fix needs owner-tagged in-flight records; that's a separate change.
- **A job that blocks the event loop for more than 90 s** can't renew its lease. The other replica could then start the same job while the first is still running, which is the same as today's behaviour.
- **Clock skew between pods** is assumed to be well under the gaps (NTP; the smallest gap is 12 s).
