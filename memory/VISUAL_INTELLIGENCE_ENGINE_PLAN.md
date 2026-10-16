# Visual Intelligence Engine: "Scan with Jessi" — audit + implementation plan

Status (Oct 16 2026): Phase B (business cards) BUILT + TESTED in preview (iteration_400), not deployed. Phases C-E not started.
Mission: a rep takes a picture, Jessi understands what matters, and the rep confirms what gets saved.

---

## 1. Existing capability inventory (what is already built)

| Area | What exists today | Where |
|---|---|---|
| Vision reader | One GPT-5.4 read per image/PDF. Returns type (business_card, vin, trade_in, id_document, insurance_card, credit_app, receipt, photo, document...), title, summary, visible, text, fields, facts (field + value + visible/inferred), sensitive, confidence. Image text is treated as content, never as instructions. PDFs: text layer for up to 25 pages; scanned PDFs are read from up to 3 rendered pages. HEIC supported. 25 MB cap. | `services/contact_files.py` `read_file`, `READ_SYSTEM`, `_pdf_extract` |
| Visual record + storage | `contact_files` doc per item: owner, contact, object-storage path, thumbnail, kind, source (upload/mms), sha256, reading, `applied` fields, sensitive flag (owner-only, locked, 30-day purge), timeline event `file_added`. | `services/contact_files.save_file`, `purge_expired` |
| Reuse / dedupe | The same image on the same contact reuses the earlier reading at $0. Duplicate Twilio deliveries are dropped by an atomic MessageSid check. | `save_file` sha256, `routers/twilio_webhooks.py` |
| Upload + capture | Chunked upload (120 x 900 KB). The app already has camera (`launchCameraAsync`), photo library and document picker (PDF + images) with scan hints (business card, VIN, trade-in). | `routers/contact_files.py POST /{user_id}/chunk`, `hooks/useContactFileUpload.ts`, `components/contact/AddFileSheet.tsx` |
| Review of extracted fields | FileDetailSheet: preview, Jessi's summary, tickable fields, "replaces X" warning, name fields never pre-ticked. Apply writes only the ticked fields; phone/email fill empty slots or are added as extra numbers/emails. | `components/contact/FileDetailSheet.tsx`, `contact_files.apply_fields` |
| Secure media | Non-sensitive files via `/api/images/{path}`; sensitive files via a signed 1-hour `/api/contact-files/open/{token}` link only. | `contact_files.py` |
| MMS photos | Jessi Photo Replies + Automatic Photo Intelligence (proposed details), rep alerts, Pause All, test-org rollout. | `services/mms_vision.py`, `routers/jessi_vision.py` |
| Cost reporting | `db.vision_usage`, one row per texted image / read upload (org, store, rep, source, analyzed/reused/failed, estimated cost, model). Photo Intelligence admin screen with daily, monthly, org, location and rep views. | `mms_vision.record_usage`, `routers/jessi_vision.py /usage`, `app/admin/photo-intelligence.tsx` |
| Relationship intelligence (rep-visible) | `contacts.personal_details` + `detail_suggestions` ("Jessi noticed" card, Add it / Not right, rep confirms; photo proposals append). Voice memos feed the same path via GPT-5.2 extraction. | `services/voice_intel.py` (`extract_personal_details`, `merge_personal_details`, `resolve_detail_suggestion`), `components/contact/IntelBriefingCard.tsx` |
| Relationship briefing | `generate_contact_intel` reads messages, events, calls, voice notes, tasks and contact_files into a cached briefing. | `routers/contact_intel.py` |
| Fact engine (newer) | `contact_facts`: time-aware layers, statuses including proposed. INTEL_* flags. No rep screen; feeds nudges only. | `services/intelligence/*` |
| Ask Jessi (one contact) | Citable record per contact: texts, calls, voice notes, events, tasks, contact_files text/summary, contact_intel, appraisal records. | `services/contact_ask.py build_record` |
| Memory search (all contacts) | "Who mentioned X": regex scan over messages, calls, voice notes, notes, contact_files text/summary/name/title, vehicle fields and tags, then one LLM check. Has a `days` filter. Live voice `find_mentions` uses it. **Not scanned:** `personal_details`, file `facts`, document dates. | `services/memory_search.py`, `routers/memory_search.py` |
| Contact search | Name, phone, email and tags only. | `GET /api/contacts?search=` |
| Duplicates | `check-duplicate` (phone last 10 digits / exact email, rep only, 5 matches) and org/store-wide `find_sets` (phone, email, sounds-alike name) + merge. | `routers/contacts.py:133`, `services/duplicates.py` |
| Contact create/update | `POST/PUT /api/contacts/{user_id}`: names, phone(s), email(s), employer, occupation, address, birthday, tags, notes, vehicle. **No "verified" flag or per-field source today.** | `routers/contacts.py`, `models.ContactCreate` |
| Tasks / reminders | `db.tasks`; `POST /tasks/{user_id}` (title, contact_id, due_date, type, appointment_type). **Automation risk:** appointment-type tasks from `source` manual or call_extraction can auto-text calendar invites and morning-of reminders to the customer; `campaign_send` tasks can auto-send. | `routers/tasks.py`, `services/calendar_invite.py` (`AUTO_SOURCES`, `INVITE_TYPES`) |
| Timeline | `contact_events` (file_added, detail_confirmed, intelligence_extracted, task_created...) merged into the contact feed. | `routers/contact_events.py`, `utils/event_types.py` |
| Tags | `PATCH /contacts/{user_id}/{contact_id}/tags`. **Automation risk:** a tag can enrol the contact in a campaign (`trigger_tag`), and "Sold" starts the sold workflow. | `routers/contacts.py:20, 1235`, `routers/sold_workflow.py` |
| Companies | No company/account entity. Company = the contact's `employer` field. | — |
| Appraisal vision | VIN (barcode + vision), odometer, photo/video damage inspection tied to an appraisal and contact. **Not cost-logged** in `vision_usage`. | `services/appraisals/readers.py`, `inspection.py` |

## 2. Reuse-versus-gap matrix

| Requested capability | Status | Reuse | Gap (new work) | Phase |
|---|---|---|---|---|
| One shared analysis service for MMS, camera, library, Files, documents | **Mostly exists** | `read_file` + `save_file` + `vision_usage` | Thin wrapper `services/visual_intel.py`. Extend the record with org, capture method, suggested actions and dates. Allow a record with no contact yet (a pre-contact scan). | B |
| Never analyze the same image twice | Exists per contact | sha256 reuse | Reuse across a rep's own pending scans, and when a scan is attached to a contact (copy the reading, no second call). | B |
| "Scan with Jessi" action | **Gap (UI)** | Existing pickers (camera/library/PDF), chunk upload | New sheet + review screen. Entry points: Add Contact, contact profile, Files "Add" sheet. | B |
| Business card -> create contact | **Gap** | Card extraction, `check-duplicate` / `find_sets`, `POST /contacts`, FileDetailSheet patterns | Pre-contact scan, duplicate warning, Create vs Update choice, attach the card, timeline event. | B |
| Business card -> update existing contact | **Exists** (on the contact's Files) | `apply_fields` + FileDetailSheet | Reachable from Scan with Jessi; fill-empty by default (see 7.3). | B |
| Document type + summary | Exists (type, summary, text) | `read_file` | Finer document types (quote, estimate, purchase order, invoice, service, spec sheet, form, screenshot) and extracted dates with what they mean. | C |
| Suggested tasks / reminders from dates | **Gap** | `db.tasks` create path | Action builder; tasks created with `source: "jessi_scan"` (not in AUTO_SOURCES, so they never auto-text) and no appointment type unless the rep picks one. | C |
| Screenshot intelligence | Partly (read as document/photo) | `read_file` (untrusted content rule) | Screenshot type, dates/commitments, proposed tasks and notes. Never sends anything. | C |
| Product / equipment / vehicle facts | Partly (MMS facts: vehicle_details, interests, personal_notes) | `propose_facts` -> `detail_suggestions` | Industry-neutral categories (tractor, excavator, powersports, home project...), visible brand/model text only. Optional "start a trade appraisal" link into the existing appraisal flow. | E |
| Personal relationship details (dog Cooper, restoring a bike) | Exists from voice memos and texted photos | `merge_personal_details`, `detail_suggestions` | Basis labels: customer-stated / visible / Jessi's guess. A scan adds the same proposals. | D/E |
| Review UI: Jessi found / suggested info / suggested actions | **Gap** | IntelBriefingCard + FileDetailSheet styles | One review screen: confirm, edit, dismiss, save selected. | B (cards), C (actions) |
| Search: "who was interested in a Kubota excavator" | Partly | `memory_search` (contact_files text/summary already scanned) | Add `personal_details` and accepted photo/scan facts to the scan. | D |
| "Who sent me a business card last week" | Partly | `memory_search` days filter over contact_files | Structured filter: scan_type + date + source (mms/upload/scan). | D |
| "Which customers have quotes that need follow-up" | **Gap** | — | Store document dates (expires/appointment) on the record; a "quotes due" list via memory search + tasks. | C/D |
| Cost / admin reporting | Exists | Photo Intelligence screen + `vision_usage` | New source values (`scan_camera`, `scan_library`, `scan_document`); optionally log appraisal reads too. | B (+E) |
| Settings / Pause All | Exists | `mms_vision.settings` | Scan follows Pause All. Rollout scope: see question 2. | B |

## 3. Proposed shared architecture (smallest change)

- **One record, no new engine.**
  - The `contact_files` document becomes the Visual Record.
  - New optional fields: `organization_id`, `capture` (camera | library | document | mms), `actions` (the suggested actions and the rep's decision on each), `dates` (date, what, basis).
  - `contact_id` may be empty while a scan is pending. It is owner-only, never listed on any contact, and auto-discarded after 30 days if never saved.
  - Saving to a contact just sets `contact_id`: same bytes, same reading, no second analysis.
- **One reader.**
  - `contact_files.read_file` (GPT-5.4, Emergent key) stays the only vision call.
  - `READ_SYSTEM` gains `doc_type` and `dates` and an industry-neutral `facts` vocabulary, all in the same call.
  - MMS replies, Files, Scan with Jessi and intelligence all reuse that one reading.
- **New thin service `services/visual_intel.py`:**
  - `scan(db, user, data, content_type, capture, contact_id=None)`: save + read (+ dedupe by sha256 across the rep's records) and log the cost.
  - `suggest(record, contact)`: plain-English "Jessi found", suggested information with basis/uncertainty, suggested actions. Pure rules over the reading, no extra model call.
  - `apply(db, user, record_id, selections)`: runs ONLY the ticked actions through existing code paths (contact create/update, file attach, `detail_suggestions` / `personal_details`, `db.tasks` with `source: "jessi_scan"`, `contact_events`).
- **New router `routers/visual_scans.py`:**
  - `POST /api/scan/{user_id}/chunk` (reuses the chunk assembler)
  - `GET /api/scan/{user_id}/{id}`
  - `POST /api/scan/{user_id}/{id}/duplicates`
  - `POST /api/scan/{user_id}/{id}/apply`
  - `DELETE /api/scan/{user_id}/{id}`
  - Same `require_user` + owner checks as contact-files.
- **Frontend.**
  - `components/scan/ScanWithJessiSheet.tsx` (pick camera / library / PDF via the existing `useContactFileUpload` pickers).
  - `components/scan/ScanReview.tsx` (Jessi found / Suggested information / Suggested actions).
  - Entry points: Add Contact header button, contact profile, AddFileSheet "Scan with Jessi" row.
  - No new tab.

## 4. Implementation phases

- **Phase A — Audit and architecture.** This document.
- **Phase B — Scan with Jessi + business card (smallest high-value).** Scope in §10.
- **Phase C — Documents and screenshots.**
  - Read `doc_type` + `dates` + summary.
  - Suggested actions: rep reminder before a quote expires (default 3 days before), an appointment from a service document (offered as a rep reminder; customer invite only if the rep picks it, with a warning), a product-interest proposal from a spec sheet, a relationship note from a screenshot.
  - Associate with the contact (company = employer field).
  - Sensitive documents: the only action offered is to attach the document privately.
- **Phase D — Relationship intelligence + search.**
  - Accepted scan facts go into `personal_details` (existing path).
  - `memory_search` also scans `personal_details` and accepted file facts, and gets structured filters ("business card in the last 7 days", "quotes expiring").
  - Ask Jessi and live voice `find_mentions` pick this up automatically.
  - Every claim is tested on fixture data before it is advertised.
- **Phase E — Broader products and personal context.**
  - Industry-neutral product/equipment categories and the basis labels "customer-stated / visible / Jessi's guess".
  - "Start a trade appraisal with this photo" hands off to the existing appraisal flow (no duplicate vehicle vision).
  - Optional: log appraisal vision reads in `vision_usage` so the cost report covers them.

## 5. Estimated AI cost impact
- One vision call per new image, about **$0.005-0.01**, the same as today's Files and MMS reads. A reused image costs $0.
- A PDF with a text layer is mostly text tokens: about $0.003-0.02 depending on length (up to 25 pages).
- A scanned PDF renders at most 3 pages in one call: about $0.01-0.03.
- Suggested actions are rules over the reading, with **no second model call**.
- Example: 20 reps x 5 scans a day x 22 days = 2,200 scans, about **$11-22 a month**.
- All of it shows in the existing Photo Intelligence report, broken down by source.

## 6. Required changes (by phase)
- **B backend:**
  - `services/visual_intel.py` (new)
  - `routers/visual_scans.py` (new)
  - `contact_files.save_file`: optional contact, org/capture fields, owner-wide sha256 reuse
  - `mms_vision.record_usage` source values
  - `jessi_vision` report labels
  - cleanup job for unsaved scans, reusing the daily purge
- **B frontend:**
  - ScanWithJessiSheet + ScanReview (business-card view)
  - 3 entry buttons
  - Photo Intelligence "Source" labels
- **C:** READ_SYSTEM `doc_type` / `dates`, action builder rules, task creation via the existing tasks code, review UI action rows.
- **D:** `memory_search` sources + structured filters, IntelBriefingCard basis labels.
- **E:** facts vocabulary, appraisal hand-off button, appraisal cost logging.

## 7. Data and security considerations
1. **Isolation.** Scans are owner-only until saved. After saving they follow the existing contact visibility rules (`get_data_filter`). Org is stored on the record and on every usage row.
2. **Sensitive documents** (ID, insurance, credit/financial):
   - The existing sensitive flag applies: owner-only, locked, purged after 30 days, no facts, no suggested actions except attaching privately.
   - Nothing goes into relationship intelligence. The timeline entry stays generic.
3. **Never overwrite verified details.** No verified flag exists today, so Phase B treats every existing non-empty value as verified:
   - A business card only fills empty fields.
   - Replacing an existing value needs an explicit per-field "Replace" tick that shows old -> new.
   - Name fields are never pre-ticked.
4. **No automatic messages.**
   - Tasks: scan tasks use `source: "jessi_scan"`, which is outside AUTO_SOURCES, so no auto calendar invite. They default to a rep reminder with no appointment type, so no customer reminder text.
   - Tags: Jessi never proposes a tag that starts a campaign or the sold workflow. Any tag the rep adds shows "this tag starts <campaign>" before saving.
   - Contact creation does not grant texting consent: the existing consent step on new contacts still applies.
5. **Prompt injection.** Everything inside images or documents is quoted, untrusted content (the existing READ_SYSTEM rule). Actions come from rules, never from instructions in the image.
6. **Media.** No raw media URLs are returned for sensitive files (signed open link only). Pending-scan bytes live under the rep's path.
7. **Database.** New optional fields and one new `source` value only. No migration of existing documents. An optional index on `contact_files {user_id, sha256}` needs your OK.
8. **Settings.** Pause All stops scan analysis: the file is kept unread and the rep is told "Jessi can't read photos right now".

## 8. Test strategy
- **Backend pytest (real GPT-5.4 on fixture images):**
  - business card -> new contact
  - card matching an existing contact (duplicate warning, update fills empty fields only)
  - card for an existing name with a different phone
  - quote PDF with an expiry date -> reminder task (`source jessi_scan`, no invite)
  - screenshot with a November revisit
  - screenshot with injected instructions
  - driver's license (private, no actions)
  - same image twice (reused, $0)
  - Pause All
  - org isolation (another org's rep can't read or apply)
  - unsaved-scan expiry
  - cost rows with the new sources
- **Regression:** MMS stage 1/2 suites, photo intel suites, contact-files suites, security 4B/4C, launch compliance.
- **Frontend:** the testing agent drives Scan with Jessi on web (upload a fixture card -> review -> Create Contact -> contact page shows the card in Files + a timeline entry), plus the existing contact-file sheet.
- **Device:** iPhone camera capture of a real card (owner).

## 9. Native app dependencies
- None new. `expo-image-picker` (camera + library) and `expo-document-picker` (PDF) are already installed. iOS camera and photo-library permission strings already exist.
- The change ships as an **eas update** (runtime 1.0.4); no native build is needed. Optional: reword the camera permission text to mention business cards, but that requires a native build, so skip it for now.

## 10. Recommended smallest Phase B
1. **Scan with Jessi** sheet (camera / photo / PDF) from **Add Contact** and the contact's **Files "Add"** sheet. The contact profile entry comes in C.
2. Backend scan endpoint: store + one GPT-5.4 read (reusing `read_file`) + cost row. Returns "Jessi found" + the card fields with confidence.
3. **Business card review:**
   - Shows the extracted name, company, title, mobile, office phone, email, website and address, each editable.
   - Possible existing contacts (org-scoped duplicate check on phone/email/name) appear with a warning.
   - Choices: **Create contact** (prefilled form; the existing consent step still applies) or **Update <existing>** (fill-empty by default, explicit Replace per field).
   - Saving attaches the card to the contact's Files with the same reading and logs a timeline entry ("Business card scanned").
4. Pause All respected; private documents are blocked from card actions.
5. Tests as in §8 for cards; testing agent on web.
6. Ships as Deploy + eas update. No DB migration.

Not in B: documents, screenshots, tasks, product facts and search changes (C-E).

## 11. Questions for the owner
1. Scope of Phase B as in §10?
2. Should Scan with Jessi follow the Automatic Photo Intelligence rollout (test org first), or be available to all reps at once?
3. Also put "Scan with Jessi" in the gold + menu?
