# Architecture Hardening Plan (Oct 5 2026)

**STATUS: ON HOLD per user (Oct 5). Reference only. Do not start any phase without the user asking for it by name.**

Source: architecture audit (REQUEST_LOG #29). Approved order pending user. Each step is independently shippable and testable;
nothing changes user-facing behavior unless stated. "Gate" = what must pass before the step is called done.

## Phase 1 · Safety rails (≈ 1 week)

### 1.1 One auth module (S, 1 day)
- Target: `routers/rbac.py` becomes the only place that defines role checks. Add thin, named dependencies there:
  `require_user`, `require_manager` (MANAGER_ROLES), `require_admin`, `require_super_admin`, `require_owner` (OWNER_EMAIL), `require_store_admin`.
- Delete the 13 router-local copies: agents.py, contact_ask.py, go_links.py, inboxes.py, integrations.py, lead_flows.py, lead_queue.py,
  lead_sources.py (x2), mystery_shops.py, scorecards.py, scripts.py, workflows.py. Each router imports from rbac instead.
- Gate: `grep -rn "^async def require_" routers/*.py` returns only rbac.py; existing backend tests for lead sources / inboxes / agents pass;
  a manager token still gets 403 on POST /api/agents (covered by tests/test_agent_hub.py).

### 1.2 Scoping sweep (M, 2-3 days)
- Inventory every `db.contacts|conversations|messages|campaign_enrollments|lead_sources|appointments.find(` in routers/ and services/ that does
  not go through `get_data_filter` / `get_scoped_query_filter`. Script it: one grep + a hand-reviewed list in this file.
- Fix in order of blast radius: scheduler.py (already partly done), twilio_webhooks.py, messages.py, contacts.py, lead_intake.py, ai_reply.py.
- Add a regression test: two stores, same phone number, inbound SMS and campaign enrollment never cross (reuses the fixture pattern from
  the leak fix).
- Gate: inventory list is empty or every remaining raw query has a one-line justification; cross-store test passes.

### 1.3 Rate limits on public routes (S, half a day)
- `routers/website_widget.py` public router (`/w/...`: chat/start, message, ask, slots, event), `routers/lead_intake.py` webhooks,
  `routers/chat_widget.py` if kept. Per-IP + per-session token bucket in Mongo or in-process (single pod today); 429 with plain text.
- Gate: 61st request in a minute from one IP returns 429; the widget shows its existing "Hmm, something hiccuped" fallback.

### 1.4 Prod config checks (S, 1 hour)
- Confirm `TWILIO_WEBHOOK_VALIDATION=enforce` and `OWNER_EMAIL` in production env; remove the hardcoded `https://app.imonsocial.com`
  fallback in `frontend/services/api.ts` (fail loudly on native if `EXPO_PUBLIC_BACKEND_URL` is missing).
- Gate: deployer confirms env; native build points at the right API.

## Phase 2 · Durable background work (≈ 1 week)

### 2.1 `job_runs` collection + helper (M, 2 days)
- `services/jobs.py`: `run_job(name, fn, *, key=None, timeout_s)` writes `{name, key, status: running|done|failed, started_at, heartbeat_at,
  finished_at, error, pod}`; heartbeat every 15 s; `fail_interrupted()` at startup (same idea as widget_crawl.fail_interrupted).
- Wrap the 50 `scheduler.add_job` targets in scheduler.py with it (one decorator). Add `GET /api/owner/jobs` (owner-only) listing the last run
  per job: this is the "is the robot alive" screen the user has asked for in spirit (digest recipients, stuck setup texts).
- Gate: kill the backend mid-job in preview; after restart the run shows `failed: interrupted`, and the next tick runs normally.

### 2.2 Re-queueable background tasks (M, 2-3 days)
- Convert fire-and-forget `BackgroundTasks` that matter if lost into queued work in a `task_queue` collection with atomic claim
  (copy the `campaign_pending_sends` lock pattern at scheduler.py:1057-1075): outbound SMS/notifications in twilio_webhooks.py (15 sites),
  ai_reply.py (7), lead_call_engine.py (6), inboxes.py (5), dialer.py (5). Leave pure-cache/UX tasks as they are.
- One scheduler tick drains the queue every 5 s. Idempotency key per task so a retry never double-texts.
- Gate: restart during an inbound-SMS burst in preview; every reply still goes out exactly once (assert on `messages` count).

## Phase 3 · One brain (≈ 1 week, unlocks Portability Step 2)

### 3.1 LLM choke point (M, 2 days)
- `services/llm.py`: `chat(system, messages, *, model=CUSTOMER_TEXT_MODEL, timeout, session_id)`, `transcribe(audio)`, `speak(text)`.
  Internally emergentintegrations today; later the openai SDK behind the same signature.
- Migrate the 36 `LlmChat` sites, 5 `OpenAISpeechToText`, 2 `OpenAITextToSpeech` (list in REQUEST_LOG #29 audit). Mechanical, file by file,
  test after each group (widget, SMS replies, voice, docs/help).
- Gate: `grep -rl emergentintegrations backend --include=*.py | grep -v tests` returns only services/llm.py and services/payments.py.

### 3.2 Payments choke point (S, 1 day)
- `services/payments.py` wraps the 7 `StripeCheckout` sites (subscriptions.py, partners.py, mystery_shops proposals).
- Gate: checkout and webhook tests pass; same grep as above.

### 3.3 Prompt module (M, 2 days)
- `services/prompts/`: shared blocks (identity, channel rules, store facts, locale rule, no-em-dash) used by the 6 builders:
  ai_campaigns.build_clone_system_prompt, agents.sms_prompt, widget_chat.system_prompt, inboxes.build_inbox_va_prompt,
  contact_ask._system_prompt, team_ask._system_prompt. Builders keep their names; they compose blocks instead of repeating them.
- Gate: snapshot test of each builder's output before/after shows only whitespace/ordering changes.

### 3.4 Portability Step 2 (already specified, needs explicit go) (M, 2 days)
- Swap services/llm.py and services/payments.py internals to `openai` and `stripe` SDKs with the user's keys. Everything else untouched.

## Phase 4 · Kill the twins (≈ 1 week, spread out)

| Pair | Keep | Retire | How |
|---|---|---|---|
| `/admin/team` shared inboxes (routers/shared_inboxes.py) vs `/inboxes` (routers/inboxes.py + services/inboxes.py) | `/inboxes` (newer, has services layer, Agent Hub wired) | shared_inboxes.py | Point `app/admin/shared-inboxes.tsx`, `app/imos/shared-inboxes.tsx`, `(tabs)/inbox.tsx` (14 refs) at `/inboxes`; keep transfer endpoints that only exist in the old router by moving them. |
| routers/chat_widget.py (`/chat`) vs website_widget.py | website_widget | chat_widget.py | Zero frontend refs; check production logs for any `/api/chat/` hits for 7 days, then delete. |
| va_profiles.py vs agents.py | agents | va_profiles.py | Already read-mapped; once the shared-inboxes screen moves, delete the router and `ai_va_profiles` collection. |
| admin.py vs admin_users.py | split by domain | neither deleted | Move user endpoints out of admin.py into admin_users.py; admin.py keeps stores/orgs/system. |
| leaderboard.py vs leaderboard_v2.py | both live (4 refs to v2) | none | Document which screen uses which; no action. |
- Gate per row: frontend grep shows zero refs to the retired prefix; router removed from server.py; tests green.

## Phase 5 · Split the big files (ongoing, as touched)

- Frontend: `app/thread/[id].tsx` (5,472) -> `components/thread/{Header,MessageList,Composer,Attachments,AIAssist}.tsx` + hooks
  (`useThread`, `useComposer`); `(tabs)/inbox.tsx` (3,305) -> list/filters/row; `contact/[id].tsx` (3,097) -> tabs as files.
  Rule: no new code lands in a file over 1,500 lines without carving first.
- Backend: `routers/messages.py`, `lead_intake.py`, `twilio_webhooks.py`, `contacts.py` -> `routers/<domain>/` packages with
  `inbound.py / outbound.py / status.py`; `server.py` startup block -> `startup.py` (indexes, migrations, owner flag, crawl sweep, agents migration).
- One shared `serialize()` in `utils/serialize.py` replacing the 40 local ones, adopted as files are touched.
- Gate: every extracted piece keeps its data-testids; testing agent runs the thread/inbox/contact flows after each split.

## Phase 6 · Hygiene (anytime, small)

- GitHub Action: ruff + the unit-only subset of backend tests (those without BASE_URL) on every push.
- Structured logs with a request id (middleware sets `X-Request-ID`, logger includes it).
- `/app/memory/PRD.md` -> PRD.md (static) + CHANGELOG.md + ROADMAP.md; Company Docs sync reads CHANGELOG for the working log.

## Order and effort
Phase 1 (1 wk) -> Phase 2 (1 wk) -> Phase 3 (1 wk, then Step 2 on approval) -> Phase 4 (spread) -> Phase 5 (ongoing) -> Phase 6 (fill gaps).
Each phase ends with a testing-agent regression (widget chat, inbound SMS reply, campaign send, lead source intake, Agent Hub, billing).
