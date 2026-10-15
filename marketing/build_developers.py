#!/usr/bin/env python3
"""Developer docs content for the marketing site (www.imonsocial.com/developers).
Source of truth = the three markdown files in /app/docs (also served by the app API at /api/public/developer-docs).
Since Oct 2026 the page itself is rendered in the new site design by marketing/site/build.py (pages.developers), which reuses render_doc() below.
After editing a doc run `python3 marketing/site/build.py preview` (staging) or `production --approved`. Needs `pip install markdown`."""
import html
import os
import re
from datetime import date

try:
    import markdown
except ImportError:
    raise SystemExit("pip install markdown   (pure python, build-time only)")

HERE = os.path.dirname(os.path.abspath(__file__))
DOCS = [
    {"slug": "api-reference", "path": "/app/docs/DEVELOPER_API.md", "title": "API Reference", "sub": "Keys, endpoints, webhooks, lead intake, testing", "icon": "fa-solid fa-code", "color": "#5856D6"},
    {"slug": "crm-integration-guide", "path": "/app/docs/CRM_INTEGRATION_GUIDE.md", "title": "CRM Integration Guide", "sub": "Two-way sync patterns and field maps", "icon": "fa-solid fa-diagram-project", "color": "#007AFF"},
    {"slug": "automotive-crm-programs", "path": "/app/docs/AUTOMOTIVE_CRM_CERTIFICATION.md", "title": "Automotive CRM Programs", "sub": "Certification checklist per vendor", "icon": "fa-solid fa-car", "color": "#34C759"},
]
APP = "https://app.imonsocial.com"


def esc(s):
    return html.escape(s, quote=True)


def slugify(t):
    return re.sub(r"[^a-z0-9]+", "-", re.sub(r"<[^>]+>", "", t).lower()).strip("-")


def render_doc(d):
    with open(d["path"], encoding="utf-8") as f:
        md = f.read()
    md = re.sub(r"^# .*\n", "", md, count=1)  # page prints its own title
    body = markdown.markdown(md, extensions=["tables", "fenced_code", "sane_lists", "attr_list"], output_format="html5")
    # checklists: "[ ] text" -> checkbox
    body = body.replace("<li>[ ] ", '<li class="todo"><span class="box"></span>')
    # h2 ids (prefixed per doc so anchors are unique across the three docs) + sidebar TOC
    toc = []

    def h2(m):
        text = m.group(1)
        hid = f"{d['slug']}--{slugify(text)}"
        toc.append((hid, re.sub(r"<[^>]+>", "", text)))
        return f'<h2 id="{hid}">{text}</h2>'

    body = re.sub(r"<h2>(.*?)</h2>", h2, body)
    body = re.sub(r"<h3>(.*?)</h3>", lambda m: f'<h3 id="{d["slug"]}--{slugify(m.group(1))}">{m.group(1)}</h3>', body)
    body = body.replace('<a href="http', '<a target="_blank" rel="noopener" href="http')
    body = re.sub(r"<table>(\s*<thead>.*?</thead>)", lambda m: ('<table class="wide">' if m.group(1).count("<th>") >= 5 else "<table>") + m.group(1), body, flags=re.S)
    updated = date.fromtimestamp(os.path.getmtime(d["path"])).strftime("%b %d, %Y")
    toc_html = "".join(f'<a href="#{hid}">{esc(t)}</a>' for hid, t in toc)
    return f'''<article class="doc" id="doc-{d["slug"]}" data-slug="{d["slug"]}" hidden>
  <div class="doc-head">
    <div class="sec-tag" style="color:{d["color"]}"><i class="{d["icon"]}"></i> {esc(d["sub"])}</div>
    <h1>{esc(d["title"])}</h1>
    <div class="doc-meta"><span>Updated {updated}</span><a href="{APP}/api/public/developer-docs/{d["slug"]}.md" target="_blank" rel="noopener"><i class="fa-solid fa-download"></i> Markdown</a></div>
  </div>
  <nav class="on-page" aria-label="On this page">{toc_html}</nav>
  <div class="md">{body}</div>
</article>'''


if __name__ == "__main__":
    raise SystemExit("Developers is now rendered by marketing/site/build.py (new design). Run that instead.")
