"""Active intent: buying signals with a window. Phase is computed when read (active 0-14 days, aging to the window, dormant after), never stored,
so no cron is needed and old dates stay honest. Only real customer actions refresh a window; campaign sends and opens never do."""
import re
from datetime import datetime, timedelta
from typing import Optional

from services.intelligence import facts as F

NOT_SHOPPING_RX = re.compile(r"\b(not|no longer|aren'?t|isn'?t|am not|i'?m not)\s+(currently\s+|really\s+|actively\s+)?(shopping|in the market|looking|buying|interested)\b|\bhold off\b|\bon hold\b|\bnot right now\b|\bnot at this time\b", re.I)
PURCHASED_ELSEWHERE_RX = re.compile(r"\b(bought|purchased|got|picked up|ended up (buying|getting|going with)|went with|already (bought|purchased|have))\b[^.!?]{0,60}\b(elsewhere|somewhere else|another (dealer|dealership|place|store)|from (another|a different)|at another|out of state|online|private party|carvana|carmax|vroom)\b|\balready (bought|purchased) (one|a|the)\b", re.I)
CLOSE_REASONS = ("purchased", "lost", "cancelled", "declined")


def detect_not_shopping(text: str) -> bool:
    return bool(text) and bool(NOT_SHOPPING_RX.search(text))


def detect_purchased_elsewhere(text: str) -> bool:
    return bool(text) and bool(PURCHASED_ELSEWHERE_RX.search(text))


def window_days(settings: dict, category: Optional[str]) -> int:
    return int((settings.get("intent_windows") or {}).get(category or "", settings.get("intent_window_days", 45)))


def make(contact: dict, settings: dict, *, key: str, domain: str, statement: str, value, occurred_at: datetime, source: dict, category: str = "purchase",
         confidence: str = "medium", actor: Optional[dict] = None, recorded_at: Optional[datetime] = None, precision: str = "exact") -> dict:
    f = F.make(contact, layer="intent", domain=domain, key=key, statement=statement, value=value, occurred_at=occurred_at, precision=precision, source=source,
               confidence=confidence, actor=actor, recorded_at=recorded_at, category=category, active_until=occurred_at + timedelta(days=window_days(settings, category)))
    f["status"] = "current"
    return f


def phase(f: dict, settings: dict, now: Optional[datetime] = None) -> Optional[dict]:
    """active | aging | dormant for a current intent fact; None for anything else."""
    if f.get("layer") != "intent" or f.get("status") != "current":
        return None
    now = now or F.now_utc()
    last = f.get("last_signal_at") or f["occurred_at"]
    days = max(0, (now - last).days)
    win = window_days(settings, f.get("category"))
    p = "active" if days <= int(settings.get("intent_fresh_days", 14)) else ("aging" if days <= win else "dormant")
    return {"phase": p, "days_since_signal": days, "window_days": win, "active_until": F.iso(f.get("active_until"))}


async def refresh(db, contact_id: str, settings: dict, at: datetime, signal: str, actor: Optional[dict] = None) -> int:
    """A real customer action (inquiry, reply, appointment, inbound call, statement) extends every current intent window. Passive activity does not."""
    if signal not in F.REFRESH_SIGNALS:
        return 0
    n = 0
    for f in await F.load(db, {"contact_id": contact_id, "layer": "intent", "status": "current", "key": {"$ne": "buying.status"}}):
        last = f.get("last_signal_at") or f["occurred_at"]
        if at <= last:
            continue
        await db[F.FACTS].update_one({"_id": f["_id"]}, {"$set": {"last_signal_at": at, "active_until": at + timedelta(days=window_days(settings, f.get("category"))), "updated_at": F.now_utc()}})
        await F._event(db, f, "window_refreshed", actor, after={"signal": signal, "at": F.iso(at)})
        n += 1
    return n


MAKES = {"ford", "chevrolet", "chevy", "gmc", "ram", "dodge", "jeep", "toyota", "honda", "nissan", "kia", "hyundai", "subaru", "mazda", "volkswagen", "vw", "bmw", "mercedes", "audi", "lexus", "acura",
         "infiniti", "cadillac", "buick", "lincoln", "chrysler", "tesla", "volvo", "porsche", "genesis", "mitsubishi", "mini", "jaguar", "land", "rover", "rivian", "polestar", "fiat", "alfa", "romeo"}
GENERIC = {"super", "duty", "truck", "suv", "car", "vehicle", "new", "used", "the", "a", "an", "crew", "cab", "4x4", "awd", "4wd", "2wd", "lariat", "xlt", "xl", "limited", "platinum", "premium", "sport", "base", "lt", "ltz", "rst", "slt", "sle", "denali", "trd", "se", "le", "xle", "ex", "lx", "touring"}


def _tokens(s) -> set:
    label = s.get("label") if isinstance(s, dict) else s
    if isinstance(s, dict) and not label:
        label = " ".join(str(s.get(k) or "") for k in ("year", "make", "model", "trim"))
    return {t for t in re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", str(label or "").lower()) if not t.isdigit() and t not in GENERIC}


def matches(a, b) -> bool:
    """Same vehicle? Model tokens decide (F-150 vs Explorer are both Ford but not the same thing); a make-only overlap counts only when neither side names a model."""
    ta, tb = _tokens(a), _tokens(b)
    ma, mb = ta - MAKES, tb - MAKES
    if ma and mb:
        return bool(ma & mb)
    return bool(ta & tb)


def _year(x) -> Optional[str]:
    text = x.get("label") if isinstance(x, dict) else str(x or "")
    m = re.search(r"\b(19[89]\d|20[0-4]\d)\b", str(x.get("year")) if isinstance(x, dict) and x.get("year") else text or "")
    return m.group(1) if m else None


def same_vehicle(a, b) -> bool:
    """A specific car, not a shopping interest: model tokens must match AND, when both sides name a model year, the years must agree (trading a 2019 F-150 leaves the 2020 F-150 alone)."""
    if not matches(a, b):
        return False
    ya, yb = _year(a), _year(b)
    return not (ya and yb) or ya == yb


async def close(db, contact_id: str, *, reason: str, at: datetime, match: Optional[object] = None, actor: Optional[dict] = None, note: str = "") -> list:
    """A purchase, lost deal or cancellation closes the relevant intents right away. With `match` (a vehicle label/dict) only matching interests close;
    without it every current vehicle interest closes. Dates and records stay."""
    assert reason in CLOSE_REASONS
    closed = []
    for f in await F.load(db, {"contact_id": contact_id, "layer": "intent", "status": "current", "key": {"$in": ["vehicle.interest", "buying.signal"]}}):
        if match is not None and f["key"] == "vehicle.interest" and not matches(f.get("value"), match):
            continue
        if match is not None and f["key"] == "buying.signal" and reason != "purchased":
            continue
        await db[F.FACTS].update_one({"_id": f["_id"]}, {"$set": {"status": "historical", "outcome": reason, "closed_at": at, "updated_at": F.now_utc()}})
        await F._event(db, f, "closed", actor, before={"status": "current"}, after={"status": "historical", "outcome": reason}, note=note)
        closed.append(f["_id"])
    return closed


async def replace_matching(db, contact_id: str, new_fact: dict, actor: Optional[dict] = None) -> list:
    """A fresh inquiry about a vehicle the customer already asked about: the earlier interest becomes superseded (kept, linked), so history can say 'asked about this in Jul 2025'."""
    out = []
    for f in await F.load(db, {"contact_id": contact_id, "key": "vehicle.interest", "status": "current", "_id": {"$ne": new_fact["_id"]}}):
        if matches(f.get("value"), new_fact.get("value")):
            await db[F.FACTS].update_one({"_id": f["_id"]}, {"$set": {"status": "superseded", "superseded_by": new_fact["_id"], "outcome": "replaced", "updated_at": F.now_utc()}})
            await F._event(db, f, "superseded", actor, before={"status": "current"}, after={"status": "superseded", "by": str(new_fact["_id"])}, note="newer inquiry about the same vehicle")
            out.append(f["_id"])
    if out:
        await db[F.FACTS].update_one({"_id": new_fact["_id"]}, {"$set": {"supersedes": out[0]}})
    return out


async def suppression(db, contact_id: str, now: Optional[datetime] = None) -> Optional[dict]:
    """The customer's standing 'not shopping' statement, if it is still in force."""
    now = now or F.now_utc()
    f = F.hydrate(await db[F.FACTS].find_one({"contact_id": contact_id, "key": "buying.status", "status": "current", "value.status": "not_shopping"}, sort=[("occurred_at", -1)]))
    return f if f and (f.get("active_until") or now) > now else None


async def not_shopping(db, contact: dict, settings: dict, *, at: datetime, source: dict, quote: str = "", actor: Optional[dict] = None) -> dict:
    """Explicit 'not shopping': a buying.status fact that suppresses intent assumptions for N days; open interests become history with outcome declined."""
    f = F.make(contact, layer="intent", domain="buying_status", key="buying.status", statement="Not currently shopping" + (f': "{quote[:140]}"' if quote else ""),
               value={"status": "not_shopping"}, occurred_at=at, source={**source, "quote": quote or source.get("quote")}, confidence="high" if source.get("kind") in F.CUSTOMER_SOURCES else "medium",
               actor=actor, category="status", active_until=at + timedelta(days=int(settings.get("not_shopping_days", 90))))
    f["status"] = "current"
    out = await F.record(db, f, actor)
    if out["action"] in ("created", "superseded"):
        await close(db, str(contact["_id"]), reason="declined", at=at, actor=actor, note="customer said they are not shopping")
    return out


async def lift_suppression(db, contact_id: str, by_fact: dict, actor: Optional[dict] = None) -> bool:
    """A new explicit customer action (inquiry, appointment, reply asking about a product) contradicts a standing 'not shopping' statement."""
    sup = await suppression(db, contact_id)
    if not sup:
        return False
    await db[F.FACTS].update_one({"_id": sup["_id"]}, {"$set": {"status": "superseded", "superseded_by": by_fact["_id"], "updated_at": F.now_utc()}})
    await F._event(db, sup, "superseded", actor, before={"status": "current"}, after={"status": "superseded", "by": str(by_fact["_id"])}, note="contradicted by a new customer action")
    return True
