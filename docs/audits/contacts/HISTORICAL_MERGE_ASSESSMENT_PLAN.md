# Historical Cross-Organization Merge Assessment: Scan Scope & Safeguards

Status: **PREPARED, NOT RUN IN PRODUCTION.** It has been run on preview only, and only with your OK.
Code: `backend/services/merge_assessment.py`. Endpoint: `GET /api/admin/contact-merge-assessment?confirm=COUNTS_ONLY` (super admin only).
Tests: `backend/tests/test_merge_assessment.py` (4/4).

## Question it answers
Did a contact merge ever fold one tenant's contact into another tenant's contact? If so, how many of the first tenant's records now
point at the second tenant's contact?

A merge here means the retired startup phone consolidation, or a manual or Jessi merge. A tenant is the owner's organization. For an
account without an organization, the tenant is the user.

## Exactly what is read (fields in brackets; nothing else is projected)
| # | Collection | Filter | Fields read | Why |
|---|---|---|---|---|
| 1 | `users` | all | `_id`, `organization_id` | owner → tenant map |
| 2 | `stores` | all | `_id`, `organization_id` | store-owned leads → tenant |
| 3 | `contacts` | `merged_into` present | `_id`, `user_id`, `merged_into`, `merged_at`, `updated_at`, `status` | every merged ("loser") record |
| 4 | `contacts` | `_id` in the merge targets from #3 | `_id`, `user_id` | owner of each merge target |
| 5 | 15 child collections* | `contact_id` in cross-tenant targets AND `user_id` in the losers' owners | grouped counts only (`$match` + `$group`) | records the loser's owner wrote that now hang off the other tenant's contact |
| 6 | `conversations` (those of #5) → `messages` | `conversation_id` in that set | count only | message volume behind those threads |
| 7 | `conversations` | `contact_id` present | `user_id`, `contact_id` | today's state: thread owner's tenant vs. contact owner's tenant |
| 8 | `contacts` | `_id` in #7 contact ids | `_id`, `user_id` | contact owner for #7 |
| 9 | `job_leases` | `_id = startup:consolidate_phone_contacts` | `runs`, `claimed_at` | how many times the old consolidation ran, and the month of its last run |

*Child collections: conversations, messages, contact_events, campaign_enrollments, campaign_pending_sends, tasks, notes, call_logs,
voice_notes, contact_files, contact_facts, ai_reply_queue, inbound_leads, congrats_cards, broadcast_messages.

**Never read:** names, phone numbers, emails, notes, personal details, message bodies, transcripts, files and photos.

## What comes back (integers and month keys only)
- `merged_contacts_scanned`, `merges_by_kind` (startup_consolidation / manual_or_jessi_merge), `merges_by_owner_relation`
  (same_owner / same_tenant_other_owner / cross_organization / cross_tenant_individual_account / owner_unknown)
- `cross_tenant_merges`, `cross_tenant_merges_by_kind`, `cross_tenant_merges_by_month` (YYYY-MM → count)
- `tenants_involved_in_cross_merges`, `contacts_receiving_cross_merges`
- `rows_from_loser_owner_on_other_tenant_contact` {collection → count}, `messages_in_those_conversations`
- `conversations_owner_tenant_differs_from_contact_tenant`, `tenants_involved_in_cross_conversations`
- `startup_consolidation_runs_recorded`, `startup_consolidation_last_run_month`, `caps_hit`, `seconds`

No ids, names or tenant labels are returned. Nothing is stored: no database row, no file and no cache. One log line records who
started the scan and how long it took.

## Safeguards (enforced in code and tested)
1. **Read-only wrapper.** Every query goes through `ReadOnlyDB`. It exposes only `find` (projection required), `count_documents` and
   `aggregate`. Calling any write method raises an error, and so does any `$out` / `$merge` pipeline stage. Tested by
   `test_read_only_wrapper_refuses_writes`.
2. **Static check.** An AST scan confirms the module never calls insert / update / replace / delete / bulk_write / drop / index /
   find_one_and_* (`test_module_never_calls_a_write_method`).
3. **Live spy.** On a real run, the only collection methods touched are `find`, `count_documents` and `aggregate`
   (`test_finds_the_cross_org_merge_counts_only_and_writes_nothing`).
4. **No PII in the output.** The test fails if the result contains a 24-character id, an `@`, `+1`, a contact name or message text.
5. **Bounded.** Every query has `max_time_ms` = 20 s. Merged records and conversations are capped at 50,000 each, and `caps_hit` says
   when a cap was reached.
6. **Access.** Super admin only (403 for managers, 401 anonymous), and the scan only runs with an explicit `?confirm=COUNTS_ONLY`
   (400 without it).
7. **No side effects.** No un-merge, no reassignment and no notification. Fixing anything found needs a separate, approved plan.

## Preview result (Oct 16 2026, preview DB only)
44 merged records: 43 same-owner manual or Jessi merges, and 1 **cross-organization** startup consolidation (2026-10). That
cross-org merge moved 1 conversation, 1 contact event and 1 campaign enrollment of the first tenant onto the other tenant's contact,
along with 1 message in that thread. Today 32 of 160 preview conversations belong to a different tenant than their contact (mostly QA
data; this is a signal to review, not proof of a merge). The old consolidation had run 87 times in preview.

## How the production run would happen (only after your explicit OK)
1. Deploy (the endpoint ships inert with the hotfix build `2026-10-16.contact-ownership`).
2. You run one command on your Mac. It signs in as you (forest@imonsocial.com, super admin) and calls the scan. I never see your
   password. Send me the JSON it prints:
   ```
   curl -s -X POST https://app.imonsocial.com/api/auth/login -H 'Content-Type: application/json' -d '{"email":"forest@imonsocial.com","password":"YOUR_PASSWORD"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['token'])" | xargs -I{} curl -s -H "Authorization: Bearer {}" "https://app.imonsocial.com/api/admin/contact-merge-assessment?confirm=COUNTS_ONLY"
   ```
3. I turn the counts into a short report. Any un-merge or cleanup is a separate plan for your approval.
