# Founder Command Center — Blueprint & Implementation Plan (v2, incorporates "Additional Requirements & Final Design Decisions")

Date: October 9, 2026 · Status: PLANNING ONLY. Nothing built, no schema, no deploy. Waiting for Phase 1 approval.

Legend: **VERIFIED** = read in code at the cited path · **ASSUMPTION** = planning estimate · **UNKNOWN** = not confirmed, treated as missing.
Precedence: where this v2 conflicts with the original prompt, the Additional Requirements win (Founder Focus is home; three-priority rule is enforced; Founder Advisor added; phases reordered).

---

## 1. What this is (and is not)

A private, founder-only strategic operating system inside I'm On Social at `/admin/command-center`. It answers, within five seconds: what am I trying to accomplish, what are my three priorities, what do I do next. It captures every idea without turning ideas into work. It is not a CRM, not a task manager, not customer-facing, and it must never touch campaigns, messages, Twilio, billing or customer records.

Operating principle encoded in software: **one objective · three strategic priorities · one next action · capture everything else.**

---

## 2. Architecture reuse assessment (verified)

| Need | What exists | Evidence | Decision |
|---|---|---|---|
| Founder-only access | `require_role("super_admin")` dependency; JWT or impersonation session | `routers/rbac.py:21-100`; used in `routers/account_health.py:1085` | **Reuse**, plus an allow-list of founder user ids in `settings` (key `command_center_access`) so other super admins (developers, support) are excluded by default |
| Admin entry point | More tab builds admin menu with `user?.role === 'super_admin'` checks; new screen = file under `app/admin/` + one menu line | `frontend/app/(tabs)/more.tsx:84-494` | **Extend** with one "Founder Command Center" entry |
| Theme (light/dark), brand accents | zustand `themeStore` with dark/light tokens, accent GOLD `#C9A962` | `frontend/store/themeStore.ts:1-90` | **Reuse as-is** |
| UI primitives | `ScreenHeader`; `Sheet, Field, Chip, GoldButton, Label, Stat, tid` (used by Journeys screens built this week) | `components/common/ScreenHeader.tsx`, `components/mystery-shops/shared.tsx` | **Reuse**; a thin `components/command-center/ui.tsx` wraps them so the module does not import from mystery-shops paths (portability) |
| Voice capture for ideas | `VoiceTextInput` (text input with mic) → `POST /api/voice/transcribe` (Whisper) | `frontend/components/VoiceTextInput.tsx`, `VoiceInput.tsx:86`, `routers/voice.py:34` | **Reuse as-is** (contact-free; no need for `voice_notes`, which requires a contact) |
| Structured LLM calls | `scripts._llm_json(system, user, timeout)` on gpt-5.2 via the existing Emergent key; `llm_models.py` constants | `services/scripts.py:178`, `services/llm_models.py:6-8` | **Reuse**; no new external AI service |
| Grounded Q&A pattern (citations, session collection) | `services/contact_ask.py` | `:1-60` | **Pattern reuse** for Founder Advisor (new session collection) |
| Versioned content | `company_docs` has a flat `version` string; SOPs have a boolean `is_published`; `phone_numbers.history[]` is the only array-history pattern | `routers/docs.py:296-339`, `models/sop.py`, `services/phone_numbers.py:306-312` | **New** `versions[]` + approval on `cc_documents` (small) |
| Audit trail | `permission_audit_log` writer; `audit_logs` and `system_logs` collections exist; no generic helper | `routers/permission_templates.py:30`, DB | **New** `cc_audit` (module-local, exportable) |
| Tasks | `tasks` is rep-facing, queried by `user_id`, contact-centric | `routers/tasks.py:314-327` | **Do not reuse** (would pollute rep "today" lists); roadmap items and priorities get their own collections |
| Platform-level config | `settings` collection keyed docs used by 10+ services | e.g. `services/compliance.py:289-294` | **Reuse** for access list and module config |
| PDF | fpdf2 (`_generate_quote_pdf`), `GET /docs/prd/pdf` | `routers/subscriptions.py:40-60`, `routers/docs.py:382` | **Reuse** fpdf2 for presentation export; web print via `window.print` on Expo web |
| Public share tokens | `stores.proof_share.token` with view counter; `short_urls` | `routers/public_proof.py:1-24`, `routers/short_urls.py` | **Pattern reuse**; new `cc_share_tokens` with expiry and revoke (external sharing off by default) |
| Weekly digest | per-entity `weekly_digest` config + scheduler cron | `services/shop_report_mail.py:279-335`, `scheduler.py` | **Optional later** (weekly idea review is a screen first; email off by default) |
| Real data for scorecard | partner agreements statuses (`routers/partners.py:766-859`), `demo_requests`, `bug_reports` (`routers/bug_reports.py:79,160`), orgs/stores counts, account health (`routers/account_health.py:217-847`) | VERIFIED collections | **Read-only adapters**; MRR / churn: `subscriptions.py` shows Stripe checkout and `status: active/inactive` on quotes, but no verified MRR aggregate → **UNKNOWN**, manual entry until verified |
| Charts | none in package.json (only react-native-svg) | VERIFIED | Phase 4 adds one small library, or uses SVG bars (recommended: SVG, no dependency) |
| Legacy header-only auth in docs router | `verify_admin_access(x_user_id)` | `routers/docs.py:17-25` | **Do not copy**; use rbac |

Safest implementation location: a self-contained module — backend `routers/command_center.py` + `services/command_center/*`, frontend `app/admin/command-center/*` + `components/command-center/*`, Mongo collections prefixed `cc_`. Zero changes to existing business logic; one menu line added in `more.tsx`; one `include_router` line in `server.py`.

---

## 3. Information architecture and navigation

Entry: More tab → **Founder Command Center** (visible only to allow-listed super admins). Default landing: **Founder Focus**.

Navigation (web: compact top bar; mobile: horizontal chip row under the header, no drawer):
`Focus · Strategy · Products · GTM · Roadmap · Idea Vault · Scorecard · Blueprint`
Strategy holds North Star + Pillars + Sales Motion (progressive disclosure, one screen with collapsible sections). Blueprint is the presentation view (Phase 5). The Founder Advisor is a slide-over available from every screen (one button), not a tab.

---

## 4. Page layouts

### 4.1 Founder Focus (home) — desktop (≥ 1024 px)
```
┌ Founder Command Center ── Focus · Strategy · Products · GTM · Roadmap · Idea Vault · Scorecard · Blueprint ──── [Advisor] ┐
│                                                                                                                         │
│  THE ONE BIG THING                                                                   ┌ CAPTURE AN IDEA ───────────────┐ │
│  Launch into equipment dealerships and validate a repeatable                         │ [ 🎙  Type or speak an idea… ]  │ │
│  partner-led sales model.                                                            │ pillar ▾  product ▾   [Save]   │ │
│  Why: … (one line)   Target: Jan 15, 2027   Progress ▇▇▇▇▁▁▁▁ 45%  · Status: On track │ "Saved to the Idea Vault"       │ │
│                                                                                      └────────────────────────────────┘ │
│  MY THREE PRIORITIES                                                                 WAITING ON                         │
│  ┌ 1 ▪ Finalize positioning & packages ──────────┐                                   • TracTru: pilot dealer list (Oct 14)│
│  │ Next: approve 3 product one-pagers · Due Oct 17│                                   • Dev: Journey Phase 3 DNS (you)    │
│  │ Owner: Forest · ▇▇▇▇▇▇▁▁ 70% · Done when: …    │                                   • Stripe: partner payout question    │
│  └───────────────────────────────────────────────┘                                                                      │
│  ┌ 2 ▪ Equipment dealer demo ─────────────────────┐                                   THIS WEEK'S WINS                   │
│  │ Next: record 6-min demo path · Due Oct 24      │                                   ✓ Journey campaigns shipped (Oct 9) │
│  └───────────────────────────────────────────────┘                                   ✓ Thread topics fix live (Oct 9)    │
│  ┌ 3 ▪ Recruit pilot partners ────────────────────┐                                   ✓ DNI plan delivered (Oct 9)        │
│  │ Next: 3 intro calls booked · Due Oct 31        │                                                                      │
│  └───────────────────────────────────────────────┘                                                                      │
│  [ + Propose a priority ]  (opens: "All three slots are full. Complete, pause or replace one, or park it as an idea.")   │
│                                                                                                                         │
│  NEXT BEST ACTION ─ recommended by Advisor, not done ─────────────────────────────────────────────────────────────────  │
│  "Send the three product one-pagers to TracTru before Tuesday's call."  Why: unblocks priority 1 and the pilot list.    │
│  [Accept]  [Modify]  [Defer ▾]  [Dismiss]                                                                              │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```
Everything below the fold (blockers detail, roadmap, metrics) is one tap away; nothing else is on this screen.

### 4.2 Founder Focus — mobile (stacked, same order of importance)
```
┌ Founder Command Center        [Advisor] ┐
│ Focus · Strategy · Products · GTM · …  │  ← horizontal chips
│ THE ONE BIG THING                      │
│ Launch into equipment dealerships…     │
│ Target Jan 15 · ▇▇▇▇▁▁▁▁ 45% · On track │
│ NEXT BEST ACTION                       │
│ Send the three one-pagers to TracTru…  │
│ [Accept] [Modify] [Defer] [Dismiss]    │
│ MY THREE PRIORITIES                    │
│ 1 Finalize positioning  ▇▇▇▇▇▇▁▁ Oct 17│
│ 2 Equipment demo        ▇▇▁▁▁▁▁▁ Oct 24│
│ 3 Recruit pilots        ▇▁▁▁▁▁▁▁ Oct 31│
│ WAITING ON (3)  ▸        WINS (3)  ▸   │
│ ┌──────────────────────────────────┐   │
│ │ 🎙  Capture an idea…      [Save] │   │  ← sticky bottom bar
│ └──────────────────────────────────┘   │
└────────────────────────────────────────┘
```
On mobile, Next Best Action sits directly under the objective (the two things you act on), the three priorities are compact rows that expand on tap, and idea capture is a sticky bar so an idea takes one tap, one sentence, one save.

### 4.3 Other screens (one line each)
- **Strategy**: North Star header (approved statements with "edit → confirm → new version"), four pillar cards → detail sheet (purpose, problems, features by primary/secondary pillar, status, target customer, revenue opportunity, KPIs, planned enhancements), Sales Motion `DIAGNOSE → DEMONSTRATE → DEPLOY → EXPAND` with editable playbooks.
- **Products**: three product cards (Relationship OS, Opportunity Intelligence, Performance Intelligence) with problem, value proposition, buyer, capabilities, readiness, pricing (uncommitted), demo/collateral/pilot readiness, revenue (only when connected).
- **GTM**: beachhead / secondary / future markets (future = "exploration" badge), partner strategy board (table on web, cards on mobile) with stage, next action, owner, date, reach, notes.
- **Roadmap**: 90-day timeline (Package 1-30 · Validate 31-60 · Replicate 61-90) with initiatives, progress bars; editing a strategic initiative asks for a reason and shows an impact assessment card.
- **Idea Vault**: capture bar, list with status chips (Captured · Evaluating · Parked · Approved · Active · Rejected), idea detail with the five questions + AI recommendation, decision-filter scorecard, **Weekly Review** tab (new, awaiting evaluation, recommended to validate, parked worth reconsidering, connected to active customer opportunities).
- **Scorecard**: four tiles (Product, Revenue, Partnerships, Execution) each with 3-5 numbers; every number shows `manual` or `system` and the as-of date; no fabricated values.
- **Blueprint**: presentation view, internal/external toggle, print/PDF, share (off by default).

---

## 5. Data model (all new, prefixed `cc_`, platform-level, exportable)

| Collection | Purpose | Key fields |
|---|---|---|
| `cc_documents` | North Star statements (company, category, vision, promise, mission, philosophy, positioning), playbooks, market definitions | `key, title, body, status: draft\|approved, versions[{body, by, at, reason}], approved_at, approved_by, visibility: internal\|external` |
| `cc_pillars` | the four pillars | `key, name, promise, capabilities[], outcome, purpose, problems[], target_customer, revenue_opportunity, kpis[], enhancements[], status` |
| `cc_features` | platform features mapped to pillars | `name, primary_pillar, secondary_pillars[], status: live\|beta\|planned\|unknown, products[]` |
| `cc_products` | three commercial offerings | `key, name, target, promise, problem, value_prop, capabilities[], readiness{product, demo, collateral, pilot}: unknown\|not_started\|in_progress\|ready, pricing{status: uncommitted, notes}, revenue{source: manual\|system, values}` |
| `cc_markets` | beachhead / secondary / future | `name, tier: primary\|secondary\|exploration, reasons[]` |
| `cc_partners` | partner strategy board | `name, type, fit, offering, stage: identified\|contacted\|exploring\|proposal\|pilot\|agreement (verified flag), next_action, owner, target_date, reach, notes, agreement_verified: bool` |
| `cc_objective` | THE ONE BIG THING (singleton, versioned) | `title, why, target_date, progress_pct, status, versions[]` |
| `cc_priorities` | strategic and operational items | `title, kind: strategic\|operational, status: proposed\|active\|paused\|completed\|replaced, slot (1-3 for active strategic), pillar, product, business_objective, next_action, due_date, owner, progress_pct, definition_of_done, replaced_by, history[]` |
| `cc_focus` | singleton enforcing the three-slot rule | `active_strategic_ids[] (max 3, enforced atomically), next_action_id, updated_at` |
| `cc_actions` | next best actions | `text, why, priority_id, source: advisor\|founder, state: recommended\|accepted\|modified\|deferred\|dismissed\|done, deferred_until, decided_at` (never auto-marked done) |
| `cc_blockers` | waiting-on items | `title, waiting_on (party), since, due, priority_id?, status` |
| `cc_wins` | this week's wins | `title, at, priority_id?, source: manual\|system` |
| `cc_roadmap` | 90-day initiatives | `phase: package\|validate\|replicate, title, priority, owner, status, due, dependencies[], definition_of_done, success_metric, pillar, product, change_log[{reason, impact, by, at}]` |
| `cc_ideas` | the Idea Vault | `title, description, transcript?, pillar, product, customer, value, complexity, urgency, status, evaluation{answers{q1..q5}, ai{recommendation: pursue\|validate\|park\|decline, rationale, at}}, decision_filter{scores, recommendation}, linked_opportunity?, created_at, reviewed_at` |
| `cc_criteria` | editable scoring criteria for the decision filter | `key, label, weight, scale_help` |
| `cc_metrics` | scorecard values | `category, key, value, unit, as_of, source: manual\|system, adapter?, note` |
| `cc_advisor_sessions` | Founder Advisor conversations | `messages[], context_snapshot_hash, proposals[{type, payload, state: proposed\|confirmed\|rejected}]` |
| `cc_presentations` | Blueprint decks | `audience: internal\|external, status: draft\|published, sections[], published_at` |
| `cc_share_tokens` | external sharing (off by default) | `presentation_id, token, expires_at, revoked, views` |
| `cc_audit` | who changed what and why | `entity, entity_id, action, before, after, reason, by, at` |
`settings` key `command_center_access`: `{user_ids: [...], weekly_review_email: false}`.
No existing collection is modified. Export: `GET /api/command-center/export` returns a JSON bundle plus Markdown renderings of statements, pillars, products, GTM, roadmap, ideas (portability requirement).

---

## 6. API surface (documented, module-local, all `Depends(require_cc_access)`)
`/api/command-center/…`
- `GET /focus` (one payload for the home screen) · `GET/PUT /objective` · `GET/POST/PATCH /priorities` · `POST /priorities/{id}/activate` (returns 409 with "which one should this replace?" when three are active) · `POST /priorities/{id}/pause|complete|replace` (body `{replace_id, reason}`)
- `GET /actions/next` · `POST /actions/recommend` (AI) · `POST /actions/{id}/accept|modify|defer|dismiss|done`
- `GET/POST/PATCH /blockers` · `GET/POST /wins`
- `GET/PUT /documents/{key}` (PUT = new draft version) · `POST /documents/{key}/approve` (confirmation + reason)
- `GET/PATCH /pillars/{key}` · `GET/POST/PATCH /features` · `GET/PATCH /products/{key}` · `GET/POST/PATCH /markets` · `GET/POST/PATCH/DELETE /partners`
- `GET/POST/PATCH /roadmap` (PATCH on a strategic item requires `reason`; returns impact assessment)
- `POST /ideas` (≤ 30 s path: title only is enough) · `GET /ideas?status=` · `PATCH /ideas/{id}` · `POST /ideas/{id}/evaluate` (AI recommendation, advisory) · `POST /ideas/{id}/filter` (decision scorecard) · `GET /ideas/weekly-review`
- `GET/PUT /criteria` · `GET /scorecard` · `PUT /metrics/{key}` · `POST /metrics/refresh` (read-only adapters)
- `POST /advisor/sessions` · `POST /advisor/sessions/{id}/message` · `POST /advisor/proposals/{id}/confirm|reject`
- `GET/POST/PATCH /presentations` · `POST /presentations/{id}/publish` · `GET /presentations/{id}/pdf` · `POST /presentations/{id}/share` (creates token, disabled unless explicitly enabled) · public `GET /api/cc/share/{token}` (external view only)
- `GET /export`

---

## 7. Enforcement rules (server-side, tested)
1. **Three strategic priorities**: `cc_focus.active_strategic_ids` is updated with `update_one({_id: "focus", "active_strategic_ids.2": {$exists: false}}, {$push: ...})`; a failed match returns 409 and the UI shows "Which existing priority should this replace, or should we park the new idea?" with the three options (complete / pause / replace) and a "Park as idea" button. Operational items (`kind: operational`) never occupy slots. No override path creates a fourth slot; overrides are limited to *which* three.
2. **Every strategic priority and roadmap initiative requires** a pillar and a business objective / commercial purpose (422 otherwise).
3. **Approved statements** change only through draft → confirm → approve, each version kept with reason; `cc_audit` written on every approve, priority change, roadmap strategic change, idea status change.
4. **Strategic roadmap changes require a reason**, and the server returns an impact assessment (which priorities and dependencies move) that the founder acknowledges.
5. **AI is advisory**: advisor and evaluators write only to `recommendation` fields and `proposals`; mutations happen through the regular endpoints with the founder's explicit confirm. Actions recommended by AI are stored as `recommended`, never `done`.
6. **Ideas default to Captured**; no notification is sent for parked ideas; the weekly review is a screen (email optional, default off).
7. **External sharing disabled by default**; external views render only `visibility: external` content and exclude financial assumptions, partner notes, roadmap details, unapproved claims, technical detail (field-level flags, server-side filtering).

---

## 8. Founder Advisor design
- Context compiler (`services/command_center/advisor.py`): builds a cached "strategy brief" (approved statements, pillars, products, GTM, active priorities with status, next action, roadmap by phase, approved decisions from `cc_audit`, idea counts by status and the ideas referenced, blockers). Cached per hash of the underlying documents; ~3-5k tokens.
- Model: gpt-5.2 through the existing Emergent key (same as Jessi; no new vendor). Sessions in `cc_advisor_sessions`.
- System prompt guardrails: constructive, direct, concise; challenge complexity; separate evidence from assumptions ("you have not established the customer problem or revenue"); recommend the simplest viable approach; state opportunity cost against the three active priorities; never approve development; never change priorities, only propose; not every idea is urgent. Default stance when an idea arrives while three slots are full: "Which one would this replace, or park it?"
- Output contract: prose plus optional `proposals[]` (e.g. `park_idea`, `replace_priority`, `set_next_action`) rendered as cards with Confirm / Reject; confirm calls the normal endpoint with the founder as actor and the advisor's rationale as `reason`.
- Tests: adversarial fixtures (shiny new feature during a full slate; idea with no customer problem; idea tied to an active pilot) asserting the recommendation class and that no state changed.

---

## 9. Seed content (from your prompt, loaded as **drafts**, not approved; readiness fields start `unknown`)
North Star statements; four pillars with promises, capabilities and outcomes; three products with targets, promises and capabilities (pricing `uncommitted`, readiness `unknown`, revenue empty); markets (equipment dealerships primary with your five reasons; automotive secondary; individual sales professionals, real estate, insurance, home services, other relationship-driven industries as exploration); partner categories; TracTru as a partner at stage `exploring` with `agreement_verified: false`; sales motion stages with empty playbooks; 90-day roadmap items (7 + 6 + 6) unassigned, status `not_started`; proposed objective "Launch into equipment dealerships and validate a repeatable partner-led sales model." as `proposed`; the three suggested priorities as `proposed` (you activate them, which is the first test of the slot rule). Nothing is marked done, verified, priced or connected.

---

## 10. Phases, effort, risk (ASSUMPTIONS: one engineer, includes tests)

| Phase | Scope | Hours | Elapsed | Risk |
|---|---|---|---|---|
| **1 Strategic Foundation** | module skeleton (router, services, `cc_` collections, access allow-list, audit, export), navigation shell (web/mobile), North Star with versions + approval, pillars + feature mapping, products, GTM (markets, partner board), sales motion playbooks, seed loader, **read-only Founder Focus preview** rendering proposed objective/priorities (no enforcement yet) | 170-190 | 3.5-4 weeks | low; biggest risk is scope creep (mitigated: anything new goes into the Idea Vault once it exists) |
| **2 Founder Focus** | objective, three-slot enforcement with replace/pause/park flow, next best action (AI recommend + accept/modify/defer/dismiss), waiting-on, wins, 90-day roadmap with timeline/progress, reason + impact assessment on strategic changes | 130-150 | 3 weeks | medium; atomic slot rule and UX for the replace flow need care |
| **3 Idea Vault + Advisor** | ≤ 30 s capture (text + VoiceTextInput), vault, statuses, five-question evaluation with AI recommendation, decision filter with editable criteria, weekly review screen, Founder Advisor slide-over with proposals | 140-160 | 3 weeks | medium; advisor agreeableness (tested with adversarial fixtures) |
| **4 Business Scorecards** | manual metrics with as-of, read-only adapters (partners stage counts, demo requests, open bug reports, orgs/stores active, roadmap completion, pilot conversion from `cc_partners`), SVG bars | 65-80 | 1.5-2 weeks | low; MRR/churn stay manual until `subscriptions` data is verified |
| **5 Executive Presentation** | internal/external Blueprint views, draft/published, print + fpdf2 PDF, share tokens (off by default, expiry, revoke) | 75-90 | 2 weeks | low-medium; PDF fidelity with fpdf2 is basic (text + simple shapes) |
| **Total** | | **580-670** | ~13-14 weeks sequential | |

Phase 1 ships nothing that changes behaviour for any other user.

---

## 11. Security and access control
- Server-side: `require_cc_access` = `require_role("super_admin")` **and** user id in `settings.command_center_access.user_ids` (default: the founder's account only; 403 otherwise, including for impersonation sessions).
- No tenant data is read except through explicit read-only adapters in Phase 4, each listing the collection and fields it reads; the module never writes to any non-`cc_` collection.
- No customer-facing navigation; routes live under `/admin/command-center`; the public share route exists only for published external presentations with a live, unexpired, unrevoked token; disabled unless the founder turns sharing on per presentation.
- Audit: every approve, priority activation/pause/replace, roadmap strategic change, idea status change, share token creation → `cc_audit` with before/after/reason/actor.
- Input validation with Pydantic; AI outputs validated to the recommendation enums; `no_em_dash` applied to AI text (house style rule).
- Secrets: none new (uses the existing Emergent LLM key). No new external services. No deploy without approval.

---

## 12. Phase 1 acceptance criteria
1. Only the allow-listed founder account can open `/admin/command-center`; another super admin gets 403 on the API and no menu entry.
2. Opening the Command Center lands on **Founder Focus**, which shows the proposed One Big Thing, three proposed priorities (as read-only preview), empty Waiting On / Wins, and a working idea capture bar that saves to `cc_ideas` with status `Captured` in one action (voice or text).
3. Strategy shows the North Star statements as drafts; editing a statement creates a new version; approving requires a confirmation with a reason; the previous version is visible in history; `cc_audit` has the entry.
4. Four pillars render with your capabilities and outcomes; a feature can be assigned a primary pillar and optional secondary pillars; pillar detail shows status fields as `unknown` until set.
5. Products show the three offerings with pricing `uncommitted` and readiness `unknown`; no revenue numbers appear.
6. GTM shows equipment dealerships as primary with the five reasons, automotive as secondary, future markets badged "exploration"; the partner board lists TracTru at stage `exploring` with no agreement marked complete.
7. Sales motion shows the four stages with editable (empty) playbooks.
8. `GET /api/command-center/export` returns a JSON + Markdown bundle of everything above.
9. Works on desktop web and a phone-width viewport; light and dark mode; no new dependencies.
10. Backend tests cover access control, versioning/approval, feature↔pillar assignment, idea capture, export; UI flows verified by the testing agent.

---

## 13. Decisions requiring your approval
1. Approve **Phase 1** as scoped (§10) and the module location `/admin/command-center` with the More-tab entry.
2. **Access list**: only your account (recommended), or all super admins?
3. **Seed content loads as drafts** you approve in the app (recommended) vs pre-approved.
4. Founder Advisor and idea evaluation use **gpt-5.2 through the existing Emergent key** (no new AI service) — confirm.
5. Idea capture reuses **VoiceTextInput → /api/voice/transcribe** (Whisper) — confirm.
6. Weekly idea review is a **screen only**; optional email digest stays off by default — confirm.
7. Scorecard: **MRR, churn, expansion are manual entry** until a verified revenue source exists — confirm; which partner/pilot statuses count as "active" (proposal: `exploring`, `proposal`, `pilot`).
8. Charts via plain SVG (no dependency) for Phase 4 — confirm, or approve a chart library.
9. Default **owner** on all seeded items = you; due dates left blank until you set them — confirm.
10. Export format: JSON + Markdown bundle (portable, Git-friendly) — confirm.

Stopped here. No code, schema or deployment changes were made.

---

# PHASE 1A — REVISED MVP PLAN (Oct 9, 2026; founder approved the direction, not the 170-190 h scope)

Decisions taken from the founder: owner-account-only access; seed as editable drafts; reuse theme / auth / Whisper; GPT-5.2 later for the Advisor; weekly review screen-only, no email; metrics manual; active partner stages Qualified / Discovery / Proposal / Pilot / Negotiation (recorded for Phase 4); plain SVG; default owner = founder, due dates blank; JSON + Markdown export; portability; smallest schema.

## A. Access (verified reuse, no new infrastructure)
The app already has an **Owner layer** above super admins: `users.is_owner` (one account: forest@imosapp.com), `is_owner(user)`, `can_see(db, user, key)` and the `OWNER_TOOLS` visibility list in `routers/owner.py:12-67`. The Command Center registers as owner tool `("command_center", "Founder Command Center", False)` → visible to the owner only; other super admins get 403 and no menu entry unless the owner later grants it from Owner Settings. No `settings` allow-list needed.

## B. Simplified data model: 20 → 5 collections (+ none modified)
| Collection | Holds | Integrity |
|---|---|---|
| `cc_blueprint` | one doc per `key`: `mission, vision, positioning, promise, philosophy, objective (One Big Thing), pillar.capture/understand/engage/improve, product.relationship_os/opportunity_intelligence/performance_intelligence, next_action, focus` (singleton holding `active_priority_ids`) · `{key, kind, data{}, status: draft\|approved, versions[{data, by, at, reason}], updated_at}` | unique index on `key`; approve requires reason; previous versions kept |
| `cc_priorities` | strategic priorities · `{title, status: proposed\|active\|paused\|completed\|replaced, pillar, product, purpose, next_action, due (null), owner, progress_pct, definition_of_done, history[]}` | **slot rule**: `cc_blueprint{key:"focus"}.active_priority_ids` updated with `update_one({key:"focus", "data.active_priority_ids.2": {$exists: false}}, {$push: ...})` → 409 when three are active; pillar + purpose required (422) |
| `cc_roadmap` | 90-day milestones · `{phase: package\|validate\|replicate, title, status: not_started\|in_progress\|done\|blocked, owner, due (null), pillar, product, note}` | simple; no dependency engine |
| `cc_ideas` | Idea Vault · `{title, description, transcript?, pillar?, product?, status: captured\|evaluating\|parked\|approved\|active\|rejected, created_at, reviewed_at}` | default `captured`; status changes never create roadmap items |
| `cc_notes` | Waiting On and Wins · `{kind: waiting\|win, title, party?, since, due?, priority_id?, status: open\|done}` | tiny |
Audit: approvals, priority activations / replacements and idea status changes append to `cc_blueprint`/`cc_priorities` `history[]`/`versions[]` (no separate audit collection in 1A; `cc_audit` arrives with Phase 2 if needed). Export reads these five collections only.

## C. Screens (4) and entry
- More tab → **Founder Command Center** (owner tool key) → `app/admin/command-center/index.tsx` = **Founder Focus** (default): One Big Thing card (title, why, target, progress, status; tap → edit sheet), up to three Active Priority cards (status, next action, due, owner, progress, done-when; tap → edit; "Propose a priority" → when 3 are active the server's 409 drives the "complete, pause or replace one, or park as an idea" sheet), Next Best Action card (manual text + why; Accept marks it current; Edit; Clear), Waiting On list (add/done), This Week's Wins (add; shows last 7 days), sticky Capture-an-idea bar (`VoiceTextInput`, saves to `cc_ideas` as `captured`).
- `strategy.tsx`: North Star (five statements; edit → "Save draft" → "Approve (reason)" → version history list), four Pillar cards (promise, capabilities, outcome; tap → detail/edit), three Product cards (target, promise, includes, readiness `unknown`, pricing `uncommitted`; tap → edit).
- `roadmap.tsx`: three phase columns on web / stacked on mobile, milestone rows with status chips, add/edit sheet, phase progress bars (SVG).
- `ideas.tsx`: capture bar, status filter chips, "New this week" and "Parked" quick filters (the screen-only weekly review), idea sheet (fields + status chips). No AI.
Shared: `components/command-center/` (nav chips, cards, sheets, progress bar). Mobile = chip row nav + stacked cards; web ≥ 1024 px = two columns on Focus.

## D. Endpoints (`/api/command-center`, all `Depends(require_cc)` = owner or granted visibility)
`GET /focus` · `GET /blueprint` · `PUT /blueprint/{key}` (new draft version) · `POST /blueprint/{key}/approve` `{reason}` · `GET /blueprint/{key}/versions`
`GET/POST /priorities` · `PATCH /priorities/{id}` · `POST /priorities/{id}/activate` (409 when full) · `POST /priorities/{id}/pause` · `POST /priorities/{id}/complete` · `POST /priorities/{id}/replace` `{replace_id, reason}`
`PUT /next-action` `{text, why}` · `DELETE /next-action`
`GET/POST /notes` · `PATCH /notes/{id}` · `DELETE /notes/{id}`
`GET/POST /roadmap` · `PATCH /roadmap/{id}` · `DELETE /roadmap/{id}`
`GET/POST /ideas` · `PATCH /ideas/{id}` · `DELETE /ideas/{id}`
`GET /export.json` · `GET /export.md` · `POST /seed` (idempotent: inserts missing keys only, never overwrites edits)
22 endpoints, one router file, one service file.

## E. Revised estimate (validated against the codebase)
| Work | Hours |
|---|---|
| Backend: service + router, slot rule, versioning/approval, seed, export, owner-tool registration | 10-12 |
| Backend tests (access, slot rule incl. concurrency, approval/versions, seed idempotency, export) | 4-5 |
| Frontend: Focus (6 blocks + sheets + capture bar), Strategy, Roadmap, Ideas, nav shell, responsive, light/dark, More-tab entry | 16-20 |
| Testing-agent pass + fixes | 4-5 |
| **Phase 1A total** | **34-42 h** |
This sits at the top of the 20-40 target. It is honest for four polished, mobile-friendly screens with sheets; the backend is small. If you want to land under 32 h, the **smallest functional release (1A-min, 26-30 h)** drops: the version-history viewer (versions still saved server-side, no UI), pillar/product *editing* (seeded content displays; edit arrives in 1B), and the roadmap edit sheet (status chips only, add via a one-line field). Everything on Founder Focus, the slot rule, idea capture and export stay.

## F. Acceptance criteria (Phase 1A)
1. Only the owner account opens `/admin/command-center` and sees the More-tab entry; another super admin gets 403 on every `/api/command-center/*` call.
2. Landing is Founder Focus with: One Big Thing (seeded proposal, editable), three priority slots (seeded proposals start `proposed`; activating the fourth returns 409 and shows the complete / pause / replace / park choice; no fourth active ever appears, including under 20 parallel activate calls in tests), Next Best Action (manual add / edit / clear), Waiting On (add / done), Wins (add, last 7 days), Capture bar (text or voice → `cc_ideas` `captured` in one action, confirmation toast, screen stays on Focus).
3. Strategy: five statements seeded as drafts; "Save draft" creates a version; "Approve" requires a reason and marks approved; history lists versions with who / when / reason. Four pillars and three products render seeded content; pricing shows "uncommitted", readiness "unknown"; edits persist.
4. Roadmap: 19 seeded milestones across Package / Validate / Replicate, owner = founder, due blank, status changes persist, phase progress bars reflect done counts.
5. Ideas: list with status filter chips, "New this week" and "Parked" filters, status edits persist; an idea never creates a roadmap item or priority.
6. `GET /export.json` and `GET /export.md` return everything in the five collections; Markdown is readable as a company blueprint.
7. Works on web desktop and a 390 px viewport, light and dark; no new dependencies; no existing collection written; no changes to campaigns, messages, Twilio, billing or customer data.

## G. Implementation risks
- Voice capture on web records WebM via MediaRecorder with a 30-s auto-stop (`components/VoiceInput.tsx:15-135`) and works on iOS/Android through expo-av; Safari web MediaRecorder support varies → text capture is always available as the fallback.
- The slot rule relies on the singleton `focus` doc; the activate / replace flow must be the only writer of `active_priority_ids` (enforced in the service; tests cover parallel activations).
- Seed idempotency: `POST /seed` and first `GET /focus` insert only missing keys so re-running never overwrites founder edits.
- Expo Router nested folder `app/admin/command-center/*` follows the pattern already used for `app/admin/journeys/[id].tsx` (works on web and native).
- Scope creep is the real risk; anything outside §C/§D goes into the Idea Vault once it exists.

STOP: awaiting final approval of Phase 1A (34-42 h) or 1A-min (26-30 h). Nothing built.
