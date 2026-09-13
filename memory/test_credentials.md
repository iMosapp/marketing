# Test Credentials

## Super Admin
- Email: forest@imosapp.com
- Password: Admin123!

## Test User (No Store / No Org)
- Email: mjeast1985@gmail.com
- Password: NavyBean1!
- Notes: onboarding_complete: null, store_id: null, org_id: null, role: user, status: active

## Activation-Flow Test User (created June 2026, preview only)
- Email: activation-tester@invalid.imonsocial.test
- Phone: +15005550006 (Twilio test number, never a real person)
- Password: NewPass123! (set via /api/auth/activate/complete)
- Notes: role user, phone_verified true. Safe to reuse for /auth/activate or forgot-password tests.

## QA Store Manager (preview only, seeded June 2026 via backend/tests/seed_qa_manager.py, idempotent)
- Email: qa-manager@invalid.imonsocial.test
- Password: Manager123!
- Notes: role store_manager on Forest's store 69a0b7095fddcede09591668 ("i'M On social"). Use for any manager screen that needs a store (Lead Source Config, Connect Zapier / Make, Proof spend editor). forest@imosapp.com is super_admin with NO store_id in preview, so store-scoped lists come back empty for him.

## SMS SAFETY RULE
- Twilio credentials in preview are LIVE. Only ever use 500-555-XXXX phone numbers (Twilio test range) for any code / invite / broadcast test. Never trigger flows against real numbers (e.g. forest's 8016349122).

## Preview URL note (June 2026)
- REACT_APP_BACKEND_URL in frontend/.env is the ONLY valid preview host (currently https://user-routing-issue.preview.emergentagent.com). imos-deploy-prep.preview.emergentagent.com is a stale preview that shows the Emergent "wake up servers" page.
- Web-only: /help and /inbox URLs are shadowed by static marketing pages; navigate in-app (history.pushState + popstate) when scripting.

## Shared Inbox demo data (preview only, `cd /app/backend && python tests/seed_inbox_demo.py` re-seeds idempotently, `--wipe` removes)
- Sales inbox (+15005550200, jump ball, members QA Manager + Activation Tester + Forest) and Service inbox (+15005550210, round robin, members QA Manager + Activation Tester), store 69a0b7095fddcede09591668.
- Demo customers are Twilio test numbers +15005550031 / 32 / 33 ("Lead (0031)" etc). SMS/push are stubbed during seeding only; live actions in the UI hit real Twilio (harmless: 500-555 numbers are rejected).
- Manager UI: log in as qa-manager; rep UI: activation-tester. Hub > Manage > Inboxes = /inboxes (library) and /inboxes/{id} (editor).

## Call Scorecards demo data (preview only, `cd /app/backend && python tests/seed_scorecard_demo.py` re-seeds + AI-grades idempotently, `--wipe` removes, `--no-grade` skips the LLM)
- Seeds 3 fake recorded calls (transcripts only, no audio) for Activation Tester: CA_scdemo_good_001 (Sarah Tester, ~100%), CA_scdemo_miss_002 (Mike Tester, low score, 2 critical misses), CA_scdemo_mid_003 (Dana Tester, mid). Also sets activation-tester.store_id to the QA store so the store's default scorecard applies.
- Default scorecard "Internet Sales Call" exists on store 69a0b7095fddcede09591668 (created by qa-manager). Manager screens: Hub > Manage > Scorecards (/scorecards, /scorecards/{id}), My Performance > Team Call Scores (/scorecards/team), rep drilldown /scorecards/rep/{userId}. Rep screen: My Performance > My Call Scores (/scorecards/my).
- Backend tests: `python -m pytest tests/test_scorecards_api.py` (24 cases, needs the seed).

## Recorded conversation demo (preview only, `cd /app/backend && python tests/seed_recorded_convo_demo.py` idempotent, `--wipe` removes)
- Seeds one `kind: conversation` voice note (12s tone WAV in object storage + realistic Sarah Tester transcript) for Activation Tester on contact 6aa413008f0d53e3f2261853 and runs Recording Highlights (creates ~4 `auto_kind: recording_highlight` tasks). Visible on the contact's Calls tab as "Recorded conversation · 12s".
- Backend tests: `python -m pytest tests/test_recording_highlights.py` (3 cases, live LLM).

## Scripts & Practice (June 2026)
- Screens: `/scripts` (everyone), `/scripts/{id}`, `/scripts/practice?script=`, `/scripts/result?session=`, `/scripts/editor?id=`, `/scripts/assign` (managers), `/scripts/training` (super_admin only). Rep = activation-tester, manager = qa-manager, super admin = forest.
- Practice chooser: `practice-mode-phone` (rings the rep's cell via Twilio; on preview the activation-tester's 500-555 number comes back "Your phone was busy" after ~30s, which exercises the `practice-failed` / `practice-retry` state) or `practice-mode-text` (type turns via `practice-text-input` + `practice-text-send`). LLM turns take 3-15s, grading 15-40s.
- Backend smoke: `cd /app/backend && python tests/scripts_practice_smoke.py` (creates + cancels an assignment, leaves one completed roleplay_session) and `python tests/relay_roleplay_sim.py` (simulates the Twilio ConversationRelay websocket end to end). Extra pytest: `tests/test_scripts_practice_extra.py`.

## Mystery Shops (June 2026, preview seed via `cd /app/backend && python tests/mystery_shop_e2e.py`)
- Entry: log in as forest@imosapp.com -> Tools tab -> Internal Operations -> Mystery Shops (`/admin/mystery-shops`, super_admin only).
- Seeded client "QA Jeep 9495" id 6aa5f046efccef2627dced30 (people Sam Seller 500-555-0006 / Val Advisor 500-555-0007, one completed 64% shop). Report token 5c631d7ba7204fb79ba6b7cdcc661cbe -> `/shop-report/<token>`; paid proposal token 75d44d8e031149e3bc5d265356ad4352 -> `/proposal/<token>`. UI links show app.imonsocial.com; swap the host for the preview host when testing.
- Only ever add people with 500-555-XXXX numbers ("Shop now" places a real Twilio call). Stripe is TEST mode; signing a proposal creates a test invoice. Use @invalid.imonsocial.test contact emails.
- Kickoff form (no login): `/shop-kickoff/da134fbca3bd4a40968353f833259fce` for QA Jeep 9495 (also via People tab "Copy setup link"). Sent proposal for the send-sheet: id 6aa5fcdbfbc94be4c788d8f3 (token 54f844a247b84ec5843beb550163fedb), To = qa-gm@invalid.imonsocial.test.
