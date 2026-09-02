# Jessi AI Routing - Rules of the Road (READ BEFORE TOUCHING ai_reply.py / twilio_webhooks.py / messages.py)

The app is LIVE. Every regression here reaches real customers and the user's phone. In June 2026 a
chain of "small" routing edits broke push notifications and auto-confirmed appointments. Never again.

## The state machine (routers/ai_reply.py queue_ai_reply)
Order of checks, first match wins:
1. `users.ai_master_paused` (Home AI switch)      -> silent + "AI is paused" notification/push
2. `ai_assist_mode == off`                          -> silent (caller already notified)
3. `conversations.ai_paused_for_human`             -> silent, re-asserts needs_assistance=True (never drops out of Waiting)
4. AI suspicion ("are you a robot?")                -> brief reply + PAUSE + You're Needed push
5. Fact question (price/stock/color/model/finance)  -> brief "let me check" + PAUSE + You're Needed push
   - exception: live inventory match answers price/stock/color questions (NEVER finance/trade/payment)
6. Scheduling (time/day/visit)                      -> Jessi DRAFTS, requires_approval=True, Waiting, ONE "Approve Jessi's reply" push
   - carry-over: while a held draft is pending, every follow-up is held too
7. Otherwise                                        -> normal auto reply (or draft/approval per mode)

Keyword matching is WHOLE-WORD (`_has_phrase`). Never go back to `sig in msg_lower`
("vin" matched "having"/"Kevin", "lease" matched "please", "apr" matched "April").

## Invariants (each has a test in backend/tests/ai_routing_matrix.py)
- Pause is lifted ONLY by: rep manual reply, All Good, AI off/on, 3-day expiry job. NOT by a happy "ok thanks".
- All Good never changes ai_mode. Jessi keeps replying afterwards.
- AI off cancels every pending queue item for that conversation (nothing stale can send later).
- Scheduler cancels a queued AI reply if the rep replied after it was queued (`rep_replied`).
- Silence follow-ups skip paused convs, convs with a held draft, and master-paused reps.
- Exactly one push per scheduling hold. Fact path pushes once from ai_reply; the webhook's
  per-message "{name} replied" push is separate and intentional (worked for months, leave it).
- No em dashes in any user-facing string (titles, pushes, banners). Use " - ".

## Before you finish ANY change in these files
```
cd /app/backend && python tests/ai_routing_matrix.py      # must print N/N passed
```
It builds a throwaway user/contact/conversation, stubs the LLM, push and Twilio, cancels every queued
item, and deletes its data. Add a case for every new rule. If it cannot express your change, extend it.

Never simulate the Twilio webhook with forest's real numbers in preview - it fires REAL SMS
(the You're Needed urgent SMS goes to his personal cell, the AI reply to the "customer").
