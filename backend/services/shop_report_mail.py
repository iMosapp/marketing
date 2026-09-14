"""Monthly mystery shop report email: the PDF + a one-line summary to the GM on the 1st, per-client toggle."""
import asyncio
import base64
import logging
import os
from datetime import datetime

from services import industries as ind
from services import mystery_shops as ms
from services import scripts as scr

logger = logging.getLogger(__name__)

SEND_HOUR_LOCAL = 8          # send after 8am in the client's timezone
CATCH_UP_DAYS = 3            # if the 1st was missed (outage), still send on the 2nd or 3rd


def previous_month(client: dict, now: datetime | None = None) -> str:
    local = (now or ms._now()).astimezone(ms._tz(client))
    y, m = (local.year, local.month - 1) if local.month > 1 else (local.year - 1, 12)
    return f"{y:04d}-{m:02d}"


def summary_line(rep: dict) -> str:
    """One sentence a GM can read in the notification bar."""
    s = rep["summary"]
    if not s["completed"]:
        return f"No shops were completed in {rep['month_label']}."
    parts = [f"{s['completed']} shop{'s' if s['completed'] != 1 else ''} completed" + (f" of {s['planned']} planned" if s.get("planned") else "")]
    if s.get("avg_score") is not None:
        parts.append(f"average score {s['avg_score']}%")
    parts.append(f"{s['people_shopped']} {'person' if s['people_shopped'] == 1 else 'people'} shopped")
    if s.get("needs_training"):
        parts.append(f"{s['needs_training']} need{'s' if s['needs_training'] == 1 else ''} training")
    depts = [f"{v.get('label') or ind.dept_label(k)} {v['avg_score']}%" for k, v in (rep.get("by_department") or {}).items() if v.get("completed") and v.get("avg_score") is not None]
    line = f"{rep['month_label']}: " + ", ".join(parts) + "."
    if len(depts) > 1:
        line += " " + " · ".join(depts) + "."
    return line


def email_html(client: dict, rep: dict, line: str, url: str, logo_src: str) -> str:
    first = (client.get("contact_name") or "").strip().split(" ")[0] or "there"
    logo = f'<img src="{logo_src}" alt="I\'m On Social" width="72" height="72" style="width:72px;height:72px;display:block;margin:0 auto" />' if logo_src else ""
    s = rep["summary"]
    boxes = "".join(
        f'<td style="padding:6px"><div style="background:#f7f3e8;border-radius:12px;padding:12px 10px;text-align:center"><div style="font-size:20px;font-weight:800;color:#111">{ms._esc(str(v))}</div>'
        f'<div style="font-size:10px;letter-spacing:1px;color:#777;text-transform:uppercase;margin-top:2px">{ms._esc(k)}</div></div></td>'
        for k, v in (("Shops", f"{s['completed']}{(' of ' + str(s['planned'])) if s.get('planned') else ''}"), ("Average", f"{s['avg_score']}%" if s.get("avg_score") is not None else "n/a"),
                     ("People", s["people_shopped"]), ("Need training", s["needs_training"])))
    top = [r for r in rep.get("people") or [] if r.get("completed")][:3]
    rows = "".join(f'<li style="margin:0 0 4px">{ms._esc(r["name"])} · {ms._esc(r.get("department_label") or ind.dept_label(r.get("department")))} · <b>{r["avg_score"]}%</b>{" · needs training" if r.get("needs_training") else ""}</li>' for r in top if r.get("avg_score") is not None)
    return f"""<div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:600px;margin:0 auto;padding:20px;background:#f5f3ee">
  <div style="background:#fff;border-radius:18px;overflow:hidden;border:1px solid #e6e1d6">
    <div style="text-align:center;padding:26px 20px 14px;border-bottom:1px solid #eee">{logo}
      <p style="margin:10px 0 0;font-size:11px;letter-spacing:2px;color:#C9A962;font-weight:800">I'M ON SOCIAL · MYSTERY SHOP REPORT</p>
    </div>
    <div style="padding:26px 30px">
      <h1 style="font-size:22px;line-height:1.3;margin:0 0 6px;color:#111">{ms._esc(client.get('name'))}: {ms._esc(rep['month_label'])}</h1>
      <p style="font-size:15px;line-height:1.65;margin:0 0 14px;color:#1a1a1a">Hi {ms._esc(first)}, here is last month's phone mystery shop report. {ms._esc(line)}</p>
      <table role="presentation" style="width:100%;border-collapse:collapse;margin:0 0 14px"><tr>{boxes}</tr></table>
      {('<p style="font-size:13px;color:#555;margin:0 0 4px;font-weight:700">Top of the list</p><ul style="margin:0 0 14px;padding-left:18px;font-size:14px;color:#1a1a1a">' + rows + '</ul>') if rows else ''}
      <p style="margin:22px 0;text-align:center"><a href="{url}" style="background:#C9A962;color:#111;text-decoration:none;font-weight:800;padding:14px 26px;border-radius:12px;display:inline-block;font-size:15px">Open the live report</a></p>
      <p style="font-size:13px;color:#666;line-height:1.6;margin:0">The full PDF is attached. Tap any name in the live report to see that person's shops, transcripts and trend. Questions? Just reply to this email.</p>
    </div>
  </div>
  <p style="text-align:center;margin:18px 0 0;color:#999;font-size:12px">I'm On Social LLC · 1741 Lunford Ln, Riverton, UT 84065 · You get this because monthly reports are on for {ms._esc(client.get('name'))}.</p>
</div>"""


async def send_report_email(db, client: dict, month: str | None = None, to: str | None = None, actor: dict | None = None, reason: str = "manual") -> dict:
    """Build last month's (or `month`'s) report, attach the PDF, email it. Records the send on the client."""
    cfg = client.get("auto_report") or {}
    to = (to or cfg.get("to") or client.get("contact_email") or "").strip().lower()
    if not to or "@" not in to:
        return {"ok": False, "error": "No GM email on this client yet"}
    key = os.environ.get("RESEND_API_KEY")
    if not key:
        return {"ok": False, "error": "Email is not configured"}
    month = month or previous_month(client)
    rep = await ms.build_report(db, client, month)
    line = summary_line(rep)
    token = client.get("report_token")
    url = f"{scr._app_url()}/shop-report/{token}?month={month}" if token else scr._app_url()
    pdf = await asyncio.to_thread(ms.report_pdf, rep)
    fname = "".join(ch if ch.isalnum() or ch in " -_" else "" for ch in f"{client.get('name')} mystery shop {month}").strip().replace(" ", "_") + ".pdf"
    import resend
    resend.api_key = key
    sender = os.environ.get("SENDER_EMAIL", "notifications@send.imonsocial.com")
    payload = {"from": f"I'm On Social <{sender}>", "to": [to], "reply_to": (actor or {}).get("email") or os.environ.get("REPORT_REPLY_TO", "support@imonsocial.com"),
               "subject": f"{client.get('name')}: mystery shop report for {rep['month_label']}", "html": email_html(client, rep, line, url, "cid:imos-logo"), "text": f"{line}\n\nOpen the live report: {url}",
               "attachments": [{"filename": fname, "content": base64.b64encode(pdf).decode(), "content_type": "application/pdf"}]}
    logo = ms.logo_b64()
    if logo:
        payload["attachments"].append({"filename": "imos-logo.png", "content": logo, "content_id": "imos-logo"})
    now = ms._now()
    try:
        r = await asyncio.to_thread(resend.Emails.send, payload)
    except Exception as e:
        logger.warning(f"[MysteryShop] monthly report email failed for {client.get('name')}: {e}")
        await db.shop_report_sends.insert_one({"client_id": str(client["_id"]), "month": month, "to": to, "ok": False, "error": str(e)[:300], "reason": reason, "at": now})
        return {"ok": False, "error": "The email did not go out, try again or copy the link"}
    await db.shop_report_sends.insert_one({"client_id": str(client["_id"]), "month": month, "to": to, "ok": True, "email_id": (r or {}).get("id"), "reason": reason, "summary": line, "at": now})
    await db.shop_clients.update_one({"_id": client["_id"]}, {"$set": {"auto_report.last_sent_month": month, "auto_report.last_sent_at": now, "auto_report.last_sent_to": to, "updated_at": now}})
    return {"ok": True, "to": to, "month": month, "month_label": rep["month_label"], "summary": line}


def due_now(client: dict, now: datetime | None = None) -> bool:
    """1st of the month (or a catch-up day) after 8am local, and last month's report has not gone out yet."""
    cfg = client.get("auto_report") or {}
    if not cfg.get("enabled") or not client.get("active", True) or client.get("demo"):
        return False
    local = (now or ms._now()).astimezone(ms._tz(client))
    if local.day > CATCH_UP_DAYS or local.hour < SEND_HOUR_LOCAL:
        return False
    return cfg.get("last_sent_month") != previous_month(client, now)


async def send_due_reports(db) -> int:
    """Scheduler tick (hourly): email last month's PDF to every client whose toggle is on and whose day has come."""
    n = 0
    async for c in db.shop_clients.find({"auto_report.enabled": True, "active": {"$ne": False}}):
        if not due_now(c):
            continue
        try:
            res = await send_report_email(db, c, reason="auto")
            if res.get("ok"):
                n += 1
            else:
                # no email / not configured: park it for this month so we do not retry every hour
                await db.shop_clients.update_one({"_id": c["_id"]}, {"$set": {"auto_report.last_sent_month": previous_month(c), "auto_report.last_error": res.get("error")}})
        except Exception as e:
            logger.warning(f"[MysteryShop] auto report failed for {c.get('name')}: {e}")
    return n


def next_send_date(c: dict, now: datetime | None = None) -> str:
    local = (now or ms._now()).astimezone(ms._tz(c))
    y, m = (local.year, local.month + 1) if local.month < 12 else (local.year + 1, 1)
    return f"{y:04d}-{m:02d}-01"


def serialize_auto_report(c: dict) -> dict:
    cfg = c.get("auto_report") or {}
    return {"enabled": bool(cfg.get("enabled")), "to": cfg.get("to") or c.get("contact_email") or "", "last_sent_month": cfg.get("last_sent_month"),
            "last_sent_at": cfg.get("last_sent_at").isoformat() if cfg.get("last_sent_at") else None, "last_sent_to": cfg.get("last_sent_to"), "last_error": cfg.get("last_error"),
            "next_send": next_send_date(c) if cfg.get("enabled") else None}
