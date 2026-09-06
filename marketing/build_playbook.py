"""Render docs/MANAGER_PLAYBOOK.md into a printable page at marketing/build-preview/playbook/index.html.

Run: python /app/marketing/build_playbook.py
"""
import html
import re
from pathlib import Path

SRC = Path("/app/docs/MANAGER_PLAYBOOK.md")
OUT = Path("/app/marketing/build-preview/playbook/index.html")


def inline(text: str) -> str:
    text = html.escape(text, quote=False)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(https?://[^\s<]+)", r'<a href="\1">\1</a>', text)
    return text


def render(md: str) -> str:
    out, i, lines = [], 0, md.split("\n")
    while i < len(lines):
        line = lines[i].rstrip()
        if not line.strip():
            i += 1
            continue
        if line.startswith("# "):
            out.append(f"<h1>{inline(line[2:])}</h1>")
        elif line.startswith("## "):
            out.append(f"<h2>{inline(line[3:])}</h2>")
        elif line.startswith("### "):
            out.append(f"<h3>{inline(line[4:])}</h3>")
        elif line.strip() == "---":
            out.append("<hr>")
        elif line.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r"-+", c) for c in cells):
                    rows.append(cells)
                i += 1
            head, body = rows[0], rows[1:]
            out.append("<table><thead><tr>" + "".join(f"<th>{inline(c)}</th>" for c in head) + "</tr></thead><tbody>")
            for r in body:
                out.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>")
            out.append("</tbody></table>")
            continue
        elif re.match(r"^\d+\. ", line):
            out.append("<ol>")
            while i < len(lines) and re.match(r"^\d+\. ", lines[i]):
                item = re.sub(r"^\d+\. ", "", lines[i])
                out.append(f"<li>{inline(item)}</li>")
                i += 1
            out.append("</ol>")
            continue
        elif line.startswith("- "):
            out.append("<ul>")
            while i < len(lines) and lines[i].startswith("- "):
                out.append(f"<li>{inline(lines[i][2:])}</li>")
                i += 1
            out.append("</ul>")
            continue
        else:
            out.append(f"<p>{inline(line)}</p>")
        i += 1
    return "\n".join(out)


CSS = """
:root{--gold:#C9A962;--ink:#111;--muted:#555;--line:#e5e1d8}
*{box-sizing:border-box}body{margin:0;background:#f6f4ef;color:var(--ink);font:16px/1.55 Georgia,'Times New Roman',serif}
.page{max-width:820px;margin:0 auto;padding:48px 32px 96px;background:#fff}
h1{font-size:34px;line-height:1.15;margin:0 0 8px;letter-spacing:-.01em}
h1+p{color:var(--muted);font-size:17px}
h2{font-size:22px;margin:40px 0 12px;padding-top:12px;border-top:3px solid var(--gold)}
h3{font-size:17px;margin:24px 0 8px;text-transform:uppercase;letter-spacing:.06em;color:#6b5a2b}
p{margin:0 0 12px}ul,ol{margin:0 0 14px;padding-left:22px}li{margin:4px 0}
table{width:100%;border-collapse:collapse;margin:8px 0 18px;font-size:15px}
th{text-align:left;background:#faf7ef;border-bottom:2px solid var(--gold);padding:8px 10px}
td{padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top}
hr{border:0;height:0;margin:8px 0}
a{color:#7a5f1c}
.bar{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:12px 32px;background:#000;color:#fff;font:14px system-ui,-apple-system,sans-serif}
.bar b{color:var(--gold)}.bar button{background:var(--gold);color:#000;border:0;border-radius:999px;padding:8px 16px;font-weight:700;cursor:pointer}
@media print{.bar{display:none}body{background:#fff}.page{padding:0}h2{break-after:avoid}table,ul,ol{break-inside:avoid}}
"""


def main():
    body = render(SRC.read_text())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        "<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>i'M On Social Manager Playbook</title><style>" + CSS + "</style></head><body>"
        "<div class='bar'><span><b>i'M On Social</b> Manager Playbook</span><button onclick='window.print()'>Print / Save as PDF</button></div>"
        f"<main class='page'>{body}</main></body></html>"
    )
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
