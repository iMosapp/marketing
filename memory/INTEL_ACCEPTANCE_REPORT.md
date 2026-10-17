# Living Relationship Intelligence - Phase 1A acceptance journeys

Generated Oct 17, 2026 01:41 UTC by tests/test_contact_intelligence.py (no model calls; the status engine, intent windows and rules-based next action are exercised directly).

## 1. Existing customer submits a new inquiry about a different product

Jan 2024 Wrangler purchase, Jun 2025 'larger vehicle' call, Mar 2026 'not shopping' text, then the F-150 form. The newest active signal drives; nothing is deleted.

**Previous state**
- Driving intent: none
- Suppression: none
- Owns: Jeep Wrangler
- Facts: 4 (2 current, 2 historical, 0 to verify)

**New event**: Website form (Oct 9 2026): information about a Ford F-150

**Updated facts (all facts after the event)**
```
CURRENT    vehicle.purchase         2024-01-14  Bought Jeep Wrangler
CURRENT    vehicle.owned            2024-01-14  Owns Jeep Wrangler
HISTORICAL vehicle.interest         2025-06-03  Considering a larger vehicle
CURRENT    buying.status            2026-03-11  Not currently shopping: "We're not currently shopping, thanks though"
CURRENT    vehicle.interest         2026-10-16  Website lead: asked about Ford F-150
```
**Retained history**: 1 historical/superseded fact(s) kept, nothing deleted.
**Active intent**: Ford F-150 (active, via lead_form)
**Recommended next action** (active_intent): Reply today with one qualifying question; do not pitch anything else first.
- Topic: Ford F-150
- Why: Newest active buying signal, yesterday via lead form (active).
- Opening: "Hi John, I saw your inquiry on the Ford F-150. Is this to replace your Jeep Wrangler, or an additional vehicle?"
- History worth mentioning: Owns Jeep Wrangler (recorded Jan 2024)
**Supporting evidence**: lead_form:6ad2d233bfd05bd70989f7dd @ 2026-10-16; sale:p1 @ 2024-01-14

## 2. Customer trades a previously owned vehicle

**Previous state**
- Driving intent: none
- Suppression: none
- Owns: 2021 Honda Pilot
- Facts: 2 (2 current, 0 historical, 0 to verify)

**New event**: Appraisal desk confirms the 2021 Honda Pilot was traded

**Updated facts (all facts after the event)**
```
CURRENT    vehicle.purchase         2021-05-02  Bought 2021 Honda Pilot
HISTORICAL vehicle.owned            2021-05-02  Owns 2021 Honda Pilot
CURRENT    vehicle.disposed         2026-10-15  2021 Honda Pilot: traded
```
**Retained history**: 1 historical/superseded fact(s) kept, nothing deleted.
**Active intent**: none
**Recommended next action** (cold): Open a conversation and capture what you learn.
- Topic: Get to know the customer
- Why: Nothing current on record.
- Opening: "Hi Tina, it has been a while. What are you driving these days?"
**Supporting evidence**: none

## 3. Customer changes their phone number

**Previous state**
- Driving intent: none
- Suppression: none
- Owns: nothing on record
- Facts: 0 (0 current, 0 historical, 0 to verify)

**New event**: Rep edits the contact: phone +18015550111 -> +18015550222

**Updated facts (all facts after the event)**
```
SUPERSEDED contact.phone            2024-04-30  Phone: +18015550111
CURRENT    contact.phone            2026-10-17  Phone: +18015550222
```
**Retained history**: 1 historical/superseded fact(s) kept, nothing deleted.
**Active intent**: none
**Recommended next action** (cold): Open a conversation and capture what you learn.
- Topic: Get to know the customer
- Why: Nothing current on record.
- Opening: "Hi Paul, it has been a while. What are you driving these days?"
**Supporting evidence**: none

## 4. A salesperson records a voice note containing new customer information

**Previous state**
- Driving intent: none
- Suppression: none
- Owns: nothing on record
- Facts: 0 (0 current, 0 historical, 0 to verify)

**New event**: Voice memo transcript -> extracted spouse, kid, interest, employer (rep's own words, each with the quoted sentence)

**Updated facts (all facts after the event)**
```
CURRENT    family.spouse            2026-10-16  Spouse: Mark
CURRENT    family.kid               2026-10-16  Kid: Max (age 7, soccer)
CURRENT    preference.interest      2026-10-16  Interest: camping
CURRENT    work.employer            2026-10-16  Employer: Hill AFB
```
**Retained history**: 0 historical/superseded fact(s) kept, nothing deleted.
**Active intent**: none
**Recommended next action** (cold): Open a conversation and capture what you learn.
- Topic: Get to know the customer
- Why: Nothing current on record.
- Opening: "Hi Vicky, it has been a while. What are you driving these days?"
**Supporting evidence**: none

## 5. Customer contradicts an earlier statement

The 4Runner interest became history (declined). The not-shopping statement held until the customer's own new action superseded it.

**Previous state**
- Driving intent: Toyota 4Runner (aging)
- Suppression: none
- Owns: nothing on record
- Facts: 1 (1 current, 0 historical, 0 to verify)

**New event**: Text 5 days ago: 'not in the market anymore, hold off' -> suppression; then today a website inquiry for a Grand Highlander

**Updated facts (all facts after the event)**
```
HISTORICAL vehicle.interest         2026-09-27  Website lead: asked about Toyota 4Runner
SUPERSEDED buying.status            2026-10-12  Not currently shopping: "Hey, we're not in the market anymore, we decided to hold off"
CURRENT    vehicle.interest         2026-10-17  Website lead: asked about Toyota Grand Highlander
```
**Retained history**: 2 historical/superseded fact(s) kept, nothing deleted.
**Active intent**: Toyota Grand Highlander (active, via lead_form)
**Recommended next action** (active_intent): Reply today with one qualifying question; do not pitch anything else first.
- Topic: Toyota Grand Highlander
- Why: Newest active buying signal, today via lead form (active).
- Opening: "Hi Nora, I saw your inquiry on the Toyota Grand Highlander. What matters most to you in it?"
**Supporting evidence**: lead_form:6ad2d233bfd05bd70989f801 @ 2026-10-17

## 6. Customer submits multiple inquiries about different products

**Previous state**
- Driving intent: Chevrolet Silverado 2500 (active)
- Suppression: none
- Owns: nothing on record
- Facts: 1 (1 current, 0 historical, 0 to verify)

**New event**: Second website inquiry (Tahoe) three days after the Silverado inquiry

**Updated facts (all facts after the event)**
```
CURRENT    vehicle.interest         2026-10-14  Website lead: asked about Chevrolet Silverado 2500
CURRENT    vehicle.interest         2026-10-17  Website lead: asked about Chevrolet Tahoe
```
**Retained history**: 0 historical/superseded fact(s) kept, nothing deleted.
**Active intent**: Chevrolet Tahoe (active, via lead_form); also active: Chevrolet Silverado 2500
**Recommended next action** (active_intent): Reply today with one qualifying question; do not pitch anything else first.
- Topic: Chevrolet Tahoe
- Why: Newest active buying signal, today via lead form (active).
- Opening: "Hi Mia, I saw your inquiry on the Chevrolet Tahoe. What matters most to you in it?"
**Supporting evidence**: lead_form:6ad2d233bfd05bd70989f80b @ 2026-10-17

## 7. Historical information becomes relevant again

The 2025 towing question is surfaced as history worth mentioning; the Silverado ownership shapes the opening line.

**Previous state**
- Driving intent: none
- Suppression: none
- Owns: 2023 Chevrolet Silverado 1500
- Facts: 3 (3 current, 0 historical, 0 to verify)

**New event**: Website inquiry today for an F-250 after a dormant 2025 F-250/camper conversation

**Updated facts (all facts after the event)**
```
CURRENT    vehicle.purchase         2023-04-10  Bought 2023 Chevrolet Silverado 1500
CURRENT    vehicle.owned            2023-04-10  Owns 2023 Chevrolet Silverado 1500
SUPERSEDED vehicle.interest         2025-07-08  Asked about towing a camper with a Ford F-250
CURRENT    vehicle.interest         2026-10-17  Website lead: asked about Ford F-250 Super Duty
```
**Retained history**: 1 historical/superseded fact(s) kept, nothing deleted.
**Active intent**: Ford F-250 Super Duty (active, via lead_form)
**Recommended next action** (active_intent): Reply today with one qualifying question; do not pitch anything else first.
- Topic: Ford F-250 Super Duty
- Why: Newest active buying signal, today via lead form (active).
- Opening: "Hi Hank, I saw your inquiry on the Ford F-250 Super Duty. Is this to replace your 2023 Chevrolet Silverado 1500, or an additional vehicle?"
- History worth mentioning: Asked about Ford F-250 in Jul 2025 (replaced); Owns 2023 Chevrolet Silverado 1500 (recorded Apr 2023)
**Supporting evidence**: lead_form:6ad2d233bfd05bd70989f817 @ 2026-10-17; message:msg-250708 @ 2025-07-08; sale:p7 @ 2023-04-10

## 8. Duplicate forms or webhook events arrive

**Previous state**
- Driving intent: none
- Suppression: none
- Owns: nothing on record
- Facts: 0 (0 current, 0 historical, 0 to verify)

**New event**: The same website lead delivered twice (same lead id)

**Updated facts (all facts after the event)**
```
CURRENT    vehicle.interest         2026-10-17  Website lead: asked about Kia Telluride
```
**Retained history**: 0 historical/superseded fact(s) kept, nothing deleted.
**Active intent**: Kia Telluride (active, via lead_form)
**Recommended next action** (active_intent): Reply today with one qualifying question; do not pitch anything else first.
- Topic: Kia Telluride
- Why: Newest active buying signal, today via lead form (active).
- Opening: "Hi Dup, I saw your inquiry on the Kia Telluride. What matters most to you in it?"
**Supporting evidence**: lead_form:6ad2d233bfd05bd70989f81d @ 2026-10-17

## 9. Older events arrive after newer events

**Previous state**
- Driving intent: none
- Suppression: none
- Owns: nothing on record
- Facts: 1 (1 current, 0 historical, 0 to verify)

**New event**: A year-old call transcript (employer Zions Bank) is processed after last week's memo (Intermountain Health)

**Updated facts (all facts after the event)**
```
HISTORICAL work.employer            2025-09-12  Employer: Zions Bank
CURRENT    work.employer            2026-10-14  Employer: Intermountain Health
```
**Retained history**: 1 historical/superseded fact(s) kept, nothing deleted.
**Active intent**: none
**Recommended next action** (cold): Open a conversation and capture what you learn.
- Topic: Get to know the customer
- Why: Nothing current on record.
- Opening: "Hi Olivia, it has been a while. What are you driving these days?"
**Supporting evidence**: none

## 10. AI lacks confidence and requests verification

Identity-like guesses wait for a human (proposed); the rep's 'Dana' stays current. Low-stakes guesses are kept but marked low confidence.

**Previous state**
- Driving intent: none
- Suppression: none
- Owns: nothing on record
- Facts: 1 (1 current, 0 historical, 0 to verify)

**New event**: Text-thread extraction guesses spouse 'Donna' and interest 'golf' without those words in the thread

**Updated facts (all facts after the event)**
```
CURRENT    family.spouse            2026-09-17  Spouse: Dana
CURRENT    preference.interest      2026-10-16  Interest: golf
```
**Retained history**: 0 historical/superseded fact(s) kept, nothing deleted.
**Active intent**: none
**Recommended next action** (cold): Open a conversation and capture what you learn.
- Topic: Get to know the customer
- Why: Nothing current on record.
- Opening: "Hi Vera, it has been a while. What are you driving these days?"
- Needs verification: Spouse: Donna [disputed]
**Supporting evidence**: none

## 11. Customer has simultaneous active opportunities

Only the F-150 interest closes (purchased); the Explorer opportunity stays active.

**Previous state**
- Driving intent: Ford Explorer (active)
- Suppression: none
- Owns: nothing on record
- Facts: 2 (2 current, 0 historical, 0 to verify)

**New event**: Sold wizard records the 2026 F-150 XLT purchase

**Updated facts (all facts after the event)**
```
HISTORICAL vehicle.interest         2026-10-11  Website lead: asked about Ford F-150
CURRENT    vehicle.interest         2026-10-13  Website lead: asked about Ford Explorer
CURRENT    vehicle.purchase         2026-10-17  Bought 2026 Ford F-150 XLT
CURRENT    vehicle.owned            2026-10-17  Owns 2026 Ford F-150 XLT
```
**Retained history**: 1 historical/superseded fact(s) kept, nothing deleted.
**Active intent**: Ford Explorer (active, via lead_form)
**Recommended next action** (active_intent): Reply today with one qualifying question; do not pitch anything else first.
- Topic: Ford Explorer
- Why: Newest active buying signal, 4 days ago via lead form (active).
- Opening: "Hi Sam, I saw your inquiry on the Ford Explorer. Is this to replace your 2026 Ford F-150 XLT, or an additional vehicle?"
- History worth mentioning: Owns 2026 Ford F-150 XLT (recorded Oct 2026)
**Supporting evidence**: lead_form:6ad2d233bfd05bd70989f837 @ 2026-10-13; sale:p11 @ 2026-10-17

## 12. Two customers share a phone number

Facts attach to the contact id (one per store); the API resolves the contact through the caller's data filter so store B never sees store A's facts.

**Previous state**
- Driving intent: none
- Suppression: none
- Owns: nothing on record
- Facts: 0 (0 current, 0 historical, 0 to verify)

**New event**: Store A receives a lead for its customer; store B's customer with the same phone gets nothing

**Updated facts (all facts after the event)**
```
```
**Retained history**: 0 historical/superseded fact(s) kept, nothing deleted.
**Active intent**: none
**Recommended next action** (cold): Open a conversation and capture what you learn.
- Topic: Get to know the customer
- Why: Nothing current on record.
- Opening: "Hi Shared, it has been a while. What are you driving these days?"
**Supporting evidence**: none

## 13. New intelligence arrives while a campaign is active

The enrollment document is untouched: intelligence never changes campaign state on its own.

**Previous state**
- Driving intent: Ram 1500 (aging)
- Suppression: none
- Owns: nothing on record
- Facts: 1 (1 current, 0 historical, 0 to verify)

**New event**: Campaign text goes out (no effect on the window); the customer replies 'still interested, come by Saturday' (score 8)

**Updated facts (all facts after the event)**
```
CURRENT    vehicle.interest         2026-09-27  Website lead: asked about Ram 1500
CURRENT    buying.signal            2026-10-17  Buying signal 8/10: wants to visit Saturday
```
**Retained history**: 0 historical/superseded fact(s) kept, nothing deleted.
**Active intent**: wants to visit Saturday (active, via message); also active: Ram 1500
**Recommended next action** (active_intent): Reply today with one qualifying question; do not pitch anything else first.
- Topic: wants to visit Saturday
- Why: Newest active buying signal, today via message (active).
- Opening: "Hi Cam, thanks for reaching out. Buying signal 8/10: wants to visit Saturday. What would be most helpful right now?"
**Supporting evidence**: message:conv1 @ 2026-10-17

## 14. Similar customer records exist in different dealership tenants

Both stores have a 'John Smith'. Store B's John gets his legacy spouse 'Ann' and a dormant Honda Accord interest (300 quiet days -> historical, went quiet); store A's John has no facts yet.

**Previous state**
- Driving intent: none
- Suppression: none
- Owns: nothing on record
- Facts: 0 (0 current, 0 historical, 0 to verify)

**New event**: Backfill dry run per store, then a controlled execute for store B only

**Updated facts (all facts after the event)**
```
HISTORICAL vehicle.interest         2025-12-21  Interested in Honda Accord (legacy field)
CURRENT    family.spouse            2026-10-16  Spouse: Ann
```
**Retained history**: 1 historical/superseded fact(s) kept, nothing deleted.
**Active intent**: none
**Recommended next action** (cold): Open a conversation and capture what you learn.
- Topic: Get to know the customer
- Why: Nothing current on record.
- Opening: "Hi John, it has been a while. What are you driving these days?"
- Needs verification: Spouse: Ann [current]
**Supporting evidence**: none
