"""
Public rep pages, server-rendered (same look as the shared-contact page):
  GET /api/card/{user_id}   Digital card  (contact-first, short bio, top reviews)
  GET /api/p/{user_id}      Landing page  (full story from the rep's bio + Virtual Assistant persona, reviews, review + referral forms)
The Expo routes /card/{id} and /p/{id} redirect here, so every existing link, QR and vCard keeps working.
"""
import html
import json
import os
from datetime import datetime, timezone, timedelta
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from routers.database import get_db
from routers.contact_share import _fmt_phone, _public_base
from utils.image_urls import resolve_user_photo, resolve_store_logo

router = APIRouter(tags=["public-pages"])

SOCIALS = [
    ("facebook", "Facebook"), ("instagram", "Instagram"), ("linkedin", "LinkedIn"),
    ("twitter", "X"), ("x", "X"), ("tiktok", "TikTok"), ("youtube", "YouTube"), ("website", "Website"),
]


def _abs(u: Optional[str]) -> str:
    if not u:
        return ""
    return u if u.startswith("http") else f"{_public_base()}{u}"


def _list(v) -> list:
    if isinstance(v, list):
        return [str(x).strip() for x in v if str(x).strip()]
    if isinstance(v, str) and v.strip():
        return [x.strip() for x in v.replace("\n", ",").split(",") if x.strip()]
    return []


async def _bundle(db, user_id: str, review_limit: int) -> Optional[dict]:
    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)}, {"password": 0})
    except Exception:
        return None
    if not user:
        return None
    store = None
    if user.get("store_id"):
        try:
            store = await db.stores.find_one({"_id": ObjectId(user["store_id"])})
        except Exception:
            store = None
    persona = user.get("persona") or {}
    reviews = await db.customer_feedback.find({
        "salesperson_id": user_id, "approved": True, "rating": {"$gte": 4},
    }).sort("created_at", -1).limit(review_limit).to_list(review_limit)
    total_reviews = await db.customer_feedback.count_documents({"salesperson_id": user_id, "approved": True, "rating": {"$gte": 4}})
    return {"user": user, "store": store, "persona": persona, "reviews": reviews, "total_reviews": total_reviews}


async def _track(db, page_type: str, user_id: str, request: Request):
    """Card-scan counter, contact activity (when the short link passed cid) and SEO visit stats."""
    if request.query_params.get("self_preview"):
        return
    try:
        from routers.digital_card import _record_card_scan
        await _record_card_scan(db, user_id, request)
    except Exception:
        pass
    cid = request.query_params.get("cid")
    if cid:
        try:
            from utils.contact_activity import log_customer_activity
            event = "digital_card_viewed" if page_type == "card" else "landing_page_viewed"
            recent = await db.contact_events.find_one({
                "contact_id": cid, "event_type": event,
                "timestamp": {"$gte": datetime.now(timezone.utc) - timedelta(hours=1)},
            })
            if not recent:
                await log_customer_activity(
                    user_id=user_id, contact_id=cid, event_type=event,
                    title="Viewed Digital Card" if page_type == "card" else "Viewed Landing Page",
                    description="Contact opened your " + ("digital card" if page_type == "card" else "landing page"),
                    icon="eye", color="#C9A962", category="customer_activity",
                    metadata={"user_id": user_id, "contact_id": cid},
                )
        except Exception:
            pass
    try:
        ua = request.headers.get("user-agent", "")
        if not any(b in ua.lower() for b in ("bot", "crawler", "spider", "preview", "facebookexternalhit", "slack", "whatsapp")):
            from routers.seo import track_page_visit
            q = request.query_params
            await track_page_visit({
                "page_type": page_type, "reference_id": user_id,
                "utm_source": q.get("utm_source", "direct"), "utm_medium": q.get("utm_medium", ""),
                "utm_campaign": q.get("utm_campaign", ""), "referrer": request.headers.get("referer", ""), "user_agent": ua,
            })
    except Exception:
        pass


CSS = """
:root{--bg:#0B0B0C;--card:#151517;--line:#26262A;--text:#F4F1EA;--muted:#9A9A9F;--gold:#C9A962;--green:#34C759}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:16px/1.45 -apple-system,BlinkMacSystemFont,"SF Pro Text",Segoe UI,Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased}
.wrap{max-width:560px;margin:0 auto;padding:28px 18px 48px}
.hero{display:flex;flex-direction:column;align-items:center;text-align:center;gap:10px;padding:28px 18px 22px;background:var(--card);border:1px solid var(--line);border-radius:22px;position:relative;overflow:hidden}
.hero:before{content:"";position:absolute;inset:0 0 auto 0;height:96px;background:linear-gradient(180deg,rgba(201,169,98,.18),rgba(201,169,98,0))}
.avatar{width:124px;height:124px;border-radius:62px;object-fit:cover;border:3px solid var(--gold);background:#222;position:relative}
.initials{display:flex;align-items:center;justify-content:center;font-size:40px;font-weight:800;color:var(--gold)}
h1{margin:6px 0 0;font-size:26px;font-weight:800;letter-spacing:-.3px}
.sub{color:var(--muted);font-size:15px;margin-top:-4px}.sub b{color:var(--text);font-weight:600}
.storeline{display:flex;align-items:center;gap:8px;color:var(--muted);font-size:13px;margin-top:2px}.storeline img{width:22px;height:22px;border-radius:6px;object-fit:cover;background:#222}
.actions{display:flex;flex-wrap:wrap;gap:8px;justify-content:center;margin-top:10px}
.btn{display:inline-block;padding:11px 16px;border-radius:999px;border:1px solid var(--line);color:var(--text);text-decoration:none;font-weight:700;font-size:14px;background:#1D1D20;transition:transform .12s,background-color .12s;cursor:pointer;font-family:inherit}
.btn:hover{transform:translateY(-1px);background:#242428}.btn.gold{background:var(--gold);color:#111;border-color:var(--gold)}.btn.wide{display:block;text-align:center;width:100%}
section{margin-top:14px;background:var(--card);border:1px solid var(--line);border-radius:18px;padding:16px 18px}
h3{margin:0 0 10px;font-size:12px;letter-spacing:1.2px;text-transform:uppercase;color:var(--gold);font-weight:800}h3 small{color:var(--muted);font-weight:600;letter-spacing:0;text-transform:none;margin-left:8px}
.row{display:flex;justify-content:space-between;gap:14px;padding:9px 0;border-top:1px solid var(--line)}.row:first-of-type{border-top:0}
.lbl{color:var(--muted);font-size:14px;flex:0 0 auto}.val{text-align:right;word-break:break-word}.val a{color:var(--text);text-decoration:none;border-bottom:1px dashed #3a3a40}
.bio{margin:0;color:#D8D5CC;white-space:pre-wrap}.more{display:inline-block;margin-top:10px;color:var(--gold);font-weight:700;text-decoration:none}
.tags{display:flex;flex-wrap:wrap;gap:6px;margin-top:12px}.tag{padding:5px 10px;border-radius:999px;background:#1F1C14;border:1px solid #3C3320;color:var(--gold);font-size:12px;font-weight:700}
.facts{margin:0;padding-left:18px;color:#D8D5CC}.facts li{margin:4px 0}
blockquote{margin:12px 0 0;padding:12px 14px;border-left:3px solid var(--gold);background:#1A1813;border-radius:0 12px 12px 0;color:#E9E4D6;font-style:italic}
.pills{display:flex;flex-wrap:wrap;gap:8px}.pill{display:inline-flex;align-items:center;gap:6px;padding:9px 14px;border-radius:999px;border:1px solid var(--line);background:#1D1D20;color:var(--text);text-decoration:none;font-size:13px;font-weight:700}
.review{padding:12px 0;border-top:1px solid var(--line)}.review:first-of-type{border-top:0}.review .who{display:flex;justify-content:space-between;align-items:center;gap:10px;font-weight:700}
.stars{color:#FFD60A;letter-spacing:1px;font-size:13px}.review p{margin:6px 0 0;color:#D8D5CC}.review img{margin-top:10px;width:100%;max-height:260px;object-fit:cover;border-radius:12px}
.links .row{align-items:center}.links .val{color:var(--gold);font-weight:700}.links .val a{color:var(--gold);border:0}
form{display:flex;flex-direction:column;gap:10px}label{font-size:12px;color:var(--muted);font-weight:700;letter-spacing:.4px}
input,textarea{width:100%;background:#0F0F11;border:1px solid var(--line);border-radius:12px;color:var(--text);padding:12px;font:inherit;font-size:15px}textarea{min-height:90px;resize:vertical}
.rate{display:flex;gap:6px}.rate input{display:none}.rate label{font-size:28px;color:#3a3a40;cursor:pointer;transition:color .12s}
.ok{display:none;color:var(--green);font-weight:700;padding:8px 0}.err{display:none;color:#FF6B6B;font-weight:700}
details summary{cursor:pointer;list-style:none;display:flex;justify-content:space-between;align-items:center;font-weight:700}details summary::-webkit-details-marker{display:none}details summary:after{content:"+";color:var(--gold);font-size:20px}details[open] summary:after{content:"–"}
details form{margin-top:14px}
footer{margin-top:22px;text-align:center;color:var(--muted);font-size:13px}footer a{color:var(--gold);text-decoration:none;font-weight:700}
"""

JS = """
function star(){var f=document.querySelector('.rate');if(!f)return;var paint=function(n){f.querySelectorAll('label').forEach(function(l,idx){l.style.color=idx<n?'#FFD60A':'#3a3a40'})};f.querySelectorAll('input').forEach(function(i){i.addEventListener('change',function(){paint(Number(i.value))});if(i.checked)paint(Number(i.value))})}
function post(form,url,asJson){var btn=form.querySelector('button'),ok=form.querySelector('.ok'),er=form.querySelector('.err');btn.disabled=true;btn.textContent='Sending…';er.style.display='none';
var fd=new FormData(form),opt={method:'POST'};if(asJson){var o={};fd.forEach(function(v,k){o[k]=v});opt.headers={'Content-Type':'application/json'};opt.body=JSON.stringify(o)}else{opt.body=fd}
fetch(url,opt).then(function(r){if(!r.ok)throw 0;return r.json()}).then(function(){form.querySelectorAll('input,textarea,button').forEach(function(x){x.style.display='none'});form.querySelectorAll('label').forEach(function(x){x.style.display='none'});ok.style.display='block'}).catch(function(){btn.disabled=false;btn.textContent='Try again';er.style.display='block'})}
document.addEventListener('DOMContentLoaded',function(){star();document.querySelectorAll('form[data-url]').forEach(function(f){f.addEventListener('submit',function(e){e.preventDefault();post(f,f.dataset.url,f.dataset.json==='1')})})});
"""


def _stars(n) -> str:
    try:
        n = max(1, min(5, int(n)))
    except Exception:
        n = 5
    return "★" * n + "☆" * (5 - n)


def build_page(b: dict, mode: str) -> str:
    e = html.escape
    u, s, p = b["user"], b["store"] or {}, b["persona"]
    uid = str(u["_id"])
    base = _public_base()
    name = u.get("name") or "Your salesperson"
    initials = "".join(x[0] for x in name.split()[:2]).upper() or "?"
    title = u.get("title") or p.get("professional_identity") or "Sales Professional"
    store_name = s.get("name") or u.get("company") or ""
    phone = u.get("mvpline_number") or u.get("twilio_number") or u.get("phone") or ""
    email = u.get("email") or ""
    photo_rel = resolve_user_photo(u) or ""
    photo_abs = _abs(photo_rel)
    logo = resolve_store_logo(s) if s else None
    bio = (p.get("bio") or u.get("bio") or "").strip()
    years = str(p.get("years_experience") or "").strip()
    hometown = (p.get("hometown") or "").strip()
    family = (p.get("family_info") or "").strip()
    motto = (p.get("personal_motto") or "").strip()
    hobbies, facts, specialties = _list(p.get("hobbies")), _list(p.get("fun_facts")), _list(p.get("specialties"))
    socials = {k: v for k, v in (u.get("social_links") or {}).items() if v}
    if u.get("website") and "website" not in socials:
        socials["website"] = u["website"]
    addr = ", ".join(x for x in [s.get("address"), s.get("city"), s.get("state")] if x) if s else ""
    if addr and s.get("zip_code"):
        addr += f" {s['zip_code']}"
    review_links = s.get("review_links") or {} if s else {}
    store_slug = s.get("slug") if s else None
    is_card = mode == "card"
    other = f"/api/p/{uid}" if is_card else f"/api/card/{uid}"

    def row(label, value, href=None):
        v = f'<a href="{e(href)}">{e(value)}</a>' if href else e(value)
        return f'<div class="row"><span class="lbl">{e(label)}</span><span class="val">{v}</span></div>'

    # --- hero
    actions = []
    if phone:
        actions.append(f'<a class="btn" href="tel:{e(phone)}">Call</a><a class="btn" href="sms:{e(phone)}">Text</a>')
    if email:
        actions.append(f'<a class="btn" href="mailto:{e(email)}">Email</a>')
    actions.append(f'<a class="btn gold" href="/api/profile/{uid}/vcard.vcf">Save to Contacts</a>')
    avatar = f'<img class="avatar" src="{e(photo_rel)}" alt="{e(name)}">' if photo_rel else f'<div class="avatar initials">{e(initials)}</div>'
    storeline = ""
    if store_name:
        logo_img = f'<img src="{e(logo)}" alt="">' if logo else ""
        storeline = f'<div class="storeline">{logo_img}<span>{e(store_name)}</span></div>'
    hero = f'<div class="hero">{avatar}<h1>{e(name)}</h1><div class="sub">{e(title)}</div>{storeline}<div class="actions">{"".join(actions)}</div></div>'

    sections = []

    # --- contact rows
    rows = ""
    if phone:
        rows += row("Mobile", _fmt_phone(phone), f"tel:{phone}")
    if email:
        rows += row("Email", email, f"mailto:{email}")
    if s.get("phone") and s.get("phone") != phone:
        rows += row("Store", _fmt_phone(s["phone"]), f"tel:{s['phone']}")
    if addr:
        rows += row("Address", addr, "https://maps.apple.com/?q=" + addr.replace(" ", "+"))
    if s.get("website"):
        rows += row("Website", s["website"].replace("https://", "").replace("http://", "").rstrip("/"), s["website"])
    if rows:
        sections.append(f"<section>{rows}</section>")

    # --- about (bio + quick facts chips)
    chips = []
    if years:
        chips.append(f"{e(years)} yrs in the business" if years.isdigit() else e(years))
    if hometown:
        chips.append(f"From {e(hometown)}")
    chips += [e(x) for x in specialties[:6]]
    def tags_html(items) -> str:
        return '<div class="tags">' + "".join(f'<span class="tag">{x}</span>' for x in items) + "</div>" if items else ""

    if bio or chips:
        text = bio
        more = ""
        if is_card and len(bio) > 260:
            cut = bio[:260].rsplit(" ", 1)[0]
            text, more = cut + "…", f'<a class="more" href="{e(other)}">Read my full story →</a>'
        sections.append(
            '<section><h3>About me</h3>'
            + (f'<p class="bio">{e(text)}</p>' if text else "")
            + more
            + tags_html(chips)
            + "</section>"
        )

    # --- landing only: get to know me
    if not is_card:
        know = ""
        if hometown:
            know += row("Hometown", hometown)
        if years:
            know += row("Experience", f"{years} years" if years.isdigit() else years)
        if family:
            know += row("Family", family)
        extras = ""
        if hobbies:
            extras += tags_html([e(h) for h in hobbies])
        if facts:
            extras += '<ul class="facts" style="margin-top:12px">' + "".join(f"<li>{e(f)}</li>" for f in facts) + "</ul>"
        if motto:
            extras += f"<blockquote>“{e(motto)}”</blockquote>"
        if know or extras:
            sections.append(f'<section><h3>Get to know me</h3>{know}{extras}</section>')

    # --- socials
    pills = ""
    seen = set()
    for key, label in SOCIALS:
        url = socials.get(key)
        if url and label not in seen:
            seen.add(label)
            href = url if url.startswith("http") else f"https://{url}"
            pills += f'<a class="pill" href="{e(href)}" target="_blank" rel="noopener">{e(label)}</a>'
    if pills:
        sections.append(f'<section><h3>Find me online</h3><div class="pills">{pills}</div></section>')

    # --- reviews
    revs = b["reviews"] if not is_card else b["reviews"][:3]
    if revs:
        items = ""
        for r in revs:
            photo = r.get("purchase_photo_url") if not is_card else None
            items += (
                f'<div class="review"><div class="who"><span>{e(r.get("customer_name") or "Happy customer")}</span><span class="stars">{_stars(r.get("rating"))}</span></div>'
                + (f'<p>“{e((r.get("text_review") or "").strip())}”</p>' if (r.get("text_review") or "").strip() else "")
                + (f'<img src="{e(photo)}" alt="" loading="lazy">' if photo and len(photo) < 2_000_000 else "")
                + "</div>"
            )
        count = b["total_reviews"]
        plural = "s" if count != 1 else ""
        more_rev = f'<a class="more" href="{e(other)}">See all {count} reviews →</a>' if is_card and count > 3 else ""
        sections.append(f'<section><h3>What customers say<small>{count} review{plural}</small></h3>{items}{more_rev}</section>')

    # --- links
    links = ""
    links += row("My showcase", "Customer photos & deliveries", f"{base}/showcase/{uid}")
    if p.get("scheduling_link"):
        links += row("Book a time", "Pick a slot that works for you", p["scheduling_link"])
    if is_card:
        links += row("More about me", "My full page", other)
    else:
        links += row("My digital card", "Quick contact card", other)
    for kl in _list(p.get("key_links"))[:4]:
        href = kl if kl.startswith("http") else f"https://{kl}"
        links += row("Link", kl.replace("https://", "").replace("http://", "").rstrip("/")[:40], href)
    review_target = None
    if review_links.get("google"):
        review_target = review_links["google"]
    elif store_slug:
        review_target = f"{base}/review/{store_slug}?sp={uid}"
    if is_card:
        links += row("Leave a review", "Had a great experience?", review_target or f"{other}#review")
    sections.append(f'<section class="links"><h3>Links</h3>{links}</section>')

    # --- landing only: review + referral forms
    if not is_card:
        rating_inputs = "".join(
            f'<input type="radio" id="r{i}" name="rating" value="{i}"{" checked" if i == 5 else ""}><label for="r{i}">★</label>' for i in range(1, 6)
        )
        google_note = f'<p style="margin:12px 0 0;text-align:center"><a class="more" href="{e(review_target)}" target="_blank" rel="noopener">Prefer Google? Review us there →</a></p>' if review_target else ""
        sections.append(
            f'<section id="review"><details><summary>Had a great experience? Leave a review</summary>'
            f'<form data-url="/api/p/review/{uid}">'
            '<label>Your name</label><input name="customer_name" required placeholder="First and last name">'
            '<label>Rating</label><div class="rate">' + rating_inputs
            + '</div><label>What stood out?</label><textarea name="text_review" placeholder="A sentence or two goes a long way"></textarea>'
            '<label>Phone (optional, so I can say thanks)</label><input name="customer_phone" type="tel" placeholder="(555) 555-5555">'
            '<button class="btn gold wide" type="submit">Submit review</button>'
            '<div class="ok">Thank you! Your review means a lot.</div><div class="err">Something went wrong. Please try again.</div>'
            + google_note
            + "</form></details></section>"
        )
        sections.append(
            f'<section id="refer"><details><summary>Know someone I could help?</summary>'
            f'<form data-url="/api/p/refer/{uid}" data-json="1">'
            '<label>Your name</label><input name="referrer_name" required placeholder="So I know who to thank">'
            '<label>Your phone</label><input name="referrer_phone" type="tel" placeholder="(555) 555-5555">'
            '<label>Their name</label><input name="referred_name" required placeholder="Who should I reach out to?">'
            '<label>Their phone</label><input name="referred_phone" type="tel" required placeholder="(555) 555-5555">'
            '<label>Anything I should know?</label><textarea name="notes" placeholder="What are they looking for?"></textarea>'
            '<button class="btn gold wide" type="submit">Send referral</button>'
            '<div class="ok">Got it! I will reach out and take great care of them.</div><div class="err">Something went wrong. Please try again.</div>'
            "</form></details></section>"
        )

    # --- meta
    desc_bits = [title, store_name, _fmt_phone(phone)]
    desc = " · ".join(x for x in desc_bits if x)
    if bio:
        desc = (bio[:150].rsplit(" ", 1)[0] + "…") if len(bio) > 150 else bio
    page_title = f"{name} · {title}" + (f" at {store_name}" if store_name else "")
    canonical = f"{base}/api/{'card' if is_card else 'p'}/{uid}"
    same_as = [v if v.startswith("http") else f"https://{v}" for v in socials.values()]
    ld = {
        "@context": "https://schema.org", "@type": "Person", "name": name, "jobTitle": title, "url": canonical,
        **({"image": photo_abs} if photo_abs else {}), **({"telephone": phone} if phone else {}), **({"email": email} if email else {}),
        **({"worksFor": {"@type": "AutoDealer" if s else "Organization", "name": store_name, **({"url": s.get("website")} if s and s.get("website") else {})}} if store_name else {}),
        **({"sameAs": same_as} if same_as else {}), **({"description": bio} if bio else {}),
    }
    footer_store = f"{e(name)} · {e(store_name)}" if store_name else e(name)

    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{e(page_title)}</title>
<meta name="description" content="{e(desc)}"><link rel="canonical" href="{e(canonical)}">
<meta property="og:type" content="profile"><meta property="og:title" content="{e(page_title)}"><meta property="og:description" content="{e(desc)}"><meta property="og:url" content="{e(canonical)}">
{f'<meta property="og:image" content="{e(photo_abs)}"><meta name="twitter:card" content="summary">' if photo_abs else ''}
<meta name="theme-color" content="#0B0B0C">
<script type="application/ld+json">{json.dumps(ld)}</script>
<style>{CSS}</style></head>
<body><div class="wrap">
{hero}
{''.join(sections)}
<footer>{footer_store}<br>via <a href="https://www.imonsocial.com">i'M On Social</a>, the Relationship OS</footer>
</div><script>{JS}</script></body></html>"""


NOT_FOUND = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Page not found</title>
<style>body{margin:0;background:#0B0B0C;color:#F4F1EA;font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;text-align:center;padding:24px}h1{font-size:22px}p{color:#9A9A9F}</style></head>
<body><div><h1>This page is no longer available</h1><p>The link may be old or the salesperson has moved on.</p></div></body></html>"""


@router.get("/card/{user_id}", response_class=HTMLResponse)
async def digital_card_page(user_id: str, request: Request):
    db = get_db()
    b = await _bundle(db, user_id, review_limit=3)
    if not b:
        return HTMLResponse(NOT_FOUND, status_code=404)
    await _track(db, "card", user_id, request)
    return HTMLResponse(build_page(b, "card"), headers={"Cache-Control": "no-cache"})


@router.get("/p/{user_id}", response_class=HTMLResponse)
async def landing_page(user_id: str, request: Request):
    db = get_db()
    b = await _bundle(db, user_id, review_limit=12)
    if not b:
        return HTMLResponse(NOT_FOUND, status_code=404)
    await _track(db, "landing", user_id, request)
    return HTMLResponse(build_page(b, "landing"), headers={"Cache-Control": "no-cache"})
