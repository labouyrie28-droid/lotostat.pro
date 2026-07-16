"""Iteration 7: POST /grids/verify-batch + auto-load code path."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://lotto-stats-analyzer.preview.emergentagent.com").rstrip("/")
TOKEN = "test_fdj_1784196939161"
H = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}


# --- verify-batch happy path ---
def test_verify_batch_three_grids():
    payload = {"grids": [
        {"numbers": [7, 13, 22, 31, 46], "chance": 5},
        {"numbers": [1, 2, 3, 4, 5], "chance": 1},
        {"numbers": [10, 20, 30, 40, 49], "chance": 7},
    ]}
    r = requests.post(f"{BASE_URL}/api/grids/verify-batch", json=payload, headers=H)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["total_draws"] == 1048
    assert d["grids_count"] == 3
    assert len(d["results"]) == 3
    for i, res in enumerate(d["results"]):
        assert res["index"] == i
        assert "grid" in res and "distribution" in res
        assert "avg_main_matches" in res and "gross_gain" in res
        assert "hit_3plus" in res and "hit_2plus" in res and "per_rank" in res
        assert isinstance(res["distribution"], list) and len(res["distribution"]) == 6
    for k in ("by_avg", "by_gain", "by_hits_3plus"):
        assert k in d["best"]
        assert 0 <= d["best"][k] < 3


# --- validation errors ---
def test_verify_batch_empty():
    r = requests.post(f"{BASE_URL}/api/grids/verify-batch", json={"grids": []}, headers=H)
    assert r.status_code == 400


def test_verify_batch_too_many():
    grids = [{"numbers": [1, 2, 3, 4, 5], "chance": 1}] * 11
    r = requests.post(f"{BASE_URL}/api/grids/verify-batch", json={"grids": grids}, headers=H)
    assert r.status_code == 400


def test_verify_batch_invalid_grid():
    payload = {"grids": [
        {"numbers": [1, 2, 3, 4, 5], "chance": 1},
        {"numbers": [1, 2, 3, 4, 50], "chance": 1},  # 50 invalid
    ]}
    r = requests.post(f"{BASE_URL}/api/grids/verify-batch", json=payload, headers=H)
    assert r.status_code == 400
    assert "Grille #2" in r.json()["detail"]


# --- load-official still delegates ---
def test_load_official_still_works():
    r = requests.post(f"{BASE_URL}/api/draws/load-official", headers=H)
    assert r.status_code == 200
    d = r.json()
    assert d.get("inserted", 0) >= 1000


# --- code-path check for auto-load in /auth/session ---
def test_auto_load_code_path_exists():
    with open("/app/backend/server.py") as f:
        src = f.read()
    # auto-load block inside create_session
    assert "existing_draws = await db.draws.count_documents" in src
    assert "await _load_official_for_user(user_id)" in src
    # helper defined
    assert "async def _load_official_for_user(user_id: str)" in src
