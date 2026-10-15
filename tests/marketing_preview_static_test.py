# Static checks for the staged marketing site (/api/marketing-preview/): pages, links, SEO, sitemap, redirects, pricing/legal copy
import json
import os
import re
import sys
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL") or open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split()[0]
BASE = BASE.rstrip("/")
PRE = BASE + "/api/marketing-preview/"
PAGES = ["", "features/", "industries/", "pricing/", "demo/", "organizations/", "individuals/", "why-imonsocial/", "help/", "training/",
         "jessi/", "inbox/", "digital-card/", "showcase/", "reviews/", "congrats-template/", "date-triggers/", "leaderboard/", "seo/",
         "dealers/", "powersports/", "real-estate/", "insurance/", "home-services/", "salons/", "medical/", "fitness/", "restaurants/",
         "privacy/", "terms/", "sms-terms/"]
REDIRECTS = {"automotive/": "dealers/", "salespresentation/": "dealers/", "hub/": "organizations/", "platform/": "features/",
             "store-reviews/": "reviews/", "future/": "why-imonsocial/", "presentation/": "presentations/"}
BANNED = ["\u2014", "free trial", "NFC", "testimonial", "job to job", "WhatsApp", "No credit card"]


class P(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links, self.imgs, self.h1, self.meta, self.canon, self.ld, self.title = [], [], 0, {}, None, [], ""
        self._in_ld = self._in_t = False
        self.text = []
        self._skip = 0

    def handle_starttag(self, t, a):
        a = dict(a)
        if t == "a" and a.get("href"):
            self.links.append((a["href"], a.get("data-testid", "")))
        if t == "img":
            self.imgs.append(a.get("src"))
        if t == "source" and a.get("srcset"):
            self.imgs.append(a["srcset"].split()[0])
        if t == "h1":
            self.h1 += 1
        if t == "meta" and a.get("name"):
            self.meta[a["name"]] = a.get("content", "")
        if t == "link" and a.get("rel") == "canonical":
            self.canon = a.get("href")
        if t == "script" and a.get("type") == "application/ld+json":
            self._in_ld = True
        if t == "title":
            self._in_t = True
        if t in ("script", "style"):
            self._skip += 1

    def handle_endtag(self, t):
        if t == "script":
            self._in_ld = False
        if t == "title":
            self._in_t = False
        if t in ("script", "style"):
            self._skip -= 1

    def handle_data(self, d):
        if self._in_ld:
            self.ld.append(json.loads(d))
        elif self._in_t:
            self.title += d
        elif not self._skip:
            self.text.append(d)


s = requests.Session()
fails, notes = [], []
titles, descs = {}, {}
all_links = {}
for pg in PAGES:
    r = s.get(PRE + pg, timeout=30)
    if r.status_code != 200:
        fails.append(f"{pg}: status {r.status_code}"); continue
    p = P(); p.feed(r.text)
    h = r.text
    if 'data-testid="site-header"' not in h or 'data-testid="site-footer"' not in h:
        fails.append(f"{pg}: missing header/footer")
    if p.h1 != 1:
        fails.append(f"{pg}: h1 count {p.h1}")
    titles.setdefault(p.title, []).append(pg)
    descs.setdefault(p.meta.get("description"), []).append(pg)
    exp_canon = "https://www.imonsocial.com/" + pg.rstrip("/")
    if p.canon != exp_canon:
        fails.append(f"{pg}: canonical {p.canon} != {exp_canon}")
    if "noindex" not in p.meta.get("robots", ""):
        fails.append(f"{pg}: no noindex")
    types = [x.get("@type") for x in p.ld]
    if "Organization" not in types:
        fails.append(f"{pg}: no Organization JSON-LD ({types})")
    has_faq = re.search(r'data-testid="[a-z-]+-faq-\d', h) is not None
    if has_faq and "FAQPage" not in types:
        fails.append(f"{pg}: FAQ but no FAQPage JSON-LD")
    text = " ".join(p.text)
    if pg not in ("privacy/", "terms/", "sms-terms/"):
        for b in BANNED:
            if b.lower() in text.lower():
                fails.append(f"{pg}: banned copy '{b}' in text: ...{text[max(0, text.lower().find(b.lower())-60):text.lower().find(b.lower())+60]!r}")
    else:
        if "\u2014" in text:
            notes.append(f"{pg}: em dash in legal text (legal text unchanged per spec)")
    for src in p.imgs:
        if src:
            all_links.setdefault(urljoin(PRE + pg, src), set()).add(pg + " [img]")
    for href, tid in p.links:
        full = urljoin(PRE + pg, href)
        u = urlparse(full)
        if u.netloc == urlparse(BASE).netloc:
            if not u.path.startswith("/api/marketing-preview/"):
                fails.append(f"{pg}: internal link not prefixed {href} ({tid})")
            all_links.setdefault(full.split("#")[0], set()).add(pg + f" [{tid}]")
        elif "imonsocial.com" in u.netloc and "app." not in u.netloc:
            notes.append(f"{pg}: absolute prod link {href} ({tid})")

for t, pgs in titles.items():
    if len(pgs) > 1: fails.append(f"duplicate title {t!r}: {pgs}")
for d, pgs in descs.items():
    if len(pgs) > 1 or not d: fails.append(f"duplicate/empty description {d!r}: {pgs}")

checked = 0
for url, frm in sorted(all_links.items()):
    r = s.get(url, timeout=30)
    checked += 1
    if r.status_code != 200:
        fails.append(f"broken link {url} -> {r.status_code} from {sorted(frm)[:3]}")

# redirects
for old, new in REDIRECTS.items():
    r = s.get(PRE + old, timeout=30)
    if r.status_code != 200 or f"url=/api/marketing-preview/{new}" not in r.text:
        fails.append(f"redirect {old} -> {new} wrong: {r.status_code} {r.text[:200]}")
    t = s.get(PRE + new, timeout=30)
    if t.status_code != 200:
        fails.append(f"redirect target {new} -> {t.status_code}")

# sitemap
r = s.get(PRE + "sitemap.xml", timeout=30)
locs = re.findall(r"<loc>(.*?)</loc>", r.text)
if r.status_code != 200 or len(locs) != 32:
    fails.append(f"sitemap status {r.status_code} count {len(locs)}")
if any(not l.startswith("https://www.imonsocial.com") for l in locs):
    fails.append("sitemap non-prod host")
for bad in ["automotive", "/hub", "platform", "store-reviews", "/future", "salespresentation"]:
    if any(bad in l for l in locs): fails.append(f"sitemap has retired {bad}")
sm_paths = {urlparse(l).path.strip("/") for l in locs}
missing = [p for p in PAGES if p.strip("/") not in sm_paths]
extra = sorted(sm_paths - {p.strip("/") for p in PAGES})
notes.append(f"sitemap missing pages: {missing}; extra: {extra}")

print("LINKS CHECKED:", checked)
print("NOTES:\n " + "\n ".join(notes))
print("FAILS (%d):\n " % len(fails) + "\n ".join(fails))
