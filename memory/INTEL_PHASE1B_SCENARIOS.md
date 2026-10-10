# Phase 1B real-world conflict scenarios (preview database, isolated QA contacts)
Generated Oct 10, 2026 19:20 UTC. Flags: {'ingest': True, 'legacy_projection': True, 'backfill_execute': True}. Every step below went through the live ingest adapters with the compatibility projection ON; the HTTP steps hit the running preview API.
The topic / why / opening / evidence lines are built in code from the facts (deterministic Layer E). The GPT phrasing layer on top of them is a later phase; nothing here calls a model.

### 1a. Customer bought a Jeep from us (2024); it appears again on a trade appraisal today
**Latest triggering event**: Appraisal opened on the 2022 Jeep Wrangler Rubicon

**Historical relationship information (kept, never deleted)**
```
CURRENT    vehicle.purchase         2024-03-09  Bought 2022 Jeep Wrangler Rubicon
```
**Current verified facts** (confirmed by a person or the customer's own action; unconfirmed ones are marked)
```
CURRENT    vehicle.owned            2024-03-09  Owns 2022 Jeep Wrangler Rubicon
```
**Active customer intent**: none
**Recommended conversation topic**: Ownership check-in on the 2022 Jeep Wrangler Rubicon
**Why now**: No open buying signal; keep the relationship warm.
**Suggested next response**: "Hi Jenna, how is the 2022 Jeep Wrangler Rubicon treating you? Anything you need from us?"
**Next action**: Relationship touch; log anything you learn as a voice note. (mode relationship)
**Evidence**: sale:s1 @ 2024-03-09
**Legacy fields after projection**: vehicle_interest=None, vehicle_purchased='2022 Jeep Wrangler Rubicon', spouse=None, employer=None

### 1b. The Jeep is traded (appraisal desk confirms)
**Latest triggering event**: Rep confirms the trade on the vehicle page

**Historical relationship information (kept, never deleted)**
```
CURRENT    vehicle.disposed         2026-10-10  2022 Jeep Wrangler Rubicon: traded
HISTORICAL vehicle.owned            2024-03-09  Owns 2022 Jeep Wrangler Rubicon  [traded]
CURRENT    vehicle.purchase         2024-03-09  Bought 2022 Jeep Wrangler Rubicon
```
**Current verified facts** (confirmed by a person or the customer's own action; unconfirmed ones are marked)
```
(none)
```
**Active customer intent**: none
**Recommended conversation topic**: Get to know the customer
**Why now**: Nothing current on record.
**Suggested next response**: "Hi Jenna, it has been a while. What are you driving these days?"
**Next action**: Open a conversation and capture what you learn. (mode cold)
**Evidence**: none
**Legacy fields after projection**: vehicle_interest=None, vehicle_purchased='2022 Jeep Wrangler Rubicon', spouse=None, employer=None

(HTTP lead webhook -> 200)

### 2a. New website inquiry for an F-150
**Latest triggering event**: Website lead: 2025 Ford F-150 XLT

**Historical relationship information (kept, never deleted)**
```
(none yet)
```
**Current verified facts** (confirmed by a person or the customer's own action; unconfirmed ones are marked)
```
(none)
```
**Active customer intent**: 2025 Ford F-150 (active, via lead_form, 0 days since signal)
**Recommended conversation topic**: 2025 Ford F-150
**Why now**: Newest active buying signal, today via lead form (active).
**Suggested next response**: "Hi Felix, I saw your inquiry on the 2025 Ford F-150. What matters most to you in it?"
**Next action**: Reply today with one qualifying question; do not pitch anything else first. (mode active_intent)
**Evidence**: lead_form:6aca901353ff6a0ac64ccecd @ 2026-10-10
**Legacy fields after projection**: vehicle_interest='2025 Ford F-150', vehicle_purchased=None, spouse=None, employer=None

### 2b. Customer texts that they bought elsewhere
**Latest triggering event**: Inbound text: "we ended up buying a truck from another dealer"

**Historical relationship information (kept, never deleted)**
```
CURRENT    purchase.elsewhere       2026-10-10  Bought elsewhere: "Thanks for following up but we ended up buying a truck from another dealer o
HISTORICAL vehicle.interest         2026-10-10  Website lead: asked about 2025 Ford F-150  [lost]
```
**Current verified facts** (confirmed by a person or the customer's own action; unconfirmed ones are marked)
```
(none)
```
**Active customer intent**: none
**Recommended conversation topic**: They bought elsewhere; stay the trusted contact
**Why now**: Customer said today they bought somewhere else; no open buying signal.
**Suggested next response**: "Hi Felix, congrats on the new ride! No pitch here. If you ever want a second set of eyes on service or a future trade, I am around."
**Next action**: Thank them, no selling; set a 6-month ownership check-in. (mode lost)
**History worth mentioning**: Was looking at 2025 Ford F-150 in Oct 2026 (bought elsewhere)
**Evidence**: message:conv-c2 @ 2026-10-10; lead_form:6aca901353ff6a0ac64ccecd @ 2026-10-10
**Legacy fields after projection**: vehicle_interest='2025 Ford F-150', vehicle_purchased=None, spouse=None, employer=None

### 3a. Inquiry about a Tacoma a month ago
**Latest triggering event**: Website lead (30 days ago): 2024 Toyota Tacoma TRD

**Historical relationship information (kept, never deleted)**
```
(none yet)
```
**Current verified facts** (confirmed by a person or the customer's own action; unconfirmed ones are marked)
```
(none)
```
**Active customer intent**: 2024 Toyota Tacoma TRD (aging, via lead_form, 30 days since signal)
**Recommended conversation topic**: 2024 Toyota Tacoma TRD
**Why now**: Newest active buying signal, 30 days ago via lead form (aging).
**Suggested next response**: "Hi Tara, I saw your inquiry on the 2024 Toyota Tacoma TRD. What matters most to you in it?"
**Next action**: Follow up this week; the signal is aging. (mode active_intent)
**Evidence**: lead_form:6aca90137e9b715d761b6068 @ 2026-09-10
**Legacy fields after projection**: vehicle_interest='2024 Toyota Tacoma TRD', vehicle_purchased=None, spouse=None, employer=None

(HTTP lead webhook -> 200)

### 3b. New inquiry today for a Grand Highlander
**Latest triggering event**: Website lead (today): 2025 Toyota Grand Highlander

**Historical relationship information (kept, never deleted)**
```
(none yet)
```
**Current verified facts** (confirmed by a person or the customer's own action; unconfirmed ones are marked)
```
(none)
```
**Active customer intent**: 2025 Toyota Grand Highlander (active, via lead_form, 0 days since signal); also active: 2024 Toyota Tacoma TRD
**Recommended conversation topic**: 2025 Toyota Grand Highlander
**Why now**: Newest active buying signal, today via lead form (active).
**Suggested next response**: "Hi Tara, I saw your inquiry on the 2025 Toyota Grand Highlander. What matters most to you in it?"
**Next action**: Reply today with one qualifying question; do not pitch anything else first. (mode active_intent)
**Evidence**: lead_form:6aca901453ff6a0ac64cced7 @ 2026-10-10
**Legacy fields after projection**: vehicle_interest='2025 Toyota Grand Highlander', vehicle_purchased=None, spouse=None, employer=None

(HTTP personal-details edit by the rep -> 200)

### 4a. Rep typed spouse 'Sarah' and employer 'Zions Bank' on the profile (verified: a person said so)
**Latest triggering event**: Rep edits personal details

**Historical relationship information (kept, never deleted)**
```
(none yet)
```
**Current verified facts** (confirmed by a person or the customer's own action; unconfirmed ones are marked)
```
CURRENT    family.spouse            2026-10-10  Spouse: Sarah
CURRENT    work.employer            2026-10-10  Employer: Zions Bank
```
**Active customer intent**: none
**Recommended conversation topic**: Get to know the customer
**Why now**: Nothing current on record.
**Suggested next response**: "Hi Victor, it has been a while. What are you driving these days?"
**Next action**: Open a conversation and capture what you learn. (mode cold)
**Evidence**: none
**Legacy fields after projection**: vehicle_interest=None, vehicle_purchased=None, spouse='Sarah', employer='Zions Bank'

### 4b. A voice note (rep's own words, quoted) says the wife is Karen
**Latest triggering event**: Voice memo: "His wife Karen came along..."

**Historical relationship information (kept, never deleted)**
```
SUPERSEDED family.spouse            2026-10-10  Spouse: Sarah
```
**Current verified facts** (confirmed by a person or the customer's own action; unconfirmed ones are marked)
```
CURRENT    family.spouse            2026-10-10  Spouse: Karen
CURRENT    identity.neighborhood    2026-10-10  Lives in: Lehi
CURRENT    work.employer            2026-10-10  Employer: Zions Bank
```
**Active customer intent**: none
**Recommended conversation topic**: Get to know the customer
**Why now**: Nothing current on record.
**Suggested next response**: "Hi Victor, it has been a while. What are you driving these days?"
**Next action**: Open a conversation and capture what you learn. (mode cold)
**Evidence**: none
**Legacy fields after projection**: vehicle_interest=None, vehicle_purchased=None, spouse='Karen', employer='Zions Bank'

### 4c. An AI text-thread extraction guesses spouse 'Donna' with no supporting words
**Latest triggering event**: AI inference from a text thread (no quote)

**Historical relationship information (kept, never deleted)**
```
SUPERSEDED family.spouse            2026-10-10  Spouse: Sarah
```
**Current verified facts** (confirmed by a person or the customer's own action; unconfirmed ones are marked)
```
CURRENT    family.spouse            2026-10-10  Spouse: Karen
CURRENT    identity.neighborhood    2026-10-10  Lives in: Lehi
CURRENT    work.employer            2026-10-10  Employer: Zions Bank
```
**Active customer intent**: none
**Recommended conversation topic**: Get to know the customer
**Why now**: Nothing current on record.
**Suggested next response**: "Hi Victor, it has been a while. What are you driving these days?"
**Next action**: Open a conversation and capture what you learn. (mode cold)
**Needs a human**: Spouse: Donna [disputed]
**Evidence**: none
**Legacy fields after projection**: vehicle_interest=None, vehicle_purchased=None, spouse='Karen', employer='Zions Bank'

### 5a. Customer brings a 2015 Honda Civic in for an appraisal
**Latest triggering event**: Appraisal opened on a 2015 Honda Civic EX

**Historical relationship information (kept, never deleted)**
```
(none yet)
```
**Current verified facts** (confirmed by a person or the customer's own action; unconfirmed ones are marked)
```
CURRENT    vehicle.owned            2026-10-10  Owns 2015 Honda Civic EX (per appraisal record, not confirmed)  (unconfirmed)
```
**Active customer intent**: none
**Recommended conversation topic**: Confirm they still own the 2015 Honda Civic EX
**Why now**: The only ownership record comes from an appraisal; nobody has confirmed it.
**Suggested next response**: "Hi Hank, quick one: is the 2015 Honda Civic EX still yours? Want to make sure I have your garage right."
**Next action**: Ask once; confirm or dispute the ownership fact from the reply. (mode verify_ownership)
**Needs a human**: Owns 2015 Honda Civic EX (per appraisal record, not confirmed) [current, unverified]
**Evidence**: appraisal:veh-c5 @ 2026-10-10
**Legacy fields after projection**: vehicle_interest=None, vehicle_purchased=None, spouse=None, employer=None

(HTTP dispute by the owning rep -> 200)

### 5b. The rep learns it is his brother's car and disputes the ownership
**Latest triggering event**: Rep disputes the fact

**Historical relationship information (kept, never deleted)**
```
(none yet)
```
**Current verified facts** (confirmed by a person or the customer's own action; unconfirmed ones are marked)
```
(none)
```
**Active customer intent**: none
**Recommended conversation topic**: Get to know the customer
**Why now**: Nothing current on record.
**Suggested next response**: "Hi Hank, it has been a while. What are you driving these days?"
**Next action**: Open a conversation and capture what you learn. (mode cold)
**Needs a human**: Owns 2015 Honda Civic EX (per appraisal record, not confirmed) [disputed]
**Evidence**: none
**Legacy fields after projection**: vehicle_interest=None, vehicle_purchased=None, spouse=None, employer=None

### 6a. Two open inquiries: an F-150 for him, an Explorer for his wife
**Latest triggering event**: Website lead (4 days ago): 2025 Ford Explorer ST

**Historical relationship information (kept, never deleted)**
```
(none yet)
```
**Current verified facts** (confirmed by a person or the customer's own action; unconfirmed ones are marked)
```
(none)
```
**Active customer intent**: 2025 Ford Explorer ST (active, via lead_form, 4 days since signal); also active: 2025 Ford F-150 Lariat
**Recommended conversation topic**: 2025 Ford Explorer ST
**Why now**: Newest active buying signal, 4 days ago via lead form (active).
**Suggested next response**: "Hi Sam, I saw your inquiry on the 2025 Ford Explorer ST. What matters most to you in it?"
**Next action**: Reply today with one qualifying question; do not pitch anything else first. (mode active_intent)
**Evidence**: lead_form:6aca90147e9b715d761b607d @ 2026-10-06
**Legacy fields after projection**: vehicle_interest='2025 Ford Explorer ST', vehicle_purchased=None, spouse=None, employer=None

### 6b. Sold wizard records the F-150 purchase
**Latest triggering event**: Sale recorded: 2025 Ford F-150 Lariat

**Historical relationship information (kept, never deleted)**
```
CURRENT    vehicle.purchase         2026-10-10  Bought 2025 Ford F-150 Lariat
HISTORICAL vehicle.interest         2026-10-04  Website lead: asked about 2025 Ford F-150 Lariat  [purchased]
```
**Current verified facts** (confirmed by a person or the customer's own action; unconfirmed ones are marked)
```
CURRENT    vehicle.owned            2026-10-10  Owns 2025 Ford F-150 Lariat
```
**Active customer intent**: 2025 Ford Explorer ST (active, via lead_form, 4 days since signal)
**Recommended conversation topic**: 2025 Ford Explorer ST
**Why now**: Newest active buying signal, 4 days ago via lead form (active).
**Suggested next response**: "Hi Sam, I saw your inquiry on the 2025 Ford Explorer ST. Is this to replace your 2025 Ford F-150 Lariat, or an additional vehicle?"
**Next action**: Reply today with one qualifying question; do not pitch anything else first. (mode active_intent)
**History worth mentioning**: Owns 2025 Ford F-150 Lariat (recorded Oct 2026)
**Evidence**: lead_form:6aca90147e9b715d761b607d @ 2026-10-06; sale:s6 @ 2026-10-10
**Legacy fields after projection**: vehicle_interest='2025 Ford Explorer ST', vehicle_purchased='2025 Ford F-150 Lariat', spouse=None, employer=None

(HTTP personal-details edit by the rep -> 200)

### 7. A year-old call transcript (employer Zions Bank) is processed after the rep verified Intermountain Health today
**Latest triggering event**: Backlogged call transcript from 400 days ago

**Historical relationship information (kept, never deleted)**
```
HISTORICAL work.employer            2025-09-05  Employer: Zions Bank  [replaced]
```
**Current verified facts** (confirmed by a person or the customer's own action; unconfirmed ones are marked)
```
CURRENT    work.employer            2026-10-10  Employer: Intermountain Health
```
**Active customer intent**: none
**Recommended conversation topic**: Get to know the customer
**Why now**: Nothing current on record.
**Suggested next response**: "Hi Olivia, it has been a while. What are you driving these days?"
**Next action**: Open a conversation and capture what you learn. (mode cold)
**Evidence**: none
**Legacy fields after projection**: vehicle_interest=None, vehicle_purchased=None, spouse=None, employer='Intermountain Health'

## What the engine did, in one table
| # | Situation | Current truth | What history kept | Legacy field |
|---|---|---|---|---|
| 1 | Jeep bought 2024, appraised, then traded | no current vehicle; disposed record | purchase 2024, owned (historical: traded), 2 appraisal corroborations | vehicle_purchased keeps the Jeep (the purchase from us is still true); never blanked |
| 2 | F-150 inquiry, then bought elsewhere | no intent; 'bought elsewhere' record | the F-150 interest, outcome lost | vehicle_interest keeps the F-150 text (never blanked); brief says do not pitch |
| 3 | Tacoma a month ago, Grand Highlander today | Grand Highlander drives; Tacoma still active (aging) | both inquiries dated | vehicle_interest -> Grand Highlander |
| 4 | Rep typed Sarah; voice note says Karen; AI guesses Donna | Karen (newer, same reliability, quoted) | Sarah superseded; Donna waits as proposed | spouse_name -> Karen |
| 5 | Appraisal on a car that is not theirs | nothing owned | the appraisal record, disputed with the rep's note | vehicle_purchased never written |
| 6 | F-150 + Explorer open, F-150 bought | owns F-150; Explorer still active | F-150 interest closed as purchased | vehicle_interest -> Explorer, vehicle_purchased -> F-150 |
| 7 | Old call says Zions after rep verified Intermountain | Intermountain Health | Zions Bank as historical (replaced) | employer unchanged |
