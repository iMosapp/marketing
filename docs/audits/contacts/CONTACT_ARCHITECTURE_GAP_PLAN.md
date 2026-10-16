# Contact Architecture — Minimal Gap Plan (awaiting approval)

The contact model itself is sound: one record per rep per person, owner = `contacts.user_id`, no global unique keys, owner-scoped
search and Jessi memory. **No new collections, ids or architecture are needed.** The gaps are a startup job and a set of handlers that
skip the ownership checks the rest of the app already uses. Every step below reuses existing helpers
(`owned_contact`, `get_data_filter`, `assert_self_or_scoped_manager`) and is independently shippable and testable.

Nothing here has been implemented. Each step needs your go-ahead.

## Step 0 — Containment (Critical, XS) — recommended first
* Stop scheduling `_consolidate_phone_contacts` at startup (`server.py:1889`), e.g. gate it behind `PHONE_CONSOLIDATION=on` (unset = off). Leave the function in place for now.
* Why first: it re-runs on every deploy and restart, so each deploy can add new cross-company merges.
* Test: restart preview → the job's lease counter (`job_leases._id = startup:consolidate_phone_contacts`) stops increasing; the read-only replay (`isolation_tests` test 10) still reports what it *would* do.
* Behaviour preserved: per-owner duplicate cleanup (Duplicates screen, Jessi "merge them", admin normalize-phones).

## Step 1 — Read-only production impact scan (needs your approval to run against production)
A script that only reads and prints counts (no ids, names or phones in the output):
1. contacts with `merged_into` whose winner has a different `user_id` (cross-owner merges), and whether the two owners are in different orgs;
2. for each such pair, how many `conversations / messages / contact_events / campaign_enrollments / tasks / notes / call_logs` now sit on the winner but still carry the loser owner's `user_id`;
3. live `campaign_enrollments` / `campaign_pending_sends` affected (could send from one company's campaign to a record owned by another);
4. contacts with no `user_id`, and conversations whose `user_id` is outside the contact owner's scope.

## Step 2 — Un-merge plan (only if step 1 finds cross-owner merges; separate approval)
Reversible because moved rows kept their own `user_id`: for each cross-owner pair, set `contact_id` back to the loser **only on rows whose
`user_id` equals the loser's owner**, clear the loser's `merged_into`, write an audit row per pair. Dry-run first with counts, then run per org.

## Step 3 — Close the contact-id sub-routes (H1, S–M)
Add `await owned_contact(db, user_id, contact_id)` (404 when out of scope) at the top of:
* `routers/contacts.py`: `photos` DELETE (1052), `toggle-automation` (1170), `personal-details` GET/PATCH (1197/1216), `photo/full` (1580), `photos/all` (1674), `campaign-journey` (1907); review `campaign-journey/mark-sent` (2134), `/remove` (2221) and `log-event-photo` (2500) while there
* `routers/contact_events.py:255` events, `:864` reply-photo
* `routers/contact_share.py:398/418/426` share link / text / vCard
* `routers/ai_outreach.py:79/116` generate / relationship-brief
* `routers/crm_push.py:114/215`, `routers/crm_timeline.py:48`, `routers/home_intelligence.py:823`, `routers/relationship_health.py:250`, `routers/calls.py:254`, `routers/contact_intel.py:243/383/459`, `routers/congrats_cards.py:1665`, `routers/ai_campaigns.py:459`
* routes without `{user_id}` (`ai_reply.py:1633`, `consent.py:79-135`, `sold_workflow.py:645/685`, `campaign_lifecycle.py:430`, `contact_ask.py:159/171`): check against the caller (`request.state.caller_id`).
Each line was flagged by a static scan; confirm per handler (some may already check through a helper) while adding the guard.
Test: promote `isolation_tests/test_contact_isolation.py` tests 04 and 14 into `backend/tests` with the assertions flipped (expect 404, no write).

## Step 4 — Jessi focus scope (H2, XS)
`live_voice.focus_contact`: allow the owner; otherwise require the contact's `user_id` to be inside `get_data_filter(caller)`; keep the shared-conversation rule. Test: test 07 flipped (manager of another org → no contact, no B detail in the reply); same-org manager still works.

## Step 5 — Bulk transfer scope (H3, XS)
`shared_inboxes.initiate_bulk_transfer`: `assert_self_or_scoped_manager(caller, from_user_id)` and `(caller, to_user_id)`. Test: test 09 flipped (403), in-scope transfer still 200.

## Step 6 — Lead intake never moves a personal relationship (H4, S)
In `lead_intake.py:569-595`: when the matched contact is `ownership_type == "personal"`, or the match was by name only, do not reassign it; route the lead as a new store record (flag it as a possible duplicate). Test: synthetic store, rep with a personal contact quiet 31 days, inbound lead with that phone → contact owner unchanged.

## Step 7 — Small one-liners (M1–M5, L1, L5)
M1 scope inbound-SMS name enrichment to the receiving org · M2 `$and` fix in partners · M3 scope the two inbox fallbacks (or retire the legacy webhook) · M4 managers-only + scope on `/webhooks/reassign-contacts` · M5 public API skips personal records · L1 CSV/VCF dedupe on last 10 digits, own records · L5 send-time owner check. One regression test each.

## Decisions for you (no code until decided)
* **D1 Ownership default.** Today everything created in the app (voice, photo, card, manual) is `org` (dealership-owned); only phone/CSV/VCF imports are `personal`. Keep, or make rep-created contacts personal (or let the org choose)?
* **D2 Super-admin access.** Keep unrestricted, or log every super-admin read of another org's contact / memos?
* **D3 Delete semantics.** Keep hard delete (orphans memos/audio), switch to soft delete, or cascade?
* **D4 Store lead pool in Jessi memory.** Keep including the store's unassigned internet leads in every rep's search (current), or own records only?

## Suggested order and verification
0 → 1 → (2 if needed) → 3 → 4 → 5 → 6 → 7. After each step: run `isolation_tests` (synthetic, self-cleaning) plus the existing
authz suites (`test_security_hotfix3_authz.py`, `test_contact_owner_validation.py`, `test_contact_ownership_visibility.py`,
`test_transcript_retry_memos_met_at.py`, `test_launch_compliance*.py`).
