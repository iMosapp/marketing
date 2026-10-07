"""Pure appraisal engine (MVP4): no database, no network. Same inputs -> same output; every line labelled by source; customer expectation
never inside the number; disabled or not-applied rules produce no line; rules validation coerces and rejects correctly."""
import copy
import sys

import pytest

sys.path.insert(0, "/app/backend")
from services.appraisals import engine  # noqa: E402
from services.appraisals.rules import DEFAULT_RULES, validate, double_count_warnings  # noqa: E402

VEHICLE = {"year": 2019, "make": "Ford", "model": "F-150", "trim": "XLT"}
MARKET = {"provider": "mock", "provider_label": "Development data", "live": False, "estimated_retail": 30000, "retail_source": "mock_model", "retail_label": "Model estimate",
          "estimated_wholesale": 25500, "median_market_price": 29400, "avg_market_price": 29650, "comps_used": 12, "listing_count": 40, "confidence": "high"}
BOOKS = [{"id": "b1", "source": "mmr", "source_label": "Manheim MMR", "value_type": "wholesale", "value": 24000, "entered_by_name": "Kira", "entered_at": "2026-10-07T10:00:00"},
         {"id": "b2", "source": "black_book", "source_label": "Black Book", "value_type": "trade_in", "value": 23500, "entered_by_name": "Kira", "entered_at": "2026-10-07T10:00:00"}]
GOOD = {"overall": "good", "label": "Good", "confirmed": 2}


def rules(**over):
    r = copy.deepcopy(DEFAULT_RULES)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(r.get(k), dict):
            r[k] = {**r[k], **v}
        else:
            r[k] = v
    return r


def calc(**kw):
    base = dict(vehicle=VEHICLE, mileage=61200, condition=GOOD, market=MARKET, book_values=BOOKS, customer_expected_value=None, rules=rules(), now_year=2026)
    base.update(kw)
    return engine.calculate(**base)


def line(out, key):
    return next((l for l in out["breakdown"] if l["key"] == key), None)


# ---------- defaults: retail basis - target gross - recon ----------
def test_default_rules_retail_minus_gross_minus_recon():
    out = calc()
    assert out["basis"]["key"] == "provider_retail" and out["basis"]["amount"] == 30000 and out["basis"]["source"] == "MARKET DATA"
    assert line(out, "target_gross")["amount"] == -3000 and line(out, "target_gross")["source"] == "I'M ON SOCIAL CALCULATION"
    assert line(out, "recon")["amount"] == -1000 and "Good" in line(out, "recon")["label"]
    assert out["suggested_acv"] == 26000 and out["suggested_low"] == 25500 and out["suggested_high"] == 26500
    assert out["manager_review_required"] is False and out["review_reasons"] == []
    assert [l["key"] for l in out["breakdown"]] == ["basis", "target_gross", "recon"]
    assert out["engine_version"] == engine.ENGINE_VERSION


def test_deterministic():
    a, b = calc(), calc()
    assert a == b


def test_customer_expectation_is_reported_not_calculated():
    without = calc()
    with_ = calc(customer_expected_value=32000)
    assert with_["suggested_acv"] == without["suggested_acv"]
    assert with_["expectation_gap"] == 6000 and without["expectation_gap"] is None
    cw = next(s for s in with_["valuation_sources"] if s["key"] == "customer_wants")
    assert cw["source"] == "CUSTOMER" and cw["amount"] == 32000


def test_valuation_sources_side_by_side():
    keys = [s["key"] for s in calc(customer_expected_value=1).get("valuation_sources")]
    assert keys == ["provider_retail", "comps_median", "comps_average", "provider_wholesale", "book:mmr", "book:black_book", "customer_wants"]
    srcs = {s["key"]: s["source"] for s in calc()["valuation_sources"]}
    assert srcs["provider_retail"] == "MARKET DATA" and srcs["book:mmr"] == "BOOK VALUE"


# ---------- basis selection ----------
def test_basis_falls_back_to_comps_median_when_prediction_missing():
    mk = {**MARKET, "estimated_retail": None}
    out = calc(market=mk)
    assert out["basis"]["key"] == "comps_median" and out["basis"]["amount"] == 29400


def test_comps_need_min_count():
    mk = {**MARKET, "estimated_retail": None, "comps_used": 2}
    out = calc(market=mk, rules=rules(basis={"order": ["provider_retail", "comps_median", "book:mmr"], "min_comps": 3}))
    assert out["basis"]["key"] == "book:mmr" and out["basis"]["kind"] == "wholesale" and out["basis"]["source"] == "BOOK VALUE"


def test_no_basis_requires_manager():
    out = calc(market=None, book_values=[])
    assert out["suggested_acv"] is None and out["manager_review_required"] is True
    assert out["breakdown"] == [] and "manager" in out["review_reasons"][0].lower()


def test_manual_basis_only_when_in_order():
    assert calc(market=None, book_values=[], manual_basis=20000)["suggested_acv"] is None
    out = calc(market=None, book_values=[], manual_basis=20000, rules=rules(basis={"order": ["provider_retail", "manual"]}))
    assert out["basis"]["key"] == "manual" and out["basis"]["source"] == "MANUAL" and out["suggested_acv"] == 20000 - 3000 - 1000


def test_latest_book_value_wins():
    books = [{"source": "mmr", "source_label": "MMR", "value_type": "wholesale", "value": 20000, "updated_at": "2026-01-01"},
             {"source": "mmr", "source_label": "MMR", "value_type": "wholesale", "value": 21000, "updated_at": "2026-02-01"}]
    out = calc(market=None, book_values=books, rules=rules(basis={"order": ["book:mmr"]}))
    assert out["basis"]["amount"] == 21000


# ---------- target gross ----------
def test_target_gross_percent():
    out = calc(rules=rules(target_gross={"method": "percent", "percent": 10}))
    assert line(out, "target_gross")["amount"] == -3000 and line(out, "target_gross")["method"] == "percent"


def test_target_gross_skipped_on_wholesale_basis_with_warning():
    out = calc(market=None, rules=rules(basis={"order": ["book:mmr"]}))
    assert line(out, "target_gross") is None
    assert any("wholesale" in w for w in out["warnings"])
    assert out["suggested_acv"] == 24000 - 1000
    out2 = calc(market=None, rules=rules(basis={"order": ["book:mmr"]}, target_gross={"apply_to_wholesale": True}))
    assert line(out2, "target_gross")["amount"] == -3000


def test_disabled_rules_leave_no_line():
    out = calc(rules=rules(target_gross={"enabled": False}, recon={"enabled": False}))
    assert [l["key"] for l in out["breakdown"]] == ["basis"] and out["suggested_acv"] == 30000


# ---------- recon / condition ----------
@pytest.mark.parametrize("cond,amt", [("very_good", -500), ("good", -1000), ("fair", -2000)])
def test_recon_by_condition(cond, amt):
    out = calc(condition={"overall": cond})
    assert line(out, "recon")["amount"] == amt


def test_poor_condition_requires_manager_and_no_recon_line():
    out = calc(condition={"overall": "poor"})
    assert line(out, "recon") is None
    assert out["manager_review_required"] is True
    assert any("Poor" in r for r in out["review_reasons"]) and sum("Poor" in r for r in out["review_reasons"]) == 1
    assert out["suggested_acv"] == 27000


def test_poor_with_amount_configured_deducts():
    out = calc(condition={"overall": "poor"}, rules=rules(recon={"by_condition": {"very_good": 500, "good": 1000, "fair": 2000, "poor": 4000}}, review={"poor_condition": False}))
    assert line(out, "recon")["amount"] == -4000 and out["manager_review_required"] is False


def test_unknown_condition_uses_default_and_flags():
    out = calc(condition=None)
    assert line(out, "recon")["amount"] == -1000 and "not graded" in line(out, "recon")["label"]
    assert any("No confirmed condition" in r for r in out["review_reasons"])
    assert out["condition_label"] == "Not graded"


# ---------- mileage ----------
def test_mileage_over_and_under():
    r = rules(mileage={"enabled": True, "expected_per_year": 12000, "per_1000_over": -100, "per_1000_under": 50, "cap": 3000})
    over = calc(mileage=104000, rules=r)   # expected 7 yrs * 12k = 84k -> +20k over -> -2000
    assert line(over, "mileage")["amount"] == -2000 and "+20,000" in line(over, "mileage")["label"]
    under = calc(mileage=64000, rules=r)   # 20k under -> +1000
    assert line(under, "mileage")["amount"] == 1000
    assert any("double count" in w.lower() for w in over["warnings"])


def test_mileage_cap_and_no_line_at_zero():
    r = rules(mileage={"enabled": True, "per_1000_over": -100, "cap": 1500})
    assert line(calc(mileage=200000, rules=r), "mileage")["amount"] == -1500
    assert line(calc(mileage=84000, rules=r), "mileage") is None


def test_mileage_skipped_without_year_or_mileage():
    r = rules(mileage={"enabled": True})
    assert line(calc(mileage=None, rules=r), "mileage") is None
    assert line(calc(vehicle={"make": "Ford", "model": "F-150"}, rules=r), "mileage") is None


# ---------- age ----------
def test_age_bands():
    r = rules(age={"enabled": True})
    assert line(calc(rules=r), "age")["amount"] == -500            # 2019 in 2026 = 7 yrs -> band 6-8
    assert line(calc(vehicle={**VEHICLE, "year": 2025}, rules=r), "age") is None   # band 0-2 amount 0 -> no line
    old = calc(vehicle={**VEHICLE, "year": 2012}, rules=r)
    assert line(old, "age") is None and any("age band" in x for x in old["review_reasons"])


# ---------- reserve / rounding / range ----------
def test_reserve_rounding_and_percent_range():
    r = rules(reserve={"enabled": True, "amount": 333}, rounding=100, range={"method": "percent", "percent": 5})
    out = calc(rules=r)
    assert line(out, "reserve")["amount"] == -333
    assert out["suggested_acv"] == 25700          # 26000 - 333 = 25667 -> 25700
    assert out["suggested_low"] == 24400 and out["suggested_high"] == 27000


def test_never_negative():
    out = calc(market={**MARKET, "estimated_retail": 1000}, rules=rules(range={"below": 5000}))
    assert out["suggested_acv"] == 0 and out["suggested_low"] == 0


# ---------- review triggers ----------
def test_low_confidence_and_customer_gap_triggers():
    out = calc(market={**MARKET, "confidence": {"level": "low", "score": 20}}, customer_expected_value=30000, rules=rules(review={"customer_gap_over": 2000}))
    assert out["confidence"] == "low"
    assert any("LOW" in r for r in out["review_reasons"]) and any("more than the suggested" in r for r in out["review_reasons"])
    assert out["manager_review_required"] is True
    out2 = calc(market={**MARKET, "confidence": "low"}, rules=rules(review={"low_confidence": False}))
    assert out2["manager_review_required"] is False


def test_no_market_warning_with_book_basis():
    out = calc(market=None, rules=rules(basis={"order": ["book:black_book"]}))
    assert any("No market snapshot" in w for w in out["warnings"]) and out["basis"]["key"] == "book:black_book"


# ---------- rules validation ----------
def test_validate_defaults_and_coercion():
    d = validate({})
    assert d == validate(DEFAULT_RULES) and d["rounding"] == 50
    d = validate({"target_gross": {"enabled": "false", "amount": "2500.4"}, "rounding": 7, "recon": {"by_condition": {"poor": ""}}, "basis": {"order": ["comps_median", "bogus", "comps_median"]}})
    assert d["target_gross"]["enabled"] is False and d["target_gross"]["amount"] == 2500 and d["rounding"] == 50
    assert d["recon"]["by_condition"]["poor"] is None and d["basis"]["order"] == ["comps_median"]


@pytest.mark.parametrize("bad", [{"basis": {"order": ["bogus"]}}, {"target_gross": {"method": "weird"}}, {"recon": {"by_condition": {"good": -5}}},
                                 {"age": {"bands": [{"min_years": 5, "max_years": 2}]}}, {"range": {"method": "x"}}, {"reserve": {"amount": "abc"}}])
def test_validate_rejects(bad):
    with pytest.raises(ValueError):
        validate(bad)


def test_double_count_warnings():
    assert double_count_warnings(validate({})) == []
    w = double_count_warnings(validate({"mileage": {"enabled": True}, "age": {"enabled": True}}))
    assert len(w) == 2
    assert double_count_warnings(validate({"mileage": {"enabled": True}, "basis": {"order": ["book:mmr"]}})) == []
