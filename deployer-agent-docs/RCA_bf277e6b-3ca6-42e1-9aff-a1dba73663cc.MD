# Mini duplicate-greeting investigation — read-only DB report

DB: imos-admin-test_database · collection: live_sessions · engine="mini" · READ-ONLY (no deploys/writes). 26 Mini sessions total.

## Identity finding
The "three two-assistant-row sessions (22:12 / 23:07 / 23:08 UTC)" ARE the same three docs as the three named live_ids — not six distinct sessions:
- 1bc8319dc49c = started 2026-10-14T22:12:02.254Z
- fff25ee9ff71 = started 2026-10-14T23:07:50.009Z
- 1799c361ce2b = started 2026-10-14T23:08:20.951Z

## Target sessions (1–4)
All three: delegations=[] (empty); voice=marin; config.greeting="Hey {first}, Who are we talking about today?"; config.mini_voice=marin. Both transcript rows are role=assistant with identical text "Hey Forest, who are we talking about today?" (pattern A,A). No rep/user turn; audio_in=0; text_in=424.

| live_id | sec | close_reason | audio_in | text_in | audio_out | text_out | cost_usd | started_at | ended_at |
|---|---|---|---|---|---|---|---|---|---|
| 1bc8319dc49c | 13 | close_requested | 0 | 424 | 97 | 47 | 0.0023 | 22:12:02.254Z | 22:12:17.197Z |
| fff25ee9ff71 | 9 | close_requested | 0 | 424 | 105 | 79 | 0.0025 | 23:07:50.009Z | 23:08:01.205Z |
| 1799c361ce2b | 3 | close_requested | 0 | 424 | 124 | 94 | 0.0030 | 23:08:20.951Z | 23:08:25.656Z |

Transcript start_ms/end_ms (both assistant rows):
- 1bc8319dc49c: row1 314–695, row2 818–924
- fff25ee9ff71: row1 270–480, row2 764–965
- 1799c361ce2b: row1 359–603, row2 1076–1348

## Contrast sessions starting A→R (5)
326b4dbb17ed (10-13 23:52) and 368d9f938ba6 (10-14 19:23). Both voice=marin, greeting="Hey {first}, Who are we talking about today?", mini_voice=marin.

| live_id | sec | close_reason | audio_in | text_in | audio_out | text_out | cost_usd | started_at | ended_at |
|---|---|---|---|---|---|---|---|---|---|
| 326b4dbb17ed | 25 | close_requested | 56 | 5169 | 729 | 352 | 0.0191 | 23:52:09.863Z | 23:52:36.932Z |
| 368d9f938ba6 | 37 | idle | 90 | 2918 | 457 | 272 | 0.0128 | 19:23:13.758Z | 19:23:52.337Z |

Delegations:
- 326b4dbb17ed: [recall_person, args{name:"Travis Bonino"}, ms 4322, at 23:52:20.824, result="Travis Bonino owns Salsalitos and Soul Cantina in South Jordan. You know him personally from Harley riding about six years ago, and you're warm with him; he and his spo…"]
- 368d9f938ba6: [find_mentions, args{days:0, query:"in the market for a Harley-Davidson / interested in a Harley"}, ms 6393, at 19:23:34.688, result="15 people match harley davidson motorcycle. Forest Ward, tagged Harley Rider. Matthew Easton, tagged Harley Rider. Jessi Ward, tagged Harley Rider. And 12 more on y…"]

Transcript 326b4dbb17ed: assistant "Hey Forest, Who are we talking about today?" (319–525); rep "Yeah, Travis Bonino." (1884–4998); assistant "Got it, one second, I'm pulling that up." (5030–5270); assistant full recall readout (10363–13578).
Transcript 368d9f938ba6: assistant greeting (290–504); rep "Yeah, can you..." (3747–7093); rep "Tell me who I know that..." (6619–9415); rep "is potentially in the market for a Harley-Davidson." (8867–13045); assistant "Give me a moment to check who mentioned a Harley." (13034–13294); assistant "You've got 15 people matched…" (20453–22337).

## Delegation-during-greeting count (6)
14 of 26 Mini sessions have ≥1 delegation. first delegation at − started_at:
- d264ce3ef1d2: 3.04s ; dcc7358d9c9f: 3.28s ; all other 12: ≥10.9s (range 11.0–35.2s).
- Sessions with first delegation within 3.00s of started_at: **0**.
- Of those, starting with two assistant rows: **0 (n/a)**.

Caveat: the two closest narrowly exceed 3s. d264ce3ef1d2 (gap 3.04s) itself is an A,A two-assistant-row duplicate-greeting session (2 rows only). A 3.5s window would change the answer to 1 / 1. Strict 3.00s = 0/0.

## Interpretation
The duplicate-greeting symptom = the assistant greeting row is emitted twice back-to-back (A,A) with no user turn in between, 0 audio_in, text_in pinned at 424 (prompt only). It is NOT accompanied by a delegation during the greeting window (all delegated sessions call tools well after the greeting, ≥3s, mostly ≥10s). So "function call during greeting" and "duplicate greeting" are disjoint in this dataset.
