# Living Relationship Intelligence: production rollout runbook (Phase 1B)

Status: PREPARED, NOT EXECUTED. Nothing in production changes until the owner explicitly approves each step below. Deploying the code alone changes nothing: every write path is behind an environment flag that production does not have.

## 1. Environment variables (Deployments > Secrets)

| Variable | Value to set | What it switches on | Default when absent |
|---|---|---|---|
| `INTEL_FACTS_INGEST` | `true` | New events (leads, customer texts, voice memos, rep edits, sales, appraisal ownership, merges) write facts to `contact_facts` | off: no fact is ever written |
| `INTEL_LEGACY_PROJECTION` | `true` | Current facts are projected into the legacy fields today's screens read (`contacts.vehicle_interest`, `contacts.personal_details.*`, `occupation`, `employer`); the first projection per contact snapshots the previous values into `intel_legacy_snapshots` | off: legacy fields untouched |
| `INTEL_BACKFILL_EXECUTE` | `true` only during the backfill window, then remove | Allows `POST /api/intel/backfill/execute` (owner / super admin, body `confirm: "EXECUTE"`) | off: execute answers 403 |

Nothing else is needed. No new third-party service, no new database, no frontend change (no EAS update).

## 2. Activation sequence (one flag at a time, verify between steps)

0. **Deploy the code** with all three flags absent. Verify `GET /api/intel/config` (as the owner) returns `"flags": {"ingest": false, "legacy_projection": false, "backfill_execute": false}`. The app behaves exactly as before.
1. **Backup** (see section 3).
2. **Dry run** (read-only, no flag needed): `GET /api/intel/backfill/dry-run` as the owner (optionally `?store_id=<one store>` first). Read `contacts_scanned`, `facts_distinct`, `repeat_evidence`, `scalar_conflicts`, `contacts_whose_legacy_fields_would_change`, `legacy_fields_changed`, `samples[].projection_diff`. Expect `by_status` all `current` for anything inside its intent window and `historical` for quiet legacy interests older than 60 days / leads older than 45 days. The run is stored in `intel_backfill_runs` (`mode: dry_run`).
3. **Turn on `INTEL_FACTS_INGEST=true`** (redeploy / restart). From this moment new events create facts; nothing visible changes for reps. Watch logs for `[Intel]`, `[LeadIntake] facts ingest skipped`, `[Contacts] facts ingest skipped`, `[Appraisals] facts ingest skipped`, `[Intent] facts ingest skipped` for 24 hours. Every host flow wraps the adapter in try/except, so an engine error can only cost a fact, never a lead or a text.
4. **Pilot backfill, one store, projection still off**: set `INTEL_BACKFILL_EXECUTE=true`, then `POST /api/intel/backfill/execute {"confirm":"EXECUTE","store_id":"<pilot store>","batch":500}`. Run it a second time: `facts_written_total` and `reaffirmed_total` must be 0 and `duplicates_total` must equal the plan. Check a few contacts with `GET /api/intel/contacts/{id}/brief`. Legacy fields are untouched at this point (projection off), so the app is unchanged.
5. **Backfill the rest**: same call without `store_id`, `batch` 1000, repeat with the returned `run_id` until `done: true` (resumable from `checkpoint`). Re-run once for the idempotency check.
6. **Turn on `INTEL_LEGACY_PROJECTION=true`** (redeploy / restart), then run the execute once more (it writes no facts; it projects every contact that has facts and snapshots each one first). Compare `GET /api/intel/projection/snapshots` with the dry run's `contacts_whose_legacy_fields_would_change`; the changed contacts are exactly the ones whose legacy fields differed from their confirmed facts.
7. **Remove `INTEL_BACKFILL_EXECUTE`** (or set `false`). Leave ingest + projection on.

## 3. Database backup requirements

- Before step 4: a full `mongodump` of the production database (or the provider's point-in-time snapshot). The collections the backfill touches: `contact_facts`, `contact_fact_events`, `intel_backfill_runs`, `intel_legacy_snapshots` (all new) and, only with projection on, four fields on `contacts` (`vehicle_interest`, `personal_details`, `occupation`, `employer`, plus the marker `intel_projected_at`).
- Additionally export just the legacy fields for an exact-diff later: `mongoexport --collection contacts --fields _id,vehicle_interest,personal_details,occupation,employer`. In preview this was hashed before and after; the hash was identical with projection off and returned to identical after the rollback.

## 4. Rollback procedure

- **Projection only** (legacy fields back to their pre-projection values, facts kept): `POST /api/intel/projection/rollback {"confirm":"ROLLBACK"}` as the owner (or `{"confirm":"ROLLBACK","contact_id":"..."}` for one contact). Verified byte-exact in preview: keys that never existed are removed again, nulls that existed come back as nulls. Then set `INTEL_LEGACY_PROJECTION=false`.
- **Stop new facts**: set `INTEL_FACTS_INGEST=false`. The fact store simply stops growing; the API keeps reading what exists.
- **Remove the facts entirely** (only if ever wanted): drop `contact_facts`, `contact_fact_events`, `intel_backfill_runs`, `intel_legacy_snapshots`. No other collection references them.
- Legacy screens never depended on the new collections, so the app keeps working at every rollback stage.

## 5. Monitoring and error checks

- Backend log lines: `[Intel] legacy projection skipped for <contact>: <error>` (projection hiccup, fact already written), the five `facts ingest skipped` warnings named above, `[Backfill] vehicles skipped` (appraisal module unavailable; plan continues without ownership).
- `GET /api/intel/backfill/runs` (managers): every dry run and execute with counts and checkpoints.
- `GET /api/intel/projection/snapshots`: how many contacts have had legacy fields rewritten.
- Spot checks: `GET /api/intel/contacts/{id}/state` and `/brief` on 5-10 known customers; `needs_verification` lists unconfirmed ownership (appraisal records) and disputed / proposed AI guesses, which is expected.
- Health of existing flows: lead intake latency unchanged (the adapter adds one or two small writes), AI reply queue unchanged, campaign enrollments unchanged (the engine never writes to campaigns, enrollments, conversations or tasks).

## 6. Production backfill dry-run procedure (read-only, safe any time)

```
GET /api/intel/backfill/dry-run                 # whole tenant, owner / super admin
GET /api/intel/backfill/dry-run?store_id=<id>   # one store; store managers get their own store automatically
GET /api/intel/backfill/dry-run?limit=200       # first 200 contacts by _id
```
Writes only a report document into `intel_backfill_runs`. Compare `facts_distinct` (what execute will create) with `facts_total` (planned rows; the difference is repeat evidence that reaffirms instead of duplicating).

## 7. Validation checklist (same list the preview passed)

- [ ] Facts created equal `facts_distinct` from the dry run; second execute writes 0 and reaffirms 0
- [ ] `contact_facts` has 0 duplicate (contact, key, value) rows among `current` facts
- [ ] Legacy-field export hash unchanged while projection is off
- [ ] With projection on: changed contacts match the dry run; list fields keep their item types (strings stay strings); nothing blanked
- [ ] Unconfirmed appraisal ownership is NOT in `vehicle_purchased`; comment-only leads are NOT in `vehicle_interest`
- [ ] Store isolation: a manager of store B gets 404 on store A's contact facts; dry run as a manager is scoped to their store
- [ ] Contact screen renders for 3 sample customers; `GET /api/contacts/{user}/{id}` unchanged in shape
- [ ] Live event check: one real lead, one rep personal-details edit, one customer text -> facts appear, brief updates, legacy field follows
- [ ] Campaign enrollments / AI reply queue counts unchanged before vs after

## 8. Expected impact on existing customers and workflows

- Reps see nothing new until the Intelligent Timeline UI ships; the `/api/intel/*` endpoints are additive.
- Legacy fields change only where a confirmed fact (a sale, a rep confirmation, the customer's own inquiry) disagrees with or fills a legacy field. In preview that was 2 of 104 contacts (both fills: `occupation`/`employer` mirrored between the two places they live, and one `vehicle_purchased` corrected from a sale record while the old value is kept as an unconfirmed fact). Expect the same order of magnitude in production: single-digit percent, fills over rewrites.
- New website leads whose comment names no vehicle no longer have their comment text copied into `vehicle_interest` by this engine (the legacy intake code's own behaviour is unchanged).
- Campaigns, AI replies, tasks, conversations, notifications: untouched. The engine reads them; it never writes them.
- Database growth: roughly one fact per lead / sale / vehicle / personal detail, plus one event per change. Preview: 111 facts + 228 events for 104 contacts.

## GO / NO-GO recommendation

GO for steps 0-3 (deploy, backup, dry run, ingest on) as soon as the owner approves: zero visible change, facts start accumulating, and the production dry run gives the real numbers.
GO for steps 4-7 after the production dry run has been read: the preview pilot, full backfill, projection, rollback round-trip and the seven conflict scenarios all passed, and the two legacy-field changes it produced were fills from better sources.
NO-GO only if the production dry run shows `scalar_conflicts` or `contacts_whose_legacy_fields_would_change` far above the preview ratio (2 of 104); in that case review `samples[].projection_diff` first.
