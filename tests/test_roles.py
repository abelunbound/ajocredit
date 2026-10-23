"""Server-side per-circle roles (#38).

The client never supplies a role. Payouts are admin-only for that circle.
A member of one circle cannot read or change another circle by changing ids.
"""

from __future__ import annotations

import os
import sys
import tempfile
import uuid
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
        _db_dir = tempfile.mkdtemp(prefix="ajo-roles-")
        os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(_db_dir) / "ajo.db")
    from alembic import command
    from alembic.config import Config

    command.upgrade(Config(str(Path(__file__).resolve().parents[1] / "alembic.ini")), "head")

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

import backend.api as api
import backend.database as database
import backend.mail as mail
import backend.roles as roles
from backend.clock import reset

client = TestClient(api.app)
PASSWORD = "correct-horse"
REPO = Path(__file__).resolve().parents[1]


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
    return f"role-{uuid.uuid4().hex}@example.test"


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _verified_token() -> str:
    email = _email()
    created = client.post(
        "/api/v1/auth/signup",
        json={"name": "Ada Test", "email": email, "password": PASSWORD},
    )
    assert created.status_code == 201, created.text
    body = mail.memory_inbox()[-1]["body"]
    token = body.split("/verify-email#", 1)[1].split()[0].strip()
    confirmed = client.post("/api/v1/auth/verification/confirm", json={"token": token})
    assert confirmed.status_code == 200, confirmed.text
    logged_in = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert logged_in.status_code == 200, logged_in.text
    return logged_in.json()["access_token"]


def _circle(token: str, name: str) -> int:
    created = client.post("/api/v1/circles", headers=_auth(token), json={"name": name, "role": "member"})
    assert created.status_code == 201, created.text
    return created.json()["circle_id"]


def _stored_role(circle_id: int, token: str) -> str:
    viewed = client.get(f"/api/v1/circles/{circle_id}", headers=_auth(token))
    assert viewed.status_code == 200, viewed.text
    return viewed.json()["role"]


def test_permission_map_denies_by_default():
    assert roles.permission_allowed("payouts.read", roles.ROLE_ADMIN) is True
    assert roles.permission_allowed("payouts.read", roles.ROLE_MEMBER) is False
    assert roles.permission_allowed("payouts.read", None) is False
    assert roles.permission_allowed("payouts.read", "owner") is False
    assert roles.permission_allowed("circle.read", roles.ROLE_MEMBER) is True
    assert roles.permission_allowed("roles.grant", roles.ROLE_MEMBER) is False
    assert roles.permission_allowed("roles.grant", roles.ROLE_ADMIN) is True
    assert roles.permission_allowed("payouts.release", roles.ROLE_ADMIN) is False
    assert roles.permission_allowed("", roles.ROLE_ADMIN) is False


def test_member_cannot_open_payouts_and_client_role_is_ignored():
    admin_token = _verified_token()
    member_token = _verified_token()
    circle_id = _circle(admin_token, "Payouts Gate")
    joined = client.post(
        f"/api/v1/circles/{circle_id}/join",
        headers=_auth(member_token),
        json={"role": "admin"},
    )
    assert joined.status_code == 200, joined.text
    assert _stored_role(circle_id, admin_token) == "admin"
    assert _stored_role(circle_id, member_token) == "member"

    payouts = f"/api/v1/circles/{circle_id}/payouts"
    allowed = client.get(
        payouts,
        headers={**_auth(admin_token), "X-Role": "member"},
        params={"role": "member"},
    )
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["role"] == "admin"
    assert allowed.json()["circle_id"] == circle_id
    assert "password" not in allowed.text

    denied = client.get(
        payouts,
        headers={**_auth(member_token), "X-Role": "admin"},
        params={"role": "admin"},
    )
    assert denied.status_code == 403
    assert denied.json()["detail"] == roles.DENIED["payouts.read"]
    assert "admin" not in denied.text
    assert "Payouts Gate" not in denied.text

    missing = client.get(payouts)
    assert missing.status_code == 401
    assert "role" not in missing.json()


def test_cross_circle_read_and_role_change_are_denied(monkeypatch):
    changes = []

    def _hook(db, change):
        changes.append(change)

    monkeypatch.setattr(roles, "record_role_change", _hook)

    admin_a = _verified_token()
    admin_b = _verified_token()
    member_b = _verified_token()
    circle_a = _circle(admin_a, "Circle A")
    circle_b = _circle(admin_b, "Circle B")
    assert client.post(f"/api/v1/circles/{circle_b}/join", headers=_auth(member_b)).status_code == 200
    db = database.SessionLocal()
    try:
        target = (
            db.query(database.CircleMember)
            .filter(database.CircleMember.circle_id == circle_b, database.CircleMember.role == "member")
            .one()
        )
        target_id = target.id
        target_user_id = target.user_id
        audit_before = db.query(database.AuthAuditEvent).count()
    finally:
        db.close()

    hidden = client.get(f"/api/v1/circles/{circle_b}", headers=_auth(member_b))
    assert hidden.status_code == 200
    outsider = client.get(f"/api/v1/circles/{circle_a}", headers=_auth(member_b))
    assert outsider.status_code == 404
    assert outsider.json()["detail"] == roles.CIRCLE_NOT_FOUND
    assert "Circle A" not in outsider.text

    other_payouts = client.get(f"/api/v1/circles/{circle_a}/payouts", headers=_auth(admin_b))
    assert other_payouts.status_code == 404
    assert "Circle A" not in other_payouts.text
    assert client.post(f"/api/v1/circles/{circle_b}/join", headers=_auth(admin_a)).status_code == 200

    joined_admin = client.get(f"/api/v1/circles/{circle_b}/payouts", headers=_auth(admin_a))
    assert joined_admin.status_code == 403
    assert joined_admin.json()["detail"] == roles.DENIED["payouts.read"]

    assert client.get(f"/api/v1/circles/{circle_b}", headers=_auth(member_b)).json()["role"] == "member"

    not_in_circle = client.post(
        f"/api/v1/circles/{circle_a}/members/{target_user_id}/role",
        headers=_auth(admin_a),
        json={"role": "admin"},
    )
    assert not_in_circle.status_code == 404
    assert not_in_circle.json()["detail"] == roles.MEMBER_NOT_FOUND

    swapped = client.post(
        f"/api/v1/circles/{circle_b}/members/{target_user_id}/role",
        headers={**_auth(admin_a), "X-Role": "admin"},
        json={"role": "admin", "actor_role": "admin", "circle_id": circle_a},
    )
    assert swapped.status_code == 403
    assert swapped.json()["detail"] == roles.DENIED["roles.grant"]

    self_promote = client.post(
        f"/api/v1/circles/{circle_b}/members/{target_user_id}/role",
        headers=_auth(member_b),
        json={"role": "admin"},
    )
    assert self_promote.status_code == 403

    missing_circle = client.post(
        f"/api/v1/circles/{circle_a}/members/{target_user_id}/role",
        headers=_auth(admin_b),
        json={"role": "member"},
    )
    assert missing_circle.status_code == 404

    db = database.SessionLocal()
    try:
        target = db.get(database.CircleMember, target_id)
        assert target.role == "member"
        assert db.query(database.AuthAuditEvent).count() == audit_before
    finally:
        db.close()

    before_grant = len(changes)
    promoted = client.post(
        f"/api/v1/circles/{circle_b}/members/{target_user_id}/role",
        headers=_auth(admin_b),
        json={"role": "admin", "actor_role": "member"},
    )
    assert promoted.status_code == 200, promoted.text
    assert promoted.json() == {"circle_id": circle_b, "user_id": target_user_id, "role": "admin"}
    assert changes[before_grant].before == "member"
    assert changes[before_grant].after == "admin"
    assert changes[before_grant].circle_id == circle_b
    assert changes[before_grant].user_id == target_user_id
    assert changes[before_grant].actor_user_id is not None

    opened = client.get(f"/api/v1/circles/{circle_b}/payouts", headers=_auth(member_b))
    assert opened.status_code == 200, opened.text
    assert opened.json()["role"] == "admin"

    unchanged = len(changes)
    again = client.post(
        f"/api/v1/circles/{circle_b}/members/{target_user_id}/role",
        headers=_auth(admin_b),
        json={"role": "admin"},
    )
    assert again.status_code == 200
    assert len(changes) == unchanged

    refused = client.post(
        f"/api/v1/circles/{circle_b}/members/{target_user_id}/role",
        headers=_auth(admin_b),
        json={"role": "owner"},
    )
    assert refused.status_code == 422
    db = database.SessionLocal()
    try:
        assert db.get(database.CircleMember, target_id).role == "admin"
    finally:
        db.close()


def test_create_and_join_record_role_changes_and_keep_one_admin(monkeypatch):
    changes = []
    monkeypatch.setattr(roles, "record_role_change", lambda db, change: changes.append(change))

    admin_token = _verified_token()
    member_token = _verified_token()
    circle_id = _circle(admin_token, "Hook Circle")
    assert [change.after for change in changes if change.circle_id == circle_id] == ["admin"]
    assert changes[-1].before is None

    assert client.post(f"/api/v1/circles/{circle_id}/join", headers=_auth(member_token)).status_code == 200
    assert [change.after for change in changes if change.circle_id == circle_id] == ["admin", "member"]
    assert changes[-1].before is None

    db = database.SessionLocal()
    try:
        admin_row = (
            db.query(database.CircleMember)
            .filter(
                database.CircleMember.circle_id == circle_id,
                database.CircleMember.role == "admin",
            )
            .one()
        )
        admin_user_id = admin_row.user_id
    finally:
        db.close()

    demoted = client.post(
        f"/api/v1/circles/{circle_id}/members/{admin_user_id}/role",
        headers=_auth(admin_token),
        json={"role": "member"},
    )
    assert demoted.status_code == 409
    assert demoted.json()["detail"] == roles.LAST_ADMIN
    assert _stored_role(circle_id, admin_token) == "admin"
    assert not any(change.before == "admin" and change.after == "member" for change in changes)


def test_unknown_role_cannot_be_granted():
    with pytest.raises(ValueError, match="unknown role"):
        roles.grant_circle_role(
            None,
            circle_id=1,
            user_id=1,
            role="owner",
            actor_user_id=1,
        )


def test_migration_backfills_creator_admin_and_keeps_one_head(tmp_path, monkeypatch):
    config = Config(str(REPO / "alembic.ini"))
    assert ScriptDirectory.from_config(config).get_heads() == ["0008_audit_log"]

    url = "sqlite:///" + str(tmp_path / "roles.db")
    monkeypatch.setenv("DATABASE_URL", url)
    command.upgrade(config, "0005_email_verification")
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO users (name, email, hashed_password)
                VALUES
                    ('Ada Test', 'creator-backfill@example.test', 'synthetic-hash-not-a-secret'),
                    ('Tunde Test', 'member-backfill@example.test', 'synthetic-hash-not-a-secret')
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO circles (name, created_by_user_id, created_at)
                VALUES ('Backfill Circle', 1, '2026-01-01 00:00:00')
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO circle_members (circle_id, user_id, joined_at)
                VALUES
                    (1, 1, '2026-01-01 00:00:00'),
                    (1, 2, '2026-01-01 00:00:00')
                """
            )
        )

    command.upgrade(config, "head")
    with engine.connect() as connection:
        rows = connection.execute(
            text("SELECT user_id, role FROM circle_members ORDER BY user_id")
        ).all()
    assert [(row[0], row[1]) for row in rows] == [(1, "admin"), (2, "member")]

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO users (name, email, hashed_password)
                VALUES ('Extra Test', 'extra-backfill@example.test', 'synthetic-hash-not-a-secret')
                """
            )
        )
        with pytest.raises(IntegrityError):
            connection.execute(
                text(
                    """
                    INSERT INTO circle_members (circle_id, user_id, role, joined_at)
                    VALUES (1, 3, 'owner', '2026-01-01 00:00:00')
                    """
                )
            )

    command.downgrade(config, "0005_email_verification")
    with engine.connect() as connection:
        columns = {row[1] for row in connection.execute(text("PRAGMA table_info(circle_members)"))}
    assert "role" not in columns
    command.upgrade(config, "head")
    with engine.connect() as connection:
        rows = connection.execute(
            text("SELECT user_id, role FROM circle_members ORDER BY user_id")
        ).all()
    assert [(row[0], row[1]) for row in rows] == [(1, "admin"), (2, "member")]
    assert ScriptDirectory.from_config(config).get_heads() == ["0008_audit_log"]
