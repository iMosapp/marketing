# Unified Mystery Shop Customer Journey Engine — Audit, Gap Analysis & Plan (Oct 8 2026)

Status: AUDIT + PLAN ONLY. No production code changed. Awaiting approval before implementation.

## 1. Existing feature inventory (what is already built)

| Area | What exists | Where |
|---|---|---|
| Mystery Shop (human target) | Clients (`shop_clients`), people shopped (`shop_targets`), 50+ challenge personas (`scripts`, pool `mystery_shop`), phone / text / email shops as `roleplay_sessions` (kind `mystery_shop`), plan-month quotas, retry policy, leaderboard, public report & score pages, monthly report + weekly digest emails | `services/mystery_shops.py`, `routers/mystery_shops.py`, `services/text_shops.py`, `services/email_shops.py`, `services/shop_report_mail.py`, `frontend/app/admin/mystery-shops/*` |
| **Lead Shops (AI buyer lead = closest to this spec)** | One virtual buyer per shop: fictional first/last name, email on `INBOUND_EMAIL_DOMAIN`, pooled Twilio number (`phone_number_pool`, cap 10, 14-day cooldown, one active shop per number), ADF/XML lead push to the store's CRM or **manual "identity card" for the admin to type into the store's web form**, inbound **call** answered by AI in persona (GPT-Live / ConversationRelay, server-side recording), inbound **text** AI reply, inbound **email** AI reply with auto-responder detection, `events[]` timeline, windows 24h / 72h / 7d, process score (first response per channel, day-1 calls, follow-up days, "must" list) + AI quality grade + LLM coaching, score token page, 60-s sweep job | `services/lead_shops.py`, `routers/lead_shops.py`, `frontend/components/mystery-shops/lead-shops/*` |
| Email (Resend) | Outbound via `resend` SDK. Inbound `POST /api/webhooks/resend/inbound` (`email.received`, Svix verified when `RESEND_WEBHOOK_SECRET` set, fetches full body from the Receiving API, strips quotes, routes lead-shop → email-shop → real inbox, unmatched parked in `inbound_email_unmatched`). Separate delivery webhook `POST /api/email/webhook/resend` updates `email_logs` (delivered/opened/bounced/complained) | `routers/resend_webhooks.py`, `routers/email.py` |
| Twilio | Inbound SMS webhook with routing precedence (lead-shop number first), `inbound_message_dedup` on MessageSid, STOP/HELP/UNSTOP + DNC, signature validation helper (`TWILIO_WEBHOOK_VALIDATION` off/log/enforce, default log), inbound voice webhook (lead-shop numbers first), recording callbacks + Whisper transcription, live voice bridge | `routers/twilio_webhooks.py`, `services/twilio_signature.py`, `services/live_shops.py`, `services/live_host.py` |
| AI engine | `LlmChat` via Emergent key, model registry (`gpt-5.2` text, `gpt-5.4` vision, realtime voice), persona system prompts (`services/scripts._customer_system`), capped exchanges, humanized reply delays, AI grader (`services/scorecards.py` → `call_evaluations`) | `services/llm_models.py`, `services/scripts.py`, `services/scorecards.py` |
| Approval constructs | Inbox AI modes `auto_reply / auto_with_approval / draft_only / off`, `message_drafts`, `needs_assistance` escalation | `services/inboxes.py`, `routers/messages.py` |
| Scheduler | APScheduler in-process: `mystery_shop_dialer` 120 s, `lead_shops_sweep` 60 s, planner 6 h, report/digest hourly, campaign due-queue pattern | `backend/scheduler.py` |
| Tenant isolation | `get_accessible_user_ids` / `get_data_filter`, Twilio subaccount tokens | `routers/database.py`, `services/twilio_tenant.py` |

## 2. Gap analysis (spec phase → status)

| Spec requirement | Status | Note |
|---|---|---|
| P2 Virtual identity: name, email, number, interest, timeline, personality, questions/objections, AI instructions, dealership + shop id | PARTIAL | Lead Shop persona has name/email/number/offering/goals/summary; **missing**: buying timeline, personality & channel preferences as structured fields, scenario questions/objections list, per-identity AI instructions, admin edit before launch |
| P2 Generate 1–10 identities per campaign | MISSING | One lead shop at a time today; no campaign/batch object |
| P2 Number pool isolation | EXISTS | `phone_number_pool` purpose `lead_shop`, cap 10, cooldown 14 d, one active shop per number |
| P3 Separate verified testing domain | PARTIAL | `INBOUND_EMAIL_DOMAIN` (receiving) exists; **sending** falls back to `SENDER_EMAIL`'s domain (`LEAD_SENDER_DOMAIN` = main domain today) → violates "never from the primary domain" |
| P3 Authenticated webhooks + Receiving API | EXISTS | Svix verify + `GET /emails/receiving/{id}` |
| P3 Attachments | MISSING | Not fetched/stored |
| P3 Store headers, message ids, timestamps | PARTIAL | Body + from/to/subject + Resend id stored on the session; **no raw headers / Message-ID / References** |
| P3 Threaded replies (In-Reply-To / References) | MISSING | Replies rely on plus-addressing and subject |
| P3 Response analysis (time, personalization, questions answered, appointment attempts) | PARTIAL | Speed + "must" list + AI quality; personalization / question resolution / appointment effort not scored separately |
| P3 Modes: manual approval / auto / observe-only | MISSING | Auto only (inbox has the pattern to reuse) |
| P3 Delivery failure + webhook error tracking | PARTIAL | `email_logs` for main sends; nothing for shop sends; unmatched inbound parked |
| P4 SMS routing, history, AI reply, compliance | EXISTS | Modes missing (same as email) |
| P4 Voicemail recording + transcription as the default disposition | PARTIAL | AI always answers; voicemail TwiML only when shop is pending/closed; no transcription event, no call duration/disposition on the timeline |
| P4 Live AI voice permission-gated | PARTIAL | Live voice exists but is the default, not gated |
| P4 Recording consent announcement | MISSING | Recording starts server-side with no spoken disclosure |
| P5 Website form automation (inspect, map, preview, submit, screenshot) | MISSING | Manual identity card only. `playwright` is in requirements.txt but unused; Chromium not confirmed in the production image |
| P6 Unified journey record with first-meaningful-X markers, 30-day window, missing-evidence vs confirmed-non-response | PARTIAL | `events[]` + 24/72/168 h windows; no derived journey markers, no 30 d, no evidence-state distinction |
| P7 Configurable transparent scoring with evidence links, timeline, coaching, comparisons | PARTIAL | Process + quality + coaching per shop; no configurable rule set with evidence links, no cross-store / department / scenario comparison views |
| P8 Kill switch, approvals, signature enforcement, duplicate-reply guard, no real appointments | PARTIAL | Dedup exists; Twilio validation default `log`; no global emergency stop; no "never commit to an appointment" guardrail |

## 3. Recommended architecture — extend Lead Shops, don't rebuild

Treat `lead_shops` as the **journey record** (one per virtual customer) and add a thin layer around it.

New / changed collections
- `journey_campaigns` (NEW): `{org/client_id, name, department, scenario_id, identities[] (lead_shop ids), modes {email, sms, voice: observe|approve|auto}, live_voice_enabled, window_hours (24|72|168|720), authorization {by, at, website_url, note}, submission_limit, status (draft|armed|live|stopped|closed), emergency_stop {at, by}}`
- `lead_shops` (EXTEND): `identity {first, last, email, phone, interest, timeline, personality, channel_prefs, questions[], objections[], ai_instructions}`, `campaign_id`, `journey {lead_submitted_at, ack_at, first_email_at, first_sms_at, first_call_at, first_voicemail_at, appointment_attempts, unanswered_questions[], missed_followups[], persistence}`, `evidence_gaps[]`
- `shop_emails` (NEW): full inbound/outbound email record: `{shop_id, direction, resend_id, message_id, in_reply_to, references[], headers, from, to, subject, text, html, attachments[{name, type, size, storage_key}], received_at, processed_at, error}`
- `journey_drafts` (NEW): AI reply awaiting approval `{shop_id, channel, draft, created_at, decided_by, decision}`
- `journey_form_submissions` (NEW): `{shop_id, url, form_signature, field_map, preview, submitted_at, screenshot_key, confirmation_text, error, status}`
- `webhook_events` (NEW): `svix_id` unique index for Resend; Twilio keeps `inbound_message_dedup`
- `journey_scoring_rules` (NEW, per client with defaults): weights + targets per dimension

Services (new files, reuse existing helpers)
- `services/journey/identities.py` — generate 1–10 identities from a scenario (LLM fills personality/timeline/questions/objections; names from a curated list), reserve numbers via `lead_shops.acquire_number`, mint emails on the test domain
- `services/journey/email.py` — Resend send from the test domain with `In-Reply-To`/`References`, store `shop_emails`, fetch attachments, delivery-event handling; refuse to send if the domain is the primary one
- `services/journey/voice.py` — consent `<Say>` + voicemail `<Record>` default, transcription (Whisper), call duration/disposition events; live voice only when `campaign.live_voice_enabled` and the admin has `manage.shop_live_voice`
- `services/journey/forms.py` — Playwright: discover forms → propose field map → preview → submit → screenshot + confirmation; respects robots/CAPTCHA (stops and falls back to manual)
- `services/journey/orchestrator.py` — derives `journey` markers from `events[]`, windows up to 30 d, evidence-gap tracking (webhook failures, late events), emergency stop
- `services/journey/scoring.py` — rule-based dimensions with evidence links + AI-graded quality; comparisons
- Modes implemented once in `orchestrator.reply(...)`: observe → log only; approve → `journey_drafts` + push to admin; auto → send (existing path)

API (all admin, under `/api/journeys`)
- `POST /campaigns`, `GET /campaigns`, `GET /campaigns/{id}`, `PATCH /campaigns/{id}` (modes, windows), `POST /campaigns/{id}/identities/generate {count}`, `PATCH /identities/{id}`, `POST /campaigns/{id}/arm`, `POST /campaigns/{id}/stop` (emergency), `POST /campaigns/{id}/close`
- `POST /forms/inspect {url}`, `POST /forms/map {url, form, identity_id}`, `POST /forms/submit {submission_id}` (requires authorization record + limit), `GET /forms/{id}` (screenshot, confirmation)
- `GET /{shop_id}/timeline`, `GET /{shop_id}/emails/{email_id}` (+attachments), `GET /drafts`, `POST /drafts/{id}/approve|edit|reject`
- `GET /{shop_id}/scorecard`, `GET /compare?store=&department=&scenario=&from=&to=`
- Webhooks: extend `POST /api/webhooks/resend/inbound` to accept `email.delivered|bounced|complained` too (dedupe on `svix-id`); Twilio routes unchanged (lead-shop numbers already take precedence)

Frontend (admin): `app/admin/journeys/index.tsx` (campaigns), `[id].tsx` (identities, modes, live timeline per identity, approvals, scorecard, stop button), `compare.tsx`; reuse `LeadShopDetailSheet` timeline rendering and `ShopperPoolCard`.

## 4. Required third-party configuration (what I need from you)

### Resend account state found during the audit (Oct 8 2026, via the account API, read-only except one additive step)
- Verified domains: `imonsocial.com` (sending only), `imosapp.com` (sending + receiving flag), `calldrip.studio` (sending + receiving).
- **Inbound email is broken in production today, twice over:** (1) the only webhook in the account points at `https://app.imosapp.com/api/email/webhook/inbound` — that host does not resolve and that path does not exist (our handler is `POST /api/webhooks/resend/inbound`, the delivery handler is `POST /api/email/webhook/resend`); (2) live DNS for `imosapp.com` has Google Workspace MX records, not Resend's `inbound-smtp.us-east-1.amazonaws.com`, so mail to `*@imosapp.com` goes to Google. Lead Shop email replies therefore never reach the app. NOT changed during the audit (user asked for no production changes) — needs a go-ahead.
- `RESEND_WEBHOOK_SECRET` is empty in preview (signature verification skipped there); production value unknown.
- ADDED (additive, no behaviour change): domain `mvpline.com` created in Resend with sending + receiving, id `9afc94a9-f8e0-4f50-bbcd-c4d7a3806afe`, status `not_started` until the DNS records below exist. `mvpline.com` has no MX/A/TXT today (safe to use the root for receiving); nameservers are Google Cloud DNS (`ns-cloud-d1..d4.googledomains.com`).

DNS records to add for mvpline.com (exact values from Resend):
| Type | Host / Name | Value | Priority |
|---|---|---|---|
| TXT | `resend._domainkey` | `p=MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDUNHnM2SDauppPBKbX9AzZqzYvob2RifbEOCjQkWY4D5bGnMBtLx2y5Cc+6ezVOiiy+QgHTUiG1/XRk7Y8m7RkdaaNYxU+D15lgeY5UsHW3ALQKSNBW61FWJ5rUi2PLoaCay7u8HpuqtDgOxLIkptP8dh1Yyw29vEAfxBZNShrxwIDAQAB` | – |
| MX | `send` | `feedback-smtp.us-east-1.amazonses.com` | 10 |
| TXT | `send` | `v=spf1 include:amazonses.com ~all` | – |
| CNAME | `rsend` | `send.forge.rmta.net` | – |
| MX | `@` (root) | `inbound-smtp.us-east-1.amazonaws.com` | 10 |
| TXT (optional) | `_dmarc` | `v=DMARC1; p=none;` | – |
Then: `POST https://api.resend.com/domains/9afc94a9-f8e0-4f50-bbcd-c4d7a3806afe/verify` and poll `GET /domains/{id}` until every record is `verified`.

Production env once verified: `INBOUND_EMAIL_DOMAIN=mvpline.com`, `LEAD_SENDER_DOMAIN=mvpline.com`, `SHOP_EMAIL_DOMAIN=mvpline.com`, `RESEND_WEBHOOK_SECRET=<signing secret of the fixed webhook>`.
Webhook fix (needs go-ahead): re-point webhook `9f67e8de-281b-4938-8fa8-df774b1d9959` to `https://app.imonsocial.com/api/webhooks/resend/inbound` and subscribe `email.received`, `email.delivered`, `email.bounced`, `email.complained`.

Resend
1. Pick a **dedicated test domain or subdomain** that is not `imonsocial.com` (e.g. `shop.<neutral-domain>.com`). Today `INBOUND_EMAIL_DOMAIN=imosapp.com` receives; sending still uses `imonsocial.com`.
2. Resend → Domains → Add Domain → add that (sub)domain. Add the SPF/DKIM records Resend shows (sending). Then "Enable receiving" and add the exact MX record Resend shows (lowest priority; no other MX on that subdomain). Add a DMARC TXT (`v=DMARC1; p=none` to start).
3. Resend → Webhooks → Add: URL `https://app.imonsocial.com/api/webhooks/resend/inbound`, events `email.received`, `email.delivered`, `email.bounced`, `email.complained`. Copy the `whsec_…` secret.
4. API key: Resend → API Keys → create one scoped to sending (ideally limited to the test domain).
5. Give me (as backend secrets, not in chat): `RESEND_API_KEY` (if a new scoped key), `RESEND_WEBHOOK_SECRET`, `INBOUND_EMAIL_DOMAIN=<test domain>`, `LEAD_SENDER_DOMAIN=<same test domain>`, `SHOP_EMAIL_DOMAIN=<same test domain>`.
Limits: 40 MB per email, 30-day content retention on Pro (we archive to Mongo/object storage), inbound counts toward the plan quota (Pro 50k/mo, $20).

Twilio
- Pool numbers already handled (`phone_number_pool`); set `LEAD_SHOP_BUY_NUMBERS=true` in production to allow buying up to the cap. Voice + SMS webhooks on pool numbers already point at our routes. Set `TWILIO_WEBHOOK_VALIDATION=enforce` after a log-mode soak (one week).

Browser automation
- Production image must have Playwright Chromium (`playwright install chromium` + deps). Needs a feasibility spike on the Emergent deploy image first; fallback = manual identity card (exists).

## 5. Phased implementation plan (each phase shippable + tested)

| Phase | Scope | Complexity | Est. |
|---|---|---|---|
| 0 | Spike: Chromium in prod image; Resend test domain verified end to end (send + receive + threading) | S | 0.5 d |
| 2 | Campaigns + identity generator (1–10), identity editor, pool reservation, armed/live/closed states | M | 2–3 d |
| 3 | Email upgrade: dedicated domain enforcement, RFC threading, full headers + attachments in `shop_emails`, delivery events, modes (observe/approve/auto) + approvals queue | M | 2–3 d |
| 4 | Voice: consent line, voicemail-by-default + transcription + duration/disposition events, live voice gated by permission; SMS modes | M | 2 d |
| 6 | Journey orchestrator: markers, 30-day window, evidence gaps, emergency stop, duplicate-reply guard | M | 2–3 d |
| 7 | Scoring rules (configurable, evidence-linked), unified scorecard + coaching, compare view | M–L | 3–4 d |
| 5 | Website form automation (inspect → map → preview → submit → screenshot), authorization + limits, CAPTCHA stop + manual fallback | L | 4–5 d (+ infra risk) |
| 8 | Hardening: signature enforce, rate limits per campaign, retries/logging, e2e tests on a controlled test site + test identities | M | 2 d |

Order: 0 → 2 → 3 → 4 → 6 → 7 → 5 → 8 (form automation last because it carries the only infrastructure risk; everything else delivers value without it).

## 6. Operating cost estimate (per 30-day campaign of 10 identities)
- Twilio: 10 numbers × ~$1.15/mo + SMS ~$0.008/segment + voice ~$0.014/min + recording ~$0.0025/min ≈ $15–25
- Resend: inbound/outbound ≈ 200–400 emails → inside the Pro plan ($20/mo account-wide)
- LLM (Emergent key): text/email replies ~200 × ~$0.02 ≈ $4; scoring/coaching ≈ $2; live voice only if enabled (~$0.06–0.30/min with `gpt-realtime-2.1-mini`)
- Whisper transcription of voicemails: negligible
≈ $25–50 per campaign plus the Resend plan.

## 7. Risks to production and mitigations
- Shared webhooks (Resend inbound, Twilio SMS/voice): lead-shop numbers/addresses are matched first; new logic lives behind those existing branches, and every new branch is `try/except` + logged so a bug never breaks real inbox traffic.
- Twilio signature `enforce` could reject misconfigured legacy webhooks → enable per pool number first, then globally after a soak.
- Chromium in the production image: size/memory; isolate in Phase 5 with a feature flag and manual fallback.
- Email domain: enforce "test domain only" at the send helper so a misconfiguration refuses to send rather than sending from `imonsocial.com`.
- Scheduler load: new sweeps reuse the 60-s `lead_shops_sweep`; 30-day windows add no extra jobs.
- AI safety: persona instructions get a hard rule ("never confirm an appointment, never commit to buy; say you need to check and will get back"); approval mode default for new campaigns.
