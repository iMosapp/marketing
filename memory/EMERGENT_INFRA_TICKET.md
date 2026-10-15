# Emergent support ticket — DRAFT (send from the account owner to support@emergent.sh)

**Subject:** Production readiness checks pass while the backend is down → repeated 502/520 on every republish (deployment `imos-deploy-prep`, app.imonsocial.com)

Hello Emergent team,

Our production app (deployment **imos-deploy-prep**, custom domain **app.imonsocial.com**, tier_1 "Launch", 2 replicas) returns intermittent Cloudflare **502/520** errors after every republish, and whenever one replica's backend restarts. We investigated read-only and need platform-side changes we cannot make ourselves.

## What we observed (all times UTC)
- **Health checks only test nginx.** The Kubernetes readiness and liveness probes call `http://POD_IP:8080/health`, which the platform-generated `nginx.conf` answers with a static `return 200 "healthy"`. The FastAPI backend on `127.0.0.1:8001` is never checked, so a pod is marked Ready and receives `/api` traffic while uvicorn is still starting or has died. nginx then logs `connect() failed (111: Connection refused) … upstream http://127.0.0.1:8001/api/...` and the client gets 502, or a Cloudflare 520.
- **Run `ccda365a-8312-48dc-8e38-a0d8523f33ef`** (a `secret_reuse` run, promoted Oct 15 01:31:54):
  - It was promoted **before any backend was ready**; the first replica (`…-75f9779f6d-m4d99`) reached "Application startup complete" at 01:32:20, so all `/api` traffic failed for about 26 s.
  - The second replica (`…-75f9779f6d-zzdlg`) hit the entrypoint's `Backend failed to start within timeout, exiting` 3 times (restart_count 3, Error / exit 1). It kept receiving traffic whenever its nginx came back up, which caused 502 bursts at 01:34–01:46 and 02:00–02:05. It recovered on its own at 02:05:13.
- **Run `740e17c7`** (promoted Oct 14 22:07:18): a 520 was reported 28 s after promotion.
- **Our app's error log has 33 reports from Oct 6–14.** All of them are 502/520/network failures, in 5–16 minute bursts. The run history before Oct 14 21:55 isn't available to us, so we can't match the older ones to deploys.
- **The entrypoint allows the backend about 60 attempts × 2 s.** A healthy cold start of our backend in production took about 61 s (most of it Python import under the 0.5 CPU limit). We have since cut our import CPU by about 57% in preview and will ship that.

## What we are asking for
1. **Backend-aware readiness.** Point the readiness probe at the backend, for example `GET /api/health` through nginx (it proxies to :8001 and returns 200 only when FastAPI answers), or make nginx's `/health` return 503 until :8001 answers. A replica whose backend is down should leave the load balancer immediately.
2. **Don't promote a run until its backends are ready.** The run `health_check` step should use the same backend-aware check, so promotion waits for at least one (ideally all) replicas to pass.
3. **A startup grace period.** Add a `startupProbe`, or raise `initialDelaySeconds` / `failureThreshold`, and the entrypoint's `MAX_ATTEMPTS` to match, so a slow but healthy cold start (60–120 s under CPU contention) isn't killed and restarted in a loop.
4. **Rolling safety.** Keep the previous run's pods serving until the new run's backends pass the backend-aware check (`maxUnavailable=0` with readiness that reflects the backend).
5. **Single-instance recovery.** When one replica is stuck restarting, can support delete or replace that one pod on request, without rebuilding and without restarting the healthy replica? If so, what's the fastest way to request it?
6. **Documentation questions.**
   - Does **Rollback** restore the old run's secret snapshot, or keep the current secrets? We have live Stripe secrets that must not be lost.
   - Does a Secrets-tab save (a `secret_reuse` rollout) keep the old run serving until the new pods pass health checks?

## What we are doing on our side
- **Faster startup:** the LLM SDK and other heavy libraries now load on first use, and routes are registered once instead of being rebuilt twice. In preview, import CPU went from 4.9 s to 2.1 s and boot-to-healthy from 7.4 s to 3.4 s.
- **Shorter blocking startup:** index builds, one-off migrations and the object-storage init now run in the background.
- **Cross-replica coordination:** scheduled jobs and boot clean-ups now run once per tick across replicas, using Mongo leases.

None of this fixes the probe design itself. Any slow start, or a backend crash on one replica, still sends live traffic to a dead backend until items 1–3 are addressed.

Thank you. We're happy to share pod events and nginx logs (with timestamps) for the run IDs above.

— Forest Ward, I'M ON SOCIAL (app.imonsocial.com)
