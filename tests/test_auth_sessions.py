"""Real sign-up and sign-in (#33).

Covers normalised emails, identical login failures, short-lived access tokens,
hashed rotating refresh tokens, logout, and the #40 rate-limit hook.
"""

from __future__ import annotations

import logging
import os
import sys
import tempfile
import time
import uuid
from datetime import timedelta
from pathlib import Path

os.environ.setdefault("JWT_SECRET_KEY", "test-only-jwt-secret-key-32chars!!")
os.environ["ALLOW_LOCAL_STUB_LOGIN"] = "false"
os.environ["SEED_DEMO_ACCOUNTS"] = "false"

if "api" not in sys.modules:
    _configured_url = os.environ.get("DATABASE_URL", "")
    if not _configured_url.startswith("postgres"):
        _db_dir = tempfile.mkdtemp(prefix="ajo-auth-")
        os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(_db_dir) / "ajo.db")
    from alembic import command
    from alembic.config import Config

    command.upgrade(Config(str(Path(__file__).resolve().parents[1] / "alembic.ini")), "head")

import bcrypt
import jwt
import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient

import api
import auth
import database
from clock import advance, freeze, reset

client = TestClient(api.app)
FROZEN = __import__("datetime").datetime(2026, 1, 15, 9, 30, tzinfo=__import__("datetime").timezone.utc)
PASSWORD = "correct-horse"


@pytest.fixture(autouse=True)
def _reset_clock():
    reset()
    yield
    reset()


def _email() -> str:
    return f"user-{uuid.uuid4().hex}@example.test"


def _signup(email: str, password: str = PASSWORD, name: str = "Ada Test"):
    return client.post(
        "/api/v1/auth/signup",
        json={"name": name, "email": email, "password": password},
    )


def _login(email: str, password: str = PASSWORD):
    return client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )


def test_migration_head_is_auth_sessions_only():
    script = ScriptDirectory.from_config(Config(str(Path(__file__).resolve().parents[1] / "alembic.ini")))
    assert script.get_heads() == ["0004_password_reset"]


def test_email_is_trimmed_and_lowercased_before_uniqueness_and_login():
    raw = f"  Ada-{uuid.uuid4().hex[:8]}@Example.TEST "
    created = _signup(raw)
    assert created.status_code == 201, created.text
    normalised = raw.strip().lower()

    db = database.SessionLocal()
    try:
        stored = db.query(database.User).filter(database.User.email == normalised).one()
        assert stored.email == normalised
        assert db.query(database.User).filter(database.User.email == raw).count() == 0
    finally:
        db.close()

    again = _signup(normalised)
    assert again.status_code == created.status_code
    assert again.json() == created.json()
    assert normalised not in again.text

    logged_in = _login(f"  {normalised.upper()}  ")
    assert logged_in.status_code == 200, logged_in.text

    db = database.SessionLocal()
    try:
        assert db.query(database.User).filter(database.User.email == normalised).count() == 1
    finally:
        db.close()


def test_signup_of_an_existing_email_does_not_change_the_password(monkeypatch):
    email = _email()
    assert _signup(email, password=PASSWORD).status_code == 201
    hashes = []
    real_hash = auth.hash_password

    def _counting(password: str) -> str:
        hashes.append(password)
        return real_hash(password)

    monkeypatch.setattr(auth, "hash_password", _counting)
    second = _signup(email, password="another-password")
    assert second.status_code == 201
    assert hashes == ["another-password"]
    assert _login(email, PASSWORD).status_code == 200
    assert _login(email, "another-password").status_code == 401


def test_unknown_email_and_wrong_password_match_and_both_run_bcrypt(monkeypatch):
    email = _email()
    assert _signup(email).status_code == 201
    auth.dummy_password_hash()

    seen: list[bytes] = []
    real_check = bcrypt.checkpw

    def _spy(password: bytes, hashed: bytes) -> bool:
        seen.append(hashed)
        return real_check(password, hashed)

    monkeypatch.setattr(auth.bcrypt, "checkpw", _spy)

    unknown = _login(f"missing-{uuid.uuid4().hex}@example.test", PASSWORD)
    wrong = _login(email, "not-the-password")
    assert unknown.status_code == 401
    assert wrong.status_code == 401
    assert unknown.json() == wrong.json() == {"detail": auth.LOGIN_FAILED}
    assert seen[0] == auth.dummy_password_hash()

    db = database.SessionLocal()
    try:
        stored = db.query(database.User).filter(database.User.email == email).one()
    finally:
        db.close()
    assert seen[1] == stored.hashed_password.encode("utf-8")

    auth.dummy_password_hash()
    unknown_started = time.perf_counter()
    unknown_again = _login(f"missing-{uuid.uuid4().hex}@example.test", PASSWORD)
    unknown_elapsed = time.perf_counter() - unknown_started
    wrong_started = time.perf_counter()
    wrong_again = _login(email, "still-wrong-pass")
    wrong_elapsed = time.perf_counter() - wrong_started
    assert unknown_again.json() == wrong_again.json()
    assert unknown_elapsed > 0.05
    assert wrong_elapsed > 0.05
    assert max(unknown_elapsed, wrong_elapsed) / min(unknown_elapsed, wrong_elapsed) < 4


def test_access_token_follows_the_clock_and_refresh_is_stored_hashed():
    freeze(FROZEN)
    email = _email()
    assert _signup(email).status_code == 201
    logged_in = _login(email)
    assert logged_in.status_code == 200, logged_in.text
    body = logged_in.json()
    access = body["access_token"]
    refresh = body["refresh_token"]
    assert body["expires_in"] == auth.access_token_minutes() * 60

    payload = jwt.decode(
        access,
        api.JWT_SECRET_KEY,
        algorithms=[api.JWT_ALGORITHM],
        options={"verify_exp": False},
    )
    expected = int((FROZEN + timedelta(minutes=auth.access_token_minutes())).timestamp())
    assert payload["exp"] == expected
    assert payload["typ"] == "access"
    me = client.get("/api/v1/me", headers={"Authorization": f"Bearer {access}"})
    assert me.status_code == 200

    db = database.SessionLocal()
    try:
        row = db.query(database.RefreshToken).filter_by(token_hash=auth.hash_token(refresh)).one()
        assert row.token_hash != refresh
        assert refresh not in row.token_hash
        assert len(row.token_hash) == 64
    finally:
        db.close()

    advance(timedelta(minutes=auth.access_token_minutes()) + auth.ACCESS_CLOCK_LEEWAY + timedelta(seconds=1))
    expired = client.get("/api/v1/me", headers={"Authorization": f"Bearer {access}"})
    assert expired.status_code == 401

    refreshed = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert refreshed.status_code == 200, refreshed.text
    new_access = refreshed.json()["access_token"]
    new_refresh = refreshed.json()["refresh_token"]
    assert new_refresh != refresh
    assert client.get("/api/v1/me", headers={"Authorization": f"Bearer {new_access}"}).status_code == 200

    reused = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert reused.status_code == 401
    assert reused.json()["detail"] == auth.REFRESH_FAILED
    assert client.get("/api/v1/me", headers={"Authorization": f"Bearer {new_access}"}).status_code == 401
    killed = client.post("/api/v1/auth/refresh", json={"refresh_token": new_refresh})
    assert killed.status_code == 401

    db = database.SessionLocal()
    try:
        assert db.query(database.RefreshToken).filter(database.RefreshToken.token_hash == refresh).count() == 0
        stored = db.query(database.RefreshToken).all()
        assert all(row.token_hash != refresh for row in stored)
        assert all(row.token_hash != new_refresh for row in stored)
    finally:
        db.close()


def test_logout_revokes_only_that_session():
    email = _email()
    assert _signup(email).status_code == 201
    first = _login(email).json()
    second = _login(email).json()
    headers = {"Authorization": f"Bearer {first['access_token']}"}
    other_headers = {"Authorization": f"Bearer {second['access_token']}"}

    listed = client.get("/api/v1/auth/sessions", headers=headers)
    assert listed.status_code == 200, listed.text
    sessions = listed.json()["sessions"]
    assert len(sessions) == 2
    assert sum(1 for item in sessions if item["current"]) == 1
    current_id = next(item["id"] for item in sessions if item["current"])
    other_id = next(item["id"] for item in sessions if not item["current"])

    logged_out = client.post("/api/v1/auth/logout", headers=headers)
    assert logged_out.status_code == 204
    assert client.get("/api/v1/me", headers=headers).status_code == 401
    assert client.post(
        "/api/v1/auth/refresh", json={"refresh_token": first["refresh_token"]}
    ).status_code == 401
    assert client.get("/api/v1/me", headers=other_headers).status_code == 200

    removed = client.delete(f"/api/v1/auth/sessions/{current_id}", headers=other_headers)
    assert removed.status_code == 204
    assert client.get("/api/v1/me", headers=other_headers).status_code == 200
    missing = client.delete("/api/v1/auth/sessions/999999", headers=other_headers)
    assert missing.status_code == 404
    closed = client.delete(f"/api/v1/auth/sessions/{other_id}", headers=other_headers)
    assert closed.status_code == 204
    assert client.get("/api/v1/me", headers=other_headers).status_code == 401


def test_logout_accepts_an_expired_access_token():
    freeze(FROZEN)
    email = _email()
    assert _signup(email).status_code == 201
    logged_in = _login(email).json()
    headers = {"Authorization": f"Bearer {logged_in['access_token']}"}
    advance(timedelta(minutes=auth.access_token_minutes()) + auth.ACCESS_CLOCK_LEEWAY + timedelta(seconds=1))
    assert client.get("/api/v1/me", headers=headers).status_code == 401
    assert client.post("/api/v1/auth/logout", headers=headers).status_code == 204
    assert client.post(
        "/api/v1/auth/refresh", json={"refresh_token": logged_in["refresh_token"]}
    ).status_code == 401


def test_moved_clock_accepts_a_new_access_token_and_expires_the_old_one():
    """iat and exp follow clock.now(), not the wall clock PyJWT would use."""
    freeze(FROZEN)
    email = _email()
    assert _signup(email).status_code == 201
    old = _login(email).json()["access_token"]
    assert client.get("/api/v1/me", headers={"Authorization": f"Bearer {old}"}).status_code == 200

    advance(timedelta(seconds=60))
    after_minute = _login(email).json()["access_token"]
    assert client.get("/api/v1/me", headers={"Authorization": f"Bearer {after_minute}"}).status_code == 200
    assert client.get("/api/v1/me", headers={"Authorization": f"Bearer {old}"}).status_code == 200

    advance(timedelta(days=3))
    assert client.get("/api/v1/me", headers={"Authorization": f"Bearer {old}"}).status_code == 401
    assert client.get("/api/v1/me", headers={"Authorization": f"Bearer {after_minute}"}).status_code == 401
    fresh = _login(email).json()["access_token"]
    assert client.get("/api/v1/me", headers={"Authorization": f"Bearer {fresh}"}).status_code == 200

    moment = __import__("clock").now()
    future = jwt.encode(
        {
            "sub": "1",
            "sid": "1",
            "typ": "access",
            "iat": int((moment + timedelta(hours=1)).timestamp()),
            "exp": int((moment + timedelta(hours=2)).timestamp()),
        },
        api.JWT_SECRET_KEY,
        algorithm="HS256",
    )
    not_yet = jwt.encode(
        {
            "sub": "1",
            "sid": "1",
            "typ": "access",
            "iat": int(moment.timestamp()),
            "nbf": int((moment + timedelta(hours=1)).timestamp()),
            "exp": int((moment + timedelta(hours=2)).timestamp()),
        },
        api.JWT_SECRET_KEY,
        algorithm="HS256",
    )
    assert client.get("/api/v1/me", headers={"Authorization": f"Bearer {future}"}).status_code == 401
    assert client.get("/api/v1/me", headers={"Authorization": f"Bearer {not_yet}"}).status_code == 401


def test_refresh_token_second_use_fails():
    """The presented refresh token is consumed by one update, so reuse fails."""
    email = _email()
    assert _signup(email).status_code == 201
    refresh = _login(email).json()["refresh_token"]
    first = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert first.status_code == 200, first.text
    second = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert second.status_code == 401
    assert second.json()["detail"] == auth.REFRESH_FAILED
    db = database.SessionLocal()
    try:
        stored = db.query(database.RefreshToken).filter_by(token_hash=auth.hash_token(refresh)).one()
        assert stored.revoked_at is not None
    finally:
        db.close()
    assert client.post(
        "/api/v1/auth/refresh", json={"refresh_token": first.json()["refresh_token"]}
    ).status_code == 401


def test_refresh_expires_after_its_lifetime():
    freeze(FROZEN)
    email = _email()
    assert _signup(email).status_code == 201
    refresh = _login(email).json()["refresh_token"]
    advance(timedelta(days=auth.refresh_token_days(), seconds=1))
    refused = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert refused.status_code == 401
    assert refused.json()["detail"] == auth.REFRESH_FAILED


def test_long_lived_access_token_settings_are_ignored(monkeypatch):
    monkeypatch.setenv("ACCESS_TOKEN_MINUTES", "43200")
    monkeypatch.setenv("JWT_EXPIRY_DAYS", "30")
    assert auth.access_token_minutes() == auth.ACCESS_TOKEN_MINUTES
    freeze(FROZEN)
    token = api.create_access_token(4, 8)
    payload = jwt.decode(token, api.JWT_SECRET_KEY, algorithms=["HS256"], options={"verify_exp": False})
    assert payload["exp"] - payload["iat"] == auth.ACCESS_TOKEN_MINUTES * 60


def test_signup_and_login_call_the_rate_limit_hook(monkeypatch):
    seen = []

    def _hook(request, *, action, email):
        host = request.client.host if request.client is not None else None
        seen.append((action, email, host))

    monkeypatch.setattr(auth, "enforce_auth_attempt_policy", _hook)
    email = f"  Hook-{uuid.uuid4().hex[:6]}@Example.TEST "
    assert _signup(email, password="short").status_code == 422
    assert _signup(email).status_code == 201
    assert _login(email, "not-the-password").status_code == 401
    assert [item[0] for item in seen] == ["signup", "signup", "login"]
    assert seen[0][1] == email.strip().lower()
    assert seen[2][1] == email.strip().lower()
    assert seen[0][2]


def test_validation_errors_do_not_echo_the_password():
    response = client.post(
        "/api/v1/auth/signup",
        json={"name": "Ada", "email": "ada@example.test", "password": ["super-secret-password"]},
    )
    assert response.status_code == 422
    assert "super-secret-password" not in response.text


def test_auth_paths_do_not_log_passwords_or_tokens(caplog):
    email = _email()
    caplog.set_level(logging.DEBUG)
    assert _signup(email).status_code == 201
    logged_in = _login(email)
    assert logged_in.status_code == 200
    refresh = logged_in.json()["refresh_token"]
    access = logged_in.json()["access_token"]
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": refresh}).status_code == 200
    text = caplog.text
    assert PASSWORD not in text
    assert refresh not in text
    assert access not in text
