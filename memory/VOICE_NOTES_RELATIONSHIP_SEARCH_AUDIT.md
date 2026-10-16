# I'm On Social: Unified Voice Notes, Relationship Search & Jessi Contact Creation
## Phase 1: read-only audit (Oct 16 2026)

No code, data or settings were changed. The evidence comes from three places:
- reading the code (file:line references below);
- read-only counts on the preview database;
- a throwaway in-process reproduction (`/tmp/vn_repro.py`). It ran against a temporary `harness_vnaudit_*` database, which was dropped afterwards. It used the real Jessi lookup code and the real LLM.

I did not read production data.

---

## 1. Root cause: why Jessi "can't see" a voice note recorded while creating a contact

### Short answer
The voice note is stored correctly. It is in two places: the contact's Notes text, and normally also a proper `voice_notes` row with a transcript. The problem is that **the Jessi chat (the Jessi screen, voice-to-chat, and the floating Jessi bubble) never reads either place.** Only the Live Jessi voice assistant and the contact "Ask Jessi" panel read them.

### Verified chain (reproduced)
| Question asked to the Jessi chat (`/api/jessie/chat`) | What Jessi was given | Result |
|---|---|---|
| "Tell me about Mike Peterson" | `No contacts found matching 'tell me  mike peterson'` | Jessi says she doesn't know Mike |
| "What do we know about Linda?" | `No contacts found matching 'what do we know  linda'` | same |
| "Who was the guy I met at NADA who owned three dealerships?" | nothing (no lookup ran) | made up or "I don't know" |
| "Find the woman I met at the golf tournament…" | `No contacts found matching 'the woman i met at…'` | same |
| "Who did I talk to about buying a Harley?" | `No contacts found matching 'who did i talk to  buying a harley'` | same |
| "Show me people I met in Las Vegas last February" | nothing | same |
| "Find the customer who mentioned their daughter was getting married" | the correct match (Linda) | works, because "find the customer who" is on the phrase list |

The same questions asked to **Live Jessi** (`memory_search.search`) found the right person every time: Mike from his Notes, Linda from her Notes, Tom from a voice memo, Mike again for "Las Vegas". **Live Jessi "tell me about Mike"** (`contact_ask.build_record`) includes his Notes and memos.

### The four defects in the Jessi chat
1. **The name lookup is broken.** `services/jessie_service.py:527-545` strips only the trigger word from the message ("about", "find"…). Whatever is left ("tell me  mike peterson") is used as a regex on first name, last name, phone and email, so it almost never matches. Jessi is then told **"No contacts found"**, so she confidently says the person doesn't exist.
2. **Even a successful lookup shows no relationship data.** The lookup returns name, phone, email and tags only (`jessie_service.py:540-541`). No notes, no voice memos, no personal details, no history.
3. **The open contact gets the same thin view.** When the rep is on a contact's page, Jessi gets `_build_contact_context` (`jessie_service.py:383-437`): phone, email, tags, "customer since", event types and tasks. **No Notes, no voice memos, no personal details.** So "what did I say about him?" on Mike's own page cannot be answered. It also filters `user_id == rep`, so store-owned or reassigned contacts return nothing.
4. **Searching by description only works for exact phrases.** The search that looks through notes and memos (`jessie_service.py:558-581` → `memory_search`) only runs when the message contains one of about 50 exact phrases. "Who was the guy I met…", "who did I talk to about…", "show me people I met…" and "find the woman…" are not on the list.

### Creation-time capture: secondary defects (verified in code)
The new-contact screen is `app/contact/new.tsx`. The legacy `app/contact/[id].tsx` with `id = new` duplicates the same logic.
- **The recording is transcribed twice.** `new.tsx:224` sends the audio to `/api/voice/transcribe` and pastes the text into the Notes field (`:227-231`). After Save, the same audio is uploaded again to `/api/voice-notes/{uid}/{cid}` (`:402-417`) and transcribed a second time (`routers/voice_notes.py:233`). That is two Whisper charges and two copies of the text that aren't linked.
- **A failed upload is silent.** `new.tsx:416` (`catch {}`) and `[id].tsx:1312` swallow any upload error. Then only the Notes text survives: no audio, no `voice_notes` row, no timeline event, and no fact extraction (reproduced: Linda got no personal details and no follow-up task).
- **Only the last recording is saved.** Starting a new recording clears the saved audio (`new.tsx:248`, `[id].tsx:1244`). The Notes text keeps both transcripts, but only the last audio is uploaded.
- **The recording length is lost.** `duration` is always `'0'` (`new.tsx:411`).
- Photo/business-card capture (`/contact/new?scan=1`, `components/scan/ScanWithJessiSheet.tsx`) only fills in the form. It has the same behaviour because it is the same screen.
- **Typed or dictated Notes are never mined for facts.** Only `voice_notes` rows go through `voice_intel` extraction (`routers/voice_notes.py:288-292`). `contacts.notes` written at creation or on edit is never extracted.

---

## 2. Current implementation map

| Area | Where | Notes |
|---|---|---|
| Contact create API | `routers/contacts.py:40-90`, model `models.py:354` | Only `first_name` is required (the UI also asks for a phone or email). The phone number is normalised. **Tags on create auto-enroll the contact in tag-triggered campaigns** (`contacts.py:84`). A memo nudge is scheduled. |
| Duplicate check | `GET /contacts/{uid}/check-duplicate` (`contacts.py:133`), `_dup_owners` (`contacts.py:575-584`), `services/duplicates.py` | Matches on phone or email only, not on name. |
| Voice note on an existing contact | `POST /voice-notes/{uid}/{cid}` (`voice_notes.py:305-321`) → `_process_voice_note` (`:212`) → `_store_note` (`:242`) | Audio stored in object storage, webm converted to m4a, Whisper `whisper-1` (`:170-198`). Inserts `voice_notes` {contact_id, user_id, transcript, kind, source, audio_url}, a `contact_events` row, and extraction. |
| Unattached memo ("record now, attach later") | `routers/voice_memos.py:140-190` (chunked upload, `contact_id: None`), attach `:270-320` | Attaching runs extraction and adds the timeline event. Unattached memos are invisible to search (`memory_search.py:166` drops hits with no contact). |
| Memo dictated to Live Jessi | `live_actions.add_note` (`services/live_actions.py:70-79`) → `create_text_memo` (`voice_notes.py:237`) | Same pipeline, `source: "jessi"`. |
| Transcription | `voice_notes._transcribe_audio` (`:170-198`) | **No retry and no failure status.** An empty transcript is stored silently. Preview: 4 of 20 notes are 3-minute recordings with empty transcripts. |
| Fact extraction | `services/voice_intel.py:60` extract, `:148` merge (new value wins for memos; identity fields queued as suggestions for texts and calls), `:272` process, `:348-387` follow-up task | GPT-5.2. Runs fire-and-forget (`asyncio.create_task`) with no retry or sweep. Preview: 14 of 15 transcribed notes are not marked `intelligence_done` (many are seeded). **"Next Tuesday" is stored as the literal text, and the follow-up task is always due in 3 days with a generated title** (reproduced: "Check in with Mike about rides Harleys", due Monday instead of Tuesday). |
| Living Intelligence facts | `services/intelligence/` (`ingest.py`, `facts.py`, `backfill.py`), flags `INTEL_FACTS_INGEST` etc. (ON in preview; production only when set to `production`) | `contact_facts` holds the source, confidence, status and conflicts (282 rows in preview). This is the right home for extracted facts. **Do not build a second memory system.** |
| Live Jessi tools | `services/live_voice.py:155` (TOOLS), `:762-787` (brain), `:1417-1534` (dispatch); actions in `services/live_actions.py` | Has find_person, recall_person, find_mentions, add_note, update_contact, set_reminder, tag_person, mark_sold (confirm step) and more. **No create_contact.** Risky actions use a PENDING-then-"yes" pattern (`live_actions.py:1-4, 135-150`). |
| Jessi chat | `routers/jessie.py:27` → `services/jessie_service.py:776` | Read-only: it pre-loads data from phrase triggers and has no tools. Used by `app/jessie.tsx` (typed and voice-to-text) and `components/JessieFloatingChat.tsx`. |
| Relationship search | `services/memory_search.py` (`terms_for` LLM keyword expansion, `scan` :108-176, `verify` LLM check) | Searches texts, call transcripts, voice memos, Notes, files, sold records and tags. **Does not search `personal_details`, `contact_facts`, the contact's creation date, or unattached memos.** Dates are only "the last N days", with no fixed month ranges. Voice memos are filtered by the *recording* user, so **memos recorded by the previous rep disappear after a contact is reassigned.** |
| Search infrastructure | — | Mongo regex only. No text index and no embeddings anywhere. `voice_notes` has only the `_id` index. |
| Permissions | `routers/database.get_data_filter` (REST); Jessi uses `_dup_owners` (rep + store + routed lead stores) | The Jessi chat filters on `user_id` only. Live Jessi uses `_dup_owners`. The campaign brief filters voice memos on `user_id` too (`relationship_intel.py:377-380`). |
| Campaign writer context | `routers/ai_campaigns.get_contact_brief` → `services/relationship_intel.build_relationship_brief` (Notes, personal details, last 5 memos, messages, events, facts rationale) | Already sees Notes and memos (reproduced). The gaps are facts that were never extracted and memos recorded by other users. Text is written at send time (good). |

---

## 3. Preview database counts (read-only)
- `voice_notes`: 20 total.
  - 9 unattached (no contact).
  - 4 with audio but an empty transcript (718 s of audio).
  - 1 under 10 characters.
  - 14 transcribed but never extracted.
  - 4 pointing at a contact that no longer exists.
  - 0 owner mismatches.
- No creation-time recordings exist in preview (no voice note within 5 minutes of its contact being created), so the creation path was reproduced in-process.
- 26 contacts have 40+ characters of Notes and no voice note. Most are lead-form text; these were never mined for facts.
- `contact_facts`: 282 rows. Facts flags are ON in preview.

Production volume is unknown. Phase 7 starts with a dry-run count script (read-only, needs approval) that produces the real numbers and cost.

---

## 4. Target architecture: one capture pipeline, one retrieval service

```
capture (any screen, Live Jessi, Jessi chat, memo inbox, scan)
   -> voice_notes row  (audio kept, ONE transcription, contact_id, user_id, recorded_at, source, kind,
                        transcript_status, intel_status)
   -> voice_intel extraction (existing)  -> contact_facts (existing ledger: source ref, quote, confidence, conflicts)
                                         -> personal_details projection (existing, legacy readers)
                                         -> follow-up task from real commitments (dated)
   -> contact_events timeline (existing)

retrieval (ONE service, used by Live Jessi, Jessi chat, Ask Jessi, campaign writer, trio preview)
   person lookup  : contact_ask.build_record          (already has notes + memos + timeline + facts)
   description    : memory_search.search              (+ personal_details, contact_facts, met-at/date ranges)
   scope          : _dup_owners / get_data_filter, by contact ownership (not memo author)
```

Principles:
- Notes typed or dictated into the Notes field go through the same extraction as memos (`source: "note"`, conflicts confirmed by the rep).
- Nothing AI-extracted becomes a verified fact. It stays `proposed` or `current` with a confidence score in `contact_facts`, and identity fields always need the rep's confirmation (the existing `CONFIRM_FIELDS` and `detail_suggestions`).

---

## 5. Design: Jessi contact creation (voice and text)
- **Phase 3, Live Jessi.** Add a `create_contact` tool to the brain. It extracts first and last name, phone, email, company, where they met (event, place) and when, plus relationship notes and a follow-up commitment. It never invents missing fields; a missing name is the only required question.
- **Duplicate check before confirming.** Check phone and email (existing `check-duplicate`), then the name within `_dup_owners`. If there is a likely match, Jessi asks: "You already have a Mike Peterson ending 0148. Add this to him instead?"
- **Confirmation.** It returns PENDING (the same pattern as `mark_sold`). Jessi reads back: "Add Mike Peterson, 602-555-0148, met at NADA. Save?" On "yes":
  1. `contacts.create_contact` with **no tags**, so no campaign auto-enrolls.
  2. `create_text_memo(source="jessi")` with the rep's original words, which runs the normal extraction and makes the contact searchable immediately.
  3. An offer: "Want a reminder to follow up Tuesday?" This uses `set_reminder` with a real date.
- **Partial contacts.** A name only is allowed (the API already accepts it). Jessi says what's missing.
- **Jessi chat parity.** Options are in §8 (question 1).
- **Phase 4 (updates).** `add_note` already exists for Live Jessi; name ambiguity is handled by `_resolve` with "the one with…". Jessi chat gets the same. Never silently overwrite verified fields; changes become suggestions.

## 6. Design: natural-language relationship search (Phase 5)
- Every Jessi surface uses one classifier, so there are no more phrase lists: person lookup → `build_record`; description → `memory_search`.
- `memory_search` adds:
  - **New sources:** `personal_details`, `contact_facts` statements, and unattached memo people (shown as "a memo, not filed yet").
  - **Time:** absolute date ranges ("last February" becomes Feb 1 to 28 of last year), using memo `created_at`, contact `created_at` and the fact's `occurred_at`.
  - **Where they met:** "met at" events and places from facts.
- Results keep the reason, quote and source, with links to `/contact/{id}` and to the note or thread. No embeddings for now: LLM-expanded keywords plus an LLM check already found all 5 test questions. Revisit (an Atlas vector index on `contact_facts`) only if recall fails on real data.

## 7. Campaign engine integration (Phase 6)
- `build_relationship_brief` keeps reading Notes, memos and facts, with two changes:
  - read memos and facts **by contact** within the contact's owner scope, not by memo author;
  - add a "How we met" line from facts.
- The trio preview's "What Jessi knew" reads the same brief.
- Writing stays at send time (already true), so anything added after enrollment is used.
- Personal details stay optional ("use only what fits"), as the writer prompt already says.

## 8. Phased plan (each step behind a switch: ON in preview, OFF in production; rollback = switch off)

| Step | What | Size | Tests |
|---|---|---|---|
| **A. Jessi can see it (fixes the reported bug)** | Jessi chat: real name resolution (reuse Live Jessi `_resolve`) + `build_record` dossier; the contact page context includes Notes, memos and facts; description questions go to `memory_search` through a small classifier; never inject "No contacts found" for non-names. | S | The repro above as pytest (7 questions × 3 capture cases), plus scope isolation (another rep or org sees nothing). |
| **B. Reliable creation-time capture** | The new-contact recorder uploads as an **unattached memo** (existing chunked upload, transcribed once, audio kept, real length). On Save it **attaches** (existing attach = extraction + timeline). Several recordings make several memos. If anything fails, the memo stays in the Voice Memos inbox and nothing is lost. Same in `[id].tsx` for new contacts. | M | Web + iOS flows; failed upload; two recordings; scan + memo; no double Whisper. |
| **C. One processing pipeline** | `transcript_status` / `intel_status` fields, 2 retries plus a scheduler sweep for failed transcription or extraction; Notes text goes through extraction; relative dates resolved from the recording date and rep timezone; follow-up tasks use the stated date; dedupe by fingerprint (existing). | M | Failed Whisper → retry → ok; duplicate events; "next Tuesday" → the correct date. |
| **D. Create a contact by voice (Live Jessi)** | `create_contact` tool + duplicate check + confirm + memo + reminder offer. | M | Full, partial, duplicate and ambiguous; no campaign enrollment; consent untouched. |
| **E. Text parity + updates** | Jessi chat can create and add notes (see question 1). | S–M | Same cases by text. |
| **F. Search upgrades** | New sources, date ranges, met-at, links. | M | Event, place, date, interest and conversation detail. |
| **G. Campaign retrieval** | Brief reads by contact scope plus how-we-met; the trio uses the brief. | S | A new memo after enrollment shows up in the next send. |
| **H. Backfill** | §9. | S code + approved run | Dry run, then execute with a confirm token. |

Recommended order: **A → B → C → D → F → E → G → H**. A alone fixes what reps feel today.

## 9. Historical backfill plan (Phase 7)
Reuse the `services/intelligence/backfill.py` pattern: `dry_run` (counts, samples, cost; persisted report) and `execute(confirm=…, run_id)` (batched, resumable, idempotent). It is gated by `INTEL_BACKFILL_EXECUTE`, which in production needs the literal value `production`.

Items, each with a per-item status and error log:
1. `voice_notes` with audio and an empty transcript → re-transcribe (retry 2, then mark `failed`).
2. `voice_notes` with a transcript of 10+ characters and no `intelligence_done` → extract. The existing `contact_facts` fingerprint prevents duplicate facts.
3. Contacts whose Notes were never extracted → extract with `source: "note"` and conflicts confirmed by the rep. Lead-form boilerplate is skipped.
4. Memos pointing at deleted or merged contacts → report only; re-point merged ones to the surviving contact.

Rules:
- Originals are never edited.
- Nothing is deleted.
- Tenant scope is by the contact's owner.

Estimated cost:
- Whisper: about $0.006 per minute.
- Extraction: one GPT-5.2 call per item, roughly $0.005–0.01.
- **Preview:** 12 minutes to re-transcribe (about $0.07), 14 memos plus about 26 Notes to extract (about $0.20–0.40). **Under $0.50 total.**
- **Production:** the dry run prints the exact counts and dollars before anything runs.

## 10. Rollback
- Every step reads a server switch (env var or `db.settings`), so the app falls back to today's behaviour without an app update. This matters for iOS builds already in reps' hands.
- New fields are additive.
- Backfill runs are logged per item with `run_id` and only add facts. They can be reversed by `run_id` (the facts ledger already records the extractor and the source).

## 11. Decisions needed before coding
1. **Jessi chat actions:** (a) route chat requests through the Live Jessi brain and tools (one tool system; recommended), or (b) add a separate tool layer to the chat.
2. **Creation-time transcript in Notes:** (a) stop pasting it into Notes; show it as a voice note card on the new contact (recommended, no duplicate), or (b) keep pasting it as well.
3. **Search depth:** (a) LLM-expanded keyword search plus an LLM check, no embeddings for now (recommended), or (b) add semantic vector search now.
4. **Production backfill:** dry-run counts first, then your go-ahead with the dollar figure.
