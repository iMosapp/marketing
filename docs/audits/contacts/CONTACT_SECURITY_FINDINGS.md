# Contact Security Findings

Status legend: VERIFIED · IMPLEMENTED / UNTESTED · PARTIAL · DEFECT · NOT IMPLEMENTED · UNKNOWN.
"Verified" = reproduced on synthetic data in preview (`isolation_tests/results.json`). Production not inspected.
No customer PII, credentials or message content is included here.

## Prioritised findings

| ID | Feature | Current implementation | Status | Risk | Evidence | Smallest recommendation | Impact | Effort |
|---|---|---|---|---|---|---|---|---|
| **C1** | Automatic merging | `_consolidate_phone_contacts` merges contacts **across all users and orgs** by phone on every boot / deploy; re-points conversations, messages, events, enrollments, tasks, notes, call logs; loser stays `active` | **DEFECT** | **Critical** | `server.py:1781-1889`; replay: synthetic cross-org fold = true; preview DB: 2 cross-owner merges planned now; no test covers it | **Stop scheduling it** (remove the `create_task` line or put it behind an env flag that defaults off). Legit cleanup already exists per owner (Duplicates screen / Jessi). Then run the read-only production scan and approve an un-merge plan | None lost: per-owner duplicate tools stay | XS |
| **H1** | Contact sub-route ownership | Several handlers load the contact by `_id` alone; the middleware only checks the `{user_id}` in the path, so any signed-in user can use *their own* id with *anyone's* contact id | **DEFECT** | High | Verified reads (another org's synthetic contact): `GET contacts/{me}/{x}/personal-details` (private notes returned), `/events` (timeline), `/share/text`, `/share/vcard`, `GET ai-outreach/relationship-brief/{me}/{x}`, `GET crm-push/{me}/{x}/preview`; `photos/all` and `campaign-journey` answer 200 (read by id only). Verified writes: `PATCH personal-details`, `PATCH toggle-automation`. Static scan lists 34 candidate routes (Gap Plan step 3) | Add the existing `owned_contact(db, user_id, contact_id)` check at the top of each listed handler (no new helper) | Fixes leak; owners and in-scope managers unaffected | S–M (≈20 handlers) |
| **H2** | Jessi contact in focus | `focus_contact` lets any `super_admin/admin/org_admin/store_manager/manager` load **any** contact | **DEFECT** | High | `live_voice.py:354-364`; verified: org X store manager → org Y contact → Jessi reply contained B-only detail | Replace the role test with the caller's `get_data_filter` scope (same rule as contact GET) | Managers keep their own org/stores | XS |
| **H3** | Admin bulk transfer | Any store manager / org admin can move **any** user's whole book (personal contacts too) to any user, no org/store check on `from`/`to` | **DEFECT** | High | `shared_inboxes.py:493-592`; verified: org X store manager moved org Y rep's contact (200) | `assert_self_or_scoped_manager(caller, from_user_id)` and `(caller, to_user_id)`; optionally keep personal contacts out unless asked | Legit in-scope transfers unchanged | XS |
| **H4** | Lead intake re-routing | A returning internet lead that matches a rep's contact (phone, email or *unique name*) is re-routed after 30 quiet days and the **rep's contact is reassigned** — `ownership_type` not checked | DEFECT (code) / UNTESTED | High | `lead_intake.py:553-595` | Never reassign `ownership_type == "personal"`; for a name-only match, do not reassign (create / flag instead) | Dealer round robin unchanged for org contacts | S |
| **M1** | Inbound SMS enrichment | New "Lead (xxxx)" for rep B copies **name + photo** from any other org's contact with that number | DEFECT (code) | Medium | `twilio_webhooks.py:405-428` | Limit the enrichment lookup to the receiving rep's org/store (or drop it) | Fewer auto-names for brand-new numbers | XS |
| **M2** | Partner agreement → contact | `{"$or": user_scope, "$or": or_clauses}` — Python keeps only the second key, so the match is global | DEFECT (code) | Medium | `partners.py:1759-1763` | Use `{"$and": [{"$or": user_scope}, {"$or": or_clauses}]}` | — | XS |
| **M3** | Global phone match in inbox fallbacks | Shared-inbox webhook fallback (ownerless contact, global match) and legacy `/messages/webhook/inbound` (global match for shared inboxes, adopts the other record's owner) | DEFECT (code) | Medium | `shared_inboxes.py:337-349`; `messages.py:2830-2867` | Scope both to the inbox's assigned users / store; retire the legacy route if unused | — | S |
| **M4** | Reassign endpoint | `POST /webhooks/reassign-contacts` sets `owner_id` / `is_unassigned` on any contact ids for any signed-in user | DEFECT (code) | Medium | `webhooks.py:381-424` | Managers only + restrict ids to their scope | `user_id` (visibility) is not changed, so integrity only | XS |
| **M5** | Public API upsert | Tenant-scoped match may overwrite a rep's **personal** contact fields and change its owner | PARTIAL | Medium | `public_api.py:283-310` | Skip personal records (or only fill blanks) | — | XS |
| **M6** | Contact delete | Hard delete; voice notes (+audio), events, messages, conversations, tasks left orphaned | PARTIAL (verified) | Medium | `contacts.py:1353-1410`; test 13 | Decision D3: soft delete, or cascade the dependent rows | — | M |
| **M7** | Super admin reach | Super admin sees / merges / moves anything; no read audit trail (impersonation headers are logged) | IMPLEMENTED | Medium (governance) | `database.py:64-120`, `duplicates.py:182`, `admin_users.py:1641` | Decision D2: log super-admin reads of other orgs' contacts | — | S |
| **L1** | CSV/VCF dedupe | last-7-digit match across the importer's whole scope; silent skip | PARTIAL | Low | `csv_import.py:470-497` | Use last-10 and own records only | — | XS |
| **L2** | Concurrent manual create | no server dedupe (5 parallel → 5 records) | PARTIAL (verified) | Low | `contacts.py:39-72` | Keep (app warns); optional idempotency key | — | S |
| **L3** | Chat widget owner | every widget lead goes to the first admin found | IMPLEMENTED | Low | `chat_widget.py:~391` | Route by the site's store | — | S |
| **L4** | Dead code | `routers/team.py` transfer has no auth guard (not mounted → 404) | NOT REACHABLE | Low | `team.py:302-438` | Delete the file or add guards before mounting | — | XS |
| **L5** | Send-time ownership | campaign send re-checks contact status / opt-out / consent but not that the enrollment owner still owns the contact | PARTIAL | Low (High after C1) | `scheduler.py:1183-1206` | Skip when `enrollment.user_id` is outside the contact owner's scope | — | XS |
| **L6** | Phone normalisation | 6+ implementations, last-7 vs last-10 | PARTIAL | Low | see Creation Map | Converge on `contact_match.phone_digits` when touching each path | — | S |

## Verified working (no change needed)

* No global unique phone/email index; unlimited independent records per person (VERIFIED).
* Default-deny middleware; `{user_id}` / `?user_id=` bound to caller or managed scope (VERIFIED 403).
* Core contact GET/PUT/DELETE, list, check-duplicate, search scoped by owner / manager scope (VERIFIED for GET, list, check-duplicate).
* Voice memo routes check contact ownership (VERIFIED 404 cross-owner); delete limited to recorder or manager (iteration 404).
* Jessi chat, history, name lookup, memory search, met-at: owner-scoped at query level (VERIFIED).
* Campaign enrollment refuses another user's contact (VERIFIED 404); broadcast recipients filtered by `user_id` (code).
* Inbound SMS contact match + conversation lookup scoped to the receiving rep (code; Twilio signature enforcement prevents a preview HTTP test).
* Opt-out / suppression and consent scoped per organization (platform scope for individual accounts) and checked in the send preflight; existing tests `test_launch_compliance*.py` cover it.

## Test coverage matrix

| Requirement | Coverage before this audit | Added by this audit (synthetic, preview) |
|---|---|---|
| Same phone across two users | none | VERIFIED (test 01) |
| Same phone across two orgs | none | VERIFIED (test 01) |
| Same email across contacts | partial (`test_contact_find_or_create.py`, one user) | VERIFIED (test 12) |
| Duplicates within one account | `test_contact_find_or_create.py`, `test_contact_merge.py` | — |
| Org-owned / personal ownership | `test_contact_ownership_visibility.py`, `test_data_isolation_fixes.py` | — |
| Notes / voice-note isolation | partial (`test_transcript_retry_memos_met_at.py`, reassignment) | VERIFIED core routes (test 03) · DEFECT sub-routes (tests 04, 14) |
| Jessi search isolation | none | VERIFIED (05, 06) · DEFECT focus (07) |
| Campaign recipient isolation | none | VERIFIED (08) |
| Incoming SMS routing with shared phone | none (`test_webhook_contact_match.py` single rep) | UNKNOWN at runtime (signature-enforced; code reviewed) |
| Contact reassignment | `test_transcript_retry_memos_met_at.py` | DEFECT cross-org bulk transfer (09) |
| Contact deletion | `test_contacts_delete.py` | PARTIAL orphans (13) |
| Concurrent creation | none | PARTIAL (11) |
| Startup consolidation | none | DEFECT (10, read-only replay) |
| IDOR on contact ids | `test_security_hotfix3_authz.py`, `test_contact_owner_validation.py` (path user ids) | DEFECT on contact-id sub-routes (04, 14) |
| Opt-out scope | `test_launch_compliance.py`, `test_launch_compliance_stop.py` | — |
