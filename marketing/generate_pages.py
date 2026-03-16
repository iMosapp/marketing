#!/usr/bin/env python3
"""Generate all branded marketing pages from templates."""
import os

PAGES = {
    "digital-card": {
        "title": "Digital Business Cards",
        "tagline": "Paper cards end up in the trash. Yours won't.",
        "desc": "A digital business card that's shareable via text, email, QR code, or NFC tap. It links to your reviews, social profiles, and contact info. And you know exactly when someone views it.",
        "features": [
            ("fa-solid fa-share-nodes", "#007AFF", "Share anywhere", "Text it, email it, QR it, NFC tap it. One card, every channel."),
            ("fa-solid fa-eye", "#34C759", "Track every view", "Know exactly who viewed your card, when, and how many times."),
            ("fa-solid fa-link", "#AF52DE", "All your links", "Reviews, social profiles, contact info, showcase page — all connected in one tap."),
            ("fa-solid fa-address-book", "#FF9500", "Save to contacts", "One tap and you're in their phone permanently. Not crumpled in a pocket."),
            ("fa-solid fa-palette", "#FF2D55", "Your brand, your style", "Customize colors, photo, bio, and links. Make it unmistakably you."),
            ("fa-solid fa-chart-line", "#007AFF", "Analytics built in", "See how many people you're reaching. Track shares, views, and saves over time."),
        ],
    },
    "reviews": {
        "title": "Personal Reviews",
        "tagline": "Your reputation should follow you for life.",
        "desc": "When a customer raves about you, that review belongs to you — not a company Google page. Build a personal review profile that moves with you, job to job, company to company.",
        "features": [
            ("fa-solid fa-user-shield", "#007AFF", "Reviews that are yours", "Not tied to a company. Not on a Google page you'll never own. These are YOUR reviews."),
            ("fa-solid fa-suitcase-rolling", "#34C759", "Portable reputation", "Switch jobs, switch industries — your 5-star track record comes with you."),
            ("fa-solid fa-paper-plane", "#FF9500", "Auto-request reviews", "After every sale, automatically invite customers to leave you a review."),
            ("fa-solid fa-star", "#FFD60A", "Personal rating score", "Customers see your average rating before they ever walk in the door."),
            ("fa-solid fa-id-card", "#AF52DE", "Connected to your card", "Your reviews show on your digital card automatically. Social proof built in."),
            ("fa-solid fa-chart-simple", "#FF2D55", "Track your growth", "Watch your review count and rating climb over time. Proof you're the real deal."),
        ],
    },
    "showcase": {
        "title": "Link Pages & Showcase",
        "tagline": "One link for everything you do.",
        "desc": "Your Instagram, TikTok, Google reviews, YouTube, digital card, and more — all in one beautiful, shareable link page. Like a Linktree built specifically for sales professionals.",
        "features": [
            ("fa-solid fa-link", "#007AFF", "One link, everything", "Stop sending five different links. Send one that has it all."),
            ("fa-solid fa-mobile-screen", "#34C759", "Mobile-first design", "Looks amazing on any phone. Because that's where your customers are."),
            ("fa-solid fa-share-nodes", "#AF52DE", "Easy to share", "Put it in your email signature, social bios, or text it directly."),
            ("fa-solid fa-palette", "#FF9500", "Fully customizable", "Match your brand colors. Add your photo. Make it yours."),
            ("fa-solid fa-chart-line", "#FF2D55", "Click tracking", "See which links get the most clicks. Know what your audience cares about."),
            ("fa-solid fa-plug", "#007AFF", "Always connected", "Links to your digital card, review page, and social profiles automatically."),
        ],
    },
    "congrats-template": {
        "title": "Congrats Cards",
        "tagline": "Celebrate every sale. Automatically.",
        "desc": "Every time you close a deal, a branded congrats card gets sent to your customer. It links to your review page, social profiles, and digital card — turning every sale into a referral machine.",
        "features": [
            ("fa-solid fa-wand-magic-sparkles", "#007AFF", "Fully automated", "Close the deal. The card sends itself. You look amazing without lifting a finger."),
            ("fa-solid fa-image", "#FF2D55", "Branded & beautiful", "Your photo, your name, your store's branding. Professional and personal."),
            ("fa-solid fa-star", "#FFD60A", "Drives reviews", "Every congrats card links directly to your review page. Reviews on autopilot."),
            ("fa-solid fa-share-nodes", "#34C759", "Shareable by customers", "Customers share their congrats card on social media. Free marketing for you."),
            ("fa-solid fa-id-card", "#AF52DE", "Links to your card", "Your digital card is one tap away. Stay top of mind after every sale."),
            ("fa-solid fa-repeat", "#FF9500", "Referral engine", "Happy customers tell friends. Congrats cards make it easy for them."),
        ],
    },
    "date-triggers": {
        "title": "Automated Campaigns",
        "tagline": "Your customers think you have a photographic memory.",
        "desc": "Birthday messages. Anniversary cards. Sold-date follow-ups. Holiday greetings. All sent automatically, all feeling personal. Your customers think you remembered. You didn't lift a finger.",
        "features": [
            ("fa-solid fa-cake-candles", "#FF2D55", "Birthday messages", "Never miss a birthday again. Automatic, personal, and on time — every single year."),
            ("fa-solid fa-calendar-check", "#007AFF", "Anniversary follow-ups", "One year since the sale? Two years? Reach out automatically at every milestone."),
            ("fa-solid fa-snowflake", "#34C759", "Holiday greetings", "Thanksgiving, Christmas, New Year's — stay top of mind during every holiday."),
            ("fa-solid fa-sliders", "#FF9500", "Per-contact control", "Pause or customize automations for any contact with one tap."),
            ("fa-solid fa-comment-dots", "#AF52DE", "SMS & email", "Send via text message, email, or both. Your choice per campaign."),
            ("fa-solid fa-bolt", "#FFD60A", "Set it and forget it", "Turn it on once. It works for you 24/7, 365 days a year."),
        ],
    },
    "inbox": {
        "title": "Inbox & Messaging",
        "tagline": "Every conversation. One place.",
        "desc": "SMS, email, automated messages — all in one unified thread per contact. Track opens, clicks, and replies. Know exactly when to follow up and what to say.",
        "features": [
            ("fa-solid fa-inbox", "#007AFF", "Unified inbox", "SMS and email in one thread. No switching between apps."),
            ("fa-solid fa-chart-bar", "#34C759", "Open & click tracking", "Know when someone opens your message or clicks your link. Follow up at the perfect time."),
            ("fa-solid fa-robot", "#AF52DE", "Auto + manual", "Automated messages and personal replies live side by side. Seamless."),
            ("fa-solid fa-users", "#FF9500", "Per-contact threads", "Every contact has their own conversation history. Nothing gets lost."),
            ("fa-solid fa-link", "#FF2D55", "Trackable links", "Every link you send is tracked. Know exactly what drives engagement."),
            ("fa-solid fa-mobile-screen", "#007AFF", "Works on any device", "Full inbox on desktop, tablet, or phone. Stay connected everywhere."),
        ],
    },
    "jessi": {
        "title": "Jessi AI Assistant",
        "tagline": "AI-powered relationship intelligence.",
        "desc": "Ask Jessi anything about your contacts, your performance, or what to do next. She knows your data, understands your goals, and gives you actionable advice in seconds.",
        "features": [
            ("fa-solid fa-wand-magic-sparkles", "#AF52DE", "Ask anything", "\"Who haven't I talked to in 30 days?\" \"What should I send Mike for his birthday?\" Jessi knows."),
            ("fa-solid fa-brain", "#007AFF", "Knows your data", "Jessi has context on your contacts, conversations, and activity. No setup required."),
            ("fa-solid fa-lightbulb", "#FFD60A", "Actionable suggestions", "Not just answers — Jessi tells you exactly what to do next and why."),
            ("fa-solid fa-clock-rotate-left", "#34C759", "Conversation memory", "Jessi remembers what you've asked before. Your AI assistant gets smarter over time."),
            ("fa-solid fa-shield-halved", "#FF9500", "Private & secure", "Your data stays yours. Jessi only sees what you share with her."),
            ("fa-solid fa-rocket", "#FF2D55", "Always improving", "New capabilities added regularly. Jessi keeps getting better at helping you win."),
        ],
    },
    "leaderboard": {
        "title": "Leaderboards",
        "tagline": "See who's actually building relationships.",
        "desc": "Cards shared, reviews collected, engagement driven — all tracked. Store-level, org-level, and individual rankings that reward the salespeople who do the work.",
        "features": [
            ("fa-solid fa-trophy", "#FFD60A", "Performance rankings", "See who's on top. Cards shared, reviews earned, messages sent — all ranked."),
            ("fa-solid fa-building", "#007AFF", "Multi-level views", "Individual, store, and organization-wide leaderboards. See the full picture."),
            ("fa-solid fa-fire", "#FF3B30", "Friendly competition", "Nothing motivates a sales team like a little healthy competition."),
            ("fa-solid fa-chart-line", "#34C759", "Track over time", "See trends, streaks, and progress. Who's improving? Who needs help?"),
            ("fa-solid fa-award", "#AF52DE", "Recognition built in", "Top performers get visibility. Great work doesn't go unnoticed."),
            ("fa-solid fa-users", "#FF9500", "Team accountability", "Managers see who's putting in the work. No more guessing."),
        ],
    },
    "organizations": {
        "title": "For Organizations",
        "tagline": "Your team. Your brand. One platform.",
        "desc": "Manage your entire organization — stores, managers, and salespeople — all under one roof. Consistent branding, centralized analytics, and full control over who does what.",
        "features": [
            ("fa-solid fa-sitemap", "#007AFF", "Org structure", "Set up your organization, stores, and team members. Mirrors your real-world structure."),
            ("fa-solid fa-palette", "#FF2D55", "Brand consistency", "Every team member's digital card, congrats cards, and outreach matches your brand."),
            ("fa-solid fa-chart-pie", "#34C759", "Centralized analytics", "See performance across your entire organization in one dashboard."),
            ("fa-solid fa-user-shield", "#FF9500", "Role-based access", "Admins, managers, and salespeople each see what they need. Nothing more, nothing less."),
            ("fa-solid fa-users-gear", "#AF52DE", "Team management", "Add, remove, and manage team members. Transfer contacts when someone leaves."),
            ("fa-solid fa-trophy", "#FFD60A", "Leaderboards", "Motivate your team with competitive rankings across stores and individuals."),
        ],
    },
    "individuals": {
        "title": "For Individuals",
        "tagline": "Own your personal brand.",
        "desc": "You don't need a company behind you. i'M On Social gives every individual salesperson the same tools the big teams use — digital cards, personal reviews, automated outreach, and analytics.",
        "features": [
            ("fa-solid fa-user", "#007AFF", "Your own profile", "Digital card, review page, and link page — all yours, all free to start."),
            ("fa-solid fa-star", "#FFD60A", "Build your reputation", "Collect reviews that follow you. Build credibility that outlasts any employer."),
            ("fa-solid fa-bolt", "#34C759", "Automate your follow-up", "Birthday messages, anniversaries, congrats cards — all on autopilot."),
            ("fa-solid fa-chart-line", "#AF52DE", "Track your impact", "See how many people view your card, click your links, and leave reviews."),
            ("fa-solid fa-suitcase", "#FF9500", "Take it with you", "Switch companies? Your reviews, contacts, and reputation come with you."),
            ("fa-solid fa-rocket", "#FF2D55", "Stand out", "In a world of generic salespeople, be the one with a brand."),
        ],
    },
    "pricing": {
        "title": "Pricing",
        "tagline": "Simple pricing. No surprises.",
        "desc": "Start free. Upgrade when you're ready. Every plan includes your digital card, review page, and link page.",
        "features": [
            ("fa-solid fa-gift", "#34C759", "Free to start", "Get your digital card, review page, and link page at no cost. No credit card required."),
            ("fa-solid fa-bolt", "#007AFF", "Pro features", "Unlock automated campaigns, analytics, inbox, and AI assistant when you upgrade."),
            ("fa-solid fa-building", "#AF52DE", "Team plans", "Organization-wide features, leaderboards, and centralized management for teams."),
            ("fa-solid fa-headset", "#FF9500", "Priority support", "Get help when you need it. Our team is here for you."),
            ("fa-solid fa-infinity", "#FF2D55", "No limits", "Unlimited cards shared, unlimited reviews, unlimited contacts on paid plans."),
            ("fa-solid fa-hand-holding-dollar", "#FFD60A", "ROI in days", "One referral from a past customer pays for a year of the platform."),
        ],
    },
    "demo": {
        "title": "Schedule a Demo",
        "tagline": "See how it works in 15 minutes.",
        "desc": "We'll walk you through the platform, show you how it fits your workflow, and answer every question. No pressure, no commitment — just a conversation about how to build your brand.",
        "features": [
            ("fa-solid fa-clock", "#007AFF", "15 minutes", "Quick, focused, and respectful of your time. We get right to what matters to you."),
            ("fa-solid fa-user-check", "#34C759", "Personalized walkthrough", "We show you the features that matter most for YOUR role and industry."),
            ("fa-solid fa-question", "#FF9500", "Ask anything", "Pricing, setup, integrations, team rollout — nothing is off limits."),
            ("fa-solid fa-handshake", "#AF52DE", "No pressure", "We're not here to hard sell you. We're here to help you decide if this is right."),
            ("fa-solid fa-rocket", "#FF2D55", "Start same day", "If you love it, you can be live the same day. It's that fast."),
            ("fa-solid fa-gift", "#FFD60A", "Free trial included", "Every demo comes with access to a free trial. Try before you buy."),
        ],
    },
    "training": {
        "title": "Training Hub",
        "tagline": "Get the most out of every feature.",
        "desc": "Courses, videos, and best practices built for salespeople. Whether you're brand new or a power user, there's always something to learn.",
        "features": [
            ("fa-solid fa-graduation-cap", "#007AFF", "Step-by-step courses", "From setup to advanced strategies, we walk you through everything."),
            ("fa-solid fa-play", "#FF2D55", "Video tutorials", "Watch and learn. Short, focused videos for every feature."),
            ("fa-solid fa-lightbulb", "#FFD60A", "Best practices", "Tips from top-performing salespeople who use the platform every day."),
            ("fa-solid fa-users", "#34C759", "Team onboarding", "Get your whole team up to speed fast with group training resources."),
            ("fa-solid fa-book", "#AF52DE", "Always updated", "New features? New training. We keep the content fresh."),
            ("fa-solid fa-headset", "#FF9500", "Live support", "Stuck on something? Reach out and we'll help you figure it out."),
        ],
    },
    "help": {
        "title": "Help Center",
        "tagline": "We've got answers.",
        "desc": "Guides, FAQs, and direct support for everything you need. If you can't find it here, just ask — we're real people and we respond fast.",
        "features": [
            ("fa-solid fa-magnifying-glass", "#007AFF", "Search & find", "Quickly find answers to the most common questions."),
            ("fa-solid fa-book-open", "#34C759", "Detailed guides", "Step-by-step walkthroughs for every feature and workflow."),
            ("fa-solid fa-comments", "#AF52DE", "Direct support", "Can't find what you need? Reach out to our team directly."),
            ("fa-solid fa-clock", "#FF9500", "Fast responses", "We're real people who care about your experience. Expect a quick reply."),
            ("fa-solid fa-circle-check", "#FFD60A", "Getting started", "New here? Start with our quick setup guide and be live in 5 minutes."),
            ("fa-solid fa-bug", "#FF2D55", "Report an issue", "Something not working right? Let us know and we'll fix it fast."),
        ],
    },
    "hub": {
        "title": "Sales Teams",
        "tagline": "Built for any team. Any industry. Any size.",
        "desc": "Whether you run a 5-person office or a 500-person sales floor, i'M On Social scales with you. Give every salesperson the tools to build relationships — and give managers the visibility to track it.",
        "features": [
            ("fa-solid fa-users", "#007AFF", "Team-wide rollout", "Onboard your whole team in minutes. Everyone gets their own card, reviews, and outreach."),
            ("fa-solid fa-chart-pie", "#34C759", "Manager dashboards", "See who's sharing cards, earning reviews, and driving engagement."),
            ("fa-solid fa-trophy", "#FFD60A", "Leaderboards", "Friendly competition that motivates the whole team to do more."),
            ("fa-solid fa-palette", "#FF2D55", "Brand control", "Ensure everyone's cards and outreach match your company's brand."),
            ("fa-solid fa-user-plus", "#AF52DE", "Easy onboarding", "New hire? They're set up and live in under 5 minutes."),
            ("fa-solid fa-arrow-right-arrow-left", "#FF9500", "Data portability", "When someone leaves, their contacts and data transfer seamlessly."),
        ],
    },
    "salespresentation": {
        "title": "Automotive",
        "tagline": "Built for dealerships. Built for you.",
        "desc": "Sell a car. Send a congrats card. Earn a review. Get a referral. Repeat. i'M On Social turns every sale into a long-term relationship that brings customers back — and brings their friends.",
        "features": [
            ("fa-solid fa-car", "#007AFF", "Built for auto sales", "Designed around the way dealerships actually work. Not a generic tool."),
            ("fa-solid fa-image", "#FF2D55", "Congrats on every sale", "Branded congrats card sent to every buyer. They share it. You get the referral."),
            ("fa-solid fa-star", "#FFD60A", "Portable reviews", "Switch dealerships and keep every review. Your reputation follows YOU."),
            ("fa-solid fa-cake-candles", "#34C759", "Automated follow-ups", "Birthday texts, service reminders, anniversary messages — all automatic."),
            ("fa-solid fa-trophy", "#AF52DE", "Dealership leaderboards", "See who's building the most relationships. Motivate the whole floor."),
            ("fa-solid fa-id-card", "#FF9500", "Digital cards for every rep", "No more paper cards in cup holders. Shareable, trackable, and always up to date."),
        ],
    },
    "presentation": {
        "title": "Sales Deck",
        "tagline": "See what we can do for you.",
        "desc": "A quick overview of everything i'M On Social offers — from digital cards to automated outreach to AI-powered insights. Share it with your team or your boss.",
        "features": [
            ("fa-solid fa-play", "#007AFF", "Quick overview", "Everything you need to know about the platform in a few minutes."),
            ("fa-solid fa-share", "#34C759", "Easy to share", "Send it to your manager, your team, or anyone who needs to see it."),
            ("fa-solid fa-list-check", "#FF9500", "Feature breakdown", "Every feature explained clearly. No jargon, no fluff."),
            ("fa-solid fa-chart-line", "#AF52DE", "ROI case studies", "Real examples of how salespeople are using the platform to grow."),
            ("fa-solid fa-question", "#FFD60A", "FAQ included", "Common questions answered upfront. Less back and forth."),
            ("fa-solid fa-rocket", "#FF2D55", "Ready to start?", "Link to sign up or schedule a demo built right in."),
        ],
    },
    "features": {
        "title": "All Features",
        "tagline": "Everything a salesperson needs. One platform.",
        "desc": "Digital cards, personal reviews, automated campaigns, unified inbox, AI assistant, leaderboards, and more. Every tool is connected. Every interaction is tracked. Every relationship is nurtured.",
        "features": [
            ("fa-solid fa-id-card", "#007AFF", "Digital Business Cards", "Shareable, trackable, always up to date. Replace paper forever."),
            ("fa-solid fa-star", "#FFD60A", "Personal Reviews", "Portable reputation that belongs to you, not your company."),
            ("fa-solid fa-bolt", "#34C759", "Automated Campaigns", "Birthdays, anniversaries, follow-ups — all on autopilot."),
            ("fa-solid fa-inbox", "#AF52DE", "Unified Inbox", "SMS, email, and auto-messages in one thread per contact."),
            ("fa-solid fa-wand-magic-sparkles", "#FF2D55", "Jessi AI Assistant", "AI-powered insights and suggestions for your relationships."),
            ("fa-solid fa-trophy", "#FF9500", "Leaderboards", "Track and rank performance across individuals, stores, and orgs."),
        ],
    },
    "privacy": {
        "title": "Privacy Policy",
        "tagline": "Your data. Your rules.",
        "desc": "We take your privacy seriously. Here's how we handle your data, protect your information, and give you control over your account.",
        "features": [
            ("fa-solid fa-shield-halved", "#007AFF", "Data protection", "Your data is encrypted in transit and at rest. Industry-standard security."),
            ("fa-solid fa-user-lock", "#34C759", "You own your data", "Your reviews, contacts, and profile are yours. Export anytime."),
            ("fa-solid fa-eye-slash", "#AF52DE", "No selling your data", "We never sell your personal information to third parties. Period."),
            ("fa-solid fa-trash-can", "#FF3B30", "Delete anytime", "Want out? You can delete your account and data at any time."),
            ("fa-solid fa-cookie-bite", "#FF9500", "Minimal cookies", "We only use cookies that are necessary for the platform to work."),
            ("fa-solid fa-gavel", "#FFD60A", "Compliant", "Built with privacy regulations in mind. We follow best practices."),
        ],
    },
    "terms": {
        "title": "Terms of Service",
        "tagline": "Fair terms. No tricks.",
        "desc": "Our terms are straightforward. Use the platform, build your brand, own your data. Here's the legal version of that.",
        "features": [
            ("fa-solid fa-file-contract", "#007AFF", "Clear terms", "Written in plain language. No legal tricks or hidden clauses."),
            ("fa-solid fa-user-check", "#34C759", "Your content is yours", "Everything you create on the platform belongs to you."),
            ("fa-solid fa-handshake", "#AF52DE", "Fair use", "Use the platform for its intended purpose. We'll treat you right."),
            ("fa-solid fa-ban", "#FF3B30", "No spam", "Don't use the platform to spam people. Build real relationships."),
            ("fa-solid fa-arrow-right-from-bracket", "#FF9500", "Cancel anytime", "No long-term contracts. Cancel whenever you want."),
            ("fa-solid fa-scale-balanced", "#FFD60A", "Dispute resolution", "If something goes wrong, we'll work it out fairly and quickly."),
        ],
    },
}

NAV_HTML = """<nav>
  <div class="nav-inner">
    <a href="/" class="logo"><img src="/logo.png" alt="i'M On Social"/></a>
    <div class="nav-links">
      <div class="nav-item"><button class="nav-trigger">Products <i class="fa-solid fa-chevron-down chev"></i></button>
        <div class="nav-dd"><div class="nav-dd-inner">
          <div class="nav-dd-label">Your Digital Presence</div>
          <a class="dd-link" href="/digital-card"><div class="dd-ico" style="background:rgba(0,122,255,.08)"><i class="fa-regular fa-id-card" style="color:#007AFF"></i></div><div class="dd-txt"><strong>Digital Cards</strong><span>Shareable, trackable business cards</span></div></a>
          <a class="dd-link" href="/reviews"><div class="dd-ico" style="background:rgba(255,214,10,.1)"><i class="fa-regular fa-star" style="color:#D4AD00"></i></div><div class="dd-txt"><strong>Personal Reviews</strong><span>Portable reputation that follows you</span></div></a>
          <a class="dd-link" href="/showcase"><div class="dd-ico" style="background:rgba(52,199,89,.08)"><i class="fa-solid fa-share-nodes" style="color:#34C759"></i></div><div class="dd-txt"><strong>Link Pages</strong><span>All your socials in one link</span></div></a>
          <div class="nav-dd-label">Engagement</div>
          <a class="dd-link" href="/congrats-template"><div class="dd-ico" style="background:rgba(255,45,85,.08)"><i class="fa-regular fa-image" style="color:#FF2D55"></i></div><div class="dd-txt"><strong>Congrats Cards</strong><span>Celebrate every sale automatically</span></div></a>
          <a class="dd-link" href="/date-triggers"><div class="dd-ico" style="background:rgba(255,149,0,.08)"><i class="fa-solid fa-rocket" style="color:#FF9500"></i></div><div class="dd-txt"><strong>Automated Campaigns</strong><span>Birthdays, follow-ups, on autopilot</span></div></a>
          <a class="dd-link" href="/inbox"><div class="dd-ico" style="background:rgba(88,86,214,.08)"><i class="fa-regular fa-comment-dots" style="color:#5856D6"></i></div><div class="dd-txt"><strong>Inbox & Messaging</strong><span>SMS, email, all in one place</span></div></a>
          <div class="nav-dd-label">Intelligence</div>
          <a class="dd-link" href="/jessi"><div class="dd-ico" style="background:rgba(175,82,222,.08)"><i class="fa-solid fa-wand-magic-sparkles" style="color:#AF52DE"></i></div><div class="dd-txt"><strong>Jessi AI</strong><span>AI-powered relationship insights</span></div></a>
          <a class="dd-link" href="/leaderboard"><div class="dd-ico" style="background:rgba(255,59,48,.08)"><i class="fa-solid fa-trophy" style="color:#FF3B30"></i></div><div class="dd-txt"><strong>Leaderboards</strong><span>Track performance across teams</span></div></a>
        </div></div>
      </div>
      <div class="nav-item"><button class="nav-trigger">Solutions <i class="fa-solid fa-chevron-down chev"></i></button>
        <div class="nav-dd"><div class="nav-dd-inner">
          <div class="nav-dd-label">By Role</div>
          <a class="dd-link" href="/organizations"><div class="dd-ico" style="background:rgba(0,122,255,.08)"><i class="fa-solid fa-building" style="color:#007AFF"></i></div><div class="dd-txt"><strong>For Organizations</strong><span>Manage teams, stores & reputation</span></div></a>
          <a class="dd-link" href="/individuals"><div class="dd-ico" style="background:rgba(201,169,98,.08)"><i class="fa-solid fa-user" style="color:#C9A962"></i></div><div class="dd-txt"><strong>For Individuals</strong><span>Own your personal brand</span></div></a>
          <div class="nav-dd-label">By Industry</div>
          <a class="dd-link" href="/salespresentation"><div class="dd-ico" style="background:rgba(52,199,89,.08)"><i class="fa-solid fa-car" style="color:#34C759"></i></div><div class="dd-txt"><strong>Automotive</strong><span>Built for dealerships</span></div></a>
          <a class="dd-link" href="/hub"><div class="dd-ico" style="background:rgba(255,149,0,.08)"><i class="fa-solid fa-briefcase" style="color:#FF9500"></i></div><div class="dd-txt"><strong>Sales Teams</strong><span>Any industry, any size</span></div></a>
        </div></div>
      </div>
      <div class="nav-item"><button class="nav-trigger">Resources <i class="fa-solid fa-chevron-down chev"></i></button>
        <div class="nav-dd"><div class="nav-dd-inner">
          <a class="dd-link" href="/training"><div class="dd-ico" style="background:rgba(0,122,255,.08)"><i class="fa-solid fa-graduation-cap" style="color:#007AFF"></i></div><div class="dd-txt"><strong>Training Hub</strong><span>Courses, videos & best practices</span></div></a>
          <a class="dd-link" href="/help"><div class="dd-ico" style="background:rgba(52,199,89,.08)"><i class="fa-regular fa-circle-question" style="color:#34C759"></i></div><div class="dd-txt"><strong>Help Center</strong><span>Guides, FAQs & support</span></div></a>
          <a class="dd-link" href="/presentation"><div class="dd-ico" style="background:rgba(255,149,0,.08)"><i class="fa-solid fa-play" style="color:#FF9500"></i></div><div class="dd-txt"><strong>Sales Deck</strong><span>See what we can do for you</span></div></a>
        </div></div>
      </div>
      <div class="nav-item"><a href="/pricing">Pricing</a></div>
    </div>
    <div class="nav-cta">
      <a href="https://app.imonsocial.com" class="btn-sign">Sign In</a>
      <a href="/demo" class="btn-demo">Get a Demo</a>
    </div>
    <button class="hamburger" onclick="document.getElementById('mob').classList.toggle('open')" aria-label="Menu"><i class="fa-solid fa-bars"></i></button>
  </div>
  <div class="mob-menu" id="mob">
    <a href="/digital-card">Digital Cards</a><a href="/reviews">Reviews</a><a href="/inbox">Inbox</a><a href="/organizations">Organizations</a><a href="/pricing">Pricing</a><a href="https://app.imonsocial.com">Sign In</a><a href="/demo" class="mob-cta">Get a Demo</a>
  </div>
</nav>"""

FOOTER_HTML = """<footer>
  <div class="ft-inner">
    <div class="ft-brand"><div class="ft-logo"><img src="/logo.png" alt="i'M On Social"/></div><p class="ft-tag">The relationship engine for sales professionals.</p>
      <div class="ft-social"><a href="https://instagram.com/imonsocialapp" target="_blank" rel="noopener"><i class="fa-brands fa-instagram"></i></a><a href="https://tiktok.com/@imonsocialapp" target="_blank" rel="noopener"><i class="fa-brands fa-tiktok"></i></a><a href="https://youtube.com/@imonsocial" target="_blank" rel="noopener"><i class="fa-brands fa-youtube"></i></a></div>
    </div>
    <div class="ft-col"><div class="ft-col-t">Product</div><a href="/digital-card">Digital Cards</a><a href="/reviews">Personal Reviews</a><a href="/inbox">Inbox</a><a href="/date-triggers">Automations</a><a href="/leaderboard">Leaderboards</a><a href="/jessi">Jessi AI</a></div>
    <div class="ft-col"><div class="ft-col-t">Company</div><a href="/organizations">For Teams</a><a href="/pricing">Pricing</a><a href="/privacy">Privacy</a><a href="/terms">Terms</a><a href="mailto:forest@imonsocial.com">Contact</a></div>
    <div class="ft-col"><div class="ft-col-t">Get Started</div><a href="/demo">Schedule a Demo</a><a href="https://app.imonsocial.com/auth/signup">Start Free Trial</a><a href="https://app.imonsocial.com">Sign In</a><a href="/training">Training</a><a href="/help">Help Center</a></div>
  </div>
  <div class="ft-bottom"><span class="ft-copy">&copy; 2026 i'M On Social. All rights reserved.</span></div>
</footer>"""

CSS = open("/app/marketing/build/shared.css").read()

TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1.0"/>
  <title>{title} — i'M On Social</title>
  <meta name="description" content="{desc}"/>
  <link rel="icon" href="/favicon.png"/>
  <link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
  <style>{css}</style>
</head>
<body>
{nav}
<section class="page-hero rv">
  <div class="sec-tag" style="color:#007AFF">{title_upper}</div>
  <h1>{tagline}</h1>
  <p class="page-hero-sub">{desc}</p>
  <div class="hero-btns">
    <a href="/demo" class="btn-lg primary"><i class="fa-regular fa-calendar"></i> Schedule a Demo</a>
    <a href="https://app.imonsocial.com/auth/signup" class="btn-lg ghost">Start Free <i class="fa-solid fa-arrow-right"></i></a>
  </div>
</section>
<section class="sec alt">
  <div class="feat-grid">
    {feature_cards}
  </div>
</section>
<section class="cta-bottom">
  <h2>You just need help remembering who you know.</h2>
  <p>Be the one they never forget. Start building your reputation today.</p>
  <div class="cta-btns">
    <a href="/demo" class="btn-w"><i class="fa-regular fa-calendar"></i> Schedule a Demo</a>
    <a href="https://app.imonsocial.com/auth/signup" class="btn-gw">Start Free Trial <i class="fa-solid fa-arrow-right"></i></a>
  </div>
</section>
{footer}
<script>
const ro=new IntersectionObserver(e=>{{e.forEach(x=>{{if(x.isIntersecting)x.target.classList.add('vis')}});}},{{threshold:.08,rootMargin:'0px 0px -32px 0px'}});
document.querySelectorAll('.rv').forEach(el=>ro.observe(el));
window.addEventListener('scroll',()=>document.querySelector('nav').classList.toggle('scrolled',scrollY>40));
</script>
</body>
</html>"""

def make_feature_cards(features):
    cards = []
    for i, (icon, color, title, desc) in enumerate(features):
        delay = f" rv-{(i%3)+1}" if i < 3 else ""
        cards.append(f"""<div class="feat-card rv{delay}">
      <div class="feat-ico" style="background:{color}14"><i class="{icon}" style="color:{color}"></i></div>
      <h3>{title}</h3>
      <p>{desc}</p>
    </div>""")
    return "\n    ".join(cards)

# Generate all pages
for slug, data in PAGES.items():
    html = TEMPLATE.format(
        title=data["title"],
        title_upper=data["title"].upper(),
        tagline=data["tagline"],
        desc=data["desc"],
        css=CSS,
        nav=NAV_HTML,
        footer=FOOTER_HTML,
        feature_cards=make_feature_cards(data["features"]),
    )
    path = f"/app/marketing/build/{slug}/index.html"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(html)
    print(f"Created: {slug}")

print(f"\nDone! {len(PAGES)} pages created.")
