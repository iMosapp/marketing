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

## Mystery Shops (June 2026, preview seed via `cd /app/backend && python tests/mystery_shop_e2e.py`, `--wipe` removes every "QA Jeep *" client)
- Entry: log in as forest@imosapp.com -> Tools tab -> Internal Operations -> Mystery Shops (`/admin/mystery-shops`, super_admin only).
- Automotive QA client "QA Jeep 979a" id 6aa6d7dfb4c41decb2734ec4 (people Sam Seller 500-555-0006 / Val Advisor 500-555-0007, one completed 64% shop). Report token 51c51185fdbf45e3b15efbadf3e3b203 -> `/shop-report/<token>`; kickoff `/shop-kickoff/eb0f264f74534f42a3d9657d5719dffc`. UI links show app.imonsocial.com; swap the host for the preview host when testing. Each e2e run creates a fresh "QA Jeep xxxx" (ids/tokens change).
- INDUSTRY-AGNOSTIC QA client "QA Realty Group" (industry real_estate) id 6aa6d92be1e1863f484f6907: people Bea Buyeragent 500-555-0061 (re_buyer) / Sal Lister 500-555-0062 (re_seller), plan 4 buyer + 2 seller, 4 scheduled buyer shops, 1 draft proposal (list via GET /api/shop-clients/{id}/proposals). Library has 2 seeded real_estate/re_buyer starters; re_seller is intentionally EMPTY to exercise the "Have Jessi write two ... starters" prompt (`library-seed-re_seller`, LLM ~60s).
- Only ever add people with 500-555-XXXX numbers ("Shop now" places a real Twilio call). Stripe is TEST mode; signing a proposal creates a test invoice. Use @invalid.imonsocial.test contact emails.
- Shop caller number: `/admin/mystery-shops` card `shop-number-card`. NEVER tap Buy / call `POST /api/shop-clients/number/buy` in tests (buys a real Twilio number). Picking an owned number (PUT) and reset (DELETE) are safe; leave the setting on the platform number when done.
- Industry packs: `GET /api/shop-clients/industries` (admin) lists the 7 packs + per-department challenge counts. Automotive = sales, service, parts, rental, collision ("Body Shop"); the global library carries 18 hand-written starters (3 each for parts/rental/collision). `POST /api/shop-clients/challenges/seed {industry, department?}` makes Jessi write 2 starters per empty department (LLM, ~30-60s per department).
- Text shops (Sep 2026): `person-text-shop-{id}` on the People tab or Quick shop `demo-channel-text`. The opener goes out as a REAL Twilio SMS from the shop number, so only 500-555 numbers. Simulate the rep's reply with `POST /api/webhooks/twilio/incoming` form data `From=<their 500 number>&To=<shop number>&Body=...&MessageSid=SMx&NumMedia=0`; the shopper answers 20-75 s later (LLM). `POST /api/shop-clients/calls/{id}/end` grades it now (LLM, ~30 s). Backend tests: `cd /app/backend && set -a && . ./.env && set +a && python -m pytest tests/test_text_shops.py` (3 fast + `-k api` real e2e ~90 s; both clean up after themselves).
- Leaderboard demo data on QA Jeep 979a: `cd /app/backend && python tests/seed_leaderboard_demo.py` (idempotent; `--wipe` removes): Bud Ward / Jessi Lane / Tom Reyes (sales), Pat Counter (parts), Dana Estimator (collision) with this-month + last-month completed shops so Report tab / public page show ranked boards with Top score / Most improved / Most shops badges.

## Dutch demo client (Phase B/C, June 2026, preview only, `cd /app/backend && python tests/seed_dutch_demo.py` re-seeds idempotently, `--wipe` removes)
- "QA Autobedrijf Jansen" (locale nl-NL, Utrecht, 4 Dutch people, 3 completed Dutch-graded shops, 1 draft proposal). The seed prints fresh tokens: `/shop-report/<token>`, `/shop-kickoff/<token>`, `/proposal/<token>`, `/shop-score/<token>`; all four public pages render in Dutch.
- Its `from_number` is preset to the platform number so submitting the kickoff form NEVER buys a Twilio number. NEVER tap `client-number-buy` on any client or POST `/api/shop-clients/{id}/number/buy-local` (real Twilio purchase, ~$3/mo). GET `/number` and DELETE `/number` (release) are safe.
- Challenge Library `/admin/mystery-shops/library`: `library-lang-nl` chip -> `localize-card` (`localize-start` runs Jessi for ~2-4 min over the 18 automotive starters, creates `language: nl` drafts with `review.status: needs_review`; `localize-approve-all`). Detail sheet `challenge-approve` / `challenge-unapprove`. Review API: GET `/api/shop-clients/challenges/review?language=nl`, PUT `/challenges/{id}/review {status}`.
- CSV import: `/admin/mystery-shops` card `shop-import` -> `import-sheet` (`import-csv` textarea, `import-preview` dry run, `import-run` creates). Template: GET `/api/shop-clients/import/template`. Use names starting with "QA Import" and @invalid.imonsocial.test emails; delete created clients afterwards (DELETE `/api/shop-clients/{id}`).
- Backend tests: `cd /app/backend && set -a && . ./.env && set +a && python -m pytest tests/test_dutch_pack.py` (3 cases, no LLM, no purchases).

## UK demo client (Phase D, June 2026, preview only)
- "QA Arnold Motors Leeds" id 6aa8b13f2c2d5fb494b1532e (locale en-GB, £450/mo, no people). Public pages in British English: `/proposal/08fb4ad374b049a387e6ada59227a80e` (do NOT sign: Stripe test invoice), `/shop-kickoff/c03ad1fa10234f6dae86a845b13f76d1`, `/shop-report/ef5113d7b7f8404e89aa54f39054c60c`.
- Its `from_number` is EMPTY on purpose: submitting the kickoff form triggers the GB auto-buy, which fails safely before any Twilio call while no GB bundle is on file (error stored in `number_error`). NEVER save a REAL bundle SID in preview; the fake `BU000…`/`AD000…` pair used by tests must be cleared afterwards (`PUT /api/shop-clients/number/bundles {"country":"GB"}`). NEVER tap `client-number-buy`.
- Regulatory bundles API: `GET/PUT /api/shop-clients/number/bundles` (admin). UI: People tab -> `client-number-card` -> `number-bundle-row` (`number-bundle-edit`, `-sid`, `-address`, `-save`).
- Library: `library-lang-en-GB` chip -> `localize-card` "British English (UK & Ireland)"; `localize-start` is a real ~3 min LLM job (18 drafts, `language: en-GB`, needs_review). Not run yet in preview.
- Backend tests: `cd /app/backend && set -a && . ./.env && set +a && python -m pytest tests/test_uk_pack.py tests/test_uk_ireland_review.py` (no LLM, no purchases; the review test saves + clears a fake GB bundle).

## Locales (Phase A, June 2026)
- `GET /api/shop-clients/locales` lists en-US, en-GB, en-IE, nl-NL, nl-BE. Set a client's locale in the client edit sheet (`client-locale-nl-NL`) or `PUT /api/shop-clients/{id} {"locale":"nl-NL"}`; a store's via the admin store page picker or `PUT /api/admin/stores/{id} {"locale":"nl-NL"}` (tests reset the QA store back to en-US).
- Voice overrides (super admin): `PUT /api/shop-clients/locales/nl-NL/voices {"voices":{"female":"ElevenLabs:<id>","say":"Polly.Laura-Neural"}}`; empty `{}` clears.
- Dutch client for manual checks: create one with locale nl-NL; scheduled shops then carry `locale` and `relay_twiml` speaks Dutch (ElevenLabs) with `language="nl-NL"`.


- Team Call Scores (`/scorecards/team`, qa-manager) has the `digest-card` (toggle per manager, "Send me last week now" = real Resend email to the manager's address; qa-manager's @invalid address bounces harmlessly). `stores.coaching_digest.last_sent_week` on the QA store gets stamped by `tests/test_coaching_ack_digest.py`, so the hourly scheduler will not re-send for that week in preview.
- Rep "Got it": activation-tester -> `/scorecards/my` -> open a call -> `eval-ack-btn`. The scorecard demo seed (`seed_scorecard_demo.py`) creates unread coaching; re-run it to reset acknowledgements (evaluations are re-inserted).

## Courses & Certification (June 2026)
- Admin: forest -> Hub/Tools > Manage > "Courses & Certification" (`/admin/courses`); managers (qa-manager) see the list + can enroll their store's reps but cannot create/edit/retire. Rep: activation-tester -> `/scripts` "MY COURSES" strip -> `/courses/{id}`.
- Preview leftover course "QA Inbound Sales" (no enrollments). Do NOT press `enrollment-call-now` / `person-shop-now` (real Twilio calls).
- Fast certification without the LLM: `cd /app/backend && python -c` calling `services.courses.record_result(db, {"_id": ObjectId(), "enrollment_id": eid, "script_id": challenge_id}, 90)` per challenge (see `tests/test_courses_certification.py`). Public page `/certificate/{token}` (no login).

## Voice Interview + Test Lab (Sep 2026)
- Test Lab: forest -> My Profile > "Test Lab" row (or Hub > Internal Operations > Test Lab) = `/admin/test-lab`, super_admin only. `voice_interview` is in `lab` status by default (reps do not see the InterviewCard; `GET /api/interview/status` .available false). Flip via `lab-release-voice_interview` or `PUT /api/lab/features/voice_interview {"status":"live"}`; leave it `lab` after tests.
- NEVER press "Call me" / "Redo" as forest (real phone 801-634-9122). activation-tester (500-555-0006) is safe: the call fails "Your phone was busy" in ~30-45 s and exercises the failed state. `POST /api/interview/start {"dry_run": true}` is super-admin only.
- Full no-phone simulation (websocket + LLM + persona build + dry run + lab flags): `cd /app/backend && python tests/interview_sim.py` (~2.5 min; `--keep` leaves the tester's completed sessions for UI checks at `/interview/review`). Pytests from testing agents: `tests/test_interview_api.py`, `tests/test_lab_api.py`.
- Voice ID: `PICOVOICE_ACCESS_KEY` is SET in preview (Sep 17 2026) -> `/api/interview/status` voice.configured true, status `none` until a rep is enrolled. The preview server is aarch64 (Neoverse), so `services/voice_id.py::_lib_kwargs()` loads pveagle's generic `cortex-a76-aarch64` library; `voice_id.available()` caches whether Eagle loads (bad key / unsupported CPU -> status `not_configured` with the reason, `lab/features` voice_interview.needs shows it). Real round trip: `cd /app/backend && set -a && . ./.env && set +a && python tests/voice_id_check.py` (TTS two voices, enroll, score: same 1.0 vs other 0.0).

## Industry VA + facts (Sep 2026)
- Test Lab feature `industry_va` is `lab` by default: only forest (super_admin) runs the new 4-layer prompt and sees `va-facts-card` on `/settings/virtual-assistant` and inside `/admin/test-lab`. qa-manager / activation-tester see nothing until `PUT /api/lab/features/industry_va {"status":"live"}` (flip back to `lab` after tests).
- forest has NO store, so his industry is his own pick (`users.industry`, currently `automotive`; `PUT /api/va/industry`) and he cannot add store facts (400). qa-manager (store_manager on 69a0b7095fddcede09591668) adds store facts (`scope: "store"`); activation-tester gets 403 on store facts, 200 on `mine`.
- Preview data to keep: store fact "We take walk-ins weekdays until 6 pm" on the QA store, forest fact "I am off Sundays, I answer texts Monday morning". Delete anything else you add.
- Backend tests: `cd /app/backend && set -a && . ./.env && set +a && python -m pytest tests/test_va_facts_api.py tests/test_va_routing.py` (routing tests call `queue_ai_reply` in-process with throwaway contacts; LLM ~5 s per case, cleaned up).

## Power Dialer + GoHighLevel (June 2026, Test Lab feature `power_dialer`, lab by default: only forest sees it; `PUT /api/lab/features/power_dialer {"status":"live"}` releases it)
- Screens: `/dialer` (campaigns; managers get + for a new campaign), `/dialer/campaign/{id}` (Leads / Call log / Settings, Add leads sheet: CSV / GoHighLevel / My contacts), `/dialer/session/{id}` (live rep screen, polls every 2 s), `/dialer/dnc` (Do Not Call list + FTC registry upload), `/admin/ghl` (GoHighLevel connection). Hub: Tools > Leads section > Power Dialer / GoHighLevel tiles; Test Lab card `dialer-lab-card`.
- **NEVER tap "Start dialing" / POST /api/dialer/sessions as forest**: it places a REAL Twilio call to his real cell (801-634-9122) and then dials the campaign's leads. Only the in-process pytest (fake Twilio) exercises sessions. Lead lists in preview must use 500-555-XXXX numbers only.
- Demo data: `cd /app/backend && set -a && . ./.env && set +a && python tests/seed_dialer_demo.py` (idempotent, `--wipe` removes) -> campaign "QA Demo: Utah dealers" with 6 leads (done / queued / callback / dnc), an ENDED session with 5 attempts in the Call log, one press-9 DNC entry (+17865550106). The script prints the /dialer/campaign/{id} and /dialer/session/{id} URLs.
- Backend tests: `cd /app/backend && set -a && . ./.env && set +a && python -m pytest tests/test_power_dialer.py -q` (5 cases: compliance rules, instant-mode session incl. abandon + press 9, press1 + AMD voicemail, API + DNC + GHL guards; fake Twilio, cleans up).
- GHL: no real sub-account in preview. `PUT /api/ghl/connection` with a bad token returns 400 "GoHighLevel rejected that...". Webhook URL shape `/api/ghl/webhook/{connection_id}?key=...` (401 on a bad key).

## Lead Shops (covert internet-lead mystery shops, Sep 2026)
- UI: forest -> `/admin/mystery-shops/{client}?tab=leads` (tab `shop-tab-leads`, hidden for the Quick shops demo client). Main screen `/admin/mystery-shops` has the `shopper-pool-card`.
- **`LEAD_SHOP_BUY_NUMBERS=false` is set in preview backend/.env**: creating a lead shop only works while a FREE fake number sits in `phone_number_pool` (purpose `lead_shop`). `cd /app/backend && set -a && . ./.env && set +a && python tests/seed_lead_shop_demo.py` (idempotent, `--wipe`) seeds +15005550311 (free) + +15005550312 (in use by a LIVE seeded shop), sets QA Jeep 979a's CRM lead email to crm-intake@invalid.imonsocial.test and adds one COMPLETED seeded lead shop with a score. NEVER call `POST /api/lead-shops/numbers/buy` with the flag on `true` (real Twilio purchase; one stray number was bought and released on Sep 17 2026 when the API test ran before the guard existed).
- Creating a lead shop with method `adf` sends a REAL email via Resend to the client's `lead_email` (use @invalid.imonsocial.test); method `manual` sends nothing until `POST /{id}/delivered`. The seeded free number is consumed by the first shop you create; delete that shop (`lead-delete`, only when not live) or close it to return the number (14-day cooldown -> set `cooldown_until` null in the DB to reuse).
- Simulate the store: call/text webhooks with To=<shopper number> (`POST /api/webhooks/twilio/incoming` form From=+18015550140&To=+15005550311&Body=...), email via `services.lead_shops.inbound_email`. Backend tests: `python -m pytest tests/test_lead_shops.py` (3, fakes for Resend/Twilio/LLM; the API case seeds its own pool row +15005550301).

## Channel-aware reports (Sep 2026)
- `python tests/seed_channel_mix.py` (idempotent, `--wipe`) gives QA Jeep 979a one completed TEXT and one completed EMAIL shop this month; prints the two `/shop-score/<token>` links, the `/shop-report/<token>` link and the Shops tab URL. `python -m pytest tests/test_report_channels.py` seeds + wipes on its own.
- Lead-shop child sessions (`lead_shop_id` set) are excluded from the store report / Shops list / weekly digest by design.

## Interview photo request (Sep 2026)
- After `interview.finalize` Jessi texts the rep from `session.from_number` asking for a card photo (`photo_requests` collection, 48 h). Reply with an image to that number -> `routers/profile._save_profile_photo` -> `users.photo_url`. `GET /api/interview/status` has `photo_request {status open|done|expired, had_photo, sms_ok}`; the InterviewCard shows `interview-photo-hint` / `interview-photo-done` on a completed session.
- Tests: `python -m pytest tests/test_photo_request.py` (2: in-process flow + real webhook e2e using `/api/public/shop-contact/logo.png` as the MMS; restores activation-tester's photo fields afterwards). In preview the outbound text to 500-555 numbers fails harmlessly (`sms.ok false`).

## Live Jessi / GPT-Live-1 (Sep 2026)
- `OPENAI_API_KEY` is NOT set in preview backend/.env: `POST /api/live-voice/session` returns 503 with the reason by design, the Home `talk-to-jessi-btn` (forest only while the Test Lab flag `jessi_live_voice` is `lab`) reads "Needs OPENAI_API_KEY on the server" and opens `/admin/voice-lab`, where Audition is disabled. Never add a real key to preview without the user.
- Voice Lab `/admin/voice-lab` (forest): change voice/levels, Save persists to `settings.jessi_voice`; restore defaults afterwards (Gleam, 4/4/3/4, cap 15, idle 25, default greeting). Recent conversations read `live_sessions`.
- Backend tests: `cd /app/backend && set -a && . ./.env && set +a && python -m pytest tests/test_live_voice.py` (6: config/prompt, fake-OpenAI session create, real LLM brain flow on Activation Tester's Sarah/Mike/Dana Tester contacts incl. a text to +15005550042 and a reminder task that is cleaned up, `test_open_targets_for_the_screen` with a faked brain, events + admin API). `tests/test_live_voice_api_iter332.py` (testing agent) covers the API guards.
- **Fake WebRTC recipe for UI tests (no key needed)**: `page.add_init_script` replacing `window.RTCPeerConnection` with a stub (createDataChannel -> EventTarget with readyState 'open' + send() recording JSON into `window.__dcSent`; setRemoteDescription -> dispatch `session.started` on the channel after 200 ms; `window.__emit(ev)` dispatches any event) + `navigator.mediaDevices.getUserMedia` stub, then `page.route` `/api/live-voice/config` (configured true), `/api/live-voice/session` ({live_id:'fake1', sdp:'x', greeting, idle_close_s, cap_left_s, voice}), `/api/live-voice/fake1/events`, `/api/live-voice/fake1/delegate` (any `{tool, content, open:{kind,id,name,first}}`), then `page.goto` the login URL AGAIN (init scripts need a fresh navigation). Emit `session.input_transcript.delta` + `session.delegation.created {delegation:{id, target:'client'}}` to drive "Jessi opens things" (pill `live-jessi-pill`, route change). Sarah Tester contact 6aa413008f0d53e3f2261853.
- **Native (iOS) live voice** cannot be tested in this container: `hooks/liveRtc.native.ts` only runs in an EAS build. Sanity check for bundling: `cd /app/frontend && CI=1 npx expo export --platform ios --no-bytecode --output-dir /tmp/ios-export` (hermesc does not run here, hence --no-bytecode) and `npx expo config --type prebuild` for the config plugin.
- **Live shop calls**: `python -m pytest tests/test_live_shops.py` (5, fake Twilio + fake GPT-Live, no network). Test Lab flag `live_shop_calls` now defaults to `live` (kill switch = flip to lab); per-client chips `client-live-calls-lab|on|off` on English clients (QA Jeep 979a is left on "Follow Test Lab" = null). `GET /api/shop-clients/live-status` (admin) tells whether the GPT-Live shopper is on and why not; `/admin/mystery-shops` card `shop-live-card`. Relay calls carry `live_transport: relay` + `live_skip_reason` (call detail `shop-call-relay-badge`). A real GPT-Live shop call needs OPENAI_API_KEY + a live English shop (500-555 people fail before the stream, so this can only be heard in production).
- **Shopper audition (Sep 2026)**: `/admin/mystery-shops` card `shop-audition-card` -> `audition-sheet`; needs OPENAI_API_KEY (503 otherwise) and WebRTC, so in preview drive it with the fake recipe above + route mocks (`POST /api/live-voice/session` -> include `greet_instruction`, `shopper: {persona_name}`, `idle_close_s: 45`; `/delegate` -> `{tool: 'hang_up', kind: 'thinking', end: true}` makes the browser send `session.close`). `GET /api/shop-clients/audition/options` lists the voices.
- **Duplicates (Sep 2026)**: `python -m pytest tests/test_duplicates_and_audition.py` (5, seeds + wipes contacts tagged "QA Dup" for activation-tester: Tod/Todd Berry, Sarah Same x2, Emil/E. Twin, Mike Solo/Snow). To look at `/contacts/duplicates` as activation-tester, insert a few contacts tagged "QA Dup" (see `_seed` in that test) and delete them afterwards. Voice: "do I have duplicates?" / "merge Tod Berry" / "yes".
