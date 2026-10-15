# i'M On Social - Marketing Website Cleanup & Conversion Plan
Status (Oct 16 2026): APPROVED. Phase 0 done in `marketing/build` (not live until Save to GitHub). Phase 1 homepage APPROVED; Phases 2-3 (every page, redirects, noindex, sitemap) built + tested in STAGING only (`marketing/site/` -> `marketing/build-preview/`), awaiting owner review. Phase 4 tracking SKIPPED by owner for now. Phase 5: owner APPROVED (Oct 16); `build.py production --approved` already run, live once the owner updates GitHub. Owner picks Oct 16: neutral-mix demo data, small "From $100/mo" line on the homepage, 46 s video as a "Watch the story" lightbox link, soften the medical HIPAA + partner AI-answers lines, Phase 1 = homepage + nav/footer + demo form only.
Site: https://www.imonsocial.com = static HTML in `marketing/build/` on Vercel (publishes on Save to GitHub). Staging copy for review: `marketing/build-preview/` served at `{preview}/api/marketing-preview/` (now public GET in preview, `services/route_guard.py`).

Already done this session (separate from this plan):
- Widget `FE2POg13` on all 67 public pages (old `XkTvZEUb` is disabled in production, which is why the widget vanished). Goes live on Save to GitHub.
- Widget chat pacing (Natural / Relaxed / Instant per store, long answers split into 2-3 texts). Needs Deploy + eas update.

---
## 1. Current website audit (evidence from `marketing/build`, Oct 15 2026)

### 1.1 Inventory
69 HTML pages. Groups:
- Core: `/` (80 KB, 1,823 words, 13 sections), `/platform` (66 KB), `/features`, `/pricing`, `/demo`, `/why-imonsocial`, `/future`, `/landing`.
- Feature pages (generic template, ~540 words each): `/digital-card`, `/reviews`, `/store-reviews`, `/showcase`, `/congrats-template`, `/date-triggers`, `/inbox`, `/jessi`, `/leaderboard`, `/seo`, `/hub`, `/organizations`, `/individuals`, `/training`, `/help`.
- Industry pages (hand-built, ~1,450 words each): `/dealers`, `/automotive`, `/powersports`, `/real-estate`, `/insurance`, `/home-services`, `/salons`, `/medical`, `/fitness`, `/restaurants`.
- Sales enablement / internal: `/presentations/*` (13 decks), `/presentation`, `/salespresentation`, `/outreach` (cold-outreach templates for reaching dealership GMs), `/tiktok` (video script), `/appdirectory` (in-app screen directory), `/industries.html` (noindex pitch directory), `/install` (PWA install).
- Paid-ad landers: `/ad-autopilot`, `/ad-digital-card`, `/ad-reviews`, `/ad-showcase`.
- Partner: `/calendar-systems`, `/calendar-systems/dealers`.
- Special (leave as is): `/mybaby` (investor deck), `/card` (QR landing), `/feature-sheet` (buried), `/developers`, `/go/card`, `/relationship-os` (old deck URL), `/404`.
- Legal: `/privacy`, `/terms`, `/sms-terms`.

### 1.2 Findings (ranked)
| # | Severity | Finding | Where |
|---|---|---|---|
| A1 | HIGH | **Fabricated testimonial + unsupported stats on a live, indexable page**: "We've seen a 40% increase in repeat customers since switching...", "10x More Follow-Ups / 67% Better Retention / 3x More Referrals" | `/landing` |
| A2 | HIGH | **Unsourced statistics on every industry page and the homepage** (74% vs 44%, 68% vs 18%, 82% vs 35%, 91% vs 14%, 70%, 92% vs 67%, 73% by Day 3, 21x) | `/`, `/dealers`, `/real-estate`, `/salons`, `/medical`, `/restaurants`, `/fitness`, `/insurance` |
| A3 | HIGH | **"WhatsApp" claimed as an inbox channel** ("SMS, WhatsApp, email in one place") in the nav descriptions of 20+ pages. In the app WhatsApp is a *share* option (opens WhatsApp to send a card or link), not an inbox channel | nav on 20+ pages, `/` |
| A4 | HIGH | **"Start Free Trial" / "Free to start" / "No credit card required"** on 21 footers + pricing + individuals. The Oct 11 founder acceptance report rated public self-serve **NO-GO** (founder-assisted pilot only). Stripe plans do carry 7/14-day trials, but the self-serve path is not approved | footers, `/pricing`, `/individuals` |
| A5 | HIGH | **Outcome promises**: "Triple your Google reviews in 90 days", "ROI in days", "Try It Free" | `/ad-reviews`, `/pricing`, `/ad-*` |
| A6 | HIGH | **No conversion tracking at all** (no GA4, Meta Pixel, TikTok Pixel, Google Ads tag). Forms send `lead_source` but **no UTM / click IDs** even though `/api/demo-requests` already classifies `utm_source/utm_medium/utm_campaign`. Paid traffic cannot be measured today | all pages |
| A7 | HIGH | **No `sitemap.xml` and no `robots.txt`** (both 404 in production) | site root |
| A8 | MED | **Navigation overload**: 3 dropdowns with 31 items (Products 11, Solutions 13, Resources 7) + Pricing; two different blue/black/gold primary CTA colors | every page |
| A9 | MED | **Footer inconsistency**: 3 different footers (home: 4 cols / 26 links; industry: 3 cols / 10 links; generic: 4 cols incl. Start Free Trial); Company column alone has 10 links | every page |
| A10 | MED | **Duplicate / competing pages**: `/dealers` vs `/automotive` vs `/salespresentation`; `/hub` vs `/organizations`; `/platform` vs `/features`; `/reviews` vs `/store-reviews`; `/future` vs `/why-imonsocial`; `/presentation` vs `/presentations` | see 4 |
| A11 | MED | **Internal sales material is public + indexable**: `/outreach` (scripts to pitch dealership GMs), `/tiktok` (our ad script), `/presentations/*` (13 decks, each with 2 H1s), `/appdirectory` (48 links to in-app routes that 404 on the marketing domain) | listed |
| A12 | MED | **Homepage is a feature catalog**: 13 sections, 1,823 words, 4 competing CTAs ("Take the 2-minute tour", "Book a Demo" x3, "Open the App", "See everything the platform does") | `/` |
| A13 | MED | **Medical page HIPAA answer** ("No PHI. No clinical content") is a compliance statement that needs counsel review before paid traffic | `/medical` |
| A14 | MED | **"Recommendation Ready: when someone asks ChatGPT or Google AI who to buy from, your name comes up"**: unverifiable outcome; the app has SEO/GEO Health tooling, not a guarantee of AI recommendations | 8 industry pages, 12 decks, `/seo` |
| A15 | MED | **Inconsistent consent**: homepage demo modal has an SMS opt-in checkbox; industry modals do not; the Contact form has none | modals |
| A16 | LOW | Canonical tag on only 4 of 69 pages; 5 pages without meta description; no structured data (Organization / SoftwareApplication / FAQ) anywhere | site-wide |
| A17 | LOW | Heavy assets: hero video 6.2 MB mp4 + 7.3 MB webm (`preload=metadata`, ok), ad slide PNGs ~1 MB each, TikTok clips 4 MB; inline CSS ~10-20 KB per page duplicated on every page | `build/` |
| A18 | LOW | `/relationship-os` serves a 200 meta-refresh instead of a real 301 | `build/vercel.json` |
| A19 | LOW | Copy inconsistency: "I'm On Social" vs "i'M On Social" vs "IMOS"; "The relationship engine" vs "Relationship OS" vs "Business Relationship Management" | site-wide |
| A20 | LOW | Accessibility: icon-only buttons without labels in modals, low-contrast grey captions (#8E8E93 on white = 3.4:1), images on ad pages missing alt | site-wide |

### 1.3 Claims verification (website vs the app today)
| Claim | Reality in the app | Website wording to use |
|---|---|---|
| SMS texting | Live: dedicated business number per rep (Twilio), STOP/opt-in compliance, quiet hours | "Text from a business number your company controls" |
| WhatsApp | Share option only | "Share your card or a link by text, email, QR or WhatsApp" (never "inbox") |
| Email | Live (signature, analytics) | ok |
| AI relationship intelligence | Live: voice memos + recorded conversations transcribed, Relationship Intel briefing, AI follow-up suggestions, People to Talk To Today | "Jessi turns a 20-second voice note into notes and a follow-up" |
| Automatic follow-up | Live: campaigns, date triggers (birthday, anniversary, sold date), tag workflows, with safety rails + opt-out | "Set it once. Birthday, anniversary and check-in messages go out on time" (always "with your approval rules" / "opt-out respected") |
| Company-owned numbers | Live (store line + rep lines, reassignment, bulk transfer) | ok, phrase as "your company keeps the number and the history" |
| Data retention when reps leave | Live: bulk transfer keeps contacts, history, voice notes | ok |
| CRM integrations | Public API v1 + Zapier/Make + inbound lead intake (ADF/email/webhook). **CRM adapters (HubSpot/Salesforce/automotive CRMs) are NOT built** | "Works next to your CRM. Leads in by email, ADF or webhook; Zapier, Make and an open API" - no vendor logos |
| SEO / AEO | SEO Health + GEO Health tooling, shareable pages with rich previews | "Every card and page you share is built to be found" - no "ChatGPT will recommend you" |
| Reviews | Live: personal + store review pages, one-tap requests, Google/Yelp/Facebook links | "Ask for reviews in one tap" - no "triple" |
| Voice assistant (Live Jessi) | **Pilot**: Test Lab / founder voice pilot, capped minutes; not generally available | Only "Coming soon" or "In pilot" badge, or leave out of the homepage |
| Website widget (Text us / Call me now / Chat with Jessi) | Live | ok |
| Leads queue + speed-to-lead timers | Live | ok |
| Print QR + 4x6 leave-behind card | Live | ok |
| Billing / signup | Stripe plans exist (Individual $100/mo or $1,000/yr, intro $50/mo x3, Store $75/user min 5, $65/user 6+), founding partner pilot is founder-assisted. Public self-serve NOT approved | CTA = Book a Demo; prices only if you approve (see decisions) |
| App availability | iPhone: live on the App Store (id6774618559, `/get/site`). Android: not published (Play checklist pending). Web app: live | "iPhone and web today. Android coming soon." |
| Quantified stats / testimonials | None verified | Remove all until we have sourced data or approved customer quotes |

---
## 2. Recommended homepage structure (one story, ~650-800 words)
1. **Hero** - H1 "Your CRM remembers the deal. i'M On Social remembers the person." Sub "Turn every customer interaction into a relationship that lasts. Capture what matters, stay connected automatically, and never let another opportunity slip through the cracks." CTAs: **Book a Demo** (primary) + **See How It Works** (scrolls to step 3 section). Visual: real People to Talk To Today screen in a phone frame, with a second phone (contact intel) offset behind; small "Watch the 46-second story" link opens the existing ad video in a lightbox. Trust line under CTAs: "iPhone and web. Works next to the CRM you already use."
2. **The Problem** (dark band) - "You're sitting on relationships you've forgotten." 4 short lines (hundreds of contacts, forgotten follow-ups, forgotten details, people leave and the history goes with them) + kicker "The problem isn't that people don't care. It's that no one can remember everything." No statistics.
3. **How It Works** (`#how-it-works`) - 3 steps, each with one real screen: CAPTURE (share card / snap photo / add contact) -> REMEMBER (voice note -> Jessi organizes it) -> STAY CONNECTED (campaigns, reminders, People to Talk To Today). Steps animate in sequence; on mobile a horizontal swipe.
4. **The Business Value** - 4 tiles: Never Forget a Customer / Follow Up Without Relying on Memory / Protect Your Customer Relationships / Turn Relationships Into Revenue. One line each + one small visual (no icon soup).
5. **See the Actual Product** - interactive tour: 6 tabs (Relationship intel, Voice memo, People to Talk To Today, Campaigns & follow-up, Inbox, Team view) swapping a real screenshot in one phone frame, with a 2-line caption each. Auto-advances, pauses on hover/tap.
6. **Built for Businesses and Individuals** - 2 cards: FOR BUSINESSES (team visibility, continuity, company-owned numbers -> Book a Demo, `lead_source=home_business`) / FOR SALES PROFESSIONALS (personal book of business -> Book a Demo, `lead_source=home_individual`; switch to "Start your trial" only if you approve self-serve).
7. **Industries** (compact) - one line "Wherever relationships drive repeat business" + chips: Automotive & equipment, Real estate, Insurance & financial services, Home services, Powersports, Professional services, "and more" -> `/industries`.
8. **Final CTA** - "Be the business they never forget." + "Build stronger relationships, remember what matters, and make every customer connection count." + **Book Your Demo**.
Removed from the homepage (moved to their own pages): flywheel, "everything around the heart" catalog, company-number deep dive, App Store block (moves to footer + Resources), the second video placement.

## 3. Proposed navigation
`How It Works` (-> `/#how-it-works`) · `Features ▾` · `Solutions ▾` · `Pricing` · `Resources ▾`  ·  right: `Sign In` · **Book a Demo**
- Features ▾ (3 short groups + "All features"): Capture & remember (Voice memos & Jessi AI `/jessi`, Digital card & QR `/digital-card`, Link page & showcase `/showcase`) · Stay connected (Campaigns & date triggers `/date-triggers`, Inbox & texting `/inbox`, Congrats cards `/congrats-template`) · Grow & manage (Reviews `/reviews`, Leaderboards `/leaderboard`, SEO & visibility `/seo`) · All features `/features`.
- Solutions ▾: For businesses `/organizations` · For sales professionals `/individuals` · Automotive & equipment `/dealers` · Real estate `/real-estate` · Insurance & financial `/insurance` · Home services `/home-services` · Powersports `/powersports` · All industries `/industries`.
- Resources ▾: Help Center `/help` · Training `/training` · Why i'M On Social `/why-imonsocial` · Developers & API `/developers` · Get the iPhone app `/get/site`.
- One primary button style everywhere (gold pill, ink text). Mobile: full-screen sheet with the same 5 items as accordions + sticky "Book a Demo".
- Footer: brand row (logo, one-line promise, App Store badge, socials) + 4 columns (Product, Solutions, Resources, Company) max 6 links each; **each column is a collapsible accordion on mobile**, open on desktop. Legal row: Privacy · Terms · SMS Policy · Contact. Feature Sheet stays a faded footer link.

## 4. Pages: keep / consolidate / retire (URLs preserved via 301)
| Action | Pages |
|---|---|
| KEEP + rebuild on the new template | `/`, `/features`, `/pricing`, `/demo`, `/organizations`, `/individuals`, `/why-imonsocial`, `/jessi`, `/inbox`, `/digital-card`, `/showcase`, `/reviews`, `/congrats-template`, `/date-triggers`, `/leaderboard`, `/seo`, `/help`, `/training`, `/install` |
| KEEP (industry, one shared template, verified feature set only, industry wording) | `/dealers`, `/powersports`, `/real-estate`, `/insurance`, `/home-services` (in nav) + `/salons`, `/medical`, `/fitness`, `/restaurants` (kept for SEO, listed on `/industries`, not in nav) |
| NEW | `/industries` (public hub; the current noindex pitch directory moves under `/presentations/`), `sitemap.xml`, `robots.txt` |
| CONSOLIDATE (301) | `/automotive` -> `/dealers` · `/salespresentation` -> `/dealers` · `/hub` -> `/organizations` · `/platform` -> `/features` · `/store-reviews` -> `/reviews` (store section) · `/future` -> `/why-imonsocial` · `/presentation` -> `/presentations` · `/relationship-os` -> `/` (true 301) |
| RETIRE (301) | `/landing` -> `/` (fabricated testimonial) · `/ad-autopilot` -> `/date-triggers` · `/ad-digital-card` -> `/digital-card` · `/ad-reviews` -> `/reviews` · `/ad-showcase` -> `/showcase` (replaced by compliant ad landers in Phase 5) |
| KEEP but NOINDEX + out of nav | `/presentations/*`, `/outreach`, `/tiktok`, `/appdirectory` (links fixed to app.imonsocial.com), `/calendar-systems*` (partner) |
| LEAVE UNTOUCHED | `/mybaby`, `/card`, `/feature-sheet`, `/developers`, `/go/card`, legal text (new chrome only), `/404` |

## 5. Copy improvements (examples)
- Nav "Inbox & Messaging - SMS, WhatsApp, email in one place" -> "Inbox & texting - every text and email with a customer in one thread".
- Industry stat blocks ("68% of customers would return vs 18% actually do") -> plain-language problem lines without numbers ("Most customers would buy again. Most never hear from their salesperson again.").
- "Triple your Google reviews in 90 days" -> "Ask for a review in one tap, while the moment is fresh."
- "ROI in days" -> "One referral can cover the year." (remove if you prefer zero math)
- "Recommendation Ready: ChatGPT will recommend you" -> "Pages built to be found: every card and link you share is search-friendly."
- "Free to start / Start Free Trial" -> "Book a Demo" (or "Start your 7-day trial" only after self-serve is approved).
- Brand name always "i'M On Social"; category line always "The Relationship OS" with the descriptor "for businesses and the people who sell for them". No em dashes anywhere.

## 6. Visual design recommendations
- Light, premium base (white / warm off-white `#F7F6F2`) with two ink bands (`#0B0B0F`) for rhythm (Problem + Final CTA). One accent: brand gold `#C9A962` (same as the app). Logo colors only inside the logo. Blue removed from buttons.
- Type: Plus Jakarta Sans 700/800 for headings, Inter 400/500/600 for body (2 families, `display=swap`, preconnect).
- Buttons: one primary (gold pill, ink text, 48px tall), one secondary (ink outline pill), text links with an arrow. Same everywhere.
- Real screenshots only, in a CSS iPhone frame (no image of a device), WebP 2x, ~60-120 KB each, `loading=lazy` below the fold, explicit width/height (no layout shift).
- Motion: fade-up on scroll (IntersectionObserver, 400 ms), tour tab crossfade, hero phones float subtly; all disabled under `prefers-reduced-motion`. No parallax, no particle effects.
- Short paragraphs (max 2 lines on desktop), one idea per section, generous spacing (section padding 96-128 px desktop / 64 px mobile).
- One shared `site.css` + `site.js` (cached once) instead of 10-20 KB inline CSS per page. Bottom-right stays free for the chat widget.
- Accessibility: 4.5:1 text contrast, focus rings, labelled icon buttons, form labels, skip link, semantic headings (one H1 per page).

## 7. SEO preservation plan
- Every existing indexed URL keeps resolving: rebuilt in place or a 301 in `marketing/build/vercel.json` (the file Vercel actually reads) + `netlify.toml` mirror.
- Unique `<title>` (<= 60 chars) and meta description (<= 155) per page; canonical on every page (`https://www.imonsocial.com/<path>/`); OG/Twitter tags kept (`add_og_tags.py`).
- `sitemap.xml` (indexable pages only, lastmod) + `robots.txt` (allow all, sitemap line, disallow noindex sections).
- JSON-LD: Organization + WebSite on all pages, SoftwareApplication (iOS app) on home/pricing, FAQPage only where a real FAQ exists.
- Internal links: every feature/industry page links to 2-3 related pages + `/demo`. No thin "city/industry" doorway pages.
- After publish: submit sitemap in Google Search Console (owner), watch 404s for 2 weeks.

## 8. Conversion improvements
- **One demo form component** on every page: first name, mobile, email, company, industry (select), team size (optional), SMS consent checkbox (unchecked, optional, exact policy text), privacy/terms line. Sends `lead_source` (page + placement), `utm_source/medium/campaign/content/term`, `fbclid/ttclid/gclid`, landing page and referrer (stored in sessionStorage on first hit so they survive page changes). Backend already accepts and classifies UTMs; no app change needed beyond optionally storing the click IDs.
- Accurate confirmation: "Thanks, {first}. Someone from our team will reach out shortly to pick a time." (matches the Website lead source + ladder you wired in production). Optional later: book a time directly (the widget already has demo slots).
- Contact form gets the same consent text; both keep `lead-retry.js`.
- Tracking (needs your IDs): GA4, Meta Pixel (+ Conversions API later), TikTok Pixel, optional Google Ads. Events: `view_demo_form`, `generate_lead` / `Lead` / `SubmitForm` on success, `contact`, `video_play`, `widget_open`. Loaded async, after first paint.
- Paid-ad landers (Phase 5): `/start/<campaign>` template = hero + 3 steps + proof-free value + form on the page (no nav), one per ad angle, noindex.
- **Testing rule**: forms are tested against the PREVIEW backend only (Playwright rewrites the production API host). No production test leads, SMS or emails without your OK.

## 9. Implementation phases (all in staging; production only after your approval)
| Phase | What | Effort |
|---|---|---|
| 0 | Quick safety fixes you can ship first: remove `/landing` testimonial + stats (301), strip "WhatsApp" inbox claim, swap "Start Free Trial" -> "Book a Demo", remove "Triple"/"ROI in days", add `robots.txt` + `sitemap.xml`, real 301s | Small (~1 hour agent time, self-tested) |
| 1 | Design system (`site.css`, `site.js`), new nav + accordion footer, shared demo/contact modal with UTM + consent, Python generator (`marketing/site/`) that renders pages from data, homepage in staging | Large (biggest phase; ends with your preview link) |
| 2 | Fresh screenshots: seed a fictional demo workspace in preview (realistic names, 500-555 numbers, no texts sent), capture 8-10 screens at 390 px from the real app, frame + compress | Medium |
| 3 | Rebuild remaining pages on the template: features hub, pricing, demo, businesses/individuals, why, 10 feature pages, 9 industry pages (one template), legal chrome, `/industries`; apply the 301/noindex map | Large |
| 4 | SEO + tracking + QA: titles/descriptions/canonicals/JSON-LD, sitemap, tracking tags (once you send IDs), Lighthouse-style checks, accessibility pass, full testing-agent run (desktop + mobile, forms against preview) | Medium |
| 5 | Publish on approval (staging -> `marketing/build`, Save to GitHub), then paid-ad landers | Small + Medium |

Credit usage: I cannot see Emergent credit pricing from here, so treat this as relative effort. Phases 1 and 3 are the largest (about 35% and 30% of the total); Phase 2 about 15%, Phase 4 about 15%, Phases 0 and 5 about 5%. The main cost drivers are the number of preview review rounds and testing-agent runs (planned: one testing run after Phase 3 and one after Phase 4). The support team can turn this into credits.

## 10. Safety boundaries
Marketing site only. No changes to app functionality, customer data, Twilio, Stripe, voice AI, subscription rules or the mobile app. Preview demo data is fictional and uses 500-555 numbers only. Nothing is republished without your approval.
