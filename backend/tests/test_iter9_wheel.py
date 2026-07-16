"""Iteration 9 - Wheel / Système Réducteur backend tests."""
import os
import math
from itertools import combinations
import pytest
import requests
from dotenv import load_dotenv

load_dotenv('/app/frontend/.env')
BASE_URL = os.environ['REACT_APP_BACKEND_URL'].rstrip('/')
TOKEN = "test_session_wheel_1784202905"
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}


def _post(payload):
    return requests.post(f"{BASE_URL}/api/grids/wheel", json=payload, headers=HEADERS, timeout=60)


# ---------- Happy path ----------
def test_wheel_pool8_target3_chance5():
    r = _post({"numbers": list(range(1, 9)), "target_matches": 3, "chance": 5})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["pool"] == list(range(1, 9))
    assert d["pool_size"] == 8
    assert d["target_matches"] == 3
    assert 8 <= d["tickets_count"] <= 12  # greedy ~9-10 expected
    assert d["cost_euros"] == round(d["tickets_count"] * 2.20, 2)
    assert all(t["chance"] == 5 for t in d["tickets"])
    assert all(len(t["numbers"]) == 5 for t in d["tickets"])
    # metrics
    assert abs(d["p_pool_covers_pct"] - 2.562) < 0.05
    assert abs(d["p_single_random_pct"] - 0.508) < 0.05
    assert abs(d["improvement_factor"] - 5.05) < 0.3


# ---------- Coverage correctness ----------
def test_wheel_covers_all_tsubsets_k8_t3():
    r = _post({"numbers": list(range(1, 9)), "target_matches": 3, "chance": 5})
    d = r.json()
    tickets = [set(t["numbers"]) for t in d["tickets"]]
    for sub in combinations(range(1, 9), 3):
        covered = any(set(sub).issubset(t) for t in tickets)
        assert covered, f"3-subset {sub} not covered"


def test_wheel_covers_all_k10_t3():
    r = _post({"numbers": list(range(1, 11)), "target_matches": 3, "chance": 7})
    d = r.json()
    assert d["pool_size"] == 10
    tickets = [set(t["numbers"]) for t in d["tickets"]]
    for sub in combinations(range(1, 11), 3):
        assert any(set(sub).issubset(t) for t in tickets), f"missing {sub}"


# ---------- Size scaling ----------
def test_wheel_size_scaling():
    counts = {}
    p_covers = {}
    for k in (6, 8, 10, 12):
        nums = list(range(1, k + 1))
        r = _post({"numbers": nums, "target_matches": 3, "chance": 3})
        assert r.status_code == 200
        d = r.json()
        counts[k] = d["tickets_count"]
        p_covers[k] = d["p_pool_covers_pct"]
    # Ranges from problem statement
    assert 3 <= counts[6] <= 6
    assert 7 <= counts[8] <= 12
    assert 15 <= counts[10] <= 25
    assert 28 <= counts[12] <= 40
    # Probability monotonic increasing
    assert p_covers[6] < p_covers[8] < p_covers[10] < p_covers[12]


# ---------- Validation ----------
def test_wheel_duplicates_400():
    r = _post({"numbers": [1, 2, 3, 4, 5, 5, 7, 8], "target_matches": 3, "chance": 5})
    assert r.status_code == 400


def test_wheel_pool_too_small():
    r = _post({"numbers": [1, 2, 3, 4, 5], "target_matches": 3, "chance": 5})
    assert r.status_code == 400


def test_wheel_pool_too_large():
    r = _post({"numbers": list(range(1, 14)), "target_matches": 3, "chance": 5})
    assert r.status_code == 400


def test_wheel_target_invalid():
    r = _post({"numbers": list(range(1, 9)), "target_matches": 2, "chance": 5})
    assert r.status_code == 400


def test_wheel_target_gt_pool():
    # target=5 with pool of 6 numbers is legal (5 <= 6). But target>K fails.
    # Instead use non-standard target which is caught by t not in {3,4,5}.
    # Test t=6 which is > pool size 6 AND not in {3,4,5}. Should 400.
    r = _post({"numbers": [1, 2, 3, 4, 5, 6], "target_matches": 6, "chance": 5})
    assert r.status_code == 400


def test_wheel_number_out_of_range():
    r = _post({"numbers": [1, 2, 3, 4, 5, 6, 50, 8], "target_matches": 3, "chance": 5})
    assert r.status_code == 400


def test_wheel_chance_out_of_range():
    r = _post({"numbers": list(range(1, 9)), "target_matches": 3, "chance": 11})
    assert r.status_code == 400


def test_wheel_unauthenticated():
    r = requests.post(f"{BASE_URL}/api/grids/wheel",
                      json={"numbers": list(range(1, 9)), "target_matches": 3, "chance": 5},
                      timeout=15)
    assert r.status_code == 401
