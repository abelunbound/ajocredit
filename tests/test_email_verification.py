"""Email verification gate for creating or joining an Ajo (#115)."""

from __future__ import annotations

import hashlib
import logging
import os
import sys
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

os.environ.setdefault("JWT_SECRET_KEY", "test-only-jwt-secret-key-32chars!!")
os.environ["ALLOW_LOCAL_STUB_LOGIN"] = "false"
os.environ["SEED_DEMO_ACCOUNTS"] = "false"
os.environ.setdefault("AJO_ENV", "local")
os.environ.setdefault("EMAIL_SENDER", "dev")
os.environ.setdefault("AUDIT_EMAIL_HMAC_KEY", "test-only-audit-email-hmac-key")

if "backend.api" not in sys.modules:
    _configured_url = os.environ.get("DATABASE_URL", "")
    if not _configured_url.startswith("postgres"):
        _db_dir = tempfile.mkdtemp(prefix="ajo-verify-")
        os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(_db_dir) / "ajo.db")
    from alembic import command
    from alembic.config import Config

    command.upgrade(Config(str(Path(__file__).resolve().parents[1] / "alembic.ini")), "head")

import pytest
from fastapi.testclient import TestClient
from flask import Flask, session

import backend.api as api
import backend.audit_email as audit_email
import backend.auth as auth
import backend.database as database
import backend.email_verification as email_verification
import backend.mail as mail
from backend.clock import advance, freeze, reset
from frontend.pages.my_circles import my_circles_rows
from frontend.pages.verification_prompt import VERIFY_EMAIL_PROMPT, verify_email_banner
from tests.fixtures.seeded_circles import (
    load_seeded_circles,
    member_is_preverified,
    seeded_verified_at,
)

client = TestClient(api.app)
FROZEN = datetime(2026, 4, 1, 8, 0, tzinfo=timezone.utc)
PASSWORD = "correct-horse"


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("AJO_ENV", "local")
    monkeypatch.setenv("EMAIL_SENDER", "dev")
    reset()
    mail.clear_memory_inbox()
    yield
    reset()
    mail.clear_memory_inbox()


def _email() -> str:
    return f"verify-{uuid.uuid4().hex}@example.test"


def _signup(email: str):
    return client.post(
        "/api/v1/auth/signup",
        json={"name": "Ada Test", "email": email, "password": PASSWORD},
    )


def _login(email: str):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _link_token() -> str:
    body = mail.memory_inbox()[-1]["body"]
    assert "/verify-email#" in body
    return body.split("/verify-email#", 1)[1].split()[0].strip()


def test_signup_sends_a_hashed_single_use_link_and_blocks_circles_until_verified(caplog):
    freeze(FROZEN)
    email = _email()
    caplog.set_level(logging.DEBUG)
    created = _signup(email)
    assert created.status_code == 201, created.text
    assert created.json()["detail"] == auth.SIGNUP_DETAIL
    token = _link_token()
    assert token not in caplog.text
    assert f"/verify-email#{token}" not in caplog.text

    db = database.SessionLocal()
    try:
        stored = db.query(database.EmailVerificationToken).filter_by(token_hash=auth.hash_token(token)).one()
        assert stored.token_hash != token
        assert token not in stored.token_hash
        user = db.query(database.User).filter_by(email=email).one()
        assert user.email_verified_at is None
    finally:
        db.close()

    access = _login(email)
    me = client.get("/api/v1/me", headers=_auth(access))
    assert me.status_code == 200
    assert me.json()["email_verified"] is False
    blocked = client.post("/api/v1/circles", headers=_auth(access), json={"name": "Test Circle"})
    assert blocked.status_code == 403
    assert blocked.json()["detail"] == email_verification.VERIFY_REQUIRED
    assert client.post("/api/v1/circles/1/join", headers=_auth(access)).status_code == 403

    advance(timedelta(hours=24, seconds=1))
    expired = client.post("/api/v1/auth/verification/confirm", json={"token": token})
    assert expired.status_code == 400
    advance(timedelta(hours=-24))
    confirmed = client.post("/api/v1/auth/verification/confirm", json={"token": token})
    assert confirmed.status_code == 200, confirmed.text
    again = client.post("/api/v1/auth/verification/confirm", json={"token": token})
    assert again.status_code == 400

    access = _login(email)
    created_circle = client.post("/api/v1/circles", headers=_auth(access), json={"name": "Test Circle"})
    assert created_circle.status_code == 201, created_circle.text
    circle_id = created_circle.json()["circle_id"]

    other = _email()
    assert _signup(other).status_code == 201
    other_access = _login(other)
    assert client.post(f"/api/v1/circles/{circle_id}/join", headers=_auth(other_access)).status_code == 403
    other_token = _link_token()
    assert client.post("/api/v1/auth/verification/confirm", json={"token": other_token}).status_code == 200
    other_access = _login(other)
    joined = client.post(f"/api/v1/circles/{circle_id}/join", headers=_auth(other_access))
    assert joined.status_code == 200, joined.text

    db = database.SessionLocal()
    try:
        verified = db.query(database.User).filter_by(email=email).one()
        assert verified.email_verified_at is not None
        events = [row.action for row in db.query(database.AuthAuditEvent).all()]
        assert "email_verification_sent" in events
        assert "email_verified" in events
        plain = hashlib.sha256(email.encode("utf-8")).hexdigest()
        for row in db.query(database.AuthAuditEvent).filter_by(user_id=verified.id).all():
            blob = f"{row.action} {row.email_hash}"
            assert token not in blob
            assert PASSWORD not in blob
            assert row.email_hash != plain
            assert row.email_hash == audit_email.hash_audit_email(email)
    finally:
        db.close()


def test_verification_token_second_use_fails():
    email = _email()
    assert _signup(email).status_code == 201
    token = _link_token()
    first = client.post("/api/v1/auth/verification/confirm", json={"token": token})
    assert first.status_code == 200, first.text
    second = client.post("/api/v1/auth/verification/confirm", json={"token": token})
    assert second.status_code == 400
    assert second.json()["detail"] == email_verification.VERIFY_INVALID
    me = client.get("/api/v1/me", headers=_auth(_login(email)))
    assert me.json()["email_verified"] is True


def test_resend_hides_whether_the_email_is_registered_and_uses_the_hook(monkeypatch):
    email = _email()
    assert _signup(email).status_code == 201
    first = _link_token()
    seen = []

    def _hook(request, *, action, email):
        seen.append((action, email))

    monkeypatch.setattr(email_verification, "enforce_auth_attempt_policy", _hook)
    mail.clear_memory_inbox()
    known = client.post("/api/v1/auth/verification/resend", json={"email": f"  {email.upper()} "})
    unknown = client.post(
        "/api/v1/auth/verification/resend",
        json={"email": f"missing-{uuid.uuid4().hex}@example.test"},
    )
    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json() == {"detail": email_verification.RESEND_DETAIL}
    assert len(mail.memory_inbox()) == 1
    assert [item[0] for item in seen] == ["resend_verification", "resend_verification"]
    assert seen[0][1] == email
    replacement = _link_token()
    assert replacement != first
    assert client.post("/api/v1/auth/verification/confirm", json={"token": first}).status_code == 400
    assert client.post("/api/v1/auth/verification/confirm", json={"token": replacement}).status_code == 200


def test_signup_of_an_existing_email_does_not_send_a_verification_link():
    email = _email()
    assert _signup(email).status_code == 201
    mail.clear_memory_inbox()
    again = _signup(email)
    assert again.status_code == 201
    assert again.json()["detail"] == auth.SIGNUP_DETAIL
    assert mail.memory_inbox()
    assert "/verify-email#" not in mail.memory_inbox()[-1]["body"]


def test_verification_link_uses_public_app_url_and_ignores_the_host_header(monkeypatch):
    import inspect

    monkeypatch.delenv("PUBLIC_APP_URL", raising=False)
    assert email_verification.verification_link("abc") == "http://localhost:8055/verify-email#abc"
    source = inspect.getsource(email_verification.verification_link)
    assert "Host" not in source
    assert "headers" not in source
    assert "request" not in source

    monkeypatch.setenv("PUBLIC_APP_URL", "https://ajo.example.test/")
    email = _email()
    mail.clear_memory_inbox()
    response = client.post(
        "/api/v1/auth/signup",
        json={"name": "Ada Test", "email": email, "password": PASSWORD},
        headers={"Host": "evil.example", "X-Forwarded-Host": "evil.example"},
    )
    assert response.status_code == 201, response.text
    body = mail.memory_inbox()[-1]["body"]
    assert "https://ajo.example.test/verify-email#" in body
    assert "evil.example" not in body
    assert "testserver" not in body


def test_email_endpoints_fail_closed_when_ajo_env_is_unset(monkeypatch):
    monkeypatch.setenv("AJO_ENV", "")
    monkeypatch.delenv("EMAIL_SENDER", raising=False)
    email = _email()
    signup = _signup(email)
    resend = client.post("/api/v1/auth/verification/resend", json={"email": email})
    assert signup.status_code == 503
    assert resend.status_code == 503
    assert signup.json() == resend.json()
    assert mail.memory_inbox() == []


def test_unverified_ui_shows_the_prompt_and_seeded_users_can_be_preverified():
    assert verify_email_banner(True) is None
    banner = verify_email_banner(False)
    assert VERIFY_EMAIL_PROMPT in str(banner)
    rows = my_circles_rows(email_verified=False)
    assert VERIFY_EMAIL_PROMPT in str(rows[0])
    assert VERIFY_EMAIL_PROMPT not in str(my_circles_rows(email_verified=True))

    flask_app = Flask(__name__)
    flask_app.secret_key = "test-only"
    from frontend.pages.join import layout

    with flask_app.test_request_context():
        session["role"] = "member"
        session["email_verified"] = False
        assert VERIFY_EMAIL_PROMPT in str(layout("member"))
        session["email_verified"] = True
        assert VERIFY_EMAIL_PROMPT not in str(layout("member"))

    document = load_seeded_circles()
    member = document["circles"][0]["members"][0]
    assert member_is_preverified(member) is True
    when = FROZEN
    assert seeded_verified_at(member, when) == when
    unverified = dict(member)
    unverified["email_verified"] = False
    assert member_is_preverified(unverified) is False
    assert seeded_verified_at(unverified, when) is None
