# AI Trade-In Appraisal — read-only implementation assessment (Oct 7 2026)

Status: ASSESSMENT ONLY. No code written. Awaiting the owner's architecture approval. Build order fixed by the owner: MVP1 → MVP5, STOP AND TEST after each.

## 1. What we reuse (audited)
| Need | Existing piece | Where |
|---|---|---|
| Auth / identity | `require_user`, `bind_identity_header` middleware, `X-User-ID` + Bearer | routers/*, server.py:157 |
| Roles | `user`, `store_manager`, `org_admin`, `super_admin` + `feature_permissions` templates | services/permissions.py:4-249 |
| Store/org scoping | users `store_id/store_ids/organization_id`; contacts `user_id` + `store_id`; `team_scope.eligible_people`, `lead_flows.store_reps`, `user_store_id` | services/team_scope.py:45-80, services/lead_flows.py:102-132 |
| Contacts | existing create flow (`app/contact/new.tsx`, POST /contacts) | frontend app/contact/new.tsx |
| Activity feed | `log_activity(db, user_id, contact_id, event_type, description, metadata, ref)` idempotent on `ref`; `EVENT_META` | utils/activity_log.py:35, utils/event_types.py |
| Tasks | `db.tasks` docs (`user_id, contact_id, title, due_date, idempotency_key`) | routers/tasks.py:120-150 |
| Notifications | `create_notification` (in-app), `send_push_to_user` (Expo push), notifications center feed | routers/notifications.py:42, routers/push_notifications.py:173, routers/notifications_center.py |
| Media storage | Emergent Object Storage `put_object/get_object/upload_image` + `/api/images` proxy + LRU cache | utils/image_storage.py:119-282 |
| Upload transport | base64 chunked POST (500 KB pieces, 25 MB cap) → `/contact-files/{uid}/chunk` | hooks/useContactFileUpload.ts, routers/contact_files.py |
| Camera / library / docs | expo-image-picker (camera + video via system camera), expo-document-picker, expo-file-system | package.json |
| AI vision | `LlmChat(...).with_model(*VISION_MODEL)` + `ImageContent` (gpt-5.4) | services/contact_files.py:125, services/llm_models.py |
| AI text | `CUSTOMER_TEXT_MODEL` gpt-5.2 | services/llm_models.py |
| Relationship intel | `contact_ask.build_record` / `_system_prompt`; `contact_files.for_context` injection pattern | services/contact_ask.py:69,167,219 |
| Memory search | `SOURCES` + per-source hit builders | services/memory_search.py:18-215 |
| Background jobs | APScheduler registrations | backend/scheduler.py:1959-2506 |
| Audit pattern | `permission_audit_log`, twilio `audit_logs` (feature-specific) | routers/permission_templates.py:19, services/twilio_tenant.py:18 |
| Tools / Home entry | `more.tsx` MenuItem + `GROUP_FOR_TITLE/GROUP_PRIORITY` + `mk()` hub; `QuickActionsFab` | app/(tabs)/more.tsx, components/home/QuickActionsFab.tsx |
| Contact UI slots | Profile/History segmented control, `SnapshotCard`, `HistoryTab` chips, `FilesSection` 'vehicles' filter, `PurchaseHistorySection` | app/contact/[id].tsx:2715-2753, components/contact/* |
| Test harness | `tests/_http.py login/auth`, one `test_<feature>.py` per feature | backend/tests |
| Video frames | ffmpeg static binary already in the venv (imageio-ffmpeg 7.0.2) | python -c "import imageio_ffmpeg" |

Not present (and what that means): expo-camera / barcode scanner / vision-camera / video-thumbnails are NOT in the binary; no live viewfinder barcode scan without a new TestFlight build. No generic approval engine, no central merge-field renderer, no rate limiter, no global audit log.

## 2. Data model (Mongo collections, normalized, raw provider payloads retained)
- `vehicles`: _id, organization_id, store_id, owner_user_id, contact_id, vin, year, make, model, trim, series, body_class, engine, fuel, drivetrain, manufacturer, vehicle_type, decoded_by (provider), decode_raw_ref, current_mileage, mileage_as_of, ownership_status (owns / traded / sold / unknown), created_at, updated_at.
- `vehicle_appraisals`: _id, organization_id, store_id, user_id (salesperson), contact_id, vehicle_id, vin, status (draft → capturing → analyzing → ready → submitted → approved | changed | needs_info | declined → presented → closed), mileage_detected, mileage_confirmed, mileage_source, inspection_id, market_snapshot_id, condition_ai, condition_final, condition_overridden_by/at, suggested_acv, suggested_range {low, high}, calc_breakdown [{label, amount, source}], approved_value, approved_by/at, presented_at, outcome (accepted / wants_more / not_trading / thinking / other), customer_expected_value, outcome_note, notes, stock_number, created_at, updated_at.
- `vehicle_inspections`: _id, appraisal_id, store_id, media [{file_id, kind: photo|video|frame, angle, storage_path, thumb_path, frame_time_s}], coverage {driver_front: bool, ...13 angles}, guided_by ("video" | "photos"), ai_run {model, started_at, finished_at, frames_used, raw_ref}, status.
- `vehicle_condition_issues`: _id, appraisal_id, inspection_id, category (body/glass/wheels/interior), subtype (dent, curb_rash…), location, severity (minor/moderate/major), confidence (low/med/high), state (detected / possible / confirmed / dismissed / manual), evidence_media_id, box (optional), note, created_by (ai|user_id), updated_by, updated_at.
- `vehicle_market_snapshots`: _id, appraisal_id, store_id, provider, requested {vin, year, make, model, trim, mileage, zip, radius, dealer_type}, result {predicted_retail, price_range, avg_market_price, mileage_adjusted, listing_count, avg_dom}, raw_ref (object storage path of raw JSON), fetched_at, expires_at, quota_remaining.
- `vehicle_comparables`: _id, snapshot_id, listing_id, year, make, model, trim, mileage, price, distance_mi, dealer_name, city, state, dom, match_quality (exact / close / loose) + why, raw_ref.
- `appraisal_decisions`: _id, appraisal_id, action (approve / change_value / request_info / decline / reopen), system_acv, manager_value, delta, reason, manager_id, created_at.
- `appraisal_rules`: _id, organization_id, store_id (null = org default), target_front_gross, recon {default, excellent, good, fair, poor: "manager_review"}, mileage_adjustments [{over_miles_per_year, per_1000_mi}], age_adjustments [{min_age_years, amount}], inventory_risk_reserve, manager_buffer, zip_override, radius_mi, dealer_type, updated_by/at, history [].
- `appraisal_activity`: _id, appraisal_id, store_id, actor_id, action, from_status, to_status, detail, created_at (immutable audit trail; contact-facing copies via `log_activity`).
- `vin_decode_cache`: vin, provider, normalized, raw, fetched_at, ttl 180 d.

## 3. API routes (all under /api, `require_user`, store-scoped)
- `GET /appraisals` (status filter, q = customer | VIN | stock | vehicle | salesperson, date range) · `POST /appraisals` (contact_id | new contact payload) · `GET /appraisals/{id}` · `PATCH /appraisals/{id}` (notes, stock) · `DELETE` (draft only)
- `POST /appraisals/vin/decode` {vin} → normalized vehicle (NHTSA, cached) · `POST /appraisals/vin/from-image` {image} → {vin, method: barcode|ocr, confidence}
- `POST /appraisals/{id}/vehicle` (confirm VIN / manual vehicle) · `POST /appraisals/{id}/mileage` {detected?, confirmed} · `POST /appraisals/{id}/mileage/from-image`
- `POST /appraisals/{id}/media/chunk` (photos + video, reuses chunk protocol, cap 150 MB) · `POST /appraisals/{id}/inspect` (frames → AI, async job) · `GET /appraisals/{id}/inspection`
- `GET/POST/PATCH/DELETE /appraisals/{id}/issues[/{issue_id}]` (confirm / dismiss / edit / add)
- `POST /appraisals/{id}/condition` (override, reason) · `POST /appraisals/{id}/market` (fetch snapshot + comparables) · `POST /appraisals/{id}/calculate`
- `POST /appraisals/{id}/submit` · `POST /appraisals/{id}/decide` {action, value?, reason?} (manager) · `POST /appraisals/{id}/present` · `POST /appraisals/{id}/outcome` {outcome, expected_value?, note?}
- `GET /appraisals/queue` (manager: waiting) · `GET /appraisal-rules` · `PUT /appraisal-rules` (store_manager / org_admin) · `GET /appraisals/reports?store_id&from&to`
- `GET /contacts/{id}/vehicles` · `GET /vehicles/{id}` (+ appraisal timeline) · `PATCH /vehicles/{id}` (ownership_status, mileage)
- `GET /appraisals/providers` (which providers are live vs mock, quota remaining) — admin

## 4. Frontend screens / components
- `app/appraisals/index.tsx` Trade Appraisal home (START NEW APPRAISAL, Drafts / Waiting / Approved / Completed / Recent, search)
- `app/appraisals/new.tsx` → stepper `app/appraisal/[id].tsx` with steps as components: `components/appraisal/CustomerStep` (existing contact picker or "create" via current contact flow), `VinStep` (photo → server decode → VIN Detected / CONFIRM / SCAN AGAIN / type it), `VehicleCard` (decoded, editable), `MileageStep` (SCAN ODOMETER / ENTER MANUALLY → Detected 47,821 / CONFIRM / EDIT), `WalkaroundStep` (Tok/Jessi guidance text + START VIDEO INSPECTION + photo fallback + 13-angle coverage checklist), `ConditionReport` (Detected vs Possible, confirm/dismiss/edit/add, score + why, manager override), `MarketPanel` (MARKET DATA badge, range, listing count, DOM), `Comparables` (match quality), `AcvBreakdown` (MARKET DATA → I'M ON SOCIAL CALCULATION → MANAGER-APPROVED VALUE, each labelled), `SubmitSheet`, `ManagerReview` (approve / change value / request info / decline), `FinalAppraisal` + `PresentSheet`, `OutcomeSheet` (What did the customer say?)
- `components/contact/VehiclesSection.tsx` (contact Profile: cars owned, last appraisal, dealer offer, customer wanted, status) + `AppraisalTimeline.tsx`
- `app/admin/appraisal-rules.tsx` (per store, org default) · `app/appraisals/reports.tsx`
- `hooks/useAppraisalMedia.ts` (camera photo / video / library / upload with progress)
- Entry points: Tools tile "Trade Appraisal" (daily group), Home + (QuickActionsFab) "Appraise a trade", contact Vehicles section "Appraise", Files "Trade-in" scan hands off to the appraisal flow.

## 5. How the hard parts work
- VIN capture (OTA-shippable): system camera photo → server: `zxing-cpp` reads Code 39 / DataMatrix / QR barcodes from the image (pip wheel, no system libs); fallback OCR via the vision model with a strict "17 chars, no I/O/Q" prompt; then `utils/vin.py` validates length, alphabet and the position-9 check digit (North American WMIs 1-5; informational elsewhere). Always a confirm screen. Live viewfinder scanning (expo-camera `CameraView barcodeTypes: ['code39','datamatrix']`) needs a native build — planned for the next TestFlight, same backend.
- Odometer: photo → vision model returns digits + unit + confidence; stored as `mileage_detected`; user confirms/edits → `mileage_confirmed`. Never auto-accepted.
- Walkaround video: `ImagePicker.launchCameraAsync({ mediaTypes: ['videos'], videoMaxDuration: 90, quality medium })` (works in today's binary) → chunked upload → server `services/video_frames.py` uses the bundled ffmpeg to pull 1 fps, scores sharpness (Laplacian via PIL/numpy), dedupes near-identical frames, keeps ~12-18 → vision model in 2-3 batches with the angle checklist → per-frame findings merged into issues. Photos path: same analyzer per image. Web: upload only.
- Condition provider: `ConditionProvider` interface → `AiVisionConditionProvider` (existing LlmChat + VISION_MODEL, structured JSON: category, location, severity, confidence, evidence frame, detected vs possible). No dollar estimates from AI. Overall + category scores computed by rules from confirmed issues; reasons listed.
- NHTSA: `VINProvider` → `NHTSAProvider` GET `https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValuesExtended/{vin}?format=json` → normalize (year, make, model, trim/series, body class, engine cyl + displacement, fuel, drive type, manufacturer, vehicle type, plant) into `NormalizedVehicle`; 180-day cache in `vin_decode_cache`; ErrorCode handling; manual entry when unavailable.
- MarketCheck (verified today from developers.marketcheck.com/AGENTS.md + docs): base `https://api.marketcheck.com/v2`, auth is ALWAYS `?api_key=` query param; Free tier 500 calls/month, 5 rps, 100-mile radius; `GET /v2/predict/car/us/marketcheck_price?vin&dealer_type&zip` (predicted price; `/comparables` tier adds comps), `GET /v2/search/car/active?year&make&model&trim&zip&radius&miles_range&rows≤50&stats=price,miles,dom` for comps + stats; honor `Retry-After`, read `Quota-Remaining`; caching/display/retention rules are contractual (terms page) → we store the snapshot for the appraisal's own audit, show "Source: MarketCheck" attribution, and keep comps display to the fields they return. `MarketDataProvider` → `MarketCheckProvider` + `MockMarketProvider` (clearly badged DEV / MOCK when no key).
- Appraisal engine (`services/appraisal_engine.py`): pure function (market snapshot, rules, condition, mileage, age) → breakdown lines with `source` tags; range = ACV ± configurable spread; "Poor → manager review" flag; every line labelled MARKET DATA vs I'M ON SOCIAL CALCULATION vs MANAGER-APPROVED VALUE.
- Manager approval: status machine in `services/appraisal_workflow.py`; submit → `waiting_manager` + `create_notification` + push to store managers/org admins (via `eligible_people` with manager roles); decisions append `appraisal_decisions` + `appraisal_activity`; salesperson notified back. Request-info reopens capture steps.
- Relationship intelligence: on approve/present/outcome → `vehicles` upsert on the contact, `log_activity` events (`appraisal_submitted/approved/presented/outcome`), `contact_ask.build_record` gains a VEHICLES & APPRAISALS block, `memory_search` gains source `appraisal` ("who wanted more for their F-150"), `merge_fields.vehicle_vars(contact)` exposes `{{vehicle_year}} … {{customer_expected_value}}` to campaigns/AI drafts; outcome triggers optional task "90-Day Trade Follow-Up" with context.

## 6. Security / RBAC / scoping
- Every appraisal/vehicle/snapshot/rule carries `organization_id` + `store_id`; all queries filter by the caller's scope: rep = own `user_id`; store_manager = `eligible_people` of their store(s); org_admin = org; super_admin = all. Media served through `/api/images` proxy only after the appraisal scope check (new authorized route for appraisal media; no public paths). Provider keys server-side only (`MARKETCHECK_API_KEY`), never returned to clients. Per-user token bucket on provider-backed endpoints (market, inspect, decode-from-image). New permission keys: `my_tools.trade_appraisal`, `manage.appraisal_approvals`, `manage.appraisal_rules`, `reports.appraisals`. Tenant-isolation regression tests: two stores, two reps, one manager each → cross-store GET/PATCH/decide/media must 403/404.

## 7. Files (estimate)
Backend new (~17): routers/appraisals.py, routers/appraisal_rules.py, services/appraisals/{workflow,engine,rules,vehicles,reporting,inspection}.py, services/providers/{vin.py (base+NHTSA), market.py (base+MarketCheck+Mock), condition.py (base+AI vision)}, services/video_frames.py, utils/vin.py, tests/test_appraisals_mvp1.py … mvp5, tests/test_appraisal_isolation.py. Modified (~7): server.py (include), services/permissions.py, utils/event_types.py, services/contact_ask.py, services/memory_search.py, scheduler.py (snapshot TTL + stale-draft cleanup), requirements.txt (zxing-cpp, numpy if absent).
Frontend new (~20): app/appraisals/{index,new,reports}.tsx, app/appraisal/[id].tsx, app/admin/appraisal-rules.tsx, components/appraisal/* (≈13), components/contact/{VehiclesSection,AppraisalTimeline}.tsx, hooks/useAppraisalMedia.ts. Modified (~5): more.tsx, QuickActionsFab.tsx, app/contact/[id].tsx, FilesSection.tsx (Trade-in scan → appraisal), notifications deep links.

## 8. Concerns
1. Live barcode viewfinder needs a native build (expo-camera). MVP1 uses photo-based decode (barcode + OCR) and typing; OTA-shippable.
2. Video size: 60-90 s medium-quality clips are 20-60 MB; chunk cap must rise (150 MB) and the upload must survive backgrounding; show progress. Alternative path: 8-13 guided photos.
3. Object storage throughput for video + raw JSON; set TTL for raw provider payloads (90 d) and cap media per appraisal.
4. MarketCheck free tier = 500 calls/month ≈ 200 appraisals; Basic plan needed before rollout; display/retention terms are contractual (confirm before caching comps beyond the appraisal).
5. Vision cost ≈ 3 calls per appraisal (frames batched); use the existing model pins so the pending Portability Step 2 swap stays a one-file change behind `ConditionProvider`.
6. No generic approval engine exists → the appraisal status machine is new but small; keep it in one service.
7. Merge fields are rendered per feature today (no central renderer); `vehicle_vars` will be wired into the campaign touch renderer and AI draft context — a modification touching 2-3 render sites.
8. Overlap with Files "Trade-in" scan and `purchase_history` free text: Vehicles becomes canonical; Files link via `vehicle_id`; purchase_history stays for sold units.
9. Web has no camera; everything must also work by upload + manual entry.
10. RBAC is checked ad hoc per screen; appraisal permissions get one shared `useAppraisalPerms()` helper on the frontend and one `scope_filter(me)` on the backend to avoid drift.

## 9. MVP sequence (owner's order)
MVP1 nav + customer + VIN (photo decode + manual) + NHTSA + mileage + vehicle record → test · MVP2 photos/video + AI condition + confirmation + report → test · MVP3 MarketCheck provider + value + comps + abstraction/mock → test · MVP4 rules + ACV + manager approval + audit → test · MVP5 contact Vehicles + timeline + campaigns/tasks + reporting → test.
