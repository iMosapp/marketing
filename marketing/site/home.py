"""Homepage content (approved outline, Oct 2026). Real app screens only, from the fictional preview demo workspace."""
from layout import esc, icon

TITLE = "i'M On Social | The Relationship OS for businesses"
DESC = ("Your CRM remembers the deal. i'M On Social remembers the person. Capture what matters, stay connected automatically "
        "and never let a customer slip through the cracks.")

PROBLEM = ["Hundreds of past customers sit in a phone, a CRM and a stack of business cards.",
           "Follow-ups slip the moment the week gets busy.",
           "The details that matter, a kid's name, a move, a renewal date, are gone by the next conversation.",
           "When someone leaves, their customers and the history go with them."]

STEPS = [("01", "Capture", "mic", "Share your card by text or QR, add a contact in seconds, or import your phone contacts. After a meeting, tap record and just talk.",
          "screen-voice-record", "Voice memos screen with a large record button"),
         ("02", "Remember", "spark", "Jessi turns a 20-second voice note into clean notes, personal details and a follow-up, filed on the right person.",
          "screen-voice-memo", "Voice memo summarized by Jessi and attached to a contact"),
         ("03", "Stay connected", "send", "Birthday, anniversary and check-in messages go out on time, with your approval rules. Every morning you see who to talk to and why.",
          "screen-home", "Home screen with Do this next and Your 3 for Today")]

VALUE = [("heart", "Never forget a customer", "Family, interests, the last conversation and important dates live on every contact, ready before you reach out."),
         ("calendar", "Follow up without relying on memory", "Campaigns and date triggers handle the routine touches. Opt-outs and quiet hours are always respected."),
         ("shield", "Protect your customer relationships", "Your company keeps the business number, the contacts and the history when someone moves on."),
         ("trend", "Turn relationships into revenue", "Ask for reviews in one tap, spot referral chances and be the first call when they are ready to buy again.")]

TOUR = [("intel", "Relationship intel", "Every text, call and voice note becomes one snapshot: family, interests, last touch and what Jessi suggests next.",
         "screen-contact-intel", "Contact snapshot with personal details and Relationship Intel"),
        ("voice", "Voice memos", "Talk for 20 seconds after a meeting. Jessi transcribes it, summarizes it and files it on the right contact.",
         "screen-voice-memo", "Voice memos attached to contacts with summaries"),
        ("today", "People to Talk To Today", "A short list every morning of who to reach out to and why: card views, follow-ups due, birthdays coming up.",
         "screen-people-today", "People to Talk To Today list with reasons and Follow Up buttons"),
        ("campaigns", "Campaigns & follow-up", "Birthday wishes, client anniversaries and check-ins run on their own, with your rules and opt-outs respected.",
         "screen-campaigns", "Campaigns list with Birthday wishes, Client anniversary and 90-day check-in"),
        ("inbox", "Inbox & texting", "Text from a business number your company controls. Jessi drafts a reply and you send, edit or dismiss it.",
         "screen-inbox-thread", "Text thread with a Jessi suggested reply"),
        ("team", "Team view", "Managers see what each person should work on today and can nudge them in one tap.",
         "screen-team-today", "Team Today screen showing each rep and their follow-ups")]

AUDIENCE = [("business", "For businesses", "Give your whole team the same memory.",
             ["Team Today shows who each person should work on", "Company-owned business numbers and shared inboxes",
              "Contacts and history stay when someone leaves", "Leads in by email, ADF or webhook. Zapier, Make and an open API"],
             "Teams $75 per user / month", "home_business", "card-ink"),
            ("individual", "For sales professionals", "Your book of business, finally organized.",
             ["Your 3 for Today, every morning", "Voice memos that turn into notes and follow-ups",
              "A digital card, review link and link page you can share anywhere", "On your iPhone and the web"],
             "From $100 / month", "home_individual", "card-light")]

CHIPS = [("Automotive & equipment", "/dealers/"), ("Real estate", "/real-estate/"), ("Insurance & financial services", "/insurance/"), ("Home services", "/home-services/"),
         ("Powersports", "/powersports/"), ("Salons & wellness", "/salons/"), ("Fitness", "/fitness/"), ("Restaurants", "/restaurants/"), ("Medical & dental", "/medical/"), ("All industries", "/industries/")]

JSONLD = [{"@context": "https://schema.org", "@type": "Organization", "name": "i'M On Social", "url": "https://www.imonsocial.com/",
           "logo": "https://www.imonsocial.com/logo.png", "sameAs": ["https://instagram.com/imonsocialapp", "https://tiktok.com/@imonsocialapp", "https://youtube.com/@imonsocial"]},
          {"@context": "https://schema.org", "@type": "WebSite", "name": "i'M On Social", "url": "https://www.imonsocial.com/"},
          {"@context": "https://schema.org", "@type": "SoftwareApplication", "name": "i'M On Social", "operatingSystem": "iOS, Web", "applicationCategory": "BusinessApplication",
           "offers": {"@type": "Offer", "price": "100", "priceCurrency": "USD"}}]


STATUS = '<div class="status" aria-hidden="true"><span>9:41</span><i class="island"></i><span class="sig"><b></b><b></b><b></b><b></b></span></div>'


def phone(site, img, alt, cls="", eager=False, tid=""):
    load = 'fetchpriority="high"' if eager else 'loading="lazy"'
    t = f' data-testid="{tid}"' if tid else ""
    return (f'<div class="phone {cls}"{t}><div class="phone-screen">{STATUS}'
            f'<img src="{site.a("img/" + img + ".webp")}" alt="{esc(alt)}" width="640" height="1385" {load} decoding="async"/></div></div>')


def hero(site):
    return f"""<section class="hero" data-testid="hero-section">
  <div class="wrap hero-grid">
    <div class="hero-copy">
      <p class="overline reveal">The Relationship OS</p>
      <h1 class="reveal" data-testid="hero-h1">Your CRM remembers the deal. <span class="ink-gold">i'M On Social remembers the person.</span></h1>
      <p class="lead reveal">Turn every customer interaction into a relationship that lasts. Capture what matters, stay connected automatically, and never let another opportunity slip through the cracks.</p>
      <div class="cta-row reveal">
        <button class="btn btn-gold btn-lg" type="button" data-demo="home_hero" data-testid="hero-book-demo-cta">Book a Demo</button>
        <a class="btn btn-outline btn-lg" href="#how-it-works" data-scroll="how-it-works" data-testid="hero-see-how-it-works-cta">See How It Works</a>
      </div>
      <div class="hero-meta reveal">
        <p class="trust" data-testid="hero-trust-line">iPhone and web. Works next to the CRM you already use.</p>
        <p class="price-line" data-testid="hero-price-line">From $100/mo for individuals. Teams $75 per user. <a href="{site.u('/pricing/')}" data-testid="hero-pricing-link">See pricing</a></p>
        <button class="watch" type="button" data-video data-testid="watch-story-link"><span class="watch-ico">{icon("play", 14)}</span>Watch the 46-second story</button>
      </div>
    </div>
    <div class="hero-visual" aria-label="Real screens from the i'M On Social app">
      {phone(site, "screen-contact-intel", "Contact snapshot for Marcus Delgado with personal details and Jessi's suggestion", "phone-back", True, "hero-phone-back")}
      {phone(site, "screen-people-today", "People to Talk To Today list with the reason to reach out to each person", "phone-front", True, "hero-phone-front")}
      <p class="screen-note">Real app screens. Demo data.</p>
    </div>
  </div>
</section>"""


def problem():
    lines = "".join(f'<li class="reveal" style="--d:{i * 80}ms">{esc(x)}</li>' for i, x in enumerate(PROBLEM))
    return f"""<section class="band band-ink problem" data-testid="problem-section">
  <div class="wrap problem-grid">
    <h2 class="reveal">You're sitting on relationships you've forgotten.</h2>
    <ul class="problem-list">{lines}</ul>
  </div>
  <div class="wrap"><p class="kicker reveal" data-testid="problem-kicker">The problem isn't that people don't care. It's that no one can remember everything.</p></div>
</section>"""


def how(site):
    steps = "".join(f"""<article class="step reveal" style="--d:{i * 120}ms" data-testid="how-step-{t.lower().replace(' ', '-')}">
      <div class="step-head"><span class="step-num">{n}</span><span class="step-ico">{icon(ic, 18)}</span></div>
      <h3>{esc(t)}</h3><p>{esc(d)}</p>
      {phone(site, img, alt, "phone-sm")}
    </article>""" for i, (n, t, ic, d, img, alt) in enumerate(STEPS))
    return f"""<section class="section how" id="how-it-works" data-testid="how-it-works-section">
  <div class="wrap">
    <div class="section-head"><p class="overline reveal">How it works</p><h2 class="reveal">Capture it once. Remember it forever. Stay connected for good.</h2></div>
    <div class="steps">{steps}</div>
  </div>
</section>"""


def value():
    tiles = "".join(f"""<article class="tile reveal" style="--d:{i * 80}ms" data-testid="value-tile-{i + 1}">
      <span class="tile-ico">{icon(ic, 22)}</span><h3>{esc(t)}</h3><p>{esc(d)}</p></article>""" for i, (ic, t, d) in enumerate(VALUE))
    return f"""<section class="section value" data-testid="value-section">
  <div class="wrap value-grid">
    <div class="section-head sticky-head"><p class="overline reveal">Why it matters</p><h2 class="reveal">Relationships are your most valuable asset. Treat them that way.</h2>
    <p class="reveal muted">Customers who feel remembered come back and send their friends. i'M On Social makes sure every customer feels remembered.</p></div>
    <div class="tiles">{tiles}</div>
  </div>
</section>"""


def tour(site):
    tabs = "".join(f"""<button class="tour-tab{' is-active' if i == 0 else ''}" type="button" role="tab" id="tour-tab-{k}" aria-selected="{'true' if i == 0 else 'false'}" aria-controls="tour-panel" data-index="{i}" data-testid="product-tour-tab-{k}">
        <span class="tt-title">{esc(t)}</span><span class="tt-cap">{esc(c)}</span><span class="tt-bar" aria-hidden="true"><i></i></span></button>""" for i, (k, t, c, _, _) in enumerate(TOUR))
    shots = "".join(f'<img class="tour-shot{" is-active" if i == 0 else ""}" src="{site.a("img/" + img + ".webp")}" alt="{esc(alt)}" width="640" height="1385" loading="lazy" decoding="async" data-testid="product-tour-screen-{k}"/>'
                    for i, (k, _, _, img, alt) in enumerate(TOUR))
    return f"""<section class="section tour" id="product" data-testid="product-tour-section">
  <div class="wrap">
    <div class="section-head center"><p class="overline reveal">See the actual product</p><h2 class="reveal">This is the app your team opens every morning.</h2>
    <p class="reveal muted">Real screens from the iPhone app. Tap through what it does.</p></div>
    <div class="tour-grid reveal" data-tour>
      <div class="tour-tabs" role="tablist" aria-label="Product tour">{tabs}</div>
      <div class="tour-stage" id="tour-panel" role="tabpanel" aria-live="polite">
        <div class="phone phone-tour" data-testid="product-tour-phone"><div class="phone-screen">{STATUS}<div class="shots">{shots}</div></div></div>
        <p class="tour-caption" data-testid="product-tour-caption">{esc(TOUR[0][2])}</p>
      </div>
    </div>
  </div>
</section>"""


def audience():
    cards = "".join(f"""<article class="aud {cls} reveal" style="--d:{i * 100}ms" data-testid="audience-card-{k}">
      <p class="overline">{esc(label)}</p><h3>{esc(h)}</h3>
      <ul>{''.join(f'<li>{icon("check", 18)}<span>{esc(b)}</span></li>' for b in bullets)}</ul>
      <div class="aud-foot"><p class="aud-price" data-testid="audience-price-{k}">{esc(price)}</p>
      <button class="btn {'btn-gold' if cls == 'card-ink' else 'btn-ink'}" type="button" data-demo="{src}" data-testid="audience-book-demo-{k}">Book a Demo</button></div>
    </article>""" for i, (k, label, h, bullets, price, src, cls) in enumerate(AUDIENCE))
    return f"""<section class="section audience" data-testid="audience-section">
  <div class="wrap">
    <div class="section-head center"><p class="overline reveal">Built for both</p><h2 class="reveal">For the business, and for the people who sell for it.</h2></div>
    <div class="aud-grid">{cards}</div>
  </div>
</section>"""


def industries(site):
    chips = "".join(f'<a class="chip" href="{site.u(p)}" data-testid="industry-chip-{p.strip("/")}">{esc(n)}</a>' for n, p in CHIPS)
    return f"""<section class="section industries" data-testid="industries-section">
  <div class="wrap ind-row">
    <h2 class="reveal">Wherever relationships drive repeat business.</h2>
    <div class="chips reveal">{chips}</div>
  </div>
</section>"""


def final_cta():
    return """<section class="band band-ink final" data-testid="final-cta-section">
  <div class="wrap final-inner">
    <h2 class="reveal">Be the business they never forget.</h2>
    <p class="reveal">Build stronger relationships, remember what matters, and make every customer connection count.</p>
    <button class="btn btn-gold btn-lg reveal" type="button" data-demo="home_cta" data-testid="final-book-demo-cta">Book Your Demo</button>
  </div>
</section>"""


def render(site):
    body = "\n".join([hero(site), problem(), how(site), value(), tour(site), audience(), industries(site), final_cta()])
    return site.page(TITLE, DESC, "/", body, JSONLD, "home")
