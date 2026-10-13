# Production Secret-Leak Audit — imos-deploy-prep

**Deployment:** imos-deploy-prep (b1e5ea0d-f3c8-4de2-973f-0e6261218b25)
**Active/live run audited:** ac6fbafc-e64f-4ba3-b61f-43cf6ba997f2 (redeploy, 2026-10-13, build voice-pilot) — this is the run currently serving traffic.
**Mode:** read-only. No secrets printed; value questions answered only as present/absent + match-or-not.
**Tool:** `list_secrets` (metadata_available=true, so is_empty / matches_expected are reliable).

## Result table

| Variable | Expected | Production state | Value answer |
|---|---|---|---|
| BILLING_ALLOW_TEST_MODE | ABSENT | **PRESENT** (non-empty) | equals "1" ✅ (matches "1"); not tested against "true" |
| TWILIO_MOCK_MODE | ABSENT | **PRESENT** (non-empty) | does NOT equal "true" and does NOT equal "1" — holds some other value |
| SMS_SEND_ONLY_TO | ABSENT | **PRESENT** (non-empty) | — |
| WIDGET_RING_DRY_RUN | ABSENT | **PRESENT** (non-empty) | equals "true" ✅ |
| APPRAISAL_ALLOW_DEV_MARKET | ABSENT | **PRESENT** (non-empty) | — |
| INTEL_FACTS_INGEST | ABSENT | **PRESENT** (non-empty) | equals "true" ✅ |
| INTEL_BACKFILL_EXECUTE | ABSENT | **PRESENT** (non-empty) | equals "true" ✅ |
| INTEL_LEGACY_PROJECTION | ABSENT | **PRESENT** (non-empty) | equals "true" ✅ |
| INTEL_NUDGES | ABSENT | **PRESENT** (non-empty) | equals "true" ✅ |
| LEAD_SHOP_BUY_NUMBERS | ABSENT | **PRESENT** (non-empty) | equals "false" ✅ |
| MARKET_DATA_PROVIDER | ABSENT | **ABSENT** ✅ | — (note: MARKET_DEALER_TYPE exists but is empty; a different key) |
| STRIPE_MODE | report only | **PRESENT** (non-empty) | — |

**Summary:** 10 of the 11 preview-only switches you listed leaked into production. Only MARKET_DATA_PROVIDER is clean (truly absent). This confirms VOICE_FAKE_PROVIDER_ALLOWED was not an isolated incident — the whole family of preview/dev/mock toggles from backend/.env is present in the live run's environment. Where a value was testable, every INTEL_* and WIDGET_RING_DRY_RUN = "true", BILLING_ALLOW_TEST_MODE = "1", LEAD_SHOP_BUY_NUMBERS = "false" — i.e. the dev-mode-enabling values. TWILIO_MOCK_MODE is present but holds a value other than "true"/"1".

## How they leaked (mechanism)
Per the platform Secrets model, custom (user-owned) keys are seeded into production from the **preview pod's backend/.env on the first deploy**, and on **every subsequent deploy the preview .env is additive** — any key present in backend/.env that is not already a customized prod secret gets ADDED to production. It never overwrites a key the user explicitly set in the Deployment Panel, but it does import brand-new keys automatically. So any preview-only toggle left in backend/.env is auto-propagated to prod on the next deploy. That is the vector here.

## Provenance of VOICE_FAKE_PROVIDER_ALLOWED — what I could and could NOT verify
- **Present on active run ac6fbafc:** confirmed (non-empty).
- **Creation timestamp / "created by sync vs. manual panel entry":** NOT AVAILABLE. `list_secrets` returns only name + is_empty + matches_expected. The platform exposes no per-secret creation time or origin/author metadata through any tool I have. I therefore cannot state a date or definitively distinguish "synced from backend/.env" vs "added by hand in the panel" for this key. Based on the Secrets model the most likely mechanism is the additive backend/.env import described above, but this is INFERRED, not recorded.
- **Does the Deployment Panel auto-import backend/.env on each deploy?** Yes — additively. First deploy seeds all custom keys from preview .env; later deploys add any new backend/.env keys while preserving panel-customized values. This is the documented behavior.
- **Was VOICE_FAKE_PROVIDER_ALLOWED already on the previous prod run a2c37ab1 (2026-10-11), or did it first appear with ac6fbafc?** CANNOT VERIFY. `list_secrets` reads the ACTIVE run only; a2c37ab1 is a superseded (non-active) run, so its secret set is not readable with available tooling. Whether the key existed on a2c37ab1 or first appeared in ac6fbafc is UNVERIFIED.

## Fix
This is user-owned config, not a platform/code defect in the pipeline. Remediation:
1. Remove the preview-only toggles from the workspace backend/.env (and anywhere they are injected into preview), so they stop being re-imported on the next deploy.
2. Delete the already-leaked keys from Deployment Panel → Secrets (the 10 present ones above). Because the panel import is additive and won't overwrite, deleting in the panel + removing from .env is required so they don't get re-added.
3. Redeploy to compose a clean production environment.
