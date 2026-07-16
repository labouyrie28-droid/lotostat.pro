"""Iteration 11 — Whitelist disabled (ALLOWED_EMAILS='').
Verify that any authenticated user (not just labouyrie28@gmail.com) can access
protected endpoints. Also verify auto-load path exists in server.py, unauth
returns 401, and public root returns 200."""

import os
import time
import uuid
import subprocess
import pytest
import requests

def _load_backend_url():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if v:
        return v.rstrip("/")
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip().strip('"').rstrip("/")
    except FileNotFoundError:
        pass
    raise RuntimeError("REACT_APP_BACKEND_URL not set")

BASE_URL = _load_backend_url()


def _mongo_eval(js):
    r = subprocess.run(
        ["mongosh", "mongodb://localhost:27017/test_database", "--quiet", "--eval", js],
        capture_output=True, text=True, timeout=30,
    )
    return r.stdout.strip(), r.stderr.strip(), r.returncode


def _make_session(email):
    uid = f"test_iter11_{uuid.uuid4().hex[:10]}"
    tok = f"test_iter11_tok_{uuid.uuid4().hex[:16]}"
    js = f"""
    db.users.insertOne({{
      user_id: '{uid}', email: '{email}', name: 'Iter11 Tester',
      picture: null, created_at: new Date().toISOString()
    }});
    db.user_sessions.insertOne({{
      user_id: '{uid}', session_token: '{tok}',
      expires_at: new Date(Date.now()+7*24*3600*1000).toISOString(),
      created_at: new Date().toISOString()
    }});
    print('OK');
    """
    out, err, rc = _mongo_eval(js)
    assert rc == 0 and "OK" in out, f"mongo insert failed: {err} / {out}"
    return uid, tok


def _cleanup(uid):
    _mongo_eval(
        f"db.user_sessions.deleteMany({{user_id:'{uid}'}}); "
        f"db.users.deleteMany({{user_id:'{uid}'}}); "
        f"db.draws.deleteMany({{user_id:'{uid}'}}); "
        f"db.saved_grids.deleteMany({{user_id:'{uid}'}}); "
        f"db.alert_prefs.deleteMany({{user_id:'{uid}'}});"
    )


@pytest.fixture(scope="module")
def new_user_session():
    """Fresh non-whitelisted user with pre-seeded draws (to test protected endpoints
    without depending on auto-load which only runs via /auth/session)."""
    email = f"test.iter11+{uuid.uuid4().hex[:6]}@example.com"
    uid, tok = _make_session(email)
    # seed 30 draws so grids/verify + wheel work independently of auto-load
    draws_js = "var docs=[];"
    for i in range(30):
        # rotate 5 unique numbers deterministically
        base = (i * 3) % 40 + 1
        nums = sorted({base, base + 1, base + 3, base + 5, base + 7})
        while len(nums) < 5:
            nums.add(((base + len(nums) * 11) % 49) + 1)
        nums = sorted(list(nums))[:5]
        draws_js += (
            f"docs.push({{id:'d{i}_{uid}', user_id:'{uid}', "
            f"date:'2024-{((i%12)+1):02d}-{((i%27)+1):02d}', "
            f"numbers:[{','.join(str(n) for n in nums)}], chance:{(i%10)+1}}});"
        )
    draws_js += "db.draws.insertMany(docs); print('SEEDED');"
    _mongo_eval(draws_js)
    yield {"user_id": uid, "token": tok, "email": email}
    _cleanup(uid)


@pytest.fixture(scope="module")
def whitelisted_session():
    """Regression: session for the previously-whitelisted email."""
    uid, tok = _make_session("labouyrie28@gmail.com")
    yield {"user_id": uid, "token": tok}
    # only cleanup the ephemeral session; DO NOT delete the real user's data
    _mongo_eval(f"db.user_sessions.deleteMany({{session_token:'{tok}'}});")
    _mongo_eval(f"db.users.deleteMany({{user_id:'{uid}'}});")
    _mongo_eval(f"db.draws.deleteMany({{user_id:'{uid}'}});")


# ---------- Public / unauth ----------

def test_public_root_200():
    r = requests.get(f"{BASE_URL}/api/")
    assert r.status_code == 200
    assert "LotoStat" in r.json().get("message", "")


def test_unauth_me_401():
    r = requests.get(f"{BASE_URL}/api/auth/me")
    assert r.status_code == 401


def test_unauth_draws_401():
    r = requests.get(f"{BASE_URL}/api/draws")
    assert r.status_code == 401


def test_invalid_token_401():
    r = requests.get(f"{BASE_URL}/api/auth/me",
                     headers={"Authorization": "Bearer nope_nope_nope"})
    assert r.status_code == 401


# ---------- New (non-whitelisted) user can access everything ----------

def test_new_user_auth_me(new_user_session):
    r = requests.get(
        f"{BASE_URL}/api/auth/me",
        headers={"Authorization": f"Bearer {new_user_session['token']}"},
    )
    assert r.status_code == 200, f"expected 200, got {r.status_code} body={r.text}"
    body = r.json()
    assert body["email"] == new_user_session["email"]
    assert body["user_id"] == new_user_session["user_id"]


def test_new_user_draws_list(new_user_session):
    r = requests.get(
        f"{BASE_URL}/api/draws",
        headers={"Authorization": f"Bearer {new_user_session['token']}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) >= 1  # seeded


def test_new_user_grids_verify(new_user_session):
    r = requests.post(
        f"{BASE_URL}/api/grids/verify",
        headers={"Authorization": f"Bearer {new_user_session['token']}"},
        json={"numbers": [1, 2, 3, 4, 5], "chance": 3},
    )
    assert r.status_code == 200, f"body={r.text}"
    body = r.json()
    assert "total_draws" in body and body["total_draws"] > 0
    assert "distribution" in body and len(body["distribution"]) == 6


def test_new_user_grids_wheel(new_user_session):
    r = requests.post(
        f"{BASE_URL}/api/grids/wheel",
        headers={"Authorization": f"Bearer {new_user_session['token']}"},
        json={"numbers": [1, 7, 13, 19, 25, 31, 37], "target_matches": 3},
    )
    assert r.status_code == 200, f"body={r.text}"
    body = r.json()
    assert body["pool_size"] == 7
    assert body["target_matches"] == 3
    assert body["tickets_count"] >= 1
    assert len(body["tickets"]) == body["tickets_count"]


def test_new_user_stats_frequency(new_user_session):
    r = requests.get(
        f"{BASE_URL}/api/stats/frequency",
        headers={"Authorization": f"Bearer {new_user_session['token']}"},
    )
    assert r.status_code == 200
    assert r.json()["total_draws"] >= 1


# ---------- Whitelisted user regression ----------

def test_whitelisted_still_works(whitelisted_session):
    r = requests.get(
        f"{BASE_URL}/api/auth/me",
        headers={"Authorization": f"Bearer {whitelisted_session['token']}"},
    )
    assert r.status_code == 200
    assert r.json()["email"] == "labouyrie28@gmail.com"


# ---------- Config sanity ----------

def test_allowed_emails_empty_in_env():
    """Ensure the env truly has an empty whitelist (config guard)."""
    with open("/app/backend/.env") as f:
        content = f.read()
    assert 'ALLOWED_EMAILS=""' in content or "ALLOWED_EMAILS=''" in content or \
           "ALLOWED_EMAILS=\n" in content, "ALLOWED_EMAILS must be empty"


def test_autoload_code_present():
    """Static check that /auth/session still calls _load_official_for_user."""
    with open("/app/backend/server.py") as f:
        src = f.read()
    assert "_load_official_for_user(user_id)" in src
    assert "existing_draws = await db.draws.count_documents" in src
