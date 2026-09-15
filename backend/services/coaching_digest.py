"""Monday coaching digest for managers: every rep's graded calls from last week, the change vs the week before,
unread coaching, and the one thing to coach next. On by default for every store manager / org admin; each manager can opt out."""
import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from bson import ObjectId

from services import i18n
from services import locales as loc
from services import scorecards as sc
from services import scripts as scr
from services.mystery_shops import _esc, logo_b64

logger = logging.getLogger(__name__)

SEND_HOUR_LOCAL = 8
OPT_OUT_FIELD = "coaching_digest_opt_out"
DIGEST_ROLES = ["store_manager", "manager", "admin", "org_admin"]


def _now():
    return datetime.now(timezone.utc)


def store_tz(store: Optional[dict]) -> ZoneInfo:
    try:
        return ZoneInfo((store or {}).get("timezone") or "America/Denver")
    except Exception:
        return ZoneInfo("America/Denver")


def last_week(tz: ZoneInfo, now: Optional[datetime] = None, lang: str = "en") -> tuple:
    """(monday_utc, next_monday_utc, key 'YYYY-Www', label 'Sep 7 to Sep 13') for the ISO week before the current local one."""
    local = (now or _now()).astimezone(tz)
    this_monday = (local - timedelta(days=local.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    monday = this_monday - timedelta(days=7)
    sunday = this_monday - timedelta(days=1)
    iso = monday.isocalendar()
    label = (f"{monday.day} {i18n.month_label(monday, 'nl', short=True)} tot {sunday.day} {i18n.month_label(sunday, 'nl', short=True)}" if lang == "nl"
             else f"{monday.strftime('%b')} {monday.day} to {sunday.strftime('%b')} {sunday.day}")
    return monday.astimezone(timezone.utc), this_monday.astimezone(timezone.utc), f"{iso[0]}-W{iso[1]:02d}", label


def next_monday(tz: ZoneInfo, now: Optional[datetime] = None) -> str:
    local = (now or _now()).astimezone(tz)
    days = (7 - local.weekday()) % 7 or 7
    return (local + timedelta(days=days)).strftime("%Y-%m-%d")


def one_thing(evals: list, cards: dict) -> Optional[dict]:
    """The criterion to coach next: lowest pass rate, critical items first, with the scorecard's coaching hint."""
    missed = [r for r in sc.criteria_rates(evals) if r["pass_rate"] is not None and r["pass_rate"] < 100]
    if not missed:
        return None
    missed.sort(key=lambda r: (not r["critical"], r["pass_rate"], -r["graded"]))
    r = missed[0]
    card = cards.get(str(r.get("scorecard_id") or "")) or {}
    hint = next((c.get("hint") for c in card.get("criteria") or [] if c.get("id") == r["id"]), "") or ""
    return {"text": r["text"], "critical": bool(r["critical"]), "pass_rate": r["pass_rate"], "passed": r["passed"], "graded": r["graded"], "hint": hint}


async def build_digest(db, store: dict, now: Optional[datetime] = None) -> dict:
    tz = store_tz(store)
    lang = loc.dialect(loc.key_of(store))
    start, end, key, label = last_week(tz, now, lang)
    sid = str(store["_id"])
    evals = await db[sc.EVAL_COLL].find({"store_id": sid, "is_mystery_shop": {"$ne": True}, "call_at": {"$gte": start - timedelta(days=7), "$lt": end}}).sort("call_at", -1).to_list(3000)
    cur = [e for e in evals if sc._dt(e) >= start]
    prev = [e for e in evals if sc._dt(e) < start]
    card_ids = [ObjectId(e["scorecard_id"]) for e in cur if ObjectId.is_valid(str(e.get("scorecard_id") or ""))]
    cards = {str(c["_id"]): c async for c in db[sc.COLL].find({"_id": {"$in": card_ids}}, {"criteria": 1})} if card_ids else {}
    by_rep: dict = {}
    for e in cur:
        by_rep.setdefault(str(e.get("user_id")), []).append(e)
    prev_by_rep: dict = {}
    for e in prev:
        prev_by_rep.setdefault(str(e.get("user_id")), []).append(e)
    ids = [ObjectId(u) for u in by_rep if ObjectId.is_valid(u)]
    users = {str(u["_id"]): u async for u in db.users.find({"_id": {"$in": ids}}, {"name": 1, "first_name": 1})} if ids else {}
    reps = []
    for uid, evs in by_rep.items():
        avg = sc._avg([e.get("score_pct") for e in evs])
        pavg = sc._avg([e.get("score_pct") for e in prev_by_rep.get(uid, [])])
        reps.append({"user_id": uid, "name": users.get(uid, {}).get("name") or evs[0].get("rep_name") or "Rep", "count": len(evs), "avg_score": avg, "prev_avg": pavg,
                     "delta": (avg - pavg) if (avg is not None and pavg is not None) else None, "critical_misses": sum(len(e.get("critical_misses") or []) for e in evs),
                     "unread_coaching": sc.unread_coaching(evs), "best": max((e.get("score_pct") for e in evs if e.get("score_pct") is not None), default=None), "one_thing": one_thing(evs, cards)})
    reps.sort(key=lambda r: (-(r["avg_score"] if r["avg_score"] is not None else -1), -r["count"]))
    avg = sc._avg([e.get("score_pct") for e in cur])
    pavg = sc._avg([e.get("score_pct") for e in prev])
    return {"store": {"id": sid, "name": store.get("name") or "your store"}, "week": key, "label": label, "start": start, "end": end, "reps": reps, "language": lang,
            "team": {"calls": len(cur), "prev_calls": len(prev), "avg_score": avg, "prev_avg": pavg, "delta": (avg - pavg) if (avg is not None and pavg is not None) else None,
                     "critical_misses": sum(len(e.get("critical_misses") or []) for e in cur), "reps": len(reps), "unread_coaching": sc.unread_coaching(cur)}}


def _signed(v) -> str:
    return f"{'+' if v > 0 else ''}{v}"


def digest_line(d: dict) -> str:
    t = d["team"]
    if d.get("language") == "nl":
        if not t["calls"]:
            return f"Er zijn {d['label']} geen gesprekken beoordeeld."
        parts = [f"{t['calls']} gesprek{'ken' if t['calls'] != 1 else ''} beoordeeld {d['label']} bij {t['reps']} medewerker{'s' if t['reps'] != 1 else ''}"]
        if t["avg_score"] is not None:
            parts.append(f"teamgemiddelde {t['avg_score']}%" + (f" ({_signed(t['delta'])} t.o.v. de week ervoor)" if t["delta"] is not None else ""))
        if t["critical_misses"]:
            parts.append(f"{t['critical_misses']} kritieke misser{'s' if t['critical_misses'] != 1 else ''}")
        if t["unread_coaching"]:
            parts.append(f"{t['unread_coaching']} coachingnotitie{'s' if t['unread_coaching'] != 1 else ''} nog niet gelezen")
        return ", ".join(parts) + "."
    if not t["calls"]:
        return f"No calls were graded {d['label']}."
    parts = [f"{t['calls']} call{'s' if t['calls'] != 1 else ''} graded {d['label']} across {t['reps']} rep{'s' if t['reps'] != 1 else ''}"]
    if t["avg_score"] is not None:
        parts.append(f"team average {t['avg_score']}%" + (f" ({_signed(t['delta'])} vs the week before)" if t["delta"] is not None else ""))
    if t["critical_misses"]:
        parts.append(f"{t['critical_misses']} critical miss{'es' if t['critical_misses'] != 1 else ''}")
    if t["unread_coaching"]:
        parts.append(f"{t['unread_coaching']} coaching note{'s' if t['unread_coaching'] != 1 else ''} not read yet")
    return ", ".join(parts) + "."


def _score_color(sc_: Optional[int]) -> str:
    return "#999" if sc_ is None else "#D64545" if sc_ < 60 else "#C9A962" if sc_ < 80 else "#2E9E5B"


def digest_html(d: dict, manager_first: str, line: str, url: str, logo_src: str) -> str:
    lang = d.get("language") or "en"
    tr = lambda k, **kw: i18n.t(lang, k, **kw)
    logo = f'<img src="{logo_src}" alt="I\'m On Social" width="72" height="72" style="width:72px;height:72px;display:block;margin:0 auto" />' if logo_src else ""
    blocks = []
    for r in d["reps"]:
        first = (r["name"] or "Rep").split(" ")[0]
        delta = f'<span style="color:{"#2E9E5B" if r["delta"] > 0 else "#D64545" if r["delta"] < 0 else "#777"};font-weight:700">{tr("dig.vs", v=_signed(r["delta"]))}</span>' if r["delta"] is not None else f'<span style="color:#777">{tr("dig.first_week")}</span>'
        meta = [tr("dig.calls" if r["count"] == 1 else "dig.calls_p", n=r["count"]), tr("dig.best", v=r["best"]) if r["best"] is not None else "", tr("dig.crit_n" if r["critical_misses"] == 1 else "dig.crit_np", n=r["critical_misses"]) if r["critical_misses"] else tr("dig.no_crit")]
        unread = (f'<span style="display:inline-block;background:#fff3d6;color:#8a5a00;border-radius:8px;padding:2px 8px;font-size:12px;font-weight:700;margin-left:6px">{tr("dig.unread", n=r["unread_coaching"])}</span>'
                  if r["unread_coaching"] else f'<span style="display:inline-block;background:#e8f6ec;color:#2E9E5B;border-radius:8px;padding:2px 8px;font-size:12px;font-weight:700;margin-left:6px">{tr("dig.read_all")}</span>')
        ot = r.get("one_thing")
        crit_tag = f' <span style="color:#D64545;font-size:11px">{tr("dig.critical")}</span>' if ot and ot["critical"] else ""
        hint_html = f'<div style="font-size:13px;color:#444;margin-top:3px;font-style:italic">{_esc(ot["hint"])}</div>' if ot and ot.get("hint") else ""
        coach = (f'<div style="margin-top:8px;background:#f7f3e8;border-left:3px solid #C9A962;border-radius:8px;padding:8px 10px">'
                 f'<div style="font-size:10.5px;letter-spacing:1px;color:#8a6d1f;font-weight:800">{tr("dig.coach_on", name=_esc(first.upper()))}</div>'
                 f'<div style="font-size:14px;color:#111;font-weight:700;margin-top:2px">{_esc(ot["text"])}{crit_tag} <span style="color:#777;font-weight:600;font-size:12px">· {tr("dig.hit", a=ot["passed"], b=ot["graded"])}</span></div>'
                 f'{hint_html}</div>') if ot else f'<div style="margin-top:8px;font-size:13px;color:#2E9E5B;font-weight:700">{tr("dig.perfect")}</div>'
        blocks.append(f'<div style="border-top:1px solid #eee;padding:14px 0">'
                      f'<div style="display:flex;justify-content:space-between;align-items:center"><span style="font-size:16px;font-weight:800;color:#111">{_esc(r["name"])}</span>'
                      f'<span style="font-size:22px;font-weight:800;color:{_score_color(r["avg_score"])}">{r["avg_score"] if r["avg_score"] is not None else "-"}%</span></div>'
                      f'<div style="font-size:12.5px;color:#666;margin-top:2px">{_esc(" · ".join(m for m in meta if m))} · {delta}{unread}</div>{coach}</div>')
    body = "".join(blocks) or f'<p style="font-size:14px;color:#666;padding:12px 0">{tr("dig.none")}</p>'
    t = d["team"]
    boxes = "".join(
        f'<td style="padding:6px"><div style="background:#f7f3e8;border-radius:12px;padding:12px 10px;text-align:center"><div style="font-size:20px;font-weight:800;color:#111">{_esc(str(v))}</div>'
        f'<div style="font-size:10px;letter-spacing:1px;color:#777;text-transform:uppercase;margin-top:2px">{_esc(k)}</div></div></td>'
        for k, v in ((tr("dig.box.calls"), t["calls"]), (tr("dig.box.avg"), f"{t['avg_score']}%" if t["avg_score"] is not None else tr("pdf.na")), (tr("dig.box.crit"), t["critical_misses"]), (tr("dig.box.unread"), t["unread_coaching"])))
    return f"""<div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:600px;margin:0 auto;padding:20px;background:#f5f3ee">
  <div style="background:#fff;border-radius:18px;overflow:hidden;border:1px solid #e6e1d6">
    <div style="text-align:center;padding:26px 20px 14px;border-bottom:1px solid #eee">{logo}
      <p style="margin:10px 0 0;font-size:11px;letter-spacing:2px;color:#C9A962;font-weight:800">{tr("dig.kicker")}</p>
    </div>
    <div style="padding:26px 30px">
      <h1 style="font-size:20px;line-height:1.3;margin:0 0 6px;color:#111">{_esc(d["store"]["name"])}: {_esc(d["label"])}</h1>
      <p style="font-size:15px;line-height:1.65;margin:0 0 14px;color:#1a1a1a">{_esc(tr("dig.morning", name=manager_first, line=line))}</p>
      <table role="presentation" style="width:100%;border-collapse:collapse;margin:0 0 10px"><tr>{boxes}</tr></table>
      {body}
      <p style="margin:22px 0 10px;text-align:center"><a href="{url}" style="background:#C9A962;color:#111;text-decoration:none;font-weight:800;padding:14px 26px;border-radius:12px;display:inline-block;font-size:15px">{tr("dig.open")}</a></p>
      <p style="font-size:12.5px;color:#666;line-height:1.6;margin:0">{_esc(tr("dig.hint"))}</p>
    </div>
  </div>
  <p style="text-align:center;margin:18px 0 0;color:#999;font-size:12px">I'm On Social LLC · 1741 Lunford Ln, Riverton, UT 84065 · {_esc(tr("dig.footer", store=d["store"]["name"]))}</p>
</div>"""


async def recipients(db, store_id: Optional[str]) -> list:
    """Managers who get the digest: the store's managers and admins (or the org's admins when the store has none), with an email, not opted out."""
    if not store_id:
        return []
    vals = [store_id] + ([ObjectId(store_id)] if ObjectId.is_valid(store_id) else [])
    proj = {"name": 1, "first_name": 1, "email": 1, "role": 1, OPT_OUT_FIELD: 1}
    users = await db.users.find({"role": {"$in": DIGEST_ROLES}, "status": {"$ne": "deactivated"}, "$or": [{"store_id": {"$in": vals}}, {"store_ids": {"$in": vals}}]}, proj).to_list(50)
    if not users and ObjectId.is_valid(store_id):
        store = await db.stores.find_one({"_id": ObjectId(store_id)}, {"organization_id": 1})
        if store and store.get("organization_id"):
            users = await db.users.find({"role": "org_admin", "organization_id": store["organization_id"], "status": {"$ne": "deactivated"}}, proj).to_list(20)
    return [u for u in users if (u.get("email") or "").strip() and "@" in u["email"] and not u.get(OPT_OUT_FIELD)]


async def send_digest(db, store: dict, to_users: list, actor: Optional[dict] = None, reason: str = "manual", now: Optional[datetime] = None, digest: Optional[dict] = None) -> dict:
    """One personalised email per manager. Logs every send; stamps the store so the scheduler does not repeat the week."""
    key = os.environ.get("RESEND_API_KEY")
    if not key:
        return {"ok": False, "error": "Email is not configured"}
    d = digest or await build_digest(db, store, now)
    line = digest_line(d)
    url = f"{scr._app_url()}/scorecards/team"
    import resend
    resend.api_key = key
    sender = os.environ.get("SENDER_EMAIL", "notifications@send.imonsocial.com")
    logo = logo_b64()
    ts = _now()
    sent = failed = 0
    for u in to_users:
        to = (u.get("email") or "").strip().lower()
        first = (u.get("first_name") or (u.get("name") or "").split(" ")[0] or "there")
        payload = {"from": f"I'm On Social <{sender}>", "to": [to], "reply_to": os.environ.get("REPORT_REPLY_TO", "support@imonsocial.com"),
                   "subject": i18n.t(d.get("language"), "dig.subject", store=d['store']['name'], label=d['label']), "html": digest_html(d, first, line, url, "cid:imos-logo"), "text": f"{line}\n\n{i18n.t(d.get('language'), 'dig.open')}: {url}"}
        if logo:
            payload["attachments"] = [{"filename": "imos-logo.png", "content": logo, "content_id": "imos-logo"}]
        log = {"store_id": d["store"]["id"], "week": d["week"], "user_id": str(u["_id"]), "to": to, "reason": reason, "at": ts, "calls": d["team"]["calls"]}
        try:
            r = await asyncio.to_thread(resend.Emails.send, payload)
            await db.coaching_digest_sends.insert_one({**log, "ok": True, "email_id": (r or {}).get("id"), "summary": line})
            sent += 1
        except Exception as e:
            logger.warning(f"[CoachingDigest] send to {to} failed for {d['store']['name']}: {e}")
            await db.coaching_digest_sends.insert_one({**log, "ok": False, "error": str(e)[:300]})
            failed += 1
    if sent and ObjectId.is_valid(d["store"]["id"]):
        await db.stores.update_one({"_id": ObjectId(d["store"]["id"])}, {"$set": {"coaching_digest.last_sent_week": d["week"], "coaching_digest.last_sent_at": ts, "coaching_digest.last_sent_count": sent}})
    if not sent:
        return {"ok": False, "error": "The email did not go out, try again", "failed": failed, "week": d["week"], "label": d["label"]}
    return {"ok": True, "sent": sent, "failed": failed, "week": d["week"], "label": d["label"], "summary": line, "calls": d["team"]["calls"]}


def due_now(store: dict, now: Optional[datetime] = None) -> bool:
    """Monday (or Tuesday catch-up) after 8am store time, not yet sent for last week."""
    cfg = store.get("coaching_digest") or {}
    if cfg.get("enabled") is False:
        return False
    tz = store_tz(store)
    local = (now or _now()).astimezone(tz)
    if local.weekday() > 1 or local.hour < SEND_HOUR_LOCAL:
        return False
    return cfg.get("last_sent_week") != last_week(tz, now)[2]


async def send_due_digests(db, now: Optional[datetime] = None) -> int:
    """Scheduler tick (hourly). Only stores with graded calls in the last two weeks are even looked at."""
    since = (now or _now()) - timedelta(days=14)
    n = 0
    for sid in await db[sc.EVAL_COLL].distinct("store_id", {"call_at": {"$gte": since}, "is_mystery_shop": {"$ne": True}}):
        if not sid or not ObjectId.is_valid(str(sid)):
            continue
        store = await db.stores.find_one({"_id": ObjectId(str(sid))})
        if not store or not due_now(store, now):
            continue
        try:
            d = await build_digest(db, store, now)
            people = await recipients(db, str(sid))
            if not d["team"]["calls"] or not people:
                await db.stores.update_one({"_id": store["_id"]}, {"$set": {"coaching_digest.last_sent_week": d["week"], "coaching_digest.last_skipped": "no graded calls" if not d["team"]["calls"] else "no managers with email"}})
                continue
            res = await send_digest(db, store, people, reason="auto", now=now, digest=d)
            if res.get("ok"):
                n += 1
            else:
                await db.stores.update_one({"_id": store["_id"]}, {"$set": {"coaching_digest.last_sent_week": d["week"], "coaching_digest.last_error": res.get("error")}})
        except Exception as e:
            logger.warning(f"[CoachingDigest] failed for store {sid}: {e}")
    return n


def serialize_for(user: dict, store: Optional[dict], people: list, now: Optional[datetime] = None) -> dict:
    tz = store_tz(store)
    cfg = (store or {}).get("coaching_digest") or {}
    enabled = not user.get(OPT_OUT_FIELD)
    return {"enabled": enabled, "email": user.get("email") or "", "store": {"id": str(store["_id"]), "name": store.get("name")} if store else None,
            "last_week_label": last_week(tz, now)[3], "next_send": next_monday(tz, now) if enabled and store else None, "recipients": len(people),
            "recipient_names": [((u.get("name") or u.get("email") or "").split(" ")[0]) for u in people][:6],
            "last_sent_week": cfg.get("last_sent_week"), "last_sent_at": cfg.get("last_sent_at").isoformat() if cfg.get("last_sent_at") else None, "last_error": cfg.get("last_error")}
