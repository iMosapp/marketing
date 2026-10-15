"""Marketing site generator (new design system, Phase 1).

  python marketing/site/build.py preview      Staging: fresh copy of marketing/build -> marketing/build-preview (links prefixed for
                                              {preview}/api/marketing-preview/, forms post to the preview API, everything noindex),
                                              old homepage kept at /current-home/, then the new pages + assets on top.
  python marketing/site/build.py production --approved
                                              Writes the new pages + assets into marketing/build (goes live on Save to GitHub). Owner approval only.
"""
import hashlib
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from layout import Site  # noqa: E402
import home  # noqa: E402

ROOT = HERE.parent
BUILD, PREVIEW = ROOT / "build", ROOT / "build-preview"
PREVIEW_BASE = "/api/marketing-preview"
PAGES = {"index.html": home.render}


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


def sync_preview():
    if PREVIEW.exists():
        shutil.rmtree(PREVIEW)
    shutil.copytree(BUILD, PREVIEW, ignore=shutil.ignore_patterns("_logo_backup"))
    for f in PREVIEW.rglob("*.html"):
        f.write_text(prefix_links(f.read_text(encoding="utf-8")), encoding="utf-8")
    (PREVIEW / "current-home").mkdir(exist_ok=True)
    shutil.copy(PREVIEW / "index.html", PREVIEW / "current-home" / "index.html")


def write(target, site):
    shutil.copytree(HERE / "assets", target / "assets", dirs_exist_ok=True)
    for name, render in PAGES.items():
        (target / name).write_text(render(site), encoding="utf-8")
        print("wrote", target / name)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "preview"
    if mode == "preview":
        sync_preview()
        write(PREVIEW, Site(PREVIEW_BASE, "", version(), preview=True))
    elif mode == "production" and "--approved" in sys.argv:
        write(BUILD, Site("", "https://app.imonsocial.com", version(), preview=False))
    else:
        sys.exit("usage: build.py preview | production --approved")


if __name__ == "__main__":
    main()
