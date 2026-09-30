# IMOS Product Rules

Non-negotiable behaviours that any change must preserve. They were established by the product owner over the
project's history (details and dates in `memory/PRD.md` and `memory/CHANGELOG.md`). When a task conflicts with one
of these, stop and ask.

## AI voice and text
1. **No em dashes or en dashes in anything AI-written** (a customer reads it as a machine). Every AI text path
   goes through `utils/text_sanitize.no_em_dash()` / `clean_ai_text(user_id)`; new AI output must too.
2. **Banned words per rep** (`persona.banned_words`) are injected into prompts and hard-stripped afterwards.
3. Jessi writes as the rep: short, specific to the thread, contractions, no lists, sparing use of the rep's
   go-to phrases. Business-mode Jessi (website widget) never says "not loaded / not on file / I need to check";
   she answers to the capability level she knows and funnels toward an appointment/demo.
4. **Mystery-shop callers stay in character** and never admit they are an AI, a recording or a shopper, even when
   asked. Reps are told practice calls are practice; covert Lead Shops tell the store nothing.
5. **Website-widget persona always discloses being an AI when asked** (Lahzo-style persona still carries the
   "AI assistant" tag; rep takeover shows "Real person").
6. A persona's voice must match its name and gender (`services/persona_gender.py` is the single resolver; a "Bill"
   never gets a woman's voice). Age labels (`young`/`older`) are flavour, never gender.
7. Practice shop calls run 10 to 13 minutes and are not cut off mid-sentence (`SHOP_MIN_MINUTES`,
   `PHONE_MAX_MINUTES`, drain-then-hangup).

## Texting and calling compliance
8. STOP/UNSTOP/HELP are honoured automatically; A2P 10DLC sending goes through the Messaging Service.
9. Automatic shops and scheduled sends never land outside 8 AM to 8 PM in the recipient's timezone; quick/manual
   actions ignore hours by design.
10. Once a web-chat booking is made, Jessi steps back (draft-only, no follow-up texts) and a human is notified.
11. Inbound calls to a business number ring the rep 18 s with press-1 screening so customers never land in the rep's
    personal voicemail; unanswered calls get the app voicemail + transcription.
12. Delivery truth: a message shows "Delivered" only on Twilio's handset receipt; failed or mocked sends are shown
    as "Never sent" with a resend action.

## Tenancy and security
13. `X-User-ID` is never trusted alone; every admin route uses the `rbac.py` dependencies; managers see only their
    store, org admins only their org, reps only their own customers. Public endpoints are tokenised.
14. Mystery Shops, Lead Shops, Test Lab, Compliance and the Challenge Library are **super_admin / iMOS admin**
    tools, never visible to dealership users.
15. Feature flags live in Test Lab (`routers/lab.py`, `settings` collection): new risky features ship as `lab`
    (super_admin only) and are released deliberately.
16. Preview-only behaviour switches must be gated on `is_preview_runtime()`; assume every `.env` key reaches
    production on Deploy (Sep 27 2026 outage lesson).

## Non-production safety
17. Never text, call or email real people from preview. Only Twilio test numbers (`+1500555xxxx`) and
    `@invalid.imonsocial.test` addresses. The super admin's real cell is on file for several buttons ("Call me",
    "Start dialing", preview call): never press them in preview.
18. Never buy Twilio numbers (`/number/buy*`, `LEAD_SHOP_BUY_NUMBERS`) or change the compliance mode away from
    `dry_run` in preview. Stripe stays in test mode.

## UX conventions
19. Every interactive/informative element has a `data-testid` (kebab-case, function not style).
20. Bottom sheets close by swipe (`SheetGrabber`); modals avoid the keyboard and text ignores the phone's font
    scaling via the Babel plugins, never by hand-editing 100 files.
21. Industry-neutral wording (offering/store) with per-industry packs; automotive is the default, equipment
    (Kubota), real estate, home services, medical, insurance, fitness, apartments and general business exist.
22. Dutch (nl-NL/nl-BE), British and Irish English locales must keep working for shop clients (relay voices,
    translated public pages).

## Process rules the owner insists on
23. Every change that touches code ends with the "Ship it" block (Save to GitHub, Deploy, the exact `eas update`
    line) so the owner never has to guess what to run.
24. Behaviour changes are recorded in `memory/PRD.md` / `memory/CHANGELOG.md` with the date.
