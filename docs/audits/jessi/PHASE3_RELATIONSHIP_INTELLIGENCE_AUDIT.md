# Phase 3: Jessi Relationship Intelligence: architecture audit and implementation plan

Status: READ-ONLY audit (Oct 2026). No Phase 3 code has been written. Everything below needs your approval before any build starts.
Builds on: `memory/VOICE_NOTES_RELATIONSHIP_SEARCH_AUDIT.md` (steps A to H), `docs/audits/contacts/*` (ownership audit), and the
same-org isolation hotfix (`services/contact_scope.py`, `services/route_guard.py`).

---

## 1. Where things stand

**Already built and tested in preview (Oct 16):**
- One brain. Typed Jessi (`/api/jessie/chat`) runs the Live Jessi `delegate`, so people lookup, notes, reminders, search and every
  yes/no work the same by voice and by text.
- Contact creation by voice or chat (`create_contact`). It reads the contact back, warns about duplicates and saves only on "yes".
  It saves How we met and offers the follow-up reminder the rep mentioned.
- Capture. Every recording becomes a real voice note. Transcripts are retried (`services/transcript_retry.py`). Notes text goes
  through the same extraction as memos. Relative dates are anchored to the recording date.
- Memos follow the contact (filtered by contact scope, "Recorded by X"), Met-At groups, and the Campaign Builder.

**Isolation hotfix (not deployed yet):**
- Private relationship data stays with the owner, the owner's managers and super admins. That data is notes, personal details, How we met,
  memos and transcripts, facts, intel summaries and files. See `contact_scope.relationship_ok` / `contact_visible`.
- A shared thread (inbox, assigned, collaborator) only opens the conversation routes (`route_guard.CONVERSATION_CONTACT_ROUTES`).
- Jessi focus (`live_voice.focus_contact`) and AI Suggest (`messages.get_ai_suggestion_smart`) follow that rule.
- **Added in this session:** automatic AI reply drafts (`ai_reply.queue_ai_reply`). A teammate who is assigned the thread, or an unclaimed
  inbox thread, no longer gets a draft or "why this reply" built from the owner's private data. Test: `tests/test_ai_reply_private_context.py`.

---

## 2. Current architecture map

### 2.1 Sources (where private relationship data lives)
| Data | Storage | Written by |
|---|---|---|
| Notes | `contacts.notes` | Contact edit; dictation (`voice_intel.process_notes_intelligence`) |
| Personal details | `contacts.personal_details` (dict) | `voice_intel.merge_personal_details` (memo + notes paths) |
| How we met | `contacts.how_we_met` | `how_we_met.fill` (auto, only if empty) / `set_by_rep` (rep always wins) |
| Facts ledger | `contact_facts`, `contact_fact_events` | `intelligence/ingest.from_extraction` (right after the personal_details merge) |
| Voice memos | `voice_notes` (transcript, transcript_status) | Recorders, Live Jessi, memo inbox; `transcript_retry` |
| Photo / document facts | `contacts.detail_suggestions`, `contact_files` | `mms_vision.propose_facts`, Scan with Jessi |
| Intel summary (cached) | `contact_intel` | `contact_intel.generate_contact_intel` |
| Follow-ups | `tasks` | `voice_intel._ensure_followup_from_voice`, Jessi reminders |

### 2.2 Consumers (who reads it, and what protects it)
| Consumer | Builds its own context in | Privacy gate today |
|---|---|---|
| Jessi chat + Live Jessi focus | `jessie_service._person_digest`, `live_voice.focus_brief` | `focus_contact` -> `contact_visible` (OK) |
| Ask Jessi about a person | `services/contact_ask.build_record` | Router `_contact()` scope (OK); the builder itself trusts its caller |
| Memory search ("the guy from NADA") | `memory_search.scan` | Owner lists (`_dup_owners`) at query level (OK) |
| Met-At | `services/met_at.py` | `get_data_filter` (OK) |
| AI Suggest (rep taps Suggest) | `messages.get_ai_suggestion_smart` | `relationship_ok` (OK) |
| Automatic AI reply / approval drafts | `ai_reply.queue_ai_reply` -> `relationship_intel.build_relationship_brief` | `relationship_ok` / store lead rule (**fixed this session**) |
| Campaign writer (scheduler) | `ai_campaigns.generate_campaign_message` -> brief | Pending-send owner. Valid while sends follow the contact owner |
| Trio preview | `campaign_preview.py` | `get_data_filter` (OK) |
| Sold-tag outreach | `ai_outreach_service.gather_customer_context` | **None inside**. Safe only because the tag route is scoped |
| Intel summary | `contact_intel._gather_contact_context` | Route middleware only |

**Main finding:** six different functions each build "what Jessi knows about this person". None of them checks privacy itself; each one
trusts its caller. Today every entry point is gated, but the next new route or tool can leak by mistake. AI replies were missed by the
first hotfix pass for exactly this reason.

---

## 3. Gaps, ranked

| # | Gap | Risk | Evidence |
|---|---|---|---|
| G1 | No single relationship-context service. Privacy is enforced at each entry point, not where the data is read | **High** (future leaks) | §2.2; AI reply gap found this session |
| G2 | Two copies of extracted facts: `personal_details` (legacy dict) and `contact_facts` (ledger). Written one after the other, not atomically | Medium (drift, stale answers) | `voice_intel.py:311-391` |
| G3 | Search blind spots. `memory_search` does not search personal_details, contact_facts or unattached memos, and has no date ranges ("last February") | Medium (Jessi "can't find" things the rep told her) | `memory_search.scan:108-180` |
| G4 | Extraction has no retry. A failed extraction keeps `intelligence_done` empty for good (transcripts are retried, extraction isn't) | Medium | `voice_intel.py:333-358` |
| G5 | Sender identity. Campaign text is written in the voice of the pending send's `user_id`. `_move_book` moves sends with store leads, but a rep's personal contact never moves on a thread handoff. Admin bulk transfer, lead queue and user delete still need to be verified | Medium (wrong voice after reassignment) | `scheduler.py:1150`, `inboxes._move_book:675-688` |
| G6 | Persona drift. The profile API reads/writes `persona.tone_preference`, the writer reads `persona.tone`. `ai_outreach_service` uses no persona at all | Low-Medium | `profile.py:184,234`, `ai_campaigns.py:194-230` |
| G7 | Campaign messages don't record which facts they used (AI replies do, via `intel_rationale`) | Low (explainability) | `scheduler.py` writer path |
| G8 | Not backfilled: How we met from older memos/notes, never-extracted Notes, memos on merged contacts | Low (older contacts know less) | Audit step H, never run |

---

## 4. Target architecture

```
capture (unchanged: voice_notes -> voice_intel -> contact_facts (+ personal_details projection) -> tasks / timeline)

retrieval: ONE function every consumer calls
  services/relationship_context.py
    pack = await for_caller(db, caller_id, contact_id, purpose)   # purpose: jessi | reply_draft | suggest | campaign | intel | search
      .thread   name, phone, vehicle of interest, thread, consent       -> anyone who can see the thread
      .private  notes, personal_details, how_we_met, memos, facts,      -> ONLY relationship_ok(caller, contact)
                intel summary, files (sensitive = uploader only)
      .sources  ids of every fact / memo used (for "why this reply" and campaign explanations)
```

- Each current builder becomes a formatter over the same `pack`, so prompts barely change.
  The builders are `_person_digest`, `build_record`, `build_relationship_brief`, `focus_brief`, `gather_customer_context` and `_gather_contact_context`.
- **Contract test:** a test fails if any new code reads `contacts.notes / personal_details / how_we_met` or `voice_notes.transcript`
  outside `relationship_context.py` and the capture writers.
- Facts ledger = source of truth. `personal_details` stays as a projection for older screens (`INTEL_LEGACY_PROJECTION` already exists).
- Search v2: add personal_details, facts, unattached memos ("a memo, not filed yet") and date ranges, with the same owner lists. Still no
  embeddings (decision from the earlier audit).
- Identity at send time: sender = the contact's current owner, falling back to the org's fallback owner, else hold with a rep task.
  The writer always uses that owner's persona.

---

## 5. Implementation plan (each step behind a switch: ON in preview, OFF in production; rollback = switch off)

| Step | What | Size | Done when (tests) |
|---|---|---|---|
| **3.0 Guard rails** | Contract test (§4) + a consumer matrix test: each consumer x {owner, teammate on shared/assigned/collaborator/inbox thread, manager, other org, super admin}, using the same-org demo | S | Matrix passes on today's code (it documents current behaviour) |
| **3.1 One context service** | `relationship_context.for_caller` + migrate the 6 builders (switch `JESSI_CONTEXT_V2`) | M | Matrix still passes; prompt snapshots for the owner unchanged; teammate prompts contain no private tier |
| **3.2 Extraction reliability** | `intel_status` + retry sweep (same lease pattern as `transcript_retry`), single write path: facts first, projection second | S-M | Simulated LLM outage -> recovers; no duplicate facts (fingerprint) |
| **3.3 Search v2** | New sources + date ranges + "met at" from facts, results keep source + link | M | "Who did I meet last February", "the guy whose daughter plays violin" (personal_details), unattached memo hit; isolation probes 0 hits for teammates |
| **3.4 Identity at send time** | Resolve sender at send time; verify / fix enrollment moves on bulk transfer, lead queue, user delete; persona `tone` field fix; outreach uses persona | S-M | Reassign -> next touch in the new owner's voice and from their number; inactive owner -> hold + task |
| **3.5 Explanations** | Campaign touches store `sources` (fact / memo ids) like `intel_rationale` | S | Trio preview and touch inspector show "what Jessi used" |
| **3.6 Backfill** | `intelligence/backfill.py` pattern: dry run (counts + $), then execute with confirm token, resumable, by `run_id` | S + approved run | Preview dry run < $0.50; production dry run reported before any execute |

Recommended order: **3.0 -> 3.1 -> 3.2 -> 3.3 -> 3.4 -> 3.5 -> 3.6**. 3.0 and 3.1 also make the isolation hotfix hard to break later.

Rough size: 3.0-3.1 about 2-3 days, 3.2-3.4 about 3-4 days, 3.5-3.6 about 1-2 days including tests.

---

## 6. Decisions needed before coding
1. **Shared-inbox / assigned teammates:** when a teammate works the owner's customer, should Jessi's drafts know **nothing** private
   (today's hotfix rule, recommended), or should the owner be able to share specific notes with that teammate (an explicit "share notes"
   switch per contact)?
2. **Store-owned leads:** keep "every rep who can see the thread sees the lead's notes" (today), or limit it to the claimer once claimed?
3. **Reassignment voice:** after a contact moves, the next campaign text follows the **new owner** (recommended), or finishes the plan in
   the old rep's voice?
4. **Search depth:** keep keyword + LLM check (recommended), or add vector search now?
5. **Production backfill:** dry-run counts first, then your go-ahead with the dollar figure.

## 7. Rollback
Every step reads a server switch (env var or `db.settings`). New fields are additive. Backfill writes only add facts and can be reversed by `run_id`.
