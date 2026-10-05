# Request Log

What Forest asked for, in order, and where it stands. Newest at the bottom. Updated by the agent at the end of every task.
Legend: DONE = built + verified in preview · DEPLOY = needs backend deploy and/or `eas update` to reach production · USER = waiting on something only you can do.

| # | Date | What you asked | Status | Notes |
|---|------|----------------|--------|-------|
| 1 | Oct 3 | Fix the old logos that resurfaced on the `/mybaby` deck and `/card` page | DONE | Canonical logo is `logo.png` (white tile). Old `imos-*` files deleted. |
| 2 | Oct 3 | Remove "Scroll or use arrow keys" hint from the deck | DONE | |
| 3 | Oct 3 | "Start a conversation" should open a lead form, not email | DONE | Posts to the same pipeline as the /demo page. |
| 4 | Oct 3 | Slide 6: no raising-money talk, make it go-to-market; then "30 years / high-tech redneck" copy | DONE | |
| 5 | Oct 3 | Report on how to wire the right GitHub repos (no changes) | USER | Push the monorepo to `imonsocial-clone`; point Vercel Root Directory at `marketing/`. |
| 6 | Oct 3 | GitHub push blocked by "secret" in `.env.example` | USER | It was a dummy `sk_test_xxx` placeholder; placeholders fixed. You still need to click GitHub's unblock link once, then push. |
| 7 | Oct 3 | Restructure the deck per the reviewer's feedback; investor "ask" only on `?investor=1`; live-usage slide | DONE | Live slide later removed at your request (#8). |
| 8 | Oct 3 | Numbers weren't populating; drop the slide; never say "IMOS" | DONE | `/api/public/platform-stats` endpoint still exists if you want the slide back after deploy. |
| 9 | Oct 3 | Add the chat widget to the deck; remove the top bar (page numbers / Save as PDF) | DONE | 8 other marketing pages still have no widget: date-triggers, calendar-systems, training, demo, reviews, help, landing, outreach. |
| 10 | Oct 3 | Jessi tag/intel hunt is glitchy; doesn't give details past what's on screen | DONE / DEPLOY | Screen now shows Jessi's exact list instantly; "keep going" reads the rest; cap raised to 150. |
| 11 | Oct 4 | Manager morning digest: "who has my team been working with…" | DONE / DEPLOY | Team Today screen + Jessi tools `team_today` / `nudge_rep`. |
| 12 | Oct 4 | Kira's list shows YOUR contacts incl. a wrong-month birthday text — get to the bottom of it | DONE / DEPLOY | Root cause: date/birthday automations ran on the manager-wide data view. Fixed 5 code paths. "Where did they come from?" screen + Stop-all button. Existing leaked enrollments must be stopped from that screen. |
| 13 | Oct 5 | All Tools: make it a clean list like the profile dropdown, keep tiles as an option, Internet Leads under Leads | DONE / DEPLOY | List/Tiles toggle, 12 groups, sidebar layout on computer. |
| 14 | Oct 5 | Stuck-in-onboarding text: only to you, not other users / other super admins | DONE / DEPLOY | Jessi Onboarding → gear → "Who gets the morning text" switches. |
| 15 | Oct 5 | Keep a log of what I've asked vs. what's done | DONE | This file. |

## Still open (from earlier sessions)
- Portability Step 2: swap `emergentintegrations` for the official OpenAI/Stripe SDKs — **waiting for your explicit go-ahead**.
- Portability Steps 3–4: object storage → S3, MongoDB → Atlas.
- CRM adapters: HubSpot two-way sync, then Salesforce / Zoho / Pipedrive.
- UI simplification Stages 4–5 (design-system pass, Contacts/Tasks polish).
- Dutch translation of the internal app UI.

## Ideas you liked but haven't green-lit
- Morning push to managers that opens straight into Jessi reading Team Today.
- "Text them all" / "Save as group" from a Jessi hunt result.
- Store-wide sweep that stops every rep's foreign automations in one tap.
