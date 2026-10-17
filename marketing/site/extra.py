"""Standalone noindex pages in the new site design: /feature-sheet and /mybaby (platform overview).

  python marketing/site/extra.py    writes marketing/build (live on Save to GitHub), marketing/build-preview and marketing/public/mybaby.html.
Not part of build.py, so they stay out of the sitemap and are never indexed."""
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import blocks as b  # noqa: E402
from build import BUILD, PREVIEW, PREVIEW_BASE, version  # noqa: E402
from extra_css import FS_CSS, OV_CSS  # noqa: E402
from layout import Site, esc, icon, slug  # noqa: E402
from build_feature_sheet import SECTIONS  # noqa: E402

AUD = {"Rep": "#C9A962", "Manager": "#3B6E8F", "Owner": "#6B5BA8", "Customer-facing": "#3E8E5E"}


def finish(html, css):
    html = html.replace('<meta name="robots" content="index, follow"/>', '<meta name="robots" content="noindex, nofollow"/>')
    return html.replace("</head>", f"<style>{css}</style>\n</head>", 1)


# ---------- Feature sheet ----------

def chips(auds):
    return "".join(f'<span class="fs-aud" style="--c:{AUD[a]}">{esc(a)}</span>' for a in auds)


def fs_hero(total):
    legend = "".join(f'<span class="fs-aud" style="--c:{c}">{esc(a)}</span>' for a, c in AUD.items())
    return f"""<section class="page-hero fs-hero" data-testid="feature-sheet-hero"><div class="wrap">
  <p class="overline reveal">Feature sheet · internal review copy</p>
  <h1 class="reveal" data-testid="feature-sheet-h1">Everything in i'M On Social, on one sheet.</h1>
  <p class="lead reveal">{total} features grouped by what they are for, each with a plain description and the reason it exists. Not everyone will use everything; the point is that every rep, manager and owner finds the handful that changes their week.</p>
  <div class="fs-meta reveal">
    <span class="fs-pill" data-testid="feature-sheet-total">{total} features</span><span class="fs-pill">{len(SECTIONS)} areas</span><span class="fs-pill gold">Internal review copy</span>
    <div class="fs-legend">Who it is for: {legend}
      <button class="btn btn-outline btn-sm fs-print" type="button" onclick="window.print()" data-testid="feature-sheet-print-button">Print / save PDF</button></div>
  </div>
</div></section>"""


def fs_why():
    return """<section class="fs-why-sec"><div class="wrap"><div class="fs-why reveal" data-testid="feature-sheet-why">
  <div>
    <p class="overline">Why "i'M On Social"?</p>
    <h2>Because relationships don't run <em>from 9 to 5.</em></h2>
    <p><strong>i'M On</strong> means always on: remembering, listening, following up, and staying connected. <strong>Social</strong> means the human relationships that drive business, not social media.</p>
    <p>i'M On Social uses AI to create 24/7 social engagement, helping you remember every relationship, know when to reach out, and stay connected long after the first conversation or sale. Every feature on this sheet is one more way the system stays on so the salesperson can stay human.</p>
  </div>
  <div class="fs-pitch"><strong>i'M ON SOCIAL</strong><p>You make the connection.<br/>We help keep it alive.</p><span>The one-line positioning</span></div>
</div></div></section>"""


def fs_row(n, name, what, why, auds):
    return f"""<div class="fs-row" data-testid="feature-row-{n}">
      <div class="fs-name"><span class="fs-num">{n:02d}</span><h3>{esc(name)}</h3><div class="fs-auds">{chips(auds)}</div></div>
      <div><span class="fs-lbl">What it does</span>{esc(what)}</div>
      <div class="fs-whyc"><span class="fs-lbl">Why it matters</span>{esc(why)}</div>
    </div>"""


def fs_groups():
    out, n = [], 0
    for s in SECTIONS:
        rows = []
        for name, what, why, auds in s["features"]:
            n += 1
            rows.append(fs_row(n, name, what, why, auds))
        out.append(f"""<section class="fs-grp" id="{s['id']}" data-testid="feature-group-{s['id']}">
    <div class="fs-grp-head"><p class="overline">{esc(s['tag'])} · {len(s['features'])} features</p><h2>{esc(s['title'])}</h2><p class="muted">{esc(s['intro'])}</p></div>
    <div class="fs-rows"><div class="fs-row fs-hdr"><div>Feature</div><div>What it does</div><div>Why it matters</div></div>{''.join(rows)}</div>
  </section>""")
    return "".join(out)


def feature_sheet(site):
    total = sum(len(s["features"]) for s in SECTIONS)
    toc = "".join(f'<a href="#{s["id"]}" data-testid="feature-toc-{s["id"]}">{esc(s["title"])}<em>{len(s["features"])}</em></a>' for s in SECTIONS)
    body = [fs_hero(total), fs_why(),
            f'<section class="section fs-body"><div class="wrap fs-grid"><aside class="fs-toc" data-testid="feature-sheet-toc"><p class="fs-toc-t">Jump to</p>{toc}</aside>'
            f'<div class="fs-main">{fs_groups()}</div></div></section>',
            b.cta_band("feature_sheet")]
    html = site.page("Feature Sheet - i'M On Social", "Internal review sheet: every feature of i'M On Social with what it does and why it matters.",
                     "/feature-sheet/", "\n".join(body), [], "feature_sheet")
    return finish(html, FS_CSS)


# ---------- Platform overview (/mybaby) ----------

LAYERS = [
    ('<path d="M12 3a4 4 0 0 0-4 4v1a4 4 0 0 0-3 3.9A4 4 0 0 0 7 19h1"/><path d="M12 3a4 4 0 0 1 4 4v1a4 4 0 0 1 3 3.9A4 4 0 0 1 17 19h-1"/><path d="M12 3v18"/>',
     "Relationship intelligence", "Persistent customer memory that turns conversations, activities, preferences, milestones and engagement history into a continuously evolving relationship profile."),
    ('<path d="M4 5h16v11H8l-4 4z"/><path d="M8 9h8M8 12h5"/>', "AI communication",
     "Real-time conversational voice, intelligent texting, email, transcription, voice generation and automated customer interaction."),
    ('<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M4.9 19.1 7 17M17 7l2.1-2.1"/>', "Automation engine",
     "Long-term campaigns, event-driven workflows, scheduled engagement, follow-up automation and salesperson task generation."),
    ('<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/>', "Sales execution",
     "Lead response, customer engagement, landing pages, digital experiences, reviews, referrals, communication tools and actionable next steps."),
    ('<path d="M2 9l10-5 10 5-10 5z"/><path d="M6 11v5c0 1.5 3 3 6 3s6-1.5 6-3v-5"/><path d="M22 9v6"/>', "Training & coaching",
     "AI practice calls, role-play scenarios, scoring, scripts, coaching, progress tracking and certification."),
    ('<path d="M3 21h18M5 21V7l7-4 7 4v14"/><path d="M9 21v-5h6v5M9 10h2M13 10h2M9 14h2M13 14h2"/>', "Enterprise infrastructure",
     "Multi-user organizations, permissions, multi-location deployments, billing, partner programs, integrations, reporting and APIs."),
]
METRICS = [("335", "K+", "Lines of application code"), ("1774", "", "API endpoints"), ("379", "", "Application screens"),
           ("57", "", "Automated background jobs"), ("14", "", "Live external integrations")]
COST = [("12–15", "Engineers", "Recreating the current platform would require a multidisciplinary team spanning backend, mobile, web, AI/voice, telephony, DevOps, QA and product."),
        ("18–24 mo", "To feature parity", "Estimated development time for a dedicated team to rebuild the current platform and reach the same depth."),
        ("$5M–$8M", "Estimated equivalent build cost", "Fully loaded US engineering cost to recreate ≈335K lines of production code plus the integration and compliance work around it."),
        ("Live now", "Execution lead", "While that team would be hiring and architecting, i'M On Social is already deployed, processing real conversations for real sales teams.")]
COMPLEX = [("Real-time voice bridge", " between carrier media streams and a live AI model, with interruptions, watchdogs and fallbacks."),
           ("Multi-tenant telephony", " with per-organization numbers, sub-accounts and carrier (10DLC) compliance."),
           ("14 live integrations", " across telephony, email, payments, AI, push, storage, identity and mapping."),
           ("57 scheduled jobs", " running campaigns, follow-ups, digests, lifecycle events and health checks around the clock."),
           ("One living profile per customer", ", continuously updated from every channel and every interaction."),
           ("Three surfaces", ": native iOS app, web app and a one-line embeddable website widget.")]
GTM = [("Dealers first", "Automotive and powersports dealerships, where the pain is sharpest: hundreds of past customers every salesperson has simply forgotten."),
       ("Land and expand", "One rep becomes the store, the store becomes the group. Team leaderboards, manager views and the referral engine already drive this inside the product."),
       ("Partners and white-label", "Partner, reseller and white-label programs are wired in, so industry channels can carry i'M On Social under their own brand."),
       ("Plug into existing workflows", "Two-way sync with the CRMs and DMS platforms dealers already run, so i'M On Social slots in on day one instead of replacing anything."),
       ("Adjacent industries", "Real estate, insurance, home services, medical and fitness: relationship-driven businesses the platform already supports with their own playbooks.")]
ASK = [("Sales & distribution", "A direct sales motion for dealer groups and multi-location operators, plus the partner and reseller channels already wired into the product."),
       ("Strategic integrations", "Two-way sync with the CRMs and DMS platforms the market already runs, so i'M On Social becomes the relationship layer on top of existing systems."),
       ("Enterprise deployment", "Onboarding, support, controls and reporting for groups rolling i'M On Social out across hundreds of reps at once."),
       ("Product expansion", "Deeper AI across voice, texting and coaching, and the adjacent industries the platform already supports.")]


def svg(paths, size=22):
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" '
            f'stroke-linejoin="round" aria-hidden="true">{paths}</svg>')


def lead_btn(where, cls="btn-gold"):
    return f'<button class="btn {cls} btn-lg" type="button" data-ov-lead data-testid="overview-{where}-start-conversation">Start a conversation</button>'


def ov_hero():
    return f"""<section class="page-hero ov-hero" id="cover" data-testid="overview-hero"><div class="wrap ov-hero-grid">
  <div>
    <p class="overline reveal">My Platform Overview · 2026</p>
    <h1 class="reveal" data-testid="overview-h1">The AI Relationship Operating System.</h1>
    <p class="lead reveal">Salespeople don't lose relationships because they don't care. They lose them because no human can remember hundreds of customers, every conversation, every milestone and exactly when to reconnect. <b>We built the system that can.</b></p>
    <div class="cta-row reveal">{lead_btn("hero")}<a class="btn btn-outline btn-lg" href="#built" data-testid="overview-hero-numbers">See the numbers</a></div>
  </div>
  <aside class="ov-glance reveal" data-testid="overview-at-a-glance">
    <p class="overline">At a glance</p>
    <ul>{''.join(f'<li><b>{f"{int(n):,}" if n.isdigit() and not s else n + s}</b>{esc(l)}</li>' for n, s, l in METRICS)}<li><b>3</b>Surfaces: iOS, web and an embeddable website widget</li></ul>
    <p class="ov-tag">Already built. Already live. Already in use.</p>
  </aside>
</div></section>"""


def ov_engine():
    nodes = "".join(f'<div class="ov-node" style="--a:{i * 72}deg"><i>0{i + 1}</i>{t}</div>' for i, t in enumerate(("Communicate", "Understand", "Remember", "Automate", "Act")))
    chain = '<em>→</em>'.join(f"<span>{t}</span>" for t in ("Who needs attention", "Why", "What should happen next", "When", "How to execute it"))
    return f"""<section class="section" id="engine" data-testid="overview-engine"><div class="wrap ov-engine">
  <div>
    <p class="overline reveal">What it actually does</p>
    <h2 class="reveal">A CRM stores what happened. i'M On Social understands what changed.</h2>
    <p class="lead reveal">Something happens. The relationship changes. The system understands the change, and the next action changes with it. Every conversation, call and customer signal strengthens the record, so the platform can determine:</p>
    <div class="ov-chain reveal" aria-label="Decision chain">{chain}</div>
    <p class="ov-fly reveal">Every interaction makes the next interaction smarter.</p>
  </div>
  <div class="ov-ring reveal" aria-label="Relationship Intelligence Engine with five connected systems" data-testid="overview-ring">
    <div class="ov-loop"></div><div class="ov-hub"><div><b>Relationship Intelligence Engine</b><small>the system of record</small></div></div>{nodes}
  </div>
</div></section>"""


def ov_layers():
    tiles = "".join(f'<article class="tile reveal" style="--d:{i * 70}ms" data-testid="overview-layer-{slug(t)}"><span class="tile-ico">{svg(p)}</span><h3>{esc(t)}</h3><p>{esc(d)}</p></article>'
                    for i, (p, t, d) in enumerate(LAYERS))
    return f"""<section class="section value" id="layers" data-testid="overview-layers"><div class="wrap">
  <div class="section-head"><p class="overline reveal">One platform. One shared context.</p><h2 class="reveal">Six systems most companies buy from six vendors. One relationship layer connecting all of them.</h2>
  <p class="reveal muted">The texting system knows what the relationship engine knows. So does voice. So does automation, training and tasks. <b>Not six features under one login: six systems sharing one memory.</b></p></div>
  <div class="tiles tiles-3">{tiles}</div>
</div></section>"""


def ov_built():
    cards = "".join(f'<div class="ov-metric reveal" style="--d:{i * 70}ms"><div class="ov-n" data-count="{n}" data-suffix="{s}">0</div><div class="ov-l">{esc(l)}</div></div>'
                    for i, (n, s, l) in enumerate(METRICS))
    return f"""<section class="band band-ink" id="built" data-testid="overview-built"><div class="wrap">
  <p class="overline reveal">Built, not just conceptualized</p>
  <h2 class="reveal">Production-grade, already built at significant scale.</h2>
  <div class="ov-metrics" data-testid="overview-metrics">{cards}</div>
  <p class="ov-foot reveal">Measured from the production repository, October 2026. Backend plus mobile/web app, excluding tests. Tests, build tooling and documentation add another 120K+ lines.</p>
  <p class="ov-foot ov-appendix">Technical appendix: 375 reusable UI components · 213 data collections · native iOS app, web app and a one-line embeddable website widget · multi-tenant telephony with carrier (10DLC) compliance.</p>
</div></section>"""


def ov_replace():
    cost = "".join(f'<div class="ov-cost reveal" style="--d:{i * 70}ms"><div class="ov-v">{esc(v)}</div><p class="ov-t">{esc(t)}</p><p>{esc(d)}</p></div>' for i, (v, t, d) in enumerate(COST))
    cx = "".join(f'<li>{icon("check", 18)}<span><b>{esc(h)}</b>{esc(t)}</span></li>' for h, t in COMPLEX)
    return f"""<section class="section" id="replace" data-testid="overview-replace"><div class="wrap">
  <div class="section-head"><p class="overline reveal">What would it take to build this today?</p><h2 class="reveal">The technical execution risk has already been absorbed.</h2></div>
  <div class="ov-costs">{cost}</div>
  <ul class="checks ov-complex reveal">{cx}</ul>
  <div class="ov-versus reveal" data-testid="overview-versus">
    <div class="ov-side"><p class="ov-t">Build from scratch</p><span>12–15 people · 18–24 months · $5M–$8M</span></div><div class="ov-vs">VS</div>
    <div class="ov-side live"><p class="ov-t">i'M On Social today</p><span>Built, deployed, in use</span></div>
  </div>
  <p class="ov-note reveal">Estimates use industry productivity benchmarks of 12–18K production lines per engineer-year and fully loaded US cost of $200–250K per engineer-year, plus product, design, QA and infrastructure overhead. Formal models (COCOMO II) produce higher figures.</p>
</div></section>"""


def ov_founder():
    stats = "".join(f"<div><b>{v}</b>{t}</div>" for v, t in (("30", "years selling, not studying sales"), ("1", "problem lived every single day"), ("335K+", "lines of code written to end it")))
    return f"""<section class="section value" id="founder" data-testid="overview-founder"><div class="wrap story-grid">
  <div><p class="overline reveal">Founder-market fit</p><h2 class="reveal">Thirty years on the sales floor. One tool built for the people on it.</h2></div>
  <div><p class="story-text reveal">Most sales systems are built around managing the pipeline. This one is built around helping the salesperson manage the relationship. i'M On Social wasn't designed by a software team that discovered automotive sales in a market report. It was built by a high-tech redneck who spent three decades carrying a quota, then built the tool he always needed, for the lifeblood of every company: <b>the salesperson.</b></p>
  <div class="ov-bar reveal">{stats}</div></div>
</div></section>"""


def uses(items, key):
    return "".join(f'<article class="track ov-use reveal" style="--d:{i * 70}ms" data-testid="overview-{key}-{slug(t)}"><span class="ov-idx">0{i + 1}</span><h3>{esc(t)}</h3><p>{esc(d)}</p></article>'
                   for i, (t, d) in enumerate(items))


def ov_gtm():
    return f"""<section class="section" id="gtm" data-testid="overview-gtm"><div class="wrap">
  <div class="section-head"><p class="overline reveal">Where we are now</p><h2 class="reveal">The product is built. The infrastructure is live. Now it goes to market.</h2>
  <p class="reveal muted">The focus shifts from building to distribution. <b>Here is the plan:</b></p></div>
  <div class="ov-uses">{uses(GTM, "gtm")}</div>
  <p class="ov-risk reveal"><i></i>Built. Live. In use. The next chapter is distribution.</p>
</div></section>"""


def ctas(site, where):
    return (f'<div class="cta-row ov-ctas reveal">{lead_btn(where)}'
            f'<a class="btn btn-lg ov-btn-light" href="{site.u("/")}" data-testid="overview-{where}-see-product">See the product</a>'
            f'<a class="btn btn-lg ov-btn-light" href="https://app.imonsocial.com" data-testid="overview-{where}-open-app">Open the live app</a></div>')


def ov_close(site):
    return f"""<section class="band band-ink final ov-close" id="close" data-mode="general" data-testid="overview-close"><div class="wrap final-inner">
  <h2 class="reveal">Remember everyone. Understand every relationship. <span class="ov-gold">Never miss what should happen next.</span></h2>
  <p class="reveal">From contact → relationship intelligence → action. One platform, already running.</p>
  {ctas(site, "close")}
</div></section>
<section class="band band-ink ov-ask" id="ask" data-mode="investor" data-testid="overview-ask"><div class="wrap">
  <p class="overline reveal">Now we scale it</p>
  <h2 class="reveal">We aren't raising capital to find out whether this can be built. <span class="ov-gold">We're raising capital to determine how fast it can be distributed.</span></h2>
  <p class="ov-ask-lead reveal">The product is built. The infrastructure is live. The market has been identified. <b>The next investment is distribution.</b></p>
  <div class="ov-uses four">{uses(ASK, "ask")}</div>
  <p class="ov-quote reveal">I've built the machine. <span>Now I'm looking for the right capital and partners to put fuel in it.</span></p>
  {ctas(site, "ask")}
</div></section>"""


def ov_modal():
    def f(name, label, typ="text", req=False, auto=""):
        star = ' <span aria-hidden="true">*</span>' if req else ' <em>(optional)</em>'
        return (f'<div class="field"><label for="ov-{name}">{label}{star}</label><input id="ov-{name}" name="{name}" type="{typ}"{" required" if req else ""}'
                f' autocomplete="{auto}" data-testid="overview-lead-{name}-input"/></div>')
    return f"""<div class="modal" id="ov-lead-modal" role="dialog" aria-modal="true" aria-labelledby="ov-lead-title" aria-hidden="true" data-testid="overview-lead-modal">
  <div class="modal-card">
    <button class="modal-close" type="button" aria-label="Close" data-modal-close data-testid="overview-lead-close">{icon("x", 22)}</button>
    <form id="ov-lead-form" novalidate data-testid="overview-lead-form">
      <p class="overline">Let's talk</p><h2 id="ov-lead-title">Start a conversation.</h2>
      <p class="modal-sub">Leave your details and Forest will reach out personally.</p>
      <div class="row2">{f("name", "Name", req=True, auto="name")}{f("company", "Company", auto="organization")}</div>
      <div class="row2">{f("email", "Email", "email", True, "email")}{f("phone", "Phone", "tel", auto="tel")}</div>
      <div class="field"><label for="ov-message">What would you like to discuss? <em>(optional)</em></label><textarea id="ov-message" name="message" rows="4" data-testid="overview-lead-message-input"></textarea></div>
      <p class="form-error" role="alert" hidden data-testid="overview-lead-error"></p>
      <button class="btn btn-gold btn-block" type="submit" data-testid="overview-lead-submit">Send</button>
      <p class="legal-line ov-fine">Your details go straight to Forest. No lists, no spam.</p>
    </form>
    <div class="form-success" hidden data-testid="overview-lead-success"><div class="success-ico">{icon("check", 28)}</div><h2>Got it.</h2>
      <p>Thanks for reaching out. Forest will be in touch shortly.</p><button class="btn btn-ink" type="button" data-modal-close data-testid="overview-lead-done">Done</button></div>
  </div>
</div>"""


OV_JS = """<script>
(function () {
  var INVESTOR = new URLSearchParams(location.search).get('investor') === '1';
  document.querySelectorAll('[data-mode]').forEach(function (s) { if (s.getAttribute('data-mode') !== (INVESTOR ? 'investor' : 'general')) s.remove(); });
  var API = document.documentElement.getAttribute('data-api') || '';
  var m = document.getElementById('ov-lead-modal'), form = document.getElementById('ov-lead-form'), ok = m.querySelector('.form-success'), err = form.querySelector('.form-error');
  var open = function () { form.hidden = false; ok.hidden = true; err.hidden = true; m.classList.add('open'); m.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden'; document.body.classList.add('overlay-open'); setTimeout(function () { document.getElementById('ov-name').focus(); }, 60); };
  var close = function () { m.classList.remove('open'); m.setAttribute('aria-hidden', 'true'); document.body.style.overflow = ''; document.body.classList.remove('overlay-open'); };
  document.querySelectorAll('[data-ov-lead]').forEach(function (b) { b.addEventListener('click', open); });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && m.classList.contains('open')) close(); });
  form.addEventListener('submit', function (e) {
    e.preventDefault();
    var v = function (n) { return form.elements[n].value.trim(); }, btn = form.querySelector('button[type="submit"]');
    if (!v('name') || !/^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$/.test(v('email'))) { err.textContent = 'Please enter your name and a valid email.'; err.hidden = false; return; }
    err.hidden = true; btn.disabled = true; btn.textContent = 'Sending...';
    fetch(API + '/api/demo-requests', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name: v('name'), email: v('email'), phone: v('phone'),
      company: v('company'), message: v('message'), source: INVESTOR ? 'platform_overview_investor_cta' : 'platform_overview_cta', referrer: document.referrer, page: location.pathname }) })
      .then(function (r) { return r.json().catch(function () { return {}; }).then(function (j) { if (!r.ok || j.status === 'error') throw new Error('failed'); }); })
      .then(function () { form.hidden = true; ok.hidden = false; form.reset(); })
      .catch(function () { err.textContent = "Couldn't reach the server. Please try again, or email forest@imonsocial.com."; err.hidden = false; })
      .then(function () { btn.disabled = false; btn.textContent = 'Send'; });
  });
  var fmt = function (el, x) { el.textContent = Math.round(x).toLocaleString('en-US') + (el.getAttribute('data-suffix') || ''); };
  var count = function (el) { if (el.dataset.done) return; el.dataset.done = '1'; var end = +el.getAttribute('data-count'), t0 = performance.now();
    var tick = function (now) { var p = Math.min(1, (now - t0) / 1400); fmt(el, end * (1 - Math.pow(1 - p, 3))); if (p < 1) requestAnimationFrame(tick); }; requestAnimationFrame(tick); };
  var nums = document.querySelectorAll('[data-count]');
  if ('IntersectionObserver' in window) { var io = new IntersectionObserver(function (es) { es.forEach(function (e) { if (e.isIntersecting) { count(e.target); io.unobserve(e.target); } }); }, { threshold: .4 });
    nums.forEach(function (n) { io.observe(n); }); } else nums.forEach(function (n) { fmt(n, +n.getAttribute('data-count')); });
  window.addEventListener('beforeprint', function () { nums.forEach(function (n) { n.dataset.done = '1'; fmt(n, +n.getAttribute('data-count')); }); });
})();
</script>"""


def overview(site):
    body = [ov_hero(), ov_engine(), ov_layers(), ov_built(), ov_replace(), ov_founder(), ov_gtm(), ov_close(site), ov_modal()]
    html = site.page("i'M On Social: My Platform Overview",
                     "i'M On Social: a production-grade AI Relationship Operating System already built at significant scale. 335K+ lines of application code, 1,774 API endpoints, 14 live integrations.",
                     "/mybaby", "\n".join(body), [], "platform_overview", OV_JS)
    return finish(html, OV_CSS)


def main():
    for target, site in ((BUILD, Site("", "https://app.imonsocial.com", version(), preview=False)), (PREVIEW, Site(PREVIEW_BASE, "", version(), preview=True))):
        (target / "feature-sheet").mkdir(parents=True, exist_ok=True)
        (target / "feature-sheet" / "index.html").write_text(feature_sheet(site), encoding="utf-8")
        (target / "mybaby.html").write_text(overview(site), encoding="utf-8")
    shutil.copy(BUILD / "mybaby.html", HERE.parent / "public" / "mybaby.html")
    print("wrote feature-sheet + mybaby into build, build-preview and public/mybaby.html")


if __name__ == "__main__":
    main()
