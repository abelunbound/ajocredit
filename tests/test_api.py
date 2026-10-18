"""API tests for health and auth.

SQLite is the default. When DATABASE_URL already points at Postgres (the CI
job), these tests keep that URL, migrate it, and hit the same endpoints.
"""

from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path

os.environ["JWT_SECRET_KEY"] = "test-only-jwt-secret-key-32chars!!"
os.environ["ALLOW_LOCAL_STUB_LOGIN"] = "false"
os.environ["SEED_DEMO_ACCOUNTS"] = "false"

_configured_url = os.environ.get("DATABASE_URL", "")
USING_POSTGRES = _configured_url.startswith("postgres")
if not USING_POSTGRES:
    _db_dir = tempfile.mkdtemp(prefix="ajo-api-")
    os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(_db_dir) / "ajo.db")

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

_config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
command.upgrade(_config, "head")

import api
import database

client = TestClient(api.app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_sqlite_foreign_keys_or_postgres():
    with database.engine.connect() as connection:
        if database.engine.dialect.name == "sqlite":
            assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
        else:
            assert database.engine.dialect.name == "postgresql"
            assert connection.exec_driver_sql("SELECT 1").scalar() == 1


def _signup(email: str | None = None, password: str = "correct-horse"):
    payload = {
        "name": "Ada Test",
        "email": email or f"user-{uuid.uuid4().hex}@example.com",
        "password": password,
    }
    return payload["email"], client.post("/api/v1/auth/signup", json=payload)


def test_signup_stores_a_hash_and_login_returns_a_session():
    email, response = _signup()
    assert response.status_code == 201, response.text
    assert response.json() == {"detail": "If this email can be registered, the account is ready. Sign in to continue."}
    assert email not in response.text
    assert "token" not in response.text

    logged_in = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "correct-horse"},
    )
    assert logged_in.status_code == 200, logged_in.text
    body = logged_in.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["token_type"] == "bearer"
    assert "password" not in body

    me = client.get(
        "/api/v1/me",
        headers={"Authorization": f"Bearer {body['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["email"] == email
    assert me.json()["name"] == "Ada Test"

    db = database.SessionLocal()
    try:
        stored = db.query(database.User).filter(database.User.email == email).one()
        assert stored.hashed_password != "correct-horse"
        assert stored.hashed_password.startswith("$2")
    finally:
        db.close()


def test_signup_does_not_reveal_a_duplicate_email():
    email, first = _signup()
    assert first.status_code == 201, first.text
    _, second = _signup(email=email)
    assert second.status_code == first.status_code
    assert second.json() == first.json()
    db = database.SessionLocal()
    try:
        assert db.query(database.User).filter(database.User.email == email).count() == 1
    finally:
        db.close()


def test_signup_rejects_a_short_password():
    _, response = _signup(password="short")
    assert response.status_code == 422


def test_signup_rejects_a_password_over_72_bytes():
    _, response = _signup(password="a" * 73)
    assert response.status_code == 422


def test_me_rejects_a_missing_token():
    response = client.get("/api/v1/me")
    assert response.status_code == 401


def test_me_rejects_an_invalid_token():
    response = client.get(
        "/api/v1/me",
        headers={"Authorization": "Bearer not-a-jwt"},
    )
    assert response.status_code == 401
