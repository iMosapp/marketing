"""Monthly mystery shop report email: the PDF + a one-line summary to the GM on the 1st, per-client toggle."""
import asyncio
import base64
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from bson import ObjectId

from services import i18n
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
    """One sentence a GM can read in the notification bar, in the client's language."""
    s = rep["summary"]
    lang = rep.get("language") or "en"
    if not s["completed"]:
        return i18n.t(lang, "sum.none", month=rep["month_label"])
    if lang == "nl":
        parts = [f"{s['completed']} shop{'s' if s['completed'] != 1 else ''} afgerond" + (f" van {s['planned']} gepland" if s.get("planned") else "")]
        if s.get("avg_score") is not None:
            parts.append(f"gemiddelde score {s['avg_score']}%")
        parts.append(f"{s['people_shopped']} {'medewerker' if s['people_shopped'] == 1 else 'medewerkers'} gebeld")
        if s.get("needs_training"):
            parts.append(f"{s['needs_training']} {'heeft' if s['needs_training'] == 1 else 'hebben'} training nodig")
    else:
        parts = [f"{s['completed']} shop{'s' if s['completed'] != 1 else ''} completed" + (f" of {s['planned']} planned" if s.get("planned") else "")]
        if s.get("avg_score") is not None:
            parts.append(f"average score {s['avg_score']}%")
        parts.append(f"{s['people_shopped']} {'person' if s['people_shopped'] == 1 else 'people'} shopped")
        if s.get("needs_training"):
            parts.append(f"{s['needs_training']} need{'s' if s['needs_training'] == 1 else ''} training")
    depts = [f"{v.get('label') or ind.dept_label(k)} {v['avg_score']}%" for k, v in (rep.get("by_department") or {}).items() if v.get("completed") and v.get("avg_score") is not None]
    line = f"{rep['month_label'][:1].upper() + rep['month_label'][1:]}: " + ", ".join(parts) + "."
    if len(depts) > 1:
        line += " " + " · ".join(depts) + "."
    return line


def email_html(client: dict, rep: dict, line: str, url: str, logo_src: str) -> str:
    lang = rep.get("language") or "en"
    tr = lambda k, **kw: i18n.t(lang, k, **kw)
    first = (client.get("contact_name") or "").strip().split(" ")[0]
    hi = tr("mail.hi", name=ms._esc(first)) if first else tr("mail.hi_generic")
    logo = f'<img src="{logo_src}" alt="I\'m On Social" width="72" height="72" style="width:72px;height:72px;display:block;margin:0 auto" />' if logo_src else ""
    s = rep["summary"]
    boxes = "".join(
        f'<td style="padding:6px"><div style="background:#f7f3e8;border-radius:12px;padding:12px 10px;text-align:center"><div style="font-size:20px;font-weight:800;color:#111">{ms._esc(str(v))}</div>'
        f'<div style="font-size:10px;letter-spacing:1px;color:#777;text-transform:uppercase;margin-top:2px">{ms._esc(k)}</div></div></td>'
        for k, v in ((tr("mail.box.completed"), tr("pdf.of", a=s['completed'], b=s['planned']) if s.get('planned') else str(s['completed'])), (tr("mail.box.avg"), f"{s['avg_score']}%" if s.get("avg_score") is not None else tr("pdf.na")),
                     (tr("mail.box.people"), s["people_shopped"]), (tr("mail.box.need"), s["needs_training"])))
    top = [r for r in rep.get("people") or [] if r.get("completed")][:3]
    rows = "".join(f'<li style="margin:0 0 4px">{ms._esc(r["name"])} · {ms._esc(r.get("department_label") or ind.dept_label(r.get("department")))} · <b>{r["avg_score"]}%</b>{" · " + tr("mail.needs_training") if r.get("needs_training") else ""}</li>' for r in top if r.get("avg_score") is not None)
    boards = [(dv.get("label") or ind.dept_label(dk), dv["leaderboard"][:3]) for dk, dv in (rep.get("by_department") or {}).items() if dv.get("leaderboard")]
    board_html = "".join(
        f'<p style="margin:0 0 6px;font-size:14px;color:#1a1a1a;line-height:1.5"><b>{ms._esc(lbl)}</b>: '
        + " &nbsp;·&nbsp; ".join(f"{r['rank']}. {ms._esc(r['name'])} <b>{r['avg_score']}%</b>" + (f' <span style="color:#C9A962;font-size:12px;font-weight:700">{ms._esc(", ".join(b["label"] for b in r["badges"]))}</span>' if r["badges"] else "") for r in rows_) + "</p>"
        for lbl, rows_ in boards)
    people_html = (f'<p style="font-size:13px;color:#555;margin:0 0 6px;font-weight:700">{tr("mail.leaderboard")}</p>' + board_html) if board_html else ((f'<p style="font-size:13px;color:#555;margin:0 0 4px;font-weight:700">{tr("mail.top")}</p><ul style="margin:0 0 14px;padding-left:18px;font-size:14px;color:#1a1a1a">' + rows + '</ul>') if rows else '')
    return f"""<div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:600px;margin:0 auto;padding:20px;background:#f5f3ee">
  <div style="background:#fff;border-radius:18px;overflow:hidden;border:1px solid #e6e1d6">
    <div style="text-align:center;padding:26px 20px 14px;border-bottom:1px solid #eee">{logo}
      <p style="margin:10px 0 0;font-size:11px;letter-spacing:2px;color:#C9A962;font-weight:800">{tr("mail.month.kicker")}</p>
    </div>
    <div style="padding:26px 30px">
      <h1 style="font-size:22px;line-height:1.3;margin:0 0 6px;color:#111">{ms._esc(client.get('name'))}: {ms._esc(rep['month_label'])}</h1>
      <p style="font-size:15px;line-height:1.65;margin:0 0 14px;color:#1a1a1a">{hi}{ms._esc(tr("mail.month.intro", month=rep['month_label'], line=line))}</p>
      <table role="presentation" style="width:100%;border-collapse:collapse;margin:0 0 14px"><tr>{boxes}</tr></table>
      {people_html}
      <p style="margin:22px 0;text-align:center"><a href="{url}" style="background:#C9A962;color:#111;text-decoration:none;font-weight:800;padding:14px 26px;border-radius:12px;display:inline-block;font-size:15px">{tr("mail.open_report")}</a></p>
      <p style="font-size:13px;color:#666;line-height:1.6;margin:0">{tr("mail.pdf_attached")}</p>
    </div>
  </div>
  <p style="text-align:center;margin:18px 0 0;color:#999;font-size:12px">{tr("mail.footer")}</p>
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
               "subject": i18n.t(rep.get("language"), "mail.month.subject", client=client.get('name'), month=rep['month_label']), "html": email_html(client, rep, line, url, "cid:imos-logo"), "text": f"{line}\n\n{i18n.t(rep.get('language'), 'mail.open_report')}: {url}",
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


# ── Weekly digest: Monday morning, just last week's shops and scores ─────────────────────────────────────────────
def last_week(client: dict, now: Optional[datetime] = None) -> tuple:
    """(monday_utc, next_monday_utc, key 'YYYY-Www', label) for the ISO week before the current local one."""
    local = (now or ms._now()).astimezone(ms._tz(client))
    this_monday = (local - timedelta(days=local.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    monday = this_monday - timedelta(days=7)
    iso = monday.isocalendar()
    from services import locales as loc
    lang = loc.dialect(loc.key_of(client))
    sunday = this_monday - timedelta(days=1)
    if lang == "nl":
        label = f"{monday.day} {i18n.month_label(monday, 'nl', short=True)} tot {sunday.day} {i18n.month_label(sunday, 'nl', short=True)}"
    else:
        label = f"{monday.strftime('%b')} {monday.day} to {sunday.strftime('%b')} {sunday.day}"
    return monday.astimezone(timezone.utc), this_monday.astimezone(timezone.utc), f"{iso[0]}-W{iso[1]:02d}", label


async def week_shops(db, client: dict, start, end) -> list:
    cid = str(client["_id"])
    calls = await db.roleplay_sessions.find({"kind": "mystery_shop", "client_id": cid, "status": {"$in": ["completed", "unreachable"]},
                                             "$or": [{"ended_at": {"$gte": start, "$lt": end}}, {"ended_at": None, "scheduled_for": {"$gte": start, "$lt": end}}]}).sort("ended_at", -1).to_list(200)
    ev_ids = [ObjectId(c["evaluation_id"]) for c in calls if c.get("evaluation_id") and ObjectId.is_valid(str(c["evaluation_id"]))]
    evals = {str(e["_id"]): e for e in await db.call_evaluations.find({"_id": {"$in": ev_ids}}, {"summary": 1, "critical_misses": 1, "coaching": 1}).to_list(300)} if ev_ids else {}
    rows = []
    for c in calls:
        ev = evals.get(str(c.get("evaluation_id"))) or {}
        rows.append({"name": c.get("rep_name") or "Unknown", "department": ind.dept_label_for(c.get("department") or "sales", client.get("locale")), "script": c.get("script_title") or "Shop", "status": c.get("status"),
                     "score": c.get("score_pct"), "when": c.get("ended_at") or c.get("scheduled_for"), "summary": ev.get("summary") or "", "critical": len(ev.get("critical_misses") or []),
                     "tip": (ev.get("coaching") or [""])[0]})
    return rows


def digest_line(rows: list, label: str, lang: str = "en") -> str:
    done = [r for r in rows if r["status"] == "completed"]
    nl = lang == "nl"
    if not done:
        if nl:
            return f"Er zijn {label} geen shops afgerond." + (f" {len(rows)} {'was' if len(rows) == 1 else 'waren'} niet bereikbaar." if rows else "")
        return f"No shops were completed {label}." + (f" {len(rows)} could not be reached." if rows else "")
    scores = [r["score"] for r in done if r["score"] is not None]
    avg = round(sum(scores) / len(scores)) if scores else None
    best = max(done, key=lambda r: r["score"] or 0)
    crit = sum(r["critical"] for r in done)
    unreach = len([r for r in rows if r["status"] == "unreachable"])
    if nl:
        parts = [f"{len(done)} shop{'s' if len(done) != 1 else ''} {label}"]
        if avg is not None:
            parts.append(f"gemiddeld {avg}%")
        parts.append(f"hoogste score {best['name']} {best['score']}%")
        if crit:
            parts.append(f"{crit} kritieke misser{'s' if crit != 1 else ''}")
        if unreach:
            parts.append(f"{unreach} onbereikbaar")
        return ", ".join(parts) + "."
    parts = [f"{len(done)} shop{'s' if len(done) != 1 else ''} {label}"]
    if avg is not None:
        parts.append(f"average {avg}%")
    parts.append(f"top score {best['name']} {best['score']}%")
    if crit:
        parts.append(f"{crit} critical miss{'es' if crit != 1 else ''}")
    if unreach:
        parts.append(f"{unreach} unreachable")
    return ", ".join(parts) + "."


def _score_color(sc) -> str:
    return "#999" if sc is None else "#D64545" if sc < 70 else "#C9A962" if sc < 85 else "#2E9E5B"


def digest_html(client: dict, rows: list, line: str, label: str, url: str, logo_src: str) -> str:
    from services import locales as loc
    lang = loc.dialect(loc.key_of(client))
    tr = lambda k, **kw: i18n.t(lang, k, **kw)
    first = (client.get("contact_name") or "").strip().split(" ")[0] or "there"
    logo = f'<img src="{logo_src}" alt="I\'m On Social" width="72" height="72" style="width:72px;height:72px;display:block;margin:0 auto" />' if logo_src else ""
    tz = ms._tz(client)
    trs = []
    for r in rows:
        when = r["when"].astimezone(tz).strftime("%a %I:%M %p").replace(" 0", " ") if r.get("when") else ""
        score = (f"{r['score']}%" if r["score"] is not None else "-") if r["status"] == "completed" else "n/r"
        summ = f'<br><span style="font-size:12px;color:#444">{ms._esc(r["summary"][:160])}</span>' if r.get("summary") else ""
        trs.append(f'<tr style="border-top:1px solid #eee"><td style="padding:9px 6px;font-size:14px;color:#111"><b>{ms._esc(r["name"])}</b><br>'
                   f'<span style="font-size:12px;color:#777">{ms._esc(r["department"])} · {ms._esc(r["script"])} · {when}</span>{summ}</td>'
                   f'<td style="padding:9px 6px;text-align:right;white-space:nowrap;font-size:18px;font-weight:800;color:{_score_color(r["score"]) if r["status"] == "completed" else "#999"}">{score}</td></tr>')
    table = "".join(trs) or f'<tr><td style="padding:12px 6px;color:#777;font-size:14px">{tr("mail.week.none")}</td></tr>'
    return f"""<div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:600px;margin:0 auto;padding:20px;background:#f5f3ee">
  <div style="background:#fff;border-radius:18px;overflow:hidden;border:1px solid #e6e1d6">
    <div style="text-align:center;padding:26px 20px 14px;border-bottom:1px solid #eee">{logo}
      <p style="margin:10px 0 0;font-size:11px;letter-spacing:2px;color:#C9A962;font-weight:800">{tr("mail.week.kicker")}</p>
    </div>
    <div style="padding:26px 30px">
      <h1 style="font-size:20px;line-height:1.3;margin:0 0 6px;color:#111">{ms._esc(client.get('name'))}: {ms._esc(label)}</h1>
      <p style="font-size:15px;line-height:1.65;margin:0 0 14px;color:#1a1a1a">{("Goedemorgen " if lang == "nl" else "Morning ") + ms._esc(first)}. {ms._esc(line)}</p>
      <table role="presentation" style="width:100%;border-collapse:collapse;margin:0 0 6px">{table}</table>
      <p style="margin:22px 0 10px;text-align:center"><a href="{url}" style="background:#C9A962;color:#111;text-decoration:none;font-weight:800;padding:14px 26px;border-radius:12px;display:inline-block;font-size:15px">{"Luister de gesprekken en lees de coaching" if lang == "nl" else "Hear the calls and read the coaching"}</a></p>
      <p style="font-size:12.5px;color:#666;line-height:1.6;margin:0">{"Dit is het korte maandagoverzicht. De volledige maand-pdf komt nog steeds op de 1e als je die aan hebt staan. Beantwoord deze mail met vragen." if lang == "nl" else "This is the quick Monday loop. The full monthly PDF still arrives on the 1st if you have it on. Reply to this email with any questions."}</p>
    </div>
  </div>
  <p style="text-align:center;margin:18px 0 0;color:#999;font-size:12px">{tr("mail.footer")}</p>
</div>"""


async def send_weekly_digest(db, client: dict, to: Optional[str] = None, actor: Optional[dict] = None, reason: str = "manual", now: Optional[datetime] = None) -> dict:
    cfg = client.get("weekly_digest") or {}
    to = (to or cfg.get("to") or (client.get("auto_report") or {}).get("to") or client.get("contact_email") or "").strip().lower()
    if not to or "@" not in to:
        return {"ok": False, "error": "No GM email on this client yet"}
    key = os.environ.get("RESEND_API_KEY")
    if not key:
        return {"ok": False, "error": "Email is not configured"}
    start, end, week_key, label = last_week(client, now)
    rows = await week_shops(db, client, start, end)
    from services import locales as loc
    lang = loc.dialect(loc.key_of(client))
    line = digest_line(rows, label, lang)
    token = client.get("report_token")
    url = f"{scr._app_url()}/shop-report/{token}" if token else scr._app_url()
    import resend
    resend.api_key = key
    sender = os.environ.get("SENDER_EMAIL", "notifications@send.imonsocial.com")
    payload = {"from": f"I'm On Social <{sender}>", "to": [to], "reply_to": (actor or {}).get("email") or os.environ.get("REPORT_REPLY_TO", "support@imonsocial.com"),
               "subject": i18n.t(lang, "mail.week.subject", client=client.get('name'), label=label), "html": digest_html(client, rows, line, label, url, "cid:imos-logo"), "text": f"{line}\n\n{i18n.t(lang, 'mail.open_report')}: {url}"}
    logo = ms.logo_b64()
    if logo:
        payload["attachments"] = [{"filename": "imos-logo.png", "content": logo, "content_id": "imos-logo"}]
    ts = ms._now()
    try:
        r = await asyncio.to_thread(resend.Emails.send, payload)
    except Exception as e:
        logger.warning(f"[MysteryShop] weekly digest failed for {client.get('name')}: {e}")
        await db.shop_report_sends.insert_one({"client_id": str(client["_id"]), "week": week_key, "kind": "weekly", "to": to, "ok": False, "error": str(e)[:300], "reason": reason, "at": ts})
        return {"ok": False, "error": "The email did not go out, try again"}
    await db.shop_report_sends.insert_one({"client_id": str(client["_id"]), "week": week_key, "kind": "weekly", "to": to, "ok": True, "email_id": (r or {}).get("id"), "reason": reason, "summary": line, "at": ts})
    await db.shop_clients.update_one({"_id": client["_id"]}, {"$set": {"weekly_digest.last_sent_week": week_key, "weekly_digest.last_sent_at": ts, "weekly_digest.last_sent_to": to, "updated_at": ts}})
    return {"ok": True, "to": to, "week": week_key, "label": label, "summary": line, "shops": len(rows)}


def digest_due_now(client: dict, now: Optional[datetime] = None) -> bool:
    """Monday (or Tuesday catch-up) after 8am local, not yet sent for last week."""
    cfg = client.get("weekly_digest") or {}
    if not cfg.get("enabled") or not client.get("active", True) or client.get("demo"):
        return False
    local = (now or ms._now()).astimezone(ms._tz(client))
    if local.weekday() > 1 or local.hour < SEND_HOUR_LOCAL:
        return False
    return cfg.get("last_sent_week") != last_week(client, now)[2]


async def send_due_digests(db) -> int:
    n = 0
    async for c in db.shop_clients.find({"weekly_digest.enabled": True, "active": {"$ne": False}}):
        if not digest_due_now(c):
            continue
        try:
            res = await send_weekly_digest(db, c, reason="auto")
            if res.get("ok"):
                n += 1
            else:
                await db.shop_clients.update_one({"_id": c["_id"]}, {"$set": {"weekly_digest.last_sent_week": last_week(c)[2], "weekly_digest.last_error": res.get("error")}})
        except Exception as e:
            logger.warning(f"[MysteryShop] weekly digest failed for {c.get('name')}: {e}")
    return n


def next_monday(c: dict, now: Optional[datetime] = None) -> str:
    local = (now or ms._now()).astimezone(ms._tz(c))
    days = (7 - local.weekday()) % 7 or 7
    return (local + timedelta(days=days)).strftime("%Y-%m-%d")


def serialize_weekly_digest(c: dict) -> dict:
    cfg = c.get("weekly_digest") or {}
    return {"enabled": bool(cfg.get("enabled")), "to": cfg.get("to") or (c.get("auto_report") or {}).get("to") or c.get("contact_email") or "", "last_sent_week": cfg.get("last_sent_week"),
            "last_sent_at": cfg.get("last_sent_at").isoformat() if cfg.get("last_sent_at") else None, "last_sent_to": cfg.get("last_sent_to"), "last_error": cfg.get("last_error"),
            "next_send": next_monday(c) if cfg.get("enabled") else None}
