"""
Share a contact's profile with anyone (no account needed):
  - vCard (.vcf) with the photo embedded  -> saves straight into the recipient's phone Contacts
  - public profile link  /api/share/{token} -> read-only page (photo, details, vehicle, tags, optional notes + intel)
  - plain-text summary for pasting anywhere
Links never expire; the sharer can revoke them. `include_private` gates notes + Relationship Intel.
"""
import base64
import html
import logging
import os
import secrets
from datetime import datetime, timezone
from typing import Optional

import httpx
from bson import ObjectId
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel

from routers.database import get_db
from utils.contact_activity import log_customer_activity
from utils.image_urls import resolve_contact_photo

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/contacts", tags=["contact-share"])          # authed (BOLA middleware: /api/contacts/{user_id}/...)
public_router = APIRouter(prefix="/share", tags=["contact-share-public"])
COLL = "contact_shares"


def _public_base() -> str:
    return os.environ.get("PUBLIC_FACING_URL", os.environ.get("APP_URL", "https://app.imonsocial.com")).rstrip("/")


def _dt(v):
    if isinstance(v, str):
        try:
            v = datetime.fromisoformat(v.replace("Z", "+00:00"))
        except Exception:
            return None
    return v if isinstance(v, datetime) else None


def _fmt_date(v) -> str:
    d = _dt(v)
    return d.strftime("%b %-d, %Y") if d else ""


def _fmt_phone(p: str) -> str:
    digits = "".join(ch for ch in (p or "") if ch.isdigit())
    if len(digits) == 11 and digits[0] == "1":
        digits = digits[1:]
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    return p or ""


def _name(c: dict) -> str:
    return f"{c.get('first_name', '')} {c.get('last_name', '')}".strip() or "Contact"


def _phones(c: dict) -> list:
    out, seen = [], set()
    for label, val in [("Mobile", c.get("phone"))] + [((p or {}).get("label") or "Phone", (p or {}).get("value")) for p in c.get("phones") or []]:
        if val and val not in seen:
            seen.add(val)
            out.append({"label": label, "value": val})
    return out


def _emails(c: dict) -> list:
    out, seen = [], set()
    for label, val in [("Email", c.get("email")), ("Work", c.get("email_work"))] + [((e or {}).get("label") or "Email", (e or {}).get("value")) for e in c.get("emails") or []]:
        if val and val.lower() not in seen:
            seen.add(val.lower())
            out.append({"label": label, "value": val})
    return out


def _address(c: dict) -> str:
    line1 = c.get("address_street") or c.get("address") or ""
    city = c.get("address_city") or c.get("city") or ""
    state = c.get("address_state") or c.get("state") or ""
    zip_ = c.get("address_zip") or c.get("zip") or ""
    tail = " ".join(x for x in [state, zip_] if x)
    locality = ", ".join(x for x in [city, tail] if x)
    return ", ".join(x for x in [line1, locality] if x)


def _org(c: dict) -> str:
    return c.get("company") or c.get("organization_name") or c.get("employer") or ""


def _role(c: dict) -> str:
    return c.get("job_title") or c.get("occupation") or c.get("title") or ""


def _vehicle_lines(c: dict) -> list:
    lines = []
    veh = c.get("vehicle") or c.get("vehicle_interest") or ""
    sold = _fmt_date(c.get("date_sold"))
    count = int(c.get("sold_count") or 0)
    if veh or sold:
        head = veh or "Vehicle"
        if sold:
            head += f" · Sold {sold}"
        if count > 1:
            head += f" · {count}x buyer"
        lines.append(head)
    elif c.get("vehicle_interest"):
        lines.append(f"Interested in {c['vehicle_interest']}")
    for h in c.get("purchase_history") or []:
        d = _fmt_date(h.get("date"))
        v = h.get("vehicle") or "Previous purchase"
        lines.append(f"{v}{' · ' + d if d else ''}")
    return lines


def _dates(c: dict) -> list:
    out = []
    if c.get("birthday"):
        d = _dt(c["birthday"])
        if d:
            out.append(("Birthday", d.strftime("%b %-d") + (f", {d.year}" if d.year > 1930 else "")))
    if c.get("anniversary"):
        d = _dt(c["anniversary"])
        if d:
            out.append(("Anniversary", d.strftime("%b %-d") + (f", {d.year}" if d.year > 1930 else "")))
    return out


async def _bundle(db, user_id: str, contact_id: str, include_private: bool) -> dict:
    """Everything the three share formats need, loaded once."""
    if not (ObjectId.is_valid(user_id) and ObjectId.is_valid(contact_id)):
        raise HTTPException(status_code=400, detail="Invalid id")
    contact = await db.contacts.find_one({"_id": ObjectId(contact_id)})
    user = await db.users.find_one({"_id": ObjectId(user_id)}, {"name": 1, "first_name": 1, "store_id": 1, "title": 1, "phone": 1, "twilio_number": 1, "email": 1})
    if not contact or not user:
        raise HTTPException(status_code=404, detail="Contact not found")
    store = None
    if user.get("store_id") and ObjectId.is_valid(str(user["store_id"])):
        store = await db.stores.find_one({"_id": ObjectId(user["store_id"])}, {"name": 1})
    intel = None
    if include_private:
        doc = await db.contact_intel.find_one({"contact_id": contact_id, "user_id": user_id}, {"summary": 1, "generated_at": 1})
        if doc and doc.get("summary"):
            intel = {"summary": doc["summary"], "generated_at": doc.get("generated_at")}
    return {"contact": contact, "user": user, "store": store, "intel": intel, "include_private": include_private}


async def _photo_bytes(contact: dict) -> Optional[bytes]:
    """JPEG bytes of the contact photo (object storage first, legacy base64 second)."""
    rel = resolve_contact_photo(contact)
    if rel:
        url = rel if rel.startswith("http") else f"http://127.0.0.1:8001{rel}"
        try:
            async with httpx.AsyncClient(timeout=8) as client:
                r = await client.get(url, params={"format": "jpeg"}, follow_redirects=True)
            if r.status_code == 200 and r.content:
                return r.content
        except Exception as e:
            logger.warning(f"[ContactShare] photo fetch failed {rel}: {e}")
    raw = contact.get("photo") or ""
    if isinstance(raw, str) and raw.startswith("data:") and "," in raw:
        try:
            return base64.b64decode(raw.split(",", 1)[1])
        except Exception:
            return None
    return None


# ---------------------------------------------------------------- formats
def _vc_escape(s: str) -> str:
    return str(s or "").replace("\\", "\\\\").replace("\n", "\\n").replace(",", "\\,").replace(";", "\\;")


def build_vcard(b: dict, photo: Optional[bytes], profile_url: Optional[str]) -> str:
    c, u = b["contact"], b["user"]
    first, last = c.get("first_name") or "", c.get("last_name") or ""
    lines = ["BEGIN:VCARD", "VERSION:3.0", f"N:{_vc_escape(last)};{_vc_escape(first)};;;", f"FN:{_vc_escape(_name(c))}"]
    for p in _phones(c):
        typ = "CELL" if p["label"].lower() in ("mobile", "cell", "phone") else p["label"].upper()[:10]
        lines.append(f"TEL;TYPE={typ}:{p['value']}")
    for e in _emails(c):
        lines.append(f"EMAIL;TYPE={'WORK' if e['label'].lower() == 'work' else 'INTERNET'}:{e['value']}")
    if _org(c):
        lines.append(f"ORG:{_vc_escape(_org(c))}")
    if _role(c):
        lines.append(f"TITLE:{_vc_escape(_role(c))}")
    if any(c.get(k) for k in ("address_street", "address_city", "address_state", "address_zip")):
        lines.append(f"ADR;TYPE=HOME:;;{_vc_escape(c.get('address_street'))};{_vc_escape(c.get('address_city'))};{_vc_escape(c.get('address_state'))};{_vc_escape(c.get('address_zip'))};{_vc_escape(c.get('address_country'))}")
    bd = _dt(c.get("birthday"))
    if bd:
        lines.append(f"BDAY:{bd.strftime('%Y-%m-%d') if bd.year > 1930 else '--' + bd.strftime('%m-%d')}")
    if photo:
        lines.append(f"PHOTO;ENCODING=b;TYPE=JPEG:{base64.b64encode(photo).decode()}")
    note_parts = []
    veh = _vehicle_lines(c)
    if veh:
        note_parts.append("Vehicle: " + " | ".join(veh))
    if c.get("tags"):
        note_parts.append("Tags: " + ", ".join(str(t) for t in c["tags"]))
    if b["include_private"]:
        if (c.get("notes") or "").strip():
            note_parts.append("Notes: " + c["notes"].strip())
        if b["intel"]:
            note_parts.append("Relationship Intel: " + b["intel"]["summary"].strip())
    note_parts.append(f"Shared by {u.get('name') or 'a teammate'}" + (f" ({b['store']['name']})" if b.get("store") and b["store"].get("name") else "") + " via i'M On Social")
    lines.append("NOTE:" + _vc_escape("\n\n".join(note_parts)))
    if profile_url:
        lines.append(f"item1.URL;TYPE=PREF:{profile_url}")
        lines.append("item1.X-ABLabel:Full profile")
    lines.append("END:VCARD")
    return "\r\n".join(lines) + "\r\n"


def build_text(b: dict, profile_url: Optional[str]) -> str:
    c, u = b["contact"], b["user"]
    out = [_name(c)]
    sub = " · ".join(x for x in [_role(c), _org(c)] if x)
    if sub:
        out.append(sub)
    out.append("")
    for p in _phones(c):
        out.append(f"{p['label']}: {_fmt_phone(p['value'])}")
    for e in _emails(c):
        out.append(f"{e['label']}: {e['value']}")
    if _address(c):
        out.append(f"Address: {_address(c)}")
    for label, val in _dates(c):
        out.append(f"{label}: {val}")
    veh = _vehicle_lines(c)
    if veh:
        out.append("")
        out.append("Vehicle & purchases:")
        out.extend(f"  - {v}" for v in veh)
    if c.get("tags"):
        out.append("")
        out.append("Tags: " + ", ".join(str(t) for t in c["tags"]))
    if b["include_private"]:
        if (c.get("notes") or "").strip():
            out.append("")
            out.append("Notes:")
            out.append(c["notes"].strip())
        if b["intel"]:
            out.append("")
            out.append("Relationship Intel:")
            out.append(b["intel"]["summary"].strip().replace("**", ""))
    if profile_url:
        out.append("")
        out.append(f"Full profile with photo: {profile_url}")
    out.append("")
    out.append(f"Shared by {u.get('name') or 'a teammate'}" + (f", {b['store']['name']}" if b.get("store") and b["store"].get("name") else "") + " via i'M On Social")
    return "\n".join(out)


def _intel_html(summary: str) -> str:
    headers = ("quick take", "key facts", "communication patterns", "personal notes", "before your next interaction")
    parts, in_list = [], False
    for raw in summary.split("\n"):
        line = raw.strip().replace("**", "")
        if not line:
            continue
        is_bullet = line.startswith(("-", "•"))
        if is_bullet and not in_list:
            parts.append("<ul>"); in_list = True
        if not is_bullet and in_list:
            parts.append("</ul>"); in_list = False
        if is_bullet:
            parts.append(f"<li>{html.escape(line.lstrip('-• ').strip())}</li>")
        elif line.lower().rstrip(':').startswith(headers):
            parts.append(f"<h4>{html.escape(line.rstrip(':'))}</h4>")
        else:
            parts.append(f"<p>{html.escape(line)}</p>")
    if in_list:
        parts.append("</ul>")
    return "".join(parts)


def build_html(b: dict, token: str, has_photo: bool) -> str:
    c, u = b["contact"], b["user"]
    e = html.escape
    base = _public_base()
    name = _name(c)
    initials = "".join(x[0] for x in name.split()[:2]).upper() or "?"
    sub = " · ".join(x for x in [_role(c), _org(c)] if x)
    phones, emails, addr = _phones(c), _emails(c), _address(c)
    primary_phone = phones[0]["value"] if phones else ""
    primary_email = emails[0]["value"] if emails else ""
    photo_rel = f"/api/share/{token}/photo.jpg" if has_photo else ""      # relative: works on any host serving the page
    photo_url = f"{base}{photo_rel}" if has_photo else ""                  # absolute: link previews (og:image)
    desc = " · ".join(x for x in [sub, _fmt_phone(primary_phone), primary_email] if x) or "Contact profile"

    def row(label, value, href=None):
        v = f'<a href="{e(href)}">{e(value)}</a>' if href else e(value)
        return f'<div class="row"><span class="lbl">{e(label)}</span><span class="val">{v}</span></div>'

    rows = "".join(row(p["label"], _fmt_phone(p["value"]), f"tel:{p['value']}") for p in phones)
    rows += "".join(row(x["label"], x["value"], f"mailto:{x['value']}") for x in emails)
    if addr:
        rows += row("Address", addr, "https://maps.apple.com/?q=" + e(addr.replace(" ", "+")))
    rows += "".join(row(l, v) for l, v in _dates(c))

    sections = []
    veh = _vehicle_lines(c)
    if veh:
        sections.append('<section><h3>Vehicle &amp; purchases</h3>' + "".join(f'<div class="row"><span class="val">{e(v)}</span></div>' for v in veh) + '</section>')
    if c.get("tags"):
        sections.append('<section><h3>Tags</h3><div class="tags">' + "".join(f'<span class="tag">{e(str(t))}</span>' for t in c["tags"]) + '</div></section>')
    if b["include_private"]:
        if (c.get("notes") or "").strip():
            sections.append(f'<section><h3>Notes</h3><p class="notes">{e(c["notes"].strip())}</p></section>')
        if b["intel"]:
            when = _fmt_date(b["intel"].get("generated_at"))
            sections.append(f'<section class="intel"><h3>Relationship Intel{(" <small>" + e(when) + "</small>") if when else ""}</h3>{_intel_html(b["intel"]["summary"])}</section>')

    actions = []
    if primary_phone:
        actions.append(f'<a class="btn" href="tel:{e(primary_phone)}">Call</a><a class="btn" href="sms:{e(primary_phone)}">Text</a>')
    if primary_email:
        actions.append(f'<a class="btn" href="mailto:{e(primary_email)}">Email</a>')
    actions.append(f'<a class="btn gold" href="/api/share/{token}.vcf">Save to Contacts</a>')
    shared_by = e(u.get("name") or "a teammate") + (f" · {e(b['store']['name'])}" if b.get("store") and b["store"].get("name") else "")
    avatar = f'<img class="avatar" src="{e(photo_rel)}" alt="{e(name)}">' if photo_rel else f'<div class="avatar initials">{e(initials)}</div>'

    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="robots" content="noindex,nofollow">
<title>{e(name)} · Contact profile</title>
<meta property="og:type" content="profile"><meta property="og:title" content="{e(name)}">
<meta property="og:description" content="{e(desc)}">
{f'<meta property="og:image" content="{e(photo_url)}"><meta name="twitter:card" content="summary">' if photo_url else ''}
<style>
:root{{--bg:#0B0B0C;--card:#151517;--line:#26262A;--text:#F4F1EA;--muted:#9A9A9F;--gold:#C9A962}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font:16px/1.45 -apple-system,BlinkMacSystemFont,"SF Pro Text",Segoe UI,Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased}}
.wrap{{max-width:560px;margin:0 auto;padding:28px 18px 48px}}
.hero{{display:flex;flex-direction:column;align-items:center;text-align:center;gap:10px;padding:28px 18px 22px;background:var(--card);border:1px solid var(--line);border-radius:22px}}
.avatar{{width:124px;height:124px;border-radius:62px;object-fit:cover;border:3px solid var(--gold);background:#222}}
.initials{{display:flex;align-items:center;justify-content:center;font-size:40px;font-weight:800;color:var(--gold)}}
h1{{margin:6px 0 0;font-size:26px;font-weight:800;letter-spacing:-.3px}}
.sub{{color:var(--muted);font-size:15px;margin-top:-4px}}
.actions{{display:flex;flex-wrap:wrap;gap:8px;justify-content:center;margin-top:10px}}
.btn{{display:inline-block;padding:11px 16px;border-radius:999px;border:1px solid var(--line);color:var(--text);text-decoration:none;font-weight:700;font-size:14px;background:#1D1D20;transition:transform .12s,background-color .12s}}
.btn:hover{{transform:translateY(-1px);background:#242428}}.btn.gold{{background:var(--gold);color:#111;border-color:var(--gold)}}
section{{margin-top:14px;background:var(--card);border:1px solid var(--line);border-radius:18px;padding:16px 18px}}
h3{{margin:0 0 10px;font-size:12px;letter-spacing:1.2px;text-transform:uppercase;color:var(--gold);font-weight:800}}h3 small{{color:var(--muted);font-weight:600;letter-spacing:0;text-transform:none;margin-left:8px}}
.row{{display:flex;justify-content:space-between;gap:14px;padding:9px 0;border-top:1px solid var(--line)}}.row:first-of-type{{border-top:0}}
.lbl{{color:var(--muted);font-size:14px;flex:0 0 auto}}.val{{text-align:right;word-break:break-word}}.val a{{color:var(--text);text-decoration:none;border-bottom:1px dashed #3a3a40}}
section .row:only-child,section .row:first-child{{border-top:0}}
.tags{{display:flex;flex-wrap:wrap;gap:6px}}.tag{{padding:5px 10px;border-radius:999px;background:#1F1C14;border:1px solid #3C3320;color:var(--gold);font-size:12px;font-weight:700}}
.notes{{white-space:pre-wrap;margin:0;color:#D8D5CC}}
.intel h4{{margin:12px 0 4px;font-size:15px}}.intel p{{margin:0 0 6px;color:#D8D5CC}}.intel ul{{margin:0 0 6px;padding-left:20px;color:#D8D5CC}}.intel li{{margin:2px 0}}
footer{{margin-top:22px;text-align:center;color:var(--muted);font-size:13px}}footer a{{color:var(--gold);text-decoration:none;font-weight:700}}
</style></head>
<body><div class="wrap">
<div class="hero">{avatar}<h1>{e(name)}</h1>{f'<div class="sub">{e(sub)}</div>' if sub else ''}<div class="actions">{''.join(actions)}</div></div>
{f'<section>{rows}</section>' if rows else ''}
{''.join(sections)}
<footer>Shared by {shared_by}<br>via <a href="https://www.imonsocial.com">i'M On Social</a>, the Relationship OS</footer>
</div></body></html>"""


# ---------------------------------------------------------------- authed management
class LinkBody(BaseModel):
    include_private: bool = True


def _serialize(doc: dict) -> dict:
    return {"token": doc["token"], "url": f"{_public_base()}/api/share/{doc['token']}", "include_private": bool(doc.get("include_private")),
            "views": int(doc.get("views") or 0), "created_at": doc["created_at"].isoformat() if isinstance(doc.get("created_at"), datetime) else doc.get("created_at"),
            "last_viewed_at": doc["last_viewed_at"].isoformat() if isinstance(doc.get("last_viewed_at"), datetime) else None}


async def _ensure_link(db, user_id: str, contact_id: str, include_private: bool) -> dict:
    q = {"contact_id": contact_id, "user_id": user_id, "include_private": include_private, "revoked_at": None}
    doc = await db[COLL].find_one(q, sort=[("created_at", -1)])
    if doc:
        return doc
    now = datetime.now(timezone.utc)
    doc = {**q, "token": secrets.token_urlsafe(8), "created_at": now, "views": 0, "last_viewed_at": None}
    await db[COLL].insert_one(doc)
    await log_customer_activity(user_id=user_id, contact_id=contact_id, event_type="profile_shared", title="Profile link created",
                                description=("Includes notes & intel" if include_private else "Basics only"), icon="share-social", color="#C9A962", category="system")
    return doc


@router.get("/{user_id}/{contact_id}/share")
async def share_overview(user_id: str, contact_id: str):
    """Active links for this contact (never expire until revoked)."""
    db = get_db()
    await _bundle(db, user_id, contact_id, False)
    links = await db[COLL].find({"contact_id": contact_id, "user_id": user_id, "revoked_at": None}).sort("created_at", -1).to_list(10)
    return {"links": [_serialize(l) for l in links]}


@router.post("/{user_id}/{contact_id}/share/link")
async def create_share_link(user_id: str, contact_id: str, body: LinkBody):
    db = get_db()
    await _bundle(db, user_id, contact_id, False)
    doc = await _ensure_link(db, user_id, contact_id, body.include_private)
    return _serialize(doc)


@router.delete("/{user_id}/{contact_id}/share/link/{token}")
async def revoke_share_link(user_id: str, contact_id: str, token: str):
    db = get_db()
    r = await db[COLL].update_one({"token": token, "contact_id": contact_id, "user_id": user_id, "revoked_at": None},
                                  {"$set": {"revoked_at": datetime.now(timezone.utc)}})
    if not r.matched_count:
        raise HTTPException(status_code=404, detail="Link not found")
    await log_customer_activity(user_id=user_id, contact_id=contact_id, event_type="profile_shared", title="Profile link revoked",
                                description="The shared profile page no longer opens", icon="share-social", color="#8E8E93", category="system")
    return {"success": True}


@router.get("/{user_id}/{contact_id}/share/text")
async def share_text(user_id: str, contact_id: str, include_private: bool = True, with_link: bool = True):
    db = get_db()
    b = await _bundle(db, user_id, contact_id, include_private)
    link = await _ensure_link(db, user_id, contact_id, include_private) if with_link else None
    return {"text": build_text(b, _serialize(link)["url"] if link else None), "link": _serialize(link) if link else None}


@router.get("/{user_id}/{contact_id}/share/vcard")
async def share_vcard(user_id: str, contact_id: str, include_private: bool = True, with_link: bool = True):
    db = get_db()
    b = await _bundle(db, user_id, contact_id, include_private)
    link = await _ensure_link(db, user_id, contact_id, include_private) if with_link else None
    photo = await _photo_bytes(b["contact"])
    if photo and len(photo) > 900 * 1024:
        photo = None
    vcf = build_vcard(b, photo, _serialize(link)["url"] if link else None)
    await log_customer_activity(user_id=user_id, contact_id=contact_id, event_type="profile_shared", title="Contact card shared",
                                description=f".vcf{' with photo' if photo else ''}{', notes & intel included' if include_private else ''}", icon="share-social", color="#C9A962", category="system")
    filename = f"{_name(b['contact']).replace(' ', '_')}.vcf"
    return Response(content=vcf, media_type="text/vcard", headers={"Content-Disposition": f'attachment; filename="{filename}"', "Content-Type": "text/vcard; charset=utf-8", "X-Has-Photo": "1" if photo else "0"})


# ---------------------------------------------------------------- public
async def _public_bundle(db, token: str) -> tuple:
    doc = await db[COLL].find_one({"token": token})
    if not doc or doc.get("revoked_at"):
        raise HTTPException(status_code=404, detail="This profile link is no longer available")
    try:
        b = await _bundle(db, doc["user_id"], doc["contact_id"], bool(doc.get("include_private")))
    except HTTPException:
        raise HTTPException(status_code=404, detail="This profile link is no longer available")
    return doc, b


_GONE = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Link unavailable</title>
<style>body{margin:0;background:#0B0B0C;color:#F4F1EA;font:16px -apple-system,Segoe UI,Helvetica,Arial,sans-serif;display:flex;min-height:100vh;align-items:center;justify-content:center;text-align:center;padding:24px}h1{font-size:22px;margin:0 0 8px}p{color:#9A9A9F;margin:0}</style></head>
<body><div><h1>This profile link is no longer available</h1><p>The person who shared it has turned it off.</p></div></body></html>"""


@public_router.get("/{token}.vcf")
async def public_vcard(token: str):
    db = get_db()
    doc, b = await _public_bundle(db, token)
    photo = await _photo_bytes(b["contact"])
    if photo and len(photo) > 900 * 1024:
        photo = None
    vcf = build_vcard(b, photo, f"{_public_base()}/api/share/{token}")
    filename = f"{_name(b['contact']).replace(' ', '_')}.vcf"
    return Response(content=vcf, media_type="text/vcard", headers={"Content-Disposition": f'attachment; filename="{filename}"', "Content-Type": "text/vcard; charset=utf-8"})


@public_router.get("/{token}/photo.jpg")
async def public_photo(token: str):
    db = get_db()
    doc, b = await _public_bundle(db, token)
    photo = await _photo_bytes(b["contact"])
    if not photo:
        raise HTTPException(status_code=404, detail="No photo")
    return Response(content=photo, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=600"})


@public_router.get("/{token}", response_class=HTMLResponse)
async def public_profile(token: str, request: Request):
    db = get_db()
    try:
        doc, b = await _public_bundle(db, token)
    except HTTPException:
        return HTMLResponse(_GONE, status_code=404)
    ua = (request.headers.get("user-agent") or "").lower()
    is_bot = any(k in ua for k in ("bot", "facebookexternalhit", "twitterbot", "slack", "whatsapp", "telegram", "imessage", "preview", "linkexpand"))
    if not is_bot:
        await db[COLL].update_one({"_id": doc["_id"]}, {"$inc": {"views": 1}, "$set": {"last_viewed_at": datetime.now(timezone.utc)}})
    has_photo = bool(resolve_contact_photo(b["contact"]) or str(b["contact"].get("photo") or "").startswith("data:"))
    return HTMLResponse(build_html(b, token, has_photo), headers={"Cache-Control": "no-store"})
