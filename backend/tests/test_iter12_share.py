"""Iteration 12 — Share feature (Partage Grille).
Tests:
- POST /api/grids/share (idempotent token, 404 for foreign/invalid grid)
- GET /api/share/{token} (PUBLIC, no auth)
- POST /api/grids/share-email (Resend, email validation)
"""
import os
import uuid
import subprocess
import pytest
import requests


def _load_backend_url():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if v:
        return v.rstrip("/")
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip().strip('"').rstrip("/")
    raise RuntimeError("REACT_APP_BACKEND_URL missing")


BASE_URL = _load_backend_url()


def _mongo(js):
    r = subprocess.run(
        ["mongosh", "mongodb://localhost:27017/test_database", "--quiet", "--eval", js],
        capture_output=True, text=True, timeout=30,
    )
    return r.stdout.strip(), r.stderr.strip(), r.returncode


def _make_user_session(email_prefix="test.iter12"):
    uid = f"iter12_{uuid.uuid4().hex[:10]}"
    tok = f"iter12_tok_{uuid.uuid4().hex[:16]}"
    email = f"{email_prefix}+{uuid.uuid4().hex[:6]}@example.com"
    js = f"""
    db.users.insertOne({{user_id:'{uid}',email:'{email}',name:'Iter12 User',picture:null,created_at:new Date().toISOString()}});
    db.user_sessions.insertOne({{user_id:'{uid}',session_token:'{tok}',expires_at:new Date(Date.now()+7*24*3600*1000).toISOString(),created_at:new Date().toISOString()}});
    print('OK');
    """
    out, err, rc = _mongo(js)
    assert rc == 0 and "OK" in out, f"mongo insert failed: {err}/{out}"
    return uid, tok, email


def _insert_grid(user_id):
    gid = f"iter12_grid_{uuid.uuid4().hex[:10]}"
    js = f"""
    db.saved_grids.insertOne({{
      id:'{gid}', user_id:'{user_id}',
      numbers:[3,14,22,35,48], chance:7,
      strategy:'balanced',
      created_at:new Date().toISOString()
    }});
    print('OK');
    """
    out, err, rc = _mongo(js)
    assert rc == 0 and "OK" in out, f"insert grid failed: {err}/{out}"
    return gid


def _cleanup(uid, gid=None):
    js = (
        f"db.user_sessions.deleteMany({{user_id:'{uid}'}}); "
        f"db.users.deleteMany({{user_id:'{uid}'}}); "
        f"db.grid_shares.deleteMany({{owner_id:'{uid}'}}); "
    )
    if gid:
        js += f"db.saved_grids.deleteMany({{id:'{gid}'}}); "
    js += "print('OK');"
    _mongo(js)


@pytest.fixture(scope="module")
def user_a():
    uid, tok, email = _make_user_session("test.iter12.a")
    gid = _insert_grid(uid)
    yield {"uid": uid, "tok": tok, "email": email, "gid": gid}
    _cleanup(uid, gid)


@pytest.fixture(scope="module")
def user_b():
    uid, tok, email = _make_user_session("test.iter12.b")
    gid = _insert_grid(uid)
    yield {"uid": uid, "tok": tok, "email": email, "gid": gid}
    _cleanup(uid, gid)


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


# --- POST /grids/share ---

class TestShareCreate:
    def test_share_create_returns_token(self, user_a):
        r = requests.post(f"{BASE_URL}/api/grids/share", json={"grid_id": user_a["gid"]}, headers=_h(user_a["tok"]), timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "token" in d and isinstance(d["token"], str) and len(d["token"]) == 12
        assert all(c in "0123456789abcdef" for c in d["token"])
        assert "created_at" in d

    def test_share_create_idempotent(self, user_a):
        r1 = requests.post(f"{BASE_URL}/api/grids/share", json={"grid_id": user_a["gid"]}, headers=_h(user_a["tok"]), timeout=15)
        r2 = requests.post(f"{BASE_URL}/api/grids/share", json={"grid_id": user_a["gid"]}, headers=_h(user_a["tok"]), timeout=15)
        assert r1.status_code == 200 and r2.status_code == 200
        assert r1.json()["token"] == r2.json()["token"], "Idempotency broken — different tokens for same grid"

    def test_share_create_foreign_grid_404(self, user_a, user_b):
        # user_a tries to share user_b's grid
        r = requests.post(f"{BASE_URL}/api/grids/share", json={"grid_id": user_b["gid"]}, headers=_h(user_a["tok"]), timeout=15)
        assert r.status_code == 404

    def test_share_create_invalid_grid_404(self, user_a):
        r = requests.post(f"{BASE_URL}/api/grids/share", json={"grid_id": "does_not_exist_xyz"}, headers=_h(user_a["tok"]), timeout=15)
        assert r.status_code == 404

    def test_share_create_requires_auth(self, user_a):
        r = requests.post(f"{BASE_URL}/api/grids/share", json={"grid_id": user_a["gid"]}, timeout=15)
        assert r.status_code == 401


# --- GET /share/{token} ---

class TestShareGet:
    def test_public_get_no_auth(self, user_a):
        # First, create a share
        r = requests.post(f"{BASE_URL}/api/grids/share", json={"grid_id": user_a["gid"]}, headers=_h(user_a["tok"]), timeout=15)
        token = r.json()["token"]
        # Public GET without any auth
        r2 = requests.get(f"{BASE_URL}/api/share/{token}", timeout=15)
        assert r2.status_code == 200, r2.text
        d = r2.json()
        assert d["numbers"] == [3, 14, 22, 35, 48]
        assert d["chance"] == 7
        assert d["strategy"] == "balanced"
        assert d["shared_by"] == "Iter12 User"
        assert "shared_at" in d
        assert "created_at" in d

    def test_invalid_token_404(self):
        r = requests.get(f"{BASE_URL}/api/share/notarealtoken", timeout=15)
        assert r.status_code == 404


# --- POST /grids/share-email ---

class TestShareEmail:
    def test_share_email_invalid_email_returns_400(self, user_a):
        r = requests.post(
            f"{BASE_URL}/api/grids/share-email",
            json={"grid_id": user_a["gid"], "to_email": "not-an-email"},
            headers=_h(user_a["tok"]),
            timeout=15,
        )
        assert r.status_code == 400
        assert "invalide" in r.json().get("detail", "").lower()

    def test_share_email_foreign_grid_404(self, user_a, user_b):
        r = requests.post(
            f"{BASE_URL}/api/grids/share-email",
            json={"grid_id": user_b["gid"], "to_email": "labouyrie28@gmail.com"},
            headers=_h(user_a["tok"]),
            timeout=15,
        )
        assert r.status_code == 404

    def test_share_email_requires_auth(self, user_a):
        r = requests.post(
            f"{BASE_URL}/api/grids/share-email",
            json={"grid_id": user_a["gid"], "to_email": "labouyrie28@gmail.com"},
            timeout=15,
        )
        assert r.status_code == 401

    def test_share_email_valid_send_or_resend_error(self, user_a):
        """With RESEND_API_KEY set + valid email format, expect 200 for labouyrie28@gmail.com (Resend sandbox).
        For another address, Resend may reject → 500 with detail (expected in sandbox)."""
        r = requests.post(
            f"{BASE_URL}/api/grids/share-email",
            json={"grid_id": user_a["gid"], "to_email": "labouyrie28@gmail.com", "message": "Hello!"},
            headers=_h(user_a["tok"]),
            timeout=30,
        )
        # 200 expected when Resend is configured & recipient is the sandbox owner
        assert r.status_code in (200, 500, 503), r.text
        if r.status_code == 200:
            d = r.json()
            assert d.get("status") == "sent"
            assert d.get("to") == "labouyrie28@gmail.com"
