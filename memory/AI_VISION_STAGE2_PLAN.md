# Stage 2 plan — Jessi AI Vision + Relationship Intelligence (plan only, not approved, not started)

## What exists today (reuse, don't rebuild)
- Inbound MMS: `routers/twilio_webhooks.py` already validates the Twilio signature, collects `MediaUrl0..N` + `MediaContentType0..N`, stores
  `media_urls` (proxy URLs), `media_types`, `num_media` on the message, and calls `queue_ai_reply(..., attachments=N)` (Stage 1).
- Secure fetch: `_fetch_twilio_media()` (credentialed GET, exact-host redirect allow-list, size cap) is the only path that touches Twilio media.
- LLM plumbing: `emergentintegrations.LlmChat` + `EMERGENT_LLM_KEY`, model in `services/llm_models.py`; `UserMessage(file_contents=[ImageContent(...)])`
  is the library's image input (exact model/version to be confirmed with the integration playbook at implementation time).
- Context: `services/thread_context.py` (dialogue/topics), `get_contact_brief()` (contact facts for prompts), `contact_intel` router (relationship notes).
- Human loop: `needs_assistance` / You're-Needed notifications / `attachment_prompted_at` (Stage 1), takeover pause, approval queue.

## Phase 1 — Secure image understanding (server-side, per message)
1. `services/vision.py` (new, ~150 lines)
   - `describe_media(db, org_id, message_id) -> VisionResult | None`
   - Gate: feature flag `org.features.ai_vision` (default off) + per-org daily budget (`org_usage.vision_images_today`, default 300/day) +
     per-conversation cap (3 images / 10 min). Over budget → skip, Stage 1 fallback still runs.
   - Fetch via `_fetch_twilio_media()` only (never trusts the stored proxy URL; rebuilds the api.twilio.com URL from stored SIDs).
   - Accept `image/jpeg|png|webp|heic→jpeg` ≤ 5 MB, ≤ 4 images per message; re-encode with Pillow (strip EXIF/GPS, max 1280px) before the model sees bytes.
     Anything else (vcf, pdf, video, gif >…) → `kind="unsupported"` → Stage 1 behaviour.
   - Prompt returns strict JSON: `{kind: screenshot|vehicle|document|person|other, summary, extracted_text, entities:{emails[],phones[],vins[],plates[]},
     vehicle:{year,make,model,color,damage_notes}, confidence 0-1, unsafe:boolean}`. System prompt: "describe only what is visible; no identity guesses".
   - Store `message.vision = {...result, model, created_at}`; cache by `sha256(bytes)` per org (`vision_cache`, 30 days) so a re-sent photo costs nothing.
   - Never log image bytes/URLs/tokens; log only `kind`, `confidence`, token usage.
2. Wire into `queue_ai_reply`: if `attachments` and vision enabled → await `describe_media` (timeout 12 s) **before** the notice;
   on success replace `attachment_notice()` with an `ATTACHMENT CONTENT` block ("A teammate's tool read the photo: … Treat as a reading, confirm anything
   you act on"). Low confidence (<0.5) or `unsafe` → keep Stage 1 fallback + human flag. Same for `/ai-suggest` and Ask Jessi.
3. Rep-facing: the thread photo tile gets a small "Jessi read: ‘screenshot of a Gmail inbox, email john@…’" caption (tap to copy extracted text).
   Mobile: `MessageBubble.tsx` reads `message.vision`; no new network calls.

## Phase 2 — Relationship intelligence (attributed, confidence-qualified)
- `contact_observations` collection: `{org_id, contact_id, source:"vision"|"text"|"rep", message_id, field, value, confidence, status: proposed|accepted|rejected, created_at}`.
- Vision entities with confidence ≥ 0.8 become **proposed** observations (email, phone, vehicle, plate), never written straight to `contacts`.
- Rep UI: a "Jessi noticed" card on the contact sheet (accept / dismiss). Accept → existing contact update endpoint (same RBAC), audit row.
- Prompts (`get_contact_brief`) include accepted facts as facts and proposed ones as "unconfirmed, customer may have sent …" so Jessi can ask, not assume.
- Tenant isolation: every query keyed by `organization_id` + contact ownership via existing `_contact_for_caller`-style guards.

## Phase 3 — Controls and rollout
- Super-admin toggle per org (reuse `tenant` admin screens): `ai_vision` on/off, daily image budget, "auto-accept emails/phones" (default off).
- Kill switch independent of MMS display: turning vision off never affects the media proxy.
- Rollout: preview → Forest's org only (shadow mode: results stored, not used in replies) for 3 days → enable in replies for that org → all orgs.

## Cost (order of magnitude)
~1–1.5k input tokens per 1280px image + ~300 output ≈ $0.005–0.01 per image on the current OpenAI tier via the Emergent key.
300 images/day budget ⇒ worst case ≈ $3/day/org; realistic dealership volume (20–60 MMS/day) ≈ $5–15/month/org.

## Tests to write
- Unit: MIME/size/count gating, EXIF stripping, JSON schema validation, cache hit, budget exhaustion → fallback, unsupported → Stage 1 path.
- Live (preview): signed MMS with a real screenshot → `message.vision.kind == "screenshot"`, extracted email proposed (not written), Jessi's draft uses it and asks to confirm;
  takeover paused thread → no AI reply; other org cannot read `/contacts/{id}/observations`; model timeout → Stage 1 notice; two photos → single human flag.
- Regression: all Hotfix 3/4/4B/4C suites + `test_mms_stage1.py`.

## Dependencies / approvals needed before coding
- Integration playbook for the chosen vision-capable model (via the integration workflow) — confirms exact model name and image-input API.
- Decision: auto-accept nothing (recommended) vs auto-accept emails/phones at ≥0.9 confidence.
- Pillow already in requirements? (check) — otherwise one dependency add.
Estimated effort: Phase 1 ≈ 1 day incl. tests, Phase 2 ≈ 1 day, Phase 3 ≈ ½ day.
