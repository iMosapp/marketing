"""Reusable page sections for the new marketing site. Every section takes plain data from content.py."""
from home import phone, tour
from layout import FEATURES, esc, icon, slug

FEATURE_INDEX = {p: (n, d) for _, items in FEATURES for n, p, d in items}
FEATURE_INDEX.update({"/organizations/": ("For businesses", "One memory for the whole team"), "/individuals/": ("For sales professionals", "Your book of business, organized"),
                      "/pricing/": ("Pricing", "$100/mo individual, $75 per user for teams"), "/why-imonsocial/": ("Why i'M On Social", "The relationship layer your CRM is missing"),
                      "/training/": ("Training", "Short lessons in the app"), "/help/": ("Help Center", "Answers, the help assistant and our team"),
                      "/features/": ("All features", "Everything in one app"), "/industries/": ("Industries", "Built for relationship businesses")})


def page_hero(site, key, overline, h1, sub, screen=None, alt="", secondary=None):
    sec = ""
    if secondary:
        label, path = secondary
        sec = f'<a class="btn btn-outline btn-lg" href="{site.u(path)}" data-testid="{key}-hero-secondary-cta">{esc(label)}</a>'
    ctas = (f'<div class="cta-row reveal"><button class="btn btn-gold btn-lg" type="button" data-demo="hero" data-testid="{key}-hero-book-demo-cta">Book a Demo</button>{sec}</div>')
    copy = (f'<p class="overline reveal">{esc(overline)}</p><h1 class="reveal" data-testid="{key}-h1">{h1}</h1>'
            f'<p class="lead reveal">{esc(sub)}</p>{ctas}')
    if not screen:
        return f'<section class="page-hero solo" data-testid="{key}-hero"><div class="wrap"><div class="solo-copy">{copy}</div></div></section>'
    return f"""<section class="page-hero" data-testid="{key}-hero">
  <div class="wrap page-hero-grid">
    <div class="hero-copy">{copy}</div>
    <div class="page-hero-visual">{phone(site, screen, alt, "phone-hero", True, f"{key}-hero-phone")}<p class="screen-note">Real app screen. Demo data.</p></div>
  </div>
</section>"""


def section_head(overline, h2, sub="", center=False):
    s = f'<p class="reveal muted">{esc(sub)}</p>' if sub else ""
    return f'<div class="section-head{" center" if center else ""}"><p class="overline reveal">{esc(overline)}</p><h2 class="reveal">{esc(h2)}</h2>{s}</div>'


def points(key, overline, h2, items, alt_bg=True):
    tiles = "".join(f"""<article class="tile reveal" style="--d:{i * 80}ms" data-testid="{key}-point-{i + 1}">
      <span class="tile-ico">{icon(ic, 22)}</span><h3>{esc(t)}</h3><p>{esc(d)}</p></article>""" for i, (ic, t, d) in enumerate(items))
    return f"""<section class="section{' value' if alt_bg else ''}" data-testid="{key}-points">
  <div class="wrap">{section_head(overline, h2)}<div class="tiles tiles-{min(len(items), 4)}">{tiles}</div></div>
</section>"""


def split(site, key, n, overline, h2, text, bullets=(), screen=None, alt="", flip=False, note=""):
    lis = "".join(f'<li>{icon("check", 18)}<span>{esc(b)}</span></li>' for b in bullets)
    ul = f'<ul class="checks">{lis}</ul>' if lis else ""
    vis = ""
    if screen:
        cap = f'<p class="split-note">{esc(note)}</p>' if note else ""
        vis = f'<div class="split-visual reveal">{phone(site, screen, alt, "phone-split")}{cap}</div>'
    return f"""<section class="section split{' flip' if flip else ''}{' no-visual' if not screen else ''}" data-testid="{key}-split-{n}">
  <div class="wrap split-grid">
    <div class="split-copy"><p class="overline reveal">{esc(overline)}</p><h2 class="reveal">{esc(h2)}</h2><p class="reveal muted split-text">{esc(text)}</p><div class="reveal">{ul}</div></div>
    {vis}
  </div>
</section>"""


def faq(key, items, h2="Fair questions"):
    rows = "".join(f"""<details class="faq-item reveal" data-testid="{key}-faq-{i + 1}"><summary data-testid="{key}-faq-{i + 1}-toggle"><span>{esc(q)}</span>{icon("chev", 20, "ico chev")}</summary>
      <p>{esc(a)}</p></details>""" for i, (q, a) in enumerate(items))
    return f"""<section class="section faq" data-testid="{key}-faq-section">
  <div class="wrap faq-grid">{section_head("Questions", h2)}<div class="faq-list">{rows}</div></div>
</section>"""


def faq_ld(items):
    return {"@context": "https://schema.org", "@type": "FAQPage",
            "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in items]}


def related(site, key, paths, h2="Keep exploring"):
    cards = "".join(f"""<a class="rel-card reveal" style="--d:{i * 80}ms" href="{site.u(p)}" data-testid="{key}-related-{slug(FEATURE_INDEX[p][0])}">
      <strong>{esc(FEATURE_INDEX[p][0])}</strong><span>{esc(FEATURE_INDEX[p][1])}</span><i>{icon("arrow", 18)}</i></a>""" for i, p in enumerate(paths))
    return f'<section class="section related" data-testid="{key}-related"><div class="wrap"><h2 class="related-h reveal">{esc(h2)}</h2><div class="rel-grid">{cards}</div></div></section>'


def problem_band(key, h2, lines, kicker):
    lis = "".join(f'<li class="reveal" style="--d:{i * 80}ms">{esc(x)}</li>' for i, x in enumerate(lines))
    return f"""<section class="band band-ink problem" data-testid="{key}-problem">
  <div class="wrap problem-grid"><h2 class="reveal">{esc(h2)}</h2><ul class="problem-list">{lis}</ul></div>
  <div class="wrap"><p class="kicker reveal">{esc(kicker)}</p></div>
</section>"""


def price_strip(site, key, label, price, note):
    return f"""<section class="price-strip" data-testid="{key}-price-strip">
  <div class="wrap"><div class="strip-inner reveal">
    <div><p class="overline">{esc(label)}</p><p class="strip-price" data-testid="{key}-price">{esc(price)}</p><p class="muted">{esc(note)}</p></div>
    <div class="strip-actions"><button class="btn btn-gold" type="button" data-demo="pricing_strip" data-testid="{key}-price-book-demo">Book a Demo</button>
    <a class="text-link" href="{site.u('/pricing/')}" data-testid="{key}-price-link">See pricing {icon("arrow", 16)}</a></div>
  </div></div>
</section>"""


def cta_band(key, h2="Be the business they never forget.", p="Build stronger relationships, remember what matters, and make every customer connection count."):
    return f"""<section class="band band-ink final" data-testid="{key}-final-cta">
  <div class="wrap final-inner">
    <h2 class="reveal">{esc(h2)}</h2>
    <p class="reveal">{esc(p)}</p>
    <button class="btn btn-gold btn-lg reveal" type="button" data-demo="cta" data-testid="{key}-final-book-demo-cta">Book Your Demo</button>
  </div>
</section>"""


def chips(site, key, items, h2):
    cs = "".join(f'<a class="chip" href="{site.u(p)}" data-testid="{key}-chip-{p.strip("/")}">{esc(n)}</a>' for n, p in items)
    return f'<section class="section industries" data-testid="{key}-chips"><div class="wrap ind-row"><h2 class="reveal">{esc(h2)}</h2><div class="chips reveal">{cs}</div></div></section>'


def checklist(key, overline, h2, items, sub=""):
    lis = "".join(f'<li class="reveal" style="--d:{(i % 6) * 50}ms">{icon("check", 18)}<span>{esc(x)}</span></li>' for i, x in enumerate(items))
    return f'<section class="section value" data-testid="{key}-checklist"><div class="wrap">{section_head(overline, h2, sub, center=True)}<ul class="check-grid">{lis}</ul></div></section>'


def card_grid(site, key, groups):
    out = []
    for g, items in groups:
        cards = "".join(f"""<a class="feat-card reveal" style="--d:{i * 70}ms" href="{site.u(p)}" data-testid="{key}-card-{slug(n)}">
          <span class="tile-ico">{icon(ic, 22)}</span><strong>{esc(n)}</strong><span>{esc(d)}</span><i class="feat-more">Learn more {icon("arrow", 16)}</i></a>"""
                        for i, (ic, n, p, d) in enumerate(items))
        out.append(f'<div class="feat-group"><h2 class="feat-group-h reveal">{esc(g)}</h2><div class="feat-grid">{cards}</div></div>')
    return f'<section class="section feats" data-testid="{key}-grid"><div class="wrap">{"".join(out)}</div></section>'


def tour_band(site):
    return tour(site)
