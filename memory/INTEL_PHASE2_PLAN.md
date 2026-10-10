# Phase 2 plan: Intelligent Timeline, Reply In Your Voice, Intelligent Nudges

Grounded in a read-only audit of what already exists (file pointers below). Rule for every phase: reuse the existing surface, keep tenant checks, keep legacy behaviour when the flags are off, no autonomous sending changes, no new competing systems.

## What exists today (reuse map)

| Capability | Existing component | Reuse decision |
|---|---|---|
| Contact screen + tabs Profile / History | `frontend/app/contact/[id].tsx` (tab state :230, `loadEvents` :625) | Keep as the home of everything; add one strip, no new screen |
| History feed (date groups, icons, filters, load more) | `components/contact/FeedTab.tsx`, `HistoryTab.tsx` (chips all/texts/calls/memos/tasks/files), `utils/contactHelpers.tsx`, `utils/eventTypes.ts` | Keep; inject milestone rows from facts into the same groups |
| Timeline data | `contact_events` via `GET /contacts/{u}/{c}/events` + `utils/activity_log.log_activity` (idempotent on ref, icon/color/category table) | Keep as the "what happened" source; facts add "what it means" |
| Snapshot (Drives / spouse / kids / work / "Ask about") | `components/contact/SnapshotCard.tsx` -> `GET /contacts/.../personal-details` | Read from the fact state when present (legacy fallback), add unconfirmed marker |
| AI relationship brief card | `components/contact/IntelBriefingCard.tsx` -> `routers/contact_intel.py` + `services/relationship_intel.build_relationship_brief` | Keep the card; feed its "Before your next interaction" from `services/intelligence/brief.py` |
| Evidence viewers | Calls / memos transcripts only (`CallsTab.tsx`, `MemosSection.tsx`); `LearnedChip` shows a channel label, not a link | Build one small "why we think this" sheet that resolves a fact's `source` to the real record |
| AI reply drafting | `routers/ai_reply.queue_ai_reply` (:260-830) -> `ai_campaigns.get_contact_context` (:277) -> `relationship_intel.build_relationship_brief()["ai_context"]`; persona prompt `build_clone_system_prompt` (:172); sanitizer `utils/text_sanitize.clean_ai_text` / `no_em_dash`; queue `ai_reply_queue` with modes off / draft_only / auto_reply / auto_with_approval; approve/reject endpoints; draft card `app/thread/[id].tsx` :2573 | One injection point (`get_contact_context`); nothing else changes |
| Other drafters | `contact_intel.suggest_message` (own context builder :22-220), `lead_intake.generate_first_message` (:408, uses `auth._build_ai_clone_prompt`) | Point both at the same context + persona builder (removes two forks) |
| Salesperson voice | `users.persona.*` (tone, humor, emoji, phrases, never_say, banned_words) edited in `app/settings/persona.tsx`; no learned style | Keep persona; add optional style exemplars from the rep's own sent texts |
| Customer preferences / compliance | opt-out STOP handling (`twilio_webhooks.py` :814-845) + `ai_reply` opted_out cancel; DNC/windows in `services/compliance.py` | Unchanged; the brief adds suppression ("not shopping", "bought elsewhere") as a do-not-pitch input |
| Tasks | `db.tasks` with `idempotency_key`, `routers/tasks.py` (create :972, system tasks :1592 dormant 90 d) | All nudges become tasks through the same key convention |
| Per-contact suggested actions | `routers/contact_events.get_suggested_actions` (:716-845, birthday / anniversary / 30-60-90 / re-engage 30 d) | Merge intel nudges into this list |
| Feed / alerts | `routers/notifications_center._build_feed` (dedupe by type+contact), `push_notifications._compose_morning_brief` (:520), home `My 3` | Nudges appear through these; Morning Brief gets one "intelligence pick" line |
| Appraisal follow-ups | `services/appraisals/followup.py` (tasks deduped on appraisal_id + kind, reappraisal daily) | Untouched; the trade nudge reads its vehicle facts |

Gaps confirmed by the audit: no evidence link for AI-derived info on the contact screen, no "why this reply" on drafts, no lease / equity / purchase-timeline logic anywhere, Morning Brief is a plain task list.

## Phase 2A: Intelligent Timeline (first)

Goal: the History tab stays the History tab; a short "Now" strip above it answers four questions in plain words. No scores, no raw facts.

Backend (flagged by `INTEL_FACTS_INGEST`, read-only on legacy data)
1. `GET /api/intel/contacts/{id}/timeline`: one call returning four bands built from `state.build` + `next_action.recommend`:
   - **Recommended** (one card): topic, why (plain), suggested opening, 1-3 evidence refs.
   - **Active** (0-3 chips): "Asked about 2025 Grand Highlander, 2 days ago, website"; aging shown as "going quiet"; suppression shown as "Said not shopping (3 weeks ago)".
   - **Current** (compact facts for the Snapshot): drives, household, work, preferences; `confirmed_by` name/date or "unconfirmed" marker; never a number.
   - **Historical markers**: purchases, trades / sold, "bought elsewhere", interest closed, identity changes ("Employer changed: Zions Bank -> Intermountain Health"), each with a date and the fact id. Served in the same shape as `contact_events` items (`event_type: intel_milestone`, `category: milestone`) so `FeedTab` renders them in its existing date groups with the existing gold milestone styling.
2. `GET /api/intel/facts/{id}/source`: resolves `source.kind/ref` to the real record behind a belief, tenant-checked through the contact: message (thread + the exact excerpt), call (transcript lines around the quote), voice memo (transcript), lead form (fields), sale (purchase entry), appraisal (vehicle), rep (name + when). Returns `{kind, title, excerpt, at, link}` where `link` is the in-app route (thread, call, memo, vehicle).
3. Snapshot: `/contacts/.../personal-details` stays; the Snapshot card prefers `timeline.current` when present.

Frontend (`components/contact/`)
- `NowStrip.tsx` (Recommended card + Active chips, collapsed to two lines by default, "Why?" opens the source sheet) placed above `HistoryTab` in `[id].tsx`; hidden entirely when `/intel/config` says ingest is off (production unchanged).
- `FactSourceSheet.tsx`: bottom sheet with the excerpt, "Confirm" / "Not right" (existing `/intel/facts/{id}/confirm|dispute`), opens the source via `link`.
- `FeedTab`: milestone rows merged into `eventDateGroups` (parent merges `timeline.historical` with `events` by timestamp); tapping a milestone opens the sheet.
- `SnapshotCard`: unconfirmed dot + tap-to-source; no other visual change.
Tests: pytest for the timeline bands and the source resolver (all source kinds, tenant denial), testing agent on the contact screen (strip present for a contact with facts, hidden when flags off, sheet opens the excerpt, confirm/dispute round trip, History tab unchanged).

## Phase 2B: Reply In Your Voice

Goal: the existing Jessi / AI-reply draft leads with the customer's current reason for reaching out, uses history only when it helps, sounds like the rep, and tells the rep why.

1. **Context**: in `ai_campaigns.get_contact_context()` append a compact block from `services/intelligence/brief.build`:
   `RIGHT NOW (lead with this): <driving intent, when, via>` / `ALSO OPEN: ...` / `RELATIONSHIP (use only if it helps this reply): owns 2022 Jeep Wrangler since Mar 2024; asked about F-150 in 2025 (no outcome)` / `DO NOT: pitch (said not shopping 3 weeks ago | bought elsewhere) ; mention unconfirmed items as facts` / `WORTH ASKING: is the Jeep a trade?`. Same block flows to campaigns automatically; `contact_intel.suggest_message` and `lead_intake.generate_first_message` switch to the shared context (the lead itself is the driving intent on a first message).
2. **Voice**: one persona builder (`build_clone_system_prompt`; retire the duplicate in `auth.py`). Optional exemplars: the rep's last 15 manually sent texts (not AI, not campaign) as "write like these" examples, capped and sanitized; no new storage.
3. **Customer preferences**: opt-out and suppression already stop sends; the block adds "prefers texts / replied fastest in the evening" only when a `contact.preferred_channel` fact exists.
4. **Compliance**: unchanged (`clean_ai_text`, banned words, business number swap, approval modes, escalation). Autonomous sending is not touched: drafts land in `ai_reply_queue` exactly as today.
5. **Why this reply**: store `intel_rationale = {topic, why, evidence: [fact ids]}` on the queue document; the thread draft card shows one line ("Based on: F-150 inquiry 2 days ago, owns a Jeep since 2024") with tap-to-source via the 2A sheet.
Acceptance (automated, no sending): Jeep owner + new F-150 inquiry -> draft mentions the F-150 first and the Jeep only as a replace / trade question; "bought elsewhere" -> no pitch; "not shopping" -> acknowledgement only; unconfirmed appraisal ownership never stated as fact; every draft passes `no_em_dash`.

## Phase 2C: Intelligent Nudges

Goal: better timing and fewer, truer tasks; every nudge says whether it rests on a verified fact or a guess.

1. `services/intelligence/nudges.py` (flag `INTEL_NUDGES`): candidates from facts, each `{kind, contact_id, title, why, basis: verified|uncertain, evidence[]}`:
   - **May have sold / traded**: a disposed or disputed ownership fact without a replacement -> "Confirm what they're driving now" (uncertain).
   - **Possible trade**: a new inquiry while a confirmed owned vehicle exists -> "Ask if the Jeep is a trade" (verified); unconfirmed ownership -> softer wording.
   - **Future purchase timeline**: extraction of "next spring / after tax season / when the lease ends" into `milestone.date` (kind purchase_timeline) -> nudge 2 weeks before (verified if the customer said it, uncertain if inferred).
   - **Interest going stale**: intent phase active -> aging (day 30 of 45) -> "Follow up before it goes cold" (verified: the customer's own inquiry).
   - **Milestone approaching**: `milestone.date` + purchase anniversaries from sale dates -> merged into the existing date-trigger digest and `get_suggested_actions`.
2. **Write path**: `db.tasks` through the existing creation pattern, `source: "intelligence"`, `type: "follow_up"`, `idempotency_key: intel_{kind}_{contact_id}_{fact_id}`; skip when an open task of the same kind exists for the contact, when the contact is opted out or suppressed (except milestones), or when an AI draft is already pending in the thread. Suppress the generic 90-day dormant task when an intelligence nudge exists for the contact (removes the duplicate).
3. **Surfaces**: existing tasks list, notifications feed, Morning Brief (one "intelligence pick" line), contact page suggested actions; no new notification types.
4. **Scheduler**: daily job after `generate_daily_system_tasks`; the audit's dead duplicate silence-follow-up block in `ai_reply.py` is left alone (out of scope).
Acceptance: for the 7 scenario contacts the right nudge appears exactly once, re-running the job creates nothing, dormant and intel tasks never coexist for one contact, every task carries `basis` and evidence.

## Order, effort, gates
1. 2A Timeline (one working session; pytest + testing agent) -> owner review on preview.
2. 2B Reply (one session; offline draft acceptance tests, no sends) -> owner review of 10 real drafts in draft-only mode.
3. 2C Nudges (one session) -> owner review of the first daily batch in preview.
Each phase ships behind its flag; production stays identical until the flags are added. Backend-only phases need no EAS update; 2A and the 2B draft line touch the mobile bundle and will need one EAS update when (and only when) approved.
