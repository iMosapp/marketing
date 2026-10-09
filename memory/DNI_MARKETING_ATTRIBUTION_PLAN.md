# I'm On Social: Dynamic Number Insertion & Marketing Attribution Platform
## Technical Discovery, Architecture Audit and Project Scope

Date: October 9, 2026 · Status: PLANNING ONLY, nothing built · Author: E1 (platform agent)

Legend used throughout:
- **VERIFIED** = read in the codebase at the cited path:line, or confirmed against the preview database.
- **ASSUMPTION** = a planning estimate; the inputs are stated so you can change them.
- **UNKNOWN** = could not be confirmed from the code; treated as missing until proven otherwise.
- Classification of existing pieces: **Reuse as-is / Extend / New / Refactor**.

---

## 1. Executive summary

**How much do we already have?** About 45 to 55 percent of the plumbing a DNI platform needs is already in production and reusable:
Twilio subaccount-per-organization tenancy, a phone-number registry with purchase and per-number webhook configuration, a shared inbound voice webhook that forwards to a cell, dual-channel recording, Whisper transcription, AI call summaries, outcome classification, appointment extraction, missed-call follow-up, contact merge, a per-store website widget served as one-line JavaScript with a visitor id and public rate-limited endpoints, an internet-lead pipeline with a (Meta-only) attribution dict and source analytics, a white-label partner model, a monthly partner invoicing job, an APScheduler job runner, a webhook outbox, and a Google OAuth pattern (Calendar).

**What is genuinely missing?** There is no dynamic number insertion of any kind (zero hits for DNI / tracking number / call tracking in the codebase), no visitor-session or UTM / click-id capture (the widget records only page, title and a visitor id), no GA4, Search Console, Google Ads, Meta or TikTok API integration (Google Calendar is the only Google OAuth), no unified call record (calls are split across `call_logs`, conversation messages and `roleplay_sessions`), no CallSid idempotency on voice webhooks, no "agency user who sees several dealerships" role (only super_admin manages partners), and no charting library in the app.

**Two production findings that matter before DNI goes live:**
1. The inbound voice handler resolves the called number through `users.twilio_number`, and when nothing matches it rings **any super_admin / org_admin** (`routers/twilio_webhooks.py:2272-2280`). An unrecognised tracking number would ring an admin's cell. DNI numbers must be resolved first, the way lead-shop numbers already are (`:2241-2249`).
2. Voice webhooks have no CallSid dedup (SMS does, `:172-186`), and Twilio signature validation defaults to log-only (`services/twilio_signature.py`). Both must be tightened for a product whose data is billed and reported on.

**Recommendation (details in §19):** Build on Twilio with our own attribution layer (build-vs-buy option B), delivered as **Option B "Commercial Partner Release"** but staged so that **Option A "Lean MVP" is milestone 1** and goes live for one TracTru dealership in week 8-9. Ad-platform APIs (Meta, Google Ads, TikTok) are deferred to Option C because their approvals take 2-8 weeks each and carry permanent maintenance cost; UTM and click-id attribution (which does not need those APIs) is included from day one.

Headline numbers (ASSUMPTIONS in §16): one-time engineering ≈ 400-450 h for A, ≈ 1,050-1,150 h for B, ≈ 1,700-1,900 h for C. Variable operating cost ≈ **$35-45 per dealership per month** at 150 tracked calls and 13 numbers, before fixed infrastructure ($150-1,000/month by scale) and support headcount. A $149-249 per dealership list price yields 70-85 percent gross margin.

---

## 2. Existing architecture audit (verified against the codebase)

### 2.1 Twilio account model, numbers, provisioning
| Finding | Evidence | Status |
|---|---|---|
| One parent Twilio account plus **one subaccount per organization**; credentials resolved by `creds_for_org()`; subaccount auth token Fernet-encrypted on the `organizations` doc | `services/twilio_tenant.py:38,54-62,76-98,230` | VERIFIED |
| Canonical number registry collection `phone_numbers` with `organization_id, location_id, assigned_user_id, twilio_phone_number_sid, twilio_account_sid, number_type (USER/STORE/SHARED/CAMPAIGN/VA), status (AVAILABLE/ASSIGNED/SUSPENDED/RELEASED), monthly_cost_usd, messaging_service_sid, incoming_sms_webhook, incoming_voice_webhook, history[]` | `services/phone_numbers.py:19,271-326` | VERIFIED (13 docs in preview) |
| Legacy mirror `phone_number_pool` (used by mystery shops / lead shops with `purpose`, `cooldown_until`, `lead_shop_id`, `POOL_CAP=10`) | `services/phone_numbers.py:226-230`, `services/lead_shops.py:22-130` | VERIFIED |
| Numbers bought with `incoming_phone_numbers.create`, voice_url / sms_url set **per number** at purchase; always the single shared voice webhook `/api/webhooks/twilio/voice`; no TwiML App | `services/phone_numbers.py:298-301` | VERIFIED |
| Env flags (names only): `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WEBHOOK_VALIDATION`, `TWILIO_MESSAGING_SERVICE_SID`, `LEAD_SHOP_BUY_NUMBERS`, `PUBLIC_FACING_URL` | various | VERIFIED |
| Usage metering is SMS-centric (`usage_daily`, `numbers_monthly_cost_usd`); **no voice-minute cost tracking** | `services/phone_numbers.py:589-624` | VERIFIED gap |
| Anything named DNI / tracking number / call tracking | repo-wide grep | VERIFIED: none |

### 2.2 Inbound call routing, recording, transcription
| Finding | Evidence | Status |
|---|---|---|
| `POST /api/webhooks/twilio/voice` → lead-shop AI numbers first, then mystery-shop numbers (neutral voicemail), then **rep lookup by `users.twilio_number`**, fallback to any super_admin/org_admin, then `<Dial record="record-from-answer-dual" recordingStatusCallback=/recording-complete timeout=REP_RING_S>` to the rep's cell, voicemail `<Record transcribe>` on no answer | `routers/twilio_webhooks.py:2222-2370` | VERIFIED; fallback is a risk for DNI |
| `/recording-complete` downloads the recording, transcribes with **OpenAI Whisper** (`stt.transcribe`), optional voice-id channel split, writes `call_logs` {call_sid, direction, duration_s, outcome, recording_sid, recording_url, transcript, transcript_segments, ai_summary, voice_id, timestamp} and a `type: call_recorded` message in the thread, then scorecard grading | `routers/twilio_webhooks.py:1513-1891` | VERIFIED |
| Click-to-call bridge with human-pickup whisper gate | `routers/twilio_webhooks.py:1287-1470, 1919-2155` | VERIFIED |
| Media Streams websocket (GPT-Live rep briefing) and ConversationRelay-style AI voice for shops | `routers/twilio_webhooks.py:2025`, `services/lead_shops.py:306-347` | VERIFIED |
| CallSid idempotency on voice webhooks | none found (SMS dedup exists at `:172-186`) | UNKNOWN / likely absent |
| Signature validation | `services/twilio_signature.py` modes off/log/enforce, default log | VERIFIED (not enforcing) |
| `call_logs` holds only 4 documents in preview; call data is fragmented across `call_logs`, thread messages (`call_log`, `call_recorded`) and `roleplay_sessions` | DB sample + `routers/calls.py` | VERIFIED |

### 2.3 AI call intelligence
| Capability | Evidence | Status / Reuse |
|---|---|---|
| Post-call summary (gpt-5.2) | `services/call_summary.py:1-60` | VERIFIED · Reuse as-is |
| Outcome classification (regex + LLM) and missed-call retry cadence | `services/call_followup.py:49-93, 221-369` | VERIFIED · Reuse as-is |
| Appointment extraction from call transcript → `tasks` (type appointment, source call_extraction) | `routers/tasks.py:821-920`, called from `twilio_webhooks.py:1786` | VERIFIED · Reuse as-is |
| Buying-intent scoring (0-10, categories incl. trade_in) | `services/intent_detection.py` | VERIFIED, texts only · Extend to calls |
| Scorecard grading of calls | `services/scorecards.py:653` → `call_logs.score_pct` | VERIFIED · Reuse |
| Sales-vs-service classification of a call | not found | UNKNOWN / New |
| "Qualified call" definition | not found as such (intent score exists for texts) | New (prompt + rule) |
| Contact auto-create from unknown caller | `routers/twilio_webhooks.py:384-402` (SMS path); voice path creates/looks up contact at `:2292-2320` | VERIFIED partial · Extend |

### 2.4 Contacts, leads, opportunities, sales
| Finding | Evidence | Status |
|---|---|---|
| `contacts`: phone, email, user_id, tags, vehicle, date_sold, purchase_history, call_retry, possible_duplicate_of, referred_by; **no attribution / lead_source field**; store resolved through `users.store_id` | `routers/contacts.py:66-75,143-220,732-804`, `services/duplicates.py:13-27` | VERIFIED |
| Merge migrates 13 linked collections (`messages, contact_events, conversations, tasks, campaign_enrollments, ..., inbound_leads, voice_notes, ai_reply_queue, inventory_interest`) | `services/duplicates.py:15-16,176-209` | VERIFIED; DNI collections must be added to this list |
| `inbound_leads`: normalized fields + `source_name` + `attribution` dict, populated **only for Meta lead ads** (`kind: ad, source: meta_lead_ad, campaign, adset, ad, form`); `utm_source` is merely an alias of `source_name`; no utm_medium/campaign, gclid, fbclid, referrer, landing page | `routers/lead_intake.py:41-159, 687-794, 1327-1334` | VERIFIED gap |
| `lead_sources` (448 docs): name, store_id, routing (team/user inbox), `inquiry_context`, `va_prompt_override`, stats endpoint | `routers/lead_sources.py:215-527`, `services/lead_context.py` | VERIFIED |
| Sales recorded via `services/sales.record_sale` → `purchase_history` / `date_sold`; sold workflow router exists; `appointments` collection (28 docs) with no shown / no-show status found; no `opportunities`, `deals`, `sales` collections | `services/sales.py:126`, `routers/sold_workflow.py`, DB sample | VERIFIED; "verified sale" concept = `date_sold` set by a human or the sold workflow |
| Lead analytics: sources, response times, proof cards (sold rate by source/campaign/ad) | `routers/lead_intake.py:1477-2101` | VERIFIED · Extend (best existing reporting surface for attribution) |

### 2.5 Website widget and public surfaces
| Finding | Evidence | Status |
|---|---|---|
| One-line script per store: `GET /api/w/{key}.js` renders a 50 KB IIFE (`services/widget_js.py`, 433 lines) with `Cache-Control: public, max-age=120` | `routers/website_widget.py:478-489` | VERIFIED · Extend (DNI can ship inside it or as a sibling script) |
| Visitor id in `localStorage['imos_vid']`; `track()` posts `{kind, page, title, visitor}` to `/api/w/{key}/event`; **no referrer, no UTM, no click ids, no GA client id** | `services/widget_js.py:66,72` | VERIFIED gap |
| Public endpoints under `/api/w/{key}/…` (config, event, text, call, chat, ring) with `W.allow(ip, bucket, limit)` rate limits; fully open CORS only for `PUBLIC_CORS_PREFIXES` (`/api/w/` included) | `routers/website_widget.py:507-662`, `services/widgets.py:340`, `server.py:321-364` | VERIFIED · Reuse |
| Domain allow-list per widget key | not found | UNKNOWN / New |
| `widget_events` collection (220 docs), `widgets` (1 doc) | `services/widgets.py:15-16` | VERIFIED |
| Other public routers: public_api (X-API-Key, SHA-256 in `api_keys`), public_landing, public_trade, public_appt, public_proof, public_review, short_urls, go_links | `routers/*` | VERIFIED |

### 2.6 Google and advertising integrations
| Finding | Evidence | Status |
|---|---|---|
| Google Calendar OAuth (`GOOGLE_CLIENT_ID/SECRET`, google-auth, googleapiclient) | `routers/calendar.py:15-70,156` | VERIFIED · Reuse the pattern and libraries |
| `google-api-python-client`, `google-auth-oauthlib`, `oauthlib` already installed | `requirements.txt:40-44,85` | VERIFIED |
| GA4, Search Console, Google Ads, Meta Graph/Marketing API, TikTok, LinkedIn APIs, Looker | repo-wide grep | VERIFIED: none |
| Meta lead-ad attribution exists only as webhook payload fields (no API call) | `routers/lead_intake.py:1327-1334` | VERIFIED |

### 2.7 Multi-tenancy, partners, white-label, billing
| Finding | Evidence | Status |
|---|---|---|
| Roles: `super_admin(4) > org_admin(3) > store_manager(2) > user(1)`; JWT or `impersonate_*` session; `require_role()` | `routers/rbac.py:21-100` | VERIFIED |
| A second cookie-based `get_current_user` in `routers/auth.py:653-663`; partner billing / invoices / account-health send-report still accept `X-User-ID` header alone | `routers/partner_billing.py:19`, `routers/partner_invoices.py:25` | VERIFIED · Refactor before agency exposure |
| `white_label_partners` (4 docs): logo, colors, slug, `assign-org/{org_id}` (a partner owns several orgs), public `/by-slug` | `routers/white_label.py:114-149` | VERIFIED · Extend (this is the TracTru object) |
| Partner agreements, e-sign, W9, Stripe checkout; monthly partner invoices job with per-store rates and waivers | `routers/partners.py`, `routers/partner_invoices.py:153,646`, `scheduler.py:1658` | VERIFIED · Reuse |
| Permission matrix is role-tiered, not plan-tiered; no `entitlements` / `modules` | `permissions.py` | VERIFIED · Extend (module flag "dni") |
| No `dealer_groups` collection; `organizations` (35) and `stores` (30) exist | DB sample | VERIFIED |
| Frontend admin scaffolding for organizations, stores, partner orgs, partner billing, white-label | `frontend/app/admin/*` | VERIFIED · Extend |
| Charting library | `package.json` | VERIFIED: none (only react-native-svg) · New dependency |

### 2.8 Background processing, observability
| Finding | Evidence | Status |
|---|---|---|
| APScheduler `AsyncIOScheduler` in-process, ~45 jobs wrapped in `safe_job()`; 60-s webhook outbox; preview/prod gate | `scheduler.py:220-2430`, `services/webhook_outbox.py`, `services/runtime_env.py` | VERIFIED; single-process (no Celery/RQ) |
| `/api/health`, `/api/health/deep`; `system_logs`, `audit_logs`, `permission_audit_log` collections exist | `server.py:377,563`, DB sample | VERIFIED |
| Sentry / external APM | not found | UNKNOWN |
| Fernet secret encryption helper | `services/twilio_tenant.py:54-62` | VERIFIED · Reuse for Google/Meta tokens |

### 2.9 Customer journey / mystery shopping
Lead Shops + the new Journey Campaigns (`services/lead_shops.py`, `services/journey/*`) already model "a tracked phone number owned by a persona, every inbound call/text/email timed and graded". The number-pool lifecycle (acquire, cooldown, release) and the events timeline are directly relevant patterns; DNI should **not** reuse those collections (they are test instruments, not production customer data) but should copy the allocator design. VERIFIED.

---

## 3. Reusable component inventory (with code references)

| # | Component | Where | Classification | Required modification for DNI |
|---|---|---|---|---|
| 1 | Twilio subaccount per org, encrypted creds | `services/twilio_tenant.py` | Reuse as-is | none; DNI numbers live in the dealer org's subaccount |
| 2 | Number registry + purchase + per-number webhook | `services/phone_numbers.py:271-340` | Extend | add `number_type: TRACKING`, `pool_id`, `dni` fields; search by area code for local presence |
| 3 | Inbound voice webhook | `routers/twilio_webhooks.py:2222-2370` | Extend | resolve tracking numbers **before** rep lookup; forward to destination; remove admin fallback for unknown numbers (play message instead) |
| 4 | Recording → Whisper → `call_logs` → summary → scorecard | `routers/twilio_webhooks.py:1513-1891` | Reuse as-is | add `dni_call_id` + attribution snapshot to `call_logs`; add CallSid dedup |
| 5 | Call summary, outcome, appointment extraction, missed-call retry | `services/call_summary.py`, `services/call_followup.py`, `routers/tasks.py:821` | Reuse as-is | hook them on tracked calls |
| 6 | Intent scoring | `services/intent_detection.py` | Extend | run on call transcripts; add sales/service + "qualified" labels |
| 7 | Contact merge | `services/duplicates.py:15-16,176` | Extend | add `dni_calls`, `dni_sessions` to migrated collections |
| 8 | Internet lead pipeline + `attribution` dict + source analytics | `routers/lead_intake.py` | Extend | generalise attribution (utm/click ids/referrer/landing) for every lead door, not only Meta lead ads |
| 9 | Widget JS delivery, visitor id, event endpoint, rate limiter | `routers/website_widget.py`, `services/widget_js.py`, `services/widgets.py:340` | Extend | DNI module inside the same script or sibling `/api/w/{key}/dni.js`; add referrer/UTM/click-id/GA cookie capture; domain allow-list |
| 10 | White-label partners + assign-org | `routers/white_label.py` | Extend | agency role + membership; branding on reports |
| 11 | Partner invoices job | `routers/partner_invoices.py`, `scheduler.py:1658` | Reuse / Extend | add DNI usage lines (numbers, minutes) |
| 12 | APScheduler + safe_job | `scheduler.py` | Reuse | add pool-recycling sweep, GA4 pulls, cost rollups |
| 13 | Google OAuth pattern + libraries | `routers/calendar.py`, requirements | Extend | generic `google_connections` with multiple scopes and Fernet-encrypted refresh tokens |
| 14 | Fernet encryption | `services/twilio_tenant.py:54-62` | Reuse as-is | tokens for Google / Meta / TikTok |
| 15 | Lead analytics endpoints and proof cards | `routers/lead_intake.py:1477-2101` | Extend | attribution dashboards reuse the aggregation style |
| 16 | Public API keys | `routers/public_api.py:80-110` | Reuse | expose DNI data to TracTru's own tools later |
| 17 | RBAC | `routers/rbac.py` | Extend | `agency_admin` / `agency_analyst` roles |
| 18 | Legacy header-auth partner routers | `routers/partner_billing.py`, `partner_invoices.py` | Refactor | move to `require_role` before agency users exist |
| 19 | Charts | none | New | add a chart library (web-first) |
| 20 | Unified call record | fragmented | Refactor (light) | `dni_calls` as the DNI-side record pointing at `call_logs`; do not rewrite existing call storage |

---

## 4. Proposed architecture

```
Dealer website (any platform / GTM)                              Ad platforms            Google
┌──────────────────────────────────┐                             (Meta, Google Ads,      (GA4, GSC)
│ <script src=…/api/w/{key}/dni.js>│  utm, gclid/fbclid/ttclid,   TikTok)  spend/ads  ▲      ▲ OAuth
│  • find phone numbers in DOM     │  referrer, landing page,         ▲ (Phase 4)     │      │ Data API / GSC API
│  • swap → tracking number        │  _ga/_ga_* cookies (consent)     │               │      │
│  • rewrite tel: links            │                                  │               │      ▼ MP events
│  • MutationObserver for SPA      │                                  │               │
│  • fail-safe: original number    │                                  │               │
└───────────────┬──────────────────┘                                  │               │
                │ POST /api/dni/{key}/session  (allocate number, 2 s budget, else fail-safe)
                ▼
┌─────────────────────────────── FastAPI (existing app) ───────────────────────────────────────────┐
│  routers/dni_public.py   (session/number allocation, heartbeat, consent)     ← rate limited W.allow │
│  services/dni/pools.py   (dni_pools, dni_numbers: atomic claim, TTL lock, LRU recycle, cooldown)    │
│  services/dni/sessions.py(dni_sessions: first/last touch, TTL index, visitor id, ga ids)            │
│  routers/twilio_webhooks.py /voice  → services/dni/routing.py (resolve To → pool/number → destination,│
│        whisper, <Dial record dual> callerId passthrough, status callback, CallSid dedup)             │
│  /recording-complete (existing) → call_logs + Whisper + summary + outcome + appointment (REUSE)      │
│  services/dni/match.py   (call ↔ session matching + confidence A/B/C/U → dni_calls.attribution)      │
│  services/dni/outcomes.py(contact link, lead, appointment, sale → journey; GA4 MP, Ads offline conv) │
│  services/google/{oauth,ga4,gsc}.py   services/ads/{meta,gads,tiktok}.py (Phase 4, optional)        │
│  routers/dni_admin.py    (pools, numbers, install verify, attribution reports, exports)              │
│  scheduler jobs: recycle sweep (60 s), cost rollup (hourly), GA4/GSC pulls (daily), reports (monthly) │
└──────────────────────────────────────────────────────────────────────────────────────────────────────┘
                │ Mongo (existing): dni_pools, dni_numbers, dni_sessions, dni_calls, dni_daily, google_connections,
                │ ad_connections, ad_spend_daily  +  existing phone_numbers, call_logs, contacts, conversations, inbound_leads
                ▼
Dashboards (Expo web admin): dealer view · agency (TracTru) view · super-admin ops view · exports · monthly email
```

**Event-driven vs integrated vs dedicated service.** Recommendation: **integrated into the existing FastAPI app and scheduler for Phases 1-3**, with two deliberate seams so it can be split later: (a) the public allocation endpoint (`/api/dni/*`) and snippet are stateless beyond Mongo and can move to a small edge service if latency or load demands it; (b) attribution outcomes are emitted as `contact_events` (which the existing webhook outbox already streams), so GA4 / Ads conversion feedback is driven by events, not by direct calls inside the voice webhook. A dedicated service now would duplicate tenancy, auth, Twilio credentials and deployment for no measurable gain at 1-100 dealerships. Trade-off: the app is single-process APScheduler; a stuck job can delay sweeps, so the recycle sweep must also run opportunistically inside the allocation path (claim = sweep the pool first).

---

## 5. DNI technical design

### 5.1 Snippet (`/api/w/{key}/dni.js`, ~6-8 KB gzipped target)
- **Delivery**: served by the same router as the widget (`routers/website_widget.py`), versioned path (`/dni.v1.js`) with `Cache-Control: public, max-age=300, stale-while-revalidate=3600`; config inlined (pools, replacement rules, session TTL, consent mode). Install routes: GTM Custom HTML tag (recommended), direct `<script async>` in `<head>`, and platform-specific notes (Dealer.com / DealerOn / Dealer Inspire allow "third-party scripts" via their tag managers; UNKNOWN per vendor until tested; see risks).
- **Detection**: rules per pool: exact numbers to replace (E.164 + display variants), optional CSS selectors / `data-imos-dni="sales"` attributes, department mapping (sales / service / parts), and a "replace all occurrences of this number" default. Numbers found in text nodes, `href="tel:"`, `aria-label`, `title`, and common dealer templates (header, sticky mobile bar, footer, VDP contact cards).
- **Swap**: one allocation request per visitor-session, then a synchronous DOM pass; a `MutationObserver` re-applies on injected content (SPAs, lazy sections, chat bubbles). Formatting is preserved (match the original's punctuation pattern). `tel:` links get the tracking number in E.164.
- **Performance**: `async`, no dependencies, runs after `DOMContentLoaded`, batches DOM writes in `requestAnimationFrame`; allocation request has a **2-second budget**; on timeout, error, pool exhaustion or 4xx the page keeps the dealership's real number (fail-safe is the default state because we only ever *replace*, never *insert*).
- **Attribution across navigation**: session id and assigned number cached in `sessionStorage` (tab) and the visitor id in `localStorage` (`imos_vid`, already exists). Each page view sends a heartbeat that extends the number lock up to the configured session TTL (default 30 minutes of inactivity, max 24 h). Returning visitors inside the attribution window keep their visitor id; a new session re-captures last-touch.
- **Captured per session (first and last touch)**: `document.referrer`, landing page, `utm_source/medium/campaign/content/term`, `gclid`, `gbraid`, `wbraid`, `fbclid`, `ttclid`, `li_fat_id`, `msclkid`, GA4 `_ga` client id and `_ga_<MEASUREMENT>` session id (read from cookies, **only with consent**), device class, page path.
- **Consent**: three modes per dealer: (1) `always` (functional swap, full capture), (2) `respect` (default): capture identifiers only when `window.imosConsent === true`, OneTrust/Cookiebot categories grant analytics, or GTM Consent Mode `analytics_storage` is granted; swap still happens (it is not tracking of the person, it is routing) but the session is "anonymous" and never stores GA ids or visitor id; (3) `off`.
- **Coexistence**: detect CallRail / CTM swap classes (`calltrk_*`, `ctm-*`) and bail out with a console warning so two DNI vendors never double-swap.
- **Verification**: `?imos_dni=debug` overlays what was found and swapped; the admin "Verify install" button loads the dealer page server-side (Playwright already available) and confirms the swap.

### 5.2 Replacement rule model
`dni_pools.rules[] = { match: ["(801) 555-0100", "+18015550100"], department: "sales", destination: "+18015550100", whisper: "Website call, sales", record: true, business_hours?: {...}, overflow_destination? }`. Multiple departments = multiple pools on one site. A **static source number** (Google Business Profile, paid-social direct call, print) is a pool of size 1 with `mode: static` and fixed `source` metadata.

---

## 6. Twilio number pool and routing design

### 6.1 Collections (new)
- `dni_pools` {organization_id, store_id, widget_key, name, mode: dynamic|static, department, destination, size_target, session_ttl_min (30), cooldown_min (≥ 2 × ttl, default 120), area_code_pref, rules[], whisper_text, record (bool), status}
- `dni_numbers` {pool_id, phone_number, registry_id → `phone_numbers._id`, twilio_sid, twilio_account_sid, state: free|locked|cooldown|static|suspended, locked_until, session_id, last_released_at, assignments_count, calls_count}
- `dni_sessions` {_id (session id), pool_id, store_id, visitor_id?, number, started_at, last_seen_at, expires_at (TTL index), consent: full|anonymous, first_touch{...}, last_touch{...}, ga{client_id, session_id}?, pages[] (≤ 20), device}
- `dni_calls` {call_sid (unique), pool_id, number, from_phone (hashed + E.164), to_destination, started_at, answered, duration_s, status, session_id?, visitor_id?, match: {level: A|B|C|U, reason, candidates[]}, attribution{source, medium, campaign, content, term, landing_page, referrer, click_ids{}, first_touch{}, last_touch{}}, call_log_id → `call_logs`, contact_id?, conversation_id?, outcomes{qualified?, sales_or_service?, appointment_task_id?, sold_at?}}
- `dni_daily` {store_id, pool_id, date, source, medium, campaign: counts (sessions, swaps, calls, answered, missed, unique_callers, qualified, appointments, sales), minutes, cost_usd}

### 6.2 Allocation and recycling
- **Claim**: `find_one_and_update({pool_id, state: "free"}, {$set: {state: "locked", locked_until, session_id}}, sort=[("last_released_at", 1)])` is atomic in Mongo; LRU order maximises the gap between a number's previous visitor and its next one. No two sessions can hold one number.
- **Extend**: heartbeat pushes `locked_until = now + ttl` (capped).
- **Release**: when `locked_until` passes, the number enters `cooldown` for `cooldown_min` (default 120 min, configurable per pool; attribution safety, see 6.4), then `free`. The sweep runs every 60 s in the scheduler **and** inline before each claim, so a stalled scheduler never starves a pool.
- **Exhaustion**: claim fails → snippet keeps the real number (no swap) → `dni_events: pool_exhausted` → alert at > 2 percent of sessions in a day with a sizing recommendation.
- **Sizing (ASSUMPTION)**: numbers ≈ peak-hour sessions × (ttl + cooldown) / 60, rounded up, min 5. A dealer site with 5,000 sessions/month (~170/day, peak hour ~10 percent = 17) at 30 + 120 minutes needs ≈ 43 if every session is held for the full lock, but real sessions average under 5 minutes, so the effective need is 8-12. Default pool: **10 numbers**, utilisation dashboard recommends resizing.
- **Collision prevention**: a number is never swapped onto a page while in `cooldown`; `dni_numbers.phone_number` unique index; registry `phone_numbers` remains the owner of Twilio SIDs (no second source of truth).
- **Local presence**: search by the dealership's area code first (`available_phone_numbers(...).local.list(area_code=…)`, already used), fall back to the state.

### 6.3 Routing (modify `handle_inbound_voice`)
1. Resolve `To` in `dni_numbers` **before** the rep lookup (same position as the lead-shop check at `twilio_webhooks.py:2241`).
2. Load the pool: destination number (department line or a rep's cell), whisper text, recording flag, business-hours overflow.
3. TwiML: `<Dial record="record-from-answer-dual" recordingStatusCallback=/recording-complete action=/dni/dial-result timeout=25><Number url=/dni/whisper?pool=…>destination</Number></Dial>`. **Caller ID pass-through** by omitting `callerId` (Twilio then presents the original caller's number to the dealership, which keeps the store's own caller-ID experience and CRM screen-pops intact). Optional recorded consent line ("this call may be recorded") per dealer for two-party-consent states.
4. `/dni/dial-result` and the status callback write `dni_calls` (idempotent on CallSid), then the existing `/recording-complete` pipeline produces transcript, summary, outcome, appointment, scorecard; `dni_calls.call_log_id` is set when `call_logs` is written (add the DNI fields to that insert).
5. Unknown numbers (not DNI, not rep, not shop): play "this number is no longer in service" and hang up instead of ringing an admin (behaviour change; needs your approval).
6. Signature validation `enforce` for `/voice`, `/dni/*`, `/recording-complete`.

### 6.4 Calls after a number was recycled (attribution uncertainty)
A visitor may save or write down a tracking number and call days later, after the number moved to another visitor. Safeguards:
- Cooldown ≥ 2 × TTL (default 2 h) absorbs most "called a few minutes later" cases.
- Matching uses the number **and** time: if the call arrives while the number is locked to a session → **A (exact)**; if it arrives during cooldown with exactly one recent session → **B (probable)**; during cooldown with several candidate sessions, or after the number was re-assigned → **C (inferred: website, session unknown)** with candidates stored, no campaign claimed; if the same caller called before and was matched A/B → inherit that attribution as **B (repeat caller)**.
- Reports always separate *verified* (A) from *estimated* (B, C). Campaign-level counts only use A and B; C counts toward "website calls" only.
- Static numbers always attribute at the source level the number was bought for (campaign/ad/GBP) with level **S (static source)**; they never claim a website session.

### 6.5 Can the existing Twilio architecture carry this without disrupting current customers?
Yes. VERIFIED: numbers already carry their own `voice_url`, subaccounts isolate billing per organization, and the shared voice webhook already branches on the called number for lead-shop and mystery-shop numbers. Required changes are additive (new branch first, remove the admin fallback). Two prerequisites: CallSid idempotency and signature enforcement.

---

## 7. Attribution data model, rules and confidence

### 7.1 What is captured (first-party)
Per session: visitor id, session id, referrer, landing page, source/medium (derived: referrer host → organic/referral/direct classification table; UTMs override), utm_*, `gclid/gbraid/wbraid`, `fbclid`, `ttclid`, `li_fat_id`, `msclkid`, GA4 client id + session id (consent), tracking number assigned, device class, pages. Per call: time, duration, caller (E.164 + salted hash), answered/missed, voicemail, recording, transcript, summary, outcomes.

### 7.2 Scenario rules
| Visitor arrives via | What we can establish | Confidence of a call during the session |
|---|---|---|
| Google organic | referrer google.com without gclid → source google / medium organic; **keyword never known** (Google withholds it; GSC gives page-level queries only) | A |
| Google paid click | `gclid` (or gbraid/wbraid on iOS) + utm if auto-tagging is complemented with manual tags → source google / medium cpc; campaign name only if UTMs present or Google Ads API connected (Phase 4) | A |
| Facebook / Instagram ad | `fbclid` + UTMs (Meta does not expose campaign in the URL unless UTMs are set) → paid-social; campaign only from UTMs or Meta API | A |
| TikTok ad | `ttclid` + UTMs | A |
| Direct | no referrer, no params → direct / none | A |
| Returns through another channel | new session; first-touch kept on the visitor record, last-touch = new channel; both reported | A for the new session |
| Calls days later from a saved number | §6.4: B if unambiguous, C otherwise | B/C |
| Calls from a different device | no session on that device; only caller-id continuity (repeat caller) or later lead-form phone match links identities | B at best, usually U |
| Blocks cookies / declines consent | swap still works; session is anonymous (no visitor id, no GA ids); attribution limited to that session's referrer/UTMs in memory; first-touch impossible | A for the live session, no history |

### 7.3 Confidence levels
- **A exact**: call during an active session lock; session carries source data.
- **B probable**: cooldown single candidate, or repeat caller with a prior A match within the attribution window (default 30 days).
- **C inferred**: website (pool) call with several or no candidate sessions; reported as "website: source unknown".
- **S static**: static source number; attribution = the number's configured source.
- **U unknown**: direct dial of the dealership's real line (not tracked), or data missing.
The UI shows the badge; exports include the level; aggregate KPIs show "verified" and "estimated" columns. We never label a call with a campaign at level C or U.

### 7.4 Identity continuity (merges, repeat calls, transfers, multiple sales)
- `dni_calls.contact_id` is set when the caller phone matches a contact (existing lookup) or when the existing voice path creates a contact; `services/duplicates.py` migration list gets `dni_calls` and `dni_sessions` so merges carry attribution.
- Journey = ordered `contact_events` for the contact (existing collection) plus `dni_calls`; first-touch is the earliest attributed event, last-touch the latest before the outcome.
- Transfers inside the dealership happen after our `<Dial>` connects and are invisible to us (UNKNOWN unless the dealer uses our click-to-call); we attribute the call, not the department it ended in.
- A sale (`contacts.date_sold` via `record_sale`) is attributed to the touches inside the lookback window (default 90 days) and reported as **verified only when a human or the sold workflow set it**; "AI thinks they bought" is never a verified sale.

---

## 8. Google Analytics 4 and Search Console design

### 8.1 OAuth connection (dealer or agency admin)
- Reuse the Calendar pattern and libraries (VERIFIED). New generic `google_connections` {organization_id, store_id, connected_by, scopes[], refresh_token_enc (Fernet), email, ga4_property_id, ga4_measurement_id, gsc_site_url, status, last_pull_at}.
- Scopes: `analytics.readonly`, `webmasters.readonly` (both **sensitive** → Google OAuth app verification needed; ASSUMPTION 2-6 weeks; the consent screen is branded "I'm On Social" unless we run a second OAuth client per white-label brand, which multiplies verification work).
- Property picker via Admin API `accountSummaries.list`.

### 8.2 Read from GA4 (Data API `runReport`)
Users, sessions, traffic acquisition (sessionSource/Medium/Campaign), landing pages, engagement (engagementRate, averageSessionDuration), key events. Daily pull per connected property into `ga_daily` (cache), on-demand refresh capped per hour. Quota: 200,000 tokens/day per standard property (VERIFIED from Google docs, Oct 2026); a daily pull of 5-6 reports uses a few hundred tokens, so quota is not a constraint below hundreds of properties.

### 8.3 Send to GA4 (Measurement Protocol)
- Events: `phone_call` (every tracked call, A/B/S levels), `qualified_phone_call` (AI qualified), `appointment_set`, `appointment_shown` (only when a human marks it), `sale_completed` (only verified). Params: `call_duration`, `call_department`, `attribution_level`, `tracking_number_pool`; never names, phone numbers, transcripts (Google PII rule).
- Requires the browser `client_id` (`_ga` cookie) and, for session-stitched reporting and Realtime, `session_id` + `engagement_time_msec` (VERIFIED). Calls hours or days later still attach to the user via client_id but **not** to the original session's acquisition (state this in the dealer UI). Without consent there is no client id and nothing is sent.
- Recommend marking `qualified_phone_call`, `appointment_set`, `sale_completed` as GA4 key events (dealer does this in GA4 Admin; we provide a one-click checklist, not an API, since key-event creation via Admin API is possible but not required for MVP).
- Validate with `/debug/mp/collect` in staging; the production endpoint returns 2xx regardless.

### 8.4 Search Console
Search Analytics API (`searchanalytics.query`): clicks, impressions, CTR, position by query, page and date; daily pull into `gsc_daily`. Quota is generous (VERIFIED order of magnitude). **Limitation to state plainly**: GSC data is aggregated and delayed ~2 days; it cannot name the query behind a specific caller. We can correlate landing-page call rates with the queries that bring traffic to that page, nothing more.

### 8.5 Reporting architecture recommendation
Support **both directions**: our dashboard is the primary surface (it is the only place that has calls + AI outcomes + sales), and we push conversion events into GA4 so dealers and TracTru can see them next to their existing GA4 reports and Google Ads imports. Looker Studio: optional later via a community connector or a BigQuery export of `dni_daily`; not in Options A/B.

---

## 9. Social and paid advertising design

### 9.1 Website-driven social (no API needed)
Covered by the snippet: `fbclid`, `ttclid`, `li_fat_id` plus UTMs. Campaign / ad names come from UTMs the agency sets (TracTru controls the ads, so this is realistic). Report at source / medium / campaign / content / term.

### 9.2 Direct-call advertising (static numbers)
Dedicated numbers per campaign (recommended), per ad group (when budgets justify $1.15/number/month and reporting granularity matters), per creative (rarely worth it). Shared numbers only across placements of one campaign. Inventory: n static numbers per dealer, bought in the dealer's subaccount, routed with the same TwiML, attribution level S. Limitation: a static number proves the ad drove the call, never which visitor.

### 9.3 Platform APIs (Phase 4 / Option C)
| Platform | What it adds | Access reality (VERIFIED from docs, Oct 2026) | Effort / maintenance |
|---|---|---|---|
| Google Ads API | campaign names for gclids, spend, clicks, offline conversion import (`ClickConversion` with gclid, qualified call → conversion) | Developer token starts with test-account access; Basic Access review ≈ 5 business days, Standard ≈ 10; RMF audit for Standard; brand verification speeds it up | 80 h build; 4-8 h/month upkeep |
| Meta Marketing API | campaign / adset / ad for fbclid via UTMs or Ads Insights, spend, Conversions API for offline call conversions | App Review for `ads_read` / `ads_management` with video + written use case; Business Verification mandatory; Marketing API access tiers depend on call volume and error rate | 80 h; 6-10 h/month (API versions deprecate quarterly) |
| TikTok Marketing API | spend, campaign metadata, Events API conversions | developer app review with business documentation; details vary | 60 h; 4-6 h/month |
Data from URL parameters (click ids, UTMs) is available on day one with no approvals; spend, impressions and conversion feedback need authenticated API access and approvals that we do not control.

---

## 10. TracTru agency / partner portal scope

- **Agency object** = existing `white_label_partners` (Extend): branding, slug, assigned organizations. New `agency_memberships` {user_id, partner_id, scope: all|org_ids[], role: agency_admin|agency_analyst}.
- **Roles**: `agency_admin` (manage assigned dealerships, numbers, connections, users of the agency), `agency_analyst` (read dashboards, exports). Both are *below* org_admin for anything outside their assignment: every DNI, call, lead and report query filters by `organization_id ∈ membership` (new dependency `require_agency_scope`). Super_admin keeps global access; dealer users see only their store.
- **Prerequisite**: migrate `partner_billing.py`, `partner_invoices.py`, `account_health.py` send-report off header-only auth (VERIFIED gap) before any agency user exists.
- **Capabilities**: dealer onboarding wizard (create org/store if new, choose area code, pool size, destination numbers, departments), install instructions (GTM tag, HTML, platform notes), **Verify install** (server-side check), number management (buy / add / suspend, utilisation, cost), connections (GA4, GSC, later ads), per-dealer dashboard, aggregate agency dashboard, monthly PDF/CSV per dealer and roll-up (reuse the partner-invoice PDF/email path), white-label logo/colors on dashboards and PDFs, usage and billing summary (numbers, minutes, calls) feeding `partner_invoices`.
- **Isolation tests**: fixture with two agencies × two dealers each; every endpoint tested for cross-agency 403.

---

## 11. Reporting and dashboard specification

### 11.1 KPIs
MVP (Options A/B): calls, unique callers, answered / missed / voicemail, average duration, first-time vs repeat callers, calls by source / medium / campaign / landing page / number / department, by hour and weekday, **qualified calls** (AI), appointments set (extracted or marked), attribution confidence split, pool utilisation and exhaustion, sessions and swaps as seen by the snippet (labelled "DNI sessions", not GA sessions). With GA4 connected (B): GA4 users, sessions, acquisition, landing pages, engagement next to our calls.
Deferred (C): ad spend, cost per call / qualified call / appointment / sale, ROAS (requires spend from APIs and verified revenue), appointments shown (needs a human workflow), multi-touch models.

### 11.2 Dimensions
dealer, dealer group (organization), agency, channel, source/medium, campaign, ad (when known), landing page, department, confidence level, date range.

### 11.3 Features
Executive summary, channel comparison, campaign table, attribution journey per contact (Facebook campaign → website visit → call → qualified → appointment → sale, each hop labelled verified / estimated), call drill-down (recording, transcript, summary, outcome, scorecard), AI conversation insights (top intents, objections), CSV export, scheduled monthly PDF (reuse `partner_invoices` PDF + scheduler + Resend). Charts: add one library (recommend `victory-native` with web support, or web-only `recharts` behind a platform check); ASSUMPTION 8 h to integrate.

---

## 12. Security and privacy requirements

- Tenant isolation on every new collection (`organization_id`, `store_id` always present; agency scope dependency; cross-tenant tests).
- Public endpoints: `W.allow` rate limits (per IP and per widget key), request size caps, widget-key domain allow-list (New), CORS stays open only for `/api/w/` and `/api/dni/` prefixes.
- Twilio: signature validation `enforce` on voice / DNI / recording routes; CallSid idempotency collection with TTL; subaccount-scoped tokens (existing).
- Secrets: Fernet-encrypted OAuth tokens; never log tokens; rotate `api_secret` for GA4 MP per property.
- Recordings: per-dealer consent announcement option; retention default 90 days for recordings and transcripts, 13 months for `dni_daily`, 90 days for `dni_sessions` (TTL indexes); deletion on request by phone number (salted hash index).
- PII to Google: none; event params whitelist enforced in code.
- Consent: §5.1 modes; anonymous sessions never persist identifiers.
- Snippet integrity: versioned URL, no third-party dependencies, CSP-friendly (no inline eval), fail-closed to the original number.
- Access logs: write admin actions on pools / numbers / connections to the existing `audit_logs`.

---

## 13. Build versus buy

| Criterion | A. Build full DNI natively (own carrier layer) | **B. Twilio + our attribution layer** | C. Integrate CallRail / CTM / WhatConverts, keep our intelligence |
|---|---|---|---|
| Initial effort | not realistic (carrier contracts, STIR/SHAKEN, number porting) | 400-450 h to MVP (we own 45-55 percent already) | 150-250 h (OAuth/API client, webhook ingest, mapping), but recordings/transcripts arrive theirs, not ours |
| Ongoing cost | highest | ≈ $35-45 variable per dealer (§16) | $50-195/dealer/month list (CallRail), + $3/number, $0.05-0.06/min; CTM $65-79 base + $2/number + $0.04/min; CallRail API above 1,500 calls/month costs $80-200/month extra (VERIFIED pricing, 2026) |
| Scalability | n/a | Twilio scales; our allocator is Mongo-atomic | vendor scales; our margin shrinks per dealer |
| Technical complexity | very high | moderate (allocator, matching, snippet across platforms) | low-moderate, but two call pipelines to reconcile |
| Vendor dependency | none | Twilio (already core) | high; vendor pricing and API changes |
| White-label flexibility | full | full | limited (their snippet, their numbers, their portal branding) |
| Ownership of attribution data | full | full | partial (export limits, API quotas) |
| Fit with existing architecture | poor | **native** (same webhook, same registry, same recording pipeline) | duplicates call records and number management |
**Recommendation: B.** Our telephony, recording and AI already run on Twilio; the missing parts are the snippet, the allocator, matching and dashboards, all of which are the parts that create product value and margin. Option C is a reasonable *interim* only if a TracTru dealer already pays for CallRail and refuses to switch; we could ingest its webhooks for that dealer as a one-off (not planned).

---

## 14. Development phases, dependencies and estimates

Hours are engineering effort for one senior full-stack engineer (ASSUMPTION), including tests; elapsed time assumes one engineer plus your review cycles; third-party delays are listed separately.

### Phase 1 — DNI Foundation (≈ 330-380 h · 7-8 weeks)
Scope: snippet (detection, swap, tel links, MutationObserver, consent, fail-safe, debug overlay), config/delivery, `/api/dni` session allocation + heartbeat, pools / numbers / sessions / calls collections, allocator with cooldown and sweep, Twilio routing branch + whisper + dial-result + CallSid dedup + signature enforce, call↔session matching with confidence, pool admin UI (buy, size, rules, utilisation), basic dashboard (calls by source/number, call list), install guide, verify-install.
Reuse: `phone_numbers`, `twilio_tenant`, `/voice`, `/recording-complete`, widget delivery, `W.allow`, scheduler. New: everything under `services/dni/*`, `routers/dni_*`, snippet, admin screens. Dependencies: a TracTru test site (or our own) on which to iterate; Twilio numbers in the dealer subaccount.
Testing: allocator concurrency (50 parallel claims, no duplicates), TTL/cooldown state machine, TwiML golden tests, Playwright against three fixture sites (static, SPA, GTM), live Twilio test calls to a tracking number, fail-safe (API down → original number).
Risks: dealer website platforms blocking scripts; number availability in the area code; the admin-fallback change.
Acceptance: a visitor from `?utm_source=facebook` sees a swapped number on all templates within 500 ms of load; a call to it reaches the dealership with the caller's ID, is recorded, transcribed, summarised, and appears in the dashboard attributed "facebook / paid-social" at level A within 2 minutes.
Production readiness: signature enforce on, dedup on, alerts for pool exhaustion and webhook errors, runbook for number purchase failures.

### Phase 2 — Call Intelligence Integration (≈ 160-190 h · 3-4 weeks)
Scope: `dni_calls ↔ call_logs` link; contact creation / lookup from tracked calls (reuse voice path); sales-vs-service and qualified-call classification (new prompt in `services/call_summary` style, model from `llm_models`); run intent scoring on transcripts; hook outcome classification, appointment extraction, missed-call retry; attribution journey view per contact; add DNI collections to merge; `contact_events` for every tracked call so the webhook outbox streams them.
Dependencies: Phase 1. Testing: fixture transcripts (sales / service / spam / wrong number), journey assembly, merge preserving attribution.
Acceptance: the journey "Facebook campaign → website visit → call → qualified → appointment → sale" renders for a seeded contact with each hop labelled verified / estimated; a wrong-number call is not "qualified".

### Phase 3 — GA4 and Search Console (≈ 200-230 h · 4-5 weeks + Google verification 2-6 weeks in parallel)
Scope: `google_connections`, OAuth flow (web), property / site pickers, Data API daily pulls and cache, MP event sender (phone_call, qualified_phone_call, appointment_set, appointment_shown, sale_completed) driven by `contact_events`, GSC pulls, dashboard panels, key-event checklist.
Dependencies: Google Cloud OAuth consent screen verification for sensitive scopes (**external delay**), a dealer GA4 property to test with.
Testing: MP debug endpoint validation, token refresh/revocation, quota back-off, PII whitelist test.
Acceptance: a tracked qualified call appears in the dealer's GA4 DebugView within 60 s with no PII; the dashboard shows GA4 sessions and GSC clicks next to calls for the same date range.

### Phase 4 — Social and Paid Advertising (≈ 300-340 h · 6-8 weeks + approvals 2-8 weeks per platform)
Scope: dedicated campaign numbers (static pools, UI), spend ingestion model, Google Ads API (OAuth, spend, campaign names for gclid, offline conversion import), Meta Marketing API (spend, insights, Conversions API), TikTok (spend, events), CPL / CPA KPIs.
Dependencies: Phases 1-3; developer tokens, App Review, Business Verification (**external**). Risks: review rejections; quarterly API deprecations; maintenance cost.
Acceptance: spend by campaign appears for a connected account; a qualified call uploads as an offline conversion with its gclid and is accepted by Google Ads.

### Phase 5 — TracTru Agency Portal (≈ 290-330 h · 6-7 weeks)
Scope: agency roles and memberships, scope dependency and tests, legacy header-auth refactor, onboarding wizard, install verification, number management, connections management, multi-dealer dashboards, monthly PDF/CSV, white-label on reports, usage lines into partner invoices.
Dependencies: Phase 1 (data), Phase 2/3 for richer dashboards.
Acceptance: an agency_admin sees exactly their assigned dealers; cross-agency access returns 403 in tests; a monthly PDF emails on the first of the month with agency branding.

### Phase 6 — Advanced Attribution (≈ 190-230 h · 4-5 weeks)
Scope: first / last / linear / position-based models, verified revenue attribution (sold workflow + DMS/CRM imports), conversion feedback completeness, anomaly alerts, pool forecasting.
Dependencies: Phases 2, 4 (spend), 5. Acceptance: ROAS shown only for dealers with verified revenue and connected spend; models reconcile to the same totals.

### 14.1 Dependency order
1 → 2 → 3 (3 can start in parallel with 2 once OAuth verification is submitted) → 5 (agency) → 4 (ads APIs) → 6. Phase 5 is placed before 4 in Option B because TracTru needs multi-dealer management earlier than it needs ad spend.

---

## 15. Engineering-hour summary

| Phase | Hours | Elapsed (1 engineer) | External delays |
|---|---|---|---|
| 1 Foundation | 330-380 | 7-8 weeks | none |
| 2 Call intelligence | 160-190 | 3-4 weeks | none |
| 3 GA4 + GSC | 200-230 | 4-5 weeks | Google OAuth verification 2-6 weeks (parallel) |
| 4 Ads APIs | 300-340 | 6-8 weeks | Google Ads Basic Access ~1-2 weeks; Meta App Review + Business Verification 2-6 weeks; TikTok 2-4 weeks |
| 5 Agency portal | 290-330 | 6-7 weeks | none |
| 6 Advanced | 190-230 | 4-5 weeks | none |
| **Total** | **1,470-1,700** | 30-37 weeks sequential | |
Add 10-15 percent for production hardening and support tooling across the program.

---

## 16. Infrastructure and operating cost estimates (ASSUMPTIONS stated)

### 16.1 Unit prices (VERIFIED Twilio US list prices, October 2026; AI prices are current list prices)
Local number $1.15/month · inbound local $0.0085/min · outbound (forward leg) $0.0140/min · recording $0.0025/min · recording storage $0.0005/min/month · Whisper transcription ≈ $0.006/min · gpt-5.2 summary + classification ≈ $0.02-0.03 per call · Google APIs $0 (quota) · Meta/TikTok APIs $0 (quota) · Twilio rounds each leg up to the minute.

### 16.2 Per-dealership assumptions
13 numbers (10 dynamic pool + 3 static sources), 150 tracked inbound calls/month, average 4 minutes, both legs billed (inbound + forward), 100 percent recorded and transcribed, recordings kept 90 days, 5,000 website sessions/month.

| Line | Monthly per dealership |
|---|---|
| Numbers 13 × $1.15 | $14.95 |
| Inbound minutes 600 × $0.0085 | $5.10 |
| Forward minutes 600 × $0.014 | $8.40 |
| Recording 600 × $0.0025 | $1.50 |
| Storage (3 months rolling, 1,800 min × $0.0005) | $0.90 |
| Whisper 600 × $0.006 | $3.60 |
| AI summary/classification 150 × $0.025 | $3.75 |
| **Variable total** | **≈ $38** (range $30-50 with ±30 percent call volume) |

### 16.3 Scenarios
| Dealerships | Variable telephony + AI | Fixed infra (API/DB/CDN/monitoring, ASSUMPTION) | Support & ops (ASSUMPTION) | Total / month |
|---|---|---|---|---|
| 1 | $38 | $150 (preview-grade; shares the current deployment) | included in current team | ≈ $190 |
| 10 | $380 | $200 | 0.1 FTE ≈ $800 | ≈ $1,400 |
| 50 | $1,900 | $350 (DB tier up, log retention) | 0.25 FTE ≈ $2,000 | ≈ $4,250 |
| 100 | $3,800 | $600 (replica set, separate DNI edge worker, CDN) | 0.5 FTE ≈ $4,000 | ≈ $8,400 |
| 250 | $9,500 | $1,200 | 1 FTE ≈ $8,000 + ads-API upkeep 15 h/month | ≈ $19,500 |
One-time development is in §15 (hours; multiply by your blended rate). Ad-API maintenance (Phase 4) adds ≈ 15-25 engineering hours per month permanently.

### 16.4 Commercial model options
- **Per dealership / month**: $149 (DNI + call intelligence, 10 numbers, 500 minutes), $249 (adds GA4/GSC, campaign attribution), $399 (adds ads APIs, agency reporting). Overage $3/number, $0.06/minute (matches market norms). Gross margin at $149 with $38 COGS ≈ 74 percent; at $249 ≈ 85 percent.
- **Per tracked number**: $5-8/number/month plus $0.06/minute; simple but penalises correct pool sizing; use only as an add-on.
- **Usage-based**: $0.50-1.00 per attributed call; attractive for low-volume stores, unpredictable for agencies.
- **Agency wholesale**: 30-40 percent off list for ≥ 10 dealers, TracTru bills its clients; minimum commitment protects number inventory.
- **White-label licence**: platform fee $1,500-3,000/month plus wholesale per dealer; covers OAuth-brand duplication and support.
Margin watch-outs: unanswered long voicemails and spam calls still bill minutes (add spam-caller screening), recording storage grows unless retention is enforced, toll-free numbers cost 2-3× (avoid unless requested).

---

## 17. Testing and production rollout plan

1. **Unit / integration (pytest, existing style)**: allocator concurrency and state machine; matching and confidence; TwiML goldens; dedup; signature enforce; consent modes; merge preserving attribution; agency scope 403 matrix; MP payload whitelist.
2. **Snippet (Playwright, already in the stack)**: fixture pages (static HTML, React SPA, GTM-injected, page with CallRail classes), timing budget, fail-safe when the API is down, debug overlay.
3. **Telephony (staging subaccount)**: real calls from two phones to a pool number: answered, missed → voicemail, during cooldown, after recycle; recording and transcript land; cost rows written.
4. **Shadow mode**: install on the pilot site with `swap: false` for 3-5 days to validate detection without changing anything the visitor sees.
5. **Pilot**: one TracTru dealership, 2-3 weeks, weekly review of attribution confidence distribution and pool utilisation; success = ≥ 90 percent of tracked calls at level A/B, zero misrouted calls, no page-speed regression > 50 ms.
6. **Rollout**: dealer by dealer through the onboarding wizard; alerts (pool exhaustion, webhook errors, OAuth token failures) to the admin bug digest that already exists; monthly cost reconciliation against Twilio usage API.

---

## 18. Risks and unknowns

| Risk / unknown | Impact | Mitigation |
|---|---|---|
| Dealer website platforms (Dealer.com, DealerOn, Dealer Inspire, Sincro) restrict third-party scripts or already run a vendor's DNI | installation friction, double-swap | GTM path, vendor-detection bail-out, per-platform install notes after testing (UNKNOWN until tried) |
| Inbound voice fallback rings an admin for unknown numbers | misrouted calls | resolve DNI first; replace fallback with a not-in-service message (needs approval) |
| No CallSid dedup on voice webhooks; signature log-only | duplicate call rows, spoofed callbacks | add dedup + enforce before go-live |
| Single-process APScheduler | delayed recycling if a job hangs | inline sweep on claim; job health alert exists (`safe_job`) |
| Two auth mechanisms; header-only auth on partner routers | cross-tenant exposure for agency users | refactor in Phase 5 prerequisites |
| Google OAuth verification timing and branding per white-label | Phase 3 slip; "I'm On Social" consent screen for TracTru's clients | submit early; decide one brand or per-brand OAuth clients |
| Ad-platform approvals and deprecations | Phase 4 slip; permanent upkeep | keep in Option C; UTM/click-id path works without them |
| Attribution after number recycling | false campaign credit | cooldown, confidence levels, verified vs estimated split |
| Keyword-level organic attribution is impossible | expectation mismatch with SEO agencies | state clearly; offer page-level GSC correlation |
| Consent regimes (CCPA/CPRA, state laws, two-party recording consent) | legal exposure | consent modes, announcement option, retention, deletion by phone |
| Number availability per area code; carrier spam labelling of dialed legs | local-presence gaps | state fallback; caller-ID pass-through avoids our numbers being the outbound caller |
| No chart library | dashboard effort | pick one in Phase 1 |
| `call_logs` holds 4 docs in preview; production volume UNKNOWN | reporting design untested at scale | `dni_daily` pre-aggregation from day one |

---

## 19. MVP recommendation and the three options

### Option A — Lean MVP (prove DNI attribution for one TracTru dealership)
Includes: Phase 1 complete + the minimal Phase 2 hook (tracked calls flow into the existing recording / transcript / summary pipeline and the call list shows them) + UTM and click-id capture (already in the snippet) + a single-dealer dashboard (calls by source / medium / campaign / number, confidence badge) + install verify + CSV export. No GA4, no agency portal, no ads APIs.
Estimate: **400-450 h · 8-9 weeks**. Operating cost: ≈ $38/month for the dealer + $150 fixed. Dependencies: pilot site access, 13 numbers in the dealer's subaccount, your approval of the voice-fallback change.

### Option B — Commercial Partner Release (multi-dealer, GA4 and campaign attribution)
Includes: Option A + Phase 2 complete (qualified / sales-vs-service, journey view, merge safety) + Phase 3 (GA4 OAuth, Data API panels, MP conversion events, GSC) + dedicated static campaign numbers (the API-free half of Phase 4) + Phase 5 core (agency roles and scope, onboarding wizard, multi-dealer dashboards, monthly PDF, white-label on reports, usage lines in partner invoices, legacy auth refactor).
Estimate: **1,050-1,150 h · 4.5-5.5 months** (Google verification runs in parallel). Operating cost: ≈ $38/dealer + $200-350 fixed + 0.1-0.25 FTE support at 10-50 dealers. Dependencies: Google Cloud OAuth verification, TracTru's dealer list and branding, pricing decision.

### Option C — Full Marketing Intelligence Platform
Includes: Option B + Phase 4 (Google Ads, Meta, TikTok APIs: spend, campaign names, offline conversion feedback) + Phase 6 (multi-touch, verified revenue attribution, ROAS, forecasting) + Looker Studio export.
Estimate: **1,700-1,900 h · 9-11 months** calendar including approvals. Operating cost: as B plus ≈ 15-25 h/month permanent API upkeep and 0.5-1 FTE support at 100-250 dealers.

### Recommended: Option B, staged so that Option A ships first
Reasons: (1) the parts that differentiate us from CallRail-class products are already ours (recording, Whisper, AI summaries, follow-up automation, journey) and Option B is what makes them visible to TracTru's clients next to GA4, which is the language an SEO/website agency sells in; (2) Option A alone is a pilot, not a product TracTru can roll out (no agency scope, no GA4); (3) the ad-platform APIs are the slowest, most fragile and least controllable work, and the attribution they add (campaign names, spend) can be approximated on day one through the UTMs TracTru already controls, so they belong after revenue exists. Shipping A at week 8-9 gives a live pilot while B's GA4 verification and agency work proceed.

---

## 20. Questions requiring your approval before any development

1. **Option**: A, B (recommended, A first), or C?
2. **Pilot dealership**: which TracTru client, its website platform, and who grants GTM / site access?
3. **Voice routing change**: approve replacing the "ring any admin" fallback for unknown numbers with a not-in-service message (affects existing behaviour), and enforcing Twilio signature validation on voice / recording routes?
4. **Number ownership and billing**: DNI numbers in the dealer organization's Twilio subaccount (recommended, per-org cost visibility) or in TracTru's own subaccount?
5. **Recording policy**: announce "this call may be recorded" by default (safe in all states) or per-dealer opt-in?
6. **Retention defaults**: recordings / transcripts 90 days, sessions 90 days, daily aggregates 13 months?
7. **GA4 OAuth branding**: one "I'm On Social" consent screen (fastest) or per white-label brand (more verification work)?
8. **Pricing**: start from the $149 / $249 / $399 structure with 30-40 percent agency wholesale?
9. **Chart library**: approve adding one frontend dependency for dashboards?
10. **Scope of the Lead Call Engine / lead sources**: should DNI calls also create `inbound_leads` records so they flow into the existing response-time analytics and proof cards, or stay as calls only? (Recommended: create a lead when the AI marks the call sales-qualified.)
11. **Legacy auth refactor**: approve moving partner billing / invoices / account-health send-report onto `require_role` as a Phase 5 prerequisite?

No code, schema, Twilio or deployment changes have been made for this plan.
