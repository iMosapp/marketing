# RCA Follow-up — Realtime Mini duplicate opening greeting

**App:** https://app.imonsocial.com (imos-deploy-prep)
**DB:** imos-admin-test_database · collection `live_sessions`
**Active run:** bf277e6b-3ca6-42e1-9aff-a1dba73663cc
**Mode:** READ-ONLY. No deploy/secret/restart/data changes made.

## Goal
Distinguish the two candidate causes of the Mini duplicate greeting:
- (A) VAD / noise / speakerphone re-trigger — ambient audio makes the model re-emit the greeting.
- (B) Code-level double emission — the greeting is sent twice programmatically.

## Sessions examined (8 most recent engine="mini")

### Section 1 — session fields
| live_id | created_at | engine | mode | meter.role | meter.fallback_reason | resumed_from | handoff_reason | close_reason | seconds | noise_turns | DUP? |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1799c361ce2b | 2026-10-14T23:08:20.951Z | mini | assistant | backup | premium_cap | null | null | close_requested | 3 | MISSING | **YES** |
| fff25ee9ff71 | 2026-10-14T23:07:50.009Z | mini | assistant | backup | premium_cap | null | null | close_requested | 9 | MISSING | **YES** |
| 1bc8319dc49c | 2026-10-14T22:12:02.254Z | mini | assistant | backup | premium_cap | null | null | close_requested | 13 | MISSING | **YES** |
| 49d6ad63ed91 | 2026-10-14T19:24:09.710Z | mini | assistant | backup | premium_cap | null | null | idle | 79 | MISSING | no (contrast) |
| 368d9f938ba6 | 2026-10-14T19:23:13.758Z | mini | assistant | backup | premium_cap | null | null | idle | 37 | MISSING | no (contrast) |

noise_turns is absent from every document → reported MISSING (not 0).

### Section 2 — first transcript rows + greeting gap
| live_id | greeting #1 (role, start_ms→end_ms) | greeting #2 (role, start_ms→end_ms) | gap end#1→start#2 | user/rep turn between? |
|---|---|---|---|---|
| 1799c361ce2b | assistant 359→603 "Hey Forest, who are we talking about today?" | assistant 1076→1348 (identical) | **473 ms** | none |
| fff25ee9ff71 | assistant 270→480 (same text) | assistant 764→965 (identical) | **284 ms** | none |
| 1bc8319dc49c | assistant 314→695 (same text) | assistant 818→924 (identical) | **123 ms** | none |
| 49d6ad63ed91 | assistant 280→444 (same text) | — (next row is rep @3469ms) | n/a | rep speaks next — single greeting |
| 368d9f938ba6 | assistant 290→504 (same text) | — (next row is rep @3747ms) | n/a | rep speaks next — single greeting |

Duplicates = two byte-identical assistant greetings back-to-back, sub-second apart, with NO user/rep turn in between.

### Section 3 — stored events/errors + session-level mini_vad
- `events` array: absent in all docs.
- `errors` array: absent in all docs.
- Session-doc `config.mini_vad` / `mini_vad_threshold` / `mini_silence_ms` / `mini_noise_reduction`:
  - 1799c361ce2b / fff25ee9ff71 / 1bc8319dc49c (all 3 DUP): mini_vad=`server`, mini_vad_threshold=`0.6`, mini_silence_ms=`700`, mini_noise_reduction=`near_field`
  - 49d6ad63ed91 / 368d9f938ba6 (both CLEAN): **identical** — mini_vad=`server`, 0.6, 700, near_field
  - → VAD config is the SAME in duplicating and non-duplicating sessions.

### Section 4 — settings.jessi_voice (source-of-truth voice config)
Doc key `jessi_voice`, updated_at 2026-10-09T03:35:07Z by forest@imonsocial.com. value:
```
engine=live, voice=gleam, mini_voice=marin, greeting="Hey {first}, Who are we talking about today?",
contact_greeting="{contact} is up. What do you want to know?", brevity=5, energy=4, pacing=5,
playful=4, idle_close_s=15, daily_cap_min=30, mini_daily_cap_min=60, notes=""
```
**mini_vad / mini_vad_threshold / mini_silence_ms / mini_noise_reduction are NOT present in settings.jessi_voice.** They exist only inside per-session `config` snapshots → they are injected as code defaults at session-create time, not read from saved settings. (Note: older Mini sessions on 2026-10-13 had config WITHOUT these keys; they appear in 10-14 sessions — a code default was added between those dates.)

### Section 5 — audio route / speakerphone
No `audio_route`, `speakerphone`, or equivalent field exists on any live_sessions document. Audio route is NOT recorded → cannot attribute to speakerphone.

## Root cause (which of A vs B)
Evidence points to **(B) code-level double emission of the opening greeting**, not (A) VAD/noise:
1. The two greeting rows are byte-identical and back-to-back with NO intervening user/rep turn.
2. Gaps are 123–473 ms — far below the 700 ms `mini_silence_ms`; a VAD/noise re-trigger would require a speech+silence cycle and could not re-fire the *same templated greeting* that fast.
3. VAD config (`server`, 0.6, 700, near_field) is byte-identical between the 3 duplicating and the 2 clean sessions → config is not the differentiator.
4. No `events`/`errors`/`noise_turns` recorded that would indicate a noise event drove a second response.
5. Secondary corroboration: session b924f52d9c64 shows the SAME double-emission pattern on a non-greeting turn ("I couldn't find anyone named Travis Camino…" emitted twice, 15815 vs 17286 ms end, near-identical text) — consistent with a general response-duplication bug, not greeting-specific noise.

Cause (A) cannot be supported: no noise/VAD event data stored, no audio-route field, and identical VAD config across dup/clean. This is inferred from stored DB evidence only — NOT reproduced live (reproduction needs the live Realtime/OpenAI session + audio, which the sandbox cannot run).

## Suggested fix
- **Code (E1):** Guard the opening-greeting send so it fires exactly once per Mini session (e.g. dedupe/idempotency flag on the initial assistant response; likely a duplicate `response.create` or greeting-injection on the gpt-realtime-mini path). Also inspect the general response path — the Travis-Camino repeat suggests the duplication is not limited to the greeting.
- **Code/data (secondary):** `settings.jessi_voice` does not persist the mini_vad* keys, so those knobs are not user-tunable from settings today — if VAD tuning is intended to be configurable, wire these into the settings doc. This is a gap, not the cause of the duplicate.
- Not a secrets / tier / infra / domain issue.
