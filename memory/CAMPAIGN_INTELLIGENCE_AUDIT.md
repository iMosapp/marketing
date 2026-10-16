# I'm On Social: Campaign Intelligence & Automation, Phase 1 Read-Only Audit + Target Architecture

**Date:** Oct 16 2026. **Mode:** read-only. No code, database, configuration, secret or production change was made. Nothing was deployed or sent.
No tests were run either: almost all campaign tests are live HTTP tests that write to the preview database.

**Evidence labels**
- **[CODE]** = read in the current code (file:line).
- **[TEST]** = a test file exists that covers it. Not re-run in this audit.
- **[PROD]** = a prior production observation (COMMERCIAL_LAUNCH_MASTER_AUDIT.md, Oct 15).
- **[UNVERIFIED]** = could not be confirmed without running it.

**Status labels**
- **WORKING** = the code path exists and is covered by a test or by prior observation.
- **PARTIAL** = it exists with gaps.
- **MISSING** = it does not exist.
- **BROKEN** = the code contradicts its intent.
- **UNVERIFIED** = it exists, but its end-to-end behaviour has not been proven.

None of the items below is "verified end-to-end in production": the production campaign send volume observed on Oct 15 was 0 [PROD].

---

## Executive summary (the 12 things that matter most)

1. **There is no single campaign engine today. There are six message paths that schedule customer contact.**
   - Campaigns (`routers/campaigns.py` + `services/tag_workflows.py` -> `campaign_pending_sends`).
   - Date triggers (`scheduler._run_date_triggers_for_user`). These create rep tasks, plus an optional direct Resend email.
   - Date-type campaigns (`scheduler._enroll_date_campaigns_for_user`).
   - The Sold workflow's immediate texts (`routers/sold_workflow.py`).
   - Broadcasts (`services/broadcast_queue.py`).
   - A dead legacy engine, `routers/campaign_lifecycle.py`. It is not mounted in `server.py`, but tests and `contact_events.py:532` still reference its `salesman_id` shape.
   - Duplicate-prevention fixes have had to be bolted on between these paths (`server.py:345-420` admin dedupe and the "Sold day 7+ only" fix).
2. **Pausing or deactivating a campaign does not stop messages that are already scheduled [CODE, BROKEN].**
   - `update_campaign` only flips `campaigns.active` (`routers/campaigns.py:908-972`).
   - The sender loads `active` but never checks it (`scheduler.py:1109`).
   - Already-queued `campaign_pending_sends` rows keep sending.
3. **A worker crash after claiming a send leaves it stuck in `processing` forever, and it silently disappears [CODE, BROKEN].**
   - The claim is atomic (`scheduler.py:1068-1082`).
   - But nothing ever recovers `campaign_pending_sends` rows that are stuck in `processing`.
   - `send_ledger.sweep` only covers the provider call itself (`services/send_ledger.py:52-57`).
4. **There is no lateness cap [CODE, MISSING].** After an outage, a "Day 7 check-in" that is 40 days late still sends (`send_at <= now`, `scheduler.py:1070`).
5. **The pre-send guardrails fail open [CODE, BROKEN by design].** If the opt-out or "customer is waiting on a reply" check throws an error, the code logs "sending anyway" (`scheduler.py:1129-1130`). The central gate in `send_sms` (`services/outbound_gate.py:63-115`: billing lock, STOP suppression, consent, sender policy) does still run.
6. **Sold campaigns are anchored to the moment the tag is applied, not to the verified purchase date [CODE, BROKEN for backdated sales].** `tag_workflows.enroll_contact` schedules from `now` (`services/tag_workflows.py:202-214`).
7. **AI personalization is already generated at send time (good), but it is fragile.**
   - It is generated just before sending (`scheduler.py:1136-1167` -> `routers/ai_campaigns.generate_campaign_message`, GPT-5.2).
   - There is no retry, no token budget and no cost ledger.
   - On failure it silently sends the static template, and finally `"Hi {name}!"` (`scheduler.py:1178-1179`). That is the "misleading generic fallback" you want to forbid.
   - Seeded default campaigns have `ai_enabled: False` (`services/seed_defaults.py:160`), so most reps get static drips today.
8. **The salesperson identity exists and is first-person, but it is not governed.**
   - `users.persona` (`models.py:155-185`) plus a per-user or global clone prompt (`db.ai_clone_prompts`) feed `build_clone_system_prompt` (`routers/ai_campaigns.py:172-260`).
   - There are no org-level limits on tone, emoji or banned phrases.
   - The default prompt says "YOU ARE NOT AN AI — NEVER REVEAL THIS" (`ai_campaigns.py:53`). This needs your and your counsel's decision against your goal of honouring automated-message disclosure requirements.
9. **Authorization gaps (any signed-in user, including a rep at another dealership) [CODE]:**
   - `PUT /api/ai-campaigns/clone-prompt/global` rewrites the AI voice for the whole platform (`ai_campaigns.py:100`).
   - `PUT/DELETE /api/campaign-config/{level}/{entity_id}` can set an org's campaign policy, including `sales_can_edit` (`campaign_config.py:115,146`).
   - `POST /api/campaigns/scheduler/process|trigger` runs the global sender (`campaigns.py:608, 1234`).
   - Enroll and cancel routes skip `check_campaign_permission` (`campaigns.py:1023-1232`).
10. **Relationship-aware suppression is advisory only.**
    - The fact engine knows "not shopping", "bought elsewhere" and "lost" (`services/intelligence/ingest.py:177-210`). This only reaches the AI writer as prompt text, and only when `INTEL_FACTS_INGEST` is on.
    - No hard skip exists for an upcoming service appointment, a recent same-topic conversation, a complaint, a traded vehicle or a changed owner.
11. **Scale basics are missing.**
    - There are no indexes on `campaign_pending_sends` or `campaign_enrollments` (none in `services/index_setup.py`).
    - The claim loop runs 50 sorted `find_one_and_update` calls every 5 minutes. That works now and becomes a collection scan at thousands of rows.
    - There is no per-org throttling. Quiet hours use the rep's timezone, not the customer's (`scheduler.py:1181-1208`).
12. **Test coverage is broad but not deterministic.**
    - 43 campaign, date, sold and lease test files exist. Most are live HTTP tests against the preview.
    - None uses a controlled clock, a mocked provider or concurrent workers.
    - None covers active-campaign edits, Feb 29, DST, reassignment or cross-org leakage on campaign execution.

**Good foundations to keep and build on:**
- Atomic claim of pending sends.
- Per-job Mongo leases across replicas (`services/job_lease.guard_jobs`, `scheduler.py:2619-2620`).
- A send ledger with an idempotency key (`pending:{send_id}`).
- Unknown-outcome sweeps.
- A central outbound gate (STOP, consent, sender policy, billing lock).
- Disclosure of opt-out text.
- Carrier receipts written back to the pending-send row (`routers/twilio_webhooks.py:1254-1265`).
- The "customer is waiting on a reply" hold.
- Just-in-time AI with the relationship brief.
- The fact engine with a compact prompt block (`services/intelligence/reply_context.py`).
- The live voice tool with a confirm-first pattern (`services/live_actions.enroll_campaign`).

---

## A. Current system audit

### A1. Message paths that contact customers on a schedule
| # | Path | Where | What it does | Status |
|---|---|---|---|---|
| 1 | Campaigns (sequence) | `routers/campaigns.py`, `services/tag_workflows.py`, `scheduler.process_pending_campaign_steps` (`scheduler.py:977-1552`) | Enrollment pre-schedules one `campaign_pending_sends` row per step; a 5-min job claims due rows and sends (auto) or creates a rep task (manual). | WORKING core, gaps below |
| 2 | Date-type campaigns | `scheduler._enroll_date_campaigns_for_user` (`:395-515`) | Daily: contacts whose birthday / anniversary / `date_sold` is today get enrolled in the FIRST matching date campaign. | PARTIAL |
| 3 | Date triggers (per-user config + holidays) | `routers/date_triggers.py`, `scheduler._run_date_triggers_for_user` (`:518-742`), cron 08:00 UTC (`:2095`) | Creates a rep task + notification; inserts a `messages` row flagged `pending_manual_send`; optional direct Resend email (`:714-726`). | PARTIAL (second date system) |
| 4 | Sold workflow immediate texts | `routers/sold_workflow.py:139` | Day-0/2 congratulations sent by the Sold wizard; campaigns were patched to start at day 7 to avoid duplicates (`server.py:375-420`). | WORKING, coupled by convention |
| 5 | Broadcasts | `routers/broadcast.py`, `services/broadcast_queue.py` | Bulk sends with their own queue + stale recovery. | Out of scope, shares the gate |
| 6 | Legacy lifecycle engine | `routers/campaign_lifecycle.py` | Templates, `/enroll`, pause/resume/skip with `salesman_id` / `next_send_date`. **Not mounted** in `server.py:35`. Dead code with schema drift. | DEAD (remove later) |
| 7 | Live Jessi enroll tool | `services/live_actions.enroll_campaign` (`:331`) | Voice: enroll a contact in an existing active campaign, confirm-first. | WORKING |

### A2. Campaign definition
| Capability | Status | Evidence |
|---|---|---|
| Model: name, type, trigger_tag, trigger_events, date_type, segment_tags, sequences[], send_time, active, delivery_mode, ai_enabled, ai_assist_mode, scope, store_id, org_id, repeat_* | WORKING | `models.py:459-537`, written `campaigns.py:625-676` |
| Step: delay_minutes/hours/days/months, channel, message_template, media_urls, action_type, card_type, `step_context` (a free-text goal for the AI) | WORKING | `models.py:459-471` |
| Lifecycle states (draft / pending approval / active / paused / archived) | MISSING (boolean `active` only) | `campaigns.py:1013,1033` |
| Versioning / controlled publishing | MISSING | — |
| Clone | WORKING (copies, sets inactive) | `campaigns.py:994-1019` |
| Approval before activation | MISSING | — |
| Prebuilt templates | WORKING (hard-coded list, `ai_enabled: True`) | `campaigns.py:20-497` |
| Seeded per-user defaults | WORKING (`ai_enabled: False`) | `services/seed_defaults.py:150-310` |
| Org / store / personal scope | WORKING by visibility query (`scope`), no explicit assignment list | `campaigns.py:690-760`, `tag_workflows.py:62-96` |
| Per-store / org config (message_mode ai_suggested / template / hybrid, sales_can_edit, managers_can_edit) | WORKING, **unguarded writes** | `routers/campaign_config.py:19,74-153` |
| Editing an active campaign | PARTIAL: edits change the definition only, existing enrollments keep their pre-scheduled snapshot (no duplicates, no reschedule, no notice) | `campaigns.py:908-972` |
| Pausing a campaign stops scheduled sends | BROKEN | see Executive summary #2 |

### A3. Enrollment
| Capability | Status | Evidence |
|---|---|---|
| Manual single enroll | WORKING [TEST] | `campaigns.py:1023-1140` |
| Bulk enroll | PARTIAL (Smart lists / broadcast; no campaign bulk endpoint found) | [UNVERIFIED] |
| Tag-triggered | WORKING [TEST] `test_tag_campaign_auto_enrollment.py`, `test_campaign_auto_enrollment_fix_269.py` | `tag_workflows.enroll_contact` `:192-228` |
| Business-event triggers | PARTIAL: `trigger_events` stored (`campaigns.py:636`); firing lives in appraisal follow-ups only | `services/appraisals/followup.py` |
| Date triggers | PARTIAL (two systems, see A1 #2/#3) | |
| Duplicate prevention | PARTIAL: tag path blocks active+completed (`tag_workflows.py:196`); manual blocks only active (`campaigns.py:1042`) | |
| Competing campaigns stop (e.g. Sold stops lead nurture) | WORKING [CODE] | `tag_workflows.stop_competing` `:231-248` |
| Anchor date | BROKEN for backdated sales (tag time, not `date_sold` / purchase record) | `tag_workflows.py:202-214` |
| Re-enrollment policy / multiple purchases | MISSING (blocked forever after completion on tag path; repeat_every_months exists for repeat step) | `scheduler.py:1503` |
| Unenroll / cancel (one, all) | WORKING [TEST] `test_campaign_removal*.py` | `campaigns.py:1179-1232` |
| Contact-level pause | MISSING in mounted code (only in dead lifecycle router) | |
| Contact deleted / merged / opted out | WORKING at send time (skip with reason) | `scheduler.py:1113-1118` (skip with reason); `contacts.py:2228` cancels an enrollment's open touches |

### A4. Execution (scheduler)
| Capability | Status | Evidence |
|---|---|---|
| Durable per-message record | WORKING: one `campaign_pending_sends` row per touch | |
| States | `pending → processing → sent / failed / unknown_outcome / skipped / pending_user_action`; `held_reason`, `skip_reason`, `delivery_status` | `scheduler.py:1100-1482` |
| Atomic claim + worker id | WORKING | `:1068-1082` |
| Cross-replica job lease | WORKING [TEST] `test_job_lease.py` | `scheduler.py:2619`, `services/job_lease.py` |
| Stale `processing` recovery | MISSING (silent loss) | grep: no update of `processing` rows |
| Provider idempotency | WORKING: `send_ledger` key `pending:{send_id}`; mid-call crash -> `unknown_outcome`, never re-sent | `twilio_service.py:163-171`, `send_ledger.py:52-57` |
| Retry/backoff | PARTIAL: generic exceptions retry ≤3 (`:1523-1536`); Twilio failures are terminal, no backoff | |
| Lateness cap / missed-job policy | MISSING | `:1070` |
| Campaign active check at send | MISSING | `:1109` |
| Guardrail failure behaviour | Fails OPEN | `:1129-1130` |
| Hold when customer is waiting on a reply | WORKING (max 3 holds of 2 days) | `:1119-1128` |
| Quiet hours | PARTIAL [TEST] `test_quiet_hours.py`: 8am-9pm in the REP's timezone, auto mode only | `:1181-1208` |
| DST | PARTIAL: delays are absolute UTC offsets, so local send time drifts 1 h across DST; quiet window re-defers | |
| Org throttling / rate limits | MISSING | |
| Indexes | MISSING for pending sends / enrollments | `services/index_setup.py` |
| Carrier receipts | WORKING: `delivery_status` delivered/undelivered on the pending row | `twilio_webhooks.py:1254-1265` |
| Manual / approval mode | WORKING: `delivery_mode` manual creates a `campaign_send` task at due time, message generated then and frozen on the row; no expiry | `scheduler.py:1397-1469`, `frontend/app/campaigns/pending-send/[id].tsx` |

### A5. Delivery and compliance (every SMS goes through `services/twilio_service.send_sms`, `:94-185`)
| Gate | Status | Evidence |
|---|---|---|
| Billing lock, STOP suppression, consent (`CONSENT_MODE`), sender policy (`SENDER_POLICY_MODE`) | WORKING in code, **wired** (this corrects the Oct 15 audit that said sender policy was not wired) | `services/outbound_gate.py:63-115` |
| Opt-out disclosure text | WORKING | `services/disclosure.py`, `twilio_service.py:132-173` |
| AI / automated-message identity disclosure | MISSING (prompt forbids revealing AI) | `ai_campaigns.py:53` |
| Sender number | rep number, else shared inbox, else platform number | `inboxes.resolve_from_number`, `scheduler.py:1257` |
| Email | Direct Resend calls in date triggers; campaign email channel [UNVERIFIED] | `scheduler.py:714-726`, `frontend/app/campaigns/email.tsx` |
| Every attempt logged incl. blocked | WORKING `sms_send_log` | `outbound_gate.py:118-130` |

### A6. Date-specific automation
| Item | Status | Evidence |
|---|---|---|
| Birthday / anniversary / sold-date anniversary daily match | WORKING [TEST] `test_birthday_campaign_triggers.py`, `test_date_triggers.py` | `scheduler.py:395-515` |
| Timezone | rep timezone (default America/Denver) | `:528` |
| Feb 29 | MISSING (never matches in non-leap years) | `:430-431, 573` |
| Duplicate prevention | WORKING: deterministic `_id` `date_send_guard`, first matching campaign only, 300-day recent check | `:443-460` |
| Updated dates / missing dates | PARTIAL (read live each day, so updates apply; missing = silently skipped, no flag) | |
| Holidays | WORKING (14 holidays) | `routers/date_triggers.py` |

### A7. Collections
- `campaigns` (definition)
- `campaign_enrollments` (contact progress, `messages_sent[]`)
- `campaign_pending_sends` (execution record per touch)
- `campaign_templates` (legacy, dead router)
- `campaign_configs` (store/org policy)
- `ai_clone_prompts` (global / user voice)
- `date_trigger_configs`, `date_trigger_log`, `date_send_guard`
- `send_ledger`, `sms_send_log`, `messages`, `contact_events`, `tasks`, `notifications`, `job_leases`

### A8. Frontend
| Screen | Purpose |
|---|---|
| `app/campaigns/index.tsx` (131 lines) | List |
| `new.tsx` (141) | Create from prebuilt template or blank |
| `[id].tsx` (426) | Detail/edit, steps, enroll |
| `dashboard.tsx` (526) | Pending / upcoming / journey overview (backed by campaign + scheduler endpoints) |
| `email.tsx` (655) | Email steps |
| `pending-send/[id].tsx` (360) | Rep reviews and sends a manual-mode touch |
| `app/campaign-config.tsx` (296) | Store/org campaign policy |

There is no "Build with Jessi", no visual timeline of intent, no health dashboard of failures/suppressions/costs.

### A9. Tests (43 files; names in `backend/tests`)
- **Permissions:** `test_campaign_permissions*.py`.
- **Creation:** `test_campaign_creation.py`, `test_campaigns_redesign.py`, `test_campaign_unification.py`.
- **Removal:** `test_campaign_removal*.py`.
- **Tag enrollment:** `test_tag_campaign_*`, `test_campaign_auto_enrollment_fix_269.py`.
- **Scheduler:** `test_campaign_journey_scheduler.py`, `test_campaign_scheduler_fix.py`, `test_scheduler_api.py`, `test_job_lease.py` (unit), `test_quiet_hours.py` (unit).
- **Date:** `test_birthday_*`, `test_date_triggers.py`.
- **Sold:** `test_sold_workflow*.py`, `test_sold_wizard_*`.
- **AI:** `test_ai_campaigns.py`, `test_relationship_intel_campaigns.py`, `test_intel_phase2_journey.py`.
- **Compliance:** `test_sender_policy.py`.

Most of these are live HTTP tests: they need the running preview and write data. None is deterministic with a fake clock, fake provider and concurrent workers.

---

## B. Reliability assessment (prioritized)
| ID | Severity | Defect | Fix direction |
|---|---|---|---|
| R1 | P0 | Pausing / deactivating a campaign keeps sending queued touches | Check campaign status + enrollment status at claim time; pausing marks queued rows `paused` (resume restores) |
| R2 | P0 | Claimed rows stuck in `processing` after a crash vanish | Sweep `processing` older than N min: if the send ledger shows a provider submit -> `unknown_outcome` (no resend); else back to `pending` with attempt+1 |
| R3 | P0 | Guardrails fail open | Fail closed: hold the touch and record `hold_reason: guard_error` |
| R4 | P0 | AI failure sends a template / "Hi {name}!" | Intelligent mode: retry with backoff, then hold + alert / rep task; never a generic text; static mode is explicit |
| R5 | P0 | Open admin-level writes (global clone prompt, campaign-config, scheduler trigger) and enroll/cancel skip campaign permission | Role-gate + org-scope; audit log |
| R6 | P1 | No lateness cap | Per-step `max_late` (default e.g. 3 days for check-ins, same-day for birthdays); past it -> `expired` with reason |
| R7 | P1 | Sold anchor = tag time | Anchor to the purchase record date (`purchase_history` / `date_sold`); missing -> flag + rep task to confirm, don't guess |
| R8 | P1 | Twilio failures terminal; no classification | Classify (permanent: invalid number / STOP; transient: 5xx / rate limit) and retry transient with backoff |
| R9 | P1 | Quiet hours in rep timezone, auto only | Contact timezone (from area code / address, fallback store, then rep); apply to every customer touch incl. manual tasks' suggested time |
| R10 | P1 | No indexes | `campaign_pending_sends {status, send_at}`, `{enrollment_id, step}` unique touch key, `{message_sid}`; `campaign_enrollments {campaign_id, contact_id, status}` |
| R11 | P1 | Two date systems + Sold wizard + campaigns can overlap | One date-event resolver; cross-campaign "same event same day" guard extended to all paths |
| R12 | P2 | Feb 29, DST drift, no org throttling, no backlog alerts | Feb 28 in non-leap years (configurable); schedule in contact local time; per-org send rate; health alerts |
| R13 | P2 | Dead `campaign_lifecycle.py` with drifted schema | Remove after confirming no callers (tests only) |

Exactly-once delivery cannot be promised. The plan keeps: an idempotency key per touch, a ledger claim before the provider call, `unknown_outcome` instead of resending, and carrier-receipt reconciliation.

---

## C. Personal VA identity assessment
- **Persona** lives on `users.persona` (`models.py:155-185`): tone, emoji_use / emoji_usage, humor_level, brevity / response_length, bio, hobbies, family, hometown, specialties, never_say, banned_words, custom_phrases, signature, greeting_style. It is edited via `routers/profile.py:232-266`. Field drift: the GET returns `tone_preference` while the model stores `tone`.
- **Voice prompt:** `ai_clone_prompts` holds the global and per-user prompts (`ai_campaigns.py:89-166`). `build_clone_system_prompt` (`:172-260`) is used for AI replies (`routers/ai_reply.py:857,1743,1864`) and campaign generation. It speaks in the first person as the rep. Style exemplars come from the fact engine when it is on.
- **Other identities:**
  - Shared-inbox threads use a department VA (`ai_reply.py:824-852`).
  - Lead sources use named VA profiles (`routers/va_profiles.py`).
  - `services/ai_outreach_service.py` uses a generic coach prompt with **no persona**.
- **Ownership:** `contacts.user_id` (+ `ownership_type` org/personal, `original_user_id`). There is no explicit org field on the contact.
  - Reassignment endpoints exist: `engagement_signals.py:477` (manager, org leads), `lead_queue.py:379`, and `admin_users.py:865` (user delete -> unassigned).
  - **Enrollments keep the old `user_id`**, so after reassignment the old rep's voice and number are used [CODE].
- **Sender number:** the rep's `twilio_number` / `mvpline_number` (two field names), else a shared inbox number, else the platform number.
- **Missing:**
  - Org messaging policy (allowed tone range, emoji cap, banned phrases, signature rules, disclosure).
  - A validator that checks generated text against persona plus policy.
  - The rule "resolve identity at send time from the current owner".
  - A reassignment policy.

**Target:** add no new profile system. Extend `users.persona` (rep preferences) and add an `organizations.messaging_policy` (limits). Resolve `sender = current contact owner at send time` (policy: follow the new owner; if the owner is inactive -> org fallback owner or hold). Every campaign generation uses `build_clone_system_prompt(owner)` plus org limits. A post-generation validator enforces length, emoji, banned words, no unverifiable claims and no "Jessi" self-intro.

---

## D. Relationship personalization assessment
| Source | Exists | Used in campaign generation today |
|---|---|---|
| Voice memo transcripts (`voice_notes`) | yes | yes, raw (`relationship_intel.py:376-393`) |
| Notes, personal_details | yes | yes |
| Relationship brief (`relationship_intel.build_relationship_brief`) | yes | yes (main context) |
| Fact engine compact block (`intelligence/brief.py`, `reply_context.py`) | yes, behind `INTEL_FACTS_INGEST` | yes when the flag is on (production value [UNVERIFIED]) |
| SMS in/out (`messages`, `thread_context`, 2,500 char dialogue) | yes | yes |
| Prior campaign touches | yes | yes ("check-ins I already sent") |
| Purchases / vehicles | yes | yes |
| Service appointments (`tasks` type appointment) | yes | **no** |
| Contact Files facts / scanned documents (new) | yes | **no** |
| Memory search | yes | no (not needed per message) |
| Engagement signals (card views) | yes | yes |

**Gaps:**
- There is no token budget. The raw transcripts and the full brief can be large.
- There is no hard suppression, no explanation record ("which facts informed it"), no LLM cost ledger, no retry and no output validation.
- Reply ingestion already updates facts: intents, bought elsewhere, not shopping, buying signals (`ingest.py:142-241`). Voice memos write `personal_details` and facts (`services/voice_intel.py` -> `ingest.plan_extraction`). Reuse these, with no new memory system.

**Target send-time pipeline (one function, `campaign_touch.prepare(touch)`):**
1. **Load:** the touch, the enrollment, the campaign version and step intent.
2. **Eligibility:** consent, opt-out, quiet hours, campaign and enrollment active, owner active, lateness.
3. **Context pack:** the fact-engine `reply_context` block, plus a trimmed brief. Keep the last 3 relevant facts with dates, the last 6 messages, upcoming appointments and the last campaign touch. Hard cap about 2.5k input tokens.
4. **Suppression rules (deterministic):**
   - Appointment already booked inside the step window: adapt or skip.
   - Same topic discussed in the last N days: skip.
   - Vehicle no longer owned: skip the ownership anniversary.
   - `not_shopping` / `lost` / complaint flag: skip celebratory and sales steps.
   - Owner changed: re-resolve the sender.
5. **Generate:** in the owner's persona plus org policy, from the step intent.
6. **Validate:** length, banned words, no fabricated claims (facts must come from the pack), no AI self-intro.
7. **Record:** facts used (ids), model, tokens, cost, suppression reasons.
8. **Submit:** through the existing `send_sms` gate.

A complaint signal does not exist today. Propose a small classifier on inbound replies (cheap model, part of the existing ingest) that sets a `concern.open` fact.

---

## E. Campaign permission architecture
- **Today:**
  - `check_campaign_permission` (`campaigns.py:500-553`): super_admin and org_admin are allowed; store_manager only if `managers_can_edit`; a rep only if `sales_can_edit` (both default off) [TEST].
  - On create, a non-admin scope is silently downgraded to personal (`:649-652`).
  - The request middleware binds any `{user_id}` route to the caller or a scoped manager (`server.py:196-197`, `services/route_guard.py:111-141`).
  - Routes without `{user_id}` are not bound (R5).
- **Target (one policy module, `services/campaign_policy.py`, used by every campaign route and the voice tools):**

| Action | Super Admin | Org Admin | Manager | Salesperson (default) | Salesperson (advanced flag) |
|---|---|---|---|---|---|
| Platform templates, global voice, reliability controls | ✓ | — | — | — | — |
| Create / edit org campaign drafts | ✓ | ✓ | per org policy, own teams | — | personal drafts |
| Approve / activate / pause / archive | ✓ | ✓ | per org policy | — | approved personal only |
| Assign to stores / teams / users | ✓ | ✓ | own teams | — | — |
| Enroll eligible contacts / apply enrollment tags | ✓ | ✓ | ✓ | own contacts | own contacts |
| Pause a contact's touches | ✓ | ✓ | ✓ | own contacts | own contacts |
| View health / costs | ✓ | org | teams | own | own |

Every write gets organization isolation (the campaign's org must equal the caller's org unless super admin) and an entry in a `campaign_audit` collection (who, what, before/after, version).

---

## F. Voice-first campaign builder design
- **Reuse:**
  - The live Jessi tool framework (`services/live_actions.py`, `services/live_voice.py`) with the confirm-first PENDING pattern.
  - Ask Jessi text chat for the typed equivalent.
  - The same campaign service that the manual builder calls.
- **New tools:** `draft_campaign`, `edit_campaign_draft`, `explain_campaign`, `submit_for_approval`, `activate_campaign`.
  - They only emit **validated structured patches** (JSON Patch over the `CampaignDraft` schema), never raw database writes.
  - The server applies each patch through `campaign_policy` plus schema validation, and returns the new draft and a timeline.
- **Flow:**
  1. Interpret (audience, trigger, timing, intents).
  2. Fill defaults from the template library.
  3. Ask only for missing must-haves (trigger, anchor date, approval mode).
  4. Show the draft as a timeline card on screen while speaking a short summary.
  5. Edits, for example "move the service reminder to 90 days, remove the second check-in, add a birthday", become 3 patches -> re-render -> "Here's the updated plan".
  6. Validate (no step before the anchor, quiet-hour feasibility, overlap with other active campaigns, consent channel).
  7. "Activate?" requires an explicit yes (spoken or tapped), and only for authorized roles; otherwise "Sent to your manager for approval".
- **Example previews:** "Show me what Brian would get" generates 2-3 representative previews for real or synthetic contacts. They are labelled examples and never stored as final text.

---

## G. Unified campaign data model (extend the existing collections; no parallel engine)
- **`campaigns`** (definition head):
  - `status` (draft | pending_approval | active | paused | archived), with `active` kept as a derived field for backward compatibility.
  - `current_version`, `org_id`, `store_ids[]`, `team_ids[]`, `user_ids[]` (assignment), `approval_required`, `mode` (intelligent | static), `created_by`, `approved_by/at`.
- **`campaign_versions`** (new, immutable snapshot on publish): `campaign_id`, `version`, `trigger`, `steps[]`, `policies`, `published_by/at`.
- **Trigger:** `{type: tag | event | date | manual, tag, event, date_field, anchor: purchase_date | tag_date | enrollment_date | custom_field, require_anchor: bool, re_enroll: never | after_completion | per_purchase, exclusions[]}`.
- **Step:**
  - `{key (stable id), offset {days, months, at_local_time}, recurring_annual?, channel, mode, intent {purpose, outcome, tone, length, context_hints[], cta}`.
  - `send_if[]`, `suppress_if[]` (rule ids: appointment_booked, recent_same_topic, vehicle_not_owned, concern_open, not_shopping...).
  - `fallback: hold | rep_task | skip`, `max_late`, `static_text` (static mode only).
- **`campaign_enrollments`:** add `version`, `anchor_date`, `anchor_source`, `owner_user_id` (current owner, re-resolved), `org_id`, `paused_reason`, a unique partial index on active (campaign_id, contact_id).
- **`campaign_pending_sends`** (the execution record, a "touch"):
  - Add `touch_key = enrollment_id:step_key[:year]` (unique).
  - `state`: scheduled → due → claimed → evaluated → generated → validated → submitted → accepted → delivered | failed | unknown | suppressed | expired | held.
  - `events[]` (timestamped lifecycle log).
  - `sender {user_id, from_number}` and `context_refs[]` (fact / message / memo ids used).
  - `generation {model, tokens_in/out, cost, attempts, validated}`, `suppression {rule, reason}`.
  - `approval {required, frozen_text, frozen_at, reviewer, expires_at}`.
  - Existing fields stay readable.
- **`ai_usage`** (new ledger, same pattern as `vision_usage`): org, user, purpose (campaign_touch | reply | builder), model, tokens, cost, touch_id.
- **`organizations.messaging_policy`** (new sub-document): tone range, emoji max, banned phrases, signature rule, AI disclosure policy, quiet hours, max texts per contact per week.
- **Active edits policy:**
  - Publishing v2 never touches touches that are already `submitted` or later.
  - The manager chooses either "new enrollments only" (default) or "apply to existing". The second option re-plans only not-yet-due touches whose step key still exists, cancels removed steps (state `cancelled_by_edit`) and adds new steps after now. A preview diff is shown first.
  - The unique `touch_key` makes duplicates impossible.

---

## H. Simplified campaign UX
- **Campaigns home (managers):** four big actions (Build with Jessi, Build Manually, Start from Template, Active Campaigns), plus a health strip (next 7 days, failures, held, suppressed).
- **Builder (shared by voice and manual):**
  - A horizontal timeline of step cards (When · Why · Outcome).
  - Audience and trigger card; anchor date card; approval and assignment card.
  - "Preview for a customer" opens 2-3 examples.
  - Validate -> Submit or Activate.
- **Campaign detail:** status pill, version history, enrolled count, upcoming touches, pause/resume, "apply edits to existing?" dialog.
- **Touch inspector** (from a contact or the health list):
  - Why scheduled, campaign/version/step, sender identity, facts used.
  - Generated / held / suppressed with the reason, and the carrier status.
- **Salesperson:** "My campaigns" (read-only), the contact's upcoming touches with "Pause for this customer", and Approve/Edit when approval mode is on.
- **Health dashboard:** active, enrolled, upcoming, overdue, submitted, delivered, failed, suppressed, replies, AI failures, duplicates prevented, cost per message and per org, plus alerts.

---

## I. Phased implementation plan (small, independently testable)

Credit use cannot be estimated reliably. Each phase is sized by effort instead: S ≈ one focused session, M ≈ two or three, L ≈ four or more.

### Phase 0: Deterministic test harness (S-M)
- **Scope:** A fake clock, a fake SMS provider (records submissions, scripted failures and timeouts), and a fake LLM (deterministic per contact) for `process_pending_campaign_steps`, `enroll_contact` and the date jobs. Seeded synthetic orgs, reps and customers. Concurrent-worker runner.
- **Reuse:** pytest, `services/job_lease`, `send_ledger`.
- **Risk:** low.
- **Migration:** none.
- **Rollback:** delete the tests.
- **Done when:** current behaviour (incl. R1-R4) is reproduced as failing tests.

### Phase 1: Execution reliability (M)
- **Scope:** R1, R2, R3, R4 (intelligent-mode hold instead of generic text), R6, R8, R10 indexes, fail-closed guards, a touch `events[]` log, the `touch_key` unique index, stale `processing` recovery, a campaign/enrollment status check at claim time.
- **Reuse:** the existing claim, ledger, gate and receipts.
- **Migration:**
  - Additive fields only.
  - Index build. Check the production row count first; build in the background.
  - Backfill `touch_key` for pending rows. Collisions are reported, not deleted.
- **Risk:** the first production deploy may re-surface stuck rows. Report them before any resend.
- **Tests:** all reliability cases from section 20 for the scheduler.
- **Rollback:** feature flag `CAMPAIGN_ENGINE_V2_GUARDS` (off = old behaviour); indexes harmless.
- **Done when:** the harness passes 100%, with 0 lost and 0 duplicate touches across 1,000 synthetic touches with crashes and timeouts.

### Phase 2: Permissions + unified model (M)
- **Scope:** R5 fixes, `services/campaign_policy.py`, `campaign_audit`, the `status` enum (`active` stays derived), `campaign_versions` + publish, assignment fields, and the active-edit policy with a diff preview.
- **Reuse:** `check_campaign_permission`, `get_data_filter`, `route_guard`.
- **Migration:** `status` from `active`; v1 snapshot for every campaign.
- **Risk:** UI that reads `active`. Keep it.
- **Tests:** a permission matrix per role + cross-org denial.
- **Rollback:** the fields are additive; the policy is behind a flag.

### Phase 3: Personal VA identity enforcement (S-M)
- **Scope:** `organizations.messaging_policy`; resolve the sender from the current contact owner at send time; a reassignment policy; persona field-drift fix (`tone_preference`); `ai_outreach_service` uses the persona; an output validator.
- **Decision needed first:** AI disclosure. The current prompt forbids it.
- **Tests:** identity-correct messages after reassignment; policy violations blocked.

### Phase 4: Just-in-time contextual generation (M)
- **Scope:** `campaign_touch.prepare()` (context pack with a token budget, suppression rules, generation with retry/backoff, validation, explanation refs), the `ai_usage` ledger, the hold or rep-task fallback, appointments and Contact Files facts in the pack, and a small concern classifier on inbound replies.
- **Reuse:** `relationship_intel`, `intelligence/reply_context`, `build_clone_system_prompt`, `thread_context`.
- **Tests:** the "Jeep / work truck / no history" trio produce different, fact-grounded messages. Acceptance criteria are scored by a rubric:
  - 0 fabricated facts.
  - ≥90% of messages reference at least one fact when one is available.
  - 100% of messages are in the right sender voice.
  - Length within the step's limit.
- **Cost:** about 2-3k input + 150 output tokens per message. Measure in `ai_usage` and confirm the price per 1k messages on real runs before any promise.

### Phase 5: Trigger and date reliability (M)
- **Scope:** anchor dates from purchase records (R7) with a missing-date flag; re-enrollment / multiple purchases; one date-event resolver covering date campaigns + date triggers + the Sold wizard (R11); Feb 29; the customer's timezone (R9); DST-safe local scheduling; per-org throttling.
- **Tests:** leap year, DST weekends, overlapping campaigns, updated dates.

### Phase 6: Voice-first builder (M-L)
- **Scope:** the `CampaignDraft` schema + patch validator; live and text Jessi tools; the timeline card; previews; the approval flow.
- **Depends on:** Phases 2 and 4.
- **Tests:** scripted conversations produce exact structured drafts; unauthorized activation is refused.

### Phase 7: Manual builder + templates (M)
- **Scope:** the same schema and screens as section H; intent-based templates (sold, service, anniversary, lead nurture).
- **Done when:** a non-technical manager builds a sold campaign in under 5 minutes in a moderated test.

### Phase 8: Monitoring + production hardening (S-M)
- **Scope:** the health dashboard, backlog and failure alerts, cost per org, spend limits, the touch inspector, removal of the dead `campaign_lifecycle.py`.

**Order rationale:** reliability and permissions come before any new interface (Phases 0-2). Identity and generation (3-4) make "every message personal" true. Triggers (5) make "when" correct. The builders (6-7) sit on a sound engine. Monitoring (8) makes it operable.

---

## J. Production validation plan
1. **Read-only production snapshot first** (deployer read): counts of active campaigns, enrollments, pending touches by status (including any stuck `processing`), the `INTEL_*`, `CONSENT_MODE` and `SENDER_POLICY_MODE` values, and index presence. No writes.
2. **Ship each phase behind a flag, off.** Deploy -> verify health endpoints -> enable for one internal test org with internal phone numbers only (Twilio test or own phones) -> 48 h watch.
3. **Canary checks:**
   - Every due touch reaches a terminal state or `held` with a reason within 15 min.
   - 0 duplicate `touch_key`s.
   - 0 sends to opted-out numbers.
   - The AI failure rate is under 2%, and failures hold rather than send generic text.
   - Cost per message is within budget.
4. **Expand:** one friendly dealership in approval mode first (managers review real generated messages), then auto mode.
5. **Rollback:** flip the phase flag (old path intact). Never bulk-resend after an incident: `unknown_outcome` touches are reviewed by a person.
6. **Alerts:** backlog over N due touches for more than 15 min, a provider error spike, an AI failure spike, and an org spend over its limit.

---

## Decisions needed from you before Phase 1
1. **AI disclosure:** keep the current rule ("never reveal AI"), or make it an org policy with a default disclosure (e.g. a one-time "Texts may be sent with help from my assistant")? This needs legal input; this audit is not legal advice.
2. **Missed-touch policy:** after an outage, should late touches send (within `max_late`), or always expire with a rep task?
3. **Reassignment:** should future touches follow the new owner's voice and number (recommended), or pause until the new owner confirms?
4. **Approval:** should approval be off by default with an org opt-in (recommended), or on by default for new orgs?
5. **Sold anchor when the purchase date is missing:** create a rep task and hold (recommended), or fall back to the tag date with a flag?
