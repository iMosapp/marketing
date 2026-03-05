"""
Training / LMS Router
Role-based learning tracks with progress tracking and admin-editable content.
"""
from fastapi import APIRouter, Request, HTTPException, Query
from bson import ObjectId
from datetime import datetime, timezone
from typing import Optional

router = APIRouter(prefix="/training", tags=["training"])


def get_db():
    from routers.database import get_db as _get_db
    return _get_db()


SEED_TRACKS = [
    {
        "slug": "sales-team",
        "title": "Sales Team Onboarding",
        "description": "Everything you need to start selling and serving customers with i'M On Social.",
        "icon": "briefcase",
        "color": "#007AFF",
        "roles": ["user", "manager", "admin", "store_manager"],
        "order": 1,
        "lessons": [
            {
                "slug": "what-is-imos",
                "title": "What is i'M On Social?",
                "description": "Understand the platform, who it's for, and why it matters.",
                "icon": "rocket",
                "duration": "5 min",
                "order": 1,
                "content": "## Welcome to i'M On Social\n\ni'M On Social is a **relationship management platform** built for sales teams who believe in the power of personal connections.\n\n### The Problem We Solve\nMost CRMs are built for data entry, not relationships. Your customers don't want to be a record in a database — they want to feel remembered, valued, and cared for.\n\n### Our Value Proposition\n- **Stay top-of-mind** with automated touchpoints (birthday cards, anniversary messages, follow-ups)\n- **Build your personal brand** with digital business cards that customers actually keep\n- **Track every interaction** so you never forget a conversation or commitment\n- **Get more reviews** by making it effortless to ask at the right moment\n- **Stand out from competitors** who rely on generic corporate outreach\n\n### The Elevator Pitch\n> \"I use i'M On Social to stay connected with my customers. It sends personalized messages, shares my digital business card, and helps me get reviews — all from my phone. My customers love it because it feels personal, not automated.\"\n\n### Key Stats to Share\n- 80% of sales come from the 5th-12th contact with a prospect\n- Customers referred by friends have a 37% higher retention rate\n- A 5% increase in customer retention can increase profits by 25-95%",
                "video_url": "",
                "steps": ["Read through the value propositions above", "Practice the elevator pitch out loud 3 times", "Think of 3 customers who would benefit most from this approach", "Write down your own version of the pitch in your words"],
            },
            {
                "slug": "navigating-the-app",
                "title": "Navigating the App",
                "description": "Learn the main tabs, features, and where everything lives.",
                "icon": "phone-portrait",
                "duration": "5 min",
                "order": 2,
                "content": "## App Navigation Guide\n\n### The Four Main Tabs\n\n**1. Home**\nYour dashboard showing quick actions, pending tasks, and recent activity. Check this first thing every morning.\n\n**2. Contacts**\nYour customer database. Add new contacts, search existing ones, and view their full history.\n\n**3. Inbox**\nAll your conversations in one place. Send SMS, email, review requests, and digital cards.\n\n**4. More**\nSettings, your digital card, templates, training (you're here!), and account management.\n\n### Quick Actions (Home Screen)\n- **Share Digital Card** — Send your business card to a customer\n- **Request Review** — Ask for a Google/Yelp review\n- **Send Congrats** — Birthday, anniversary, or thank-you cards\n- **New Contact** — Add someone to your database\n\n### Pro Tips\n- Use the search bar at the top of Contacts to find anyone fast\n- Tap a contact's name to see their full timeline of interactions\n- The activity feed on Home shows what's happening across your account",
                "video_url": "",
                "steps": ["Open each of the 4 main tabs and explore", "Try the Quick Actions on the Home screen", "Search for an existing contact", "Open a contact and review their timeline"],
            },
            {
                "slug": "your-digital-card",
                "title": "Your Digital Business Card",
                "description": "Set up and share your personal digital card.",
                "icon": "card",
                "duration": "3 min",
                "order": 3,
                "content": "## Your Digital Business Card\n\nYour digital card is your **always-on personal brand**. Unlike paper cards that get lost, your digital card lives on the customer's phone forever.\n\n### What's On Your Card\n- Your photo and name\n- Job title and company\n- Direct phone number and email\n- Social media links\n- One-tap call, text, or email buttons\n- Your bio\n\n### How to Share It\n1. **Text it** — Send via SMS from any conversation\n2. **QR Code** — Show it on your phone for in-person meetings\n3. **Email signature** — Add the link to every email you send\n4. **Social media** — Post it on LinkedIn, Facebook, Instagram\n\n### Why It Works\n- Customers save it to their phone contacts\n- They can tap to call/text you anytime\n- It makes you look professional and tech-savvy\n- It tracks who views it and when\n\n### Best Practices\n- Use a **professional, well-lit headshot** (not a selfie)\n- Keep your bio **under 3 sentences** — highlight your specialty\n- Update your card when you get promoted or change roles",
                "video_url": "",
                "steps": ["Go to More > My Digital Card", "Make sure your photo, title, and bio are set", "Send your card to yourself to see how it looks", "Share it with 3 customers today"],
            },
            {
                "slug": "messaging-customers",
                "title": "Messaging & Follow-Up Process",
                "description": "How to communicate with customers effectively.",
                "icon": "chatbubbles",
                "duration": "5 min",
                "order": 4,
                "content": "## Messaging & Follow-Up\n\n### The Golden Rule\nEvery customer touchpoint should feel **personal, not automated**. Even when using templates, add a personal detail.\n\n### When to Message\n- **Day of sale** — Thank them for their business\n- **1 week after** — Check in, ask if they have questions\n- **30 days** — Follow up, ask for a review\n- **90 days** — Touch base, mention seasonal offers\n- **Birthdays & Anniversaries** — Never miss these!\n- **After service visits** — Thank them for coming in\n\n### Message Types\n1. **SMS** — Best for quick, casual touchpoints\n2. **Email** — Better for detailed info, links, or formal communication\n3. **Review Requests** — Use the built-in review link feature\n4. **Digital Card** — Share when meeting someone new\n5. **Congrats Cards** — Birthday, anniversary, holiday cards\n\n### Using Templates\n- Go to your conversation > tap the template icon\n- Templates auto-fill the customer's name\n- **Always personalize** — add one specific detail about them\n\n### Pro Tips\n- Best response times: **within 5 minutes** of receiving a message\n- Morning messages (8-10am) get the highest open rates\n- Keep texts under 160 characters when possible\n- Use voice-to-text for faster messaging on the go",
                "video_url": "",
                "steps": ["Send a follow-up message to your most recent customer", "Try using a template and personalizing it", "Set a reminder to follow up with 3 customers this week", "Practice using voice-to-text for a message"],
            },
            {
                "slug": "getting-reviews",
                "title": "Getting Reviews & Referrals",
                "description": "The process for asking for and getting 5-star reviews.",
                "icon": "star",
                "duration": "4 min",
                "order": 5,
                "content": "## Getting Reviews & Referrals\n\n### Why Reviews Matter\n- 93% of consumers read online reviews before making a purchase\n- A one-star increase on Yelp leads to 5-9% increase in revenue\n- Google reviews directly impact your search ranking\n\n### When to Ask\nThe **best time** to ask for a review is when the customer is happiest:\n- Right after a successful sale\n- After resolving a problem quickly\n- When they compliment you or your service\n- After a positive service experience\n\n### How to Ask (The Script)\n> \"I'm so glad everything worked out! Would you mind leaving me a quick review? It really helps me out. I'll send you the link right now — it takes less than a minute.\"\n\n### Using the App\n1. Open the customer's contact\n2. Tap \"Request Review\" in quick actions\n3. Choose the platform (Google, Yelp, Facebook)\n4. The app sends a tracked link\n5. You'll see when they click and complete it\n\n### Getting Referrals\nAfter a positive interaction:\n> \"Thanks so much! If you know anyone else who could use our services, I'd really appreciate you sending them my way. I'll send you my digital card so you can share it easily.\"\n\n### Monthly Goal\nAim for **4-5 new reviews per month**. That's roughly one per week.",
                "video_url": "",
                "steps": ["Identify 5 happy customers who haven't left a review", "Send review requests to all 5 today", "Practice the review ask script with a colleague", "Set a weekly reminder to request reviews"],
            },
            {
                "slug": "quotes-payments",
                "title": "Sending Quotes & Collecting Payments",
                "description": "How to create quotes and process payments.",
                "icon": "cash",
                "duration": "4 min",
                "order": 6,
                "content": "## Quotes & Payments\n\n### Creating a Quote\n1. From the customer's contact, tap **Create Quote**\n2. Add line items with descriptions and pricing\n3. Apply any discounts or promotions\n4. Add terms and conditions\n5. Send via email or text\n\n### Payment Collection\n- Quotes include a **Pay Now** button for the customer\n- Payments are processed securely through our payment system\n- You'll be notified when payment is received\n- All payment history is tracked on the contact's timeline\n\n### Best Practices\n- Send quotes **within 1 hour** of the conversation\n- Follow up on unsent quotes within 24 hours\n- Include a personal note with every quote\n- Make it easy — the fewer steps for the customer, the better\n\n### Pricing Guidelines\n*Your admin will provide specific pricing for your products/services. Refer to your organization's pricing sheet for current rates and available discounts.*",
                "video_url": "",
                "steps": ["Review your organization's pricing sheet", "Practice creating a sample quote", "Understand the payment flow from customer's perspective", "Know your discount approval limits"],
            },
        ],
    },
    {
        "slug": "partners-resellers",
        "title": "Partner & Reseller Onboarding",
        "description": "Everything you need to sell, onboard clients, and manage your partner business.",
        "icon": "people-circle",
        "color": "#C9A962",
        "roles": ["partner", "reseller", "admin", "super_admin"],
        "order": 2,
        "lessons": [
            {
                "slug": "why-partner",
                "title": "Why Partner with i'M On Social?",
                "description": "The value proposition for your customers and your business.",
                "icon": "diamond",
                "duration": "5 min",
                "order": 1,
                "content": "## Why Partner With Us?\n\n### For Your Customers\ni'M On Social solves a real problem for businesses that depend on relationships:\n- Sales teams forget to follow up\n- Customer data is scattered across phones, spreadsheets, and sticky notes\n- Review generation is inconsistent\n- Personal branding is non-existent\n\n### For Your Business\n- **Recurring revenue** — Monthly subscriptions mean predictable income\n- **Low churn** — Once teams adopt it, they don't want to go back\n- **Easy to sell** — Live demo takes 15 minutes, ROI is immediately clear\n- **Scalable** — Onboard locations yourself with our partner tools\n- **Commission structure** — Competitive rates on every account you bring in\n\n### Target Industries\n- **Automotive / Dealerships** — Sales teams, service advisors, BDC\n- **Real Estate** — Agents and brokerages\n- **Insurance** — Agents managing client portfolios\n- **Home Services** — HVAC, plumbing, roofing contractors\n- **Any relationship-driven business**\n\n### Your Competitive Advantage\nUnlike generic CRMs (Salesforce, HubSpot), i'M On Social is:\n- Built for the **individual salesperson**, not the corporation\n- **Mobile-first** — works from your phone\n- Includes **digital business cards**, not just a contact database\n- Has **built-in review generation** — others charge extra for this\n- Feels **personal, not corporate**",
                "video_url": "",
                "steps": ["Read through the value props and identify your top 3", "Think of 5 businesses in your network that fit the target profile", "Practice explaining the difference vs. generic CRMs", "Review your commission structure in your partner agreement"],
            },
            {
                "slug": "how-to-sell",
                "title": "How to Sell i'M On Social",
                "description": "Demo script, objection handling, and closing techniques.",
                "icon": "megaphone",
                "duration": "7 min",
                "order": 2,
                "content": "## How to Sell i'M On Social\n\n### The Discovery Call (5 min)\nAsk these questions:\n1. \"How do your salespeople stay in touch with customers after the sale?\"\n2. \"How many Google reviews do you get per month?\"\n3. \"Do your salespeople have digital business cards?\"\n4. \"What happens to customer relationships when an employee leaves?\"\n\n*Most businesses will admit they're weak in at least 2-3 of these areas.*\n\n### The Demo (15 min)\nShow these features in order:\n1. **Digital Card** — Share yours with them live. They'll be impressed.\n2. **Contact Timeline** — Show how every interaction is tracked\n3. **One-Tap Actions** — Review request, congrats card, SMS — all from one screen\n4. **Activity Dashboard** — Show how managers can see team performance\n5. **Templates** — Show how fast messaging becomes with pre-built templates\n\n### Handling Objections\n\n**\"We already have a CRM\"**\n> \"Great — this isn't a replacement. Think of it as the front-end that your salespeople actually use. It's the personal touch layer on top of your existing system.\"\n\n**\"My team won't use it\"**\n> \"That's actually our sweet spot. It's built for salespeople, not admins. It takes 2 minutes to learn because it works like texting. Plus, the leaderboard creates healthy competition.\"\n\n**\"It's too expensive\"**\n> \"Let me ask — what's one customer worth to you over their lifetime? If this tool helps retain even one extra customer per month, it pays for itself 10x over.\"\n\n**\"We tried something similar before\"**\n> \"What was different? Usually it's because the tool was built for the company, not the salesperson. i'M On Social is the first thing your team will actually want to use.\"\n\n### Closing\n> \"Based on what you've told me, I think we could have your team up and running in 48 hours. Want me to set up a pilot with 5 users so you can see the results firsthand?\"",
                "video_url": "",
                "steps": ["Practice the discovery call questions with a partner", "Do a mock demo — time yourself to stay under 15 minutes", "Role-play each objection with a colleague", "Identify your first 3 prospects to call this week"],
            },
            {
                "slug": "quoting-pricing",
                "title": "Quoting & Pricing Guide",
                "description": "How to create proposals and understand the pricing model.",
                "icon": "calculator",
                "duration": "5 min",
                "order": 3,
                "content": "## Quoting & Pricing\n\n### Pricing Model\n*Your specific pricing tier and discounting authority are outlined in your partner agreement. Refer to that document for exact numbers.*\n\n### General Pricing Structure\n- **Per-user monthly subscription** — Each salesperson gets their own account\n- **Volume discounts** — Larger teams get better per-user rates\n- **Annual vs. Monthly** — Annual commitments come with a discount\n- **Setup fees** — May apply for custom branding or data migration\n\n### Creating a Quote\n1. Determine the number of users needed\n2. Apply the appropriate volume tier\n3. Add any setup fees or customization\n4. Calculate your commission\n5. Present with a simple, clear format\n\n### Quote Presentation Tips\n- Always present **3 options** (good, better, best)\n- Lead with the **middle option** — it's the one most will choose\n- Show the **ROI calculation** — cost per user vs. value of retained customers\n- Include a **pilot offer** — \"Start with 5 users for 30 days\"\n\n### Discount Authority\nRefer to your partner agreement for your discount limits. When in doubt, ask your account manager before discounting below your authorized threshold.",
                "video_url": "",
                "steps": ["Review your partner agreement for pricing tiers", "Create a sample quote for a 10-person sales team", "Practice presenting 3-tier pricing options", "Understand your discount authority limits"],
            },
            {
                "slug": "onboarding-clients",
                "title": "How to Onboard a New Client",
                "description": "Step-by-step process from signed deal to live account.",
                "icon": "clipboard",
                "duration": "6 min",
                "order": 4,
                "content": "## Client Onboarding Process\n\n### Overview\nOnce a deal is signed, getting the client live should take **24-48 hours**. Here's the exact process:\n\n### Step 1: Gather Information\nCollect from the client:\n- Company name and logo\n- List of users (name, email, phone, role)\n- Google/Yelp/Facebook review page URLs\n- Any existing message templates they use\n\n### Step 2: Use the Partner Onboard Wizard\n1. Go to **Partner Portal > Onboard New Location**\n2. Select the organization (assigned to you by admin)\n3. Create the store/location with address and contact info\n4. Upload their logo and set brand colors\n5. Add all team members — the system generates temp passwords\n6. Add review links for Google, Yelp, etc.\n7. Download the **credentials CSV** from the handoff screen\n\n### Step 3: Deliver Credentials\n- Send each user their login email and temp password\n- They'll be prompted to set up their profile on first login\n- Schedule a **15-minute kickoff call** to walk through the basics\n\n### Step 4: Follow Up\n- **Day 1:** Confirm everyone can log in\n- **Day 3:** Check that profiles are complete\n- **Week 1:** Review activity — are they sending messages?\n- **Week 2:** Address any questions, suggest templates\n- **Month 1:** Review results, ask for a case study/testimonial\n\n### Common Issues\n- **\"I can't log in\"** — Make sure they're using the correct email (case sensitive)\n- **\"Where's my card?\"** — They need to complete their profile first\n- **\"Templates aren't showing\"** — Check they were created at the org level",
                "video_url": "",
                "steps": ["Bookmark the Partner Portal in your browser", "Do a practice onboarding with test data", "Create a checklist template you can reuse for each client", "Draft your kickoff call agenda"],
            },
            {
                "slug": "setting-up-payments",
                "title": "Setting Up Payment Collection",
                "description": "How to ensure recurring payments come in from your clients.",
                "icon": "card",
                "duration": "4 min",
                "order": 5,
                "content": "## Setting Up Payments\n\n### Payment Flow\n1. **Quote approved** — Client agrees to the subscription\n2. **Invoice sent** — Automated or manual invoice via the system\n3. **Payment collected** — Credit card or ACH payment processed\n4. **Subscription active** — Account goes live\n5. **Recurring billing** — Automatic monthly charges\n\n### Your Responsibilities\n- Ensure the client's payment method is on file **before** activating their account\n- Follow up on any failed payments within 24 hours\n- Know when client contracts renew so you can check in beforehand\n\n### Commission Tracking\n- Your commissions are calculated based on your partner agreement terms\n- Commission reports are available in your partner dashboard\n- Payments are made on the schedule outlined in your agreement\n\n### Handling Payment Issues\n- **Declined card** — Contact the client, ask them to update payment info\n- **Requesting cancellation** — Understand why, offer solutions, escalate if needed\n- **Downgrading** — Help them find the right tier, don't lose the account entirely\n\n*Refer to your partner agreement for specific commission rates and payment schedules.*",
                "video_url": "",
                "steps": ["Understand the payment flow end-to-end", "Know where to find your commission reports", "Create a template for payment follow-up emails", "Review your payment schedule in your partner agreement"],
            },
            {
                "slug": "partner-dashboard-guide",
                "title": "Your Partner Dashboard",
                "description": "How to use the partner portal to manage your accounts.",
                "icon": "grid",
                "duration": "3 min",
                "order": 6,
                "content": "## Partner Dashboard Guide\n\n### Accessing Your Dashboard\nGo to **Partner Portal** from the main menu. This is your home base for managing all your client accounts.\n\n### What You'll See\n- **Stats Overview** — Total orgs, locations, and users you manage\n- **Your Organizations** — Expandable cards showing each client org\n- **Per-Org Details** — Click to see locations, team members, and their status\n\n### Key Actions\n- **Onboard New Location** — The gold button at the top starts the wizard\n- **Add to Existing Org** — Click \"Add Location & Team\" on any org card\n- **View User Status** — See if users have completed onboarding (\"Pending\" badge)\n\n### What You Can't Do (By Design)\n- You **cannot modify** organization settings (name, type, etc.)\n- You **cannot delete** users or locations — contact your admin\n- You **cannot see** other partners' accounts\n\n### Best Practices\n- Check your dashboard weekly to monitor user adoption\n- Follow up with any users showing \"Pending\" status after 3 days\n- Use the stats to report your growth to your account manager",
                "video_url": "",
                "steps": ["Open the Partner Portal and explore each section", "Expand an organization to see its locations and users", "Try the Onboard New Location flow with test data", "Note any pending users who need follow-up"],
            },
        ],
    },
    {
        "slug": "white-label-partners",
        "title": "White Label Partner Guide",
        "description": "Run the platform under your brand — setup, client onboarding, and support playbook.",
        "icon": "color-palette",
        "color": "#AF52DE",
        "roles": ["partner", "reseller", "admin", "super_admin"],
        "order": 3,
        "lessons": [
            {
                "slug": "wl-what-is-white-label",
                "title": "What is White Labeling?",
                "description": "Understand how white-label works and what you control.",
                "icon": "layers",
                "duration": "4 min",
                "order": 1,
                "content": "## What is White Labeling?\n\nAs a **white-label partner**, you run i'M On Social under **your own brand**. Your clients see your logo, your colors, and your company name — they never see ours.\n\n### What You Control\n- **Your logo** replaces ours throughout the app\n- **Your brand colors** are applied to buttons, headers, and emails\n- **Your company name** appears in all client-facing communications\n- **Custom email domain** — emails come from your domain (e.g., noreply@yourbrand.com)\n- **Custom footer text** on all automated messages\n\n### What Stays the Same\n- The core platform functionality\n- All features (messaging, cards, reviews, reporting)\n- Backend infrastructure and uptime\n- Mobile app experience\n\n### Your Value Proposition\nWhite labeling lets you:\n- Build a **recurring revenue stream** without building software\n- Offer a **premium, branded experience** to your clients\n- **Differentiate** from competitors who resell generic tools\n- Maintain **full control** of the client relationship\n\n### Getting Started\nYour admin will configure your brand assets. Once set up, everything your clients see will carry your brand.",
                "video_url": "",
                "steps": ["Review your brand assets (logo, colors, tagline)", "Confirm your custom email domain is verified", "Visit the White Label settings page to see your branding", "Open a test account to see the white-label experience"],
            },
            {
                "slug": "wl-branding-setup",
                "title": "Setting Up Your Brand",
                "description": "Configure logos, colors, and email branding.",
                "icon": "brush",
                "duration": "5 min",
                "order": 2,
                "content": "## Setting Up Your Brand\n\n### Brand Assets Needed\nBefore you begin, gather:\n1. **Logo** — High-res PNG with transparent background (min 400x400px)\n2. **Primary brand color** — Hex code (e.g., #FF5500)\n3. **Secondary color** — For accents and highlights\n4. **Company tagline** — Short phrase for email footers\n5. **Support email** — Where clients send questions\n\n### Configuration Steps\n1. Go to **Admin > White Label Settings**\n2. Upload your logo\n3. Set your primary and secondary brand colors\n4. Enter your company name and tagline\n5. Configure your email \"From\" name and domain\n6. Save and preview\n\n### Email Branding\nAll automated emails will include:\n- Your logo at the top\n- Your brand colors for buttons and accents\n- Your company name in the footer\n- A \"Powered by\" link (optional, can be hidden)\n\n### Testing Your Brand\n- Send a test email from the inbox to yourself\n- Open a digital business card link\n- Check the login page appearance\n- Verify review request emails look correct\n\n### Best Practices\n- Use a **clean, horizontal logo** for email headers\n- Choose colors with **good contrast** for readability\n- Keep your tagline **under 10 words**\n- Test on both desktop and mobile email clients",
                "video_url": "",
                "steps": ["Upload your logo to the White Label settings", "Set your brand colors", "Send a test email and verify branding", "Check the digital card appearance"],
            },
            {
                "slug": "wl-onboarding-clients",
                "title": "Onboarding Clients Under Your Brand",
                "description": "The step-by-step process to get clients live with your branded platform.",
                "icon": "person-add",
                "duration": "6 min",
                "order": 3,
                "content": "## Onboarding Clients Under Your Brand\n\n### Overview\nWhen you onboard a client, they experience **your brand** from day one. Here's how to deliver a seamless, professional onboarding.\n\n### Step 1: Prepare the Account\n1. Use the **Partner Onboard Wizard** to create the organization\n2. Upload the client's store logo and set their location details\n3. Add team members — the system generates temporary passwords\n4. Download the credentials CSV\n\n### Step 2: Customize Their Experience\n- Their emails will show **your logo and colors** (not theirs)\n- Digital cards will link back to **your branded domain**\n- Review requests go out under **your brand identity**\n\n### Step 3: Deliver a Branded Welcome\nSend a welcome email (using your branded template) that includes:\n- Login credentials\n- A link to the Training Hub\n- Your support contact information\n- A quick-start guide or short video\n\n### Step 4: The Kickoff Call\nSchedule a 20-minute kickoff:\n1. **Walk through the app** — show the 4 main tabs (2 min)\n2. **Set up their profile** — photo, bio, title (5 min)\n3. **Send their first message** — a real customer text (3 min)\n4. **Share their digital card** — with you, as practice (2 min)\n5. **Q&A** — address any concerns (8 min)\n\n### Step 5: Follow-Up Cadence\n- **Day 1:** Confirm login works for everyone\n- **Day 3:** Check profile completion\n- **Week 1:** Review activity numbers\n- **Week 2:** Coaching call if needed\n- **Month 1:** ROI review and testimonial request",
                "video_url": "",
                "steps": ["Create a test organization in the Partner Wizard", "Verify the welcome email shows your branding", "Practice the 20-minute kickoff call flow", "Set calendar reminders for the follow-up cadence"],
            },
            {
                "slug": "wl-messaging-guide",
                "title": "Messaging Under Your Brand",
                "description": "How your clients' messages are sent and branded.",
                "icon": "chatbubble-ellipses",
                "duration": "4 min",
                "order": 4,
                "content": "## Messaging Under Your Brand\n\n### How It Works\nWhen your clients send messages through the platform, the experience varies by channel:\n\n### SMS Messages\n- Sent from the **user's personal phone** (carrier-agnostic mode) or a provisioned number\n- The app pre-fills the message and opens the native SMS app\n- All activity is **logged in the CRM** regardless of how it's sent\n- Tracking links are included for review requests and digital cards\n\n### Email Messages\n- Sent through your **branded email domain**\n- Your logo and colors appear in the email header\n- A custom footer with your company info is included\n- Reply-to address can be the user's direct email\n\n### Review Requests\n- Custom short URLs track click-through and completion\n- The landing page carries **your branding**\n- Automated follow-ups can be scheduled\n\n### Digital Business Cards\n- Cards display your user's info under **your brand umbrella**\n- Card share links are tracked\n- Analytics show views, saves, and clicks\n\n### Training Your Clients on Messaging\nTeach them the **5-touch rule**:\n1. **Day of sale** — Thank you message\n2. **1 week later** — Check-in\n3. **30 days** — Review request\n4. **90 days** — Touch base\n5. **Birthdays/Anniversaries** — Never miss these\n\n### Pro Tips for Your Team\n- Always personalize — add the customer's name and a specific detail\n- Best time to text: 8-10am or 5-7pm\n- Keep texts under 160 characters\n- Use templates but add personal touches",
                "video_url": "",
                "steps": ["Send a test SMS through the app", "Send a test email and verify your branding", "Share a digital card and check the branded link", "Review the tracking analytics after sending"],
            },
            {
                "slug": "wl-support-playbook",
                "title": "Supporting Your Clients",
                "description": "Handle common questions and keep clients happy.",
                "icon": "help-circle",
                "duration": "4 min",
                "order": 5,
                "content": "## Supporting Your Clients\n\n### Your Support Responsibilities\nAs a white-label partner, **you are the first line of support**. Your clients reach out to you, not to us.\n\n### Common Questions & Answers\n\n**\"How do I send a message?\"**\n> Open a contact > Tap the message icon > Choose SMS or Email > Type your message > Send. The app logs everything automatically.\n\n**\"I can't log in\"**\n> Verify they're using the correct email (case-sensitive). Reset their password from Admin > Users if needed.\n\n**\"Where's my digital card?\"**\n> They need to complete their profile first. Go to My Account > Edit Profile > ensure photo, title, and bio are filled in.\n\n**\"How do I get more reviews?\"**\n> Open a customer's contact > Quick Actions > Request Review. The link is tracked so they can see when it's clicked and completed.\n\n**\"My messages aren't sending\"**\n> For SMS: Make sure they're opening the native SMS app when prompted. For Email: Check that the email address on the contact is correct.\n\n**\"Can I see my team's activity?\"**\n> Managers can view the Activity Dashboard and Leaderboard. Users can only see their own metrics.\n\n### Escalation Path\nIf you can't resolve an issue:\n1. Gather the details (user email, screenshot, steps to reproduce)\n2. Contact your account manager\n3. We'll respond within 24 business hours\n\n### Reducing Support Volume\n- Point clients to the **Training Hub** for self-service learning\n- Create a **FAQ document** with your branding\n- Schedule **monthly check-in calls** to address issues proactively",
                "video_url": "",
                "steps": ["Create a branded FAQ document for your clients", "Practice answering each common question out loud", "Set up your escalation email template", "Schedule monthly check-ins with your top clients"],
            },
        ],
    },
    {
        "slug": "managers",
        "title": "Manager's Playbook",
        "description": "Lead your team, read the data, and coach for performance.",
        "icon": "shield",
        "color": "#34C759",
        "roles": ["manager", "admin", "store_manager", "super_admin"],
        "order": 4,
        "lessons": [
            {
                "slug": "manager-overview",
                "title": "Your Role as a Manager",
                "description": "What i'M On Social means for team leadership.",
                "icon": "people",
                "duration": "4 min",
                "order": 1,
                "content": "## The Manager's Role\n\n### Why This Matters\nAs a manager, you're not just overseeing software — you're building a **culture of follow-through**. i'M On Social gives you visibility into whether your team is actually nurturing customer relationships.\n\n### Your Key Responsibilities\n1. **Monitor Activity** — Are your people reaching out? How often?\n2. **Coach** — Use conversation data to provide specific, actionable feedback\n3. **Recognize** — Celebrate top performers using the leaderboard\n4. **Onboard New Hires** — Ensure they complete training and set up their profiles\n5. **Lead by Example** — Use the platform yourself\n\n### The Metrics That Matter\n- **Touches per week** — How many outbound messages per salesperson?\n- **Review conversion rate** — Of review requests sent, how many completed?\n- **Response time** — How fast does your team reply to inbound messages?\n- **Card shares** — Are they actively sharing their digital card?\n\n### Your Goal\nGet every team member to make **at least 5 meaningful customer touches per day**. That's the baseline for relationship-driven selling.",
                "video_url": "",
                "steps": ["Review the activity dashboard for your team", "Identify your top 3 performers and your bottom 3", "Set a team goal for touches per week", "Schedule weekly 1:1s to review individual metrics"],
            },
            {
                "slug": "reading-reports",
                "title": "Reading Activity Reports",
                "description": "Understand the data and use it to drive performance.",
                "icon": "bar-chart",
                "duration": "5 min",
                "order": 2,
                "content": "## Reading Activity Reports\n\n### The Activity Dashboard\nAccess via **Admin > Reports > Activity**. This shows:\n- Total messages sent (SMS + Email)\n- Review requests sent and completed\n- Digital cards shared\n- Congrats cards sent\n- Average response time\n\n### Date Filters\nUse the date picker to compare:\n- This week vs. last week\n- This month vs. last month\n- Quarter over quarter\n\n### What to Look For\n- **Declining activity** — Is someone disengaged or struggling?\n- **High sends, low reviews** — They're reaching out but not asking for reviews\n- **Low card shares** — They're not leveraging their digital card\n- **Slow response times** — Customers are waiting too long\n\n### Taking Action\nFor each metric, have a coaching conversation:\n- \"I noticed your review requests dropped this week. What's getting in the way?\"\n- \"Your response time is great — 4 minutes average. Keep it up.\"\n- \"You shared your card 15 times this month. Challenge: hit 30 next month.\"\n\n### Scheduled Reports\nSet up **weekly email reports** to get a summary delivered to your inbox every Monday morning.",
                "video_url": "",
                "steps": ["Pull up the Activity Dashboard", "Compare this week to last week", "Identify one positive trend and one area for improvement", "Set up a weekly email report for your team"],
            },
            {
                "slug": "coaching-playbook",
                "title": "Coaching Your Team",
                "description": "Specific coaching techniques using platform data.",
                "icon": "fitness",
                "duration": "5 min",
                "order": 3,
                "content": "## Coaching Playbook\n\n### The 5-Minute Daily Huddle\nEvery morning, spend 5 minutes with your team:\n1. **Celebrate** — Who had the most touches yesterday?\n2. **Challenge** — Set today's team goal (e.g., \"Everyone send 3 follow-ups\")\n3. **Coach** — Share one quick tip or template\n\n### Weekly 1:1 Format (15 min)\n1. **Review their numbers** (2 min) — Messages, reviews, cards\n2. **Ask what's working** (3 min) — Let them share wins\n3. **Address gaps** (5 min) — Specific coaching on one metric\n4. **Set one goal** (2 min) — One measurable goal for next week\n5. **Encouragement** (3 min) — End positive\n\n### Coaching by Metric\n\n**Low message volume:** Often fear of bothering customers. Role-play with them. Show examples of positive customer responses.\n\n**No review requests:** Usually fear of asking. Practice the script: \"Would you mind leaving me a quick review? It really helps me out.\"\n\n**Not sharing cards:** May not see the value. Show them click analytics — \"Your card was viewed 23 times this month.\"\n\n**Slow response time:** May be checking the app infrequently. Suggest setting notification alerts.\n\n### The Leaderboard\nUse the leaderboard for **positive motivation**, never punishment. Recognize publicly, coach privately.",
                "video_url": "",
                "steps": ["Schedule your first daily huddle", "Prepare talking points for this week's 1:1s", "Identify one team member who needs extra coaching", "Practice the review request script yourself"],
            },
            {
                "slug": "managing-accounts",
                "title": "Managing Team Accounts",
                "description": "Add users, manage permissions, and handle departures.",
                "icon": "settings",
                "duration": "4 min",
                "order": 4,
                "content": "## Managing Team Accounts\n\n### Adding New Team Members\n1. Use the **Setup Wizard** or **Admin > Accounts**\n2. Create their account with temp password\n3. They'll complete profile setup on first login\n4. Assign them to the correct store/location\n\n### When Someone Leaves\n- **Deactivate** their account (don't delete — contacts stay intact)\n- Reassign their active contacts to another team member\n- Their conversation history remains for continuity\n- Their digital card will show a generic company fallback\n\n### Permission Levels\n- **Sales (User)** — Can manage their own contacts and messages\n- **Manager** — Can see team activity, reports, and leaderboards\n- **Admin** — Can manage accounts, settings, and organization config\n\n### Best Practices\n- Always use the **onboarding wizard** for new hires\n- Set up their **message templates** before they start\n- Pair new hires with a **top performer** for their first week\n- Check onboarding completion status in the admin dashboard",
                "video_url": "",
                "steps": ["Review your current team's account status", "Ensure all active users have completed onboarding", "Create a new hire checklist based on this lesson", "Identify any inactive accounts that should be deactivated"],
            },
        ],
    },
]


@router.post("/seed")
async def seed_training_content():
    """Seed the training tracks with placeholder content"""
    db = get_db()
    created = 0
    for track_data in SEED_TRACKS:
        existing = await db.training_tracks.find_one({"slug": track_data["slug"]})
        if existing:
            continue
        lessons = track_data.pop("lessons")
        track_data["created_at"] = datetime.now(timezone.utc)
        track_data["updated_at"] = datetime.now(timezone.utc)
        result = await db.training_tracks.insert_one(track_data)
        track_id = str(result.inserted_id)
        for lesson in lessons:
            lesson["track_id"] = track_id
            lesson["created_at"] = datetime.now(timezone.utc)
            lesson["updated_at"] = datetime.now(timezone.utc)
            await db.training_lessons.insert_one(lesson)
        created += 1
    return {"seeded": created, "total_tracks": len(SEED_TRACKS)}


@router.get("/tracks")
async def get_tracks(request: Request, role: Optional[str] = Query(None)):
    """Get training tracks filtered by role, with lesson counts and user progress"""
    db = get_db()
    user_id = request.headers.get("X-User-ID")

    # Auto-seed if no tracks exist
    count = await db.training_tracks.count_documents({})
    if count == 0:
        await seed_training_content()

    query = {}
    # super_admin and admin see all tracks
    if role and role not in ("super_admin", "admin"):
        query["roles"] = role

    tracks_cursor = db.training_tracks.find(query)
    tracks_raw = await tracks_cursor.to_list(50)
    result = []
    for track in tracks_raw:
        track_id = str(track["_id"])
        lesson_count = await db.training_lessons.count_documents({"track_id": track_id})
        completed = 0
        if user_id:
            completed = await db.training_progress.count_documents({"user_id": user_id, "track_id": track_id, "completed": True})
        result.append({
            "id": track_id,
            "slug": track["slug"],
            "title": track["title"],
            "description": track["description"],
            "icon": track.get("icon"),
            "color": track.get("color"),
            "roles": track.get("roles", []),
            "order": track.get("order", 0),
            "lesson_count": lesson_count,
            "completed_count": completed,
        })
    result.sort(key=lambda x: x["order"])
    return result


@router.get("/tracks/{track_id}")
async def get_track_detail(track_id: str):
    """Get a track with all its lessons"""
    db = get_db()
    track = await db.training_tracks.find_one({"_id": ObjectId(track_id)})
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")
    lessons = await db.training_lessons.find({"track_id": track_id}).sort("order", 1).to_list(50)
    return {
        "id": str(track["_id"]),
        "slug": track["slug"],
        "title": track["title"],
        "description": track["description"],
        "icon": track.get("icon"),
        "color": track.get("color"),
        "roles": track.get("roles", []),
        "lessons": [{
            "id": str(l["_id"]),
            "slug": l["slug"],
            "title": l["title"],
            "description": l.get("description", ""),
            "icon": l.get("icon"),
            "duration": l.get("duration"),
            "order": l.get("order", 0),
            "content": l.get("content", ""),
            "video_url": l.get("video_url", ""),
            "steps": l.get("steps", []),
        } for l in lessons],
    }


@router.get("/progress/{user_id}")
async def get_user_progress(user_id: str):
    """Get all completed lessons for a user"""
    db = get_db()
    progress = await db.training_progress.find({"user_id": user_id}, {"_id": 0}).to_list(200)
    return [{"track_id": p["track_id"], "lesson_id": p["lesson_id"], "completed": p.get("completed", False), "completed_at": p.get("completed_at").isoformat() if p.get("completed_at") else None} for p in progress]


@router.post("/progress")
async def update_progress(request: Request):
    """Mark a lesson as complete or incomplete"""
    db = get_db()
    data = await request.json()
    user_id = data.get("user_id") or request.headers.get("X-User-ID")
    lesson_id = data.get("lesson_id")
    track_id = data.get("track_id")
    completed = data.get("completed", True)

    if not user_id or not lesson_id:
        raise HTTPException(status_code=400, detail="user_id and lesson_id required")

    await db.training_progress.update_one(
        {"user_id": user_id, "lesson_id": lesson_id},
        {"$set": {"track_id": track_id, "completed": completed, "completed_at": datetime.now(timezone.utc) if completed else None}},
        upsert=True,
    )
    return {"success": True}


@router.put("/lessons/{lesson_id}")
async def update_lesson(lesson_id: str, request: Request):
    """Admin: update lesson content"""
    db = get_db()
    data = await request.json()
    allowed = ["title", "description", "content", "video_url", "steps", "duration", "icon", "order"]
    update = {k: v for k, v in data.items() if k in allowed}
    if not update:
        raise HTTPException(status_code=400, detail="No valid fields to update")
    update["updated_at"] = datetime.now(timezone.utc)
    await db.training_lessons.update_one({"_id": ObjectId(lesson_id)}, {"$set": update})
    return {"success": True}


# ---- Admin CRUD for Tracks ----

@router.get("/admin/tracks")
async def admin_list_tracks():
    """Admin: list all tracks with lesson counts"""
    db = get_db()
    tracks_raw = await db.training_tracks.find().sort("order", 1).to_list(50)
    result = []
    for t in tracks_raw:
        tid = str(t["_id"])
        lesson_count = await db.training_lessons.count_documents({"track_id": tid})
        result.append({
            "id": tid,
            "slug": t["slug"],
            "title": t["title"],
            "description": t["description"],
            "icon": t.get("icon"),
            "color": t.get("color"),
            "roles": t.get("roles", []),
            "order": t.get("order", 0),
            "lesson_count": lesson_count,
        })
    return result


@router.put("/admin/tracks/{track_id}")
async def admin_update_track(track_id: str, request: Request):
    """Admin: update track metadata"""
    db = get_db()
    data = await request.json()
    allowed = ["title", "description", "icon", "color", "roles", "order"]
    update = {k: v for k, v in data.items() if k in allowed}
    if not update:
        raise HTTPException(status_code=400, detail="No valid fields to update")
    update["updated_at"] = datetime.now(timezone.utc)
    await db.training_tracks.update_one({"_id": ObjectId(track_id)}, {"$set": update})
    return {"success": True}


@router.post("/admin/tracks")
async def admin_create_track(request: Request):
    """Admin: create a new track"""
    db = get_db()
    data = await request.json()
    track = {
        "slug": data.get("slug", data.get("title", "").lower().replace(" ", "-")),
        "title": data["title"],
        "description": data.get("description", ""),
        "icon": data.get("icon", "book"),
        "color": data.get("color", "#007AFF"),
        "roles": data.get("roles", []),
        "order": data.get("order", 99),
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    result = await db.training_tracks.insert_one(track)
    return {"id": str(result.inserted_id), "success": True}


@router.delete("/admin/tracks/{track_id}")
async def admin_delete_track(track_id: str):
    """Admin: delete a track and its lessons"""
    db = get_db()
    await db.training_lessons.delete_many({"track_id": track_id})
    await db.training_progress.delete_many({"track_id": track_id})
    await db.training_tracks.delete_one({"_id": ObjectId(track_id)})
    return {"success": True}


# ---- Admin CRUD for Lessons ----

@router.get("/admin/tracks/{track_id}/lessons")
async def admin_list_lessons(track_id: str):
    """Admin: list all lessons in a track"""
    db = get_db()
    lessons = await db.training_lessons.find({"track_id": track_id}).sort("order", 1).to_list(100)
    return [{
        "id": str(l["_id"]),
        "slug": l.get("slug", ""),
        "title": l["title"],
        "description": l.get("description", ""),
        "icon": l.get("icon"),
        "duration": l.get("duration"),
        "order": l.get("order", 0),
        "content": l.get("content", ""),
        "video_url": l.get("video_url", ""),
        "steps": l.get("steps", []),
    } for l in lessons]


@router.post("/admin/tracks/{track_id}/lessons")
async def admin_create_lesson(track_id: str, request: Request):
    """Admin: add a new lesson to a track"""
    db = get_db()
    data = await request.json()
    lesson = {
        "track_id": track_id,
        "slug": data.get("slug", data.get("title", "").lower().replace(" ", "-")),
        "title": data["title"],
        "description": data.get("description", ""),
        "icon": data.get("icon", "document-text"),
        "duration": data.get("duration", "5 min"),
        "order": data.get("order", 99),
        "content": data.get("content", ""),
        "video_url": data.get("video_url", ""),
        "steps": data.get("steps", []),
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    result = await db.training_lessons.insert_one(lesson)
    return {"id": str(result.inserted_id), "success": True}


@router.delete("/admin/lessons/{lesson_id}")
async def admin_delete_lesson(lesson_id: str):
    """Admin: delete a lesson"""
    db = get_db()
    await db.training_progress.delete_many({"lesson_id": lesson_id})
    await db.training_lessons.delete_one({"_id": ObjectId(lesson_id)})
    return {"success": True}


@router.post("/reseed")
async def reseed_new_tracks():
    """Seed only new tracks that don't already exist in the DB"""
    db = get_db()
    created = 0
    for track_data in SEED_TRACKS:
        existing = await db.training_tracks.find_one({"slug": track_data["slug"]})
        if existing:
            continue
        td = {k: v for k, v in track_data.items() if k != "lessons"}
        td["created_at"] = datetime.now(timezone.utc)
        td["updated_at"] = datetime.now(timezone.utc)
        result = await db.training_tracks.insert_one(td)
        track_id = str(result.inserted_id)
        for lesson in track_data.get("lessons", []):
            lesson_copy = {**lesson, "track_id": track_id, "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc)}
            await db.training_lessons.insert_one(lesson_copy)
        created += 1
    return {"seeded": created}
