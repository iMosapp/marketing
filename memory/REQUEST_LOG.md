# Request Log

Your exact words, in order, and where each one stands. Newest at the bottom. Updated by the agent at the end of every task.
Legend: DONE = built + verified in preview · DEPLOY = needs backend deploy and/or `eas update` to reach production · USER = waiting on something only you can do.

---

### 1 · Oct 3 — DONE
> Jesus where are these old logos coming from??? Current logo is this one [screenshot of imonsocial.com header]

Canonical logo is `logo.png` (white tile). Old `imos-logo.png` / `imos-wordmark.png` deleted from `public/`, `build/`, `build-preview/`. `/mybaby` and `/card` fixed.

### 2 · Oct 3 — DONE
> For fuck sakes! Put the white tile around behind it like it's always been! Dont touch anything else besides this one presentation

Reverted the deck to the white-tile `logo.png`.

### 3 · Oct 3 — DONE
> Get ride of the scroll or use arrows thing that's gay

Removed the "Scroll or use arrow keys" hint from the cover slide.

### 4 · Oct 3 — DONE
> the start conversation should pull up a web form to submit a lead to me

Modal lead form (Name*, Company, Email*, Phone, Message) posting to `POST /api/demo-requests` with `source: platform_overview_cta`.

### 5 · Oct 3 — DONE
> slide 6 needs to be changed from any talk of raising money or needing capital.. the is just the story of my platform and it should focus more on just a go to market strategy which is where I am at now. I want to be able to show this to anyone to give the history of what I have built over the last 8 months

Slide 6 rewritten as go-to-market (5 pillars). All capital language removed.

### 6 · Oct 3 — DONE
> lets take 8 months out and say something like 30 years of experience has shaped what is missing in the market.. a tool designed by a high tech redneck to help the life blood of every company.. the salesman
>
> or something like that.. make it better

Headline: "Thirty years on the sales floor. One tool built for the people on it." + high-tech redneck / salesperson copy.

### 7 · Oct 3 — USER
> ok so this project should be connected to two specific repos in github and it's not wired right.. how do i make sure the right repos are associated to the right projects? don't change anything just report back what I need to do

Report delivered (from support): push the monorepo to `imonsocial-clone`; point Vercel's Root Directory at `marketing/`; one job pushes to one repo per Save.

### 8 · Oct 3 — USER
> so it got blocked becasue of this: [GitHub push-protection error: "Stripe Test API Secret Key … backend/.env.example:123 / :125"]

It was a dummy `sk_test_xxx…` placeholder, not a real key. Placeholders changed to `<your-stripe-secret-key>` so it can't trip again. You still need to click GitHub's unblock link once (old commit still contains it), then push.

### 9 · Oct 3 — DONE
> I watched the full recording. This is substantially better than I expected. It looks like an investor microsite/deck rather than a normal marketing page, which is exactly right for /mybaby. [full reviewer feedback: reorder Problem → insight → built → does → scale → moat → recreate → founder → distribution → ask; compress metrics; "Six systems… One relationship layer connecting all of them"; move the Relationship Intelligence Engine earlier; "Every interaction makes the next interaction smarter"; rename Replacement Cost → Estimated equivalent build cost; soften competitor claim; founder slide "Most sales systems are built around managing the pipeline…"; add an evidence slide BUILT → DEPLOYED → USED; add a final NOW WE SCALE IT page with "We aren't raising capital to find out whether this can be built. We're raising capital to determine how fast it can be distributed."]
>
> this is the new /mybaby marketing page

Your choices: investor ask only on `/mybaby?investor=1`; live numbers from a public stats endpoint; no revenue. Deck restructured to that order.

### 10 · Oct 3 — DONE
> We don't have any numbers populating slide seven or whatever, so that API obviously isn't working right. Let's either dummy up numbers or get rid of it altogether. And let's not reference iMOS ever. It's I'm On Social

Evidence slide removed (endpoint `GET /api/public/platform-stats` kept for later). Every "IMOS" → "i'M On Social".

### 11 · Oct 3 — DONE
> why is the chat widget not on this page? how do we install it?

One script tag: `<script src="https://app.imonsocial.com/api/w/XkTvZEUb.js" async></script>`. Added to the deck. Still missing on: date-triggers, calendar-systems, training, demo, reviews, help, landing, outreach.

### 12 · Oct 3 — DONE
> also lets get rid of the page numbers save as pdf etc across the top

Top bar removed. Progress line, side dots and arrow keys stay; Cmd/Ctrl+P still prints all slides.

### 13 · Oct 3 — DONE / DEPLOY
> When we are hunting for tags or intel and it pulls up the screen sometimes it's a bit glitchy and if I have more than what is on the screen it doesn't tell me details. I'd like this to work a bit better than it does

Root cause: the screen re-ran the whole AI search after Jessi already had the list. Now her exact list renders instantly; "keep going / who else / read the rest / read them all" walks the full list; "pull up the fourth one" resolves correctly; result cap 40 → 150.

### 14 · Oct 4 — DONE / DEPLOY
> As a store manager I want to be able to get a daily digest from Jessi.. so think this: I'm on my way to work and I ask Jessi who has my team been working with that I should have them follow up on today.. it goes through the whole team and gives me people each team member can work on.. so I'm in the loop on every salesperson

Team Today: Jessi tools `team_today` / `nudge_rep`, screen with per-rep follow-ups + Nudge buttons, `GET /api/team-today`, `POST /api/team-today/nudge`.

### 15 · Oct 4 — DONE / DEPLOY
> OK, so with this last update, I pushed to have a manager ask about their team and what they have going on. I'm very concerned about the data. It's telling me that Kira has context to follow up with that are actually my contacts and one of the messages was a birthday message, but the person's birthday is in April. How do we get to the bottom of what's going on here?

Root cause: birthday/anniversary/sold-date automations picked contacts with the manager-wide data filter (whole store/org — whole DB for super admins). Fixed in 5 code paths. Added owner flags, "Where did they come from?" screen, and Stop-all for a rep's automations on other reps' customers. Existing leaked enrollments in production must be stopped from that screen.

### 16 · Oct 5 — DONE / DEPLOY
> So let's make this All Tools button Instead of having all the tiles, let's clean it up and make it look like the dropdown under my profile. I love how that looks. It's super clean on a computer screen, which is what I gave you a screenshot. Let's go through one last time an organization on that All Tools. When I click that, have it be a nice, easy, clean screen with everything organized and bucketed correctly on where it should live. [screenshots of the profile dropdown]
>
> i'm not sure I want this option to be a way to view them still but I want to be able to switch between views primarily because it looks so much better on a browser.
>
> add the internet leads box under leads
>
> use your best justjment for organization. you know the things I talk to you about the most. Think of this as my full admin dashboard for my internal team. I will upload an example of how I have been managing anoterh admin dashboard
>
> these [screenshots of the Calldrip admin dashboard: left sidebar with collapsible groups, "Press / to search"]

List/Tiles toggle (remembered per user), 12 groups, sidebar + detail layout on computer, single column on phone, Internet Leads under Leads.

### 17 · Oct 5 — DONE / DEPLOY
> also ONLY send the text out to me with the people stuck in setup for jessi onboarding.. other users are getting it and they shouldn't be

Recipients limited to super admins (`digest_roles` config). Preview DB: 22 → 1.

### 18 · Oct 5 — DONE / DEPLOY
> stuck in setup needs to ONLY go to me not other super admins.. how do I toggle other super admins off?

Jessi Onboarding → gear → Morning digest → "Who gets the morning text": on/off switch per super admin.

### 19 · Oct 5 — answered
> ok now show me where to find this setting to turn everyone else off!

Home → avatar → All tools → Account Management → Onboarding Hub (or Admin Dashboard → Jessi Onboarding) → gear → Morning digest. Web: `app.imonsocial.com/admin/onboarding-jessi`.

### 20 · Oct 5 — DONE
> how would I go about finding the last 5 things I've asked you to do? I want to keep a log of these for myself so I can compair it to what has been done already and what I need to do?

This file.

### 21 · Oct 5 — DONE
> does it have my exact full prompt I gave you?
>
> yes

Switched the log to your verbatim words (this version). Earlier sessions can't be recovered word-for-word; they were summarized before this fork.

### 22 · Oct 5 — DONE / DEPLOY
> and I want this log to push into my super admin panel also but only visible to me not all super admins. tell me how I should structure the super admin settings since there are things I only want to see but not let other super admins see? Do I only user super admin setting for me? I don't know the best way to do this
>
> is_owner flag · That list is right · An "Owner" settings screen where you tick, per tool, whether other super admins can see it

Owner layer: `is_owner` flag on your account (set from `OWNER_EMAIL`), **Request Log** screen in the admin panel (All tools → Internal Operations, and your profile dropdown), **Owner Settings** screen with a switch per internal tool for what other super admins can see (Request Log, Billing & Revenue, Revenue Forecast, Partner Agreements, White Label Partners, Discount Codes and the digest switches are hidden by default) plus an Owners list to promote someone you trust. Production needs `OWNER_EMAIL` set in the backend env.

---

## Still open (from earlier sessions, paraphrased — originals not recoverable)
- Portability Step 2: swap `emergentintegrations` for the official OpenAI/Stripe SDKs — **waiting for your explicit go-ahead**.
- Portability Steps 3–4: object storage → S3, MongoDB → Atlas.
- CRM adapters: HubSpot two-way sync, then Salesforce / Zoho / Pipedrive.
- UI simplification Stages 4–5 (design-system pass, Contacts/Tasks polish).
- Dutch translation of the internal app UI.

## Ideas you liked but haven't green-lit
- Morning push to managers that opens straight into Jessi reading Team Today.
- "Text them all" / "Save as group" from a Jessi hunt result.
- Store-wide sweep that stops every rep's foreign automations in one tap.
- Chat widget on the 8 remaining marketing pages.
