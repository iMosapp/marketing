# Jessi voice: GPT-Live vs Realtime Mini prompt parity (Oct 13 2026)

## Phase 1: what each engine actually gets (backend/services/live_voice.py)
| Block | GPT-Live (`gpt-live-1`, voice Gleam) | Realtime Mini (`gpt-realtime-2.1-mini`, voice Marin) |
|---|---|---|
| Personality (identity + Voice Lab sliders energy/pacing/playful/brevity + admin notes) | `personality(cfg)` | same text |
| Rep profile (first name, role, store) | `rep_line(user)` | same |
| Contact in focus / language | `focus_line`, `Speak {language}` | same |
| No-backchannel rule, interruption rule | in `assistant_instructions` | same |
| Delegation policy + 26 backend tools (who_today, recall, text, reminder, note, call, ... ) | prose in `assistant_instructions`; tools run server-side in `delegate()` via GPT-Live's native `delegation: client` | same prose; one function tool `delegate(request)` + `tool_choice auto`; same server-side `delegate()` |
| Relationship memory / history | never in the prompt: fetched per request by `delegate()` (recall_person etc.) | same |
| Time, screen, team digest, walkthrough | `context` sent as a separate developer-role input item | `context` appended INSIDE the one instructions string |
| Hand-off (premium pool spent) | `_handoff_context(prev)`: last 40 turns / 6000 chars + "do not greet again" + pending yes/no; greet `_handoff_greet` "Okay, still here, go ahead" | same two blocks |
| Fresh-session greeting | `session.instructions.append` "say, in your own words: ..." | `response.create` (a forced turn) with the same "in your own words" text |
| Tool pre-ack | nothing | `REALTIME_RULES`: "say two or three words first ('one sec', 'pulling that up')" before every call |
| Model parameters | none (GPT-Live handles turn taking) | `semantic_vad` on from the first millisecond (create + interrupt), no `max_output_tokens`, default temperature |
| Transcription | internal | `gpt-4o-mini-transcribe` |
| Pricing | $0.05/min flat, 15 s minimum | token based (audio in $10/M, out $20/M, text in $0.60/M, cached $0.06/M); fallback $0.015/min |

What Mini was missing or handling differently: nothing in content (profile, memory, tools and hand-off context are identical), but (1) the brevity rule was one clause buried at the top of a 6,000-character string, which the compact model does not weigh like GPT-Live does; (2) an extra chatter instruction before each tool call; (3) no output cap; (4) turn detection live during the greeting. The iPhone screenshot (fresh Mini session, 0:07, transcript "Hey Forest, who are we talking about today?Hey Forest, who are we talking about today? I'm listening—go ahead...") is (4): the greeting is a forced `response.create`; semantic VAD was already armed, so room noise / the speaker's own echo registered as a rep turn, interrupted the greeting and triggered a second response, which re-greeted and padded.

## Phase 2 + 3: the smallest change (all in preview, nothing deployed)
- `CORE_RULES` (shared, appended to `assistant_instructions` right after the language line for BOTH engines; GPT-Live personality text is byte-identical): answer first, one or two spoken sentences for simple asks, no openers/recaps/repeated confirmations/filler/piled-on enthusiasm, one follow-up only when needed and never "anything else?", introduce yourself at most once, never narrate process or read ids/labels, respond right away and stop when interrupted, open up for detail/story/brainstorm/coaching, short by default but still warm.
- `MINI_RULES` (Mini only, placed right before the context): lead with the answer and stop; after a backend result say it once and stop; one follow-up max; never greet or restart after the first turn, "if a CONVERSATION SO FAR is given you are mid-conversation"; if a turn was silence/noise/unclear say "Go ahead" or nothing; two words at most before a backend call. `REALTIME_RULES` pre-ack trimmed from "two or three words ('one sec', 'pulling that up')" to "two words at most, if it will take a moment".
- `max_output_tokens: 1600` on Mini (~80 s of speech: room for a long read-back, a hard stop for a runaway).
- Mini opens with `turn_detection: null`; the app sends the greeting, and on that response's `response.done` clears the input buffer and switches `semantic_vad` on via `session.update` (8 s safety timer). Fresh Mini greeting instruction is now "Say exactly this and nothing more" (GPT-Live keeps "in your own words").
- Hand-off path, caps, ledger, kill switch, other accounts: untouched. Mini still receives the identical profile, tool access and 40-turn hand-off transcript.

## Phase 4: founder engine switch
Voice Pilot screen > ENGINE TEST (MY ACCOUNT): "GPT-Live first, then Mini" (default) / "Realtime Mini only". Policy field `engine_mode` on the founder's own org only (`POST /api/voice-controls/pilot/engine-mode {mode}`), `pick_engine()` returns the backup engine in `mini_only`; sessions carry `fallback_reason: mini_only`; the premium pool is never touched; backup pool, $ cap, ledger, watchdog and kill switch work exactly as before. Test: `tests/test_voice_pilot.py::test_engine_mode_mini_only`.

## Phase 5: comparison
### SIMULATED (text stand-in, NOT real OpenAI audio): `tests/voice_prompt_parity_eval.py`, full transcripts in `VOICE_MINI_PARITY_EVAL.md`
gpt-4.1-mini plays Jessi with the exact instruction strings (only the prompt differs between variants), 10 scenarios x 26 replies, gpt-5.2 judge. Costs below are ESTIMATES from speech seconds and the PRICING table.
| variant | words/reply | simple replies <= 2 sentences | questions/reply | real re-greets | filler | "anything else" | est $ / 10 scenarios | judge quality / concise / adherence / flow / context |
|---|---|---|---|---|---|---|---|---|
| mini before | 22.7 | 55% | 1.15 | 0 | 0 | 1 | $0.116 | 4.2 / 3.9 / 4.1 / 4.6 / 5.0 |
| **mini after** | **18.3** | **91%** | **0.77** | 0 | 0 | 0 | **$0.099** | **4.6 / 4.5 / 4.6 / 4.7 / 4.9** |
| live before | 21.2 | 82% | 1.15 | 0 | 0 | 1 | $0.256 | 4.0 / 3.8 / 3.8 / 4.3 / 4.9 |
| live after | 18.8 | 91% | 0.96 | 0 | 0 | 3 | $0.236 | 4.5 / 4.5 / 4.5 / 4.6 / 5.0 |
(The counter's "1 re-greet" per variant is a false positive: it matched "Hi Sarah, it's Forest" inside the text read back in scenario 10.) Mini after = Live after on every judged dimension; the brainstorm scenario still opens up (3-4 sentences), the memo/task/contact scenarios land in one sentence. Live's personality is unchanged; the shared rules made Live slightly tighter too.

### REAL OpenAI audio (your iPhone, production ledger)
Not available from preview (no OpenAI key here). The Voice Pilot screen's Recent segments show the real numbers per segment: seconds, est $, `cost_basis client_report` (token usage the app reported) for Mini vs `server_clock` for GPT-Live. Yesterday's hand-off test already produced one Live and one Mini segment; after the Mini-only test compare `est_cost_usd / billable_s` of the two kinds. Expected: Mini $0.010-0.020 per minute of conversation vs GPT-Live $0.050 flat (60-80 % lower).

## GO / NO-GO for testing Mini-only on your iPhone
**GO**, once this build is deployed and the OTA is on the phone (the greeting fix lives in the app bundle). Script: Voice Pilot > ENGINE TEST > Realtime Mini only > Talk to Jessi.
1. Opener: exactly "Hey Forest, it's Jessi. Who are we talking about today?" once, then silence until you speak. FAIL = repeated greeting or extra sentences.
2. "Save a note on Bud Carter ..." -> one-sentence confirmation of the saved facts, no follow-up question.
3. "What do I know about Sarah Mitchell?" -> the facts once, no "anything else".
4. "What day is it?" -> one sentence.
5. "Let's brainstorm referrals" -> she opens up (that is correct).
6. Talk past 10 minutes -> "Today's voice minutes are used up" (Mini pool), GPT-Live minutes still at 2:00 on the screen.
Then switch back to "GPT-Live first, then Mini" and repeat 1-3 to compare feel; the ledger rows give the real $ per minute.
NO-GO signs: any re-greeting after the first turn, a reply that keeps going past ~80 s (the cap would cut it: report it), "Could not switch the voice line" on hand-off, tool results read with names or numbers missing.

## Verification in preview
`test_voice_pilot` 6/6 (new engine-mode test), `test_live_voice` 9/9 (session contract updated: VAD off at creation, output cap, both rule blocks present), `test_voice_fallback` 6/6, `test_voice_controls` 7/7, `test_preview_only_flags` 3/3; Voice Pilot screen screenshot: engine card switches Mini-only <-> Live-first with the "next conversation starts on" line updating; forest's preview org left un-enrolled afterwards.
