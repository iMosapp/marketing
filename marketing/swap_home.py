"""One-off: make the Relationship OS story the site home, move the old home to /platform, fix links.
run: cd /app/marketing && python swap_home.py
"""
import re
from pathlib import Path

B = Path("/app/marketing/build")
old = (B / "index.html").read_text()
ro = (B / "relationship-os" / "index.html").read_text()
OL, RL = old.split("\n"), ro.split("\n")


def lines(src, a, b):  # 1-based inclusive
    return "\n".join(src[a - 1:b])


# ---------- pieces from the old home ----------
head_top = lines(OL, 1, 15)
css_nav = lines(OL, 47, 89)
css_getapp = lines(OL, 27, 45)
css_sectag = lines(OL, 108, 108)
css_footer = lines(OL, 181, 196)
css_modal = lines(OL, 198, 212)
css_rv = lines(OL, 214, 217)
nav = lines(OL, 223, 346)
getapp = lines(OL, 558, 578)
footer = lines(OL, 585, 627)
modals_scripts = lines(OL, 629, 767)

# ---------- pieces from the Relationship OS page ----------
css_root = lines(RL, 12, 14)
css_ro = lines(RL, 34, 171)
ro_body = lines(RL, 219, 445).replace('src="img/', 'src="/relationship-os/img/')

# hero: add a quiet link to the full platform under the buttons
ro_body = ro_body.replace(
    """    <a href="#" class="btn-lg ghost" onclick="openDemoModal(event,'hero')">Book a Demo</a>
  </div>
</section>""",
    """    <a href="#" class="btn-lg ghost" onclick="openDemoModal(event,'hero')">Book a Demo</a>
  </div>
  <p class="hero-more">Looking for the full feature list? <a href="/platform/">See everything the platform does <i class="fa-solid fa-arrow-right"></i></a></p>
</section>""")

css_platform = """
/* HERO extra */
.hero-more{margin-top:22px;font-size:14px;color:var(--text-3)}
.hero-more a{color:var(--text);font-weight:600;text-decoration:none;border-bottom:1px solid var(--border-2);padding-bottom:1px}
.hero-more a:hover{color:var(--gold);border-color:var(--gold)}
.hero-more a i{font-size:11px;margin-left:4px}

/* FULL PLATFORM */
.platform{background:var(--bg-2);padding:100px 24px;border-top:1px solid var(--border)}
.platform .k{max-width:1100px;margin:0 auto;text-align:center}
.platform .eyebrow{margin-bottom:18px}
.platform h2{font-size:44px;font-weight:900;line-height:1.1;letter-spacing:-.03em;margin-bottom:14px}
.platform h2 .g{color:var(--gold)}
.platform .sub{font-size:18px;color:var(--text-2);max-width:640px;margin:0 auto 44px}
.pf-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;text-align:left;margin-bottom:40px}
.pf{display:flex;align-items:center;gap:14px;background:#FFF;border:1px solid var(--border-2);border-radius:18px;padding:18px 20px;text-decoration:none;color:var(--text);transition:all .25s}
.pf:hover{transform:translateY(-3px);box-shadow:0 14px 40px rgba(0,0,0,.07);border-color:var(--gold)}
.pf .ic{width:44px;height:44px;border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:18px;flex-shrink:0}
.pf strong{display:block;font-size:15px;font-weight:700}
.pf span{font-size:13px;color:var(--text-3);line-height:1.35}
.pf-more{display:flex;flex-wrap:wrap;justify-content:center;gap:8px 10px;margin-bottom:40px}
.pf-more a{font-size:13px;font-weight:600;color:var(--text-2);text-decoration:none;background:#FFF;border:1px solid var(--border-2);border-radius:980px;padding:8px 14px;transition:all .2s}
.pf-more a:hover{border-color:var(--gold);color:var(--text)}
.pf-cta{display:inline-flex;align-items:center;gap:10px;background:#0A0A0F;color:#FFF;padding:16px 34px;border-radius:980px;font-size:16px;font-weight:700;text-decoration:none;transition:all .25s}
.pf-cta:hover{transform:translateY(-2px);box-shadow:0 10px 30px rgba(0,0,0,.2)}
.pf-cta i{color:var(--gold)}
@media(max-width:900px){.pf-grid{grid-template-columns:1fr 1fr}}
@media(max-width:768px){.platform{padding:72px 20px}.platform h2{font-size:30px}.platform .sub{font-size:16px}}
@media(max-width:560px){.pf-grid{grid-template-columns:1fr}}
"""

platform_section = """
<!-- THE FULL PLATFORM -->
<section class="platform" id="platform">
  <div class="k">
    <span class="eyebrow rv">The full platform</span>
    <h2 class="rv">The Relationship OS is the heart.<br/><span class="g">Here is everything around it.</span></h2>
    <p class="sub rv">Digital cards, personal reviews, automated campaigns, one inbox, Jessi AI, leaderboards and SEO. Every piece feeds the book of business you just saw.</p>
    <div class="pf-grid">
      <a class="pf rv" href="/digital-card/"><div class="ic" style="background:rgba(0,122,255,.08)"><i class="fa-regular fa-id-card" style="color:#007AFF"></i></div><div><strong>Digital Business Cards</strong><span>Shareable, trackable, always current</span></div></a>
      <a class="pf rv" href="/reviews/"><div class="ic" style="background:rgba(255,214,10,.12)"><i class="fa-regular fa-star" style="color:#D4AD00"></i></div><div><strong>Personal Reviews</strong><span>A reputation that follows the rep</span></div></a>
      <a class="pf rv" href="/date-triggers/"><div class="ic" style="background:rgba(255,149,0,.1)"><i class="fa-solid fa-rocket" style="color:#FF9500"></i></div><div><strong>Automated Campaigns</strong><span>Birthdays and follow-ups on autopilot</span></div></a>
      <a class="pf rv" href="/inbox/"><div class="ic" style="background:rgba(88,86,214,.1)"><i class="fa-regular fa-comment-dots" style="color:#5856D6"></i></div><div><strong>Inbox &amp; Messaging</strong><span>SMS, WhatsApp and email in one place</span></div></a>
      <a class="pf rv" href="/jessi/"><div class="ic" style="background:rgba(175,82,222,.1)"><i class="fa-solid fa-wand-magic-sparkles" style="color:#AF52DE"></i></div><div><strong>Jessi AI</strong><span>Answers texts and remembers everyone</span></div></a>
      <a class="pf rv" href="/leaderboard/"><div class="ic" style="background:rgba(255,59,48,.1)"><i class="fa-solid fa-trophy" style="color:#FF3B30"></i></div><div><strong>Leaderboards</strong><span>Friendly competition across the team</span></div></a>
    </div>
    <div class="pf-more rv">
      <a href="/dealers/">Automotive</a><a href="/real-estate/">Real Estate</a><a href="/powersports/">Powersports</a><a href="/home-services/">Home Services</a><a href="/insurance/">Insurance</a><a href="/medical/">Medical &amp; Dental</a><a href="/restaurants/">Restaurants</a><a href="/salons/">Salons &amp; Spas</a><a href="/fitness/">Fitness</a><a href="/hub/">Sales Teams</a>
    </div>
    <a class="pf-cta rv" href="/platform/"><i class="fa-solid fa-grip"></i> Explore the full platform</a>
  </div>
</section>
"""

# ---------- nav changes for the NEW home ----------
FEATURED_RO = re.search(r'          <a class="dd-link" href="/relationship-os/" style="background:linear-gradient[^\n]*\n', nav).group(0)
FEATURED_PLATFORM = ('          <a class="dd-link" href="/platform/" style="background:linear-gradient(90deg,rgba(201,169,98,.10),rgba(201,169,98,0));border:1px solid rgba(201,169,98,.25);border-radius:12px;margin-bottom:6px">'
                     '<div class="dd-ico" style="background:rgba(201,169,98,.14)"><i class="fa-solid fa-grip" style="color:#C9A962"></i></div>'
                     '<div class="dd-txt"><strong>The Full Platform</strong><span>Every product and industry on one page</span></div></a>\n')
RES_RO = '<a class="dd-link" href="/relationship-os/"><div class="dd-ico" style="background:rgba(201,169,98,.1)"><i class="fa-solid fa-heart-circle-bolt" style="color:#C9A962"></i></div><div class="dd-txt"><strong>Relationship OS</strong><span>How it works &amp; what we solve</span></div></a>'
RES_HOME = RES_RO.replace('href="/relationship-os/"', 'href="/"')
MOB_RO = '        <a href="/relationship-os/">The Relationship OS</a>\n'
MOB_PLATFORM = '        <a href="/platform/">The Full Platform</a>\n'

nav_home = nav.replace(FEATURED_RO, FEATURED_PLATFORM).replace(RES_RO, RES_HOME).replace(MOB_RO, MOB_PLATFORM)
assert nav_home.count("/platform/") == 2 and "/relationship-os/" not in nav_home

footer_home = footer.replace('      <a href="/organizations/">For Teams</a>\n',
                             '      <a href="/platform/">The Full Platform</a>\n      <a href="/organizations/">For Teams</a>\n      <a href="/presentation/">Sales Deck</a>\n      <a href="/salespresentation/">Automotive Deck</a>\n')
assert "/platform/" in footer_home

head_home = head_top.replace(
    "<title>I'm On Social The Relationship Engine for Sales Professionals</title>",
    "<title>i'M On Social - The Relationship OS for Sales Teams</title>")
head_home = re.sub(r'<meta name="description" content="[^"]*"/>',
                   '<meta name="description" content="Your CRM remembers the deal. i\'M On Social remembers the person. A living book of business that tells every rep who to talk to, why, and what to say."/>', head_home)
head_home = re.sub(r'<meta property="og:title" content="[^"]*"/>', '<meta property="og:title" content="i\'M On Social - The Relationship OS"/>', head_home)
head_home = re.sub(r'<meta property="og:description" content="[^"]*"/>',
                   '<meta property="og:description" content="Your CRM remembers the deal. i\'M On Social remembers the person."/>', head_home)
head_home = head_home.replace('<link rel="icon" href="favicon.png"/>', '<link rel="icon" href="/favicon.png"/>\n  <link rel="canonical" href="https://www.imonsocial.com/"/>')

new_home = "\n".join([
    head_home,
    "  <style>",
    lines(OL, 17, 17),  # reset
    css_root, "html{scroll-behavior:smooth}",
    css_nav, css_getapp, css_sectag, css_ro, css_platform, css_footer, css_modal, css_rv,
    "  </style>",
    '<script src="/lead-retry.js"></script>',
    "</head>", "<body>", "",
    nav_home, "",
    ro_body.replace("<!-- CTA -->\n<section class=\"cta-bottom\">", platform_section + "\n" + getapp + "\n\n<!-- CTA -->\n<section class=\"cta-bottom\">"),
    "",
    footer_home, "",
    modals_scripts.replace("lead_source:_demoSource||'homepage'", "lead_source:_demoSource||'homepage_ros'"),
    "</body>", "</html>", "",
])
assert new_home.count('id="demoModal"') == 1 and 'class="platform"' in new_home and 'id="get-the-app"' in new_home
# hero button colours: the story page uses black primary; keep nav CTA blue from the shared nav

# ---------- /platform page = old home, relabelled ----------
plat = old
plat = plat.replace("<title>I'm On Social The Relationship Engine for Sales Professionals</title>",
                    "<title>The Full Platform - i'M On Social</title>")
plat = plat.replace('<link rel="icon" href="favicon.png"/>', '<link rel="icon" href="/favicon.png"/>\n  <link rel="canonical" href="https://www.imonsocial.com/platform/"/>')
plat = plat.replace('<div class="hero-tag"><i class="fa-solid fa-bolt" style="color:var(--yellow)"></i> Built for sales professionals</div>',
                    '<div class="hero-tag"><i class="fa-solid fa-grip" style="color:var(--blue)"></i> The full platform</div>')
plat = plat.replace("""  <p>Every customer you've ever helped is a referral waiting to happen. They just need a reason to remember your name. We give them that reason , on autopilot.</p>
</section>""", """  <p>Every customer you've ever helped is a referral waiting to happen. They just need a reason to remember your name. We give them that reason, on autopilot.</p>
  <div class="hero-btns">
    <a href="/" class="btn-lg ghost"><i class="fa-solid fa-heart-pulse" style="color:#C9A962"></i> Start with the Relationship OS story</a>
    <a href="#" class="btn-lg primary" onclick="openDemoModal(event,'platform_hero')">Book a Demo</a>
  </div>
</section>""")
plat = plat.replace(FEATURED_RO, FEATURED_RO.replace('href="/relationship-os/"', 'href="/"').replace(
    '<span style="display:inline-block;margin-left:6px;padding:1px 7px;border-radius:999px;background:#C9A962;color:#000;font-size:10px;font-weight:800;letter-spacing:.6px;vertical-align:middle">PRESENTATION</span>',
    '<span style="display:inline-block;margin-left:6px;padding:1px 7px;border-radius:999px;background:#C9A962;color:#000;font-size:10px;font-weight:800;letter-spacing:.6px;vertical-align:middle">HOME</span>'))
plat = plat.replace(RES_RO, RES_HOME).replace(MOB_RO, '        <a href="/">The Relationship OS</a>\n')
plat = plat.replace("lead_source:_demoSource||'homepage'", "lead_source:_demoSource||'platform_page'")
plat = plat.replace("openDemoModal(event,'homepage_nav')", "openDemoModal(event,'platform_nav')").replace("openDemoModal(event,'homepage_footer')", "openDemoModal(event,'platform_footer')")
assert "/relationship-os/" not in plat
(B / "platform").mkdir(exist_ok=True)
(B / "platform" / "index.html").write_text(plat)
(B / "index.html").write_text(new_home)

# ---------- old story URL -> home ----------
(B / "relationship-os" / "index.html").write_text("""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>i'M On Social</title>
<meta http-equiv="refresh" content="0; url=/"><link rel="canonical" href="https://www.imonsocial.com/"><script>location.replace('/')</script></head>
<body style="font-family:Inter,sans-serif;padding:40px;text-align:center">The Relationship OS is now our home page. <a href="/">Continue</a></body></html>
""")

# ---------- every other page: repoint links ----------
changed = 0
for f in B.rglob("*.html"):
    if f in (B / "index.html", B / "platform" / "index.html", B / "relationship-os" / "index.html"):
        continue
    s = f.read_text()
    if "/relationship-os/" not in s:
        continue
    t = s.replace(FEATURED_RO, FEATURED_PLATFORM).replace(MOB_RO, MOB_PLATFORM).replace(RES_RO, RES_HOME)
    t = t.replace('href="/relationship-os/"', 'href="/"')  # anything left (story footers etc.)
    f.write_text(t)
    changed += 1
print("pages repointed:", changed)
