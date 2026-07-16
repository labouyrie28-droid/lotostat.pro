"""Iteration 8 tests: credible_top5 strategy + /draws limit >500."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://lotto-stats-analyzer.preview.emergentagent.com").rstrip("/")
TOKEN = "test_fdj_1784196939161"  # user with 1048 real FDJ draws


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"})
    return s


# --- credible_top5 strategy ---
class TestCredibleTop5:
    def test_basic_shape(self, client):
        r = client.post(f"{BASE_URL}/api/grids/generate", json={"strategy": "credible_top5"})
        assert r.status_code == 200, r.text
        data = r.json()
        assert "grids" in data and "pool_size" in data and "credibility_stats" in data
        assert data["pool_size"] == 10
        assert len(data["grids"]) == 5

        stats = data["credibility_stats"]
        assert set(stats.keys()) >= {"hist_sum_mean", "hist_sum_sigma", "hist_even_mean"}
        # Historical FDJ sum mean should be around 124.7
        assert 120 <= stats["hist_sum_mean"] <= 130, stats
        # Historical even count around 2.5
        assert 2.0 <= stats["hist_even_mean"] <= 3.0, stats

    def test_grid_fields_and_sort(self, client):
        r = client.post(f"{BASE_URL}/api/grids/generate", json={"strategy": "credible_top5"})
        data = r.json()
        prev_score = None
        for g in data["grids"]:
            assert set(g.keys()) >= {"numbers", "chance", "score", "sum", "evens", "strategy"}
            assert g["strategy"] == "credible_top5"
            assert len(g["numbers"]) == 5
            assert all(1 <= n <= 49 for n in g["numbers"])
            assert 1 <= g["chance"] <= 10
            assert g["sum"] == sum(g["numbers"])
            assert g["evens"] == sum(1 for n in g["numbers"] if n % 2 == 0)
            assert isinstance(g["score"], (int, float))
            if prev_score is not None:
                assert g["score"] <= prev_score, "grids not sorted desc by score"
            prev_score = g["score"]

    def test_sums_close_to_mean(self, client):
        # Sample mean of grid sums should generally be nearer to hist mean than uniform expectation
        r = client.post(f"{BASE_URL}/api/grids/generate", json={"strategy": "credible_top5"})
        data = r.json()
        mean = data["credibility_stats"]["hist_sum_mean"]
        sums = [g["sum"] for g in data["grids"]]
        avg = sum(sums) / len(sums)
        assert abs(avg - mean) < 40, f"grid avg sum {avg} too far from hist mean {mean}"


# --- Regression: other strategies still work ---
class TestOtherStrategiesRegression:
    @pytest.mark.parametrize("strat", ["hot", "cold", "balanced", "weighted_random"])
    def test_strategy(self, client, strat):
        r = client.post(f"{BASE_URL}/api/grids/generate", json={"strategy": strat, "count": 3})
        assert r.status_code == 200, r.text
        data = r.json()
        assert "grids" in data
        assert len(data["grids"]) == 3
        for g in data["grids"]:
            assert len(g["numbers"]) == 5
            assert 1 <= g["chance"] <= 10
            assert g.get("strategy") == strat

    def test_invalid_strategy_rejected(self, client):
        r = client.post(f"{BASE_URL}/api/grids/generate", json={"strategy": "nonsense"})
        assert r.status_code == 422

    def test_credible_top5_accepted_no_422(self, client):
        r = client.post(f"{BASE_URL}/api/grids/generate", json={"strategy": "credible_top5"})
        assert r.status_code != 422


# --- Draws limit ---
class TestDrawsLimit:
    def test_default_returns_500(self, client):
        r = client.get(f"{BASE_URL}/api/draws")
        assert r.status_code == 200
        assert len(r.json()) == 500  # default cap

    def test_limit_1500_returns_all_1048(self, client):
        r = client.get(f"{BASE_URL}/api/draws?limit=1500")
        assert r.status_code == 200
        rows = r.json()
        assert len(rows) == 1048, f"expected 1048 got {len(rows)}"
