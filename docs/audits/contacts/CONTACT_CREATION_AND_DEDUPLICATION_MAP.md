# Contact Creation & Deduplication Map

Read-only trace of every code path that inserts or attaches a contact (`/app/backend`, tests excluded).
Scope legend: **Own** = caller's `user_id` only · **Scope** = `get_data_filter` (manager widens) · **Store** = store + its reps · **Tenant** = API-key org/stores · **GLOBAL** = all users of the platform.

## 1. Creation pathways

| # | Pathway | Function (file:line) | Owner assigned | Org / store written | Existing-contact lookup | Scope | Can touch another user's record? |
|---|---|---|---|---|---|---|---|
| 1 | Manual create (app form, also used by snap-a-photo, business-card scan and voice/Jessi saves) | `create_contact` `routers/contacts.py:39-72` | path `user_id` (middleware + `require_real_owner`) | `ownership_type` org (personal if `phone_import`) | none on the server; app calls `GET /{user_id}/check-duplicate` first (`contacts.py:165-202`) | Own | No |
| 2 | Voice / Jessi "save this person" | `live_actions.create_contact` `services/live_actions.py:557` → #1; dup warning `_possible_dups` `:522-545` | caller | as #1 | phone last-10 / email / close name in the rep's duplicate universe | Own + store leads | No (warns, waits for "yes") |
| 3 | Business-card / photo OCR | `jessi_vision.py`, `visual_scans.py` extract fields only → #1 | — | — | — | — | NOT a separate creation path |
| 4 | Phone-book sync / bulk import | `_prepare_import_rows` `contacts.py:1435-1500`, `POST /{user_id}/import` | path user | personal when source `phone_import` | own phones, last 10 digits | Own | No |
| 5 | CSV / VCF import | `routers/csv_import.py:470-537` | importer | personal | skip if any record in **Scope** ends with the same **last 7 digits** | Scope | No write, but a manager's import silently skips rows owned by teammates; different area codes can collide (L1) |
| 6 | Digital card / custom event "find or create" | `find_or_create_contact_and_log_event` `contact_events.py:953-1080` | path user | org | phone suffix, then email | Own | No |
| 7 | Public referral form | `public_landing.py:337-398` (`/p/refer/{user_id}`) | the salesperson in the public URL | store_id | exact phone | Own (of that salesperson) | No (public by design) |
| 8 | Internet lead / ADF / lead-source webhook (API key) | `process_inbound_lead` `lead_intake.py:553-645`; `lead_sources.py:528-592` | round robin rep, or the store id (unassigned) | store_id, org, lead_source_id | `find_existing_contact` phone/email/unique name (`services/contact_match.py:58-108`) | Store | **Yes, inside the store**: attaches to a rep's existing record (also a *name-only* match), fills blanks, and when the rep has been quiet ≥30 days re-routes and **reassigns that rep's contact — personal ones included** (H4) |
| 9 | Public API upsert (partner key) | `api_upsert_contact` `public_api.py:262-321` | `owner_user_id` in tenant or default rep | store_id, org | external id, then `find_existing_contact` | Tenant | **Yes, inside the tenant**: overwrites fields and may change `user_id` of a matched rep record, personal included (M5) |
| 10 | CRM inbound webhook (org secret) | `routers/webhooks.py:272-335` | resolved assignee in org | organization_id, store_id, owner_id | external_id + organization_id | Org | No |
| 11 | Incoming SMS from unknown number | `routers/twilio_webhooks.py:380-446` | the rep / inbox that owns the `To` number | — | `{"user_id": rep, status not merged, phone last-10}` | Own (of receiving rep) | No write — but **copies name + photo from any other org's contact with that phone** (M1) |
| 12 | Incoming SMS, legacy route | `messages.py:2748-2867` (`/messages/webhook/inbound`, signed) | inbox owner | shared_inbox_id | own first, then **GLOBAL by phone** for shared inboxes; adopts the matched record's owner for the conversation | GLOBAL | **Yes** (M3). Twilio numbers are provisioned to `/webhooks/twilio/incoming`, so this route looks unused, but it is still mounted |
| 13 | Shared-inbox lead webhook fallback (only when lead intake throws) | `shared_inboxes.py:337-349` | **none** (contact has no `user_id`) | — | `{"phone": e164}` | GLOBAL | Yes, returns another user's contact id (M3) |
| 14 | Partner agreement → contact | `add_agreement_contact` `partners.py:1745-1800` | body/header user | org | `{"$or": user_scope, "$or": or_clauses}` — duplicate dict key, **the owner clause is dropped** | GLOBAL | Yes: links the agreement to any user's contact with that phone/email (M2) |
| 15 | Website chat widget | `chat_widget.py:~391` | first admin found | admin's org | admin's own email/phone | Own (admin) | No (all widget leads go to one admin, L3) |
| 16 | Demo request (public) | `demo_requests.py:502`, `:820` | resolved owner / path user | org, store | first: owner-scoped; second: **none** | Own | No (duplicates only, L8) |
| 17 | Quote / subscription | `subscriptions.py:1417` | path user | org | phone / email | Own | No |
| 18 | Dialer lead promotion | `promote_lead` `services/dialer.py:813-830` | dialer session rep | org | `{"user_id": rep, "phone": exact}` | Own | No |
| 19 | New team member auto-contact | `admin_users.py:407` | acting admin | — | none | — | No (duplicates only) |
| 20 | Campaign workflows | — | — | — | — | — | NOT IMPLEMENTED (campaigns never create contacts) |
| 21 | Email inbound | — | — | — | — | — | NOT IMPLEMENTED as a contact creator |
| 22 | GoHighLevel sync | `services/ghl.py:135` writes to GHL only | — | — | — | — | NOT a local creation path |
| 23 | Background jobs | none create contacts; `_consolidate_phone_contacts` re-points them (below) | — | — | — | — | — |

Phone normalisation is implemented at least six times (`services/twilio_service.normalize_phone`, `twilio_webhooks.normalize_phone`, `contact_match.phone_digits` (last 10), `csv_import` (last 7), `admin.py:1789`, `utils/contact_activity.py:15`, `widgets.clean_phone`). Matching is mostly last-10-digit regex; CSV/VCF uses last 7.

## 2. Merge / consolidation / re-pointing functions

| Function | Trigger | Match | Scope | Writes | Reversible? |
|---|---|---|---|---|---|
| **`_consolidate_phone_contacts`** `server.py:1781-1886` | `run_once` at **every** backend start (`server.py:1889`; the lease only stops two replicas from running it in the same 3-minute window — preview lease counter shows 87 runs) | phone digits only; winner = record with a real name, loser = generic / "Lead (…)" name; two named records are skipped | **GLOBAL — any user, any org** | re-points `contact_id` in `conversations`, `messages`, `contact_events`, `campaign_enrollments`, `tasks`, `notes`, `call_logs`; loser gets `merged_into` but **status stays active**; then closes duplicate conversations per (user_id, contact_id) | Partly: moved rows keep their own `user_id`, so they can be traced back to the loser's owner |
| `duplicates.merge` / `merge_set` `services/duplicates.py:176-221` (`POST /contacts/{user_id}/merge`, Jessi "merge them") | user action | chosen ids | rep's duplicate universe (own + store leads); **super admin: any ids** | 15 collections incl. voice_notes, contact_facts; loser `status: merged` | Yes (record kept, `merged-history` endpoint) |
| `find_sets` `duplicates.py:140-175` | duplicates screen | phone last 10, email, sounds-alike name | own + store leads | read only | — |
| `normalize-phones` `contacts.py:2319-2399` (admin) | manual | (owner, normalised phone) | per owner | 10 collections; loser `status: merged` | Yes |
| `repair-merge` `contacts.py:2414-2434` | manual | `merged_into` | own | re-points stragglers | — |
| `merge_users` `admin_users.py:1641-1760` (super admin) | manual | two user ids | **no org boundary** | moves the whole book of the secondary user (13 collections) | No |
| Bulk transfer `shared_inboxes.py:493-592` (`POST /admin/team/bulk-transfer`) | manager | from/to user | **no scope check on from/to** (H3, verified) | contacts (personal too), conversations, tasks, enrollments | Logged in `bulk_transfers` |
| Legacy team transfer `routers/team.py:302-438` | — | — | no auth guard in code | — | **Not mounted** in `server.py` (404, verified) — dead code |
| `/webhooks/reassign-contacts` `webhooks.py:381-424` | any signed-in user | contact ids | **none** | sets `owner_id`, `is_unassigned` on any contacts (M4) | — |
| Lead intake re-route `lead_intake.py:589-595` | inbound lead | store match | store | sets `user_id` to round-robin rep | No record of the old owner except logs |
| `intelligence.on_merge` `services/intelligence/ingest.py:327-333` | after `duplicates.merge` | — | — | moves `contact_facts` + events, writes a merge record | Yes |

## 3. Startup consolidation — answers

* **Still exists?** Yes, `server.py:1781`.
* **Trigger?** Scheduled with `asyncio.create_task(run_once(...))` during app startup — so on every deploy, restart and (in preview) every hot reload.
* **Scope?** All contacts in the database with a phone (up to 50 000), no owner / org filter.
* **Phone alone?** Yes (digits, 10→11 with leading 1). Names decide only who wins.
* **Different users / orgs?** Yes. Synthetic replay: org Y rep B's auto-created "Lead (0142)" would be folded into org X rep A's "John" (`results.json → startup_phone_consolidation`). Read-only replay over the whole **preview** DB right now: 3 merges planned, **2 across different owners**; 1 preview record already carries the job's signature.
* **What is updated?** `contact_id` in 7 collections (list above); loser flagged `merged_into` only. **Not moved:** `voice_notes`, `contact_facts`, `contact_photos`, `campaign_pending_sends` (so pending campaign sends keep the loser id while their enrollment moved).
* **Exposure / corruption?** The winning owner's contact now carries the other company's conversations, events, tasks, notes and call logs. Routes that read by `contact_id` only (e.g. the contact timeline `contact_events.py:255`, verified to filter by contact id alone) would show them. The other owner's conversations, tasks and campaign enrollments now point at a contact they cannot open. **Whether this has happened in production is unknown** — production was not inspected; a read-only scan is proposed in the Gap Plan (step 1).
