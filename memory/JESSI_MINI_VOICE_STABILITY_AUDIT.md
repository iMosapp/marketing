# Jessi Mini: Voice Quality & Unexpected Disconnect Audit (Oct 15 2026)

INVESTIGATION ONLY. No code, model, limit, prompt or production setting was changed. No paid voice test was run (owner choice).
Evidence: code (file:line below), **read-only production records** (owner account, last 14 days, through the deployer agent: no transcript text),
a **mocked-session simulation that runs the real `hooks/useLiveJessi.ts`** on a virtual clock (`frontend/scripts/sim-mini-lifecycle.js`,
results `/app/test_reports/mini_lifecycle_sim.json`), and the existing server-side voice suites (24/24 pass, fake provider, no voice cost).

---
## 0. Short answers
| Question | Answer |
|---|---|
| Most likely reason conversations are cut off | **The app's own idle timer, and it only hits Mini.** Production is set to **15 s** (`jessi_voice.idle_close_s`). The timer restarts only when a caption or "speech started" event arrives. On Mini, her caption text arrives faster than her voice, and nothing arrives while the rep is talking. So the 15 s get used up while she is still speaking, while the rep is mid-sentence, or during a lookup. Production: **17 of 31 Mini sessions (55%) ended "idle"** (median 37 s into the conversation). **0 of 33 Premium sessions did.** GPT-Live captions follow its audio and stream while the rep talks. Mini had 0 network drops and 0 allowance stops. |
| Is a time limit causing it? | **Yes: the 15 s idle auto-close**, which acts like a time limit because it is measured wrongly. Separately, the owner's account allows **5 premium minutes a day** (super admins capped too). At minute 5 the app cuts GPT-Live mid-sentence and reconnects on Mini with another voice (3 times in the window). The Mini allowance is **20 min/day** for the owner and **never** ended a session. OpenAI's 60-minute session limit is never reached. |
| Why she repeats the name | The prompt tells her to: `"Use their first name now and then, not every sentence."` (`live_voice.py:264`, same text for Premium and Mini; Mini follows the first half and drops the limit). Her greeting opens with the name, and a compact model copies its own first turn. The production sliders ("fast and clipped", "playful", "as few words as possible") favour stock one-liners where the name becomes filler. Section 6. |
| Fix first | The idle timer fix (P0-1), raising `idle_close_s` in the Voice Lab, and treating a short network blip as recoverable (P0-2). Then the prompt changes in section 6. |
| Without materially raising cost? | **Yes.** Mini bills tokens, not minutes. Silence and waiting add almost no Mini cost. The prompt edits add about 60 instruction tokens, which are cached at $0.06 per 1M. Nothing proposed adds a reconnect loop or raises any allowance. Section 8. |

---
## 1. Current model and configuration (verified)
| Item | Code | Production (read-only) |
|---|---|---|
| Premium engine | `gpt-live-1` (`services/live_voice.py:29`), flat $0.05/min | same |
| Mini engine | `gpt-realtime-2.1-mini` (`live_voice.py:30`), token-billed (`MINI_PRICES` :36), transcription `gpt-4o-mini-transcribe` (:105) | same |
| Mini max output | 1600 tokens per reply, about 80 s of speech (:100) | same |
| Mini listening | server VAD, threshold 0.6, silence 700 ms, prefix 300 ms, near-field noise reduction (`DEFAULTS` :137-140, `mini_turn_detection` :111) | see section 9 |
| Idle auto-close | default 25 s (:137), range 10-120 (:221-225) | **15 s** |
| Personality sliders | defaults energy 4, pacing 4, playful 3, brevity 4 | **energy 4, pacing 5 "fast and clipped", playful 4 "playful", brevity 5 "as few words as possible"**, notes empty |
| Greetings | defaults (:140) | customised: "Hey {first}, Who are we talking about today?" / "{contact} is up. What do you want to know?" |
| Mini listening (VAD) | defaults | not set, so defaults (server VAD 0.6 / 700 ms / near-field) |
| Legacy daily caps (accounts not enrolled) | premium 15 min, Mini 60 min (`DEFAULTS`) | not used for the owner |
| Voice AI controls (enrolled accounts) | `DEFAULT_POLICY` premium 15 / backup 60 min (`voice_controls.py:43-49`). Founder pilot defaults 2 / 10 min, `cap_super_admins = true` (:703-711) | owner org `699aab42780c997666f5ef25`: **premium 5 min/day, Mini 20 min/day, `live_first`, `cap_super_admins = true`, hard cap $25/month**, no user override. Premium 300/303 s used Oct 14-15 (cap hit) |
| Client usage report | every 6 s (`useLiveJessi.ts:325-329`) | as built |
| Limits checked | at start (`create_session` :441-455, `vc.start`) **and on every heartbeat** (`vc.on_heartbeat` :527-611: 60 s slices, stop when the pool is empty) | as built |
| Mini session stop | client 1 s timer vs `cap_left_s` (`useLiveJessi.ts:322`), plus server stop on the heartbeat (:151) | as built |
| Backend build | | `2026-10-14.mms-stage1` |

The documented "Premium 15 / Mini 60 min" values are only the **defaults**. The owner's account runs the founder policy at **5 premium + 20 Mini minutes a day**, with super admins capped too. The legacy `mini_daily_cap_min = 60` doesn't apply to enrolled accounts.

---
## 2. Session lifecycle
```
Tap "Talk to Jessi"  (TalkToJessiButton / WalkMyDay / contact Ask -> LiveJessiProvider.open, app root: _layout.tsx:327)
 └ useLiveJessi.start (state connecting)                                   useLiveJessi.ts:523
    ├ startAudioSession: InCallManager.start + speaker-route poll every 3 s   liveRtc.native.ts:59-65
    ├ connect(): RTCPeerConnection, mic (echo/noise/AGC), data channel        :419-430
    │   ├ ICE gathering <= 10 s, else error                                   :443-455
    │   ├ POST /api/live-voice/session (<= 40 s)                              :458
    │   │    server: allowance check, reserve a 60 s slice (vc.start), build prompt,
    │   │    OpenAI POST /v1/realtime/calls (Mini) or /v1/live/sessions (<= 25 s)   live_voice.py:413-587
    │   └ answer SDP; "no session.started in 20 s" -> no_start                :484-489
    ├ session.created -> onStarted (state live)                                :302-331
    │   ├ greeting response.create, listening OFF until greeting done/8 s     miniSession.ts:73-80, :310, :386
    │   ├ 1 s tick: seconds; Mini: seconds >= cap_left_s -> capHit             :316-324
    │   ├ 6 s heartbeat: POST /events -> on_heartbeat (settle, top-up, maybe stop) :325-329, :151
    │   └ idle timer = idle_close_s (prod 15 s)                                :205-208
    ├ each turn: speech_started -> transcript -> response.created -> transcript deltas -> response.done
    │            (function call -> POST /delegate, up to 60 s -> function_call_output + response.create) :265-300
    └ end -> finish(reason): post "closed", stop mic, close pc/dc, InCallManager.stop   :181-193
```
Not handled anywhere: `output_audio_buffer.started/stopped` (when Jessi's audio actually plays), `input_audio_buffer.speech_stopped`, AppState (background/lock), iOS audio-session interruptions, ICE restart.

---
## 3. Every session termination path
| # | Trigger | Where | close_reason / what the rep sees | Evidence |
|---|---|---|---|---|
| T1 | **Idle timer.** Restarted only by a caption change (`publish`), `speech_started` or session start. `input_audio_transcription.delta`, `function_call_arguments.delta` and `output_audio_buffer.*` are ignored | `useLiveJessi.ts:205-208, 226, 330, 381` | `idle` / "Closed after a quiet spell" (small grey status text) | **17 of 31 Mini sessions, 0 of 33 Premium**. Simulations A-D |
| T2 | Peer connection `disconnected` **or** `failed` | `:432-440` | `connection_lost` / "The connection dropped" | 0 on Mini. 6 on older (pre-engine-field) Premium sessions. Simulation E |
| T3 | Data channel closes (network, provider ended the call, server hang-up) | `:431` | `connection_lost`, same label as T2 | Simulation F |
| T4 | Start problems: ICE 10 s, POST 40 s, no `session.started` in 20 s | `:445, :458, :485-489` | error / `no_start` "did not pick up" | 1 `no_start` in production |
| T5 | Allowance timer (client): Mini `cap_left_s` reached; GPT-Live via `session.usage.updated` | `:216-220, :322, :399` | Premium -> **handoff to Mini** (`premium_cap`). Mini -> `backup_cap` / `daily_cap`, immediate | 3 Premium `premium_cap` handoffs. 0 Mini allowance stops. Simulation G |
| T6 | Server stop in the heartbeat answer (pool empty, kill switch) | `:151, :211-215` <- `voice_controls.py:583-599` | same as T5 | Simulation H |
| T7 | Server kill: stop requested and still open after 20 s -> provider hang-up | `voice_controls.py:687-689`, `live_voice.py:626-651` | the client sees T3 `connection_lost` | 0 seen |
| T8 | Server watchdog: no heartbeat for 150 s -> segment and session closed on the server | `voice_controls.py:29, 682-686` | client keeps talking. The next lookup gets 409 and Jessi says **"That session is closed"** (`routers/live_voice.py:136`, `useLiveJessi.ts:286`) | 1 Mini + 1 older `stale` in production. Simulation J |
| T9 | Stale sweeper: open > 3 h | `live_voice.py:1535-1544` | server only | n/a |
| T10 | Rep taps End (sheet or pill) | `LiveJessiSheet.tsx:37`, `LiveJessiPill` | `close_requested`. Mini audio stops instantly (`:198`) | |
| T11 | Tool result says end | `:298` (shopper mode only, `live_voice.py:1380`) | n/a for assistant | |
| T12 | Hook unmount | `:553`. The provider sits at the app root, so this only happens on a JS reload/crash | `unmounted` / "Closed" | |
| T13 | Engine switch fails | `:494-521` | `handoff_failed` / `voice_cap` | |
| T14 | GPT-Live `session.closed` from the provider | `:402-406` | provider reason, e.g. `expired` "Session limit reached" | |
| T15 | Provider limits | OpenAI (documented): a Realtime session lasts at most 60 min (`expires_at` in `session.created`, never read by the app). The context window is 32,768 tokens; by default older turns are truncated, so the session doesn't end. The app's instructions + tool are about 2k tokens. Errors arrive as `error` events (shown, not fatal) | via T3 | Owner sessions are far below 60 min |
| T16 | iOS audio interruption (call, Siri, another app, **expo-av changing the audio mode**) | no handler | silent mic/speaker -> no events -> T1 idle | needs a device test (section 5) |
| T17 | App backgrounded / screen locked | `app.json` `UIBackgroundModes: audio` keeps WebRTC alive. No AppState handling | if JS pauses > 150 s -> T8 | needs a device test |

Competing cleanups are safe: `finish()` runs once (`finalized` guard). Simulation I: End twice + channel close + unmount -> exactly one close event.

---
## 4. Confirmed bugs (P0 / P1 / P2)
**P0-1 Idle timer measures the wrong thing** (`useLiveJessi.ts:205-208, 226, 381`). Production: Mini idle closes at 16-79 s into the conversation (median 37 s). Their last lookups took 1.1-6.4 s (one 17.5 s), so slow lookups are not the main trigger. On WebRTC, OpenAI streams the transcript faster than real time. `response.done` arrives **before** her audio has finished playing (documented: `output_audio_buffer.stopped` comes after `response.done`). The hook ignores the audio-buffer events, the rep's `speech_stopped`, and in-flight lookups. Simulation, real hook code:
| Scenario | 25 s (code default) | **15 s (production)** |
|---|---|---|
| A: 12 s answer, rep then thinks | closes 14.5 s after she stops talking | **closes 4.5 s after she stops talking** |
| B: long answer (30 s / 18 s), text generated in 2 s | **cut 3 s before her answer ends** | **cut 1.5 s before her 18 s answer ends** |
| C: rep talks without a 0.7 s pause | cut at 25 s while the rep is talking | **cut 15 s into the rep talking** |
| D: slow lookup, 30 s / 20.2 s (production max: Mini 17.5 s, Premium 46.8 s) | closed at 34 s, result never spoken | **closed at 24 s, before the 20.2 s lookup returned** |

**P0-2 A short network blip ends the conversation** (`:434`). `disconnected` is a transient WebRTC state that usually recovers by itself (Wi-Fi roaming, cellular hiccup). The hook ends on it immediately (simulation E). There's no ICE restart and no grace period.

**P0-3 Production idle setting = 15 s** (Voice Lab `idle_close_s`). Combined with P0-1, a 10 s answer leaves the rep about 5 s to start talking (simulation A15: 4.5 s), and any answer longer than about 15 s gets cut (B15). Mini lookup latency: median 4.1 s, p90 11.1 s, max 17.5 s. GPT-Live: median 3.1 s, max 46.8 s.

**P1-1 Mid-call engine switch at 5 premium minutes.** `capHit` -> `handoff('premium_cap')` (`:218`) drops the call immediately, whatever is being said. It reconnects on Mini with a new voice and the line "still here". With 5 min/day and `cap_super_admins = true`, the owner hits this every day.

**P1-2 The Mini allowance end is abrupt with no warning** (`:198, :322`). Simulation G: cut 1.3 s before her answer ended, 0 warnings to the rep or the model. The sheet shows "N min left today" only while live, in small grey text (`LiveJessiSheet.tsx:67`).

**P1-3 The meter watchdog dies on MongoDB timeouts** (production logs, `run_voice_meter_watchdog_job` -> `voice_controls.py:682`, not caught per segment). Dead sessions keep their reserved seconds, which count as **used** (`resolve`, :306-307), so the day's allowance shrinks and caps hit earlier. Ledger rows stay unconfirmed.

**P1-4 (needs a device test) iPhone audio-mode changes during a live call.** `utils/leadChime.ts:27-29` calls `Audio.setAudioModeAsync({ playsInSilentModeIOS: true })`. That defaults `allowsRecordingIOS` to false, i.e. a playback-only category. It fires on a lead push (`_layout.tsx:167`) or when Home's 30 s lead poll sees a bigger queue (`NeedsYouStrip.tsx:26/36`, `LeadsWaitingStrip.tsx:27/29`). Also `liveRtc.native.ts:43` creates an expo-av `Recording` every 3 s to check the route. Either can disturb WebRTC's audio session. The likely effect is "she stopped hearing me", followed by an idle close.

**P2-1 Duplicate `response.create`** after a tool result while a response is active (`:292`). Production: 2x "Conversation already has an active response in progress". The UI filter (`:410`) misses that wording, so it shows as red error text.

**P2-2 End reasons can't be told apart.** Provider end, network loss and server kill are all `connection_lost`. Only the last error is kept (`live_voice.py:684`). The trace keeps the first 60 events instead of the last (`miniSession.ts:42`). `device_id` is never sent by the app (`connect()` omits it). There is no app build/OTA id, no ICE / AppState / audio-route history, and no "last audio event" or "last provider event" time.

**P2-3** After a server-side close (T8) the call stays up, and Jessi reads out "That session is closed".

---
## 5. Likely causes that still need reproduction (physical iPhone, owner)
1. Lead chime / expo-av during a live call (P1-4): talk to Jessi on Home while a test lead arrives.
2. Screen lock / app switch for 30 s and 3 min (T17): does audio continue, do heartbeats continue (server `heartbeat_at`), does the session survive?
3. Wi-Fi -> cellular walk-out (P0-2): expect `connection_lost` within a second today.
4. AirPods in/out and car Bluetooth mid-call (route poll every 3 s).
5. A phone call or Siri arriving during a session (T16).

---
## 6. Repetitive name use
### Exactly what Mini receives (assembled by `create_session` -> `mini_instructions`, `live_voice.py:126-128, 515`): about 8,000 characters / 2,000 tokens
1. `personality()` (:251-257), with the **production sliders**: "You are Jessi... You sound upbeat and energetic, speak at **fast and clipped**, and are **playful**... Keep replies to **as few words as possible**." Clipped + playful + minimal words pushes Mini toward short stock lines ("Got it, Forest."), where the name works as filler.
2. **`rep_line()` (:260-264): "You are talking with {first}, super_admin at {org}. Use their first name now and then, not every sentence."** This is a positive instruction to use the name, with only a vague limit. Mini follows "use their first name" and largely ignores "not every sentence". It also reads the raw role id ("super_admin").
3. `CORE_RULES` (:84-92), backchannel / interruption / delegation policies (:277-319), `REALTIME_RULES` (:79-82), `MINI_RULES` (:94-99), then the context (time, screen, focus contact brief).
4. **Greeting** (production custom text: "Hey {first}, Who are we talking about today?"; `greeting_text` :328-332). Mini is told to say it exactly (`miniSession.ts:75`). Her first turn has the name in it, and a compact model copies the style of its own earlier turns.
5. **Tool results.** Every lookup result is wrapped as **"SAY THIS TO THE REP in your own voice, keep every name and number, add nothing"** (`useLiveJessi.ts:289`). The `answer` tool's longer answers come from a second LLM (`live_voice.py:1145-1151`) whose prompt contains **"Use the person's name occasionally"**, **"Be encouraging: 'Great question!'"** (`jessie_service.py:212, 214`) and **"Address this user as {name}"** (`jessie_service.py:379`). Production shows this path added **0** name mentions in the window (section 9b). It's a latent risk, not today's cause.
6. Walkthrough intro "Hey {first}." (`day_agenda.py:149-151`). The handoff replays the transcript, greeting included (`live_voice.py:605-617`).
7. Premium and Mini get the **same** personality/rep_line/CORE_RULES (prompt parity). Mini only adds the tool and length layers. The difference in behaviour is the model: Mini obeys "use the name" and drops the nuance.

Ranked causes of the repetition: (1) the rep_line instruction "Use their first name now and then", (2) self-imitation from the greeting, which opens with the name, (3) the production sliders "fast and clipped" + "playful" + "as few words as possible", which favour stock one-liners where the name becomes filler, (4) a latent risk: the answer-tool LLM is told to address the user by name (0 in today's data).

### Proposed conversational policy (exact text, for approval)
- Replace `rep_line` with:
  "You are talking with {first}, {role in plain words}{at org}. You already know each other. Say their name at most once, in the greeting. After that, don't use it: never start a reply with it, never use it as filler, in a question or in a confirmation. Use it again only to get their attention after a long silence."
- Add to `CORE_RULES` (both engines, so personality and tone stay the same):
  "- Talk like a person on a phone call: contractions, plain words, no stock phrases. Don't reuse the same opener, acknowledgment or sign-off two replies in a row ('Got it', 'Okay so', 'Perfect').
  - When something needs a follow-up, ask one specific question about the task; otherwise just answer and stop."
- Add to `MINI_RULES`: "After the greeting, do not say the rep's name again."
- Tool result wrapper (`useLiveJessi.ts:289`): "...keep every customer name and number; don't add the rep's name or a greeting."
- `answer` tool (`live_voice.py:1150`): add "Don't address the user by name and no 'great question'." Plus a deterministic clean-up that removes a leading "{first}," from any tool result before it reaches the voice.
- Keep the greeting as is (one name, once). Keep every Voice Lab slider (energy, pacing, playful, brevity) and the owner's notes untouched.
- Check after the change: the production name-count query (section 9) re-run after a week of use. Target: 0 name mentions after the greeting in most sessions.

---
## 7. Proposed stability fixes (for approval, in order)
| # | Fix | Cost effect |
|---|---|---|
| P0-1 | Idle timer counts **real** quiet: pause while Jessi's audio plays (`output_audio_buffer.started` -> `stopped`), while the rep is speaking (`speech_started` -> `speech_stopped`) and while a lookup is in flight. Restart it after each of those ends | none (Mini) |
| P0-1b | Owner setting: Voice Lab `idle_close_s` 15 -> 45 s (setting only, no code) | Mini ~$0 (silence isn't billed as tokens). It does use allowance minutes. GPT-Live: up to 30 s x $0.05/min = $0.025 per conversation |
| P0-2 | `disconnected` = "Reconnecting..." for up to 10 s, end only on `failed` or timeout, with reason `network_lost`. No reconnect loop | none |
| P1-1 | Premium -> Mini switch waits for a natural pause (end of her answer and not mid rep-speech, max 20 s grace counted as overrun), and the 5-min owner policy gets reviewed (owner decision: raise premium minutes, or `mini_only` for the owner) | at most 20 s of premium a day, about $0.017 |
| P1-2 | Allowance warning at 60 s left (visible banner + one quiet note to the model "about a minute left, help them wrap up"), then let the current answer finish (up to 8 s) before closing | a few tokens |
| P1-3 | Watchdog: per-segment try/except + timeout so one Mongo timeout doesn't stop the sweep. Alert when it fails twice in a row | none |
| P1-4 | No lead chime / expo-av audio-mode change while a live session is open. Replace the 3 s `new Recording()` route poll with route-change events (after the device test confirms) | none |
| P2-1 | Send `response.create` only when no response is active (queue until `response.done`), and filter that provider message from the UI | none |
| P2-2 | Keep the LAST 60 provider events in the trace (ring buffer) instead of the first 60. Clear end reasons: `user_ended`, `idle`, `allowance_reached`, `premium_switched`, `network_lost`, `provider_ended` (dc closed while ICE connected), `server_stopped`, `app_error`, `unknown`. Each shown in plain words in the sheet. Send `device_id` and app build/OTA id; keep the last 10 errors, last provider event + time, last audio event + time, ICE/AppState/audio-route history in the existing trace | none (text in Mongo) |
| P2-3 | When the server says the session is closed, end the call with a clear message instead of speaking "That session is closed" | none |
| P2-4 | Elapsed time is already shown. Add remaining allowance before Start and in the pill | none |
| P2-5 | Optional, later: one bounded automatic recovery after `failed` (reuse the existing handoff path, max 1 per conversation, same reservation rules) | at most 1 extra session start per conversation (~2k cached instruction tokens, under $0.001) |
Server-authoritative usage tracking already exists (server clock, client can only raise it: `on_heartbeat` :535-537). Keep it.

---
## 8. Cost implications
- Mini cost is per token. Waiting, silence and "Reconnecting..." add no tokens. Longer idle only uses allowance minutes.
- Prompt changes: about 60-80 more instruction tokens, cached ($0.06 per 1M cached text). Shorter, name-free replies reduce audio output tokens ($20 per 1M), so likely a slight saving.
- No allowance is raised and no reconnect loop is added. The only bounded additions are the switch grace (max 20 s premium a day) and the optional single recovery (P2-5).

---
## 9. Production evidence (read-only, owner account, user_id 69be2bc65c4c5af1e821aecc)
242 sessions in total. 64 carry the engine field (newer sessions): 31 Mini, 33 Premium. 178 older sessions predate the field (GPT-Live era). Every `/api/live-voice/*` call returned HTTP 200. Backend build `2026-10-14.mms-stage1`.

| End reason (min / median / max seconds) | Mini (31) | Premium GPT-Live (33) | Older, no engine field (178) |
|---|---|---|---|
| idle | **17** (16 / 37 / 79) | 0 | 0 |
| close_requested (rep tapped End) | 13 (3 / 9 / 91) | 30 (15 / 80 / 965) | 170 |
| premium_cap (switch to Mini) | n/a | 3 (59 / 122 / 303) | 0 |
| connection_lost | 0 | 0 | 6 |
| no_start | 0 | 0 | 1 |
| stale (server) | 1 (35) | 0 | 1 |
| backup_cap / daily_cap (allowance) | **0** | 0 | 0 |

The 17 Mini idle sessions: seconds 34, 21, 23, 33, 52, 42, 16, 40, 32, 54, 37, 79, 50, 35, 46, 19, 71. Lookups per session 0-5 (5 had none). Last lookup 1.1-6.4 s, one 17.5 s. Only 3 have a trace.
- **Logging gap found:** the trace keeps the FIRST 60 provider events (`miniSession.ts:42`, `TRACE_LIMIT`), not the last ones. So it can't show what happened right before a close. In those 3 traces, events 57-60 are `input_audio_transcription.delta` (the rep's words still being transcribed) and `response.function_call_arguments.delta` (a lookup being formed). The hook ignores both event types for the idle timer.

Lookup latency (606 lookups): median 2.8 s, p90 5.5 s, max 46.8 s, 2 over 15 s. Mini (28): median 4.1 s, p90 11.1 s, max 17.5 s, 1 over 15 s.
Other: 2x provider error "Conversation already has an active response in progress". The meter watchdog job is throwing MongoDB timeouts (`voice_controls.py:682`; platform Atlas latency).

**Why only Mini goes idle:** GPT-Live's caption events follow its audio and stream while the rep talks (`session.input_transcript.delta`). Every delta restarts the idle timer. On Mini the transcript arrives ahead of the audio, and nothing arrives while the rep talks until they stop. Same timer, same 15 s, very different result.

### 9b. Name use (production counts, numbers only)
Delegation results containing the rep's first name: Mini 8, Premium 26, `answer` tool 0 on both. Most of these are drafted customer texts that legitimately contain the rep's name ("it's Forest from..."), and the "answer" tool path didn't contribute. Rep rows containing the name: Mini 0, Premium 4. First reply after the 3 handoffs: 0 mentions. The per-row assistant counts (greeting vs later, Mini vs Premium) have been requested; they're not needed to decide the prompt fix, but they're the before/after metric.
---
## 10. Test results
| Test | Type | Result |
|---|---|---|
| `frontend/scripts/sim-mini-lifecycle.js` (real hook, mocked provider, virtual clock) | automated, mocked | A/A15, B/B15, C/C15, D/D15 reproduce idle cut-offs; E short blip ends the call; F provider end looks like network; G allowance cut with 0 warnings; H server stop honoured; I one close only; J "That session is closed" spoken |
| `tests/test_voice_controls.py`, `test_voice_fallback.py`, `test_live_voice.py` | automated, fake provider | 24/24 pass (allowance, handoff, watchdog stale, kill switch, listening config) |
| Name-use measurement | production counts | section 9b (tool results: Mini 8 / Premium 26, answer tool 0) |
| Paid live Mini test | not run | owner skipped it. Preview has no OpenAI key |
| Short/long conversations, silence, interruptions, rapid back-and-forth | mocked (A-D) | as above |
| Network switch, backgrounding, screen lock, audio interruptions | **physical iPhone, owner** | checklist below |

### Owner iPhone checklist (after the fixes, or now to confirm the diagnosis)
1. Ask a question that needs a lookup ("who asked about a Tesla last month") and wait. Today it closes about 15 s after "one sec".
2. Ask for a long answer ("walk me through everyone today"). Today it cuts before she finishes.
3. Talk for 20 s without pausing. Today it cuts while you are talking.
4. Walk from Wi-Fi to cellular mid-conversation.
5. Lock the screen for 30 s, then for 3 min, and keep talking.
6. On Home, have a test lead arrive during a conversation.
7. AirPods in/out mid-conversation. A phone call coming in.
8. Use Jessi for more than 5 minutes in a day (premium -> Mini switch).
After each: note the time and what the sheet said. The session row records the reason.

---
## 11. Prioritized implementation plan (awaiting approval)
1. **P0 (one small frontend change + one setting):** P0-1 idle timer fix, P0-2 network grace, Voice Lab `idle_close_s` -> 45 s. Re-run the simulation (all of A-E must pass) and the 24 server tests. iPhone checklist items 1-4.
2. **P1:** prompt and policy changes in section 6 (name, repetition, tool wrapper, answer-tool prompt), premium-switch grace + owner policy decision, allowance warning + graceful end, watchdog hardening, lead chime / audio-mode guard.
3. **P2:** end-reason codes + diagnostics + device/build id, `response.create` guard, server-closed handling, remaining-minutes display, optional single recovery.
Delivery: backend changes need Deploy. App changes ship with the next OTA (no native change). Nothing ships without approval.
