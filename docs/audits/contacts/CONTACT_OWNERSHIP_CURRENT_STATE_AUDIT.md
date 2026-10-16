# Contact Ownership — Current State Audit

Audit date: Oct 16 2026 · Mode: READ-ONLY (no app code, index, permission, Twilio or record changes)
Evidence: source code at HEAD, preview MongoDB schema/indexes (read-only), and the synthetic isolation run in
`isolation_tests/` (two throwaway orgs, wiped afterwards — `isolation_tests/results.json`).
**Production data was NOT inspected.** Every statement about data is about the preview database only.

---

## 1. Data model actually in use

| Concept | Where | Notes |
|---|---|---|
| Contact id | `contacts._id` (ObjectId) | Stable, never reused. Every relationship row (`messages`, `conversations`, `contact_events`, `voice_notes`, `tasks`, `campaign_enrollments`, `campaign_pending_sends`, `notes`, `call_logs`, `contact_facts`, `contact_photos`…) points at it by the string `contact_id`. |
| Owning salesperson | `contacts.user_id` (string user id) | The ONLY field the app uses to decide who owns / sees a contact. Store-owned internet leads that are not yet assigned use the **store id** as `user_id` (`lead_intake.py:643`). |
| Creator / prior owner | `contacts.original_user_id` | Set on create; reused on deactivation / hard delete / transfer to remember the previous owner. |
| Ownership category | `contacts.ownership_type` = `org` \| `personal` | Set server-side at create (`routers/contacts.py:54-62`): **`personal` only when `source == "phone_import"`; every other in-app create (manual, voice, photo, card, Jessi) is `org`.** CSV/VCF import also writes `personal` (`csv_import.py:530`). Preview: 150 org / 47 personal. |
| Organization / store | Not stored on most contacts. Derived from the owner's `users.organization_id` / `users.store_id`. Lead-intake and API contacts also carry `store_id` (+ `organization_id` for some webhooks). | Org scope is always computed through the owner user, not the contact. |
| Status | `active`, `hidden` (owner deactivated), `merged` (+`merged_into`), `deleted` | Normal reads exclude merged/hidden via `NOT_MERGED` / `LIVE` filters. |
| Sharing | No internal "share with a teammate" grant. `contact_shares` = **public** link / vCard / text export for people outside the app (`routers/contact_share.py`). | Team access comes only from manager scope and shared inboxes. |

### Indexes (preview, read-only listing)
All `contacts` indexes are **non-unique and prefixed by `user_id`** (`user_id_1_phone_1`, `user_id_1_email_1`, …). There is **no globally unique phone or email index**, so the same phone/email can exist under any number of users (verified: two orgs, same phone + email → two records). Production indexes were not listed; startup index creation in code matches what preview shows.

## 2. Who can see a contact (enforcement points)

1. **Global identity middleware** (`server.py:161-200`) — default-deny for `/api`; `X-User-ID` must equal the Bearer-token caller; any `{user_id}` path parameter or `?user_id=` must be the caller or a user inside a manager's org/stores (`services/route_guard.py:111-135`). Verified: rep A on rep B's path → **403**.
2. **Per-handler data filter** `get_data_filter(user_id)` (`routers/database.py:98-120`) → `user`: own id only; `store_manager`: users of their stores; `org_admin`: users of their org; `super_admin`: **every user** (no extra gate, no read audit log).
3. **`owned_contact()`** helper (`services/contact_scope.py:9-24`) — the contact must be inside `get_data_filter(user_id)` (or a shared/assigned thread). Used by voice notes, contact files, conversations, re-extract… but **not** by many contact sub-routes (see Security Findings H1).

Listing (`GET /contacts/{user_id}`, `contacts.py:300-343`): a rep sees only their own; managers get `view_mode=team` (their scope) **excluding `personal`**. `check-duplicate` and `/search/{user_id}` follow the same scoping (verified for check-duplicate).

## 3. Lifecycle

| Event | Current behaviour | Evidence |
|---|---|---|
| Create | Always a new record under the caller; no server-side dedupe on manual create (5 parallel creates → 5 records). The app warns first through `check-duplicate` (own records only). | `contacts.py:39-72`, test `concurrent_create_same_phone` |
| Reassignment | (a) `POST /admin/team/bulk-transfer` (managers): moves contacts **incl. personal**, conversations, tasks, enrollments. (b) Lead intake "returning customer" re-routes a quiet rep's contact to round robin. (c) Public API / CRM webhooks may set owner. Voice memos follow the contact (by design, "Recorded by" label). | `shared_inboxes.py:493-592`, `lead_intake.py:569-595`, `voice_notes.py:384-404` |
| Rep deactivated | Personal contacts → `hidden` (still owned by the departed user, invisible to the org). Org contacts keep `user_id`, are stamped `user_deactivated`, stay visible to managers; a manager must bulk-transfer them. Reactivation un-hides. | `admin_users.py:740-825`, `967-1000` |
| Rep hard-deleted (super admin) | All contacts → `user_id: "unassigned"`, `original_user_id` kept. | `admin_users.py:853-878` |
| Rep changes org/store | No code moves their contacts; contacts follow the user record, so the new org's managers gain scope and the old org loses it. | searched admin_users / team / user_lifecycle |
| Contact deleted | **Hard delete** of the contact + `contact_photos`; voice notes, events, messages, conversations, tasks stay orphaned (verified). | `contacts.py:1353-1410` |
| Merge (user action) | Owner-scoped duplicates screen + Jessi "merge them": records move, loser → `status: merged`. Super admin may merge any two ids. | `services/duplicates.py:140-221` |
| Merge (automatic) | **`_consolidate_phone_contacts` runs on every backend boot / deploy over ALL contacts, grouped by phone only, across users and orgs.** | `server.py:1781-1889` — see Critical finding C1 |
| Export | No bulk contact export endpoint. Per-contact public share link / vCard / text. | `contact_share.py` |

## 4. Answers to the brief's questions

| Question | Answer |
|---|---|
| Stable unique id per contact? | Yes (`_id`). |
| How is the owning salesperson identified? | `contacts.user_id`. |
| How is the owning org identified? | Indirectly via the owner's `users.organization_id`/`store_id` (some lead/API contacts also carry `store_id`). |
| Can many users store the same phone? | **Yes** — verified across two orgs. |
| Can many orgs store the same person? | **Yes** — verified. |
| Are contacts ever merged automatically? | **Yes** — the startup consolidation job, globally (C1). Lead intake / public API also *attach* an incoming lead to an existing store contact (store-scoped) instead of creating a new one. |
| Is duplicate detection scoped correctly? | Interactive tools: yes (owner / store). Startup consolidation: **no (global)**. Partner-agreement contact: **no (global, dict-key bug)**. Shared-inbox webhook fallback + legacy messages webhook: **no (global)**. |
| Globally unique phone/email indexes? | None found (preview). |
| Salesperson changes org? | Contacts follow the user record; nothing is copied or split. |
| Contact shared with an employee? | No internal sharing primitive; access comes from manager scope, shared inboxes, or ownership transfer. |

## 5. Personal vs organization vs shared — current business rules (as coded)

* **Personal** = phone-book / CSV / VCF imports only. Never in a manager's team list, hidden (not transferred) when the rep leaves, excluded from the legacy team transfer — but **included** by the active admin bulk transfer and by lead-intake re-routing.
* **Organization** = everything else created in the app, including contacts a rep creates by voice, photo or card with their own private memos. Visible to managers in scope; stays with the dealership when the rep leaves.
* **Shared** = shared-inbox conversations (team-visible by design) and store-owned leads (`user_id = store_id`, visible in every rep's duplicate/memory universe for that store).

> Decision needed (not a defect): the brief describes rep-owned relationships, while the code treats most in-app contacts as dealership-owned. This audit does not change that rule; see Gap Plan, Decision D1.
