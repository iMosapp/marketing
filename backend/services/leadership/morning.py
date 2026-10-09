"""Morning brief: the Chief of Staff's operating review pushed to the founder's phone at a local hour of their choosing.
Settings live on the lt_companies document; the hourly cron tick decides whether it is time. One review call, one push, once per local day."""
import logging
import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from bson import ObjectId

from services import command_center as cc
from services.leadership import core
from services.leadership import orchestrator as rt

logger = logging.getLogger(__name__)
DEFAULT = {"enabled": False, "hour": 7, "user_id": None, "user_name": None, "timezone": None, "last_sent_day": None, "last_sent_at": None, "last_error": None, "last_headline": None, "last_pushed": None}
TITLE = "Morning brief from your Chief of Staff"
LINK = "/admin/command-center/team?view=roster"
CRON_MINUTE = 5


def _tz(name) -> str | None:
    try:
        return name if name and ZoneInfo(name) else None
    except (KeyError, ValueError, TypeError):
        return None


async def _resolve_tz(mb: dict) -> str:
    if _tz(mb.get("timezone")):
        return mb["timezone"]
    if mb.get("user_id"):
        from routers.user_schedule import resolve_user_tz
        return await resolve_user_tz(str(mb["user_id"]))
    return "America/Denver"


def _next(mb: dict, tzname: str, now: datetime | None = None) -> datetime:
    now = (now or datetime.now(timezone.utc)).astimezone(ZoneInfo(tzname))
    target = now.replace(hour=int(mb["hour"]), minute=CRON_MINUTE, second=0, microsecond=0)
    if target <= now or mb.get("last_sent_day") == now.strftime("%Y-%m-%d"):
        target += timedelta(days=1)
    return target


async def settings(db, company_id: str) -> dict:
    mb = {**DEFAULT, **((await core.company(db, company_id)).get("morning_brief") or {})}
    tzname = await _resolve_tz(mb)
    out = {k: (cc._iso(v) if isinstance(v, datetime) else v) for k, v in mb.items()}
    out.update({"timezone": tzname, "next_send": _next(mb, tzname).isoformat() if mb["enabled"] else None, "link": LINK, "title": TITLE})
    return out


async def update(db, company_id: str, me: dict, body: dict) -> dict:
    cur = {**DEFAULT, **((await core.company(db, company_id)).get("morning_brief") or {})}
    upd = {}
    if body.get("enabled") is not None:
        upd["enabled"] = bool(body["enabled"])
    if body.get("hour") is not None:
        h = int(body["hour"])
        if not 0 <= h <= 23:
            raise ValueError("Pick an hour between 0 and 23")
        upd["hour"] = h
    if body.get("timezone"):
        if not _tz(body["timezone"]):
            raise ValueError("Unknown timezone")
        upd["timezone"] = body["timezone"]
    if upd.get("enabled", cur["enabled"]):
        upd["user_id"], upd["user_name"] = str(me["_id"]), cc._who(me)["name"]
    if not upd:
        raise ValueError("Nothing to change")
    await db[core.COMPANIES].update_one({"_id": company_id}, {"$set": {**{f"morning_brief.{k}": v for k, v in upd.items()}, "updated_at": core._now()}})
    keys = ("enabled", "hour", "timezone")
    await core.audit(db, company_id, me, "morning_brief_updated", {"kind": "company", "id": company_id}, before={k: cur.get(k) for k in keys}, after={k: {**cur, **upd}.get(k) for k in keys})
    return await settings(db, company_id)


def _plain(s: str) -> str:
    return re.sub(r"\s*\[(?:F\d+|CC|D\d+|peer_assessments)\]", "", s or "").strip()


def compose(review: dict) -> str:
    parts = [_plain(review.get("headline")) or "Your operating review is ready."]
    if review.get("one_big_thing"):
        parts.append(f"One Big Thing: {_plain(review['one_big_thing'])}")
    n = len(review.get("pending_decisions") or [])
    if n:
        parts.append(f"{n} decision{'s' if n != 1 else ''} waiting on you.")
    first = ((review.get("next_actions") or [{}])[0]).get("action")
    if first:
        parts.append(f"First move: {_plain(first)}")
    body = " ".join(p if p.endswith((".", "!", "?")) else p + "." for p in parts)
    return body if len(body) <= 240 else body[:237].rsplit(" ", 1)[0] + "..."


async def send(db, company_id: str, me: dict, reason: str = "scheduled") -> dict:
    """One review call, one push. Stamps the founder's local day so the hourly tick never sends twice; a manual send counts as today's brief."""
    mb = {**DEFAULT, **((await core.company(db, company_id)).get("morning_brief") or {})}
    tzname = await _resolve_tz({**mb, "user_id": mb.get("user_id") or str(me["_id"])})
    today = datetime.now(ZoneInfo(tzname)).strftime("%Y-%m-%d")
    actor = me if reason == "manual" else None
    try:
        review = await rt.review(db, company_id, me)
    except Exception as e:
        await db[core.COMPANIES].update_one({"_id": company_id}, {"$set": {"morning_brief.last_error": str(e)[:300]}})
        await core.audit(db, company_id, actor, "morning_brief_failed", {"kind": "company", "id": company_id}, reason=str(e)[:300])
        raise
    body = compose(review)
    pushed = 0
    try:
        from routers.push_notifications import send_push_to_user
        pushed = int(await send_push_to_user(str(me["_id"]), TITLE, body, url=LINK, icon="sparkles") or 0)
    except Exception as e:  # noqa: BLE001 - the brief is still on record in the Team screen
        logger.warning("[Leadership] morning brief push failed: %s", e)
    latest = await db[rt.REVIEWS].find_one({"company_id": company_id}, {"_id": 1}, sort=[("generated_at", -1)])
    if latest:
        await db[rt.REVIEWS].update_one({"_id": latest["_id"]}, {"$set": {"source": f"morning_brief:{reason}", "pushed": pushed}})
    await db[core.COMPANIES].update_one({"_id": company_id}, {"$set": {"morning_brief.last_sent_day": today, "morning_brief.last_sent_at": core._now(), "morning_brief.last_error": None, "morning_brief.last_headline": review.get("headline"), "morning_brief.last_pushed": pushed}})
    await core.audit(db, company_id, actor, "morning_brief_sent", {"kind": "review", "id": str(latest["_id"]) if latest else company_id}, after={"pushed": pushed, "reason": reason, "day": today})
    return {"sent": True, "pushed": pushed, "title": TITLE, "body": body, "review": review, "timezone": tzname, "day": today}


async def tick(db) -> dict:
    """Hourly from the platform cron: every company with the brief on gets it once per local day at the chosen hour."""
    out = {"checked": 0, "sent": 0, "skipped": [], "errors": []}
    async for co in db[core.COMPANIES].find({"morning_brief.enabled": True}):
        out["checked"] += 1
        cid, mb = co["_id"], {**DEFAULT, **(co.get("morning_brief") or {})}
        try:
            tzname = await _resolve_tz(mb)
            now = datetime.now(ZoneInfo(tzname))
            if now.hour != int(mb["hour"]):
                out["skipped"].append(f"{cid}: it is {now.hour}:00 in {tzname}, brief is at {mb['hour']}:00")
                continue
            if mb.get("last_sent_day") == now.strftime("%Y-%m-%d"):
                out["skipped"].append(f"{cid}: already sent today")
                continue
            me = await db.users.find_one({"_id": ObjectId(mb["user_id"])}) if ObjectId.is_valid(str(mb.get("user_id") or "")) else None
            if not me:
                out["skipped"].append(f"{cid}: no founder on record")
                continue
            await send(db, cid, me, reason="scheduled")
            out["sent"] += 1
        except Exception as e:  # noqa: BLE001 - one company's failure must not stop the others
            logger.warning("[Leadership] morning brief for %s failed: %s", cid, e)
            out["errors"].append(f"{cid}: {str(e)[:200]}")
    return out
