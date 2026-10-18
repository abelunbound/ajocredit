"""Sign-in rate limits and account lockout (#40).

Per-IP and per-account windows, progressive lockout, and the same 429 for a
known address and an unknown one. Time comes from clock.now().
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
os.environ.setdefault("AJO_ENV", "local")
os.environ.setdefault("EMAIL_SENDER", "dev")
os.environ.setdefault("AUDIT_EMAIL_HMAC_KEY", "test-only-audit-email-hmac-key")

if "api" not in sys.modules:
    _configured_url = os.environ.get("DATABASE_URL", "")
    if not _configured_url.startswith("postgres"):
        _db_dir = tempfile.mkdtemp(prefix="ajo-rate-")
        os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(_db_dir) / "ajo.db")
    from alembic import command
    from alembic.config import Config

    command.upgrade(Config(str(Path(__file__).resolve().parents[1] / "alembic.ini")), "head")

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect

import api
import audit_email
import auth
import database
import mail
from clock import advance, freeze, reset

client = TestClient(api.app)
PASSWORD = "correct-horse"
FROZEN = __import__("datetime").datetime(2026, 6, 1, 12, 0, tzinfo=__import__("datetime").timezone.utc)
_ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"


@pytest.fixture(autouse=True)
def _clock_and_inbox():
    reset()
    mail.clear_memory_inbox()
    yield
    reset()
    mail.clear_memory_inbox()


def _email() -> str:
    return f"limit-{uuid.uuid4().hex}@example.test"


def _signup(email: str, http: TestClient | None = None) -> None:
    response = (http or client).post(
        "/api/v1/auth/signup",
        json={"name": "Ada Test", "email": email, "password": PASSWORD},
    )
    assert response.status_code == 201, response.text


def _login(email: str, password: str = PASSWORD, http: TestClient | None = None, headers: dict | None = None):
    return (http or client).post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
        headers=headers,
    )


def _from(host: str) -> TestClient:
    return TestClient(api.app, client=(host, 50000))


def _fast_wrong_password(monkeypatch):
    real = auth.password_matches

    def _check(password: str, hashed: str | bytes) -> bool:
        if password != PASSWORD:
            return False
        return real(password, hashed)

    monkeypatch.setattr(auth, "password_matches", _check)


def test_migration_head_is_single_and_rate_tables_roundtrip(tmp_path, monkeypatch):
    script = ScriptDirectory.from_config(Config(str(_ALEMBIC_INI)))
    assert script.get_heads() == ["0007_auth_rate_limits"]

    url = "sqlite:///" + str(tmp_path / "rate-limits.db")
    monkeypatch.setenv("DATABASE_URL", url)
    cfg = Config(str(_ALEMBIC_INI))
    command.upgrade(cfg, "head")
    engine = create_engine(url)
    names = set(inspect(engine).get_table_names())
    engine.dispose()
    assert "auth_rate_buckets" in names
    assert "auth_account_guards" in names

    command.downgrade(cfg, "0005_email_verification")
    engine = create_engine(url)
    names = set(inspect(engine).get_table_names())
    engine.dispose()
    assert "auth_rate_buckets" not in names
    assert "auth_account_guards" not in names
    command.upgrade(cfg, "head")


def test_login_lockout_matches_for_known_and_unknown_and_uses_the_clock(monkeypatch, caplog):
    _fast_wrong_password(monkeypatch)
    monkeypatch.setattr(auth, "LOCKOUT_THRESHOLDS", (2, 4, 6))
    freeze(FROZEN)
    known = _email()
    unknown = _email()
    _signup(known)
    mail.clear_memory_inbox()
    caplog.set_level(logging.DEBUG)

    assert _login(known, "not-the-password").status_code == 401
    locked = _login(known, "not-the-password")
    assert locked.status_code == 429
    assert locked.json()["detail"] == auth.RATE_LIMITED
    assert known not in locked.text
    assert PASSWORD not in locked.text

    assert _login(unknown, "not-the-password").status_code == 401
    unknown_locked = _login(unknown, "not-the-password")
    assert unknown_locked.status_code == 429
    assert unknown_locked.json() == locked.json()
    assert unknown not in unknown_locked.text

    notices = [item for item in mail.memory_inbox() if item["subject"] == "Ajo sign-in locked"]
    assert len(notices) == 1
    assert notices[0]["to"] == known
    assert known not in notices[0]["body"]
    assert "not-the-password" not in notices[0]["body"]
    assert "/reset-password#" not in notices[0]["body"]
    again = _login(known, "not-the-password")
    assert again.status_code == 429
    assert [item["subject"] for item in mail.memory_inbox()].count("Ajo sign-in locked") == 1

    text = caplog.text
    assert known not in text
    assert unknown not in text
    assert PASSWORD not in text
    assert "not-the-password" not in text

    db = database.SessionLocal()
    try:
        buckets = db.query(database.AuthRateBucket).all()
        guards = db.query(database.AuthAccountGuard).all()
        stored = " ".join(row.subject for row in [*buckets, *guards])
        assert known not in stored
        assert unknown not in stored
        assert "@" not in stored
        assert audit_email.hash_audit_email(known) in stored
        hashes = {
            audit_email.hash_audit_email(known),
            audit_email.hash_audit_email(unknown),
        }
        events = (
            db.query(database.AuthAuditEvent)
            .filter(
                database.AuthAuditEvent.action == "login_lockout",
                database.AuthAuditEvent.email_hash.in_(hashes),
            )
            .all()
        )
        assert len(events) == 2
        assert {event.email_hash for event in events} == hashes
        assert all(known not in (event.email_hash or "") for event in events)
    finally:
        db.close()

    correct = _login(known, PASSWORD)
    assert correct.status_code == 429
    advance(timedelta(minutes=1))
    assert _login(known, "not-the-password").status_code == 401
    assert _login(known, PASSWORD).status_code == 200
    assert _login(known, "not-the-password").status_code == 401


def test_locked_login_timing_matches_for_known_and_unknown(monkeypatch):
    monkeypatch.setattr(auth, "LOCKOUT_THRESHOLDS", (2, 4, 6))
    known = _email()
    unknown = _email()
    _signup(known)
    assert _login(known, "not-the-password").status_code == 401
    assert _login(known, "not-the-password").status_code == 429
    assert _login(unknown, "not-the-password").status_code == 401
    assert _login(unknown, "not-the-password").status_code == 429

    started = time.perf_counter()
    known_again = _login(known, "still-wrong-pass")
    known_elapsed = time.perf_counter() - started
    started = time.perf_counter()
    unknown_again = _login(unknown, "still-wrong-pass")
    unknown_elapsed = time.perf_counter() - started
    assert known_again.json() == unknown_again.json() == {"detail": auth.RATE_LIMITED}
    assert known_elapsed > 0.05
    assert unknown_elapsed > 0.05
    assert max(known_elapsed, unknown_elapsed) / min(known_elapsed, unknown_elapsed) < 4


def test_lockout_duration_steps_up(monkeypatch):
    _fast_wrong_password(monkeypatch)
    monkeypatch.setattr(auth, "LOCKOUT_THRESHOLDS", (2, 4))
    monkeypatch.setattr(
        auth,
        "LOCKOUT_DURATIONS",
        (timedelta(minutes=1), timedelta(minutes=15)),
    )
    freeze(FROZEN)
    email = _email()
    _signup(email)
    assert _login(email, "not-the-password").status_code == 401
    assert _login(email, "not-the-password").status_code == 429
    advance(timedelta(seconds=30))
    assert _login(email, "not-the-password").status_code == 429
    advance(timedelta(seconds=31))
    assert _login(email, "not-the-password").status_code == 401
    assert _login(email, "not-the-password").status_code == 429
    advance(timedelta(minutes=1))
    assert _login(email, "not-the-password").status_code == 429
    advance(timedelta(minutes=14))
    assert _login(email, "not-the-password").status_code == 401


def test_login_is_limited_per_ip_and_ignores_forwarded_for(monkeypatch):
    _fast_wrong_password(monkeypatch)
    monkeypatch.setitem(auth.IP_LIMITS, "login", 2)
    monkeypatch.setattr(auth, "LOCKOUT_THRESHOLDS", (50, 100, 150))
    first = _from("203.0.113.10")
    second = _from("203.0.113.11")
    emails = [_email() for _ in range(3)]
    assert _login(emails[0], "not-the-password", http=first).status_code == 401
    assert _login(emails[1], "not-the-password", http=first).status_code == 401
    blocked = _login(
        emails[2],
        "not-the-password",
        http=first,
        headers={"X-Forwarded-For": "198.51.100.20"},
    )
    assert blocked.status_code == 429
    assert blocked.json()["detail"] == auth.RATE_LIMITED
    assert emails[2] not in blocked.text
    spoofed = _login(
        emails[2],
        "not-the-password",
        http=first,
        headers={"X-Forwarded-For": "198.51.100.21"},
    )
    assert spoofed.json() == blocked.json()
    other_ip = _login(emails[2], "not-the-password", http=second)
    assert other_ip.status_code == 401


def test_login_account_window_resets_on_the_clock(monkeypatch):
    _fast_wrong_password(monkeypatch)
    monkeypatch.setitem(auth.ACCOUNT_LIMITS, "login", 2)
    monkeypatch.setattr(auth, "LOCKOUT_THRESHOLDS", (50, 100, 150))
    freeze(FROZEN)
    email = _email()
    other = _email()
    _signup(email)
    assert _login(email, "not-the-password").status_code == 401
    assert _login(email, "not-the-password").status_code == 401
    blocked = _login(email, "not-the-password")
    assert blocked.status_code == 429
    assert blocked.json()["detail"] == auth.RATE_LIMITED
    assert _login(other, "not-the-password").status_code == 401
    advance(timedelta(minutes=15))
    assert _login(email, "not-the-password").status_code == 401


def test_password_reset_lockout_is_the_same_for_known_and_unknown(monkeypatch):
    monkeypatch.setattr(auth, "LOCKOUT_THRESHOLDS", (2, 4, 6))
    freeze(FROZEN)
    known = _email()
    unknown = _email()
    _signup(known)
    mail.clear_memory_inbox()
    assert client.post("/api/v1/auth/password/forgot", json={"email": known}).status_code == 200
    token = mail.memory_inbox()[-1]["body"].split("/reset-password#", 1)[1].split()[0].strip()
    locked = client.post("/api/v1/auth/password/forgot", json={"email": known})
    missing = client.post("/api/v1/auth/password/forgot", json={"email": unknown})
    missing_again = client.post("/api/v1/auth/password/forgot", json={"email": unknown})
    assert locked.status_code == missing_again.status_code == 429
    assert locked.json() == missing_again.json() == {"detail": auth.RATE_LIMITED}
    assert missing.status_code == 200
    assert known not in locked.text
    assert unknown not in missing_again.text
    notices = [item for item in mail.memory_inbox() if item["subject"] == "Ajo password reset locked"]
    assert len(notices) == 1
    assert token not in notices[0]["body"]
    assert "/reset-password#" not in notices[0]["body"]
    refused = client.post(
        "/api/v1/auth/password/reset",
        json={"token": token, "password": "another-password"},
    )
    assert refused.status_code == 429
    assert refused.json() == locked.json()
    advance(timedelta(minutes=1))
    reset = client.post(
        "/api/v1/auth/password/reset",
        json={"token": token, "password": "another-password"},
    )
    assert reset.status_code == 200, reset.text
    assert _login(known, "another-password").status_code == 200


def test_verification_resend_is_limited_per_account(monkeypatch):
    monkeypatch.setitem(auth.ACCOUNT_LIMITS, "resend_verification", 2)
    monkeypatch.setattr(auth, "LOCKOUT_THRESHOLDS", (50, 100, 150))
    freeze(FROZEN)
    known = _email()
    unknown = _email()
    _signup(known)
    mail.clear_memory_inbox()

    def _resend(address: str):
        return client.post("/api/v1/auth/verification/resend", json={"email": address})

    assert _resend(known).status_code == 200
    assert _resend(known).status_code == 200
    blocked = _resend(known)
    assert _resend(unknown).status_code == 200
    assert _resend(unknown).status_code == 200
    missing = _resend(unknown)
    assert blocked.status_code == missing.status_code == 429
    assert blocked.json() == missing.json() == {"detail": auth.RATE_LIMITED}
    assert known not in blocked.text
    assert unknown not in missing.text
    advance(timedelta(minutes=15))
    assert _resend(known).status_code == 200


def test_production_default_limits_are_strict():
    assert auth.STRICT_IP_LIMITS == {
        "signup": 20,
        "login": 50,
        "password_reset": 20,
        "resend_verification": 20,
    }
    assert auth.STRICT_ACCOUNT_LIMITS == {
        "signup": 5,
        "login": 20,
        "password_reset": 5,
        "resend_verification": 5,
    }
    for env_name in ("", "production", "staging", "live"):
        ip_caps, account_caps = auth.attempt_limits({"AJO_ENV": env_name})
        assert ip_caps == auth.STRICT_IP_LIMITS
        assert account_caps == auth.STRICT_ACCOUNT_LIMITS
    ip_caps, account_caps = auth.attempt_limits({})
    assert ip_caps["password_reset"] == 20
    assert ip_caps["resend_verification"] == 20
    assert account_caps["password_reset"] == 5
    assert account_caps["resend_verification"] == 5
    assert account_caps["signup"] == 5
    assert ip_caps["login"] == 50


def test_relaxed_limits_apply_only_in_local_and_dev(monkeypatch):
    monkeypatch.setattr(auth, "LOCKOUT_THRESHOLDS", (100, 200, 300))
    def _burst(env_name: str, host: str) -> list[int]:
        monkeypatch.setenv("AJO_ENV", env_name)
        monkeypatch.setenv("EMAIL_SENDER", "dev")
        http = _from(host)
        email = _email()
        return [
            http.post("/api/v1/auth/password/forgot", json={"email": email}).status_code
            for _ in range(6)
        ]

    assert auth.limits_relaxed({"AJO_ENV": "local"}) is True
    assert auth.limits_relaxed({"AJO_ENV": "dev"}) is True
    assert auth.limits_relaxed({"AJO_ENV": ""}) is False
    assert auth.limits_relaxed({}) is False
    assert auth.limits_relaxed({"AJO_ENV": "production"}) is False
    local_ip, local_account = auth.attempt_limits({"AJO_ENV": "local"})
    dev_ip, dev_account = auth.attempt_limits({"AJO_ENV": "dev"})
    assert local_ip is auth.IP_LIMITS
    assert dev_ip is auth.IP_LIMITS
    assert local_account["password_reset"] > auth.STRICT_ACCOUNT_LIMITS["password_reset"]
    assert dev_account["resend_verification"] > auth.STRICT_ACCOUNT_LIMITS["resend_verification"]

    assert _burst("local", "203.0.113.70") == [200, 200, 200, 200, 200, 200]
    assert _burst("dev", "203.0.113.71") == [200, 200, 200, 200, 200, 200]
    assert _burst("production", "203.0.113.72") == [503, 503, 503, 503, 503, 429]
    assert _burst("", "203.0.113.73") == [503, 503, 503, 503, 503, 429]
    assert _burst("staging", "203.0.113.74") == [503, 503, 503, 503, 503, 429]


def test_signup_limit_is_the_same_for_a_new_and_existing_email(monkeypatch):
    monkeypatch.setitem(auth.IP_LIMITS, "signup", 2)
    http = _from("203.0.113.40")
    existing = _email()
    _signup(existing, http=http)
    created = http.post(
        "/api/v1/auth/signup",
        json={"name": "Ada Test", "email": _email(), "password": PASSWORD},
    )
    assert created.status_code == 201
    fresh = _email()
    blocked_new = http.post(
        "/api/v1/auth/signup",
        json={"name": "Ada Test", "email": fresh, "password": PASSWORD},
        headers={"X-Forwarded-For": "198.51.100.40"},
    )
    blocked_old = http.post(
        "/api/v1/auth/signup",
        json={"name": "Ada Test", "email": existing, "password": "another-password"},
    )
    assert blocked_new.status_code == blocked_old.status_code == 429
    assert blocked_new.json() == blocked_old.json() == {"detail": auth.RATE_LIMITED}
    assert fresh not in blocked_new.text
    assert existing not in blocked_old.text
    assert _login(existing, PASSWORD).status_code == 200
    db = database.SessionLocal()
    try:
        assert db.query(database.User).filter(database.User.email == fresh).count() == 0
    finally:
        db.close()
