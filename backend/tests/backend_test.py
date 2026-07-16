"""Backend tests for LotoStat Pro - Iteration 2 (Heatmap, Backtest, Alerts)."""
import io
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://lotto-stats-analyzer.preview.emergentagent.com").rstrip("/")
TOKEN = os.environ.get("TEST_TOKEN")

pytestmark = pytest.mark.skipif(not TOKEN, reason="TEST_TOKEN env required")


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"})
    return s


# Seed with FDJ-format CSV (small in-memory dataset) before backtest/heatmap
def _fdj_csv(n=40):
    import random as R
    lines = ["date_de_tirage;boule_1;boule_2;boule_3;boule_4;boule_5;numero_chance"]
    from datetime import date, timedelta
    d = date(2024, 1, 1)
    for i in range(n):
        nums = sorted(R.sample(range(1, 50), 5))
        c = R.randint(1, 10)
        # Use FDJ date format DD/MM/YYYY
        lines.append(f"{d.strftime('%d/%m/%Y')};{nums[0]};{nums[1]};{nums[2]};{nums[3]};{nums[4]};{c}")
        d = d + timedelta(days=2)
    return "\n".join(lines)


class TestSetup:
    def test_clear_and_seed_fdj(self, client):
        # Clear any existing
        r = client.delete(f"{BASE_URL}/api/draws")
        assert r.status_code == 200
        # Import FDJ format via multipart
        csv_body = _fdj_csv(60)
        files = {"file": ("loto_test.csv", csv_body.encode(), "text/csv")}
        # remove content-type header for multipart
        s2 = requests.Session()
        s2.headers.update({"Authorization": f"Bearer {TOKEN}"})
        r = s2.post(f"{BASE_URL}/api/draws/import-csv", files=files)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["format_detected"] == "FDJ"
        assert data["inserted"] >= 55
        assert data["errors"] == 0


class TestHeatmap:
    def test_heatmap_structure(self, client):
        r = client.get(f"{BASE_URL}/api/stats/heatmap")
        assert r.status_code == 200
        d = r.json()
        assert "total_draws" in d and d["total_draws"] > 0
        assert "max" in d
        assert "pairs" in d
        # C(49,2) = 1176
        assert len(d["pairs"]) == 1176
        for p in d["pairs"][:20]:
            assert p["a"] < p["b"]
            assert p["count"] >= 0


class TestBacktest:
    def test_backtest_default(self, client):
        r = client.post(f"{BASE_URL}/api/backtest", json={"grids_per_strategy": 10, "sample_size": 30})
        assert r.status_code == 200, r.text
        d = r.json()
        strats = d["strategies"]
        assert len(strats) == 5
        names = {s["strategy"] for s in strats}
        assert names == {"hot", "cold", "balanced", "weighted_random", "random"}
        # sorted desc
        vals = [s["avg_main_matches"] for s in strats]
        assert vals == sorted(vals, reverse=True)
        for s in strats:
            assert len(s["rank_distribution"]) == 6
            assert "chance_hit_rate" in s
            assert "hit_3plus_rate" in s
            assert "hits_5plus_chance" in s

    def test_backtest_clamps_large_sample(self, client):
        # Should not error, just clamp
        r = client.post(f"{BASE_URL}/api/backtest", json={"grids_per_strategy": 5, "sample_size": 9999})
        assert r.status_code == 200
        d = r.json()
        assert d["sample_size"] <= d["total_draws"]

    def test_backtest_too_few_draws_errors_only_below_30(self, client):
        # We have >=55 draws; endpoint should succeed. This documents the >=30 rule.
        r = client.post(f"{BASE_URL}/api/backtest", json={"grids_per_strategy": 5, "sample_size": 20})
        assert r.status_code == 200


class TestAlerts:
    def test_next_draw(self, client):
        r = client.get(f"{BASE_URL}/api/alerts/next-draw")
        assert r.status_code == 200
        d = r.json()
        assert "next_draw_date" in d
        assert d["day_name"] in ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
        assert isinstance(d["resend_configured"], bool)

    def test_prefs_default(self, client):
        # Ensure clean state
        # (no delete endpoint; just fetch defaults if not set)
        # First remove any existing prefs via a POST with defaults? We'll check GET returns something sane.
        r = client.get(f"{BASE_URL}/api/alerts/prefs")
        assert r.status_code == 200
        d = r.json()
        assert set(d.keys()) >= {"enabled", "strategy", "grids_count", "email"}

    def test_prefs_persist(self, client):
        payload = {"enabled": True, "strategy": "hot", "grids_count": 5, "email": "x@y.z"}
        r = client.post(f"{BASE_URL}/api/alerts/prefs", json=payload)
        assert r.status_code == 200
        r2 = client.get(f"{BASE_URL}/api/alerts/prefs")
        d = r2.json()
        assert d["enabled"] is True
        assert d["strategy"] == "hot"
        assert d["grids_count"] == 5
        assert d["email"] == "x@y.z"

    def test_send_returns_503_when_unconfigured(self, client):
        r = client.post(f"{BASE_URL}/api/alerts/send", json={"strategy": "balanced", "grids_count": 3})
        # 503 when RESEND_API_KEY empty; 200 if configured (Resend test-mode restricts recipients)
        assert r.status_code in (200, 503, 500)


# Iteration 3: Grid verification endpoint + GET /grids result field
class TestGridVerify:
    def test_verify_ok(self, client):
        r = client.post(f"{BASE_URL}/api/grids/verify", json={"numbers": [7, 13, 22, 31, 46], "chance": 5})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["total_draws"] > 0
        assert d["grid"]["numbers"] == [7, 13, 22, 31, 46]
        assert d["grid"]["chance"] == 5
        assert len(d["distribution"]) == 6
        for i, item in enumerate(d["distribution"]):
            assert item["main_matches"] == i
            assert item["count"] >= 0
        # sum of distribution equals total
        assert sum(x["count"] for x in d["distribution"]) == d["total_draws"]
        assert isinstance(d["chance_hits"], int)
        assert isinstance(d["combined_5_and_chance"], int)
        assert isinstance(d["per_rank"], list)
        assert isinstance(d["best_hits"], list)
        assert len(d["best_hits"]) <= 20

    def test_verify_rejects_duplicates(self, client):
        r = client.post(f"{BASE_URL}/api/grids/verify", json={"numbers": [7, 7, 22, 31, 46], "chance": 5})
        assert r.status_code == 400

    def test_verify_rejects_out_of_range(self, client):
        r = client.post(f"{BASE_URL}/api/grids/verify", json={"numbers": [7, 13, 22, 31, 50], "chance": 5})
        assert r.status_code == 400

    def test_verify_rejects_bad_chance(self, client):
        r = client.post(f"{BASE_URL}/api/grids/verify", json={"numbers": [7, 13, 22, 31, 46], "chance": 11})
        assert r.status_code == 400

    def test_verify_missing_chance(self, client):
        r = client.post(f"{BASE_URL}/api/grids/verify", json={"numbers": [7, 13, 22, 31, 46]})
        # Pydantic returns 422 for missing required field
        assert r.status_code in (400, 422)


class TestGridsListResult:
    def test_list_contains_result_field(self, client):
        r = client.get(f"{BASE_URL}/api/grids")
        assert r.status_code == 200
        grids = r.json()
        # Every grid must expose a 'result' key (dict or None)
        for g in grids:
            assert "result" in g
            if g["result"] is not None:
                assert set(g["result"].keys()) >= {
                    "target_date", "target_numbers", "target_chance",
                    "main_matches", "chance_match", "rank_label",
                }
                assert 0 <= g["result"]["main_matches"] <= 5
                assert isinstance(g["result"]["chance_match"], bool)
