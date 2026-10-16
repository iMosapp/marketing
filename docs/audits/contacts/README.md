# Contact Ownership, Isolation & Deduplication Audit (Oct 16 2026)

Read-only audit. No app code, indexes, permissions, Twilio settings or records were changed. Production data was not inspected.

| Document | What it covers |
|---|---|
| `CONTACT_OWNERSHIP_CURRENT_STATE_AUDIT.md` | How ownership, visibility and the contact lifecycle work today |
| `CONTACT_CREATION_AND_DEDUPLICATION_MAP.md` | Every creation path, match rule and merge / re-point function |
| `JESSI_RELATIONSHIP_ISOLATION_AUDIT.md` | Jessi search, memory, memos, focus contact, and the Jeep-event scenario |
| `CONTACT_SECURITY_FINDINGS.md` | Prioritised findings with evidence + test coverage matrix |
| `CONTACT_ARCHITECTURE_GAP_PLAN.md` | Smallest safe fixes, in order, awaiting approval |
| `isolation_tests/test_contact_isolation.py` | Synthetic probes (two throwaway orgs, self-cleaning). `results.json` = last run |

Re-run (preview only):
```
cd /app/backend && set -a && . ./.env && . ../frontend/.env && set +a && \
python -m pytest /app/docs/audits/contacts/isolation_tests/test_contact_isolation.py -q -p no:cacheprovider --rootdir=/app/docs/audits/contacts/isolation_tests
```
Note: tests 04, 07, 09, 10 and 14 currently record DEFECT verdicts; after the fixes their assertions should be flipped and the file moved to `backend/tests`.
