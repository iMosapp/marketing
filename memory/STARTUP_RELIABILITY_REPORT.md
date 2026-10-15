# Production startup reliability — preview build report (Oct 15 2026)

**Status:** built and tested in preview. Nothing has been deployed, republished or restarted in production, and no secrets were touched.

## Measured startup (preview, 16 cores; `tests/startup_benchmark.py`, medians; raw data in `startup_benchmark.jsonl`)
| Metric | Before | After | Change |
|---|---|---|---|
| `import server` CPU (warm bytecode) | 4.87 s | 2.07 s | **-57%** |
| `import server` CPU (app code recompiled; site-packages cached, like the image) | 5.61 s | 2.81 s | **-50%** |
| Supervisor restart → `/api/health` 200 | 7.42 s | 3.39 s | **-54%** |
| Startup handler (`starting` → `started` log lines) | 0.31 s | 0.05 s | -84% |

**Production projection.** Production runs at 0.5 CPU, where startup is CPU-bound: about 59 s of import on the healthy pod and about 96 s on the slow one. With roughly half the import CPU, that becomes about 25–30 s typical and about 45 s worst case, well inside the entrypoint's gate (about 60 attempts). This has not been measured in production; it can only be confirmed after a deploy.

## What changed (11 source files)
- **Lazy imports** (loaded on first use):
  - The `emergentintegrations` LLM SDK, and through it litellm/openai, in `routers/voice.py`, `services/jessie_service.py`, `services/voice_intel.py` and `services/ai_outreach_service.py`.
  - The Google API client in `routers/calendar.py`.
  - `phonenumbers` in `services/compliance.py`.
  - `numpy` in `services/print_card.py` and `services/appraisals/frames.py`.
- **Routes built once instead of twice, on top of the decorator pass** (`server.py`): `api_router` now carries `UTCJSONResponse`, and its routes are appended to the app as they are, instead of `app.include_router` rebuilding about 1,700 routes. The route table and OpenAPI result are identical; `tests/route_table_snapshot.py` checks all 1,789 routes.
- **Less blocking work at startup** (`server.py`):
  - Object storage init now runs in a worker thread in the background. It was a synchronous HTTP call of up to 30 s on the event loop.
  - Prompt cleanup and the index build, the Twilio admin-number assignment and the campaign delivery_mode migration all moved to background tasks.
- **Cross-replica ownership** (`services/job_lease.py` new, `scheduler.py`): per-job Mongo leases with expiry, renewal and takeover. Boot clean-ups run on one replica per rollout via `run_once`. Design: `SCHEDULER_OWNERSHIP_DESIGN.md`. Kill switch: `JOB_LEASES=off`.

## Tests
- **New `tests/test_job_lease.py`: 12/12.** Includes a two-replica simulation using the real 56 jobs, plus takeover, renewal, fail-open, exactly-once claims and boot run-once.
- **Testing agent (`iteration_389`): 100% on in-scope suites, no regressions.**
  - Lease docs are live in preview; `memory_gc` stays local; the route table is identical.
  - Billing webhook returns 400 for both a missing and an invalid signature. `test_billing_stage2` passed 10/11; the one failure was already there before this change. `test_pilot_program` 10/10.
  - Twilio: inbound webhook returns 200; `test_twilio_tenant` 7/7, `test_message_delivery` 7/7, `test_text_shops` 4/4.
  - Jessi: `test_live_voice` 11/11, `test_voice_controls` 7/7, `test_voice_fallback` 6/6, `test_jessi_onboarding` 3/3; voice parse-task and status work.
  - Campaigns CRUD and contacts CRUD (fresh API checks) pass; `test_voice_findings_pings_snapshots` 4/4.
  - Also passing: `test_security_hotfix4c` 13/13, `test_live_host` 8/8, `test_power_dialer` 5/5; the agent's new `test_startup_reliability_regression` 9/9.
- **Lazy paths checked by hand:** `compliance.region` (UT/Denver, GB/London), the print-card gradient, the frames sharpness/dhash/select functions, a Jessi LLM extraction (litellm loads on first use) and TTS.

## Remaining risks / follow-ups
1. **The probe design isn't fixed by this change.** Any slow start or backend crash still receives traffic until Emergent changes the health check (ticket: `EMERGENT_INFRA_TICKET.md`).
2. **Index build has been silently skipped on every boot (existing issue).** In both preview and production, `asyncio.gather(create_index…)` stops on an `IndexKeySpecsConflict` (`short_code_1` in prod, `user_id_1` in preview). The TTL indexes and the `inbound_message_dedup.message_sid` unique index after it are therefore never ensured. Separate small fix proposed: `return_exceptions=True` plus explicit names.
3. **The interruption markers are not replica-aware (existing issue).** `fail_interrupted` / `recover_interrupted` at boot can mark work as failed while it is still running on the other replica.
4. **Every boot cancels some campaign sends (existing issue).** The campaign delivery_mode migration still cancels `pending` sends with no `delivery_mode` on every boot, now on one replica per rollout.
5. **Behaviour change after deploy:** shared scheduled jobs run once per tick across the 2 replicas instead of on both. This should remove the duplicate SMS/push/email and double calls that two replicas could cause until now.
6. **Old live-API test files are stale.** Several fail on old credentials or auth rules, unrelated to this change, and cause login lockouts. Don't use them as a regression gate.
