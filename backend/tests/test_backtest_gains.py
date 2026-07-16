"""Iteration 4: verify gains/ROI in POST /api/backtest response."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
TOKEN = os.environ.get("TEST_TOKEN")

pytestmark = pytest.mark.skipif(not TOKEN, reason="TEST_TOKEN env required")

EXPECTED_PAYOUTS = {
    "Rang 1 · Jackpot": 5_000_000.0,
    "Rang 2": 100_000.0,
    "Rang 3": 1_000.0,
    "Rang 4": 50.0,
    "Rang 5": 20.0,
    "Rang 6": 10.0,
    "Rang 7": 5.0,
    "Rang 8": 2.20,
    "Rang 9 · N° Chance": 2.20,
    "Perdu": 0.0,
}
GRID_COST = 2.20


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"})
    return s


class TestBacktestGains:
    def test_top_level_gains_metadata(self, client):
        r = client.post(f"{BASE_URL}/api/backtest",
                        json={"grids_per_strategy": 10, "sample_size": 50})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["grid_cost"] == GRID_COST
        assert d["payout_table"] == EXPECTED_PAYOUTS

    def test_per_strategy_gains_fields(self, client):
        r = client.post(f"{BASE_URL}/api/backtest",
                        json={"grids_per_strategy": 10, "sample_size": 50})
        d = r.json()
        strats = d["strategies"]
        assert len(strats) == 5
        for s in strats:
            for key in ("gross_gains", "total_cost", "net_gains", "roi_percent"):
                assert key in s, f"{key} missing in {s['strategy']}"
                assert isinstance(s[key], (int, float))
            # Cost math
            assert abs(s["total_cost"] - round(s["grids_tested"] * GRID_COST, 2)) < 0.01
            # Net math
            assert abs(s["net_gains"] - round(s["gross_gains"] - s["total_cost"], 2)) < 0.01
            # ROI math
            if s["total_cost"] > 0:
                expected_roi = round(s["net_gains"] / s["total_cost"] * 100, 2)
                assert abs(s["roi_percent"] - expected_roi) < 0.05
            # Gains never negative (gross), cost always positive
            assert s["gross_gains"] >= 0
            assert s["total_cost"] > 0

    def test_gains_consistency_with_rank_distribution(self, client):
        """Cross-check: gross_gains lower bound = sum of small rank counts × payouts.
        The rank_distribution only tracks main-matches count (0..5), not chance combos.
        So we can only assert gross_gains >= sum(main_matches only payouts for ranks 6, 4, 2 without chance).
        Simpler: since rank 8 (2 nums no chance) pays 2.20, and there's usually many, gross_gains > 0 for any strategy."""
        r = client.post(f"{BASE_URL}/api/backtest",
                        json={"grids_per_strategy": 15, "sample_size": 60})
        d = r.json()
        for s in d["strategies"]:
            # With 60 draws × 15 grids = 900 grids, expect at least *some* wins at rank 8 (2 main)
            # rank_distribution[2] × 2.20 gives lower bound (some of those 2-hit might also have chance = higher payout)
            # Use loose lower bound: gross_gains >= (rank_distribution[2] no-chance-fraction) — hard to compute exactly
            # Instead: verify gross_gains <= max possible = rank_dist[5]*5M + rank_dist[4]*1k + rank_dist[3]*20 + rank_dist[2]*5
            rd = s["rank_distribution"]
            upper = rd[5] * 5_000_000 + rd[4] * 1_000 + rd[3] * 20 + rd[2] * 5 + s["grids_tested"] * 2.20  # + chance-only
            assert s["gross_gains"] <= upper + 1
