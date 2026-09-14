# i'M On Social: Shared Inboxes, Internet Leads and Lead Workflows

Setup guide for store managers and admins. Every screen below is reached from the **Tools** tab (bottom bar).

## How the pieces fit

```
Lead provider / website form / Zapier
        │  (webhook, ADF XML, or email)
        ▼
  LEAD SOURCE  ─── "lands in" ───►  SHARED INBOX  (one number + the team that works it)
        │                                  │
        └──── Response Workflow / Lead Flow ┘
              (intake text, who rings in what order, after-hours rule, Jessi)
                                  │
                                  ▼
        Reps' phones ring → first to press 1 (or tap Claim) owns the lead
        Thread lives in Inbox → Team Inbox / Leads until it is closed or handed to a rep's own line
```

- **Shared Inbox** = the number customers text or call, plus the people who work it. This is the single "team" definition: whoever is on the inbox can see, get pinged on, and claim the leads that land there.
- **Lead Source** = one feed of leads (Cars.com, website form, Facebook, Zapier). It points at ONE inbox.
- **Response Workflow** = what happens the second a lead arrives. Configure it directly on the source, or build a reusable **Lead Flow** once and attach it to many sources.

---

## Part 0: Prerequisites (do these first)

| Check | Where | Why |
|---|---|---|
| Every rep has a **cell number** on their profile | Tools → Account Management → Users (or the rep's My Profile) | The call ladder rings this number. No cell = that rep is skipped. |
| Every rep has a **texting number** assigned | Tools → Account Management → Phone Assignments | Claimed leads graduate to the rep's own line. |
| **Store hours** are set | Tools → Account Management → Stores → your store | After-hours rule and "opens at" timing use these. |
| Reps set **My Schedule** (optional) | More → My Schedule | Off-shift reps are skipped for pushes when at least one rep is on shift. If nobody is on shift, everyone is pinged so a lead is never dropped. |
| A Twilio number for the inbox that is **not** a rep's personal line | Tools → Account Management → Twilio Numbers | The inbox number cannot double as someone's rep line. |

---

## Part 1: Set up a Shared Inbox

**Path:** Tools → Manage → **Inboxes** → **Create your first inbox** (or the + button).

### Step 1: Setup tab
1. **Name** (for example "Sales Internet", "Service BDC").
2. **What it's for** (optional): shows on every thread so reps know which hat they are wearing.
3. **Number**: pick the Twilio number customers will text. Replies always go out from this number while the thread lives in the inbox.
4. **Routing** (how a new customer who texts in is assigned):
   - **First to claim** (jump ball): everyone is pinged, first tap owns it.
   - **Take turns** (round robin): the next rep in line gets it.
   - **Weighted turns**: round robin weighted by the rep's share.
   - **Daily cap per rep** (0 = none): once a rep hits the cap today, new customers skip to the next rep.

### Step 2: Team tab
1. Members are grouped **ON <STORE NAME> · N**. Tap **Everyone on the team** to check them all, or tap individuals.
2. Super admins and org admins can expand **Show others** and search for people not on this store. Adding someone from there **also puts them on this store's team** (you will see a toast "N added to <store>'s team").
3. Tap **Create**. You land on the **Leads** tab.

### Step 3: Leads tab ("Is this team wired up?")
This is the checklist that tells you if leads will actually reach the team:
- **Number**: the inbox has a texting number.
- **Team**: at least one member.
- **Members without a number / without a cell**: fix in Part 0 or those people cannot be rung.
- **Lead sources that land here**: if empty you will see "No lead source points here yet". Tap **Point a lead source here** and pick one (or create one in Part 2 and choose this inbox).
- **Ringing**: per source you see who rings ("everyone", "some", "others", "none", or "text only"). Tap the gold **Ring everyone on this inbox** button on a source to make attempt 1 ring the whole team, and to keep ringing new hires without touching it again.
- **Jessi**: whether the assistant is on for this inbox.

### Step 4: Jessi tab (optional)
- **Instant first reply**: sent the moment a brand-new customer texts this number. Blank = nothing automatic.
- **Assistant name**, **What she should know**, **Rules she must follow**, **Hand to a human when**.

### Step 5: Closing tab (optional)
- **When a contact gets this tag, the thread is done being shared** (for example "Sold").
- **Bridge text from the rep's line**: the customer's first text from the rep's own number so they save it.

### Test the inbox (5 minutes)
1. From your own cell, **text the inbox number**.
2. Open **Inbox** tab → tap the **Team Inbox** chip. The thread should appear as up-for-grabs (First to claim) or already assigned (Take turns).
3. If you set an instant first reply, your cell receives it within seconds.
4. Every member on the inbox should get a push. Tap **Claim** on one phone: it disappears from everyone else's grabs list.
5. Reply from the app. The text arrives on your cell **from the inbox number**, not the rep's line.
6. Tap the gold **Rules & team** button in the chip row to jump back to the inbox's Leads tab any time.

---

## Part 2: Receive internet leads (Lead Sources)

**Path:** Tools → Leads → **Lead Source Config** → **+** (New Lead Source).

### Step 1: Create the source
1. **Source name**: one source per feed ("Cars.com", "Website Form", "AutoTrader"). One source per feed keeps Proof (cost per sale) honest.
2. **Assign to team**: pick the shared inbox from Part 1. This is the "lands in" link.
3. **Assignment method**: Jump Ball, Round Robin or Weighted Round Robin (used when a lead is assigned rather than rung).
4. **Create**. You land on the source page with its credentials.

### Step 2: Connect the provider (pick the one that matches how leads are delivered)

| How the provider sends leads | Use this | What to give the provider |
|---|---|---|
| **Posts ADF/XML directly** (Cars.com, AutoTrader, CarGurus, OEM portals) | **ADF / XML URL** (tap to copy) | The URL. No key needed. |
| **Emails ADF leads** (most CRM-style feeds) | **Email Lead Intake** URL | Create a free inbound address on **CloudMailin** or **SendGrid Inbound Parse**, point it at this URL, then give the provider that email address. ADF is auto-extracted from the body or attachments. |
| **Website form / JSON** (your site, custom dev) | **Webhook URL** + **API Key** (`X-API-Key` header) | Copy the **Example Request** on the page. `phone` is the only required field; `name`, `email`, `notes` are optional. |
| **Zapier / Make / any app** | Tools → Leads → **Connect Zapier / Make** | Pick the source; the page shows the field names to use as Data keys and says **"Listening for your test..."** until your first post arrives. |

Also on the source page:
- **LANDS IN SHARED INBOX**: switch the inbox later without recreating the source. "No inbox (reps below only)" means only the reps checked in the workflow see it.
- **Active** toggle: a paused source rejects posts.

### Test the source (before touching the workflow)
1. **Fastest:** scroll to **Send a test lead** on the source page. Enter **your own cell** as the customer phone, leave the ladder box unchecked for now, tap **Send test lead**, then tap again to confirm. The contact is tagged "Test Lead" and stays out of Proof.
   - The result card shows: Intake text sent now / held until <time>, Jessi on/off, Store open/closed, N reps pushed.
2. **From the provider side:** send a real test from the portal or Zap, or run the curl in Example Request with `"is_test": true` added to the JSON body.
3. Confirm it landed: Tools → Leads → **Lead Source Queue** shows the lead with the first-text status: **SENT** went out, **QUEUED** is waiting for store hours or the texting window, **FAILED** could not deliver (bad number or opt-out).
4. Confirm the team sees it: **Inbox → Leads** shows it as WAITING (nobody has claimed it yet). Everyone on the inbox should have a push.

---

## Part 3: Set up the workflow (who gets texted, who rings, when)

You can configure this in two places. They have the same controls:
- **On the source:** Lead Source Config → open the source → **Response Workflow** section → **Save Workflow**. Good for one-off sources.
- **As a reusable Lead Flow:** Tools → Leads → **Lead Flows** → **Start a new flow** (from a proven template or blank). Then on each source, tap **Use a flow from the library** in the Response Workflow section. Edit the flow once and every source using it updates. Recommended once you have more than one source.

### Step 1: Instant intake text
- **Instant Intake Text**: sent to the lead the moment it arrives (inside the texting window). Tap a merge field to insert it (first name, vehicle, rep name, store).
- **What are these leads asking about?** (optional): context so Jessi answers in the right lane.
- **After-hours version**: used instead of the intake text when the store is closed. Blank = same text.
- **"Just tried you" text**: sent automatically after a call attempt goes unanswered.
- The text goes out **from the inbox number** when the source lands in an inbox, so the customer's reply comes back to the whole team.

### Step 2: Who gets the push
- **Notify these reps (first to reply claims the lead)**: everyone checked is pushed the second the lead lands. When the source lives in a shared inbox, **everyone on that inbox is pinged too**, automatically.

### Step 3: Customer contact
- **Text only**: no phones ring; reps claim from the push or the Leads list.
- **Text + Call**: the **call ladder** rings reps and bridges the first one to press 1 to the customer.

### Step 4: The call ladder (Text + Call only)
Each **attempt** is a rung: who rings, then how long to wait before the next rung.
1. Attempt 1: tap the gold **Everyone on <inbox>** chip to ring the whole inbox team (this follows the roster, so new hires ring without editing), or pick specific reps.
2. **Text first, ring after**: Same moment / 15 / 30 / 45 / 60 s. The customer sees your text before phones ring. The rung is skipped if a rep already claimed or texted in the meantime.
3. Add attempt 2, 3... with different reps or managers. "Pick at least one rep or this attempt is skipped."
4. **Caller ID when ringing reps** (Lead Flows): the number the rep sees, and the customer sees on the bridged call.
5. **When nobody answers**: after the last rung rings out, alert the managers. The lead always stays in the shared queue.
6. **When a rep claims**: **Claim = call me** (auto-dials the rep and bridges) and **Tags to add** (tag workflows run too, so a "Working" tag can start its campaign).

### Step 5: After store hours
- **Text + Jessi, ring at opening** (default): customer gets the after-hours text, Jessi answers replies, the ladder fires when the store opens.
- **Ring reps anyway**.
- **Texting Window (TCPA)**: Federal 8 AM to 9 PM or Strict states 9 AM to 8 PM, in the **customer's** time zone. Texts outside the window are held and sent at the window start.

### Step 6: Returning customers
- A lead whose number already belongs to one of your reps normally goes **straight to that rep** (text only, no ring).
- **Quiet for N days** (14/30/60/90): if that rep has no sale and nothing has happened in N days, the lead goes back to the team and the old rep gets a quiet "lead reopened" note. "Always their rep" turns this off.

### Step 7: Jessi and the queue
- **Enable AI Auto-Reply (Jessi)**: she answers the customer's replies until a human claims.
- **VA Profile for this source** (optional) and **Custom Instructions**.
- **Lead Queue Timers**: turns amber after / turns red after / alert managers after / release to queue after (an unclaimed or ignored lead is released back to everyone).
- **Daily Manager Report** toggle.

Tap **Save Workflow** (or **Save** on the flow).

### Test the workflow (10 minutes, use two phones if you can)
1. On the source page, **Send a test lead** with **your cell** as the customer and **Ring the call ladder too** checked. Tap twice to confirm.
2. Within a few seconds:
   - Your cell gets the intake text (or the result card says it is held until the window/opening).
   - Every rep in attempt 1 gets a push and their **cell rings** (after the ring delay you set).
3. On a rep's phone, answer and **press 1**. That rep is bridged to your cell (the "customer"). Everyone else's ring stops.
4. Reply from your cell. The reply lands in the thread, Jessi stays quiet because a human owns it.
5. Open the thread in **Inbox → Leads**. The **lead timeline** at the top shows every step: text sent, who rang at what time, who claimed, or "Text first, phones ring 30 s later" and "Forest's customer, sent straight to Forest" for returning customers.
6. Let a second test ring out with nobody answering: confirm the "Just tried you" text arrives, the ladder moves to attempt 2, and managers get the alert after the last rung.
7. Tools → Leads → **Call Retries** shows the retry timing report; **Lead Source Queue** shows the text statuses.
8. Re-send a test lead for the same number later: the thread flips back to WAITING as a brand-new lead (expected).

---

## Part 4: One-page test matrix

| Flow | Do this | Expect | Where to confirm |
|---|---|---|---|
| Inbox texting | Text the inbox number from your cell | Thread appears under Team Inbox, instant reply arrives, members pushed | Inbox → Team Inbox chip |
| Inbox claim | Tap Claim on one phone | Gone from other phones' grabs list; replies go out from the inbox number | Your cell shows the inbox number as sender |
| Source intake | Send a test lead (ladder off) | Result card: text sent/held, N reps pushed | Lead Source Queue → SENT / QUEUED |
| Provider connection | Real test from portal / Zap / curl | Lead row appears, tagged with the source | Lead Source Queue, Connect Zapier page stops "Listening" |
| Ladder ringing | Send a test lead (ladder on) | Attempt-1 phones ring after the delay | Rep phones, thread timeline |
| Press 1 claim | Answer and press 1 | Bridged to the customer, others stop | Thread timeline shows the claim |
| No answer path | Let it ring out | "Just tried you" text, next attempt, manager alert | Thread timeline, Alerts |
| After hours | Send a test lead when the store is closed | After-hours text, Jessi replies, ladder held until opening | Result card "rings at <time>" |
| Returning customer | Test lead from a number already owned by a rep | Goes straight to that rep, no ring | Timeline: "<Rep>'s customer" |
| Inbox checklist | Open inbox → Leads tab | Everything green, every source shows who rings | Inboxes → your inbox → Leads |

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| A rep never rings | No cell on their profile, not in the attempt, or not on the inbox team | Add their cell; use "Everyone on <inbox>" on attempt 1; check the inbox Team tab |
| "Members without a cell" on the checklist | Same as above | Fix profiles, the checklist clears itself |
| Text says QUEUED | Outside the customer's texting window or store closed with the default after-hours rule | Normal; it sends at window start / opening. Use Ring reps anyway if you want calls after hours |
| Nothing rings but the text went out | Source is Text only, or the ladder has no reps | Switch Customer Contact to Text + Call and fill attempt 1 |
| Reps outside the source's list cannot see the lead | The source is not pointed at their inbox | Set LANDS IN SHARED INBOX on the source |
| Leads go to one rep, skipping the team | Returning-customer rule (the number already belongs to that rep) | Expected; lower "quiet for N days" or set the flow to send stale ones back to the team |
| Provider posts rejected | Source is paused, or wrong/missing X-API-Key | Turn the source Active; copy the key from the source page |
| Calls flagged "Carrier spam filter declined" | The number ringing reps is toll-free (8xx) or flagged | Use a local caller ID; see Number Health notes |
| Rep gets pushes at night | They have no My Schedule set | Have them set work hours and quiet times in More → My Schedule |
