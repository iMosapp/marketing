# Production Secrets Verification — imos-deploy-prep

## Scope
Read-only verification. No changes made. FastAPI backend, expected build tag `2026-10-13.voice-pilot`.

## 1. Active run identity
- Active run id: `ac6fbafc-e64f-4ba3-b61f-43cf6ba997f2`
- Promotion timestamp: 2026-10-13T05:41:09Z
- Comparison vs referenced run `ac6fbafc-e64f-4ba3-b61f-43cf6ba997f2` (2026-10-13T05:41:09Z): **IDENTICAL — same run, not a new one.**
- Conclusion: **The owner has NOT redeployed.** Any Secrets-tab edits are NOT yet reflected in the live/active run. `list_secrets` reads only the active run, which here is the pre-edit run.

## 2. Secret safety (values never printed; `matches_expected` from list_secrets)
All seven are PRESENT (is_empty=false) and NONE matches its SAFE value (matches_expected=false → UNSAFE).

| Variable | Present | Matches SAFE | Verdict |
|---|---|---|---|
| VOICE_FAKE_PROVIDER_ALLOWED | yes | no (safe=absent/"0") | UNSAFE |
| BILLING_ALLOW_TEST_MODE | yes | no (safe=absent/"0") | UNSAFE |
| INTEL_FACTS_INGEST | yes | no (safe=absent/"false") | UNSAFE |
| INTEL_LEGACY_PROJECTION | yes | no (safe=absent/"false") | UNSAFE |
| INTEL_BACKFILL_EXECUTE | yes | no (safe=absent/"false") | UNSAFE |
| INTEL_NUDGES | yes | no (safe=absent/"false") | UNSAFE |
| APPRAISAL_ALLOW_DEV_MARKET | yes | no (safe=absent/"0") | UNSAFE |

Note: tool confirms only "not equal to SAFE"; literal values are never returned. Consistent with still holding the unsafe preview value ("1"/"true") since this is the unchanged pre-edit run, but the exact literal cannot be byte-confirmed.

## 3. Build / pipeline logs (active run)
- build_state: SUCCESS. No errors. Final steps docker-push-latest → PUSH → DONE; image digest pushed (sha256:8cf02942...).

## Overall
- Owner has not yet redeployed; the live run still carries all 7 flags in their UNSAFE state.
- Fix is the user's: edit the 7 Secrets to their safe values in Deployment Panel → Secrets and redeploy, then re-verify against the NEW active run id.
