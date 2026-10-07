"""Pure appraisal engine (MVP4). No database, no clock, no randomness: the same inputs always give the same output, and every line says
where it came from (MARKET DATA · BOOK VALUE · I'M ON SOCIAL CALCULATION · MANUAL). Customer expectation is reported next to the number, never inside it."""
from typing import Optional

from services.appraisals.rules import BASIS_OPTIONS, CONDITION_LABELS

ENGINE_VERSION = 1
SRC_MARKET, SRC_BOOK, SRC_CALC, SRC_MANUAL = "MARKET DATA", "BOOK VALUE", "I'M ON SOCIAL CALCULATION", "MANUAL"
BOOK_LABELS = {"black_book": "Black Book", "mmr": "Manheim MMR", "jd_power": "J.D. Power (NADA)", "kbb": "Kelley Blue Book", "galves": "Galves", "other": "Other"}


def _round(x: Optional[float], step: int) -> Optional[int]:
    if x is None:
        return None
    step = step or 1
    return int(round(float(x) / step) * step)


def _latest_book(book_values: list, source: str) -> Optional[dict]:
    rows = [b for b in (book_values or []) if b.get("source") == source and b.get("value")]
    rows.sort(key=lambda b: str(b.get("updated_at") or b.get("entered_at") or ""), reverse=True)
    return rows[0] if rows else None


def valuation_sources(market: Optional[dict], book_values: list, customer_expected_value: Optional[int]) -> list:
    """Every reference the desk should see side by side. Decision inputs, never averaged."""
    out = []
    if market:
        if market.get("estimated_retail"):
            out.append({"key": "provider_retail", "label": f"{market.get('provider_label') or 'Market'} retail", "amount": market["estimated_retail"], "source": SRC_MARKET,
                        "note": market.get("retail_label"), "live": market.get("live")})
        if market.get("median_market_price"):
            out.append({"key": "comps_median", "label": "Comparable median", "amount": market["median_market_price"], "source": SRC_MARKET, "note": f"{market.get('comps_used') or 0} comps", "live": market.get("live")})
        if market.get("avg_market_price"):
            out.append({"key": "comps_average", "label": "Comparable average", "amount": market["avg_market_price"], "source": SRC_MARKET, "note": f"{market.get('comps_used') or 0} comps", "live": market.get("live")})
        if market.get("estimated_wholesale"):
            out.append({"key": "provider_wholesale", "label": f"{market.get('provider_label') or 'Market'} wholesale", "amount": market["estimated_wholesale"], "source": SRC_MARKET, "live": market.get("live")})
    for b in book_values or []:
        if b.get("value"):
            out.append({"key": f"book:{b.get('source')}", "label": b.get("source_label") or BOOK_LABELS.get(b.get("source"), "Book"), "amount": b["value"], "source": SRC_BOOK,
                        "note": str(b.get("value_type") or "").replace("_", "-"), "entered_by_name": b.get("entered_by_name")})
    if customer_expected_value:
        out.append({"key": "customer_wants", "label": "Customer wants", "amount": customer_expected_value, "source": "CUSTOMER", "note": "Not part of the calculation"})
    return out


def resolve_basis(rules: dict, market: Optional[dict], book_values: list, manual_basis: Optional[int] = None) -> Optional[dict]:
    """Walk the dealership's preferred order and take the first reference that exists."""
    min_comps = int((rules.get("basis") or {}).get("min_comps") or 3)
    for key in (rules.get("basis") or {}).get("order") or []:
        opt = BASIS_OPTIONS.get(key)
        if not opt:
            continue
        if key == "provider_retail" and market and market.get("estimated_retail") and market.get("retail_source") in ("marketcheck_price", "mock_model"):
            return {"key": key, "label": opt["label"], "amount": int(market["estimated_retail"]), "source": SRC_MARKET, "kind": "retail",
                    "reason": f"{market.get('retail_label') or 'Provider retail estimate'} ({market.get('provider_label')}{'' if market.get('live') else ', development data'})"}
        if key == "comps_median" and market and market.get("median_market_price") and (market.get("comps_used") or 0) >= min_comps:
            return {"key": key, "label": opt["label"], "amount": int(market["median_market_price"]), "source": SRC_MARKET, "kind": "retail",
                    "reason": f"Median asking price of {market.get('comps_used')} comparables ({market.get('provider_label')})"}
        if key == "comps_average" and market and market.get("avg_market_price") and (market.get("comps_used") or 0) >= min_comps:
            return {"key": key, "label": opt["label"], "amount": int(market["avg_market_price"]), "source": SRC_MARKET, "kind": "retail",
                    "reason": f"Average asking price of {market.get('comps_used')} comparables ({market.get('provider_label')})"}
        if key.startswith("book:"):
            b = _latest_book(book_values, key.split(":", 1)[1])
            if b:
                kind = "retail" if b.get("value_type") == "retail" else "wholesale"
                return {"key": key, "label": b.get("source_label") or opt["label"], "amount": int(b["value"]), "source": SRC_BOOK, "kind": kind,
                        "reason": f"{b.get('source_label')} {str(b.get('value_type') or '').replace('_', '-')} entered by {b.get('entered_by_name') or 'the team'}"}
        if key == "manual" and manual_basis:
            return {"key": key, "label": opt["label"], "amount": int(manual_basis), "source": SRC_MANUAL, "kind": "manual", "reason": "Starting value entered by a manager"}
    return None


def _age_years(vehicle: dict, now_year: int) -> Optional[int]:
    y = (vehicle or {}).get("year")
    return max(0, int(now_year) - int(y)) if y else None


def calculate(*, vehicle: dict, mileage: Optional[int], condition: Optional[dict], market: Optional[dict], book_values: list,
              customer_expected_value: Optional[int], rules: dict, now_year: int, manual_basis: Optional[int] = None) -> dict:
    """-> {suggested_acv, suggested_low, suggested_high, basis, breakdown, warnings, confidence, manager_review_required, review_reasons,
    customer_expected_value, expectation_gap, valuation_sources, engine_version}. Disabled or not-applied rules produce no breakdown line."""
    rounding = int(rules.get("rounding") or 50)
    warnings, review, lines = [], [], []
    cond_key = (condition or {}).get("overall")
    cond_label = CONDITION_LABELS.get(cond_key or "", "Not graded")
    basis = resolve_basis(rules, market, book_values, manual_basis)
    sources = valuation_sources(market, book_values, customer_expected_value)
    conf = (market or {}).get("confidence")
    conf = conf.get("level") if isinstance(conf, dict) else conf
    if not basis:
        review.append("No market value or book value to start from. A manager has to set the value.")
        return {"suggested_acv": None, "suggested_low": None, "suggested_high": None, "basis": None, "breakdown": [], "warnings": warnings, "confidence": conf,
                "manager_review_required": True, "review_reasons": review, "customer_expected_value": customer_expected_value, "expectation_gap": None,
                "valuation_sources": sources, "condition": cond_key, "condition_label": cond_label, "engine_version": ENGINE_VERSION}
    lines.append({"key": "basis", "label": basis["label"], "amount": basis["amount"], "source": basis["source"], "reason": basis["reason"], "rule": "basis"})
    total = float(basis["amount"])

    tg = rules.get("target_gross") or {}
    if tg.get("enabled"):
        if basis["kind"] == "retail" or (basis["kind"] == "manual") or tg.get("apply_to_wholesale"):
            amt = float(tg.get("amount") or 0) if tg.get("method") == "fixed" else basis["amount"] * float(tg.get("percent") or 0) / 100
            if amt:
                lines.append({"key": "target_gross", "label": "Target gross", "amount": -_round(amt, 1), "source": SRC_CALC,
                              "reason": tg.get("reason") or "Target front-end gross", "rule": "target_gross", "method": tg.get("method")})
                total -= amt
        else:
            warnings.append(f"Target gross not deducted: the starting value ({basis['label']}) is already a wholesale number.")

    rc = rules.get("recon") or {}
    if rc.get("enabled"):
        if cond_key in (rc.get("by_condition") or {}):
            amt = (rc.get("by_condition") or {}).get(cond_key)
            if amt is None:
                if cond_key == "poor" and rc.get("poor_requires_review", True):
                    review.append("Condition is Poor: reconditioning needs a manager's estimate.")
                warnings.append(f"No recon allowance deducted for {cond_label} condition (rule says manager review).")
            else:
                lines.append({"key": "recon", "label": f"Condition / recon ({cond_label})", "amount": -int(amt), "source": SRC_CALC, "reason": rc.get("reason") or "Reconditioning allowance", "rule": "recon"})
                total -= float(amt)
        else:
            amt = rc.get("unknown_amount")
            if rc.get("unknown_requires_review", True):
                review.append("No confirmed condition on this appraisal yet.")
            if amt is not None:
                lines.append({"key": "recon", "label": "Condition / recon (not graded)", "amount": -int(amt), "source": SRC_CALC, "reason": "Default recon while the condition is not confirmed", "rule": "recon"})
                total -= float(amt)
                warnings.append("Recon uses the default amount because the inspection has no confirmed overall condition.")

    age = _age_years(vehicle, now_year)
    mi = rules.get("mileage") or {}
    if mi.get("enabled") and mileage is not None and age is not None:
        expected = int(mi.get("expected_per_year") or 12000) * max(age, 1)
        delta = int(mileage) - expected
        rate = float(mi.get("per_1000_over") or 0) if delta > 0 else float(mi.get("per_1000_under") or 0)
        amt = abs(delta) / 1000.0 * rate
        cap = float(mi.get("cap") or 0)
        if cap:
            amt = max(-cap, min(cap, amt))
        amt = _round(amt, 1)
        if amt:
            lines.append({"key": "mileage", "label": f"Mileage ({'+' if delta > 0 else '-'}{abs(delta):,} vs {expected:,} expected)", "amount": amt, "source": SRC_CALC,
                          "reason": mi.get("reason") or "Mileage adjustment", "rule": "mileage"})
            total += amt
        if basis["key"] in ("provider_retail", "comps_median", "comps_average"):
            warnings.append("Mileage adjustment applied on top of market data that already reflects mileage. Possible double count; check the dealership rules.")

    ag = rules.get("age") or {}
    if ag.get("enabled") and age is not None:
        band = next((b for b in ag.get("bands") or [] if age >= int(b.get("min_years") or 0) and (b.get("max_years") is None or age <= int(b["max_years"]))), None)
        if band:
            if band.get("amount") is None:
                if band.get("requires_review"):
                    review.append(f"Vehicle is {age} years old: age band says manager review.")
            elif band["amount"]:
                lines.append({"key": "age", "label": f"Vehicle age ({age} yr)", "amount": int(band["amount"]), "source": SRC_CALC, "reason": ag.get("reason") or "Age adjustment", "rule": "age"})
                total += float(band["amount"])
            if basis["key"] in ("provider_retail", "comps_median", "comps_average") and band.get("amount"):
                warnings.append("Age adjustment applied on top of market data for this exact model year. Possible double count; check the dealership rules.")

    rs = rules.get("reserve") or {}
    if rs.get("enabled") and rs.get("amount"):
        lines.append({"key": "reserve", "label": "Inventory / risk reserve", "amount": -int(rs["amount"]), "source": SRC_CALC, "reason": rs.get("reason") or "Inventory risk reserve", "rule": "reserve"})
        total -= float(rs["amount"])

    suggested = max(0, _round(total, rounding))
    rg = rules.get("range") or {}
    if (rg.get("method") or "fixed") == "percent":
        spread = suggested * float(rg.get("percent") or 0) / 100
        low, high = _round(suggested - spread, rounding), _round(suggested + spread, rounding)
    else:
        low, high = _round(suggested - float(rg.get("below") or 0), rounding), _round(suggested + float(rg.get("above") or 0), rounding)

    rv = rules.get("review") or {}
    if rv.get("low_confidence") and conf == "low":
        review.append("Market confidence is LOW.")
    if rv.get("poor_condition") and cond_key == "poor" and not any("Poor" in r for r in review):
        review.append("Condition is Poor.")
    if not market:
        warnings.append("No market snapshot on this appraisal; the starting value came from a book value.")
    gap = (int(customer_expected_value) - suggested) if customer_expected_value else None
    if rv.get("customer_gap_over") is not None and gap is not None and gap > int(rv["customer_gap_over"]):
        review.append(f"Customer wants ${gap:,} more than the suggested ACV.")
    return {"suggested_acv": suggested, "suggested_low": max(0, low), "suggested_high": max(0, high), "basis": basis, "breakdown": lines, "warnings": warnings,
            "confidence": conf, "manager_review_required": bool(review), "review_reasons": review, "customer_expected_value": customer_expected_value,
            "expectation_gap": gap, "valuation_sources": sources, "condition": cond_key, "condition_label": cond_label, "engine_version": ENGINE_VERSION}
