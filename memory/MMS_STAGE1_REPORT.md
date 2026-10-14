# MMS Stage 1 — report (Oct 14 2026) · NOT DEPLOYED

Build label: `2026-10-14.mms-stage1` (server.py BUILD + prod smoke DEFAULT_BUILD). Production is still on `2026-10-14.security-hotfix4c`.

## Root cause (confirmed live)
Twilio serves an inbound MMS image as `api.twilio.com/.../Media/ME…` → `307` → `https://mms.twiliocdn.com/...`.
Hotfix 4B's proxy only trusted `media.twiliocdn.com`, so the redirect was refused → `502 GET /api/webhooks/twilio/media-proxy` → gray tile on iPhone.
Recordings don't redirect (`200 audio/mpeg`), which is why only photos broke.

## A. Media proxy — `backend/routers/twilio_webhooks.py`
- `_TWILIO_CDN_HOSTS = ("media.twiliocdn.com", "mms.twiliocdn.com")` — exact host match only. Unchanged: HTTPS-only, no userinfo, no port,
  `allowed_media_url` (api.twilio.com Accounts/…/Media or Recordings paths only), 1 redirect hop, media token required, signature enforcement.

## B. Attachment-aware Jessi (text-only fallback until AI Vision)
- `routers/ai_reply.py`: `queue_ai_reply(..., attachments=N)`; new `attachment_notice()` prompt block + `attachment_preview()`.
  - Flags the thread (`needs_assistance`, `you_are_needed_at`, `attachment_prompted_at`), inserts a "sent a photo - Jessi can't see it"
    You're-Needed notification + push to the assigned rep (or alerts the inbox team).
  - A second photo-only text within 30 min: human already flagged, **no second AI reply** (no nagging).
  - The prompt forbids describing/reading the image, promising to send anything, or apologising in loops; asks for the one typed detail.
  - Draft/approval cards show `[sent a photo]` instead of an empty preview.
- Call sites pass the count: `twilio_webhooks.py` (3 sites: conversation-level, assigned-inbox, drip) and `services/inboxes.py` (whose
  empty-body gate now lets photo-only texts through so the inbox team gets the flag).
- `services/thread_context.py`: customer lines with media read `[sent a photo you cannot see]` (+ text), so Ask Jessi and the draft
  endpoints see the same thing. `routers/messages.py` `/ai-suggest` appends the same notice when the last inbound has media.
- Not changed: ai_mode/off/draft_only gates, human takeover pause, approval flow, SMS send guard.

## C. Relabel
"All Good" → "Mark Handled" in `app/thread/[id].tsx`, `app/(tabs)/inbox.tsx`, `app/help.tsx`. Same `updateConversation(needs_assistance:false)`,
same permissions, same testids (`all-good-btn` kept).

## Frontend photo tile — `components/thread/MessageBubble.tsx`
`MediaImage` re-resolves the URL when the media token arrives/refreshes (store subscription), shows "Couldn't load this photo · Tap to retry"
on error, tap opens the full image. No change to token/auth flow (`resolvePhotoUrl` / `withMediaToken` as before).

## Tests (preview, Oct 14 2026)
- New `tests/test_mms_stage1.py` — 7/7: allow-list exact (lookalike/port/userinfo/http/S3-path rejected); live proxy on a **real** inbound MMS
  from the Twilio account → 401 without token, 200 image/* with token; helpers; signed photo-only inbound → flagged + notification + draft
  never claims to see it, second photo within 30 min → no second draft; text+photo → normal reply with the notice; thread reader labels;
  Ask Jessi suggestion on a photo-only thread (real LLM): "Hey, I can't open photos/attachments on my end, can you just type the best email…".
- Regression batch (hotfix3 authz, hotfix4, 4b, 4c, twilio tenant, thread_context, mms): **84 pass**. Two pre-existing failures in
  `test_thread_bugfixes.py::TestConversationInfoEndpoint` (unauthenticated calls, 401 since Hotfix 3 — unrelated, stale test).
- Preview runs `TWILIO_WEBHOOK_VALIDATION=log` (as requested); the unsigned-callback assertions now read the mode via `tests/live_auth.unsigned_twilio_codes()`
  so they still assert 403 in enforce mode (production).
- Frontend: `tsc` no new errors (one pre-existing in help.tsx); web screenshot of a QA thread shows the retry tile for an unreachable proxy URL,
  a rendered image, and the "✓ Mark Handled" chip in the Jessi banner.
- QA artefacts cleaned; QA rep `qa-mms-rep@…` recorded in `memory/test_credentials.md`.

## Deployment (awaiting approval)
Backend deploy only (media proxy + Jessi fallback). The MessageBubble/label changes ship with the next mobile OTA/EAS build; web picks them up on deploy.
Post-deploy checks: `/api/health` build = `2026-10-14.mms-stage1`; open an MMS thread on iPhone → photo renders; prod smoke `tests/prod_smoke_hotfix3.py`.
No secrets rotated, no env changes, no other integrations touched.
