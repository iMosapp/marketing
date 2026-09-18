#!/usr/bin/env python3
"""Public developer docs page for the marketing site (www.imonsocial.com/developers).
Source of truth = the three markdown files in /app/docs (also served by the app API at /api/public/developer-docs).
Run `python3 build_developers.py` after editing a doc, then redeploy marketing. Needs `pip install markdown`."""
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


def render():
    tabs = "".join(
        f'<a class="tab" href="?doc={d["slug"]}" data-slug="{d["slug"]}" style="--c:{d["color"]}"><i class="{d["icon"]}"></i><span><strong>{esc(d["title"])}</strong><em>{esc(d["sub"])}</em></span></a>'
        for d in DOCS)
    docs = "".join(render_doc(d) for d in DOCS)
    return TEMPLATE.replace("{{TABS}}", tabs).replace("{{DOCS}}", docs).replace("{{YEAR}}", str(date.today().year))


TEMPLATE = r'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1.0"/>
  <title>Developers & API - I'm On Social</title>
  <meta name="description" content="Open REST API and signed webhooks for every customer, text, call, note, task and sold record. CRM integration guide for HubSpot, Salesforce, Zoho, Pipedrive and the automotive CRM certification checklist."/>
  <link rel="canonical" href="https://www.imonsocial.com/developers"/>
  <meta property="og:title" content="Developers & API - I'm On Social"/>
  <meta property="og:description" content="Connect your CRM, DMS or automation tool. API reference, webhooks, CRM integration guide, automotive CRM programs."/>
  <meta property="og:type" content="website"/>
  <meta property="og:url" content="https://www.imonsocial.com/developers"/>
  <meta property="og:image" content="https://www.imonsocial.com/og-image.png"/>
  <meta property="og:image:width" content="1200"/>
  <meta property="og:image:height" content="630"/>
  <meta property="og:image:alt" content="i'M On Social - The Relationship OS for Sales Teams"/>
  <meta name="twitter:card" content="summary_large_image"/>
  <meta name="twitter:image" content="https://www.imonsocial.com/og-image.png"/>
  <link rel="icon" href="/favicon.png"/>
  <link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
  <style>*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{--blue:#007AFF;--blue-dark:#0059CC;--gold:#C9A962;--purple:#5856D6;--green:#34C759;--text:#111;--text-2:#555;--text-3:#888;--bg:#FFF;--bg-2:#F8F9FB;--border:rgba(0,0,0,.06);--border-2:rgba(0,0,0,.1);--mono:'JetBrains Mono',ui-monospace,SFMono-Regular,Menlo,monospace}
html{scroll-behavior:smooth;scroll-padding-top:110px}
body{font-family:'Inter',-apple-system,BlinkMacSystemFont,sans-serif;background:var(--bg);color:var(--text);line-height:1.6;-webkit-font-smoothing:antialiased}
nav.top{position:fixed;top:0;left:0;right:0;z-index:1000;transition:all .3s}
nav.top.scrolled{background:rgba(255,255,255,.96);backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);box-shadow:0 1px 0 var(--border-2)}
.nav-inner{max-width:1200px;margin:0 auto;display:flex;align-items:center;justify-content:space-between;padding:14px 24px}
.logo{display:flex;align-items:center;text-decoration:none}.logo img{height:72px;width:auto}
.nav-cta{display:flex;align-items:center;gap:10px}
.btn-sign{padding:10px 20px;border-radius:980px;font-size:14px;font-weight:600;color:var(--text);text-decoration:none;transition:background .2s}.btn-sign:hover{background:var(--bg-2)}
.btn-demo{background:var(--blue);padding:10px 24px;border-radius:980px;font-size:14px;font-weight:600;color:#FFF;text-decoration:none;transition:all .25s;box-shadow:0 2px 12px rgba(0,122,255,.25)}.btn-demo:hover{background:var(--blue-dark);transform:translateY(-1px)}
.hero{background:var(--bg-2);border-bottom:1px solid var(--border);padding:150px 24px 44px}
.hero-in{max-width:1200px;margin:0 auto}
.sec-tag{font-size:12px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;margin-bottom:12px;display:flex;align-items:center;gap:8px}
.hero h1{font-size:46px;font-weight:900;line-height:1.08;letter-spacing:-.035em;margin-bottom:14px;max-width:820px}
.hero p.lead{font-size:18px;color:var(--text-2);line-height:1.6;max-width:760px}
.quick{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-top:32px}
.qc{background:#FFF;border:1px solid var(--border-2);border-radius:18px;padding:22px;text-decoration:none;color:var(--text);display:block;transition:transform .2s,box-shadow .2s}
.qc:hover{transform:translateY(-2px);box-shadow:0 10px 30px rgba(0,0,0,.06)}
.qc .ico{width:44px;height:44px;border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:18px;margin-bottom:14px;background:color-mix(in srgb,var(--c) 10%,#FFF);color:var(--c)}
.qc h3{font-size:17px;font-weight:700;margin-bottom:6px}
.qc p{font-size:14px;color:var(--text-2);line-height:1.5;margin-bottom:12px}
.qc .cta{font-size:14px;font-weight:700;color:var(--c);display:inline-flex;align-items:center;gap:6px}
.qc code{font-family:var(--mono);font-size:12.5px;background:var(--bg-2);padding:2px 6px;border-radius:6px}
.wrap{max-width:1200px;margin:0 auto;padding:40px 24px 90px;display:grid;grid-template-columns:280px 1fr;gap:44px;align-items:start}
.side{position:sticky;top:104px;display:flex;flex-direction:column;gap:6px}
.side-t{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1.2px;color:var(--text-3);padding:0 12px 6px}
.tab{display:flex;gap:12px;align-items:flex-start;text-decoration:none;color:var(--text-2);padding:12px;border-radius:14px;border:1px solid transparent;transition:background .2s}
.tab i{width:20px;text-align:center;margin-top:3px;color:var(--text-3)}
.tab strong{display:block;font-size:15px;font-weight:600;color:var(--text)}.tab em{font-style:normal;font-size:12.5px;color:var(--text-3);line-height:1.4}
.tab:hover{background:var(--bg-2)}
.tab.on{background:color-mix(in srgb,var(--c) 8%,#FFF);border-color:color-mix(in srgb,var(--c) 30%,#FFF)}.tab.on i{color:var(--c)}
.side .help{margin-top:14px;padding:14px;border-radius:14px;background:rgba(201,169,98,.1);border:1px solid rgba(201,169,98,.35);font-size:13px;color:var(--text-2);line-height:1.5}
.side .help a{color:#8a6d2b;font-weight:700;text-decoration:none}
main{min-width:0}
.doc-head{margin-bottom:18px}
.doc-head h1{font-size:36px;font-weight:900;letter-spacing:-.03em;line-height:1.1;margin-bottom:10px}
.doc-meta{display:flex;gap:16px;align-items:center;font-size:13px;color:var(--text-3)}
.doc-meta a{color:var(--blue);text-decoration:none;font-weight:600}
.on-page{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 26px;padding:14px;border:1px solid var(--border-2);border-radius:14px;background:#FFF}
.on-page a{font-size:12.5px;font-weight:600;color:var(--text-2);text-decoration:none;background:var(--bg-2);border-radius:980px;padding:5px 11px}
.on-page a:hover{color:var(--blue)}
.md{font-size:15.5px;line-height:1.7;color:#222}
.md h2{font-size:26px;font-weight:900;letter-spacing:-.025em;line-height:1.2;margin:44px 0 12px;padding-top:12px;border-top:1px solid var(--border)}
.md h3{font-size:18px;font-weight:700;margin:28px 0 8px;color:var(--purple)}
.md p{margin:0 0 12px}
.md a{color:var(--blue);text-decoration:none;font-weight:600}.md a:hover{text-decoration:underline}
.md ul,.md ol{margin:0 0 14px 22px}.md li{margin-bottom:5px}.md li>ul{margin-top:5px}
.md li.todo{list-style:none;margin-left:-22px;display:flex;gap:10px;align-items:flex-start}
.md .box{flex-shrink:0;width:16px;height:16px;border:1.5px solid var(--border-2);border-radius:4px;margin-top:5px;background:#FFF}
.md code{font-family:var(--mono);font-size:13px;background:var(--bg-2);border:1px solid var(--border);padding:1px 6px;border-radius:6px;color:#7A4B00;word-break:break-word}
.md pre{background:#0F1420;color:#E6EDF3;border-radius:14px;padding:18px 20px;overflow:auto;margin:12px 0 18px;font-size:13px;line-height:1.55;border:1px solid rgba(255,255,255,.06)}
.md pre code{background:none;border:none;padding:0;color:inherit;font-size:inherit}
.md table{width:100%;border-collapse:separate;border-spacing:0;border:1px solid var(--border-2);border-radius:14px;overflow:hidden;margin:12px 0 20px;font-size:14px;display:block;overflow-x:auto}
.md thead th{background:var(--bg-2);text-align:left;padding:10px 14px;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1.1px;color:var(--text-3);white-space:nowrap}
.md td{padding:11px 14px;border-top:1px solid var(--border);vertical-align:top;line-height:1.5;color:var(--text-2);min-width:120px}
.md td:first-child{color:var(--text);font-weight:600}
.md tr:hover td{background:#FCFCFD}
.md table.wide{font-size:13px}.md table.wide td{min-width:92px;padding:9px 10px}.md table.wide thead th{padding:8px 10px}
.md blockquote{border-left:3px solid var(--gold);background:rgba(201,169,98,.1);padding:12px 16px;border-radius:10px;margin:12px 0 18px;color:#222}
.md blockquote p:last-child{margin:0}
.md hr{border:none;border-top:1px solid var(--border);margin:30px 0}
.md strong{font-weight:700;color:var(--text)}
footer{border-top:1px solid var(--border);background:var(--bg-2)}
.ft-inner{max-width:1200px;margin:0 auto;padding:40px 24px;display:flex;flex-wrap:wrap;justify-content:space-between;gap:16px;align-items:center}
.ft-copy{font-size:12px;color:var(--text-3)}
.ft-links{display:flex;gap:18px;flex-wrap:wrap}.ft-links a{font-size:13px;color:var(--text-3);text-decoration:none}.ft-links a:hover{color:var(--blue)}
@media(max-width:1000px){.wrap{grid-template-columns:1fr;gap:20px}.side{position:static;flex-direction:row;flex-wrap:wrap}.side-t,.side .help,.tab em{display:none}.tab{padding:9px 14px;border:1px solid var(--border-2);border-radius:980px;align-items:center}.tab i{margin:0}.quick{grid-template-columns:1fr}}
@media(max-width:768px){.hero{padding:110px 18px 28px}.hero h1{font-size:30px}.hero p.lead{font-size:15.5px}.wrap{padding:0 14px 60px}.logo img{height:56px}.nav-cta .btn-sign{display:none}.doc-head h1{font-size:27px}.md h2{font-size:22px}.md pre{border-radius:10px;padding:14px}}
</style>
</head>
<body>
<nav class="top">
  <div class="nav-inner">
    <a href="/" class="logo"><img src="/logo.png" alt="I'm On Social"/></a>
    <div class="nav-cta">
      <a href="/help/" class="btn-sign">Help Center</a>
      <a href="https://app.imonsocial.com" class="btn-sign">Sign In</a>
      <a href="/demo" class="btn-demo">Book a Demo</a>
    </div>
  </div>
</nav>
<section class="hero">
  <div class="hero-in">
    <div class="sec-tag" style="color:var(--purple)"><i class="fa-solid fa-terminal"></i> Developers</div>
    <h1>Build on I'm On Social.</h1>
    <p class="lead">An open REST API and signed webhooks for every customer, text, call, note, task and sold record in a store. Connect your CRM, DMS, marketing stack or automation tool. No partnership paperwork: a dealership admin hands you a key and you are live.</p>
    <div class="quick">
      <a class="qc" style="--c:var(--green)" href="https://app.imonsocial.com/api/public/reference" target="_blank" rel="noopener" data-testid="dev-console-btn"><div class="ico"><i class="fa-solid fa-play"></i></div><h3>Try it live</h3><p>Interactive console. Paste your key under <strong>Authorize</strong> and run real calls against your store.</p><span class="cta">Open API console <i class="fa-solid fa-arrow-right"></i></span></a>
      <a class="qc" style="--c:var(--blue)" href="https://app.imonsocial.com/api/public/openapi-v1.json" target="_blank" rel="noopener" data-testid="dev-openapi-btn"><div class="ico"><i class="fa-regular fa-file-code"></i></div><h3>OpenAPI 3 schema</h3><p>Import into Postman or Insomnia, or generate a client in any language.</p><span class="cta"><code>openapi-v1.json</code> <i class="fa-solid fa-arrow-right"></i></span></a>
      <a class="qc" style="--c:var(--gold)" href="https://app.imonsocial.com" data-testid="dev-key-btn"><div class="ico"><i class="fa-solid fa-key"></i></div><h3>Get an API key</h3><p>A dealership admin creates one in the app: <strong>Tools, Integrations, API Keys</strong>. One key = one store; ask for an organization key for a group.</p><span class="cta">Sign in to the app <i class="fa-solid fa-arrow-right"></i></span></a>
    </div>
  </div>
</section>
<div class="wrap">
  <aside class="side">
    <div class="side-t">Documentation</div>
    {{TABS}}
    <div class="help"><strong>Need a sandbox store, an organization key, or an engineer on a call?</strong><br>Email <a href="mailto:support@imonsocial.com">support@imonsocial.com</a> with your company, the system you are connecting and the dealership you are integrating for.</div>
  </aside>
  <main id="docs">{{DOCS}}</main>
</div>
<footer>
  <div class="ft-inner">
    <span class="ft-copy">&copy; {{YEAR}} I'm On Social. Powered by VI Ventures Group LLC.</span>
    <div class="ft-links"><a href="/">Home</a><a href="/platform/">The Full Platform</a><a href="/help/">Help Center</a><a href="/pricing/">Pricing</a><a href="/privacy/">Privacy</a><a href="/terms/">Terms</a><a href="https://app.imonsocial.com">Sign In</a></div>
  </div>
</footer>
<script>
(function(){
  var sc=function(){document.querySelector('nav.top').classList.toggle('scrolled',scrollY>40)};addEventListener('scroll',sc);sc();
  var tabs=[].slice.call(document.querySelectorAll('.tab')),docs=[].slice.call(document.querySelectorAll('.doc'));
  function show(slug,push){
    if(!docs.some(function(d){return d.dataset.slug===slug}))slug=docs[0].dataset.slug;
    docs.forEach(function(d){d.hidden=d.dataset.slug!==slug});
    tabs.forEach(function(t){t.classList.toggle('on',t.dataset.slug===slug)});
    if(push){history.pushState(null,'','?doc='+slug+location.hash)}
  }
  function fromUrl(){
    var q=new URLSearchParams(location.search).get('doc');
    var h=location.hash.slice(1);
    if(!q&&h&&h.indexOf('--')>0)q=h.split('--')[0];
    show(q||docs[0].dataset.slug,false);
    if(h){var el=document.getElementById(h);if(el)setTimeout(function(){el.scrollIntoView()},0)}
  }
  tabs.forEach(function(t){t.addEventListener('click',function(e){e.preventDefault();show(t.dataset.slug,true);document.getElementById('docs').scrollIntoView({behavior:'smooth'})})});
  // links inside a doc that point at another doc (?doc=slug#anchor) switch without a reload
  document.getElementById('docs').addEventListener('click',function(e){
    var a=e.target.closest('a');if(!a)return;
    var href=a.getAttribute('href')||'';
    var m=href.match(/^(?:https?:\/\/(?:www\.)?imonsocial\.com)?\/developers\/?\?doc=([a-z0-9-]+)(#.*)?$/);
    if(m){e.preventDefault();show(m[1],true);if(m[2]){location.hash=m[2]}else{document.getElementById('docs').scrollIntoView()}}
  });
  addEventListener('popstate',fromUrl);
  fromUrl();
})();
</script>
</body>
</html>
'''

if __name__ == "__main__":
    out = os.path.join(HERE, "build", "developers", "index.html")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(render())
    print("wrote", out, os.path.getsize(out), "bytes")
