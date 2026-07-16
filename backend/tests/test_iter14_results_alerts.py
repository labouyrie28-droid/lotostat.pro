"""Iter 14 tests: Feature #12 (auto-results email) + PWA endpoints."""
import os
import time
import subprocess
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://lotto-stats-analyzer.preview.emergentagent.com").rstrip("/")


def _mongo(js: str) -> str:
    r = subprocess.run(["mongosh", "--quiet", "--eval", f"use('test_database');{js}"], capture_output=True, text=True)
    return r.stdout.strip()


@pytest.fixture(scope="module")
def fresh_session():
    """New user, no draws — used for defaults + legacy payload + 400 error."""
    uid = f"TEST_iter14_fresh_{int(time.time()*1000)}"
    tok = f"tok_iter14_fresh_{int(time.time()*1000)}"
    _mongo(
        f"db.users.insertOne({{user_id:'{uid}',email:'labouyrie28@gmail.com',name:'T',created_at:new Date().toISOString()}});"
        f"db.user_sessions.insertOne({{user_id:'{uid}',session_token:'{tok}',"
        f"expires_at:new Date(Date.now()+7*24*3600*1000).toISOString(),created_at:new Date().toISOString()}});"
    )
    yield {"user_id": uid, "token": tok}
    _mongo(f"db.users.deleteOne({{user_id:'{uid}'}});db.user_sessions.deleteMany({{user_id:'{uid}'}});db.alert_prefs.deleteMany({{user_id:'{uid}'}});")


@pytest.fixture(scope="module")
def seeded_session():
    """Session for a seeded user that has 1048 draws — needed to send real results email."""
    uid = "test-fdj-1784196939161"
    tok = f"tok_iter14_seeded_{int(time.time()*1000)}"
    _mongo(
        f"db.users.updateOne({{user_id:'{uid}'}},{{$set:{{email:'labouyrie28@gmail.com',name:'Seeded',user_id:'{uid}'}}}},{{upsert:true}});"
        f"db.user_sessions.insertOne({{user_id:'{uid}',session_token:'{tok}',"
        f"expires_at:new Date(Date.now()+7*24*3600*1000).toISOString(),created_at:new Date().toISOString()}});"
        f"db.saved_grids.insertOne({{id:'TEST_grid_{int(time.time()*1000)}',user_id:'{uid}',"
        f"numbers:[1,2,3,4,5],chance:1,strategy:'test',created_at:'2020-01-01T00:00:00'}});"
    )
    yield {"user_id": uid, "token": tok}
    _mongo(f"db.user_sessions.deleteMany({{session_token:'{tok}'}});db.saved_grids.deleteMany({{user_id:'{uid}',id:/^TEST_/}});")


def _h(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


# --------- alert prefs ---------

def test_get_prefs_default_has_results_enabled(fresh_session):
    r = requests.get(f"{BASE_URL}/api/alerts/prefs", headers=_h(fresh_session["token"]))
    assert r.status_code == 200
    data = r.json()
    assert data["results_enabled"] is False
    assert data["enabled"] is False


def test_post_prefs_persists_results_enabled_true(fresh_session):
    payload = {"enabled": True, "strategy": "balanced", "grids_count": 3, "results_enabled": True}
    r = requests.post(f"{BASE_URL}/api/alerts/prefs", headers=_h(fresh_session["token"]), json=payload)
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    # verify persistence
    g = requests.get(f"{BASE_URL}/api/alerts/prefs", headers=_h(fresh_session["token"])).json()
    assert g["results_enabled"] is True
    assert g["enabled"] is True


def test_post_prefs_persists_results_enabled_false(fresh_session):
    payload = {"enabled": False, "strategy": "hot", "grids_count": 5, "results_enabled": False}
    r = requests.post(f"{BASE_URL}/api/alerts/prefs", headers=_h(fresh_session["token"]), json=payload)
    assert r.status_code == 200
    g = requests.get(f"{BASE_URL}/api/alerts/prefs", headers=_h(fresh_session["token"])).json()
    assert g["results_enabled"] is False
    assert g["strategy"] == "hot"
    assert g["grids_count"] == 5


def test_post_prefs_legacy_payload_no_results_enabled(fresh_session):
    """Backward compat: old payload without results_enabled should default to False."""
    payload = {"enabled": True, "strategy": "cold", "grids_count": 2}
    r = requests.post(f"{BASE_URL}/api/alerts/prefs", headers=_h(fresh_session["token"]), json=payload)
    assert r.status_code == 200
    g = requests.get(f"{BASE_URL}/api/alerts/prefs", headers=_h(fresh_session["token"])).json()
    assert g["results_enabled"] is False
    assert g["strategy"] == "cold"


# --------- send-results endpoint ---------

def test_send_results_no_draws_returns_400(fresh_session):
    r = requests.post(f"{BASE_URL}/api/alerts/send-results", headers=_h(fresh_session["token"]))
    assert r.status_code == 400
    assert "tirage" in r.json()["detail"].lower()


def test_send_results_success_with_eligible_grid(seeded_session):
    r = requests.post(f"{BASE_URL}/api/alerts/send-results", headers=_h(seeded_session["token"]))
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["status"] == "sent"
    assert data["to"] == "labouyrie28@gmail.com"
    assert data["grids_count"] >= 1
    assert "total_won" in data and "total_cost" in data and "draw_date" in data
    assert isinstance(data["total_cost"], (int, float))


# --------- PWA endpoints ---------

def test_manifest_json():
    r = requests.get(f"{BASE_URL}/manifest.json")
    assert r.status_code == 200
    m = r.json()
    assert m["short_name"] == "LotoStat.Pro"
    assert m["display"] == "standalone"
    assert m["theme_color"] == "#F59E0B"
    assert m["start_url"] == "/"
    assert m["name"]


def test_icon_svg():
    r = requests.get(f"{BASE_URL}/icon.svg")
    assert r.status_code == 200
    assert "image/svg+xml" in r.headers.get("content-type", "")


def test_index_html_has_manifest_and_icon_links():
    r = requests.get(f"{BASE_URL}/")
    assert r.status_code == 200
    html = r.text
    assert 'rel="manifest"' in html
    assert 'href="/manifest.json"' in html
    assert 'rel="icon"' in html and 'image/svg+xml' in html
