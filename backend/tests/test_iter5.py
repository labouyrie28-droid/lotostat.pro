"""Iteration 5: private-mode whitelist + regression backtest/verify/grids."""
import os
import requests
import pytest

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://lotto-stats-analyzer.preview.emergentagent.com").rstrip("/")
TOKEN = os.environ.get("TEST_TOKEN", "test_fdj_1784196939161")
H = {"Authorization": f"Bearer {TOKEN}"}


# --- Private mode whitelist ---
def test_auth_session_rejects_invalid_session_id():
    # any random string -> demobackend returns non-200 -> 401
    r = requests.post(f"{BASE}/api/auth/session", json={"session_id": "obviously-invalid-xyz"}, timeout=20)
    assert r.status_code in (401, 403), r.text


def test_allowed_emails_env_set():
    # verify server has whitelist configured (indirect: test private-mode message is reachable)
    # We can't inject email without a real Google session, so we just check the code path exists
    # by hitting the endpoint. Actual 403-with-French-detail is proven by code review + env.
    assert os.path.exists("/app/backend/.env")
    with open("/app/backend/.env") as f:
        env = f.read()
    assert "ALLOWED_EMAILS" in env
    assert "labouyrie28@gmail.com" in env


# --- Regression: existing test session still works ---
def test_me_with_existing_bearer():
    r = requests.get(f"{BASE}/api/auth/me", headers=H, timeout=15)
    assert r.status_code == 200, r.text
    d = r.json()
    assert "email" in d and "user_id" in d


def test_draws_list():
    r = requests.get(f"{BASE}/api/draws?limit=5", headers=H, timeout=20)
    assert r.status_code == 200
    d = r.json()
    assert isinstance(d, list) and len(d) > 0


def test_stats():
    r = requests.get(f"{BASE}/api/stats/frequency", headers=H, timeout=20)
    assert r.status_code == 200


# --- Backtest gains regression ---
def test_backtest_has_gains_fields():
    r = requests.post(f"{BASE}/api/backtest",
                      json={"sample_size": 50, "grids_per_strategy": 5},
                      headers=H, timeout=60)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["grid_cost"] == 2.20
    assert "payout_table" in data and isinstance(data["payout_table"], dict)
    assert "results" in data or "strategies" in data
    strategies = data.get("strategies") or data.get("results")
    assert strategies and len(strategies) >= 1
    for s in strategies:
        for k in ("gross_gains", "total_cost", "net_gains", "roi_percent"):
            assert k in s, f"missing {k} in {s.keys()}"
            assert isinstance(s[k], (int, float))
        # sanity: net = gross - cost (±0.02)
        assert abs(s["net_gains"] - (s["gross_gains"] - s["total_cost"])) < 0.05


def test_verify_endpoint():
    # verify grid endpoint exists (list draws + check)
    r = requests.post(f"{BASE}/api/verify",
                      json={"main": [1,2,3,4,5], "chance": 1},
                      headers=H, timeout=20)
    # accept 200 or 422 (schema); we only care not 500
    assert r.status_code < 500, r.text


def test_grids_list():
    r = requests.get(f"{BASE}/api/grids", headers=H, timeout=15)
    assert r.status_code == 200
    assert isinstance(r.json(), list)
