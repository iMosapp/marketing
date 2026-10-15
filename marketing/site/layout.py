"""Shared chrome for the new marketing site: head, nav, footer, demo/contact modals, video lightbox."""
import html
import json

ICONS = {
    "chev": '<path d="m6 9 6 6 6-6"/>',
    "arrow": '<path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>',
    "play": '<polygon points="7 4 20 12 7 20 7 4"/>',
    "menu": '<line x1="4" x2="20" y1="7" y2="7"/><line x1="4" x2="20" y1="12" y2="12"/><line x1="4" x2="20" y1="17" y2="17"/>',
    "x": '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
    "check": '<path d="M20 6 9 17l-5-5"/>',
    "heart": '<path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z"/>',
    "calendar": '<path d="M8 2v4"/><path d="M16 2v4"/><rect width="18" height="18" x="3" y="4" rx="2"/><path d="M3 10h18"/><path d="m9 16 2 2 4-4"/>',
    "shield": '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="m9 12 2 2 4-4"/>',
    "trend": '<polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/>',
    "mic": '<path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" x2="12" y1="19" y2="22"/>',
    "spark": '<path d="M9.94 15.5A2 2 0 0 0 8.5 14.06l-6.14-1.58a.5.5 0 0 1 0-.96L8.5 9.94A2 2 0 0 0 9.94 8.5l1.58-6.14a.5.5 0 0 1 .96 0L14.06 8.5A2 2 0 0 0 15.5 9.94l6.14 1.58a.5.5 0 0 1 0 .96L15.5 14.06a2 2 0 0 0-1.44 1.44l-1.58 6.14a.5.5 0 0 1-.96 0z"/>',
    "send": '<path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/>',
}


def icon(name, size=20, cls="ico"):
    return (f'<svg class="{cls}" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
            f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{ICONS[name]}</svg>')


def esc(s):
    return html.escape(s, quote=True)


FEATURES = [
    ("Capture & remember", [("Voice memos & Jessi AI", "/jessi/", "Talk it out, Jessi writes it down"), ("Digital card & QR", "/digital-card/", "A card people keep and share"),
                            ("Link page & showcase", "/showcase/", "Your work, reviews and links in one place")]),
    ("Stay connected", [("Campaigns & date triggers", "/date-triggers/", "Birthdays, anniversaries, check-ins"), ("Inbox & texting", "/inbox/", "Every text and email with a customer in one thread"),
                        ("Congrats cards", "/congrats-template/", "Celebrate every purchase")]),
    ("Grow & manage", [("Reviews", "/reviews/", "Ask for a review in one tap"), ("Leaderboards", "/leaderboard/", "Friendly competition for teams"),
                       ("SEO & visibility", "/seo/", "Pages built to be found")]),
]
SOLUTIONS = [("For businesses", "/organizations/"), ("For sales professionals", "/individuals/"), ("Automotive & equipment", "/dealers/"), ("Real estate", "/real-estate/"),
             ("Insurance & financial", "/insurance/"), ("Home services", "/home-services/"), ("Powersports", "/powersports/")]
RESOURCES = [("Help Center", "/help/"), ("Training", "/training/"), ("Why i'M On Social", "/why-imonsocial/"), ("Developers & API", "/developers/"),
             ("Get the iPhone app", "https://app.imonsocial.com/api/get/site")]
SIGN_IN = "https://app.imonsocial.com"
FOOTER = [
    ("Product", [("How it works", "/#how-it-works"), ("All features", "/features/"), ("Jessi AI", "/jessi/"), ("Inbox & texting", "/inbox/"), ("Campaigns", "/date-triggers/"), ("Pricing", "/pricing/")]),
    ("Solutions", [("For businesses", "/organizations/"), ("For sales professionals", "/individuals/"), ("Automotive & equipment", "/dealers/"), ("Real estate", "/real-estate/"),
                   ("Insurance & financial", "/insurance/"), ("Home services", "/home-services/")]),
    ("Resources", [("Help Center", "/help/"), ("Training", "/training/"), ("Developers & API", "/developers/"), ("Why i'M On Social", "/why-imonsocial/"),
                   ("Get the iPhone app", "https://app.imonsocial.com/api/get/site")]),
    ("Company", [("Book a demo", "#demo"), ("Contact us", "#contact"), ("Sign in", SIGN_IN), ("Privacy", "/privacy/"), ("Terms", "/terms/"), ("SMS policy", "/sms-terms/")]),
]
INDUSTRIES = [("", "Select your industry"), ("real_estate", "Real estate"), ("insurance", "Insurance & financial services"), ("car_dealer", "Automotive & equipment"),
              ("powersports", "Powersports"), ("home_services", "Home services"), ("professional_services", "Professional services"), ("salon_wellness", "Salons, fitness & wellness"),
              ("other", "Other")]
TEAM_SIZES = ["Just me", "2-5", "6-20", "21-50", "51+"]


def slug(s):
    return "".join(c if c.isalnum() else "-" for c in s.lower()).strip("-").replace("--", "-")


class Site:
    def __init__(self, base, api, version, preview):
        self.base, self.api, self.v, self.preview = base, api, version, preview

    def u(self, path):
        if path.startswith(("http", "#", "mailto:", "tel:")):
            return path
        return self.base + path

    def a(self, path):
        return f"{self.base}/assets/{path}?v={self.v}"

    def link(self, label, path, tid, cls=""):
        ext = ' target="_blank" rel="noopener"' if path.startswith("http") and "imonsocial.com/api/get" not in path else ""
        if path == "#demo":
            return f'<a href="#demo" class="{cls}" data-demo="footer" data-testid="{tid}">{esc(label)}</a>'
        if path == "#contact":
            return f'<a href="#contact" class="{cls}" data-contact data-testid="{tid}">{esc(label)}</a>'
        return f'<a href="{self.u(path)}" class="{cls}"{ext} data-testid="{tid}">{esc(label)}</a>'

    def head(self, title, desc, path, jsonld):
        canon = "https://www.imonsocial.com" + path
        robots = '<meta name="robots" content="noindex, nofollow"/>' if self.preview else '<meta name="robots" content="index, follow"/>'
        ld = "".join(f'<script type="application/ld+json">{json.dumps(x, separators=(",", ":"))}</script>' for x in jsonld)
        return f"""<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}"/>
{robots}
<link rel="canonical" href="{canon}"/>
<meta property="og:title" content="{esc(title)}"/>
<meta property="og:description" content="{esc(desc)}"/>
<meta property="og:type" content="website"/>
<meta property="og:url" content="{canon}"/>
<meta property="og:image" content="https://www.imonsocial.com/og-image.png"/>
<meta property="og:image:width" content="1200"/>
<meta property="og:image:height" content="630"/>
<meta name="twitter:card" content="summary_large_image"/>
<meta name="twitter:image" content="https://www.imonsocial.com/og-image.png"/>
<meta name="theme-color" content="#FDFCF9"/>
<link rel="icon" href="{self.u('/favicon.png')}"/>
<link rel="preconnect" href="https://api.fontshare.com" crossorigin/>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
<link rel="stylesheet" href="https://api.fontshare.com/v2/css?f[]=cabinet-grotesk@500,700,800&display=swap"/>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap"/>
<link rel="stylesheet" href="{self.a('site.css')}"/>
{ld}
</head>"""

    def logo(self, tid):
        return (f'<a href="{self.u("/")}" class="logo" data-testid="{tid}" aria-label="i\'M On Social home">'
                f'<picture><source srcset="{self.a("img/logo.webp")}" type="image/webp"/><img src="{self.a("img/logo.png")}" alt="i\'M On Social" width="42" height="48"/></picture></a>')

    def _dd_features(self):
        cols = "".join(
            f'<div class="dd-col"><p class="dd-label">{esc(g)}</p>' + "".join(
                f'<a class="dd-link" href="{self.u(p)}" data-testid="nav-features-{slug(n)}"><strong>{esc(n)}</strong><span>{esc(d)}</span></a>' for n, p, d in items) + "</div>"
            for g, items in FEATURES)
        return (f'<div class="dd dd-wide" id="dd-features" role="menu">{cols}<a class="dd-all" href="{self.u("/features/")}" data-testid="nav-features-all">'
                f'All features {icon("arrow", 16)}</a></div>')

    def _dd_list(self, key, items):
        links = "".join(f'<a class="dd-link" href="{self.u(p)}" data-testid="nav-{key}-{slug(n)}"><strong>{esc(n)}</strong></a>' for n, p in items)
        return f'<div class="dd" id="dd-{key}" role="menu">{links}</div>'

    def _trigger(self, key, label):
        return (f'<button class="nav-trigger" type="button" aria-expanded="false" aria-controls="dd-{key}" data-dd="{key}" data-testid="nav-{key}-trigger">'
                f'{esc(label)} {icon("chev", 16, "ico chev")}</button>')

    def nav(self):
        return f"""<a class="skip" href="#main">Skip to content</a>
<header class="site-header" data-testid="site-header">
  <div class="wrap header-inner">
    {self.logo("nav-logo")}
    <nav class="nav" aria-label="Main">
      <a class="nav-link" href="{self.u('/#how-it-works')}" data-scroll="how-it-works" data-testid="nav-how-it-works">How It Works</a>
      <div class="nav-item">{self._trigger("features", "Features")}{self._dd_features()}</div>
      <div class="nav-item">{self._trigger("solutions", "Solutions")}{self._dd_list("solutions", SOLUTIONS)}</div>
      <a class="nav-link" href="{self.u('/pricing/')}" data-testid="nav-pricing">Pricing</a>
      <div class="nav-item">{self._trigger("resources", "Resources")}{self._dd_list("resources", RESOURCES)}</div>
    </nav>
    <div class="header-actions">
      <a class="nav-link signin" href="{SIGN_IN}" data-testid="nav-sign-in">Sign In</a>
      <button class="btn btn-gold btn-sm" type="button" data-demo="nav" data-testid="nav-book-demo-button">Book a Demo</button>
      <button class="menu-btn" type="button" aria-label="Open menu" aria-expanded="false" aria-controls="mobile-sheet" data-testid="nav-mobile-toggle">{icon("menu", 24)}</button>
    </div>
  </div>
</header>
{self.mobile_sheet()}"""

    def _acc(self, key, label, links):
        return (f'<details class="sheet-acc" data-testid="mobile-acc-{key}"><summary data-testid="mobile-acc-{key}-toggle">{esc(label)} {icon("chev", 18, "ico chev")}</summary>'
                f'<div class="sheet-links">{links}</div></details>')

    def mobile_sheet(self):
        feat = "".join(self.link(n, p, f"mobile-features-{slug(n)}") for _, items in FEATURES for n, p, _ in items) + self.link("All features", "/features/", "mobile-features-all")
        sol = "".join(self.link(n, p, f"mobile-solutions-{slug(n)}") for n, p in SOLUTIONS)
        res = "".join(self.link(n, p, f"mobile-resources-{slug(n)}") for n, p in RESOURCES)
        return f"""<div class="sheet" id="mobile-sheet" aria-hidden="true" data-testid="mobile-sheet">
  <div class="sheet-top">{self.logo("mobile-sheet-logo")}<button class="menu-btn" type="button" aria-label="Close menu" data-sheet-close data-testid="mobile-sheet-close">{icon("x", 24)}</button></div>
  <div class="sheet-body">
    <a class="sheet-link" href="{self.u('/#how-it-works')}" data-scroll="how-it-works" data-testid="mobile-how-it-works">How It Works</a>
    {self._acc("features", "Features", feat)}
    {self._acc("solutions", "Solutions", sol)}
    <a class="sheet-link" href="{self.u('/pricing/')}" data-testid="mobile-pricing">Pricing</a>
    {self._acc("resources", "Resources", res)}
    <a class="sheet-link" href="{SIGN_IN}" data-testid="mobile-sign-in">Sign In</a>
  </div>
  <div class="sheet-cta"><button class="btn btn-gold btn-block" type="button" data-demo="mobile_nav" data-testid="mobile-book-demo-button">Book a Demo</button></div>
</div>"""

    def footer(self):
        cols = "".join(
            f'<details class="f-col" open data-testid="footer-col-{slug(t)}"><summary data-testid="footer-accordion-toggle-{slug(t)}">{esc(t)} {icon("chev", 18, "ico chev")}</summary>'
            f'<div class="f-links">' + "".join(self.link(n, p, f"footer-{slug(t)}-{slug(n)}") for n, p in links) + "</div></details>"
            for t, links in FOOTER)
        socials = "".join(f'<a href="{h}" target="_blank" rel="noopener" data-testid="footer-social-{n.lower()}">{n}</a>' for n, h in
                          (("Instagram", "https://instagram.com/imonsocialapp"), ("TikTok", "https://tiktok.com/@imonsocialapp"), ("YouTube", "https://youtube.com/@imonsocial")))
        return f"""<footer class="site-footer" data-testid="site-footer">
  <div class="wrap footer-grid">
    <div class="f-brand">
      {self.logo("footer-logo")}
      <p>The Relationship OS for businesses and the people who sell for them.</p>
      <a class="appstore" href="https://app.imonsocial.com/api/get/site" data-testid="footer-app-store">Get the iPhone app {icon("arrow", 16)}</a>
      <div class="socials">{socials}</div>
    </div>
    <div class="f-cols">{cols}</div>
  </div>
  <div class="wrap f-legal">
    <p>&copy; 2026 i'M On Social. Operated by VI Ventures Group LLC.</p>
    <div>{self.link("Privacy", "/privacy/", "footer-legal-privacy")}{self.link("Terms", "/terms/", "footer-legal-terms")}{self.link("SMS Policy", "/sms-terms/", "footer-legal-sms")}{self.link("Contact", "#contact", "footer-legal-contact")}<a class="faded" href="{self.u('/feature-sheet/')}" data-testid="footer-feature-sheet">Feature sheet</a></div>
  </div>
</footer>"""

    def _consent(self, prefix):
        return (f'<label class="consent" data-testid="{prefix}-sms-consent-label"><input type="checkbox" name="sms_opt_in" data-testid="{prefix}-sms-consent"/>'
                f'<span>I agree to receive SMS messages from i\'M On Social about my request and follow-up communications. Msg &amp; data rates may apply. '
                f'Message frequency varies. Reply STOP to opt out, HELP for help. See our <a href="{self.u("/sms-terms/")}" data-testid="{prefix}-sms-policy-link">SMS Messaging Policy</a>.</span></label>'
                f'<p class="legal-line">By submitting you agree to our <a href="{self.u("/terms/")}">Terms</a> and <a href="{self.u("/privacy/")}">Privacy Policy</a>. '
                f'i\'M On Social is operated by VI Ventures Group LLC.</p>')

    def _field(self, prefix, name, label, typ="text", req=True, auto="", ph=""):
        star = ' <span aria-hidden="true">*</span>' if req else ' <em>(optional)</em>'
        return (f'<div class="field"><label for="{prefix}-{name}">{label}{star}</label><input id="{prefix}-{name}" name="{name}" type="{typ}"'
                f'{" required" if req else ""}{f" autocomplete={chr(34)}{auto}{chr(34)}" if auto else ""}{f" placeholder={chr(34)}{ph}{chr(34)}" if ph else ""} data-testid="{prefix}-{name}-input"/></div>')

    def modals(self):
        inds = "".join(f'<option value="{v}">{esc(t)}</option>' for v, t in INDUSTRIES)
        sizes = '<option value="">Select team size</option>' + "".join(f'<option value="{s}">{s}</option>' for s in TEAM_SIZES)
        x = icon("x", 22)
        return f"""<div class="modal" id="demo-modal" role="dialog" aria-modal="true" aria-labelledby="demo-title" aria-hidden="true" data-testid="book-demo-modal">
  <div class="modal-card">
    <button class="modal-close" type="button" aria-label="Close" data-modal-close data-testid="demo-modal-close">{x}</button>
    <form class="demo-form" id="demo-form" novalidate data-testid="demo-form">
      <p class="overline">Book a demo</p>
      <h2 id="demo-title">See i'M On Social with your own customers in mind.</h2>
      <p class="modal-sub">A short call with our team. We will show you the app and set you up on the plan that fits.</p>
      <div class="row2">{self._field("demo", "first_name", "First name", auto="given-name")}{self._field("demo", "last_name", "Last name", req=False, auto="family-name")}</div>
      <div class="row2">{self._field("demo", "phone", "Mobile", "tel", auto="tel")}{self._field("demo", "email", "Email", "email", auto="email")}</div>
      {self._field("demo", "company", "Company", auto="organization")}
      <div class="row2">
        <div class="field"><label for="demo-industry">Industry <span aria-hidden="true">*</span></label><select id="demo-industry" name="business_type" required data-testid="demo-industry-select">{inds}</select></div>
        <div class="field"><label for="demo-team">Team size <em>(optional)</em></label><select id="demo-team" name="team_size" data-testid="demo-team-size-select">{sizes}</select></div>
      </div>
      {self._consent("demo")}
      <p class="form-error" role="alert" data-testid="demo-form-error" hidden></p>
      <button class="btn btn-gold btn-block" type="submit" data-testid="demo-form-submit-button">Book my demo</button>
    </form>
    <div class="form-success" hidden data-testid="demo-form-success-message">
      <div class="success-ico">{icon("check", 28)}</div>
      <h2>Thanks, <span data-first>there</span>.</h2>
      <p>Someone from our team will reach out shortly to pick a time.</p>
      <button class="btn btn-ink" type="button" data-modal-close data-testid="demo-success-close">Done</button>
    </div>
  </div>
</div>
<div class="modal" id="contact-modal" role="dialog" aria-modal="true" aria-labelledby="contact-title" aria-hidden="true" data-testid="contact-modal">
  <div class="modal-card">
    <button class="modal-close" type="button" aria-label="Close" data-modal-close data-testid="contact-modal-close">{x}</button>
    <form class="contact-form" id="contact-form" novalidate data-testid="contact-form">
      <p class="overline">Contact us</p>
      <h2 id="contact-title">How can we help?</h2>
      <p class="modal-sub">Send us a note and we will get back to you within one business day.</p>
      <div class="row2">{self._field("contact", "first_name", "First name", auto="given-name")}{self._field("contact", "last_name", "Last name", req=False, auto="family-name")}</div>
      <div class="row2">{self._field("contact", "email", "Email", "email", auto="email")}{self._field("contact", "phone", "Mobile", "tel", req=False, auto="tel")}</div>
      <div class="field"><label for="contact-message">Message <span aria-hidden="true">*</span></label><textarea id="contact-message" name="message" rows="4" required data-testid="contact-message-input"></textarea></div>
      {self._consent("contact")}
      <p class="form-error" role="alert" data-testid="contact-form-error" hidden></p>
      <button class="btn btn-ink btn-block" type="submit" data-testid="contact-form-submit-button">Send message</button>
    </form>
    <div class="form-success" hidden data-testid="contact-form-success-message">
      <div class="success-ico">{icon("check", 28)}</div>
      <h2>Thanks, <span data-first>there</span>.</h2>
      <p>We got your message and will reply within one business day.</p>
      <button class="btn btn-ink" type="button" data-modal-close data-testid="contact-success-close">Done</button>
    </div>
  </div>
</div>
<div class="modal modal-video" id="video-modal" role="dialog" aria-modal="true" aria-label="The i'M On Social story" aria-hidden="true" data-testid="video-lightbox">
  <div class="video-card">
    <button class="modal-close" type="button" aria-label="Close video" data-modal-close data-testid="video-lightbox-close">{x}</button>
    <video controls playsinline preload="none" poster="{self.u('/video/social-ad-poster.jpg')}" data-testid="video-lightbox-player">
      <source src="{self.u('/video/social-ad.webm')}" type="video/webm"/><source src="{self.u('/video/social-ad.mp4')}" type="video/mp4"/>
    </video>
  </div>
</div>"""

    def page(self, title, desc, path, body, jsonld, page_key):
        return f"""<!DOCTYPE html>
<html lang="en" data-api="{self.api}" data-page="{page_key}">
{self.head(title, desc, path, jsonld)}
<body>
{self.nav()}
<main id="main">
{body}
</main>
{self.footer()}
{self.modals()}
<script src="{self.u('/lead-retry.js')}" defer></script>
<script src="{self.a('site.js')}" defer></script>
<script src="https://app.imonsocial.com/api/w/FE2POg13.js" async></script>
</body>
</html>
"""
