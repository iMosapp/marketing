"""Give every marketing page a real link-preview image (iMessage/Slack/LinkedIn read og:image; it must be absolute).
run: cd /app/marketing && python3 add_og_tags.py
"""
import re
from pathlib import Path

ROOT = Path("/app/marketing")
IMG = "https://www.imonsocial.com/og-image.png"
TAGS = (
    f'  <meta property="og:image" content="{IMG}"/>\n'
    '  <meta property="og:image:width" content="1200"/>\n'
    '  <meta property="og:image:height" content="630"/>\n'
    '  <meta property="og:image:alt" content="i\'M On Social - The Relationship OS for Sales Teams"/>\n'
    '  <meta name="twitter:card" content="summary_large_image"/>\n'
    f'  <meta name="twitter:image" content="{IMG}"/>\n'
)
OLD_TAG = re.compile(r'\s*<meta (?:property|name)="(?:og:image(?::width|:height|:alt)?|twitter:image|twitter:card)" content="[^"]*"\s*/?>', re.I)

changed = 0
for html in list((ROOT / "build").rglob("*.html")) + [ROOT / "public" / "index.html"]:
    if "_logo_backup" in html.parts or "node_modules" in html.parts:
        continue
    src = html.read_text(encoding="utf-8", errors="ignore")
    if "</head>" not in src:
        continue
    out = OLD_TAG.sub("", src)
    # sit right after the last og: tag when there is one, else just before </head>
    m = None
    for m in re.finditer(r'<meta property="og:[^"]+" content="[^"]*"\s*/?>\n?', out):
        pass
    if m:
        out = out[:m.end()] + ("" if out[m.end() - 1] == "\n" else "\n") + TAGS + out[m.end():]
    else:
        out = out.replace("</head>", TAGS + "</head>", 1)
    if out != src:
        html.write_text(out, encoding="utf-8")
        changed += 1
print(f"updated {changed} pages")
