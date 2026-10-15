# Jessi Mini: Voice Quality & Disconnect Fixes — Preview Report (Oct 15 2026)

PREVIEW ONLY. Not deployed, no OTA. Models, prices, daily allowances and Premium (GPT-Live) behaviour unchanged.
Audit: `JESSI_MINI_VOICE_STABILITY_AUDIT.md`.

## Root cause (from the audit, production data)
- **Cut-offs:** the app's 15 s quiet timer (`useLiveJessi.ts` `resetIdle`) restarted only on caption / speech-start events. On Mini, caption text arrives ahead of the audio and nothing arrives while the rep talks, so the 15 s ran out while Jessi was still speaking, while the rep was mid-sentence, or during a lookup. 17 of 31 Mini sessions ended "idle"; 0 of 33 Premium sessions did.
- **Name repetition:** the prompt line shared by both engines, "Use their first name now and then, not every sentence." Mini over-applies it (31% of replies after the greeting vs 8% on Premium), mostly as the first word ("Got it, Forest.").

## Files changed
| File | Change |
|---|---|
| `backend/services/live_voice.py` | `REP_NAME_HINT` (same sentence, now a constant). `MINI_NAME_RULES`. `mini_instructions()` drops the hint and adds the rules (not in shopper mode). `REALTIME_RULES`: "keep every **customer** name and number". `_answer(mini=True)`: no addressing by name or "great question". `close_diag()` whitelist; `record_events` stores `close_diag` + one `[Live] closed ...` log line; `serialize` exposes it |
| `frontend/hooks/miniQuiet.ts` (new) | What counts as quiet (audio / turn / lookup events), hint / warning / end levels |
| `frontend/hooks/useLiveJessi.ts` | Mini: quiet never hangs up early (hint, warning, calm end). Lookup tracking. `keepGoing()`. Close diagnostics (`closeDiag`, `stopBy`, AppState). Mini tool-result wrapper "keep every customer name and number, don't add the rep's name". Premium path unchanged |
| `frontend/components/jessi/LiveJessiSheet.tsx`, `LiveJessiPill.tsx`, `LiveJessiProvider.tsx` | "Still here, take your time" status; "Still there? Closing in N s · Keep going" button (`live-jessi-keep-going`); pill line; new end text `away` |
| Tests | `backend/tests/test_mini_voice_quality.py` (6), `backend/tests/voice_name_use_eval.py` (stand-in eval), `frontend/scripts/sim-mini-lifecycle.js` (19 mocked scenarios on the real hook) |

## New prompt instructions (Mini only)
Removed from Mini's assembled prompt: "Use their first name now and then, not every sentence."
Added (`MINI_NAME_RULES`):
> NAMES: you may say the rep's first name once, in your greeting. After that, leave it out. Never start a reply with it, and never use it as filler, for emphasis or in an acknowledgment ('Absolutely, [name]', 'Great question, [name]', 'You got it, [name]'). Say it again only for a real reason, like getting their attention after a long silence. This is only about addressing the rep: when you read back a drafted text or a quote that contains their name, read it exactly as written. Customer and contact names are different: use those whenever they make the answer clearer. Sound like a person on a call, not a script: start with the answer itself rather than an acknowledgment, and don't open two replies in a row the same way ('Absolutely', 'Got it', 'Perfect', 'Okay so'). Your personality, humor and tone stay exactly as described above.

Tool results: "SAY THIS TO THE REP in your own voice, keep every customer name and number, don't add the rep's name, add nothing: ..."
Unchanged: personality sliders, the owner's notes, the greeting ("Hey {first}, ..." = the one name use), all of GPT-Live's prompt. No text replacement on replies.

## New quiet / idle behaviour (Mini only)
- Quiet = nobody talking and no lookup running: Jessi's audio (`output_audio_buffer.started` -> `stopped/cleared`), the rep's speech (`speech_started` -> `speech_stopped`), a reply being made, a lookup in flight. Any of these, or a caption, restarts it. Each "busy" flag expires after 60-90 s, so a lost event can't keep a session open forever.
- At `idle_close_s` (production 15 s): **no disconnect**. The status just reads "Still here, take your time".
- At **120 s of true quiet**: "Still there? Closing in 30 s · Keep going" (sheet button; tapping the pill also keeps it going).
- At **150 s of true quiet**: a calm end, reason `away` ("Closed after 2 minutes of quiet"). Nobody is talking at that moment, so nothing is cut off.
- Coming back to the app counts as activity (no instant end after a long background).
- Unchanged: End button (mic, peer connection and audio session released once), daily allowance (client timer + server heartbeat stop), server kill / stop, OpenAI's limits, all cost accounting. No reconnects; no new provider sessions.
- **Owner decision built in on best judgment:** the 2-minute + 30 s backstop. It lets a quiet session stay open up to 2.5 min instead of 15 s, which uses up to about 2.5 allowance minutes per forgotten session. Change it before deploy if you prefer 5 min or none.

## Close diagnostics (no transcript or audio)
Stored on the session as `close_diag` and logged as one line: `initiated_by` (user / app / server / provider / network), `unexpected`, `pc_state`, `ice_state`, `dc_state`, last provider event type and age, last audio event type and age, `quiet_s`, app state and background count, app build. Session id, model, duration and reason are already on the session row. A provider-ended call (events channel closed while WebRTC is still connected) is now told apart from a network drop. The reason stays `connection_lost` for compatibility; `initiated_by` tells them apart.

## Test results
| Test | Result |
|---|---|
| Mocked lifecycle on the real hook (`node frontend/scripts/sim-mini-lifecycle.js`) | **19/19 pass**: one greeting / one session; 40 s silence stays live; 60 s + 110 s pauses survive; rep talks 30 s; 30 s answer not cut and no hint while she speaks; 30 s lookup; interruption; forgotten session warns, Keep going resets, ends `away` at 150 s; End releases everything once (diag `user`); allowance `backup_cap` at 90 s as before; server stop (diag `server`); provider end vs network told apart; lost audio event doesn't stick; backgrounding counted; 200 s background resume doesn't insta-end; **Premium still closes idle at 15 s (unchanged)**; no extra sessions; failed lookup clears its flag |
| Before-fix replay (`/app/test_reports/mini_lifecycle_sim.json`) | old code cut off at 4.5 s after an answer, mid-answer, mid-rep-speech and mid-lookup |
| Backend `test_mini_voice_quality.py` + `test_live_voice.py` + `test_voice_controls.py` + `test_voice_fallback.py` | 6 new + 24 existing pass |
| Guard scripts `check-mini-opening.ts`, `check-mini-captions.ts` | pass (no duplicate greeting, events acted on once) |
| **Name use, text-model stand-in** (gpt-4.1-mini on the Emergent key, exact Mini prompts, production sliders, 3 conversations x 3 runs, **81 post-greeting replies per variant**, about $0.05) | **before 19.8% -> after 0.0%** replies addressing the rep by name; "Got it, Forest"-style openers 6 -> 0 with the name; customer names kept 100%; drafted texts containing "it's Forest" read back 6/6 (`/app/memory/VOICE_MINI_NAME_EVAL.json`). Stand-in, not the realtime model: confirm in production (below) |
| Testing agent (iteration_395) | all pass; 1 UI bug found (pill kept "Closing in 0 s" after an `away` end), fixed and covered by sim #8 |
| TypeScript | 248 before and after (no new errors) |
| Paid live Mini test | not run (no OpenAI key in preview) |

## Cost impact
- Mini is billed per token: silence, the hint and the warning add **no tokens** (the warning is on screen, not spoken). Prompt +~110 tokens per session, cached on later turns (cached text $0.06 per 1M), well under $0.0001 per conversation. Shorter, name-free openers trim a little audio output.
- Allowance minutes: a forgotten Mini session can now stay open up to 2.5 min (was 15 s). Real conversations that used to be cut off now continue, which uses the minutes they were meant to use. Allowances, caps and the $25/month hard cap are unchanged.
- Premium: unchanged.

## Is an OTA required?
- **Prompt / name fix: backend only.** It applies to every installed app as soon as the backend is deployed. The small tool-wrapper wording also ships in the app (OTA).
- **Quiet timer, warning UI, close diagnostics: app JavaScript, so an OTA (`eas update`).** No native or App Store build is needed.
- Compatible in both orders: an old app with the new backend keeps the old 15 s behaviour and sends no diagnostics; a new app with the old backend still works, and its diagnostics are simply ignored.

## Production recommendation
1. Deploy the backend (name fix + diagnostics storage). Check `/api/health` and one owner Mini conversation.
2. Publish the OTA (quiet timer + warning + diagnostics).
3. After about a week of normal use, re-run the read-only production count. Targets: Mini replies after the greeting with the name **< 5%** (was 31%), and `idle` ends on Mini ~0 (was 55%). Then read `close_diag` for any remaining unexpected ends.
4. iPhone checks (owner): a lookup question and a long "walk me through today" answer (no cut-off); a 30 s pause (stays, "Still here"); leave it 2 min (warning, then a calm end); tap End (mic indicator goes off); Wi-Fi to cellular; lock screen 30 s.
