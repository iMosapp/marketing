# Living Customer Intelligence & Timeline Accuracy Engine
## Part 1: Audit of what exists · Part 2: Recommended architecture (reuse-first)

Status: AUDIT + PROPOSAL ONLY (Oct 10 2026). Nothing implemented. Read-only review of /app/backend and /app/frontend.

---

## 0. TL;DR

- The raw material is already here: every customer touch is stored (texts, emails, calls with transcripts and clean summaries, voice memos with transcripts, web/ADF leads, campaign sends, purchases, vehicles/appraisals, tasks, appointments) and three extraction pipelines already turn text into structure (personal details, buying intent, appraisal findings).
- What is missing is a **time-aware fact layer**. Customer knowledge lives as overwritten string fields (`contacts.vehicle_interest`, `contacts.personal_details.*`, `contact_intel.summary`) with no event date, no source link, no confidence, no status. "Newest wins" today means "old is deleted."
- The timeline is assembled three different ways (`contact_events.py`, `crm_timeline.py`, `contact_ask.build_record`), and the one the rep sees is the least complete (no calls, voice memos, tasks, appointments, appraisal events).
- Jessi's context builders mostly do not tell the model what today's date is, so a 2024 interest and a 2026 inquiry read as equally current.
- The codebase already contains the exact pattern we need: `services/leadership/knowledge.py` (`ck_facts`: as_of vs created_at, source {kind, ref, excerpt}, status proposed/verified/disputed/retired, supersedes/superseded_by, stale_after per domain). The recommendation is to copy that pattern to a `contact_facts` collection, feed it from the existing writers, build ONE timeline service, and compute the five layers (Identity, History, Current State, Active Intent, Next Action) from facts in code, using one LLM call only to phrase the next action.

---

## 1. Audit: what exists today

### 1.1 Contact profile and custom fields
- Model `models.py:268 Contact`. Identity: first/last, phone/email + `phones[]`/`emails[]` with labels, address, `organization_name`, `occupation`, `employer`, `tags[]`, `source`, CRM ids (`external_id`, `dms_id`, `crm_id`, `customer_number`), retention fields, `created_at/updated_at/last_activity_at`.
- "Custom fields" = `personal_details: Dict[str, Any]` (free-form bag: spouse, kids, interests, pets, neighborhood, purchase_context, communication_preference, etc.) + `custom_dates[]`. No per-store field registry.
- Gaps: no `timezone`, `preferred_channel`, `language`, household/family links (only referral chain), no `do_not_contact` on the contact (consent lives in `routers/opt_in.py` + `sms_consent*` set by lead intake). Nothing in `personal_details` carries a date, a source or a confidence; the bag is overwritten in place.

### 1.2 The timeline (three implementations)
| Where | Unions | Used by | Notes |
|---|---|---|---|
| `routers/contact_events.py:253 get_contact_events` | contact_events, messages (via conversations), campaign_enrollments (+messages_sent), congrats_cards_sent, broadcast_recipients | Contact page `FeedTab` | Sorted by raw `timestamp`; each source fetched with its own limit then merged, so `skip` paginates incorrectly. **Excludes calls, voice notes, tasks, appointments, appraisal events, lead forms as first-class items.** |
| `routers/crm_timeline.py:63 get_public_timeline` | copy of the above | Public/CRM share link | Forked code, drifts from the first. |
| `services/contact_ask.py:69 build_record` | messages, call_logs (transcripts for last 6, summaries older), voice_notes, contact_events (noise filtered), tasks, contact_files, vehicles/appraisals, contact_intel | Ask Jessi, Live Jessi `focus_brief`/`_recall`/`_draft` | **Most complete union, every line dated absolutely and cited (`[T12]`, `[C3@4:12]`).** Not shown to the rep. Rebuilt on every call, 70k-char budget trims oldest first. |
- Frontend: `components/contact/FeedTab.tsx` (feed), `CallsTab.tsx` (calls + voice notes), `MemosSection.tsx`, `ContactTasksCard.tsx`, `FilesSection.tsx` are separate tabs/cards, so the rep never sees one chronological story.
- Event time vs recorded time: `messages.timestamp` is the send/receive time (good). `call_logs` mixes `timestamp` and `created_at` across readers. `voice_notes.recorded_at` is just a copy of `created_at`. `appointments.start_time` exists but appointments are not on the feed. `purchase_history[].date` (sale date) vs `created_at` (entry) is correctly separated (`services/sales.py`). Appraisal relationship entries separate `closed_at/submitted_at` from `created_at` (`services/appraisals/relationship.py:37`).

### 1.3 AI insights: Relationship Intel
- `routers/contact_intel.py` + `services/relationship_intel.py` -> collection `contact_intel` {contact_id, user_id, summary (one free-text blob with sections Quick Take / Key Facts / Communication Patterns / Personal Notes / Before Your Next Interaction), generated_at, data_points counts}. Inputs: contact fields, contact_events, messages, voice_notes transcripts (NOT call_logs/transcripts).
- Generated on demand; `stale` is computed at read time by comparing newest activity to `generated_at` (good mechanism, reusable).
- UI: `components/contact/SnapshotCard.tsx` (gold card: Drives, Last touch, Personal, the "Jessi" line = Before Your Next Interaction / Quick Take) and `IntelBriefingCard.tsx` (full brief + "JESSI NOTICED A CHANGE" accept/reject rows).
- Gaps: one blob, overwritten on regenerate, no per-fact source, date, confidence or status. Historical and current are mixed inside prose.

### 1.4 Extraction pipelines (already turning text into structure)
1. **Personal details**: `services/voice_intel.py extract_personal_details` (spouse, kids, interests, occupation, employer, vehicle_purchased, vehicle_color, trade_in, purchase_context, important_dates, pets, neighborhood, referral_potential, communication_preference). Runs on voice memos (`process_voice_note_intelligence`) and incrementally on new texts/calls (`process_conversation_intelligence`, cursor `contacts.conv_intel_cursor`). `merge_personal_details`: lists dedupe, scalars "newest wins"; identity-like fields (`CONFIRM_FIELDS`) that conflict are parked in `contacts.detail_suggestions` for the rep to accept/reject (`resolve_detail_suggestion`). Rejections remembered. **Closest thing to a fact-confirmation flow, but ad hoc on the contact doc; no event date, no quote, no confidence.**
2. **Buying intent**: `services/intent_detection.py` (gpt-4.1-mini) on every inbound text: {score 0-10, signals[], category, hot_summary} -> `conversations.intent_*`, `contacts.hot_opportunity/hot_score/hot_last_at` + tag `hot`; push when score >= store threshold; hourly `scheduler.py:2487 _dissolve_stale_hot_leads` clears after 7 quiet days. **Detection time only; nothing records what the intent was about as a durable fact; it overwrites.**
3. **Appraisal findings**: `services/appraisals/voice_findings.py` -> findings with `confidence` high/medium/low, verbatim `quote` validated against the transcript, `decision` pending/confirmed/dismissed, `voice_note_id`, edit history. **Best evidence/confidence pattern in the codebase, scoped to vehicle condition.**
4. **Voice memo people**: `routers/voice_memos.py` extracts `people[]`, matches to contacts, `new_people` computed at read time.

### 1.5 Conversations and topic episodes
- `conversations` {user_id, contact_id, status, ai_mode, last_message_at, intent_*}; `messages` {conversation_id, sender user|contact|ai|ai_draft|system, content (sometimes `body`), channel, type event|call_log|webchat_transcript, kind trade_link|..., is_lead_marker, timestamp}. Pydantic models are thinner than the stored documents (schema drift).
- `services/thread_context.py`: per-conversation topic episodes with triggers (web-chat handoff, trade link, `is_lead_marker`) and a prompt block that separates CURRENT TOPIC from "EARLIER, SEPARATE TOPICS ... background only" (`topic_block`). Computed per request, never stored, one conversation only. **This is the right instinct (current vs background) applied at the conversation level; it needs to exist at the customer level.**
- `services/lead_context.inquiry_prompt_block`: "the inquiry beats your background, the contact's history and any older messages" (precedence rule, not date-based).

### 1.6 Inbound leads and website forms
- `routers/lead_sources.py` (sources, timers, notify rules) + `routers/lead_intake.py` (ADF/XML, web forms). Matching by phone, then email, then exact name (`services/contact_match.find_existing_contact`); same-name/different-phone -> `possible_duplicate_of` flag, not auto-attached.
- Returning customer: lead lands inside the existing thread as a message with `is_lead_marker: True` ("New {source} lead from this customer · {what}"), contact_event `returning_lead`, and `contacts.vehicle_interest` / `vehicle` are **overwritten** with the new vehicle string (`lead_intake.py:627/723`). `inbound_leads` keeps the raw lead {source, vehicle_interest, comments, vehicle_raw, matched_inventory, received time}.
- Gap: no durable "active intent" object; the previous interest is gone from the contact; the contact page has no "new inquiry right now" banner (it is just a feed line).

### 1.7 Campaigns and engagement
- `campaign_enrollments` {contact_id, campaign_id, enrolled_at, messages_sent[{step, sent_at, body, channel}]}, `broadcast_recipients`, `congrats_cards_sent`, journey campaigns (`services/journey/`), quarterly Sold check-in writer. No per-send delivered/replied/clicked fields found; a reply is only visible as the next inbound message.

### 1.8 Purchases and vehicles
- `contacts.purchase_history[]` {id, title, category, date (sale date), notes, created_at, source}; derived `date_sold`, `vehicle`, `sold_count` (`services/sales.py`, 7-day correction window). Vehicles as relationship records with `ownership_status` owns/traded/sold/no_longer_owns/unknown, `trade_intent_status`, `ownership_updated_at/_by` (`services/appraisals/relationship.py`). Good event-time hygiene; no confidence/supersede semantics.

### 1.9 Tasks, reminders, follow-ups
- `tasks` {due_date, source campaign|system|rep, ...} (`routers/tasks.py`); contact page "Next Move" (`ContactTasksCard`), Home "Do This Next" (`app/(tabs)/home.tsx next-move-card`, `services/day_agenda.py`), contact `suggested-actions` (`contact_events.py:716`, rules: birthday, anniversary, sold milestones, 30-day re-engage, thank reviewer). Rules only; none of them read intent, calls or appointments.

### 1.10 Dedupe and merge
- `services/duplicates.py`: phone (last 10), email, exact/soundex name, flagged pairs. `merge()` re-points `contact_id` in 13 collections, copies missing scalars, unions tags, marks the loser `status: merged, merged_into`. **No merge audit document, no undo, `purchase_history` and `personal_details` are not merged.**

### 1.11 Jessi context and memory retrieval
- Live Jessi: `focus_brief` (vehicle + 6 tags + 700 chars of profile), `_recall` (profile[:4000] + last 6000 chars of timeline summarized to ~90 words), `_draft`. Only Live Jessi injects "now is <date>" (`live_voice.py:406`).
- Ask Jessi (`contact_ask.ask`): full `build_record`, absolute dates per line, citations, but **no "today is" anchor** in the system prompt.
- Memory search (`services/memory_search.py`): keyword/regex over messages, call transcripts, voice notes, notes, files, purchase titles, vehicle fields, tags; LLM only expands terms and verifies snippets; returns `when_label` + `when_spoken`. No embeddings anywhere. Tags have no dates.
- `update_contact` live tool writes directly to `vehicle_interest`/`personal` (overwrite).

### 1.12 Reusable building blocks (keep, do not rebuild)
- `services/leadership/knowledge.py` fact lifecycle (`ck_facts`): the template for `contact_facts`.
- `services/leadership/core.py audit` + `lt_usage` real token accounting; `services/command_center_ai.py complete/complete_json` with usage/cost recording (the only central wrapper; 36+ other call sites use `LlmChat` directly).
- `contact_ask.build_record` union + citation scheme -> becomes the unified timeline service.
- `thread_context.topic_block` current-vs-background framing; `lead_context` precedence rule.
- `voice_intel` extractor schema + `detail_suggestions` accept/reject UX ("Jessi noticed a change") -> becomes fact confirmation.
- `voice_findings` quote-must-exist-in-transcript rule -> evidence validation for every extracted fact.
- `contact_intel.stale` read-time staleness -> brief invalidation.
- `duplicates.MIGRATE` list -> add `contact_facts`, `contact_merges`.
- `utils/text_sanitize.no_em_dash`, `services/llm_models.CUSTOMER_TEXT_MODEL`.

### 1.13 Gap matrix (requirement 2 of the brief)
| Store | fact text | source link | occurred_at | recorded_at | last confirmed | confidence | status (current/hist/disputed/superseded) | links to conversations |
|---|---|---|---|---|---|---|---|---|
| contacts.personal_details | yes | no | no | updated_at only | no | no | no (overwrite) | no |
| contacts.vehicle_interest / hot_* | yes | no | no (detected_at) | yes | no | score only | no (overwrite, 7-day dissolve) | conversation only |
| detail_suggestions | yes | implied | no | yes | accept/reject | no | pending only | no |
| contact_intel.summary | prose | counts only | no | generated_at | stale flag | no | overwritten | no |
| purchase_history | yes | source string | yes (date) | yes | no | no | heuristic window | no |
| vehicles (appraisal relationship) | yes | appraisal id | yes | yes | ownership_updated_at | no | ownership status | yes |
| voice_findings (appraisal) | yes | quote + note id | no | yes | decision_at | yes | pending/confirmed/dismissed | yes |
| ck_facts (leadership) | yes | kind/ref/excerpt | as_of | created_at | verified_at + stale_after | proxy (kind+status) | yes + supersede chain | ref |

---

## 2. Recommended architecture (reuse-first)

### 2.1 Three additions, everything else is wiring
1. **`contact_facts`**: one time-aware fact collection (copy of the `ck_facts` lifecycle, customer-scoped).
2. **`services/timeline.py`**: one unified, typed, paginated timeline that every reader uses (FeedTab, public CRM link, Ask Jessi, Relationship Intel, Live Jessi).
3. **Customer Brief**: a computed view `GET /contacts/{id}/brief` that returns Layers A-E, assembled from facts in code; one cached LLM call phrases Layer E.

### 2.2 `contact_facts` document
```
{
  _id, contact_id, owner_user_id, store_id,
  layer: identity | history | state | intent,
  domain: vehicle_owned | vehicle_interest | buying_status | service | finance | trade |
          family | work | preference | contact_pref | milestone | experience | note,
  key: "vehicle.interest" | "vehicle.owned" | "buying.status" | "family.spouse" | "contact.preferred_channel" | ...,
  statement: "Submitted a website lead asking about a Ford F-150",      # one human sentence
  value: { year, make, model, trim } | { name } | { channel } | { status: shopping|not_shopping|bought } | free,
  occurred_at: ISO,  occurred_precision: exact | day | month | year | unknown,   # when it was TRUE / happened
  recorded_at: ISO,                                                            # when it entered our system
  confirmed_at: ISO | null, confirmed_by: {user_id, name} | null,
  confidence: high | medium | low,  confidence_score: 0..1,
  status: current | historical | disputed | superseded | retired,
  active_until: ISO | null,                 # intent layer only: when this signal stops driving the conversation
  outcome: purchased | declined | went_quiet | replaced | null,
  source: { kind: message | call | voice_memo | lead_form | appraisal | sale | rep | import | ai_inference | crm_sync,
            ref: <id>, conversation_id, quote: "verbatim excerpt", excerpt_at: ISO },
  supersedes: <fact_id> | null, superseded_by: <fact_id> | null,
  extractor: { name: "voice_intel", version: 2 } | null,
  created_at, updated_at
}
```
Indexes: `(contact_id, status, layer)`, `(contact_id, key, occurred_at desc)`, `(owner_user_id, status, active_until)`.

Rules:
- `occurred_at` defaults to the message/call/memo/lead timestamp, never to "now". The extractor is asked for a relative time when the text says one ("last January" -> month precision) and for tense (past / current / planned).
- Every extracted fact must carry a `source.quote` that exists in the transcript (reuse the `voice_findings._said` check); otherwise it is stored as `confidence: low`, `status: disputed` and waits for the rep.
- Nothing is ever deleted. Status changes are the only mutation; each change writes an `contact_fact_events` row (reuse `core.audit` shape) so the history of the knowledge itself is visible.

### 2.3 Supersession and status engine (code, not the model)
- **Same key, scalar value** (`vehicle.interest`, `buying.status`, `contact.preferred_channel`, `family.spouse`): a new fact with newer `occurred_at` and `confidence >= medium` marks the previous `superseded` (linked both ways). Lower confidence or older `occurred_at` -> new fact `disputed`, old stays `current`, rep is asked.
- **List keys** (`family.kid`, `preference.interest`, `vehicle.owned`): coexist as `current`; a later contradicting statement ("sold the Jeep") marks the matching one `historical` with `outcome`.
- **Intent layer**: a `vehicle.interest` from a lead form / inbound text is `current` with `active_until = occurred_at + INTENT_WINDOW` (proposal: 45 days). A purchase of the same vehicle -> `historical, outcome: purchased`. A "not shopping right now" statement supersedes every active intent (they become `historical, outcome: declined`), and itself expires after 90 days. Any newer buying signal reopens intent as a NEW fact (old ones are not edited).
- **Source precedence** when two facts conflict within a short window: customer's own words (message/call/lead form) > rep statement (voice memo, manual edit) > AI inference without a quote > imported CRM data.
- **Confirmation**: identity-like keys (today's `voice_intel.CONFIRM_FIELDS`) created by extraction are `current` only after the rep confirms (reuse the "Jessi noticed a change" rows); low-stakes keys (interests, hobbies) are `current` immediately with `confidence: medium` and show "unconfirmed" in the UI.
- **Staleness**: per-domain `stale_after` like `knowledge.FRESH_DAYS` (contact_pref 365d, work 365d, buying_status 90d, vehicle_interest 45d, family none). Stale facts stay `current` but are labelled "last confirmed <date>" and the brief asks the rep to re-confirm when relevant.

### 2.4 Writers (ingest adapters) - all hook into code that already runs
| Existing hook | Writes facts |
|---|---|
| `voice_intel.extract_personal_details` (voice memos, new texts, calls) | identity/state facts per field with quote + source; replaces direct writes to `personal_details` (keep mirroring the accepted value into `personal_details` for backward compatibility so nothing else breaks) |
| `intent_detection.process_inbound_intent` | intent fact `buying.signal` {score, category, signals} with `occurred_at` = message time, `active_until`; keeps `hot_*` mirrors |
| `lead_intake` returning/new lead | intent fact `vehicle.interest` from the form (vehicle, comments, source, inbound_lead id); stops overwriting `vehicle_interest` directly (mirror the newest active value instead) |
| `sales.record_sale` / Sold wizard | history fact `vehicle.owned` {date sold}, supersedes matching interest |
| `appraisals.relationship.set_ownership` / trade intent | state facts `vehicle.owned` status + `trade.intent` |
| rep edits (`PUT contact`, personal details editor, Jessi `update_contact` tool) | identity facts `confirmed_by` the rep, confidence high |
| `voice_memos` people / `new_people` | note facts `relationship.mentioned_person` |
| `duplicates.merge` | re-point `contact_facts`, merge `purchase_history` + `personal_details`, write `contact_merges` {primary, merged, by, at, fields_copied, counts} |
| backfill job (one-time) | purchase_history -> history; personal_details -> state/identity (`recorded_at` = contact.updated_at, confidence medium, source import); inbound_leads + current `vehicle_interest` -> intent (active only if < 60 days old, else historical); hot flags -> intent |

### 2.5 Unified timeline service
- `services/timeline.py build(db, contact_id, *, kinds, cursor, limit)` generalizes `contact_ask.build_record`'s union into typed items:
  `{id, kind: text|email|call|voice_memo|lead|event|task|appointment|campaign_send|sale|appraisal|fact_change, occurred_at, recorded_at, channel, direction, title, body, who, refs{conversation_id, call_id, note_id, lead_id, fact_id}, cite}`.
- Cursor pagination on `occurred_at` across the union (fetch each source with the same cursor bound, merge, cut). Fixes the `skip` bug.
- Readers: `GET /contacts/{id}/timeline` (FeedTab shows one story with kind filters), `crm_timeline` (same service, public projection), `contact_ask.build_record` (keeps its citation ids by mapping from items), `relationship_intel` (now sees calls too), Live Jessi recall.
- `fact_change` items make the knowledge itself visible on the timeline ("Oct 9: new interest recorded - Ford F-150 (website form)").

### 2.6 Customer Brief (Layers A-E)
`GET /contacts/{id}/brief` -> cached document `contact_briefs` {contact_id, as_of, version, layers, stale, cost}
- **A Identity**: current identity-layer facts (name, best phone/email with labels, preferred channel, language, household, employer) - code.
- **B Relationship history**: history facts + sales + appraisal events + milestone dates, newest first, each with date and source - code.
- **C Current state**: current state-layer facts not stale (owns, trade intent, life context), each "as of <date>, confirmed <date> by <who>" - code.
- **D Active intent**: intent facts with `status current` and `active_until > now`, newest first; the newest is "driving" - code. Empty when nothing is active ("no open buying signal; last one Mar 2026: not shopping").
- **E Recommended next action**: rules first, then one phrasing call:
  - rules (no model): new lead < 24h and no reply -> "reply now about <vehicle>"; active intent and no outbound in N days -> follow up; appointment upcoming -> confirm; unresolved disputed facts -> ask to confirm; anniversary/sold milestone (existing `suggested-actions`); nothing active -> relationship touch.
  - one `gpt-5.2` call through a shared wrapper (lift `command_center_ai.complete_json` into `services/llm_wrapper.py` so usage/cost is recorded) that receives Layers A-D with dates + the top rule, and returns `{what_to_do, what_to_say (<=2 sentences, no em dashes), why, cites[]}`; system prompt states `today is <local date>`, "the newest ACTIVE INTENT drives the conversation; HISTORY is background; never present a HISTORICAL or SUPERSEDED fact as current".
  - Cache until a new timeline item or fact for the contact arrives (write-through invalidation flag on the contact: `brief_dirty_at`), max age 24h.
- Replaces the single `contact_intel.summary` blob over time: SnapshotCard shows Layer D ("Right now") + Layer E ("Next"); IntelBriefingCard shows A-C with dates and status chips; "Jessi noticed a change" becomes the disputed-facts queue.

### 2.7 Prompt and retrieval rules (apply to every existing builder)
- Inject `today is <weekday, Month D, YYYY> (<tz>)` in `contact_ask`, `thread_context` callers, `memory_search.verify`, the reply writer; Live Jessi already does.
- Render facts with status labels: `CURRENT (as of Oct 9 2026, website form)`, `HISTORICAL (bought Jan 2024)`, `UNCONFIRMED (heard in a voice memo Jun 2025)`, `SUPERSEDED`.
- `build_record` profile section is replaced by the brief's Layers A-D; the timeline stays for evidence.
- Memory search also indexes `contact_facts.statement` and returns `occurred_at` + status so "who mentioned a Tesla" can say "Mar 2025, superseded by an F-150 inquiry this month".

### 2.8 Surfaces
1. Contact page: SnapshotCard -> "Right now" (active intent with source and date) · "Next" (Layer E) · "Known" (3 current state facts) · "History" chip count; the feed becomes the unified timeline with filters.
2. Thread header strip (`app/thread/[id].tsx`): one line "Active: F-150 inquiry (website, 2d ago) · Owns: 2024 Wrangler" and the next action.
3. Home "Do This Next": ranks by Layer E across contacts (newest active intents first).
4. Live Jessi `focus_brief`: Layers D + E + 3 facts instead of the 700-char profile slice; `update_contact` tool writes facts (confirmed by rep voice).
5. Inbox Hot chip: driven by active intent facts rather than the 7-day tag dissolve.

### 2.9 Guardrails (the brief's constraints)
- Agents never mutate core contact fields on their own: extraction writes facts; identity-like changes wait for the rep; mirrors to legacy fields happen only on confirmed/current facts.
- Every AI fact cites a quote that exists; no quote -> disputed.
- Real token usage recorded per call (`llm_usage` ledger, same shape as `lt_usage`); the brief shows cost per contact per month.
- No vector DB: keyword search + dated facts is enough at this scale (consistent with today's memory search).
- History is never deleted; status changes are audited.

---

## 3. Walk-through: the Jeep -> F-150 customer
Facts after ingestion (statement · layer · occurred_at · recorded_at · status):
1. "Bought a Jeep Wrangler" · history · 2024-01-14 (day) · 2024-01-15 · current (owned) -> source sale
2. "Considering a larger vehicle" · intent · 2025-06-03 · 2025-06-03 · historical, outcome went_quiet (expired after 45d) -> source call quote "we've been thinking about something bigger"
3. "Not currently shopping" · intent/buying.status · 2026-03-11 · 2026-03-11 · historical (superseded by #4) -> source text
4. "Website form: information about a Ford F-150" · intent/vehicle.interest · 2026-10-09 · 2026-10-09 · current, active_until 2026-11-23, supersedes #3 -> source lead_form #L123
Brief: A identity · B "Bought Wrangler Jan 2024; asked about bigger vehicle Jun 2025; said not shopping Mar 2026" · C "Owns 2024 Wrangler (as of Jan 2024, unconfirmed since)" · D "F-150 inquiry via website, today" · E "Reply today about the F-150: ask what changed since March and whether the Wrangler would be a trade; cite L123, T88".

---

## 4. Phased delivery (each phase testable on its own)
| Phase | Scope | Est. | Tests |
|---|---|---|---|
| 1 Fact store + writers | `contact_facts` + status engine + audit; adapters for voice_intel, intent_detection, lead_intake, sales, appraisal ownership, rep edits; backfill job (dry-run report first) | 2-3 days | pytest: supersession matrix, precedence, quote validation, backfill idempotence; the Jeep/F-150 scenario as a fixture |
| 2 Unified timeline | `services/timeline.py`, `GET /timeline` with cursor, FeedTab filters, crm_timeline + build_record + relationship_intel on the service | 1.5-2 days | pytest union/pagination; UI iteration (feed shows calls, memos, tasks, leads in one story) |
| 3 Customer Brief A-D + surfaces | brief endpoint (code layers), SnapshotCard "Right now/Next/Known", disputed-facts queue, thread strip line | 2 days | pytest layer assembly from facts; UI flows |
| 4 Next action (Layer E) + Jessi wiring | shared LLM wrapper with usage ledger, rules + phrasing call, cache/invalidation, Live Jessi focus_brief, Ask Jessi "today is", Home Do This Next ranking | 2 days | pytest with fake model; live check on 3 real contacts; cost report |
| 5 Merge audit + cleanup | `contact_merges`, purchase_history/personal_details merge, facts re-pointed, remove crm_timeline fork, schema notes | 1 day | pytest merge |

---

## 5. Decisions needed before building
1. Intent window: how long does a buying signal stay "active" with no follow-up signal? (proposal 45 days; "not shopping" lasts 90 days)
2. Who may confirm a fact: any rep who owns the contact, or managers too?
3. Extraction on every inbound text (cost: one small-model call per customer message, today's intent detector already does this) vs batched hourly per contact?
4. Backfill scope: all contacts, or active-in-last-24-months only? Mirror accepted facts back into legacy fields (recommended, keeps every existing screen working)?
5. Show disputed/unconfirmed facts to reps inline (greyed "unconfirmed") or only in the "Jessi noticed" queue?
6. Model for Layer E phrasing: gpt-5.2 (today's customer text model) or a cheaper internal model with gpt-5.2 only for customer-facing drafts?
7. The brief's Layer E spec was cut off in the request ("What the salesperson or AI assistant should say or do next, ..."): paste the remainder (Layer E details and any later sections) before Phase 3/4 is designed in detail.
