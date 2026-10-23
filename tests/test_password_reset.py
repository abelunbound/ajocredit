"""Password reset by email link (#114)."""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import stat
import subprocess
import sys
import tempfile
import uuid
from datetime import timedelta
from pathlib import Path

os.environ.setdefault("JWT_SECRET_KEY", "test-only-jwt-secret-key-32chars!!")
os.environ["ALLOW_LOCAL_STUB_LOGIN"] = "false"
os.environ["SEED_DEMO_ACCOUNTS"] = "false"
os.environ["AJO_ENV"] = "local"
os.environ["EMAIL_SENDER"] = "dev"
os.environ["AUDIT_EMAIL_HMAC_KEY"] = "test-only-audit-email-hmac-key"

if "backend.api" not in sys.modules:
    _configured_url = os.environ.get("DATABASE_URL", "")
    if not _configured_url.startswith("postgres"):
        _db_dir = tempfile.mkdtemp(prefix="ajo-reset-")
        os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(_db_dir) / "ajo.db")
    from alembic import command
    from alembic.config import Config

    command.upgrade(Config(str(Path(__file__).resolve().parents[1] / "alembic.ini")), "head")

import pytest
from fastapi.testclient import TestClient

import backend.api as api
import backend.audit_email as audit_email
import backend.auth as auth
import backend.database as database
import backend.mail as mail
import backend.password_reset as password_reset
from backend.clock import advance, freeze, reset

client = TestClient(api.app)
FROZEN = __import__("datetime").datetime(2026, 3, 1, 12, 0, tzinfo=__import__("datetime").timezone.utc)
PASSWORD = "correct-horse"
NEW_PASSWORD = "new-password-1"


@pytest.fixture(autouse=True)
def _clock_and_inbox(monkeypatch):
    monkeypatch.setenv("AJO_ENV", "local")
    monkeypatch.setenv("EMAIL_SENDER", "dev")
    monkeypatch.delenv("AJO_EMAIL_INBOX", raising=False)
    reset()
    mail.clear_memory_inbox()
    yield
    reset()
    mail.clear_memory_inbox()


def _email() -> str:
    return f"reset-{uuid.uuid4().hex}@example.test"


def _signup(email: str) -> None:
    response = client.post(
        "/api/v1/auth/signup",
        json={"name": "Ada Test", "email": email, "password": PASSWORD},
    )
    assert response.status_code == 201, response.text


def _forgot(email: str):
    return client.post("/api/v1/auth/password/forgot", json={"email": email})


def _token_from_inbox() -> str:
    messages = mail.memory_inbox()
    assert messages
    body = messages[-1]["body"]
    assert "/reset-password#token=" in body
    return password_reset.token_from_link_body(body)


def test_forgot_password_response_ignores_whether_the_email_exists():
    email = _email()
    _signup(email)
    mail.clear_memory_inbox()
    known = _forgot(f"  {email.upper()}  ")
    unknown = _forgot(f"missing-{uuid.uuid4().hex}@example.test")
    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json() == {"detail": password_reset.FORGOT_DETAIL}
    assert len(mail.memory_inbox()) == 1
    assert mail.memory_inbox()[0]["to"] == email


def test_reset_link_is_single_use_hashed_and_expires_after_thirty_minutes():
    freeze(FROZEN)
    email = _email()
    _signup(email)
    mail.clear_memory_inbox()
    assert _forgot(email).status_code == 200
    first = _forgot(email)
    assert first.status_code == 200
    token = _token_from_inbox()
    older = password_reset.token_from_link_body(mail.memory_inbox()[0]["body"])

    db = database.SessionLocal()
    try:
        rows = db.query(database.PasswordResetToken).all()
        assert rows
        assert all(row.token_hash != token for row in rows)
        assert all(token not in (row.token_hash or "") for row in rows)
        assert db.query(database.PasswordResetToken).filter_by(token_hash=auth.hash_token(token)).count() == 1
    finally:
        db.close()

    advance(timedelta(minutes=30, seconds=1))
    expired = client.post(
        "/api/v1/auth/password/reset",
        json={"token": token, "password": NEW_PASSWORD},
    )
    assert expired.status_code == 400
    assert expired.json()["detail"] == password_reset.RESET_INVALID

    advance(timedelta(minutes=-30))
    changed = client.post(
        "/api/v1/auth/password/reset",
        json={"token": token, "password": NEW_PASSWORD},
    )
    assert changed.status_code == 200, changed.text
    again = client.post(
        "/api/v1/auth/password/reset",
        json={"token": token, "password": "another-password"},
    )
    assert again.status_code == 400
    other = client.post(
        "/api/v1/auth/password/reset",
        json={"token": older, "password": "another-password"},
    )
    assert other.status_code == 400
    assert client.post(
        "/api/v1/auth/login", json={"email": email, "password": NEW_PASSWORD}
    ).status_code == 200
    assert client.post(
        "/api/v1/auth/login", json={"email": email, "password": PASSWORD}
    ).status_code == 401


def test_reset_ends_sessions_and_writes_an_audit_row_without_secrets(caplog):
    email = _email()
    _signup(email)
    first = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD}).json()
    second = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD}).json()
    mail.clear_memory_inbox()
    caplog.set_level(logging.DEBUG)
    assert _forgot(email).status_code == 200
    token = _token_from_inbox()
    link = password_reset.reset_link(token)
    reset = client.post(
        "/api/v1/auth/password/reset",
        json={"token": token, "password": NEW_PASSWORD},
    )
    assert reset.status_code == 200, reset.text
    assert token not in caplog.text
    assert link not in caplog.text
    assert NEW_PASSWORD not in caplog.text

    assert client.get(
        "/api/v1/me", headers={"Authorization": f"Bearer {first['access_token']}"}
    ).status_code == 401
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": first["refresh_token"]}).status_code == 401
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": second["refresh_token"]}).status_code == 401

    db = database.SessionLocal()
    try:
        user = db.query(database.User).filter_by(email=email).one()
        events = db.query(database.AuthAuditEvent).filter_by(user_id=user.id).all()
        actions = [event.action for event in events]
        assert "password_reset_requested" in actions
        assert "password_reset_completed" in actions
        plain = hashlib.sha256(email.encode("utf-8")).hexdigest()
        for event in events:
            blob = " ".join(
                str(part)
                for part in (event.action, event.email_hash, event.ip, event.user_id)
            )
            assert token not in blob
            assert NEW_PASSWORD not in blob
            assert PASSWORD not in blob
            assert link not in blob
            assert event.email_hash != plain
            assert event.email_hash == audit_email.hash_audit_email(email)
    finally:
        db.close()


def test_forgot_password_uses_the_rate_limit_hook(monkeypatch):
    seen = []

    def _hook(request, *, action, email):
        seen.append((action, email))

    monkeypatch.setattr(password_reset, "enforce_auth_attempt_policy", _hook)
    email = f"  Hook-{uuid.uuid4().hex[:6]}@Example.TEST "
    assert _forgot(email).status_code == 200
    assert seen == [("password_reset", email.strip().lower())]


def test_dev_sender_fails_closed_when_the_environment_is_not_local(monkeypatch, tmp_path):
    email = _email()
    _signup(email)
    monkeypatch.setenv("AJO_ENV", "")
    monkeypatch.setenv("AJO_EMAIL_INBOX", str(tmp_path))
    monkeypatch.delenv("EMAIL_SENDER", raising=False)
    mail.clear_memory_inbox()
    response = _forgot(email)
    assert response.status_code == 503
    assert response.json()["detail"] == password_reset.EMAIL_UNAVAILABLE
    missing = _forgot(f"missing-{uuid.uuid4().hex}@example.test")
    assert missing.status_code == 503
    assert missing.json() == response.json()
    assert mail.memory_inbox() == []
    assert list(tmp_path.iterdir()) == []

    monkeypatch.setenv("AJO_ENV", "local")
    monkeypatch.setenv("EMAIL_SENDER", "dev")
    assert _forgot(email).status_code == 200
    written = list(tmp_path.glob("*.json"))
    assert len(written) == 1
    text = written[0].read_text(encoding="utf-8")
    assert "/reset-password#" in text
    assert text.count("token") >= 0


def test_dev_sender_refuses_to_start_outside_local_or_dev():
    env = os.environ.copy()
    for name in ("AJO_ENV", "EMAIL_SENDER", "PYTEST_CURRENT_TEST", "ALLOW_TEST_CLOCK"):
        env.pop(name, None)
    env.update(
        {
            "JWT_SECRET_KEY": "b" * 32,
            "DATABASE_URL": "sqlite:///:memory:",
            "ALLOW_LOCAL_STUB_LOGIN": "false",
            "SEED_DEMO_ACCOUNTS": "false",
            "EMAIL_SENDER": "dev",
            "AJO_ENV": "production",
        }
    )
    refused = subprocess.run(
        [sys.executable, "-c", "import backend.api"],
        env=env,
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).resolve().parents[1]),
    )
    assert refused.returncode == 1
    assert "dev email sender" in refused.stderr
    assert "Refusing to start" in refused.stderr

    env["AJO_ENV"] = ""
    unset = subprocess.run(
        [sys.executable, "-c", "import backend.api"],
        env=env,
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).resolve().parents[1]),
    )
    assert unset.returncode == 1
    assert "(unset)" in unset.stderr

    env["AJO_ENV"] = "local"
    allowed = subprocess.run(
        [sys.executable, "-c", "import backend.api"],
        env=env,
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).resolve().parents[1]),
    )
    assert allowed.returncode == 0, allowed.stderr


def test_reset_token_second_use_fails():
    email = _email()
    _signup(email)
    mail.clear_memory_inbox()
    assert _forgot(email).status_code == 200
    token = _token_from_inbox()
    first = client.post(
        "/api/v1/auth/password/reset",
        json={"token": token, "password": NEW_PASSWORD},
    )
    assert first.status_code == 200, first.text
    second = client.post(
        "/api/v1/auth/password/reset",
        json={"token": token, "password": "second-password"},
    )
    assert second.status_code == 400
    assert second.json()["detail"] == password_reset.RESET_INVALID
    assert client.post(
        "/api/v1/auth/login", json={"email": email, "password": NEW_PASSWORD}
    ).status_code == 200
    assert client.post(
        "/api/v1/auth/login", json={"email": email, "password": "second-password"}
    ).status_code == 401


def test_audit_email_hash_is_hmac_not_sha256():
    email = _email()
    digest = audit_email.hash_audit_email(email)
    plain = hashlib.sha256(email.encode("utf-8")).hexdigest()
    expected = hmac.new(
        os.environ["AUDIT_EMAIL_HMAC_KEY"].encode("utf-8"),
        email.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    assert digest == expected
    assert digest != plain
    assert len(digest) == 64


def test_local_audit_key_file_is_created_and_gitignored(tmp_path, monkeypatch):
    key_file = tmp_path / "audit-email-hmac.key"
    monkeypatch.delenv("AUDIT_EMAIL_HMAC_KEY", raising=False)
    source = {"AJO_ENV": "local", "AUDIT_EMAIL_HMAC_KEY_FILE": str(key_file)}
    first = audit_email.audit_email_key(source)
    second = audit_email.audit_email_key(source)
    assert first == second
    assert key_file.read_text(encoding="utf-8").strip().encode("utf-8") == first
    assert stat.S_IMODE(key_file.stat().st_mode) == 0o600
    ignored = subprocess.run(
        ["git", "check-ignore", "-q", "local/audit-email-hmac.key"],
        cwd=str(Path(__file__).resolve().parents[1]),
    )
    assert ignored.returncode == 0


def test_dash_copy_matches_the_api_forgot_message():
    from frontend.pages.password_flow import NEUTRAL_FORGOT

    assert NEUTRAL_FORGOT == password_reset.FORGOT_DETAIL


def test_reset_link_uses_public_app_url_and_ignores_the_host_header(monkeypatch):
    import inspect

    monkeypatch.delenv("PUBLIC_APP_URL", raising=False)
    assert password_reset.public_app_origin() == "http://localhost:8055"
    assert password_reset.reset_link("abc") == "http://localhost:8055/reset-password#token=abc"
    source = inspect.getsource(password_reset.reset_link)
    assert "request" not in source
    assert "Host" not in source
    assert "headers" not in source

    monkeypatch.setenv("PUBLIC_APP_URL", "https://ajo.example.test/")
    email = _email()
    _signup(email)
    mail.clear_memory_inbox()
    response = client.post(
        "/api/v1/auth/password/forgot",
        json={"email": email},
        headers={"Host": "evil.example", "X-Forwarded-Host": "evil.example"},
    )
    assert response.status_code == 200, response.text
    body = mail.memory_inbox()[-1]["body"]
    assert "https://ajo.example.test/reset-password#token=" in body
    assert "evil.example" not in body
    assert "testserver" not in body
    token = password_reset.token_from_link_body(body)
    assert token
    assert f"#token={token}" in body


def test_audit_key_is_required_outside_local_or_dev():
    for env_name in ("", "production", "staging"):
        with pytest.raises(audit_email.AuditKeyError):
            audit_email.hash_audit_email(
                "ada@example.test",
                {"AJO_ENV": env_name},
            )
