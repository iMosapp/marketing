# Jessi Relationship Isolation Audit

Question: when a rep asks Jessi about a person, can she reach another rep's private relationship data?
Method: code trace of every Jessi read path + synthetic run (`isolation_tests/`, tests 05-07, 14).

## 1. Required scenario — result

Synthetic setup: org X rep A and org Y rep B both saved "John Audit" with the same phone and email.
A's memo / notes: *Jeep event, drives a Rubicon*. B's memo / notes: *Ford dealership, daughter Zelda plays violin*.

| Check | Result |
|---|---|
| A asks Jessi (typed, same brain as voice) "Find the guy I met at the Jeep event. What do I know about him?" | **VERIFIED** — answer uses A's record; no B-only detail (no "Zelda", no "Ford") |
| Jessi keyword memory scan for A, "Jeep" | **VERIFIED** — 3 hits, all on A's record; B's record never appears |
| Same scan for B, "Jeep" | **VERIFIED** — 0 hits |
| A scans for B's private word ("Zelda") | **VERIFIED** — 0 hits |
| Rep A opens Jessi with B's contact id in focus | **VERIFIED** — refused (focus returns nothing) |
| **Store manager in org X** opens Jessi with org Y rep B's contact id in focus | **DEFECT** — the contact loads and Jessi's reply contains B's private detail ("Zelda") |

Enforcement is at the **query level** (Mongo filters on `user_id` / owner lists) for search, lookup and listing. It is a **role check in Python** (not scoped to org/store) for the focus contact — that is the gap.

## 2. Read paths and their scope

| Jessi capability | Function (file:line) | Filter | Scope | Status |
|---|---|---|---|---|
| Typed chat / voice brain entry | `POST /jessie/chat` `routers/jessie.py:34-40` | body `user_id` must equal the token's caller | caller | VERIFIED (code) |
| Chat history / session | `GET/DELETE /jessie/history/{user_id}`, `/jessie/session/{user_id}` `jessie.py:93-155` | no in-handler check, but the global middleware binds `{user_id}` | caller / manager scope | VERIFIED (403 for another rep) |
| Spoken-name lookup ("who is Todd Berry") | `live_voice._find` `services/live_voice.py:888-905` | `{"user_id": caller}` | own only (managers do not get their team here) | VERIFIED (code) |
| "Who mentioned X / the guy from the Jeep event" | `memory_search.scan/search` `services/memory_search.py:102-290` | `messages`/`call_logs` by `user_id ∈ owners`; `voice_notes`, notes, how_we_met, files by the owners' contact ids; sensitive files only for their uploader | own + the store's unassigned leads + stores whose lead sources route to the rep (`_dup_owners`, `contacts.py:607-616`) | VERIFIED (test 05) |
| Met-at groups ("everyone I met at NADA") | `services/met_at.py:34-37` | `{"user_id": caller}` | own | VERIFIED (code, iteration 404 tests) |
| Contact in focus (opened from a contact, or `contact_id` on chat) | `live_voice.focus_contact` `:354-364` used by `jessie_service._build_contact_context:384-412`, live session start `:475/486`, delegate `:1442/1587` | `find_one({_id})` then allow if owner **or role ∈ super_admin/admin/org_admin/store_manager/manager**, else shared conversation | **any manager role → any contact on the platform** | **DEFECT (H2)** |
| Person digest fed to the model | `_person_digest` `jessie_service.py:525-546` | voice notes by `contact_id` only | whoever can focus the contact | inherits H2 |
| Relationship brief | `GET /ai-outreach/relationship-brief/{user_id}/{contact_id}` `ai_outreach.py:116`; `services/relationship_intel.py:380-397` | contact by id, **no owner check** | any signed-in user with the id | **DEFECT (H1, verified leak)** |
| Voice memos list / play | `routers/voice_notes.py:384-404` (+`owned_contact`) | contact must be in the caller's scope; then every memo on that contact | owner + managers in scope | VERIFIED; memos follow reassignment by design ("Recorded by", delete = recorder or manager) |
| Customer facts / AI memory | `contact_facts`, `contact_fact_events` (`services/intelligence/*`) | keyed by `contact_id` | follows the contact | IMPLEMENTED / UNTESTED |
| Photo intelligence, documents | `contact_files` via `owned_contact` (`contact_files.py:58`); sensitive flag honoured in memory search (`memory_search.py:159-163`) | owner scope | owner + managers | IMPLEMENTED / UNTESTED |
| Campaign Builder / personalisation | `services/campaign_builder.py` (no contact data), scheduler AI writer uses the enrollment's contact | enrollment owner | owner | IMPLEMENTED / UNTESTED |
| Voice contact creation duplicate warning | `live_actions._possible_dups` `:522-545` | `user_id ∈ owners` | own + store leads | VERIFIED (iteration 403/404) |
| Background AI jobs (briefings, nudges, relationship health, transcript retry) | `scheduler.py` jobs iterate per user / per contact and write back to the same contact | per owner | no requesting user, no cross-user merge of content found | IMPLEMENTED / UNTESTED |

### Vector search, embeddings, caches
* **No vector store / embeddings exist** for contacts. "Semantic" search is keyword expansion by the LLM (`memory_search.terms_for`) + Mongo regex on owner-scoped collections + an LLM re-rank of already-scoped hits. There is no vector index that could bypass owner filters.
* Conversation memory: `jessie_sessions` keyed by `user_id`; live voice sessions keyed by `live_id` + `user_id`. No cross-user cache keys found.
* The model itself receives only what the backend fetched; prompt instructions are not relied on for isolation.

## 3. Where isolation can still break (Jessi-relevant)

1. **H2 focus contact role bypass** — any manager-tier account can pull any contact (notes, personal details, how-we-met, memo transcripts) into Jessi by id.
2. **H1 contact sub-routes** — relationship brief, timeline, share text/vCard and CRM preview return another company's contact data to any signed-in user who has the id (ObjectIds are not secrets: they appear in links and are partly sequential).
3. **C1 startup consolidation** — once records are merged across owners, the other company's events and notes sit on the winner's record; any `contact_id`-only read (timeline) shows them, and Jessi's focus digest reads the record's events / notes.
4. **H4 lead-intake re-routing** — a rep's personal contact can be reassigned to a teammate, and memos follow the contact, so the teammate's Jessi sees the first rep's private memos.
5. **By design (decision, not defect):** memory search includes the store's unassigned internet leads for every rep in that store, and managers see their reps' memos.
