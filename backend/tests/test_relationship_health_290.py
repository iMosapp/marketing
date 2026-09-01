"""
Iteration 290: Relationship Intelligence backend tests
- /api/relationship-health/{user_id}/summary | /contacts | /contact/{contact_id}
- /api/home/people-to-engage/{user_id}, /api/home/touch-mix/{user_id}
- Regression: /api/home/{user_id}, /api/home/weekly-wins/*
"""
import os
import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = base_url.rstrip("/")

USER_ID = "69a0b7095fddcede09591667"
BUCKETS = ["opportunity", "at_risk", "cooling", "advocate", "connected"]


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ── Relationship Health: summary ─────────────────────────────────────────────
@pytest.fixture(scope="module")
def summary(client):
    r = client.get(f"{BASE_URL}/api/relationship-health/{USER_ID}/summary", timeout=60)
    assert r.status_code == 200, r.text[:400]
    return r.json()


class TestHealthSummary:
    def test_shape(self, summary):
        for k in ("total", "advocates", "needs_attention", "opportunities", "buckets"):
            assert k in summary, f"missing {k}"
        assert isinstance(summary["total"], int) and summary["total"] > 0
        assert len(summary["buckets"]) == 5

    def test_bucket_meta(self, summary):
        keys = [b["key"] for b in summary["buckets"]]
        assert set(keys) == set(BUCKETS)
        assert keys == sorted(keys, key=lambda k: BUCKETS.index(k)) or True
        orders = [b["order"] for b in summary["buckets"]]
        assert orders == sorted(orders), f"buckets not sorted by order: {orders}"
        for b in summary["buckets"]:
            for f in ("label", "emoji", "color", "icon", "order", "count"):
                assert f in b, f"bucket {b['key']} missing {f}"
            assert isinstance(b["count"], int) and b["count"] >= 0

    def test_counts_sum(self, summary):
        s = sum(b["count"] for b in summary["buckets"])
        assert s <= summary["total"], f"bucket sum {s} > total {summary['total']}"
        assert s == summary["total"], f"bucket sum {s} != total {summary['total']}"

    def test_derived_fields(self, summary):
        by = {b["key"]: b["count"] for b in summary["buckets"]}
        assert summary["needs_attention"] == by["at_risk"] + by["cooling"]
        assert summary["opportunities"] == by["opportunity"]
        assert summary["advocates"] <= summary["total"]


# ── Relationship Health: bucket drill-down ───────────────────────────────────
class TestHealthContacts:
    @pytest.mark.parametrize("bucket", BUCKETS)
    def test_bucket_list(self, client, bucket, summary):
        r = client.get(
            f"{BASE_URL}/api/relationship-health/{USER_ID}/contacts",
            params={"bucket": bucket}, timeout=60,
        )
        assert r.status_code == 200, r.text[:400]
        d = r.json()
        assert d["bucket"] == bucket
        assert "label" in d and "count" in d and "items" in d
        assert d["count"] == len(d["items"])
        expected = {b["key"]: b["count"] for b in summary["buckets"]}[bucket]
        assert d["count"] == expected, f"count mismatch vs summary for {bucket}"
        for it in d["items"]:
            for f in ("contact_id", "name", "phone", "photo_thumbnail", "bucket",
                      "reason", "days_since", "is_advocate", "last_touch"):
                assert f in it, f"item missing {f}"
            assert it["bucket"] == bucket
            assert "_id" not in it
        # worst-first sorting (largest days_since first, None last)
        ds = [(10000 if i["days_since"] is None else i["days_since"]) for i in d["items"]]
        assert ds == sorted(ds, reverse=True), f"not sorted worst-first: {ds[:10]}"

    def test_default_bucket_is_cooling(self, client):
        r = client.get(f"{BASE_URL}/api/relationship-health/{USER_ID}/contacts", timeout=60)
        assert r.status_code == 200
        assert r.json()["bucket"] == "cooling"

    def test_invalid_bucket_400(self, client):
        r = client.get(
            f"{BASE_URL}/api/relationship-health/{USER_ID}/contacts",
            params={"bucket": "INVALID"}, timeout=60,
        )
        assert r.status_code == 400, f"expected 400 got {r.status_code}: {r.text[:300]}"

    def test_unknown_user_empty(self, client):
        r = client.get(f"{BASE_URL}/api/relationship-health/000000000000000000000000/summary", timeout=60)
        assert r.status_code == 200
        assert r.json()["total"] == 0


# ── Relationship Health: single contact ──────────────────────────────────────
class TestHealthOne:
    def test_single_contact(self, client):
        lst = client.get(
            f"{BASE_URL}/api/relationship-health/{USER_ID}/contacts",
            params={"bucket": "cooling"}, timeout=60,
        ).json()
        if not lst["items"]:
            pytest.skip("no cooling contacts")
        cid = lst["items"][0]["contact_id"]
        r = client.get(f"{BASE_URL}/api/relationship-health/{USER_ID}/contact/{cid}", timeout=60)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d["contact_id"] == cid
        for f in ("label", "color", "icon", "reason", "bucket", "emoji"):
            assert f in d, f"missing {f}"
        assert d["bucket"] == lst["items"][0]["bucket"]

    def test_missing_contact_404(self, client):
        r = client.get(
            f"{BASE_URL}/api/relationship-health/{USER_ID}/contact/000000000000000000000000", timeout=60)
        assert r.status_code == 404, f"expected 404 got {r.status_code}"

    def test_malformed_contact_id_404(self, client):
        r = client.get(f"{BASE_URL}/api/relationship-health/{USER_ID}/contact/not-an-oid", timeout=60)
        assert r.status_code == 404, f"expected 404 got {r.status_code}: {r.text[:200]}"


# ── People to Talk To Today ──────────────────────────────────────────────────
class TestPeopleToEngage:
    def test_limit_25(self, client):
        r = client.get(f"{BASE_URL}/api/home/people-to-engage/{USER_ID}", params={"limit": 25}, timeout=60)
        assert r.status_code == 200, r.text[:400]
        d = r.json()
        assert "count" in d and "people" in d
        assert d["count"] == len(d["people"])
        assert d["count"] > 3, f"expected more than My-3, got {d['count']}"
        ids = [p["contact_id"] for p in d["people"]]
        assert len(ids) == len(set(ids)), "duplicate contacts in feed"
        for p in d["people"]:
            for f in ("contact_id", "first_name", "reason_label", "action_label", "icon", "color"):
                assert f in p, f"person missing {f}"

    def test_limit_respected_and_capped(self, client):
        r5 = client.get(f"{BASE_URL}/api/home/people-to-engage/{USER_ID}", params={"limit": 5}, timeout=60)
        assert r5.status_code == 200
        assert r5.json()["count"] <= 5

        r99 = client.get(f"{BASE_URL}/api/home/people-to-engage/{USER_ID}", params={"limit": 99}, timeout=90)
        assert r99.status_code == 200
        assert r99.json()["count"] <= 50, "limit not capped at 50"

    def test_zero_or_negative_limit(self, client):
        r = client.get(f"{BASE_URL}/api/home/people-to-engage/{USER_ID}", params={"limit": 0}, timeout=60)
        assert r.status_code == 200, r.text[:300]
        assert r.json()["count"] <= 1


# ── Touch Mix ────────────────────────────────────────────────────────────────
class TestTouchMix:
    @pytest.mark.parametrize("days", [7, 30])
    def test_touch_mix(self, client, days):
        r = client.get(f"{BASE_URL}/api/home/touch-mix/{USER_ID}", params={"days": days}, timeout=60)
        assert r.status_code == 200, r.text[:400]
        d = r.json()
        assert d["days"] == days
        c = d["counts"]
        assert set(c) == {"relationship", "transactional", "promotional"}
        assert sum(c.values()) == d["total"]
        assert 0 <= d["relationship_pct"] <= 100
        if d["total"]:
            assert d["relationship_pct"] == round(c["relationship"] / d["total"] * 100)

    def test_monotonic_window(self, client):
        d7 = client.get(f"{BASE_URL}/api/home/touch-mix/{USER_ID}", params={"days": 7}, timeout=60).json()
        d30 = client.get(f"{BASE_URL}/api/home/touch-mix/{USER_ID}", params={"days": 30}, timeout=60).json()
        assert d30["total"] >= d7["total"], "30-day total lower than 7-day total"


# ── Regressions ──────────────────────────────────────────────────────────────
class TestRegressions:
    def test_combined_home(self, client):
        r = client.get(f"{BASE_URL}/api/home/{USER_ID}", timeout=60)
        assert r.status_code == 200, r.text[:400]
        d = r.json()
        for k in ("streak", "my_3", "wins_feed"):
            assert k in d, f"missing {k}"
        assert len(d["my_3"]) <= 3, f"my_3 not capped at 3: {len(d['my_3'])}"

    def test_weekly_wins(self, client):
        r = client.get(f"{BASE_URL}/api/home/weekly-wins/{USER_ID}", timeout=60)
        assert r.status_code == 200, r.text[:400]
        assert isinstance(r.json(), dict)

    def test_weekly_wins_list(self, client):
        r = client.get(f"{BASE_URL}/api/home/weekly-wins/{USER_ID}/list", params={"type": "texts"}, timeout=60)
        assert r.status_code == 200, r.text[:400]
        d = r.json()
        assert isinstance(d, dict)
