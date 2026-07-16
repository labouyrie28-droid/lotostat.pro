"""Iteration 10 — Post code-review fix regression tests."""
import os
import requests
import pytest

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else "https://lotto-stats-analyzer.preview.emergentagent.com"

WL_TOKEN = os.environ.get("WL_TOKEN", "test_wl_1784203853043")
BAD_TOKEN = os.environ.get("BAD_TOKEN", "test_bad_tok_1784203853045")


def _h(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


# --------- Root import health (LOW FIX: imports cleaned) ---------
def test_root_api_ok():
    r = requests.get(f"{BASE_URL}/api/")
    assert r.status_code == 200
    assert r.json().get("message") == "LotoStat Pro API"


# --------- MEDIUM: whitelist enforcement ---------
def test_whitelist_rejects_non_allowed_email():
    r = requests.get(f"{BASE_URL}/api/grids", headers=_h(BAD_TOKEN))
    assert r.status_code == 403
    assert "Accès refusé" in r.json().get("detail", "")


def test_whitelist_allows_allowed_email():
    r = requests.get(f"{BASE_URL}/api/grids", headers=_h(WL_TOKEN))
    assert r.status_code == 200


# --------- HIGH: MyGrids result historical fallback ---------
def test_save_grid_then_list_has_historical_result():
    payload = {"strategy": "hot", "numbers": [1, 2, 3, 4, 5], "chance": 7}
    r = requests.post(f"{BASE_URL}/api/grids/save", json=payload, headers=_h(WL_TOKEN))
    assert r.status_code == 200, r.text
    saved_id = r.json()["id"]

    r2 = requests.get(f"{BASE_URL}/api/grids", headers=_h(WL_TOKEN))
    assert r2.status_code == 200
    grids = r2.json()
    match = next((g for g in grids if g["id"] == saved_id), None)
    assert match is not None, "Saved grid missing from list"
    assert match.get("result") is not None, "result must not be None (historical fallback)"
    assert match["result"].get("is_historical") is True
    assert "target_date" in match["result"]
    assert "rank_label" in match["result"]

    # cleanup
    requests.delete(f"{BASE_URL}/api/grids/{saved_id}", headers=_h(WL_TOKEN))


# --------- MEDIUM: wheel input validation ---------
def test_wheel_rejects_target5_with_pool_gt8():
    payload = {"numbers": [1, 2, 3, 4, 5, 6, 7, 8, 9], "target_matches": 5, "chance": 3}
    r = requests.post(f"{BASE_URL}/api/grids/wheel", json=payload, headers=_h(WL_TOKEN))
    assert r.status_code == 400
    assert "target 5+" in r.json().get("detail", "") or "8 numéros" in r.json().get("detail", "")


def test_wheel_accepts_target5_pool8():
    payload = {"numbers": [1, 2, 3, 4, 5, 6, 7, 8], "target_matches": 5, "chance": 3}
    r = requests.post(f"{BASE_URL}/api/grids/wheel", json=payload, headers=_h(WL_TOKEN))
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["tickets_count"] >= 1
    assert data["target_matches"] == 5


# --------- MEDIUM: wheel correctness (K=8, t=3) ---------
def test_wheel_k8_t3_correctness():
    payload = {"numbers": [1, 2, 3, 4, 5, 6, 7, 8], "target_matches": 3, "chance": 3}
    r = requests.post(f"{BASE_URL}/api/grids/wheel", json=payload, headers=_h(WL_TOKEN))
    assert r.status_code == 200, r.text
    data = r.json()
    # Expected ~9 tickets, p_pool ≈ 2.562%
    assert 8 <= data["tickets_count"] <= 12
    assert abs(data["p_pool_covers_pct"] - 2.562) < 0.01
    assert abs(data["p_single_random_pct"] - 0.508) < 0.02


# --------- LOW: credible_top5 clamp ---------
def test_credible_top5_scores_in_range():
    r = requests.post(f"{BASE_URL}/api/grids/generate",
                      json={"strategy": "credible_top5", "count": 5},
                      headers=_h(WL_TOKEN))
    assert r.status_code == 200, r.text
    grids = r.json()["grids"]
    assert len(grids) >= 1
    for g in grids:
        assert 0.0 <= g["score"] <= 1.0, f"score out of range: {g['score']}"


# --------- Regression: all strategies ---------
@pytest.mark.parametrize("strat", ["hot", "cold", "balanced", "weighted_random"])
def test_generate_strategies(strat):
    r = requests.post(f"{BASE_URL}/api/grids/generate",
                      json={"strategy": strat, "count": 2}, headers=_h(WL_TOKEN))
    assert r.status_code == 200
    grids = r.json()["grids"]
    assert len(grids) == 2
    for g in grids:
        assert len(g["numbers"]) == 5
        assert all(1 <= n <= 49 for n in g["numbers"])
        assert 1 <= g["chance"] <= 10


# --------- Regression: verify / verify-batch / stats / backtest / alerts ---------
def test_verify_endpoint():
    r = requests.post(f"{BASE_URL}/api/grids/verify",
                      json={"numbers": [1, 2, 3, 4, 5], "chance": 7},
                      headers=_h(WL_TOKEN))
    assert r.status_code == 200


def test_verify_batch():
    r = requests.post(f"{BASE_URL}/api/grids/verify-batch",
                      json={"grids": [
                          {"numbers": [1, 2, 3, 4, 5], "chance": 7},
                          {"numbers": [10, 20, 30, 40, 49], "chance": 3},
                      ]}, headers=_h(WL_TOKEN))
    assert r.status_code == 200


@pytest.mark.parametrize("path", [
    "/api/stats/frequency",
    "/api/stats/hot-cold",
    "/api/stats/pairs",
    "/api/alerts/prefs",
    "/api/alerts/next-draw",
])
def test_misc_get_endpoints(path):
    r = requests.get(f"{BASE_URL}{path}", headers=_h(WL_TOKEN))
    assert r.status_code == 200, f"{path} -> {r.status_code}: {r.text[:200]}"


def test_backtest():
    r = requests.post(f"{BASE_URL}/api/backtest",
                      json={"strategy": "balanced", "window": 100, "count": 3},
                      headers=_h(WL_TOKEN))
    # Should be 200 or 400 with meaningful msg
    assert r.status_code in (200, 400), r.text
