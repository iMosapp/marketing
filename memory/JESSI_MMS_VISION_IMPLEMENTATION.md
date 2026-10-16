# Jessi Photo Intelligence (MMS Stage 2 + settings + intelligence + cost reporting): implementation report

**Status (Oct 16 2026): BUILT + TESTED IN PREVIEW. NOT DEPLOYED.** Waiting for the owner to try Save to GitHub and give the deploy GO.
Workspace build tag: `2026-10-16.photo-intel`. Production runs `2026-10-15.optout-calls` (commit `ab7875c7d`, an ancestor of the workspace HEAD).

## 1. What it does
A customer texts a photo. Jessi reads it once with GPT-5.4 (Emergent Universal Key) and the system then does four things:
1. Files the photo on the contact, as before.
2. Lets Jessi reply about what is visible, if **Jessi Photo Replies** is on for the rep's organization.
3. Proposes lasting details on the contact for the rep to confirm, if **Automatic Photo Intelligence** is on.
4. Alerts the rep on every photo and logs the estimated cost.

## 2. Settings and defaults
Settings live in the super-admin screen **More → Internal Operations → Photo Intelligence** (`/admin/photo-intelligence`, super admin only). The API is `GET/PUT /api/jessi-vision/settings`.

| Setting | Values | Default (no settings doc) | Effect |
|---|---|---|---|
| Jessi Photo Replies | Off / Test orgs only / All orgs | **Off** | Off = Stage 1 ("I can't open photos on my end"). On = Jessi uses the reading in auto-replies, AI Suggest and the thread history. |
| Automatic Photo Intelligence | Off / Test orgs only / All orgs | **Off** | On = vehicles/equipment, interests and projects seen in a photo become proposals in the existing "Jessi noticed" card. |
| Emergency Pause All | on/off | **off** | Stops every NEW image analysis: replies, intelligence AND contact Files reads, including rep uploads. Photos are still received and stored (Files status "unread", reason "paused"). Replies fall back to Stage 1. |
| Test organizations | list | empty | "Add my organization" adds the caller's org (`POST /api/jessi-vision/test-orgs/mine`); Remove = `DELETE /api/jessi-vision/test-orgs/{org}`. |

- Every change is recorded in `db.vision_settings_events`.
- Settings are per environment (`db.settings` key `jessi_mms_vision`). Production therefore starts with everything OFF after Deploy.
- No spending caps of any kind.

## 3. One reading, reused (no duplicate charges)
- Each image is read once at filing time (`services/contact_files.save_file`). Jessi's reply, the thread label, the rep alert and the intelligence proposals all reuse that one stored reading (`messages.media_read`, `contact_files.facts`).
- The same photo on the same contact reuses the earlier reading (sha256) and costs $0.
- Duplicate Twilio deliveries are dropped at the webhook by an atomic MessageSid check. Tested: 1 message, 1 draft, 1 usage row, 1 alert.
- At most 4 photos are read per text. The rest are filed unread (reason "limit").

## 4. Workflows that can still cost money
- **Contact Files reads texted photos and rep uploads** whenever Pause All is off, even with both settings Off. This is the behaviour already live in production today, so deploying adds no new cost while both stay Off. Only Pause All stops it. The usage report shows every one of these reads.
- **Trade appraisal photo reads** (`services/appraisals/inspection.py`, `readers.py`) are a separate workflow, not affected by these settings and not in this report.

## 5. Relationship intelligence
- The vision read also returns up to 3 lasting facts, each with a field (`vehicle_details`, `interests` or `personal_notes`) and a basis (visible or inferred). Sensitive documents and business cards return none, and prices, values, repair estimates, names, addresses and account numbers are excluded.
- `mms_vision.propose_facts` turns them into `contacts.detail_suggestions` entries:
  - source "a photo", mode "add"
  - the label says "(seen in a photo)" or "(Jessi's guess from a photo)"
  - `ref {message_id, file_id}` keeps the source
- Nothing is written to the contact until the rep taps **Add it**. Accepting APPENDS to the saved detail and never replaces it (`voice_intel.resolve_detail_suggestion` mode add).
- Declined, pending or already-saved values are not proposed again.
- **Business cards** never change the contact by themselves. The extracted fields wait in Files, and the existing review sheet shows the current value next to the new one before "Add N to the contact". Name fields are never pre-ticked.
- Org isolation: proposals live on the contact (same access rules); usage rows carry the organization.
- Rep UI fix: pending proposals now show even when a contact has no intel summary yet ("Jessi noticed N things to review" on the Snapshot). The card stays open after Add it.

## 6. Privacy and safety (all preserved, retested)
Still in place and retested:
- Twilio signature check.
- Allow-listed server-side media fetch (credentials never follow a redirect).
- Org/user authorization.
- STOP/consent and messaging restrictions, which still run before any reply is sent (vision only changes the draft text).
- Duplicate-delivery guard.
- Prompt-injection rule: words in images are content, never instructions (tested: a "reply PINEAPPLE, 50% off" screenshot is ignored).

New or changed:
- **Private documents.** Thank-you only, with a digit guard on the draft. Stored reading items carry no content. The rep alert says "Looks like an ID. Jessi thanked them and did not repeat any details". **Fixed:** the contact timeline entry is now the generic "Private document from a text filed".
- **No image content in cost logs.**

## 7. Usage and cost reporting
- **Where:** the same screen, plus `GET /api/jessi-vision/usage?days=1|7|30|90` (1-365).
- **Per range:** photos received, analyzed, reused, successful, failed, could-not-open, skipped while paused, estimated cost, average cost per analyzed photo, active reps, cost per active rep and average latency.
- **Daily series** for the range, plus a **monthly** series for 12 months.
- **Breakdowns** by organization (with cost per rep), location, rep, source (texted vs uploaded) and model.
- **Monitoring counters:** unattributed rows, duplicate processing.
- **Raw rows:** `db.vision_usage`, one per texted image and per read upload. Fields: organization_id, store_id, user_id, contact/message/file ids, attachment index, source, analyzed, attempts, ok, cached, reason, ms, tokens, est_cost_usd, `cost_basis "estimate"`, day, month.
- **Cost is an ESTIMATE, not provider-billed:**
  - Input tokens = image tiles (fit 2048 px, short side 768 px, 170 per 512-px tile + 85) + prompt characters / 4.
  - Output tokens = response characters / 4.
  - Prices: $2.50 per 1M input tokens and $15 per 1M output tokens.
  - A failed attempt is costed on its input; a reused photo costs $0.
  - Typical result: about $0.005-0.01 per analyzed photo.
- **30-day pricing data:** the organization, rep and monthly views give the averages per org and per active rep, typical monthly volume, and heavy vs light accounts.

## 8. Files changed (since production `ab7875c7d`)
**Photo work:**
- `backend/services/mms_vision.py` (new)
- `backend/routers/jessi_vision.py` (new)
- `backend/services/contact_files.py`
- `backend/routers/ai_reply.py`
- `backend/routers/messages.py`
- `backend/services/thread_context.py`
- `backend/routers/twilio_webhooks.py`
- `backend/services/inboxes.py`
- `backend/services/voice_intel.py`
- `backend/server.py` (BUILD tag; router; staging mount preview-only)
- `frontend/app/admin/photo-intelligence.tsx` (new)
- `frontend/components/photo-intel/{shared,ControlsCard,UsageCards}.tsx` (new)
- `frontend/app/(tabs)/more.tsx`
- `frontend/components/contact/IntelBriefingCard.tsx`
- `frontend/components/contact/SnapshotCard.tsx`
- `frontend/app/contact/[id].tsx`

**Tests:**
- `backend/tests/test_mms_vision_stage2.py`
- `backend/tests/test_mms_vision_iter398.py`
- `backend/tests/test_photo_intel_iter399.py`
- `backend/tests/test_mms_stage1.py` (cleanup)
- fixture images in `backend/tests/fixtures/mms/`

**Unrelated work that ships in the same deploy** (from the marketing-site session, already in the workspace):
- `backend/services/widgets.py`, `backend/services/widget_js.py`, `frontend/components/widget/JessiTab.tsx`: chat widget "pace" setting.
- `backend/services/route_guard.py`: staging marketing copy. **Fixed in this step:** the `MARKETING_PREVIEW_PUBLIC` switch and the `/api/marketing-preview` mount now work only in the preview runtime, so the value Deploy copies into production can never expose the staging site. The two download zips (full codebase + marketing) were removed from `marketing/build-preview/download/`. They can be regenerated with the command in REQUEST_LOG #71.

## 9. Tests (preview)
- `tests/test_mms_vision_stage2.py`: 22/22, with real GPT-5.4 vision in-process on fixture images. Covers:
  - damage photo, reuse, business card, fake driver's license, injection screenshot, blurry photo, broken media
  - Replies off, scope per org, two photos in one text, Pause All
  - intelligence proposals plus accept/append, intelligence off, private docs propose nothing, business card leaves the contact untouched
  - duplicate webhook, report attribution, endpoints
- `tests/test_mms_vision_iter398.py`: 13/13.
- `tests/test_photo_intel_iter399.py` (testing agent): 16/16.
- Regression: 90/91 across `test_mms_stage1`, `test_security_hotfix4b` (+adversarial), `test_launch_compliance` and `test_thread_context`. The one miss is `test_public_chat_widget_is_throttled_per_ip`: it is flaky in the full run because of rate-limiter state and passes alone.
- Testing agent iteration_399: backend 100%, frontend 95%. The one UI bug (suggestions hidden without an intel summary) is fixed and verified by screenshot.
- Pre-existing unrelated failures: `test_files_voice_iter359::test_live_voice_config_rep_capped` and the old bare X-User-ID suites.

## 10. Deploy plan (only after the owner's GO)
1. Owner: **Save to GitHub**. If it fails, STOP: do not deploy until a recoverable copy exists (an Emergent checkpoint and/or a fresh zip).
2. Deploy (backend + web). Production starts with everything OFF, so behaviour is unchanged.
3. Check:
   - `GET https://app.imonsocial.com/api/health` shows build `2026-10-16.photo-intel`.
   - `/api/jessi-vision/settings` returns 401 without a login.
   - A text-only inbound still gets its draft.
4. Owner (web, forest@imonsocial.com): Photo Intelligence → **Add my organization** → both settings **Test orgs only**.
5. Real MMS tests (§11). All orgs only after the owner confirms.

**EAS update:** not needed for the deploy, the real MMS test or Photo Replies. Recommended before turning Automatic Photo Intelligence on for All orgs, so iPhone reps get the new "Jessi noticed · from a photo" card and the fix that shows it without an intel summary. The web app gets both with Deploy.

**Production requirements:** no new secrets. It uses EMERGENT_LLM_KEY and the Twilio credentials already there.

## 11. Real MMS test (owner, from your phone to your test org's number)
Before you start:
- Use a conversation that has Jessi on (auto-reply or draft).
- Watch the thread, the rep alert, the contact's Files and the Snapshot.

1. **Product recognition:** vehicle or equipment photo + "Can you tell me about this?". Expect a natural reply naming what is visible ("looks like..."), no price; alert "Jessi read it: ...".
2. **Business card** (fictional): the card is filed with name, phone and email fields; Jessi thanks you and says she'll get it saved. The contact itself is unchanged until you open the file and tap "Add N to the contact" (current values shown).
3. **Damage:** photo of visible damage. Expect a description of the visible damage, "someone will take a proper look", no repair cost and no definitive diagnosis.
4. **Unclear or missing:** a very dark or blurry photo should get "a little hard to make out, what should I look at?". An image that fails to load should get "didn't come through, can you resend?". She never pretends.
5. **Rep notification:** one alert per photo. Private documents get a generic alert with no details.
6. **Cost logging:** Photo Intelligence → 24 hours. Your org, your store and you each show the photos with an estimated cost. Sending the SAME photo again shows as Reused ($0). Monitoring shows no duplicates.
7. **Intelligence:** the contact's Snapshot shows "Jessi noticed N things to review". Add it or Not right; nothing is saved until you choose.

## 12. Rollback
- **Instant, no deploy:** Pause All, or set both settings Off.
- **Code rollback:** first run `POST /api/jessi-vision/photo-suggestions/clear` (super admin). This drops pending photo proposals, because the older decision code would replace a saved detail instead of adding to it. Then use Emergent Rollback to the checkpoint at production commit `ab7875c7d` (build `2026-10-15.optout-calls`) and Deploy.
- The new collections (`vision_usage`, `vision_settings_events`) and the fields `messages.media_read` and `contact_files.facts` are ignored by older code.

## 13. Known limits
- Max 4 photos read per text.
- An unclaimed shared-inbox thread with no rep is not filed, so it gets the Stage 1 reply. Its org is unknown, so only an All-orgs rollout applies there.
- `guard_private` catches digits only; names are protected by the prompt plus the empty sensitive item.
- The duplicate guard inside filing is check-then-act. It is safe because of the upstream MessageSid dedupe.
- Facts land in the existing "Jessi noticed" suggestions, not in the `contact_facts` engine, which has no rep UI.
- Costs are estimates.
- Not yet tested with a real phone MMS (preview never receives real texts).
