"""Time frames in a search ask: 'last February', 'three months ago', 'people I met in October', 'last week', 'in the past 3 months', 'in 2025'.
Deterministic (no LLM). parse() returns the window [start, end) in UTC, a label Jessi can say, and the phrase to drop before keyword search."""
import calendar
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

_MONTH_NAMES = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]
MONTHS = {**{m: i + 1 for i, m in enumerate(_MONTH_NAMES)}, **{m[:3]: i + 1 for i, m in enumerate(_MONTH_NAMES)}, "sept": 9}
_NUMS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
         "eleven": 11, "twelve": 12, "a couple of": 2, "couple of": 2, "a couple": 2, "a few": 3, "few": 3, "several": 4}
_N = r"(?P<n>\d{1,3}|a couple of|couple of|a couple|a few|few|several|an?|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)"
_U = r"(?P<u>day|week|month|year)s?"
_M = r"(?P<m>" + "|".join(sorted(MONTHS, key=len, reverse=True)) + r")\.?"
_Q = r"(?P<q>last|this|in|during|back in|since|from|around|early|late|mid|mid-|of)"
_Y = r"(?P<y>(?:19|20)\d{2})"

ROLLING = re.compile(r"\b(?:in\s+|over\s+|within\s+)?(?:the\s+)?(?:last|past)\s+" + _N + r"\s+" + _U + r"\b")
AGO = re.compile(r"\b(?:about\s+|around\s+|like\s+|maybe\s+)?" + _N + r"\s+" + _U + r"\s+ago\b")
MONTH = re.compile(r"\b" + _Q + r"[\s-]+" + _M + r"(?:,?\s+(?:of\s+)?" + _Y + r")?\b")
MONTH_Y = re.compile(r"\b(?P<q>)" + _M + r",?\s+" + _Y + r"\b")
RELATIVE = re.compile(r"\b(?P<q>last|this|past|previous)\s+(?P<u>week|month|year)\b")
YEAR = re.compile(r"\b(?P<q>in|during|back in|since|from)\s+" + _Y + r"\b")
DAY = re.compile(r"\b(?P<d>yesterday|today|this morning)\b")


def _n(s: str) -> int:
    return int(s) if s.isdigit() else _NUMS.get(s, 1)


def _month_start(y: int, m: int) -> datetime:
    return datetime(y, m, 1, tzinfo=timezone.utc)


def _add_months(d: datetime, k: int) -> datetime:
    y, m = divmod(d.month - 1 + k, 12)
    y, m = d.year + y, m + 1
    return d.replace(year=y, month=m, day=min(d.day, calendar.monthrange(y, m)[1]))


def _span(d: datetime, unit: str, k: int) -> datetime:
    if unit == "day":
        return d + timedelta(days=k)
    if unit == "week":
        return d + timedelta(weeks=k)
    if unit == "month":
        return _add_months(d, k)
    return _add_months(d, 12 * k)


def _fmt(d: datetime) -> str:
    return f"{d.strftime('%b')} {d.day}, {d.year}"


def parse(text: str, now: Optional[datetime] = None) -> Optional[dict]:
    """{start, end, label, phrase} for the first time frame in the ask, else None."""
    now = now or datetime.now(timezone.utc)
    t = (text or "").lower()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    m = ROLLING.search(t)
    if m:
        n, u = _n(m["n"]), m["u"]
        return {"start": _span(now, u, -n), "end": now, "label": f"the last {n} {u}{'s' if n != 1 else ''}", "phrase": m.group(0)}

    m = AGO.search(t)
    if m:
        n, u = _n(m["n"]), m["u"]
        target = _span(now, u, -n)
        slack = {"day": timedelta(days=1), "week": timedelta(days=4), "month": timedelta(days=21), "year": timedelta(days=183)}[u]
        start, end = target - slack, min(now, target + slack)
        return {"start": start, "end": end, "label": f"about {n} {u}{'s' if n != 1 else ''} ago ({_fmt(start)} to {_fmt(end)})", "phrase": m.group(0)}

    m = MONTH.search(t) or MONTH_Y.search(t)
    if m:
        mon, q = MONTHS[m["m"]], (m["q"] or "")
        if m["y"]:
            y = int(m["y"])
        elif q == "last":
            y = now.year if mon < now.month else now.year - 1
        elif q == "this":
            y = now.year
        else:
            y = now.year if mon <= now.month else now.year - 1
        start = _month_start(y, mon)
        if q == "since":
            return {"start": start, "end": now, "label": f"since {start.strftime('%B %Y')}", "phrase": m.group(0)}
        end = _add_months(start, 1)
        return {"start": start, "end": min(end, now) if end > now else end, "label": start.strftime("%B %Y"), "phrase": m.group(0)}

    m = RELATIVE.search(t)
    if m:
        q, u = m["q"], m["u"]
        if q in ("last", "past", "previous"):
            # how people say it: "last month" = the last few weeks, not strictly the previous calendar month (same lookbacks Live Jessi uses)
            back = {"week": 10, "month": 45, "year": 400}[u]
            return {"start": now - timedelta(days=back), "end": now, "label": f"the last {u}", "phrase": m.group(0)}
        if u == "week":
            cur = today - timedelta(days=today.weekday())
        elif u == "month":
            cur = _month_start(now.year, now.month)
        else:
            cur = datetime(now.year, 1, 1, tzinfo=timezone.utc)
        return {"start": cur, "end": now, "label": f"this {u}", "phrase": m.group(0)}

    m = YEAR.search(t)
    if m:
        y = int(m["y"])
        start = datetime(y, 1, 1, tzinfo=timezone.utc)
        end = now if m["q"] == "since" else min(now, datetime(y + 1, 1, 1, tzinfo=timezone.utc))
        return {"start": start, "end": end, "label": f"since {y}" if m["q"] == "since" else str(y), "phrase": m.group(0)}

    m = DAY.search(t)
    if m:
        if m["d"] == "yesterday":
            return {"start": today - timedelta(days=1), "end": today, "label": "yesterday", "phrase": m.group(0)}
        return {"start": today, "end": now, "label": "today", "phrase": m.group(0)}
    return None


def strip(text: str, win: Optional[dict]) -> str:
    """The ask without its time frame, so 'October' never becomes a keyword."""
    if not win:
        return text or ""
    return re.sub(r"\s{2,}", " ", re.sub(re.escape(win["phrase"]), " ", text or "", count=1, flags=re.IGNORECASE)).strip(" ,.?")


def period(value: str) -> Optional[tuple]:
    """A stored partial date ('2026', '2026-10', '2026-10-16') as [start, end)."""
    v = (value or "").strip()
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
            d = datetime.strptime(v, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            return d, d + timedelta(days=1)
        if re.fullmatch(r"\d{4}-\d{2}", v):
            d = datetime.strptime(v, "%Y-%m").replace(tzinfo=timezone.utc)
            return d, _add_months(d, 1)
        if re.fullmatch(r"\d{4}", v):
            return datetime(int(v), 1, 1, tzinfo=timezone.utc), datetime(int(v) + 1, 1, 1, tzinfo=timezone.utc)
    except ValueError:
        return None
    return None


def overlaps(a: tuple, win: dict) -> bool:
    return a[0] < win["end"] and a[1] > win["start"]
