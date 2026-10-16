# Contact Ownership Hotfix: pre-deploy regression report (Oct 16 2026, preview only)

Build: `2026-10-16.contact-ownership`. **NOT DEPLOYED.** Production deployment waits for the owner's explicit approval.

## 1. Results
| Suite | Result |
|---|---|
| Same-org rep isolation (`test_same_org_rep_isolation.py`) | 31/31 |
| Ownership hotfix (`test_contact_ownership_hotfix.py`) | 25/25 |
| Thread-claim hijack / cross-org reassign / foreign task (`test_t1_claim_hijack_406.py`) | 6/6 |
| Everyday workflows: contacts, chunked voice note, scan, texting, campaigns, lead intake, Jessi, manager (`test_t1_everyday_regression_406.py`) | 12/12 |
| AI reply drafts keep the owner's private data away from teammates (`test_ai_reply_private_context.py`, new) | 4/4 |
| Merge assessment is read-only (`test_merge_assessment.py`) | 4/4 |
| Security suites: hotfix3 authz 19, 4 12, 4b 15, 4b-adversarial 9, 4c-adversarial 15, BOLA middleware, sender policy 27, send paths 2, team view 7 | all pass (4c: 2 stale fails, identical before the hotfix) |
| Jessi contact creation 17/17, Jessi Campaign Builder + voice limits 17/17, contact owner validation 25/25, campaign reliability 31 + 31 | pass |
| **A/B against the pre-hotfix code** (31 older modules, same DB snapshot, scheduler off) | **No new failures.** Each remaining failure also fails on the pre-hotfix code: stale tests (bare X-User-ID, older voice rules) or preview fixtures that are gone |
| UI smoke (testing agent, iteration_406): owner, teammate on a shared thread, teammate asks Jessi, manager, everyday rep and manager | 6/6, no leak |

A/B logs: `isolation_tests/regression_ab_hotfix.log` vs `isolation_tests/regression_ab_prehotfix.log`.

## 2. Fixed in this pass
- `POST /api/tasks/{user_id}` refuses a `contact_id` outside the user's scope (404). Before, any rep could attach a task to any contact.
- `POST /api/engagement/reassign-lead`: the contact must be in the manager's data scope, and the new owner must be someone they manage.
  Before, a manager in another org could take the lead.
- Inbox ownership actions (claim, assign, release, move, collaborators, graduate) only work on threads the caller runs, and only hand
  threads to people on the caller's team. Claiming applies only to shared-inbox threads.
- **Automatic AI reply drafts** (`ai_reply.queue_ai_reply`) were missed in the first pass. When the thread is assigned to a teammate or is
  sitting unclaimed in a shared inbox, the draft and its "why this reply" are no longer built from the owner's notes, memos or intelligence.
  The owner and the owner's managers still get them.
- Contact page: a contact the caller can't open now shows "This contact isn't available" instead of an empty editable "New Contact" form.

Tests changed to match real preview conditions; no security assertion was loosened. All changes are in `test_t1_everyday_regression_406.py`:
- The text test accepts the sender-policy refusal for an account without an organization.
- The campaign test turns on `managers_can_edit` for the run, then restores it.
- The demo contact is looked up from the database instead of a stale `/tmp` file.

## 3. Preview data incident (preview only, production untouched)
An earlier cleanup in `test_same_org_rep_isolation.py` ran `delete_many({"user_id": {"$in": [..., None]}})` across every collection.
In MongoDB, `None` in `$in` also matches documents that have no `user_id` field, so most preview users, stores, organizations and
settings were deleted. The tests only ever use the preview database (`MONGO_URL=localhost`); production has its own database.
- Fixed: every wipe now drops empty or invalid ids before `$in` (`test_same_org_rep_isolation.py`, `test_contact_ownership_hotfix.py`).
- Restored with their original ids where the tests pin them (`tests/t1_restore_core_accounts.py`, idempotent): forest, qa-manager,
  activation-tester, mjeast, qa-orgadmin, TEST_Store_Org + store, the QA store, and the documented Scan rollout. Also re-seeded:
  qa-consent-rep, qa-voice-ui, the same-org demo.
- Not restorable (no backup): other preview demo orgs and accounts (QA Accept, QA FP Demo, hotfix victims, ...) and other preview settings.
  Re-run their seed scripts when they're needed.

## 4. Historical cross-organization merge assessment (read-only, counts only)
Preview (run before the incident): 44 merged records. 43 are same-owner manual or Jessi merges, and **1 is a cross-organization startup
consolidation** (2026-10). That merge moved 1 conversation, 1 event, 1 campaign enrollment and 1 message onto the other company's contact.
The old consolidation had run 87 times in preview. Production has **not** been scanned; the steps are in `HISTORICAL_MERGE_ASSESSMENT_PLAN.md`.

## 5. Deploy steps (only after approval)
1. Save to GitHub -> Deploy. This also ships every earlier "NOT DEPLOYED" preview feature (see PRD).
2. `python tests/prod_smoke_contact_ownership.py https://app.imonsocial.com 2026-10-16.contact-ownership`, then `prod_smoke_hotfix3.py`.
3. Owner runs the merge-assessment command (plan §"How the production run would happen") and sends back the JSON.
4. `eas update` for native apps (contact "not available" screen; web ships with Deploy).
