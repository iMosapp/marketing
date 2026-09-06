"""June 2026 refresh of the in-app training that ships with the product.

Applied once per environment by `apply_training_refresh()` (versioned in app_meta), so production picks it up on the
first Training Hub / SOP request after deploy. Lessons describe the app as it is today: Tools (not "More"), Jessi,
Alerts, the rep-first Home, Share the App, one Phone Numbers screen.
"""
from datetime import datetime, timezone

CONTENT_VERSION = 3
APP_STORE_URL = "https://apps.apple.com/us/app/im-on-social/id6774618559"


def _now():
    return datetime.now(timezone.utc)


SALES_TEAM_TRACK = {
    "slug": "sales-team",
    "title": "Sales Team Onboarding",
    "description": "Eight short lessons. Finish them on day one and you will know exactly what to tap tomorrow morning.",
    "icon": "briefcase",
    "color": "#C9A962",
    "roles": ["user", "manager", "admin", "store_manager", "org_admin", "super_admin"],
    "order": 1,
    "lessons": [
        {
            "slug": "first-15-minutes", "title": "Your First 15 Minutes", "icon": "rocket", "duration": "5 min", "order": 1,
            "description": "Activate, log in, and set up the profile customers will see.",
            "content": (
                "## Your First 15 Minutes\n\n"
                "Your manager created your account. You got a text and an email with the App Store link and three steps. Here they are again.\n\n"
                "### 1. Install and activate\n"
                f"1. Install **i'M On Social** from the App Store: {APP_STORE_URL}\n"
                "2. Open the app and tap **Activate my account** under the login button.\n"
                "3. Enter the mobile number your manager put on your account. We text you a 6-digit code.\n"
                "4. Enter the code, choose a password, tap **Activate & Log In**.\n\n"
                "No text? The number your manager typed must match your phone. Ask them to check it under Tools > Set Up > Team Members.\n\n"
                "### 2. Say yes to notifications\n"
                "When iPhone asks, tap **Allow**. Every hot shopper, reply and reminder comes through here. You can quiet them at night later (Settings > Notifications).\n\n"
                "### 3. Make your profile customer-ready (2 minutes)\n"
                "Tap **Tools** (bottom right) > your name at the top > **Profile**.\n"
                "- Photo: a clear headshot, no sunglasses.\n"
                "- Title and store.\n"
                "- Bio: two sentences about you. Customers read this on your card.\n\n"
                "This one profile powers your Digital Card, Link Page, Landing Page and Showcase. Change it once, it updates everywhere.\n\n"
                "### 4. Look at your card\n"
                "Tools > **My Brand** > **My Digital Card**. That is what a customer sees when you text them your card. Fix anything that looks off.\n\n"
                "You are ready. Tomorrow morning, open the app and do what the Home screen says."
            ),
            "steps": ["Install from the App Store link in your welcome text", "Tap Activate my account, enter your mobile number, enter the code, set a password", "Allow notifications", "Tools > Profile: add photo, title and a two-sentence bio", "Tools > My Brand > My Digital Card: check how you look"],
        },
        {
            "slug": "home-three-cards", "title": "Home: Your Day in Three Cards", "icon": "home", "duration": "4 min", "order": 2,
            "description": "Do This Next, Your 3 for Today, Needs a Reply. That is the whole job.",
            "content": (
                "## Home: Your Day in Three Cards\n\n"
                "Home is built so you never wonder what to do. Top to bottom:\n\n"
                "### Do This Next\n"
                "One action, already chosen for you: a customer to text, a review to ask for, a lead to call. Tap the gold button to do it, or **Skip** if today is not the day.\n\n"
                "### Your 3 for Today\n"
                "Three people worth a 30-second text, with the reason: back from a trip, birthday Friday, left a review, bought a year ago. Each card has:\n"
                "- **Text** (or Call): opens a message we already wrote from what you know about them. Edit it, send it.\n"
                "- **Check**: mark it done if you handled it another way.\n"
                "- **X**: skip for today.\n\n"
                "Finish all three and your streak grows. Streaks are how managers see who is working their book.\n\n"
                "### Needs a Reply\n"
                "Conversations waiting on you. A red **WAITING** badge means Jessi stepped back and the customer is waiting for a human. Tap the row, read, reply. **Open Inbox** shows everything.\n\n"
                "### The gold + button\n"
                "Always in the corner: **SOLD!** (log a sale), **Make a Call**, **Voice Note**, **Send Photo**, **Calendar**.\n\n"
                "### Top of the screen\n"
                "- **QR icon**: your card as a QR code for a customer to scan.\n"
                "- **AI ON**: Jessi is answering your texts. Tap to pause her for everyone.\n"
                "- **Bell**: Alerts. Every push notification you get lands here too.\n\n"
                "That is it. Three cards, one button. If you clear the three cards and the inbox, you are done with the app for the morning."
            ),
            "steps": ["Open the app, do the Do This Next action", "Work Your 3 for Today: Text, Check or X on each", "Clear Needs a Reply, WAITING rows first", "Log any sale with the gold + then SOLD!"],
        },
        {
            "slug": "meet-jessi", "title": "Meet Jessi, Your AI Assistant", "icon": "sparkles", "duration": "5 min", "order": 3,
            "description": "Jessi answers your texts 24/7 in your voice and hands off when a human is needed.",
            "content": (
                "## Meet Jessi\n\n"
                "Jessi is the assistant that lives on your business number. When a customer texts and you do not answer within a couple of minutes, she does, sounding like you, using what is on your profile and in the store's inventory.\n\n"
                "### What she does on her own\n"
                "- Replies to inbound texts within seconds, day or night.\n"
                "- Answers inventory questions with real vehicles, photos and a lot link from the store feed.\n"
                "- Books appointments and puts them on your calendar.\n"
                "- Sends your review link and digital card when it fits.\n\n"
                "### When she hands off to you\n"
                "Jessi steps back and you get a **You're Needed** alert when the customer asks for pricing or payments, asks for a person, gets frustrated, or says something she should not guess at. The conversation shows a red **WAITING** badge until you reply.\n\n"
                "Open the thread. The gold banner says **Jessi is handling this** with two buttons:\n"
                "- **Take Over**: you reply yourself and Jessi stays quiet on this customer. When you are done, tap **Resume AI** to hand it back.\n"
                "- **All Good**: the customer only said thanks or ok. Clears the WAITING flag, Jessi keeps going.\n\n"
                "### Pausing her\n"
                "- Everyone: tap **AI ON** on Home. It turns to **AI PAUSED**. Tap again to resume.\n"
                "- One customer: open the thread and tap **Take Over**.\n\n"
                "### Teaching her to sound like you\n"
                "Tools > **Settings** > **My VA**. Add how you talk, what you know, your hobbies. Then tap **Hear Your VA in Action** and read a sample reply. If it is not you, edit and try again. Five minutes here pays off every day.\n\n"
                "### Ask her anything\n"
                "Tools > Today > **AI Follow-ups** shows who she thinks you should reach out to and why."
            ),
            "steps": ["Tools > Settings > My VA: fill in how you talk and what you know", "Tap Hear Your VA in Action and read the sample", "On Home, find the AI ON toggle and know where it is", "Open a WAITING thread, tap Take Over, reply, then tap Resume AI"],
        },
        {
            "slug": "inbox-fast", "title": "Inbox: Reply Fast", "icon": "chatbubbles", "duration": "4 min", "order": 4,
            "description": "Tabs, thread actions, templates and photos.",
            "content": (
                "## Inbox: Reply Fast\n\n"
                "The **Inbox** tab is every text conversation on your number.\n\n"
                "### Filters (left to right)\n"
                "- **Hot**: buying signals detected (test drive, trade-in, financing, ready to buy).\n"
                "- **Waiting**: Jessi handed off, customer is waiting on you. Start here.\n"
                "- **Unread**: new customer texts.\n"
                "- **All**: everything.\n"
                "- **AI**: Jessi is handling these. Skim them once a day.\n"
                "- **Active**: assigned to you and moving along.\n"
                "- **Closed**: done.\n\n"
                "### Inside a thread\n"
                "- Type and send. Photos: the camera icon, or tap **Send Photo** from the gold + on Home to pick a lot photo.\n"
                "- Header buttons: **Call** and **Voice Note** (the mic; say what you learned and the app remembers it).\n"
                "- Templates: tap the document icon to drop in a saved text (Tools > Settings > My Templates).\n"
                "- Tap the customer's name to open their contact card.\n"
                "- Back on the Inbox list, the **...** on a row gives you **Task**, **Tag** and **Close**.\n\n"
                "### Speed matters\n"
                "Reply time is one of the numbers your manager sees. Jessi covers you, but a WAITING row is a real person expecting you. Aim for under five minutes during your shift.\n\n"
                "### Closing\n"
                "When a deal is done or dead, tap **Close**. Closed threads still keep the history; they just stop cluttering your list."
            ),
            "steps": ["Open Inbox and tap the Waiting filter", "Reply to one thread, then use the ... menu on its row to add a Task", "Save one template you send every day (Tools > Settings > My Templates)", "Close one finished conversation"],
        },
        {
            "slug": "contacts-book", "title": "Contacts and Your Book of Business", "icon": "people", "duration": "5 min", "order": 5,
            "description": "Add people, talk to the app after a sale, and let it remember for you.",
            "content": (
                "## Contacts and Your Book of Business\n\n"
                "The **Contacts** tab is your book. Every person you sell to, plus the family, hobbies and dates that make the next conversation easy.\n\n"
                "### Adding people\n"
                "- **+** on the Contacts tab: name and phone is enough.\n"
                "- **Import**: bring your iPhone or Google contacts in one shot. Contacts > Import Contacts walks you through exporting a file and uploading it.\n"
                "- Texts from new numbers create a contact automatically.\n\n"
                "### After a sale: talk, do not type\n"
                "Tap the gold + then **Voice Note**, pick the customer, and say what you learned:\n"
                "*\"Closed with Steve and Michelle, daughter starts at Utah State, headed to Lake Powell next month, Steve rides a Harley, Michelle's birthday is October 3.\"*\n\n"
                "The app turns that into memory chips (spouse, kids, hobbies, dates) and follow-ups (\"Ask Steve how Lake Powell was\"). Those show up later as **Your 3 for Today**.\n\n"
                "### SOLD!\n"
                "Gold + then **SOLD!**. Pick the customer, the vehicle, snap the delivery photo. That one tap logs the sale, sets the anniversary, schedules the review ask and the check-ins, and can post the photo to your Showcase.\n\n"
                "### Dates\n"
                "Birthday, anniversary and sold date live on the contact under **Important Dates**. Add a birthday once and the app reminds you every year, and can send the text for you.\n\n"
                "### Advocates\n"
                "Customers who refer people or leave reviews are marked as **Advocates**. Thank them. Home will remind you."
            ),
            "steps": ["Add one contact with the + on the Contacts tab", "Import your phone contacts using Contacts > Import Contacts", "Leave a voice note on one customer with three personal details", "Add a birthday on one contact"],
        },
        {
            "slug": "your-brand", "title": "Your Brand: Card, Reviews, Showcase", "icon": "id-card", "duration": "4 min", "order": 6,
            "description": "The links you send every day and where they live.",
            "content": (
                "## Your Brand\n\n"
                "Tools > **My Brand** holds everything a customer can see about you. Each one is a link you can text.\n\n"
                "### My Digital Card\n"
                "Your photo, title, phone, socials, save-to-contacts button. Send it to every new customer.\n"
                "- Fast: **Share My Card** (Tools > My Brand) picks a contact and texts it.\n"
                "- In person: the **QR icon** on Home. They scan, they have you.\n\n"
                "### Get Reviews\n"
                "**Get Reviews** texts your review link (Google first, Facebook and Yelp as backups). Best moment: right after delivery while they are smiling, and again three days later if they did not tap. Reviews you earn show on your Showcase and Landing Page.\n\n"
                "### My Showcase\n"
                "Your delivery photos and reviews on one page. Every SOLD! can add to it. Share it on social media or in your email signature.\n\n"
                "### My Link Page\n"
                "One link with all your links, for Instagram bios and email signatures.\n\n"
                "### Share the App\n"
                "Your personal install link and QR for the app itself. Share it with a colleague or a friend in the business; you get a ping when someone installs and their name when they sign up.\n\n"
                "### Preview before you send\n"
                "Each item has **View**. Look at it once as a customer would."
            ),
            "steps": ["Tools > My Brand > My Digital Card > View", "Send your card to yourself with Share My Card", "Send one review request to a recent happy customer", "Put your Link Page in your Instagram bio or email signature"],
        },
        {
            "slug": "inventory-lot-links", "title": "Inventory and Lot Photos", "icon": "car-sport", "duration": "3 min", "order": 7,
            "description": "What shoppers are looking at, and how to know the moment they look.",
            "content": (
                "## Inventory and Lot Photos\n\n"
                "Tools > **Inventory** is the store's live stock, pulled from the feed your manager connected.\n\n"
                "### Hot This Week\n"
                "At the top: the vehicles shoppers opened most, and which shoppers. That is what to push.\n\n"
                "### Lot links\n"
                "When Jessi (or you) sends a vehicle, the customer gets photos and a short **lot link**. The second they open it you get an alert like **\"Sarah just opened the Tacoma\"**. Tap it and the text is already written: *\"Hey Sarah, saw you were checking out the Tacoma. Want me to set it aside so you can see it in person?\"* Send it while they are looking.\n\n"
                "### Sending photos yourself\n"
                "Gold + then **Send Photo**: pick the customer, pick the vehicle or take a photo, send. Or ask Jessi in the thread: type the customer's question and let her pull the vehicle.\n\n"
                "### If a vehicle is missing\n"
                "The feed updates on a schedule. If something is on the lot but not in the app, tell your manager; they can force a sync under Tools > Manage > Inventory Feed."
            ),
            "steps": ["Open Tools > Inventory and look at Hot This Week", "Send one vehicle to a customer with Send Photo", "When a lot-link alert arrives, tap it and send the prewritten text"],
        },
        {
            "slug": "alerts-notifications", "title": "Alerts and Notifications", "icon": "notifications", "duration": "3 min", "order": 8,
            "description": "Where every ping lands and how to keep the noise down.",
            "content": (
                "## Alerts and Notifications\n\n"
                "The **bell** on Home opens Alerts. Every push notification you receive is also here, so if you swiped one away on your lock screen you can still find it.\n\n"
                "### Buckets\n"
                "- **NOW**: a customer is waiting or looking right now.\n"
                "- **TODAY**: do it before you leave.\n"
                "- **LATER**: nice to have.\n\n"
                "### Gestures\n"
                "- Swipe **left** to dismiss.\n"
                "- Swipe **right** to snooze until tomorrow morning.\n"
                "- Tap the gold action button (Text, Call, Open) to handle it.\n"
                "- **Clear all** at the top empties the list; Undo appears for a few seconds.\n\n"
                "### Quiet hours\n"
                "Tools > Settings > **Notifications**: set the hours you do not want your phone to buzz. Alerts that arrive overnight are held and summarized in the morning, and they still show in the Alerts list.\n\n"
                "### Not getting pushes?\n"
                "Tools > Settings > Notifications > **Push Health Check** > **Send me a test push**. If nothing arrives, the card tells you what is off (usually iPhone Settings > Notifications > i'M On Social is turned off)."
            ),
            "steps": ["Open Alerts from the bell", "Swipe one alert left to dismiss and one right to snooze", "Set quiet hours under Tools > Settings > Notifications", "Run Send me a test push"],
        },
    ],
}

MANAGER_TRACK = {
    "slug": "managers",
    "title": "Manager's Playbook",
    "description": "Onboard a rep in ten minutes, buy them a number, set up the store, and know what to look at every week.",
    "icon": "people-circle",
    "color": "#34C759",
    "roles": ["manager", "admin", "store_manager", "org_admin", "super_admin"],
    "order": 2,
    "lessons": [
        {
            "slug": "onboard-a-rep", "title": "Onboard a Rep in 10 Minutes", "icon": "person-add", "duration": "5 min", "order": 1,
            "description": "Invite, activation text, first login. What the rep sees and what to do when it stalls.",
            "content": (
                "## Onboard a Rep in 10 Minutes\n\n"
                "### 1. Invite (2 minutes)\n"
                "Tools > **Set Up** > **Invite Team**. Enter first name, last name, email and **mobile number** (this matters), pick the role **Salesperson**, tap **Send**.\n\n"
                "The rep immediately gets:\n"
                "- A **text** with the App Store link and three steps.\n"
                "- An **email** with the same, plus an Activate button for the web version.\n"
                "- A **copy** button appears for you, so you can paste the same message into your own text thread with them.\n\n"
                "### 2. What the rep does (3 minutes)\n"
                "Install > open > **Activate my account** > enter their mobile number > enter the 6-digit code > choose a password. They land on Home.\n\n"
                "### 3. Give them a number (2 minutes)\n"
                "Tools > Set Up > **Phone Numbers** > **Buy**. See the next lesson. A rep without a number cannot text customers and Jessi cannot answer for them.\n\n"
                "### 4. Have them do the Sales Team Onboarding track\n"
                "Tools > **Learning** > **Training Hub**. Eight lessons, about 30 minutes. The track shows a completion count on their Training Hub; iMOS admins can see everyone under Manage Training.\n\n"
                "### When it stalls\n"
                "- **No activation text**: the mobile number on the account is wrong or has a typo. Tools > Set Up > Team Members > open the rep > fix the phone > resend from Invite Team.\n"
                "- **Wrong email**: same place, edit and resend.\n"
                "- **Rep already had an account**: use **Forgot password** on the login screen instead of Activate.\n"
                "- **Android**: the app is iPhone only today. They can use the web version at app.imonsocial.com until the Android build ships."
            ),
            "steps": ["Tools > Set Up > Invite Team: name, email, mobile, role Salesperson, Send", "Confirm the rep received the text and can tap Activate my account", "Tools > Set Up > Phone Numbers > Buy and assign their number", "Ask them to finish the Sales Team Onboarding track"],
        },
        {
            "slug": "buy-a-number", "title": "Buy and Assign a Phone Number", "icon": "call", "duration": "3 min", "order": 2,
            "description": "One screen: buy by area code, assign, pool, health, release.",
            "content": (
                "## Buy and Assign a Phone Number\n\n"
                "Tools > **Set Up** > **Phone Numbers** is the only place numbers live now.\n\n"
                "### Buy and assign in one step\n"
                "1. Tap **Buy**.\n"
                "2. Under **Assign to**, tap the rep (or leave **Number pool**).\n"
                "3. Enter the local area code, tap **Search**.\n"
                "4. Tap **Buy & assign** on any number.\n\n"
                "That is it. Texting, calling, voicemail and Jessi are wired automatically. Numbers cost $1.15 a month each.\n\n"
                "### Reading the list\n"
                "- **ASSIGNED** with the rep's name: their customers text this number, Jessi answers as them.\n"
                "- **POOL**: no rep. Jessi answers as the store and hands leads to whoever is available.\n"
                "- **Texts and calls OK**: healthy. If you ever see **Needs a fix**, tap **Fix**; it repairs the connection in a second.\n"
                "- Contacts, messages this month and last activity tell you if a number is actually being used.\n\n"
                "### Reassign / move to pool\n"
                "Tap **Reassign** on any number. Pick a different rep, or **Move to Pool**. The number keeps working the whole time; customers never notice.\n\n"
                "### Release\n"
                "**Release** gives the number back to the carrier and stops billing. It cannot be undone, so move it to the pool instead if there is any chance you want it back."
            ),
            "steps": ["Tools > Set Up > Phone Numbers > Buy", "Pick the rep under Assign to, enter an area code, Search", "Tap Buy & assign", "Confirm the number shows ASSIGNED and Texts and calls OK"],
        },
        {
            "slug": "store-setup", "title": "Set Up the Store for Jessi", "icon": "storefront", "duration": "5 min", "order": 3,
            "description": "Store profile, inventory feed, lead sources and availability.",
            "content": (
                "## Set Up the Store for Jessi\n\n"
                "Jessi is only as good as what the store gives her. Five screens, all under Tools.\n\n"
                "### Store Profile (Tools > Set Up)\n"
                "Logo, address, hours, website. Jessi quotes hours and directions from here, and the logo goes on every card and review page. Business hours also drive the after-hours rule for leads.\n\n"
                "### Inventory Feed (Tools > Manage)\n"
                "Connect the lot: HomeNet, vAuto, a CSV or JSON link from your website vendor, a Google Sheet, or an SFTP drop. Once connected the app pulls hourly. Tap **Pull now** anytime. Jessi answers \"do you have a white Tacoma\" with real units, photos and lot links only when this is connected.\n\n"
                "### Lead Sources (Tools > Leads)\n"
                "**Lead Source Config**: how each source (website, Cars.com, AutoTrader, Facebook) is texted and called, and how fast.\n"
                "**Connect Zapier / Make**: send leads from any tool with a single webhook. There is a ready recipe for Facebook Lead Ads.\n"
                "Every source shows health: green means leads arrived recently, red means something upstream stopped.\n\n"
                "### Team Availability (Tools > Leads)\n"
                "Who is on shift. Leads route to available reps first; the pool number and Jessi cover the gaps.\n\n"
                "### Review Links (Tools > Manage)\n"
                "Google, Facebook and Yelp links for the store. Reps' **Get Reviews** button uses these."
            ),
            "steps": ["Tools > Set Up > Store Profile: logo, address, hours", "Tools > Manage > Inventory Feed: connect and Pull now", "Tools > Leads > Lead Source Config: check each source is green", "Tools > Leads > Team Availability: set shifts", "Tools > Manage > Review Links: paste the Google link"],
        },
        {
            "slug": "what-reps-see", "title": "What Reps See (and How to Give Them More)", "icon": "eye", "duration": "3 min", "order": 4,
            "description": "The rep-first Home and Tools, and permissions.",
            "content": (
                "## What Reps See\n\n"
                "Salespeople get a focused app. Managers, admins and partners see everything.\n\n"
                "### Rep Home\n"
                "Do This Next, Your 3 for Today, Needs a Reply, and the gold + (SOLD!, Call, Voice Note, Send Photo, Calendar). Nothing else.\n\n"
                "### Rep Tools\n"
                "Five items: **Today** (Touchpoints, Calendar, My Numbers, AI Follow-ups), **My Brand** (Card, Share My Card, Get Reviews, Showcase, Link Page, Share the App), **Inventory**, **Learning**, **Settings**.\n\n"
                "### See it yourself\n"
                "On your Tools screen, use **View as rep** to preview exactly what they get.\n\n"
                "### Giving a rep more\n"
                "Tools > Set Up > **Team Members** > open the rep > **Permissions**. Turn on Campaigns, Broadcast, Internet Leads or reports for that person. They appear in their Tools the next time they open the app.\n\n"
                "### Why so little\n"
                "A rep who clears three cards and the inbox every morning is doing the job. Everything else is reporting, and reporting is your screen, not theirs."
            ),
            "steps": ["Tap View as rep on your Tools screen", "Open Tools > Set Up > Team Members and look at one rep's Permissions", "Turn one extra tool on for a rep who needs it"],
        },
        {
            "slug": "weekly-rhythm", "title": "Your Weekly Rhythm", "icon": "calendar", "duration": "4 min", "order": 5,
            "description": "Five screens, ten minutes, once a week.",
            "content": (
                "## Your Weekly Rhythm\n\n"
                "Monday morning, ten minutes, in this order.\n\n"
                "1. **Home > Leads Waiting**: anything unanswered from the weekend gets claimed now.\n"
                "2. **Home > AI Reply Health**: if Jessi failed to send anything, it shows here with the reason.\n"
                "3. **Tools > My Performance > Leaderboard**: touches, replies, reviews, sales by rep. Praise the top, ask the bottom what got in the way.\n"
                "4. **Tools > My Performance > Team Tasks**: overdue follow-ups by rep. Overdue means a customer is waiting.\n"
                "5. **Home > Hot Vehicles**: what shoppers opened most. Tell the floor.\n\n"
                "### The three numbers that matter\n"
                "- **Reply time** on WAITING threads. Under five minutes during shift.\n"
                "- **Touches per rep per day**. Five is the floor; Your 3 for Today gets them to three before coffee.\n"
                "- **Review conversion**: reviews earned divided by review requests sent.\n\n"
                "### Coaching with receipts\n"
                "Open any rep's contact from Team Tasks or the Activity Feed and read the thread. Coach on what was actually said, not on a feeling."
            ),
            "steps": ["Monday: clear Leads Waiting and check AI Reply Health", "Read the Leaderboard and Team Tasks", "Pick one rep and read three of their threads before your 1:1"],
        },
        {
            "slug": "when-a-rep-leaves", "title": "When a Rep Leaves", "icon": "swap-horizontal", "duration": "3 min", "order": 6,
            "description": "Keep the relationships. Three taps.",
            "content": (
                "## When a Rep Leaves\n\n"
                "The relationships belong to the store. Here is how they stay.\n\n"
                "1. **Tools > Set Up > Phone Numbers**: tap **Reassign** on their number and pick the new rep, or **Move to Pool**. Customers who text the old number reach the store, not a dead line.\n"
                "2. **Move their contacts**: iMOS admins do this in Tools > Admin > Bulk Transfer (to one rep, or split across the team). Notes, dates, voice-note memories and history come along. If you do not see Bulk Transfer, ask your iMOS admin.\n"
                "3. **Tools > Set Up > Team Members**: open the rep and **Deactivate**. Their login stops working immediately and their number is held in the pool.\n\n"
                "Do step 1 and 3 first if you are in a hurry; the contacts can move later.\n\n"
                "The new rep's **Your 3 for Today** starts surfacing those customers the next morning, with the reasons, as if they had known them all along."
            ),
            "steps": ["Reassign or pool the number", "Have an iMOS admin Bulk Transfer the contacts", "Deactivate the user"],
        },
    ],
}

GETTING_STARTED_SOPS = [
    {
        "title": "Onboard a New Rep (Manager Checklist)", "summary": "Invite, activation, phone number, training. Ten minutes end to end.",
        "department": "all", "category": "getting_started", "is_required_reading": True, "estimated_time": "10 minutes", "difficulty": "beginner",
        "tags": ["onboarding", "invite", "activation", "phone number"],
        "steps": [
            {"order": 1, "title": "Invite", "description": "Tools > Set Up > Invite Team. First name, last name, email, mobile number, role Salesperson. Tap Send.", "tip": "The mobile number must be the phone they will install the app on. The activation code goes there."},
            {"order": 2, "title": "What they receive", "description": f"A text and an email with the App Store link ({APP_STORE_URL}) and three steps: install, tap Activate my account, enter the code and choose a password. Use the Copy button to paste the same message into your own text thread with them.", "tip": "Android is not live yet. Android users can use app.imonsocial.com in the browser."},
            {"order": 3, "title": "Buy and assign a number", "description": "Tools > Set Up > Phone Numbers > Buy. Pick the rep under Assign to, enter the local area code, Search, Buy & assign. Confirm it shows ASSIGNED and Texts and calls OK.", "warning": "Without a number the rep cannot text customers and Jessi cannot answer for them."},
            {"order": 4, "title": "Profile", "description": "Have the rep open Tools > Profile and add a headshot, title and a two-sentence bio. This powers their Digital Card, Link Page, Landing Page and Showcase."},
            {"order": 5, "title": "Training", "description": "Have the rep finish Tools > Learning > Training Hub > Sales Team Onboarding (8 lessons, about 30 minutes). iMOS admins can track completion under Tools > Learning > Manage Training."},
            {"order": 6, "title": "If activation stalls", "description": "No text means the mobile number on the account is wrong. Tools > Set Up > Team Members > open the rep > fix the phone > resend from Invite Team. If they already had an account, use Forgot password instead of Activate."},
        ],
    },
    {
        "title": "Buy, Assign, Pool or Release a Phone Number", "summary": "Everything about numbers happens on one screen.",
        "department": "all", "category": "getting_started", "is_required_reading": True, "estimated_time": "3 minutes", "difficulty": "beginner",
        "tags": ["phone number", "twilio", "assign"],
        "steps": [
            {"order": 1, "title": "Open Phone Numbers", "description": "Tools > Set Up > Phone Numbers. The chips show total numbers, assigned, in pool and monthly cost."},
            {"order": 2, "title": "Buy & assign", "description": "Tap Buy. Under Assign to, pick the rep or Number pool. Enter an area code, Search, then Buy & assign. Texting, calling and Jessi are wired automatically.", "tip": "Numbers are $1.15 a month. Local area codes get more replies."},
            {"order": 3, "title": "Health", "description": "Each number shows Texts and calls OK when healthy. If it says Needs a fix, tap Fix."},
            {"order": 4, "title": "Reassign or pool", "description": "Tap Reassign on any number to pick another rep or Move to Pool. Pooled numbers are answered by Jessi as the store."},
            {"order": 5, "title": "Release", "description": "Release returns the number to the carrier and stops billing. It cannot be undone.", "warning": "Prefer Move to Pool unless you are sure."},
        ],
    },
    {
        "title": "Rep First Day Setup", "summary": "What a new rep does in their first 15 minutes.",
        "department": "sales", "category": "getting_started", "is_required_reading": True, "estimated_time": "15 minutes", "difficulty": "beginner",
        "tags": ["onboarding", "rep", "profile"],
        "steps": [
            {"order": 1, "title": "Install and activate", "description": "Install from the App Store link in the welcome text. Open the app, tap Activate my account, enter the mobile number your manager used, enter the 6-digit code, choose a password."},
            {"order": 2, "title": "Allow notifications", "description": "Tap Allow when iPhone asks. Quiet hours can be set later under Tools > Settings > Notifications."},
            {"order": 3, "title": "Profile", "description": "Tools > your name > Profile: headshot, title, two-sentence bio."},
            {"order": 4, "title": "Check your card", "description": "Tools > My Brand > My Digital Card > View. This is what customers see."},
            {"order": 5, "title": "Teach Jessi", "description": "Tools > Settings > My VA: how you talk, what you know, hobbies. Tap Hear Your VA in Action."},
            {"order": 6, "title": "Import contacts", "description": "Contacts > Import Contacts and follow the guide for iPhone or Google."},
            {"order": 7, "title": "Tomorrow morning", "description": "Open Home. Do This Next, Your 3 for Today, Needs a Reply. Clear them and you are done with the app."},
        ],
    },
    {
        "title": "Send the Right Link: Card, Reviews, Lot Photos, App", "summary": "Where each shareable link lives and when to send it.",
        "department": "sales", "category": "getting_started", "is_required_reading": False, "estimated_time": "5 minutes", "difficulty": "beginner",
        "tags": ["digital card", "reviews", "lot photos", "share the app"],
        "steps": [
            {"order": 1, "title": "Digital Card", "description": "Tools > My Brand > Share My Card picks a contact and texts it. In person, tap the QR icon on Home and let them scan. Send it to every new customer."},
            {"order": 2, "title": "Review request", "description": "Tools > My Brand > Get Reviews. Best right after delivery, again three days later if they did not tap. Store review links are set by the manager under Tools > Manage > Review Links."},
            {"order": 3, "title": "Lot photos", "description": "Gold + on Home > Send Photo: pick the customer and the vehicle. The customer gets photos and a short lot link. When they open it you get an alert with a prewritten text."},
            {"order": 4, "title": "Showcase and Link Page", "description": "Tools > My Brand. Showcase is delivery photos and reviews; Link Page is every link in one. Both belong in your social bios and email signature."},
            {"order": 5, "title": "Share the App", "description": "Tools > My Brand > Share the App. Your personal install link and QR. You get a ping when someone installs and their name when they sign up."},
        ],
    },
    {
        "title": "Troubleshooting: Activation, Texts and Notifications", "summary": "The five things that go wrong and the fix for each.",
        "department": "all", "category": "getting_started", "is_required_reading": False, "estimated_time": "5 minutes", "difficulty": "beginner",
        "tags": ["troubleshooting", "activation", "push", "sms"],
        "steps": [
            {"order": 1, "title": "No activation text", "description": "The mobile number on the account does not match the phone. Tools > Set Up > Team Members > open the rep > fix the number > resend from Invite Team."},
            {"order": 2, "title": "Rep cannot text customers", "description": "They have no number, or it is in the pool. Tools > Set Up > Phone Numbers > assign one. If the number says Needs a fix, tap Fix."},
            {"order": 3, "title": "Jessi is not answering", "description": "Check AI ON on the rep's Home (it may say AI PAUSED), then open the customer's thread: if a rep tapped Take Over, Jessi stays quiet until Resume AI. Failed sends show under Home > AI Reply Health for managers."},
            {"order": 4, "title": "No push notifications", "description": "Tools > Settings > Notifications > Push Health Check > Send me a test push. The card explains what is off. Most often iPhone Settings > Notifications > i'M On Social is turned off, or quiet hours are on. Every push also appears in Alerts (bell) regardless."},
            {"order": 5, "title": "Inventory missing a vehicle", "description": "Tools > Manage > Inventory Feed > Pull now. If the vehicle is still missing, it is not in the feed the vendor sends; check with them."},
        ],
    },
]


MANAGER_ROLES = ["manager", "admin", "store_manager", "org_admin", "super_admin"]

NAVIGATION_MAP = (
    "TABS (bottom bar): Home, Contacts, Inbox, Activity, Tools.\n"
    "HOME (salesperson): Do This Next card, Your 3 for Today (Text / Check / X per card, See all), Needs a Reply (WAITING badge, Open Inbox), gold + button (SOLD!, Calendar, Send Photo, Voice Note, Make a Call). Header: QR icon (my card), AI ON / AI PAUSED toggle, bell (Alerts).\n"
    "HOME (manager, extra): Leads Waiting, AI Reply Health, Hot This Week vehicles, Weekly Wins, Book of Business, quick tiles SOLD! / Contact / Card / Review.\n"
    "TOOLS (salesperson): Today (Touchpoints, Calendar, My Numbers, AI Follow-ups), My Brand (My Digital Card, Share My Card, Get Reviews, My Showcase, My Link Page, Share the App), Inventory, Learning (Training Hub, Help Center, Report a Bug), Settings (My Profile, My VA, Notifications, My Schedule, My Templates, Security). Profile strip at the top with Profile and My VA pills.\n"
    "TOOLS (manager/admin, additional folders): Leads (Internet Leads, Call Retries, Lead Source Queue, Lead Source Config, Connect Zapier / Make, Team Availability), Manage (Tags, Calendar, Keyword Auto-Tags, Keyword Search, Inventory, Review Center, Showcase, Inventory Feed, Review Links), My Tools, Campaigns (Campaigns, Broadcast, Date Triggers), My Performance (My Stats, Team Sales, Team Tasks, Customer Engagement, Leaderboard, Activity Reports, Email Analytics), Set Up (Store Profile, Brand Kit, Messaging Channels, SMS Notifications, Phone Numbers, Team Members, Invite Team, Integrations), Learning, Settings. View as Rep link previews the salesperson layout.\n"
    "ADMIN folder (iMOS super admins / partners): Onboarding Hub, Account Health, Organizations, Accounts, All Users, Bulk Transfer, SOPs & Guides, Manage Training, Billing.\n"
    "ALERTS (bell): NOW / TODAY / LATER buckets, swipe left = dismiss, swipe right = snooze, Clear all with Undo. Every push notification is mirrored here.\n"
    "INBOX filters: Hot, Waiting, Unread, All, AI, Active, Closed. Thread banner 'Jessi is handling this' has Take Over and All Good; after Take Over use Resume AI.\n"
    "PHONE NUMBERS: Tools > Set Up > Phone Numbers is the single screen: Buy (pick rep under Assign to, area code, Search, Buy & assign), Reassign / Move to Pool, Fix when 'Needs a fix', Release.\n"
    "THERE IS NO 'More' TAB ANY MORE. It is called Tools. Never say 'More >'.\n"
)


def knowledge_text() -> str:
    """Plain-text dump of the current training used as the Help Center AI's knowledge."""
    parts = ["NAVIGATION MAP:\n" + NAVIGATION_MAP]
    for track in (SALES_TEAM_TRACK, MANAGER_TRACK):
        parts.append(f"\n=== TRACK: {track['title']} ===")
        for lesson in track["lessons"]:
            parts.append(lesson["content"].replace("**", ""))
    parts.append("\n=== CHECKLISTS ===")
    for sop in GETTING_STARTED_SOPS:
        parts.append(f"\n{sop['title']}: {sop['summary']}")
        for step in sop["steps"]:
            extra = " ".join(f"{k.upper()}: {v}" for k, v in step.items() if k in ("tip", "warning"))
            parts.append(f"{step['order']}. {step['title']}: {step['description']} {extra}".rstrip())
    return "\n".join(parts)


async def apply_training_refresh(db) -> bool:
    """Replace the refreshed tracks/lessons and getting_started SOPs once per environment. Returns True when applied."""
    meta = await db.app_meta.find_one({"key": "training_content_version"})
    if meta and int(meta.get("value", 0)) >= CONTENT_VERSION:
        return False
    now = _now()
    for track in (SALES_TEAM_TRACK, MANAGER_TRACK):
        fields = {k: v for k, v in track.items() if k != "lessons"}
        existing = await db.training_tracks.find_one({"slug": track["slug"]})
        if existing:
            track_id = str(existing["_id"])
            await db.training_tracks.update_one({"_id": existing["_id"]}, {"$set": {**fields, "updated_at": now}})
        else:
            res = await db.training_tracks.insert_one({**fields, "created_at": now, "updated_at": now})
            track_id = str(res.inserted_id)
        await db.training_lessons.delete_many({"track_id": track_id})
        await db.training_progress.delete_many({"track_id": track_id})
        for lesson in track["lessons"]:
            await db.training_lessons.insert_one({**lesson, "video_url": "", "track_id": track_id, "created_at": now, "updated_at": now})
    # Old-interface videos stay available to managers only; reps see just their own track.
    await db.training_tracks.update_one(
        {"slug": "onboarding-videos"},
        {"$set": {"title": "Legacy Videos (old interface)", "description": "Recorded on the previous layout. Kept for reference until the new videos are ready.", "roles": MANAGER_ROLES, "order": 99, "updated_at": now}},
    )
    await db.training_tracks.update_many(
        {"slug": {"$nin": ["sales-team", "managers", "onboarding-videos"]}},
        {"$pull": {"roles": {"$in": ["user", "manager", "store_manager"]}}},
    )
    await db.sops.delete_many({"category": "getting_started"})
    for sop in GETTING_STARTED_SOPS:
        await db.sops.insert_one({**sop, "is_published": True, "created_at": now, "updated_at": now, "created_by": "system"})
    await db.app_meta.update_one({"key": "training_content_version"}, {"$set": {"value": CONTENT_VERSION, "applied_at": now}}, upsert=True)
    return True
