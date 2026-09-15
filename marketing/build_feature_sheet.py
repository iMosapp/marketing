#!/usr/bin/env python3
"""Internal review sheet: every feature in the app with what it does and why it matters.
Edit the data below, run `python3 build_feature_sheet.py`, redeploy marketing. Output: build/feature-sheet/index.html (noindex)."""
import html
import os
from datetime import date

R, M, O, C = "Rep", "Manager", "Owner", "Customer-facing"

SECTIONS = [
    {
        "id": "daily", "tag": "Every day", "color": "#C9A962", "title": "Home, contacts and the daily routine",
        "intro": "What a rep opens first thing in the morning. Everything here is about never letting a relationship go cold.",
        "features": [
            ("People to Talk To Today", "A prioritized list built overnight: touchpoints that are due, hot leads waiting, birthdays and sold-date anniversaries, threads that went quiet. One tap opens the contact or the text.",
             "The rep knows exactly who to reach out to without hunting through a CRM.", [R]),
            ("Contacts (the personal CRM)", "Full customer records: phones (normalized, de-duplicated), vehicle, birthday, anniversary and date sold, tags, notes, photos, plus CSV import with duplicate detection, a merge tool and a duplicate finder.",
             "Every customer in one place on the rep's phone; no spreadsheets or sticky notes.", [R, M]),
            ("Relationship Intel briefing", "Jessi reads the whole history and writes a quick take, two key facts and a 'Next:' step at the top of every contact. It refreshes itself whenever new activity comes in.",
             "Walk into any conversation prepared in ten seconds, even a customer from three years ago.", [R]),
            ("Activity timeline", "Every call, text, card, campaign send, voice memo and AI action on one scrolling feed per contact.",
             "Anyone covering for a rep sees the full story instantly.", [R, M]),
            ("Photo gallery per contact", "Profile photo history, MMS photos texted in or out, delivery photos and card photos; camera or library upload; set any photo as the profile.",
             "The delivery shot and every picture the customer sent live with the customer, not in a camera roll.", [R]),
            ("Voice memos and recorded conversations", "Record a quick note or a live conversation from the contact page. It is transcribed, summarized and turned into follow-up tasks automatically; playback and delete in place.",
             "Details from the lot make it into the record before they are forgotten.", [R]),
            ("Tasks and Team Tasks", "Customer tasks with due dates on each contact and on the calendar. Managers see every open task per rep, overdue first.",
             "Promises to customers get kept, and managers can see which ones are slipping.", [R, M]),
            ("Calendar and calendar sync", "Appointments, tasks, birthdays and sold dates on one calendar, with Google or Apple calendar sync.",
             "The rep's work calendar and personal calendar finally agree.", [R]),
            ("SOLD wizard and Sold Quick", "Mark a sale in seconds: customer, vehicle, backdatable date, delivery photo. It kicks off the congrats card, the review request and the long-term follow-up plan.",
             "One action turns a sale into a lifetime of automated, personal follow-up.", [R]),
            ("Book of Business and Sales List", "Every customer grouped by relationship stage and every sale by month, with referrals and repeat buyers called out.",
             "Reps see the size and health of the book they are building; it goes with them.", [R, M]),
            ("Tags and Keyword Auto-Tags", "Personal, store and org tags on any contact. Keyword rules tag calls and texts automatically (for example 'trade', 'lease end', 'service').",
             "Segments build themselves from what customers actually say.", [R, M]),
            ("Keyword Search", "Search any word or phrase across every text and every call transcript in the account.",
             "Find the customer who 'mentioned a boat' or 'asked about a Tahoe' in seconds.", [R, M]),
            ("Search by name or digits", "Server-side search of the entire contact book by name or by the last digits of a phone number, from the dialer or the contacts tab.",
             "Works even when the rep only remembers part of a number.", [R]),
            ("Home intelligence and notifications center", "Push and in-app notifications for leads, replies, claims, alerts and digests, with per-type preferences and quiet times.",
             "Reps get pinged for what matters and nothing else.", [R, M]),
        ],
    },
    {
        "id": "messaging", "tag": "Messaging and calling", "color": "#007AFF", "title": "Texting, calling and the inbox",
        "intro": "Every rep gets a real business number. Every conversation is one thread, whoever or whatever sent it.",
        "features": [
            ("Dedicated business number per rep", "Each rep texts and calls from their own Twilio number. Inbound texts and calls route to the owning rep; the number stays with the store if the rep leaves.",
             "Customers get one number to remember and the store keeps the relationship.", [R, O]),
            ("Unified Inbox", "SMS and MMS, email, automated sends, cards and call logs in one thread per contact, with media, contact-card tiles, read state and quick filters.",
             "No more 'which app did they text me on'.", [R]),
            ("Shared department inboxes", "One number worked by a team (Sales BDC, Service, Parts). Routing by jump ball, round robin or weighted; claim, assign, hand off with a note; the first reply owns the thread; collaborators are pulled in when the owner is silent or off shift; Jessi sends the first reply; a close tag hands the customer to the rep's own number.",
             "A department line gets answered fast by whoever is free, and nobody steps on each other.", [R, M]),
            ("Dialer with press-1 safety", "Full-screen keypad with search and recents. Click-to-call rings the rep's cell first; the rep presses 1 to connect, so a pocket dial never reaches a customer. Live in-call status and a red hang-up that ends the call server-side.",
             "Calls from the business number, from a cell phone, with zero accidental dials.", [R]),
            ("Call recording and call logs", "Calls record from answer (with consent messaging), land in the contact timeline and the thread with playback, transcript and summary.",
             "Every call is coachable and nothing said on the phone gets lost.", [R, M]),
            ("Inbound call handling", "Customer calls to the business number ring the rep's cell with a whisper ('Call for you from Sarah'), fall back to voicemail, and trigger a missed-call text.",
             "Customers always reach a human or hear back within minutes.", [R, C]),
            ("Call Retries", "When a call hits voicemail the system schedules the retries and sends the 'just tried you' text automatically, with timing you control.",
             "The second and third attempt happen without the rep remembering.", [R, M]),
            ("Broadcast (Send a Blast)", "Mass text from the rep's own number to a tag or a list, scheduled or immediate, with automatic opt-out handling.",
             "Month-end pushes and event invites go out in one tap, compliantly.", [R, M]),
            ("Quick Send", "One-tap sends of the digital card, review link, showcase or a card to any contact, with the message pre-written.",
             "The stuff reps should send after every conversation actually gets sent.", [R]),
            ("Templates and merge fields", "SMS and email templates with merge fields (first name, vehicle, rep name, links), personal and store-level.",
             "Consistent messaging that still reads personal.", [R, M]),
            ("Email with signature and analytics", "Send templated emails from the thread, generate a branded email signature to paste into any mail app, and see opens and clicks.",
             "The rep's brand shows up in every email and they know who is engaging.", [R]),
            ("Quiet hours, opt-in and STOP compliance", "Every automated send waits for 9 AM in the contact's time zone. STOP is honored instantly, opt-in pages capture consent, and the numbers run on a registered A2P 10DLC brand.",
             "Deliverability stays high and the store stays out of trouble.", [O]),
            ("SMS notifications and 'You're Needed' alerts", "The rep gets a text or push when a customer needs a human: Jessi is unsure, a lead is waiting, a thread went quiet.",
             "AI handles the routine; the rep is pulled in at the right moment.", [R]),
        ],
    },
    {
        "id": "jessi", "tag": "Jessi AI", "color": "#AF52DE", "title": "Jessi, the AI that sounds like the rep",
        "intro": "Jessi is trained per rep, knows the inventory, and knows when to hand the conversation back.",
        "features": [
            ("My VA (per-rep AI persona)", "Each rep's Jessi is trained on their tone, brevity, emoji and humor during onboarding and voice training. Stores can also build named Virtual Assistant personas in the VA Library.",
             "Customers cannot tell the AI reply from the rep's own.", [R, M]),
            ("AI replies with escalation", "Per conversation or per campaign: fully automatic, draft-for-approval, or off. Jessi escalates to the rep when she is unsure or the customer asks for a human, and an intent engine with a per-store sensitivity slider flags hot conversations.",
             "Replies in seconds around the clock, with the rep always in control.", [R, M]),
            ("Live inventory in replies", "Jessi quotes real in-stock vehicles (year, make, model, price) and texts the photo, pulled from the store's live inventory.",
             "No made-up cars, no 'let me check and get back to you'.", [R, C]),
            ("Ask Jessi", "Chat with your own book: 'who did I promise a callback this week', 'who mentioned a trade', 'draft a text to everyone with a lease ending in March'.",
             "The rep's memory, searchable in plain English.", [R]),
            ("Ask Jessi About The Team", "Managers ask across every rep: who is waiting on a reply, which calls were missed, who mentioned a trade, what happened yesterday.",
             "Team oversight without opening thirty threads.", [M]),
            ("AI Follow-ups (Relationship Intelligence)", "Jessi suggests who to reach out to and drafts the message based on last contact, sentiment and history.",
             "Warm follow-ups that would otherwise never happen.", [R]),
            ("Help Center AI", "An in-app assistant that knows every guide, SOP and screen and answers 'how do I…' questions with the exact path.",
             "Fewer support calls, faster onboarding.", [R, M, O]),
        ],
    },
    {
        "id": "leads", "tag": "Leads", "color": "#FF3B30", "title": "Internet leads",
        "intro": "Leads arrive from anywhere, get a reply, and reach the right rep so nothing sits unanswered.",
        "features": [
            ("Lead intake from any source", "ADF/XML from the CRM or third-party sites, lead emails parsed automatically, website forms, and Zapier / Make webhooks. Each lead source gets its own webhook URL and forwarding address.",
             "Every source lands in one queue with no re-typing.", [M, O]),
            ("First reply with the vehicle photo", "Jessi texts the lead back, matches the vehicle to live inventory and sends the photo along with the first message, so the rep steps into a conversation that has already started.",
             "Every lead hears back, with the right car, even when the whole team is busy.", [C, M]),
            ("Lead Flows (ring ladder)", "Reusable playbooks: who rings first, then who, how long between attempts, press 1 to claim, 'Ring me & connect' from the app, deferral to opening time when the store is closed, and what Jessi does meanwhile.",
             "A lead at 11 PM rings the right person at 9:05 AM instead of dying in an inbox.", [M]),
            ("Shared lead queue and claiming", "Reps see the queue, claim by answering the ring or tapping in the app; a claimed lead is protected from double-handling.",
             "Fair, fast distribution without a manager refereeing.", [R, M]),
            ("Team availability and shifts", "Who is on shift drives routing; off-shift reps are skipped and collaborators are pulled in when an owner goes quiet.",
             "Leads never route to someone who is off today.", [M]),
            ("Lead response reporting", "Each lead shows when a person replied, with a team view and a per-rep breakdown. Only a human reply counts.",
             "Managers can see how leads are being handled without asking.", [M, O]),
            ("Source ROI", "Monthly cost per source, funnel from lead to sale, cost per lead and per sale, and a monthly ROI email on the 1st.",
             "Know which sites deserve the budget.", [O]),
            ("Connect Zapier / Make and a Setup & Test Guide", "Any app can send leads to a source, and the in-app guide walks through shared inbox, lead source and workflow setup with a test for each step.",
             "A store can be fully wired in an afternoon.", [M, O]),
        ],
    },
    {
        "id": "campaigns", "tag": "Automation", "color": "#FF2D55", "title": "Campaigns and workflows",
        "intro": "Years-long follow-up that reads like the rep wrote it this morning.",
        "features": [
            ("Campaign builder", "Multi-step text and email plans with timing from minutes to years, template or Jessi-personalized, automatic or manual delivery, previewed as a real enrolled person. Start from proven plans.",
             "Set the plan once; every new customer gets it.", [M, R]),
            ("Tag workflows", "What happens when a contact is tagged Sold, Working, Met, Lost and so on: which plan starts, which stops, who Jessi handles.",
             "The tag a rep already applies does all the follow-up work.", [M]),
            ("Date triggers (birthday and anniversary)", "Birthday and sold-date anniversary messages with a card featuring the customer's car. Strictly opt-in per contact, fires only on the day, one send per occasion, and the rep gets an 8 AM preview of who is receiving today.",
             "Hundreds of personal moments a year without a single one going out by mistake.", [R, C]),
            ("Sold workflow", "Delivery congrats card, scheduled delivery-week texts, contact card (VCF) to the customer, review request, then long-term nurture.",
             "The two weeks after delivery, where referrals are won, run themselves.", [R]),
            ("Campaign dashboard", "Live plans, people enrolled, texts this week, what needs fixing, per-plan performance.",
             "Managers see automation working (or not) at a glance.", [M]),
            ("Safety rails", "Quiet hours, same-day guards, single-campaign-per-occasion, idempotent sends and opt-out checks on every automated message.",
             "Nothing double-fires and nothing goes to someone who said stop.", [O]),
        ],
    },
    {
        "id": "brand", "tag": "Personal brand", "color": "#34C759", "title": "Cards, pages, reviews and reputation",
        "intro": "The public-facing side: what customers tap, save and share. It belongs to the rep and follows them.",
        "features": [
            ("Digital business card", "A shareable card at a personal link: text it, QR it, NFC tap it, save to contacts in one tap. Every view is tracked.",
             "Never crumpled in a pocket; the rep knows who looked.", [R, C]),
            ("Link page and personal landing page", "One link with every profile, review page, card and showcase (like Linktree, built for sales), plus a full personal page.",
             "One link in every bio and signature that does everything.", [R, C]),
            ("Showcase", "A gallery of happy customers and deliveries, with manager approval before anything goes public.",
             "Social proof that sells the next car.", [R, M, C]),
            ("Congrats, thank-you, birthday, anniversary and holiday cards", "Branded, trackable cards with the store logo and the customer's photo, sent automatically or on demand; customers share them to social. Card templates are editable per store.",
             "Every sale becomes a post the customer's friends see.", [R, C]),
            ("Create a card to share", "Pick a template and get a trackable link with no recipient needed, for socials, events or signage.",
             "Marketing collateral in a tap.", [R]),
            ("Personal reviews and the Review Center", "A review funnel per rep and store, auto-requested after every sale, with Google / Facebook / Yelp links, template replies and manager approval before publishing.",
             "Reviews the rep owns for life, not a company page they will leave behind.", [R, M, C]),
            ("Print QR and the 4x6 leave-behind card", "A tracked QR for cards, flyers and signs, a print-ready 4x6 card PDF per rep, and scan analytics.",
             "Print finally reports back.", [R, O]),
            ("Share the App", "Personal install link and QR; see who installed from it.",
             "Reps recruit the next reps.", [R]),
            ("Brand kit and store profile", "Logo, colors, address and email branding applied across cards, emails and public pages.",
             "Everything customers see looks like the store.", [O]),
            ("SEO Health and GEO Health", "An online-visibility score and an AI-citation score (how often ChatGPT, Gemini and Perplexity mention the rep or store), each with a fix-it guide.",
             "Be found by search engines and by the AI that customers now ask.", [R, O]),
            ("Your Advocates", "Customers ranked by referrals, repeats and engagement, ready for a thank-you.",
             "The 20% who send the referrals get treated like it.", [R]),
        ],
    },
    {
        "id": "coaching", "tag": "Coaching and quality", "color": "#FF9500", "title": "Scorecards, practice calls, training and certification",
        "intro": "Every real call is graded, every rep can practice against an AI customer, and managers see who needs what.",
        "features": [
            ("Call Scorecards", "Manager-built checklists per department (sales, service BDC, phone-ups) with weights and critical items. Every recorded call is graded by AI within minutes with quoted evidence, a summary, wins and coaching. Managers can override or re-score.",
             "Objective, consistent call coaching without listening to every call.", [M, R]),
            ("Critical-miss alerts", "A missed critical item (no appointment asked, no trade mentioned) pushes the manager right away; reps get their score and top tip when enabled.",
             "Fix the habit the same day it happens.", [M]),
            ("Team Call Scores", "Leaderboard, 'who misses what' heatmap by criterion, alert feed and per-rep drilldowns.",
             "The next sales meeting writes itself.", [M]),
            ("Scripts and Practice Calls", "Printable phone scripts, and practice calls where Jessi phones the rep and plays the customer (real voice, curveballs, objections), then grades the call against the scorecard.",
             "Reps rehearse the hard calls before a real customer is on the line.", [R, M]),
            ("Assign Practice Calls", "Managers pick a script, reps and curveballs; the calls go out on a schedule and results land on the team board.",
             "Training that happens on the phone, where the job is.", [M]),
            ("Courses and Certification", "Enroll reps in a course of challenges; pass every one to earn a certificate with a public verification page.",
             "A visible standard for 'phone ready'.", [M, R]),
            ("Training Hub, SOPs and Company Docs", "Lessons and tracks with video engagement reporting, step-by-step SOPs (with a test at the end of each), and the store's own docs and policies in the app.",
             "New hires learn the platform and the process in one place.", [R, M, O]),
            ("Mystery Shop Program (a service we run)", "Our AI callers phone-shop a store's sales, service, parts and bodyshop people every month as real customers, record and grade every call, and send the GM a monthly report with coaching themes per department. Signed proposal, monthly invoice, no logins needed for the store.",
             "Know how the phones are really answered, every month, for the price of one lost deal.", [O, M]),
            ("Leaderboards and power rankings", "Individual, store and org rankings on activity, engagement and sales.",
             "Healthy competition on the numbers that drive sales.", [R, M, O]),
            ("My Stats and Customer Engagement", "Day / week / month personal performance, plus customers ranked by engagement level.",
             "Reps manage themselves with real numbers.", [R]),
        ],
    },
    {
        "id": "reports", "tag": "Reporting", "color": "#32ADE6", "title": "Reports and intelligence",
        "intro": "Delivered to the inbox and available in the app, for the rep, the manager and the owner.",
        "features": [
            ("Activity reports", "Detailed texting, calling, card and campaign activity by rep, store and org, with daily report delivery.",
             "See effort, not just results.", [M, O]),
            ("Team Sales", "Monthly sold, referrals and repeat buyers by rep.",
             "The report that shows who is building a book, not just hitting a month.", [M, O]),
            ("Weekly coaching digest and monthly reports", "A weekly digest of scores and coaching themes to managers, monthly account-health and ROI emails to owners.",
             "The important numbers arrive without anyone running a report.", [M, O]),
            ("Account Health", "Retention dashboard across every store: usage, engagement, risk flags.",
             "Spot a store going quiet before it churns.", [O]),
            ("Email and card analytics", "Opens, clicks, card views and saves, link clicks (de-duplicated).",
             "Know what customers actually engage with.", [R, M]),
            ("Activity feed", "Live team activity across accounts: sales, cards, reviews, claims.",
             "Momentum is visible to everyone.", [M, O]),
        ],
    },
    {
        "id": "team", "tag": "Management", "color": "#5856D6", "title": "Team, store and org management",
        "intro": "Org to stores to users, with permissions that match the job.",
        "features": [
            ("Hierarchy and roles", "Organization → stores → users, with rep, store manager, org admin and owner roles, permission templates and per-feature access.",
             "Everyone sees exactly what they should, across one store or fifty.", [O]),
            ("Team members, invites and approvals", "Invite by text or email, approve pending signups, manage users and permissions, deactivate cleanly.",
             "Onboarding a new rep takes minutes.", [M, O]),
            ("Bulk transfer", "Move a departing rep's contacts (and their history) to another rep in one action.",
             "Customers stay with the store when people move on.", [M, O]),
            ("Phone numbers", "Twilio number inventory, assignment and billing per rep and per shared inbox.",
             "Numbers are a managed asset, not a mystery.", [O]),
            ("Inventory and the inventory feed", "Vehicle records with photos, status and visibility; HomeNet, vAuto or a catalog link pulled hourly; missing-photo reminders to admins.",
             "Jessi and the lead engine always work from what is really on the lot.", [M, O]),
            ("Team Chat", "Internal messaging for the team, separate from customer threads.",
             "Quick coordination without group texts.", [R, M]),
            ("Store settings", "AI sensitivity, login lockout rules, ROI email recipient, review links, notification rules, messaging channels.",
             "Each store tunes the platform to how it sells.", [M, O]),
            ("Integrations", "API keys, webhooks, Zapier / Make, calendar sync, lead-source connectors.",
             "Fits the tools the store already uses.", [O]),
            ("Onboarding Hub and setup wizard", "Create and onboard new accounts step by step, with progress tracking.",
             "A new store is live the same day.", [O]),
        ],
    },
    {
        "id": "platform", "tag": "Platform", "color": "#8E8E93", "title": "Platform, security, compliance and international",
        "intro": "The parts nobody sees until they matter.",
        "features": [
            ("iPhone, Android and web from one app", "Native apps plus a web version that works on any computer, updated over the air without app-store waits.",
             "Reps use their phone; managers use a desk; everyone sees the same data.", [R, M, O]),
            ("Security", "Encrypted sign-in with Face ID, brute-force lockout, password-reset throttling, object-level authorization on every record, media served only through the app.",
             "Customer data stays with the people who should have it.", [O]),
            ("Compliance", "Registered A2P 10DLC messaging, opt-in / STOP handling, quiet hours, recording consent messaging, per-store policies.",
             "Carrier-friendly and audit-friendly.", [O]),
            ("Support in the app", "Report a Bug with one tap (admins pushed instantly), Help Center, error monitoring for the team.",
             "Problems get to the right person the same hour.", [R, O]),
            ("International: US, UK, Ireland, Netherlands", "Country, language, currency and time zone per store and client. British and Dutch AI voices and vocabulary on calls, Dutch and British client pages, PDFs and emails, local shop numbers (+31, +44), and invoices in GBP / EUR with iDEAL, SEPA and Bacs.",
             "The same platform sells and coaches in London, Dublin and Amsterdam.", [O, C]),
        ],
    },
    {
        "id": "partners", "tag": "Partners and billing", "color": "#E87722", "title": "Partner program and billing",
        "intro": "For resellers and for the owner running the business side.",
        "features": [
            ("Partner Portal", "Partners see their accounts, create quotes, onboard clients and view commission statements and invoices.",
             "A reseller runs their book without calling us.", [O]),
            ("Agreements, NDA and W-9", "E-signed partner agreements, NDA flow and W-9 collection, all in the app.",
             "Paperwork done before the first client.", [O]),
            ("Quotes, discount codes and subscriptions", "Generate subscription quotes, apply promo codes, bill by Stripe; mystery-shop clients get a signed proposal and a monthly invoice.",
             "Selling the platform is as smooth as using it.", [O]),
            ("Billing, revenue and forecast", "Payments, MRR, commissions and a revenue forecast in one dashboard; white-label configuration for branded partners.",
             "The business runs on the same numbers as the product.", [O]),
        ],
    },
]

AUD_COLOR = {R: "#007AFF", M: "#FF9500", O: "#5856D6", C: "#34C759"}


def esc(s):
    return html.escape(s, quote=True)


def chips(auds):
    return "".join(f'<span class="aud" style="--c:{AUD_COLOR[a]}">{esc(a)}</span>' for a in auds)


def render():
    total = sum(len(s["features"]) for s in SECTIONS)
    toc = "".join(f'<a href="#{s["id"]}"><span class="dot" style="background:{s["color"]}"></span>{esc(s["title"])}<em>{len(s["features"])}</em></a>' for s in SECTIONS)
    body = []
    n = 0
    for s in SECTIONS:
        rows = []
        for name, what, why, auds in s["features"]:
            n += 1
            rows.append(f'''<div class="row">
        <div class="c-name"><span class="num">{n:02d}</span><h3>{esc(name)}</h3><div class="auds">{chips(auds)}</div></div>
        <div class="c-what"><span class="lbl">What it does</span>{esc(what)}</div>
        <div class="c-why"><span class="lbl">Why it matters</span>{esc(why)}</div>
      </div>''')
        body.append(f'''<section class="grp" id="{s["id"]}">
      <div class="grp-head">
        <div class="sec-tag" style="color:{s["color"]}">{esc(s["tag"])} · {len(s["features"])} features</div>
        <h2>{esc(s["title"])}</h2>
        <p>{esc(s["intro"])}</p>
      </div>
      <div class="rows">
        <div class="row hdr"><div>Feature</div><div>What it does</div><div>Why it matters</div></div>
        {"".join(rows)}
      </div>
    </section>''')
    return TEMPLATE.replace("{{TOC}}", toc).replace("{{BODY}}", "".join(body)).replace("{{TOTAL}}", str(total)).replace("{{DATE}}", date.today().strftime("%B %Y"))


TEMPLATE = r'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1.0"/>
  <title>Feature Sheet - I'm On Social</title>
  <meta name="robots" content="noindex,nofollow"/>
  <meta name="description" content="Internal review sheet: every feature of I'm On Social with what it does and why it matters."/>
  <link rel="icon" href="/favicon.png"/>
  <link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
  <style>*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{--blue:#007AFF;--blue-dark:#0059CC;--gold:#C9A962;--text:#111;--text-2:#555;--text-3:#888;--bg:#FFF;--bg-2:#F8F9FB;--border:rgba(0,0,0,.06);--border-2:rgba(0,0,0,.1)}
html{scroll-behavior:smooth}
body{font-family:'Inter',-apple-system,BlinkMacSystemFont,sans-serif;background:var(--bg);color:var(--text);line-height:1.6;-webkit-font-smoothing:antialiased}
nav{position:fixed;top:0;left:0;right:0;z-index:1000;transition:all .3s}
nav.scrolled{background:rgba(255,255,255,.96);backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);box-shadow:0 1px 0 var(--border-2)}
.nav-inner{max-width:1200px;margin:0 auto;display:flex;align-items:center;justify-content:space-between;padding:14px 24px}
.logo{display:flex;align-items:center;text-decoration:none}.logo img{height:72px;width:auto}
.nav-cta{display:flex;align-items:center;gap:10px}
.btn-sign{padding:10px 20px;border-radius:980px;font-size:14px;font-weight:600;color:var(--text);text-decoration:none;transition:background .2s}
.btn-sign:hover{background:var(--bg-2)}
.btn-demo{background:var(--blue);padding:10px 24px;border-radius:980px;font-size:14px;font-weight:600;color:#FFF;text-decoration:none;transition:all .25s;box-shadow:0 2px 12px rgba(0,122,255,.25)}
.btn-demo:hover{background:var(--blue-dark);transform:translateY(-1px)}
.page-hero{padding:150px 24px 36px;max-width:1240px;margin:0 auto}
.sec-tag{font-size:12px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;margin-bottom:12px}
.page-hero h1{font-size:46px;font-weight:900;line-height:1.08;letter-spacing:-.035em;margin-bottom:14px;max-width:820px}
.page-hero-sub{font-size:18px;color:var(--text-2);line-height:1.6;max-width:720px}
.hero-meta{display:flex;flex-wrap:wrap;gap:10px;margin-top:22px;align-items:center}
.pill{font-size:13px;font-weight:600;color:var(--text-2);background:var(--bg-2);border:1px solid var(--border-2);border-radius:980px;padding:7px 14px}
.pill.gold{color:#8a6d2b;background:rgba(201,169,98,.12);border-color:rgba(201,169,98,.35)}
.legend{display:flex;flex-wrap:wrap;gap:8px;margin-left:auto;align-items:center;font-size:12px;color:var(--text-3)}
.btn-print{margin-left:6px;background:var(--text);color:#FFF;border:none;border-radius:980px;padding:9px 18px;font-size:13px;font-weight:700;cursor:pointer;font-family:inherit;display:inline-flex;align-items:center;gap:8px}
.btn-print:hover{background:#333}
.wrap{max-width:1240px;margin:0 auto;padding:0 24px 80px;display:grid;grid-template-columns:260px 1fr;gap:40px;align-items:start}
.toc{position:sticky;top:104px;display:flex;flex-direction:column;gap:2px;border:1px solid var(--border-2);border-radius:18px;padding:12px;background:#FFF}
.toc-t{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1.2px;color:var(--text-3);padding:8px 10px 6px}
.toc a{display:flex;align-items:center;gap:10px;font-size:13.5px;font-weight:500;color:var(--text-2);text-decoration:none;padding:8px 10px;border-radius:10px;line-height:1.3}
.toc a:hover{background:var(--bg-2);color:var(--text)}
.toc a em{margin-left:auto;font-style:normal;font-size:11px;color:var(--text-3);font-weight:600}
.dot{width:8px;height:8px;border-radius:50%;flex-shrink:0}
.grp{padding-top:24px;margin-bottom:44px;scroll-margin-top:110px}
.grp-head{margin-bottom:18px;max-width:760px}
.grp-head h2{font-size:28px;font-weight:900;letter-spacing:-.025em;line-height:1.15;margin-bottom:8px}
.grp-head p{font-size:15.5px;color:var(--text-2)}
.rows{border:1px solid var(--border-2);border-radius:18px;overflow:hidden;background:#FFF}
.row{display:grid;grid-template-columns:24% 1fr 32%;gap:0;border-top:1px solid var(--border)}
.row>div{padding:18px 20px;font-size:14.5px;line-height:1.55;color:var(--text-2)}
.row.hdr{background:var(--bg-2);border-top:none}
.row.hdr>div{padding:10px 20px;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1.2px;color:var(--text-3)}
.row:not(.hdr):hover{background:#FCFCFD}
.c-name{border-right:1px solid var(--border)}
.c-name h3{font-size:15.5px;font-weight:700;color:var(--text);line-height:1.3;margin:2px 0 8px}
.num{font-size:11px;font-weight:700;color:var(--text-3);letter-spacing:.5px}
.c-why{background:rgba(201,169,98,.05);border-left:1px solid var(--border);color:var(--text)}
.lbl{display:none}
.auds{display:flex;flex-wrap:wrap;gap:5px}
.aud{font-size:10.5px;font-weight:700;letter-spacing:.3px;color:var(--c);background:color-mix(in srgb,var(--c) 10%,#FFF);border-radius:980px;padding:2px 8px}
.legend .aud{font-size:11px}
footer{border-top:1px solid var(--border);background:var(--bg-2)}
.ft-inner{max-width:1200px;margin:0 auto;padding:40px 24px;display:flex;flex-wrap:wrap;justify-content:space-between;gap:16px;align-items:center}
.ft-copy{font-size:12px;color:var(--text-3)}
.ft-links{display:flex;gap:18px}.ft-links a{font-size:13px;color:var(--text-3);text-decoration:none}.ft-links a:hover{color:var(--blue)}
@media(max-width:1000px){.wrap{grid-template-columns:1fr}.toc{position:static;flex-direction:row;flex-wrap:wrap}.toc-t{display:none}.toc a em{display:none}}
@media(max-width:768px){.page-hero{padding:110px 20px 24px}.page-hero h1{font-size:30px}.page-hero-sub{font-size:15.5px}.wrap{padding:0 14px 60px;gap:20px}.logo img{height:56px}.nav-cta{display:none}
.row{grid-template-columns:1fr}.row.hdr{display:none}.c-name{border-right:none;padding-bottom:6px}.c-what{padding-top:6px}.c-why{border-left:none;border-top:1px dashed var(--border)}
.lbl{display:block;font-size:10.5px;font-weight:700;text-transform:uppercase;letter-spacing:1.2px;color:var(--text-3);margin-bottom:4px}.grp-head h2{font-size:23px}.legend{margin-left:0}}
@media print{nav,.toc,.btn-print,footer,.hero-meta .pill.gold{display:none!important}.page-hero{padding:0 0 16px}.page-hero h1{font-size:26px}.page-hero-sub{font-size:13px}.wrap{display:block;padding:0}.grp{margin-bottom:22px;padding-top:6px;break-inside:auto}.grp-head h2{font-size:18px}.grp-head p{font-size:12px}
.rows{border-radius:6px}.row{break-inside:avoid}.row>div{padding:8px 10px;font-size:10.5px;line-height:1.4}.c-name h3{font-size:11.5px;margin:0 0 4px}.row.hdr>div{padding:5px 10px;font-size:9px}.aud{font-size:8.5px;border:1px solid var(--c)}body{color:#000}}
</style>
</head>
<body>
<nav>
  <div class="nav-inner">
    <a href="/" class="logo"><img src="/logo.png" alt="I'm On Social"/></a>
    <div class="nav-cta">
      <a href="https://app.imonsocial.com" class="btn-sign">Sign In</a>
      <a href="/demo" class="btn-demo">Book a Demo</a>
    </div>
  </div>
</nav>
<section class="page-hero">
  <div class="sec-tag" style="color:#C9A962">Feature sheet · internal review copy</div>
  <h1>Everything in I'm On Social, on one sheet.</h1>
  <p class="page-hero-sub">{{TOTAL}} features grouped by what they are for, each with a plain description and the reason it exists. Not everyone will use everything; the point is that every rep, manager and owner finds the handful that changes their week.</p>
  <div class="hero-meta">
    <span class="pill">{{TOTAL}} features</span><span class="pill">11 areas</span><span class="pill gold">Internal review copy</span>
    <div class="legend">Who it is for: <span class="aud" style="--c:#007AFF">Rep</span><span class="aud" style="--c:#FF9500">Manager</span><span class="aud" style="--c:#5856D6">Owner</span><span class="aud" style="--c:#34C759">Customer-facing</span>
      <button class="btn-print" onclick="window.print()"><i class="fa-solid fa-print"></i> Print / save PDF</button></div>
  </div>
</section>
<div class="wrap">
  <aside class="toc"><div class="toc-t">Jump to</div>{{TOC}}</aside>
  <main>{{BODY}}</main>
</div>
<footer>
  <div class="ft-inner">
    <span class="ft-copy">&copy; 2026 I'm On Social. Powered by VI Ventures Group LLC. Internal review sheet, not indexed.</span>
    <div class="ft-links"><a href="/">Home</a><a href="/platform/">The Full Platform</a><a href="/pricing/">Pricing</a><a href="https://app.imonsocial.com">Sign In</a></div>
  </div>
</footer>
<script>const _sc=()=>document.querySelector('nav').classList.toggle('scrolled',scrollY>40);window.addEventListener('scroll',_sc);_sc();</script>
</body>
</html>
'''

if __name__ == "__main__":
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "build", "feature-sheet", "index.html")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        f.write(render())
    print("wrote", out, sum(len(s["features"]) for s in SECTIONS), "features")
