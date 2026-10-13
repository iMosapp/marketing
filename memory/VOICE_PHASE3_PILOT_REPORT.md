# Voice AI Controls, Phase 3: Automatic Model Fallback. Test results and pilot GO / NO-GO (Oct 13 2026)

## What was tested

### Backend (pytest, live preview API + Mongo, zero OpenAI spend via the fake provider)
| Suite | Result | Covers |
|---|---|---|
| `tests/test_voice_fallback.py` | **6 / 6** | premium cap -> `stop` + `fallback_engine` -> app closes the old session FIRST, resumes on Realtime Mini with the conversation + pending yes/no carried in `handoff_context` ("Do not greet again"); no overlapping reservation across the switch; audit trail (`GET /api/live-voice/{id}/trail` from either end, super admin `GET /api/voice-controls/sessions/{id}/trail`) with per-engine seconds, est. cost, cost basis, handoff count; server settles a still-open premium session itself on a reconnect (`stop_reason handoff`, unused seconds released); backup exhausted -> `backup_cap` with no fallback, new starts / resumes -> 429 ("used today's Jessi voice minutes"); bypass attempts refused (reconnect churn, second device, `overrides.engine`, somebody else's session, lab session, rep editing their own allowance -> 403); kill switch (client ignoring `stop` is closed by the server after `STOP_GRACE_S`, `provider_close` hits the documented hang-up endpoints, never without a key); account-wide hard $ cap across two users and concurrent sessions (binds a super-admin-authorized override too) |
| `tests/test_voice_controls.py` | **7 / 7** | Phase 2 / 4 regression: policy + access, precedence + hard caps, day boundary per account tz, premium cap -> backup, two devices share one pool + 8-way race, watchdog, non-enrolled accounts unchanged |
| `tests/test_live_voice.py` | **9 / 9** | Live Jessi regression |

Run: `cd /app/backend && set -a && . ./.env && . ../frontend/.env && set +a && python -m pytest tests/test_voice_fallback.py tests/test_voice_controls.py tests/test_live_voice.py -q` (~75 s). Both voice suites were run twice back to back: green both times.

Fix made this session: the "resume closes the open premium session" case backdated the session by 49.5 s and the server (which truncates to whole seconds on its own clock) billed 49 s; the test now aims at the middle of the 50th second. The second failure (account hard cap expected ~70 s, got 12 s) was a cascade of the first (the aborted test left a 60 s reservation open) and passed once the first was fixed. **No server logic was changed.**

### Frontend (web, Playwright, real preview backend + fake provider; testing agent iteration_384)
Mocked: `GET /api/live-voice/config` forced to `configured: true` (preview has no `OPENAI_API_KEY`), `POST /api/live-voice/session` body enriched with `overrides.fake_provider: true`, browser WebRTC stubbed. Everything else (metering, reservations, handoff, trail) was the real server.

| Scenario | Result |
|---|---|
| A. Mid-conversation handoff (1 premium minute) | **PASS**. "Listening · gleam" -> within one heartbeat "Listening · marin · mini", note "Switched to Jessi's standard voice", cap "59 min left today on the standard voice", both caption rows preserved, timer kept counting (0:03 -> 0:06), no error / no retry button, the new data channel got the "still here" `response.create` (no re-greeting). Old session `closed` event went out BEFORE the new `POST /session`. After End: `/api/voice-controls/me` premium_left 0 / reserved 0 / backup_reserved 0, trail = 2 segments, 1 handoff, engines [live, mini], 71 s premium + 15 s mini. |
| B. Backup exhausted (premium off, 1 mini minute) | **PASS**. Conversation ends on its own: "Today's voice minutes are used up", gold **Ask Jessi by text** button (no "Talk again"), tap -> typed Ask Jessi (`/jessie`). `next_engine null`, `backup_left_s 0`. |
| C. Everything already spent before the tap | **PASS (intended UX)**. The Home card pre-reads the allowance and shows "Live Jessi is resting · All N live minutes for today are used. Back at 6:00 AM. Until then, ask me by text or voice note" and taps straight into the typed Jessi (inside the tab bar, `/(tabs)/jessi`, which re-exports the same `/jessie` screen). The server 429 remains the backstop for a stale config. |
| D. Bypass guard (API) | **PASS**. `overrides.engine: "live"` with premium spent -> 200 but `engine mini`, `fallback_reason premium_cap`; rep `PUT` on their own allowance -> 403. |

Cosmetic fixes made after the first manual run: cap text reads "Under a minute left today" below 60 s (was "0 min left today"), the total timer carries the local clock across the switch when GPT-Live sent no usage event. Naming check: no "Tok" anywhere.

Demo account kept in preview: `qa-voice-ui@invalid.imonsocial.test / VoiceRep123!` (org "QA Voice UI Org", policy on). `python tests/seed_voice_ui_demo.py --scenario handoff|exhausted|refused` resets it; `tests/voice_ui_backdater.py` ages open sessions so the cap arrives in seconds. The Test Lab flag `jessi_live_voice` was put back to `lab` and `EXPO_PUBLIC_BACKEND_URL` back to production after the run.

## What this does NOT prove yet
1. **Real providers.** Preview has no `OPENAI_API_KEY`, so the GPT-Live close, the Mini reconnect and the "still here" continuation were exercised against the fake provider and a stubbed browser WebRTC stack. The server side (metering, reservations, handoff context, trail, kill switch) is provider-independent and fully tested; the ~1-2 s audio gap during the switch and how natural the continuation sounds can only be heard in production.
2. **Native iOS.** `hooks/liveRtc.native.ts` only runs in an EAS build. The handoff reuses the microphone track across two peer connections; this is standard react-native-webrtc behaviour but was not run here (web was).
3. **Mini cost accuracy** depends on the token counts the app reports (`response.done` usage). Minutes are still metered by the server clock, so the caps hold even if an app misreports; only the $ estimate for Mini could drift. GPT-Live is costed by the server clock (never under-billed).
4. **No dashboard / no alerts yet** (Phase 5 / 7). Policies, overrides, grants and the trail are reachable only through `/api/voice-controls/*` and `/api/live-voice/admin/*`.

## GO / NO-GO
**GO for a small preview pilot (2-3 reps on ONE account, the owner included), NO-GO for turning the controls on for every account.**

Conditions for the pilot:
- Production backend deploy + EAS update (the handoff needs the new app; old apps still stop at the premium cap by themselves via `cap_left_s`, so an un-updated phone is safe, it just does not switch).
- `VOICE_FAKE_PROVIDER_ALLOWED` must NOT exist in production.
- Enrol only the pilot org: `PUT /api/voice-controls/accounts/{org} {"enabled": true, "per_user_daily_premium_min": 15, "per_user_daily_backup_min": 60, "hard_premium_cap_usd": <ceiling>}`. Every other account stays `enabled: false` (legacy behaviour, byte for byte).
- Set a `hard_premium_cap_usd` on the pilot account for the month: it binds everyone, including super admins.
- Watch for a week: `GET /api/voice-controls/accounts?range=7d` (minutes, est. cost, cap hits), `GET /api/voice-controls/ledger?org_id=...` (segments with `stop_reason`, `fallback_reason`, `unconfirmed`, `kill_attempts`). A rising count of `server_kill` or `stale_meter` rows means an app build is ignoring the stop and must be fixed before widening.
- Listen to the switch once yourself: the expected experience is a short pause, then Jessi continues the same sentence or question in the standard voice without greeting again.

Widen (more accounts) only after: zero `server_kill` rows in the pilot week, est. cost within the budget you set, and the Phase 5 dashboard exists so you are not reading JSON.
