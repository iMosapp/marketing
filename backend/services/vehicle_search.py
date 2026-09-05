"""Turn a customer's shopping message ("any trucks under $30k?") into inventory filters,
classify vehicles by body type, and rank the matches. Pure functions, no DB."""
import re
from typing import Optional

BODY_LABEL = {"truck": "Truck", "suv": "SUV", "sedan": "Sedan", "van": "Van", "coupe": "Coupe",
              "convertible": "Convertible", "hatchback": "Hatchback", "wagon": "Wagon"}

_EXPLICIT_BODY = {
    "truck": "truck", "trucks": "truck", "pickup": "truck", "pick-up": "truck", "pickup truck": "truck",
    "suv": "suv", "suvs": "suv", "sport utility": "suv", "sport utility vehicle": "suv", "crossover": "suv", "cuv": "suv",
    "sedan": "sedan", "van": "van", "minivan": "van", "mini van": "van", "cargo van": "van", "passenger van": "van",
    "coupe": "coupe", "convertible": "convertible", "cabriolet": "convertible", "roadster": "convertible",
    "hatchback": "hatchback", "hatch": "hatchback", "wagon": "wagon", "estate": "wagon",
}

# Checked in order: first hit wins. Vans before trucks (Ram ProMaster), SUVs before sedans (Corolla Cross).
_BODY_PATTERNS = [
    ("van", r"promaster|transit(?!\s*connect pickup)|sprinter|metris|sienna|odyssey|pacifica|voyager|carnival|sedona|grand caravan|"
            r"\bexpress\b|savana|nv ?200|nv ?[123]500|\bminivan\b|cargo van|passenger van|\bvan\b"),
    ("truck", r"f-?[1-4]50|super duty|silverado|sierra|\bram\s?[123]500|\bram\b|tacoma|tundra|colorado|canyon|ranger|frontier|"
              r"\btitan\b|ridgeline|maverick|gladiator|santa cruz|cybertruck|lightning|\br1t\b|hummer ev|\bpickup\b|"
              r"crew ?cab|double ?cab|quad ?cab|mega ?cab|super ?crew|super ?cab|regular cab|extended cab|king cab|access cab|"
              r"tradesman|big horn|laramie|\bz71\b|trail boss|\btruck\b"),
    ("suv", r"rav-?4|highlander|4-?runner|sequoia|land cruiser|venza|corolla cross|bz4x|c-?hr\b|cr-?v\b|\bpilot\b|passport|hr-?v\b|"
            r"explorer|escape|expedition|bronco|\bedge\b|mach-?e|ecosport|tahoe|suburban|equinox|traverse|blazer|trailblazer|\btrax\b|"
            r"yukon|acadia|terrain|envision|enclave|encore|wrangler|cherokee|compass|renegade|wagoneer|durango|\brogue\b|murano|"
            r"pathfinder|armada|\bkicks\b|xterra|tucson|santa fe|palisade|\bkona\b|\bvenue\b|ioniq 5|sportage|sorento|telluride|"
            r"seltos|\bniro\b|\bev6\b|\bev9\b|cx-?[3-9]0?\b|outback|forester|crosstrek|ascent|\br1s\b|\bariya\b|"
            r"lexus\s+(rx|nx|gx|lx|tx|ux)\b|\brx ?[345]50h?\b|\bnx ?[23][05]0h?\b|\bgx ?[45][56]0\b|\bx[1-7]\b|\bglc\b|\bgle\b|\bgls\b|"
            r"\bgla\b|\bglb\b|g-?class|g ?wagon|\bq[3-8]\b|e-tron|model x|model y|tiguan|\batlas\b|\btaos\b|touareg|id\.?4|xc[469]0|"
            r"macan|cayenne|range rover|discovery|defender|evoque|velar|\bmdx\b|\brdx\b|qx[5-8]0|\bsuv\b|crossover|sport utility"),
    ("convertible", r"convertible|cabriolet|roadster|spyder|spider|miata|mx-?5|\bz4\b|\bslc\b|\bslk\b"),
    ("coupe", r"mustang(?!\s*mach)|camaro|challenger|corvette|supra|gr ?86|\bbrz\b|\b370z\b|\b400z\b|nissan z\b|\bcoupe\b|2-?dr\b|2-?door"),
    ("hatchback", r"hatchback|\bhatch\b|golf(?! r wagon)|\bgti\b|veloster|\bfit\b|yaris|\bspark\b|\bbolt\b|\bleaf\b|5-?dr\b|5-?door|mini cooper"),
    ("wagon", r"\bwagon\b|sportwagen|alltrack|allroad|\bv60\b|\bv90\b"),
    ("sedan", r"camry|corolla|avalon|prius|\bcrown\b|civic|accord|insight|clarity|altima|sentra|maxima|versa|elantra|sonata|accent|"
              r"azera|\bg[789]0\b|\bk5\b|forte|optima|\brio\b|cadenza|stinger|mazda ?[36]\b|legacy|impreza|\bwrx\b|malibu|impala|cruze|"
              r"\bsonic\b|fusion|taurus|focus|fiesta|charger|chrysler 300|\bjetta\b|passat|arteon|model 3|model s|"
              r"lexus\s+(es|is|ls|gs)\b|\bes ?[23][05]0h?\b|\bis ?[23][05]0\b|[357] series|\b[35][234]\di\b|c-?class|e-?class|s-?class|"
              r"\ba[3-8]\b|\btlx\b|\bilx\b|integra|\bq50\b|\bq70\b|\bsedan\b|4-?dr\b|4-?door"),
]
_BODY_RX = [(b, re.compile(p, re.I)) for b, p in _BODY_PATTERNS]

_FEATURE_PATTERNS = {
    "electric": r"electric|\bev\b|plug-?in|phev|lightning|mach-?e|model [3sxy]\b|\bbolt\b|\bleaf\b|ioniq [56]|\bev[69]\b|id\.?4|bz4x|"
                r"cybertruck|\br1[st]\b|ariya|hummer ev|e-tron|\beq[abces]\b|\bi[47x]\b|taycan|polestar",
    "hybrid": r"hybrid|prius|insight|\bphev\b|plug-?in|e:hev|\bniro\b",
    "diesel": r"diesel|duramax|power ?stroke|cummins|ecodiesel|\btdi\b",
    "awd_4x4": r"4x4|4wd|4-?wheel|four.?wheel|\bawd\b|all.?wheel|quattro|xdrive|4matic|sh-?awd|symmetrical|4motion|trd off-?road|trd pro|\bz71\b|\btrail boss\b|\brubicon\b",
}
_FEATURE_RX = {k: re.compile(v, re.I) for k, v in _FEATURE_PATTERNS.items()}
FEATURE_LABEL = {"electric": "electric", "hybrid": "hybrid", "diesel": "diesel", "awd_4x4": "AWD/4x4"}

# customer words -> body set
_ASK_BODY = [
    (r"\b(trucks?|pick-?ups?|pickup trucks?)\b", {"truck"}),
    (r"\b(suvs?|crossovers?|sport utilit(?:y|ies))\b", {"suv"}),
    (r"\b(sedans?)\b", {"sedan"}),
    (r"\b(vans?|mini-?vans?)\b", {"van"}),
    (r"\b(convertibles?|cabriolets?|roadsters?)\b", {"convertible"}),
    (r"\b(coupes?|sports? cars?)\b", {"coupe", "convertible"}),
    (r"\b(hatchbacks?|hatch)\b", {"hatchback"}),
    (r"\b(wagons?)\b", {"wagon"}),
    (r"\b(third row|3rd row|[78][- ]?seaters?|seats [78]|family hauler)\b", {"suv", "van"}),
]
_ASK_BODY_RX = [(re.compile(p, re.I), s) for p, s in _ASK_BODY]

_ASK_FEATURE = [
    (r"\b(electric|evs?|plug-?in|phev|battery)\b", "electric"),
    (r"\b(hybrids?)\b", "hybrid"),
    (r"\b(diesels?)\b", "diesel"),
    (r"\b(4x4|4wd|four wheel drive|awd|all wheel drive|all-wheel)\b", "awd_4x4"),
]
_ASK_FEATURE_RX = [(re.compile(p, re.I), f) for p, f in _ASK_FEATURE]

_NUM = r"\$?\s*(\d[\d,]*(?:\.\d+)?)\s*(k|grand|thousand)?"
_MILES_RX = re.compile(r"(?:under|below|less than|fewer than|max(?:imum)?|up to|no more than)\s*" + _NUM + r"\s*(?:miles|mi\b|mileage|on the clock|on it)", re.I)
_LOW_MILES_RX = re.compile(r"\blow(?:er)? (?:miles|mileage)\b|\bnot (?:too )?many miles\b", re.I)
_YEAR_MIN_RX = re.compile(r"\b((?:19|20)\d\d)\s*(?:or newer|and newer|or later|and up|\+)|\b(?:newer than|after|since|at least a)\s*((?:19|20)\d\d)\b", re.I)
_YEAR_MAX_RX = re.compile(r"\b((?:19|20)\d\d)\s*(?:or older|and older|or earlier)|\b(?:older than|before)\s*((?:19|20)\d\d)\b", re.I)
_PRICE_RANGE_RX = re.compile(r"(?:between|from)?\s*" + _NUM + r"\s*(?:-|to|and|through|thru)\s*" + _NUM + r"(?![\d,]*\s*(?:miles|mi\b|mileage|seats?))", re.I)
_PRICE_MAX_RX = re.compile(r"(?:under|below|less than|no more than|max(?:imum)?|up to|at most|cheaper than|within|budget(?: is| of)?|spend(?:ing)?|afford|around|about|close to|roughly|approximately|~)\s*(?:of\s*)?" + _NUM, re.I)
_PRICE_AROUND_RX = re.compile(r"(?:around|about|close to|roughly|approximately|~|in the)\s*" + _NUM, re.I)
_PRICE_MIN_RX = re.compile(r"(?:over|above|more than|at least|starting at|starting from|minimum)\s*" + _NUM, re.I)
_LONE_PRICE_RX = re.compile(r"\$\s*(\d[\d,]*(?:\.\d+)?)\s*(k|grand|thousand)?", re.I)
_CHEAP_RX = re.compile(r"\b(cheapest|cheap|most affordable|affordable|budget|lowest price|least expensive|inexpensive|best deal|good deal)\b", re.I)
_NEWEST_RX = re.compile(r"\b(newest|latest|brand new|new model|current year)\b", re.I)

_STOP = {
    "the", "and", "you", "your", "have", "has", "does", "what", "which", "with", "how", "much", "many", "any", "are", "was",
    "for", "can", "could", "would", "come", "there", "that", "this", "one", "ones", "get", "got", "still", "about", "price",
    "pricing", "cost", "stock", "available", "availability", "color", "colour", "like", "want", "looking", "interested",
    "info", "more", "anything", "something", "under", "below", "over", "around", "between", "budget", "cheapest", "cheap",
    "affordable", "newer", "older", "than", "miles", "mileage", "low", "high", "show", "need", "hey", "hello", "please",
    "thanks", "thank", "market", "shopping", "options", "option", "sell", "selling", "guys", "yall", "all", "lot", "deal",
    "deals", "car", "cars", "vehicle", "vehicles", "ride", "rides", "used", "new", "pre", "owned", "preowned", "inventory",
    "trucks", "truck", "suv", "suvs", "sedan", "sedans", "van", "vans", "minivan", "minivans", "coupe", "coupes", "hatchback",
    "hatchbacks", "wagon", "wagons", "convertible", "convertibles", "pickup", "pickups", "crossover", "crossovers", "hybrid",
    "hybrids", "electric", "diesel", "awd", "4x4", "4wd", "row", "seater", "seats", "grand", "thousand", "just", "maybe",
    "prefer", "preferably", "ideally", "really", "kind", "sort", "type", "some", "good", "nice", "best", "big", "small",
    "thing", "things", "third", "3rd", "here", "saying", "love", "newest", "latest", "cheapest", "lowest", "least", "most",
}


def _num(s: str, unit: Optional[str]) -> Optional[float]:
    try:
        v = float(s.replace(",", ""))
    except Exception:
        return None
    if unit:
        v *= 1000
    elif v < 1000:
        return None  # "under 30" without k/$ is too ambiguous
    return v


def parse_query(message: str) -> dict:
    """Extract body types, features, price/year/mileage bounds, sort hint and leftover search tokens."""
    text = (message or "").lower()
    q = {"bodies": set(), "features": set(), "price_min": None, "price_max": None, "year_min": None, "year_max": None,
         "miles_max": None, "sort": None, "tokens": [], "consumed": []}
    work = text

    m = _MILES_RX.search(work)
    if m:
        try:
            v = float(m.group(1).replace(",", ""))
            q["miles_max"] = v * 1000 if (m.group(2) or v < 1000) else v
        except Exception:
            pass
        work = work[:m.start()] + " " + work[m.end():]
    if _LOW_MILES_RX.search(work):
        q["sort"] = q["sort"] or "miles"
    m = _YEAR_MIN_RX.search(work)
    if m:
        y = int(m.group(1) or m.group(2))
        q["year_min"] = y if m.group(1) or re.search(r"since|at least", m.group(0), re.I) else y + 1
        work = work[:m.start()] + " " + work[m.end():]
    m = _YEAR_MAX_RX.search(work)
    if m:
        y = int(m.group(1) or m.group(2))
        q["year_max"] = y if m.group(1) else y - 1
        work = work[:m.start()] + " " + work[m.end():]

    m = _PRICE_RANGE_RX.search(work)
    lo = hi = None
    if m:
        lo, hi = _num(m.group(1), m.group(2) or m.group(4)), _num(m.group(3), m.group(4))
    if lo and hi and lo < hi:
        q["price_min"], q["price_max"] = lo, hi
        work = work[:m.start()] + " " + work[m.end():]
    else:
        m = _PRICE_AROUND_RX.search(work)
        if m and _num(m.group(1), m.group(2)):
            v = _num(m.group(1), m.group(2))
            q["price_min"], q["price_max"] = v * 0.88, v * 1.12
            q["around"] = v
            work = work[:m.start()] + " " + work[m.end():]
        else:
            m = _PRICE_MAX_RX.search(work)
            if m and _num(m.group(1), m.group(2)):
                q["price_max"] = _num(m.group(1), m.group(2))
                work = work[:m.start()] + " " + work[m.end():]
        m = _PRICE_MIN_RX.search(work)
        if m and _num(m.group(1), m.group(2)):
            q["price_min"] = _num(m.group(1), m.group(2))
            work = work[:m.start()] + " " + work[m.end():]
    if q["price_max"] is None and q["price_min"] is None:
        m = _LONE_PRICE_RX.search(work)
        if m and _num(m.group(1), m.group(2)) and _num(m.group(1), m.group(2)) >= 3000:
            q["price_max"] = _num(m.group(1), m.group(2))
            work = work[:m.start()] + " " + work[m.end():]

    for rx, bodies in _ASK_BODY_RX:
        if rx.search(work):
            if bodies == {"suv", "van"} and q["bodies"]:
                continue  # "minivan with a third row" stays van-only
            q["bodies"] |= bodies
    for rx, feat in _ASK_FEATURE_RX:
        if rx.search(work):
            q["features"].add(feat)
    if _CHEAP_RX.search(work):
        q["sort"] = "price"
        q["cheap"] = True
    elif _NEWEST_RX.search(work):
        q["sort"] = q["sort"] or "year"

    raw = [w for w in re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)?", work) if len(w) >= 3 and w not in _STOP]
    tokens, words = [], []
    for t in raw[:8]:
        if re.fullmatch(r"\d{4}", t) and 1980 <= int(t) <= 2100 and (q["year_min"] or q["year_max"]):
            continue
        if re.fullmatch(r"\d+k?", t):
            continue
        words.append(t)
        tokens.append(t)
        if t.endswith("s") and len(t) > 3:
            tokens.append(t[:-1])
    q["tokens"] = tokens
    q["words"] = words
    q["has_filters"] = bool(q["bodies"] or q["features"] or q["price_min"] or q["price_max"] or q["year_min"] or q["year_max"]
                            or q["miles_max"] or q["sort"])
    q["numeric"] = bool(q["price_min"] or q["price_max"] or q["year_min"] or q["year_max"] or q["miles_max"])
    return q


_INTENT_RX = re.compile(
    r"\?|\b(any|anything|looking|look at|have|got|want|need|show|interested|shopping|market|options?|what|which|do you|"
    r"you have|sell|selling|available|in stock|carry|find|cheapest|cheap|affordable|budget|under|below|around|between|newest|"
    r"price[ds]?|how much|whatcha|what'?s|recommend)\b", re.I)


def is_shopping_message(message: str) -> bool:
    """A body type / fuel / price / year / mileage ask that should hit live inventory.
    A body word alone ("love my truck") is not shopping; it needs a question or intent word, or a number."""
    q = parse_query(message)
    if not q["has_filters"]:
        return False
    return q["numeric"] or bool(_INTENT_RX.search(message or ""))


def _blob(it: dict) -> str:
    a = it.get("attributes") or {}
    return " ".join(str(x) for x in [a.get("make", ""), a.get("model", ""), a.get("trim", ""), it.get("name", ""),
                                     a.get("body_type", ""), a.get("body_style", ""), it.get("description", ""),
                                     " ".join(it.get("tags") or [])] if x).lower()


def classify_body(it: dict) -> Optional[str]:
    a = it.get("attributes") or {}
    for key in ("body_type", "body_style", "body", "vehicle_type", "bodystyle"):
        v = str(a.get(key) or it.get(key) or "").strip().lower()
        if v:
            for k, b in _EXPLICIT_BODY.items():
                if re.search(r"\b" + re.escape(k) + r"\b", v):
                    return b
    for tag in it.get("tags") or []:
        b = _EXPLICIT_BODY.get(str(tag).strip().lower())
        if b:
            return b
    head = " ".join(str(x) for x in [a.get("make", ""), a.get("model", ""), a.get("trim", ""), it.get("name", "")] if x).lower()
    for body, rx in _BODY_RX:
        if rx.search(head):
            return body
    desc = str(it.get("description") or "").lower()
    for body, rx in _BODY_RX:
        if rx.search(desc):
            return body
    return None


def features_of(it: dict) -> set:
    blob = _blob(it)
    a = it.get("attributes") or {}
    extra = " ".join(str(a.get(k) or "") for k in ("fuel", "fuel_type", "drivetrain", "drive_type", "engine")).lower()
    return {f for f, rx in _FEATURE_RX.items() if rx.search(blob) or rx.search(extra)}


def _price(it) -> Optional[float]:
    try:
        return float(it.get("price")) if it.get("price") not in (None, "", 0) else None
    except Exception:
        return None


def _year(it) -> Optional[int]:
    try:
        return int(str((it.get("attributes") or {}).get("year", "")).strip()[:4])
    except Exception:
        return None


def _miles(it) -> Optional[float]:
    try:
        return float(str((it.get("attributes") or {}).get("mileage", "")).replace(",", "").replace("miles", "").strip())
    except Exception:
        return None


def _token_hits(it, tokens) -> int:
    blob = f"{it.get('name', '')} {it.get('description', '')} " + " ".join(str(v) for v in (it.get("attributes") or {}).values())
    blob = blob.lower()
    return sum(1 for t in set(tokens) if t in blob)


def _passes_numeric(it, q) -> bool:
    p, y, mi = _price(it), _year(it), _miles(it)
    if q["price_max"] is not None and (p is None or p > q["price_max"]):
        return False
    if q["price_min"] is not None and (p is None or p < q["price_min"]):
        return False
    if q["year_min"] is not None and (y is None or y < q["year_min"]):
        return False
    if q["year_max"] is not None and (y is None or y > q["year_max"]):
        return False
    if q["miles_max"] is not None and (mi is None or mi > q["miles_max"]):
        return False
    return True


def _passes_type(it, q) -> bool:
    if q["bodies"] and classify_body(it) not in q["bodies"]:
        return False
    hard = q["features"] - {"awd_4x4"}
    if hard and not hard <= features_of(it):
        return False
    return True


def _sort_key(q):
    def key(it):
        p = _price(it)
        y = _year(it) or 0
        mi = _miles(it)
        soft = 1 if ("awd_4x4" in q["features"] and "awd_4x4" in features_of(it)) else 0
        primary = -(_token_hits(it, q["tokens"]) * 10 + soft * 3)
        if q["sort"] == "year":
            return (primary, -y, p if p is not None else 1e12)
        if q["sort"] == "miles":
            return (primary, mi if mi is not None else 1e12, p if p is not None else 1e12)
        return (primary, p if p is not None else 1e12, -y)
    return key


def _distance(it, q) -> float:
    p, y, mi = _price(it), _year(it), _miles(it)
    d = 0.0
    if q["price_max"] is not None and p is not None and p > q["price_max"]:
        d += (p - q["price_max"]) / max(q["price_max"], 1)
    if q["price_min"] is not None and p is not None and p < q["price_min"]:
        d += (q["price_min"] - p) / max(q["price_min"], 1)
    if q["year_min"] is not None and y is not None and y < q["year_min"]:
        d += (q["year_min"] - y) * 0.15
    if q["year_max"] is not None and y is not None and y > q["year_max"]:
        d += (y - q["year_max"]) * 0.15
    if q["miles_max"] is not None and mi is not None and mi > q["miles_max"]:
        d += (mi - q["miles_max"]) / max(q["miles_max"], 1)
    if p is None and (q["price_max"] is not None or q["price_min"] is not None):
        d += 5
    return d


def select_matches(items: list, q: dict) -> tuple:
    """Return (matches, exact). exact=False means nothing fit every filter and these are the closest."""
    tokens = q["tokens"]
    if not q["has_filters"]:
        hits = [it for it in items if _token_hits(it, tokens) > 0] if tokens else []
        hits.sort(key=_sort_key(q))
        return hits, True

    typed = [it for it in items if _passes_type(it, q)]
    if not typed:
        return [], True
    if tokens:
        named = [it for it in typed if _token_hits(it, tokens) > 0]
        if named:
            typed = named
    full = [it for it in typed if _passes_numeric(it, q)]
    if full:
        full.sort(key=_sort_key(q))
        return full, True
    closest = sorted(typed, key=lambda it: (_distance(it, q), _sort_key(q)(it)))
    return closest, False


def describe_filters(q: dict) -> str:
    parts = []
    if q["bodies"]:
        parts.append("/".join(BODY_LABEL[b].lower() + "s" for b in sorted(q["bodies"])))
    for f in sorted(q["features"]):
        parts.append(FEATURE_LABEL[f])
    if q.get("around"):
        parts.append(f"around ${q['around']:,.0f}")
    elif q["price_min"] is not None and q["price_max"] is not None:
        parts.append(f"${q['price_min']:,.0f}-${q['price_max']:,.0f}")
    elif q["price_max"] is not None:
        parts.append(f"under ${q['price_max']:,.0f}")
    elif q["price_min"] is not None:
        parts.append(f"over ${q['price_min']:,.0f}")
    if q["year_min"] is not None and q["year_max"] is not None:
        parts.append(f"{q['year_min']}-{q['year_max']}")
    elif q["year_min"] is not None:
        parts.append(f"{q['year_min']} or newer")
    elif q["year_max"] is not None:
        parts.append(f"{q['year_max']} or older")
    if q["miles_max"] is not None:
        parts.append(f"under {q['miles_max']:,.0f} miles")
    if q.get("cheap"):
        parts.append("lowest price")
    if q.get("words"):
        parts.append(" ".join(q["words"]))
    return ", ".join(p for p in parts if p)


def describe_vehicle(it: dict) -> str:
    a = it.get("attributes") or {}
    bits = [it.get("name", "")]
    body = classify_body(it)
    if body:
        bits.append(BODY_LABEL[body])
    feats = [FEATURE_LABEL[f] for f in sorted(features_of(it)) if f != "awd_4x4"]
    if "awd_4x4" in features_of(it):
        feats.append("AWD/4x4")
    if feats:
        bits.append(", ".join(feats))
    if a.get("color"):
        bits.append(str(a["color"]))
    p = _price(it)
    if p:
        bits.append(f"${p:,.0f}")
    mi = _miles(it)
    if mi is not None:
        bits.append(f"{mi:,.0f} miles")
    if a.get("stock_number"):
        bits.append(f"Stock #{a['stock_number']}")
    return " · ".join(str(b) for b in bits if b)
