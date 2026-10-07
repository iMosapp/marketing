"""Dealership appraisal rules (MVP4): organization defaults with optional store overrides, versioned so yesterday's appraisal never changes.
Every rule carries enabled / method / amount / reason so the engine can explain exactly what it did (and skipped)."""
import copy
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId

RULES = "appraisal_rules"
RULES_SCHEMA_VERSION = 1
CONDITIONS = ("very_good", "good", "fair", "poor")
CONDITION_LABELS = {"very_good": "Excellent", "good": "Good", "fair": "Fair", "poor": "Poor"}
BASIS_OPTIONS = {
    "provider_retail": {"label": "Market estimated retail", "source": "MARKET DATA", "kind": "retail", "hint": "MarketCheck Price prediction when live; the provider's retail estimate otherwise"},
    "comps_median": {"label": "Comparable median", "source": "MARKET DATA", "kind": "retail", "hint": "Median asking price of the comparables pulled"},
    "comps_average": {"label": "Comparable average", "source": "MARKET DATA", "kind": "retail", "hint": "Average asking price of the comparables pulled"},
    "book:mmr": {"label": "Manheim MMR (manual)", "source": "BOOK VALUE", "kind": "book", "hint": "Entered by hand on the Market step"},
    "book:black_book": {"label": "Black Book (manual)", "source": "BOOK VALUE", "kind": "book", "hint": "Entered by hand on the Market step"},
    "book:jd_power": {"label": "J.D. Power (manual)", "source": "BOOK VALUE", "kind": "book", "hint": "Entered by hand on the Market step"},
    "book:kbb": {"label": "Kelley Blue Book (manual)", "source": "BOOK VALUE", "kind": "book", "hint": "Entered by hand on the Market step"},
    "book:galves": {"label": "Galves (manual)", "source": "BOOK VALUE", "kind": "book", "hint": "Entered by hand on the Market step"},
    "manual": {"label": "Manager-entered basis", "source": "MANUAL", "kind": "manual", "hint": "A manager types the starting value"},
}

DEFAULT_RULES = {
    "schema_version": RULES_SCHEMA_VERSION,
    "basis": {"order": ["provider_retail", "comps_median"], "min_comps": 3, "reason": "Start from what the market says the car retails for; fall back to the comparable median."},
    "target_gross": {"enabled": True, "method": "fixed", "amount": 3000, "percent": 0, "apply_to_wholesale": False, "reason": "Target front-end gross on the retail."},
    "recon": {"enabled": True, "by_condition": {"very_good": 500, "good": 1000, "fair": 2000, "poor": None}, "poor_requires_review": True,
              "unknown_amount": 1000, "unknown_requires_review": True, "reason": "Reconditioning allowance by confirmed condition."},
    "mileage": {"enabled": False, "expected_per_year": 12000, "per_1000_over": -100, "per_1000_under": 50, "cap": 3000,
                "reason": "Adjust for miles above or below what is expected for the age. Market predictions usually already reflect mileage, so this is off by default."},
    "age": {"enabled": False, "bands": [{"min_years": 0, "max_years": 2, "amount": 0}, {"min_years": 3, "max_years": 5, "amount": -250},
                                         {"min_years": 6, "max_years": 8, "amount": -500}, {"min_years": 9, "max_years": None, "amount": None, "requires_review": True}],
            "reason": "Older units carry more risk. Off by default because market data already prices the model year."},
    "reserve": {"enabled": False, "amount": 500, "reason": "Inventory / risk reserve."},
    "review": {"low_confidence": True, "poor_condition": True, "customer_gap_over": None, "reason": "When to require a manager's eyes before any number goes out."},
    "range": {"method": "fixed", "below": 500, "above": 500, "percent": 2, "reason": "Trade range shown around the suggested ACV."},
    "rounding": 50,
    "follow_up": {"tag_on_outcome": False, "tags": {"accepted": "trade-accepted", "wants_more": "trade-wants-more", "thinking": "trade-thinking", "not_trading": "trade-not-trading", "other": ""},
                  "reason": "When on, each outcome adds a contact tag so your existing tag workflows (campaigns, Jessi) take it from there. Nothing is enrolled automatically otherwise."},
}

MANAGER_ROLES = ("super_admin", "org_admin", "store_manager")


def _now():
    return datetime.now(timezone.utc)


def _num(v, default=None, allow_none=False):
    if v is None or v == "":
        if allow_none:
            return None
        return default
    try:
        return int(round(float(v)))
    except (TypeError, ValueError):
        raise ValueError("Every amount must be a number")


def _bool(v) -> bool:
    return bool(v) if not isinstance(v, str) else v.lower() in ("1", "true", "yes", "on")


def validate(raw: dict) -> dict:
    """Coerce + check a rules dict. Unknown keys are dropped; missing sections fall back to the defaults so partial saves are safe."""
    d = copy.deepcopy(DEFAULT_RULES)
    raw = raw or {}
    b = raw.get("basis") or {}
    order = [k for k in (b.get("order") or d["basis"]["order"]) if k in BASIS_OPTIONS]
    if not order:
        raise ValueError("Pick at least one valuation basis")
    d["basis"].update({"order": list(dict.fromkeys(order)), "min_comps": max(1, _num(b.get("min_comps"), 3)), "reason": str(b.get("reason") or d["basis"]["reason"])[:300]})
    tg = raw.get("target_gross") or {}
    method = tg.get("method") or "fixed"
    if method not in ("fixed", "percent"):
        raise ValueError("Target gross method must be fixed or percent")
    d["target_gross"].update({"enabled": _bool(tg.get("enabled", d["target_gross"]["enabled"])), "method": method, "amount": max(0, _num(tg.get("amount"), 3000)),
                              "percent": max(0, min(100, _num(tg.get("percent"), 0))), "apply_to_wholesale": _bool(tg.get("apply_to_wholesale", False)),
                              "reason": str(tg.get("reason") or d["target_gross"]["reason"])[:300]})
    rc = raw.get("recon") or {}
    byc = rc.get("by_condition") or {}
    d["recon"].update({"enabled": _bool(rc.get("enabled", True)), "by_condition": {c: _num(byc.get(c, d["recon"]["by_condition"][c]), None, allow_none=True) for c in CONDITIONS},
                       "poor_requires_review": _bool(rc.get("poor_requires_review", True)), "unknown_amount": _num(rc.get("unknown_amount", d["recon"]["unknown_amount"]), 1000, allow_none=True),
                       "unknown_requires_review": _bool(rc.get("unknown_requires_review", True)), "reason": str(rc.get("reason") or d["recon"]["reason"])[:300]})
    for c in CONDITIONS:
        if d["recon"]["by_condition"][c] is not None and d["recon"]["by_condition"][c] < 0:
            raise ValueError("Recon amounts cannot be negative")
    mi = raw.get("mileage") or {}
    d["mileage"].update({"enabled": _bool(mi.get("enabled", False)), "expected_per_year": max(1000, _num(mi.get("expected_per_year"), 12000)),
                         "per_1000_over": _num(mi.get("per_1000_over"), -100), "per_1000_under": _num(mi.get("per_1000_under"), 50), "cap": max(0, _num(mi.get("cap"), 3000)),
                         "reason": str(mi.get("reason") or d["mileage"]["reason"])[:300]})
    ag = raw.get("age") or {}
    bands = []
    for band in (ag.get("bands") if ag.get("bands") is not None else d["age"]["bands"]):
        lo = max(0, _num(band.get("min_years"), 0))
        hi = _num(band.get("max_years"), None, allow_none=True)
        if hi is not None and hi < lo:
            raise ValueError("An age band ends before it starts")
        bands.append({"min_years": lo, "max_years": hi, "amount": _num(band.get("amount"), None, allow_none=True), "requires_review": _bool(band.get("requires_review", False))})
    bands.sort(key=lambda x: x["min_years"])
    d["age"].update({"enabled": _bool(ag.get("enabled", False)), "bands": bands, "reason": str(ag.get("reason") or d["age"]["reason"])[:300]})
    rs = raw.get("reserve") or {}
    d["reserve"].update({"enabled": _bool(rs.get("enabled", False)), "amount": max(0, _num(rs.get("amount"), 500)), "reason": str(rs.get("reason") or d["reserve"]["reason"])[:300]})
    rv = raw.get("review") or {}
    d["review"].update({"low_confidence": _bool(rv.get("low_confidence", True)), "poor_condition": _bool(rv.get("poor_condition", True)),
                        "customer_gap_over": _num(rv.get("customer_gap_over"), None, allow_none=True), "reason": str(rv.get("reason") or d["review"]["reason"])[:300]})
    rg = raw.get("range") or {}
    if (rg.get("method") or "fixed") not in ("fixed", "percent"):
        raise ValueError("Range method must be fixed or percent")
    d["range"].update({"method": rg.get("method") or "fixed", "below": max(0, _num(rg.get("below"), 500)), "above": max(0, _num(rg.get("above"), 500)),
                       "percent": max(0, min(50, _num(rg.get("percent"), 2))), "reason": str(rg.get("reason") or d["range"]["reason"])[:300]})
    d["rounding"] = _num(raw.get("rounding"), 50) if _num(raw.get("rounding"), 50) in (1, 5, 10, 25, 50, 100) else 50
    fu = raw.get("follow_up") or {}
    tags = {k: str((fu.get("tags") or {}).get(k, v) or "").strip().lower()[:40] for k, v in d["follow_up"]["tags"].items()}
    d["follow_up"].update({"tag_on_outcome": _bool(fu.get("tag_on_outcome", False)), "tags": tags, "reason": str(fu.get("reason") or d["follow_up"]["reason"])[:300]})
    d["schema_version"] = RULES_SCHEMA_VERSION
    return d


def double_count_warnings(rules: dict) -> list:
    """Shown to admins in the editor and attached to calculations: market predictions already reflect mileage and age."""
    out = []
    uses_market = any(k in ("provider_retail", "comps_median", "comps_average") for k in rules["basis"]["order"][:1])
    if rules["mileage"]["enabled"] and uses_market:
        out.append("Mileage adjustment is ON while the starting value is market data that already reflects this vehicle's mileage. You may be counting miles twice.")
    if rules["age"]["enabled"] and uses_market:
        out.append("Age adjustment is ON while the starting value is market data for this exact model year. You may be counting age twice.")
    return out


def _oid(s):
    return ObjectId(str(s)) if s and ObjectId.is_valid(str(s)) else None


def public_rules_doc(doc: Optional[dict]) -> Optional[dict]:
    if not doc:
        return None
    return {"id": str(doc["_id"]), "organization_id": doc.get("organization_id"), "store_id": doc.get("store_id"), "scope": "store" if doc.get("store_id") else "org",
            "version": doc.get("version") or 1, "rules": doc.get("rules"), "updated_by_name": doc.get("updated_by_name"), "updated_at": doc.get("updated_at"),
            "history_count": len(doc.get("history") or [])}


async def get_docs(db, organization_id: Optional[str], store_id: Optional[str]) -> dict:
    org_doc = await db[RULES].find_one({"organization_id": organization_id, "store_id": None}) if organization_id else None
    store_doc = await db[RULES].find_one({"store_id": store_id}) if store_id else None
    return {"org": org_doc, "store": store_doc}


async def effective(db, organization_id: Optional[str], store_id: Optional[str]) -> dict:
    """Store override > organization default > platform defaults. Returns the rules plus where they came from and their version."""
    docs = await get_docs(db, organization_id, store_id)
    if docs["store"]:
        src, doc = "store", docs["store"]
    elif docs["org"]:
        src, doc = "org", docs["org"]
    else:
        return {"rules": copy.deepcopy(DEFAULT_RULES), "source": "default", "version": 0, "rules_id": None, "scope_label": "I'm On Social defaults"}
    return {"rules": doc["rules"], "source": src, "version": doc.get("version") or 1, "rules_id": str(doc["_id"]),
            "scope_label": "Store override" if src == "store" else "Organization default"}


async def save(db, me: dict, *, organization_id: Optional[str], store_id: Optional[str], rules: dict) -> dict:
    """Upsert one scope. Previous versions go to `history` (last 50) so any submitted calculation can be matched to the rules it used."""
    clean = validate(rules)
    key = {"store_id": store_id} if store_id else {"organization_id": organization_id, "store_id": None}
    cur = await db[RULES].find_one(key)
    now = _now()
    name = (me.get("name") or f"{me.get('first_name') or ''} {me.get('last_name') or ''}".strip() or me.get("email") or "").strip()
    if cur:
        hist_entry = {"version": cur.get("version") or 1, "rules": cur.get("rules"), "updated_by": cur.get("updated_by"), "updated_by_name": cur.get("updated_by_name"), "updated_at": cur.get("updated_at")}
        await db[RULES].update_one({"_id": cur["_id"]}, {"$set": {"rules": clean, "version": (cur.get("version") or 1) + 1, "updated_by": str(me["_id"]), "updated_by_name": name, "updated_at": now},
                                                          "$push": {"history": {"$each": [hist_entry], "$slice": -50}}})
        return await db[RULES].find_one({"_id": cur["_id"]})
    doc = {"_id": ObjectId(), "organization_id": organization_id, "store_id": store_id, "rules": clean, "version": 1, "updated_by": str(me["_id"]), "updated_by_name": name,
           "created_at": now, "updated_at": now, "history": []}
    await db[RULES].insert_one(doc)
    return doc


async def remove_store_override(db, store_id: str) -> bool:
    res = await db[RULES].delete_one({"store_id": store_id})
    return res.deleted_count > 0


def _store_row(s: dict) -> dict:
    return {"id": str(s["_id"]), "name": s.get("name") or "Store", "organization_id": str(s["organization_id"]) if s.get("organization_id") else None}


async def reach(db, me: dict) -> dict:
    """Which organization and stores this user may configure. Super admin: every store; org admin: the org's stores + the org default;
    store manager: only a store override for their own store(s)."""
    role = me.get("role")
    org = str(me["organization_id"]) if me.get("organization_id") else None
    if role == "super_admin":
        rows = await db.stores.find({}, {"name": 1, "organization_id": 1}).sort("name", 1).to_list(300)
        return {"organization_id": org, "org_editable": True, "stores": [_store_row(s) for s in rows]}
    if role == "org_admin" and org:
        rows = await db.stores.find({"organization_id": {"$in": [org, _oid(org)]}}, {"name": 1, "organization_id": 1}).sort("name", 1).to_list(200)
        return {"organization_id": org, "org_editable": True, "stores": [_store_row(s) for s in rows]}
    sids = [str(s) for s in (([me.get("store_id")] if me.get("store_id") else []) + list(me.get("store_ids") or []))]
    rows = await db.stores.find({"_id": {"$in": [ObjectId(s) for s in dict.fromkeys(sids) if ObjectId.is_valid(s)]}}, {"name": 1, "organization_id": 1}).to_list(20)
    if not org and rows and rows[0].get("organization_id"):
        org = str(rows[0]["organization_id"])
    return {"organization_id": org, "org_editable": False, "stores": [_store_row(s) for s in rows]}
