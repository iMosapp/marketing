"""Marketing site generator (new design system).

  python marketing/site/build.py preview      Staging: fresh copy of marketing/build -> marketing/build-preview (links prefixed for
                                              {preview}/api/marketing-preview/, forms post to the preview API, everything noindex),
                                              old homepage kept at /current-home/, retired URLs become redirect stubs, then all new pages + assets.
  python marketing/site/build.py production --approved
                                              Writes the new pages + assets into marketing/build, removes retired pages, adds their 301s to
                                              vercel.json / netlify.toml and rewrites sitemap.xml (goes live on Save to GitHub). Owner approval only.
"""
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from layout import Site  # noqa: E402
import pages  # noqa: E402

ROOT = HERE.parent
BUILD, PREVIEW = ROOT / "build", ROOT / "build-preview"
PREVIEW_BASE = "/api/marketing-preview"
SITE_URL = "https://www.imonsocial.com"

# Retired pages folded into the new structure (approved plan, section 4).
REDIRECTS = {"/automotive": "/dealers", "/salespresentation": "/dealers", "/hub": "/organizations", "/platform": "/features",
             "/store-reviews": "/reviews", "/future": "/why-imonsocial", "/presentation": "/presentations"}
# Phase 0 sent /industries to the homepage; it is a real page now.
UNREDIRECT = {"/industries": "/industries", "/industries.html": "/industries"}
NOINDEX_DIRS = ["presentations", "calendar-systems"]
SITEMAP_EXTRA = ["/developers"]


def version():
    h = hashlib.md5()
    for f in sorted((HERE / "assets").rglob("*")):
        if f.is_file():
            h.update(f.read_bytes())
    return h.hexdigest()[:8]


def prefix_links(text):
    text = re.sub(r'((?:href|src|poster|action)=["\'])/(?!/)', rf"\1{PREVIEW_BASE}/", text)
    text = text.replace("https://app.imonsocial.com/api/demo-requests", "/api/demo-requests")
    return text.replace("<head>", '<head>\n<meta name="robots" content="noindex, nofollow"/>', 1)


def add_noindex(target):
    for d in NOINDEX_DIRS:
        for f in (target / d).rglob("*.html"):
            t = f.read_text(encoding="utf-8")
            if 'name="robots"' not in t:
                f.write_text(t.replace("<head>", '<head>\n<meta name="robots" content="noindex, nofollow"/>', 1), encoding="utf-8")


def stub(dest):
    return (f'<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"/><meta name="robots" content="noindex"/><title>Moved</title>'
            f'<meta http-equiv="refresh" content="0; url={dest}"/><link rel="canonical" href="{dest}"/></head>'
            f'<body><p>This page moved to <a href="{dest}">{dest}</a>.</p></body></html>')


def sync_preview():
    if PREVIEW.exists():
        shutil.rmtree(PREVIEW)
    shutil.copytree(BUILD, PREVIEW, ignore=shutil.ignore_patterns("_logo_backup"))
    for f in PREVIEW.rglob("*.html"):
        f.write_text(prefix_links(f.read_text(encoding="utf-8")), encoding="utf-8")
    (PREVIEW / "current-home").mkdir(exist_ok=True)
    shutil.copy(PREVIEW / "index.html", PREVIEW / "current-home" / "index.html")
    for src, dst in REDIRECTS.items():
        d = PREVIEW / src.strip("/")
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)
        (d / "index.html").write_text(stub(f"{PREVIEW_BASE}{dst}/"), encoding="utf-8")


def write_pages(target, site):
    shutil.copytree(HERE / "assets", target / "assets", dirs_exist_ok=True)
    rendered = pages.all_pages(HERE / "legal")
    for rel, render in rendered.items():
        out = target / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render(site), encoding="utf-8")
    print(f"wrote {len(rendered)} pages into {target}")
    return rendered


def sitemap(target, rendered):
    paths = sorted({"/" + rel[: -len("index.html")].rstrip("/") for rel in rendered} | set(SITEMAP_EXTRA))
    urls = "".join(f"  <url><loc>{SITE_URL}{p}</loc></url>\n" for p in paths)
    (target / "sitemap.xml").write_text(f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls}</urlset>\n',
                                        encoding="utf-8")


def update_vercel(path):
    d = json.loads(path.read_text())
    keep = [r for r in d["redirects"] if r["source"] not in UNREDIRECT and r["source"].rstrip("/") not in REDIRECTS]
    keep.append({"source": "/industries.html", "destination": "/industries", "permanent": True})
    keep += [{"source": s, "destination": t, "permanent": True} for s, t in REDIRECTS.items()]
    d["redirects"] = keep
    path.write_text(json.dumps(d, indent=2) + "\n")


def update_netlify(path):
    t = path.read_text()
    for src in list(UNREDIRECT) + list(REDIRECTS):
        t = re.sub(rf'\n\[\[redirects\]\]\n  from = "{re.escape(src)}/?"\n[^\[]*', "\n", t)
    rules = [("/industries.html", "/industries")] + list(REDIRECTS.items())
    t = t.rstrip() + "\n" + "".join(f'\n[[redirects]]\n  from = "{s}"\n  to = "{d}"\n  status = 301\n  force = true\n' for s, d in rules)
    path.write_text(t)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "preview"
    if mode == "preview":
        sync_preview()
        rendered = write_pages(PREVIEW, Site(PREVIEW_BASE, "", version(), preview=True))
        add_noindex(PREVIEW)
        sitemap(PREVIEW, rendered)
    elif mode == "production" and "--approved" in sys.argv:
        for src in REDIRECTS:
            shutil.rmtree(BUILD / src.strip("/"), ignore_errors=True)
        rendered = write_pages(BUILD, Site("", "https://app.imonsocial.com", version(), preview=False))
        add_noindex(BUILD)
        sitemap(BUILD, rendered)
        for v in (ROOT / "vercel.json", BUILD / "vercel.json"):
            update_vercel(v)
        update_netlify(ROOT / "netlify.toml")
    else:
        sys.exit("usage: build.py preview | production --approved")


if __name__ == "__main__":
    main()
