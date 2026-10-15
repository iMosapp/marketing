# RCA — imos-deploy-prep (forest@imonsocial.com)

Read-only production investigation. Active run `b28dc7f3-bcab-456a-bcce-d8d8c0bede3c` (redeploy, success 2026-10-15T19:08:25Z). Frontend: cloudflare. DB: `imos-admin-test_database`.

---

## PROBLEM 1 — Inbound calls to the owner's Twilio number fail ("application error")

### a. Build / deploy status
- `GET /api/health` → 200, body `{"status":"healthy","message":"I'm On Social API v2.0","build":"2026-10-15.mini-voice"}`. Source `server.py:56` `BUILD = "2026-10-15.mini-voice"`.
- Today's deploy FINISHED: active run `b28dc7f3` type=redeploy status=success, created 18:55:50Z, completed 19:08:25Z.

### b. Voice webhook logs (last 24h)
Most recent real inbound-call traffic is on the PRIOR build (run `17cc5f8c`, active ~08:25–18:05Z). The current mini-voice run (`b28dc7f3`, pods up 19:08Z) has had **NO inbound/voice webhook calls at all** since deploy — only scheduler jobs. So the reported "application error" is **NOT reproduced in any log**.

Observed inbound self-calls on run 17cc5f8c, all From `+18016349122` → To `+14352203414`:
- 16:13:59 `[Voice] Inbound call ... SID=CA9e9799...` → `POST /voice` 200 → `POST /call-whisper` 200 → 16:14:15 `[Voice] Dial status=completed bridged=false from +18016349122` → `POST /voice-fallback` 200
- 16:14:25 `... SID=CAb24aac...` → `/voice` 200 → `/call-whisper` 200 → 16:14:41 `Dial status=completed bridged=false` → `/voice-fallback` 200
- 16:25:13 `... SID=CA75bf6b...` → `/voice` 200 → `/call-whisper` 200 → 16:25:30 `Dial status=completed bridged=false` → `/voice-fallback` 200

Outbound (worked): 16:15:43 `[Voice] Outbound call: rep=+18016349122 → customer=+18016349122 | SID=CA1dd2a...`; bridged; `/recording-complete` 200; transcribed.

- NO `[TwilioSig]` warning lines, NO 403/"forbidden"/"signature mismatch" lines in any run.
- NO tracebacks on any voice endpoint (`/voice`, `/voice-fallback`, `/call-whisper`, `/call-whisper-accept`, `/recording-complete`, `/voicemail-recording`, `/voicemail-transcription`). `/call-whisper-accept`, `/voicemail-recording`, `/voicemail-transcription` did not fire in the window (no caller left a recording).
- Only errors in the 24h window: a TRANSIENT MongoDB DNS outage 17:25–17:26Z — `ServerSelectionTimeoutError ... [Errno -3] Temporary failure in name resolution` on `/api/tasks/.../summary` and `/api/notification-center/.../unread-count` (plus an incidental `TypeError: Object of type ObjectId is not JSON serializable` during that blip). Unrelated to voice; self-resolved. Infra blip, not a voice fault.

### c. Secrets / URLs
- `TWILIO_WEBHOOK_VALIDATION` = set, value "enforce" (matches_expected=true).
- `PUBLIC_FACING_URL` = `https://app.imonsocial.com` (matches_expected=true).
- `APP_URL` = `https://imos-deploy-prep.emergent.host` (the platform default host, NOT the custom domain; matches_expected=true for that value).
- Signature validator (`services/twilio_signature.py` `candidate_urls`) tries `PUBLIC_FACING_URL` first, then the raw request URL, then `x-forwarded-host` — so the `APP_URL`=default-host value is tolerated and is NOT causing 403s. Confirmed: pre-deploy inbound calls validated fine (all 200), no `[TwilioSig]` lines.

### d. Owner doc & number comparison
users `_id=69be2bc65c4c5af1e821aecc`, email `forest@imonsocial.com`, status **active**, organization_id `699aab42780c997666f5ef25`:
- `phone` = **"8016349122"** — SET, last4 **9122**, stored WITHOUT `+1`.
- `twilio_number` = `+14352203414` (last4 3414); `mvpline_number` = `+14352203414`.
- Inbound calls are From `+18016349122` (last4 **9122**).
- **YES — the owner's cell (`users.phone`, 9122) and the number he calls FROM (9122) are the SAME number.** (Note: 2 other docs share this number — forestward@gmail.com `+18016349122` active, and merged_forest@imosapp.com 8016349122 deactivated.)

Consequence (root cause of the "inbound won't connect" symptom): `handle_inbound_voice` (`routers/twilio_webhooks.py` ~2294) looks up the rep by `twilio_number`/`mvpline_number` = the owner, then `<Dial>`s `normalize_phone(rep_user.phone)` = `+18016349122` — i.e. the owner's OWN cell, which is the very phone placing the call. The dial can never bridge (`bridged=false`), so Twilio invokes the action `/voice-fallback` → voicemail. Every "call my own number from my own cell" test is a self-call collision that always falls to voicemail; it can never ring through.

### e. phone_numbers registry row
- The app code (`services/voicemails.py` `line_owner`) queries `db.phone_numbers`, but **there is NO `phone_numbers` collection** in this database (211 collections; none named `phone_numbers`). So there is **no registry row** for `+14352203414` in the app DB, and the voice/sms webhook URLs are NOT stored app-side — they live in the Twilio console.
- Only app-side record is `phone_number_pool`: `_id=6a0e89fa6c2bf0eca077bb31`, `assigned_user_id=69be2bc65c4c5af1e821aecc`, `status="assigned"`, `twilio_sid=PNa5a637e4f5b00f2a6fae020883a363e5` (PN… phone SID). No webhook URLs on this doc.
- Twilio account: SID seen in callback URLs is **AC**92414d0b73ac4dd71376763874db99f8 — the **parent "AC" account** (no subaccount indicated).

### f. Voicemail greeting doc
- **YES** — `voicemail_greetings` has a doc for the owner: `_id=6ab71f5f7e62ed54f9550f43`, `user_id=69be2bc65c4c5af1e821aecc`, created 2026-09-26. `greeting_twiml` therefore returns `<Play>{greeting mp3 url}</Play>` for this user.

### Problem 1 conclusion
The literal "An application error has occurred" could NOT be reproduced — the mini-voice build has logged no inbound calls, and the last real inbound calls (prior build) all returned 200 and routed correctly to voicemail. The clearly-proven issue is the **self-call collision**: `users.phone` (owner's cell, 9122) equals the number he dials from, and the inbound handler dials that same cell, so it never bridges. To diagnose the specific "application error", a test call is needed FROM A DIFFERENT phone (not 9122), capturing the Twilio Call SID + the exact error, so the specific failing webhook response can be pulled. The `APP_URL` pointing at the default host (not the custom domain) is noted but is NOT causal (validator prefers `PUBLIC_FACING_URL`, which is correct, and no 403s were seen).

---

## PROBLEM 2 — Every outbound text carries the "Reply STOP to opt out" disclosure

### Data
`sms_disclosure_state` (1 doc for this phone):
- `_id` = `699aab42780c997666f5ef25:sender:+14352203414:+18016349122`
- `program` = **`sender:+14352203414`**
- **`first_at` = ABSENT (NO)**
- `total` = 4, `disclosures` = 3, `since_last` = 0, `last_at` = 2026-10-15T16:19:45.344Z, `last_version` = 2026-06-v1, `last_delivery_status` = delivered.

`sms_disclosure_events` (3 docs total for this phone, newest first):
- 2026-10-15T16:19:45.344Z — program `sender:+14352203414`, reason **first_message**, version 2026-06-v1
- 2026-10-15T16:16:45.289Z — program `sender:+14352203414`, reason **first_message**, version 2026-06-v1
- 2026-10-15T16:14:45.531Z — program `sender:+14352203414`, reason **first_message**, version 2026-06-v1

- NO `[Disclosure] record failed` or `[SMS] disclosure plan failed` log lines.
- `settings.disclosure_policy` — **not present** (no such settings doc).
- `organizations.messaging_disclosure` — **not present**. Org exists (`_id=699aab42780c997666f5ef25`, name "I'm On Social") but has no `messaging_disclosure`/`disclosure` field. So disclosure behavior falls entirely to the code DEFAULT_POLICY.

### Root cause (code — CONFIRMED by reading `backend/services/disclosure.py`)
Program `sender:+14352203414` maps to category **"standard"** (`program_id()` returns `sender:<from>` for non-marketing purposes; standard rules = `first_message:True, every_message:False`). So the INTENDED behavior is disclosure on the first message only — this is a bug, not config.

The first-message gate in `plan()`:
```
st = await db[STATE].find_one({"_id": sid}) or {}
if not st.get("first_at"):
    reason = "first_message" if rules.get("first_message") else None
```
It keys entirely off `first_at`. But `record()` only ever writes `first_at` via `$setOnInsert`:
```
# included (disclosure sent) branch
update_one({"_id": sid}, {"$set": {... "since_last": 0}, "$setOnInsert": {"first_at": now}, "$inc": {"total":1,"disclosures":1}}, upsert=True)
# else (no disclosure) branch
update_one({"_id": sid}, {"$set": {...}, "$inc": {"total":1,"since_last":1}}, upsert=True)   # <-- NO first_at
```
`$setOnInsert` only fires on document CREATION. If the state doc gets created once WITHOUT `first_at` (the `else` branch has no `first_at`; and on any already-existing doc `$setOnInsert` is a no-op), then `first_at` is NEVER populated. Once `first_at` is permanently absent, the gate `if not st.get("first_at")` is ALWAYS true → every eligible message is classified `first_message` → the standard disclosure is appended to (nearly) every outbound text. The data proves it: `first_at` absent, 3 of 4 messages disclosed, all three events reason `first_message`.

### Problem 2 fix (E1 / Code — requires redeploy)
In `backend/services/disclosure.py` `record()`, guarantee `first_at` is written the FIRST time ANY message is recorded for a `(org, sender, phone)` state — e.g. add `"$setOnInsert": {"first_at": now}` to the `else` (no-disclosure) branch as well, OR set `first_at` in `$set` when it is missing. After the fix, back-filling `first_at` on existing `sms_disclosure_state` docs (or letting it set on next message) will stop the repeated disclosures.

---

## Fix summary
- Problem 1: Not reproduced as an "application error"; proven cause of non-bridging is the self-call collision (owner's `users.phone` 9122 == call-from number). USER: retest from a different phone and capture the Twilio Call SID + exact error. (Optional CODE hardening: detect From == rep cell in `handle_inbound_voice`.)
- Problem 2: CODE bug in `services/disclosure.py` `record()` — `first_at` never persists, so every text is treated as "first_message". E1 fix + redeploy; back-fill/repair existing state docs.
