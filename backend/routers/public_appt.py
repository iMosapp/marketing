"""Public Add-to-Calendar page + .ics for a booked appointment. No auth: the URL carries a random token."""
import html
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, Response

from routers.database import get_db
from services.calendar_invite import load_context, build_ics, google_url, when_label, _utc

router = APIRouter(prefix="/public/appt", tags=["Public Appointment"])
logger = logging.getLogger(__name__)

_PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{title}</title><meta name="robots" content="noindex">
<style>
:root{{--gold:#C9A962;--bg:#0B0B0D;--card:#15161A;--line:#26272C;--text:#F4F1EA;--muted:#9A9AA2}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font:16px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased}}
.wrap{{max-width:440px;margin:0 auto;padding:40px 20px 56px}}
.eyebrow{{font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:var(--gold);margin:0 0 14px;font-weight:700}}
h1{{font-size:30px;line-height:1.15;margin:0 0 6px;font-weight:800}}
.time{{font-size:20px;color:var(--text);margin:0 0 18px;font-weight:600}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:18px 18px 8px;margin:22px 0}}
.row{{display:flex;gap:12px;align-items:flex-start;padding:0 0 12px}}.row svg{{flex:none;margin-top:2px}}
.row .k{{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.08em;margin:0 0 2px}}.row .v{{margin:0;font-weight:600}}
.row a{{color:var(--text);text-decoration:none;border-bottom:1px solid var(--line)}}
.btn{{display:flex;align-items:center;justify-content:center;gap:10px;width:100%;padding:16px 18px;border-radius:999px;font-weight:800;font-size:16px;text-decoration:none;margin:10px 0;border:1px solid var(--line);color:var(--text);background:var(--card);transition:transform .12s ease,background-color .12s ease}}
.btn:active{{transform:scale(.98)}}.btn.primary{{background:var(--gold);color:#000;border-color:var(--gold)}}
.foot{{margin-top:26px;font-size:14px;color:var(--muted)}}.foot a{{color:var(--gold);text-decoration:none;font-weight:700}}
.hide{{display:none}}
</style></head><body><div class="wrap">
<p class="eyebrow">{eyebrow}</p>
<h1>{day}</h1>
<p class="time">{time}</p>
<div class="card">
 <div class="row"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#C9A962" stroke-width="2"><circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 4-6 8-6s8 2 8 6"/></svg><div><p class="k">With</p><p class="v">{rep}</p></div></div>
 {where}
</div>
<a class="btn primary" id="apple" href="{ics}">Add to Apple Calendar</a>
<a class="btn" id="google" href="{google}" target="_blank" rel="noopener">Add to Google Calendar</a>
<a class="btn" id="other" href="{ics}" download="appointment.ics">Outlook / other calendars</a>
<p class="foot">Need to change it? {contact_line}</p>
</div>
<script>
var ua=navigator.userAgent||"";var a=document.getElementById("apple"),g=document.getElementById("google"),o=document.getElementById("other");
if(/Android/i.test(ua)){{g.classList.add("primary");a.classList.remove("primary");g.parentNode.insertBefore(g,a);}}
else if(!/iPhone|iPad|iPod|Macintosh/i.test(ua)){{a.textContent="Download calendar file (.ics)";}}
</script></body></html>"""

_GONE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Appointment</title><style>body{{margin:0;background:#0B0B0D;color:#F4F1EA;font:16px/1.5 -apple-system,Segoe UI,Helvetica,Arial,sans-serif}}
.wrap{{max-width:440px;margin:0 auto;padding:56px 20px}}h1{{font-size:26px;margin:0 0 10px}}p{{color:#9A9AA2}}a{{color:#C9A962;font-weight:700;text-decoration:none}}</style></head>
<body><div class="wrap"><h1>{title}</h1><p>{body}</p></div></body></html>"""

_PIN = ('<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#C9A962" stroke-width="2">'
        '<path d="M12 22s7-6.2 7-12a7 7 0 1 0-14 0c0 5.8 7 12 7 12z"/><circle cx="12" cy="10" r="2.5"/></svg>')


async def _ctx_for_token(token: str):
    db = get_db()
    task = await db.tasks.find_one({"invite_token": token}) if token and len(token) < 64 else None
    if not task:
        return None, None
    return task, await load_context(db, task)


@router.get("/{token}.ics")
async def appointment_ics(token: str):
    task, ctx = await _ctx_for_token(token)
    if not ctx:
        return Response("Not found", status_code=404)
    return Response(build_ics(ctx), media_type="text/calendar; charset=utf-8",
                    headers={"Content-Disposition": 'inline; filename="appointment.ics"', "Cache-Control": "no-store"})


@router.get("/{token}", response_class=HTMLResponse)
async def appointment_page(token: str, request: Request):
    task, ctx = await _ctx_for_token(token)
    if not ctx or task.get("status") == "dismissed":
        return HTMLResponse(_GONE.format(title="This appointment is no longer on the books",
                                         body="Text your rep to set a new time."), status_code=404)
    e = lambda v: html.escape(v, quote=False)  # text nodes
    ea = html.escape  # attribute values
    past = _utc(task["due_date"]) < datetime.now(timezone.utc)
    if task.get("completed") or task.get("status") == "completed":
        eyebrow = "Thanks for coming in"
    elif past:
        eyebrow = "This appointment has passed"
    else:
        eyebrow = "Updated appointment" if int(task.get("invite_sequence") or 0) > 0 else "You're all set"
    local = ctx["local"]
    where = ""
    if ctx["location"]:
        maps = "https://maps.apple.com/?q=" + ea(ctx["location"]).replace(" ", "+")
        where = (f'<div class="row">{_PIN}<div><p class="k">Where</p><p class="v"><a href="{maps}">{e(ctx["location"])}</a></p></div></div>')
    if ctx["rep_number"]:
        contact_line = f'<a href="sms:{ea(ctx["rep_number"])}">Text {e(ctx["rep_first"])}</a> or <a href="tel:{ea(ctx["rep_number"])}">call</a>.'
    else:
        contact_line = f"Reply to {e(ctx['rep_first'])}'s text."
    page = _PAGE.format(
        title=e(f"{when_label(ctx)} with {ctx['rep_first']}"),
        eyebrow=e(eyebrow),
        day=e(local.strftime("%A, %B %-d")),
        time=e(local.strftime("%-I:%M %p %Z")),
        rep=e(ctx["rep_name"] + (f" at {ctx['store_name']}" if ctx["store_name"] else "")),
        where=where,
        ics=f"/api/public/appt/{ea(token)}.ics",
        google=ea(google_url(ctx)),
        contact_line=contact_line,
    )
    return HTMLResponse(page, headers={"Cache-Control": "no-store"})
