"""Page renderers: each returns full HTML for one URL. Content lives in content.py, sections in blocks.py."""
import re
from pathlib import Path

import sys

import blocks as b
import content as c
import home
from layout import esc, icon

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import build_developers as devdocs  # noqa: E402

ORG_LD = home.JSONLD[0]


def _faq_ld(items):
    return [b.faq_ld(items)] if items else []


def feature_page(site, key, d):
    body = [b.page_hero(site, key, d["overline"], esc(d["h1"]), d["sub"], d["screen"], c.S[d["screen"]], ("See all features", "/features/")),
            b.points(key, "What it does", d["points_h2"], d["points"])]
    for i, (ov, h2, txt, bullets, scr, note) in enumerate(d["splits"]):
        body.append(b.split(site, key, i + 1, ov, h2, txt, bullets, scr, c.S.get(scr, ""), flip=i % 2 == 1, note=note))
    if d["faq"]:
        body.append(b.faq(key, d["faq"], "Questions people ask"))
    body += [b.related(site, key, d["related"]), b.cta_band(key)]
    return site.page(d["title"], d["desc"], d["path"], "\n".join(body), [ORG_LD] + _faq_ld(d["faq"]), key)


def audience_page(site, key, d):
    body = [b.page_hero(site, key, d["overline"], esc(d["h1"]), d["sub"], d["screen"], c.S[d["screen"]], ("See pricing", "/pricing/")),
            b.points(key, "What you get", d["points_h2"], d["points"])]
    for i, (ov, h2, txt, bullets, scr, note) in enumerate(d["splits"]):
        body.append(b.split(site, key, i + 1, ov, h2, txt, bullets, scr, c.S.get(scr, ""), flip=i % 2 == 1, note=note))
    body += [b.price_strip(site, key, *d["price"]), b.tour_band(site), b.related(site, key, d["related"]), b.cta_band(key)]
    return site.page(d["title"], d["desc"], d["path"], "\n".join(body), [ORG_LD], key)


def industry_page(site, key, d):
    others = [(v["name"], v["path"]) for k, v in c.INDUSTRY_PAGES.items() if k != key]
    body = [b.page_hero(site, key, d["overline"], esc(d["h1"]), d["sub"], d["screen"], c.S[d["screen"]], ("See How It Works", "/#how-it-works")),
            b.problem_band(key, *d["problem"]),
            b.points(key, "How teams use it", f"How {d['name'].lower()} teams use i'M On Social.", d["uses"], alt_bg=False),
            b.tour_band(site), b.faq(key, d["faq"]), b.chips(site, key, others, "Also built for"), b.cta_band(key)]
    return site.page(d["title"], d["desc"], d["path"], "\n".join(body), [ORG_LD] + _faq_ld(d["faq"]), key)


def features_hub(site):
    d = c.FEATURES_HUB
    body = [b.page_hero(site, "features", d["overline"], esc(d["h1"]), d["sub"], secondary=("See pricing", "/pricing/")),
            b.card_grid(site, "features", d["groups"]), b.checklist("features", "Also included", "And the things that make it all work.", d["also"]),
            b.tour_band(site), b.cta_band("features")]
    return site.page(d["title"], d["desc"], d["path"], "\n".join(body), [ORG_LD], "features")


def industries_hub(site):
    d = c.INDUSTRIES_HUB
    groups = [("Choose your industry", [(v["icon"], v["name"], v["path"], v["sub"]) for v in c.INDUSTRY_PAGES.values()])]
    body = [b.page_hero(site, "industries", d["overline"], esc(d["h1"]), d["sub"], secondary=("See all features", "/features/")),
            b.card_grid(site, "industries", groups), b.cta_band("industries")]
    return site.page(d["title"], d["desc"], d["path"], "\n".join(body), [ORG_LD], "industries")


def plan_card(site, p):
    k, name, price, per, note, items, src, featured = p
    lis = "".join(f'<li>{icon("check", 18)}<span>{esc(x)}</span></li>' for x in items)
    return f"""<article class="plan{' plan-featured' if featured else ''} reveal" data-testid="pricing-plan-{k}">
      <p class="overline">{esc(name)}</p>
      <p class="plan-price" data-testid="pricing-plan-{k}-price"><strong>{esc(price)}</strong><span>{esc(per)}</span></p>
      <p class="plan-note" data-testid="pricing-plan-{k}-note">{esc(note)}</p>
      <ul class="checks">{lis}</ul>
      <button class="btn {'btn-gold' if featured else 'btn-ink'} btn-block" type="button" data-demo="{src}" data-testid="pricing-plan-{k}-book-demo">Book a Demo</button>
    </article>"""


def pricing(site):
    d = c.PRICING
    plans = "".join(plan_card(site, p) for p in d["plans"])
    body = [b.page_hero(site, "pricing", d["overline"], esc(d["h1"]), d["sub"]),
            f'<section class="section plans-sec" data-testid="pricing-plans"><div class="wrap plans">{plans}</div>'
            f'<p class="wrap plans-foot reveal">Prices in US dollars, billed monthly. Every plan starts with a short demo so we can set it up around your business.</p></section>',
            b.checklist("pricing", "Everything included", "Every feature, in every plan.", d["included"]), b.faq("pricing", d["faq"], "Pricing questions"),
            b.cta_band("pricing")]
    ld = [ORG_LD, {"@context": "https://schema.org", "@type": "SoftwareApplication", "name": "i'M On Social", "operatingSystem": "iOS, Web",
                   "applicationCategory": "BusinessApplication", "offers": [
                       {"@type": "Offer", "name": "Individual", "price": "100", "priceCurrency": "USD"},
                       {"@type": "Offer", "name": "Team (per user, 5-seat minimum)", "price": "75", "priceCurrency": "USD"}]}] + _faq_ld(d["faq"])
    return site.page(d["title"], d["desc"], d["path"], "\n".join(body), ld, "pricing")


def demo(site):
    d = c.DEMO
    steps = "".join(f'<li class="reveal" style="--d:{i * 90}ms"><span class="step-num">0{i + 1}</span><div><strong>{esc(t)}</strong><p>{esc(x)}</p></div></li>'
                    for i, (t, x) in enumerate(d["steps"]))
    body = f"""<section class="page-hero demo-hero" data-testid="demo-page-hero">
  <div class="wrap demo-grid">
    <div class="hero-copy">
      <p class="overline reveal">{esc(d['overline'])}</p><h1 class="reveal" data-testid="demo-page-h1">{esc(d['h1'])}</h1><p class="lead reveal">{esc(d['sub'])}</p>
      <ol class="demo-steps">{steps}</ol>
      <p class="price-line reveal" data-testid="demo-page-price-line">From $100/mo for individuals. Teams $75 per user. <a href="{site.u('/pricing/')}" data-testid="demo-page-pricing-link">See pricing</a></p>
    </div>
    <div class="demo-card reveal" data-testid="demo-page-form-card">{site.demo_form("demo-page", "demo_page")}</div>
  </div>
</section>"""
    return site.page(d["title"], d["desc"], d["path"], body, [ORG_LD], "demo")


def why(site):
    d = c.WHY
    ov, h2, txt = d["story"]
    dov, dh2, dtxt, dbul, dscr = d["different"]
    body = [b.page_hero(site, "why", d["overline"], esc(d["h1"]), d["sub"], d["screen"], c.S[d["screen"]], ("See How It Works", "/#how-it-works")),
            f'<section class="section story" data-testid="why-story"><div class="wrap story-grid"><div>{b.section_head(ov, h2)}</div><p class="story-text reveal">{esc(txt)}</p></div></section>',
            b.points("why", "What we believe", "Four ideas behind everything we build.", d["principles"]),
            b.split(site, "why", 1, dov, dh2, dtxt, dbul, dscr, c.S[dscr]), b.cta_band("why")]
    return site.page(d["title"], d["desc"], d["path"], "\n".join(body), [ORG_LD], "why")


def help_page(site):
    d = c.RESOURCE_PAGES["help"]
    cards = "".join(f"""<article class="tile help-card reveal" style="--d:{i * 80}ms" data-testid="help-card-{i + 1}"><span class="tile-ico">{icon(ic, 22)}</span><h3>{esc(t)}</h3><p>{esc(x)}</p>
      <a class="text-link" href="{site.u(h)}" data-testid="help-card-{i + 1}-link">{esc(lbl)} {icon("arrow", 16)}</a></article>""" for i, (ic, t, x, lbl, h) in enumerate(d["cards"]))
    body = [b.page_hero(site, "help", d["overline"], esc(d["h1"]), d["sub"]),
            f'<section class="section help-sec" data-testid="help-cards"><div class="wrap"><div class="tiles tiles-3">{cards}</div></div></section>',
            b.faq("help", d["faq"], "Common questions"), b.cta_band("help", "Still have a question?", "Our team is happy to walk you through it on a short call.")]
    return site.page(d["title"], d["desc"], d["path"], "\n".join(body), [ORG_LD] + _faq_ld(d["faq"]), "help")


def training(site):
    d = c.RESOURCE_PAGES["training"]
    tracks = "".join(f'<article class="track reveal" style="--d:{i * 80}ms" data-testid="training-track-{i + 1}"><span class="step-num">0{i + 1}</span><h3>{esc(t)}</h3><p>{esc(x)}</p></article>'
                     for i, (t, x) in enumerate(d["tracks"]))
    body = [b.page_hero(site, "training", d["overline"], esc(d["h1"]), d["sub"], d["screen"], c.S[d["screen"]], ("Get help", "/help/")),
            f'<section class="section" data-testid="training-tracks"><div class="wrap">{b.section_head("In the Training Hub", "Tracks for reps and for managers.")}<div class="tracks">{tracks}</div></div></section>',
            b.points("training", "How it works", "Training that fits into a busy day.", d["points"]), b.cta_band("training")]
    return site.page(d["title"], d["desc"], d["path"], "\n".join(body), [ORG_LD], "training")


def legal_page(site, key, inner, title, desc, path):
    inner = re.sub(r'href="/(terms|privacy|sms-terms)"', lambda x: f'href="{site.u("/" + x.group(1) + "/")}"', inner)
    body = f'<section class="section legal" data-testid="{key}-legal"><div class="wrap legal-wrap">{inner}</div></section>'
    return site.page(title, desc, path, body, [ORG_LD], key)


DEV_JS = """<script>
(function(){
  var tabs=[].slice.call(document.querySelectorAll('.dev-tab')),docs=[].slice.call(document.querySelectorAll('.doc'));
  function show(slug,push){
    if(!docs.some(function(d){return d.dataset.slug===slug}))slug=docs[0].dataset.slug;
    docs.forEach(function(d){d.hidden=d.dataset.slug!==slug});
    tabs.forEach(function(t){var on=t.dataset.slug===slug;t.classList.toggle('on',on);t.setAttribute('aria-current',on?'page':'false')});
    if(push){history.pushState(null,'','?doc='+slug+location.hash)}
  }
  function fromUrl(){
    var q=new URLSearchParams(location.search).get('doc'),h=location.hash.slice(1);
    if(!q&&h&&h.indexOf('--')>0)q=h.split('--')[0];
    show(q||docs[0].dataset.slug,false);
    if(h){var el=document.getElementById(h);if(el)setTimeout(function(){el.scrollIntoView()},0)}
  }
  tabs.forEach(function(t){t.addEventListener('click',function(e){e.preventDefault();show(t.dataset.slug,true);document.getElementById('docs').scrollIntoView({behavior:'smooth'})})});
  document.getElementById('docs').addEventListener('click',function(e){
    var a=e.target.closest('a');if(!a)return;
    var m=(a.getAttribute('href')||'').match(/^(?:https?:\\/\\/(?:www\\.)?imonsocial\\.com)?\\/developers\\/?\\?doc=([a-z0-9-]+)(#.*)?$/);
    if(m){e.preventDefault();show(m[1],true);if(m[2]){location.hash=m[2]}else{document.getElementById('docs').scrollIntoView()}}
  });
  addEventListener('popstate',fromUrl);fromUrl();
})();
</script>"""
DEV_ICONS = {"api-reference": "code", "crm-integration-guide": "send", "automotive-crm-programs": "car"}


def developers(site):
    quick = [("play", "Try it live", "Interactive console. Paste your key under <strong>Authorize</strong> and run real calls against your store.", "Open API console",
              "https://app.imonsocial.com/api/public/reference", "dev-console-btn"),
             ("code", "OpenAPI 3 schema", "Import into Postman or Insomnia, or generate a client in any language.", "openapi-v1.json",
              "https://app.imonsocial.com/api/public/openapi-v1.json", "dev-openapi-btn"),
             ("key", "Get an API key", "A dealership admin creates one in the app: <strong>Tools, Integrations, API Keys</strong>. One key = one store; ask for an organization key for a group.",
              "Sign in to the app", "https://app.imonsocial.com", "dev-key-btn")]
    cards = "".join(f'''<a class="tile dev-quick reveal" style="--d:{i * 80}ms" href="{h}" target="_blank" rel="noopener" data-testid="{tid}"><span class="tile-ico">{icon(ic, 22)}</span>
      <h3>{esc(t)}</h3><p>{txt}</p><span class="text-link">{esc(lbl)} {icon("arrow", 16)}</span></a>''' for i, (ic, t, txt, lbl, h, tid) in enumerate(quick))
    tabs = "".join(f'''<a class="dev-tab" href="?doc={d["slug"]}" data-slug="{d["slug"]}" data-testid="dev-tab-{d["slug"]}">{icon(DEV_ICONS[d["slug"]], 18)}
      <span><strong>{esc(d["title"])}</strong><em>{esc(d["sub"])}</em></span></a>''' for d in devdocs.DOCS)
    docs = "".join(re.sub(r'<i class="fa-[^"]*"></i>\s*', "", devdocs.render_doc(d)) for d in devdocs.DOCS)
    body = f"""<section class="page-hero solo dev-hero" data-testid="developers-hero"><div class="wrap">
  <p class="overline reveal">Developers</p><h1 class="reveal" data-testid="developers-h1">Build on i'M On Social.</h1>
  <p class="lead reveal">An open REST API and signed webhooks for every customer, text, call, note, task and sold record in a store. Connect your CRM, DMS, marketing stack or automation tool. No partnership paperwork: a dealership admin hands you a key and you are live.</p>
  <div class="tiles tiles-3 dev-quicks">{cards}</div>
</div></section>
<section class="section dev-docs" data-testid="developers-docs"><div class="wrap dev-grid">
  <aside class="dev-side"><p class="dev-side-t">Documentation</p>{tabs}
    <div class="dev-help"><strong>Need a sandbox store, an organization key, or an engineer on a call?</strong> Email <a href="mailto:support@imonsocial.com">support@imonsocial.com</a> with your company, the system you are connecting and the dealership you are integrating for.</div>
  </aside>
  <div id="docs" class="dev-main">{docs}</div>
</div></section>"""
    return site.page("Developers & API | i'M On Social",
                     "Open REST API and signed webhooks for every customer, text, call, note, task and sold record. CRM integration guide and the automotive CRM certification checklist.",
                     "/developers/", body, [ORG_LD], "developers", DEV_JS)


LEGAL = {"privacy": ("Privacy Policy | i'M On Social", "How i'M On Social collects, uses and protects your information."),
         "terms": ("Terms of Service | i'M On Social", "The terms that govern your use of i'M On Social."),
         "sms-terms": ("SMS Messaging Policy | i'M On Social", "How SMS messaging works on i'M On Social, including how to opt in, opt out and get help.")}


def all_pages(legal_dir: Path):
    """path (relative file) -> renderer(site). Legal text is a verbatim snapshot in site/legal/ so the wording never changes here."""
    pages = {"index.html": home.render, "features/index.html": features_hub, "industries/index.html": industries_hub, "pricing/index.html": pricing,
             "demo/index.html": demo, "why-imonsocial/index.html": why, "help/index.html": help_page, "training/index.html": training,
             "developers/index.html": developers}
    for k, d in c.FEATURE_PAGES.items():
        pages[d["path"].strip("/") + "/index.html"] = lambda s, k=k, d=d: feature_page(s, k, d)
    for k, d in c.AUDIENCE_PAGES.items():
        pages[d["path"].strip("/") + "/index.html"] = lambda s, k=k, d=d: audience_page(s, k, d)
    for k, d in c.INDUSTRY_PAGES.items():
        pages[d["path"].strip("/") + "/index.html"] = lambda s, k=k, d=d: industry_page(s, k, d)
    for k, (t, desc) in LEGAL.items():
        inner = (legal_dir / f"{k}.html").read_text(encoding="utf-8")
        pages[f"{k}/index.html"] = lambda s, k=k, t=t, desc=desc, inner=inner: legal_page(s, k, inner, t, desc, f"/{k}/")
    return pages
