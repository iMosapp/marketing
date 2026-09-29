# RCA — Mystery Shop "Lead Shops" banner in production

## Problem statement
Production shows the red banner: "Email receiving is not set up on the server yet (INBOUND_EMAIL_DOMAIN)... Lead shops are off until it is." The banner is driven by `backend/services/lead_shops.py` → `inbound_domain()` returning `os.environ.get("INBOUND_EMAIL_DOMAIN")`; `configured()` returns the error string when it is empty. Confirmed working in preview (set to `imosapp.com`). Request: verify production secrets (read-only).

## Investigation (read-only)
- `describe_deployment_state`: active_run_id = `03e3e5da-d4f2-49be-b1bc-ca730203a9f1`, run_status = **success**, completed 2026-09-29T22:59:27Z (the most recent run). The active/serving run IS the latest build — pod is on the latest image. No stale deploy.
- `list_secrets` (active run, metadata_available=true, so is_empty is reliable):

### Answers to the three questions
1. **INBOUND_EMAIL_DOMAIN** — key EXISTS but is **EMPTY** (`is_empty: true`, `matches_expected: false` vs `imosapp.com`). This is the direct cause of the banner. The variable was set in the preview `.env` but is a user/custom secret that is blank in production; it never got carried into the prod Secrets.
2. Requested keys (names only):
   - RESEND_API_KEY — **present, non-empty** ✓
   - RESEND_WEBHOOK_SECRET — **present but EMPTY** (`is_empty: true`)
   - LEAD_SENDER_DOMAIN — **NOT DEFINED at all** (absent from the run's secret set)
   - APP_URL — **present, non-empty** ✓
   - PUBLIC_FACING_URL — **present, non-empty** ✓
   - TWILIO_ACCOUNT_SID — **present, non-empty** ✓
   - TWILIO_AUTH_TOKEN — **present, non-empty** ✓
3. The most recent deployment (run 03e3e5da) **finished successfully** and is the active run; the running pod is on the latest build. The problem is not a failed/stale deploy — it is missing/empty production environment values.

## Root cause
Production is missing the lead-email environment configuration. `INBOUND_EMAIL_DOMAIN` is defined but empty, which is exactly what makes `configured()` emit the banner and disable Lead Shops. Additionally `RESEND_WEBHOOK_SECRET` is empty and `LEAD_SENDER_DOMAIN` is not defined — these will be needed for inbound email receiving / webhook verification / outbound sender to function once lead shops are re-enabled.

## Fix (user action — Deployment Panel → Secrets, then redeploy)
- Set **INBOUND_EMAIL_DOMAIN** = `imosapp.com` (matches preview) — clears the banner.
- Set **RESEND_WEBHOOK_SECRET** (currently empty) — required to verify inbound Resend webhooks.
- Add **LEAD_SENDER_DOMAIN** (currently absent).
- These are user-owned custom secrets; the deployer cannot set values. After saving, redeploy so the new env is written into the pod.
