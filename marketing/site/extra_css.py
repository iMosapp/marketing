"""Page CSS for extra.py (feature sheet + platform overview), on top of assets/site.css tokens."""

FS_CSS = """
.fs-hero{padding:64px 0 40px}
.fs-hero h1{max-width:15em}
.fs-hero .lead{max-width:44em}
.fs-meta{display:flex;flex-wrap:wrap;align-items:center;gap:10px;margin-top:32px}
.fs-pill{display:inline-flex;align-items:center;height:36px;padding:0 16px;border-radius:999px;border:1px solid var(--line);background:var(--white);font-size:.86rem;font-weight:600;color:var(--text-2)}
.fs-pill.gold{background:var(--gold-tint);border-color:#E9DDBF;color:var(--gold-deep)}
.fs-legend{display:flex;flex-wrap:wrap;align-items:center;gap:6px;margin-left:auto;font-size:.84rem;color:var(--muted)}
.fs-print{margin-left:8px}
.fs-aud{display:inline-flex;align-items:center;gap:6px;padding:3px 10px;border-radius:999px;background:var(--bg-2);border:1px solid var(--line);font-size:.72rem;font-weight:700;color:var(--text-2);white-space:nowrap}
.fs-aud::before{content:"";width:7px;height:7px;border-radius:50%;background:var(--c)}
.fs-why-sec{padding:8px 0 24px}
.fs-why{display:grid;grid-template-columns:1.3fr .9fr;gap:48px;align-items:center;padding:44px 48px;border-radius:30px;background:var(--gold-tint);border:1px solid #E9DDBF}
.fs-why h2{font-size:clamp(1.6rem,1.2rem + 1.2vw,2.3rem);margin-bottom:16px}
.fs-why h2 em{font-style:normal;color:var(--gold-deep)}
.fs-why p{color:var(--text-2)}
.fs-why p + p{margin-top:12px}
.fs-pitch{padding:8px 0 8px 28px;border-left:3px solid var(--gold)}
.fs-pitch strong{display:block;font-size:.78rem;letter-spacing:.2em;color:var(--gold-deep);margin-bottom:10px}
.fs-pitch p{font-family:var(--font-h);font-weight:700;font-size:clamp(1.3rem,1rem + .8vw,1.7rem);line-height:1.3;color:var(--ink)}
.fs-pitch span{display:block;margin-top:12px;font-size:.74rem;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:var(--muted)}
.fs-body{padding-top:64px}
.fs-grid{display:grid;grid-template-columns:270px minmax(0,1fr);gap:48px;align-items:start}
.fs-toc{position:sticky;top:calc(var(--header-h) + 24px);display:flex;flex-direction:column;gap:2px;padding:12px;border:1px solid var(--line);border-radius:22px;background:var(--white)}
.fs-toc-t{font-size:.72rem;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);padding:8px 12px 6px}
.fs-toc a{display:flex;align-items:center;gap:10px;padding:9px 12px;border-radius:12px;font-size:.88rem;font-weight:500;line-height:1.3;color:var(--text-2);text-decoration:none;transition:background-color .2s,color .2s}
.fs-toc a:hover{background:var(--gold-tint);color:var(--ink)}
.fs-toc a em{margin-left:auto;font-style:normal;font-size:.75rem;font-weight:700;color:var(--gold-deep)}
.fs-grp{scroll-margin-top:calc(var(--header-h) + 24px)}
.fs-grp + .fs-grp{margin-top:80px}
.fs-grp-head{max-width:760px;margin-bottom:24px}
.fs-grp-head .overline{margin-bottom:10px}
.fs-grp-head h2{font-size:clamp(1.55rem,1.15rem + 1.2vw,2.2rem)}
.fs-grp-head .muted{margin-top:10px}
.fs-rows{border:1px solid var(--line);border-radius:24px;overflow:hidden;background:var(--white)}
.fs-row{display:grid;grid-template-columns:26% minmax(0,1fr) 31%;border-top:1px solid var(--line);transition:background-color .2s}
.fs-row > div{padding:20px 22px;font-size:.93rem;line-height:1.6;color:var(--text-2)}
.fs-row:not(.fs-hdr):hover{background:#FEFDFB}
.fs-hdr{border-top:0;background:var(--bg-2)}
.fs-hdr > div{padding:12px 22px;font-size:.7rem;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:var(--muted)}
.fs-name{border-right:1px solid var(--line)}
.fs-name h3{font-size:1.06rem;line-height:1.3;margin:4px 0 10px;color:var(--ink)}
.fs-num{font-family:var(--font-h);font-weight:800;font-size:.8rem;letter-spacing:.08em;color:var(--gold-deep)}
.fs-auds{display:flex;flex-wrap:wrap;gap:5px}
.fs-whyc{background:#FBF8F1;border-left:1px solid var(--line);color:var(--ink) !important}
.fs-lbl{display:none}
@media (max-width:960px){
  .fs-grid{grid-template-columns:1fr;gap:28px}
  .fs-toc{position:static;flex-direction:row;flex-wrap:wrap;gap:8px;padding:0;border:0;background:none}
  .fs-toc-t,.fs-toc a em{display:none}
  .fs-toc a{padding:8px 14px;border:1px solid var(--line);border-radius:999px;background:var(--white)}
  .fs-why{grid-template-columns:1fr;gap:28px;padding:32px 28px}
  .fs-legend{margin-left:0}
}
@media (max-width:720px){
  .fs-hero{padding:40px 0 24px}
  .fs-row{grid-template-columns:1fr}
  .fs-hdr{display:none}
  .fs-name{border-right:0;padding-bottom:4px !important}
  .fs-whyc{border-left:0;border-top:1px dashed var(--line)}
  .fs-lbl{display:block;font-size:.68rem;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);margin-bottom:4px}
}
@media print{
  .site-header,.site-footer,.fs-toc,.fs-print,.final,.modal,.sheet,.imosw-root,.skip{display:none !important}
  body::after{display:none}
  body{background:#fff;font-size:11px}
  .js .reveal{opacity:1 !important;transform:none !important}
  .fs-hero{padding:0 0 12px}.fs-hero h1{font-size:24px}.fs-hero .lead{font-size:12px;margin-top:8px}
  .fs-why{padding:14px 18px;gap:16px;border-radius:10px}.fs-why h2{font-size:16px}.fs-why p{font-size:10.5px}.fs-pitch p{font-size:13px}
  .section{padding:0}.fs-body{padding-top:16px}.fs-grid{display:block}.fs-grp + .fs-grp{margin-top:18px}.fs-grp-head h2{font-size:16px}
  .fs-rows{border-radius:6px}.fs-row{break-inside:avoid}.fs-row > div{padding:7px 10px;font-size:10px;line-height:1.4}.fs-name h3{font-size:11px;margin:0 0 4px}
}
"""

OV_CSS = """
.ov-hero{padding:72px 0 112px}
.ov-hero-grid{display:grid;grid-template-columns:1.2fr .8fr;gap:56px;align-items:center}
.ov-hero h1{font-size:clamp(2.5rem,1.4rem + 3.4vw,4.4rem);max-width:12em}
.ov-hero .lead b,.section-head .muted b,.story-text b,.ov-ask-lead b{color:var(--ink);font-weight:700}
.ov-glance{background:var(--white);border:1px solid var(--line);border-radius:28px;padding:32px 30px;box-shadow:var(--shadow)}
.ov-glance ul{list-style:none;margin:6px 0 0;padding:0}
.ov-glance li{display:flex;align-items:baseline;gap:14px;padding:12px 0;border-top:1px solid var(--line);color:var(--text-2);font-size:.95rem}
.ov-glance li:first-child{border-top:0}
.ov-glance li b{min-width:4.2em;font-family:var(--font-h);font-weight:800;font-size:1.45rem;letter-spacing:-.02em;color:var(--ink)}
.ov-tag{margin-top:16px;font-weight:700;color:var(--gold-deep)}
.ov-engine{display:grid;grid-template-columns:1.05fr .95fr;gap:72px;align-items:center}
.ov-chain{display:flex;flex-wrap:wrap;gap:8px;margin-top:28px}
.ov-chain span{padding:9px 16px;border-radius:999px;background:var(--white);border:1px solid var(--line);font-size:.9rem;font-weight:600}
.ov-chain em{font-style:normal;color:var(--gold-deep);align-self:center}
.ov-fly{margin-top:30px;padding-left:22px;border-left:3px solid var(--gold);font-family:var(--font-h);font-weight:700;font-size:clamp(1.3rem,1rem + 1vw,1.8rem);line-height:1.25}
.ov-ring{position:relative;width:min(100%,500px);aspect-ratio:1;margin:0 auto;container-type:inline-size}
.ov-ring::before{content:"";position:absolute;inset:4%;border-radius:50%;background:radial-gradient(closest-side,rgba(201,169,98,.22),rgba(201,169,98,0))}
.ov-loop{position:absolute;inset:11%;border:1.5px dashed rgba(201,169,98,.6);border-radius:50%;animation:ovspin 80s linear infinite}
@keyframes ovspin{to{transform:rotate(360deg)}}
.ov-hub{position:absolute;left:50%;top:50%;width:46%;aspect-ratio:1;transform:translate(-50%,-50%);border-radius:50%;background:var(--ink);display:grid;place-items:center;text-align:center;padding:18px;
  box-shadow:0 0 0 10px rgba(201,169,98,.12),var(--shadow-phone)}
.ov-hub b{font-family:var(--font-h);font-weight:800;font-size:clamp(1rem,.8rem + .6vw,1.35rem);line-height:1.15;color:var(--gold)}
.ov-hub small{display:block;margin-top:8px;color:var(--d-text-2);font-size:.68rem;letter-spacing:.16em;text-transform:uppercase}
.ov-node{--r:44cqw;position:absolute;left:50%;top:50%;width:122px;margin:-26px 0 0 -61px;transform:rotate(var(--a)) translate(0,calc(var(--r) * -1)) rotate(calc(var(--a) * -1));
  background:var(--white);border:1px solid var(--line);border-radius:999px;padding:10px;text-align:center;font-weight:700;font-size:.78rem;letter-spacing:.06em;text-transform:uppercase;box-shadow:0 10px 24px -16px rgba(11,11,15,.35)}
.ov-node i{display:block;font-style:normal;font-size:.64rem;letter-spacing:.12em;color:var(--gold-deep);margin-bottom:2px}
.ov-metrics{display:grid;grid-template-columns:repeat(5,1fr);gap:16px;margin-top:56px}
.ov-metric{position:relative;overflow:hidden;padding:28px 24px 24px;border-radius:24px;background:var(--ink-2);border:1px solid var(--line-dark)}
.ov-metric::after{content:"";position:absolute;right:-40px;top:-40px;width:130px;height:130px;border-radius:50%;background:radial-gradient(circle,rgba(201,169,98,.25),transparent 70%)}
.ov-n{font-family:var(--font-h);font-weight:800;font-size:clamp(2.2rem,1.4rem + 2vw,3.3rem);line-height:1;letter-spacing:-.03em;color:var(--gold);font-variant-numeric:tabular-nums}
.ov-l{margin-top:12px;font-size:.9rem;font-weight:600;color:var(--d-text-2)}
.ov-foot{margin-top:22px;font-size:.84rem;color:var(--d-text-2)}
.ov-appendix{display:none}
.ov-costs{display:grid;grid-template-columns:repeat(4,1fr);gap:18px}
.ov-cost{padding:30px 26px;border-radius:26px;background:var(--white);border:1px solid var(--line);transition:transform .3s var(--ease),box-shadow .3s var(--ease),border-color .3s}
.ov-cost:hover{transform:translateY(-4px);border-color:var(--gold);box-shadow:var(--shadow)}
.ov-v{font-family:var(--font-h);font-weight:800;font-size:clamp(1.9rem,1.3rem + 1.4vw,2.6rem);line-height:1;letter-spacing:-.02em}
.ov-t{margin-top:12px;font-size:.74rem;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:var(--gold-deep)}
.ov-cost p:last-child{margin-top:10px;color:var(--text-2);font-size:.93rem}
.ov-complex{grid-template-columns:1fr 1fr;gap:14px 40px;margin-top:48px}
.ov-complex li{color:var(--text-2)}
.ov-complex b{color:var(--ink)}
.ov-versus{display:grid;grid-template-columns:1fr auto 1fr;gap:20px;align-items:center;margin-top:48px}
.ov-side{padding:24px 28px;border-radius:22px;background:var(--white);border:1px solid var(--line)}
.ov-side .ov-t{margin:0 0 8px}
.ov-side span{font-family:var(--font-h);font-weight:700;font-size:1.3rem}
.ov-side.live{background:var(--gold-tint);border-color:#E9DDBF}
.ov-vs{font-weight:800;font-size:.8rem;letter-spacing:.2em;color:var(--muted)}
.ov-note{margin-top:24px;font-size:.84rem;color:var(--muted);max-width:60em}
.ov-bar{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-top:36px}
.ov-bar div{padding:22px;border-radius:20px;background:var(--white);border:1px solid var(--line);font-size:.9rem;color:var(--text-2)}
.ov-bar b{display:block;font-family:var(--font-h);font-weight:800;font-size:2rem;line-height:1;color:var(--ink);margin-bottom:8px}
.ov-uses{display:grid;grid-template-columns:repeat(5,1fr);gap:16px}
.ov-uses.four{grid-template-columns:repeat(4,1fr);margin-top:44px}
.ov-use h3{font-size:1.12rem;margin:12px 0 8px}
.ov-idx{font-family:var(--font-h);font-weight:800;font-size:.9rem;letter-spacing:.08em;color:var(--gold-deep)}
.ov-risk{display:inline-flex;align-items:center;gap:12px;margin-top:36px;padding:12px 20px;border-radius:999px;background:var(--gold-tint);border:1px solid #E9DDBF;font-weight:600;color:var(--gold-deep)}
.ov-risk i{width:8px;height:8px;border-radius:50%;background:var(--gold);box-shadow:0 0 0 4px rgba(201,169,98,.25)}
.ov-gold{color:var(--gold)}
.ov-close h2{max-width:16em}
.ov-ctas{justify-content:center;margin-top:0}
.ov-ask .ov-ctas{justify-content:flex-start;margin-top:40px}
.ov-btn-light{background:transparent;color:#fff;border-color:rgba(255,255,255,.35)}
.ov-btn-light:hover{background:#fff;color:var(--ink);border-color:#fff;transform:translateY(-2px)}
.ov-ask h2{max-width:22em}
.ov-ask-lead{margin-top:22px;font-size:1.12rem;color:var(--d-text-2);max-width:40em}
.ov-ask-lead b{color:#fff}
.ov-ask .ov-use{background:var(--ink-2);border-color:var(--line-dark)}
.ov-ask .ov-use p{color:var(--d-text-2)}
.ov-ask .ov-idx{color:var(--gold)}
.ov-quote{margin-top:44px;padding-left:24px;border-left:3px solid var(--gold);font-family:var(--font-h);font-weight:700;font-size:clamp(1.3rem,1rem + 1.1vw,1.9rem);line-height:1.3;max-width:34em}
.ov-quote span{color:var(--gold)}
.ov-fine{margin:12px 0 0;text-align:center}
@media (max-width:1080px){
  .ov-metrics{grid-template-columns:repeat(3,1fr)}
  .ov-costs,.ov-uses.four{grid-template-columns:1fr 1fr}
  .ov-uses{grid-template-columns:repeat(3,1fr)}
}
@media (max-width:960px){
  .ov-hero-grid,.ov-engine{grid-template-columns:1fr;gap:48px}
  .ov-complex{grid-template-columns:1fr}
}
@media (max-width:720px){
  .ov-hero{padding:44px 0 80px}
  .ov-metrics,.ov-uses{grid-template-columns:1fr 1fr}
  .ov-costs,.ov-uses.four,.ov-bar{grid-template-columns:1fr}
  .ov-versus{grid-template-columns:1fr;gap:10px}
  .ov-vs{text-align:center}
  .ov-node{width:96px;margin:-22px 0 0 -48px;font-size:.66rem;padding:8px 6px}
  .ov-ctas .btn{width:100%}
}
@media print{
  .site-header,.site-footer,.modal,.sheet,.imosw-root,.skip,.ov-ctas,.cta-row{display:none !important}
  body::after{display:none}
  .js .reveal{opacity:1 !important;transform:none !important}
  .section,.band{padding:28px 0;break-inside:avoid}
  .band-ink{-webkit-print-color-adjust:exact;print-color-adjust:exact}
  .ov-appendix{display:block}
  .ov-loop{animation:none}
}
"""
