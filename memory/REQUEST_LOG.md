# Request Log

Your exact words, in order, and where each one stands. Newest at the bottom. Updated by the agent at the end of every task.
Legend: DONE = built + verified in preview · DEPLOY = needs backend deploy and/or `eas update` to reach production · USER = waiting on something only you can do.

---
### 60 · Oct 9 — DONE (1A-min built + fully UI-tested) · NOT DEPLOYED (you asked to review first)
> Founder Command Center ... Phase 1A-min ... I choose Option A — complete UI testing and fix any issues before we proceed. Please run the testing agent against all Phase 1A-min interactive workflows ... Fix any issues discovered within the approved Phase 1A-min scope. Do not add new features or begin Phase 1B. After testing, provide a concise pass/fail report ... Do not deploy to production or publish an EAS update yet.

BUILT (previous session): `/admin/command-center` (Focus · Strategy · Roadmap · Ideas), owner-only via the Owner Tools gate, 5 `cc_*` collections, atomic three-slot rule, JSON + Markdown export. TESTED (this session): backend 4/4 + 9/9 API spot checks (testing agent) + every interactive UI flow driven in the browser (activate x3, 4th -> 409 -> replace/park, pause/complete/reactivate, statement draft + approve with reason, text + Whisper voice capture, roadmap status/add/remove, Waiting On / Wins / Next Best Action, exports, non-owner 403 + hidden menu, 1400 px + 390 px, dark + light).
FIXED (3, all in scope): parking a 4th priority left it behind as a stray "proposed" row (new owner-only `DELETE /priorities/{id}`, proposed only); a non-owner deep link showed an endless spinner (now bounces to the hub); roadmap phases overlapped on a 390 px screen. Preview data reset to the pristine seed (3 proposed priorities, 0 ideas, 0 notes). Ship when you say so: Save to GitHub -> Deploy -> eas update.

---

### 59 · Oct 9 — PHASE 1 + 2 DONE / DEPLOY + EAS UPDATE · Phases 3-8 IN PROGRESS · USER (DNS for mvpline.com)
> Unified Mystery Shop Customer Journey Engine ... Do not rebuild existing features. Audit the current codebase first and reuse all existing mystery shop, Twilio, Resend, AI assistant, scoring, reporting, and campaign functionality wherever practical. (Phases 1-8) ... test domain: mvpline.com ... i need help after with this

PHASE 1 (audit) in `memory/JOURNEY_ENGINE_PLAN.md`: Lead Shops already cover ~60%, so the engine EXTENDS Lead Shops. Two production findings need your go-ahead: the only Resend webhook points at a dead host/path, and imosapp.com MX goes to Google, so inbound email never reaches the app today.
PHASE 2 (built, tested iteration_373): Journeys tab on every mystery-shop client -> campaign of 1-10 virtual customers (name, cell from the pool, email on the test domain, timeline, personality, channel prefs, questions, objections, AI instructions, hard no-commit rule), edit before launch, reply modes (email/text observe | approve | auto, voice voicemail | live), window up to 30 days, arm with a signed authorization, emergency stop, 30-day auto-close.
USER: paste the 6 DNS records for mvpline.com (table in the plan file) so Resend can verify the domain; then I switch INBOUND_EMAIL_DOMAIN / LEAD_SENDER_DOMAIN to it.



### 58 · Oct 8 — DONE / DEPLOY + EAS UPDATE (push leak: owner got Kira's Morning Brief)
> i continue to get notifications as if i'm kira.. this is not ok at all!!!!

ROOT CAUSE (code, confirmed): `POST /push/subscribe-native/{user_id}` upserted on (user_id, token), so one phone could be bound to many people. The app registers the phone's push token on every launch for whoever is signed in, INCLUDING while a super-admin is in "view as" (impersonation) mode, so the owner's phone got bound to Kira the moment he viewed as Kira, and Kira's 7 AM Morning Brief then went to his phone. Nothing in the digest itself crosses users; the device table did.
FIX: (1) one device = one person: registering a token unbinds it from every other user; same for web push endpoints. (2) impersonate_* sessions never bind and actively remove a stale binding to the viewed user (backend guard, so even the OLD app build is safe after deploy). (3) sign-out now calls `DELETE /push/unsubscribe-native/{user_id}` with the phone's token. (4) startup self-heal `dedupe_push_devices()` keeps only the newest owner per device in prod. App: `_layout.tsx` skips registration while impersonating; `authStore.logout` unbinds. Tests: `tests/test_push_device_binding.py` 4/4.
OWNER ACTION: after deploy, open the app once signed in as yourself so your phone re-binds to you (it happens automatically on launch).

---

### 57 · Oct 8 — DONE / DEPLOY + EAS UPDATE (full-screen photos on the desk + trade-link text in the inbox thread)
> As a manager I want to be able to click on photos submitted and have them expand full screen so I can see them better
> I text Bridget the link to submit his trade but it doesn't show in the inbox text thread that I did

Built: `components/appraisal/MediaViewer.tsx`, a full-screen viewer (swipe or arrows between items, pinch-zoom on the phone, counter, caption with role + who sent it + when, video plays inline, tap or X to close). Wired on the Value step grid, the Inspect step grid, and both desk cards (FROM <REP>, FROM THE CUSTOMER photo strip). Fixed: texting the trade link now sends from the rep's own number (when they have one) and logs the bubble in the rep's inbox thread with that customer (`intake._thread_log`, same conversation key the Twilio webhook uses, so the reply lands beside it). Tests: test_trade_link_and_tags sms case asserts the bubble; testing_agent iteration_369 green on all surfaces.

---

### 56 · Oct 8 — DONE / EAS UPDATE ONLY (home quick-actions order)
> lets move appraise trade above sold

Swapped the two entries in the home FAB list (`app/(tabs)/home.tsx`): Appraise trade now sits directly above SOLD! (SOLD! stays closest to the +). Frontend only.

---

### 55 · Oct 7 — DONE / DEPLOY + EAS UPDATE (voice notes on appraisals)
> I want to be able to record voice notes about the car also and if customer can great if not no big deal then transcribe those and add to description

Built: "Record a note about this car" mic button on the Inspect and Value steps (tap, talk, tap; Jessi types it into the appraisal notes as "[Rep voice note · time] ..."; clip kept for playback with a VOICE NOTES list + delete that takes the words back out). Customer trade-link page got "Or just tell us about it" under the notes box (browser recording, same path, "[Customer voice note · time] ..."). Desk FROM THE SALESPERSON card shows the full notes + every clip with play. Whisper runs with a vehicle-condition prompt and drops silence so quiet clips do not invent words. Tests: test_appraisal_voice_notes 4 (real speech) + 21 regression + testing_agent iteration_368 green.

---

### 54 · Oct 7 — DONE (formatting + auto trade tags + customer trade link; owner said 'use your best judgement')
> look at formatting on some of the boxes and clean it up.  Also I didn't see that vinaudit did anything? and I want to be able to group or tag these for campaign follow ups just not sure best way to do this yet.. also how do I send a link to a customer that is not at store to have them upload info?
> (screen recording: production desk detail for a 2021 Jeep Gladiator Mojave, live MarketCheck $29,469 / 36 comps; truncated "$29,4…" tiles, "ASKING RANGE $29,59…", "Not prov…" reference row)

Fixed: three-number tiles and snapshot tiles shrink-to-fit on native (adjustsFontSizeToFit), subs wrap to 2-3 lines, ASK RANGE shows low on the value line and "to high · basis" beneath, reference rows put the note under the label, shorter labels (APPROVED, ASK RANGE, DAYS LISTED). VinAudit: by design it only runs in Provider Lab or on an appraisal's Market step after the rule "Let admins compare" is on, and needs VINAUDIT_API_KEY in Deploy > Secrets. Owner: 'use your best judgement' → built auto tags (trade-appraised on submit; outcome tag + gap bucket replacing earlier trade tags; rule default ON + gap switch) and the CUSTOMER TRADE LINK (rep texts/copies a 7-day public page at /api/public/trade/{token}; customer sends VIN, mileage, ZIP, photos, 6 answers, notes, number in mind; media lands as customer_supplied; VIN sets the vehicle, mileage stays reported until the rep confirms; FROM THE CUSTOMER card on the desk). Tests: test_trade_link_and_tags 4 + testing_agent iteration_367 (10 API + 3 screens) green.

---

### 53 · Oct 7 — BUILT, awaiting keys + approval (live matrix not run)

> MVP5 is approved.
> DO NOT build any additional Trade Appraisal features.
> We are now moving into production valuation-provider activation and validation.
> I now have API accounts/credentials for: MarketCheck, VinAudit Market Values API. The credentials will be installed as secure environment/secrets. Do not place API keys in source code, GitHub, logs, screenshots, documentation, PRD files, test fixtures, frontend code, or API responses.
> FIRST — AUDIT ONLY. Before changing the valuation engine, inspect the existing MVP3–MVP5 provider architecture and tell me exactly how MarketCheck is currently implemented and where VinAudit should plug into the existing MarketDataProvider abstraction. Do not create a parallel valuation architecture.
> The goal is: I'M ON SOCIAL → Vehicle Identity → Market Data Providers → MarketCheck → VinAudit → normalized market snapshot → existing appraisal engine → Suggested ACV → Manager Approval. The existing appraisal engine remains authoritative for calculating Suggested ACV. External providers supply market/reference data only.
> MARKETCHECK: Connect the real MarketCheck API using the existing MarketCheck provider. Verify the current MarketCheck API documentation and endpoints against the implementation before making live requests. Report: endpoint used, inputs sent, response fields received, retail/market value fields, wholesale fields (if actually supplied), comparable/listing data, mileage handling, ZIP/geographic handling, confidence/statistics, rate limits, errors, API usage/cost considerations. Do not assume a field means wholesale, trade-in, retail, or ACV unless the provider documentation supports that interpretation.
> VINAUDIT: Add VinAuditProvider inside the existing provider abstraction. Use the VinAudit Market Values API. Verify the current VinAudit API documentation before implementation. Normalize its response into the existing market-data model wherever possible. Do NOT modify the appraisal engine merely because VinAudit uses different terminology. Preserve provider-specific raw responses separately if the existing architecture already supports that.
> CRITICAL RULE: Do NOT average MarketCheck and VinAudit together. Example: MarketCheck $34,850, VinAudit $32,400 → two independent provider observations. Do not create "Combined Market Value = $33,625" unless we explicitly design such a model later.
> PROVIDER COMPARISON MODE: Create an INTERNAL/ADMIN provider-comparison capability for validating providers before choosing our production strategy. For the same vehicle show, per provider (MarketCheck, VinAudit): estimated market/retail value, wholesale/trade value (only if genuinely provided), comparable median, comparable average, price range, comparable count, mileage, ZIP/location, confidence, provider timestamp, live status. Then VALUE DIFFERENCE: dollar difference, percentage difference. Do not label either provider "correct."
> TEST MATRIX: Build a validation harness to run approximately 10–20 real vehicles through both providers. Capture VIN, year, make, model, trim, mileage, ZIP, MarketCheck value(s), VinAudit value(s), provider difference, comparable count, confidence/data quality, response time, provider errors, API calls consumed. Do not automatically run large batches; deliberate testing so we don't waste API calls.
> PRODUCTION BASIS: Do NOT change the dealership's production ACV basis yet. MarketCheck can remain the currently configured primary provider while we test VinAudit. VinAudit initially operates as SECONDARY / COMPARISON PROVIDER, not an automatic ACV basis. After real-world testing we will decide: A. MarketCheck remains primary, B. VinAudit becomes primary, C. one supplies valuation and the other supplies comparables, D. both remain available and each dealership chooses.
> DEVELOPMENT DATA: Preserve the existing safety system. Production must NEVER allow mocked/development market data to silently become the basis of a customer-facing Suggested ACV. APPRAISAL_ALLOW_DEV_MARKET must NOT be enabled in production. Live provider responses must clearly record: provider, live = true, timestamp, request/lookup identifier where available, normalized values.
> FAILURE BEHAVIOR: If MarketCheck fails, do not automatically substitute VinAudit as the ACV basis unless the dealership rules explicitly allow that provider as a fallback. If VinAudit fails, MarketCheck should continue functioning normally. If both fail, use legitimate configured manual/book-value fallback or require manager valuation. Never invent a value.
> API USAGE PROTECTION: Reuse existing snapshots/cache where appropriate. Do not call both APIs every time someone opens an appraisal. Provider comparison should be deliberate. Normal appraisal workflow should call only the provider(s) required by dealership configuration. Reappraisal should request fresh data according to the existing freshness rules. Track provider usage so we can eventually understand API cost per appraisal.
> SECURITY: Keys backend only. Never expose credentials to Expo/web frontend. Never return keys in API payloads. Never write keys to Mongo. Never log keys. Never commit keys.
> TESTING: MarketCheck live success, VinAudit live success, MarketCheck normalization, VinAudit normalization, different values preserved independently, no averaging, MarketCheck failure, VinAudit failure, both fail, rate-limit/provider error, invalid VIN, missing mileage, missing ZIP, snapshot reuse, forced refresh, development data rejected in production, provider comparison tenant isolation, API credentials never returned to frontend, existing MVP1–MVP5 regression suite.
> STOP AFTER VALIDATION. Do not change the production valuation strategy after testing. Give me a report containing: existing provider architecture, changes made, MarketCheck endpoint + actual normalized response, VinAudit endpoint + actual normalized response, side-by-side comparison, provider differences, API usage/cost behavior, cache behavior, failure behavior, security verification, test results, recommendation for which provider should be primary (but DO NOT implement that recommendation yet). Then STOP for approval.

Audit delivered Oct 7 (architecture + docs verified against docs.marketcheck.com and data.vinaudit.com). Owner picked: VinAudit retail + tradein (2 calls) in comparisons, MarketCheck stays Base + search, go. Built the same day: VinAuditProvider, rules.market (primary/fallback/comparison), admin comparison (ad-hoc Provider Lab + per-appraisal), call ledger + cost summary, matrix harness, 19 + 20 tests, testing_agent iteration_366. Live matrix waits for the keys to be installed as backend env secrets; production strategy untouched.

---

### 52 · Oct 7 — DONE (MVP5, approved in #53)

> MVP4 APPROVED. START MVP5 — VEHICLE RELATIONSHIP INTELLIGENCE + FOLLOW-UP + REPORTING. Vehicles as first-class records (Contact → Vehicles: current ownership, last appraisal, chronological history). Easy REAPPRAISE that reuses the vehicle and the previous numbers and asks only for fresh mileage / condition / market; a new appraisal, never a duplicate vehicle. Concise normalized context to Jessi (date, mileage, market, suggested ACV, dealer offered, customer wanted, outcome), no raw provider payloads. Expose `trade_appraisal.*` triggers and `{{trade_*}}` merge fields to the EXISTING campaign engine. Do NOT send automated texts with trade values by default: org setting `allow_trade_values_in_automated_messages` (default OFF). Tasks ("Follow up on $2k gap") + concise timeline events. Correction: accepted ≠ completed trade; set `trade_intent_status = accepted`, keep `ownership_status = owns`, migrate existing test records safely. Manager Trade Appraisal dashboard (submitted, approved, accepted, average ACV / manager adjustment / gap / response time), salesperson "My Trade Pipeline", appraisal search (VIN, name, status…). Strict tenant isolation (rep / store / org) across reports, search, history. (paraphrased from the handoff spec)

Built: `relationship.py` (vehicle cards, history, value changes, ownership via manual confirm only, reappraisal opportunities, startup migration `appraisal_accepted_not_traded`), `followup.py` (8 triggers into the existing campaign engine, `{{trade_*}}` merge fields with money gate, rule tasks, daily reappraisal tasks), `reporting.py` (summary, follow-up view, pipeline, search, all behind `core.scope`), Jessi `core.for_context`; UI: contact VEHICLES section, `/vehicle/{id}`, pipeline on `/appraisals`, `/appraisal/reports`, "A trade" trigger + merge-field picker in campaign new/edit. Verified: 9 + 19 backend tests, 69 MVP1-4 regression, testing_agent iteration_365 (tenant isolation incl. other-org admin sees nothing).

---

### 51 · Oct 7 — DONE (MVP4 verification report, approved in #52)
> MVP4 sounds good, but DO NOT proceed to MVP5 yet. Before I approve MVP4, give me the same detailed technical completion report … 20 numbered points (files, DB changes, rule model, engine example $34,850 / $35,100 / MMR $29,100 / Black Book $28,750 / GOOD / wants $32,000, double-adjustment protection, basis fallback, rule versioning proof, status machine, manager desk + screenshots, override audit, request-info flow, notifications, permissions, present before outcome, outcomes, relationship intelligence, campaign events, analytics data, test breakdown, real market data status) … If the environment is production and MarketCheck is not configured, the system should require a legitimate manual valuation basis rather than using MockMarketProvider … STOP.

Delivered the report. Defect found while verifying point 20 and fixed: development (mock) market data can no longer start a Suggested ACV unless `APPRAISAL_ALLOW_DEV_MARKET=1` (preview only). Small additions: `customer_expected_value_before_outcome`, richer Jessi context line, 5 more tests (37 engine + 7 e2e), mobile screenshots at `/qa/mvp4/*.jpeg` on the preview URL. MVP5 still blocked on approval.

---

### 50 · Oct 7 — DONE (MVP4, awaiting review before MVP5)
> MVP3 APPROVED … START MVP4 — DEALERSHIP APPRAISAL ENGINE + MANAGER APPROVAL. Three distinct values stored and never blurred: MARKET VALUE, SUGGESTED ACV (dealership rules), MANAGER APPROVED VALUE. Configurable dealership rules (target front-end gross, recon allowance, mileage/age adjustments, risk reserve, market/condition rules, ACV range, base value selection). Pure calculation engine (`services/appraisals/engine.py`, no DB, unit-tested, clear breakdown). Manager review workflow: submit, desk-manager review screen, approve / change value / request more info / decline. Strict status machine draft → capturing → analyzing → ready → submitted → needs_info → resubmitted → approved → changed → declined → presented → closed. Customer outcome (ACCEPTED, WANTS MORE…) + relationship intelligence on close. Event triggers (`trade_appraisal.approved` …) for campaigns/notifications. RBAC `manage.appraisal_approvals` / `manage.appraisal_rules`. DO NOT START MVP5.

Built: `permissions.py` new `manage` section (both keys ON for store_manager/org_admin/super_admin, OFF for reps, grantable per rep in Team Members → Permissions "Desk Powers"); `services/appraisals/rules.py` (org default + store override, versioned with history, `reach()`), `engine.py` (pure; basis order → target gross → recon by condition → mileage → age → reserve → rounding → range → review flags; every line labelled MARKET DATA / BOOK VALUE / I'M ON SOCIAL CALCULATION / MANUAL; customer expectation reported, never calculated), `workflow.py` (status machine, immutable `appraisal_calculations` snapshots with the rules used, `appraisal_decisions`, `appraisal_events` `trade_appraisal.*`, notifications with deep links, contact `trade_appraisal` + vehicle `last_appraisal` relationship record, optional outcome → contact tag hook). Routes: `GET/PUT /appraisals/rules`, `DELETE /rules/store/{id}`, `GET /desk`, `GET /desk/{id}`, `GET /{id}/calculate`, `POST /{id}/submit|decide|present|outcome`; every input route 409s once submitted. UI: Value step (`SubmitPanel` + `ValueBreakdown` three-number strip), `StatusPanel` (waiting / approved / changed / declined / presented / closed, Present + Outcome sheet), Manager Desk `/appraisal/desk` + `/appraisal/desk/{id}` (decision bar: Approve $X · Change value · Ask for more · Decline), `/admin/appraisal-rules` editor with double-count warnings, Tools tiles + `/appraisals` desk card. Tests: `tests/test_appraisal_engine.py` 34 pure + `tests/test_appraisals_mvp4.py` 5 e2e + MVP1-3 regression 48 + testing_agent iteration_364 (9/9 web flows). Report delivered; MVP5 blocked on approval.

---

### 49 · Oct 7 — DONE (MVP3, awaiting review before MVP4)
> MVP2 APPROVED … START MVP3 — MARKET DATA + COMPARABLES + VALUATION FOUNDATION. Normalized MarketDataProvider with MarketCheckProvider and a fallback MockMarketProvider; do not invent endpoints, verify MarketCheck via docs; badge mock data "DEVELOPMENT DATA — NOT LIVE"; vehicle_market_snapshots (estimated retail/wholesale, listing count, days on market) never overwritten on refresh; vehicle_comparables with I'm On Social's own match quality (EXACT/STRONG/CLOSE/LOOSE MATCH); MARKET ANALYSIS screen with snapshot, confidence and best comparables; manual external book values (Black Book, MMR, etc.); tenant isolation, rate limiting, failure handling, caching. DO NOT build the final ACV yet (MVP4). When MVP3 is complete, STOP: files created, example normalized snapshot, full test results, wait for approval before MVP4.

Built: `services/appraisals/market_providers.py` (MarketCheck live provider verified against developers.marketcheck.com + docs, Mock provider), `services/appraisals/market.py` (snapshots, comparables + match quality, confidence, book values), 5 new routes + providers status route, Market step UI (MarketStep / MarketSnapshotCard / ComparablesList / BookValuesEditor), review row. 16 backend tests + testing_agent iteration_362 (backend 8 e2e + full web flows at 1920 and 390) all green. No key in preview → mock badged everywhere. Report delivered; MVP4 blocked on approval.

---


### 48 · Oct 7 — DONE (MVP2, awaiting review before MVP3)
> B — MVP1 APPROVED with the following additions before proceeding into MVP2 … START MVP2 … AI VEHICLE INSPECTION … When MVP2 is complete, STOP. Do not begin MarketCheck/MVP3.

Built the AI Vehicle Inspection: record/import walkaround video + take/import photos (mixed, with provenance), ffmpeg frame extraction + quality/dedupe, Jessi vision findings with evidence frames + timestamps, coverage, confirm/dismiss/edit/add, condition report with explained grade + override, org video-retention setting. 32 backend tests green, testing_agent iteration_361 frontend pass. Report delivered; MVP3 blocked on approval.

---

### 47 · Oct 7 — DONE (report only)
> MVP1 Completion Report requested ("When MVP1 is complete, STOP and give me: files created…")

Delivered the MVP1 report; on the way in fixed requirements.txt (zxing-cpp missing), a flaky test assertion, appraisal feed labels, and the 403 redirect on web.

---

### 1 · Oct 3 — DONE
> Jesus where are these old logos coming from??? Current logo is this one [screenshot of imonsocial.com header]

Canonical logo is `logo.png` (white tile). Old `imos-logo.png` / `imos-wordmark.png` deleted from `public/`, `build/`, `build-preview/`. `/mybaby` and `/card` fixed.

### 2 · Oct 3 — DONE
> For fuck sakes! Put the white tile around behind it like it's always been! Dont touch anything else besides this one presentation

Reverted the deck to the white-tile `logo.png`.

### 3 · Oct 3 — DONE
> Get ride of the scroll or use arrows thing that's gay

Removed the "Scroll or use arrow keys" hint from the cover slide.

### 4 · Oct 3 — DONE
> the start conversation should pull up a web form to submit a lead to me

Modal lead form (Name*, Company, Email*, Phone, Message) posting to `POST /api/demo-requests` with `source: platform_overview_cta`.

### 5 · Oct 3 — DONE
> slide 6 needs to be changed from any talk of raising money or needing capital.. the is just the story of my platform and it should focus more on just a go to market strategy which is where I am at now. I want to be able to show this to anyone to give the history of what I have built over the last 8 months

Slide 6 rewritten as go-to-market (5 pillars). All capital language removed.

### 6 · Oct 3 — DONE
> lets take 8 months out and say something like 30 years of experience has shaped what is missing in the market.. a tool designed by a high tech redneck to help the life blood of every company.. the salesman
>
> or something like that.. make it better

Headline: "Thirty years on the sales floor. One tool built for the people on it." + high-tech redneck / salesperson copy.

### 7 · Oct 3 — USER
> ok so this project should be connected to two specific repos in github and it's not wired right.. how do i make sure the right repos are associated to the right projects? don't change anything just report back what I need to do

Report delivered (from support): push the monorepo to `imonsocial-clone`; point Vercel's Root Directory at `marketing/`; one job pushes to one repo per Save.

### 8 · Oct 3 — USER
> so it got blocked becasue of this: [GitHub push-protection error: "Stripe Test API Secret Key … backend/.env.example:123 / :125"]

It was a dummy `sk_test_xxx…` placeholder, not a real key. Placeholders changed to `<your-stripe-secret-key>` so it can't trip again. You still need to click GitHub's unblock link once (old commit still contains it), then push.

### 9 · Oct 3 — DONE
> I watched the full recording. This is substantially better than I expected. It looks like an investor microsite/deck rather than a normal marketing page, which is exactly right for /mybaby. [full reviewer feedback: reorder Problem → insight → built → does → scale → moat → recreate → founder → distribution → ask; compress metrics; "Six systems… One relationship layer connecting all of them"; move the Relationship Intelligence Engine earlier; "Every interaction makes the next interaction smarter"; rename Replacement Cost → Estimated equivalent build cost; soften competitor claim; founder slide "Most sales systems are built around managing the pipeline…"; add an evidence slide BUILT → DEPLOYED → USED; add a final NOW WE SCALE IT page with "We aren't raising capital to find out whether this can be built. We're raising capital to determine how fast it can be distributed."]
>
> this is the new /mybaby marketing page

Your choices: investor ask only on `/mybaby?investor=1`; live numbers from a public stats endpoint; no revenue. Deck restructured to that order.

### 10 · Oct 3 — DONE
> We don't have any numbers populating slide seven or whatever, so that API obviously isn't working right. Let's either dummy up numbers or get rid of it altogether. And let's not reference iMOS ever. It's I'm On Social

Evidence slide removed (endpoint `GET /api/public/platform-stats` kept for later). Every "IMOS" → "i'M On Social".

### 11 · Oct 3 — DONE
> why is the chat widget not on this page? how do we install it?

One script tag: `<script src="https://app.imonsocial.com/api/w/XkTvZEUb.js" async></script>`. Added to the deck. Still missing on: date-triggers, calendar-systems, training, demo, reviews, help, landing, outreach.

### 12 · Oct 3 — DONE
> also lets get rid of the page numbers save as pdf etc across the top

Top bar removed. Progress line, side dots and arrow keys stay; Cmd/Ctrl+P still prints all slides.

### 13 · Oct 3 — DONE / DEPLOY
> When we are hunting for tags or intel and it pulls up the screen sometimes it's a bit glitchy and if I have more than what is on the screen it doesn't tell me details. I'd like this to work a bit better than it does

Root cause: the screen re-ran the whole AI search after Jessi already had the list. Now her exact list renders instantly; "keep going / who else / read the rest / read them all" walks the full list; "pull up the fourth one" resolves correctly; result cap 40 → 150.

### 14 · Oct 4 — DONE / DEPLOY
> As a store manager I want to be able to get a daily digest from Jessi.. so think this: I'm on my way to work and I ask Jessi who has my team been working with that I should have them follow up on today.. it goes through the whole team and gives me people each team member can work on.. so I'm in the loop on every salesperson

Team Today: Jessi tools `team_today` / `nudge_rep`, screen with per-rep follow-ups + Nudge buttons, `GET /api/team-today`, `POST /api/team-today/nudge`.

### 15 · Oct 4 — DONE / DEPLOY
> OK, so with this last update, I pushed to have a manager ask about their team and what they have going on. I'm very concerned about the data. It's telling me that Kira has context to follow up with that are actually my contacts and one of the messages was a birthday message, but the person's birthday is in April. How do we get to the bottom of what's going on here?

Root cause: birthday/anniversary/sold-date automations picked contacts with the manager-wide data filter (whole store/org — whole DB for super admins). Fixed in 5 code paths. Added owner flags, "Where did they come from?" screen, and Stop-all for a rep's automations on other reps' customers. Existing leaked enrollments in production must be stopped from that screen.

### 16 · Oct 5 — DONE / DEPLOY
> So let's make this All Tools button Instead of having all the tiles, let's clean it up and make it look like the dropdown under my profile. I love how that looks. It's super clean on a computer screen, which is what I gave you a screenshot. Let's go through one last time an organization on that All Tools. When I click that, have it be a nice, easy, clean screen with everything organized and bucketed correctly on where it should live. [screenshots of the profile dropdown]
>
> i'm not sure I want this option to be a way to view them still but I want to be able to switch between views primarily because it looks so much better on a browser.
>
> add the internet leads box under leads
>
> use your best justjment for organization. you know the things I talk to you about the most. Think of this as my full admin dashboard for my internal team. I will upload an example of how I have been managing anoterh admin dashboard
>
> these [screenshots of the Calldrip admin dashboard: left sidebar with collapsible groups, "Press / to search"]

List/Tiles toggle (remembered per user), 12 groups, sidebar + detail layout on computer, single column on phone, Internet Leads under Leads.

### 17 · Oct 5 — DONE / DEPLOY
> also ONLY send the text out to me with the people stuck in setup for jessi onboarding.. other users are getting it and they shouldn't be

Recipients limited to super admins (`digest_roles` config). Preview DB: 22 → 1.

### 18 · Oct 5 — DONE / DEPLOY
> stuck in setup needs to ONLY go to me not other super admins.. how do I toggle other super admins off?

Jessi Onboarding → gear → Morning digest → "Who gets the morning text": on/off switch per super admin.

### 19 · Oct 5 — answered
> ok now show me where to find this setting to turn everyone else off!

Home → avatar → All tools → Account Management → Onboarding Hub (or Admin Dashboard → Jessi Onboarding) → gear → Morning digest. Web: `app.imonsocial.com/admin/onboarding-jessi`.

### 20 · Oct 5 — DONE
> how would I go about finding the last 5 things I've asked you to do? I want to keep a log of these for myself so I can compair it to what has been done already and what I need to do?

This file.

### 21 · Oct 5 — DONE
> does it have my exact full prompt I gave you?
>
> yes

Switched the log to your verbatim words (this version). Earlier sessions can't be recovered word-for-word; they were summarized before this fork.

### 22 · Oct 5 — DONE / DEPLOY
> and I want this log to push into my super admin panel also but only visible to me not all super admins. tell me how I should structure the super admin settings since there are things I only want to see but not let other super admins see? Do I only user super admin setting for me? I don't know the best way to do this
>
> is_owner flag · That list is right · An "Owner" settings screen where you tick, per tool, whether other super admins can see it

Owner layer: `is_owner` flag on your account (set from `OWNER_EMAIL`), **Request Log** screen in the admin panel (All tools → Internal Operations, and your profile dropdown), **Owner Settings** screen with a switch per internal tool for what other super admins can see (Request Log, Billing & Revenue, Revenue Forecast, Partner Agreements, White Label Partners, Discount Codes and the digest switches are hidden by default) plus an Owners list to promote someone you trust. Production needs `OWNER_EMAIL` set in the backend env.

### 23 · Oct 5 — DONE / DEPLOY + EAS UPDATE
> Jessi is stuck in widgets reading website
> *(screenshot: Widgets → I'm On Social → "Reading https://imonsocial.com… A whole site takes a minute or two." spinner never ends)*

Cause: a site read left as "running" forever when the server restarted mid-read (a deploy does that); nothing ever closed it and the Read button stayed locked. Fix: startup sweep marks interrupted reads failed, the status poll fails any read silent for 4 minutes, a hard timeout on the whole read (150 s pages + 90 s draft), live "Read 23 pages so far…" progress, Read again button on any failure. Verified in preview: imonsocial.com reads 60 pages in 12 s.

### 24 · Oct 5 — STANDING RULE
> Give me the prompt for terminal EVERY time I new to run it

Every reply that touches `/app/frontend` ends with the `eas update` terminal command; backend-only changes say "Deploy only".

### 46 · Oct 7 — ASSESSMENT DELIVERED (no code) — awaiting architecture approval
> BUILD: AI TRADE-IN APPRAISAL SYSTEM — We are adding a new Trade Appraisal module to I'm On Social. The goal is to let a salesperson quickly scan a VIN, capture mileage, perform a guided photo/video walkaround, use AI to identify visible vehicle condition issues, retrieve current market/comparable data, calculate a suggested trade/ACV range, submit the appraisal to a manager, and permanently attach the vehicle/appraisal information to the customer's relationship intelligence. [24 phases + build rules + MVP1-5 order; full verbatim spec is long — key rules: reuse existing auth/RBAC/media/notifications/AI/contacts/scoping; provider abstraction for VIN (NHTSA first), market data (MarketCheck first, Black Book / J.D. Power / AccuTrade later) and condition AI; never trap the salesperson; tenant isolation tests; AI must not price repairs; distinguish MARKET DATA vs I'M ON SOCIAL CALCULATION vs MANAGER-APPROVED VALUE; STOP AND TEST after each MVP.] FINAL REQUIREMENT BEFORE CODING: give me a read-only implementation assessment … DO NOT CODE YET.

Assessment written to /app/memory/APPRAISAL_PLAN.md and posted in chat (reuse table, data model, routes, screens, VIN/video/NHTSA/MarketCheck/provider/approval/intel mechanics, security, file estimate, concerns, MVP order).

### 45 · Oct 7 — DONE / EAS UPDATE (+ Deploy for web)
> Just a couple of cosmetic things here. I love the new files under history, but let's move it to the far right so tasks would be to the left of it. And then the gold bar just on camera, photos and files PDF is a little bit confusing. I would think we would want a button that says upload. And then I would feel like if I click on photos or PDFs, it would sort them by what's what. I don't know. It's really cool. I just don't love the way it's laid out. Let's think through that

History chips now end with Files (All · Texts · Calls · Memos · Tasks · Files · N). Files section rebuilt: a quiet summary line ("5 files · 2 photos · 2 PDFs · 1 card") with ONE gold "+ Add" button that opens an "Add to files" sheet (Take a photo on phones, Choose photos, File / PDF, then JESSI SCANS: Business card, VIN / odometer, Trade-in); below it outline filter chips with counts (All · Photos · PDFs · Cards · Vehicles · Locked, zero-count chips hidden) that filter the grid. Nothing looks pressed by default any more.

### 44 · Oct 7 — DONE / DEPLOY + EAS UPDATE
> Strong match is causing names to wrap let's change placement so it doesn't do this *(screenshot: "1. Tami Ice Queeen" wrapping beside the badge)*

Who mentioned… results: the "Strong match" pill left the name row; the name now has the full width (one line, ellipsised), and a small gold STRONG MATCH tag sits on the second line in front of the phone number.

### 43 · Oct 7 — DONE / DEPLOY + EAS UPDATE
> How would I do a manual search for something like "who do I know looking at Harley's" same as voice search but typing it?
> Yes do 1

Answer: Contacts → sparkle icon → "Who mentioned…" (typed twin of the voice hunt, same engine). Built #1: a search box on Home right under the Talk to Jessi card ("Type it: who's looking at Harleys, who asked about a Tahoe", Enter or the arrow runs the hunt), plus a "Who Mentioned" tile in Tools (daily group, also in the rep-first hub). Verified on web: typing "who is looking at a Kubota" returned Sarah Tester via her filed fleet-quote PDF.

### 42 · Oct 6 — DONE / EAS UPDATE
> When I talk to Jessi with AirPods in it doesn't play through my headphones?  It played though my phone speaker

Root cause: `hooks/liveRtc.native.ts` forced the loudspeaker (`InCallManager.setForceSpeakerphoneOn(true)`) for every live talk, which overrides AirPods/CarPlay/wired. Now the route is decided from the audio session's available inputs (expo-av `getAvailableInputs`, types BluetoothHFP/LE/A2DP, Headphones, HeadsetMic, CarAudio, USBAudio): something worn or a car = system route (AirPods), nothing = loudspeaker; re-checked every 3 s so putting AirPods in mid-talk follows along. Phones only (web unchanged).

### 41 · Oct 6 — DONE / DEPLOY + EAS UPDATE
> This never actually talks to me just loads entail it ends and the buttons are up in the apple bar so it's not laid out right anymore *(screenshot: "Connecting to Jessi · gleam", header under the status bar)*

Layout: LiveJessiSheet now pads the header by the safe-area top inset and the End button by the bottom inset. Connecting-forever: production RCA (deployer) showed sessions created fine (HTTP 200 + SDP, OpenAI key valid, a working session at 23:03Z with byte-identical code) but the phone never completed the WebRTC link (0 s, connection_lost); OpenAI status green; i.e. the phone-to-OpenAI media path (that Wi-Fi) blocked UDP. Client now reports the ICE/data-channel state back as a session `last_error` when it times out or fails before `session.started`, the sheet explains "could not open on this network, switch to cellular", and Voice Lab session detail shows "Last error from the phone". User asked to test on cellular.

### 40 · Oct 6 — DONE / DEPLOY + EAS UPDATE
> theres no way i used the full jessi gpt live today.. so that's why i didn't even think to check that.. how do i audit that to see how i hit my limit?

Audit lives in Jessi Voice Lab → RECENT CONVERSATIONS: new "Your minutes today: M:SS across N talks" row (tap = only your talks since your local midnight); every row now says how it started (Live · Home, Live · Sarah, Walk my day, Team today, Voice Lab audition, Shopper audition) and how it ended (ended / closed after a quiet spell / connection dropped / never closed, cut off after 3 h / hit the daily cap); tap a row for the transcript and what the brain did. Likely explanation: the old cap counted the UTC day, which starts at 6 pm Mountain, so yesterday evening's talks were charged to "today"; production breakdown requested from the deployer.

### 39 · Oct 6 — DONE / DEPLOY + EAS UPDATE
> go but gpt live jessi quit working on the home screen??? very bad!
> it responds the old way that is not the live gpt live voice
> getting this not the live interactive gpt live version *(screenshot: old Jessi screen, "Jessi is speaking")*

Not broken: the production check showed the 30-minute daily live cap (Voice Lab → Minutes per rep per day) was used up today (16 sessions, 30m14s), so `/live-voice/session` returned 429 and the Home card fell back to the old Jessi screen with only a small grey line saying why. Fixes: the cap window now resets at YOUR local midnight (was UTC midnight = 6 pm Mountain); the Home card now turns orange, says "Live Jessi is resting · all 30 live minutes for today are used · back at midnight" and (for you) taps straight into the Voice Lab; the Voice Lab cap picker gained 120 and 240 minutes. To get her back right now: Voice Lab → Minutes per rep per day → 120 (or 240), Save.

### 38 · Oct 6 — DONE / DEPLOY + EAS UPDATE
> go *(Contact Files UI: Files chip in the contact's History tab, defaults accepted)*
> how do I change my daily limits up and is there a better way to respond as jessi outside of gpt live?  the current version isn't even usable
> *(options: owner no cap = yes · Jessi Classic on the live brain = you decide · both = ok)*

Contact page → History → new **Files · N** chip: Photos / Files-PDF buttons (Camera too on phones), SCAN chips (Business card, VIN / odometer, Trade-in), grid of filed items (PDF badge, red lock for sensitive, "Texted" for customer MMS), detail sheet with Jessi's summary, "Show everything Jessi read", tick-box details → "Add N to the contact" (first/last name are never pre-ticked once the contact has a name and show `replaces "Sarah"`), type chips, Sensitive switch (30-day auto-destroy), Open full size, Delete. Tested end to end on web (iteration_359: PDF + business-card uploads, Jessi read in ~15 s, apply, type, sensitive, rename, delete, chip counts). Owner/super admins are now never capped on live Jessi (reps keep the Voice Lab cap). Jessi Classic (push-to-talk on the live brain as the fallback) is the next build.


### 37 · Oct 6 — DONE / DEPLOY + EAS UPDATE
> where can I go see my voice memos and assign them to contacts later on?  are they all in one place like voice memo on iphone or something?  can I label them to organize and find them easier?  apply tags to them? things like that?
> do all 4

Voice Memos (Tools → Daily → Voice Memos, or + → Voice memo) now works like the iPhone app: (1) Tags: every memo takes your existing contact tags (dashed "Add tag" chip → pick or create), and a tag row at the top filters the list. (2) Search: one box searches titles, Jessi's summaries, full transcripts, the names and companies Jessi heard, tags and the contact it was filed on. (3) "To file / Attached" switch: Attached lists every memo you have filed with who it went to ("Sarah Tester · filed as a voice memo · Oct 4"), tap → their card; tags still editable there. (4) Day folders: memos grouped under Today / Yesterday / Sat, Oct 3 with a pencil to name the day ("NADA show day 2"); the name sticks across both tabs. Tested: 13 backend tests + full web flows (iteration_358).

### 36 · Oct 6 — DONE / DEPLOY + EAS UPDATE
> where did all tools go?
> it was under everything else section i don't see on the webapp

Nothing was removed: "All tools" was the last row of the avatar menu, under EVERYTHING ELSE. On the web the menu is taller than the browser window for a super admin (30+ rows) and it hid its scrollbar, so that section sat about a thousand pixels below the fold with no hint it was there. Fix: "All tools" is now a pinned gold row right under your name at the top of the menu (always visible, every role), the web menu shows its scrollbar, and EVERYTHING ELSE keeps Help & Support and Terms & Privacy. Verified on web at 1400x800: row at the top, tap opens Tools.

### 35 · Oct 6 — DONE / DEPLOY + EAS UPDATE
> Memo To Contact Card: Let you create the new contact right from a memo, with the name and company Jessi heard already filled in
>
> Choices: chips on the memo card AND the "not in my contacts yet" rows in the Attach sheet · full New Contact screen, prefilled · ask "voice memo vs recorded conversation" after Save

Anyone Jessi hears who matches nobody in your book becomes an "Add Marcus Delgado · Rocky Mountain Kubota" chip on the memo card, and the Attach sheet lists them as "Add ... as a new contact" rows (plus "Someone else"). Tap → New Contact opens with first name, last name and Company already filled (gold "From your voice memo" banner, Company row only in this mode), cursor in Mobile. Save → "Marcus is saved. Now the memo." → voice memo / recorded conversation / skip → the memo attaches and you land on their card. If the duplicate check finds they already exist, tapping that match attaches the memo to the existing record instead. Also fixed: Jessi Match now reads the contact's Company (employer) field, so "Sarah from Tester Motors" ranks the right Sarah. Tested: backend API + full web flows (iteration_357).

### 34 · Oct 6 — DONE / DEPLOY + EAS UPDATE
> Memo Reminder: Give you a nudge the next morning for any memo still unattached so speakers don't slip through
> Jessi Match: Let Jessi suggest which contact a memo belongs to from names she hears in the recording
> Stop Leaked Automations: Make the "Where did they come from?" screen stop legacy campaign enrollments that leaked across stores

Memo Reminder: at 8 AM in the rep's own timezone, one in-app alert + push a day for memos older than 10 hours still not attached, tapping opens Voice Memos. Jessi Match: when a memo is saved Jessi lists the people it names and looks them up in your book; matches show as "Jessi thinks this is about" pills on the memo and as "Jessi's guess" at the top of the attach sheet, one tap pre-picks them; guesses refresh every time the list opens so a contact added later shows up. Stop Leaked Automations: the "Where did these come from?" screen now ends with a whole-team (every store for super admins) leak card, per rep, with "Stop the N cross-store" and "Stop all N" buttons. Tested: 7 backend tests + web flows.

---

### 33 · Oct 6 — DONE / DEPLOY + EAS UPDATE
> in the + menu I want generic voice memo's that I can later attach to a contact.  example I might want to record a presentation and then after meeting the speaker attach it to them.  make sense?

"Voice memo" in the + menu (Home and every tab) opens Voice Memos and starts recording (up to 45 min, screen stays awake). Jessi transcribes, titles and summarizes each one. The list holds everything not attached yet: play, rename, delete, "Attach to a contact" → search the whole book → file it as a voice memo or as a recorded conversation (summary, tasks, Jessi can cite it) → lands on that contact. Also a Voice Memos tile in More. Tested: 11 backend tests + full web flow incl. recording with a fake mic.

---

### 32 · Oct 6 — DONE / DEPLOY + EAS UPDATE
> ERROR REPORTS (100 total, filter: all) … *(pasted the production error report list)*

Triage: 45 of 100 were `GET/PATCH /users/{id}` 500 UnicodeDecodeError, every day since Sep 19, still firing Oct 5: the Voice ID enrollment stores a binary Eagle profile on the user doc and those two endpoints returned the raw doc (login and /auth/me were already fixed, these two were missed). Fixed by stripping the binary the same way. ~30 were Cloudflare 502/520/503 from pollers during deploy restarts (clusters match deploy times; expected, nothing in code). Web `S.Audio is not a constructor` on voice-note playback fixed (expo-av import shadowed the browser Audio). `'Pause AI' is not a function` (iOS, Sep 26) and SearchScreen `query` (Android reviewer, Sep 27) are from older bundles; current code is correct. 401 login errors are wrong passwords.

---

### 31 · Oct 5 — HELD
> Ok hold all this for future reference

Architecture plan parked in `/app/memory/ARCH_PLAN.md`. Do not start any phase until the user asks. Keep shipping features.

---

### 30 · Oct 5 — DONE (plan only, no code)
> plan it out please

Wrote `/app/memory/ARCH_PLAN.md`: six phases, each step with target files, effort and a pass/fail gate. Phase 1 safety rails (one auth module, scoping sweep, rate limits, prod config), Phase 2 durable background work (job_runs + re-queueable tasks), Phase 3 one brain (LLM/payments choke points, prompt module, then Portability Step 2 on approval), Phase 4 kill the twins, Phase 5 split the big files as touched, Phase 6 hygiene (CI, request ids, PRD split). Awaiting go on Phase 1.

---

### 29 · Oct 5 — DONE (report only, no code)
> is this app written and laid out in the best possible way currently?  do a quick assesment and let me know what we should change in architecture if anything.  just audit and report to me no coding

Architecture audit delivered in chat (see summary below). Headline: solid foundations (JWT middleware that verifies X-User-ID, startup indexes, Twilio signature guard, locked campaign queue), but five structural debts: giant files (thread screen 5.4k lines, 4 routers near 3k), 18 copies of role-check helpers, two generations of inboxes/widgets/VA living side by side, in-process scheduler + 85 fire-and-forget tasks that die on deploy, and the Emergent LLM wrapper bypassed in 42 files. Recommended order: shared auth helpers → durable background jobs → kill legacy twins → split the big screens → finish Portability Step 2.

---

### 28 · Oct 5 — DONE / DEPLOY ONLY
> This is still happening on mobile or it's jumping the conversation to the bottom when it tries to set an appointment I have to scroll up to read what was actually said with the widget
> *(screen recording on imonsocial.com: reply shows, booking form appears, list jumps to the bottom)*

Cause: the booking form redraws the thread a second time when its open times load (and again on polls and chip taps), and every redraw still forced the list to the bottom. Now only three things move the view: a new reply (anchored at its first line when it plus the form do not fit, bottom when short), the visitor's own message and the typing dots. Every other redraw keeps the view where it was. Verified on a phone-size screen: reply stays readable after the form and its times load and after a poll. Widget JS is backend-served: Deploy only.

---

### 27 · Oct 5 — DONE / DEPLOY + EAS UPDATE
> this new prd working log causes app to crash when i try to access it
> *(screenshot: Company Docs → "PRD Working Log (Full Build History)" v2026.10.05)*

Cause: that doc is the raw build log (over half a megabyte, 860 long lines) and the doc viewer mounted every line as its own text node at once, which the phone could not take. Fix: the markdown viewer now renders 150 blocks at a time with a "Keep reading · about N more lines" button, and the working log is stored newest-first (latest work at the top) with a note saying so. Verified on web: opens in 0.4 s, Keep reading pages through.

---

### 26 · Oct 5 — DONE / DEPLOY ONLY
> when a long response is in the chat widget it jumps to the bottom of what the response is instead of starting the message thread at the top of that message so currently i hvae to scroll back up to read the reply.  this needs fixed

`services/widget_js.py draw()`: a new Jessi/rep reply that is taller than the chat window now scrolls so its first line sits at the top; short replies still sit at the bottom like any chat. Verified in the live widget with a 600 px reply (top of message at 6 px) and a short one (at bottom). Widget JS is served by the backend (2 minute cache), so a Deploy is all it needs.

---

### 25 · Oct 5 — DONE / DEPLOY + EAS UPDATE
> I want an agent hub where I can build a library of ai agents this would be used in different areas in the tool.  I may want to deploy an agent based on a specific lead source for example.  I may use a different one for my chat widget etc
>
> Only super admins / you build them, stores just pick · (other choices skipped, defaults: widget + lead sources + shared inboxes; agents carry their own facts on top of store knowledge; text-only for now)

Agent Hub (Tools → Agent Hub, `/admin/agents`): library of agents with name, title, color/photo, tone, length, emoji, language, job, instructions, specialties, agent facts, always-collect, hand-to-a-person topics, never-say, advanced owner prompt, status. Six starters (Internet Sales, Service Scheduler, Website Concierge, After-Hours, Spanish, Demo Setter). "Try it" practice chat (text or website chat). Deploy tab with switches for every widget / lead source / shared inbox plus "where it is working". Pickers inside the widget Look tab (persona → "An Agent Hub agent"), the lead source workflow ("Agent for this source") and the inbox Jessi tab. The agent actually answers: website chat (name, face, brief, hand-off topics), lead-source text replies (replaces the rep's clone, rep still owns the lead), unclaimed inbox texts. The old VA Library (never wired to replies) was migrated into it; `/admin/va-library` redirects.

---

## Still open (from earlier sessions, paraphrased — originals not recoverable)
- Portability Step 2: swap `emergentintegrations` for the official OpenAI/Stripe SDKs — **waiting for your explicit go-ahead**.
- Portability Steps 3–4: object storage → S3, MongoDB → Atlas.
- CRM adapters: HubSpot two-way sync, then Salesforce / Zoho / Pipedrive.
- UI simplification Stages 4–5 (design-system pass, Contacts/Tasks polish).
- Dutch translation of the internal app UI.

## Ideas you liked but haven't green-lit
- Morning push to managers that opens straight into Jessi reading Team Today.
- "Text them all" / "Save as group" from a Jessi hunt result.
- Store-wide sweep that stops every rep's foreign automations in one tap.
- Chat widget on the 8 remaining marketing pages.
