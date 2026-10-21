"""Append-only audit log (#32).

Emails are HMAC-SHA256. The log rejects updates and deletes. The read API
and page are platform-admin only, from the stored role.
"""

from __future__ import annotations

import hashlib
import os
import shutil
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

if "api" not in sys.modules:
    _configured_url = os.environ.get("DATABASE_URL", "")
    if not _configured_url.startswith("postgres"):
        _db_dir = tempfile.mkdtemp(prefix="ajo-audit-")
        os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(_db_dir) / "ajo.db")
    from alembic import command
    from alembic.config import Config

    command.upgrade(Config(str(Path(__file__).resolve().parents[1] / "alembic.ini")), "head")

import jwt
import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import sessionmaker

import api
import audit
import audit_email
import auth
import database
import mail
import roles
from clock import freeze, reset
from database import AuditLog, AuthAuditEvent

client = TestClient(api.app)
PASSWORD = "correct-horse"
NEW_PASSWORD = "replacement-horse"
SECRET_PASSWORD = "horse-battery-staple-secret"
SECRET_TOKEN = "synthetic-reset-token-value"
SECRET_BVN = "12345678901"
SECRET_ETHNICITY = "synthetic-ethnicity-value"
SECRET_ACCOUNT = "11223344"
REPO = Path(__file__).resolve().parents[1]
HEAD = "0008_audit_log"


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("AJO_ENV", "local")
    monkeypatch.setenv("EMAIL_SENDER", "dev")
    monkeypatch.setenv("AUDIT_EMAIL_HMAC_KEY", "test-only-audit-email-hmac-key")
    reset()
    mail.clear_memory_inbox()
    yield
    reset()
    mail.clear_memory_inbox()


def _email() -> str:
    return f"audit-{uuid.uuid4().hex}@example.test"


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _signup_and_token(email: str | None = None) -> tuple[str, str, int]:
    address = email or _email()
    created = client.post(
        "/api/v1/auth/signup",
        json={"name": "Ada Test", "email": address, "password": PASSWORD},
    )
    assert created.status_code == 201, created.text
    body = mail.memory_inbox()[-1]["body"]
    link = body.split("/verify-email#", 1)[1].split()[0].strip()
    confirmed = client.post("/api/v1/auth/verification/confirm", json={"token": link})
    assert confirmed.status_code == 200, confirmed.text
    logged_in = client.post("/api/v1/auth/login", json={"email": address, "password": PASSWORD})
    assert logged_in.status_code == 200, logged_in.text
    token = logged_in.json()["access_token"]
    me = client.get("/api/v1/me", headers=_auth(token))
    assert me.status_code == 200, me.text
    return address, token, me.json()["user_id"]


def _promote(user_id: int) -> None:
    db = database.SessionLocal()
    try:
        audit.grant_platform_admin(db, user_id=user_id, actor_user_id=user_id)
        db.commit()
    finally:
        db.close()


def _blob(row: AuditLog) -> str:
    parts = [
        row.action,
        row.actor_role,
        row.request_id,
        row.ip,
        row.user_agent,
        row.email_hash,
        row.before_values,
        row.after_values,
        row.prev_hash,
        row.entry_hash,
        row.canonical,
    ]
    return " ".join("" if part is None else str(part) for part in parts)


def _assert_no_secrets(blob: str, email: str) -> None:
    assert email not in blob
    assert SECRET_PASSWORD not in blob
    assert PASSWORD not in blob
    assert NEW_PASSWORD not in blob
    assert SECRET_TOKEN not in blob
    assert SECRET_BVN not in blob
    assert SECRET_ETHNICITY not in blob
    assert SECRET_ACCOUNT not in blob
    assert "Bearer " not in blob


def test_migration_is_a_single_head():
    script = ScriptDirectory.from_config(Config(str(REPO / "alembic.ini")))
    assert script.get_heads() == [HEAD]


def test_listed_events_mask_secrets_and_reject_mutation():
    email = _email()
    digest = audit_email.hash_audit_email(email)
    dirty = {
        "password": SECRET_PASSWORD,
        "token": SECRET_TOKEN,
        "bvn": SECRET_BVN,
        "ethnicity": SECRET_ETHNICITY,
        "account_number": SECRET_ACCOUNT,
        "note": f"reach {email} with password={SECRET_PASSWORD}",
        "position": 2,
    }
    db = database.SessionLocal()
    try:
        for action in audit.LISTED_EVENTS:
            audit.record_event(
                db,
                action=action,
                actor_user_id=None,
                circle_id=770001,
                email=email,
                before=dirty,
                after=dict(dirty),
            )
        db.commit()
        stored = db.query(AuditLog).filter(AuditLog.circle_id == 770001).all()
        assert {row.action for row in stored} == set(audit.LISTED_EVENTS)
        for row in stored:
            blob = _blob(row)
            _assert_no_secrets(blob, email)
            assert row.email_hash == digest
            assert "password" not in (row.before_values or "")
            assert "account_number" not in (row.before_values or "")
        assert audit.verify_chain(db) is True

        sample = stored[0]
        sample_id = sample.id
        sample_action = sample.action
        with pytest.raises(PermissionError, match="append-only"):
            sample.action = "tampered"
            db.flush()
        db.rollback()
        with pytest.raises(PermissionError, match="append-only"):
            db.delete(db.get(AuditLog, sample_id))
            db.flush()
        db.rollback()
        with pytest.raises(SQLAlchemyError, match="append-only"):
            db.execute(text("UPDATE audit_log SET action = 'tampered' WHERE id = :id"), {"id": sample_id})
        db.rollback()
        with pytest.raises(SQLAlchemyError, match="append-only"):
            db.execute(text("DELETE FROM audit_log WHERE id = :id"), {"id": sample_id})
        db.rollback()
        kept = db.get(AuditLog, sample_id)
        assert kept is not None
        assert kept.action == sample_action
        assert audit.verify_chain(db) is True
    finally:
        db.close()
    with pytest.raises(ValueError, match="unknown audit action"):
        audit.record_event(database.SessionLocal(), action="Not An Action")


def test_sign_in_reset_verification_and_lockout_use_the_clock_and_hmac():
    moment = datetime(2026, 10, 18, 9, 30, tzinfo=timezone.utc)
    freeze(moment)
    email, token, user_id = _signup_and_token()
    unknown = _email()
    failed = client.post(
        "/api/v1/auth/login",
        json={"email": unknown, "password": SECRET_PASSWORD},
        headers={
            "X-Forwarded-For": "203.0.113.50",
            "User-Agent": "synthetic-agent",
            "X-Request-ID": "req-audit-1",
        },
    )
    assert failed.status_code == 401
    assert failed.json()["detail"] == "Invalid email or password."
    assert unknown not in failed.text

    wrong = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": SECRET_PASSWORD},
        headers={"X-Forwarded-For": "203.0.113.51", "X-Request-ID": unknown},
    )
    assert wrong.status_code == 401

    logged_out = client.post("/api/v1/auth/logout", headers=_auth(token))
    assert logged_out.status_code == 204

    mail.clear_memory_inbox()
    forgot = client.post("/api/v1/auth/password/forgot", json={"email": email})
    assert forgot.status_code == 200, forgot.text
    reset_token = mail.memory_inbox()[-1]["body"].split("/reset-password#token=", 1)[1].split()[0].strip()
    reset = client.post(
        "/api/v1/auth/password/reset",
        json={"token": reset_token, "password": NEW_PASSWORD},
    )
    assert reset.status_code == 200, reset.text

    db = database.SessionLocal()
    try:
        rows = db.query(AuditLog).filter(AuditLog.email_hash == audit_email.hash_audit_email(email)).all()
        actions = {row.action for row in rows}
        assert {"sign_in_success", "sign_in_failure", "logout", "password_reset_requested", "password_reset_completed", "email_verification_sent", "email_verified"} <= actions
        failure = (
            db.query(AuditLog)
            .filter(AuditLog.action == "sign_in_failure", AuditLog.email_hash == audit_email.hash_audit_email(unknown))
            .one()
        )
        assert failure.actor_user_id is None
        assert failure.ip != "203.0.113.50"
        assert failure.request_id == "req-audit-1"
        assert failure.user_agent == "synthetic-agent"
        assert _iso_matches(failure, moment)
        known_failure = (
            db.query(AuditLog)
            .filter(AuditLog.action == "sign_in_failure", AuditLog.target_user_id == user_id)
            .one()
        )
        assert unknown not in _blob(known_failure)
        assert known_failure.request_id != unknown
        for row in db.query(AuditLog).all():
            _assert_no_secrets(_blob(row), email)
            _assert_no_secrets(_blob(row), unknown)
            assert reset_token not in _blob(row)
        success = (
            db.query(AuditLog)
            .filter(AuditLog.action == "sign_in_success", AuditLog.actor_user_id == user_id)
            .order_by(AuditLog.id)
            .first()
        )
        payload = jwt.decode(token, os.environ["JWT_SECRET_KEY"], algorithms=["HS256"], options={"verify_exp": False})
        assert success.session_id == int(payload["sid"])
        audit.record_lockout(db, action="login", email=email, user_id=user_id)
        db.add(
            AuthAuditEvent(
                created_at=moment,
                action="login_lockout",
                user_id=user_id,
                email_hash=audit_email.hash_audit_email(email),
                ip="127.0.0.1",
            )
        )
        db.commit()
        locked = db.query(AuditLog).filter(AuditLog.action == "account_locked", AuditLog.target_user_id == user_id).all()
        assert len(locked) == 2
        assert {row.after_values for row in locked} == {'{"auth_action":"login"}'}
        for row in locked:
            assert email not in _blob(row)
        assert audit.verify_chain(db) is True
    finally:
        db.close()


def _iso_matches(row: AuditLog, moment: datetime) -> bool:
    return audit._iso(row.created_at) == audit._iso(moment)


def test_role_and_position_changes_are_recorded_and_admin_read_is_gated():
    admin_email, admin_token, admin_id = _signup_and_token()
    member_email, member_token, member_id = _signup_and_token()
    created = client.post(
        "/api/v1/circles",
        headers={**_auth(admin_token), "X-Role": "member"},
        json={"name": "Audit Circle", "role": "member"},
    )
    assert created.status_code == 201, created.text
    circle_id = created.json()["circle_id"]
    joined = client.post(
        f"/api/v1/circles/{circle_id}/join",
        headers=_auth(member_token),
        json={"role": "admin"},
    )
    assert joined.status_code == 200, joined.text
    changed = client.post(
        f"/api/v1/circles/{circle_id}/members/{member_id}/role",
        headers={**_auth(admin_token), "X-Role": "member"},
        json={"role": "admin", "actor_role": "member"},
    )
    assert changed.status_code == 200, changed.text

    db = database.SessionLocal()
    try:
        roles.record_position_change(
            db,
            circle_id=circle_id,
            user_id=member_id,
            actor_user_id=admin_id,
            before=1,
            after=3,
        )
        db.commit()
        role_rows = (
            db.query(AuditLog)
            .filter(AuditLog.action == "role_changed", AuditLog.circle_id == circle_id, AuditLog.target_user_id == member_id)
            .all()
        )
        assert any(row.before_values == '{"role":"member"}' and row.after_values == '{"role":"admin"}' for row in role_rows)
        assert any(row.actor_user_id == admin_id and row.actor_role == "admin" for row in role_rows)
        creator = (
            db.query(AuditLog)
            .filter(
                AuditLog.action == "role_changed",
                AuditLog.circle_id == circle_id,
                AuditLog.target_user_id == admin_id,
                AuditLog.after_values == '{"role":"admin"}',
            )
            .one()
        )
        assert creator.before_values == '{"role":null}'
        assert creator.actor_role == "admin"
        position = db.query(AuditLog).filter(AuditLog.action == "payout_position_changed", AuditLog.circle_id == circle_id).one()
        assert position.before_values == '{"position":1}'
        assert position.after_values == '{"position":3}'
        assert db.query(AuditLog).filter(AuditLog.action == "ajo_created", AuditLog.circle_id == circle_id).count() == 1
        assert db.query(AuditLog).filter(AuditLog.action == "ajo_joined", AuditLog.circle_id == circle_id).count() == 1
        payload = jwt.decode(admin_token, os.environ["JWT_SECRET_KEY"], algorithms=["HS256"], options={"verify_exp": False})
        promoted = next(row for row in role_rows if row.after_values == '{"role":"admin"}' and row.actor_user_id == admin_id)
        assert promoted.session_id == int(payload["sid"])
    finally:
        db.close()

    refused = client.get(
        "/api/v1/admin/audit",
        headers={**_auth(admin_token), "X-Role": "platform_admin"},
        params={"role": "platform_admin"},
    )
    assert refused.status_code == 403
    assert refused.json()["detail"] == audit.NOT_ALLOWED
    assert admin_email not in refused.text
    page_refused = client.get("/admin/audit", headers=_auth(member_token))
    assert page_refused.status_code == 403
    missing = client.get("/api/v1/admin/audit")
    assert missing.status_code == 401
    removed = client.delete("/api/v1/admin/audit", headers=_auth(admin_token))
    assert removed.status_code == 405

    _promote(admin_id)
    listed = client.get(
        "/api/v1/admin/audit",
        headers={**_auth(admin_token), "X-Role": "member"},
        params={"role": "member", "circle_id": circle_id, "event_type": "role_changed", "user_id": member_id},
    )
    assert listed.status_code == 200, listed.text
    body = listed.json()
    assert body["before_id"] == body["entries"][-1]["id"]
    assert body["after_id"] == body["entries"][0]["id"]
    assert body["total"] >= 1
    assert all(entry["action"] == "role_changed" for entry in body["entries"])
    assert all(entry["circle_id"] == circle_id for entry in body["entries"])
    assert admin_email not in listed.text
    assert member_email not in listed.text
    assert "password" not in listed.text
    assert "before" in body["entries"][0]
    assert "email" not in body["entries"][0]

    page = client.get(
        "/admin/audit",
        headers=_auth(admin_token),
        params={"circle_id": circle_id, "event_type": "payout_position_changed"},
    )
    assert page.status_code == 200, page.text
    assert "Read-only" in page.text
    assert "payout_position_changed" in page.text
    assert "Delete" not in page.text
    assert "Edit" not in page.text
    assert 'method="post"' not in page.text.lower()
    assert admin_email not in page.text
    assert member_email not in page.text
    assert page.headers["cache-control"] == "no-store"

    db = database.SessionLocal()
    try:
        reads = db.query(AuditLog).filter(AuditLog.action == "audit_log_read", AuditLog.actor_user_id == admin_id).all()
        assert len(reads) >= 2
        denied = db.query(AuditLog).filter(AuditLog.action == "audit_log_denied", AuditLog.actor_user_id == admin_id).count()
        assert denied >= 1
        assert audit.verify_chain(db) is True
    finally:
        db.close()

    again = client.get(
        "/api/v1/admin/audit",
        headers=_auth(admin_token),
        params={"event_type": "audit_log_read", "user_id": admin_id},
    )
    assert again.status_code == 200, again.text
    assert again.json()["total"] >= 2


def test_filters_pagination_and_dates():
    email, token, user_id = _signup_and_token()
    _promote(user_id)
    start = datetime(2026, 5, 1, 8, 0, tzinfo=timezone.utc)
    db = database.SessionLocal()
    try:
        for offset in range(3):
            freeze(start + timedelta(days=offset))
            audit.record_event(
                db,
                action="settings_changed",
                actor_user_id=user_id,
                circle_id=880001,
                after={"n": offset},
            )
        db.commit()
    finally:
        db.close()
    reset()
    window = client.get(
        "/api/v1/admin/audit",
        headers=_auth(token),
        params={"circle_id": 880001, "event_type": "settings_changed", "page_size": 2, "start": "2026-05-01", "end": "2026-05-02"},
    )
    assert window.status_code == 200, window.text
    assert window.json()["total"] == 2
    assert len(window.json()["entries"]) == 2
    first = client.get(
        "/api/v1/admin/audit",
        headers=_auth(token),
        params={"circle_id": 880001, "event_type": "settings_changed", "page_size": 2},
    )
    assert first.status_code == 200, first.text
    assert first.json()["total"] == 3
    assert len(first.json()["entries"]) == 2
    second = client.get(
        "/api/v1/admin/audit",
        headers=_auth(token),
        params={
            "circle_id": 880001,
            "event_type": "settings_changed",
            "page_size": 2,
            "before_id": first.json()["before_id"],
        },
    )
    assert second.status_code == 200, second.text
    assert second.json()["total"] == 3
    assert len(second.json()["entries"]) == 1
    assert second.json()["entries"][0]["id"] < first.json()["before_id"]
    outside = client.get(
        "/api/v1/admin/audit",
        headers=_auth(token),
        params={"circle_id": 880001, "start": "2026-06-01", "end": "2026-06-02"},
    )
    assert outside.status_code == 200
    assert outside.json()["total"] == 0
    bad = client.get("/api/v1/admin/audit", headers=_auth(token), params={"before_id": 0})
    assert bad.status_code == 422
    both = client.get(
        "/api/v1/admin/audit",
        headers=_auth(token),
        params={"before_id": 1, "after_id": 2},
    )
    assert both.status_code == 422


def test_lockout_and_rate_limit_land_in_the_audit_log(monkeypatch):
    monkeypatch.setattr(auth, "LOCKOUT_THRESHOLDS", (2, 4, 6))
    email, _token, user_id = _signup_and_token()
    first = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "not-the-password"},
    )
    assert first.status_code == 401
    locked = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "not-the-password"},
    )
    assert locked.status_code == 429
    assert email not in locked.text
    assert "not-the-password" not in locked.text
    again = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "not-the-password"},
        headers={"X-Forwarded-For": "203.0.113.77"},
    )
    assert again.status_code == 429

    db = database.SessionLocal()
    try:
        digest = audit_email.hash_audit_email(email)
        locked_rows = (
            db.query(AuditLog)
            .filter(AuditLog.action == "account_locked", AuditLog.email_hash == digest)
            .all()
        )
        limited = (
            db.query(AuditLog)
            .filter(AuditLog.action == "rate_limited", AuditLog.email_hash == digest)
            .all()
        )
        assert locked_rows
        assert limited
        assert all(row.after_values == '{"auth_action":"login"}' for row in locked_rows)
        assert all(row.after_values == '{"auth_action":"login"}' for row in limited)
        assert any(row.actor_user_id == user_id for row in locked_rows)
        for row in [*locked_rows, *limited]:
            blob = _blob(row)
            assert email not in blob
            assert "not-the-password" not in blob
            assert "203.0.113.77" not in blob
        assert audit.verify_chain(db) is True
    finally:
        db.close()


AUDIT_COLUMNS = (
    "id",
    "created_at",
    "actor_user_id",
    "actor_role",
    "session_id",
    "request_id",
    "ip",
    "user_agent",
    "circle_id",
    "action",
    "target_user_id",
    "email_hash",
    "before_values",
    "after_values",
    "prev_hash",
    "entry_hash",
    "canonical",
)


def _tampered_value(column: str):
    if column == "id":
        return -1
    if column == "created_at":
        return datetime(1999, 1, 1, tzinfo=timezone.utc)
    if column in {"actor_user_id", "target_user_id", "circle_id", "session_id"}:
        return 9_000_001
    if column in {"prev_hash", "entry_hash", "email_hash"}:
        return hashlib.sha256(f"tamper-{column}".encode()).hexdigest()
    if column == "canonical":
        return '{"tampered":true}'
    if column == "action":
        return "tampered_action"
    if column == "actor_role":
        return "tampered-role"
    if column == "request_id":
        return "tampered-request"
    if column == "ip":
        return "192.0.2.99"
    if column == "user_agent":
        return "tampered-agent"
    if column in {"before_values", "after_values"}:
        return '{"tampered":true}'
    raise AssertionError(column)


@pytest.fixture(scope="module")
def _migrated_audit_sqlite(tmp_path_factory):
    """Schema copy used only to tamper rows. The shared test database stays append-only."""
    directory = tmp_path_factory.mktemp("audit-chain")
    base = directory / "base.db"
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = "sqlite:///" + str(base)
    try:
        command.upgrade(Config(str(REPO / "alembic.ini")), "head")
    finally:
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous
    return base


@pytest.mark.parametrize("column", AUDIT_COLUMNS)
def test_changing_one_stored_column_fails_verification(column, _migrated_audit_sqlite, tmp_path):
    copy_path = tmp_path / "audit.db"
    shutil.copy(_migrated_audit_sqlite, copy_path)
    engine = create_engine("sqlite:///" + str(copy_path), connect_args={"check_same_thread": False})
    db = sessionmaker(bind=engine)()
    try:
        audit.record_event(
            db,
            action="settings_changed",
            actor_user_id=1,
            actor_role="member",
            after={"n": 1},
        )
        second = audit.record_event(
            db,
            action="role_changed",
            actor_user_id=11,
            actor_role="admin",
            session_id=22,
            request_id="req-tamper",
            ip="198.51.100.10",
            user_agent="tamper-agent",
            circle_id=880099,
            target_user_id=12,
            email=_email(),
            before={"role": "member"},
            after={"role": "admin"},
        )
        db.commit()
        assert audit.verify_chain(db) is True
        original = getattr(db.get(AuditLog, second.id), column)
        replacement = _tampered_value(column)
        assert replacement != original
        db.execute(text("DROP TRIGGER IF EXISTS audit_log_append_only_update"))
        db.execute(text("DROP TRIGGER IF EXISTS audit_log_append_only_delete"))
        db.commit()
        db.execute(
            text(f"UPDATE audit_log SET {column} = :value WHERE id = :id"),
            {"value": replacement, "id": second.id},
        )
        db.commit()
        db.expire_all()
        assert audit.verify_chain(db) is False
    finally:
        db.close()
        engine.dispose()


def test_keyset_pages_do_not_repeat_when_the_read_is_logged():
    email, token, user_id = _signup_and_token()
    _promote(user_id)
    db = database.SessionLocal()
    try:
        for offset in range(4):
            audit.record_event(
                db,
                action="settings_changed",
                actor_user_id=user_id,
                circle_id=880003,
                after={"n": offset},
            )
        db.commit()
    finally:
        db.close()
    first = client.get(
        "/api/v1/admin/audit",
        headers=_auth(token),
        params={"circle_id": 880003, "page_size": 2},
    )
    assert first.status_code == 200, first.text
    ids1 = [entry["id"] for entry in first.json()["entries"]]
    assert len(ids1) == 2
    assert ids1 == sorted(ids1, reverse=True)
    second = client.get(
        "/api/v1/admin/audit",
        headers=_auth(token),
        params={"circle_id": 880003, "page_size": 2, "before_id": first.json()["before_id"]},
    )
    assert second.status_code == 200, second.text
    ids2 = [entry["id"] for entry in second.json()["entries"]]
    assert len(ids2) == 2
    assert set(ids1).isdisjoint(ids2)
    assert max(ids2) < min(ids1)


def test_downgrade_removes_the_audit_table(tmp_path, monkeypatch):
    url = "sqlite:///" + str(tmp_path / "audit-down.db")
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config(str(REPO / "alembic.ini"))
    command.upgrade(config, "head")
    command.downgrade(config, "0006_circle_roles")
    from sqlalchemy import create_engine, inspect

    engine = create_engine(url)
    names = set(inspect(engine).get_table_names())
    assert "audit_log" not in names
    assert "audit_chain_lock" not in names
    with engine.connect() as connection:
        columns = {row[1] for row in connection.execute(text("PRAGMA table_info(users)"))}
    assert "platform_role" not in columns
    command.upgrade(config, "head")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO users (name, email, hashed_password) "
                "VALUES ('Ada Test', 'role-check@example.test', 'synthetic-hash-not-a-secret')"
            )
        )
        with pytest.raises(IntegrityError):
            connection.execute(text("UPDATE users SET platform_role = 'owner' WHERE email = 'role-check@example.test'"))
    engine.dispose()
