# Stripe billing audit: production is in TEST mode (Oct 12 2026)

Read-only audit; no secret values appear in this document (prefix classes and lengths only). Sources: deployer production-secrets
comparison (value-safe `matches_expected` against the preview `.env`), Stripe sandbox object listing with the preview key, code review.

## 1. Findings
| Item | Production | Verdict |
|---|---|---|
| `STRIPE_BILLING_SECRET_KEY` (Phase 1 customer billing) | present, **`rk_test_`**, len 107, byte-identical to the preview sandbox key | **TEST key in production** |
| `STRIPE_BILLING_WEBHOOK_SECRET` | present, `whsec_`, len 38, identical to preview | **TEST-mode secret**, and it belongs to the sandbox endpoint registered for the PREVIEW URL, so production receives no Stripe events at all today (anything it did receive would fail signature or be a sandbox event) |
| `STRIPE_MODE` | `test` (informational; the code never reads it) | consistent with the above |
| Legacy `STRIPE_API_KEY` (quotes / emergentintegrations), `STRIPE_SECRET_KEY` (Mystery Shops invoices), `STRIPE_WEBHOOK_SECRET` | present, `sk_test_` / `sk_test_` / differs from preview | untouched by this work, out of scope as requested |
| Live key anywhere | none (`rk_live_` / `sk_live_` absent) | live billing NOT configured |
| Backend health | 2 pods Ready, 0 restarts, no stripe/billing errors in 24 h | fine |

Could a production customer reach a test-mode Checkout today? **In principle yes, in practice no one has.**
- Reachable paths with the current build (`2026-10-11.phase1-pilot`): a pilot owner's "Continue after the pilot" button (shown because a key is configured), the founder's "Send continue link" / "Send payment link", and the owner Billing portal button. Each would create a Stripe **sandbox** Checkout. A real card entered there is refused by Stripe ("request was in test mode, but used a non test card"); only Stripe test cards work, so no money can move, but the record could be marked converted/paid by a test card, which would be wrong.
- Evidence nothing happened: every one of the 55 Checkout sessions in the sandbox returns to the preview host (`user-routing-issue.preview...`), none to `app.imonsocial.com`; the 5 sandbox customers and all subscriptions are the QA ones; production has no pilot/paying customer yet (the founder-controlled production pilot account from the release checklist has not been created as far as this environment can tell).

## 2. Safety gate built (preview, tested, NOT deployed yet)
`services/billing.py`: `key_mode()` (prefix only), `conversion_enabled()` = live key, or test key **only when `BILLING_ALLOW_TEST_MODE=1`** (preview/QA flag; production does not have it and must not get it), `require_conversion()` used by `create_checkout` and `portal_url` (503 "Billing is in Stripe TEST mode on this server; paid conversion is paused until live billing is configured. Complimentary pilots are not affected."), `handle_event` acknowledges and ignores `livemode:false` events when conversion is disabled (`ignored_test_event`), `owner_summary` exposes `billing_mode` + `conversion_enabled` and hides Continue / portal / checkout links, founder rows carry `billing_config`.
Frontend: `BillingModeNotice` (orange, `billing-mode-notice`) inside the Founding Partner Pilot panel and the Stripe Billing panel; Send/Copy link buttons disappear while conversion is paused; Extend / End / Resume / Check Stripe stay.
Also fixed on the way: `pilot_program.mark_converted` now claims the state atomically, so two concurrent webhook deliveries (two pods, or `checkout.session.completed` + `customer.subscription.created` together) record `pilot_converted` and notify the founder exactly once (a double was observed once under load in preview).

Verified: production simulation in preview (test key, flag removed) `tests/testmode_gate_check.py` **13/13**: create pilot -> Activate -> Invite -> owner activation starts the clock; founder row `{configured true, mode test, conversion_enabled false}`; owner Billing renders with Continue hidden; owner Checkout 503 and founder Send link 503 with the TEST-mode message; Check Stripe still answers; nothing created in Stripe; Hub row potential MRR; Extend / End (login 403) / Resume unaffected; a correctly signed sandbox webhook event is acknowledged (200) and ignored, customer untouched. Flag restored -> preview QA behaves as before (`can_continue true`). Regression after the change: pilot 10/10 + 169 (Stage 1/2/3, P0 security, onboarding) = **179 passed**. Mystery Shops billing and the legacy `STRIPE_API_KEY` flows are not touched (different env vars, different code).

Until this build is deployed, production still has the buttons enabled with test keys. Removing the two secrets from the Secrets panel would also pause conversion, but that too only takes effect at the next deploy (pods do not hot-reload secrets), so the fastest safe path is the pending Tools-menu deploy, which carries this gate.

## 3. Live Stripe setup checklist (owner, Stripe Dashboard with the **Live mode** toggle ON; never paste live keys into preview)
1. **Restricted key**: Developers -> API keys -> **Create restricted key** -> name `imonsocial-billing-live` -> permissions exactly:
   Customers **Write**, Checkout Sessions **Write**, Subscriptions **Write**, Products **Write**, Prices **Write**, Customer portal / Billing Portal **Write** (configurations + sessions). Everything else **None** (no Charges, Invoices, PaymentIntents, Webhook Endpoints, Test Clocks). Create -> copy the `rk_live_...` once (it is shown only once).
2. **Webhook endpoint**: Developers -> Webhooks -> **Add endpoint** -> URL `https://app.imonsocial.com/api/billing/stripe/webhook` -> listen to events on your account -> select exactly: `checkout.session.completed`, `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.paid`, `invoice.payment_failed` -> Add endpoint -> **Reveal** signing secret `whsec_...` and copy it. (The sandbox endpoint pointing at the preview URL stays as is.)
3. **Products and prices**: the app creates them itself on first use by lookup key (`pilot_store_monthly` $375.00/month "i'M On Social Pilot Store", `pilot_seat_monthly` $75.00/month "i'M On Social Additional Seat", `pilot_individual_monthly` $100.00/month "i'M On Social Pilot Individual"), idempotently. To create them deliberately before the first customer, from a checkout of the repo on your Mac (not in preview): `cd backend && STRIPE_BILLING_SECRET_KEY='rk_live_...' PYTHONPATH=. python tests/ensure_billing_catalog.py --dry-run`, then the same without `--dry-run`; it prints the three live price ids and creates nothing on a second run. If you prefer the Dashboard: Product catalog -> Add product, recurring monthly USD, and set the **lookup key** on each price to exactly the keys above (the app matches on lookup key, not on names).
4. **Failed-payment policy**: Settings -> Billing -> Subscriptions and emails -> Manage failed payments: Smart Retries on, "Email customers about failed payments" on. (The app marks `past_due` with a 14-day grace, alerts you, and blocks sign-in after the grace.)
5. **Customer portal**: nothing to do; the app creates its portal configuration (invoice history, payment-method update, cancel at period end) on first use.

## 4. Production secrets to replace, and redeploy
| Secret (Deployments > Secrets) | Action |
|---|---|
| `STRIPE_BILLING_SECRET_KEY` | replace with the live `rk_live_...` from step 1 |
| `STRIPE_BILLING_WEBHOOK_SECRET` | replace with the live `whsec_...` from step 2 |
| `STRIPE_MODE` | set to `live` (informational only, keeps the panel honest) |
| `BILLING_ALLOW_TEST_MODE` | must NOT exist in production (it is a preview-only flag) |
| `STRIPE_API_KEY`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` | leave untouched (legacy quotes flow and Mystery Shops invoices) |

**Redeploy required: yes.** Secrets-panel edits only reach the pods at the next Deploy; running pods do not reload them. Order that keeps
everything safe: (a) deploy the pending build now with the test keys still in place -> the gate pauses conversion and shows the orange notice;
(b) when the live key + webhook are ready, replace the two secrets and Deploy again -> notice disappears, Continue reappears, webhook signature
check uses the live secret. After (b): `curl -s -o /dev/null -w "%{http_code}" -X POST https://app.imonsocial.com/api/billing/stripe/webhook`
-> 400 (unsigned refused), Stripe Dashboard -> the new endpoint -> "Send test webhook" -> 200 (acknowledged; test events are ignored by design
in live mode), founder customer page shows no notice, owner Billing of a pilot shows "Continue after the pilot". The first real conversion
should be one you control (a founder-owned test customer with your own card): it saves the card, charges nothing until the trial end, and
can be cancelled from the Stripe portal before the first charge.

## 5. Nothing was created, charged or switched
No subscription, charge, key or webhook was created or changed. The only live-side artefacts remain in the sandbox (QA customers).
