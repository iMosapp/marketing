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
            ("fa-solid fa-link", "#AF52DE", "All your links", "Reviews, social profiles, contact info, showcase page - all connected in one tap."),
            ("fa-solid fa-address-book", "#FF9500", "Save to contacts", "One tap and you're in their phone permanently. Not crumpled in a pocket."),
            ("fa-solid fa-palette", "#FF2D55", "Your brand, your style", "Customize colors, photo, bio, and links. Make it unmistakably you."),
            ("fa-solid fa-chart-line", "#007AFF", "Analytics built in", "See how many people you're reaching. Track shares, views, and saves over time."),
        ],
    },
    "reviews": {
        "title": "Personal Reviews",
        "tagline": "Your reputation should follow you for life.",
        "desc": "When a customer raves about you, that review belongs to you - not a company Google page. Build a personal review profile that moves with you, job to job, company to company.",
        "features": [
            ("fa-solid fa-user-shield", "#007AFF", "Reviews that are yours", "Not tied to a company. Not on a Google page you'll never own. These are YOUR reviews."),
            ("fa-solid fa-suitcase-rolling", "#34C759", "Portable reputation", "Switch jobs, switch industries - your 5-star track record comes with you."),
            ("fa-solid fa-paper-plane", "#FF9500", "Auto-request reviews", "After every sale, automatically invite customers to leave you a review."),
            ("fa-solid fa-star", "#FFD60A", "Personal rating score", "Customers see your average rating before they ever walk in the door."),
            ("fa-solid fa-id-card", "#AF52DE", "Connected to your card", "Your reviews show on your digital card automatically. Social proof built in."),
            ("fa-solid fa-chart-simple", "#FF2D55", "Track your growth", "Watch your review count and rating climb over time. Proof you're the real deal."),
        ],
    },
    "showcase": {
        "title": "Link Pages & Showcase",
        "tagline": "One link for everything you do.",
        "desc": "Your Instagram, TikTok, Google reviews, YouTube, digital card, and more - all in one beautiful, shareable link page. Like a Linktree built specifically for sales professionals.",
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
        "desc": "Every time you close a deal, a branded congrats card gets sent to your customer. It links to your review page, social profiles, and digital card - turning every sale into a referral machine.",
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
            ("fa-solid fa-cake-candles", "#FF2D55", "Birthday messages", "Never miss a birthday again. Automatic, personal, and on time - every single year."),
            ("fa-solid fa-calendar-check", "#007AFF", "Anniversary follow-ups", "One year since the sale? Two years? Reach out automatically at every milestone."),
            ("fa-solid fa-snowflake", "#34C759", "Holiday greetings", "Thanksgiving, Christmas, New Year's - stay top of mind during every holiday."),
            ("fa-solid fa-sliders", "#FF9500", "Per-contact control", "Pause or customize automations for any contact with one tap."),
            ("fa-solid fa-comment-dots", "#AF52DE", "SMS & email", "Send via text message, email, or both. Your choice per campaign."),
            ("fa-solid fa-bolt", "#FFD60A", "Set it and forget it", "Turn it on once. It works for you 24/7, 365 days a year."),
        ],
    },
    "inbox": {
        "title": "Inbox & Messaging",
        "tagline": "Every conversation. One place.",
        "desc": "SMS, email, automated messages - all in one unified thread per contact. Track opens, clicks, and replies. Know exactly when to follow up and what to say.",
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
            ("fa-solid fa-lightbulb", "#FFD60A", "Actionable suggestions", "Not just answers - Jessi tells you exactly what to do next and why."),
            ("fa-solid fa-clock-rotate-left", "#34C759", "Conversation memory", "Jessi remembers what you've asked before. Your AI assistant gets smarter over time."),
            ("fa-solid fa-shield-halved", "#FF9500", "Private & secure", "Your data stays yours. Jessi only sees what you share with her."),
            ("fa-solid fa-rocket", "#FF2D55", "Always improving", "New capabilities added regularly. Jessi keeps getting better at helping you win."),
        ],
    },
    "leaderboard": {
        "title": "Leaderboards",
        "tagline": "See who's actually building relationships.",
        "desc": "Cards shared, reviews collected, engagement driven - all tracked. Store-level, org-level, and individual rankings that reward the salespeople who do the work.",
        "features": [
            ("fa-solid fa-trophy", "#FFD60A", "Performance rankings", "See who's on top. Cards shared, reviews earned, messages sent - all ranked."),
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
        "desc": "Manage your entire organization - stores, managers, and salespeople - all under one roof. Consistent branding, centralized analytics, and full control over who does what.",
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
        "desc": "You don't need a company behind you. I'm On Social gives every individual salesperson the same tools the big teams use - digital cards, personal reviews, automated outreach, and analytics.",
        "features": [
            ("fa-solid fa-user", "#007AFF", "Your own profile", "Digital card, review page, and link page - all yours, all free to start."),
            ("fa-solid fa-star", "#FFD60A", "Build your reputation", "Collect reviews that follow you. Build credibility that outlasts any employer."),
            ("fa-solid fa-bolt", "#34C759", "Automate your follow-up", "Birthday messages, anniversaries, congrats cards - all on autopilot."),
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
        "desc": "We'll walk you through the platform, show you how it fits your workflow, and answer every question. No pressure, no commitment - just a conversation about how to build your brand.",
        "features": [
            ("fa-solid fa-clock", "#007AFF", "15 minutes", "Quick, focused, and respectful of your time. We get right to what matters to you."),
            ("fa-solid fa-user-check", "#34C759", "Personalized walkthrough", "We show you the features that matter most for YOUR role and industry."),
            ("fa-solid fa-question", "#FF9500", "Ask anything", "Pricing, setup, integrations, team rollout - nothing is off limits."),
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
        "desc": "Guides, FAQs, and direct support for everything you need. If you can't find it here, just ask - we're real people and we respond fast.",
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
        "desc": "Whether you run a 5-person office or a 500-person sales floor, I'm On Social scales with you. Give every salesperson the tools to build relationships - and give managers the visibility to track it.",
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
        "desc": "Sell a car. Send a congrats card. Earn a review. Get a referral. Repeat. I'm On Social turns every sale into a long-term relationship that brings customers back - and brings their friends.",
        "features": [
            ("fa-solid fa-car", "#007AFF", "Built for auto sales", "Designed around the way dealerships actually work. Not a generic tool."),
            ("fa-solid fa-image", "#FF2D55", "Congrats on every sale", "Branded congrats card sent to every buyer. They share it. You get the referral."),
            ("fa-solid fa-star", "#FFD60A", "Portable reviews", "Switch dealerships and keep every review. Your reputation follows YOU."),
            ("fa-solid fa-cake-candles", "#34C759", "Automated follow-ups", "Birthday texts, service reminders, anniversary messages - all automatic."),
            ("fa-solid fa-trophy", "#AF52DE", "Dealership leaderboards", "See who's building the most relationships. Motivate the whole floor."),
            ("fa-solid fa-id-card", "#FF9500", "Digital cards for every rep", "No more paper cards in cup holders. Shareable, trackable, and always up to date."),
        ],
    },
    "presentation": {
        "title": "Sales Deck",
        "tagline": "See what we can do for you.",
        "desc": "A quick overview of everything I'm On Social offers - from digital cards to automated outreach to AI-powered insights. Share it with your team or your boss.",
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
            ("fa-solid fa-bolt", "#34C759", "Automated Campaigns", "Birthdays, anniversaries, follow-ups - all on autopilot."),
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
    <a href="/" class="logo"><img src="/logo.png" alt="I'm On Social"/></a>
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
      <a href="#" class="btn-demo" onclick="openDemoModal(event,'nav')">Book a Demo</a>
    </div>
    <button class="hamburger" onclick="document.getElementById('mob').classList.toggle('open')" aria-label="Menu"><i class="fa-solid fa-bars"></i></button>
  </div>
  <div class="mob-menu" id="mob">
    <a href="/digital-card">Digital Cards</a><a href="/reviews">Reviews</a><a href="/inbox">Inbox</a><a href="/organizations">Organizations</a><a href="/pricing">Pricing</a><a href="https://app.imonsocial.com">Sign In</a><a href="/demo" class="mob-cta">Get a Demo</a>
  </div>
</nav>"""


CONTACT_MODAL_HTML = """
<div class="demo-overlay" id="contactModal">
  <div class="demo-modal">
    <button class="demo-close" onclick="closeContactModal()">&times;</button>
    <div id="contactFormWrap">
      <div style="margin-bottom:20px;">
        <p style="font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:1.5px;color:#007AFF;margin-bottom:6px;">Get in Touch</p>
        <h2 style="font-size:24px;font-weight:900;color:#1C1C1E;margin-bottom:6px;">Contact Us</h2>
        <p style="font-size:14px;color:#8E8E93;">We'd love to hear from you. Send us a message and we'll get back to you within 1 business day.</p>
      </div>
      <form onsubmit="submitContactForm(event)">
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px;">
          <div class="dm-field"><label>First Name *</label><input type="text" id="ct-first" placeholder="John" required/></div>
          <div class="dm-field"><label>Last Name</label><input type="text" id="ct-last" placeholder="Smith"/></div>
        </div>
        <div class="dm-field"><label>Email *</label><input type="email" id="ct-email" placeholder="john@company.com" required/></div>
        <div class="dm-field"><label>Phone</label><input type="tel" id="ct-phone" placeholder="(555) 123-4567"/></div>
        <div class="dm-field">
          <label>How can we help you? *</label>
          <textarea id="ct-message" placeholder="Tell us what's on your mind..." required style="width:100%;padding:12px 14px;background:#FAFAFA;border:1px solid #E5E5EA;border-radius:10px;color:#1C1C1E;font-size:15px;font-family:'Inter',sans-serif;outline:none;resize:vertical;min-height:120px;box-sizing:border-box;transition:border-color .2s;"></textarea>
        </div>
        <button type="submit" class="dm-submit" id="ctSubmitBtn" style="background:#1C1C1E;">Send Message</button>
        <p style="font-size:11px;color:#8E8E93;text-align:center;margin-top:10px;line-height:1.5;">By submitting you agree to our <a href="/terms" style="color:#007AFF;">Terms</a> &amp; <a href="/privacy" style="color:#007AFF;">Privacy Policy</a>. Operated by VI Ventures Group LLC.</p>
      </form>
    </div>
    <div id="contactSuccessWrap" style="display:none;text-align:center;padding:40px 20px">
      <div style="font-size:52px;color:#34C759;margin-bottom:14px">&#10003;</div>
      <h3 style="font-size:20px;font-weight:800;color:#1C1C1E;margin-bottom:8px;">Message Sent!</h3>
      <p style="font-size:14px;color:#8E8E93;line-height:1.6;">Thanks for reaching out. We'll get back to you within 1 business day at the email you provided.</p>
    </div>
  </div>
</div>
<script>
function openContactModal(e){if(e)e.preventDefault();document.getElementById('contactModal').classList.add('active');document.body.style.overflow='hidden';}
function closeContactModal(){document.getElementById('contactModal').classList.remove('active');document.body.style.overflow='';}
document.getElementById('contactModal').addEventListener('click',function(e){if(e.target===this)closeContactModal();});
async function submitContactForm(e){
  e.preventDefault();
  var btn=document.getElementById('ctSubmitBtn');btn.disabled=true;btn.textContent='Sending...';
  try{
    var r=await fetch('https://app.imonsocial.com/api/demo-requests',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({name:(document.getElementById('ct-first').value+' '+document.getElementById('ct-last').value).trim(),email:document.getElementById('ct-email').value,phone:document.getElementById('ct-phone').value,message:document.getElementById('ct-message').value,source:'contact_footer',lead_source:'contact_us'})
    });
    if(r.ok){document.getElementById('contactFormWrap').style.display='none';document.getElementById('contactSuccessWrap').style.display='block';}
    else throw new Error();
  }catch(ex){btn.disabled=false;btn.textContent='Send Message';alert("We couldn't reach our server just now. Please try again in a moment, or email sales@imonsocial.com and we'll get you set up.");}
}
</script>"""



DEMO_MODAL_HTML = """
<style>
  .demo-overlay{position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:9999;display:flex;align-items:center;justify-content:center;opacity:0;pointer-events:none;transition:opacity .25s}
  .demo-overlay.active{opacity:1;pointer-events:all}
  .demo-modal{background:#fff;border-radius:20px;padding:32px 28px;width:90%;max-width:480px;max-height:90vh;overflow-y:auto;position:relative;transform:translateY(20px);transition:transform .25s}
  .demo-overlay.active .demo-modal{transform:translateY(0)}
  .demo-close{position:absolute;top:14px;right:16px;background:none;border:none;font-size:22px;cursor:pointer;color:#8E8E93;line-height:1}
  .dm-field{margin-bottom:14px}
  .dm-field label{display:block;font-size:12px;font-weight:600;color:#8E8E93;margin-bottom:4px;text-transform:uppercase;letter-spacing:1px}
  .dm-field input,.dm-field select{width:100%;padding:12px 14px;background:#FAFAFA;border:1px solid #E5E5EA;border-radius:10px;color:#1C1C1E;font-size:15px;font-family:'Inter',sans-serif;outline:none;transition:border-color .2s;box-sizing:border-box}
  .dm-field input:focus,.dm-field select:focus{border-color:#007AFF;background:#fff}
  .dm-submit{width:100%;padding:14px;background:#007AFF;color:#FFF;font-size:16px;font-weight:800;border:none;border-radius:980px;cursor:pointer;margin-top:4px;transition:all .25s;font-family:'Inter',sans-serif}
  .dm-submit:hover{background:#0062CC}
  .dm-submit:disabled{opacity:.5;cursor:not-allowed}
</style>
<div class="demo-overlay" id="demoModal">
  <div class="demo-modal">
    <button class="demo-close" onclick="closeDemoModal()">&times;</button>
    <div id="demoFormWrap">
      <h2 style="font-size:24px;font-weight:900;margin-bottom:4px">Book a Demo</h2>
      <p style="font-size:14px;color:#8E8E93;margin-bottom:20px">See how I'm On Social can transform your business.</p>
      <form onsubmit="submitDemoForm(event)">
        <div class="dm-field"><label>Full Name *</label><input type="text" id="dm-name" placeholder="John Smith" required/></div>
        <div class="dm-field"><label>Email *</label><input type="email" id="dm-email" placeholder="john@company.com" required/></div>
        <div class="dm-field"><label>Phone *</label><input type="tel" id="dm-phone" placeholder="(555) 123-4567" required/></div>
        <div class="dm-field"><label>Business Type</label><select id="dm-type"><option value="">Select your industry...</option><option value="car_dealer">Car Dealership</option><option value="real_estate">Real Estate</option><option value="small_business">Small Business / Retail</option><option value="hospitality">Hospitality / Food &amp; Beverage</option><option value="sales_team">Sales Team</option><option value="other">Other</option></select></div>
        <div class="dm-field"><label>Company</label><input type="text" id="dm-company" placeholder="Your business name"/></div>
        <div style="background:#F2F9FF;border:1px solid rgba(0,122,255,.2);border-radius:10px;padding:12px 14px;margin-bottom:14px;">
          <label style="display:flex;align-items:flex-start;gap:10px;cursor:pointer;text-transform:none;letter-spacing:0;font-size:13px;color:#3C3C43;font-weight:400;">
            <input type="checkbox" id="dm-sms-opt-in" style="width:16px;height:16px;margin-top:2px;flex-shrink:0;accent-color:#007AFF;cursor:pointer;"/>
            <span>I agree to receive SMS messages from I'm On Social about my demo request and follow-up. Msg &amp; data rates may apply. Reply STOP to opt out. <a href="/sms-terms" style="color:#007AFF;">SMS Policy</a>.</span>
          </label>
        </div>
        <button type="submit" class="dm-submit" id="dmSubmitBtn">Book My Demo</button>
        <p style="font-size:11px;color:#8E8E93;text-align:center;margin-top:10px;line-height:1.5;">By submitting you agree to our <a href="/terms" style="color:#007AFF;">Terms</a> &amp; <a href="/privacy" style="color:#007AFF;">Privacy Policy</a>. Operated by VI Ventures Group LLC.</p>
      </form>
    </div>
    <div id="demoSuccessWrap" style="display:none;text-align:center;padding:32px 0">
      <div style="font-size:48px;color:#34C759;margin-bottom:12px">&#10003;</div>
      <h3 style="font-size:20px;font-weight:700;margin-bottom:8px">You're In!</h3>
      <p style="font-size:14px;color:#8E8E93">We'll reach out within 24 hours to schedule your personalized demo.</p>
    </div>
  </div>
</div>
<script>
var _demoSource='';
function openDemoModal(e,src){if(e)e.preventDefault();_demoSource=src||'';document.getElementById('demoModal').classList.add('active');document.body.style.overflow='hidden';}
function closeDemoModal(){document.getElementById('demoModal').classList.remove('active');document.body.style.overflow='';}
document.getElementById('demoModal').addEventListener('click',function(e){if(e.target===this)closeDemoModal();});
async function submitDemoForm(e){
  e.preventDefault();
  var btn=document.getElementById('dmSubmitBtn');btn.disabled=true;btn.textContent='Submitting...';
  try{
    var r=await fetch('https://app.imonsocial.com/api/demo-requests',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({name:document.getElementById('dm-name').value,email:document.getElementById('dm-email').value,phone:document.getElementById('dm-phone').value,business_type:document.getElementById('dm-type').value,company:document.getElementById('dm-company').value,sms_opt_in:document.getElementById('dm-sms-opt-in')&&document.getElementById('dm-sms-opt-in').checked,lead_source:_demoSource||'subpage'})
    });
    if(r.ok){document.getElementById('demoFormWrap').style.display='none';document.getElementById('demoSuccessWrap').style.display='block';}
    else throw new Error();
  }catch(ex){btn.disabled=false;btn.textContent='Book My Demo';alert("We couldn't reach our server just now. Please try again in a moment, or email sales@imonsocial.com and we'll get you set up.");}
}
</script>"""


FOOTER_HTML = """<footer>
  <div class="ft-inner">
    <div class="ft-brand"><div class="ft-logo"><img src="/logo.png" alt="I'm On Social"/></div><p class="ft-tag">The relationship engine for sales professionals.</p>
      <div class="ft-social"><a href="https://instagram.com/imonsocialapp" target="_blank" rel="noopener"><i class="fa-brands fa-instagram"></i></a><a href="https://tiktok.com/@imonsocialapp" target="_blank" rel="noopener"><i class="fa-brands fa-tiktok"></i></a><a href="https://youtube.com/@imonsocial" target="_blank" rel="noopener"><i class="fa-brands fa-youtube"></i></a></div>
    </div>
    <div class="ft-col"><div class="ft-col-t">Product</div><a href="/digital-card">Digital Cards</a><a href="/reviews">Personal Reviews</a><a href="/inbox">Inbox</a><a href="/date-triggers">Automations</a><a href="/leaderboard">Leaderboards</a><a href="/jessi">Jessi AI</a></div>
    <div class="ft-col"><div class="ft-col-t">Company</div><a href="/organizations">For Teams</a><a href="/pricing">Pricing</a><a href="/privacy">Privacy Policy</a><a href="/terms">Terms of Service</a><a href="/sms-terms">SMS Policy</a><a href="#" onclick="openContactModal(event)">Contact Us</a></div>
    <div class="ft-col"><div class="ft-col-t">Get Started</div><a href="#" onclick="openDemoModal(event,'footer')">Schedule a Demo</a><a href="https://app.imonsocial.com/auth/signup">Start Free Trial</a><a href="https://app.imonsocial.com">Sign In</a><a href="/training">Training</a><a href="/help">Help Center</a></div>
  </div>
  <div class="ft-bottom"><span class="ft-copy">&copy; 2026 I'm On Social. Powered by VI Ventures Group LLC.</span><span class="ft-copy" style="margin-top:4px"><a href="/sms-terms" style="color:#007AFF">SMS Messaging Policy</a></span></div>
</footer>"""

CSS = open("/app/marketing/build/shared.css").read()

TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1.0"/>
  <title>{title} - I'm On Social</title>
  <meta name="description" content="{desc}"/>
  <link rel="icon" href="/favicon.png"/>
  <link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
  <style>{css}</style>
<script src="/lead-retry.js"></script>
</head>
<body>
{nav}
<section class="page-hero rv">
  <div class="sec-tag" style="color:#007AFF">{title_upper}</div>
  <h1>{tagline}</h1>
  <p class="page-hero-sub">{desc}</p>
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
    <a href="#" onclick="openDemoModal(event,'cta_bottom')" class="btn-w"><i class="fa-regular fa-calendar"></i> Schedule a Demo</a>
    <a href="https://app.imonsocial.com/auth/signup" class="btn-gw">Start Free Trial <i class="fa-solid fa-arrow-right"></i></a>
  </div>
</section>
{{footer}}
{modal}
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



# ── Demo page ─────────────────────────────────────────────────────────────────

DEMO_PAGE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1.0"/>
  <title>Schedule a Demo - I'm On Social</title>
  <meta name="description" content="See how I'm On Social transforms your sales process. Schedule a personalized demo with our team."/>
  <link rel="icon" href="/favicon.png"/>
  <link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
  <style>{css}
  .demo-wrap{{max-width:680px;margin:0 auto;padding:60px 24px 80px;}}
  .demo-eyebrow{{font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:1.5px;color:#007AFF;margin-bottom:12px;}}
  .demo-title{{font-size:clamp(28px,5vw,44px);font-weight:800;color:#1C1C1E;line-height:1.15;margin-bottom:10px;}}
  .demo-sub{{font-size:17px;color:#636366;line-height:1.6;margin-bottom:36px;}}
  .demo-card{{background:#fff;border:1px solid #E5E5EA;border-radius:20px;padding:36px;box-shadow:0 4px 24px rgba(0,0,0,.06);}}
  .d-form-row{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px;}}
  @media(max-width:560px){{.d-form-row{{grid-template-columns:1fr;}}}}
  .d-form-group{{display:flex;flex-direction:column;gap:6px;margin-bottom:16px;}}
  .d-form-group label{{font-size:14px;font-weight:600;color:#1C1C1E;}}
  .d-form-group input,.d-form-group textarea{{padding:12px 14px;border:1.5px solid #E5E5EA;border-radius:10px;font-size:15px;font-family:Inter,sans-serif;color:#1C1C1E;outline:none;transition:border-color .15s;background:#FAFAFA;width:100%;box-sizing:border-box;}}
  .d-form-group input:focus,.d-form-group textarea:focus{{border-color:#007AFF;background:#fff;}}
  .d-form-group textarea{{resize:vertical;min-height:100px;}}
  .opt-in-wrap{{background:#F2F9FF;border:1px solid #007AFF30;border-radius:12px;padding:14px 16px;margin-bottom:20px;}}
  .opt-in-row{{display:flex;align-items:flex-start;gap:10px;}}
  .opt-in-row input[type=checkbox]{{width:17px;height:17px;margin-top:2px;flex-shrink:0;accent-color:#007AFF;cursor:pointer;}}
  .opt-in-row label{{font-size:13px;color:#3C3C43;line-height:1.55;cursor:pointer;}}
  .opt-in-row a{{color:#007AFF;}}
  .btn-demo-submit{{width:100%;padding:16px;background:#007AFF;color:#fff;border:none;border-radius:12px;font-size:17px;font-weight:700;cursor:pointer;transition:background .15s;font-family:Inter,sans-serif;}}
  .btn-demo-submit:hover{{background:#0062CC;}}
  .btn-demo-submit:disabled{{background:#8E8E93;cursor:not-allowed;}}
  .form-legal-note{{font-size:12px;color:#8E8E93;text-align:center;margin-top:12px;line-height:1.5;}}
  .form-legal-note a{{color:#007AFF;}}
  .demo-success{{text-align:center;padding:40px 20px;}}
  .demo-success .si{{font-size:52px;color:#34C759;margin-bottom:16px;}}
  .demo-success h3{{font-size:24px;font-weight:800;color:#1C1C1E;margin-bottom:8px;}}
  .demo-success p{{font-size:16px;color:#636366;}}
  .benefits{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-bottom:36px;}}
  @media(max-width:560px){{.benefits{{grid-template-columns:1fr;}}}}
  .benefit{{text-align:center;padding:20px;background:#FAFAFA;border-radius:14px;}}
  .benefit i{{font-size:22px;margin-bottom:8px;display:block;}}
  .benefit h4{{font-size:15px;font-weight:700;color:#1C1C1E;margin-bottom:3px;}}
  .benefit p{{font-size:13px;color:#636366;margin:0;}}
  </style>
<script src="/lead-retry.js"></script>
</head>
<body>
{nav}
<div class="demo-wrap">
  <div class="demo-eyebrow">Schedule a Demo</div>
  <h1 class="demo-title">See I'm On Social in action</h1>
  <p class="demo-sub">Get a personalized walkthrough with our team. We'll show you exactly how it works for your business.</p>

  <div class="benefits">
    <div class="benefit"><i class="fa-solid fa-clock" style="color:#007AFF"></i><h4>30 minutes</h4><p>Quick, focused, no fluff</p></div>
    <div class="benefit"><i class="fa-solid fa-user-tie" style="color:#34C759"></i><h4>Personalized</h4><p>Built around your use case</p></div>
    <div class="benefit"><i class="fa-solid fa-circle-check" style="color:#FF9500"></i><h4>No pressure</h4><p>See if it's the right fit</p></div>
  </div>

  <div class="demo-card">
    <div id="form-area">
      <div class="d-form-row">
        <div class="d-form-group"><label for="d-name">Full Name *</label><input type="text" id="d-name" placeholder="Forest Ward" required /></div>
        <div class="d-form-group"><label for="d-email">Email *</label><input type="email" id="d-email" placeholder="forest@company.com" required /></div>
      </div>
      <div class="d-form-row">
        <div class="d-form-group"><label for="d-phone">Phone Number *</label><input type="tel" id="d-phone" placeholder="(801) 555-1234" required /></div>
        <div class="d-form-group"><label for="d-company">Company</label><input type="text" id="d-company" placeholder="Your Company" /></div>
      </div>
      <div class="d-form-group"><label for="d-msg">What are you looking for? (Optional)</label><textarea id="d-msg" placeholder="Tell us about your team, industry, or what problem you're trying to solve..."></textarea></div>

      <div class="opt-in-wrap">
        <div class="opt-in-row">
          <input type="checkbox" id="sms-opt-in" />
          <label for="sms-opt-in">I agree to receive SMS messages from I'm On Social about my demo request and follow-up communications. Msg &amp; data rates may apply. Reply STOP to opt out at any time. See our <a href="/sms-terms" target="_blank">SMS Messaging Policy</a>.</label>
        </div>
      </div>

      <button class="btn-demo-submit" id="submit-btn" onclick="submitDemo()">Request My Demo <i class="fa-solid fa-arrow-right"></i></button>
      <p class="form-legal-note">By submitting, you agree to our <a href="/terms">Terms of Service</a> and <a href="/privacy">Privacy Policy</a>.<br>I'm On Social is operated by VI Ventures Group LLC.</p>
    </div>

    <div id="success-area" class="demo-success" style="display:none">
      <div class="si"><i class="fa-solid fa-circle-check"></i></div>
      <h3>You're on the list!</h3>
      <p>We'll reach out within 1 business day to schedule your demo.<br>Check your inbox - and spam just in case.</p>
    </div>
  </div>
</div>
{footer}
<script>
window.addEventListener('scroll',()=>document.querySelector('nav').classList.toggle('scrolled',scrollY>40));
async function submitDemo() {{
  const name=document.getElementById('d-name').value.trim();
  const email=document.getElementById('d-email').value.trim();
  const phone=document.getElementById('d-phone').value.trim();
  const company=document.getElementById('d-company').value.trim();
  const msg=document.getElementById('d-msg').value.trim();
  const smsOptIn=document.getElementById('sms-opt-in').checked;
  if(!name||!email||!phone){{alert('Please fill in your name, email, and phone number.');return;}}
  const btn=document.getElementById('submit-btn');
  btn.disabled=true;btn.innerHTML='Submitting...';
  try{{
    const r=await fetch('https://app.imonsocial.com/api/demo-requests',{{
      method:'POST',headers:{{'Content-Type':'application/json'}},
      body:JSON.stringify({{name,email,phone,company,message:msg,sms_opt_in:smsOptIn,source:'website_demo_page'}})
    }});
    if(r.ok){{
      document.getElementById('form-area').style.display='none';
      document.getElementById('success-area').style.display='block';
    }}else{{btn.disabled=false;btn.innerHTML='Request My Demo <i class="fa-solid fa-arrow-right"></i>';alert("We couldn't reach our server just now. Please try again in a moment, or email sales@imonsocial.com and we'll get you set up.");}}
  }}catch(e){{btn.disabled=false;btn.innerHTML='Request My Demo <i class="fa-solid fa-arrow-right"></i>';alert("We couldn't reach our server just now. Please try again in a moment, or email sales@imonsocial.com and we'll get you set up.");}}
}}
</script>
</body>
</html>"""



# ── Legal pages ───────────────────────────────────────────────────────────────

LEGAL_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1.0"/>
  <title>{title} - I'm On Social</title>
  <meta name="description" content="{desc}"/>
  <link rel="icon" href="/favicon.png"/>
  <link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
  <style>{css}
  .legal-wrap{{max-width:780px;margin:0 auto;padding:60px 24px 80px;}}
  .legal-eyebrow{{font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:1.5px;color:#007AFF;margin-bottom:12px;}}
  .legal-title{{font-size:clamp(28px,5vw,44px);font-weight:800;color:#1C1C1E;line-height:1.15;margin-bottom:10px;}}
  .legal-meta{{font-size:14px;color:#8E8E93;margin-bottom:36px;border-bottom:1px solid #F2F2F7;padding-bottom:20px;}}
  .legal-stop{{background:#f0fff4;border:1px solid #34C75940;border-radius:12px;padding:16px 20px;margin-bottom:36px;}}
  .legal-stop strong{{color:#1a7a37;display:block;font-size:16px;margin-bottom:4px;}}
  .legal-stop span{{color:#1a7a37;font-size:14px;}}
  .legal-section{{margin-bottom:32px;}}
  .legal-section h2{{font-size:18px;font-weight:700;color:#1C1C1E;margin-bottom:10px;}}
  .legal-section p{{font-size:15px;color:#3C3C43;line-height:1.7;white-space:pre-line;}}
  .legal-related{{margin-top:40px;padding-top:28px;border-top:1px solid #F2F2F7;}}
  .legal-related h3{{font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;color:#8E8E93;margin-bottom:12px;}}
  .legal-related a{{display:inline-block;font-size:15px;font-weight:600;color:#007AFF;margin-right:20px;text-decoration:none;}}
  .legal-related a:hover{{text-decoration:underline;}}
  </style>
<script src="/lead-retry.js"></script>
</head>
<body>
{nav}
<div class="legal-wrap">
  <div class="legal-eyebrow">{eyebrow}</div>
  <h1 class="legal-title">{title}</h1>
  <p class="legal-meta">{meta}</p>
  {stop_box}
  {sections}
  {related}
</div>
{footer}
<script>
window.addEventListener('scroll',()=>document.querySelector('nav').classList.toggle('scrolled',scrollY>40));
</script>
</body>
</html>"""


def make_legal_sections(sections):
    html = []
    for title, content in sections:
        html.append(f'<div class="legal-section"><h2>{title}</h2><p>{content}</p></div>')
    return "\n".join(html)


LEGAL_PAGES = {
    "privacy": {
        "title": "Privacy Policy",
        "eyebrow": "Legal",
        "desc": "How I'm On Social collects, uses, and protects your personal information.",
        "meta": "Effective Date: January 1, 2026 &nbsp;·&nbsp; I'm On Social is operated by VI Ventures Group LLC.",
        "stop_box": "",
        "related": '<div class="legal-related"><h3>Related Policies</h3><a href="/terms">Terms of Service &rarr;</a><a href="/sms-terms">SMS Messaging Policy &rarr;</a></div>',
        "sections": [
            ("1. Information We Collect", "We collect information you provide directly (name, email, phone, profile photo, bio, job title), information generated through your use of the platform (contacts, messages, campaign activity, event logs), and technical data (device type, browser, IP address, usage patterns).\n\nWe do not sell your personal information to third parties."),
            ("2. How We Use Your Information", "We use your information to:\n\n- Provide and maintain I'm On Social services, including digital business cards, messaging, campaigns, and AI features\n- Process and deliver communications you initiate through our platform\n- Generate analytics and activity reports for you and your organization\n- Improve our AI assistant and recommendation algorithms\n- Send service-related notices, updates, and security alerts\n- Provide customer support"),
            ("3. Contact & CRM Data", "When you use I'm On Social's relationship management features, you may store customer and prospect contact information. You represent and warrant that you have obtained all necessary consents from individuals whose data you store. You are responsible for complying with applicable data protection laws (TCPA, CAN-SPAM, CCPA, GDPR) when collecting, storing, and using contact data."),
            ("4. Data Sharing", "We do not sell your data. We share information only with:\n\n- Service providers who help us operate the platform (cloud hosting, email delivery, SMS delivery)\n- Your organization's administrators within your account hierarchy\n- Law enforcement when required by law\n\nAll third-party providers are bound by confidentiality agreements."),
            ("5. Data Security", "We use industry-standard encryption in transit (TLS) and at rest. Access to personal data is restricted to authorized personnel only. We maintain security practices consistent with applicable industry standards."),
            ("6. Data Retention", "We retain your data for as long as your account is active. Upon account termination, data is retained for 90 days to allow export, then permanently deleted. You may request data export or deletion at any time by contacting support@imonsocial.com."),
            ("7. Your Rights", "You have the right to:\n\n- Access the personal information we hold about you\n- Correct inaccurate information\n- Request deletion of your account and associated data\n- Export your contacts and content\n- Opt out of marketing communications\n\nTo exercise these rights, contact support@imonsocial.com."),
            ("8. Cookies", "We use cookies and similar technologies to maintain your session, remember preferences, and analyze platform usage. You can control cookie behavior through your browser settings."),
            ("9. Children's Privacy", "I'm On Social is not directed to children under 13. We do not knowingly collect personal information from children under 13. If you believe a child has provided us with personal information, contact us immediately."),
            ("10. Changes to This Policy", "We may update this Privacy Policy periodically. Material changes will be communicated via email or in-app notification at least 30 days before taking effect."),
            ("11. Contact", "I'm On Social is operated by VI Ventures Group LLC.\nEmail: support@imonsocial.com\nWebsite: https://imonsocial.com"),
        ],
    },
    "terms": {
        "title": "Terms of Service",
        "eyebrow": "Legal",
        "desc": "The terms and conditions for using the I'm On Social platform.",
        "meta": "Effective Date: January 1, 2026 &nbsp;·&nbsp; I'm On Social is operated by VI Ventures Group LLC.",
        "stop_box": "",
        "related": '<div class="legal-related"><h3>Related Policies</h3><a href="/privacy">Privacy Policy &rarr;</a><a href="/sms-terms">SMS Messaging Policy &rarr;</a></div>',
        "sections": [
            ("1. Acceptance of Terms", "By accessing or using I'm On Social (\"the Service\"), you agree to be bound by these Terms of Service. If you do not agree to these terms, do not use the Service. These terms apply to all users, including individual users, team members, store managers, and organization administrators."),
            ("2. Description of Service", "I'm On Social provides a Relationship Management System (RMS) platform that includes digital business cards, contact management, messaging (SMS, email, and personal SMS), automated campaigns, AI-powered communication tools, analytics, and related services. The Service is available through web and mobile applications."),
            ("3. Account Registration & Security", "You must provide accurate and complete information when creating an account. You are responsible for maintaining the confidentiality of your account credentials and for all activities that occur under your account. You must notify us immediately of any unauthorized use.\n\nOrganization administrators are responsible for managing user access within their organization, including adding, deactivating, and removing team members."),
            ("4. Acceptable Use", "You agree not to:\n\n- Use the Service to send unsolicited commercial messages (spam)\n- Violate any applicable laws, including CAN-SPAM, TCPA, and GDPR\n- Upload or transmit malicious code or content\n- Attempt to gain unauthorized access to the Service or other users' accounts\n- Use the Service to harass, defame, or threaten any person\n- Resell or redistribute the Service without written permission\n- Use the AI features to generate harmful, misleading, or illegal content"),
            ("5. Subscription & Billing", "Paid plans are billed on a monthly or annual basis as selected at the time of purchase. Prices are subject to change with 30 days' notice. All fees are non-refundable except as required by applicable law.\n\nFree trials, if offered, automatically convert to paid subscriptions at the end of the trial period unless cancelled. You may cancel your subscription at any time."),
            ("6. SMS, Email & Communication Terms", "You agree to use the messaging features of I'm On Social in compliance with all applicable laws, including the Telephone Consumer Protection Act (TCPA), CAN-SPAM Act, and any state-level regulations.\n\nYou must obtain proper consent before sending automated messages to contacts. The platform provides tools for managing opt-outs, and you are required to honor all unsubscribe and opt-out requests promptly."),
            ("7. Contact Data & CRM Information", "You represent and warrant that you have obtained all necessary consents from individuals whose data you store in the platform. You are responsible for complying with all applicable data protection laws (including TCPA, CAN-SPAM, CCPA, and GDPR where applicable) when collecting, storing, and using contact data through the Service."),
            ("8. Intellectual Property", "The Service, including all software, design, text, graphics, and other content, is owned by I'm On Social and protected by intellectual property laws. You retain ownership of content you create or upload through the Service."),
            ("9. Limitation of Liability", "The Service is provided \"as is\" without warranties of any kind. I'm On Social shall not be liable for any indirect, incidental, special, consequential, or punitive damages. Our total liability for any claim shall not exceed the amount you paid us in the 12 months preceding the claim."),
            ("10. Termination", "We may suspend or terminate your access to the Service at any time for violation of these terms with reasonable notice. You may terminate your account at any time. Upon termination, your right to use the Service ceases immediately."),
            ("11. Modifications to Terms", "We reserve the right to modify these Terms at any time. Material changes will be communicated via email or in-app notification at least 30 days before they take effect."),
            ("12. Governing Law", "These Terms shall be governed by and construed in accordance with the laws of the State of Wyoming, United States. Any disputes arising from these Terms shall be resolved in the courts of Wyoming."),
            ("13. Contact", "I'm On Social is operated by VI Ventures Group LLC.\nEmail: support@imonsocial.com\nWebsite: https://imonsocial.com"),
        ],
    },
    "sms-terms": {
        "title": "SMS Messaging Policy",
        "eyebrow": "Legal",
        "desc": "How I'm On Social handles SMS messaging, opt-in, opt-out, and carrier compliance.",
        "meta": "Effective Date: January 1, 2026 &nbsp;·&nbsp; I'm On Social is operated by VI Ventures Group LLC.",
        "stop_box": '<div class="legal-stop"><strong>To stop receiving messages: Reply STOP</strong><span>For help: Reply HELP or email support@imonsocial.com</span></div>',
        "related": '<div class="legal-related"><h3>Related Policies</h3><a href="/privacy">Privacy Policy &rarr;</a><a href="/terms">Terms of Service &rarr;</a></div>',
        "sections": [
            ("1. Overview", "I'm On Social, operated by VI Ventures Group LLC, provides SMS messaging as a feature of its Relationship Management System (RMS) platform. This policy explains how SMS messaging works within our platform, how to opt in and out, and what types of messages you may receive."),
            ("2. Who Sends Messages", "SMS messages sent through I'm On Social are sent by individual sales professionals, service advisors, and business users who have active accounts on the platform. These users send messages to their own customers and contacts who have provided consent to receive communications.\n\nI'm On Social (VI Ventures Group LLC) provides the technology platform. Message content is created and sent by individual platform users, not by VI Ventures Group LLC directly."),
            ("3. Types of Messages", "Platform users may send the following types of messages:\n\n- Relationship follow-up messages and check-ins\n- Appointment reminders and confirmations\n- Review and feedback requests\n- Digital business card and contact information sharing\n- Congratulations and milestone messages (birthdays, anniversaries, purchases)\n- Campaign-based automated follow-up sequences\n- Account notifications and updates\n- Responses to inbound customer inquiries"),
            ("4. Message Frequency", "Message frequency varies based on the individual platform user's settings and the contact's relationship with that user. You will not receive unsolicited marketing messages. All automated messages are sent by users to their own opted-in customer contacts."),
            ("5. How to Opt In", "You may receive SMS messages from an I'm On Social user if:\n\n- You have provided your phone number to a business or sales professional who uses I'm On Social\n- You have verbally or in writing agreed to receive communications from that individual\n- You have submitted a contact form or lead form that includes consent language\n- You have scanned or tapped a digital business card and provided your contact information"),
            ("6. How to Opt Out (STOP)", "You can stop receiving SMS messages at any time by replying STOP to any message you receive.\n\n- Reply STOP to unsubscribe from all messages from that sender\n- Reply HELP to receive assistance\n- Reply INFO to receive information about the service\n\nAfter opting out, you will receive one confirmation message and no further messages from that sender. Opt-out requests are processed immediately."),
            ("7. Supported Carriers & Rates", "I'm On Social's SMS messaging is supported by all major U.S. wireless carriers including AT&T, T-Mobile, Verizon, and others. Message and data rates may apply depending on your wireless carrier plan. I'm On Social does not charge separately for SMS messages received."),
            ("8. TCPA Compliance", "I'm On Social platform users are required to comply with the Telephone Consumer Protection Act (TCPA) and all applicable federal and state communications laws. Platform users must obtain proper written or verbal consent before sending automated messages and honor all opt-out requests immediately.\n\nVI Ventures Group LLC reserves the right to suspend or terminate any user account found to be in violation of TCPA or these messaging policies."),
            ("9. A2P 10DLC Registration", "I'm On Social uses A2P (Application-to-Person) 10DLC (10-Digit Long Code) messaging registration as required by U.S. mobile carriers.\n\nRegistered use case: Relationship follow-up, customer engagement, appointment reminders, review requests, and account notifications for opted-in users and their contacts."),
            ("10. Privacy", "Your phone number and message history are used solely for the purpose of facilitating communications between you and the I'm On Social user you have a relationship with. We do not sell phone numbers to third parties. For full details, see our Privacy Policy at https://imonsocial.com/privacy."),
            ("11. Contact & Support", "I'm On Social is operated by VI Ventures Group LLC.\nEmail: support@imonsocial.com\nWebsite: https://imonsocial.com\n\nTo opt out: Reply STOP to any message.\nFor help: Reply HELP or email support@imonsocial.com."),
        ],
    },
}


# ── Generate all pages ────────────────────────────────────────────────────────

# Generate all pages
for slug, data in PAGES.items():
    html = TEMPLATE.format(
        title=data["title"],
        title_upper=data["title"].upper(),
        tagline=data["tagline"],
        desc=data["desc"],
        css=CSS,
        nav=NAV_HTML,
        modal=DEMO_MODAL_HTML + CONTACT_MODAL_HTML,
        feature_cards=make_feature_cards(data["features"]),
    ).replace("{footer}", FOOTER_HTML)
    path = f"/app/marketing/build/{slug}/index.html"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(html)
    print(f"Created: {slug}")

# Generate legal pages
for slug, data in LEGAL_PAGES.items():
    html = LEGAL_TEMPLATE.format(
        title=data["title"],
        eyebrow=data["eyebrow"],
        desc=data["desc"],
        meta=data["meta"],
        stop_box=data["stop_box"],
        sections=make_legal_sections(data["sections"]),
        related=data["related"],
        css=CSS,
        nav=NAV_HTML,
        footer=FOOTER_HTML + DEMO_MODAL_HTML + CONTACT_MODAL_HTML,
    )
    path = f"/app/marketing/build/{slug}/index.html"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(html)
    print(f"Created legal: {slug}")

print(f"\nDone! {len(PAGES) + len(LEGAL_PAGES)} pages total.")

# Generate demo page
demo_html = DEMO_PAGE_HTML.format(css=CSS, nav=NAV_HTML, footer=FOOTER_HTML + DEMO_MODAL_HTML + CONTACT_MODAL_HTML)
os.makedirs("/app/marketing/build/demo", exist_ok=True)
with open("/app/marketing/build/demo/index.html", "w") as f:
    f.write(demo_html)
print("Created: demo")
